"""Issue #327 (ADR-0033): `knowledge.literature_search.
search_literature_for_capability_warning` -- the design loop's one narrow
literature-search tool for a Material-/Ink-property library miss that
already carries a Capability warning (issue #324).

`_CAPABILITY_WARNING` below mirrors the real shape `orchestration.
design_loop._validate_capability_warnings` enforces and
`tests/test_design_loop.py`'s own `_capability_warning_entry` fixture uses
-- `family` is the DESIGN family this warning is attached to (e.g.
"patch_antenna"), never a material/ink product name (no field on a real
Capability-warning entry carries one), which is why
`search_literature_for_capability_warning` takes `material_or_ink_name` as
its own explicit parameter rather than reading it off the entry.

Tested at the seam, mirroring tests/test_sourcing_arxiv.py's own style: both
`search_local` and `search_external` are injectable callables (default the
real `knowledge.search.search_knowledge` / `knowledge.sourcing.arxiv.
search_arxiv_papers`), stubbed here with plain call-recording fakes -- no
database, no network, matching this ticket's own acceptance criterion that
tests run against recorded/fake search responses, not live external calls.
"""

from __future__ import annotations

import pytest

from knowledge.literature_search import (
    UnsupportedCapabilityWarningError,
    search_literature_for_capability_warning,
)

_CAPABILITY_WARNING = {
    "family": "patch_antenna",
    "capability_kind": "material",
    "capability_property": "eps_r",
    "value": 4.0,
    "comparator": "AT_MOST",
    "unit": "unitless",
    "reason": "needs eps_r <= 4.0; no library entry exists for this material at all",
}

_MATERIAL_NAME = "MXene ink film"


