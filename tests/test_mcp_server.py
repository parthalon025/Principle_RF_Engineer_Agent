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
from conftest import make_fake_executable

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
    # (optimize_patch_length_for_target_frequency) added by #41, plus 1 more
    # (correlate_simulated_and_measured) added by
    # #45, plus 3 more (start_design_loop, advance_design_loop_step,
    # inspect_design_loop_state) added by #46, plus 4 more (create_design,
    # read_design, record_decision, verify_requirement) from a separately-
    # merged PR (#15, docs/adr/0005-0007) reconciled into this branch, plus
    # 1 more (run_openparem_simulation) added by #62, plus 1 more
    # (run_elmer_simulation) added by #64, plus 1 more
    # (run_ltspice_simulation) added by #59, plus 1 more
    # (run_qucs_simulation) added by #58, plus 1 more
    # (run_kicad_gerber2ems_simulation) added by #65, plus 2 more
    # (run_ngspice_simulation, run_xyce_simulation) added by #57, plus 1 more
    # (run_palace_simulation) added by #61, plus 4 more
    # (lookup_digikey_component, lookup_mouser_component,
    # lookup_nexar_component, reconcile_component_sources) added by #67,
    # plus 1 more (run_gprmax_simulation) added by #63, plus 1 more
    # (run_meep_simulation) added by #60, plus 1 more
    # (generate_freecad_curved_geometry) added by #66, plus 3 more
    # (propose_requirement_target, mark_requirement_unscoreable,
    # confirm_requirement_target) added by #92.
    #
    # #43 added 2 (request_vna_measurement_approval, measure_vna_s_parameters)
    # and #44 added 6 more (request_spectrum_analyzer_measurement_approval,
    # measure_spectrum_analyzer_trace,
    # request_signal_generator_output_approval, set_signal_generator_output,
    # request_power_meter_measurement_approval, measure_power_meter_reading)
    # -- ticket #90 REMOVED all 8: the SCPI/VISA instrument-actuation
    # approval gate and every tool built on it are gone (this system offers
    # no physical-instrument actuation capability at all -- see ADR-0012),
    # so the "+ 2" and "+ 6" terms those tickets added are gone with them.
    #
    # Running total: 82 (pre-#92) + 3 (#92) - 8 (#90) = 77. #90's own branch
    # computed 82 - 8 = 74 against a base that predated #92; both tickets
    # landed, so both adjustments apply.
    #
    # issue #94 adds 1 more (compile_lab_test_plan) and issue #95 adds 1
    # more (run_candidate_search, the candidate solver). Both were built in
    # parallel against the same 77 baseline and each computed 77 + 1 = 78 on
    # its own branch; both landed, so both apply: 77 + 1 + 1 = 79.
    #
    # issue #143 adds 1 more (synthesize_filter_prototype): 79 + 1 = 80.
    #
    # issue #145 adds 1 more (advance_design_status): 80 + 1 = 81.
    #
    # arxiv-doc-builder integration adds 1 more (ingest_arxiv_paper): 81 + 1 = 82.
    #
    # issue #219 adds 1 more (ingest_patent, the USPTO patent/published-
    # application fetcher): 82 + 1 = 83.
    expected = (
        11
        + len(NEW_TOOL_NAMES)
        + 1
        + 1
        + 1
        + 1
        + 1
        + 1
        + 3
        + 4
        + 1
        + 1
        + 1
        + 1
        + 1
        + 2
        + 1
        + 4
        + 1
        + 1
        + 1
        + 3
        + 1
        + 1
        + 1  # issue #143: synthesize_filter_prototype
        + 1  # issue #145: advance_design_status
        + 1  # arxiv-doc-builder integration: ingest_arxiv_paper
        + 1  # issue #219: ingest_patent
    )
    assert len(registered_names) == expected


def test_component_sourcing_tools_are_registered():
    registered_names = {t.name for t in asyncio.run(server.mcp.list_tools())}
    assert "lookup_digikey_component" in registered_names
    assert "lookup_mouser_component" in registered_names
    assert "lookup_nexar_component" in registered_names
    assert "reconcile_component_sources" in registered_names


