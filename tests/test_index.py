import os

import psycopg
import pytest
from dotenv import load_dotenv

from knowledge import db
from knowledge.backend import RestrictedBackendViolation
from knowledge.embedding import LocalBackendUnavailableError
from knowledge.index import index_document
from knowledge.models import ChunkDraft, Classification, DocumentDraft, SourceType

load_dotenv()

_DIM = 1536
_LOCAL_DIM = int(os.environ.get("EMBEDDING_DIM_LOCAL", "1536"))


def _vector(seed: float) -> list[float]:
    return [seed] * _DIM


def _local_vector(seed: float) -> list[float]:
    """Sized for the `embedding_local` column, which -- per this repo's own
    .env.example/docker-compose.yml default (EMBEDDING_DIM_LOCAL=1024, BAAI/
    bge-m3's actual dimension) -- is independent of `embedding`'s (_DIM)."""
    return [seed] * _LOCAL_DIM


@pytest.fixture
def cleanup_documents():
    """Same pattern as tests/test_ingest.py's fixture: index_document opens
    its own committed connection, so isolation can't rely on a rolled-back
    transaction -- track ids and delete them afterward."""
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


def _seed_document(classification: Classification, checksum: str, n_chunks: int = 2) -> int:
    """Insert and commit a document with `n_chunks` chunks, for index_document
    (on its own connection) to see."""
    draft = DocumentDraft(
        title=f"Seeded Doc {checksum}",
        source_type=SourceType.DATASHEET,
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


def _fetch_columns(document_id: int) -> list[tuple]:
    conn = psycopg.connect(os.environ["DATABASE_URL"], autocommit=True)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT chunk_index, embedding IS NOT NULL, embedding_local IS NOT NULL "
                "FROM document_chunks WHERE document_id = %s ORDER BY chunk_index",
                (document_id,),
            )
            return cur.fetchall()
    finally:
        conn.close()


