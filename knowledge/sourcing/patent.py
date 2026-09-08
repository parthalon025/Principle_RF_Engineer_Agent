"""Thin client: US patent document -> knowledge base (issue #219), converted
via the vendored arxiv-doc-builder skill's PDF converters
(`.claude/skills/arxiv-doc-builder`).

Fetch by identifier only, like every other client in this package. Patent
*search* -- "find me patents about conformal metamaterial skins" -- is not
built here or anywhere in this repo.

SOURCE, VERIFIED DIRECTLY, NOT RECONSTRUCTED FROM MEMORY
--------------------------------------------------------
    https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/<number>

returns `application/pdf`, HTTP 200, with no API key, no account and no
credential of any kind. Confirmed live against five documents during this
ticket: grants 12089385 (32 pages), 11000000 (8 pages), and pre-grant
publications 20220192066 (31 pages), 20240001234 (18 pages). `<number>` is
bare digits: the endpoint returns HTTP 400 for "US12089385B2", which is why
`normalize_patent_number` strips the country code and kind code before
building the URL.

Google Patents is NOT used and must not be added: it answers HTTP 503 to
this network (anti-bot filtering on datacenter IP ranges), so anything built
on it would work on a laptop and fail everywhere this project actually runs.

EVERY USPTO PDF SAMPLED IS A SCANNED IMAGE -- AN HONEST WARNING
---------------------------------------------------------------
All five PDFs above come back with a **zero-character text layer**: they are
page images produced by "USPTO PDF Builder", not digital text. That includes
the pre-grant publications, which is worth stating plainly because it
contradicts the reasonable assumption that a modern application publication
is born digital. An OCR'd copy of the *same* disclosure obtained elsewhere
(e.g. US 2022/0192066 A1 as distributed by Google's patent-image mirror)
does carry a text layer -- 71,864 characters over 31 pages -- so the two
kinds of document genuinely both exist; they just do not both come from this
endpoint today.

*In plain terms: what USPTO hands back is a photograph of the patent, not
the words of it. You can see it; a text search cannot read it until
something transcribes it.*

This is why the route below is decided by **what the file actually
contains**, never by whether the number is a grant or a publication:

  - **Text-layer route** (`TEXT_LAYER_ROUTE`). The PDF has real text. The
    vendored `pdf_converter_lib.extract_page_content(..., is_double_column=
    True)` reads it two columns at a time and strips running headers/footers
    -- exactly a patent's printed layout -- and the resulting Markdown, with
    a patent frontmatter block on top, is what gets ingested.
  - **Scanned/vision route** (`SCANNED_VISION_ROUTE`). The PDF has no text
    to read. Two things then happen, and both matter:
      * the **original PDF** is handed to `ingest_document`, whose docling
        pipeline runs OCR (`knowledge/extraction.py`, `do_ocr=True`), so the
        document still becomes searchable text in the knowledge base; and
      * every page, plus its two column crops, is rendered to PNG by the
        vendored `pdf_image_lib.convert_pdf_to_images`, because OCR reads
        prose far better than it reads a drawing sheet, and this project's
        load-bearing numbers live in the figures. Settling one digit in
        FIG. 11C of US12089385B2 took exactly this rendering step.
    Rendering needs poppler installed (pdf2image shells out to it). If it is
    missing, the ingest still happens and the failure is recorded rather
    than raised -- warn, never block. The images are an aid to reading, not
    the document.

NO AUTHORITY-RANK OVERRIDE IS PASSED, DELIBERATELY. Unlike
`knowledge/sourcing/arxiv.py`, this client sets no `authority_rank_override`:
`source_type='patent'` already defaults to `PATENT_AUTHORITY_RANK` (50) in
`knowledge/provenance.py`, ranked below a peer-reviewed paper because a
patent office examines for novelty and candor, not for whether a stated
number reproduces. Passing an override here would restate that default in a
second place, where the two could drift apart.

READ A PATENT'S CLAIMS AS LEGAL TEXT, NEVER AS DESIGN GUIDANCE. Chunking is
by text and cannot tell a claim from a worked example (see
`knowledge/provenance.py`). This client cannot fix that and does not pretend
to; it is repeated here because this is the module that puts patents into
the corpus in the first place.

Not gated behind ALLOW_EXTERNAL_NETWORK_TOOLS: that gate
(`knowledge/sourcing_common.py`) exists for the three CREDENTIALED
distributor APIs. USPTO, like this package's 3GPP/ETSI/FCC/arXiv siblings,
needs no account or credential -- same ungated posture as those, and the
same `ingestion_auto` category in `policies/tool_policy.yaml`.
"""

