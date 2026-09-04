"""Tests for orchestration/score_fields.py (issue #102).

This module is the single source of truth for the `(step, result_field,
unit)` triples that used to be written down twice, independently, in
`orchestration/solver.py`'s `_DEFAULT_SCORE_FIELDS` and `orchestration/
lab_test_plan.py`'s `_FIELD_SOURCES` -- see orchestration/score_fields.py's
own module docstring for why that duplication was incidental, not
structural, and issue #102's own body for how it was found (the Standards
axis of the code review on #87's branch).

Three things are checked here, deliberately:

  1. `SCORE_FIELD_SOURCES` itself carries exactly the three triples the
     ticket names, and nothing else -- a direct test of the shared table,
     so an accidental edit to a field name or unit here fails once, loudly,
     right at its source, per the ticket's own acceptance criteria ("A test
     covers the shared table directly, so a renamed field fails once and
     loudly rather than diverging silently").
  2. `orchestration.solver`'s own `_DEFAULT_SCORE_FIELDS` is *derived* from
     `SCORE_FIELD_SOURCES` -- not a second, independently-maintained copy.
  3. `orchestration.lab_test_plan`'s own `_FIELD_SOURCES` is likewise
     derived, preserving its existing grouping-by-quantity-kind shape (see
     that module's own "DESIGN QUESTION 2").

Together, (2) and (3) are the structural guard the old duplication lacked:
since both consumers' private lookups are built FROM this module's table
at import time, a future rename made only in `SCORE_FIELD_SOURCES` changes
both consumers' behaviour identically and automatically -- there is no
second copy left to go stale silently.
"""

from __future__ import annotations

import orchestration.lab_test_plan as lab_test_plan_module
import orchestration.solver as solver_module
from orchestration.design_loop import DesignStep
from orchestration.score_fields import SCORE_FIELD_SOURCES, ScoreFieldSource


def test_score_field_sources_is_exactly_the_three_named_triples():
    """Issue #102's own body names these three triples explicitly -- this
    is the direct test of the shared table itself."""
    assert set(SCORE_FIELD_SOURCES) == {
        ScoreFieldSource(DesignStep.ANALYSIS, "resonant_frequency_hz", "Hz"),
        ScoreFieldSource(DesignStep.SIMULATION, "gain_dbi", "dBi"),
        ScoreFieldSource(DesignStep.OPTIMIZATION, "achieved_frequency_hz", "Hz"),
    }
    assert len(SCORE_FIELD_SOURCES) == 3


def test_score_field_source_triple_is_step_field_unit_in_that_order():
    """`ScoreFieldSource` unpacks like the plain `(step, field, unit)`
    tuple both consumers used to spell out by hand -- callers that iterate
    `for step, field, unit in sources` (orchestration/lab_test_plan.py's
    `_find_expected`) keep working unchanged against the shared type."""
    source = ScoreFieldSource(DesignStep.SIMULATION, "gain_dbi", "dBi")
    step, field, unit = source
    assert step is DesignStep.SIMULATION
    assert field == "gain_dbi"
    assert unit == "dBi"


def test_solver_default_score_fields_is_derived_from_the_shared_table():
    """`orchestration.solver._DEFAULT_SCORE_FIELDS` must be built FROM
    `SCORE_FIELD_SOURCES`, not restated as its own literal dict -- proven
    by checking it holds exactly one entry per shared triple, with the
    identical field/unit pair."""
    expected = {source.step: (source.result_field, source.unit) for source in SCORE_FIELD_SOURCES}
    assert solver_module._DEFAULT_SCORE_FIELDS == expected


def test_lab_test_plan_field_sources_is_derived_from_the_shared_table():
    """`orchestration.lab_test_plan._FIELD_SOURCES`'s FREQUENCY/GAIN groups
    the SAME shared triples by quantity kind (via that module's own
    `_classify_unit`) -- every triple in the shared table must show up in
    exactly one of those groups, under the same field/unit pair, and the
    module's FREQUENCY/GAIN grouping shape (see that module's own "DESIGN
    QUESTION 2") must be unchanged.

    S_PARAMETER is a deliberate, documented EXCEPTION (issue #101), checked
    separately below: `SCORE_FIELD_SOURCES` gives each step exactly one
    default scoreable field, and SIMULATION's stays `gain_dbi` -- so
    `vswr`/`return_loss_db` are layered onto `_FIELD_SOURCES` afterward
    rather than folded into the shared table (see the code comment where
    `_FIELD_SOURCES[_S_PARAMETER]` is assigned)."""
    derived_sources = [
        source
        for kind, sources in lab_test_plan_module._FIELD_SOURCES.items()
        if kind != lab_test_plan_module._S_PARAMETER
        for source in sources
    ]
    assert len(derived_sources) == len(SCORE_FIELD_SOURCES)
    assert set(derived_sources) == set(SCORE_FIELD_SOURCES)

    # The specific grouping this module's docstring documents by name.
    assert set(lab_test_plan_module._FIELD_SOURCES["FREQUENCY"]) == {
        ScoreFieldSource(DesignStep.ANALYSIS, "resonant_frequency_hz", "Hz"),
        ScoreFieldSource(DesignStep.OPTIMIZATION, "achieved_frequency_hz", "Hz"),
    }
    assert lab_test_plan_module._FIELD_SOURCES["GAIN"] == [
        ScoreFieldSource(DesignStep.SIMULATION, "gain_dbi", "dBi"),
    ]

    # S_PARAMETER itself: NOT derived from SCORE_FIELD_SOURCES, verified as
    # its own, separately-asserted fact (issue #101).
    assert set(lab_test_plan_module._FIELD_SOURCES[lab_test_plan_module._S_PARAMETER]) == {
        ScoreFieldSource(DesignStep.SIMULATION, "vswr", "VSWR"),
        ScoreFieldSource(DesignStep.SIMULATION, "return_loss_db", "dB"),
    }


def test_solver_and_lab_test_plan_agree_on_every_shared_step():
    """Cross-module consistency, for the facts BOTH modules actually derive
    from the shared table (FREQUENCY/GAIN): for every step present in both
    derived lookups, the (field, unit) pair must be identical -- the exact
    divergence issue #102 says the old duplication risked (one copy
    updated, the other left behind, both suites still green).

    S_PARAMETER is deliberately excluded from this comparison -- see
    test_lab_test_plan_field_sources_is_derived_from_the_shared_table. It
    holds two additional SIMULATION facts (`vswr`, `return_loss_db`) that
    were never meant to agree with solver.py's one default per step
    (`gain_dbi`); collapsing all three into one `{step: (field, unit)}`
    dict here would silently keep only whichever happened to be last,
    hiding the other two rather than comparing anything meaningful."""
    lab_test_plan_by_step = {
        source.step: (source.result_field, source.unit)
        for kind, sources in lab_test_plan_module._FIELD_SOURCES.items()
        if kind != lab_test_plan_module._S_PARAMETER
        for source in sources
    }
    for step, (field, unit) in solver_module._DEFAULT_SCORE_FIELDS.items():
        assert lab_test_plan_by_step[step] == (field, unit)
