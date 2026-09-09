"""Filter-prototype synthesis, checked against published g-value tables.

Issue #143. The expected values here are *independently sourced* -- Pozar,
"Microwave Engineering" 4th ed., Tables 8.3 (maximally flat) and 8.4
(equal-ripple) -- not regenerated from this implementation. That is the whole
point of the fixture: a self-consistency check would pass just as happily on a
wrong formula. Tables are printed to 4 decimal places, so comparisons use a
tolerance that reflects the table's own rounding, not float precision.
"""

import math

import pytest

from rf_tools.calculations import (
    microstrip_effective_permittivity,
    microstrip_synthesize_width_m,
)
from rf_tools.filter_synthesis import (
    butterworth_g_values,
    chebyshev_g_values,
    realize_lowpass_stepped_impedance_microstrip,
    synthesize_filter,
)

TABLE_TOL = 1e-3

# Pozar Table 8.3 -- maximally flat (Butterworth), g1..gn. g_{n+1} is always 1.
BUTTERWORTH_TABLE = {
    1: [2.0000],
    2: [1.4142, 1.4142],
    3: [1.0000, 2.0000, 1.0000],
    4: [0.7654, 1.8478, 1.8478, 0.7654],
    5: [0.6180, 1.6180, 2.0000, 1.6180, 0.6180],
    6: [0.5176, 1.4142, 1.9318, 1.9318, 1.4142, 0.5176],
}

# Pozar Table 8.4 -- equal-ripple (Chebyshev). Value is (g1..gn, g_{n+1}).
CHEBYSHEV_TABLE = {
    (0.5, 1): ([0.6986], 1.0000),
    (0.5, 2): ([1.4029, 0.7071], 1.9841),
    (0.5, 3): ([1.5963, 1.0967, 1.5963], 1.0000),
    (0.5, 4): ([1.6703, 1.1926, 2.3661, 0.8419], 1.9841),
    (0.5, 5): ([1.7058, 1.2296, 2.5408, 1.2296, 1.7058], 1.0000),
    (3.0, 1): ([1.9953], 1.0000),
    (3.0, 2): ([3.1013, 0.5339], 5.8095),
    (3.0, 3): ([3.3487, 0.7117, 3.3487], 1.0000),
    (3.0, 5): ([3.4817, 0.7618, 4.5381, 0.7618, 3.4817], 1.0000),
}


@pytest.mark.parametrize("order", sorted(BUTTERWORTH_TABLE))
def test_butterworth_g_values_match_published_table(order):
    g = butterworth_g_values(order)
    assert g[0] == pytest.approx(1.0)
    assert list(g[1:-1]) == pytest.approx(BUTTERWORTH_TABLE[order], abs=TABLE_TOL)
    assert g[-1] == pytest.approx(1.0, abs=TABLE_TOL)


@pytest.mark.parametrize(("ripple_db", "order"), sorted(CHEBYSHEV_TABLE))
def test_chebyshev_g_values_match_published_table(ripple_db, order):
    expected_g, expected_load = CHEBYSHEV_TABLE[(ripple_db, order)]
    g = chebyshev_g_values(order, ripple_db)
    assert g[0] == pytest.approx(1.0)
    assert list(g[1:-1]) == pytest.approx(expected_g, abs=TABLE_TOL)
    assert g[-1] == pytest.approx(expected_load, abs=TABLE_TOL)


def test_butterworth_g_values_are_symmetric():
    """A maximally-flat prototype is its own mirror image."""
    g = butterworth_g_values(7)
    assert list(g[1:-1]) == pytest.approx(list(reversed(g[1:-1])))


