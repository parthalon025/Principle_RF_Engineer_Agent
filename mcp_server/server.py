import asyncio
from typing import Any

import numpy as np
from mcp.server.fastmcp import FastMCP

from designs.requirement_targets import confirm_requirement_target as _confirm_requirement_target
from designs.requirement_targets import (
    mark_requirement_unscoreable as _mark_requirement_unscoreable,
)
from designs.requirement_targets import (
    propose_requirement_target as _propose_requirement_target,
)
from designs.service import create_design as _create_design
from designs.service import read_design as _read_design
from designs.service import record_decision as _record_decision
from designs.service import record_engineering_result as _record_engineering_result
from designs.service import update_design_status as _update_design_status
from designs.service import verify_requirement as _verify_requirement
from geometry.freecad_curved import run_freecad_curved_geometry as _run_freecad_curved_geometry
from knowledge.component_resolution import (
    reconcile_components_from_matches as _reconcile_components_from_matches,
)
from knowledge.digikey import lookup_digikey_datasheet as _lookup_digikey_datasheet
from knowledge.extract import extract_components as _extract_components
from knowledge.index import index_document as _index_document
from knowledge.ingest import ingest_document as _ingest_document
from knowledge.mouser import lookup_mouser_datasheet as _lookup_mouser_datasheet
from knowledge.nexar import lookup_nexar_datasheet as _lookup_nexar_datasheet
from knowledge.read import read_document as _read_document
from knowledge.search import search_design_records as _search_design_records
from knowledge.search import search_knowledge as _search_knowledge
from knowledge.sourcing.arxiv import ingest_arxiv_paper as _ingest_arxiv_paper
from knowledge.sourcing.arxiv import search_arxiv_papers as _search_arxiv_papers
from knowledge.sourcing.etsi import ingest_etsi_standard as _ingest_etsi_standard
from knowledge.sourcing.fcc_ecfr import ingest_fcc_rule as _ingest_fcc_rule
from knowledge.sourcing.patent import ingest_patent as _ingest_patent
from knowledge.sourcing.threegpp import ingest_3gpp_spec as _ingest_3gpp_spec
from optimization.rf_objectives import (
    optimize_patch_length_for_target_frequency as _optimize_patch_length_for_target_frequency,
)
from orchestration.lab_test_plan import compile_lab_test_plan_for_loop as _compile_lab_test_plan
from orchestration.policy import assert_all_tools_categorized
from orchestration.solver import run_candidate_search as _run_candidate_search
from orchestration.tooling import advance_design_loop_step as _advance_design_loop_step
from orchestration.tooling import inspect_design_loop_state as _inspect_design_loop_state
from orchestration.tooling import start_new_design_loop as _start_new_design_loop
from rf_tools.calculations import (
    abcd_to_s,
    aperture_gain,
    cascade_gain_db,
    cascade_output_ip3_linear,
    curvature_length_correction_factor,
    curvature_shifted_resonant_frequency_hz,
    db_to_linear,
    fractional_bandwidth_from_q,
    free_space_path_loss_db,
    friis_noise_factor,
    iip3_from_oip3_db,
    input_stability_circle,
    l_network_match,
    linear_to_db,
    link_budget_margin_db,
    maxwell_garnett_effective_permeability,
    noise_factor_to_db,
    oip3_from_iip3_db,
    output_stability_circle,
    patch_effective_permittivity,
    patch_length_extension_m,
    patch_resonant_frequency_hz,
    quality_factor_from_fractional_bandwidth,
    quarter_wave_transformer_impedance,
    return_loss_db,
    rollett_k_factor,
    s_to_abcd,
    s_to_y,
    s_to_z,
    stability_verdict,
    third_order_intermod_dbc,
    third_order_intermod_output_dbm,
    two_port_stability_delta,
    vswr_from_gamma,
    wavelength,
    y_to_s,
    z_to_s,
)
from rf_tools.correlation import (
    correlate_simulation_measurement as _correlate_simulation_measurement,
)
from rf_tools.filter_synthesis import synthesize_filter
from rf_tools.touchstone import (
    analyze_touchstone,
    cascade_touchstone,
    compare_touchstone,
    deembed_touchstone,
    interpolate_touchstone,
)
from simulation.elmer import run_elmer_simulation as _run_elmer_simulation
from simulation.gprmax import run_gprmax_simulation as _run_gprmax_simulation
from simulation.hfss import run_hfss_simulation as _run_hfss_simulation
from simulation.kicad_gerber2ems import (
    run_kicad_gerber2ems_simulation as _run_kicad_gerber2ems_simulation,
)
from simulation.ltspice import run_ltspice_simulation as _run_ltspice_simulation
from simulation.meep import run_meep_simulation as _run_meep_simulation
from simulation.nec2pp import run_nec2_simulation as _run_nec2_simulation
from simulation.ngspice import run_ngspice_simulation as _run_ngspice_simulation
from simulation.openems import run_openems_simulation as _run_openems_simulation
from simulation.openparem import run_openparem_simulation as _run_openparem_simulation
from simulation.palace import run_palace_simulation as _run_palace_simulation
from simulation.qucs import run_qucs_simulation as _run_qucs_simulation
from simulation.xyce import run_xyce_simulation as _run_xyce_simulation

mcp = FastMCP("principal-rf-engineer")


@mcp.tool()
def calculate_wavelength(frequency_hz: float, design_id: int | None = None) -> float | dict:
    """Calculate free-space wavelength in meters. Pass design_id to also record this
    result as an engineering_results row against that design; the return value then
    gains a recorded_as field naming the new row's id."""
    result = wavelength(frequency_hz)
    if design_id is None:
        return result
    recorded = _record_engineering_result(
        design_id=design_id, tool_name="calculate_wavelength", value=result
    )
    return {"value": result, "recorded_as": recorded}


@mcp.tool()
def calculate_vswr(
    reflection_coefficient_magnitude: float, design_id: int | None = None
) -> float | dict:
    """Calculate VSWR from |Gamma|. Pass design_id to also record this result as an
    engineering_results row against that design; the return value then gains a
    recorded_as field naming the new row's id."""
    result = vswr_from_gamma(reflection_coefficient_magnitude)
    if design_id is None:
        return result
    recorded = _record_engineering_result(
        design_id=design_id, tool_name="calculate_vswr", value=result
    )
    return {"value": result, "recorded_as": recorded}


@mcp.tool()
def calculate_return_loss(
    reflection_coefficient_magnitude: float, design_id: int | None = None
) -> float | dict:
    """Calculate return loss in dB from |Gamma|. Pass design_id to also record this
    result as an engineering_results row against that design; the return value then
    gains a recorded_as field naming the new row's id."""
    result = return_loss_db(reflection_coefficient_magnitude)
    if design_id is None:
        return result
    recorded = _record_engineering_result(
        design_id=design_id, tool_name="calculate_return_loss", value=result
    )
    return {"value": result, "recorded_as": recorded}


@mcp.tool()
def calculate_cascade_gain(gains_db: list[float], design_id: int | None = None) -> float | dict:
    """Calculate cascaded gain in dB. Pass design_id to also record this result as an
    engineering_results row against that design; the return value then gains a
    recorded_as field naming the new row's id."""
    result = cascade_gain_db(gains_db)
    if design_id is None:
        return result
    recorded = _record_engineering_result(
        design_id=design_id, tool_name="calculate_cascade_gain", value=result
    )
    return {"value": result, "recorded_as": recorded}


@mcp.tool()
def calculate_noise_figure(
    noise_factors: list[float], gains_linear: list[float], design_id: int | None = None
) -> dict:
    """Calculate cascaded noise factor and noise figure. Pass design_id to also record
    this result as an engineering_results row against that design; the return value
    then gains a recorded_as field naming the new row's id."""
    f_total = friis_noise_factor(noise_factors, gains_linear)
    result = {
        "noise_factor": f_total,
        "noise_figure_db": noise_factor_to_db(f_total),
        "provenance": "CALCULATED",
    }
    if design_id is not None:
        result["recorded_as"] = _record_engineering_result(
            design_id=design_id, tool_name="calculate_noise_figure", value=result
        )
    return result


@mcp.tool()
def analyze_touchstone_file(path: str, design_id: int | None = None) -> dict:
    """Analyze a local Touchstone network file. Pass design_id to also record this
    result as an engineering_results row against that design; the return value then
    gains a recorded_as field naming the new row's id."""
    result = analyze_touchstone(path)
    result["provenance"] = "CALCULATED"
    if design_id is not None:
        result["recorded_as"] = _record_engineering_result(
            design_id=design_id, tool_name="analyze_touchstone_file", value=result
        )
    return result


# ---------------------------------------------------------------------------
# Phase 1-2 calculations and Touchstone capabilities as tools (issue #36).
#
# Every tool below wraps its return value in a dict carrying
# "provenance": "CALCULATED", following the pattern calculate_noise_figure
# already established above (unlike the four oldest tools, which return bare
# floats -- pre-existing inconsistency, not fixed here per the ticket).
#
# Matrix convention (S/Z/Y/ABCD conversions and the stability-circle tools,
# which all take a two-port matrix): a matrix is a plain nested list
# `[[a, b], [c, d]]`; each entry is either a real number or a Python
# complex()-parseable string (e.g. "1+2j", "0.5-0.3j" -- exactly what
# Python's own `str(complex(...))` produces). Every tool's matrix/complex
# *output* uses this same string convention, so a tool's output can be fed
# straight into another conversion tool's input without reformatting.
# ---------------------------------------------------------------------------


def _complex_matrix_to_strings(matrix) -> list[list[str]]:
    """Convert a 2x2 complex matrix into the nested-list-of-complex()-parseable-strings
    convention documented above."""
    return [[str(complex(entry)) for entry in row] for row in np.asarray(matrix)]


@mcp.tool()
def convert_db_to_linear(db: float) -> dict:
    """Convert a dB value to its linear (power ratio) equivalent."""
    return {"linear_value": db_to_linear(db), "provenance": "CALCULATED"}


@mcp.tool()
def convert_linear_to_db(value: float) -> dict:
    """Convert a linear (power ratio) value to dB."""
    return {"db_value": linear_to_db(value), "provenance": "CALCULATED"}


@mcp.tool()
def convert_s_to_z(s_params: list[list[complex]], z0: float = 50.0) -> dict:
    """Convert a two-port S-parameter matrix to Z-parameters relative to z0.
    See the matrix convention documented in this module's Phase 1-2 tools section."""
    z = s_to_z(s_params, z0)
    return {"z_params": _complex_matrix_to_strings(z), "provenance": "CALCULATED"}


@mcp.tool()
def convert_z_to_s(z_params: list[list[complex]], z0: float = 50.0) -> dict:
    """Convert a two-port Z-parameter matrix to S-parameters relative to z0.
    Same matrix convention as convert_s_to_z."""
    s = z_to_s(z_params, z0)
    return {"s_params": _complex_matrix_to_strings(s), "provenance": "CALCULATED"}


