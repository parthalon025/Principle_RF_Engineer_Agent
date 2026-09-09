"""Thin client: FCC rule text (via eCFR Title 47) -> knowledge base
(ticket #68).

eCFR's own public "versioner" REST API is used, not the human-facing
www.ecfr.gov pages (which require a full chapter/subchapter breadcrumb in
the path -- e.g. /title-47/chapter-I/subchapter-A/part-15, not the shorter
/title-47/part-15 -- that isn't worth deriving when the API below is
simpler and was directly confirmed working during this ticket's research):

- `GET https://www.ecfr.gov/api/versioner/v1/titles.json` -- no
  authentication. Confirmed live during this ticket's research: returned
  real JSON for every title, including title 47's `up_to_date_as_of` date
  field.
- `GET https://www.ecfr.gov/api/versioner/v1/full/{date}/title-47.xml?
  part={part}` -- no authentication. Confirmed live during this ticket's
  research with `date` set to title 47's own `up_to_date_as_of` value and
  `part=15`: returned real regulation text opening "PART 15--RADIO
  FREQUENCY DEVICES", as a Federal-Register-specific XML DTD (`<DIV5
  TYPE="PART">`, `<HEAD>`, `<PSPACE>`, ... -- not general-purpose XHTML).
  `date` must be a date the versioner actually has an edition boundary
  for -- an arbitrary caller-supplied date can 404 (observed directly: an
  arbitrary historical date plus `?part=` 404'd where the title's own
  `up_to_date_as_of` date succeeded) -- so this client always resolves
  `date` from `titles.json` rather than accepting one from the caller.

Docling's confirmed supported-input-formats list (PDF, DOCX, PPTX, XLSX,
HTML, plain text, and a handful of specifically named XML schemas -- see
https://github.com/docling-project/docling) does not include this eCFR-
specific Federal-Register DTD, so this client does not hand the raw XML to
`ingest_document` and hope docling's generic handling copes with it.
Instead it flattens the XML to plain text locally (via
`xml.etree.ElementTree`, stdlib only, no new dependency) and writes that as
a `.txt` file -- the same plain-text-from-a-non-PDF-authoritative-source
shape this repo's own `knowledge/corpus/*.txt` files already use for other
non-PDF government sources (see tests/test_literature_corpus.py).

eCFR content is public domain as a work of the U.S. Government -- the
strongest license status of any source in this package. eCFR itself is
also explicitly not the official legal edition (GPO's Federal Register
printing is authoritative) -- fine for engineering reference; flag the
distinction if a result is ever used for formal regulatory sign-off (see
docs/FREE_AND_OPEN_SOURCE_TOOLING.md's FCC/eCFR row).

Thin client per this repo's knowledge-sourcing seam: resolve the current
edition date, fetch the part's XML, flatten it to text locally, hand that
file to `knowledge.ingest.ingest_document` unchanged
(`source_type='standard'`). No new ingestion logic lives here.

Discovery search (issue #279): `search_fcc_rules` below is a second,
separate entry point alongside `ingest_fcc_rule` -- "find which part covers
a topic" rather than "fetch the part I already know the number of". It
mirrors the "search returns candidates, a separate call ingests one" shape
issue #257 established in this same package for arXiv
(`search_arxiv_papers` in `knowledge/sourcing/arxiv.py`): same `fetch_fn`-
injection seam, same "empty list on zero matches, never an error" contract,
same "never itself calls `ingest_document`" guarantee.

It hits a third eCFR endpoint group this module hadn't used before --
`GET https://www.ecfr.gov/api/search/v1/results?query=<query>` -- confirmed
live during this ticket's research (734 hits for a search on "EIRP", the
FCC's cap on how strong a radiated signal is allowed to be). Each JSON
result carries a `hierarchy` object (`title`/`part`/`section`, all as
strings), a `headings` object (the matched section's actual heading text),
and a `full_text_excerpt` snippet with the matched term(s) wrapped in
`<strong>`; a zero-match query returns `{"results": [], "meta":
{"total_count": 0, ...}}` cleanly, not an error.

One eCFR-specific wrinkle arXiv's search doesn't have: the Search Service
accepts **no server-side title filter** -- confirmed live during this
ticket's research, passing `title=47` or `title[]=47` to `search/v1/results`
is rejected outright ("Found unpermitted parameter: :title"). Results span
every CFR title, not just 47. Since `ingest_fcc_rule` only ever fetches
Title 47 (its `title: int = 47` default is the only title this module's
XML-fetch path is confirmed to handle -- see this module's own docstring
above), `search_fcc_rules` filters non-Title-47 hits out client-side, so a
candidate handed back is never one `ingest_fcc_rule`'s hardcoded Title-47
assumption would silently mis-fetch or 404 against.
"""

