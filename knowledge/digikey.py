"""Digi-Key Product Information API v4 thin client (ticket #67).

PRIMARY SOURCE, verified against Digi-Key's own developer docs directly (via
live fetch of developer.digikey.com pages plus corroborating working-code
examples), per CLAUDE.md's rule against reconstructing an external tool's
API surface from memory:

  - Auth: OAuth 2.0 "2 Legged Flow" (`client_credentials` grant), documented
    at developer.digikey.com/tutorials-and-resources/oauth-20-2-legged-flow.
    POST `application/x-www-form-urlencoded` to the token endpoint with
    `client_id`, `client_secret`, `grant_type=client_credentials`; response
    is `{"access_token": ..., "expires_in": ..., "token_type": "Bearer"}`.
    Production token endpoint: `https://api.digikey.com/v1/oauth2/token`.
    Sandbox: `https://sandbox-api.digikey.com/v1/oauth2/token` (this
    module's `DIGIKEY_SANDBOX=true` env var selects it).
  - API requests need BOTH the bearer token AND a separate
    `X-DIGIKEY-Client-Id` header carrying the same client id -- confirmed
    by a working third-party integration
    (briankhuu.com/blog/2024/09/17/playing-around-with-digikey-api/) whose
    author specifically flagged the client-id header as required in
    addition to the token, even though Digi-Key's own docs page reads as
    if the header alone (without the token) might be sufficient.
  - Keyword/part-number search: `POST /products/v4/search/keyword`, JSON
    body `{"Keywords": "<part number>"}`, headers
    `Authorization: Bearer <token>`, `X-DIGIKEY-Client-Id: <client_id>`,
    `Content-Type`/`Accept: application/json` -- same source as above, and
    matching the endpoint Digi-Key's own portal names at
    developer.digikey.com/products/product-information-v4/productsearch.

HONEST CAVEAT: no DIGIKEY_CLIENT_ID/DIGIKEY_CLIENT_SECRET is registered in
this environment and this client has NOT been run against the real API
end-to-end -- treat any result as unverified end-to-end until it has been
run against the real API at least once (same posture this repo's
NEC2++/openEMS/HFSS adapters already state for their own unverified-in-
sandbox status). The exact top-level response JSON key holding the product
list (taken here as `"Products"`, each entry carrying
`"Manufacturer": {"Name": ...}`, `"ManufacturerProductNumber"`, and
`"DatasheetUrl"`) is inferred from the snake_case attribute names of
Digi-Key's own generated OpenAPI Python client
(`response.products[i].manufacturer_product_number` etc., per the
`digikey-apiv4` PyPI package's documented usage) rather than read directly
off a raw JSON response -- reasonably likely, but NOT independently
confirmed against a live call. `_parse_matches` below is written
defensively (skips any product missing a usable part number rather than
raising) so a wrong assumption here fails as "no match", not a crash.

ADDENDUM (ticket #275) -- `lookup_digikey_product_details()`/`ProductDetails`:

developer.digikey.com/products/product-information-v4/productsearch/
productdetails itself is a JS-rendered navigation page carrying no schema
body (confirmed by a live fetch attempt for this ticket -- only a
breadcrumb and a "Download Swagger File" link render server-side, per this
repo's own established pattern of naming exactly which page was a dead
end, e.g. docs/tools/mouser.md's Swagger-UI-behind-a-login-wall note).
Corroborated instead, same evidentiary tier as the `digikey-apiv4` PyPI
citation above, from `Innovoltive/digikey_apiv4` (github.com/Innovoltive/
digikey_apiv4) -- a swagger-codegen-generated client (its own repo carries
a `.swagger-codegen/` generator-config directory, i.e. generated directly
from Digi-Key's real OpenAPI spec, not hand-typed) whose docs/*.md pages
were fetched directly for this ticket:

  - `docs/ProductSearchApi.md`: `product_details` is `GET
    /search/{productNumber}/productdetails` (relative to
    `https://api.digikey.com/products/v4`), requiring the same
    `X-DIGIKEY-Client-Id` header as KeywordSearch and returning a
    `ProductDetails` object; documented as "Retrieve detailed product
    information including real time pricing and availability" -- i.e.
    pricing is embedded in this one response, not a separate call (see
    discrepancy note below). The `Authorization: Bearer <token>` header is
    NOT listed among this method's own per-call parameters (only the
    client-id header, plus optional locale headers, are) -- inferred by
    symmetry with KeywordSearch's confirmed requirement for it, since both
    endpoints share the same module-level 2-legged OAuth2 flow (see
    top-of-file docstring); NOT independently confirmed for this specific
    endpoint.
  - `docs/ProductDetails.md`: response envelope is
    `{"SearchLocaleUsed": ..., "Product": {...}}` (both optional).
  - `docs/Product.md`: the `Product` object carries (among ~25 other
    fields) `ManufacturerProductNumber`, `Manufacturer`, `DatasheetUrl`,
    `QuantityAvailable`, `ProductStatus` ({"Id", "Status"}), `Discontinued`,
    `EndOfLife`, `Category` (a `CategoryNode`), `ProductVariations`, and
    `Parameters` -- a flat list of generic per-category attribute records
    (Digi-Key does not expose a fixed "Frequency"/"Impedance"/"Tolerance"
    JSON field; those are catalog category metadata that varies by part
    type, carried generically -- see `ParameterValue.md` below).
  - `docs/ParameterValue.md`: each `Parameters[]` entry carries
    `ParameterId`, `ParameterText` (the attribute's name, e.g. "Frequency
    Range"), `ParameterType`, `ValueId`, `ValueText` (the attribute's
    value, e.g. "2.4GHz").
  - `docs/ProductVariation.md`: each `ProductVariations[]` entry (one per
    packaging option -- cut tape vs. reel, etc.) carries
    `DigiKeyProductNumber`, `PackageType` ({"Id", "Name"}),
    `StandardPricing` (list price/quantity breaks) and `MyPricing` (the
    "MyPricing" contract pricing docs/tools/digikey.md already names,
    dependent on the authenticated account/locale) -- both lists of
    `PriceBreak`.
  - `docs/PriceBreak.md`: `BreakQuantity`, `UnitPrice`, `TotalPrice`.
  - `docs/CategoryNode.md`: `CategoryId`, `ParentId`, `Name`, plus
    browsing/SEO fields not read here.
  - `docs/PackageType.md`, `docs/Manufacturer.md`: both just `{"Id",
    "Name"}` -- the `Manufacturer` shape matches what `_parse_matches`
    above already assumes.

DISCREPANCY vs. `docs/tools/digikey.md`: that report's "Full capabilities"
section names `ProductDetails` and `ProductPricing` as two separate GET
endpoints. This ticket's own corroborating source (the
`Innovoltive/digikey_apiv4` client's `ProductSearchApi.md` method list --
`associations`, `categories`, `categories_by_id`, `digi_reel_pricing`,
`keyword_search`, `manufacturers`, `media`, `package_type_by_quantity`,
`product_details`, `recommended_products`, `substitutions`) has no
`product_pricing` method at all; `product_details` is the one documented
as already returning pricing. Trusting that evidence over the doc report
per this ticket's own instruction, `lookup_digikey_product_details()`
below calls only `ProductDetails` and reads `StandardPricing`/`MyPricing`
off its embedded `ProductVariations` -- no second call is made. Whether a
distinct `ProductPricing` endpoint additionally exists and simply isn't
wrapped by this one community client remains UNCONFIRMED; if a live call
ever proves `ProductDetails` does NOT carry current pricing after all,
that would be the next thing to check.

Same HONEST CAVEAT as above applies to all of this: no live credential or
network access here, so none of it has been run against the real API.
`_parse_product_details` is written with the same defensive posture as
`_parse_matches` -- a missing/absent field reads as `None`/`[]`, never
raises.
"""

