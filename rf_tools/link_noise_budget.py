from math import log10

import numpy as np


def friis_noise_factor(noise_factors: list[float], gains_linear: list[float]) -> float:
    if len(noise_factors) != len(gains_linear):
        raise ValueError("Noise-factor and gain lists must have equal length.")
    if not noise_factors:
        raise ValueError("At least one stage is required.")
    if any(f < 1 for f in noise_factors):
        raise ValueError("Noise factors must be >= 1.")
    if any(g <= 0 for g in gains_linear):
        raise ValueError("Gains must be positive.")
    total = noise_factors[0]
    product = gains_linear[0]
    for f, g in zip(noise_factors[1:], gains_linear[1:], strict=True):
        total += (f - 1) / product
        product *= g
    return total


def noise_factor_to_db(factor: float) -> float:
    if factor < 1:
        raise ValueError("Noise factor must be >= 1.")
    return 10 * log10(factor)


def db_to_linear(db: float) -> float:
    return 10 ** (db / 10)


def linear_to_db(value: float) -> float:
    if value <= 0:
        raise ValueError("Linear value must be positive.")
    return 10 * log10(value)


def cascade_gain_db(gains_db: list[float]) -> float:
    return float(np.sum(gains_db))


# --- Link budget ---


def free_space_path_loss_db(distance_km: float, freq_mhz: float) -> float:
    """Free-space path loss (FSPL) in dB.

    Units are fixed: distance in kilometres, frequency in megahertz.

        FSPL(dB) = 20*log10(distance_km) + 20*log10(freq_mhz) + 32.44

    The 32.44 constant is the standard ITU-R P.525 / textbook constant for
    this specific km/MHz unit pairing (it is a different constant for any
    other unit combination, e.g. metres/Hz -- do not reuse it there).
    """
    if distance_km <= 0:
        raise ValueError("Distance must be positive.")
    if freq_mhz <= 0:
        raise ValueError("Frequency must be positive.")
    return 20 * log10(distance_km) + 20 * log10(freq_mhz) + 32.44


def link_budget_margin_db(
    tx_power_dbm: float,
    tx_antenna_gain_db: float,
    path_loss_db: float,
    rx_antenna_gain_db: float,
    rx_sensitivity_dbm: float,
    other_losses_db: float = 0.0,
) -> float:
    """Link margin (dB): how far the received power sits above receiver sensitivity.

    All power terms must share one consistent unit -- dBm is conventional;
    dBW works equally well as long as tx_power_dbm and rx_sensitivity_dbm
    use the same unit as each other. Gains and losses are in dB.

        EIRP (dBm)     = tx_power_dbm + tx_antenna_gain_db
        Rx power (dBm) = EIRP - path_loss_db + rx_antenna_gain_db - other_losses_db
        Margin (dB)    = Rx power - rx_sensitivity_dbm

    A positive margin means the link closes with that many dB to spare;
    negative means the link does not close. path_loss_db and
    other_losses_db are loss *magnitudes* and must be non-negative -- a
    negative loss (i.e. a gain) is not physically meaningful for a passive
    propagation path or cable/feeder run.
    """
    if path_loss_db < 0:
        raise ValueError("Path loss must be non-negative.")
    if other_losses_db < 0:
        raise ValueError("Other losses must be non-negative.")
    eirp_dbm = tx_power_dbm + tx_antenna_gain_db
    rx_power_dbm = eirp_dbm - path_loss_db + rx_antenna_gain_db - other_losses_db
    return rx_power_dbm - rx_sensitivity_dbm


# --- Third-order intercept (IP3) and intermodulation distortion (IMD) ---


