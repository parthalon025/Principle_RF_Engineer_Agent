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
