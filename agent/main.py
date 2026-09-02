import os
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from agents import Agent, FunctionTool, Runner, function_tool
from agents.run import RunResult
from dotenv import load_dotenv

from knowledge.extract import extract_components as _extract_components
from knowledge.index import index_document as _index_document
from knowledge.ingest import ingest_document as _ingest_document
from knowledge.read import read_document as _read_document
from knowledge.search import search_design_records as _search_design_records
from knowledge.search import search_knowledge as _search_knowledge
from optimization.rf_objectives import (
    optimize_patch_length_for_target_frequency as _optimize_patch_length_for_target_frequency,
)
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
from rf_tools.touchstone import (
    analyze_touchstone,
    cascade_touchstone,
    compare_touchstone,
    deembed_touchstone,
    interpolate_touchstone,
)
from simulation.hfss import run_hfss_simulation as _run_hfss_simulation
from simulation.nec2pp import run_nec2_simulation as _run_nec2_simulation
from simulation.openems import run_openems_simulation as _run_openems_simulation

load_dotenv()

PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "principal_engineer.md"
SYSTEM_PROMPT = PROMPT_PATH.read_text(encoding="utf-8")


@function_tool
def calculate_wavelength(frequency_hz: float) -> float:
    """Calculate free-space wavelength in meters for a given frequency in Hz."""
    return wavelength(frequency_hz)


@function_tool
def calculate_vswr(reflection_coefficient_magnitude: float) -> float:
    """Calculate VSWR from the magnitude of the reflection coefficient (|Gamma|)."""
    return vswr_from_gamma(reflection_coefficient_magnitude)


@function_tool
def calculate_return_loss(reflection_coefficient_magnitude: float) -> float:
    """Calculate return loss in dB from the magnitude of the reflection coefficient (|Gamma|)."""
    return return_loss_db(reflection_coefficient_magnitude)


@function_tool
def calculate_cascade_gain(gains_db: list[float]) -> float:
    """Calculate the total cascaded gain in dB for a chain of stage gains in dB."""
    return cascade_gain_db(gains_db)


@function_tool
def calculate_noise_figure(noise_factors: list[float], gains_linear: list[float]) -> dict:
    """Calculate cascaded noise factor and noise figure (Friis equation) for a chain of
    stages, given each stage's linear noise factor and linear gain."""
    f_total = friis_noise_factor(noise_factors, gains_linear)
    return {
        "noise_factor": f_total,
        "noise_figure_db": noise_factor_to_db(f_total),
        "provenance": "CALCULATED",
    }


@function_tool
def analyze_touchstone_file(path: str) -> dict:
    """Analyze a local Touchstone network file (.sNp) and return port count, frequency
    range, and S11/S21 extrema."""
    result = analyze_touchstone(path)
    result["provenance"] = "CALCULATED"
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


@function_tool
def compare_touchstone_files(path_a: str, path_b: str) -> dict:
    """Quantify how two Touchstone networks differ, per S-parameter (max/RMS magnitude
    difference and per-point complex difference across their common frequency grid). Both
    networks must have the same port count and an overlapping frequency range."""
    result = compare_touchstone(path_a, path_b)
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
    jsonified["provenance"] = "CALCULATED"
    return jsonified


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
    can't adequately model. Returns "SIMULATED" provenance. IMPORTANT SCOPE LIMIT:
    S-parameter and far-field extraction are NOT computed in this implementation --
    they require FFT post-processing of port time-domain data and openEMS's separate
    nf2ff tool, both out of scope for this pass (see simulation/openems.py's module
    docstring); only convergence metadata is real. Format verified against primary
    openEMS/CSXCAD documentation (see simulation/openems.py's module docstring for
    citations) but NOT against a real openEMS binary -- none is installed in this
    environment; treat any result as unverified end-to-end until it has been run
    against the real tool at least once."""
    return _run_openems_simulation(geometry=geometry, fdtd=fdtd, timeout_s=timeout_s)


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
#                   unit converters those calculations lean on, plus the two
#                   knowledge-base *authoring* tools (ingest_document,
#                   index_document), since standing up the knowledge base for
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
#                   against its predicted/spec values, plus (issue #38, #39)
#                   run_nec2_simulation and run_openems_simulation --
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
    run_nec2_simulation,
    run_openems_simulation,
    run_hfss_simulation,
    ingest_document,
    index_document,
    read_document,
    search_knowledge,
    search_design_records,
    extract_components,
    optimize_patch_length_for_target_frequency,
]


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
            "microwave, antenna, test, verification) as the problem requires."
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
            "documents) other roles rely on. Defer network-level S-parameter "
            "detail to the microwave role and document auditing to the "
            "verification role."
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
            "matching synthesis (quarter-wave transformer, L-network), and "
            "IP3/IM3 linearity. Defer system-chain-level gain/link budgeting "
            "to the systems role."
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
            "simulation/openems.py) -- and full-wave HFSS simulation via "
            "PyAEDT (run_hfss_simulation) for real S-parameter/report "
            "extraction, confined to a controlled licensed workstation "
            "(it refuses to run anywhere else, including this one). Also "
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
            run_hfss_simulation,
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
            "(run_nec2_simulation), openEMS (run_openems_simulation), and "
            "HFSS (run_hfss_simulation, controlled-licensed-workstation-"
            "only) reference results to validate hardware against. You do "
            "not ingest or extract documents -- that is the systems/"
            "verification roles' job."
        ),
        tools=[
            analyze_touchstone_file,
            interpolate_touchstone_file,
            deembed_touchstone_file,
            cascade_touchstone_files,
            compare_touchstone_files,
            calculate_vswr,
            calculate_return_loss,
            calculate_cascade_gain,
            run_nec2_simulation,
            run_openems_simulation,
            run_hfss_simulation,
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
        model=os.getenv("OPENAI_MODEL", "gpt-5.5"),
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
    model=os.getenv("OPENAI_MODEL", "gpt-5.5"),
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
