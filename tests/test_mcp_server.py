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
from orchestration.policy import assert_all_tools_categorized
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
    # added by issue #37, plus 1 more (run_nec2_simulation) added by #38,
    # plus 1 more (run_openems_simulation) added by #39, plus 1 more
    # (run_hfss_simulation) added by #40, plus 1 more
    # (optimize_patch_length_for_target_frequency) added by #41, plus 2 more
    # (request_vna_measurement_approval, measure_vna_s_parameters) added by
    # #43, plus 6 more (request_spectrum_analyzer_measurement_approval,
    # measure_spectrum_analyzer_trace,
    # request_signal_generator_output_approval, set_signal_generator_output,
    # request_power_meter_measurement_approval, measure_power_meter_reading)
    # added by #44, plus 1 more (correlate_simulated_and_measured) added by
    # #45, plus 3 more (start_design_loop, advance_design_loop_step,
    # inspect_design_loop_state) added by #46, plus 4 more (create_design,
    # read_design, record_decision, verify_requirement) from a separately-
    # merged PR (#15, docs/adr/0005-0007) reconciled into this branch, plus
    # 1 more (run_gprmax_simulation) added by #63.
    expected = 11 + len(NEW_TOOL_NAMES) + 1 + 1 + 1 + 1 + 1 + 2 + 6 + 1 + 3 + 4 + 1
    assert len(registered_names) == expected


def test_correlate_simulated_and_measured_is_registered():
    registered_names = {t.name for t in asyncio.run(server.mcp.list_tools())}
    assert "correlate_simulated_and_measured" in registered_names


def test_run_nec2_simulation_is_registered():
    registered_names = {t.name for t in asyncio.run(server.mcp.list_tools())}
    assert "run_nec2_simulation" in registered_names


def test_run_openems_simulation_is_registered():
    registered_names = {t.name for t in asyncio.run(server.mcp.list_tools())}
    assert "run_openems_simulation" in registered_names


def test_run_hfss_simulation_is_registered():
    registered_names = {t.name for t in asyncio.run(server.mcp.list_tools())}
    assert "run_hfss_simulation" in registered_names


def test_run_gprmax_simulation_is_registered():
    registered_names = {t.name for t in asyncio.run(server.mcp.list_tools())}
    assert "run_gprmax_simulation" in registered_names


def test_every_registered_tool_is_categorized_in_tool_policy():
    # Mirrors the import-time assert_all_tools_categorized() call at the
    # bottom of mcp_server/server.py -- this test makes the same guarantee
    # explicit and independently re-checkable here.
    registered_names = [t.name for t in asyncio.run(server.mcp.list_tools())]
    assert_all_tools_categorized(registered_names)


def test_optimize_patch_length_for_target_frequency_is_registered():
    registered_names = {t.name for t in asyncio.run(server.mcp.list_tools())}
    assert "optimize_patch_length_for_target_frequency" in registered_names


def test_design_loop_tools_are_registered():
    registered_names = {t.name for t in asyncio.run(server.mcp.list_tools())}
    assert "start_design_loop" in registered_names
    assert "advance_design_loop_step" in registered_names
    assert "inspect_design_loop_state" in registered_names


def test_optimize_patch_length_for_target_frequency_calls_through():
    result = server.optimize_patch_length_for_target_frequency(
        eps_r=4.4,
        w_m=0.038,
        h_m=0.0016,
        target_frequency_hz=2.4e9,
        length_lower_m=0.02,
        length_upper_m=0.04,
        method="grid",
        n_evaluations=10,
    )
    assert result["method"] == "grid_search"
    assert result["provenance"] == "CALCULATED"
    assert 0.02 <= result["best_length_m"] <= 0.04
    assert result["achieved_frequency_hz"] == pytest.approx(
        patch_resonant_frequency_hz(4.4, 0.038, 0.0016, result["best_length_m"])
    )
    assert result["n_evaluations"] == 10
    assert result["constraints"] == {"eps_r": 4.4, "w_m": 0.038, "h_m": 0.0016}


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


# ---------------------------------------------------------------------------
# NEC2++ simulation (issue #38)
#
# The real nec2++ binary is not installed in this environment, so this
# exercises the MCP wrapper's call-through to simulation.nec2pp via a fake
# "nec2++" script pointed to by NEC2PP_BIN -- same not-verified-against-a-
# real-binary caveat as tests/test_nec2pp.py. The section headings and
# field order below match the documented NEC2 output format (see
# tests/test_nec2pp.py for the letter-for-letter guide transcription used
# to actually validate the parser -- this one is just re-wrapped to fit
# this file's line length).
# ---------------------------------------------------------------------------

