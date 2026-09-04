"""Retrieval-quality evaluation for the knowledge pipeline (issue #144).

The existing test suite checks that search *runs*. It does not check that
search returns *good answers*, and those are different things: you can change
the embedding model, the chunking strategy or the ranking, destroy retrieval
quality, and watch every test stay green -- because no test knows what a good
result looks like.

This module supplies the missing half: a fixed set of questions whose right
answers are known (the golden queries), three standard metrics, and a
threshold a CI gate can fail on.

In plain terms: a golden query is a question plus the documents that ought to
come back for it. Run all of them, measure how often the right document
actually appears, and refuse to ship a change that makes that number worse.

The three metrics, in plain terms:

- **Recall@k** -- of the documents that should have come back, what fraction
  appeared in the top k? This is the one the gate uses: for this corpus,
  missing the right document entirely is the failure that matters.
- **Precision@k** -- of the results returned, what fraction were relevant?
  Reported for context, not gated: a chunk-level search over a small corpus
  legitimately returns near-miss chunks alongside the right one.
- **Reciprocal rank** -- one divided by the position of the first correct
  hit. Tracks whether right answers are drifting down the list, which recall
  alone hides until they fall off the end.

Scoring is at *document* granularity, not chunk: several chunks of the right
document is still one document found, and which chunk of a paper answered a
question is not a stable thing to assert.

Pure functions over ranked lists -- no database and no embedding model, so
these run anywhere. `tests/test_retrieval_gate.py` drives them against the
real corpus and needs Postgres, so it runs in CI.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

__all__ = [
    "DEFAULT_GOLDEN_QUERIES_PATH",
    "EvaluationReport",
    "GoldenQuery",
    "QueryResult",
    "SearchFn",
    "evaluate_retrieval",
    "load_golden_queries",
    "precision_at_k",
    "recall_at_k",
    "reciprocal_rank",
]

DEFAULT_GOLDEN_QUERIES_PATH = Path(__file__).resolve().parent / "golden_queries.json"

#: A search callable: (query_text, limit) -> ranked document identifiers,
#: best first. The gate adapts `knowledge.search.search_knowledge` to this.
SearchFn = Callable[[str, int], Sequence[str]]


def _dedupe(retrieved: Sequence[str], k: int) -> list[str]:
    """Top-k document ids, first occurrence kept, duplicates dropped."""
    seen: list[str] = []
    for doc in retrieved[:k]:
        if doc not in seen:
            seen.append(doc)
    return seen


def recall_at_k(retrieved: Sequence[str], expected: Iterable[str], k: int) -> float:
    """Fraction of `expected` documents appearing in the top `k` of `retrieved`.

    Raises `ValueError` on an empty `expected` set: a query with no known
    answer cannot be scored, and scoring it 0 would drag the aggregate down
    for a fixture bug rather than a retrieval problem.
    """
    wanted = set(expected)
    if not wanted:
        raise ValueError(
            "a golden query must name at least one expected document; "
            "an unanswerable query cannot be scored"
        )
    found = wanted.intersection(_dedupe(retrieved, k))
    return len(found) / len(wanted)


def precision_at_k(retrieved: Sequence[str], expected: Iterable[str], k: int) -> float:
    """Fraction of the returned top-`k` documents that were expected.

    Divides by how many results actually came back, not by `k`: returning two
    correct results when `k=5` is not two-fifths right.
    """
    wanted = set(expected)
    top = _dedupe(retrieved, k)
    if not top:
        return 0.0
    return len([doc for doc in top if doc in wanted]) / len(top)


def reciprocal_rank(retrieved: Sequence[str], expected: Iterable[str]) -> float:
    """1 / (rank of the first expected document), or 0.0 if none appears."""
    wanted = set(expected)
    for position, doc in enumerate(_dedupe(retrieved, len(retrieved)), start=1):
        if doc in wanted:
            return 1.0 / position
    return 0.0


@dataclass(frozen=True)
class GoldenQuery:
    """One question, and the documents that ought to answer it.

    `expected_documents` holds corpus file stems (e.g. `army_sbir_a214-029`),
    which is what the gate maps retrieved documents back to.
    """

    query_id: str
    query: str
    expected_documents: frozenset[str]
    notes: str = ""


@dataclass(frozen=True)
class QueryResult:
    """One golden query's scored outcome. Frozen: a score is evidence."""

    query_id: str
    query: str
    expected: frozenset[str]
    retrieved: tuple[str, ...]
    recall: float
    precision: float
    reciprocal_rank: float


