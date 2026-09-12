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
from designs.design_families import get_design_family as _get_design_family
from designs.requirement_targets import GroundPlaneStatus as _GroundPlaneStatus
from designs.requirement_targets import (
    InvalidRequirementTargetError as _InvalidRequirementTargetError,
)
from designs.requirement_targets import TargetComparator as _TargetComparator
from designs.requirement_targets import propose_target as _propose_target
from designs.requirements_document import DocumentStatus as _RequirementsDocumentStatus
from measurement.external import record_external_measurement as _record_external_measurement

# Unused in this module itself -- `_optimize_continuous_patch_length`/
# `_optimize_combinatorial_symbol_placement`
# (orchestration/design_loop_optimization.py, issue #519) each read the
# matching name back off THIS module lazily, at call time, rather than
# binding their own top-level copy, specifically so that
# tests/test_design_loop.py's `monkeypatch.setattr(design_loop_module,
# "_optimize_patch_length_for_target_frequency", ...)` and
# `monkeypatch.setattr(design_loop_module, "_combinatorial_symbol_placement",
# ...)` -- which patch these exact attributes -- keep intercepting the real
# search calls after the split, the same as they did before they moved.
# `_EmptyCandidateShelfError` is kept for the identical reason, even though
# nothing in this module raises or catches it directly any more:
# tests/test_design_loop.py constructs one as
# `design_loop_module._EmptyCandidateShelfError(...)`, so this module must
# keep the name bound as its own attribute.
from optimization.combinatorial import (
    EmptyCandidateShelfError as _EmptyCandidateShelfError,  # noqa: F401
)
from optimization.combinatorial import (
    combinatorial_symbol_placement as _combinatorial_symbol_placement,  # noqa: F401
)
from optimization.rf_objectives import (
    optimize_patch_length_for_target_frequency as _optimize_patch_length_for_target_frequency,  # noqa: F401
)
from rf_tools.calculations import (
    curvature_exceeds_validity_box as _curvature_exceeds_validity_box,
)
from rf_tools.correlation import (
    correlate_simulation_measurement as _correlate_simulation_measurement,
)

# Unused in this module itself -- `_simulate_nec2`/`_simulate_meep_floquet`/
# `_simulate_palace_floquet` (orchestration/design_loop_simulation.py, issue
# #516) each read the matching name back off THIS module lazily, at call
# time, rather than binding their own top-level copy, specifically so that
# tests/test_design_loop.py's `monkeypatch.setattr(design_loop_module,
# "_run_nec2_simulation", ...)` (and its Meep/Palace equivalents) -- which
# patches this exact attribute -- keeps intercepting the real solver call
# after the split, the same as it did before it moved.
from simulation.meep import run_meep_simulation as _run_meep_simulation  # noqa: F401
from simulation.nec2pp import run_nec2_simulation as _run_nec2_simulation  # noqa: F401
from simulation.palace import run_palace_simulation as _run_palace_simulation  # noqa: F401

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

# _handle_optimization is wired into _STEP_HANDLERS below; the other names
# are unused in this module itself but re-exported as orchestration.design_
# loop attributes (issue #519) so a caller that already reached them there
# -- tests/test_design_loop.py's direct imports of
# _combinatorial_result_to_dict/_optimizer_class_for, and its
# design_loop_module._optimize_combinatorial_symbol_placement/
# design_loop_module._OPTIMIZER_HANDLERS references, included -- keeps
# working unchanged.
from .design_loop_optimization import (
    _OPTIMIZER_HANDLERS,  # noqa: F401
    _combinatorial_candidate_options,  # noqa: F401
    _combinatorial_result_to_dict,  # noqa: F401
    _handle_optimization,
    _optimize_combinatorial_symbol_placement,  # noqa: F401
    _optimize_continuous_patch_length,  # noqa: F401
    _optimizer_class_for,  # noqa: F401
)