from __future__ import annotations

import json
import re
import subprocess
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from knowledge.ingest import ingest_document
from knowledge.sourcing._http import download_bytes

_USPTO_PDF_URL_BASE = "https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf"

# .claude/skills/arxiv-doc-builder from this file's location:
# knowledge/sourcing/patent.py -> knowledge/sourcing -> knowledge -> repo root.
_REPO_ROOT = Path(__file__).resolve().parents[2]
_ARXIV_DOC_BUILDER_DIR = _REPO_ROOT / ".claude" / "skills" / "arxiv-doc-builder"
_CONVERT_SCRIPT = Path(__file__).resolve().parent / "_patent_convert.py"

# Same generous bound as arxiv.py's convert-paper call: enough for a cold
# `uv sync` of the skill's environment plus a full-document pass, without
# hanging the caller forever on a stalled subprocess.
_PATENT_CONVERT_TIMEOUT_S = 600

GRANT = "grant"
PRE_GRANT_PUBLICATION = "pre_grant_publication"

TEXT_LAYER_ROUTE = "text_layer"
SCANNED_VISION_ROUTE = "scanned_vision"

# Route threshold, in mean extracted characters per page. The gap this sits
# in is enormous, not marginal: every USPTO-served PDF measured here scores
# 0, and a real text layer scores ~2,300 (the OCR'd US 2022/0192066 A1:
# 71,864 characters over 31 pages, its thinnest drawing sheet still 87 and
# its body pages ~7,000). 100 is a fence in empty ground -- it is not
# claiming that 99 means scanned and 101 means readable.
#
# The mean, not the per-page minimum, is what is tested: a patent's drawing
# sheets carry only reference numerals even in a perfectly readable
# document, so a per-page rule would call a good document scanned.
_MIN_MEAN_TEXT_CHARS_PER_PAGE = 100

# INID codes -- the parenthesised numbers printed on a patent's front sheet
# (WIPO Standard ST.9), which label each bibliographic field the same way in
# every country. These are the ones this client reads.
_INID_TITLE = "54"
_INID_DOCUMENT_NUMBER = "10"
_INID_PUBLICATION_DATE = "43"  # pre-grant publication
_INID_GRANT_DATE = "45"  # granted patent
_INID_APPLICATION_NUMBER = "21"
_INID_FILING_DATE = "22"
_INID_APPLICANT = "71"
_INID_INVENTORS = "72"
_INID_ASSIGNEE = "73"
_INID_ABSTRACT = "57"

# A marker as it survives extraction: "( 54 )", "(43)", and -- seen for real
# on the US 2022/0192066 A1 front sheet -- "(4 3 )", where the space fell
# between the two digits.
_INID_MARKER_RE = re.compile(r"\(\s*(\d)\s*(\d)\s*\)")

# The printed label that follows a marker and is not part of the value.
_INID_LABELS: dict[str, re.Pattern[str]] = {
    _INID_DOCUMENT_NUMBER: re.compile(r"^(?:Pub|Patent)\s*\.?\s*No\s*\.?\s*:?\s*", re.I),
    _INID_PUBLICATION_DATE: re.compile(r"^Pub\s*\.?\s*Date\s*\.?\s*:?\s*", re.I),
    _INID_GRANT_DATE: re.compile(r"^Date\s+of\s+Patent\s*:?\s*", re.I),
    _INID_APPLICATION_NUMBER: re.compile(r"^Appl\s*\.?\s*No\s*\.?\s*:?\s*", re.I),
    _INID_FILING_DATE: re.compile(r"^(?:Filed|PCT\s+Filed)\s*:?\s*", re.I),
    _INID_APPLICANT: re.compile(r"^Applicants?\s*:?\s*", re.I),
    _INID_INVENTORS: re.compile(r"^Inventors?\s*:?\s*", re.I),
    _INID_ASSIGNEE: re.compile(r"^Assignee\s*:?\s*", re.I),
    _INID_ABSTRACT: re.compile(r"^ABSTRACT\s*", re.I),
}

