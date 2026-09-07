"""Persistent, cross-run Material-property library (issue #154; ADR-0015;
CONTEXT.md: Material-property library, Family fallback bracket,
Requirement-derived constraint).

ADR-0015 and issue #148 settled the design; that decision was accepted but
never built (a 2026-09-04 repo sweep found no `material_propert*`/
`MaterialProperty`/`family_fallback` implementation anywhere in the tree).
This module is that implementation.

THE ONE THING THIS MODULE IS FOR. A material's permittivity, loss tangent,
or conductivity is a fact about the material, not about any one customer
requirement -- unlike a Requirement-derived constraint (a threshold, a bend
radius), which is re-derived fresh every design pass and never carried
forward, a material property accumulates once in this library and is
reused by every future design that references that material. See
`designs/requirement_targets.py`'s own module docstring for the contrasting
case this library is a deliberate, named exception to.

WHY EVERY MATCHING CITATION IS RETURNED, NEVER COLLAPSED TO ONE NUMBER.
Issue #154's own worked example is the reason this module exists in this
particular shape: three independent, peer-reviewed X-band FR4 papers report
epsilon_r as 4.3, 4.4, and 4.4, and loss tangent as 0.025, 0.02, and
0.024 -- roughly 2% disagreement on epsilon_r and up to 25% on tan_delta,
for "the same" material. Silently averaging those into one hardcoded
constant, or picking whichever citation happened to be entered first,
would quietly assume the answer for tan_delta -- typically the property
that decides an absorber's score. So `lookup_entries`/
`resolve_material_property` return every citation that matches a
(material, property, frequency) query, never one merged value; a caller
building a score from them sees the full disagreement, not a false
precision.

WHY AN ENTRY'S FREQUENCY IS A BAND, NOT A SINGLE POINT. CONTEXT.md
describes the library as "keyed by (material, frequency, property)", and a
literal single-point key would fit a caller who typed one bare number. But
every real citation this ticket seeds the library with reports a validity
band ("epsilon_r = 4.3 ... across 7-10 GHz"), not a single test frequency --
a citation that only ever held at one exact Hz value would be a strange
thing for a materials paper to report. `add_entry` therefore takes
`frequency_low_hz`/`frequency_high_hz` (equal for a caller who genuinely
has just one point, e.g. a datasheet's single test condition), and a lookup
matches a query frequency against that band. This is an implementation
decision about how to store what a citation actually says, not a new
design question requiring its own ADR -- the (material, frequency, property)
key ADR-0015 names is preserved; only "frequency" is modeled as the
interval a real citation is valid over, matching #148's own repeated
concern that a fact about a material must not be reported more precisely
than it actually is.

WHAT COUNTS AS AN ENTRY'S PROVENANCE. ADR-0015 gives exactly three ways a
human adds an entry: citing a manufacturer datasheet
(`MANUFACTURER-SPECIFIED`), citing a paper (`LITERATURE-SUPPORTED` --
this project's own existing source-type convention for a `paper`,
`knowledge/provenance.py`), or typing a bare value with a one-line note of
where it came from, even "no source, just entering it" (`ASSUMED`).
`ENTRY_PROVENANCE_VALUES` is exactly that three-value subset of
CONTEXT.md's fixed 8-value Provenance vocabulary -- not the full set, and
not a new tier invented for this feature (the same discipline
`designs/requirement_targets.py` already applies to its own `ASSUMED`-only
tagging). A `MANUFACTURER-SPECIFIED`/`LITERATURE-SUPPORTED` entry must
carry a real `citation` (the library "never parses a document itself, only
cites it" -- ADR-0015); an `ASSUMED` entry must carry a `note` explaining
where the number came from, even if that explanation is "no source".
Neither is optional for its tier: an uncited "spec" entry or an unexplained
guess would defeat the entire point of a provenance-tagged library.

FAMILY FALLBACK BRACKET, NEVER A BORROWED POINT VALUE. When no entry exists
for the exact material asked for, ADR-0015 requires a cited MIN/MAX range
for the material's broad family (e.g. "generic polymer"), not a single
number borrowed from something similar -- #127's own worked example (a
substrate whose "no data anywhere" turned out to be a fetch failure, not a
fact, and an absorber material whose datasheet published attenuation but
not loss tangent) showed that a single borrowed point value quietly
decides the result for whichever property matters most. `add_family_bracket`
enforces `max_value >= min_value` and requires both ends independently
cited; `resolve_material_property` only reaches for a caller-supplied
bracket after confirming no per-material entry exists.

WHAT resolve_material_property NEVER DOES: invent a number. A material with
no per-material entry AND no family bracket supplied comes back
`status="no_data"`, with a message explaining exactly what was looked for
-- the same "excluded with the reason stated, never silently dropped"
treatment CONTEXT.md's Fabrication capability gives a failed capability
check. #127's rejected alternative ("silently excluding a candidate with
no data") is exactly the failure mode this refuses to reproduce.

MODULE SHAPE. Two layers, the same pure/I-O seam
`designs/requirement_targets.py` already establishes for this package:

  - Pure, DB-free functions (`add_entry`, `add_family_bracket`,
    `lookup_entries`, `resolve_material_property`) -- all of this ticket's
    actual validation/lookup/fallback logic, exhaustively unit-tested in
    `tests/test_material_properties.py` with no database needed.
  - Thin I/O wrappers (`insert_material_property_entry`,
    `insert_family_bracket`, `fetch_material_property_entries`,
    `fetch_family_bracket`, `resolve_material_property_from_db`) -- read/write
    the `material_properties`/`material_family_brackets` tables
    (`db/schema.sql`) directly with their own small amount of raw SQL,
    mirroring `designs/db.py`'s no-ORM style. Not unit-tested here for the
    same documented reason `designs/requirement_targets.py`'s own I/O
    wrappers aren't: there is no live DATABASE_URL in this sandbox. They are
    thin glue over the pure functions above, which carry all the real logic
    and are fully covered.

FR4_SEED_ENTRIES: the issue's own three independently-cited X-band FR4
measurements (epsilon_r and tan_delta each), pulled from a separate
literature corpus (`F:\\data\\rf_metamaterials\\`) during the 2026-09-04
sweep that found this feature unbuilt. Given here as real `add_entry` output
-- both the library's first real content and a live worked example of why it
stores a value per citation (see "WHY EVERY MATCHING CITATION..." above).
A human/agent inserts them into a real database via
`insert_material_property_entry`; nothing in this module does that
automatically -- ADR-0015 is explicit that the library is filled in by a
human citing a source, never auto-seeded as a side effect of importing a
module.
"""

