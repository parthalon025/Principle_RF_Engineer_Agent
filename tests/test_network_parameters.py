import numpy as np
import pytest

from rf_tools.network_parameters import (
    abcd_to_s,
    input_stability_circle,
    output_stability_circle,
    reflection_coefficient_from_impedance,
    return_loss_db,
    rollett_k_factor,
    s_to_abcd,
    s_to_y,
    s_to_z,
    stability_verdict,
    two_port_stability_delta,
    vswr_from_gamma,
    y_to_s,
    z_to_s,
)


def test_vswr():
    assert vswr_from_gamma(1 / 3) == pytest.approx(2.0)


def test_return_loss():
    assert return_loss_db(0.1) == pytest.approx(20.0)


def test_invalid_gamma():
    with pytest.raises(ValueError):
        vswr_from_gamma(1.0)


# --- Reflection coefficient from feed-point impedance (issue #101) ---
#
# Gamma = (Z_load - Z0) / (Z_load + Z0) -- the standard transmission-line
# result (Pozar, "Microwave Engineering"), the missing link between a
# SIMULATION step's feed-point impedance and vswr_from_gamma/return_loss_db
# above, both of which take |Gamma| directly, not an impedance.


def test_reflection_coefficient_of_a_matched_load_is_zero():
    # Z_load == Z0: no reflection at all.
    assert reflection_coefficient_from_impedance(50.0, z0=50.0) == pytest.approx(0.0)


def test_reflection_coefficient_of_a_short_circuit_is_minus_one():
    assert reflection_coefficient_from_impedance(0.0, z0=50.0) == pytest.approx(-1.0)


def test_reflection_coefficient_of_a_known_complex_impedance():
    # The same feed-point impedance tests/test_design_loop.py's/tests/
    # test_nec2pp.py's own NEC-2 User's Guide "Example 1" sample output
    # parses to (82.6979 + j46.3060 ohms), referenced to 50 ohms --
    # independently computed via (Z-Z0)/(Z+Z0).
    gamma = reflection_coefficient_from_impedance(complex(82.6979, 46.3060), z0=50.0)
    assert abs(gamma) == pytest.approx(0.40333507086482756)


def test_reflection_coefficient_composes_with_vswr_and_return_loss():
    gamma = reflection_coefficient_from_impedance(complex(82.6979, 46.3060), z0=50.0)
    gamma_mag = abs(gamma)
    assert vswr_from_gamma(gamma_mag) == pytest.approx(2.35196506839923)
    assert return_loss_db(gamma_mag) == pytest.approx(7.8866802699461624)


def test_reflection_coefficient_rejects_a_non_positive_reference_impedance():
    with pytest.raises(ValueError):
        reflection_coefficient_from_impedance(50.0, z0=0.0)
    with pytest.raises(ValueError):
        reflection_coefficient_from_impedance(50.0, z0=-50.0)


def test_reflection_coefficient_undefined_when_load_cancels_reference():
    # Z_load + Z0 = 0 (a negative-resistance load equal in magnitude to
    # Z0) makes the formula's denominator zero -- genuinely undefined, not
    # a value to silently guess at.
    with pytest.raises(ValueError):
        reflection_coefficient_from_impedance(complex(-50.0, 0.0), z0=50.0)


# --- Network parameter conversions (S/Z/Y/ABCD) ---
#
# Reference values below come from two independent, well-known special cases:
#
# 1. A fully matched, isolated two-port (S = 0): the algebraic identities
#    Z = z0*(I+S)(I-S)^-1 and Y = (1/z0)*(I-S)(I+S)^-1 collapse to Z = z0*I
#    and Y = (1/z0)*I regardless of any physical network, and this same
#    matrix (S=0) is a textbook example of a network with no ABCD
#    representation (S21 = 0, so the S->ABCD formula divides by zero).
#
# 2. An ideal matched thru line (S = [[0,1],[1,0]]): its ABCD matrix is the
#    identity (a textbook result), while its Z- and Y-matrices are formally
#    undefined (both (I-S) and (I+S) are singular for this S) -- a genuine
#    physical example of a singular conversion, not a contrived one.
#
# 3. A matched resistive attenuator ("pad"), built two ways that must agree:
#    - S-parameter form: S11 = S22 = 0, S21 = S12 = 10**(-L_dB/20)
#      (textbook matched-pad result).
#    - T-network resistor form: series R1, shunt R2, series R1, with
#      R1 = z0*(K-1)/(K+1), R2 = z0*2K/(K**2-1), K = 10**(L_dB/20)
#      (textbook T-attenuator design equations). Its Z-parameters are the
#      classic T-network result Z11=Z22=R1+R2, Z12=Z21=R2, and its ABCD
#      matrix is the cascade of series/shunt ABCD elements. Y is checked
#      against the general two-port identity Y = Z^-1.
#    These are independent derivations (S-domain textbook formula vs.
#    resistor-network circuit theory) that our conversion functions must
#    reconcile.


