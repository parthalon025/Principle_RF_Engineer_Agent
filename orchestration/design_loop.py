"""Controlled autonomous design-iteration loop (issue #46, Phase 12 -- the
final ticket of the 23-ticket build-out, issue #23/docs/BUILD_PLAN.md).

Walks requirements -> architecture -> analysis -> simulation ->
optimization -> verification -> measurement -> correlation -> redesign
(docs/BUILD_PLAN.md's Phase 12 text), tying together the capabilities built
in Phases 1-11 by CALLING INTO the real functions those tickets already
built and tested -- not reimplementing any of them:

  - ANALYSIS    runs the model the design family DECLARES -- its
                `analysis_model` in designs/design_families.py (issue #239),
                not its name. ABSORBER declares ABSORBER_BAND_RESPONSE and
                calls rf_tools.absorber.absorber_band_response -- the
                Costa/Luukkonen equivalent-circuit stack adopted at #111 --
                scored on the single worst-absorbing frequency in the
                required band (#110's minimax rule). PATCH declares
                PATCH_RESONANT_FREQUENCY and calls
                rf_tools.calculations.patch_resonant_frequency_hz (Phase 1).
                Both return exactly what they returned before. A family that
                declares no model is a reported failure here, never a
                fall-through: #191 dispatched by comparing the family name
                against the string "ABSORBER", so every other family --
                including ABSORBER_TRANSMISSIVE, a surface with no ground
                plane behind it -- silently received a patch antenna's
                resonant transmit frequency, which is not a wrong number so
                much as a number about a different device.
                ONE named calculation per family, not an arbitrary callable
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
  - SIMULATION  dispatches on the design family's declared
                `simulation_adapter` (issue #229; ADR-0018 declared the
                field, nothing read it). There is no default any more
                (issue #241): a family with no settled adapter raises,
                naming itself and what is missing, instead of falling back
                to NEC2 -- a thin-wire code that cannot express a periodic
                surface at all, so the fallback was a wrong answer waiting
                to be produced confidently. PATCH declares NEC2 by name:
                simulation.nec2pp.run_nec2_simulation
                (Phase 6), then (issue #101) derives VSWR/return loss from
                that call's own feed-point impedance against an explicit
                reference_impedance_ohms -- see _simulate_nec2's own
                docstring. ABSORBER declares MEEP_FLOQUET, because NEC2 is
                a thin-wire method-of-moments code with no periodic
                boundary of any kind: a metamaterial unit cell is not a
                hard case for it but an inexpressible one. That path is
                honest about simulation/meep.py's own three gaps rather
                than returning a number the adapter cannot stand behind --
                see _simulate_meep_floquet. It also chooses HOW to turn
                that run into an absorption from the family's declared
                `port_count` (issue #243): a ground-backed, one-port
                surface keeps A = 1 - R, because with metal behind it
                anything that did not bounce back had nowhere to go but
                into heat; an unbacked, two-port surface must measure the
                power that passed THROUGH as well and use A = 1 - R - T,
                or it credits the design for every watt that escaped out
                the back. ABSORBER_TRANSMISSIVE declares MEEP_FLOQUET too
                (settled at #243, once #240 gave the adapter a
                transmission monitor), and its run is refused outright if
                that transmittance is missing rather than falling back to
                the one-port sum.
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

from designs.design_families import (
    UndeclaredAnalysisModelError as _UndeclaredAnalysisModelError,
)
from designs.design_families import (
    UnknownDesignFamilyError as _UnknownDesignFamilyError,
)
from designs.design_families import (
    UnsettledSimulationAdapterError as _UnsettledSimulationAdapterError,
)
from designs.design_families import get_design_family as _get_design_family
from measurement.external import record_external_measurement as _record_external_measurement
from optimization.rf_objectives import (
    optimize_patch_length_for_target_frequency as _optimize_patch_length_for_target_frequency,
)
from rf_tools.absorber import absorber_band_response as _absorber_band_response
from rf_tools.calculations import patch_resonant_frequency_hz as _patch_resonant_frequency_hz
from rf_tools.calculations import (
    reflection_coefficient_from_impedance as _reflection_coefficient_from_impedance,
)
from rf_tools.calculations import return_loss_db as _return_loss_db
from rf_tools.calculations import vswr_from_gamma as _vswr_from_gamma
from rf_tools.correlation import (
    correlate_simulation_measurement as _correlate_simulation_measurement,
)
from rf_tools.transmissive_absorber import (
    energy_balance_violations as _energy_balance_violations,
)
from rf_tools.transmissive_absorber import (
    energy_balance_warning as _energy_balance_warning,
)
from rf_tools.transmissive_absorber import (
    one_port_absorption as _one_port_absorption,
)
from rf_tools.transmissive_absorber import (
    refuse_ground_backed_model as _refuse_ground_backed_model,
)
from rf_tools.transmissive_absorber import (
    transmissive_absorber_band_response as _transmissive_absorber_band_response,
)
from rf_tools.transmissive_absorber import (
    two_port_absorption as _two_port_absorption,
)
from simulation.base import SimulatorError as _SimulatorError
from simulation.meep import (
    PERIODIC_ABSORBER_VALIDITY as _MEEP_PERIODIC_ABSORBER_VALIDITY,
)
from simulation.meep import (
    periodic_absorber_capability_gaps as _meep_periodic_absorber_capability_gaps,
)
from simulation.meep import run_meep_simulation as _run_meep_simulation
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
    # cache) both need this as a grouping key.
    #
    # The name is now validated against the Design family registry
    # (`designs/design_families.py`, ADR-0018), which #161 could not do
    # because the registry did not exist. A misspelled or invented family
    # fails HERE, at the step that named it, rather than surviving into
    # `decision_records` as a grouping key nothing else recognises.
    #
    # Validation is deliberately all this step does with the registry. The
    # loop does not evaluate the family's physical bound: that needs inputs
    # (a thickness budget and band for an absorber; a reference half-wave
    # simulation for a patch) that the ARCHITECTURE step does not have and
    # which differ per family by design. The registry entry is echoed into
    # the recorded decision so the ANALYSIS step and any downstream consumer
    # can reach the bound without re-deriving which one applies -- and, for a
    # family whose bound is unread or non-existent, can say WHICH of those
    # two it is rather than seeing an undifferentiated absence.
    _require_fields(step_input, {"decision", "rationale", "design_family"}, "architecture")
    try:
        family = _get_design_family(step_input["design_family"])
    except _UnknownDesignFamilyError as exc:
        raise DesignLoopValidationError(str(exc)) from exc

    recorded = dict(step_input)
    # `design_family` keeps the caller's own string verbatim -- a human wrote
    # it, and a decision record that quietly rewrites what they wrote is worse
    # than one that carries a second field. The canonical registry name goes
    # alongside it instead, so a run recording "patch_antenna" and one
    # recording "PATCH" still group together for #150/#151.
    recorded["design_family_registry"] = {
        "canonical_name": family.name,
        "simulation_tier": str(family.simulation_tier),
        "requires_ground_plane": family.requires_ground_plane,
        "has_physical_bound": family.has_physical_bound,
        "physical_bound": _describe_physical_bound(family),
    }
    return "architecture_decision", recorded, None


def _describe_physical_bound(family: Any) -> dict[str, Any]:
    """Flatten one family's `physical_bound` slot into a JSON-safe record.

    ADR-0018 rejected a fixed schema partly because a bare `None` would be
    "ambiguous between 'not yet computed' and 'doesn't exist for this
    family'". That distinction is worth nothing if it collapses on the way
    into the decision record, so `status` carries it explicitly:
    `available` / `unread_primary_source` / `none_exists`.
    """
    bound = family.physical_bound
    if family.has_physical_bound:
        return {
            "status": "available",
            "name": bound.name,
            "citation": bound.citation,
            "primary_source_doc": bound.primary_source_doc,
            "validity": bound.validity,
        }
    if hasattr(bound, "citation"):
        return {
            "status": "unread_primary_source",
            "name": bound.name,
            "citation": bound.citation,
        }
    return {"status": "none_exists", "reason": bound.reason}


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


def _family_of_record(state: DesignLoopState) -> str | None:
    """The `design_family` the ARCHITECTURE step recorded for this
    iteration, or None if ARCHITECTURE has not run yet. The family is
    validated against the registry at ARCHITECTURE (see _handle_architecture),
    so anything reaching here is a registry name."""
    decision = _find_last_decision(state, DesignStep.ARCHITECTURE)
    if decision is None:
        return None
    return decision.input.get("design_family")


def _registry_family_of_record(state: DesignLoopState, step_name: str) -> Any:
    """The Design family registry entry this iteration's ARCHITECTURE
    decision named, or a raise saying why there isn't one.

    A step that needs to know what KIND of device this is -- which analysis
    to run, which solver can even pose the question -- reads it here, from
    the registry, and never infers it from a name or a default. With no
    ARCHITECTURE decision recorded there is no family, and therefore nothing
    to read: that is a state to report, not to guess past (issues #239,
    #241).
    """
    family_name = _family_of_record(state)
    if family_name is None:
        raise DesignLoopValidationError(
            f"{step_name} cannot proceed: this iteration has recorded no "
            "ARCHITECTURE decision, so no design_family has been named and there "
            "is nothing to read a model or a solver off. Record the ARCHITECTURE "
            "decision (which states design_family) before this step. The loop "
            "never picks a family itself -- CONTEXT.md: selection stays "
            "human-authored."
        )
    try:
        return _get_design_family(family_name)
    except _UnknownDesignFamilyError as exc:
        # Unreachable in a normal loop -- ARCHITECTURE validates the name at
        # the step that stated it -- but a hand-assembled state can reach
        # here, and a named wrong family is still better than a silent one.
        raise DesignLoopValidationError(str(exc)) from exc


def _handle_analysis(
    state: DesignLoopState, step_input: dict[str, Any]
) -> tuple[str, dict[str, Any], str | None]:
    """Run the analysis the design family DECLARES (issue #239).

    Issue #191 first split this step in two, but it chose between the halves
    by comparing the family's NAME against the single string "ABSORBER":
    everything else got the patch-antenna resonant-frequency formula,
    whether or not it was a patch antenna. That is how ABSORBER_TRANSMISSIVE
    (#216) came to be analysed as a transmitting antenna the moment it was
    created -- its name simply is not the word "ABSORBER". In plain terms:
    the loop was reading the label on the box to decide which instrument to
    reach for.

    It now reads `analysis_model` off the registry entry
    (`designs/design_families.py`) and looks that name up in
    `_ANALYSIS_MODELS` below. ABSORBER and PATCH declare exactly the models
    they already ran, so both return identical results to before.

    A family that declares no model raises here rather than borrowing
    another family's. That is deliberate and is NOT the charter's "warn,
    never block" being broken -- that rule governs withholding a candidate
    design from a reader, and nothing is withheld here. What is refused is
    manufacturing a number the programme cannot stand behind: an analysis
    that answers a question about a different device produces a confidently
    wrong number, not an uncertain one, and no warning attached to it would
    tell a reader which it was.
    """
    family = _registry_family_of_record(state, "analysis")
    try:
        model = family.declared_analysis_model()
    except _UndeclaredAnalysisModelError as exc:
        # Re-raised as this loop's own error type, message intact, the same
        # way _handle_architecture re-raises UnknownDesignFamilyError: a
        # caller of advance_loop_step should not have to know the registry's
        # exception vocabulary to learn that a step could not run. The
        # registry error stays attached as __cause__ for anyone who does.
        raise DesignLoopValidationError(str(exc)) from exc
    handler = _ANALYSIS_MODELS.get(model.name)
    if handler is None:
        raise DesignLoopValidationError(
            f"Design family {family.name!r} declares analysis_model "
            f"{model.name!r} ({model.function}), and this loop has no handler "
            "wired for it. Add one to _ANALYSIS_MODELS in "
            "orchestration/design_loop.py, or correct the declaration in "
            "designs/design_families.py -- running a different family's model "
            "instead is the exact defect issue #239 removed."
        )
    return handler(family, step_input)


def _handle_analysis_absorber(
    family: Any,
    step_input: dict[str, Any],
) -> tuple[str, dict[str, Any], str | None]:
    """Worst-in-band absorption for a ground-backed printed absorber.

    Scored on the single worst-absorbing frequency in the required band
    (#110's minimax rule), never the mean or the peak. The result carries
    a `validity` list naming each load-bearing assumption -- notably the
    unrecovered thin-spacer term (#190) -- and never withholds a number
    for one: the loop reports and proceeds.

    Refuses a transmissive stack before computing anything (#242). This
    model's whole legitimacy is that a ground plane guarantees nothing gets
    through, so every watt not reflected became heat; applied to a surface
    with free space behind it, it would credit as absorbed the power that
    simply escaped out the back. The guard is defined beside the two-port
    model it points at, and reads what the family DECLARES -- its
    `requires_ground_plane` and `port_count` -- rather than its name.
    """
    _refuse_ground_backed_model(family)
    _require_fields(
        step_input,
        {
            "f_low_hz",
            "f_high_hz",
            "tan_delta",
            "thickness_m",
            "period_m",
            "gap_m",
            "sheet_resistance_ohm_sq",
            "squares",
        },
        "analysis",
    )
    eps_r_low, eps_r_high, material_property = _resolve_eps_r_bounds(step_input, "analysis")

    def response(eps_r: float) -> dict[str, Any]:
        return _absorber_band_response(
            f_low_hz=step_input["f_low_hz"],
            f_high_hz=step_input["f_high_hz"],
            eps_r=eps_r,
            tan_delta=step_input["tan_delta"],
            thickness_m=step_input["thickness_m"],
            period_m=step_input["period_m"],
            gap_m=step_input["gap_m"],
            sheet_resistance_ohm_sq=step_input["sheet_resistance_ohm_sq"],
            squares=step_input["squares"],
        )

    at_low = response(eps_r_low)
    if eps_r_high == eps_r_low:
        result = dict(at_low)
    else:
        # A bracketed permittivity (ADR-0015's Family fallback bracket)
        # gives a RANGE of worst-case absorption, not one false-precise
        # number -- #127's rule: a guess on a decisive property swings the
        # answer widely, and that swing IS the warning.
        at_high = response(eps_r_high)
        result = dict(at_low)
        result["worst_absorption_low"] = min(
            at_low["worst_absorption"], at_high["worst_absorption"]
        )
        result["worst_absorption_high"] = max(
            at_low["worst_absorption"], at_high["worst_absorption"]
        )
        # Both endpoints' warnings apply; neither is discarded.
        seen = {v["flag"] for v in result["validity"]}
        result["validity"] = list(result["validity"]) + [
            v for v in at_high["validity"] if v["flag"] not in seen
        ]
    if material_property is not None:
        result["material_property"] = material_property
    return "calculation", result, "CALCULATED"


def _handle_analysis_transmissive_absorber(
    family: Any,
    step_input: dict[str, Any],
) -> tuple[str, dict[str, Any], str | None]:
    """Worst-in-band absorption for an UNBACKED, TWO-PORT surface (#242).

    Same minimax rule as the ground-backed handler above -- the single
    worst-absorbing frequency in the band, never the mean and never the peak
    (#110) -- and the same bracketed-permittivity treatment (ADR-0015/#127: a
    guess on a decisive property yields a RANGE, and the swing IS the
    warning).

    What differs is the sum. This family has no metal behind it, so power can
    leave out the back, and absorption is what is left after BOTH the
    reflected and the transmitted share: A = 1 - |S11|^2 - |S21|^2
    (docs/absorber-scoring-conventions.md section 1). The transmitted
    fraction rides along in the result rather than being folded away, because
    for this family it is a different decision: "44 % absorbed" and "44 %
    absorbed, 44 % straight through the part" are not the same answer to
    someone who has to know whether whatever sits behind the surface will
    hear it.

    The family's physical bound rides along as UNREAD rather than absent, and
    the Rozanov bound is never quoted here: its own opening line fixes a slab
    over a perfectly reflecting plane, which this family has not got.
    """
    del family  # the model needs no family fact; the signature is the dispatch's
    _require_fields(
        step_input,
        {
            "f_low_hz",
            "f_high_hz",
            "tan_delta",
            "thickness_m",
            "period_m",
            "gap_m",
            "sheet_resistance_ohm_sq",
            "squares",
        },
        "analysis",
    )
    eps_r_low, eps_r_high, material_property = _resolve_eps_r_bounds(step_input, "analysis")

    def response(eps_r: float) -> dict[str, Any]:
        return _transmissive_absorber_band_response(
            f_low_hz=step_input["f_low_hz"],
            f_high_hz=step_input["f_high_hz"],
            eps_r=eps_r,
            tan_delta=step_input["tan_delta"],
            thickness_m=step_input["thickness_m"],
            period_m=step_input["period_m"],
            gap_m=step_input["gap_m"],
            sheet_resistance_ohm_sq=step_input["sheet_resistance_ohm_sq"],
            squares=step_input["squares"],
        )

    at_low = response(eps_r_low)
    if eps_r_high == eps_r_low:
        result = dict(at_low)
    else:
        at_high = response(eps_r_high)
        result = dict(at_low)
        result["worst_absorption_low"] = min(
            at_low["worst_absorption"], at_high["worst_absorption"]
        )
        result["worst_absorption_high"] = max(
            at_low["worst_absorption"], at_high["worst_absorption"]
        )
        # Both endpoints' warnings apply; neither is discarded.
        seen = {v["flag"] for v in result["validity"]}
        result["validity"] = list(result["validity"]) + [
            v for v in at_high["validity"] if v["flag"] not in seen
        ]
    if material_property is not None:
        result["material_property"] = material_property
    return "calculation", result, "CALCULATED"


def _handle_analysis_patch(
    family: Any,
    step_input: dict[str, Any],
) -> tuple[str, dict[str, Any], str | None]:
    del family  # a patch resonance needs no family fact; the signature is uniform
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


# The dispatch table `_handle_analysis` reads. One named calculation per
# declared model name -- never an arbitrary callable crossing the tool
# boundary, the same reasoning optimization/rf_objectives.py gives for wiring
# one named objective. A family declaring a name that is not a key here is a
# reported failure, not a fallback.
_ANALYSIS_MODELS: dict[str, Any] = {
    "ABSORBER_BAND_RESPONSE": _handle_analysis_absorber,
    "TRANSMISSIVE_ABSORBER_BAND_RESPONSE": _handle_analysis_transmissive_absorber,
    "PATCH_RESONANT_FREQUENCY": _handle_analysis_patch,
}


# There is no default simulation adapter, deliberately (issue #241). The
# `DEFAULT_SIMULATION_ADAPTER = "NEC2"` that used to sit here caught every
# family that declared no solver and sent it to a thin-wire method-of-moments
# code whose entire geometry vocabulary is wires over an optional ground
# plane. A periodic printed surface is not a hard case for NEC2 -- it is one
# you cannot write an input file for. Nothing else in this repo needed the
# constant, so it is gone rather than kept unused: a default nobody chose is
# precisely what #241 removed.


def _simulation_adapter_for(state: DesignLoopState) -> str:
    """The NAME of the solver this iteration's design family declares.

    Read off `simulation_adapter` in the Design family registry
    (`designs/design_families.py`), which holds either a settled
    `SimulationAdapter` or an explicit `UnsettledSimulationAdapter` saying
    the question is open -- never a bare `None`, and never a default. A
    family with no settled adapter, and an iteration that has not recorded an
    ARCHITECTURE decision at all, both raise here naming what is missing.
    """
    return _declared_adapter_name(_registry_family_of_record(state, "simulation"))


def _declared_adapter_name(family: Any) -> str:
    """The solver name a registry entry declares, or a raise saying the
    choice is still open. Split out from `_simulation_adapter_for` so
    `_handle_simulation` can read the family ONCE and pass it on: the
    handlers need the family itself, not only its solver's name -- since
    #243 the absorption arithmetic is selected from the family's declared
    `port_count`."""
    try:
        return family.declared_simulation_adapter().name
    except _UnsettledSimulationAdapterError as exc:
        # Re-raised as this loop's own error type with the registry's message
        # intact, the same way _handle_architecture and _handle_analysis do.
        raise DesignLoopValidationError(str(exc)) from exc


def _handle_simulation(
    state: DesignLoopState, step_input: dict[str, Any]
) -> tuple[str, dict[str, Any], str | None]:
    """Dispatch SIMULATION to the solver this design family declares (#229).

    Before this, every family ran NEC2. NEC2 is a thin-wire method-of-
    moments code: it solves Maxwell's equations honestly, but the only
    geometry it can express is wires in free space over an optional ground.
    It has no periodic boundary, so it cannot represent a metamaterial unit
    cell at all -- and a unit cell is not a hard case for it, it is an
    inexpressible one. In plain terms: it was being asked to model an
    infinite repeating surface using a tool whose entire vocabulary is
    single wires.

    PATCH declares NEC2 by name and ABSORBER declares MEEP_FLOQUET, so both
    route exactly as they did. What changed at #241 is what happens to
    everything else: a family with no settled adapter raises (see
    `_simulation_adapter_for`) instead of quietly becoming a NEC2 run, and a
    family declaring a solver this loop has no handler for is reported by
    name below rather than answered by whichever handler happened to be
    last. Both refusals are deliberate: a solver that cannot represent the
    structure returns a confidently wrong number, not an uncertain one, and
    no caveat attached to it would tell a reader which it was.

    The registry entry itself -- not just its solver's name -- is handed to
    the handler, because since #243 the handler also has to know how many
    ports the family declares before it can turn the run into an absorption.
    """
    family = _registry_family_of_record(state, "simulation")
    adapter = _declared_adapter_name(family)
    handler = _SIMULATION_ADAPTERS.get(adapter)
    if handler is None:
        raise _SimulatorError(
            f"Design family {_family_of_record(state)!r} declares "
            f"simulation_adapter {adapter!r}, and this loop has no handler wired "
            f"for it -- it can drive {sorted(_SIMULATION_ADAPTERS)}. Wire one in "
            "orchestration/design_loop.py's _SIMULATION_ADAPTERS, or correct the "
            "declaration in designs/design_families.py. Running a different "
            "solver instead is the exact defect issue #241 removed."
        )
    return handler(family, step_input)


def _simulate_meep_floquet(
    family: Any,
    step_input: dict[str, Any],
) -> tuple[str, dict[str, Any], str | None]:
    """The Floquet unit-cell path, with the absorption sum chosen by the
    family's declared port count (#243).

    HOW A RUN BECOMES AN ABSORPTION. Meep returns how much power came back
    (reflectance, R) and -- on request -- how much went through
    (transmittance, T). Absorption is what is left:

        one port  (ground-backed, `port_count=1`):  A = 1 - R
        two ports (unbacked,      `port_count=2`):  A = 1 - R - T

    In plain terms: with metal behind the surface, anything that did not
    bounce back had nowhere to go but into heat. With free space behind it,
    some of it simply carried on out the far side, and that share has to be
    taken off. Using the one-port sum on an unbacked surface credits the
    design for power that escaped -- a stack absorbing 0.44 reported as
    1.00, with nothing in the number to say so, which reads as success. See
    docs/absorber-scoring-conventions.md section 1; both sums are the
    field's own, not a house convention.

    WHY THE PORT COUNT IS READ HERE. This is the one place a design family
    and a solver result are both in hand: the registry knows the ports, the
    adapter knows the powers, and neither knows the other. The arithmetic
    itself, and its refusal, live beside the two absorber models in
    rf_tools/transmissive_absorber.py -- a reader who opens either absorber
    module finds the rule; a reader who opens the loop finds the dispatch.

    A TWO-PORT RUN MUST ACTUALLY ASK FOR T, and is refused twice over if it
    cannot have it: once before the solver runs (no transmission monitor in
    the geometry -- the answer is unobtainable however long the run takes,
    and full-wave time is the expensive thing here) and once after (a
    monitor was asked for and the adapter could not measure through it).
    Quietly falling back to A = 1 - R in either case is the precise defect
    #243 exists to remove.

    Both are raises rather than warnings, for the same reason the analysis
    dispatch raises: they would produce a confidently wrong number, not an
    uncertain one, and no caveat attached to it would tell a reader which it
    was. This is not the charter's "warn, never block" being broken -- that
    rule governs withholding a CANDIDATE from a reader, and nothing is
    withheld: ANALYSIS's closed-form absorption is already recorded and
    survives this step's failure, exactly as #111's two-tier design intends.
    The genuinely uncertain case -- R + T summing to more than the power
    that arrived -- is warned about and the candidate is still returned and
    ranked; see `_meep_absorption_for_family` below.
    """
    gaps = _meep_periodic_absorber_capability_gaps()
    if gaps:
        detail = "; ".join(f"{gap['gap']}: {gap['costs']}" for gap in gaps)
        raise _SimulatorError(
            "MEEP_FLOQUET is the right adapter for a periodic absorber cell "
            "and simulation/meep.py cannot yet deliver one. Missing: "
            f"{detail}. ANALYSIS's closed-form absorption still stands as this "
            "candidate's evidence (rf_tools/absorber.py, provenance "
            "CALCULATED); what is unavailable is the full-wave confirmation "
            "that would raise it to SIMULATED. See simulation/meep.py's "
            "periodic_absorber_capability_gaps() for how to close each one."
        )

    _require_fields(step_input, {"geometry", "frequency_hz"}, "simulation")
    geometry = dict(step_input["geometry"])
    # A unit cell is periodic in the plane by definition. The caller may
    # override, but it must not have to remember: forgetting this is the
    # difference between an infinite surface and one lonely element, and it
    # fails silently rather than loudly.
    geometry.setdefault("periodic_axes", ["x", "y"])
    _require_transmission_monitor_for_two_port(family, geometry)

    result = _run_meep_simulation(
        geometry=geometry,
        characteristic_length_m=step_input.get("characteristic_length_m", 1e-3),
        nfreq=int(step_input.get("nfreq", 1)),
        workdir=step_input.get("workdir"),
    )

    s_parameters = result.get("s_parameters") or {}
    reflectance = s_parameters.get("reflectance") or []
    absorption_reading = _meep_absorption_for_family(family, s_parameters)

    recorded = {
        "function": "run_meep_simulation",
        "simulator": result.get("simulator"),
        "status": result.get("status"),
        "frequency_hz": s_parameters.get("frequency_hz"),
        "reflectance": reflectance,
        "absorption": absorption_reading["absorption"],
        "worst_absorption": (
            min(absorption_reading["absorption"]) if absorption_reading["absorption"] else None
        ),
        # What the arithmetic assumed, said out loud rather than inferred
        # from the family's name by whoever reads the result later.
        "port_count": absorption_reading["port_count"],
        "absorption_formula": absorption_reading["absorption_formula"],
        # The transmitted share, and separately the adapter's own three-state
        # account of whether it was even looked for (#240): "not asked",
        # "asked and could not be measured" and "measured, possibly zero" are
        # three different facts, and collapsing them is how a measured zero
        # becomes indistinguishable from silence.
        "transmittance": absorption_reading["transmittance"],
        "transmittance_measurement": absorption_reading["transmittance_measurement"],
        "energy_balance_violations": absorption_reading["energy_balance_violations"],
        "periodic_axes": geometry["periodic_axes"],
        "validity": [dict(entry) for entry in _MEEP_PERIODIC_ABSORBER_VALIDITY]
        + absorption_reading["validity"],
        "provenance": result.get("provenance", "SIMULATED"),
    }
    return "simulation", recorded, recorded["provenance"]


def _require_transmission_monitor_for_two_port(family: Any, geometry: dict[str, Any]) -> None:
    """A two-port family's run must carry a transmission monitor, checked
    BEFORE the solver starts.

    The loop cannot supply the plane itself: where it goes depends on which
    side the source is on and where the absorbing boundary ends, and only
    whoever laid the cell out knows that. Guessing a plane would be worse
    than asking -- a monitor in the wrong place returns a number that looks
    like a measurement.

    Checked up front because the alternative is spending a full-wave run to
    discover something already knowable from the step_input, and because the
    message can then say exactly which key to add.
    """
    if int(getattr(family, "port_count", 1)) == 1:
        # One port: nothing gets through by construction, so asking for the
        # monitor would only buy solver time to confirm a structural zero.
        return
    if geometry.get("transmission_monitor_center_m") is not None:
        return
    raise DesignLoopValidationError(
        f"Design family {getattr(family, 'name', family)!r} declares "
        f"port_count={getattr(family, 'port_count', None)}, so its absorption is "
        "A = 1 - R - T and the run must measure how much power passes THROUGH "
        "the surface. This simulation step_input's geometry has no "
        "'transmission_monitor_center_m', so there is nothing to measure it "
        "with. Add that key -- a plane on the far side of the structure from "
        "the source, inside the cell and clear of the PML (see "
        "simulation/meep.py's run_meep_simulation geometry contract). This is "
        "refused before the solver runs rather than after, because no length "
        "of run can produce a quantity nothing was set up to record, and "
        "falling back to A = 1 - R would credit this candidate for every watt "
        "that escaped out the back -- the exact defect issue #243 removes."
    )


def _meep_absorption_for_family(family: Any, s_parameters: dict[str, Any]) -> dict[str, Any]:
    """Turn one Meep run's powers into an absorption, by the family's ports.

    Returns the absorption spectrum together with everything a reader needs
    to check it: which sum was used, the transmitted share (or None where
    the family has no such quantity), the adapter's own three-state
    transmittance entry verbatim, any frequency where the powers do not add
    up, and the warning that goes with those.
    """
    reflectance = s_parameters.get("reflectance") or []
    measurement = s_parameters.get("transmittance")
    ports = int(getattr(family, "port_count", 1))

    if ports == 1:
        # Ground-backed, so nothing is transmitted and every watt not
        # reflected was dissipated. That guarantee is the ONLY reason
        # A = 1 - R is legitimate, and one_port_absorption re-checks it
        # against the family rather than trusting this branch.
        return {
            "absorption": _one_port_absorption(family, reflectance),
            "port_count": ports,
            "absorption_formula": "A = 1 - R",
            "transmittance": None,
            "transmittance_measurement": measurement,
            "energy_balance_violations": [],
            "validity": [],
        }

    transmittance = _two_port_transmittance(family, measurement)
    frequency_hz = s_parameters.get("frequency_hz") or []
    violations = _energy_balance_violations(reflectance, transmittance, frequency_hz)
    return {
        "absorption": _two_port_absorption(family, reflectance, transmittance),
        "port_count": ports,
        "absorption_formula": "A = 1 - R - T",
        "transmittance": transmittance,
        "transmittance_measurement": measurement,
        "energy_balance_violations": violations,
        # More power leaving than arrived is impossible for a passive
        # surface, so it is a violated assumption surfacing -- uncertain,
        # not confidently wrong. The charter's "warn, never block" governs
        # exactly this: the candidate is returned and ranked with the
        # warning attached, never withheld to protect the reader from it.
        "validity": [_energy_balance_warning(violations)] if violations else [],
    }


def _two_port_transmittance(family: Any, measurement: Any) -> list[float]:
    """The measured transmitted-power spectrum, or a raise saying why there
    is none.

    `measurement` is simulation/meep.py's `s_parameters["transmittance"]`
    entry (#240), which always says which of three things happened: nobody
    asked, somebody asked and it could not be computed, or it was measured
    (possibly as zero). Only the third can be used here, and a measured zero
    is a real result -- it means this surface genuinely passes nothing at
    these frequencies, which is different from never having looked.
    """
    if isinstance(measurement, dict) and measurement.get("computed"):
        return [float(t) for t in measurement.get("transmittance") or []]
    name = getattr(family, "name", repr(family))
    if measurement is None:
        detail = (
            "the solver returned no 'transmittance' entry at all, so this "
            "adapter predates issue #240 or was bypassed"
        )
    elif not measurement.get("requested"):
        detail = (
            "the solver reports no transmittance because no transmission "
            "monitor was requested, even though this step asked for one -- the "
            "monitor plane did not reach the adapter"
        )
    else:
        detail = (
            "a transmission monitor was requested and the solver could not "
            f"compute a transmittance from it: {measurement.get('note', 'no reason given')}"
        )
    raise _SimulatorError(
        f"Design family {name!r} is two-port, so its absorption is "
        f"A = 1 - R - T, and T is missing: {detail}. No absorption is recorded "
        "for this run. Computing A = 1 - R instead would silently book every "
        "watt that passed through the surface as heat -- reporting 0.80 where "
        "the truth may be 0.50 -- and a too-high absorption reads as success, "
        "which is why this is refused rather than warned about (issue #243). "
        "ANALYSIS's closed-form two-port absorption "
        "(rf_tools/transmissive_absorber.py, provenance CALCULATED) still "
        "stands as this candidate's evidence."
    )


def _simulate_nec2(
    family: Any,
    step_input: dict[str, Any],
) -> tuple[str, dict[str, Any], str | None]:
    """Runs run_nec2_simulation, then (issue #101) derives VSWR and return
    loss from the feed-point impedance that call already returns, against
    an explicit `reference_impedance_ohms` step_input MUST state -- never
    silently assumed to be 50 ohms (CONTEXT.md's provenance discipline:
    every recorded number's inputs are stated, not guessed). This is
    deterministic arithmetic over SIMULATION's own already-computed
    impedance, not a second solver run -- no new evidence is manufactured,
    only a different reading of the same evidence, so the result still
    carries run_nec2_simulation's own SIMULATED provenance, not a fresh
    CALCULATED one.

    NEC2++'s adapter only ever solves at ONE frequency (the frequency_hz
    this step_input states) -- so the derived vswr/return_loss_db is
    inherently a single-frequency point prediction, honestly recorded as
    `single_frequency_prediction=True`: a requirement typically stated as
    a band (e.g. "VSWR <= 2.0 across 8-12 GHz") is not fully evaluated by
    one point. orchestration/lab_test_plan.py surfaces this flag alongside
    the traced expected value rather than silently presenting one
    frequency's answer as if it covered the whole band.

    vswr_from_gamma/return_loss_db are each undefined at one of the two
    physical extremes (|Gamma| == 0: perfect match, return loss is
    infinite; |Gamma| == 1: total mismatch, VSWR is infinite) -- each is
    caught independently so the whole step doesn't fail just because the
    OTHER quantity happens to be finite; a genuinely undefined value is
    recorded as None, never guessed at. impedance itself can also be None
    (run_nec2_simulation's own parser found no ANTENNA INPUT PARAMETERS
    block) -- nothing to derive from, so vswr/return_loss_db/
    reflection_coefficient_magnitude are all None, but the step still
    advances: the underlying simulation itself completed.
    """
    del family  # a wire-antenna run needs no family fact; the signature is the dispatch's
    _require_fields(
        step_input, {"geometry", "frequency_hz", "reference_impedance_ohms"}, "simulation"
    )
    result = _run_nec2_simulation(
        geometry=step_input["geometry"],
        frequency_hz=step_input["frequency_hz"],
        timeout_s=step_input.get("timeout_s", 600),
        executable=step_input.get("executable"),
        workdir=step_input.get("workdir"),
    )

    reference_impedance_ohms = step_input["reference_impedance_ohms"]
    reflection_coefficient_magnitude: float | None = None
    vswr: float | None = None
    return_loss_db_value: float | None = None
    impedance = result.get("impedance")
    if impedance is not None:
        z_load = complex(impedance["resistance_ohms"], impedance["reactance_ohms"])
        gamma = _reflection_coefficient_from_impedance(z_load, reference_impedance_ohms)
        reflection_coefficient_magnitude = abs(gamma)
        try:
            vswr = _vswr_from_gamma(reflection_coefficient_magnitude)
        except ValueError:
            vswr = None  # |Gamma| == 1: total mismatch, VSWR is undefined (infinite)
        try:
            return_loss_db_value = _return_loss_db(reflection_coefficient_magnitude)
        except ValueError:
            return_loss_db_value = None  # |Gamma| == 0: perfect match, return loss undefined

    result = {
        **result,
        "reference_impedance_ohms": reference_impedance_ohms,
        "reflection_coefficient_magnitude": reflection_coefficient_magnitude,
        "vswr": vswr,
        "return_loss_db": return_loss_db_value,
        "frequency_hz": step_input["frequency_hz"],
        "single_frequency_prediction": True,
    }
    return "simulation", result, result.get("provenance", "SIMULATED")


# The dispatch table `_handle_simulation` reads, keyed by the adapter name a
# family declares. Each handler takes (family, step_input): the family comes
# along because reading a solver's numbers can depend on what KIND of surface
# was simulated -- MEEP_FLOQUET's absorption sum is chosen by the declared
# port count (#243) -- and a handler that needs no family fact says so with a
# `del family` rather than the table carrying two shapes of callable.
# Every solver this loop can actually drive is listed here
# and nothing else runs: an adapter name with no entry is reported by name,
# never quietly served by another solver (issue #241). Palace, for instance,
# is implemented in simulation/palace.py and validated against a real binary
# (#210) but has no entry yet -- so a family declaring it would be told so.
_SIMULATION_ADAPTERS: dict[str, Any] = {
    "NEC2": _simulate_nec2,
    "MEEP_FLOQUET": _simulate_meep_floquet,
}


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
