import pytest

from knowledge.db import (
    DuplicateDocumentError,
    find_document_by_checksum,
    insert_chunks,
    insert_document,
)
from knowledge.models import ChunkDraft, Classification, DocumentDraft, SourceType


def _draft(**overrides) -> DocumentDraft:
    defaults = dict(
        title="LM7805 Voltage Regulator",
        source_type=SourceType.DATASHEET,
        classification=Classification.PUBLIC,
        license="manufacturer-datasheet",
        checksum_sha256="a" * 64,
        source_uri="/tmp/lm7805.pdf",
        metadata={"classification": "PUBLIC", "extraction_status": "ok"},
    )
    defaults.update(overrides)
    return DocumentDraft(**defaults)


def test_find_document_by_checksum_returns_none_when_absent(db_conn):
    assert find_document_by_checksum(db_conn, "no-such-checksum") is None


def test_insert_document_then_find_by_checksum(db_conn):
    draft = _draft(checksum_sha256="b" * 64)
    row = insert_document(db_conn, draft, authority_rank=20)

    assert row["title"] == draft.title
    assert row["status"] == "ACTIVE"
    assert row["supersedes_document_id"] is None
    assert row["checksum_sha256"] == draft.checksum_sha256

    found = find_document_by_checksum(db_conn, draft.checksum_sha256)
    assert found is not None
    assert found["id"] == row["id"]


def test_insert_document_rejects_identical_checksum(db_conn):
    draft = _draft(checksum_sha256="c" * 64)
    first = insert_document(db_conn, draft, authority_rank=20)

    with pytest.raises(DuplicateDocumentError) as exc_info:
        insert_document(db_conn, draft, authority_rank=20)

    assert exc_info.value.document_id == first["id"]


def test_insert_document_supersedes_prior_active_revision(db_conn):
    rev_a = _draft(title="XYZ Amplifier", checksum_sha256="d" * 64, revision="A")
    first = insert_document(db_conn, rev_a, authority_rank=20)
    assert first["status"] == "ACTIVE"

    rev_b = _draft(title="XYZ Amplifier", checksum_sha256="e" * 64, revision="B")
    second = insert_document(db_conn, rev_b, authority_rank=20)

    assert second["supersedes_document_id"] == first["id"]
    assert second["status"] == "ACTIVE"

    with db_conn.cursor() as cur:
        cur.execute("SELECT status FROM documents WHERE id = %s", (first["id"],))
        (prior_status,) = cur.fetchone()
    assert prior_status == "SUPERSEDED"


def test_insert_document_does_not_supersede_different_title(db_conn):
    doc1 = _draft(title="Part One", checksum_sha256="f" * 64)
    insert_document(db_conn, doc1, authority_rank=20)

    doc2 = _draft(title="Part Two", checksum_sha256="0" * 64)
    row2 = insert_document(db_conn, doc2, authority_rank=20)

    assert row2["supersedes_document_id"] is None


def test_insert_chunks_stores_content_and_positions(db_conn):
    draft = _draft(checksum_sha256="1" * 64)
    doc_row = insert_document(db_conn, draft, authority_rank=20)

    chunks = [
        ChunkDraft(chunk_index=0, content="Intro text.", section="Overview", page_number=1),
        ChunkDraft(
            chunk_index=1,
            content="| Vcc | 5V |",
            section="Electrical",
            page_number=2,
            metadata={"kind": "table"},
        ),
    ]
    count = insert_chunks(db_conn, doc_row["id"], chunks)
    assert count == 2

    with db_conn.cursor() as cur:
        cur.execute(
            "SELECT chunk_index, content, section, page_number FROM document_chunks "
            "WHERE document_id = %s ORDER BY chunk_index",
            (doc_row["id"],),
        )
        rows = cur.fetchall()

    assert rows[0] == (0, "Intro text.", "Overview", 1)
    assert rows[1] == (1, "| Vcc | 5V |", "Electrical", 2)


def test_insert_chunks_with_empty_list_is_a_noop(db_conn):
    draft = _draft(checksum_sha256="2" * 64)
    doc_row = insert_document(db_conn, draft, authority_rank=20)
    assert insert_chunks(db_conn, doc_row["id"], []) == 0