@dataclass(frozen=True)
class EvaluationReport:
    """Every query's result plus the aggregates a gate decides on."""

    k: int
    results: tuple[QueryResult, ...]

    def __post_init__(self) -> None:
        # Every aggregate below divides by len(results). An empty report would
        # raise ZeroDivisionError from a property, far from the cause -- and a
        # gate built on one would be silently meaningless. Refuse it here.
        if not self.results:
            raise ValueError(
                "an EvaluationReport needs at least one scored query; an empty "
                "report has no meaningful aggregate to gate on"
            )

    @property
    def mean_recall(self) -> float:
        return sum(r.recall for r in self.results) / len(self.results)

    @property
    def mean_precision(self) -> float:
        return sum(r.precision for r in self.results) / len(self.results)

    @property
    def mean_reciprocal_rank(self) -> float:
        return sum(r.reciprocal_rank for r in self.results) / len(self.results)

    def failures(self, threshold: float) -> tuple[QueryResult, ...]:
        """Queries whose own recall fell below `threshold`."""
        return tuple(r for r in self.results if r.recall < threshold)

    def meets_threshold(self, threshold: float) -> bool:
        """Whether mean recall clears `threshold` -- the gate decision."""
        return self.mean_recall >= threshold

    def summary(self, threshold: float | None = None) -> str:
        """A report a failing CI job can be read from without rerunning it.

        Names the individual queries that fell short, what they expected and
        what they got -- a bare aggregate tells nobody what to fix.
        """
        lines = [
            f"mean recall@{self.k}:    {self.mean_recall:.3f}",
            f"mean precision@{self.k}: {self.mean_precision:.3f}",
            f"mean reciprocal rank:  {self.mean_reciprocal_rank:.3f}",
            f"queries:               {len(self.results)}",
        ]
        if threshold is not None:
            failures = self.failures(threshold)
            if failures:
                lines.append(f"\nbelow recall {threshold:.2f}:")
                for r in failures:
                    lines.append(
                        f"  {r.query_id}: {r.query!r}\n"
                        f"    expected: {sorted(r.expected)}\n"
                        f"    got:      {list(r.retrieved) or '(nothing)'}"
                    )
            else:
                lines.append(f"\nevery query cleared recall {threshold:.2f}")
        return "\n".join(lines)


def evaluate_retrieval(
    queries: Sequence[GoldenQuery], search: SearchFn, k: int = 5
) -> EvaluationReport:
    """Run every golden query through `search` and score the results.

    Rejects an empty query set: an empty fixture clears any threshold, which
    is the most dangerous way for a quality gate to fail -- silently.
    """
    if not queries:
        raise ValueError(
            "at least one golden query is required; an empty fixture would "
            "clear every threshold without testing anything"
        )
    ids = [q.query_id for q in queries]
    if len(set(ids)) != len(ids):
        duplicates = sorted({i for i in ids if ids.count(i) > 1})
        raise ValueError(f"duplicate golden-query ids: {duplicates}")

    results = []
    for query in queries:
        retrieved = list(search(query.query, k))
        results.append(
            QueryResult(
                query_id=query.query_id,
                query=query.query,
                expected=query.expected_documents,
                retrieved=tuple(retrieved),
                recall=recall_at_k(retrieved, query.expected_documents, k),
                precision=precision_at_k(retrieved, query.expected_documents, k),
                reciprocal_rank=reciprocal_rank(retrieved, query.expected_documents),
            )
        )
    return EvaluationReport(k=k, results=tuple(results))


def load_golden_queries(path: Path | None = None) -> tuple[GoldenQuery, ...]:
    """Load the golden-query fixture (JSON list of query objects)."""
    source = Path(path) if path is not None else DEFAULT_GOLDEN_QUERIES_PATH
    raw = json.loads(source.read_text(encoding="utf-8"))
    return tuple(
        GoldenQuery(
            query_id=entry["query_id"],
            query=entry["query"],
            expected_documents=frozenset(entry["expected_documents"]),
            notes=entry.get("notes", ""),
        )
        for entry in raw
    )
