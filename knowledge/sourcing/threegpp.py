"""Thin client: 3GPP specification -> knowledge base (ticket #68).

URL shape and no-login access confirmed against 3GPP's own FTP archive
(`https://www.3gpp.org/ftp/Specs/archive/`, an openly browsable directory
tree), cross-checked against two independent third-party tools that
document scripting against it directly with no authentication step:
- https://github.com/bnlrnz/3GPP_Spec_Downloader
- https://blueskyjunkie.ca/articles/2020-02/announcing-download-3gpp

Confirmed pattern:
    https://www.3gpp.org/ftp/Specs/archive/{series}_series/{spec}/
        {spec_with_first_dot_removed}-{version}.zip
e.g. spec "38.331" version "h00" ->
.../38_series/38.331/38331-h00.zip; a multi-part spec like "38.521-1"
keeps its own internal dash intact ->
.../38_series/38.521-1/38521-1-h00.zip (only the first "." -- the one
separating series from spec number -- is removed).

3GPP distributes each spec as a .zip containing one Word document (.docx
for current specs; older specs sometimes ship legacy binary .doc, which
docling's own supported-input-formats list -- PDF, DOCX, PPTX, XLSX, HTML,
plain text, and others, see https://github.com/docling-project/docling --
does not confirm support for). This client extracts the single .docx/.doc
member from the downloaded zip (preferring .docx when both are present,
and the largest file of whichever suffix wins, since 3GPP zips sometimes
bundle a small cover/history sheet alongside the actual spec text) and
hands *that* file to `ingest_document`. If the extracted file turns out to
be a legacy .doc docling can't parse, `ingest_document`'s own existing
failure handling still stores the document row with
`extraction_status="failed"` rather than crashing -- this client does not
special-case that; the honest caveat is simply that a pre-2020ish spec may
come back with zero chunks.

3GPP specifications are free to download with no registration, but are
**not** public domain: copyright is jointly held by the 3GPP Organizational
Partners and each document carries its own reproduction-restriction notice
(confirmed against 3gpp.org during docs/FREE_AND_OPEN_SOURCE_TOOLING.md's
own prior research pass). Pass the license string that reflects that --
this client does not assume a specific one.

Thin client per this repo's knowledge-sourcing seam: download the zip,
extract the one document file, hand it to `knowledge.ingest.ingest_document`
unchanged (`source_type='standard'`). No new ingestion logic lives here.

This module also holds a second responsibility added by ticket #285:
`lookup_3gpp_spec_status`, a DynaReport-backed version/withdrawal status
lookup with no ingestion step of its own (see the "DynaReport version/
withdrawal lookup" section comment below, above `SpecNotFoundError`, for
its full scope). Kept in this file rather than split out per CLAUDE.md's
"Improve before adding" SRP guidance -- "extend when the file stays
cohesive; split only when adding would push it past one responsibility":
both functions are 3GPP-sourcing concerns sharing the same `_spec_url`-
style series-derivation rule (text before the first ".") and the same
injectable `fetch_fn` seam, and a reader asking "how does this repo talk
to 3GPP" needs both together, not decoupled into separate files.
"""

from __future__ import annotations

import io
import tempfile
import zipfile
from collections.abc import Callable
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

from knowledge.ingest import ingest_document
from knowledge.sourcing._http import download_bytes


class SpecNotFoundError(ValueError):
    """Raised by `lookup_3gpp_spec_status` when `spec_number` does not
    appear as a row in the fetched DynaReport per-series table -- e.g. a
    typo, or a spec that belongs to a different series than the one
    derived from it.

    A `ValueError` subclass, not a bare `Exception`: this is "the
    identifier given doesn't resolve to a row in a fetched collection", the
    same failure shape this repo's closest precedents already name --
    `geometry.unit_cell.SymbolNotFoundError` and
    `designs.design_families.UnknownDesignFamilyError`, both `ValueError`
    subclasses naming exactly what was looked for and what IS available,
    never a bare `KeyError` (`knowledge.db.DuplicateDocumentError`, the
    other module this class was previously compared to, is the same "warn,
    never guess" instinct applied to a different failure shape -- a
    conflict/already-exists case, not a lookup miss -- so it is a weaker
    analog for base-class choice than the two above). Identify exactly what
    is missing rather than returning an empty/placeholder result."""


# Preference order when a 3GPP zip contains more than one candidate member:
# .docx (current specs) before legacy .doc (docling support unconfirmed).
_DOC_SUFFIXES = (".docx", ".doc")


def _spec_url(spec_number: str, version: str) -> str:
    series = spec_number.split(".", 1)[0]
    spec_no_first_dot = spec_number.replace(".", "", 1)
    return (
        f"https://www.3gpp.org/ftp/Specs/archive/{series}_series/"
        f"{spec_number}/{spec_no_first_dot}-{version}.zip"
    )