@mcp.tool()
def convert_s_to_y(s_params: list[list[complex]], z0: float = 50.0) -> dict:
    """Convert a two-port S-parameter matrix to Y-parameters relative to z0.
    Same matrix convention as convert_s_to_z."""
    y = s_to_y(s_params, z0)
    return {"y_params": _complex_matrix_to_strings(y), "provenance": "CALCULATED"}


@mcp.tool()
def convert_y_to_s(y_params: list[list[complex]], z0: float = 50.0) -> dict:
    """Convert a two-port Y-parameter matrix to S-parameters relative to z0.
    Same matrix convention as convert_s_to_z."""
    s = y_to_s(y_params, z0)
    return {"s_params": _complex_matrix_to_strings(s), "provenance": "CALCULATED"}


@mcp.tool()
def convert_s_to_abcd(s_params: list[list[complex]], z0: float = 50.0) -> dict:
    """Convert a two-port S-parameter matrix to ABCD-parameters relative to z0.
    Same matrix convention as convert_s_to_z."""
    abcd = s_to_abcd(s_params, z0)
    return {"abcd_params": _complex_matrix_to_strings(abcd), "provenance": "CALCULATED"}


@mcp.tool()
def convert_abcd_to_s(abcd_params: list[list[complex]], z0: float = 50.0) -> dict:
    """Convert a two-port ABCD-parameter matrix to S-parameters relative to z0.
    Same matrix convention as convert_s_to_z."""
    s = abcd_to_s(abcd_params, z0)
    return {"s_params": _complex_matrix_to_strings(s), "provenance": "CALCULATED"}


@mcp.tool()
def calculate_free_space_path_loss(distance_km: float, freq_mhz: float) -> dict:
    """Calculate free-space path loss (FSPL) in dB for a distance in km and frequency
    in MHz."""
    return {
        "path_loss_db": free_space_path_loss_db(distance_km, freq_mhz),
        "provenance": "CALCULATED",
    }


@mcp.tool()
def calculate_link_budget_margin(
    tx_power_dbm: float,
    tx_antenna_gain_db: float,
    path_loss_db: float,
    rx_antenna_gain_db: float,
    rx_sensitivity_dbm: float,
    other_losses_db: float = 0.0,
) -> dict:
    """Calculate link margin in dB: how far received power sits above receiver
    sensitivity, given transmit power/gain, path loss, receive gain/sensitivity."""
    margin = link_budget_margin_db(
        tx_power_dbm,
        tx_antenna_gain_db,
        path_loss_db,
        rx_antenna_gain_db,
        rx_sensitivity_dbm,
        other_losses_db,
    )
    return {"margin_db": margin, "provenance": "CALCULATED"}


@mcp.tool()
def calculate_cascade_output_ip3(oip3_linear: list[float], gains_linear: list[float]) -> dict:
    """Calculate cascaded output-referred third-order intercept (OIP3), linear units,
    for a chain of stages given in signal-flow order."""
    return {
        "oip3_linear": cascade_output_ip3_linear(oip3_linear, gains_linear),
        "provenance": "CALCULATED",
    }


@mcp.tool()
def calculate_oip3_from_iip3(iip3_dbm: float, gain_db: float) -> dict:
    """Calculate output-referred IP3 (dBm) from input-referred IP3 and stage gain (dB)."""
    return {"oip3_dbm": oip3_from_iip3_db(iip3_dbm, gain_db), "provenance": "CALCULATED"}


@mcp.tool()
def calculate_iip3_from_oip3(oip3_dbm: float, gain_db: float) -> dict:
    """Calculate input-referred IP3 (dBm) from output-referred IP3 and stage gain (dB)."""
    return {"iip3_dbm": iip3_from_oip3_db(oip3_dbm, gain_db), "provenance": "CALCULATED"}


@mcp.tool()
def calculate_third_order_intermod_output(pout_dbm: float, oip3_dbm: float) -> dict:
    """Calculate the two-tone third-order intermodulation (IM3) product power,
    output-referred, in dBm."""
    return {
        "im3_output_dbm": third_order_intermod_output_dbm(pout_dbm, oip3_dbm),
        "provenance": "CALCULATED",
    }


@mcp.tool()
def calculate_third_order_intermod_dbc(pout_dbm: float, oip3_dbm: float) -> dict:
    """Calculate the two-tone IM3 product level relative to the carrier, in dBc."""
    return {
        "im3_dbc": third_order_intermod_dbc(pout_dbm, oip3_dbm),
        "provenance": "CALCULATED",
    }


@mcp.tool()
def calculate_stability_delta(s_params: list[list[complex]]) -> dict:
    """Calculate the two-port determinant Delta = S11*S22 - S12*S21.
    Same matrix convention as convert_s_to_z; delta is a complex()-parseable string."""
    delta = two_port_stability_delta(s_params)
    return {"delta": str(complex(delta)), "provenance": "CALCULATED"}


@mcp.tool()
def calculate_rollett_k_factor(s_params: list[list[complex]]) -> dict:
    """Calculate the Rollett stability factor K for a two-port network's S-parameters.
    Same matrix convention as convert_s_to_z."""
    return {"k_factor": rollett_k_factor(s_params), "provenance": "CALCULATED"}


@mcp.tool()
def calculate_stability_verdict(s_params: list[list[complex]]) -> dict:
    """Determine the unconditional/conditional-stability verdict (K > 1 and |Delta| < 1)
    for a two-port network. Same matrix convention as convert_s_to_z."""
    return {"verdict": stability_verdict(s_params), "provenance": "CALCULATED"}


@mcp.tool()
def calculate_output_stability_circle(s_params: list[list[complex]]) -> dict:
    """Calculate the output (load-plane) stability circle center and radius.
    Same matrix convention as convert_s_to_z; center is a complex()-parseable string."""
    center, radius = output_stability_circle(s_params)
    return {"center": str(complex(center)), "radius": radius, "provenance": "CALCULATED"}


@mcp.tool()
def calculate_input_stability_circle(s_params: list[list[complex]]) -> dict:
    """Calculate the input (source-plane) stability circle center and radius.
    Same matrix convention as convert_s_to_z; center is a complex()-parseable string."""
    center, radius = input_stability_circle(s_params)
    return {"center": str(complex(center)), "radius": radius, "provenance": "CALCULATED"}


@mcp.tool()
def calculate_quarter_wave_transformer_impedance(z_source: float, z_load: float) -> dict:
    """Calculate the characteristic impedance of a quarter-wave transformer matching two
    real (resistive) impedances."""
    return {
        "transformer_impedance_ohms": quarter_wave_transformer_impedance(z_source, z_load),
        "provenance": "CALCULATED",
    }


@mcp.tool()
def calculate_l_network_match(z_source: float, z_load: complex) -> dict:
    """Synthesize a lossless L-network matching a complex z_load to a real z_source.
    Returns one or two independent (series reactance ohms, shunt susceptance siemens)
    solutions."""
    solutions = l_network_match(z_source, z_load)
    return {
        "solutions": [
            {"series_reactance_ohms": x, "shunt_susceptance_siemens": b} for x, b in solutions
        ],
        "provenance": "CALCULATED",
    }


@mcp.tool()
def synthesize_filter_prototype(
    response: str,
    band: str,
    order: int,
    impedance_ohm: float = 50.0,
    ripple_db: float | None = None,
    cutoff_hz: float | None = None,
    center_hz: float | None = None,
    bandwidth_hz: float | None = None,
    first_element: str = "shunt",
) -> dict:
    """Synthesize a lumped-element ladder filter from a specification (issue #143).

    response: "butterworth" (maximally flat, no pass-band ripple) or "chebyshev"
    (equal-ripple -- accepts a stated pass-band wobble in exchange for a sharper
    cut-off at the same order). band: "lowpass"/"highpass" (need cutoff_hz) or
    "bandpass"/"bandstop" (need center_hz and bandwidth_hz). ripple_db is required
    for chebyshev and rejected for butterworth. first_element picks between the two
    equivalent ladders ("shunt" = capacitor-input, "series" = inductor-input).

    Returns the prototype g-values and the ladder as ideal inductor/capacitor values
    in henries and farads. Note load_impedance_ohm: an even-order Chebyshev is
    deliberately NOT terminated in the source impedance. For bandpass/bandstop,
    center_hz is the geometric centre, so the band edges are not center_hz +/-
    bandwidth_hz/2. Ideal lumped elements only -- physical realization (microstrip
    stubs, coupled lines, real vendor parts) is a separate step."""
    network = synthesize_filter(
        response=response,
        band=band,
        order=order,
        impedance_ohm=impedance_ohm,
        ripple_db=ripple_db,
        cutoff_hz=cutoff_hz,
        center_hz=center_hz,
        bandwidth_hz=bandwidth_hz,
        first_element=first_element,
    )
    return {**network.to_dict(), "provenance": "CALCULATED"}


@mcp.tool()
def calculate_patch_effective_permittivity(eps_r: float, w_m: float, h_m: float) -> dict:
    """Calculate the effective dielectric constant of a microstrip patch
    (transmission-line model). Only valid for patch width/substrate-thickness W/h > 1."""
    return {
        "eps_eff": patch_effective_permittivity(eps_r, w_m, h_m),
        "provenance": "CALCULATED",
    }


@mcp.tool()
def calculate_patch_length_extension(eps_eff: float, w_m: float, h_m: float) -> dict:
    """Calculate the fringing-field length extension dL (metres) for a microstrip patch."""
    return {
        "length_extension_m": patch_length_extension_m(eps_eff, w_m, h_m),
        "provenance": "CALCULATED",
    }


@mcp.tool()
def calculate_patch_resonant_frequency(
    eps_r: float, w_m: float, h_m: float, l_m: float, c_m_s: float = 299_792_458.0
) -> dict:
    """Calculate the dominant-mode (TM010) resonant frequency of a flat rectangular
    microstrip patch, from substrate properties and patch dimensions."""
    return {
        "resonant_frequency_hz": patch_resonant_frequency_hz(eps_r, w_m, h_m, l_m, c_m_s),
        "provenance": "CALCULATED",
    }


@mcp.tool()
def calculate_fractional_bandwidth_from_q(q: float, vswr: float = 2.0) -> dict:
    """Calculate fractional impedance bandwidth from quality factor Q, for a given VSWR
    threshold (defaults to the standard 2:1 VSWR bandwidth definition)."""
    return {
        "fractional_bandwidth": fractional_bandwidth_from_q(q, vswr),
        "provenance": "CALCULATED",
    }


@mcp.tool()
def calculate_quality_factor_from_fractional_bandwidth(fbw: float, vswr: float = 2.0) -> dict:
    """Calculate quality factor Q from fractional impedance bandwidth, for a given VSWR
    threshold (defaults to the standard 2:1 VSWR bandwidth definition)."""
    return {
        "quality_factor": quality_factor_from_fractional_bandwidth(fbw, vswr),
        "provenance": "CALCULATED",
    }


