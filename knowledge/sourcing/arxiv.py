"""Thin client: arXiv preprint -> knowledge base (ticket #68), converted
via the arxiv-doc-builder skill (.claude/skills/arxiv-doc-builder).

Primary source verified directly against arXiv's own documentation, not
reconstructed from memory:
- No-auth confirmation: arXiv API User Manual,
  https://info.arxiv.org/help/api/user-manual.html -- "No API key or
  authentication is required" to use the query API.
- Good-citizen etiquette (no hard rate limit, but a descriptive
  User-Agent and restraint on request rate is expected): arXiv API Terms
  of Use, https://info.arxiv.org/help/api/tou.html.

IEEE Xplore -- the paywalled peer-reviewed-literature source arXiv
preprints most often substitute for (arXiv content is typically posted
before or instead of a peer-reviewed venue) in this repo's evidence
hierarchy -- is confirmed genuinely paywalled with no broad free-developer
tier (IEEE's own subscriptions page,
https://www.ieee.org/publications/subscriptions/index.html, quotes
institutional package pricing in the tens of thousands of dollars/year;
see also this package's own `__init__.py` docstring and
docs/FREE_AND_OPEN_SOURCE_TOOLING.md's IEEE Xplore row). No IEEE Xplore
ingestion path is built here or anywhere in this repo.

Authority rank: an arXiv preprint is not peer-reviewed -- arXiv's own
description of its moderation process calls it a "superficial" check, not
peer review (https://info.arxiv.org/help/moderation/index.html) -- so this
module always overrides `documents.authority_rank` downward via
`knowledge.provenance.arxiv_preprint_authority_rank()` rather than letting
an arXiv-sourced document silently inherit `source_type='paper'`'s
peer-reviewed default rank.

Conversion path: fetching the raw PDF and handing it straight to docling
(this module's original ticket #68 shape) loses arXiv's own LaTeX source --
docling never sees the math environments and section structure a two-column
PDF's text layer garbles, and no author/date/DOI/category metadata was ever
captured beyond docling's own best-effort title guess. `.claude/skills/
arxiv-doc-builder` already solves exactly this: its `convert-paper` CLI
fetches LaTeX source (preferred) + PDF, converts via pandoc when source is
available (preserving math/structure per knowledge/README.md's "never strip
units" mandate), falls back to naive PDF extraction otherwise, and always
emits a Markdown file with a YAML frontmatter block carrying title/authors/
version/published/categories/DOI/journal/abstract (arxiv_doc_builder/
arxiv_metadata.py's `build_frontmatter` -- a total schema, present
regardless of which conversion path ran or whether the arXiv API fetch
itself succeeded). `_run_convert_paper` shells out to that CLI via `uv run
--project` rather than importing arxiv_doc_builder as a library: it is a
separate, independently-versioned package (own pyproject.toml/uv.lock)
designed as a standalone tool, and invoking it as a subprocess keeps this
module a genuinely thin client -- no ingestion, fetch, or LaTeX/PDF
conversion logic is duplicated here, matching this file's original
"no new ingestion logic lives here" design and this repo's existing pattern
for every other external tool (pandoc, curl, tar -- like NEC2++, LTspice,
KiCad) it shells out to elsewhere.

Not gated behind ALLOW_EXTERNAL_NETWORK_TOOLS: that gate (knowledge/
sourcing_common.py) exists specifically for the three CREDENTIALED
distributor APIs (Digi-Key/Mouser/Nexar) that place a real, credentialed
call to a third party the instant they run. arXiv, like this package's
3GPP/ETSI/FCC siblings, needs no account or credential
(info.arxiv.org/help/api/user-manual.html, quoted above) -- same
ungated posture as those.

Discovery search (issue #257): `search_arxiv_papers` below is a second,
separate entry point alongside `ingest_arxiv_paper` -- "find candidates
about a topic" rather than "fetch document #Y". It hits the same
credential-free query API named above, but with its `search_query`
parameter (a keyword/topic search over titles, abstracts, authors and
categories) instead of `id_list` (fetch by known identifier, what
`ingest_arxiv_paper` uses, indirectly, via arxiv-doc-builder). It returns
a ranked list of *candidate* dicts (id/title/published/abstract) for a
caller to review -- it never writes to the database and never calls
`ingest_document`, directly or indirectly. Bringing a candidate in as
evidence is a separate, deliberate call to `ingest_arxiv_paper`, with its
own required `license`/`classification` per ADR-0001; search finding a
paper is not the same as this program trusting it.
"""

