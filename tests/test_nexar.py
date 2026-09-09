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

from knowledge.nexar import lookup_nexar_datasheet, lookup_nexar_part_data
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
        lookup_nexar_datasheet("LM358DR", license="manufacturer-datasheet", classification="PUBLIC")


def test_ok_match_downloads_and_calls_ingest_document_with_correct_arguments(tmp_path, monkeypatch):
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


# --- lookup_nexar_part_data (ticket #276) --------------------------------
#
# `lookup_nexar_datasheet` (above) answers "does this exact part exist, and
# where's its datasheet" -- the same narrow question digikey.py/mouser.py
# already answer. `lookup_nexar_part_data` answers the two things only
# Nexar's cross-distributor aggregation can answer in one query: "who --
# across every distributor -- stocks this part, at what price" (`sellers ->
# offers`) and "what are its actual specs" (`specs`) -- see
# docs/tools/nexar.md's "Capabilities not yet used here" and this module's
# own docstring citations for the confirmed field names these fixtures use.


def _nexar_part_data_raw(
    mpn: str = "LM358DR",
    manufacturer: str = "Texas Instruments",
    datasheet_url: str | None = "https://example.com/lm358.pdf",
    specs: list[dict] | None = None,
    sellers: list[dict] | None = None,
) -> dict:
    """A recorded-shape Nexar `supSearchMpn` GraphQL response carrying the
    extended `specs`/`sellers -> offers` field set (ticket #276) -- see
    `knowledge/nexar.py`'s module docstring for where each sub-field name
    (`attribute.name`, `value`, `displayValue`, `unitsName`, `company.name`,
    `offers.inventoryLevel`, `offers.prices.quantity`/`price`) is confirmed
    against Nexar's own support-site worked query examples."""
    return {
        "data": {
            "supSearchMpn": {
                "results": [
                    {
                        "part": {
                            "mpn": mpn,
                            "manufacturer": {"name": manufacturer},
                            "bestDatasheet": {"url": datasheet_url} if datasheet_url else None,
                            "specs": specs if specs is not None else [],
                            "sellers": sellers if sellers is not None else [],
                        }
                    }
                ]
            }
        }
    }


def test_part_data_refuses_without_allow_external_network_tools(monkeypatch):
    monkeypatch.delenv("ALLOW_EXTERNAL_NETWORK_TOOLS", raising=False)
    with pytest.raises(ExternalNetworkToolsDisabledError):
        lookup_nexar_part_data("LM358DR")


def test_part_data_no_match_returns_status_with_no_specs_or_offers_call(monkeypatch):
    monkeypatch.setenv("ALLOW_EXTERNAL_NETWORK_TOOLS", "true")

    result = lookup_nexar_part_data(
        "NOSUCHPART",
        get_token=lambda: "fake-token",
        search=lambda part_number, token: {"data": {"supSearchMpn": {"results": []}}},
    )

    assert result == {
        "status": "no_match",
        "distributor": "nexar",
        "queried_part_number": "NOSUCHPART",
    }


def test_part_data_search_is_called_with_the_token_from_get_token(monkeypatch):
    monkeypatch.setenv("ALLOW_EXTERNAL_NETWORK_TOOLS", "true")
    seen: dict = {}

    def fake_search(part_number: str, token: str) -> dict:
        seen["part_number"] = part_number
        seen["token"] = token
        return {"data": {"supSearchMpn": {"results": []}}}

    lookup_nexar_part_data(
        "LM358DR",
        get_token=lambda: "expected-token",
        search=fake_search,
    )

    assert seen == {"part_number": "LM358DR", "token": "expected-token"}