@mcp.tool()
def calculate_curvature_length_correction_factor(l_m: float, radius_of_curvature_m: float) -> dict:
    """Calculate the first-order geometric length-correction factor (L/chord) for a
    patch bent to a radius of curvature. Restricted to L/R < 0.5; approximation only."""
    return {
        "correction_factor": curvature_length_correction_factor(l_m, radius_of_curvature_m),
        "provenance": "CALCULATED",
    }


@mcp.tool()
def calculate_curvature_shifted_resonant_frequency(
    f_flat_hz: float, l_m: float, radius_of_curvature_m: float
) -> dict:
    """Estimate a nominally-flat patch design's resonant frequency once conformed to a
    curved host surface. First-order geometric approximation, not a substitute for
    simulation or measurement."""
    return {
        "resonant_frequency_hz": curvature_shifted_resonant_frequency_hz(
            f_flat_hz, l_m, radius_of_curvature_m
        ),
        "provenance": "CALCULATED",
    }


@mcp.tool()
def calculate_maxwell_garnett_effective_permeability(
    fill_fraction: float, mu_r: float, mu_host: float = 1.0
) -> dict:
    """Calculate the effective relative permeability of a dilute array of magnetic
    metamaterial elements (Maxwell-Garnett mixing formula). Dilute-limit approximation;
    treat fill_fraction >~ 0.3 as outside its comfortable validity range."""
    return {
        "mu_eff": maxwell_garnett_effective_permeability(fill_fraction, mu_r, mu_host),
        "provenance": "CALCULATED",
    }


@mcp.tool()
def calculate_aperture_gain(
    area_m2: float, freq_hz: float, aperture_efficiency: float = 0.55
) -> dict:
    """Calculate the estimated linear gain of an aperture antenna from its physical area,
    frequency, and aperture efficiency (defaults to a nominal 0.55 planning value)."""
    return {
        "gain_linear": aperture_gain(area_m2, freq_hz, aperture_efficiency),
        "provenance": "CALCULATED",
    }


def _network_summary(network) -> dict:
    """Build the same summary shape as analyze_touchstone_file (port count, frequency
    range, S11/S21 extrema), from an in-memory skrf.Network rather than a file on disk --
    shared by the tools below whose underlying rf_tools.touchstone function returns a
    Network instead of reading one from a path."""
    result: dict = {
        "ports": int(network.nports),
        "frequency_start_hz": float(network.f[0]),
        "frequency_stop_hz": float(network.f[-1]),
        "points": int(len(network.f)),
        "z0": np.asarray(network.z0).tolist(),
    }
    if network.nports >= 2:
        s11_db = 20 * np.log10(np.maximum(np.abs(network.s[:, 0, 0]), 1e-15))
        s21_db = 20 * np.log10(np.maximum(np.abs(network.s[:, 1, 0]), 1e-15))
        result["s11_min_db"] = float(np.min(s11_db))
        result["s21_max_db"] = float(np.max(s21_db))
        result["s11_min_frequency_hz"] = float(network.f[np.argmin(s11_db)])
        result["s21_max_frequency_hz"] = float(network.f[np.argmax(s21_db)])
    return result


@mcp.tool()
def interpolate_touchstone_file(path: str, target_freqs_hz: list[float]) -> dict:
    """Interpolate a Touchstone network's S-parameters onto a new frequency grid (Hz) and
    summarize the result (same shape as analyze_touchstone_file). Every target frequency
    must fall within the source network's original range -- extrapolation is rejected."""
    network = interpolate_touchstone(path, target_freqs_hz)
    result = _network_summary(network)
    result["provenance"] = "CALCULATED"
    return result


@mcp.tool()
def deembed_touchstone_file(
    measured_path: str, fixture_path: str, output_fixture_path: str | None = None
) -> dict:
    """De-embed a test fixture's effect from a measured Touchstone network and summarize
    the recovered device-under-test response (same shape as analyze_touchstone_file). Pass
    output_fixture_path for a fixture on both sides (same path twice for a symmetric one)."""
    network = deembed_touchstone(measured_path, fixture_path, output_fixture_path)
    result = _network_summary(network)
    result["provenance"] = "CALCULATED"
    return result


@mcp.tool()
def cascade_touchstone_files(paths: list[str]) -> dict:
    """Cascade an ordered chain of two-port Touchstone networks front-to-back and
    summarize the end-to-end result (same shape as analyze_touchstone_file). Every
    network must be a two-port sharing the same reference impedance."""
    network = cascade_touchstone(paths)
    result = _network_summary(network)
    result["provenance"] = "CALCULATED"
    return result


def _jsonify_comparison(result: dict) -> dict:
    """Convert a compare_touchstone-shaped dict's complex numpy arrays into
    JSON-safe values -- shared by compare_touchstone_files and
    correlate_simulated_and_measured below, both of which embed this exact
    per-S-parameter shape."""
    jsonified: dict = {}
    for key, value in result.items():
        if isinstance(value, dict) and "diff" in value:
            jsonified[key] = {
                "diff": [str(complex(x)) for x in value["diff"]],
                "magnitude_diff_db": [float(x) for x in value["magnitude_diff_db"]],
                "max_magnitude_diff_db": value["max_magnitude_diff_db"],
                "rms_diff": value["rms_diff"],
                "max_abs_diff": value["max_abs_diff"],
            }
        else:
            jsonified[key] = value
    return jsonified


@mcp.tool()
def compare_touchstone_files(path_a: str, path_b: str) -> dict:
    """Quantify how two Touchstone networks differ, per S-parameter (max/RMS magnitude
    difference and per-point complex difference across their common frequency grid). Both
    networks must have the same port count and an overlapping frequency range."""
    jsonified = _jsonify_comparison(compare_touchstone(path_a, path_b))
    jsonified["provenance"] = "CALCULATED"
    return jsonified


@mcp.tool()
def correlate_simulated_and_measured(
    simulated: dict,
    measured: dict,
    fixture_path: str | None = None,
    output_fixture_path: str | None = None,
    temperature_tolerance_c: float = 5.0,
) -> dict:
    """Correlate a SIMULATED result against a MEASURED result so you can judge how much
    to trust a given simulation for future design decisions on similar geometries:
    normalizes the two onto a common frequency grid and reference impedance (reusing
    compare_touchstone/interpolate_touchstone), de-embeds fixture effects when
    fixture_path is given (reusing deembed_touchstone -- SKIPPED, and said so in the
    result, when omitted), and returns a quantified per-S-parameter comparison, not a
    bare pass/fail. `simulated`/`measured` each accept a dict shaped like
    measurement/external.py's record_external_measurement output
    (frequency_hz/s_parameters/z0), or one carrying a "touchstone_file" path -- see
    rf_tools/correlation.py's module docstring for exactly which of run_nec2_simulation's/
    run_openems_simulation's current outputs this can and cannot use yet (NEC2++'s
    single-frequency impedance and openEMS's stubbed S-parameters are both honestly
    rejected, not fabricated from). Temperature normalization is a documented no-op
    unless both inputs happen to carry a "temperature_c" field, since no current
    simulator/external-measurement source populates one --
    see the returned temperature_note. Returns "CALCULATED" provenance for the
    correlation result itself, alongside the input results' own SIMULATED/MEASURED
    provenance tags."""
    result = _correlate_simulation_measurement(
        simulated=simulated,
        measured=measured,
        fixture_path=fixture_path,
        output_fixture_path=output_fixture_path,
        temperature_tolerance_c=temperature_tolerance_c,
    )
    result["comparison"] = _jsonify_comparison(result["comparison"])
    return result


@mcp.tool()
def run_nec2_simulation(geometry: dict, frequency_hz: float, timeout_s: int = 600) -> dict:
    """Simulate a wire-antenna structure with NEC2++: generate a NEC2 card deck from
    structured geometry (wires with tag/segments/endpoints/radius in meters, optional
    ground_condition "free_space"/"perfect"/finite-ground dict, optional excitation and
    pattern-sweep overrides -- see simulation.nec2pp.generate_nec2_deck for the full
    shape), run it via nec2++, and parse impedance/radiation-pattern/gain from the
    output. Returns "SIMULATED" provenance. Deck/output format verified against the
    primary NEC-2 documentation (see simulation/nec2pp.py's module docstring for the
    citation) but NOT against a real nec2++ binary -- none is installed in this
    environment; treat any result as unverified end-to-end until it has been run
    against the real tool at least once."""
    return _run_nec2_simulation(geometry=geometry, frequency_hz=frequency_hz, timeout_s=timeout_s)


@mcp.tool()
def run_openems_simulation(geometry: dict, fdtd: dict | None = None, timeout_s: int = 3600) -> dict:
    """Simulate a conformal/metamaterial antenna structure with openEMS (FDTD):
    generate an FDTD-XML file from structured geometry (box/cylinder material and
    conductor primitives in meters, one or more lumped ports with direction/
    resistance_ohms/frequency_hz, and explicit rectilinear mesh lines -- see
    simulation.openems.generate_openems_xml for the full shape), run it via openEMS,
    and return convergence metadata (energy end-criteria vs. max-timesteps exit) plus
    S-parameter/far-field result keys. Use this over run_nec2_simulation for
    conformal/curved or metamaterial geometry NEC2++'s wire method-of-moments can't
    adequately model. Returns "SIMULATED" provenance. S-parameters are REAL -- FFT-
    computed from the run's port ProbeBox voltage/current time-domain dumps -- when
    those dump files are present (this module's own XML now requests them); they fall
    back to an honestly-flagged computed=False when they aren't (e.g. a run that
    genuinely didn't produce them). SCOPE LIMIT: far-field extraction is still NOT
    computed -- it requires openEMS's separate nf2ff tool, out of scope for this pass
    (see simulation/openems.py's module docstring). Format verified against primary
    openEMS/CSXCAD documentation (see simulation/openems.py's module docstring for
    citations) but NOT against a real openEMS binary -- none is installed in this
    environment."""
    return _run_openems_simulation(geometry=geometry, fdtd=fdtd, timeout_s=timeout_s)


@mcp.tool()
def run_qucs_simulation(circuit: dict, analysis: dict, timeout_s: int = 600) -> dict:
    """Simulate a lumped-element/transmission-line circuit (a matching network,
    filter, or feed network -- schematic-level circuit simulation, the free/GPL
    alternative to Keysight ADS this repo has no adapter for) with Qucs-S's
    qucsator_rf engine: generate a netlist from structured circuit input (ports
    with node/impedance, plus R/L/C/TLIN components with node connections -- see
    simulation.qucs.generate_qucs_netlist for the full shape), run it via
    qucsator_rf, and parse the FULL native N-port S-parameter matrix out of the
    result in one run (unlike run_openems_simulation, which only yields the
    excited port's own column per run). Returns "SIMULATED" provenance, plus a
    "touchstone_file" (any port count) when the ports are contiguously numbered
    1..N, ready for correlate_simulated_and_measured/compare_touchstone_files.
    `analysis` sets the frequency sweep: {"sweep_type": "lin"|"log" (default
    "lin"), "start_hz", "stop_hz" (both required), "points" (default 201)}.
    Netlist/dataset format verified against qucsator_rf's own primary source
    (see simulation/qucs.py's module docstring for the full citation list) but
    NOT against a real qucsator_rf binary -- none is installed in this
    environment. IMPORTANT: the real executable this adapter shells out to is
    named "qucsator_rf", not the bare "qucsator" its upstream project is
    colloquially called -- see that module docstring for why."""
    return _run_qucs_simulation(circuit=circuit, analysis=analysis, timeout_s=timeout_s)