from __future__ import annotations

import re
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from collections.abc import Callable
from pathlib import Path
from typing import Any
from urllib.parse import urlencode, urlparse

import yaml

from knowledge.ingest import ingest_document
from knowledge.provenance import arxiv_preprint_authority_rank
from knowledge.sourcing._http import download_bytes

# arXiv ids are either the modern "YYMM.NNNNN" form or the pre-2007
# "archive/YYMMNNN" form (e.g. "cond-mat/0207270") -- both documented in
# the arXiv API User Manual's id_list examples. Deliberately permissive
# (word chars, dots, dashes, one optional slash) rather than a strict
# format lock, since arXiv itself has extended the numeric width over
# time; this is a sanity check against garbage input, not a validator of
# arXiv's own id grammar -- convert-paper (arxiv_doc_builder/arxiv_id.py)
# does its own strict validation on top of this and fails clearly if this
# permissive check let something through it doesn't accept.
_ARXIV_ID_RE = re.compile(r"^[\w][\w.\-]*(?:/[\w.\-]+)?$")

# .claude/skills/arxiv-doc-builder from this file's location:
# knowledge/sourcing/arxiv.py -> knowledge/sourcing -> knowledge -> repo root.
_ARXIV_DOC_BUILDER_DIR = (
    Path(__file__).resolve().parents[2] / ".claude" / "skills" / "arxiv-doc-builder"
)

# Frontmatter keys that get promoted to their own ingest_document parameter
# rather than riding along in extra_metadata -- see _split_frontmatter.
_PROMOTED_FRONTMATTER_KEYS = frozenset({"title", "authors", "version"})


def _parse_frontmatter(md_text: str) -> dict[str, Any]:
    """Extract the YAML frontmatter block arxiv-doc-builder's
    `arxiv_metadata.build_frontmatter` prepends to every converted paper,
    regardless of which conversion path (LaTeX or PDF fallback) produced it
    or whether the arXiv API fetch itself succeeded (it's a total schema --
    an unknown field renders as YAML null, not an absent key).

    Returns {} if the file carries no `---`-delimited frontmatter block at
    all (e.g. a hand-authored Markdown file with no arxiv-doc-builder
    provenance), so callers can treat "no frontmatter" the same as "fetch
    failed and every field came back null" -- both mean no usable override.
    """
    lines = md_text.splitlines()
    if not lines or lines[0] != "---":
        return {}
    for i in range(1, len(lines)):
        if lines[i] == "---":
            block = "\n".join(lines[1:i])
            parsed = yaml.safe_load(block)
            return parsed if isinstance(parsed, dict) else {}
    return {}


# Same default as simulation/nec2pp.py's run_nec2_simulation(timeout_s=600) --
# generous enough to cover a cold `uv sync` (first-run venv build), the arXiv
# network fetch, and convert_latex.py's own internal 180s pandoc bound
# (PANDOC_TIMEOUT_SECONDS) with room to spare, without hanging the calling
# process indefinitely on a stalled fetch or a pandoc runaway that somehow
# outlives its own internal watchdog.
_CONVERT_PAPER_TIMEOUT_S = 600


