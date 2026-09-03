"""Thin client: ETSI standard -> knowledge base (ticket #68).

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
"""

from __future__ import annotations

import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from knowledge.ingest import ingest_document
from knowledge.sourcing._http import download_bytes

_ALLOWED_HOST = "www.etsi.org"
_ALLOWED_PATH_PREFIX = "/deliver/"


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
