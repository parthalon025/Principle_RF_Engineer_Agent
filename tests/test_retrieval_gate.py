"""The retrieval quality gate (issue #144).

Ingests the real corpus under `knowledge/corpus/`, runs every golden query in
`verification/golden_queries.json` through the real `search_knowledge`, and
fails if mean recall falls below the threshold.

This is the test the issue exists for. The rest of the suite proves retrieval
*runs*; this one proves it still *finds the right documents*, so a change to
chunking, ranking or the embedding model can be told apart from a regression
instead of sailing through a green suite.

Needs Postgres, so it runs in CI (which provides a pgvector service container)
and errors locally on a missing DATABASE_URL like every other persistence
suite here.

**What this measures, honestly.** CI configures no embedding backend, so
`search_knowledge`'s two semantic paths degrade to None and only the lexical
path runs (`knowledge/search.py::_query_vector` swallows the failure by
design, so lexical search is never blocked by a missing embedding model).
This gate therefore measures LEXICAL retrieval quality in CI, and lexical plus
semantic anywhere an embedding backend is configured. That is a real floor,
not the whole picture -- and it is the half that a chunking or ranking change
can break.

It is also why the golden queries read as keyword strings rather than natural
questions: lexical search is `plainto_tsquery`, an AND over every term, so a
natural-language query only matches if a single chunk happens to contain all
of its content words. Every query here was verified against the corpus to be
lexically reachable before being committed. Answering natural-language
questions is what the semantic path is for, and gating that needs an
embedding backend in CI -- worth doing, and not in this ticket's scope.
"""

from __future__ import annotations

import os
from pathlib import Path

import psycopg
import pytest
from dotenv import load_dotenv

from knowledge.ingest import ingest_document
from knowledge.search import search_knowledge
from verification.retrieval_eval import evaluate_retrieval, load_golden_queries

load_dotenv()

_CORPUS_DIR = Path(__file__).resolve().parent.parent / "knowledge" / "corpus"

#: Results considered per query. Five is what a reader actually looks at.
K = 5

#: Gate floor for mean recall@K. Every shipped golden query was verified
#: lexically reachable against the corpus, so the expected value here is 1.0.
#: The floor sits below that deliberately: it absorbs ts_rank ordering jitter
#: (a hit sliding out of the top K when many chunks match) without going red,
#: while still catching any real collapse in retrieval. Raise it toward 1.0
#: once CI has established a stable baseline across a few runs.
MIN_MEAN_RECALL = 0.8


@pytest.fixture
def corpus_documents():
    """Ingest every corpus file once, yield {document_id: corpus file stem}.

    `ingest_document` commits its own connection, so cleanup is explicit
    rather than a transaction rollback -- same pattern as
    tests/test_literature_corpus.py. A file already present from an earlier
    test returns status "duplicate"; its id is still needed for the mapping
    but must not be deleted here, since this test did not create it.
    """
    mapping: dict[int, str] = {}
    created: list[int] = []
    for path in sorted(_CORPUS_DIR.glob("*.txt")):
        result = ingest_document(
            file_path=str(path),
            source_type="paper",
            license="public-domain-us-government-work",
            classification="PUBLIC",
        )
        mapping[result["document_id"]] = path.stem
        if result["status"] != "duplicate":
            created.append(result["document_id"])

    yield mapping

    if created:
        conn = psycopg.connect(os.environ["DATABASE_URL"], autocommit=True)
        try:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM documents WHERE id = ANY(%s)", (created,))
        finally:
            conn.close()


def _search_fn(document_stems: dict[int, str]):
    """Adapt `search_knowledge` to the harness's (query, limit) -> [doc ids].

    Chunks are collapsed to their documents, first occurrence kept, so a
    document matching on five chunks counts once and does not crowd the
    ranked list -- scoring is at document granularity (see
    verification/retrieval_eval.py).
    """

    def search(query: str, limit: int) -> list[str]:
        ordered: list[str] = []
        # Ask for more chunks than documents wanted, since several chunks of
        # one document collapse to a single entry.
        for row in search_knowledge(query, limit=limit * 10):
            stem = document_stems.get(row["document_id"])
            if stem is not None and stem not in ordered:
                ordered.append(stem)
        return ordered[:limit]

    return search


def test_retrieval_meets_the_recall_gate(corpus_documents):
    queries = load_golden_queries()
    report = evaluate_retrieval(queries, _search_fn(corpus_documents), k=K)

    assert report.meets_threshold(MIN_MEAN_RECALL), (
        "knowledge-base retrieval quality regressed below the gate.\n\n"
        + report.summary(threshold=MIN_MEAN_RECALL)
        + "\n\nIf this change was intended (a new embedding model, a different "
        "chunking strategy), update verification/golden_queries.json and this "
        "threshold deliberately -- do not lower the gate to make a regression "
        "pass."
    )


def test_every_golden_query_finds_at_least_one_expected_document(corpus_documents):
    """Recall averaged across queries can hide one question breaking
    completely. This catches that: no query may return nothing relevant."""
    queries = load_golden_queries()
    report = evaluate_retrieval(queries, _search_fn(corpus_documents), k=K)
    dead = [r.query_id for r in report.results if r.recall == 0.0]
    assert not dead, (
        f"these golden queries found none of their expected documents: {dead}\n\n"
        + report.summary(threshold=MIN_MEAN_RECALL)
    )


def test_the_gate_reports_its_numbers(corpus_documents, capsys):
    """Always print the measured numbers, passing or failing, so a CI log
    records the baseline instead of only saying 'ok'."""
    queries = load_golden_queries()
    report = evaluate_retrieval(queries, _search_fn(corpus_documents), k=K)
    with capsys.disabled():
        print("\n--- knowledge-base retrieval quality ---")
        print(report.summary(threshold=MIN_MEAN_RECALL))
    assert len(report.results) == len(queries)
