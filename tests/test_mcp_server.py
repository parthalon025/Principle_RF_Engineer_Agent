"""Thin wiring tests for the MCP server (issue #36).

These tests confirm every Phase 1/2 calculation and Touchstone tool added in
issue #36 is registered on the MCP server, and that calling it (directly as
a Python function -- `@mcp.tool()`-decorated functions remain plain
callables) reaches the underlying `rf_tools` function correctly for at
least one representative input. They deliberately do NOT re-test the
underlying functions' own math -- that is already covered by
test_calculations.py and test_touchstone.py.
"""

import asyncio
from pathlib import Path

import numpy as np
import pytest
import skrf as rf

import mcp_server.server as server
from rf_tools.calculations import (
    abcd_to_s,
    aperture_gain,
    cascade_output_ip3_linear,
    curvature_length_correction_factor,
    curvature_shifted_resonant_frequency_hz,
    db_to_linear,
    fractional_bandwidth_from_q,
    free_space_path_loss_db,
    iip3_from_oip3_db,
    input_stability_circle,
    l_network_match,
    linear_to_db,
    link_budget_margin_db,
    maxwell_garnett_effective_permeability,
    oip3_from_iip3_db,
    output_stability_circle,
    patch_effective_permittivity,
    patch_length_extension_m,
    patch_resonant_frequency_hz,
    quality_factor_from_fractional_bandwidth,
    quarter_wave_transformer_impedance,
    rollett_k_factor,
    s_to_abcd,
    s_to_y,
    s_to_z,
    stability_verdict,
    third_order_intermod_dbc,
    third_order_intermod_output_dbm,
    two_port_stability_delta,
    y_to_s,
    z_to_s,
)

# A generic, well-behaved two-port S-parameter matrix (unconditionally
# stable amplifier-like response) reused across every S/Z/Y/ABCD/stability
# tool test below.
S_MATRIX = [[0.2 + 0.1j, 0.05], [1.5, 0.3 - 0.05j]]

NEW_TOOL_NAMES = {
    "convert_db_to_linear",
    "convert_linear_to_db",
    "convert_s_to_z",
    "convert_z_to_s",
    "convert_s_to_y",
    "convert_y_to_s",
    "convert_s_to_abcd",
    "convert_abcd_to_s",
    "calculate_free_space_path_loss",
    "calculate_link_budget_margin",
    "calculate_cascade_output_ip3",
    "calculate_oip3_from_iip3",
    "calculate_iip3_from_oip3",
    "calculate_third_order_intermod_output",
    "calculate_third_order_intermod_dbc",
    "calculate_stability_delta",
    "calculate_rollett_k_factor",
    "calculate_stability_verdict",
    "calculate_output_stability_circle",
    "calculate_input_stability_circle",
    "calculate_quarter_wave_transformer_impedance",
    "calculate_l_network_match",
    "calculate_patch_effective_permittivity",
    "calculate_patch_length_extension",
    "calculate_patch_resonant_frequency",
    "calculate_fractional_bandwidth_from_q",
    "calculate_quality_factor_from_fractional_bandwidth",
    "calculate_curvature_length_correction_factor",
    "calculate_curvature_shifted_resonant_frequency",
    "calculate_maxwell_garnett_effective_permeability",
    "calculate_aperture_gain",
    "interpolate_touchstone_file",
    "deembed_touchstone_file",
    "cascade_touchstone_files",
    "compare_touchstone_files",
}


def test_all_new_tools_are_registered():
    registered_names = {t.name for t in asyncio.run(server.mcp.list_tools())}
    missing = NEW_TOOL_NAMES - registered_names
    assert not missing, f"missing MCP tool registrations: {missing}"


def test_registered_tool_count_matches_old_plus_new():
    registered_names = {t.name for t in asyncio.run(server.mcp.list_tools())}
    # 11 tools wired before issue #36 (6 calc/touchstone + 5 knowledge) plus
    # the 35 new ones this ticket adds, plus 1 more (search_design_records)
    # added by issue #37.
    assert len(registered_names) == 11 + len(NEW_TOOL_NAMES) + 1


# ---------------------------------------------------------------------------
# Unit conversions
# ---------------------------------------------------------------------------


def test_convert_db_to_linear_calls_through():
    result = server.convert_db_to_linear(10.0)
    assert result["linear_value"] == pytest.approx(db_to_linear(10.0))
    assert result["provenance"] == "CALCULATED"


def test_convert_linear_to_db_calls_through():
    result = server.convert_linear_to_db(2.0)
    assert result["db_value"] == pytest.approx(linear_to_db(2.0))
    assert result["provenance"] == "CALCULATED"


# ---------------------------------------------------------------------------
# S/Z/Y/ABCD conversions
# ---------------------------------------------------------------------------