def test_odd_order_chebyshev_terminates_in_the_source_impedance():
    """Odd-order equal-ripple ends at g_{n+1} = 1; even-order does not.

    This is the classic surprise: an even-order Chebyshev filter is *not*
    matched to its source impedance at the load end, and the mismatch grows
    with ripple. Guarding it here because it is the kind of thing a plausible
    but wrong implementation silently normalizes away.
    """
    assert chebyshev_g_values(3, 0.5)[-1] == pytest.approx(1.0, abs=TABLE_TOL)
    assert chebyshev_g_values(4, 0.5)[-1] == pytest.approx(1.9841, abs=TABLE_TOL)
    assert chebyshev_g_values(2, 3.0)[-1] == pytest.approx(5.8095, abs=TABLE_TOL)


@pytest.mark.parametrize("order", [0, -1])
def test_order_must_be_positive(order):
    with pytest.raises(ValueError, match="[Oo]rder"):
        butterworth_g_values(order)


def test_chebyshev_ripple_must_be_positive():
    with pytest.raises(ValueError, match="[Rr]ipple"):
        chebyshev_g_values(3, 0.0)


# --- denormalization into real component values ---------------------------


def test_lowpass_shunt_first_gives_alternating_c_and_l():
    """n=3 Butterworth, 1 GHz, 50 ohm, shunt-first: C, L, C."""
    net = synthesize_filter(response="butterworth", band="lowpass", order=3, cutoff_hz=1e9)
    assert [(e.position, e.topology) for e in net.elements] == [
        ("shunt", "C"),
        ("series", "L"),
        ("shunt", "C"),
    ]
    wc = 2 * math.pi * 1e9
    # g = 1.0, 2.0, 1.0 -> C1 = g1/(R0 wc), L2 = g2 R0/wc, C3 = g3/(R0 wc)
    assert net.elements[0].capacitance_f == pytest.approx(1.0 / (50.0 * wc))
    assert net.elements[1].inductance_h == pytest.approx(2.0 * 50.0 / wc)
    assert net.elements[2].capacitance_f == pytest.approx(1.0 / (50.0 * wc))


def test_lowpass_series_first_is_the_dual_ladder():
    """The same g-values, realized L, C, L instead of C, L, C."""
    net = synthesize_filter(
        response="butterworth",
        band="lowpass",
        order=3,
        cutoff_hz=1e9,
        first_element="series",
    )
    assert [(e.position, e.topology) for e in net.elements] == [
        ("series", "L"),
        ("shunt", "C"),
        ("series", "L"),
    ]
    wc = 2 * math.pi * 1e9
    assert net.elements[0].inductance_h == pytest.approx(1.0 * 50.0 / wc)
    assert net.elements[1].capacitance_f == pytest.approx(2.0 / (50.0 * wc))


def test_highpass_swaps_element_kinds_and_inverts_g():
    net = synthesize_filter(response="butterworth", band="highpass", order=3, cutoff_hz=1e9)
    assert [(e.position, e.topology) for e in net.elements] == [
        ("shunt", "L"),
        ("series", "C"),
        ("shunt", "L"),
    ]
    wc = 2 * math.pi * 1e9
    # shunt L = R0/(wc g), series C = 1/(R0 wc g)
    assert net.elements[0].inductance_h == pytest.approx(50.0 / (wc * 1.0))
    assert net.elements[1].capacitance_f == pytest.approx(1.0 / (50.0 * wc * 2.0))


def test_bandpass_elements_resonate_at_the_centre_frequency():
    """Every branch of a band-pass ladder resonates at f0 -- the defining check."""
    f0 = 2.4e9
    net = synthesize_filter(
        response="chebyshev",
        band="bandpass",
        order=3,
        ripple_db=0.5,
        center_hz=f0,
        bandwidth_hz=0.24e9,
    )
    assert len(net.elements) == 3
    for element in net.elements:
        assert element.topology in {"LC_SERIES", "LC_PARALLEL"}
        resonant = 1.0 / (2 * math.pi * math.sqrt(element.inductance_h * element.capacitance_f))
        assert resonant == pytest.approx(f0, rel=1e-9)


