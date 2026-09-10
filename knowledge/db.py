"""psycopg-based reads/writes for `documents` and `document_chunks`.

Thin I/O module, mirroring `rf_tools/touchstone.py`'s real-I/O style: no
ORM, raw SQL via psycopg, matching `db/schema.sql`'s design directly.
Functions take an already-open connection and never commit it themselves
-- the caller (production: `knowledge.ingest`; tests: the test fixture)
owns the transaction boundary.
"""

from __future__ import annotations

import os
from typing import Any

import psycopg
from pgvector.psycopg import register_vector
from psycopg import sql
from psycopg.rows import dict_row
from psycopg.types.json import Json

from knowledge.models import ChunkDraft, DocumentDraft, DocumentStatus

_EMBEDDING_COLUMNS = {"embedding", "embedding_local"}


class DuplicateDocumentError(Exception):
    """Raised by `insert_document` when a document with this checksum is
    already stored. Carries the existing document's id and full row so the
    caller can point the user at it instead of creating a duplicate."""

    def __init__(self, document_id: int, document: dict[str, Any]):
        self.document_id = document_id
        self.document = document
        super().__init__(f"document with this checksum already exists: id={document_id}")


class InvalidSupersessionError(Exception):
    """Raised by `insert_document` when `draft.supersedes_document_id` does
    not point at a document that can actually be superseded: it doesn't
    exist, isn't ACTIVE (already superseded, or superseded by something
    else), or is a different `source_type`."""

    def __init__(self, document_id: int, reason: str):
        self.document_id = document_id
        self.reason = reason
        super().__init__(f"cannot supersede document_id={document_id}: {reason}")


def get_connection() -> psycopg.Connection:
    """Open a new connection using DATABASE_URL from the environment."""
    return psycopg.connect(os.environ["DATABASE_URL"])


def find_document_by_checksum(
    conn: psycopg.Connection, checksum_sha256: str
) -> dict[str, Any] | None:
    """Return the most recent document row with this checksum, if any exists
    (of any status -- an identical file is a duplicate regardless of
    whether the existing row happens to be ACTIVE or SUPERSEDED)."""
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT * FROM documents
            WHERE checksum_sha256 = %s
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (checksum_sha256,),
        )
        return cur.fetchone()