# Fields printed on one line. Anything after that line belongs to whatever
# comes next on the sheet, not to this field.
_SINGLE_LINE_INIDS = frozenset(
    {
        _INID_DOCUMENT_NUMBER,
        _INID_PUBLICATION_DATE,
        _INID_GRANT_DATE,
        _INID_APPLICATION_NUMBER,
        _INID_FILING_DATE,
    }
)

# Section headings that end a multi-line field even though no new INID
# marker has appeared yet.
_SECTION_HEADINGS = (
    "publication classification",
    "prior publication data",
    "related u.s. application data",
    "foreign application priority data",
    "references cited",
    "field of classification search",
    "primary examiner",
    "assistant examiner",
    "attorney, agent",
)

_CLAIMS_LINE_RE = re.compile(r"^\d+\s+claims\b", re.I)

# A line with no letters at all is not prose. On a front sheet it is the
# drawing bleeding into the text layer -- the real US 2022/0192066 A1
# extraction ends its abstract with "1*1?," and "$" picked up off FIG. 1 --
# so a multi-line field stops there rather than carrying the artifact into
# the stored abstract.
_HAS_LETTER_RE = re.compile(r"[A-Za-z]")

# Frontmatter keys promoted to their own `ingest_document` parameter rather
# than riding along in extra_metadata -- same split arxiv.py makes.
_PROMOTED_FRONTMATTER_KEYS = frozenset({"title", "inventors", "kind_code"})


class PatentNumberError(ValueError):
    """The given identifier is not a US patent or publication number this
    client will fetch. Raised before any network call."""


@dataclass(frozen=True)
class PatentIdentifier:
    """One US patent document, in the three forms this client needs.

    `number` is bare digits, which is the only form the USPTO endpoint
    accepts. `kind_code` is the letter-and-digit suffix that says what
    *kind* of document it is -- "A1" a published application, "B2" a granted
    patent that was published as an application first, "B1" one that was
    not -- and is `None` when the caller did not supply one. `display` is the
    conventional written form, e.g. "US12089385B2".
    """

    number: str
    kind_code: str | None
    document_kind: str
    display: str


def _digits_kind(digits: str) -> str:
    """Grant or pre-grant publication, decided by how many digits there are.

    A US publication number is 11 digits -- a four-digit year followed by a
    seven-digit serial (20220192066 is the 192,066th publication of 2022).
    A granted US patent number is a plain running count, 7 or 8 digits at
    today's numbers (12,089,385 was granted in 2024). Nothing else is
    accepted, because nothing else was verified against the endpoint.
    """
    if len(digits) == 11:
        year = int(digits[:4])
        if not 2001 <= year <= 2099:
            raise PatentNumberError(
                f"{digits!r} looks like an 11-digit publication number but its year "
                f"({year}) is outside 2001-2099; US pre-grant publication began in "
                "March 2001."
            )
        return PRE_GRANT_PUBLICATION
    if len(digits) in (7, 8):
        return GRANT
    raise PatentNumberError(
        f"{digits!r} is neither a 7-8 digit US grant number nor an 11-digit US "
        "pre-grant publication number. Reissue (RE), design (D), plant (PP) and "
        "other prefixed series are refused here because their URL form was never "
        "verified against the USPTO endpoint -- refusing beats fetching the wrong "
        "document."
    )


