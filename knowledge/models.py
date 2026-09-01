"""Shared types for the knowledge-ingestion package.

Ticket #8 (this file) defines `SourceType`, `Classification`, and the draft
dataclasses that move data between the parse -> chunk -> store stages.
Later tickets (#2 indexing, #4 component extraction) extend this module
with `Backend` and `ComponentCategory` — leave room, don't build those yet.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class SourceType(StrEnum):
    """Classification of an ingested knowledge document (CONTEXT.md: Source type)."""

    DATASHEET = "datasheet"
    APPLICATION_NOTE = "application_note"
    STANDARD = "standard"
    TEXTBOOK = "textbook"
    PAPER = "paper"


class Classification(StrEnum):
    """Data-sensitivity classification (docs/SECURITY.md: Data classification)."""

    PUBLIC = "PUBLIC"
    INTERNAL = "INTERNAL"
    SENSITIVE = "SENSITIVE"
    RESTRICTED = "RESTRICTED"


class DocumentStatus(StrEnum):
    """Lifecycle status of a `documents` row (ADR-0002)."""

    ACTIVE = "ACTIVE"
    SUPERSEDED = "SUPERSEDED"


@dataclass(frozen=True)
class ParsedBlock:
    """One structural block from docling's parse, in document order.

    `kind` is one of "heading", "text", "table", "caption". `level` is the
    heading depth (1 = top-level) and is only meaningful when kind == "heading".
    """

    kind: str
    text: str
    page_number: int | None = None
    level: int | None = None


@dataclass(frozen=True)
class ParsedDocument:
    """The intermediate representation produced by `extraction.parse_document`."""

    title: str
    blocks: list[ParsedBlock] = field(default_factory=list)


@dataclass(frozen=True)
class ChunkDraft:
    """One chunk produced by `extraction.sections_to_chunks`, not yet stored."""

    chunk_index: int
    content: str
    section: str | None
    page_number: int | None
    metadata: dict = field(default_factory=dict)


@dataclass(frozen=True)
class DocumentDraft:
    """Document-level metadata gathered before a `documents` row is written."""

    title: str
    source_type: SourceType
    classification: Classification
    license: str
    checksum_sha256: str
    source_uri: str | None = None
    author: str | None = None
    revision: str | None = None
    metadata: dict = field(default_factory=dict)
