import cmath
import math
from math import log10, radians, sin

import numpy as np

# Free-space constants, for the printed-surface sheet-impedance formulas at
# the end of this module. CODATA values; EPS0 is exact-derived from MU0 and c.
MU0 = 4e-7 * math.pi
EPS0 = 8.8541878128e-12


def wavelength(f_hz: float, c_m_s: float = 299_792_458.0) -> float:
    if f_hz <= 0:
        raise ValueError("Frequency must be positive.")
    return c_m_s / f_hz


def reflection_coefficient_from_impedance(z_load: complex, z0: float = 50.0) -> complex:
    """Voltage reflection coefficient Gamma looking into a load impedance,
    referenced to z0 (standard transmission-line result, Pozar, "Microwave
    Engineering"):

        Gamma = (z_load - z0) / (z_load + z0)

    z_load may be a plain float (a purely resistive impedance) or a
    complex number (resistance + j*reactance, e.g. a NEC2/openEMS
    feed-point impedance). z0 defaults to 50 ohms, matching every other
    z0-parameterized conversion in this module (s_to_z/z_to_s/s_to_y/...).
    That default is fine for this general-purpose math function -- the
    caller-facing layer this feeds (orchestration/design_loop.py's
    SIMULATION step, issue #101) requires its own caller to state the
    reference impedance explicitly and records whatever value was used
    alongside the result, rather than leaning on this default silently.

    |Gamma| from the return value feeds directly into vswr_from_gamma/
    return_loss_db above, both of which take |Gamma| (a magnitude), not an
    impedance.
    """
    if z0 <= 0:
        raise ValueError("Reference impedance z0 must be positive.")
    z = complex(z_load)
    z0c = complex(z0)
    denom = z + z0c
    if denom == 0:
        raise ValueError(
            "Reflection coefficient is undefined when z_load + z0 = 0 "
            "(a negative-resistance load exactly cancelling the reference "
            "impedance)."
        )
    return (z - z0c) / denom


def vswr_from_gamma(gamma_mag: float) -> float:
    if not 0 <= gamma_mag < 1:
        raise ValueError("Reflection coefficient magnitude must be in [0, 1).")
    return (1 + gamma_mag) / (1 - gamma_mag)


def return_loss_db(gamma_mag: float) -> float:
    if not 0 < gamma_mag <= 1:
        raise ValueError("Reflection coefficient magnitude must be in (0, 1].")
    return -20 * log10(gamma_mag)


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


def _as_two_port(matrix: list[list[complex]] | np.ndarray, name: str) -> np.ndarray:
    m = np.asarray(matrix, dtype=complex)
    if m.ndim != 2 or m.shape[0] != m.shape[1]:
        raise ValueError(f"{name} matrix must be square.")
    if m.shape != (2, 2):
        raise ValueError(f"{name} matrix must be a 2x2 two-port matrix.")
    return m


def _require_positive_z0(z0: float) -> None:
    if z0 <= 0:
        raise ValueError("Reference impedance z0 must be positive.")


def _invert(matrix: np.ndarray, context: str) -> np.ndarray:
    try:
        return np.linalg.inv(matrix)
    except np.linalg.LinAlgError as exc:
        raise ValueError(f"{context}: matrix is singular and cannot be converted.") from exc


def s_to_z(s_params: list[list[complex]] | np.ndarray, z0: float = 50.0) -> np.ndarray:
    """Convert two-port S-parameters to Z-parameters relative to z0."""
    s = _as_two_port(s_params, "S-parameter")
    _require_positive_z0(z0)
    identity = np.eye(2)
    return z0 * (identity + s) @ _invert(identity - s, "S-to-Z conversion")


def z_to_s(z_params: list[list[complex]] | np.ndarray, z0: float = 50.0) -> np.ndarray:
    """Convert two-port Z-parameters to S-parameters relative to z0."""
    z = _as_two_port(z_params, "Z-parameter")
    _require_positive_z0(z0)
    identity = np.eye(2)
    return (z - z0 * identity) @ _invert(z + z0 * identity, "Z-to-S conversion")


def s_to_y(s_params: list[list[complex]] | np.ndarray, z0: float = 50.0) -> np.ndarray:
    """Convert two-port S-parameters to Y-parameters relative to z0."""
    s = _as_two_port(s_params, "S-parameter")
    _require_positive_z0(z0)
    identity = np.eye(2)
    return (identity - s) @ _invert(identity + s, "S-to-Y conversion") / z0


def y_to_s(y_params: list[list[complex]] | np.ndarray, z0: float = 50.0) -> np.ndarray:
    """Convert two-port Y-parameters to S-parameters relative to z0."""
    y = _as_two_port(y_params, "Y-parameter")
    _require_positive_z0(z0)
    identity = np.eye(2)
    return (identity - z0 * y) @ _invert(identity + z0 * y, "Y-to-S conversion")


def s_to_abcd(s_params: list[list[complex]] | np.ndarray, z0: float = 50.0) -> np.ndarray:
    """Convert two-port S-parameters to ABCD-parameters relative to z0."""
    s = _as_two_port(s_params, "S-parameter")
    _require_positive_z0(z0)
    s11, s12, s21, s22 = s[0, 0], s[0, 1], s[1, 0], s[1, 1]
    if s21 == 0:
        raise ValueError("S-to-ABCD conversion: S21 is zero, ABCD representation is undefined.")
    a = ((1 + s11) * (1 - s22) + s12 * s21) / (2 * s21)
    b = z0 * ((1 + s11) * (1 + s22) - s12 * s21) / (2 * s21)
    c = ((1 - s11) * (1 - s22) - s12 * s21) / (2 * s21 * z0)
    d = ((1 - s11) * (1 + s22) + s12 * s21) / (2 * s21)
    return np.array([[a, b], [c, d]], dtype=complex)


def abcd_to_s(abcd_params: list[list[complex]] | np.ndarray, z0: float = 50.0) -> np.ndarray:
    """Convert two-port ABCD-parameters to S-parameters relative to z0."""
    abcd = _as_two_port(abcd_params, "ABCD-parameter")
    _require_positive_z0(z0)
    a, b, c, d = abcd[0, 0], abcd[0, 1], abcd[1, 0], abcd[1, 1]
    denom = a + b / z0 + c * z0 + d
    if denom == 0:
        raise ValueError(
            "ABCD-to-S conversion: denominator is zero, S representation is undefined."
        )
    s11 = (a + b / z0 - c * z0 - d) / denom
    s12 = 2 * (a * d - b * c) / denom
    s21 = 2 / denom
    s22 = (-a + b / z0 - c * z0 + d) / denom
    return np.array([[s11, s12], [s21, s22]], dtype=complex)


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


# --- Stability (Rollett K-factor and stability circles) ---


def two_port_stability_delta(s_params: list[list[complex]] | np.ndarray) -> complex:
    """The two-port determinant Delta = S11*S22 - S12*S21.

    Delta feeds both the Rollett K-factor and the stability-circle formulas
    below (Pozar, "Microwave Engineering"). |Delta| < 1 is one of the two
    conditions (together with K > 1) required for unconditional stability.
    """
    s = _as_two_port(s_params, "S-parameter")
    s11, s12, s21, s22 = s[0, 0], s[0, 1], s[1, 0], s[1, 1]
    return complex(s11 * s22 - s12 * s21)


def rollett_k_factor(s_params: list[list[complex]] | np.ndarray) -> float:
    """The Rollett stability factor K for a two-port network's S-parameters.

        K = (1 - |S11|^2 - |S22|^2 + |Delta|^2) / (2*|S12*S21|)

    where Delta = S11*S22 - S12*S21 (see two_port_stability_delta). K alone
    does not determine stability -- see stability_verdict, which also
    requires |Delta| < 1.
    """
    s = _as_two_port(s_params, "S-parameter")
    s11, s12, s21, s22 = s[0, 0], s[0, 1], s[1, 0], s[1, 1]
    denom = 2 * abs(s12 * s21)
    if denom == 0:
        raise ValueError(
            "Rollett K-factor is undefined when S12*S21 = 0 "
            "(no forward/reverse coupling between the ports)."
        )
    delta = s11 * s22 - s12 * s21
    k = (1 - abs(s11) ** 2 - abs(s22) ** 2 + abs(delta) ** 2) / denom
    return float(k)


