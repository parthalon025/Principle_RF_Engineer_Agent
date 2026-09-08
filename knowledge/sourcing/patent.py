"""Thin client: US patent/publication -> knowledge base (ticket #219),
reusing arxiv-doc-builder's generic PDF converters via the same subprocess
seam `knowledge/sourcing/arxiv.py` established (commit 0274b42).

Endpoint, verified directly against the live USPTO endpoint during this
ticket's research (not reconstructed from memory):

    GET https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/{number}

returns a grant or a pre-grant publication as `application/pdf`, HTTP 200,
no API key, no registration -- confirmed with a real unauthenticated GET
against both a real grant number ("12089385" -> US12089385B2) and a real
publication number ("20220192066" -> US 2022/0192066 A1). `{number}` must
be BARE DIGITS -- also confirmed directly: "US12089385" and "12089385" both
return 200; "US12089385B2" (kind code attached) returns 400. This module's
`_normalize_patent_number` always strips the "US" prefix and any trailing
kind-code letter+digit suffix (e.g. "B2", "A1") before building the URL, so
callers can pass a number in any of the forms a real citation uses.

Google Patents (`patents.google.com`) was tried and rejected as a source:
it returns HTTP 503 to this network (an anti-bot response to datacenter
IPs, not a real "not found"), confirmed directly during this ticket's
research -- not a viable, reliably-fetchable source.

**Scanned vs. text-layer is a per-document fact, not a per-source-type
one -- this module routes on it, never assumes it from "grant" vs.
"publication".** The common expectation (grants are always scanned images;
pre-grant publications usually carry a real text layer) does NOT hold
universally: fetching the real US12089385B2 grant AND its real pre-grant
publication US 2022/0192066 A1 from the live endpoint above during this
ticket's research, both came back as scanned images with pypdf/pdfplumber
extracting ZERO characters from every page of both. So this module (like
`.claude/skills/arxiv-doc-builder`'s own convert_paper.py LaTeX-vs-PDF
router) detects the document's own actual character -- "does this specific
PDF have a real text layer" -- and branches per-document, not per source
type; a no-text-layer PDF is a NORMAL case handled without error, exactly
as ticket #219 specifies, for a grant AND (as it turns out, sometimes) for
a publication alike.

**Fetch BOTH documents where they exist, by identifier only -- never by
search.** A caller passing only a grant number gets only the grant; a
caller who also already knows the sibling publication number (there is no
confirmed public, unauthenticated API to look one up from the other --
patent SEARCH is explicitly out of scope for every client in this package,
same as 3GPP/ETSI/FCC) passes it as `related_number` and gets both,
ingested as two independent `source_type='patent'` documents. `patent_number`
may itself be either a grant number or a publication number -- both are
"a patent/publication number" per ticket #219's own phrasing -- and
`related_number`, when given, must resolve to the *other* kind; passing two
numbers of the same kind is a caller error (`ValueError`).

**Conversion seam, mirroring arxiv.py's subprocess pattern exactly, but
through a different door.** `arxiv.py` shells out to arxiv-doc-builder's
OWN `convert-paper` CLI (a project script). This module instead shells out
to `knowledge/sourcing/_patent_pdf_convert.py` -- a script that lives in
THIS package, never under `.claude/skills/arxiv-doc-builder/` (excluded
from ruff per commit 2f8f894; never edited) -- run via `uv run --project
.claude/skills/arxiv-doc-builder --extra pdf --no-dev` so it executes
against that vendored project's own installed pdfplumber/pdf2image/pypdf/
pillow stack (its `pdf` optional-dependency group) without adding any of
those four heavy PDF libraries to THIS project's own dependencies. That
script imports only the vendored library's document-agnostic functions --
`pdf_converter_lib.extract_page_content` (two-column extraction with
running-header/footer stripping -- exactly the shape a patent's body pages
need) and `pdf_image_lib.convert_pdf_to_images` (page-to-PNG rendering) --
and NEVER `arxiv_doc_builder.arxiv_metadata` or `pdf_converter_lib.
convert_pdf_to_markdown`, both of which hard-code arXiv-shaped frontmatter
(title/authors/version/DOI/journal/categories). Patent bibliographic
metadata (number, title, assignee, inventors, dates) is parsed HERE, by
`_parse_patent_frontmatter`, from the page-1 text `_patent_pdf_convert.py`
hands back -- keyed on WIPO ST.9 INID field codes ((54) title, (72)
inventors, (73) assignee, ...) every USPTO front page carries regardless of
exact label wording -- never by touching the vendored `arxiv_metadata`
module, which has no patent-shaped fields to offer anyway.

Figure/body pages of a scanned document are rendered to PNG at
`_DEFAULT_DPI` (1200 -- ticket #219: "the original hand-authored work used
1200 dpi for a similar case", see docs/ishape-interior-tuning.md) rather
than transcribed: no OCR or vision call happens anywhere in this repo's
automated ingestion path. The ingested Markdown says this plainly and lists
every rendered image's path, so a human (or a later vision-capable session)
can read them -- this repo's "warn, never block" charter rule, applied to a
gap this module cannot itself close.

Authority rank: untouched. `patent` already has its own
`PATENT_AUTHORITY_RANK` in `knowledge/provenance.py` (ticket #103); this
module passes no `authority_rank_override`, unlike `arxiv.py`'s downgrade
for unreviewed preprints -- a granted/published patent's rank is exactly
what `default_authority_rank(SourceType.PATENT)` already gives it.

Tool-policy category: `ingestion_auto`, alongside `ingest_arxiv_paper`/
`ingest_3gpp_spec`/`ingest_etsi_standard`/`ingest_fcc_rule` -- justified the
same way those four are (see `policies/tool_policy.yaml`'s own comment,
quoted in part here): the USPTO print endpoint above needs no API key, no
account, and no registration of any kind, confirmed directly against the
live endpoint, the same "real, unauthenticated download" posture as
arXiv's API -- not a credentialed third-party call like the three
distributor lookups (`approval_self_gated`), which have their own
independent `ALLOW_EXTERNAL_NETWORK_TOOLS` gate this module has no
equivalent need for.
"""

