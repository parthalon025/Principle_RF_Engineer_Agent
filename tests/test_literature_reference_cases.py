"""Literature reference cases -- four published metasurfaces (issue #386).

The cases in `tests/test_simulator_reference_cases.py` check the solvers
against CLOSED-FORM answers: problems where algebra already knows the
result. That proves the plumbing. It says nothing about whether a solver,
handed a real printed metasurface geometry, predicts what the object did on
a bench.

These four cases each reconstruct a published paper that carries BOTH a
fabricated geometry AND a measured curve. Everything here runs with no
solver installed: the reconstructions, the pass-band arithmetic, the
outcome model, and -- for the one case this repo can actually pose today --
the executed circuit result itself.

*In plain terms: the older tests ask "does the calculator add up?". These
ask "when somebody built the thing and measured it, did we predict what
they got?" -- and, where we cannot yet answer that, they make the machinery
say so out loud instead of guessing.*
"""

from __future__ import annotations

import math
import re
import subprocess
from pathlib import Path

import pytest

from verification.fss_bandpass_circuit_check import (
    CASE_ID as FSS_CASE_ID,
)
from verification.fss_bandpass_circuit_check import (
    circuit_reading,
    layer_stack_thickness_m,
    run_case,
)
from verification.simulator_reference_cases import (
    BANDPASS_FSS_SILVER_PASTE,
    BIANISOTROPIC_HUYGENS_REFRACTION,
    CPC_METASURFACE_RCS,
    LITERATURE_CASES,
    REFERENCE_CASES,
    VARACTOR_RIS_UNIT_CELL,
    CaseOutcome,
    Comparison,
    ExpectedValue,
    PassBand,
    QuantityKind,
    literature_expected_value,
    score_reference_case,
)

_REPO_ROOT = Path(__file__).resolve().parent.parent
_WRITE_UP = _REPO_ROOT / "docs" / "literature-validation-cases.md"


# --- the four cases are registered where the existing ones live -----------


def test_all_four_literature_cases_are_in_the_existing_registry():
    """Acceptance criterion 1: the existing reference-case module, not a new
    parallel harness. A second registry is a second thing to keep honest."""
    expected = (
        CPC_METASURFACE_RCS,
        BIANISOTROPIC_HUYGENS_REFRACTION,
        BANDPASS_FSS_SILVER_PASTE,
        VARACTOR_RIS_UNIT_CELL,
    )
    for case in expected:
        assert REFERENCE_CASES[case.case_id] is case
    assert set(LITERATURE_CASES) == {case.case_id for case in expected}


def test_a_literature_case_is_exactly_one_that_names_a_paper():
    """`LITERATURE_CASES` must be derived, not a hand-kept second list that
    can silently drift out of step with the registry it summarises."""
    assert LITERATURE_CASES == {
        case_id: case for case_id, case in REFERENCE_CASES.items() if case.source is not None
    }


def test_every_literature_case_names_its_paper_by_id_and_version():
    """Acceptance criterion 2. A paper without a version is not a citation:
    v1 and v2 can carry different numbers in the same figure."""
    for case in LITERATURE_CASES.values():
        source = case.source
        assert source is not None
        assert re.fullmatch(r"\d{4}\.\d{4,5}", source.arxiv_id), case.case_id
        assert re.fullmatch(r"v\d+", source.version), case.case_id
        assert source.title.strip()
        assert source.scored_against.strip()
        assert source.arxiv_id in source.citation
        assert source.version in source.citation


def test_every_literature_case_records_its_reconstruction_and_what_was_inferred():
    """Acceptance criterion 2, second half: substrate, the dimensions read
    off the paper, and -- separately -- the ones that had to be inferred.
    A reconstruction that does not distinguish the two is unfalsifiable."""
    for case in LITERATURE_CASES.values():
        reconstruction = case.reconstruction
        assert reconstruction is not None, case.case_id
        assert reconstruction.substrate.strip(), case.case_id
        assert reconstruction.read_from_text, case.case_id
        # `inferred` may be empty only if nothing was inferred; every one of
        # these four had something missing, so an empty tuple here means a
        # gap went unrecorded rather than that there was none.
        assert reconstruction.inferred, case.case_id