def stability_verdict(s_params: list[list[complex]] | np.ndarray) -> str:
    """Unconditional/conditional-stability verdict for a two-port network.

    A network is unconditionally stable -- stable for *any* passive
    source and load termination -- only when BOTH standard conditions
    hold simultaneously (Rollett's criterion):

        K > 1  AND  |Delta| < 1

    Returns the literal string "unconditionally stable" when both hold,
    otherwise "potentially unstable" -- meaning at least one region of
    passive source/load impedances exists that can drive the network into
    oscillation, even though specific terminations (see
    input_stability_circle / output_stability_circle) may still be safe.
    """
    k = rollett_k_factor(s_params)
    delta_mag = abs(two_port_stability_delta(s_params))
    if k > 1 and delta_mag < 1:
        return "unconditionally stable"
    return "potentially unstable"


def output_stability_circle(s_params: list[list[complex]] | np.ndarray) -> tuple[complex, float]:
    """Output (load-plane) stability circle center and radius.

    Returns (center, radius) for the locus of load reflection coefficients
    Gamma_L that place the input reflection coefficient exactly on
    |Gamma_in| = 1 -- the boundary between stable and potentially-unstable
    load terminations (Pozar, "Microwave Engineering"):

        Delta  = S11*S22 - S12*S21
        C_out  = conj(S22 - Delta*conj(S11)) / (|S22|^2 - |Delta|^2)
        R_out  = |S12*S21| / |S22|^2 - |Delta|^2|
    """
    s = _as_two_port(s_params, "S-parameter")
    s11, s12, s21, s22 = s[0, 0], s[0, 1], s[1, 0], s[1, 1]
    delta = s11 * s22 - s12 * s21
    denom = abs(s22) ** 2 - abs(delta) ** 2
    if denom == 0:
        raise ValueError("Output stability circle is undefined when |S22|^2 = |Delta|^2.")
    center = np.conj(s22 - delta * np.conj(s11)) / denom
    radius = abs(s12 * s21) / abs(denom)
    return complex(center), float(radius)


def input_stability_circle(s_params: list[list[complex]] | np.ndarray) -> tuple[complex, float]:
    """Input (source-plane) stability circle center and radius.

    Returns (center, radius) for the locus of source reflection
    coefficients Gamma_S that place the output reflection coefficient
    exactly on |Gamma_out| = 1. Mirrors output_stability_circle with
    S11 and S22 swapped (Pozar, "Microwave Engineering"):

        Delta = S11*S22 - S12*S21
        C_in  = conj(S11 - Delta*conj(S22)) / (|S11|^2 - |Delta|^2)
        R_in  = |S12*S21| / |S11|^2 - |Delta|^2|
    """
    s = _as_two_port(s_params, "S-parameter")
    s11, s12, s21, s22 = s[0, 0], s[0, 1], s[1, 0], s[1, 1]
    delta = s11 * s22 - s12 * s21
    denom = abs(s11) ** 2 - abs(delta) ** 2
    if denom == 0:
        raise ValueError("Input stability circle is undefined when |S11|^2 = |Delta|^2.")
    center = np.conj(s11 - delta * np.conj(s22)) / denom
    radius = abs(s12 * s21) / abs(denom)
    return complex(center), float(radius)


# --- Impedance matching ---


def quarter_wave_transformer_impedance(z_source: float, z_load: float) -> float:
    """Characteristic impedance of a quarter-wave (Q-wave) transformer.

    Matches two *real* (resistive) impedances at the design frequency
    where the transformer section is electrically one quarter-wavelength
    long:

        Z_transformer = sqrt(Z_source * Z_load)

    This is the standard, well-defined case (Pozar, "Microwave
    Engineering"); it is not valid for complex/reactive impedances -- use
    l_network_match for a complex load instead.
    """
    if z_source <= 0:
        raise ValueError("Source impedance must be positive.")
    if z_load <= 0:
        raise ValueError("Load impedance must be positive.")
    return (z_source * z_load) ** 0.5


def l_network_match(z_source: float, z_load: complex) -> list[tuple[float, float]]:
    """Synthesize a lossless L-network matching z_load to a real z_source.

    Standard two-solution L-network synthesis (Pozar, "Microwave
    Engineering", sec. 5.1). Returns a list of one or two (X, B) pairs,
    where X is a series reactance in ohms (positive = inductive,
    negative = capacitive) and B is a shunt susceptance in siemens
    (positive = capacitive, negative = inductive). Both pairs are valid,
    independent solutions to the same matching problem (e.g. one may be
    realizable with smaller/cheaper components at a given frequency); a
    single solution is returned only when the two roots coincide exactly
    (e.g. a purely resistive load already equal to z_source).

    Topology is chosen from Re(z_load) relative to z_source, per Pozar:

    - Re(z_load) >= z_source: the shunt element (B) connects directly
      across the load, with the series element (X) between that node and
      the source -- i.e. build the network load-to-source as
      1/(1/z_load + jB) then + jX, and that total should equal z_source.
    - Re(z_load) < z_source: the series element (X) connects directly to
      the load, with the shunt element (B) between that node and the
      source -- i.e. build the network load-to-source as
      1/(1/(z_load + jX) + jB), and that total should equal z_source.

    Raises ValueError if z_source or Re(z_load) is not positive (an L-network
    matching a purely reactive or active/negative-resistance load is a
    different problem, not covered here).
    """
    if z_source <= 0:
        raise ValueError("Source impedance must be positive.")
    zl = complex(z_load)
    rl, xl = zl.real, zl.imag
    if rl <= 0:
        raise ValueError("Load resistance (real part of z_load) must be positive.")

    solutions: list[tuple[float, float]] = []
    if rl >= z_source:
        denom = rl**2 + xl**2
        discriminant = rl**2 + xl**2 - z_source * rl
        sqrt_term = (rl / z_source) ** 0.5 * discriminant**0.5
        gl = rl / denom
        bl_prime = -xl / denom
        for b in {(xl + sqrt_term) / denom, (xl - sqrt_term) / denom}:
            x = (bl_prime + b) * z_source / gl
            solutions.append((float(x), float(b)))
    else:
        discriminant = rl * (z_source - rl)
        sqrt_term = discriminant**0.5
        for x in {-xl + sqrt_term, -xl - sqrt_term}:
            b = (xl + x) / (rl * z_source)
            solutions.append((float(x), float(b)))
    return solutions


# --- Conformal antenna: resonant frequency and bandwidth ---
#
# The functions below implement the standard microstrip patch antenna
# transmission-line model (Balanis, "Antenna Theory: Analysis and Design",
# the widely-used starting point for "resonant frequency from substrate +
# dimensions"). All geometric inputs/outputs are in metres, all frequencies
# in hertz.


def patch_effective_permittivity(eps_r: float, w_m: float, h_m: float) -> float:
    """Effective dielectric constant of a microstrip patch (transmission-line model).

    Standard result (Balanis, "Antenna Theory", transmission-line model for
    a rectangular microstrip patch):

        eps_eff = (eps_r+1)/2 + (eps_r-1)/2 * (1 + 12*h/W)^(-0.5)

    where eps_r is the substrate's relative dielectric constant, h is the
    substrate thickness (m), and W is the patch width (m). Only valid for
    W/h > 1 (the wide-microstrip regime the formula was derived for); a
    narrower patch needs a different fringing-field model not implemented
    here.
    """
    if eps_r <= 1:
        raise ValueError(
            "patch_effective_permittivity's fringing-field fit is only "
            "valid for eps_r > 1 (it interpolates between eps_r and 1)."
        )
    if h_m <= 0:
        raise ValueError("Substrate thickness h_m must be positive.")
    if w_m <= 0:
        raise ValueError("Patch width w_m must be positive.")
    if w_m / h_m <= 1:
        raise ValueError(
            "patch_effective_permittivity is only valid for W/h > 1 "
            "(wide-microstrip transmission-line model)."
        )
    return (eps_r + 1) / 2 + (eps_r - 1) / 2 * (1 + 12 * h_m / w_m) ** -0.5


