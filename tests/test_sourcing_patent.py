"""Issue #219: knowledge/sourcing/patent.py, tested at its seams.

No network, no subprocess, no PDF, no database. The three real boundaries
-- the HTTP GET, the two `uv run` calls into the vendored arxiv-doc-builder
skill, and `ingest_document` -- are each stubbed, the same way
tests/test_sourcing_arxiv.py stubs `convert_fn` and tests/test_nec2pp.py
stubs a fake executable.

The front-page fixtures below are NOT invented. They are the real output of
`pdf_converter_lib.extract_page_content` run over the real US 2022/0192066
A1 front sheet, trimmed to the lines each test needs -- OCR spacing damage
("(4 3 )", "sub -w avelength", "HIGHLY - CONFORMAL") preserved exactly,
because parsing has to survive that damage rather than a cleaned-up version
of it.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
import yaml

from knowledge.models import SourceType
from knowledge.provenance import PATENT_AUTHORITY_RANK, default_authority_rank
from knowledge.sourcing import patent

# --- fixtures ---------------------------------------------------------

# What the two-column crop of the front sheet really produces: the left
# block clean, the full-width top band pushed to the end (and "Patent
# Application Publicati|on" sliced in half by the crop line).
FRONT_PAGE_DOUBLE_COLUMN = """( 19 ) United States

( 12 ) Patent Application Publicati

Zaghloul et al .

( 54 ) HIGHLY - CONFORMAL , PLIABLE THIN

ELECTROMAGNETIC SKIN

( 71 ) Applicant: U.S. Army Combat Capabilities

Development Command , Army

Research Laboratory , Adelphi, MD

( US )

( 72 ) Inventors: Amir I. Zaghloul , Bethesda, MD (U S );

Quang Minh Nguyen, Severn, MD

( US ) ; Eric D. Adler , Columbia , MD

( US )

( 21 ) Appl . No .: 17 / 123,902

( 22 ) Filed : Dec. 16 , 2020

Publication Classification

( 51 ) Int . Ci.

H05K 9/00 ( 2006.01 )

50

TU

ion ( 10 ) Pub . No .: US 2022/0192066 A1

(4 3 ) Pub . Date : Jun . 16 , 2022

( 57 ) ABSTRACT

A highly - conformal, pliable thin electromagnetic ( EM ) skin

for altering at least one electromagnetic property of a surface

1*1?,

$
"""

# The same sheet read without cropping: the top band survives intact, but
# the two printed columns interleave line by line, so the title runs
# straight into the (52) block beside it.
FRONT_PAGE_SINGLE_COLUMN = """( 19 ) United States

( 12 ) Patent Application Publication ( 10 ) Pub . No .: US 2022/0192066 A1

Zaghloul et al . (4 3 ) Pub . Date : Jun . 16 , 2022

( 54 ) HIGHLY - CONFORMAL , PLIABLE THIN (5 2 ) U.S. CI .

ELECTROMAGNETIC SKIN CPC H05K 9/0081 ( 2013.01 )

( 71 ) Applicant: U.S. Army Combat Capabilities ( 2013.01 )
"""

# A granted patent's front sheet uses (45) for its date and (73) for the
# assignee where a publication uses (43) and (71).
GRANT_FRONT_PAGE = """( 12 ) United States Patent

( 10 ) Patent No .: US 12,089,385 B2

( 45 ) Date of Patent : Sep . 10 , 2024

( 54 ) HIGHLY - CONFORMAL , PLIABLE THIN

ELECTROMAGNETIC SKIN

( 73 ) Assignee : The Government of the United States

as represented by the Secretary of

the Army , Adelphi , MD ( US )

( 22 ) Filed : Dec. 16 , 2020