def normalize_patent_number(raw: str) -> PatentIdentifier:
    """Turn a written patent number into the parts this client needs, or
    raise `PatentNumberError` explaining what was wrong.

    Accepts the forms people actually paste: "US12089385B2",
    "US 12,089,385 B2", "12089385", "US 2022/0192066 A1", "20220192066".
    Separators (spaces, commas, slashes, hyphens) carry no meaning in a
    patent number, so they are dropped.

    Validated the way `arxiv_doc_builder/arxiv_id.py` validates an arXiv ID
    -- strictly, and *before* the network call, so a typo produces a
    sentence rather than a wrong document. In particular a kind code that
    disagrees with the number's own shape is refused rather than ignored:
    "US12089385A1" claims to be a published application while carrying a
    grant number, and one of the two is a mistake.
    """
    if not raw or not raw.strip():
        raise PatentNumberError("no patent number given")

    compact = re.sub(r"[\s,/\-.]", "", raw.strip().upper())

    country = re.match(r"^([A-Z]{2})(?=\d)", compact)
    if country and country.group(1) != "US":
        raise PatentNumberError(
            f"{raw!r} names a {country.group(1)} document; this client fetches US "
            "documents only, because the endpoint it uses is the USPTO's."
        )
    if country:
        compact = compact[2:]

    match = re.fullmatch(r"(\d+)([A-Z]\d?)?", compact)
    if not match:
        raise PatentNumberError(
            f"not a recognizable US patent or publication number: {raw!r}. Expected "
            'e.g. "US12089385B2", "12089385", "US 2022/0192066 A1" or "20220192066".'
        )

    digits, kind_code = match.group(1), match.group(2)
    document_kind = _digits_kind(digits)

    if kind_code:
        expected_letter = "A" if document_kind == PRE_GRANT_PUBLICATION else "BCEHPS"
        if kind_code[0] not in expected_letter:
            raise PatentNumberError(
                f"{raw!r} carries kind code {kind_code!r}, which disagrees with the "
                f"number itself ({digits} is a {document_kind.replace('_', ' ')}). "
                "One of the two is wrong; this client will not guess which."
            )

    display = f"US{digits}{kind_code or ''}"
    return PatentIdentifier(
        number=digits, kind_code=kind_code, document_kind=document_kind, display=display
    )


def patent_pdf_url(identifier: PatentIdentifier) -> str:
    """The USPTO download URL for this document. Bare digits only -- the
    endpoint answers HTTP 400 to "US12089385B2"."""
    return f"{_USPTO_PDF_URL_BASE}/{identifier.number}"


def choose_conversion_route(text_chars: int, page_count: int) -> str:
    """Decide how to read this PDF, from what it actually contains.

    Returns `TEXT_LAYER_ROUTE` when the document carries enough real text to
    read directly, `SCANNED_VISION_ROUTE` when it is page images and must be
    OCR'd and looked at instead. Pure: no I/O, so the threshold is testable
    on its own. See `_MIN_MEAN_TEXT_CHARS_PER_PAGE` for where the line sits
    and why it is nowhere near either population.
    """
    if page_count <= 0:
        return SCANNED_VISION_ROUTE
    return (
        TEXT_LAYER_ROUTE
        if text_chars / page_count >= _MIN_MEAN_TEXT_CHARS_PER_PAGE
        else SCANNED_VISION_ROUTE
    )


def _tidy(text: str) -> str:
    """Collapse whitespace and close up the space PDF extraction leaves in
    front of punctuation ("Zaghloul , Bethesda" -> "Zaghloul, Bethesda").

    Deliberately conservative. Extraction also splits words at hyphens
    ("HIGHLY - CONFORMAL") and inside them ("sub -w avelength"), and those
    are left exactly as they came out: repairing them means guessing which
    spaces were never in the printed document, and a guessed title that
    reads well is worse than a scruffy one that is verifiably what the page
    said.
    """
    collapsed = re.sub(r"\s+", " ", text).strip()
    collapsed = re.sub(r"\s+([,;:.])", r"\1", collapsed)
    collapsed = re.sub(r"\(\s+", "(", collapsed)
    collapsed = re.sub(r"\s+\)", ")", collapsed)
    return collapsed.strip()


def _is_boundary(line: str) -> bool:
    """Whether `line` ends the multi-line field being accumulated."""
    stripped = line.strip()
    lowered = stripped.lower().rstrip(".")
    if any(lowered.startswith(heading) for heading in _SECTION_HEADINGS):
        return True
    if _CLAIMS_LINE_RE.match(stripped):
        return True
    return not _HAS_LETTER_RE.search(stripped)