def patch_length_extension_m(eps_eff: float, w_m: float, h_m: float) -> float:
    """Fringing-field length extension dL for a microstrip patch, in metres.

    Standard result (Balanis, "Antenna Theory", transmission-line model):
    the patch's fringing fields make it look electrically longer than its
    physical length L by 2*dL (one extension per radiating edge), with

        dL = 0.412*h*(eps_eff+0.3)*(W/h+0.264) / ((eps_eff-0.258)*(W/h+0.8))

    where eps_eff is the effective permittivity (see
    patch_effective_permittivity), h the substrate thickness (m), and W the
    patch width (m).
    """
    if eps_eff <= 0.258:
        raise ValueError(
            "patch_length_extension_m requires eps_eff > 0.258 "
            "(the fringing-extension formula's denominator is undefined otherwise)."
        )
    if w_m <= 0:
        raise ValueError("Patch width w_m must be positive.")
    if h_m <= 0:
        raise ValueError("Substrate thickness h_m must be positive.")
    w_over_h = w_m / h_m
    return (
        0.412 * h_m * (eps_eff + 0.3) * (w_over_h + 0.264) / ((eps_eff - 0.258) * (w_over_h + 0.8))
    )


def patch_resonant_frequency_hz(
    eps_r: float,
    w_m: float,
    h_m: float,
    l_m: float,
    c_m_s: float = 299_792_458.0,
) -> float:
    """Dominant-mode (TM010) resonant frequency of a rectangular microstrip patch.

    Standard microstrip transmission-line model result (Balanis, "Antenna
    Theory"):

        eps_eff = patch_effective_permittivity(eps_r, w_m, h_m)
        dL      = patch_length_extension_m(eps_eff, w_m, h_m)
        L_eff   = L + 2*dL
        f_r     = c / (2 * L_eff * sqrt(eps_eff))

    where L is the patch's physical (flat, nominally uncurved) resonant
    length. This is the reference "as-designed-flat" resonant frequency
    that curvature_shifted_resonant_frequency_hz perturbs for a curved
    host surface -- see that function's docstring, and the "Conformal
    antenna" definition in CONTEXT.md, for how the two connect.
    """
    if l_m <= 0:
        raise ValueError("Patch length l_m must be positive.")
    if c_m_s <= 0:
        raise ValueError("Speed of light c_m_s must be positive.")
    eps_eff = patch_effective_permittivity(eps_r, w_m, h_m)
    dl = patch_length_extension_m(eps_eff, w_m, h_m)
    l_eff = l_m + 2 * dl
    return c_m_s / (2 * l_eff * eps_eff**0.5)


# --- Microstrip line: characteristic impedance and width synthesis (issue #286) ---
#
# Distinct from patch_effective_permittivity/patch_length_extension_m above,
# on purpose: those restate this identical Hammerstad fringing-field fit
# inside Balanis's patch-ANTENNA presentation, which frames it for W/h > 1
# (a resonant patch is normally much wider than the substrate is thick) and
# enforces that as a hard precondition. Pozar's general microstrip
# TRANSMISSION-LINE treatment ("Microwave Engineering" 4th ed., Table 3.2)
# states the same eps_eff formula with no such floor, and adds the
# characteristic-impedance analysis/synthesis pair below, which DOES split
# at W/h = 1 -- exactly the geometry rf_tools/filter_synthesis.py's
# stepped-impedance realization needs: its high-impedance ("Hi-Z") line
# sections come out narrow (W/h < 1, outside patch_effective_permittivity's
# own domain) and its low-impedance ("Lo-Z") sections come out wide
# (W/h > 1). Two functions computing the same fringing-field number for two
# different stated domains is deliberate here, the same way this module
# already carries two published forms of Costa's thin-spacer correction
# side by side (COSTA_EQ10_FORMS) rather than picking one and hoping it
# generalizes.


def microstrip_effective_permittivity(eps_r: float, w_m: float, h_m: float) -> float:
    """Effective dielectric constant of a microstrip line, valid for any W/h
    (Pozar, "Microwave Engineering" 4th ed., Table 3.2):

        eps_eff = (eps_r+1)/2 + (eps_r-1)/2 * (1 + 12*h/W)^(-0.5)

    Same closed form as patch_effective_permittivity above -- restated here
    because Pozar's general line treatment carries no W/h > 1 floor, unlike
    Balanis's patch-antenna one (see the module note just above).
    """
    if eps_r <= 1:
        raise ValueError(f"eps_r must be > 1; got {eps_r!r}.")
    if h_m <= 0:
        raise ValueError("Substrate thickness h_m must be positive.")
    if w_m <= 0:
        raise ValueError("Line width w_m must be positive.")
    return (eps_r + 1) / 2 + (eps_r - 1) / 2 * (1 + 12 * h_m / w_m) ** -0.5


def microstrip_characteristic_impedance_ohm(eps_r: float, w_m: float, h_m: float) -> float:
    """Characteristic impedance of a microstrip line from its geometry (the
    analysis direction: width known, impedance wanted). Pozar, Table 3.2,
    split at W/h = 1:

        W/h <= 1:  Z0 = (60/sqrt(eps_eff)) * ln(8h/W + W/(4h))
        W/h >= 1:  Z0 = (120*pi/sqrt(eps_eff)) / (W/h + 1.393 + 0.667*ln(W/h + 1.444))

    eps_eff is microstrip_effective_permittivity(eps_r, w_m, h_m). This is
    the inverse direction of microstrip_synthesize_width_m, and exists
    mainly to check that pairing: running a synthesized width back through
    this function recovers the target Z0 to within Pozar's own stated
    accuracy for the pair (about 1%), which is the standard way this
    approximate design procedure is verified in the literature.
    """
    if eps_r <= 1:
        raise ValueError(f"eps_r must be > 1; got {eps_r!r}.")
    if w_m <= 0:
        raise ValueError("Line width w_m must be positive.")
    if h_m <= 0:
        raise ValueError("Substrate thickness h_m must be positive.")
    eps_eff = microstrip_effective_permittivity(eps_r, w_m, h_m)
    w_over_h = w_m / h_m
    if w_over_h <= 1:
        return (60.0 / eps_eff**0.5) * math.log(8.0 / w_over_h + w_over_h / 4.0)
    return (120.0 * math.pi / eps_eff**0.5) / (
        w_over_h + 1.393 + 0.667 * math.log(w_over_h + 1.444)
    )


def microstrip_synthesize_width_m(z0_ohm: float, eps_r: float, h_m: float) -> float:
    """Microstrip line width for a target characteristic impedance (the
    synthesis direction: impedance known, width wanted). Pozar, Table 3.2:

        A = Z0/60 * sqrt((eps_r+1)/2) + (eps_r-1)/(eps_r+1) * (0.23 + 0.11/eps_r)
        W/h = 8*e^A / (e^(2A) - 2)                                    -- narrow/high-Z0

        B = 377*pi / (2*Z0*sqrt(eps_r))
        W/h = (2/pi) * [B-1-ln(2B-1) + (eps_r-1)/(2*eps_r)*(ln(B-1)+0.39-0.61/eps_r)]
                                                                        -- wide/low-Z0

    The A-formula is only self-consistent where it predicts W/h <= 2 (a
    genuinely narrow, high-impedance line); computed for a lower target Z0
    it would predict W/h > 2, so the B-formula is used instead. This project
    verified the pair by hand against two independently published worked
    examples reproducing this exact procedure before relying on it here
    (see rf_tools/filter_synthesis.py's stepped-impedance realization and
    tests/test_calculations.py).

    Returns the width in metres for a substrate of thickness h_m and
    relative permittivity eps_r.
    """
    if z0_ohm <= 0:
        raise ValueError("z0_ohm must be positive.")
    if eps_r <= 1:
        raise ValueError(f"eps_r must be > 1; got {eps_r!r}.")
    if h_m <= 0:
        raise ValueError("Substrate thickness h_m must be positive.")
    a = z0_ohm / 60.0 * ((eps_r + 1) / 2) ** 0.5 + (eps_r - 1) / (eps_r + 1) * (0.23 + 0.11 / eps_r)
    w_over_h = 8.0 * math.exp(a) / (math.exp(2 * a) - 2.0)
    if w_over_h > 2.0:
        b = 377.0 * math.pi / (2.0 * z0_ohm * eps_r**0.5)
        w_over_h = (2.0 / math.pi) * (
            b
            - 1.0
            - math.log(2 * b - 1)
            + (eps_r - 1) / (2 * eps_r) * (math.log(b - 1) + 0.39 - 0.61 / eps_r)
        )
    return w_over_h * h_m


