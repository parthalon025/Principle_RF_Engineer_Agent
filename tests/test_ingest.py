import inspect
import os
from pathlib import Path

import psycopg
import pytest
from dotenv import load_dotenv

from knowledge import extraction
from knowledge.ingest import ingest_document

load_dotenv()


def _extraction_error(document_id: int) -> str | None:
    """Fetch the captured extraction-error text for a document, for use in
    assertion-failure messages -- so a red `extraction_status` check shows
    *why* parsing failed (per issue #141) instead of just a bare status
    mismatch. `ingest_document`'s return value doesn't carry this text (only
    the stored row's metadata does), so this is a small direct DB read."""
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
    OCR (image-to-text) switched off, for tests whose fixture PDF already
    has a real, selectable text layer and never needs it.

    Patches the `parse_document` name as looked up inside `knowledge.ingest`
    (not `knowledge.extraction`'s own default) so this is scoped to the
    tests that opt into it -- `parse_document`'s own default (`do_ocr=True`)
    is untouched, so any other caller (real ingestion of a scanned document)
    still gets OCR by default (issue #141)."""
    monkeypatch.setattr(
        "knowledge.ingest.parse_document",
        lambda path: extraction.parse_document(path, do_ocr=False),
    )


def _write_pdf(path: Path, lines: list[str]) -> None:
    """Hand-rolled minimal single-page PDF with the given text lines -- no
    third-party PDF-authoring library is a project dependency, so this
    writes the raw PDF object structure directly."""
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
    """Tracks document ids created by ingest_document (which commits its
    own connection) and deletes them afterward -- unlike knowledge/db.py's
    tests, this can't rely on a rolled-back transaction for isolation.

    Deletes one row at a time in REVERSED (LIFO) append order, not a single
    bulk `WHERE id = ANY(%s)` statement -- a later-appended document can
    reference an earlier one via supersedes_document_id (self-referential
    FK), and a single bulk DELETE gives Postgres no row-order guarantee, so
    it can (and did, in practice: ForeignKeyViolation on
    documents_supersedes_document_id_fkey) try to delete the referenced row
    before the referencing one. Deleting newest-first always clears any such
    reference before reaching the row it points to."""
    ids: list[int] = []
    yield ids
    if not ids:
        return
    conn = psycopg.connect(os.environ["DATABASE_URL"], autocommit=True)
    try:
        with conn.cursor() as cur:
            for doc_id in reversed(ids):
                cur.execute("DELETE FROM documents WHERE id = %s", (doc_id,))
    finally:
        conn.close()


def test_classification_and_license_have_no_default():
    sig = inspect.signature(ingest_document)
    assert sig.parameters["classification"].default is inspect.Parameter.empty
    assert sig.parameters["license"].default is inspect.Parameter.empty


def test_ingest_missing_file_raises():
    with pytest.raises(FileNotFoundError):
        ingest_document(
            file_path="/no/such/file.pdf",
            source_type="datasheet",
            license="manufacturer-datasheet",
            classification="PUBLIC",
        )


def test_ingest_rejects_invalid_source_type():
    with pytest.raises(ValueError):
        ingest_document(
            file_path="/no/such/file.pdf",
            source_type="not-a-real-source-type",
            license="manufacturer-datasheet",
            classification="PUBLIC",
        )


def test_ingest_new_document_creates_row_and_chunks(tmp_path, cleanup_documents, no_ocr):
    pdf_path = tmp_path / "widget_amp.pdf"
    _write_pdf(pdf_path, ["Widget Amplifier Datasheet", "Gain: 20 dB typical."])

    result = ingest_document(
        file_path=str(pdf_path),
        source_type="datasheet",
        license="manufacturer-datasheet",
        classification="PUBLIC",
    )
    cleanup_documents.append(result["document_id"])

    assert result["status"] == "ingested"
    assert result["extraction_status"] == "ok", _extraction_error(result["document_id"])
    assert result["chunk_count"] >= 1
    assert result["supersedes_document_id"] is None


def test_reingesting_identical_file_is_rejected_and_returns_existing_id(
    tmp_path, cleanup_documents
):
    pdf_path = tmp_path / "dup_amp.pdf"
    _write_pdf(pdf_path, ["Duplicate Test Amplifier", "Vcc: 5V."])

    first = ingest_document(
        file_path=str(pdf_path),
        source_type="datasheet",
        license="manufacturer-datasheet",
        classification="PUBLIC",
    )
    cleanup_documents.append(first["document_id"])

    second = ingest_document(
        file_path=str(pdf_path),
        source_type="datasheet",
        license="manufacturer-datasheet",
        classification="PUBLIC",
    )

    assert second["status"] == "duplicate"
    assert second["document_id"] == first["document_id"]

    conn = psycopg.connect(os.environ["DATABASE_URL"], autocommit=True)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT count(*) FROM documents WHERE checksum_sha256 = ("
                "SELECT checksum_sha256 FROM documents WHERE id = %s)",
                (first["document_id"],),
            )
            (count,) = cur.fetchone()
    finally:
        conn.close()
    assert count == 1


def test_ingesting_newer_revision_supersedes_prior_when_explicitly_declared(
    tmp_path, cleanup_documents
):
    """ADR-0002: supersession is a human-declared claim (`supersedes_document_id`),
    never inferred from title or filename -- these two PDFs deliberately have
    unrelated titles/filenames to prove that."""
    pdf_a = tmp_path / "power_amp_datasheet_2023.pdf"
    pdf_b = tmp_path / "totally_different_filename.pdf"
    _write_pdf(pdf_a, ["Power Amp Rev A", "Gain: 18 dB."])
    _write_pdf(pdf_b, ["Power Amp Rev B -- Improved", "Gain: 19 dB, improved linearity."])

    first = ingest_document(
        file_path=str(pdf_a),
        source_type="datasheet",
        license="manufacturer-datasheet",
        classification="PUBLIC",
    )
    cleanup_documents.append(first["document_id"])

    second = ingest_document(
        file_path=str(pdf_b),
        source_type="datasheet",
        license="manufacturer-datasheet",
        classification="PUBLIC",
        supersedes_document_id=first["document_id"],
    )
    cleanup_documents.append(second["document_id"])

    assert second["status"] == "ingested"
    assert second["supersedes_document_id"] == first["document_id"]

    conn = psycopg.connect(os.environ["DATABASE_URL"], autocommit=True)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT status FROM documents WHERE id = %s", (first["document_id"],))
            (prior_status,) = cur.fetchone()
    finally:
        conn.close()
    assert prior_status == "SUPERSEDED"


def test_ingesting_unrelated_document_with_matching_title_does_not_supersede(
    tmp_path, cleanup_documents
):
    """A coincidentally-matching title must never trigger supersession on its
    own -- only an explicit `supersedes_document_id` does (ADR-0002)."""
    pdf_a = tmp_path / "first.pdf"
    pdf_b = tmp_path / "second.pdf"
    _write_pdf(pdf_a, ["Shared Title", "Some content."])
    _write_pdf(pdf_b, ["Shared Title", "Unrelated different content."])

    first = ingest_document(
        file_path=str(pdf_a),
        source_type="datasheet",
        license="manufacturer-datasheet",
        classification="PUBLIC",
    )
    cleanup_documents.append(first["document_id"])

    second = ingest_document(
        file_path=str(pdf_b),
        source_type="datasheet",
        license="manufacturer-datasheet",
        classification="PUBLIC",
    )
    cleanup_documents.append(second["document_id"])

    assert second["supersedes_document_id"] is None


def test_ingest_with_invalid_supersession_target_returns_structured_error(
    tmp_path, cleanup_documents
):
    pdf_path = tmp_path / "orphan_revision.pdf"
    _write_pdf(pdf_path, ["Orphan Revision", "Gain: 10 dB."])

    result = ingest_document(
        file_path=str(pdf_path),
        source_type="datasheet",
        license="manufacturer-datasheet",
        classification="PUBLIC",
        supersedes_document_id=999_999,
    )

    assert result["status"] == "invalid_supersession"
    assert result["supersedes_document_id"] == 999_999


def test_authority_rank_override_replaces_source_type_default(tmp_path, cleanup_documents):
    """Ticket #68: `authority_rank_override` is the mechanism
    `knowledge/sourcing/arxiv.py` uses to rank an arXiv preprint below the
    peer-reviewed `paper` default -- exercised directly here against the
    real DB to confirm the override actually reaches the stored row's
    `authority_rank`, not just the returned dict."""
    pdf_path = tmp_path / "overridden_rank.pdf"
    _write_pdf(pdf_path, ["Rank Override Test", "Some content."])

    result = ingest_document(
        file_path=str(pdf_path),
        source_type="paper",
        license="cc-by-4.0",
        classification="PUBLIC",
        authority_rank_override=50,
    )
    cleanup_documents.append(result["document_id"])

    assert result["authority_rank"] == 50

    conn = psycopg.connect(os.environ["DATABASE_URL"], autocommit=True)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT authority_rank FROM documents WHERE id = %s",
                (result["document_id"],),
            )
            (stored_rank,) = cur.fetchone()
    finally:
        conn.close()
    assert stored_rank == 50


def test_title_override_replaces_docling_derived_title(tmp_path, cleanup_documents):
    pdf_path = tmp_path / "some_internal_filename.pdf"
    _write_pdf(pdf_path, ["Whatever docling extracts as a title", "Body text."])

    result = ingest_document(
        file_path=str(pdf_path),
        source_type="paper",
        license="cc-by-4.0",
        classification="PUBLIC",
        title_override="Metamaterial Design for Adaptive EM Skins",
    )
    cleanup_documents.append(result["document_id"])

    assert result["title"] == "Metamaterial Design for Adaptive EM Skins"

    conn = psycopg.connect(os.environ["DATABASE_URL"], autocommit=True)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT title FROM documents WHERE id = %s", (result["document_id"],))
            (stored_title,) = cur.fetchone()
    finally:
        conn.close()
    assert stored_title == "Metamaterial Design for Adaptive EM Skins"


def test_title_override_applies_even_when_extraction_fails(tmp_path, cleanup_documents):
    corrupt_path = tmp_path / "corrupt_with_override.pdf"
    corrupt_path.write_bytes(b"%PDF-1.4\nthis is not a valid pdf body\n%%EOF")

    result = ingest_document(
        file_path=str(corrupt_path),
        source_type="paper",
        license="cc-by-4.0",
        classification="PUBLIC",
        title_override="Title From Authoritative Metadata",
    )
    cleanup_documents.append(result["document_id"])

    assert result["extraction_status"] == "failed"
    assert result["title"] == "Title From Authoritative Metadata"


def test_author_and_revision_are_stored(tmp_path, cleanup_documents):
    pdf_path = tmp_path / "author_revision.pdf"
    _write_pdf(pdf_path, ["Author Revision Test", "Body text."])

    result = ingest_document(
        file_path=str(pdf_path),
        source_type="paper",
        license="cc-by-4.0",
        classification="PUBLIC",
        author="Jane Doe, John Smith",
        revision="2401.01234v2",
    )
    cleanup_documents.append(result["document_id"])

    conn = psycopg.connect(os.environ["DATABASE_URL"], autocommit=True)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT author, revision FROM documents WHERE id = %s",
                (result["document_id"],),
            )
            stored_author, stored_revision = cur.fetchone()
    finally:
        conn.close()
    assert stored_author == "Jane Doe, John Smith"
    assert stored_revision == "2401.01234v2"