20 Claims , 15 Drawing Sheets
"""

# What the vendored extractor emits for a page with no text layer at all --
# every USPTO-served PDF measured during this ticket looks like this.
NO_TEXT_PAGE = "\n<!-- Page 1: No text extracted -->\n"


def _capture_ingest(monkeypatch, result=None):
    captured: dict = {}

    def fake_ingest_document(**kwargs):
        captured.update(kwargs)
        return result if result is not None else {"status": "ingested", "document_id": 1}

    monkeypatch.setattr(patent, "ingest_document", fake_ingest_document)
    return captured


def _extract_stub(page_count=31, text_chars=71864, body="# body\n", front=None):
    """Stand in for the `uv run ... _patent_convert.py extract` subprocess."""

    def run_extract(pdf_path: Path, output_dir: Path) -> dict:
        body_path = output_dir / "body.md"
        body_path.write_text(body, encoding="utf-8")
        return {
            "page_count": page_count,
            "text_chars": text_chars,
            "body_path": str(body_path),
            "front_page_double_column": (FRONT_PAGE_DOUBLE_COLUMN if front is None else front),
            "front_page_single_column": (FRONT_PAGE_SINGLE_COLUMN if front is None else front),
        }

    return run_extract


def _render_stub(image_count=96):
    def run_render(pdf_path: Path, output_dir: Path, dpi: int) -> dict:
        return {
            "image_dir": str(output_dir / "images"),
            "image_count": image_count,
            "dpi": dpi,
        }

    return run_render


def _pdf_bytes() -> bytes:
    return b"%PDF-1.4\nnot a real pdf, never parsed in these tests\n"


# --- normalize_patent_number ------------------------------------------


@pytest.mark.parametrize(
    "raw,number,kind_code,document_kind",
    [
        ("US12089385B2", "12089385", "B2", patent.GRANT),
        ("US 12,089,385 B2", "12089385", "B2", patent.GRANT),
        ("us12089385b2", "12089385", "B2", patent.GRANT),
        ("12089385", "12089385", None, patent.GRANT),
        ("US12089385", "12089385", None, patent.GRANT),
        ("4000000", "4000000", None, patent.GRANT),
        ("US 2022/0192066 A1", "20220192066", "A1", patent.PRE_GRANT_PUBLICATION),
        ("US20220192066A1", "20220192066", "A1", patent.PRE_GRANT_PUBLICATION),
        ("20220192066", "20220192066", None, patent.PRE_GRANT_PUBLICATION),
    ],
)
def test_normalize_accepts_the_forms_people_actually_paste(raw, number, kind_code, document_kind):
    identifier = patent.normalize_patent_number(raw)
    assert identifier.number == number
    assert identifier.kind_code == kind_code
    assert identifier.document_kind == document_kind


def test_normalize_builds_a_conventional_display_form():
    assert patent.normalize_patent_number("US 12,089,385 B2").display == "US12089385B2"
    assert patent.normalize_patent_number("20220192066").display == "US20220192066"


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "   ",
        "not a number",
        "EP1234567B1",  # a European document; this endpoint is the USPTO's
        "123456",  # too short for a grant
        "123456789",  # neither a grant nor a publication number
        "19990192066",  # 11 digits but before pre-grant publication existed
        "RE046000",  # reissue series, URL form never verified
    ],
)
def test_normalize_rejects_what_it_cannot_fetch(raw):
    with pytest.raises(patent.PatentNumberError):
        patent.normalize_patent_number(raw)


def test_normalize_refuses_a_kind_code_that_contradicts_the_number():
    """A1 says "published application"; 12089385 is a grant number. Guessing
    which half the caller meant is how the wrong document gets ingested."""
    with pytest.raises(patent.PatentNumberError, match="disagrees"):
        patent.normalize_patent_number("US12089385A1")
    with pytest.raises(patent.PatentNumberError, match="disagrees"):
        patent.normalize_patent_number("US20220192066B2")


def test_normalize_rejects_a_non_us_country_code_by_name():
    with pytest.raises(patent.PatentNumberError, match="US documents only"):
        patent.normalize_patent_number("JP2020123456A")


# --- patent_pdf_url ---------------------------------------------------


def test_pdf_url_uses_bare_digits_because_the_endpoint_rejects_anything_else():
    """Verified live: .../downloadPdf/12089385 returns HTTP 200 with a PDF,
    .../downloadPdf/US12089385B2 returns HTTP 400."""
    identifier = patent.normalize_patent_number("US12089385B2")
    assert patent.patent_pdf_url(identifier) == (
        "https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/12089385"
    )


# --- choose_conversion_route (pure) -----------------------------------


def test_route_is_scanned_when_the_pdf_has_no_text_layer():
    # The real US12089385B2 grant: 32 pages, zero extractable characters.
    assert patent.choose_conversion_route(0, 32) == patent.SCANNED_VISION_ROUTE


def test_route_is_text_layer_when_the_pdf_has_real_text():
    # The real OCR'd US 2022/0192066 A1: 71,864 characters over 31 pages.
    assert patent.choose_conversion_route(71864, 31) == patent.TEXT_LAYER_ROUTE


def test_route_is_scanned_for_a_stray_character_or_two_per_page():
    assert patent.choose_conversion_route(300, 32) == patent.SCANNED_VISION_ROUTE


def test_route_is_scanned_when_there_are_no_pages_at_all():
    assert patent.choose_conversion_route(0, 0) == patent.SCANNED_VISION_ROUTE


# --- parse_front_page_metadata (pure) ---------------------------------


def test_parse_reads_every_field_off_a_real_publication_front_sheet():
    meta = patent.parse_front_page_metadata(FRONT_PAGE_DOUBLE_COLUMN, FRONT_PAGE_SINGLE_COLUMN)
    assert meta["title"] == "HIGHLY - CONFORMAL, PLIABLE THIN ELECTROMAGNETIC SKIN"
    assert meta["inventors"] == [
        "Amir I. Zaghloul",
        "Quang Minh Nguyen",
        "Eric D. Adler",
    ]
    assert meta["applicant"].startswith("U.S. Army Combat Capabilities Development Command")
    assert meta["printed_document_number"] == "US 2022/0192066 A1"
    assert meta["publication_date"] == "Jun. 16, 2022"
    assert meta["application_number"] == "17 / 123,902"
    assert meta["filing_date"] == "Dec. 16, 2020"
    assert meta["abstract"].startswith("A highly - conformal, pliable thin electromagnetic")


def test_parse_reads_a_split_inid_marker():
    """The real sheet prints "(4 3 )" -- the space landed between the two
    digits of the code. A marker regex that assumes "(43)" loses the
    publication date entirely."""
    meta = patent.parse_front_page_metadata(
        "", "Zaghloul et al . (4 3 ) Pub . Date : Jun . 16 , 2022"
    )
    assert meta["publication_date"] == "Jun. 16, 2022"


def test_parse_prefers_the_two_column_reading_over_the_interleaved_one():
    """Uncropped, the title runs into the (52) block printed beside it and
    stops mid-phrase. Cropped, it is whole. Both are offered; the cropped
    one has to win."""
    single_only = patent.parse_front_page_metadata("", FRONT_PAGE_SINGLE_COLUMN)
    assert single_only["title"] == "HIGHLY - CONFORMAL, PLIABLE THIN"

    both = patent.parse_front_page_metadata(FRONT_PAGE_DOUBLE_COLUMN, FRONT_PAGE_SINGLE_COLUMN)
    assert both["title"] == "HIGHLY - CONFORMAL, PLIABLE THIN ELECTROMAGNETIC SKIN"


def test_parse_falls_back_to_the_uncropped_reading_for_the_top_band():
    """The publication number sits in the full-width band the crop cuts in
    half, so it can only come from the uncropped rendering."""
    cropped_without_top_band = FRONT_PAGE_DOUBLE_COLUMN.split("ion ( 10 )")[0]
    meta = patent.parse_front_page_metadata(cropped_without_top_band, FRONT_PAGE_SINGLE_COLUMN)
    assert meta["printed_document_number"] == "US 2022/0192066 A1"


def test_parse_reads_a_grants_own_inid_codes():
    """A grant prints (45) Date of Patent and (73) Assignee where a
    publication prints (43) Pub. Date and (71) Applicant."""
    meta = patent.parse_front_page_metadata(GRANT_FRONT_PAGE)
    assert meta["printed_document_number"] == "US 12,089,385 B2"
    assert meta["publication_date"] == "Sep. 10, 2024"
    assert meta["assignee"].startswith("The Government of the United States")
    assert meta["filing_date"] == "Dec. 16, 2020"


def test_parse_stops_a_field_at_the_drawing_sheet_count():
    """ "20 Claims, 15 Drawing Sheets" is the next thing printed after the
    assignee block, and is not part of the assignee."""
    meta = patent.parse_front_page_metadata(GRANT_FRONT_PAGE)
    assert "Drawing Sheets" not in meta["assignee"]


def test_parse_stops_a_field_at_a_section_heading():
    """ "Publication Classification" follows the filing date on the sheet."""
    meta = patent.parse_front_page_metadata(FRONT_PAGE_DOUBLE_COLUMN)
    assert "Publication Classification" not in (meta["filing_date"] or "")


def test_parse_drops_the_drawing_artifacts_trailing_the_abstract():
    """The real extraction ends the abstract with "1*1?," and "$" picked up
    off FIG. 1. A line with no letters in it is not prose."""
    meta = patent.parse_front_page_metadata(FRONT_PAGE_DOUBLE_COLUMN)
    assert not meta["abstract"].endswith("$")
    assert "1*1?," not in meta["abstract"]


def test_parse_returns_every_key_as_none_for_a_scanned_page():
    """ "Unknown stays unknown": a scanned front sheet yields nothing, and
    the schema still carries every key so a reader can tell "the sheet had
    no assignee" from "nobody looked"."""
    meta = patent.parse_front_page_metadata(NO_TEXT_PAGE, NO_TEXT_PAGE)
    assert meta["inventors"] == []
    assert set(meta) == {
        "title",
        "inventors",
        "assignee",
        "applicant",
        "printed_document_number",
        "publication_date",
        "application_number",
        "filing_date",
        "abstract",
    }
    for key, value in meta.items():
        if key != "inventors":
            assert value is None


