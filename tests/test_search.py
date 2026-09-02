import os

import psycopg
import pytest
from dotenv import load_dotenv

from knowledge.db import (
    get_chunks,
    insert_chunks,
    insert_document,
    search_lexical,
    search_semantic,
    write_chunk_embeddings,
)
from knowledge.models import ChunkDraft, Classification, DocumentDraft, SourceType
from knowledge.search import search_design_records, search_knowledge

load_dotenv()

_DIM = 1536


def _vector(seed: float) -> list[float]:
    return [seed] * _DIM


def _draft(**overrides) -> DocumentDraft:
    defaults = dict(
        title="Search Fixture Document",
        source_type=SourceType.DATASHEET,
        classification=Classification.PUBLIC,
        license="manufacturer-datasheet",
        checksum_sha256="s" * 64,
        metadata={"classification": "PUBLIC", "extraction_status": "ok"},
    )
    defaults.update(overrides)
    return DocumentDraft(**defaults)


def _seed_doc_with_chunks(
    conn, *, checksum: str, contents: list[str], authority_rank: int = 20, **draft_overrides
):
    draft = _draft(checksum_sha256=checksum, **draft_overrides)
    row = insert_document(conn, draft, authority_rank=authority_rank)
    chunks = [
        ChunkDraft(chunk_index=i, content=content, section=None, page_number=1)
        for i, content in enumerate(contents)
    ]
    insert_chunks(conn, row["id"], chunks)
    return row


def test_content_fts_gin_index_exists(db_conn):
    """Ticket #10: a GIN full-text index on document_chunks.content must
    exist, applied idempotently alongside the two HNSW embedding indexes
    (db/schema.sql, applied via db/apply_schema.py)."""
    with db_conn.cursor() as cur:
        cur.execute(
            "SELECT indexdef FROM pg_indexes "
            "WHERE tablename = 'document_chunks' AND indexname = %s",
            ("document_chunks_content_fts_gin",),
        )
        row = cur.fetchone()
    assert row is not None
    (indexdef,) = row
    assert "gin" in indexdef.lower()
    assert "to_tsvector" in indexdef.lower()


def test_search_lexical_matches_on_content(db_conn):
    doc = _seed_doc_with_chunks(
        db_conn,
        checksum="1" * 64,
        contents=["Wideband low-noise amplifier with 20 dB gain.", "Unrelated filler text."],
    )

    results = search_lexical(db_conn, "low-noise amplifier")

    assert any(r["document_id"] == doc["id"] and r["chunk_index"] == 0 for r in results)
    assert all(r["chunk_index"] != 1 for r in results if r["document_id"] == doc["id"])


def test_search_lexical_returns_empty_when_no_match(db_conn):
    _seed_doc_with_chunks(db_conn, checksum="2" * 64, contents=["Nothing relevant here."])

    results = search_lexical(db_conn, "gallium nitride transistor")

    assert results == []


def test_search_lexical_excludes_superseded_by_default(db_conn):
    superseded = _seed_doc_with_chunks(
        db_conn, checksum="3" * 64, contents=["Klystron amplifier chain design notes."]
    )
    with db_conn.cursor() as cur:
        cur.execute("UPDATE documents SET status = 'SUPERSEDED' WHERE id = %s", (superseded["id"],))

    results = search_lexical(db_conn, "klystron amplifier")

    assert results == []


def test_search_lexical_pinned_document_id_retrieves_superseded(db_conn):
    superseded = _seed_doc_with_chunks(
        db_conn, checksum="4" * 64, contents=["Traveling wave tube amplifier notes."]
    )
    with db_conn.cursor() as cur:
        cur.execute("UPDATE documents SET status = 'SUPERSEDED' WHERE id = %s", (superseded["id"],))

    results = search_lexical(db_conn, "traveling wave tube", document_id=superseded["id"])

    assert len(results) == 1
    assert results[0]["document_id"] == superseded["id"]
    assert results[0]["status"] == "SUPERSEDED"


def test_search_semantic_rejects_unknown_column(db_conn):
    with pytest.raises(ValueError):
        search_semantic(db_conn, "not_a_real_column", _vector(1.0))


def test_search_semantic_matches_by_cosine_distance(db_conn):
    doc = _seed_doc_with_chunks(
        db_conn, checksum="5" * 64, contents=["Chunk A content.", "Chunk B content."]
    )
    chunks = get_chunks(db_conn, doc["id"])
    write_chunk_embeddings(
        db_conn, "embedding", [c["id"] for c in chunks], [_vector(1.0), _vector(-1.0)]
    )

    results = search_semantic(db_conn, "embedding", _vector(1.0))

    assert results[0]["document_id"] == doc["id"]
    assert results[0]["chunk_index"] == 0
    assert results[0]["score"] > results[-1]["score"]


