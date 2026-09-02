import os
from dataclasses import dataclass, field
from pathlib import Path

from agents import Agent, FunctionTool, Runner, function_tool
from agents.run import RunResult
from dotenv import load_dotenv

from knowledge.extract import extract_components as _extract_components
from knowledge.index import index_document as _index_document
from knowledge.ingest import ingest_document as _ingest_document
from knowledge.read import read_document as _read_document
from knowledge.search import search_knowledge as _search_knowledge
from rf_tools.calculations import (
    cascade_gain_db,
    friis_noise_factor,
    noise_factor_to_db,
    return_loss_db,
    vswr_from_gamma,
    wavelength,
)
from rf_tools.touchstone import analyze_touchstone

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
def extract_components(document_id: int, requested_backend: str | None = None) -> dict:
    """Extract structured component specifications from a stored datasheet/application_note
    and upsert a components row per part, keyed by (manufacturer, part_number). Runs
    automatically, no confirmation step. Each specification field carries its own
    provenance (MANUFACTURER-SPECIFIED/INFERRED/UNKNOWN) and, if it fails its category's
    physical-plausibility bound, a validation_error. SENSITIVE/RESTRICTED documents always
    use the self-hosted backend, with no fallback to the external API; requesting
    "external" for one raises. A non-datasheet/application_note document is a no-op."""
    return _extract_components(document_id=document_id, requested_backend=requested_backend)


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
#   - systems:      link-level/systems-engineering concerns. Gets all five
#                   calculation tools (wavelength through noise figure --
#                   link budget math is exactly cascaded gain/NF today) plus
#                   the two knowledge-base *authoring* tools (ingest_document,
#                   index_document), since standing up the knowledge base for
#                   the team is systems-level work. Does NOT get
#                   analyze_touchstone_file (device-level network data,
#                   not a systems-level concern) or the knowledge *auditing*
#                   tools (read_document/extract_components -- verification's
#                   job, see below).
#   - microwave:    passive/active RF component and network analysis. Gets
#                   VSWR, return loss, noise figure, and Touchstone analysis
#                   -- the closest fit to S-parameter/network-level work
#                   until S/Z/Y/ABCD conversions are wired as tools (#36).
#                   Does NOT get calculate_cascade_gain (a system-chain
#                   concern, not a single component/network concern) or the
#                   knowledge-authoring tools.
#   - antenna:      antenna-specific. Gets wavelength (electrical size),
#                   VSWR/return loss (antenna input match), and Touchstone
#                   analysis (antenna port measurements) -- the closest
#                   currently-wired fit; the Phase 1 antenna-synthesis
#                   functions (resonant frequency, bandwidth, aperture gain)
#                   are not yet tools (#36). Does NOT get calculate_noise_
#                   figure or calculate_cascade_gain (receiver-chain
#                   concerns, not the antenna element itself).
#   - test:         verification/measurement-adjacent. Gets Touchstone
#                   analysis (the measured-network artifact), plus VSWR,
#                   return loss, and cascade gain for comparing a measured
#                   chain against its predicted/spec values. Does NOT get
#                   any knowledge-authoring or knowledge-auditing tool --
#                   test validates hardware against a spec, it doesn't
#                   ingest or extract documents.
#   - verification: knowledge/provenance-checking, per the ticket's own
#                   frame. Gets the knowledge-base *auditing* tools
#                   (read_document, extract_components) that check what's
#                   already in the knowledge base against its source and
#                   provenance. Does NOT get ingest_document/index_document
#                   (authoring is systems' job -- verification checks the
#                   result, it doesn't add to the store) or any calculation
#                   tool (verification audits documented/extracted claims
#                   and their provenance, it does not itself run RF
#                   arithmetic).
#
#   search_knowledge is shared by every role: literature lookup is useful
#   regardless of domain, and giving every role its own copy of the same
#   tool object is the intended (not accidental) overlap the ticket calls
#   out as fine.
# ---------------------------------------------------------------------------

_ALL_TOOLS = [
    calculate_wavelength,
    calculate_vswr,
    calculate_return_loss,
    calculate_cascade_gain,
    calculate_noise_figure,
    analyze_touchstone_file,
    ingest_document,
    index_document,
    read_document,
    search_knowledge,
    extract_components,
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
            "input match (VSWR, return loss), noise figure, and Touchstone "
            "(.sNp) network data. Defer system-chain-level gain budgeting to "
            "the systems role."
        ),
        tools=[
            calculate_vswr,
            calculate_return_loss,
            calculate_noise_figure,
            analyze_touchstone_file,
            search_knowledge,
        ],
    ),
    RoleSpec(
        key="antenna",
        display_name="Antenna Engineer",
        domain_note=(
            "You focus on antenna-specific concerns: electrical size "
            "(wavelength), input match at the antenna port (VSWR, return "
            "loss), and Touchstone measurements of antenna ports. Defer "
            "receiver-chain noise figure and cascaded gain to the systems "
            "role."
        ),
        tools=[
            calculate_wavelength,
            calculate_vswr,
            calculate_return_loss,
            analyze_touchstone_file,
            search_knowledge,
        ],
    ),
    RoleSpec(
        key="test",
        display_name="Test Engineer",
        domain_note=(
            "You focus on verification and measurement: analyzing Touchstone "
            "network data and comparing measured VSWR/return loss/cascaded "
            "gain against predicted or specified values. You do not ingest or "
            "extract documents -- that is the systems/verification roles' job."
        ),
        tools=[
            analyze_touchstone_file,
            calculate_vswr,
            calculate_return_loss,
            calculate_cascade_gain,
            search_knowledge,
        ],
    ),
    RoleSpec(
        key="verification",
        display_name="Verification Engineer",
        domain_note=(
            "You focus on knowledge and provenance checking: reading a stored "
            "document's full metadata and chunks, and extracting/auditing "
            "structured component specifications with their per-field "
            "provenance. You do not run RF calculations yourself and you do "
            "not add new documents to the knowledge base -- you audit what is "
            "already there."
        ),
        tools=[
            read_document,
            search_knowledge,
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
