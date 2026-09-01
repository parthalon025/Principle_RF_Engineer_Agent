"""Ticket #9: embed a document's chunks and write the vectors (ADR-0004).

`index_document` is what gets wrapped as the `index_document` tool in
`agent/main.py` and `mcp_server/server.py`. It composes `knowledge.backend`
(the pure floor-enforcing decision), `knowledge.embedding` (the two
structurally separate I/O adapters), and `knowledge.db` (storage) -- no
embedding logic of its own.

Structural separation, not a runtime guard: `_index_restricted` and
`_index_permissive` are two distinct functions below. `_index_restricted` is
the only path a SENSITIVE/RESTRICTED document's chunks take, and it never
references the external adapter -- there's no call, import-time reference,
or branch inside it that reaches `embed_external`. `_index_permissive`
handles PUBLIC/INTERNAL, and is the only place a local-unreachable fallback
to the external API can happen.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from typing import Any

from knowledge import db
from knowledge.backend import select_backend
from knowledge.embedding import (
    LocalBackendUnavailableError,
    _embed_via_external,
    _embed_via_local,
)
from knowledge.models import Backend, Classification

EmbedFn = Callable[[list[str]], list[list[float]]]

_RESTRICTED = {Classification.SENSITIVE, Classification.RESTRICTED}

# The one place that ties a backend to the document_chunks column it writes
# to, so the two can't drift independently of each other.
_COLUMN_FOR_BACKEND = {Backend.LOCAL: "embedding_local", Backend.EXTERNAL: "embedding"}


def index_document(
    document_id: int,
    requested_backend: str | None = None,
    *,
    embed_local: EmbedFn = _embed_via_local,
    embed_external: EmbedFn = _embed_via_external,
) -> dict[str, Any]:
    """Embed every chunk of `document_id` and write the resulting vectors to
    whichever of `embedding` / `embedding_local` corresponds to the backend
    that actually produced them -- not to the document's classification
    alone (a PUBLIC document embedded via the local backend still writes to
    `embedding_local`).

    `requested_backend` is an optional explicit "local"/"external" choice,
    otherwise `DEFAULT_LLM_BACKEND` picks for PUBLIC/INTERNAL documents.
    SENSITIVE/RESTRICTED documents reject an explicit "external" request
    outright (`knowledge.backend.RestrictedBackendViolation`) and otherwise
    always route through the local backend only, with no fallback if it's
    unreachable -- the operation fails loudly and the document's chunks stay
    unembedded rather than risk leaking restricted content externally
    (ADR-0004). PUBLIC/INTERNAL documents fall back from local to external
    if the self-hosted backend is briefly unreachable.

    `embed_local` / `embed_external` are the real I/O adapters by default;
    tests inject fakes here to verify routing without a live backend.
    """
    requested = Backend(requested_backend) if requested_backend else None
    config_default = Backend(os.environ.get("DEFAULT_LLM_BACKEND", Backend.LOCAL.value))

    conn = db.get_connection()
    try:
        document = db.get_document(conn, document_id)
        if document is None:
            raise ValueError(f"No document with id={document_id}")
        classification = Classification(document["metadata"]["classification"])

        # Enforces the floor (raises for SENSITIVE/RESTRICTED + EXTERNAL)
        # before any chunk is touched.
        selected = select_backend(classification, requested, config_default)

        chunks = db.get_chunks(conn, document_id)
        if not chunks:
            return {
                "status": "indexed",
                "document_id": document_id,
                "chunk_count": 0,
                "backend": selected.value,
                "column": None,
            }

        chunk_ids = [c["id"] for c in chunks]
        texts = [c["content"] for c in chunks]

        if classification in _RESTRICTED:
            column, vectors, backend_used = _index_restricted(texts, embed_local)
        else:
            column, vectors, backend_used = _index_permissive(
                texts, selected, embed_local, embed_external
            )

        written = db.write_chunk_embeddings(conn, column, chunk_ids, vectors)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    return {
        "status": "indexed",
        "document_id": document_id,
        "chunk_count": written,
        "backend": backend_used.value,
        "column": column,
    }


def _index_restricted(
    texts: list[str], embed_local: EmbedFn
) -> tuple[str, list[list[float]], Backend]:
    """SENSITIVE/RESTRICTED path -- local backend only. This function has no
    reference to an external-backend call anywhere in its body: there's
    structurally no route out of it to the external API (ADR-0004: "no
    shared fallback path"). If `embed_local` raises (self-hosted endpoint
    down), that propagates out of `index_document` unhandled -- the document
    stays un-embedded rather than falling back."""
    vectors = embed_local(texts)
    return _COLUMN_FOR_BACKEND[Backend.LOCAL], vectors, Backend.LOCAL


def _index_permissive(
    texts: list[str],
    backend: Backend,
    embed_local: EmbedFn,
    embed_external: EmbedFn,
) -> tuple[str, list[list[float]], Backend]:
    """PUBLIC/INTERNAL path -- honors the selected backend. Falls back from
    local to external only when the self-hosted endpoint is briefly
    unreachable (ADR-0004); a backend explicitly/config-selected as external
    is called directly with no reverse fallback."""
    if backend is Backend.LOCAL:
        try:
            return _COLUMN_FOR_BACKEND[Backend.LOCAL], embed_local(texts), Backend.LOCAL
        except LocalBackendUnavailableError:
            pass
    used = Backend.EXTERNAL
    return _COLUMN_FOR_BACKEND[used], embed_external(texts), used
