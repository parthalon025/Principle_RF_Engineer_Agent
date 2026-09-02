"""Component identity resolution across distributor sources (ticket #67).

Reconciles the same physical part -- found via more than one of
`knowledge/digikey.py`, `knowledge/mouser.py`, `knowledge/nexar.py` -- into
one `components` row rather than a duplicate per distributor. CONTEXT.md's
Component vocabulary is the exact contract this module honors: identity is
`(manufacturer, part_number)` with *package and tape-and-reel suffix
included as part of that identity* -- "a different package is a different
component, not a variant of the same row." `db/schema.sql` already enforces
`UNIQUE(manufacturer, part_number)` and `knowledge/db.py`'s
`upsert_component` already does exact-match upsert-by-that-pair; what this
module adds is the *normalization* needed for two distributors' differing
formatting of the same manufacturer/part-number string to actually collide
on that exact-match key instead of silently becoming two rows over
whitespace/case noise -- and the *grouping* that turns N raw distributor
hits describing the same part into exactly one `upsert_component` call.

Deliberately narrow scope: this module reconciles IDENTITY (which raw
distributor hits describe the same physical part) and ensures ONE row per
resolved identity exists. It does not itself populate or merge per-field
specifications with confidence/provenance -- that remains
`knowledge/extract.py`'s job (ticket #11), run separately over whichever
ingested datasheet(s) this reconciliation points at. Building spec-merging
logic here too would duplicate `extract.py`'s existing provenance/
confidence machinery instead of reusing it (this repo's "search-before-
write, reuse beats reinvention" convention).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

import psycopg

from knowledge import db
from knowledge.models import ComponentCategory
from knowledge.sourcing_common import ComponentMatch

_WHITESPACE_RE = re.compile(r"\s+")


def normalize_manufacturer(name: str) -> str:
    """Casefold + collapse/trim whitespace, for *comparison* only -- the
    canonical stored value is whichever record's original string is picked
    as its group's representative (see `resolve_identity`), never this
    normalized form.

    Deliberately does NOT strip corporate suffixes ("Inc.", "Ltd.",
    "Corp.") or attempt fuzzy/edit-distance matching: CONTEXT.md's identity
    model has no tolerance for treating two similarly-named but different
    manufacturers as the same one, and this repo's "never silently
    degrade" stance means a formatting difference this function doesn't
    recognize should fail to merge (two rows, safely over-cautious) rather
    than risk merging two different companies into one.
    """
    return _WHITESPACE_RE.sub(" ", name).strip().casefold()


def normalize_part_number(part_number: str) -> str:
    """Uppercase + remove ALL whitespace, for *comparison* only.

    Deliberately does NOT strip or normalize hyphens/underscores or any
    other punctuation: CONTEXT.md is explicit that a component's package
    and tape-and-reel suffix are part of its identity, not a variant to
    collapse away, and a real manufacturer part-numbering scheme routinely
    uses exactly those characters to distinguish one orderable package/reel
    option from another (e.g. TI's "LM358DR" SOIC-8/reel vs "LM358PWR"
    TSSOP-8/reel; Analog Devices' "-R7"/"-RL7" reel-size suffixes).
    Collapsing punctuation to chase distributor formatting noise would risk
    exactly the false-positive merge CONTEXT.md rules out -- only the
    unambiguous noise (surrounding/embedded whitespace, letter case) is
    normalized here.

    Known, deliberate limitation: a distributor that formats the identical
    part number with, say, a stray extra hyphen another distributor omits
    will NOT be reconciled by this function -- a false negative (two rows
    survive where a human would see one part), chosen over the opposite,
    worse failure mode of silently merging two genuinely different
    orderable parts.
    """
    return _WHITESPACE_RE.sub("", part_number).upper()


@dataclass(frozen=True)
class ResolvedComponentIdentity:
    """One physical part, as agreed on by every distributor hit grouped
    into it. `manufacturer`/`part_number` are the *first* group member's
    original (non-normalized) strings -- a deterministic pick, not a
    synthesized "prettiest string" merge -- since normalization
    (`normalize_manufacturer`/`normalize_part_number`) is for comparison
    only, never for what gets stored."""

    manufacturer: str | None
    part_number: str
    sources: list[ComponentMatch]


def resolve_identity(matches: list[ComponentMatch]) -> list[ResolvedComponentIdentity]:
    """Group raw distributor `ComponentMatch` hits by normalized
    `(manufacturer, part_number)` identity, preserving first-seen order
    both across and within groups (deterministic output for a given input
    order, and for `reconcile_components`'s "first entry with a datasheet_
    document_id wins" rule below)."""
    groups: dict[tuple[str, str], list[ComponentMatch]] = {}
    order: list[tuple[str, str]] = []
    for match in matches:
        key = (
            normalize_manufacturer(match.manufacturer) if match.manufacturer else "",
            normalize_part_number(match.manufacturer_part_number),
        )
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(match)

    resolved: list[ResolvedComponentIdentity] = []
    for key in order:
        members = groups[key]
        first = members[0]
        resolved.append(
            ResolvedComponentIdentity(
                manufacturer=first.manufacturer,
                part_number=first.manufacturer_part_number,
                sources=members,
            )
        )
    return resolved


def reconcile_components(
    conn: psycopg.Connection,
    matches: list[ComponentMatch],
    category: ComponentCategory,
    *,
    datasheet_document_ids: dict[str, int] | None = None,
) -> list[dict[str, Any]]:
    """Resolve `matches` (typically the combined hits from
    `lookup_digikey_datasheet`/`lookup_mouser_datasheet`/
    `lookup_nexar_datasheet` for the same queried part number) into one
    `components` row per distinct physical part, via
    `knowledge.db.upsert_component` -- ONE call per resolved identity, not
    one per distributor hit, so two- or three-source agreement collapses
    to a single row instead of duplicates.

    Existing specifications are preserved: for each resolved identity, any
    `components` row already stored under that exact `(manufacturer,
    part_number)` (typically populated by a prior `extract_components`
    run, ticket #11) has its `specifications` read via `knowledge.db.
    get_component` and passed straight back through, rather than being
    wiped by `upsert_component`'s wholesale-overwrite `specifications={}`
    default -- this module has no per-field spec data of its own to offer
    (see module docstring), so it must not destroy real data it can't
    replace with anything better.

    `datasheet_document_ids`, if given, maps `ComponentMatch.distributor`
    -> the `documents.id` that distributor's datasheet was ingested as
    (i.e. each lookup call's own `ingest_result["document_id"]`); the
    first resolved-group member (in `matches`' original order) with an
    entry in that map wins as the stored `datasheet_document_id`, so a
    group's canonical row still links back to a real ingested document
    when at least one source's ingest succeeded. Omitted or no entry for
    any group member -> the group's existing `datasheet_document_id` (if
    any) is preserved, same reasoning as `specifications` above.

    `category` is caller-supplied (an RF `ComponentCategory`) rather than
    inferred from any distributor's own, differently-shaped catalog
    taxonomy -- none of Digi-Key/Mouser/Nexar categorize into this repo's
    ten RF-specific categories, so guessing one here would be exactly the
    kind of invented-not-verified behavior CLAUDE.md rules out.

    Returns one dict per resolved identity: `{"manufacturer",
    "part_number", "sources": [distributor names that agreed], "row": the
    stored components row}`.
    """
    datasheet_document_ids = datasheet_document_ids or {}
    stored: list[dict[str, Any]] = []
    for identity in resolve_identity(matches):
        existing = db.get_component(conn, identity.manufacturer, identity.part_number)

        datasheet_document_id = next(
            (
                datasheet_document_ids[m.distributor]
                for m in identity.sources
                if m.distributor in datasheet_document_ids
            ),
            existing["datasheet_document_id"] if existing else None,
        )
        specifications = existing["specifications"] if existing else {}

        row = db.upsert_component(
            conn,
            manufacturer=identity.manufacturer,
            part_number=identity.part_number,
            category=category.value,
            specifications=specifications,
            datasheet_document_id=datasheet_document_id,
        )
        stored.append(
            {
                "manufacturer": identity.manufacturer,
                "part_number": identity.part_number,
                "sources": [m.distributor for m in identity.sources],
                "row": row,
            }
        )
    return stored


def _match_from_raw(raw: ComponentMatch | dict[str, Any]) -> ComponentMatch:
    if isinstance(raw, ComponentMatch):
        return raw
    return ComponentMatch(
        distributor=raw["distributor"],
        manufacturer=raw.get("manufacturer"),
        manufacturer_part_number=raw["manufacturer_part_number"],
        datasheet_url=raw.get("datasheet_url"),
    )


def reconcile_components_from_matches(
    matches: list[ComponentMatch | dict[str, Any]],
    category: str,
    *,
    datasheet_document_ids: dict[str, int] | None = None,
) -> dict[str, Any]:
    """Tool-facing entrypoint that owns its own DB connection (open,
    commit, rollback-on-exception, close) -- unlike `reconcile_components`
    above, which takes an already-open connection per `knowledge/db.py`'s
    own convention and is what this repo's tests call directly (see
    tests/test_component_resolution.py). Mirrors
    `knowledge.extract.extract_components`'s connection-lifecycle shape,
    since this is the function `agent/main.py`'s
    `reconcile_component_sources` tool and `mcp_server/server.py`'s
    equivalent both call.

    `matches` accepts either `ComponentMatch` instances or plain dicts with
    (at least) "distributor" and "manufacturer_part_number" keys -- the
    exact shape a `lookup_digikey_datasheet`/`lookup_mouser_datasheet`/
    `lookup_nexar_datasheet` result already carries -- so an agent tool
    call (which can only pass JSON-serializable arguments) can hand this
    function those results' fields directly.

    `category` is a `ComponentCategory` value string (e.g. "amplifier");
    an invalid value raises `ValueError` via `ComponentCategory(category)`,
    same as every other category-accepting entry point in this repo
    (`knowledge/extract.py`'s `_store_component`).
    """
    parsed_matches = [_match_from_raw(m) for m in matches]
    category_enum = ComponentCategory(category)

    conn = db.get_connection()
    try:
        reconciled = reconcile_components(
            conn, parsed_matches, category_enum, datasheet_document_ids=datasheet_document_ids
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    return {"status": "reconciled", "components": reconciled}
