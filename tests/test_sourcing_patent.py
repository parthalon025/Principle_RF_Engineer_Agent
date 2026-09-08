"""Ticket #219: knowledge/sourcing/patent.py, tested at the seam -- stubbed
`fetch_fn`/`convert_fn` stand in for the real USPTO HTTP GET and the real
`uv run --project .../arxiv-doc-builder` subprocess call, and
`ingest_document` is monkeypatched to capture exactly what it was called
with, mirroring tests/test_sourcing_arxiv.py's own pattern.

No network access, no real subprocess, no database, no pypdf/pdfplumber
import (those live only in the vendored arxiv-doc-builder environment, not
this project's own dependency tree -- see patent.py's module docstring).
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from knowledge.sourcing import patent

# --- normalize_patent_number (pure) -------------------------------------


@pytest.mark.parametrize(
    "raw, expected_digits, expected_kind",
    [
        ("12089385", "12089385", "grant"),
        ("US12089385", "12089385", "grant"),
        ("US12089385B2", "12089385", "grant"),
        ("us12089385b2", "12089385", "grant"),
        ("  US 12089385 B2  ", "12089385", "grant"),
        ("11005187", "11005187", "grant"),
        ("2022/0192066", "20220192066", "publication"),
        ("US2022/0192066A1", "20220192066", "publication"),
        ("US 2022/0192066 A1", "20220192066", "publication"),
        ("20220192066", "20220192066", "publication"),
        ("US20220192066A1", "20220192066", "publication"),
    ],
)
def test_normalize_patent_number_valid_forms(raw, expected_digits, expected_kind):
    digits, kind, _kind_code = patent.normalize_patent_number(raw)
    assert digits == expected_digits
    assert kind == expected_kind


def test_normalize_patent_number_captures_kind_code():
    _digits, _kind, kind_code = patent.normalize_patent_number("US12089385B2")
    assert kind_code == "B2"

    _digits, _kind, kind_code = patent.normalize_patent_number("US20220192066A1")
    assert kind_code == "A1"

    _digits, _kind, kind_code = patent.normalize_patent_number("12089385")
    assert kind_code is None


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "   ",
        "not-a-patent",
        "D123456",  # design patent (letter-prefixed) -- out of scope
        "PP12345",  # plant patent -- out of scope
        "US123",  # too short to be a grant (< 4 digits)
        "123456789",  # 9 digits: neither an 8-digit grant nor an 11-digit publication
        "12089385XYZ99",  # malformed kind code
        "2022/019206",  # publication sequence one digit short
        "2022019206",  # 10 digits total, not 11
    ],
)
def test_normalize_patent_number_rejects_implausible_input(raw):
    with pytest.raises(ValueError):
        patent.normalize_patent_number(raw)


# --- _parse_patent_frontmatter (pure) ------------------------------------

_SAMPLE_FRONT_PAGE_TEXT = """(19) United States
(12) Patent Application Publication
(10) Pub. No.: US 2022/0192066 A1
(43) Pub. Date: Jun. 16, 2022
(54) HIGHLY-CONFORMAL, PLIABLE THIN ELECTROMAGNETIC SKIN
(71) Applicant: United States of America, as represented by the Secretary of the Army
(72) Inventors: Amir I. Zaghloul, Fairfax, VA (US); Chi-Chih Chen, Columbus, OH (US)
(73) Assignee: United States of America, as represented by the Secretary of the Army
(21) Appl. No.: 17/123,456
(22) Filed: Dec. 1, 2020
"""


def test_parse_patent_frontmatter_extracts_inid_fields():
    fm = patent._parse_patent_frontmatter(_SAMPLE_FRONT_PAGE_TEXT)
    assert fm["title"] == "HIGHLY-CONFORMAL, PLIABLE THIN ELECTROMAGNETIC SKIN"
    assert fm["publication_number"] == "US 2022/0192066 A1"
    assert fm["publication_date"] == "Jun. 16, 2022"
    assert fm["inventors"] == "Amir I. Zaghloul, Fairfax, VA (US); Chi-Chih Chen, Columbus, OH (US)"
    assert fm["assignee"] == "United States of America, as represented by the Secretary of the Army"
    assert fm["appl_no"] == "17/123,456"
    assert fm["filed"] == "Dec. 1, 2020"
    assert fm["grant_number"] is None
    assert fm["date_of_patent"] is None


def test_parse_patent_frontmatter_grant_form():
    text = (
        "(10) Patent No.: US 12,089,385 B2\n"
        "(45) Date of Patent: Sep. 10, 2024\n"
        "(54) HIGHLY-CONFORMAL, PLIABLE THIN ELECTROMAGNETIC SKIN\n"
        "(73) Assignee: United States of America\n"
    )
    fm = patent._parse_patent_frontmatter(text)
    assert fm["grant_number"] == "US 12,089,385 B2"
    assert fm["date_of_patent"] == "Sep. 10, 2024"
    assert fm["title"] == "HIGHLY-CONFORMAL, PLIABLE THIN ELECTROMAGNETIC SKIN"


def test_parse_patent_frontmatter_returns_all_none_for_empty_text():
    fm = patent._parse_patent_frontmatter("")
    assert all(value is None for value in fm.values())
    assert set(fm.keys()) == set(patent._INID_FIELD_PATTERNS.keys())


# --- _run_pdf_convert (subprocess boundary, stubbed) ---------------------


def test_run_pdf_convert_invokes_uv_run_against_the_skill_project_with_pdf_extra(
    tmp_path, monkeypatch
):
    captured_cmd = {}

    def fake_run(cmd, capture_output, text, timeout):
        captured_cmd["cmd"] = cmd
        captured_cmd["timeout"] = timeout
        manifest_path = tmp_path / "manifest.json"
        manifest_path.write_text(json.dumps({"route": "text", "page_count": 2}))
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(patent.subprocess, "run", fake_run)
    pdf_path = tmp_path / "12089385.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 fake")

    manifest = patent._run_pdf_convert(pdf_path, tmp_path, dpi=1200)

    assert manifest == {"route": "text", "page_count": 2}
    cmd = captured_cmd["cmd"]
    assert cmd[:3] == ["uv", "run", "--project"]
    assert str(patent._ARXIV_DOC_BUILDER_DIR) in cmd
    assert "--extra" in cmd
    assert "pdf" in cmd
    assert "--no-dev" in cmd
    assert str(patent._PATENT_PDF_CONVERT_SCRIPT) in cmd
    assert str(pdf_path) in cmd
    assert "--dpi" in cmd
    assert "1200" in cmd
    assert captured_cmd["timeout"] == patent._CONVERT_TIMEOUT_S


def test_run_pdf_convert_raises_on_nonzero_exit(tmp_path, monkeypatch):
    def fake_run(cmd, capture_output, text, timeout):
        return subprocess.CompletedProcess(cmd, 1, stdout="oops", stderr="bad pdf")

    monkeypatch.setattr(patent.subprocess, "run", fake_run)
    pdf_path = tmp_path / "x.pdf"
    pdf_path.write_bytes(b"fake")
    with pytest.raises(RuntimeError, match="oops"):
        patent._run_pdf_convert(pdf_path, tmp_path)


def test_run_pdf_convert_raises_if_manifest_missing(tmp_path, monkeypatch):
    def fake_run(cmd, capture_output, text, timeout):
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(patent.subprocess, "run", fake_run)
    pdf_path = tmp_path / "x.pdf"
    pdf_path.write_bytes(b"fake")
    with pytest.raises(RuntimeError, match="does not exist"):
        patent._run_pdf_convert(pdf_path, tmp_path)


def test_run_pdf_convert_raises_on_timeout(tmp_path, monkeypatch):
    def fake_run(cmd, capture_output, text, timeout):
        raise subprocess.TimeoutExpired(cmd, timeout)

    monkeypatch.setattr(patent.subprocess, "run", fake_run)
    pdf_path = tmp_path / "x.pdf"
    pdf_path.write_bytes(b"fake")
    with pytest.raises(RuntimeError, match="timed out"):
        patent._run_pdf_convert(pdf_path, tmp_path)


# --- ingest_patent (fetch_fn/convert_fn seam, ingest_document monkeypatched) --


def _capture_ingest(monkeypatch):
    calls: list[dict] = []

    def fake_ingest_document(**kwargs):
        calls.append(kwargs)
        return {"status": "ingested", "document_id": len(calls)}

    monkeypatch.setattr(patent, "ingest_document", fake_ingest_document)
    return calls


def _write_text_route_manifest(tmp_path, front_page_text: str, body: str = "Body text.") -> dict:
    md_path = tmp_path / "converted.md"
    md_path.write_text(body, encoding="utf-8")
    return {
        "route": "text",
        "page_count": 2,
        "markdown_path": str(md_path),
        "front_page_text": front_page_text,
    }


def _vision_route_manifest(image_paths: list[str], dpi: int = 1200, page_count: int = 32) -> dict:
    return {
        "route": "vision",
        "page_count": page_count,
        "image_dir": str(Path(image_paths[0]).parent) if image_paths else "",
        "image_paths": image_paths,
        "dpi": dpi,
        "front_page_text": "",
    }


def test_ingest_patent_text_route_parses_metadata_into_frontmatter(tmp_path, monkeypatch):
    calls = _capture_ingest(monkeypatch)
    manifest = _write_text_route_manifest(tmp_path, _SAMPLE_FRONT_PAGE_TEXT, body="Body content.")

    def fake_fetch(url):
        assert url == "https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/20220192066"
        return b"%PDF-1.4 fake bytes"

    def fake_convert(pdf_path, work_dir, *, dpi):
        assert pdf_path.exists()
        return manifest

    result = patent.ingest_patent(
        "US2022/0192066A1",
        license="US Government Work",
        classification="PUBLIC",
        download_dir=str(tmp_path / "work"),
        fetch_fn=fake_fetch,
        convert_fn=fake_convert,
    )

    assert len(calls) == 1
    captured = calls[0]
    assert captured["source_type"] == "patent"
    assert captured["license"] == "US Government Work"
    assert captured["classification"] == "PUBLIC"
    assert captured["title_override"] == "HIGHLY-CONFORMAL, PLIABLE THIN ELECTROMAGNETIC SKIN"
    assert captured["author"] == (
        "Amir I. Zaghloul, Fairfax, VA (US); Chi-Chih Chen, Columbus, OH (US)"
    )
    assert captured["extra_metadata"]["assignee"] == (
        "United States of America, as represented by the Secretary of the Army"
    )
    assert captured["extra_metadata"]["identifier"] == "20220192066"
    assert captured["extra_metadata"]["kind"] == "publication"
    assert captured["extra_metadata"]["conversion_route"] == "text"
    assert "title" not in captured["extra_metadata"]
    assert "inventors" not in captured["extra_metadata"]

    # The final Markdown handed to ingest_document carries our own
    # patent-shaped frontmatter (never arxiv_metadata's arXiv-shaped one)
    # plus the real extracted body.
    md_text = Path(captured["file_path"]).read_text(encoding="utf-8")
    assert "publication_number: '20220192066'" in md_text or "20220192066" in md_text
    assert "Body content." in md_text

    assert result == {"grant": None, "publication": {"status": "ingested", "document_id": 1}}


def test_ingest_patent_vision_route_notes_no_text_layer_and_lists_images(tmp_path, monkeypatch):
    calls = _capture_ingest(monkeypatch)
    image_paths = [str(tmp_path / "images" / f"page_{i:03d}_full.png") for i in range(1, 4)]
    manifest = _vision_route_manifest(image_paths, dpi=1200, page_count=32)

    result = patent.ingest_patent(
        "12089385",
        license="US Government Work",
        classification="PUBLIC",
        download_dir=str(tmp_path / "work"),
        fetch_fn=lambda url: b"%PDF-1.4 fake",
        convert_fn=lambda pdf_path, work_dir, *, dpi: manifest,
    )

    assert result == {"grant": {"status": "ingested", "document_id": 1}, "publication": None}
    captured = calls[0]
    assert captured["title_override"] is None
    assert captured["author"] is None
    assert captured["extra_metadata"]["conversion_route"] == "vision"

    md_text = Path(captured["file_path"]).read_text(encoding="utf-8")
    assert "no text layer" in md_text.lower()
    assert "normal case" in md_text.lower()
    for image_path in image_paths:
        assert image_path in md_text


def test_ingest_patent_fetches_both_grant_and_related_publication(tmp_path, monkeypatch):
    calls = _capture_ingest(monkeypatch)
    seen_urls: list[str] = []

    def fake_fetch(url):
        seen_urls.append(url)
        return b"%PDF-1.4 fake"

    def fake_convert(pdf_path, work_dir, *, dpi):
        if "12089385" in pdf_path.name:
            return _write_text_route_manifest(work_dir, "", body="Grant body.")
        return _write_text_route_manifest(work_dir, _SAMPLE_FRONT_PAGE_TEXT, body="Pub body.")

    result = patent.ingest_patent(
        "US12089385B2",
        license="US Government Work",
        classification="PUBLIC",
        related_number="US2022/0192066A1",
        download_dir=str(tmp_path / "work"),
        fetch_fn=fake_fetch,
        convert_fn=fake_convert,
    )

    assert result["grant"] is not None
    assert result["publication"] is not None
    assert len(calls) == 2
    assert any(url.endswith("/12089385") for url in seen_urls)
    assert any(url.endswith("/20220192066") for url in seen_urls)


def test_ingest_patent_rejects_related_number_of_same_kind(tmp_path, monkeypatch):
    _capture_ingest(monkeypatch)

    def fake_convert(pdf_path, work_dir, *, dpi):
        return _write_text_route_manifest(work_dir, "")

    with pytest.raises(ValueError, match="sibling kind"):
        patent.ingest_patent(
            "US12089385B2",
            license="x",
            classification="PUBLIC",
            related_number="US11005187B2",  # also a grant number
            download_dir=str(tmp_path),
            fetch_fn=lambda url: b"unused",
            convert_fn=fake_convert,
        )


def test_ingest_patent_rejects_implausible_patent_number(tmp_path):
    with pytest.raises(ValueError):
        patent.ingest_patent(
            "; rm -rf /",
            license="x",
            classification="PUBLIC",
            download_dir=str(tmp_path),
            fetch_fn=lambda url: b"unused",
            convert_fn=lambda pdf_path, work_dir, *, dpi: {"route": "text"},
        )


def test_ingest_patent_supersedes_document_id_applies_only_to_primary(tmp_path, monkeypatch):
    calls = _capture_ingest(monkeypatch)

    def fake_convert(pdf_path, work_dir, *, dpi):
        return _write_text_route_manifest(work_dir, "")

    patent.ingest_patent(
        "US12089385B2",
        license="x",
        classification="PUBLIC",
        related_number="US2022/0192066A1",
        supersedes_document_id=42,
        download_dir=str(tmp_path / "work"),
        fetch_fn=lambda url: b"fake",
        convert_fn=fake_convert,
    )

    by_kind = {call["extra_metadata"]["kind"]: call for call in calls}
    assert by_kind["grant"]["supersedes_document_id"] == 42
    assert by_kind["publication"]["supersedes_document_id"] is None


def test_ingest_patent_creates_tempdir_when_download_dir_omitted(monkeypatch):
    _capture_ingest(monkeypatch)
    seen_work_dirs: list[Path] = []

    def fake_convert(pdf_path, work_dir, *, dpi):
        seen_work_dirs.append(work_dir)
        return _write_text_route_manifest(work_dir, "")

    patent.ingest_patent(
        "12089385",
        license="x",
        classification="PUBLIC",
        fetch_fn=lambda url: b"fake",
        convert_fn=fake_convert,
    )

    assert len(seen_work_dirs) == 1
    assert seen_work_dirs[0].exists()
