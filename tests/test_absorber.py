"""Closed-form absorber model (issue #191, rf_tools/absorber.py).

The physics assertions here are the ones that catch a wrong model rather
than a changed one: a short-circuited line's two known limits, the
impedance match that absorption actually requires, and the direction the
answer moves when a lossy stack gets lossier.
"""

import math

import pytest

from rf_tools import calculations
from rf_tools.absorber import (
    ETA0_OHM,
    THIN_SPACER_RATIO,
    absorber_band_response,
    absorptivity,
    grounded_slab_impedance,
    patterned_sheet_impedance,
)
from rf_tools.calculations import COSTA_EQ10_FORM, COSTA_EQ10_FORMS

# A plausible printed X-band stack: silicone spacer, 3 mm cell, 0.2 mm gap.
STACK = {
    "eps_r": 2.9,
    "tan_delta": 0.10,
    "thickness_m": 2.0e-3,
    "period_m": 3.0e-3,
    "gap_m": 0.2e-3,
    "sheet_resistance_ohm_sq": 500.0,
    "squares": 0.1,
}

# #128's own design point (PR #186, geometry/PROTOTYPE-lossy-cell-fit.md):
# 6.0 mm cell, 0.498 mm gap, 1.50 mm silicone spacer. d/p = 0.25, so it sits
# inside the regime where Costa's eq (10) thin-spacer correction bites --
# this is the stack the correction was recovered for, so it is the one the
# tests measure it on.
THIN_STACK = dict(STACK, thickness_m=1.5e-3, period_m=6.0e-3, gap_m=0.498e-3)

# The same cell with the ground plane twice as far back: d/p = 0.50, where
# eq (10)'s exponential has decayed to under 0.1% of C0. Same geometry, so
# any difference between the two tests is the ratio and nothing else.
THICK_STACK = dict(THIN_STACK, thickness_m=3.0e-3)


def _uncorrected_absorptivity(
    frequency_hz: float,
    eps_r: float,
    tan_delta: float,
    thickness_m: float,
    period_m: float,
    gap_m: float | None,
    sheet_resistance_ohm_sq: float,
    squares: float,
) -> float:
    """The pre-#245 model: the same stack with the thin-spacer correction
    left out, rebuilt from the same primitives.

    `patterned_sheet_impedance` computes the uncorrected sheet whenever no
    spacer thickness is handed to it, so the only thing reproduced here is
    the parallel combination and the reflection coefficient -- three lines
    that must stay in step with `absorptivity`. It exists so a test can ask
    "how far did the correction move the answer?", which needs both answers.
    """
    z_d = grounded_slab_impedance(frequency_hz, eps_r, tan_delta, thickness_m)
    z_s = patterned_sheet_impedance(
        frequency_hz, period_m, gap_m, eps_r, tan_delta, sheet_resistance_ohm_sq, squares
    )
    z_in = (z_s * z_d) / (z_s + z_d)
    gamma = (z_in - ETA0_OHM) / (z_in + ETA0_OHM)
    return min(1.0, max(0.0, 1.0 - abs(gamma) ** 2))


def _peak_frequency_hz(curve: list[dict[str, float]]) -> float:
    """Resonance, read off a swept curve as the frequency of PEAK absorption.

    This model has no solver behind it, so the resonance is not available as
    a root -- it is wherever the swept curve happens to be highest, to within
    the sweep step. Tests that use this must therefore sweep finely enough
    that the shift they are looking for is several steps wide.
    """
    return max(curve, key=lambda point: point["absorption"])["frequency_hz"]


def _uncorrected_peak_frequency_hz(
    f_low_hz: float, f_high_hz: float, points: int, **stack: float
) -> float:
    step = (f_high_hz - f_low_hz) / (points - 1)
    curve = [
        {
            "frequency_hz": f_low_hz + i * step,
            "absorption": _uncorrected_absorptivity(f_low_hz + i * step, **stack),
        }
        for i in range(points)
    ]
    return _peak_frequency_hz(curve)


def test_the_uncorrected_helper_still_matches_the_real_model():
    """`_uncorrected_absorptivity` copies three lines out of `absorptivity`
    so a test can ask how far the correction moved the answer. Nothing stops
    those lines drifting apart, so pin them: on a continuous sheet
    (`gap_m=None`) there is no gap capacitance for the correction to move,
    so the two must agree exactly.

    In plain terms -- the test file keeps its own copy of part of the model,
    and this is the check that the copy is still faithful.
    """
    unpatterned = dict(STACK, gap_m=None, squares=1.0)
    for f in (8e9, 10e9, 12e9):
        assert _uncorrected_absorptivity(f, **unpatterned) == absorptivity(f, **unpatterned)