# --- the pass band, and where its width comes from ------------------------


def test_every_literature_band_is_max_of_digitization_and_published_gap():
    """Acceptance criterion 3, as arithmetic rather than as prose.

    Never an invented tolerance: the band is the wider of (a) how accurately
    the number can be read off the published figure and (b) how far the
    paper's own simulation missed the paper's own measurement.
    """
    for case in LITERATURE_CASES.values():
        for expected in case.expected:
            band = expected.band
            assert band is not None, f"{case.case_id}:{expected.name}"
            floor = band.digitization_error if band.published_gap is None else band.published_gap
            assert band.width == max(band.digitization_error, floor)
            assert expected.tolerance == band.width, f"{case.case_id}:{expected.name}"


def test_every_literature_band_says_which_of_the_two_set_it():
    """Criterion 3's tail: where the paper publishes no gap, the digitization
    error alone sets the band AND that fact is recorded."""
    for case in LITERATURE_CASES.values():
        for expected in case.expected:
            band = expected.band
            assert band is not None
            if band.published_gap is None:
                assert band.set_by == "digitization"
                assert "publishes no" in expected.tolerance_rationale.lower(), expected.name
            else:
                assert band.set_by in {"digitization", "published-gap"}
                assert band.published_gap_citation.strip(), expected.name


def test_every_digitization_error_is_estimated_with_a_stated_basis():
    """Acceptance criterion 4: reading a curve off a published figure has
    real uncertainty. Quantified, with the reasoning shown -- not assumed
    negligible and not left as a bare number nobody can argue with."""
    for case in LITERATURE_CASES.values():
        for expected in case.expected:
            band = expected.band
            assert band is not None
            assert band.digitization_error > 0.0, f"{case.case_id}:{expected.name}"
            assert len(band.digitization_basis.split()) >= 8, expected.name


def test_a_band_narrower_than_its_digitization_error_is_refused():
    """The floor exists so nobody can quietly tighten a band below the
    accuracy the source figure actually supports."""
    with pytest.raises(ValueError, match="digitization"):
        PassBand(digitization_error=-0.1, digitization_basis="x " * 10)


def test_the_factory_is_the_only_place_the_width_is_written_down():
    """The band width must be computed from its two inputs, never typed in
    beside them, or the two can disagree and the comment wins over the
    arithmetic."""
    band = PassBand(
        digitization_error=0.5,
        digitization_basis="read to a fifth of a five decibel division on the published figure",
        published_gap=1.0,
        published_gap_citation="the paper's own sentence",
    )
    value = literature_expected_value(
        name="transmission_db_at_10ghz",
        value=-1.7,
        unit="dB",
        citation="arXiv:x",
        kind=QuantityKind.TRANSMISSION,
        band=band,
        rationale="because",
    )
    assert value.tolerance == 1.0
    assert value.band is band


def test_a_hand_built_expected_value_whose_tolerance_contradicts_its_band_is_refused():
    band = PassBand(
        digitization_error=0.5,
        digitization_basis="read to a fifth of a five decibel division on the published figure",
        published_gap=1.0,
        published_gap_citation="the paper's own sentence",
    )
    with pytest.raises(ValueError, match="tolerance"):
        ExpectedValue(
            name="transmission_db_at_10ghz",
            value=-1.7,
            tolerance=0.25,
            unit="dB",
            citation="arXiv:x",
            tolerance_rationale="tightened by hand",
            band=band,
        )


# --- reflection and transmission never share a number ---------------------