# --- Fractional bandwidth <-> quality factor ---
#
# Standard antenna-engineering relation between an antenna's (loaded)
# quality factor Q and its impedance bandwidth for a given VSWR threshold
# (Balanis, "Antenna Theory"; also Pozar, "Microwave Engineering", sec.
# 6.x resonator-bandwidth treatment, applied to an antenna's resonant
# input impedance):
#
#     FBW = (VSWR - 1) / (Q * sqrt(VSWR))
#
# where FBW = Delta_f / f_r is the fractional bandwidth over which the
# antenna's VSWR stays at or below the given threshold. This is the
# VSWR-dependent bandwidth definition (not the simpler FBW = 1/Q, which is
# the special case of a matched-load half-power/3-dB bandwidth, VSWR ~
# 2.618 -- deliberately not assumed here since VSWR targets in antenna
# design are usually stated explicitly, most commonly VSWR = 2.0).


def fractional_bandwidth_from_q(q: float, vswr: float = 2.0) -> float:
    """Fractional impedance bandwidth from quality factor Q, for a given VSWR threshold.

        FBW = (VSWR - 1) / (Q * sqrt(VSWR))

    vswr defaults to 2.0 (the standard 2:1 VSWR bandwidth definition
    commonly used in antenna design, corresponding to -9.54 dB return
    loss). See module notes above for the formula's source.
    """
    if q <= 0:
        raise ValueError("Quality factor Q must be positive.")
    if vswr <= 1:
        raise ValueError("VSWR must be > 1.")
    return (vswr - 1) / (q * vswr**0.5)


def quality_factor_from_fractional_bandwidth(fbw: float, vswr: float = 2.0) -> float:
    """Quality factor Q from fractional impedance bandwidth, for a given VSWR threshold.

    Inverse of fractional_bandwidth_from_q:

        Q = (VSWR - 1) / (FBW * sqrt(VSWR))
    """
    if fbw <= 0:
        raise ValueError("Fractional bandwidth must be positive.")
    if vswr <= 1:
        raise ValueError("VSWR must be > 1.")
    return (vswr - 1) / (fbw * vswr**0.5)


# --- Curvature-induced resonant-frequency shift ---
#
# APPROXIMATION NOTICE: unlike the formulas above, there is no single
# settled closed-form textbook formula for exactly how much a microstrip
# patch's resonant frequency shifts when it is conformed to a curved host
# surface -- the general conformal-antenna literature (e.g. Josefsson &
# Persson, "Conformal Array Antenna Theory and Design"; various microstrip-
# on-cylinder studies) agrees curvature perturbs the resonant frequency by
# effectively changing the patch's electrical length as seen by the
# resonant cavity mode, but the reported magnitude/sign vary by bend axis
# (E-plane vs. H-plane), substrate properties, and analysis method, and
# usually require full-wave simulation to pin down precisely.
#
# The model implemented here is a first-order *geometric* proxy for that
# effect, not a re-derivation of a specific paper's result. It models a
# patch of fixed physical (material) length L -- i.e. conformed to the
# host surface by bending, not by stretching -- as an arc of a circle of
# radius R (the host's radius of curvature). The straight-line separation
# between the patch's two radiating edges (the "chord") is what actually
# sets the free-space fringing-field geometry the cavity model depends on,
# and is exactly (circular-arc chord-length geometry):
#
#     chord = 2*R*sin(L / (2*R))
#
# which is always < L for R finite, i.e. curvature always shortens that
# edge-to-edge separation relative to the flat design. Treating the
# resonant frequency as inversely proportional to that edge separation
# (consistent with f_r ~ 1/L_eff in the flat-patch formula above) gives
# the first-order curvature correction:
#
#     f_r_curved = f_r_flat * L / chord = f_r_flat * L / (2*R*sin(L/(2*R)))
#
# This always predicts a small frequency *increase* under curvature (chord
# < L), consistent with the general literature direction ("curvature
# changes the effective electrical length") for a bend that shortens the
# edge-to-edge span; it does not capture bend-axis-dependent sign reversals
# reported in some studies. Validity is restricted to L/R < 0.5 (a
# moderate-curvature regime where the geometric picture above stays a
# credible first-order proxy); treat results near that bound as order-of-
# magnitude estimates only, and validate against simulation/measurement
# before using this for a final design.


def curvature_length_correction_factor(l_m: float, radius_of_curvature_m: float) -> float:
    """First-order geometric length-correction factor for a patch bent to radius R.

    Returns L / chord = L / (2*R*sin(L/(2*R))), always >= 1 -- see the
    module notes above (under "Curvature-induced resonant-frequency
    shift") for the derivation, its approximation status, and its citation.
    Restricted to L/R < 0.5.
    """
    if l_m <= 0:
        raise ValueError("Patch length l_m must be positive.")
    if radius_of_curvature_m <= 0:
        raise ValueError("Radius of curvature must be positive.")
    if l_m / radius_of_curvature_m >= 0.5:
        raise ValueError(
            "curvature_length_correction_factor is only valid for L/R < 0.5 "
            "(moderate-curvature regime; see module notes for the approximation "
            "this bound protects)."
        )
    half_angle = l_m / (2 * radius_of_curvature_m)
    chord = 2 * radius_of_curvature_m * sin(half_angle)
    return l_m / chord


def curvature_shifted_resonant_frequency_hz(
    f_flat_hz: float, l_m: float, radius_of_curvature_m: float
) -> float:
    """Estimated resonant frequency of a nominally-flat patch design conformed to radius R.

        f_r_curved = f_r_flat * curvature_length_correction_factor(L, R)

    f_flat_hz is the resonant frequency of the nominally-flat reference
    design (e.g. from patch_resonant_frequency_hz), L is the patch's
    physical resonant length (m), and radius_of_curvature_m is the host
    surface's radius of curvature (m). See the module notes above (under
    "Curvature-induced resonant-frequency shift") for the model's
    derivation and its explicit approximation/validity caveats -- this is
    a first-order estimate for first-pass sizing, not a substitute for
    simulation or measurement.
    """
    if f_flat_hz <= 0:
        raise ValueError("Flat-design resonant frequency f_flat_hz must be positive.")
    factor = curvature_length_correction_factor(l_m, radius_of_curvature_m)
    return f_flat_hz * factor


# --- Periodic/coded-surface curvature validity box (S <= 2*theta_max*R) ---
#
# A DIFFERENT curvature question than the patch model above: not "how much
# does the resonant frequency shift", but "does a Tier B coded/periodic
# surface's element still behave the way it was characterised, once the
# host bends it". docs/curvature-effects-on-em-surfaces.md section 4.2
# derives the rule from Khan et al.'s measured central-angle/element-
# stability relation: on a cylinder of radius R, a cell an arc distance s
# from the crown sees a local incidence angle theta(s) = s/R (section 0(i)).
# An element is only characterised (CONTEXT.md's Validity box) up to some
# angular-stability limit theta_max before its reflection response leaves
# the tolerance the design actually needs -- so the usable aperture arc
# length is bounded by
#
#     S <= 2 * theta_max * R
#
# (the special case S = 2*45degrees*R is Khan et al.'s own worked result).
# Exceeding it is exactly the validity-box violation issue #322/ADR-0021/
# ADR-0025 mean by a family's OWN characterised limits excluding it -- a
# fact about the requirement's stated host curvature and the chosen
# family's own characterised element, never about configured shop
# equipment.


def curvature_exceeds_validity_box(
    arc_length_m: float, host_radius_m: float, theta_max_deg: float
) -> bool:
    """True if a periodic/coded surface's stated host curvature puts its
    outermost cells beyond the characterised element's angular-stability
    limit -- i.e. `arc_length_m > 2 * theta_max * host_radius_m` (module
    notes above, "Periodic/coded-surface curvature validity box"; docs/
    curvature-effects-on-em-surfaces.md section 4.2).

    `arc_length_m` (S) is the requirement's own stated usable aperture arc
    length along the bend; `host_radius_m` (R) is the host's stated radius
    of curvature; `theta_max_deg` is the chosen family/element's OWN
    characterised angular-stability limit (never a shop-equipment figure).
    Both S and R must be positive, and theta_max_deg must be in (0, 90]
    degrees (no published element stays angle-stable at or past grazing
    incidence) -- raises ValueError otherwise, the geometry is undefined.
    """
    if arc_length_m <= 0:
        raise ValueError("arc_length_m must be positive.")
    if host_radius_m <= 0:
        raise ValueError("host_radius_m must be positive.")
    if not 0 < theta_max_deg <= 90:
        raise ValueError("theta_max_deg must be in (0, 90] degrees.")
    return arc_length_m > 2 * radians(theta_max_deg) * host_radius_m