def test_convert_s_to_z_calls_through():
    result = server.convert_s_to_z(S_MATRIX, 50.0)
    assert result["provenance"] == "CALCULATED"
    parsed = [[complex(x) for x in row] for row in result["z_params"]]
    np.testing.assert_allclose(parsed, s_to_z(S_MATRIX, 50.0))


def test_convert_z_to_s_calls_through():
    z = s_to_z(S_MATRIX, 50.0)
    z_matrix = [[str(x) for x in row] for row in z]
    result = server.convert_z_to_s(z_matrix, 50.0)
    parsed = [[complex(x) for x in row] for row in result["s_params"]]
    np.testing.assert_allclose(parsed, z_to_s(z, 50.0), atol=1e-9)
    assert result["provenance"] == "CALCULATED"


def test_convert_s_to_y_calls_through():
    result = server.convert_s_to_y(S_MATRIX, 50.0)
    parsed = [[complex(x) for x in row] for row in result["y_params"]]
    np.testing.assert_allclose(parsed, s_to_y(S_MATRIX, 50.0))
    assert result["provenance"] == "CALCULATED"


def test_convert_y_to_s_calls_through():
    y = s_to_y(S_MATRIX, 50.0)
    y_matrix = [[str(x) for x in row] for row in y]
    result = server.convert_y_to_s(y_matrix, 50.0)
    parsed = [[complex(x) for x in row] for row in result["s_params"]]
    np.testing.assert_allclose(parsed, y_to_s(y, 50.0), atol=1e-9)
    assert result["provenance"] == "CALCULATED"


def test_convert_s_to_abcd_calls_through():
    result = server.convert_s_to_abcd(S_MATRIX, 50.0)
    parsed = [[complex(x) for x in row] for row in result["abcd_params"]]
    np.testing.assert_allclose(parsed, s_to_abcd(S_MATRIX, 50.0))
    assert result["provenance"] == "CALCULATED"


def test_convert_abcd_to_s_calls_through():
    abcd = s_to_abcd(S_MATRIX, 50.0)
    abcd_matrix = [[str(x) for x in row] for row in abcd]
    result = server.convert_abcd_to_s(abcd_matrix, 50.0)
    parsed = [[complex(x) for x in row] for row in result["s_params"]]
    np.testing.assert_allclose(parsed, abcd_to_s(abcd, 50.0), atol=1e-9)
    assert result["provenance"] == "CALCULATED"


# ---------------------------------------------------------------------------
# Link budget
# ---------------------------------------------------------------------------


def test_calculate_free_space_path_loss_calls_through():
    result = server.calculate_free_space_path_loss(10.0, 2400.0)
    assert result["path_loss_db"] == pytest.approx(free_space_path_loss_db(10.0, 2400.0))
    assert result["provenance"] == "CALCULATED"


def test_calculate_link_budget_margin_calls_through():
    result = server.calculate_link_budget_margin(30.0, 10.0, 100.0, 15.0, -90.0, 2.0)
    expected = link_budget_margin_db(30.0, 10.0, 100.0, 15.0, -90.0, 2.0)
    assert result["margin_db"] == pytest.approx(expected)
    assert result["provenance"] == "CALCULATED"


# ---------------------------------------------------------------------------
# IP3 / intermodulation
# ---------------------------------------------------------------------------


def test_calculate_cascade_output_ip3_calls_through():
    result = server.calculate_cascade_output_ip3([100.0, 50.0], [10.0, 20.0])
    expected = cascade_output_ip3_linear([100.0, 50.0], [10.0, 20.0])
    assert result["oip3_linear"] == pytest.approx(expected)
    assert result["provenance"] == "CALCULATED"


def test_calculate_oip3_from_iip3_calls_through():
    result = server.calculate_oip3_from_iip3(10.0, 20.0)
    assert result["oip3_dbm"] == pytest.approx(oip3_from_iip3_db(10.0, 20.0))
    assert result["provenance"] == "CALCULATED"


def test_calculate_iip3_from_oip3_calls_through():
    result = server.calculate_iip3_from_oip3(30.0, 20.0)
    assert result["iip3_dbm"] == pytest.approx(iip3_from_oip3_db(30.0, 20.0))
    assert result["provenance"] == "CALCULATED"


def test_calculate_third_order_intermod_output_calls_through():
    result = server.calculate_third_order_intermod_output(0.0, 30.0)
    expected = third_order_intermod_output_dbm(0.0, 30.0)
    assert result["im3_output_dbm"] == pytest.approx(expected)
    assert result["provenance"] == "CALCULATED"