# --- build_patent_frontmatter -----------------------------------------


def test_frontmatter_round_trips_through_a_yaml_parser():
    metadata = {
        "patent_number": "US20220192066A1",
        "title": "HIGHLY - CONFORMAL, PLIABLE THIN ELECTROMAGNETIC SKIN",
        "inventors": ["Amir I. Zaghloul"],
        "assignee": None,
    }
    block = patent.build_patent_frontmatter(metadata)
    assert block.startswith("---\n")
    assert block.endswith("---\n\n")
    parsed = yaml.safe_load(block.strip().strip("-"))
    assert parsed["patent_number"] == "US20220192066A1"
    assert parsed["inventors"] == ["Amir I. Zaghloul"]
    assert parsed["assignee"] is None


# --- the subprocess boundary (stubbed) --------------------------------


def test_extract_invokes_uv_run_against_the_skill_project(tmp_path, monkeypatch):
    captured: dict = {}

    def fake_run(cmd, capture_output, text, timeout):
        captured["cmd"] = cmd
        captured["timeout"] = timeout
        (tmp_path / "manifest.json").write_text(
            json.dumps({"page_count": 3, "text_chars": 9000}), encoding="utf-8"
        )
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(patent.subprocess, "run", fake_run)
    manifest = patent._run_patent_extract(tmp_path / "x.pdf", tmp_path)

    assert manifest == {"page_count": 3, "text_chars": 9000}
    cmd = captured["cmd"]
    assert cmd[:3] == ["uv", "run", "--project"]
    assert str(patent._ARXIV_DOC_BUILDER_DIR) in cmd
    # The PDF converters live behind the skill's own optional `pdf` extra.
    assert "--extra" in cmd and "pdf" in cmd
    assert "--no-dev" in cmd
    assert str(patent._CONVERT_SCRIPT) in cmd
    assert "extract" in cmd
    assert captured["timeout"] == patent._PATENT_CONVERT_TIMEOUT_S