@mcp.tool()
def run_gprmax_simulation(geometry: dict, fdtd: dict | None = None, timeout_s: int = 3600) -> dict:
    """Simulate a ground-coupled or lossy-half-space antenna structure with gprMax (FDTD):
    generate a .in file from structured geometry (an optional lossy dielectric ground
    half-space, box/cylinder/edge/plate material and PEC conductor primitives in metres,
    and a single #transmission_line excitation port -- see
    simulation.gprmax.generate_gprmax_input for the full shape), run it via
    "python -m gprMax" (gprMax has no standalone binary), and return S-parameters/input
    impedance FFT-computed from the port's own incident/total voltage-current dumps, plus
    any declared receivers' raw field data. Use this over run_nec2_simulation/
    run_openems_simulation when the antenna's host surface is a real lossy dielectric half-
    space (soil, concrete, a vehicle hull) rather than free space or an idealized ground
    plane -- NEC2++'s ground models can't represent that, and openEMS's adapter has no
    explicit ground-half-space workflow either. Returns "SIMULATED" provenance.
    IMPORTANT: this adapter deliberately does NOT use gprMax's bundled antenna-model
    library (GSSI/MALA) -- those are calibrated replicas of specific commercial GPR
    antenna hardware, not stand-ins for this repo's own antenna designs (see
    simulation/gprmax.py's module docstring "ADAPTATION WORK"). SCOPE LIMIT: far-field/
    gain extraction is NOT computed -- gprMax has no near-field-to-far-field tool at all
    (see simulation/gprmax.py's module docstring). Format verified against primary
    gprMax documentation (see simulation/gprmax.py's module docstring for citations) but
    NOT against a real gprMax run -- gprMax is not installed in this environment and
    (unlike NEC2++/openEMS) cannot be installed via pip at all, only via a conda + C-
    compiler source build (see that module's "CORRECTION" section); treat any result as
    unverified end-to-end until it has been run against the real tool at least once."""
    return _run_gprmax_simulation(geometry=geometry, fdtd=fdtd, timeout_s=timeout_s)


@mcp.tool()
def run_hfss_simulation(
    geometry: dict,
    frequency_hz: float,
    sweep: dict | None = None,
    project_name: str = "hfss_project",
    design_name: str = "hfss_design",
) -> dict:
    """Simulate a structure with HFSS via PyAEDT: create a project, apply geometry
    (box material/conductor primitives with materials in meters, a lumped port,
    length-based mesh -- see simulation.hfss._apply_hfss_geometry for the full
    shape), solve, extract S-parameters, export a Touchstone file, and archive the
    solved project plus extracted report. Returns "SIMULATED" provenance. CRITICAL:
    unlike run_nec2_simulation/run_openems_simulation, HFSS is commercial, licensed
    software that fundamentally cannot run without a paid license -- execution is
    confined to a configured, explicitly-designated licensed workstation and
    refuses to run anywhere else (see simulation/hfss.py's check_hfss_workstation_
    confinement). PyAEDT API call shapes are verified against the primary
    ansys/pyaedt GitHub source (see simulation/hfss.py's module docstring for the
    full citation list) but NOT against a real HFSS/AEDT installation -- none is
    licensed or available in this environment, and none genuinely can be."""
    return _run_hfss_simulation(
        geometry=geometry,
        frequency_hz=frequency_hz,
        sweep=sweep,
        project_name=project_name,
        design_name=design_name,
    )


@mcp.tool()
def run_openparem_simulation(
    mesh_file: str,
    ports: dict,
    project: dict | None = None,
    project_name: str = "openparem_project",
    mpi_processes: int | None = None,
    timeout_s: int = 3600,
) -> dict:
    """Simulate a structure with OpenParEM3D (full-wave FEM): given an already-meshed
    Gmsh msh22 `mesh_file` (mesh generation is out of scope -- see simulation/
    openparem.py's module docstring SCOPE; produce one via FreeCAD+gmsh first) and
    structured `ports` geometry (Path/Boundary/Port definitions -- see
    simulation.openparem.generate_openparem_ports_file for the full shape), generate
    the `.proj` project-control file (frequency plan, mesh/refinement settings,
    reference impedance, Touchstone format -- see simulation.openparem.
    generate_openparem_project_config for the full `project` shape) plus the ports
    file, run OpenParEM3D, and parse S-parameters AND antenna far-field gain/
    directivity/radiation-efficiency from the SAME FEM solve -- no separate tool or
    manual post-processing step. Set `project["far_field"] = {"quantity": "G"}` (or
    "D" for directivity) to request far-field metrics; this only actually computes
    when `ports["boundaries"]` includes a `type="radiation"` boundary. Returns
    "SIMULATED" provenance with `s_parameters`/`far_field` each honestly flagged
    computed=True/False (never fabricated) plus a `touchstone_file` key when a
    single-port renormalized Touchstone was written. `.proj`/ports-file format and
    CLI invocation verified against OpenParEM's own primary GitHub source and its
    official Installation Manual PDF (see simulation/openparem.py's module docstring
    for the full citation list) but NOT against a real OpenParEM3D binary -- none is
    installed in this environment. OpenParEM is also considerably younger and less
    battle-tested than NEC2++/openEMS/HFSS (initial release Sept. 2024)."""
    return _run_openparem_simulation(
        mesh_file=mesh_file,
        ports=ports,
        project=project,
        project_name=project_name,
        mpi_processes=mpi_processes,
        timeout_s=timeout_s,
    )


@mcp.tool()
def run_elmer_simulation(
    geometry: dict,
    frequency_hz: float,
    timeout_s: int = 1800,
    gmsh_executable: str | None = None,
    elmergrid_executable: str | None = None,
    elmersolver_executable: str | None = None,
) -> dict:
    """Simulate a structure with Elmer FEM's VectorHelmholtz module (a general,
    multiphysics-ready EM cross-check for a FUTURE coupled-physics need, e.g. EM/
    thermal on a mounted "adaptive EM skin" -- NOT a replacement for run_nec2_
    simulation/run_openems_simulation/run_hfss_simulation on everyday antenna work):
    generate a Gmsh OpenCASCADE .geo script from structured geometry (a single
    rectangular domain with isotropic material, plus an optional rectangular
    excitation sub-region -- see simulation.elmer.generate_gmsh_geo_script for the
    full shape), mesh it with gmsh, convert the mesh to ElmerSolver's native format
    with ElmerGrid, generate a matching VectorHelmholtz .sif (see simulation.elmer.
    generate_elmer_sif), run it with ElmerSolver, and parse whatever raw output is
    available. Returns "SIMULATED" provenance. CRITICAL SCOPE LIMIT: Elmer's
    VectorHelmholtz module has NO native antenna-specific port/S-parameter/far-field/
    gain post-processing (unlike OpenParEM/Palace) -- this tool's excitation
    (impressed "Body Force"/"Current Density" current source) and boundary conditions
    (PEC "E Re"/"E Im"=0, or the solver's own generic "Absorbing BC" flag) are
    hand-assembled, real FEM techniques but NOT a calibrated port; "s_parameters" and
    "far_field" are therefore ALWAYS returned computed=False with an explanatory note,
    never fabricated -- see simulation/elmer.py's module docstring "SCOPE AND
    LIMITATIONS" for the full detail. .geo/.sif/CLI format verified against Gmsh's own
    official reference manual and ElmerGrid's/ElmerSolver's own primary GitHub source
    (see simulation/elmer.py's module docstring for the full citation list, each fact
    graded by confidence) but NOT against real gmsh/ElmerGrid/ElmerSolver binaries --
    none is installed in this environment; treat any result as unverified end-to-end
    until it has been run against the real tools at least once."""
    return _run_elmer_simulation(
        geometry=geometry,
        frequency_hz=frequency_hz,
        timeout_s=timeout_s,
        gmsh_executable=gmsh_executable,
        elmergrid_executable=elmergrid_executable,
        elmersolver_executable=elmersolver_executable,
    )


@mcp.tool()
def generate_freecad_curved_geometry(
    primitives: list[dict],
    curvature: dict,
    timeout_s: int = 600,
    executable: str | None = None,
) -> dict:
    """Map a FLAT unit-cell/array layout (a list of this repo's own "box"/"polygon"
    geometry-dict primitives -- e.g. straight out of geometry.unit_cell.
    generate_unit_cell_array()/generate_metamaterial_array(), issue #55) onto a curved
    host surface (a cylinder or a sphere, described by `curvature`) -- the case a
    perfectly flat unit-cell layout gets physically wrong: an antenna wrapped around a
    real fuselage/missile-body/radome has its elements stretched, tilted, and
    repositioned by the host's own curvature, which a flat layout ignores. Returns
    THIS REPO'S OWN existing geometry-dict "polygon" primitive shape (drops straight
    into run_openems_simulation's/run_palace_simulation's own
    geometry["conductors"]/geometry["materials"] list) -- computed via pure curvature
    trigonometry, always available even without FreeCAD installed -- PLUS drives a
    headless FreeCADCmd Python macro (no GUI dependency, see geometry/
    freecad_curved.py's module docstring for the FreeCAD-source citations) that builds
    the SAME array as a real, exact 3D solid model (each cell correctly tilted to the
    surface's true local normal, a "box" primitive's thickness correctly extruded
    along that true normal rather than the flat layout's own Z axis) and exports it to
    a STEP file. CRITICAL SCOPE LIMIT: CSXCAD's own Polygon primitive can only lie in
    a plane perpendicular to a global x/y/z axis, so the returned geometry-dict is a
    "staircase"-style approximation -- each cell individually snapped to whichever
    cardinal axis its own true local surface normal is closest to (the same kind of
    approximation an FDTD solver's own rectilinear mesh already makes for any curved
    boundary), NOT the exact tilted plane the FreeCAD-built STEP model represents; each
    returned primitive carries a non-standard, informational `approx_sag_m` field
    quantifying exactly how much that approximation cost for that cell. Returns
    "SIMULATED" provenance. FreeCADCmd's headless invocation and every FreeCAD Python
    API call used were verified directly against FreeCAD's own C++/`.pyi` source on
    GitHub (see geometry/freecad_curved.py's module docstring for the full citation
    list) but NOT against a real FreeCADCmd binary -- none is installed in this
    environment; treat the FreeCAD-built STEP model as unverified end-to-end until it
    has been run against the real tool at least once (the geometry-dict mapping itself
    is pure Python, exercised directly in tests, and needs no FreeCAD install)."""
    return _run_freecad_curved_geometry(
        primitives=primitives,
        curvature=curvature,
        timeout_s=timeout_s,
        executable=executable,
    )


