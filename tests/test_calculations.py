import numpy as np
import pytest

from rf_tools.calculations import (
    abcd_to_s,
    cascade_gain_db,
    friis_noise_factor,
    return_loss_db,
    s_to_abcd,
    s_to_y,
    s_to_z,
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