def test_render_invokes_uv_run_with_the_requested_dpi(tmp_path, monkeypatch):
    captured: dict = {}

    def fake_run(cmd, capture_output, text, timeout):
        captured["cmd"] = cmd
        (tmp_path / "render_manifest.json").write_text(
            json.dumps({"image_dir": "i", "image_count": 4}), encoding="utf-8"
        )
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(patent.subprocess, "run", fake_run)
    manifest = patent._run_patent_render(tmp_path / "x.pdf", tmp_path, 1200)

    assert manifest["image_count"] == 4
    assert "render" in captured["cmd"]
    assert "1200" in captured["cmd"]


def test_extract_raises_with_the_subprocess_output_embedded(tmp_path, monkeypatch):
    def fake_run(cmd, capture_output, text, timeout):
        return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="pdfplumber exploded")

    monkeypatch.setattr(patent.subprocess, "run", fake_run)
    with pytest.raises(RuntimeError, match="pdfplumber exploded"):
        patent._run_patent_extract(tmp_path / "x.pdf", tmp_path)


def test_extract_raises_when_the_manifest_is_missing(tmp_path, monkeypatch):
    def fake_run(cmd, capture_output, text, timeout):
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(patent.subprocess, "run", fake_run)
    with pytest.raises(RuntimeError, match="does not exist"):
        patent._run_patent_extract(tmp_path / "x.pdf", tmp_path)


