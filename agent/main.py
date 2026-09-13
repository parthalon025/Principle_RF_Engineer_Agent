import os
from dataclasses import dataclass, field
from pathlib import Path

from agents import (
    Agent,
    AsyncOpenAI,
    Handoff,
    ModelSettings,
    Runner,
    RunResult,
    handoff,
    set_default_openai_api,
    set_default_openai_client,
    set_tracing_disabled,
)
from agents.mcp import MCPServerManager, MCPServerStdio
from agents.models.default_models import get_default_model_settings
from dotenv import load_dotenv
from openai.types.shared import Reasoning

from orchestration.policy import category_for

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


def _resolve_llm_provider() -> str:
    """The single place that reads LLM_PROVIDER from the environment. In
    plain terms: this answers "which provider is configured right now" --
    "openai" (default), "anthropic", "local", or "runpod" -- normalized to
    lowercase so callers never need to re-normalize or re-read the
    environment themselves.

    `_resolve_agent_model`, `_resolve_agent_model_settings`,
    `_local_reasoning_output_tail`, and
    `_configure_hosted_openai_compatible_backend` all call this instead of
    independently reading and lowercasing the environment variable
    themselves, so there is exactly one place that can drift out of sync
    with the others (issue #499)."""
    return os.getenv("LLM_PROVIDER", "openai").lower()


def _resolve_agent_model():
    """Build the value to pass as every Agent's `model=`: a plain model-name
    string for the "openai" (SDK default provider), "local", and "runpod"
    providers (the latter two routed via
    _configure_hosted_openai_compatible_backend's default client, below), or
    a `agents.extensions.models.litellm_model.LitellmModel` instance -- a
    `Model` object, not a string -- for any LiteLLM-routed provider like
    "anthropic". `Agent.model` accepts either (`str | Model`)."""
    provider = _resolve_llm_provider()
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
    if _resolve_llm_provider() != "local":
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
    if _resolve_llm_provider() != "local":
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
    provider = _resolve_llm_provider()
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


@dataclass(frozen=True)
class RoleSpec:
    """One specialist role: its display name, tool subset, and the domain
    note appended to the shared system prompt explaining that scope.

    `tools` is always empty now (issue #573): every role's tool-name list
    lives in `agent/mcp_roles.py`'s `MIGRATED_ROLE_TOOL_NAMES` instead.
    `display_name`/`domain_note` stay here because
    `agent.mcp_roles.build_role_agent` reads them for every role -- only the
    tool data moved. The field itself stays (rather than being deleted) so
    `ROLES`'s own `tools=list(_SPEC_BY_KEY[key].tools)` construction below
    keeps working unchanged, and so a future role could still opt back into
    a hand-built tool list without a shape change here.
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
# Every one of them comes out of this with no tools (issue #573: all six
# roles are now migrated), and the principal below has none either: `run()`
# reaches all six through `agent.mcp_roles.build_role_agent`, never through
# these objects. They stay as the constructible registry the test suite and
# any remaining importer expect (display_name/domain_note/handoff wiring).
# Wiring one of them into a live run would give that role an agent with
# nothing to call -- reach for `build_role_agent(key)` instead.
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


# All six roles (issue #573: microwave/antenna/test joined principal/
# systems/verification here, closing out ADR-0059) -- `run()` connects one
# MCPServerStdio per role, eagerly, before the principal's own conversation
# starts.
_LIVE_MCP_ROLE_KEYS = ("principal", "systems", "microwave", "antenna", "test", "verification")


def _build_live_principal(servers: dict[str, MCPServerStdio]) -> Agent:
    """Build `run()`'s principal from already-connected per-role MCP servers.

    `agent.mcp_roles` is imported here rather than at module level because it
    imports several names from this module at ITS own module level -- a
    module-level import either way round is a circular import that breaks
    depending on which of the two a caller reaches first.

    Every specialist handoff target is now built the same way (issue #573):
    `build_role_agent(key, mcp_server=servers[key])`, matching how systems/
    verification were already built before this ticket. There is no more
    "old-style" `SPECIALIST_HANDOFFS[key]` entry left to mix in here --
    `SPECIALIST_HANDOFFS` itself still exists (see its own definition above)
    as part of the non-live `ROLES` constructible registry, but the live
    principal no longer reads from it.
    """
    from agent.mcp_roles import build_role_agent

    specialist_keys = ("systems", "microwave", "antenna", "test", "verification")
    mixed_handoffs: list[Agent | Handoff] = [
        _build_role_handoff(key, build_role_agent(key, mcp_server=servers[key]))
        for key in specialist_keys
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
    # connect_in_parallel=True (issue #573, closing out the #479 investigation's
    # own Point 1 finding): connecting six servers sequentially each pays the
    # ~2.0s cost of a fresh subprocess re-importing the whole mcp_server.server
    # module, dominated by import time, not handshake or process-launch
    # overhead -- measured at ~14.0s sequential for 6 servers, ~3.7s with this
    # flag on. `MCPServerManager` has shipped this flag, unused, since #377;
    # this is the one-line change that turns it on now that every query
    # actually connects all six servers (never five, never partial) before the
    # principal's own conversation starts.
    manager = MCPServerManager(list(servers.values()), strict=True, connect_in_parallel=True)
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
    # condition: that guardrail runs once per Agent it is attached to, and
    # this is the one check that sees a claim ANY specialist produced after a
    # handoff, from a single post-hoc read of the run's own finished result.
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