def test_ingest_arxiv_paper_is_registered():
    registered_names = {t.name for t in asyncio.run(server.mcp.list_tools())}
    assert "ingest_arxiv_paper" in registered_names


def test_ingest_patent_is_registered():
    registered_names = {t.name for t in asyncio.run(server.mcp.list_tools())}
    assert "ingest_patent" in registered_names


def test_correlate_simulated_and_measured_is_registered():
    registered_names = {t.name for t in asyncio.run(server.mcp.list_tools())}
    assert "correlate_simulated_and_measured" in registered_names


def test_run_nec2_simulation_is_registered():
    registered_names = {t.name for t in asyncio.run(server.mcp.list_tools())}
    assert "run_nec2_simulation" in registered_names


def test_run_openems_simulation_is_registered():
    registered_names = {t.name for t in asyncio.run(server.mcp.list_tools())}
    assert "run_openems_simulation" in registered_names


def test_run_ngspice_simulation_is_registered():
    registered_names = {t.name for t in asyncio.run(server.mcp.list_tools())}
    assert "run_ngspice_simulation" in registered_names


def test_run_xyce_simulation_is_registered():
    registered_names = {t.name for t in asyncio.run(server.mcp.list_tools())}
    assert "run_xyce_simulation" in registered_names


def test_run_hfss_simulation_is_registered():
    registered_names = {t.name for t in asyncio.run(server.mcp.list_tools())}
    assert "run_hfss_simulation" in registered_names


def test_run_openparem_simulation_is_registered():
    registered_names = {t.name for t in asyncio.run(server.mcp.list_tools())}
    assert "run_openparem_simulation" in registered_names


def test_run_elmer_simulation_is_registered():
    registered_names = {t.name for t in asyncio.run(server.mcp.list_tools())}
    assert "run_elmer_simulation" in registered_names


def test_run_ltspice_simulation_is_registered():
    registered_names = {t.name for t in asyncio.run(server.mcp.list_tools())}
    assert "run_ltspice_simulation" in registered_names


def test_run_palace_simulation_is_registered():
    registered_names = {t.name for t in asyncio.run(server.mcp.list_tools())}
    assert "run_palace_simulation" in registered_names


def test_run_gprmax_simulation_is_registered():
    registered_names = {t.name for t in asyncio.run(server.mcp.list_tools())}
    assert "run_gprmax_simulation" in registered_names


def test_generate_freecad_curved_geometry_is_registered():
    registered_names = {t.name for t in asyncio.run(server.mcp.list_tools())}
    assert "generate_freecad_curved_geometry" in registered_names


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
    body = (
        f'import sys\nOUTPUT = """{_FAKE_NEC2PP_OUTPUT}"""\nsys.stdout.write(OUTPUT)\nsys.exit(0)\n'
    )
    return make_fake_executable(tmp_path, body, name="fake_nec2pp")


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
    body = (
        "import sys\n"
        f'OUTPUT = """{_FAKE_OPENEMS_OUTPUT}"""\n'
        "sys.stdout.write(OUTPUT)\n"
        "sys.exit(0)\n"
    )
    return make_fake_executable(tmp_path, body, name="fake_openems")


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
# ngspice / Xyce circuit simulation (issue #57)
#
# Neither real binary is installed in this environment, so these exercise
# only the MCP wrappers' call-through to simulation.ngspice/simulation.xyce
# via a fake script pointed to by NGSPICE_BIN/XYCE_BIN -- same not-verified-
# against-a-real-binary caveat as tests/test_ngspice.py/tests/test_xyce.py.
# ---------------------------------------------------------------------------

_MATCHING_NETWORK_JOB = {
    "components": [
        {"type": "L", "name": "L1", "n1": "in", "n2": "out", "value": 10e-9},
        {"type": "C", "name": "C1", "n1": "out", "n2": "0", "value": 5e-12},
        {"type": "V", "name": "V1", "n1": "in", "n2": "0", "dc": 0.0, "ac_mag": 1.0},
    ],
    "analysis": {
        "type": "ac",
        "sweep_type": "dec",
        "points": 10,
        "start_freq_hz": 1e8,
        "stop_freq_hz": 1e10,
    },
    "outputs": ["v(out)"],
}


