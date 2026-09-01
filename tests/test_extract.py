import os

import psycopg
import pytest
from dotenv import load_dotenv

from knowledge import db
from knowledge.backend import RestrictedBackendViolation
from knowledge.extract import extract_components
from knowledge.extraction_llm import LocalExtractionUnavailableError
from knowledge.models import ChunkDraft, Classification, DocumentDraft, SourceType

load_dotenv()


@pytest.fixture
def cleanup_documents():
    """extract_components (like index_document) opens its own committed
    connection, so isolation can't rely on a rolled-back transaction --
    track document ids and delete them, and any components row pointing at
    them (no ON DELETE CASCADE on that FK), afterward."""
    ids: list[int] = []
    yield ids
    if not ids:
        return
    conn = psycopg.connect(os.environ["DATABASE_URL"], autocommit=True)
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM components WHERE datasheet_document_id = ANY(%s)", (ids,))
            cur.execute("DELETE FROM documents WHERE id = ANY(%s)", (ids,))
    finally:
        conn.close()


def _seed_document(
    classification: Classification,
    checksum: str,
    source_type: SourceType = SourceType.DATASHEET,
    n_chunks: int = 1,
) -> int:
    draft = DocumentDraft(
        title=f"Seeded Doc {checksum}",
        source_type=source_type,
        classification=classification,
        license="manufacturer-datasheet",
        checksum_sha256=checksum,
        metadata={"classification": classification.value},
    )
    conn = psycopg.connect(os.environ["DATABASE_URL"])
    try:
        row = db.insert_document(conn, draft, authority_rank=20)
        chunks = [
            ChunkDraft(chunk_index=i, content=f"chunk {i} content", section=None, page_number=1)
            for i in range(n_chunks)
        ]
        db.insert_chunks(conn, row["id"], chunks)
        conn.commit()
        return row["id"]
    finally:
        conn.close()


def _raw_amp(part_number: str, confidence: str = "high", nf_db: float = 1.5) -> list[dict]:
    return [
        {
            "manufacturer": "Acme RF",
            "part_number": part_number,
            "category": "amplifier",
            "fields": {
                "gain_db": {
                    "value": 20.0,
                    "unit": "dB",
                    "condition": "Vcc=5V",
                    "confidence": confidence,
                    "chunk_id": 1,
                    "page_number": 1,
                },
                "nf_db": {
                    "value": nf_db,
                    "unit": "dB",
                    "condition": None,
                    "confidence": confidence,
                    "chunk_id": 1,
                    "page_number": 1,
                },
            },
        }
    ]


class _Spy:
    """Same call-recording fake pattern as tests/test_index.py's _Spy, here
    standing in for `extract_local`/`extract_external`."""

    def __init__(self, result=None, raises=None):
        self.calls: list = []
        self._result = result
        self._raises = raises

    def __call__(self, chunks):
        self.calls.append(chunks)
        if self._raises is not None:
            raise self._raises
        return self._result if self._result is not None else []


def _fetch_components(document_id: int) -> list[tuple]:
    conn = psycopg.connect(os.environ["DATABASE_URL"], autocommit=True)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT manufacturer, part_number, category, specifications "
                "FROM components WHERE datasheet_document_id = %s",
                (document_id,),
            )
            return cur.fetchall()
    finally:
        conn.close()


def test_extract_components_missing_document_raises():
    with pytest.raises(ValueError):
        extract_components(document_id=-1, extract_local=_Spy(), extract_external=_Spy())


def test_extract_components_skips_non_datasheet_application_note_source_types(
    cleanup_documents,
):
    doc_id = _seed_document(Classification.PUBLIC, "t11-s1" * 11, source_type=SourceType.STANDARD)
    cleanup_documents.append(doc_id)

    local_spy = _Spy()
    external_spy = _Spy()
    result = extract_components(doc_id, extract_local=local_spy, extract_external=external_spy)

    assert result["status"] == "skipped"
    assert local_spy.calls == []
    assert external_spy.calls == []