_FAKE_NEC2PP_OUTPUT = """
              - - - ANTENNA INPUT PARAMETERS - - -
  TAG SEG.  VOLTAGE (VOLTS)      CURRENT (AMPS)    IMPEDANCE (OHMS)
  NO. NO.  REAL       IMAG.     REAL      IMAG.    REAL      IMAG.
    0   4 1.0E+00 0.0E+00 9.2E-03-5.1E-03 8.3E+01 4.6E+01 9.2E-03-5.1E-03 4.6E-03
                    - - - RADIATION PATTERNS - - -
- - ANGLES - -    - POWER GAINS -   - - POLARIZATION - -   - E(THETA) -
THETA   PHI     VERT.   HOR.  TOTAL   AXIAL   TILT  SENSE   MAGNITUDE
DEGREES DEGREES   DB     DB    DB    RATIO    DEG.           VOLTS/M
  90.00    .00   8.52 -999.99  8.52  .00000    .00  LINEAR  1.4E+00  62.47  0.0E-01  .00
"""


def _write_fake_nec2pp(tmp_path: Path) -> Path:
    import stat
    import sys

    script = tmp_path / "fake_nec2pp.py"
    script.write_text(
        f"#!{sys.executable}\n"
        "import sys\n"
        f'OUTPUT = """{_FAKE_NEC2PP_OUTPUT}"""\n'
        "sys.stdout.write(OUTPUT)\n"
        "sys.exit(0)\n"
    )
    script.chmod(script.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return script


def test_run_nec2_simulation_calls_through(tmp_path: Path, monkeypatch):
    script = _write_fake_nec2pp(tmp_path)
    monkeypatch.setenv("NEC2PP_BIN", str(script))

    geometry = {
        "wires": [
            {
                "tag": 1,
                "segments": 7,
                "x1_m": 0.0,
                "y1_m": 0.0,
                "z1_m": -0.25,
                "x2_m": 0.0,
                "y2_m": 0.0,
                "z2_m": 0.25,
                "radius_m": 0.001,
            }
        ]
    }
    result = server.run_nec2_simulation(geometry, frequency_hz=300e6, timeout_s=10)

    assert result["provenance"] == "SIMULATED"
    assert result["simulator"] == "NEC2++"
    assert result["impedance"]["resistance_ohms"] == pytest.approx(83.0)
    assert result["gain_dbi"] == pytest.approx(8.52)


# ---------------------------------------------------------------------------
# openEMS simulation (issue #39)
#
# The real openEMS binary is not installed in this environment, so this
# exercises the MCP wrapper's call-through to simulation.openems via a fake
# "openEMS" script pointed to by OPENEMS_BIN -- same not-verified-against-a-
# real-binary caveat as tests/test_openems.py. See that file's module
# docstring for the source citations behind this transcribed log text
# (re-wrapped here, whitespace-compacted, to fit this file's line length).
# ---------------------------------------------------------------------------

_FAKE_OPENEMS_OUTPUT = """
[@ 4s] Timestep: 500 || Speed: 88.8 MC/s (3.040e-03 s/TS) || Energy: ~7.06e-03 (- 5.00dB)
[@ 8s] Timestep: 1326 || Speed: 88.8 MC/s (3.040e-03 s/TS) || Energy: ~7.06e-17 (- 50.00dB)
Time for 1326 iterations with 269780.00 cells : 32.41 sec
Speed: 118.02 MCells/s
"""


def _write_fake_openems(tmp_path: Path) -> Path:
    import stat
    import sys

    script = tmp_path / "fake_openems.py"
    script.write_text(
        f"#!{sys.executable}\n"
        "import sys\n"
        f'OUTPUT = """{_FAKE_OPENEMS_OUTPUT}"""\n'
        "sys.stdout.write(OUTPUT)\n"
        "sys.exit(0)\n"
    )
    script.chmod(script.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return script


def test_run_openems_simulation_calls_through(tmp_path: Path, monkeypatch):
    script = _write_fake_openems(tmp_path)
    monkeypatch.setenv("OPENEMS_BIN", str(script))

    geometry = {
        "materials": [
            {
                "name": "substrate",
                "shape": "box",
                "p1_m": [0.0, 0.0, 0.0],
                "p2_m": [0.03, 0.02, 0.0016],
                "epsilon_r": 3.5,
            }
        ],
        "conductors": [
            {
                "name": "patch",
                "shape": "box",
                "p1_m": [0.005, 0.005, 0.0016],
                "p2_m": [0.025, 0.015, 0.0016],
            }
        ],
        "ports": [
            {
                "name": "feed",
                "p1_m": [0.015, 0.005, 0.0],
                "p2_m": [0.015, 0.005, 0.0016],
                "direction": "z",
                "resistance_ohms": 50.0,
            }
        ],
        "mesh": {
            "x_lines_m": [0.0, 0.01, 0.02, 0.03],
            "y_lines_m": [0.0, 0.01, 0.02],
            "z_lines_m": [0.0, 0.0016],
        },
        "frequency_hz": 2.45e9,
    }
    result = server.run_openems_simulation(
        geometry, fdtd={"max_timesteps": 30000, "end_criteria": 1e-5}, timeout_s=10
    )

    assert result["provenance"] == "SIMULATED"
    assert result["simulator"] == "openEMS"
    assert result["convergence"]["terminated_reason"] == "end_criteria"
    assert result["s_parameters"]["computed"] is False
    assert result["far_field"]["computed"] is False


# ---------------------------------------------------------------------------
# gprMax simulation (issue #63)
#
# gprMax genuinely cannot be installed in this environment at all (no pip
# package exists -- see simulation/gprmax.py's module docstring
# "CORRECTION" section), so this exercises the MCP wrapper's call-through
# to simulation.gprmax via a fake "python -m gprMax" script (pointed to by
# GPRMAX_PYTHON) that writes a synthetic .out HDF5 file next to the input
# file it's given, matching gprMax's own documented output-file naming and
# /tls/tlN/ structure (see simulation/gprmax.py's module docstring
# citation) -- kept self-contained in this file rather than importing
# tests/test_gprmax.py's own fake-data helpers, same "not re-imported here
# to keep this file self-contained" discipline as this file's HFSS section
# below (which does the same for tests/test_hfss.py's FakeHfss).
# ---------------------------------------------------------------------------


def _write_fake_gprmax_python(tmp_path: Path, vinc, vtotal, itotal, dt: float) -> Path:
    import stat
    import sys

    script = tmp_path / "fake_gprmax_python.py"
    script.write_text(
        f"#!{sys.executable}\n"
        "import sys\n"
        "from pathlib import Path\n"
        "import h5py\n"
        f"VINC = {list(float(v) for v in vinc)!r}\n"
        f"VTOTAL = {list(float(v) for v in vtotal)!r}\n"
        f"ITOTAL = {list(float(v) for v in itotal)!r}\n"
        f"DT = {float(dt)!r}\n"
        "args = sys.argv[1:]\n"
        "assert args[:2] == ['-m', 'gprMax'], args\n"
        "input_file = Path(args[2])\n"
        "out_path = Path(str(input_file) + '.out')\n"
        "with h5py.File(out_path, 'w') as f:\n"
        "    f.attrs['dt'] = DT\n"
        "    f.attrs['Iterations'] = len(VINC)\n"
        "    tl = f.create_group('tls/tl1')\n"
        "    tl.create_dataset('Vinc', data=VINC)\n"
        "    tl.create_dataset('Vtotal', data=VTOTAL)\n"
        "    tl.create_dataset('Itotal', data=ITOTAL)\n"
        "sys.exit(0)\n"
    )
    script.chmod(script.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return script


def test_run_gprmax_simulation_calls_through(tmp_path: Path, monkeypatch):
    # A short Gaussian pulse for Vinc, with Vtotal = (1+GAMMA)*Vinc pointwise
    # in time -- so Vref=Vtotal-Vinc=GAMMA*Vinc and S11(f)=GAMMA at every
    # frequency, a closed-form known answer (see tests/test_gprmax.py for
    # the fuller version of this same construction).
    n = 256
    dt = 2e-11
    t = np.arange(n) * dt
    vinc = np.exp(-(((t - 2.5e-9) / 5e-10) ** 2))
    gamma = -0.3
    vtotal = (1 + gamma) * vinc
    itotal = vtotal / 50.0

    script = _write_fake_gprmax_python(tmp_path, vinc, vtotal, itotal, dt)
    monkeypatch.setenv("GPRMAX_PYTHON", str(script))

    geometry = {
        "domain_m": [0.1, 0.1, 0.1],
        "resolution_m": 0.002,
        "half_space": {"z_m": 0.04, "epsilon_r": 6.0, "conductivity_s_m": 0.01},
        "conductors": [
            {"shape": "box", "p1_m": [0.03, 0.03, 0.04], "p2_m": [0.07, 0.07, 0.04]}
        ],
        "port": {
            "polarization": "z",
            "position_m": [0.05, 0.05, 0.04],
            "resistance_ohms": 50.0,
            "center_frequency_hz": 1.0e9,
        },
    }
    result = server.run_gprmax_simulation(
        geometry, fdtd={"time_window_s": 6e-8}, timeout_s=10
    )

    assert result["provenance"] == "SIMULATED"
    assert result["simulator"] == "gprMax"
    assert result["s_parameters"]["computed"] is True
    s11_values = result["s_parameters"]["values"]["S11"]
    assert s11_values, "expected at least one in-band S11 frequency point"
    for re, im in s11_values:
        assert re == pytest.approx(gamma, abs=1e-6)
        assert im == pytest.approx(0.0, abs=1e-6)
    assert result["far_field"]["computed"] is False


# ---------------------------------------------------------------------------
# HFSS simulation (issue #40)
#
# HFSS/PyAEDT genuinely cannot run in this environment even in principle --
# no license, no AEDT install, and simulation.hfss.check_hfss_workstation_
# confinement() is designed to reject this sandbox (see tests/test_hfss.py
# for the direct, unmockable proof of that). This test therefore exercises
# only the MCP wrapper's parameter call-through to
# simulation.hfss.run_hfss_simulation, by monkeypatching the module-level
# `_run_hfss_simulation` reference server.py calls through so it engages
# that function's own hfss_factory/confinement_check test-injection seams
# (documented on HfssSimulator.__init__) against a hand-written fake --
# same fake shape as tests/test_hfss.py's FakeHfss, not re-imported here to
# keep this file self-contained like its NEC2++/openEMS sections above.
# ---------------------------------------------------------------------------


class _FakeHfssForMcpTest:
    def __init__(self, project, design, **kwargs):
        self.project = project

    def assign_material(self, assignment, material):
        pass

    def lumped_port(self, **kwargs):
        pass

    def create_setup(self, **kwargs):
        pass

    def create_linear_count_sweep(self, **kwargs):
        pass

    def analyze(self, **kwargs):
        pass

    def export_touchstone(self, **kwargs):
        from pathlib import Path as _Path

        _Path(kwargs["output_file"]).write_text("! fake touchstone\n")
        return kwargs["output_file"]

    def save_project(self):
        from pathlib import Path as _Path

        _Path(self.project).write_text("fake project\n")
        return True

    def release_desktop(self, **kwargs):
        return True

    @property
    def modeler(self):
        return self

    def create_box(self, origin, sizes, name=None, **kwargs):
        return name

    @property
    def mesh(self):
        return self

    def assign_length_mesh(self, **kwargs):
        return None

    @property
    def post(self):
        return self

    def get_solution_data(self, **kwargs):
        from types import SimpleNamespace

        return SimpleNamespace(
            primary_sweep_values=[2.4, 2.45, 2.5],
            full_matrix_mag_phase=({"S(1,1)": [0.2, 0.02, 0.25]}, {"S(1,1)": [0.0, 0.5, 1.0]}),
        )


def test_run_hfss_simulation_calls_through(tmp_path: Path, monkeypatch):
    from simulation.hfss import run_hfss_simulation as real_run_hfss_simulation

    def fake_run(geometry, frequency_hz, sweep=None, project_name="hfss_project",
                 design_name="hfss_design"):
        return real_run_hfss_simulation(
            geometry=geometry,
            frequency_hz=frequency_hz,
            sweep=sweep,
            project_name=project_name,
            design_name=design_name,
            archive_dir=str(tmp_path),
            hfss_factory=lambda **kw: _FakeHfssForMcpTest(**kw),
            confinement_check=lambda: None,
        )

    monkeypatch.setattr(server, "_run_hfss_simulation", fake_run)

    geometry = {
        "conductors": [
            {"name": "ground", "p1_m": [0.0, 0.0, 0.0], "p2_m": [0.03, 0.02, 0.0]},
        ],
        "port": {
            "name": "feed",
            "sheet": {"p1_m": [0.015, 0.005, 0.0], "p2_m": [0.015, 0.005, 0.0016]},
        },
    }
    result = server.run_hfss_simulation(geometry, frequency_hz=2.45e9)

    assert result["provenance"] == "SIMULATED"
    assert result["simulator"] == "HFSS"
    assert result["status"] == "COMPLETED"
    assert result["s_parameters"]["computed"] is True
    assert Path(result["touchstone_file"]).exists()