def test_extra_metadata_is_merged_into_stored_metadata(tmp_path, cleanup_documents):
    pdf_path = tmp_path / "extra_metadata.pdf"
    _write_pdf(pdf_path, ["Extra Metadata Test", "Body text."])

    result = ingest_document(
        file_path=str(pdf_path),
        source_type="paper",
        license="cc-by-4.0",
        classification="PUBLIC",
        extra_metadata={"arxiv_id": "2401.01234", "doi": "10.1000/example"},
    )
    cleanup_documents.append(result["document_id"])

    conn = psycopg.connect(os.environ["DATABASE_URL"], autocommit=True)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT metadata FROM documents WHERE id = %s", (result["document_id"],))
            (stored_metadata,) = cur.fetchone()
    finally:
        conn.close()
    assert stored_metadata["arxiv_id"] == "2401.01234"
    assert stored_metadata["doi"] == "10.1000/example"
    assert stored_metadata["classification"] == "PUBLIC"
    assert stored_metadata["extraction_status"] == "ok"


def test_ingest_document_stores_classification_as_a_real_column(tmp_path, cleanup_documents):
    """Issue #407: classification must land in `documents.classification` (a
    real, schema-enforced column), not only inside the `metadata` JSONB
    blob -- `insert_document` writes `draft.classification` as a real INSERT
    argument now, so this must be true for every classification value, not
    just PUBLIC."""
    pdf_path = tmp_path / "classification_column.pdf"
    _write_pdf(pdf_path, ["Classification Column Test", "Body text."])

    result = ingest_document(
        file_path=str(pdf_path),
        source_type="paper",
        license="cc-by-4.0",
        classification="SENSITIVE",
    )
    cleanup_documents.append(result["document_id"])

    conn = psycopg.connect(os.environ["DATABASE_URL"], autocommit=True)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT classification FROM documents WHERE id = %s", (result["document_id"],)
            )
            (stored_classification,) = cur.fetchone()
    finally:
        conn.close()
    assert stored_classification == "SENSITIVE"