@mcp.tool()
def run_ltspice_simulation(
    netlist: str | None = None,
    netlist_file: str | None = None,
    timeout_s: int = 600,
) -> dict:
    """Simulate a circuit with LTspice (ADS alternative, part 3 of 3 -- issue
    #59): run an existing SPICE netlist (either `netlist`, raw netlist text,
    or `netlist_file`, a path to an existing .net/.cir/.asc file already on
    disk; exactly one is required) through LTspice's real batch-mode CLI
    (driven via the spicelib package -- see simulation/ltspice.py's module
    docstring for the primary-source citation), and parse the resulting
    .raw output into structured trace data (plot type, axis, and every
    named trace, complex for an AC analysis or real for a transient/DC
    sweep) via spicelib's own RawRead. Returns "SIMULATED" provenance.
    LOWEST PRIORITY / LOWEST INVESTMENT of this batch's "ADS alternative"
    simulators: LTspice is the one non-open-source item here (free-of-
    charge proprietary Analog Devices freeware, NOT OSI-approved -- see
    docs/LICENSE_MATRIX.md) and is capability-redundant with any ngspice/
    Xyce/Qucs-S adapter this repo may also have. Unlike run_nec2_
    simulation/run_openems_simulation, this tool does NOT generate a
    netlist from a structured component dict -- bring your own. spicelib
    is an OPTIONAL install (`pip install '.[ltspice]'` / `uv sync --extra
    ltspice`); this tool raises a clear SimulatorError, not a bare
    ImportError, if it isn't installed. Format/invocation verified against
    spicelib's own primary GitHub source but NOT against a real LTspice
    binary -- none is installed in this environment."""
    return _run_ltspice_simulation(netlist=netlist, netlist_file=netlist_file, timeout_s=timeout_s)


@mcp.tool()
def run_kicad_gerber2ems_simulation(board_file: str, config: dict, timeout_s: int = 3600) -> dict:
    """Derive PCB signal-integrity simulation geometry from a REAL, as-laid-out KiCad
    PCB design (a .kicad_pcb file) -- NOT a hand-modeled geometry dict -- and simulate
    it with gerber2ems (which drives openEMS internally through its own Python
    interface, with its own config schema; this is a separate pipeline from
    run_openems_simulation, not built on top of it). Connects to a headless KiCad
    instance via kicad-python's IPC API, exports the board's Gerber/drill/position
    fileset plus a translated stackup.json, writes gerber2ems's own simulation.json
    from `config` (REQUIRED: `{"frequency": {"start": hz, "stop": hz}}`; optional
    "ports"/"traces"/"differential_pairs"/"grid"/"max_steps"/"pixel_size"/"via" in
    gerber2ems's own schema -- see simulation.kicad_gerber2ems.generate_gerber2ems_
    config for the full shape), runs `gerber2ems -a`, and parses its per-port results.

    SCOPED EXPLICITLY TO PCB SIGNAL-INTEGRITY RESULTS -- trace impedance and
    via/stackup S-parameters, per gerber2ems's own actual scope -- NOT antenna
    far-field/gain patterns; gerber2ems has no far-field capability at all, so
    (unlike run_openems_simulation) this tool's result carries no far-field key to
    even stub. Returns "SIMULATED" provenance. REQUIRES the PCB design to already
    place "Simulation_Port"-valued footprints (reference designators SP1, SP2, ...)
    at the trace endpoints of interest -- this is gerber2ems's own PCB-design-time
    port-discovery convention, not something this tool can synthesize. Format/API
    verified against gerber2ems's and kicad-python's own primary sources (see
    simulation/kicad_gerber2ems.py's module docstring for the full citation list)
    but NOT against a real KiCad/kicad-cli/gerbv/gerber2ems/openEMS installation --
    none is installed in this environment; treat any result as unverified end-to-end
    until it has been run against the real tools at least once. One honestly-flagged
    gap beyond that: kicad-python's drill export does not yet expose a plated/
    non-plated-hole split, so a board with unplated holes may get a mis-labeled drill
    file (see that module's own docstring and each result's own `warnings`)."""
    return _run_kicad_gerber2ems_simulation(
        board_file=board_file, config=config, timeout_s=timeout_s
    )


@mcp.tool()
def run_ngspice_simulation(job: dict, timeout_s: int = 600) -> dict:
    """Simulate a matching network, filter, or amplifier bias/termination sub-circuit
    with ngspice (a free/open circuit-level SPICE simulator, no paid ADS license
    needed): generate a netlist from a structured job dict (R/L/C/V/I components,
    optional "raw_cards" escape hatch for nonlinear devices/subcircuits, an
    op/ac/tran "analysis", and node-voltage/branch-current "outputs" -- see
    simulation.ngspice.generate_ngspice_netlist for the full shape), run it via
    ngspice, and parse the requested outputs' AC (real/imag pairs vs. frequency),
    TRAN (values vs. time), or OP data back out. Returns "SIMULATED" provenance.
    SCOPE LIMIT: S-parameters are NOT computed -- stable ngspice has no built-in
    S-parameter analysis; use run_xyce_simulation's native `.LIN` S-parameter/
    Touchstone path for that need instead. Netlist/output format verified against
    the primary ngspice manual (see simulation/ngspice.py's module docstring for
    the citation) but NOT against a real ngspice binary -- none is installed in
    this environment."""
    return _run_ngspice_simulation(job=job, timeout_s=timeout_s)


@mcp.tool()
def run_xyce_simulation(job: dict, timeout_s: int = 600) -> dict:
    """Simulate a matching network, filter, or amplifier bias/termination sub-circuit
    with Xyce (Sandia's free/open parallel-capable circuit simulator, no paid ADS
    license needed -- prefer this over run_ngspice_simulation for a larger circuit or
    when real S-parameters are needed): generate a netlist from a structured job dict
    (R/L/C/V/I components, optional "raw_cards" escape hatch, an op/ac/tran
    "analysis", optional node-voltage/branch-current "outputs", and optional "ports"
    -- see simulation.xyce.generate_xyce_netlist for the full shape), run it via
    Xyce, and return the requested `.PRINT` outputs (CSV columns vs. frequency/time)
    and/or, when "ports" are given (requires analysis type "ac"), REAL S-parameters
    extracted via Xyce's native `.LIN` linear-network analysis and exported to a
    genuine Touchstone file (surfaced as "touchstone_file", integrating with
    correlate_simulated_and_measured the same way simulation/hfss.py's and
    simulation/openems.py's computed=True S-parameters do). Returns "SIMULATED"
    provenance. HONEST CONFIDENCE CAVEAT: the `.LIN` S-parameter path is verified
    against Xyce's own primary Reference Guide but carries one extra notch of
    uncertainty beyond this tool's `.AC`/`.TRAN`/`.PRINT` coverage -- see
    simulation/xyce.py's module docstring "HONEST CONFIDENCE CAVEAT ON `.LIN`
    SPECIFICALLY" for why. Format verified against the primary Xyce Reference Guide
    (see simulation/xyce.py's module docstring for the citation) but NOT against a
    real Xyce binary -- none is installed in this environment."""
    return _run_xyce_simulation(job=job, timeout_s=timeout_s)


@mcp.tool()
def run_palace_simulation(
    geometry: dict,
    frequency_hz: float,
    sweep: dict | None = None,
    num_processes: int = 1,
    timeout_s: int = 3600,
    solver_order: int = 1,
) -> dict:
    """Simulate a periodic metamaterial unit cell with Palace, a full-wave finite-element
    solver with NATIVE Floquet/periodic-boundary ports -- the only simulator in this
    repo that can characterize a repeating-element design's actual electromagnetic
    behavior (neither run_nec2_simulation's method-of-moments nor run_openems_
    simulation's FDTD adapter expose periodic boundaries). Generates a structured
    hexahedral mesh (MFEM .mesh format) and a Palace JSON config for a rectangular unit
    cell -- periodic in x/y, a Floquet port on each of its two z-normal faces, zero or
    more embedded axis-aligned dielectric material boxes -- from structured geometry
    (unit_cell lx_m/ly_m/lz_m, optional materials list, optional floquet wave-vector/
    polarization/max_order overrides -- see simulation.palace.generate_palace_mesh and
    generate_palace_config for the full shape), runs it via the real `palace` binary,
    and parses port-floquet-S.csv into structured per-diffraction-order S-parameter
    data (plus a "specular" convenience view keyed "S11_TE"/"S21_TE"/... for the
    fundamental order -- the key carries the polarization because Palace reports both,
    and the co-polarized one is whichever matches the polarization you asked for).
    `solver_order` is the finite-element order: 1 (Palace's own default) is fast and
    approximate, 2 is what Palace's own worked example uses and what reproduced its
    published answers. Returns "SIMULATED" provenance. Embedded PEC conductor patches
    (a metallic metasurface, as opposed to an all-dielectric grating/photonic-crystal
    unit cell) are NOT supported in this pass -- see simulation/palace.py's module
    docstring. This adapter HAS been run end to end against a real palace binary
    (issue #210): driving Palace's own "Floquet Ports for a Dielectric Grating"
    example through this exact function reproduced Palace's published S-parameters to
    within 0.056 dB and 0.91 degrees, and agreed on which diffraction orders
    propagate. That is one all-dielectric geometry at one incidence angle, and it is
    still a simulation agreeing with a simulation -- nothing here has been checked
    against a bench measurement. See docs/palace-floquet-validation.md."""
    return _run_palace_simulation(
        geometry=geometry,
        frequency_hz=frequency_hz,
        sweep=sweep,
        num_processes=num_processes,
        timeout_s=timeout_s,
        solver_order=solver_order,
    )


