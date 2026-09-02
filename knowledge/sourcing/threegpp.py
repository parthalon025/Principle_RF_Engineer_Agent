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
"""

from __future__ import annotations

import io
import tempfile
import zipfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

from knowledge.ingest import ingest_document
from knowledge.sourcing._http import download_bytes

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