def test_extract_raises_on_timeout(tmp_path, monkeypatch):
    def fake_run(cmd, capture_output, text, timeout):
        raise subprocess.TimeoutExpired(cmd, timeout)

    monkeypatch.setattr(patent.subprocess, "run", fake_run)
    with pytest.raises(RuntimeError, match="timed out"):
        patent._run_patent_extract(tmp_path / "x.pdf", tmp_path)


# --- ingest_patent ----------------------------------------------------


def test_ingest_patent_ingests_as_source_type_patent(tmp_path, monkeypatch):
    captured = _capture_ingest(monkeypatch)

    patent.ingest_patent(
        "US 2022/0192066 A1",
        license="us-government-work",
        classification="PUBLIC",
        download_dir=str(tmp_path),
        fetch_fn=lambda url: _pdf_bytes(),
        extract_fn=_extract_stub(),
        render_fn=_render_stub(),
    )

    assert captured["source_type"] == "patent"
    assert captured["license"] == "us-government-work"
    assert captured["classification"] == "PUBLIC"


def test_ingest_patent_passes_no_authority_rank_override(tmp_path, monkeypatch):
    """Unlike the arXiv client, this one leans on the source type's own
    default. `patent` already defaults to PATENT_AUTHORITY_RANK -- below a
    peer-reviewed paper -- so restating it here would be a second copy of
    the same number, free to drift."""
    captured = _capture_ingest(monkeypatch)

    patent.ingest_patent(
        "US12089385B2",
        license="us-government-work",
        classification="PUBLIC",
        download_dir=str(tmp_path),
        fetch_fn=lambda url: _pdf_bytes(),
        extract_fn=_extract_stub(text_chars=0, page_count=32),
        render_fn=_render_stub(),
    )

    assert "authority_rank_override" not in captured
    assert default_authority_rank(SourceType.PATENT) == PATENT_AUTHORITY_RANK
    assert PATENT_AUTHORITY_RANK > default_authority_rank(SourceType.PAPER)


def test_ingest_patent_fetches_the_bare_digit_uspto_url(tmp_path, monkeypatch):
    _capture_ingest(monkeypatch)
    urls: list[str] = []

    def fetch(url):
        urls.append(url)
        return _pdf_bytes()

    patent.ingest_patent(
        "US 12,089,385 B2",
        license="us-government-work",
        classification="PUBLIC",
        download_dir=str(tmp_path),
        fetch_fn=fetch,
        extract_fn=_extract_stub(text_chars=0, page_count=32),
        render_fn=_render_stub(),
    )

    assert urls == ["https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/12089385"]


def test_ingest_patent_refuses_a_response_that_is_not_a_pdf(tmp_path, monkeypatch):
    _capture_ingest(monkeypatch)
    with pytest.raises(RuntimeError, match="did not return a PDF"):
        patent.ingest_patent(
            "12089385",
            license="us-government-work",
            classification="PUBLIC",
            download_dir=str(tmp_path),
            fetch_fn=lambda url: b"<html>Not Found</html>",
            extract_fn=_extract_stub(),
            render_fn=_render_stub(),
        )


def test_ingest_patent_validates_before_touching_the_network(tmp_path):
    def exploding_fetch(url):  # pragma: no cover - must never run
        raise AssertionError("fetched despite an invalid patent number")

    with pytest.raises(patent.PatentNumberError):
        patent.ingest_patent(
            "; rm -rf /",
            license="x",
            classification="PUBLIC",
            download_dir=str(tmp_path),
            fetch_fn=exploding_fetch,
        )


# --- routing ----------------------------------------------------------


def test_text_layer_pdf_is_converted_to_markdown_and_that_is_what_is_ingested(
    tmp_path, monkeypatch
):
    captured = _capture_ingest(monkeypatch)

    result = patent.ingest_patent(
        "US20220192066A1",
        license="us-government-work",
        classification="PUBLIC",
        download_dir=str(tmp_path),
        fetch_fn=lambda url: _pdf_bytes(),
        extract_fn=_extract_stub(body="\n\n<!-- Page 1 -->\n\nbody text\n"),
        render_fn=_render_stub(),
    )

    assert result["patent_conversion"]["route"] == patent.TEXT_LAYER_ROUTE
    ingested = Path(captured["file_path"])
    assert ingested.suffix == ".md"
    text = ingested.read_text(encoding="utf-8")
    assert text.startswith("---\n")
    assert "body text" in text