def _write_fake_ngspice(tmp_path: Path) -> Path:
    body = (
        "import sys\n"
        "args = sys.argv[1:]\n"
        "with open(args[2], 'w') as f:\n"
        "    f.write('')\n"
        "with open('ngspice_output.dat', 'w') as f:\n"
        "    f.write('1e+08 2.0 0.0\\n1e+09 1.5 -0.5\\n')\n"
        "sys.exit(0)\n"
    )
    return make_fake_executable(tmp_path, body, name="fake_ngspice")


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
    body = (
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
    return make_fake_executable(tmp_path, body, name="fake_gprmax_python")


def test_run_ngspice_simulation_calls_through(tmp_path: Path, monkeypatch):
    script = _write_fake_ngspice(tmp_path)
    monkeypatch.setenv("NGSPICE_BIN", str(script))

    result = server.run_ngspice_simulation(_MATCHING_NETWORK_JOB, timeout_s=10)

    assert result["provenance"] == "SIMULATED"
    assert result["simulator"] == "ngspice"
    assert result["scale_name"] == "frequency_hz"
    assert result["values"]["v(out)"] == [
        [pytest.approx(2.0), pytest.approx(0.0)],
        [pytest.approx(1.5), pytest.approx(-0.5)],
    ]


def _write_fake_xyce(tmp_path: Path) -> Path:
    body = (
        "import sys\n"
        "with open('xyce_output.csv', 'w') as f:\n"
        "    f.write('FREQ,V(OUT)\\n100000000.0,2.0\\n1000000000.0,1.5\\n')\n"
        "sys.exit(0)\n"
    )
    return make_fake_executable(tmp_path, body, name="fake_xyce")


def test_run_xyce_simulation_calls_through(tmp_path: Path, monkeypatch):
    script = _write_fake_xyce(tmp_path)
    monkeypatch.setenv("XYCE_BIN", str(script))
    job = {**_MATCHING_NETWORK_JOB, "outputs": ["V(out)"]}

    result = server.run_xyce_simulation(job, timeout_s=10)

    assert result["provenance"] == "SIMULATED"
    assert result["simulator"] == "Xyce"
    assert result["scale_name"] == "FREQ"
    assert result["values"]["V(OUT)"] == pytest.approx([2.0, 1.5])


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
        "conductors": [{"shape": "box", "p1_m": [0.03, 0.03, 0.04], "p2_m": [0.07, 0.07, 0.04]}],
        "port": {
            "polarization": "z",
            "position_m": [0.05, 0.05, 0.04],
            "resistance_ohms": 50.0,
            "center_frequency_hz": 1.0e9,
        },
    }
    result = server.run_gprmax_simulation(geometry, fdtd={"time_window_s": 6e-8}, timeout_s=10)

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

    def fake_run(
        geometry, frequency_hz, sweep=None, project_name="hfss_project", design_name="hfss_design"
    ):
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


# ---------------------------------------------------------------------------
# OpenParEM3D simulation (issue #62)
#
# The real OpenParEM3D binary is not installed in this environment, so this
# exercises the MCP wrapper's call-through to simulation.openparem via a fake
# "OpenParEM3D" script pointed to by OPENPAREM3D_BIN, mirroring
# test_run_nec2_simulation_calls_through/test_run_openems_simulation_calls_
# through above -- same not-verified-against-a-real-binary caveat as
# tests/test_openparem.py. See that file's/simulation/openparem.py's module
# docstrings for the *_results.csv/*_FarField_results.csv format citations
# behind this fake script's written output.
# ---------------------------------------------------------------------------

_FAKE_OPENPAREM3D_RESULTS_CSV = (
    "#OpenParEM3D 2.1.0\n"
    "#Touchstone format,RI\n"
    "#frequency unit,GHz\n"
    "#number of frequencies,1\n"
    "#number of ports,1\n"
    "#S-port 1,net1,50\n"
    "#Frequency(GHz),Re(S(1;1)),Im(S(1;1))\n"
    "2.45,-0.1,0.05\n"
)

