"""Seam tests for knowledge/digikey.py (ticket #67; ticket #275).

Per this ticket's testing instructions, these exercise the seam -- given a
stubbed/recorded API response, assert `lookup_digikey_datasheet` calls
`ingest_document` (injected as `ingest`) with the correct arguments -- not
re-testing `ingest_document`'s own internals (see tests/test_ingest.py for
that). No real DIGIKEY_CLIENT_ID/SECRET or network access is used or
required; `get_token`/`search`/`download`/`ingest` are all stubbed.

The `lookup_digikey_product_details` tests below (ticket #275) follow the
same stub-injection style, feeding a canned `ProductDetails` JSON fixture
(`_digikey_product_details_raw`) through the seam -- no `download`/`ingest`
step exists for that function (it returns structured data, it does not
fetch a PDF), so only `get_token`/`fetch` are stubbed.
"""

from pathlib import Path

import pytest

from knowledge.digikey import lookup_digikey_datasheet, lookup_digikey_product_details
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


# ProductDetails parametric-attribute and pricing fields (ticket #275) -- see
# docs/tools/digikey.md "Capabilities not yet used here": ProductDetails is a
# distinct endpoint lookup_digikey_datasheet never calls at all (not a field
# on KeywordSearch's response that was merely discarded), returning generic
# per-category parametric attributes and price/quantity breaks.


def _digikey_product_details_raw(
    mpn: str = "LM358DR",
    manufacturer: str = "Texas Instruments",
    datasheet_url: str | None = "https://example.com/lm358.pdf",
    *,
    parameters: list[dict] | None = None,
    standard_pricing: list[dict] | None = None,
    my_pricing: list[dict] | None = None,
    package_name: str | None = "SOIC-8_N",
    category_name: str | None = "Linear - Amplifiers - Instrumentation, OP Amps, Buffer Amps",
) -> dict:
    """A recorded-shape Digi-Key `GET
    /products/v4/search/{productNumber}/productdetails` response, per
    `lookup_digikey_product_details`'s own docstring citation -- see
    knowledge/digikey.py.

    `parameters` defaults to a small, representative slice of the kind of
    generic name/value parametric attributes Digi-Key's catalog actually
    returns for an RF part (frequency range, impedance, tolerance) rather
    than the op-amp example `mpn` above, since this ticket's own concern is
    that parametric data, not this fixture's specific part.
    """
    if parameters is None:
        parameters = [
            {
                "ParameterId": 100,
                "ParameterText": "Frequency Range",
                "ParameterType": "String",
                "ValueId": "1",
                "ValueText": "2.4GHz",
            },
            {
                "ParameterId": 101,
                "ParameterText": "Impedance",
                "ParameterType": "String",
                "ValueId": "2",
                "ValueText": "50 Ohm",
            },
            {
                "ParameterId": 102,
                "ParameterText": "Tolerance",
                "ParameterType": "String",
                "ValueId": "3",
                "ValueText": "±5%",
            },
        ]
    if standard_pricing is None:
        standard_pricing = [
            {"BreakQuantity": 1, "UnitPrice": 0.61, "TotalPrice": 0.61},
            {"BreakQuantity": 10, "UnitPrice": 0.487, "TotalPrice": 4.87},
        ]
    if my_pricing is None:
        my_pricing = [{"BreakQuantity": 1, "UnitPrice": 0.55, "TotalPrice": 0.55}]

    return {
        "Product": {
            "ManufacturerProductNumber": mpn,
            "Manufacturer": {"Id": 469, "Name": manufacturer},
            "DatasheetUrl": datasheet_url,
            "QuantityAvailable": 12345,
            "ProductStatus": {"Id": 0, "Status": "Active"},
            "Discontinued": False,
            "EndOfLife": False,
            "Parameters": parameters,
            "Category": {"CategoryId": 9, "Name": category_name},
            "ProductVariations": [
                {
                    "DigiKeyProductNumber": f"{mpn}-ND",
                    "PackageType": {"Id": 1, "Name": package_name},
                    "StandardPricing": standard_pricing,
                    "MyPricing": my_pricing,
                    "QuantityAvailable": 12345,
                    "MinimumOrderQuantity": 1,
                }
            ],
        }
    }


def test_product_details_refuses_without_allow_external_network_tools(monkeypatch):
    monkeypatch.delenv("ALLOW_EXTERNAL_NETWORK_TOOLS", raising=False)
    with pytest.raises(ExternalNetworkToolsDisabledError):
        lookup_digikey_product_details("LM358DR")


