"""Thin orchestration: fetch a stored document plus its chunks.

`read_document` is what gets wrapped as the `read_document` tool in
`agent/main.py` and `mcp_server/server.py` (already listed under
`read_only` in `policies/tool_policy.yaml`, per ticket #13). Composes
`knowledge.db`'s reads -- no logic of its own beyond wiring them together
and turning a missing id into a structured result instead of `None`.
"""

from __future__ import annotations

from typing import Any

from knowledge import db


def read_document(document_id: int) -> dict[str, Any]:
    """Fetch a stored document's full metadata plus its chunks, in
    `chunk_index` order.

    A nonexistent `document_id` returns `{"status": "not_found",
    "document_id": document_id}` rather than raising or leaking a DB
    exception (matching `ingest_document`'s existing pattern of a status
    dict for expected non-error cases).
    """
    conn = db.get_connection()
    try:
        document = db.get_document(conn, document_id)
        if document is None:
            return {"status": "not_found", "document_id": document_id}

        chunk_rows = db.get_chunk_details(conn, document_id)
    finally:
        conn.close()

    publication_date = document["publication_date"]

    return {
        "status": document["status"],
        "document_id": document["id"],
        "title": document["title"],
        "source_type": document["source_type"],
        "license": document["license"],
        "classification": document["metadata"].get("classification"),
        "authority_rank": document["authority_rank"],
        "revision": document["revision"],
        "supersedes_document_id": document["supersedes_document_id"],
        "publication_date": publication_date.isoformat() if publication_date else None,
        "author": document["author"],
        "chunks": [
            {
                "chunk_index": row["chunk_index"],
                "content": row["content"],
                "page_number": row["page_number"],
                "section": row["section"],
            }
            for row in chunk_rows
        ],
    }