_FAKE_OPENPAREM3D_FARFIELD_CSV = (
    "#S-port,frequency(GHz),gain,directivity,radiation efficiency\n1,2.45,5.23,5.90,0.89\n"
)


def _write_fake_openparem3d(tmp_path: Path, project_name: str) -> Path:
    body = (
        "import sys\n"
        f'with open("{project_name}_results.csv", "w") as f:\n'
        f'    f.write("""{_FAKE_OPENPAREM3D_RESULTS_CSV}""")\n'
        f'with open("{project_name}_FarField_results.csv", "w") as f:\n'
        f'    f.write("""{_FAKE_OPENPAREM3D_FARFIELD_CSV}""")\n'
        "sys.exit(0)\n"
    )
    return make_fake_executable(tmp_path, body, name="fake_openparem3d")


# ---------------------------------------------------------------------------
# Palace simulation (issue #61)
#
# The real palace binary is not installed in this environment, so this
# exercises the MCP wrapper's call-through to simulation.palace via a fake
# "palace" script pointed to by PALACE_BIN -- same not-verified-against-a-
# real-binary caveat as tests/test_palace.py. The fake script writes a
# synthetic port-floquet-S.csv (RFC4180-quoted, per simulation/palace.py's
# module docstring honest caveat) into the config's declared Output
# directory, matching how a real Palace run would.
# ---------------------------------------------------------------------------

# Palace separates the two diffraction-order indices with a SEMICOLON in its
# CSV header cells ("S[P1(0;0)TE][1]"), not a comma -- confirmed against its
# own published reference output, see tests/test_palace.py and issue #210.
_FAKE_PALACE_CSV_HEADER = ["f (GHz)", "|S[P1(0;0)TE][1]| (dB)", "arg(S[P1(0;0)TE][1]) (deg.)"]
_FAKE_PALACE_CSV_ROW = ["10.000000e+00", "-6.0206", "0.0"]


def _write_fake_palace(tmp_path: Path) -> Path:
    import csv
    import io

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(_FAKE_PALACE_CSV_HEADER)
    writer.writerow(_FAKE_PALACE_CSV_ROW)
    csv_text = buf.getvalue()

    body = (
        "import json\n"
        "import sys\n"
        "from pathlib import Path\n"
        f'CSV = """{csv_text}"""\n'
        "config_path = Path(sys.argv[3])\n"
        "config = json.loads(config_path.read_text())\n"
        'output_dir = Path(config["Problem"]["Output"])\n'
        "output_dir.mkdir(parents=True, exist_ok=True)\n"
        '(output_dir / "port-floquet-S.csv").write_text(CSV)\n'
        "sys.exit(0)\n"
    )
    return make_fake_executable(tmp_path, body, name="fake_palace")


def test_run_openparem_simulation_calls_through(tmp_path: Path, monkeypatch):
    script = _write_fake_openparem3d(tmp_path, "openparem_project")
    monkeypatch.setenv("OPENPAREM3D_BIN", str(script))

    ports = {
        "paths": [
            {
                "name": "port",
                "points": [[0.0, 0.0, 0.0], [0.001, 0.0, 0.0], [0.0, 0.001, 0.0]],
                "closed": True,
            },
            {
                "name": "front",
                "points": [
                    [-0.1, -0.1, -0.1],
                    [0.1, -0.1, -0.1],
                    [0.1, -0.1, 0.1],
                    [-0.1, -0.1, 0.1],
                ],
                "closed": True,
            },
        ],
        "boundaries": [{"name": "front", "type": "radiation", "path": "+front"}],
        "ports": [
            {
                "name": "in",
                "path": "+port",
                "modes": [{"sport": 1, "integration_path": {"type": "voltage", "path": "+port"}}],
            }
        ],
    }
    result = server.run_openparem_simulation(
        mesh_file="model.msh",
        ports=ports,
        project={
            "frequency_plan": {"point": [{"frequency_hz": 2.45e9}]},
            "far_field": {"quantity": "G"},
        },
        timeout_s=10,
    )

    assert result["provenance"] == "SIMULATED"
    assert result["simulator"] == "OpenParEM3D"
    assert result["status"] == "COMPLETED"
    assert result["s_parameters"]["computed"] is True
    assert result["far_field"]["computed"] is True
    assert result["far_field"]["entries"][0]["gain_dbi"] == pytest.approx(5.23)


