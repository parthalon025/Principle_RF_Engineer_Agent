"""Ticket #10: unified knowledge search across lexical and semantic matches.

`search_knowledge` is what gets wrapped as the `search_knowledge` tool in
`agent/main.py` and `mcp_server/server.py`. It composes `knowledge.db`'s
three read-only query functions -- `search_lexical` (ts_rank against the GIN
index) and `search_semantic` against each of the two embedding columns --
into one ranked list, each result tagged with which kind of match it is.
No logic of its own beyond that composition and the final ordering.

Ticket #37 adds `source_types` (threaded straight through to `knowledge.db`'s
optional `source_types` filter) and `search_design_records`, a thin wrapper
around `search_knowledge` pinned to `SourceType.DESIGN_RECORD` -- so an
engineer (or an external MCP client) can look up a prior design/decision
record before proposing a new one, reusing this module's existing ranking
and match-type semantics rather than duplicating them.

Query embedding: computed by this function itself (via ticket #9's same two
adapters, `knowledge.embedding._embed_via_local` / `_embed_via_external`),
not required as an argument from the caller. `agent/main.py` exposes no
separate "embed text" tool to the LLM agent, so requiring a pre-computed
query_embedding_external/query_embedding_local would leave the agent with no
way to produce one; computing it here mirrors how `knowledge.index` already
uses those adapters, and keeps them injectable for tests. Advanced callers
that already have a query vector (e.g. from a prior embedding call) may
still pass one in directly via query_embedding_external/query_embedding_local
to skip re-embedding.

Embedding the query text is best-effort per backend: any exception -- the
backend unreachable, unconfigured, or (for the external adapter, which has
no dedicated "unavailable" exception type) simply missing OPENAI_API_KEY --
is caught and that match_type is skipped rather than raised. Lexical search
always runs regardless (ticket #10's acceptance criteria): a chunk that was
never embedded by either backend still surfaces via `match_type=lexical`.

No score fusion (ticket #10's explicit non-goal): results are ordered by
`documents.authority_rank` ascending first (lower rank wins -- ADR-0002 /
knowledge/provenance.py), then by a fixed match_type group order (semantic_
external, semantic_local, lexical -- arbitrary but stable), then by each
result's own native score descending within its group. Cosine similarity
and ts_rank are never combined into one sortable float.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from knowledge import db
from knowledge.embedding import _embed_via_external, _embed_via_local
from knowledge.models import SourceType

EmbedFn = Callable[[list[str]], list[list[float]]]

_MATCH_TYPE_ORDER = {"semantic_external": 0, "semantic_local": 1, "lexical": 2}


def _query_vector(
    supplied: list[float] | None, query_text: str, embed: EmbedFn
) -> list[float] | None:
    """Return `supplied` if given, else attempt to embed `query_text` via
    `embed`. Any failure degrades to None (that match_type is skipped) --
    never raised, since embedding availability must never block lexical
    search (ticket #10's acceptance criteria)."""
    if supplied is not None:
        return supplied
    try:
        return embed([query_text])[0]
    except Exception:
        return None


def search_knowledge(
    query_text: str,
    document_id: int | None = None,
    limit: int = 20,
    *,
    source_types: list[SourceType] | None = None,
    query_embedding_external: list[float] | None = None,
    query_embedding_local: list[float] | None = None,
    embed_local: EmbedFn = _embed_via_local,
    embed_external: EmbedFn = _embed_via_external,
) -> list[dict[str, Any]]:
    """Search the knowledge base for `query_text` and return one ranked list
    of chunk matches, each tagged with its `match_type`
    ("semantic_external" | "semantic_local" | "lexical").

    Defaults to `documents.status = 'ACTIVE'` only. Pass `document_id` to
    search a specific document/revision instead -- including a SUPERSEDED
    one (ADR-0002) -- regardless of its status. Pass `source_types` (ticket
    #37) to further restrict results to documents of those source types
    (e.g. `[SourceType.DESIGN_RECORD]`); None (default) searches every
    source type, same as before this filter existed -- see
    `search_design_records` below for the pinned convenience wrapper.

    Ordering: `authority_rank` ascending first, then match_type group, then
    each match's own native score descending within its group -- never a
    single blended score across match types (see module docstring).
    """
    source_type_values = [st.value for st in source_types] if source_types is not None else None
    conn = db.get_connection()
    try:
        results: list[dict[str, Any]] = []

        for row in db.search_lexical(
            conn, query_text, document_id=document_id, source_types=source_type_values, limit=limit
        ):
            results.append({**row, "match_type": "lexical"})

        ext_vector = _query_vector(query_embedding_external, query_text, embed_external)
        if ext_vector is not None:
            rows = db.search_semantic(
                conn,
                "embedding",
                ext_vector,
                document_id=document_id,
                source_types=source_type_values,
                limit=limit,
            )
            for row in rows:
                results.append({**row, "match_type": "semantic_external"})

        local_vector = _query_vector(query_embedding_local, query_text, embed_local)
        if local_vector is not None:
            rows = db.search_semantic(
                conn,
                "embedding_local",
                local_vector,
                document_id=document_id,
                source_types=source_type_values,
                limit=limit,
            )
            for row in rows:
                results.append({**row, "match_type": "semantic_local"})
    finally:
        conn.close()

    def sort_key(row: dict[str, Any]) -> tuple[int, int, float]:
        return (row["authority_rank"], _MATCH_TYPE_ORDER[row["match_type"]], -row["score"])

    results.sort(key=sort_key)
    return results[:limit]


def search_design_records(
    query_text: str,
    document_id: int | None = None,
    limit: int = 20,
    *,
    query_embedding_external: list[float] | None = None,
    query_embedding_local: list[float] | None = None,
    embed_local: EmbedFn = _embed_via_local,
    embed_external: EmbedFn = _embed_via_external,
) -> list[dict[str, Any]]:
    """Search for prior design/decision records relevant to `query_text` --
    e.g. by component, frequency band, or design pattern -- so an engineer
    can find precedent before proposing a new design (ticket #37).

    A thin wrapper around `search_knowledge`, pinned to
    `source_types=[SourceType.DESIGN_RECORD]`: same ranking, match-type
    tagging, and ACTIVE-by-default/`document_id`-pinning semantics, just
    scoped to documents ingested with `source_type="design_record"`
    (internally-authored design notes and decision write-ups -- CONTEXT.md's
    "internal engineering history" evidence tier) rather than every source
    type. No separate query path or duplicated ranking logic.
    """
    return search_knowledge(
        query_text,
        document_id=document_id,
        limit=limit,
        source_types=[SourceType.DESIGN_RECORD],
        query_embedding_external=query_embedding_external,
        query_embedding_local=query_embedding_local,
        embed_local=embed_local,
        embed_external=embed_external,
    )