def test_bandstop_elements_also_resonate_at_the_centre_frequency():
    f0 = 2.4e9
    net = synthesize_filter(
        response="butterworth",
        band="bandstop",
        order=3,
        center_hz=f0,
        bandwidth_hz=0.5e9,
    )
    for element in net.elements:
        resonant = 1.0 / (2 * math.pi * math.sqrt(element.inductance_h * element.capacitance_f))
        assert resonant == pytest.approx(f0, rel=1e-9)


def test_bandpass_series_branch_is_series_lc_and_shunt_branch_is_shunt_lc():
    net = synthesize_filter(
        response="butterworth",
        band="bandpass",
        order=3,
        center_hz=1e9,
        bandwidth_hz=1e8,
    )
    assert [(e.position, e.topology) for e in net.elements] == [
        ("shunt", "LC_PARALLEL"),
        ("series", "LC_SERIES"),
        ("shunt", "LC_PARALLEL"),
    ]


def test_bandstop_inverts_the_bandpass_branch_topologies():
    net = synthesize_filter(
        response="butterworth",
        band="bandstop",
        order=3,
        center_hz=1e9,
        bandwidth_hz=1e8,
    )
    assert [(e.position, e.topology) for e in net.elements] == [
        ("shunt", "LC_SERIES"),
        ("series", "LC_PARALLEL"),
        ("shunt", "LC_SERIES"),
    ]


def test_load_impedance_direction_depends_on_how_the_ladder_ends():
    """g_(N+1) is a load RESISTANCE when the ladder ends shunt and a load
    CONDUCTANCE when it ends series (Pozar fig. 8.25), so it is multiplied in
    one case and divided in the other. Reading it as a resistance both ways
    produces a filter that misses its own ripple spec -- see
    test_even_order_chebyshev_meets_its_ripple_spec_into_its_stated_load."""
    # order 2, shunt-first -> ends on a series inductor -> conductance
    ends_series = synthesize_filter(
        response="chebyshev",
        band="lowpass",
        order=2,
        ripple_db=3.0,
        cutoff_hz=1e9,
        impedance_ohm=50.0,
        first_element="shunt",
    )
    assert ends_series.elements[-1].position == "series"
    assert ends_series.load_impedance_ohm == pytest.approx(50.0 / 5.8095, abs=0.01)

    # order 2, series-first -> ends on a shunt capacitor -> resistance
    ends_shunt = synthesize_filter(
        response="chebyshev",
        band="lowpass",
        order=2,
        ripple_db=3.0,
        cutoff_hz=1e9,
        impedance_ohm=50.0,
        first_element="series",
    )
    assert ends_shunt.elements[-1].position == "shunt"
    assert ends_shunt.load_impedance_ohm == pytest.approx(50.0 * 5.8095, abs=0.1)


def test_odd_order_chebyshev_is_matched_to_its_source():
    odd = synthesize_filter(
        response="chebyshev", band="lowpass", order=3, ripple_db=3.0, cutoff_hz=1e9
    )
    assert odd.load_impedance_ohm == pytest.approx(50.0)


def test_scaling_impedance_scales_l_up_and_c_down():
    """Doubling R0 doubles every inductance and halves every capacitance."""
    base = synthesize_filter(response="butterworth", band="lowpass", order=3, cutoff_hz=1e9)
    doubled = synthesize_filter(
        response="butterworth",
        band="lowpass",
        order=3,
        cutoff_hz=1e9,
        impedance_ohm=100.0,
    )
    assert doubled.elements[1].inductance_h == pytest.approx(2 * base.elements[1].inductance_h)
    assert doubled.elements[0].capacitance_f == pytest.approx(base.elements[0].capacitance_f / 2)


# --- input validation -----------------------------------------------------


def test_chebyshev_requires_a_ripple():
    with pytest.raises(ValueError, match="ripple_db"):
        synthesize_filter(response="chebyshev", band="lowpass", order=3, cutoff_hz=1e9)