# --- Metamaterial unit-cell effective-medium parameters (Maxwell-Garnett) ---


def maxwell_garnett_effective_permeability(
    fill_fraction: float, mu_r: float, mu_host: float = 1.0
) -> float:
    """Effective relative permeability of a dilute array of magnetic elements.

    Standard Maxwell-Garnett effective-medium mixing formula (Maxwell
    Garnett, 1904; the standard homogenization-theory starting point for
    predicting a metamaterial unit cell's bulk effective magnetic property
    from its element geometry -- see CONTEXT.md's "Metamaterial unit cell"
    entry: elongated, passive-magnetic-property elements at a given fill
    fraction in a host medium), applied here to permeability (the form
    matching this project's actual metamaterial elements) rather than the
    more commonly quoted permittivity form -- both are the same mixing
    rule with mu <-> eps swapped:

        (mu_eff - mu_host) / (mu_eff + 2*mu_host)
            = f * (mu_r - mu_host) / (mu_r + 2*mu_host)

    Solved for mu_eff (closed form):

        beta   = (mu_r - mu_host) / (mu_r + 2*mu_host)
        mu_eff = mu_host * (1 + 2*f*beta) / (1 - f*beta)

    where f is the elements' fill fraction (volume filling factor, 0-1) in
    the host medium, mu_r is the element material's own relative
    permeability, and mu_host is the host medium's relative permeability
    (defaults to 1.0 for free space / a typical non-magnetic host).

    This is a DILUTE-LIMIT approximation: it assumes the elements are
    sparse enough that each sees only the host medium's applied field, not
    its neighbors' scattered fields. It is standard and well cited for
    small fill fractions, but is known to lose accuracy as f grows --
    element-element electromagnetic coupling becomes significant and this
    Clausius-Mossotti-style mixing rule under/overestimates mu_eff. Treat
    f >~ 0.3 as outside this formula's comfortable validity range (a rough,
    commonly cited homogenization-theory rule of thumb, not a hard physical
    cutoff enforced here); do not present this function's output as an
    exact result at high fill fraction without validating against
    simulation or measurement.
    """
    if not 0 <= fill_fraction < 1:
        raise ValueError("Fill fraction must be in [0, 1).")
    if mu_r <= 0:
        raise ValueError("Element relative permeability mu_r must be positive.")
    if mu_host <= 0:
        raise ValueError("Host relative permeability mu_host must be positive.")
    beta = (mu_r - mu_host) / (mu_r + 2 * mu_host)
    denom = 1 - fill_fraction * beta
    if denom == 0:
        raise ValueError(
            "Maxwell-Garnett mixing formula is undefined for this "
            "fill_fraction/mu_r/mu_host combination (1 - f*beta = 0)."
        )
    return mu_host * (1 + 2 * fill_fraction * beta) / denom


# --- Aperture antenna gain ---


def aperture_gain(area_m2: float, freq_hz: float, aperture_efficiency: float = 0.55) -> float:
    """Estimated linear (dimensionless) gain of an aperture antenna.

    Standard aperture-antenna gain formula (Balanis, "Antenna Theory:
    Analysis and Design"):

        G = 4*pi*A_eff / lambda^2 * eta_ap

    where A_eff is the antenna's physical aperture area (m^2), lambda is
    the free-space wavelength at freq_hz (computed via this module's own
    wavelength() function, per this project's convention of composing
    prior deterministic functions rather than recomputing them), and
    eta_ap is the aperture efficiency -- the fraction of the physical
    aperture that radiates as if uniformly illuminated (illumination
    taper, spillover, and phase error all reduce it below 1.0).

    aperture_efficiency defaults to 0.55, a commonly cited "typical"
    aperture efficiency for practical reflector/horn/array apertures
    (Balanis; antenna-engineering references commonly cite a broad
    0.5-0.6 "typical" range). This default is a nominal planning value,
    not a measured or simulated figure for any specific design -- pass an
    explicit value once one is known (datasheet, simulation, or
    measurement).

    Returns linear gain (dimensionless, referenced to an isotropic
    radiator); use linear_to_db() from this module to convert to dBi.
    """
    if area_m2 <= 0:
        raise ValueError("Aperture area must be positive.")
    if not 0 < aperture_efficiency <= 1:
        raise ValueError("Aperture efficiency must be in (0, 1].")
    lambda_m = wavelength(freq_hz)
    return 4 * np.pi * area_m2 / lambda_m**2 * aperture_efficiency


# --- Printed-surface sheet impedance: the grid pair, and the squares rule ---
#
# The formulas below are what a printed metamaterial skin's unit cell
# presents to an incident wave, and they had lived only inside a browser
# prototype (geometry/prototype_lossy_cell_fit.html) and a throwaway bench
# script -- so every question about a printed cell was re-deriving them.
#
# CAPACITIVE GRID (patches separated by gaps), Luukkonen et al.'s
# analytical grid impedance as used inside Costa et al.'s absorber stack
# model (arXiv:1211.1902), which issue #111 adopted:
#
#     C = eps_0 * eps_eff * (2p / pi) * ln(1 / sin(pi*g / 2p))
#
# with p the cell period, g the gap between adjacent patches, and
# eps_eff = (eps_r + 1)/2 -- the half-air, half-substrate average the gap
# field actually sees, which is also why the gap's effective loss tangent
# is diluted to eps_r*tan_delta/(eps_r + 1).
#
# INDUCTIVE GRID (a mesh of wires or loops) is the EXACT BABINET DUAL of
# that expression -- the complementary structure, with the roles of the
# metal and the gap exchanged:
#
#     L = mu_0 * (p / 2pi) * ln(1 / sin(pi*w / 2p))
#
# with w the strip width. Keeping the pair together, and derived from one
# duality rather than two independent fits, is what lets a ring/loop cell
# and a patch cell be evaluated on the same code path (L = 0 recovers the
# pure-patch case exactly).
#
# VALIDITY BOX for both: a sub-wavelength periodic grid (p << lambda),
# normal incidence, an infinitesimally thin perfect grid over a uniform
# half-space. They are SCATTERING surrogates -- valid for predicting what a
# surface reflects, never for extracting a material's own properties
# (#111).


def grid_effective_permittivity(eps_r: float) -> float:
    """The half-air, half-substrate average a coplanar grid's gap field sees.

        eps_eff = (eps_r + 1) / 2

    Not an approximation of the substrate's own permittivity -- the gap
    field genuinely straddles both media, so a grid printed on eps_r = 3
    behaves as though the gap sat in eps_eff = 2.

    ASSUMPTION: AIR ABOVE. The "+ 1" is eps_r of air/vacuum, hardcoded
    because this grid was assumed bare. That fails for a grid with an
    encapsulation or coverlay layer on top instead of open air -- the gap
    field then straddles substrate and coverlay, not substrate and air. The
    general form is eps_eff = (eps_above + eps_below) / 2, valid while each
    bounding layer is thicker than roughly 0.3-0.5x the cell period (thinner
    than that, the field reaches through to whatever is beyond it too, and
    even the two-layer average stops holding). See
    docs/encapsulation-em-coupling.md for how encapsulation is meant to enter
    this stack; this function does not yet take an `eps_above` argument.
    """
    if eps_r < 1:
        raise ValueError(f"eps_r must be >= 1; got {eps_r!r}.")
    return (eps_r + 1) / 2


def grid_gap_loss_tangent(eps_r: float, tan_delta: float) -> float:
    """The loss tangent the gap actually sees, diluted by the air above it.

        tan_delta_gap = eps_r * tan_delta / (eps_r + 1)

    Always smaller than the bulk substrate's -- roughly half of it for
    large eps_r, and less than that for small. Using the bulk figure in a
    grid model overstates the gap's dissipation.
    """
    if eps_r < 1:
        raise ValueError(f"eps_r must be >= 1; got {eps_r!r}.")
    if tan_delta < 0:
        raise ValueError(f"tan_delta must be non-negative; got {tan_delta!r}.")
    return eps_r * tan_delta / (eps_r + 1)


