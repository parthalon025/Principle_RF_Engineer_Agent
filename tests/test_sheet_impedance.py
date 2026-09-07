"""Tests for the printed-surface sheet-impedance formulas in
rf_tools/calculations.py (issues #111, #128).

These formulas previously existed only inside a browser prototype
(geometry/prototype_lossy_cell_fit.html) and a throwaway bench script, so
every published figure that used them was produced by code nobody could
import. The assertions below pin the implementations to figures the repo has
already published, so the two cannot drift.
"""

import math

import pytest

from rf_tools.calculations import (
    capacitive_grid_sheet_capacitance_f,
    grid_effective_permittivity,
    grid_gap_loss_tangent,
    inductive_grid_sheet_inductance_h,
    min_overlay_sheet_resistance_ohm_sq,
    path_resistance_from_squares,
    sheet_resistance_dc_ohm_sq,
    sheet_resistance_for_target_path_resistance,
    sheet_resistance_ohm_sq,
    skin_depth_m,
    skin_depths_of_thickness,
    squares_count,
)

# ---------------------------------------------------------------------------
# The grid pair: capacitive patches and their exact Babinet dual
# ---------------------------------------------------------------------------


def test_ring_inductance_reproduces_the_published_bench_figure():
    """docs/supercell-ring-inductance-bench.md: 'A 0.5 mm trace on a 9.0 mm
    period gives 4392 pH/sq' -- the figure that killed the ring hypothesis."""
    inductance = inductive_grid_sheet_inductance_h(9.0e-3, 0.5e-3)
    assert inductance * 1e12 == pytest.approx(4392, rel=1e-3)


def test_the_two_grid_formulas_are_babinet_duals_of_one_another():
    """Same logarithm, same argument shape -- the capacitance's gap and the
    inductance's strip width play the same role. Feeding both the same
    fraction of the period must give the same log factor."""
    period, feature = 9.0e-3, 1.3e-3
    capacitance = capacitive_grid_sheet_capacitance_f(period, feature, eps_r=1.0)
    inductance = inductive_grid_sheet_inductance_h(period, feature)
    log_from_c = capacitance / (8.8541878128e-12 * 1.0 * (2 * period / math.pi))
    log_from_l = inductance / (4e-7 * math.pi * (period / (2 * math.pi)))
    assert log_from_c == pytest.approx(log_from_l, rel=1e-12)


def test_a_narrower_gap_is_more_capacitive_and_a_narrower_strip_more_inductive():
    assert capacitive_grid_sheet_capacitance_f(
        9e-3, 0.5e-3, 3.0
    ) > capacitive_grid_sheet_capacitance_f(9e-3, 2.0e-3, 3.0)
    assert inductive_grid_sheet_inductance_h(9e-3, 0.2e-3) > inductive_grid_sheet_inductance_h(
        9e-3, 2.0e-3
    )


def test_a_feature_cannot_be_wider_than_its_own_period():
    with pytest.raises(ValueError, match="smaller than period_m"):
        capacitive_grid_sheet_capacitance_f(9e-3, 9e-3, 3.0)
    with pytest.raises(ValueError, match="smaller than period_m"):
        inductive_grid_sheet_inductance_h(9e-3, 12e-3)


def test_the_gap_sees_half_air_and_a_diluted_loss_tangent():
    assert grid_effective_permittivity(3.0) == pytest.approx(2.0)
    # Always LESS than the bulk substrate's -- using the bulk figure
    # overstates the gap's dissipation.
    assert grid_gap_loss_tangent(3.0, 0.10) == pytest.approx(0.075)
    assert grid_gap_loss_tangent(3.0, 0.10) < 0.10


# ---------------------------------------------------------------------------
# The squares rule (#128): what the wave sees is R_sheet x squares
# ---------------------------------------------------------------------------


def test_squares_count_is_scale_invariant():
    """A pure shape ratio -- which is why a squares figure transfers from a
    published design at one frequency to the same shape scaled to another."""
    assert squares_count(4.0e-3, 0.245e-3) == pytest.approx(squares_count(4.0e-6, 0.245e-6))


def test_the_published_ring_transfer_reproduces():
    """docs/five-paper-absorber-corpus-findings.md section 3: P1's outer ring
    is 449.2 squares at 8.681 ohm/sq -> 3,900 ohm; the same ring scaled to
    10 GHz is 7.203 mm around, giving 36.0 squares at a printable 0.2 mm
    line, so ~108 ohm/sq reproduces the same loop resistance."""
    assert path_resistance_from_squares(8.681, 449.2) == pytest.approx(3900, rel=1e-3)
    squares_at_10ghz = squares_count(7.203e-3, 0.2e-3)
    assert squares_at_10ghz == pytest.approx(36.0, rel=1e-2)
    assert sheet_resistance_for_target_path_resistance(
        3900, squares_at_10ghz
    ) == pytest.approx(108, rel=1e-2)