def test_the_recorded_form_cannot_disagree_with_the_numbers():
    """#245's safeguard: the result names which published form produced it.
    A `from ... import COSTA_EQ10_FORM` would freeze that name at import
    time, so overriding the selection moved every number while the result
    went on reporting the old form -- the exact "two runs disagree with no
    way to reconstruct why" failure the key exists to prevent.
    """
    before = absorber_band_response(8e9, 12e9, **THIN_STACK)
    assert before["costa_eq10_form"] == "eps0"

    calculations.COSTA_EQ10_FORM = "eps0_epsr"
    try:
        after = absorber_band_response(8e9, 12e9, **THIN_STACK)
    finally:
        calculations.COSTA_EQ10_FORM = "eps0"

    assert after["costa_eq10_form"] == "eps0_epsr"
    # And the numbers really did move, so the label is tracking something.
    assert after["worst_absorption"] != before["worst_absorption"]
    assert (
        "eps0_epsr"
        in next(v for v in after["validity"] if v["flag"] == "thin_spacer_prefactor_disputed")[
            "assumed"
        ]
    )


def test_quarter_wave_grounded_slab_looks_like_an_open_circuit():
    """A short circuit a quarter-wavelength away transforms to an open --
    the mechanism that lets a resistive sheet dissipate instead of being
    shorted out by the ground plane."""
    f, eps_r = 10e9, 4.0
    quarter_wave_m = 299_792_458.0 / (f * math.sqrt(eps_r)) / 4
    z = grounded_slab_impedance(f, eps_r, 0.0, quarter_wave_m)
    assert abs(z) > 1e6


def test_electrically_thin_grounded_slab_looks_like_a_short():
    z = grounded_slab_impedance(10e9, 4.0, 0.0, 1e-6)
    assert abs(z) < 1.0


def test_lossless_slab_impedance_is_purely_reactive():
    z = grounded_slab_impedance(10e9, 4.0, 0.0, 0.5e-3)
    assert z.real == pytest.approx(0.0, abs=1e-9)


def test_lossy_slab_gains_a_real_part():
    """Substrate dissipation is a real term, not a rounding detail --
    adopting the full model moved substrate loss on silicone from a few
    per cent of the loss budget to 20-36 % of it."""
    z = grounded_slab_impedance(10e9, 2.9, 0.10, 2.0e-3)
    assert z.real > 0.0


def test_absorption_peaks_where_the_surface_matches_free_space():
    """Absorption is an impedance match: it is high exactly where the
    stack's input impedance approaches eta_0, and low where it does not."""
    best_a, best_f = 0.0, None
    for i in range(400):
        f = 4e9 + i * 0.1e9
        a = absorptivity(f, **STACK)
        if a > best_a:
            best_a, best_f = a, f
    assert best_a > 0.9

    z_s = patterned_sheet_impedance(
        best_f,
        STACK["period_m"],
        STACK["gap_m"],
        STACK["eps_r"],
        STACK["tan_delta"],
        STACK["sheet_resistance_ohm_sq"],
        STACK["squares"],
    )
    z_d = grounded_slab_impedance(best_f, STACK["eps_r"], STACK["tan_delta"], STACK["thickness_m"])
    z_in = (z_s * z_d) / (z_s + z_d)
    # At the absorption peak the surface must look RESISTIVE and of roughly
    # free-space magnitude: the reactance is largely cancelled (that is what
    # resonance means here) and what remains is near eta_0. Asserting
    # |z_in - eta_0| directly would just restate A = 1 - |Gamma|^2 and prove
    # nothing about the mechanism.
    assert 0.4 * ETA0_OHM < z_in.real < 2.5 * ETA0_OHM
    assert abs(z_in.imag) < z_in.real


def test_absorption_is_bounded_to_a_physical_range():
    for i in range(200):
        a = absorptivity(1e9 + i * 0.2e9, **STACK)
        assert 0.0 <= a <= 1.0


def test_a_far_too_resistive_sheet_reflects_like_a_ground_plane():
    """Example 3's I-shape multiplies 500 ohm/sq into ~6.7 kohm/sq. Against
    a GROUND-BACKED stack that is a huge mismatch and absorbs almost
    nothing -- which is why that device is two-port and must not be scored
    with this model."""
    over = dict(STACK, squares=13.3)
    assert absorptivity(10e9, **over) < 0.2


