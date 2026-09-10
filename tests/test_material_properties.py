"""Tests for designs/material_properties.py (issue #154; ADR-0015;
CONTEXT.md: Material-property library, Family fallback bracket).

Pure-function tests only, following tests/test_requirement_targets.py's own
precedent for this package: `add_entry`/`add_family_bracket`/
`lookup_entries`/`resolve_material_property` carry all of this ticket's
actual validation/lookup/fallback logic and need no database, so they are
exercised directly here. The DB-backed I/O wrappers
(`insert_material_property_entry`/`insert_family_bracket`/
`fetch_material_property_entries`/`fetch_family_bracket`/
`resolve_material_property_from_db`) need a live Postgres via DATABASE_URL --
they are thin glue over the pure functions above, the same shape those
modules' own untested I/O wrappers already have.

The one exception, guarded by the module-level `DATABASE_URL` connectivity
probe at the bottom of this file (mirroring tests/test_requirement_targets.py's
identical `pytest.mark.skipif` pattern): issue #404's material/family
vocabulary check must reject an unrecognized `family` (and warn on an
unrecognized `material`) through the *real* insert wrappers too, not just the
pure functions they call -- proving the check actually fires before any SQL
runs, and that a rejected bracket insert leaves no row behind.
"""

from __future__ import annotations

import math
import os
import warnings

import psycopg
import pytest

from designs.material_families import UnknownMaterialNameWarning
from designs.material_properties import (
    DATASHEET_SEED_ENTRIES,
    FR4_SEED_ENTRIES,
    SUBSTRATE_SEED_ENTRIES,
    InvalidMaterialPropertyError,
    add_entry,
    add_family_bracket,
    fetch_family_bracket,
    fetch_material_property_entries,
    insert_family_bracket,
    insert_material_property_entry,
    lookup_entries,
    resolve_material_property,
)
from knowledge.provenance import LITERATURE_SUPPORTED

# ---------------------------------------------------------------------------
# add_entry -- validation and provenance tagging
# ---------------------------------------------------------------------------


def test_add_entry_manufacturer_specified_requires_a_citation():
    entry = add_entry(
        material="Rogers RT/duroid 5880",
        property_name="eps_r",
        frequency_low_hz=10e9,
        frequency_high_hz=10e9,
        value=2.2,
        unit="unitless",
        provenance="MANUFACTURER-SPECIFIED",
        citation="Rogers RT/duroid 5880 datasheet, rev 2023",
    )
    assert entry["material"] == "Rogers RT/duroid 5880"
    assert entry["property"] == "eps_r"
    assert entry["frequency_low_hz"] == 10e9
    assert entry["frequency_high_hz"] == 10e9
    assert entry["value"] == 2.2
    assert entry["unit"] == "unitless"
    assert entry["provenance"] == "MANUFACTURER-SPECIFIED"
    assert entry["citation"] == "Rogers RT/duroid 5880 datasheet, rev 2023"
    assert entry["note"] is None


def test_add_entry_manufacturer_specified_without_citation_is_rejected():
    with pytest.raises(InvalidMaterialPropertyError, match="citation"):
        add_entry(
            material="Rogers RT/duroid 5880",
            property_name="eps_r",
            frequency_low_hz=10e9,
            frequency_high_hz=10e9,
            value=2.2,
            unit="unitless",
            provenance="MANUFACTURER-SPECIFIED",
        )


def test_add_entry_literature_supported_without_citation_is_rejected():
    with pytest.raises(InvalidMaterialPropertyError, match="citation"):
        add_entry(
            material="FR4",
            property_name="eps_r",
            frequency_low_hz=7e9,
            frequency_high_hz=10e9,
            value=4.3,
            unit="unitless",
            provenance="LITERATURE-SUPPORTED",
        )


def test_add_entry_assumed_requires_a_note():
    entry = add_entry(
        material="generic flexible TPU",
        property_name="eps_r",
        frequency_low_hz=2.4e9,
        frequency_high_hz=2.4e9,
        value=3.0,
        unit="unitless",
        provenance="ASSUMED",
        note="no source, just entering it -- placeholder pending a real datasheet",
    )
    assert entry["provenance"] == "ASSUMED"
    assert entry["citation"] is None
    assert "no source" in entry["note"]


def test_add_entry_assumed_without_note_is_rejected():
    with pytest.raises(InvalidMaterialPropertyError, match="note"):
        add_entry(
            material="generic flexible TPU",
            property_name="eps_r",
            frequency_low_hz=2.4e9,
            frequency_high_hz=2.4e9,
            value=3.0,
            unit="unitless",
            provenance="ASSUMED",
        )


