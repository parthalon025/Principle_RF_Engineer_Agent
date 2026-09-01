import os
from pathlib import Path
from typing import Any

from agents import Agent, Runner, function_tool
from dotenv import load_dotenv

from designs.service import create_design as _create_design
from designs.service import read_design as _read_design
from designs.service import record_decision as _record_decision
from designs.service import verify_requirement as _verify_requirement
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


principal = Agent(
    name="Principal RF Engineer",
    model=os.getenv("OPENAI_MODEL", "gpt-5.5"),
    instructions=SYSTEM_PROMPT,
    tools=[
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
        create_design,
        read_design,
        record_decision,
        verify_requirement,
    ],
)

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
