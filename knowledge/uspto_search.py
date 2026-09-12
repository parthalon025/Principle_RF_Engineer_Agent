"""USPTO Open Data Portal (ODP) full-text patent search -- topic/keyword
discovery search, `search_uspto_patents` (issue #280).

Split out of `knowledge/sourcing/patent.py` into its own top-level module
(issue #513) to match this package's one-file-per-credentialed-external-API
-client convention -- `knowledge/digikey.py`, `knowledge/mouser.py`,
`knowledge/nexar.py` are the existing siblings this module now joins.
`knowledge/sourcing/patent.py` keeps patent-number parsing/normalization
(`normalize_patent_number`/`PatentIdentifier`/`PatentNumberError`, imported
from there below) and the fetch-by-number ingestion pipeline
(`ingest_patent`) -- a separate, credential-free entry point with a separate
posture from everything in this file (see below).

DISCOVERY SEARCH (issue #280): CREDENTIALED, GATED -- A DIFFERENT POSTURE
FROM `ingest_patent` (`knowledge/sourcing/patent.py`)
--------------------------------------------------------------------------
Issue #257 named USPTO patent search as its own deferred follow-up and
explicitly declined to pick a backend without verifying it live first. This
is that verification, done directly against the real, current endpoint (not
reconstructed from memory or from documentation alone), the same evidentiary
bar every fetch-by-number fact in `knowledge/sourcing/patent.py`'s own
docstring was already held to.

WHAT WAS HIT LIVE, THIS TICKET, AND WHAT IT SHOWED
    $ curl -X POST https://api.uspto.gov/api/v1/patent/applications/search \\
        -H "Content-Type: application/json" -d '{"q":"metamaterial"}'
    -> HTTP 401 {"message":"Unauthorized"}

    $ curl -X POST https://api.uspto.gov/api/v1/patent/applications/search \\
        -H "Content-Type: application/json" -H "X-Api-Key: bogus" -d '{"q":"metamaterial"}'
    -> HTTP 403 {"message":"Forbidden"}

    $ curl -X OPTIONS https://api.uspto.gov/api/v1/patent/applications/search
    -> HTTP 200, header access-control-allow-headers:
       "Content-Type,X-Amz-Date,Authorization,X-Amz-Security-Token,X-Api-Key"
       (also x-amz-apigw-id present -- an AWS API Gateway deployment)

This confirms, directly: the endpoint is real and live; it accepts POST with
a JSON body; a request with **no** key is refused before the body is even
read (401 "Unauthorized"); a request with a **present-but-wrong** key is
refused differently (403 "Forbidden") -- exactly the two-tier behaviour an
AWS API-Gateway API-key/usage-plan setup gives, and the `X-Api-Key` header
name the CORS preflight advertises matches every independent secondhand
account found (below). No GET/POST/`q`-parameter shape here was invented;
the 401/403 split above is this ticket's own direct evidence for it.

THE CREDENTIAL ITSELF: A FREE ACCOUNT, BUT NOT A FREE-TO-AUTOMATE ONE
Confirmed against USPTO's own subscription-center notice (already cited as
source [8] in docs/tools/uspto-patents.md): ODP access requires a free
USPTO.gov account -- no payment. What that notice does NOT mention, and
which several independent secondhand sources agree on (a Go client's own
setup docs, a blog post aimed at patent professionals, and this repo's own
web search of USPTO's help-center content), is that *issuing an API key*
specifically requires that USPTO.gov account to be additionally linked to a
**validated ID.me identity** -- multi-factor identity verification against
a government-issued ID (and a video call for anyone outside the US). This
is consistent with USPTO's broader 2025-2026 rollout of ID.me verification
across its other systems (Patent Center required it from September 2025).
None of this was independently re-confirmed by actually completing that
flow -- it requires a real person's real government ID, which is neither
available nor appropriate to attempt from an automated coding session --
so it is reported here as well-corroborated but not first-party-witnessed,
exactly the distinction `knowledge/digikey.py`'s own "HONEST CAVEAT"
draws for its own unregistered credential.

HONEST CAVEAT, MATCHING knowledge/digikey.py's OWN: no USPTO_ODP_API_KEY is
registered in this environment, and `search_uspto_patents` has NOT been run
against the real ODP endpoint end-to-end -- treat any result as unverified
until it has been run against the real API at least once. The request body
shape below (`{"q": ..., "limit": ..., "offset": ...}`) and the response
envelope (`patentFileWrapperDataBag`, each entry's `applicationMetaData`
sub-object carrying `patentNumber`/`inventionTitle`/`filingDate`/
`grantDate`/`earliestPublicationNumber`/`earliestPublicationDate`) are
inferred from multiple independently-authored working API clients that
exercise this exact endpoint (a documented ODP-facing MCP server, a Python
"patent-client" library's own field-mapping docs, and a third-party agent
skill's worked example) rather than read directly off a live authenticated
response -- reasonably likely and mutually corroborating, but NOT
independently confirmed the way the fetch-by-number PDF endpoint above was.
`_parse_odp_search_candidates` is written defensively (a record with no
usable patent/publication number is skipped, never surfaced with a made-up
one) for the same reason `knowledge/digikey.py`'s `_parse_matches` is.

WHAT THIS SEARCH DOES NOT DO: RETURN A TEXT SNIPPET. `docs/tools/
uspto-patents.md`'s "Capabilities not yet used here" section (before this
ticket) read ODP as offering "separate fields for claims, brief-summary,
detailed-description and drawing-description text" the way PatentsView's
retired standalone API once did. What this ticket's research actually
found is narrower: ODP's `/patent/applications/search` endpoint accepts a
full-text `q` query (it searches the application's full text, per the
corroborating sources above), but the *response* it returns is
bibliographic/front-page metadata only -- title, dates, applicant/inventor,
classification -- not an excerpt of the matched claims or summary text.
Getting the actual document text back out requires a separate per-
application documents/content call, which is exactly what `ingest_patent`
(`knowledge/sourcing/patent.py`) already does for a chosen candidate (via
the real USPTO PDF, OCR'd if needed). So every candidate below carries a
`snippet` key for parity with `search_arxiv_papers`' candidate shape, and
it is always `None` -- an honestly-absent field, not a guess, mirroring
`parse_front_page_metadata`'s own "every key always present, `None` where
the sheet did not yield it" rule. `docs/tools/uspto-patents.md` records this
distinction plainly rather than repeating the more expansive claim
uncritically.

A CANDIDATE'S NUMBER COMES FROM `applicationMetaData`, NEVER FROM
`applicationNumberText`. USPTO's internal application number (e.g.
"17/123,902") is a THIRD numbering scheme, distinct from both a granted
patent number and an 11-digit pre-grant publication number --
`normalize_patent_number` was never verified against it and, worse, naively
stripping its "/" would turn "17/123,902" into "17123902", an 8-digit
string that would be silently (and wrongly) accepted as if it were a grant
number. `_candidate_identifier` below reads only `patentNumber` (once
granted) and `earliestPublicationNumber` (once published, even if not yet
granted) for exactly this reason.

Gated behind `require_external_network_tools_enabled("USPTO")`
(`knowledge/sourcing_common.py`) -- unlike `ingest_patent`
(`knowledge/sourcing/patent.py`), which fetches a document by number with no
account or credential of any kind, this call is credentialed the instant it
runs, the same posture as `knowledge/digikey.py`'s `lookup_digikey_datasheet`.
"""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from typing import Any