def _split_inid_fields(text: str) -> dict[str, str]:
    """Split front-sheet text into `{INID code: raw value}`.

    A value runs from the end of its own marker to the start of the next
    one, which is what makes this work on a line like "(12) Patent
    Application Publication (10) Pub. No.: US 2022/0192066 A1" where two
    fields share a line. Single-line fields are then cut back to their first
    line, and multi-line fields are cut at the first section heading, so a
    field never swallows the block printed after it.

    Later markers do not overwrite earlier ones: the first occurrence of a
    code wins, because a front sheet prints each field once and a repeat is
    more likely to be a stray from the drawing or the classification block.
    """
    fields: dict[str, str] = {}
    matches = list(_INID_MARKER_RE.finditer(text))
    for index, match in enumerate(matches):
        code = match.group(1) + match.group(2)
        if code in fields:
            continue
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        raw = text[match.end() : end]

        label = _INID_LABELS.get(code)
        if label:
            raw = label.sub("", raw.lstrip())

        lines = [line for line in (ln.strip() for ln in raw.splitlines()) if line]
        if not lines:
            continue
        if code in _SINGLE_LINE_INIDS:
            lines = lines[:1]
        else:
            kept: list[str] = []
            for line in lines:
                if _is_boundary(line):
                    break
                kept.append(line)
            lines = kept
        value = _tidy(" ".join(lines))
        if value:
            fields[code] = value
    return fields


def _split_inventors(value: str) -> list[str]:
    """Names out of a front sheet's (72) Inventors block.

    USPTO prints one inventor per entry as "Name, City, ST (US)", entries
    separated by semicolons, so the name is what precedes the first comma.
    That is a heuristic and it has a known failure: an inventor printed
    surname-first, or with no residence, comes back wrong or whole. It is
    used anyway because the alternative -- storing "Amir I. Zaghloul,
    Bethesda, MD (US); ..." as the author -- is wrong for every document
    rather than a few.
    """
    names: list[str] = []
    for entry in value.split(";"):
        name = _tidy(entry.split(",")[0])
        if name:
            names.append(name)
    return names


def parse_front_page_metadata(
    double_column_text: str, single_column_text: str = ""
) -> dict[str, Any]:
    """Read a patent's bibliographic fields off its front sheet.

    Both renderings of page 1 are consulted because neither is reliable
    alone. The two-column crop reads the left block cleanly (title,
    applicant, inventors, application number, filing date) but can cut the
    full-width top band in half; the uncropped rendering keeps that band
    intact but interleaves the two columns line by line. **The two-column
    reading wins per field, and the uncropped one fills the gaps** -- one
    rule, applied field by field, rather than a per-field table of which
    source to trust.

    Every key is always present, `None` where the sheet did not yield it --
    the same total-schema contract the vendored `arxiv_metadata` keeps, and
    for the same reason: "the front page had no assignee" and "nobody
    looked" must not read identically downstream. A scanned document yields
    every field as `None`, which is the honest answer, not a failure.
    """
    primary = _split_inid_fields(double_column_text)
    fallback = _split_inid_fields(single_column_text) if single_column_text else {}

    def field(code: str) -> str | None:
        return primary.get(code) or fallback.get(code) or None

    inventors_raw = field(_INID_INVENTORS)
    return {
        "title": field(_INID_TITLE),
        "inventors": _split_inventors(inventors_raw) if inventors_raw else [],
        "assignee": field(_INID_ASSIGNEE),
        "applicant": field(_INID_APPLICANT),
        "printed_document_number": field(_INID_DOCUMENT_NUMBER),
        "publication_date": field(_INID_PUBLICATION_DATE) or field(_INID_GRANT_DATE),
        "application_number": field(_INID_APPLICATION_NUMBER),
        "filing_date": field(_INID_FILING_DATE),
        "abstract": field(_INID_ABSTRACT),
    }


