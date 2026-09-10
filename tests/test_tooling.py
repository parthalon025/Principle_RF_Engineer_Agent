# ruff: noqa: E501 -- see tests/test_design_loop.py's own header for why the
# NEC2 fixed-column sample output isn't reflowed.
"""Tests for orchestration/tooling.py's design-loop persistence (docs/adr/0011).

Needs a real Postgres via DATABASE_URL, unlike tests/test_design_loop.py's
pure-logic suite -- `orchestration.tooling.start_new_design_loop`/
`advance_design_loop_step` now call `designs.db`/`designs.service`
directly, each committing their own connection (not participating in a
`db_conn` fixture's rolled-back transaction), so this file follows
tests/test_designs_service.py's `cleanup_designs` convention instead:
track every `design_id` created and delete it (cascade-deleting its
decision_records/engineering_results/verification_items) afterward.

Reuses tests/test_design_loop.py's proven end-to-end step sequence (fake
NEC2++ executable, real approval receipts, a real Touchstone file for
MEASUREMENT) rather than re-deriving a new one -- duplicated, not
imported, matching this test suite's existing per-file convention.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import numpy as np
import psycopg
import pytest
import skrf as rf
from conftest import make_fake_executable
from dotenv import load_dotenv
from psycopg.types.json import Json

import designs.db as designs_db
from designs.db import get_connection, record_decision
from designs.requirement_targets import (
    confirm_requirement_target,
    propose_requirement_target,
    propose_target,
)
from designs.service import read_design
from orchestration.approval import request_loop_step_approval
from orchestration.design_loop import DesignLoopValidationError, DesignStep
from orchestration.solver import run_candidate_search
from orchestration.tooling import (
    DesignLoopPersistenceError,
    advance_design_loop_step,
    inspect_design_loop_state,
    reevaluate_capability_verdicts,
    reevaluate_capability_warnings,
    start_new_design_loop,
)
from rf_tools.calculations import patch_resonant_frequency_hz

load_dotenv()

REQUIREMENTS = {"R1": {"requirement": "gain >= 5 dBi over 2.4-2.5 GHz"}}

# Issue #322: a requirement stating a host curvature that VIOLATES
# S <= 2*theta_max*R for a 45-degree-stable element --
# arc_length_m=0.30 > 2*45deg*0.10 == ~0.157.
CURVATURE_REQUIREMENTS = {
    "R1": {
        "requirement": "conform to a 100 mm radius housing across a 300 mm bend",
        "curvature": {"arc_length_m": 0.30, "host_radius_m": 0.10},
    }
}


def _capability_verdict_entry(**overrides: Any) -> dict[str, Any]:
    """Duplicated from tests/test_design_loop.py's own helper of the same
    name, not imported -- matching this suite's own "duplicated, not
    imported" convention (this module's docstring)."""
    entry = {
        "family": "reflection_phase_surface",
        "verdict": "dropped",
        "reason": "host curvature exceeds this family's angle-stable element validity box",
        "reason_kind": "capability-verdict",
        "requirement_id": "R1",
        "validity_box_property": "curvature",
        "theta_max_deg": 45.0,
    }
    entry.update(overrides)
    return entry


def _capability_warning_entry(**overrides: Any) -> dict[str, Any]:
    """Duplicated from tests/test_design_loop.py's own helper of the same
    name, not imported -- see this module's docstring, "duplicated, not
    imported"."""
    entry = {
        "family": "patch_antenna",
        "capability_kind": "fabrication",
        "capability_property": "min_feature_size_mm",
        "value": 0.2,
        "comparator": "AT_MOST",
        "unit": "mm",
        "reason": "needs 0.2 mm features; loaded printer achieves 0.5 mm",
    }
    entry.update(overrides)
    return entry


@pytest.fixture
def cleanup_designs():
    """See this module's docstring -- mirrors tests/test_designs_service.py's
    fixture of the same name (duplicated, not imported, same convention)."""
    ids: list[int] = []
    yield ids
    if not ids:
        return
    conn = psycopg.connect(os.environ["DATABASE_URL"], autocommit=True)
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM designs WHERE id = ANY(%s)", (ids,))
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# start_new_design_loop: creates the backing designs row.
# ---------------------------------------------------------------------------


def test_start_new_design_loop_creates_a_draft_design_row(cleanup_designs):
    state = start_new_design_loop("TOOL-1", "Tooling Test Design", "A", REQUIREMENTS)
    cleanup_designs.append(state["design_id"])

    assert state["current_step"] == DesignStep.ARCHITECTURE.value
    assert state["persisted_decision_count"] == 0
    assert state["design_key"] == "TOOL-1"

    stored = read_design(state["design_id"])
    assert stored["design_key"] == "TOOL-1"
    assert stored["status"] == "DRAFT"
    assert stored["verification_items"][0]["requirement_id"] == "R1"
    assert stored["verification_items"][0]["status"] == "NOT VERIFIED"


def test_start_new_design_loop_rejects_bad_requirements_shape():
    # Old free-form "customer requirement" shape -- no longer accepted
    # (see orchestration/tooling.py's module docstring, "REQUIREMENTS
    # SHAPE"). Rejected before any database write, so nothing to clean up.
    with pytest.raises(DesignLoopPersistenceError):
        start_new_design_loop(
            "TOOL-BAD",
            "Bad Requirements Design",
            "A",
            {"band_ghz": [2.4, 2.5], "gain_dbi_min": 5.0},
        )


def test_advance_design_loop_step_requires_design_id_in_state():
    with pytest.raises(DesignLoopPersistenceError, match="design_id"):
        advance_design_loop_step({"loop_id": "x"}, {})


# ---------------------------------------------------------------------------
# engineering_results.tool_name for a MEASUREMENT decision (issue #89).
#
# Reaches for the private _tool_name_for rather than going through a flush,
# which is a deliberate exception to this suite's own "exercise the public
# dict-in/dict-out functions" habit: the only public path that reads a tool
# name is _flush_decisions, which commits to a real Postgres, and this
# environment has none (see the module docstring, and issue #97 for the
# absent CI that would).
# ---------------------------------------------------------------------------


def _engineering_decision(
    step: DesignStep,
    kind: str,
    result: dict[str, Any],
    provenance: str | None = None,
) -> Any:
    """One LoopDecision of an engineering-result kind (calculation/
    simulation/optimization/measurement/correlation), shaped exactly as
    `orchestration.design_loop.advance_loop_step` records it -- only
    `step`/`kind`/`result` matter to `_tool_name_for`, so the rest is
    filled with plausible constants."""
    from orchestration.design_loop import LoopDecision

    return LoopDecision(
        step=step.value,
        kind=kind,
        input={},
        result=result,
        provenance=provenance,
        approved_by="jane.engineer",
        recorded_at=0.0,
    )


def test_external_measurement_is_recorded_as_record_external_measurement():
    """A MEASUREMENT decision's evidence -- a Touchstone file an engineer
    measured elsewhere and carried back (ticket #90: the only MEASUREMENT
    path there is) -- is persisted under the real function name that
    produced it."""
    from orchestration.tooling import _tool_name_for

    decision = _engineering_decision(
        DesignStep.MEASUREMENT,
        "measurement",
        {
            "touchstone_file": "/tmp/dut.s2p",
            "provenance": "MEASURED",
            "source": "external_test_iteration",
        },
        provenance="MEASURED",
    )
    assert _tool_name_for(decision) == "record_external_measurement"


# ---------------------------------------------------------------------------
# Issue #334: engineering_results.tool_name must name the function that
# ACTUALLY ran, not whatever the step's name used to imply.
#
# ANALYSIS, SIMULATION and OPTIMIZATION each dispatch per design family
# (issues #239/#229/#241/#255): an ABSORBER's SIMULATION runs Meep, a
# PATCH's runs NEC2, and the flat `tool_name` column used to be filled from
# a fixed per-step table that said "run_nec2_simulation" for every one of
# them. In plain terms: every Meep and Palace run in the database was filed
# under the name of a solver that never touched it, so anything counting
# results per solver counted them all as NEC2.
#
# These reach for the private `_tool_name_for` for the same reason the
# MEASUREMENT test above does -- the only public path that reads a tool
# name is the flush, which needs a real Postgres. The end-to-end proof
# against a real database is
# test_flush_records_a_meep_run_under_its_own_tool_name below.
# ---------------------------------------------------------------------------


def test_a_meep_run_is_recorded_as_run_meep_simulation():
    """The defect this issue names: an ABSORBER's SIMULATION decision is
    the output of `run_meep_simulation` (design_loop.py's
    `_simulate_meep_floquet`), and must be filed under that name."""
    from orchestration.tooling import _tool_name_for

    decision = _engineering_decision(
        DesignStep.SIMULATION,
        "simulation",
        {
            "function": "run_meep_simulation",
            "simulator": "MEEP",
            "status": "COMPLETED",
            "worst_absorption": 0.8,
            "provenance": "SIMULATED",
        },
        provenance="SIMULATED",
    )
    assert _tool_name_for(decision) == "run_meep_simulation"


def test_a_palace_run_is_recorded_as_run_palace_simulation():
    """The same for REFLECTION_PHASE/DIFFUSIVE's declared solver (#252) --
    proving the fix reads the result rather than swapping one hardcoded
    solver name for another."""
    from orchestration.tooling import _tool_name_for

    decision = _engineering_decision(
        DesignStep.SIMULATION,
        "simulation",
        {
            "function": "run_palace_simulation",
            "simulator": "PALACE",
            "status": "COMPLETED",
            "provenance": "SIMULATED",
        },
        provenance="SIMULATED",
    )
    assert _tool_name_for(decision) == "run_palace_simulation"


def test_a_nec2_run_is_still_recorded_as_run_nec2_simulation():
    """The PATCH path, unchanged: what used to be right by accident (every
    SIMULATION was called NEC2) must still be right on purpose."""
    from orchestration.tooling import _tool_name_for

    decision = _engineering_decision(
        DesignStep.SIMULATION,
        "simulation",
        {
            "function": "run_nec2_simulation",
            "simulator": "NEC2++",
            "status": "COMPLETED",
            "vswr": 1.9,
            "provenance": "SIMULATED",
        },
        provenance="SIMULATED",
    )
    assert _tool_name_for(decision) == "run_nec2_simulation"


