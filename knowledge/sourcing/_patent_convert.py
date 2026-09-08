#!/usr/bin/env python3
"""Subprocess entry point that drives the vendored arxiv-doc-builder skill's
PDF converters against a patent PDF (issue #219).

NOT IMPORTED BY THIS PACKAGE. `knowledge/sourcing/patent.py` executes this
file as a script through

    uv run --project .claude/skills/arxiv-doc-builder --extra pdf --no-dev \\
        python knowledge/sourcing/_patent_convert.py ...

so it runs inside the *skill's* own isolated environment, where
`arxiv_doc_builder` and its `pdf` extra (pdfplumber / pypdf / pdf2image /
pillow) are installed. None of those live in this project's dependency tree,
which is exactly why this is a subprocess and not an import -- the same
boundary `knowledge/sourcing/arxiv.py` already draws around `convert-paper`
(commit 0274b42). Nothing in this file may import from this repo: its
interpreter cannot see it.

*In plain terms: this is a small program run in a borrowed toolbox. It opens
the PDF, pulls out whatever text is really in it, and writes a JSON note
saying what it found, so the caller on the other side of the wall can decide
what to do next.*

WHY A REPO-SIDE SCRIPT RATHER THAN A NEW VENDORED ONE. The skill is
deliberately excluded from this repo's ruff config (commit 2f8f894) because
it is upstream code, so adding a patent-shaped entry point *inside* it would
create a permanent local diff to re-merge on every skill update. Everything
patent-specific therefore lives here, on this repo's side of the seam, and
the vendored library is used strictly as a library:

  - `pdf_converter_lib.extract_page_content(page, n, is_double_column=...)`
    -- generic, no arXiv coupling, already does the two-column split and the
    running-header/footer stripping a patent needs.
  - `pdf_image_lib.convert_pdf_to_images` -- renders pages (and per-column
    crops) to PNG, the "read the drawing sheet with your eyes" path.

`pdf_converter_lib.convert_pdf_to_markdown` is the one function deliberately
NOT used: it is the layer that reaches for `arxiv_metadata` to write arXiv
frontmatter. Assembling the Markdown here instead is what keeps the patent
path off that arXiv coupling without editing a vendored line.

Two subcommands, because the caller must see how much real text a document
has before deciding whether rendering every page to an image is worth it:

    extract <pdf> --output-dir D
        Writes D/body.md (all pages, two-column) and D/manifest.json
        (page_count, text_chars, the two front-page renderings).

    render <pdf> --output-dir D [--dpi 300]
        Writes page/column PNGs under D/images and D/render_manifest.json.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

EXTRACT_MANIFEST_NAME = "manifest.json"
RENDER_MANIFEST_NAME = "render_manifest.json"
BODY_MARKDOWN_NAME = "body.md"
IMAGES_DIR_NAME = "images"


def _extract(pdf_path: Path, output_dir: Path) -> dict:
    """Pull the text layer out of `pdf_path`, two-column, page by page.

    Patents are printed in two columns with a running header on every page
    after the front sheet, which is precisely the shape
    `extract_page_content(..., is_double_column=True)` handles: it crops each
    page down the middle, reads the left half then the right half, and drops
    lines that look like a header or a footer.

    The front sheet is the exception and is captured twice. It is a
    bibliographic cover, not body text: the INID-coded fields (the
    parenthesised numbers -- (54) title, (72) inventors, and so on) sit in a
    left block while the abstract sits in a right block, but the top band
    with the patent number and date spans the full width and is cut in half
    by the two-column crop. So both renderings are handed back and
    `patent.py` reads whichever one carries each field.

    `text_chars` counts raw extracted characters *before* any header/footer
    stripping -- it answers only "does this PDF have a text layer at all",
    and must not be biased by the cleanup.
    """
    import pdfplumber
    from arxiv_doc_builder.pdf_converter_lib import extract_page_content

    output_dir.mkdir(parents=True, exist_ok=True)
    body_path = output_dir / BODY_MARKDOWN_NAME

    parts: list[str] = []
    text_chars = 0
    front_page_double_column = ""
    front_page_single_column = ""

    with pdfplumber.open(pdf_path) as pdf:
        page_count = len(pdf.pages)
        for page_number, page in enumerate(pdf.pages, 1):
            raw = page.extract_text() or ""
            text_chars += len(raw)

            content = extract_page_content(page, page_number, is_double_column=True)
            if page_number == 1:
                front_page_double_column = content
                front_page_single_column = extract_page_content(
                    page, page_number, is_double_column=False
                )

            parts.append(f"\n\n<!-- Page {page_number} (double-column) -->\n\n")
            parts.append(content)

    body_path.write_text("".join(parts), encoding="utf-8")

    return {
        "page_count": page_count,
        "text_chars": text_chars,
        "body_path": str(body_path),
        "front_page_double_column": front_page_double_column,
        "front_page_single_column": front_page_single_column,
    }


def _render(pdf_path: Path, output_dir: Path, dpi: int) -> dict:
    """Render every page (plus its two column crops) to PNG.

    This is the vendored skill's own vision workflow, unchanged: a scanned
    patent has no text to extract, and a drawing sheet has no text worth
    extracting even when the rest of the document does, so the only way to
    read either is to look at the picture.
    """
    from arxiv_doc_builder.pdf_image_lib import convert_pdf_to_images

    images_dir = output_dir / IMAGES_DIR_NAME
    image_paths, _metadata = convert_pdf_to_images(
        pdf_path, images_dir, dpi, split_columns=True, num_columns=2
    )
    return {
        "image_dir": str(images_dir),
        "image_count": len(image_paths),
        "dpi": dpi,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    extract_parser = subparsers.add_parser("extract", help="extract the PDF's text layer")
    extract_parser.add_argument("pdf_path", type=Path)
    extract_parser.add_argument("--output-dir", type=Path, required=True)

    render_parser = subparsers.add_parser("render", help="render pages to PNG images")
    render_parser.add_argument("pdf_path", type=Path)
    render_parser.add_argument("--output-dir", type=Path, required=True)
    render_parser.add_argument("--dpi", type=int, default=300)

    args = parser.parse_args(argv)

    if not args.pdf_path.exists():
        print(f"Error: PDF file not found: {args.pdf_path}", file=sys.stderr)
        return 1

    args.output_dir.mkdir(parents=True, exist_ok=True)
    if args.command == "extract":
        manifest = _extract(args.pdf_path, args.output_dir)
        manifest_path = args.output_dir / EXTRACT_MANIFEST_NAME
    else:
        manifest = _render(args.pdf_path, args.output_dir, args.dpi)
        manifest_path = args.output_dir / RENDER_MANIFEST_NAME

    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Wrote {manifest_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
