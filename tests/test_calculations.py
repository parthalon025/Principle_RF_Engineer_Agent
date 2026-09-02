import numpy as np
import pytest

from rf_tools.calculations import (
    abcd_to_s,
    cascade_gain_db,
    cascade_output_ip3_linear,
    db_to_linear,
    free_space_path_loss_db,
    friis_noise_factor,
    iip3_from_oip3_db,
    input_stability_circle,
    l_network_match,
    link_budget_margin_db,
    oip3_from_iip3_db,
    output_stability_circle,
    quarter_wave_transformer_impedance,
    return_loss_db,
    rollett_k_factor,
    s_to_abcd,
    s_to_y,
    s_to_z,
    stability_verdict,
    third_order_intermod_dbc,
    third_order_intermod_output_dbm,
    two_port_stability_delta,
    vswr_from_gamma,
    wavelength,
    y_to_s,
    z_to_s,
)


def test_wavelength():
    assert wavelength(299_792_458.0) == pytest.approx(1.0)


def test_vswr():
    assert vswr_from_gamma(1 / 3) == pytest.approx(2.0)


def test_return_loss():
    assert return_loss_db(0.1) == pytest.approx(20.0)


def test_friis():
    f1 = 10 ** (2 / 10)
    f2 = 10 ** (3 / 10)
    g1 = 10 ** (10 / 10)
    result = friis_noise_factor([f1, f2], [g1, 10.0])
    expected = f1 + (f2 - 1) / g1
    assert result == pytest.approx(expected)


def test_gain():
    assert cascade_gain_db([10, -3, 20]) == pytest.approx(27)


def test_invalid_gamma():
    with pytest.raises(ValueError):
        vswr_from_gamma(1.0)


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


# --- Link budget ---
#
# free_space_path_loss_db uses the standard ITU-R P.525 / textbook
# FSPL(dB) = 20*log10(d_km) + 20*log10(f_MHz) + 32.44 formula. d=1 km,
# f=1000 MHz is chosen because log10(1)=0 and log10(1000)=3 exactly, so the
# expected value (92.44 dB) can be hand-verified with no rounding.
#
# link_budget_margin_db is checked against the same standard dB-domain
# link-budget identity (EIRP - path loss + Rx gain - other losses - Rx
# sensitivity), both with hand-picked round numbers and with FSPL plugged
# in as the path-loss term, following this module's existing convention
# (see test_friis) of asserting against the definitional formula evaluated
# independently in the test.


def test_free_space_path_loss_round_numbers():
    assert free_space_path_loss_db(1.0, 1000.0) == pytest.approx(92.44)


def test_free_space_path_loss_invalid_inputs():
    with pytest.raises(ValueError):
        free_space_path_loss_db(0.0, 1000.0)
    with pytest.raises(ValueError):
        free_space_path_loss_db(-1.0, 1000.0)
    with pytest.raises(ValueError):
        free_space_path_loss_db(1.0, 0.0)
    with pytest.raises(ValueError):
        free_space_path_loss_db(1.0, -1000.0)


def test_link_budget_margin_round_numbers():
    margin = link_budget_margin_db(
        tx_power_dbm=30.0,
        tx_antenna_gain_db=10.0,
        path_loss_db=100.0,
        rx_antenna_gain_db=5.0,
        rx_sensitivity_dbm=-90.0,
        other_losses_db=2.0,
    )
    # EIRP = 40 dBm; Rx power = 40 - 100 + 5 - 2 = -57 dBm; margin = -57 - (-90) = 33 dB.
    assert margin == pytest.approx(33.0)


def test_link_budget_margin_zero_other_losses_default():
    margin = link_budget_margin_db(
        tx_power_dbm=30.0,
        tx_antenna_gain_db=10.0,
        path_loss_db=100.0,
        rx_antenna_gain_db=5.0,
        rx_sensitivity_dbm=-90.0,
    )
    assert margin == pytest.approx(35.0)


def test_link_budget_margin_with_free_space_path_loss():
    fspl = free_space_path_loss_db(1.0, 1000.0)
    margin = link_budget_margin_db(
        tx_power_dbm=30.0,
        tx_antenna_gain_db=10.0,
        path_loss_db=fspl,
        rx_antenna_gain_db=5.0,
        rx_sensitivity_dbm=-90.0,
    )
    expected = (30.0 + 10.0) - fspl + 5.0 - 0.0 - (-90.0)
    assert margin == pytest.approx(expected)


def test_link_budget_margin_invalid_path_loss_raises():
    with pytest.raises(ValueError):
        link_budget_margin_db(30.0, 10.0, -5.0, 5.0, -90.0)