def _run_convert_paper(arxiv_id: str, output_dir: Path) -> Path:
    """Fetch and convert `arxiv_id` via arxiv-doc-builder's `convert-paper`
    CLI, run through `uv run --project` against that package's own isolated
    environment (it declares no dependencies of its own for the LaTeX happy
    path, so this needs no network beyond what convert-paper itself does).
    Returns the path to the produced `{arxiv_id}/{arxiv_id}.md` file.

    Raises RuntimeError, with convert-paper's own stdout/stderr embedded,
    on any non-zero exit -- including exit code 2 ("ambiguous main .tex
    file", see SKILL.md's "Troubleshooting: Multiple \\documentclass
    Files"), whose message already names the candidate files and how to
    re-run with `--tex-file` against the same (idempotently cached)
    `output_dir`. No special-casing here: the message is actionable as-is.

    Also raises RuntimeError (wrapping subprocess.TimeoutExpired) if the
    whole call exceeds `_CONVERT_PAPER_TIMEOUT_S` -- matching every other
    subprocess boundary in this repo (e.g. simulation/nec2pp.py), none of
    which run a subprocess uncapped.
    """
    try:
        result = subprocess.run(
            [
                "uv",
                "run",
                "--project",
                str(_ARXIV_DOC_BUILDER_DIR),
                "--no-dev",  # skip ruff/pyright/the pdf test-extra -- convert-paper's
                # own PDF fallback resolves pdfplumber/pdf2image/pypdf/pillow itself,
                # independently, via a nested `uv run --no-project` on convert_pdf_
                # simple.py's own PEP 723 inline deps (see pyproject.toml's comment
                # in .claude/skills/arxiv-doc-builder), so none of this project's
                # env is needed for a real conversion run, only for local dev/test.
                "convert-paper",
                arxiv_id,
                "--output-dir",
                str(output_dir),
            ],
            capture_output=True,
            text=True,
            timeout=_CONVERT_PAPER_TIMEOUT_S,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(
            f"convert-paper timed out after {_CONVERT_PAPER_TIMEOUT_S}s for arXiv:{arxiv_id}: {exc}"
        ) from exc
    if result.returncode != 0:
        raise RuntimeError(
            f"convert-paper failed for arXiv:{arxiv_id} (exit {result.returncode}):\n"
            f"{result.stdout}\n{result.stderr}"
        )

    safe_id = arxiv_id.replace("/", "_")
    md_path = output_dir / safe_id / f"{safe_id}.md"
    if not md_path.exists():
        raise RuntimeError(
            f"convert-paper reported success for arXiv:{arxiv_id} but {md_path} does not exist"
        )
    return md_path


def ingest_arxiv_paper(
    arxiv_id: str,
    *,
    license: str,
    classification: str,
    supersedes_document_id: int | None = None,
    download_dir: str | None = None,
    convert_fn: Callable[[str, Path], Path] = _run_convert_paper,
) -> dict[str, Any]:
    """Fetch and convert arXiv preprint `arxiv_id` (e.g. "2401.01234", or the
    older "cond-mat/0207270" form) via arxiv-doc-builder, and ingest the
    result as `source_type='paper'`, with its authority rank automatically
    overridden below the peer-reviewed default -- see this module's
    docstring.

    `license` and `classification` are passed straight through to
    `ingest_document` -- mandatory there (ADR-0001), so mandatory here too.
    arXiv's own reuse terms vary per paper (arXiv's default license lets
    arXiv distribute the work but does not itself grant downstream reuse
    beyond citation/summary use; some authors separately opt into CC0/
    CC-BY -- see https://info.arxiv.org/help/license/index.html), so the
    caller must supply the license string that actually applies to this
    specific paper, not a guessed default.

    `convert_fn` defaults to the real `_run_convert_paper` (a `uv run
    --project` subprocess call) and exists so tests can inject a stub
    instead of shelling out. The produced Markdown's YAML frontmatter
    supplies `ingest_document`'s `title_override`/`author`/`revision`
    directly from arXiv's own record rather than docling's guess; every
    other frontmatter field (arxiv_id, published, primary_category,
    categories, doi, journal, abstract, ...) rides along as
    `extra_metadata` unchanged, so a future frontmatter field is captured
    automatically without this module needing to name it. A file with no
    frontmatter (or one arXiv couldn't populate) degrades gracefully: no
    override, no extra metadata, docling's own parse decides the title.
    """
    if not arxiv_id or not _ARXIV_ID_RE.match(arxiv_id):
        raise ValueError(f"not a plausible arXiv id: {arxiv_id!r}")

    work_dir = Path(download_dir) if download_dir else Path(tempfile.mkdtemp(prefix="arxiv_"))
    work_dir.mkdir(parents=True, exist_ok=True)

    md_path = convert_fn(arxiv_id, work_dir)
    frontmatter = _parse_frontmatter(md_path.read_text(encoding="utf-8"))
    extra_metadata = {
        key: value for key, value in frontmatter.items() if key not in _PROMOTED_FRONTMATTER_KEYS
    }

    return ingest_document(
        file_path=str(md_path),
        source_type="paper",
        license=license,
        classification=classification,
        supersedes_document_id=supersedes_document_id,
        authority_rank_override=arxiv_preprint_authority_rank(),
        title_override=frontmatter.get("title"),
        author=frontmatter.get("authors"),
        revision=frontmatter.get("version"),
        extra_metadata=extra_metadata,
    )


# --- search_arxiv_papers: topic/keyword discovery search (issue #257) -----
#
# Everything below is a second, separate entry point from ingest_arxiv_paper
# above: it queries the same credential-free arXiv query API, but with the
# `search_query` parameter (topic/keyword search) instead of `id_list`
# (fetch by known identifier). It returns candidate dicts for review, never
# writes to the database, and never calls ingest_document -- see this
# module's docstring ("Discovery search (issue #257)") for the full
# rationale.

# arXiv's query API base -- the same no-auth endpoint this module's
# docstring already cites (arXiv API User Manual), used here with
# `search_query` rather than `id_list`. https (not http) matches arXiv's
# own current documentation and arxiv_doc_builder/arxiv_metadata.py's
# `_API_URL`.
_ARXIV_QUERY_API_URL = "https://export.arxiv.org/api/query"

# Only the plain Atom namespace is needed to pull id/title/published/summary
# out of a search response -- the arxiv: extension namespace (primary
# category, DOI, journal ref) that arxiv_doc_builder/arxiv_metadata.py's
# fetch_metadata also reads is not part of the minimal candidate shape this
# function returns (id/title/published/abstract -- see search_arxiv_papers'
# docstring).
_ATOM_NS = {"atom": "http://www.w3.org/2005/Atom"}


def _search_query_url(query: str, max_results: int) -> str:
    """Build the `search_query`-form query API URL: `query` verbatim (a
    caller may pass a bare keyword string or arXiv's own field-prefixed
    syntax, e.g. "all:metamaterial AND cat:physics.app-ph" -- this function
    does not interpret or validate it, only URL-encodes it), `start=0`
    (always the first page -- this function does not paginate), and
    `max_results` capping how many candidates come back."""
    params = {"search_query": query, "start": 0, "max_results": max_results}
    return f"{_ARXIV_QUERY_API_URL}?{urlencode(params)}"


def _entry_text(entry: ET.Element, path: str) -> str | None:
    """Return the text of `entry`'s first child matching `path` (an
    `atom:`-prefixed tag name), or None if absent."""
    el = entry.find(path, _ATOM_NS)
    return el.text if el is not None else None


def _clean_text(text: str | None) -> str | None:
    """Collapse the indentation/newlines arXiv's pretty-printed Atom XML
    puts inside <title>/<summary> text nodes down to single-line,
    single-spaced text. Mirrors the whitespace-collapsing half of
    arxiv_doc_builder/arxiv_metadata.py's `_normalize` (reimplemented
    minimally here rather than imported -- see this module's docstring on
    why arxiv_doc_builder, a separate independently-versioned package, is
    only ever shelled out to, never imported as a library). Returns None
    for None or whitespace-only input."""
    if text is None:
        return None
    collapsed = re.sub(r"\s+", " ", text).strip()
    return collapsed or None


def _candidate_id_from_entry(entry: ET.Element) -> str | None:
    """Extract the versioned arXiv id (e.g. "2401.01234v2", or the legacy
    "cond-mat/0207270v1") from an Atom <entry>'s <id> URL
    (e.g. "http://arxiv.org/abs/2401.01234v2") -- the same tail
    arxiv_doc_builder/arxiv_metadata.py's `parse_version_from_id` pulls out
    of the by-id form of this same feed. This is exactly the id form
    `_ARXIV_ID_RE` accepts and `ingest_arxiv_paper` expects, so a candidate
    from this function can be handed straight to `ingest_arxiv_paper`
    unchanged."""
    id_url = _entry_text(entry, "atom:id")
    if not id_url:
        return None
    path = urlparse(id_url).path
    if path.startswith("/abs/"):
        return path[len("/abs/") :] or None
    return id_url.rsplit("/", 1)[-1] or None


def _parse_search_candidates(atom_bytes: bytes) -> list[dict[str, Any]]:
    """Parse a `search_query` Atom response into an ordered list of
    candidate dicts, one per <entry>, in the order arXiv's own relevance
    ranking returned them (feed order is preserved, nothing here re-sorts).
    A response with no <entry> elements -- a real "no matches" search, not
    a fetch failure -- parses cleanly to []."""
    root = ET.fromstring(atom_bytes)
    candidates: list[dict[str, Any]] = []
    for entry in root.findall("atom:entry", _ATOM_NS):
        candidates.append(
            {
                "id": _candidate_id_from_entry(entry),
                "title": _clean_text(_entry_text(entry, "atom:title")),
                # arXiv's <published> is a full ISO timestamp; a candidate
                # only needs the paper's calendar date.
                "published": (_entry_text(entry, "atom:published") or "")[:10] or None,
                "abstract": _clean_text(_entry_text(entry, "atom:summary")),
            }
        )
    return candidates


def search_arxiv_papers(
    query: str,
    *,
    max_results: int = 10,
    fetch_fn: Callable[[str], bytes] = download_bytes,
) -> list[dict[str, Any]]:
    """Search arXiv by topic/keyword and return a ranked list of
    **candidates for review** -- not documents in the corpus, and nothing
    this function does writes to the database or calls `ingest_document`
    (directly or indirectly), under any input. Finding a paper and
    trusting it as evidence are two separate, deliberate steps: hand a
    chosen candidate's `id` straight to `ingest_arxiv_paper` (unchanged --
    same id form, see `_candidate_id_from_entry`) along with the
    `license`/`classification` ADR-0001 requires for that specific paper.

    `query` is arXiv's `search_query` parameter -- a keyword/topic search
    over titles, abstracts, authors and categories (as opposed to
    `ingest_arxiv_paper`'s `id_list`-style fetch by already-known
    identifier). Accepts a bare keyword string or arXiv's own
    field-prefixed syntax (e.g. "all:conformal metamaterial absorber" or
    "abs:magnetic mirror AND cat:physics.app-ph"); this function passes it
    through verbatim (URL-encoded), it does not interpret or validate it --
    see the arXiv API User Manual (cited in this module's docstring) for
    the full query grammar.

    Each candidate dict carries `id` (the same versioned arXiv id form
    `ingest_arxiv_paper` accepts, e.g. "2401.01234v2"), `title`,
    `published` (the paper's date, "YYYY-MM-DD"), and `abstract` -- enough
    to judge relevance before spending an ingestion pass on it. Results
    come back in the order arXiv's own relevance ranking returned them.

    A topic with no matches returns `[]` -- a real "nobody has published
    this" result, not an error. A `fetch_fn` failure (the API unreachable,
    a network error) is deliberately *not* caught here and propagates as
    a raised exception instead, so "nobody has published this" and "the
    search itself failed" can never be confused with each other (user
    stories 8-9, issue #257).

    `max_results` caps how many candidates come back in one call (arXiv's
    own `max_results` query parameter, default 10) -- small enough that a
    caller, human or model, can actually triage the list rather than
    getting back an unbounded page to sort through by hand.

    `fetch_fn` defaults to a real HTTP GET (`knowledge.sourcing._http.
    download_bytes`) against the same credential-free query API this
    module's docstring already confirms needs no authentication, and
    exists so tests can inject a stub instead of hitting the network --
    the same seam every other sourcing client in this package uses.
    """
    atom_bytes = fetch_fn(_search_query_url(query, max_results))
    return _parse_search_candidates(atom_bytes)
