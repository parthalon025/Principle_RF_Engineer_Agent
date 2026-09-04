# ruff: noqa: E501 -- this file transcribes the fixed-column NEC2 sample
# output verbatim (see tests/test_nec2pp.py's own header for why reflowing
# it would break the exact fixed-column shape the parser under test reads).
"""Tests for the controlled autonomous design-iteration loop (issue #46,
Phase 12 -- the final ticket of the 23-ticket build-out).

  1. The approval gate against a REAL, unmodified DesignLoopState -- proving
     advance_loop_step structurally cannot advance past ARCHITECTURE,
     MEASUREMENT, or REDESIGN_DECISION without a valid
     LoopStepApprovalReceipt, and that request_loop_step_approval itself
     always raises with no approval_callback (the only way this codebase's
     current agent/MCP tool wiring -- orchestration/tooling.py -- could ever
     call it).
  2. Cryptographic receipt binding -- a receipt granted for one loop/
     iteration/step/decision cannot be replayed for a different one; a bare
     dict/string cannot substitute.
  3. State-machine mechanics: start/advance/to_dict/from_dict, ungated steps
     advancing freely, pending_approval being queryable at any point
     mid-loop (not just at completion).
  4. The "no manufacturing-release path exists" property -- simple,
     direct introspection, per this ticket's own scope guidance.
  5. An end-to-end test driving one full requirements -> redesign cycle
     through all nine DesignStep values, composing the REAL Phase 1/6/9/11
     functions (rf_tools.calculations.patch_resonant_frequency_hz,
     simulation.nec2pp.run_nec2_simulation, optimization.rf_objectives.
     optimize_patch_length_for_target_frequency, measurement.external.
     record_external_measurement, rf_tools.correlation.
     correlate_simulation_measurement) against a fake NEC2++ executable
     (tests/test_nec2pp.py's own pattern) and a real Touchstone file for
     MEASUREMENT (ticket #90: the design loop has no live-instrument path
     left -- see measurement/external.py and ADR-0012/ADR-0013).
"""

import re
import stat
import sys
from dataclasses import replace as _dc_replace
from pathlib import Path

import numpy as np
import pytest
import skrf as rf

from measurement.external import ExternalMeasurementError
from orchestration.approval import (
    LoopStepApprovalReceipt,
    OrchestrationError,
    request_loop_step_approval,
)
from orchestration.design_loop import (
    GATED_STEPS,
    REDESIGN_ACTIONS,
    STEP_ORDER,
    DesignLoopState,
    DesignLoopValidationError,
    DesignStep,
    LoopDecision,
    advance_loop_step,
    start_design_loop,
)

REQUIREMENTS = {
    "band_ghz": [2.4, 2.5],
    "gain_dbi_min": 5.0,
    "form_factor": "conformal patch, curved host",
}


# ---------------------------------------------------------------------------
# Group 1: the real, unmockable proof that unattended advancement is
# rejected.
# ---------------------------------------------------------------------------


def test_request_loop_step_approval_raises_by_default_with_no_callback():
    with pytest.raises(OrchestrationError, match="No human-approval mechanism"):
        request_loop_step_approval({"loop_id": "x", "step": "architecture"}, approved_by="a.human")


def test_request_loop_step_approval_requires_approved_by():
    with pytest.raises(OrchestrationError, match="approved_by"):
        request_loop_step_approval(
            {"loop_id": "x", "step": "architecture"}, approval_callback=lambda fields: True
        )


def test_request_loop_step_approval_raises_when_callback_declines():
    with pytest.raises(OrchestrationError, match="not approved"):
        request_loop_step_approval(
            {"loop_id": "x", "step": "architecture"},
            approved_by="a.human",
            approval_callback=lambda fields: False,
        )


@pytest.mark.parametrize("step", sorted(GATED_STEPS, key=lambda s: s.value))
def test_advance_loop_step_rejects_gated_step_with_no_approval(step):
    """The core safety property: for EVERY gated step, in this real,
    unmodified sandbox, advance_loop_step refuses to proceed without a
    valid approval -- no bypass exists from this call surface."""
    state = start_design_loop(REQUIREMENTS)
    # Walk to `step` using ungated advances plus the minimum valid approvals
    # for any gated steps encountered before it, then attempt the gated
    # step itself with NO approval.
    state = _advance_to(state, step, grant_intermediate_approvals=True)
    with pytest.raises(OrchestrationError, match="Design-loop step advancement refused"):
        advance_loop_step(state, _valid_step_input(state, step))
    # The loop did not advance -- current_step is unchanged.
    assert state.current_step == step.value