from __future__ import annotations

import json
import re
import subprocess
import tempfile
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from knowledge.ingest import ingest_document
from knowledge.sourcing._http import download_bytes

# .claude/skills/arxiv-doc-builder from this file's location:
# knowledge/sourcing/patent.py -> knowledge/sourcing -> knowledge -> repo root.
_ARXIV_DOC_BUILDER_DIR = (
    Path(__file__).resolve().parents[2] / ".claude" / "skills" / "arxiv-doc-builder"
)

# Our own conversion driver -- lives beside this module, never under
# _ARXIV_DOC_BUILDER_DIR (see this module's docstring).
_PATENT_PDF_CONVERT_SCRIPT = Path(__file__).resolve().parent / "_patent_pdf_convert.py"

_DOWNLOAD_URL_TEMPLATE = "https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/{digits}"

# Ticket #219: "the original hand-authored work used 1200 dpi for a similar
# case" -- see docs/ishape-interior-tuning.md, which rendered US12089385B2's
# own FIG. 7E at up to 2400 dpi to read a halftone scan numerically. 1200 is
# this module's own default; callers needing more can override via `dpi`.
_DEFAULT_DPI = 1200

# Same generous bound as arxiv.py's _CONVERT_PAPER_TIMEOUT_S -- a cold `uv
# sync` of the pdf extra plus whatever pdfplumber/pdf2image actually takes
# for a real multi-page patent PDF, without hanging indefinitely on a
# runaway conversion.
_CONVERT_TIMEOUT_S = 600