from __future__ import annotations

import json
import os
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlencode

from knowledge.ingest import ingest_document
from knowledge.sourcing_common import (
    ComponentMatch,
    download_to_file,
    make_workdir,
    require_external_network_tools_enabled,
)

_TOKEN_URL = "https://api.digikey.com/v1/oauth2/token"
_TOKEN_URL_SANDBOX = "https://sandbox-api.digikey.com/v1/oauth2/token"
_SEARCH_URL = "https://api.digikey.com/products/v4/search/keyword"
_SEARCH_URL_SANDBOX = "https://sandbox-api.digikey.com/products/v4/search/keyword"
_PRODUCT_DETAILS_URL = "https://api.digikey.com/products/v4/search/{product_number}/productdetails"
_PRODUCT_DETAILS_URL_SANDBOX = (
    "https://sandbox-api.digikey.com/products/v4/search/{product_number}/productdetails"
)

GetTokenFn = Callable[[], str]
SearchFn = Callable[[str, str], dict[str, Any]]
DownloadFn = Callable[[str, Path], Path]
IngestFn = Callable[..., dict[str, Any]]
ProductDetailsFn = Callable[[str, str], dict[str, Any]]


def _use_sandbox() -> bool:
    return os.environ.get("DIGIKEY_SANDBOX", "false").strip().lower() == "true"