# --- Costa's thin-spacer capacitance correction (issue #245) ---
#
# The grid capacitance above is a FREE-STANDING result: it assumes the
# patches see nothing but the substrate around them. Put a ground plane a
# short distance behind them and that stops being true -- the patches also
# couple to the mirror, and store more charge than the free-standing formula
# admits. Costa et al. (arXiv:1211.1902 eq 10) add that charge back:
#
#     C0_thin = C0 - (2p*eps_0/pi) * ln(1 - exp(-4*pi*d/p))
#
# with p the cell period and d the spacer thickness. The exponential is
# between 0 and 1, so the logarithm is negative and subtracting it ADDS --
# the capacitance can only rise, and the rise grows as the spacer thins,
# which is exactly what Costa's prose says ("the value of the capacitor
# increases exponentially as the spacer thickness is reduced").
#
# In plain terms: the closer the printed pattern sits to the metal behind
# it, the more extra charge builds up between the two, and that extra
# charge makes the surface resonate LOWER than the uncorrected model draws
# it. At this programme's #128 design point (6.0 mm period, 1.50 mm spacer)
# the uncorrected model was drawing the resonance about 1% too high.
#
# TWO PUBLISHED FORMS, ONE UNRESOLVED (#234) -- AND THEY DIFFER IN WHERE THE
# CORRECTION IS APPLIED, NOT ONLY IN ITS PREFACTOR.
#
#   "eps0" -- Costa et al. 2013 (arXiv:1211.1902 eq 10), read off a 400 dpi
#   render and confirmed at 22x through a second rasteriser. The prefactor is
#   `2*D*eps_0/pi` and the correction substitutes into the UNLOADED C0; eq (6)
#   then loads the corrected sum. Net effect on the loaded capacitance is
#   `eps_eff * delta`.
#
#   "eps0_epsr" -- Costa & Borgese 2021 (arXiv:2102.10666, eqs 9-10, taken
#   from the authors' own LaTeX source, so verbatim rather than inferred).
#   The prefactor is `2*D*eps_0*eps_r/pi` and the correction is subtracted
#   from an ALREADY-LOADED capacitance (their C_patch already carries
#   eps_eff), so it is never multiplied by eps_eff. Net effect on the loaded
#   capacitance is `eps_r * delta`.
#
# So the real disagreement between the two papers is a factor of
# `eps_r / eps_eff` -- 1.487 at eps_r = 2.9, not eps_r itself. Reading the
# 2021 prefactor as a straight eps_r multiplier applied at the 2013 paper's
# composition point would give `eps_eff * eps_r * delta` and count the
# permittivity twice; `_thin_spacer_composed_capacitance` below exists to
# make that mistake impossible to make by accident.
#
# The 2021 placement is physically coherent, and worth stating because it is
# not an arbitrary difference: the correction is a patch-to-GROUND
# capacitance, whose field sits entirely inside the substrate, so it carries
# eps_r; the gap capacitance between neighbouring patches straddles air and
# substrate, so it carries eps_eff = (eps_r + 1)/2. That asymmetry is an
# argument in the 2021 form's favour. It is not a verdict -- which form is
# right is #234, and neither can be checked against the original, Tretyakov
# & Simovski 2003, which is closed access with no repository copy in
# existence (RUNNING-LISTS.md section 1). Both are carried, and the
# conservative `eps0` form is the default.
#
# PROVENANCE: INFERRED, not LITERATURE-SUPPORTED, for the 2013 form -- the
# functional form is corroborated four ways (machine-readable text layer,
# two independent renderers, a separate publication, and an R^2 = 0.99902
# fit to the source's own Figure 2(b)), but it was still ultimately read by
# eye off a rasterised page. The 2021 restatement is LITERATURE-SUPPORTED:
# it comes from the arXiv LaTeX source. See
# docs/costa-thin-spacer-correction.md.

COSTA_EQ10_FORMS = ("eps0", "eps0_epsr")
"""The two published statements of Costa eq (10). See #234.

Each name is a whole form -- prefactor AND composition point -- because the
two papers differ in both, which is why these are `..._FORMS` and not
`..._PREFACTORS`. `_compose_thin_spacer_
capacitance` is where the second half of that distinction lives.
"""

COSTA_EQ10_FORM = "eps0"
"""Which of the two forms this programme uses. Module-level, deliberately.

Settling #234 is a one-line change here. It is NOT a per-call argument on
the public absorber API, and must not become one: a caller free to vary the
prefactor design-by-design could quietly pick whichever form flatters the
candidate in front of them, which is a thumb on the scale.
"""


def _resolve_thin_spacer_form(form: str | None) -> str:
    """`None` means the module-level selection; anything unrecognised is an
    error rather than a silent fall-back to the default."""
    resolved = COSTA_EQ10_FORM if form is None else form
    if resolved not in COSTA_EQ10_FORMS:
        raise ValueError(
            f"Unknown eq (10) form {form!r}; expected one of {COSTA_EQ10_FORMS} (see #234)."
        )
    return resolved


def _compose_thin_spacer_capacitance(
    unloaded_c0_f: float, correction_f: float, eps_r: float, form: str
) -> float:
    """Combine an unloaded grid capacitance with its thin-spacer correction
    AT THE POINT THE CHOSEN PUBLISHED FORM APPLIES IT.

        "eps0"      -> eps_eff * (C0 + dC)     dC = (2p*eps_0/pi)*Lterm
        "eps0_epsr" -> eps_eff * C0 + dC       dC = eps_r * (2p*eps_0/pi)*Lterm

    This function exists for one reason: the two forms are NOT related by a
    scalar. Costa 2013 corrects the unloaded capacitance and then loads the
    sum; Costa & Borgese 2021 correct an already-loaded capacitance, so their
    term never meets eps_eff. Net effect on the loaded value is `eps_eff*dC0`
    for the first and `eps_r*dC0` for the second, where dC0 is the bare
    `(2p*eps_0/pi)*Lterm` quantity.

    Reading the 2021 prefactor as "eps_r times the 2013 correction" and then
    applying it at the 2013 composition point gives `eps_eff*eps_r*dC0` --
    the permittivity counted twice, and an overstated correction. Keeping
    the composition here, keyed off the same name that chose the prefactor,
    is what makes that mistake impossible to make by accident.

    *In plain terms: the two papers disagree about how much of the substrate
    the extra charge sits in. Getting that wrong once is a 50% error in the
    correction; getting it wrong twice over is a 190% one.*
    """
    eps_eff = grid_effective_permittivity(eps_r)
    if form == "eps0":
        return eps_eff * (unloaded_c0_f + correction_f)
    return eps_eff * unloaded_c0_f + correction_f


def thin_spacer_capacitance_correction_f(
    period_m: float,
    spacer_thickness_m: float,
    eps_r: float,
    form: str | None = None,
) -> float:
    """The extra sheet capacitance (F per square) a nearby ground plane adds.

        dC = (2p * eps_0 / pi) * -ln(1 - exp(-4*pi*d / p))          "eps0"
        dC = (2p * eps_0 * eps_r / pi) * -ln(1 - exp(-4*pi*d / p))  "eps0_epsr"

    Costa, Genovesi, Monorchio & Manara, arXiv:1211.1902 eq (10) (published
    IEEE TAP 61(3), 1201-1209). `period_m` is Costa's D, the FSS repeat
    distance; `spacer_thickness_m` is his d, the dielectric between the
    printed pattern and the ground plane. The ratio that matters is d/p --
    spacer thickness over CELL PERIOD, not over wavelength; eq (10) has no
    frequency in it at all.

    THE TWO FORMS ARE APPLIED AT DIFFERENT POINTS, and this function returns
    only the term -- `_compose_thin_spacer_capacitance` decides where it
    lands, and `capacitive_grid_sheet_capacitance_f` is the caller that does
    both together. Taking the "eps0_epsr" return and pushing it through the
    "eps0" composition would count the permittivity twice.

      - "eps0" (Costa 2013): corrects the UNLOADED capacitance -- free
        space, no substrate loading -- and Costa's eq (6) loading,
        eps_eff = (eps_r + 1)/2, is applied to the corrected sum afterwards.
        Net effect on the loaded capacitance: `eps_eff` times this return.
      - "eps0_epsr" (Costa & Borgese 2021): corrects an ALREADY-LOADED
        capacitance, so this return is added as-is and never meets eps_eff.
        Net effect on the loaded capacitance: exactly this return.

    So the two published answers differ by `eps_r / eps_eff` on the loaded
    capacitance -- 1.487 at eps_r = 2.9 -- not by `eps_r`.

    The 2021 placement has a physical argument behind it, worth stating
    because the difference is not arbitrary: this correction is a
    patch-to-GROUND capacitance whose field sits entirely inside the
    substrate, so eps_r is the permittivity it should see, whereas the gap
    capacitance between neighbouring patches straddles air and substrate and
    so sees eps_eff. That is a reason to prefer the 2021 form, not a verdict
    on it; which is right is #234, and "eps0" stays the conservative default.

    The return is always >= 0 and falls monotonically as the spacer thickens:
    at d/p = 0.25 it is ~2.2% of C0, at d/p = 0.5 under 0.1%, and it tends to
    zero rather than reaching it.

    *In plain terms: how much extra electrical charge the printed pattern
    stores because there is metal close behind it. More stored charge means
    the surface resonates lower, so leaving this term out draws the
    resonance too high.*

    NOT GATED AT d/p = 0.3, deliberately. Costa writes the regime boundary
    as `if (d > 0.3D)` inside eq (6), but eq (10) itself decays smoothly and
    is a strictly better approximation on both sides of that ratio. Gating
    it would put a step discontinuity in the capacitance at exactly the
    ratio this programme's designs cluster around, which is an optimiser
    hazard with nothing physical behind it. This is a reasoned deviation
    from a literal reading of the paper, not an oversight (#245).

    `form` selects between the two published forms (#234) and defaults
    to the module-level `COSTA_EQ10_FORM`. As a bare term, the "eps0"
    form does not depend on `eps_r` and the "eps0_epsr" form is exactly
    `eps_r` times it -- but see above: they do not land in the same place.
    """
    p = _require_positive_length("period_m", period_m)
    d = _require_positive_length("spacer_thickness_m", spacer_thickness_m)
    if eps_r < 1:
        raise ValueError(f"eps_r must be >= 1; got {eps_r!r}.")
    form = _resolve_thin_spacer_form(form)
    permittivity = EPS0 if form == "eps0" else EPS0 * eps_r
    log_term = -math.log1p(-math.exp(-4 * math.pi * d / p))
    return (2 * p * permittivity / math.pi) * log_term


