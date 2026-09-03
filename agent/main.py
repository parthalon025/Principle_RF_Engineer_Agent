import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
from agents import (
    Agent,
    AsyncOpenAI,
    FunctionTool,
    Runner,
    function_tool,
    set_default_openai_api,
    set_default_openai_client,
    set_tracing_disabled,
)
from agents.run import RunResult
from dotenv import load_dotenv

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
from measurement.power_meter import (
    request_power_meter_measurement_approval as _request_power_meter_measurement_approval,
)
from measurement.power_meter import run_power_meter_measurement as _run_power_meter_measurement
from measurement.signal_generator import (
    request_signal_generator_output_approval as _request_signal_generator_output_approval,
)
from measurement.signal_generator import run_signal_generator_output as _run_signal_generator_output
from measurement.spectrum_analyzer import (
    request_spectrum_analyzer_measurement_approval as _request_sa_measurement_approval,
)
from measurement.spectrum_analyzer import (
    run_spectrum_analyzer_measurement as _run_sa_measurement,
)
from measurement.vna import request_vna_measurement_approval as _request_vna_measurement_approval
from measurement.vna import run_vna_measurement as _run_vna_measurement
from optimization.rf_objectives import (
    optimize_patch_length_for_target_frequency as _optimize_patch_length_for_target_frequency,
)
from orchestration.policy import assert_all_tools_categorized
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

load_dotenv()

PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "principal_engineer.md"
SYSTEM_PROMPT = PROMPT_PATH.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Agent model provider interface (extends ADR-0004's self-hosted-backend
# rationale from the knowledge base to the agent's own reasoning calls). In
# plain terms: LLM_PROVIDER picks who answers the agent's tool-calling
# loop -- "openai" (default, paid, OpenAI's API, unchanged prior
# behavior), "anthropic" (paid, Claude via Anthropic's API), or "local"
# (free, a self-hosted OpenAI-compatible server -- Ollama by default --
# running on this machine, no per-token cost). This is deliberately a
# SEPARATE knob from DEFAULT_LLM_BACKEND, which governs the knowledge
# base's embedding/extraction calls (knowledge/embedding.py, knowledge/
# extraction_llm.py) for data-sensitivity reasons (ADR-0004) -- provider
# choice here is a capability/cost decision, not a data-handling one, so
# the two are independently configurable. Adding another LiteLLM-routed
# provider (Gemini, Mistral, etc. -- see https://docs.litellm.ai/docs/providers)
# is a one-line addition to _LITELLM_PROVIDERS below, not new plumbing.
# ---------------------------------------------------------------------------

_LITELLM_PROVIDERS = {
    # provider name -> (litellm model-string prefix, model env var, model
    # env var default, API key env var)
    "anthropic": ("anthropic", "ANTHROPIC_MODEL", "claude-sonnet-5", "ANTHROPIC_API_KEY"),
}


def _resolve_agent_model():
    """Build the value to pass as every Agent's `model=`: a plain model-name
    string for the "openai" (SDK default provider) and "local" (routed via
    _configure_local_llm_backend's default client, below) providers, or a
    `agents.extensions.models.litellm_model.LitellmModel` instance -- a
    `Model` object, not a string -- for any LiteLLM-routed provider like
    "anthropic". `Agent.model` accepts either (`str | Model`)."""
    provider = os.getenv("LLM_PROVIDER", "openai").lower()
    if provider in _LITELLM_PROVIDERS:
        from agents.extensions.models.litellm_model import LitellmModel

        prefix, model_env, model_default, key_env = _LITELLM_PROVIDERS[provider]
        return LitellmModel(
            model=f"{prefix}/{os.getenv(model_env, model_default)}",
            api_key=os.getenv(key_env),
        )
    if provider == "local":
        return os.getenv("LOCAL_AGENT_MODEL", "gpt-oss:20b")
    return os.getenv("OPENAI_MODEL", "gpt-5.5")


def _configure_local_llm_backend() -> None:
    """When LLM_PROVIDER=local, point the SDK's default OpenAI-compatible
    client at LOCAL_LLM_BASE_URL (Ollama by default) instead of OpenAI's
    API, so a plain model-name string from _resolve_agent_model resolves
    against the local server -- no per-Agent wiring needed. A no-op for
    every other provider."""
    if os.getenv("LLM_PROVIDER", "openai").lower() != "local":
        return
    base_url = os.getenv("LOCAL_LLM_BASE_URL", "http://localhost:11434/v1")
    client = AsyncOpenAI(base_url=base_url, api_key=os.getenv("LOCAL_LLM_API_KEY") or "unused")
    set_default_openai_client(client, use_for_tracing=False)
    # Self-hosted OpenAI-compatible servers (Ollama, llama.cpp, LM Studio)
    # implement the older /v1/chat/completions surface, not OpenAI's newer
    # /v1/responses API that this SDK defaults to.
    set_default_openai_api("chat_completions")
    # No real OPENAI_API_KEY exists in this mode, so trace uploads to
    # OpenAI's platform would only fail noisily -- turn tracing off rather
    # than let every run attempt and fail one.
    set_tracing_disabled(True)


_configure_local_llm_backend()


@function_tool
def calculate_wavelength(frequency_hz: float, design_id: int | None = None) -> float | dict:
    """Calculate free-space wavelength in meters for a given frequency in Hz.
    Pass design_id to also record this result as an engineering_results row
    against that design; the return value then gains a recorded_as field
    naming the new row's id."""
    result = wavelength(frequency_hz)
    if design_id is None:
        return result
    recorded = _record_engineering_result(
        design_id=design_id, tool_name="calculate_wavelength", value=result
    )
    return {"value": result, "recorded_as": recorded}


@function_tool
def calculate_vswr(
    reflection_coefficient_magnitude: float, design_id: int | None = None
) -> float | dict:
    """Calculate VSWR from the magnitude of the reflection coefficient (|Gamma|).
    Pass design_id to also record this result as an engineering_results row
    against that design; the return value then gains a recorded_as field
    naming the new row's id."""
    result = vswr_from_gamma(reflection_coefficient_magnitude)
    if design_id is None:
        return result
    recorded = _record_engineering_result(
        design_id=design_id, tool_name="calculate_vswr", value=result
    )
    return {"value": result, "recorded_as": recorded}


@function_tool
def calculate_return_loss(
    reflection_coefficient_magnitude: float, design_id: int | None = None
) -> float | dict:
    """Calculate return loss in dB from the magnitude of the reflection coefficient (|Gamma|).
    Pass design_id to also record this result as an engineering_results row
    against that design; the return value then gains a recorded_as field
    naming the new row's id."""
    result = return_loss_db(reflection_coefficient_magnitude)
    if design_id is None:
        return result
    recorded = _record_engineering_result(
        design_id=design_id, tool_name="calculate_return_loss", value=result
    )
    return {"value": result, "recorded_as": recorded}


@function_tool
def calculate_cascade_gain(gains_db: list[float], design_id: int | None = None) -> float | dict:
    """Calculate the total cascaded gain in dB for a chain of stage gains in dB.
    Pass design_id to also record this result as an engineering_results row
    against that design; the return value then gains a recorded_as field
    naming the new row's id."""
    result = cascade_gain_db(gains_db)
    if design_id is None:
        return result
    recorded = _record_engineering_result(
        design_id=design_id, tool_name="calculate_cascade_gain", value=result
    )
    return {"value": result, "recorded_as": recorded}


@function_tool
def calculate_noise_figure(
    noise_factors: list[float], gains_linear: list[float], design_id: int | None = None
) -> dict:
    """Calculate cascaded noise factor and noise figure (Friis equation) for a chain of
    stages, given each stage's linear noise factor and linear gain. Pass design_id to
    also record this result as an engineering_results row against that design; the
    return value then gains a recorded_as field naming the new row's id."""
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


@function_tool
def analyze_touchstone_file(path: str, design_id: int | None = None) -> dict:
    """Analyze a local Touchstone network file (.sNp) and return port count, frequency
    range, and S11/S21 extrema. Pass design_id to also record this result as an
    engineering_results row against that design; the return value then gains a
    recorded_as field naming the new row's id."""
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


@function_tool
def convert_db_to_linear(db: float) -> dict:
    """Convert a dB value to its linear (power ratio) equivalent."""
    return {"linear_value": db_to_linear(db), "provenance": "CALCULATED"}


@function_tool
def convert_linear_to_db(value: float) -> dict:
    """Convert a linear (power ratio) value to dB."""
    return {"db_value": linear_to_db(value), "provenance": "CALCULATED"}


@function_tool
def convert_s_to_z(s_params: list[list[complex]], z0: float = 50.0) -> dict:
    """Convert a two-port S-parameter matrix to Z-parameters relative to z0.
    See the matrix convention documented in this module's Phase 1-2 tools section."""
    z = s_to_z(s_params, z0)
    return {"z_params": _complex_matrix_to_strings(z), "provenance": "CALCULATED"}


@function_tool
def convert_z_to_s(z_params: list[list[complex]], z0: float = 50.0) -> dict:
    """Convert a two-port Z-parameter matrix to S-parameters relative to z0.
    Same matrix convention as convert_s_to_z."""
    s = z_to_s(z_params, z0)
    return {"s_params": _complex_matrix_to_strings(s), "provenance": "CALCULATED"}


@function_tool
def convert_s_to_y(s_params: list[list[complex]], z0: float = 50.0) -> dict:
    """Convert a two-port S-parameter matrix to Y-parameters relative to z0.
    Same matrix convention as convert_s_to_z."""
    y = s_to_y(s_params, z0)
    return {"y_params": _complex_matrix_to_strings(y), "provenance": "CALCULATED"}


@function_tool
def convert_y_to_s(y_params: list[list[complex]], z0: float = 50.0) -> dict:
    """Convert a two-port Y-parameter matrix to S-parameters relative to z0.
    Same matrix convention as convert_s_to_z."""
    s = y_to_s(y_params, z0)
    return {"s_params": _complex_matrix_to_strings(s), "provenance": "CALCULATED"}


@function_tool
def convert_s_to_abcd(s_params: list[list[complex]], z0: float = 50.0) -> dict:
    """Convert a two-port S-parameter matrix to ABCD-parameters relative to z0.
    Same matrix convention as convert_s_to_z."""
    abcd = s_to_abcd(s_params, z0)
    return {"abcd_params": _complex_matrix_to_strings(abcd), "provenance": "CALCULATED"}


@function_tool
def convert_abcd_to_s(abcd_params: list[list[complex]], z0: float = 50.0) -> dict:
    """Convert a two-port ABCD-parameter matrix to S-parameters relative to z0.
    Same matrix convention as convert_s_to_z."""
    s = abcd_to_s(abcd_params, z0)
    return {"s_params": _complex_matrix_to_strings(s), "provenance": "CALCULATED"}


@function_tool
def calculate_free_space_path_loss(distance_km: float, freq_mhz: float) -> dict:
    """Calculate free-space path loss (FSPL) in dB for a distance in km and frequency
    in MHz."""
    return {
        "path_loss_db": free_space_path_loss_db(distance_km, freq_mhz),
        "provenance": "CALCULATED",
    }


@function_tool
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


@function_tool
def calculate_cascade_output_ip3(oip3_linear: list[float], gains_linear: list[float]) -> dict:
    """Calculate cascaded output-referred third-order intercept (OIP3), linear units,
    for a chain of stages given in signal-flow order."""
    return {
        "oip3_linear": cascade_output_ip3_linear(oip3_linear, gains_linear),
        "provenance": "CALCULATED",
    }


@function_tool
def calculate_oip3_from_iip3(iip3_dbm: float, gain_db: float) -> dict:
    """Calculate output-referred IP3 (dBm) from input-referred IP3 and stage gain (dB)."""
    return {"oip3_dbm": oip3_from_iip3_db(iip3_dbm, gain_db), "provenance": "CALCULATED"}


@function_tool
def calculate_iip3_from_oip3(oip3_dbm: float, gain_db: float) -> dict:
    """Calculate input-referred IP3 (dBm) from output-referred IP3 and stage gain (dB)."""
    return {"iip3_dbm": iip3_from_oip3_db(oip3_dbm, gain_db), "provenance": "CALCULATED"}


@function_tool
def calculate_third_order_intermod_output(pout_dbm: float, oip3_dbm: float) -> dict:
    """Calculate the two-tone third-order intermodulation (IM3) product power,
    output-referred, in dBm."""
    return {
        "im3_output_dbm": third_order_intermod_output_dbm(pout_dbm, oip3_dbm),
        "provenance": "CALCULATED",
    }


@function_tool
def calculate_third_order_intermod_dbc(pout_dbm: float, oip3_dbm: float) -> dict:
    """Calculate the two-tone IM3 product level relative to the carrier, in dBc."""
    return {
        "im3_dbc": third_order_intermod_dbc(pout_dbm, oip3_dbm),
        "provenance": "CALCULATED",
    }


@function_tool
def calculate_stability_delta(s_params: list[list[complex]]) -> dict:
    """Calculate the two-port determinant Delta = S11*S22 - S12*S21.
    Same matrix convention as convert_s_to_z; delta is a complex()-parseable string."""
    delta = two_port_stability_delta(s_params)
    return {"delta": str(complex(delta)), "provenance": "CALCULATED"}


@function_tool
def calculate_rollett_k_factor(s_params: list[list[complex]]) -> dict:
    """Calculate the Rollett stability factor K for a two-port network's S-parameters.
    Same matrix convention as convert_s_to_z."""
    return {"k_factor": rollett_k_factor(s_params), "provenance": "CALCULATED"}


@function_tool
def calculate_stability_verdict(s_params: list[list[complex]]) -> dict:
    """Determine the unconditional/conditional-stability verdict (K > 1 and |Delta| < 1)
    for a two-port network. Same matrix convention as convert_s_to_z."""
    return {"verdict": stability_verdict(s_params), "provenance": "CALCULATED"}


@function_tool
def calculate_output_stability_circle(s_params: list[list[complex]]) -> dict:
    """Calculate the output (load-plane) stability circle center and radius.
    Same matrix convention as convert_s_to_z; center is a complex()-parseable string."""
    center, radius = output_stability_circle(s_params)
    return {"center": str(complex(center)), "radius": radius, "provenance": "CALCULATED"}


@function_tool
def calculate_input_stability_circle(s_params: list[list[complex]]) -> dict:
    """Calculate the input (source-plane) stability circle center and radius.
    Same matrix convention as convert_s_to_z; center is a complex()-parseable string."""
    center, radius = input_stability_circle(s_params)
    return {"center": str(complex(center)), "radius": radius, "provenance": "CALCULATED"}


@function_tool
def calculate_quarter_wave_transformer_impedance(z_source: float, z_load: float) -> dict:
    """Calculate the characteristic impedance of a quarter-wave transformer matching two
    real (resistive) impedances."""
    return {
        "transformer_impedance_ohms": quarter_wave_transformer_impedance(z_source, z_load),
        "provenance": "CALCULATED",
    }


@function_tool
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


@function_tool
def calculate_patch_effective_permittivity(eps_r: float, w_m: float, h_m: float) -> dict:
    """Calculate the effective dielectric constant of a microstrip patch
    (transmission-line model). Only valid for patch width/substrate-thickness W/h > 1."""
    return {
        "eps_eff": patch_effective_permittivity(eps_r, w_m, h_m),
        "provenance": "CALCULATED",
    }


@function_tool
def calculate_patch_length_extension(eps_eff: float, w_m: float, h_m: float) -> dict:
    """Calculate the fringing-field length extension dL (metres) for a microstrip patch."""
    return {
        "length_extension_m": patch_length_extension_m(eps_eff, w_m, h_m),
        "provenance": "CALCULATED",
    }


@function_tool
def calculate_patch_resonant_frequency(
    eps_r: float, w_m: float, h_m: float, l_m: float, c_m_s: float = 299_792_458.0
) -> dict:
    """Calculate the dominant-mode (TM010) resonant frequency of a flat rectangular
    microstrip patch, from substrate properties and patch dimensions."""
    return {
        "resonant_frequency_hz": patch_resonant_frequency_hz(eps_r, w_m, h_m, l_m, c_m_s),
        "provenance": "CALCULATED",
    }


@function_tool
def calculate_fractional_bandwidth_from_q(q: float, vswr: float = 2.0) -> dict:
    """Calculate fractional impedance bandwidth from quality factor Q, for a given VSWR
    threshold (defaults to the standard 2:1 VSWR bandwidth definition)."""
    return {
        "fractional_bandwidth": fractional_bandwidth_from_q(q, vswr),
        "provenance": "CALCULATED",
    }


@function_tool
def calculate_quality_factor_from_fractional_bandwidth(fbw: float, vswr: float = 2.0) -> dict:
    """Calculate quality factor Q from fractional impedance bandwidth, for a given VSWR
    threshold (defaults to the standard 2:1 VSWR bandwidth definition)."""
    return {
        "quality_factor": quality_factor_from_fractional_bandwidth(fbw, vswr),
        "provenance": "CALCULATED",
    }


@function_tool
def calculate_curvature_length_correction_factor(
    l_m: float, radius_of_curvature_m: float
) -> dict:
    """Calculate the first-order geometric length-correction factor (L/chord) for a
    patch bent to a radius of curvature. Restricted to L/R < 0.5; approximation only."""
    return {
        "correction_factor": curvature_length_correction_factor(l_m, radius_of_curvature_m),
        "provenance": "CALCULATED",
    }


@function_tool
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


@function_tool
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


@function_tool
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


@function_tool
def interpolate_touchstone_file(path: str, target_freqs_hz: list[float]) -> dict:
    """Interpolate a Touchstone network's S-parameters onto a new frequency grid (Hz) and
    summarize the result (same shape as analyze_touchstone_file). Every target frequency
    must fall within the source network's original range -- extrapolation is rejected."""
    network = interpolate_touchstone(path, target_freqs_hz)
    result = _network_summary(network)
    result["provenance"] = "CALCULATED"
    return result


@function_tool
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


@function_tool
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


@function_tool
def compare_touchstone_files(path_a: str, path_b: str) -> dict:
    """Quantify how two Touchstone networks differ, per S-parameter (max/RMS magnitude
    difference and per-point complex difference across their common frequency grid). Both
    networks must have the same port count and an overlapping frequency range."""
    jsonified = _jsonify_comparison(compare_touchstone(path_a, path_b))
    jsonified["provenance"] = "CALCULATED"
    return jsonified


@function_tool(strict_mode=False)  # `simulated`/`measured`'s shape (free-form
# dicts from whatever simulator/instrument-adapter output the caller has --
# an skrf.Network can't itself cross this JSON boundary) doesn't fit the
# SDK's strict-schema requirement -- same rationale as run_nec2_simulation's
# geometry parameter above.
def correlate_simulated_and_measured(
    simulated: dict,
    measured: dict,
    fixture_path: str | None = None,
    output_fixture_path: str | None = None,
    temperature_tolerance_c: float = 5.0,
) -> dict:
    """Correlate a SIMULATED result against a MEASURED result so you can
    judge how much to trust a given simulation for future design decisions
    on similar geometries: normalizes the two onto a common frequency grid
    and reference impedance (reusing compare_touchstone/interpolate_
    touchstone), de-embeds fixture effects when fixture_path is given
    (reusing deembed_touchstone -- SKIPPED, and said so in the result, when
    omitted), and returns a quantified per-S-parameter comparison, not a
    bare pass/fail. `simulated`/`measured` each accept a dict shaped like
    measure_vna_s_parameters' output (frequency_hz/s_parameters/z0), or one
    carrying a "touchstone_file" path -- see rf_tools/correlation.py's
    module docstring for exactly which of run_nec2_simulation's/
    run_openems_simulation's current outputs this can and cannot use yet
    (NEC2++'s single-frequency impedance is always honestly rejected, not
    fabricated from; openEMS's S-parameters are accepted via its
    "touchstone_file" output when computed=True -- real port probe data was
    available -- and honestly rejected when computed=False). Temperature
    normalization is a documented no-op unless both inputs happen to carry
    a "temperature_c" field, since no current simulator/instrument adapter
    populates one -- see the returned temperature_note. Returns
    "CALCULATED" provenance for the correlation result itself, alongside
    the input results' own SIMULATED/MEASURED provenance tags."""
    result = _correlate_simulation_measurement(
        simulated=simulated,
        measured=measured,
        fixture_path=fixture_path,
        output_fixture_path=output_fixture_path,
        temperature_tolerance_c=temperature_tolerance_c,
    )
    result["comparison"] = _jsonify_comparison(result["comparison"])
    return result


@function_tool(strict_mode=False)  # same rationale as run_nec2_simulation below --
# geometry's shape (optional half_space/materials/conductors/receivers lists, a
# single port dict) does not fit the SDK's strict-schema requirement.
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


@function_tool(strict_mode=False)  # geometry's shape (optional keys, variable-length
# wires list) doesn't fit the SDK's strict-schema requirement that object
# parameters have no additionalProperties -- see generate_nec2_deck's
# docstring in simulation/nec2pp.py for the accepted shape.
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
    return _run_nec2_simulation(
        geometry=geometry, frequency_hz=frequency_hz, timeout_s=timeout_s
    )


@function_tool(strict_mode=False)  # same rationale as run_nec2_simulation above --
# geometry's shape (optional materials/conductors lists, variable-length ports) does
# not fit the SDK's strict-schema requirement.
def run_openems_simulation(geometry: dict, fdtd: dict | None = None, timeout_s: int = 3600) -> dict:
    """Simulate a conformal/metamaterial antenna structure with openEMS (FDTD):
    generate an FDTD-XML file from structured geometry (box/cylinder material and
    conductor primitives in meters, one or more lumped ports with direction/
    resistance_ohms/frequency_hz, and explicit rectilinear mesh lines -- see
    simulation.openems.generate_openems_xml for the full shape), run it via openEMS,
    and return convergence metadata (did the run converge on the energy end-criteria
    or hit max timesteps -- the latter signals the mesh/excitation may need revision)
    plus S-parameter/far-field result keys. Use this over run_nec2_simulation for
    conformal/curved or metamaterial geometry that NEC2++'s wire method-of-moments
    can't adequately model. Returns "SIMULATED" provenance. S-parameters are REAL --
    FFT-computed from the run's port ProbeBox voltage/current time-domain dumps --
    when those dump files are present (this module's own XML now requests them);
    they fall back to an honestly-flagged computed=False when they aren't. IMPORTANT
    SCOPE LIMIT: far-field extraction is still NOT computed -- it requires openEMS's
    separate nf2ff tool, out of scope for this pass (see simulation/openems.py's
    module docstring). Format verified against primary openEMS/CSXCAD documentation
    (see simulation/openems.py's module docstring for citations) but NOT against a
    real openEMS binary -- none is installed in this environment; treat any result as
    unverified end-to-end until it has been run against the real tool at least once."""
    return _run_openems_simulation(geometry=geometry, fdtd=fdtd, timeout_s=timeout_s)


@function_tool(strict_mode=False)  # same rationale as run_nec2_simulation above --
# circuit's shape (variable-length ports/components lists) does not fit the SDK's
# strict-schema requirement.
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
    Netlist/dataset format verified against qucsator_rf's own primary source (a
    real test-suite fixture netlist plus its CLI/netlist-grammar/output-format
    source -- see simulation/qucs.py's module docstring for the full citation
    list) but NOT against a real qucsator_rf binary -- none is installed in this
    environment; treat any result as unverified end-to-end until it has been run
    against the real tool at least once. IMPORTANT: the real executable this
    adapter shells out to is named "qucsator_rf", not the bare "qucsator" its
    upstream project is colloquially called -- see that module docstring for why."""
    return _run_qucs_simulation(circuit=circuit, analysis=analysis, timeout_s=timeout_s)


@function_tool(strict_mode=False)  # same rationale as run_nec2_simulation above --
# geometry's shape (optional materials/conductors lists, one port dict) does not fit
# the SDK's strict-schema requirement.
def run_hfss_simulation(
    geometry: dict,
    frequency_hz: float,
    sweep: dict | None = None,
    project_name: str = "hfss_project",
    design_name: str = "hfss_design",
) -> dict:
    """Simulate a structure with HFSS via PyAEDT: create a project, apply geometry
    (box material/conductor primitives with materials in meters -- see
    simulation.hfss._apply_hfss_geometry for the full shape), a lumped port, and a
    length-based mesh, solve, extract S-parameters, export a Touchstone file, and
    archive the solved project plus extracted report for later reproducibility.
    Returns "SIMULATED" provenance. CRITICAL: unlike run_nec2_simulation/
    run_openems_simulation, HFSS is commercial, licensed software (Ansys HFSS via
    PyAEDT) that fundamentally cannot run without a paid license -- execution is
    confined to a configured, explicitly-designated licensed workstation and refuses
    to run anywhere else (see simulation/hfss.py's check_hfss_workstation_
    confinement -- it will raise on any host that is not that workstation, including
    this one). PyAEDT API call shapes are verified against the primary ansys/pyaedt
    GitHub source (see simulation/hfss.py's module docstring for the full citation
    list, graded by confidence per fact) but NOT against a real HFSS/AEDT
    installation -- none is licensed or available in this environment, and none
    genuinely can be; treat any result as unverified end-to-end until it has
    actually been run on a real licensed workstation at least once."""
    return _run_hfss_simulation(
        geometry=geometry,
        frequency_hz=frequency_hz,
        sweep=sweep,
        project_name=project_name,
        design_name=design_name,
    )


@function_tool(strict_mode=False)  # same rationale as run_nec2_simulation above --
# ports'/project's shapes (optional materials/nested path/boundary/mode lists) do not
# fit the SDK's strict-schema requirement.
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
    installed in this environment; treat any result as unverified end-to-end until it
    has been run against the real tool at least once. OpenParEM is also considerably
    younger and less battle-tested than NEC2++/openEMS/HFSS (initial release Sept.
    2024) -- extra caution warranted."""
    return _run_openparem_simulation(
        mesh_file=mesh_file,
        ports=ports,
        project=project,
        project_name=project_name,
        mpi_processes=mpi_processes,
        timeout_s=timeout_s,
    )