def test_calculate_third_order_intermod_dbc_calls_through():
    result = server.calculate_third_order_intermod_dbc(0.0, 30.0)
    assert result["im3_dbc"] == pytest.approx(third_order_intermod_dbc(0.0, 30.0))
    assert result["provenance"] == "CALCULATED"


# ---------------------------------------------------------------------------
# Stability
# ---------------------------------------------------------------------------


def test_calculate_stability_delta_calls_through():
    result = server.calculate_stability_delta(S_MATRIX)
    assert complex(result["delta"]) == pytest.approx(two_port_stability_delta(S_MATRIX))
    assert result["provenance"] == "CALCULATED"


def test_calculate_rollett_k_factor_calls_through():
    result = server.calculate_rollett_k_factor(S_MATRIX)
    assert result["k_factor"] == pytest.approx(rollett_k_factor(S_MATRIX))
    assert result["provenance"] == "CALCULATED"


def test_calculate_stability_verdict_calls_through():
    result = server.calculate_stability_verdict(S_MATRIX)
    assert result["verdict"] == stability_verdict(S_MATRIX)
    assert result["provenance"] == "CALCULATED"


def test_calculate_output_stability_circle_calls_through():
    result = server.calculate_output_stability_circle(S_MATRIX)
    center, radius = output_stability_circle(S_MATRIX)
    assert complex(result["center"]) == pytest.approx(center)
    assert result["radius"] == pytest.approx(radius)
    assert result["provenance"] == "CALCULATED"


def test_calculate_input_stability_circle_calls_through():
    result = server.calculate_input_stability_circle(S_MATRIX)
    center, radius = input_stability_circle(S_MATRIX)
    assert complex(result["center"]) == pytest.approx(center)
    assert result["radius"] == pytest.approx(radius)
    assert result["provenance"] == "CALCULATED"


# ---------------------------------------------------------------------------
# Impedance matching
# ---------------------------------------------------------------------------


def test_calculate_quarter_wave_transformer_impedance_calls_through():
    result = server.calculate_quarter_wave_transformer_impedance(50.0, 75.0)
    expected = quarter_wave_transformer_impedance(50.0, 75.0)
    assert result["transformer_impedance_ohms"] == pytest.approx(expected)
    assert result["provenance"] == "CALCULATED"


def test_calculate_l_network_match_calls_through():
    result = server.calculate_l_network_match(50.0, 25.0 + 15.0j)
    expected = l_network_match(50.0, 25.0 + 15.0j)
    assert len(result["solutions"]) == len(expected)
    got = {
        (s["series_reactance_ohms"], s["shunt_susceptance_siemens"]) for s in result["solutions"]
    }
    want = set(expected)
    for gx, gb in got:
        assert any(gx == pytest.approx(wx) and gb == pytest.approx(wb) for wx, wb in want)
    assert result["provenance"] == "CALCULATED"


# ---------------------------------------------------------------------------
# Conformal antenna resonant frequency / bandwidth
# ---------------------------------------------------------------------------


def test_calculate_patch_effective_permittivity_calls_through():
    result = server.calculate_patch_effective_permittivity(4.4, 0.03, 0.0016)
    expected = patch_effective_permittivity(4.4, 0.03, 0.0016)
    assert result["eps_eff"] == pytest.approx(expected)
    assert result["provenance"] == "CALCULATED"


def test_calculate_patch_length_extension_calls_through():
    result = server.calculate_patch_length_extension(3.0, 0.03, 0.0016)
    expected = patch_length_extension_m(3.0, 0.03, 0.0016)
    assert result["length_extension_m"] == pytest.approx(expected)
    assert result["provenance"] == "CALCULATED"


def test_calculate_patch_resonant_frequency_calls_through():
    result = server.calculate_patch_resonant_frequency(4.4, 0.03, 0.0016, 0.028)
    expected = patch_resonant_frequency_hz(4.4, 0.03, 0.0016, 0.028)
    assert result["resonant_frequency_hz"] == pytest.approx(expected)
    assert result["provenance"] == "CALCULATED"


def test_calculate_fractional_bandwidth_from_q_calls_through():
    result = server.calculate_fractional_bandwidth_from_q(50.0)
    assert result["fractional_bandwidth"] == pytest.approx(fractional_bandwidth_from_q(50.0))
    assert result["provenance"] == "CALCULATED"


def test_calculate_quality_factor_from_fractional_bandwidth_calls_through():
    result = server.calculate_quality_factor_from_fractional_bandwidth(0.02)
    expected = quality_factor_from_fractional_bandwidth(0.02)
    assert result["quality_factor"] == pytest.approx(expected)
    assert result["provenance"] == "CALCULATED"


