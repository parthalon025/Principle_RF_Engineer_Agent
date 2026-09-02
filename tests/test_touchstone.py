from pathlib import Path

import numpy as np
import pytest
import skrf as rf

from rf_tools.touchstone import (
    analyze_touchstone,
    cascade_touchstone,
    compare_touchstone,
    deembed_touchstone,
    interpolate_touchstone,
)

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
    tmp_path: Path, freqs_hz: np.ndarray, length_m: float, er: float = 1.0, name: str = "line"
) -> Path:
    s = np.zeros((len(freqs_hz), 2, 2), dtype=complex)
    s21 = _lossless_line_s21(freqs_hz, length_m, er)
    s[:, 1, 0] = s21
    s[:, 0, 1] = s21
    freq = rf.Frequency.from_f(freqs_hz, unit="hz")
    ntwk = rf.Network(frequency=freq, s=s, z0=50)
    path = tmp_path / f"{name}.s2p"
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


def _make_matched_attenuator(freqs_hz: np.ndarray, atten_db: float, z0: float = 50) -> rf.Network:
    """A synthetic matched attenuator: S11 = S22 = 0, S21 = S12 = 10**(-atten_db/20)."""
    s = np.zeros((len(freqs_hz), 2, 2), dtype=complex)
    s21 = 10 ** (-atten_db / 20)
    s[:, 1, 0] = s21
    s[:, 0, 1] = s21
    freq = rf.Frequency.from_f(freqs_hz, unit="hz")
    return rf.Network(frequency=freq, s=s, z0=z0)


def test_cascade_touchstone_two_matched_attenuators(tmp_path: Path):
    freqs_hz = np.linspace(1e9, 5e9, 9)
    atten_a_db = 3.0
    atten_b_db = 6.0
    a = _make_matched_attenuator(freqs_hz, atten_a_db)
    b = _make_matched_attenuator(freqs_hz, atten_b_db)

    path_a = _write_network(a, tmp_path, "atten_a")
    path_b = _write_network(b, tmp_path, "atten_b")

    result = cascade_touchstone([str(path_a), str(path_b)])

    assert isinstance(result, rf.Network)
    expected_s21 = 10 ** (-(atten_a_db + atten_b_db) / 20)
    np.testing.assert_allclose(np.abs(result.s[:, 1, 0]), expected_s21, atol=1e-9)
    np.testing.assert_allclose(result.s[:, 0, 0], 0.0, atol=1e-9)
    np.testing.assert_allclose(result.s[:, 1, 1], 0.0, atol=1e-9)


def test_cascade_touchstone_three_or_more_networks(tmp_path: Path):
    freqs_hz = np.linspace(1e9, 5e9, 9)
    atten_db_values = [2.0, 4.0, 5.0, 1.5]
    paths = []
    for i, atten_db in enumerate(atten_db_values):
        ntwk = _make_matched_attenuator(freqs_hz, atten_db)
        paths.append(str(_write_network(ntwk, tmp_path, f"atten_{i}")))

    result = cascade_touchstone(paths)

    assert isinstance(result, rf.Network)
    expected_s21 = 10 ** (-sum(atten_db_values) / 20)
    np.testing.assert_allclose(np.abs(result.s[:, 1, 0]), expected_s21, atol=1e-9)
    np.testing.assert_allclose(result.s[:, 0, 0], 0.0, atol=1e-9)


def test_cascade_touchstone_mismatched_port_count_raises_value_error(tmp_path: Path):
    freqs_hz = np.linspace(1e9, 3e9, 3)
    two_port = _make_matched_attenuator(freqs_hz, 3.0)
    freq = rf.Frequency.from_f(freqs_hz, unit="hz")
    one_port = rf.Network(frequency=freq, s=np.zeros((3, 1, 1), dtype=complex), z0=50)

    two_port_path = _write_network(two_port, tmp_path, "two_port")
    one_port_path = tmp_path / "one_port.s1p"
    one_port.write_touchstone(one_port_path.with_suffix(""))

    with pytest.raises(ValueError, match="ports"):
        cascade_touchstone([str(two_port_path), str(one_port_path)])


def test_cascade_touchstone_mismatched_z0_raises_value_error(tmp_path: Path):
    freqs_hz = np.linspace(1e9, 3e9, 3)
    a = _make_matched_attenuator(freqs_hz, 3.0, z0=50)
    b = _make_matched_attenuator(freqs_hz, 6.0, z0=75)

    path_a = _write_network(a, tmp_path, "atten_z0_a")
    path_b = _write_network(b, tmp_path, "atten_z0_b")

    with pytest.raises(ValueError, match="z0"):
        cascade_touchstone([str(path_a), str(path_b)])


def test_cascade_touchstone_missing_file(tmp_path: Path):
    freqs_hz = np.linspace(1e9, 3e9, 3)
    a = _make_matched_attenuator(freqs_hz, 3.0)
    path_a = _write_network(a, tmp_path, "atten_missing")

    with pytest.raises(FileNotFoundError):
        cascade_touchstone([str(path_a), str(tmp_path / "missing.s2p")])


