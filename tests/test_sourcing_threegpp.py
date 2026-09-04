"""Ticket #68: knowledge/sourcing/threegpp.py, tested at the seam -- a
stubbed `fetch_fn` stands in for the real network GET, and `ingest_document`
is monkeypatched to capture exactly what it was called with. No network
access, no database."""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pytest

from knowledge.sourcing import threegpp


def _capture(monkeypatch, result=None):
    captured: dict = {}

    def fake_ingest_document(**kwargs):
        captured.update(kwargs)
        return result if result is not None else {"status": "ingested", "document_id": 1}

    monkeypatch.setattr(threegpp, "ingest_document", fake_ingest_document)
    return captured


def _make_zip(entries: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, content in entries.items():
            zf.writestr(name, content)
    return buf.getvalue()


def test_ingest_3gpp_spec_calls_ingest_document_with_standard_source_type(tmp_path, monkeypatch):
    captured = _capture(monkeypatch)
    zip_bytes = _make_zip({"38331-h00.docx": b"docx content"})
    fetched_urls: list[str] = []

    def fake_fetch(url: str) -> bytes:
        fetched_urls.append(url)
        return zip_bytes

    result = threegpp.ingest_3gpp_spec(
        "38.331",
        "h00",
        license="3gpp-copyright",
        classification="PUBLIC",
        download_dir=str(tmp_path),
        fetch_fn=fake_fetch,
    )

    assert fetched_urls == ["https://www.3gpp.org/ftp/Specs/archive/38_series/38.331/38331-h00.zip"]
    assert captured["source_type"] == "standard"
    assert captured["license"] == "3gpp-copyright"
    assert captured["classification"] == "PUBLIC"
    assert Path(captured["file_path"]).name == "38331-h00.docx"
    assert Path(captured["file_path"]).read_bytes() == b"docx content"
    assert result == {"status": "ingested", "document_id": 1}


def test_multi_part_spec_number_keeps_its_own_dash_in_the_url(tmp_path, monkeypatch):
    _capture(monkeypatch)
    zip_bytes = _make_zip({"38521-1-h00.docx": b"x"})
    fetched_urls: list[str] = []

    def fake_fetch(url: str) -> bytes:
        fetched_urls.append(url)
        return zip_bytes

    threegpp.ingest_3gpp_spec(
        "38.521-1",
        "h00",
        license="3gpp-copyright",
        classification="PUBLIC",
        download_dir=str(tmp_path),
        fetch_fn=fake_fetch,
    )

    assert fetched_urls == [
        "https://www.3gpp.org/ftp/Specs/archive/38_series/38.521-1/38521-1-h00.zip"
    ]


def test_prefers_docx_over_legacy_doc_and_the_largest_docx_member(tmp_path, monkeypatch):
    captured = _capture(monkeypatch)
    zip_bytes = _make_zip(
        {
            "cover_sheet.docx": b"small",
            "38331-h00.docx": b"the actual much longer spec text" * 10,
            "38331-h00.doc": b"legacy fallback, should be ignored when docx exists",
        }
    )

    threegpp.ingest_3gpp_spec(
        "38.331",
        "h00",
        license="3gpp-copyright",
        classification="PUBLIC",
        download_dir=str(tmp_path),
        fetch_fn=lambda url: zip_bytes,
    )

    assert Path(captured["file_path"]).name == "38331-h00.docx"


def test_falls_back_to_legacy_doc_when_no_docx_present(tmp_path, monkeypatch):
    captured = _capture(monkeypatch)
    zip_bytes = _make_zip({"24008-h90.doc": b"legacy binary word doc content"})

    threegpp.ingest_3gpp_spec(
        "24.008",
        "h90",
        license="3gpp-copyright",
        classification="PUBLIC",
        download_dir=str(tmp_path),
        fetch_fn=lambda url: zip_bytes,
    )

    assert Path(captured["file_path"]).name == "24008-h90.doc"


def test_raises_when_zip_has_no_document_member(tmp_path):
    zip_bytes = _make_zip({"readme.txt": b"nothing useful"})

    with pytest.raises(ValueError):
        threegpp.ingest_3gpp_spec(
            "38.331",
            "h00",
            license="3gpp-copyright",
            classification="PUBLIC",
            download_dir=str(tmp_path),
            fetch_fn=lambda url: zip_bytes,
        )
