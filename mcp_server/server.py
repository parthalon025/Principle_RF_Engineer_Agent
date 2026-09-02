import numpy as np
from mcp.server.fastmcp import FastMCP

from knowledge.extract import extract_components as _extract_components
from knowledge.index import index_document as _index_document
from knowledge.ingest import ingest_document as _ingest_document
from knowledge.read import read_document as _read_document
from knowledge.search import search_knowledge as _search_knowledge
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

mcp = FastMCP("principal-rf-engineer")


@mcp.tool()
def calculate_wavelength(frequency_hz: float) -> float:
    """Calculate free-space wavelength in meters."""
    return wavelength(frequency_hz)


@mcp.tool()
def calculate_vswr(reflection_coefficient_magnitude: float) -> float:
    """Calculate VSWR from |Gamma|."""
    return vswr_from_gamma(reflection_coefficient_magnitude)


@mcp.tool()
def calculate_return_loss(reflection_coefficient_magnitude: float) -> float:
    """Calculate return loss in dB from |Gamma|."""
    return return_loss_db(reflection_coefficient_magnitude)


@mcp.tool()
def calculate_cascade_gain(gains_db: list[float]) -> float:
    """Calculate cascaded gain in dB."""
    return cascade_gain_db(gains_db)


@mcp.tool()
def calculate_noise_figure(
    noise_factors: list[float], gains_linear: list[float]
) -> dict:
    """Calculate cascaded noise factor and noise figure."""
    f_total = friis_noise_factor(noise_factors, gains_linear)
    return {
        "noise_factor": f_total,
        "noise_figure_db": noise_factor_to_db(f_total),
        "provenance": "CALCULATED",
    }


@mcp.tool()
def analyze_touchstone_file(path: str) -> dict:
    """Analyze a local Touchstone network file."""
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
def calculate_curvature_length_correction_factor(
    l_m: float, radius_of_curvature_m: float
) -> dict:
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


@mcp.tool()
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


@mcp.tool()
def ingest_document(
    file_path: str,
    source_type: str,
    license: str,
    classification: str,
    supersedes_document_id: int | None = None,
) -> dict:
    """Parse a datasheet/standard/textbook/paper PDF via docling, chunk it, and store it.
    Pass supersedes_document_id to declare this upload a newer revision of that document
    (never inferred from title); omit it for a plain new, independent document."""
    return _ingest_document(
        file_path=file_path,
        source_type=source_type,
        license=license,
        classification=classification,
        supersedes_document_id=supersedes_document_id,
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
def extract_components(document_id: int, requested_backend: str | None = None) -> dict:
    """Extract structured component specifications from a stored datasheet/application_note
    and upsert a components row per part. Runs automatically, no confirmation step.
    SENSITIVE/RESTRICTED documents always use the self-hosted backend, no fallback to
    external."""
    return _extract_components(document_id=document_id, requested_backend=requested_backend)


if __name__ == "__main__":
    mcp.run()