def test_add_entry_rejects_unknown_provenance():
    with pytest.raises(InvalidMaterialPropertyError, match="provenance"):
        add_entry(
            material="FR4",
            property_name="eps_r",
            frequency_low_hz=10e9,
            frequency_high_hz=10e9,
            value=4.3,
            unit="unitless",
            provenance="MEASURED",
            citation="some citation",
        )


def test_add_entry_rejects_empty_material():
    with pytest.raises(InvalidMaterialPropertyError, match="material"):
        add_entry(
            material="   ",
            property_name="eps_r",
            frequency_low_hz=10e9,
            frequency_high_hz=10e9,
            value=4.3,
            unit="unitless",
            provenance="ASSUMED",
            note="placeholder",
        )


def test_add_entry_rejects_non_finite_value():
    with pytest.raises(InvalidMaterialPropertyError, match="value"):
        add_entry(
            material="FR4",
            property_name="eps_r",
            frequency_low_hz=10e9,
            frequency_high_hz=10e9,
            value=math.inf,
            unit="unitless",
            provenance="ASSUMED",
            note="placeholder",
        )


def test_add_entry_rejects_negative_frequency():
    with pytest.raises(InvalidMaterialPropertyError, match="frequency"):
        add_entry(
            material="FR4",
            property_name="eps_r",
            frequency_low_hz=-1.0,
            frequency_high_hz=10e9,
            value=4.3,
            unit="unitless",
            provenance="ASSUMED",
            note="placeholder",
        )


def test_add_entry_rejects_frequency_high_below_frequency_low():
    with pytest.raises(InvalidMaterialPropertyError, match="frequency"):
        add_entry(
            material="FR4",
            property_name="eps_r",
            frequency_low_hz=10e9,
            frequency_high_hz=7e9,
            value=4.3,
            unit="unitless",
            provenance="ASSUMED",
            note="placeholder",
        )


def test_add_entry_allows_a_single_frequency_point():
    entry = add_entry(
        material="FR4",
        property_name="eps_r",
        frequency_low_hz=10e9,
        frequency_high_hz=10e9,
        value=4.3,
        unit="unitless",
        provenance="LITERATURE-SUPPORTED",
        citation="some paper",
    )
    assert entry["frequency_low_hz"] == entry["frequency_high_hz"] == 10e9


# ---------------------------------------------------------------------------
# add_entry -- material vocabulary (issue #404). Unlike an unrecognized
# `family` on add_family_bracket below, an unrecognized `material` never
# raises -- see designs/material_families.py's module docstring for why the
# two vocabularies are enforced differently.
# ---------------------------------------------------------------------------


def test_add_entry_warns_for_an_unrecognized_material():
    with pytest.warns(UnknownMaterialNameWarning, match="Unobtainium Composite Z9"):
        add_entry(
            material="Unobtainium Composite Z9",
            property_name="eps_r",
            frequency_low_hz=10e9,
            frequency_high_hz=10e9,
            value=3.0,
            unit="unitless",
            provenance="ASSUMED",
            note="placeholder pending a real datasheet",
        )


def test_add_entry_does_not_warn_for_an_already_known_material():
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        # FR4 is one of the harvested, already-known materials -- must not warn.
        add_entry(
            material="FR4",
            property_name="eps_r",
            frequency_low_hz=10e9,
            frequency_high_hz=10e9,
            value=4.3,
            unit="unitless",
            provenance="LITERATURE-SUPPORTED",
            citation="some paper",
        )


def test_add_entry_unrecognized_material_still_builds_the_entry():
    # A typo warns, but the Material-property library is a growing record,
    # never a fixed reference table (CONTEXT.md) -- so the entry is still
    # built, not rejected.
    with pytest.warns(UnknownMaterialNameWarning):
        entry = add_entry(
            material="Brand New Substrate Never Seen Before",
            property_name="eps_r",
            frequency_low_hz=10e9,
            frequency_high_hz=10e9,
            value=3.0,
            unit="unitless",
            provenance="ASSUMED",
            note="placeholder",
        )
    assert entry["material"] == "Brand New Substrate Never Seen Before"


# ---------------------------------------------------------------------------
# add_family_bracket -- validation
# ---------------------------------------------------------------------------


def test_add_family_bracket_builds_a_cited_range():
    bracket = add_family_bracket(
        family="generic polymer",
        property_name="eps_r",
        min_value=2.0,
        min_citation="Pozar, Microwave Engineering, low-loss polymer table",
        max_value=6.0,
        max_citation="Pozar, Microwave Engineering, filled/composite polymer table",
        unit="unitless",
    )
    assert bracket["family"] == "generic polymer"
    assert bracket["property"] == "eps_r"
    assert bracket["min_value"] == 2.0
    assert bracket["max_value"] == 6.0
    assert bracket["min_citation"]
    assert bracket["max_citation"]
    assert bracket["unit"] == "unitless"


