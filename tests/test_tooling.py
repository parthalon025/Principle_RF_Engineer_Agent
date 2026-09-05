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
import stat
import sys
from pathlib import Path
from typing import Any

import numpy as np
import psycopg
import pytest
import skrf as rf
from dotenv import load_dotenv

from designs.requirement_targets import (
    confirm_requirement_target,
    propose_requirement_target,
    propose_target,
)
from designs.service import read_design
from orchestration.approval import request_loop_step_approval
from orchestration.design_loop import DesignStep
from orchestration.solver import run_candidate_search
from orchestration.tooling import (
    DesignLoopPersistenceError,
    advance_design_loop_step,
    inspect_design_loop_state,
    start_new_design_loop,
)
from rf_tools.calculations import patch_resonant_frequency_hz

load_dotenv()

REQUIREMENTS = {"R1": {"requirement": "gain >= 5 dBi over 2.4-2.5 GHz"}}


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


def _measurement_decision(result: dict[str, Any]) -> Any:
    from orchestration.design_loop import LoopDecision

    return LoopDecision(
        step=DesignStep.MEASUREMENT.value,
        kind="measurement",
        input={},
        result=result,
        provenance="MEASURED",
        approved_by="jane.engineer",
        recorded_at=0.0,
    )


def test_external_measurement_is_recorded_as_record_external_measurement():
    """A MEASUREMENT decision's evidence -- a Touchstone file an engineer
    measured elsewhere and carried back (ticket #90: the only MEASUREMENT
    path there is) -- is persisted under the real function name that
    produced it."""
    from orchestration.tooling import _tool_name_for

    decision = _measurement_decision(
        {
            "touchstone_file": "/tmp/dut.s2p",
            "provenance": "MEASURED",
            "source": "external_test_iteration",
        }
    )
    assert _tool_name_for(decision) == "record_external_measurement"


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

_FAKE_NEC2PP_PY = '''#!{python}
import sys

OUTPUT = """{sample}"""

args = sys.argv[1:]
assert "-i" in args, args
sys.stdout.write(OUTPUT)
sys.exit(0)
'''


def _make_fake_nec2pp(tmp_path: Path) -> Path:
    script = tmp_path / "fake_nec2pp.py"
    script.write_text(_FAKE_NEC2PP_PY.format(python=sys.executable, sample=_GUIDE_SAMPLE_OUTPUT))
    script.chmod(script.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return script


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
    fields = _fingerprint(state, step, step_input)
    receipt = request_loop_step_approval(
        fields, approved_by="jane.engineer", approval_callback=lambda f: True
    )
    return advance_design_loop_step(state, step_input, approval=receipt.to_dict())


def _drive_to_redesign_decision(
    state: dict[str, Any], tmp_path: Path, verification_status: str = "PASS"
) -> dict[str, Any]:
    """Real ARCHITECTURE -> ... -> CORRELATION, leaving `state` positioned
    at REDESIGN_DECISION -- callers advance the final gated step themselves
    with whatever next_action they're testing. `verification_status` lets
    callers exercise design_loop.py's wider VERIFICATION_STATUSES
    vocabulary (CONDITIONAL PASS/BLOCKED, not just designs.models.
    VerificationStatus's own PASS/FAIL/MARGINAL/NOT VERIFIED)."""
    state = _grant_and_advance(
        state,
        DesignStep.ARCHITECTURE,
        {
            "decision": "rectangular microstrip patch on FR4",
            "rationale": "meets band/gain target with a simple, low-cost fabrication",
            "design_family": "patch_antenna",
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

    assert stored["verification_items"][0]["status"] == "PASS"
    assert stored["verification_items"][0]["method"] == "analysis"


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
