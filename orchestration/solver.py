"""The candidate solver -- software iterates a design loop's ungated
ANALYSIS/SIMULATION/OPTIMIZATION span, candidate after candidate, scoring
each as it goes, until it has taken the design as far as software alone
can (issue #95; docs/adr/0014; direct inputs: orchestration/design_loop.py,
orchestration/tooling.py, designs/success_score.py, designs/
requirement_targets.py).

WHAT THIS MODULE ANSWERS. Once a loop is positioned past its ARCHITECTURE
gate (an engineer has already approved one architecture -- see below), an
engineer no longer wants to hand-drive one candidate parameter set at a
time through ANALYSIS -> SIMULATION -> OPTIMIZATION, read its score, propose
another by hand, and repeat. `run_candidate_search` is that loop, run in
software: given the loop's current state and a batch of LLM-proposed
candidate parameter sets, it drives each candidate through the loop's own
step functions, scores every scoreable step against a stated requirement
target, and stops on target satisfaction, a score plateau, or its
evaluation budget -- reporting which, so the engineer knows precisely when
software has taken the design as far as it can and a lab trip (or a fresh
architecture decision) is the honest next move.

------------------------------------------------------------------------
THE NON-NEGOTIABLE CONSTRAINT THIS MODULE OBEYS (docs/adr/0014, read twice
before touching this file): the solver is additive and NEVER bypasses the
design loop's approval gates. This module:

  - does NOT modify orchestration/design_loop.py's state machine, its
    handlers, GATED_STEPS, or advance_loop_step's gate check -- it imports
    orchestration.tooling.advance_design_loop_step (itself a thin wrapper
    over design_loop.advance_loop_step, see below) and calls it, nothing
    more.
  - does NOT construct, forge, fabricate, or pass an approval receipt --
    every call this module makes to advance_design_loop_step passes
    `approval=None`, which is exactly correct because this module only
    ever drives steps outside GATED_STEPS (see "SCOPE" below); passing
    None is not a workaround, it is the honest value for an ungated step.
  - does NOT call orchestration.approval.request_loop_step_approval.
  - on reaching a gated step (ARCHITECTURE, MEASUREMENT, REDESIGN_DECISION)
    -- because the state handed in already sits there, not because this
    module ever tries to walk into one -- returns NORMALLY with a report
    naming the pending approval (`stop_reason="gated_step_pending_approval"`,
    `pending_approval` copied verbatim from the loop's own, untouched
    `pending_approval` computation in design_loop.py's `_pending_approval_
    for`). It never raises to signal this, and it never attempts anything
    once it sees a gated current_step.

tests/test_solver.py's `test_solver_halts_at_a_gated_redesign_decision_
step_with_no_receipt_ever_created` and `test_module_never_imports_
approval_receipt_machinery` are the explicit, structural proof: the
first inspects the returned report after driving a real state all the
way to a gated step; the second parses this module's own AST to prove
neither `LoopStepApprovalReceipt` nor `request_loop_step_approval` is
ever imported here at all -- not merely uncalled.

------------------------------------------------------------------------
SCOPE: PARAMETER-LEVEL SEARCH INSIDE AN ALREADY-APPROVED ARCHITECTURE.

Committing to an architecture is the gated decision (ARCHITECTURE, in
GATED_STEPS); trying candidate dimensions inside one is OPTIMIZATION,
already ungated -- so this module only ever operates on a loop state
already positioned PAST ARCHITECTURE, and never needs a receipt for its
own work. `_ORDERED_UNGATED_SPAN = (ANALYSIS, SIMULATION, OPTIMIZATION)`
below is the exact and only span this module drives.

This module does NOT search over architectures. docs/adr/0014 explicitly
records "auto-trying multiple architectures... auto-pick the best-scoring
one before a human ever sees the rejected ones" as the rejected
alternative, and it stays rejected here: a `state` handed to this module
whose `current_step` is ARCHITECTURE is refused exactly like MEASUREMENT
or REDESIGN_DECISION -- `stop_reason="gated_step_pending_approval"`, no
candidate is ever evaluated.

CORRECTION TO ADR-0014'S OWN WORDING -- read before assuming CORRELATION
is in scope. ADR-0014's prose names "ANALYSIS/SIMULATION/OPTIMIZATION/
CORRELATION" as the steps the (then not-yet-built) solver would drive.
Issue #95's own acceptance criteria and "WHAT YOU ARE BUILDING ON" section
-- written after that ADR, and this module's actual binding spec --
narrow that to exactly three: ANALYSIS, SIMULATION, OPTIMIZATION.
CORRELATION is deliberately excluded here, for a reason ADR-0014 did not
fully work through: `_handle_correlation` (design_loop.py) needs a
recorded MEASUREMENT decision (or an explicit `measured=` override in
step_input). A recorded MEASUREMENT decision cannot exist without having
already passed the MEASUREMENT gate -- so a solver that "drove CORRELATION"
would either (a) require the very lab trip this module exists to defer, at
which point candidate-searching before that trip is moot, or (b) accept a
caller-supplied `measured=` override with NO real MEASUREMENT decision
behind it, letting an agent quietly synthesize "measured" values that were
never gated through MEASUREMENT at all -- a softer, easier-to-miss version
of exactly the gate-bypass docs/adr/0014 forbids. Neither is acceptable,
so CORRELATION stays out of this module's driven span. (Matches designs/
success_score.py's own precedent of a documented, deliberate correction to
its governing ticket's literal wording -- see that module's "CRITICAL
CORRECTION" section.)

------------------------------------------------------------------------
DESIGN QUESTION 1 -- WHERE CANDIDATES COME FROM: A BATCH, PER CALL.

The LLM proposes candidates -- it is the agent -- so they arrive as tool
arguments, never as a model call inside this module (the same foundational
rule designs/requirement_targets.py and designs/success_score.py both
already obey: the LLM never does RF arithmetic or judgment a tool's caller
was supposed to have already done). This module accepts a BATCH
(`candidates: list[dict]`) in one call, not one candidate per call.
Rejected: one candidate per call. Rejected because the entire point of
this ticket (see its own framing: "software has taken the design as far
as it can", "iteration speed is set by the free/OSS simulators, not by
lab or approval availability") is that software, not the LLM turn-by-turn,
drives the fast loop -- a one-candidate-per-call shape would put a full
LLM round trip between every evaluation, reintroducing exactly the
bottleneck ("too slow to be the iteration mechanism") this ticket exists
to remove, merely swapping the lab bench for chat turns. A batch call lets
the LLM front-load a proposal strategy (a grid, an educated bisection, a
Bayesian-optimizer-style guess sequence) and get every candidate's full
score trail back from ONE tool call. `evaluation_budget` (design question
2's sibling parameter) still lets a caller cap how much of a supplied
batch is actually spent, so a batch is not an all-or-nothing commitment --
see "STOPPING RULES" below.

------------------------------------------------------------------------
DESIGN QUESTION 2 -- SCORE PLATEAU, PRECISELY.

Plateau is defined on the RUNNING BEST overall score (design question 3
defines "overall score" per candidate) across successfully-evaluated
candidates, in evaluation order: after each successful candidate, this
module appends the running best-so-far `overall_score_percent` to a list.
Once that list holds at least `plateau_window + 1` entries (default 5,
caller-overridable -- one more than the window itself, since comparing
the latest snapshot to the one `plateau_window` entries back needs both
endpoints to exist), it compares the latest running-best value to the
value `plateau_window` entries back; if the improvement is `<=
plateau_epsilon` percentage points (default 0.5, caller-overridable), the
search stops with `stop_reason="score_plateau"`. In words: "no improvement
exceeding epsilon in the best score found so far, across N consecutive
successfully-evaluated candidates" -- exactly the shape issue #95's own
text suggests ("e.g. no improvement exceeding some epsilon across N
consecutive candidates"), applied to the RUNNING BEST rather than to
consecutive raw scores, so one lucky-then-unlucky pair of candidates
cannot look like a plateau while the search is still trending upward
overall.

Failed candidates (see design question 4) are excluded from this
computation entirely -- neither consuming a slot in the N-window nor
resetting it -- since they contribute no score to compare. A caller whose
batch is mostly failures will exhaust `evaluation_budget` long before a
meaningful plateau window accumulates; that is the honest outcome, not
patched over here.

------------------------------------------------------------------------
DESIGN QUESTION 3 -- WHICH SCORE DRIVES CONVERGENCE: THE WORST SCORED
STEP, PER CANDIDATE ("worst_of_scored_steps", named in every result dict's
`convergence_rule` field).

A candidate can produce up to three scored steps (ANALYSIS/SIMULATION/
OPTIMIZATION, whichever the caller supplied a `score_specs` entry for --
see "SCORING" below). This module's `overall_score_percent` for that
candidate is the MINIMUM of its scored steps' `score_percent` values --
the design is only as good as its worst-performing stated requirement.
Rejected: best single score (would let a candidate that nails frequency
while badly missing gain read as a near-success, hiding the failing
requirement entirely behind the passing one -- exactly the kind of
selective reporting this project's provenance discipline exists to
prevent). Rejected: a mean/average of scored steps (a below-threshold gain
and an above-threshold frequency could average out to a comfortable
number while neither requirement is actually satisfied, and unlike the
threshold formulas in designs/success_score.py themselves -- which are
deliberately NOT linear/unbounded because "a design is not more done for
overshooting" -- an average would let a huge overshoot on one target paper
over a real shortfall on another). Rejected: all-must-pass (a bare
boolean) discards the very "how close" proximity signal `designs/
success_score.py` exists to compute, and would make `score_plateau`
detection undefined (there is no continuous number to compare
running-best against).

BE HONEST ABOUT WHAT "WORST" HIDES: this rule reports the single weakest
requirement's compliance, not how MANY requirements are failing, nor by
how much each one individually differs. Two candidates that both score
62% overall might be failing one target narrowly and another might be
failing two targets narrowly, or one target badly -- `overall_score_
percent` alone cannot distinguish them. The full per-step `score` dicts
are preserved in every candidate's trail entry (`steps`) specifically so a
reader who needs that finer picture always has it; `overall_score_percent`
is a convergence/ranking convenience over that full trail, never a
replacement for reading it.

------------------------------------------------------------------------
DESIGN QUESTION 4 -- A FAILING CANDIDATE IS RECORDED AND SKIPPED, NEVER
ABORTS THE RUN.

A candidate's drive can raise for reasons that have nothing to do with any
OTHER candidate: a missing NEC2++ binary (`simulation.base.SimulatorError`
-- an environment problem, but one candidate's SIMULATION failing does not
mean the next candidate's SIMULATION would too, once the binary exists),
a geometrically invalid patch (`rf_tools.calculations` raising `ValueError`
for a nonphysical `l_m`), a candidate dict missing a required field for the
step it reaches (`orchestration.design_loop.DesignLoopValidationError`,
raised by the SAME `_handle_analysis`/`_handle_simulation`/`_handle_
optimization` validation this module never reimplements), or a
`score_specs` field extraction that finds no numeric value where expected
(`designs.success_score.SuccessScoreError`). This module catches any
exception raised while driving ONE candidate, records it on that
candidate's trail entry (`status="failed"`, `failed_at_step`, `error`),
and continues to the next candidate -- it does not abort the whole batch.
Rejected: aborting the run on the first failure. Rejected because it would
let one bad candidate near the front of a batch (a typo'd dimension, an
LLM-proposed geometry outside NEC2's happy path) silently discard every
candidate after it that the caller already paid the evaluation-budget cost
to have proposed -- a single data problem with one candidate is not
evidence the search itself is broken. A failed candidate still consumes
one unit of `evaluation_budget` (an attempt was spent on it) but never
becomes `best_candidate_state` and never participates in plateau
detection (see design question 2).

A candidate that fails PARTWAY through `steps_to_drive` (e.g. a clean
ANALYSIS and SIMULATION, then a broken OPTIMIZATION) does not lose the
steps that already succeeded: `_drive_candidate` records each step's own
trail entry (raw result, and its score if one was requested) as it goes
and only stops at the step that failed, so the failed candidate's trail
entry still shows every step that DID run, each with its own score, right
up to the point of failure -- consistent with "each score visible as it is
evaluated" applying to a failed candidate's partial progress too, not only
to a fully-evaluated one. `overall_score_percent`/`all_targets_met` are
still computed from whatever WAS scored (so a reader can see how the
attempt was trending before it broke), but a failed candidate never
becomes `best_candidate_state` regardless of how good its partial score
looks: its resulting loop state is positioned mid-span at the step that
failed, not a coherent, fully-advanced point a caller could safely
continue the design from.

------------------------------------------------------------------------
WHICH LAYER THIS MODULE DRIVES: `orchestration.tooling.advance_design_
loop_step` (the TOOLING layer), not `orchestration.design_loop.
advance_loop_step` directly -- deliberately, to satisfy the acceptance
criterion "a run's engineering results and scores persist at the existing
iteration-boundary flush". That flush (docs/adr/0011) lives entirely in
`orchestration/tooling.py`'s `_flush_decisions`, keyed off `state["design_
id"]`/`state["persisted_decision_count"]`, and fires only on a
REDESIGN_DECISION transition -- this module never reaches REDESIGN_
DECISION itself (see "SCOPE" above), so it never triggers a flush directly.
What it DOES do is return, for the best candidate found, the exact
`advance_design_loop_step`-produced state dict that candidate's drive
built -- carrying `design_id`/`persisted_decision_count` through unchanged,
and with that candidate's ANALYSIS/SIMULATION/OPTIMIZATION `LoopDecision`s
already appended to `decisions`. When the engineer later continues THAT
state through VERIFICATION -> MEASUREMENT -> CORRELATION -> REDESIGN_
DECISION by calling `advance_design_loop_step` themselves (this module's
own scope ends at OPTIMIZATION -- see "SCOPE"), the existing flush picks
up every decision this module recorded for the winning candidate, exactly
as if an engineer had typed them in by hand one call at a time. Driving at
the design_loop layer instead would have produced a bare `DesignLoopState.
to_dict()` with no `design_id` at all -- not feedable back into `advance_
design_loop_step` (which requires one), and so not persistable at any
future flush boundary. This also means `state` passed into this module
MUST already be tooling-shaped (from `start_new_design_loop` or a prior
`advance_design_loop_step` call) -- `_validate_state_shape` below checks
for exactly this and raises `SolverError` immediately, not a confusing
failure three candidates into a batch, if it is not.

Losing (non-best) candidates' states are deliberately NOT returned or kept
-- see "RESULT SHAPE" below for why, and the size cost of doing otherwise.

------------------------------------------------------------------------
SCORING: `score_specs` NAMES WHICH STEPS TO SCORE, AGAINST WHAT, AND HOW TO
READ THE ACTUAL VALUE OUT OF THAT STEP'S RAW RESULT.

`success_score(step, target, actual_value, actual_unit, note=None)`
(designs/success_score.py) needs a target (this module never invents one
-- it must already be a `designs.requirement_targets.propose_target`/
`confirm_target` output, `PROPOSED` or `CONFIRMED`) and a plain
`actual_value`/`actual_unit` pair. But `orchestration.design_loop`'s own
step handlers each return a small, DIFFERENT dict shape (ANALYSIS:
`{"resonant_frequency_hz": ...}`; SIMULATION: `{"gain_dbi": ...,
"impedance": {...}, "pattern": [...], ...}`; OPTIMIZATION: `{"achieved_
frequency_hz": ...}`, among other fields) -- something has to say which
key of which step's result is the number being scored, and in what unit.
`_DEFAULT_SCORE_FIELDS` below is that lookup (`resonant_frequency_hz`/Hz
for ANALYSIS, `gain_dbi`/dBi for SIMULATION, `achieved_frequency_hz`/Hz
for OPTIMIZATION), built at import time from `orchestration/
score_fields.py`'s `SCORE_FIELD_SOURCES` -- the single source of truth
this module and `orchestration/lab_test_plan.py` both derive their own
lookup shape from (issue #102; that module needs the same facts grouped
by physical quantity kind instead of by step, so it builds a differently-
shaped index from the identical triples rather than this module's flat
one). See `orchestration/score_fields.py`'s own docstring for why this is
mechanical wiring knowledge fixed by those functions' own documented
output shapes (rf_tools/calculations.py, simulation/nec2pp.py,
optimization/rf_objectives.py), not an RF judgment call, and for why it is
kept separate from `orchestration/tooling.py`'s own `_STEP_TO_TOOL_NAME`
despite the overlapping step keys. A caller wanting a DIFFERENT field
scored (e.g. SIMULATION's `average_power_gain_linear` instead of
`gain_dbi`) overrides `result_field` in that step's `score_specs` entry,
but then MUST also supply an explicit `unit` -- this module has no basis
for guessing the unit of an arbitrary overridden field, matching designs/
success_score.py's own "refuse rather than guess a unit conversion" rule
exactly (see that module's "UNIT HANDLING" section); `_resolve_score_field`
below enforces this and raises `SolverError` naming the problem if
violated.

A step with no `score_specs` entry is still DRIVEN (its `LoopDecision` is
recorded, exactly as if scored) but never scored -- its trail entry
carries `"score": None`. This lets a caller drive all three steps while
scoring only, say, OPTIMIZATION's frequency target, without inventing a
target for a step nobody stated a requirement for.

------------------------------------------------------------------------
STOPPING RULES -- the three this ticket names, plus two structural halts.

  - `"target_satisfaction"`: the first candidate whose `overall_score_
    percent` (design question 3) reaches `target_satisfaction_threshold`
    (default 100.0, caller-overridable) ends the search immediately.
  - `"score_plateau"`: see design question 2.
  - `"evaluation_budget"`: `evaluation_budget` (default: every supplied
    candidate, i.e. `len(candidates)`; if given, capped at `len(candidates)`
    -- this module never asks the caller for more candidates than they
    handed it) is exhausted with neither of the above having fired.
  - `"gated_step_pending_approval"`: the state handed in is already
    sitting at ARCHITECTURE, MEASUREMENT, or REDESIGN_DECISION -- see "THE
    NON-NEGOTIABLE CONSTRAINT" above. Zero candidates are evaluated.
  - `"out_of_scope_step"`: the state handed in sits at a step this module
    was never asked to drive and which is NOT gated either (VERIFICATION,
    CORRELATION, or REQUIREMENTS) -- e.g. a caller resuming a loop that
    has already moved past OPTIMIZATION on its own. Honestly distinguished
    from a gated halt: nothing is blocking approval here, this module
    simply has no behavior for that step. Zero candidates are evaluated.
  - `"loop_completed"`: `state["completed"]` is already `True` (the loop
    already reached `REDESIGN_DECISION` -> `next_action="accept_design"`)
    -- there is nothing left to search. Zero candidates are evaluated.

------------------------------------------------------------------------
"VISIBLE AS IT IS EVALUATED, NOT ONLY AT THE END": LOGGING PLUS AN ORDERED
TRAIL, NOT A COLLAPSED FINAL SUMMARY.

This project has no long-running server process and no streaming tool
transport (see orchestration/design_loop.py's own "STATE DESIGN" section)
-- an agent/MCP tool call is one request, one JSON response, so nothing
can literally stream partial results mid-call. Within that real
constraint, this module still makes every candidate's score visible AS
COMPUTED, not only in a final collapsed summary, two ways: (1) `logging`
(`logging.getLogger("orchestration.solver")`, INFO level) emits one record
the moment each scoreable step's score is computed and one when each
candidate finishes -- a caller tailing logs (or a test using `caplog`)
observes scores in real evaluation order, before the tool call itself
returns; (2) the returned `trail` is an ORDERED list, one entry per
candidate in the order evaluated, each carrying its OWN full per-step
score trail -- never collapsed to just the winning candidate's number, so
a reader inspecting the response after the fact still sees every attempt's
scores, not merely the final "best". Rejected: returning only the winning
candidate's score with no trail. Rejected because it throws away the exact
"how did the search get here" evidence this ticket's acceptance criteria
name explicitly ("each score visible... rather than only at the end").

------------------------------------------------------------------------
RESULT SHAPE (see `run_candidate_search`'s own docstring for the field-by-
field contract). One structural note up front: `best_candidate_state` --
the ONE candidate's tooling-shaped state dict returned in full, to be
handed straight back into `advance_design_loop_step` by whoever continues
this design -- is populated only for the best-scoring, non-failed
candidate, never for every candidate. Returning every candidate's full
state (each carrying its own growing `decisions` list, including
SIMULATION's `pattern`/`impedance` sub-dicts) would multiply the response
size by the batch length for no benefit: only one candidate's parameters
can honestly continue as "the" design going forward, and every candidate's
SCORE (not its full state) is already in `trail`.

------------------------------------------------------------------------
OPTIONAL `design_id`: SEEDING FROM A DESIGN'S OWN PRIOR RESULTS -- issue
#87's "cross-run learning" follow-up to this ticket's own user story #21
("a design's score history across iterations, so I can see whether
iterating is still improving anything"), left unimplemented when this
module was first built: every call used to start `best_so_far` (design
question 2) empty, so a caller re-running the same design later got no
benefit from what an earlier call (or an earlier session) had already
found. `run_candidate_search(..., design_id=<int>)` closes that gap: it
reads `design_id`'s own best-ever recorded score, per scoreable step (via
a new READ-ONLY query, `designs.db.read_engineering_results_for_scoring`),
and seeds the plateau-window baseline with it before evaluating any NEW
candidate -- see `_prior_best_from_design`'s own docstring for the full
mechanics, including the one honestly-documented limitation in how it
infers "which prior iteration" from recording order alone. Two properties
worth stating up front, both already true of the rest of this module: (1)
this is READ-ONLY -- it opens a connection only to SELECT, never to write,
same discipline "THE NON-NEGOTIABLE CONSTRAINT" above already holds this
whole module to for gates; (2) it never touches GATED_STEPS or any
approval machinery -- it is pure historical arithmetic over already-
recorded numbers, exactly like every OTHER score this module computes.
"""