def cascade_output_ip3_linear(oip3_linear: list[float], gains_linear: list[float]) -> float:
    """Cascaded output-referred third-order intercept point (OIP3), linear units.

    Stages are given in signal-flow order (stage 1 first, i.e. the stage
    the signal hits first). oip3_linear[i] is stage i's own output-referred
    IP3, and gains_linear[i] is stage i's linear power gain; both lists
    must use consistent linear units (e.g. mW for power, dimensionless
    ratio for gain -- use db_to_linear to convert from dB/dBm first). The
    result is in the same power unit as oip3_linear.

    Standard cascade formula (mirrors this module's friis_noise_factor
    pattern, but runs in the opposite direction: friis_noise_factor
    weights each *later* stage's noise contribution by the gain of every
    *earlier* stage, while OIP3 cascading weights each *earlier* stage's
    IP3 contribution by the gain of every *later* stage, since that
    downstream gain amplifies the intermodulation products an early stage
    creates):

        1/OIP3_total = 1/OIP3_n + G_n/OIP3_(n-1) + G_n*G_(n-1)/OIP3_(n-2) + ...

    So a low-IP3 early stage followed by a lot of gain can dominate and
    pull the cascade's OIP3 well below any individual stage's own OIP3.
    """
    if len(oip3_linear) != len(gains_linear):
        raise ValueError("OIP3 and gain lists must have equal length.")
    if not oip3_linear:
        raise ValueError("At least one stage is required.")
    if any(p <= 0 for p in oip3_linear):
        raise ValueError("OIP3 values must be positive.")
    if any(g <= 0 for g in gains_linear):
        raise ValueError("Gains must be positive.")
    inv_total = 0.0
    trailing_gain_product = 1.0
    for oip3, gain in zip(reversed(oip3_linear), reversed(gains_linear), strict=True):
        inv_total += trailing_gain_product / oip3
        trailing_gain_product *= gain
    return 1.0 / inv_total


def oip3_from_iip3_db(iip3_dbm: float, gain_db: float) -> float:
    """Output-referred IP3 from input-referred IP3 and stage gain (all in dB/dBm).

    OIP3(dBm) = IIP3(dBm) + Gain(dB).
    """
    return iip3_dbm + gain_db


def iip3_from_oip3_db(oip3_dbm: float, gain_db: float) -> float:
    """Input-referred IP3 from output-referred IP3 and stage gain (all in dB/dBm).

    IIP3(dBm) = OIP3(dBm) - Gain(dB).
    """
    return oip3_dbm - gain_db


def third_order_intermod_output_dbm(pout_dbm: float, oip3_dbm: float) -> float:
    """Two-tone third-order intermodulation (IM3) product power, output-referred.

    Standard textbook relation between output-referred OIP3 and the IM3
    product power for a two-tone test (e.g. Pozar, "Microwave Engineering";
    also the standard formula used in RF systems engineering references and
    component vendor application notes):

        P_IM3(dBm) = 3*Pout(dBm) - 2*OIP3(dBm)

    where Pout is the output power per tone and OIP3 is the output-referred
    third-order intercept point (both in dBm). At Pout = OIP3 this gives
    P_IM3 = Pout, which is exactly the defining property of the
    (extrapolated) third-order intercept point: the point at which the
    linearly-extrapolated fundamental and IM3 curves cross.

    Requires pout_dbm < oip3_dbm: at or above the intercept the third-order
    extrapolation the model relies on is no longer physically meaningful
    (real amplifiers compress well before reaching their intercept point).
    """
    if pout_dbm >= oip3_dbm:
        raise ValueError(
            "Output power must be below OIP3 for the third-order extrapolation to be valid."
        )
    return 3 * pout_dbm - 2 * oip3_dbm


def third_order_intermod_dbc(pout_dbm: float, oip3_dbm: float) -> float:
    """Two-tone IM3 product level relative to the carrier, in dBc.

        IM3_dBc = 2*(OIP3(dBm) - Pout(dBm))

    Equivalent to pout_dbm - third_order_intermod_output_dbm(pout_dbm, oip3_dbm)
    (how many dB the IM3 product sits below the fundamental). Same validity
    requirement as third_order_intermod_output_dbm: pout_dbm < oip3_dbm.
    """
    if pout_dbm >= oip3_dbm:
        raise ValueError(
            "Output power must be below OIP3 for the third-order extrapolation to be valid."
        )
    return 2 * (oip3_dbm - pout_dbm)