def test_the_programmes_own_carbon_bridge_is_a_fraction_of_a_square():
    """0.245 x 4.0 mm carried along its short axis is 0.06 squares -- the low
    end of the corpus's 0.06-to-36 range, which is how one ink spans four
    orders of magnitude of loop resistance."""
    assert squares_count(0.245e-3, 4.0e-3) == pytest.approx(0.061, abs=0.002)


def test_geometry_spans_the_ink_catalogue_gap():
    """One ink at 250-1000 ohm/sq across 0.06-36 squares brackets every
    target the corpus implies -- the point of #128."""
    lowest = path_resistance_from_squares(250, 0.06)
    highest = path_resistance_from_squares(1000, 36.0)
    assert lowest < 20
    assert highest > 30_000


# ---------------------------------------------------------------------------
# Resistive overlay: the multispectral continuity threshold
# ---------------------------------------------------------------------------


def test_overlay_thresholds_reproduce_the_published_numbers():
    """section 4: 'must exceed 407 ohm/sq to leave a 90 % absorption floor
    intact, and 1,695 ohm/sq for a 99 % floor'."""
    assert min_overlay_sheet_resistance_ohm_sq(0.90) == pytest.approx(407, rel=1e-2)
    assert min_overlay_sheet_resistance_ohm_sq(0.99) == pytest.approx(1695, rel=1e-2)


def test_a_stricter_absorption_floor_demands_a_more_resistive_overlay():
    assert min_overlay_sheet_resistance_ohm_sq(0.99) > min_overlay_sheet_resistance_ohm_sq(0.90)


def test_absorption_outside_zero_to_one_is_rejected():
    for bad in (0.0, 1.0, 1.5, -0.1):
        with pytest.raises(ValueError, match="strictly between"):
            min_overlay_sheet_resistance_ohm_sq(bad)


# ---------------------------------------------------------------------------
# Sheet resistance: the DC-formula-at-RF error, gated
# ---------------------------------------------------------------------------


def test_the_dc_and_rf_forms_agree_for_a_film_much_thinner_than_a_skin_depth():
    sigma, thickness = 2.22e6, 0.01e-6
    assert sheet_resistance_ohm_sq(sigma, thickness, 10e9) == pytest.approx(
        sheet_resistance_dc_ohm_sq(sigma, thickness), rel=1e-3
    )


def test_a_thick_film_saturates_at_the_half_space_limit():
    """Past a few skin depths, extra thickness buys nothing: the sheet
    resistance stops falling and settles at 1/(sigma*delta)."""
    sigma, frequency = 2.22e6, 10e9
    delta = skin_depth_m(frequency, sigma)
    saturated = 1 / (sigma * delta)
    assert sheet_resistance_ohm_sq(sigma, 20e-6, frequency) == pytest.approx(saturated, rel=1e-2)
    assert sheet_resistance_ohm_sq(sigma, 35e-6, frequency) == pytest.approx(saturated, rel=1e-2)


def test_the_dc_formula_understates_a_thick_film_by_a_large_factor():
    """The documented repeat error, quantified: at 20 um and 10 GHz the DC
    expression claims roughly a sixth of the true sheet resistance."""
    sigma, thickness, frequency = 2.22e6, 20e-6, 10e9
    dc = sheet_resistance_dc_ohm_sq(sigma, thickness)
    rf = sheet_resistance_ohm_sq(sigma, thickness, frequency)
    assert rf > 5 * dc
    assert skin_depths_of_thickness(thickness, frequency, sigma) > 2


def test_omitting_the_frequency_gives_the_dc_answer_explicitly():
    """The frequency argument is optional so a genuine DC question stays
    easy -- but it must not silently produce an RF answer, or vice versa."""
    sigma, thickness = 2.22e6, 20e-6
    assert sheet_resistance_ohm_sq(sigma, thickness) == pytest.approx(
        sheet_resistance_dc_ohm_sq(sigma, thickness)
    )


def test_skin_depth_falls_as_the_square_root_of_frequency():
    sigma = 2.22e6
    assert skin_depth_m(1e9, sigma) / skin_depth_m(4e9, sigma) == pytest.approx(2.0)


def test_a_carbon_salisbury_screen_needs_a_realistic_thickness():
    """A 377 ohm/sq resistive sheet from a 167 S/m carbon ink is ~15.9 um --
    a thickness a printer can actually deposit, which is why the 'no ink in
    the window' reading was wrong."""
    thickness = 1 / (167 * 376.730313412)
    assert thickness * 1e6 == pytest.approx(15.9, rel=1e-2)
    assert sheet_resistance_dc_ohm_sq(167, thickness) == pytest.approx(376.73, rel=1e-3)