def test_add_family_bracket_rejects_max_below_min():
    with pytest.raises(InvalidMaterialPropertyError, match="max_value"):
        add_family_bracket(
            family="generic polymer",
            property_name="eps_r",
            min_value=6.0,
            min_citation="a",
            max_value=2.0,
            max_citation="b",
            unit="unitless",
        )


def test_add_family_bracket_requires_both_citations():
    with pytest.raises(InvalidMaterialPropertyError, match="citation"):
        add_family_bracket(
            family="generic polymer",
            property_name="eps_r",
            min_value=2.0,
            min_citation="",
            max_value=6.0,
            max_citation="b",
            unit="unitless",
        )


def test_add_family_bracket_rejects_an_unrecognized_family():
    # Issue #404: unlike an unrecognized material on add_entry above, an
    # unrecognized family fails loudly -- the family vocabulary is a small,
    # closed set of broad categories (ADR-0015), so a bracket filed under a
    # misspelled one would be one resolve_material_property could never find.
    with pytest.raises(InvalidMaterialPropertyError, match="family"):
        add_family_bracket(
            family="generic plasticky stuff",
            property_name="eps_r",
            min_value=2.0,
            min_citation="a",
            max_value=6.0,
            max_citation="b",
            unit="unitless",
        )


def test_add_family_bracket_accepts_a_known_family_case_insensitively():
    bracket = add_family_bracket(
        family="Generic Polymer",
        property_name="eps_r",
        min_value=2.0,
        min_citation="a",
        max_value=6.0,
        max_citation="b",
        unit="unitless",
    )
    # Unlike orchestration.design_loop's design_family (ADR-0037: kept in the
    # caller's own spelling because it is a decision record of what a human/
    # agent typed), `family` here is this table's lookup key
    # (db/schema.sql's UNIQUE(family, property)), so the CANONICAL spelling
    # is what gets stored -- not the caller's literal casing. Storing the
    # raw text would let "Generic Polymer" and "generic polymer" file as two
    # disconnected brackets that can never find each other, reproducing
    # issue #404's own failure mode on the casing axis instead of the
    # spelling axis (see the two tests below).
    assert bracket["family"] == "generic polymer"


def test_add_family_bracket_canonicalizes_regardless_of_the_caller_s_casing():
    # Two callers citing the SAME family under different casing must land on
    # the SAME canonical spelling, not two independently-cased strings.
    from_title_case = add_family_bracket(
        family="Generic Polymer",
        property_name="eps_r",
        min_value=2.0,
        min_citation="a",
        max_value=6.0,
        max_citation="b",
        unit="unitless",
    )
    from_upper_case = add_family_bracket(
        family="GENERIC POLYMER",
        property_name="eps_r",
        min_value=2.0,
        min_citation="a",
        max_value=6.0,
        max_citation="b",
        unit="unitless",
    )
    assert from_title_case["family"] == from_upper_case["family"] == "generic polymer"


def test_resolve_material_property_finds_a_bracket_cited_under_different_casing():
    # The bracket is filed under "Generic Polymer"; a later caller asks
    # under a differently-cased spelling of the SAME registered family
    # ("generic polymer"). Before issue #404's casing fix, comparing raw
    # strings here would have raised a false family/property mismatch, or
    # (via fetch_family_bracket's exact-match SQL) never found the row at
    # all -- exactly the "no lookup will ever find it" failure issue #404
    # was opened to close.
    bracket = add_family_bracket(
        family="Generic Polymer",
        property_name="eps_r",
        min_value=2.0,
        min_citation="citation A",
        max_value=6.0,
        max_citation="citation B",
        unit="unitless",
    )
    result = resolve_material_property(
        [],
        material="unobtainium foam",
        property_name="eps_r",
        frequency_hz=9.5e9,
        family="generic polymer",
        family_bracket=bracket,
    )
    assert result["status"] == "family_fallback"
    assert result["low"] == 2.0
    assert result["high"] == 6.0


# ---------------------------------------------------------------------------
# lookup_entries -- exact (material, property, frequency) match, never
# collapsed to one row.
# ---------------------------------------------------------------------------