def test_advance_loop_step_rejects_a_bare_string_masquerading_as_approval():
    state = start_design_loop(REQUIREMENTS)
    step_input = _valid_step_input(state, DesignStep.ARCHITECTURE)
    with pytest.raises(OrchestrationError, match="not a bare str"):
        advance_loop_step(state, step_input, approval="trust me, a human approved this")


def test_advance_loop_step_rejects_a_forged_dict_shaped_like_a_receipt():
    """A dict that coerces into a LoopStepApprovalReceipt-shaped object
    (all fields present) but whose token was never actually produced by
    request_loop_step_approval -- the signature check catches it."""
    state = start_design_loop(REQUIREMENTS)
    step_input = _valid_step_input(state, DesignStep.ARCHITECTURE)
    forged = {
        "token": "0" * 64,
        "decision_fingerprint": "0" * 64,
        "approved_by": "nobody",
        "granted_at": 0.0,
    }
    with pytest.raises(OrchestrationError, match="signature is invalid"):
        advance_loop_step(state, step_input, approval=forged)


def test_advance_loop_step_rejects_approval_granted_for_different_content():
    state = start_design_loop(REQUIREMENTS)
    step_input = _valid_step_input(state, DesignStep.ARCHITECTURE)
    other_input = {**step_input, "decision": "a completely different architecture"}
    fields = {
        "loop_id": state.loop_id,
        "iteration": state.iteration,
        "step": DesignStep.ARCHITECTURE.value,
        "content": other_input,
    }
    receipt = request_loop_step_approval(
        fields, approved_by="jane", approval_callback=lambda f: True
    )
    with pytest.raises(OrchestrationError, match="does not match"):
        advance_loop_step(state, step_input, approval=receipt)


def test_advance_loop_step_rejects_approval_granted_for_a_different_loop():
    state_a = start_design_loop(REQUIREMENTS)
    state_b = start_design_loop(REQUIREMENTS)
    step_input = _valid_step_input(state_a, DesignStep.ARCHITECTURE)
    fields_b = {
        "loop_id": state_b.loop_id,
        "iteration": state_b.iteration,
        "step": DesignStep.ARCHITECTURE.value,
        "content": step_input,
    }
    receipt_for_b = request_loop_step_approval(
        fields_b, approved_by="jane", approval_callback=lambda f: True
    )
    with pytest.raises(OrchestrationError, match="does not match"):
        advance_loop_step(state_a, step_input, approval=receipt_for_b)


def test_a_granted_receipt_round_trips_through_a_dict_and_still_works():
    """A receipt that crossed an agent/MCP JSON tool boundary and back (a
    plain dict) is accepted."""
    state = start_design_loop(REQUIREMENTS)
    step_input = _valid_step_input(state, DesignStep.ARCHITECTURE)
    fields = _fingerprint(state, DesignStep.ARCHITECTURE, step_input)
    receipt = request_loop_step_approval(
        fields, approved_by="jane", approval_callback=lambda f: True
    )
    receipt_dict = receipt.to_dict()
    assert isinstance(receipt_dict, dict)

    new_state = advance_loop_step(state, step_input, approval=receipt_dict)
    assert new_state.current_step == DesignStep.ANALYSIS.value


def test_forged_token_is_rejected():
    state = start_design_loop(REQUIREMENTS)
    step_input = _valid_step_input(state, DesignStep.ARCHITECTURE)
    fields = _fingerprint(state, DesignStep.ARCHITECTURE, step_input)
    receipt = request_loop_step_approval(
        fields, approved_by="jane", approval_callback=lambda f: True
    )
    forged = LoopStepApprovalReceipt(
        token="0" * 64,
        decision_fingerprint=receipt.decision_fingerprint,
        approved_by=receipt.approved_by,
        granted_at=receipt.granted_at,
    )
    with pytest.raises(OrchestrationError, match="signature is invalid"):
        advance_loop_step(state, step_input, approval=forged)


# ---------------------------------------------------------------------------
# Group 2: state-machine mechanics.
# ---------------------------------------------------------------------------


def test_start_design_loop_requires_a_nonempty_requirements_dict():
    with pytest.raises(DesignLoopValidationError):
        start_design_loop({})
    with pytest.raises(DesignLoopValidationError):
        start_design_loop(None)  # type: ignore[arg-type]


def test_start_design_loop_records_requirements_and_positions_at_architecture():
    state = start_design_loop(REQUIREMENTS)
    assert state.current_step == DesignStep.ARCHITECTURE.value
    assert state.iteration == 1
    assert not state.completed
    assert len(state.decisions) == 1
    assert state.decisions[0].step == DesignStep.REQUIREMENTS.value
    assert state.decisions[0].result == REQUIREMENTS


