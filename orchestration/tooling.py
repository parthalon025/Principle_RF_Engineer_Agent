"""The design-iteration loop's agent/MCP tool surface (issue #46) -- three
focused, JSON-in/JSON-out functions, per this ticket's own scope guidance
("a reasonable, narrow agent/MCP tool surface is: a tool to start a new
loop, a tool to advance to the next step, and a tool to inspect current
state -- three focused tools, not one that tries to do everything"). See
agent/main.py's start_design_loop/advance_design_loop_step/
inspect_design_loop_state tools (principal role) and
mcp_server/server.py's mirrors of the same.

Each function here takes/returns plain dicts (DesignLoopState.to_dict()
shape) so the loop's state crosses the agent/MCP JSON tool boundary and
back unchanged -- the caller (an agent conversation, or any other MCP
client) holds it and passes it back in on the next call, per
design_loop.py's "STATE DESIGN" note.

Deliberately NOT exposed here (or anywhere in this project's agent/MCP tool
wiring): a fourth "request loop-step approval" tool. orchestration.
approval.request_loop_step_approval always raises without a real
approval_callback (see that module's docstring), and a Python callable
cannot cross this JSON boundary -- so exposing it as a tool would provide
no additional capability today, exactly as measurement/base.py's own
request_physical_measurement_approval is not itself a tool (only its
per-instrument wrappers are). It remains directly callable in Python by any
future human-approval workflow.
"""

from typing import Any

from .design_loop import DesignLoopState, advance_loop_step, start_design_loop


def start_new_design_loop(requirements: dict[str, Any]) -> dict[str, Any]:
    """Start a new design-iteration loop from a customer requirement dict
    (frequency band, gain/VSWR/bandwidth target, form factor, host-surface
    curvature, platform -- CONTEXT.md's "Customer requirement"). Returns
    the new loop's state (DesignLoopState.to_dict()), positioned at the
    ARCHITECTURE step -- hold onto this dict and pass it back into
    advance_design_loop_step for every subsequent call."""
    return start_design_loop(requirements).to_dict()


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

    Returns the loop's new state dict. Query its "pending_approval" key
    (also present on the state returned by inspect_design_loop_state) to
    see, at any point, whether the loop is currently blocked on an
    approval and which step it's blocked at."""
    new_state = advance_loop_step(
        DesignLoopState.from_dict(state), step_input=step_input, approval=approval
    )
    return new_state.to_dict()


def inspect_design_loop_state(state: dict[str, Any]) -> dict[str, Any]:
    """Return a design-iteration loop's current state -- current step,
    every decision recorded so far with its own provenance, and whether an
    approval is currently pending (and for which step) -- from a state dict
    returned by start_new_design_loop or advance_design_loop_step. Safe to
    call at any point mid-loop, not just at completion; does not mutate or
    advance the loop."""
    return DesignLoopState.from_dict(state).to_dict()
