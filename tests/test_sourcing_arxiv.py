"""Ticket #68 (and its arxiv-doc-builder integration follow-up):
knowledge/sourcing/arxiv.py, tested at the seam -- a stubbed `convert_fn`
stands in for the real `uv run --project .../arxiv-doc-builder convert-paper`
subprocess, and `ingest_document` is monkeypatched to capture exactly what
it was called with, mirroring tests/test_nec2pp.py's fake-executable-not-
real-binary pattern applied to a subprocess call instead of a network fetch.
No network access, no subprocess, no database.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from knowledge.models import SourceType
from knowledge.provenance import arxiv_preprint_authority_rank, default_authority_rank
from knowledge.sourcing import arxiv


def _capture(monkeypatch, result=None):
    captured: dict = {}

    def fake_ingest_document(**kwargs):
        captured.update(kwargs)
        return result if result is not None else {"status": "ingested", "document_id": 1}

    monkeypatch.setattr(arxiv, "ingest_document", fake_ingest_document)
    return captured


def _write_md_with_frontmatter(path: Path, **fields) -> None:
    """Hand-write a Markdown file shaped like arxiv-doc-builder's real
    output: a YAML frontmatter block (arxiv_metadata.build_frontmatter's
    exact key set is a superset of what's passed here -- callers only need
    to supply the fields a given test cares about) followed by body text."""
    lines = ["---"]
    for key, value in fields.items():
        if value is None:
            lines.append(f"{key}:")
        elif isinstance(value, list):
            lines.append(f"{key}:")
            lines.extend(f'  - "{item}"' for item in value)
        else:
            lines.append(f'{key}: "{value}"')
    lines += ["---", "", "", "# Body", "", "Paper content."]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


# --- _parse_frontmatter (pure) ----------------------------------------

_SAMPLE_FRONTMATTER = """---
title: "Adaptive Metamaterial Skins for Conformal Antennas"
authors: "Jane Doe, John Smith"
arxiv_id: "2401.01234"
version: "2401.01234v2"
published: "2024-01-15"
primary_category: "physics.app-ph"
categories:
  - "physics.app-ph"
  - "eess.SP"
doi:
journal:
source_type: "paper"
conversion_date: "2026-09-05"
abstract: |-
  We present a design for adaptive metamaterial skins.
---

# Adaptive Metamaterial Skins

