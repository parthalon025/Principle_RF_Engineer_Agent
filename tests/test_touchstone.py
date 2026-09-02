from pathlib import Path

import numpy as np
import pytest
import skrf as rf

from rf_tools.touchstone import analyze_touchstone, interpolate_touchstone

C0 = 299792458.0  # speed of light, m/s


def test_touchstone(tmp_path: Path):
    f = rf.Frequency(1, 3, 3, unit="ghz")
    s = np.zeros((3, 2, 2), dtype=complex)
    s[:, 0, 0] = 10 ** (-20 / 20)
    s[:, 1, 0] = 10 ** (-3 / 20)
    ntwk = rf.Network(frequency=f, s=s, z0=50)
    path = tmp_path / "test.s2p"
    ntwk.write_touchstone(path.with_suffix(""))

    result = analyze_touchstone(str(path))
    assert result["ports"] == 2
    assert result["s11_min_db"] == pytest.approx(-20.0)


def _lossless_line_s21(freqs_hz: np.ndarray, length_m: float, er: float = 1.0) -> np.ndarray:
    """Closed-form S21 of a matched, lossless transmission line.

    For a line perfectly matched at both ports, S11 = S22 = 0 and
    S21 = S12 = exp(-j*beta*length), with beta = 2*pi*f*sqrt(er)/c0.
    """
    beta = 2 * np.pi * freqs_hz * np.sqrt(er) / C0
    return np.exp(-1j * beta * length_m)


def _write_matched_line_touchstone(
    tmp_path: Path, freqs_hz: np.ndarray, length_m: float, er: float = 1.0
) -> Path:
    s = np.zeros((len(freqs_hz), 2, 2), dtype=complex)
    s21 = _lossless_line_s21(freqs_hz, length_m, er)
    s[:, 1, 0] = s21
    s[:, 0, 1] = s21
    freq = rf.Frequency.from_f(freqs_hz, unit="hz")
    ntwk = rf.Network(frequency=freq, s=s, z0=50)
    path = tmp_path / "line.s2p"
    ntwk.write_touchstone(path.with_suffix(""))
    return path


def test_interpolate_touchstone_matches_closed_form(tmp_path: Path):
    length_m = 0.05
    f_src = np.linspace(1e9, 5e9, 9)  # sparse source grid, 9 points, 1-5 GHz
    path = _write_matched_line_touchstone(tmp_path, f_src, length_m)

    f_target = np.linspace(1.3e9, 4.7e9, 15)  # denser grid, strictly inside source range
    result = interpolate_touchstone(str(path), f_target.tolist())

    assert isinstance(result, rf.Network)
    np.testing.assert_allclose(result.f, f_target, rtol=1e-9)

    expected_s21 = _lossless_line_s21(f_target, length_m)
    np.testing.assert_allclose(result.s[:, 1, 0], expected_s21, atol=1e-9)
    # matched line: S11 stays ~0 throughout
    np.testing.assert_allclose(result.s[:, 0, 0], 0.0, atol=1e-9)


def test_interpolate_touchstone_rejects_extrapolation(tmp_path: Path):
    length_m = 0.05
    f_src = np.linspace(1e9, 5e9, 9)
    path = _write_matched_line_touchstone(tmp_path, f_src, length_m)

    # 6 GHz is above the source network's 5 GHz upper bound.
    f_target = [2e9, 3e9, 6e9]
    with pytest.raises(ValueError):
        interpolate_touchstone(str(path), f_target)


def test_interpolate_touchstone_missing_file(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        interpolate_touchstone(str(tmp_path / "missing.s2p"), [2e9])