def test_squares_is_the_loss_knob_and_has_an_optimum():
    """More squares is not monotonically better or worse: the sheet
    resistance has to land near eta_0, so absorption rises then falls."""
    without_squares = {k: v for k, v in STACK.items() if k != "squares"}
    scores = {
        n: absorber_band_response(8e9, 12e9, squares=n, **without_squares)["best_absorption"]
        for n in (0.01, 0.1, 1.0, 13.3)
    }
    assert scores[0.1] > scores[0.01]
    assert scores[0.1] > scores[1.0] > scores[13.3]


def test_band_response_reports_the_worst_frequency_not_the_average():
    """#110: score the single worst-absorbing frequency in band. A design
    with one deep null and poor edges must not be flattered by its peak."""
    r = absorber_band_response(8e9, 12e9, **STACK)
    curve = [p["absorption"] for p in r["curve"]]
    assert r["worst_absorption"] == pytest.approx(min(curve))
    assert r["best_absorption"] == pytest.approx(max(curve))
    assert r["worst_absorption"] <= sum(curve) / len(curve)


def test_band_response_self_tags_no_provenance():
    """#506: provenance tagging belongs to the caller (the design loop's
    ANALYSIS handler tags `decision.provenance` explicitly -- see
    orchestration/design_loop.py's `_handle_analysis_absorber`), the same
    convention `rf_tools/filter_synthesis.py` documents and follows. This
    calculation function returns a plain result with no second, undocumented
    source of truth for that field."""
    r = absorber_band_response(8e9, 12e9, **STACK)
    assert "provenance" not in r


def test_the_spacer_thickness_reaches_the_sheet_and_lowers_its_reactance():
    """A ground plane 1.5 mm behind the grid stores extra charge in the
    gaps, and more capacitance means less reactance at a fixed frequency.

    `patterned_sheet_impedance` is public surface with its own tests above,
    so this is behaviour at a seam, not a check that an argument was
    threaded through -- the assertions below would all still hold if the
    correction reached the capacitance by some other route.

    In plain terms -- metal close behind the printed pattern makes the gaps
    hold more charge, which makes the sheet easier for the wave to push
    current through.
    """
    common = (10e9, THIN_STACK["period_m"], THIN_STACK["gap_m"], THIN_STACK["eps_r"])
    tail = (THIN_STACK["tan_delta"], STACK["sheet_resistance_ohm_sq"], STACK["squares"])
    free_standing = patterned_sheet_impedance(*common, *tail)
    grounded = patterned_sheet_impedance(*common, *tail, THIN_STACK["thickness_m"])

    assert abs(grounded.imag) < abs(free_standing.imag)
    # The real part moves too, and should: it is the printed film's own
    # R_s*N_squares (50 ohm here) PLUS the gap dielectric's dissipation,
    # which is 1/(omega*C*tan_d) and so falls as the capacitance rises. The
    # film's own contribution is the floor and is untouched by what sits
    # behind the sheet.
    film_only = STACK["sheet_resistance_ohm_sq"] * STACK["squares"]
    assert film_only < grounded.real < free_standing.real


def test_thin_spacer_resonates_lower_once_the_costa_term_is_carried():
    """#245: with eq (10) applied the gap capacitance rises, so the stack
    resonates BELOW where the uncorrected model drew it.

    At #128's design point the recomputation in
    `docs/costa-thin-spacer-correction.md` §7 puts that shift near -1% for
    the `eps0` form. The assertion here is direction plus order of
    magnitude, not a pinned digit: the resonance is read off a swept curve,
    not solved for, so it is only ever accurate to the sweep step.
    """
    f_low, f_high, points = 9.5e9, 11.0e9, 1501  # 1 MHz resolution
    corrected = _peak_frequency_hz(
        absorber_band_response(f_low, f_high, points=points, **THIN_STACK)["curve"]
    )
    uncorrected = _uncorrected_peak_frequency_hz(f_low, f_high, points, **THIN_STACK)

    assert corrected < uncorrected
    shift_percent = 100 * (corrected - uncorrected) / uncorrected
    assert -2.0 < shift_percent < -0.4


def test_a_thick_spacer_is_left_materially_alone_by_the_correction():
    """At d/p = 0.5 eq (10)'s exponential has decayed to under 0.1% of C0.
    Applying it unconditionally is therefore safe: it does not disturb the
    designs that were never in its regime."""
    f_low, f_high, points = 6.5e9, 7.3e9, 1601  # 0.5 MHz resolution
    response = absorber_band_response(f_low, f_high, points=points, **THICK_STACK)
    corrected = _peak_frequency_hz(response["curve"])
    uncorrected = _uncorrected_peak_frequency_hz(f_low, f_high, points, **THICK_STACK)

    assert abs(corrected - uncorrected) / uncorrected < 1e-3
    uncorrected_peak = max(
        _uncorrected_absorptivity(point["frequency_hz"], **THICK_STACK)
        for point in response["curve"]
    )
    assert response["best_absorption"] == pytest.approx(uncorrected_peak, abs=1e-3)