@mcp.tool()
def run_meep_simulation(
    geometry: dict,
    characteristic_length_m: float = 1e-3,
    nfreq: int = 1,
) -> dict:
    """Simulate a structure with MEEP (FDTD, driven as a Python library, not a
    subprocess binary) as a SECOND, INDEPENDENT full-wave EM solver you can cross-
    check a design decision against instead of resting on run_openems_simulation's
    output alone -- e.g. run the same geometry through both and compare |S11|. Takes
    box/cylinder dielectric materials and PEC conductors in meters (see
    simulation.meep.run_meep_simulation for the full geometry shape), a single port
    modeled as a Gaussian-pulse source plus a reflection-flux monitor (MEEP has no
    lumped-RLC-port concept the way openEMS/HFSS do -- see simulation/meep.py's PORT
    MODEL caveat), and returns "SIMULATED" provenance. IMPORTANT SCOPE LIMITS: POWER
    quantities only -- power reflectance and its magnitude |S11| are always computed
    (via MEEP's own documented flux-subtraction technique), and power TRANSMITTANCE
    (how much of the arriving power goes straight through and out the far side) is
    computed too IF you ask for it by putting a "transmission_monitor_center_m" plane
    in `geometry`; without it no transmission monitor is built and the result says
    "not requested" rather than a misleading zero. NO complex phase, so no complex
    S21 and no multi-port S-matrix, NO Touchstone export, and NO far-field/gain (see
    simulation/meep.py's module docstring SCOPE section). This tool does NOT compute
    absorption: 1 - R - T is a reading of two measurements, not a measurement.
    `characteristic_length_m` is MEEP's own dimensionless-unit lengthscale "a"
    (default 1mm). Geometry/units translation verified against MEEP's own primary
    documentation (see simulation/meep.py's module docstring for the citation), and
    the underlying physics recipe and unit conversions have been checked against a
    real pymeep 1.34.0 install on three reference cases with known answers
    (docs/meep-absorber-validation.md), two of them driving THIS adapter's own path
    end to end via verification/meep_adapter_transmittance_check.py and
    verification/meep_two_port_absorption_check.py -- but MEEP is not installed in
    the interpreter this application runs under (no PyPI wheel, no native Windows
    support: conda-forge only, WSL required on Windows; the Dockerfile puts it in a
    separate conda env named by MEEP_PYTHON, which this adapter shells out to), and
    CI has no solver at all, so treat a result on a geometry unlike those reference
    cases as unverified end-to-end."""
    return _run_meep_simulation(
        geometry=geometry, characteristic_length_m=characteristic_length_m, nfreq=nfreq
    )


@mcp.tool()
def optimize_patch_length_for_target_frequency(
    eps_r: float,
    w_m: float,
    h_m: float,
    target_frequency_hz: float,
    length_lower_m: float,
    length_upper_m: float,
    method: str = "bayesian",
    n_evaluations: int = 20,
) -> dict:
    """Search microstrip patch length (substrate eps_r/h_m and patch width w_m held
    fixed) in [length_lower_m, length_upper_m] for the value whose TM010 resonant
    frequency (patch_resonant_frequency_hz) is closest to target_frequency_hz. method
    selects the search: "sweep" (evenly-spaced points), "grid" (equivalent to sweep in
    this single-parameter case), or "bayesian" (from-scratch Gaussian-process
    optimization -- see optimization/bayesian.py), each using n_evaluations calls to the
    underlying calculation. This is the one concrete case (issue #41) wiring this
    project's optimization/ package across the MCP JSON boundary: the objective itself
    -- patch_resonant_frequency_hz -- is fixed/named, not an arbitrary callable, since
    only JSON-serializable arguments can cross this boundary (see
    optimization/rf_objectives.py's module docstring for the full rationale). Returns
    "CALCULATED" provenance, tagged with the method, objective description, and the
    fixed eps_r/w_m/h_m constraints that produced it."""
    return _optimize_patch_length_for_target_frequency(
        eps_r=eps_r,
        w_m=w_m,
        h_m=h_m,
        target_frequency_hz=target_frequency_hz,
        length_lower_m=length_lower_m,
        length_upper_m=length_upper_m,
        method=method,
        n_evaluations=n_evaluations,
    )


# ---------------------------------------------------------------------------
# Controlled autonomous design-iteration loop (issue #46, Phase 12 -- the
# final ticket of the 23-ticket build-out). Three focused tools mirroring
# agent/main.py's principal-role wiring -- see orchestration/design_loop.py
# and orchestration/tooling.py for the state machine and approval-gate
# design. advance_design_loop_step's `approval` is required whenever the
# loop's current step is ARCHITECTURE, MEASUREMENT, or REDESIGN_DECISION;
# there is no tool here (or anywhere in this project) that can produce a
# granted loop-step approval, and no code path from this loop to a
# manufacturing-release action.
#
# start_design_loop creates a real `designs` row backing the loop, and
# advance_design_loop_step's REDESIGN_DECISION transition flushes that
# iteration's decisions to the database (docs/adr/0011) -- see
# orchestration/tooling.py's module docstring for the persistence design.
# ---------------------------------------------------------------------------


@mcp.tool()
def start_design_loop(design_key: str, name: str, revision: str, requirements: dict) -> dict:
    """Start a new controlled design-iteration loop, backed by a real
    `designs` row created in `DRAFT` status (docs/adr/0011). `design_key`/
    `name`/`revision` are exactly `designs.service.create_design`'s own
    fields. `requirements` must be in that function's shape -- a dict
    keyed by `requirement_id`, each value a dict carrying a non-empty
    string `requirement` field -- not the older free-form "customer
    requirement" shape (frequency band, gain/VSWR/bandwidth target, form
    factor, host-surface curvature, platform); those details can still go
    in each requirement's extra keys or its `requirement` prose. A
    rejected `requirements` shape raises DesignLoopPersistenceError and no
    loop is started. Returns the new loop's state, positioned at the
    ARCHITECTURE step and carrying `design_id` -- hold onto this dict and
    pass it back into advance_design_loop_step for every subsequent call;
    it is the whole loop's session token (this project has no long-running
    server process, so the state itself is not persisted server-side --
    only the loop's history, once flushed at an iteration boundary, is)."""
    return _start_new_design_loop(design_key, name, revision, requirements)


@mcp.tool()
def advance_design_loop_step(state: dict, step_input: dict, approval: dict | None = None) -> dict:
    """Advance a design-iteration loop from its current step to the next
    one: requirements -> architecture -> analysis -> simulation ->
    optimization -> verification -> measurement -> correlation -> redesign.
    `state` is a prior call's returned loop state; `step_input` is step-
    specific (see orchestration/design_loop.py's per-step handlers).
    `approval` is REQUIRED whenever the loop is currently at ARCHITECTURE,
    MEASUREMENT, or REDESIGN_DECISION -- every step that is not a pure
    calculation or simulation run -- and must be bound to this exact loop/
    iteration/step/step_input combination or this raises and the loop does
    not advance. Check the returned state's "pending_approval" key to see,
    at any point, whether the loop is blocked on an approval.

    A REDESIGN_DECISION transition also flushes that iteration's decisions
    to the database and advances the backing design's status (docs/adr/
    0011). A failed flush raises DesignLoopPersistenceError instead of
    returning -- the caller's already-held `state` remains the only valid
    state."""
    return _advance_design_loop_step(state, step_input, approval=approval)


@mcp.tool()
def inspect_design_loop_state(state: dict) -> dict:
    """Return a design-iteration loop's current state -- current step,
    every decision recorded so far with its own provenance, and whether an
    approval is currently pending (and for which step). Safe to call at any
    point mid-loop, not just at completion; does not mutate or advance the
    loop.

    When `state` carries a `design_id`, this opens a real database
    connection and substitutes `requirements` with a fresh read of the
    persisted `designs.requirements` column (issue #100), so a target
    proposed or confirmed via `designs.requirement_targets` after `state`
    was captured is reflected here without the caller re-reading the
    design themselves -- everything else is passed through unchanged,
    read-only. Without a `design_id`, this never touches the database and
    `requirements` is returned exactly as given."""
    return _inspect_design_loop_state(state)


@mcp.tool()
def compile_lab_test_plan(state: dict) -> dict:
    """Compile a batched lab-test plan (issue #94) for every requirement on
    this design: what to measure, by what method, and what value this
    iteration's own recorded CALCULATED/SIMULATED engineering results
    already predict -- so one lab trip is enough. A requirement with no
    proposed target, an explicitly UNSCOREABLE one, one whose quantity a
    Touchstone S-parameter sweep cannot report (e.g. antenna gain or
    radiation pattern -- needs a range/chamber, not a bench VNA), or one
    with nothing computed this iteration to predict from is flagged with a
    distinguishing reason, not silently dropped -- see
    orchestration/lab_test_plan.py's own docstring for the full design.

    `state` is a state dict from start_design_loop/advance_design_loop_step/
    inspect_design_loop_state -- safe to call at any point in the loop, on
    any current_step. Read-only: advances nothing, writes nothing to the
    database, and needs no approval receipt."""
    return _compile_lab_test_plan(state)


@mcp.tool()
def run_candidate_search(
    state: dict,
    candidates: list,
    score_specs: dict,
    evaluation_budget: int | None = None,
    plateau_window: int = 5,
    plateau_epsilon: float = 0.5,
    target_satisfaction_threshold: float = 100.0,
) -> dict:
    """The candidate solver (issue #95, docs/adr/0014): drive a batch of
    proposed candidate parameter sets through a design loop's ungated
    ANALYSIS -> SIMULATION -> OPTIMIZATION span, scoring each scoreable
    step against a stated requirement target, candidate after candidate,
    stopping on target satisfaction, a score plateau, or the evaluation
    budget -- see orchestration/solver.py's module docstring for the full
    design.

    `state` must already be positioned past ARCHITECTURE (inside an
    approved architecture) and must be a tooling-shaped state dict (from
    start_design_loop or a prior advance_design_loop_step call, carrying
    design_id). `candidates` is a non-empty list of dicts, each supplying
    the fields the driven steps need. `score_specs` names which steps to
    score and against what target (a designs.requirement_targets
    PROPOSED/CONFIRMED target), keyed by step name ("analysis"/
    "simulation"/"optimization").

    This tool NEVER constructs, forges, or accepts an approval receipt,
    and never calls request_loop_step_approval -- every step it drives is,
    by construction, outside GATED_STEPS. If the state handed in is
    already sitting at a gated step (ARCHITECTURE/MEASUREMENT/
    REDESIGN_DECISION), this returns normally with
    stop_reason="gated_step_pending_approval" and the loop's own
    pending_approval report -- it never raises to signal this. Reaching
    VERIFICATION/CORRELATION/REQUIREMENTS similarly halts with
    stop_reason="out_of_scope_step".

    A stop_reason="score_plateau" result is not the same signal as
    target_satisfaction or evaluation_budget: it means the running-best
    overall_score_percent stopped improving by more than plateau_epsilon
    across the last plateau_window candidates -- it does NOT mean this
    architecture's OPTIMIZATION is exhausted. Read a plateau stop as a cue
    to construct and submit ONE more batch that is deliberately different
    from the one that just plateaued -- built on a different region of the
    parameter space, or a different construction/proposal strategy, never
    a near-identical resubmission with minor tweaks -- before concluding
    parameter-level search is exhausted for this architecture. Only after
    that second, deliberately-different batch also plateaus should the
    caller move on to compile_lab_test_plan or a REDESIGN_DECISION for
    this architecture.

    Returns a report dict: stop_reason/stop_detail naming exactly why the
    search stopped, an ordered `trail` (one entry per candidate actually
    evaluated, each carrying its own per-step score trail), and
    best_candidate_state -- the winning candidate's own tooling-shaped
    state dict, ready to hand straight back into advance_design_loop_step
    to continue the design (its decisions persist at the existing
    REDESIGN_DECISION flush once that continuation reaches it, docs/adr/
    0011 -- this tool itself never flushes anything)."""
    return _run_candidate_search(
        state,
        candidates,
        score_specs,
        evaluation_budget=evaluation_budget,
        plateau_window=plateau_window,
        plateau_epsilon=plateau_epsilon,
        target_satisfaction_threshold=target_satisfaction_threshold,
    )