def _extract_primary_document(zip_bytes: bytes, dest_dir: Path) -> Path:
    """Pick the one .docx/.doc member to hand to `ingest_document` -- see
    this module's docstring for the preference rule."""
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        candidates = [
            info
            for info in zf.infolist()
            if not info.is_dir() and info.filename.lower().endswith(_DOC_SUFFIXES)
        ]
        if not candidates:
            raise ValueError(
                "3GPP archive contained no .docx/.doc member "
                f"(found: {[i.filename for i in zf.infolist()]})"
            )
        chosen = None
        for suffix in _DOC_SUFFIXES:
            matching = [c for c in candidates if c.filename.lower().endswith(suffix)]
            if matching:
                chosen = max(matching, key=lambda c: c.file_size)
                break
        assert chosen is not None  # every candidate matched one of _DOC_SUFFIXES
        extracted_path = Path(zf.extract(chosen, path=dest_dir))
    return extracted_path


def ingest_3gpp_spec(
    spec_number: str,
    version: str,
    *,
    license: str,
    classification: str,
    supersedes_document_id: int | None = None,
    download_dir: str | None = None,
    fetch_fn: Callable[[str], bytes] = download_bytes,
) -> dict[str, Any]:
    """Download 3GPP spec `spec_number` (e.g. "38.331") at `version` (3GPP's
    own version string as it appears in the archive filename, e.g. "h00")
    and ingest it as `source_type='standard'`.

    `fetch_fn` defaults to a real HTTP GET (`knowledge.sourcing._http.
    download_bytes`) and exists so tests can inject a stub instead of
    hitting the network; when stubbed it must return the raw zip bytes for
    the constructed archive URL.
    """
    url = _spec_url(spec_number, version)
    zip_bytes = fetch_fn(url)

    work_dir = Path(download_dir) if download_dir else Path(tempfile.mkdtemp(prefix="3gpp_"))
    work_dir.mkdir(parents=True, exist_ok=True)
    doc_path = _extract_primary_document(zip_bytes, work_dir)

    return ingest_document(
        file_path=str(doc_path),
        source_type="standard",
        license=license,
        classification=classification,
        supersedes_document_id=supersedes_document_id,
    )


# --- DynaReport version/withdrawal lookup (ticket #285) --------------------
#
# `ingest_3gpp_spec` above requires the caller to already know 3GPP's own
# base-36 version string and never checks whether the spec has been
# withdrawn -- see this module's docstring for what `ingest_3gpp_spec` does
# and does not do. `lookup_3gpp_spec_status` below is a standalone answer to
# "what is the current version of spec X, and has it been withdrawn?",
# fetched from 3GPP's own DynaReport per-series HTML table
# (`https://www.3gpp.org/dynareport?code={series}-series.htm`), built the
# same way `_spec_url` above derives `series` (text before the first "."
# only). It does not change `ingest_3gpp_spec`'s signature or behaviour.
#
# THE VERSION FIELD IS ALWAYS `None`, AND THAT IS NOT A BUG. This ticket's
# own acceptance criteria (and docs/tools/3gpp.md's "Capabilities not yet
# used here" section, written before this function existed) both assumed
# the per-series DynaReport table carries a current-version string per
# spec row. Fetching the real live page during this ticket's implementation
# (`https://www.3gpp.org/dynareport?code=38-series.htm`, 2026-09) disproves
# that: its own `<thead>` declares exactly three columns -- "spec number",
# "title", "notes" -- and every one of its 272 data rows' notes cell is one
# of exactly two values, a blank `&nbsp;` or "SPECIFICATION WITHDRAWN".
# There is no version column to parse, on this report, for any spec. A real
# current-version number does exist on 3GPP's site, but only on the much
# heavier, ASP.NET/RadGrid-rendered per-*spec* detail page
# (`https://www.3gpp.org/dynareport/{spec-no-dot}.htm`, one fetch per spec,
# not per series) -- a different report, a different URL shape, and enough
# extra parsing surface that pulling it in here would silently turn a
# "parse one HTML table" ticket into "scrape an ASP.NET postback widget".
# Per this repo's "warn, never silently apply the wrong tool" convention:
# rather than fabricate a version number this endpoint does not publish, or
# silently drop the field, `version` is always returned as `None` with this
# reasoning on the record. Closing the gap for real means a follow-up ticket
# against the per-spec detail page, not stretching this one.
#
# Independently re-checked during this diff's own code review (2026-09-09):
# a direct fetch of the live page hit the same HTTP 403 3gpp.org returns to
# most automated clients, but a text-rendering proxy fetch of the same URL
# confirmed the same shape reported above -- a flat "spec number / title /
# status" list with no version column and no base-36 version-style token
# (e.g. "h00") anywhere on the page. This does not replace re-fetching the
# real page if 3GPP ever changes its markup; it corroborates the finding on
# the record a second time, from a second vantage point.
class _SeriesTableParser(HTMLParser):
    """Parses the `<table id="a3dyntab">` on a 3GPP DynaReport per-series
    page into rows of `{"spec_number", "title", "withdrawn"}`. Handles the
    real page's own markup quirks confirmed against a live fetch: a stray
    unmatched `</span>` after the spec-number link (HTMLParser tolerates an
    end tag with no matching start tag -- it is simply a no-op here), and
    the spec number itself living inside a nested `<a>` rather than being
    the cell's whole text (the cell also carries a leading "TS "/"TR " type
    label)."""

    _TABLE_ID = "a3dyntab"

    def __init__(self) -> None:
        super().__init__()
        self.rows: list[dict[str, Any]] = []
        self._table_depth = 0
        self._in_row = False
        self._cell_index = -1
        self._in_link = False
        self._current_row: dict[str, Any] | None = None
        self._current_text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = dict(attrs)
        if tag == "table":
            if attrs_dict.get("id") == self._TABLE_ID:
                self._table_depth = 1
            elif self._table_depth:
                self._table_depth += 1
            return
        if not self._table_depth:
            return
        if tag == "tr":
            self._in_row = True
            self._cell_index = -1
            self._current_row = {"spec_number": "", "title": "", "withdrawn": False}
        elif tag == "td" and self._in_row:
            self._cell_index += 1
            self._current_text = []
        elif tag == "a" and self._cell_index == 0:
            self._in_link = True
            self._current_text = []

    def handle_endtag(self, tag: str) -> None:
        if not self._table_depth:
            return
        if tag == "table":
            self._table_depth -= 1
        elif tag == "a" and self._in_link:
            self._in_link = False
            assert self._current_row is not None  # only set inside a <tr>
            self._current_row["spec_number"] = "".join(self._current_text).strip()
        elif tag == "td" and self._in_row:
            text = "".join(self._current_text).strip()
            assert self._current_row is not None  # only set inside a <tr>
            if self._cell_index == 1:
                self._current_row["title"] = text
            elif self._cell_index == 2:
                self._current_row["withdrawn"] = "WITHDRAWN" in text.upper()
        elif tag == "tr" and self._in_row:
            self._in_row = False
            if self._current_row is not None and self._current_row["spec_number"]:
                self.rows.append(self._current_row)
            self._current_row = None

    def handle_data(self, data: str) -> None:
        if self._in_row and self._cell_index >= 0:
            self._current_text.append(data)