class _Spy:
    """Minimal call-recording fake, matching tests/test_search.py's own
    `_Spy` -- records every call it receives and returns a canned result
    (or raises, to prove a branch that must not call it really doesn't)."""

    def __init__(self, result=None, raises=None):
        self.calls: list[tuple] = []
        self._result = result if result is not None else []
        self._raises = raises

    def __call__(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        if self._raises is not None:
            raise self._raises
        return self._result


def _local_row(**overrides):
    row = {
        "chunk_id": 1,
        "document_id": 42,
        "document_title": "X-band substrate dielectric survey",
        "content": "Measured eps_r = 3.9 at 10 GHz via coaxial probe.",
        "match_type": "lexical",
    }
    row.update(overrides)
    return row


def _arxiv_candidate(**overrides):
    candidate = {
        "id": "2401.01234v1",
        "title": "Printed conductive ink films for conformal antennas",
        "published": "2024-01-15",
        "abstract": "We report a volume resistivity of 5.2e-5 ohm-m after cure.",
    }
    candidate.update(overrides)
    return candidate


# --- input validation --------------------------------------------------


def test_rejects_fabrication_capability_kind_without_searching():
    fabrication_warning = dict(_CAPABILITY_WARNING, capability_kind="fabrication")
    must_not_search = AssertionError("must not search when capability_kind is unsupported")
    local_spy = _Spy(raises=must_not_search)
    external_spy = _Spy(raises=must_not_search)

    with pytest.raises(UnsupportedCapabilityWarningError, match="fabrication"):
        search_literature_for_capability_warning(
            fabrication_warning,
            _MATERIAL_NAME,
            search_local=local_spy,
            search_external=external_spy,
        )


def test_rejects_missing_required_field():
    incomplete = {"family": "patch_antenna", "capability_kind": "material"}
    with pytest.raises(UnsupportedCapabilityWarningError, match="capability_property"):
        search_literature_for_capability_warning(
            incomplete, _MATERIAL_NAME, search_local=_Spy(), search_external=_Spy()
        )


def test_rejects_blank_capability_property():
    blank = dict(_CAPABILITY_WARNING, capability_property="   ")
    with pytest.raises(UnsupportedCapabilityWarningError, match="capability_property"):
        search_literature_for_capability_warning(
            blank, _MATERIAL_NAME, search_local=_Spy(), search_external=_Spy()
        )


def test_rejects_blank_material_or_ink_name():
    with pytest.raises(UnsupportedCapabilityWarningError, match="material_or_ink_name"):
        search_literature_for_capability_warning(
            _CAPABILITY_WARNING, "   ", search_local=_Spy(), search_external=_Spy()
        )


def test_accepts_ink_capability_kind():
    ink_warning = dict(_CAPABILITY_WARNING, capability_kind="ink")
    result = search_literature_for_capability_warning(
        ink_warning, "Silver nanoparticle ink", search_local=_Spy(), search_external=_Spy()
    )
    assert result["capability_kind"] == "ink"


def test_ignores_family_field_entirely():
    """`family` names the DESIGN family (e.g. "patch_antenna"), never a
    material/ink product name -- confirmed against tests/test_design_loop.
    py's own `_capability_warning_entry` fixture. Two entries that differ
    only in `family` must search identically."""
    local_spy_a = _Spy()
    local_spy_b = _Spy()

    search_literature_for_capability_warning(
        dict(_CAPABILITY_WARNING, family="patch_antenna"),
        _MATERIAL_NAME,
        search_local=local_spy_a,
        search_external=_Spy(),
    )
    search_literature_for_capability_warning(
        dict(_CAPABILITY_WARNING, family="reflection_phase_surface"),
        _MATERIAL_NAME,
        search_local=local_spy_b,
        search_external=_Spy(),
    )

    assert local_spy_a.calls[0][0] == local_spy_b.calls[0][0]


# --- candidate surfacing -------------------------------------------------


def test_returns_local_candidate_with_title_identifier_and_excerpt():
    local_spy = _Spy(result=[_local_row()])
    result = search_literature_for_capability_warning(
        _CAPABILITY_WARNING, _MATERIAL_NAME, search_local=local_spy, search_external=_Spy()
    )

    assert result["found"] is True
    assert len(result["candidates"]) == 1
    candidate = result["candidates"][0]
    assert candidate["source"] == "local_knowledge"
    assert candidate["title"] == "X-band substrate dielectric survey"
    assert candidate["identifier"] == 42
    assert candidate["excerpt"] == "Measured eps_r = 3.9 at 10 GHz via coaxial probe."


def test_returns_external_candidate_with_title_identifier_and_excerpt():
    external_spy = _Spy(result=[_arxiv_candidate()])
    result = search_literature_for_capability_warning(
        _CAPABILITY_WARNING, _MATERIAL_NAME, search_local=_Spy(), search_external=external_spy
    )

    assert result["found"] is True
    assert len(result["candidates"]) == 1
    candidate = result["candidates"][0]
    assert candidate["source"] == "arxiv"
    assert candidate["title"] == "Printed conductive ink films for conformal antennas"
    assert candidate["identifier"] == "2401.01234v1"
    assert candidate["excerpt"] == "We report a volume resistivity of 5.2e-5 ohm-m after cure."


def test_local_candidates_are_ordered_before_external_candidates():
    local_spy = _Spy(result=[_local_row()])
    external_spy = _Spy(result=[_arxiv_candidate()])

    result = search_literature_for_capability_warning(
        _CAPABILITY_WARNING, _MATERIAL_NAME, search_local=local_spy, search_external=external_spy
    )

    sources = [c["source"] for c in result["candidates"]]
    assert sources == ["local_knowledge", "arxiv"]


def test_passes_material_name_and_property_into_the_search_query():
    local_spy = _Spy()
    external_spy = _Spy()

    search_literature_for_capability_warning(
        _CAPABILITY_WARNING, _MATERIAL_NAME, search_local=local_spy, search_external=external_spy
    )

    (local_args, _local_kwargs) = local_spy.calls[0]
    (external_args, _external_kwargs) = external_spy.calls[0]
    assert _MATERIAL_NAME in local_args[0]
    assert "eps_r" in local_args[0]
    assert _MATERIAL_NAME in external_args[0]
    assert "eps_r" in external_args[0]


def test_result_limits_are_threaded_through_to_each_search():
    local_spy = _Spy()
    external_spy = _Spy()

    search_literature_for_capability_warning(
        _CAPABILITY_WARNING,
        _MATERIAL_NAME,
        max_local_results=3,
        max_external_results=7,
        search_local=local_spy,
        search_external=external_spy,
    )

    assert local_spy.calls[0][1]["limit"] == 3
    assert external_spy.calls[0][1]["max_results"] == 7


# --- honest "nothing found" (AC2) ----------------------------------------


def test_found_false_and_plain_message_when_nothing_citable_exists():
    result = search_literature_for_capability_warning(
        _CAPABILITY_WARNING,
        _MATERIAL_NAME,
        search_local=_Spy(result=[]),
        search_external=_Spy(result=[]),
    )

    assert result["found"] is False
    assert result["candidates"] == []
    assert result["message"] is not None
    assert _MATERIAL_NAME in result["message"]
    assert "eps_r" in result["message"]


def test_message_is_none_when_something_is_found():
    result = search_literature_for_capability_warning(
        _CAPABILITY_WARNING,
        _MATERIAL_NAME,
        search_local=_Spy(result=[_local_row()]),
        search_external=_Spy(),
    )
    assert result["message"] is None


# --- AC3: never writes to the knowledge base or the property library -----


def test_never_calls_ingest_document(monkeypatch):
    """Enforces AC3: this tool never calls ingest_document, directly or
    indirectly -- mirrors tests/test_sourcing_arxiv.py's own
    test_search_arxiv_papers_never_calls_ingest_document guard."""
    import knowledge.ingest as ingest_module

    def fail_if_called(**kwargs):
        raise AssertionError(
            "search_literature_for_capability_warning must never call ingest_document"
        )

    monkeypatch.setattr(ingest_module, "ingest_document", fail_if_called)

    result = search_literature_for_capability_warning(
        _CAPABILITY_WARNING,
        _MATERIAL_NAME,
        search_local=_Spy(result=[_local_row()]),
        search_external=_Spy(result=[_arxiv_candidate()]),
    )

    # Sanity: the search itself ran and found results -- this isn't passing
    # merely because nothing happened.
    assert result["found"] is True