def test_an_absorber_analysis_is_recorded_as_absorber_band_response():
    """ANALYSIS has the same defect as SIMULATION (this issue's own scope
    check): it dispatches per family too (#239), so an ABSORBER's closed-
    form absorption was being filed under the patch-antenna resonant-
    frequency formula's name."""
    from orchestration.tooling import _tool_name_for

    decision = _engineering_decision(
        DesignStep.ANALYSIS,
        "calculation",
        {
            "function": "absorber_band_response",
            "worst_absorption": 0.62,
            "provenance": "CALCULATED",
        },
        provenance="CALCULATED",
    )
    assert _tool_name_for(decision) == "absorber_band_response"


def test_a_patch_analysis_is_still_recorded_as_patch_resonant_frequency_hz():
    from orchestration.tooling import _tool_name_for

    decision = _engineering_decision(
        DesignStep.ANALYSIS,
        "calculation",
        {
            "function": "patch_resonant_frequency_hz",
            "resonant_frequency_hz": 2.45e9,
            "provenance": "CALCULATED",
        },
        provenance="CALCULATED",
    )
    assert _tool_name_for(decision) == "patch_resonant_frequency_hz"


def test_a_combinatorial_optimization_is_recorded_as_its_own_search():
    """OPTIMIZATION dispatches per family too (#255/#267): a
    REFLECTION_PHASE/DIFFUSIVE family runs the combinatorial symbol-
    placement search, not the continuous patch-length one."""
    from orchestration.tooling import _tool_name_for

    decision = _engineering_decision(
        DesignStep.OPTIMIZATION,
        "optimization",
        {
            "function": "combinatorial_symbol_placement",
            "method": "combinatorial_symbol_placement",
            "achieved_error": 12.0,
            "provenance": "CALCULATED",
        },
        provenance="CALCULATED",
    )
    assert _tool_name_for(decision) == "combinatorial_symbol_placement"


def test_a_continuous_optimization_falls_back_to_the_step_table():
    """The continuous patch-length search states no `function` of its own
    (its `method` names the SEARCH -- "bayesian"/"sweep"/"grid" -- not the
    tool), so this step keeps its per-step table entry as the documented
    fallback."""
    from orchestration.tooling import _tool_name_for

    decision = _engineering_decision(
        DesignStep.OPTIMIZATION,
        "optimization",
        {
            "method": "parameter_sweep",
            "best_length_m": 0.0286,
            "provenance": "CALCULATED",
        },
        provenance="CALCULATED",
    )
    assert _tool_name_for(decision) == "optimize_patch_length_for_target_frequency"


def test_a_correlation_falls_back_to_the_step_table():
    from orchestration.tooling import _tool_name_for

    decision = _engineering_decision(
        DesignStep.CORRELATION,
        "correlation",
        {"comparison": {}, "provenance": "CALCULATED"},
        provenance="CALCULATED",
    )
    assert _tool_name_for(decision) == "correlate_simulation_measurement"


def test_a_simulation_naming_no_function_is_refused_not_filed_as_nec2():
    """A future solver wired into `_SIMULATION_ADAPTERS` without stating
    which function produced its result is a mapping gap, and this module
    already fails loud for those (`_flush_target_for`'s unknown-kind
    branch) rather than guessing. Guessing here is precisely the bug: the
    silent guess was "NEC2", and a wrong tool_name is unrecoverable once
    written, whereas this raise happens before the flush opens a
    connection, leaving the caller's pre-call state the only valid one.

    This shape is also what a SIMULATION decision recorded BEFORE this fix
    looks like -- a NEC2 run whose result never stated its function -- so
    the message must name the repair (add the key to the held state) rather
    than assume the historical answer and re-establish the guess."""
    from orchestration.tooling import DesignLoopPersistenceError, _tool_name_for

    decision = _engineering_decision(
        DesignStep.SIMULATION,
        "simulation",
        {"simulator": "SOME_NEW_SOLVER", "status": "COMPLETED"},
        provenance="SIMULATED",
    )
    with pytest.raises(DesignLoopPersistenceError, match="simulation"):
        _tool_name_for(decision)


# ---------------------------------------------------------------------------
# Issue #400: decision.input must not be silently dropped from a
# calculation/simulation/optimization/measurement/correlation decision's
# persisted engineering_results.value -- for every one of those five kinds,
# not just the combinatorial-optimization case the issue was filed against
# (a combinatorial OPTIMIZATION step's decision.input carries the exact
# symbol_entries/process_id/frequency_hz query that resolved each matched
# symbol_alphabet_entries row -- see optimization/combinatorial.py's
# SymbolOption.entry_id and CombinatorialPlacementResult.entry_id_layout
# for the other half of this same issue). Exercised as a pure unit test
# directly against the private _flush_target_for, the same "reach for the
# private function directly" precedent test_external_measurement_is_
# recorded_as_record_external_measurement above already sets for this
# module: _flush_target_for only BUILDS a _FlushTarget, it never executes
# designs_db.record_engineering_result against a real connection, so no
# database is needed either way.
# ---------------------------------------------------------------------------


def _engineering_result_decision(
    step: DesignStep, kind: str, step_input: dict[str, Any], result: dict[str, Any]
) -> Any:
    from orchestration.design_loop import LoopDecision

    return LoopDecision(
        step=step.value,
        kind=kind,
        input=step_input,
        result=result,
        provenance="CALCULATED",
        approved_by=None,
        recorded_at=0.0,
    )


@pytest.mark.parametrize(
    ("step", "kind"),
    [
        (DesignStep.ANALYSIS, "calculation"),
        (DesignStep.SIMULATION, "simulation"),
        (DesignStep.OPTIMIZATION, "optimization"),
        (DesignStep.MEASUREMENT, "measurement"),
        (DesignStep.CORRELATION, "correlation"),
    ],
)
def test_flush_target_for_folds_decision_input_into_engineering_result_value(step, kind):
    """Before this fix, _flush_target_for's ENGINEERING_RESULT_KINDS branch
    persisted only decision.result -- decision.input was silently dropped
    at the flush boundary, for every one of these five decision kinds."""
    from orchestration.tooling import _flush_target_for

    decision = _engineering_result_decision(
        step,
        kind,
        step_input={"process_id": 7, "note": "resolved against real inputs"},
        # Issue #334 (merged after this test was written): ANALYSIS and
        # SIMULATION dispatch per design family and no longer fall back to
        # a per-step table name, so a decision of either kind must state
        # which function actually ran. The value itself is irrelevant to
        # what this test checks (decision.input riding along); it only
        # needs to be present so _tool_name_for doesn't raise.
        result={"achieved_value": 42.0, "function": f"{kind}_function"},
    )

    target = _flush_target_for(
        decision,
        design_id=1,
        design_key="X",
        loop_id="loop-1",
        iteration=1,
        design_family=None,
        design_family_canonical=None,
    )

    assert target is not None
    value = target.kwargs["value"]
    # The result's own field(s) must still be reachable at the TOP level --
    # orchestration/solver.py's _prior_best_from_design reads a persisted
    # row's value this way for ANALYSIS/SIMULATION/OPTIMIZATION, and this
    # shape must not silently move underneath it.
    assert value["achieved_value"] == 42.0
    # ... and decision.input, previously dropped entirely, now rides along.
    assert value["input"] == {"process_id": 7, "note": "resolved against real inputs"}


def test_flush_target_for_engineering_result_value_keeps_the_scored_field_readable():
    """A more pointed version of the "top-level, not nested" guarantee
    above, against ANALYSIS's real scored field name
    (orchestration/score_fields.py's own `resonant_frequency_hz`/Hz entry):
    proves the field orchestration.solver._score_step/_prior_best_from_
    design reads is still directly readable on the flushed value after
    decision.input is folded in -- i.e. that folding it in never shadows
    the field actually being scored."""
    from orchestration.tooling import _flush_target_for

    decision = _engineering_result_decision(
        DesignStep.ANALYSIS,
        "calculation",
        step_input={"target_frequency_hz": 2.45e9},
        # "function" required since issue #334 (merged after this test was
        # written): ANALYSIS dispatches per design family and no longer
        # falls back to a per-step table name.
        result={"resonant_frequency_hz": 2.451e9, "function": "patch_resonant_frequency_hz"},
    )

    target = _flush_target_for(
        decision,
        design_id=1,
        design_key="X",
        loop_id="loop-1",
        iteration=1,
        design_family=None,
        design_family_canonical=None,
    )

    value = target.kwargs["value"]
    assert value["resonant_frequency_hz"] == pytest.approx(2.451e9)
    assert value["input"]["target_frequency_hz"] == pytest.approx(2.45e9)


def test_inspect_design_loop_state_passes_through_design_fields(cleanup_designs):
    state = start_new_design_loop("TOOL-2", "Inspect Test", "A", REQUIREMENTS)
    cleanup_designs.append(state["design_id"])

    inspected = inspect_design_loop_state(state)
    assert inspected["design_id"] == state["design_id"]
    assert inspected["design_key"] == "TOOL-2"
    assert inspected["persisted_decision_count"] == 0


# ---------------------------------------------------------------------------
# Issue #100: a loop's carried `requirements` must reflect a requirement
# target proposed/confirmed after the loop started, not the frozen snapshot
# `start_design_loop` recorded once and orchestration/design_loop.py never
# updates again.
# ---------------------------------------------------------------------------


def test_inspect_design_loop_state_reflects_a_target_confirmed_after_start(cleanup_designs):
    """The exact stale case issue #100 names: start a loop, confirm a
    target (a write straight to the persisted `designs.requirements`
    column via designs.requirement_targets -- a completely different path
    than anything orchestration.tooling touches directly), then read the
    loop's own state back -- with no advance_design_loop_step call in
    between -- and see the confirmed target, not the empty snapshot from
    start time."""
    state = start_new_design_loop("TOOL-FRESH-1", "Fresh Requirements Test", "A", REQUIREMENTS)
    cleanup_designs.append(state["design_id"])
    design_id = state["design_id"]

    assert "target" not in state["requirements"]["R1"]

    propose_result = propose_requirement_target(
        design_id=design_id,
        requirement_id="R1",
        value=5.0,
        comparator="AT_LEAST",
        unit="dBi",
    )
    assert propose_result["status"] == "proposed"
    confirm_result = confirm_requirement_target(
        design_id=design_id, requirement_id="R1", confirmed_by="jane.engineer"
    )
    assert confirm_result["status"] == "confirmed"

    # `state` itself was captured BEFORE either of those calls -- this is
    # the exact caller pattern the issue describes: holding a loop-state
    # dict from before a target was confirmed, then reading it later.
    inspected = inspect_design_loop_state(state)
    target = inspected["requirements"]["R1"]["target"]
    assert target["target_status"] == "CONFIRMED"
    assert target["value"] == 5.0
    assert target["confirmed_by"] == "jane.engineer"