def test_s_to_z_matched_network():
    s = [[0, 0], [0, 0]]
    z = s_to_z(s, z0=50.0)
    assert z == pytest.approx(np.diag([50.0, 50.0]))


def test_s_to_y_matched_network():
    s = [[0, 0], [0, 0]]
    y = s_to_y(s, z0=50.0)
    assert y == pytest.approx(np.diag([0.02, 0.02]))


def test_s_to_abcd_zero_s21_raises():
    s = [[0, 0], [0, 0]]
    with pytest.raises(ValueError):
        s_to_abcd(s)


def test_s_to_abcd_matched_thru_is_identity():
    s = [[0, 1], [1, 0]]
    abcd = s_to_abcd(s, z0=50.0)
    assert abcd == pytest.approx(np.eye(2))


def test_abcd_to_s_identity_is_matched_thru():
    s = abcd_to_s(np.eye(2), z0=50.0)
    assert s == pytest.approx(np.array([[0, 1], [1, 0]]))


def test_s_to_z_singular_thru_line_raises():
    with pytest.raises(ValueError):
        s_to_z([[0, 1], [1, 0]])


def test_s_to_y_singular_thru_line_raises():
    with pytest.raises(ValueError):
        s_to_y([[0, 1], [1, 0]])


def _matched_t_attenuator_z(z0: float, l_db: float) -> np.ndarray:
    k = 10 ** (l_db / 20)
    r1 = z0 * (k - 1) / (k + 1)
    r2 = z0 * 2 * k / (k**2 - 1)
    return np.array([[r1 + r2, r2], [r2, r1 + r2]])


def _matched_t_attenuator_abcd(z0: float, l_db: float) -> np.ndarray:
    k = 10 ** (l_db / 20)
    r1 = z0 * (k - 1) / (k + 1)
    r2 = z0 * 2 * k / (k**2 - 1)
    m_series = np.array([[1.0, r1], [0.0, 1.0]])
    m_shunt = np.array([[1.0, 0.0], [1.0 / r2, 1.0]])
    return m_series @ m_shunt @ m_series


def test_z_to_s_matched_attenuator_matches_textbook_s():
    z0 = 50.0
    l_db = 6.0
    z_t = _matched_t_attenuator_z(z0, l_db)

    s = z_to_s(z_t, z0=z0)

    s_expected_mag = 10 ** (-l_db / 20)
    assert s[0, 0] == pytest.approx(0.0, abs=1e-9)
    assert s[1, 1] == pytest.approx(0.0, abs=1e-9)
    assert s[1, 0] == pytest.approx(s_expected_mag, abs=1e-9)
    assert s[0, 1] == pytest.approx(s_expected_mag, abs=1e-9)


def test_s_to_z_matched_attenuator_matches_t_network():
    z0 = 50.0
    l_db = 6.0
    z_expected = _matched_t_attenuator_z(z0, l_db)
    s_pad = 10 ** (-l_db / 20)

    z = s_to_z([[0, s_pad], [s_pad, 0]], z0=z0)

    assert z == pytest.approx(z_expected, abs=1e-9)


def test_s_to_y_matched_attenuator_matches_z_inverse():
    z0 = 50.0
    l_db = 6.0
    z_expected = _matched_t_attenuator_z(z0, l_db)
    y_expected = np.linalg.inv(z_expected)
    s_pad = 10 ** (-l_db / 20)

    y = s_to_y([[0, s_pad], [s_pad, 0]], z0=z0)

    assert y == pytest.approx(y_expected, abs=1e-9)


