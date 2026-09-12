import pytest

from rf_tools.link_noise_budget import (
    cascade_gain_db,
    cascade_output_ip3_linear,
    db_to_linear,
    free_space_path_loss_db,
    friis_noise_factor,
    iip3_from_oip3_db,
    link_budget_margin_db,
    oip3_from_iip3_db,
    third_order_intermod_dbc,
    third_order_intermod_output_dbm,
)


def test_friis():
    f1 = 10 ** (2 / 10)
    f2 = 10 ** (3 / 10)
    g1 = 10 ** (10 / 10)
    result = friis_noise_factor([f1, f2], [g1, 10.0])
    expected = f1 + (f2 - 1) / g1
    assert result == pytest.approx(expected)


def test_gain():
    assert cascade_gain_db([10, -3, 20]) == pytest.approx(27)


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
