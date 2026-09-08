"""Tests for the printed-surface sheet-impedance formulas in
rf_tools/calculations.py (issues #111, #128).

These formulas previously existed only inside a browser prototype
(geometry/prototype_lossy_cell_fit.html) and a throwaway bench script, so
every published figure that used them was produced by code nobody could
import. The assertions below pin the implementations to figures the repo has
already published, so the two cannot drift.
"""

import itertools
import math

import pytest

from rf_tools.calculations import (
    COSTA_EQ10_FORM,
    COSTA_EQ10_FORMS,
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
    thin_spacer_capacitance_correction_f,
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
    assert sheet_resistance_for_target_path_resistance(3900, squares_at_10ghz) == pytest.approx(
        108, rel=1e-2
    )


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


# ---------------------------------------------------------------------------
# Costa's thin-spacer capacitance correction (#245, from #190 /
# docs/costa-thin-spacer-correction.md)
# ---------------------------------------------------------------------------
#
# When the spacer under a printed patch grid is thin compared with the cell
# period, the patches start "seeing" the ground plane behind them and store
# more charge than the free-standing grid formula admits. Costa's eq (10)
# adds that charge back. The tests below pin the equation itself -- it was
# transcribed by eye off a 400 dpi render, so a wrong sign, prefactor or
# exponent is the single most likely failure, and an exact arithmetic anchor
# is the only thing that catches it.

# #128's design point, and the reason it is the anchor: at d/p = 0.25 the
# exponent -4*pi*d/p is exactly -pi, so the whole correction is checkable by
# hand. See docs/costa-thin-spacer-correction.md section 7.
ANCHOR_PERIOD_M = 6.0e-3
ANCHOR_GAP_M = 0.498e-3
ANCHOR_SPACER_M = 1.5e-3
ANCHOR_EPS_R = 2.9


def test_the_thin_spacer_correction_matches_the_hand_checked_anchor():
    """docs/costa-thin-spacer-correction.md section 7, at #128's cell
    (p = 6.0 mm, d = 1.50 mm, so d/p = 0.25 and the exponent is exactly -pi):
    exp(-pi) = 0.0432139, -ln(1 - exp(-pi)) = 0.04417544, and the eps0-form
    correction is 1.4940 fF. Asserted tightly on purpose -- this is the test
    that catches a mis-transcribed sign, prefactor or exponent."""
    correction = thin_spacer_capacitance_correction_f(
        ANCHOR_PERIOD_M, ANCHOR_SPACER_M, ANCHOR_EPS_R, form="eps0"
    )
    assert correction * 1e15 == pytest.approx(1.4940, rel=1e-4)
    # And the log factor it is built from, isolated from the prefactor.
    log_factor = correction / (2 * ANCHOR_PERIOD_M * 8.8541878128e-12 / math.pi)
    assert log_factor == pytest.approx(0.04417544257, rel=1e-9)
    assert log_factor == pytest.approx(-math.log(1 - math.exp(-math.pi)), rel=1e-12)


def test_the_correction_is_2_2_percent_of_the_anchor_cells_capacitance():
    """Same section: C0 unloaded is 68.998 fF at g = 0.498 mm, and the bare
    eps0 term is 2.165% of it. The plain reading: the thin spacer makes the
    cell store about two percent more charge, which drags its resonance about
    one percent lower."""
    c0_unloaded = capacitive_grid_sheet_capacitance_f(ANCHOR_PERIOD_M, ANCHOR_GAP_M, eps_r=1.0)
    assert c0_unloaded * 1e15 == pytest.approx(68.998, rel=1e-4)
    eps0_form = thin_spacer_capacitance_correction_f(
        ANCHOR_PERIOD_M, ANCHOR_SPACER_M, ANCHOR_EPS_R, form="eps0"
    )
    assert 100 * eps0_form / c0_unloaded == pytest.approx(2.165, rel=1e-3)


def test_the_two_forms_composed_loaded_capacitances_are_pinned():
    """The numbers a caller actually gets, at #128's cell (p = 6.0 mm,
    g = 0.498 mm, d = 1.50 mm, silicone eps_r = 2.9). These pin the
    COMPOSITION, which is where the two published forms really differ:

        uncorrected  134.549 fF
        "eps0"       137.462 fF   (+2.913 fF, +2.165%)   Costa 2013
        "eps0_epsr"  138.882 fF   (+4.333 fF, +3.220%)   Costa & Borgese 2021

    In plain terms: the two papers disagree about how much extra charge the
    thin spacer adds by about half as much again, not by a factor of three.
    """
    args = (ANCHOR_PERIOD_M, ANCHOR_GAP_M, ANCHOR_EPS_R)
    uncorrected = capacitive_grid_sheet_capacitance_f(*args)
    eps0 = capacitive_grid_sheet_capacitance_f(*args, ANCHOR_SPACER_M, "eps0")
    eps0_epsr = capacitive_grid_sheet_capacitance_f(*args, ANCHOR_SPACER_M, "eps0_epsr")
    assert uncorrected * 1e15 == pytest.approx(134.549, rel=1e-4)
    assert eps0 * 1e15 == pytest.approx(137.462, rel=1e-4)
    assert eps0_epsr * 1e15 == pytest.approx(138.882, rel=1e-4)
    assert 100 * (eps0 - uncorrected) / uncorrected == pytest.approx(2.165, rel=1e-3)
    assert 100 * (eps0_epsr - uncorrected) / uncorrected == pytest.approx(3.220, rel=1e-3)


def test_a_corrected_cell_is_always_more_capacitive_than_an_uncorrected_one():
    """The log's argument is below 1, so its log is negative and the term is
    subtracted -- the capacitance can only rise. Costa's own prose: 'the
    value of the capacitor increases exponentially as the spacer thickness is
    reduced'."""
    uncorrected = capacitive_grid_sheet_capacitance_f(6.0e-3, 0.498e-3, 2.9)
    for spacer in (0.2e-3, 0.75e-3, 1.5e-3, 3.0e-3, 12.0e-3):
        corrected = capacitive_grid_sheet_capacitance_f(
            6.0e-3, 0.498e-3, 2.9, spacer_thickness_m=spacer
        )
        assert corrected > uncorrected


def test_the_correction_decays_smoothly_and_never_reaches_zero():
    """Why #245 applies the term unconditionally instead of gating it at
    d/p = 0.3: it falls off monotonically and is still strictly positive far
    above that ratio, so gating would put a step in the capacitance at exactly
    the ratio this programme's designs cluster around -- an optimiser hazard
    with no physical justification."""
    period = 6.0e-3
    ratios = [0.1, 0.2, 0.25, 0.3, 0.4, 0.5, 0.75, 1.0, 2.0]
    corrections = [thin_spacer_capacitance_correction_f(period, r * period, 2.9) for r in ratios]
    assert all(later < earlier for earlier, later in itertools.pairwise(corrections))
    # Small but strictly non-zero well past the 0.3 gate: under a tenth of a
    # percent of C0 at d/p = 0.5, and still not zero at twice the period.
    c0_unloaded = capacitive_grid_sheet_capacitance_f(period, 0.498e-3, eps_r=1.0)
    at_half = thin_spacer_capacitance_correction_f(period, 0.5 * period, 2.9)
    assert 0 < at_half / c0_unloaded < 0.002
    assert corrections[-1] > 0


def test_omitting_the_spacer_reproduces_todays_uncorrected_value_exactly():
    """Bit-for-bit against the pre-#245 expression written out longhand, not
    approximately: the Babinet dual test above and every free-standing caller
    (no ground plane behind the grid) must be provably untouched.

    The last case is the reason this is `==` and not `pytest.approx`: at
    eps_r = 10.2 the reassociated arithmetic differs in the final bit, so a
    tolerant assertion would not have noticed the change at all."""
    eps0 = 8.8541878128e-12
    for period, gap, eps_r in (
        (9.0e-3, 1.3e-3, 1.0),
        (6.0e-3, 0.498e-3, 2.9),
        (4.0e-3, 0.1639e-3, 2.9),
        (1.0e-3, 0.37e-3, 10.2),
    ):
        eps_eff = grid_effective_permittivity(eps_r)
        before = (
            eps0
            * eps_eff
            * (2 * period / math.pi)
            * math.log(1 / math.sin(math.pi * gap / (2 * period)))
        )
        assert capacitive_grid_sheet_capacitance_f(period, gap, eps_r) == before
        assert capacitive_grid_sheet_capacitance_f(period, gap, eps_r, None, None) == before


def test_both_published_prefactor_terms_are_pinned_and_the_default_is_eps0():
    """#234, unresolved: the 2013 paper prints 2*D*eps0/pi and Costa &
    Borgese 2021 -- citing it -- print 2*D*eps0*eps_r/pi. As bare TERMS the
    second is exactly eps_r times the first; where each one lands is the
    subject of the composition tests below. Carry both; default to the
    conservative 2013 form."""
    assert COSTA_EQ10_FORMS == ("eps0", "eps0_epsr")
    assert COSTA_EQ10_FORM == "eps0"
    eps0_form = thin_spacer_capacitance_correction_f(6.0e-3, 1.5e-3, 2.9, "eps0")
    epsr_form = thin_spacer_capacitance_correction_f(6.0e-3, 1.5e-3, 2.9, "eps0_epsr")
    assert epsr_form == pytest.approx(2.9 * eps0_form, rel=1e-12)
    # The default is the module-level selection, not a per-call whim.
    assert thin_spacer_capacitance_correction_f(6.0e-3, 1.5e-3, 2.9) == eps0_form
    # The eps0 form does not depend on eps_r at all.
    assert thin_spacer_capacitance_correction_f(6.0e-3, 1.5e-3, 1.0, "eps0") == eps0_form


def test_the_two_forms_disagree_by_eps_r_over_eps_eff_not_by_eps_r():
    """Once composed, the 2013 form contributes eps_eff*dC0 to the loaded
    capacitance and the 2021 form contributes eps_r*dC0 -- because the 2021
    term is subtracted from an already-loaded capacitance and so never meets
    eps_eff. The published disagreement is therefore eps_r/eps_eff = 1.487 at
    eps_r = 2.9, not eps_r = 2.9.

    In plain terms: the two papers are about 50% apart on the size of the
    correction, not 200% apart."""
    args = (ANCHOR_PERIOD_M, ANCHOR_GAP_M, ANCHOR_EPS_R)
    uncorrected = capacitive_grid_sheet_capacitance_f(*args)
    eps0_delta = capacitive_grid_sheet_capacitance_f(*args, ANCHOR_SPACER_M, "eps0") - uncorrected
    epsr_delta = (
        capacitive_grid_sheet_capacitance_f(*args, ANCHOR_SPACER_M, "eps0_epsr") - uncorrected
    )
    eps_eff = grid_effective_permittivity(ANCHOR_EPS_R)
    assert epsr_delta / eps0_delta == pytest.approx(ANCHOR_EPS_R / eps_eff, rel=1e-9)
    assert epsr_delta / eps0_delta == pytest.approx(1.4872, rel=1e-4)
    # And the bare terms it is built from: eps_eff*dC0 and eps_r*dC0.
    bare = thin_spacer_capacitance_correction_f(ANCHOR_PERIOD_M, ANCHOR_SPACER_M, ANCHOR_EPS_R)
    assert eps0_delta == pytest.approx(eps_eff * bare, rel=1e-9)
    assert epsr_delta == pytest.approx(ANCHOR_EPS_R * bare, rel=1e-9)


def test_the_eps0_epsr_form_does_not_double_count_the_permittivity():
    """The mistake this test exists to prevent: reading the 2021 prefactor as
    'eps_r times the 2013 term' and then applying it where the 2013 paper
    applies its own term, i.e. eps_eff*(C0 + eps_r*dC0). That lands at
    142.998 fF instead of 138.882 fF -- a correction 190% too large rather
    than 50% -- because eps_r has been counted twice. The 2021 term is
    subtracted from an ALREADY-LOADED capacitance and must not be loaded
    again."""
    args = (ANCHOR_PERIOD_M, ANCHOR_GAP_M, ANCHOR_EPS_R)
    c0_unloaded = capacitive_grid_sheet_capacitance_f(ANCHOR_PERIOD_M, ANCHOR_GAP_M, eps_r=1.0)
    epsr_term = thin_spacer_capacitance_correction_f(
        ANCHOR_PERIOD_M, ANCHOR_SPACER_M, ANCHOR_EPS_R, "eps0_epsr"
    )
    eps_eff = grid_effective_permittivity(ANCHOR_EPS_R)
    double_counted = eps_eff * (c0_unloaded + epsr_term)
    assert double_counted * 1e15 == pytest.approx(142.998, rel=1e-4)
    actual = capacitive_grid_sheet_capacitance_f(*args, ANCHOR_SPACER_M, "eps0_epsr")
    assert actual * 1e15 == pytest.approx(138.882, rel=1e-4)
    assert actual * 1e15 != pytest.approx(double_counted * 1e15, rel=1e-3)
    # Correct composition: the loaded uncorrected value plus the term, as-is.
    assert actual == pytest.approx(eps_eff * c0_unloaded + epsr_term, rel=1e-12)


def test_the_four_mm_cell_is_not_rescued_by_the_correction():
    """#245 story 22 / #186: at `p` = 4.0 mm with a 1.50 mm spacer the ratio
    is `d/p` = 0.375, outside the regime where eq (10) bites, so the
    correction cannot lift the gap the physics wants (~0.164 mm) over the
    printer's 0.2 mm feature floor. Confirmed here rather than assumed.

    In plain terms -- the smaller cell still needs a gap finer than the
    printer can draw, and carrying the correction does not change that.
    """
    period_m, spacer_m, eps_r = 4.0e-3, 1.50e-3, 2.9
    assert spacer_m / period_m == pytest.approx(0.375)

    gap_m = 0.1639e-3
    uncorrected = capacitive_grid_sheet_capacitance_f(period_m, gap_m, eps_r)
    for form in COSTA_EQ10_FORMS:
        corrected = capacitive_grid_sheet_capacitance_f(period_m, gap_m, eps_r, spacer_m, form=form)
        moved = (corrected - uncorrected) / uncorrected
        # Under 1% either way: far too small to close a 0.164 -> 0.200 mm
        # gap, which is a 22% move.
        assert 0 < moved < 0.01, form


def test_an_unknown_eq10_form_is_rejected():
    with pytest.raises(ValueError, match="Unknown eq \\(10\\) form"):
        thin_spacer_capacitance_correction_f(6.0e-3, 1.5e-3, 2.9, "eps_eff")


def test_the_eps0_correction_lands_before_the_effective_permittivity_loading():
    """Costa 2013's composition, which is this module's default: eq (10)
    substitutes for the UNLOADED C0, and eq (6)'s eps_eff = (eps_r + 1)/2
    then loads the corrected value. Adding the free-space term to an
    already-loaded capacitance instead would under-count it by eps_eff.
    This is the single easiest thing to get wrong in #245, so it is asserted
    directly. (The 2021 form deliberately DOES compose the other way -- see
    the two tests above; the difference is the eps_r in its prefactor.)"""
    period, gap, eps_r, spacer = 6.0e-3, 0.498e-3, 2.9, 1.5e-3
    c0_unloaded = capacitive_grid_sheet_capacitance_f(period, gap, eps_r=1.0)
    correction = thin_spacer_capacitance_correction_f(period, spacer, eps_r)
    eps_eff = grid_effective_permittivity(eps_r)
    corrected = capacitive_grid_sheet_capacitance_f(period, gap, eps_r, spacer_thickness_m=spacer)
    assert corrected == pytest.approx(eps_eff * (c0_unloaded + correction), rel=1e-12)
    # The other order is a real, visible difference -- about 1% of the total,
    # not a rounding artefact. (Compared in femtofarads: raw farads are small
    # enough that pytest.approx's default absolute tolerance would swallow
    # every capacitance in this module whole.)
    # NB this is not the 2021 form either: that one carries eps_r in its
    # prefactor, and 138.882 fF is what it gives.
    wrong_order = eps_eff * c0_unloaded + correction
    assert corrected * 1e15 != pytest.approx(wrong_order * 1e15, rel=1e-3)
    assert abs(corrected - wrong_order) / corrected > 0.005