def test_s_to_abcd_matched_attenuator_matches_cascaded_t_network():
    z0 = 50.0
    l_db = 6.0
    abcd_expected = _matched_t_attenuator_abcd(z0, l_db)
    s_pad = 10 ** (-l_db / 20)

    abcd = s_to_abcd([[0, s_pad], [s_pad, 0]], z0=z0)

    assert abcd == pytest.approx(abcd_expected, abs=1e-9)


_GENERIC_S = [[0.1 + 0.05j, 0.02 - 0.01j], [0.6 + 0.1j, 0.15 - 0.1j]]


def test_round_trip_s_z_s():
    z = s_to_z(_GENERIC_S, z0=50.0)
    s_back = z_to_s(z, z0=50.0)
    assert s_back == pytest.approx(np.array(_GENERIC_S), abs=1e-9)


def test_round_trip_s_y_s():
    y = s_to_y(_GENERIC_S, z0=50.0)
    s_back = y_to_s(y, z0=50.0)
    assert s_back == pytest.approx(np.array(_GENERIC_S), abs=1e-9)


def test_round_trip_s_abcd_s():
    abcd = s_to_abcd(_GENERIC_S, z0=50.0)
    s_back = abcd_to_s(abcd, z0=50.0)
    assert s_back == pytest.approx(np.array(_GENERIC_S), abs=1e-9)


def test_generic_conversions_match_scikit_rf():
    """Cross-check against a trusted third-party implementation (per ticket #24)."""
    skrf = pytest.importorskip("skrf")
    z0 = 50.0
    freq = skrf.Frequency(1, 1, 1, unit="ghz")
    net = skrf.Network(frequency=freq, s=np.array([_GENERIC_S]), z0=z0)

    assert s_to_z(_GENERIC_S, z0=z0) == pytest.approx(net.z[0], abs=1e-9)
    assert s_to_y(_GENERIC_S, z0=z0) == pytest.approx(net.y[0], abs=1e-9)
    assert s_to_abcd(_GENERIC_S, z0=z0) == pytest.approx(net.a[0], abs=1e-9)


def test_s_to_z_non_square_raises():
    with pytest.raises(ValueError):
        s_to_z([[0, 1, 2], [1, 0, 3]])


def test_s_to_z_non_2x2_square_raises():
    with pytest.raises(ValueError):
        s_to_z(np.eye(3))


def test_s_to_abcd_non_square_raises():
    with pytest.raises(ValueError):
        s_to_abcd([[0, 1, 2], [1, 0, 3]])


def test_invalid_z0_raises():
    with pytest.raises(ValueError):
        s_to_z([[0, 0], [0, 0]], z0=-50.0)
    with pytest.raises(ValueError):
        s_to_z([[0, 0], [0, 0]], z0=0.0)


# --- Stability (Rollett K-factor and stability circles) ---
#
# rollett_k_factor / two_port_stability_delta / stability_verdict use the
# standard Rollett criterion (K = (1-|S11|^2-|S22|^2+|Delta|^2)/(2|S12*S21|),
# Delta = S11*S22-S12*S21, unconditional stability iff K>1 AND |Delta|<1;
# Pozar, "Microwave Engineering"). Reference values below are computed
# independently in each test from that same definitional formula (the
# established pattern in this module -- see test_cascade_output_ip3_two_stage),
# using S-parameter sets chosen to hit each branch of the verdict:
#
# - S=[[0,0.5],[0.5,0]]: a matched, reciprocal, purely-resistive-coupling
#   network -- the textbook case of a network with no possible gain
#   mechanism, whose K and Delta are simple enough to also hand-verify
#   (K=(1+0.5^4)/(2*0.25)=2.125, Delta=-0.25).
# - S11=0.3, S22=0.4, S12=0.05, S21=2.0: a generic gain-stage-shaped
#   S-matrix (small input/output reflection, high forward gain, low
#   reverse isolation) used for both K and the stability-circle checks,
#   cross-validated against scikit-rf's independent stability/
#   stability_circle implementation.
# - S11=S22=0.5, S12=S21=1: |Delta|<1 but K<1 -- exercises the
#   "potentially unstable" branch on the K condition alone.
# - S11=S22=0, S12=S21=2: K>1 but |Delta|>=1 -- exercises the
#   "potentially unstable" branch on the Delta condition alone, proving
#   the verdict checks both conditions and not just K.