def test_scanned_pdf_is_handed_to_docling_itself_so_ocr_still_runs(tmp_path, monkeypatch):
    """A scanned patent has no text to convert, so the original PDF goes to
    `ingest_document` -- docling OCRs it (knowledge/extraction.py runs with
    do_ocr=True) and the document still becomes searchable. An empty
    Markdown file would have thrown the document away."""
    captured = _capture_ingest(monkeypatch)

    result = patent.ingest_patent(
        "US12089385B2",
        license="us-government-work",
        classification="PUBLIC",
        download_dir=str(tmp_path),
        fetch_fn=lambda url: _pdf_bytes(),
        extract_fn=_extract_stub(text_chars=0, page_count=32, front=NO_TEXT_PAGE),
        render_fn=_render_stub(),
    )

    assert result["patent_conversion"]["route"] == patent.SCANNED_VISION_ROUTE
    assert Path(captured["file_path"]).suffix == ".pdf"


def test_scanned_pdf_renders_its_pages_for_the_vision_path(tmp_path, monkeypatch):
    _capture_ingest(monkeypatch)
    calls: list[tuple] = []

    def render(pdf_path, output_dir, dpi):
        calls.append((pdf_path, output_dir, dpi))
        return {"image_dir": str(output_dir / "images"), "image_count": 96, "dpi": dpi}

    result = patent.ingest_patent(
        "US12089385B2",
        license="us-government-work",
        classification="PUBLIC",
        download_dir=str(tmp_path),
        image_dpi=1200,
        fetch_fn=lambda url: _pdf_bytes(),
        extract_fn=_extract_stub(text_chars=0, page_count=32, front=NO_TEXT_PAGE),
        render_fn=render,
    )

    assert len(calls) == 1
    assert calls[0][2] == 1200
    assert result["patent_conversion"]["page_image_count"] == 96
    assert result["patent_conversion"]["page_images_dir"].endswith("images")


def test_text_layer_pdf_does_not_render_page_images(tmp_path, monkeypatch):
    _capture_ingest(monkeypatch)

    def render(pdf_path, output_dir, dpi):  # pragma: no cover - must never run
        raise AssertionError("rendered images for a readable document")

    result = patent.ingest_patent(
        "US20220192066A1",
        license="us-government-work",
        classification="PUBLIC",
        download_dir=str(tmp_path),
        fetch_fn=lambda url: _pdf_bytes(),
        extract_fn=_extract_stub(),
        render_fn=render,
    )

    assert result["patent_conversion"]["page_image_count"] == 0
    assert result["patent_conversion"]["page_images_dir"] is None


def test_render_can_be_switched_off(tmp_path, monkeypatch):
    _capture_ingest(monkeypatch)

    def render(pdf_path, output_dir, dpi):  # pragma: no cover - must never run
        raise AssertionError("rendered images despite render_page_images=False")

    patent.ingest_patent(
        "US12089385B2",
        license="us-government-work",
        classification="PUBLIC",
        download_dir=str(tmp_path),
        render_page_images=False,
        fetch_fn=lambda url: _pdf_bytes(),
        extract_fn=_extract_stub(text_chars=0, page_count=32, front=NO_TEXT_PAGE),
        render_fn=render,
    )


def test_a_failed_render_warns_but_never_blocks_the_ingest(tmp_path, monkeypatch):
    """Rendering needs poppler on PATH. Losing the figure images costs the
    reader a way to check a drawing; it must not cost the document."""
    captured = _capture_ingest(monkeypatch)

    def render(pdf_path, output_dir, dpi):
        raise RuntimeError("Unable to get page count. Is poppler installed and in PATH?")

    result = patent.ingest_patent(
        "US12089385B2",
        license="us-government-work",
        classification="PUBLIC",
        download_dir=str(tmp_path),
        fetch_fn=lambda url: _pdf_bytes(),
        extract_fn=_extract_stub(text_chars=0, page_count=32, front=NO_TEXT_PAGE),
        render_fn=render,
    )

    assert captured["file_path"].endswith(".pdf")  # the ingest still happened
    assert "poppler" in result["patent_conversion"]["page_image_error"]
    assert result["patent_conversion"]["page_image_count"] == 0


