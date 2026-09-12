"""knowledge/uspto_search.py: search_uspto_patents (issue #280), tested at
its seam -- given a stubbed `get_api_key`/`search`, assert the parsing,
gating, and error-propagation contract described in that module's own
docstring. No real USPTO_ODP_API_KEY or network access is used or required.

Split out of tests/test_sourcing_patent.py by issue #513, alongside the
module split of the same name: these tests moved here unchanged (only the
import line changed, `from knowledge.sourcing import patent` ->
`from knowledge import uspto_search`) except for
`test_search_uspto_patents_never_calls_ingest_patent_or_ingest_document`,
which still monkeypatches `ingest_document`/`ingest_patent` on
`knowledge.sourcing.patent` -- the module that actually still defines
them -- rather than on `knowledge.uspto_search`, which never imports either
name at all (a direct consequence of the split this test now double-checks:
`search_uspto_patents` cannot reach them through this module's own
namespace, because they aren't in it).
"""

from __future__ import annotations

import pytest

from knowledge import uspto_search
from knowledge.sourcing import patent
from knowledge.sourcing_common import ExternalNetworkToolsDisabledError

# A canned two-record USPTO ODP `/api/v1/patent/applications/search` response,
# shaped per this module's docstring citation: `patentFileWrapperDataBag` is
# the top-level results array, each entry carrying `applicationNumberText`
# plus a nested `applicationMetaData` object with the bibliographic fields
# (`patentNumber`, `inventionTitle`, `filingDate`, `grantDate`,
# `earliestPublicationNumber`, `earliestPublicationDate`). The first record
# is a granted patent (has `patentNumber`); the second is a still-pending
# application that has published but not yet granted (`patentNumber` is
# `None`, only `earliestPublicationNumber` is set) -- both are real states an
# ODP record can be in, and the parser has to produce a usable identifier
# for both.
_ODP_SEARCH_MULTI: dict = {
    "count": 2,
    "patentFileWrapperDataBag": [
        {
            "applicationNumberText": "17123902",
            "applicationMetaData": {
                "patentNumber": "12089385",
                "inventionTitle": "Highly-Conformal, Pliable Thin Electromagnetic Skin",
                "filingDate": "2020-12-16",
                "grantDate": "2024-09-10",
                "earliestPublicationNumber": "US20220192066A1",
                "earliestPublicationDate": "2022-06-16",
            },
        },
        {
            "applicationNumberText": "18999111",
            "applicationMetaData": {
                "patentNumber": None,
                "inventionTitle": "Conformal Frequency Selective Surface Absorber",
                "filingDate": "2025-02-01",
                "grantDate": None,
                "earliestPublicationNumber": "US20250123456A1",
                "earliestPublicationDate": "2025-08-01",
            },
        },
    ],
}

# A real "no matches" ODP response -- an empty results array, not a fetch
# failure.
_ODP_SEARCH_EMPTY: dict = {"count": 0, "patentFileWrapperDataBag": []}


def test_search_uspto_patents_refuses_without_allow_external_network_tools(monkeypatch):
    monkeypatch.delenv("ALLOW_EXTERNAL_NETWORK_TOOLS", raising=False)
    with pytest.raises(ExternalNetworkToolsDisabledError):
        uspto_search.search_uspto_patents(
            "conformal metamaterial skin",
            get_api_key=lambda: "fake-key",
            search=lambda query, api_key, max_results: _ODP_SEARCH_EMPTY,
        )


def test_search_uspto_patents_parses_multi_record_response_in_order(monkeypatch):
    monkeypatch.setenv("ALLOW_EXTERNAL_NETWORK_TOOLS", "true")

    candidates = uspto_search.search_uspto_patents(
        "conformal metamaterial skin",
        get_api_key=lambda: "fake-key",
        search=lambda query, api_key, max_results: _ODP_SEARCH_MULTI,
    )

    assert [c["number"] for c in candidates] == ["US12089385", "US20250123456A1"]

    first = candidates[0]
    assert first["title"] == "Highly-Conformal, Pliable Thin Electromagnetic Skin"
    # A granted record's own grant date wins over its earlier publication
    # date -- it is the more specific, more recent milestone of the two.
    assert first["date"] == "2024-09-10"

    second = candidates[1]
    assert second["title"] == "Conformal Frequency Selective Surface Absorber"
    # Not yet granted: no grantDate, so the record's own publication date is
    # what is offered instead.
    assert second["date"] == "2025-08-01"


def test_search_uspto_patents_candidate_numbers_round_trip_through_normalize(monkeypatch):
    monkeypatch.setenv("ALLOW_EXTERNAL_NETWORK_TOOLS", "true")

    candidates = uspto_search.search_uspto_patents(
        "conformal metamaterial skin",
        get_api_key=lambda: "fake-key",
        search=lambda query, api_key, max_results: _ODP_SEARCH_MULTI,
    )

    assert len(candidates) == 2
    for candidate in candidates:
        # Must not raise -- this is the round-trip the acceptance criteria
        # requires: a candidate handed straight to ingest_patent() must be
        # accepted, never rejected as an implausible number.
        identifier = uspto_search.normalize_patent_number(candidate["number"])
        assert identifier.number