@mcp.tool()
def ingest_document(
    file_path: str,
    source_type: str,
    license: str,
    classification: str,
    supersedes_document_id: int | None = None,
    author: str | None = None,
    revision: str | None = None,
) -> dict:
    """Parse a document PDF via docling, chunk it, and store it. source_type must be one
    of: datasheet, application_note, standard, textbook, paper, patent, partner_research,
    design_record -- it is fixed at ingest time and sets the document's default provenance
    and authority rank, so a wrong value permanently mis-ranks everything retrieved from
    it. Note patent: its numbers are citable evidence but rank below a peer-reviewed paper
    (a patent office does not check that a stated number reproduces), and its claim text is
    legal boundary-setting, never design guidance. Note partner_research (ADR-0029):
    unpublished technical work received from an outside research partner -- use this, not
    paper (which would overclaim peer review, outranking even a granted patent) or
    design_record (which claims a document as this team's own authorship); it ranks between
    patent and design_record and gets no structured component extraction, same as
    paper/patent. Pass supersedes_document_id to declare this upload a newer revision of
    that document (never inferred from title); omit it for a plain new, independent
    document. author/revision are stored as-is on the document (both optional) -- for a
    partner_research document, author should identify the partner/author, since a partner
    source is not much use without knowing whose work it is."""
    return _ingest_document(
        file_path=file_path,
        source_type=source_type,
        license=license,
        classification=classification,
        supersedes_document_id=supersedes_document_id,
        author=author,
        revision=revision,
    )


@mcp.tool()
def ingest_arxiv_paper(
    arxiv_id: str,
    license: str,
    classification: str,
    supersedes_document_id: int | None = None,
) -> dict:
    """Fetch and convert an arXiv preprint (e.g. "2401.01234", or the older
    "cond-mat/0207270" form) into the knowledge base as source_type='paper'.
    Uses the arxiv-doc-builder skill to fetch LaTeX source (preferred) + PDF and
    convert to Markdown via pandoc -- preserving math/structure far better than
    feeding a raw PDF to docling -- falling back to naive PDF text extraction
    when no LaTeX source exists. Automatically pulls title/authors/publication
    date/DOI/journal/categories/abstract from arXiv's own record into the
    stored document. license must be the reuse terms that actually apply to
    this specific paper (arXiv's default license does not itself grant
    downstream reuse beyond citation/summary; check for an author-chosen CC0/
    CC-BY license). authority_rank is always overridden below the peer-
    reviewed 'paper' default, since arXiv preprints are not peer-reviewed --
    only a "superficial" moderator check. Pass supersedes_document_id to
    declare this upload a newer revision of that document (never inferred)."""
    return _ingest_arxiv_paper(
        arxiv_id,
        license=license,
        classification=classification,
        supersedes_document_id=supersedes_document_id,
    )


@mcp.tool()
def search_arxiv_papers(query: str, max_results: int = 10) -> list:
    """Search arXiv by topic/keyword (issue #257) and return a ranked list of
    candidates for review -- NOT documents in the corpus. Each candidate carries
    id/title/published/abstract; use "search precedent before inventing" (CLAUDE.md)
    to judge relevance before spending an ingestion pass on it. Pass a chosen
    candidate's id straight to ingest_arxiv_paper unchanged, along with the license/
    classification ADR-0001 requires for that specific paper -- this tool never calls
    ingest_document itself, so finding a paper here never counts as trusting it.
    query is arXiv's search_query syntax (a bare keyword string, e.g. "conformal
    metamaterial absorber", or field-prefixed, e.g. "abs:magnetic mirror AND
    cat:physics.app-ph") searched over titles/abstracts/authors/categories -- not
    ingest_arxiv_paper's id_list-style fetch by already-known identifier. A topic
    with no matches returns [] (a real "nobody has published this" result); an
    unreachable arXiv API raises instead of returning an empty list, so the two
    cases are never confused."""
    return _search_arxiv_papers(query, max_results=max_results)


@mcp.tool()
def ingest_3gpp_spec(
    spec_number: str,
    version: str,
    license: str,
    classification: str,
    supersedes_document_id: int | None = None,
) -> dict:
    """Download a 3GPP specification from 3GPP's own open FTP archive (no
    registration/credential needed) and ingest it into the knowledge base as
    source_type='standard'. Fetch-by-identifier only, not search -- you must
    already know the identifier:
    spec_number: the spec's own number, e.g. "38.331" (or a multi-part spec
    like "38.521-1", dash kept intact).
    version: 3GPP's own version string exactly as it appears in the archive
    filename, e.g. "h00" -- not a bare revision letter or a guess.
    3GPP specs are free to download but are NOT public domain -- copyright is
    jointly held by the 3GPP Organizational Partners and each document
    carries its own reproduction-restriction notice. license must be the
    reuse terms that actually apply; this tool does not assume a default.
    Extracts the single .docx/.doc member from the downloaded zip (preferring
    .docx). A legacy pre-2020ish .doc spec docling can't parse still stores
    the document row with extraction_status="failed" rather than raising --
    expect zero chunks in that case. Pass supersedes_document_id to declare
    this upload a newer revision of that document (never inferred from
    title); omit it for a plain new, independent document."""
    return _ingest_3gpp_spec(
        spec_number,
        version,
        license=license,
        classification=classification,
        supersedes_document_id=supersedes_document_id,
    )


@mcp.tool()
def ingest_etsi_standard(
    document_url: str,
    license: str,
    classification: str,
    supersedes_document_id: int | None = None,
) -> dict:
    """Download an ETSI standard PDF and ingest it into the knowledge base as
    source_type='standard'. Fetch-by-identifier only, not search -- and
    unlike ingest_3gpp_spec/ingest_fcc_rule, the identifier here is a full
    URL, not a bare document number: ETSI's per-document "deliver" path
    (document-type folder, a grouped numeric-range folder, the document-
    number folder, a version folder, then the filename) is not mechanically
    derivable from a bare standard number alone, and no confirmed public
    search API exists to script that lookup -- only ETSI's own human-facing
    standards-search UI (https://www.etsi.org/standards-search) resolves a
    document number to its deliver path today.
    document_url: the full deliverable URL, e.g. "https://www.etsi.org/
    deliver/etsi_ts/119600_119699/119612/02.02.01_60/ts_119612v020201p.pdf"
    -- must be an https://www.etsi.org/deliver/... URL (no registration
    needed to fetch it), obtained however you already found it (e.g. from
    the standards-search UI or a citation).
    ETSI standards are free to download but carry ETSI's own copyright and
    (F)RAND patent terms, same internal-use posture as 3GPP. license must be
    the reuse terms that actually apply; this tool does not assume a
    default. Pass supersedes_document_id to declare this upload a newer
    revision of that document (never inferred from title); omit it for a
    plain new, independent document."""
    return _ingest_etsi_standard(
        document_url,
        license=license,
        classification=classification,
        supersedes_document_id=supersedes_document_id,
    )


@mcp.tool()
def ingest_fcc_rule(
    part: int,
    license: str,
    classification: str,
    title: int = 47,
    supersedes_document_id: int | None = None,
) -> dict:
    """Fetch FCC rule text via eCFR's public versioner API (no
    authentication) and ingest it into the knowledge base as
    source_type='standard'. Fetch-by-identifier only, not search -- you must
    already know the identifier:
    part: the CFR part number, e.g. 15 for the Part 15 unlicensed-device
    rules, or 97 for the Part 97 amateur-radio rules.
    title: the CFR title number, default 47 (Telecommunication) -- pass a
    different title only if you genuinely need rule text outside Title 47.
    Always resolves the current edition date from eCFR's own titles.json
    first (an arbitrary caller-supplied date can 404 against eCFR's
    versioner), then flattens the fetched Federal-Register XML to plain text
    locally before ingesting (docling does not support that XML DTD).
    eCFR content is public domain as a work of the U.S. Government -- the
    strongest license status of any source this package ingests -- but is
    explicitly not the official legal edition (GPO's Federal Register
    printing is authoritative); flag that distinction if a result is ever
    used for formal regulatory sign-off. license must still be the reuse
    terms that actually apply; this tool does not assume a default. Pass
    supersedes_document_id to declare this upload a newer revision of that
    document (never inferred from title); omit it for a plain new,
    independent document."""
    return _ingest_fcc_rule(
        part,
        license=license,
        classification=classification,
        title=title,
        supersedes_document_id=supersedes_document_id,
    )


@mcp.tool()
def ingest_patent(
    patent_number: str,
    license: str,
    classification: str,
    supersedes_document_id: int | None = None,
    render_page_images: bool = True,
) -> dict:
    """Fetch a US patent document from the USPTO and ingest it as
    source_type='patent'. Takes either a granted patent number ("US12089385B2",
    "12089385") or the pre-grant publication number of the same application
    ("US 2022/0192066 A1", "20220192066") -- the same invention published at two
    moments, often worth ingesting both. It cannot look one number up from the
    other, and it does not search: call it once per number you have.
    Which conversion runs depends on what is in the file, not on which number
    you gave. Every USPTO PDF measured so far is a scan -- a photograph of the
    page with no machine-readable text -- so the usual path hands the PDF to the
    normal ingest pipeline, whose OCR transcribes it, and renders every page to
    an image so the drawings can be read by eye. A PDF that does carry real text
    is converted to Markdown two columns at a time, the way a patent is printed,
    with the front-page fields (title, inventors, assignee, dates, application
    number) parsed into its header; anything the page did not yield stays empty
    rather than guessed. render_page_images=False skips the image rendering.
    authority_rank is NOT overridden: source_type='patent' already defaults below
    a peer-reviewed paper. A patent's CLAIMS are legal boundary-setting, never
    design guidance. Pass supersedes_document_id to declare this a newer revision
    of a stored document (never inferred)."""
    return _ingest_patent(
        patent_number,
        license=license,
        classification=classification,
        supersedes_document_id=supersedes_document_id,
        render_page_images=render_page_images,
    )


@mcp.tool()
def index_document(document_id: int, requested_backend: str | None = None) -> dict:
    """Embed a stored document's chunks and write the vectors. SENSITIVE/RESTRICTED
    documents always use the self-hosted backend, no fallback to external."""
    return _index_document(document_id=document_id, requested_backend=requested_backend)


@mcp.tool()
def read_document(document_id: int) -> dict:
    """Fetch a stored document's full metadata plus its chunks (content, page number,
    section) in order. Returns a not-found result rather than raising if document_id
    doesn't exist."""
    return _read_document(document_id)


@mcp.tool()
def search_knowledge(query_text: str, document_id: int | None = None, limit: int = 20) -> list:
    """Search the knowledge base and return one ranked list of chunk matches, each
    tagged with its match_type ("semantic_external", "semantic_local", or "lexical").
    Defaults to ACTIVE documents only; pass document_id to search a specific
    document/revision (including a SUPERSEDED one) instead."""
    return _search_knowledge(query_text=query_text, document_id=document_id, limit=limit)