def _get_access_token() -> str:
    """Real OAuth2 client_credentials token request -- see module docstring
    citation. This is the actual network I/O boundary, not exercised
    directly by this repo's tests (no live DIGIKEY_CLIENT_ID/SECRET or
    network access here); `lookup_digikey_datasheet` takes `get_token` as
    an injectable parameter defaulting to this function."""
    client_id = os.environ["DIGIKEY_CLIENT_ID"]
    client_secret = os.environ["DIGIKEY_CLIENT_SECRET"]
    url = _TOKEN_URL_SANDBOX if _use_sandbox() else _TOKEN_URL
    data = urlencode(
        {"client_id": client_id, "client_secret": client_secret, "grant_type": "client_credentials"}
    ).encode()
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/x-www-form-urlencoded"}, method="POST"
    )
    with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310 -- real OAuth2 token call
        payload = json.loads(resp.read())
    return payload["access_token"]


def _search_by_part_number(part_number: str, access_token: str) -> dict[str, Any]:
    """Real keyword-search POST -- see module docstring citation."""
    client_id = os.environ["DIGIKEY_CLIENT_ID"]
    url = _SEARCH_URL_SANDBOX if _use_sandbox() else _SEARCH_URL
    body = json.dumps({"Keywords": part_number}).encode()
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Authorization": f"Bearer {access_token}",
            "X-DIGIKEY-Client-Id": client_id,
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310 -- real search call
        return json.loads(resp.read())


def _fetch_product_details(part_number: str, access_token: str) -> dict[str, Any]:
    """Real `ProductDetails` GET -- see module docstring's ticket #275
    addendum. This is the actual network I/O boundary, not exercised
    directly by this repo's tests (no live DIGIKEY_CLIENT_ID/SECRET or
    network access here); `lookup_digikey_product_details` takes `fetch`
    as an injectable parameter defaulting to this function, mirroring
    `_search_by_part_number`'s role for `lookup_digikey_datasheet`."""
    client_id = os.environ["DIGIKEY_CLIENT_ID"]
    base = _PRODUCT_DETAILS_URL_SANDBOX if _use_sandbox() else _PRODUCT_DETAILS_URL
    url = base.format(product_number=quote(part_number, safe=""))
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {access_token}",
            "X-DIGIKEY-Client-Id": client_id,
            "Accept": "application/json",
        },
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310 -- real product-details call
        return json.loads(resp.read())