def test_lookup_entries_returns_every_matching_citation_never_one():
    # The issue's own worked example: three independent, disagreeing X-band
    # FR4 citations. lookup_entries must return all three, not merge them.
    matches = lookup_entries(
        FR4_SEED_ENTRIES, material="FR4", property_name="eps_r", frequency_hz=9.5e9
    )
    assert len(matches) == 3
    assert {m["value"] for m in matches} == {4.3, 4.4}


def test_lookup_entries_excludes_a_citation_whose_band_does_not_cover_the_frequency():
    # The 9.1-10.2 GHz citation does not cover 8.0 GHz; the 7-10 GHz one does.
    matches = lookup_entries(
        FR4_SEED_ENTRIES, material="FR4", property_name="eps_r", frequency_hz=8.0e9
    )
    assert len(matches) == 1
    assert matches[0]["value"] == 4.3


def test_lookup_entries_is_scoped_to_material_and_property():
    matches = lookup_entries(
        FR4_SEED_ENTRIES,
        material="Rogers RT/duroid 5880",
        property_name="eps_r",
        frequency_hz=9.5e9,
    )
    assert matches == []


# ---------------------------------------------------------------------------
# resolve_material_property -- the orchestration entry point: per-material
# entries first, then Family fallback bracket, then an explicit "no data"
# report (never a silent guess -- #127's own TPU history).
# ---------------------------------------------------------------------------


def test_resolve_material_property_reports_the_full_spread_across_disagreeing_citations():
    result = resolve_material_property(
        FR4_SEED_ENTRIES, material="FR4", property_name="eps_r", frequency_hz=9.5e9
    )
    assert result["status"] == "material_entries"
    assert result["low"] == 4.3
    assert result["high"] == 4.4
    assert result["unit"] == "unitless"
    assert len(result["entries"]) == 3
    # Never collapsed to a single number -- every citation rides along.
    assert {e["citation"] for e in result["entries"]} == {
        e["citation"] for e in FR4_SEED_ENTRIES if e["value"] in (4.3, 4.4)
    }


def test_resolve_material_property_degenerates_to_a_point_for_one_confident_entry():
    entries = [
        add_entry(
            material="Rogers RT/duroid 5880",
            property_name="eps_r",
            frequency_low_hz=10e9,
            frequency_high_hz=10e9,
            value=2.2,
            unit="unitless",
            provenance="MANUFACTURER-SPECIFIED",
            citation="Rogers datasheet",
        )
    ]
    result = resolve_material_property(
        entries, material="Rogers RT/duroid 5880", property_name="eps_r", frequency_hz=10e9
    )
    assert result["status"] == "material_entries"
    assert result["low"] == result["high"] == 2.2


def test_resolve_material_property_falls_back_to_family_bracket_when_no_entry_exists():
    bracket = add_family_bracket(
        family="generic polymer",
        property_name="eps_r",
        min_value=2.0,
        min_citation="citation A",
        max_value=6.0,
        max_citation="citation B",
        unit="unitless",
    )
    result = resolve_material_property(
        [],
        material="unobtainium foam",
        property_name="eps_r",
        frequency_hz=9.5e9,
        family="generic polymer",
        family_bracket=bracket,
    )
    assert result["status"] == "family_fallback"
    assert result["low"] == 2.0
    assert result["high"] == 6.0
    assert result["min_citation"] == "citation A"
    assert result["max_citation"] == "citation B"
    # A bracket is never a single point value (ADR-0015).
    assert result["low"] != result["high"]


def test_resolve_material_property_never_silently_guesses_with_nothing_to_go_on():
    result = resolve_material_property(
        [], material="unobtainium foam", property_name="eps_r", frequency_hz=9.5e9
    )
    assert result["status"] == "no_data"
    assert "unobtainium foam" in result["message"]


def test_resolve_material_property_prefers_a_specific_material_entry_over_the_family_bracket():
    bracket = add_family_bracket(
        family="generic polymer",
        property_name="eps_r",
        min_value=2.0,
        min_citation="citation A",
        max_value=6.0,
        max_citation="citation B",
        unit="unitless",
    )
    result = resolve_material_property(
        FR4_SEED_ENTRIES,
        material="FR4",
        property_name="eps_r",
        frequency_hz=9.5e9,
        family="generic polymer",
        family_bracket=bracket,
    )
    assert result["status"] == "material_entries"


def test_resolve_material_property_rejects_conflicting_units_among_matches():
    entries = [
        add_entry(
            material="FR4",
            property_name="conductivity_s_per_m",
            frequency_low_hz=10e9,
            frequency_high_hz=10e9,
            value=1.0,
            unit="S/m",
            provenance="ASSUMED",
            note="placeholder",
        ),
        add_entry(
            material="FR4",
            property_name="conductivity_s_per_m",
            frequency_low_hz=10e9,
            frequency_high_hz=10e9,
            value=1000.0,
            unit="mS/m",
            provenance="ASSUMED",
            note="placeholder, different unit by mistake",
        ),
    ]
    with pytest.raises(InvalidMaterialPropertyError, match="unit"):
        resolve_material_property(
            entries, material="FR4", property_name="conductivity_s_per_m", frequency_hz=10e9
        )


