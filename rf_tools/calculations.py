from math import log10

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