def test_advance_design_loop_step_reflects_a_target_confirmed_after_start(cleanup_designs):
    """Same staleness fix, exercised through advance_design_loop_step
    instead of inspect_design_loop_state -- and checks the REQUIREMENTS
    decision itself is untouched (issue #100 acceptance criteria: "the
    record of what the customer first said is not overwritten by later
    interpretation")."""
    state = start_new_design_loop("TOOL-FRESH-2", "Fresh Requirements Test 2", "A", REQUIREMENTS)
    cleanup_designs.append(state["design_id"])
    design_id = state["design_id"]

    propose_requirement_target(
        design_id=design_id,
        requirement_id="R1",
        value=5.0,
        comparator="AT_LEAST",
        unit="dBi",
    )
    confirm_requirement_target(
        design_id=design_id, requirement_id="R1", confirmed_by="jane.engineer"
    )

    state = _grant_and_advance(
        state,
        DesignStep.ARCHITECTURE,
        {
            "decision": "rectangular microstrip patch on FR4",
            "rationale": "meets band/gain target with a simple, low-cost fabrication",
            "design_family": "patch_antenna",
        },
    )

    target = state["requirements"]["R1"]["target"]
    assert target["target_status"] == "CONFIRMED"
    assert target["confirmed_by"] == "jane.engineer"

    # The REQUIREMENTS decision (decisions[0]) still shows exactly what was
    # originally stated at loop start -- the confirmed target must not leak
    # into it.
    requirements_decision = state["decisions"][0]
    assert requirements_decision["step"] == DesignStep.REQUIREMENTS.value
    assert "target" not in requirements_decision["result"]["R1"]
    assert "target" not in requirements_decision["input"]["R1"]


# ---------------------------------------------------------------------------
# Shared end-to-end driver -- same real step sequence as
# tests/test_design_loop.py's test_end_to_end_full_requirements_to_redesign_cycle,
# driven through orchestration.tooling's dict-in/dict-out functions instead
# of the pure advance_loop_step, up to (not including) the REDESIGN_DECISION
# call -- callers supply their own next_action ("iterate"/"accept_design")
# so this one driver serves both flush-boundary tests below.
# ---------------------------------------------------------------------------

_GUIDE_SAMPLE_OUTPUT = """
                                          - - - ANTENNA INPUT PARAMETERS - - -
   TAG   SEG.    VOLTAGE (VOLTS)         CURRENT (AMPS)         IMPEDANCE (OHMS)        ADMITTANCE (MHOS)      POWER
   NO.   NO.    REAL        IMAG.       REAL        IMAG.       REAL        IMAG.       REAL        IMAG.     (WATTS)
     0     4 1.00000E+00 0.00000E+00 9.20585E-03-5.15474E-03 8.26979E+01 4.63060E+01 9.20585E-03-5.15474E-03 4.60292E-03
"""

_DIPOLE_GEOMETRY = {
    "wires": [
        {
            "tag": 1,
            "segments": 7,
            "x1_m": 0.0,
            "y1_m": 0.0,
            "z1_m": -0.25,
            "x2_m": 0.0,
            "y2_m": 0.0,
            "z2_m": 0.25,
            "radius_m": 0.001,
        }
    ]
}

_FAKE_NEC2PP_PY = '''
import sys

OUTPUT = """{sample}"""

args = sys.argv[1:]
assert "-i" in args, args
sys.stdout.write(OUTPUT)
sys.exit(0)
'''


def _make_fake_nec2pp(tmp_path: Path) -> Path:
    body = _FAKE_NEC2PP_PY.format(sample=_GUIDE_SAMPLE_OUTPUT)
    return make_fake_executable(tmp_path, body, name="fake_nec2pp")


def _write_measured_touchstone(tmp_path: Path, name: str = "measured") -> Path:
    """A real one-port Touchstone file for the MEASUREMENT step -- same
    construction as tests/test_design_loop.py's own helper of the same
    name (duplicated, not imported, matching this suite's per-file
    convention). One-port (S11 only) to match this file's own CORRELATION
    `simulated_override` shape."""
    freqs_hz = [2.0e9, 2.5e9, 3.0e9]
    f = rf.Frequency.from_f(freqs_hz, unit="hz")
    s = np.zeros((3, 1, 1), dtype=complex)
    s[:, 0, 0] = 10 ** (-15 / 20)
    ntwk = rf.Network(frequency=f, s=s, z0=50)
    path = tmp_path / f"{name}.s1p"
    ntwk.write_touchstone(path.with_suffix(""))
    return path


def _fingerprint(state: dict[str, Any], step: DesignStep, step_input: dict) -> dict:
    return {
        "loop_id": state["loop_id"],
        "iteration": state["iteration"],
        "step": step.value,
        "content": step_input,
    }


def _grant_and_advance(state: dict[str, Any], step: DesignStep, step_input: dict) -> dict:
    """`requirements_document_status="CONFIRMED"` (issue #325, docs/adr/0031)
    is passed unconditionally, the same way `approval` already is -- a
    no-op for every step but ARCHITECTURE, the only one
    advance_design_loop_step reads it for, and keeps every ARCHITECTURE-
    advancing call in this file that goes through this helper working now
    that ARCHITECTURE also gates on it."""
    fields = _fingerprint(state, step, step_input)
    receipt = request_loop_step_approval(
        fields, approved_by="jane.engineer", approval_callback=lambda f: True
    )
    return advance_design_loop_step(
        state,
        step_input,
        approval=receipt.to_dict(),
        requirements_document_status="CONFIRMED",
    )


