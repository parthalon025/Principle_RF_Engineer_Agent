"""Retrieval-quality metrics and the golden-query harness (issue #144).

Pure functions over ranked result lists, so these run without a database.
The gate that drives them against the real corpus is tests/test_retrieval_gate.py,
which needs Postgres and therefore only runs in CI.

The point of the whole harness: the existing suite checks that retrieval
*runs*, not that it returns *good* results. Without a fixed set of questions
whose right answers are known, a change to the embedding model, the chunking,
or the ranking cannot be told apart from a regression -- every test stays
green either way.
"""

import json

import pytest

from verification.retrieval_eval import (
    EvaluationReport,
    GoldenQuery,
    QueryResult,
    evaluate_retrieval,
    load_golden_queries,
    precision_at_k,
    recall_at_k,
    reciprocal_rank,
)

# --- the metrics ----------------------------------------------------------


def test_recall_is_the_fraction_of_expected_documents_found():
    assert recall_at_k(["a", "b", "c"], {"a", "d"}, k=3) == pytest.approx(0.5)
    assert recall_at_k(["a", "d"], {"a", "d"}, k=3) == pytest.approx(1.0)
    assert recall_at_k(["x", "y"], {"a"}, k=3) == pytest.approx(0.0)


def test_recall_only_counts_the_top_k():
    """A correct answer ranked 5th is not found by someone reading the top 3."""
    retrieved = ["x", "y", "z", "w", "a"]
    assert recall_at_k(retrieved, {"a"}, k=3) == pytest.approx(0.0)
    assert recall_at_k(retrieved, {"a"}, k=5) == pytest.approx(1.0)


def test_recall_ignores_duplicate_hits_on_the_same_document():
    """Several chunks of one document is still one document found."""
    assert recall_at_k(["a", "a", "a"], {"a", "b"}, k=3) == pytest.approx(0.5)


def test_recall_with_no_expected_documents_is_undefined_not_zero():
    """A query with no known answer cannot score -- scoring it 0 would drag
    the aggregate down for a fixture bug rather than a retrieval problem."""
    with pytest.raises(ValueError, match="expected"):
        recall_at_k(["a"], set(), k=3)


def test_precision_is_the_fraction_of_returned_results_that_are_relevant():
    assert precision_at_k(["a", "x", "y"], {"a"}, k=3) == pytest.approx(1 / 3)
    assert precision_at_k(["a", "b"], {"a", "b"}, k=2) == pytest.approx(1.0)


def test_precision_divides_by_results_actually_returned():
    """Returning 2 results when k=5 should not be punished as if 3 were wrong."""
    assert precision_at_k(["a", "b"], {"a", "b"}, k=5) == pytest.approx(1.0)


def test_precision_of_an_empty_result_list_is_zero():
    assert precision_at_k([], {"a"}, k=5) == pytest.approx(0.0)


def test_reciprocal_rank_rewards_the_first_correct_hit_being_early():
    assert reciprocal_rank(["a", "x"], {"a"}) == pytest.approx(1.0)
    assert reciprocal_rank(["x", "a"], {"a"}) == pytest.approx(0.5)
    assert reciprocal_rank(["x", "y", "a"], {"a"}) == pytest.approx(1 / 3)
    assert reciprocal_rank(["x", "y"], {"a"}) == pytest.approx(0.0)


# --- the harness ----------------------------------------------------------


QUERIES = [
    GoldenQuery(
        query_id="q1",
        query="metamaterial antenna for army aviation",
        expected_documents=frozenset({"army_sbir"}),
        notes="",
    ),
    GoldenQuery(
        query_id="q2",
        query="patent claims about magnetic elements",
        expected_documents=frozenset({"patent"}),
        notes="",
    ),
]


def _search(mapping):
    """Build a fake search function returning a fixed ranked list per query."""
    return lambda query, limit: mapping.get(query, [])[:limit]


def test_evaluate_scores_each_query_and_aggregates():
    report = evaluate_retrieval(
        QUERIES,
        _search(
            {
                "metamaterial antenna for army aviation": ["army_sbir", "patent"],
                "patent claims about magnetic elements": ["ieee", "patent"],
            }
        ),
        k=5,
    )
    assert isinstance(report, EvaluationReport)
    assert [r.query_id for r in report.results] == ["q1", "q2"]
    assert report.results[0].recall == pytest.approx(1.0)
    assert report.results[1].recall == pytest.approx(1.0)
    assert report.mean_recall == pytest.approx(1.0)
    # q1's answer is first, q2's is second -> MRR = (1 + 1/2) / 2
    assert report.mean_reciprocal_rank == pytest.approx(0.75)