Body content here.
"""


def test_parse_frontmatter_extracts_all_fields():
    fm = arxiv._parse_frontmatter(_SAMPLE_FRONTMATTER)
    assert fm["title"] == "Adaptive Metamaterial Skins for Conformal Antennas"
    assert fm["authors"] == "Jane Doe, John Smith"
    assert fm["version"] == "2401.01234v2"
    assert fm["doi"] is None
    assert fm["categories"] == ["physics.app-ph", "eess.SP"]
    assert fm["abstract"] == "We present a design for adaptive metamaterial skins."


def test_parse_frontmatter_returns_empty_dict_when_absent():
    assert arxiv._parse_frontmatter("# No frontmatter here\n\nJust body text.\n") == {}


# --- _run_convert_paper (subprocess boundary, stubbed) -----------------


def test_run_convert_paper_invokes_uv_run_against_the_skill_project(tmp_path, monkeypatch):
    captured_cmd = {}

    def fake_run(cmd, capture_output, text, timeout):
        captured_cmd["cmd"] = cmd
        captured_cmd["timeout"] = timeout
        md_path = tmp_path / "2401.01234" / "2401.01234.md"
        _write_md_with_frontmatter(md_path, title="X", authors="Y", version="v1")
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(arxiv.subprocess, "run", fake_run)
    md_path = arxiv._run_convert_paper("2401.01234", tmp_path)

    assert md_path == tmp_path / "2401.01234" / "2401.01234.md"
    cmd = captured_cmd["cmd"]
    assert cmd[:3] == ["uv", "run", "--project"]
    assert "--no-dev" in cmd
    assert str(arxiv._ARXIV_DOC_BUILDER_DIR) in cmd
    assert "convert-paper" in cmd
    assert "2401.01234" in cmd
    assert "--output-dir" in cmd
    assert str(tmp_path) in cmd
    assert captured_cmd["timeout"] == arxiv._CONVERT_PAPER_TIMEOUT_S


def test_run_convert_paper_raises_on_nonzero_exit(tmp_path, monkeypatch):
    def fake_run(cmd, capture_output, text, timeout):
        return subprocess.CompletedProcess(cmd, 1, stdout="fetch failed", stderr="network error")

    monkeypatch.setattr(arxiv.subprocess, "run", fake_run)
    with pytest.raises(RuntimeError, match="fetch failed"):
        arxiv._run_convert_paper("2401.01234", tmp_path)


def test_run_convert_paper_raises_if_output_file_missing(tmp_path, monkeypatch):
    def fake_run(cmd, capture_output, text, timeout):
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(arxiv.subprocess, "run", fake_run)
    with pytest.raises(RuntimeError, match="does not exist"):
        arxiv._run_convert_paper("2401.01234", tmp_path)


def test_run_convert_paper_raises_on_timeout(tmp_path, monkeypatch):
    def fake_run(cmd, capture_output, text, timeout):
        raise subprocess.TimeoutExpired(cmd, timeout)

    monkeypatch.setattr(arxiv.subprocess, "run", fake_run)
    with pytest.raises(RuntimeError, match="timed out"):
        arxiv._run_convert_paper("2401.01234", tmp_path)


# --- ingest_arxiv_paper (convert_fn seam, ingest_document monkeypatched) --


def test_ingest_arxiv_paper_calls_ingest_document_with_paper_source_type(tmp_path, monkeypatch):
    captured = _capture(monkeypatch)
    md_path = tmp_path / "2401.01234" / "2401.01234.md"
    _write_md_with_frontmatter(md_path, title="A Great Paper", authors="Jane Doe", version="v1")

    result = arxiv.ingest_arxiv_paper(
        "2401.01234",
        license="cc-by-4.0",
        classification="PUBLIC",
        download_dir=str(tmp_path),
        convert_fn=lambda arxiv_id, output_dir: md_path,
    )

    assert captured["source_type"] == "paper"
    assert captured["license"] == "cc-by-4.0"
    assert captured["classification"] == "PUBLIC"
    assert captured["file_path"] == str(md_path)
    assert result == {"status": "ingested", "document_id": 1}


def test_ingest_arxiv_paper_extracts_title_author_revision_from_frontmatter(tmp_path, monkeypatch):
    captured = _capture(monkeypatch)
    md_path = tmp_path / "paper.md"
    _write_md_with_frontmatter(
        md_path,
        title="Adaptive Metamaterial Skins",
        authors="Jane Doe, John Smith",
        version="2401.01234v2",
    )

    arxiv.ingest_arxiv_paper(
        "2401.01234",
        license="cc-by-4.0",
        classification="PUBLIC",
        download_dir=str(tmp_path),
        convert_fn=lambda arxiv_id, output_dir: md_path,
    )

    assert captured["title_override"] == "Adaptive Metamaterial Skins"
    assert captured["author"] == "Jane Doe, John Smith"
    assert captured["revision"] == "2401.01234v2"


def test_ingest_arxiv_paper_passes_remaining_frontmatter_as_extra_metadata(tmp_path, monkeypatch):
    captured = _capture(monkeypatch)
    md_path = tmp_path / "paper.md"
    _write_md_with_frontmatter(
        md_path,
        title="A Paper",
        authors="Jane Doe",
        version="v1",
        arxiv_id="2401.01234",
        doi="10.1000/example",
        categories=["physics.app-ph"],
    )

    arxiv.ingest_arxiv_paper(
        "2401.01234",
        license="cc-by-4.0",
        classification="PUBLIC",
        download_dir=str(tmp_path),
        convert_fn=lambda arxiv_id, output_dir: md_path,
    )

    extra = captured["extra_metadata"]
    assert extra["arxiv_id"] == "2401.01234"
    assert extra["doi"] == "10.1000/example"
    assert extra["categories"] == ["physics.app-ph"]
    assert "title" not in extra
    assert "authors" not in extra
    assert "version" not in extra


def test_ingest_arxiv_paper_handles_missing_frontmatter_gracefully(tmp_path, monkeypatch):
    captured = _capture(monkeypatch)
    md_path = tmp_path / "paper.md"
    md_path.write_text("# No frontmatter\n\nJust body text.\n", encoding="utf-8")

    arxiv.ingest_arxiv_paper(
        "2401.01234",
        license="cc-by-4.0",
        classification="PUBLIC",
        download_dir=str(tmp_path),
        convert_fn=lambda arxiv_id, output_dir: md_path,
    )

    assert captured["title_override"] is None
    assert captured["author"] is None
    assert captured["revision"] is None
    assert captured["extra_metadata"] == {}


def test_ingest_arxiv_paper_overrides_authority_rank_below_peer_reviewed_default(
    tmp_path, monkeypatch
):
    captured = _capture(monkeypatch)
    md_path = tmp_path / "paper.md"
    _write_md_with_frontmatter(md_path, title="X", authors="Y", version="v1")

    arxiv.ingest_arxiv_paper(
        "2401.01234",
        license="cc-by-4.0",
        classification="PUBLIC",
        download_dir=str(tmp_path),
        convert_fn=lambda arxiv_id, output_dir: md_path,
    )

    assert captured["authority_rank_override"] == arxiv_preprint_authority_rank()
    # The whole point of the override: worse (numerically higher) than what
    # a peer-reviewed "paper" document would default to.
    assert captured["authority_rank_override"] > default_authority_rank(SourceType.PAPER)


def test_ingest_arxiv_paper_passes_raw_arxiv_id_to_convert_fn(tmp_path, monkeypatch):
    _capture(monkeypatch)
    md_path = tmp_path / "paper.md"
    _write_md_with_frontmatter(md_path, title="X", authors="Y", version="v1")
    seen_ids: list[str] = []

    def fake_convert(arxiv_id, output_dir):
        seen_ids.append(arxiv_id)
        return md_path

    arxiv.ingest_arxiv_paper(
        "cond-mat/0207270",
        license="arxiv-perpetual-non-exclusive",
        classification="PUBLIC",
        download_dir=str(tmp_path),
        convert_fn=fake_convert,
    )

    assert seen_ids == ["cond-mat/0207270"]


def test_ingest_arxiv_paper_creates_tempdir_when_download_dir_omitted(monkeypatch):
    _capture(monkeypatch)
    seen_dirs: list[Path] = []

    def fake_convert(arxiv_id, output_dir):
        seen_dirs.append(output_dir)
        md_path = output_dir / "paper.md"
        _write_md_with_frontmatter(md_path, title="X", authors="Y", version="v1")
        return md_path

    arxiv.ingest_arxiv_paper(
        "2401.01234",
        license="cc-by-4.0",
        classification="PUBLIC",
        convert_fn=fake_convert,
    )

    assert len(seen_dirs) == 1
    assert seen_dirs[0].exists()


def test_ingest_arxiv_paper_rejects_implausible_id(tmp_path):
    with pytest.raises(ValueError):
        arxiv.ingest_arxiv_paper(
            "; rm -rf /",
            license="x",
            classification="PUBLIC",
            download_dir=str(tmp_path),
            convert_fn=lambda arxiv_id, output_dir: Path("unused"),
        )


def test_arxiv_authority_rank_sits_between_paper_and_internal_history_tiers():
    """Sanity-checks the override constant itself, independent of the
    client: worse than a peer-reviewed paper, but not as low as this
    team's own unreviewed internal design-record history (the
    `design_record` source type's default rank, per knowledge/provenance.py's
    INTERNAL_HISTORY tier)."""
    rank = arxiv_preprint_authority_rank()
    assert default_authority_rank(SourceType.PAPER) < rank
    assert rank < default_authority_rank(SourceType.DESIGN_RECORD)


# --- search_arxiv_papers (issue #257: discovery search, fetch_fn seam,
# candidates only -- never ingests) --------------------------------------

# A canned two-entry `search_query` Atom response, shaped like arXiv's real
# query API output (the same Atom + arxiv: extension namespaces
# arxiv_doc_builder/arxiv_metadata.py's fetch_metadata parses for the by-id
# form of this feed) -- indentation inside <title>/<summary> deliberately
# mirrors arXiv's actual pretty-printed responses, to exercise whitespace
# collapsing.
_SEARCH_ATOM_MULTI = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom"
      xmlns:opensearch="http://a9.com/-/spec/opensearch/1.1/"
      xmlns:arxiv="http://arxiv.org/schemas/atom">
  <link href="http://arxiv.org/api/query?search_query=all:metamaterial" rel="self"
        type="application/atom+xml"/>
  <title type="html">ArXiv Query: search_query=all:metamaterial</title>
  <id>http://arxiv.org/api/dGhpcyBpcyBhIHRlc3Q</id>
  <updated>2024-01-16T00:00:00-05:00</updated>
  <opensearch:totalResults>2</opensearch:totalResults>
  <opensearch:startIndex>0</opensearch:startIndex>
  <opensearch:itemsPerPage>2</opensearch:itemsPerPage>
  <entry>
    <id>http://arxiv.org/abs/2401.01234v2</id>
    <updated>2024-01-16T00:00:00Z</updated>
    <published>2024-01-15T00:00:00Z</published>
    <title>
   Adaptive Metamaterial Skins for Conformal Antennas
    </title>
    <summary>
  We present a design for adaptive metamaterial skins that behave as a
  magnetic mirror across X-band.
    </summary>
    <author><name>Jane Doe</name></author>
    <author><name>John Smith</name></author>
    <link href="http://arxiv.org/abs/2401.01234v2" rel="alternate" type="text/html"/>
    <link title="pdf" href="http://arxiv.org/pdf/2401.01234v2" rel="related"
          type="application/pdf"/>
    <arxiv:primary_category term="physics.app-ph" scheme="http://arxiv.org/schemas/atom"/>
    <category term="physics.app-ph" scheme="http://arxiv.org/schemas/atom"/>
  </entry>
  <entry>
    <id>http://arxiv.org/abs/cond-mat/0207270v1</id>
    <updated>2002-07-11T00:00:00Z</updated>
    <published>2002-07-11T00:00:00Z</published>
    <title>Legacy Frequency Selective Surface Absorbers</title>
    <summary>An early study of frequency selective surface absorbers.</summary>
    <author><name>A. Researcher</name></author>
    <link href="http://arxiv.org/abs/cond-mat/0207270v1" rel="alternate" type="text/html"/>
    <link title="pdf" href="http://arxiv.org/pdf/cond-mat/0207270v1" rel="related"
          type="application/pdf"/>
    <arxiv:primary_category term="cond-mat.mtrl-sci" scheme="http://arxiv.org/schemas/atom"/>
    <category term="cond-mat.mtrl-sci" scheme="http://arxiv.org/schemas/atom"/>
  </entry>
</feed>
"""