def test_reflection_and_transmission_are_scored_in_separate_buckets():
    """Acceptance criterion 5. Two errors of opposite sign cancel inside a
    total and manufacture a false pass; keeping them apart makes that
    impossible rather than merely discouraged."""
    case = BIANISOTROPIC_HUYGENS_REFRACTION
    kinds = {e.kind for e in case.expected}
    assert QuantityKind.REFLECTION in kinds
    assert QuantityKind.TRANSMISSION in kinds

    score = score_reference_case(
        case,
        {
            "specular_reflection_resonance_hz": 20.6e9,
            "refraction_efficiency": 0.80,
            "provenance": "SIMULATED",
        },
        ignore_unresolved=True,
    )
    assert score.outcome is CaseOutcome.PASS
    assert score.reflection == ()
    assert score.transmission == ()


def test_a_transmission_error_never_hides_behind_a_reflection_one():
    score = score_reference_case(
        BIANISOTROPIC_HUYGENS_REFRACTION,
        {
            "specular_reflection_resonance_hz": 20.6e9,
            "refraction_efficiency": 0.20,
            "provenance": "SIMULATED",
        },
        ignore_unresolved=True,
    )
    assert score.outcome is CaseOutcome.FAIL
    assert score.reflection == ()
    assert [d.name for d in score.transmission] == ["refraction_efficiency"]


def test_the_score_exposes_no_combined_figure_of_merit():
    """There is deliberately no total, no mean and no aggregate error on a
    score object -- because the moment one exists somebody will report it,
    and a cancelled pair of errors reads as a pass inside it."""
    score = score_reference_case(
        BIANISOTROPIC_HUYGENS_REFRACTION,
        {"provenance": "SIMULATED"},
        ignore_unresolved=True,
    )
    banned = {"total", "aggregate", "combined", "score", "error", "rms", "mean", "sum"}
    for field_name in score.__dataclass_fields__:
        assert not banned & set(field_name.split("_")), field_name


def test_every_literature_expected_value_declares_reflection_or_transmission():
    """`OTHER` is available but nothing here may use it: a quantity nobody
    has classified is a quantity that can be quietly summed with anything."""
    for case in LITERATURE_CASES.values():
        for expected in case.expected:
            assert expected.kind in {QuantityKind.REFLECTION, QuantityKind.TRANSMISSION}


# --- UNRESOLVED is a real third outcome -----------------------------------


def test_an_ambiguous_reconstruction_reports_unresolved_not_a_verdict():
    """Acceptance criterion 6. Forcing a case with missing information into
    pass/fail turns that missing information into a false verdict."""
    case = CPC_METASURFACE_RCS
    assert case.unresolved_reason
    score = score_reference_case(
        case,
        {
            "cross_pol_resonance_c_band_hz": 7.8e9,
            "cross_pol_resonance_x_band_hz": 11.7e9,
            "cross_pol_resonance_ku_band_hz": 18.0e9,
            "provenance": "SIMULATED",
        },
    )
    assert score.outcome is CaseOutcome.UNRESOLVED
    assert score.unresolved_reason == case.unresolved_reason
    # A result that would otherwise have passed still does not pass.
    assert score.reflection == ()
    assert score.transmission == ()


def test_a_solver_that_did_not_converge_reports_unresolved():
    score = score_reference_case(
        BANDPASS_FSS_SILVER_PASTE,
        {"converged": False, "provenance": "SIMULATED"},
    )
    assert score.outcome is CaseOutcome.UNRESOLVED
    assert "converge" in score.unresolved_reason


def test_three_of_the_four_cases_are_unresolved_today_and_say_why():
    """The honest state of this ticket, asserted rather than described.

    If a later session closes one of these gaps, this test fails and forces
    the write-up to be updated with it -- which is the point.
    """
    unresolved = {c.case_id for c in LITERATURE_CASES.values() if c.unresolved_reason}
    assert unresolved == {
        CPC_METASURFACE_RCS.case_id,
        BIANISOTROPIC_HUYGENS_REFRACTION.case_id,
        VARACTOR_RIS_UNIT_CELL.case_id,
    }
    for case in LITERATURE_CASES.values():
        if case.unresolved_reason:
            assert len(case.unresolved_reason.split()) >= 20, case.case_id


