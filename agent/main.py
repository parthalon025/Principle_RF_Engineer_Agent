import os
from pathlib import Path

from agents import Agent, Runner, function_tool
from dotenv import load_dotenv

from knowledge.index import index_document as _index_document
from knowledge.ingest import ingest_document as _ingest_document
from knowledge.read import read_document as _read_document
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