def test_butterworth_rejects_a_ripple():
    """Maximally flat has no ripple by definition -- accepting one silently
    would let a caller believe a ripple spec was honoured when it was ignored."""
    with pytest.raises(ValueError, match="ripple_db"):
        synthesize_filter(
            response="butterworth",
            band="lowpass",
            order=3,
            cutoff_hz=1e9,
            ripple_db=0.5,
        )


def test_lowpass_requires_cutoff_not_centre():
    with pytest.raises(ValueError, match="cutoff_hz"):
        synthesize_filter(response="butterworth", band="lowpass", order=3, center_hz=1e9)


def test_bandpass_requires_centre_and_bandwidth():
    with pytest.raises(ValueError, match="center_hz|bandwidth_hz"):
        synthesize_filter(response="butterworth", band="bandpass", order=3, cutoff_hz=1e9)


def test_bandwidth_must_be_narrower_than_the_centre_frequency():
    with pytest.raises(ValueError, match="bandwidth_hz"):
        synthesize_filter(
            response="butterworth",
            band="bandpass",
            order=3,
            center_hz=1e9,
            bandwidth_hz=2e9,
        )


def test_unknown_response_and_band_are_rejected():
    with pytest.raises(ValueError, match="response"):
        synthesize_filter(response="elliptic", band="lowpass", order=3, cutoff_hz=1e9)
    with pytest.raises(ValueError, match="band"):
        synthesize_filter(response="butterworth", band="allpass", order=3, cutoff_hz=1e9)


# --- end-to-end: analyze the synthesized ladder as a circuit ---------------
#
# The g-value tests above check the *normalized* prototype. They say nothing
# about whether the denormalization into real henries and farads is correct.
# These tests close that gap by cascading the synthesized elements into an
# ABCD matrix and checking the resulting transfer function against the closed-
# form response the filter is supposed to have -- an independent statement of
# the same physics, so a sign error or a misplaced factor in the scaling shows
# up here even though every g-value is right.


def _branch_impedance(element, f_hz):
    """Impedance of one branch at `f_hz`, in ohms.

    A parallel LC is built from its admittance (1/jwL + jwC) rather than the
    product-over-sum form, which divides by zero at resonance. At resonance the
    branch really is an ideal open circuit, so the reciprocal below still
    raises -- callers evaluate just off centre rather than exactly on the
    singularity of a lossless ideal notch.
    """
    w = 2 * math.pi * f_hz
    zl = 1j * w * element.inductance_h if element.inductance_h else 0j
    zc = 1.0 / (1j * w * element.capacitance_f) if element.capacitance_f else 0j
    if element.topology == "L":
        return zl
    if element.topology == "C":
        return zc
    if element.topology == "LC_SERIES":
        return zl + zc
    return 1.0 / (1.0 / zl + 1.0 / zc)  # LC_PARALLEL


def _s21(network, f_hz):
    """|S21| of the synthesized ladder at `f_hz`, by ABCD cascade.

    Referenced to the source impedance at port 1 and to the network's OWN
    stated load impedance at port 2. That distinction is the whole point: an
    even-order Chebyshev is deliberately not terminated in its source
    impedance, so measuring it into R0 at both ends reports a filter that
    misses its ripple spec even when the synthesis is correct -- and, worse,
    hides a wrong load impedance when the synthesis is not.
    """
    abcd = [[1 + 0j, 0j], [0j, 1 + 0j]]
    for element in network.elements:
        z = _branch_impedance(element, f_hz)
        if element.position == "series":
            m = [[1 + 0j, z], [0j, 1 + 0j]]
        else:
            m = [[1 + 0j, 0j], [1.0 / z, 1 + 0j]]
        abcd = [
            [
                abcd[0][0] * m[0][0] + abcd[0][1] * m[1][0],
                abcd[0][0] * m[0][1] + abcd[0][1] * m[1][1],
            ],
            [
                abcd[1][0] * m[0][0] + abcd[1][1] * m[1][0],
                abcd[1][0] * m[0][1] + abcd[1][1] * m[1][1],
            ],
        ]
    rs = network.source_impedance_ohm
    rl = network.load_impedance_ohm
    a, b, c, d = abcd[0][0], abcd[0][1], abcd[1][0], abcd[1][1]
    # Generalized to unequal real reference impedances; reduces to the usual
    # 2 / (A + B/Z0 + C*Z0 + D) when rl == rs.
    return abs(2.0 * math.sqrt(rs * rl) / (a * rl + b + c * rs * rl + d * rs))