def _nested_field(value: Any, key: str = "Name", default: Any = None) -> Any:
    """Digi-Key represents several attributes -- `Manufacturer`, `Category`,
    `ProductStatus`, `PackageType` (see module docstring's ticket #275
    addendum) -- as a nested `{"Id": ..., <key>: ...}` object rather than a
    bare scalar. Unwrap that shape defensively, the same way `_parse_matches`
    always has: if `value` is a dict, read `key` off it; otherwise return
    `default`. Shared by `_parse_matches` and `_parse_product_details` below
    so this ternary isn't repeated once per field."""
    return value.get(key) if isinstance(value, dict) else default


def _parse_matches(raw: dict[str, Any]) -> list[ComponentMatch]:
    """See module docstring's honest caveat on the `"Products"`/PascalCase
    field-name assumption."""
    matches: list[ComponentMatch] = []
    for product in raw.get("Products") or []:
        mpn = product.get("ManufacturerProductNumber")
        if not mpn:
            continue
        mfr = product.get("Manufacturer")
        mfr_name = _nested_field(mfr, default=mfr)
        matches.append(
            ComponentMatch(
                distributor="digikey",
                manufacturer=mfr_name,
                manufacturer_part_number=mpn,
                datasheet_url=product.get("DatasheetUrl"),
            )
        )
    return matches


def lookup_digikey_datasheet(
    part_number: str,
    *,
    license: str,
    classification: str,
    download_dir: str | None = None,
    get_token: GetTokenFn = _get_access_token,
    search: SearchFn = _search_by_part_number,
    download: DownloadFn = download_to_file,
    ingest: IngestFn = ingest_document,
) -> dict[str, Any]:
    """Search Digi-Key for `part_number`, download its datasheet PDF, and
    ingest it via the unchanged `ingest_document(source_type='datasheet')`
    pipeline (`knowledge/ingest.py`).

    Refuses to run unless ALLOW_EXTERNAL_NETWORK_TOOLS=true (see
    `knowledge/sourcing_common.py` and `.env.example`) -- this makes a
    real, credentialed call to a third party the moment it runs, same
    posture as this repo's other real-world-reaching tools.

    `get_token`/`search`/`download`/`ingest` are the real I/O by default;
    tests inject stubs for all four to verify this function's own
    argument-passing/response-parsing logic against a canned API response,
    with no live DIGIKEY_CLIENT_ID/SECRET or network access (see
    tests/test_digikey.py) -- mirroring `knowledge/extract.py`'s
    extract_local/extract_external injection pattern.

    Returns `{"status": "no_match" | "no_datasheet" | "ok", ...}`.
    `"no_match"`: Digi-Key returned zero products for this part number.
    `"no_datasheet"`: a product matched but had no datasheet URL to fetch.
    `"ok"`: the first match's datasheet was downloaded and ingested; the
    manufacturer/manufacturer_part_number Digi-Key reported are included so
    `knowledge.component_resolution` can reconcile this hit against
    Mouser's/Nexar's for the same physical part.
    """
    require_external_network_tools_enabled("Digi-Key")

    token = get_token()
    raw = search(part_number, token)
    matches = _parse_matches(raw)
    if not matches:
        return {"status": "no_match", "distributor": "digikey", "queried_part_number": part_number}

    best = matches[0]
    if not best.datasheet_url:
        return {
            "status": "no_datasheet",
            "distributor": "digikey",
            "manufacturer": best.manufacturer,
            "manufacturer_part_number": best.manufacturer_part_number,
        }

    dest_dir = Path(download_dir) if download_dir else make_workdir("digikey_")
    file_path = download(best.datasheet_url, dest_dir)
    ingest_result = ingest(
        file_path=str(file_path),
        source_type="datasheet",
        license=license,
        classification=classification,
    )
    return {
        "status": "ok",
        "distributor": "digikey",
        "manufacturer": best.manufacturer,
        "manufacturer_part_number": best.manufacturer_part_number,
        "datasheet_url": best.datasheet_url,
        "ingest": ingest_result,
    }


