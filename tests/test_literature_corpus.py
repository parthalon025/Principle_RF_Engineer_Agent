"""Ticket #33: ingest the public metaferrite/conformal-antenna literature
corpus (knowledge/corpus/) and verify it's retrievable with correct
provenance.

Two layers, matching this repo's existing split:

- `test_search.py`-style tests using `db_conn` (real Postgres, rolled back
  on teardown) that seed a chunk via `knowledge.db.insert_document` /
  `insert_chunks` directly and verify `search_lexical` retrieval plus the
  `source_type` -> provenance-tier mapping (`knowledge.provenance`). The
  seeded content is not fabricated -- it's copied verbatim from
  `knowledge/corpus/army_sbir_a214-029.txt`, one of the files this ticket's
  ingestion run actually fetched from armysbir.army.mil.
- `test_ingest.py`/`test_read.py`-style tests using the `cleanup_documents`
  fixture (ingest_document/index_document/search_knowledge each commit
  their own connection, so isolation can't rely on db_conn's rollback)
  that run the real corpus file through `ingest_document` end to end and
  confirm it's readable and searchable.
"""

from __future__ import annotations

import os
from pathlib import Path

import psycopg
import pytest
from dotenv import load_dotenv

from knowledge.db import insert_chunks, insert_document, search_lexical
from knowledge.index import index_document
from knowledge.ingest import ingest_document
from knowledge.models import ChunkDraft, Classification, DocumentDraft, SourceType
from knowledge.provenance import LITERATURE_SUPPORTED, default_authority_rank, provenance_tier_for
from knowledge.read import read_document
from knowledge.search import search_knowledge

load_dotenv()

_CORPUS_DIR = Path(__file__).resolve().parent.parent / "knowledge" / "corpus"

# A real excerpt copied verbatim from knowledge/corpus/army_sbir_a214-029.txt
# (fetched live from https://armysbir.army.mil/topics/metamaterial-based-antenna/
# as part of this ticket's ingestion run) -- not fabricated text.
_ARMY_SBIR_OBJECTIVE_EXCERPT = (
    "The SBIR objective is to create an antenna design for satellite communication "
    "bands, including Ku, K, and Ka bands, based on metamaterials to decrease size, "
    "weight, performance and cost (SWaP-C) and increase antenna bandwidth, improve "
    "signal reception, and provide a higher gain. The antenna design would be "
    "developed for Army Aviation platforms with a focus on a low profile and a "
    "conformal fit, while maintaining optimal performance to allow installation on "
    "non-ideal surfaces encountered in the adverse aviation environment."
)


def test_corpus_source_files_exist_with_source_url_citation():
    """Every corpus file under knowledge/corpus/ carries a `Source URL:` line
    citing where it was actually fetched from (ticket #33's no-fabrication
    requirement)."""
    files = sorted(_CORPUS_DIR.glob("*.txt"))
    assert len(files) >= 5
    for f in files:
        first_line = f.read_text(encoding="utf-8").splitlines()[0]
        assert first_line.startswith("Source URL: https://")


def test_paper_source_type_resolves_to_literature_supported():
    """CONTEXT.md / knowledge/provenance.py: standard/textbook/paper sit at
    the LITERATURE-SUPPORTED tier. This corpus is ingested as source_type
    "paper" (no dedicated "patent"/"government-solicitation" SourceType
    exists -- see knowledge/models.py's fixed enum), so this is the mapping
    that governs every document in it."""
    assert provenance_tier_for(SourceType.PAPER) == LITERATURE_SUPPORTED


def _draft(checksum: str) -> DocumentDraft:
    return DocumentDraft(
        title="Metamaterial Based Antenna – Army SBIR|STTR Program (excerpt)",
        source_type=SourceType.PAPER,
        classification=Classification.PUBLIC,
        license="public-domain-us-government-work",
        checksum_sha256=checksum,
        source_uri="https://armysbir.army.mil/topics/metamaterial-based-antenna/",
        metadata={"classification": "PUBLIC", "extraction_status": "ok"},
    )


def test_ingested_army_sbir_excerpt_is_retrievable_via_lexical_search(db_conn):
    """Seeds a chunk (via knowledge.db directly, inside db_conn's
    transaction) with the real Army SBIR A214-029 objective text and
    confirms knowledge.db.search_lexical finds it for a representative
    query -- the acceptance criterion's "search_knowledge returns relevant
    chunks" requirement, exercised at the db layer that search_knowledge
    itself composes."""
    authority_rank = default_authority_rank(SourceType.PAPER)
    draft = _draft(checksum="c33" * 21 + "c")
    row = insert_document(db_conn, draft, authority_rank=authority_rank)
    insert_chunks(
        db_conn,
        row["id"],
        [
            ChunkDraft(
                chunk_index=0,
                content=_ARMY_SBIR_OBJECTIVE_EXCERPT,
                section="Topic Objective",
                page_number=None,
            )
        ],
    )

    results = search_lexical(db_conn, "conformal metamaterial antenna Army")

    matches = [r for r in results if r["document_id"] == row["id"]]
    assert len(matches) == 1
    assert matches[0]["chunk_index"] == 0
    assert matches[0]["status"] == "ACTIVE"
    # authority_rank on the stored row must match what a "paper" source
    # type defaults to (LITERATURE-SUPPORTED tier -- rank 40).
    assert row["authority_rank"] == authority_rank == 40