from __future__ import annotations

import json
import tempfile
import xml.etree.ElementTree as ET
from collections.abc import Callable
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

from knowledge.ingest import ingest_document
from knowledge.sourcing._http import download_bytes

_TITLES_URL = "https://www.ecfr.gov/api/versioner/v1/titles.json"


def _full_text_url(as_of_date: str, title: int, part: int) -> str:
    return f"https://www.ecfr.gov/api/versioner/v1/full/{as_of_date}/title-{title}.xml?part={part}"


def _resolve_as_of_date(title: int, fetch_fn: Callable[[str], bytes]) -> str:
    payload = json.loads(fetch_fn(_TITLES_URL))
    for entry in payload.get("titles", []):
        if entry.get("number") == title:
            return entry["up_to_date_as_of"]
    raise ValueError(f"title {title} not found in eCFR titles.json response")


def _xml_to_text(xml_bytes: bytes) -> str:
    """Flatten eCFR's Federal-Register XML DTD down to plain text: every
    text node, in document order, whitespace-joined -- enough for lexical
    search and citation, not a layout-preserving transform."""
    root = ET.fromstring(xml_bytes)
    parts = [node.strip() for node in root.itertext() if node and node.strip()]
    return "\n".join(parts)


def ingest_fcc_rule(
    part: int,
    *,
    license: str,
    classification: str,
    title: int = 47,
    supersedes_document_id: int | None = None,
    download_dir: str | None = None,
    fetch_fn: Callable[[str], bytes] = download_bytes,
) -> dict[str, Any]:
    """Fetch FCC rule text for CFR `title` (default 47, Telecommunication)
    `part` (e.g. 15 for the Part 15 unlicensed-device rules, or 97 for the
    Part 97 amateur-radio rules) via eCFR's versioner API, and ingest it as
    `source_type='standard'`.

    `fetch_fn` defaults to a real HTTP GET (`knowledge.sourcing._http.
    download_bytes`) and exists so tests can inject a stub instead of
    hitting the network; when stubbed it is called twice -- once for the
    `titles.json` lookup, once for the resolved `full/{date}/title-{title}
    .xml?part={part}` fetch -- and must return the right bytes for each
    URL it's given (see this module's tests for the exact shape).
    """
    as_of_date = _resolve_as_of_date(title, fetch_fn)
    xml_bytes = fetch_fn(_full_text_url(as_of_date, title, part))
    text = _xml_to_text(xml_bytes)

    work_dir = Path(download_dir) if download_dir else Path(tempfile.mkdtemp(prefix="fcc_ecfr_"))
    work_dir.mkdir(parents=True, exist_ok=True)
    text_path = work_dir / f"title-{title}-part-{part}.txt"
    text_path.write_text(text, encoding="utf-8")

    return ingest_document(
        file_path=str(text_path),
        source_type="standard",
        license=license,
        classification=classification,
        supersedes_document_id=supersedes_document_id,
    )


# --- search_fcc_rules: topic/keyword discovery search (issue #279) --------
#
# Everything below is a second, separate entry point from ingest_fcc_rule
# above: it queries eCFR's `search/v1/results` endpoint (full-text query
# across every CFR title) instead of fetching a caller-named part's XML by
# number. It returns candidate dicts for review, never writes to the
# database, and never calls ingest_document -- see this module's docstring
# ("Discovery search (issue #279)") for the full rationale, including the
# client-side Title-47 filter this function applies (the Search Service
# itself rejects a server-side title parameter outright).

_SEARCH_API_URL = "https://www.ecfr.gov/api/search/v1/results"

# Deepest-to-shallowest CFR hierarchy levels eCFR's `headings` object can
# carry a heading for. A section-level hit (the common case) has a
# "section" heading; a result matched at a coarser level (no section in
# its own `hierarchy`) still has a heading at whichever level it landed on.
# Walking deepest-first picks the most specific heading text available
# without needing to cross-reference which level `hierarchy` itself bottoms
# out at.
_HEADING_LEVELS = (
    "section",
    "appendix",
    "subpart",
    "part",
    "subchapter",
    "chapter",
    "subtitle",
    "title",
)


def _search_url(query: str) -> str:
    """Build the eCFR Search Service URL: `query` verbatim (URL-encoded,
    not interpreted or validated here) and nothing else. No `per_page` or
    similar result-count parameter is added -- only `query=<query>` was
    confirmed live during this ticket's research; `max_results` below caps
    the parsed candidate list client-side instead of trusting an unverified
    query parameter (the same caution this module already applies to the
    Search Service's rejected `title` parameter -- see this module's
    docstring)."""
    return f"{_SEARCH_API_URL}?{urlencode({'query': query})}"