def test_extra_metadata_cannot_override_reserved_metadata_keys(tmp_path, cleanup_documents):
    pdf_path = tmp_path / "extra_metadata_collision.pdf"
    _write_pdf(pdf_path, ["Extra Metadata Collision Test", "Body text."])

    result = ingest_document(
        file_path=str(pdf_path),
        source_type="paper",
        license="cc-by-4.0",
        classification="PUBLIC",
        extra_metadata={"classification": "SOMETHING_ELSE", "extraction_status": "bogus"},
    )
    cleanup_documents.append(result["document_id"])

    assert result["extraction_status"] == "ok"
    conn = psycopg.connect(os.environ["DATABASE_URL"], autocommit=True)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT metadata FROM documents WHERE id = %s", (result["document_id"],))
            (stored_metadata,) = cur.fetchone()
    finally:
        conn.close()
    assert stored_metadata["classification"] == "PUBLIC"
    assert stored_metadata["extraction_status"] == "ok"


def test_extraction_failure_still_writes_document_with_zero_chunks(tmp_path, cleanup_documents):
    corrupt_path = tmp_path / "corrupt.pdf"
    corrupt_path.write_bytes(b"%PDF-1.4\nthis is not a valid pdf body\n%%EOF")

    result = ingest_document(
        file_path=str(corrupt_path),
        source_type="datasheet",
        license="manufacturer-datasheet",
        classification="PUBLIC",
    )
    cleanup_documents.append(result["document_id"])

    assert result["status"] == "ingested"
    assert result["extraction_status"] == "failed"
    assert result["chunk_count"] == 0

    conn = psycopg.connect(os.environ["DATABASE_URL"], autocommit=True)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT metadata->>'extraction_status' FROM documents WHERE id = %s",
                (result["document_id"],),
            )
            (extraction_status,) = cur.fetchone()
            cur.execute(
                "SELECT count(*) FROM document_chunks WHERE document_id = %s",
                (result["document_id"],),
            )
            (chunk_count,) = cur.fetchone()
    finally:
        conn.close()
    assert extraction_status == "failed"
    assert chunk_count == 0