from __future__ import annotations

import logging
from typing import Any

import designs.db as designs_db
from designs.requirement_targets import TargetStatus
from designs.success_score import success_score

from .design_loop import GATED_STEPS, DesignStep
from .score_fields import SCORE_FIELD_SOURCES
from .tooling import advance_design_loop_step

_logger = logging.getLogger(__name__)

CALCULATED = "CALCULATED"

# The exact and only span this module ever drives -- see this module's
# docstring, "SCOPE". Order matters: _steps_from below relies on it.
_ORDERED_UNGATED_SPAN: tuple[DesignStep, ...] = (
    DesignStep.ANALYSIS,
    DesignStep.SIMULATION,
    DesignStep.OPTIMIZATION,
)

# The design_loop.py step handlers' own required step_input fields
# (design_loop.py's module docstring and issue #95's own "WHAT YOU ARE
# BUILDING ON" section both state these) -- duplicated, not imported, so
# this module can build a step_input from a flat candidate dict without
# reaching into design_loop.py's private _handle_*/_require_fields
# internals. A missing field here simply means the built step_input omits
# it, and the REAL handler's own _require_fields raises
# DesignLoopValidationError naming it when advance_design_loop_step runs
# -- this module performs no validation of its own on these.
_REQUIRED_FIELDS: dict[DesignStep, tuple[str, ...]] = {
    DesignStep.ANALYSIS: ("eps_r", "w_m", "h_m", "l_m"),
    # reference_impedance_ohms (issue #101): _handle_simulation now derives
    # VSWR/return loss from the feed-point impedance it already computes,
    # and requires its caller to state the reference impedance explicitly
    # -- never silently assumed to be 50 ohms. A candidate driving
    # SIMULATION through this module must carry it the same way it must
    # carry geometry/frequency_hz.
    DesignStep.SIMULATION: ("geometry", "frequency_hz", "reference_impedance_ohms"),
    DesignStep.OPTIMIZATION: (
        "eps_r",
        "w_m",
        "h_m",
        "target_frequency_hz",
        "length_lower_m",
        "length_upper_m",
    ),
}
_OPTIONAL_FIELDS: dict[DesignStep, tuple[str, ...]] = {
    DesignStep.SIMULATION: ("timeout_s", "executable", "workdir"),
    DesignStep.OPTIMIZATION: ("method", "n_evaluations"),
}