def _heading_text(headings: dict[str, Any]) -> str | None:
    """Return the most specific heading text present in a search result's
    `headings` object, or None if it carries none of the recognized
    levels."""
    for level in _HEADING_LEVELS:
        value = headings.get(level)
        if value:
            return value
    return None


def _parse_search_candidates(payload: dict[str, Any], max_results: int) -> list[dict[str, Any]]:
    """Parse a `search/v1/results` JSON payload into an ordered list of
    **Title-47-only** candidate dicts, in the order eCFR's own relevance
    ranking returned them (feed order is preserved, nothing here re-sorts).
    A payload with an empty `results` array -- a real "no matches" search,
    not a fetch failure -- parses cleanly to [].

    A result whose `hierarchy["title"]` is not the string `"47"` is dropped
    -- see this module's docstring on why: `ingest_fcc_rule` only ever
    fetches Title 47, so a non-47 candidate would silently mis-fetch or
    404 if handed straight to it. A dropped result does not count against
    `max_results` -- the cap applies to the Title-47 candidates actually
    returned, not to eCFR's raw (every-title) result count.
    """
    candidates: list[dict[str, Any]] = []
    for result in payload.get("results", []):
        hierarchy = result.get("hierarchy") or {}
        if hierarchy.get("title") != "47":
            continue
        part_raw = hierarchy.get("part")
        try:
            part = int(part_raw)
        except (TypeError, ValueError):
            continue

        candidates.append(
            {
                "part": part,
                "title": 47,
                "section": hierarchy.get("section"),
                "heading": _heading_text(result.get("headings") or {}),
                "full_text_excerpt": result.get("full_text_excerpt"),
            }
        )
        if len(candidates) >= max_results:
            break
    return candidates


def search_fcc_rules(
    query: str,
    *,
    max_results: int = 10,
    fetch_fn: Callable[[str], bytes] = download_bytes,
) -> list[dict[str, Any]]:
    """Search eCFR's full-text Search Service by topic/keyword and return a
    ranked list of **Title-47 candidates for review** -- not documents in
    the corpus, and nothing this function does writes to the database or
    calls `ingest_document` (directly or indirectly), under any input.
    Finding a rule and trusting it as evidence are two separate, deliberate
    steps: hand a chosen candidate's `part` straight to `ingest_fcc_rule`
    (unchanged -- same `title=47` default, same int form) along with the
    `license`/`classification` ADR-0001 requires for that specific rule.

    `query` is eCFR's `query` parameter -- a full-text search over every
    CFR title's rule text (as opposed to `ingest_fcc_rule`'s fetch-by-
    already-known-part-number). Passed through verbatim (URL-encoded); this
    function does not interpret or validate it.

    Each candidate dict carries `part` (int, e.g. `90` -- the exact form
    `ingest_fcc_rule(part, ...)` already accepts), `title` (always `47`;
    every non-Title-47 hit eCFR returns is filtered out before it reaches
    this list -- see below), `section` (the CFR citation, e.g. `"90.391"`),
    `heading` (the matched section's heading text, e.g. `"Maximum EIRP and
    antenna height."`), and `full_text_excerpt` (eCFR's own snippet, matched
    term(s) wrapped in `<strong>`) -- enough to judge relevance before
    spending an ingestion pass on it.

    eCFR's Search Service spans every CFR title, not just 47, and accepts
    **no server-side title filter** (confirmed live during this ticket's
    research: passing `title=47` or `title[]=47` is rejected outright,
    "Found unpermitted parameter: :title"). Since `ingest_fcc_rule` only
    ever fetches Title 47, this function filters non-Title-47 results out
    client-side rather than returning a candidate `ingest_fcc_rule` would
    silently mis-fetch or 404 against.

    A topic with no matches returns `[]` -- a real "no Title 47 rule
    mentions this" result, not an error. A `fetch_fn` failure (the API
    unreachable, a network error) is deliberately *not* caught here and
    propagates as a raised exception instead, so "nothing matches" and "the
    search itself failed" can never be confused with each other (mirroring
    `search_arxiv_papers`, issue #257).

    `max_results` caps how many Title-47 candidates come back in one call
    (default 10) -- applied after the client-side title filter, so it
    always bounds what a caller actually receives, not eCFR's raw
    every-title hit count.

    `fetch_fn` defaults to a real HTTP GET (`knowledge.sourcing._http.
    download_bytes`) against the same credential-free eCFR API this
    module's docstring already confirms needs no authentication, and
    exists so tests can inject a stub instead of hitting the network --
    the same seam `ingest_fcc_rule` already uses.
    """
    payload = json.loads(fetch_fn(_search_url(query)))
    return _parse_search_candidates(payload, max_results)
