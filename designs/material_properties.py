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

WHY AN ENTRY STORES ITS OWN UNCERTAINTY AND ITS MEASUREMENT METHOD. Both
were added when the twelve substrates of
`docs/xband-absorber-substrate-shortlist.md` were migrated in, because the
schema could not hold what the sources actually report.

`uncertainty` is the source's OWN stated error bar on that one value --
Kapton 500HN is published as `tan_delta = 0.012 +/- 0.004`, and dropping
the `+/- 0.004` loses the only statement the source makes about how well it
knows its own number. It is a DIFFERENT quantity from the spread across
disagreeing citations, which `resolve_material_property` already derives
from the entries themselves: the spread says how much two labs disagree,
the uncertainty says how much one lab doubts itself. A caller needs both,
and neither substitutes for the other.

`method` is how the value was obtained -- a coaxial dielectric probe, a
microstrip ring resonator, a CPW de-embedding. Different methods carry
different systematic biases (a probe pressed on a soft elastomer has an
air-gap error a ring resonator does not), so two values that disagree may
not really disagree; they may have been measured differently. Without the
method a caller cannot tell a genuine conflict from a systematic offset,
which is exactly the judgment the "never collapse citations" rule above
hands to the caller. Storing "not stated" is itself informative: it says
the disagreement CANNOT be adjudicated.

Both are optional and default to `None`, so every caller written before
they existed is unaffected.

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