# Which raw result field a scoreable step's numeric value lives at, and its
# unit -- see this module's docstring, "SCORING". Derived from
# orchestration/score_fields.py's SCORE_FIELD_SOURCES (issue #102's single
# source of truth), not restated here -- see that module's own docstring.
_DEFAULT_SCORE_FIELDS: dict[DesignStep, tuple[str, str]] = {
    source.step: (source.result_field, source.unit) for source in SCORE_FIELD_SOURCES
}

# Which engineering_results.tool_name a scoreable step's own PAST rows are
# recorded under -- the same lookup orchestration/tooling.py's own
# _STEP_TO_TOOL_NAME keeps for ANALYSIS/SIMULATION/OPTIMIZATION,
# duplicated rather than imported (same convention _DEFAULT_SCORE_FIELDS
# above already follows). Used only by _prior_best_from_design, below, for
# the optional design_id-seeding feature (issue #87's cross-run-learning
# follow-up) -- nothing else in this module reads engineering_results.
_STEP_TOOL_NAME: dict[DesignStep, str] = {
    DesignStep.ANALYSIS: "patch_resonant_frequency_hz",
    DesignStep.SIMULATION: "run_nec2_simulation",
    DesignStep.OPTIMIZATION: "optimize_patch_length_for_target_frequency",
}