def test_the_outcome_vocabulary_is_exactly_three_words():
    assert {o.value for o in CaseOutcome} == {"PASS", "FAIL", "UNRESOLVED"}


# --- the pin, and the provenance ceiling ----------------------------------


def test_every_literature_case_pins_a_solver_version_and_an_adapter_commit():
    """Acceptance criterion 7: a result must be traceable to the exact code
    that produced it, and re-runnable later."""
    for case in LITERATURE_CASES.values():
        run = case.run
        assert run is not None, case.case_id
        assert run.solver.strip()
        assert run.solver_version.strip()
        assert re.fullmatch(r"[0-9a-f]{7,40}", run.adapter_commit), case.case_id
        assert (_REPO_ROOT / run.adapter_module).is_file(), run.adapter_module


def test_every_pinned_commit_is_a_real_commit_in_this_repository():
    """A pin nobody can resolve is decoration. Skips cleanly where git is
    unavailable rather than pretending the check ran."""
    try:
        subprocess.run(
            ["git", "-C", str(_REPO_ROOT), "rev-parse", "--git-dir"],
            capture_output=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError):  # pragma: no cover - env dependent
        pytest.skip("git is not available here, so the pinned commits cannot be resolved")

    for case in LITERATURE_CASES.values():
        assert case.run is not None
        revision = f"{case.run.adapter_commit}^{{commit}}"
        completed = subprocess.run(
            ["git", "-C", str(_REPO_ROOT), "cat-file", "-e", revision],
            capture_output=True,
        )
        assert completed.returncode == 0, (
            f"{case.case_id} pins adapter commit {case.run.adapter_commit}, "
            "which is not a commit in this repository"
        )


def test_every_literature_case_is_capped_at_simulated():
    """Acceptance criterion 11. Nothing here is a measurement of our own
    hardware and must not be labelled as one."""
    for case in LITERATURE_CASES.values():
        assert case.provenance == "SIMULATED"


def test_a_result_claiming_measured_provenance_is_refused():
    """The failure this guards is mislabelling: a solver result filed as a
    bench measurement would jump the evidence hierarchy CONTEXT.md sets."""
    with pytest.raises(ValueError, match="MEASURED"):
        score_reference_case(
            BANDPASS_FSS_SILVER_PASTE,
            {"transmission_db_at_10ghz": -1.7, "provenance": "MEASURED"},
        )


# --- case 1: the accuracy bar comes from the authors, not from us ---------


def test_case_one_takes_its_bands_from_the_authors_own_measured_versus_simulated_offset():
    """Acceptance criterion 9. The paper prints both its simulated and its
    measured conversion frequencies, so the gap between them is published
    arithmetic rather than a tolerance we chose."""
    case = CPC_METASURFACE_RCS
    simulated = {"c_band": 6.66e9, "x_band": 9.75e9, "ku_band": 15.1e9}
    measured = {"c_band": 7.8e9, "x_band": 11.7e9, "ku_band": 18.0e9}
    for band_name, expected_name in (
        ("c_band", "cross_pol_resonance_c_band_hz"),
        ("x_band", "cross_pol_resonance_x_band_hz"),
        ("ku_band", "cross_pol_resonance_ku_band_hz"),
    ):
        expected = next(e for e in case.expected if e.name == expected_name)
        assert expected.value == pytest.approx(measured[band_name])
        assert expected.band is not None
        gap = abs(measured[band_name] - simulated[band_name])
        assert expected.band.published_gap == pytest.approx(gap, rel=1e-9)
        assert "0.5" in expected.band.published_gap_citation
        assert "3" in expected.band.published_gap_citation