def test_pending_approval_is_queryable_mid_loop_for_a_gated_step():
    state = start_design_loop(REQUIREMENTS)
    pending = state.to_dict()["pending_approval"]
    assert pending is not None
    assert pending["step"] == DesignStep.ARCHITECTURE.value
    assert pending["requires_approval"] is True


def test_pending_approval_is_none_for_an_ungated_step():
    state = start_design_loop(REQUIREMENTS)
    state = _advance_to(state, DesignStep.ANALYSIS, grant_intermediate_approvals=True)
    assert state.to_dict()["pending_approval"] is None


def test_ungated_steps_advance_without_any_approval():
    state = start_design_loop(REQUIREMENTS)
    state = _advance_to(state, DesignStep.ARCHITECTURE, grant_intermediate_approvals=True)
    state = _grant_and_advance(state, DesignStep.ARCHITECTURE)
    assert state.current_step == DesignStep.ANALYSIS.value
    state = advance_loop_step(state, _valid_step_input(state, DesignStep.ANALYSIS))
    assert state.current_step == DesignStep.SIMULATION.value
    assert state.decisions[-1].provenance == "CALCULATED"


def test_requirements_decision_is_tagged_with_iteration_1():
    state = start_design_loop(REQUIREMENTS)
    assert state.decisions[0].iteration == 1


def test_decisions_recorded_within_an_iteration_all_carry_that_iteration():
    state = start_design_loop(REQUIREMENTS)
    state = _grant_and_advance(state, DesignStep.ARCHITECTURE)
    state = advance_loop_step(state, _valid_step_input(state, DesignStep.ANALYSIS))
    for decision in state.decisions:
        assert decision.iteration == 1


def test_redesign_decision_that_closes_an_iteration_is_tagged_with_the_iteration_it_closes():
    """The REDESIGN_DECISION decision with next_action='iterate' is tagged
    with the iteration it CLOSES (1), not the new iteration (2) the loop
    moves to as a result of that same decision -- issue #88's core
    acceptance criterion."""
    state = start_design_loop(REQUIREMENTS)
    state = _run_full_cycle_up_to_redesign(state)
    step_input = {
        "decision": "revise substrate thickness",
        "rationale": "measured bandwidth narrower than required",
        "next_action": "iterate",
    }
    state = _grant_and_advance(state, DesignStep.REDESIGN_DECISION, step_input_override=step_input)

    assert state.iteration == 2
    redesign_decision = state.decisions[-1]
    assert redesign_decision.step == DesignStep.REDESIGN_DECISION.value
    assert redesign_decision.iteration == 1


def test_decisions_recorded_after_an_iterate_transition_carry_the_new_iteration():
    state = start_design_loop(REQUIREMENTS)
    state = _run_full_cycle_up_to_redesign(state)
    step_input = {
        "decision": "revise substrate thickness",
        "rationale": "measured bandwidth narrower than required",
        "next_action": "iterate",
    }
    state = _grant_and_advance(state, DesignStep.REDESIGN_DECISION, step_input_override=step_input)
    assert state.current_step == DesignStep.ARCHITECTURE.value

    state = _grant_and_advance(state, DesignStep.ARCHITECTURE)
    assert state.decisions[-1].iteration == 2

    # And decisions either side of the boundary are distinguishable by
    # iteration alone, without consulting persisted_decision_count. (Note:
    # _run_full_cycle_up_to_redesign teleports current_step directly to
    # REDESIGN_DECISION via _advance_to, per that helper's own docstring,
    # so only REQUIREMENTS and the closing REDESIGN_DECISION were actually
    # recorded for iteration 1 here -- see the end-to-end test for a real,
    # step-by-step walk through every step of an iteration.)
    iteration_1_decisions = [d for d in state.decisions if d.iteration == 1]
    iteration_2_decisions = [d for d in state.decisions if d.iteration == 2]
    assert len(iteration_1_decisions) == 2  # REQUIREMENTS + the closing REDESIGN_DECISION
    assert len(iteration_2_decisions) == 1  # this iteration's ARCHITECTURE decision


def test_loop_decision_iteration_round_trips_through_to_dict_and_from_dict():
    state = start_design_loop(REQUIREMENTS)
    state = _run_full_cycle_up_to_redesign(state)
    step_input = {
        "decision": "revise substrate thickness",
        "rationale": "measured bandwidth narrower than required",
        "next_action": "iterate",
    }
    state = _grant_and_advance(state, DesignStep.REDESIGN_DECISION, step_input_override=step_input)

    as_dict = state.to_dict()
    assert as_dict["decisions"][-1]["iteration"] == 1
    restored = DesignLoopState.from_dict(as_dict)
    assert restored.decisions[-1].iteration == 1
    assert restored.to_dict() == as_dict


