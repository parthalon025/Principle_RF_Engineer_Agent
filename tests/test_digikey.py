"""Seam tests for knowledge/digikey.py (ticket #67).

Per this ticket's testing instructions, these exercise the seam -- given a
stubbed/recorded API response, assert `lookup_digikey_datasheet` calls
`ingest_document` (injected as `ingest`) with the correct arguments -- not
re-testing `ingest_document`'s own internals (see tests/test_ingest.py for
that). No real DIGIKEY_CLIENT_ID/SECRET or network access is used or
required; `get_token`/`search`/`download`/`ingest` are all stubbed.
"""

from pathlib import Path

import pytest

from knowledge.digikey import lookup_digikey_datasheet, search_digikey_product
from knowledge.sourcing_common import ExternalNetworkToolsDisabledError


class _IngestSpy:
    def __init__(self, result: dict | None = None):
        self.calls: list[dict] = []
        self._result = result or {"status": "ingested", "document_id": 42}

    def __call__(self, **kwargs) -> dict:
        self.calls.append(kwargs)
        return self._result


def _digikey_raw(
    mpn: str = "LM358DR",
    manufacturer: str = "Texas Instruments",
    datasheet_url: str | None = "https://example.com/lm358.pdf",
) -> dict:
    """A recorded-shape Digi-Key /products/v4/search/keyword response, per
    this module's cited primary-source research -- see knowledge/digikey.py
    module docstring."""
    return {
        "Products": [
            {
                "ManufacturerProductNumber": mpn,
                "Manufacturer": {"Name": manufacturer},
                "DatasheetUrl": datasheet_url,
            }
        ]
    }


def _download_stub(dest_path: Path):
    def _download(url: str, dest_dir: Path) -> Path:
        dest_path.write_bytes(b"%PDF-1.4 fake datasheet")
        return dest_path

    return _download


def test_refuses_without_allow_external_network_tools(monkeypatch):
    monkeypatch.delenv("ALLOW_EXTERNAL_NETWORK_TOOLS", raising=False)
    with pytest.raises(ExternalNetworkToolsDisabledError):
        lookup_digikey_datasheet(
            "LM358DR", license="manufacturer-datasheet", classification="PUBLIC"
        )


def test_ok_match_downloads_and_calls_ingest_document_with_correct_arguments(tmp_path, monkeypatch):
    monkeypatch.setenv("ALLOW_EXTERNAL_NETWORK_TOOLS", "true")
    ingest_spy = _IngestSpy(result={"status": "ingested", "document_id": 99})
    pdf_path = tmp_path / "LM358DR.pdf"

    result = lookup_digikey_datasheet(
        "LM358DR",
        license="manufacturer-datasheet",
        classification="PUBLIC",
        get_token=lambda: "fake-token",
        search=lambda part_number, token: _digikey_raw(mpn=part_number),
        download=_download_stub(pdf_path),
        ingest=ingest_spy,
    )

    assert result["status"] == "ok"
    assert result["distributor"] == "digikey"
    assert result["manufacturer"] == "Texas Instruments"
    assert result["manufacturer_part_number"] == "LM358DR"
    assert result["ingest"] == {"status": "ingested", "document_id": 99}

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

    result = lookup_digikey_datasheet(
        "NOSUCHPART",
        license="manufacturer-datasheet",
        classification="PUBLIC",
        get_token=lambda: "fake-token",
        search=lambda part_number, token: {"Products": []},
        download=lambda url, dest_dir: pytest.fail("download should not be called"),
        ingest=ingest_spy,
    )

    assert result["status"] == "no_match"
    assert result["queried_part_number"] == "NOSUCHPART"
    assert ingest_spy.calls == []


def test_match_with_no_datasheet_url_skips_download_and_ingest(monkeypatch):
    monkeypatch.setenv("ALLOW_EXTERNAL_NETWORK_TOOLS", "true")
    ingest_spy = _IngestSpy()

    result = lookup_digikey_datasheet(
        "LM358DR",
        license="manufacturer-datasheet",
        classification="PUBLIC",
        get_token=lambda: "fake-token",
        search=lambda part_number, token: _digikey_raw(datasheet_url=None),
        download=lambda url, dest_dir: pytest.fail("download should not be called"),
        ingest=ingest_spy,
    )

    assert result["status"] == "no_datasheet"
    assert result["manufacturer_part_number"] == "LM358DR"
    assert ingest_spy.calls == []