from knowledge.sourcing.patent import PatentIdentifier, PatentNumberError, normalize_patent_number
from knowledge.sourcing_common import post_json, require_external_network_tools_enabled

# The live, verified ODP full-text search endpoint -- see this module's
# docstring ("DISCOVERY SEARCH") for the 401/403/CORS evidence confirming it
# is real and what it requires.
_ODP_SEARCH_URL = "https://api.uspto.gov/api/v1/patent/applications/search"

GetApiKeyFn = Callable[[], str]
SearchOdpFn = Callable[[str, str, int], dict[str, Any]]


def _get_odp_api_key() -> str:
    """Real credential read -- see module docstring's "DISCOVERY SEARCH"
    section. This is the actual credential I/O boundary, not exercised
    directly by this repo's tests (no live USPTO_ODP_API_KEY or network
    access here); `search_uspto_patents` takes `get_api_key` as an
    injectable parameter defaulting to this function, exactly as
    `knowledge/digikey.py`'s `_get_access_token` does for `get_token`."""
    return os.environ["USPTO_ODP_API_KEY"]


def _search_uspto_odp(query: str, api_key: str, max_results: int) -> dict[str, Any]:
    """Real POST against the live ODP search endpoint -- see module
    docstring citation for the 401/403/CORS evidence that this URL, this
    method, and this header name are correct. The request body shape
    (`q`/`limit`/`offset`) is the best-corroborated of the shapes found
    across independent secondhand sources but was NOT itself confirmed
    against a live authenticated call -- see the docstring's honest
    caveat.

    The actual `Request`/`urlopen`/JSON-decode is
    `knowledge.sourcing_common.post_json` -- the same helper
    `knowledge/digikey.py`, `knowledge/mouser.py` and `knowledge/nexar.py`
    use for their own credentialed POSTs, factored out there rather than
    duplicated here a sixth time (see that function's own docstring)."""
    body = json.dumps({"q": query, "limit": max_results, "offset": 0}).encode()
    headers = {
        "X-Api-Key": api_key,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    return post_json(_ODP_SEARCH_URL, body, headers)


def _candidate_identifier(metadata: dict[str, Any]) -> PatentIdentifier | None:
    """The one usable identifier for an ODP search result, or `None` if it
    has none.

    Reads only `patentNumber` (set once the application has granted) and
    `earliestPublicationNumber` (set once it has published, granted or
    not) -- never `applicationNumberText`, USPTO's internal application
    number, which is a different numbering scheme entirely and would
    silently misparse (see module docstring). A record with neither --
    filed but not yet published, or in a document-kind series this client
    never verified against the fetch-by-number endpoint -- has nothing
    `ingest_patent` could use, so it is skipped rather than surfaced with
    an identifier that would fail on the very next call.
    """
    for raw_number in (metadata.get("patentNumber"), metadata.get("earliestPublicationNumber")):
        if not raw_number:
            continue
        try:
            return normalize_patent_number(str(raw_number))
        except PatentNumberError:
            continue
    return None


def _parse_odp_search_candidates(raw: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse an ODP `/patent/applications/search` response into an ordered
    list of candidate dicts, in the order ODP's own relevance/sort order
    returned them (nothing here re-sorts). A response with an empty
    `patentFileWrapperDataBag` -- a real "no matches" search, not a fetch
    failure -- parses cleanly to `[]`. See `_candidate_identifier` for why a
    record can be dropped rather than included."""
    candidates: list[dict[str, Any]] = []
    for item in raw.get("patentFileWrapperDataBag") or []:
        metadata = item.get("applicationMetaData") or {}
        identifier = _candidate_identifier(metadata)
        if identifier is None:
            continue
        candidates.append(
            {
                "number": identifier.display,
                "title": metadata.get("inventionTitle"),
                # The most specific milestone date available: a grant date
                # once granted, else the record's own (pre-grant)
                # publication date, else its filing date -- never all
                # three, so a caller reads one unambiguous date per
                # candidate rather than reconciling several.
                "date": (
                    metadata.get("grantDate")
                    or metadata.get("earliestPublicationDate")
                    or metadata.get("filingDate")
                ),
                # Always None: ODP's search response is bibliographic
                # metadata, not a full-text excerpt of the matched
                # document -- see module docstring's "WHAT THIS SEARCH
                # DOES NOT DO". Present anyway, for the same "unknown
                # stays unknown" total-schema reason
                # parse_front_page_metadata always emits every key.
                "snippet": None,
            }
        )
    return candidates


def search_uspto_patents(
    query: str,
    *,
    max_results: int = 10,
    get_api_key: GetApiKeyFn = _get_odp_api_key,
    search: SearchOdpFn = _search_uspto_odp,
) -> list[dict[str, Any]]:
    """Search the USPTO Open Data Portal by topic/full-text and return a
    list of **candidates for review** -- not documents in the corpus, and
    nothing this function does writes to the database or calls
    `ingest_document`/`ingest_patent` (directly or indirectly), under any
    input. Finding a patent and trusting it as evidence are two separate,
    deliberate steps: hand a chosen candidate's `number` straight to
    `ingest_patent` (`knowledge/sourcing/patent.py`, unchanged -- it already
    round-trips through `normalize_patent_number`, see
    `_candidate_identifier`) along with the `license`/`classification`
    ADR-0001 requires for that specific document.

    Refuses to run unless `ALLOW_EXTERNAL_NETWORK_TOOLS=true`
    (`require_external_network_tools_enabled`, see
    `knowledge/sourcing_common.py`) -- unlike `ingest_patent`
    (`knowledge/sourcing/patent.py`), this call is credentialed (a
    USPTO.gov account with a linked, ID.me-verified identity, see module
    docstring) the moment it runs, the same posture as this repo's
    Digi-Key/Mouser/Nexar distributor clients.

    `query` is ODP's own `q` full-text search parameter, passed through
    verbatim -- it searches the application's full text (per this module's
    docstring citations), not just its bibliographic fields. This function
    does not interpret or validate it.

    Each candidate dict carries `number` (the same written form
    `normalize_patent_number`/`ingest_patent` accept, e.g. "US12089385" or
    "US20250123456A1"), `title`, `date` (the most specific milestone date
    available -- see `_parse_odp_search_candidates`), and `snippet`
    (always `None` -- see module docstring's "WHAT THIS SEARCH DOES NOT
    DO"). A record ODP returns with no patent/publication number
    `normalize_patent_number` accepts is left out entirely, so every
    candidate this function returns is guaranteed usable by `ingest_patent`
    without a second validation pass.

    A topic with no matches returns `[]` -- a real "nobody has filed this"
    result, not an error. A `get_api_key` or `search` failure (a missing
    credential, the API unreachable, a network error) is deliberately
    *not* caught here and propagates as a raised exception instead, so
    "nobody has filed this" and "the search itself failed" can never be
    confused with each other -- mirroring `search_arxiv_papers`' same
    `fetch_fn`-failure contract (issue #257).

    `max_results` caps how many candidates come back in one call (ODP's own
    `limit` request field, default 10) -- small enough that a caller, human
    or model, can actually triage the list rather than getting back an
    unbounded page to sort through by hand.

    `get_api_key` and `search` default to the real credential read and the
    real HTTP POST (`_get_odp_api_key`, `_search_uspto_odp`) and exist so
    tests can inject stubs for both instead of a live credential or a live
    network call -- the same seam `knowledge/digikey.py`'s
    `lookup_digikey_datasheet` gives `get_token`/`search`.
    """
    require_external_network_tools_enabled("USPTO")
    api_key = get_api_key()
    raw = search(query, api_key, max_results)
    return _parse_odp_search_candidates(raw)
