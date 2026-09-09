"""Ticket #68: knowledge/sourcing/etsi.py, tested at the seam -- a stubbed
`fetch_fn` stands in for the real network GET, and `ingest_document` is
monkeypatched to capture exactly what it was called with. No network
access, no database."""

from __future__ import annotations

from pathlib import Path

import pytest

from knowledge.sourcing import etsi

_REAL_DELIVER_URL = (
    "https://www.etsi.org/deliver/etsi_ts/119600_119699/119612/02.02.01_60/ts_119612v020201p.pdf"
)


def _capture(monkeypatch, result=None):
    captured: dict = {}

    def fake_ingest_document(**kwargs):
        captured.update(kwargs)
        return result if result is not None else {"status": "ingested", "document_id": 1}

    monkeypatch.setattr(etsi, "ingest_document", fake_ingest_document)
    return captured


def test_ingest_etsi_standard_calls_ingest_document_with_standard_source_type(
    tmp_path, monkeypatch
):
    captured = _capture(monkeypatch)
    fetched_urls: list[str] = []

    def fake_fetch(url: str) -> bytes:
        fetched_urls.append(url)
        return b"%PDF-1.4 fake etsi pdf"

    result = etsi.ingest_etsi_standard(
        _REAL_DELIVER_URL,
        license="etsi-copyright",
        classification="PUBLIC",
        download_dir=str(tmp_path),
        fetch_fn=fake_fetch,
    )

    assert fetched_urls == [_REAL_DELIVER_URL]
    assert captured["source_type"] == "standard"
    assert captured["license"] == "etsi-copyright"
    assert captured["classification"] == "PUBLIC"
    assert Path(captured["file_path"]).name == "ts_119612v020201p.pdf"
    assert Path(captured["file_path"]).read_bytes() == b"%PDF-1.4 fake etsi pdf"
    assert result == {"status": "ingested", "document_id": 1}


def test_rejects_a_url_on_a_different_host(tmp_path):
    with pytest.raises(ValueError):
        etsi.ingest_etsi_standard(
            "https://evil.example.com/deliver/etsi_ts/foo.pdf",
            license="x",
            classification="PUBLIC",
            download_dir=str(tmp_path),
            fetch_fn=lambda url: b"stub",
        )


def test_rejects_an_etsi_url_outside_the_deliver_path(tmp_path):
    with pytest.raises(ValueError):
        etsi.ingest_etsi_standard(
            "https://www.etsi.org/standards-search?query=foo",
            license="x",
            classification="PUBLIC",
            download_dir=str(tmp_path),
            fetch_fn=lambda url: b"stub",
        )


# issue #284: ingest_etsi_ipr_declaration -- the SR 000 314 IPR/FRAND
# declaration register, served dynamically from a distinct subdomain
# (ipr.etsi.org, not www.etsi.org) rather than as a static per-document PDF
# path. Confirmed live during this ticket's research: an individual
# declaration's URL is `https://ipr.etsi.org/IPRDetails.aspx?IPRD_ID=<n>&
# IPRD_TYPE_ID=<n>&MODE=<n>` -- e.g. Google's own crawler has indexed
# https://ipr.etsi.org/IPRDetails.aspx?IPRD_ID=198&IPRD_TYPE_ID=2&MODE=2
# with no `sessionkey` parameter at all, which is decisive: Googlebot holds
# no ETSI session, so a page it can index and cache must render without one
# -- `sessionkey` is a same-session browsing convenience the search UI adds
# to its own links, not a required credential. This matches ETSI's own
# "User Guide for Anonymous Users" for this database, which documents
# anonymous (unauthenticated) read-only access to declarations in
# "reflected" state.
_REAL_IPR_DECLARATION_URL = "https://ipr.etsi.org/IPRDetails.aspx?IPRD_ID=198&IPRD_TYPE_ID=2&MODE=2"


def test_ingest_etsi_ipr_declaration_calls_ingest_document_with_declared_against_metadata(
    tmp_path, monkeypatch
):
    captured = _capture(monkeypatch)
    fetched_urls: list[str] = []

    def fake_fetch(url: str) -> bytes:
        fetched_urls.append(url)
        return b"%PDF-1.4 fake ipr declaration pdf"

    result = etsi.ingest_etsi_ipr_declaration(
        _REAL_IPR_DECLARATION_URL,
        declared_against_document_id=42,
        license="etsi-copyright",
        classification="PUBLIC",
        download_dir=str(tmp_path),
        fetch_fn=fake_fetch,
    )

    assert fetched_urls == [_REAL_IPR_DECLARATION_URL]
    assert captured["source_type"] == "standard"
    assert captured["license"] == "etsi-copyright"
    assert captured["classification"] == "PUBLIC"
    assert captured["extra_metadata"] == {"declared_against_document_id": 42}
    assert Path(captured["file_path"]).read_bytes() == b"%PDF-1.4 fake ipr declaration pdf"
    assert result == {"status": "ingested", "document_id": 1}


def test_ingest_etsi_ipr_declaration_rejects_a_url_on_a_different_host(tmp_path):
    with pytest.raises(ValueError):
        etsi.ingest_etsi_ipr_declaration(
            "https://evil.example.com/IPRDetails.aspx?IPRD_ID=198",
            declared_against_document_id=42,
            license="x",
            classification="PUBLIC",
            download_dir=str(tmp_path),
            fetch_fn=lambda url: b"stub",
        )


def test_ingest_etsi_ipr_declaration_rejects_an_ipr_host_url_outside_the_details_path(tmp_path):
    # Right host (ipr.etsi.org), wrong page -- the human-facing search form
    # itself, not a specific declaration's detail page. Mirrors
    # test_rejects_an_etsi_url_outside_the_deliver_path above.
    with pytest.raises(ValueError):
        etsi.ingest_etsi_ipr_declaration(
            "https://ipr.etsi.org/Search.aspx?query=foo",
            declared_against_document_id=42,
            license="x",
            classification="PUBLIC",
            download_dir=str(tmp_path),
            fetch_fn=lambda url: b"stub",
        )