_REQUIRED_STATE_KEYS = (
    "design_id",
    "design_key",
    "loop_id",
    "iteration",
    "current_step",
    "completed",
    "decisions",
)


class SolverError(ValueError):
    """Raised by `run_candidate_search` for a malformed CALL -- a bad
    `state` shape (not a tooling-layer state dict; see this module's
    docstring's "WHICH LAYER" section), an empty/malformed `candidates` or
    `score_specs`, or an out-of-range `evaluation_budget`/`plateau_window`/
    `plateau_epsilon`. Distinct from a single candidate's own drive
    failing (recorded on that candidate's trail entry, never raised -- see
    this module's docstring, design question 4): a `SolverError` means the
    CALL itself cannot proceed at all, before any candidate is evaluated,
    the same distinction `designs.success_score.SuccessScoreError` and
    `orchestration.design_loop.DesignLoopValidationError` already draw
    between "this input is unusable" and a step's own runtime outcome. A
    `ValueError` subclass, matching this project's established convention
    for a domain-specific error naming exactly what's wrong."""


def _steps_from(current_step: DesignStep) -> list[DesignStep] | None:
    """The suffix of `_ORDERED_UNGATED_SPAN` starting at `current_step`,
    or `None` if `current_step` is not in that span at all (a gated step,
    or an ungated-but-out-of-scope one -- VERIFICATION/CORRELATION/
    REQUIREMENTS). `None` is exactly the signal `run_candidate_search`
    uses to halt before evaluating any candidate."""
    if current_step not in _ORDERED_UNGATED_SPAN:
        return None
    idx = _ORDERED_UNGATED_SPAN.index(current_step)
    return list(_ORDERED_UNGATED_SPAN[idx:])


def _build_step_input(step: DesignStep, candidate: dict[str, Any]) -> dict[str, Any]:
    """Project `candidate`'s fields down to exactly the ones `step`'s real
    handler reads (required + optional) -- a missing required field is
    left out, not filled in or defaulted, so the real handler's own
    validation is what raises for it (see this module's docstring)."""
    fields = (*_REQUIRED_FIELDS[step], *_OPTIONAL_FIELDS.get(step, ()))
    return {field: candidate[field] for field in fields if field in candidate}