# _handle_simulation is wired into _STEP_HANDLERS below; the other names are
# unused in this module itself but re-exported as orchestration.design_loop
# attributes (issue #516) so a caller that already reached them there --
# tests/test_design_loop.py's direct imports of
# _require_reflector_or_confirmed_host_ground_plane/_simulation_adapter_for,
# and verification/meep_two_port_absorption_check.py's direct import of
# _simulate_meep_floquet, included -- keeps working unchanged.
from .design_loop_simulation import (
    _SIMULATION_ADAPTERS,  # noqa: F401
    _declared_adapter_name,  # noqa: F401
    _handle_simulation,
    _meep_absorption_for_family,  # noqa: F401
    _require_reflector_or_confirmed_host_ground_plane,  # noqa: F401
    _require_transmission_monitor_for_two_port,  # noqa: F401
    _role_tagged_primitives,  # noqa: F401
    _simulate_meep_floquet,  # noqa: F401
    _simulate_nec2,  # noqa: F401
    _simulate_palace_floquet,  # noqa: F401
    _simulation_adapter_for,  # noqa: F401
    _two_port_transmittance,  # noqa: F401
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


# The step_input fields `_simulate_nec2` requires, named so
# `orchestration/solver.py` can import this fact instead of restating it as
# its own literal (issue #497/#510) -- exactly today's inline set, moved
# here with zero behavior change to the handler below.
SIMULATE_NEC2_REQUIRED_FIELDS: set[str] = {
    "geometry",
    "frequency_hz",
    "reference_impedance_ohms",
}


# _optimizer_class_for, _handle_optimization and its two search handlers
# (_optimize_continuous_patch_length, _optimize_combinatorial_symbol_
# placement), their supporting helpers (_combinatorial_candidate_options,
# _combinatorial_result_to_dict), and the _OPTIMIZER_HANDLERS dispatch table
# they share, moved to orchestration/design_loop_optimization.py (issue
# #519, split out of issue #498 -- the last of the three dispatch-axis
# extractions) -- imported at this module's top, alongside its other
# imports; see that module's own docstring for why its reverse dependency on
# THIS module (_registry_family_of_record, _require_fields,
# DesignLoopValidationError, DesignLoopState,
# OPTIMIZE_CONTINUOUS_PATCH_LENGTH_REQUIRED_FIELDS,
# _optimize_patch_length_for_target_frequency, _combinatorial_symbol_
# placement, _EmptyCandidateShelfError) is resolved lazily rather than up
# front, which is what keeps this import safe to sit at the top here rather
# than needing to wait for those names' definitions below. This import also
# re-exports _combinatorial_result_to_dict and _optimizer_class_for as
# orchestration.design_loop attributes, so nothing that already imported
# them from here (tests/test_design_loop.py included) needs to change.


# The step_input fields `_optimize_continuous_patch_length`
# (orchestration/design_loop_optimization.py, issue #519) requires, named
# so `orchestration/solver.py` can import this fact instead of restating it
# as its own literal (issue #497/#510) -- exactly today's inline set. This
# constant stays here, not moved alongside the handler that reads it: issue
# #510 already added it to this module for `solver.py`'s own `from
# .design_loop import OPTIMIZE_CONTINUOUS_PATCH_LENGTH_REQUIRED_FIELDS` to
# resolve, and that import must keep resolving unchanged.
OPTIMIZE_CONTINUOUS_PATCH_LENGTH_REQUIRED_FIELDS: set[str] = {
    "eps_r",
    "w_m",
    "h_m",
    "target_frequency_hz",
    "length_lower_m",
    "length_upper_m",
}


# _handle_optimization is wired into _STEP_HANDLERS below; _optimize_
# continuous_patch_length, _optimize_combinatorial_symbol_placement,
# _combinatorial_candidate_options, and _OPTIMIZER_HANDLERS are unused in
# this module itself but re-exported as orchestration.design_loop
# attributes (issue #519) so a caller that already reached them there
# keeps working unchanged.


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