@pytest.mark.parametrize("order", [3, 5])
@pytest.mark.parametrize("first_element", ["shunt", "series"])
def test_butterworth_lowpass_matches_its_closed_form_response(order, first_element):
    """|S21|^2 = 1 / (1 + (w/wc)^2n) -- the definition of maximally flat."""
    fc = 1e9
    net = synthesize_filter(
        response="butterworth",
        band="lowpass",
        order=order,
        cutoff_hz=fc,
        first_element=first_element,
    )
    for ratio in (0.1, 0.5, 1.0, 2.0, 5.0):
        expected = math.sqrt(1.0 / (1.0 + ratio ** (2 * order)))
        assert _s21(net, ratio * fc) == pytest.approx(expected, rel=1e-9)


def test_butterworth_lowpass_is_3db_down_at_cutoff():
    """The textbook definition of the Butterworth cut-off frequency."""
    net = synthesize_filter(response="butterworth", band="lowpass", order=3, cutoff_hz=1e9)
    loss_db = -20 * math.log10(_s21(net, 1e9))
    assert loss_db == pytest.approx(3.0103, abs=1e-4)


@pytest.mark.parametrize("order", [3, 5])
def test_chebyshev_lowpass_ripple_stays_within_its_spec(order):
    """Across the pass band the loss oscillates between 0 and exactly the
    stated ripple -- never worse. Odd orders only: an even-order prototype
    ends on a deliberate mismatch, so it is not 50-ohm terminated."""
    ripple_db = 0.5
    fc = 1e9
    net = synthesize_filter(
        response="chebyshev",
        band="lowpass",
        order=order,
        ripple_db=ripple_db,
        cutoff_hz=fc,
    )
    losses = [-20 * math.log10(_s21(net, fc * i / 200.0)) for i in range(1, 201)]
    # Confined to [0, ripple] everywhere in the band -- the equal-ripple
    # guarantee. Sampling on a fixed grid cannot land exactly on the nulls, so
    # the floor is asserted as "gets close to 0 dB", not "is 0 dB".
    assert all(-1e-9 <= loss <= ripple_db + 1e-9 for loss in losses)
    assert min(losses) < 1e-3
    # At the cut-off an odd-order equal-ripple filter sits at full ripple.
    assert losses[-1] == pytest.approx(ripple_db, abs=1e-9)


def test_chebyshev_rolls_off_faster_than_butterworth_at_equal_order():
    """The trade the ripple buys: same component count, sharper skirt."""
    fc, order = 1e9, 5
    butter = synthesize_filter(response="butterworth", band="lowpass", order=order, cutoff_hz=fc)
    cheby = synthesize_filter(
        response="chebyshev", band="lowpass", order=order, ripple_db=0.5, cutoff_hz=fc
    )
    assert _s21(cheby, 2 * fc) < _s21(butter, 2 * fc)


def test_highpass_is_the_mirror_of_the_lowpass():
    """A high-pass at wc/w should equal the low-pass at w/wc."""
    fc = 1e9
    lp = synthesize_filter(response="butterworth", band="lowpass", order=3, cutoff_hz=fc)
    hp = synthesize_filter(response="butterworth", band="highpass", order=3, cutoff_hz=fc)
    for ratio in (0.25, 0.5, 2.0, 4.0):
        assert _s21(hp, fc / ratio) == pytest.approx(_s21(lp, ratio * fc), rel=1e-9)


