"""Shared plumbing for the distributor/component-intelligence thin clients
(ticket #67): `knowledge/digikey.py`, `knowledge/mouser.py`,
`knowledge/nexar.py` -- plus one credentialed, gated non-distributor
caller, `knowledge/sourcing/patent.py`'s `search_uspto_patents` (issue
#280): a USPTO Open Data Portal government patent-search API, not a
component distributor, but held to the same "real credentialed outbound
call the instant it runs" posture (see `ExternalNetworkToolsDisabledError`
below), so it shares this gate and the `post_json` helper too.

Per CLAUDE.md's knowledge-sourcing seam, each of the three distributor
modules is a THIN client: authenticate against that provider's own
free-developer-tier credentials, search by part number, download the
matched datasheet PDF locally, and hand it to
`knowledge.ingest.ingest_document(source_type="datasheet", ...)`
unchanged -- no new ingestion logic. `search_uspto_patents` is shaped the
same way credential- and gate-wise, but returns candidate dicts for a
caller to review rather than downloading and ingesting anything itself
(see its own module's docstring). This module factors out the three
pieces all four would otherwise duplicate -- downloading a URL to a local
file, the shared `Request`/`urlopen`/JSON-decode shape behind every
credentialed POST, and the outbound-network-call safety gate -- per this
repo's "search-before-write, reuse beats reinvention" convention (see
../CLAUDE.md).
"""

from __future__ import annotations

import json
import os
import tempfile
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

_USER_AGENT = "principal-rf-engineer/0.1 (+component-sourcing)"


class ExternalNetworkToolsDisabledError(PermissionError):
    """Raised when a gated client is invoked without
    ALLOW_EXTERNAL_NETWORK_TOOLS=true.

    This repo's other real-world-reaching tools refuse by default behind
    an explicit env-var gate too -- HFSS_ENABLED (simulation/hfss.py). The
    three distributor clients, plus `search_uspto_patents` (issue #280,
    `knowledge/sourcing/patent.py`), place a real, credentialed outbound
    HTTP call to a third party the instant they run, so they all get the
    same posture.
    ALLOW_EXTERNAL_NETWORK_TOOLS was already declared in .env.example
    (defaulting to "false") before this ticket, but nothing read it yet --
    this is the first thing that does.
    """


def require_external_network_tools_enabled(distributor: str) -> None:
    """Refuse to proceed unless ALLOW_EXTERNAL_NETWORK_TOOLS=true. Called
    as the very first line of each gated function before any credential
    is read or any request is built: the three `lookup_*_datasheet`
    functions, and `search_uspto_patents` (issue #280)."""
    if os.environ.get("ALLOW_EXTERNAL_NETWORK_TOOLS", "false").strip().lower() != "true":
        raise ExternalNetworkToolsDisabledError(
            f"ALLOW_EXTERNAL_NETWORK_TOOLS is not 'true' -- refusing to call the real "
            f"{distributor} API. Set ALLOW_EXTERNAL_NETWORK_TOOLS=true in the environment "
            "to allow this tool to make outbound network calls."
        )


@dataclass(frozen=True)
class ComponentMatch:
    """One distributor's answer to "this part number resolves to this exact
    orderable part, with this datasheet."

    `manufacturer_part_number` is exactly that distributor's own report of
    the manufacturer's own part code -- e.g. Digi-Key's
    `ManufacturerProductNumber`, Mouser's `ManufacturerPartNumber`, Nexar's
    `mpn` -- NEVER that distributor's own catalog/SKU number (Digi-Key's
    own "296-1234-1-ND"-style code, Mouser's own MouserPartNumber). Reading
    the wrong field here would silently defeat
    `knowledge.component_resolution`, which compares this exact value
    across sources to decide whether two distributor hits describe the
    same physical part (CONTEXT.md: Component -- identity is
    `(manufacturer, part_number)`, package/tape-and-reel suffix included).
    """

    distributor: str
    manufacturer: str | None
    manufacturer_part_number: str
    datasheet_url: str | None


def download_to_file(url: str, dest_dir: Path, filename: str | None = None) -> Path:
    """Download `url` (a real datasheet PDF link) to a file under
    `dest_dir` (created if needed) and return its path.

    `filename` defaults to the URL's own last path segment, falling back to
    a generic name if that's empty (e.g. a query-string-only URL) --
    real distributor datasheet URLs seen in this ticket's cited
    primary-source research for all three providers are plain
    `https://.../<name>.pdf` links, so this fallback is not expected to
    bite in practice.

    This is the actual network I/O boundary -- like
    `knowledge/embedding.py`'s `_embed_via_local`/`_embed_via_external`, it
    is not exercised directly by this repo's tests (no live network access
    to an arbitrary host in this sandbox); `lookup_*_datasheet` functions
    take `download` as an injectable parameter defaulting to this function,
    and tests inject a stub instead.
    """
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    name = filename or Path(urlparse(url).path).name or "datasheet.pdf"
    dest = dest_dir / name
    req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    with urllib.request.urlopen(req, timeout=60) as resp:  # noqa: S310 -- real datasheet fetch
        dest.write_bytes(resp.read())
    return dest


def post_json(
    url: str, data: bytes, headers: dict[str, str], *, timeout: int = 30
) -> dict[str, Any]:
    """POST `data` (already-encoded request body bytes) to `url` and parse
    the response body as JSON.

    The one shape behind every credentialed POST this package's clients
    make, factored out of what was five duplicate copies across three
    files -- Digi-Key's OAuth2 token request and its keyword search
    (`knowledge/digikey.py`), Mouser's part-number search
    (`knowledge/mouser.py`), Nexar's OAuth2 token request and its GraphQL
    query (`knowledge/nexar.py`) -- before USPTO ODP's full-text search
    (`knowledge/sourcing/patent.py`'s `search_uspto_patents`, issue #280)
    added a sixth. Body encoding (form-urlencoded for an OAuth2 token
    request, JSON for everything else) and headers (the auth scheme
    differs client to client -- a bearer token, an API-key header, an
    API-key query parameter) stay each caller's own job; this factors out
    only the `Request`/`urlopen`/`json.loads` triplet that was otherwise
    copied six times over.

    Like `download_to_file`, this is the actual network I/O boundary. Five
    of its six call sites are reached only through their own `get_token`/
    `get_api_key`/`search` injectable parameter, which is what their tests
    stub instead (no live credential or network access in this sandbox);
    this function's own request-building and JSON-parsing are covered
    directly by `tests/test_sourcing_common.py`.
    """
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 -- shared credentialed POST helper, see this function's own docstring for every caller
        return json.loads(resp.read())


def make_workdir(prefix: str) -> Path:
    """A fresh temp directory for one lookup call's downloaded datasheet,
    mirroring `simulation/nec2pp.py`'s `run_nec2_simulation` use of
    `tempfile.mkdtemp` when no caller-supplied workdir is given."""
    return Path(tempfile.mkdtemp(prefix=prefix))
