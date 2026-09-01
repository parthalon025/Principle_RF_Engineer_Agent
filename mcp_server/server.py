from typing import Any

from mcp.server.fastmcp import FastMCP

from designs.service import create_design as _create_design
from designs.service import read_design as _read_design
from designs.service import record_decision as _record_decision
from designs.service import record_engineering_result as _record_engineering_result
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


if __name__ == "__main__":
    mcp.run()