# ---------------------------------------------------------------------------
# FR4_SEED_ENTRIES -- the issue's own three real, citable X-band FR4
# measurements (each citing BOTH eps_r and tan_delta), pulled from
# F:\data\rf_metamaterials\.
# ---------------------------------------------------------------------------


def test_fr4_seed_entries_are_three_citations_each_covering_eps_r_and_tan_delta():
    # 3 papers x 2 properties (eps_r, tan_delta) each = 6 entries -- every
    # citation stored on its own, never merged into one row per material.
    assert len(FR4_SEED_ENTRIES) == 6
    for entry in FR4_SEED_ENTRIES:
        assert entry["material"] == "FR4"
        assert entry["property"] in {"eps_r", "tan_delta"}
        assert entry["provenance"] == "LITERATURE-SUPPORTED"
        assert entry["citation"]
    eps_r_entries = [e for e in FR4_SEED_ENTRIES if e["property"] == "eps_r"]
    tan_delta_entries = [e for e in FR4_SEED_ENTRIES if e["property"] == "tan_delta"]
    assert len(eps_r_entries) == 3
    assert len(tan_delta_entries) == 3
    assert {e["value"] for e in eps_r_entries} == {4.3, 4.4}
    # Up to ~25% disagreement on tan_delta across the three citations --
    # exactly the disagreement issue #154 cites as the reason to store each
    # one rather than collapse to a hardcoded constant.
    assert {round(e["value"], 3) for e in tan_delta_entries} == {0.02, 0.024, 0.025}


# ---------------------------------------------------------------------------
# uncertainty and method -- the two fields the substrate migration needed
# ---------------------------------------------------------------------------


def _minimal_entry(**overrides):
    kwargs = {
        "material": "Kapton 500HN",
        "property_name": "tan_delta",
        "frequency_low_hz": 10.0e9,
        "frequency_high_hz": 65.0e9,
        "value": 0.012,
        "unit": "unitless",
        "provenance": LITERATURE_SUPPORTED,
        "citation": "Yang et al., microstrip ring resonator",
    }
    kwargs.update(overrides)
    return add_entry(**kwargs)


def test_uncertainty_and_method_default_to_none_so_existing_callers_are_unaffected():
    entry = _minimal_entry()
    assert entry["uncertainty"] is None
    assert entry["method"] is None


def test_uncertainty_records_the_sources_own_error_bar():
    # Kapton 500HN is published as tan_delta 0.012 +/- 0.004. The +/- is a
    # property of that one measurement, not of the spread across citations,
    # so the library has to be able to hold both.
    entry = _minimal_entry(uncertainty=0.004)
    assert entry["uncertainty"] == pytest.approx(0.004)


def test_uncertainty_may_be_zero_but_never_negative():
    assert _minimal_entry(uncertainty=0.0)["uncertainty"] == 0.0
    with pytest.raises(InvalidMaterialPropertyError, match="uncertainty"):
        _minimal_entry(uncertainty=-0.004)


def test_uncertainty_must_be_finite():
    with pytest.raises(InvalidMaterialPropertyError, match="uncertainty"):
        _minimal_entry(uncertainty=math.inf)


def test_method_records_how_the_value_was_obtained():
    entry = _minimal_entry(method="microstrip ring resonator, 10-65 GHz")
    assert entry["method"] == "microstrip ring resonator, 10-65 GHz"


def test_method_when_given_must_not_be_blank():
    # Omitting the method is honest; claiming one and leaving it empty is not.
    with pytest.raises(InvalidMaterialPropertyError, match="method"):
        _minimal_entry(method="   ")


# ---------------------------------------------------------------------------
# SUBSTRATE_SEED_ENTRIES -- the migrated shortlist
# ---------------------------------------------------------------------------


def test_substrate_seeds_cover_the_eight_migratable_substrates():
    # Twelve substrates are catalogued; four are deliberately absent because
    # the shortlist states no value the library can hold honestly (Eccosorb
    # publishes none, PDMS is a dispersion curve, felt and denim are
    # unattributed ranges measured off-band). See the module comment.
    assert len({e["material"] for e in SUBSTRATE_SEED_ENTRIES}) == 8