def test_case_one_bands_widen_towards_the_ku_band_as_the_paper_says_they_should():
    """ "the deviation being most prominent in the Ku-band" -- if our bands
    did not widen the same way, we would have transcribed something."""
    case = CPC_METASURFACE_RCS
    widths = [
        next(e for e in case.expected if e.name == name).tolerance
        for name in (
            "cross_pol_resonance_c_band_hz",
            "cross_pol_resonance_x_band_hz",
            "cross_pol_resonance_ku_band_hz",
        )
    ]
    assert widths == sorted(widths)


# --- case 2: the permittivity is an assumption, and says so ---------------


def test_case_two_records_the_ten_gigahertz_datasheet_permittivity_as_an_assumption():
    """Acceptance criterion 10. The paper never states RT/duroid 6010's
    permittivity at all; the datasheet characterises it at 10 GHz and this
    case runs at 20 GHz. If the case fails, that is a prime suspect, so it
    must be visible rather than buried."""
    case = BIANISOTROPIC_HUYGENS_REFRACTION
    assert case.reconstruction is not None
    assumptions = case.reconstruction.assumptions
    assert assumptions, case.case_id
    permittivity = [a for a in assumptions if "10 GHz" in a.statement and "20 GHz" in a.statement]
    assert permittivity, "the 10 GHz-datasheet-at-20 GHz permittivity is not recorded"
    only = permittivity[0]
    assert only.cost_if_wrong.strip()
    assert only.cheapest_check.strip()


def test_every_assumption_carries_its_cost_and_its_cheapest_check():
    """CLAUDE.md's contract for a warning: what is assumed, what it costs if
    that is wrong, and the cheapest way to find out."""
    for case in LITERATURE_CASES.values():
        assert case.reconstruction is not None
        for assumption in case.reconstruction.assumptions:
            assert len(assumption.statement.split()) >= 8
            assert len(assumption.cost_if_wrong.split()) >= 6
            assert len(assumption.cheapest_check.split()) >= 6


# --- case 3: the planar curve, and only the planar curve ------------------


def test_case_three_is_scored_against_the_planar_figure_seventeen_curve():
    """Acceptance criterion 8. Scoring a flat, infinitely-repeating
    simulation against a measurement taken on a dome compares two different
    physical problems and can produce either a false pass or a false fail."""
    source = BANDPASS_FSS_SILVER_PASTE.source
    assert source is not None
    assert "Fig. 17" in source.scored_against
    assert "planar" in source.scored_against.lower()
    assert "hemispherical" in source.excluded.lower()
    assert len(source.excluded.split()) >= 20


def test_the_write_up_says_the_hemispherical_result_was_deliberately_excluded():
    text = _WRITE_UP.read_text(encoding="utf-8").lower()
    assert "hemispherical" in text
    assert "fig. 17" in text


# --- case 3 is the one this repo can actually pose today ------------------


def test_case_three_is_the_only_one_with_no_unresolved_reason():
    assert not BANDPASS_FSS_SILVER_PASTE.unresolved_reason
    assert BANDPASS_FSS_SILVER_PASTE.case_id == FSS_CASE_ID


def test_the_circuit_stack_is_four_and_a_half_millimetres_of_abs():
    """The paper's own total. A stack that does not add up to it has a layer
    missing or doubled, which no S-parameter comparison would tell you."""
    assert layer_stack_thickness_m() == pytest.approx(4.5e-3, abs=1e-12)


def test_the_circuit_stack_is_in_the_order_the_wave_meets_it():
    """ABCD matrices do not commute: a capacitive sheet in front of a spacer
    is a different part from a spacer in front of a capacitive sheet."""
    kinds = [layer["kind"] for layer in BANDPASS_FSS_SILVER_PASTE.geometry["layers"]]
    assert kinds == [
        "dielectric",
        "shunt_capacitance",
        "dielectric",
        "shunt_inductance",
        "dielectric",
        "shunt_capacitance",
        "dielectric",
    ]


