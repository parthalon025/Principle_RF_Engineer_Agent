from knowledge.extraction import sections_to_chunks
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
