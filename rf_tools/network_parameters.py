from math import log10

import numpy as np


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
