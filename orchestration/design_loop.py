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
  - OPTIMIZATION dispatches on the design family's declared `optimizer_class`
                (`designs/design_families.py`; issue #255 ticket 1 -- a pure
                prefactor, the same family-lookup seam ANALYSIS/SIMULATION
                already use). `CONTINUOUS`, or no `optimizer_class` declared
                at all (every family in this tree today), calls
                optimization.rf_objectives.optimize_patch_length_for_target_
                frequency (Phase 9) exactly as before, unchanged.
                `COMBINATORIAL` (REFLECTION_PHASE/DIFFUSIVE's Tier B search,
                CONTEXT.md) has no path wired yet -- that is separate, later
                work, blocked on the not-yet-built Element/Coding-Alphabet
                library (issue #255) -- and raises rather than silently
                running the continuous search against a placement/selection
                problem. See _handle_optimization/_optimizer_class_for.
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

REQUIREMENTS-DOCUMENT GATE (issue #325, docs/adr/0034): ARCHITECTURE carries
ONE MORE precondition beyond the approval receipt every GATED_STEPS member
already requires -- the design's Requirements document (designs/
requirements_document.py, issue #321) must have reached `CONFIRMED` (ADR-0034:
"you don't pick a physical approach before the customer's actual ask is
locked in"). This is checked as part of the SAME `if current_step in
GATED_STEPS:` block in advance_loop_step, immediately after
check_loop_step_approval_gate, scoped to DesignStep.ARCHITECTURE only -- not
a second, independent gate bolted on elsewhere. This module stays DB-free
(see "STATE DESIGN" below): `advance_loop_step`'s `requirements_document_status`
parameter is the caller's own freshest read of `designs.requirements_document.
read_requirements_document`'s `document_status`, supplied exactly like
`approval` already is, never fetched by this module itself. `None` (the
default) covers both "the caller didn't say" and "no Requirements document
exists yet for this design" -- both mean the customer's actual ask is not
locked in, so ARCHITECTURE may not proceed on either.

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
    UnknownDesignFamilyError as _UnknownDesignFamilyError,
)
from designs.design_families import (
    UnsettledSimulationAdapterError as _UnsettledSimulationAdapterError,
)
from designs.design_families import get_design_family as _get_design_family
from designs.element_alphabet import lookup_symbol_entries as _lookup_symbol_entries
from designs.element_alphabet import (
    reduce_response_at_frequency as _reduce_response_at_frequency,
)
from designs.requirement_targets import GroundPlaneStatus as _GroundPlaneStatus
from designs.requirement_targets import (
    InvalidRequirementTargetError as _InvalidRequirementTargetError,
)
from designs.requirement_targets import TargetComparator as _TargetComparator
from designs.requirement_targets import propose_target as _propose_target
from designs.requirements_document import DocumentStatus as _RequirementsDocumentStatus
from measurement.external import record_external_measurement as _record_external_measurement
from optimization.combinatorial import (
    EmptyCandidateShelfError as _EmptyCandidateShelfError,
)
from optimization.combinatorial import SymbolOption as _SymbolOption
from optimization.combinatorial import (
    combinatorial_symbol_placement as _combinatorial_symbol_placement,
)
from optimization.rf_objectives import (
    optimize_patch_length_for_target_frequency as _optimize_patch_length_for_target_frequency,
)
from rf_tools.calculations import (
    curvature_exceeds_validity_box as _curvature_exceeds_validity_box,
)
from rf_tools.correlation import (
    correlate_simulation_measurement as _correlate_simulation_measurement,
)
from rf_tools.network_parameters import (
    reflection_coefficient_from_impedance as _reflection_coefficient_from_impedance,
)
from rf_tools.network_parameters import return_loss_db as _return_loss_db
from rf_tools.network_parameters import vswr_from_gamma as _vswr_from_gamma
from rf_tools.transmissive_absorber import (
    declared_port_count as _declared_port_count,
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
    two_port_absorption as _two_port_absorption,
)
from simulation.base import SimulatorError as _SimulatorError
from simulation.meep import (
    PERIODIC_ABSORBER_VALIDITY as _MEEP_PERIODIC_ABSORBER_VALIDITY,
)
from simulation.meep import GeometryRole as _GeometryRole
from simulation.meep import (
    periodic_absorber_capability_gaps as _meep_periodic_absorber_capability_gaps,
)
from simulation.meep import run_meep_simulation as _run_meep_simulation
from simulation.nec2pp import run_nec2_simulation as _run_nec2_simulation
from simulation.palace import (
    metasurface_capability_gaps as _palace_metasurface_capability_gaps,
)
from simulation.palace import run_palace_simulation as _run_palace_simulation

from .approval import LoopStepApprovalReceipt, OrchestrationError, check_loop_step_approval_gate

# _handle_analysis is wired into _STEP_HANDLERS below; the other four names
# are unused in this module itself but re-exported as orchestration.design_
# loop attributes (issue #511) so a caller that already reached them there
# -- tests/test_design_loop.py's design_loop_module._handle_analysis_absorber
# included -- keeps working unchanged.
from .design_loop_analysis import (
    _ANALYSIS_MODELS,  # noqa: F401
    _handle_analysis,
    _handle_analysis_absorber,  # noqa: F401
    _handle_analysis_patch,  # noqa: F401
    _handle_analysis_transmissive_absorber,  # noqa: F401
)


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


class DesignLoopStateVersionError(ValueError):
    """Raised when a stored DesignLoopState snapshot's version doesn't match
    what the current code expects. This prevents silent data loss when the
    schema changes while a human-approval request is still pending. A ValueError
    subclass (like DesignLoopValidationError), as this is a data deserialization
    error, not an approval-gate failure."""


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


def _require_requirements_document_confirmed(status: str | None) -> None:
    """Raise OrchestrationError naming exactly what's missing unless
    `status` is the design's Requirements document CONFIRMED status
    (issue #325, docs/adr/0034: "ARCHITECTURE gates on the document
    reaching CONFIRMED"). Called by advance_loop_step for ARCHITECTURE
    only, as one more condition inside the SAME `if current_step in
    GATED_STEPS:` block that already checks the approval receipt -- see
    this module's own docstring's "REQUIREMENTS-DOCUMENT GATE" section --
    never a second, independent gate.

    `status` is the caller's own freshest read of `designs.
    requirements_document.read_requirements_document`'s `document_status`
    (this module stays DB-free, per "STATE DESIGN" below, so it never reads
    that row itself). `None` covers both "no Requirements document exists
    yet for this design" and "the caller supplied nothing" -- both mean the
    customer's actual ask has not been locked in, and ARCHITECTURE may not
    proceed on either.
    """
    if status == _RequirementsDocumentStatus.CONFIRMED.value:
        return
    detail = (
        "no Requirements document exists yet for this design"
        if status is None
        else f"its Requirements document is currently {status!r}, not CONFIRMED"
    )
    raise OrchestrationError(
        "Design-loop step advancement refused: the ARCHITECTURE decision may "
        "not run until this design's Requirements document reaches CONFIRMED "
        f"(docs/adr/0034) -- {detail}. Confirm it "
        "(designs.requirements_document.transition_requirements_document) "
        "before retrying this exact ARCHITECTURE decision."
    )


@dataclass(frozen=True)
class DesignLoopState:
    """The whole design-iteration loop's state: current step, every
    decision recorded so far (with its own provenance), and what approval
    (if any) is currently pending -- JSON-serializable end to end (see
    to_dict/from_dict) so the CALLER holds and passes it back in on each
    call, per this module's docstring's "STATE DESIGN" section."""

    CURRENT_STATE_VERSION = 1

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
            "version": self.CURRENT_STATE_VERSION,
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
        # Check version explicitly to provide a clear error if schema changes
        version = data.get("version")
        if version != DesignLoopState.CURRENT_STATE_VERSION:
            raise DesignLoopStateVersionError(
                f"DesignLoopState snapshot has version={version!r}, but this code "
                f"expects version={DesignLoopState.CURRENT_STATE_VERSION}. A schema "
                "change may have occurred while this approval was pending. "
                "Either start a new design loop (orchestration.design_loop."
                "start_design_loop) or use the code version that created this snapshot."
            )
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


# ---------------------------------------------------------------------------
# Considered-and-dropped ledger (ADR-0025; CONTEXT.md's "Considered-and-
# dropped ledger"; issue #322). An ARCHITECTURE or REDESIGN_DECISION
# step_input may carry an optional `considered_and_dropped` list -- per
# entry, the `family` weighed, whether it was `verdict`="kept"/"dropped",
# one free-text `reason`, and a `reason_kind` (ADR-0025's 2026-09-08
# correction): "human-decision" / "capability-verdict" /
# "engineering-judgment". No gate: a step_input carrying no such key at all
# is untouched and the step proceeds exactly as before (ADR-0025's own "No
# gate" -- recording this ledger is never required).
#
# ADR-0025's 2026-09-09 CORRECTION (issue #322 is the implementation
# ticket). Its own 2026-09-08 correction had briefly read `capability-
# verdict` as "the configured fabrication capability cannot build it" --
# which directly contradicted ADR-0021's rule that an unbuildable candidate
# must be REPORTED, never dropped. The fix is not a gate on dropping (this
# module never drops anything; the LLM caller decides what to propose) but
# a gate on the LABEL: `reason_kind="capability-verdict"` may only be
# recorded for a family excluded by its OWN characterised validity box
# (CONTEXT.md's Validity box) for a property the design's REQUIREMENTS
# themselves state -- never a fact about configured shop equipment/ink/
# material, which never appears in `requirements` at all (that gap is
# #324's separate Capability warning, which never excludes a candidate).
# `human-decision`/`engineering-judgment` carry no such extra requirement --
# only `capability-verdict` is narrowed.
#
# Concretely, a capability-verdict entry must additionally name
# `requirement_id` (a real key in `requirements`) and `validity_box_property`
# (a real key stated on THAT requirement) -- so a later run can re-check the
# SAME lookup against the requirement's CURRENT value (see
# `capability_verdict_holds` below, reused by
# `orchestration.tooling.reevaluate_capability_verdicts`) and flip a stale
# exclusion to reconsiderable the moment that property changes, never
# against equipment. `curvature` is the one validity-box property this
# codebase has a published closed-form bound for (docs/
# curvature-effects-on-em-surfaces.md's `S <= 2*theta_max*R`) -- a
# capability-verdict entry naming it must also carry `theta_max_deg` (the
# excluded family/element's own characterised angular-stability limit), and
# the entry is rejected outright if the requirement's stated curvature does
# not actually exceed that bound, so the label cannot be used as a generic
# "we don't like this family" excuse. Any OTHER `validity_box_property` is
# accepted once it is confirmed to be a real, requirement-stated property
# (structural check only -- no other closed-form validity box is published
# in this codebase yet; a documented scope limit, not an oversight, mirroring
# ADR-0025's own numeric-vs-categorical distinction for relaxation reporting).
_LEDGER_VERDICTS = frozenset({"kept", "dropped"})
_LEDGER_REASON_KINDS = frozenset({"human-decision", "capability-verdict", "engineering-judgment"})


def capability_verdict_holds(entry: dict[str, Any], requirements: dict[str, Any]) -> bool:
    """True if a `reason_kind="capability-verdict"` ledger `entry` is still
    justified by `requirements`' CURRENT stated properties -- the exact
    same check `_validate_capability_verdict_entry` enforces at write time,
    reused (never re-derived) by
    `orchestration.tooling.reevaluate_capability_verdicts` so a later run's
    re-evaluation cannot silently drift from the rule that justified writing
    the entry in the first place.

    Returns `False` (never raises) for any reason the exclusion can no
    longer be confirmed against `requirements` as they stand right now: a
    missing/renamed `requirement_id`, a `validity_box_property` no longer
    stated on that requirement, a malformed/missing `curvature` value, or a
    stated curvature that no longer exceeds `S <= 2*theta_max*R` for this
    entry's own `theta_max_deg`. Every one of those is "the property that
    excluded this family changed or vanished" -- exactly ADR-0025's
    "flips to reconsiderable the moment that property changes."
    """
    if not isinstance(requirements, dict):
        return False
    requirement = requirements.get(entry.get("requirement_id"))
    validity_box_property = entry.get("validity_box_property")
    if not isinstance(requirement, dict) or validity_box_property not in requirement:
        return False
    if validity_box_property == "curvature":
        curvature = requirement["curvature"]
        try:
            return _curvature_exceeds_validity_box(
                curvature["arc_length_m"], curvature["host_radius_m"], entry["theta_max_deg"]
            )
        except (KeyError, TypeError, ValueError):
            return False
    # No other validity-box property has a published closed-form check in
    # this codebase (see this section's own module comment) -- structural
    # presence (already confirmed above) is all that can be reconfirmed.
    return True


def _validate_capability_verdict_entry(
    entry: dict[str, Any], requirements: dict[str, Any], prefix: str
) -> None:
    if entry["verdict"] != "dropped":
        raise DesignLoopValidationError(
            f"{prefix} has reason_kind='capability-verdict' but verdict={entry['verdict']!r} "
            "-- a family excluded by its own validity box is, by definition, dropped; "
            "'kept' + 'capability-verdict' is a contradiction (a soft preference for a "
            "kept family belongs under reason_kind='engineering-judgment' instead)"
        )
    missing = {"requirement_id", "validity_box_property"} - entry.keys()
    if missing:
        raise DesignLoopValidationError(
            f"{prefix} has reason_kind='capability-verdict' but is missing required "
            f"field(s) {sorted(missing)} -- a capability-verdict must name which "
            "requirement and which of its own stated properties it was excluded "
            "against (ADR-0021/ADR-0025: never a shop-equipment fact)"
        )
    requirement_id = entry["requirement_id"]
    if requirement_id not in requirements:
        raise DesignLoopValidationError(
            f"{prefix}['requirement_id']={requirement_id!r} is not a key in this "
            "design's requirements -- capability-verdict must trace to a real "
            "customer requirement, never to configured shop equipment/ink/material"
        )
    requirement = requirements[requirement_id]
    validity_box_property = entry["validity_box_property"]
    if not isinstance(requirement, dict) or validity_box_property not in requirement:
        raise DesignLoopValidationError(
            f"{prefix}['validity_box_property']={validity_box_property!r} is not a "
            f"stated property of requirement {requirement_id!r} -- a capability-verdict "
            "may only be recorded against a property the requirement itself states"
        )
    if validity_box_property == "curvature" and "theta_max_deg" not in entry:
        raise DesignLoopValidationError(
            f"{prefix} has validity_box_property='curvature' but is missing "
            "'theta_max_deg' -- the excluded family/element's own characterised "
            "angular-stability limit"
        )
    if not capability_verdict_holds(entry, requirements):
        raise DesignLoopValidationError(
            f"{prefix} claims reason_kind='capability-verdict' for "
            f"validity_box_property={validity_box_property!r}, but the requirement's "
            "own current stated value does not actually violate that validity box -- "
            "capability-verdict may only be recorded for a real violation, never a "
            "generic 'this family is not preferred'"
        )


def _validate_considered_and_dropped(
    entries: Any, requirements: dict[str, Any], step_name: str
) -> None:
    """Validate an optional `considered_and_dropped` ledger on an
    ARCHITECTURE/REDESIGN_DECISION step_input -- see this section's own
    module comment above for the full shape and the issue #322 narrowing.
    `None` (the key absent) is a no-op: recording this ledger is never
    required (ADR-0025's "No gate")."""
    if entries is None:
        return
    if not isinstance(entries, list):
        raise DesignLoopValidationError(
            f"{step_name} step_input['considered_and_dropped'] must be a list, "
            f"got {type(entries).__name__}"
        )
    for index, entry in enumerate(entries):
        prefix = f"{step_name} step_input['considered_and_dropped'][{index}]"
        if not isinstance(entry, dict):
            raise DesignLoopValidationError(f"{prefix} must be a dict, got {type(entry).__name__}")
        missing = {"family", "verdict", "reason", "reason_kind"} - entry.keys()
        if missing:
            raise DesignLoopValidationError(
                f"{prefix} is missing required field(s): {sorted(missing)}"
            )
        for text_field in ("family", "reason"):
            if not isinstance(entry[text_field], str) or not entry[text_field].strip():
                raise DesignLoopValidationError(
                    f"{prefix}[{text_field!r}] must be a non-empty string, "
                    f"got {entry[text_field]!r}"
                )
        if entry["verdict"] not in _LEDGER_VERDICTS:
            raise DesignLoopValidationError(
                f"{prefix}['verdict'] must be one of {sorted(_LEDGER_VERDICTS)}, "
                f"got {entry['verdict']!r}"
            )
        reason_kind = entry["reason_kind"]
        if reason_kind not in _LEDGER_REASON_KINDS:
            raise DesignLoopValidationError(
                f"{prefix}['reason_kind'] must be one of {sorted(_LEDGER_REASON_KINDS)}, "
                f"got {reason_kind!r}"
            )
        if reason_kind == "capability-verdict":
            _validate_capability_verdict_entry(entry, requirements, prefix)


# ---------------------------------------------------------------------------
# Capability warning (issue #324; ADR-0025's 2026-09-09 correction;
# CONTEXT.md's "Capability warning"). A WHOLLY SEPARATE mechanism from the
# considered_and_dropped ledger above -- deliberately its own step_input key
# (`capability_warnings`), its own list, its own reason vocabulary (none:
# there is no verdict, because a Capability warning never drops anything) --
# so that "a capability-verdict entry never gains a Capability warning and
# vice versa" (issue #324 acceptance criterion 3) holds structurally, not
# merely by convention on a shared list.
#
# A design candidate that is a good fit but that the currently configured
# Fabrication capability, Ink-property library selection, or Material-
# property library selection cannot meet stays `kept` -- it is never
# dropped, per the charter's "present equipment... shape the ranking and the
# warnings, never the search" and ADR-0021's rule that an unbuildable
# candidate is reported, never deleted. Instead it carries a
# `capability_warnings` entry naming the `family` it is attached to, which
# of the three capability sources fell short (`capability_kind`: one of
# "fabrication"/"ink"/"material"), which of that source's own properties
# (`capability_property`, e.g. "min_feature_size_mm"), the stated need in
# the SAME `value`/`comparator`/`unit` shape a Requirement target uses (the
# issue's own "so the gap is a precise, actionable spec rather than
# descriptive prose"), and the charter's own three-part warning contract
# (CLAUDE.md's "Warn, never block"; ADR-0028) as three required string
# fields -- `assumed` (what is assumed), `costs` (what it costs if that
# assumption is wrong), and `cheapest_test` (the cheapest way to find out)
# -- issue #515/#496: the same vocabulary already implemented and
# test-pinned by `rf_tools/absorber.py`'s/`rf_tools/transmissive_absorber.py`'s
# `validity` entries, copied verbatim rather than re-derived, in place of
# the single freeform `reason` field this shape used to fold both ideas
# into with nothing enforcing either was actually present.
#
# No closed-form "must actually violate" check gates this at write time,
# unlike capability-verdict's curvature bound -- no such published bound
# exists for shop equipment/ink/material capability in this codebase (see
# CONTEXT.md's Fabrication capability/Ink-property library/Material-
# property library entries), and the charter's own rule is that the
# JUDGMENT is the model's; the code only checks FORM. What IS checked here
# is exactly the same Requirement-target shape check
# `designs.requirement_targets.propose_target` already enforces for a real
# Requirement target -- reused, not re-derived, so "Stated in Requirement
# target shape" cannot silently drift into a looser check here than it
# means everywhere else.
_CAPABILITY_KINDS = frozenset({"fabrication", "ink", "material"})


def capability_warning_holds(
    entry: dict[str, Any], capability_configuration: dict[str, Any]
) -> bool:
    """True if a `capability_warnings` `entry`'s stated gap still holds
    against `capability_configuration` -- the currently configured value for
    `entry["capability_kind"]`/`entry["capability_property"]`
    (e.g. `{"fabrication": {"min_feature_size_mm": 0.5}}`) -- issue #324
    acceptance criterion 2: "re-evaluated every run against the current
    manufacturing configuration and clears automatically when the
    configuration improves enough."

    Returns `True` (the warning still applies) whenever the current value
    cannot be confirmed to meet the entry's own stated need: a missing
    `capability_kind`/`capability_property` in `capability_configuration`, or
    a non-numeric current value. This is the OPPOSITE fail-safe direction
    from `capability_verdict_holds` above, deliberately: there, missing data
    means "no longer confirmed, stop excluding" (silently keeping an
    unjustified exclusion is the dangerous failure); here, missing data
    means "not yet confirmed resolved, keep warning" (silently clearing a
    warning -- a candidate that still cannot be built looking clean -- is
    the dangerous failure instead). Never raises.
    """
    if not isinstance(capability_configuration, dict):
        return True
    kind_config = capability_configuration.get(entry.get("capability_kind"))
    if not isinstance(kind_config, dict):
        return True
    current_value = kind_config.get(entry.get("capability_property"))
    if isinstance(current_value, bool) or not isinstance(current_value, (int, float)):
        return True
    try:
        comparator = _TargetComparator(entry["comparator"])
    except (KeyError, ValueError):
        return True
    needed_value = entry["value"]
    if comparator is _TargetComparator.AT_MOST:
        meets_need = current_value <= needed_value
    elif comparator is _TargetComparator.AT_LEAST:
        meets_need = current_value >= needed_value
    else:
        meets_need = current_value == needed_value
    return not meets_need


def _validate_capability_warnings(entries: Any, step_name: str) -> None:
    """Validate an optional `capability_warnings` list on an
    ARCHITECTURE/REDESIGN_DECISION step_input -- see this section's own
    module comment above for the full shape. `None` (the key absent) is a
    no-op, same "No gate" as `_validate_considered_and_dropped` -- attaching
    a Capability warning is never required.

    Issue #515/#496: `assumed`/`costs`/`cheapest_test` are each required,
    non-empty string fields -- the charter's own three-part warning
    contract (what is assumed / what it costs if that assumption is wrong /
    the cheapest way to find out) enforced structurally instead of folded,
    optionally, into one freeform `reason` string. Same field names as
    `rf_tools/absorber.py`'s/`rf_tools/transmissive_absorber.py`'s existing
    `validity` entries -- copied verbatim, not a new vocabulary.
    `family`/`capability_kind`/`capability_property`/`value`/`comparator`/
    `unit` are unchanged: they identify WHAT the gap is about, not the
    three-part warning contract itself.
    """
    if entries is None:
        return
    if not isinstance(entries, list):
        raise DesignLoopValidationError(
            f"{step_name} step_input['capability_warnings'] must be a list, "
            f"got {type(entries).__name__}"
        )
    required = {
        "family",
        "capability_kind",
        "capability_property",
        "value",
        "comparator",
        "unit",
        "assumed",
        "costs",
        "cheapest_test",
    }
    for index, entry in enumerate(entries):
        prefix = f"{step_name} step_input['capability_warnings'][{index}]"
        if not isinstance(entry, dict):
            raise DesignLoopValidationError(f"{prefix} must be a dict, got {type(entry).__name__}")
        missing = required - entry.keys()
        if missing:
            raise DesignLoopValidationError(
                f"{prefix} is missing required field(s): {sorted(missing)}"
            )
        for text_field in (
            "family",
            "capability_property",
            "assumed",
            "costs",
            "cheapest_test",
        ):
            if not isinstance(entry[text_field], str) or not entry[text_field].strip():
                raise DesignLoopValidationError(
                    f"{prefix}[{text_field!r}] must be a non-empty string, "
                    f"got {entry[text_field]!r}"
                )
        if entry["capability_kind"] not in _CAPABILITY_KINDS:
            raise DesignLoopValidationError(
                f"{prefix}['capability_kind'] must be one of {sorted(_CAPABILITY_KINDS)}, "
                f"got {entry['capability_kind']!r}"
            )
        try:
            _propose_target(
                value=entry["value"], comparator=entry["comparator"], unit=entry["unit"]
            )
        except _InvalidRequirementTargetError as exc:
            raise DesignLoopValidationError(
                f"{prefix} is not a valid Requirement target shape (value/comparator/unit): {exc}"
            ) from exc


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
    _validate_considered_and_dropped(
        step_input.get("considered_and_dropped"), _state.requirements, "architecture"
    )
    _validate_capability_warnings(step_input.get("capability_warnings"), "architecture")

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


# _handle_analysis and its per-model handlers (_handle_analysis_absorber,
# _handle_analysis_transmissive_absorber, _handle_analysis_patch), and the
# _ANALYSIS_MODELS dispatch table they share, moved to
# orchestration/design_loop_analysis.py (issue #511, split out of issue
# #498) -- imported at this module's top, alongside its other imports; see
# that module's own docstring for why its reverse dependency on THIS module
# (_registry_family_of_record, _require_fields, _resolve_eps_r_bounds,
# DesignLoopValidationError) is resolved lazily rather than up front, which
# is what keeps this import safe to sit at the top here rather than needing
# to wait for those names' definitions below. This import also re-exports
# all five names as orchestration.design_loop attributes, so nothing that
# already imported them from here needs to change.


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


def _role_tagged_primitives(geometry: Any) -> list[Any]:
    """Every raw, unvalidated `role` value across `geometry`'s combined
    `materials`+`conductors` lists (issue #486, reading #485's own tag back
    out). Deliberately NOT re-validating each value against `GeometryRole`
    -- that is `simulation/meep.py`'s `_validate_role`'s job, run for real
    when (and only when) a MEEP_FLOQUET candidate actually builds its
    geometry; this function only needs to know whether ANY primitive
    opted into role-tagging at all, and (via the caller) how many claim
    `REFLECTOR`.

    Tolerates `geometry` being `None` or not a dict at all -- returning `[]`
    rather than raising -- because this can run (from `_handle_simulation`)
    before a handler's own `_require_fields` has had a chance to say
    'geometry is missing'; this check must not pre-empt that with a
    different, confusing error of its own. A NEC2-shaped geometry (a
    `{'wires': [...]}` dict) also lands here safely: `.get('materials'/
    'conductors', [])` simply finds nothing, the same as no geometry at
    all -- which is exactly the "PATCH's own wire representation cannot
    carry a role tag in the first place" case this ticket's legacy
    exemption exists for.
    """
    if not isinstance(geometry, dict):
        return []
    primitives = list(geometry.get("materials") or []) + list(geometry.get("conductors") or [])
    return [
        prim.get("role")
        for prim in primitives
        if isinstance(prim, dict) and prim.get("role") is not None
    ]


def _any_requirement_confirms_host_ground_plane(requirements: Any) -> bool:
    """Whether ANY entry in a design's `requirements` carries a CONFIRMED,
    `is_ground_plane=True` `host_ground_plane` assertion (#484).

    THE AMBIGUITY THIS RESOLVES, stated plainly. #481/#486 both describe
    this as consulting "the owning requirement's host ground-plane
    assertion" -- phrasing that presumes one requirement per candidate.
    In fact `requirements` is a dict of every requirement entry recorded
    for the whole design, and whether the host surface is a reliable
    ground plane is a physical fact about that surface, not something
    tied to any one numeric target (a gain requirement and a VSWR
    requirement on the same design share the same host). There is no
    natural "the" requirement_id to demand a match against, and refusing
    a candidate because the confirmation happened to be attached to a
    different requirement entry than some arbitrarily chosen one would be
    checking bookkeeping, not physics. So this deliberately asks "does
    ANY entry confirm it" rather than requiring a specific requirement_id
    -- the same design-wide fact, read off whichever entry happens to
    carry it.

    Tolerates `requirements` being anything other than a dict (returns
    `False`), and tolerates entries that are not themselves dicts or that
    carry no `host_ground_plane` key at all -- `state.requirements` in this
    loop is an open, caller-supplied dict (see `DesignLoopState`'s own
    docstring), not guaranteed to be shaped like `designs.requirement_
    targets`'s own requirement-entry schema.
    """
    if not isinstance(requirements, dict):
        return False
    for entry in requirements.values():
        if not isinstance(entry, dict):
            continue
        host_ground_plane = entry.get("host_ground_plane")
        if not isinstance(host_ground_plane, dict):
            continue
        if (
            host_ground_plane.get("ground_plane_status") == _GroundPlaneStatus.CONFIRMED.value
            and host_ground_plane.get("is_ground_plane") is True
        ):
            return True
    return False


def _require_reflector_or_confirmed_host_ground_plane(
    family: Any, geometry: Any, requirements: Any
) -> None:
    """ADR-0017's rule, finally read against itself (issue #486): a
    candidate whose family needs a ground plane must get one from
    somewhere -- its own bottom printed layer, or the surface it mounts
    on -- and until now nothing checked which. #484 gave a design a place
    to confirm the host is one; #485 gave a geometry primitive a `role` to
    say it IS one (`REFLECTOR`); this is the first thing that reads the
    two against each other.

    CHECKED IN THIS ORDER, and each step here is a deliberate pass, not
    an oversight:

    1. `family.requires_ground_plane` is falsy: exempt outright. A family
       whose physics never depends on a ground plane at all
       (ABSORBER_TRANSMISSIVE's own shape) has nothing here to check.
    2. `geometry` carries no `role` tag anywhere across its combined
       `materials`+`conductors` (`_role_tagged_primitives` above): exempt.
       This is a DELIBERATE decision carried over from the parent spec
       (#481), not a gap -- `role` (#485) is opt-in metadata, and PATCH's
       own NEC2 wire-geometry representation (the other family with
       requires_ground_plane=True) has no materials/conductors list to
       tag in the first place, so it can never satisfy a check phrased in
       terms of that tag. Legacy/pre-#485 MEEP_FLOQUET geometry gets the
       identical pass, for the identical reason: only geometry that opts
       into role-tagging is held to this check.
    3. At least one primitive claims `role=REFLECTOR`
       (`_build_geometry_list` itself caps this at exactly one across a
       geometry's combined materials+conductors): the candidate supplies
       its own reflector, ADR-0017's default. Passes.
    4. Otherwise, passes only if `_any_requirement_confirms_host_ground_
       plane` says this design has a CONFIRMED, is_ground_plane=True
       assertion (#484) -- ADR-0017's named escape hatch: a design may
       skip its own reflector layer and lean on the host instead, but
       only once a human has vouched the host actually is one.

    Raises `DesignLoopValidationError` otherwise, naming the family and
    exactly what to add -- mirroring `_require_transmission_monitor_for_
    two_port`'s own message shape and its own reason for checking here,
    before the solver runs: no length of a Meep run can supply a reflector
    the geometry never described, or a confirmation a human never gave.
    """
    if not getattr(family, "requires_ground_plane", False):
        return

    roles = _role_tagged_primitives(geometry)
    if not roles:
        return

    reflector_count = sum(1 for role in roles if role == _GeometryRole.REFLECTOR)
    if reflector_count >= 1:
        return

    if _any_requirement_confirms_host_ground_plane(requirements):
        return

    raise DesignLoopValidationError(
        f"Design family {getattr(family, 'name', family)!r} declares "
        "requires_ground_plane=True (ADR-0017), so this candidate needs a "
        "reflector from somewhere: its own bottom printed layer, or the "
        "surface it mounts on. This candidate's geometry has role-tagged "
        "layers (issue #485) but none of them is role=REFLECTOR, and no "
        "requirement on this design confirms the host is a reliable ground "
        "plane (issue #484). Add a REFLECTOR-role primitive to this "
        "candidate's geometry (materials or conductors), or confirm the "
        "host assertion via designs.requirement_targets."
        "confirm_requirement_host_ground_plane before retrying -- this is "
        "refused before the solver runs rather than after, because no "
        "length of run can supply a reflector the geometry never described "
        "or a confirmation a human never gave."
    )


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

    WHY THE REFLECTOR-PROVENANCE CHECK (#486) LIVES HERE, NOT INSIDE A
    HANDLER. `_require_reflector_or_confirmed_host_ground_plane` needs both
    `state.requirements` (where a design's `host_ground_plane` assertion,
    #484, actually lives) and this step's own geometry -- and this function
    is the one place both are already in scope, with no per-handler
    signature change needed. `_simulate_meep_floquet`/`_simulate_nec2`/
    `_simulate_palace_floquet` all take `(family, step_input)` only, per
    `_SIMULATION_ADAPTERS`'s own dispatch contract; threading `requirements`
    through that contract for one check, when every handler's `family`
    argument already carries `requires_ground_plane`, would touch three
    handlers to give one of them one more fact. Checking here also means it
    runs for every adapter uniformly, with no adapter-name special-casing:
    NEC2's geometry is `{'wires': [...]}` and PALACE_FLOQUET's is
    `{'unit_cell', 'ground_backed', 'pec_patches', ...}` -- neither carries a
    `materials`/`conductors` list to tag a `role` onto in the first place
    (#485's tag exists only on `simulation/meep.py`'s own geometry shape),
    so `_role_tagged_primitives` finds nothing for either and the legacy
    exemption fires on its own. PATCH (NEC2, requires_ground_plane=True)
    is proof of this: it is never refused by this check, and never needed a
    line of code naming NEC2 to arrange that.
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
    _require_reflector_or_confirmed_host_ground_plane(
        family, step_input.get("geometry"), state.requirements
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
    if _declared_port_count(family) == 1:
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
    ports = _declared_port_count(family)

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


def _simulate_palace_floquet(
    family: Any,
    step_input: dict[str, Any],
) -> tuple[str, dict[str, Any], str | None]:
    """The Palace Floquet unit-cell path for REFLECTION_PHASE/DIFFUSIVE
    (#252 ticket 3), mirroring `_simulate_meep_floquet`'s own shape: check
    the capability gap BEFORE spending any solver time, raise a named
    `SimulatorError` if the candidate's geometry cannot pose the family's
    question, otherwise run the solver and record what it returned.

    `family` is accepted for the same reason every handler in
    `_SIMULATION_ADAPTERS` takes it -- the dispatch table's one shared
    signature -- but this handler needs no fact off it: unlike
    `_simulate_meep_floquet`'s port-count-dependent absorption arithmetic,
    Palace's own S-parameter/conservation-check output already IS the
    answer this family needs (a per-diffraction-order reflectance and
    phase), nothing here derives a second quantity from it.

    WHAT "capability gap" MEANS HERE, AND WHY IT IS CHECKED ON THE GEOMETRY
    RATHER THAN ON THE ADAPTER. Unlike MEEP_FLOQUET's gap check (three
    things the adapter itself cannot yet DO, checked with no arguments),
    both features REFLECTION_PHASE/DIFFUSIVE need -- an embedded PEC
    conductor patch, a ground-backed one-port cell -- are already
    implemented in simulation/palace.py (issue #252 tickets 1/2). What can
    still be wrong is a CANDIDATE's own geometry dict: nothing stops a
    caller from handing this handler the module's OTHER shape (an
    all-dielectric, two-port transmissive grating) by simply omitting
    "ground_backed"/"pec_patches", which would run Palace successfully and
    return a confidently wrong answer -- a bare dielectric grating's
    transmission standing in for a metal-backed metasurface's reflection
    phase. `simulation.palace.metasurface_capability_gaps()` is the probe
    that catches this, per candidate, before any solver time is spent. See
    that function's own docstring for the full reasoning.

    Refusing here is not the charter's "warn, never block" being broken:
    that rule governs withholding a CANDIDATE from a reader, and nothing is
    withheld -- REFLECTION_PHASE/DIFFUSIVE currently declare no closed-form
    ANALYSIS model at all (designs/design_families.py), so there is no
    earlier-stage evidence this refusal could erase; what is refused is
    manufacturing a SIMULATED number for a structure the candidate never
    actually described.
    """
    _require_fields(step_input, {"geometry", "frequency_hz"}, "simulation")
    geometry = dict(step_input["geometry"])

    gaps = _palace_metasurface_capability_gaps(geometry)
    if gaps:
        detail = "; ".join(f"{gap['gap']}: {gap['costs']}" for gap in gaps)
        raise _SimulatorError(
            "PALACE_FLOQUET is the right adapter for a ground-backed metasurface "
            "cell (REFLECTION_PHASE/DIFFUSIVE), and this candidate's geometry does "
            f"not yet describe one. Missing: {detail}. No SIMULATION result is "
            "recorded for this candidate. See simulation/palace.py's "
            "metasurface_capability_gaps() for how to close each gap -- this is "
            "checked in the geometry dict itself, before any solver time is spent."
        )

    result = _run_palace_simulation(
        geometry=geometry,
        frequency_hz=step_input["frequency_hz"],
        sweep=step_input.get("sweep"),
        num_processes=int(step_input.get("num_processes", 1)),
        timeout_s=int(step_input.get("timeout_s", 3600)),
        executable=step_input.get("executable"),
        workdir=step_input.get("workdir"),
        solver_order=int(step_input.get("solver_order", 1)),
    )

    s_parameters = result.get("s_parameters") or {}
    recorded = {
        "function": "run_palace_simulation",
        "simulator": result.get("simulator"),
        "status": result.get("status"),
        "frequency_hz": s_parameters.get("frequency_hz"),
        # Palace's own per-diffraction-order reflectance/phase output --
        # what this family actually needs to know (issue #252's user story
        # 6/7), not a quantity derived or borrowed from another family's
        # physics.
        "s_parameters": s_parameters,
        "specular": s_parameters.get("specular"),
        # Power-balance/passivity/reciprocity, carried through unmodified
        # (issue #221) -- warned on, never blocked on, per ADR-0028.
        "conservation_check": result.get("conservation_check"),
        "provenance": result.get("provenance", "SIMULATED"),
    }
    return "simulation", recorded, recorded["provenance"]


# The step_input fields `_simulate_nec2` requires, named so
# `orchestration/solver.py` can import this fact instead of restating it as
# its own literal (issue #497/#510) -- exactly today's inline set, moved
# here with zero behavior change to the handler below.
SIMULATE_NEC2_REQUIRED_FIELDS: set[str] = {
    "geometry",
    "frequency_hz",
    "reference_impedance_ohms",
}


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
    _require_fields(step_input, SIMULATE_NEC2_REQUIRED_FIELDS, "simulation")
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
        # Which function actually ran, stated on the result itself -- the
        # same key `_simulate_meep_floquet`/`_simulate_palace_floquet`
        # already record, and the one `orchestration/tooling.py`'s flush
        # reads for `engineering_results.tool_name` (issue #334). Without
        # it this branch would depend on a per-step default to be labelled
        # correctly, which is precisely how every Meep and Palace run came
        # to be filed under NEC2's name.
        "function": "run_nec2_simulation",
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
# never quietly served by another solver (issue #241). Palace is implemented
# in simulation/palace.py, validated against a real binary (#210), and wired
# here as PALACE_FLOQUET for REFLECTION_PHASE/DIFFUSIVE (#252 ticket 3).
_SIMULATION_ADAPTERS: dict[str, Any] = {
    "NEC2": _simulate_nec2,
    "MEEP_FLOQUET": _simulate_meep_floquet,
    "PALACE_FLOQUET": _simulate_palace_floquet,
}


def _optimizer_class_for(state: DesignLoopState) -> str | None:
    """The `optimizer_class` (`designs/design_families.py`) this iteration's
    ARCHITECTURE-recorded family declares -- issue #255 ticket 1.

    Mirrors `_simulation_adapter_for`: it reads the SAME family-lookup seam
    `_handle_analysis` (#239) and `_handle_simulation` (#229) already use
    (`_registry_family_of_record`) to resolve which family this iteration's
    step belongs to, off the recorded ARCHITECTURE decision -- never a
    second, parallel lookup, and never a hardcoded family-name list (issue
    #255's own user story 3/17: dispatch must key off the family's declared
    field).

    Unlike `_simulation_adapter_for`, this never raises for an UNSET value.
    `optimizer_class` is an open, optional field (ADR-0018) -- `None` is
    what every family in this tree declares today (nothing has opted into
    `COMBINATORIAL` yet) and is itself a legitimate, un-raising answer
    ("this family's OPTIMIZATION step is the plain continuous search"), not
    a missing-declaration error the way an unsettled `simulation_adapter`
    is. Only "there is no ARCHITECTURE decision to read a family off at
    all" raises here, via `_registry_family_of_record`.
    """
    return _registry_family_of_record(state, "optimization").optimizer_class


# The step_input fields `_optimize_continuous_patch_length` requires, named
# so `orchestration/solver.py` can import this fact instead of restating it
# as its own literal (issue #497/#510) -- exactly today's inline set, moved
# here with zero behavior change to the handler below.
OPTIMIZE_CONTINUOUS_PATCH_LENGTH_REQUIRED_FIELDS: set[str] = {
    "eps_r",
    "w_m",
    "h_m",
    "target_frequency_hz",
    "length_lower_m",
    "length_upper_m",
}


def _optimize_continuous_patch_length(
    _family: Any, step_input: dict[str, Any]
) -> tuple[str, dict[str, Any], str | None]:
    """The plain continuous patch-length search (issue #255 ticket 1) --
    this loop's ONLY OPTIMIZATION path until issue #267 added
    `_optimize_combinatorial_symbol_placement` beside it. Handles
    `optimizer_class == "CONTINUOUS"` and, via `_OPTIMIZER_HANDLERS`'s
    lookup key below, the unset (`None`) case too -- see `_handle_
    optimization`'s docstring for why both route here identically.

    `_family` is unused: this search has never needed anything off the
    registry entry, unlike its COMBINATORIAL sibling (which needs the
    family's name for its own error messages). It is still accepted, not
    dropped, so both entries in `_OPTIMIZER_HANDLERS` share one call
    signature `(family, step_input)` -- the same uniform-signature
    discipline `_ANALYSIS_MODELS`/`_SIMULATION_ADAPTERS`'s handlers already
    follow.
    """
    _require_fields(step_input, OPTIMIZE_CONTINUOUS_PATCH_LENGTH_REQUIRED_FIELDS, "optimization")
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


def _handle_optimization(
    state: DesignLoopState, step_input: dict[str, Any]
) -> tuple[str, dict[str, Any], str | None]:
    """Dispatch OPTIMIZATION to the search this design family's declared
    `optimizer_class` calls for (issue #255 ticket 1; wired up to a real
    `COMBINATORIAL` search at issue #267; converted to the same dict-
    dispatch pattern as `_handle_analysis`/`_handle_simulation` at issue
    #508 -- this docstring claimed that pattern from issue #255 onward, but
    the code underneath it was actually a chain of `if/elif optimizer_class
    == ... / raise` checks with no table a reader (or the error message
    below) could point at).

    `optimizer_class == "CONTINUOUS"`, and a family that declares no
    optimizer_class at all (`None` -- every family in `designs/
    design_families.py` except REFLECTION_PHASE/DIFFUSIVE; ADR-0018 leaves
    the field open until a family opts in), both route to the SAME
    patch-length search this step has always run, byte-for-byte unchanged:
    same required fields, same call, same result shape (issue #255 ticket
    1's own acceptance criterion, re-confirmed unchanged by issues #267 and
    #508). The `None` case is folded into the `"CONTINUOUS"` lookup key
    right here, before `_OPTIMIZER_HANDLERS` is consulted, rather than
    given its own dict entry -- `None` is not itself an `optimizer_class`
    value a family could declare a handler for, it is the ABSENCE of one.

    `optimizer_class == "COMBINATORIAL"` -- the shape issue #109/CONTEXT.md
    give REFLECTION_PHASE and DIFFUSIVE's Tier B optimizer, a genetic-
    algorithm search over a pre-characterized symbol alphabet -- routes to
    `_optimize_combinatorial_symbol_placement` (issue #267), which resolves
    real candidate symbols from the Element/Coding-Alphabet library (issue
    #256) and hands them to `optimization.combinatorial.
    combinatorial_symbol_placement` (issue #255 ticket 2). See that
    function's own docstring for the full shape of this branch, including
    why a family with nothing characterised yet still fails loudly here
    rather than falling through to the continuous search.

    Any OTHER declared value (a hypothetical third `optimizer_class`, e.g.
    ML-direct inverse design -- ADR-0018 names this as a credible future
    value) is not a key in `_OPTIMIZER_HANDLERS`, so `.get` returns `None`
    and the block below raises, naming the family and the unhandled value
    -- per issue #255's user story 4, reported by name, never guessed past,
    in the exact wording style `_handle_analysis`'s own "no handler wired"
    raise uses for `_ANALYSIS_MODELS`.
    """
    optimizer_class = _optimizer_class_for(state)
    if optimizer_class is None:
        optimizer_class = "CONTINUOUS"
    family = _registry_family_of_record(state, "optimization")
    handler = _OPTIMIZER_HANDLERS.get(optimizer_class)
    if handler is None:
        raise DesignLoopValidationError(
            f"Design family {family.name!r} declares optimizer_class "
            f"{optimizer_class!r}, and this loop has no handler wired for it. "
            "Add one to _OPTIMIZER_HANDLERS in orchestration/design_loop.py, "
            "or correct the declaration in designs/design_families.py -- "
            "silently falling through to the patch-length search is exactly "
            "what issues #239/#241 already removed for ANALYSIS/SIMULATION."
        )
    return handler(family, step_input)


def _combinatorial_candidate_options(
    symbol_entries: list[dict[str, Any]],
    element_family: str,
    frequency_hz: float,
    incidence_angle_deg: float,
    process_id: int,
    response_field: str,
) -> list[_SymbolOption]:
    """Resolve the ONE shared set of candidate symbols a COMBINATORIAL
    OPTIMIZATION step searches over, from an already-fetched
    `designs.element_alphabet.fetch_symbol_entries` result (issue #267
    design decision 2).

    `symbol_entries` is whatever the caller already fetched for
    `element_family` -- this function, like `designs.element_alphabet.
    lookup_symbol_entries` it calls, never touches a database itself (see
    `_optimize_combinatorial_symbol_placement`'s own docstring for why).

    HOW CANDIDATES ARE FOUND: every DISTINCT `symbol` name present in
    `symbol_entries` is checked, via `lookup_symbol_entries`, against the
    single shared `(frequency_hz, incidence_angle_deg, process_id)` point
    query -- reusing that function's own public match logic rather than
    reaching into its private `_symbol_entry_matches` helper (a module
    should not depend on another module's underscore-prefixed internals;
    `lookup_symbol_entries` is the supported seam for exactly this "does a
    stored entry match this point" question). ALL matching entries for a
    symbol are kept, not just the first: `resolve_symbol_entry`'s own
    docstring is explicit that "picking the best of several [simultaneously
    matching] candidates is the combinatorial optimizer's job" -- this is
    that job, so an ambiguous symbol (e.g. two runs whose declared bands
    happen to overlap the query point) contributes one `SymbolOption` per
    matching entry, and the search decides which one, if any, belongs in
    the winning layout.

    Returns a plain list, empty if nothing matches -- the caller checks for
    that and raises a named error before ever reaching
    `combinatorial_symbol_placement` (design decision 4a).
    """
    distinct_symbols = sorted({entry["symbol"] for entry in symbol_entries})
    options: list[_SymbolOption] = []
    for symbol in distinct_symbols:
        matches = _lookup_symbol_entries(
            symbol_entries,
            element_family,
            symbol,
            frequency_hz,
            incidence_angle_deg,
            process_id,
        )
        for entry in matches:
            achieved_value = _reduce_response_at_frequency(
                entry["response"], frequency_hz, response_field
            )
            # entry_id (issue #400): the matched row's own `id`, when it has
            # one -- a REAL `designs.element_alphabet.fetch_symbol_entries`
            # row always does (it's the table's own `BIGSERIAL PRIMARY
            # KEY`, via `SELECT *`). `.get`, not `entry["id"]`: a hand-built
            # fixture entry (a test's own `symbol_entries`, standing in for
            # the not-yet-existing Element/Coding-Alphabet library
            # lookup -- see this function's own docstring) may omit `id`
            # entirely, and `None` here is the honest "not resolved against
            # a real row" reading `SymbolOption.entry_id`'s own docstring
            # already documents, not a reason to raise on a well-formed but
            # id-less caller-supplied entry.
            options.append(
                _SymbolOption(
                    symbol_id=symbol, achieved_value=achieved_value, entry_id=entry.get("id")
                )
            )
    return options


def _combinatorial_result_to_dict(result: Any) -> dict[str, Any]:
    """`optimization.combinatorial.CombinatorialPlacementResult` -> a flat,
    JSON-friendly dict -- the same "flat dict, JSON-friendly for the
    MCP/agent tool boundary" convention `optimization.rf_objectives.
    optimize_patch_length_for_target_frequency`'s own docstring states for
    the continuous path's result, applied here so `LoopDecision.result`
    (this module's docstring's "STATE DESIGN" section: `DesignLoopState`
    is a plain, JSON-serializable dataclass) can hold this step's result
    exactly the way it holds every other step's.

    `combinatorial_symbol_placement`'s own return value is deliberately
    NOT already this shape -- it stays generic/reusable there (a `Position`
    `(i, j)` TUPLE key and `SymbolOption` dataclass values in
    `candidate_snapshot`, neither of which is valid JSON), and this
    dispatch site is what owns converting it, the same "generic function,
    JSON conversion at the tool boundary" split `rf_objectives` already
    draws for its own result.
    """
    candidate_snapshot = [
        {
            "i": i,
            "j": j,
            "candidates": [
                {
                    "symbol_id": option.symbol_id,
                    "achieved_value": option.achieved_value,
                    # entry_id (issue #400): the matched symbol_alphabet_
                    # entries.id this option resolved from, so a candidate
                    # that was AVAILABLE at (i, j) but not chosen is still
                    # traceable to its own measured row, not just the
                    # winning cell's own entry_id_layout entry below.
                    "entry_id": option.entry_id,
                }
                for option in options
            ],
        }
        # Row-major, j-outer/i-inner -- the SAME grid-walk order
        # optimization.combinatorial's own `positions = [(i, j) for j in
        # range(n_rows) for i in range(n_cols)]` and `_grid_from_choices`'s
        # `layout[j][i]` already use, so this debug/audit snapshot's order
        # agrees with every other grid walk this feature touches (each
        # entry is still self-describing via its own "i"/"j" fields either
        # way, but there is no reason for this one list to be the odd one
        # out).
        for (i, j), options in sorted(
            result.candidate_snapshot.items(), key=lambda kv: (kv[0][1], kv[0][0])
        )
    ]
    return {
        # Which search actually ran, stated the same way every other
        # family-dispatched step states it (issue #334), so
        # `orchestration/tooling.py`'s flush files this row under the
        # combinatorial search rather than under the continuous patch-length
        # one this family never touched. `method` happens to carry the same
        # string here, but it is not the same fact: on the CONTINUOUS path
        # `method` is the search algorithm ("parameter_sweep"/
        # "bayesian_optimize"), so a reader cannot use it as a tool name.
        "function": "combinatorial_symbol_placement",
        "method": result.method,
        "layout": result.layout,
        # entry_id_layout (issue #400): the SAME [j][i] shape as "layout"
        # above, naming which measured symbol_alphabet_entries row -- and
        # therefore which process/machine/ink -- backed the WINNING choice
        # at each cell. A bare symbol_id in "layout" cannot answer that on
        # its own: several entries can share one symbol/band/incidence-
        # angle-range/process (ADR-0027 point 4's "two runs are still two
        # distinct rows" rule).
        "entry_id_layout": result.entry_id_layout,
        "achieved_error": result.achieved_error,
        "evaluations": result.evaluations,
        "target": result.target,
        "candidate_snapshot": candidate_snapshot,
        "delta_phi_max_deg": result.delta_phi_max_deg,
        "random_seed": result.random_seed,
        "warnings": result.warnings,
        "objective_name": result.objective_name,
        "provenance": result.provenance,
    }


def _optimize_combinatorial_symbol_placement(
    family: Any,
    step_input: dict[str, Any],
) -> tuple[str, dict[str, Any], str | None]:
    """The COMBINATORIAL OPTIMIZATION path for REFLECTION_PHASE/DIFFUSIVE
    (issue #267): resolve real candidate symbols from the Element/
    Coding-Alphabet library (issue #256) and hand them to `optimization.
    combinatorial.combinatorial_symbol_placement` (issue #255 ticket 2) --
    replacing `_handle_optimization`'s former "not wired yet" raise (ticket
    1's interim safety net).

    step_input FIELDS, AND WHY (design decision 1). Required:
    `element_family`, `symbol_entries` (a list already fetched via
    `designs.element_alphabet.fetch_symbol_entries` -- this module never
    opens a database connection itself; `_resolve_eps_r_bounds`'s own "the
    design loop stays the DB-free, pure state machine" rule applies here
    identically -- the caller resolves the library lookup, this handler
    only filters/reduces the plain list it was handed), `frequency_hz`,
    `incidence_angle_deg`, `process_id` (the SAME three names
    `designs.element_alphabet.lookup_symbol_entries` itself uses -- the
    path of least translation for a caller who already has that function's
    signature in front of it), `target` (matching
    `combinatorial_symbol_placement`'s own parameter name and
    `target[j][i]` shape), and `delta_phi_max_deg` (ditto). Optional,
    forwarded unchanged when given: `random_seed`, `max_generations`,
    `population_size`, `objective_name` --
    `combinatorial_symbol_placement`'s own defaults apply when omitted.

    `frequency_hz`, NOT `target_frequency_hz`: the CONTINUOUS branch just
    above this one in `_handle_optimization` uses `target_frequency_hz`,
    but this handler's SIMULATION-step sibling for these same two families,
    `_simulate_palace_floquet`, already uses a bare `frequency_hz` for the
    identical "one point on the band this run is evaluated at" idea, and
    `lookup_symbol_entries`'s own parameter is spelled `frequency_hz` too.
    Both spellings are established precedent in this codebase;
    `frequency_hz` is chosen here because it agrees with BOTH of this
    handler's direct neighbours (the sibling SIMULATION handler for these
    families, and the library function this handler calls), where
    `target_frequency_hz` would only agree with the unrelated continuous
    patch-length search.

    ONE SHARED CANDIDATE SET, NOT ONE PER GRID POSITION (design decision
    2): nothing in this codebase varies incidence angle or process across a
    single design's grid, so "the current design's target band,
    incidence-angle range, and process" (issue #267's own wording) is ONE
    point query, resolved once by `_combinatorial_candidate_options` and
    reused identically at every `(i, j)` position
    `combinatorial_symbol_placement` asks about.

    THE RESPONSE-TO-SCALAR FIELD IS NAMED "phase_deg" HERE, NOT DEFAULTED
    INSIDE THE REDUCTION FUNCTION (design decision 3): REFLECTION_PHASE and
    DIFFUSIVE are both designed by their per-cell reflection PHASE
    (designs/design_families.py's own comments on both families -- "a
    coding cell IS its reflection phase"). That fact belongs at THIS call
    site, not baked into `designs.element_alphabet.
    reduce_response_at_frequency`, which stays generic on purpose,
    mirroring `SymbolOption.achieved_value`'s own "generic on purpose"
    docstring.

    ZERO MATCHING ENTRIES FAILS LOUDLY, NAMING THE KEY, BEFORE THE
    COMBINATORIAL SEARCH EVER RUNS (design decision 4a): every grid
    position shares the one candidate list `_combinatorial_candidate_
    options` resolves, so an empty result means EVERY position has nothing
    to place -- checked and reported here, naming exactly which
    family/band/incidence-angle/process came up empty, rather than letting
    `combinatorial_symbol_placement` discover it position-by-position via
    `EmptyCandidateShelfError`. In production today the alphabet holds
    nothing (issue #132's print-and-measure work has not happened) -- this
    is the path a real run actually takes, and it must never fall through
    to the continuous patch-length search (the same discipline issues
    #239/#241 already apply to ANALYSIS/SIMULATION).

    `EmptyCandidateShelfError` (design decision 4b) -- raised by
    `combinatorial_symbol_placement` itself, reachable if some narrower gap
    slips past the check above -- is re-raised as `DesignLoopValidationError`
    with its own message intact, the same `raise DesignLoopValidationError
    (str(exc)) from exc` convention `_handle_architecture`/`_handle_analysis`/
    `_declared_adapter_name` already use for every other adapter-level
    exception in this file.

    THE TARGET-SHAPE GUARD BELOW ALSO CHECKS RAGGEDNESS (design decision
    4c), duplicating part of `optimization.combinatorial._validate_target`'s
    own non-empty/rectangular check. That duplication is only partly
    avoidable -- this handler needs `n_rows`/`n_cols` before it can build
    `candidates` at all, a real constraint of `combinatorial_symbol_
    placement`'s signature (the caller supplies candidates, so the caller
    must already know the grid shape) -- but the two checks must agree on
    what they reject: a ragged `target` that only `_validate_target` caught
    would raise a bare, un-wrapped `ValueError` from inside
    `combinatorial_symbol_placement`, past this handler's `except
    _EmptyCandidateShelfError` clause, with none of this dispatch layer's
    naming/wrapping discipline. Checking row-length consistency here too
    closes that gap up front, the same place the non-empty/2D check already
    lives.
    """
    _require_fields(
        step_input,
        {
            "element_family",
            "symbol_entries",
            "frequency_hz",
            "incidence_angle_deg",
            "process_id",
            "target",
            "delta_phi_max_deg",
        },
        "optimization",
    )
    element_family = step_input["element_family"]
    frequency_hz = step_input["frequency_hz"]
    incidence_angle_deg = step_input["incidence_angle_deg"]
    process_id = step_input["process_id"]
    target = step_input["target"]

    candidate_options = _combinatorial_candidate_options(
        symbol_entries=step_input["symbol_entries"],
        element_family=element_family,
        frequency_hz=frequency_hz,
        incidence_angle_deg=incidence_angle_deg,
        process_id=process_id,
        response_field="phase_deg",
    )
    if not candidate_options:
        raise DesignLoopValidationError(
            f"Design family {family.name!r} needs at least one candidate symbol "
            f"for element_family={element_family!r} at frequency_hz={frequency_hz!r}, "
            f"incidence_angle_deg={incidence_angle_deg!r}, process_id={process_id!r}, "
            "and none of the supplied symbol_entries match that key. Every grid "
            "position in this design shares this same lookup, so none of them can "
            "be placed until at least one symbol is characterised for this "
            "family/band/incidence-angle/process (issue #132's print-and-measure "
            "work) -- this never falls through to the continuous patch-length "
            "search (the same discipline issues #239/#241 already apply to "
            "ANALYSIS/SIMULATION, per issue #267)."
        )

    if not isinstance(target, list) or not target or not isinstance(target[0], list):
        raise DesignLoopValidationError(
            "optimization step_input['target'] must be a non-empty 2D grid "
            f"(target[j][i]), got {target!r}"
        )
    n_rows = len(target)
    n_cols = len(target[0])
    if any(not isinstance(row, list) or len(row) != n_cols for row in target):
        raise DesignLoopValidationError(
            "optimization step_input['target'] must be rectangular (every row "
            f"the same length): row lengths were "
            f"{[len(row) if isinstance(row, list) else type(row).__name__ for row in target]}"
        )
    candidates = {(i, j): candidate_options for j in range(n_rows) for i in range(n_cols)}

    try:
        result = _combinatorial_symbol_placement(
            target=target,
            candidates=candidates,
            delta_phi_max_deg=step_input["delta_phi_max_deg"],
            random_seed=step_input.get("random_seed"),
            max_generations=step_input.get("max_generations", 100),
            population_size=step_input.get("population_size", 15),
            objective_name=step_input.get("objective_name"),
        )
    except _EmptyCandidateShelfError as exc:
        raise DesignLoopValidationError(str(exc)) from exc

    recorded = _combinatorial_result_to_dict(result)
    return "optimization", recorded, recorded["provenance"]


# The dispatch table `_handle_optimization` reads -- this loop's counterpart
# to `_ANALYSIS_MODELS`/`_SIMULATION_ADAPTERS` above. One named handler per
# declared `optimizer_class` value (`"CONTINUOUS"` also standing in for the
# unset/`None` case -- see `_handle_optimization`'s own docstring for why
# that fold happens before this dict is consulted rather than as a third
# entry here). A family declaring a value that is not a key here is a
# reported failure, not a fallback (issue #508).
_OPTIMIZER_HANDLERS: dict[str, Any] = {
    "CONTINUOUS": _optimize_continuous_patch_length,
    "COMBINATORIAL": _optimize_combinatorial_symbol_placement,
}


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
            if "tolerance_comparison" in value:
                jsonified[key]["tolerance_comparison"] = value["tolerance_comparison"]
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
        known_tolerance_db=step_input.get("known_tolerance_db"),
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
    _validate_considered_and_dropped(
        step_input.get("considered_and_dropped"), _state.requirements, "redesign_decision"
    )
    _validate_capability_warnings(step_input.get("capability_warnings"), "redesign_decision")
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
    requirements_document_status: str | None = None,
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

    For ARCHITECTURE specifically, `requirements_document_status` is ALSO
    checked (issue #325, docs/adr/0034; see this module's own docstring's
    "REQUIREMENTS-DOCUMENT GATE" section) -- it must equal `"CONFIRMED"`
    (`designs.requirements_document.DocumentStatus.CONFIRMED.value`) or the
    same OrchestrationError is raised, naming what's missing, with `state`
    equally untouched. Pass the design's current Requirements-document
    status here (from `designs.requirements_document.
    read_requirements_document`'s `document_status`); the default `None`
    covers both "the caller didn't say" and "no Requirements document
    exists yet". Ignored for every other step.
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

        if current_step is DesignStep.ARCHITECTURE:
            _require_requirements_document_confirmed(requirements_document_status)

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