# ---------------------------------------------------------------------------
# Elmer FEM VectorHelmholtz simulation (issue #64)
#
# None of gmsh, ElmerGrid, or ElmerSolver is installed in this environment,
# so this exercises the MCP wrapper's call-through to simulation.elmer via
# small fake "gmsh"/"ElmerGrid"/"ElmerSolver" scripts passed through the
# tool's own gmsh_executable/elmergrid_executable/elmersolver_executable
# override parameters -- same not-verified-against-real-binaries caveat as
# tests/test_elmer.py, whose module docstring carries the full citation
# list for the .geo/.sif/CLI formats these fakes stand in for.
# ---------------------------------------------------------------------------

_FAKE_GMSH_FOR_MCP_TEST = """
import sys
args = sys.argv[1:]
out = args[args.index("-o") + 1]
with open(out, "w") as f:
    f.write("$MeshFormat\\n2.2 0 8\\n$EndMeshFormat\\n")
sys.exit(0)
"""

_FAKE_ELMERGRID_FOR_MCP_TEST = """
import sys, os
args = sys.argv[1:]
out_dir = args[args.index("-out") + 1]
os.makedirs(out_dir, exist_ok=True)
with open(os.path.join(out_dir, "mesh.header"), "w") as f:
    f.write("fake mesh header\\n")
sys.exit(0)
"""

_FAKE_ELMERSOLVER_FOR_MCP_TEST = """
import sys
with open("scalar_values.dat.names", "w") as f:
    f.write("Variables in columns of matrix:\\n   1: Line Marker\\n   2: res: energy functional\\n")
with open("scalar_values.dat", "w") as f:
    f.write("1 4.2\\n")
sys.stdout.write("*** Elmer Solver: ALL DONE ***\\n")
sys.exit(0)
"""


def _write_fake_elmer_toolchain(tmp_path: Path):
    scripts = {}
    for name, body in (
        ("fake_gmsh.py", _FAKE_GMSH_FOR_MCP_TEST),
        ("fake_elmergrid.py", _FAKE_ELMERGRID_FOR_MCP_TEST),
        ("fake_elmersolver.py", _FAKE_ELMERSOLVER_FOR_MCP_TEST),
    ):
        scripts[name] = make_fake_executable(tmp_path, body, name=name.removesuffix(".py"))
    return scripts


def test_run_elmer_simulation_calls_through(tmp_path: Path):
    scripts = _write_fake_elmer_toolchain(tmp_path)

    geometry = {"domain": {"p1_m": [0.0, 0.0, 0.0], "p2_m": [0.1, 0.08, 0.06]}}
    result = server.run_elmer_simulation(
        geometry,
        frequency_hz=2.45e9,
        timeout_s=10,
        gmsh_executable=str(scripts["fake_gmsh.py"]),
        elmergrid_executable=str(scripts["fake_elmergrid.py"]),
        elmersolver_executable=str(scripts["fake_elmersolver.py"]),
    )

    assert result["provenance"] == "SIMULATED"
    assert result["simulator"] == "Elmer/VectorHelmholtz"
    assert result["status"] == "COMPLETED"
    assert result["completed_normally"] is True
    assert result["raw_scalars"]["computed"] is True
    assert result["s_parameters"]["computed"] is False
    assert result["far_field"]["computed"] is False