@mcp.tool()
def search_design_records(query_text: str, document_id: int | None = None, limit: int = 20) -> list:
    """Search for prior design/decision records relevant to query_text -- e.g. by
    component, frequency band, or design pattern -- to find precedent before proposing
    a new design. A thin wrapper around search_knowledge scoped to
    source_type="design_record" documents; same ranking and match_type semantics."""
    return _search_design_records(query_text=query_text, document_id=document_id, limit=limit)


@mcp.tool()
def extract_components(document_id: int, requested_backend: str | None = None) -> dict:
    """Extract structured component specifications from a stored datasheet/application_note
    and upsert a components row per part. Runs automatically, no confirmation step.
    SENSITIVE/RESTRICTED documents always use the self-hosted backend, no fallback to
    external."""
    return _extract_components(document_id=document_id, requested_backend=requested_backend)


@mcp.tool()
def lookup_digikey_component(part_number: str, license: str, classification: str) -> dict:
    """Search Digi-Key's Product Information API v4 for part_number, download its
    datasheet PDF, and ingest it via ingest_document (source_type='datasheet'),
    unchanged. Refuses to run unless ALLOW_EXTERNAL_NETWORK_TOOLS=true AND
    DIGIKEY_CLIENT_ID/DIGIKEY_CLIENT_SECRET are configured. Returns {"status":
    "no_match" | "no_datasheet" | "ok", ...}; on "ok", manufacturer/
    manufacturer_part_number are Digi-Key's own report of the part's identity, for
    reconcile_component_sources to cross-check against Mouser's/Nexar's hit for the
    same part. NOT run against the real API in this environment -- see
    knowledge/digikey.py's module docstring."""
    return _lookup_digikey_datasheet(part_number, license=license, classification=classification)


@mcp.tool()
def lookup_mouser_component(part_number: str, license: str, classification: str) -> dict:
    """Same contract as lookup_digikey_component, against Mouser's Search API
    (MOUSER_API_KEY). NOT run against the real API in this environment -- see
    knowledge/mouser.py's module docstring."""
    return _lookup_mouser_datasheet(part_number, license=license, classification=classification)


@mcp.tool()
def lookup_nexar_component(part_number: str, license: str, classification: str) -> dict:
    """Same contract as lookup_digikey_component, against Nexar's GraphQL API
    (Octopart data; NEXAR_CLIENT_ID/NEXAR_CLIENT_SECRET). NOT run against the real API
    in this environment -- see knowledge/nexar.py's module docstring."""
    return _lookup_nexar_datasheet(part_number, license=license, classification=classification)


@mcp.tool()
def reconcile_component_sources(
    matches: list[dict],
    category: str,
    datasheet_document_ids: dict[str, int] | None = None,
) -> dict:
    """Reconcile two or three distributor lookups (lookup_digikey_component/
    lookup_mouser_component/lookup_nexar_component results for the SAME queried part
    number) into ONE components row instead of a duplicate per distributor. Each
    entry in matches needs at least "distributor" and "manufacturer_part_number"
    (pass a lookup_* result's fields straight through). datasheet_document_ids
    optionally maps distributor name -> the document_id its ingest produced.
    category must be one of this repo's ten RF component categories -- never guessed
    from a distributor's own catalog taxonomy. Runs automatically, no confirmation
    step, same posture as extract_components."""
    return _reconcile_components_from_matches(
        matches=matches, category=category, datasheet_document_ids=datasheet_document_ids
    )


@mcp.tool()
def create_design(
    design_key: str,
    name: str,
    revision: str,
    requirements: dict,
    architecture: dict,
) -> dict:
    """Start a new design: a designs row with design_key, name, revision,
    requirements, and architecture, starting in DRAFT status. requirements
    must be a dict keyed by requirement_id, each value carrying a
    'requirement' text field; one verification_items row is auto-created
    per key, all starting NOT VERIFIED. Every component_id referenced
    anywhere in architecture must already exist in components -- a
    dangling reference is rejected with a structured error naming the
    offending block, never silently written."""
    return _create_design(
        design_key=design_key,
        name=name,
        revision=revision,
        requirements=requirements,
        architecture=architecture,
    )


@mcp.tool()
def read_design(design_id: int) -> dict:
    """Fetch a stored design's full payload: design_key, name, revision, status,
    requirements, architecture (every component_id resolved inline to its
    manufacturer/part_number, not left as a bare id), and all engineering_results,
    decision_records (with approval_status), and verification_items rows. Returns
    a not-found result rather than raising if design_id doesn't exist."""
    return _read_design(design_id)


@mcp.tool()
def record_decision(
    design_id: int,
    record_key: str,
    decision: str,
    alternatives: list,
    rationale: str,
    evidence: list,
    design_family: str | None = None,
    approval_required: bool = True,
) -> dict:
    """Log a judgment-laden design choice -- a decision between real
    alternatives, distinct from a mechanical calculation -- with its
    rationale and evidence. Always an explicit agent judgment call, never
    triggered automatically by an architecture change. record_key follows
    '{design_key}-{slug}' and must be globally unique; reusing one is
    rejected with a structured error pointing at the existing record,
    never silently overwritten. Every new decision starts
    approval_status='PENDING' -- this does not yet block anything (no
    manufacturing_release tool or review UI exists). design_family (issue
    #167) is optional -- which design family (absorber, reflection-phase
    steering surface, patch antenna, ...) this decision was made about;
    leave unset for a decision that isn't about a design family at all."""
    return _record_decision(
        design_id=design_id,
        record_key=record_key,
        decision=decision,
        alternatives=alternatives,
        rationale=rationale,
        evidence=evidence,
        design_family=design_family,
        approval_required=approval_required,
    )


@mcp.tool()
def advance_design_status(design_id: int, status: str) -> dict:
    """Advance a design through docs/OPERATIONS.md's lifecycle (issue #145):
    DRAFT -> ANALYSIS -> SIMULATION -> OPTIMIZATION -> VERIFICATION ->
    CONDITIONAL-PASS/PASS/FAIL/BLOCKED -> RELEASED.

    Only legal next steps are accepted. A design cannot skip a stage, cannot
    jump straight to RELEASED, and cannot move at all once RELEASED (a released
    design gets a new revision instead). Work in progress can go BLOCKED from
    any stage, and FAIL/BLOCKED/CONDITIONAL-PASS return to ANALYSIS for rework.
    A refusal comes back tagged illegal_transition with a legal_next list
    naming what IS reachable from here.

    RELEASED additionally requires a signed human-approval receipt, which this
    tool cannot supply: no human-facing approval workflow is wired up in this
    codebase, so a release attempt returns release_not_approved. That is the
    intended behaviour -- a design must never reach RELEASED autonomously
    (docs/adr/0007; docs/BUILD_PLAN.md's Phase 12).

    This is the explicit path, for design work tracked outside the opt-in
    design loop (ADR-0010). The loop persists its own status at each iteration
    boundary (ADR-0011) and does not go through here."""
    return _update_design_status(design_id=design_id, status=status)


@mcp.tool()
def verify_requirement(
    design_id: int,
    requirement_id: str,
    method: str,
    status: str,
    expected: Any = None,
    actual: Any = None,
    evidence_uri: str | None = None,
    notes: str | None = None,
) -> dict:
    """Explicitly record verification of one requirement on a design:
    updates its verification_items row (auto-created by create_design)
    with method, status, expected, actual, evidence_uri, and notes.
    status must be one of NOT VERIFIED/PASS/FAIL/MARGINAL. Verification is
    always this explicit call -- never inferred by matching an
    engineering_results name against a requirement_id. A requirement_id
    with no matching row on this design_id is rejected with a structured
    error rather than creating a stray row."""
    return _verify_requirement(
        design_id=design_id,
        requirement_id=requirement_id,
        method=method,
        status=status,
        expected=expected,
        actual=actual,
        evidence_uri=evidence_uri,
        notes=notes,
    )


@mcp.tool()
def propose_requirement_target(
    design_id: int,
    requirement_id: str,
    value: float,
    comparator: str,
    unit: str,
    tolerance: float | None = None,
) -> dict:
    """Propose a structured requirement target for one of a design's
    requirements, interpreted from that requirement's own prose (issue #92).
    YOU (the calling agent) read the requirement's prose yourself and decide
    what value/comparator/unit/tolerance it means -- this tool does not read
    prose or call any model itself; it only validates the shape of what you
    propose, tags it ASSUMED (never a stronger provenance -- it is your
    reading of prose, not the customer's own stated number), and stores it
    on the design next to that requirement's original prose text (which is
    left untouched). comparator must be one of: EQUALS (a point target to
    hit, e.g. resonant frequency = 2.45 GHz), AT_LEAST (a minimum bound,
    e.g. gain >= 5 dBi), or AT_MOST (a maximum bound, e.g. VSWR <= 2.0).
    tolerance is optional and must be >= 0 if given. If the prose yields no
    defensible numeric target at all, call mark_requirement_unscoreable
    instead of guessing a value here. Calling this again for the same
    requirement_id corrects/replaces whatever target (proposed or
    confirmed) was there before -- nothing is scored against a target until
    a human calls confirm_requirement_target on it."""
    return _propose_requirement_target(
        design_id=design_id,
        requirement_id=requirement_id,
        value=value,
        comparator=comparator,
        unit=unit,
        tolerance=tolerance,
    )


@mcp.tool()
def mark_requirement_unscoreable(
    design_id: int,
    requirement_id: str,
    reason: str,
) -> dict:
    """Record that one of a design's requirements has prose with no
    defensible numeric target to propose (issue #92) -- e.g. a purely
    qualitative statement with no comparable value, comparator, or unit.
    reason must explain why, in enough detail for a human reader to agree
    or disagree with the call. Never invents a placeholder number: use this
    instead of propose_requirement_target whenever you cannot honestly
    defend a value/comparator/unit reading of the prose."""
    return _mark_requirement_unscoreable(
        design_id=design_id,
        requirement_id=requirement_id,
        reason=reason,
    )


@mcp.tool()
def confirm_requirement_target(
    design_id: int,
    requirement_id: str,
    confirmed_by: str,
) -> dict:
    """Confirm the currently-proposed target on one of a design's
    requirements (issue #92) -- records that it was confirmed and by whom
    (confirmed_by), so a later reader can see a human vouched that the
    proposed reading matches what the customer meant. Only a target with
    status PROPOSED can be confirmed here: an UNSCOREABLE target has no
    number to confirm, and an already-CONFIRMED target should be corrected
    via propose_requirement_target (which resets it to PROPOSED) rather
    than re-confirmed, so a stale confirmation is never silently
    overwritten. Nothing should be scored against a target that has not
    been confirmed."""
    return _confirm_requirement_target(
        design_id=design_id,
        requirement_id=requirement_id,
        confirmed_by=confirmed_by,
    )


assert_all_tools_categorized([tool.name for tool in asyncio.run(mcp.list_tools())])


if __name__ == "__main__":
    mcp.run()
