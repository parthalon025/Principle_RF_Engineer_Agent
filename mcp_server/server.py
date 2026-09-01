from mcp.server.fastmcp import FastMCP

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


if __name__ == "__main__":
    mcp.run()
