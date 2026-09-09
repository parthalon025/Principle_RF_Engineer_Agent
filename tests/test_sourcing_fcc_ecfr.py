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


# --- search_fcc_rules (issue #279: discovery search, fetch_fn seam,
# candidates only -- never ingests) --------------------------------------
#
# Fixtures below are shaped like (not copied verbatim from) the real
# eCFR Search Service response this ticket's own research fetched live from
# https://www.ecfr.gov/api/search/v1/results?query=EIRP (734 real hits) --
# see knowledge/sourcing/fcc_ecfr.py's search_fcc_rules docstring for that
# citation. Two of the three results below carry a Title-47 hierarchy (the
# only title ingest_fcc_rule's hardcoded XML-fetch path is confirmed to
# handle); the third is deliberately a non-47 title, to exercise the
# client-side title filter the eCFR Search Service itself does not offer
# (passing `title=47` server-side is rejected outright -- confirmed live,
# "Found unpermitted parameter: :title").

_SEARCH_RESULTS_MULTI = json.dumps(
    {
        "results": [
            {
                "hierarchy": {"title": "47", "part": "90", "section": "90.391"},
                "headings": {"section": "Maximum EIRP and antenna height."},
                "full_text_excerpt": "the <strong>EIRP</strong> shall not exceed...",
            },
            {
                # A non-Title-47 hit -- eCFR's Search Service spans every CFR
                # title, not just 47; this one must be dropped, not returned.
                "hierarchy": {"title": "15", "part": "1110", "section": "1110.4"},
                "headings": {"section": "Definitions."},
                "full_text_excerpt": "an <strong>EIRP</strong> limit adopted by...",
            },
            {
                "hierarchy": {"title": "47", "part": "15", "section": "15.209"},
                "headings": {"section": "Radiated emission limits, general requirements."},
                "full_text_excerpt": "field strength of <strong>emissions</strong>...",
            },
        ],
        "meta": {"total_count": 3},
    }
).encode("utf-8")

# A real "no matches" eCFR Search Service response -- not an error.
_SEARCH_RESULTS_EMPTY = json.dumps({"results": [], "meta": {"total_count": 0}}).encode("utf-8")


def test_search_fcc_rules_parses_multi_result_response_in_order():
    candidates = fcc_ecfr.search_fcc_rules("EIRP", fetch_fn=lambda url: _SEARCH_RESULTS_MULTI)

    # The non-Title-47 middle result is excluded -- only the two Title-47
    # hits survive, in the order eCFR returned them.
    assert [c["part"] for c in candidates] == [90, 15]

    first = candidates[0]
    assert first["title"] == 47
    assert first["section"] == "90.391"
    assert first["heading"] == "Maximum EIRP and antenna height."
    assert first["full_text_excerpt"] == "the <strong>EIRP</strong> shall not exceed..."

    second = candidates[1]
    assert second["part"] == 15
    assert second["title"] == 47
    assert second["section"] == "15.209"
    assert second["heading"] == "Radiated emission limits, general requirements."


def test_search_fcc_rules_excludes_non_title_47_results():
    candidates = fcc_ecfr.search_fcc_rules("EIRP", fetch_fn=lambda url: _SEARCH_RESULTS_MULTI)
    assert all(c["title"] == 47 for c in candidates)
    assert 1110 not in [c["part"] for c in candidates]


def test_search_fcc_rules_returns_empty_list_on_zero_matches():
    candidates = fcc_ecfr.search_fcc_rules(
        "zzznomatchzzz", fetch_fn=lambda url: _SEARCH_RESULTS_EMPTY
    )
    assert candidates == []


def test_search_fcc_rules_propagates_fetch_fn_error_instead_of_swallowing_it():
    def failing_fetch(url):
        raise OSError("network unreachable")

    with pytest.raises(OSError, match="network unreachable"):
        fcc_ecfr.search_fcc_rules("EIRP", fetch_fn=failing_fetch)


def test_search_fcc_rules_threads_query_into_url():
    captured_urls: list[str] = []

    def fake_fetch(url):
        captured_urls.append(url)
        return _SEARCH_RESULTS_EMPTY

    fcc_ecfr.search_fcc_rules("spurious emissions", fetch_fn=fake_fetch)

    assert len(captured_urls) == 1
    assert captured_urls[0].startswith("https://www.ecfr.gov/api/search/v1/results?")
    assert "query=spurious" in captured_urls[0]
    # No server-side title filter is ever sent -- eCFR rejects it outright
    # ("Found unpermitted parameter: :title"); filtering happens client-side
    # on the parsed response instead.
    assert "title" not in captured_urls[0]


def test_search_fcc_rules_respects_max_results_after_title_filtering():
    candidates = fcc_ecfr.search_fcc_rules(
        "EIRP", max_results=1, fetch_fn=lambda url: _SEARCH_RESULTS_MULTI
    )
    assert len(candidates) == 1
    assert candidates[0]["part"] == 90


_SEARCH_RESULTS_WITH_COARSE_HIT = json.dumps(
    {
        "results": [
            {
                # A Title-47 hit matched above part level -- e.g. a
                # chapter- or title-level heading -- carries no "part" key
                # at all. ingest_fcc_rule(part, ...) has no meaning to call
                # without one, so this must be dropped like a non-47 title
                # is, not raise and not appear in the returned candidates.
                "hierarchy": {"title": "47"},
                "headings": {"title": "Telecommunication"},
                "full_text_excerpt": "this chapter governs <strong>EIRP</strong>...",
            },
            {
                "hierarchy": {"title": "47", "part": "15", "section": "15.209"},
                "headings": {"section": "Radiated emission limits, general requirements."},
                "full_text_excerpt": "field strength of <strong>emissions</strong>...",
            },
        ],
        "meta": {"total_count": 2},
    }
).encode("utf-8")


def test_search_fcc_rules_drops_title_47_hit_with_no_parseable_part():
    """A Title-47 result matched at a coarser level than "part" (no `part`
    key in its `hierarchy`) is not ingestible via `ingest_fcc_rule(part,
    ...)` and must be dropped rather than raising or producing a candidate
    with a garbage `part` value."""
    candidates = fcc_ecfr.search_fcc_rules(
        "EIRP", fetch_fn=lambda url: _SEARCH_RESULTS_WITH_COARSE_HIT
    )

    assert len(candidates) == 1
    assert candidates[0]["part"] == 15
    assert candidates[0]["section"] == "15.209"


def test_search_fcc_rules_never_calls_ingest_document(monkeypatch):
    """Enforces the same "search returns candidates, a separate call
    ingests one" split as search_arxiv_papers (issue #257) --
    ingest_document is monkeypatched to raise if it is ever called, so any
    accidental auto-ingest path fails this test loudly instead of passing
    silently."""

    def fail_if_called(**kwargs):
        raise AssertionError("search_fcc_rules must never call ingest_document")

    monkeypatch.setattr(fcc_ecfr, "ingest_document", fail_if_called)

    candidates = fcc_ecfr.search_fcc_rules("EIRP", fetch_fn=lambda url: _SEARCH_RESULTS_MULTI)

    # Sanity: the search itself ran and found results -- this isn't passing
    # merely because nothing happened.
    assert len(candidates) == 2
