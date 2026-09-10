import os

import psycopg
import pytest
from dotenv import load_dotenv

from knowledge import extraction
from knowledge.ingest import ingest_document
from knowledge.read import read_document

load_dotenv()


def _extraction_error(document_id: int) -> str | None:
    """Fetch the captured extraction-error text for a document, for use in
    assertion-failure messages -- mirrors tests/test_ingest.py's identical
    helper (see its docstring for why `ingest_document`'s return value alone
    doesn't carry this text)."""
    conn = psycopg.connect(os.environ["DATABASE_URL"], autocommit=True)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT metadata->>'extraction_error' FROM documents WHERE id = %s",
                (document_id,),
            )
            row = cur.fetchone()
            return row[0] if row else None
    finally:
        conn.close()


@pytest.fixture
def no_ocr(monkeypatch):
    """Forces `ingest_document`'s internal `parse_document` call to run with
    OCR switched off -- mirrors tests/test_ingest.py's identical fixture
    (see its docstring for why this doesn't touch OCR's on-by-default
    behavior for any other caller)."""
    monkeypatch.setattr(
        "knowledge.ingest.parse_document",
        lambda path: extraction.parse_document(path, do_ocr=False),
    )


def _write_pdf(path, lines: list[str]) -> None:
    """Hand-rolled minimal single-page PDF -- mirrors tests/test_ingest.py's
    helper so read_document tests can set up real ingested documents without
    a third-party PDF-authoring dependency."""
    content = "BT /F1 14 Tf 72 700 Td 16 TL\n"
    for line in lines:
        esc = line.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")
        content += f"({esc}) Tj T*\n"
    content += "ET"
    content_bytes = content.encode("latin-1")

    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            b"<< /Type /Page /Parent 2 0 R /Resources << /Font << /F1 4 0 R >> >> "
            b"/MediaBox [0 0 612 792] /Contents 5 0 R >>"
        ),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        (
            f"<< /Length {len(content_bytes)} >>\nstream\n".encode("latin-1")
            + content_bytes
            + b"\nendstream"
        ),
    ]

    out = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for i, obj in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode("latin-1") + obj + b"\nendobj\n"

    xref_offset = len(out)
    n = len(objects) + 1
    out += f"xref\n0 {n}\n".encode("latin-1")
    out += b"0000000000 65535 f \n"
    for off in offsets[1:]:
        out += f"{off:010d} 00000 n \n".encode("latin-1")
    out += (f"trailer\n<< /Size {n} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF").encode(
        "latin-1"
    )

    path.write_bytes(bytes(out))


@pytest.fixture
def cleanup_documents():
    """Tracks document ids created via ingest_document (which commits its own
    connection) and deletes them afterward -- mirrors tests/test_ingest.py."""
    ids: list[int] = []
    yield ids
    if not ids:
        return
    conn = psycopg.connect(os.environ["DATABASE_URL"], autocommit=True)
    try:
        with conn.cursor() as cur:
            # One row at a time, reversed (LIFO) -- see tests/test_ingest.py's
            # identical fixture docstring for why a single bulk `ANY(%s)`
            # DELETE risks a self-referential (supersedes_document_id) FK
            # violation.
            for doc_id in reversed(ids):
                cur.execute("DELETE FROM documents WHERE id = %s", (doc_id,))
    finally:
        conn.close()


def test_read_document_returns_not_found_for_nonexistent_id():
    result = read_document(999_999)
    assert result == {"status": "not_found", "document_id": 999_999}


def test_read_document_returns_full_metadata_and_ordered_chunks(
    tmp_path, cleanup_documents, no_ocr
):
    pdf_path = tmp_path / "read_me_amp.pdf"
    _write_pdf(
        pdf_path,
        ["Read Me Amplifier Datasheet", "Section one text.", "Section two text, more detail."],
    )

    ingested = ingest_document(
        file_path=str(pdf_path),
        source_type="datasheet",
        license="manufacturer-datasheet",
        classification="PUBLIC",
    )
    cleanup_documents.append(ingested["document_id"])
    assert ingested["extraction_status"] == "ok", _extraction_error(ingested["document_id"])
    assert ingested["chunk_count"] >= 1

    result = read_document(ingested["document_id"])

    assert result["status"] == "ACTIVE"
    assert result["document_id"] == ingested["document_id"]
    assert result["title"] == ingested["title"]
    assert result["source_type"] == "datasheet"
    assert result["license"] == "manufacturer-datasheet"
    assert result["classification"] == "PUBLIC"
    assert result["authority_rank"] == ingested["authority_rank"]
    assert result["revision"] is None
    assert result["supersedes_document_id"] is None
    assert result["publication_date"] is None
    assert result["author"] is None

    assert len(result["chunks"]) == ingested["chunk_count"]
    assert [c["chunk_index"] for c in result["chunks"]] == sorted(
        c["chunk_index"] for c in result["chunks"]
    )
    for chunk in result["chunks"]:
        assert set(chunk) == {"chunk_index", "content", "page_number", "section"}


def test_read_document_classification_reads_the_column_not_metadata(cleanup_documents):
    """Issue #407: `read_document` must surface `documents.classification`
    (the real column), not the `metadata` JSONB blob's own key -- proven by
    inserting a document whose metadata carries no 'classification' key at
    all via `knowledge.db.insert_document` directly (bypassing
    `ingest_document`) and confirming `read_document` still reports it
    correctly from the column."""
    from knowledge import db
    from knowledge.models import Classification, DocumentDraft, SourceType

    draft = DocumentDraft(
        title="Read Document Column Test",
        source_type=SourceType.DATASHEET,
        classification=Classification.RESTRICTED,
        license="manufacturer-datasheet",
        checksum_sha256="f7" * 32,
        metadata={},  # deliberately no "classification" key
    )
    conn = psycopg.connect(os.environ["DATABASE_URL"], autocommit=True)
    try:
        row = db.insert_document(conn, draft, authority_rank=20)
    finally:
        conn.close()
    cleanup_documents.append(row["id"])

    result = read_document(row["id"])
    assert result["classification"] == "RESTRICTED"


def test_read_document_with_zero_chunks_returns_empty_chunk_list(tmp_path, cleanup_documents):
    """A document whose extraction failed (per #8) is still stored, with zero
    chunks -- read_document must reflect that as an empty list, not an error."""
    corrupt_path = tmp_path / "corrupt_read.pdf"
    corrupt_path.write_bytes(b"%PDF-1.4\nthis is not a valid pdf body\n%%EOF")

    ingested = ingest_document(
        file_path=str(corrupt_path),
        source_type="datasheet",
        license="manufacturer-datasheet",
        classification="PUBLIC",
    )
    cleanup_documents.append(ingested["document_id"])
    assert ingested["chunk_count"] == 0

    result = read_document(ingested["document_id"])

    assert result["status"] == "ACTIVE"
    assert result["chunks"] == []