def test_run_palace_simulation_calls_through(tmp_path: Path, monkeypatch):
    script = _write_fake_palace(tmp_path)
    monkeypatch.setenv("PALACE_BIN", str(script))

    geometry = {
        "unit_cell": {"lx_m": 0.04, "ly_m": 0.01, "lz_m": 0.08},
        "materials": [
            {"p1_m": [0.01, 0.0, 0.0375], "p2_m": [0.03, 0.01, 0.0425], "epsilon_r": 7.0}
        ],
        "mesh": {"nx": 1, "ny": 1, "nz": 1},
    }
    result = server.run_palace_simulation(geometry, frequency_hz=10e9, timeout_s=10)

    assert result["provenance"] == "SIMULATED"
    assert result["simulator"] == "Palace"
    assert result["status"] == "COMPLETED"
    assert result["s_parameters"]["computed"] is True
    assert result["s_parameters"]["frequency_hz"] == pytest.approx([10e9])
    # Key carries the polarization: Palace reports every order in both.
    assert "S11_TE" in result["s_parameters"]["specular"]


# ---------------------------------------------------------------------------
# MEEP simulation (issue #60)
#
# MEEP genuinely is not installed in this environment (see tests/test_meep.py
# for the direct, unmockable proof). This test exercises only the MCP
# wrapper's parameter call-through to simulation.meep.run_meep_simulation,
# by monkeypatching the module-level `_run_meep_simulation` reference
# server.py calls through so it engages that function's own `meep_module`
# test-injection seam (documented on MeepSimulator.__init__) against a
# minimal fake -- same shape as tests/test_meep.py's FakeMeepModule, not
# re-imported here to keep this file self-contained like its NEC2++/
# openEMS/HFSS sections above.
# ---------------------------------------------------------------------------


def test_run_meep_simulation_is_registered():
    registered_names = {t.name for t in asyncio.run(server.mcp.list_tools())}
    assert "run_meep_simulation" in registered_names


def test_run_meep_simulation_calls_through(monkeypatch):
    from simulation.meep import run_meep_simulation as real_run_meep_simulation

    class _FakeFlux:
        def __init__(self, freqs, values):
            self.freqs = freqs
            self.values = values

    class _FakeMedium:
        def __init__(self, epsilon=1.0, mu=1.0):
            self.epsilon = epsilon
            self.mu = mu

    class _FakeSimulation:
        def __init__(self, module, **kwargs):
            self._module = module

        def add_flux(self, fcen, df, nfreq, region):
            return self._module._next_flux()

        def run(self, *step_funcs, **kwargs):
            pass

        def get_flux_data(self, flux):
            return {"saved_from": flux}

        def load_minus_flux_data(self, flux, data):
            pass

        def reset_meep(self):
            pass

    class _FakeMeepModuleForMcpTest:
        def __init__(self):
            freqs = [0.1]
            self._script = [(freqs, [0.0]), (freqs, [2.0]), (freqs, [-0.5])]
            self._index = 0
            self.inf = float("inf")
            self.metal = _FakeMedium(epsilon=-1e20)
            for name in ("Ex", "Ey", "Ez", "Hx", "Hy", "Hz"):
                setattr(self, name, name)

        def _next_flux(self):
            freqs, values = self._script[self._index]
            self._index += 1
            return _FakeFlux(freqs, values)

        def Vector3(self, x=0.0, y=0.0, z=0.0):
            return (x, y, z)

        def Medium(self, epsilon=1.0, mu=1.0, **kwargs):
            return _FakeMedium(epsilon=epsilon, mu=mu)

        def Block(self, material=None, center=None, size=None, **kwargs):
            return {"material": material, "center": center, "size": size}

        def Cylinder(self, **kwargs):
            return kwargs

        def PML(self, thickness, **kwargs):
            return {"thickness": thickness}

        def GaussianSource(self, frequency, fwidth=0.0, **kwargs):
            return {"frequency": frequency, "fwidth": fwidth}

        def Source(self, src, component=None, center=None, size=None, **kwargs):
            return {"src": src, "component": component}

        def FluxRegion(self, center=None, size=None, **kwargs):
            return {"center": center, "size": size}

        def Simulation(self, **kwargs):
            return _FakeSimulation(self, **kwargs)

        def get_fluxes(self, flux):
            return list(flux.values)

        def get_flux_freqs(self, flux):
            return list(flux.freqs)

        def stop_when_fields_decayed(self, dt, component, pt, decay_by):
            return None

    def fake_run(geometry, characteristic_length_m=1e-3, nfreq=1):
        return real_run_meep_simulation(
            geometry=geometry,
            characteristic_length_m=characteristic_length_m,
            nfreq=nfreq,
            meep_module=_FakeMeepModuleForMcpTest(),
        )

    monkeypatch.setattr(server, "_run_meep_simulation", fake_run)

    geometry = {
        "cell_size_m": [30e-3, 20e-3, 10e-3],
        "pml_thickness_m": 1e-3,
        "mesh_cell_size_m": 0.5e-3,
        "conductors": [
            {"name": "ground", "shape": "box", "p1_m": [0, 0, 0], "p2_m": [30e-3, 20e-3, 0]},
        ],
        "port": {
            "center_m": [-10e-3, 10e-3, 0.8e-3],
            "size_m": [0, 20e-3, 1.6e-3],
            "direction": "x",
            "frequency_hz": 2.45e9,
        },
        "reflection_monitor_center_m": [-8e-3, 10e-3, 0.8e-3],
        "reference_monitor_center_m": [12e-3, 10e-3, 0.8e-3],
    }
    result = server.run_meep_simulation(geometry)

    assert result["provenance"] == "SIMULATED"
    assert result["simulator"] == "MEEP"
    assert result["status"] == "COMPLETED"
    assert result["s_parameters"]["computed"] is True
    assert result["s_parameters"]["s11_magnitude"] == pytest.approx([0.5])


