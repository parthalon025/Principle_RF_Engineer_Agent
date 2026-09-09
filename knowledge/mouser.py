"""Mouser Search API thin client (ticket #67).

PRIMARY SOURCE: Mouser's official Search API is registered at
https://www.mouser.com/api-hub/, with its interactive spec hosted at
https://api.mouser.com/api/docs/ui/index. That Swagger UI itself sits
behind a registered-API-key/login wall this environment cannot pass (fetch
attempts returned only the page shell, no schema body), so the exact
request/response field names below are corroborated instead from THREE
independent third-party integrations that each reproduce a working call
against the real API -- not reconstructed from memory, per CLAUDE.md's
verification rule:

  - `sparkmicro/mouser-api` (GitHub issue #4): a working request body
    `{"SearchByPartRequest": {"mouserPartNumber": <part>, ...}}` sent via
    `POST .../search/partnumber?apiKey=<key>`.
  - `openhoo/mouserhoo` (TypeScript SDK): exposes
    `productSearch.partNumberSearch({ mouserPartNumber, partSearchOptions
    })`; the api key is a client-constructor option, sent as the same
    `apiKey` query parameter under the hood.
  - `AlexSartori/pymouser` (Python wrapper): reads `match['DataSheetUrl']`,
    `match['MouserPartNumber']`, `match['ProductDetailUrl']` off each
    returned part -- confirming those exact response field names.

`partSearchOptions` (vs. a competing `IncludeExtendedAttributes` boolean
field seen in only one of the four community sources found) is used here as
the request field name, since it is the field two of the three independent
sources above agree exists; its value `"None"` (no extra options) is this
repo's own conservative default -- the exact accepted enum values for that
field were not found in any source read and are UNVERIFIED.

Field-name convention (`MouserPartNumber` = Mouser's own catalog number,
`ManufacturerPartNumber` = the manufacturer's own code) is consistent
across all three sources above -- `_parse_matches` below reads
`ManufacturerPartNumber`, never `MouserPartNumber`, as this ticket's
identity-resolution key (CONTEXT.md: Component identity is the
manufacturer's own part number, not a distributor catalog code).

HONEST CAVEAT: no MOUSER_API_KEY is registered in this environment and this
client has NOT been run against the real API end-to-end -- treat any result
as unverified end-to-end until it has been run against the real API at
least once. The top-level response envelope (taken here as
`{"SearchResults": {"Parts": [...]}}`) was this repo's own best inference
from the community sources above when first written; `docs/tools/mouser.md`
(primary-source capability research, fetched directly from Mouser's own
official V1/V2 Swagger/OpenAPI specs at api.mouser.com/api/docs/{V1,V2})
has since confirmed it exactly right, alongside every field name
`_parse_matches`/`_parse_pricing_and_compliance` read below (ticket #274).
`_parse_matches` is still written defensively (returns no matches for
anything not matching this shape, rather than raising) so a wrong
assumption here fails as "no match", not a crash.
"""

from __future__ import annotations

import json
import os
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from knowledge.ingest import ingest_document
from knowledge.sourcing_common import (
    ComponentMatch,
    download_to_file,
    make_workdir,
    require_external_network_tools_enabled,
)

_SEARCH_URL = "https://api.mouser.com/api/v1/search/partnumber"

GetApiKeyFn = Callable[[], str]
SearchFn = Callable[[str, str], dict[str, Any]]
DownloadFn = Callable[[str, Path], Path]
IngestFn = Callable[..., dict[str, Any]]


def _get_api_key() -> str:
    """Reads MOUSER_API_KEY. Its own function (mirroring
    `knowledge.digikey._get_access_token`/`knowledge.nexar._get_access_token`)
    rather than inlined in `lookup_mouser_datasheet`, so tests can inject
    `get_api_key` alongside `search` and never need a real MOUSER_API_KEY in
    the environment -- consistent with how the other two clients keep every
    credential read behind an injectable seam."""
    return os.environ["MOUSER_API_KEY"]


def _search_by_part_number(part_number: str, api_key: str) -> dict[str, Any]:
    """Real part-number-search POST -- see module docstring citations. This
    is the actual network I/O boundary, not exercised directly by this
    repo's tests; `lookup_mouser_datasheet` takes `search` as an
    injectable parameter defaulting to this function."""
    body = json.dumps(
        {"SearchByPartRequest": {"mouserPartNumber": part_number, "partSearchOptions": "None"}}
    ).encode()
    url = f"{_SEARCH_URL}?apiKey={api_key}"
    req = urllib.request.Request(
        url, data=body, headers={"Content-Type": "application/json"}, method="POST"
    )
    with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310 -- real search call
        return json.loads(resp.read())


@dataclass(frozen=True)
class _MouserPricingAndCompliance:
    """The pricing/availability/lifecycle/compliance fields Mouser returns
    on every matched `SearchResults.Parts[]` entry (ticket #274,
    docs/tools/mouser.md's "Capabilities not yet used here") but that don't
    belong on the shared `ComponentMatch` (`knowledge/sourcing_common.py`):
    that dataclass is reconstructed from a raw dict by
    `knowledge.component_resolution._match_from_raw` and shared unchanged
    by `knowledge/digikey.py`/`knowledge/nexar.py`, so it stays limited to
    the four identity fields every distributor can report. These ten are
    Mouser-specific (confirmed only in Mouser's own response shape) and
    stay local to this module -- attached only onto
    `lookup_mouser_datasheet`'s own result dict, per this ticket's own
    suggested resolution.

    A field absent or null in the raw response comes through as `None`
    here, never raises -- same defensive posture as `_parse_matches`
    (module docstring: a wrong/missing shape "fails as 'no match', not a
    crash").
    """

    price_breaks: list[dict[str, Any]] | None
    availability: str | None
    lead_time: str | None
    lifecycle_status: str | None
    is_discontinued: bool | None
    suggested_replacement: str | None
    rohs_status: str | None
    reach_svhc: list[Any] | None
    product_compliance: list[dict[str, Any]] | None
    trade_compliance: list[dict[str, Any]] | None


