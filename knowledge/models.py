"""Shared types for the knowledge-ingestion package.

Ticket #8 defined `SourceType`, `Classification`, and the draft dataclasses
that move data between the parse -> chunk -> store stages. Ticket #9 added
`Backend`. Ticket #11 (component extraction) adds `ComponentCategory` — the
per-category specification field/unit schema itself lives in
`knowledge/component_schema.py`, not here.
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


class Backend(StrEnum):
    """An embedding/LLM backend, identified by which base URL/key pair it
    resolves to (ADR-0004) -- not by deployment location. `LOCAL` covers any
    org-controlled self-hosted instance (on-prem or rented GPU infra);
    `EXTERNAL` is OpenAI's own hosted API."""

    LOCAL = "local"
    EXTERNAL = "external"


class ComponentCategory(StrEnum):
    """Fixed classification of a component (CONTEXT.md: Category) -- determines
    which specification fields `components.specifications` is expected to
    carry. Field names and units per category live in
    `knowledge/component_schema.py`."""

    AMPLIFIER = "amplifier"
    FILTER = "filter"
    MIXER = "mixer"
    ATTENUATOR = "attenuator"
    COUPLER_SPLITTER = "coupler_splitter"
    CIRCULATOR_ISOLATOR = "circulator_isolator"
    SWITCH = "switch"
    ANTENNA = "antenna"
    CONNECTOR_CABLE = "connector_cable"
    PASSIVE_COMPONENT = "passive_component"


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
    """Document-level metadata gathered before a `documents` row is written.

    `supersedes_document_id`, if given, is a human-declared claim -- "this
    upload is a newer revision of that document" -- never inferred (ADR-0002:
    inferring supersession from title/metadata matching was considered and
    rejected as fragile and silently wrong when it fails). Omitted means the
    upload is a plain new, independent document, full stop, regardless of
    what it's titled.
    """

    title: str
    source_type: SourceType
    classification: Classification
    license: str
    checksum_sha256: str
    source_uri: str | None = None
    author: str | None = None
    revision: str | None = None
    metadata: dict = field(default_factory=dict)
    supersedes_document_id: int | None = None
