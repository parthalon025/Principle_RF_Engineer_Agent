"""Seam tests for knowledge/nexar.py (ticket #67).

Per this ticket's testing instructions, these exercise the seam -- given a
stubbed/recorded GraphQL response, assert `lookup_nexar_datasheet` calls
`ingest_document` (injected as `ingest`) with the correct arguments -- not
re-testing `ingest_document`'s own internals. No real
NEXAR_CLIENT_ID/SECRET or network access is used or required;
`get_token`/`search`/`download`/`ingest` are all stubbed.
"""

from pathlib import Path

import pytest

from knowledge.nexar import lookup_nexar_datasheet
from knowledge.sourcing_common import ExternalNetworkToolsDisabledError


class _IngestSpy:
    def __init__(self, result: dict | None = None):
        self.calls: list[dict] = []
        self._result = result or {"status": "ingested", "document_id": 42}

    def __call__(self, **kwargs) -> dict:
        self.calls.append(kwargs)
        return self._result


def _nexar_raw(
    mpn: str = "LM358DR",
    manufacturer: str = "Texas Instruments",
    datasheet_url: str | None = "https://example.com/lm358.pdf",
) -> dict:
    """A recorded-shape Nexar `supSearchMpn` GraphQL response, per this
    module's cited primary-source research -- see knowledge/nexar.py module
    docstring."""
    return {
        "data": {
            "supSearchMpn": {
                "results": [
                    {
                        "part": {
                            "mpn": mpn,
                            "manufacturer": {"name": manufacturer},
                            "bestDatasheet": {"url": datasheet_url} if datasheet_url else None,
                        }
                    }
                ]
            }
        }
    }


def _download_stub(dest_path: Path):
    def _download(url: str, dest_dir: Path) -> Path:
        dest_path.write_bytes(b"%PDF-1.4 fake datasheet")
        return dest_path

    return _download


def test_refuses_without_allow_external_network_tools(monkeypatch):
    monkeypatch.delenv("ALLOW_EXTERNAL_NETWORK_TOOLS", raising=False)
    with pytest.raises(ExternalNetworkToolsDisabledError):
        lookup_nexar_datasheet(
            "LM358DR", license="manufacturer-datasheet", classification="PUBLIC"
        )


def test_ok_match_downloads_and_calls_ingest_document_with_correct_arguments(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("ALLOW_EXTERNAL_NETWORK_TOOLS", "true")
    ingest_spy = _IngestSpy(result={"status": "ingested", "document_id": 7})
    pdf_path = tmp_path / "LM358DR.pdf"

    result = lookup_nexar_datasheet(
        "LM358DR",
        license="manufacturer-datasheet",
        classification="PUBLIC",
        get_token=lambda: "fake-token",
        search=lambda part_number, token: _nexar_raw(mpn=part_number),
        download=_download_stub(pdf_path),
        ingest=ingest_spy,
    )

    assert result["status"] == "ok"
    assert result["distributor"] == "nexar"
    assert result["manufacturer"] == "Texas Instruments"
    assert result["manufacturer_part_number"] == "LM358DR"
    assert result["ingest"] == {"status": "ingested", "document_id": 7}

    assert len(ingest_spy.calls) == 1
    call = ingest_spy.calls[0]
    assert call == {
        "file_path": str(pdf_path),
        "source_type": "datasheet",
        "license": "manufacturer-datasheet",
        "classification": "PUBLIC",
    }


def test_no_match_returns_status_without_downloading_or_ingesting(monkeypatch):
    monkeypatch.setenv("ALLOW_EXTERNAL_NETWORK_TOOLS", "true")
    ingest_spy = _IngestSpy()

    result = lookup_nexar_datasheet(
        "NOSUCHPART",
        license="manufacturer-datasheet",
        classification="PUBLIC",
        get_token=lambda: "fake-token",
        search=lambda part_number, token: {"data": {"supSearchMpn": {"results": []}}},
        download=lambda url, dest_dir: pytest.fail("download should not be called"),
        ingest=ingest_spy,
    )

    assert result["status"] == "no_match"
    assert ingest_spy.calls == []


def test_match_with_no_datasheet_url_skips_download_and_ingest(monkeypatch):
    monkeypatch.setenv("ALLOW_EXTERNAL_NETWORK_TOOLS", "true")
    ingest_spy = _IngestSpy()

    result = lookup_nexar_datasheet(
        "LM358DR",
        license="manufacturer-datasheet",
        classification="PUBLIC",
        get_token=lambda: "fake-token",
        search=lambda part_number, token: _nexar_raw(datasheet_url=None),
        download=lambda url, dest_dir: pytest.fail("download should not be called"),
        ingest=ingest_spy,
    )

    assert result["status"] == "no_datasheet"
    assert ingest_spy.calls == []


def test_search_is_called_with_the_token_from_get_token(monkeypatch):
    monkeypatch.setenv("ALLOW_EXTERNAL_NETWORK_TOOLS", "true")
    seen: dict = {}

    def fake_search(part_number: str, token: str) -> dict:
        seen["part_number"] = part_number
        seen["token"] = token
        return {"data": {"supSearchMpn": {"results": []}}}

    lookup_nexar_datasheet(
        "LM358DR",
        license="manufacturer-datasheet",
        classification="PUBLIC",
        get_token=lambda: "expected-token",
        search=fake_search,
    )

    assert seen == {"part_number": "LM358DR", "token": "expected-token"}


def test_part_missing_mpn_is_skipped(monkeypatch):
    """Defensive parsing: a result whose part has no `mpn` must not crash
    and must not be treated as a match (see module docstring's honest
    caveat on the `bestDatasheet` corroboration)."""
    monkeypatch.setenv("ALLOW_EXTERNAL_NETWORK_TOOLS", "true")
    ingest_spy = _IngestSpy()

    raw = {
        "data": {
            "supSearchMpn": {
                "results": [{"part": {"manufacturer": {"name": "Acme"}, "bestDatasheet": None}}]
            }
        }
    }

    result = lookup_nexar_datasheet(
        "LM358DR",
        license="manufacturer-datasheet",
        classification="PUBLIC",
        get_token=lambda: "fake-token",
        search=lambda part_number, token: raw,
        ingest=ingest_spy,
    )

    assert result["status"] == "no_match"
    assert ingest_spy.calls == []