class _Spy:
    """A minimal call-recording fake, standing in for `simple monkeypatch/
    fake of the two adapter functions` per ticket #9's design notes -- no
    mocking framework, matching this repo's existing test style."""

    def __init__(self, result=None, raises=None):
        self.calls: list[list[str]] = []
        self._result = result
        self._raises = raises

    def __call__(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(texts)
        if self._raises is not None:
            raise self._raises
        return self._result if self._result is not None else [_vector(1.0) for _ in texts]


def test_index_document_missing_raises():
    with pytest.raises(ValueError):
        index_document(document_id=-1, embed_local=_Spy(), embed_external=_Spy())


def test_public_document_defaults_to_local(cleanup_documents, monkeypatch):
    monkeypatch.delenv("DEFAULT_LLM_BACKEND", raising=False)
    doc_id = _seed_document(Classification.PUBLIC, "1" * 64)
    cleanup_documents.append(doc_id)

    local_spy = _Spy(result=[_local_vector(0.5), _local_vector(0.5)])
    external_spy = _Spy()

    result = index_document(doc_id, embed_local=local_spy, embed_external=external_spy)

    assert result["status"] == "indexed"
    assert result["backend"] == "local"
    assert result["column"] == "embedding_local"
    assert result["chunk_count"] == 2
    assert len(local_spy.calls) == 1
    assert external_spy.calls == []

    rows = _fetch_columns(doc_id)
    assert rows == [(0, False, True), (1, False, True)]


def test_public_document_explicit_external_request(cleanup_documents):
    doc_id = _seed_document(Classification.INTERNAL, "2" * 64)
    cleanup_documents.append(doc_id)

    local_spy = _Spy()
    external_spy = _Spy(result=[_vector(0.2), _vector(0.2)])

    result = index_document(
        doc_id, requested_backend="external", embed_local=local_spy, embed_external=external_spy
    )

    assert result["backend"] == "external"
    assert result["column"] == "embedding"
    assert local_spy.calls == []
    assert len(external_spy.calls) == 1

    rows = _fetch_columns(doc_id)
    assert rows == [(0, True, False), (1, True, False)]


def test_public_document_respects_default_llm_backend_env_var(cleanup_documents, monkeypatch):
    monkeypatch.setenv("DEFAULT_LLM_BACKEND", "external")
    doc_id = _seed_document(Classification.PUBLIC, "3" * 64)
    cleanup_documents.append(doc_id)

    local_spy = _Spy()
    external_spy = _Spy(result=[_vector(0.1), _vector(0.1)])

    result = index_document(doc_id, embed_local=local_spy, embed_external=external_spy)

    assert result["backend"] == "external"
    assert local_spy.calls == []
    assert len(external_spy.calls) == 1


def test_public_document_falls_back_to_external_when_local_unreachable(
    cleanup_documents, monkeypatch
):
    monkeypatch.delenv("DEFAULT_LLM_BACKEND", raising=False)
    doc_id = _seed_document(Classification.INTERNAL, "4" * 64)
    cleanup_documents.append(doc_id)

    local_spy = _Spy(raises=LocalBackendUnavailableError("down"))
    external_spy = _Spy(result=[_vector(0.3), _vector(0.3)])

    result = index_document(doc_id, embed_local=local_spy, embed_external=external_spy)

    assert result["backend"] == "external"
    assert result["column"] == "embedding"
    assert len(local_spy.calls) == 1
    assert len(external_spy.calls) == 1

    rows = _fetch_columns(doc_id)
    assert rows == [(0, True, False), (1, True, False)]


@pytest.mark.parametrize("classification", [Classification.SENSITIVE, Classification.RESTRICTED])
def test_restricted_document_uses_local_only(cleanup_documents, classification):
    doc_id = _seed_document(classification, f"{classification.value[0].lower()}5" * 32)
    cleanup_documents.append(doc_id)

    local_spy = _Spy(result=[_local_vector(0.7), _local_vector(0.7)])
    external_spy = _Spy()

    result = index_document(doc_id, embed_local=local_spy, embed_external=external_spy)

    assert result["backend"] == "local"
    assert result["column"] == "embedding_local"
    assert len(local_spy.calls) == 1
    assert external_spy.calls == []

    rows = _fetch_columns(doc_id)
    assert rows == [(0, False, True), (1, False, True)]


@pytest.mark.parametrize("classification", [Classification.SENSITIVE, Classification.RESTRICTED])
def test_restricted_document_rejects_explicit_external_request(cleanup_documents, classification):
    doc_id = _seed_document(classification, f"{classification.value[0].lower()}6" * 32)
    cleanup_documents.append(doc_id)

    local_spy = _Spy()
    external_spy = _Spy()

    with pytest.raises(RestrictedBackendViolation):
        index_document(
            doc_id, requested_backend="external", embed_local=local_spy, embed_external=external_spy
        )

    # Neither adapter was ever called -- the floor is enforced before any
    # chunk is touched.
    assert local_spy.calls == []
    assert external_spy.calls == []

    rows = _fetch_columns(doc_id)
    assert rows == [(0, False, False), (1, False, False)]


def test_restricted_routing_reads_the_classification_column_not_metadata(cleanup_documents):
    """Issue #407: `index_document`'s RESTRICTED/SENSITIVE-forces-local floor
    must be driven by `documents.classification` (the real column), not by
    the `metadata` JSONB blob -- proven by seeding a document whose metadata
    carries no 'classification' key at all and confirming the floor is still
    enforced. This is the regression test for the promotion being a pure
    storage-location change: the routing behavior itself must be identical
    to test_restricted_document_uses_local_only/
    test_restricted_document_rejects_explicit_external_request above."""
    draft = DocumentDraft(
        title="No Metadata Classification Key",
        source_type=SourceType.DATASHEET,
        classification=Classification.RESTRICTED,
        license="manufacturer-datasheet",
        checksum_sha256="d8" * 32,
        metadata={},  # deliberately no "classification" key
    )
    conn = psycopg.connect(os.environ["DATABASE_URL"])
    try:
        row = db.insert_document(conn, draft, authority_rank=20)
        chunks = [ChunkDraft(chunk_index=0, content="chunk 0", section=None, page_number=1)]
        db.insert_chunks(conn, row["id"], chunks)
        conn.commit()
        doc_id = row["id"]
    finally:
        conn.close()
    cleanup_documents.append(doc_id)

    # The floor still rejects an explicit external request...
    with pytest.raises(RestrictedBackendViolation):
        index_document(
            doc_id, requested_backend="external", embed_local=_Spy(), embed_external=_Spy()
        )

    # ...and still routes to local-only by default.
    local_spy = _Spy(result=[_local_vector(0.9)])
    external_spy = _Spy()
    result = index_document(doc_id, embed_local=local_spy, embed_external=external_spy)

    assert result["backend"] == "local"
    assert result["column"] == "embedding_local"
    assert len(local_spy.calls) == 1
    assert external_spy.calls == []


@pytest.mark.parametrize("classification", [Classification.SENSITIVE, Classification.RESTRICTED])
def test_restricted_document_local_unavailable_fails_loudly_no_fallback(
    cleanup_documents, classification
):
    doc_id = _seed_document(classification, f"{classification.value[0].lower()}7" * 32)
    cleanup_documents.append(doc_id)

    local_spy = _Spy(raises=LocalBackendUnavailableError("self-hosted endpoint down"))
    external_spy = _Spy()

    with pytest.raises(LocalBackendUnavailableError):
        index_document(doc_id, embed_local=local_spy, embed_external=external_spy)

    # The failure must never be caught and retried against the external API.
    assert len(local_spy.calls) == 1
    assert external_spy.calls == []

    rows = _fetch_columns(doc_id)
    assert rows == [(0, False, False), (1, False, False)]