def insert_document(
    conn: psycopg.Connection, draft: DocumentDraft, authority_rank: int
) -> dict[str, Any]:
    """Insert a new `documents` row for `draft`.

    - Same checksum already stored -> raises `DuplicateDocumentError`
      instead of inserting; no duplicate row is created. Checked twice: once
      up front (the common case, and the only check that can name the
      pre-existing row without a round trip), and again by catching the
      database's own `documents_checksum_sha256_key` partial unique index if
      a concurrent insert of the identical checksum won the race in between
      -- the up-front check alone cannot see a write that commits after it
      ran but before this one does.
    - `draft.supersedes_document_id` set -> that document must exist, be
      ACTIVE, and share this draft's `source_type`, or `InvalidSupersessionError`
      is raised; otherwise its status flips to SUPERSEDED and the new row's
      `supersedes_document_id` links to it, both in one transaction
      (ADR-0002). This is a human-declared claim, never inferred from title
      or any other metadata matching. The same up-front-check-then-insert
      race applies here as for checksums above: two concurrent inserts can
      both see the target as ACTIVE before either commits. The database's
      own `documents_supersedes_document_id_key` partial unique index
      (issue #401) is the backstop -- caught below and reported as
      `InvalidSupersessionError`, not misread as a duplicate checksum.
    - `draft.supersedes_document_id` unset -> a plain new ACTIVE row, no
      supersession, regardless of whether its title matches anything else
      already stored.
    """
    existing = find_document_by_checksum(conn, draft.checksum_sha256)
    if existing is not None:
        raise DuplicateDocumentError(existing["id"], existing)

    try:
        with conn.transaction():
            supersedes_id = draft.supersedes_document_id
            if supersedes_id is not None:
                with conn.cursor(row_factory=dict_row) as cur:
                    cur.execute("SELECT * FROM documents WHERE id = %s", (supersedes_id,))
                    prior = cur.fetchone()
                if prior is None:
                    raise InvalidSupersessionError(supersedes_id, "no such document")
                if prior["status"] != DocumentStatus.ACTIVE.value:
                    raise InvalidSupersessionError(
                        supersedes_id, f"not ACTIVE (status={prior['status']!r})"
                    )
                if prior["source_type"] != draft.source_type.value:
                    raise InvalidSupersessionError(
                        supersedes_id,
                        f"source_type mismatch (target is {prior['source_type']!r}, "
                        f"upload is {draft.source_type.value!r})",
                    )

            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    INSERT INTO documents (
                        title, source_uri, source_type, author, revision,
                        license, authority_rank, checksum_sha256, metadata,
                        status, supersedes_document_id, classification
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING *
                    """,
                    (
                        draft.title,
                        draft.source_uri,
                        draft.source_type.value,
                        draft.author,
                        draft.revision,
                        draft.license,
                        authority_rank,
                        draft.checksum_sha256,
                        Json(draft.metadata),
                        DocumentStatus.ACTIVE.value,
                        supersedes_id,
                        draft.classification.value,
                    ),
                )
                new_row = cur.fetchone()

                if supersedes_id is not None:
                    cur.execute(
                        "UPDATE documents SET status = %s WHERE id = %s",
                        (DocumentStatus.SUPERSEDED.value, supersedes_id),
                    )
    except psycopg.errors.UniqueViolation as exc:
        if exc.diag.constraint_name == "documents_supersedes_document_id_key":
            raise InvalidSupersessionError(
                draft.supersedes_document_id,
                "already claimed as superseded by another document",
            ) from None
        existing = find_document_by_checksum(conn, draft.checksum_sha256)
        assert existing is not None
        raise DuplicateDocumentError(existing["id"], existing) from None

    assert new_row is not None
    return new_row


def get_document(conn: psycopg.Connection, document_id: int) -> dict[str, Any] | None:
    """Fetch a `documents` row by id, or None if it doesn't exist."""
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT * FROM documents WHERE id = %s", (document_id,))
        return cur.fetchone()


def get_chunks(conn: psycopg.Connection, document_id: int) -> list[dict[str, Any]]:
    """Fetch `document_chunks` rows for a document, in chunk order."""
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            "SELECT id, chunk_index, content FROM document_chunks "
            "WHERE document_id = %s ORDER BY chunk_index",
            (document_id,),
        )
        return cur.fetchall()


def get_chunk_details(conn: psycopg.Connection, document_id: int) -> list[dict[str, Any]]:
    """Fetch `document_chunks` rows for a document in chunk order, including
    `page_number` and `section` (ticket #13's `read_document`). Kept separate
    from `get_chunks` -- whose narrower column list (ticket #9) still serves
    `knowledge.index`'s embedding pass -- rather than widening that function's
    columns underneath its existing caller."""
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            "SELECT id, chunk_index, content, page_number, section FROM document_chunks "
            "WHERE document_id = %s ORDER BY chunk_index",
            (document_id,),
        )
        return cur.fetchall()


def write_chunk_embeddings(
    conn: psycopg.Connection,
    column: str,
    chunk_ids: list[int],
    vectors: list[list[float]],
) -> int:
    """Write embedding vectors into `column` ("embedding" or
    "embedding_local") for the given chunk ids. `column` is chosen by the
    caller from whichever backend actually produced `vectors` (ticket #9) --
    not from the document's classification alone. Returns the number of
    rows updated.
    """
    if column not in _EMBEDDING_COLUMNS:
        raise ValueError(f"Not an embedding column: {column!r}")
    if len(chunk_ids) != len(vectors):
        raise ValueError("chunk_ids and vectors must have equal length")
    if not chunk_ids:
        return 0

    register_vector(conn)
    query = sql.SQL("UPDATE document_chunks SET {col} = %s WHERE id = %s").format(
        col=sql.Identifier(column)
    )
    with conn.cursor() as cur:
        cur.executemany(
            query, [(vector, chunk_id) for chunk_id, vector in zip(chunk_ids, vectors, strict=True)]
        )
    return len(chunk_ids)