def test_part_data_returns_specs_and_multi_distributor_offers(monkeypatch):
    """The exact scenario ticket #276's acceptance criteria call for: a
    single query's response carrying more than one seller and at least one
    spec attribute produces pricing/availability entries for more than one
    distributor and a non-empty specs list -- proving the multi-distributor
    aggregation behavior, not just that the code runs without error."""
    monkeypatch.setenv("ALLOW_EXTERNAL_NETWORK_TOOLS", "true")
    specs = [
        {
            "attribute": {"name": "Frequency Range"},
            "value": "2400000000",
            "displayValue": "2.4 GHz",
            "unitsName": "Hz",
        },
        {
            "attribute": {"name": "Impedance"},
            "value": "50",
            "displayValue": "50 Ohm",
            "unitsName": "Ohm",
        },
    ]
    sellers = [
        {
            "company": {"name": "Digi-Key"},
            "offers": [
                {
                    "inventoryLevel": 15000,
                    "prices": [
                        {"quantity": 1, "price": 0.45},
                        {"quantity": 100, "price": 0.30},
                    ],
                }
            ],
        },
        {
            "company": {"name": "Mouser"},
            "offers": [
                {
                    "inventoryLevel": 8000,
                    "prices": [{"quantity": 1, "price": 0.50}],
                }
            ],
        },
    ]

    result = lookup_nexar_part_data(
        "LM358DR",
        get_token=lambda: "fake-token",
        search=lambda part_number, token: _nexar_part_data_raw(
            mpn=part_number, specs=specs, sellers=sellers
        ),
    )

    assert result["status"] == "ok"
    assert result["distributor"] == "nexar"
    assert result["manufacturer"] == "Texas Instruments"
    assert result["manufacturer_part_number"] == "LM358DR"
    assert result["datasheet_url"] == "https://example.com/lm358.pdf"

    assert result["specs"] == [
        {
            "name": "Frequency Range",
            "value": "2400000000",
            "display_value": "2.4 GHz",
            "units": "Hz",
        },
        {"name": "Impedance", "value": "50", "display_value": "50 Ohm", "units": "Ohm"},
    ]

    assert len(result["offers"]) == 2
    sellers_seen = {offer["seller"] for offer in result["offers"]}
    assert sellers_seen == {"Digi-Key", "Mouser"}
    digikey_offer = next(o for o in result["offers"] if o["seller"] == "Digi-Key")
    assert digikey_offer["stock_level"] == 15000
    assert digikey_offer["price_breaks"] == [
        {"quantity": 1, "price": 0.45},
        {"quantity": 100, "price": 0.30},
    ]
    mouser_offer = next(o for o in result["offers"] if o["seller"] == "Mouser")
    assert mouser_offer["stock_level"] == 8000
    assert mouser_offer["price_breaks"] == [{"quantity": 1, "price": 0.50}]


def test_part_data_with_no_specs_or_sellers_surfaces_empty_lists_not_a_crash(monkeypatch):
    """A matched part with neither field populated (the default shape
    `_nexar_part_data_raw()` already returns) must not crash -- empty lists,
    not a missing key or an exception, matching this module's existing
    defensive-parsing posture (module docstring: a wrong/missing shape
    "fails as 'no match', not a crash")."""
    monkeypatch.setenv("ALLOW_EXTERNAL_NETWORK_TOOLS", "true")

    result = lookup_nexar_part_data(
        "LM358DR",
        get_token=lambda: "fake-token",
        search=lambda part_number, token: _nexar_part_data_raw(mpn=part_number),
    )

    assert result["status"] == "ok"
    assert result["specs"] == []
    assert result["offers"] == []


def test_part_data_part_missing_mpn_is_skipped(monkeypatch):
    """Same defensive posture as `lookup_nexar_datasheet`'s own
    `test_part_missing_mpn_is_skipped`: a result whose part has no `mpn`
    must not crash and must not be treated as a match."""
    monkeypatch.setenv("ALLOW_EXTERNAL_NETWORK_TOOLS", "true")

    raw = {
        "data": {
            "supSearchMpn": {
                "results": [
                    {"part": {"manufacturer": {"name": "Acme"}, "specs": [], "sellers": []}}
                ]
            }
        }
    }

    result = lookup_nexar_part_data(
        "LM358DR",
        get_token=lambda: "fake-token",
        search=lambda part_number, token: raw,
    )

    assert result["status"] == "no_match"