def test_the_thin_spacer_bias_is_no_longer_reported_as_unrecovered():
    """#190's flag said the term was missing. It is not missing any more,
    and a flag that outlives its cause teaches a reader the wrong thing."""
    response = absorber_band_response(8e9, 12e9, **THIN_STACK)
    assert "thin_spacer_bias_unrecovered" not in {v["flag"] for v in response["validity"]}


def test_thin_spacer_flags_the_disputed_prefactor_and_a_thick_one_does_not():
    """What survives #245 is narrower than what it replaced: the correction
    is applied, but two papers by the same author publish it with different
    prefactors at different composition points (#234). The flag fires only
    where the correction is big enough for that disagreement to matter."""
    thin = absorber_band_response(8e9, 12e9, **THIN_STACK)
    warnings = [v for v in thin["validity"] if v["flag"] == "thin_spacer_prefactor_disputed"]
    assert len(warnings) == 1
    warning = warnings[0]

    # Charter: every warning names what is assumed, what it costs, and the
    # cheapest way to find out.
    assert warning["assumed"] and warning["costs"] and warning["cheapest_test"]
    text = " ".join(warning.values())
    assert "#234" in text
    # It must say the correction IS applied, in which form, and that the
    # rival form differs by eps_r/eps_eff -- 1.487 here, NOT eps_r = 2.9.
    assert COSTA_EQ10_FORM in text
    assert "1.487" in text
    assert "Tretyakov" in text

    thick = absorber_band_response(6.5e9, 7.3e9, **THICK_STACK)
    assert "thin_spacer_prefactor_disputed" not in {v["flag"] for v in thick["validity"]}
    assert THICK_STACK["thickness_m"] / THICK_STACK["period_m"] >= THIN_SPACER_RATIO


def test_the_result_records_which_published_form_produced_the_numbers():
    """A selectable constant that leaves no trace in the result is how two
    runs come to disagree with no way to reconstruct why. Settling #234
    changes the numbers, so the answer has to carry which form it used."""
    response = absorber_band_response(8e9, 12e9, **THIN_STACK)
    assert response["costa_eq10_form"] == COSTA_EQ10_FORM
    assert response["costa_eq10_form"] in COSTA_EQ10_FORMS
    # A thick stack carries the correction too, so it records the form too.
    thick = absorber_band_response(6.5e9, 7.3e9, **THICK_STACK)
    assert thick["costa_eq10_form"] == COSTA_EQ10_FORM


def test_absorption_stays_physical_with_the_correction_active():
    """The correction raises a capacitance; a passive stack must still not
    absorb more than the power that hits it."""
    response = absorber_band_response(2e9, 20e9, points=361, **THIN_STACK)
    for point in response["curve"]:
        assert 0.0 <= point["absorption"] <= 1.0


def test_rozanov_advises_and_never_blocks():
    """#129: report the bound, never fail a candidate for appearing to beat
    it -- that means an assumption was violated, and the flag is the useful
    output."""
    r = absorber_band_response(8e9, 12e9, **dict(STACK, thickness_m=0.2e-3))
    assert "below_rozanov_floor_for_10db" in {v["flag"] for v in r["validity"]}
    assert isinstance(r["worst_absorption"], float)
    assert r["rozanov_min_thickness_m"] > 0


def test_rejects_an_inverted_band():
    with pytest.raises(ValueError, match="f_high_hz"):
        absorber_band_response(12e9, 8e9, **STACK)


def test_rejects_a_gap_wider_than_the_period():
    with pytest.raises(ValueError, match="gap_m"):
        absorptivity(**dict(STACK, gap_m=5.0e-3), frequency_hz=10e9)


def test_rejects_nonphysical_permittivity():
    with pytest.raises(ValueError, match="eps_r"):
        grounded_slab_impedance(10e9, 0.5, 0.0, 1e-3)


def test_rejects_a_nan_frequency():
    """#494: NaN compares False against every bound (`nan <= 0` is False), so
    a bare `<= 0` check silently lets it through where a normal non-positive
    value would be rejected. `_require_positive` must guard `math.isfinite`
    too, the same way `rf_tools.physical_bounds`'s own copy already does."""
    with pytest.raises(ValueError, match="frequency_hz"):
        grounded_slab_impedance(math.nan, STACK["eps_r"], STACK["tan_delta"], STACK["thickness_m"])
