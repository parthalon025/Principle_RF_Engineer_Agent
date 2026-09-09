"""Thin client: ETSI standard -> knowledge base (ticket #68), plus the ETSI
IPR/FRAND-declaration register -> knowledge base (issue #284).

ETSI publishes every deliverable as a directly downloadable PDF with no
registration (only the editable Word version is access-restricted) --
confirmed from ETSI's own "Download ETSI ICT Standards for free" page,
https://www.etsi.org/standards/get-standards, and cross-checked against
several live `www.etsi.org/deliver/...` PDF URLs, e.g.
https://www.etsi.org/deliver/etsi_ts/119600_119699/119612/02.02.01_60/
ts_119612v020201p.pdf.

The deliver path (document-type folder, a grouped numeric-range folder,
the document-number folder, a version folder, then the filename) is
per-document and not mechanically derivable from a bare standard number
alone -- no confirmed public JSON search API was found during this
ticket's research to script that lookup against (ETSI's own standards
search UI, https://www.etsi.org/standards-search, is the human-facing
front end for it). This client therefore does not attempt to *discover* a
document's deliver URL from a bare document number; it takes the deliver
URL directly, obtained however the caller already found it.

ETSI standards are free to download but carry ETSI's own copyright and
(F)RAND patent terms, same internal-use posture as 3GPP (see
docs/FREE_AND_OPEN_SOURCE_TOOLING.md's ETSI row). Pass the license string
that reflects that -- this client does not assume a specific one.

Thin client per this repo's knowledge-sourcing seam: download the PDF at
the given deliver URL, hand it to `knowledge.ingest.ingest_document`
unchanged (`source_type='standard'`). No new ingestion logic lives here.

---

`ingest_etsi_ipr_declaration()` (issue #284) applies the exact same
resolution to a second, separate ETSI register: SR 000 314, the public
IPR/patent-declaration register listing (F)RAND licensing undertakings
member companies file against a standard. Plain language: a company that
holds a patent it believes is essential to building to a given standard
declares that patent here and promises (F)RAND terms -- "fair, reasonable,
and non-discriminatory" licensing, not free -- so a design that leans on a
standard with a declaration on file may still cost something to license
before it can actually be built. Surfacing that is CLAUDE.md's "warn,
never block" discipline applied to standards the same way it already
applies to element/material claims.

This register is served from a *different* host than the deliver-path
PDFs above -- `ipr.etsi.org`, a dedicated subdomain whose entire purpose is
this database (unlike `www.etsi.org`, which is ETSI's general site and
needs the extra `/deliver/` path check to narrow in on just the PDF
archive). Confirmed live during this ticket's research: an individual
declaration's page is `https://ipr.etsi.org/IPRDetails.aspx?IPRD_ID=<n>&
IPRD_TYPE_ID=<n>&MODE=<n>` -- e.g. Google's own crawler has indexed
https://ipr.etsi.org/IPRDetails.aspx?IPRD_ID=198&IPRD_TYPE_ID=2&MODE=2 with
no `sessionkey` parameter at all. That is decisive evidence, not a guess:
Googlebot holds no ETSI session, so a page it can render, cache, and serve
from its index must not require one -- `sessionkey` is a same-browsing-
session convenience the search UI appends to its own generated links, not
a credential this client needs to supply. This matches ETSI's own "ETSI
IPR Online Database User Guide for Anonymous Users"
(ipr.etsi.org/UserGuide/UserGuide_Anonymous.htm, via search index), which
documents that anonymous, unauthenticated users get read-only access to
declarations in "reflected" state -- the same "no credential needed"
posture `docs/tools/etsi.md` already established for the deliver-path
PDFs, now confirmed for this register too. As with `ingest_etsi_standard`,
this client does not attempt to *discover* a declaration's URL from a bare
company or patent number -- no scriptable search/query API for this
register was found either (ipr.etsi.org is a dynamic ASP.NET application,
not a static per-document path); it takes the declaration's detail-page
URL directly, obtained however the caller already found it (e.g. by
searching https://ipr.etsi.org/ by hand).
"""

from __future__ import annotations

import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from knowledge.ingest import ingest_document
from knowledge.sourcing._http import download_bytes

