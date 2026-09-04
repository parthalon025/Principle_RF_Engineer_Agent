"""Verification corpus: a golden-query recall@k / zero-result-rate gate for
`knowledge.search.search_knowledge`, run against the five real files already
committed under `knowledge/corpus/` (ticket #33 / `tests/test_literature_
corpus.py`).

This is deliberately the minimum useful version of the "verification
corpus" gap CONTEXT.md's "Correctness bar" section names: no golden-query
fixture existed anywhere in this repo before this file (checked by grep),
so today a broken GIN index, a wrong `ACTIVE`-only default, or an
authority-rank-ordering bug that buries the one real match would pass
`uv run pytest` silently. This test would catch any of those.

Query design: each entry in GOLDEN_QUERIES is a short phrase whose every
word appears -- verbatim, or as a shared English stem (`plainto_tsquery`'s
matching unit) -- in exactly one of the five corpus files, confirmed by
direct grep against the real files before writing this docstring, not
assumed from memory. `plainto_tsquery` is an AND of terms, so as long as at
least one query term is absent from every other document, cross-document
false positives are structurally ruled out even when other terms in the
same query are shared vocabulary (e.g. "helicopters" also appears -- as the
singular "helicopter" -- in army_sbir_a214-029.txt, but that document lacks
"SATCOM"/"RHCP", so the three-term AND still resolves to exactly one file).

No embedding credential is configured in this environment (see
test_real_corpus_file_index_document_fails_without_embedding_credential),
so every result here necessarily comes back `match_type="lexical"` --
this gate covers `search_knowledge`'s lexical path only, which is also the
only path guaranteed to run without a paid API key or a local embedding
backend, consistent with this repo's software-only/open-source-only
constraint on new work in this area.
"""

from __future__ import annotations

from pathlib import Path

from knowledge.ingest import ingest_document
from knowledge.models import SourceType
from knowledge.search import search_knowledge

_CORPUS_DIR = Path(__file__).resolve().parent.parent / "knowledge" / "corpus"

# (query, expected corpus filename) -- see module docstring for how these
# were chosen and verified.
GOLDEN_QUERIES: list[tuple[str, str]] = [
    ("AH-64E CH-47F UH-60M helicopter", "army_sbir_a214-029.txt"),
    ("Kymeta Echodyne cloaking", "ieee_aess_metamaterial_scanning.txt"),
    ("SATCOM RHCP helicopters", "sbir_award_136890_si2_technologies.txt"),
    ("anisotropic inhomogeneous octave", "sbir_award_145942_metamaterials_inc.txt"),
    ("flexible metamaterial antenna conformal mounting", "us_patent_11005187B2.txt"),
]

# recall@K -- see CONTEXT.md's "Correctness bar": start minimal (recall@k +
# zero-result rate only), not the full nDCG/MRR/citation-precision contract.
_K = 5


def _ingest_corpus(cleanup_documents) -> dict[str, int]:
    """Ingest every knowledge/corpus/*.txt file and return {filename:
    document_id}. Idempotent: `ingest_document`'s checksum dedup means a
    file already ingested by an earlier test/session in this run returns
    `"duplicate"` with the existing id rather than a new row, so this is
    cheap and safe to call from more than one test."""
    ids_by_file: dict[str, int] = {}
    for path in sorted(_CORPUS_DIR.glob("*.txt")):
        result = ingest_document(
            file_path=str(path),
            source_type="paper",
            license="public-domain-us-government-work",
            classification="PUBLIC",
        )
        if result["status"] != "duplicate":
            cleanup_documents.append(result["document_id"])
        ids_by_file[path.name] = result["document_id"]
    return ids_by_file


def test_golden_query_recall_and_zero_result_rate(cleanup_documents):
    """Every golden query must retrieve its own source document within the
    top _K lexical results (recall@k), and none may come back empty
    (zero-result rate). Failing either is this repo's actual regression
    signal for the knowledge pipeline's retrieval path."""
    ids_by_file = _ingest_corpus(cleanup_documents)

    zero_result_queries: list[str] = []
    recall_misses: list[tuple[str, str]] = []
    for query, filename in GOLDEN_QUERIES:
        expected_document_id = ids_by_file[filename]
        results = search_knowledge(query, limit=_K, source_types=[SourceType.PAPER])
        if not results:
            zero_result_queries.append(query)
            continue
        top_k_document_ids = {r["document_id"] for r in results[:_K]}
        if expected_document_id not in top_k_document_ids:
            recall_misses.append((query, filename))

    assert not zero_result_queries, f"queries with zero results: {zero_result_queries}"
    assert not recall_misses, f"recall@{_K} misses (query, expected file): {recall_misses}"