def test_loop_decision_from_dict_tolerates_a_pre_88_dump_with_no_iteration_field():
    """A DesignLoopState serialized before issue #88 has no `iteration` key
    on any decision -- from_dict must still load it, defaulting each
    decision's iteration to 1 (see LoopDecision's own docstring for why 1
    is the only value such a dump's decisions could have meant)."""
    state = start_design_loop(REQUIREMENTS)
    legacy_dict = state.to_dict()
    for decision_dict in legacy_dict["decisions"]:
        del decision_dict["iteration"]

    restored = DesignLoopState.from_dict(legacy_dict)
    assert restored.decisions[0].iteration == 1
    assert isinstance(restored.decisions[0], LoopDecision)


def test_state_round_trips_through_to_dict_and_from_dict():
    state = start_design_loop(REQUIREMENTS)
    state = _grant_and_advance(state, DesignStep.ARCHITECTURE)
    as_dict = state.to_dict()
    restored = DesignLoopState.from_dict(as_dict)
    assert restored.loop_id == state.loop_id
    assert restored.current_step == state.current_step
    assert len(restored.decisions) == len(state.decisions)
    assert all(isinstance(d, LoopDecision) for d in restored.decisions)
    assert restored.to_dict() == as_dict


def test_advance_loop_step_never_mutates_the_passed_in_state():
    state = start_design_loop(REQUIREMENTS)
    before = state.to_dict()
    _grant_and_advance(state, DesignStep.ARCHITECTURE)
    assert state.to_dict() == before


def test_advance_loop_step_raises_after_the_loop_is_completed():
    state = start_design_loop(REQUIREMENTS)
    state = _run_full_cycle_up_to_redesign(state)
    state = _grant_and_advance(
        state,
        DesignStep.REDESIGN_DECISION,
        step_input_override={
            "decision": "ship it",
            "rationale": "meets spec",
            "next_action": "accept_design",
        },
    )
    assert state.completed
    with pytest.raises(OrchestrationError, match="already reached its terminal state"):
        advance_loop_step(state, {})


def test_redesign_decision_iterate_loops_back_to_architecture():
    state = start_design_loop(REQUIREMENTS)
    state = _run_full_cycle_up_to_redesign(state)
    step_input = {
        "decision": "revise substrate thickness",
        "rationale": "measured bandwidth narrower than required",
        "next_action": "iterate",
    }
    state = _grant_and_advance(state, DesignStep.REDESIGN_DECISION, step_input_override=step_input)
    assert state.current_step == DesignStep.ARCHITECTURE.value
    assert state.iteration == 2
    assert not state.completed


def test_invalid_redesign_next_action_is_rejected():
    state = start_design_loop(REQUIREMENTS)
    state = _run_full_cycle_up_to_redesign(state)
    step_input = {
        "decision": "x",
        "rationale": "y",
        "next_action": "release_to_manufacturing",
    }
    fields = _fingerprint(state, DesignStep.REDESIGN_DECISION, step_input)
    receipt = request_loop_step_approval(
        fields, approved_by="jane", approval_callback=lambda f: True
    )
    with pytest.raises(DesignLoopValidationError, match="next_action"):
        advance_loop_step(state, step_input, approval=receipt)


def test_analysis_requires_expected_fields():
    state = start_design_loop(REQUIREMENTS)
    state = _grant_and_advance(state, DesignStep.ARCHITECTURE)
    with pytest.raises(DesignLoopValidationError, match="missing required field"):
        advance_loop_step(state, {"eps_r": 4.4})


def test_verification_rejects_an_unrecognized_status():
    state = start_design_loop(REQUIREMENTS)
    state = _advance_to(state, DesignStep.VERIFICATION, grant_intermediate_approvals=True)
    bad_input = {
        "requirement_id": "R1",
        "requirement": "gain >= 5 dBi",
        "method": "analysis",
        "status": "PROBABLY_FINE",
    }
    with pytest.raises(DesignLoopValidationError, match="status"):
        advance_loop_step(state, bad_input)


# ---------------------------------------------------------------------------
# Group 3: no manufacturing-release path exists. Simple, direct
# introspection, per this ticket's own scope guidance.
# ---------------------------------------------------------------------------

_BANNED_SUBSTRINGS = ("release", "manufactur", "production")


def test_no_manufacturing_release_step_exists():
    for step in DesignStep:
        lowered = f"{step.name} {step.value}".lower()
        for banned in _BANNED_SUBSTRINGS:
            assert banned not in lowered, f"DesignStep {step!r} looks like a release step"


