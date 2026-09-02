"""Ticket #68: knowledge/sourcing/fcc_ecfr.py, tested at the seam -- a
stubbed `fetch_fn` stands in for the real network GET (dispatched on URL,
since this client makes two calls: titles.json, then the part's full-text
XML), and `ingest_document` is monkeypatched to capture exactly what it was
called with. No network access, no database.

The titles.json/XML byte fixtures below are shaped like (not copied
verbatim from, since eCFR's real title-47 XML runs to megabytes) the real
responses this ticket's own research fetched live from
https://www.ecfr.gov/api/versioner/v1/titles.json and
https://www.ecfr.gov/api/versioner/v1/full/2026-08-31/title-47.xml?part=15
-- see knowledge/sourcing/fcc_ecfr.py's module docstring for that citation.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from knowledge.sourcing import fcc_ecfr

_TITLES_JSON = json.dumps(
    {
        "titles": [
            {"number": 47, "name": "Telecommunication", "up_to_date_as_of": "2026-08-31"},
            {"number": 15, "name": "Commerce and Foreign Trade", "up_to_date_as_of": "2026-08-30"},
        ]
    }
).encode("utf-8")

_PART_15_XML = (
    b'<?xml version="1.0"?>\n'
    b'<DIV5 N="15" TYPE="PART">'
    b"<HEAD>PART 15--RADIO FREQUENCY DEVICES</HEAD>"
    b"<P>No person shall operate an intentional radiator without a license"
    b" issued by the Commission.</P>"
    b"</DIV5>"
)


def _capture(monkeypatch, result=None):
    captured: dict = {}

    def fake_ingest_document(**kwargs):
        captured.update(kwargs)
        return result if result is not None else {"status": "ingested", "document_id": 1}

    monkeypatch.setattr(fcc_ecfr, "ingest_document", fake_ingest_document)
    return captured


def test_ingest_fcc_rule_calls_ingest_document_with_standard_source_type(tmp_path, monkeypatch):
    captured = _capture(monkeypatch)
    fetched_urls: list[str] = []

    def fake_fetch(url: str) -> bytes:
        fetched_urls.append(url)
        return _TITLES_JSON if url == fcc_ecfr._TITLES_URL else _PART_15_XML

    result = fcc_ecfr.ingest_fcc_rule(
        part=15,
        license="public-domain-us-government-work",
        classification="PUBLIC",
        download_dir=str(tmp_path),
        fetch_fn=fake_fetch,
    )

    assert fetched_urls == [
        fcc_ecfr._TITLES_URL,
        "https://www.ecfr.gov/api/versioner/v1/full/2026-08-31/title-47.xml?part=15",
    ]
    assert captured["source_type"] == "standard"
    assert captured["license"] == "public-domain-us-government-work"
    assert captured["classification"] == "PUBLIC"

    text_path = Path(captured["file_path"])
    assert text_path.name == "title-47-part-15.txt"
    text = text_path.read_text(encoding="utf-8")
    assert "RADIO FREQUENCY DEVICES" in text
    assert "No person shall operate" in text
    assert "<DIV5" not in text  # markup stripped, not just concatenated

    assert result == {"status": "ingested", "document_id": 1}


def test_part_97_resolves_a_different_url_and_filename(tmp_path, monkeypatch):
    captured = _capture(monkeypatch)
    fetched_urls: list[str] = []
    part_97_xml = (
        b'<?xml version="1.0"?><DIV5 N="97" TYPE="PART">'
        b"<HEAD>PART 97--AMATEUR RADIO SERVICE</HEAD></DIV5>"
    )

    def fake_fetch(url: str) -> bytes:
        fetched_urls.append(url)
        return _TITLES_JSON if url == fcc_ecfr._TITLES_URL else part_97_xml

    fcc_ecfr.ingest_fcc_rule(
        part=97,
        license="public-domain-us-government-work",
        classification="PUBLIC",
        download_dir=str(tmp_path),
        fetch_fn=fake_fetch,
    )

    assert fetched_urls[1] == (
        "https://www.ecfr.gov/api/versioner/v1/full/2026-08-31/title-47.xml?part=97"
    )
    assert Path(captured["file_path"]).name == "title-47-part-97.txt"


def test_raises_when_title_not_found_in_titles_response(tmp_path):
    def fake_fetch(url: str) -> bytes:
        return json.dumps({"titles": []}).encode("utf-8")

    with pytest.raises(ValueError):
        fcc_ecfr.ingest_fcc_rule(
            part=15,
            license="public-domain-us-government-work",
            classification="PUBLIC",
            download_dir=str(tmp_path),
            fetch_fn=fake_fetch,
        )