from __future__ import annotations

import math
from typing import Any

import psycopg
from psycopg.rows import dict_row

from designs.requirement_targets import ASSUMED
from knowledge.provenance import LITERATURE_SUPPORTED, MANUFACTURER_SPECIFIED

# The three provenance tiers ADR-0015 allows a Material-property library
# entry to carry -- a closed subset of CONTEXT.md's fixed Provenance
# vocabulary, not the full 8-value set (see this module's docstring).
ENTRY_PROVENANCE_VALUES = frozenset({MANUFACTURER_SPECIFIED, LITERATURE_SUPPORTED, ASSUMED})

_CITATION_REQUIRED_PROVENANCE = frozenset({MANUFACTURER_SPECIFIED, LITERATURE_SUPPORTED})


class InvalidMaterialPropertyError(ValueError):
    """Raised by `add_entry`/`add_family_bracket`/`resolve_material_property`
    when the shape they were handed is wrong -- an empty `material`/
    `property_name`/`family`, a non-finite `value`/`frequency`, a negative
    or inverted frequency band, a `provenance` outside
    `ENTRY_PROVENANCE_VALUES`, a missing `citation` for a
    `MANUFACTURER-SPECIFIED`/`LITERATURE-SUPPORTED` entry, a missing `note`
    for an `ASSUMED` entry, an inverted family bracket, or a set of matching
    entries that disagree on unit. Named and raised the same way
    `designs.requirement_targets.InvalidRequirementTargetError` is -- naming
    exactly what's wrong rather than a bare `TypeError`/`KeyError`."""