def test_search_uspto_patents_every_candidate_carries_a_total_schema(monkeypatch):
    """Same "unknown stays unknown" discipline as parse_front_page_metadata:
    every candidate always carries a `snippet` key, `None` here because
    ODP's bibliographic search response (confirmed live -- see module
    docstring) does not return a full-text excerpt of the matched
    document -- only front-page metadata."""
    monkeypatch.setenv("ALLOW_EXTERNAL_NETWORK_TOOLS", "true")

    candidates = uspto_search.search_uspto_patents(
        "conformal metamaterial skin",
        get_api_key=lambda: "fake-key",
        search=lambda query, api_key, max_results: _ODP_SEARCH_MULTI,
    )

    for candidate in candidates:
        assert set(candidate) == {"number", "title", "date", "snippet"}
        assert candidate["snippet"] is None


def test_search_uspto_patents_skips_a_record_with_no_usable_number(monkeypatch):
    """A defensive-parsing case, mirroring digikey.py's own
    `_parse_matches`: a record that is neither granted nor published yet (no
    `patentNumber`, no `earliestPublicationNumber`) has nothing
    `normalize_patent_number` can accept, so it is left out rather than
    surfaced with an unusable identifier."""
    monkeypatch.setenv("ALLOW_EXTERNAL_NETWORK_TOOLS", "true")
    raw = {
        "count": 1,
        "patentFileWrapperDataBag": [
            {
                "applicationNumberText": "18999222",
                "applicationMetaData": {
                    "patentNumber": None,
                    "inventionTitle": "Unpublished pending application",
                    "filingDate": "2026-01-01",
                    "earliestPublicationNumber": None,
                },
            }
        ],
    }

    candidates = uspto_search.search_uspto_patents(
        "conformal metamaterial skin",
        get_api_key=lambda: "fake-key",
        search=lambda query, api_key, max_results: raw,
    )

    assert candidates == []


def test_search_uspto_patents_returns_empty_list_on_zero_matches(monkeypatch):
    monkeypatch.setenv("ALLOW_EXTERNAL_NETWORK_TOOLS", "true")

    candidates = uspto_search.search_uspto_patents(
        "zzznomatchzzz",
        get_api_key=lambda: "fake-key",
        search=lambda query, api_key, max_results: _ODP_SEARCH_EMPTY,
    )
    assert candidates == []


def test_search_uspto_patents_propagates_search_error_instead_of_swallowing_it(monkeypatch):
    monkeypatch.setenv("ALLOW_EXTERNAL_NETWORK_TOOLS", "true")

    def failing_search(query, api_key, max_results):
        raise OSError("network unreachable")

    with pytest.raises(OSError, match="network unreachable"):
        uspto_search.search_uspto_patents(
            "conformal metamaterial skin",
            get_api_key=lambda: "fake-key",
            search=failing_search,
        )


def test_search_uspto_patents_propagates_get_api_key_error_instead_of_swallowing_it(monkeypatch):
    """Distinguishable from "no matches" the same way a `search` failure is:
    a missing/invalid credential must never be silently reported as an
    empty result list."""
    monkeypatch.setenv("ALLOW_EXTERNAL_NETWORK_TOOLS", "true")

    def failing_get_api_key():
        raise KeyError("USPTO_ODP_API_KEY")

    def exploding_search(query, api_key, max_results):  # pragma: no cover - must never run
        raise AssertionError("search called despite a missing API key")

    with pytest.raises(KeyError, match="USPTO_ODP_API_KEY"):
        uspto_search.search_uspto_patents(
            "conformal metamaterial skin",
            get_api_key=failing_get_api_key,
            search=exploding_search,
        )


def test_search_uspto_patents_threads_query_and_max_results_into_search(monkeypatch):
    monkeypatch.setenv("ALLOW_EXTERNAL_NETWORK_TOOLS", "true")
    seen: dict = {}

    def fake_search(query, api_key, max_results):
        seen["query"] = query
        seen["api_key"] = api_key
        seen["max_results"] = max_results
        return _ODP_SEARCH_EMPTY

    uspto_search.search_uspto_patents(
        "conformal metamaterial skin",
        max_results=25,
        get_api_key=lambda: "expected-key",
        search=fake_search,
    )

    assert seen == {
        "query": "conformal metamaterial skin",
        "api_key": "expected-key",
        "max_results": 25,
    }


def test_search_uspto_patents_never_calls_ingest_patent_or_ingest_document(monkeypatch):
    """Enforces the acceptance criterion directly: search returns
    candidates, ingestion stays a separate, deliberate call. Both
    `ingest_document` and `ingest_patent` are monkeypatched -- on
    `knowledge.sourcing.patent`, the module that still defines them, since
    `knowledge.uspto_search` does not import either name -- to raise if
    called, so an accidental auto-ingest path fails this test loudly
    instead of passing silently."""
    monkeypatch.setenv("ALLOW_EXTERNAL_NETWORK_TOOLS", "true")

    def fail_if_called(*args, **kwargs):
        raise AssertionError("search_uspto_patents must never ingest anything")

    monkeypatch.setattr(patent, "ingest_document", fail_if_called)
    monkeypatch.setattr(patent, "ingest_patent", fail_if_called)

    candidates = uspto_search.search_uspto_patents(
        "conformal metamaterial skin",
        get_api_key=lambda: "fake-key",
        search=lambda query, api_key, max_results: _ODP_SEARCH_MULTI,
    )

    # Sanity: the search itself ran and found results -- this isn't passing
    # merely because nothing happened.
    assert len(candidates) == 2