def test_rollett_k_factor_and_delta_matched_reciprocal_network():
    s = [[0, 0.5], [0.5, 0]]
    assert two_port_stability_delta(s) == pytest.approx(-0.25)
    assert rollett_k_factor(s) == pytest.approx(2.125)
    assert stability_verdict(s) == "unconditionally stable"


def test_rollett_k_factor_unconditionally_stable_generic():
    s11, s12, s21, s22 = 0.3, 0.05, 2.0, 0.4
    s = [[s11, s12], [s21, s22]]
    delta = s11 * s22 - s12 * s21
    denom = 2 * abs(s12 * s21)
    expected_k = (1 - abs(s11) ** 2 - abs(s22) ** 2 + abs(delta) ** 2) / denom

    assert two_port_stability_delta(s) == pytest.approx(delta)
    assert rollett_k_factor(s) == pytest.approx(expected_k)
    assert stability_verdict(s) == "unconditionally stable"


def test_stability_verdict_potentially_unstable_low_k():
    # |Delta| = 0.75 < 1, but K = 0.53125 < 1: fails the K condition alone.
    s = [[0.5, 1.0], [1.0, 0.5]]
    assert rollett_k_factor(s) == pytest.approx(0.53125)
    assert abs(two_port_stability_delta(s)) < 1
    assert stability_verdict(s) == "potentially unstable"


def test_stability_verdict_potentially_unstable_high_delta():
    # K = 2.125 > 1, but |Delta| = 4 >= 1: fails the Delta condition alone,
    # proving the verdict is not just "K > 1".
    s = [[0, 2.0], [2.0, 0]]
    assert rollett_k_factor(s) > 1
    assert abs(two_port_stability_delta(s)) == pytest.approx(4.0)
    assert stability_verdict(s) == "potentially unstable"


def test_rollett_k_factor_zero_coupling_raises():
    with pytest.raises(ValueError):
        rollett_k_factor([[0.5, 0], [0.9, 0.5]])


def test_stability_circles_generic_hand_and_scikit_rf():
    s11, s12, s21, s22 = 0.3, 0.05, 2.0, 0.4
    s = [[s11, s12], [s21, s22]]
    delta = s11 * s22 - s12 * s21

    denom_out = abs(s22) ** 2 - abs(delta) ** 2
    expected_center_out = complex(s22 - delta * s11).conjugate() / denom_out
    expected_radius_out = abs(s12 * s21) / abs(denom_out)

    denom_in = abs(s11) ** 2 - abs(delta) ** 2
    expected_center_in = complex(s11 - delta * s22).conjugate() / denom_in
    expected_radius_in = abs(s12 * s21) / abs(denom_in)

    center_out, radius_out = output_stability_circle(s)
    center_in, radius_in = input_stability_circle(s)

    assert center_out == pytest.approx(expected_center_out)
    assert radius_out == pytest.approx(expected_radius_out)
    assert center_in == pytest.approx(expected_center_in)
    assert radius_in == pytest.approx(expected_radius_in)

    skrf = pytest.importorskip("skrf")
    freq = skrf.Frequency(1, 1, 1, unit="ghz")
    net = skrf.Network(frequency=freq, s=np.array([s], dtype=complex), z0=50.0)

    assert rollett_k_factor(s) == pytest.approx(net.stability[0])

    loci_out = net.stability_circle(target_port=1)[:, 0]
    assert np.abs(loci_out - center_out) == pytest.approx(radius_out, abs=0.01)

    loci_in = net.stability_circle(target_port=0)[:, 0]
    assert np.abs(loci_in - center_in) == pytest.approx(radius_in, abs=0.01)


def test_output_stability_circle_singular_raises():
    # |S22|^2 == |Delta|^2 with S22=S12=S21=0: denominator is exactly zero.
    with pytest.raises(ValueError):
        output_stability_circle([[0.5, 0], [0, 0]])


def test_input_stability_circle_singular_raises():
    with pytest.raises(ValueError):
        input_stability_circle([[0, 0], [0, 0.5]])
