from knowledge.extraction import parse_document, sections_to_chunks
from knowledge.models import ParsedBlock, ParsedDocument, SourceType


def test_headings_start_new_chunks():
    parsed = ParsedDocument(
        title="Doc",
        blocks=[
            ParsedBlock(kind="heading", text="1. Introduction", level=1),
            ParsedBlock(kind="text", text="This part introduces the device."),
            ParsedBlock(kind="heading", text="2. Electrical Characteristics", level=1),
            ParsedBlock(kind="text", text="Vcc range is 3.0V to 3.6V."),
        ],
    )

    chunks = sections_to_chunks(parsed, SourceType.DATASHEET)

    assert len(chunks) == 2
    assert chunks[0].section == "1. Introduction"
    assert "introduces the device" in chunks[0].content
    assert chunks[1].section == "2. Electrical Characteristics"
    assert "3.0V to 3.6V" in chunks[1].content


def test_table_is_kept_as_its_own_chunk():
    table_text = "| Param | Min | Max |\n| Vcc | 3.0 | 3.6 |"
    parsed = ParsedDocument(
        title="Doc",
        blocks=[
            ParsedBlock(kind="heading", text="Electrical Characteristics", level=1),
            ParsedBlock(kind="text", text="See table below."),
            ParsedBlock(kind="table", text=table_text, page_number=4),
            ParsedBlock(kind="text", text="Notes follow the table."),
        ],
    )

    chunks = sections_to_chunks(parsed, SourceType.DATASHEET)

    table_chunks = [c for c in chunks if c.content == table_text]
    assert len(table_chunks) == 1
    table_chunk = table_chunks[0]
    assert table_chunk.page_number == 4
    assert table_chunk.section == "Electrical Characteristics"
    # The table is not merged into the surrounding prose chunks.
    assert "See table below." not in table_chunk.content
    assert "Notes follow the table." not in table_chunk.content


def test_caption_stays_attached_to_its_heading():
    parsed = ParsedDocument(
        title="Doc",
        blocks=[
            ParsedBlock(kind="heading", text="Typical Application", level=1),
            ParsedBlock(kind="table", text="| f | Gain |", page_number=7),
            ParsedBlock(kind="caption", text="Figure 3. Gain vs frequency.", page_number=7),
            ParsedBlock(kind="heading", text="Ordering Information", level=1),
            ParsedBlock(kind="text", text="See distributor."),
        ],
    )

    chunks = sections_to_chunks(parsed, SourceType.DATASHEET)

    caption_chunks = [c for c in chunks if "Figure 3" in c.content]
    assert len(caption_chunks) == 1
    caption_chunk = caption_chunks[0]
    # The caption belongs under the heading that precedes it, not the one
    # that follows, and not left with no section at all.
    assert caption_chunk.section == "Typical Application"
    assert caption_chunk.page_number == 7


def test_page_references_are_kept_on_text_chunks():
    parsed = ParsedDocument(
        title="Doc",
        blocks=[
            ParsedBlock(kind="heading", text="Overview", level=1),
            ParsedBlock(kind="text", text="First paragraph.", page_number=1),
            ParsedBlock(kind="text", text="Second paragraph.", page_number=1),
        ],
    )

    chunks = sections_to_chunks(parsed, SourceType.STANDARD)

    assert len(chunks) == 1
    assert chunks[0].page_number == 1


def test_chunk_indices_are_sequential():
    parsed = ParsedDocument(
        title="Doc",
        blocks=[
            ParsedBlock(kind="heading", text="A", level=1),
            ParsedBlock(kind="text", text="a1"),
            ParsedBlock(kind="table", text="t1", page_number=2),
            ParsedBlock(kind="heading", text="B", level=1),
            ParsedBlock(kind="text", text="b1"),
        ],
    )

    chunks = sections_to_chunks(parsed, SourceType.PAPER)

    assert [c.chunk_index for c in chunks] == list(range(len(chunks)))


def test_empty_document_yields_no_chunks():
    parsed = ParsedDocument(title="Empty", blocks=[])
    assert sections_to_chunks(parsed, SourceType.DATASHEET) == []


def test_parse_document_defaults_to_ocr_enabled(tmp_path, monkeypatch):
    """Issue #141: `knowledge.ingest.ingest_document` never overrides
    `do_ocr`, so a caller relying on OCR (reading text out of a scanned or
    image-only page, as opposed to a page that already has real, selectable
    text) for a document with no text layer must still get it by default.

    This proves the *wiring*, not real OCR behavior: it fakes out docling's
    `DocumentConverter` so no actual parsing (and no OCR-model download)
    happens, and just inspects the `PdfPipelineOptions` that `parse_document`
    builds when a caller doesn't pass `do_ocr` at all -- confirming it comes
    out `True`, matching docling's own default. `knowledge/test_ingest.py`
    and `knowledge/test_read.py` are the only callers that ever pass
    `do_ocr=False`, and they do it by monkeypatching the `parse_document`
    reference in `knowledge.ingest`, not by changing this default."""
    from docling.datamodel.base_models import InputFormat

    pdf_path = tmp_path / "fake.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n%%EOF")  # never actually parsed -- converter is faked below

    captured: dict[str, object] = {}

    class _FakeDocument:
        name = "Fake"

        def iterate_items(self, included_content_layers=None):
            return iter(())

    class _FakeResult:
        document = _FakeDocument()

    class _FakeConverter:
        def __init__(self, *, format_options=None, **kwargs):
            captured["format_options"] = format_options

        def convert(self, path):
            return _FakeResult()

    monkeypatch.setattr("docling.document_converter.DocumentConverter", _FakeConverter)

    parse_document(str(pdf_path))

    pdf_option = captured["format_options"][InputFormat.PDF]
    assert pdf_option.pipeline_options.do_ocr is True