def test_bandpass_passes_the_centre_and_rejects_both_skirts():
    f0, bw = 2.4e9, 0.24e9
    net = synthesize_filter(
        response="butterworth",
        band="bandpass",
        order=3,
        center_hz=f0,
        bandwidth_hz=bw,
    )
    assert _s21(net, f0) == pytest.approx(1.0, abs=1e-9)
    # 3 dB down at both band edges. Note the edges are spaced *geometrically*
    # about f0, not arithmetically: the transformation defines f0 as sqrt(f1 f2),
    # so the edges are not f0 +/- bw/2. The width between them is still exactly
    # bw. Solving (1/delta)(w/w0 - w0/w) = +/-1 gives the factors below.
    delta = bw / f0
    upper = f0 * (delta + math.sqrt(delta**2 + 4)) / 2
    lower = f0 * (-delta + math.sqrt(delta**2 + 4)) / 2
    assert upper - lower == pytest.approx(bw)
    assert math.sqrt(upper * lower) == pytest.approx(f0)
    for edge in (lower, upper):
        assert -20 * math.log10(_s21(net, edge)) == pytest.approx(3.0103, abs=1e-3)
    assert _s21(net, f0 / 4) < 1e-3
    assert _s21(net, f0 * 4) < 1e-3


def test_bandstop_rejects_the_centre_and_passes_both_skirts():
    f0, bw = 2.4e9, 0.5e9
    net = synthesize_filter(
        response="butterworth",
        band="bandstop",
        order=3,
        center_hz=f0,
        bandwidth_hz=bw,
    )
    # Exactly at f0 an ideal lossless band-stop is an infinitely deep notch --
    # a genuine singularity, not a number to assert. Check just off centre.
    assert _s21(net, f0 * 1.0001) < 1e-3
    assert _s21(net, f0 * 0.9999) < 1e-3
    assert _s21(net, f0 / 8) == pytest.approx(1.0, abs=1e-3)
    assert _s21(net, f0 * 8) == pytest.approx(1.0, abs=1e-3)


@pytest.mark.parametrize("order", [2, 4])
@pytest.mark.parametrize("ripple_db", [0.5, 3.0])
@pytest.mark.parametrize("first_element", ["shunt", "series"])
def test_even_order_chebyshev_meets_its_ripple_spec_into_its_stated_load(
    order, ripple_db, first_element
):
    """The test that catches a wrong load impedance.

    An even-order equal-ripple filter is only 0-to-ripple dB flat when it is
    terminated in the load its own prototype calls for. Every earlier
    end-to-end check used an odd order, where g_(N+1) is exactly 1 and the
    load equals the source -- which makes a wrong load-impedance formula
    completely invisible. This one exercises both ladder orientations at even
    order, where g_(N+1) is 5.81 at 3 dB and the direction actually matters.

    Terminating the shunt-first order-2 3 dB design at 290 ohms instead of
    8.6 ohms runs 3-12 dB of passband loss against a 0-3 dB spec.
    """
    fc = 1e9
    net = synthesize_filter(
        response="chebyshev",
        band="lowpass",
        order=order,
        ripple_db=ripple_db,
        cutoff_hz=fc,
        first_element=first_element,
    )
    losses = [-20 * math.log10(_s21(net, fc * i / 200.0)) for i in range(1, 201)]
    assert all(-1e-6 <= loss <= ripple_db + 1e-6 for loss in losses), (
        f"passband loss {min(losses):.3f}..{max(losses):.3f} dB is outside the "
        f"0..{ripple_db} dB spec, into load {net.load_impedance_ohm:.3f} ohm"
    )
    assert min(losses) < 1e-3
    assert max(losses) == pytest.approx(ripple_db, abs=1e-6)


