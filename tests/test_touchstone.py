from pathlib import Path

import numpy as np
import pytest
import skrf as rf

from rf_tools.touchstone import analyze_touchstone, deembed_touchstone, interpolate_touchstone

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


def _make_lossy_two_port(
    freqs_hz: np.ndarray,
    *,
    reflection: complex,
    insertion_loss_mag: float,
    length_m: float,
    er: float = 1.0,
) -> rf.Network:
    """A synthetic reciprocal, symmetric 2-port with constant reflection and
    a lossy, phase-shifting through path -- distinct "fixture" and "DUT"
    networks are built from this with different parameter values so that
    a fixture and a DUT never coincidentally have the same response.
    """
    s21 = insertion_loss_mag * _lossless_line_s21(freqs_hz, length_m, er)
    s = np.zeros((len(freqs_hz), 2, 2), dtype=complex)
    s[:, 0, 0] = reflection
    s[:, 1, 1] = reflection
    s[:, 1, 0] = s21
    s[:, 0, 1] = s21
    freq = rf.Frequency.from_f(freqs_hz, unit="hz")
    return rf.Network(frequency=freq, s=s, z0=50)


def _write_network(ntwk: rf.Network, tmp_path: Path, name: str) -> Path:
    path = tmp_path / f"{name}.s2p"
    ntwk.write_touchstone(path.with_suffix(""))
    return path


def test_deembed_touchstone_recovers_known_dut(tmp_path: Path):
    freqs_hz = np.linspace(1e9, 5e9, 9)
    fixture = _make_lossy_two_port(
        freqs_hz, reflection=0.05 + 0.02j, insertion_loss_mag=0.9, length_m=0.01
    )
    dut = _make_lossy_two_port(
        freqs_hz, reflection=0.1 - 0.03j, insertion_loss_mag=0.3, length_m=0.03
    )
    measured = fixture**dut

    fixture_path = _write_network(fixture, tmp_path, "fixture")
    measured_path = _write_network(measured, tmp_path, "measured")

    result = deembed_touchstone(str(measured_path), str(fixture_path))

    assert isinstance(result, rf.Network)
    np.testing.assert_allclose(result.s, dut.s, atol=1e-6)


def test_deembed_touchstone_symmetric_two_sided(tmp_path: Path):
    freqs_hz = np.linspace(2e9, 6e9, 7)
    fixture = _make_lossy_two_port(
        freqs_hz, reflection=0.07 + 0.01j, insertion_loss_mag=0.85, length_m=0.02
    )
    dut = _make_lossy_two_port(
        freqs_hz, reflection=0.15 - 0.05j, insertion_loss_mag=0.4, length_m=0.015
    )
    measured = fixture**dut**fixture

    fixture_path = _write_network(fixture, tmp_path, "fixture_sym")
    measured_path = _write_network(measured, tmp_path, "measured_sym")

    result = deembed_touchstone(str(measured_path), str(fixture_path), str(fixture_path))

    assert isinstance(result, rf.Network)
    np.testing.assert_allclose(result.s, dut.s, atol=1e-6)


def test_deembed_touchstone_two_different_fixtures(tmp_path: Path):
    freqs_hz = np.linspace(1e9, 4e9, 6)
    fixture_a = _make_lossy_two_port(
        freqs_hz, reflection=0.05 + 0.02j, insertion_loss_mag=0.9, length_m=0.01
    )
    fixture_b = _make_lossy_two_port(
        freqs_hz, reflection=0.02 - 0.04j, insertion_loss_mag=0.8, length_m=0.02
    )
    dut = _make_lossy_two_port(
        freqs_hz, reflection=0.1 - 0.03j, insertion_loss_mag=0.3, length_m=0.03
    )
    measured = fixture_a**dut**fixture_b

    fixture_a_path = _write_network(fixture_a, tmp_path, "fixture_a")
    fixture_b_path = _write_network(fixture_b, tmp_path, "fixture_b")
    measured_path = _write_network(measured, tmp_path, "measured_ab")

    result = deembed_touchstone(str(measured_path), str(fixture_a_path), str(fixture_b_path))

    assert isinstance(result, rf.Network)
    np.testing.assert_allclose(result.s, dut.s, atol=1e-6)


def test_deembed_touchstone_singular_fixture_raises_value_error(tmp_path: Path):
    freqs_hz = np.linspace(1e9, 3e9, 3)
    s = np.zeros((3, 2, 2), dtype=complex)
    s[:, 1, 0] = [0.5, 0.0, 0.5]  # zero transmission at the middle point
    s[:, 0, 1] = [0.5, 0.0, 0.5]
    freq = rf.Frequency.from_f(freqs_hz, unit="hz")
    singular_fixture = rf.Network(frequency=freq, s=s, z0=50)

    dut = _make_lossy_two_port(
        freqs_hz, reflection=0.1 - 0.03j, insertion_loss_mag=0.3, length_m=0.03
    )
    measured = singular_fixture**dut

    fixture_path = _write_network(singular_fixture, tmp_path, "singular_fixture")
    measured_path = _write_network(measured, tmp_path, "measured_singular")

    with pytest.raises(ValueError, match="singular"):
        deembed_touchstone(str(measured_path), str(fixture_path))


def test_deembed_touchstone_missing_measured_file(tmp_path: Path):
    freqs_hz = np.linspace(1e9, 3e9, 3)
    fixture = _make_lossy_two_port(
        freqs_hz, reflection=0.05 + 0.02j, insertion_loss_mag=0.9, length_m=0.01
    )
    fixture_path = _write_network(fixture, tmp_path, "fixture_missing_measured")

    with pytest.raises(FileNotFoundError):
        deembed_touchstone(str(tmp_path / "missing.s2p"), str(fixture_path))


def test_deembed_touchstone_missing_fixture_file(tmp_path: Path):
    freqs_hz = np.linspace(1e9, 3e9, 3)
    dut = _make_lossy_two_port(
        freqs_hz, reflection=0.1 - 0.03j, insertion_loss_mag=0.3, length_m=0.03
    )
    measured_path = _write_network(dut, tmp_path, "measured_missing_fixture")

    with pytest.raises(FileNotFoundError):
        deembed_touchstone(str(measured_path), str(tmp_path / "missing.s2p"))
