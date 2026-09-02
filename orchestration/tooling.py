"""The design-iteration loop's agent/MCP tool surface (issue #46) -- three
focused, JSON-in/JSON-out functions, per this ticket's own scope guidance
("a reasonable, narrow agent/MCP tool surface is: a tool to start a new
loop, a tool to advance to the next step, and a tool to inspect current
state -- three focused tools, not one that tries to do everything"). See
agent/main.py's start_design_loop/advance_design_loop_step/
inspect_design_loop_state tools (principal role) and
mcp_server/server.py's mirrors of the same.

Each function here takes/returns plain dicts so the loop's state crosses
the agent/MCP JSON tool boundary and back unchanged -- the caller (an
agent conversation, or any other MCP client) holds it and passes it back
in on the next call, per design_loop.py's "STATE DESIGN" note. The dict is
no longer exactly DesignLoopState.to_dict(): it also carries `design_id`
(the backing `designs` row created by start_new_design_loop) and
`persisted_decision_count` (this module's own bookkeeping -- see
"PERSISTENCE" below). `DesignLoopState.from_dict` ignores unknown keys, so
extending the dict this way doesn't require design_loop.py to know
anything about either field.

PERSISTENCE (docs/adr/0011). design_loop.py's own module docstring
deferred this to "a FUTURE ticket" -- this is that ticket. Two flush
points, both `REDESIGN_DECISION` outcomes:

  - `next_action="iterate"`: every decision recorded since the last flush
    (this iteration's ARCHITECTURE through REDESIGN_DECISION) is written
    to decision_records/engineering_results/verification_items, and
    `designs.status` moves to ANALYSIS (the next iteration starts there).
  - `next_action="accept_design"`: the same flush, and `designs.status`
    moves to PASS.

No other transition writes anything -- see _maybe_flush below. All writes
for one flush share a single connection/transaction (design_id/design_key
requirements: DesignLoopState.decisions[persisted_decision_count:] is
never partially written -- either the whole batch commits, or the
exception propagates and the caller's PRE-transition state, which they
still hold, remains the only valid state (`advance_design_loop_step`
raises rather than returning a state that claims the transition
succeeded). This module calls `designs.db` functions directly (not
`designs.service`'s per-call-own-connection wrappers) specifically so a
whole iteration's decisions share one transaction rather than each
landing (or not) independently.

`orchestration/design_loop.py` gains no database awareness for any of
this -- every DB call here happens in this module, wrapping the pure
state machine.

REQUIREMENTS SHAPE. `start_new_design_loop`'s `requirements` must be in
the SAME shape `designs.service.create_design` expects -- a dict keyed by
`requirement_id`, each value carrying a `requirement` text field (see
`designs.validation.validate_requirements`) -- not the looser "customer
requirement" free-form dict `orchestration.design_loop.start_design_loop`'s
own docstring describes (frequency band, gain/VSWR/bandwidth target, form
factor, host-surface curvature, platform). This is a deliberate
reconciliation, not an oversight: the loop's REQUIREMENTS decision now
backs a real `designs` row with real, auto-created `verification_items`
rows (one per `requirement_id`) that the loop's own VERIFICATION step
already expects to be able to target by `requirement_id` -- there is no
honest way to keep both shapes and know which one `verify_requirement`
step_input's `requirement_id` is supposed to match. A caller wanting to
capture a customer requirement's own descriptive fields (frequency band,
gain target, etc.) that don't fit this shape can carry them inside each
requirement's own free-form extra keys, or as prose in `requirement`
itself -- `validate_requirements` only checks for the `requirement` text
field, never rejects extra ones.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import designs.db as designs_db
import designs.service as designs_service
from designs.models import DesignStatus
from designs.validation import InvalidRequirementsError, InvalidVerificationStatusError

from .design_loop import (
    DesignLoopState,
    DesignStep,
    LoopDecision,
    advance_loop_step,
    start_design_loop,
)

# LoopDecision.step (a DesignStep value) -> the real function name that
# produced its result, for engineering_results.tool_name -- see
# design_loop.py's own module docstring for which Phase 1/6/9/10/11
# function each step calls. Deliberately NOT reusing designs/provenance.py's
# tool-name table: these are the design loop's own internal function
# names (patch_resonant_frequency_hz, run_nec2_simulation, ...), a
# different vocabulary than the ~65 agent/MCP tool names that table maps,
# and provenance for every one of these is passed explicitly from the
# loop's own already-computed LoopDecision.provenance (docs/adr/0011),
# never looked up from this table.
_STEP_TO_TOOL_NAME: dict[str, str] = {
    DesignStep.ANALYSIS.value: "patch_resonant_frequency_hz",
    DesignStep.SIMULATION.value: "run_nec2_simulation",
    DesignStep.OPTIMIZATION.value: "optimize_patch_length_for_target_frequency",
    DesignStep.MEASUREMENT.value: "run_vna_measurement",
    DesignStep.CORRELATION.value: "correlate_simulation_measurement",
}

# LoopDecision.kind values that carry a computed result, bound for
# engineering_results -- everything else (architecture_decision,
# redesign_decision -> decision_records; verification_record ->
# verification_items; requirements -> nothing, see below) is handled by
# its own branch in _flush_one_decision.
_ENGINEERING_RESULT_KINDS = frozenset(
    {"calculation", "simulation", "optimization", "measurement", "correlation"}
)

# design_loop.py's own VERIFICATION_STATUSES (verification/README.md's
# vocabulary: PASS/CONDITIONAL PASS/FAIL/NOT VERIFIED/BLOCKED) is WIDER
# than designs.models.VerificationStatus (NOT VERIFIED/PASS/FAIL/MARGINAL
# -- CONTEXT.md's "Verification item"), a pre-existing mismatch this
# module's flush is the first thing to actually exercise: a VERIFICATION
# step recording "CONDITIONAL PASS" or "BLOCKED" is accepted by the loop's
# own _handle_verification, but designs.db.verify_requirement would
# reject it outright at the next flush -- permanently, since the decision
# is already baked into the caller's held state by then, with no way to
# retry past it. Reconciled here (not in design_loop.py, which stays
# unaware of designs.models' narrower vocabulary) by mapping the two
# extra values down to their closest designs.models equivalent, same
# spirit as this module's REQUIREMENTS SHAPE reconciliation above:
# CONDITIONAL PASS -> MARGINAL (passes with reservations), BLOCKED -> FAIL
# (conservative -- an unresolved blocker is treated as a failure to
# verify, not silently as a pass). The original design-loop status is
# never silently lost: _flush_target_for appends it to `notes`.
_VERIFICATION_STATUS_MAP = {
    "CONDITIONAL PASS": "MARGINAL",
    "BLOCKED": "FAIL",
}


class DesignLoopPersistenceError(RuntimeError):
    """Raised when a design-loop flush (docs/adr/0011) cannot be written --
    either a real database error, or a designs.db call refusing the write
    (a record_key collision, an unknown requirement_id, ...). None of
    these should ever legitimately occur during a design-loop-driven
    flush -- the loop's own step handlers already validated their inputs
    before this point -- so any such refusal is treated as a bug worth
    failing loudly on, not a recoverable case to route around. Raised
    instead of returning a state that claims the transition succeeded;
    the caller's pre-transition state (which they still hold) remains the
    only valid state (docs/adr/0011's "fail loud" decision)."""


@dataclass(frozen=True)
class _FlushTarget:
    """One decision's destination: which designs.db function to call, and
    with what arguments -- computed by _flush_one_decision, executed by
    _flush_decisions on the shared transaction."""

    call: Any
    kwargs: dict[str, Any]


def _flush_target_for(
    decision: LoopDecision, design_id: int, design_key: str, loop_id: str, iteration: int
) -> _FlushTarget | None:
    """The designs.db call one LoopDecision translates to, or None for a
    decision kind with nothing to persist (`requirements` -- it already
    became the design's own `requirements`/`verification_items` at
    creation time, via start_new_design_loop's create_design call, not a
    decision_records/engineering_results/verification_items row)."""
    record_key = f"{design_key}-{loop_id}-iter{iteration}-{decision.step}"

    if decision.kind in ("architecture_decision", "redesign_decision"):
        return _FlushTarget(
            designs_db.record_decision,
            {
                "design_id": design_id,
                "record_key": record_key,
                "decision": decision.input["decision"],
                "alternatives": [],
                "rationale": decision.input["rationale"],
                "evidence": [],
            },
        )
    if decision.kind == "verification_record":
        loop_status = decision.input["status"]
        mapped_status = _VERIFICATION_STATUS_MAP.get(loop_status, loop_status)
        notes = decision.input.get("notes")
        if loop_status in _VERIFICATION_STATUS_MAP:
            remap_note = (
                f"design-loop status was {loop_status!r}, "
                f"recorded here as {mapped_status!r} (see orchestration/tooling.py's "
                "_VERIFICATION_STATUS_MAP)"
            )
            notes = f"{notes} -- {remap_note}" if notes else remap_note
        return _FlushTarget(
            designs_db.verify_requirement,
            {
                "design_id": design_id,
                "requirement_id": decision.input["requirement_id"],
                "method": decision.input["method"],
                "status": mapped_status,
                "expected": decision.input.get("expected"),
                "actual": decision.input.get("actual"),
                "notes": notes,
            },
        )
    if decision.kind in _ENGINEERING_RESULT_KINDS:
        return _FlushTarget(
            designs_db.record_engineering_result,
            {
                "design_id": design_id,
                "tool_name": _STEP_TO_TOOL_NAME[decision.step],
                "value": decision.result,
                "provenance": decision.provenance,
            },
        )
    if decision.kind == "requirements":
        return None
    raise DesignLoopPersistenceError(
        f"no flush target known for LoopDecision.kind={decision.kind!r} "
        f"(step={decision.step!r}) -- this indicates design_loop.py added a "
        "new decision kind that orchestration/tooling.py's flush mapping "
        "was never updated for"
    )


def _flush_decisions(
    design_id: int,
    design_key: str,
    loop_id: str,
    iteration: int,
    decisions: list[LoopDecision],
    final_status: DesignStatus,
) -> None:
    """Write every decision in `decisions` (docs/adr/0011: everything
    recorded since the last flush) plus the `designs.status` transition,
    all on ONE connection/transaction -- commits once, or none of it
    lands. Raises `DesignLoopPersistenceError` for a REFUSED write (a
    designs.db call rejecting the write outright -- a record_key
    collision, an unknown requirement_id, ...); any other failure (a real
    database error) is rolled back and re-raised with its own original
    type, matching designs/service.py's own convention ("a write that
    fails for any other reason still raises") rather than relabeling it.
    Both cases share one property: `advance_design_loop_step` never
    returns a state that claims the transition succeeded.
    """
    targets = [
        target
        for decision in decisions
        if (target := _flush_target_for(decision, design_id, design_key, loop_id, iteration))
        is not None
    ]

    conn = designs_db.get_connection()
    try:
        try:
            for target in targets:
                target.call(conn, **target.kwargs)
            designs_db.update_design_status(conn, design_id=design_id, status=final_status.value)
        except (
            designs_db.RecordKeyCollisionError,
            designs_db.UnknownVerificationItemError,
            designs_db.UnknownDesignError,
            InvalidVerificationStatusError,
            InvalidRequirementsError,
            ValueError,
        ) as exc:
            conn.rollback()
            raise DesignLoopPersistenceError(
                f"design-loop flush for design_id={design_id}, loop_id={loop_id!r}, "
                f"iteration={iteration} refused: {exc}"
            ) from exc
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def start_new_design_loop(
    design_key: str,
    name: str,
    revision: str,
    requirements: dict[str, Any],
) -> dict[str, Any]:
    """Start a new design-iteration loop backed by a real `designs` row
    (docs/adr/0011). `requirements` must already be in
    `designs.service.create_design`'s shape -- see this module's
    docstring's "REQUIREMENTS SHAPE" section. Creates the `designs` row
    (in `DRAFT` status, with its auto-created `verification_items` rows)
    via `designs.service.create_design` before starting the pure loop
    state machine; a rejected creation (bad `requirements` shape) raises
    `DesignLoopPersistenceError` naming the problem, and no loop is
    started. Returns the new loop's state dict, positioned at the
    ARCHITECTURE step, extended with `design_id` and
    `persisted_decision_count` (0) -- hold onto this dict and pass it
    back into advance_design_loop_step for every subsequent call."""
    created = designs_service.create_design(
        design_key=design_key,
        name=name,
        revision=revision,
        requirements=requirements,
        architecture={},
    )
    if created["status"] != "created":
        raise DesignLoopPersistenceError(
            f"could not create the design backing this loop: {created}"
        )

    state_dict = start_design_loop(requirements).to_dict()
    state_dict["design_id"] = created["design_id"]
    state_dict["design_key"] = design_key
    state_dict["persisted_decision_count"] = 0
    return state_dict


def advance_design_loop_step(
    state: dict[str, Any],
    step_input: dict[str, Any],
    approval: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Advance a design-iteration loop from its current step to the next
    one. `state` is a prior call's returned state dict (from
    start_new_design_loop or a prior advance_design_loop_step call).
    `step_input` is step-specific -- see orchestration/design_loop.py's
    per-step handlers (_handle_architecture/_handle_analysis/etc.) for
    exactly what each step's current_step expects.

    `approval` is REQUIRED whenever the loop's current step is one of
    ARCHITECTURE, MEASUREMENT, or REDESIGN_DECISION (see design_loop.py's
    GATED_STEPS) -- a LoopStepApprovalReceipt.to_dict()-shaped dict from a
    prior, separate call to orchestration.approval.
    request_loop_step_approval() for THIS EXACT loop/iteration/step/
    step_input combination. Without a valid one, this raises
    OrchestrationError and the loop does not advance -- there is no way to
    skip a gated step from this tool surface.

    A `REDESIGN_DECISION` transition (docs/adr/0011) additionally flushes
    every decision recorded since the last flush to the database and
    moves `designs.status` -- see this module's docstring's "PERSISTENCE"
    section. If that flush fails, this call raises
    `DesignLoopPersistenceError` and returns nothing: `state` (which the
    caller still holds) remains the only valid state, exactly as if the
    step had never advanced.

    Returns the loop's new state dict. Query its "pending_approval" key
    (also present on the state returned by inspect_design_loop_state) to
    see, at any point, whether the loop is currently blocked on an
    approval and which step it's blocked at."""
    if "design_id" not in state:
        raise DesignLoopPersistenceError(
            "state has no 'design_id' -- it must come from start_new_design_loop "
            "(or a prior advance_design_loop_step call), not "
            "orchestration.design_loop.start_design_loop directly"
        )
    design_id = state["design_id"]
    design_key = state["design_key"]
    persisted_count = state.get("persisted_decision_count", 0)

    loop_state = DesignLoopState.from_dict(state)
    current_step_before = loop_state.current_step
    iteration_before = loop_state.iteration

    new_loop_state = advance_loop_step(loop_state, step_input=step_input, approval=approval)

    next_action = step_input.get("next_action") if step_input else None
    if current_step_before == DesignStep.REDESIGN_DECISION.value and next_action in (
        "iterate",
        "accept_design",
    ):
        final_status = DesignStatus.ANALYSIS if next_action == "iterate" else DesignStatus.PASS
        _flush_decisions(
            design_id=design_id,
            design_key=design_key,
            loop_id=new_loop_state.loop_id,
            iteration=iteration_before,
            decisions=new_loop_state.decisions[persisted_count:],
            final_status=final_status,
        )
        persisted_count = len(new_loop_state.decisions)

    result = new_loop_state.to_dict()
    result["design_id"] = design_id
    result["design_key"] = design_key
    result["persisted_decision_count"] = persisted_count
    return result


def inspect_design_loop_state(state: dict[str, Any]) -> dict[str, Any]:
    """Return a design-iteration loop's current state -- current step,
    every decision recorded so far with its own provenance, and whether an
    approval is currently pending (and for which step) -- from a state dict
    returned by start_new_design_loop or advance_design_loop_step. Safe to
    call at any point mid-loop, not just at completion; does not mutate or
    advance the loop, and does not touch the database (`design_id`/
    `design_key`/`persisted_decision_count` are passed through unchanged,
    read-only)."""
    result = DesignLoopState.from_dict(state).to_dict()
    result["design_id"] = state.get("design_id")
    result["design_key"] = state.get("design_key")
    result["persisted_decision_count"] = state.get("persisted_decision_count", 0)
    return result
