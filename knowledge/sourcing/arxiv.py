"""Thin client: arXiv preprint -> knowledge base (ticket #68).

Primary source verified directly against arXiv's own documentation, not
reconstructed from memory:
- No-auth confirmation: arXiv API User Manual,
  https://info.arxiv.org/help/api/user-manual.html -- "No API key or
  authentication is required" to use the query API.
- PDF download URL shape: the same manual documents each Atom query-API
  entry carrying a `<link title="pdf">` element pointing at
  `http://arxiv.org/pdf/{arxiv_id}` -- confirmed as the stable public PDF
  URL for a given id, which this client builds directly rather than
  round-tripping through the query API just to read that link back out.
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

Thin client per this repo's knowledge-sourcing seam: download the paper's
PDF by its known, stable `arxiv.org/pdf/{id}` URL, hand the local file to
`knowledge.ingest.ingest_document` unchanged (`source_type='paper'`, with
the authority-rank override above). No new ingestion logic lives here --
`ingest_document` still does all of the actual parsing/chunking/storage,
and derives its own title from the downloaded PDF rather than this module
querying arXiv's metadata API for one.
"""

from __future__ import annotations

import re
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

from knowledge.ingest import ingest_document
from knowledge.provenance import arxiv_preprint_authority_rank
from knowledge.sourcing._http import download_bytes

# arXiv ids are either the modern "YYMM.NNNNN" form or the pre-2007
# "archive/YYMMNNN" form (e.g. "cond-mat/0207270") -- both documented in
# the arXiv API User Manual's id_list examples. Deliberately permissive
# (word chars, dots, dashes, one optional slash) rather than a strict
# format lock, since arXiv itself has extended the numeric width over
# time; this is a sanity check against garbage input, not a validator of
# arXiv's own id grammar.
_ARXIV_ID_RE = re.compile(r"^[\w][\w.\-]*(?:/[\w.\-]+)?$")


def _pdf_url(arxiv_id: str) -> str:
    return f"https://arxiv.org/pdf/{arxiv_id}"


def ingest_arxiv_paper(
    arxiv_id: str,
    *,
    license: str,
    classification: str,
    supersedes_document_id: int | None = None,
    download_dir: str | None = None,
    fetch_fn: Callable[[str], bytes] = download_bytes,
) -> dict[str, Any]:
    """Download arXiv preprint `arxiv_id` (e.g. "2401.01234", or the older
    "cond-mat/0207270" form) and ingest it as `source_type='paper'`, with
    its authority rank automatically overridden below the peer-reviewed
    default -- see this module's docstring.

    `license` and `classification` are passed straight through to
    `ingest_document` -- mandatory there (ADR-0001), so mandatory here too.
    arXiv's own reuse terms vary per paper (arXiv's default license lets
    arXiv distribute the work but does not itself grant downstream reuse
    beyond citation/summary use; some authors separately opt into CC0/
    CC-BY -- see https://info.arxiv.org/help/license/index.html), so the
    caller must supply the license string that actually applies to this
    specific paper, not a guessed default.

    `fetch_fn` defaults to a real HTTP GET (`knowledge.sourcing._http.
    download_bytes`) and exists so tests can inject a stub instead of
    hitting the network.
    """
    if not arxiv_id or not _ARXIV_ID_RE.match(arxiv_id):
        raise ValueError(f"not a plausible arXiv id: {arxiv_id!r}")

    pdf_bytes = fetch_fn(_pdf_url(arxiv_id))

    work_dir = Path(download_dir) if download_dir else Path(tempfile.mkdtemp(prefix="arxiv_"))
    work_dir.mkdir(parents=True, exist_ok=True)
    safe_name = arxiv_id.replace("/", "_")
    pdf_path = work_dir / f"{safe_name}.pdf"
    pdf_path.write_bytes(pdf_bytes)

    return ingest_document(
        file_path=str(pdf_path),
        source_type="paper",
        license=license,
        classification=classification,
        supersedes_document_id=supersedes_document_id,
        authority_rank_override=arxiv_preprint_authority_rank(),
    )
