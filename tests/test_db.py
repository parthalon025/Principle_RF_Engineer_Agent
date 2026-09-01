import pytest

from knowledge.db import (
    DuplicateDocumentError,
    InvalidSupersessionError,
    find_document_by_checksum,
    get_chunk_details,
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


def test_insert_document_supersedes_when_explicitly_declared(db_conn):
    rev_a = _draft(title="XYZ Amplifier", checksum_sha256="d" * 64, revision="A")
    first = insert_document(db_conn, rev_a, authority_rank=20)
    assert first["status"] == "ACTIVE"

    rev_b = _draft(
        title="XYZ Amplifier",
        checksum_sha256="e" * 64,
        revision="B",
        supersedes_document_id=first["id"],
    )
    second = insert_document(db_conn, rev_b, authority_rank=20)

    assert second["supersedes_document_id"] == first["id"]
    assert second["status"] == "ACTIVE"

    with db_conn.cursor() as cur:
        cur.execute("SELECT status FROM documents WHERE id = %s", (first["id"],))
        (prior_status,) = cur.fetchone()
    assert prior_status == "SUPERSEDED"


def test_insert_document_never_infers_supersession_from_title(db_conn):
    """ADR-0002: a shared title alone must never trigger supersession --
    only an explicit `supersedes_document_id` does."""
    doc1 = _draft(title="Same Title", checksum_sha256="f" * 64)
    insert_document(db_conn, doc1, authority_rank=20)

    doc2 = _draft(title="Same Title", checksum_sha256="0" * 64)
    row2 = insert_document(db_conn, doc2, authority_rank=20)

    assert row2["supersedes_document_id"] is None


def test_insert_document_rejects_nonexistent_supersession_target(db_conn):
    draft = _draft(checksum_sha256="3" * 64, supersedes_document_id=999_999)
    with pytest.raises(InvalidSupersessionError) as exc_info:
        insert_document(db_conn, draft, authority_rank=20)
    assert exc_info.value.document_id == 999_999


def test_insert_document_rejects_superseding_a_superseded_document(db_conn):
    rev_a = _draft(checksum_sha256="4" * 64)
    first = insert_document(db_conn, rev_a, authority_rank=20)
    rev_b = _draft(checksum_sha256="5" * 64, supersedes_document_id=first["id"])
    insert_document(db_conn, rev_b, authority_rank=20)

    rev_c = _draft(checksum_sha256="6" * 64, supersedes_document_id=first["id"])
    with pytest.raises(InvalidSupersessionError):
        insert_document(db_conn, rev_c, authority_rank=20)


def test_insert_document_rejects_source_type_mismatch_on_supersession(db_conn):
    standard = _draft(
        checksum_sha256="7" * 64, source_type=SourceType.STANDARD, title="Some Standard"
    )
    first = insert_document(db_conn, standard, authority_rank=20)

    textbook = _draft(
        checksum_sha256="8" * 64,
        source_type=SourceType.TEXTBOOK,
        supersedes_document_id=first["id"],
    )
    with pytest.raises(InvalidSupersessionError):
        insert_document(db_conn, textbook, authority_rank=20)


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


def test_get_chunk_details_includes_page_number_and_section_in_order(db_conn):
    draft = _draft(checksum_sha256="9" * 64)
    doc_row = insert_document(db_conn, draft, authority_rank=20)
    chunks = [
        ChunkDraft(chunk_index=1, content="second", section="B", page_number=2),
        ChunkDraft(chunk_index=0, content="first", section="A", page_number=1),
    ]
    insert_chunks(db_conn, doc_row["id"], chunks)

    details = get_chunk_details(db_conn, doc_row["id"])

    assert [d["chunk_index"] for d in details] == [0, 1]
    assert details[0]["content"] == "first"
    assert details[0]["section"] == "A"
    assert details[0]["page_number"] == 1
    assert details[1]["content"] == "second"
    assert details[1]["section"] == "B"
    assert details[1]["page_number"] == 2


def test_get_chunk_details_with_no_chunks_returns_empty_list(db_conn):
    draft = _draft(checksum_sha256="aa" + "1" * 62)
    doc_row = insert_document(db_conn, draft, authority_rank=20)
    assert get_chunk_details(db_conn, doc_row["id"]) == []