@pytest.fixture
def cleanup_documents():
    """Tracks document ids created via ingest_document (which commits its
    own connection) and deletes them afterward -- mirrors
    tests/test_ingest.py and tests/test_read.py."""
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


def test_real_corpus_file_ingests_and_is_readable(cleanup_documents):
    """Runs one of the actually-fetched corpus files
    (sbir_award_136890_si2_technologies.txt, fetched live from
    https://www.sbir.gov/awards/136890) through the real ingest_document
    pipeline and confirms read_document surfaces it with PUBLIC
    classification and the "paper" source type."""
    corpus_file = _CORPUS_DIR / "sbir_award_136890_si2_technologies.txt"
    assert corpus_file.exists()

    result = ingest_document(
        file_path=str(corpus_file),
        source_type="paper",
        license="public-domain-us-government-work",
        classification="PUBLIC",
    )
    cleanup_documents.append(result["document_id"])

    assert result["status"] in {"ingested", "duplicate"}
    document_id = result["document_id"]

    read = read_document(document_id)
    assert read["status"] == "ACTIVE"
    assert read["source_type"] == "paper"
    assert read["classification"] == "PUBLIC"
    assert provenance_tier_for(SourceType(read["source_type"])) == LITERATURE_SUPPORTED
    assert any(
        "SI2" in c["content"] or "metaferrite" in c["content"].lower() for c in read["chunks"]
    )


def test_real_corpus_file_index_document_fails_without_embedding_credential(cleanup_documents):
    """Documents this environment's real constraint: no OPENAI_API_KEY and
    no local embedding backend is configured, so index_document's embedding
    step legitimately fails for a PUBLIC document -- called anyway so the
    failure is on record, per the ticket. This must not be silently
    swallowed; it must actually raise."""
    if os.environ.get("OPENAI_API_KEY") or os.environ.get("LOCAL_LLM_BASE_URL"):
        pytest.skip("an embedding backend is configured in this environment")

    corpus_file = _CORPUS_DIR / "sbir_award_145942_metamaterials_inc.txt"
    result = ingest_document(
        file_path=str(corpus_file),
        source_type="paper",
        license="public-domain-us-government-work",
        classification="PUBLIC",
    )
    # Re-running this test after this ticket's own corpus ingestion has
    # already committed this exact file (same checksum) is expected to
    # return "duplicate", pointing at the already-ingested document_id
    # rather than creating a new row -- either way, exercise index_document
    # against a real, chunked document_id.
    if result["status"] == "duplicate":
        document_id = result["document_id"]
    else:
        cleanup_documents.append(result["document_id"])
        assert result["chunk_count"] >= 1
        document_id = result["document_id"]
    assert len(read_document(document_id)["chunks"]) >= 1

    with pytest.raises(Exception) as excinfo:
        index_document(document_id)
    # Falls back from the unconfigured local backend to the external one,
    # which then fails loudly on the missing credential -- not a silent
    # no-op and not a fabricated success.
    assert "credential" in str(excinfo.value).lower() or "api_key" in str(excinfo.value).lower()


def test_search_knowledge_finds_real_corpus_content_via_lexical_match(cleanup_documents):
    """End-to-end acceptance check: search_knowledge (the tool-facing
    function) returns a chunk from the real, committed corpus for the
    ticket's representative query, via match_type="lexical" -- the only
    mode available without an embedding credential."""
    # The patent text is the one corpus document whose (English-stemmed)
    # vocabulary covers every term in the query below -- "mounted" stems to
    # the same root as "mounting" -- so it's the one guaranteed to match
    # plainto_tsquery's AND-of-terms lexical search.
    corpus_file = _CORPUS_DIR / "us_patent_11005187B2.txt"
    result = ingest_document(
        file_path=str(corpus_file),
        source_type="paper",
        license="public-domain-us-government-work",
        classification="PUBLIC",
    )
    # See test_real_corpus_file_index_document_fails_without_embedding_credential:
    # re-running against an already-ingested corpus file returns "duplicate".
    if result["status"] != "duplicate":
        cleanup_documents.append(result["document_id"])
        assert result["chunk_count"] >= 1
    document_id = result["document_id"]

    results = search_knowledge(
        "flexible metamaterial antenna conformal mounting",
        document_id=document_id,
    )

    assert len(results) >= 1
    assert all(r["match_type"] == "lexical" for r in results)
    assert results[0]["document_id"] == document_id