def test_redesign_decision_has_no_release_action():
    assert REDESIGN_ACTIONS == frozenset({"iterate", "accept_design"})
    for action in REDESIGN_ACTIONS:
        for banned in _BANNED_SUBSTRINGS:
            assert banned not in action


def test_no_release_or_manufacturing_callable_exists_anywhere_in_the_package():
    import orchestration.approval as approval_module
    import orchestration.design_loop as design_loop_module
    import orchestration.tooling as tooling_module

    for module in (approval_module, design_loop_module, tooling_module):
        for attr_name in dir(module):
            lowered = attr_name.lower()
            for banned in _BANNED_SUBSTRINGS:
                assert banned not in lowered, (
                    f"{module.__name__}.{attr_name} looks like a manufacturing-"
                    "release path -- none should exist (docs/BUILD_PLAN.md's "
                    "Phase 12: 'Never allow autonomous manufacturing release')"
                )


def test_completed_loop_has_no_further_action_available_but_to_start_a_new_one():
    """Even once a design is accepted, advancing further raises -- there is
    no hidden terminal action reachable from a completed loop."""
    state = start_design_loop(REQUIREMENTS)
    state = _run_full_cycle_up_to_redesign(state)
    state = _grant_and_advance(
        state,
        DesignStep.REDESIGN_DECISION,
        step_input_override={
            "decision": "ship it",
            "rationale": "meets spec",
            "next_action": "accept_design",
        },
    )
    assert state.completed
    with pytest.raises(OrchestrationError):
        advance_loop_step(state, {"next_action": "iterate"})