def build_patent_frontmatter(metadata: dict[str, Any]) -> str:
    """Render `metadata` as a YAML frontmatter block for the converted
    Markdown.

    Written here rather than through the vendored
    `arxiv_doc_builder.arxiv_metadata.build_frontmatter` on purpose: that
    module's schema is arXiv's (arxiv_id, primary_category, journal, DOI),
    and teaching it about assignees and INID codes would mean editing
    vendored code that this repo deliberately keeps unmodified and
    unlinted (commit 2f8f894). The shape it establishes -- one block, every
    key always present, unknown rendered as null -- is kept.
    """
    return "---\n" + yaml.safe_dump(metadata, sort_keys=False, allow_unicode=True) + "---\n\n"


def _run_uv(args: list[str], *, what: str) -> subprocess.CompletedProcess[str]:
    """Run `_patent_convert.py` inside the skill's own environment.

    `uv run --project` rather than an import, matching arxiv.py exactly: the
    PDF stack (pdfplumber / pypdf / pdf2image / pillow) is declared by the
    skill's `pdf` extra and is not in this project's dependency tree, and
    the skill is an independently-versioned package meant to be driven, not
    vendored into an import graph.
    """
    command = [
        "uv",
        "run",
        "--project",
        str(_ARXIV_DOC_BUILDER_DIR),
        "--extra",
        "pdf",
        "--no-dev",
        "python",
        str(_CONVERT_SCRIPT),
        *args,
    ]
    try:
        result = subprocess.run(
            command, capture_output=True, text=True, timeout=_PATENT_CONVERT_TIMEOUT_S
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"{what} timed out after {_PATENT_CONVERT_TIMEOUT_S}s: {exc}") from exc
    if result.returncode != 0:
        raise RuntimeError(
            f"{what} failed (exit {result.returncode}):\n{result.stdout}\n{result.stderr}"
        )
    return result


def _read_manifest(path: Path, *, what: str) -> dict[str, Any]:
    if not path.exists():
        raise RuntimeError(f"{what} reported success but {path} does not exist")
    return json.loads(path.read_text(encoding="utf-8"))


def _run_patent_extract(pdf_path: Path, output_dir: Path) -> dict[str, Any]:
    """Extract the PDF's text layer; returns `_patent_convert.py`'s manifest
    (page_count, text_chars, body_path, and both front-page renderings)."""
    _run_uv(
        ["extract", str(pdf_path), "--output-dir", str(output_dir)],
        what=f"patent text extraction for {pdf_path.name}",
    )
    return _read_manifest(
        output_dir / "manifest.json", what=f"patent text extraction for {pdf_path.name}"
    )


def _run_patent_render(pdf_path: Path, output_dir: Path, dpi: int) -> dict[str, Any]:
    """Render every page and column crop to PNG; returns the render
    manifest (image_dir, image_count, dpi)."""
    _run_uv(
        ["render", str(pdf_path), "--output-dir", str(output_dir), "--dpi", str(dpi)],
        what=f"patent page rendering for {pdf_path.name}",
    )
    return _read_manifest(
        output_dir / "render_manifest.json", what=f"patent page rendering for {pdf_path.name}"
    )