def test_a_query_that_finds_nothing_drags_the_aggregate_down():
    report = evaluate_retrieval(
        QUERIES,
        _search({"metamaterial antenna for army aviation": ["army_sbir"]}),
        k=5,
    )
    assert report.mean_recall == pytest.approx(0.5)
    assert [r.query_id for r in report.failures(0.99)] == ["q2"]


def test_the_report_names_which_queries_fell_below_the_threshold():
    """A gate failure has to say WHICH question stopped working, or nobody
    can act on it."""
    report = evaluate_retrieval(
        QUERIES,
        _search(
            {
                "metamaterial antenna for army aviation": ["army_sbir"],
                "patent claims about magnetic elements": ["x", "y"],
            }
        ),
        k=5,
    )
    failures = report.failures(0.5)
    assert len(failures) == 1
    assert failures[0].query_id == "q2"
    assert failures[0].expected == frozenset({"patent"})
    assert list(failures[0].retrieved) == ["x", "y"]


def test_report_summary_is_human_readable_and_names_failures():
    report = evaluate_retrieval(
        QUERIES, _search({"metamaterial antenna for army aviation": ["army_sbir"]}), k=5
    )
    summary = report.summary(threshold=0.99)
    assert "mean recall@5" in summary
    assert "q2" in summary
    assert "patent" in summary


def test_meets_threshold_is_the_gate_decision():
    good = evaluate_retrieval(
        QUERIES,
        _search(
            {
                "metamaterial antenna for army aviation": ["army_sbir"],
                "patent claims about magnetic elements": ["patent"],
            }
        ),
        k=5,
    )
    assert good.meets_threshold(1.0)
    bad = evaluate_retrieval(
        QUERIES, _search({"metamaterial antenna for army aviation": ["army_sbir"]}), k=5
    )
    assert not bad.meets_threshold(0.99)
    assert bad.meets_threshold(0.5)


def test_evaluate_rejects_an_empty_query_set():
    """An empty fixture would trivially pass any threshold -- the most
    dangerous way for a quality gate to fail."""
    with pytest.raises(ValueError, match="at least one"):
        evaluate_retrieval([], _search({}), k=5)


def test_duplicate_query_ids_are_rejected():
    dupe = [QUERIES[0], QUERIES[0]]
    with pytest.raises(ValueError, match="duplicate"):
        evaluate_retrieval(dupe, _search({}), k=5)


# --- the fixture file -----------------------------------------------------


def test_load_golden_queries_reads_the_shipped_fixture():
    queries = load_golden_queries()
    assert len(queries) >= 5
    assert all(isinstance(q, GoldenQuery) for q in queries)
    assert all(q.expected_documents for q in queries)


def test_shipped_fixture_has_unique_ids_and_real_corpus_targets():
    """Every expected document names a file that actually exists in
    knowledge/corpus/, so the fixture cannot rot silently against a renamed
    or deleted corpus file."""
    from pathlib import Path

    corpus_dir = Path(__file__).resolve().parent.parent / "knowledge" / "corpus"
    corpus = {p.stem for p in corpus_dir.glob("*.txt")}
    queries = load_golden_queries()
    assert len({q.query_id for q in queries}) == len(queries)
    for q in queries:
        for expected in q.expected_documents:
            assert expected in corpus, f"{q.query_id} expects unknown corpus file {expected!r}"


def test_load_golden_queries_accepts_an_explicit_path(tmp_path):
    path = tmp_path / "queries.json"
    path.write_text(
        json.dumps(
            [
                {
                    "query_id": "x",
                    "query": "anything",
                    "expected_documents": ["army_sbir_a214-029"],
                    "notes": "n",
                }
            ]
        ),
        encoding="utf-8",
    )
    queries = load_golden_queries(path)
    assert queries[0].query_id == "x"
    assert queries[0].expected_documents == frozenset({"army_sbir_a214-029"})


def test_a_query_result_is_immutable():
    """Report rows are evidence; nothing downstream should be able to edit a
    score after the fact."""
    report = evaluate_retrieval(
        QUERIES[:1], _search({"metamaterial antenna for army aviation": ["army_sbir"]}), k=5
    )
    with pytest.raises((AttributeError, TypeError)):
        report.results[0].recall = 0.0  # type: ignore[misc]
    assert isinstance(report.results[0], QueryResult)
