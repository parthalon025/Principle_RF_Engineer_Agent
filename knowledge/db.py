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
from psycopg.rows import dict_row
from psycopg.types.json import Json

from knowledge.models import ChunkDraft, DocumentDraft, DocumentStatus


class DuplicateDocumentError(Exception):
    """Raised by `insert_document` when a document with this checksum is
    already stored. Carries the existing document's id and full row so the
    caller can point the user at it instead of creating a duplicate."""

    def __init__(self, document_id: int, document: dict[str, Any]):
        self.document_id = document_id
        self.document = document
        super().__init__(f"document with this checksum already exists: id={document_id}")


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


def _find_active_revision(
    conn: psycopg.Connection, title: str, source_type: str, exclude_checksum: str
) -> dict[str, Any] | None:
    """Find the ACTIVE document a newer revision would supersede: same
    title and source_type, different content. Matching on (title,
    source_type) is this ticket's revision-detection rule -- there is no
    separate "same logical document" identifier yet."""
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT * FROM documents
            WHERE status = %s
              AND source_type = %s
              AND lower(title) = lower(%s)
              AND checksum_sha256 IS DISTINCT FROM %s
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (DocumentStatus.ACTIVE.value, source_type, title, exclude_checksum),
        )
        return cur.fetchone()


def insert_document(
    conn: psycopg.Connection, draft: DocumentDraft, authority_rank: int
) -> dict[str, Any]:
    """Insert a new `documents` row for `draft`.

    - Same checksum already stored -> raises `DuplicateDocumentError`
      instead of inserting; no duplicate row is created.
    - An ACTIVE document with the same (title, source_type) but a
      different checksum exists -> treated as a newer revision: that row's
      status flips to SUPERSEDED and the new row's `supersedes_document_id`
      links to it, both in one transaction (ADR-0002).
    - Otherwise -> a plain new ACTIVE row with no supersession.
    """
    existing = find_document_by_checksum(conn, draft.checksum_sha256)
    if existing is not None:
        raise DuplicateDocumentError(existing["id"], existing)

    with conn.transaction():
        prior = _find_active_revision(
            conn, draft.title, draft.source_type.value, draft.checksum_sha256
        )
        supersedes_id = prior["id"] if prior else None

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

            if prior is not None:
                cur.execute(
                    "UPDATE documents SET status = %s WHERE id = %s",
                    (DocumentStatus.SUPERSEDED.value, prior["id"]),
                )

    assert new_row is not None
    return new_row


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