def test_product_details_ok_match_returns_parsed_parameters_and_pricing(monkeypatch):
    monkeypatch.setenv("ALLOW_EXTERNAL_NETWORK_TOOLS", "true")

    result = lookup_digikey_product_details(
        "LM358DR",
        get_token=lambda: "fake-token",
        fetch=lambda part_number, token: _digikey_product_details_raw(mpn=part_number),
    )

    assert result["status"] == "ok"
    assert result["distributor"] == "digikey"
    assert result["manufacturer"] == "Texas Instruments"
    assert result["manufacturer_part_number"] == "LM358DR"
    assert result["digikey_product_number"] == "LM358DR-ND"
    assert result["package"] == "SOIC-8_N"
    assert result["category"] == "Linear - Amplifiers - Instrumentation, OP Amps, Buffer Amps"
    assert result["quantity_available"] == 12345
    assert result["product_status"] == "Active"
    assert result["discontinued"] is False
    assert result["end_of_life"] is False
    assert result["datasheet_url"] == "https://example.com/lm358.pdf"

    assert result["parameters"] == [
        {
            "ParameterId": 100,
            "ParameterText": "Frequency Range",
            "ParameterType": "String",
            "ValueId": "1",
            "ValueText": "2.4GHz",
        },
        {
            "ParameterId": 101,
            "ParameterText": "Impedance",
            "ParameterType": "String",
            "ValueId": "2",
            "ValueText": "50 Ohm",
        },
        {
            "ParameterId": 102,
            "ParameterText": "Tolerance",
            "ParameterType": "String",
            "ValueId": "3",
            "ValueText": "±5%",
        },
    ]
    assert result["price_breaks"] == [
        {"BreakQuantity": 1, "UnitPrice": 0.61, "TotalPrice": 0.61},
        {"BreakQuantity": 10, "UnitPrice": 0.487, "TotalPrice": 4.87},
    ]
    assert result["my_pricing"] == [{"BreakQuantity": 1, "UnitPrice": 0.55, "TotalPrice": 0.55}]


def test_product_details_no_match_returns_status_with_no_pricing_or_parameters(monkeypatch):
    monkeypatch.setenv("ALLOW_EXTERNAL_NETWORK_TOOLS", "true")

    result = lookup_digikey_product_details(
        "NOSUCHPART",
        get_token=lambda: "fake-token",
        fetch=lambda part_number, token: {"SearchLocaleUsed": {}, "Product": None},
    )

    assert result == {
        "status": "no_match",
        "distributor": "digikey",
        "queried_part_number": "NOSUCHPART",
    }


def test_product_details_missing_manufacturer_product_number_is_no_match(monkeypatch):
    """Same defensive-parsing discipline as `_parse_matches`: a `Product`
    object present but missing a usable manufacturer part number must not
    crash, and must not be treated as a match."""
    monkeypatch.setenv("ALLOW_EXTERNAL_NETWORK_TOOLS", "true")

    result = lookup_digikey_product_details(
        "LM358DR",
        get_token=lambda: "fake-token",
        fetch=lambda part_number, token: {"Product": {"Manufacturer": {"Name": "Acme"}}},
    )

    assert result["status"] == "no_match"


def test_product_details_missing_optional_fields_default_to_empty_or_none(monkeypatch):
    """A `Product` with none of the optional Parameters/ProductVariations/
    Category/ProductStatus fields present must parse to empty lists/None
    rather than raising -- these are genuinely optional per the primary
    source (see knowledge/digikey.py's `_parse_product_details` docstring)."""
    monkeypatch.setenv("ALLOW_EXTERNAL_NETWORK_TOOLS", "true")

    result = lookup_digikey_product_details(
        "LM358DR",
        get_token=lambda: "fake-token",
        fetch=lambda part_number, token: {
            "Product": {
                "ManufacturerProductNumber": "LM358DR",
                "Manufacturer": {"Name": "Texas Instruments"},
            }
        },
    )

    assert result["status"] == "ok"
    assert result["parameters"] == []
    assert result["price_breaks"] == []
    assert result["my_pricing"] == []
    assert result["digikey_product_number"] is None
    assert result["package"] is None
    assert result["category"] is None
    assert result["product_status"] is None
    assert result["quantity_available"] is None
    assert result["discontinued"] is None
    assert result["end_of_life"] is None
    assert result["datasheet_url"] is None


def test_product_details_fetch_is_called_with_the_token_from_get_token(monkeypatch):
    monkeypatch.setenv("ALLOW_EXTERNAL_NETWORK_TOOLS", "true")
    seen: dict = {}

    def fake_fetch(part_number: str, token: str) -> dict:
        seen["part_number"] = part_number
        seen["token"] = token
        return {"Product": None}

    lookup_digikey_product_details(
        "LM358DR",
        get_token=lambda: "expected-token",
        fetch=fake_fetch,
    )

    assert seen == {"part_number": "LM358DR", "token": "expected-token"}