def _resolve_score_field(step: DesignStep, spec: dict[str, Any]) -> tuple[str, str]:
    """Which raw-result field to score for `step`, and its unit -- see
    this module's docstring, "SCORING". Raises `SolverError` if the caller
    overrode `result_field` away from this module's own documented default
    without also stating an explicit `unit` for it."""
    default_field, default_unit = _DEFAULT_SCORE_FIELDS[step]
    result_field = spec.get("result_field", default_field)
    if result_field == default_field:
        unit = spec.get("unit", default_unit)
    elif "unit" in spec:
        unit = spec["unit"]
    else:
        raise SolverError(
            f"score_specs[{step.value!r}] overrides result_field to "
            f"{result_field!r} but supplies no explicit 'unit' -- this module "
            f"only knows the unit ({default_unit!r}) of its own default field "
            f"({default_field!r}) for this step; a different field's unit "
            "must be stated explicitly, never guessed (see designs/"
            "success_score.py's own unit-mismatch-refusal precedent)."
        )
    return result_field, unit


def _validate_state_shape(state: Any) -> None:
    if not isinstance(state, dict):
        raise SolverError(f"state must be a dict, got {type(state).__name__}")
    missing = [key for key in _REQUIRED_STATE_KEYS if key not in state]
    if missing:
        raise SolverError(
            f"state is missing required key(s) {missing} -- run_candidate_search "
            "requires a design-loop state dict returned by "
            "orchestration.tooling.start_new_design_loop or advance_design_loop_step "
            "(NOT orchestration.design_loop.start_design_loop's bare "
            "DesignLoopState.to_dict(), which has no design_id) -- this module drives "
            "the TOOLING layer specifically so a winning candidate's decisions are "
            "ready for the existing REDESIGN_DECISION flush; see this module's "
            "docstring, 'WHICH LAYER THIS MODULE DRIVES'."
        )
    if state.get("design_id") is None:
        raise SolverError(
            "state['design_id'] is None -- run_candidate_search requires a real "
            "design_id (from orchestration.tooling.start_new_design_loop), so a "
            "winning candidate's state can be persisted at the next REDESIGN_"
            "DECISION flush."
        )


def _validate_candidates(candidates: Any) -> list[dict[str, Any]]:
    if not isinstance(candidates, list) or not candidates:
        raise SolverError(f"candidates must be a non-empty list of dicts, got {candidates!r}")
    for i, candidate in enumerate(candidates):
        if not isinstance(candidate, dict):
            raise SolverError(
                f"candidates[{i}] must be a dict of step_input fields, got "
                f"{type(candidate).__name__}"
            )
    return candidates


def _validate_score_specs(score_specs: Any) -> dict[str, dict[str, Any]]:
    drivable = {step.value for step in _ORDERED_UNGATED_SPAN}
    if not isinstance(score_specs, dict) or not score_specs:
        raise SolverError(
            "score_specs must be a non-empty dict keyed by step name "
            f"({sorted(drivable)}), each value carrying at least a 'target' "
            "(a designs.requirement_targets.propose_target/confirm_target output)"
        )
    for step_name, spec in score_specs.items():
        if step_name not in drivable:
            raise SolverError(
                f"score_specs key {step_name!r} is not one of this solver's "
                f"drivable steps {sorted(drivable)}"
            )
        if not isinstance(spec, dict) or "target" not in spec:
            raise SolverError(
                f"score_specs[{step_name!r}] must be a dict carrying at least a 'target' key"
            )
        target = spec["target"]
        target_status = target.get("target_status") if isinstance(target, dict) else None
        if target_status not in (TargetStatus.PROPOSED.value, TargetStatus.CONFIRMED.value):
            raise SolverError(
                f"score_specs[{step_name!r}]['target'] must be a "
                "designs.requirement_targets target dict with target_status "
                f"{TargetStatus.PROPOSED.value!r} or {TargetStatus.CONFIRMED.value!r} "
                f"(an 'UNSCOREABLE' target has no number to score against) -- got "
                f"target_status={target_status!r}"
            )
        # Validated eagerly, here, rather than lazily inside _score_step:
        # an overridden result_field with no explicit unit is a CALL-level
        # configuration mistake (it would fail identically for every
        # candidate), not a per-candidate data problem -- see SolverError's
        # own docstring for that distinction. Raising it up front means the
        # caller learns about it before spending any evaluation_budget, not
        # buried inside candidate[0]'s "failed" trail entry.
        _resolve_score_field(DesignStep(step_name), spec)
    return score_specs


def _score_step(
    step: DesignStep,
    spec: dict[str, Any],
    decision_result: dict[str, Any],
    note: str | None,
) -> dict[str, Any]:
    """Score one driven step's raw result against `spec["target"]`. Raises
    `SuccessScoreError` (from `designs.success_score.success_score`) for
    everything that function itself refuses -- including a missing/non-
    numeric value at the resolved `result_field` -- letting that module's
    own validation do the work rather than duplicating it here."""
    result_field, unit = _resolve_score_field(step, spec)
    actual_value = decision_result.get(result_field)
    return success_score(
        step=step.value,
        target=spec["target"],
        actual_value=actual_value,
        actual_unit=unit,
        note=note,
    )