# --- patent/publication number validation -----------------------------
#
# Mirrors arxiv_id.py's style (strict regex, canonicalize, raise ValueError
# with an actionable message) applied to USPTO's two numbering schemes:
#
#   grant:       4-8 digits, e.g. "12089385" (a modern utility grant; US
#                grant numbers crossed 8 digits in June 2018 and have never
#                had more than 8), optionally "US"-prefixed and/or carrying
#                a trailing kind code ("B1"/"B2"/...).
#   publication: a 4-digit year plus a 7-digit sequence, written either
#                slash-separated ("2022/0192066", the human-citation form)
#                or run together ("20220192066", 11 digits total, the form
#                the download endpoint itself accepts), optionally
#                "US"-prefixed and/or carrying a trailing kind code
#                ("A1"/"A2"/...).
#
# Design/plant/reissue-prefixed numbers ("D123456", "PP12345", "RE12345")
# are out of scope (ticket #219's own worked examples are both modern
# utility numbers) and are rejected cleanly: the leading letter fails the
# "digits (and an optional single '/') only" match below.
_NUMBER_RE = re.compile(r"^(?P<digits>[\d/]+)(?P<kind_code>[A-Z]{1,2}\d{0,2})?$")


def normalize_patent_number(raw: str) -> tuple[str, str, str | None]:
    """Validate and canonicalize a grant or publication number.

    Returns ``(digits, kind, kind_code)``: `digits` is the bare numeric
    string the download endpoint accepts (no "US" prefix, no kind code, no
    slash); `kind` is ``"grant"`` or ``"publication"``; `kind_code` is the
    trailing letter+digit suffix as given (e.g. ``"B2"``, ``"A1"``), or
    ``None`` if the caller didn't include one.

    Raises ``ValueError`` for anything that isn't plausibly one of the two
    schemes above -- a sanity check against garbage/malicious input, not a
    guarantee the number exists at USPTO.
    """
    if not raw or not raw.strip():
        raise ValueError(f"not a plausible patent/publication number: {raw!r}")

    cleaned = re.sub(r"\s+", "", raw.strip().upper())
    if cleaned.startswith("US"):
        cleaned = cleaned[2:]

    m = _NUMBER_RE.match(cleaned)
    if not m:
        raise ValueError(
            f"not a plausible patent/publication number: {raw!r}. Expected a "
            "grant number (e.g. \"12089385\" or \"US12089385B2\") or a "
            "publication number (e.g. \"2022/0192066\" or "
            '"US20220192066A1"), optionally "US"-prefixed and/or carrying a '
            "trailing kind code."
        )

    digits_part = m.group("digits")
    kind_code = m.group("kind_code")

    if "/" in digits_part:
        year, seq = digits_part.split("/", 1)
        if len(year) != 4 or len(seq) != 7:
            raise ValueError(
                f"not a plausible publication number: {raw!r}. Expected "
                'YYYY/NNNNNNN (4-digit year, 7-digit sequence, e.g. "2022/0192066").'
            )
        return year + seq, "publication", kind_code

    if len(digits_part) == 11:
        return digits_part, "publication", kind_code
    if 4 <= len(digits_part) <= 8:
        return digits_part, "grant", kind_code

    raise ValueError(
        f"not a plausible patent/publication number: {raw!r}. A bare-digit "
        f"number of length {len(digits_part)} is neither a grant number "
        "(4-8 digits) nor a publication number (11 digits)."
    )


def _download_url(digits: str) -> str:
    return _DOWNLOAD_URL_TEMPLATE.format(digits=digits)


