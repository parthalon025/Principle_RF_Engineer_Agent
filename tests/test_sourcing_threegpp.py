"""Ticket #68: knowledge/sourcing/threegpp.py, tested at the seam -- a
stubbed `fetch_fn` stands in for the real network GET, and `ingest_document`
is monkeypatched to capture exactly what it was called with. No network
access, no database."""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pytest

from knowledge.sourcing import threegpp


def _capture(monkeypatch, result=None):
    captured: dict = {}

    def fake_ingest_document(**kwargs):
        captured.update(kwargs)
        return result if result is not None else {"status": "ingested", "document_id": 1}

    monkeypatch.setattr(threegpp, "ingest_document", fake_ingest_document)
    return captured


def _make_zip(entries: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, content in entries.items():
            zf.writestr(name, content)
    return buf.getvalue()


def test_ingest_3gpp_spec_calls_ingest_document_with_standard_source_type(tmp_path, monkeypatch):
    captured = _capture(monkeypatch)
    zip_bytes = _make_zip({"38331-h00.docx": b"docx content"})
    fetched_urls: list[str] = []

    def fake_fetch(url: str) -> bytes:
        fetched_urls.append(url)
        return zip_bytes

    result = threegpp.ingest_3gpp_spec(
        "38.331",
        "h00",
        license="3gpp-copyright",
        classification="PUBLIC",
        download_dir=str(tmp_path),
        fetch_fn=fake_fetch,
    )

    assert fetched_urls == ["https://www.3gpp.org/ftp/Specs/archive/38_series/38.331/38331-h00.zip"]
    assert captured["source_type"] == "standard"
    assert captured["license"] == "3gpp-copyright"
    assert captured["classification"] == "PUBLIC"
    assert Path(captured["file_path"]).name == "38331-h00.docx"
    assert Path(captured["file_path"]).read_bytes() == b"docx content"
    assert result == {"status": "ingested", "document_id": 1}


def test_multi_part_spec_number_keeps_its_own_dash_in_the_url(tmp_path, monkeypatch):
    _capture(monkeypatch)
    zip_bytes = _make_zip({"38521-1-h00.docx": b"x"})
    fetched_urls: list[str] = []

    def fake_fetch(url: str) -> bytes:
        fetched_urls.append(url)
        return zip_bytes

    threegpp.ingest_3gpp_spec(
        "38.521-1",
        "h00",
        license="3gpp-copyright",
        classification="PUBLIC",
        download_dir=str(tmp_path),
        fetch_fn=fake_fetch,
    )

    assert fetched_urls == [
        "https://www.3gpp.org/ftp/Specs/archive/38_series/38.521-1/38521-1-h00.zip"
    ]


def test_prefers_docx_over_legacy_doc_and_the_largest_docx_member(tmp_path, monkeypatch):
    captured = _capture(monkeypatch)
    zip_bytes = _make_zip(
        {
            "cover_sheet.docx": b"small",
            "38331-h00.docx": b"the actual much longer spec text" * 10,
            "38331-h00.doc": b"legacy fallback, should be ignored when docx exists",
        }
    )

    threegpp.ingest_3gpp_spec(
        "38.331",
        "h00",
        license="3gpp-copyright",
        classification="PUBLIC",
        download_dir=str(tmp_path),
        fetch_fn=lambda url: zip_bytes,
    )

    assert Path(captured["file_path"]).name == "38331-h00.docx"


def test_falls_back_to_legacy_doc_when_no_docx_present(tmp_path, monkeypatch):
    captured = _capture(monkeypatch)
    zip_bytes = _make_zip({"24008-h90.doc": b"legacy binary word doc content"})

    threegpp.ingest_3gpp_spec(
        "24.008",
        "h90",
        license="3gpp-copyright",
        classification="PUBLIC",
        download_dir=str(tmp_path),
        fetch_fn=lambda url: zip_bytes,
    )

    assert Path(captured["file_path"]).name == "24008-h90.doc"


def test_raises_when_zip_has_no_document_member(tmp_path):
    zip_bytes = _make_zip({"readme.txt": b"nothing useful"})

    with pytest.raises(ValueError):
        threegpp.ingest_3gpp_spec(
            "38.331",
            "h00",
            license="3gpp-copyright",
            classification="PUBLIC",
            download_dir=str(tmp_path),
            fetch_fn=lambda url: zip_bytes,
        )


# --- lookup_3gpp_spec_status (ticket #285) --------------------------------
#
# Fixture below reproduces the structure of the real per-series DynaReport
# table fetched from https://www.3gpp.org/dynareport?code=38-series.htm
# (confirmed by fetching that live page during this ticket's implementation,
# 2026-09): a `<table id="a3dyntab">` with three columns -- spec number
# (nested inside an `<a>`, with a leading "TS " label and a stray unmatched
# `</span>` after the link, both present on the real page), title, and
# notes -- rows alternating class="odd"/"even", a withdrawn spec's notes
# cell reading "SPECIFICATION WITHDRAWN" in red bold, and a current spec's
# notes cell always exactly the same "&nbsp;" wrapped in the same <font><b>
# tags. Titles below are shortened paraphrases, not the real page's exact
# wording (kept under this repo's 100-column limit) -- the two facts this
# fixture must be faithful to for `lookup_3gpp_spec_status`'s own claims to
# hold are the column count/notes values above, not the title text. Real
# per-series report has no version column at all (only "spec number",
# "title", "notes" in its own <thead>), which is why
# `lookup_3gpp_spec_status` documents `version` as always `None`. See this
# module's docstring and docs/tools/3gpp.md for that finding in full.
_SERIES_TABLE_HTML = """
<html><body>
<h1>3GPP Specification series</h1>
<table id="a3dyntab" class="sortable dsptab adynspec tablesorter">
<thead><tr bgcolor="#BEF781"><th>spec number</th><th>title</th><th>notes</th></tr></thead>
<tbody>
  <tr class="odd">
    <td width="100">TS <a target="_blank" href="/dynareport/38101.htm" >38.101</a></span></td>
    <td width="500">NR; UE radio transmission and reception</td>
    <td width="160"><font color="#FF0000" size="1" face="Arial"><b>SPECIFICATION WITHDRAWN</b></td>
  </tr>
  <tr class="even">
    <td width="100">TS <a target="_blank" href="/dynareport/38101-1.htm" >38.101-1</a></span></td>
    <td width="500">NR; UE radio TX/RX; Part 1: Range 1 Standalone</td>
    <td width="160"><font color="#FF0000" size="1" face="Arial"><b>&nbsp;</b></td>
  </tr>
  <tr class="odd">
    <td width="100">TS <a target="_blank" href="/dynareport/38101-2.htm" >38.101-2</a></span></td>
    <td width="500">NR; UE radio TX/RX; Part 2: Range 2 Standalone</td>
    <td width="160"><font color="#FF0000" size="1" face="Arial"><b>&nbsp;</b></td>
  </tr>
  <tr class="even">
    <td width="100">TS <a target="_blank" href="/dynareport/38101-3.htm" >38.101-3</a></span></td>
    <td width="500">NR; UE radio TX/RX; Part 3: R1/R2 interworking w/ other radios</td>
    <td width="160"><font color="#FF0000" size="1" face="Arial"><b>&nbsp;</b></td>
  </tr>
  <tr class="odd">
    <td width="100">TS <a target="_blank" href="/dynareport/38101-4.htm" >38.101-4</a></span></td>
    <td width="500">NR; UE radio TX/RX; Part 4: Performance requirements</td>
    <td width="160"><font color="#FF0000" size="1" face="Arial"><b>&nbsp;</b></td>
  </tr>
  <tr class="even">
    <td width="100">TS <a target="_blank" href="/dynareport/38101-5.htm" >38.101-5</a></span></td>
    <td width="500">NR; UE radio TX/RX; Part 5: Satellite access RF/performance</td>
    <td width="160"><font color="#FF0000" size="1" face="Arial"><b>&nbsp;</b></td>
  </tr>
</tbody>
</table>
</body></html>
"""


def test_lookup_reports_withdrawn_spec_as_withdrawn():
    fetched_urls: list[str] = []

    def fake_fetch(url: str) -> bytes:
        fetched_urls.append(url)
        return _SERIES_TABLE_HTML.encode("utf-8")

    result = threegpp.lookup_3gpp_spec_status("38.101", fetch_fn=fake_fetch)

    assert fetched_urls == ["https://www.3gpp.org/dynareport?code=38-series.htm"]
    assert result["spec_number"] == "38.101"
    assert result["withdrawn"] is True
    assert result["title"] == "NR; UE radio transmission and reception"


def test_lookup_reports_current_part_as_not_withdrawn():
    result = threegpp.lookup_3gpp_spec_status(
        "38.101-1", fetch_fn=lambda url: _SERIES_TABLE_HTML.encode("utf-8")
    )

    assert result["spec_number"] == "38.101-1"
    assert result["withdrawn"] is False
    assert result["title"] == "NR; UE radio TX/RX; Part 1: Range 1 Standalone"


def test_lookup_derives_series_url_from_multi_part_spec_number():
    fetched_urls: list[str] = []

    def fake_fetch(url: str) -> bytes:
        fetched_urls.append(url)
        return _SERIES_TABLE_HTML.encode("utf-8")

    threegpp.lookup_3gpp_spec_status("38.101-3", fetch_fn=fake_fetch)

    # Same series-extraction rule as `_spec_url`: text before the first "."
    # only -- "38.101-3" still maps to the "38" series, not "38.101-3".
    assert fetched_urls == ["https://www.3gpp.org/dynareport?code=38-series.htm"]


def test_lookup_raises_a_named_error_when_spec_not_in_table():
    with pytest.raises(threegpp.SpecNotFoundError):
        threegpp.lookup_3gpp_spec_status(
            "38.999", fetch_fn=lambda url: _SERIES_TABLE_HTML.encode("utf-8")
        )


def test_lookup_not_found_error_is_a_value_error_naming_known_specs():
    # Matches geometry.unit_cell.SymbolNotFoundError's "name what was sought
    # AND what IS available" shape (both are ValueError subclasses for the
    # same "identifier doesn't resolve to a row in a fetched collection"
    # failure), so a caller can tell a mistyped spec/dash/suffix apart from
    # a series table that came back empty or malformed.
    with pytest.raises(ValueError, match="38.999") as exc_info:
        threegpp.lookup_3gpp_spec_status(
            "38.999", fetch_fn=lambda url: _SERIES_TABLE_HTML.encode("utf-8")
        )

    assert isinstance(exc_info.value, threegpp.SpecNotFoundError)
    message = str(exc_info.value)
    assert "38.101" in message
    assert "38.101-1" in message


def test_lookup_reports_version_as_none_since_the_real_per_series_page_has_no_version_column():
    """Ticket #285's acceptance criteria ask for "the correct current version
    string for a non-withdrawn spec row" -- but the real per-series
    DynaReport table (fetched from the live page during this ticket's
    implementation) has exactly three columns -- spec number, title, notes
    -- confirmed by reading its own <thead>, and its notes column carries
    only two distinct values across all 272 rows of the real 38-series page:
    blank or "SPECIFICATION WITHDRAWN". A version number is never present.
    Fabricating a fourth "version" column in the fixture above so this test
    could show a version string would test a page shape 3GPP does not
    publish -- exactly the "silently apply the wrong tool" this repo's own
    CLAUDE.md warns against. `version` is therefore always `None` from this
    endpoint; see this module's docstring for where a real version number
    does live (the much heavier per-spec detail page) and why fetching it is
    out of scope here."""
    result = threegpp.lookup_3gpp_spec_status(
        "38.101-1", fetch_fn=lambda url: _SERIES_TABLE_HTML.encode("utf-8")
    )

    assert result["version"] is None


def test_parse_series_table_is_a_pure_function_no_fetch_needed():
    """`_parse_series_table` is the pure parsing half of the lookup -- the
    "caller fetches, this function only resolves" split `geometry/
    unit_cell.py`'s own docstring establishes for `designs.
    material_properties.resolve_material_property`'s fetch/resolve seam.
    Directly unit-testable with a plain string, no fetch_fn/monkeypatching
    required."""
    rows = threegpp._parse_series_table(_SERIES_TABLE_HTML)

    by_spec = {row["spec_number"]: row for row in rows}
    assert by_spec["38.101"]["withdrawn"] is True
    assert by_spec["38.101-1"]["withdrawn"] is False
    assert len(rows) == 6
