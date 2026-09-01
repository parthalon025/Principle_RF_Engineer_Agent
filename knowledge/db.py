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
      instead of inserting; no duplicate row is created.
    - `draft.supersedes_document_id` set -> that document must exist, be
      ACTIVE, and share this draft's `source_type`, or `InvalidSupersessionError`
      is raised; otherwise its status flips to SUPERSEDED and the new row's
      `supersedes_document_id` links to it, both in one transaction
      (ADR-0002). This is a human-declared claim, never inferred from title
      or any other metadata matching.
    - `draft.supersedes_document_id` unset -> a plain new ACTIVE row, no
      supersession, regardless of whether its title matches anything else
      already stored.
    """
    existing = find_document_by_checksum(conn, draft.checksum_sha256)
    if existing is not None:
        raise DuplicateDocumentError(existing["id"], existing)

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
                    status, supersedes_document_id
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
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
                ),
            )
            new_row = cur.fetchone()

            if supersedes_id is not None:
                cur.execute(
                    "UPDATE documents SET status = %s WHERE id = %s",
                    (DocumentStatus.SUPERSEDED.value, supersedes_id),
                )

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