def test_no_substrate_seed_claims_MEASURED_provenance():
    # The shortlist tags several rows MEASURED, meaning "somebody measured
    # this." CONTEXT.md reserves MEASURED for what this programme measured
    # itself, and ENTRY_PROVENANCE_VALUES does not admit it at all.
    #
    # Asserting `provenance != "MEASURED"` over the seed list CANNOT FAIL --
    # add_entry raises at import for anything outside ENTRY_PROVENANCE_VALUES,
    # so the list could never have contained one. That is a guarantee worth
    # proving rather than restating, so the constructor is exercised directly.
    with pytest.raises(InvalidMaterialPropertyError, match="provenance"):
        add_entry(
            material="Anything",
            property_name="eps_r",
            frequency_low_hz=1.0e10,
            frequency_high_hz=1.0e10,
            value=1.0,
            unit="unitless",
            provenance="MEASURED",
            citation="a real measurement someone else made",
        )

    # What CAN drift is the data: an unsourced value slipping into a list whose
    # every row is supposed to carry a citation.
    assert all(e["provenance"] != "ASSUMED" for e in SUBSTRATE_SEED_ENTRIES)
    assert all(e["citation"] for e in SUBSTRATE_SEED_ENTRIES)


def test_every_substrate_seed_records_its_method_even_when_it_is_unknown():
    # A missing method is a fact worth storing: it is why two disagreeing
    # values cannot be adjudicated.
    assert all(e["method"] for e in SUBSTRATE_SEED_ENTRIES)


def test_the_patents_FR4_disagrees_with_the_three_seeded_FR4_citations():
    # The whole reason this library stores a value per citation. The patent's
    # 4.8 sits well outside the 4.3-4.4 the other three report.
    seeded = [e["value"] for e in FR4_SEED_ENTRIES if e["property"] == "eps_r"]
    migrated = [
        e["value"]
        for e in SUBSTRATE_SEED_ENTRIES
        if e["material"] == "FR4" and e["property"] == "eps_r"
    ]
    assert migrated == [4.8]
    assert max(seeded) < min(migrated)


def test_PET_is_entered_at_its_datasheet_band_so_an_x_band_lookup_misses():
    # No X-band measurement exists for Melinex ST505. Entering the kHz-MHz
    # datasheet value at X-band would silently hand a low-frequency number to
    # an X-band design; entering it at its real band makes the lookup miss.
    pet = [e for e in SUBSTRATE_SEED_ENTRIES if e["material"].startswith("PET")]
    assert lookup_entries(pet, pet[0]["material"], "eps_r", 10.0e9) == []
    assert lookup_entries(pet, pet[0]["material"], "eps_r", 1.0e5) == pet


# ---------------------------------------------------------------------------
# DATASHEET_SEED_ENTRIES -- the 2026-09-09 manufacturer datasheet sweep.
#
# The behaviour worth protecting here is NOT that a particular number is
# stored. It is that the deliberately out-of-band values -- a 1 kHz Kapton
# loss tangent, a 1 MHz Pyralux permittivity, a DC ink conductivity -- are
# recorded as evidence WITHOUT ever being returnable for an in-band query.
# That is the whole reason they are entered at all: an unrecorded wrong number
# gets rediscovered and reused, and a recorded-but-reachable one gets returned
# and believed. These tests pin the middle path.
# ---------------------------------------------------------------------------

# This project's stated operating band (issue #337), used to assert that no
# out-of-band datasheet value can leak into an in-band answer.
_IN_BAND_HZ = (2.0e9, 1.0e10, 2.8e10, 5.0e10)


def test_datasheet_entries_all_carry_a_method_and_a_document_citation():
    """Every entry in this batch came off a vendor datasheet, so each must be
    MANUFACTURER-SPECIFIED and each citation must name a *document*, not only the
    sweep that found it.

    This replaces an earlier `provenance != "MEASURED"` assertion that could never
    fail: MEASURED is not in ENTRY_PROVENANCE_VALUES, so `add_entry` raises at
    import time for it and the test only restated a guarantee the constructor
    already enforces. What can genuinely drift is the data -- someone adding an
    ASSUMED value, or a citation that names the research pass and no document.
    """
    assert all(e["method"] for e in DATASHEET_SEED_ENTRIES)
    assert all(e["provenance"] == "MANUFACTURER-SPECIFIED" for e in DATASHEET_SEED_ENTRIES)

    for entry in DATASHEET_SEED_ENTRIES:
        document = entry["citation"].split(", via ")[0].strip()
        assert document, f"{entry['material']}: citation is only a sweep reference"
        assert document != entry["citation"].strip(), (
            f"{entry['material']}: citation names no document before the sweep reference"
        )


