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
"""

from __future__ import annotations

import json
import os
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

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

GetTokenFn = Callable[[], str]
SearchFn = Callable[[str, str], dict[str, Any]]
DownloadFn = Callable[[str, Path], Path]
IngestFn = Callable[..., dict[str, Any]]


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


def _parse_matches(raw: dict[str, Any]) -> list[ComponentMatch]:
    """See module docstring's honest caveat on the `"Products"`/PascalCase
    field-name assumption."""
    matches: list[ComponentMatch] = []
    for product in raw.get("Products") or []:
        mpn = product.get("ManufacturerProductNumber")
        if not mpn:
            continue
        mfr = product.get("Manufacturer")
        mfr_name = mfr.get("Name") if isinstance(mfr, dict) else mfr
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
