#!/usr/bin/env python3
"""Standalone PDF-conversion driver for `knowledge/sourcing/patent.py`
(ticket #219), run as a subprocess via
`uv run --project .claude/skills/arxiv-doc-builder --extra pdf --no-dev`
against that vendored project's own installed pdfplumber/pdf2image/pypdf/
pillow stack (see `.claude/skills/arxiv-doc-builder/pyproject.toml`'s `pdf`
optional-dependency group) -- **this file itself lives outside
`.claude/skills/arxiv-doc-builder/` and is never edited under that tree**
(that directory is deliberately excluded from ruff per commit 2f8f894; see
`patent.py`'s own module docstring). It only *imports* the vendored,
document-agnostic library functions:

    arxiv_doc_builder.pdf_converter_lib.extract_page_content   -- per-page
        text extraction, with optional two-column splitting and running-
        header/footer stripping (`is_likely_header`/`is_likely_footer`).
    arxiv_doc_builder.pdf_image_lib.convert_pdf_to_images       -- renders
        every page to PNG at a given DPI, optionally column-split.

It never imports `arxiv_doc_builder.arxiv_metadata` or
`pdf_converter_lib.convert_pdf_to_markdown` -- both are arXiv-shaped
(title/authors/version/DOI/journal/categories) and would be the wrong
frontmatter schema for a patent (number/title/assignee/inventors/dates);
`patent.py` builds that frontmatter itself from this script's output, never
from the vendored `arxiv_metadata` module (ticket #219's acceptance
criterion: parse patent metadata "WITHOUT editing the vendored
arxiv_metadata module" -- not touching it at all is stronger than not
editing it).

Routing decision, mirroring `convert_paper.py`'s LaTeX-vs-PDF router SHAPE
(detect a document property, then branch) on a different signal: a granted
US patent's print-endpoint PDF is routinely a scanned image with no text
layer (confirmed directly against the real USPTO endpoint during this
ticket's research -- see patent.py's module docstring), so the signal here
is "does this PDF have any real extractable text", not "does LaTeX source
exist":

  - text layer present -> pdfplumber double-column extraction
    (`extract_page_content(page, i, is_double_column=True)` for every page
    -- patents are two-column with a running header on every page, exactly
    the shape that function already handles) plus page 1's raw text handed
    back separately for the caller's own INID-code bibliographic parsing.
  - no text layer -> `convert_pdf_to_images` renders every page to PNG at
    `--dpi` (default 1200 -- ticket #219: "the original hand-authored work
    used 1200 dpi for a similar case"). No OCR or vision transcription
    happens here, or anywhere in this repo's automated ingestion path: the
    rendered images are handed back as artifacts for a human, or a
    vision-capable follow-up session, to read -- the caller's ingested
    Markdown says this plainly rather than inventing body text it cannot
    support (this repo's "warn, never block" charter rule).

Writes one JSON manifest to `--manifest` (default `<output-dir>/
manifest.json`) rather than being parsed from this process's own stdout,
which also carries `pdf_image_lib`/`pdf_converter_lib`'s own progress
prints -- the caller reads that file, not this process's stdout/stderr.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pdfplumber
from arxiv_doc_builder.pdf_converter_lib import extract_page_content
from arxiv_doc_builder.pdf_image_lib import convert_pdf_to_images
from pypdf import PdfReader

# Below this many non-whitespace characters, summed across every page's
# pypdf `extract_text()`, the PDF is treated as scanned/no-text-layer rather
# than "has a text layer, just an unusually short one" -- comfortably above
# the noise floor of stray glyph/whitespace artifacts pypdf occasionally
# returns for a genuinely image-only page, comfortably below one real
# sentence of body or bibliographic text.
_TEXT_LAYER_MIN_CHARS = 40

_DEFAULT_DPI = 1200


def _has_text_layer(pdf_path: Path) -> bool:
    reader = PdfReader(pdf_path)
    total = 0
    for page in reader.pages:
        total += len((page.extract_text() or "").strip())
        if total >= _TEXT_LAYER_MIN_CHARS:
            return True
    return False


def _convert_text_layer(pdf_path: Path, output_dir: Path) -> dict:
    markdown_path = output_dir / f"{pdf_path.stem}.md"
    parts: list[str] = []
    front_page_text = ""
    with pdfplumber.open(pdf_path) as pdf:
        page_count = len(pdf.pages)
        for i, page in enumerate(pdf.pages, 1):
            page_text = page.extract_text() or ""
            if i == 1:
                front_page_text = page_text
            parts.append(f"\n\n<!-- Page {i} -->\n\n")
            parts.append(extract_page_content(page, i, is_double_column=True))
    markdown_path.write_text("".join(parts), encoding="utf-8")
    return {
        "route": "text",
        "page_count": page_count,
        "markdown_path": str(markdown_path),
        "front_page_text": front_page_text,
    }


def _convert_vision(pdf_path: Path, output_dir: Path, dpi: int) -> dict:
    images_dir = output_dir / "images"
    image_paths, _pdf_meta = convert_pdf_to_images(
        pdf_path, images_dir, dpi=dpi, split_columns=True, num_columns=2
    )
    page_count = len(PdfReader(pdf_path).pages)
    return {
        "route": "vision",
        "page_count": page_count,
        "image_dir": str(images_dir),
        "image_paths": [str(p) for p in image_paths],
        "dpi": dpi,
        # No text layer at all -- there is nothing to parse INID fields
        # from, so the caller gets an explicit empty string (same "unknown
        # stays unknown" contract as the text route's own front_page_text
        # when a field is simply absent from page 1).
        "front_page_text": "",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf_path", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--dpi", type=int, default=_DEFAULT_DPI)
    parser.add_argument("--manifest", type=Path, default=None)
    args = parser.parse_args()

    if not args.pdf_path.exists():
        print(f"Error: PDF not found: {args.pdf_path}", file=sys.stderr)
        return 1

    args.output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = args.manifest or (args.output_dir / "manifest.json")

    if _has_text_layer(args.pdf_path):
        print(f"Text layer detected in {args.pdf_path}; running double-column extraction.")
        result = _convert_text_layer(args.pdf_path, args.output_dir)
    else:
        print(
            f"No text layer in {args.pdf_path} (scanned image, a normal case for a "
            f"USPTO print PDF); rendering pages to PNG at {args.dpi} DPI."
        )
        result = _convert_vision(args.pdf_path, args.output_dir, args.dpi)

    manifest_path.write_text(json.dumps(result), encoding="utf-8")
    print(f"Wrote manifest: {manifest_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
