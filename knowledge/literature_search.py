"""Issue #327 (ADR-0035): the design loop's one narrow literature-search
tool, scoped exactly to a Material-property or Ink-property library miss
that already carries a Capability warning (issue #324; CONTEXT.md's
"Capability warning").

WHAT THIS IS FOR. ADR-0035 settled the gap: `search_knowledge` can only
search documents a human already ingested, so when nobody has ever measured
a material's/ink's RF properties at all, closing that gap was entirely a
human's job. `search_literature_for_capability_warning` closes it partway --
it finds and cites candidate sources for whoever is reviewing the warning;
it never decides anything on its own.

WHY `material_or_ink_name` IS ITS OWN PARAMETER, NOT READ OFF
`capability_warning`. A Capability-warning entry (`orchestration.
design_loop`'s `{"family", "capability_kind", "capability_property",
"value", "comparator", "unit", "reason"}`) names WHICH DESIGN it is
attached to (`family` -- CONTEXT.md's Design family, e.g. "patch_antenna",
NOT a material's own name -- confirmed against
`tests/test_design_loop.py`'s own `_capability_warning_entry` fixture) and
WHICH PROPERTY of the material/ink source falls short (`capability_property`,
e.g. "eps_r"). Nothing in that shape names the specific material or ink
product (e.g. "FR4", "MXene ink") the warning is actually about -- #324
built no such field, and inventing a heuristic to guess one out of the
free-text `reason` field here would be exactly the kind of parsing/
extraction the charter reserves for the model ("Nothing here parses a
requirement, invents a target, or proposes a geometry" -- CLAUDE.md). Only
the caller -- who holds the full design context the warning entry itself
does not carry -- knows which material/ink is short, so it supplies that
name directly.

WHY IT STILL TAKES THE WHOLE `capability_warning` ENTRY, NOT JUST
`capability_kind`. The issue's own "Blocked by #324" note says this tool
"fires on that mechanism's output shape": the caller already has one
`capability_warnings` entry in hand (from `advance_design_loop_step`'s
result or `inspect_design_loop_state`) and hands it straight to this tool
rather than picking a field out of it first. `capability_kind` gates scope
(see below); `capability_property` (e.g. "eps_r") is folded into the search
query alongside `material_or_ink_name` for precision. `family`/`value`/
`comparator`/`unit`/`reason` describe the gap's own shape (already enforced
by `orchestration.design_loop._validate_capability_warnings` at write time)
and are not read here.

WHY `capability_kind="fabrication"` IS REJECTED. ADR-0035's own
Consequences section is explicit: "The equipment and materials-catalog gaps
... have no equivalent tool, because no queryable source exists for
either" -- a citation-only spec for a human to research by hand, not a
tool this ticket builds. Only "material"/"ink" are literature-searchable
gaps; a "fabrication" entry here is a caller error, raised loudly rather
than silently returning an empty result.

LOCAL CORPUS FIRST, THEN BROADER SOURCES (CLAUDE.md's "search precedent
before inventing"). Both `search_local` (default: `knowledge.search.
search_knowledge`, this project's own already-ingested documents) and
`search_external` (default: `knowledge.sourcing.arxiv.search_arxiv_papers`,
the free, credential-free arXiv discovery search) are always searched --
there is no short-circuit -- and combined into one candidate list, local
matches ordered ahead of external ones, matching the project's own
established convention rather than a new rule invented for this tool. Both
search functions are injectable (same fetch_fn-style seam
`knowledge/sourcing/arxiv.py` already uses) so tests run against recorded/
fake responses only (issue #327's own acceptance criterion) -- no database,
no network.

WHAT A CANDIDATE CARRIES, AND WHY NEVER A SETTLED NUMBER. Per ADR-0035: "A
found paper's reported eps_r/tan_delta (or ink resistivity/cure schedule)
is surfaced to whoever is reviewing the warning ... who decides whether to
add it." Each candidate is `{"source", "title", "identifier", "excerpt"}`:
`excerpt` is the source's own text (a local chunk's content, or an arXiv
abstract) verbatim -- never a value this module parses or extracts out of
it. Parsing a number out of prose is exactly the "library itself never
parses a document" discipline `designs/material_properties.py` already
enforces for a human-entered citation; extending that discipline to a
tool-found one is the same rule, not a new one.

WHAT THIS NEVER DOES (ADR-0035's Decision, and issue #327's AC3): it never
calls `ingest_document`, and it never writes a Material-property/Ink-
property library entry. Finding a source and trusting it as evidence stay
two separate, deliberate steps -- exactly as `search_arxiv_papers` already
keeps them for a general arXiv topic search (knowledge/sourcing/arxiv.py).

WHEN NOTHING IS FOUND (AC2). `found=False` and a `message` stating plainly
what was searched for and that nothing came back -- never an invented or
approximated number. `docs/material-property-literature-research.md`
(produced during this ticket's own design session) models exactly this
honesty for the equivalent by-hand research pass; this is the same
discipline in a tool.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from knowledge.search import search_knowledge
from knowledge.sourcing.arxiv import search_arxiv_papers

SearchLocalFn = Callable[..., list[dict[str, Any]]]
SearchExternalFn = Callable[..., list[dict[str, Any]]]

# The only two Capability-warning `capability_kind` values this tool has a
# literature-search equivalent for -- see this module's docstring's "WHY
# capability_kind='fabrication' IS REJECTED" section.
_SUPPORTED_CAPABILITY_KINDS = frozenset({"material", "ink"})

# Everything this function actually reads off a `capability_warnings` entry
# -- deliberately not the full seven-key shape `orchestration.design_loop.
# _validate_capability_warnings` enforces at write time (`family`/`value`/
# `comparator`/`unit`/`reason` describe the gap, not what to search for --
# see this module's docstring's "WHY material_or_ink_name IS ITS OWN
# PARAMETER" section for why `family` in particular is not a material name).
_REQUIRED_FIELDS = frozenset({"capability_kind", "capability_property"})


class UnsupportedCapabilityWarningError(ValueError):
    """Raised by `search_literature_for_capability_warning` when
    `capability_warning` is missing a required field, `capability_property`
    is blank, `material_or_ink_name` is blank, or `capability_warning`
    names a `capability_kind` this tool has no literature-search equivalent
    for (anything other than "material"/"ink" -- see this module's
    docstring). Named and raised the same way `designs.material_properties.
    InvalidMaterialPropertyError` is: exactly what's wrong, never a bare
    `KeyError`/`ValueError`."""


def _require_nonempty_string(field_name: str, value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise UnsupportedCapabilityWarningError(
            f"{field_name} must be a non-empty string, got {value!r}"
        )
    return value


def search_literature_for_capability_warning(
    capability_warning: dict[str, Any],
    material_or_ink_name: str,
    *,
    max_local_results: int = 5,
    max_external_results: int = 5,
    search_local: SearchLocalFn = search_knowledge,
    search_external: SearchExternalFn = search_arxiv_papers,
) -> dict[str, Any]:
    """Search this project's own knowledge base, then arXiv, for a citable
    measured value for `material_or_ink_name`'s `capability_property` --
    the gap named by one Capability-warning entry (issue #327; ADR-0035).

    `capability_warning` is one entry from a design loop's own
    `capability_warnings` list (CONTEXT.md's Capability warning;
    `orchestration.design_loop`) -- only `capability_kind` and
    `capability_property` are read (see this module's docstring for why
    `family` is not, and never was, a material/ink name).
    `material_or_ink_name` is the specific material or ink product this
    warning is actually about (e.g. "FR4", "MXene ink") -- supplied by the
    caller, since no field on a Capability-warning entry carries it.

    Raises `UnsupportedCapabilityWarningError` if `capability_warning` is
    missing `capability_kind`/`capability_property`, if
    `capability_property`/`material_or_ink_name` is blank, or if
    `capability_kind` is not "material" or "ink" (a "fabrication" gap has
    no literature-search equivalent -- see this module's docstring).

    Returns `{"material_or_ink_name", "capability_kind",
    "capability_property", "found", "candidates", "message"}`. `candidates`
    is a list of `{"source": "local_knowledge" | "arxiv", "title",
    "identifier", "excerpt"}` -- local-knowledge matches first, then arXiv
    matches, never merged or re-ranked against each other (no score fusion,
    matching `knowledge.search.search_knowledge`'s own discipline).
    `excerpt` is the source's own text verbatim (a chunk's content, or an
    arXiv abstract) -- never a number this function parses out of it.
    `found` is `True` iff `candidates` is non-empty; when `False`, `message`
    states plainly what was searched for and that nothing citable came back
    (AC2) -- this function never approximates or invents a value.

    This function never calls `ingest_document` and never writes a
    Material-property/Ink-property library entry, under any input (ADR-0035;
    AC3) -- finding a source and trusting it as evidence stay two separate,
    deliberate steps.

    `search_local`/`search_external` default to the real
    `knowledge.search.search_knowledge` / `knowledge.sourcing.arxiv.
    search_arxiv_papers` and exist so tests can inject a fake instead of
    hitting a database or the network (AC4) -- the same seam
    `knowledge/sourcing/arxiv.py`'s `fetch_fn` parameter already gives every
    other sourcing client in this package.
    """
    missing = _REQUIRED_FIELDS - capability_warning.keys()
    if missing:
        raise UnsupportedCapabilityWarningError(
            f"capability_warning is missing required field(s): {sorted(missing)}"
        )

    capability_property = _require_nonempty_string(
        "capability_warning['capability_property']", capability_warning["capability_property"]
    )
    material_or_ink_name = _require_nonempty_string("material_or_ink_name", material_or_ink_name)
    capability_kind = capability_warning["capability_kind"]
    if capability_kind not in _SUPPORTED_CAPABILITY_KINDS:
        raise UnsupportedCapabilityWarningError(
            f"capability_warning['capability_kind'] must be one of "
            f"{sorted(_SUPPORTED_CAPABILITY_KINDS)} to search literature for -- got "
            f"{capability_kind!r}. A 'fabrication' gap (equipment/machine capability) has "
            "no literature-search equivalent (ADR-0035); it stays a citation-only spec for "
            "a human to research by hand."
        )

    query = f"{material_or_ink_name} {capability_property}"

    candidates: list[dict[str, Any]] = []
    for row in search_local(query, limit=max_local_results):
        candidates.append(
            {
                "source": "local_knowledge",
                "title": row.get("document_title"),
                "identifier": row.get("document_id"),
                "excerpt": row.get("content"),
            }
        )
    for row in search_external(query, max_results=max_external_results):
        candidates.append(
            {
                "source": "arxiv",
                "title": row.get("title"),
                "identifier": row.get("id"),
                "excerpt": row.get("abstract"),
            }
        )

    found = bool(candidates)
    message = None
    if not found:
        message = (
            f"no citable literature found for {capability_kind}={material_or_ink_name!r} "
            f"property={capability_property!r} -- searched this project's own knowledge "
            "base and arXiv; neither returned a match. A human still has to research this "
            "by hand before a Material-property/Ink-property library entry can be added "
            "(this tool never writes one itself)."
        )

    return {
        "material_or_ink_name": material_or_ink_name,
        "capability_kind": capability_kind,
        "capability_property": capability_property,
        "found": found,
        "candidates": candidates,
        "message": message,
    }