# --- what reaches the documents row -----------------------------------


def test_front_page_metadata_is_promoted_onto_the_document_row(tmp_path, monkeypatch):
    captured = _capture_ingest(monkeypatch)

    patent.ingest_patent(
        "US20220192066A1",
        license="us-government-work",
        classification="PUBLIC",
        download_dir=str(tmp_path),
        fetch_fn=lambda url: _pdf_bytes(),
        extract_fn=_extract_stub(),
        render_fn=_render_stub(),
    )

    assert captured["title_override"] == ("HIGHLY - CONFORMAL, PLIABLE THIN ELECTROMAGNETIC SKIN")
    assert captured["author"] == "Amir I. Zaghloul, Quang Minh Nguyen, Eric D. Adler"
    # The kind code is what distinguishes two publications of one disclosure:
    # the A1 application publication and the B2 grant of the same invention.
    assert captured["revision"] == "A1"


def test_a_scanned_patent_reports_unknown_rather_than_a_guess(tmp_path, monkeypatch):
    captured = _capture_ingest(monkeypatch)

    patent.ingest_patent(
        "US12089385B2",
        license="us-government-work",
        classification="PUBLIC",
        download_dir=str(tmp_path),
        fetch_fn=lambda url: _pdf_bytes(),
        extract_fn=_extract_stub(text_chars=0, page_count=32, front=NO_TEXT_PAGE),
        render_fn=_render_stub(),
    )

    assert captured["title_override"] is None
    assert captured["author"] is None
    # The identifier is still known, because the caller supplied it.
    assert captured["revision"] == "B2"
    assert captured["extra_metadata"]["patent_number"] == "US12089385B2"


def test_extra_metadata_carries_the_identifier_source_and_route(tmp_path, monkeypatch):
    captured = _capture_ingest(monkeypatch)

    patent.ingest_patent(
        "US 2022/0192066 A1",
        license="us-government-work",
        classification="PUBLIC",
        download_dir=str(tmp_path),
        fetch_fn=lambda url: _pdf_bytes(),
        extract_fn=_extract_stub(),
        render_fn=_render_stub(),
    )

    extra = captured["extra_metadata"]
    assert extra["patent_number"] == "US20220192066A1"
    assert extra["uspto_number"] == "20220192066"
    assert extra["document_kind"] == patent.PRE_GRANT_PUBLICATION
    assert extra["source_url"].endswith("/20220192066")
    assert extra["conversion"]["route"] == patent.TEXT_LAYER_ROUTE
    assert extra["conversion"]["text_chars"] == 71864
    assert extra["publication_date"] == "Jun. 16, 2022"
    # Promoted to their own ingest_document parameters, not duplicated here.
    assert "title" not in extra
    assert "inventors" not in extra


def test_supersedes_document_id_is_passed_straight_through(tmp_path, monkeypatch):
    """A grant supersedes nothing automatically -- ADR-0002 keeps that an
    explicit caller decision -- but when the caller says so, it must reach
    ingest_document."""
    captured = _capture_ingest(monkeypatch)

    patent.ingest_patent(
        "US12089385B2",
        license="us-government-work",
        classification="PUBLIC",
        supersedes_document_id=42,
        download_dir=str(tmp_path),
        fetch_fn=lambda url: _pdf_bytes(),
        extract_fn=_extract_stub(text_chars=0, page_count=32, front=NO_TEXT_PAGE),
        render_fn=_render_stub(),
    )

    assert captured["supersedes_document_id"] == 42


def test_ingest_patent_creates_a_tempdir_when_download_dir_is_omitted(monkeypatch):
    _capture_ingest(monkeypatch)
    seen: list[Path] = []

    def extract(pdf_path, output_dir):
        seen.append(output_dir)
        return _extract_stub(text_chars=0, page_count=32, front=NO_TEXT_PAGE)(pdf_path, output_dir)

    patent.ingest_patent(
        "US12089385B2",
        license="us-government-work",
        classification="PUBLIC",
        render_page_images=False,
        fetch_fn=lambda url: _pdf_bytes(),
        extract_fn=extract,
    )

    assert len(seen) == 1
    assert seen[0].exists()
