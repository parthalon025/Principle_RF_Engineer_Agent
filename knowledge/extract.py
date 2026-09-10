"""Ticket #11: extract structured component specifications from an ingested
datasheet/application_note's chunks and store them (ADR-0003, ADR-0004).

`extract_components` is what gets wrapped as the `extract_components` tool
in `agent/main.py` and `mcp_server/server.py`. It composes `knowledge.backend`
(the pure floor-enforcing decision, reused verbatim from ticket #9),
`knowledge.extraction_llm` (the two structurally separate I/O adapters),
`knowledge.component_schema` (which fields a category expects),
`knowledge.validation` (physical-plausibility bounds), `knowledge.provenance`
(confidence + validity -> provenance tag), and `knowledge.db` -- no
extraction logic of its own.

Runs automatically, no confirmation step (ADR-0003: this company has no RF
engineer to staff a review queue). Only applies to datasheet/application_note
documents -- extraction over a standard/textbook/paper is a no-op, since
those source types don't describe one orderable part.

Structural separation, not a runtime guard, exactly like `knowledge/index.py`:
`_extract_restricted` and `_extract_permissive` are two distinct functions
below. `_extract_restricted` is the only path a SENSITIVE/RESTRICTED
document's chunks take, and it never references the external adapter --
there's no call, import-time reference, or branch inside it that reaches
`extract_external`. `_extract_permissive` handles PUBLIC/INTERNAL, and is the
only place a local-unreachable fallback to the external API can happen.

Segmentation assumption (multi-part datasheets): where one component's
fields end and the next begin is decided entirely by the extraction call
itself (`extract_local`/`extract_external`) -- it returns an
already-segmented list of raw components, each carrying its own
manufacturer/part_number/category/fields. This module does no segmentation
of its own; it validates, tags provenance, and stores whatever components
the extractor already split out. A raw component with an unrecognized
category, or missing its part number, is skipped (recorded under
`skipped` in the result) rather than failing the whole extraction -- one
malformed entry in a multi-part datasheet shouldn't lose the others.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from typing import Any

import psycopg

from knowledge import db
from knowledge.backend import select_backend
from knowledge.component_schema import CATEGORY_FIELDS
from knowledge.extraction_llm import (
    LocalExtractionUnavailableError,
    _extract_via_external,
    _extract_via_local,
)
from knowledge.models import Backend, Classification, ComponentCategory, SourceType
from knowledge.provenance import component_field_provenance
from knowledge.validation import validate_field

ExtractFn = Callable[[list[dict[str, Any]]], list[dict[str, Any]]]

_RESTRICTED = {Classification.SENSITIVE, Classification.RESTRICTED}
_EXTRACTABLE_SOURCE_TYPES = {SourceType.DATASHEET.value, SourceType.APPLICATION_NOTE.value}


def extract_components(
    document_id: int,
    requested_backend: str | None = None,
    *,
    extract_local: ExtractFn = _extract_via_local,
    extract_external: ExtractFn = _extract_via_external,
) -> dict[str, Any]:
    """Extract every component described in `document_id`'s chunks and
    upsert a `components` row per component, keyed by the exact orderable
    part code (`manufacturer`, `part_number`).

    A no-op ("skipped") for any document whose `source_type` is not
    datasheet/application_note. `requested_backend` and the floor/fallback
    rules (SENSITIVE/RESTRICTED local-only with no fallback; PUBLIC/INTERNAL
    honor an explicit request or `DEFAULT_LLM_BACKEND`, falling back from
    local to external if the self-hosted backend is briefly unreachable)
    are identical to `knowledge.index.index_document` (ADR-0004).

    `extract_local` / `extract_external` are the real I/O adapters by
    default; tests inject fakes here to verify routing without a live LLM
    endpoint.
    """
    requested = Backend(requested_backend) if requested_backend else None
    config_default = Backend(os.environ.get("DEFAULT_LLM_BACKEND", Backend.LOCAL.value))

    conn = db.get_connection()
    try:
        document = db.get_document(conn, document_id)
        if document is None:
            raise ValueError(f"No document with id={document_id}")

        if document["source_type"] not in _EXTRACTABLE_SOURCE_TYPES:
            return {
                "status": "skipped",
                "document_id": document_id,
                "reason": (
                    f"source_type={document['source_type']!r} is not datasheet/"
                    "application_note; component extraction only applies to those."
                ),
            }

        classification = Classification(document["classification"])

        # Enforces the floor (raises for SENSITIVE/RESTRICTED + EXTERNAL)
        # before any chunk is touched.
        selected = select_backend(classification, requested, config_default)

        chunks = db.get_chunks(conn, document_id)
        if not chunks:
            return {
                "status": "extracted",
                "document_id": document_id,
                "component_count": 0,
                "backend": selected.value,
                "components": [],
            }

        if classification in _RESTRICTED:
            raw_components, backend_used = _extract_restricted(chunks, extract_local)
        else:
            raw_components, backend_used = _extract_permissive(
                chunks, selected, extract_local, extract_external
            )

        stored: list[dict[str, Any]] = []
        skipped: list[dict[str, Any]] = []
        for raw in raw_components:
            try:
                stored.append(_store_component(conn, document_id, raw))
            except (KeyError, ValueError) as exc:
                skipped.append({"raw": raw, "reason": str(exc)})

        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    result: dict[str, Any] = {
        "status": "extracted",
        "document_id": document_id,
        "component_count": len(stored),
        "backend": backend_used.value,
        "components": stored,
    }
    if skipped:
        result["skipped"] = skipped
    return result


def _extract_restricted(
    chunks: list[dict[str, Any]], extract_local: ExtractFn
) -> tuple[list[dict[str, Any]], Backend]:
    """SENSITIVE/RESTRICTED path -- local backend only. This function has no
    reference to an external-backend call anywhere in its body: there's
    structurally no route out of it to the external API (ADR-0004: "no
    shared fallback path"). If `extract_local` raises (self-hosted endpoint
    down), that propagates out of `extract_components` unhandled -- the
    document stays unextracted rather than falling back."""
    return extract_local(chunks), Backend.LOCAL


def _extract_permissive(
    chunks: list[dict[str, Any]],
    backend: Backend,
    extract_local: ExtractFn,
    extract_external: ExtractFn,
) -> tuple[list[dict[str, Any]], Backend]:
    """PUBLIC/INTERNAL path -- honors the selected backend. Falls back from
    local to external only when the self-hosted endpoint is briefly
    unreachable (ADR-0004); a backend explicitly/config-selected as external
    is called directly with no reverse fallback."""
    if backend is Backend.LOCAL:
        try:
            return extract_local(chunks), Backend.LOCAL
        except LocalExtractionUnavailableError:
            pass
    return extract_external(chunks), Backend.EXTERNAL


def _store_component(
    conn: psycopg.Connection, document_id: int, raw: dict[str, Any]
) -> dict[str, Any]:
    """Validate and store one raw extracted component. Raises `KeyError` if
    `part_number` is absent, `ValueError` if `category` isn't one of the ten
    starter categories -- both are caught by the caller and recorded under
    `skipped` rather than failing the whole extraction."""
    part_number = raw["part_number"]
    category = ComponentCategory(raw["category"])
    manufacturer = raw.get("manufacturer")
    known_fields = CATEGORY_FIELDS[category]

    specifications: dict[str, Any] = {}
    for field_name, raw_field in raw.get("fields", {}).items():
        if field_name not in known_fields:
            # Not a field this category's schema expects -- drop it rather
            # than store an unmodeled key components.specifications readers
            # wouldn't know how to interpret.
            continue

        confidence = raw_field.get("confidence")
        if confidence not in ("high", "low"):
            confidence = "low"

        value = raw_field.get("value")
        validation = validate_field(field_name, value)

        entry: dict[str, Any] = {
            "value": value,
            "unit": raw_field.get("unit", known_fields[field_name]),
            "provenance": component_field_provenance(confidence, validation.physically_valid),
            "condition": raw_field.get("condition"),
            "chunk_id": raw_field.get("chunk_id"),
            "page_number": raw_field.get("page_number"),
        }
        if not validation.physically_valid:
            entry["validation_error"] = validation.error
        specifications[field_name] = entry

    return db.upsert_component(
        conn,
        manufacturer=manufacturer,
        part_number=part_number,
        category=category.value,
        specifications=specifications,
        datasheet_document_id=document_id,
    )