@dataclass(frozen=True)
class _DigikeyProductDetails:
    """The parametric-attribute and pricing fields Digi-Key's `ProductDetails`
    endpoint returns (ticket #275, docs/tools/digikey.md's "Capabilities not
    yet used here") that don't belong on the shared `ComponentMatch`
    (`knowledge/sourcing_common.py`, kept limited to the four identity
    fields every distributor can report -- see that dataclass's own
    docstring). Kept local to this module and this function's own result
    dict, per this ticket's own instruction not to touch `ComponentMatch`
    or the Mouser/Nexar clients -- the same "new fields stay local,
    `ComponentMatch` stays untouched" principle
    `knowledge.mouser._MouserPricingAndCompliance` (ticket #274) follows.

    NOT structurally identical to that sibling, though: Mouser's dataclass
    carries only its ten new fields and comes back paired in a tuple
    alongside an unmodified `ComponentMatch` (`knowledge/mouser.py`'s
    `_parse_matches` returns `list[tuple[ComponentMatch,
    _MouserPricingAndCompliance]]`), because ticket #274 extended that
    module's existing `_parse_matches`/`lookup_mouser_datasheet` pipeline in
    place. `lookup_digikey_product_details` below is a separate lookup path
    against a different endpoint, not an extension of this module's own
    `_parse_matches`/`lookup_digikey_datasheet` pipeline -- there is no
    `ComponentMatch` produced by this call to pair with, so
    `_DigikeyProductDetails` re-declares `manufacturer`/
    `manufacturer_part_number` itself instead.

    `parameters`/`price_breaks`/`my_pricing` are passed through as raw
    lists of dicts in Digi-Key's own PascalCase field names (ParameterId/
    ParameterText/ValueId/ValueText; BreakQuantity/UnitPrice/TotalPrice),
    not re-wrapped in per-field dataclasses -- Digi-Key's `Parameters` are
    a generic, per-category attribute list (frequency/impedance/tolerance/
    package are catalog metadata that varies by part type, not a fixed
    JSON schema; see module docstring's ticket #275 addendum), so there is
    no fixed set of named fields to parse them into, and doing so would
    invent field names never confirmed against a live response.
    """

    manufacturer: str | None
    manufacturer_part_number: str
    digikey_product_number: str | None
    package: str | None
    category: str | None
    parameters: list[dict[str, Any]]
    price_breaks: list[dict[str, Any]]
    my_pricing: list[dict[str, Any]]
    quantity_available: int | None
    product_status: str | None
    discontinued: bool | None
    end_of_life: bool | None
    datasheet_url: str | None


def _parse_product_details(raw: dict[str, Any]) -> _DigikeyProductDetails | None:
    """Pure function: reads one raw `ProductDetails` response's `"Product"`
    envelope into a `_DigikeyProductDetails`, or `None` if there is no
    usable product (no `"Product"` object, or one missing a manufacturer
    part number) -- same defensive posture as `_parse_matches` (module
    docstring: a wrong/missing shape "fails as 'no match', not a crash").

    Split out from `lookup_digikey_product_details` per this repo's
    "caller fetches, pure function resolves" convention (CLAUDE.md) --
    directly unit-testable with a plain dict, no stubbing required.

    Pricing (`StandardPricing`/`MyPricing`) and packaging (`PackageType`)
    are read off `ProductVariations[0]` -- Digi-Key returns one entry per
    orderable packaging option (cut tape vs. reel, etc.); this takes the
    first, same "first match wins" convention `lookup_digikey_datasheet`
    already uses for `matches[0]`. A `Product` with no `ProductVariations`
    at all (e.g. this ticket's own defensive-parsing test) reads as no
    packaging/pricing data, not a crash.
    """
    product = raw.get("Product")
    if not isinstance(product, dict):
        return None
    mpn = product.get("ManufacturerProductNumber")
    if not mpn:
        return None

    mfr = product.get("Manufacturer")
    mfr_name = _nested_field(mfr, default=mfr)

    category = product.get("Category")
    category_name = _nested_field(category)

    status = product.get("ProductStatus")
    status_name = _nested_field(status, key="Status")

    variations = product.get("ProductVariations") or []
    first_variation = variations[0] if variations and isinstance(variations[0], dict) else {}

    package = first_variation.get("PackageType")
    package_name = _nested_field(package)

    return _DigikeyProductDetails(
        manufacturer=mfr_name,
        manufacturer_part_number=mpn,
        digikey_product_number=first_variation.get("DigiKeyProductNumber"),
        package=package_name,
        category=category_name,
        parameters=product.get("Parameters") or [],
        price_breaks=first_variation.get("StandardPricing") or [],
        my_pricing=first_variation.get("MyPricing") or [],
        quantity_available=product.get("QuantityAvailable"),
        product_status=status_name,
        discontinued=product.get("Discontinued"),
        end_of_life=product.get("EndOfLife"),
        datasheet_url=product.get("DatasheetUrl"),
    )