# --- INID-code bibliographic parsing (page 1 text -> patent metadata) --
#
# Keyed on WIPO ST.9 INID codes, which every USPTO grant/publication front
# page carries in parentheses regardless of exact label wording ("Patent
# No." vs "Pat. No.", "Inventors" vs "Inventor") -- a fixed-string search
# would miss label variants; the numeric code does not vary.
_INID_FIELD_PATTERNS: dict[str, re.Pattern[str]] = {
    "title": re.compile(r"\(54\)\s*(.+)"),
    "grant_number": re.compile(r"\(10\)\s*Pat(?:ent)?\.?\s*No\.?:?\s*(.+)", re.IGNORECASE),
    "publication_number": re.compile(
        r"\(10\)\s*Pub(?:lication)?\.?\s*No\.?:?\s*(.+)", re.IGNORECASE
    ),
    "date_of_patent": re.compile(r"\(45\)\s*Date of Patent:?\s*(.+)", re.IGNORECASE),
    "publication_date": re.compile(r"\(43\)\s*Pub(?:lication)?\.?\s*Date:?\s*(.+)", re.IGNORECASE),
    "applicant": re.compile(r"\(71\)\s*Applicant\S*:?\s*(.+)", re.IGNORECASE),
    "inventors": re.compile(r"\(72\)\s*Inventors?:?\s*(.+)", re.IGNORECASE),
    "assignee": re.compile(r"\(73\)\s*Assignee:?\s*(.+)", re.IGNORECASE),
    "appl_no": re.compile(r"\(21\)\s*Appl\.?\s*No\.?:?\s*(.+)", re.IGNORECASE),
    "filed": re.compile(r"\(22\)\s*Filed:?\s*(.+)", re.IGNORECASE),
}


def _parse_patent_frontmatter(front_page_text: str) -> dict[str, str | None]:
    """Best-effort bibliographic-field extraction from a patent/
    publication's page-1 text (see `_INID_FIELD_PATTERNS` for the field
    codes matched).

    Approximate, not authoritative: each field is captured to the end of
    its own text line, so a value that wraps onto a second line (a long
    inventor list, a multi-line assignee address) is truncated at the first
    line break -- fine as a citable provenance hint, not for legal
    reproduction. A field absent from the text (including every field, when
    called with `""` for a scanned PDF with no text layer at all) comes
    back `None` rather than a guess -- "unknown stays unknown", the same
    convention `pdf_converter_lib.extract_metadata` (vendored) already uses
    for a PDF's own embedded title/author.
    """
    result: dict[str, str | None] = dict.fromkeys(_INID_FIELD_PATTERNS)
    for key, pattern in _INID_FIELD_PATTERNS.items():
        found = pattern.search(front_page_text)
        if found:
            value = found.group(1).strip()
            result[key] = value or None
    return result


# --- PDF conversion (subprocess boundary) ------------------------------


