import os
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from agents import (
    Agent,
    AsyncOpenAI,
    Handoff,
    ModelSettings,
    Runner,
    RunResult,
    function_tool,
    handoff,
    set_default_openai_api,
    set_default_openai_client,
    set_tracing_disabled,
)
from agents.mcp import MCPServerManager, MCPServerStdio
from agents.models.default_models import get_default_model_settings
from dotenv import load_dotenv
from openai.types.shared import Reasoning

from designs.service import record_engineering_result as _record_engineering_result
from geometry.freecad_curved import run_freecad_curved_geometry as _run_freecad_curved_geometry
from knowledge.search import search_knowledge as _search_knowledge
from optimization.rf_objectives import (
    optimize_patch_length_for_target_frequency as _optimize_patch_length_for_target_frequency,
)
from orchestration.lab_test_plan import compile_lab_test_plan_for_loop as _compile_lab_test_plan
from orchestration.policy import assert_all_tools_categorized, category_for
from rf_tools.calculations import (
    abcd_to_s,
    aperture_gain,
    cascade_gain_db,
    cascade_output_ip3_linear,
    curvature_length_correction_factor,
    curvature_shifted_resonant_frequency_hz,
    db_to_linear,
    fractional_bandwidth_from_q,
    friis_noise_factor,
    iip3_from_oip3_db,
    input_stability_circle,
    l_network_match,
    linear_to_db,
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
from rf_tools.filter_synthesis import (
    realize_lowpass_stepped_impedance_microstrip,
    synthesize_filter,
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
    string for the "openai" (SDK default provider), "local", and "runpod"
    providers (the latter two routed via
    _configure_hosted_openai_compatible_backend's default client, below), or
    a `agents.extensions.models.litellm_model.LitellmModel` instance -- a
    `Model` object, not a string -- for any LiteLLM-routed provider like
    "anthropic". `Agent.model` accepts either (`str | Model`)."""
    provider = os.getenv("LLM_PROVIDER", "openai").lower()
    if provider in _LITELLM_PROVIDERS:
        from agents.extensions.models.litellm_model import LitellmModel

        prefix, model_env, model_default, key_env = _LITELLM_PROVIDERS[provider]
        return LitellmModel(
            model=f"{prefix}/{os.getenv(model_env) or model_default}",
            api_key=os.getenv(key_env),
        )
    if provider == "local":
        return os.getenv("LOCAL_AGENT_MODEL", "gpt-oss:20b")
    if provider == "runpod":
        model = os.getenv("RUNPOD_MODEL")
        if not model:
            raise RuntimeError(
                "LLM_PROVIDER=runpod requires RUNPOD_MODEL to be set to the exact "
                "model name your RunPod Serverless vLLM endpoint was deployed with "
                "-- there is no sensible default the way LOCAL_AGENT_MODEL has "
                "Ollama's, since a RunPod endpoint is deployed for one specific "
                "model at creation time."
            )
        return model
    return os.getenv("OPENAI_MODEL", "gpt-5.5")


def _resolve_agent_model_settings() -> ModelSettings:
    """Sampling/reasoning settings for `Agent(model_settings=...)`.

    Scoped to `LLM_PROVIDER=local` only (Ollama serving LOCAL_AGENT_MODEL) --
    the SDK's own `get_default_model_settings()` for every other provider,
    since this repo has no basis to second-guess OpenAI's/Anthropic's own
    recommended defaults, and a paid API's reasoning effort has direct cost
    implications nothing here asked to change. (Passing `model_settings=None`
    to `Agent(...)` is a TypeError, unlike simply omitting the argument --
    `Agent.model_settings`'s own default is `get_default_model_settings()`,
    not `None`, so returning that here for the non-local case reproduces
    exactly what omitting the kwarg would have done.)

    Values are Qwen3.8's own documented defaults for its "thinking" mode
    (the model's default mode): temperature=1.0, top_p=0.95, top_k=20,
    presence_penalty=0.0, reasoning_effort="xhigh" -- "xhigh" specifically,
    not "high": Qwen3.8 only supports xhigh/medium/low, and "xhigh" (not
    "high") is both its own default and the deepest level it offers, for
    the most thorough analysis on this repo's multi-step RF design-loop
    tool-calling. `top_k` has no native `ModelSettings` field (OpenAI's API
    doesn't expose one) -- passed via `extra_body["options"]`, the
    documented mechanism Ollama's OpenAI-compatible endpoint uses for
    llama.cpp-native sampling parameters that aren't part of the OpenAI
    wire format itself.
    """
    if os.getenv("LLM_PROVIDER", "openai").lower() != "local":
        return get_default_model_settings()
    return ModelSettings(
        temperature=1.0,
        top_p=0.95,
        presence_penalty=0.0,
        reasoning=Reasoning(effort="xhigh"),
        # num_ctx: Ollama serves a model at its OWN small default context
        # window (no num_ctx in `ollama show qwen3.8:27b --parameters`,
        # confirmed by reading it directly) regardless of what the model
        # itself supports (Qwen3.8 natively handles up to 262K, extendable
        # to 1M) -- a well-known Ollama gotcha, not a qwen3.8 limitation.
        # CRITICAL: this only takes effect on a FRESH model load -- Ollama
        # does NOT resize an already-loaded model's context per request
        # (confirmed empirically: `ollama ps` kept reporting CONTEXT=4096
        # after several requests with num_ctx=65536, until the model was
        # explicitly stopped/unloaded and reloaded -- only then did `ollama
        # ps` show CONTEXT=65536 for real). Any change to this value needs
        # `ollama stop qwen3.8:27b` (or waiting for its idle-unload) before
        # it takes effect, and every earlier round of diagnostic testing in
        # this repo's own history ran against a stale, wrong context size.
        # 8192 is sized for the CURRENT principal (20 tools, not the
        # original 86) -- generous headroom without the VRAM/CPU-offload
        # pressure a much larger window causes on a 16GB card (confirmed:
        # 65536 pushed this model from 69% GPU-resident to a 50/50 CPU/GPU
        # split). Re-check if the tool list grows substantially, or if a
        # specialist role's own reasoning needs more room than this leaves.
        extra_body={"options": {"top_k": 20, "num_ctx": 8192}},
    )


def _local_reasoning_output_tail() -> str:
    """Appended to every role's instructions only when LLM_PROVIDER=local.

    Explicit output-format steering for local reasoning-enabled models
    (Qwen3-family "thinking" mode): tell the model plainly that thinking is
    welcome and unbounded, but the VISIBLE answer must start directly with
    the final result -- no restated question, no reasoning preamble. This
    mirrors the exact prompt change that fixed empty/wrong outputs on the
    same class of model in prior work (reworded from "reason internally...
    output ONLY the final result" to "think step by step first, take as
    long as you need... then write your VISIBLE answer as ONLY the final
    result, start directly with the answer").

    Omitted for openai/anthropic/runpod, which have their own well-tuned
    default behavior this repo has no basis to second-guess.
    """
    if os.getenv("LLM_PROVIDER", "openai").lower() != "local":
        return ""
    return (
        "\n\n## Output format\n\n"
        "Think step by step first, internally, for as long as the problem "
        "actually needs -- do not rush a multi-step design or tool-selection "
        "decision. Then write your visible answer starting DIRECTLY with the "
        "final result: no restated question, no meta-commentary about your "
        "own reasoning process, no preamble."
    )


def _configure_hosted_openai_compatible_backend() -> None:
    """When LLM_PROVIDER is "local" or "runpod", point the SDK's default
    OpenAI-compatible client at that provider's endpoint instead of OpenAI's
    own API, so a plain model-name string from _resolve_agent_model resolves
    against it -- no per-Agent wiring needed. A no-op for every other
    provider ("openai", and any _LITELLM_PROVIDERS entry -- those route
    through LitellmModel instances instead and need no default-client
    override here).

    "runpod" is RunPod's Serverless vLLM endpoint (pay-per-second, scales to
    zero when idle): api.runpod.ai/v2/<endpoint_id>/openai/v1, genuinely
    OpenAI-wire-compatible so it needs no LiteLLM routing, just a different
    base_url/api_key than "local"'s Ollama default. Unlike "local", there is
    no sensible base_url default -- RUNPOD_ENDPOINT_ID and RUNPOD_API_KEY
    must both be set, or this fails loudly at import time rather than
    producing a confusing 401/404 on the first agent call.

    Per ADR-0004, this function only ever affects the AGENT's own reasoning
    (LLM_PROVIDER) -- the knowledge base's separate DEFAULT_LLM_BACKEND
    (local/external) gate for SENSITIVE/RESTRICTED documents is untouched by
    either branch here. "runpod" is a hosted cloud API from a data-egress
    standpoint, the same category as "openai"/"anthropic" -- it just also
    happens to be OpenAI-wire-compatible, which is why it's handled
    alongside "local" here rather than through _LITELLM_PROVIDERS.
    """
    provider = os.getenv("LLM_PROVIDER", "openai").lower()
    if provider == "local":
        base_url = os.getenv("LOCAL_LLM_BASE_URL") or "http://localhost:11434/v1"
        api_key = os.getenv("LOCAL_LLM_API_KEY") or "unused"
    elif provider == "runpod":
        endpoint_id = os.getenv("RUNPOD_ENDPOINT_ID")
        api_key = os.getenv("RUNPOD_API_KEY")
        if not endpoint_id or not api_key:
            raise RuntimeError(
                "LLM_PROVIDER=runpod requires both RUNPOD_ENDPOINT_ID and "
                "RUNPOD_API_KEY to be set -- see .env.example."
            )
        base_url = f"https://api.runpod.ai/v2/{endpoint_id}/openai/v1"
    else:
        return
    client = AsyncOpenAI(base_url=base_url, api_key=api_key)
    set_default_openai_client(client, use_for_tracing=False)
    # Self-hosted/self-served OpenAI-compatible servers (Ollama, llama.cpp,
    # LM Studio, RunPod's vLLM Serverless workers) implement the older
    # /v1/chat/completions surface, not OpenAI's newer /v1/responses API
    # this SDK defaults to.
    set_default_openai_api("chat_completions")
    # No real OPENAI_API_KEY exists in either mode, so trace uploads to
    # OpenAI's platform would only fail noisily -- turn tracing off rather
    # than let every run attempt and fail one.
    set_tracing_disabled(True)


_configure_hosted_openai_compatible_backend()


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


@function_tool
def realize_lowpass_stepped_impedance_microstrip_filter(
    response: str,
    order: int,
    eps_r: float,
    h_m: float,
    impedance_ohm: float = 50.0,
    ripple_db: float | None = None,
    cutoff_hz: float | None = None,
    z_high_ohm: float = 120.0,
    z_low_ohm: float = 20.0,
    first_element: str = "shunt",
) -> dict:
    """Synthesize a LOWPASS ladder (issue #143) and realize it as a stepped-
    impedance ("Hi-Z, Lo-Z") microstrip layout (issue #286): each series
    inductor becomes a short high-impedance line, each shunt capacitor a
    short low-impedance line (Pozar, "Microwave Engineering" sec. 8.6).
    response/order/impedance_ohm/ripple_db/cutoff_hz mean exactly what they
    mean in synthesize_filter_prototype (band is always "lowpass" here --
    the stepped-impedance method has no realization for highpass/bandpass/
    bandstop, see docs/adr/0031). eps_r and h_m describe the microstrip
    substrate (relative permittivity, thickness in metres); z_high_ohm/
    z_low_ohm are the highest/lowest characteristic impedance the target
    board can manufacture (default 120/20 ohm, Pozar's own example values).

    Returns the ideal ladder (as synthesize_filter_prototype does) plus a
    "sections" list, one microstrip line per branch, each with its
    characteristic impedance, width (m), length (m), electrical length
    (rad) and effective permittivity. Closed-form and textbook-sourced
    throughout -- no simulator involved, `provenance: CALCULATED`. Two
    approximations by construction: each section assumes an electrically
    short line (accuracy degrades gracefully, not sharply, as a section's
    electrical length grows past ~pi/4), and each width's effective
    permittivity is the quasi-static, non-dispersive value at cutoff_hz --
    no coupling or discontinuity reactance between adjacent sections.
    Cross-check a result that matters against a full-wave simulator
    (run_openems_simulation/run_hfss_simulation) or qucsator_rf's own
    dispersive MLIN model before fabrication."""
    network = synthesize_filter(
        response=response,
        band="lowpass",
        order=order,
        impedance_ohm=impedance_ohm,
        ripple_db=ripple_db,
        cutoff_hz=cutoff_hz,
        first_element=first_element,
    )
    sections = realize_lowpass_stepped_impedance_microstrip(
        network,
        eps_r=eps_r,
        h_m=h_m,
        z_high_ohm=z_high_ohm,
        z_low_ohm=z_low_ohm,
    )
    return {
        "network": network.to_dict(),
        "sections": [s.to_dict() for s in sections],
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
def calculate_curvature_length_correction_factor(l_m: float, radius_of_curvature_m: float) -> dict:
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
# dicts from whatever simulator/external-measurement output the caller has --
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
    measurement/external.py's record_external_measurement output
    (frequency_hz/s_parameters/z0), or one carrying a "touchstone_file"
    path -- see rf_tools/correlation.py's
    module docstring for exactly which of run_nec2_simulation's/
    run_openems_simulation's current outputs this can and cannot use yet
    (NEC2++'s single-frequency impedance is always honestly rejected, not
    fabricated from; openEMS's S-parameters are accepted via its
    "touchstone_file" output only for the single-port case with
    computed=True -- real port probe data was available -- and honestly
    rejected otherwise: when computed=False, and also for a multi-port
    computed=True run, which has no "touchstone_file" and whose
    "values"/"z0_ohms" shape doesn't match the generic "s_parameters"/"z0"
    shape this function accepts either). Temperature normalization is a
    documented no-op unless both inputs happen to carry
    a "temperature_c" field, since no current simulator/external-measurement
    source populates one -- see the returned temperature_note. Returns
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
    return _run_nec2_simulation(geometry=geometry, frequency_hz=frequency_hz, timeout_s=timeout_s)


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
    they fall back to an honestly-flagged computed=False when they aren't. Far-field/
    gain is REAL too (issue #269) when geometry includes an optional "nf2ff" key: a
    near-field-to-far-field recording box ("p1_m"/"p2_m" corners enclosing every
    radiating structure, plus optional "directions"/"name"/"frequencies_hz"/
    "radius_m"/"center_m"/"eps_r"/"mue_r"/theta-phi angle-grid overrides -- see
    simulation.openems.generate_openems_xml for the full shape). Requesting it also
    keeps this run's field/NF2FF dumps enabled automatically (the default
    --disable-dumps flag would otherwise suppress them). The result's "gain_dbi" is
    then a real number and "far_field" carries a real per-angle "pattern" table,
    structurally parallel to run_nec2_simulation's own "pattern"/"gain_dbi" keys --
    which is what lets the design loop's default SIMULATION-step scored field
    (gain_dbi) work the same way for either simulator. Without an "nf2ff" key, or if
    openEMS's separate nf2ff post-processing step doesn't produce a parseable result,
    "far_field" stays an honestly-flagged computed=False stub with an explanatory
    note -- never a fabricated number. Format verified against primary openEMS/CSXCAD
    documentation (see simulation/openems.py's module docstring for citations) but
    NOT against a real openEMS binary -- none is installed in this environment; treat
    any result as unverified end-to-end until it has been run against the real tool
    at least once."""
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
    simulation.hfss._apply_hfss_geometry for the full shape), either a single
    lumped port (geometry["port"]) or a periodic Floquet-port unit cell
    (geometry["periodic"], issue #273), and a length-based mesh, solve, extract
    S-parameters (per-mode reflection for the Floquet case), export a Touchstone
    file, and archive the solved project plus extracted report for later
    reproducibility.
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
# ports'/project's/materials' shapes (optional materials/nested path/boundary/mode
# lists) do not fit the SDK's strict-schema requirement.
def run_openparem_simulation(
    ports: dict,
    mesh_file: str | None = None,
    geometry: dict | None = None,
    project: dict | None = None,
    project_name: str = "openparem_project",
    materials: list[dict] | None = None,
    mpi_processes: int | None = None,
    timeout_s: int = 3600,
    gmsh_executable: str | None = None,
    gmsh_timeout_s: int = 600,
) -> dict:
    """Simulate a structure with OpenParEM3D (full-wave FEM): given EITHER an
    already-meshed Gmsh msh22 `mesh_file` OR a `geometry` dict (this repo's own
    primitive-dict shape -- issue #278; meshed internally via
    simulation.elmer.generate_gmsh_geo_script + simulation.openparem.
    run_openparem_gmsh_meshing, forcing OpenParEM3D's required msh22 format) and
    structured `ports` geometry (Path/Boundary/Port definitions -- see
    simulation.openparem.generate_openparem_ports_file for the full shape), generate
    the `.proj` project-control file (frequency plan, mesh/refinement settings,
    reference impedance, Touchstone format -- see simulation.openparem.
    generate_openparem_project_config for the full `project` shape) plus the ports
    file and (when `materials` is given, in place of a pre-existing materials
    library on disk -- see simulation.openparem.generate_openparem_materials_file/
    openparem_materials_from_property_entries for the input shapes) a materials
    file, run OpenParEM3D, and parse S-parameters AND antenna far-field gain/
    directivity/radiation-efficiency from the SAME FEM solve -- no separate tool or
    manual post-processing step. Set `project["far_field"] = {"quantity": "G"}` (or
    "D" for directivity) to request far-field metrics; this only actually computes
    when `ports["boundaries"]` includes a `type="radiation"` boundary. Returns
    "SIMULATED" provenance with `s_parameters`/`far_field` each honestly flagged
    computed=True/False (never fabricated) plus a `touchstone_file` key when a
    single-port renormalized Touchstone was written. `.proj`/ports-file/materials-file
    format and CLI invocation verified against OpenParEM's own primary GitHub source
    and its official Installation Manual/Users Manual PDFs (see simulation/
    openparem.py's module docstring for the full citation list) but NOT against a
    real OpenParEM3D (or gmsh) binary -- none is installed in this environment; treat
    any result as unverified end-to-end until it has been run against the real tools
    at least once. OpenParEM is also considerably younger and less battle-tested than
    NEC2++/openEMS/HFSS (initial release Sept. 2024) -- extra caution warranted."""
    return _run_openparem_simulation(
        mesh_file=mesh_file,
        geometry=geometry,
        ports=ports,
        project=project,
        project_name=project_name,
        materials=materials,
        mpi_processes=mpi_processes,
        timeout_s=timeout_s,
        gmsh_executable=gmsh_executable,
        gmsh_timeout_s=gmsh_timeout_s,
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
    unit cell) are NOT supported in this pass -- an explicitly-scoped gap, see
    simulation/palace.py's module docstring. This adapter HAS been run end to end
    against a real palace binary (issue #210): driving Palace's own "Floquet Ports for
    a Dielectric Grating" example through this exact function reproduced Palace's
    published S-parameters to within 0.056 dB and 0.91 degrees, and agreed on which
    diffraction orders propagate. That is one all-dielectric geometry at one incidence
    angle, and it is still a simulation agreeing with a simulation -- nothing here has
    been checked against a bench measurement. See docs/palace-floquet-validation.md."""
    return _run_palace_simulation(
        geometry=geometry,
        frequency_hz=frequency_hz,
        sweep=sweep,
        num_processes=num_processes,
        timeout_s=timeout_s,
        solver_order=solver_order,
    )


@function_tool(strict_mode=False)  # same rationale as run_nec2_simulation above --
# geometry's shape (domain/material/optional excitation) does not fit the SDK's
# strict-schema requirement.
def run_elmer_simulation(
    geometry: dict,
    frequency_hz: float,
    timeout_s: int = 1800,
    gmsh_executable: str | None = None,
    elmergrid_executable: str | None = None,
    elmersolver_executable: str | None = None,
) -> dict:
    """Simulate a structure with Elmer FEM's VectorHelmholtz module: a general,
    multiphysics-ready EM cross-check -- NOT a replacement for run_nec2_simulation/
    run_openems_simulation/run_hfss_simulation on everyday antenna work, since
    Elmer's primary user base is structural/CFD/heat-transfer, not EM. Generates a
    Gmsh OpenCASCADE .geo script from structured geometry (a single rectangular
    domain with isotropic material, plus an optional rectangular excitation
    sub-region -- see simulation.elmer.generate_gmsh_geo_script for the full shape),
    meshes it with gmsh, converts the mesh to ElmerSolver's native format with
    ElmerGrid, generates a matching VectorHelmholtz .sif (see simulation.elmer.
    generate_elmer_sif), runs it with ElmerSolver, and parses whatever raw output is
    available. Returns "SIMULATED" provenance. COUPLED EM+THERMAL (issue #281): pass
    an optional `geometry["thermal"]` block (`heat_conductivity_w_mk`,
    `density_kg_m3`, `heat_capacity_j_kgk`, plus optional `fixed_temperature_faces_k`/
    `convective_faces` boundary conditions -- see simulation.elmer.generate_elmer_sif
    for the full shape) to add a Heat Equation solve driven by the EM solve's own
    Joule-heating loss on the same mesh -- e.g. how hot a mounted "adaptive EM skin"
    gets from soaking up radio energy while sitting on a warm surface, in the same
    run as the EM-only result. The returned dict then also carries a `thermal_result`
    key (`computed=True` with `max_temperature_k`, or `computed=False` with an
    explanatory note -- same honest-gap pattern as `s_parameters`/`far_field`).
    Omitting `geometry["thermal"]` runs EM-only exactly as before. CRITICAL SCOPE
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
        geometry=geometry,
        frequency_hz=frequency_hz,
        timeout_s=timeout_s,
        gmsh_executable=gmsh_executable,
        elmergrid_executable=elmergrid_executable,
        elmersolver_executable=elmersolver_executable,
    )


@function_tool(strict_mode=False)  # same rationale as run_elmer_simulation above --
# `primitives`/`curvature`'s shape (box/polygon primitive dicts, curvature params)
# does not fit the SDK's strict-schema requirement.
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


@function_tool(strict_mode=False)  # same rationale as run_nec2_simulation above --
# job's shape (optional keys, variable-length components/ports/raw_cards lists)
# doesn't fit the SDK's strict-schema requirement -- see
# simulation.ltspice.generate_ltspice_net_netlist for the accepted shape.
def run_ltspice_simulation(
    netlist: str | None = None,
    netlist_file: str | None = None,
    job: dict | None = None,
    timeout_s: int = 600,
) -> dict:
    """Simulate a circuit with LTspice (ADS alternative, part 3 of 3 -- issue
    #59): run a SPICE netlist through LTspice's real batch-mode CLI (driven
    via the spicelib package, not hand-rolled -- see simulation/ltspice.py's
    module docstring for the primary-source citation), and parse the
    resulting .raw output into structured trace data (plot type, axis, and
    every named trace, complex for an AC analysis or real for a transient/DC
    sweep) via spicelib's own RawRead. Takes EXACTLY ONE of `netlist` (raw
    netlist text -- e.g. exported from LTspice's own File > Export Netlist),
    `netlist_file` (a path to an existing .net/.cir/.asc file already on
    disk), or `job` (a structured two-port job dict -- R/L/C/V/I components,
    a driven-port/loaded-port pair under "ports", and an "ac"-type
    "analysis" -- templated into LTspice's native `.net` two-port S-/Y-/Z-/
    H-parameter extraction statement by generate_ltspice_net_netlist(),
    issue #287; see that function's docstring for the exact shape). When
    `job` is given, the returned dict also carries "network_parameters"
    (whichever S11/S21/S12/S22/Zin/Zout/etc. traces `.net` produced, via
    extract_ltspice_network_parameters()). Returns "SIMULATED" provenance.
    LOWEST PRIORITY / LOWEST INVESTMENT of this batch's "ADS alternative"
    simulators: LTspice is the one non-open-source item here (free-of-
    charge proprietary Analog Devices freeware, NOT OSI-approved -- see
    docs/LICENSE_MATRIX.md) and is capability-redundant with any
    ngspice/Xyce/Qucs-S adapter this repo may also have -- `job`'s S/Y/Z/H-
    parameter extraction duplicates what run_xyce_simulation's native `.LIN`
    path already provides; it matters only when a design specifically needs
    LTspice's own bundled device-model library, not new simulation
    capability. Outside the `job` case, this tool does NOT generate a
    netlist from an arbitrary structured component-description dict -- a
    SPICE netlist is already the natural structured/text format for a
    circuit, so bring your own. spicelib itself is an OPTIONAL install
    (`pip install '.[ltspice]'` / `uv sync --extra ltspice`) -- this tool
    raises a clear, actionable SimulatorError (not a bare ImportError) if it
    isn't installed. Format/invocation verified against spicelib's own
    primary GitHub source (see simulation/ltspice.py's module docstring for
    the full citation) but NOT against a real LTspice binary -- none is
    installed in this environment; treat any result as unverified
    end-to-end until it has been run against the real tool at least once."""
    return _run_ltspice_simulation(
        netlist=netlist, netlist_file=netlist_file, job=job, timeout_s=timeout_s
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
    port-discovery convention, not something this tool can synthesize.

    Runs KiCad's own Design Rule Check (`kicad-cli pcb drc`) FIRST, before export
    or simulation (issue #272) -- the result's "drc" key carries the violation
    count/detail, and "warnings" carries a human-readable note if any were found.
    Per CLAUDE.md's "warn, never block", a board with DRC violations still gets
    exported and simulated; nothing here withholds a result over it.

    Format/API verified against gerber2ems's, kicad-python's, and kicad-cli's own
    primary sources (see simulation/kicad_gerber2ems.py's module docstring and
    run_kicad_drc's own docstring for the full citation list) but NOT against a
    real KiCad/kicad-cli/gerbv/gerber2ems/openEMS installation -- none is installed
    in this environment; treat any result as unverified end-to-end until it has
    been run against the real tools at least once. One honestly-flagged gap beyond
    that: kicad-python's drill export does not yet expose a plated/non-plated-hole
    split, so a board with unplated holes may get a mis-labeled drill file (see
    that module's own docstring and each result's own `warnings`)."""
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
    op/ac/tran/noise/disto/pz/sens "analysis", and "outputs" -- see
    simulation.ngspice.generate_ngspice_netlist for the full per-analysis-type
    shape), run it via ngspice, and parse the results back out: AC/DISTO (real/imag
    pairs vs. frequency), TRAN/OP/NOISE (real values vs. time or frequency), or
    PZ/SENS (a small unswept set of poles/zeros or per-parameter sensitivities,
    with no frequency/time axis at all -- "scale"/"scale_name" are None for these
    two). Use NOISE for amplifier/LNA noise-figure work, DISTO or TRAN for
    nonlinearity (harmonic distortion / large-signal compression), and PZ/SENS for
    stability (pole locations) or design-parameter sensitivity. Returns "SIMULATED"
    provenance. IMPORTANT SCOPE LIMIT: S-parameters and `.TF` (transfer function)
    are NOT computed here -- stable ngspice has no built-in S-parameter analysis and
    this adapter does not yet wire up `.TF`; use run_xyce_simulation's native `.LIN`
    S-parameter/Touchstone path for that need instead (see simulation/ngspice.py's
    module docstring for why). Netlist/output format verified against the primary
    ngspice manual (see simulation/ngspice.py's module docstring for the citation)
    but NOT against a real ngspice binary for noise/disto/pz/sens -- none is
    installed in this environment (the `.AC` path alone was verified against a real
    binary; see that same module docstring); treat any result as unverified
    end-to-end until it has been run against the real tool at least once."""
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
    devices/subcircuits, an op/ac/tran/hb "analysis" (hb = Harmonic Balance, Xyce's
    periodic large-signal steady-state analysis for a driven mixer or nonlinear
    amplifier/unit cell -- see simulation/xyce.py's module docstring), optional
    node-voltage/branch-current "outputs", and optional "ports" -- see
    simulation.xyce.generate_xyce_netlist for the full shape), run it via Xyce,
    and return the requested `.PRINT` outputs
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
    MODEL caveat), and returns "SIMULATED" provenance. IMPORTANT SCOPE LIMITS: POWER
    quantities only -- power reflectance and its magnitude |S11| are always computed
    (via MEEP's own documented flux-subtraction technique), and power TRANSMITTANCE
    (how much of the arriving power goes straight through and out the far side) is
    computed too IF you ask for it by putting a "transmission_monitor_center_m" plane
    in `geometry`; without it no transmission monitor is built and the result says
    "not requested" rather than a misleading zero. NO complex phase, so no complex
    S21 and no multi-port S-matrix, and NO Touchstone export (see simulation/meep.py's
    module docstring SCOPE section) -- so only |S11| magnitude, not phase, can be
    cross-checked against run_openems_simulation's complex S11. Antenna gain/
    radiation pattern (`gain_dbi`, `far_field`) is ALSO opt-in, via MEEP's own
    documented near-to-far-field transform (#270): put a "far_field_monitor" dict
    in `geometry` (an "enclosing_regions" closed box plus "directions" far-field
    points -- see simulation.meep.run_meep_simulation's own docstring for the full
    shape) and `gain_dbi` carries a real dBi figure instead of None; leave it out
    and both stay exactly as they were (far_field computed=False, gain_dbi=None),
    at no extra solver cost. That gain figure is a peak among only the directions
    YOU named, not a full-sphere scan, and its absolute scale rests on a reasoned-
    but-not-yet-pymeep-verified assumption (see simulation/meep.py's
    FAR_FIELD_VALIDITY) -- newer and less battle-tested than the reflectance/
    transmittance recipe below. This tool does NOT compute absorption: 1 - R - T
    is a reading of two measurements, not a measurement. `characteristic_length_m`
    is MEEP's own dimensionless-unit lengthscale "a" (default 1mm, reasonable for patch-antenna-
    scale geometry); geometry/units translation verified against MEEP's own primary
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


@function_tool(strict_mode=False)  # `state` is a free-form dict (the loop's
# own session-token shape) -- same rationale as run_nec2_simulation's
# geometry parameter above.
def compile_lab_test_plan(state: dict) -> dict:
    """Compile a batched lab-test plan (issue #94) for every requirement on
    this design: what to measure, by what method, and what value this
    iteration's own recorded CALCULATED/SIMULATED engineering results
    already predict -- so one lab trip is enough, instead of the engineer
    discovering mid-trip that a requirement can't be confirmed with what
    they brought. A requirement with no proposed target, an explicitly
    UNSCOREABLE one, one whose quantity a Touchstone S-parameter sweep
    cannot report (e.g. antenna gain or radiation pattern -- needs a range/
    chamber, not a bench VNA), or one with nothing computed this iteration
    to predict from is flagged with a distinguishing reason, not silently
    dropped -- see orchestration/lab_test_plan.py's own docstring for the
    full design.

    `state` is a state dict from start_design_loop/advance_design_loop_step/
    inspect_design_loop_state -- safe to call at any point in the loop, on
    any current_step. Read-only: advances nothing, writes nothing to the
    database, and needs no approval receipt (there is nothing here for
    orchestration.approval.check_loop_step_approval_gate to check)."""
    return _compile_lab_test_plan(state)


# ---------------------------------------------------------------------------
# WHY THIS FILE STILL HOLDS TOOLS AT ALL, AND ONLY THESE: every tool this
# file wraps is also registered, independently, in `mcp_server/server.py`
# (ADR-0032's single-registration destination). The duplicates that survive
# here are the ones microwave/antenna/test still need as `FunctionTool`s,
# because those three roles shell out to external solvers and every such tool
# hangs indefinitely over the MCP stdio transport on native Windows (see
# `tests/test_mcp_tool_call_parity.py`'s module docstring). principal,
# systems and verification hold no such tool and run entirely over
# `agent/mcp_roles.py`'s MCP-routed construction, so their wrappers are gone
# and `agent/mcp_roles.py` owns their tool-name lists outright -- a role
# whose `RoleSpec.tools` is empty below is migrated, not broken.
#
# A tool shared between a migrated role and one of the three still on the old
# path (search_knowledge, compile_lab_test_plan, the cascade/IP3 family) keeps
# its wrapper here for the old-path role's sake, and is served to the migrated
# role over MCP like everything else -- the two surfaces are not a fallback
# pair, they are two callers of the same underlying function.
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
    synthesize_filter_prototype,
    realize_lowpass_stepped_impedance_microstrip_filter,
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
    search_knowledge,
    optimize_patch_length_for_target_frequency,
    compile_lab_test_plan,
]

assert_all_tools_categorized([tool.name for tool in _ALL_TOOLS])


@dataclass(frozen=True)
class RoleSpec:
    """One specialist role: its display name, tool subset, and the domain
    note appended to the shared system prompt explaining that scope.

    `tools` is empty for a role whose tool-name list `agent/mcp_roles.py`
    owns instead (principal, systems, verification). Their `display_name`/
    `domain_note` stay here because `agent.mcp_roles.build_role_agent` reads
    them for every role, migrated or not -- only the tool data moved.
    """

    key: str
    display_name: str
    domain_note: str
    tools: list = field(default_factory=list)


ROLE_SPECS: list[RoleSpec] = [
    RoleSpec(
        key="principal",
        display_name="Principal RF Engineer",
        domain_note=(
            "You are the coordinating principal-level reviewer. You do NOT hold "
            "the specialist calculation/simulation tools directly -- hand off "
            "to the relevant `route_to_<role>_role` specialist (systems, "
            "microwave, antenna, test, verification) for any RF calculation, "
            "simulation, or domain-specific analysis; that specialist has the "
            "tool you need, and takes over the conversation to answer "
            "directly once you hand off. This is deliberate, not a gap: "
            "giving one agent dozens of granular tools at once measurably "
            "degrades tool-selection reliability (see this repo's own "
            "testing history) -- routing keeps each agent's toolset small "
            "and its choices reliable. "
            "You directly hold: the design-record tools (create_design/"
            "read_design/record_decision/verify_requirement/"
            "advance_design_status/propose_requirement_target/"
            "mark_requirement_unscoreable/confirm_requirement_target), "
            "search_knowledge, search_design_records, and the controlled "
            "design-iteration loop tools "
            "(start_design_loop/advance_design_loop_step/"
            "inspect_design_loop_state, issue #46) -- walking a design through "
            "requirements/architecture/analysis/simulation/optimization/"
            "verification/measurement/correlation/redesign is a cross-cutting "
            "orchestration concern spanning every specialist's domain, not any "
            "one specialist's own scope. Advancing past an architecture "
            "decision, physical measurement, or a redesign/iteration decision "
            "always requires a distinct human-approval receipt first -- this "
            "loop never reaches, and has no path to, an autonomous "
            "manufacturing-release action. compile_lab_test_plan (issue #94), "
            "by contrast, is read-only (no mutation, no approval needed) and "
            "is shared with the test role, which owns lab-test-plan work day "
            "to day. You alone also hold "
            "run_candidate_search (issue #95): once a design is inside an "
            "approved architecture, drive a batch of candidate parameter sets "
            "through ANALYSIS/SIMULATION/OPTIMIZATION and score each -- the "
            "same ungated span advance_design_loop_step already lets you walk "
            "by hand, just run in software, candidate after candidate, until "
            "a target is met, scores plateau, or the evaluation budget runs "
            "out; it halts and reports rather than proceeding the instant it "
            "would reach a gated step. You alone also hold "
            "search_literature_for_capability_warning (issue #327, ADR-0033): "
            "given one of the loop's own capability_warnings entries whose "
            "capability_kind is 'material' or 'ink', plus the actual material/ink "
            "product name from the design's own context (the entry's own 'family' "
            "names the design family it's attached to, not a material/ink name), "
            "search this project's knowledge base then arXiv for a citable "
            "measured value -- candidates only, never a settled number, and it "
            "never writes a library entry itself; a human still confirms and adds "
            "one."
        ),
    ),
    RoleSpec(
        key="systems",
        display_name="Systems RF Engineer",
        domain_note=(
            "You focus on link-level and systems-engineering concerns: cascaded "
            "gain/noise-figure budgets, wavelength/electrical-size bookkeeping, "
            "and standing up the knowledge base (ingesting and indexing "
            "documents, sourcing component datasheets directly from Digi-Key/"
            "Mouser/Nexar, querying Nexar's cross-distributor pricing/"
            "availability and parametric specs via lookup_nexar_part_data to "
            "screen a candidate component against a requirement before "
            "committing to it, fetching/converting arXiv preprints via "
            "ingest_arxiv_paper, searching arXiv by topic/keyword via "
            "search_arxiv_papers before proposing a new element or mechanism "
            "-- 'search precedent before inventing' -- fetching 3GPP specs/"
            "ETSI standards/FCC eCFR rule text via ingest_3gpp_spec/"
            "ingest_etsi_standard/ingest_fcc_rule (check a 3GPP spec's "
            "current DynaReport withdrawn/current status via "
            "lookup_3gpp_spec_status first, so a withdrawn spec doesn't "
            "get ingested as if it were current), surfacing ETSI's "
            "IPR/(F)RAND-declaration register against a standard already "
            "ingested via ingest_etsi_ipr_declaration, searching FCC eCFR "
            "rule text by topic/keyword via search_fcc_rules before you "
            "already know which part covers it, fetching US "
            "patents and published patent applications from the USPTO via "
            "ingest_patent, or searching the USPTO Open Data Portal by topic "
            "via search_uspto_patents first (issue #280) -- same 'search "
            "precedent before inventing' discipline as arXiv, credentialed "
            "this time -- and (issue #326) resolving an unresolved ink-"
            "related Capability warning via search_ink_product -- searching "
            "Digi-Key/Mouser for a real, purchasable product citation, "
            "never a settled property value) other roles rely on. Defer "
            "network-level "
            "S-parameter detail to the microwave role and document auditing to "
            "the verification role."
        ),
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
            "at all). run_ngspice_simulation additionally covers (issue "
            "#283) `.NOISE` (amplifier/LNA noise figure -- the LNA-"
            "noise-and-distortion reasoning this role exists for), `.DISTO` "
            "(harmonic distortion), `.PZ` (pole-zero stability), and "
            "`.SENS` (DC/AC parameter sensitivity) analyses, alongside its "
            "existing OP/AC/TRAN support. Also gets filter synthesis: "
            "synthesize_filter_prototype (issue #143) turns a Butterworth/"
            "Chebyshev lowpass/highpass/bandpass/bandstop specification "
            "into an ideal lumped-element ladder (henries/farads), and "
            "(issue #286) realize_lowpass_stepped_impedance_microstrip_filter "
            "carries a LOWPASS ladder one step further into a physical "
            "stepped-impedance ('Hi-Z, Lo-Z') microstrip layout -- narrow "
            "high-impedance lines standing in for series inductors, wide "
            "low-impedance lines for shunt capacitors (Pozar sec. 8.6); "
            "highpass/bandpass/bandstop physical realization is still open "
            "(see docs/adr/0031). Defer system-chain-level gain/link "
            "budgeting to the systems role."
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
            synthesize_filter_prototype,
            realize_lowpass_stepped_impedance_microstrip_filter,
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
            "ready EM cross-check -- NOT a substitute for the three tools "
            "above on everyday antenna work, since Elmer's VectorHelmholtz "
            "module has no native antenna-specific port/S-parameter/far-"
            "field/gain post-processing (its excitation and boundary "
            "conditions are hand-assembled, see simulation/elmer.py); it "
            "also now supports a coupled EM+thermal run mode (issue #281 "
            "-- pass geometry['thermal'] to add a Heat Equation solve "
            "driven by the EM solve's own Joule heating, e.g. how hot a "
            "mounted 'adaptive EM skin' gets from soaking up radio energy "
            "on a warm surface; the result's 'thermal_result' key carries "
            "the outcome), "
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
            "solver alone -- power quantities only: reflectance/|S11| "
            "magnitude always, power transmittance on request (name a "
            "'transmission_monitor_center_m' plane in the geometry, for a "
            "surface with free space behind it), never phase and so never "
            "a complex S21 (see simulation/meep.py). Also gets "
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
            "from the same solve. MEASURED-provenance data enters this "
            "system only from outside it (a Touchstone file from an "
            "external test bench, ingested through the design loop's "
            "measurement step -- see measurement/external.py and ADR-0013); "
            "this project does not actuate physical lab instruments itself "
            "(README.md, docs/SECURITY.md). Before a prototype leaves for "
            "the bench, use compile_lab_test_plan (issue #94) to compile a "
            "single batched plan covering every requirement on the design: "
            "what to measure, by what method, and what value this "
            "iteration's own recorded CALCULATED/SIMULATED results already "
            "predict, plus which requirements can't be verified with what's "
            "on hand (no target, an unscoreable one, a quantity a "
            "Touchstone sweep can't report, or nothing computed yet) and "
            "why -- so one trip is enough. Read-only: it advances nothing "
            "and needs no approval. You do not ingest or extract "
            "documents -- that is the systems/verification roles' job."
        ),
        tools=[
            analyze_touchstone_file,
            interpolate_touchstone_file,
            deembed_touchstone_file,
            cascade_touchstone_files,
            compare_touchstone_files,
            correlate_simulated_and_measured,
            compile_lab_test_plan,
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
    ),
]

_SPEC_BY_KEY: dict[str, RoleSpec] = {spec.key: spec for spec in ROLE_SPECS}
_SPECIALIST_KEYS = [key for key in _SPEC_BY_KEY if key != "principal"]

# Build the five specialist agents first (systems, microwave, antenna, test,
# verification). None of them delegate further -- only the principal role
# gets delegation tools, below -- so this is a plain, non-circular build.
#
# systems and verification come out of this with no tools, and the principal
# below with none either: `run()` reaches all three through
# `agent.mcp_roles.build_role_agent`, never through these objects. They stay
# as the constructible registry the test suite and any remaining importer
# expect. Wiring one of them into a live run would give that role an agent
# with nothing to call -- reach for `build_role_agent(key)` instead.
ROLES: dict[str, Agent] = {
    key: Agent(
        name=_SPEC_BY_KEY[key].display_name,
        model=_resolve_agent_model(),
        model_settings=_resolve_agent_model_settings(),
        instructions=(
            f"{SYSTEM_PROMPT}\n\n## Role scope\n\n{_SPEC_BY_KEY[key].domain_note}"
            f"{_local_reasoning_output_tail()}"
        ),
        tools=list(_SPEC_BY_KEY[key].tools),
    )
    for key in _SPECIALIST_KEYS
}

# ---------------------------------------------------------------------------
# Principal routing to specialists (issue #35, redesigned).
#
# `openai-agents` (>=0.17.4) offers two distinct mechanisms for one agent to
# involve another:
#
#   - `Agent(handoffs=[...])`: one-way control transfer, sequential. The
#     model emits a plain structured (JSON) tool call to trigger it; the
#     target agent then takes over the *whole* conversation and its
#     response becomes the run's final output. The original agent never
#     regains control within that same Runner.run() call.
#   - `Agent.as_tool(...)`: wraps an agent as a `FunctionTool`. The nested
#     agent runs via its OWN internal `Runner.run()` call, and that
#     nested run's nested request is what a delegating call constructs.
#
# This repo used `.as_tool()` first (see this section's git history for the
# original citation-synthesis design it was built around). It was replaced
# after live testing against a real local model (qwen3.8:27b via Ollama)
# reproduced a real, repeatable failure specific to the nested shape:
# `openai.InternalServerError: 500 - "no user query found in messages"` on
# the nested Runner.run() call `.as_tool()` constructs internally --
# confirmed NOT caused by context size or tool count (reproduced on a
# freshly-loaded model at a correctly-sized context, with only the 20-tool
# reduced principal toolset in play). `handoffs=[...]` does not construct a
# second nested completion request the way `.as_tool()` does -- the target
# agent continues within the SAME Runner.run() call -- so it does not hit
# this failure mode.
#
# The real, deliberate behavior change this brings: the principal now
# ROUTES a question to the one specialist whose domain it matches, and that
# specialist's own answer becomes the final output directly -- there is no
# more principal-side synthesis/citation-tagging step combining multiple
# specialists' contributions into one answer (the old `.as_tool()` design's
# `custom_output_extractor` citation-tag mechanism and the "keeps composing,
# cites which specialist role(s) contributed which part" framing are gone
# with it). A genuinely multi-domain question is handled by the first
# specialist it's routed to, using its own judgment about what it can
# answer -- this repo does not currently have a way to chain a second
# handoff after the first without giving specialists handoffs of their own
# (deliberately not done here, to avoid delegation cycles and keep each
# specialist's own tool-selection reliability intact).
# ---------------------------------------------------------------------------

# Short, third-person, routing-only summaries -- deliberately NOT the same
# text as each specialist's `domain_note` above. `domain_note` is written as
# second-person internal instructions for that specialist's own ~20-26-tool
# selection (right down to individual issue numbers and per-simulator
# caveats) and ranges from ~400 characters (verification) to 2,500+
# characters (antenna) -- reused verbatim as a handoff's tool description,
# that produces five wildly uneven, pronoun-switching ("it takes over...
# You focus on...") tool schemas for the PRINCIPAL to choose between, not
# five parallel routing options. Live testing against qwen3.8:27b showed the
# principal reliably recognizing only `route_to_verification_role` -- the
# shortest, simplest description of the five -- and silently failing to see
# the other four. These summaries fix that by being short, third-person, and
# uniformly shaped (what it's for, then what it defers) across all five, so
# no one handoff's schema dwarfs or grammatically confuses the others.
_ROUTING_SUMMARY: dict[str, str] = {
    "systems": (
        "Link-level and systems-engineering work: cascaded gain/noise-figure "
        "budgets, IP3/IM3 linearity, wavelength/electrical-size bookkeeping, "
        "and knowledge-base ingestion/indexing plus datasheet sourcing "
        "(Digi-Key/Mouser/Nexar). Not for network-level S-parameter detail "
        "(microwave) or document auditing (verification)."
    ),
    "microwave": (
        "Passive/active RF component and network analysis: VSWR/return "
        "loss, noise figure, Touchstone S/Z/Y/ABCD conversions, stability "
        "(K-factor, stability circles), impedance-matching and filter-"
        "prototype synthesis, IP3/IM3 linearity, and circuit-level "
        "simulation (Qucs-S, LTspice, ngspice, Xyce) for a matching "
        "network, filter, or amplifier. Not for system-chain gain/link "
        "budgeting (systems)."
    ),
    "antenna": (
        "Antenna-specific electrical size, input match, and synthesis "
        "(patch dimensions, bandwidth/Q, curvature, metamaterial "
        "permeability, aperture gain), full-wave antenna simulation "
        "(NEC2++, openEMS, gprMax, HFSS, OpenParEM3D, Elmer, Palace, MEEP), "
        "real-KiCad-PCB trace/via signal-integrity simulation (gerber2ems -- "
        "not far-field/gain), and curved/conformal geometry generation. Not "
        "for receiver-chain gain/noise figure (systems) or S/Z/Y/ABCD/"
        "stability/matching (microwave)."
    ),
    "test": (
        "Verification and measurement: Touchstone interpolation/"
        "de-embedding/cascading, comparing measured vs. predicted/"
        "simulated results across every simulator this repo has, and "
        "compiling a pre-bench lab test plan. Not for ingesting or "
        "extracting documents (systems/verification)."
    ),
    "verification": (
        "Knowledge and provenance auditing: reading a stored document's "
        "full metadata/chunks, extracting and auditing structured "
        "component specs with per-field provenance, and looking up prior "
        "design/decision records for precedent. Does not run RF "
        "calculations or add new documents."
    ),
}


def _build_role_handoff(key: str, target_agent: Agent) -> Handoff:
    return handoff(
        target_agent,
        tool_name_override=f"route_to_{key}_role",
        tool_description_override=(
            f"Hand this question off to the {_SPEC_BY_KEY[key].display_name} "
            f"specialist -- it takes over and answers directly. "
            f"{_ROUTING_SUMMARY[key]}"
        ),
    )


SPECIALIST_HANDOFFS: dict[str, Handoff] = {
    key: _build_role_handoff(key, ROLES[key]) for key in _SPECIALIST_KEYS
}

_PRINCIPAL_ROUTING_INSTRUCTIONS = (
    "\n\n## Routing to a specialist\n\n"
    "For ANY RF calculation, simulation, or domain-specific analysis, "
    "hand the question off to the one specialist role whose domain it "
    "matches (systems, microwave, antenna, test, verification) -- you "
    "do not hold those tools directly, and that specialist will answer "
    "directly once you hand off. Only use your own direct tools "
    "(design-record management, the design-iteration loop, or "
    "knowledge search) for what's actually your own job: tracking a "
    "design's state, not computing RF values yourself. Never label a "
    "value you reasoned out yourself CALCULATED -- that label means a "
    "calculation tool actually computed it. If you (or the specialist "
    "you hand off to) work a number out by reasoning instead of calling "
    "a calculation tool, label it INFERRED or ASSUMED instead."
)

_principal_spec = _SPEC_BY_KEY["principal"]
ROLES["principal"] = Agent(
    name=_principal_spec.display_name,
    model=_resolve_agent_model(),
    model_settings=_resolve_agent_model_settings(),
    instructions=(
        f"{SYSTEM_PROMPT}\n\n## Role scope\n\n{_principal_spec.domain_note}"
        f"{_PRINCIPAL_ROUTING_INSTRUCTIONS}"
        f"{_local_reasoning_output_tail()}"
    ),
    handoffs=list(SPECIALIST_HANDOFFS.values()),
)

# Kept as a module-level name for backward compatibility. This is NOT the
# Agent `run()` drives -- that one is built by `_build_live_principal` below.
principal = ROLES["principal"]


# ---------------------------------------------------------------------------
# Issue #158: provenance-integrity guard.
#
# Live-testing against a real local Ollama backend reproduced a failure
# mode distinct from the routing-recall bug this branch's rebase target
# (#165) fixed: on some draws, a role skips every calculation tool AND
# every route_to_<role>_role handoff, answers a squarely tool-shaped
# question from its own reasoning instead -- then labels that hand-computed
# number CALCULATED anyway. CONTEXT.md's Provenance entry and
# prompts/principal_engineer.md's "Mandatory provenance" section both
# define CALCULATED as "deterministic calculation" specifically -- the kind
# "Numerical discipline" says to get from a tool "instead of mental
# arithmetic". A reader has no way to tell a mislabeled hand-computed value
# apart from a genuinely tool-verified one, so this is a provenance-
# integrity violation, not a wording nuance.
#
# WHERE THIS IS WIRED, AND WHY ONLY HERE: the prior version of this fix
# (see git history on this branch) also hooked `Agent.as_tool()`'s
# `custom_output_extractor` to guard each specialist's nested result before
# it reached the principal. That mechanism is gone -- issue #165's routing
# redesign (this section's own "Principal routing to specialists" comment
# above) replaced `.as_tool()` with `Agent(handoffs=[...])`, which transfers
# control to the specialist WITHIN THE SAME `Runner.run()` call instead of
# starting a second, nested one. Concretely verified (not assumed) against
# this repo's actual installed `openai-agents` version: a scripted fake
# model driven through a real `Runner.run()` call -- one turn emitting a
# handoff tool call, the next (now running as the handed-off-to agent)
# emitting a real function-tool call, a final turn emitting the answer --
# shows the specialist's own post-handoff `tool_call_item` lands in the
# SAME top-level `RunResult.new_items` list `run()` below already inspects.
# There is no second `RunResult` for a specialist's answer to hide a
# mislabeled claim inside of anymore, and no `custom_output_extractor`
# hook left to attach a second guard to even if there were -- one guard
# here, on the run's own top-level result, now covers the principal's own
# answer AND every specialist's handed-off answer.
#
# `_assert_calculated_provenance_is_tool_backed` is the "cheap runtime
# guard" the issue's own suggested next steps floated: a CALCULATED claim
# in `final_output` with no matching tool call anywhere in that run's
# `new_items` gets rejected -- fail closed, the same idiom
# orchestration/policy.py's PolicyError already establishes for a policy
# violation, rather than silently letting a mislabeled claim reach the
# user. A HandoffCallItem does not count: handing control to another agent
# is not itself a deterministic calculation.
#
# NARROWER THAN "any tool call at all" (a real gap a reviewer of this
# branch's prior version found before it merged): a run can legitimately
# call an unrelated tool -- search_knowledge, read_document -- and
# separately hand-compute and mislabel an unrelated RF value in the same
# final_output. A bare "does new_items contain *a* tool_call_item"
# check passes that run, exactly the mislabeling issue #158 reports,
# right past the guard meant to catch it. So this checks that the tool
# call is specifically categorized `calculation` in
# policies/tool_policy.yaml (orchestration/policy.py's `category_for`,
# the same lookup `enforce()` already uses for its own gating) -- the
# category that file's own comment defines as "Deterministic,
# CALCULATED-provenance functions". A tool_call_item for search_knowledge
# or read_document does not satisfy this; one for calculate_cascade_gain
# (or any other calculation-category tool) does.
#
# Deliberately a plain substring check on `final_output`, not a structured
# parse -- "cheap" per the issue's own framing, and this repo's own
# provenance labels are always the bare uppercase token from the closed set
# in CONTEXT.md's Provenance entry. This can false-positive on a
# CALCULATED-that-isn't-a-label mention in running prose; a real structured
# provenance parse would be the fuller fix, not attempted here.
# ---------------------------------------------------------------------------


class ProvenanceIntegrityError(RuntimeError):
    """Raised when a run's `final_output` labels a result CALCULATED with no
    calculation-category tool call anywhere in that run's `new_items` to
    back it -- see issue #158. `_assert_calculated_provenance_is_tool_backed`
    raises this; nothing here rewrites the label instead, since silently
    "fixing" a claim nobody actually reviewed would just trade one
    unverifiable label for another."""


def _run_result_has_calculation_tool_call(result: RunResult) -> bool:
    """True if `result.new_items` contains at least one real `tool_call_item`
    whose tool is categorized `calculation` in `policies/tool_policy.yaml` --
    the only kind of item that can back a CALCULATED provenance label. A
    `handoff_call_item` alone does not count (handing control to another
    agent is not itself a deterministic calculation), and neither does a
    `tool_call_item` for a tool outside the `calculation` category (e.g.
    search_knowledge) -- see this section's module-level comment above for
    the concrete mislabeling that gap would otherwise miss."""
    return any(
        getattr(item, "type", None) == "tool_call_item"
        and category_for(getattr(item, "tool_name", None)) == "calculation"
        for item in result.new_items
    )


def _assert_calculated_provenance_is_tool_backed(result: RunResult) -> None:
    """Raise `ProvenanceIntegrityError` if `result.final_output` claims
    CALCULATED provenance but this run never actually called a
    calculation-category tool -- see issue #158 and this section's
    module-level comment above. Does nothing for any other provenance label
    (INFERRED/ASSUMED/etc. never claimed a tool verified them, so there is
    nothing to enforce) and does nothing when a CALCULATED claim genuinely
    is tool-backed.
    """
    if "CALCULATED" in result.final_output and not _run_result_has_calculation_tool_call(result):
        raise ProvenanceIntegrityError(
            "final_output labels a result CALCULATED, but no calculation-"
            "category tool_call_item (policies/tool_policy.yaml) appears "
            "anywhere in this run's new_items -- the number came from the "
            "model's own reasoning (or from an unrelated tool call), not a "
            "deterministic calculation tool. Relabel as INFERRED or "
            "ASSUMED (or call the calculation tool / route to the "
            "specialist role that would actually compute it) instead of "
            "reporting it as CALCULATED. See issue #158 and "
            "prompts/principal_engineer.md's Mandatory provenance section."
        )


_LIVE_MCP_ROLE_KEYS = ("systems", "verification", "principal")


def _build_live_principal(servers: dict[str, MCPServerStdio]) -> Agent:
    """Build `run()`'s principal from already-connected per-role MCP servers.

    `agent.mcp_roles` is imported here rather than at module level because it
    imports several names from this module at ITS own module level -- a
    module-level import either way round is a circular import that breaks
    depending on which of the two a caller reaches first.
    """
    from agent.mcp_roles import build_role_agent

    mixed_handoffs: list[Agent | Handoff] = [
        _build_role_handoff("systems", build_role_agent("systems", mcp_server=servers["systems"])),
        _build_role_handoff(
            "verification",
            build_role_agent("verification", mcp_server=servers["verification"]),
        ),
        SPECIALIST_HANDOFFS["microwave"],
        SPECIALIST_HANDOFFS["antenna"],
        SPECIALIST_HANDOFFS["test"],
    ]
    return build_role_agent(
        "principal",
        mcp_server=servers["principal"],
        handoffs=mixed_handoffs,
        extra_instructions=_PRINCIPAL_ROUTING_INSTRUCTIONS,
    )


async def run(query: str) -> str:
    from agent.mcp_roles import ProvenanceTrackingContext, build_role_mcp_server

    servers = {key: build_role_mcp_server(key) for key in _LIVE_MCP_ROLE_KEYS}
    manager = MCPServerManager(list(servers.values()), strict=True)
    # Everything that can spawn or hold a subprocess belongs inside this try:
    # the connect and the agent construction that follows it both run against
    # already-live servers, so an exception in either would otherwise strand
    # them. Connecting is eager and unconditional rather than deferred until a
    # handoff picks a role, because the SDK re-fetches an agent's MCP tools on
    # every turn -- a handoff target's server must already be live by the time
    # its own turn arrives, and nothing hooks handoff selection to connect it.
    try:
        await manager.connect_all()
        result = await Runner.run(
            _build_live_principal(servers), query, context=ProvenanceTrackingContext()
        )
    finally:
        await manager.cleanup_all()

    # Load-bearing despite `provenance_integrity_guardrail` covering the same
    # condition: that guardrail only ever runs for the agent it is attached to,
    # and microwave/antenna/test carry none. This reads the finished
    # RunResult instead, so it is the only check that sees a claim one of them
    # produced after a handoff.
    _assert_calculated_provenance_is_tool_backed(result)
    return result.final_output


if __name__ == "__main__":
    import asyncio
    import sys

    query = " ".join(sys.argv[1:]) or (
        "Explain the engineering workflow you will use for RF design and identify "
        "which claims require calculation, simulation, measurement, or human approval."
    )
    print(asyncio.run(run(query)))