_ALLOWED_HOST = "www.etsi.org"
_ALLOWED_PATH_PREFIX = "/deliver/"

_ALLOWED_IPR_HOST = "ipr.etsi.org"
_ALLOWED_IPR_PATH = "/IPRDetails.aspx"


def ingest_etsi_standard(
    document_url: str,
    *,
    license: str,
    classification: str,
    supersedes_document_id: int | None = None,
    download_dir: str | None = None,
    fetch_fn: Callable[[str], bytes] = download_bytes,
) -> dict[str, Any]:
    """Download the ETSI deliverable PDF at `document_url` (must be an
    `https://www.etsi.org/deliver/...` URL -- see this module's docstring
    for why this client takes the URL directly rather than a bare document
    number) and ingest it as `source_type='standard'`.

    `fetch_fn` defaults to a real HTTP GET (`knowledge.sourcing._http.
    download_bytes`) and exists so tests can inject a stub instead of
    hitting the network.
    """
    parsed = urlparse(document_url)
    if parsed.netloc != _ALLOWED_HOST or not parsed.path.startswith(_ALLOWED_PATH_PREFIX):
        raise ValueError(
            f"expected an https://{_ALLOWED_HOST}{_ALLOWED_PATH_PREFIX}... URL, "
            f"got {document_url!r}"
        )

    pdf_bytes = fetch_fn(document_url)

    work_dir = Path(download_dir) if download_dir else Path(tempfile.mkdtemp(prefix="etsi_"))
    work_dir.mkdir(parents=True, exist_ok=True)
    filename = Path(parsed.path).name or "etsi_standard.pdf"
    pdf_path = work_dir / filename
    pdf_path.write_bytes(pdf_bytes)

    return ingest_document(
        file_path=str(pdf_path),
        source_type="standard",
        license=license,
        classification=classification,
        supersedes_document_id=supersedes_document_id,
    )


def ingest_etsi_ipr_declaration(
    document_url: str,
    *,
    declared_against_document_id: int,
    license: str,
    classification: str,
    download_dir: str | None = None,
    fetch_fn: Callable[[str], bytes] = download_bytes,
) -> dict[str, Any]:
    """Download an ETSI IPR/FRAND-declaration document from the SR 000 314
    register (must be an `https://ipr.etsi.org/IPRDetails.aspx?...` URL --
    see this module's docstring for how that host/path was confirmed, and
    why this client takes the URL directly rather than a bare company or
    patent number) and ingest it as `source_type='standard'` -- the same
    source type `ingest_etsi_standard` already uses for every ETSI
    deliverable type, since a licensing declaration is still an ETSI
    document, not a new kind of source this repo tracks separately.

    `declared_against_document_id` is the `documents.id` of the standard
    (from a prior `ingest_etsi_standard()` call) this declaration was filed
    against. It is passed through as
    `extra_metadata={"declared_against_document_id": declared_against_document_id}`
    on the `ingest_document()` call, so the stored declaration stays
    traceably linked to the standard it constrains rather than becoming a
    free-floating PDF -- it is never inferred or guessed.

    `fetch_fn` defaults to a real HTTP GET (`knowledge.sourcing._http.
    download_bytes`) and exists so tests can inject a stub instead of
    hitting the network.
    """
    parsed = urlparse(document_url)
    if parsed.netloc != _ALLOWED_IPR_HOST or parsed.path != _ALLOWED_IPR_PATH:
        raise ValueError(
            f"expected an https://{_ALLOWED_IPR_HOST}{_ALLOWED_IPR_PATH}?... URL, "
            f"got {document_url!r}"
        )

    document_bytes = fetch_fn(document_url)

    work_dir = Path(download_dir) if download_dir else Path(tempfile.mkdtemp(prefix="etsi_ipr_"))
    work_dir.mkdir(parents=True, exist_ok=True)
    iprd_id = parse_qs(parsed.query).get("IPRD_ID", ["declaration"])[0]
    document_path = work_dir / f"etsi_ipr_declaration_{iprd_id}.pdf"
    document_path.write_bytes(document_bytes)

    return ingest_document(
        file_path=str(document_path),
        source_type="standard",
        license=license,
        classification=classification,
        extra_metadata={"declared_against_document_id": declared_against_document_id},
    )