MATERIAL / FAMILY VOCABULARY (issue #404). `material` and `family` used to
be checked only for being non-empty strings, so a typo when citing a new
entry (or filing a Family fallback bracket) silently created a row no
lookup would ever find -- `resolve_material_property` would just report
`status="no_data"`, indistinguishable from a genuine absence of data.
`designs/material_families.py` is the fix, mirroring
`designs/design_families.py`'s registry pattern but split by how open each
vocabulary actually is: `family` is a small, closed set of broad categories
(ADR-0015 names them), so `add_family_bracket` REJECTS one this registry
doesn't hold; `material` is deliberately open-ended (CONTEXT.md: "a
growing... record, not a fixed reference table"), so `add_entry` only WARNS
on one it doesn't yet recognize -- see that module's own docstring for why
the two are not treated the same way. Because `family` is this closed
registry's key, `add_family_bracket` stores its CANONICAL spelling (not the
caller's literal casing), and `fetch_family_bracket`/`resolve_material_property`
canonicalize before comparing or querying too -- otherwise two callers citing
the same registered family under different casing ("Generic Polymer" vs
"generic polymer") would land in two disconnected rows, reproducing issue
#404's own failure on the casing axis instead of the spelling axis.

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

from designs.material_families import (
    UnknownMaterialFamilyError,
    get_material_family,
    warn_if_unknown_material,
)
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
    for an `ASSUMED` entry, an inverted family bracket, an unrecognized
    `family` (`designs.material_families.get_material_family`; issue
    #404), or a set of matching entries that disagree on unit. Named and
    raised the same way `designs.requirement_targets.InvalidRequirementTargetError`
    is -- naming exactly what's wrong rather than a bare `TypeError`/`KeyError`.

    Note that an unrecognized `material` (as opposed to `family`) does NOT
    raise this -- see `designs.material_families`'s module docstring for why
    the two are enforced differently."""


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
    uncertainty: float | None = None,
    method: str | None = None,
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

    # Issue #404: an unrecognized material never blocks the entry -- the
    # Material-property library is deliberately a growing record, not a
    # fixed reference table (CONTEXT.md) -- but it warns, since this is also
    # exactly what a typo of an already-cited material looks like.
    warn_if_unknown_material(resolved_material)

    low = _require_nonnegative_finite_number("frequency_low_hz", frequency_low_hz)
    high = _require_nonnegative_finite_number("frequency_high_hz", frequency_high_hz)
    if high < low:
        raise InvalidMaterialPropertyError(
            f"frequency_high_hz ({high!r}) must be >= frequency_low_hz ({low!r})"
        )

    resolved_value = _require_finite_number("value", value)

    resolved_uncertainty: float | None = None
    if uncertainty is not None:
        resolved_uncertainty = _require_nonnegative_finite_number("uncertainty", uncertainty)

    resolved_method: str | None = None
    if method is not None:
        resolved_method = _require_nonempty_string("method", method)

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
        "uncertainty": resolved_uncertainty,
        "method": resolved_method,
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

    `family` must be one of `designs.material_families.known_material_family_names()`
    (case-insensitively), unlike `material` on `add_entry` -- unlike a
    specific material, the family vocabulary for a fallback bracket is a
    small, closed set of broad categories (ADR-0015: "generic polymer,
    generic conductor, etc."), so an unrecognized one raises rather than
    warns: a bracket filed under a misspelled family is one
    `resolve_material_property` will never find for the correctly-spelled
    family a later caller asks for (issue #404).

    The CANONICAL spelling `designs.material_families.get_material_family`
    returns is what gets stored on the returned bracket, not the caller's
    literal text -- deliberately unlike `orchestration.design_loop`'s
    `design_family` field, which ADR-0037 keeps in the caller's own spelling
    because it is a decision record of what a human/agent actually typed. A
    Family fallback bracket is not that: `family` is this table's lookup key
    (`db/schema.sql`'s `UNIQUE(family, property)`, and
    `fetch_family_bracket`/`resolve_material_property`'s exact-match
    comparisons), so two callers citing the SAME family under different
    casing ("Generic Polymer" vs "generic polymer") must land on the same
    row. Storing the raw text would silently split them into two brackets
    that can never find each other -- exactly issue #404's failure mode,
    moved from the spelling axis to the casing axis.
    """
    resolved_family = _require_nonempty_string("family", family)
    try:
        canonical_family = get_material_family(resolved_family)
    except UnknownMaterialFamilyError as exc:
        # Reuse get_material_family's own message (it already names every
        # known family and issue #404) rather than composing a second,
        # independently-worded "unrecognized family" message here that could
        # drift out of sync with it.
        raise InvalidMaterialPropertyError(str(exc)) from exc
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
        "family": canonical_family,
        "property": resolved_property,
        "min_value": resolved_min,
        "min_citation": resolved_min_citation,
        "max_value": resolved_max,
        "max_citation": resolved_max_citation,
        "unit": resolved_unit,
    }


def _canonical_family_or_raw(family: str) -> str:
    """`family`'s canonical spelling if it names a known material family
    (`designs.material_families.get_material_family`), else `family`
    unchanged.

    Used everywhere a `family` a CALLER supplied is compared against, or
    queried for, a bracket that `add_family_bracket` already stored under
    its canonical spelling (see that function's own docstring) -- so a
    caller asking under a different casing of the SAME family still matches
    the stored row instead of silently missing it (issue #404, casing
    axis). Never raises: an unrecognized family was never going to match a
    stored bracket either way (`add_family_bracket` already refuses to
    store one), and rejecting a name is that function's job, not this
    lookup-time helper's.
    """
    try:
        return get_material_family(family)
    except UnknownMaterialFamilyError:
        return family


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
       `["property"]` must match `family`/`property_name` (`family`
       compared case-insensitively via its canonical spelling, since
       `add_family_bracket` only ever stores that spelling -- issue #404),
       or this raises (a caller-supplied bracket for the wrong family/
       property would silently mislead).
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
        # Compare canonically, not by raw spelling: add_family_bracket only
        # ever stores the canonical spelling of a known family (see its own
        # docstring), so a caller asking under a DIFFERENT casing of the
        # SAME family ("Generic Polymer" vs "generic polymer") must still
        # match here -- comparing raw strings would falsely report a
        # family/property mismatch for a bracket that is, in fact, the
        # right one (issue #404, casing axis).
        canonical_family = _canonical_family_or_raw(family)
        bracket_family = family_bracket.get("family")
        bracket_property = family_bracket.get("property")
        if bracket_family != canonical_family or bracket_property != property_name:
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
    uncertainty: float | None = None,
    method: str | None = None,
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
        uncertainty=uncertainty,
        method=method,
    )
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            INSERT INTO material_properties
                (material, property, frequency_low_hz, frequency_high_hz, value, unit,
                 provenance, citation, note, uncertainty, method)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
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
                entry["uncertainty"],
                entry["method"],
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
    mirrors `designs.db.read_design`'s "None means not found" convention.

    `family` is canonicalized first, via `designs.material_families
    .get_material_family`, when it names a known material family --
    `insert_family_bracket`/`add_family_bracket` only ever store the
    canonical spelling (see `add_family_bracket`'s own docstring), so a
    caller asking under a different casing of the SAME family ("Generic
    Polymer" vs "generic polymer") still finds the row, rather than
    `WHERE family = %s`'s exact, case-sensitive match silently reporting
    "no bracket" for one that exists (issue #404, casing axis). An
    unrecognized family is passed through unchanged and simply matches no
    row, same as before -- rejecting a name is `add_family_bracket`'s job,
    not this function's."""
    canonical_family = _canonical_family_or_raw(family)
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            "SELECT * FROM material_family_brackets WHERE family = %s AND property = %s",
            (canonical_family, property_name),
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


# ---------------------------------------------------------------------------
# SUBSTRATE_SEED_ENTRIES -- the twelve substrates catalogued in
# docs/xband-absorber-substrate-shortlist.md section 1, migrated out of that
# markdown table. Transcribed, never re-derived: no value here was computed,
# converted, or interpolated, and nothing was auto-extracted from a cited
# document (ADR-0015: "the library never parses a document itself, only
# cites it").
#
# THREE THINGS THE MIGRATION HAD TO DECIDE, recorded here because a later
# reader will otherwise assume the shortlist and the library disagree.
#
# 1. PROVENANCE WAS DOWNGRADED, and the shortlist is the one that is wrong.
#    Its rows for silicone, Kapton and PDMS are tagged `MEASURED`, meaning
#    "somebody measured this." CONTEXT.md's ladder reserves `MEASURED` for
#    what THIS programme measured, and maps a `paper` source type to
#    `LITERATURE-SUPPORTED`. ENTRY_PROVENANCE_VALUES does not admit
#    `MEASURED` at all, so the library's own type system catches it. These
#    entries are therefore `LITERATURE-SUPPORTED`; the measurement method
#    that earned the shortlist's tag is preserved in `method`.
#
# 2. FOUR SUBSTRATES ARE DELIBERATELY ABSENT, because the shortlist does not
#    state a value the library can hold honestly:
#      - Eccosorb BSR/MFS -- eps'/eps''/mu'/mu'' are not published at all;
#        the datasheet gives dB/cm attenuation only.
#      - PDMS -- reported as a dispersion curve, "2.9 -> 2.55 over
#        1-220 GHz", with no single X-band point stated. Entering either
#        endpoint as an X-band value would invent a number.
#      - Textile felt and denim -- ranges (eps_r 1.13-1.34, 1.63-1.81) with
#        no per-source attribution, and measured mostly at 2.45/5.8 GHz
#        rather than X-band. A range needs either the underlying citations
#        as separate entries or a Family fallback bracket with both ends
#        independently cited; the shortlist supplies neither.
#    Their absence is the correct `status="no_data"` outcome, not an
#    oversight. Same for the fused-silica loss tangent (~0.0002-0.001, a
#    range) and the PET loss tangent (UNKNOWN at X-band).
#
# 3. THE SHORTLIST'S TPU ROW IS STALE. It records eps_r and tan_delta as
#    UNKNOWN at X-band; issue #114 has since resolved them from Vong et al.
#    The resolved values are entered here and the shortlist row wants
#    updating to match.
#
# FR4 APPEARS HERE AS WELL AS IN FR4_SEED_ENTRIES, deliberately. The patent's
# own 4.8 / 0.017 is a fourth, disagreeing citation alongside the three that
# seeded this library (4.3, 4.4, 4.4 / 0.025, 0.02, 0.024) -- and the widest
# disagreement of the set. Keeping it beside them, rather than reconciling
# it, is the whole reason this library stores a value per citation.
# ---------------------------------------------------------------------------

_SHORTLIST = "docs/xband-absorber-substrate-shortlist.md section 1"

# A citation names a DOCUMENT a reader can go and check, not the activity that
# found it. These two strings say which document, which table inside it, and --
# honestly -- that the vendor PDF's revision was never captured, so a reader
# knows the one thing they must re-verify rather than discovering it later.
# ADR-0015's rule is that "the library never parses a document itself, only
# cites it"; a citation that cannot be followed back to a document fails that
# rule even when the number itself is right.
_ROGERS_DESIGN_DK_CITATION = (
    "Rogers RO4000-series laminate datasheet, Design Dk table -- transcribed in the "
    "2026-09-09 datasheet sweep for issue #337; the vendor PDF revision was not "
    "captured, so re-verify against the current datasheet before relying on it"
)

SUBSTRATE_SEED_ENTRIES: list[dict[str, Any]] = [
    # 1. Silicone sheet, 60 Shore A (Polymax SILONA GP/FDA)
    add_entry(
        material="Silicone sheet 60 ShA (Polymax SILONA GP/FDA)",
        property_name="eps_r",
        frequency_low_hz=8.0e9,
        frequency_high_hz=12.0e9,
        value=2.9,
        unit="unitless",
        provenance=LITERATURE_SUPPORTED,
        method="Agilent 85070E coaxial dielectric probe",
        citation=f"Huang et al. 2016, via {_SHORTLIST} (shortlist tags this MEASURED; "
        "downgraded per CONTEXT.md, which reserves MEASURED for this programme's own "
        "measurements and maps a paper to LITERATURE-SUPPORTED)",
    ),
    add_entry(
        material="Silicone sheet 60 ShA (Polymax SILONA GP/FDA)",
        property_name="tan_delta",
        frequency_low_hz=8.0e9,
        frequency_high_hz=12.0e9,
        value=0.10,
        unit="unitless",
        provenance=LITERATURE_SUPPORTED,
        method="Agilent 85070E coaxial dielectric probe",
        citation=f"Huang et al. 2016, via {_SHORTLIST}",
    ),
    # 2. Polyimide (DuPont Kapton 500HN) -- the one row carrying stated
    #    uncertainties, and the reason `uncertainty` exists as a column.
    add_entry(
        material="Polyimide (DuPont Kapton 500HN)",
        property_name="eps_r",
        frequency_low_hz=10.0e9,
        frequency_high_hz=65.0e9,
        value=3.2,
        uncertainty=0.03,
        unit="unitless",
        provenance=LITERATURE_SUPPORTED,
        method="microstrip ring resonator, 10-65 GHz",
        citation=f"Yang et al., via {_SHORTLIST} (shortlist tags this MEASURED; downgraded)",
    ),
    add_entry(
        material="Polyimide (DuPont Kapton 500HN)",
        property_name="tan_delta",
        frequency_low_hz=10.0e9,
        frequency_high_hz=65.0e9,
        value=0.012,
        uncertainty=0.004,
        unit="unitless",
        provenance=LITERATURE_SUPPORTED,
        method="microstrip ring resonator, 10-65 GHz",
        citation=f"Yang et al., via {_SHORTLIST}. The datasheet figure is ~0.002 at kHz -- "
        "a 6x gap against this at-frequency measurement",
    ),
    # 3. LCP (Rogers ULTRALAM 3850) -- at-frequency datasheet, not kHz
    add_entry(
        material="LCP (Rogers ULTRALAM 3850)",
        property_name="eps_r",
        frequency_low_hz=10.0e9,
        frequency_high_hz=10.0e9,
        value=2.9,
        unit="unitless",
        provenance=MANUFACTURER_SPECIFIED,
        method="IPC-TM-650 2.5.5.5.1, 23 degrees C",
        citation=f"Rogers ULTRALAM 3850 datasheet, via {_SHORTLIST}",
    ),
    add_entry(
        material="LCP (Rogers ULTRALAM 3850)",
        property_name="tan_delta",
        frequency_low_hz=10.0e9,
        frequency_high_hz=10.0e9,
        value=0.0025,
        unit="unitless",
        provenance=MANUFACTURER_SPECIFIED,
        method="IPC-TM-650 2.5.5.5.1, 23 degrees C",
        citation=f"Rogers ULTRALAM 3850 datasheet, via {_SHORTLIST}",
    ),
    # 4. PET, heat-stabilised (DuPont Melinex ST505). Entered at the band the
    #    datasheet actually reports -- kHz to MHz -- precisely so a later
    #    lookup at X-band MISSES rather than silently returning a
    #    low-frequency number. No X-band measurement exists for this film.
    add_entry(
        material="PET heat-stabilised (DuPont Melinex ST505)",
        property_name="eps_r",
        frequency_low_hz=1.0e3,
        frequency_high_hz=1.0e6,
        value=3.0,
        unit="unitless",
        provenance=MANUFACTURER_SPECIFIED,
        method="datasheet electrical test, kHz-MHz",
        citation=f"DuPont Melinex ST505 datasheet, via {_SHORTLIST}. Shortlist records the "
        "value as approximate and notes no X-band measurement was found; the band here is "
        "the datasheet's, so an X-band query correctly misses",
    ),
    # 5. TPU -- resolved by #114 after the shortlist recorded it UNKNOWN
    add_entry(
        material="TPU (solid ester-based)",
        property_name="eps_r",
        frequency_low_hz=10.0e9,
        frequency_high_hz=10.0e9,
        value=2.71,
        uncertainty=0.3,
        unit="unitless",
        provenance=LITERATURE_SUPPORTED,
        method="not stated in the accessible text",
        citation="Vong et al., Materials 15(9):3320, doi:10.3390/ma15093320, via issue #114. "
        "Honest uncertainty stated there as eps_r 2.7 +/- 0.3; the point value is 2.71",
    ),
    add_entry(
        material="TPU (solid ester-based)",
        property_name="tan_delta",
        frequency_low_hz=10.0e9,
        frequency_high_hz=10.0e9,
        value=0.099,
        uncertainty=0.01,
        unit="unitless",
        provenance=LITERATURE_SUPPORTED,
        method="not stated in the accessible text",
        citation="Vong et al., Materials 15(9):3320, doi:10.3390/ma15093320, via issue #114. "
        "Honest uncertainty stated there as tan_delta 0.10 +/- 0.01",
    ),
    # 6. FR4, the patent's own figures -- a fourth citation disagreeing with
    #    the three in FR4_SEED_ENTRIES, and third-hand into the bargain
    add_entry(
        material="FR4",
        property_name="eps_r",
        frequency_low_hz=8.0e9,
        frequency_high_hz=12.0e9,
        value=4.8,
        unit="unitless",
        provenance=LITERATURE_SUPPORTED,
        method="not stated -- the patent reports the value without a method",
        citation=f"US12089385B2 Example 3, via the handoff document, via {_SHORTLIST}. "
        "Third-hand: neither this library nor the shortlist read the value off the patent "
        "directly. Disagrees with the three citations in FR4_SEED_ENTRIES (4.3, 4.4, 4.4)",
    ),
    add_entry(
        material="FR4",
        property_name="tan_delta",
        frequency_low_hz=8.0e9,
        frequency_high_hz=12.0e9,
        value=0.017,
        unit="unitless",
        provenance=LITERATURE_SUPPORTED,
        method="not stated -- the patent reports the value without a method",
        citation=f"US12089385B2 Example 3, via the handoff document, via {_SHORTLIST}. "
        "Disagrees with FR4_SEED_ENTRIES (0.025, 0.02, 0.024) by up to 47%",
    ),
    # 7. Rogers RO4350B
    #
    # ROGERS PUBLISHES TWO DIFFERENT PERMITTIVITIES FOR THIS ONE LAMINATE, and
    # which one a caller wants depends on the geometry being modelled. Both are
    # entered here, distinguished by their `method`, because storing only one of
    # them silently answers a question the caller did not ask:
    #
    #   - PROCESS Dk (3.48) is measured on the bare laminate clamped in a
    #     stripline fixture (IPC-TM-650 2.5.5.5). It is a factory
    #     quality-control number for incoming material.
    #   - DESIGN Dk (3.66) is extracted by building and measuring real
    #     microstrip transmission lines -- a printed pattern on one face with
    #     air on the other, which is exactly this project's own unit-cell
    #     geometry (a printed element over a substrate, per ADR-0017's printed
    #     reflector default). It is the number a solver should be fed.
    #
    # The gap is ~5%, which is not noise: at 40 GHz it moves a predicted
    # resonance by roughly 1-1.4 GHz, enough to walk a narrowband Ka-band
    # element off its target. Before this entry existed the library held only
    # the Process number, so every lookup returned the wrong quantity for a
    # printed design.
    #
    # A THICKNESS CAVEAT THAT NEITHER ENTRY CAN CARRY: Rogers states Design Dk
    # falls by about 0.1 as core thickness drops from 0.020" to 0.004", and
    # that 4-mil RO4350B has a Process Dk of 3.33 rather than 3.48. A thin core
    # is the likely choice for a conformal part, and for it BOTH values below
    # are wrong. The library has no thickness field (see this module's
    # docstring), so that cannot be expressed here -- it is recorded in the
    # note instead rather than left for a caller to rediscover.
    add_entry(
        material="Rogers RO4350B",
        property_name="eps_r",
        frequency_low_hz=10.0e9,
        frequency_high_hz=10.0e9,
        value=3.48,
        uncertainty=0.05,
        unit="unitless",
        provenance=MANUFACTURER_SPECIFIED,
        method="datasheet Process Dk, IPC-TM-650 2.5.5.5 clamped stripline, 10 GHz / 23 degrees C",
        note="PROCESS Dk -- a bare-laminate incoming-QC number, NOT the value to feed a solver "
        "for a printed pattern with air above it. Use the Design Dk entry (3.66) for that. "
        "For 4-mil core Rogers publishes 3.33, not 3.48",
        citation=f"Rogers RO4350B datasheet, via {_SHORTLIST}",
    ),
    add_entry(
        material="Rogers RO4350B",
        property_name="eps_r",
        frequency_low_hz=8.0e9,
        frequency_high_hz=40.0e9,
        value=3.66,
        unit="unitless",
        provenance=MANUFACTURER_SPECIFIED,
        method="datasheet Design Dk, extracted from measured microstrip transmission lines, "
        "8-40 GHz",
        note="DESIGN Dk -- the value for a printed pattern on one face with air on the other, "
        "which is this project's own unit-cell geometry. ~5% above the Process Dk (3.48); at "
        "40 GHz that difference moves a predicted resonance by roughly 1-1.4 GHz. Design Dk "
        'falls by about 0.1 from 0.020" to 0.004" core, and the library has no thickness '
        "field, so a thin-core part needs this checked against the datasheet directly",
        # NOT cited via _SHORTLIST. docs/xband-absorber-substrate-shortlist.md
        # records only this laminate's Process Dk (3.48) and its 10 GHz
        # tan_delta (0.0037) -- the strings "3.66" and "Design Dk" appear
        # nowhere in it. Citing it here would point a reader at a document that
        # does not contain the value, which is the exact failure this library
        # exists to prevent (ADR-0015: "the library never parses a document
        # itself, only cites it").
        citation=_ROGERS_DESIGN_DK_CITATION,
    ),
    # Loss tangent is entered at BOTH published test frequencies rather than
    # only the 10 GHz one. tan_delta disperses far more strongly than eps_r,
    # so a single point invites a caller to reuse it across the whole 2-50 GHz
    # design band -- exactly the extrapolation this module's "WHY AN ENTRY'S
    # FREQUENCY IS A BAND" section exists to prevent. Two points at least make
    # the slope visible.
    add_entry(
        material="Rogers RO4350B",
        property_name="tan_delta",
        frequency_low_hz=2.5e9,
        frequency_high_hz=2.5e9,
        value=0.0031,
        unit="unitless",
        provenance=MANUFACTURER_SPECIFIED,
        method="datasheet, 2.5 GHz / 23 degrees C",
        note="Second published point, entered alongside the 10 GHz value (0.0037) so the "
        "frequency dependence is visible rather than inferred",
        # Also NOT via _SHORTLIST -- that document carries only the 10 GHz
        # tan_delta (0.0037), not this 2.5 GHz one. See the Design Dk entry above.
        citation=_ROGERS_DESIGN_DK_CITATION,
    ),
    add_entry(
        material="Rogers RO4350B",
        property_name="tan_delta",
        frequency_low_hz=10.0e9,
        frequency_high_hz=10.0e9,
        value=0.0037,
        unit="unitless",
        provenance=MANUFACTURER_SPECIFIED,
        method="datasheet, 10 GHz / 23 degrees C",
        citation=f"Rogers RO4350B datasheet, via {_SHORTLIST}",
    ),
    # 8. Glass / fused silica -- eps_r only; the loss tangent is a range
    add_entry(
        material="Borosilicate glass / fused silica",
        property_name="eps_r",
        frequency_low_hz=8.0e9,
        frequency_high_hz=12.0e9,
        value=3.8,
        unit="unitless",
        provenance=LITERATURE_SUPPORTED,
        method="not stated",
        citation=f"{_SHORTLIST}, which records the value as approximate and notes that no "
        "first-party X-band measurement was retrieved. The loss tangent is reported only as "
        "a range (~0.0002-0.001) and is therefore not entered",
    ),
]


# ---------------------------------------------------------------------------
# DATASHEET_SEED_ENTRIES -- manufacturer datasheet values gathered in a
# 2026-09-09 sweep of the materials this project actually prints with, across
# its stated 2-50 GHz operating band.
#
# WHY THIS IS A SEPARATE LIST rather than more rows in SUBSTRATE_SEED_ENTRIES:
# that list has its own provenance story (the twelve substrates migrated from
# docs/xband-absorber-substrate-shortlist.md) and its own test asserting how
# many materials it holds. Mixing a differently-sourced batch into it would
# blur both. Same reason FR4_SEED_ENTRIES is separate.
#
# THE ONE STRUCTURAL FINDING BEHIND THIS BATCH. Whether a vendor publishes an
# RF number is decided by who buys the product, not by the material. Rogers
# and Isola sell to radar and base-station engineers, so they test at 2-40 GHz.
# DuPont sells Kapton film to flexible-circuit customers, so it tests at 1 kHz
# -- six orders of magnitude below this project's band. The same split appears
# INSIDE one company: DuPont's Pyralux LF bonding film, sold for RF multilayer
# boards, publishes a 10 GHz number, while DuPont's Kapton film does not.
#
# WHY THE OUT-OF-BAND VALUES ARE ENTERED AT ALL, AND HOW. A 1 kHz permittivity
# is not "the same number, less precise" -- it is wrong in band, and the errors
# run in OPPOSITE directions between materials, so no correction factor exists:
# Kapton's published loss tangent is ~5-6x too LOW against a 9.975 GHz
# measurement, while TPU's published permittivity is up to 2.2x too HIGH
# against a 5.1-18 GHz sweep. Entering them keyed at their own kHz/MHz band
# means a 2-50 GHz lookup MISSES them -- returning no_data when the caller
# supplies no family bracket, or that family's cited MIN/MAX range when they do,
# but NEVER this entry's out-of-band number either way -- rather than either
# silently returning a wrong number or leaving the value to be rediscovered
# and misused. This is the pattern the library already applies to Melinex
# ST505 (see SUBSTRATE_SEED_ENTRIES).
#
# THE SAME TRICK CARRIES THE INK CONDUCTIVITIES. Not one ink vendor -- Voltera,
# ACI Materials, DuPont/Celanese, Novacentrix -- publishes conductivity at any
# RF frequency; every published figure is a DC bench measurement, and most do
# not state a test frequency at all. Keying them at DC (low = high = 0.0 Hz)
# makes them unreturnable by any in-band query while still recording them as
# evidence. Each carries its cure schedule in `note`, because cure alone swings
# one ink's conductivity by 8x, and a conductivity without its cure schedule is
# not a number.
# ---------------------------------------------------------------------------

# Every citation below reads "<vendor> <document>, via {_DATASHEET_SWEEP}". The
# leading half is the document a reader checks; this trailing half says how it
# reached us and what is missing from it. Naming the sweep ALONE would be a
# provenance smell -- an activity is not a retrievable document -- so the vendor
# document is always named first, and this string exists to record honestly that
# the PDF revision was not captured. Where a revision IS known it is written
# into the citation directly (see the Intexar PE874 entry, which cites
# "TDS K-29701"); that is the shape every entry here should eventually take.
_DATASHEET_SWEEP = (
    "2026-09-09 datasheet sweep for issue #337 -- vendor document revision not "
    "captured, re-verify before relying on the value"
)

DATASHEET_SEED_ENTRIES: list[dict[str, Any]] = [
    # -- Isola Astra MT77: the only genuinely MULTI-POINT manufacturer dataset
    #    found in the whole sweep. Five separate published test frequencies for
    #    one laminate, which is what makes dispersion visible instead of
    #    inferred. Entered as five entries, not one wide band, because the
    #    vendor measured five points and did not claim the values in between.
    #
    #    THIS IS WHY ISOLA IS FIVE POINTS AND ROGERS' DESIGN Dk IS ONE WIDE
    #    BAND, which otherwise looks inconsistent: a query at 12 GHz misses
    #    Isola entirely but returns Rogers' 3.55. The difference is in what the
    #    vendor claimed, not in how this file treats them. Isola publishes five
    #    discrete test points; Rogers publishes Design Dk as a value asserted
    #    ACROSS 8-40 GHz. Storing Isola as a band would invent coverage the
    #    vendor never claimed, and storing Rogers as points would discard
    #    coverage it did. An entry's frequency band is meant to be the interval
    #    the citation is valid over -- see this module's docstring's "WHY AN
    #    ENTRY'S FREQUENCY IS A BAND" section -- so both shapes are that same
    #    rule applied to two differently-shaped claims.
    *[
        add_entry(
            material="Isola Astra MT77",
            property_name="eps_r",
            frequency_low_hz=f,
            frequency_high_hz=f,
            value=3.00,
            unit="unitless",
            provenance=MANUFACTURER_SPECIFIED,
            method="datasheet, published test point",
            note="One of five published points (2/5/10/15/20 GHz) -- the only multi-point "
            "manufacturer dataset in this batch",
            citation=f"Isola Astra MT77 datasheet, via {_DATASHEET_SWEEP}",
        )
        for f in (2.0e9, 5.0e9, 1.0e10, 1.5e10, 2.0e10)
    ],
    *[
        add_entry(
            material="Isola Astra MT77",
            property_name="tan_delta",
            frequency_low_hz=f,
            frequency_high_hz=f,
            value=0.0017,
            unit="unitless",
            provenance=MANUFACTURER_SPECIFIED,
            method="datasheet, published test point",
            citation=f"Isola Astra MT77 datasheet, via {_DATASHEET_SWEEP}",
        )
        for f in (2.0e9, 5.0e9, 1.0e10, 1.5e10, 2.0e10)
    ],
    # -- Rogers RO4003C: same Process/Design Dk split as RO4350B above. See
    #    that entry's comment for why both are stored and which one a printed
    #    pattern actually wants.
    add_entry(
        material="Rogers RO4003C",
        property_name="eps_r",
        frequency_low_hz=1.0e10,
        frequency_high_hz=1.0e10,
        value=3.38,
        uncertainty=0.05,
        unit="unitless",
        provenance=MANUFACTURER_SPECIFIED,
        method="datasheet Process Dk, IPC-TM-650 2.5.5.5 clamped stripline, 10 GHz",
        note="PROCESS Dk -- incoming-QC number for bare laminate, NOT the value for a printed "
        "pattern with air above it. Use the Design Dk entry (3.55) for that",
        citation=f"Rogers RO4003C datasheet, via {_DATASHEET_SWEEP}",
    ),
    add_entry(
        material="Rogers RO4003C",
        property_name="eps_r",
        frequency_low_hz=8.0e9,
        frequency_high_hz=4.0e10,
        value=3.55,
        unit="unitless",
        provenance=MANUFACTURER_SPECIFIED,
        method="datasheet Design Dk, extracted from measured microstrip lines, 8-40 GHz",
        note="DESIGN Dk -- the value for this project's own geometry, a printed element over a "
        "substrate (ADR-0017). ~5% above the Process Dk",
        citation=f"Rogers RO4003C datasheet, via {_DATASHEET_SWEEP}",
    ),
    add_entry(
        material="Rogers RO4003C",
        property_name="tan_delta",
        frequency_low_hz=2.5e9,
        frequency_high_hz=2.5e9,
        value=0.0021,
        unit="unitless",
        provenance=MANUFACTURER_SPECIFIED,
        method="datasheet, 2.5 GHz",
        citation=f"Rogers RO4003C datasheet, via {_DATASHEET_SWEEP}",
    ),
    add_entry(
        material="Rogers RO4003C",
        property_name="tan_delta",
        frequency_low_hz=1.0e10,
        frequency_high_hz=1.0e10,
        value=0.0027,
        unit="unitless",
        provenance=MANUFACTURER_SPECIFIED,
        method="datasheet, 10 GHz",
        note="Second published point alongside 2.5 GHz (0.0021), so the frequency dependence "
        "is visible rather than extrapolated",
        citation=f"Rogers RO4003C datasheet, via {_DATASHEET_SWEEP}",
    ),
    # -- Rogers 2929 Bondply: the library's FIRST adhesive-layer dielectric.
    #    Worth calling out because an adhesive layer can be thicker than the
    #    substrate carrying the printed pattern, and almost no adhesive has any
    #    published electrical data in band (see the Kapton/3M notes).
    add_entry(
        material="Rogers 2929 Bondply",
        property_name="eps_r",
        frequency_low_hz=1.0e10,
        frequency_high_hz=1.0e10,
        value=2.94,
        uncertainty=0.05,
        unit="unitless",
        provenance=MANUFACTURER_SPECIFIED,
        method="datasheet, 10 GHz",
        note="First adhesive/bonding-layer dielectric in this library. An adhesive line can be "
        "thicker than the substrate it bonds, so its loss is not negligible",
        citation=f"Rogers 2929 Bondply datasheet, via {_DATASHEET_SWEEP}",
    ),
    add_entry(
        material="Rogers 2929 Bondply",
        property_name="tan_delta",
        frequency_low_hz=1.0e10,
        frequency_high_hz=1.0e10,
        value=0.003,
        unit="unitless",
        provenance=MANUFACTURER_SPECIFIED,
        method="datasheet, 10 GHz",
        citation=f"Rogers 2929 Bondply datasheet, via {_DATASHEET_SWEEP}",
    ),
    # -- DuPont Pyralux LF: the one honest kHz-to-GHz comparison a manufacturer
    #    publishes, both numbers in the same table of the same document. Kept as
    #    two entries at their two real bands so the in-band query returns the
    #    in-band value and the 1 MHz value can never be returned for a GHz
    #    question. This pair is the clearest demonstration in the library of why
    #    the frequency band on an entry is load-bearing.
    add_entry(
        material="DuPont Pyralux LF",
        property_name="eps_r",
        frequency_low_hz=1.0e10,
        frequency_high_hz=1.0e10,
        value=2.8,
        unit="unitless",
        provenance=MANUFACTURER_SPECIFIED,
        method="datasheet, 10 GHz",
        citation=f"DuPont Pyralux LF datasheet, via {_DATASHEET_SWEEP}",
    ),
    add_entry(
        material="DuPont Pyralux LF",
        property_name="tan_delta",
        frequency_low_hz=1.0e10,
        frequency_high_hz=1.0e10,
        value=0.02,
        unit="unitless",
        provenance=MANUFACTURER_SPECIFIED,
        method="datasheet, 10 GHz",
        citation=f"DuPont Pyralux LF datasheet, via {_DATASHEET_SWEEP}",
    ),
    add_entry(
        material="DuPont Pyralux LF",
        property_name="eps_r",
        frequency_low_hz=1.0e6,
        frequency_high_hz=1.0e6,
        value=3.5,
        unit="unitless",
        provenance=MANUFACTURER_SPECIFIED,
        method="datasheet, 1 MHz",
        note="OUT OF BAND, deliberately kept. The same document also publishes 2.8 at 10 GHz, "
        "so this vendor shows directly how far a 1 MHz number sits from the in-band one. Keyed "
        "at 1 MHz so a 2-50 GHz query cannot return it",
        citation=f"DuPont Pyralux LF datasheet, via {_DATASHEET_SWEEP}",
    ),
    # -- Kapton HN: the sharpest frequency trap in the sweep. The published
    #    dissipation factor is a 1 kHz number, and an independent 9.975 GHz
    #    split-cylinder measurement puts the real value 5-6x higher. Kept at
    #    1 kHz so no in-band lookup can reach it.
    add_entry(
        material="DuPont Kapton HN",
        property_name="tan_delta",
        frequency_low_hz=1.0e3,
        frequency_high_hz=1.0e3,
        value=0.0026,
        unit="unitless",
        provenance=MANUFACTURER_SPECIFIED,
        method="datasheet, ASTM D-150, 1 kHz",
        note="OUT OF BAND and known to be badly unrepresentative: an independent split-cylinder "
        "measurement near 9.975 GHz gives ~0.01066, roughly 5-6x higher. DuPont's own bulletin "
        "plots 0.004-0.010 from 10 MHz to 100 GHz, contradicting this headline figure. Recorded "
        "keyed at 1 kHz so a 2-50 GHz query misses it -- entering it is what stops it being "
        "rediscovered and used in band",
        citation=f"DuPont/Qnity Kapton Summary of Properties, via {_DATASHEET_SWEEP}",
    ),
    # -- Ink conductivities, all keyed at DC. Every one is a bench four-point-
    #    probe or drawdown figure; no vendor states an RF value or even a test
    #    frequency. Cure schedule lives in `note` because it is inseparable
    #    from the number.
    add_entry(
        material="ACI Materials SS1109 silver",
        property_name="conductivity_s_per_m",
        frequency_low_hz=0.0,
        frequency_high_hz=0.0,
        value=2.22e6,
        unit="S/m",
        provenance=MANUFACTURER_SPECIFIED,
        method="DC volume resistivity, bench measurement; no frequency stated by vendor",
        note="Cure: the datasheet's resistivity row states 135 C for 15 min, but its own "
        "recommended PROCESS cure is only 5 min at >=135 C -- following the vendor's process "
        "instructions does not reproduce the conditions of this number. A guaranteed floor, "
        "not a typical value",
        citation=f"ACI Materials SS1109 datasheet, via {_DATASHEET_SWEEP}",
    ),
    add_entry(
        material="ACI Materials SC1502 carbon",
        property_name="conductivity_s_per_m",
        frequency_low_hz=0.0,
        frequency_high_hz=0.0,
        value=167.0,
        unit="S/m",
        provenance=MANUFACTURER_SPECIFIED,
        method="DC volume resistivity, bench measurement; no frequency stated by vendor",
        note="Cure: resistivity row states 135 C for 15 min; recommended process cure is 15 min "
        "at >=120 C. Never electrically thick anywhere in 2-50 GHz at any printable thickness, "
        "which is the intended behaviour for a deliberately resistive layer and the one case "
        "where the thin-film form Rs = 1/(sigma*t) is actually valid. A LOWER BOUND, not a "
        "typical value: the vendor publishes an upper bound on resistivity (< 0.6 ohm.cm), so "
        "the real cured ink is at least this conductive and may be more. The library's "
        "`uncertainty` field takes a single symmetric error bar and cannot express a one-sided "
        "bound, so the direction is stated here instead of being silently dropped",
        citation=f"ACI Materials SC1502 datasheet, via {_DATASHEET_SWEEP}",
    ),
    add_entry(
        material="DuPont Celanese Intexar PE874 silver",
        property_name="conductivity_s_per_m",
        frequency_low_hz=0.0,
        frequency_high_hz=0.0,
        value=8.0e5,
        unit="S/m",
        provenance=MANUFACTURER_SPECIFIED,
        method="DC sheet resistance <50 mOhm/sq normalized to 25 um, measured on a 5 um dried "
        "print on PET; converted to conductivity here",
        note="Cure: 130 C for 15 min, ventilated oven. The Voltera NOVA's own heater reaches "
        "only 40 C (viscosity conditioning), so an external oven is required. Named by Voltera "
        "as NOVA-compatible. At its typical 8-12 um cured thickness this is only 0.6-1.0 skin "
        "depths at 2 GHz and does not reach 3 skin depths until roughly 20-45 GHz -- i.e. NOT "
        "safely a good conductor over most of the band in a single pass. Two passes moves that "
        "crossover down to ~5-7 GHz. A LOWER BOUND, not a typical value: the vendor publishes "
        "sheet resistance as '< 50 mOhm/sq', an upper bound, so the cured ink is at least this "
        "conductive and may be more -- which also means the skin-depth figures above are the "
        "PESSIMISTIC end and the real film may cross into good-conductor behaviour lower in "
        "the band than stated",
        citation=f"DuPont/Celanese Intexar PE874 TDS K-29701, via {_DATASHEET_SWEEP}",
    ),
]


# ---------------------------------------------------------------------------
# MXENE_SEED_ENTRIES -- issue #458: the first entries this library holds for
# any MXene, seeded from the batch of open-access/abstract-level MXene
# citations verified during a 2026-09-04/2026-09-10 adversarial pass over
# #104's wayfinder map (NYS7). Separate from DATASHEET_SEED_ENTRIES for the
# same reason that list is separate from SUBSTRATE_SEED_ENTRIES: a distinct
# provenance story (a peer-reviewed literature measurement, not a vendor
# datasheet) and a distinct caveat this batch alone carries (see below) that
# would blur into the datasheet sweep's own if merged into it.
#
# THE CAVEAT THIS WHOLE BATCH TURNS ON, STATED ONCE HERE SO IT IS NOT LOST IN
# THREE SEPARATE NOTE FIELDS: every eps_r value below was measured on a 15
# wt.% MXene-in-paraffin-wax COMPOSITE FILLER -- a solid block of wax loaded
# with MXene powder, machined to a coaxial-airline sample, not a printed or
# deposited conductive film. This project's own printed-film question (#104's
# NYS7: what does a printed MXene TRACE look like at RF) is a DIFFERENT
# measurement of a DIFFERENT physical object that happens to share a chemical
# name. Citing eps_r=4.5 for "Ti2NbC2Tx" here says nothing about a printed
# Ti2NbC2Tx line's permittivity, conductivity, or thickness -- treating this
# entry as if it answered that question would be exactly the "silently
# looks like it answers the printed-ink question it doesn't" failure #104
# was written to catch. Repeated in every entry's own `note` below, not only
# here, because a caller reading one entry in isolation (e.g. via
# `fetch_material_property_entries`) never sees this module comment.
#
# WHY THREE MXENES, NOT ALL SIX THE PAPER REPORTS. Wang et al. 2025
# synthesised and measured six transition-metal-doped MXenes (Ti3C2Tx,
# Ti2NbC2Tx, Ti2TaC2Tx, Ti2VC2Tx, Nb2CTx, V2CTx). Issue #458 names only three
# (Ti2NbC2Tx, Ti3C2Tx, V2CTx -- the highest-eps_r, intermediate, and
# lowest-eps_r of the six, per the paper's own framing) as the confirmed
# figures to enter; the other three are left uncited here rather than
# guessed at from a figure this pipeline cannot read pixel values out of --
# a later ticket citing Ti2TaC2Tx/Ti2VC2Tx/Nb2CTx from the same paper's
# Figure 7a should read the real values off that figure directly rather than
# assume they fall inside the three-value range already entered.
#
# WHY THE Ti3C2Tx VALUE IS 3.9 +/- 0.1, NOT A BARE POINT. The paper states
# Ti3C2Tx's eps_r as the range "3.8-4.0" in prose, not a single point value
# the way it does for the highest (Ti2NbC2Tx, 4.5) and lowest (V2CTx, 3.0).
# Entering the range's midpoint with the half-width as `uncertainty` records
# exactly what the source says -- a value known to within +/-0.1, not a
# point measured to 3.9 precisely -- rather than inventing a false-precision
# point value or silently narrowing the source's own stated range.
_WANG_2025_CITATION_BASE = (
    "Wang et al. 2025, Adv. Sci. 12(41):e09994, DOI 10.1002/advs.202509994 "
    "(PMC12591198, open access, fetched in full 2026-09-10 -- issue #458)"
)
_WANG_2025_PARAFFIN_CAVEAT = (
    "MEASURED ON A 15 wt.% MXene-IN-PARAFFIN COMPOSITE FILLER (coaxial-airline "
    "sample, 22.86x10.16 mm, 2 mm thick), NOT a printed or deposited film -- "
    "see this module's MXENE_SEED_ENTRIES comment. Does not answer #104's "
    "NYS7 printed-ink question; measured via vector network analyzer across "
    "X-band, 8.2-12.4 GHz."
)

MXENE_SEED_ENTRIES: list[dict[str, Any]] = [
    add_entry(
        material="Ti2NbC2Tx",
        property_name="eps_r",
        frequency_low_hz=8.2e9,
        frequency_high_hz=12.4e9,
        value=4.5,
        unit="unitless",
        provenance=LITERATURE_SUPPORTED,
        method="vector network analyzer, MXene-paraffin composite (15 wt.%), X-band",
        note=f"Highest real permittivity of the six MXenes Wang et al. measured, attributed to "
        f"Nb-induced electronic-structure optimisation and enhanced interfacial polarisation. "
        f"{_WANG_2025_PARAFFIN_CAVEAT}",
        citation=_WANG_2025_CITATION_BASE,
    ),
    add_entry(
        material="Ti3C2Tx",
        property_name="eps_r",
        frequency_low_hz=8.2e9,
        frequency_high_hz=12.4e9,
        value=3.9,
        uncertainty=0.1,
        unit="unitless",
        provenance=LITERATURE_SUPPORTED,
        method="vector network analyzer, MXene-paraffin composite (15 wt.%), X-band",
        note=f"Paper states this as a range, '3.8-4.0', not a point value like the highest/lowest "
        f"of the six MXenes -- entered as the range's midpoint with uncertainty=0.1 recording the "
        f"stated range exactly rather than inventing false point precision. Intermediate/"
        f"'characteristic of its intrinsic dielectric behavior' per the paper. "
        f"{_WANG_2025_PARAFFIN_CAVEAT}",
        citation=_WANG_2025_CITATION_BASE,
    ),
    add_entry(
        material="V2CTx",
        property_name="eps_r",
        frequency_low_hz=8.2e9,
        frequency_high_hz=12.4e9,
        value=3.0,
        unit="unitless",
        provenance=LITERATURE_SUPPORTED,
        method="vector network analyzer, MXene-paraffin composite (15 wt.%), X-band",
        note=f"Lowest real permittivity of the six MXenes Wang et al. measured, attributed to "
        f"suppressed dielectric storage from its single-metal V framework and delocalised "
        f"d-orbital electronic structure -- despite this, the paper reports V2CTx as the best "
        f"absorber of the six (highest attenuation constant and RL as low as -53.8 dB at 15 mm), "
        f"driven by loss mechanisms this eps_r entry alone does not capture. "
        f"{_WANG_2025_PARAFFIN_CAVEAT}",
        citation=_WANG_2025_CITATION_BASE,
    ),
    # Ti3C2Tx RF conductivity -- a genuinely different measurement of a
    # genuinely different physical object (a spray-coated thin FILM, not a
    # paraffin composite) from a DIFFERENT, PAYWALLED paper only its abstract
    # was read for. Never claim MEASURED or full-text provenance for this --
    # AlHassoon et al. 2020 is not in `documents` (its only located PDF is
    # DRM-encrypted; Unpaywall confirms no legitimate open copy exists
    # anywhere -- see RUNNING-LISTS.md), so this citation is abstract-only
    # and says so explicitly, per issue #458's own instruction never to
    # claim full-text ingestion for a paper only the abstract was read for.
    add_entry(
        material="Ti3C2Tx",
        property_name="conductivity_s_per_m",
        frequency_low_hz=1.0e9,
        frequency_high_hz=1.0e10,
        value=1.2e6,
        unit="S/m",
        provenance=LITERATURE_SUPPORTED,
        method="capacitively-coupled transmission-line test fixture, S-parameter curve-fit "
        "against full-wave simulation (contactless -- not a DC four-point probe); spray-coated "
        "4.3 um film on PET, highest of three thicknesses tested (1.0/1.5/4.3 um)",
        note="ABSTRACT ONLY -- full text is DRM-locked (the only located PDF, on the Gogotsi "
        "group's own Drexel site, is rejected by pdftotext/PyMuPDF/pypdf/pikepdf alike) and "
        "Unpaywall confirms no legitimate open-access copy exists anywhere; the abstract text "
        "itself is openly available via Crossref/Semantic Scholar/Unpaywall APIs and is what "
        "this entry is drawn from (see RUNNING-LISTS.md). NOT ingested into `documents` for "
        "this reason -- issue #458 explicitly instructs against claiming full-text/MEASURED "
        "provenance for a paper only the abstract was read for. Two things the abstract cannot "
        "settle: (a) whether 1.2e6 S/m is one frequency-independent fitted value across the "
        "whole 1-10 GHz sweep or the peak of a value that varies with frequency inside it; "
        "(b) the synthesis/etching route. Also for citation precision: the measured range "
        "(1-10 GHz) overlaps only the BOTTOM HALF of X-band (8-12 GHz), not most of it, and "
        "deposition is spray-coating, not inkjet/screen printing -- both distinctions matter if "
        "this is cited against #104's NYS7 printed-ink question.",
        citation="AlHassoon, K. et al. 2020, Appl. Phys. Lett. 116:184101, DOI 10.1063/5.0002514 "
        "-- abstract only (Crossref-registered text via Unpaywall/Semantic Scholar APIs), full "
        "text not read; see this entry's own note",
    ),
]
