"""Thin orchestration: parse -> chunk -> store.

`ingest_document` is what gets wrapped as the `ingest_document` tool in
`agent/main.py` and `mcp_server/server.py`. It composes `extraction.py`,
`provenance.py`, and `db.py` -- no logic of its own beyond wiring them
together and turning failures into a stored row instead of a crash.

No LLM call happens anywhere in this module: docling's parsing is
deterministic, and storage is plain SQL.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from knowledge import db
from knowledge.extraction import parse_document, sections_to_chunks
from knowledge.models import ChunkDraft, Classification, DocumentDraft, SourceType
from knowledge.provenance import default_authority_rank

_CHUNK_SIZE = 1024 * 1024


def _sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(_CHUNK_SIZE), b""):
            digest.update(block)
    return digest.hexdigest()


def ingest_document(
    file_path: str,
    source_type: str,
    license: str,
    classification: str,
) -> dict[str, Any]:
    """Parse, chunk, and store a datasheet/standard/textbook/paper PDF.

    `source_type`, `license`, and `classification` are mandatory (ADR-0001
    requires an explicit classification on every ingested document; no
    default is offered for any of the three). Deterministic end to end --
    docling's parsing is not LLM-based, so this has no backend dependency.

    Re-ingesting an identical file (matching checksum) is rejected and
    returns the existing document's id instead of creating a duplicate.
    Ingesting a newer revision of an already-stored document (same title
    and source_type, different content) creates a new row and flips the
    prior row to SUPERSEDED (ADR-0002).

    If the file fails to parse, the `documents` row is still written, with
    `metadata.extraction_status = "failed"` and zero chunks, rather than
    raising -- an unparseable file is a fact worth recording, not a reason
    to lose track of the document entirely.
    """
    source_type_enum = SourceType(source_type)
    classification_enum = Classification(classification)

    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(file_path)

    checksum = _sha256_of(path)
    authority_rank = default_authority_rank(source_type_enum)

    title = path.stem
    extraction_status = "ok"
    extraction_error: str | None = None
    chunk_drafts: list[ChunkDraft] = []
    try:
        parsed = parse_document(str(path))
        title = parsed.title or path.stem
        chunk_drafts = sections_to_chunks(parsed, source_type_enum)
    except Exception as exc:  # docling can raise a variety of error types
        extraction_status = "failed"
        extraction_error = str(exc)

    metadata: dict[str, Any] = {
        "classification": classification_enum.value,
        "extraction_status": extraction_status,
    }
    if extraction_error is not None:
        metadata["extraction_error"] = extraction_error

    draft = DocumentDraft(
        title=title,
        source_type=source_type_enum,
        classification=classification_enum,
        license=license,
        checksum_sha256=checksum,
        source_uri=str(path.resolve()),
        metadata=metadata,
    )

    conn = db.get_connection()
    try:
        try:
            row = db.insert_document(conn, draft, authority_rank)
        except db.DuplicateDocumentError as exc:
            conn.rollback()
            return {
                "status": "duplicate",
                "document_id": exc.document_id,
                "message": (
                    "A document with this exact content is already stored "
                    f"as document_id={exc.document_id}."
                ),
            }

        inserted = db.insert_chunks(conn, row["id"], chunk_drafts)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    return {
        "status": "ingested",
        "document_id": row["id"],
        "title": row["title"],
        "chunk_count": inserted,
        "extraction_status": extraction_status,
        "supersedes_document_id": row["supersedes_document_id"],
        "authority_rank": authority_rank,
    }
