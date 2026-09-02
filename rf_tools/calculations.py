from math import log10, sin

import numpy as np


def wavelength(f_hz: float, c_m_s: float = 299_792_458.0) -> float:
    if f_hz <= 0:
        raise ValueError("Frequency must be positive.")
    return c_m_s / f_hz


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
        raise ValueError(
            "Output stability circle is undefined when |S22|^2 = |Delta|^2."
        )
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
        raise ValueError(
            "Input stability circle is undefined when |S11|^2 = |Delta|^2."
        )
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
        raise ValueError("Substrate dielectric constant eps_r must be > 1.")
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
        0.412
        * h_m
        * (eps_eff + 0.3)
        * (w_over_h + 0.264)
        / ((eps_eff - 0.258) * (w_over_h + 0.8))
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
