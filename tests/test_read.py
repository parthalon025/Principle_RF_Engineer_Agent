import os

import psycopg
from conftest import extraction_error as _extraction_error
from conftest import write_pdf as _write_pdf
from dotenv import load_dotenv

from knowledge.ingest import ingest_document
from knowledge.read import read_document

load_dotenv()


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