def test_calculate_curvature_length_correction_factor_calls_through():
    result = server.calculate_curvature_length_correction_factor(0.02, 0.1)
    expected = curvature_length_correction_factor(0.02, 0.1)
    assert result["correction_factor"] == pytest.approx(expected)
    assert result["provenance"] == "CALCULATED"


def test_calculate_curvature_shifted_resonant_frequency_calls_through():
    result = server.calculate_curvature_shifted_resonant_frequency(2.4e9, 0.02, 0.1)
    expected = curvature_shifted_resonant_frequency_hz(2.4e9, 0.02, 0.1)
    assert result["resonant_frequency_hz"] == pytest.approx(expected)
    assert result["provenance"] == "CALCULATED"


def test_calculate_maxwell_garnett_effective_permeability_calls_through():
    result = server.calculate_maxwell_garnett_effective_permeability(0.1, 5.0)
    expected = maxwell_garnett_effective_permeability(0.1, 5.0)
    assert result["mu_eff"] == pytest.approx(expected)
    assert result["provenance"] == "CALCULATED"


def test_calculate_aperture_gain_calls_through():
    result = server.calculate_aperture_gain(0.5, 10e9)
    expected = aperture_gain(0.5, 10e9)
    assert result["gain_linear"] == pytest.approx(expected)
    assert result["provenance"] == "CALCULATED"


# ---------------------------------------------------------------------------
# Touchstone
# ---------------------------------------------------------------------------


def _write_matched_attenuator(tmp_path: Path, atten_db: float, name: str) -> Path:
    freqs_hz = np.linspace(1e9, 5e9, 9)
    s = np.zeros((len(freqs_hz), 2, 2), dtype=complex)
    s21 = 10 ** (-atten_db / 20)
    s[:, 1, 0] = s21
    s[:, 0, 1] = s21
    freq = rf.Frequency.from_f(freqs_hz, unit="hz")
    ntwk = rf.Network(frequency=freq, s=s, z0=50)
    path = tmp_path / f"{name}.s2p"
    ntwk.write_touchstone(path.with_suffix(""))
    return path


def test_interpolate_touchstone_file_calls_through(tmp_path: Path):
    path = _write_matched_attenuator(tmp_path, 3.0, "interp")
    target = [1.5e9, 2.5e9, 3.5e9]
    result = server.interpolate_touchstone_file(str(path), target)
    assert result["ports"] == 2
    assert result["points"] == len(target)
    assert result["frequency_start_hz"] == pytest.approx(target[0])
    assert result["frequency_stop_hz"] == pytest.approx(target[-1])
    assert result["s21_max_db"] == pytest.approx(-3.0, abs=1e-6)
    assert result["provenance"] == "CALCULATED"


def test_deembed_touchstone_file_calls_through(tmp_path: Path):
    fixture_db = 2.0
    dut_db = 5.0
    fixture_path = _write_matched_attenuator(tmp_path, fixture_db, "deembed_fixture")

    fixture = rf.Network(str(fixture_path))
    freqs_hz = fixture.f
    s = np.zeros((len(freqs_hz), 2, 2), dtype=complex)
    s21 = 10 ** (-dut_db / 20)
    s[:, 1, 0] = s21
    s[:, 0, 1] = s21
    dut = rf.Network(frequency=fixture.frequency, s=s, z0=50)
    measured = fixture**dut
    measured_path = tmp_path / "deembed_measured.s2p"
    measured.write_touchstone(measured_path.with_suffix(""))

    result = server.deembed_touchstone_file(str(measured_path), str(fixture_path))
    assert result["ports"] == 2
    assert result["s21_max_db"] == pytest.approx(-dut_db, abs=1e-6)
    assert result["provenance"] == "CALCULATED"


def test_cascade_touchstone_files_calls_through(tmp_path: Path):
    path_a = _write_matched_attenuator(tmp_path, 3.0, "cascade_a")
    path_b = _write_matched_attenuator(tmp_path, 6.0, "cascade_b")
    result = server.cascade_touchstone_files([str(path_a), str(path_b)])
    assert result["ports"] == 2
    assert result["s21_max_db"] == pytest.approx(-9.0, abs=1e-6)
    assert result["provenance"] == "CALCULATED"


def test_compare_touchstone_files_calls_through(tmp_path: Path):
    path_a = _write_matched_attenuator(tmp_path, 3.0, "compare_a")
    path_b = _write_matched_attenuator(tmp_path, 4.0, "compare_b")
    result = server.compare_touchstone_files(str(path_a), str(path_b))
    assert result["ports"] == 2
    assert result["s21"]["max_magnitude_diff_db"] == pytest.approx(1.0, abs=1e-6)
    assert isinstance(result["s21"]["diff"][0], str)
    complex(result["s21"]["diff"][0])  # round-trips through complex()
    assert result["provenance"] == "CALCULATED"