def test_public_datasheet_defaults_to_local_and_stores_component(cleanup_documents, monkeypatch):
    monkeypatch.delenv("DEFAULT_LLM_BACKEND", raising=False)
    doc_id = _seed_document(Classification.PUBLIC, "t11-s2" * 11)
    cleanup_documents.append(doc_id)

    local_spy = _Spy(result=_raw_amp(part_number="T11-ACM-2", confidence="high", nf_db=1.5))
    external_spy = _Spy()

    result = extract_components(doc_id, extract_local=local_spy, extract_external=external_spy)

    assert result["status"] == "extracted"
    assert result["backend"] == "local"
    assert result["component_count"] == 1
    assert len(local_spy.calls) == 1
    assert external_spy.calls == []

    rows = _fetch_components(doc_id)
    assert len(rows) == 1
    manufacturer, part_number, category, specs = rows[0]
    assert manufacturer == "Acme RF"
    assert part_number == "T11-ACM-2"
    assert category == "amplifier"
    assert specs["nf_db"]["value"] == 1.5
    assert specs["nf_db"]["unit"] == "dB"
    assert specs["nf_db"]["provenance"] == "MANUFACTURER-SPECIFIED"
    assert specs["nf_db"]["chunk_id"] == 1
    assert specs["nf_db"]["page_number"] == 1
    assert "validation_error" not in specs["nf_db"]


def test_low_confidence_field_is_inferred(cleanup_documents):
    doc_id = _seed_document(Classification.PUBLIC, "t11-s3" * 11)
    cleanup_documents.append(doc_id)

    local_spy = _Spy(result=_raw_amp(part_number="T11-ACM-3", confidence="low", nf_db=1.5))
    result = extract_components(doc_id, extract_local=local_spy, extract_external=_Spy())
    assert result["status"] == "extracted"

    rows = _fetch_components(doc_id)
    _, _, _, specs = rows[0]
    assert specs["nf_db"]["provenance"] == "INFERRED"


def test_physically_invalid_field_is_unknown_regardless_of_confidence(cleanup_documents):
    doc_id = _seed_document(Classification.PUBLIC, "t11-s4" * 11)
    cleanup_documents.append(doc_id)

    local_spy = _Spy(result=_raw_amp(part_number="T11-ACM-4", confidence="high", nf_db=-3.0))
    result = extract_components(doc_id, extract_local=local_spy, extract_external=_Spy())
    assert result["status"] == "extracted"

    rows = _fetch_components(doc_id)
    _, _, _, specs = rows[0]
    assert specs["nf_db"]["provenance"] == "UNKNOWN"
    assert "validation_error" in specs["nf_db"]


def test_public_document_explicit_external_request(cleanup_documents):
    doc_id = _seed_document(Classification.INTERNAL, "t11-s5" * 11)
    cleanup_documents.append(doc_id)

    local_spy = _Spy()
    external_spy = _Spy(result=_raw_amp(part_number="T11-ACM-5"))

    result = extract_components(
        doc_id,
        requested_backend="external",
        extract_local=local_spy,
        extract_external=external_spy,
    )
    assert result["backend"] == "external"
    assert local_spy.calls == []
    assert len(external_spy.calls) == 1


def test_public_document_respects_default_llm_backend_env_var(cleanup_documents, monkeypatch):
    monkeypatch.setenv("DEFAULT_LLM_BACKEND", "external")
    doc_id = _seed_document(Classification.PUBLIC, "t11-s6" * 11)
    cleanup_documents.append(doc_id)

    local_spy = _Spy()
    external_spy = _Spy(result=_raw_amp(part_number="T11-ACM-6"))

    result = extract_components(doc_id, extract_local=local_spy, extract_external=external_spy)
    assert result["backend"] == "external"
    assert local_spy.calls == []
    assert len(external_spy.calls) == 1


def test_public_document_falls_back_to_external_when_local_unreachable(
    cleanup_documents, monkeypatch
):
    monkeypatch.delenv("DEFAULT_LLM_BACKEND", raising=False)
    doc_id = _seed_document(Classification.INTERNAL, "t11-s7" * 11)
    cleanup_documents.append(doc_id)

    local_spy = _Spy(raises=LocalExtractionUnavailableError("down"))
    external_spy = _Spy(result=_raw_amp(part_number="T11-ACM-7"))

    result = extract_components(doc_id, extract_local=local_spy, extract_external=external_spy)
    assert result["backend"] == "external"
    assert len(local_spy.calls) == 1
    assert len(external_spy.calls) == 1