def test_datasheet_out_of_band_traps_are_unreachable_in_band():
    """The 1 kHz Kapton and 1 MHz Pyralux values must never answer a GHz query.

    Kapton's published 1 kHz dissipation factor is roughly 5-6x lower than an
    independent ~9.975 GHz measurement of the same film, so returning it for an
    in-band question would be worse than returning nothing.
    """
    for frequency_hz in _IN_BAND_HZ:
        kapton = resolve_material_property(
            DATASHEET_SEED_ENTRIES, "DuPont Kapton HN", "tan_delta", frequency_hz
        )
        assert kapton["status"] == "no_data"

    # ... but the value IS recorded, at its own frequency, so it is not lost.
    assert (
        resolve_material_property(DATASHEET_SEED_ENTRIES, "DuPont Kapton HN", "tan_delta", 1.0e3)[
            "status"
        ]
        == "material_entries"
    )


def test_datasheet_pyralux_returns_its_in_band_value_and_hides_its_1mhz_one():
    """Pyralux LF publishes both a 1 MHz and a 10 GHz permittivity in one
    document -- the clearest case in the library of why an entry's frequency
    band is load-bearing. The in-band query must get 2.8, never 3.5."""
    in_band = resolve_material_property(
        DATASHEET_SEED_ENTRIES, "DuPont Pyralux LF", "eps_r", 1.0e10
    )
    assert in_band["status"] == "material_entries"
    assert in_band["low"] == in_band["high"] == 2.8

    # 20 GHz sits outside both published points, so nothing is returned rather
    # than the 1 MHz value being stretched to cover it.
    assert (
        resolve_material_property(DATASHEET_SEED_ENTRIES, "DuPont Pyralux LF", "eps_r", 2.0e10)[
            "status"
        ]
        == "no_data"
    )


def test_datasheet_ink_conductivities_are_dc_keyed_and_never_answer_an_rf_query():
    """No ink vendor publishes conductivity at any RF frequency; every figure
    is a DC bench measurement. Keying them at DC records the evidence while
    making it impossible to return for an in-band question."""
    inks = sorted(
        {e["material"] for e in DATASHEET_SEED_ENTRIES if e["property"] == "conductivity_s_per_m"}
    )
    assert inks, "expected at least one ink conductivity entry"

    for ink in inks:
        for frequency_hz in _IN_BAND_HZ:
            assert (
                resolve_material_property(
                    DATASHEET_SEED_ENTRIES, ink, "conductivity_s_per_m", frequency_hz
                )["status"]
                == "no_data"
            )
        at_dc = resolve_material_property(DATASHEET_SEED_ENTRIES, ink, "conductivity_s_per_m", 0.0)
        assert at_dc["status"] == "material_entries"
        # A conductivity without its cure schedule is not a number.
        assert all("Cure" in e["note"] for e in at_dc["entries"])


def test_datasheet_multi_point_laminate_does_not_interpolate_between_points():
    """Isola Astra MT77 publishes five separate test points. A query between
    two of them returns nothing -- the vendor measured points, not a curve."""
    on_point = resolve_material_property(
        DATASHEET_SEED_ENTRIES, "Isola Astra MT77", "eps_r", 1.5e10
    )
    assert on_point["status"] == "material_entries"

    between = resolve_material_property(DATASHEET_SEED_ENTRIES, "Isola Astra MT77", "eps_r", 1.2e10)
    assert between["status"] == "no_data"


def test_datasheet_process_and_design_dk_are_both_stored_and_distinguishable():
    """Rogers publishes two permittivities for one laminate. At 10 GHz both
    match, and the caller must see the spread rather than inherit whichever
    was stored first; at 40 GHz only the Design Dk is valid."""
    at_10ghz = resolve_material_property(DATASHEET_SEED_ENTRIES, "Rogers RO4003C", "eps_r", 1.0e10)
    assert at_10ghz["low"] == 3.38
    assert at_10ghz["high"] == 3.55
    methods = " ".join(e["method"] for e in at_10ghz["entries"])
    assert "Process Dk" in methods and "Design Dk" in methods

    at_40ghz = resolve_material_property(DATASHEET_SEED_ENTRIES, "Rogers RO4003C", "eps_r", 4.0e10)
    assert at_40ghz["low"] == at_40ghz["high"] == 3.55