def _document_scope_clause(document_id: int | None) -> tuple[str, Any]:
    """The `document_id`-pin-vs-ACTIVE-default WHERE fragment shared by
    `search_lexical` and `search_semantic` (ticket #10): `document_id` given
    -> only that document's chunks, any status; `document_id` None -> only
    `ACTIVE` documents' chunks (ADR-0002). Returns (sql_fragment, param)."""
    if document_id is not None:
        return "dc.document_id = %s", document_id
    return "d.status = %s", DocumentStatus.ACTIVE.value


def _source_type_clause(source_types: list[str] | None) -> tuple[str | None, list[str] | None]:
    """The optional `documents.source_type` filter shared by `search_lexical`
    and `search_semantic` (ticket #37): `source_types` given -> only chunks
    of documents whose source_type is in that list; None (default) -> no
    filter, every source type is eligible, matching pre-#37 behavior."""
    if source_types is None:
        return None, None
    return "d.source_type = ANY(%s)", list(source_types)


def search_lexical(
    conn: psycopg.Connection,
    query_text: str,
    *,
    document_id: int | None = None,
    source_types: list[str] | None = None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Full-text search `document_chunks.content` against `query_text`
    (`plainto_tsquery('english', ...)`, ranked by `ts_rank`, backed by the
    `document_chunks_content_fts_gin` index -- ticket #10).

    `document_id` is None (default): only chunks of `ACTIVE` documents are
    searched. `document_id` given: only that document's chunks are searched,
    regardless of its status -- pinning a specific document/revision id can
    retrieve a SUPERSEDED one (ADR-0002). `source_types` (ticket #37), given,
    additionally restricts results to documents of those source types (e.g.
    `["design_record"]` for `search_design_records`) -- None searches every
    source type, same as before this filter existed. Results are ordered by
    `ts_rank` descending; `search_knowledge` (knowledge/search.py) is
    responsible for the final authority-rank-first ordering across match
    types.
    """
    scope_clause, scope_param = _document_scope_clause(document_id)
    where = ["to_tsvector('english', dc.content) @@ plainto_tsquery('english', %s)", scope_clause]
    where_params: list[Any] = [query_text, scope_param]
    source_type_clause, source_type_param = _source_type_clause(source_types)
    if source_type_clause is not None:
        where.append(source_type_clause)
        where_params.append(source_type_param)

    query = f"""
        SELECT
            dc.id AS chunk_id, dc.document_id, dc.chunk_index, dc.content,
            dc.page_number, dc.section,
            d.title AS document_title, d.source_type, d.authority_rank, d.status,
            ts_rank(to_tsvector('english', dc.content), plainto_tsquery('english', %s)) AS score
        FROM document_chunks dc
        JOIN documents d ON d.id = dc.document_id
        WHERE {" AND ".join(where)}
        ORDER BY score DESC
        LIMIT %s
    """
    # Placeholder order top-to-bottom: the SELECT's own ts_rank(%s), then
    # each of `where_params` in the order they were appended, then LIMIT.
    params = [query_text, *where_params, limit]
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(query, params)
        return cur.fetchall()


def search_semantic(
    conn: psycopg.Connection,
    column: str,
    query_embedding: list[float],
    *,
    document_id: int | None = None,
    source_types: list[str] | None = None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Nearest-neighbor search of `column` ("embedding" or "embedding_local")
    against `query_embedding` via pgvector cosine distance, backed by that
    column's HNSW index (ticket #10). `score` is `1 - cosine_distance` (1.0
    = identical direction), so higher is better, matching `search_lexical`'s
    `ts_rank` convention of higher-is-better -- callers must not compare the
    two numbers to each other (no score fusion -- ticket #10).

    Only chunks where `column IS NOT NULL` are eligible -- a chunk embedded
    via the other backend, or not yet indexed at all, is silently absent
    rather than an error. `document_id` and `source_types` (ticket #37)
    behave as in `search_lexical`.
    """
    if column not in _EMBEDDING_COLUMNS:
        raise ValueError(f"Not an embedding column: {column!r}")

    scope_clause, scope_param = _document_scope_clause(document_id)
    where = [f"dc.{column} IS NOT NULL", scope_clause]
    where_params: list[Any] = [scope_param]
    source_type_clause, source_type_param = _source_type_clause(source_types)
    if source_type_clause is not None:
        where.append(source_type_clause)
        where_params.append(source_type_param)

    register_vector(conn)
    query = sql.SQL(
        """
        SELECT
            dc.id AS chunk_id, dc.document_id, dc.chunk_index, dc.content,
            dc.page_number, dc.section,
            d.title AS document_title, d.source_type, d.authority_rank, d.status,
            1 - (dc.{col} <=> %s::vector) AS score
        FROM document_chunks dc
        JOIN documents d ON d.id = dc.document_id
        WHERE {where}
        ORDER BY dc.{col} <=> %s::vector ASC
        LIMIT %s
        """
    ).format(col=sql.Identifier(column), where=sql.SQL(" AND ".join(where)))
    # Placeholder order top-to-bottom: the SELECT's own similarity %s, then
    # each of `where_params`, then ORDER BY's distance %s, then LIMIT.
    params = [query_embedding, *where_params, query_embedding, limit]
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(query, params)
        return cur.fetchall()


def upsert_component(
    conn: psycopg.Connection,
    manufacturer: str | None,
    part_number: str,
    category: str,
    specifications: dict[str, Any],
    datasheet_document_id: int | None,
) -> dict[str, Any]:
    """Insert or update a `components` row keyed by the exact orderable part
    code -- `UNIQUE(manufacturer, part_number)` (ticket #11, CONTEXT.md:
    Component). A conflict on that pair overwrites `category`,
    `specifications`, and `datasheet_document_id` wholesale: `extract_components`
    always re-extracts every field a category schema defines from the latest
    datasheet read, so there's no per-field merge with whatever was stored
    before -- the newest extraction simply replaces it.
    """
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            INSERT INTO components (
                manufacturer, part_number, category, specifications, datasheet_document_id
            ) VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (manufacturer, part_number) DO UPDATE SET
                category = EXCLUDED.category,
                specifications = EXCLUDED.specifications,
                datasheet_document_id = EXCLUDED.datasheet_document_id
            RETURNING *
            """,
            (manufacturer, part_number, category, Json(specifications), datasheet_document_id),
        )
        row = cur.fetchone()
    assert row is not None
    return row


def get_component(
    conn: psycopg.Connection, manufacturer: str | None, part_number: str
) -> dict[str, Any] | None:
    """Fetch a `components` row by its exact `(manufacturer, part_number)`
    identity, or None if no such row exists yet.

    `IS NOT DISTINCT FROM` (rather than `=`) on `manufacturer` is
    deliberate: plain SQL `NULL = NULL` is never true, so a `=` comparison
    would never find a row whose `manufacturer` is NULL even when
    `manufacturer` here is also None -- `IS NOT DISTINCT FROM` treats two
    NULLs as a match, matching how a caller reading "no manufacturer on
    either side" would expect this lookup to behave.

    Ticket #67's `knowledge.component_resolution.reconcile_components`
    reads the existing row's `specifications` via this function before
    calling `upsert_component`, so identity reconciliation -- which has no
    per-field spec data of its own (that's `extract_components`'s job) --
    never wipes specifications an earlier extraction already stored.
    """
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            "SELECT * FROM components WHERE manufacturer IS NOT DISTINCT FROM %s "
            "AND part_number = %s",
            (manufacturer, part_number),
        )
        return cur.fetchone()


def insert_chunks(conn: psycopg.Connection, document_id: int, chunks: list[ChunkDraft]) -> int:
    """Bulk-insert chunk drafts for a document. Returns the number inserted.
    Embeddings are left NULL -- populating them is ticket #2's concern."""
    if not chunks:
        return 0
    with conn.cursor() as cur:
        cur.executemany(
            """
            INSERT INTO document_chunks (
                document_id, chunk_index, content, page_number, section, metadata
            ) VALUES (%s, %s, %s, %s, %s, %s)
            """,
            [
                (
                    document_id,
                    c.chunk_index,
                    c.content,
                    c.page_number,
                    c.section,
                    Json(c.metadata),
                )
                for c in chunks
            ],
        )
    return len(chunks)