@pytest.mark.parametrize("classification", [Classification.SENSITIVE, Classification.RESTRICTED])
def test_restricted_document_uses_local_only(cleanup_documents, classification):
    doc_id = _seed_document(classification, f"{classification.value[0].lower()}t11a" * 12)
    cleanup_documents.append(doc_id)

    local_spy = _Spy(result=_raw_amp(part_number=f"T11-ACM-{classification.value}-A"))
    external_spy = _Spy()

    result = extract_components(doc_id, extract_local=local_spy, extract_external=external_spy)
    assert result["backend"] == "local"
    assert len(local_spy.calls) == 1
    assert external_spy.calls == []

    rows = _fetch_components(doc_id)
    assert len(rows) == 1


@pytest.mark.parametrize("classification", [Classification.SENSITIVE, Classification.RESTRICTED])
def test_restricted_document_rejects_explicit_external_request(cleanup_documents, classification):
    doc_id = _seed_document(classification, f"{classification.value[0].lower()}t11b" * 12)
    cleanup_documents.append(doc_id)

    local_spy = _Spy()
    external_spy = _Spy()
    with pytest.raises(RestrictedBackendViolation):
        extract_components(
            doc_id,
            requested_backend="external",
            extract_local=local_spy,
            extract_external=external_spy,
        )
    assert local_spy.calls == []
    assert external_spy.calls == []

    rows = _fetch_components(doc_id)
    assert rows == []


@pytest.mark.parametrize("classification", [Classification.SENSITIVE, Classification.RESTRICTED])
def test_restricted_document_local_unavailable_fails_loudly_no_fallback(
    cleanup_documents, classification
):
    doc_id = _seed_document(classification, f"{classification.value[0].lower()}t11c" * 12)
    cleanup_documents.append(doc_id)

    local_spy = _Spy(raises=LocalExtractionUnavailableError("self-hosted endpoint down"))
    external_spy = _Spy()
    with pytest.raises(LocalExtractionUnavailableError):
        extract_components(doc_id, extract_local=local_spy, extract_external=external_spy)

    assert len(local_spy.calls) == 1
    assert external_spy.calls == []

    rows = _fetch_components(doc_id)
    assert rows == []


def test_unknown_category_in_raw_result_is_skipped_not_fatal(cleanup_documents):
    doc_id = _seed_document(Classification.PUBLIC, "t11-s8" * 11)
    cleanup_documents.append(doc_id)

    raw = [
        {
            "manufacturer": "Acme",
            "part_number": "T11-BAD-1",
            "category": "not-a-real-category",
            "fields": {},
        },
        *_raw_amp(part_number="T11-ACM-8"),
    ]
    local_spy = _Spy(result=raw)
    result = extract_components(doc_id, extract_local=local_spy, extract_external=_Spy())

    assert result["component_count"] == 1
    assert len(result.get("skipped", [])) == 1

    rows = _fetch_components(doc_id)
    assert len(rows) == 1
    assert rows[0][1] == "T11-ACM-8"


def test_field_not_in_category_schema_is_dropped(cleanup_documents):
    doc_id = _seed_document(Classification.PUBLIC, "t11-s9" * 11)
    cleanup_documents.append(doc_id)

    raw = [
        {
            "manufacturer": "Acme",
            "part_number": "T11-ACM-9",
            "category": "amplifier",
            "fields": {
                "gain_db": {
                    "value": 15.0,
                    "unit": "dB",
                    "confidence": "high",
                    "chunk_id": 1,
                    "page_number": 1,
                },
                "made_up_field": {
                    "value": 1,
                    "unit": "",
                    "confidence": "high",
                    "chunk_id": 1,
                    "page_number": 1,
                },
            },
        }
    ]
    local_spy = _Spy(result=raw)
    extract_components(doc_id, extract_local=local_spy, extract_external=_Spy())

    rows = _fetch_components(doc_id)
    _, _, _, specs = rows[0]
    assert "made_up_field" not in specs
    assert "gain_db" in specs
