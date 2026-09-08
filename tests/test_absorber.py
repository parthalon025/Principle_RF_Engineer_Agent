"""Closed-form absorber model (issue #191, rf_tools/absorber.py).

The physics assertions here are the ones that catch a wrong model rather
than a changed one: a short-circuited line's two known limits, the
impedance match that absorption actually requires, and the direction the
answer moves when a lossy stack gets lossier.
"""

import math

import pytest

from rf_tools.absorber import (
    ETA0_OHM,
    absorber_band_response,
    absorptivity,
    grounded_slab_impedance,
    patterned_sheet_impedance,
)

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
    assert r["provenance"] == "CALCULATED"


def test_thin_spacer_warns_about_the_unrecovered_costa_term():
    """#190: below ~0.3 spacer-to-period the fast tier carries a known,
    unquantified bias. It must warn and still return a number."""
    r = absorber_band_response(8e9, 12e9, **dict(STACK, thickness_m=0.5e-3))
    flags = {v["flag"] for v in r["validity"]}
    assert "thin_spacer_bias_unrecovered" in flags
    assert r["worst_absorption"] is not None

    warning = next(v for v in r["validity"] if v["flag"] == "thin_spacer_bias_unrecovered")
    # Charter: every warning names what is assumed, what it costs, and the
    # cheapest way to find out.
    assert warning["assumed"] and warning["costs"] and warning["cheapest_test"]


def test_a_thick_enough_spacer_raises_no_thin_spacer_warning():
    r = absorber_band_response(8e9, 12e9, **dict(STACK, thickness_m=1.2e-3))
    assert "thin_spacer_bias_unrecovered" not in {v["flag"] for v in r["validity"]}


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
