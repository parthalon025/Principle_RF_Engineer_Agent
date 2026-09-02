"""Seam tests for knowledge/mouser.py (ticket #67).

Per this ticket's testing instructions, these exercise the seam -- given a
stubbed/recorded API response, assert `lookup_mouser_datasheet` calls
`ingest_document` (injected as `ingest`) with the correct arguments -- not
re-testing `ingest_document`'s own internals. No real MOUSER_API_KEY or
network access is used or required; `get_api_key`/`search`/`download`/
`ingest` are all stubbed.
"""

from pathlib import Path

import pytest

from knowledge.mouser import lookup_mouser_datasheet
from knowledge.sourcing_common import ExternalNetworkToolsDisabledError


class _IngestSpy:
    def __init__(self, result: dict | None = None):
        self.calls: list[dict] = []
        self._result = result or {"status": "ingested", "document_id": 42}

    def __call__(self, **kwargs) -> dict:
        self.calls.append(kwargs)
        return self._result


def _mouser_raw(
    mpn: str = "LM358DR",
    manufacturer: str = "Texas Instruments",
    datasheet_url: str | None = "https://example.com/lm358.pdf",
) -> dict:
    """A recorded-shape Mouser /api/v1/search/partnumber response, per this
    module's cited primary-source research -- see knowledge/mouser.py
    module docstring."""
    return {
        "SearchResults": {
            "NumberOfResult": 1,
            "Parts": [
                {
                    "MouserPartNumber": "595-LM358DR",
                    "ManufacturerPartNumber": mpn,
                    "Manufacturer": manufacturer,
                    "DataSheetUrl": datasheet_url,
                }
            ],
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
        lookup_mouser_datasheet(
            "LM358DR", license="manufacturer-datasheet", classification="PUBLIC"
        )


def test_ok_match_downloads_and_calls_ingest_document_with_correct_arguments(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("ALLOW_EXTERNAL_NETWORK_TOOLS", "true")
    ingest_spy = _IngestSpy(result={"status": "ingested", "document_id": 100})
    pdf_path = tmp_path / "LM358DR.pdf"

    result = lookup_mouser_datasheet(
        "LM358DR",
        license="manufacturer-datasheet",
        classification="INTERNAL",
        get_api_key=lambda: "fake-api-key",
        search=lambda part_number, api_key: _mouser_raw(mpn=part_number),
        download=_download_stub(pdf_path),
        ingest=ingest_spy,
    )

    assert result["status"] == "ok"
    assert result["distributor"] == "mouser"
    assert result["manufacturer"] == "Texas Instruments"
    assert result["manufacturer_part_number"] == "LM358DR"
    assert result["ingest"] == {"status": "ingested", "document_id": 100}

    assert len(ingest_spy.calls) == 1
    call = ingest_spy.calls[0]
    assert call == {
        "file_path": str(pdf_path),
        "source_type": "datasheet",
        "license": "manufacturer-datasheet",
        "classification": "INTERNAL",
    }


def test_no_match_returns_status_without_downloading_or_ingesting(monkeypatch):
    monkeypatch.setenv("ALLOW_EXTERNAL_NETWORK_TOOLS", "true")
    ingest_spy = _IngestSpy()

    result = lookup_mouser_datasheet(
        "NOSUCHPART",
        license="manufacturer-datasheet",
        classification="PUBLIC",
        get_api_key=lambda: "fake-api-key",
        search=lambda part_number, api_key: {"SearchResults": {"NumberOfResult": 0, "Parts": []}},
        download=lambda url, dest_dir: pytest.fail("download should not be called"),
        ingest=ingest_spy,
    )

    assert result["status"] == "no_match"
    assert ingest_spy.calls == []


def test_match_with_no_datasheet_url_skips_download_and_ingest(monkeypatch):
    monkeypatch.setenv("ALLOW_EXTERNAL_NETWORK_TOOLS", "true")
    ingest_spy = _IngestSpy()

    result = lookup_mouser_datasheet(
        "LM358DR",
        license="manufacturer-datasheet",
        classification="PUBLIC",
        get_api_key=lambda: "fake-api-key",
        search=lambda part_number, api_key: _mouser_raw(datasheet_url=None),
        download=lambda url, dest_dir: pytest.fail("download should not be called"),
        ingest=ingest_spy,
    )

    assert result["status"] == "no_datasheet"
    assert ingest_spy.calls == []


def test_search_is_called_with_the_key_from_get_api_key(monkeypatch):
    monkeypatch.setenv("ALLOW_EXTERNAL_NETWORK_TOOLS", "true")
    seen: dict = {}

    def fake_search(part_number: str, api_key: str) -> dict:
        seen["part_number"] = part_number
        seen["api_key"] = api_key
        return {"SearchResults": {"Parts": []}}

    lookup_mouser_datasheet(
        "LM358DR",
        license="manufacturer-datasheet",
        classification="PUBLIC",
        get_api_key=lambda: "expected-key",
        search=fake_search,
    )

    assert seen == {"part_number": "LM358DR", "api_key": "expected-key"}


def test_identity_uses_manufacturer_part_number_not_mouser_catalog_number(tmp_path, monkeypatch):
    """CONTEXT.md: Component identity is the manufacturer's own part
    number, never a distributor's own catalog/SKU code -- Mouser's
    `MouserPartNumber` ("595-LM358DR" here) must never leak into the
    returned identity."""
    monkeypatch.setenv("ALLOW_EXTERNAL_NETWORK_TOOLS", "true")
    pdf_path = tmp_path / "LM358DR.pdf"

    result = lookup_mouser_datasheet(
        "LM358DR",
        license="manufacturer-datasheet",
        classification="PUBLIC",
        get_api_key=lambda: "fake-api-key",
        search=lambda part_number, api_key: _mouser_raw(mpn="LM358DR"),
        download=_download_stub(pdf_path),
        ingest=_IngestSpy(),
    )

    assert result["manufacturer_part_number"] == "LM358DR"
    assert "595-LM358DR" not in result.values()
