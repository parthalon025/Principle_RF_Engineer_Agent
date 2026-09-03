"""Nexar API (Octopart data) thin client (ticket #67).

PRIMARY SOURCE, each verified against Nexar's own docs/support site and
official sample code directly:

  - Auth: OAuth 2.0 `client_credentials` grant against Nexar's own Identity
    service, confirmed at support.nexar.com's "Authorization" article and
    Nexar's own `nexar-token-py` sample
    (github.com/NexarDeveloper/nexar-token-py): POST
    `application/x-www-form-urlencoded` to
    `https://identity.nexar.com/connect/token` with `client_id`,
    `client_secret`, `grant_type=client_credentials`; response
    `{"access_token": ..., "expires_in": 86400, "token_type": "Bearer",
    "scope": "supply.domain"}`.
  - API: a single GraphQL endpoint, `https://api.nexar.com/graphql`, POST
    `{"query": "..."}` with `Authorization: Bearer <token>` -- confirmed via
    Nexar's own "Query Templates" support article, which gives a working
    curl example against this exact endpoint.
  - Exact-MPN match query: `supSearchMpn(q: "<mpn>")` -- "returns 1 hit per
    exact MPN" per that same Query Templates article, as opposed to
    `supSearch`'s fuzzy keyword matching -- the right choice here since this
    module is always searching by a specific manufacturer part number.
  - Datasheet field: `part { bestDatasheet { url } }` -- corroborated by a
    Nexar support article on compliance documents (showing the broader
    `documentCollections` schema, whose "single best datasheet" sibling
    field is `bestDatasheet`) and by a community-maintained Nexar API
    client's TypeScript type definitions (`bestDatasheet?: { url: string
    }` on the part type, read directly off the live schema). Neither
    source shows `bestDatasheet` used inline in one complete worked query
    example, so this is corroborated-but-not-directly-quoted from Nexar's
    own docs -- treat with slightly less confidence than the auth/endpoint
    facts above.

Free tier: a Nexar "Evaluation" application is capped around 1,000 matched
parts (100 in the pre-signup Playground) per Nexar's own product page
(nexar.com/api) -- exceeding that needs a paid plan. Not enforced by this
client; Nexar's own API is what would reject an over-cap call.

HONEST CAVEAT: no NEXAR_CLIENT_ID/NEXAR_CLIENT_SECRET is registered in this
environment and this client has NOT been run against the real API
end-to-end -- treat any result as unverified end-to-end until it has been
run against the real API at least once.
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

_TOKEN_URL = "https://identity.nexar.com/connect/token"
_GRAPHQL_URL = "https://api.nexar.com/graphql"

_QUERY = """
query PartByMpn($mpn: String!) {
  supSearchMpn(q: $mpn, limit: 5) {
    results {
      part {
        mpn
        manufacturer { name }
        bestDatasheet { url }
      }
    }
  }
}
"""

GetTokenFn = Callable[[], str]
SearchFn = Callable[[str, str], dict[str, Any]]
DownloadFn = Callable[[str, Path], Path]
IngestFn = Callable[..., dict[str, Any]]


def _get_access_token() -> str:
    """Real OAuth2 client_credentials token request -- see module docstring
    citation. This is the actual network I/O boundary, not exercised
    directly by this repo's tests; `lookup_nexar_datasheet` takes
    `get_token` as an injectable parameter defaulting to this function."""
    client_id = os.environ["NEXAR_CLIENT_ID"]
    client_secret = os.environ["NEXAR_CLIENT_SECRET"]
    data = urlencode(
        {"client_id": client_id, "client_secret": client_secret, "grant_type": "client_credentials"}
    ).encode()
    req = urllib.request.Request(
        _TOKEN_URL,
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310 -- real OAuth2 token call
        payload = json.loads(resp.read())
    return payload["access_token"]


def _search_by_part_number(part_number: str, access_token: str) -> dict[str, Any]:
    """Real GraphQL exact-MPN query -- see module docstring citation."""
    body = json.dumps({"query": _QUERY, "variables": {"mpn": part_number}}).encode()
    req = urllib.request.Request(
        _GRAPHQL_URL,
        data=body,
        headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310 -- real GraphQL call
        return json.loads(resp.read())


def _parse_matches(raw: dict[str, Any]) -> list[ComponentMatch]:
    results = (((raw.get("data") or {}).get("supSearchMpn") or {}).get("results")) or []
    matches: list[ComponentMatch] = []
    for result in results:
        part = result.get("part") or {}
        mpn = part.get("mpn")
        if not mpn:
            continue
        manufacturer = (part.get("manufacturer") or {}).get("name")
        best_datasheet = part.get("bestDatasheet") or {}
        matches.append(
            ComponentMatch(
                distributor="nexar",
                manufacturer=manufacturer,
                manufacturer_part_number=mpn,
                datasheet_url=best_datasheet.get("url"),
            )
        )
    return matches


def lookup_nexar_datasheet(
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
    """Search Nexar (Octopart data) for `part_number` via an exact-MPN
    GraphQL query, download its datasheet PDF, and ingest it via the
    unchanged `ingest_document(source_type='datasheet')` pipeline
    (`knowledge/ingest.py`).

    Refuses to run unless ALLOW_EXTERNAL_NETWORK_TOOLS=true -- see
    `knowledge/sourcing_common.py` and `.env.example`.

    `get_token`/`search`/`download`/`ingest` are the real I/O by default;
    tests inject stubs to verify this function's argument-passing/response-
    parsing logic against a canned GraphQL response, with no live
    NEXAR_CLIENT_ID/SECRET or network access (see tests/test_nexar.py).

    Returns `{"status": "no_match" | "no_datasheet" | "ok", ...}` -- same
    contract as `knowledge.digikey.lookup_digikey_datasheet`.
    """
    require_external_network_tools_enabled("Nexar")

    token = get_token()
    raw = search(part_number, token)
    matches = _parse_matches(raw)
    if not matches:
        return {"status": "no_match", "distributor": "nexar", "queried_part_number": part_number}

    best = matches[0]
    if not best.datasheet_url:
        return {
            "status": "no_datasheet",
            "distributor": "nexar",
            "manufacturer": best.manufacturer,
            "manufacturer_part_number": best.manufacturer_part_number,
        }

    dest_dir = Path(download_dir) if download_dir else make_workdir("nexar_")
    file_path = download(best.datasheet_url, dest_dir)
    ingest_result = ingest(
        file_path=str(file_path),
        source_type="datasheet",
        license=license,
        classification=classification,
    )
    return {
        "status": "ok",
        "distributor": "nexar",
        "manufacturer": best.manufacturer,
        "manufacturer_part_number": best.manufacturer_part_number,
        "datasheet_url": best.datasheet_url,
        "ingest": ingest_result,
    }
