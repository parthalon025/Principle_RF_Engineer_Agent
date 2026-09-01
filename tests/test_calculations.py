import pytest

from rf_tools.calculations import (
    cascade_gain_db,
    friis_noise_factor,
    return_loss_db,
    vswr_from_gamma,
    wavelength,
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