def _drive_candidate(
    base_state: dict[str, Any],
    steps_to_drive: list[DesignStep],
    candidate: dict[str, Any],
    score_specs: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Drive ONE candidate through `steps_to_drive`, forked fresh from
    `base_state` (never chained from a previous candidate's result -- see
    this module's docstring's "DESIGN QUESTION 1"). Every step advance goes
    through `orchestration.tooling.advance_design_loop_step` -- the real
    design-loop step functions, unmodified, called with `approval=None`
    (correct: every step in `steps_to_drive` is, by construction, outside
    GATED_STEPS).

    NEVER RAISES: a step failure (the loop's own step advance raising, or
    that step's own `score_specs` extraction/scoring raising) stops driving
    THIS candidate at that step and is reported back in the return value
    (`failed_at_step`/`error`) rather than propagated -- see this module's
    docstring, "DESIGN QUESTION 4". Critically, `steps` still carries every
    step that succeeded BEFORE the failure, each with its own already-
    computed score: a candidate that fails at OPTIMIZATION after a clean
    ANALYSIS and SIMULATION does not lose those two steps' visibility just
    because the run, as a whole, could not be completed -- "visible as it
    is evaluated" (this module's docstring) applies to a failed candidate's
    partial progress too, not only to a fully-evaluated one.

    Returns `{"state": <the last successfully-advanced tooling-shaped state
    dict -- base_state itself if the very first step failed>, "steps":
    [...], "failed_at_step": <step name or None>, "error": <message or
    None>}`. `state` reflects having driven every step THAT SUCCEEDED, for
    THIS candidate only -- `run_candidate_search` only ever treats it as a
    candidate for `best_candidate_state` when `failed_at_step` is `None`
    (a partially-driven state is not a coherent point to hand back to the
    caller as "the" continuable design)."""
    working_state = base_state
    note = candidate.get("note")
    step_trail: list[dict[str, Any]] = []
    failed_at_step: str | None = None
    error_message: str | None = None

    for step in steps_to_drive:
        step_input = _build_step_input(step, candidate)
        try:
            working_state = advance_design_loop_step(working_state, step_input, approval=None)
        except Exception as exc:
            failed_at_step = step.value
            error_message = str(exc)
            break

        decision = working_state["decisions"][-1]
        spec = score_specs.get(step.value)
        score: dict[str, Any] | None = None
        if spec is not None:
            try:
                score = _score_step(step, spec, decision["result"], note)
            except Exception as exc:
                failed_at_step = step.value
                error_message = str(exc)
                # The step itself DID advance (working_state already
                # reflects it) -- only scoring it failed. Record the raw
                # result (score=None) before stopping, rather than
                # silently dropping evidence that the step actually ran.
                step_trail.append(
                    {
                        "step": step.value,
                        "decision_provenance": decision["provenance"],
                        "raw_result": decision["result"],
                        "score": None,
                    }
                )
                break
            _logger.info(
                "solver: step scored step=%s score_percent=%.2f target_met=%s",
                step.value,
                score["score_percent"],
                score["target_met"],
            )

        step_trail.append(
            {
                "step": step.value,
                "decision_provenance": decision["provenance"],
                "raw_result": decision["result"],
                "score": score,
            }
        )

    return {
        "state": working_state,
        "steps": step_trail,
        "failed_at_step": failed_at_step,
        "error": error_message,
    }


def _overall_score(step_trail: list[dict[str, Any]]) -> tuple[float | None, bool | None]:
    """`(overall_score_percent, all_targets_met)` for one candidate's
    `step_trail` -- see this module's docstring's "DESIGN QUESTION 3" for
    why `overall_score_percent` is the MINIMUM of scored steps'
    `score_percent`. `all_targets_met` is `True` only if every scored
    step's `target_met` is exactly `True` (a `None` target_met -- an
    EQUALS target with no stated tolerance, see `designs.success_score.
    score_point_target` -- is treated as "not decisively met", not
    silently ignored). Both are `None` if `step_trail` has no scored step
    at all."""
    scored = [entry["score"] for entry in step_trail if entry["score"] is not None]
    if not scored:
        return None, None
    overall = min(score["score_percent"] for score in scored)
    all_met = all(score["target_met"] is True for score in scored)
    return overall, all_met


def _prior_best_from_design(
    design_id: int,
    scoreable_steps: list[DesignStep],
    score_specs: dict[str, dict[str, Any]],
) -> tuple[float | None, int | None]:
    """The best `overall_score_percent` (design question 3's own
    worst_of_scored_steps rule, reused unchanged) that `design_id` has
    EVER already recorded on `scoreable_steps`, and which of its prior
    iterations achieved it -- read-only, via `designs.db.
    read_engineering_results_for_scoring`; this function issues no write
    of any kind (see that function's own docstring for the read/write
    split it preserves). `run_candidate_search`'s optional `design_id`
    parameter (issue #87's cross-run-learning follow-up to issue #95's own
    user story #21, "a design's score history across iterations") calls
    this once, before evaluating any NEW candidate, to seed the plateau-
    window baseline (design question 2) from this design's OWN past
    results -- so a fresh call does not have to re-discover, at the cost
    of a fresh evaluation_budget, a local optimum a PRIOR call (or a prior
    session) already found for the exact same design.

    HOW "WHICH PRIOR ITERATION" IS DETERMINED, HONESTLY: engineering_results
    rows carry no iteration number of their own -- design_loop.py's
    LoopDecision.iteration exists only in memory; orchestration/tooling.py's
    flush never persists it onto the row it writes (a pre-existing gap,
    not something this function fixes or needs fixed). This function
    infers one instead, from recording order alone: within one design's
    history, a row is only ever written by orchestration/tooling.py's
    REDESIGN_DECISION flush (docs/adr/0011), and that flush fires at most
    once per design-loop iteration, writing at most one row per step per
    firing (the loop's own linear state machine visits ANALYSIS/
    SIMULATION/OPTIMIZATION exactly once each before REDESIGN_DECISION can
    even be reached) -- so, for a design_id whose engineering_results were
    written EXCLUSIVELY by that flush, the Nth-recorded row for a given
    step's tool_name really is that design's Nth iteration to reach that
    step. A design_id that ALSO received a row from some other caller
    (e.g. record_engineering_result called directly, outside any design
    loop) would make this numbering wrong in a way nothing here can
    detect -- accepted as a known limitation, not solved, the same
    "accepted rather than solved" honesty LoopDecision.iteration's own
    docstring already applies to a different gap in the same area.

    Combining PER-STEP bests into one prior_best_score/prior_iteration
    pair (rather than reporting a best per step, which would leave
    "seed the plateau baseline" with no single number to seed from):
    treat each recording ordinal `i` as if it were one historical
    candidate's own step_trail (exactly design question 3's shape), taking
    the SAME worst_of_scored_steps rule across whichever scoreable steps
    have a value recorded at that ordinal, then keep the best (highest)
    such per-ordinal overall across all ordinals -- mirroring, at the
    granularity of "one design's whole history" rather than "one call's
    candidate batch", precisely how `_overall_score` already turns one
    candidate's own steps into one number.

    Returns `(None, None)` if `design_id` has no prior row for ANY step in
    `scoreable_steps`, if `scoreable_steps` is empty, or if every prior row
    found fails to score (e.g. an old row missing the scored field
    entirely -- logged and skipped, never raised: a corrupt or unrelated
    historical row must not block evaluating this call's own NEW
    candidates).
    """
    if not scoreable_steps:
        return None, None

    tool_names = [_STEP_TOOL_NAME[step] for step in scoreable_steps]
    conn = designs_db.get_connection()
    try:
        grouped = designs_db.read_engineering_results_for_scoring(conn, design_id, tool_names)
    finally:
        conn.close()

    per_step_scores: dict[DesignStep, list[dict[str, Any] | None]] = {}
    for step in scoreable_steps:
        spec = score_specs[step.value]
        rows = grouped.get(_STEP_TOOL_NAME[step], [])
        scores: list[dict[str, Any] | None] = []
        for row in rows:
            try:
                scores.append(_score_step(step, spec, row.get("value") or {}, note=None))
            except Exception as exc:
                _logger.info(
                    "solver: design_id=%s prior engineering_results id=%s for step=%s "
                    "could not be scored, skipped for prior-best seeding: %s",
                    design_id,
                    row.get("id"),
                    step.value,
                    exc,
                )
                scores.append(None)
        per_step_scores[step] = scores

    n_common = min(len(scores) for scores in per_step_scores.values())
    best_overall: float | None = None
    best_iteration: int | None = None
    for i in range(n_common):
        step_trail = [{"score": per_step_scores[step][i]} for step in scoreable_steps]
        if any(entry["score"] is None for entry in step_trail):
            # Not every scored step has a usable value at this ordinal --
            # skipped rather than computing a partial "worst" that would
            # silently ignore a step that failed to score at this position
            # (same reasoning _overall_score's own docstring gives for
            # treating a missing target_met as "not decisively met").
            continue
        overall, _ = _overall_score(step_trail)
        if overall is None:
            continue
        if best_overall is None or overall > best_overall:
            best_overall = overall
            best_iteration = i + 1  # 1-based, matching this module's other ordinals

    return best_overall, best_iteration


def run_candidate_search(
    state: dict[str, Any],
    candidates: list[dict[str, Any]],
    score_specs: dict[str, dict[str, Any]],
    evaluation_budget: int | None = None,
    plateau_window: int = 5,
    plateau_epsilon: float = 0.5,
    target_satisfaction_threshold: float = 100.0,
    design_id: int | None = None,
) -> dict[str, Any]:
    """Drive a batch of LLM-proposed candidates through a design loop's
    ungated ANALYSIS/SIMULATION/OPTIMIZATION span, candidate after
    candidate, scoring each as it goes, stopping on target satisfaction,
    score plateau, or the evaluation budget -- see this module's docstring
    for the full design (every design question issue #95 posed is answered
    there, at length, with what was considered and rejected).

    Arguments:
      - `state`: a design-loop state dict from `orchestration.tooling.
        start_new_design_loop` or a prior `advance_design_loop_step` call,
        already positioned past ARCHITECTURE (inside an approved
        architecture). `SolverError` if it is not tooling-shaped (see
        "WHICH LAYER THIS MODULE DRIVES").
      - `candidates`: a non-empty list of plain dicts, each the union of
        whatever `_REQUIRED_FIELDS`/`_OPTIONAL_FIELDS` the steps actually
        driven need (e.g. `eps_r`/`w_m`/`h_m`/`l_m` for ANALYSIS,
        `geometry`/`frequency_hz`/`reference_impedance_ohms` for
        SIMULATION -- the last one stated explicitly per candidate, never
        assumed to be 50 ohms (issue #101) -- plus `target_frequency_
        hz`/`length_lower_m`/`length_upper_m` for OPTIMIZATION). An
        optional `"note"` key, if present, is forwarded to every scored
        step's `success_score(note=...)` call for that candidate.
      - `score_specs`: a non-empty dict keyed by step name (`"analysis"`/
        `"simulation"`/`"optimization"`), each value `{"target": <a
        designs.requirement_targets PROPOSED/CONFIRMED target dict>,
        "result_field": <optional str>, "unit": <optional str, required
        if result_field is overridden>}` -- see "SCORING" in this module's
        docstring. A step with no entry here is still driven, never
        scored.
      - `evaluation_budget`: max candidates actually evaluated; defaults
        to `len(candidates)` (try every supplied one), capped at
        `len(candidates)` if given larger.
      - `plateau_window` / `plateau_epsilon`: see "DESIGN QUESTION 2".
        Defaults 5 / 0.5 (percentage points).
      - `target_satisfaction_threshold`: an `overall_score_percent` (see
        "DESIGN QUESTION 3") at or above this (default 100.0) ends the
        search immediately on that candidate.
      - `design_id`: optional (default `None`, meaning no seeding at all --
        no database is touched). When supplied, `run_candidate_search`
        reads this design's own PRIOR recorded scores for whichever steps
        in `score_specs` it would actually drive this call (via
        `designs.db.read_engineering_results_for_scoring`, read-only --
        see `_prior_best_from_design`) and seeds the plateau-window
        baseline (design question 2) with the best one found, before
        evaluating any NEW candidate. This lets a caller re-run the same
        design later without re-spending evaluation_budget rediscovering a
        local optimum a PRIOR call (or session) already found -- issue
        #87's "cross-run learning" follow-up to issue #95's own user story
        #21. Independent of `state["design_id"]`: nothing here requires
        the two to match (a caller MAY seed from a different, related
        design's history -- see this module's docstring for why that
        flexibility is deliberate), and `state["design_id"]` is never
        substituted in when this argument is omitted. Never affects
        `best_candidate_index`/`best_candidate_overall_score_percent`/
        `best_candidate_state` -- those three remain scoped to THIS call's
        own newly-evaluated candidates only, since a historical score has
        no matching NEW state to hand back.

    Raises `SolverError` for a malformed call (bad `state`/`candidates`/
    `score_specs`/`design_id` shape, or an out-of-range budget/plateau
    parameter) -- before any candidate is evaluated. Never raises for a
    single candidate's own drive failing (see "DESIGN QUESTION 4") -- that
    is recorded on the candidate's own trail entry instead. NOT covered by
    that `SolverError` guarantee: when `design_id` is supplied, a hard
    failure of `designs_db.get_connection()`/`designs_db.
    read_engineering_results_for_scoring()` itself (e.g. the database being
    unreachable) propagates as whatever exception that call raises,
    uncaught here -- `_prior_best_from_design` only catches a single prior
    ROW's own scoring failure (see its docstring), never a connection-level
    one. A documented, disclosed choice, not a defect.

    Returns a dict:
      - `provenance`: always `"CALCULATED"` -- every score and stopping
        decision here is deterministic arithmetic over already-recorded
        numbers (`designs.success_score`'s own reasoning applies
        identically).
      - `loop_id` / `iteration` / `design_id`: copied from `state`, for a
        reader who has only this result at hand.
      - `convergence_rule`: always `"worst_of_scored_steps"` -- see
        "DESIGN QUESTION 3".
      - `target_satisfaction_threshold` / `plateau_window` /
        `plateau_epsilon`: the resolved values actually used (including
        defaults), so a reader never has to guess what was applied.
      - `evaluation_budget`: the resolved (possibly capped) budget.
      - `candidates_requested` / `candidates_evaluated`: batch size vs.
        how many were actually attempted before stopping.
      - `stop_reason`: one of `"target_satisfaction"`, `"score_plateau"`,
        `"evaluation_budget"`, `"gated_step_pending_approval"`,
        `"out_of_scope_step"`, `"loop_completed"` -- see "STOPPING RULES".
      - `stop_detail`: a human-readable sentence naming exactly why/where.
      - `pending_approval`: `state`'s own, untouched `pending_approval`
        dict (from `orchestration.design_loop`'s `_pending_approval_for`)
        when `stop_reason="gated_step_pending_approval"`, else `None`.
      - `trail`: an ORDERED list, one entry per candidate ACTUALLY
        evaluated, each `{"candidate_index", "candidate", "status"
        ("evaluated"|"failed"), "error", "failed_at_step", "steps" (that
        candidate's own per-step trail -- "step"/"decision_provenance"/
        "raw_result"/"score"), "overall_score_percent",
        "all_targets_met"}`.
      - `best_candidate_index` / `best_candidate_overall_score_percent`:
        the best-scoring, non-failed candidate found (ties keep the
        earliest), or both `None` if none scored.
      - `best_candidate_state`: that ONE candidate's tooling-shaped state
        dict, ready to hand straight back into `advance_design_loop_step`
        to continue the design -- or `None`. See "RESULT SHAPE" in this
        module's docstring for why only the best candidate's state is
        returned in full.
      - `prior_best_score` / `prior_iteration`: `None`/`None` when
        `design_id` was not supplied, or when it was but nothing prior was
        found to score. Otherwise the best `overall_score_percent` this
        `design_id` had ALREADY recorded (across every prior iteration,
        not just this call) on whichever `score_specs` steps this call
        would drive, and which prior iteration achieved it -- see
        `_prior_best_from_design`'s own docstring for exactly how "prior
        iteration" is determined (and its one honestly-documented
        limitation). This value is also what seeded the plateau-window
        baseline (design question 2) before any NEW candidate ran.
    """
    _validate_state_shape(state)
    candidates = _validate_candidates(candidates)
    score_specs = _validate_score_specs(score_specs)
    if plateau_window < 1:
        raise SolverError(f"plateau_window must be >= 1, got {plateau_window!r}")
    if plateau_epsilon < 0:
        raise SolverError(f"plateau_epsilon must be >= 0, got {plateau_epsilon!r}")
    if evaluation_budget is not None and evaluation_budget < 1:
        raise SolverError(f"evaluation_budget must be >= 1, got {evaluation_budget!r}")
    if design_id is not None and not isinstance(design_id, int):
        raise SolverError(f"design_id must be an int or None, got {type(design_id).__name__}")

    report: dict[str, Any] = {
        "provenance": CALCULATED,
        "loop_id": state.get("loop_id"),
        "iteration": state.get("iteration"),
        "design_id": state.get("design_id"),
        "convergence_rule": "worst_of_scored_steps",
        "target_satisfaction_threshold": target_satisfaction_threshold,
        "plateau_window": plateau_window,
        "plateau_epsilon": plateau_epsilon,
        "candidates_requested": len(candidates),
        "candidates_evaluated": 0,
        "evaluation_budget": 0,
        "trail": [],
        "best_candidate_index": None,
        "best_candidate_overall_score_percent": None,
        "best_candidate_state": None,
        "pending_approval": None,
        "prior_best_score": None,
        "prior_iteration": None,
    }

    if state.get("completed"):
        report["stop_reason"] = "loop_completed"
        report["stop_detail"] = (
            "this design loop has already completed (REDESIGN_DECISION -> "
            "next_action='accept_design') -- there is nothing left to search"
        )
        return report

    current_step_value = state.get("current_step")
    try:
        current_step = DesignStep(current_step_value)
    except ValueError:
        raise SolverError(
            f"state['current_step'] is not a recognized DesignStep: {current_step_value!r}"
        ) from None

    steps_to_drive = _steps_from(current_step)
    if steps_to_drive is None:
        if current_step in GATED_STEPS:
            report["stop_reason"] = "gated_step_pending_approval"
            report["stop_detail"] = (
                f"the design loop is currently at {current_step.value.upper()}, a gated "
                "step (orchestration.design_loop.GATED_STEPS) -- this solver never "
                "constructs, forges, or bypasses an approval receipt; a human must "
                "grant one via orchestration.approval.request_loop_step_approval and "
                "advance past it with advance_design_loop_step before searching can "
                "resume. No candidate was evaluated."
            )
            report["pending_approval"] = state.get("pending_approval")
        else:
            report["stop_reason"] = "out_of_scope_step"
            report["stop_detail"] = (
                f"the design loop is currently at {current_step.value.upper()}, which is "
                "not gated but is outside this solver's driven span "
                f"({[s.value for s in _ORDERED_UNGATED_SPAN]}) -- see this module's "
                "docstring, 'SCOPE'. No candidate was evaluated."
            )
        return report

    relevant_step_names = {step.value for step in steps_to_drive}
    if not (set(score_specs) & relevant_step_names):
        raise SolverError(
            f"none of score_specs' step(s) ({sorted(score_specs)}) are among the "
            f"steps this call would actually drive ({sorted(relevant_step_names)}, "
            f"starting from current_step={current_step.value!r}) -- nothing would "
            "ever be scored"
        )

    effective_budget = (
        len(candidates) if evaluation_budget is None else min(evaluation_budget, len(candidates))
    )
    report["evaluation_budget"] = effective_budget

    best_so_far: list[float] = []
    if design_id is not None:
        scoreable_steps = [step for step in steps_to_drive if step.value in score_specs]
        prior_best_score, prior_iteration = _prior_best_from_design(
            design_id, scoreable_steps, score_specs
        )
        report["prior_best_score"] = prior_best_score
        report["prior_iteration"] = prior_iteration
        if prior_best_score is not None:
            # Seeds the plateau-window baseline (design question 2) with
            # this design's own best PRIOR result -- never touches
            # best_candidate_index/best_candidate_overall_score_percent/
            # best_candidate_state, which stay scoped to THIS call's own
            # newly-evaluated candidates (see this function's own
            # docstring's `design_id` paragraph).
            best_so_far.append(prior_best_score)

    stop_reason = "evaluation_budget"
    stop_detail: str | None = None

    for i in range(effective_budget):
        candidate = candidates[i]
        driven = _drive_candidate(state, steps_to_drive, candidate, score_specs)
        overall, all_met = _overall_score(driven["steps"])
        failed = driven["failed_at_step"] is not None

        entry: dict[str, Any] = {
            "candidate_index": i,
            "candidate": dict(candidate),
            "status": "failed" if failed else "evaluated",
            "error": driven["error"],
            "failed_at_step": driven["failed_at_step"],
            "steps": driven["steps"],
            "overall_score_percent": overall,
            "all_targets_met": all_met,
        }
        report["trail"].append(entry)
        report["candidates_evaluated"] += 1

        if failed:
            _logger.info(
                "solver: candidate %d failed at %s: %s",
                i,
                driven["failed_at_step"],
                driven["error"],
            )
            continue

        _logger.info(
            "solver: candidate %d evaluated overall_score_percent=%s all_targets_met=%s",
            i,
            overall,
            all_met,
        )

        if overall is None:
            continue

        improved = (
            report["best_candidate_overall_score_percent"] is None
            or overall > report["best_candidate_overall_score_percent"]
        )
        if improved:
            report["best_candidate_index"] = i
            report["best_candidate_overall_score_percent"] = overall
            report["best_candidate_state"] = driven["state"]
        best_so_far.append(report["best_candidate_overall_score_percent"])

        if overall >= target_satisfaction_threshold:
            stop_reason = "target_satisfaction"
            stop_detail = (
                f"candidate {i} reached overall_score_percent={overall:.2f} >= "
                f"target_satisfaction_threshold={target_satisfaction_threshold}"
            )
            break

        # Comparing the latest running-best to the value plateau_window
        # entries back needs plateau_window + 1 recorded snapshots (index
        # -1 and index -1-plateau_window must both exist) -- >= plateau_
        # window alone is an off-by-one that indexes before the list start.
        if len(best_so_far) >= plateau_window + 1:
            baseline = best_so_far[-1 - plateau_window]
            latest = best_so_far[-1]
            if latest - baseline <= plateau_epsilon:
                stop_reason = "score_plateau"
                stop_detail = (
                    f"no improvement exceeding plateau_epsilon={plateau_epsilon} "
                    f"percentage points in the running-best overall_score_percent "
                    f"over the last plateau_window={plateau_window} successfully-"
                    f"evaluated candidates (best went from {baseline:.2f}% to "
                    f"{latest:.2f}%)"
                )
                break
    else:
        stop_detail = (
            f"evaluated {report['candidates_evaluated']} of {effective_budget} budgeted "
            "candidates with no target satisfaction or score plateau"
        )

    report["stop_reason"] = stop_reason
    report["stop_detail"] = stop_detail
    return report
