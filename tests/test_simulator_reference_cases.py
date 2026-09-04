"""Simulator reference-case validation (issue #144).

Two layers:

- The case definitions and the checking logic are pure, and run everywhere.
  They are what stops the fixture itself from being wrong: a geometry with an
  even segment count, a tolerance so wide it accepts anything, an accessor
  reading the wrong field.
- The actual solve is an integration test that skips when no solver binary is
  installed. Nothing installs one here or in CI, so it skips today. That is
  the honest state, and the skip message says so rather than reporting a pass.
"""

from __future__ import annotations

import shutil

import pytest

from verification.simulator_reference_cases import (
    HALF_WAVE_DIPOLE,
    REFERENCE_CASES,
    check_reference_case,
    half_wave_dipole_geometry,
)


def _passing_result(resistance=73.0, reactance=42.5, gain=2.15):
    return {
        "impedance": {"resistance_ohm": resistance, "reactance_ohm": reactance},
        "gain_dbi": gain,
        "provenance": "SIMULATED",
    }


# --- the geometry ---------------------------------------------------------


def test_dipole_is_half_a_wavelength_long_at_its_design_frequency():
    geometry = half_wave_dipole_geometry(300e6)
    wire = geometry["wires"][0]
    length = wire["z2_m"] - wire["z1_m"]
    wavelength = 299_792_458.0 / 300e6
    assert length == pytest.approx(wavelength / 2)


def test_dipole_is_centred_on_the_origin_and_fed_at_its_centre():
    """An off-centre feed changes the impedance, so this is exactly the quiet
    setup error the reference case exists to catch."""
    geometry = half_wave_dipole_geometry(300e6, segments=21)
    wire = geometry["wires"][0]
    assert wire["z1_m"] == pytest.approx(-wire["z2_m"])
    # segment 11 of 21 is the middle one, 1-indexed
    assert geometry["excitation"]["segment"] == 11


def test_an_even_segment_count_is_rejected():
    """With an even count there is no centre segment to excite."""
    with pytest.raises(ValueError, match="odd"):
        half_wave_dipole_geometry(300e6, segments=20)


def test_dipole_is_thin_enough_for_the_analytic_figures_to_apply():
    geometry = half_wave_dipole_geometry(300e6)
    wire = geometry["wires"][0]
    wavelength = 299_792_458.0 / 300e6
    assert wire["radius_m"] / wavelength <= 1e-4


def test_the_case_is_posed_in_free_space():
    """Ground would change the impedance completely -- the published 73 ohms
    is a free-space figure."""
    assert HALF_WAVE_DIPOLE.geometry["ground_condition"] == "free_space"


# --- the checking logic ---------------------------------------------------


def test_a_correct_result_produces_no_discrepancies():
    assert check_reference_case(HALF_WAVE_DIPOLE, _passing_result()) == ()


def test_a_wrong_resistance_is_caught():
    problems = check_reference_case(HALF_WAVE_DIPOLE, _passing_result(resistance=50.0))
    assert [p.name for p in problems] == ["input_resistance"]
    assert "73" in str(problems[0])


def test_the_sign_of_the_reactance_is_caught():
    """A full-length half-wave dipole is inductive. A negative reactance means
    the model is resonating short, which the tolerance must not absorb."""
    problems = check_reference_case(HALF_WAVE_DIPOLE, _passing_result(reactance=-42.5))
    assert [p.name for p in problems] == ["input_reactance"]


def test_a_missing_quantity_is_a_failure_not_a_skip():
    """An adapter that silently returns no impedance has failed the case."""
    problems = check_reference_case(HALF_WAVE_DIPOLE, {"gain_dbi": 2.15})
    assert {p.name for p in problems} == {"input_resistance", "input_reactance"}
    assert all(p.actual is None for p in problems)
    assert "missing from the result" in str(problems[0])


def test_a_non_numeric_value_is_a_failure():
    result = _passing_result()
    result["impedance"]["resistance_ohm"] = "n/a"
    problems = check_reference_case(HALF_WAVE_DIPOLE, result)
    assert [p.name for p in problems] == ["input_resistance"]


def test_every_discrepancy_names_its_source():
    """A failure has to be traceable to the published number it contradicts,
    or nobody can tell a solver bug from a wrong expectation."""
    problems = check_reference_case(HALF_WAVE_DIPOLE, _passing_result(resistance=0.0))
    assert "Balanis" in str(problems[0])


# --- the fixture's own integrity ------------------------------------------


def test_tolerances_are_tight_enough_to_fail_a_wrong_answer():
    """A tolerance wide enough to accept anything is worse than no test. Each
    expected value must reject a result 50% away from it."""
    for case in REFERENCE_CASES.values():
        for expected in case.expected:
            assert expected.tolerance < abs(expected.value) * 0.5, expected.name


def test_every_expected_value_carries_a_citation_and_a_rationale():
    for case in REFERENCE_CASES.values():
        assert case.expected, case.case_id
        for expected in case.expected:
            assert expected.citation.strip()
            assert expected.tolerance_rationale.strip()
            assert expected.unit.strip()


def test_case_ids_match_their_registry_keys():
    for key, case in REFERENCE_CASES.items():
        assert key == case.case_id


# --- the real solve -------------------------------------------------------


@pytest.mark.parametrize("case_id", sorted(REFERENCE_CASES))
def test_reference_case_against_a_real_nec2_solve(case_id):
    """Run the case through the real adapter and the real solver.

    Skips when nec2++ is not installed, which is every environment this repo
    currently runs in -- no full-wave solver is pip-installable, and CI
    installs none (README.md). This test is the thing that would make
    SIMULATED provenance mean 'validated simulation' in CONTEXT.md's evidence
    hierarchy, and it has never yet been executed.
    """
    executable = shutil.which("nec2++")
    if executable is None:
        pytest.skip(
            "nec2++ is not installed, so the reference case cannot be solved. "
            "This is the unrun state issue #144 describes: install nec2++ and "
            "re-run to actually validate the adapter against published values."
        )

    from simulation.nec2pp import run_nec2_simulation

    case = REFERENCE_CASES[case_id]
    result = run_nec2_simulation(case.geometry, case.frequency_hz)
    assert result["provenance"] == "SIMULATED"

    problems = check_reference_case(case, result)
    assert not problems, "\n".join(
        [f"{case.case_id} did not reproduce its published values:"] + [f"  {p}" for p in problems]
    )
