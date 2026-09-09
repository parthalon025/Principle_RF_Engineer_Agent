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

PRIMARY SOURCE for `_PART_DATA_QUERY` (ticket #276, `lookup_nexar_part_data`
-- adding the `specs`/`sellers -> offers` capability
`docs/tools/nexar.md`'s "Capabilities not yet used here" names as unused),
each sub-field individually confirmed against a worked, on-page query on
Nexar's own support site rather than guessed, per that ticket's own
instruction:

  - `specs { attribute { name } value displayValue unitsName }` -- quoted
    verbatim (field-for-field) from the "Multi-Match Filter Example" query
    in support.nexar.com's "Supply: Sorting and Filtering your Queries"
    article (101000452264). This is a single, complete, on-page worked
    query already using exactly this sub-field set together, the strongest
    confirmation level this module has for any field.
  - `sellers { company { name } offers { inventoryLevel } }` -- quoted
    verbatim from the "Total Availability" example query (searching
    `supSearchMpn(q: "acs770", ...)`) in support.nexar.com's "Nexar
    Playground GraphQL Query Examples" article (101000494582).
  - `sellers { company { name } offers { prices { quantity price } } }`
    -- quoted verbatim from the same article's "Pricing Breaks" example
    query (also `supSearchMpn(q: "acs770", ...)`).
  - `inventoryLevel` and `prices { quantity price }` are confirmed as real
    fields on the `offers` type individually, each in its own worked
    example above, but NOT merged into one on-page example in Nexar's own
    docs -- `_PART_DATA_QUERY` below requests both together (a normal,
    valid GraphQL selection over the same `offers` type), so treat that
    specific combination with the same "corroborated-but-not-directly-
    quoted" caution this docstring already applies to `bestDatasheet`
    above, even though each individual field is a direct verbatim quote.

`lookup_nexar_datasheet`'s own `_QUERY`/behavior above are unchanged by
this addition -- see `lookup_nexar_part_data`'s own docstring.
"""

from __future__ import annotations

import json
import os
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
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

# Ticket #276 -- extends the identity fields `_QUERY` above already
# requests with `specs` (parametric attributes) and `sellers -> offers`
# (multi-distributor pricing/stock), the two capabilities
# `docs/tools/nexar.md` names as unused. See module docstring for each
# sub-field's individual citation. Used only by `lookup_nexar_part_data`;
# `_QUERY`/`lookup_nexar_datasheet` above are untouched by this addition.
_PART_DATA_QUERY = """
query PartDataByMpn($mpn: String!) {
  supSearchMpn(q: $mpn, limit: 5) {
    results {
      part {
        mpn
        manufacturer { name }
        bestDatasheet { url }
        specs {
          attribute { name }
          value
          displayValue
          unitsName
        }
        sellers {
          company { name }
          offers {
            inventoryLevel
            prices { quantity price }
          }
        }
      }
    }
  }
}
"""

GetTokenFn = Callable[[], str]
SearchFn = Callable[[str, str], dict[str, Any]]
DownloadFn = Callable[[str, Path], Path]
IngestFn = Callable[..., dict[str, Any]]
# `lookup_nexar_part_data` (ticket #276) reuses `SearchFn` unchanged for its
# own `search` parameter -- same `(part_number, access_token) -> raw dict`
# shape as `lookup_nexar_datasheet`'s, since only the query text posted
# underneath differs (see `_search_part_data_by_part_number` below), not the
# seam's signature. Grouped here with the other `*Fn` aliases per this
# module's (and digikey.py's/mouser.py's) convention of declaring every
# Callable alias in one block right after the module constants.


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


def _post_graphql(query: str, part_number: str, access_token: str) -> dict[str, Any]:
    """The actual network I/O both `_search_by_part_number` and
    `_search_part_data_by_part_number` (ticket #276) perform -- same
    endpoint, same auth header, same request/response shape; the only thing
    that ever differs between `lookup_nexar_datasheet`'s query and
    `lookup_nexar_part_data`'s is which GraphQL query TEXT gets posted, so
    that's the one thing this helper takes as a parameter rather than
    hard-coding. Factored out so that difference doesn't require copying
    the surrounding request-building boilerplate a second time."""
    body = json.dumps({"query": query, "variables": {"mpn": part_number}}).encode()
    req = urllib.request.Request(
        _GRAPHQL_URL,
        data=body,
        headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310 -- real GraphQL call
        return json.loads(resp.read())


def _search_by_part_number(part_number: str, access_token: str) -> dict[str, Any]:
    """Real GraphQL exact-MPN query -- see module docstring citation. Posts
    `_QUERY` via the shared `_post_graphql` helper."""
    return _post_graphql(_QUERY, part_number, access_token)


def _iter_matched_parts(raw: dict[str, Any]):
    """Walk the `supSearchMpn.results[]` envelope both `_QUERY` and
    `_PART_DATA_QUERY` share by construction (same `supSearchMpn` operation,
    just a different field selection on `part`), yielding each result's
    `part` dict that carries an `mpn` -- a part with no `mpn` is skipped
    here rather than by each caller separately (module docstring's honest
    caveat: a wrong/missing shape "fails as 'no match', not a crash").
    Shared by `_parse_matches` and `_parse_part_data` (ticket #276) so this
    envelope-walking/mpn-skip rule lives in exactly one place instead of
    being duplicated field-for-field between the two."""
    results = (((raw.get("data") or {}).get("supSearchMpn") or {}).get("results")) or []
    for result in results:
        part = result.get("part") or {}
        if part.get("mpn"):
            yield part


def _match_from_part(part: dict[str, Any]) -> ComponentMatch:
    """Build the shared `ComponentMatch` identity from one already-
    `mpn`-validated `part` dict (see `_iter_matched_parts`). Used by both
    `_parse_matches` and `_parse_part_data` (ticket #276) since `_QUERY` and
    `_PART_DATA_QUERY` request the identical `mpn`/`manufacturer`/
    `bestDatasheet` identity fields alongside their differing extra
    fields."""
    manufacturer = (part.get("manufacturer") or {}).get("name")
    best_datasheet = part.get("bestDatasheet") or {}
    return ComponentMatch(
        distributor="nexar",
        manufacturer=manufacturer,
        manufacturer_part_number=part["mpn"],
        datasheet_url=best_datasheet.get("url"),
    )


def _parse_matches(raw: dict[str, Any]) -> list[ComponentMatch]:
    return [_match_from_part(part) for part in _iter_matched_parts(raw)]


def _search_part_data_by_part_number(part_number: str, access_token: str) -> dict[str, Any]:
    """Real GraphQL query for `lookup_nexar_part_data` (ticket #276) -- see
    module docstring citation. Posts `_PART_DATA_QUERY`, not `_QUERY`, via
    the shared `_post_graphql` helper: reusing `_search_by_part_number` as-
    is would silently send the narrow identity-only query and never return
    `specs`/`sellers -> offers`, defeating this ticket's purpose, so this
    stays a distinct function even though the two now share their actual
    network I/O."""
    return _post_graphql(_PART_DATA_QUERY, part_number, access_token)


@dataclass(frozen=True)
class _NexarPartData:
    """The `specs`/`sellers -> offers` fields `_PART_DATA_QUERY` requests
    (ticket #276, `docs/tools/nexar.md`'s "Capabilities not yet used here")
    but that don't belong on the shared `ComponentMatch`
    (`knowledge/sourcing_common.py`): that dataclass is reconstructed from a
    raw dict by `knowledge.component_resolution._match_from_raw` and shared
    unchanged by `knowledge/digikey.py`/`knowledge/mouser.py`, so it stays
    limited to the four identity fields every distributor can report. These
    two are Nexar-specific (its cross-distributor aggregation is the whole
    reason this ticket exists) and stay local to this module -- attached
    only onto `lookup_nexar_part_data`'s own result dict, mirroring
    `knowledge.mouser._MouserPricingAndCompliance`'s same resolution for
    ticket #274.

    `specs` is a list of `{"name", "value", "display_value", "units"}`
    dicts (one per parametric attribute); `offers` is a list of
    `{"seller", "stock_level", "price_breaks"}` dicts, one entry per
    (seller, offer) pair -- see `_parse_seller_offers` for why offers are
    never merged/aggregated within one seller. Both default to an empty
    list, never `None`, when the raw response carries neither field --
    same defensive posture as `_parse_matches` above (a wrong/missing shape
    "fails as 'no match', not a crash", not by raising here).
    """

    specs: list[dict[str, Any]]
    offers: list[dict[str, Any]]


def _parse_specs(part: dict[str, Any]) -> list[dict[str, Any]]:
    """Pure function: reads each `specs[]` entry off one raw `part`,
    translating Nexar's field names (`attribute.name`, `value`,
    `displayValue`, `unitsName` -- see module docstring citation) to this
    module's snake_case keys. Split out from the top-level parse function
    per this repo's 'caller fetches, pure function resolves' convention
    (CLAUDE.md) -- directly unit-testable with a plain dict, no stubbing
    required, mirroring `knowledge.mouser._parse_pricing_and_compliance`.
    `.get()` throughout means a missing key reads as `None` rather than
    raising."""
    specs = part.get("specs") or []
    parsed: list[dict[str, Any]] = []
    for spec in specs:
        attribute = spec.get("attribute") or {}
        parsed.append(
            {
                "name": attribute.get("name"),
                "value": spec.get("value"),
                "display_value": spec.get("displayValue"),
                "units": spec.get("unitsName"),
            }
        )
    return parsed


def _parse_seller_offers(part: dict[str, Any]) -> list[dict[str, Any]]:
    """Pure function: reads each `sellers[].offers[]` entry off one raw
    `part` into one dict per (seller, offer) pair -- a seller can carry
    more than one offer (e.g. per-country availability, per Nexar's own
    schema), and nothing here merges or aggregates across a seller's
    offers, since Nexar's own docs don't state a rule for combining them
    and inventing one would risk a wrong number reading as a real one
    (CLAUDE.md: never silently guess a placeholder value). A part with two
    offers from the same seller therefore yields two entries with the same
    `seller` name, not one merged entry."""
    sellers = part.get("sellers") or []
    parsed: list[dict[str, Any]] = []
    for seller in sellers:
        seller_name = (seller.get("company") or {}).get("name")
        for offer in seller.get("offers") or []:
            parsed.append(
                {
                    "seller": seller_name,
                    "stock_level": offer.get("inventoryLevel"),
                    "price_breaks": offer.get("prices") or [],
                }
            )
    return parsed


def _parse_part_data(raw: dict[str, Any]) -> list[tuple[ComponentMatch, _NexarPartData]]:
    """Same envelope-walking as `_parse_matches` above (both go through the
    shared `_iter_matched_parts`), paired with each match's `_NexarPartData`
    (ticket #276) -- kept alongside rather than folded into `ComponentMatch`
    so the shared dataclass (knowledge/digikey.py, knowledge/mouser.py,
    knowledge/component_resolution.py) is untouched, mirroring
    `knowledge.mouser._parse_matches`'s identical resolution."""
    return [
        (
            _match_from_part(part),
            _NexarPartData(specs=_parse_specs(part), offers=_parse_seller_offers(part)),
        )
        for part in _iter_matched_parts(raw)
    ]


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


def lookup_nexar_part_data(
    part_number: str,
    *,
    get_token: GetTokenFn = _get_access_token,
    search: SearchFn = _search_part_data_by_part_number,
) -> dict[str, Any]:
    """Search Nexar (Octopart data) for `part_number` via the extended
    exact-MPN GraphQL query (`_PART_DATA_QUERY`) that also requests `specs`
    (structured parametric attributes -- frequency range, impedance,
    tolerance, package) and `sellers -> offers` (multi-distributor
    pricing/stock) -- ticket #276, closing the two gaps
    `docs/tools/nexar.md`'s "Capabilities not yet used here" names: today
    `lookup_nexar_datasheet` (above) only confirms a part exists and fetches
    its datasheet, the same narrow question `knowledge.digikey`/
    `knowledge.mouser` already answer; this is the one query only Nexar's
    cross-distributor aggregation can answer -- "who, across every
    distributor, stocks this part, at what price" and "what are its actual
    specs" -- which is what would let a caller screen a candidate component
    against an RF requirement (e.g. an impedance or frequency-range
    threshold) instead of only confirming it exists.

    This is structured data, not a document: unlike `lookup_nexar_datasheet`
    it never calls `download`/`ingest_document`, so no datasheet PDF is
    fetched or ingested in this path (the query still carries
    `bestDatasheet.url` for identification, matching `_QUERY`'s shape, but
    that URL is only returned, never downloaded).

    Refuses to run unless ALLOW_EXTERNAL_NETWORK_TOOLS=true -- see
    `knowledge/sourcing_common.py` and `.env.example`.

    `get_token` is reused unchanged from `lookup_nexar_datasheet` (auth
    doesn't change); `search` defaults to `_search_part_data_by_part_number`
    (posting `_PART_DATA_QUERY`, not `_QUERY` -- see that function's own
    docstring for why it can't just be `_search_by_part_number`). Both are
    injectable, same DI-seam pattern as `lookup_nexar_datasheet`; tests
    inject stubs to verify this function's argument-passing/response-
    parsing logic against a canned GraphQL response, with no live
    NEXAR_CLIENT_ID/SECRET or network access (see tests/test_nexar.py).

    Returns `{"status": "no_match" | "ok", "distributor": "nexar", ...}`;
    on "ok" also carries `manufacturer`/`manufacturer_part_number`/
    `datasheet_url` (identity, from the unmodified `ComponentMatch` shape
    -- ticket #276 instructs not to repurpose it), `specs` (list of
    `{"name", "value", "display_value", "units"}` dicts -- see
    `_parse_specs`), and `offers` (list of `{"seller", "stock_level",
    "price_breaks"}` dicts, one entry per (seller, offer) pair -- see
    `_parse_seller_offers`). `specs`/`offers` are `[]`, never absent, when
    a match has neither -- same "fails as no-match, not a crash" posture as
    the rest of this module.
    """
    require_external_network_tools_enabled("Nexar")

    token = get_token()
    raw = search(part_number, token)
    parsed = _parse_part_data(raw)
    if not parsed:
        return {"status": "no_match", "distributor": "nexar", "queried_part_number": part_number}

    identity, data = parsed[0]
    return {
        "status": "ok",
        "distributor": "nexar",
        "manufacturer": identity.manufacturer,
        "manufacturer_part_number": identity.manufacturer_part_number,
        "datasheet_url": identity.datasheet_url,
        "specs": data.specs,
        "offers": data.offers,
    }