def test_search_is_called_with_the_token_from_get_token(monkeypatch):
    monkeypatch.setenv("ALLOW_EXTERNAL_NETWORK_TOOLS", "true")
    seen: dict = {}

    def fake_search(part_number: str, token: str) -> dict:
        seen["part_number"] = part_number
        seen["token"] = token
        return {"Products": []}

    lookup_digikey_datasheet(
        "LM358DR",
        license="manufacturer-datasheet",
        classification="PUBLIC",
        get_token=lambda: "expected-token",
        search=fake_search,
    )

    assert seen == {"part_number": "LM358DR", "token": "expected-token"}


# ---------------------------------------------------------------------------
# search_digikey_product (issue #326): the same real keyword-search request
# as lookup_digikey_datasheet, but WITHOUT the download/ingest half -- a
# citation-only match for a human to review, never a step that writes to the
# knowledge base itself. No `download`/`ingest` seam exists to inject here
# because this function never calls either.
# ---------------------------------------------------------------------------


def test_search_refuses_without_allow_external_network_tools(monkeypatch):
    monkeypatch.delenv("ALLOW_EXTERNAL_NETWORK_TOOLS", raising=False)
    with pytest.raises(ExternalNetworkToolsDisabledError):
        search_digikey_product("conductive silver ink")


def test_search_ok_match_returns_product_and_datasheet_without_ingesting(monkeypatch):
    monkeypatch.setenv("ALLOW_EXTERNAL_NETWORK_TOOLS", "true")

    result = search_digikey_product(
        "conductive silver ink",
        get_token=lambda: "fake-token",
        search=lambda query, token: _digikey_raw(
            mpn="8331-14G",
            manufacturer="MG Chemicals",
            datasheet_url="https://example.com/8331-14g.pdf",
        ),
    )

    assert result == {
        "status": "ok",
        "distributor": "digikey",
        "manufacturer": "MG Chemicals",
        "manufacturer_part_number": "8331-14G",
        "datasheet_url": "https://example.com/8331-14g.pdf",
    }


def test_search_no_match_returns_clear_nothing_found_result(monkeypatch):
    monkeypatch.setenv("ALLOW_EXTERNAL_NETWORK_TOOLS", "true")

    result = search_digikey_product(
        "no such ink exists anywhere",
        get_token=lambda: "fake-token",
        search=lambda query, token: {"Products": []},
    )

    assert result == {
        "status": "no_match",
        "distributor": "digikey",
        "queried": "no such ink exists anywhere",
    }


def test_search_match_with_no_datasheet_url_is_reported_as_no_datasheet(monkeypatch):
    monkeypatch.setenv("ALLOW_EXTERNAL_NETWORK_TOOLS", "true")

    result = search_digikey_product(
        "conductive silver ink",
        get_token=lambda: "fake-token",
        search=lambda query, token: _digikey_raw(datasheet_url=None),
    )

    assert result["status"] == "no_datasheet"
    assert result["manufacturer_part_number"] == "LM358DR"


def test_search_never_downloads_or_ingests_anything():
    """search_digikey_product takes no download/ingest parameters at all --
    there is no way to call it and have it write to the knowledge base
    (issue #326 acceptance criterion 3)."""
    import inspect

    params = inspect.signature(search_digikey_product).parameters
    assert "download" not in params
    assert "ingest" not in params


def test_product_missing_manufacturer_product_number_is_skipped(monkeypatch):
    """A defensive-parsing case (see module docstring's honest caveat on the
    response-field-name assumption): a product entry with no usable part
    number must not crash `_parse_matches`, and must not be treated as a
    match."""
    monkeypatch.setenv("ALLOW_EXTERNAL_NETWORK_TOOLS", "true")
    ingest_spy = _IngestSpy()

    raw = {"Products": [{"Manufacturer": {"Name": "Acme"}, "DatasheetUrl": "https://x/y.pdf"}]}

    result = lookup_digikey_datasheet(
        "LM358DR",
        license="manufacturer-datasheet",
        classification="PUBLIC",
        get_token=lambda: "fake-token",
        search=lambda part_number, token: raw,
        ingest=ingest_spy,
    )

    assert result["status"] == "no_match"
    assert ingest_spy.calls == []