def capacitive_grid_sheet_capacitance_f(
    period_m: float,
    gap_m: float,
    eps_r: float,
    spacer_thickness_m: float | None = None,
    form: str | None = None,
) -> float:
    """Sheet capacitance (farads per square) of a capacitive patch grid.

        C = eps_0 * eps_eff * (2p / pi) * ln(1 / sin(pi*g / 2p))

    Luukkonen's grid capacitance, as used by Costa et al. and adopted in
    #111. `gap_m` must be less than `period_m`: the gap is the space
    between adjacent patches within one period, not the period itself.

    `spacer_thickness_m` is OPTIONAL and describes a ground plane sitting
    that far behind the grid. Given, Costa's thin-spacer correction (eq 10,
    `thin_spacer_capacitance_correction_f`, #245) is applied -- at the point
    the selected form applies it, which is the whole of
    `_compose_thin_spacer_capacitance`:

        "eps0"      C = eps_eff * (C0_unloaded + dC)   Costa 2013, the default
        "eps0_epsr" C = eps_eff * C0_unloaded + dC     Costa & Borgese 2021

    Under "eps0" the correction is a free-space quantity that eq (6) then
    loads; under "eps0_epsr" it already carries eps_r and is added to an
    already-loaded capacitance. Mixing the two -- loading the eps_r-bearing
    term as well -- counts the permittivity twice and is the easiest thing
    to get wrong here.

    Omitted (the default), the returned value is bit-for-bit the
    free-standing result it has always been -- the Babinet dual test and
    every caller with no ground plane behind the grid are untouched.
    """
    p = _require_positive_length("period_m", period_m)
    g = _require_positive_length("gap_m", gap_m)
    if g >= p:
        raise ValueError(
            f"gap_m must be smaller than period_m (the gap sits inside one "
            f"period); got gap_m={g!r}, period_m={p!r}."
        )
    eps_eff = grid_effective_permittivity(eps_r)
    s = math.sin(math.pi * g / (2 * p))
    log_factor = math.log(1 / s)
    if spacer_thickness_m is None:
        # The original expression, verbatim and in its original association
        # order. Factoring eps_eff out of it to share a code path with the
        # corrected branch below would move the rounding by one bit on some
        # inputs, and "bit-for-bit unchanged" above is meant literally.
        return EPS0 * eps_eff * (2 * p / math.pi) * log_factor
    form = _resolve_thin_spacer_form(form)
    unloaded = EPS0 * (2 * p / math.pi) * log_factor
    correction = thin_spacer_capacitance_correction_f(p, spacer_thickness_m, eps_r, form)
    return _compose_thin_spacer_capacitance(unloaded, correction, eps_r, form)


def inductive_grid_sheet_inductance_h(period_m: float, strip_width_m: float) -> float:
    """Sheet inductance (henries per square) of an inductive wire/loop grid --
    the exact Babinet dual of `capacitive_grid_sheet_capacitance_f`.

        L = mu_0 * (p / 2pi) * ln(1 / sin(pi*w / 2p))

    A ring or loop element carries this in series with its capacitance,
    where a plain patch element carries none. That difference is not
    cosmetic: a 0.5 mm trace on a 9 mm period is 4.39 nH/sq, which is an
    order of magnitude more inductance than a same-period absorber design
    tolerates before it stops meeting its absorption target at all (see
    docs/supercell-ring-inductance-bench.md).
    """
    p = _require_positive_length("period_m", period_m)
    w = _require_positive_length("strip_width_m", strip_width_m)
    if w >= p:
        raise ValueError(
            f"strip_width_m must be smaller than period_m; got strip_width_m={w!r}, period_m={p!r}."
        )
    s = math.sin(math.pi * w / (2 * p))
    return MU0 * (p / (2 * math.pi)) * math.log(1 / s)


def _require_positive_length(name: str, value: float) -> float:
    if not math.isfinite(value) or value <= 0:
        raise ValueError(f"{name} must be a positive finite number of metres; got {value!r}.")
    return float(value)


# --- The squares rule (issue #128) ---
#
# What a wave sees is not an ink's conductivity. It is the ink's SHEET
# RESISTANCE multiplied by the number of SQUARES the current path traverses
# -- and the squares count is a pure shape ratio, so it is scale-invariant:
# the same pattern shrunk to a tenth the size has the same squares count and
# therefore the same resistance at the same sheet resistance.
#
# This is why an apparently empty gap in an ink catalogue is not a wall.
# Between a carbon ink at hundreds of ohms/sq and a silver at milliohms/sq
# there can be four orders of magnitude with nothing in it, and geometry
# spans that gap: one ink at 250-1000 ohm/sq reaches an effective loop
# resistance from tens of ohms to tens of kilohms purely by how many squares
# the designer draws.


def squares_count(path_length_m: float, path_width_m: float) -> float:
    """Number of squares in a uniform conductive path: length / width.

    Dimensionless and scale-invariant -- doubling both dimensions leaves it
    unchanged, which is exactly why a squares figure transfers between a
    published design at one frequency and the same shape scaled to another.
    """
    length = _require_positive_length("path_length_m", path_length_m)
    width = _require_positive_length("path_width_m", path_width_m)
    return length / width


def path_resistance_from_squares(sheet_resistance_ohm_sq: float, squares: float) -> float:
    """End-to-end resistance of a printed path: R = R_sheet * N_squares."""
    if sheet_resistance_ohm_sq < 0:
        raise ValueError(
            f"sheet_resistance_ohm_sq must be non-negative; got {sheet_resistance_ohm_sq!r}."
        )
    if squares <= 0:
        raise ValueError(f"squares must be positive; got {squares!r}.")
    return sheet_resistance_ohm_sq * squares


def sheet_resistance_for_target_path_resistance(
    target_resistance_ohm: float, squares: float
) -> float:
    """The sheet resistance an ink must have for a given shape to reach a
    target path resistance -- the inverse of `path_resistance_from_squares`,
    and the form a designer actually needs when choosing an ink for a
    drawn geometry.
    """
    if target_resistance_ohm <= 0:
        raise ValueError(f"target_resistance_ohm must be positive; got {target_resistance_ohm!r}.")
    if squares <= 0:
        raise ValueError(f"squares must be positive; got {squares!r}.")
    return target_resistance_ohm / squares


