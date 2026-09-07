"""Datasheet/standard/textbook/paper parsing and chunking.

`parse_document` is a thin I/O wrapper around docling (real PDF parsing —
not unit tested against a fixture, only via integration tests with real
files). `sections_to_chunks` is pure: it operates on the already-parsed
`ParsedDocument` intermediate representation and is tested with hand-built
fixtures, no docling call involved.
"""

from __future__ import annotations

from pathlib import Path

from knowledge.models import ChunkDraft, ParsedBlock, ParsedDocument, SourceType

_HEADING_LABELS = {"section_header", "title"}
_TABLE_LABELS = {"table"}
_CAPTION_LABELS = {"caption"}


def parse_document(path: str, *, do_ocr: bool = True) -> ParsedDocument:
    """Parse a PDF file into a `ParsedDocument` via docling.

    `do_ocr` controls whether docling's OCR (optical character recognition
    -- reading text out of a scanned/image page) stage runs, and defaults to
    `True` so real ingestion of a scanned/image-only document still gets OCR
    with no behavior change for any existing caller. `knowledge.ingest.
    ingest_document` never overrides it (issue #141): only tests that
    already know their fixture PDF has a real, selectable text layer pass
    `do_ocr=False` (by monkeypatching the `parse_document` reference in
    `knowledge.ingest`), so their outcome doesn't depend on whether an
    OCR-model download happens to succeed at test time.

    Raises whatever docling raises on an unparseable/corrupt file — callers
    (see `knowledge.ingest.ingest_document`) are responsible for turning
    that into a stored "extraction failed" document rather than crashing.
    """
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions
    from docling.document_converter import DocumentConverter, PdfFormatOption
    from docling_core.types.doc import ContentLayer

    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(path)

    pipeline_options = PdfPipelineOptions(do_ocr=do_ocr)
    converter = DocumentConverter(
        format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)}
    )
    result = converter.convert(str(p))
    doc = result.document

    blocks: list[ParsedBlock] = []
    included_layers = {ContentLayer.BODY, ContentLayer.FURNITURE}
    for item, _level in doc.iterate_items(included_content_layers=included_layers):
        kind = _label_to_kind(item)
        text = _item_text(item, doc)
        if not text:
            continue
        blocks.append(ParsedBlock(kind=kind, text=text, page_number=_item_page(item)))

    title = getattr(doc, "name", None) or p.stem
    return ParsedDocument(title=title, blocks=blocks)


def _label_to_kind(item) -> str:
    label = getattr(item, "label", None)
    label_str = str(getattr(label, "value", label)).lower()
    if label_str in _TABLE_LABELS:
        return "table"
    if label_str in _CAPTION_LABELS:
        return "caption"
    if label_str in _HEADING_LABELS:
        return "heading"
    return "text"


def _item_text(item, doc) -> str | None:
    text = getattr(item, "text", None)
    if text:
        return text
    export_md = getattr(item, "export_to_markdown", None)
    if callable(export_md):
        try:
            return export_md(doc=doc)
        except TypeError:
            return export_md()
    return None


def _item_page(item) -> int | None:
    prov = getattr(item, "prov", None)
    if not prov:
        return None
    first = prov[0]
    return getattr(first, "page_no", None)


def sections_to_chunks(parsed: ParsedDocument, source_type: SourceType) -> list[ChunkDraft]:
    """Split a `ParsedDocument` into chunks, preserving section/table/caption
    boundaries and page references. Pure — no I/O, no docling call.

    Rules:
    - A heading starts a new section and flushes any accumulated prose into
      its own chunk (tagged with the *previous* section).
    - A table is always its own chunk, never merged with surrounding prose.
    - A caption is always its own chunk, tagged with the current (nearest
      preceding) section — so it stays attached to its heading even when it
      immediately follows a table.
    - Consecutive prose blocks under the same heading are merged into one
      chunk.
    """
    chunks: list[ChunkDraft] = []
    current_section: str | None = None
    buffer_texts: list[str] = []
    buffer_pages: list[int] = []

    def flush() -> None:
        if not buffer_texts:
            return
        page = buffer_pages[0] if buffer_pages else None
        chunks.append(
            ChunkDraft(
                chunk_index=len(chunks),
                content="\n\n".join(buffer_texts),
                section=current_section,
                page_number=page,
                metadata={"kind": "text"},
            )
        )
        buffer_texts.clear()
        buffer_pages.clear()

    for block in parsed.blocks:
        if block.kind == "heading":
            flush()
            current_section = block.text
        elif block.kind == "table":
            flush()
            chunks.append(
                ChunkDraft(
                    chunk_index=len(chunks),
                    content=block.text,
                    section=current_section,
                    page_number=block.page_number,
                    metadata={"kind": "table"},
                )
            )
        elif block.kind == "caption":
            flush()
            chunks.append(
                ChunkDraft(
                    chunk_index=len(chunks),
                    content=block.text,
                    section=current_section,
                    page_number=block.page_number,
                    metadata={"kind": "caption"},
                )
            )
        else:
            buffer_texts.append(block.text)
            if block.page_number is not None:
                buffer_pages.append(block.page_number)

    flush()
    return chunks