# A real "no matches" arXiv response -- zero <entry> elements, not a fetch
# failure.
_SEARCH_ATOM_EMPTY = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom"
      xmlns:opensearch="http://a9.com/-/spec/opensearch/1.1/">
  <link href="http://arxiv.org/api/query?search_query=all:zzznomatchzzz" rel="self"
        type="application/atom+xml"/>
  <title type="html">ArXiv Query: search_query=all:zzznomatchzzz</title>
  <id>http://arxiv.org/api/abc123</id>
  <updated>2024-01-16T00:00:00-05:00</updated>
  <opensearch:totalResults>0</opensearch:totalResults>
  <opensearch:startIndex>0</opensearch:startIndex>
  <opensearch:itemsPerPage>0</opensearch:itemsPerPage>
</feed>
"""


def test_search_arxiv_papers_parses_multi_entry_response_in_feed_order():
    candidates = arxiv.search_arxiv_papers(
        "metamaterial absorber",
        fetch_fn=lambda url: _SEARCH_ATOM_MULTI.encode("utf-8"),
    )

    assert [c["id"] for c in candidates] == ["2401.01234v2", "cond-mat/0207270v1"]

    first = candidates[0]
    assert first["title"] == "Adaptive Metamaterial Skins for Conformal Antennas"
    assert first["published"] == "2024-01-15"
    assert first["abstract"] == (
        "We present a design for adaptive metamaterial skins that behave "
        "as a magnetic mirror across X-band."
    )

    second = candidates[1]
    assert second["title"] == "Legacy Frequency Selective Surface Absorbers"
    assert second["published"] == "2002-07-11"
    assert second["abstract"] == "An early study of frequency selective surface absorbers."


def test_search_arxiv_papers_returns_empty_list_on_zero_matches():
    candidates = arxiv.search_arxiv_papers(
        "zzznomatchzzz", fetch_fn=lambda url: _SEARCH_ATOM_EMPTY.encode("utf-8")
    )
    assert candidates == []


def test_search_arxiv_papers_propagates_fetch_fn_error_instead_of_swallowing_it():
    def failing_fetch(url):
        raise OSError("network unreachable")

    with pytest.raises(OSError, match="network unreachable"):
        arxiv.search_arxiv_papers("metamaterial", fetch_fn=failing_fetch)


def test_search_arxiv_papers_threads_max_results_into_query_url():
    captured_urls: list[str] = []

    def fake_fetch(url):
        captured_urls.append(url)
        return _SEARCH_ATOM_EMPTY.encode("utf-8")

    arxiv.search_arxiv_papers("metamaterial", max_results=25, fetch_fn=fake_fetch)

    assert len(captured_urls) == 1
    assert "max_results=25" in captured_urls[0]
    assert "search_query=" in captured_urls[0]


def test_search_arxiv_papers_candidate_ids_round_trip_through_arxiv_id_re():
    candidates = arxiv.search_arxiv_papers(
        "metamaterial", fetch_fn=lambda url: _SEARCH_ATOM_MULTI.encode("utf-8")
    )

    assert len(candidates) == 2
    for candidate in candidates:
        assert arxiv._ARXIV_ID_RE.match(candidate["id"])


def test_search_arxiv_papers_never_calls_ingest_document(monkeypatch):
    """Enforces user story 19: search and ingest stay two separate calls,
    with nothing wired to auto-chain them. `ingest_document` is
    monkeypatched to raise if it is ever called, so any accidental
    auto-ingest path fails this test loudly instead of passing silently."""

    def fail_if_called(**kwargs):
        raise AssertionError("search_arxiv_papers must never call ingest_document")

    monkeypatch.setattr(arxiv, "ingest_document", fail_if_called)

    candidates = arxiv.search_arxiv_papers(
        "metamaterial", fetch_fn=lambda url: _SEARCH_ATOM_MULTI.encode("utf-8")
    )

    # Sanity: the search itself ran and found results -- this isn't passing
    # merely because nothing happened.
    assert len(candidates) == 2