def _run_pdf_convert(pdf_path: Path, work_dir: Path, *, dpi: int = _DEFAULT_DPI) -> dict[str, Any]:
    """Run `_patent_pdf_convert.py` against `pdf_path`, against
    arxiv-doc-builder's own installed `pdf`-extra environment (see this
    module's docstring), and return the parsed JSON manifest it writes.

    Raises `RuntimeError` (with the subprocess's own stdout/stderr
    embedded) on any non-zero exit, a missing manifest, or a timeout --
    same shape as `arxiv.py._run_convert_paper`.
    """
    manifest_path = work_dir / "manifest.json"
    try:
        result = subprocess.run(
            [
                "uv",
                "run",
                "--project",
                str(_ARXIV_DOC_BUILDER_DIR),
                "--extra",
                "pdf",
                "--no-dev",
                str(_PATENT_PDF_CONVERT_SCRIPT),
                str(pdf_path),
                "--output-dir",
                str(work_dir),
                "--dpi",
                str(dpi),
                "--manifest",
                str(manifest_path),
            ],
            capture_output=True,
            text=True,
            timeout=_CONVERT_TIMEOUT_S,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(
            f"patent PDF conversion timed out after {_CONVERT_TIMEOUT_S}s for {pdf_path}: {exc}"
        ) from exc
    if result.returncode != 0:
        raise RuntimeError(
            f"patent PDF conversion failed for {pdf_path} (exit {result.returncode}):\n"
            f"{result.stdout}\n{result.stderr}"
        )
    if not manifest_path.exists():
        raise RuntimeError(
            f"patent PDF conversion reported success for {pdf_path} but "
            f"{manifest_path} does not exist"
        )
    return json.loads(manifest_path.read_text(encoding="utf-8"))


# --- Markdown + frontmatter assembly -----------------------------------

_PROMOTED_FIELDS = frozenset({"title", "inventors"})


def _build_patent_markdown(
    manifest: dict[str, Any],
    *,
    digits: str,
    kind: str,
    kind_code: str | None,
    parsed: dict[str, str | None],
    work_dir: Path,
) -> Path:
    """Write the final Markdown file `ingest_document` will parse: our own
    patent-shaped YAML frontmatter (never arxiv_doc_builder.arxiv_metadata's
    arXiv-shaped one -- see this module's docstring) followed by either the
    real extracted body text (`manifest["route"] == "text"`) or an honest
    "no text layer, here is where the rendered pages are" note plus every
    image path (`manifest["route"] == "vision"`).
    """
    number_key = "grant_number" if kind == "grant" else "publication_number"
    date = parsed.get("date_of_patent") or parsed.get("publication_date")
    frontmatter_data = {
        number_key: digits,
        "kind": kind,
        "kind_code": kind_code,
        "title": parsed.get("title"),
        "applicant": parsed.get("applicant"),
        "inventors": parsed.get("inventors"),
        "assignee": parsed.get("assignee"),
        "appl_no": parsed.get("appl_no"),
        "filed": parsed.get("filed"),
        "date": date,
        "conversion_route": manifest["route"],
        "conversion_date": datetime.now(UTC).isoformat(),
    }
    frontmatter_yaml = yaml.safe_dump(frontmatter_data, sort_keys=False).strip()

    parts = ["---", frontmatter_yaml, "---", ""]
    if manifest["route"] == "text":
        body_path = Path(manifest["markdown_path"])
        parts.append(body_path.read_text(encoding="utf-8"))
    else:
        dpi = manifest.get("dpi")
        page_count = manifest.get("page_count")
        parts.append(
            "## Scanned document -- no text layer\n\n"
            f"This {kind} PDF ({page_count} pages) has no extractable text layer "
            "(the USPTO print endpoint returned a scanned image, not a native PDF) "
            "-- a normal case for a USPTO grant or publication PDF, not an error. "
            f"Every page was rendered to PNG at {dpi} DPI for manual or "
            "vision-based transcription; no OCR or automated transcription has "
            "been run:\n"
        )
        parts.extend(f"- {image_path}" for image_path in manifest.get("image_paths", []))

    md_path = work_dir / f"{digits}.md"
    md_path.write_text("\n".join(parts), encoding="utf-8")
    return md_path


# --- ingest_patent -------------------------------------------------------


def _ingest_one(
    digits: str,
    kind: str,
    kind_code: str | None,
    *,
    license: str,
    classification: str,
    supersedes_document_id: int | None,
    download_dir: str | None,
    dpi: int,
    fetch_fn: Callable[[str], bytes],
    convert_fn: Callable[..., dict[str, Any]],
) -> dict[str, Any]:
    url = _download_url(digits)
    pdf_bytes = fetch_fn(url)

    work_dir = (
        Path(download_dir) if download_dir else Path(tempfile.mkdtemp(prefix=f"patent_{kind}_"))
    )
    work_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = work_dir / f"{digits}.pdf"
    pdf_path.write_bytes(pdf_bytes)

    manifest = convert_fn(pdf_path, work_dir, dpi=dpi)
    parsed = _parse_patent_frontmatter(manifest.get("front_page_text", "") or "")
    md_path = _build_patent_markdown(
        manifest, digits=digits, kind=kind, kind_code=kind_code, parsed=parsed, work_dir=work_dir
    )

    extra_metadata = {
        "identifier": digits,
        "kind": kind,
        "kind_code": kind_code,
        "conversion_route": manifest["route"],
        **{key: value for key, value in parsed.items() if key not in _PROMOTED_FIELDS},
    }

    return ingest_document(
        file_path=str(md_path),
        source_type="patent",
        license=license,
        classification=classification,
        supersedes_document_id=supersedes_document_id,
        title_override=parsed.get("title"),
        author=parsed.get("inventors"),
        revision=kind_code,
        extra_metadata=extra_metadata,
    )


def ingest_patent(
    patent_number: str,
    *,
    license: str,
    classification: str,
    related_number: str | None = None,
    supersedes_document_id: int | None = None,
    download_dir: str | None = None,
    dpi: int = _DEFAULT_DPI,
    fetch_fn: Callable[[str], bytes] = download_bytes,
    convert_fn: Callable[..., dict[str, Any]] = _run_pdf_convert,
) -> dict[str, Any]:
    """Fetch a US patent grant and/or pre-grant publication by number and
    ingest each as `source_type='patent'`.

    `patent_number` may be either a grant number (e.g. "12089385" or
    "US12089385B2") or a publication number (e.g. "2022/0192066" or
    "US20220192066A1") -- both are "a patent/publication number" per ticket
    #219's own framing, and which one this is gets auto-detected (see
    `normalize_patent_number`). Pass `related_number` when you already know
    the SIBLING identifier of the opposite kind (there is no
    search/lookup here -- see this module's docstring for why) to fetch and
    ingest both the grant and the publication in one call; passing two
    numbers of the same kind raises `ValueError`.

    `license` and `classification` are passed straight through to
    `ingest_document` -- mandatory there (ADR-0001), so mandatory here too.
    A granted US patent's specification text is conventionally treated as
    freely reproducible, but this module does not assume that for you:
    supply the license string that actually applies.

    `supersedes_document_id`, if given, applies only to the document
    resolved from `patent_number` (the primary identifier) -- a grant and
    its own pre-grant publication are two independent documents, and this
    parameter cannot express "supersede two different documents at once"
    without ambiguity, so it deliberately targets only the one the caller
    named as primary. Pass `ingest_patent` again with the other identifier
    as `patent_number` if the sibling document also needs to supersede
    something.

    `dpi` controls the page-image render resolution used only for a
    document that turns out to have no text layer (default 1200 -- see
    `_DEFAULT_DPI`). `fetch_fn`/`convert_fn` default to the real HTTP GET
    and the real `uv run` subprocess call respectively, and exist so tests
    can inject stubs instead of hitting the network or a subprocess.

    Returns `{"grant": <ingest_document result> | None, "publication":
    <ingest_document result> | None}` -- whichever of the two was actually
    fetched.
    """
    digits1, kind1, kind_code1 = normalize_patent_number(patent_number)

    # Validate related_number BEFORE fetching/ingesting anything, so a
    # caller error (two numbers of the same kind) fails cleanly with no
    # partial side effect (one document already fetched and ingested,
    # the other rejected).
    digits2 = kind2 = kind_code2 = None
    if related_number is not None:
        digits2, kind2, kind_code2 = normalize_patent_number(related_number)
        if kind2 == kind1:
            raise ValueError(
                f"related_number {related_number!r} is also a {kind2} number; "
                f"expected the sibling kind of patent_number {patent_number!r} "
                f"({kind1}), e.g. a publication number alongside a grant number."
            )

    results: dict[str, Any] = {"grant": None, "publication": None}
    primary_download_dir = (
        str(Path(download_dir) / kind1) if download_dir is not None else None
    )
    results[kind1] = _ingest_one(
        digits1,
        kind1,
        kind_code1,
        license=license,
        classification=classification,
        supersedes_document_id=supersedes_document_id,
        download_dir=primary_download_dir,
        dpi=dpi,
        fetch_fn=fetch_fn,
        convert_fn=convert_fn,
    )

    if related_number is not None:
        related_download_dir = (
            str(Path(download_dir) / kind2) if download_dir is not None else None
        )
        results[kind2] = _ingest_one(
            digits2,
            kind2,
            kind_code2,
            license=license,
            classification=classification,
            supersedes_document_id=None,
            download_dir=related_download_dir,
            dpi=dpi,
            fetch_fn=fetch_fn,
            convert_fn=convert_fn,
        )

    return results
