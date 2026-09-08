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

from verification.meep_two_port_absorption_check import (
    CASE_ID as TWO_PORT_CASE_ID,
)
from verification.meep_two_port_absorption_check import (
    closed_form_reading,
    guard_refuses_the_collapse_on_this_family,
    one_port_collapse,
    overstatement_factor,
)
from verification.simulator_reference_cases import (
    FREE_STANDING_RESISTIVE_SHEET_TWO_PORT,
    HALF_WAVE_DIPOLE,
    MATCHED_SHEET_RESISTANCE_OHM_SQ,
    REFERENCE_CASES,
    check_reference_case,
    free_standing_sheet_geometry,
    half_wave_dipole_geometry,
)


def _passing_result(resistance=73.0, reactance=42.5, gain=2.15):
    return {
        "impedance": {"resistance_ohms": resistance, "reactance_ohms": reactance},
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
    result["impedance"]["resistance_ohms"] = "n/a"
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


NEC2_CASE_IDS = sorted(
    case_id for case_id, case in REFERENCE_CASES.items() if case.solver == "NEC2"
)


def test_every_reference_case_names_a_solver_that_can_pose_it():
    """A case is only meaningful to the adapter its geometry is written for.

    This test exists because the registry was briefly iterated wholesale by
    the NEC2 runner below, which would have handed an absorber stack's empty
    wire list to nec2++ the moment that binary appeared on PATH. It skipped
    everywhere, so nothing caught it -- a permanently-skipping test hides its
    own bugs.
    """
    for case in REFERENCE_CASES.values():
        assert case.solver in {"NEC2", "MEEP"}, case.case_id
        if case.solver == "NEC2":
            assert case.geometry, f"{case.case_id} must carry a deck for nec2++"


@pytest.mark.parametrize("case_id", NEC2_CASE_IDS)
def test_reference_case_against_a_real_nec2_solve(case_id):
    """Run a NEC2 case through the real adapter and the real solver.

    Only NEC2 cases: the MEEP cases in the registry are posed by
    verification/meep_absorber_validation.py, which needs a solver CI does
    not have and runs as a script rather than a test.

    Skips when nec2++ is not installed, which is every environment CI runs
    in. Note the Dockerfile DOES build nec2++, so this is takeable in the
    container -- it is unrun, not unrunnable, and #222 tracks running it.
    """
    executable = shutil.which("nec2++")
    if executable is None:
        pytest.skip(
            "nec2++ is not installed here, so this case cannot be solved. "
            "The Dockerfile builds nec2++, so this is runnable in the "
            "container -- see #222. The MEEP cases in this registry HAVE been "
            "executed; see docs/meep-absorber-validation.md."
        )

    from simulation.nec2pp import run_nec2_simulation

    case = REFERENCE_CASES[case_id]
    result = run_nec2_simulation(case.geometry, case.frequency_hz)
    assert result["provenance"] == "SIMULATED"

    problems = check_reference_case(case, result)
    assert not problems, "\n".join(
        [f"{case.case_id} did not reproduce its published values:"] + [f"  {p}" for p in problems]
    )


# --- the free-standing sheet through the two-port path (issue #244) -------
#
# The solve itself is verification/meep_two_port_absorption_check.py, which
# needs a solver CI does not have. Everything below is the MECHANICS around
# it -- the geometry it poses, the scoring it applies, and the collapse
# arithmetic it reports -- and all of it runs with no solver installed.
#
# The numbers are from a real pymeep 1.34.0 run of that script, transcribed
# once, here, so that a change in the scoring can be told apart from a
# change in the physics: if these stop passing, the arithmetic moved, not
# the solver.


TWO_PORT_MEASURED_R = 0.2899
TWO_PORT_MEASURED_T = 0.2130
TWO_PORT_MEASURED_A = 0.4971  # 1 - R - T, to the digits the runner prints
TWO_PORT_COLLAPSED_A = 0.7101  # 1 - R, the ground-backed sum on the same run


def _measured_two_port_record(absorptance=TWO_PORT_MEASURED_A):
    """One SIMULATION record, shaped exactly as the design loop writes it.

    Not a shim invented for the test: `check_reference_case` reads this
    shape because it is what `orchestration/design_loop.py` hands back, so
    what the script scores and what this test scores are the same object.
    """
    return {
        "function": "run_meep_simulation",
        "simulator": "MEEP",
        "reflectance": [TWO_PORT_MEASURED_R],
        "transmittance": [TWO_PORT_MEASURED_T],
        "absorption": [absorptance],
        "absorption_formula": "A = 1 - R - T",
        "port_count": 2,
        "provenance": "SIMULATED",
    }


def test_the_two_port_case_is_registered_and_names_meep_as_its_solver():
    case = REFERENCE_CASES[TWO_PORT_CASE_ID]
    assert case is FREE_STANDING_RESISTIVE_SHEET_TWO_PORT
    assert case.solver == "MEEP"


def test_the_measured_two_port_run_reproduces_the_exact_half():
    record = _measured_two_port_record()
    assert check_reference_case(FREE_STANDING_RESISTIVE_SHEET_TWO_PORT, record) == ()


def test_the_one_port_collapse_fails_this_case():
    """The point of the whole ticket, as an assertion.

    Score the same run with A = 1 - R and the answer is 0.7101, which the
    case rejects. A tolerance that accepted both sums would be measuring
    nothing.
    """
    problems = check_reference_case(
        FREE_STANDING_RESISTIVE_SHEET_TWO_PORT,
        _measured_two_port_record(absorptance=TWO_PORT_COLLAPSED_A),
    )
    assert [p.name for p in problems] == ["absorptance"]
    assert problems[0].actual == pytest.approx(TWO_PORT_COLLAPSED_A)


def test_the_collapse_arithmetic_on_the_measured_reflectance():
    """1 - R, through the committed one-port function aimed at the real
    ground-backed family -- not recomputed inside the test."""
    assert one_port_collapse([TWO_PORT_MEASURED_R])[0] == pytest.approx(TWO_PORT_COLLAPSED_A)


def test_the_overstatement_is_one_point_four_three_not_two():
    """The ticket that commissioned this work said "roughly double". It is
    not, and the reason is structural rather than a matter of precision: at
    the matched sheet the power splits 25/25/50, so discarding the
    transmitted quarter inflates a half into three quarters."""
    assert overstatement_factor(0.75, 0.5) == pytest.approx(1.5)
    measured = overstatement_factor(TWO_PORT_COLLAPSED_A, TWO_PORT_MEASURED_A)
    assert measured == pytest.approx(1.428, abs=0.001)
    assert measured < 1.5


def test_the_collapse_is_refused_outright_on_the_two_port_family():
    """The overstatement above is what the collapse WOULD say. This is why
    no run can reach it through the loop."""
    message = guard_refuses_the_collapse_on_this_family()
    assert "ABSORBER_TRANSMISSIVE" in message
    assert "port_count=2" in message


def test_the_closed_form_sits_exactly_on_the_half_power_ceiling():
    """No mesh, so no excuse: the two-port model must return the exact
    25/25/50 split at Rs = eta0/2, or the model is wrong rather than
    coarse."""
    closed = closed_form_reading(10e9)
    assert closed["reflectance"] == pytest.approx(0.25, abs=1e-9)
    assert closed["transmittance"] == pytest.approx(0.25, abs=1e-9)
    assert closed["absorptance"] == pytest.approx(0.5, abs=1e-9)


@pytest.mark.parametrize("sheet_resistance", [94.2, 376.73, 754.0])
def test_the_closed_form_absorbs_less_at_every_other_sheet_resistance(sheet_resistance):
    """0.5 is a MAXIMUM, not merely a value the model happens to produce at
    one input. If some other sheet beat it, the exactness this whole case
    leans on would be gone."""
    assert closed_form_reading(10e9, sheet_resistance)["absorptance"] < 0.5


def test_the_full_wave_and_closed_form_disagreement_is_where_it_is_claimed():
    """The absorbed total agrees to 0.003; the split does not, by more than
    ten times that. The document says so, and this is the assertion that
    keeps the document honest."""
    closed = closed_form_reading(10e9)
    assert abs(TWO_PORT_MEASURED_A - closed["absorptance"]) < 0.005
    assert abs(TWO_PORT_MEASURED_R - closed["reflectance"]) > 0.03
    assert abs(TWO_PORT_MEASURED_T - closed["transmittance"]) > 0.03


# --- the geometry the case poses ------------------------------------------


def test_the_case_carries_the_geometry_the_builder_produces():
    assert FREE_STANDING_RESISTIVE_SHEET_TWO_PORT.geometry == free_standing_sheet_geometry(10e9)


def test_the_sheet_is_matched_and_declared_by_its_sheet_resistance():
    """A conductor stating neither a conductivity nor a sheet resistance is
    an ideal perfect metal in simulation/meep.py, and a perfect metal
    absorbs nothing -- defect #230. So how the sheet is declared matters as
    much as the value."""
    conductor = free_standing_sheet_geometry(10e9)["conductors"][0]
    assert conductor["sheet_resistance_ohm_sq"] == pytest.approx(MATCHED_SHEET_RESISTANCE_OHM_SQ)
    assert conductor["sheet_resistance_ohm_sq"] == pytest.approx(188.365, abs=1e-3)
    assert "thickness_m" in conductor
    assert "conductivity_s_m" not in conductor


def test_a_two_port_case_must_ask_for_a_transmission_monitor():
    """Without it the loop refuses the run outright (#243), and rightly:
    A = 1 - R - T cannot be computed from a run that never measured T."""
    assert "transmission_monitor_center_m" in free_standing_sheet_geometry(10e9)


def test_the_monitor_planes_sit_where_the_physics_needs_them():
    """Source, then reflection plane, then the sheet, then the transmission
    plane -- all inside the cell and all clear of the absorbing layers. A
    monitor inside the PML returns a number that looks like a measurement
    and is not."""
    geometry = free_standing_sheet_geometry(10e9)
    half_cell = geometry["cell_size_m"][2] / 2
    pml = geometry["pml_thickness_m"]
    source_z = geometry["port"]["center_m"][2]
    reflection_z = geometry["reflection_monitor_center_m"][2]
    transmission_z = geometry["transmission_monitor_center_m"][2]
    sheet_z = 0.0

    assert -half_cell + pml < source_z < reflection_z < sheet_z
    assert sheet_z < transmission_z < half_cell - pml


def test_reflectance_is_normalised_on_the_plane_it_is_measured_on():
    """The baseline for R is the forward flux at `reference_monitor_center_m`
    in the empty run. Putting it anywhere but the reflection plane would
    normalise a measurement against a different plane's wave."""
    geometry = free_standing_sheet_geometry(10e9)
    assert geometry["reference_monitor_center_m"] == geometry["reflection_monitor_center_m"]


def test_the_sheet_is_several_pixels_thick():
    """Not a demand for accuracy -- the split IS inaccurate at this mesh and
    the tolerances say so -- but a sheet thinner than a pixel is not in the
    simulation at all."""
    geometry = free_standing_sheet_geometry(10e9)
    conductor = geometry["conductors"][0]
    thickness = conductor["p2_m"][2] - conductor["p1_m"][2]
    assert thickness / geometry["mesh_cell_size_m"] >= 4


# --- reading one number out of a spectrum ---------------------------------


def test_a_multi_frequency_spectrum_is_not_silently_reduced():
    """A reference case names ONE frequency. Taking the first point of a
    sweep would check a band edge against the design frequency's published
    answer and call it a pass."""
    record = _measured_two_port_record()
    record["absorption"] = [TWO_PORT_MEASURED_A, 0.31]
    problems = check_reference_case(FREE_STANDING_RESISTIVE_SHEET_TWO_PORT, record)
    assert [p.name for p in problems] == ["absorptance"]
    assert problems[0].actual is None


def test_a_missing_transmittance_is_a_failure_not_a_pass():
    """A run that never measured T is not a run that measured zero."""
    record = _measured_two_port_record()
    del record["transmittance"]
    problems = check_reference_case(FREE_STANDING_RESISTIVE_SHEET_TWO_PORT, record)
    assert [p.name for p in problems] == ["transmittance"]
    assert problems[0].actual is None


def test_the_split_tolerance_still_catches_a_factor_of_two_normalisation_error():
    """Why +/-0.06 on R and T is wide rather than lax: the failure mode it
    exists to catch (#240) is a transmittance uniformly doubled or halved by
    the wrong baseline plane, and both land far outside it."""
    transmittance = next(
        e for e in FREE_STANDING_RESISTIVE_SHEET_TWO_PORT.expected if e.name == "transmittance"
    )
    assert transmittance.matches(TWO_PORT_MEASURED_T)
    assert not transmittance.matches(0.5)
    assert not transmittance.matches(0.125)


def test_the_absorptance_band_is_no_looser_than_the_hand_built_case():
    """Routing the identical problem through the adapter and the loop must
    not need a wider band to pass than posing it by hand does."""
    hand_built = REFERENCE_CASES["free-standing-resistive-sheet-10ghz"].expected[0]
    through_the_loop = next(
        e for e in FREE_STANDING_RESISTIVE_SHEET_TWO_PORT.expected if e.name == "absorptance"
    )
    assert through_the_loop.tolerance <= hand_built.tolerance
    assert through_the_loop.value == hand_built.value
