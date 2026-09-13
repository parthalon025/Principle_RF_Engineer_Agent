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
     functions (rf_tools.patch_synthesis.patch_resonant_frequency_hz,
     simulation.nec2pp.run_nec2_simulation, optimization.rf_objectives.
     optimize_patch_length_for_target_frequency, measurement.external.
     record_external_measurement, rf_tools.correlation.
     correlate_simulation_measurement) against a fake NEC2++ executable
     (tests/test_nec2pp.py's own pattern) and a real Touchstone file for
     MEASUREMENT (ticket #90: the design loop has no live-instrument path
     left -- see measurement/external.py and ADR-0012/ADR-0013).
"""

import re
from dataclasses import replace as _dc_replace
from pathlib import Path
from typing import Any

import numpy as np
import pytest
import skrf as rf
from conftest import make_fake_executable

import designs.design_families as design_families_module
import orchestration.design_loop as design_loop_module
from designs.element_alphabet import (
    fetch_symbol_entries,
    insert_process_record,
    insert_symbol_entry,
)
from designs.material_properties import FR4_SEED_ENTRIES, resolve_material_property
from designs.requirement_targets import (
    confirm_host_ground_plane,
    propose_host_ground_plane,
    propose_intended_effect,
    propose_target,
)
from designs.requirements_document import (
    DocumentStatus,
    draft_requirements_document,
    extract_requirement_fields,
    revise_requirements_document,
)
from measurement.external import ExternalMeasurementError
from optimization.combinatorial import CombinatorialPlacementResult, SymbolOption
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
    _any_requirement_confirms_host_ground_plane,
    _combinatorial_result_to_dict,
    _optimizer_class_for,
    _require_reflector_or_confirmed_host_ground_plane,
    _simulation_adapter_for,
    advance_loop_step,
    start_design_loop,
)
from simulation.base import SimulatorError as _SimulatorError
from simulation.meep import (
    PERIODIC_ABSORBER_VALIDITY as MEEP_PERIODIC_ABSORBER_VALIDITY,
)
from simulation.meep import (
    periodic_absorber_capability_gaps as meep_periodic_absorber_capability_gaps,
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

    new_state = advance_loop_step(
        state, step_input, approval=receipt_dict, requirements_document_status="CONFIRMED"
    )
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
    on any decision -- from_dict must still load it, but it must NOT guess
    which round produced it. A pre-#88 dump could have come from any round
    (issue #135): filling the blank with 1 would misrepresent a decision
    genuinely recorded in round 5 as round 1. from_dict defaults the
    missing value to None -- "nobody recorded this" -- instead."""
    state = start_design_loop(REQUIREMENTS)
    legacy_dict = state.to_dict()
    for decision_dict in legacy_dict["decisions"]:
        del decision_dict["iteration"]

    restored = DesignLoopState.from_dict(legacy_dict)
    assert restored.decisions[0].iteration is None
    assert isinstance(restored.decisions[0], LoopDecision)


def test_loop_decision_from_dict_keeps_a_real_recorded_iteration():
    """A decision that DOES carry an `iteration` field (every dump from
    issue #88 onward) must still round-trip to its real value, not be
    swept into the same None bucket as a genuinely unknown one."""
    state = start_design_loop(REQUIREMENTS)
    as_dict = state.to_dict()
    assert as_dict["decisions"][0]["iteration"] == 1

    restored = DesignLoopState.from_dict(as_dict)
    assert restored.decisions[0].iteration == 1


def test_grouping_decisions_by_iteration_treats_none_as_its_own_case():
    """A mixed old/new decision list -- some decisions carry a real
    `iteration` (freshly recorded, or a post-#135 dump), others carry
    `None` (a pre-#88 dump with no round recorded at all, issue #135).
    Filtering for "this round's decisions" must not lump the unknown-round
    decision into round 1's bucket, and filtering for "round 1's
    decisions" must not include it either -- it belongs in neither."""
    now = 0.0
    unknown_round = LoopDecision(
        step=DesignStep.ARCHITECTURE.value,
        kind="architecture_decision",
        input={},
        result={"decision": "legacy, pre-#88"},
        provenance=None,
        approved_by="a.human",
        recorded_at=now,
        iteration=None,
    )
    round_one = LoopDecision(
        step=DesignStep.ANALYSIS.value,
        kind="calculation",
        input={},
        result={},
        provenance="CALCULATED",
        approved_by=None,
        recorded_at=now,
        iteration=1,
    )
    round_two = LoopDecision(
        step=DesignStep.ANALYSIS.value,
        kind="calculation",
        input={},
        result={},
        provenance="CALCULATED",
        approved_by=None,
        recorded_at=now,
        iteration=2,
    )
    decisions = [unknown_round, round_one, round_two]

    round_1_decisions = [d for d in decisions if d.iteration == 1]
    round_2_decisions = [d for d in decisions if d.iteration == 2]
    unknown_decisions = [d for d in decisions if d.iteration is None]

    assert round_1_decisions == [round_one]
    assert round_2_decisions == [round_two]
    assert unknown_decisions == [unknown_round]


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


def test_from_dict_raises_named_error_on_missing_version():
    """An old-shaped DesignLoopState dict missing the version field should
    fail with a clear, named error (not a bare KeyError) when from_dict
    attempts to load it. This proves that schema changes are caught
    explicitly rather than silently collapsing into undiagnosable
    KeyErrors."""
    state = start_design_loop(REQUIREMENTS)
    old_shaped_dict = state.to_dict()
    # Simulate an old snapshot missing the version key
    del old_shaped_dict["version"]

    # Should raise DesignLoopStateVersionError, not bare KeyError
    with pytest.raises(design_loop_module.DesignLoopStateVersionError):
        DesignLoopState.from_dict(old_shaped_dict)


def test_from_dict_raises_named_error_on_mismatched_version():
    """A DesignLoopState dict with a mismatched version should fail with a
    clear, named error (not a bare KeyError or silent truncation)."""
    state = start_design_loop(REQUIREMENTS)
    new_dict = state.to_dict()
    # Simulate a future version
    new_dict["version"] = 999

    # Should raise DesignLoopStateVersionError, not silently accept it
    with pytest.raises(design_loop_module.DesignLoopStateVersionError):
        DesignLoopState.from_dict(new_dict)


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


def test_architecture_requires_a_design_family():
    """#161: design_family is a required, structured slot on the
    ARCHITECTURE decision -- alongside the existing free-form decision/
    rationale prose, not replacing it -- so #150/#151 have a grouping key
    to key off of without parsing prose. No enum/registry validation yet
    (docs/adr/0018 is the separate, harder ticket for that): a bare string
    is enough, so a step_input missing the key entirely is the only
    rejection this ticket adds."""
    state = start_design_loop(REQUIREMENTS)
    step_input = {
        "decision": "rectangular microstrip patch on FR4",
        "rationale": "meets band/gain target with a simple, low-cost fabrication",
    }
    fields = _fingerprint(state, DesignStep.ARCHITECTURE, step_input)
    receipt = request_loop_step_approval(
        fields, approved_by="jane", approval_callback=lambda f: True
    )
    with pytest.raises(DesignLoopValidationError, match="design_family"):
        advance_loop_step(
            state, step_input, approval=receipt, requirements_document_status="CONFIRMED"
        )


def test_architecture_decision_records_the_design_family_alongside_decision_and_rationale():
    state = start_design_loop(REQUIREMENTS)
    step_input = {
        "decision": "rectangular microstrip patch on FR4",
        "rationale": "meets band/gain target with a simple, low-cost fabrication",
        "design_family": "patch_antenna",
    }
    state = _grant_and_advance(state, DesignStep.ARCHITECTURE, step_input_override=step_input)

    architecture_decision = state.decisions[-1]
    assert architecture_decision.kind == "architecture_decision"
    assert architecture_decision.result["design_family"] == "patch_antenna"
    # The existing prose fields are still there, not replaced by the new
    # structured field.
    assert architecture_decision.result["decision"] == step_input["decision"]
    assert architecture_decision.result["rationale"] == step_input["rationale"]


# ---------------------------------------------------------------------------
# Issue #322 (ADR-0021; ADR-0025's 2026-09-08 correction, narrowed further):
# an ARCHITECTURE/REDESIGN_DECISION step_input may carry an optional
# `considered_and_dropped` ledger. `reason_kind="capability-verdict"` may
# ONLY be recorded for a family excluded by its own characterised validity
# box, evaluated against a property the design's REQUIREMENTS themselves
# state -- never against configured shop equipment/ink/material.
# ---------------------------------------------------------------------------

# A requirement stating a host curvature that VIOLATES S <= 2*theta_max*R
# for a 45-degree-stable element: arc_length_m=0.30 > 2*45deg*0.10 == ~0.157.
_CURVATURE_REQUIREMENTS = {
    "R1": {
        "requirement": "conform to a 100 mm radius housing across a 300 mm bend",
        "curvature": {"arc_length_m": 0.30, "host_radius_m": 0.10},
    }
}


def _capability_verdict_entry(**overrides: Any) -> dict[str, Any]:
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


def _architecture_step_input(considered_and_dropped: list | None = None) -> dict[str, Any]:
    step_input = {
        "decision": "printed carbon absorber patch",
        "rationale": "the only family whose curvature validity box the host survives",
        "design_family": "patch_antenna",
    }
    if considered_and_dropped is not None:
        step_input["considered_and_dropped"] = considered_and_dropped
    return step_input


def test_architecture_records_a_valid_capability_verdict_ledger_entry():
    state = start_design_loop(_CURVATURE_REQUIREMENTS)
    step_input = _architecture_step_input([_capability_verdict_entry()])
    state = _grant_and_advance(state, DesignStep.ARCHITECTURE, step_input_override=step_input)

    recorded = state.decisions[-1].result["considered_and_dropped"]
    assert recorded == [_capability_verdict_entry()]


def test_architecture_accepts_a_ledger_with_no_capability_verdict_entries():
    """human-decision/engineering-judgment entries carry none of the extra
    capability-verdict fields, and neither needs requirements to say
    anything about curvature at all."""
    state = start_design_loop(REQUIREMENTS)
    ledger = [
        {
            "family": "printed_dipole",
            "verdict": "dropped",
            "reason": "narrowband versus the stated requirement",
            "reason_kind": "engineering-judgment",
        },
        {
            "family": "patch_antenna",
            "verdict": "kept",
            "reason": "meets band/gain target with simple, low-cost fabrication",
            "reason_kind": "engineering-judgment",
        },
    ]
    state = _grant_and_advance(
        state, DesignStep.ARCHITECTURE, step_input_override=_architecture_step_input(ledger)
    )
    assert state.decisions[-1].result["considered_and_dropped"] == ledger


def test_architecture_step_input_with_no_ledger_key_is_unaffected():
    """ADR-0025's own 'No gate': omitting considered_and_dropped entirely
    changes nothing about the step."""
    state = start_design_loop(REQUIREMENTS)
    state = _grant_and_advance(
        state, DesignStep.ARCHITECTURE, step_input_override=_architecture_step_input()
    )
    assert "considered_and_dropped" not in state.decisions[-1].result


def test_capability_verdict_rejected_when_curvature_does_not_actually_violate_the_bound():
    """The heart of issue #322's narrowing: capability-verdict cannot be
    used as a generic 'we don't like this family' label -- the requirement's
    own stated curvature must actually exceed S <= 2*theta_max*R for the
    entry's own stated theta_max_deg."""
    requirements = {
        "R1": {
            "requirement": "conform to a 500 mm radius housing across a 100 mm bend",
            "curvature": {"arc_length_m": 0.10, "host_radius_m": 0.50},  # comfortably inside
        }
    }
    state = start_design_loop(requirements)
    step_input = _architecture_step_input([_capability_verdict_entry()])
    with pytest.raises(DesignLoopValidationError, match="does not actually violate"):
        _grant_and_advance(state, DesignStep.ARCHITECTURE, step_input_override=step_input)


def test_capability_verdict_rejected_for_an_equipment_shaped_property():
    """Nothing else can produce reason_kind='capability-verdict' (issue
    #322 acceptance criterion 1): a property that is not a key the
    requirement itself states -- e.g. a shop-equipment fact like a printer's
    feature floor -- is rejected outright, never silently accepted."""
    state = start_design_loop(_CURVATURE_REQUIREMENTS)
    entry = _capability_verdict_entry(validity_box_property="printer_feature_floor_mm")
    step_input = _architecture_step_input([entry])
    with pytest.raises(DesignLoopValidationError, match="not a stated property"):
        _grant_and_advance(state, DesignStep.ARCHITECTURE, step_input_override=step_input)


def test_capability_verdict_rejected_for_an_unknown_requirement_id():
    state = start_design_loop(_CURVATURE_REQUIREMENTS)
    entry = _capability_verdict_entry(requirement_id="NOT-A-REAL-REQUIREMENT")
    step_input = _architecture_step_input([entry])
    with pytest.raises(
        DesignLoopValidationError, match="is not a key in this design's requirements"
    ):
        _grant_and_advance(state, DesignStep.ARCHITECTURE, step_input_override=step_input)


def test_capability_verdict_rejected_when_verdict_is_kept():
    """A family excluded by its own validity box is, by definition,
    dropped -- 'kept' + 'capability-verdict' is a contradiction issue #322
    catches rather than silently accepting."""
    state = start_design_loop(_CURVATURE_REQUIREMENTS)
    entry = _capability_verdict_entry(verdict="kept")
    step_input = _architecture_step_input([entry])
    with pytest.raises(DesignLoopValidationError, match="contradiction"):
        _grant_and_advance(state, DesignStep.ARCHITECTURE, step_input_override=step_input)


def test_capability_verdict_requires_requirement_id_and_validity_box_property():
    state = start_design_loop(_CURVATURE_REQUIREMENTS)
    entry = {
        "family": "reflection_phase_surface",
        "verdict": "dropped",
        "reason": "curvature exceeds the validity box",
        "reason_kind": "capability-verdict",
        # deliberately no requirement_id/validity_box_property
    }
    step_input = _architecture_step_input([entry])
    with pytest.raises(DesignLoopValidationError, match="missing required field"):
        _grant_and_advance(state, DesignStep.ARCHITECTURE, step_input_override=step_input)


def test_capability_verdict_curvature_requires_theta_max_deg():
    state = start_design_loop(_CURVATURE_REQUIREMENTS)
    entry = _capability_verdict_entry()
    del entry["theta_max_deg"]
    step_input = _architecture_step_input([entry])
    with pytest.raises(DesignLoopValidationError, match="theta_max_deg"):
        _grant_and_advance(state, DesignStep.ARCHITECTURE, step_input_override=step_input)


def test_ledger_entry_rejects_an_unknown_reason_kind():
    state = start_design_loop(REQUIREMENTS)
    entry = {
        "family": "patch_antenna",
        "verdict": "dropped",
        "reason": "we just didn't like it",
        "reason_kind": "vibes",
    }
    step_input = _architecture_step_input([entry])
    with pytest.raises(DesignLoopValidationError, match="reason_kind"):
        _grant_and_advance(state, DesignStep.ARCHITECTURE, step_input_override=step_input)


def test_ledger_entry_rejects_an_unknown_verdict():
    state = start_design_loop(REQUIREMENTS)
    entry = {
        "family": "patch_antenna",
        "verdict": "maybe",
        "reason": "still deciding",
        "reason_kind": "engineering-judgment",
    }
    step_input = _architecture_step_input([entry])
    with pytest.raises(DesignLoopValidationError, match="verdict"):
        _grant_and_advance(state, DesignStep.ARCHITECTURE, step_input_override=step_input)


def test_redesign_decision_also_validates_the_considered_and_dropped_ledger():
    """The same narrowing applies wherever the ledger can be written --
    ADR-0025's own batch record is not exclusive to ARCHITECTURE."""
    state = start_design_loop(_CURVATURE_REQUIREMENTS)
    state = _grant_and_advance(
        state, DesignStep.ARCHITECTURE, step_input_override=_architecture_step_input()
    )
    state = _advance_to(state, DesignStep.REDESIGN_DECISION)
    step_input = {
        "decision": "abandon this geometry, try another patch variant",
        "rationale": "the first geometry cannot meet the gain target",
        "next_action": "iterate",
        "considered_and_dropped": [
            _capability_verdict_entry(validity_box_property="printer_feature_floor_mm")
        ],
    }
    with pytest.raises(DesignLoopValidationError, match="not a stated property"):
        _grant_and_advance(state, DesignStep.REDESIGN_DECISION, step_input_override=step_input)


def test_capability_verdict_holds_flips_false_when_curvature_changes():
    """capability_verdict_holds is the exact mechanism
    orchestration.tooling.reevaluate_capability_verdicts (issue #322 -- "re-
    evaluated every run") reuses -- exercised directly here as a pure
    function, no database required."""
    entry = _capability_verdict_entry()
    still_violating = _CURVATURE_REQUIREMENTS
    assert design_loop_module.capability_verdict_holds(entry, still_violating) is True

    now_comfortable = {
        "R1": {
            "requirement": "conform to a 100 mm radius housing across a 300 mm bend",
            "curvature": {"arc_length_m": 0.05, "host_radius_m": 0.10},  # no longer violates
        }
    }
    assert design_loop_module.capability_verdict_holds(entry, now_comfortable) is False

    requirement_removed = {}
    assert design_loop_module.capability_verdict_holds(entry, requirement_removed) is False


# ---------------------------------------------------------------------------
# Issue #324 (ADR-0025's 2026-09-09 correction; CONTEXT.md's "Capability
# warning"): a wholly separate mechanism from the considered_and_dropped
# ledger above -- a design candidate stays `kept` and instead carries a
# `capability_warnings` entry stating, in Requirement-target shape
# (value/comparator/unit), the gap between a stated need and what the
# currently configured Fabrication capability / Ink-property library /
# Material-property library selection actually provides. Never drops a
# candidate, and never shares a reason_kind or a list with capability-verdict
# -- see the coexistence test at the end of this group (issue #324
# acceptance criterion 3).
# ---------------------------------------------------------------------------


def _capability_warning_entry(**overrides: Any) -> dict[str, Any]:
    entry = {
        "family": "patch_antenna",
        "capability_kind": "fabrication",
        "capability_property": "min_feature_size_mm",
        "value": 0.2,
        "comparator": "AT_MOST",
        "unit": "mm",
        # Issue #515/#496: the charter's own three-part warning contract
        # (assumed / costs / cheapest_test), same field names as
        # rf_tools/absorber.py's/rf_tools/transmissive_absorber.py's
        # existing `validity` entries, in place of the single freeform
        # `reason` this fixture used to carry.
        "assumed": "needs 0.2 mm features; loaded printer achieves 0.5 mm",
        "costs": "features finer than 0.5 mm will not resolve; the printed "
        "geometry will not match the design",
        "cheapest_test": "print a resolution test coupon on the loaded printer",
    }
    entry.update(overrides)
    return entry


def test_architecture_records_a_valid_capability_warning_entry():
    state = start_design_loop(REQUIREMENTS)
    step_input = _architecture_step_input()
    step_input["capability_warnings"] = [_capability_warning_entry()]
    state = _grant_and_advance(state, DesignStep.ARCHITECTURE, step_input_override=step_input)

    recorded = state.decisions[-1].result["capability_warnings"]
    assert recorded == [_capability_warning_entry()]


def test_architecture_step_input_with_no_capability_warnings_key_is_unaffected():
    """No gate, same as considered_and_dropped: a step_input that never
    mentions capability_warnings is untouched -- attaching one is never
    required."""
    state = start_design_loop(REQUIREMENTS)
    state = _grant_and_advance(
        state, DesignStep.ARCHITECTURE, step_input_override=_architecture_step_input()
    )
    assert "capability_warnings" not in state.decisions[-1].result


def test_capability_warning_rejected_for_missing_required_field():
    state = start_design_loop(REQUIREMENTS)
    entry = _capability_warning_entry()
    del entry["capability_property"]
    step_input = _architecture_step_input()
    step_input["capability_warnings"] = [entry]
    with pytest.raises(DesignLoopValidationError, match="missing required field"):
        _grant_and_advance(state, DesignStep.ARCHITECTURE, step_input_override=step_input)


@pytest.mark.parametrize("missing_field", ["assumed", "costs", "cheapest_test"])
def test_capability_warning_rejected_for_missing_any_one_of_the_three_required_parts(
    missing_field,
):
    """Issue #496: the charter's own three-part warning contract (what is
    assumed / what it costs if that assumption is wrong / the cheapest way
    to find out) must be structurally enforced, not foldable into one
    freeform field where a caller could omit one part unnoticed -- a
    warning missing any single one of `assumed`/`costs`/`cheapest_test` is
    rejected."""
    state = start_design_loop(REQUIREMENTS)
    entry = _capability_warning_entry()
    del entry[missing_field]
    step_input = _architecture_step_input()
    step_input["capability_warnings"] = [entry]
    with pytest.raises(DesignLoopValidationError, match="missing required field"):
        _grant_and_advance(state, DesignStep.ARCHITECTURE, step_input_override=step_input)


def test_capability_warning_rejected_for_an_unknown_capability_kind():
    state = start_design_loop(REQUIREMENTS)
    entry = _capability_warning_entry(capability_kind="printer")
    step_input = _architecture_step_input()
    step_input["capability_warnings"] = [entry]
    with pytest.raises(DesignLoopValidationError, match="capability_kind"):
        _grant_and_advance(state, DesignStep.ARCHITECTURE, step_input_override=step_input)


def test_capability_warning_rejected_for_an_invalid_requirement_target_shape():
    """The value/comparator/unit fields are validated by the exact same
    designs.requirement_targets.propose_target a Requirement target uses --
    issue #324's 'Stated in Requirement target shape' -- so an invalid
    comparator is rejected here rather than silently accepted."""
    state = start_design_loop(REQUIREMENTS)
    entry = _capability_warning_entry(comparator="GREATER_THAN")
    step_input = _architecture_step_input()
    step_input["capability_warnings"] = [entry]
    with pytest.raises(DesignLoopValidationError, match="Requirement target shape"):
        _grant_and_advance(state, DesignStep.ARCHITECTURE, step_input_override=step_input)


def test_redesign_decision_also_validates_capability_warnings():
    state = start_design_loop(REQUIREMENTS)
    state = _grant_and_advance(
        state, DesignStep.ARCHITECTURE, step_input_override=_architecture_step_input()
    )
    state = _advance_to(state, DesignStep.REDESIGN_DECISION)
    step_input = {
        "decision": "abandon this geometry, try another patch variant",
        "rationale": "the first geometry cannot meet the gain target",
        "next_action": "iterate",
        "capability_warnings": [_capability_warning_entry(capability_kind="printer")],
    }
    with pytest.raises(DesignLoopValidationError, match="capability_kind"):
        _grant_and_advance(state, DesignStep.REDESIGN_DECISION, step_input_override=step_input)


def test_capability_warning_holds_true_while_current_configuration_still_falls_short():
    entry = _capability_warning_entry()
    still_short = {"fabrication": {"min_feature_size_mm": 0.5}}
    assert design_loop_module.capability_warning_holds(entry, still_short) is True


def test_capability_warning_holds_clears_once_configuration_improves_enough():
    entry = _capability_warning_entry()
    now_meets_it = {"fabrication": {"min_feature_size_mm": 0.15}}
    assert design_loop_module.capability_warning_holds(entry, now_meets_it) is False


def test_capability_warning_holds_stays_true_when_configuration_data_is_missing():
    """Missing/unconfirmed configuration data never silently clears a
    warning -- the opposite fail-safe direction from
    capability_verdict_holds, since silently clearing a warning (a
    candidate that still cannot be built looking clean) is the dangerous
    failure here, not silently keeping one."""
    entry = _capability_warning_entry()
    assert design_loop_module.capability_warning_holds(entry, {}) is True
    assert design_loop_module.capability_warning_holds(entry, {"ink": {}}) is True


def test_capability_verdict_and_capability_warning_coexist_on_the_same_ledger():
    """Issue #324 acceptance criterion 3: a capability-verdict entry never
    gains a Capability warning and vice versa -- both can be recorded on the
    same design's decision without either affecting the other."""
    state = start_design_loop(_CURVATURE_REQUIREMENTS)
    step_input = _architecture_step_input([_capability_verdict_entry()])
    step_input["capability_warnings"] = [_capability_warning_entry()]
    state = _grant_and_advance(state, DesignStep.ARCHITECTURE, step_input_override=step_input)

    result = state.decisions[-1].result
    assert result["considered_and_dropped"] == [_capability_verdict_entry()]
    assert result["capability_warnings"] == [_capability_warning_entry()]


# ---------------------------------------------------------------------------
# Group 2b (issue #154, ADR-0015): ANALYSIS wired to the Material-property
# library -- a caller may supply 'material_property' (a
# designs.material_properties.resolve_material_property result) instead of
# a bare 'eps_r' number. A confident single-value lookup behaves exactly
# like the existing eps_r path; a Family fallback bracket or a set of
# disagreeing citations is computed at BOTH ends of the range (ADR-0015's
# Consequences section), never collapsed to one number.
# ---------------------------------------------------------------------------


def test_analysis_accepts_material_property_in_place_of_eps_r():
    material_property = resolve_material_property(
        FR4_SEED_ENTRIES, material="FR4", property_name="eps_r", frequency_hz=9.5e9
    )
    assert material_property["low"] != material_property["high"]  # sanity: this is the spread case

    state = start_design_loop(REQUIREMENTS)
    state = _grant_and_advance(state, DesignStep.ARCHITECTURE)
    state = advance_loop_step(
        state,
        {"material_property": material_property, "w_m": 0.03, "h_m": 0.0016, "l_m": 0.0286},
    )
    result = state.decisions[-1].result
    assert "resonant_frequency_hz" not in result
    assert result["resonant_frequency_hz_low"] < result["resonant_frequency_hz_high"]
    assert result["material_property"] == material_property
    assert state.decisions[-1].provenance == "CALCULATED"


def test_analysis_material_property_degenerates_to_a_single_value_for_one_confident_entry():
    material_property = resolve_material_property(
        FR4_SEED_ENTRIES, material="FR4", property_name="eps_r", frequency_hz=9.5e9
    )
    material_property = dict(
        material_property, low=4.4, high=4.4, entries=[]
    )  # a confident, agreed value

    state = start_design_loop(REQUIREMENTS)
    state = _grant_and_advance(state, DesignStep.ARCHITECTURE)
    step_input_material = {
        "material_property": material_property,
        "w_m": 0.03,
        "h_m": 0.0016,
        "l_m": 0.0286,
    }
    state_material = advance_loop_step(state, step_input_material)
    result_material = state_material.decisions[-1].result

    state_direct = advance_loop_step(
        state, {"eps_r": 4.4, "w_m": 0.03, "h_m": 0.0016, "l_m": 0.0286}
    )
    result_direct = state_direct.decisions[-1].result

    assert result_material["resonant_frequency_hz"] == result_direct["resonant_frequency_hz"]
    assert "resonant_frequency_hz_low" not in result_material


def test_analysis_rejects_both_eps_r_and_material_property():
    material_property = resolve_material_property(
        FR4_SEED_ENTRIES, material="FR4", property_name="eps_r", frequency_hz=9.5e9
    )
    state = start_design_loop(REQUIREMENTS)
    state = _grant_and_advance(state, DesignStep.ARCHITECTURE)
    with pytest.raises(DesignLoopValidationError, match="exactly one"):
        advance_loop_step(
            state,
            {
                "eps_r": 4.4,
                "material_property": material_property,
                "w_m": 0.03,
                "h_m": 0.0016,
                "l_m": 0.0286,
            },
        )


def test_analysis_rejects_a_material_property_with_no_library_data():
    material_property = resolve_material_property(
        [], material="unobtainium foam", property_name="eps_r", frequency_hz=9.5e9
    )
    assert material_property["status"] == "no_data"
    state = start_design_loop(REQUIREMENTS)
    state = _grant_and_advance(state, DesignStep.ARCHITECTURE)
    with pytest.raises(DesignLoopValidationError, match="no usable"):
        advance_loop_step(
            state,
            {"material_property": material_property, "w_m": 0.03, "h_m": 0.0016, "l_m": 0.0286},
        )


# ---------------------------------------------------------------------------
# Group 2c (issue #101): SIMULATION derives VSWR/return loss from its own
# feed-point impedance, against an explicitly caller-stated reference
# impedance. These stub out run_nec2_simulation itself (monkeypatching the
# name orchestration/design_loop.py imports it under) rather than driving a
# real/fake nec2++ subprocess -- that subprocess path is exercised for real
# by the end-to-end test below (Group 5); isolating this arithmetic from
# subprocess execution keeps these tests fast and independent of whether a
# shell can exec a Python script directly (which native Windows cannot do
# without going through the interpreter -- issue #159's own tracked gap,
# see test_end_to_end_full_requirements_to_redesign_cycle below).
# ---------------------------------------------------------------------------


def _fake_nec2_result(
    resistance_ohms: float = 82.6979, reactance_ohms: float = 46.3060, **overrides
):
    """A run_nec2_simulation-shaped return value, carrying the same
    feed-point impedance tests/test_nec2pp.py's/this file's own NEC-2
    User's Guide 'Example 1' sample output parses to, by default."""
    result = {
        "provenance": "SIMULATED",
        "impedance": {
            "tag": 0,
            "segment": 4,
            "voltage_real_v": 1.0,
            "voltage_imag_v": 0.0,
            "current_real_a": 0.00920585,
            "current_imag_a": -0.00515474,
            "resistance_ohms": resistance_ohms,
            "reactance_ohms": reactance_ohms,
            "admittance_real_mhos": 0.00920585,
            "admittance_imag_mhos": -0.00515474,
            "power_w": 0.00460292,
        },
        "pattern": [],
        "gain_dbi": None,
        "average_power_gain_linear": None,
        "simulator": "NEC2++",
        "status": "COMPLETED",
        "workdir": "/fake/workdir",
        "input_file": "/fake/workdir/model.nec",
    }
    result.update(overrides)
    return result


def _advance_to_simulation(monkeypatch, fake_result) -> DesignLoopState:
    monkeypatch.setattr(design_loop_module, "_run_nec2_simulation", lambda **kw: fake_result)
    state = start_design_loop(REQUIREMENTS)
    state = _grant_and_advance(state, DesignStep.ARCHITECTURE)
    state = advance_loop_step(state, _valid_step_input(state, DesignStep.ANALYSIS))
    assert state.current_step == DesignStep.SIMULATION.value
    return state


def test_simulation_requires_reference_impedance_ohms_explicitly(monkeypatch):
    state = _advance_to_simulation(monkeypatch, _fake_nec2_result())
    with pytest.raises(DesignLoopValidationError, match="missing required field"):
        advance_loop_step(state, {"geometry": _DIPOLE_GEOMETRY, "frequency_hz": 300e6})


def test_simulation_derives_vswr_and_return_loss_from_feed_point_impedance(monkeypatch):
    state = _advance_to_simulation(monkeypatch, _fake_nec2_result())
    state = advance_loop_step(
        state,
        {
            "geometry": _DIPOLE_GEOMETRY,
            "frequency_hz": 300e6,
            "reference_impedance_ohms": 50.0,
        },
    )
    decision = state.decisions[-1]
    assert decision.step == DesignStep.SIMULATION.value
    assert decision.provenance == "SIMULATED"
    # Independently computed from (82.6979 + j46.3060) referenced to 50
    # ohms -- see tests/test_calculations.py's own
    # test_reflection_coefficient_of_a_known_complex_impedance.
    assert decision.result["reflection_coefficient_magnitude"] == pytest.approx(0.40333507086482756)
    assert decision.result["vswr"] == pytest.approx(2.35196506839923)
    assert decision.result["return_loss_db"] == pytest.approx(7.8866802699461624)
    # The reference impedance is recorded verbatim alongside the value --
    # never silently assumed (issue #101's own acceptance criterion).
    assert decision.result["reference_impedance_ohms"] == 50.0
    assert decision.result["frequency_hz"] == 300e6
    # NEC2++'s adapter only ever solves at one frequency -- honestly
    # flagged, so a reader never mistakes this for a swept-band answer.
    assert decision.result["single_frequency_prediction"] is True


def test_simulation_reference_impedance_is_never_silently_defaulted_to_50(monkeypatch):
    """The same feed-point impedance, scored against a DIFFERENT explicit
    reference impedance, produces a materially different VSWR -- proving
    the value actually came from step_input, not a hardcoded 50 ohms."""
    state = _advance_to_simulation(monkeypatch, _fake_nec2_result())
    state = advance_loop_step(
        state,
        {
            "geometry": _DIPOLE_GEOMETRY,
            "frequency_hz": 300e6,
            "reference_impedance_ohms": 75.0,
        },
    )
    decision = state.decisions[-1]
    assert decision.result["reference_impedance_ohms"] == 75.0
    assert decision.result["vswr"] != pytest.approx(2.35196506839923)


def test_simulation_vswr_undefined_at_total_mismatch_is_recorded_as_none(monkeypatch):
    # A short-circuit feed point (0 ohms): |Gamma| = 1 exactly -- VSWR is
    # mathematically infinite/undefined (vswr_from_gamma's own domain is
    # [0, 1)), so it is recorded as None rather than raising and failing
    # the whole step. Return loss (0 dB at total reflection) is finite and
    # still computed.
    state = _advance_to_simulation(
        monkeypatch, _fake_nec2_result(resistance_ohms=0.0, reactance_ohms=0.0)
    )
    state = advance_loop_step(
        state,
        {
            "geometry": _DIPOLE_GEOMETRY,
            "frequency_hz": 300e6,
            "reference_impedance_ohms": 50.0,
        },
    )
    decision = state.decisions[-1]
    assert decision.result["vswr"] is None
    assert decision.result["return_loss_db"] == pytest.approx(0.0)


def test_simulation_return_loss_undefined_at_perfect_match_is_recorded_as_none(monkeypatch):
    # A feed point exactly at the reference impedance: |Gamma| = 0 -- VSWR
    # is a valid, finite 1.0, but return loss (-20*log10(0)) is
    # mathematically infinite/undefined, so it is recorded as None.
    state = _advance_to_simulation(
        monkeypatch, _fake_nec2_result(resistance_ohms=50.0, reactance_ohms=0.0)
    )
    state = advance_loop_step(
        state,
        {
            "geometry": _DIPOLE_GEOMETRY,
            "frequency_hz": 300e6,
            "reference_impedance_ohms": 50.0,
        },
    )
    decision = state.decisions[-1]
    assert decision.result["vswr"] == pytest.approx(1.0)
    assert decision.result["return_loss_db"] is None


def test_simulation_with_no_parsed_impedance_records_no_vswr_but_still_advances(monkeypatch):
    # A defensive case: if run_nec2_simulation's own parse ever fails to
    # find an ANTENNA INPUT PARAMETERS block (impedance=None), there is
    # nothing to derive VSWR/return loss from -- recorded as None, not
    # raised, since the underlying simulation itself still completed.
    state = _advance_to_simulation(monkeypatch, _fake_nec2_result(impedance=None))
    state = advance_loop_step(
        state,
        {
            "geometry": _DIPOLE_GEOMETRY,
            "frequency_hz": 300e6,
            "reference_impedance_ohms": 50.0,
        },
    )
    decision = state.decisions[-1]
    assert decision.result["vswr"] is None
    assert decision.result["return_loss_db"] is None
    assert decision.result["reflection_coefficient_magnitude"] is None
    assert decision.result["reference_impedance_ohms"] == 50.0


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


def test_correlation_passes_known_tolerance_db_through_to_the_recorded_decision(
    tmp_path: Path,
):
    """issue #254: known_tolerance_db in step_input reaches
    rf_tools.correlation.correlate_simulation_measurement the same
    pass-through way fixture_path/output_fixture_path/
    temperature_tolerance_c already do, and its mechanical, three-value
    tolerance_comparison result (never a model-vs-design verdict -- see
    docs/adr/0009) shows up in the recorded decision's result."""
    touchstone_path = _write_measured_touchstone(tmp_path, name="for_tolerance")
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
    state = advance_loop_step(
        state,
        {"simulated": simulated_override, "known_tolerance_db": 0.01},
    )

    decision = state.decisions[-1]
    assert decision.kind == "correlation"
    comparison = decision.result["comparison"]
    assert comparison["s11"]["tolerance_comparison"] == "EXCEEDS_KNOWN_TOLERANCE"
    assert "tolerance_comparison_note" in decision.result
    allowed = {"WITHIN_KNOWN_TOLERANCE", "EXCEEDS_KNOWN_TOLERANCE", "NO_TOLERANCE_ON_RECORD"}
    assert comparison["s11"]["tolerance_comparison"] in allowed


def test_correlation_omits_known_tolerance_db_still_records_no_data_by_default(tmp_path: Path):
    """User story 15: a run that never supplies known_tolerance_db behaves
    exactly like it did before this feature -- no new required field, no
    new gate -- and each S-parameter honestly reads NO_TOLERANCE_ON_RECORD
    rather than a fabricated pass/fail."""
    touchstone_path = _write_measured_touchstone(tmp_path, name="no_tolerance_supplied")
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
    state = advance_loop_step(state, {"simulated": simulated_override})

    decision = state.decisions[-1]
    assert decision.result["comparison"]["s11"]["tolerance_comparison"] == "NO_TOLERANCE_ON_RECORD"


def test_redesign_decision_step_input_shape_is_unchanged_by_tolerance_comparison():
    """Regression guard for issue #254's own scope boundary: this feature
    lives entirely in the ungated CORRELATION step (rf_tools/correlation.py)
    and orchestration/design_loop.py's _handle_correlation pass-through --
    it must leave REDESIGN_DECISION's required step_input fields,
    DesignLoopValidationError behavior, and the legal next_action values
    completely untouched (docs/adr/0009; issue #254 user story 16)."""
    assert REDESIGN_ACTIONS == frozenset({"iterate", "accept_design"})

    state = start_design_loop(REQUIREMENTS)
    state = _run_full_cycle_up_to_redesign(state)

    for missing_field in ("decision", "rationale", "next_action"):
        step_input = {
            "decision": "x",
            "rationale": "y",
            "next_action": "iterate",
        }
        del step_input[missing_field]
        fields = _fingerprint(state, DesignStep.REDESIGN_DECISION, step_input)
        receipt = request_loop_step_approval(
            fields, approved_by="jane", approval_callback=lambda f: True
        )
        with pytest.raises(DesignLoopValidationError, match="missing required field"):
            advance_loop_step(state, step_input, approval=receipt)

    # A known_tolerance_db-shaped extra field is not part of this step's
    # schema and must not be silently accepted as a substitute for the
    # real required fields, nor smuggle a fourth next_action value in.
    step_input = {
        "decision": "x",
        "rationale": "y",
        "next_action": "known_tolerance_db",
    }
    fields = _fingerprint(state, DesignStep.REDESIGN_DECISION, step_input)
    receipt = request_loop_step_approval(
        fields, approved_by="jane", approval_callback=lambda f: True
    )
    with pytest.raises(DesignLoopValidationError, match="next_action"):
        advance_loop_step(state, step_input, approval=receipt)


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

    with pytest.raises(ExternalMeasurementError, match=re.escape(repr(str(missing_path)))):
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

    with pytest.raises(ExternalMeasurementError, match=re.escape(repr(str(bad_path)))):
        advance_loop_step(state, step_input, approval=receipt)
    assert state.current_step == DesignStep.MEASUREMENT.value
    assert all(d.step != DesignStep.MEASUREMENT.value for d in state.decisions)


def test_end_to_end_full_requirements_to_redesign_cycle(tmp_path: Path):
    """One full requirements -> redesign cycle through all nine DesignStep
    values, composing the REAL Phase 1/6/9/11 functions (rf_tools.
    patch_synthesis.patch_resonant_frequency_hz, simulation.nec2pp.
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
            "reference_impedance_ohms": 50.0,
        },
    )
    seen_steps.append(DesignStep.SIMULATION)
    assert state.decisions[-1].result["reference_impedance_ohms"] == 50.0
    assert state.decisions[-1].result["vswr"] is not None
    assert state.decisions[-1].result["return_loss_db"] is not None

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
            "design_family": "patch_antenna",
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
    gated. `requirements_document_status="CONFIRMED"` is passed
    unconditionally (issue #325, docs/adr/0034) -- harmless for every step
    other than ARCHITECTURE, the only one advance_loop_step actually reads
    it for, and keeps every ARCHITECTURE-advancing call site in this file
    that goes through this helper working unchanged now that ARCHITECTURE
    also gates on it."""
    assert state.current_step == step.value
    step_input = step_input_override or _valid_step_input(state, step)
    approval = None
    if step in GATED_STEPS:
        fields = _fingerprint(state, step, step_input)
        approval = request_loop_step_approval(
            fields, approved_by="jane.engineer", approval_callback=lambda f: True
        )
    return advance_loop_step(
        state, step_input, approval=approval, requirements_document_status="CONFIRMED"
    )


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


# ---------------------------------------------------------------------------
# Group 2c (issue #109, ADR-0018): ARCHITECTURE validates `design_family`
# against the Design family registry. #161 landed the field as a bare,
# unvalidated string because the registry did not exist; it does now.
# ---------------------------------------------------------------------------


def test_architecture_rejects_a_design_family_the_registry_does_not_know():
    """A misspelled family previously survived into `decision_records` as a
    grouping key nothing downstream recognises (#150, #151). It now fails at
    the step that named it."""
    state = start_design_loop(REQUIREMENTS)
    step_input = {
        "decision": "rectangular microstrip patch on FR4",
        "rationale": "meets band/gain target",
        "design_family": "absorbre",
    }
    with pytest.raises(DesignLoopValidationError, match="Unknown design_family"):
        _grant_and_advance(state, DesignStep.ARCHITECTURE, step_input_override=step_input)


def test_architecture_records_the_registry_entry_for_the_named_family():
    state = start_design_loop(REQUIREMENTS)
    step_input = {
        "decision": "rectangular microstrip patch on FR4",
        "rationale": "meets band/gain target",
        "design_family": "patch_antenna",
    }
    state = _grant_and_advance(state, DesignStep.ARCHITECTURE, step_input_override=step_input)
    registry = state.decisions[-1].result["design_family_registry"]

    # The caller's own string survives verbatim; the canonical name is added
    # alongside it so runs spelling it differently still group together.
    assert state.decisions[-1].result["design_family"] == "patch_antenna"
    assert registry["canonical_name"] == "PATCH"
    assert registry["simulation_tier"] == "TIER_A"
    assert registry["physical_bound"]["status"] == "available"
    assert "Nel" in registry["physical_bound"]["citation"]
    assert registry["physical_bound"]["primary_source_doc"].startswith("docs/")


def test_architecture_distinguishes_an_unread_bound_from_a_family_with_none():
    """ADR-0018 rejected a fixed schema because a bare `None` would be
    ambiguous between 'not yet computed' and 'doesn't exist for this family'.
    That distinction must survive into the decision record, not collapse on
    the way in."""
    unread = _grant_and_advance(
        start_design_loop(REQUIREMENTS),
        DesignStep.ARCHITECTURE,
        step_input_override={
            "decision": "reflectarray on a grounded silicone spacer",
            "rationale": "beam steering is the requirement",
            "design_family": "reflection_phase",
        },
    )
    none_exists = _grant_and_advance(
        start_design_loop(REQUIREMENTS),
        DesignStep.ARCHITECTURE,
        step_input_override={
            "decision": "1-bit coding surface",
            "rationale": "backscatter redistribution, not absorption",
            "design_family": "diffusive",
        },
    )
    unread_bound = unread.decisions[-1].result["design_family_registry"]["physical_bound"]
    none_bound = none_exists.decisions[-1].result["design_family_registry"]["physical_bound"]

    assert unread_bound["status"] == "unread_primary_source"
    assert "Gustafsson" in unread_bound["citation"]
    assert none_bound["status"] == "none_exists"
    assert none_bound != unread_bound


# ---------------------------------------------------------------------------
# Group 2d (issue #325, docs/adr/0034, CONTEXT.md's "Requirements document"):
# ARCHITECTURE gates on the design's Requirements document reaching
# CONFIRMED, as ONE MORE condition inside advance_loop_step's existing
# `if current_step in GATED_STEPS:` block -- checked immediately after
# check_loop_step_approval_gate, scoped to DesignStep.ARCHITECTURE only, not
# a second, independent check bolted on elsewhere. This module stays
# DB-free (see this module's own docstring's "STATE DESIGN" section):
# `requirements_document_status` is the caller's own freshest read of
# designs.requirements_document.read_requirements_document's
# `document_status`, passed in exactly like `approval` already is, never
# fetched by design_loop.py itself.
# ---------------------------------------------------------------------------

_DOC_REQUIREMENT_IDS = ["R1"]


def _draft_requirements_document_with_target(
    value: float = 2.45e9, effect: str = "behave as a magnetic mirror"
) -> dict:
    """A real DRAFT Requirements document (issue #321) carrying one
    requirement's proposed target and intended effect (issue #323) -- used
    to demonstrate the ARCHITECTURE gate against real document content,
    not a bare status string."""
    target = propose_target(value=value, comparator="EQUALS", unit="Hz")
    target["intended_effect"] = propose_intended_effect(effect)
    return draft_requirements_document(
        _DOC_REQUIREMENT_IDS,
        narrative="Customer needs a conformal reflector for the 2.45 GHz band.",
        requirement_targets={"R1": target},
    )


def _confirm_requirements_document(document: dict) -> dict:
    """Walk `document` through ADR-0034's full review cycle to CONFIRMED
    (DRAFT -> UNDER_REVIEW -> REFINED -> CONFIRMED) via
    revise_requirements_document, restating the same narrative/
    requirement_targets at each step exactly like
    tests/test_requirements_document.py's own revision tests do."""
    for status in (DocumentStatus.UNDER_REVIEW, DocumentStatus.REFINED, DocumentStatus.CONFIRMED):
        document = revise_requirements_document(
            document,
            status,
            document["narrative"],
            document["requirement_targets"],
            _DOC_REQUIREMENT_IDS,
        )
    return document


def test_architecture_is_refused_when_no_requirements_document_exists():
    """`requirements_document_status=None` -- advance_loop_step's own
    default, and also what a caller reading `read_requirements_document`'s
    `"not_found"` result would pass -- refuses ARCHITECTURE with the same
    OrchestrationError family the approval gate already raises, naming
    what's missing. A valid approval receipt alone is not enough."""
    state = start_design_loop(REQUIREMENTS)
    step_input = _valid_step_input(state, DesignStep.ARCHITECTURE)
    fields = _fingerprint(state, DesignStep.ARCHITECTURE, step_input)
    receipt = request_loop_step_approval(
        fields, approved_by="jane.engineer", approval_callback=lambda f: True
    )
    with pytest.raises(OrchestrationError, match="Requirements document"):
        advance_loop_step(state, step_input, approval=receipt)
    # The loop did not advance -- the same guarantee the approval gate
    # itself already gives.
    assert state.current_step == DesignStep.ARCHITECTURE.value


@pytest.mark.parametrize("status", ["DRAFT", "UNDER_REVIEW", "REFINED"])
def test_architecture_is_refused_while_the_requirements_document_is_not_yet_confirmed(status):
    document = _draft_requirements_document_with_target()
    for target_status in (DocumentStatus.UNDER_REVIEW, DocumentStatus.REFINED):
        if document["status"] == status:
            break
        document = revise_requirements_document(
            document,
            target_status,
            document["narrative"],
            document["requirement_targets"],
            _DOC_REQUIREMENT_IDS,
        )
    assert document["status"] == status

    state = start_design_loop(REQUIREMENTS)
    step_input = _valid_step_input(state, DesignStep.ARCHITECTURE)
    fields = _fingerprint(state, DesignStep.ARCHITECTURE, step_input)
    receipt = request_loop_step_approval(
        fields, approved_by="jane.engineer", approval_callback=lambda f: True
    )
    with pytest.raises(OrchestrationError, match="CONFIRMED"):
        advance_loop_step(
            state,
            step_input,
            approval=receipt,
            requirements_document_status=document["status"],
        )
    assert state.current_step == DesignStep.ARCHITECTURE.value


def test_confirming_the_requirements_document_lets_the_same_architecture_call_succeed():
    """The acceptance-criterion demo, end to end: the SAME loop state,
    step_input and approval receipt that ARCHITECTURE refused while the
    Requirements document was still DRAFT succeed immediately once #321/
    #323's own machinery -- revise_requirements_document walking it to
    CONFIRMED, extract_requirement_fields pulling the real target/
    intended_effect off it -- confirms it. No other change to the call is
    needed; only the freshly-read document status differs."""
    document = _draft_requirements_document_with_target()
    state = start_design_loop(REQUIREMENTS)
    step_input = _valid_step_input(state, DesignStep.ARCHITECTURE)
    fields = _fingerprint(state, DesignStep.ARCHITECTURE, step_input)
    receipt = request_loop_step_approval(
        fields, approved_by="jane.engineer", approval_callback=lambda f: True
    )

    with pytest.raises(OrchestrationError, match="CONFIRMED"):
        advance_loop_step(
            state,
            step_input,
            approval=receipt,
            requirements_document_status=document["status"],
        )
    assert state.current_step == DesignStep.ARCHITECTURE.value

    document = _confirm_requirements_document(document)
    assert document["status"] == DocumentStatus.CONFIRMED.value

    # #323's own extraction, proving this is real CONFIRMED-derived data --
    # not a bare "CONFIRMED" string typed into the test.
    extracted = extract_requirement_fields(
        {"R1": {"requirement": "reduce RCS at 2.45 GHz"}}, document
    )
    assert extracted["R1"]["target"]["value"] == 2.45e9
    assert extracted["R1"]["intended_effect"]["effect"] == "behave as a magnetic mirror"

    new_state = advance_loop_step(
        state,
        step_input,
        approval=receipt,
        requirements_document_status=document["status"],
    )
    assert new_state.current_step == DesignStep.ANALYSIS.value
    assert new_state.decisions[-1].kind == "architecture_decision"


# --- #191: ANALYSIS dispatches on the design family -------------------------

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


def _architecture_input(family: str) -> dict:
    return {
        "decision": f"a {family.lower()} design",
        "rationale": "chosen for this requirement",
        "design_family": family,
    }


def test_analysis_runs_the_absorber_model_when_architecture_chose_absorber():
    """#191: an ABSORBER must not be analysed with a patch-antenna resonant
    frequency -- that answers a question about a different device."""
    state = start_design_loop(REQUIREMENTS)
    state = _grant_and_advance(state, DesignStep.ARCHITECTURE, _architecture_input("ABSORBER"))
    state = advance_loop_step(state, dict(_ABSORBER_ANALYSIS_INPUT))

    result = state.decisions[-1].result
    assert result["function"] == "absorber_band_response"
    assert "resonant_frequency_hz" not in result
    assert 0.0 <= result["worst_absorption"] <= 1.0
    assert 8e9 <= result["worst_frequency_hz"] <= 12e9
    assert state.decisions[-1].provenance == "CALCULATED"


def test_analysis_still_runs_the_patch_model_for_patch():
    """The dispatch is additive: PATCH keeps exactly the analysis it had."""
    state = start_design_loop(REQUIREMENTS)
    state = _grant_and_advance(state, DesignStep.ARCHITECTURE, _architecture_input("PATCH"))
    state = advance_loop_step(state, {"eps_r": 4.4, "w_m": 0.038, "h_m": 0.0016, "l_m": 0.029})
    result = state.decisions[-1].result
    assert result["function"] == "patch_resonant_frequency_hz"
    assert result["resonant_frequency_hz"] > 0


def test_absorber_analysis_requires_its_own_fields_not_the_patch_ones():
    state = start_design_loop(REQUIREMENTS)
    state = _grant_and_advance(state, DesignStep.ARCHITECTURE, _architecture_input("ABSORBER"))
    with pytest.raises(DesignLoopValidationError, match="missing required field"):
        advance_loop_step(state, {"eps_r": 4.4, "w_m": 0.038, "h_m": 0.0016, "l_m": 0.029})


def test_absorber_analysis_carries_its_validity_warnings_into_the_decision():
    """A warning that never reaches the recorded decision is not a warning.
    The thin-spacer flag must ride in the loop's own trail.

    Renamed at #245: #190's `thin_spacer_bias_unrecovered` is gone because
    Costa's eq (10) IS carried now; what survives is the narrower
    `thin_spacer_prefactor_disputed` -- the correction is applied, but which
    of two published prefactors is right is still open (#234). What this
    test guards is unchanged: the flag has to reach the decision record."""
    state = start_design_loop(REQUIREMENTS)
    state = _grant_and_advance(state, DesignStep.ARCHITECTURE, _architecture_input("ABSORBER"))
    thin = dict(_ABSORBER_ANALYSIS_INPUT, thickness_m=0.5e-3)
    state = advance_loop_step(state, thin)
    flags = {v["flag"] for v in state.decisions[-1].result["validity"]}
    assert "thin_spacer_prefactor_disputed" in flags


def test_absorber_analysis_reports_a_range_for_a_bracketed_permittivity():
    """ADR-0015/#127: a bracketed material property yields a RANGE, never
    one false-precise number -- the swing is the warning."""
    state = start_design_loop(REQUIREMENTS)
    state = _grant_and_advance(state, DesignStep.ARCHITECTURE, _architecture_input("ABSORBER"))
    material_property = resolve_material_property(
        FR4_SEED_ENTRIES, material="FR4", property_name="eps_r", frequency_hz=9.5e9
    )
    assert material_property["low"] != material_property["high"]  # sanity: the spread case
    bracketed = {k: v for k, v in _ABSORBER_ANALYSIS_INPUT.items() if k != "eps_r"}
    bracketed["material_property"] = material_property
    state = advance_loop_step(state, bracketed)
    result = state.decisions[-1].result
    assert result["worst_absorption_low"] <= result["worst_absorption_high"]


# --- #239: ANALYSIS dispatches on what the family DECLARES, not on its name --
#
# Before #239 this step compared the family's NAME against the single string
# "ABSORBER" and handed the patch-antenna resonant-frequency formula to
# everything else. In plain terms: it read the label on the box to decide
# which instrument to reach for, so any family not spelled "ABSORBER" was
# measured as though it were a transmitting antenna -- which is how
# ABSORBER_TRANSMISSIVE (#216) came to be analysed as one the moment it was
# created.


_PATCH_ANALYSIS_INPUT = {"eps_r": 4.4, "w_m": 0.038, "h_m": 0.0016, "l_m": 0.029}

# Every family that declares no analysis model today. Each is a deliberate
# declaration recorded in designs/design_families.py, not an omission -- see
# that file for why each one has nothing to declare yet.
_FAMILIES_DECLARING_NO_ANALYSIS = [
    # ABSORBER_TRANSMISSIVE was here until #242 gave it the two-port model.
    "DIFFUSIVE",
    "POLARIZATION_CONVERTER",
    "REFLECTION_PHASE",
]


@pytest.mark.parametrize("family", _FAMILIES_DECLARING_NO_ANALYSIS)
def test_a_family_declaring_no_analysis_fails_loudly_instead_of_becoming_a_patch(family):
    """The negative case is the whole point of #239: a family with no
    analysis of its own must produce a recognisable, reported state, not a
    resonant frequency for a device it is not."""
    state = start_design_loop(REQUIREMENTS)
    state = _grant_and_advance(state, DesignStep.ARCHITECTURE, _architecture_input(family))
    with pytest.raises(DesignLoopValidationError) as exc:
        advance_loop_step(state, dict(_PATCH_ANALYSIS_INPUT))

    message = str(exc.value)
    assert family in message
    assert "analysis_model" in message
    assert "designs/design_families.py" in message
    # Nothing was recorded and the loop did not move on: a refusal, not a
    # silently wrong number.
    assert state.current_step == DesignStep.ANALYSIS.value
    assert all(d.step != DesignStep.ANALYSIS.value for d in state.decisions)


def test_the_transmissive_absorber_runs_the_two_port_model_not_the_patch_formula():
    """The defect #239 existed to remove, now checked on the family that had
    it: ABSORBER_TRANSMISSIVE reaches the unbacked two-port model (#242) and
    its result carries a transmitted share -- the quantity a patch resonant
    frequency has no notion of."""
    state = start_design_loop(REQUIREMENTS)
    state = _grant_and_advance(
        state, DesignStep.ARCHITECTURE, _architecture_input("ABSORBER_TRANSMISSIVE")
    )
    state = advance_loop_step(state, dict(_ABSORBER_ANALYSIS_INPUT))

    result = state.decisions[-1].result
    assert "resonant_frequency_hz" not in result
    assert result["worst_absorption"] is not None
    # #506: rf_tools.transmissive_absorber returns a plain result with no
    # provenance field of its own; the tag lives on the decision, applied by
    # the ANALYSIS handler (_handle_analysis_transmissive_absorber).
    assert "provenance" not in result
    assert state.decisions[-1].provenance == "CALCULATED"


def test_the_same_stack_scores_lower_unbacked_because_power_leaves_out_the_back():
    """The number this whole spec exists to correct. One printed stack,
    scored under both families: the ground-backed sum credits every watt not
    reflected as heat, which is legitimate ONLY because a ground plane means
    nothing gets through. Take the ground plane away and some of that power
    walked out the back -- so the honest score must be lower, by at least the
    transmitted share."""

    def _score(family: str) -> dict:
        state = start_design_loop(REQUIREMENTS)
        state = _grant_and_advance(state, DesignStep.ARCHITECTURE, _architecture_input(family))
        state = advance_loop_step(state, dict(_ABSORBER_ANALYSIS_INPUT))
        return state.decisions[-1].result

    backed = _score("ABSORBER")
    unbacked = _score("ABSORBER_TRANSMISSIVE")

    assert unbacked["worst_absorption"] < backed["worst_absorption"]
    # And the gap is not a tuning artefact: it is the power that got through.
    # The ground-backed model has no such quantity to report at all, which is
    # the structural difference between the two families.
    assert unbacked["transmission_at_worst"] > 0.0
    assert "transmission_at_worst" not in backed


def test_the_transmissive_analysis_reports_its_bound_unread_and_never_names_rozanov():
    """The bound is reported as UNREAD, never as absent -- absence of a
    citation is not evidence that no bound exists. And the ground-backed
    family's bound is not named anywhere in the result: its derivation fixes
    a slab over a perfectly reflecting plane, this family has no such plane,
    and issue #216's failure mode is somebody finding the familiar name
    sitting beside a transmissive number and reapplying it."""
    import json as _json

    from designs.design_families import ABSORBER_TRANSMISSIVE as _AT

    state = start_design_loop(REQUIREMENTS)
    state = _grant_and_advance(
        state, DesignStep.ARCHITECTURE, _architecture_input("ABSORBER_TRANSMISSIVE")
    )
    state = advance_loop_step(state, dict(_ABSORBER_ANALYSIS_INPUT))
    result = state.decisions[-1].result

    assert result["physical_bound"]["status"] == "unread_primary_source"
    assert result["physical_bound"]["applies"] is False
    assert "rozanov" not in _json.dumps(result, default=str).lower()
    # The registry entry is where that explanation belongs, and it is there.
    assert "Rozanov" in _AT.physical_bound.citation


def test_the_ground_backed_model_refuses_a_transmissive_family_at_the_dispatch():
    """The guard sits where a design family and a model first meet. Aimed at
    the transmissive family, the ground-backed handler must raise rather than
    return the high score it would happily compute for a stack that lets a
    large share straight through."""
    from designs.design_families import ABSORBER_TRANSMISSIVE as _AT
    from rf_tools.transmissive_absorber import GroundBackedModelMisappliedError

    with pytest.raises(GroundBackedModelMisappliedError, match="ABSORBER_TRANSMISSIVE"):
        design_loop_module._handle_analysis_absorber(_AT, dict(_ABSORBER_ANALYSIS_INPUT))


def test_the_ground_backed_absorber_result_is_byte_for_byte_what_it_always_was():
    """#242 must not move ABSORBER. The loop's result has to equal a direct
    call to the untouched `rf_tools.absorber.absorber_band_response` for the
    same inputs -- not merely resemble it."""
    from rf_tools.absorber import absorber_band_response as _abr

    state = start_design_loop(REQUIREMENTS)
    state = _grant_and_advance(state, DesignStep.ARCHITECTURE, _architecture_input("ABSORBER"))
    state = advance_loop_step(state, dict(_ABSORBER_ANALYSIS_INPUT))
    assert state.decisions[-1].result == _abr(**_ABSORBER_ANALYSIS_INPUT)


def test_analysis_follows_the_declared_model_even_when_the_family_name_disagrees(monkeypatch):
    """Proof the name comparison is really gone. The registry entry this
    ARCHITECTURE step resolves to declares the absorber model but is named
    something else entirely, and the step_input names the family "PATCH" --
    so the old string comparison would have run the patch formula here and
    failed on its missing w_m/h_m/l_m. Reading the declaration instead gets
    the absorber model."""
    renamed = _dc_replace(design_families_module.ABSORBER, name="NOT_SPELLED_ABSORBER")
    monkeypatch.setattr(design_loop_module, "_get_design_family", lambda _name: renamed)

    state = start_design_loop(REQUIREMENTS)
    state = _grant_and_advance(state, DesignStep.ARCHITECTURE, _architecture_input("PATCH"))
    state = advance_loop_step(state, dict(_ABSORBER_ANALYSIS_INPUT))
    assert state.decisions[-1].result["function"] == "absorber_band_response"


def test_analysis_needs_an_architecture_decision_before_it_can_choose_a_model():
    """With no ARCHITECTURE decision there is no declared family, so there is
    nothing to read a model off. Guessing one is exactly what #239 removes."""
    state = start_design_loop(REQUIREMENTS)
    state = _advance_to(state, DesignStep.ANALYSIS)
    with pytest.raises(DesignLoopValidationError, match="design_family"):
        advance_loop_step(state, dict(_PATCH_ANALYSIS_INPUT))


# --- #229: SIMULATION dispatches on the family's declared adapter -----------


def test_no_architecture_decision_means_there_is_no_adapter_to_read(monkeypatch):
    """#241: with no ARCHITECTURE decision no family has been named, so
    nothing declares a solver. The old code answered NEC2 here -- a wire
    solver picked by default for a design nobody had described yet."""

    def exploding_nec2(*args, **kwargs):
        raise AssertionError("NEC2 must never be reached by default")

    monkeypatch.setattr(design_loop_module, "_run_nec2_simulation", exploding_nec2)
    state = start_design_loop(REQUIREMENTS)
    with pytest.raises(DesignLoopValidationError, match="design_family"):
        _simulation_adapter_for(state)


def test_patch_declares_nec2_and_absorber_declares_meep():
    state = start_design_loop(REQUIREMENTS)
    patch = _grant_and_advance(state, DesignStep.ARCHITECTURE, _architecture_input("PATCH"))
    absorber = _grant_and_advance(state, DesignStep.ARCHITECTURE, _architecture_input("ABSORBER"))
    assert _simulation_adapter_for(patch) == "NEC2"
    assert _simulation_adapter_for(absorber) == "MEEP_FLOQUET"


def test_reflection_phase_and_diffusive_declare_palace_floquet():
    """#252 ticket 3: both Tier B unit-cell families now route to Palace,
    not to whichever handler used to answer for an unsettled adapter."""
    state = start_design_loop(REQUIREMENTS)
    reflection_phase = _grant_and_advance(
        state, DesignStep.ARCHITECTURE, _architecture_input("REFLECTION_PHASE")
    )
    diffusive = _grant_and_advance(state, DesignStep.ARCHITECTURE, _architecture_input("DIFFUSIVE"))
    assert _simulation_adapter_for(reflection_phase) == "PALACE_FLOQUET"
    assert _simulation_adapter_for(diffusive) == "PALACE_FLOQUET"


# --- #241: an undeclared simulation adapter is a loud failure, not NEC2 -----
#
# NEC2 is a thin-wire method-of-moments solver: its whole geometry vocabulary
# is wires over an optional ground plane -- no dielectrics, no sheet
# impedance, no periodicity. A periodic surface is not a HARD case for it, it
# is one you cannot write an input file for. So falling back to it was never
# a conservative default; it was a wrong answer waiting to be produced
# confidently.

# Every family with no settled adapter today. Each states WHY in
# designs/design_families.py rather than being left silently unset.
_FAMILIES_WITH_NO_SETTLED_ADAPTER = [
    # ABSORBER_TRANSMISSIVE was here until #243 settled it on MEEP_FLOQUET.
    # DIFFUSIVE and REFLECTION_PHASE were here until #252 ticket 3 settled
    # both on PALACE_FLOQUET -- see the PALACE_FLOQUET dispatch tests below.
    "POLARIZATION_CONVERTER",
]


def _at_simulation(family: str) -> DesignLoopState:
    """An iteration whose ARCHITECTURE named `family`, positioned at
    SIMULATION. ANALYSIS is stepped over rather than run, because these
    families declare no analysis either (#239) -- this test is about the
    solver choice, not about that."""
    state = start_design_loop(REQUIREMENTS)
    state = _grant_and_advance(state, DesignStep.ARCHITECTURE, _architecture_input(family))
    return _advance_to(state, DesignStep.SIMULATION)


@pytest.mark.parametrize("family", _FAMILIES_WITH_NO_SETTLED_ADAPTER)
def test_a_family_with_no_settled_adapter_refuses_to_simulate(family, monkeypatch):
    def exploding_nec2(*args, **kwargs):
        raise AssertionError(f"NEC2 must never be reached for {family}")

    monkeypatch.setattr(design_loop_module, "_run_nec2_simulation", exploding_nec2)
    state = _at_simulation(family)

    with pytest.raises(DesignLoopValidationError) as exc:
        advance_loop_step(
            state,
            {"geometry": {}, "frequency_hz": 10e9, "reference_impedance_ohms": 50.0},
        )
    message = str(exc.value)
    assert family in message
    assert "simulation_adapter" in message
    assert "designs/design_families.py" in message
    assert state.current_step == DesignStep.SIMULATION.value
    assert all(d.step != DesignStep.SIMULATION.value for d in state.decisions)


def test_the_transmissive_absorber_now_routes_to_meep_and_never_to_nec2(monkeypatch):
    """#243 settled it. The family that used to refuse to simulate at all --
    because the adapter could not say how much power went THROUGH the
    surface -- now names MEEP_FLOQUET, and must never reach NEC2, whose
    entire geometry vocabulary is wires and which cannot express a repeating
    surface at all."""

    def exploding_nec2(*args, **kwargs):
        raise AssertionError("NEC2 must never be reached for ABSORBER_TRANSMISSIVE")

    monkeypatch.setattr(design_loop_module, "_run_nec2_simulation", exploding_nec2)
    state = _at_simulation("ABSORBER_TRANSMISSIVE")
    assert _simulation_adapter_for(state) == "MEEP_FLOQUET"


def test_a_declared_adapter_this_loop_cannot_drive_is_reported_not_routed_to_nec2(monkeypatch):
    """The other half of the same defect: a family may declare a solver this
    loop has no handler wired for. That must be said, not silently answered
    by whichever handler happens to be last.

    "HFSS_DRIVEN" is used here (rather than PALACE_FLOQUET, this test's
    original example) because #252 ticket 3 wired PALACE_FLOQUET into
    `_SIMULATION_ADAPTERS` -- see test_reflection_phase_and_diffusive_route_
    to_palace_not_nec2 below for that adapter's own dispatch coverage. This
    test needs a name that stays genuinely unwired."""
    unwired = _dc_replace(
        design_families_module.ABSORBER,
        simulation_adapter=design_families_module.SimulationAdapter(
            name="HFSS_DRIVEN", reason="a solver this loop has no handler for"
        ),
    )
    monkeypatch.setattr(design_loop_module, "_get_design_family", lambda _name: unwired)

    def exploding_nec2(*args, **kwargs):
        raise AssertionError("NEC2 must never stand in for an unwired adapter")

    monkeypatch.setattr(design_loop_module, "_run_nec2_simulation", exploding_nec2)
    state = _at_simulation("ABSORBER")
    with pytest.raises(_SimulatorError, match="HFSS_DRIVEN"):
        advance_loop_step(
            state,
            {"geometry": {}, "frequency_hz": 10e9, "reference_impedance_ohms": 50.0},
        )


def test_absorber_simulation_runs_meep_with_a_periodic_cell(monkeypatch):
    """#230/#231: the three capability gaps are closed, so the absorber path
    now runs rather than refusing. It must reach Meep -- never NEC2 -- and it
    must make the cell periodic, because a unit cell IS an infinite array and
    forgetting that fails silently."""
    captured = {}

    def fake_run(geometry, characteristic_length_m, nfreq, workdir):
        captured["geometry"] = geometry
        return {
            "provenance": "SIMULATED",
            "simulator": "MEEP",
            "status": "COMPLETED",
            "s_parameters": {"frequency_hz": [9e9, 10e9], "reflectance": [0.2, 0.01]},
        }

    monkeypatch.setattr(design_loop_module, "_run_meep_simulation", fake_run)

    state = start_design_loop(REQUIREMENTS)
    state = _grant_and_advance(state, DesignStep.ARCHITECTURE, _architecture_input("ABSORBER"))
    state = advance_loop_step(state, dict(_ABSORBER_ANALYSIS_INPUT))
    state = advance_loop_step(
        state, {"geometry": {"cell_size_m": [3e-3, 3e-3, 40e-3]}, "frequency_hz": 10e9}
    )

    assert captured["geometry"]["periodic_axes"] == ["x", "y"]
    result = state.decisions[-1].result
    assert result["function"] == "run_meep_simulation"
    # Ground-backed: nothing transmits, so every watt not reflected was
    # dissipated. A = 1 - R is legitimate only for that reason.
    assert result["absorption"] == pytest.approx([0.8, 0.99])
    assert result["worst_absorption"] == pytest.approx(0.8)
    assert result["port_count"] == 1  # #243: the arithmetic says what it assumed
    assert state.decisions[-1].provenance == "SIMULATED"


def test_absorber_simulation_records_meep_workdir(monkeypatch):
    """#461, the #345 gap for MEEP: `run_meep_simulation` already returns
    its own working directory; a completed ABSORBER/ABSORBER_TRANSMISSIVE
    decision must record it too, or a persisted-and-reloaded decision can
    no longer be traced back to the solver run that produced it."""

    def fake_run(geometry, characteristic_length_m, nfreq, workdir):
        del geometry, characteristic_length_m, nfreq, workdir
        return {
            "provenance": "SIMULATED",
            "simulator": "MEEP",
            "status": "COMPLETED",
            "workdir": "/tmp/meep_xyz789",
            "s_parameters": {"frequency_hz": [10e9], "reflectance": [0.2]},
        }

    monkeypatch.setattr(design_loop_module, "_run_meep_simulation", fake_run)

    state = start_design_loop(REQUIREMENTS)
    state = _grant_and_advance(state, DesignStep.ARCHITECTURE, _architecture_input("ABSORBER"))
    state = advance_loop_step(state, dict(_ABSORBER_ANALYSIS_INPUT))
    state = advance_loop_step(
        state, {"geometry": {"cell_size_m": [3e-3, 3e-3, 40e-3]}, "frequency_hz": 10e9}
    )

    result = state.decisions[-1].result
    assert result["workdir"] == "/tmp/meep_xyz789"

    restored = LoopDecision.from_dict(state.decisions[-1].to_dict())
    assert restored.result["workdir"] == "/tmp/meep_xyz789"


def test_absorber_simulation_never_silently_falls_back_to_nec2(monkeypatch):
    """The failure this whole dispatch exists to remove: quietly running the
    wire solver on a metamaterial cell and reporting success."""

    def exploding_nec2(*args, **kwargs):
        raise AssertionError("NEC2 must never be reached for an ABSORBER")

    monkeypatch.setattr(design_loop_module, "_run_nec2_simulation", exploding_nec2)
    monkeypatch.setattr(
        design_loop_module,
        "_run_meep_simulation",
        lambda **kwargs: {
            "provenance": "SIMULATED",
            "simulator": "MEEP",
            "status": "COMPLETED",
            "s_parameters": {"frequency_hz": [10e9], "reflectance": [0.05]},
        },
    )
    state = start_design_loop(REQUIREMENTS)
    state = _grant_and_advance(state, DesignStep.ARCHITECTURE, _architecture_input("ABSORBER"))
    state = advance_loop_step(state, dict(_ABSORBER_ANALYSIS_INPUT))
    state = advance_loop_step(state, {"geometry": {}, "frequency_hz": 10e9})
    assert state.decisions[-1].result["simulator"] == "MEEP"


def test_the_absorbers_closed_form_analysis_is_kept_alongside_the_full_wave_run(monkeypatch):
    """#111's two tiers: the cheap closed form screens, the expensive
    full-wave run confirms. Both stay in the trail -- the point of a
    cross-check is that you can compare them."""
    monkeypatch.setattr(
        design_loop_module,
        "_run_meep_simulation",
        lambda **kwargs: {
            "provenance": "SIMULATED",
            "simulator": "MEEP",
            "status": "COMPLETED",
            "s_parameters": {"frequency_hz": [10e9], "reflectance": [0.05]},
        },
    )
    state = start_design_loop(REQUIREMENTS)
    state = _grant_and_advance(state, DesignStep.ARCHITECTURE, _architecture_input("ABSORBER"))
    state = advance_loop_step(state, dict(_ABSORBER_ANALYSIS_INPUT))
    state = advance_loop_step(state, {"geometry": {}, "frequency_hz": 10e9})

    kinds = [(d.step, d.result.get("function")) for d in state.decisions]
    assert ("analysis", "absorber_band_response") in kinds
    assert ("simulation", "run_meep_simulation") in kinds


# ---------------------------------------------------------------------------
# #252 ticket 3: SIMULATION dispatches REFLECTION_PHASE/DIFFUSIVE to
# PALACE_FLOQUET, mirroring the ABSORBER/MEEP_FLOQUET dispatch tests above.
# ---------------------------------------------------------------------------

# The physically-correct shape for a REFLECTION_PHASE/DIFFUSIVE candidate:
# ground_backed=True (the family's own requires_ground_plane=True/
# port_count=1 physics) plus at least one embedded conductor patch (the
# printed metasurface element these families are designed by).
_GROUND_BACKED_METASURFACE_GEOMETRY = {
    "unit_cell": {"lx_m": 0.01, "ly_m": 0.01, "lz_m": 0.01},
    "ground_backed": True,
    "pec_patches": [
        {"name": "patch", "p1_m": [0.002, 0.002, 0.005], "p2_m": [0.008, 0.008, 0.005]},
    ],
}


def _fake_palace_result(**_kwargs):
    return {
        "provenance": "SIMULATED",
        "simulator": "Palace",
        "status": "COMPLETED",
        "s_parameters": {
            "computed": True,
            "frequency_hz": [10e9],
            "modes": {},
            "specular": {"S11_TE": [complex(-1.0, 0.0)]},
        },
        "conservation_check": {
            "all_ok": True,
            "power_balance": [],
            "passivity": [],
            "reciprocity": [],
        },
        "workdir": "/tmp/palace_abc123",
        "mesh_file": "/tmp/palace_abc123/unit_cell.mesh",
        "config_file": "/tmp/palace_abc123/config.json",
        "output_dir": "/tmp/palace_abc123/postpro",
        "num_mesh_elements": 4096,
    }


@pytest.mark.parametrize("family", ["REFLECTION_PHASE", "DIFFUSIVE"])
def test_reflection_phase_and_diffusive_route_to_palace_not_nec2(family, monkeypatch):
    """#252 ticket 3: a candidate whose geometry sets ground_backed=True and
    carries a pec_patches entry reaches Palace, never NEC2, and records a
    SIMULATED result carrying Palace's own s_parameters/specular/
    conservation_check output -- the per-diffraction-order reflectance and
    phase this family actually needs (issue #252's user stories 6/7), not a
    quantity borrowed from another family's physics."""
    captured = {}

    def exploding_nec2(*args, **kwargs):
        raise AssertionError(f"NEC2 must never be reached for {family}")

    def fake_run(**kwargs):
        captured["kwargs"] = kwargs
        return _fake_palace_result()

    monkeypatch.setattr(design_loop_module, "_run_nec2_simulation", exploding_nec2)
    monkeypatch.setattr(design_loop_module, "_run_palace_simulation", fake_run)

    state = _at_simulation(family)
    state = advance_loop_step(
        state, {"geometry": dict(_GROUND_BACKED_METASURFACE_GEOMETRY), "frequency_hz": 10e9}
    )

    assert captured["kwargs"]["geometry"]["ground_backed"] is True
    assert captured["kwargs"]["geometry"]["pec_patches"]
    assert captured["kwargs"]["frequency_hz"] == 10e9

    result = state.decisions[-1].result
    assert result["function"] == "run_palace_simulation"
    assert result["simulator"] == "Palace"
    assert result["s_parameters"]["specular"] == {"S11_TE": [complex(-1.0, 0.0)]}
    assert result["specular"] == {"S11_TE": [complex(-1.0, 0.0)]}
    assert result["conservation_check"]["all_ok"] is True
    assert state.decisions[-1].provenance == "SIMULATED"


@pytest.mark.parametrize("family", ["REFLECTION_PHASE", "DIFFUSIVE"])
def test_palace_simulation_decision_records_solver_artifact_paths(family, monkeypatch):
    """#345: a completed Palace SIMULATION decision names the mesh, config
    and output directory it came from -- `run_palace_simulation` always
    returns these, and until now the decision this loop records dropped
    them on the way in, so a persisted-and-reloaded decision could no
    longer be traced back to the solver artifacts that produced it. The
    fake workdir here ("/tmp/...") is NOT the durable default
    (#466), so the decision also carries that ticket's non-durability
    warning -- see test_palace_simulation_using_default_workdir_is_silent
    for the silent, durable-default case."""

    def exploding_nec2(*args, **kwargs):
        raise AssertionError(f"NEC2 must never be reached for {family}")

    monkeypatch.setattr(design_loop_module, "_run_nec2_simulation", exploding_nec2)
    monkeypatch.setattr(design_loop_module, "_run_palace_simulation", _fake_palace_result)

    state = _at_simulation(family)
    state = advance_loop_step(
        state, {"geometry": dict(_GROUND_BACKED_METASURFACE_GEOMETRY), "frequency_hz": 10e9}
    )

    result = state.decisions[-1].result
    assert result["workdir"] == "/tmp/palace_abc123"
    assert result["mesh_file"] == "/tmp/palace_abc123/unit_cell.mesh"
    assert result["config_file"] == "/tmp/palace_abc123/config.json"
    assert result["output_dir"] == "/tmp/palace_abc123/postpro"
    assert result["num_mesh_elements"] == 4096
    assert [entry["flag"] for entry in result["validity"]] == ["solver_workdir_not_durable"]

    # A decision round-trips through persistence and still resolves to its
    # solver artifacts -- `LoopDecision.result` is stored and restored as a
    # plain dict, so nothing but this handler recording the fields in the
    # first place stands between a saved loop and losing them.
    restored = LoopDecision.from_dict(state.decisions[-1].to_dict())
    assert restored.result["workdir"] == "/tmp/palace_abc123"
    assert restored.result["mesh_file"] == "/tmp/palace_abc123/unit_cell.mesh"
    assert restored.result["output_dir"] == "/tmp/palace_abc123/postpro"


def test_palace_simulation_using_default_workdir_is_silent(monkeypatch):
    """#466: a Palace run recorded under the durable default directory
    (simulation.base.new_solver_workdir) must NOT carry the non-durability
    warning -- that warning firing on every run regardless of where the
    artifacts actually live is precisely the blanket-warning defect #466
    exists to remove (CLAUDE.md: "a warning is only useful if it is rare
    and specific")."""
    from simulation.base import new_solver_workdir

    durable_workdir = str(new_solver_workdir("palace"))

    def fake_run(**_kwargs):
        result = _fake_palace_result()
        result["workdir"] = durable_workdir
        result["mesh_file"] = f"{durable_workdir}/unit_cell.mesh"
        result["config_file"] = f"{durable_workdir}/config.json"
        result["output_dir"] = f"{durable_workdir}/postpro"
        return result

    monkeypatch.setattr(design_loop_module, "_run_palace_simulation", fake_run)

    state = _at_simulation("REFLECTION_PHASE")
    state = advance_loop_step(
        state, {"geometry": dict(_GROUND_BACKED_METASURFACE_GEOMETRY), "frequency_hz": 10e9}
    )

    result = state.decisions[-1].result
    assert result["workdir"] == durable_workdir
    assert result["validity"] == []


@pytest.mark.parametrize("family", ["REFLECTION_PHASE", "DIFFUSIVE"])
def test_reflection_phase_and_diffusive_never_silently_fall_back_to_nec2(family, monkeypatch):
    """The failure this dispatch exists to remove: quietly running the wire
    solver -- or Palace on this module's OTHER (transmissive, all-
    dielectric) shape -- on a metasurface cell and reporting success. An
    unsupported geometry (missing ground_backed/pec_patches) must raise,
    naming the gap, and must never reach a solver run at all."""

    def exploding_nec2(*args, **kwargs):
        raise AssertionError(f"NEC2 must never be reached for {family}")

    def exploding_palace_run(*args, **kwargs):
        raise AssertionError(
            f"run_palace_simulation must never run on an unsupported {family} geometry"
        )

    monkeypatch.setattr(design_loop_module, "_run_nec2_simulation", exploding_nec2)
    monkeypatch.setattr(design_loop_module, "_run_palace_simulation", exploding_palace_run)

    state = _at_simulation(family)
    with pytest.raises(_SimulatorError) as exc:
        advance_loop_step(
            state,
            {
                "geometry": {"unit_cell": {"lx_m": 0.01, "ly_m": 0.01, "lz_m": 0.01}},
                "frequency_hz": 10e9,
            },
        )
    message = str(exc.value)
    assert "ground_backed=True" in message
    assert "pec_patches" in message
    assert state.current_step == DesignStep.SIMULATION.value
    assert all(d.step != DesignStep.SIMULATION.value for d in state.decisions)


def test_reflection_phase_missing_only_pec_patches_names_only_that_gap(monkeypatch):
    """A geometry that already sets ground_backed=True but has no
    pec_patches must name only the missing patch, not the (already-
    satisfied) ground_backed gap too."""

    def exploding_palace_run(*args, **kwargs):
        raise AssertionError("run_palace_simulation must never run on an unsupported geometry")

    monkeypatch.setattr(design_loop_module, "_run_palace_simulation", exploding_palace_run)
    state = _at_simulation("REFLECTION_PHASE")
    with pytest.raises(_SimulatorError) as exc:
        advance_loop_step(
            state,
            {
                "geometry": {
                    "unit_cell": {"lx_m": 0.01, "ly_m": 0.01, "lz_m": 0.01},
                    "ground_backed": True,
                },
                "frequency_hz": 10e9,
            },
        )
    message = str(exc.value)
    assert "ground_backed=True" not in message
    assert "pec_patches" in message


def test_patch_and_absorber_routing_is_unaffected_by_the_palace_dispatch(monkeypatch):
    """Regression: wiring PALACE_FLOQUET must not move PATCH off NEC2 or
    ABSORBER off MEEP_FLOQUET, and DEFAULT_SIMULATION_ADAPTER (removed at
    #241) stays gone -- nothing here reintroduces a default."""
    assert not hasattr(design_loop_module, "DEFAULT_SIMULATION_ADAPTER")

    def exploding_palace_run(*args, **kwargs):
        raise AssertionError("Palace must never be reached for PATCH or ABSORBER")

    monkeypatch.setattr(design_loop_module, "_run_palace_simulation", exploding_palace_run)
    monkeypatch.setattr(
        design_loop_module, "_run_nec2_simulation", lambda **kw: _fake_nec2_result()
    )

    state = start_design_loop(REQUIREMENTS)
    patch = _grant_and_advance(state, DesignStep.ARCHITECTURE, _architecture_input("PATCH"))
    absorber = _grant_and_advance(state, DesignStep.ARCHITECTURE, _architecture_input("ABSORBER"))
    assert _simulation_adapter_for(patch) == "NEC2"
    assert _simulation_adapter_for(absorber) == "MEEP_FLOQUET"

    patch_state = advance_loop_step(
        _advance_to(patch, DesignStep.SIMULATION),
        {"geometry": {}, "frequency_hz": 10e9, "reference_impedance_ohms": 50.0},
    )
    assert patch_state.decisions[-1].result["simulator"] == "NEC2++"
    assert "s_parameters" not in patch_state.decisions[-1].result


def test_no_capability_gaps_remain_and_the_survivors_are_honest_caveats():
    """The three gaps (#230) are closed and verified against real Meep. What
    is left is approximate rather than absent, and each survivor still owes
    the charter's three things: what is assumed, what it costs, the cheapest
    way to find out."""
    assert meep_periodic_absorber_capability_gaps() == []
    assert MEEP_PERIODIC_ABSORBER_VALIDITY
    for entry in MEEP_PERIODIC_ABSORBER_VALIDITY:
        assert entry["flag"] and entry["assumed"] and entry["costs"] and entry["cheapest_test"]


# --- #243: the absorption sum is chosen by the family's declared ports ------
#
# `A = 1 - R` says "whatever did not bounce back was turned into heat". That
# is only true when nothing can get through. On a surface with free space
# behind it, some of the power walks out the back, and crediting that as
# absorbed makes a design look better than it is -- with nothing in the
# number to say so. So the sum is selected from the family's declared
# `port_count`: one port (ground-backed) keeps `A = 1 - R`; two ports
# (unbacked) must subtract the measured transmitted share as well.


def _meep_result(reflectance, transmittance_entry=..., frequency_hz=(10e9,)):
    """A fake `run_meep_simulation` return. `transmittance_entry` is the
    adapter's own three-state entry (#240) -- left out entirely by default,
    which is what a pre-#240 adapter would return."""
    s_parameters = {"frequency_hz": list(frequency_hz), "reflectance": list(reflectance)}
    if transmittance_entry is not ...:
        s_parameters["transmittance"] = transmittance_entry
    return {
        "provenance": "SIMULATED",
        "simulator": "MEEP",
        "status": "COMPLETED",
        "s_parameters": s_parameters,
    }


_TWO_PORT_GEOMETRY = {
    "cell_size_m": [3e-3, 3e-3, 40e-3],
    # The plane behind the structure at which the power that got through is
    # counted. The loop cannot invent this: only whoever laid out the cell
    # knows which side the source is on and where the PML ends.
    "transmission_monitor_center_m": [0.0, 0.0, -8e-3],
}


def _run_two_port_simulation(monkeypatch, meep_result, geometry=None):
    """Drive ABSORBER_TRANSMISSIVE through the real SIMULATION step with a
    fake solver return, and hand back (state, captured geometry)."""
    captured = {}

    def fake_run(geometry, characteristic_length_m, nfreq, workdir):
        captured["geometry"] = geometry
        return meep_result

    monkeypatch.setattr(design_loop_module, "_run_meep_simulation", fake_run)
    state = _at_simulation("ABSORBER_TRANSMISSIVE")
    state = advance_loop_step(
        state,
        {
            "geometry": dict(_TWO_PORT_GEOMETRY if geometry is None else geometry),
            "frequency_hz": 10e9,
        },
    )
    return state, captured


def test_a_two_port_familys_absorption_excludes_the_power_that_went_through(monkeypatch):
    """The defect this ticket removes, stated as arithmetic. A fifth of the
    power bounces back and just under a third passes straight through, so
    what actually became heat is a half -- not the four fifths `1 - R` would
    have reported."""
    state, _ = _run_two_port_simulation(
        monkeypatch,
        _meep_result(
            [0.2],
            {"computed": True, "requested": True, "transmittance": [0.3]},
        ),
    )
    result = state.decisions[-1].result
    assert result["port_count"] == 2
    assert result["absorption_formula"] == "A = 1 - R - T"
    assert result["absorption"] == pytest.approx([0.5])
    assert result["worst_absorption"] == pytest.approx(0.5)
    assert result["transmittance"] == pytest.approx([0.3])
    assert state.decisions[-1].provenance == "SIMULATED"


def test_a_two_port_run_asks_the_adapter_for_the_transmitted_power(monkeypatch):
    """Asking is not optional for a two-port family: the transmission
    monitor has to reach the solver, or there is no T to subtract."""
    _, captured = _run_two_port_simulation(
        monkeypatch,
        _meep_result([0.2], {"computed": True, "requested": True, "transmittance": [0.3]}),
    )
    assert captured["geometry"]["transmission_monitor_center_m"] == [0.0, 0.0, -8e-3]
    assert captured["geometry"]["periodic_axes"] == ["x", "y"]


def test_a_two_port_run_with_no_transmission_monitor_refuses_before_spending_solver_time(
    monkeypatch,
):
    """Caught up front, not after a full-wave run: without a monitor plane
    the answer cannot be computed however long the solver runs, and FDTD
    time is the expensive thing here."""

    def exploding_run(**kwargs):
        raise AssertionError("the solver must not run when T can never be computed")

    monkeypatch.setattr(design_loop_module, "_run_meep_simulation", exploding_run)
    state = _at_simulation("ABSORBER_TRANSMISSIVE")
    with pytest.raises(DesignLoopValidationError) as exc:
        advance_loop_step(
            state, {"geometry": {"cell_size_m": [3e-3, 3e-3, 40e-3]}, "frequency_hz": 10e9}
        )
    message = str(exc.value)
    assert "ABSORBER_TRANSMISSIVE" in message
    assert "port_count=2" in message
    assert "transmission_monitor_center_m" in message
    assert state.current_step == DesignStep.SIMULATION.value
    assert all(d.step != DesignStep.SIMULATION.value for d in state.decisions)


@pytest.mark.parametrize(
    "transmittance_entry",
    [
        # Asked for, and the adapter could not compute it (#240's middle state).
        {"computed": False, "requested": True, "note": "the reference run's flux was empty"},
        # Asked for by the loop, yet the result says nobody asked -- an
        # adapter that ignored the monitor.
        {"computed": False, "requested": False, "note": "no transmission monitor was requested"},
        # No transmittance entry at all: an adapter from before #240.
        ...,
    ],
)
def test_a_two_port_family_whose_transmittance_is_missing_refuses(monkeypatch, transmittance_entry):
    """Silently falling back to `1 - R` here is the precise defect #243
    removes -- it would report 0.8 absorbed where the truth might be 0.5,
    and the number would look like a success."""
    monkeypatch.setattr(
        design_loop_module,
        "_run_meep_simulation",
        lambda **kwargs: _meep_result([0.2], transmittance_entry),
    )
    state = _at_simulation("ABSORBER_TRANSMISSIVE")
    with pytest.raises(_SimulatorError) as exc:
        advance_loop_step(state, {"geometry": dict(_TWO_PORT_GEOMETRY), "frequency_hz": 10e9})
    message = str(exc.value)
    assert "ABSORBER_TRANSMISSIVE" in message
    assert "transmittance" in message
    assert all(d.step != DesignStep.SIMULATION.value for d in state.decisions)


def test_a_measured_zero_transmission_is_not_the_same_as_an_unmeasured_one(monkeypatch):
    """The three states stay apart. A measured zero is a real result -- the
    structure genuinely passes nothing at this frequency -- and it computes
    the same number `1 - R` would have, honestly this time, because T was
    actually looked at."""
    state, _ = _run_two_port_simulation(
        monkeypatch,
        _meep_result([0.2], {"computed": True, "requested": True, "transmittance": [0.0]}),
    )
    result = state.decisions[-1].result
    assert result["absorption"] == pytest.approx([0.8])
    assert result["transmittance"] == pytest.approx([0.0])
    assert result["transmittance_measurement"]["computed"] is True


def test_the_one_port_collapse_raises_when_aimed_at_a_two_port_family():
    """Named and refused, not warned about: `1 - R` on a transmitting
    surface is a confidently wrong number, and no caveat attached to it
    would tell a reader that it was."""
    from designs.design_families import ABSORBER_TRANSMISSIVE as _AT
    from rf_tools.transmissive_absorber import (
        GroundBackedModelMisappliedError,
        one_port_absorption,
    )

    with pytest.raises(GroundBackedModelMisappliedError) as exc:
        one_port_absorption(_AT, [0.2])
    message = str(exc.value)
    assert "ABSORBER_TRANSMISSIVE" in message
    assert "port_count=2" in message
    assert "1 - R" in message


def test_reflected_plus_transmitted_over_one_is_flagged_and_the_candidate_still_returned(
    monkeypatch,
):
    """More power came back and got through than arrived, which cannot
    physically happen -- so an assumption behind the run is wrong. That is
    warned about and handed over, never withheld: the charter's "warn, never
    block" governs keeping a candidate from a reader."""
    state, _ = _run_two_port_simulation(
        monkeypatch,
        _meep_result([0.7], {"computed": True, "requested": True, "transmittance": [0.5]}),
    )
    decision = state.decisions[-1]
    result = decision.result

    # Returned and recorded, with the arithmetic shown rather than clipped.
    assert decision.step == DesignStep.SIMULATION.value
    assert result["absorption"] == pytest.approx([-0.2])
    assert state.current_step == DesignStep.OPTIMIZATION.value

    violations = result["energy_balance_violations"]
    assert len(violations) == 1
    assert violations[0]["reflected_plus_transmitted"] == pytest.approx(1.2)
    assert violations[0]["frequency_hz"] == pytest.approx(10e9)

    warning = next(
        v for v in result["validity"] if v["flag"] == "reflected_plus_transmitted_exceeds_incident"
    )
    # The charter's three-part warning shape.
    assert warning["assumed"] and warning["costs"] and warning["cheapest_test"]


def test_a_physical_two_port_run_carries_no_energy_balance_warning(monkeypatch):
    """A warning on every run is the same as no warning at all. It fires
    only where the sum is actually impossible."""
    state, _ = _run_two_port_simulation(
        monkeypatch,
        _meep_result([0.2], {"computed": True, "requested": True, "transmittance": [0.3]}),
    )
    result = state.decisions[-1].result
    assert result["energy_balance_violations"] == []
    assert all(
        v["flag"] != "reflected_plus_transmitted_exceeds_incident" for v in result["validity"]
    )


def test_the_ground_backed_family_pays_nothing_for_the_two_port_machinery(monkeypatch):
    """#243 must not move ABSORBER. Its absorption is the same `1 - R` it
    always was, and its run does not ask for a transmission monitor it has
    no use for -- with metal behind the surface, nothing gets through by
    construction, and measuring that costs solver time for a known zero."""
    captured = {}

    def fake_run(geometry, characteristic_length_m, nfreq, workdir):
        captured["geometry"] = geometry
        return _meep_result([0.2, 0.01], frequency_hz=(9e9, 10e9))

    monkeypatch.setattr(design_loop_module, "_run_meep_simulation", fake_run)
    state = start_design_loop(REQUIREMENTS)
    state = _grant_and_advance(state, DesignStep.ARCHITECTURE, _architecture_input("ABSORBER"))
    state = advance_loop_step(state, dict(_ABSORBER_ANALYSIS_INPUT))
    state = advance_loop_step(
        state, {"geometry": {"cell_size_m": [3e-3, 3e-3, 40e-3]}, "frequency_hz": 10e9}
    )

    assert "transmission_monitor_center_m" not in captured["geometry"]
    result = state.decisions[-1].result
    assert result["port_count"] == 1
    assert result["absorption_formula"] == "A = 1 - R"
    assert result["absorption"] == pytest.approx([0.8, 0.99])
    assert result["transmittance"] is None
    assert result["energy_balance_violations"] == []


# ---------------------------------------------------------------------------
# Issue #486: a reflector-provenance check wired into SIMULATION.
#
# ADR-0017's rule (captured by #484's host_ground_plane assertion and #485's
# REFLECTOR geometry role) has, until now, had nowhere it was actually read:
# a candidate whose family needs a ground plane could reach scoring having
# neither a REFLECTOR layer of its own nor a confirmed host. This section
# closes that gap at the one place a family's requirement and a candidate's
# geometry are both in hand -- the SIMULATION step -- mirroring
# `_require_transmission_monitor_for_two_port`'s own shape: a pure check,
# unit-tested directly, then proven wired in via the real step.
# ---------------------------------------------------------------------------

# Minimal role-tagged/untagged geometry fixtures. Only the `role` field (and,
# for the reflector case, which of materials/conductors it sits in) matters
# to this check -- shape/p1_m/p2_m are never read by it, so they're omitted
# except where a fixture needs to look like a real primitive.
_NO_ROLE_TAGS_GEOMETRY: dict[str, Any] = {"cell_size_m": [3e-3, 3e-3, 40e-3]}
_ROLE_TAGGED_NO_REFLECTOR_GEOMETRY: dict[str, Any] = {
    "materials": [{"role": "PATTERN", "epsilon_r": 2.9}],
}
_ROLE_TAGGED_WITH_REFLECTOR_GEOMETRY: dict[str, Any] = {
    "conductors": [{"role": "REFLECTOR"}],
    "materials": [{"role": "PATTERN", "epsilon_r": 2.9}],
}


def _confirmed_host_ground_plane_requirements(requirement_id: str = "host_backing") -> dict:
    """A `state.requirements`-shaped dict carrying one CONFIRMED,
    is_ground_plane=True host_ground_plane assertion (#484's own pure
    layer, not the DB-touching I/O wrapper) -- the fixture this section's
    "confirmed" cases reuse."""
    proposed = propose_host_ground_plane(is_ground_plane=True)
    confirmed = confirm_host_ground_plane(
        proposed, confirmed_by="jane.engineer", confirmed_at="2026-01-01T00:00:00+00:00"
    )
    return {
        requirement_id: {
            "requirement": "the host is solid aluminum",
            "host_ground_plane": confirmed,
        }
    }


class _FakeFamily:
    """A minimal stand-in carrying only what
    `_require_reflector_or_confirmed_host_ground_plane` reads
    (`requires_ground_plane`, `name`) -- deliberately NOT a real
    `DesignFamily`, so these unit tests exercise this check's own logic in
    isolation from `__post_init__`'s unrelated requires_ground_plane/
    port_count cross-check (issue #216), the same way
    `_require_transmission_monitor_for_two_port`'s own `getattr(family,
    'name', family)`/`getattr(family, 'port_count', None)` tolerate an
    arbitrary object rather than demanding a real registry entry."""

    def __init__(self, requires_ground_plane: bool, name: str = "FAKE_FAMILY"):
        self.requires_ground_plane = requires_ground_plane
        self.name = name


def test_any_requirement_confirms_host_ground_plane_is_false_for_no_requirements():
    assert _any_requirement_confirms_host_ground_plane({}) is False


def test_any_requirement_confirms_host_ground_plane_ignores_non_dict_requirements():
    """`state.requirements` in this test file's own REQUIREMENTS fixture
    carries plain scalar/list values (band_ghz, gain_dbi_min, ...), not
    requirement_id-keyed dicts -- this helper must not choke on that shape,
    only find nothing to confirm."""
    assert _any_requirement_confirms_host_ground_plane(REQUIREMENTS) is False


def test_any_requirement_confirms_host_ground_plane_true_when_any_entry_confirms():
    """The ambiguity resolution this ticket makes explicit: `requirements`
    holds several requirement entries, and this design's host is confirmed
    a ground plane if ANY of them carries a CONFIRMED, is_ground_plane=True
    assertion -- there is no single 'the' requirement id it must match."""
    requirements = {
        "req_band": {"requirement": "2.4-2.5 GHz"},
        **_confirmed_host_ground_plane_requirements("req_host"),
        "req_gain": {"requirement": "gain >= 5 dBi"},
    }
    assert _any_requirement_confirms_host_ground_plane(requirements) is True


def test_any_requirement_confirms_host_ground_plane_false_when_only_proposed():
    """A PROPOSED, unconfirmed reading is not enough (ADR-0017) -- mirrors
    the Host ground-plane assertion glossary entry's own "not a `CONFIRMED`
    assertion until a human confirms the reading" rule."""
    proposed = propose_host_ground_plane(is_ground_plane=True)
    requirements = {"req_host": {"requirement": "solid aluminum", "host_ground_plane": proposed}}
    assert _any_requirement_confirms_host_ground_plane(requirements) is False


def test_any_requirement_confirms_host_ground_plane_false_when_confirmed_false():
    """A human can confirm that the host is NOT a reliable ground plane --
    that is a genuine, informative CONFIRMED reading, and must not be
    read as satisfying the assertion."""
    proposed = propose_host_ground_plane(is_ground_plane=False)
    confirmed = confirm_host_ground_plane(proposed, confirmed_by="jane.engineer")
    requirements = {"req_host": {"requirement": "a PET film", "host_ground_plane": confirmed}}
    assert _any_requirement_confirms_host_ground_plane(requirements) is False


@pytest.mark.parametrize(
    "requires_ground_plane, geometry, requirements_confirmed, expect_raise",
    [
        # requires_ground_plane=False: exempt outright, in every geometry/
        # confirmation combination -- this family's physics does not depend
        # on a ground plane at all (ABSORBER_TRANSMISSIVE's own shape).
        (False, _NO_ROLE_TAGS_GEOMETRY, False, False),
        (False, _ROLE_TAGGED_NO_REFLECTOR_GEOMETRY, False, False),
        (False, _ROLE_TAGGED_WITH_REFLECTOR_GEOMETRY, False, False),
        (False, _ROLE_TAGGED_NO_REFLECTOR_GEOMETRY, True, False),
        # requires_ground_plane=True, no role tags anywhere: legacy/
        # non-role-tagging geometry is exempt (a DELIBERATE #481 decision,
        # not an oversight) -- covers NEC2's own wire geometry, which never
        # carries `role` at all.
        (True, _NO_ROLE_TAGS_GEOMETRY, False, False),
        # requires_ground_plane=True, role-tagged geometry, one REFLECTOR:
        # the candidate supplies its own reflector -- passes regardless of
        # whether any requirement also confirms the host.
        (True, _ROLE_TAGGED_WITH_REFLECTOR_GEOMETRY, False, False),
        (True, _ROLE_TAGGED_WITH_REFLECTOR_GEOMETRY, True, False),
        # requires_ground_plane=True, role-tagged geometry, no REFLECTOR,
        # host confirmed: the escape hatch ADR-0017 names -- passes.
        (True, _ROLE_TAGGED_NO_REFLECTOR_GEOMETRY, True, False),
        # requires_ground_plane=True, role-tagged geometry, no REFLECTOR,
        # host NOT confirmed: neither half of ADR-0017's rule is satisfied
        # -- must raise.
        (True, _ROLE_TAGGED_NO_REFLECTOR_GEOMETRY, False, True),
    ],
)
def test_reflector_provenance_check_full_combination_matrix(
    requires_ground_plane, geometry, requirements_confirmed, expect_raise
):
    family = _FakeFamily(requires_ground_plane=requires_ground_plane, name="A_TEST_FAMILY")
    requirements = _confirmed_host_ground_plane_requirements() if requirements_confirmed else {}

    if expect_raise:
        with pytest.raises(DesignLoopValidationError) as exc:
            _require_reflector_or_confirmed_host_ground_plane(family, geometry, requirements)
        message = str(exc.value)
        assert "A_TEST_FAMILY" in message
        assert "REFLECTOR" in message
        assert "host" in message.lower()
        assert "confirm_requirement_host_ground_plane" in message
    else:
        _require_reflector_or_confirmed_host_ground_plane(family, geometry, requirements)


def test_reflector_provenance_check_reads_conductors_as_well_as_materials():
    """A REFLECTOR primitive sitting in `conductors` (the common case -- a
    ground plane is a metal layer) must count exactly like one in
    `materials`; `_build_geometry_list` itself treats the two lists as one
    combined pool, and this check must agree with it."""
    family = _FakeFamily(requires_ground_plane=True)
    geometry = {"conductors": [{"role": "REFLECTOR"}]}
    _require_reflector_or_confirmed_host_ground_plane(family, geometry, {})  # must not raise


def test_reflector_provenance_check_geometry_missing_entirely_is_exempt():
    """`_handle_simulation` runs this check with whatever
    `step_input.get('geometry')` returns, which is `None` when a caller
    forgot the key entirely -- that must not crash this check itself; the
    handler's own `_require_fields` is what reports a missing geometry, and
    it must get the chance to say so, not have this check pre-empt it with
    an unrelated error."""
    family = _FakeFamily(requires_ground_plane=True)
    _require_reflector_or_confirmed_host_ground_plane(family, None, {})  # must not raise


def test_reflector_provenance_check_message_names_the_remedy():
    """The message shape `_require_transmission_monitor_for_two_port`
    itself uses: name the family, say what is missing, say what to do."""
    family = _FakeFamily(requires_ground_plane=True, name="REFLECTION_PHASE")
    with pytest.raises(DesignLoopValidationError) as exc:
        _require_reflector_or_confirmed_host_ground_plane(
            family, _ROLE_TAGGED_NO_REFLECTOR_GEOMETRY, {}
        )
    message = str(exc.value)
    assert "REFLECTION_PHASE" in message
    assert "role-tagged" in message or "role=REFLECTOR" in message
    assert "confirm_requirement_host_ground_plane" in message


# --- Integration: the check is actually wired into the SIMULATION step -----


def test_ground_backed_absorber_simulation_with_no_role_tags_is_unaffected(monkeypatch):
    """ABSORBER's own existing tests use geometry with no materials/
    conductors keys at all -- the legacy exemption must keep every one of
    those passing exactly as before; this pins that regression directly."""
    monkeypatch.setattr(
        design_loop_module,
        "_run_meep_simulation",
        lambda **kwargs: {
            "provenance": "SIMULATED",
            "simulator": "MEEP",
            "status": "COMPLETED",
            "s_parameters": {"frequency_hz": [10e9], "reflectance": [0.05]},
        },
    )
    state = start_design_loop(REQUIREMENTS)
    state = _grant_and_advance(state, DesignStep.ARCHITECTURE, _architecture_input("ABSORBER"))
    state = advance_loop_step(state, dict(_ABSORBER_ANALYSIS_INPUT))
    state = advance_loop_step(state, {"geometry": {}, "frequency_hz": 10e9})
    assert state.decisions[-1].result["simulator"] == "MEEP"


def test_ground_backed_family_with_role_tags_but_no_reflector_or_confirmation_refuses(
    monkeypatch,
):
    """ABSORBER declares requires_ground_plane=True. Once its candidate's
    own geometry opts into role-tagging (#485) but supplies no REFLECTOR,
    and no requirement on the design confirms the host, this must be
    refused before the solver runs -- not scored on a candidate that has
    neither its own reflector nor a vouched-for one."""

    def exploding_run(**kwargs):
        raise AssertionError("the solver must not run when neither half of ADR-0017 is met")

    monkeypatch.setattr(design_loop_module, "_run_meep_simulation", exploding_run)
    state = start_design_loop(REQUIREMENTS)
    state = _grant_and_advance(state, DesignStep.ARCHITECTURE, _architecture_input("ABSORBER"))
    state = advance_loop_step(state, dict(_ABSORBER_ANALYSIS_INPUT))
    with pytest.raises(DesignLoopValidationError) as exc:
        advance_loop_step(
            state,
            {
                "geometry": {
                    "cell_size_m": [3e-3, 3e-3, 40e-3],
                    "materials": [{"role": "PATTERN", "epsilon_r": 2.9}],
                },
                "frequency_hz": 10e9,
            },
        )
    message = str(exc.value)
    assert "ABSORBER" in message
    assert "REFLECTOR" in message
    assert state.current_step == DesignStep.SIMULATION.value
    assert all(d.step != DesignStep.SIMULATION.value for d in state.decisions)


def test_ground_backed_family_with_a_reflector_role_layer_runs(monkeypatch):
    """The candidate supplies its own reflector (#485's REFLECTOR role) --
    ADR-0017's default case -- so the run proceeds with no confirmed host
    assertion needed at all."""
    monkeypatch.setattr(
        design_loop_module,
        "_run_meep_simulation",
        lambda **kwargs: {
            "provenance": "SIMULATED",
            "simulator": "MEEP",
            "status": "COMPLETED",
            "s_parameters": {"frequency_hz": [10e9], "reflectance": [0.05]},
        },
    )
    state = start_design_loop(REQUIREMENTS)
    state = _grant_and_advance(state, DesignStep.ARCHITECTURE, _architecture_input("ABSORBER"))
    state = advance_loop_step(state, dict(_ABSORBER_ANALYSIS_INPUT))
    state = advance_loop_step(
        state,
        {
            "geometry": {
                "cell_size_m": [3e-3, 3e-3, 40e-3],
                "conductors": [{"role": "REFLECTOR"}],
            },
            "frequency_hz": 10e9,
        },
    )
    assert state.decisions[-1].result["simulator"] == "MEEP"


def test_ground_backed_family_with_confirmed_host_and_no_reflector_runs(monkeypatch):
    """ADR-0017's escape hatch: no REFLECTOR of its own, but this design's
    requirements confirm the host is a reliable ground plane -- so the run
    proceeds leaning on the host instead."""
    monkeypatch.setattr(
        design_loop_module,
        "_run_meep_simulation",
        lambda **kwargs: {
            "provenance": "SIMULATED",
            "simulator": "MEEP",
            "status": "COMPLETED",
            "s_parameters": {"frequency_hz": [10e9], "reflectance": [0.05]},
        },
    )
    requirements = {**REQUIREMENTS, **_confirmed_host_ground_plane_requirements()}
    state = start_design_loop(requirements)
    state = _grant_and_advance(state, DesignStep.ARCHITECTURE, _architecture_input("ABSORBER"))
    state = advance_loop_step(state, dict(_ABSORBER_ANALYSIS_INPUT))
    state = advance_loop_step(
        state,
        {
            "geometry": {
                "cell_size_m": [3e-3, 3e-3, 40e-3],
                "materials": [{"role": "PATTERN", "epsilon_r": 2.9}],
            },
            "frequency_hz": 10e9,
        },
    )
    assert state.decisions[-1].result["simulator"] == "MEEP"


def test_unbacked_transmissive_family_is_exempt_even_with_role_tags_and_no_confirmation(
    monkeypatch,
):
    """ABSORBER_TRANSMISSIVE declares requires_ground_plane=False: exempt
    outright regardless of role tags or host confirmation -- its physics
    never depended on a ground plane, so there is nothing here to check."""
    state, captured = _run_two_port_simulation(
        monkeypatch,
        _meep_result([0.2], {"computed": True, "requested": True, "transmittance": [0.3]}),
        geometry={
            **_TWO_PORT_GEOMETRY,
            "materials": [{"role": "PATTERN", "epsilon_r": 2.9}],
        },
    )
    assert state.decisions[-1].result["simulator"] == "MEEP"


# ---------------------------------------------------------------------------
# Issue #255 ticket 1: OPTIMIZATION dispatches on the family's declared
# optimizer_class (designs/design_families.py), mirroring the
# _registry_family_of_record seam ANALYSIS (#239) and SIMULATION (#229)
# already use -- rather than the single, unconditional patch-length search
# this step ran before. A pure prefactor: no family in this tree today
# declares anything other than None, so every one of them must keep routing
# to exactly the search it always ran. The one new capability this ticket
# adds is a safety net: a family that DOES declare something this loop has
# no path for (COMBINATORIAL today; a hypothetical third value later) must
# fail loudly rather than silently receive the continuous patch-length
# search -- the same "wrong tool applied silently" defect issues #239/#241
# already removed for ANALYSIS/SIMULATION, one step over. The real
# COMBINATORIAL symbol-placement search itself is separate, later work
# (issue #255's own scope) -- not built here.
# ---------------------------------------------------------------------------


def _at_optimization(family: str) -> DesignLoopState:
    """An iteration whose ARCHITECTURE named `family`, positioned at
    OPTIMIZATION without running ANALYSIS/SIMULATION for real -- these tests
    are about the optimizer_class dispatch, not about those steps' own
    behaviour (mirrors `_at_simulation` above)."""
    state = start_design_loop(REQUIREMENTS)
    state = _grant_and_advance(state, DesignStep.ARCHITECTURE, _architecture_input(family))
    return _advance_to(state, DesignStep.OPTIMIZATION)


_OPTIMIZATION_PATCH_INPUT = {
    "eps_r": 4.4,
    "w_m": 0.03,
    "h_m": 0.0016,
    "target_frequency_hz": 2.45e9,
    "length_lower_m": 0.02,
    "length_upper_m": 0.04,
    "method": "sweep",
    "n_evaluations": 5,
}


def test_optimizer_class_for_reads_none_for_a_family_that_declares_nothing():
    """PATCH declares no optimizer_class at all in designs/design_families.py
    today. Unlike an unsettled simulation_adapter, that is a legitimate,
    un-raising answer here -- not a missing-declaration error (ADR-0018:
    the field is open, unset until a family opts in)."""
    state = _at_optimization("PATCH")
    assert _optimizer_class_for(state) is None


def test_optimizer_class_for_reads_an_explicitly_declared_value(monkeypatch):
    """The helper reads whatever the registry entry declares -- proven with
    a fake PATCH-shaped family so this test's assertion is about the
    helper's own read-the-declaration behaviour, independently of which
    real family(s) currently declare COMBINATORIAL (issue #267 gave
    REFLECTION_PHASE/DIFFUSIVE that declaration for real; see
    test_reflection_phase_and_diffusive_declare_combinatorial_optimizer_class
    below for that claim)."""
    combinatorial = _dc_replace(design_families_module.PATCH, optimizer_class="COMBINATORIAL")
    monkeypatch.setattr(design_loop_module, "_get_design_family", lambda _name: combinatorial)
    state = _at_optimization("PATCH")
    assert _optimizer_class_for(state) == "COMBINATORIAL"


def test_reflection_phase_and_diffusive_declare_combinatorial_optimizer_class():
    """Issue #267 acceptance criterion 1: REFLECTION_PHASE and DIFFUSIVE --
    CONTEXT.md/issue #109's own Tier B "which characterised symbol goes in
    which grid square" families -- declare optimizer_class="COMBINATORIAL"
    in designs/design_families.py, so _handle_optimization's dispatch
    actually routes them to the real combinatorial search below instead of
    raising "not wired yet" (ticket 1's interim state)."""
    assert design_families_module.REFLECTION_PHASE.optimizer_class == "COMBINATORIAL"
    assert design_families_module.DIFFUSIVE.optimizer_class == "COMBINATORIAL"


def test_every_other_registered_family_s_optimizer_class_is_unaffected_by_267():
    """Byte-for-byte regression, matching issue #255 ticket 1's own
    regression-coverage style (see test_optimization_routes_patch_to_the_
    unchanged_patch_length_search below): opting REFLECTION_PHASE/DIFFUSIVE
    into COMBINATORIAL must not change ANY other registered family's own
    declared optimizer_class -- every one of them is still unset (`None`),
    the same "no family has opted in" state ADR-0018 left them in."""
    unaffected = {
        "ABSORBER": design_families_module.ABSORBER,
        "ABSORBER_TRANSMISSIVE": design_families_module.ABSORBER_TRANSMISSIVE,
        "PATCH": design_families_module.PATCH,
        "POLARIZATION_CONVERTER": design_families_module.POLARIZATION_CONVERTER,
    }
    for name, family in unaffected.items():
        assert family.optimizer_class is None, (
            f"{name} declares optimizer_class={family.optimizer_class!r}; issue "
            "#267 must only change REFLECTION_PHASE/DIFFUSIVE"
        )


def test_no_architecture_decision_means_there_is_no_optimizer_class_to_read():
    """Mirrors test_no_architecture_decision_means_there_is_no_adapter_to_
    read: with no ARCHITECTURE decision, no family has been named, so there
    is nothing to read optimizer_class off -- reported, not guessed past."""
    state = start_design_loop(REQUIREMENTS)
    with pytest.raises(DesignLoopValidationError, match="design_family"):
        _optimizer_class_for(state)


def test_optimization_routes_patch_to_the_unchanged_patch_length_search(monkeypatch):
    """The core "byte-for-byte unchanged" claim: PATCH's optimizer_class is
    unset (None) in the real registry, and OPTIMIZATION must still call
    optimize_patch_length_for_target_frequency with EXACTLY the same
    keyword arguments -- and hand its result straight through -- as it did
    before this ticket's dispatch existed."""
    captured = {}

    def fake_optimize(**kwargs):
        captured.update(kwargs)
        return {"achieved_frequency_hz": 2.451e9, "provenance": "CALCULATED"}

    monkeypatch.setattr(
        design_loop_module, "_optimize_patch_length_for_target_frequency", fake_optimize
    )
    state = _at_optimization("PATCH")
    new_state = advance_loop_step(state, dict(_OPTIMIZATION_PATCH_INPUT))

    assert captured == {
        "eps_r": 4.4,
        "w_m": 0.03,
        "h_m": 0.0016,
        "target_frequency_hz": 2.45e9,
        "length_lower_m": 0.02,
        "length_upper_m": 0.04,
        "method": "sweep",
        "n_evaluations": 5,
    }
    decision = new_state.decisions[-1]
    assert decision.step == DesignStep.OPTIMIZATION.value
    assert decision.kind == "optimization"
    assert decision.result == {"achieved_frequency_hz": 2.451e9, "provenance": "CALCULATED"}
    assert decision.provenance == "CALCULATED"


def test_optimization_routes_an_explicitly_continuous_family_the_same_way(monkeypatch):
    """optimizer_class == "CONTINUOUS" (stated explicitly, not merely
    unset) must route to the identical patch-length search -- proving the
    dispatch reads the DECLARED value, never the family's name, the same
    "read the declaration, not the label" rule #239/#229 already applied to
    ANALYSIS/SIMULATION."""
    continuous = _dc_replace(design_families_module.PATCH, optimizer_class="CONTINUOUS")
    monkeypatch.setattr(design_loop_module, "_get_design_family", lambda _name: continuous)

    def fake_optimize(**kwargs):
        return {"achieved_frequency_hz": 2.451e9, "provenance": "CALCULATED"}

    monkeypatch.setattr(
        design_loop_module, "_optimize_patch_length_for_target_frequency", fake_optimize
    )
    state = _at_optimization("PATCH")
    new_state = advance_loop_step(state, dict(_OPTIMIZATION_PATCH_INPUT))
    assert new_state.decisions[-1].result["achieved_frequency_hz"] == pytest.approx(2.451e9)


_COMBINATORIAL_SYMBOL_ENTRIES = [
    {
        # "id" (issue #400): a real designs.element_alphabet.
        # fetch_symbol_entries row always carries its own BIGSERIAL "id"
        # (db/schema.sql) -- present here so this hand-built fixture can
        # exercise SymbolOption.entry_id/CombinatorialPlacementResult.
        # entry_id_layout threading through _combinatorial_candidate_
        # options end to end, the same way a real alphabet-library lookup
        # would.
        "id": 501,
        "element_family": "interdigital_elc",
        "symbol": "elc_finger_4",
        "frequency_low_hz": 8.0e9,
        "frequency_high_hz": 12.0e9,
        "incidence_angle_low_deg": 0.0,
        "incidence_angle_high_deg": 30.0,
        "process_id": 1,
        "geometry": {"shape": "box", "p1_m": [0.0, 0.0, 0.0], "p2_m": [0.001, 0.001, 0.0]},
        "response": [{"frequency_hz": 10.0e9, "magnitude": 0.99, "phase_deg": 0.0}],
    },
    {
        "id": 502,
        "element_family": "interdigital_elc",
        "symbol": "elc_finger_6",
        "frequency_low_hz": 8.0e9,
        "frequency_high_hz": 12.0e9,
        "incidence_angle_low_deg": 0.0,
        "incidence_angle_high_deg": 30.0,
        "process_id": 1,
        "geometry": {"shape": "box", "p1_m": [0.002, 0.0, 0.0], "p2_m": [0.003, 0.001, 0.0]},
        "response": [{"frequency_hz": 10.0e9, "magnitude": 0.97, "phase_deg": 180.0}],
    },
]

_COMBINATORIAL_OPTIMIZATION_INPUT = {
    "element_family": "interdigital_elc",
    "symbol_entries": _COMBINATORIAL_SYMBOL_ENTRIES,
    "frequency_hz": 10.0e9,
    "incidence_angle_deg": 15.0,
    "process_id": 1,
    "target": [[0.0, 180.0]],
    "delta_phi_max_deg": 200.0,
    "random_seed": 1,
}


# NOTE ON THE TEST THIS REPLACED (test_optimization_refuses_a_combinatorial_
# family_instead_of_guessing): that test encoded ticket 1's INTERIM safety
# net -- REFLECTION_PHASE declaring optimizer_class="COMBINATORIAL" had to
# raise, because nothing was wired for it yet. Issue #267 (this ticket) is
# what finishes wiring it, so that premise is no longer true, BY DESIGN --
# this is a deliberate, expected consequence of finishing #255/#267, not an
# accidental regression. test_optimization_refuses_an_unrecognised_
# optimizer_class below still covers "an unhandled value still raises" with
# a made-up third value, unchanged.
def test_optimization_routes_a_combinatorial_family_to_the_real_combinatorial_search(
    monkeypatch,
):
    """Issue #267: REFLECTION_PHASE now genuinely declares optimizer_class
    ="COMBINATORIAL" (designs/design_families.py, unmonkeypatched -- the
    real registry entry), and OPTIMIZATION must route it to the real
    combinatorial symbol-placement search, resolving real candidates from
    the supplied symbol_entries and returning a real placed layout through
    the SAME successful-step shape (kind="optimization", a dict result,
    CALCULATED provenance) the continuous path already uses -- never the
    patch-length search."""

    def exploding_patch_search(**kwargs):
        raise AssertionError("the patch-length search must never run for a COMBINATORIAL family")

    monkeypatch.setattr(
        design_loop_module, "_optimize_patch_length_for_target_frequency", exploding_patch_search
    )
    state = _at_optimization("REFLECTION_PHASE")
    new_state = advance_loop_step(state, dict(_COMBINATORIAL_OPTIMIZATION_INPUT))

    decision = new_state.decisions[-1]
    assert decision.step == DesignStep.OPTIMIZATION.value
    assert decision.kind == "optimization"
    assert decision.provenance == "CALCULATED"
    assert decision.result["method"] == "combinatorial_symbol_placement"
    # Each candidate matches its target exactly (0 deg / 180 deg), so the
    # search should find the exact assignment with ~zero error.
    assert decision.result["layout"] == [["elc_finger_4", "elc_finger_6"]]
    assert decision.result["achieved_error"] == pytest.approx(0.0, abs=1e-6)
    # Issue #400: entry_id_layout names WHICH matched symbol_alphabet_
    # entries row (id=501/502 in the fixture above) backed each winning
    # cell -- not just its bare symbol_id, which "layout" alone reports and
    # which cannot disambiguate several entries sharing one symbol/band/
    # process (ADR-0027 point 4).
    assert decision.result["entry_id_layout"] == [[501, 502]]
    # candidate_snapshot is JSON-safe (a list, not a dict keyed by tuples),
    # and each candidate now also names its own entry_id (issue #400) --
    # not just the winning cell above, every AVAILABLE candidate.
    assert isinstance(decision.result["candidate_snapshot"], list)
    snapshot_entry_ids = {
        candidate["entry_id"]
        for row in decision.result["candidate_snapshot"]
        for candidate in row["candidates"]
    }
    assert snapshot_entry_ids == {501, 502}
    assert new_state.current_step == DesignStep.VERIFICATION.value


def test_optimization_combinatorial_end_to_end_with_real_alphabet_rows(db_conn):
    """Issue #267 acceptance criterion 2: seed REAL rows via
    designs.element_alphabet.insert_process_record/insert_symbol_entry
    against the live Postgres already reachable in this environment
    (tests/conftest.py's db_conn fixture -- a real psycopg connection,
    rolled back on teardown, tests/test_element_alphabet.py's own
    TestSymbolAlphabetEntryDatabaseRoundTrip pattern), fetch them back with
    fetch_symbol_entries exactly the way a real caller would, then drive a
    REFLECTION_PHASE design loop to its OPTIMIZATION step and confirm the
    real placed layout comes back through the SAME successful-step shape
    (the same decision-recording path via advance_loop_step) the
    CONTINUOUS path already uses -- not a special-cased return shape.

    Also issue #400 acceptance criterion 3, proven against these REAL
    inserted rows rather than a hand-built id in a fixture: a query against
    this persisted result's entry_id_layout can answer "which measured
    process backed cell (i, j)" by cross-referencing the row's own real
    `id` (RETURNING * from the live INSERT below) -- not merely a symbol
    name that, in production, could match several such rows."""
    process = insert_process_record(
        db_conn,
        machine="Voltera NOVA",
        ink="MXene Ti3C2Tx",
        ink_grade="battery grade",
        substrate_stack="50 um PET on 3 mm PDMS carrier",
        pass_count=3,
        achieved_film_thickness_m=12.0e-6,
        cure_schedule="80 degrees C for 30 min, ambient RH",
    )
    entry_finger_4 = insert_symbol_entry(
        db_conn,
        element_family="interdigital_elc",
        symbol="elc_finger_4",
        frequency_low_hz=8.0e9,
        frequency_high_hz=12.0e9,
        incidence_angle_low_deg=0.0,
        incidence_angle_high_deg=30.0,
        process_id=process["id"],
        geometry={"shape": "box", "p1_m": [0.0, 0.0, 0.0], "p2_m": [0.001, 0.001, 0.0]},
        response=[{"frequency_hz": 10.0e9, "magnitude": 0.99, "phase_deg": 0.0}],
    )
    entry_finger_6 = insert_symbol_entry(
        db_conn,
        element_family="interdigital_elc",
        symbol="elc_finger_6",
        frequency_low_hz=8.0e9,
        frequency_high_hz=12.0e9,
        incidence_angle_low_deg=0.0,
        incidence_angle_high_deg=30.0,
        process_id=process["id"],
        geometry={"shape": "box", "p1_m": [0.002, 0.0, 0.0], "p2_m": [0.003, 0.001, 0.0]},
        response=[{"frequency_hz": 10.0e9, "magnitude": 0.97, "phase_deg": 180.0}],
    )
    fetched_entries = fetch_symbol_entries(db_conn, "interdigital_elc")
    assert len(fetched_entries) == 2  # both rows this test just inserted, nothing stale

    state = _at_optimization("REFLECTION_PHASE")
    step_input = {
        "element_family": "interdigital_elc",
        "symbol_entries": fetched_entries,
        "frequency_hz": 10.0e9,
        "incidence_angle_deg": 15.0,
        "process_id": process["id"],
        "target": [[0.0, 180.0]],
        "delta_phi_max_deg": 200.0,
        "random_seed": 1,
    }
    new_state = advance_loop_step(state, step_input)

    decision = new_state.decisions[-1]
    assert decision.step == DesignStep.OPTIMIZATION.value
    assert decision.kind == "optimization"
    assert decision.provenance == "CALCULATED"
    assert decision.result["method"] == "combinatorial_symbol_placement"
    assert decision.result["layout"] == [["elc_finger_4", "elc_finger_6"]]
    assert decision.result["achieved_error"] == pytest.approx(0.0, abs=1e-6)
    # Issue #400: the winning layout's own entry_id_layout names the REAL
    # symbol_alphabet_entries.id backing each cell -- the exact ids
    # returned by the live INSERT ... RETURNING * calls above, not a
    # fixture-supplied stand-in.
    assert decision.result["entry_id_layout"] == [[entry_finger_4["id"], entry_finger_6["id"]]]
    # decision.input carries the query this entry_id_layout was resolved
    # under (process_id, frequency_hz, ...) -- together with entry_id_
    # layout above, this is what answers "which measured process backed
    # cell (i, j)"; orchestration/tooling.py's own flush-boundary fix
    # (tests/test_tooling.py's test_flush_target_for_folds_decision_input_
    # into_engineering_result_value) is what stops this from being dropped
    # once persisted.
    assert decision.input["process_id"] == process["id"]
    assert new_state.current_step == DesignStep.VERIFICATION.value


def test_optimization_combinatorial_zero_matching_entries_fails_loudly():
    """Design decision 4a: a shared candidate lookup that matches NOTHING
    (the real state of the alphabet in production today -- issue #132's
    print-and-measure work has not happened) must raise a clear,
    named error identifying the missing key, and never fall through to the
    continuous patch-length search."""
    state = _at_optimization("REFLECTION_PHASE")
    step_input = dict(_COMBINATORIAL_OPTIMIZATION_INPUT, symbol_entries=[])
    with pytest.raises(DesignLoopValidationError) as exc:
        advance_loop_step(state, step_input)
    message = str(exc.value)
    assert "REFLECTION_PHASE" in message
    assert "interdigital_elc" in message
    assert repr(10.0e9) in message  # frequency_hz, named exactly
    assert "15.0" in message  # incidence_angle_deg
    assert "process_id=1" in message
    assert state.current_step == DesignStep.OPTIMIZATION.value
    assert all(d.step != DesignStep.OPTIMIZATION.value for d in state.decisions)


def test_optimization_combinatorial_no_entries_match_this_bands_process_fails_loudly():
    """Same design decision 4a failure mode as the fully-empty-alphabet test
    above, but against the more realistic production shape: a NON-empty
    alphabet that holds real, otherwise-valid entries -- just none that
    match THIS design's band/incidence-angle/process point query. Issue
    #267's acceptance criterion is "a grid position with no matching
    alphabet entries," which an entries-exist-elsewhere alphabet satisfies
    just as much as a literally-empty one; both take the identical code
    path (_combinatorial_candidate_options returns [], the same raise
    fires), but this is the shape a populated alphabet actually produces
    once issue #132's print-and-measure work lands."""
    other_band_entries = [
        dict(entry, frequency_low_hz=1.0e9, frequency_high_hz=2.0e9)
        for entry in _COMBINATORIAL_SYMBOL_ENTRIES
    ]
    state = _at_optimization("REFLECTION_PHASE")
    # _COMBINATORIAL_OPTIMIZATION_INPUT queries frequency_hz=10.0e9, well
    # outside every entry's now-shifted 1-2 GHz band -- element_family,
    # symbol, incidence_angle_deg, and process_id all still match; only the
    # band doesn't, so this exercises the "point query misses" path, not
    # an empty-list shortcut.
    step_input = dict(_COMBINATORIAL_OPTIMIZATION_INPUT, symbol_entries=other_band_entries)
    with pytest.raises(DesignLoopValidationError) as exc:
        advance_loop_step(state, step_input)
    message = str(exc.value)
    assert "REFLECTION_PHASE" in message
    assert "interdigital_elc" in message
    assert repr(10.0e9) in message  # frequency_hz, named exactly
    assert "process_id=1" in message
    assert state.current_step == DesignStep.OPTIMIZATION.value
    assert all(d.step != DesignStep.OPTIMIZATION.value for d in state.decisions)


def test_optimization_combinatorial_empty_candidate_shelf_is_wrapped(monkeypatch):
    """Design decision 4b: EmptyCandidateShelfError -- raised by
    optimization.combinatorial.combinatorial_symbol_placement itself if a
    narrower gap slips past the zero-match check above -- must surface as
    this loop's own DesignLoopValidationError, with the underlying
    message intact, the same wrapping convention _handle_architecture/
    _handle_analysis already use for their own adapter-level exceptions."""

    def exploding_search(**kwargs):
        raise design_loop_module._EmptyCandidateShelfError(
            "position(s) [(1, 0)] have zero candidate symbols to search over."
        )

    monkeypatch.setattr(design_loop_module, "_combinatorial_symbol_placement", exploding_search)
    state = _at_optimization("REFLECTION_PHASE")
    with pytest.raises(DesignLoopValidationError, match="zero candidate symbols"):
        advance_loop_step(state, dict(_COMBINATORIAL_OPTIMIZATION_INPUT))


def test_optimization_combinatorial_ragged_target_fails_loudly_as_a_named_error():
    """Design decision 4c: a ragged `target` (rows of unequal length) must
    be rejected by THIS handler's own guard, as a named
    DesignLoopValidationError -- not slip past it and only get caught by
    optimization.combinatorial.combinatorial_symbol_placement's own
    _validate_target, which raises a bare, un-wrapped ValueError that this
    handler's `except _EmptyCandidateShelfError` clause does not catch.
    Candidate resolution succeeds first (real matching entries), so this
    test proves the target-shape guard specifically, not the zero-match
    path covered above."""
    state = _at_optimization("REFLECTION_PHASE")
    ragged_input = dict(_COMBINATORIAL_OPTIMIZATION_INPUT, target=[[0.0, 180.0], [90.0]])
    with pytest.raises(DesignLoopValidationError, match="rectangular"):
        advance_loop_step(state, ragged_input)
    assert state.current_step == DesignStep.OPTIMIZATION.value
    assert all(d.step != DesignStep.OPTIMIZATION.value for d in state.decisions)


def test_combinatorial_result_to_dict_orders_candidate_snapshot_row_major():
    """candidate_snapshot's JSON conversion must walk the grid the SAME
    row-major, j-outer/i-inner order every other grid walk this feature
    touches already uses -- optimization.combinatorial's own
    `positions = [(i, j) for j in range(n_rows) for i in range(n_cols)]`
    and `_grid_from_choices`'s `layout[j][i]`. A 2-row, 2-col fake result
    is built with its `candidate_snapshot` dict populated out of order, and
    the resulting list must still come back as [(0,0), (1,0), (0,1), (1,1)]
    -- j varying slowest, i fastest -- not the column-major (i, j) tuple
    order plain `sorted()` on the dict would give."""
    option = SymbolOption(symbol_id="elc_finger_4", achieved_value=0.0)
    fake_result = CombinatorialPlacementResult(
        method="combinatorial_symbol_placement",
        layout=[["a", "b"], ["c", "d"]],
        achieved_error=0.0,
        evaluations=[],
        target=[[0.0, 0.0], [0.0, 0.0]],
        candidate_snapshot={
            (1, 1): [option],
            (0, 0): [option],
            (1, 0): [option],
            (0, 1): [option],
        },
        delta_phi_max_deg=200.0,
        random_seed=1,
    )
    recorded = _combinatorial_result_to_dict(fake_result)
    assert [(entry["i"], entry["j"]) for entry in recorded["candidate_snapshot"]] == [
        (0, 0),
        (1, 0),
        (0, 1),
        (1, 1),
    ]


def test_optimization_refuses_an_unrecognised_optimizer_class(monkeypatch):
    """ADR-0018 leaves optimizer_class open for a THIRD value (e.g.
    ML-direct inverse design) to arrive later. Issue #255 user story 4:
    that must fail loudly at OPTIMIZATION, naming the family and the
    unhandled value, rather than falling through to the patch-length
    search."""
    ml_direct = _dc_replace(
        design_families_module.PATCH, optimizer_class="ML_DIRECT_INVERSE_DESIGN"
    )
    monkeypatch.setattr(design_loop_module, "_get_design_family", lambda _name: ml_direct)

    def exploding_patch_search(**kwargs):
        raise AssertionError(
            "the patch-length search must never run for an unhandled optimizer_class"
        )

    monkeypatch.setattr(
        design_loop_module, "_optimize_patch_length_for_target_frequency", exploding_patch_search
    )
    state = _at_optimization("PATCH")
    with pytest.raises(DesignLoopValidationError) as exc:
        advance_loop_step(state, {})
    message = str(exc.value)
    assert "PATCH" in message
    assert "ML_DIRECT_INVERSE_DESIGN" in message
    assert state.current_step == DesignStep.OPTIMIZATION.value
    assert all(d.step != DesignStep.OPTIMIZATION.value for d in state.decisions)


def test_optimization_dispatches_through_a_lookup_table_like_its_two_siblings(monkeypatch):
    """Issue #508: `_handle_optimization` claimed in its own docstring to
    mirror `_handle_analysis`/`_handle_simulation`'s dict-dispatch pattern
    (`_ANALYSIS_MODELS`/`_SIMULATION_ADAPTERS`), but actually used a chain
    of `if/elif optimizer_class == ... / raise` checks -- no lookup table
    existed to name. This pins the same shape those two siblings have:

      * a module-level `_OPTIMIZER_HANDLERS` dict (this loop's counterpart
        to `_ANALYSIS_MODELS`/`_SIMULATION_ADAPTERS`) mapping every
        currently-supported `optimizer_class` value to its handler
        function, so a reader (or the error message below) can point at
        one place that lists what is wired;
      * the "no handler wired" error for an unrecognised value NAMES that
        table, the same way `_handle_analysis`'s error says "Add one to
        _ANALYSIS_MODELS in orchestration/design_loop.py" and
        `_handle_simulation`'s says "Wire one in orchestration/
        design_loop.py's _SIMULATION_ADAPTERS" -- rather than pointing at
        the dispatcher function itself, which is what the old if/elif
        chain's message did.
    """
    assert hasattr(design_loop_module, "_OPTIMIZER_HANDLERS")
    handlers = design_loop_module._OPTIMIZER_HANDLERS
    assert set(handlers) == {"CONTINUOUS", "COMBINATORIAL"}
    assert handlers["COMBINATORIAL"] is design_loop_module._optimize_combinatorial_symbol_placement
    assert callable(handlers["CONTINUOUS"])

    ml_direct = _dc_replace(
        design_families_module.PATCH, optimizer_class="ML_DIRECT_INVERSE_DESIGN"
    )
    monkeypatch.setattr(design_loop_module, "_get_design_family", lambda _name: ml_direct)
    state = _at_optimization("PATCH")
    with pytest.raises(DesignLoopValidationError) as exc:
        advance_loop_step(state, {})
    message = str(exc.value)
    assert "no handler wired for it" in message
    assert "_OPTIMIZER_HANDLERS" in message
    assert "orchestration/design_loop.py" in message
    assert "designs/design_families.py" in message