def test_compare_touchstone_known_1db_difference_same_grid(tmp_path: Path):
    freqs_hz = np.linspace(1e9, 5e9, 9)
    atten_a_db = 3.0
    atten_b_db = 4.0
    a = _make_matched_attenuator(freqs_hz, atten_a_db)
    b = _make_matched_attenuator(freqs_hz, atten_b_db)

    path_a = _write_network(a, tmp_path, "cmp_atten_a")
    path_b = _write_network(b, tmp_path, "cmp_atten_b")

    result = compare_touchstone(str(path_a), str(path_b))

    assert result["ports"] == 2
    np.testing.assert_allclose(result["common_frequencies_hz"], freqs_hz, rtol=1e-9)

    # S21 differs by exactly 1 dB (4 dB - 3 dB) at every frequency, hand-computable.
    s21 = result["s21"]
    np.testing.assert_allclose(s21["magnitude_diff_db"], -1.0, atol=1e-9)
    assert s21["max_magnitude_diff_db"] == pytest.approx(1.0, abs=1e-9)

    expected_s21_a = 10 ** (-atten_a_db / 20)
    expected_s21_b = 10 ** (-atten_b_db / 20)
    expected_abs_diff = abs(expected_s21_b - expected_s21_a)
    assert s21["rms_diff"] == pytest.approx(expected_abs_diff, abs=1e-9)
    assert s21["max_abs_diff"] == pytest.approx(expected_abs_diff, abs=1e-9)
    np.testing.assert_allclose(
        np.asarray(s21["diff"]), expected_s21_b - expected_s21_a, atol=1e-9
    )

    # Both attenuators are perfectly matched, so S11/S22 are identical (zero diff).
    for key in ("s11", "s22"):
        assert result[key]["rms_diff"] == pytest.approx(0.0, abs=1e-9)
        assert result[key]["max_abs_diff"] == pytest.approx(0.0, abs=1e-9)


def test_compare_touchstone_interpolates_onto_common_grid(tmp_path: Path):
    length_a_m = 0.05
    length_b_m = 0.06

    f_a = np.linspace(1e9, 5e9, 9)  # sparse: 0.5 GHz spacing, 1-5 GHz
    f_b = np.linspace(2e9, 4.5e9, 13)  # denser, different grid, narrower range

    path_a = _write_matched_line_touchstone(tmp_path, f_a, length_a_m, name="line_a")
    path_b = _write_matched_line_touchstone(tmp_path, f_b, length_b_m, name="line_b")

    result = compare_touchstone(str(path_a), str(path_b))

    # Common grid picks the sparser network's (a's) own points, restricted to the
    # overlap of both ranges: [2 GHz, 4.5 GHz] out of a's 0.5 GHz-spaced grid.
    expected_common_freqs = np.array([2e9, 2.5e9, 3e9, 3.5e9, 4e9, 4.5e9])
    np.testing.assert_allclose(
        result["common_frequencies_hz"], expected_common_freqs, rtol=1e-9
    )

    expected_s21_a = _lossless_line_s21(expected_common_freqs, length_a_m)
    expected_s21_b = _lossless_line_s21(expected_common_freqs, length_b_m)
    expected_diff = expected_s21_b - expected_s21_a

    s21 = result["s21"]
    np.testing.assert_allclose(np.asarray(s21["diff"]), expected_diff, atol=1e-9)
    assert s21["rms_diff"] == pytest.approx(
        float(np.sqrt(np.mean(np.abs(expected_diff) ** 2))), abs=1e-9
    )
    # Both lines are matched (S11 = S22 = 0), so those diffs are exactly zero.
    assert result["s11"]["rms_diff"] == pytest.approx(0.0, abs=1e-9)


def test_compare_touchstone_mismatched_port_count_raises_value_error(tmp_path: Path):
    freqs_hz = np.linspace(1e9, 3e9, 3)
    two_port = _make_matched_attenuator(freqs_hz, 3.0)
    freq = rf.Frequency.from_f(freqs_hz, unit="hz")
    one_port = rf.Network(frequency=freq, s=np.zeros((3, 1, 1), dtype=complex), z0=50)

    two_port_path = _write_network(two_port, tmp_path, "cmp_two_port")
    one_port_path = tmp_path / "cmp_one_port.s1p"
    one_port.write_touchstone(one_port_path.with_suffix(""))

    with pytest.raises(ValueError, match="ports"):
        compare_touchstone(str(two_port_path), str(one_port_path))


def test_compare_touchstone_no_overlapping_range_raises_value_error(tmp_path: Path):
    freqs_hz_a = np.linspace(1e9, 2e9, 5)
    freqs_hz_b = np.linspace(3e9, 4e9, 5)
    a = _make_matched_attenuator(freqs_hz_a, 3.0)
    b = _make_matched_attenuator(freqs_hz_b, 3.0)

    path_a = _write_network(a, tmp_path, "cmp_no_overlap_a")
    path_b = _write_network(b, tmp_path, "cmp_no_overlap_b")

    with pytest.raises(ValueError, match="overlap"):
        compare_touchstone(str(path_a), str(path_b))


def test_compare_touchstone_missing_file(tmp_path: Path):
    freqs_hz = np.linspace(1e9, 3e9, 3)
    a = _make_matched_attenuator(freqs_hz, 3.0)
    path_a = _write_network(a, tmp_path, "cmp_missing")

    with pytest.raises(FileNotFoundError):
        compare_touchstone(str(path_a), str(tmp_path / "missing.s2p"))