def _parse_series_table(html_text: str) -> list[dict[str, Any]]:
    """Pure parsing half of `lookup_3gpp_spec_status` -- "caller fetches,
    this function only resolves" (this repo's own convention; see
    `geometry/unit_cell.py`'s docstring, which credits
    `designs.material_properties.resolve_material_property` for the same
    phrasing, for the pattern this mirrors). Takes the already-decoded HTML
    of a DynaReport per-series page and returns one dict per spec row:
    `spec_number`, `title`, `withdrawn` (`version` is not present here --
    see the section docstring above for why `lookup_3gpp_spec_status`
    always reports it as `None`). Directly unit-testable with a plain
    string, no network/fetch_fn involved.
    """
    parser = _SeriesTableParser()
    parser.feed(html_text)
    return parser.rows


def lookup_3gpp_spec_status(
    spec_number: str,
    *,
    fetch_fn: Callable[[str], bytes] = download_bytes,
) -> dict[str, Any]:
    """Look up `spec_number` (e.g. "38.101" or "38.101-1") in 3GPP's own
    DynaReport per-series table and report its title and whether 3GPP has
    marked it withdrawn -- e.g. TS 38.101 itself is withdrawn while its
    five parts, 38.101-1..5, remain current.

    Returns `{"spec_number", "title", "withdrawn", "version"}`. `version`
    is always `None` -- see the section docstring above this function for
    why the per-series report this function reads has no version column to
    report, on the real page, for any spec.

    Raises `SpecNotFoundError` if `spec_number` does not appear as a row in
    the fetched table (a typo, or a spec whose series differs from the one
    derived from it) -- this function never guesses or returns a
    placeholder status. The error names every spec number the fetched
    table DID contain (matching `geometry.unit_cell.SymbolNotFoundError`'s
    "name what was sought and what IS available" shape), so a caller can
    tell a mistyped spec/dash/suffix apart from a series table that came
    back empty or malformed.

    `fetch_fn` defaults to a real HTTP GET (`knowledge.sourcing._http.
    download_bytes`) and exists so tests can inject a stub instead of
    hitting the network, the same seam `ingest_3gpp_spec` above uses.
    """
    series = spec_number.split(".", 1)[0]
    url = f"https://www.3gpp.org/dynareport?code={series}-series.htm"
    html_bytes = fetch_fn(url)
    rows = _parse_series_table(html_bytes.decode("utf-8", errors="replace"))

    for row in rows:
        if row["spec_number"] == spec_number:
            return {
                "spec_number": spec_number,
                "title": row["title"],
                "withdrawn": row["withdrawn"],
                "version": None,
            }

    known = sorted(row["spec_number"] for row in rows)
    raise SpecNotFoundError(
        f"{spec_number!r} not found in the {series}-series DynaReport table "
        f"fetched from {url}. Known spec numbers in that table: "
        f"{known if known else '(table had no rows -- check the series page itself)'}."
    )