def test_search_semantic_excludes_chunks_with_null_column(db_conn):
    doc = _seed_doc_with_chunks(db_conn, checksum="6" * 64, contents=["Unembedded chunk."])

    results = search_semantic(db_conn, "embedding", _vector(1.0))

    assert all(r["document_id"] != doc["id"] for r in results)


def test_search_semantic_excludes_superseded_by_default(db_conn):
    doc = _seed_doc_with_chunks(db_conn, checksum="7" * 64, contents=["Embedded chunk."])
    chunks = get_chunks(db_conn, doc["id"])
    write_chunk_embeddings(db_conn, "embedding", [c["id"] for c in chunks], [_vector(1.0)])
    with db_conn.cursor() as cur:
        cur.execute("UPDATE documents SET status = 'SUPERSEDED' WHERE id = %s", (doc["id"],))

    results = search_semantic(db_conn, "embedding", _vector(1.0))

    assert all(r["document_id"] != doc["id"] for r in results)


def test_search_semantic_pinned_document_id_retrieves_superseded(db_conn):
    doc = _seed_doc_with_chunks(db_conn, checksum="8" * 64, contents=["Embedded chunk."])
    chunks = get_chunks(db_conn, doc["id"])
    write_chunk_embeddings(db_conn, "embedding", [c["id"] for c in chunks], [_vector(1.0)])
    with db_conn.cursor() as cur:
        cur.execute("UPDATE documents SET status = 'SUPERSEDED' WHERE id = %s", (doc["id"],))

    results = search_semantic(db_conn, "embedding", _vector(1.0), document_id=doc["id"])

    assert len(results) == 1
    assert results[0]["document_id"] == doc["id"]


class _Spy:
    """Minimal call-recording fake for the embed_local/embed_external
    parameters, matching tests/test_index.py's no-mocking-framework style."""

    def __init__(self, result=None, raises=None):
        self.calls: list[list[str]] = []
        self._result = result
        self._raises = raises

    def __call__(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(texts)
        if self._raises is not None:
            raise self._raises
        return self._result if self._result is not None else [_vector(1.0) for _ in texts]


@pytest.fixture
def cleanup_documents():
    """`search_knowledge` opens its own committed connection (mirroring
    `index_document`/`ingest_document`), so isolation can't rely on a
    rolled-back transaction -- track ids and delete them afterward."""
    ids: list[int] = []
    yield ids
    if not ids:
        return
    conn = psycopg.connect(os.environ["DATABASE_URL"], autocommit=True)
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM documents WHERE id = ANY(%s)", (ids,))
    finally:
        conn.close()


def _seed_committed_doc(
    *, checksum: str, contents: list[str], authority_rank: int = 20, status: str | None = None,
    **draft_overrides,
) -> dict:
    draft = _draft(checksum_sha256=checksum, **draft_overrides)
    conn = psycopg.connect(os.environ["DATABASE_URL"])
    try:
        row = insert_document(conn, draft, authority_rank=authority_rank)
        chunks = [
            ChunkDraft(chunk_index=i, content=content, section=None, page_number=1)
            for i, content in enumerate(contents)
        ]
        insert_chunks(conn, row["id"], chunks)
        if status is not None:
            with conn.cursor() as cur:
                cur.execute("UPDATE documents SET status = %s WHERE id = %s", (status, row["id"]))
        conn.commit()
        return row
    finally:
        conn.close()


def _fetch_committed_chunks(document_id: int) -> list[dict]:
    conn = psycopg.connect(os.environ["DATABASE_URL"], autocommit=True)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, chunk_index FROM document_chunks "
                "WHERE document_id = %s ORDER BY chunk_index",
                (document_id,),
            )
            return [{"id": r[0], "chunk_index": r[1]} for r in cur.fetchall()]
    finally:
        conn.close()


def test_search_knowledge_active_only_by_default(cleanup_documents):
    active_doc = _seed_committed_doc(checksum="a1" * 32, contents=["Antenna gain pattern notes."])
    cleanup_documents.append(active_doc["id"])
    superseded_doc = _seed_committed_doc(
        checksum="a2" * 32, contents=["Antenna gain pattern notes."], status="SUPERSEDED"
    )
    cleanup_documents.append(superseded_doc["id"])

    results = search_knowledge(
        "antenna gain pattern",
        embed_local=_Spy(raises=Exception()),
        embed_external=_Spy(raises=Exception()),
    )

    doc_ids = {r["document_id"] for r in results}
    assert active_doc["id"] in doc_ids
    assert superseded_doc["id"] not in doc_ids