def _parse_pricing_and_compliance(part: dict[str, Any]) -> _MouserPricingAndCompliance:
    """Pure function: reads the ten pricing/availability/lifecycle/
    compliance fields off one raw `SearchResults.Parts[]` entry, translating
    Mouser's PascalCase field names to this module's snake_case keys (same
    translation already used for `ManufacturerPartNumber`/`DataSheetUrl`).
    Split out from `_parse_matches` per this module's 'caller fetches, pure
    function resolves' convention -- directly unit-testable with a plain
    dict, no stubbing required. `.get()` throughout means a missing key
    reads as `None` rather than raising."""
    return _MouserPricingAndCompliance(
        price_breaks=part.get("PriceBreaks"),
        availability=part.get("Availability"),
        lead_time=part.get("LeadTime"),
        lifecycle_status=part.get("LifecycleStatus"),
        is_discontinued=part.get("IsDiscontinued"),
        suggested_replacement=part.get("SuggestedReplacement"),
        rohs_status=part.get("ROHSStatus"),
        reach_svhc=part.get("REACH-SVHC"),
        product_compliance=part.get("ProductCompliance"),
        trade_compliance=part.get("TradeCompliance"),
    )


def _parse_matches(
    raw: dict[str, Any],
) -> list[tuple[ComponentMatch, _MouserPricingAndCompliance]]:
    """See module docstring's honest caveat on the
    `{"SearchResults": {"Parts": [...]}}` envelope assumption.

    Returns each match paired with its `_MouserPricingAndCompliance`
    (ticket #274) -- kept alongside rather than folded into `ComponentMatch`
    so the shared dataclass (knowledge/digikey.py, knowledge/nexar.py,
    knowledge/component_resolution.py) is untouched."""
    parts = ((raw.get("SearchResults") or {}).get("Parts")) or []
    matches: list[tuple[ComponentMatch, _MouserPricingAndCompliance]] = []
    for part in parts:
        mpn = part.get("ManufacturerPartNumber")
        if not mpn:
            continue
        matches.append(
            (
                ComponentMatch(
                    distributor="mouser",
                    manufacturer=part.get("Manufacturer"),
                    manufacturer_part_number=mpn,
                    datasheet_url=part.get("DataSheetUrl"),
                ),
                _parse_pricing_and_compliance(part),
            )
        )
    return matches


def lookup_mouser_datasheet(
    part_number: str,
    *,
    license: str,
    classification: str,
    download_dir: str | None = None,
    get_api_key: GetApiKeyFn = _get_api_key,
    search: SearchFn = _search_by_part_number,
    download: DownloadFn = download_to_file,
    ingest: IngestFn = ingest_document,
) -> dict[str, Any]:
    """Search Mouser for `part_number`, download its datasheet PDF, and
    ingest it via the unchanged `ingest_document(source_type='datasheet')`
    pipeline (`knowledge/ingest.py`).

    Refuses to run unless ALLOW_EXTERNAL_NETWORK_TOOLS=true -- see
    `knowledge/sourcing_common.py` and `.env.example`.

    `get_api_key`/`search`/`download`/`ingest` are the real I/O by default;
    tests inject stubs to verify this function's argument-passing/response-
    parsing logic against a canned API response, with no live
    MOUSER_API_KEY or network access (see tests/test_mouser.py) --
    mirroring `knowledge/extract.py`'s extract_local/extract_external
    injection pattern.

    Returns `{"status": "no_match" | "no_datasheet" | "ok", ...}` -- same
    contract as `knowledge.digikey.lookup_digikey_datasheet`. On "ok", also
    carries the pricing/availability/lead-time/lifecycle/compliance fields
    described in `_MouserPricingAndCompliance` (ticket #274) -- so a caller
    scoring manufacturability or checking export compliance gets that from
    this same call, with zero additional API calls.
    """
    require_external_network_tools_enabled("Mouser")

    api_key = get_api_key()
    raw = search(part_number, api_key)
    matches = _parse_matches(raw)
    if not matches:
        return {"status": "no_match", "distributor": "mouser", "queried_part_number": part_number}

    best, details = matches[0]
    if not best.datasheet_url:
        return {
            "status": "no_datasheet",
            "distributor": "mouser",
            "manufacturer": best.manufacturer,
            "manufacturer_part_number": best.manufacturer_part_number,
        }

    dest_dir = Path(download_dir) if download_dir else make_workdir("mouser_")
    file_path = download(best.datasheet_url, dest_dir)
    ingest_result = ingest(
        file_path=str(file_path),
        source_type="datasheet",
        license=license,
        classification=classification,
    )
    return {
        "status": "ok",
        "distributor": "mouser",
        "manufacturer": best.manufacturer,
        "manufacturer_part_number": best.manufacturer_part_number,
        "datasheet_url": best.datasheet_url,
        "price_breaks": details.price_breaks,
        "availability": details.availability,
        "lead_time": details.lead_time,
        "lifecycle_status": details.lifecycle_status,
        "is_discontinued": details.is_discontinued,
        "suggested_replacement": details.suggested_replacement,
        "rohs_status": details.rohs_status,
        "reach_svhc": details.reach_svhc,
        "product_compliance": details.product_compliance,
        "trade_compliance": details.trade_compliance,
        "ingest": ingest_result,
    }
