"""Ticket #68: knowledge/sourcing/arxiv.py, tested at the seam -- a
stubbed `fetch_fn` stands in for the real network GET, and `ingest_document`
is monkeypatched to capture exactly what it was called with, mirroring
tests/test_nec2pp.py's fake-executable-not-real-binary pattern applied to a
network fetch instead of a subprocess. No network access, no database.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from knowledge.models import SourceType
from knowledge.provenance import arxiv_preprint_authority_rank, default_authority_rank
from knowledge.sourcing import arxiv


def _capture(monkeypatch, result=None):
    captured: dict = {}

    def fake_ingest_document(**kwargs):
        captured.update(kwargs)
        return result if result is not None else {"status": "ingested", "document_id": 1}

    monkeypatch.setattr(arxiv, "ingest_document", fake_ingest_document)
    return captured


def test_ingest_arxiv_paper_calls_ingest_document_with_paper_source_type(tmp_path, monkeypatch):
    captured = _capture(monkeypatch)
    fetched_urls: list[str] = []

    def fake_fetch(url: str) -> bytes:
        fetched_urls.append(url)
        return b"%PDF-1.4 fake pdf bytes"

    result = arxiv.ingest_arxiv_paper(
        "2401.01234",
        license="cc-by-4.0",
        classification="PUBLIC",
        download_dir=str(tmp_path),
        fetch_fn=fake_fetch,
    )

    assert fetched_urls == ["https://arxiv.org/pdf/2401.01234"]
    assert captured["source_type"] == "paper"
    assert captured["license"] == "cc-by-4.0"
    assert captured["classification"] == "PUBLIC"
    assert Path(captured["file_path"]).read_bytes() == b"%PDF-1.4 fake pdf bytes"
    assert result == {"status": "ingested", "document_id": 1}


def test_ingest_arxiv_paper_overrides_authority_rank_below_peer_reviewed_default(
    tmp_path, monkeypatch
):
    captured = _capture(monkeypatch)

    arxiv.ingest_arxiv_paper(
        "2401.01234",
        license="cc-by-4.0",
        classification="PUBLIC",
        download_dir=str(tmp_path),
        fetch_fn=lambda url: b"stub",
    )

    assert captured["authority_rank_override"] == arxiv_preprint_authority_rank()
    # The whole point of the override: worse (numerically higher) than what
    # a peer-reviewed "paper" document would default to.
    assert captured["authority_rank_override"] > default_authority_rank(SourceType.PAPER)


def test_ingest_arxiv_paper_accepts_old_style_slash_id(tmp_path, monkeypatch):
    captured = _capture(monkeypatch)

    arxiv.ingest_arxiv_paper(
        "cond-mat/0207270",
        license="arxiv-perpetual-non-exclusive",
        classification="PUBLIC",
        download_dir=str(tmp_path),
        fetch_fn=lambda url: b"stub",
    )

    assert Path(captured["file_path"]).name == "cond-mat_0207270.pdf"


def test_ingest_arxiv_paper_rejects_implausible_id(tmp_path):
    with pytest.raises(ValueError):
        arxiv.ingest_arxiv_paper(
            "; rm -rf /",
            license="x",
            classification="PUBLIC",
            download_dir=str(tmp_path),
            fetch_fn=lambda url: b"stub",
        )


def test_arxiv_authority_rank_sits_between_paper_and_internal_history_tiers():
    """Sanity-checks the override constant itself, independent of the
    client: worse than a peer-reviewed paper, but not as low as this
    team's own unreviewed internal design-record history (the
    `design_record` source type's default rank, per knowledge/provenance.py's
    INTERNAL_HISTORY tier)."""
    rank = arxiv_preprint_authority_rank()
    assert default_authority_rank(SourceType.PAPER) < rank
    assert rank < default_authority_rank(SourceType.DESIGN_RECORD)