# --- Resistive overlay: the multispectral continuity threshold ---
#
# A second, IR-functional layer laid over a matched microwave absorber acts
# as a shunt sheet across the absorber's input. A CONTINUOUS conductive film
# shorts it out; the SAME metal cut into a sub-wavelength grid is invisible
# at microwave frequencies, because its period is thousands of times smaller
# than the wavelength that matters. So the multispectral conflict is not
# material-versus-material -- it is continuous-versus-patterned, and it has
# a number.
#
# For a shunt sheet R_s across a matched absorber presenting Z_0:
#
#     Gamma = -Z_0 / (2*R_s + Z_0),   A = 1 - |Gamma|^2
#
# which inverts to the minimum R_s that leaves a target absorption intact.


def min_overlay_sheet_resistance_ohm_sq(
    target_absorption: float, z0_ohm: float = 376.730313412
) -> float:
    """Lowest sheet resistance a resistive overlay may have while still
    leaving `target_absorption` (0..1) intact on a matched absorber beneath.

        R_s,min = (Z_0 / 2) * (1 / sqrt(1 - A) - 1)

    Returns 407.3 ohm/sq for a 90 % absorption floor and 1695.3 ohm/sq for
    99 % -- the thresholds that turn "will an IR layer ruin the radar
    absorber?" from a hand-wave into a design rule. An overlay BELOW the
    returned value degrades the absorber; above it, the absorber survives.

    SCOPE: THIS MODEL IS RESISTIVE-ONLY, AND THAT MAKES PASSING IT NECESSARY
    BUT NOT SUFFICIENT. `Gamma = -Z_0/(2*R_s+Z_0)` treats the overlay as a
    pure resistance R_s with no reactive part -- true for a uniform,
    non-resonant conductive film, but NOT true for a resonant PATTERNED
    overlay (an FSS, a metal grid tuned near a wavelength): that is a complex
    sheet ADMITTANCE Y = G + jB, and this closed form has no term for the
    susceptance B. A real patterned layer can clear this function's
    resistance floor by an order of magnitude and still fail the absorption
    target on susceptance alone -- the general case needs the full two-port
    ABCD/S-parameter cascade in `rf_tools/transmissive_absorber.py`
    (`shunt_sheet_abcd` takes a complex admittance; `cascade`/`s_parameters`
    turn it into reflection and transmission), not this formula.

    WORKED COUNTER-EXAMPLE, from a measured screen-printed Ti3C2Tx MXene
    chessboard FSS: transmittance T = 0.78, reflectance R = 0.16, so
    A = 1 - T - R = 0.06 is dissipated in the sheet itself. The equivalent
    lumped shunt admittance that reproduces those three numbers is
    y = 0.077 + j0.90 (normalized to Y_0 = 1/Z_0) -- check:
    4*Re(y)/|y+2|^2 = 0.0601, matching the measured A = 0.06. Read only
    Re(y), the sheet looks like a Z_0/Re(y) = ~4,893 ohm/sq resistor --
    twelve times this function's own 407 ohm/sq floor for a 90 % target, so
    a resistive-only check would wave it through, and a TRULY resistive
    4,893 ohm/sq sheet placed over a matched absorber would indeed leave
    99.86 % absorption intact. But this sheet is not purely resistive:
    carrying its actual susceptance of 0.90*Y_0 over that same matched
    absorber (Gamma = -y/(y+2) with the full complex y) leaves only
    1 - |Gamma|^2 = 84.1 % absorption -- below the 90 % floor this function
    exists to guarantee. In plain terms: this number only answers "is the
    sheet resistive enough" -- it says nothing about whether the sheet is
    also reactive enough to detune the absorber underneath it, and a
    patterned overlay that passes with room to spare can still ruin the
    absorber it sits on.
    """
    if not 0 < target_absorption < 1:
        raise ValueError(
            f"target_absorption must be strictly between 0 and 1; got {target_absorption!r}."
        )
    if z0_ohm <= 0:
        raise ValueError(f"z0_ohm must be positive; got {z0_ohm!r}.")
    gamma_mag = math.sqrt(1 - target_absorption)
    return (z0_ohm / 2) * (1 / gamma_mag - 1)


# --- Sheet resistance from conductivity: derive, never store ---
#
# A printed conductor's sheet resistance is NOT a stored property of an ink.
# It depends on the deposited thickness and, at microwave frequencies, on
# how that thickness compares to the skin depth -- so it must be derived
# from sigma and t through a function that carries its own frequency gate,
# never entered into a library as a number.
#
# THE ERROR THIS FUNCTION EXISTS TO PREVENT. The DC expression
# R_s = 1/(sigma*t) is correct only while the film is much THINNER than a
# skin depth. Applied at 10 GHz to a film several skin depths thick it
# understates the sheet resistance, because the current is not using the
# whole cross-section: it is crowded into the top few micrometres. This
# repo has made that exact substitution more than once, which is why the
# gate is inside the function rather than in a comment beside it.
#
# IN PLAIN TERMS: at high frequencies current only flows in a thin skin at
# the surface of a conductor. Making the film thicker past that skin stops
# helping, so a formula that keeps rewarding thickness gives an answer
# that is too good.


def skin_depth_m(frequency_hz: float, conductivity_s_m: float, mu_r: float = 1.0) -> float:
    """Classical skin depth of a good conductor:

        delta = 1 / sqrt(pi * f * mu * sigma)

    The depth at which the current density has fallen to 1/e of its surface
    value. `mu_r` defaults to 1.0 (non-magnetic), correct for every printed
    silver, copper, carbon and MXene ink.
    """
    f = _require_positive_length("frequency_hz", frequency_hz)
    sigma = _require_positive_length("conductivity_s_m", conductivity_s_m)
    if mu_r <= 0:
        raise ValueError(f"mu_r must be positive; got {mu_r!r}.")
    return 1.0 / math.sqrt(math.pi * f * MU0 * mu_r * sigma)


def sheet_resistance_dc_ohm_sq(conductivity_s_m: float, thickness_m: float) -> float:
    """DC sheet resistance, R_s = 1 / (sigma * t).

    VALID ONLY where the film is thin compared to a skin depth. Use
    `sheet_resistance_ohm_sq` instead for anything at RF -- it computes this
    same value where it applies and the correct one where it does not.
    """
    sigma = _require_positive_length("conductivity_s_m", conductivity_s_m)
    t = _require_positive_length("thickness_m", thickness_m)
    return 1.0 / (sigma * t)


def sheet_resistance_ohm_sq(
    conductivity_s_m: float,
    thickness_m: float,
    frequency_hz: float | None = None,
    mu_r: float = 1.0,
) -> float:
    """Sheet resistance of a conductive film, correct at both DC and RF.

    With `frequency_hz` omitted this is the DC expression 1/(sigma*t). With
    a frequency supplied it is the real part of the surface impedance of a
    film of finite thickness,

        Z_s = (1 + j) / (sigma * delta) * coth((1 + j) * t / delta)

    which reduces to 1/(sigma*t) for t << delta and to 1/(sigma*delta) for
    t >> delta -- so a caller never has to decide which regime they are in.
    Passing the frequency is always the safer call; the two agree wherever
    the DC form is valid.
    """
    sigma = _require_positive_length("conductivity_s_m", conductivity_s_m)
    t = _require_positive_length("thickness_m", thickness_m)
    if frequency_hz is None:
        return 1.0 / (sigma * t)
    delta = skin_depth_m(frequency_hz, sigma, mu_r)
    arg = complex(1.0, 1.0) * t / delta
    # coth(z) = cosh(z)/sinh(z); for large |z| this saturates at 1, which is
    # the t >> delta limit. Guard the overflow explicitly rather than relying
    # on cmath to stay finite for a very thick film.
    if abs(arg) > 30:
        coth = complex(1.0, 0.0)
    else:
        coth = cmath.cosh(arg) / cmath.sinh(arg)
    return (complex(1.0, 1.0) / (sigma * delta) * coth).real


def skin_depths_of_thickness(
    thickness_m: float, frequency_hz: float, conductivity_s_m: float, mu_r: float = 1.0
) -> float:
    """How many skin depths thick a film is at a given frequency -- the
    number that decides whether the DC sheet-resistance formula applies.

    Below ~0.3 the DC form is safe; above ~2 the film behaves as a
    half-space and extra thickness buys nothing. In between, use
    `sheet_resistance_ohm_sq` with a frequency and do not approximate.
    """
    return _require_positive_length("thickness_m", thickness_m) / skin_depth_m(
        frequency_hz, conductivity_s_m, mu_r
    )