def test_the_circuit_reconstruction_uses_the_papers_own_published_c_and_l():
    layers = BANDPASS_FSS_SILVER_PASTE.geometry["layers"]
    capacitances = [layer["farads"] for layer in layers if layer["kind"] == "shunt_capacitance"]
    inductances = [layer["henries"] for layer in layers if layer["kind"] == "shunt_inductance"]
    assert capacitances == [78e-15, 78e-15]
    assert inductances == [1.66e-9]


#: The executed result, transcribed once, here, from a real run of
#: `verification/fss_bandpass_circuit_check.py` against the committed
#: `rf_tools/transmissive_absorber.py` ABCD primitives. If these stop
#: matching, the model moved -- not the paper.
CIRCUIT_S21_DB_AT_10GHZ = -0.3931
CIRCUIT_S21_DB_AT_20GHZ = -15.6923


def test_the_executed_circuit_result_is_reproducible_to_four_decimals():
    assert circuit_reading(10e9)["s21_db"] == pytest.approx(CIRCUIT_S21_DB_AT_10GHZ, abs=5e-5)
    assert circuit_reading(20e9)["s21_db"] == pytest.approx(CIRCUIT_S21_DB_AT_20GHZ, abs=5e-5)


def test_the_circuit_reconstruction_is_passive_at_every_frequency_it_is_read_at():
    """No mesh here, so an S21 above unity would be an arithmetic error in
    the model rather than a discretisation artefact."""
    for ghz in (6, 8, 10, 13, 15, 20, 26):
        reading = circuit_reading(ghz * 1e9)
        assert reading["s21_db"] <= 0.0
        assert reading["s11_db"] <= 0.0
        total = 10 ** (reading["s21_db"] / 10) + 10 ** (reading["s11_db"] / 10)
        assert total <= 1.0 + 1e-9


def test_case_three_fails_on_its_passband_insertion_loss_and_passes_its_stopband():
    """The finding this ticket actually produced, asserted.

    The reconstruction is built from the paper's own lossless C and L, so it
    predicts a passband roughly 1.3 dB shallower than the measurement -- more
    than the paper's own 1 dB simulated-versus-measured gap allows. The
    stopband, which does not depend on conductor loss nearly as much, lands
    inside its band.
    """
    score = run_case()
    assert score.outcome is CaseOutcome.FAIL
    assert score.reflection == ()
    assert [d.name for d in score.transmission] == ["transmission_db_at_10ghz"]
    assert score.transmission[0].actual == pytest.approx(CIRCUIT_S21_DB_AT_10GHZ, abs=5e-5)


def test_the_missing_paste_loss_is_named_as_the_suspect_rather_than_the_band_widened():
    """Step 5 of CLAUDE.md's loop: say which broke, the model or the design.

    The dispensed silver paste is 10^6 S/m -- about sixty times worse a
    conductor than copper -- and the paper never states how thick the
    dispensed traces are, so the loss those traces contribute cannot be
    reconstructed. That omission is recorded as an inferred quantity, not
    absorbed into a wider tolerance.
    """
    reconstruction = BANDPASS_FSS_SILVER_PASTE.reconstruction
    assert reconstruction is not None
    joined = " ".join(reconstruction.inferred).lower()
    assert "thickness" in joined
    assert "paste" in joined or "silver" in joined


# --- case 4: the case no adapter here can pose ----------------------------


def test_case_four_says_exactly_which_capability_is_missing():
    reason = VARACTOR_RIS_UNIT_CELL.unresolved_reason.lower()
    assert "lumped" in reason
    assert "periodic" in reason
    assert "openems" in reason


def test_case_four_records_that_the_measured_axis_is_bias_voltage_not_capacitance():
    """The paper sweeps capacitance in simulation (Fig. 3) and reverse-bias
    voltage in measurement (Fig. 5); it publishes no C(V) curve for the
    diode, so the two axes cannot be laid over one another."""
    case = VARACTOR_RIS_UNIT_CELL
    assert case.reconstruction is not None
    joined = " ".join(case.reconstruction.inferred).lower()
    assert "bias" in joined or "c(v)" in joined