def lookup_digikey_product_details(
    part_number: str,
    *,
    get_token: GetTokenFn = _get_access_token,
    fetch: ProductDetailsFn = _fetch_product_details,
) -> dict[str, Any]:
    """Look up `part_number`'s parametric attributes and price/quantity
    breaks via Digi-Key's `ProductDetails` endpoint (ticket #275) -- see
    module docstring's ticket #275 addendum for the primary-source
    citations backing every field name read below.

    Unlike `lookup_digikey_datasheet`, this does not download or ingest
    anything -- its job is "return a part's specs," a narrower, separate
    contract from "find and ingest a datasheet PDF" (this ticket's own
    instruction), so there is no `download`/`ingest`/`license`/
    `classification` parameter here.

    Refuses to run unless ALLOW_EXTERNAL_NETWORK_TOOLS=true, via the same
    `require_external_network_tools_enabled` gate `lookup_digikey_datasheet`
    already uses -- see `knowledge/sourcing_common.py` and `.env.example`.

    `get_token`/`fetch` are the real I/O by default (`fetch` reuses
    `_get_access_token`'s OAuth2 token and the same `X-DIGIKEY-Client-Id`
    header handling as `lookup_digikey_datasheet` -- no new auth path);
    tests inject stubs for both to verify this function's own response-
    parsing logic against a canned API response, with no live
    DIGIKEY_CLIENT_ID/SECRET or network access (see tests/test_digikey.py).

    Returns `{"status": "no_match" | "ok", ...}`. `"no_match"`: Digi-Key
    had no product for this part number (or one missing a usable
    manufacturer part number -- see `_parse_product_details`). `"ok"`:
    carries `manufacturer`/`manufacturer_part_number` (same identity
    contract as `lookup_digikey_datasheet`, for
    `knowledge.component_resolution` to reconcile against Mouser's/
    Nexar's hit for the same part), `digikey_product_number`, `package`,
    `category`, `parameters` (Digi-Key's raw per-category parametric
    attribute list -- frequency range, impedance, tolerance, or whatever
    that part's category actually names them), `price_breaks` (list
    pricing quantity breaks) and `my_pricing` (the authenticated account's
    own contract pricing, per docs/tools/digikey.md), plus
    `quantity_available`/`product_status`/`discontinued`/`end_of_life`/
    `datasheet_url` for a manufacturability check with zero additional API
    calls.
    """
    require_external_network_tools_enabled("Digi-Key")

    token = get_token()
    raw = fetch(part_number, token)
    details = _parse_product_details(raw)
    if details is None:
        return {"status": "no_match", "distributor": "digikey", "queried_part_number": part_number}

    return {
        "status": "ok",
        "distributor": "digikey",
        "manufacturer": details.manufacturer,
        "manufacturer_part_number": details.manufacturer_part_number,
        "digikey_product_number": details.digikey_product_number,
        "package": details.package,
        "category": details.category,
        "parameters": details.parameters,
        "price_breaks": details.price_breaks,
        "my_pricing": details.my_pricing,
        "quantity_available": details.quantity_available,
        "product_status": details.product_status,
        "discontinued": details.discontinued,
        "end_of_life": details.end_of_life,
        "datasheet_url": details.datasheet_url,
    }