def ingest_patent(
    patent_number: str,
    *,
    license: str,
    classification: str,
    supersedes_document_id: int | None = None,
    download_dir: str | None = None,
    render_page_images: bool = True,
    image_dpi: int = 300,
    fetch_fn: Callable[[str], bytes] = download_bytes,
    extract_fn: Callable[[Path, Path], dict[str, Any]] = _run_patent_extract,
    render_fn: Callable[[Path, Path, int], dict[str, Any]] = _run_patent_render,
) -> dict[str, Any]:
    """Fetch US patent document `patent_number` from the USPTO and ingest it
    as `source_type='patent'`.

    Accepts either kind of number, in any of the usual written forms -- a
    granted patent ("US12089385B2", "12089385") or the pre-grant publication
    of the same application ("US 2022/0192066 A1", "20220192066"). They are
    the same disclosure at two moments in its life and differ enormously in
    machine-readability, so ingesting both is often worth it; call this once
    per number. **This client cannot derive one number from the other** --
    that lookup needs a keyed USPTO/PatentsView API this project has no
    credential for, and patent search is out of scope -- so the caller
    supplies whichever numbers it has.

    `license` and `classification` are passed straight through to
    `ingest_document`, mandatory there (ADR-0001) and so mandatory here. US
    patent documents carry no USPTO copyright claim, but a specific document
    may contain third-party copyrighted material with a notice attached, so
    the caller states the terms rather than this client assuming them.

    Which conversion route ran is reported back, not hidden: the returned
    dict is `ingest_document`'s own result plus a `patent_conversion` entry
    naming the route, the page count, the characters of real text found, and
    where the rendered page images landed. On the scanned route those images
    are the only way to read a drawing sheet, so a caller that never learned
    the directory could not use them. The same facts are stored on the
    document as metadata.

    `fetch_fn`, `extract_fn` and `render_fn` default to the real HTTP GET
    and the two `uv run` subprocess calls, and exist so tests can drive
    every route without a network, a subprocess, or a PDF -- the same seam
    this package's other clients use.
    """
    identifier = normalize_patent_number(patent_number)
    url = patent_pdf_url(identifier)

    work_dir = Path(download_dir) if download_dir else Path(tempfile.mkdtemp(prefix="patent_"))
    work_dir.mkdir(parents=True, exist_ok=True)

    pdf_bytes = fetch_fn(url)
    if not pdf_bytes.startswith(b"%PDF"):
        raise RuntimeError(
            f"{url} did not return a PDF (first bytes: {pdf_bytes[:16]!r}). The USPTO "
            "endpoint answers with an error page rather than a PDF for a number it "
            "does not hold; nothing was ingested."
        )
    pdf_path = work_dir / f"{identifier.display}.pdf"
    pdf_path.write_bytes(pdf_bytes)

    manifest = extract_fn(pdf_path, work_dir)
    page_count = int(manifest.get("page_count", 0))
    text_chars = int(manifest.get("text_chars", 0))
    route = choose_conversion_route(text_chars, page_count)

    front_page = parse_front_page_metadata(
        manifest.get("front_page_double_column", ""),
        manifest.get("front_page_single_column", ""),
    )

    conversion: dict[str, Any] = {
        "route": route,
        "page_count": page_count,
        "text_chars": text_chars,
        "page_images_dir": None,
        "page_image_count": 0,
        "page_image_error": None,
    }

    if route == SCANNED_VISION_ROUTE and render_page_images:
        try:
            render = render_fn(pdf_path, work_dir, image_dpi)
        except (RuntimeError, OSError) as exc:
            # Warn, never block. A missing poppler install costs the figure
            # images; it does not cost the document, which docling still
            # OCRs on its way into the knowledge base.
            conversion["page_image_error"] = str(exc)
        else:
            conversion["page_images_dir"] = render.get("image_dir")
            conversion["page_image_count"] = int(render.get("image_count", 0))

    metadata: dict[str, Any] = {
        "patent_number": identifier.display,
        "uspto_number": identifier.number,
        "kind_code": identifier.kind_code,
        "document_kind": identifier.document_kind,
        "source_url": url,
        "source_type": "patent",
        "conversion_date": datetime.now(UTC).isoformat(),
        **front_page,
        "conversion": conversion,
    }

    if route == TEXT_LAYER_ROUTE:
        body = Path(manifest["body_path"]).read_text(encoding="utf-8")
        ingest_path = work_dir / f"{identifier.display}.md"
        ingest_path.write_text(build_patent_frontmatter(metadata) + body, encoding="utf-8")
    else:
        # No text to convert. docling's OCR gets the original PDF, which is
        # strictly more than an empty Markdown file would carry.
        ingest_path = pdf_path

    extra_metadata = {
        key: value for key, value in metadata.items() if key not in _PROMOTED_FRONTMATTER_KEYS
    }
    inventors = front_page["inventors"]

    result = ingest_document(
        file_path=str(ingest_path),
        source_type="patent",
        license=license,
        classification=classification,
        supersedes_document_id=supersedes_document_id,
        title_override=front_page["title"],
        author=", ".join(inventors) if inventors else None,
        revision=identifier.kind_code,
        extra_metadata=extra_metadata,
    )
    return {**result, "patent_conversion": conversion}
