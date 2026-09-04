"""Controlled autonomous design-iteration loop (issue #46, Phase 12 -- the
final ticket of the 23-ticket build-out, issue #23/docs/BUILD_PLAN.md).

Walks requirements -> architecture -> analysis -> simulation ->
optimization -> verification -> measurement -> correlation -> redesign
(docs/BUILD_PLAN.md's Phase 12 text), tying together the capabilities built
in Phases 1-11 by CALLING INTO the real functions those tickets already
built and tested -- not reimplementing any of them:

  - ANALYSIS    calls rf_tools.calculations.patch_resonant_frequency_hz
                (Phase 1). ONE named calculation, not an arbitrary callable
                crossing the tool boundary -- same reasoning
                optimization/rf_objectives.py's module docstring gives for
                wiring one named objective rather than a generic one. Its
                substrate permittivity input (eps_r) may come from a bare
                number OR from a resolved designs.material_properties.
                resolve_material_property lookup (issue #154, ADR-0015,
                CONTEXT.md: Material-property library) -- see
                _resolve_eps_r_bounds and _handle_analysis below for how a
                Family fallback bracket or a set of disagreeing citations is
                computed at both ends of the range rather than collapsed to
                one number. SIMULATION and OPTIMIZATION are not wired to the
                library by this ticket: SIMULATION's step_input (geometry,
                frequency_hz) never carries a material property at all, and
                OPTIMIZATION's "which of two independently-searched lengths
                is THE recommended one for a two-ended eps_r" is a genuine
                new design question ADR-0015 does not settle -- left for a
                separate ticket rather than decided inline here.
  - SIMULATION  calls simulation.nec2pp.run_nec2_simulation (Phase 6).
  - OPTIMIZATION calls
                optimization.rf_objectives.optimize_patch_length_for_target_
                frequency (Phase 9), the one named optimization use case
                that ticket wired against this same patch-resonant-
                frequency calculation.
  - MEASUREMENT routes to measurement.external.record_external_measurement
                (issue #89, ADR-0012/ADR-0013): a Touchstone file an
                engineer measured on independent equipment and brought
                back -- no live instrument, no VISA resource, and no
                instrument-actuation approval anywhere in this system
                (ticket #90 removed the instrument-control package
                entirely; ADR-0013's "no dual-mode branching is needed"
                is this END state, not an aspiration). This loop's own
                MEASUREMENT gate (see GATED_STEPS below) still applies: a
                SEPARATE, higher-level approval from anything an
                instrument-actuation gate would have checked -- the
                business decision "should this design accept this
                measurement evidence at all", unrelated to how the data
                was physically obtained.
  - CORRELATION calls rf_tools.correlation.correlate_simulation_measurement
                (Phase 11) against the loop's own recorded SIMULATION/
                MEASUREMENT decisions (or an explicit override -- see
                _handle_correlation).
  - ARCHITECTURE, VERIFICATION, and REDESIGN_DECISION are, per this
    ticket's own scope guidance, lighter-weight recorded decisions rather
    than deep tool integrations: ARCHITECTURE and REDESIGN_DECISION are
    human/agent-authored decision records (see _handle_architecture /
    _handle_redesign_decision); VERIFICATION compiles a verification-matrix
    entry (verification/README.md's own field shape: requirement_id /
    requirement / method / expected / actual / status / notes) from
    evidence already recorded earlier in the loop.
  - REQUIREMENTS is the loop's own starting input (see start_design_loop) --
    there is nothing upstream of it to call into.

STATE DESIGN: per this ticket's own guidance, this project has no
long-running server process -- each agent/MCP tool call is a discrete
request -- so `DesignLoopState` is a plain, JSON-serializable dataclass the
CALLER holds and passes back in on each step-advancing call (like a session
token), not server-side persisted state. No new Postgres table was added
for this ticket (unlike ticket #37's knowledge-base tables): a design's own
`designs`/`decision_records` rows already exist in db/schema.sql for a
FUTURE ticket to persist a loop's outcome into, but wiring that persistence
is a separate concern from representing and gating the loop's OWN state
machine, which is this ticket's job.

APPROVAL GATE: see orchestration/approval.py. GATED_STEPS below are exactly
the three transitions this ticket's acceptance criteria name by name --
"architecture decisions, moving to physical measurement (Phase 10), and any
redesign/iteration decision" -- i.e. every step whose result is NOT itself
tagged CALCULATED/SIMULATED provenance by the Phase 1-11 function it calls:
ANALYSIS/SIMULATION are pure calculation/simulation runs (excluded by the
acceptance criteria's own wording); OPTIMIZATION and CORRELATION both
return "CALCULATED" provenance from their own Phase 9/11 functions (a
deterministic search over / comparison of prior calculated values -- this
project's own provenance vocabulary already classifies them as
calculation-shaped, not human decisions); VERIFICATION compiles already-
recorded evidence into a verification-matrix entry rather than exercising
new judgment. REQUIREMENTS is the loop's human-supplied starting input, not
a step the loop "advances past" via advance_loop_step.

NO MANUFACTURING-RELEASE PATH: DesignStep has no RELEASE/MANUFACTURING
member, REDESIGN_DECISION's only two valid `next_action` values are
"iterate" (loop back to ARCHITECTURE for another cycle) and "accept_design"
(mark the loop complete -- a human then takes the accepted design out of
this system entirely for whatever comes next), and no function anywhere in
this module performs, or is one step away from performing, a release/
manufacturing action -- see tests/test_design_loop.py's
test_no_manufacturing_release_path_exists.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, replace
from enum import StrEnum
from typing import Any

from measurement.external import record_external_measurement as _record_external_measurement
from optimization.rf_objectives import (
    optimize_patch_length_for_target_frequency as _optimize_patch_length_for_target_frequency,
)
from rf_tools.calculations import patch_resonant_frequency_hz as _patch_resonant_frequency_hz
from rf_tools.correlation import (
    correlate_simulation_measurement as _correlate_simulation_measurement,
)
from simulation.nec2pp import run_nec2_simulation as _run_nec2_simulation

from .approval import LoopStepApprovalReceipt, OrchestrationError, check_loop_step_approval_gate


class DesignStep(StrEnum):
    """The loop's fixed, small step sequence (docs/BUILD_PLAN.md's Phase
    12 text). Deliberately a closed enum, not an open string -- see this
    module's docstring's "NO MANUFACTURING-RELEASE PATH" section."""

    REQUIREMENTS = "requirements"
    ARCHITECTURE = "architecture"
    ANALYSIS = "analysis"
    SIMULATION = "simulation"
    OPTIMIZATION = "optimization"
    VERIFICATION = "verification"
    MEASUREMENT = "measurement"
    CORRELATION = "correlation"
    REDESIGN_DECISION = "redesign_decision"


STEP_ORDER: tuple[DesignStep, ...] = (
    DesignStep.REQUIREMENTS,
    DesignStep.ARCHITECTURE,
    DesignStep.ANALYSIS,
    DesignStep.SIMULATION,
    DesignStep.OPTIMIZATION,
    DesignStep.VERIFICATION,
    DesignStep.MEASUREMENT,
    DesignStep.CORRELATION,
    DesignStep.REDESIGN_DECISION,
)

# Every non-calculation/non-simulation step -- see this module's docstring's
# "APPROVAL GATE" section for why exactly these three and no others.
GATED_STEPS = frozenset(
    {DesignStep.ARCHITECTURE, DesignStep.MEASUREMENT, DesignStep.REDESIGN_DECISION}
)

# verification/README.md's own status vocabulary.
VERIFICATION_STATUSES = frozenset({"PASS", "CONDITIONAL PASS", "FAIL", "NOT VERIFIED", "BLOCKED"})

# The only two valid outcomes of a REDESIGN_DECISION -- see this module's
# docstring's "NO MANUFACTURING-RELEASE PATH" section. Neither loops out to
# any release/manufacturing action; "accept_design" simply marks the loop
# complete, full stop.
REDESIGN_ACTIONS = frozenset({"iterate", "accept_design"})


class DesignLoopValidationError(ValueError):
    """Raised for malformed step_input -- e.g. a missing required field or
    an invalid `next_action` -- as distinct from OrchestrationError (an
    approval-gate failure). Mirrors rf_tools.correlation.CorrelationError's
    convention of a domain-specific ValueError subclass."""


@dataclass(frozen=True)
class LoopDecision:
    """One recorded step outcome -- the loop's provenance trail. `kind`
    names what KIND of action produced `result` ("requirements",
    "architecture_decision", "calculation", "simulation", "optimization",
    "verification_record", "measurement", "correlation",
    "redesign_decision"); `provenance` carries this project's own
    MEASURED/SIMULATED/CALCULATED/... tag when the underlying Phase 1-11
    function supplied one (None for the two step kinds -- architecture and
    redesign decisions -- that are human/agent-authored records, not
    computed results).

    `iteration` (issue #88 prefactor) is the `DesignLoopState.iteration`
    this decision was recorded UNDER -- i.e. the iteration whose evidence
    this decision IS, not necessarily the iteration the loop is in by the
    time some later reader looks. This matters exactly once per cycle: the
    REDESIGN_DECISION decision with `next_action="iterate"` is what closes
    out an iteration and increments `DesignLoopState.iteration` (see
    advance_loop_step's REDESIGN_DECISION branch), so that decision's own
    `iteration` is tagged with the iteration it closes, not the new one the
    loop moves to immediately afterward -- `advance_loop_step` stamps
    `iteration` from `state.iteration` (the pre-transition value) onto the
    decision it is about to append, before ever computing the post-
    transition state.

    This exists so a later reader (planned: a batched lab-test-plan ticket
    and a candidate-solver ticket, both of which need "every decision this
    iteration recorded so far") can filter `DesignLoopState.decisions` by
    `iteration` directly against this pure state machine's own state --
    without reaching into `orchestration/tooling.py`'s
    `persisted_decision_count`, which answers a DIFFERENT question (how
    much of `decisions` has been flushed to the database as of the last
    REDESIGN_DECISION boundary, docs/adr/0011) and is this module's
    caller's bookkeeping, not this module's own. `persisted_decision_count`
    is NOT replaced or superseded by this field -- the two answer unrelated
    questions and both remain necessary.

    `iteration` is `None` when nobody recorded one -- exactly a
    `DesignLoopState` serialized BEFORE this field existed (issue #88's own
    prefactor shipped with a `.get("iteration", 1)` default instead; issue
    #135 replaced it, once a saved multi-round loop was no longer
    hypothetical). Guessing `1` for a missing value is only ever correct
    for a loop saved during round 1 -- for a loop saved during round 5,
    every decision in it would be mislabeled "round 1", indistinguishable
    from a decision genuinely recorded in round 1. That is the same
    category of mistake as tagging an assumption `MEASURED`: a guess
    written down as though it were a fact, in a codebase whose whole
    discipline is that a recorded value carries an honest account of where
    it came from (CONTEXT.md, Provenance). `None` reads as "nobody recorded
    this," which is exactly what happened, and matches how `provenance`/
    `approved_by` already tolerate absence on this same dataclass.
    `from_dict` fills a missing value with `None` accordingly; a consumer
    that groups or filters `DesignLoopState.decisions` by `iteration` (see
    the paragraph above -- the lab-test-plan and candidate-solver readers
    this field was added for) must treat `None` as its own case, belonging
    in neither round's bucket, rather than folding it into round 1.

    Everything freshly recorded still gets a real `int`: every
    `LoopDecision(...)` call in this module (`start_design_loop`,
    `advance_loop_step`) passes `iteration=state.iteration` explicitly --
    `None` is reachable only through `from_dict` on a pre-#88 dump."""

    step: str
    kind: str
    input: dict[str, Any]
    result: dict[str, Any]
    provenance: str | None
    approved_by: str | None
    recorded_at: float
    iteration: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "step": self.step,
            "kind": self.kind,
            "input": self.input,
            "result": self.result,
            "provenance": self.provenance,
            "approved_by": self.approved_by,
            "recorded_at": self.recorded_at,
            "iteration": self.iteration,
        }

    @staticmethod
    def from_dict(data: dict[str, Any]) -> LoopDecision:
        return LoopDecision(
            step=data["step"],
            kind=data["kind"],
            input=data.get("input", {}),
            result=data.get("result", {}),
            provenance=data.get("provenance"),
            approved_by=data.get("approved_by"),
            recorded_at=data["recorded_at"],
            iteration=data.get("iteration"),
        )


def _pending_approval_for(step: DesignStep, completed: bool) -> dict[str, Any] | None:
    """A description of the approval this loop is currently waiting on,
    derived purely from `current_step` (and `completed`) -- so it is
    queryable at any point mid-loop without the caller having to guess or
    replay history. Not itself a fingerprint (the fingerprint depends on
    the not-yet-submitted decision content too -- see
    _decision_fingerprint_fields) -- this is the human-readable "what's
    blocking progress right now" view the inspect tool surfaces."""
    if completed or step not in GATED_STEPS:
        return None
    return {
        "step": step.value,
        "requires_approval": True,
        "message": (
            f"Advancing past the {step.value.upper()} step requires a valid "
            "LoopStepApprovalReceipt (orchestration.approval."
            "request_loop_step_approval) fingerprinted to this exact "
            "decision's content before advance_loop_step will proceed."
        ),
    }


@dataclass(frozen=True)
class DesignLoopState:
    """The whole design-iteration loop's state: current step, every
    decision recorded so far (with its own provenance), and what approval
    (if any) is currently pending -- JSON-serializable end to end (see
    to_dict/from_dict) so the CALLER holds and passes it back in on each
    call, per this module's docstring's "STATE DESIGN" section."""

    loop_id: str
    iteration: int
    current_step: str
    completed: bool
    requirements: dict[str, Any]
    decisions: list[LoopDecision]
    created_at: float
    updated_at: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "loop_id": self.loop_id,
            "iteration": self.iteration,
            "current_step": self.current_step,
            "completed": self.completed,
            "requirements": self.requirements,
            "decisions": [d.to_dict() for d in self.decisions],
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "pending_approval": _pending_approval_for(
                DesignStep(self.current_step), self.completed
            ),
        }

    @staticmethod
    def from_dict(data: dict[str, Any]) -> DesignLoopState:
        decisions = [LoopDecision.from_dict(d) for d in data.get("decisions", [])]
        return DesignLoopState(
            loop_id=data["loop_id"],
            iteration=data["iteration"],
            current_step=data["current_step"],
            completed=data["completed"],
            requirements=data.get("requirements", {}),
            decisions=decisions,
            created_at=data["created_at"],
            updated_at=data["updated_at"],
        )


def start_design_loop(requirements: dict[str, Any]) -> DesignLoopState:
    """Start a new design-iteration loop from a customer requirement
    (CONTEXT.md's "Customer requirement"). Records it as the REQUIREMENTS
    decision immediately (it is the human-supplied starting input, not a
    step the loop advances past) and positions the loop at ARCHITECTURE,
    ready for the first call to advance_loop_step."""
    if not requirements or not isinstance(requirements, dict):
        raise DesignLoopValidationError(
            "requirements must be a non-empty dict describing the customer "
            "requirement (frequency band, gain/VSWR/bandwidth target, form "
            "factor, host-surface curvature, platform -- CONTEXT.md's "
            "'Customer requirement')."
        )
    now = time.time()
    requirements_decision = LoopDecision(
        step=DesignStep.REQUIREMENTS.value,
        kind="requirements",
        input=dict(requirements),
        result=dict(requirements),
        provenance="ASSUMED",
        approved_by=None,
        recorded_at=now,
        iteration=1,
    )
    return DesignLoopState(
        loop_id=uuid.uuid4().hex,
        iteration=1,
        current_step=DesignStep.ARCHITECTURE.value,
        completed=False,
        requirements=dict(requirements),
        decisions=[requirements_decision],
        created_at=now,
        updated_at=now,
    )


def _next_step(step: DesignStep) -> DesignStep | None:
    idx = STEP_ORDER.index(step)
    if idx + 1 < len(STEP_ORDER):
        return STEP_ORDER[idx + 1]
    return None


def _decision_fingerprint_fields(
    state: DesignLoopState, step: DesignStep, step_input: dict[str, Any]
) -> dict[str, Any]:
    """The exact decision this step's approval must be bound to: which
    loop, which iteration, which step, and the decision content itself --
    so an approval granted for one loop/iteration/step/content combination
    cannot be replayed for a different one."""
    return {
        "loop_id": state.loop_id,
        "iteration": state.iteration,
        "step": step.value,
        "content": step_input,
    }


def _coerce_receipt(approval: Any) -> Any:
    """dict -> LoopStepApprovalReceipt coercion for a receipt that already
    crossed an agent/MCP JSON tool boundary and back."""
    if isinstance(approval, dict):
        return LoopStepApprovalReceipt(**approval)
    return approval


def _require_fields(step_input: dict[str, Any], required: set[str], step_name: str) -> None:
    missing = required - step_input.keys()
    if missing:
        raise DesignLoopValidationError(
            f"{step_name} step_input is missing required field(s): {sorted(missing)}"
        )


def _handle_architecture(
    _state: DesignLoopState, step_input: dict[str, Any]
) -> tuple[str, dict[str, Any], str | None]:
    # `design_family` (issue #161) is a required structured slot recording
    # WHICH design family (absorber, reflection-phase steering surface,
    # patch antenna, ...) this decision targets -- alongside the existing
    # free-form decision/rationale prose, not replacing it. #150 (cross-run
    # simulator-trust ledger) and #151 (DesignHistoryIndex/geometry-result
    # cache) both need this as a grouping key. A bare string is accepted
    # with no enum/registry validation -- docs/adr/0018's design family
    # registry (which family declares which analysis/optimizer/simulation-
    # adapter/physical-bound) is a separate, not-yet-landed ticket; this
    # field only names the family, it doesn't validate the name against one.
    _require_fields(step_input, {"decision", "rationale", "design_family"}, "architecture")
    return "architecture_decision", dict(step_input), None


def _resolve_eps_r_bounds(
    step_input: dict[str, Any], step_name: str
) -> tuple[float, float, dict[str, Any] | None]:
    """Return `(eps_r_low, eps_r_high, material_property)` for one ANALYSIS
    step_input (issue #154; ADR-0015; CONTEXT.md: Material-property
    library). `eps_r` (a bare number, the pre-existing path) and
    `material_property` (a `designs.material_properties.
    resolve_material_property` result the caller already looked up) are
    mutually exclusive ways to supply the same input -- exactly one must be
    given, or this raises `DesignLoopValidationError`. This module never
    calls into `designs.material_properties` itself (the design loop stays
    the DB-free, pure state machine its own module docstring's "STATE
    DESIGN" section describes); the caller resolves the library lookup
    first, the same way an agent proposes a Requirement target before
    `designs.requirement_targets.attach_target` ever sees it.

    `eps_r_low == eps_r_high` for the `eps_r` path (nothing to spread) and
    for a `material_property` whose own `low == high` (one confident entry,
    or several that happen to agree) -- both take the SAME single-value
    codepath through `_handle_analysis` below, so a caller migrating from
    `eps_r` to `material_property` sees identical results once the library
    holds exactly one value. A `material_property` whose `low != high` (a
    Family fallback bracket, or several disagreeing citations -- CONTEXT.md's
    "the spread itself is the signal that this guess matters") makes
    `_handle_analysis` compute the resonant frequency at both ends rather
    than collapsing to one (ADR-0015's Consequences section), instead of
    picking a value.

    A `material_property` with `status="no_data"` (the library has nothing
    to offer -- no per-material entry, no Family fallback bracket) raises
    rather than proceeding with a made-up number, mirroring #127's own
    rejected "silently excluding a candidate with no data" alternative.
    """
    has_eps_r = "eps_r" in step_input
    has_material_property = "material_property" in step_input
    if has_eps_r == has_material_property:
        raise DesignLoopValidationError(
            f"{step_name} step_input must supply exactly one of 'eps_r' (a bare "
            "number) or 'material_property' (a designs.material_properties."
            "resolve_material_property result) -- got eps_r="
            f"{'present' if has_eps_r else 'absent'}, material_property="
            f"{'present' if has_material_property else 'absent'}"
        )
    if has_eps_r:
        eps_r = step_input["eps_r"]
        return eps_r, eps_r, None

    material_property = step_input["material_property"]
    status = material_property.get("status") if isinstance(material_property, dict) else None
    if not isinstance(material_property, dict) or status == "no_data":
        raise DesignLoopValidationError(
            f"{step_name} step_input['material_property'] has no usable eps_r data "
            f"(status={status!r}) -- CONTEXT.md's Material-property library: a "
            "missing entry with no Family fallback bracket is reported, never "
            "silently guessed past (#127)."
        )
    return material_property["low"], material_property["high"], material_property


def _handle_analysis(
    _state: DesignLoopState, step_input: dict[str, Any]
) -> tuple[str, dict[str, Any], str | None]:
    _require_fields(step_input, {"w_m", "h_m", "l_m"}, "analysis")
    eps_r_low, eps_r_high, material_property = _resolve_eps_r_bounds(step_input, "analysis")

    frequency_at_low = _patch_resonant_frequency_hz(
        eps_r_low, step_input["w_m"], step_input["h_m"], step_input["l_m"]
    )
    if eps_r_high == eps_r_low:
        result = {
            "function": "patch_resonant_frequency_hz",
            "resonant_frequency_hz": frequency_at_low,
            "provenance": "CALCULATED",
        }
    else:
        frequency_at_high = _patch_resonant_frequency_hz(
            eps_r_high, step_input["w_m"], step_input["h_m"], step_input["l_m"]
        )
        # Higher eps_r lowers the resonant frequency (f ~ 1/sqrt(eps_r)), so
        # eps_r_low's frequency is the HIGHER of the two -- min/max over the
        # actual results, never assumed from the eps_r ordering.
        result = {
            "function": "patch_resonant_frequency_hz",
            "resonant_frequency_hz_low": min(frequency_at_low, frequency_at_high),
            "resonant_frequency_hz_high": max(frequency_at_low, frequency_at_high),
            "provenance": "CALCULATED",
        }
    if material_property is not None:
        result["material_property"] = material_property
    return "calculation", result, "CALCULATED"


def _handle_simulation(
    _state: DesignLoopState, step_input: dict[str, Any]
) -> tuple[str, dict[str, Any], str | None]:
    _require_fields(step_input, {"geometry", "frequency_hz"}, "simulation")
    result = _run_nec2_simulation(
        geometry=step_input["geometry"],
        frequency_hz=step_input["frequency_hz"],
        timeout_s=step_input.get("timeout_s", 600),
        executable=step_input.get("executable"),
        workdir=step_input.get("workdir"),
    )
    return "simulation", result, result.get("provenance", "SIMULATED")


def _handle_optimization(
    _state: DesignLoopState, step_input: dict[str, Any]
) -> tuple[str, dict[str, Any], str | None]:
    _require_fields(
        step_input,
        {"eps_r", "w_m", "h_m", "target_frequency_hz", "length_lower_m", "length_upper_m"},
        "optimization",
    )
    result = _optimize_patch_length_for_target_frequency(
        eps_r=step_input["eps_r"],
        w_m=step_input["w_m"],
        h_m=step_input["h_m"],
        target_frequency_hz=step_input["target_frequency_hz"],
        length_lower_m=step_input["length_lower_m"],
        length_upper_m=step_input["length_upper_m"],
        method=step_input.get("method", "bayesian"),
        n_evaluations=step_input.get("n_evaluations", 20),
    )
    return "optimization", result, result.get("provenance", "CALCULATED")


def _handle_verification(
    _state: DesignLoopState, step_input: dict[str, Any]
) -> tuple[str, dict[str, Any], str | None]:
    _require_fields(
        step_input, {"requirement_id", "requirement", "method", "status"}, "verification"
    )
    status = step_input["status"]
    if status not in VERIFICATION_STATUSES:
        raise DesignLoopValidationError(
            f"verification step_input['status'] must be one of "
            f"{sorted(VERIFICATION_STATUSES)}, got {status!r}"
        )
    return "verification_record", dict(step_input), None


def _handle_measurement(
    state: DesignLoopState, step_input: dict[str, Any]
) -> tuple[str, dict[str, Any], str | None]:
    """Delegates entirely to measurement.external.record_external_measurement
    (issue #89, ADR-0012/ADR-0013) -- a Touchstone file an engineer measured
    on independent equipment and brought back. No live instrument, no VISA
    resource, no instrument-actuation approval/gate of any kind is involved
    or possible: ticket #90 removed the instrument-control package this
    step used to have a second path through, so external results are now
    the ONLY path, not a fallback alongside one (ADR-0013: "no dual-mode
    branching is needed"). `lab_report`/`notes`, if given, ride along on
    the result untouched -- never parsed for numbers.

    `state` is unused (measurement is stateless with respect to prior
    decisions -- unlike CORRELATION, which reads back the loop's own prior
    SIMULATION/MEASUREMENT decisions). The loop's own MEASUREMENT approval
    gate (GATED_STEPS, checked in advance_loop_step BEFORE this handler
    ever runs) still applies -- the business decision "should this design
    accept this measurement evidence at all", unaffected by how the data
    was physically obtained.
    """
    del state
    _require_fields(step_input, {"touchstone_file"}, "measurement")
    result = _record_external_measurement(
        touchstone_file=step_input["touchstone_file"],
        lab_report=step_input.get("lab_report"),
        notes=step_input.get("notes"),
    )
    return "measurement", result, result.get("provenance", "MEASURED")


def _jsonify_correlation_comparison(comparison: dict[str, Any]) -> dict[str, Any]:
    """compare_touchstone's per-S-parameter shape carries raw complex numpy
    values -- convert to the same JSON-safe string/float convention
    agent/main.py's _jsonify_comparison already established, so a
    correlation decision's `result` stays JSON-serializable for
    DesignLoopState.to_dict(). Duplicated here (not imported from
    agent/main.py) to avoid a reverse dependency from orchestration/ onto
    agent/ -- ~10 lines, not worth a shared-utility module for this
    ticket's scope."""
    jsonified: dict[str, Any] = {}
    for key, value in comparison.items():
        if isinstance(value, dict) and "diff" in value:
            jsonified[key] = {
                "diff": [str(complex(x)) for x in value["diff"]],
                "magnitude_diff_db": [float(x) for x in value["magnitude_diff_db"]],
                "max_magnitude_diff_db": value["max_magnitude_diff_db"],
                "rms_diff": value["rms_diff"],
                "max_abs_diff": value["max_abs_diff"],
            }
        else:
            jsonified[key] = value
    return jsonified


def _find_last_decision(state: DesignLoopState, step: DesignStep) -> LoopDecision | None:
    for decision in reversed(state.decisions):
        if decision.step == step.value:
            return decision
    return None


def _handle_correlation(
    state: DesignLoopState, step_input: dict[str, Any]
) -> tuple[str, dict[str, Any], str | None]:
    if "simulated" in step_input:
        simulated = step_input["simulated"]
    else:
        sim_decision = _find_last_decision(state, DesignStep.SIMULATION)
        simulated = sim_decision.result if sim_decision else None
    if "measured" in step_input:
        measured = step_input["measured"]
    else:
        meas_decision = _find_last_decision(state, DesignStep.MEASUREMENT)
        measured = meas_decision.result if meas_decision else None

    if simulated is None or measured is None:
        raise DesignLoopValidationError(
            "correlation step requires a recorded SIMULATION and MEASUREMENT "
            "decision in this loop's state, or explicit 'simulated'/"
            "'measured' values in step_input (see rf_tools.correlation."
            "correlate_simulation_measurement for the accepted shapes)."
        )

    result = _correlate_simulation_measurement(
        simulated=simulated,
        measured=measured,
        fixture_path=step_input.get("fixture_path"),
        output_fixture_path=step_input.get("output_fixture_path"),
        temperature_tolerance_c=step_input.get("temperature_tolerance_c", 5.0),
    )
    result = {**result, "comparison": _jsonify_correlation_comparison(result["comparison"])}
    return "correlation", result, result.get("provenance", "CALCULATED")


def _handle_redesign_decision(
    _state: DesignLoopState, step_input: dict[str, Any]
) -> tuple[str, dict[str, Any], str | None]:
    _require_fields(step_input, {"decision", "rationale", "next_action"}, "redesign_decision")
    next_action = step_input["next_action"]
    if next_action not in REDESIGN_ACTIONS:
        raise DesignLoopValidationError(
            f"redesign_decision step_input['next_action'] must be one of "
            f"{sorted(REDESIGN_ACTIONS)}, got {next_action!r}. There is no "
            "'release'/'manufacture' action -- this loop never proceeds to "
            "manufacturing release (docs/BUILD_PLAN.md's Phase 12)."
        )
    return "redesign_decision", dict(step_input), None


_STEP_HANDLERS = {
    DesignStep.ARCHITECTURE: _handle_architecture,
    DesignStep.ANALYSIS: _handle_analysis,
    DesignStep.SIMULATION: _handle_simulation,
    DesignStep.OPTIMIZATION: _handle_optimization,
    DesignStep.VERIFICATION: _handle_verification,
    DesignStep.CORRELATION: _handle_correlation,
    DesignStep.REDESIGN_DECISION: _handle_redesign_decision,
}


def advance_loop_step(
    state: DesignLoopState,
    step_input: dict[str, Any],
    approval: LoopStepApprovalReceipt | dict[str, Any] | None = None,
) -> DesignLoopState:
    """Advance the loop from its current step to the next one, per
    STEP_ORDER. Returns a NEW DesignLoopState (never mutates `state`).

    For a step in GATED_STEPS (ARCHITECTURE, MEASUREMENT,
    REDESIGN_DECISION), `approval` MUST be a valid LoopStepApprovalReceipt
    (or an equivalent dict) fingerprinted to THIS exact loop/iteration/step/
    step_input combination (see _decision_fingerprint_fields) -- obtained
    from a prior, separate call to
    orchestration.approval.request_loop_step_approval(). The gate is
    checked BEFORE the step's action runs or any state changes; a missing
    or invalid approval raises OrchestrationError and `state` is left
    completely untouched (the caller's existing `state` reference is still
    valid and still shows the loop parked at the gated step).
    """
    if state.completed:
        raise OrchestrationError(
            "This design loop already reached its terminal state "
            "(REDESIGN_DECISION -> next_action='accept_design'); no further "
            "steps can be advanced. Start a new loop (start_design_loop) for "
            "further design work."
        )

    current_step = DesignStep(state.current_step)
    step_input = dict(step_input or {})
    approved_by: str | None = None

    if current_step in GATED_STEPS:
        fingerprint_fields = _decision_fingerprint_fields(state, current_step, step_input)
        receipt = _coerce_receipt(approval)
        check_loop_step_approval_gate(receipt, fingerprint_fields)
        approved_by = receipt.approved_by

    if current_step is DesignStep.MEASUREMENT:
        kind, result, provenance = _handle_measurement(state, step_input)
    else:
        handler = _STEP_HANDLERS.get(current_step)
        if handler is None:
            raise OrchestrationError(
                f"No handler for design-loop step {current_step.value!r} -- "
                "this indicates the loop's current_step is REQUIREMENTS, "
                "which is only ever set by start_design_loop, never advanced "
                "through advance_loop_step."
            )
        kind, result, provenance = handler(state, step_input)

    now = time.time()
    decision = LoopDecision(
        step=current_step.value,
        kind=kind,
        input=step_input,
        result=result,
        provenance=provenance,
        approved_by=approved_by,
        recorded_at=now,
        # The PRE-transition iteration -- i.e. the iteration this decision
        # is evidence FOR, not whatever iteration the loop moves to right
        # after (only REDESIGN_DECISION's next_action="iterate" branch,
        # below, ever changes state.iteration, and it does so only in the
        # replace() it returns, after this decision is already built). See
        # LoopDecision's own docstring's "iteration" paragraph.
        iteration=state.iteration,
    )
    new_decisions = [*state.decisions, decision]

    if current_step is DesignStep.REDESIGN_DECISION:
        if step_input["next_action"] == "iterate":
            return replace(
                state,
                iteration=state.iteration + 1,
                current_step=DesignStep.ARCHITECTURE.value,
                decisions=new_decisions,
                updated_at=now,
                completed=False,
            )
        return replace(
            state,
            decisions=new_decisions,
            updated_at=now,
            completed=True,
        )

    next_step = _next_step(current_step)
    assert next_step is not None  # REDESIGN_DECISION (the last step) is handled above
    return replace(state, current_step=next_step.value, decisions=new_decisions, updated_at=now)