# ---------------------------------------------------------------------------
# FreeCAD curved/conformal host-surface geometry generation (issue #66)
#
# FreeCADCmd is not installed in this environment (matching this repo's
# other manually-installed simulator/geometry tools). This exercises the MCP
# wrapper's call-through to geometry.freecad_curved.run_freecad_curved_
# geometry against a small fake "FreeCADCmd" Python-shebang script, standing
# in for the real binary -- same fake-executable pattern as the Elmer
# section above (tests/test_elmer.py's own module docstring documents the
# discipline this mirrors).
# ---------------------------------------------------------------------------

_FAKE_FREECADCMD_FOR_MCP_TEST = """
import sys, json
status = {
    "objects_built": ["patch_0"],
    "errors": [],
    "step_file": "curved_unit_cell_array.step",
    "total_input": 1,
}
with open("curved_unit_cell_array_status.json", "w") as f:
    json.dump(status, f)
with open("curved_unit_cell_array.step", "w") as f:
    f.write("ISO-10303-21;\\nfake step file\\nEND-ISO-10303-21;\\n")
sys.exit(0)
"""


def _write_fake_freecadcmd(tmp_path: Path) -> Path:
    return make_fake_executable(tmp_path, _FAKE_FREECADCMD_FOR_MCP_TEST, name="fake_freecadcmd")


def test_run_freecad_curved_geometry_calls_through(tmp_path: Path, monkeypatch):
    script = _write_fake_freecadcmd(tmp_path)
    monkeypatch.setenv("FREECAD_BIN", str(script))

    primitives = [
        {
            "name": "patch",
            "shape": "box",
            "p1_m": [-0.001, -0.001, 0.0],
            "p2_m": [0.001, 0.001, 0.0016],
        }
    ]
    curvature = {"kind": "cylinder", "radius_m": 0.05, "axis": "z"}
    result = server.generate_freecad_curved_geometry(primitives, curvature, timeout_s=10)

    assert result["provenance"] == "SIMULATED"
    assert result["simulator"] == "FreeCADCmd"
    assert result["status"] == "COMPLETED"
    assert len(result["primitives"]) == 1
    assert result["primitives"][0]["shape"] == "polygon"
    assert result["freecad"]["objects_built"] == ["patch_0"]
    assert result["freecad"]["errors"] == []
    assert result["freecad"]["step_file"] is not None