def test_the_wrong_load_impedance_would_be_caught():
    """Guards the guard: confirm the check above actually fails on the bug it
    was written for, rather than passing for an unrelated reason."""
    import dataclasses

    net = synthesize_filter(
        response="chebyshev", band="lowpass", order=2, ripple_db=3.0, cutoff_hz=1e9
    )
    wrong = dataclasses.replace(net, load_impedance_ohm=net.source_impedance_ohm * net.g_values[-1])
    losses = [-20 * math.log10(_s21(wrong, 1e9 * i / 200.0)) for i in range(1, 201)]
    assert max(losses) > 3.0 + 1e-6


# --- Physical realization: stepped-impedance ("Hi-Z, Lo-Z") microstrip (issue #286) ---
#
# The reference bl (electrical length) values below are NOT regenerated from
# this implementation -- they are hand-copied from two independently
# published worked examples of this exact procedure (Bostic & Dittman,
# "Designing Microstrip ISM Low-pass Filter"; Le/Nguyen/Truong, "Stepped-
# impedance Lowpass Filter", both reproducing Pozar's own bl = g*R0/Zh
# (series) / g*Zl/R0 (shunt) formulas), the same "checked against a
# published table, not against this implementation" discipline the g-value
# tests at the top of this file already use.
#
# Bostic & Dittman's N=5 Butterworth example uses g = 0.6180, 1.6180,
# 2.0000, 1.6180, 0.6180 -- exactly BUTTERWORTH_TABLE[5] above -- with
# R0=50, z_high_ohm=100, z_low_ohm=20, giving bl = 0.2472, 0.809 (their
# rounded 0.805; 1.6180*50/100 = 0.809 exactly), 0.8, 0.809, 0.2472 rad.

_EPS_R, _H_M = 4.4, 0.0016  # an arbitrary but fixed FR4-like substrate


def test_stepped_impedance_electrical_lengths_match_a_published_worked_example():
    net = synthesize_filter(response="butterworth", band="lowpass", order=5, cutoff_hz=1e9)
    sections = realize_lowpass_stepped_impedance_microstrip(
        net, eps_r=_EPS_R, h_m=_H_M, z_high_ohm=100.0, z_low_ohm=20.0
    )
    expected_bl = [0.2472, 0.809, 0.8, 0.809, 0.2472]
    assert [s.electrical_length_rad for s in sections] == pytest.approx(expected_bl, abs=1e-3)


def test_stepped_impedance_electrical_length_is_independent_of_cutoff_frequency():
    """bl = wc*L/Zh (series) or wc*C*Zl (shunt); L and C themselves scale as
    1/wc (see _lowpass_element), so wc cancels algebraically and a section's
    electrical length depends only on its g-value, Zh/Zl and R0 -- not on
    which cutoff frequency was used to denormalize the ladder."""
    net_1ghz = synthesize_filter(response="butterworth", band="lowpass", order=3, cutoff_hz=1e9)
    net_5ghz = synthesize_filter(response="butterworth", band="lowpass", order=3, cutoff_hz=5e9)
    sections_1ghz = realize_lowpass_stepped_impedance_microstrip(net_1ghz, eps_r=_EPS_R, h_m=_H_M)
    sections_5ghz = realize_lowpass_stepped_impedance_microstrip(net_5ghz, eps_r=_EPS_R, h_m=_H_M)
    assert [s.electrical_length_rad for s in sections_1ghz] == pytest.approx(
        [s.electrical_length_rad for s in sections_5ghz]
    )
    # Physical length, unlike electrical length, DOES depend on cutoff: the
    # same electrical length is a shorter physical line at a higher frequency.
    for lo, hi in zip(sections_1ghz, sections_5ghz, strict=True):
        assert hi.length_m == pytest.approx(lo.length_m / 5.0)