def test_search_knowledge_pinned_document_id_retrieves_superseded(cleanup_documents):
    superseded_doc = _seed_committed_doc(
        checksum="a3" * 32, contents=["Circulator isolation figures."], status="SUPERSEDED"
    )
    cleanup_documents.append(superseded_doc["id"])

    results = search_knowledge(
        "circulator isolation",
        document_id=superseded_doc["id"],
        embed_local=_Spy(raises=Exception()),
        embed_external=_Spy(raises=Exception()),
    )

    assert len(results) == 1
    assert results[0]["document_id"] == superseded_doc["id"]
    assert results[0]["match_type"] == "lexical"


def test_search_knowledge_orders_by_authority_rank_first(cleanup_documents):
    """A lower-authority-rank (higher-tier) document's match must sort ahead
    of a higher-authority-rank document's match even when the higher-rank
    document has the stronger native score."""
    high_authority = _seed_committed_doc(
        checksum="a4" * 32, contents=["Mixer conversion loss specification."], authority_rank=10
    )
    cleanup_documents.append(high_authority["id"])
    low_authority = _seed_committed_doc(
        checksum="a5" * 32,
        contents=["Mixer conversion loss conversion loss conversion loss specification."],
        authority_rank=90,
    )
    cleanup_documents.append(low_authority["id"])

    results = search_knowledge(
        "mixer conversion loss",
        embed_local=_Spy(raises=Exception()),
        embed_external=_Spy(raises=Exception()),
    )

    doc_ids_in_order = [r["document_id"] for r in results]
    assert doc_ids_in_order.index(high_authority["id"]) < doc_ids_in_order.index(
        low_authority["id"]
    )


def test_search_knowledge_surfaces_lexical_only_match(cleanup_documents):
    """A chunk with no embedding on either backend must still surface, via
    match_type='lexical' -- embeddings are never required for search."""
    doc = _seed_committed_doc(checksum="a6" * 32, contents=["Isolator return loss table."])
    cleanup_documents.append(doc["id"])

    results = search_knowledge(
        "isolator return loss",
        embed_local=_Spy(raises=Exception("no local backend configured")),
        embed_external=_Spy(raises=Exception("no OPENAI_API_KEY")),
    )

    assert len(results) == 1
    assert results[0]["document_id"] == doc["id"]
    assert results[0]["match_type"] == "lexical"


def test_search_knowledge_tags_semantic_matches_by_backend(cleanup_documents):
    doc = _seed_committed_doc(
        checksum="a7" * 32, contents=["Attenuator power handling notes.", "Unrelated filler."]
    )
    cleanup_documents.append(doc["id"])
    chunks = _fetch_committed_chunks(doc["id"])
    conn = psycopg.connect(os.environ["DATABASE_URL"])
    try:
        write_chunk_embeddings(conn, "embedding", [chunks[0]["id"]], [_vector(1.0)])
        write_chunk_embeddings(conn, "embedding_local", [chunks[1]["id"]], [_vector(1.0)])
        conn.commit()
    finally:
        conn.close()

    results = search_knowledge(
        "attenuator power handling",
        embed_local=_Spy(result=[_vector(1.0)]),
        embed_external=_Spy(result=[_vector(1.0)]),
    )

    match_types = {r["match_type"] for r in results if r["document_id"] == doc["id"]}
    assert "semantic_external" in match_types
    assert "semantic_local" in match_types


def test_search_knowledge_uses_supplied_query_embedding_without_calling_embed_fn(
    cleanup_documents,
):
    """A caller that already has a query vector (query_embedding_external /
    query_embedding_local) can pass it directly, skipping re-embedding --
    embed_local/embed_external must not be called in that case."""
    doc = _seed_committed_doc(checksum="a8" * 32, contents=["Coupler directivity spec."])
    cleanup_documents.append(doc["id"])
    chunks = _fetch_committed_chunks(doc["id"])
    conn = psycopg.connect(os.environ["DATABASE_URL"])
    try:
        write_chunk_embeddings(conn, "embedding", [chunks[0]["id"]], [_vector(1.0)])
        conn.commit()
    finally:
        conn.close()

    external_spy = _Spy()

    results = search_knowledge(
        "coupler directivity",
        query_embedding_external=_vector(1.0),
        query_embedding_local=_vector(1.0),
        embed_local=_Spy(),
        embed_external=external_spy,
    )

    # Both vectors were supplied directly, so neither embed_* fn is called.
    assert external_spy.calls == []
    match_types = {r["match_type"] for r in results if r["document_id"] == doc["id"]}
    assert "semantic_external" in match_types