@function_tool(strict_mode=False)  # same rationale as run_nec2_simulation above --
# geometry's shape (optional materials list, mesh/floquet override dicts) does not fit
# the SDK's strict-schema requirement.
def run_palace_simulation(
    geometry: dict,
    frequency_hz: float,
    sweep: dict | None = None,
    num_processes: int = 1,
    timeout_s: int = 3600,
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
    data (plus a "specular" S11/S21-style convenience view for the fundamental order).
    Returns "SIMULATED" provenance. Embedded PEC conductor patches (a metallic
    metasurface, as opposed to an all-dielectric grating/photonic-crystal unit cell)
    are NOT supported in this pass -- an explicitly-scoped gap, see simulation/
    palace.py's module docstring. Config/mesh format verified against Palace's own
    primary documentation and MFEM's own mesh-format documentation (see simulation/
    palace.py's module docstring for the full citation list, several facts there
    graded as reasoned-by-analogy rather than independently confirmed byte-exact) but
    NOT against a real palace binary -- none is installed in this environment; treat
    any result as unverified end-to-end until it has been run against the real tool at
    least once."""
    return _run_palace_simulation(
        geometry=geometry,
        frequency_hz=frequency_hz,
        sweep=sweep,
        num_processes=num_processes,
        timeout_s=timeout_s,
    )


@function_tool(strict_mode=False)  # same rationale as run_nec2_simulation above --
# geometry's shape (domain/material/optional excitation) does not fit the SDK's
# strict-schema requirement.
def run_elmer_simulation(
    geometry: dict,
    frequency_hz: float,
    timeout_s: int = 1800,
) -> dict:
    """Simulate a structure with Elmer FEM's VectorHelmholtz module: a general,
    multiphysics-ready EM cross-check kept available for a FUTURE coupled-physics
    need (e.g. EM/thermal analysis on a mounted "adaptive EM skin") -- NOT a
    replacement for run_nec2_simulation/run_openems_simulation/run_hfss_simulation on
    everyday antenna work, since Elmer's primary user base is structural/CFD/heat-
    transfer, not EM. Generates a Gmsh OpenCASCADE .geo script from structured
    geometry (a single rectangular domain with isotropic material, plus an optional
    rectangular excitation sub-region -- see simulation.elmer.generate_gmsh_geo_script
    for the full shape), meshes it with gmsh, converts the mesh to ElmerSolver's
    native format with ElmerGrid, generates a matching VectorHelmholtz .sif (see
    simulation.elmer.generate_elmer_sif), runs it with ElmerSolver, and parses
    whatever raw output is available. Returns "SIMULATED" provenance. CRITICAL SCOPE
    LIMIT: unlike OpenParEM/Palace, Elmer's VectorHelmholtz module has NO native
    antenna-specific port/S-parameter/far-field/gain post-processing -- this tool's
    excitation (an impressed "Body Force"/"Current Density" current source) and
    boundary conditions (PEC "E Re"/"E Im"=0, or the solver's own generic "Absorbing
    BC" flag) are hand-assembled, real FEM techniques, not a calibrated port;
    "s_parameters" and "far_field" in the result are therefore ALWAYS computed=False
    with an explanatory note, never fabricated -- see simulation/elmer.py's module
    docstring "SCOPE AND LIMITATIONS" for the full detail. .geo/.sif/CLI format
    verified against Gmsh's own official reference manual and ElmerGrid's/
    ElmerSolver's own primary GitHub source (see simulation/elmer.py's module
    docstring for the full citation list, each fact graded by confidence) but NOT
    against real gmsh/ElmerGrid/ElmerSolver binaries -- none is installed in this
    environment; treat any result as unverified end-to-end until it has been run
    against the real tools at least once."""
    return _run_elmer_simulation(
        geometry=geometry, frequency_hz=frequency_hz, timeout_s=timeout_s
    )


@function_tool(strict_mode=False)  # same rationale as run_elmer_simulation above --
# `primitives`/`curvature`'s shape (box/polygon primitive dicts, curvature params)
# does not fit the SDK's strict-schema requirement.
def generate_freecad_curved_geometry(
    primitives: list[dict],
    curvature: dict,
    timeout_s: int = 600,
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
        primitives=primitives, curvature=curvature, timeout_s=timeout_s
    )


@function_tool
def run_ltspice_simulation(
    netlist: str | None = None,
    netlist_file: str | None = None,
    timeout_s: int = 600,
) -> dict:
    """Simulate a circuit with LTspice (ADS alternative, part 3 of 3 -- issue
    #59): run an existing SPICE netlist (either `netlist`, raw netlist text
    -- e.g. exported from LTspice's own File > Export Netlist -- or
    `netlist_file`, a path to an existing .net/.cir/.asc file already on
    disk; exactly one is required) through LTspice's real batch-mode CLI
    (driven via the spicelib package, not hand-rolled -- see simulation/
    ltspice.py's module docstring for the primary-source citation), and
    parse the resulting .raw output into structured trace data (plot type,
    axis, and every named trace, complex for an AC analysis or real for a
    transient/DC sweep) via spicelib's own RawRead. Returns "SIMULATED"
    provenance. LOWEST PRIORITY / LOWEST INVESTMENT of this batch's "ADS
    alternative" simulators: LTspice is the one non-open-source item here
    (free-of-charge proprietary Analog Devices freeware, NOT OSI-approved --
    see docs/LICENSE_MATRIX.md) and is capability-redundant with any
    ngspice/Xyce/Qucs-S adapter this repo may also have -- its value is
    vendor device-model-library and engineer familiarity, not new
    simulation capability. Unlike run_nec2_simulation/run_openems_
    simulation, this tool does NOT generate a netlist from a structured
    component-description dict -- a SPICE netlist is already the natural
    structured/text format for a circuit, so bring your own. spicelib
    itself is an OPTIONAL install (`pip install '.[ltspice]'` /
    `uv sync --extra ltspice`) -- this tool raises a clear, actionable
    SimulatorError (not a bare ImportError) if it isn't installed. Format/
    invocation verified against spicelib's own primary GitHub source (see
    simulation/ltspice.py's module docstring for the full citation) but NOT
    against a real LTspice binary -- none is installed in this environment;
    treat any result as unverified end-to-end until it has been run against
    the real tool at least once."""
    return _run_ltspice_simulation(
        netlist=netlist, netlist_file=netlist_file, timeout_s=timeout_s
    )


@function_tool(strict_mode=False)  # `config`'s shape (gerber2ems's own optional
# ports/traces/differential_pairs/grid/via keys) doesn't fit the SDK's strict-schema
# requirement -- same rationale as run_nec2_simulation's geometry parameter above.
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


@function_tool(strict_mode=False)  # same rationale as run_nec2_simulation above --
# job's shape (optional keys, variable-length components/raw_cards lists) doesn't fit
# the SDK's strict-schema requirement -- see simulation.ngspice.generate_ngspice_netlist
# for the accepted shape.
def run_ngspice_simulation(job: dict, timeout_s: int = 600) -> dict:
    """Simulate a matching network, filter, or amplifier bias/termination sub-circuit
    with ngspice (a free/open circuit-level SPICE simulator, no paid ADS license
    needed): generate a netlist from a structured job dict (R/L/C/V/I components,
    optional "raw_cards" escape hatch for nonlinear devices/subcircuits, an
    op/ac/tran "analysis", and node-voltage/branch-current "outputs" -- see
    simulation.ngspice.generate_ngspice_netlist for the full shape), run it via
    ngspice, and parse the requested outputs' AC (real/imag pairs vs. frequency),
    TRAN (values vs. time), or OP data back out. Returns "SIMULATED" provenance.
    IMPORTANT SCOPE LIMIT: S-parameters are NOT computed here -- stable ngspice has
    no built-in S-parameter analysis; use run_xyce_simulation's native `.LIN`
    S-parameter/Touchstone path for that need instead (see simulation/ngspice.py's
    module docstring for why). Netlist/output format verified against the primary
    ngspice manual (see simulation/ngspice.py's module docstring for the citation)
    but NOT against a real ngspice binary -- none is installed in this environment;
    treat any result as unverified end-to-end until it has been run against the
    real tool at least once."""
    return _run_ngspice_simulation(job=job, timeout_s=timeout_s)


@function_tool(strict_mode=False)  # same rationale as run_nec2_simulation above --
# job's shape (optional keys, variable-length components/ports/raw_cards lists)
# doesn't fit the SDK's strict-schema requirement -- see
# simulation.xyce.generate_xyce_netlist for the accepted shape.
def run_xyce_simulation(job: dict, timeout_s: int = 600) -> dict:
    """Simulate a matching network, filter, or amplifier bias/termination sub-circuit
    with Xyce (Sandia's free/open parallel-capable circuit simulator, no paid ADS
    license needed -- prefer this over run_ngspice_simulation for a larger circuit
    or when real S-parameters are needed): generate a netlist from a structured job
    dict (R/L/C/V/I components, optional "raw_cards" escape hatch for nonlinear
    devices/subcircuits, an op/ac/tran "analysis", optional node-voltage/branch-
    current "outputs", and optional "ports" -- see simulation.xyce.generate_xyce_netlist
    for the full shape), run it via Xyce, and return the requested `.PRINT` outputs
    (CSV columns vs. frequency/time) and/or, when "ports" are given (requires
    analysis type "ac"), REAL S-parameters extracted via Xyce's native `.LIN` linear-
    network analysis and exported to a genuine Touchstone file (surfaced as
    "touchstone_file", integrating with correlate_simulated_and_measured the same way
    simulation/hfss.py's and simulation/openems.py's computed=True S-parameters do).
    Returns "SIMULATED" provenance. HONEST CONFIDENCE CAVEAT: the `.LIN` S-parameter
    path is verified against Xyce's own primary Reference Guide but carries one extra
    notch of uncertainty beyond this tool's `.AC`/`.TRAN`/`.PRINT` coverage -- see
    simulation/xyce.py's module docstring "HONEST CONFIDENCE CAVEAT ON `.LIN`
    SPECIFICALLY" for why. Format verified against the primary Xyce Reference Guide
    (see simulation/xyce.py's module docstring for the citation) but NOT against a
    real Xyce binary -- none is installed in this environment; treat any result as
    unverified end-to-end until it has been run against the real tool at least once."""
    return _run_xyce_simulation(job=job, timeout_s=timeout_s)


@function_tool(strict_mode=False)  # same rationale as run_nec2_simulation above --
# geometry's shape (optional materials/conductors lists, a single port dict) does
# not fit the SDK's strict-schema requirement.
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
    MODEL caveat), and returns "SIMULATED" provenance. IMPORTANT SCOPE LIMITS: only
    POWER REFLECTANCE and its magnitude |S11| are computed (via MEEP's own documented
    flux-subtraction technique) -- NO complex phase, NO S21/multi-port, NO Touchstone
    export, and NO far-field/gain (see simulation/meep.py's module docstring SCOPE
    section) -- so only |S11| magnitude, not phase, can be cross-checked against
    run_openems_simulation's complex S11. `characteristic_length_m` is MEEP's own
    dimensionless-unit lengthscale "a" (default 1mm, reasonable for patch-antenna-
    scale geometry); geometry/units translation verified against MEEP's own primary
    documentation (see simulation/meep.py's module docstring for the citation) but
    NOT against a real MEEP install -- MEEP has no PyPI wheel and no native Windows
    support (conda-forge only, WSL required on Windows; see README.md's Optional
    tools list); treat any result as unverified end-to-end until it has been run
    against the real library at least once."""
    return _run_meep_simulation(
        geometry=geometry, characteristic_length_m=characteristic_length_m, nfreq=nfreq
    )


# ---------------------------------------------------------------------------
# VNA measurement (issue #43, Phase 10 ticket 1 of 2) -- deliberately TWO
# separate tools, not one tool with an easily-flippable boolean parameter,
# per this ticket's design guidance and mirroring measurement/base.py's
# structural approval-gate design: request_vna_measurement_approval() is
# the ONLY way to obtain an approval receipt, and does nothing dangerous
# itself; measure_vna_s_parameters() is the only tool that can actually
# reach the instrument, and it cryptographically verifies (via
# measurement/base.py's check_physical_actuation_gate) that the `approval`
# it was given is a genuine, unmodified receipt granted for this EXACT
# resource/start_hz/stop_hz/points/sparams combination -- a receipt for a
# different request, a forged token, or a bare string/boolean in place of
# a real receipt are all rejected, not silently accepted.
#
# IMPORTANT: this codebase does not yet wire up any real human-facing
# approval UI/workflow (see measurement/base.py's module docstring), so
# request_vna_measurement_approval below ALWAYS raises when actually
# invoked through this tool surface -- a Python approval_callback cannot
# cross this JSON tool-call boundary, so there is currently no way for an
# agent invocation of this tool to produce a granted approval. This is
# intentional: physical lab instruments are never controlled autonomously
# in this project (README.md, docs/BUILD_PLAN.md's Phase 10 "Physical
# control remains approval-required", docs/SECURITY.md). Wiring a real
# approval_callback (a genuine human-facing confirmation workflow) is a
# project for later.
# ---------------------------------------------------------------------------


@function_tool
def request_vna_measurement_approval(
    resource: str,
    start_hz: float,
    stop_hz: float,
    points: int = 201,
    sparams: list[str] | None = None,
    approved_by: str = "",
) -> dict:
    """Request the distinct, auditable human-approval step required before
    ANY VNA S-parameter measurement can physically actuate a real
    instrument. Does nothing dangerous itself -- no SCPI, no VISA, no
    instrument I/O of any kind. On success, returns an approval receipt
    (a plain dict) to pass UNCHANGED as measure_vna_s_parameters'
    `approval` argument, for THIS EXACT resource/start_hz/stop_hz/points/
    sparams combination -- a receipt requested for a different combination
    will be rejected there.

    THIS TOOL CURRENTLY ALWAYS RAISES: no real human-facing approval
    workflow is wired into this codebase yet (see this module's comment
    above and measurement/base.py's module docstring). Do not attempt to
    work around this by fabricating a token yourself -- measure_vna_
    s_parameters cryptographically verifies the receipt and rejects
    anything that did not genuinely come from this function having
    actually granted an approval."""
    return _request_vna_measurement_approval(
        resource=resource,
        start_hz=start_hz,
        stop_hz=stop_hz,
        points=points,
        sparams=sparams,
        approved_by=approved_by or None,
    )


@function_tool(strict_mode=False)  # `approval`'s shape (an opaque receipt
# dict passed through unchanged from request_vna_measurement_approval's
# output) and `calibration` (free-form caller metadata) don't fit the
# SDK's strict-schema requirement -- same rationale as run_nec2_
# simulation's geometry parameter above.
def measure_vna_s_parameters(
    resource: str,
    start_hz: float,
    stop_hz: float,
    approval: dict,
    points: int = 201,
    sparams: list[str] | None = None,
    z0: float = 50.0,
    calibration: dict | None = None,
) -> dict:
    """Perform a real VNA S-parameter measurement over SCPI/VISA, GIVEN a
    valid approval receipt already obtained from a separate, prior call to
    request_vna_measurement_approval for this EXACT resource/start_hz/
    stop_hz/points/sparams combination. Configures the frequency sweep,
    triggers a measurement, and reads back S-parameter data, returning a
    "MEASURED"-provenance result (this project's top evidence tier --
    README.md's "Design goals") with instrument identity and calibration
    metadata attached, structured Touchstone-compatibly (an in-memory
    skrf.Network is built from the parsed data -- see measurement/vna.py,
    which reuses this project's existing rf_tools/touchstone.py
    conventions). Refuses to run without ALL of: ALLOW_INSTRUMENT_
    CONTROL=true, a configured VISA resource, pyvisa installed, AND a
    cryptographically valid approval receipt for this exact request (see
    measurement/base.py's check_physical_actuation_gate) -- none of this
    is optional or bypassable from this tool surface. Exact SCPI command
    syntax is documented, generic, and explicitly vendor-variable (see
    measurement/vna.py's module docstring's citations and caveat); it is
    NOT verified against any real instrument in this environment -- none
    is installed or available here."""
    return _run_vna_measurement(
        resource=resource,
        start_hz=start_hz,
        stop_hz=stop_hz,
        approval=approval,
        points=points,
        sparams=sparams,
        z0=z0,
        calibration=calibration,
    )


# ---------------------------------------------------------------------------
# Spectrum analyzer, signal generator, and power meter measurement (issue
# #44, Phase 10 ticket 2 of 2) -- three MORE instrument classes, each
# wired as TWO separate tools (an approval-request tool + a measure/
# actuate tool), exactly mirroring the VNA tools above and measurement/
# base.py's structural approval-gate design. See measurement/
# spectrum_analyzer.py, measurement/signal_generator.py, and measurement/
# power_meter.py's module docstrings for the SCPI command citations and
# vendor-variability caveats.
#
# The signal generator tools are the one pair of these six that actively
# commands RF output onto the physical world (a spectrum analyzer and a
# power meter only observe whatever is already present) -- see
# measurement/signal_generator.py's module docstring for why its approval
# fingerprint deliberately includes power_dbm and output_on, not just
# frequency_hz, so an approval for one power/frequency/on-off combination
# cannot be silently reused for a different one.
#
# IMPORTANT: exactly as with the VNA tools above, none of the three
# request_*_approval tools below can currently produce a granted approval
# through this tool surface -- no real human-facing approval UI/workflow is
# wired into this codebase yet (see measurement/base.py's module
# docstring), and a Python approval_callback cannot cross this JSON tool-
# call boundary. Physical lab instruments are never controlled
# autonomously in this project (README.md, docs/BUILD_PLAN.md's Phase 10
# "Physical control remains approval-required", docs/SECURITY.md).
# ---------------------------------------------------------------------------


@function_tool
def request_spectrum_analyzer_measurement_approval(
    resource: str,
    center_hz: float,
    span_hz: float,
    res_bw_hz: float | None = None,
    points: int = 401,
    approved_by: str = "",
) -> dict:
    """Request the distinct, auditable human-approval step required before
    ANY spectrum analyzer trace measurement can physically actuate a real
    instrument. Does nothing dangerous itself -- no SCPI, no VISA, no
    instrument I/O of any kind. On success, returns an approval receipt (a
    plain dict) to pass UNCHANGED as measure_spectrum_analyzer_trace's
    `approval` argument, for THIS EXACT resource/center_hz/span_hz/
    res_bw_hz/points combination.

    THIS TOOL CURRENTLY ALWAYS RAISES: no real human-facing approval
    workflow is wired into this codebase yet. Do not attempt to work
    around this by fabricating a token yourself --
    measure_spectrum_analyzer_trace cryptographically verifies the receipt
    and rejects anything that did not genuinely come from this function
    having actually granted an approval."""
    return _request_sa_measurement_approval(
        resource=resource,
        center_hz=center_hz,
        span_hz=span_hz,
        res_bw_hz=res_bw_hz,
        points=points,
        approved_by=approved_by or None,
    )


@function_tool(strict_mode=False)  # `approval` (an opaque receipt dict) and
# `calibration` (free-form caller metadata) don't fit the SDK's strict-
# schema requirement -- same rationale as measure_vna_s_parameters above.
def measure_spectrum_analyzer_trace(
    resource: str,
    center_hz: float,
    span_hz: float,
    approval: dict,
    res_bw_hz: float | None = None,
    points: int = 401,
    calibration: dict | None = None,
) -> dict:
    """Perform a real spectrum analyzer trace measurement over SCPI/VISA,
    GIVEN a valid approval receipt already obtained from a separate, prior
    call to request_spectrum_analyzer_measurement_approval for this EXACT
    resource/center_hz/span_hz/res_bw_hz/points combination. Configures
    center frequency/span/resolution bandwidth, triggers a sweep, and reads
    back an amplitude-vs-frequency trace, returning a "MEASURED"-provenance
    result with instrument identity and calibration metadata attached (see
    measurement/spectrum_analyzer.py). Refuses to run without ALL of:
    ALLOW_INSTRUMENT_CONTROL=true, a configured VISA resource, pyvisa
    installed, AND a cryptographically valid approval receipt for this
    exact request -- none of this is optional or bypassable from this tool
    surface. Exact SCPI command syntax is documented, generic, and
    explicitly vendor-variable (see measurement/spectrum_analyzer.py's
    module docstring's citations and caveat); it is NOT verified against
    any real instrument in this environment."""
    return _run_sa_measurement(
        resource=resource,
        center_hz=center_hz,
        span_hz=span_hz,
        approval=approval,
        res_bw_hz=res_bw_hz,
        points=points,
        calibration=calibration,
    )


@function_tool
def request_signal_generator_output_approval(
    resource: str,
    frequency_hz: float,
    power_dbm: float,
    output_on: bool = True,
    approved_by: str = "",
) -> dict:
    """Request the distinct, auditable human-approval step required before
    a signal generator can be commanded to output RF power onto a real
    instrument. Does nothing dangerous itself -- no SCPI, no VISA, no RF
    output of any kind. On success, returns an approval receipt (a plain
    dict) to pass UNCHANGED as set_signal_generator_output's `approval`
    argument, for THIS EXACT resource/frequency_hz/power_dbm/output_on
    combination -- an approval requested for a different frequency, power
    level, OR on/off state will be rejected there (see measurement/
    signal_generator.py's module docstring: a signal generator actively
    outputs RF power, arguably a more consequential physical actuation
    than a VNA's own low, calibrated stimulus, so this fingerprint is held
    to be at least as strict).

    THIS TOOL CURRENTLY ALWAYS RAISES: no real human-facing approval
    workflow is wired into this codebase yet. Do not attempt to work
    around this by fabricating a token yourself --
    set_signal_generator_output cryptographically verifies the receipt and
    rejects anything that did not genuinely come from this function having
    actually granted an approval."""
    return _request_signal_generator_output_approval(
        resource=resource,
        frequency_hz=frequency_hz,
        power_dbm=power_dbm,
        output_on=output_on,
        approved_by=approved_by or None,
    )


@function_tool(strict_mode=False)  # `approval` (an opaque receipt dict)
# doesn't fit the SDK's strict-schema requirement -- same rationale as
# measure_vna_s_parameters above.
def set_signal_generator_output(
    resource: str,
    frequency_hz: float,
    power_dbm: float,
    approval: dict,
    output_on: bool = True,
) -> dict:
    """Command a real signal generator's output frequency/power/on-off
    state over SCPI/VISA, GIVEN a valid approval receipt already obtained
    from a separate, prior call to request_signal_generator_output_approval
    for this EXACT resource/frequency_hz/power_dbm/output_on combination.
    Returns a "MEASURED"-provenance result confirming the actuated state
    plus best-effort instrument readback (see measurement/
    signal_generator.py). Refuses to run without ALL of: ALLOW_INSTRUMENT_
    CONTROL=true, a configured VISA resource, pyvisa installed, AND a
    cryptographically valid approval receipt for this EXACT
    frequency/power/output-on-off combination -- none of this is optional
    or bypassable from this tool surface, and this is the one tool pair in
    this project that commands a physical instrument to actively output RF
    power rather than merely observe or apply a low, calibrated stimulus,
    so its approval gate is held to be at least as strict as
    measure_vna_s_parameters'. Exact SCPI command syntax is documented,
    generic, and explicitly vendor-variable (see measurement/
    signal_generator.py's module docstring's citations and caveat); it is
    NOT verified against any real instrument in this environment."""
    return _run_signal_generator_output(
        resource=resource,
        frequency_hz=frequency_hz,
        power_dbm=power_dbm,
        approval=approval,
        output_on=output_on,
    )


@function_tool
def request_power_meter_measurement_approval(
    resource: str,
    frequency_hz: float,
    approved_by: str = "",
) -> dict:
    """Request the distinct, auditable human-approval step required before
    ANY RF power meter reading can physically actuate a real instrument.
    Does nothing dangerous itself -- no SCPI, no VISA, no instrument I/O of
    any kind. On success, returns an approval receipt (a plain dict) to
    pass UNCHANGED as measure_power_meter_reading's `approval` argument,
    for THIS EXACT resource/frequency_hz combination.

    THIS TOOL CURRENTLY ALWAYS RAISES: no real human-facing approval
    workflow is wired into this codebase yet. Do not attempt to work
    around this by fabricating a token yourself --
    measure_power_meter_reading cryptographically verifies the receipt and
    rejects anything that did not genuinely come from this function having
    actually granted an approval."""
    return _request_power_meter_measurement_approval(
        resource=resource,
        frequency_hz=frequency_hz,
        approved_by=approved_by or None,
    )


@function_tool(strict_mode=False)  # `approval` (an opaque receipt dict) and
# `calibration` (free-form caller metadata) don't fit the SDK's strict-
# schema requirement -- same rationale as measure_vna_s_parameters above.
def measure_power_meter_reading(
    resource: str,
    frequency_hz: float,
    approval: dict,
    calibration: dict | None = None,
) -> dict:
    """Perform a real RF power meter reading over SCPI/VISA, GIVEN a valid
    approval receipt already obtained from a separate, prior call to
    request_power_meter_measurement_approval for this EXACT resource/
    frequency_hz combination. Sets the measurement frequency (used for the
    meter's stored calibration-factor lookup), triggers a measurement, and
    reads back a scalar power value, returning a "MEASURED"-provenance
    result with instrument identity, units, and calibration-factor
    metadata attached (see measurement/power_meter.py). Refuses to run
    without ALL of: ALLOW_INSTRUMENT_CONTROL=true, a configured VISA
    resource, pyvisa installed, AND a cryptographically valid approval
    receipt for this exact request -- none of this is optional or
    bypassable from this tool surface. Exact SCPI command syntax is
    documented, generic, and explicitly vendor-variable (see measurement/
    power_meter.py's module docstring's citations and caveat); it is NOT
    verified against any real instrument in this environment."""
    return _run_power_meter_measurement(
        resource=resource,
        frequency_hz=frequency_hz,
        approval=approval,
        calibration=calibration,
    )


@function_tool
def ingest_document(
    file_path: str,
    source_type: str,
    license: str,
    classification: str,
    supersedes_document_id: int | None = None,
) -> dict:
    """Parse a datasheet/standard/textbook/paper PDF via docling, chunk it, and store it
    in the knowledge base. source_type, license, and classification are all mandatory.
    Pass supersedes_document_id to declare this upload a newer revision of that document
    (never inferred from title); omit it for a plain new, independent document."""
    return _ingest_document(
        file_path=file_path,
        source_type=source_type,
        license=license,
        classification=classification,
        supersedes_document_id=supersedes_document_id,
    )


@function_tool
def index_document(document_id: int, requested_backend: str | None = None) -> dict:
    """Embed a stored document's chunks and write the vectors to the knowledge base.
    SENSITIVE/RESTRICTED documents always use the self-hosted backend, with no
    fallback to the external API; requesting "external" for one raises. PUBLIC/
    INTERNAL documents honor an explicit requested_backend ("local"/"external") or
    fall back to the configured default, and fall back from local to external if
    the self-hosted backend is briefly unreachable."""
    return _index_document(document_id=document_id, requested_backend=requested_backend)


@function_tool
def read_document(document_id: int) -> dict:
    """Fetch a stored document's full metadata (title, source_type, license, classification,
    authority_rank, status, revision, supersedes_document_id, publication date, author) plus
    its chunks (content, page number, section) in order. Returns a not-found result rather
    than raising if document_id doesn't exist."""
    return _read_document(document_id)


@function_tool
def search_knowledge(query_text: str, document_id: int | None = None, limit: int = 20) -> list:
    """Search the knowledge base for query_text and return one ranked list of chunk
    matches, each tagged with its match_type ("semantic_external", "semantic_local",
    or "lexical"). Defaults to ACTIVE documents only; pass document_id to search a
    specific document/revision (including a SUPERSEDED one) instead. Ordered by
    authority_rank first, then each match's own native score -- never a single
    blended score across match types."""
    return _search_knowledge(query_text=query_text, document_id=document_id, limit=limit)


@function_tool
def search_design_records(query_text: str, document_id: int | None = None, limit: int = 20) -> list:
    """Search for prior design/decision records relevant to query_text -- e.g. by
    component, frequency band, or design pattern -- so you can find precedent before
    proposing a new design instead of starting from nothing. A thin wrapper around
    search_knowledge scoped to source_type="design_record" documents (internally-authored
    design notes and decision write-ups); same ranking and match_type semantics."""
    return _search_design_records(query_text=query_text, document_id=document_id, limit=limit)


@function_tool
def extract_components(document_id: int, requested_backend: str | None = None) -> dict:
    """Extract structured component specifications from a stored datasheet/application_note
    and upsert a components row per part, keyed by (manufacturer, part_number). Runs
    automatically, no confirmation step. Each specification field carries its own
    provenance (MANUFACTURER-SPECIFIED/INFERRED/UNKNOWN) and, if it fails its category's
    physical-plausibility bound, a validation_error. SENSITIVE/RESTRICTED documents always
    use the self-hosted backend, with no fallback to the external API; requesting
    "external" for one raises. A non-datasheet/application_note document is a no-op."""
    return _extract_components(document_id=document_id, requested_backend=requested_backend)


@function_tool
def lookup_digikey_component(part_number: str, license: str, classification: str) -> dict:
    """Search Digi-Key's Product Information API v4 for part_number, download its
    datasheet PDF, and ingest it into the knowledge base (source_type='datasheet') via
    ingest_document, unchanged. Refuses to run unless ALLOW_EXTERNAL_NETWORK_TOOLS=true
    AND DIGIKEY_CLIENT_ID/DIGIKEY_CLIENT_SECRET are configured (see .env.example) --
    this places a real, credentialed call to a third party. Returns {"status": "no_match"
    | "no_datasheet" | "ok", ...}; on "ok", "manufacturer"/"manufacturer_part_number" are
    Digi-Key's own report of the part's identity, for reconcile_component_sources to
    cross-check against Mouser's/Nexar's hit for the same part. Digi-Key's real API
    surface is verified against its own docs (see knowledge/digikey.py's module
    docstring) but NOT run against the real API in this environment -- treat any result
    as unverified end-to-end until it has been run against the real API at least once."""
    return _lookup_digikey_datasheet(part_number, license=license, classification=classification)


@function_tool
def lookup_mouser_component(part_number: str, license: str, classification: str) -> dict:
    """Same contract as lookup_digikey_component, against Mouser's Search API
    (MOUSER_API_KEY). Refuses to run unless ALLOW_EXTERNAL_NETWORK_TOOLS=true AND
    MOUSER_API_KEY is configured. Mouser's real API surface is corroborated from
    third-party integrations (see knowledge/mouser.py's module docstring's honest
    caveat -- Mouser's own Swagger spec sits behind a login wall) but NOT run against
    the real API in this environment."""
    return _lookup_mouser_datasheet(part_number, license=license, classification=classification)


@function_tool
def lookup_nexar_component(part_number: str, license: str, classification: str) -> dict:
    """Same contract as lookup_digikey_component, against Nexar's GraphQL API
    (Octopart data; NEXAR_CLIENT_ID/NEXAR_CLIENT_SECRET). Refuses to run unless
    ALLOW_EXTERNAL_NETWORK_TOOLS=true AND those credentials are configured. Nexar's
    free "Evaluation" tier caps around 1,000 matched parts. Nexar's real API surface is
    verified against its own docs (see knowledge/nexar.py's module docstring) but NOT
    run against the real API in this environment."""
    return _lookup_nexar_datasheet(part_number, license=license, classification=classification)


@function_tool(strict_mode=False)  # `matches` (a list of open-shaped distributor-hit
# dicts) and `datasheet_document_ids` (an open string-keyed map) don't fit the SDK's
# strict-schema requirement -- same rationale as create_design's `requirements`/
# `architecture` below.
def reconcile_component_sources(
    matches: list[dict],
    category: str,
    datasheet_document_ids: dict[str, int] | None = None,
) -> dict:
    """Reconcile two or three distributor lookups (lookup_digikey_component/
    lookup_mouser_component/lookup_nexar_component results for the SAME queried part
    number) into ONE components row instead of a duplicate per distributor --
    CONTEXT.md's Component identity, (manufacturer, part_number) with package/tape-
    and-reel suffix included, decides what counts as "the same part." Each entry in
    matches needs at least "distributor" and "manufacturer_part_number" (as returned
    by the lookup_* tools -- pass those results' fields straight through, do not
    reformat them). datasheet_document_ids optionally maps distributor name -> the
    document_id its ingest produced, so the resulting row links back to a real
    ingested datasheet; omitted or a group with no entry preserves whatever
    datasheet_document_id (and specifications) the row already had, rather than
    wiping either. category must be one of this repo's ten RF component categories
    (amplifier, filter, mixer, attenuator, coupler_splitter, circulator_isolator,
    switch, antenna, connector_cable, passive_component) -- never guessed from a
    distributor's own, differently-shaped catalog taxonomy. Runs automatically, no
    confirmation step, same posture as extract_components."""
    return _reconcile_components_from_matches(
        matches=matches, category=category, datasheet_document_ids=datasheet_document_ids
    )


# strict_mode=False: `requirements`/`architecture` are genuinely free-form
# JSON (arbitrary requirement_id keys; architecture shape isn't fixed by
# this ticket) -- the SDK's default strict-schema mode rejects an open
# `dict` parameter outright (`additionalProperties` must be false), which
# a fixed schema can't express here without inventing structure this
# ticket doesn't define.
@function_tool(strict_mode=False)
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
    per key, all starting NOT VERIFIED, so no stated requirement can end up
    with no verification row. Every component_id referenced anywhere in
    architecture must already exist in components -- a dangling reference
    is rejected with a structured error naming the offending block, never
    silently written."""
    return _create_design(
        design_key=design_key,
        name=name,
        revision=revision,
        requirements=requirements,
        architecture=architecture,
    )


@function_tool
def read_design(design_id: int) -> dict:
    """Fetch a stored design's full payload: design_key, name, revision, status,
    requirements, architecture (every component_id resolved inline to its
    manufacturer/part_number, not left as a bare id), and all engineering_results,
    decision_records (with approval_status), and verification_items rows. Returns
    a not-found result rather than raising if design_id doesn't exist."""
    return _read_design(design_id)


# strict_mode=False: `alternatives`/`evidence` are free-form JSON lists
# (each entry's shape isn't fixed by this ticket), same reasoning as
# create_design's requirements/architecture above.
@function_tool(strict_mode=False)
def record_decision(
    design_id: int,
    record_key: str,
    decision: str,
    alternatives: list,
    rationale: str,
    evidence: list,
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
    manufacturing_release tool or review UI exists)."""
    return _record_decision(
        design_id=design_id,
        record_key=record_key,
        decision=decision,
        alternatives=alternatives,
        rationale=rationale,
        evidence=evidence,
        approval_required=approval_required,
    )


# strict_mode=False: `expected`/`actual` are free-form JSON evidence values
# (a number, a dict of measured quantities, whatever the verification
# method produced) -- same open-schema reason as `create_design` above.
@function_tool(strict_mode=False)
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
    updates its verification_items row (auto-created by create_design) with
    method, status, expected, actual, evidence_uri, and notes. status must
    be one of NOT VERIFIED/PASS/FAIL/MARGINAL. Verification is always this
    explicit call -- never inferred by matching an engineering_results name
    against a requirement_id, since a wrong automatic guess would produce a
    silently wrong verification. A requirement_id with no matching row on
    this design_id is rejected with a structured error rather than
    creating a stray row. Folding a FAIL into any approval/release gate is
    out of scope here; this only records the status."""
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


@function_tool
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


@function_tool
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


@function_tool
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


@function_tool
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
    optimization), each using n_evaluations calls to the underlying calculation. Returns
    "CALCULATED" provenance, tagged with the method, objective description, and the
    fixed eps_r/w_m/h_m constraints that produced it -- see
    optimization/rf_objectives.py for why this wires ONE named objective, not an
    arbitrary optimization callable, across the tool boundary."""
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
# final ticket of the 23-ticket build-out). Three focused tools, per this
# ticket's own scope guidance -- start a loop, advance it one step, inspect
# its state -- added to the "principal" role only (this is a cross-cutting
# orchestration concern spanning every specialist's domain, not any one
# specialist's own scope). See orchestration/design_loop.py and
# orchestration/tooling.py for the state machine and approval-gate design.
#
# advance_design_loop_step's `approval` is REQUIRED whenever the loop's
# current step is ARCHITECTURE, MEASUREMENT, or REDESIGN_DECISION (every
# step that isn't a pure Phase 1 calculation or Phase 6-8 simulation run --
# orchestration/design_loop.py's GATED_STEPS) -- a receipt from a prior,
# separate call to orchestration.approval.request_loop_step_approval() for
# THIS EXACT loop/iteration/step/step_input combination. That function is
# deliberately NOT wired up as a fourth tool here (see
# orchestration/tooling.py's module docstring): it always raises without a
# real human-facing approval_callback, which no agent/MCP tool boundary in
# this project can supply, exactly as measurement/base.py's own instrument-
# actuation approval gate (issue #43) always raises through this tool
# surface. There is no code path from this loop to a manufacturing-release
# action -- see tests/test_design_loop.py's
# test_no_manufacturing_release_step_exists and its sibling tests.
#
# start_design_loop now creates a real `designs` row backing the loop
# (docs/adr/0011), and advance_design_loop_step's REDESIGN_DECISION
# transition flushes that iteration's decisions to the database -- see
# orchestration/tooling.py's module docstring for the persistence design,
# including the DesignLoopPersistenceError a failed flush raises.
# ---------------------------------------------------------------------------


@function_tool(strict_mode=False)  # `requirements` is a free-form dict --
# same rationale as run_nec2_simulation's geometry parameter above.
def start_design_loop(design_key: str, name: str, revision: str, requirements: dict) -> dict:
    """Start a new controlled design-iteration loop, backed by a real
    `designs` row created in `DRAFT` status (docs/adr/0011).

    `design_key`, `name`, and `revision` are exactly `designs.service.
    create_design`'s own fields for that row. `requirements` must be in
    that same function's shape -- a dict keyed by `requirement_id`, each
    value a dict carrying a non-empty string `requirement` field (e.g.
    `{"gain_req": {"requirement": "Gain >= 5 dBi over 2.4-2.5 GHz"}}`) --
    NOT the older free-form "customer requirement" shape (frequency band,
    gain/VSWR/bandwidth target, form factor, host-surface curvature,
    platform -- CONTEXT.md's "Customer requirement"); those descriptive
    details can still be carried as extra keys on each requirement, or as
    prose inside its `requirement` text, since only the `requirement`
    field itself is checked. A rejected `requirements` shape raises
    DesignLoopPersistenceError naming the problem, and no loop is started.

    Returns the new loop's state, positioned at the ARCHITECTURE step and
    additionally carrying `design_id` -- hold onto this dict and pass it
    back into advance_design_loop_step for every subsequent call; it is
    the whole loop's session token (this project has no long-running
    server process, so the state dict itself is still not persisted
    server-side -- only the loop's history, once flushed at an iteration
    boundary, is)."""
    return _start_new_design_loop(design_key, name, revision, requirements)


@function_tool(strict_mode=False)  # `state`/`step_input`/`approval` are
# free-form dicts whose shape depends on which of the loop's nine steps is
# current -- same rationale as run_nec2_simulation's geometry parameter
# above.
def advance_design_loop_step(state: dict, step_input: dict, approval: dict | None = None) -> dict:
    """Advance a design-iteration loop from its current step to the next
    one: requirements -> architecture -> analysis -> simulation ->
    optimization -> verification -> measurement -> correlation -> redesign
    (docs/BUILD_PLAN.md's Phase 12). `state` is a prior call's returned
    loop state. `step_input` is step-specific -- see
    orchestration/design_loop.py's per-step handlers for exactly what each
    current_step expects (e.g. ARCHITECTURE wants "decision"/"rationale";
    ANALYSIS wants the patch_resonant_frequency_hz inputs eps_r/w_m/h_m/
    l_m; SIMULATION wants the same geometry/frequency_hz run_nec2_
    simulation itself takes).

    `approval` is REQUIRED whenever the loop is currently at ARCHITECTURE,
    MEASUREMENT, or REDESIGN_DECISION -- every step that is not a pure
    calculation or simulation run. Without a valid one (bound to this exact
    loop/iteration/step/step_input combination), this raises and the loop
    does not advance; there is no way to skip a gated step from this tool.
    Check the returned state's "pending_approval" key (also available from
    inspect_design_loop_state) to see, at any point, whether the loop is
    currently blocked on an approval and which step it's blocked at.

    A REDESIGN_DECISION transition additionally flushes that iteration's
    decisions to the database and advances the backing design's status
    (docs/adr/0011). If that flush fails, this raises
    DesignLoopPersistenceError instead of returning: the `state` the
    caller already holds remains the only valid state, exactly as if the
    step had never advanced."""
    return _advance_design_loop_step(state, step_input, approval=approval)


@function_tool(strict_mode=False)  # `state` is a free-form dict (the loop's
# own session-token shape) -- same rationale as run_nec2_simulation's
# geometry parameter above.
def inspect_design_loop_state(state: dict) -> dict:
    """Return a design-iteration loop's current state -- current step,
    every decision recorded so far with its own provenance, and whether an
    approval is currently pending (and for which step). Safe to call at any
    point mid-loop, not just at completion; does not mutate or advance the
    loop, and does not touch the database."""
    return _inspect_design_loop_state(state)


# ---------------------------------------------------------------------------
# Specialist roles (issue #34) + principal delegation/synthesis (issue #35).
#
# The single generalist agent is split into six named roles, each scoped to a
# tool subset appropriate to its domain. `run()` below still drives the whole
# conversation through the "principal" role, same as before the split -- but
# the principal can now delegate a sub-question to any one specialist role
# and get its result back to synthesize into one answer (see "Principal
# delegation" below, after ROLES is built).
#
# Rationale for the tool split, by role:
#
#   - principal:   the coordinating/generalist role. Gets every currently
#                   wired tool -- it is the one role expected to reach across
#                   domains, so scoping it down would just recreate the
#                   single-agent behavior under a different name.
#   - systems:      link-level/systems-engineering concerns. Gets the
#                   cascaded gain/noise-figure/link-budget/IP3 tools,
#                   wavelength/electrical-size bookkeeping, the dB<->linear
#                   unit converters those calculations lean on, plus the
#                   knowledge-base *authoring* tools (ingest_document,
#                   index_document, and (ticket #67) lookup_digikey_component/
#                   lookup_mouser_component/lookup_nexar_component/
#                   reconcile_component_sources -- sourcing a datasheet
#                   straight from a distributor and reconciling it into one
#                   components row is the same authoring concern as manually
#                   ingesting one), since standing up the knowledge base for
#                   the team is systems-level work. Shares the cascaded-IP3/
#                   IM3 tools with microwave -- linearity budgeting is both a
#                   chain-level (systems) and single-stage (microwave)
#                   concern, same overlap already established for
#                   calculate_noise_figure. Does NOT get analyze_touchstone_
#                   file or the S/Z/Y/ABCD/stability/matching tools
#                   (device/network-level, not a systems-level concern) or
#                   the knowledge *auditing* tools (read_document/
#                   extract_components -- verification's job, see below).
#   - microwave:    passive/active RF component and network analysis. Gets
#                   VSWR, return loss, noise figure, Touchstone analysis, the
#                   S/Z/Y/ABCD two-port parameter conversions, stability
#                   (K-factor, Delta, stability circles), impedance-matching
#                   synthesis (quarter-wave, L-network), and (shared with
#                   systems, see above) the IP3/IM3 tools. Does NOT get
#                   calculate_cascade_gain (a system-chain concern, not a
#                   single component/network concern), link budget, or the
#                   knowledge-authoring tools.
#   - antenna:      antenna-specific. Gets wavelength (electrical size),
#                   VSWR/return loss (antenna input match), Touchstone
#                   analysis (antenna port measurements), the Phase 1
#                   antenna-synthesis tools (patch effective permittivity/
#                   length extension/resonant frequency, fractional-
#                   bandwidth<->Q, curvature-shifted resonant frequency,
#                   Maxwell-Garnett metamaterial permeability, aperture
#                   gain), the dB<->linear unit converters aperture gain
#                   composes with, (issue #38) run_nec2_simulation --
#                   simulating a wire-antenna structure's impedance/pattern/
#                   gain is squarely antenna-element work -- and (issue #39)
#                   run_openems_simulation, the FDTD counterpart for
#                   conformal/curved or metamaterial geometry NEC2++'s wire
#                   method-of-moments can't adequately model, and (issue
#                   #63) run_gprmax_simulation, the ground-coupled/lossy-
#                   half-space FDTD counterpart for when the host surface
#                   is a real lossy dielectric (soil, concrete, a vehicle
#                   hull) neither NEC2++'s ground models nor openEMS's
#                   adapter can represent, and (issue #66)
#                   generate_freecad_curved_geometry, mapping a flat unit-cell/
#                   array layout onto a curved host surface (cylinder/sphere) --
#                   the geometry-prep step for a real conformal antenna, feeding
#                   straight into run_openems_simulation's/run_palace_simulation's
#                   own geometry dict, and (issue
#                   #41) optimize_patch_length_for_target_frequency --
#                   searching patch length against a target resonant
#                   frequency via the generic optimization/ package's
#                   parameter sweep/grid search/Bayesian optimization is
#                   antenna-synthesis work, the same family as the Phase 1
#                   patch-resonant-frequency tool it composes with. Does
#                   NOT get calculate_noise_figure or calculate_cascade_gain
#                   (receiver-chain concerns, not the antenna element
#                   itself) or the S/Z/Y/ABCD/stability/matching tools
#                   (microwave's job).
#   - test:         verification/measurement-adjacent. Gets Touchstone
#                   analysis (the measured-network artifact) plus the new
#                   Touchstone capabilities that are squarely test-engineering
#                   work -- interpolation onto a target grid, fixture
#                   de-embedding, network cascading, and quantified
#                   measured-vs-predicted comparison -- plus VSWR, return
#                   loss, and cascade gain for comparing a measured chain
#                   against its predicted/spec values, plus (issue #38, #39,
#                   #63) run_nec2_simulation, run_openems_simulation, and
#                   run_gprmax_simulation --
#                   generating a SIMULATED-provenance reference result is
#                   itself something a measured result gets validated
#                   against. Does NOT get any knowledge-
#                   authoring or knowledge-auditing tool -- test validates
#                   hardware against a spec, it doesn't ingest or extract
#                   documents.
#   - verification: knowledge/provenance-checking, per the ticket's own
#                   frame. Gets the knowledge-base *auditing* tools
#                   (read_document, extract_components) that check what's
#                   already in the knowledge base against its source and
#                   provenance, plus (issue #37) search_design_records --
#                   looking up whether a prior design/decision record exists
#                   for a given precedent is itself a knowledge-audit
#                   question, same family as read_document/extract_components,
#                   not an authoring action. Does NOT get ingest_document/
#                   index_document (authoring is systems' job -- verification
#                   checks the result, it doesn't add to the store) or any
#                   calculation tool (verification audits documented/
#                   extracted claims and their provenance, it does not
#                   itself run RF arithmetic).
#
#   search_knowledge is shared by every role: literature lookup is useful
#   regardless of domain, and giving every role its own copy of the same
#   tool object is the intended (not accidental) overlap the ticket calls
#   out as fine. search_design_records (issue #37) is scoped more narrowly
#   than search_knowledge -- it is a knowledge-audit tool (see verification,
#   above), so it is only on the principal (which gets every tool) and
#   verification, not every specialist.
# ---------------------------------------------------------------------------

_ALL_TOOLS = [
    calculate_wavelength,
    calculate_vswr,
    calculate_return_loss,
    calculate_cascade_gain,
    calculate_noise_figure,
    analyze_touchstone_file,
    convert_db_to_linear,
    convert_linear_to_db,
    convert_s_to_z,
    convert_z_to_s,
    convert_s_to_y,
    convert_y_to_s,
    convert_s_to_abcd,
    convert_abcd_to_s,
    calculate_free_space_path_loss,
    calculate_link_budget_margin,
    calculate_cascade_output_ip3,
    calculate_oip3_from_iip3,
    calculate_iip3_from_oip3,
    calculate_third_order_intermod_output,
    calculate_third_order_intermod_dbc,
    calculate_stability_delta,
    calculate_rollett_k_factor,
    calculate_stability_verdict,
    calculate_output_stability_circle,
    calculate_input_stability_circle,
    calculate_quarter_wave_transformer_impedance,
    calculate_l_network_match,
    calculate_patch_effective_permittivity,
    calculate_patch_length_extension,
    calculate_patch_resonant_frequency,
    calculate_fractional_bandwidth_from_q,
    calculate_quality_factor_from_fractional_bandwidth,
    calculate_curvature_length_correction_factor,
    calculate_curvature_shifted_resonant_frequency,
    calculate_maxwell_garnett_effective_permeability,
    calculate_aperture_gain,
    interpolate_touchstone_file,
    deembed_touchstone_file,
    cascade_touchstone_files,
    compare_touchstone_files,
    correlate_simulated_and_measured,
    run_nec2_simulation,
    run_openems_simulation,
    run_qucs_simulation,
    run_gprmax_simulation,
    run_hfss_simulation,
    run_openparem_simulation,
    run_elmer_simulation,
    run_ltspice_simulation,
    run_kicad_gerber2ems_simulation,
    run_ngspice_simulation,
    run_xyce_simulation,
    run_palace_simulation,
    run_meep_simulation,
    generate_freecad_curved_geometry,
    request_vna_measurement_approval,
    measure_vna_s_parameters,
    request_spectrum_analyzer_measurement_approval,
    measure_spectrum_analyzer_trace,
    request_signal_generator_output_approval,
    set_signal_generator_output,
    request_power_meter_measurement_approval,
    measure_power_meter_reading,
    ingest_document,
    index_document,
    read_document,
    search_knowledge,
    search_design_records,
    extract_components,
    lookup_digikey_component,
    lookup_mouser_component,
    lookup_nexar_component,
    reconcile_component_sources,
    create_design,
    read_design,
    record_decision,
    verify_requirement,
    propose_requirement_target,
    mark_requirement_unscoreable,
    confirm_requirement_target,
    optimize_patch_length_for_target_frequency,
    start_design_loop,
    advance_design_loop_step,
    inspect_design_loop_state,
]

assert_all_tools_categorized([tool.name for tool in _ALL_TOOLS])


@dataclass(frozen=True)
class RoleSpec:
    """One specialist role: its display name, tool subset, and the domain
    note appended to the shared system prompt explaining that scope."""

    key: str
    display_name: str
    domain_note: str
    tools: list = field(default_factory=list)


ROLE_SPECS: list[RoleSpec] = [
    RoleSpec(
        key="principal",
        display_name="Principal RF Engineer",
        domain_note=(
            "You are the coordinating principal-level reviewer, with access to "
            "every tool below. Bring in a specialist's perspective (systems, "
            "microwave, antenna, test, verification) as the problem requires. "
            "You alone also hold the controlled design-iteration loop tools "
            "(start_design_loop/advance_design_loop_step/"
            "inspect_design_loop_state, issue #46) -- walking a design through "
            "requirements/architecture/analysis/simulation/optimization/"
            "verification/measurement/correlation/redesign is a cross-cutting "
            "orchestration concern spanning every specialist's domain, not any "
            "one specialist's own scope. Advancing past an architecture "
            "decision, physical measurement, or a redesign/iteration decision "
            "always requires a distinct human-approval receipt first -- this "
            "loop never reaches, and has no path to, an autonomous "
            "manufacturing-release action."
        ),
        tools=list(_ALL_TOOLS),
    ),
    RoleSpec(
        key="systems",
        display_name="Systems RF Engineer",
        domain_note=(
            "You focus on link-level and systems-engineering concerns: cascaded "
            "gain/noise-figure budgets, wavelength/electrical-size bookkeeping, "
            "and standing up the knowledge base (ingesting and indexing "
            "documents, and sourcing component datasheets directly from "
            "Digi-Key/Mouser/Nexar) other roles rely on. Defer network-level "
            "S-parameter detail to the microwave role and document auditing to "
            "the verification role."
        ),
        tools=[
            calculate_wavelength,
            calculate_vswr,
            calculate_return_loss,
            calculate_cascade_gain,
            calculate_noise_figure,
            convert_db_to_linear,
            convert_linear_to_db,
            calculate_free_space_path_loss,
            calculate_link_budget_margin,
            calculate_cascade_output_ip3,
            calculate_oip3_from_iip3,
            calculate_iip3_from_oip3,
            calculate_third_order_intermod_output,
            calculate_third_order_intermod_dbc,
            ingest_document,
            index_document,
            search_knowledge,
            lookup_digikey_component,
            lookup_mouser_component,
            lookup_nexar_component,
            reconcile_component_sources,
        ],
    ),
    RoleSpec(
        key="microwave",
        display_name="Microwave Engineer",
        domain_note=(
            "You focus on passive/active RF component and network analysis: "
            "input match (VSWR, return loss), noise figure, Touchstone (.sNp) "
            "network data, S/Z/Y/ABCD two-port parameter conversions, "
            "stability (K-factor, Delta, stability circles), impedance-"
            "matching synthesis (quarter-wave transformer, L-network), "
            "IP3/IM3 linearity, and (issue #58) schematic-level circuit "
            "simulation of a matching network/filter/feed network via "
            "Qucs-S's qucsator_rf engine (run_qucs_simulation) -- the free/"
            "GPL alternative to Keysight ADS, returning the full native "
            "N-port S-parameter matrix from a single run. Also gets LTspice "
            "circuit simulation (run_ltspice_simulation, issue #59) for "
            "SPICE-level transistor/matching-network circuit validation "
            "against a vendor device-model library -- the lowest-priority, "
            "lowest-investment item in this repo's 'ADS alternative' batch "
            "(its value is vendor-model-library familiarity, not new "
            "capability). Also gets (issue #57) run_ngspice_simulation and "
            "run_xyce_simulation -- free/open circuit-level SPICE "
            "simulation of a matching network, filter, or amplifier bias/"
            "termination sub-circuit (no paid ADS license needed); prefer "
            "run_xyce_simulation over run_ngspice_simulation for a larger "
            "circuit or when real S-parameters are needed (Xyce's native "
            "`.LIN` analysis produces a genuine Touchstone file, subject to "
            "its own honest confidence caveat -- see simulation/xyce.py's "
            "module docstring; ngspice has no built-in S-parameter analysis "
            "at all). Defer system-chain-level gain/link budgeting to the "
            "systems role."
        ),
        tools=[
            calculate_vswr,
            calculate_return_loss,
            calculate_noise_figure,
            analyze_touchstone_file,
            convert_db_to_linear,
            convert_linear_to_db,
            convert_s_to_z,
            convert_z_to_s,
            convert_s_to_y,
            convert_y_to_s,
            convert_s_to_abcd,
            convert_abcd_to_s,
            calculate_cascade_output_ip3,
            calculate_oip3_from_iip3,
            calculate_iip3_from_oip3,
            calculate_third_order_intermod_output,
            calculate_third_order_intermod_dbc,
            calculate_stability_delta,
            calculate_rollett_k_factor,
            calculate_stability_verdict,
            calculate_output_stability_circle,
            calculate_input_stability_circle,
            calculate_quarter_wave_transformer_impedance,
            calculate_l_network_match,
            run_qucs_simulation,
            run_ltspice_simulation,
            run_ngspice_simulation,
            run_xyce_simulation,
            search_knowledge,
        ],
    ),
    RoleSpec(
        key="antenna",
        display_name="Antenna Engineer",
        domain_note=(
            "You focus on antenna-specific concerns: electrical size "
            "(wavelength), input match at the antenna port (VSWR, return "
            "loss), Touchstone measurements of antenna ports, and antenna "
            "synthesis (patch effective permittivity/length extension/"
            "resonant frequency, fractional-bandwidth<->Q, curvature-shifted "
            "resonant frequency, Maxwell-Garnett metamaterial permeability, "
            "aperture gain), NEC2++ wire-antenna simulation "
            "(run_nec2_simulation) for SIMULATED-provenance impedance/"
            "pattern/gain, openEMS FDTD simulation "
            "(run_openems_simulation) for conformal/curved or metamaterial "
            "geometry NEC2++'s wire method-of-moments can't adequately "
            "model -- its convergence metadata is real, but S-parameter/"
            "far-field extraction is not computed in this pass (see "
            "simulation/openems.py) -- gprMax FDTD simulation "
            "(run_gprmax_simulation, issue #63) for a ground-coupled or "
            "lossy-half-space host surface (soil, concrete, a vehicle "
            "hull) that NEC2++'s ground models and openEMS's adapter can't "
            "represent -- its S-parameters/input impedance are real, "
            "FFT-computed from the excited port's own voltage/current "
            "dumps, but it deliberately does not use gprMax's bundled "
            "commercial-GPR-antenna model library (see simulation/"
            "gprmax.py) -- and full-wave HFSS simulation via "
            "PyAEDT (run_hfss_simulation) for real S-parameter/report "
            "extraction, confined to a controlled licensed workstation "
            "(it refuses to run anywhere else, including this one), "
            "OpenParEM3D full-wave FEM simulation (run_openparem_"
            "simulation, issue #62) for antenna-specific far-field gain/"
            "directivity/radiation-efficiency computed from the SAME solve "
            "as its S-parameters -- requires an already-meshed Gmsh file "
            "(mesh generation is out of scope, see simulation/openparem.py) "
            "and is young/less battle-tested than the other three "
            "simulators, Elmer FEM's VectorHelmholtz simulation "
            "(run_elmer_simulation, issue #64) as a general, multiphysics-"
            "ready EM cross-check kept available for a future coupled-"
            "physics need (e.g. EM/thermal on a mounted 'adaptive EM "
            "skin') -- NOT a substitute for the three tools above on "
            "everyday antenna work, since Elmer's VectorHelmholtz module "
            "has no native antenna-specific port/S-parameter/far-field/"
            "gain post-processing (its excitation and boundary conditions "
            "are hand-assembled, see simulation/elmer.py), "
            "(issue #65) run_kicad_gerber2ems_simulation for a REAL, "
            "as-laid-out KiCad PCB design (not a hand-modeled geometry "
            "dict) -- gerber2ems drives openEMS internally via its own "
            "Python interface and is scoped explicitly to PCB "
            "signal-integrity results (trace impedance, via/stackup "
            "S-parameters), NOT far-field/gain, so use it for a "
            "PCB-etched antenna feed network's real copper geometry, not "
            "the radiating element's own pattern/gain, and full-wave "
            "Palace simulation with NATIVE Floquet/periodic-boundary "
            "ports (run_palace_simulation, issue #61) for a periodic "
            "metamaterial unit cell's actual electromagnetic behavior -- "
            "the only simulator here that can characterize a repeating-"
            "element design at all (embedded PEC conductor patches -- a "
            "metallic metasurface pattern, as opposed to an all-dielectric "
            "grating/photonic-crystal cell -- are not supported yet, see "
            "simulation/palace.py), and MEEP FDTD simulation "
            "(run_meep_simulation, issue #60) as a SECOND, INDEPENDENT "
            "full-wave solver to cross-check a design decision against "
            "run_openems_simulation's output instead of resting on one "
            "solver alone -- power-reflectance/|S11| magnitude only, no "
            "phase or S21 (see simulation/meep.py). Also gets "
            "generate_freecad_curved_geometry (issue #66) to map a flat unit-cell/"
            "array layout (e.g. from geometry.unit_cell, issue #55) onto a curved "
            "host surface (cylinder or sphere) -- the flat-vs-conformal geometry "
            "prep step for a real wrap-around antenna, feeding straight into "
            "run_openems_simulation's/run_palace_simulation's own geometry dict; "
            "drives a headless FreeCADCmd macro to also build a real, exact 3D "
            "STEP model, but the returned geometry-dict is itself a staircase-"
            "style approximation since CSXCAD's Polygon primitive cannot express "
            "an arbitrarily tilted plane (see geometry/freecad_curved.py). Also "
            "gets optimize_patch_length_for_target_frequency (issue #41) "
            "to search patch length against a target resonant frequency "
            "via parameter sweep, grid search, or Bayesian optimization "
            "(all built on the generic optimization/ package). Defer "
            "receiver-chain noise figure and cascaded gain to the systems "
            "role, and S/Z/Y/ABCD/stability/matching tools to the "
            "microwave role."
        ),
        tools=[
            calculate_wavelength,
            calculate_vswr,
            calculate_return_loss,
            analyze_touchstone_file,
            convert_db_to_linear,
            convert_linear_to_db,
            calculate_patch_effective_permittivity,
            calculate_patch_length_extension,
            calculate_patch_resonant_frequency,
            calculate_fractional_bandwidth_from_q,
            calculate_quality_factor_from_fractional_bandwidth,
            calculate_curvature_length_correction_factor,
            calculate_curvature_shifted_resonant_frequency,
            calculate_maxwell_garnett_effective_permeability,
            calculate_aperture_gain,
            run_nec2_simulation,
            run_openems_simulation,
            run_gprmax_simulation,
            run_hfss_simulation,
            run_openparem_simulation,
            run_elmer_simulation,
            run_kicad_gerber2ems_simulation,
            run_palace_simulation,
            run_meep_simulation,
            generate_freecad_curved_geometry,
            optimize_patch_length_for_target_frequency,
            search_knowledge,
        ],
    ),
    RoleSpec(
        key="test",
        display_name="Test Engineer",
        domain_note=(
            "You focus on verification and measurement: analyzing Touchstone "
            "network data (including interpolation onto a target grid, "
            "fixture de-embedding, network cascading, and quantified "
            "measured-vs-predicted comparison) and comparing measured VSWR/"
            "return loss/cascaded gain against predicted or specified "
            "values, including SIMULATED-provenance NEC2++ "
            "(run_nec2_simulation), openEMS (run_openems_simulation), "
            "HFSS (run_hfss_simulation, controlled-licensed-workstation-"
            "only), Elmer FEM VectorHelmholtz (run_elmer_simulation, "
            "issue #64 -- a general multiphysics-ready cross-check with no "
            "native S-parameter/far-field/gain post-processing, see "
            "simulation/elmer.py), LTspice (run_ltspice_simulation, "
            "issue #59), Qucs-S/qucsator_rf circuit simulation "
            "(run_qucs_simulation, issue #58), (issue #65) gerber2ems "
            "PCB signal-integrity (run_kicad_gerber2ems_simulation, trace "
            "impedance and via/stackup S-parameters from a real KiCad PCB "
            "design), (issue #57) ngspice/Xyce (run_ngspice_simulation, "
            "run_xyce_simulation) circuit-level, Palace "
            "(run_palace_simulation, issue #61 -- native Floquet/periodic-"
            "port full-wave results for a metamaterial unit cell), gprMax "
            "(run_gprmax_simulation, issue #63, ground-coupled/lossy-"
            "half-space), and MEEP (run_meep_simulation, issue #60 -- a "
            "second, independent full-wave solver for cross-checking a "
            "design decision instead of resting on one solver's output "
            "alone) reference results to validate hardware against. Use "
            "correlate_simulated_and_measured (issue #45) to quantify how "
            "well a simulated result matches a measured one -- common "
            "frequency grid/reference impedance normalization, optional "
            "fixture de-embedding (calibration-plane normalization), and a "
            "per-S-parameter error metric across frequency, not a bare "
            "pass/fail -- so you can judge how much to trust a given "
            "simulation for similar future designs, including OpenParEM3D "
            "(run_openparem_simulation, issue #62) reference results, whose "
            "S-parameters and far-field gain/directivity/efficiency come "
            "from the same solve. You also "
            "get the real physical-instrument measurement tools for the "
            "full standard test-bench set (issue #43's VNA adapter plus "
            "issue #44's spectrum analyzer, signal generator, and power "
            "meter adapters) -- request_vna_measurement_approval/"
            "measure_vna_s_parameters, "
            "request_spectrum_analyzer_measurement_approval/"
            "measure_spectrum_analyzer_trace, "
            "request_signal_generator_output_approval/"
            "set_signal_generator_output, and "
            "request_power_meter_measurement_approval/"
            "measure_power_meter_reading -- for pulling real "
            "MEASURED-provenance data off physical instruments via SCPI/"
            "VISA (or, for the signal generator, commanding one). Each "
            "instrument is deliberately TWO separate tools, not one with a "
            "boolean flag: physical lab instruments are never controlled "
            "autonomously in this project (README.md, docs/BUILD_PLAN.md's "
            "Phase 10, docs/SECURITY.md), so a real instrument actuation "
            "requires a distinct approval receipt from the first tool of "
            "each pair before the second will run -- and in this "
            "codebase's current state, every one of these four "
            "approval-request tools always raises, since no human-facing "
            "approval workflow is wired up yet. The signal generator pair "
            "is the one that actively outputs RF power (not just observes, "
            "like the others), so its approval fingerprint additionally "
            "binds to the exact power level and on/off state requested, "
            "not just frequency. You do not ingest or extract documents -- "
            "that is the systems/verification roles' job."
        ),
        tools=[
            analyze_touchstone_file,
            interpolate_touchstone_file,
            deembed_touchstone_file,
            cascade_touchstone_files,
            compare_touchstone_files,
            correlate_simulated_and_measured,
            calculate_vswr,
            calculate_return_loss,
            calculate_cascade_gain,
            run_nec2_simulation,
            run_openems_simulation,
            run_qucs_simulation,
            run_gprmax_simulation,
            run_hfss_simulation,
            run_openparem_simulation,
            run_elmer_simulation,
            run_ltspice_simulation,
            run_kicad_gerber2ems_simulation,
            run_ngspice_simulation,
            run_xyce_simulation,
            run_palace_simulation,
            run_meep_simulation,
            request_vna_measurement_approval,
            measure_vna_s_parameters,
            request_spectrum_analyzer_measurement_approval,
            measure_spectrum_analyzer_trace,
            request_signal_generator_output_approval,
            set_signal_generator_output,
            request_power_meter_measurement_approval,
            measure_power_meter_reading,
            search_knowledge,
        ],
    ),
    RoleSpec(
        key="verification",
        display_name="Verification Engineer",
        domain_note=(
            "You focus on knowledge and provenance checking: reading a stored "
            "document's full metadata and chunks, extracting/auditing "
            "structured component specifications with their per-field "
            "provenance, and looking up prior design/decision records for "
            "precedent. You do not run RF calculations yourself and you do "
            "not add new documents to the knowledge base -- you audit what is "
            "already there."
        ),
        tools=[
            read_document,
            search_knowledge,
            search_design_records,
            extract_components,
        ],
    ),
]

_SPEC_BY_KEY: dict[str, RoleSpec] = {spec.key: spec for spec in ROLE_SPECS}
_SPECIALIST_KEYS = [key for key in _SPEC_BY_KEY if key != "principal"]

# Build the five specialist agents first (systems, microwave, antenna, test,
# verification). None of them delegate further -- only the principal role
# gets delegation tools, below -- so this is a plain, non-circular build.
ROLES: dict[str, Agent] = {
    key: Agent(
        name=_SPEC_BY_KEY[key].display_name,
        model=_resolve_agent_model(),
        instructions=f"{SYSTEM_PROMPT}\n\n## Role scope\n\n{_SPEC_BY_KEY[key].domain_note}",
        tools=list(_SPEC_BY_KEY[key].tools),
    )
    for key in _SPECIALIST_KEYS
}

# ---------------------------------------------------------------------------
# Principal delegation and synthesis (issue #35).
#
# `openai-agents` (>=0.17.4) offers two distinct mechanisms for one agent to
# involve another:
#
#   - `Agent(handoffs=[...])`: one-way control transfer. The target agent
#     takes over the *whole* conversation; the original agent never
#     regains control and never sees a return value.
#   - `Agent.as_tool(...)`: wraps an agent as a `FunctionTool` callable by
#     another agent. The nested agent runs on generated input, its result
#     comes back as the tool's return value, and the *calling* agent keeps
#     driving the conversation and can call further tools/roles afterward.
#
# The ticket's acceptance criteria -- "delegate a sub-question ... and
# receive its structured/provenance-tagged result back", "keeps composing",
# "cites which specialist role(s) contributed which part" -- describes the
# second shape, not the first: the principal must stay in control and weave
# multiple specialists' answers into one response, not hand off and vanish.
# So this uses `Agent.as_tool()`, confirmed present on the installed SDK
# (agents.Agent.as_tool, see agents/agent.py) rather than `handoffs`.
#
# Each specialist is wrapped as a `consult_<role>_role` tool on the
# principal only (specialists do not delegate to each other, avoiding
# delegation cycles). `custom_output_extractor` prefixes every nested run's
# final output with that role's display name in square brackets --
# deterministic code, not LLM cooperation -- so any specialist contribution
# that reaches the principal's tool-call history is already citable by role
# by construction; the principal's instructions additionally ask it to
# carry that citation through into its own final answer.
# ---------------------------------------------------------------------------


def _specialist_output_tag(spec: RoleSpec, run_result: RunResult) -> str:
    """Prefix a nested specialist run's final output with its role name, so
    a delegated result is citable by role wherever it is quoted or logged."""
    return f"[{spec.display_name}] {run_result.final_output}"


def _make_delegation_tool(key: str) -> FunctionTool:
    spec = _SPEC_BY_KEY[key]
    role_agent = ROLES[key]

    async def _tag_output(run_result: RunResult) -> str:
        return _specialist_output_tag(spec, run_result)

    return role_agent.as_tool(
        tool_name=f"consult_{key}_role",
        tool_description=(
            f"Delegate a sub-question to the {spec.display_name} specialist role "
            f"and receive its structured, provenance-tagged result back so you can "
            f"synthesize it into your own answer. {spec.domain_note} Its response "
            f"is prefixed with '[{spec.display_name}]' -- carry that citation "
            f"through into your final answer so the reader can see which "
            f"specialist role(s) contributed which part."
        ),
        custom_output_extractor=_tag_output,
    )


DELEGATION_TOOLS: dict[str, FunctionTool] = {
    key: _make_delegation_tool(key) for key in _SPECIALIST_KEYS
}

_principal_spec = _SPEC_BY_KEY["principal"]
ROLES["principal"] = Agent(
    name=_principal_spec.display_name,
    model=_resolve_agent_model(),
    instructions=(
        f"{SYSTEM_PROMPT}\n\n## Role scope\n\n{_principal_spec.domain_note}"
        "\n\n## Delegating to specialists\n\n"
        "For a multi-domain question, call the relevant `consult_<role>_role` "
        "tool(s) (systems, microwave, antenna, test, verification) instead of "
        "guessing at their domain expertise yourself. Each tool's result comes "
        "back prefixed with '[<Role Name>]'; when you synthesize your final "
        "answer, keep that attribution visible so it is clear which "
        "specialist role(s) contributed which part of the answer."
    ),
    tools=list(_ALL_TOOLS) + list(DELEGATION_TOOLS.values()),
)

# Kept as a module-level name for backward compatibility.
principal = ROLES["principal"]


def run(query: str) -> str:
    result = Runner.run_sync(principal, query)
    return result.final_output

if __name__ == "__main__":
    import sys
    query = " ".join(sys.argv[1:]) or (
        "Explain the engineering workflow you will use for RF design and identify "
        "which claims require calculation, simulation, measurement, or human approval."
    )
    print(run(query))