# ---------------------------------------------------------------------------
# Group 4 (orchestration/tooling.py's three agent/MCP-facing dict-in/
# dict-out functions) moved to tests/test_tooling.py: since docs/adr/0011,
# those functions call designs.db/designs.service and need a real
# Postgres, unlike every test in this file -- see that file's own header.
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Group 5 (issue #89, ADR-0012/ADR-0013): MEASUREMENT accepts a Touchstone
# file brought back from external testing -- CONTEXT.md's "Test iteration"
# -- the ONLY MEASUREMENT path since ticket #90 removed the instrument-
# control package. Focused unit tests (real Touchstone data, real approval
# gate, real CORRELATION call), plus one full end-to-end walk of all nine
# DesignStep values (test_end_to_end_full_requirements_to_redesign_cycle
# below) composing the real Phase 1/6/9/11 functions against a fake NEC2++
# executable (shared helpers below) and a real Touchstone file for
# MEASUREMENT.
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
    """A real one-port Touchstone file, built with skrf the same way
    tests/test_touchstone.py does -- this exercises the actual
    rf_tools.touchstone.analyze_touchstone parse path (reused unmodified by
    measurement/external.py), not a stub or a hand-rolled fake. One-port
    (S11 only) to match this file's own CORRELATION `simulated_override`
    shape (S11-only -- see rf_tools/correlation.py's own "same port count"
    requirement)."""
    freqs_hz = [2.0e9, 2.5e9, 3.0e9]
    f = rf.Frequency.from_f(freqs_hz, unit="hz")
    s = np.zeros((3, 1, 1), dtype=complex)
    s[:, 0, 0] = 10 ** (-15 / 20)
    ntwk = rf.Network(frequency=f, s=s, z0=50)
    path = tmp_path / f"{name}.s1p"
    ntwk.write_touchstone(path.with_suffix(""))
    return path


def test_measurement_accepts_external_touchstone_file_with_measured_provenance(tmp_path: Path):
    touchstone_path = _write_measured_touchstone(tmp_path)
    state = start_design_loop(REQUIREMENTS)
    state = _advance_to(state, DesignStep.MEASUREMENT, grant_intermediate_approvals=True)

    step_input = {
        "touchstone_file": str(touchstone_path),
        "lab_report": "s3://lab-reports/2026-09-03-patch-A.pdf",
        "notes": "Anechoic chamber, 23C ambient, cal kit lot 4471, test date 2026-09-03.",
    }
    state = _grant_and_advance(state, DesignStep.MEASUREMENT, step_input_override=step_input)

    assert state.current_step == DesignStep.CORRELATION.value
    decision = state.decisions[-1]
    assert decision.kind == "measurement"
    assert decision.provenance == "MEASURED"
    assert decision.approved_by == "jane.engineer"
    # The shape rf_tools.correlation._result_to_network already accepts,
    # with zero changes to rf_tools/correlation.py.
    assert decision.result["touchstone_file"] == str(touchstone_path.resolve())
    # The lab report and notes are stored on the decision verbatim...
    assert decision.result["lab_report"] == step_input["lab_report"]
    assert decision.result["notes"] == step_input["notes"]
    # ...and neither was read for numeric values: nothing in the parsed
    # result depends on their content (they're plain strings, never fed to
    # analyze_touchstone or otherwise interpreted).
    assert decision.result["ports"] == 1
    # No instrument was ever involved on this path.
    assert "instrument" not in decision.result
    assert "resource" not in decision.result


def test_external_measurement_lab_report_and_notes_are_optional(tmp_path: Path):
    touchstone_path = _write_measured_touchstone(tmp_path, name="no_report")
    state = start_design_loop(REQUIREMENTS)
    state = _advance_to(state, DesignStep.MEASUREMENT, grant_intermediate_approvals=True)

    step_input = {"touchstone_file": str(touchstone_path)}
    state = _grant_and_advance(state, DesignStep.MEASUREMENT, step_input_override=step_input)

    decision = state.decisions[-1]
    assert decision.provenance == "MEASURED"
    assert decision.result["lab_report"] is None
    assert decision.result["notes"] is None


def test_correlation_consumes_external_measurement_result_with_no_changes(tmp_path: Path):
    touchstone_path = _write_measured_touchstone(tmp_path, name="for_correlation")
    state = start_design_loop(REQUIREMENTS)
    state = _advance_to(state, DesignStep.MEASUREMENT, grant_intermediate_approvals=True)
    state = _grant_and_advance(
        state, DesignStep.MEASUREMENT, step_input_override={"touchstone_file": str(touchstone_path)}
    )

    simulated_override = {
        "frequency_hz": [2.0e9, 2.5e9, 3.0e9],
        "s_parameters": {"S11": ["0.1+0.01j", "0.2+0.02j", "0.3+0.03j"]},
        "z0": 50.0,
    }
    # No 'measured' override supplied -- CORRELATION must pick up the
    # loop's own just-recorded external MEASUREMENT decision on its own.
    state = advance_loop_step(state, {"simulated": simulated_override})

    assert state.current_step == DesignStep.REDESIGN_DECISION.value
    decision = state.decisions[-1]
    assert decision.kind == "correlation"
    assert decision.provenance == "CALCULATED"
    assert decision.result["measured_provenance"] == "MEASURED"
    assert "s11" in decision.result["comparison"]


def test_advance_loop_step_rejects_external_measurement_with_no_approval(tmp_path: Path):
    touchstone_path = _write_measured_touchstone(tmp_path, name="no_approval")
    state = start_design_loop(REQUIREMENTS)
    state = _advance_to(state, DesignStep.MEASUREMENT, grant_intermediate_approvals=True)

    step_input = {"touchstone_file": str(touchstone_path)}
    with pytest.raises(OrchestrationError, match="Design-loop step advancement refused"):
        advance_loop_step(state, step_input)
    # Nothing advanced: still parked at MEASUREMENT, no decision recorded.
    assert state.current_step == DesignStep.MEASUREMENT.value


def test_advance_loop_step_has_no_instrument_injection_seam_left():
    """ticket #90 removed the instrument-control package, and with it the
    only reason advance_loop_step ever accepted test-only instrument-
    transport injection parameters (a pre-#90 straddle -- see git history).
    Passing either of the old parameter names now raises TypeError: there
    is no live-instrument path left for them to seam into."""
    state = start_design_loop(REQUIREMENTS)
    with pytest.raises(TypeError):
        advance_loop_step(state, {}, instrument_transport_factory=lambda r: None)
    with pytest.raises(TypeError):
        advance_loop_step(state, {}, instrument_confinement_check=lambda *a, **kw: None)


def test_external_measurement_missing_file_names_it_and_records_nothing(tmp_path: Path):
    missing_path = tmp_path / "missing.s2p"
    state = start_design_loop(REQUIREMENTS)
    state = _advance_to(state, DesignStep.MEASUREMENT, grant_intermediate_approvals=True)

    step_input = {"touchstone_file": str(missing_path)}
    fields = _fingerprint(state, DesignStep.MEASUREMENT, step_input)
    receipt = request_loop_step_approval(
        fields, approved_by="jane.engineer", approval_callback=lambda f: True
    )

    with pytest.raises(ExternalMeasurementError, match=re.escape(str(missing_path))):
        advance_loop_step(state, step_input, approval=receipt)
    # No evidence was recorded -- the loop is still parked at MEASUREMENT.
    assert state.current_step == DesignStep.MEASUREMENT.value
    assert all(d.step != DesignStep.MEASUREMENT.value for d in state.decisions)


def test_external_measurement_unreadable_file_names_it_and_records_nothing(tmp_path: Path):
    bad_path = tmp_path / "corrupt.s2p"
    bad_path.write_text("this is not a touchstone file at all\n")
    state = start_design_loop(REQUIREMENTS)
    state = _advance_to(state, DesignStep.MEASUREMENT, grant_intermediate_approvals=True)

    step_input = {"touchstone_file": str(bad_path)}
    fields = _fingerprint(state, DesignStep.MEASUREMENT, step_input)
    receipt = request_loop_step_approval(
        fields, approved_by="jane.engineer", approval_callback=lambda f: True
    )

    with pytest.raises(ExternalMeasurementError, match=re.escape(str(bad_path))):
        advance_loop_step(state, step_input, approval=receipt)
    assert state.current_step == DesignStep.MEASUREMENT.value
    assert all(d.step != DesignStep.MEASUREMENT.value for d in state.decisions)


def test_end_to_end_full_requirements_to_redesign_cycle(tmp_path: Path):
    """One full requirements -> redesign cycle through all nine DesignStep
    values, composing the REAL Phase 1/6/9/11 functions (rf_tools.
    calculations.patch_resonant_frequency_hz, simulation.nec2pp.
    run_nec2_simulation, optimization.rf_objectives.
    optimize_patch_length_for_target_frequency, measurement.external.
    record_external_measurement, rf_tools.correlation.
    correlate_simulation_measurement) against a fake NEC2++ executable and a
    real Touchstone file for MEASUREMENT -- ticket #90's acceptance
    criterion, verbatim: 'A full requirements-to-redesign loop cycle
    completes with no instrument involved.' There is no live-instrument
    path left in this codebase for MEASUREMENT to reach even if it wanted
    to (see measurement/external.py and ADR-0012/ADR-0013)."""
    state = start_design_loop(REQUIREMENTS)
    seen_steps = [DesignStep.REQUIREMENTS]

    state = _grant_and_advance(state, DesignStep.ARCHITECTURE)
    seen_steps.append(DesignStep.ARCHITECTURE)

    state = advance_loop_step(state, {"eps_r": 4.4, "w_m": 0.03, "h_m": 0.0016, "l_m": 0.0286})
    seen_steps.append(DesignStep.ANALYSIS)

    fake_nec2pp = _make_fake_nec2pp(tmp_path)
    state = advance_loop_step(
        state,
        {
            "geometry": _DIPOLE_GEOMETRY,
            "frequency_hz": 300e6,
            "executable": str(fake_nec2pp),
            "workdir": str(tmp_path / "nec2_run"),
        },
    )
    seen_steps.append(DesignStep.SIMULATION)

    state = advance_loop_step(
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
    seen_steps.append(DesignStep.OPTIMIZATION)

    state = advance_loop_step(
        state,
        {
            "requirement_id": "R1",
            "requirement": "resonant frequency within band",
            "method": "analysis",
            "expected": 2.45e9,
            "actual": state.decisions[-1].result["achieved_frequency_hz"],
            "status": "PASS",
            "notes": "within tolerance of optimized length",
        },
    )
    seen_steps.append(DesignStep.VERIFICATION)
    assert state.current_step == DesignStep.MEASUREMENT.value

    # --- MEASUREMENT: a Touchstone file brought back from external
    # testing -- the only shape this step accepts. ---
    touchstone_path = _write_measured_touchstone(tmp_path, name="full_cycle_external")
    measurement_input = {
        "touchstone_file": str(touchstone_path),
        "lab_report": "range-report-2026-09-03.pdf",
        "notes": "Outdoor range, 23C, calibrated with a known-good short/open/load standard.",
    }
    state = _grant_and_advance(state, DesignStep.MEASUREMENT, step_input_override=measurement_input)
    seen_steps.append(DesignStep.MEASUREMENT)
    assert state.current_step == DesignStep.CORRELATION.value
    assert state.decisions[-1].kind == "measurement"
    assert state.decisions[-1].provenance == "MEASURED"
    assert state.decisions[-1].approved_by == "jane.engineer"

    # --- CORRELATION (calls rf_tools.correlation, ungated, unmodified). ---
    simulated_override = {
        "frequency_hz": [2.0e9, 2.5e9, 3.0e9],
        "s_parameters": {"S11": ["0.1+0.01j", "0.2+0.02j", "0.3+0.03j"]},
        "z0": 50.0,
    }
    state = advance_loop_step(state, {"simulated": simulated_override})
    seen_steps.append(DesignStep.CORRELATION)
    assert state.current_step == DesignStep.REDESIGN_DECISION.value
    assert state.decisions[-1].kind == "correlation"
    assert state.decisions[-1].provenance == "CALCULATED"
    assert "s11" in state.decisions[-1].result["comparison"]

    # --- REDESIGN_DECISION (gated) ---
    redesign_input = {
        "decision": "accept the design as-is",
        "rationale": "measured and correlated results meet the customer requirement",
        "next_action": "accept_design",
    }
    state = _grant_and_advance(
        state, DesignStep.REDESIGN_DECISION, step_input_override=redesign_input
    )
    seen_steps.append(DesignStep.REDESIGN_DECISION)

    assert state.completed is True
    assert set(seen_steps) == set(DesignStep)
    assert [DesignStep(d.step) for d in state.decisions] == list(STEP_ORDER)

    import json

    json.dumps(state.to_dict())


# ---------------------------------------------------------------------------
# Shared test helpers.
# ---------------------------------------------------------------------------


def _fingerprint(state: DesignLoopState, step: DesignStep, step_input: dict) -> dict:
    return {
        "loop_id": state.loop_id,
        "iteration": state.iteration,
        "step": step.value,
        "content": step_input,
    }


def _valid_step_input(_state: DesignLoopState, step: DesignStep) -> dict:
    """The minimum valid step_input for `step`, usable regardless of what
    (if anything) earlier steps recorded -- used by the smaller, focused
    tests below, which only need a syntactically valid input to prove the
    approval gate or a step's own validation (not another step's composed
    action) is what's being tested. Covers every step these smaller tests
    actually exercise; SIMULATION/OPTIMIZATION/CORRELATION are only
    exercised for real in the dedicated end-to-end test (Group 5), which
    builds their inputs itself.

    MEASUREMENT's placeholder is safe only because every caller of this
    case attempts the step with no approval -- see the case's own
    comment."""
    if step is DesignStep.ARCHITECTURE:
        return {
            "decision": "rectangular microstrip patch on FR4",
            "rationale": "meets band/gain target with a simple, low-cost fabrication",
            "eps_r": 4.4,
            "w_m": 0.03,
            "h_m": 0.0016,
        }
    if step is DesignStep.ANALYSIS:
        return {"eps_r": 4.4, "w_m": 0.03, "h_m": 0.0016, "l_m": 0.0286}
    if step is DesignStep.VERIFICATION:
        return {
            "requirement_id": "R1",
            "requirement": "gain >= 5 dBi",
            "method": "analysis",
            "expected": 5.0,
            "actual": 5.2,
            "status": "PASS",
        }
    if step is DesignStep.MEASUREMENT:
        # A placeholder path, not a real file -- fine here, since every
        # caller of this case (see this function's own docstring) attempts
        # the step with NO approval, so the loop-level gate rejects it
        # before _handle_measurement ever reads the path.
        return {"touchstone_file": "/nonexistent/placeholder.s2p"}
    if step is DesignStep.REDESIGN_DECISION:
        return {
            "decision": "accept the design as-is",
            "rationale": "meets the customer requirement",
            "next_action": "accept_design",
        }
    raise AssertionError(f"_valid_step_input has no case for {step!r}")


def _grant_and_advance(
    state: DesignLoopState, step: DesignStep, step_input_override: dict | None = None
) -> DesignLoopState:
    """Advance past `step` for real (state.current_step must equal it),
    via the real handler, granting a real approval first if `step` is
    gated."""
    assert state.current_step == step.value
    step_input = step_input_override or _valid_step_input(state, step)
    approval = None
    if step in GATED_STEPS:
        fields = _fingerprint(state, step, step_input)
        approval = request_loop_step_approval(
            fields, approved_by="jane.engineer", approval_callback=lambda f: True
        )
    return advance_loop_step(state, step_input, approval=approval)


def _advance_to(
    state: DesignLoopState, target: DesignStep, grant_intermediate_approvals: bool = True
) -> DesignLoopState:
    """Jump `state.current_step` directly to `target`, WITHOUT executing
    any intermediate step's real action -- these smaller, focused tests
    care about the target step's own behavior (its approval gate, its own
    validation, pending_approval's computation), not about whether earlier
    steps' recorded decisions are individually realistic. A genuine,
    real, step-by-step walk through every step (including SIMULATION's
    fake nec2++ executable and MEASUREMENT's real Touchstone file) is
    exercised once, in full, by the dedicated end-to-end test (Group 5)
    below -- this helper deliberately does not duplicate that."""
    del grant_intermediate_approvals  # kept for call-site readability only
    return _dc_replace(state, current_step=target.value)


def _run_full_cycle_up_to_redesign(state: DesignLoopState) -> DesignLoopState:
    return _advance_to(state, DesignStep.REDESIGN_DECISION)