def _require_nonempty_string(field_name: str, value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise InvalidMaterialPropertyError(
            f"{field_name} must be a non-empty string, got {value!r}"
        )
    return value


def _require_finite_number(field_name: str, value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise InvalidMaterialPropertyError(f"{field_name} must be a real number, got {value!r}")
    numeric = float(value)
    if not math.isfinite(numeric):
        raise InvalidMaterialPropertyError(f"{field_name} must be finite, got {value!r}")
    return numeric


def _require_nonnegative_finite_number(field_name: str, value: Any) -> float:
    numeric = _require_finite_number(field_name, value)
    if numeric < 0:
        raise InvalidMaterialPropertyError(f"{field_name} must be >= 0, got {value!r}")
    return numeric


def add_entry(
    material: str,
    property_name: str,
    frequency_low_hz: float,
    frequency_high_hz: float,
    value: float,
    unit: str,
    provenance: str,
    citation: str | None = None,
    note: str | None = None,
) -> dict[str, Any]:
    """Validate and tag one Material-property library entry (ADR-0015).

    `material` and `property_name` (e.g. `"eps_r"`, `"tan_delta"`,
    `"conductivity_s_per_m"`) and `unit` must be non-empty strings.
    `frequency_low_hz`/`frequency_high_hz` must be finite and >= 0, with
    `frequency_high_hz >= frequency_low_hz` -- a caller with a single test
    frequency passes the same value for both (see this module's docstring's
    "WHY AN ENTRY'S FREQUENCY IS A BAND" section). `value` must be a real,
    finite number.

    `provenance` must be one of `ENTRY_PROVENANCE_VALUES`
    (`MANUFACTURER-SPECIFIED`, `LITERATURE-SUPPORTED`, `ASSUMED`).
    `MANUFACTURER-SPECIFIED`/`LITERATURE-SUPPORTED` require a non-empty
    `citation` (the library never parses a document itself, only cites it);
    `ASSUMED` requires a non-empty `note` (a one-line note of where the
    value came from, even "no source, just entering it").

    Raises `InvalidMaterialPropertyError` naming exactly which field is
    wrong -- never coerces or guesses a fixed-up value.
    """
    resolved_material = _require_nonempty_string("material", material)
    resolved_property = _require_nonempty_string("property_name", property_name)
    resolved_unit = _require_nonempty_string("unit", unit)

    low = _require_nonnegative_finite_number("frequency_low_hz", frequency_low_hz)
    high = _require_nonnegative_finite_number("frequency_high_hz", frequency_high_hz)
    if high < low:
        raise InvalidMaterialPropertyError(
            f"frequency_high_hz ({high!r}) must be >= frequency_low_hz ({low!r})"
        )

    resolved_value = _require_finite_number("value", value)

    if provenance not in ENTRY_PROVENANCE_VALUES:
        raise InvalidMaterialPropertyError(
            f"provenance must be one of {sorted(ENTRY_PROVENANCE_VALUES)}, got {provenance!r}"
        )

    if provenance in _CITATION_REQUIRED_PROVENANCE:
        if not isinstance(citation, str) or not citation.strip():
            raise InvalidMaterialPropertyError(
                f"a {provenance} entry requires a non-empty citation -- the "
                "Material-property library never parses a document itself, "
                "only cites it (ADR-0015)"
            )
    else:  # ASSUMED
        if not isinstance(note, str) or not note.strip():
            raise InvalidMaterialPropertyError(
                "an ASSUMED entry requires a non-empty note explaining where "
                'the value came from, even "no source, just entering it" '
                "(ADR-0015)"
            )

    return {
        "material": resolved_material,
        "property": resolved_property,
        "frequency_low_hz": low,
        "frequency_high_hz": high,
        "value": resolved_value,
        "unit": resolved_unit,
        "provenance": provenance,
        "citation": citation,
        "note": note,
    }


def add_family_bracket(
    family: str,
    property_name: str,
    min_value: float,
    min_citation: str,
    max_value: float,
    max_citation: str,
    unit: str,
) -> dict[str, Any]:
    """Validate and build one Family fallback bracket (ADR-0015): a cited
    `[min_value, max_value]` range for a material family's broad property
    (e.g. "generic polymer" epsilon_r), used only when no per-material
    library entry exists yet. Both ends must be independently, non-emptily
    cited -- a bracket is never a single borrowed point value, and never an
    uncited number (see this module's docstring's "FAMILY FALLBACK
    BRACKET" section). `max_value` must be `>= min_value`.
    """
    resolved_family = _require_nonempty_string("family", family)
    resolved_property = _require_nonempty_string("property_name", property_name)
    resolved_unit = _require_nonempty_string("unit", unit)
    resolved_min_citation = _require_nonempty_string("min_citation", min_citation)
    resolved_max_citation = _require_nonempty_string("max_citation", max_citation)

    resolved_min = _require_finite_number("min_value", min_value)
    resolved_max = _require_finite_number("max_value", max_value)
    if resolved_max < resolved_min:
        raise InvalidMaterialPropertyError(
            f"max_value ({resolved_max!r}) must be >= min_value ({resolved_min!r})"
        )

    return {
        "family": resolved_family,
        "property": resolved_property,
        "min_value": resolved_min,
        "min_citation": resolved_min_citation,
        "max_value": resolved_max,
        "max_citation": resolved_max_citation,
        "unit": resolved_unit,
    }


def _entry_matches(
    entry: dict[str, Any], material: str, property_name: str, frequency_hz: float
) -> bool:
    return (
        entry["material"] == material
        and entry["property"] == property_name
        and entry["frequency_low_hz"] <= frequency_hz <= entry["frequency_high_hz"]
    )


def lookup_entries(
    entries: list[dict[str, Any]], material: str, property_name: str, frequency_hz: float
) -> list[dict[str, Any]]:
    """Return every stored entry matching `(material, property_name)` whose
    frequency band covers `frequency_hz` -- ALL of them, in the order given,
    never merged or reduced to one. `entries` is whatever the caller already
    fetched (in production, `fetch_material_property_entries`'s result; in a
    test, a hand-built or `FR4_SEED_ENTRIES`-derived list) -- this function
    itself never touches a database, so it composes with either."""
    return [e for e in entries if _entry_matches(e, material, property_name, frequency_hz)]


def resolve_material_property(
    entries: list[dict[str, Any]],
    material: str,
    property_name: str,
    frequency_hz: float,
    family: str | None = None,
    family_bracket: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """The Material-property library's one lookup entry point (ADR-0015;
    CONTEXT.md: Material-property library, Family fallback bracket).

    1. If any per-material entry matches `(material, property_name,
       frequency_hz)` (`lookup_entries`), return every one of them plus the
       `low`/`high` value spread across them (`low == high` when exactly one
       entry matches, or when several happen to agree) -- `status =
       "material_entries"`. All matching entries must share the same `unit`;
       a mismatch raises `InvalidMaterialPropertyError` rather than silently
       comparing incompatible numbers.
    2. Otherwise, if a `family_bracket` is supplied (fetched by the caller
       for `family`), return its cited `[min_value, max_value]` range --
       `status = "family_fallback"`. `family_bracket["family"]` and
       `["property"]` must match `family`/`property_name`, or this raises
       (a caller-supplied bracket for the wrong family/property would
       silently mislead).
    3. Otherwise, `status = "no_data"` with a `message` naming exactly what
       was looked for and found nothing -- never an invented number (#127's
       rejected "silently excluding a candidate with no data").

    Every branch carries `material`, `property`, and `frequency_hz` for
    traceability; branches 1 and 2 also carry `low`/`high`/`unit` so a
    caller can treat them uniformly (e.g.
    `orchestration.design_loop._handle_analysis`'s "compute at both ends of
    the range" wiring -- ADR-0015's Consequences section).
    """
    matches = lookup_entries(entries, material, property_name, frequency_hz)
    if matches:
        units = {m["unit"] for m in matches}
        if len(units) > 1:
            raise InvalidMaterialPropertyError(
                f"matching Material-property library entries for material={material!r} "
                f"property={property_name!r} disagree on unit: {sorted(units)} -- cannot "
                "compute a value spread across incompatible units"
            )
        values = [m["value"] for m in matches]
        return {
            "status": "material_entries",
            "material": material,
            "property": property_name,
            "frequency_hz": frequency_hz,
            "low": min(values),
            "high": max(values),
            "unit": units.pop(),
            "entries": matches,
        }

    if family_bracket is not None:
        if family is None:
            raise InvalidMaterialPropertyError(
                "family_bracket was supplied without a family -- pass the "
                "family name the bracket applies to"
            )
        bracket_family = family_bracket.get("family")
        bracket_property = family_bracket.get("property")
        if bracket_family != family or bracket_property != property_name:
            raise InvalidMaterialPropertyError(
                f"family_bracket is for family={bracket_family!r} "
                f"property={bracket_property!r}, which does not match "
                f"the requested family={family!r} property={property_name!r}"
            )
        return {
            "status": "family_fallback",
            "material": material,
            "family": family,
            "property": property_name,
            "frequency_hz": frequency_hz,
            "low": family_bracket["min_value"],
            "high": family_bracket["max_value"],
            "unit": family_bracket["unit"],
            "min_citation": family_bracket["min_citation"],
            "max_citation": family_bracket["max_citation"],
        }

    return {
        "status": "no_data",
        "material": material,
        "property": property_name,
        "frequency_hz": frequency_hz,
        "message": (
            f"no Material-property library entry for material={material!r} "
            f"property={property_name!r} at {frequency_hz:g} Hz, and no Family "
            "fallback bracket was supplied -- CONTEXT.md's Material-property "
            "library: a missing entry with no family bracket available is "
            "reported, never silently guessed (#127's own TPU history)."
        ),
    }


# ---------------------------------------------------------------------------
# FR4_SEED_ENTRIES -- issue #154's three real, independently-cited X-band
# FR4 measurements (see this module's docstring's "FR4_SEED_ENTRIES"
# section). Frequency bands and provenance transcribed exactly as the issue
# states them; nothing here is auto-extracted from the cited documents
# (ADR-0015: "the library never parses a document itself, only cites it").
# ---------------------------------------------------------------------------

FR4_SEED_ENTRIES: list[dict[str, Any]] = [
    add_entry(
        material="FR4",
        property_name="eps_r",
        frequency_low_hz=7.0e9,
        frequency_high_hz=10.0e9,
        value=4.3,
        unit="unitless",
        provenance=LITERATURE_SUPPORTED,
        citation="F:\\data\\rf_metamaterials\\chunks\\10.25046_aj040210.json "
        "(X-band UWB antenna paper, 7-10 GHz)",
    ),
    add_entry(
        material="FR4",
        property_name="tan_delta",
        frequency_low_hz=7.0e9,
        frequency_high_hz=10.0e9,
        value=0.025,
        unit="unitless",
        provenance=LITERATURE_SUPPORTED,
        citation="F:\\data\\rf_metamaterials\\chunks\\10.25046_aj040210.json "
        "(X-band UWB antenna paper, 7-10 GHz)",
    ),
    add_entry(
        material="FR4",
        property_name="eps_r",
        frequency_low_hz=9.1e9,
        frequency_high_hz=10.2e9,
        value=4.4,
        unit="unitless",
        provenance=LITERATURE_SUPPORTED,
        citation="F:\\data\\rf_metamaterials\\chunks\\10.25046_aj040310.json (9.1-10.2 GHz design)",
    ),
    add_entry(
        material="FR4",
        property_name="tan_delta",
        frequency_low_hz=9.1e9,
        frequency_high_hz=10.2e9,
        value=0.02,
        unit="unitless",
        provenance=LITERATURE_SUPPORTED,
        citation="F:\\data\\rf_metamaterials\\chunks\\10.25046_aj040310.json (9.1-10.2 GHz design)",
    ),
    add_entry(
        material="FR4",
        property_name="eps_r",
        frequency_low_hz=8.98e9,
        frequency_high_hz=10.65e9,
        value=4.4,
        unit="unitless",
        provenance=LITERATURE_SUPPORTED,
        citation="F:\\data\\rf_metamaterials\\chunks\\10.1109_aemc.2017.8325711.json "
        "(one of three bands, 8.98-10.65 GHz)",
    ),
    add_entry(
        material="FR4",
        property_name="tan_delta",
        frequency_low_hz=8.98e9,
        frequency_high_hz=10.65e9,
        value=0.024,
        unit="unitless",
        provenance=LITERATURE_SUPPORTED,
        citation="F:\\data\\rf_metamaterials\\chunks\\10.1109_aemc.2017.8325711.json "
        "(one of three bands, 8.98-10.65 GHz)",
    ),
]


# ---------------------------------------------------------------------------
# I/O layer: persistent storage in `material_properties` /
# `material_family_brackets` (db/schema.sql). Same connection-lifecycle
# discipline as designs/db.py: functions take an already-open connection and
# never commit it themselves -- the caller owns the transaction boundary.
# Not unit-tested here -- no live DATABASE_URL in this sandbox (see this
# module's docstring's "MODULE SHAPE" section); each wrapper is thin glue
# over the pure functions above, which carry all the real logic.
# ---------------------------------------------------------------------------


def insert_material_property_entry(
    conn: psycopg.Connection,
    material: str,
    property_name: str,
    frequency_low_hz: float,
    frequency_high_hz: float,
    value: float,
    unit: str,
    provenance: str,
    citation: str | None = None,
    note: str | None = None,
) -> dict[str, Any]:
    """Validate (`add_entry`) and insert one Material-property library entry.
    Every citation is stored as its own row -- there is no update/upsert
    path here, deliberately: a second, disagreeing citation for the same
    `(material, property, frequency)` is exactly the case this library
    exists to keep, not collapse (see this module's docstring)."""
    entry = add_entry(
        material=material,
        property_name=property_name,
        frequency_low_hz=frequency_low_hz,
        frequency_high_hz=frequency_high_hz,
        value=value,
        unit=unit,
        provenance=provenance,
        citation=citation,
        note=note,
    )
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            INSERT INTO material_properties
                (material, property, frequency_low_hz, frequency_high_hz, value, unit,
                 provenance, citation, note)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING *
            """,
            (
                entry["material"],
                entry["property"],
                entry["frequency_low_hz"],
                entry["frequency_high_hz"],
                entry["value"],
                entry["unit"],
                entry["provenance"],
                entry["citation"],
                entry["note"],
            ),
        )
        row = cur.fetchone()
        assert row is not None
    return row


def insert_family_bracket(
    conn: psycopg.Connection,
    family: str,
    property_name: str,
    min_value: float,
    min_citation: str,
    max_value: float,
    max_citation: str,
    unit: str,
) -> dict[str, Any]:
    """Validate (`add_family_bracket`) and upsert one Family fallback
    bracket. Unlike a per-material entry, a bracket IS upserted on
    `(family, property)` (`db/schema.sql`'s `UNIQUE` constraint) -- ADR-0015
    describes brackets as narrowing over time as more per-material entries
    accumulate, i.e. one current best cited range per family/property, not
    an accumulating list of disagreeing brackets the way per-material
    entries deliberately are."""
    bracket = add_family_bracket(
        family=family,
        property_name=property_name,
        min_value=min_value,
        min_citation=min_citation,
        max_value=max_value,
        max_citation=max_citation,
        unit=unit,
    )
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            INSERT INTO material_family_brackets
                (family, property, min_value, min_citation, max_value, max_citation, unit)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (family, property) DO UPDATE SET
                min_value = EXCLUDED.min_value,
                min_citation = EXCLUDED.min_citation,
                max_value = EXCLUDED.max_value,
                max_citation = EXCLUDED.max_citation,
                unit = EXCLUDED.unit
            RETURNING *
            """,
            (
                bracket["family"],
                bracket["property"],
                bracket["min_value"],
                bracket["min_citation"],
                bracket["max_value"],
                bracket["max_citation"],
                bracket["unit"],
            ),
        )
        row = cur.fetchone()
        assert row is not None
    return row


def fetch_material_property_entries(
    conn: psycopg.Connection, material: str, property_name: str
) -> list[dict[str, Any]]:
    """Return every stored entry for `(material, property_name)`, in
    insertion order -- the full citation set `lookup_entries`/
    `resolve_material_property` filter by frequency band."""
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            "SELECT * FROM material_properties WHERE material = %s AND property = %s ORDER BY id",
            (material, property_name),
        )
        return cur.fetchall()


def fetch_family_bracket(
    conn: psycopg.Connection, family: str, property_name: str
) -> dict[str, Any] | None:
    """Return the stored Family fallback bracket for `(family,
    property_name)`, or `None` if no bracket has been entered for it yet --
    mirrors `designs.db.read_design`'s "None means not found" convention."""
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            "SELECT * FROM material_family_brackets WHERE family = %s AND property = %s",
            (family, property_name),
        )
        return cur.fetchone()


def resolve_material_property_from_db(
    conn: psycopg.Connection,
    material: str,
    property_name: str,
    frequency_hz: float,
    family: str | None = None,
) -> dict[str, Any]:
    """`resolve_material_property`, fetching its `entries`/`family_bracket`
    inputs from the database first. `family` is optional -- a caller with no
    known family for `material` gets `status="no_data"` on a library miss
    rather than this function guessing one."""
    entries = fetch_material_property_entries(conn, material, property_name)
    family_bracket = fetch_family_bracket(conn, family, property_name) if family else None
    return resolve_material_property(
        entries,
        material=material,
        property_name=property_name,
        frequency_hz=frequency_hz,
        family=family,
        family_bracket=family_bracket,
    )