def test_ro4350b_process_and_design_dk_behave_like_ro4003c():
    """RO4350B got the same Process/Design Dk split as RO4003C but had no test
    of its own. Both laminates must behave identically: a caller at 10 GHz sees
    the spread between the two published quantities, and a caller at 40 GHz gets
    only the Design Dk, which is the one valid there."""
    at_10ghz = resolve_material_property(SUBSTRATE_SEED_ENTRIES, "Rogers RO4350B", "eps_r", 1.0e10)
    assert at_10ghz["low"] == 3.48
    assert at_10ghz["high"] == 3.66
    methods = " ".join(e["method"] for e in at_10ghz["entries"])
    assert "Process Dk" in methods and "Design Dk" in methods

    at_40ghz = resolve_material_property(SUBSTRATE_SEED_ENTRIES, "Rogers RO4350B", "eps_r", 4.0e10)
    assert at_40ghz["low"] == at_40ghz["high"] == 3.66

    # tan_delta is published at two points and must not span between them.
    assert (
        resolve_material_property(SUBSTRATE_SEED_ENTRIES, "Rogers RO4350B", "tan_delta", 5.0e9)[
            "status"
        ]
        == "no_data"
    )


def test_ro4350b_new_entries_do_not_cite_a_document_that_lacks_their_values():
    """Regression guard on a real defect found in review.

    The Design Dk (3.66) and the 2.5 GHz tan_delta (0.0031) were originally
    cited to `docs/xband-absorber-substrate-shortlist.md`, which records only
    this laminate's Process Dk (3.48) and its 10 GHz tan_delta (0.0037). Citing
    a document that does not contain the value is precisely the failure this
    library exists to prevent -- ADR-0015's "the library never parses a document
    itself, only cites it" is worthless if the cited document is the wrong one.
    """
    values_absent_from_the_shortlist = {3.66, 0.0031}
    for entry in SUBSTRATE_SEED_ENTRIES:
        if entry["material"] != "Rogers RO4350B":
            continue
        if entry["value"] not in values_absent_from_the_shortlist:
            continue
        assert "xband-absorber-substrate-shortlist" not in entry["citation"], (
            f"RO4350B {entry['property']}={entry['value']} cites the shortlist, "
            "which does not contain that value"
        )
        assert "datasheet" in entry["citation"].lower()


# ---------------------------------------------------------------------------
# DB-backed: issue #404's material/family vocabulary check through the real
# insert wrappers -- see this module's docstring for why this is the one
# DB-backed exception here.
# ---------------------------------------------------------------------------

_TEST_DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql://rf:rf_dev_password@localhost:5432/rfengineer"
)


def _database_reachable() -> bool:
    try:
        with psycopg.connect(_TEST_DATABASE_URL, connect_timeout=3):
            return True
    except psycopg.OperationalError:
        return False


_DB_REACHABLE = _database_reachable()


@pytest.mark.skipif(
    not _DB_REACHABLE,
    reason=f"no reachable Postgres at {_TEST_DATABASE_URL.split('@')[-1]!r} in this sandbox",
)
class TestInsertWrappersEnforceTheVocabulary:
    def test_insert_family_bracket_rejects_an_unrecognized_family_and_writes_no_row(self):
        conn = psycopg.connect(_TEST_DATABASE_URL)
        try:
            with pytest.raises(InvalidMaterialPropertyError, match="family"):
                insert_family_bracket(
                    conn,
                    family="generic squishy stuff",
                    property_name="eps_r",
                    min_value=2.0,
                    min_citation="a",
                    max_value=6.0,
                    max_citation="b",
                    unit="unitless",
                )
            # The check fires before any SQL runs -- confirm no row landed
            # for this property under any family, on the same connection.
            assert fetch_family_bracket(conn, "generic squishy stuff", "eps_r") is None
        finally:
            conn.rollback()
            conn.close()

    def test_insert_material_property_entry_warns_but_still_inserts(self):
        conn = psycopg.connect(_TEST_DATABASE_URL)
        try:
            with pytest.warns(UnknownMaterialNameWarning, match="Issue 404 DB Probe Material"):
                row = insert_material_property_entry(
                    conn,
                    material="Issue 404 DB Probe Material",
                    property_name="eps_r",
                    frequency_low_hz=10e9,
                    frequency_high_hz=10e9,
                    value=3.0,
                    unit="unitless",
                    provenance="ASSUMED",
                    note="issue #404 DB-backed wiring probe, never committed",
                )
            assert row["material"] == "Issue 404 DB Probe Material"
            # The Material-property library never blocks a new material --
            # confirm the row is actually visible on this connection.
            fetched = fetch_material_property_entries(conn, "Issue 404 DB Probe Material", "eps_r")
            assert len(fetched) == 1
        finally:
            # Never committed -- rolling back leaves the real table untouched.
            conn.rollback()
            conn.close()