def test_link_budget_margin_invalid_other_losses_raises():
    with pytest.raises(ValueError):
        link_budget_margin_db(30.0, 10.0, 100.0, 5.0, -90.0, other_losses_db=-1.0)


# --- Third-order intercept (IP3) and intermodulation distortion (IMD) ---
#
# cascade_output_ip3_linear mirrors friis_noise_factor's cascading pattern
# (see module docstring for the formula and the reasoning). The reference
# values below are computed independently in the test from the same
# standard formula, using round dB/dBm inputs (10 dB / 30 dBm and
# 20 dB / 40 dBm) so the linear conversions and expected result can be
# hand-verified.
#
# third_order_intermod_output_dbm / third_order_intermod_dbc use the
# standard two-tone P_IM3(dBm) = 3*Pout(dBm) - 2*OIP3(dBm) relation (e.g.
# Pozar, Microwave Engineering), cross-checked against its defining
# property: at Pout = OIP3, P_IM3 must equal Pout.


def test_cascade_output_ip3_two_stage():
    g1_db, oip3_1_dbm = 10.0, 30.0
    g2_db, oip3_2_dbm = 20.0, 40.0
    g1 = db_to_linear(g1_db)
    g2 = db_to_linear(g2_db)
    oip3_1 = db_to_linear(oip3_1_dbm)  # mW, since dBm is dB relative to 1 mW
    oip3_2 = db_to_linear(oip3_2_dbm)

    result = cascade_output_ip3_linear([oip3_1, oip3_2], [g1, g2])

    expected_inv = 1 / oip3_2 + g2 / oip3_1
    expected = 1 / expected_inv
    assert result == pytest.approx(expected)
    # The gain-heavy second stage amplifies the first stage's IM products,
    # so the cascade OIP3 should sit well below either individual stage's
    # own OIP3.
    assert result < oip3_1
    assert result < oip3_2


def test_cascade_output_ip3_single_stage_is_unchanged():
    oip3 = db_to_linear(30.0)
    assert cascade_output_ip3_linear([oip3], [db_to_linear(10.0)]) == pytest.approx(oip3)


def test_cascade_output_ip3_mismatched_lengths_raises():
    with pytest.raises(ValueError):
        cascade_output_ip3_linear([1.0, 2.0], [1.0])


def test_cascade_output_ip3_empty_raises():
    with pytest.raises(ValueError):
        cascade_output_ip3_linear([], [])


def test_cascade_output_ip3_nonpositive_oip3_raises():
    with pytest.raises(ValueError):
        cascade_output_ip3_linear([1.0, -2.0], [1.0, 1.0])


def test_cascade_output_ip3_nonpositive_gain_raises():
    with pytest.raises(ValueError):
        cascade_output_ip3_linear([1.0, 2.0], [1.0, 0.0])


def test_oip3_iip3_round_trip():
    assert oip3_from_iip3_db(20.0, 10.0) == pytest.approx(30.0)
    assert iip3_from_oip3_db(30.0, 10.0) == pytest.approx(20.0)


def test_third_order_intermod_output_dbm():
    result = third_order_intermod_output_dbm(pout_dbm=0.0, oip3_dbm=30.0)
    assert result == pytest.approx(3 * 0.0 - 2 * 30.0)


def test_third_order_intermod_output_dbm_at_intercept_equals_pout():
    # Defining property of the extrapolated intercept: as Pout -> OIP3,
    # P_IM3 -> Pout. Check just below the (excluded) boundary.
    pout, oip3 = 29.999, 30.0
    assert third_order_intermod_output_dbm(pout, oip3) == pytest.approx(pout, abs=1e-2)


def test_third_order_intermod_dbc_matches_output_dbm_difference():
    pout, oip3 = 10.0, 30.0
    im3_dbm = third_order_intermod_output_dbm(pout, oip3)
    im3_dbc = third_order_intermod_dbc(pout, oip3)
    assert im3_dbc == pytest.approx(pout - im3_dbm)
    assert im3_dbc == pytest.approx(2 * (oip3 - pout))


def test_third_order_intermod_at_or_above_intercept_raises():
    with pytest.raises(ValueError):
        third_order_intermod_output_dbm(30.0, 30.0)
    with pytest.raises(ValueError):
        third_order_intermod_dbc(35.0, 30.0)


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