# --- the write-up states the scope limits, in substance -------------------


def test_the_write_up_exists_and_states_the_scope_limits():
    """Acceptance criterion 12, first half."""
    text = _WRITE_UP.read_text(encoding="utf-8").lower()
    for phrase in ("passive", "planar", "periodic", "known substrate", "normal incidence"):
        assert phrase in text, phrase
    assert "4" in text and "30 ghz" in text


def test_the_write_up_states_that_no_magnetic_mirror_case_is_covered():
    """Acceptance criterion 12, second half -- and the most important line in
    the document. CONTEXT.md opens on the magnetic-mirror physics; passing
    all four of these would leave it with zero validation coverage, and a
    green result must not imply otherwise."""
    text = _WRITE_UP.read_text(encoding="utf-8").lower()
    assert "artificial magnetic conductor" in text
    assert "magnetic mirror" in text
    assert "zero" in text


def test_the_write_up_pins_every_case_by_arxiv_id_and_adapter_commit():
    text = _WRITE_UP.read_text(encoding="utf-8")
    for case in LITERATURE_CASES.values():
        assert case.source is not None and case.run is not None
        assert case.source.arxiv_id in text, case.case_id
        assert case.run.adapter_commit[:7] in text, case.case_id


def test_the_write_up_does_not_claim_the_unrun_cases_were_run():
    """The mistake `verification/README.md` records having made before:
    scaffolding for a test nobody executed, written up as though it were a
    result."""
    text = _WRITE_UP.read_text(encoding="utf-8").lower()
    assert "unresolved" in text
    assert "not been run" in text or "unexecuted" in text or "cannot be posed" in text


# --- the comparison vocabulary --------------------------------------------


@pytest.mark.parametrize(
    ("comparison", "actual", "matches"),
    [
        (Comparison.WITHIN, -1.7, True),
        (Comparison.WITHIN, -3.0, False),
        (Comparison.AT_LEAST, 5.0, True),
        (Comparison.AT_LEAST, -3.0, False),
        (Comparison.AT_MOST, -9.0, True),
        (Comparison.AT_MOST, 5.0, False),
    ],
)
def test_a_published_bound_is_not_forced_into_a_two_sided_band(comparison, actual, matches):
    """Three of these four papers state their headline result as a bound --
    "exceeding 95%", "less than 0.2%", "15-20 dB rejection". Turning a bound
    into a two-sided band would reject correct answers on the permitted side
    of it, which is its own kind of false verdict."""
    value = ExpectedValue(
        name="transmission_db_at_10ghz",
        value=-1.7,
        tolerance=1.0,
        unit="dB",
        citation="arXiv:x",
        tolerance_rationale="x",
        comparison=comparison,
    )
    assert value.matches(actual) is matches


def test_a_missing_quantity_is_still_a_discrepancy_under_every_comparison():
    """A run that never produced the number has not satisfied a bound
    either -- silence is not compliance."""
    score = score_reference_case(
        BANDPASS_FSS_SILVER_PASTE,
        {"provenance": "SIMULATED"},
    )
    assert score.outcome is CaseOutcome.FAIL
    assert {d.name for d in score.transmission} == {
        "transmission_db_at_10ghz",
        "transmission_db_at_20ghz",
    }
    assert all(d.actual is None for d in score.transmission)


def test_a_literature_case_reads_its_quantities_by_declared_key():
    """New quantities arrive declaratively rather than by editing a
    name-to-field switch, which is where a transcription error hides."""
    for case in LITERATURE_CASES.values():
        for expected in case.expected:
            assert expected.result_key == expected.name, expected.name


def test_frequencies_are_stored_in_hertz_not_gigahertz():
    """A unit slip of 10^9 passes every band in this module trivially in one
    direction and fails everything in the other."""
    for case in LITERATURE_CASES.values():
        for expected in case.expected:
            if expected.unit == "Hz":
                assert expected.value > 1e9
                assert math.isfinite(expected.value)