def test_search_knowledge_registered_as_agent_tool():
    import agent.main as agent_main

    tool_names = {tool.name for tool in agent_main.principal.tools}
    assert "search_knowledge" in tool_names


def test_search_knowledge_registered_as_mcp_tool():
    import asyncio

    import mcp_server.server as mcp_module

    tools = asyncio.run(mcp_module.mcp.list_tools())
    assert "search_knowledge" in {t.name for t in tools}


# ---------------------------------------------------------------------------
# Issue #37: search_design_records (design/decision-record retrieval).
#
# search_design_records is a thin wrapper around search_knowledge, pinned to
# source_type="design_record" -- these tests confirm the filter actually
# excludes other source types, not the underlying ranking/match-type
# behavior already covered above for search_knowledge itself.
# ---------------------------------------------------------------------------


def test_search_design_records_returns_design_record_and_excludes_reference_doc(
    cleanup_documents,
):
    """Seed one design_record document and one plain datasheet with
    overlapping keywords -- search_design_records must return only the
    design record, even though both would match a plain search_knowledge
    lexical query."""
    design_doc = _seed_committed_doc(
        checksum="d1" * 32,
        contents=[
            "Patch antenna design decision: patch selected over dipole for "
            "conformal mounting; dipole rejected for bend sensitivity."
        ],
        source_type=SourceType.DESIGN_RECORD,
    )
    cleanup_documents.append(design_doc["id"])
    reference_doc = _seed_committed_doc(
        checksum="d2" * 32,
        contents=[
            "Patch antenna datasheet: dipole comparison chart and gain "
            "specifications for the reference part."
        ],
        source_type=SourceType.DATASHEET,
    )
    cleanup_documents.append(reference_doc["id"])

    results = search_design_records(
        "patch antenna dipole",
        embed_local=_Spy(raises=Exception()),
        embed_external=_Spy(raises=Exception()),
    )

    doc_ids = {r["document_id"] for r in results}
    assert design_doc["id"] in doc_ids
    assert reference_doc["id"] not in doc_ids

    # Also confirm the plain search_knowledge query (no source_types filter)
    # would have matched both -- proving the exclusion above is the filter
    # doing its job, not just the two documents failing to overlap.
    unfiltered = search_knowledge(
        "patch antenna dipole",
        embed_local=_Spy(raises=Exception()),
        embed_external=_Spy(raises=Exception()),
    )
    unfiltered_doc_ids = {r["document_id"] for r in unfiltered}
    assert design_doc["id"] in unfiltered_doc_ids
    assert reference_doc["id"] in unfiltered_doc_ids


def test_search_design_records_returns_empty_when_no_design_record_matches(
    cleanup_documents,
):
    reference_doc = _seed_committed_doc(
        checksum="d3" * 32,
        contents=["Klystron amplifier chain design notes and gain figures."],
        source_type=SourceType.DATASHEET,
    )
    cleanup_documents.append(reference_doc["id"])

    results = search_design_records(
        "klystron amplifier chain",
        embed_local=_Spy(raises=Exception()),
        embed_external=_Spy(raises=Exception()),
    )

    assert results == []


def test_search_design_records_excludes_superseded_by_default(cleanup_documents):
    design_doc = _seed_committed_doc(
        checksum="d4" * 32,
        contents=["Decision: circulator isolation target set to 20 dB minimum."],
        source_type=SourceType.DESIGN_RECORD,
        status="SUPERSEDED",
    )
    cleanup_documents.append(design_doc["id"])

    results = search_design_records(
        "circulator isolation target",
        embed_local=_Spy(raises=Exception()),
        embed_external=_Spy(raises=Exception()),
    )

    assert results == []


def test_search_design_records_registered_as_agent_tool():
    import agent.main as agent_main

    tool_names = {tool.name for tool in agent_main.principal.tools}
    assert "search_design_records" in tool_names


def test_search_design_records_registered_as_mcp_tool():
    import asyncio

    import mcp_server.server as mcp_module

    tools = asyncio.run(mcp_module.mcp.list_tools())
    assert "search_design_records" in {t.name for t in tools}