def _drive_to_redesign_decision(
    state: dict[str, Any],
    tmp_path: Path,
    verification_status: str = "PASS",
    design_family: str = "patch_antenna",
    considered_and_dropped: list[dict[str, Any]] | None = None,
    capability_warnings: list[dict[str, Any]] | None = None,
    analysis_input: dict[str, Any] | None = None,
    simulation_input: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Real ARCHITECTURE -> ... -> CORRELATION, leaving `state` positioned
    at REDESIGN_DECISION -- callers advance the final gated step themselves
    with whatever next_action they're testing. `verification_status` lets
    callers exercise design_loop.py's wider VERIFICATION_STATUSES
    vocabulary (CONDITIONAL PASS/BLOCKED, not just designs.models.
    VerificationStatus's own PASS/FAIL/MARGINAL/NOT VERIFIED). `design_family`
    (issue #167) lets a caller drive two iterations with two DIFFERENT
    families, to prove the ADR-0011 flush's design_family carry-forward is
    scoped to each iteration's own flush batch, not a stale value left over
    from a previous one. `considered_and_dropped` (issue #322) lets a caller
    attach a Considered-and-dropped ledger to this iteration's ARCHITECTURE
    decision -- omitted entirely (not `[]`) when the caller supplies none,
    matching `alternatives`'s own `.get(..., [])`-default convention rather
    than asserting an empty list is what every caller wants. `capability_warnings`
    (issue #324) does the same for a Capability warning list -- a wholly
    separate key from `considered_and_dropped` above, so both can be
    supplied together without either affecting the other.

    `analysis_input`/`simulation_input` (issue #334) let a caller drive a
    family whose ANALYSIS and SIMULATION are not the patch antenna's --
    ABSORBER's closed-form absorption and its Meep unit-cell run, say.
    Omitted, both default to the patch-antenna inputs every other test in
    this file already drives (including the fake NEC2++ executable, which
    is only created when the caller supplies no `simulation_input` of its
    own -- a Meep-driven iteration has no NEC2 binary to fake)."""
    architecture_input = {
        "decision": "rectangular microstrip patch on FR4",
        "rationale": "meets band/gain target with a simple, low-cost fabrication",
        "design_family": design_family,
    }
    if considered_and_dropped is not None:
        architecture_input["considered_and_dropped"] = considered_and_dropped
    if capability_warnings is not None:
        architecture_input["capability_warnings"] = capability_warnings
    state = _grant_and_advance(state, DesignStep.ARCHITECTURE, architecture_input)
    state = advance_design_loop_step(
        state, analysis_input or {"eps_r": 4.4, "w_m": 0.03, "h_m": 0.0016, "l_m": 0.0286}
    )
    if simulation_input is None:
        fake_nec2pp = _make_fake_nec2pp(tmp_path)
        simulation_input = {
            "geometry": _DIPOLE_GEOMETRY,
            "frequency_hz": 300e6,
            "reference_impedance_ohms": 50.0,
            "executable": str(fake_nec2pp),
            "workdir": str(tmp_path / "nec2_run"),
        }
    state = advance_design_loop_step(state, simulation_input)
    state = advance_design_loop_step(
        state,
        {
            "eps_r": 4.4,
            "w_m": 0.03,
            "h_m": 0.0016,
            "target_frequency_hz": 2.45e9,
            "length_lower_m": 0.02,
            "length_upper_m": 0.04,
            "method": "sweep",
            "n_evaluations": 5,
        },
    )
    state = advance_design_loop_step(
        state,
        {
            "requirement_id": "R1",
            "requirement": "gain >= 5 dBi over 2.4-2.5 GHz",
            "method": "analysis",
            "expected": 5.0,
            "actual": 5.2,
            "status": verification_status,
        },
    )
    # A real Touchstone file brought back from external testing (ticket
    # #90: the only MEASUREMENT path there is). The LOOP's own separate
    # MEASUREMENT gate (a real LoopStepApprovalReceipt) is still enforced
    # by _grant_and_advance below, same as every other GATED_STEPS member.
    touchstone_path = _write_measured_touchstone(
        tmp_path, name=f"tooling-{state['design_key']}-iter{state['iteration']}"
    )
    measurement_input = {"touchstone_file": str(touchstone_path)}
    state = _grant_and_advance(state, DesignStep.MEASUREMENT, measurement_input)
    simulated_override = {
        "frequency_hz": [2.0e9, 2.5e9, 3.0e9],
        "s_parameters": {"S11": ["0.1+0.01j", "0.2+0.02j", "0.3+0.03j"]},
        "z0": 50.0,
    }
    state = advance_design_loop_step(state, {"simulated": simulated_override})
    assert state["current_step"] == DesignStep.REDESIGN_DECISION.value
    return state


# ---------------------------------------------------------------------------
# Flush at accept_design (ticket 4).
# ---------------------------------------------------------------------------


def test_flush_at_accept_design_persists_full_history(cleanup_designs, tmp_path):
    state = start_new_design_loop("TOOL-ACCEPT", "Accept Flush Test", "A", REQUIREMENTS)
    cleanup_designs.append(state["design_id"])
    design_id = state["design_id"]

    state = _drive_to_redesign_decision(state, tmp_path)
    redesign_input = {
        "decision": "accept the design as-is",
        "rationale": "measured and correlated results meet the customer requirement",
        "next_action": "accept_design",
    }
    state = _grant_and_advance(state, DesignStep.REDESIGN_DECISION, redesign_input)

    assert state["completed"] is True
    assert state["persisted_decision_count"] == len(state["decisions"])

    stored = read_design(design_id)
    assert stored["status"] == "PASS"

    decision_records = {d["record_key"].rsplit("-", 1)[-1]: d for d in stored["decision_records"]}
    assert set(decision_records) == {"architecture", "redesign_decision"}
    assert decision_records["architecture"]["decision"] == "rectangular microstrip patch on FR4"
    assert decision_records["redesign_decision"]["decision"] == "accept the design as-is"
    # Issue #167: design_family survives the flush on BOTH rows. The
    # REDESIGN_DECISION step_input above never states a design_family of
    # its own (design_loop.py's _handle_redesign_decision doesn't ask for
    # one) -- its persisted row carries forward this iteration's own
    # ARCHITECTURE decision's family rather than persisting NULL (this
    # module's own "DESIGN_FAMILY CARRY-FORWARD" decision).
    assert decision_records["architecture"]["design_family"] == "patch_antenna"
    assert decision_records["redesign_decision"]["design_family"] == "patch_antenna"

    results_by_tool = {r["tool_name"]: r for r in stored["engineering_results"]}
    assert set(results_by_tool) == {
        "patch_resonant_frequency_hz",
        "run_nec2_simulation",
        "optimize_patch_length_for_target_frequency",
        "record_external_measurement",
        "correlate_simulation_measurement",
    }
    assert results_by_tool["patch_resonant_frequency_hz"]["provenance"] == "CALCULATED"
    assert results_by_tool["run_nec2_simulation"]["provenance"] == "SIMULATED"
    assert results_by_tool["record_external_measurement"]["provenance"] == "MEASURED"


# ---------------------------------------------------------------------------
# Issue #334, end to end against a real database: an ABSORBER iteration --
# closed-form absorption for ANALYSIS, a Meep unit-cell run for SIMULATION --
# must land in engineering_results under the names of the functions that
# actually ran. The unit-level counterpart is the _tool_name_for block near
# the top of this file.
# ---------------------------------------------------------------------------

# Duplicated from tests/test_design_loop.py's constant of the same name, not
# imported -- this file's own "duplicated, not imported" convention (module
# docstring).
_ABSORBER_ANALYSIS_INPUT = {
    "f_low_hz": 8e9,
    "f_high_hz": 12e9,
    "eps_r": 2.9,
    "tan_delta": 0.10,
    "thickness_m": 2.0e-3,
    "period_m": 3.0e-3,
    "gap_m": 0.2e-3,
    "sheet_resistance_ohm_sq": 500.0,
    "squares": 0.1,
}


def _fake_meep_run(geometry, characteristic_length_m, nfreq, workdir):
    """Stands in for `simulation.meep.run_meep_simulation`, whose real run
    needs a Meep install this suite does not assume -- the same
    monkeypatched-adapter approach tests/test_design_loop.py's own ABSORBER
    dispatch tests take. What is under test here is which NAME the run is
    filed under, not the solver's numbers."""
    del geometry, characteristic_length_m, nfreq, workdir
    return {
        "provenance": "SIMULATED",
        "simulator": "MEEP",
        "status": "COMPLETED",
        "s_parameters": {"frequency_hz": [9e9, 10e9], "reflectance": [0.2, 0.01]},
    }


def test_flush_records_a_meep_run_under_its_own_tool_name(cleanup_designs, tmp_path, monkeypatch):
    """The consequence issue #334 names, proved against a real Postgres:
    group `engineering_results` by `tool_name` after an ABSORBER iteration
    and the Meep run must appear as `run_meep_simulation`. Before the fix
    this whole design's five rows claimed a NEC2 run and a patch-antenna
    resonance calculation, neither of which happened -- in plain terms, the
    filing cabinet named a different instrument than the one that took the
    reading."""
    import orchestration.design_loop as design_loop_module

    monkeypatch.setattr(design_loop_module, "_run_meep_simulation", _fake_meep_run)

    state = start_new_design_loop("TOOL-MEEP", "Absorber Flush Test", "A", REQUIREMENTS)
    design_id = state["design_id"]
    cleanup_designs.append(design_id)

    state = _drive_to_redesign_decision(
        state,
        tmp_path,
        design_family="ABSORBER",
        analysis_input=dict(_ABSORBER_ANALYSIS_INPUT),
        simulation_input={
            "geometry": {"cell_size_m": [3e-3, 3e-3, 40e-3]},
            "frequency_hz": 10e9,
        },
    )
    state = _grant_and_advance(
        state,
        DesignStep.REDESIGN_DECISION,
        {
            "decision": "accept the absorber as-is",
            "rationale": "worst-in-band absorption meets the requirement",
            "next_action": "accept_design",
        },
    )
    assert state["completed"] is True

    stored = read_design(design_id)
    results_by_tool = {r["tool_name"]: r for r in stored["engineering_results"]}
    assert set(results_by_tool) == {
        "absorber_band_response",
        "run_meep_simulation",
        "optimize_patch_length_for_target_frequency",
        "record_external_measurement",
        "correlate_simulation_measurement",
    }
    # The row's own value already carried the truth (this issue's "where the
    # real value already lives"); the flat column must now agree with it.
    assert results_by_tool["run_meep_simulation"]["value"]["function"] == "run_meep_simulation"
    assert results_by_tool["run_meep_simulation"]["value"]["simulator"] == "MEEP"
    assert results_by_tool["run_meep_simulation"]["provenance"] == "SIMULATED"
    assert results_by_tool["absorber_band_response"]["provenance"] == "CALCULATED"


# ---------------------------------------------------------------------------
# Issue #205: a decision's `alternatives` must survive the flush, not be
# discarded as a hardcoded `[]`.
# ---------------------------------------------------------------------------


def test_flush_persists_alternatives_the_caller_supplied(cleanup_designs, tmp_path):
    """Prerequisite for ADR-0026 (#125): a rejected alternative is worthless
    to a later human review if `_flush_target_for` throws it away at the
    flush. Drives ARCHITECTURE with a real `alternatives` list and asserts
    the persisted `decision_records` row carries it through verbatim --
    the regression this issue asks for. `redesign_decision`'s own step_input
    supplies no `alternatives` key at all here, proving the `.get(...,
    [])` default (not a `KeyError`) is what a caller who legitimately
    offers none gets back."""
    state = start_new_design_loop("TOOL-ALTS", "Alternatives Flush Test", "A", REQUIREMENTS)
    design_id = state["design_id"]
    cleanup_designs.append(design_id)

    architecture_alternatives = [
        {"decision": "printed dipole", "rejected_because": "narrowband vs. requirement"},
        {"decision": "PIFA", "rejected_because": "host surface curvature too tight"},
    ]
    state = _grant_and_advance(
        state,
        DesignStep.ARCHITECTURE,
        {
            "decision": "rectangular microstrip patch on FR4",
            "rationale": "meets band/gain target with a simple, low-cost fabrication",
            "design_family": "patch_antenna",
            "alternatives": architecture_alternatives,
        },
    )
    state = advance_design_loop_step(
        state, {"eps_r": 4.4, "w_m": 0.03, "h_m": 0.0016, "l_m": 0.0286}
    )
    fake_nec2pp = _make_fake_nec2pp(tmp_path)
    state = advance_design_loop_step(
        state,
        {
            "geometry": _DIPOLE_GEOMETRY,
            "frequency_hz": 300e6,
            "reference_impedance_ohms": 50.0,
            "executable": str(fake_nec2pp),
            "workdir": str(tmp_path / "nec2_run"),
        },
    )
    state = advance_design_loop_step(
        state,
        {
            "eps_r": 4.4,
            "w_m": 0.03,
            "h_m": 0.0016,
            "target_frequency_hz": 2.45e9,
            "length_lower_m": 0.02,
            "length_upper_m": 0.04,
            "method": "sweep",
            "n_evaluations": 5,
        },
    )
    state = advance_design_loop_step(
        state,
        {
            "requirement_id": "R1",
            "requirement": "gain >= 5 dBi over 2.4-2.5 GHz",
            "method": "analysis",
            "expected": 5.0,
            "actual": 5.2,
            "status": "PASS",
        },
    )
    touchstone_path = _write_measured_touchstone(tmp_path, name="tooling-alts")
    state = _grant_and_advance(
        state, DesignStep.MEASUREMENT, {"touchstone_file": str(touchstone_path)}
    )
    simulated_override = {
        "frequency_hz": [2.0e9, 2.5e9, 3.0e9],
        "s_parameters": {"S11": ["0.1+0.01j", "0.2+0.02j", "0.3+0.03j"]},
        "z0": 50.0,
    }
    state = advance_design_loop_step(state, {"simulated": simulated_override})
    assert state["current_step"] == DesignStep.REDESIGN_DECISION.value

    redesign_input = {
        "decision": "accept the design as-is",
        "rationale": "measured and correlated results meet the customer requirement",
        "next_action": "accept_design",
        # deliberately no "alternatives" key -- proves the .get(..., [])
        # default, not a KeyError, is what a caller supplying none gets.
    }
    state = _grant_and_advance(state, DesignStep.REDESIGN_DECISION, redesign_input)
    assert state["completed"] is True

    stored = read_design(design_id)
    decision_records = {d["record_key"].rsplit("-", 1)[-1]: d for d in stored["decision_records"]}
    assert decision_records["architecture"]["alternatives"] == architecture_alternatives
    assert decision_records["redesign_decision"]["alternatives"] == []

    assert stored["verification_items"][0]["status"] == "PASS"
    assert stored["verification_items"][0]["method"] == "analysis"


# ---------------------------------------------------------------------------
# Issue #322: the Considered-and-dropped ledger's `considered_and_dropped`
# key must survive the ADR-0011 flush, and a persisted
# `reason_kind="capability-verdict"` entry must be re-evaluatable against
# this design's CURRENT stated requirements -- never against configured
# shop equipment.
# ---------------------------------------------------------------------------


def test_flush_persists_a_capability_verdict_ledger_entry(cleanup_designs, tmp_path):
    """Acceptance criterion 4: the persisted ledger entry shape after a
    flush -- a validity-box exclusion lands verbatim on the ARCHITECTURE
    decision_records row, alongside a kept engineering-judgment entry for
    the family actually chosen."""
    state = start_new_design_loop(
        "TOOL-LEDGER", "Capability Verdict Ledger Test", "A", CURVATURE_REQUIREMENTS
    )
    design_id = state["design_id"]
    cleanup_designs.append(design_id)

    ledger = [
        _capability_verdict_entry(),
        {
            "family": "patch_antenna",
            "verdict": "kept",
            "reason": "the only family whose curvature validity box the host survives",
            "reason_kind": "engineering-judgment",
        },
    ]
    state = _drive_to_redesign_decision(state, tmp_path, considered_and_dropped=ledger)
    redesign_input = {
        "decision": "accept the design as-is",
        "rationale": "measured and correlated results meet the customer requirement",
        "next_action": "accept_design",
    }
    state = _grant_and_advance(state, DesignStep.REDESIGN_DECISION, redesign_input)
    assert state["completed"] is True

    stored = read_design(design_id)
    decision_records = {d["record_key"].rsplit("-", 1)[-1]: d for d in stored["decision_records"]}
    assert decision_records["architecture"]["considered_and_dropped"] == ledger
    # Nothing on REDESIGN_DECISION's own step_input stated a ledger --
    # matching alternatives's own `.get(..., [])` default, not the
    # ARCHITECTURE row's design_family carry-forward (this key never
    # carries forward across decisions).
    assert decision_records["redesign_decision"]["considered_and_dropped"] == []


def test_advance_design_loop_step_rejects_a_capability_verdict_that_does_not_violate_the_bound(
    cleanup_designs,
):
    """The issue #322 narrowing is enforced through the SAME tooling.py
    entry point an agent/MCP caller actually uses, not only through
    orchestration.design_loop's own pure state machine (already covered
    exhaustively in tests/test_design_loop.py) -- nothing here reaches the
    database, since the raise happens before any flush."""
    comfortable_requirements = {
        "R1": {
            "requirement": "conform to a 500 mm radius housing across a 100 mm bend",
            "curvature": {"arc_length_m": 0.10, "host_radius_m": 0.50},
        }
    }
    state = start_new_design_loop(
        "TOOL-LEDGER-REJECT", "Capability Verdict Rejection Test", "A", comfortable_requirements
    )
    cleanup_designs.append(state["design_id"])
    architecture_input = {
        "decision": "rectangular microstrip patch on FR4",
        "rationale": "meets band/gain target with a simple, low-cost fabrication",
        "design_family": "patch_antenna",
        "considered_and_dropped": [_capability_verdict_entry()],
    }
    with pytest.raises(DesignLoopValidationError, match="does not actually violate"):
        _grant_and_advance(state, DesignStep.ARCHITECTURE, architecture_input)


def test_reevaluate_capability_verdicts_flips_to_reconsiderable_when_curvature_changes(
    cleanup_designs, tmp_path
):
    """Acceptance criterion 2: re-evaluated every run against the
    requirement's own CURRENT stated properties, never a frozen snapshot --
    and never against shop equipment, which this test never touches."""
    state = start_new_design_loop(
        "TOOL-LEDGER-REEVAL", "Capability Verdict Reevaluation Test", "A", CURVATURE_REQUIREMENTS
    )
    design_id = state["design_id"]
    cleanup_designs.append(design_id)

    state = _drive_to_redesign_decision(
        state, tmp_path, considered_and_dropped=[_capability_verdict_entry()]
    )
    redesign_input = {
        "decision": "accept the design as-is",
        "rationale": "measured and correlated results meet the customer requirement",
        "next_action": "accept_design",
    }
    _grant_and_advance(state, DesignStep.REDESIGN_DECISION, redesign_input)

    still_violating = reevaluate_capability_verdicts(design_id)
    assert still_violating == [
        {
            "record_key": f"TOOL-LEDGER-REEVAL-{state['loop_id']}-iter1-architecture",
            "family": "reflection_phase_surface",
            "requirement_id": "R1",
            "validity_box_property": "curvature",
            "status": "excluded",
        }
    ]

    # The requirement's OWN stated curvature changes -- not any equipment
    # configuration -- via the exact raw-SQL-sabotage pattern this suite
    # already uses (test_flush_failure_is_atomic_and_leaves_design_status_
    # untouched) to simulate a fact this ticket adds no production write
    # path for yet.
    conn = psycopg.connect(os.environ["DATABASE_URL"])
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE designs SET requirements = %s WHERE id = %s",
                (
                    Json(
                        {
                            "R1": {
                                "requirement": (
                                    "conform to a 100 mm radius housing across a 300 mm bend"
                                ),
                                "curvature": {"arc_length_m": 0.05, "host_radius_m": 0.10},
                            }
                        }
                    ),
                    design_id,
                ),
            )
        conn.commit()
    finally:
        conn.close()

    now_reconsiderable = reevaluate_capability_verdicts(design_id)
    assert now_reconsiderable[0]["status"] == "reconsiderable"
    assert now_reconsiderable[0]["family"] == "reflection_phase_surface"


def test_reevaluate_capability_verdicts_skips_non_capability_verdict_entries(
    cleanup_designs, tmp_path
):
    """Only reason_kind='capability-verdict' entries are ever subject to
    re-evaluation (ADR-0025) -- a kept engineering-judgment entry for the
    chosen family is never reported as excluded/reconsiderable."""
    state = start_new_design_loop(
        "TOOL-LEDGER-SKIP", "Capability Verdict Skip Test", "A", REQUIREMENTS
    )
    design_id = state["design_id"]
    cleanup_designs.append(design_id)

    ledger = [
        {
            "family": "patch_antenna",
            "verdict": "kept",
            "reason": "meets band/gain target with a simple, low-cost fabrication",
            "reason_kind": "engineering-judgment",
        }
    ]
    state = _drive_to_redesign_decision(state, tmp_path, considered_and_dropped=ledger)
    redesign_input = {
        "decision": "accept the design as-is",
        "rationale": "measured and correlated results meet the customer requirement",
        "next_action": "accept_design",
    }
    _grant_and_advance(state, DesignStep.REDESIGN_DECISION, redesign_input)

    assert reevaluate_capability_verdicts(design_id) == []


def test_reevaluate_capability_verdicts_raises_for_an_unknown_design_id():
    with pytest.raises(DesignLoopPersistenceError, match="no design found"):
        reevaluate_capability_verdicts(-1)


def test_reevaluate_capability_verdicts_aggregates_entries_across_multiple_decision_records(
    cleanup_designs,
):
    """Issue #396 regression: reevaluate_capability_verdicts moved from
    looping over read_design's aggregated considered_and_dropped JSON to
    querying considered_and_dropped_entries directly
    (designs.db.find_capability_verdict_entries) -- this proves the
    OUTCOME is unchanged for a case the single-decision-record tests above
    don't exercise: capability-verdict entries recorded on TWO SEPARATE
    decision_records rows for the same design are still all found and
    aggregated together, in decision_records.id order, exactly as they
    would have been read out of read_design's old aggregated view."""
    state = start_new_design_loop(
        "TOOL-LEDGER-MULTI", "Capability Verdict Multi-Record Test", "A", CURVATURE_REQUIREMENTS
    )
    design_id = state["design_id"]
    cleanup_designs.append(design_id)

    conn = get_connection()
    try:
        record_decision(
            conn,
            design_id=design_id,
            record_key="TOOL-LEDGER-MULTI-manual-1",
            decision="rectangular microstrip patch on FR4",
            alternatives=[],
            rationale="meets band/gain target with a simple, low-cost fabrication",
            evidence=[],
            design_family="patch_antenna",
            considered_and_dropped=[_capability_verdict_entry(family="reflection_phase_surface")],
        )
        record_decision(
            conn,
            design_id=design_id,
            record_key="TOOL-LEDGER-MULTI-manual-2",
            decision="revisit after simulation",
            alternatives=[],
            rationale="checking a second family too",
            evidence=[],
            design_family="patch_antenna",
            considered_and_dropped=[_capability_verdict_entry(family="checkerboard_amc")],
        )
        conn.commit()
    finally:
        conn.close()

    results = reevaluate_capability_verdicts(design_id)
    assert [r["record_key"] for r in results] == [
        "TOOL-LEDGER-MULTI-manual-1",
        "TOOL-LEDGER-MULTI-manual-2",
    ]
    assert [r["family"] for r in results] == ["reflection_phase_surface", "checkerboard_amc"]
    assert all(r["status"] == "excluded" for r in results)


# ---------------------------------------------------------------------------
# Issue #324 (ADR-0025's 2026-09-09 correction; CONTEXT.md's "Capability
# warning"). A WHOLLY SEPARATE mechanism from the Considered-and-dropped
# ledger above: the `capability_warnings` key must survive the ADR-0011
# flush on its own column, and a persisted entry must be re-evaluatable
# against a caller-supplied CURRENT manufacturing configuration -- never
# against this design's own `requirements` (that's capability-verdict's
# axis, not this one).
# ---------------------------------------------------------------------------


def test_flush_persists_a_capability_warning_entry(cleanup_designs, tmp_path):
    """Acceptance criterion 4: the persisted entry shape after a flush --
    lands verbatim on the ARCHITECTURE decision_records row, in its own
    `capability_warnings` column, alongside an empty
    `considered_and_dropped` (this iteration's ARCHITECTURE step never
    stated one)."""
    state = start_new_design_loop(
        "TOOL-CAPWARN", "Capability Warning Flush Test", "A", REQUIREMENTS
    )
    design_id = state["design_id"]
    cleanup_designs.append(design_id)

    warnings = [_capability_warning_entry()]
    state = _drive_to_redesign_decision(state, tmp_path, capability_warnings=warnings)
    redesign_input = {
        "decision": "accept the design as-is",
        "rationale": "measured and correlated results meet the customer requirement",
        "next_action": "accept_design",
    }
    state = _grant_and_advance(state, DesignStep.REDESIGN_DECISION, redesign_input)
    assert state["completed"] is True

    stored = read_design(design_id)
    decision_records = {d["record_key"].rsplit("-", 1)[-1]: d for d in stored["decision_records"]}
    assert decision_records["architecture"]["capability_warnings"] == warnings
    assert decision_records["architecture"]["considered_and_dropped"] == []
    # Nothing on REDESIGN_DECISION's own step_input stated one either --
    # same "never carries forward across decisions" shape as
    # considered_and_dropped.
    assert decision_records["redesign_decision"]["capability_warnings"] == []


def test_reevaluate_capability_warnings_flips_to_resolved_once_configuration_improves(
    cleanup_designs, tmp_path
):
    """Acceptance criterion 2: re-evaluated every run against the CURRENT
    manufacturing configuration a caller supplies -- never a frozen
    snapshot, and never against this design's own `requirements` (which
    this test never touches)."""
    state = start_new_design_loop(
        "TOOL-CAPWARN-REEVAL", "Capability Warning Reevaluation Test", "A", REQUIREMENTS
    )
    design_id = state["design_id"]
    cleanup_designs.append(design_id)

    state = _drive_to_redesign_decision(
        state, tmp_path, capability_warnings=[_capability_warning_entry()]
    )
    redesign_input = {
        "decision": "accept the design as-is",
        "rationale": "measured and correlated results meet the customer requirement",
        "next_action": "accept_design",
    }
    _grant_and_advance(state, DesignStep.REDESIGN_DECISION, redesign_input)

    still_short = reevaluate_capability_warnings(
        design_id, {"fabrication": {"min_feature_size_mm": 0.5}}
    )
    assert still_short == [
        {
            "record_key": f"TOOL-CAPWARN-REEVAL-{state['loop_id']}-iter1-architecture",
            "family": "patch_antenna",
            "capability_kind": "fabrication",
            "capability_property": "min_feature_size_mm",
            "status": "unresolved",
        }
    ]

    now_resolved = reevaluate_capability_warnings(
        design_id, {"fabrication": {"min_feature_size_mm": 0.15}}
    )
    assert now_resolved[0]["status"] == "resolved"
    assert now_resolved[0]["family"] == "patch_antenna"


def test_reevaluate_capability_warnings_raises_for_an_unknown_design_id():
    with pytest.raises(DesignLoopPersistenceError, match="no design found"):
        reevaluate_capability_warnings(-1, {})


def test_reevaluate_capability_warnings_reads_the_entries_table_directly(cleanup_designs):
    """Issue #397 acceptance criterion 3: this function queries
    `capability_warning_entries` directly, not `read_design`'s aggregated
    JSON -- proved here against a decision record written straight through
    `designs.db.record_decision`, with no design loop involved at all (the
    design loop's own ADR-0011 flush is exercised separately by
    test_flush_persists_a_capability_warning_entry above). Since
    `record_decision` (issue #397) no longer writes real content into
    `decision_records.capability_warnings`, this entry is only visible AT
    ALL if the read path really is the new table -- a `read_design`-based
    implementation would see an empty list here and return `[]`."""
    conn = designs_db.get_connection()
    try:
        design_row = designs_db.create_design(
            conn,
            design_key="TOOL-CAPWARN-DIRECT",
            name="Direct Capability Warning Table Read Test",
            revision="A",
            requirements={},
            architecture={},
        )
        design_id = design_row["id"]
        cleanup_designs.append(design_id)
        designs_db.record_decision(
            conn,
            design_id=design_id,
            record_key="TOOL-CAPWARN-DIRECT-architecture",
            decision="checkerboard AMC absorber",
            alternatives=[],
            rationale="best absorption for the stated band",
            evidence=[],
            design_family="patch_antenna",
            capability_warnings=[_capability_warning_entry()],
        )
        conn.commit()
    finally:
        conn.close()

    still_short = reevaluate_capability_warnings(
        design_id, {"fabrication": {"min_feature_size_mm": 0.5}}
    )
    assert still_short == [
        {
            "record_key": "TOOL-CAPWARN-DIRECT-architecture",
            "family": "patch_antenna",
            "capability_kind": "fabrication",
            "capability_property": "min_feature_size_mm",
            "status": "unresolved",
        }
    ]

    now_resolved = reevaluate_capability_warnings(
        design_id, {"fabrication": {"min_feature_size_mm": 0.15}}
    )
    assert now_resolved[0]["status"] == "resolved"


def test_capability_verdict_and_capability_warning_reevaluations_are_independent(
    cleanup_designs, tmp_path
):
    """Issue #324 acceptance criterion 3: a capability-verdict entry never
    gains a Capability warning and vice versa -- proved here against the
    ACTUAL PERSISTED shape, on the same ARCHITECTURE decision_records row,
    re-evaluating each mechanism through the axis that changed and
    confirming the other one never moves."""
    state = start_new_design_loop(
        "TOOL-BOTH-LEDGERS",
        "Capability Verdict and Warning Coexist Test",
        "A",
        CURVATURE_REQUIREMENTS,
    )
    design_id = state["design_id"]
    cleanup_designs.append(design_id)

    state = _drive_to_redesign_decision(
        state,
        tmp_path,
        considered_and_dropped=[_capability_verdict_entry()],
        capability_warnings=[_capability_warning_entry()],
    )
    redesign_input = {
        "decision": "accept the design as-is",
        "rationale": "measured and correlated results meet the customer requirement",
        "next_action": "accept_design",
    }
    _grant_and_advance(state, DesignStep.REDESIGN_DECISION, redesign_input)

    # Both start "still applies".
    assert reevaluate_capability_verdicts(design_id)[0]["status"] == "excluded"
    stale_config = {"fabrication": {"min_feature_size_mm": 0.5}}
    assert reevaluate_capability_warnings(design_id, stale_config)[0]["status"] == "unresolved"

    # Improving the SHOP CONFIGURATION resolves the Capability warning but
    # never touches the capability-verdict's own re-evaluation.
    fresh_config = {"fabrication": {"min_feature_size_mm": 0.15}}
    assert reevaluate_capability_warnings(design_id, fresh_config)[0]["status"] == "resolved"
    assert reevaluate_capability_verdicts(design_id)[0]["status"] == "excluded"

    # Relaxing the REQUIREMENT's own stated curvature flips the
    # capability-verdict but never touches the Capability warning's own
    # re-evaluation against the (still-short) stale configuration.
    conn = psycopg.connect(os.environ["DATABASE_URL"])
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE designs SET requirements = %s WHERE id = %s",
                (
                    Json(
                        {
                            "R1": {
                                "requirement": (
                                    "conform to a 100 mm radius housing across a 300 mm bend"
                                ),
                                "curvature": {"arc_length_m": 0.05, "host_radius_m": 0.10},
                            }
                        }
                    ),
                    design_id,
                ),
            )
        conn.commit()
    finally:
        conn.close()

    assert reevaluate_capability_verdicts(design_id)[0]["status"] == "reconsiderable"
    assert reevaluate_capability_warnings(design_id, stale_config)[0]["status"] == "unresolved"


@pytest.mark.parametrize(
    ("loop_status", "expected_designs_status"),
    [("CONDITIONAL PASS", "MARGINAL"), ("BLOCKED", "FAIL")],
)
def test_flush_maps_verification_statuses_designs_models_does_not_accept(
    cleanup_designs, tmp_path, loop_status, expected_designs_status
):
    """design_loop.py's VERIFICATION_STATUSES accepts CONDITIONAL PASS/
    BLOCKED, but designs.models.VerificationStatus doesn't -- a mismatch
    the flush's own status-remapping (orchestration/tooling.py's
    _VERIFICATION_STATUS_MAP) must reconcile, or every future flush for
    this iteration would fail permanently (found in code review)."""
    state = start_new_design_loop("TOOL-VSTAT", "Verification Status Map Test", "A", REQUIREMENTS)
    cleanup_designs.append(state["design_id"])
    design_id = state["design_id"]

    state = _drive_to_redesign_decision(state, tmp_path, verification_status=loop_status)
    redesign_input = {
        "decision": "accept the design as-is",
        "rationale": "measured and correlated results meet the customer requirement",
        "next_action": "accept_design",
    }
    state = _grant_and_advance(state, DesignStep.REDESIGN_DECISION, redesign_input)

    assert state["completed"] is True  # the flush succeeded, not raised
    stored = read_design(design_id)
    assert stored["verification_items"][0]["status"] == expected_designs_status
    assert loop_status in stored["verification_items"][0]["notes"]


# ---------------------------------------------------------------------------
# Flush at each iterate boundary (ticket 5).
# ---------------------------------------------------------------------------


def test_flush_at_iterate_persists_that_iteration_and_moves_status_to_analysis(
    cleanup_designs, tmp_path
):
    state = start_new_design_loop("TOOL-ITER", "Iterate Flush Test", "A", REQUIREMENTS)
    cleanup_designs.append(state["design_id"])
    design_id = state["design_id"]

    state = _drive_to_redesign_decision(state, tmp_path)
    iterate_input = {
        "decision": "try a wider patch",
        "rationale": "gain margin too thin, widen for more bandwidth",
        "next_action": "iterate",
    }
    state = _grant_and_advance(state, DesignStep.REDESIGN_DECISION, iterate_input)

    assert state["completed"] is False
    assert state["iteration"] == 2
    assert state["current_step"] == DesignStep.ARCHITECTURE.value
    first_iteration_flushed_count = state["persisted_decision_count"]
    assert first_iteration_flushed_count == len(state["decisions"])

    stored = read_design(design_id)
    assert stored["status"] == "ANALYSIS"
    iter1_keys = {d["record_key"] for d in stored["decision_records"]}
    assert any("iter1-architecture" in k for k in iter1_keys)
    assert any("iter1-redesign_decision" in k for k in iter1_keys)
    assert len(stored["engineering_results"]) == 5  # this iteration's 5 computed results

    # A second full iteration flushes its OWN decisions (distinct record_keys
    # -- "iter2-...") without touching or re-writing iteration 1's rows, and
    # without a record_key collision (proving persisted_decision_count
    # correctly prevents double-flushing the same decisions).
    state = _drive_to_redesign_decision(state, tmp_path)
    accept_input = {
        "decision": "accept the wider design",
        "rationale": "second iteration meets the requirement with margin",
        "next_action": "accept_design",
    }
    state = _grant_and_advance(state, DesignStep.REDESIGN_DECISION, accept_input)

    stored = read_design(design_id)
    assert stored["status"] == "PASS"
    all_keys = {d["record_key"] for d in stored["decision_records"]}
    assert any("iter2-architecture" in k for k in all_keys)
    assert len([k for k in all_keys if "architecture" in k]) == 2  # iter1 + iter2, not merged
    assert len(stored["engineering_results"]) == 10  # 5 per iteration x 2 iterations


def test_flush_design_family_carry_forward_is_scoped_to_its_own_iteration(
    cleanup_designs, tmp_path
):
    """Issue #167. A REDESIGN_DECISION's step_input never states its own
    design_family (design_loop.py's _handle_redesign_decision doesn't ask
    for one) -- orchestration/tooling.py's _flush_decisions carries forward
    the MOST RECENT design_family stated within the batch being flushed, so
    a redesign_decision row is recorded against the family its own
    iteration's ARCHITECTURE decision actually declared, not left NULL.

    This drives TWO iterations that each state a DIFFERENT design_family
    string to prove that carry-forward is scoped to each flush's own batch
    of decisions -- iteration 2's redesign_decision row must show iteration
    2's family, never iteration 1's stale one left over from the previous,
    already-committed flush.

    WHY TWO SPELLINGS OF ONE FAMILY RATHER THAN TWO FAMILIES. This test
    used to abandon a patch for "reflection_phase_surface". Issue #239
    stopped ANALYSIS from falling through to the patch formula for a family
    that declares no analysis model of its own, and REFLECTION_PHASE
    declares none -- it is designed by its per-cell reflection PHASE and no
    closed form here returns a phase -- so the loop can no longer be driven
    end to end with it, by design. `_drive_to_redesign_decision` also feeds
    patch-shaped ANALYSIS inputs and a NEC2 run, which only PATCH declares.

    Nothing under test is weakened by the swap: the carry-forward this
    guards is over the design_family STRING, which `_handle_architecture`
    records verbatim as the caller wrote it, and "patch_antenna" and
    "microstrip_patch" are two different strings (both registry aliases of
    PATCH). The leak #167 fixed -- iteration 1's already-flushed value
    reappearing on iteration 2's row -- fails this test exactly as before.
    Restoring a genuine cross-family change here needs a second family that
    is drivable end to end, which is what issues #242/#243 are adding."""
    state = start_new_design_loop(
        "TOOL-FAMILY-ITER", "Design Family Carry-Forward Test", "A", REQUIREMENTS
    )
    cleanup_designs.append(state["design_id"])
    design_id = state["design_id"]

    state = _drive_to_redesign_decision(state, tmp_path, design_family="patch_antenna")
    iterate_input = {
        "decision": "abandon this patch variant, try another patch geometry instead",
        "rationale": "the first geometry cannot meet the gain target",
        "next_action": "iterate",
    }
    state = _grant_and_advance(state, DesignStep.REDESIGN_DECISION, iterate_input)

    state = _drive_to_redesign_decision(state, tmp_path, design_family="microstrip_patch")
    accept_input = {
        "decision": "accept the second patch geometry",
        "rationale": "meets the gain requirement with margin",
        "next_action": "accept_design",
    }
    state = _grant_and_advance(state, DesignStep.REDESIGN_DECISION, accept_input)

    stored = read_design(design_id)
    by_record_key = {d["record_key"]: d for d in stored["decision_records"]}

    def _row(iteration_marker: str, kind_marker: str) -> dict[str, Any]:
        matches = [
            row
            for key, row in by_record_key.items()
            if iteration_marker in key and kind_marker in key
        ]
        assert len(matches) == 1, f"expected exactly one {iteration_marker}-{kind_marker} row"
        return matches[0]

    assert _row("iter1", "architecture")["design_family"] == "patch_antenna"
    assert _row("iter1", "redesign_decision")["design_family"] == "patch_antenna"
    assert _row("iter2", "architecture")["design_family"] == "microstrip_patch"
    # The real regression this test guards: iteration 2's redesign_decision
    # must show iteration 2's OWN family, not iteration 1's already-flushed
    # "patch_antenna" leaking forward across a flush boundary.
    assert _row("iter2", "redesign_decision")["design_family"] == "microstrip_patch"


def test_flush_persists_design_family_canonical_alongside_the_raw_spelling(
    cleanup_designs, tmp_path
):
    """Issue #408 (ADR-0037). `_handle_architecture` (design_loop.py) has
    always computed a registry-resolved canonical name alongside the
    caller's raw `design_family` string (`design_family_registry
    .canonical_name`) -- this test proves that value actually reaches
    Postgres, not just design_loop.py's in-memory state, and that a query
    grouping by the canonical field merges two differently-spelled runs of
    the same family while grouping by the raw field would not.

    WHY "patch_antenna" / "PATCH" RATHER THAN THE ISSUE'S OWN LITERAL PAIRING.
    Issue #408's acceptance criteria illustrate this with "design_family=
    'PATCH'" and "registry canonical name ... patch_antenna" -- but
    designs/design_families.py's actual registry (_REGISTRY, keyed by
    `fam.name`) defines the PATCH family with `name="PATCH"` (uppercase) and
    lists `"PATCH_ANTENNA"` only as an _ALIASES entry pointing AT it, never
    the other way around: every real `get_design_family` call resolves to
    canonical_name="PATCH", regardless of which of "PATCH"/"patch_antenna"/
    "microstrip_patch" the caller wrote. So this test states the two
    spellings against the registry's real, verifiable behavior instead of
    the issue's (reversed) illustrative pairing: iteration 1's ARCHITECTURE
    step states the lowercase alias "patch_antenna" (already used by
    _drive_to_redesign_decision's own default and by
    test_flush_design_family_carry_forward_is_scoped_to_its_own_iteration
    above), iteration 2 states the literal uppercase spelling "PATCH" the
    issue names -- both resolve to the SAME canonical_name="PATCH", which is
    exactly the cross-run-grouping behavior #150/#151 and this test exist to
    prove.
    """
    state = start_new_design_loop(
        "TOOL-FAMILY-CANON", "Design Family Canonical Test", "A", REQUIREMENTS
    )
    cleanup_designs.append(state["design_id"])
    design_id = state["design_id"]

    state = _drive_to_redesign_decision(state, tmp_path, design_family="patch_antenna")
    iterate_input = {
        "decision": "abandon this patch variant, try another patch geometry instead",
        "rationale": "the first geometry cannot meet the gain target",
        "next_action": "iterate",
    }
    state = _grant_and_advance(state, DesignStep.REDESIGN_DECISION, iterate_input)

    state = _drive_to_redesign_decision(state, tmp_path, design_family="PATCH")
    accept_input = {
        "decision": "accept the second patch geometry",
        "rationale": "meets the gain requirement with margin",
        "next_action": "accept_design",
    }
    state = _grant_and_advance(state, DesignStep.REDESIGN_DECISION, accept_input)

    stored = read_design(design_id)
    by_record_key = {d["record_key"]: d for d in stored["decision_records"]}

    def _row(iteration_marker: str, kind_marker: str) -> dict[str, Any]:
        matches = [
            row
            for key, row in by_record_key.items()
            if iteration_marker in key and kind_marker in key
        ]
        assert len(matches) == 1, f"expected exactly one {iteration_marker}-{kind_marker} row"
        return matches[0]

    # Both values persist, distinctly, on the row that stated them: the raw
    # spelling verbatim (never rewritten to match the registry), and the
    # registry's canonical name alongside it.
    iter1_architecture = _row("iter1", "architecture")
    assert iter1_architecture["design_family"] == "patch_antenna"
    assert iter1_architecture["design_family_canonical"] == "PATCH"

    iter2_architecture = _row("iter2", "architecture")
    assert iter2_architecture["design_family"] == "PATCH"
    assert iter2_architecture["design_family_canonical"] == "PATCH"

    # The DESIGN_FAMILY CARRY-FORWARD reconciliation (_flush_decisions)
    # applies to the canonical field the same way it already does for the
    # raw one: each iteration's redesign_decision row (which never states
    # either field itself) carries forward that SAME iteration's own
    # ARCHITECTURE values, not a stale value from the other iteration.
    assert _row("iter1", "redesign_decision")["design_family"] == "patch_antenna"
    assert _row("iter1", "redesign_decision")["design_family_canonical"] == "PATCH"
    assert _row("iter2", "redesign_decision")["design_family"] == "PATCH"
    assert _row("iter2", "redesign_decision")["design_family_canonical"] == "PATCH"

    # The acceptance criteria's real point: grouping by the RAW field
    # fragments this design's two architecture_decision rows into two
    # separate buckets (different spellings, "patch_antenna" vs "PATCH")
    # even though they are the same family -- exactly the failure mode
    # ADR-0037 exists to fix. Grouping by the CANONICAL field instead
    # correctly merges them into one.
    architecture_rows = [iter1_architecture, iter2_architecture]
    by_raw_family: dict[str, list[dict[str, Any]]] = {}
    by_canonical_family: dict[str, list[dict[str, Any]]] = {}
    for row in architecture_rows:
        by_raw_family.setdefault(row["design_family"], []).append(row)
        by_canonical_family.setdefault(row["design_family_canonical"], []).append(row)

    assert len(by_raw_family) == 2  # "patch_antenna" and "PATCH" fragment apart
    assert len(by_canonical_family) == 1  # both group under canonical "PATCH"
    assert len(by_canonical_family["PATCH"]) == 2


# ---------------------------------------------------------------------------
# Fail-loud, all-or-nothing flush (docs/adr/0011).
# ---------------------------------------------------------------------------


def test_flush_failure_is_atomic_and_leaves_design_status_untouched(cleanup_designs, tmp_path):
    state = start_new_design_loop("TOOL-FAIL", "Flush Failure Test", "A", REQUIREMENTS)
    design_id = state["design_id"]
    cleanup_designs.append(design_id)

    state = _drive_to_redesign_decision(state, tmp_path)

    # Sabotage the flush: pre-insert a decision_records row using the exact
    # record_key this design's REDESIGN_DECISION flush is about to try to
    # write for its ARCHITECTURE decision, forcing designs.db.record_decision
    # to raise RecordKeyCollisionError partway through the flush.
    colliding_key = f"TOOL-FAIL-{state['loop_id']}-iter1-architecture"
    conn = psycopg.connect(os.environ["DATABASE_URL"])
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO decision_records
                    (design_id, record_key, decision, rationale)
                VALUES (%s, %s, %s, %s)
                """,
                (design_id, colliding_key, "sabotage row", "forces a collision"),
            )
        conn.commit()
    finally:
        conn.close()

    redesign_input = {
        "decision": "accept the design as-is",
        "rationale": "measured and correlated results meet the customer requirement",
        "next_action": "accept_design",
    }
    with pytest.raises(DesignLoopPersistenceError, match="refused"):
        _grant_and_advance(state, DesignStep.REDESIGN_DECISION, redesign_input)

    stored = read_design(design_id)
    assert stored["status"] == "DRAFT"  # never reached PASS -- the whole flush rolled back
    assert len(stored["decision_records"]) == 1  # only the sabotage row -- nothing else landed
    assert stored["engineering_results"] == []  # none of the 5 computed results landed either


def test_fresh_requirements_failure_leaves_the_redesign_decision_flush_uncommitted(
    cleanup_designs, tmp_path, monkeypatch
):
    """Code-review fix on issue #100: advance_design_loop_step's own
    _fresh_requirements(design_id) read must run BEFORE the
    REDESIGN_DECISION flush, not after -- it has no data dependency on the
    flush (it neither reads nor writes designs.requirements). Simulates
    that read's own DB connection/read failing on the exact call that
    would otherwise immediately follow a successful flush, and asserts
    nothing from the flush landed: `designs.status` is still whatever it
    was before this call (DRAFT), and no decision_records/
    engineering_results rows exist for it.

    Reproduces the bug this test guards against: under the ordering this
    fixes (fresh-requirements read AFTER the flush), the flush would
    already have committed -- design status ANALYSIS/PASS,
    decision_records/engineering_results already written -- by the time
    this same simulated failure raised, so this test's assertions below
    would fail (status would read PASS, decision_records/
    engineering_results would be non-empty) even though the caller only
    ever saw an exception and still holds their pre-call `state`."""
    state = start_new_design_loop(
        "TOOL-FRESH-FAIL", "Fresh Requirements Failure Test", "A", REQUIREMENTS
    )
    design_id = state["design_id"]
    cleanup_designs.append(design_id)

    # Drive to REDESIGN_DECISION first, unpatched -- _fresh_requirements is
    # called (successfully) on every one of these intermediate steps too
    # (see orchestration/tooling.py's module docstring, "REQUIREMENTS
    # FRESHNESS"), so the sabotage below is installed only after that real
    # traffic is done, to isolate it to the one call under test.
    state = _drive_to_redesign_decision(state, tmp_path)

    class _FreshRequirementsReadFailed(Exception):
        pass

    import orchestration.tooling as tooling_module

    # Mirrors _fresh_requirements' real signature exactly, `fallback` included
    # and deliberately not defaulted: a default here would let this double
    # drift out of step with production again without any test noticing, which
    # is how it came to be stale in the first place.
    def _boom(design_id_arg: int, fallback: dict[str, Any]) -> dict[str, Any]:
        assert design_id_arg == design_id
        raise _FreshRequirementsReadFailed("fresh requirements read failed (simulated)")

    monkeypatch.setattr(tooling_module, "_fresh_requirements", _boom)

    redesign_input = {
        "decision": "accept the design as-is",
        "rationale": "measured and correlated results meet the customer requirement",
        "next_action": "accept_design",
    }
    with pytest.raises(_FreshRequirementsReadFailed):
        _grant_and_advance(state, DesignStep.REDESIGN_DECISION, redesign_input)

    stored = read_design(design_id)
    assert stored["status"] == "DRAFT"  # never reached PASS -- the flush never ran
    assert stored["decision_records"] == []  # nothing landed
    assert stored["engineering_results"] == []  # none of the 5 computed results landed either


# ---------------------------------------------------------------------------
# The candidate solver's decisions persist at the existing flush (issue #95).
#
# orchestration/solver.py's own module docstring ("WHICH LAYER THIS MODULE
# DRIVES") argues this should already work, by construction, with zero new
# persistence code: run_candidate_search drives via THIS module's own
# advance_design_loop_step, so a winning candidate's ANALYSIS/SIMULATION/
# OPTIMIZATION LoopDecisions land in state["decisions"] exactly as if an
# engineer had called advance_design_loop_step by hand for each one --
# nothing downstream of that (this file's _flush_decisions) can tell the
# difference. This test is the live-Postgres proof of that argument -- it
# CANNOT run in the sandbox this ticket was implemented in (no DATABASE_URL,
# see this module's own docstring); it is written to this suite's existing
# convention and should be run in CI/a real environment before being relied
# on. NOT run as part of this ticket's own verification for that reason.
# ---------------------------------------------------------------------------


def test_solver_produced_decisions_persist_at_the_redesign_decision_flush(
    cleanup_designs, tmp_path
):
    """Drives ANALYSIS/SIMULATION/OPTIMIZATION for one candidate via
    orchestration.solver.run_candidate_search (not by hand, unlike every
    other test in this file), then continues that winning candidate's own
    returned state through VERIFICATION/MEASUREMENT/CORRELATION/
    REDESIGN_DECISION exactly like test_flush_at_accept_design_persists_
    full_history does -- and asserts the same five engineering_results
    tool_names land, proving the solver's decisions are indistinguishable,
    at the flush, from ones an engineer recorded one call at a time."""
    state = start_new_design_loop("TOOL-SOLVER", "Solver Persistence Test", "A", REQUIREMENTS)
    design_id = state["design_id"]
    cleanup_designs.append(design_id)

    architecture_input = {
        "decision": "rectangular microstrip patch on FR4",
        "rationale": "meets band/gain target with a simple, low-cost fabrication",
        "design_family": "patch_antenna",
    }
    state = _grant_and_advance(state, DesignStep.ARCHITECTURE, architecture_input)
    assert state["current_step"] == DesignStep.ANALYSIS.value

    fake_nec2pp = _make_fake_nec2pp(tmp_path)
    candidate = {
        "eps_r": 4.4,
        "w_m": 0.03,
        "h_m": 0.0016,
        "l_m": 0.0286,
        "geometry": _DIPOLE_GEOMETRY,
        "frequency_hz": 300e6,
        "reference_impedance_ohms": 50.0,
        "executable": str(fake_nec2pp),
        "workdir": str(tmp_path / "nec2_run"),
        "target_frequency_hz": 2.45e9,
        "length_lower_m": 0.02,
        "length_upper_m": 0.04,
        "method": "sweep",
        "n_evaluations": 5,
    }
    achieved_analysis_freq = patch_resonant_frequency_hz(
        candidate["eps_r"], candidate["w_m"], candidate["h_m"], candidate["l_m"]
    )
    analysis_target = propose_target(
        value=achieved_analysis_freq, comparator="EQUALS", unit="Hz", tolerance=5e7
    )
    optimization_target = propose_target(
        value=candidate["target_frequency_hz"], comparator="EQUALS", unit="Hz", tolerance=5e7
    )
    score_specs = {
        "analysis": {"target": analysis_target},
        "optimization": {"target": optimization_target},
    }

    solver_result = run_candidate_search(state, [candidate], score_specs)
    assert solver_result["candidates_evaluated"] == 1
    assert solver_result["trail"][0]["status"] == "evaluated"
    assert solver_result["best_candidate_index"] == 0
    won_state = solver_result["best_candidate_state"]
    assert won_state["current_step"] == DesignStep.VERIFICATION.value
    assert won_state["design_id"] == design_id
    assert won_state["persisted_decision_count"] == 0  # nothing flushed yet

    state = advance_design_loop_step(
        won_state,
        {
            "requirement_id": "R1",
            "requirement": "gain >= 5 dBi over 2.4-2.5 GHz",
            "method": "analysis",
            "expected": candidate["target_frequency_hz"],
            "actual": won_state["decisions"][-1]["result"]["achieved_frequency_hz"],
            "status": "PASS",
        },
    )
    touchstone_path = _write_measured_touchstone(tmp_path, name="solver-persistence")
    state = _grant_and_advance(
        state, DesignStep.MEASUREMENT, {"touchstone_file": str(touchstone_path)}
    )
    simulated_override = {
        "frequency_hz": [2.0e9, 2.5e9, 3.0e9],
        "s_parameters": {"S11": ["0.1+0.01j", "0.2+0.02j", "0.3+0.03j"]},
        "z0": 50.0,
    }
    state = advance_design_loop_step(state, {"simulated": simulated_override})
    assert state["current_step"] == DesignStep.REDESIGN_DECISION.value

    redesign_input = {
        "decision": "accept the design as-is",
        "rationale": "solver-driven candidate met both requirement targets",
        "next_action": "accept_design",
    }
    state = _grant_and_advance(state, DesignStep.REDESIGN_DECISION, redesign_input)

    assert state["completed"] is True
    assert state["persisted_decision_count"] == len(state["decisions"])

    stored = read_design(design_id)
    assert stored["status"] == "PASS"

    results_by_tool = {r["tool_name"]: r for r in stored["engineering_results"]}
    # The exact same five tool_names test_flush_at_accept_design_persists_
    # full_history asserts for a hand-driven cycle -- the solver's ANALYSIS/
    # SIMULATION/OPTIMIZATION decisions are here too, indistinguishable from
    # ones recorded one advance_design_loop_step call at a time.
    assert set(results_by_tool) == {
        "patch_resonant_frequency_hz",
        "run_nec2_simulation",
        "optimize_patch_length_for_target_frequency",
        "record_external_measurement",
        "correlate_simulation_measurement",
    }
    assert results_by_tool["patch_resonant_frequency_hz"]["provenance"] == "CALCULATED"
    assert (
        results_by_tool["optimize_patch_length_for_target_frequency"]["provenance"] == "CALCULATED"
    )
    assert stored["verification_items"][0]["status"] == "PASS"