# --- Impedance matching ---
#
# quarter_wave_transformer_impedance uses the standard real-impedance
# quarter-wave transformer formula Z_t = sqrt(Z_source*Z_load) (Pozar).
#
# l_network_match uses the standard Pozar sec. 5.1 two-solution L-network
# synthesis. Rather than re-deriving its closed-form output values, each
# test case below independently verifies the *physical claim* the function
# makes: that assembling the returned (X, B) pair into the L-network
# topology its own docstring specifies (shunt-then-series for
# Re(z_load) >= z_source, series-then-shunt otherwise) reduces the network's
# input impedance to exactly z_source -- i.e. impedance-combination algebra
# independent of the closed-form formula used to derive X and B. The two
# all-real cases below (Z0=50, Zl=100 and Z0=50, Zl=25) were additionally
# hand-verified against that same reconstruction offline with exact
# fractions, so the expected (X, B) literals are known-good, not just
# self-consistent.


def _reconstruct_shunt_at_load_then_series(z_load: complex, x: float, b: float) -> complex:
    y_shunt = 1 / z_load + 1j * b
    z_after_shunt = 1 / y_shunt
    return z_after_shunt + 1j * x


def _reconstruct_series_at_load_then_shunt(z_load: complex, x: float, b: float) -> complex:
    z_after_series = z_load + 1j * x
    y_total = 1 / z_after_series + 1j * b
    return 1 / y_total


def test_quarter_wave_transformer_round_numbers():
    assert quarter_wave_transformer_impedance(50.0, 200.0) == pytest.approx(100.0)


def test_quarter_wave_transformer_invalid_inputs_raise():
    with pytest.raises(ValueError):
        quarter_wave_transformer_impedance(0.0, 200.0)
    with pytest.raises(ValueError):
        quarter_wave_transformer_impedance(-50.0, 200.0)
    with pytest.raises(ValueError):
        quarter_wave_transformer_impedance(50.0, 0.0)
    with pytest.raises(ValueError):
        quarter_wave_transformer_impedance(50.0, -200.0)


def test_l_network_match_shunt_first_topology_real_load():
    # Z0=50, Zl=100 (Rl > Z0): hand-verified exact solutions.
    solutions = sorted(l_network_match(50.0, 100.0 + 0j), key=lambda pair: pair[0])
    expected = [(-50.0, -0.01), (50.0, 0.01)]
    assert len(solutions) == len(expected)
    for (x, b), (expected_x, expected_b) in zip(solutions, expected, strict=True):
        assert x == pytest.approx(expected_x)
        assert b == pytest.approx(expected_b)
        z_in = _reconstruct_shunt_at_load_then_series(100.0 + 0j, x, b)
        assert z_in == pytest.approx(50.0 + 0j, abs=1e-9)


def test_l_network_match_series_first_topology_real_load():
    # Z0=50, Zl=25 (Rl < Z0): hand-verified exact solutions.
    solutions = sorted(l_network_match(50.0, 25.0 + 0j), key=lambda pair: pair[0])
    expected = [(-25.0, -0.02), (25.0, 0.02)]
    assert len(solutions) == len(expected)
    for (x, b), (expected_x, expected_b) in zip(solutions, expected, strict=True):
        assert x == pytest.approx(expected_x)
        assert b == pytest.approx(expected_b)
        z_in = _reconstruct_series_at_load_then_shunt(25.0 + 0j, x, b)
        assert z_in == pytest.approx(50.0 + 0j, abs=1e-9)


def test_l_network_match_complex_load_reconstructs_to_source():
    z0 = 50.0
    z_load = 100.0 + 50.0j
    solutions = l_network_match(z0, z_load)
    assert len(solutions) == 2
    for x, b in solutions:
        z_in = _reconstruct_shunt_at_load_then_series(z_load, x, b)
        assert z_in == pytest.approx(complex(z0), abs=1e-9)


def test_l_network_match_boundary_rl_equals_z0_reconstructs_to_source():
    # Rl == Z0 exactly, with a nonzero load reactance: still two distinct
    # solutions (one of which is the trivial X=-Xl, B=0 cancellation).
    z0 = 50.0
    z_load = 50.0 + 30.0j
    solutions = l_network_match(z0, z_load)
    assert len(solutions) == 2
    trivial = [pair for pair in solutions if pair[1] == pytest.approx(0.0, abs=1e-9)]
    assert len(trivial) == 1
    assert trivial[0][0] == pytest.approx(-30.0)
    for x, b in solutions:
        z_in = _reconstruct_shunt_at_load_then_series(z_load, x, b)
        assert z_in == pytest.approx(complex(z0), abs=1e-9)


def test_l_network_match_invalid_inputs_raise():
    with pytest.raises(ValueError):
        l_network_match(0.0, 100.0 + 0j)
    with pytest.raises(ValueError):
        l_network_match(-50.0, 100.0 + 0j)
    with pytest.raises(ValueError):
        l_network_match(50.0, 0.0 + 10j)
    with pytest.raises(ValueError):
        l_network_match(50.0, -10.0 + 10j)
