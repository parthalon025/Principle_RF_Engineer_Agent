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
"""

from __future__ import annotations

import json
import tempfile
import xml.etree.ElementTree as ET
from collections.abc import Callable
from pathlib import Path
from typing import Any

from knowledge.ingest import ingest_document
from knowledge.sourcing._http import download_bytes

_TITLES_URL = "https://www.ecfr.gov/api/versioner/v1/titles.json"


def _full_text_url(as_of_date: str, title: int, part: int) -> str:
    return (
        f"https://www.ecfr.gov/api/versioner/v1/full/{as_of_date}/"
        f"title-{title}.xml?part={part}"
    )


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