def test_stepped_impedance_topology_matches_the_ladder_and_uses_the_right_impedance():
    """Every 'L' branch (series inductor) becomes a z_high_ohm line; every
    'C' branch (shunt capacitor) becomes a z_low_ohm line -- matching the
    method's own physical reasoning (narrow line ~ inductive, wide line ~
    capacitive), not just the ladder's series/shunt position."""
    net = synthesize_filter(response="butterworth", band="lowpass", order=3, cutoff_hz=2.4e9)
    sections = realize_lowpass_stepped_impedance_microstrip(
        net, eps_r=_EPS_R, h_m=_H_M, z_high_ohm=90.0, z_low_ohm=15.0
    )
    assert [(s.position, s.topology) for s in sections] == [
        ("shunt", "C"),
        ("series", "L"),
        ("shunt", "C"),
    ]
    for s in sections:
        expected_z0 = 90.0 if s.topology == "L" else 15.0
        assert s.characteristic_impedance_ohm == expected_z0
        assert s.width_m > 0
        assert s.length_m > 0
        assert 1.0 < s.effective_permittivity < _EPS_R


def test_stepped_impedance_length_matches_an_independent_hand_calculation():
    """Recomputes one section's physical length from the underlying physics
    (bl / beta, beta = wc*sqrt(eps_eff)/c) using the already-independently-
    tested microstrip primitives directly, rather than re-deriving from
    this function's own internals."""
    fc = 1e9
    net = synthesize_filter(response="butterworth", band="lowpass", order=3, cutoff_hz=fc)
    sections = realize_lowpass_stepped_impedance_microstrip(
        net, eps_r=_EPS_R, h_m=_H_M, z_high_ohm=100.0, z_low_ohm=20.0
    )
    series_element = net.elements[1]
    assert series_element.topology == "L"
    omega_c = 2 * math.pi * fc
    beta_l = omega_c * series_element.inductance_h / 100.0
    width_m = microstrip_synthesize_width_m(100.0, _EPS_R, _H_M)
    eps_eff = microstrip_effective_permittivity(_EPS_R, width_m, _H_M)
    beta = omega_c * eps_eff**0.5 / 299_792_458.0
    expected_length_m = beta_l / beta
    assert sections[1].length_m == pytest.approx(expected_length_m)
    assert sections[1].width_m == pytest.approx(width_m)


@pytest.mark.parametrize(
    ("band", "kwargs"),
    [
        ("highpass", {"cutoff_hz": 1e9}),
        ("bandpass", {"center_hz": 2.4e9, "bandwidth_hz": 0.24e9}),
        ("bandstop", {"center_hz": 2.4e9, "bandwidth_hz": 0.24e9}),
    ],
)
def test_stepped_impedance_rejects_non_lowpass_bands(band, kwargs):
    net = synthesize_filter(response="butterworth", band=band, order=3, **kwargs)
    with pytest.raises(ValueError, match="lowpass"):
        realize_lowpass_stepped_impedance_microstrip(net, eps_r=_EPS_R, h_m=_H_M)


def test_stepped_impedance_requires_z_high_above_z_low():
    net = synthesize_filter(response="butterworth", band="lowpass", order=3, cutoff_hz=1e9)
    with pytest.raises(ValueError, match="z_high_ohm"):
        realize_lowpass_stepped_impedance_microstrip(
            net, eps_r=_EPS_R, h_m=_H_M, z_high_ohm=20.0, z_low_ohm=20.0
        )
    with pytest.raises(ValueError, match="z_high_ohm"):
        realize_lowpass_stepped_impedance_microstrip(
            net, eps_r=_EPS_R, h_m=_H_M, z_high_ohm=10.0, z_low_ohm=20.0
        )


def test_stepped_impedance_invalid_substrate_inputs_raise():
    net = synthesize_filter(response="butterworth", band="lowpass", order=3, cutoff_hz=1e9)
    with pytest.raises(ValueError):
        realize_lowpass_stepped_impedance_microstrip(net, eps_r=1.0, h_m=_H_M)
    with pytest.raises(ValueError):
        realize_lowpass_stepped_impedance_microstrip(net, eps_r=_EPS_R, h_m=0.0)
