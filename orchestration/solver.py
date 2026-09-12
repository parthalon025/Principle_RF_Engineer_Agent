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

WHAT A PLATEAU MEANS FOR THE CALLING AGENT'S NEXT MOVE: this module only
detects and reports a plateau (`stop_reason="score_plateau"`) -- it never
decides what happens next, and never re-enters itself between batches
(that would need a mechanism this module deliberately does not have; see
docs/design-loop-convergence-sequencing.md Sec.5a's SGDR/warm-restart
comparison). That operating convention lives in the prompt layer instead,
per ADR-0010: `prompts/principal_engineer.md`'s "Candidate-search
plateaus" section, and both tool-wrapper docstrings (`agent/main.py`,
`mcp_server/server.py`) for `run_candidate_search`, tell the calling agent
to treat a plateau stop as a cue to submit one more, deliberately
different batch before concluding this architecture's OPTIMIZATION is
exhausted -- not to read it the same way as `target_satisfaction` or
`evaluation_budget`. This module's own return value is unchanged by that
convention: `stop_reason`/`stop_detail` report the plateau exactly as
before, and nothing here gates, refuses, or automates the next batch.

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
step handlers each return a small, DIFFERENT dict shape depending on the
step AND, for SIMULATION, on the design family being driven (ANALYSIS:
`{"resonant_frequency_hz": ...}` for PATCH, `{"worst_absorption": ...}`
for ABSORBER; SIMULATION: `{"gain_dbi": ..., "impedance": {...}, ...}`
for a NEC2-driven patch, `{"worst_absorption": ..., "reflectance": [...],
...}` for a MEEP-driven absorber; OPTIMIZATION: `{"achieved_frequency_hz":
...}`, among other fields) -- something has to say which key of which
step's result is the number being scored, and in what unit.

ANALYSIS and OPTIMIZATION use `_DEFAULT_SCORE_FIELDS` for that (built at
import time from `orchestration/score_fields.py`'s `SCORE_FIELD_SOURCES`
-- the single source of truth this module and `orchestration/
lab_test_plan.py` both derive their own lookup shape from, issue #102;
that module needs the same facts grouped by physical quantity kind
instead of by step, so it builds a differently-shaped index from the
identical triples rather than this module's flat one). See
`orchestration/score_fields.py`'s own docstring for why this is
mechanical wiring knowledge fixed by those functions' own documented
output shapes (rf_tools/calculations.py, optimization/rf_objectives.py),
not an RF judgment call, and for why it is kept separate from
`orchestration/tooling.py`'s own `_STEP_TO_TOOL_NAME` despite the
overlapping step keys.

SIMULATION does NOT use that single global default (issue #249): a
patch's SIMULATION result and an absorber's carry no shared shape at all
-- `_default_score_field_for` instead reads the driven design family's OWN
`simulation_scored_field` declaration (`designs/design_families.py`),
which PATCH states as `gain_dbi`/dBi (`simulation/nec2pp.py`'s own parsed
peak gain, matching `_DEFAULT_SCORE_FIELDS`'s prior hardcoded value
exactly, so PATCH's own scoring is unchanged) and ABSORBER/
ABSORBER_TRANSMISSIVE state as `worst_absorption`/fraction (`orchestration/
design_loop.py`'s `_simulate_meep_floquet`, via `_meep_absorption_for_
family`). A family that has declared no `simulation_scored_field` at all
(`UndeclaredScoredField`) has no default to fall back to -- scoring its
SIMULATION step without an explicit override is refused as a call-level
`SolverError`, raised before any candidate is evaluated, rather than
silently reusing PATCH's `gain_dbi` (a confidently wrong field) or
reporting a confusing per-candidate `failed_at_step`.

A caller wanting a DIFFERENT field scored than either kind of default
(e.g. SIMULATION's `average_power_gain_linear` instead of `gain_dbi`, or
any field at all for a family with no declared default) overrides
`result_field` in that step's `score_specs` entry, but then MUST also
supply an explicit `unit` -- this module has no basis for guessing the
unit of an arbitrary overridden field, matching designs/success_score.py's
own "refuse rather than guess a unit conversion" rule exactly (see that
module's "UNIT HANDLING" section); `_resolve_score_field` below enforces
this and raises `SolverError` naming the problem if violated.

A step with no `score_specs` entry is still DRIVEN (its `LoopDecision` is
recorded, exactly as if scored) but never scored -- its trail entry
carries `"score": None`. This lets a caller drive all three steps while
scoring only, say, OPTIMIZATION's frequency target, without inventing a
target for a step nobody stated a requirement for.

------------------------------------------------------------------------
PREDICTION: A CANDIDATE'S STATED GUESS, SCORED AGAINST ITS OWN RELEVANT
STEP, IN THE SAME PASS (issue #253, docs/adr/0022).

A candidate dict may carry an optional `"prediction"` key -- `{"value":
<float>, "tolerance": <float>}`, in the unit of whichever step's target it
is compared against (see "which step" below) -- stating what the LLM
expects THIS candidate's scored quantity to come out to, before this
module looks at the answer. Exactly like `"note"` above, this is never
required and never gates: a candidate with no `"prediction"` key, or one
that is present but malformed (not a dict, a non-numeric or missing
`value`/`tolerance`, a negative `tolerance`), simply reads as no
prediction stated -- never raises, never blocks that candidate's drive.

WHICH STEP A PREDICTION IS ABOUT: the first step (in driven order) that
`score_specs` actually scores -- computed once per call, before any
candidate runs (`steps_to_drive` and `score_specs` are already fixed at
that point), never per candidate. The common case this module's tests and
the ADR's own examples use is a single-entry `score_specs` (e.g. only
OPTIMIZATION's achieved frequency scored), where this is simply "the one
step being scored" and no choice is actually being made. A caller who
scores more than one step in the same call has every one of those steps'
own scores in `trail`'s per-step `steps` list regardless -- only WHICH
step a stated Prediction is compared against is fixed to the first.

STATUS -- computed immediately after that relevant step's own score is
known (or is known to have never been reached), same pass, never a later
one:

  - `"UNSCOREABLE"`: no prediction was stated (or what was stated could
    not be parsed as a valid value/tolerance pair), OR a valid prediction
    WAS stated but its own `tolerance` is not narrower than the relevant
    step's target's own `tolerance` (ADR-0022's own example: "82 +/- 15"
    cannot honestly separate a pass from a fail against a target whose own
    tolerance is, say, 10 -- reusing `target["tolerance"]` directly as the
    yardstick, no new target concept invented) -- including when that
    target carries no `tolerance` at all, since there is then no yardstick
    to compare narrowness against.
  - `"PREDICTED"`: a valid prediction was stated, but the candidate never
    reached a scored value for its relevant step to compare against --
    it failed (at that step or an earlier one) before a comparison was
    possible. This is deliberately the resolution to a real ambiguity in
    ADR-0022's status vocabulary (`PREDICTED -> CONFIRMED/REFUTED`, plus
    `UNSCOREABLE`): since status is computed in this same pass rather than
    a later one, `PREDICTED` would otherwise never appear in a returned
    trail entry at all. Making it the status for "stated, but failed
    before its relevant step produced a value" keeps it a real, reachable
    state instead of dead vocabulary, and is the one place this module
    knowingly departs from the ADR's own worked "failed candidate" example
    (which named `UNSCOREABLE`) -- `UNSCOREABLE` stays reserved for the
    two cases above instead, so it always means "the stated tolerance
    itself could never separate a pass from a fail", never "the run
    failed".
  - `"CONFIRMED"` / `"REFUTED"`: the relevant step DID produce a score
    (whether or not some LATER step then failed -- see design question 4;
    a candidate's relevant step succeeding is what matters here, not
    whether the whole candidate did), the stated tolerance IS narrower
    than the target's own, and the actual value fell inside
    (`"CONFIRMED"`) or outside (`"REFUTED"`) the stated `value +/-
    tolerance` band.

`residual` is `predicted - actual` (signed, matching `designs.success_
score.score_point_target`'s own `deviation` sign convention) for
`"CONFIRMED"`/`"REFUTED"` only -- `None` for `"PREDICTED"`/`"UNSCOREABLE"`,
since neither has an actual value a residual could honestly be computed
against.

`provenance` is always `"INFERRED"`, unconditionally -- including when no
prediction was stated at all. This is the exact `designs/success_score.py`
precedent this module already imports `INFERRED` from: a Requirement
target's `provenance` stays `"ASSUMED"` forever regardless of confirmation
because confirming a reading changes how much to trust it, not what kind
of evidence it is (that module's own "CRITICAL CORRECTION" section). A
Prediction is permanently `"INFERRED"` on identical logic -- an LLM's
stated guess does not become anything else because this module's own
arithmetic later happened to agree with it. Unlike `note_provenance`
(`None` when no note was given), `provenance` here is never `None`: the
field itself always exists on every trail entry, so a reader never has to
special-case "was a prediction even attempted" before reading it.

This never influences `overall_score_percent`/`all_targets_met`/
`best_candidate_index`/any stopping rule -- `_score_prediction` (below) is
a pure function of already-computed values, called strictly for its own
return value, after every field that DOES drive convergence is already
finalized for that candidate. See `tests/test_solver.py`'s own regression
test running the same batch with and without Predictions attached and
asserting every pre-existing field is byte-for-byte identical.

------------------------------------------------------------------------
MECHANISM CLAIM: ONE TESTABLE REASON FOR THE WHOLE BATCH, NOT ONE GUESS
PER CANDIDATE (issue #253, docs/adr/0022).

`mechanism_claim` is a single optional string parameter on the call
itself, not a candidate field -- a Prediction (above) states what value a
candidate is expected to score; a Mechanism claim states WHY the batch was
shaped the way it was (ADR-0022's own example: "the shortest candidate
scores worst"), one ordering statement for the batch as a whole. It is
carried straight through onto the result dict's own `mechanism_claim`
field, verbatim, and is never parsed, validated, or scored by this
module -- exactly as Predictions are never allowed to influence
`overall_score_percent`/convergence, the reverse also holds: nothing here
checks whether the claim held up. That reading is left to a human, or a
later LLM turn, working from the batch's own `trail`. Omitted, it reads
`None`; present, it appears unchanged, including on every early-return
path (`loop_completed`/`gated_step_pending_approval`/`out_of_scope_step`),
since the claim is recorded before any candidate runs.

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
import math
from typing import Any

import designs.db as designs_db
from designs.design_families import AnalysisModel as _AnalysisModel
from designs.design_families import ScoredField as _ScoredField
from designs.design_families import UnknownDesignFamilyError as _UnknownDesignFamilyError
from designs.design_families import get_design_family as _get_design_family
from designs.requirement_targets import TargetStatus
from designs.success_score import INFERRED, success_score

from .design_loop import GATED_STEPS, DesignStep
from .score_fields import SCORE_FIELD_SOURCES
from .tooling import advance_design_loop_step

_logger = logging.getLogger(__name__)

CALCULATED = "CALCULATED"

# Prediction status vocabulary -- ADR-0022's own four names, with PREDICTED's
# meaning resolved for the "same pass" constraint (see this module's
# docstring, "PREDICTION"). Kept as plain module-level strings, matching
# this module's own CALCULATED constant above, rather than a new enum --
# ADR-0022 is explicit this is not a parallel confidence scale, so it does
# not get the ceremony designs.requirement_targets.TargetStatus has.
PREDICTED = "PREDICTED"
CONFIRMED = "CONFIRMED"
REFUTED = "REFUTED"
UNSCOREABLE = "UNSCOREABLE"

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
#
# ANALYSIS has no entry here (issue #249): its required fields used to be
# hardcoded to the patch antenna's own eps_r/w_m/h_m/l_m shape, which
# `_build_step_input` applied to EVERY family -- an absorber candidate's
# real fields (f_low_hz, tan_delta, ...) were stripped before ANALYSIS ever
# ran, so it failed on fields that were never missing, only discarded.
# `_required_fields_for` below reads ANALYSIS's required fields off the
# design family's own `analysis_model.required_fields` declaration
# (designs/design_families.py) instead. SIMULATION and OPTIMIZATION keep
# their own single, generic entries here unchanged: SIMULATION's shape
# (geometry/frequency_hz/reference_impedance_ohms) is the same regardless
# of family, and OPTIMIZATION's family-awareness is `optimizer_class`
# wiring -- a separate, related gap this ticket does not touch.
_REQUIRED_FIELDS: dict[DesignStep, tuple[str, ...]] = {
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


def _family_from_state(state: dict[str, Any]) -> Any:
    """The `designs.design_families.DesignFamily` this iteration's
    ARCHITECTURE decision named (issue #249) -- read straight off
    `state["decisions"]`, the tooling-shaped state's own trail, mirroring
    `orchestration.design_loop`'s private `_family_of_record`/
    `_registry_family_of_record` (duplicated, not imported -- matching this
    module's own established precedent of duplicating design_loop.py's
    private step-handler facts rather than reaching into its internals; see
    `_REQUIRED_FIELDS`'s own comment above).

    Only ever called once `_steps_from` has already confirmed
    `state["current_step"]` sits inside `_ORDERED_UNGATED_SPAN` -- the
    design loop's own state machine cannot reach ANALYSIS/SIMULATION/
    OPTIMIZATION without an ARCHITECTURE decision already recorded, so this
    lookup is never expected to come up empty for a state a real loop
    produced. A hand-assembled state missing one is reported by name here
    rather than silently treated as any particular family."""
    family_name = None
    for decision in state.get("decisions") or ():
        if decision.get("step") == DesignStep.ARCHITECTURE.value:
            family_name = decision.get("input", {}).get("design_family")
    if family_name is None:
        raise SolverError(
            "state has no recorded ARCHITECTURE decision naming a design_family "
            "-- run_candidate_search only reaches this point once state['current_"
            "step'] is already positioned past ARCHITECTURE (see _steps_from), so "
            "this indicates a hand-assembled state missing its own architecture "
            "decision."
        )
    try:
        return _get_design_family(family_name)
    except _UnknownDesignFamilyError as exc:
        raise SolverError(str(exc)) from exc


def _required_fields_for(step: DesignStep, family: Any) -> tuple[str, ...]:
    """Required `step_input` fields for `step`, from the design family's
    own registry declaration where one exists (issue #249).

    ANALYSIS reads `family.analysis_model.required_fields` -- an absorber's
    real fields (`f_low_hz`, `tan_delta`, ...) no longer get stripped down
    to the patch antenna's `eps_r`/`w_m`/`h_m`/`l_m` shape just because
    ANALYSIS used to have one single hardcoded entry regardless of family.
    A family whose `analysis_model` is `UndeclaredAnalysisModel` (no
    closed-form model at all) has no required fields to strip TO here --
    an empty tuple is correct, not a gap: `advance_design_loop_step`'s own
    ANALYSIS dispatch raises naming the undeclared model regardless of what
    step_input it is handed, so the real failure is reported honestly
    either way.

    SIMULATION and OPTIMIZATION keep this module's own single, generic
    `_REQUIRED_FIELDS` entry, unchanged: SIMULATION's shape (geometry/
    frequency_hz/reference_impedance_ohms) does not vary by family, and
    OPTIMIZATION's family-awareness is `optimizer_class` wiring -- a
    separate, related gap this ticket does not touch."""
    if step is DesignStep.ANALYSIS:
        model = family.analysis_model
        return model.required_fields if isinstance(model, _AnalysisModel) else ()
    return _REQUIRED_FIELDS[step]


def _build_step_input(step: DesignStep, candidate: dict[str, Any], family: Any) -> dict[str, Any]:
    """Project `candidate`'s fields down to exactly the ones `step`'s real
    handler reads (required + optional) -- a missing required field is
    left out, not filled in or defaulted, so the real handler's own
    validation is what raises for it (see this module's docstring)."""
    fields = (*_required_fields_for(step, family), *_OPTIONAL_FIELDS.get(step, ()))
    return {field: candidate[field] for field in fields if field in candidate}


def _default_score_field_for(step: DesignStep, family: Any) -> tuple[str, str] | None:
    """The `(result_field, unit)` this module scores `step` on by default,
    or `None` if none is available -- see this module's docstring,
    "SCORING", and issue #249.

    ANALYSIS and OPTIMIZATION keep this module's own single, generic
    default (`_DEFAULT_SCORE_FIELDS`, derived from `orchestration.
    score_fields.SCORE_FIELD_SOURCES`) -- both handlers' result shapes
    (`resonant_frequency_hz`/`achieved_frequency_hz`) do not vary by
    family today. SIMULATION reads the family's OWN declaration instead
    (`family.simulation_scored_field`): a patch's SIMULATION result and an
    absorber's carry no shared shape at all -- one reports a radiated gain,
    the other a worst-in-band absorbed fraction -- so a single hardcoded
    default (`gain_dbi`) was never a conservative fallback for every other
    family, it was a wrong answer waiting to be produced confidently.
    `None` here means the family declares no scored field for this step;
    `_resolve_score_field` below is what turns that into the "not scored"
    `SolverError`."""
    if step is DesignStep.SIMULATION:
        scored = family.simulation_scored_field
        return (scored.result_field, scored.unit) if isinstance(scored, _ScoredField) else None
    return _DEFAULT_SCORE_FIELDS[step]


def _resolve_score_field(step: DesignStep, spec: dict[str, Any], family: Any) -> tuple[str, str]:
    """Which raw-result field to score for `step`, and its unit -- see
    this module's docstring, "SCORING". Raises `SolverError` if the caller
    overrode `result_field` away from this module's own documented default
    without also stating an explicit `unit` for it, OR if `family` declares
    no default scored field for `step` at all (issue #249) and the caller
    did not supply a complete override (`result_field` AND `unit`) to score
    a specific field anyway -- the distinct, clearly-named "not scored"
    state this ticket's acceptance criteria ask for: a call-level
    `SolverError`, raised before any candidate is evaluated, never a
    silent wrong-field lookup and never a per-candidate `failed_at_step`."""
    default = _default_score_field_for(step, family)
    if default is None:
        if "result_field" in spec and "unit" in spec:
            return spec["result_field"], spec["unit"]
        # _default_score_field_for only returns None for SIMULATION, and
        # only when family.simulation_scored_field is the
        # UndeclaredScoredField sentinel -- its own `reason` names why,
        # matching this module's existing precedent (the override-without-
        # unit branch below) of surfacing the concrete reason rather than a
        # generic message.
        undeclared = family.simulation_scored_field
        raise SolverError(
            f"score_specs[{step.value!r}] cannot be scored by default: "
            f"design family {getattr(family, 'name', family)!r} declares no "
            f"simulation_scored_field. Why not: {undeclared.reason} State an "
            "explicit 'result_field' and 'unit' in this score_specs entry to "
            "score a specific field instead, or remove this step from "
            "score_specs to drive it without scoring it (issue #249)."
        )

    default_field, default_unit = default
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
        # Field resolution itself (the default-field/override/unit checks
        # `_resolve_score_field` performs) is deliberately NOT done here
        # any more (issue #249): it needs the design family this call's
        # `state` names, and `state` is not validated to be positioned past
        # ARCHITECTURE until `run_candidate_search` itself has checked for
        # a gated/out-of-scope/completed step -- resolving the family here
        # would raise for a state legitimately still sitting at a gated
        # ARCHITECTURE step, before this function ever gets a chance to
        # report that as `stop_reason="gated_step_pending_approval"`
        # instead. `run_candidate_search` performs the equivalent eager,
        # call-level `_resolve_score_field` check itself, once the family
        # is known and BEFORE any candidate is evaluated -- see its own
        # body, immediately after the "none of score_specs" check.
    return score_specs


def _score_step(
    step: DesignStep,
    spec: dict[str, Any],
    decision_result: dict[str, Any],
    note: str | None,
    family: Any,
) -> dict[str, Any]:
    """Score one driven step's raw result against `spec["target"]`. Raises
    `SuccessScoreError` (from `designs.success_score.success_score`) for
    everything that function itself refuses -- including a missing/non-
    numeric value at the resolved `result_field` -- letting that module's
    own validation do the work rather than duplicating it here."""
    result_field, unit = _resolve_score_field(step, spec, family)
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
    family: Any,
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
        step_input = _build_step_input(step, candidate, family)
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
                score = _score_step(step, spec, decision["result"], note, family)
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


def _parse_stated_prediction(stated: Any) -> tuple[float | None, float | None]:
    """`(value, tolerance)` parsed out of a candidate's raw `"prediction"`
    field, or `(None, None)` for anything that is not a well-formed
    prediction -- absent entirely, not a dict, a missing/non-numeric
    `value` or `tolerance`, or a negative `tolerance`. Never raises: this
    module's Prediction handling is explicitly under no gate (this
    module's docstring, "PREDICTION"), so a malformed `"prediction"` reads
    exactly like an absent one -- `(None, None)`, which `_score_prediction`
    below turns into `UNSCOREABLE`."""
    if not isinstance(stated, dict):
        return None, None
    raw_value = stated.get("value")
    raw_tolerance = stated.get("tolerance")
    if isinstance(raw_value, bool) or not isinstance(raw_value, (int, float)):
        return None, None
    if not math.isfinite(raw_value):
        return None, None
    if isinstance(raw_tolerance, bool) or not isinstance(raw_tolerance, (int, float)):
        return None, None
    if not math.isfinite(raw_tolerance) or raw_tolerance < 0:
        return None, None
    return float(raw_value), float(raw_tolerance)


def _score_prediction(
    stated: Any,
    target: dict[str, Any],
    relevant_step: DesignStep,
    step_trail: list[dict[str, Any]],
) -> dict[str, Any]:
    """One candidate's Prediction sub-dict -- see this module's docstring,
    "PREDICTION", for the full rule this implements. Pure function: takes
    the candidate's raw `"prediction"` field, the target `relevant_step`
    was scored against (`score_specs[relevant_step.value]["target"]`), and
    that candidate's OWN already-driven `step_trail` (`_drive_candidate`'s
    `"steps"` list) -- never mutates any of them, never raises, and never
    influences anything this module uses for convergence.

    Returns `{"value", "tolerance", "status", "residual", "provenance"}`
    -- always present, even when no prediction was stated at all (`value`/
    `tolerance`/`residual` are `None`, `status` is `UNSCOREABLE`,
    `provenance` is still `"INFERRED"`)."""
    value, tolerance = _parse_stated_prediction(stated)
    if value is None:
        return {
            "value": None,
            "tolerance": None,
            "status": UNSCOREABLE,
            "residual": None,
            "provenance": INFERRED,
        }

    relevant_entry = next(
        (entry for entry in step_trail if entry["step"] == relevant_step.value), None
    )
    actual_value = None
    if relevant_entry is not None and relevant_entry["score"] is not None:
        actual_value = relevant_entry["score"]["actual_value"]

    if actual_value is None:
        # Stated, but this candidate never reached a scored value for its
        # relevant step to compare against -- see this module's docstring,
        # "PREDICTION", for why this is PREDICTED rather than UNSCOREABLE.
        return {
            "value": value,
            "tolerance": tolerance,
            "status": PREDICTED,
            "residual": None,
            "provenance": INFERRED,
        }

    decision_tolerance = target.get("tolerance") if isinstance(target, dict) else None
    tolerance_is_narrower = (
        isinstance(decision_tolerance, (int, float))
        and not isinstance(decision_tolerance, bool)
        and tolerance < decision_tolerance
    )
    if not tolerance_is_narrower:
        # ADR-0022's own rule: a stated tolerance that is not narrower than
        # the target's own cannot honestly separate a pass from a fail --
        # UNSCOREABLE by construction, never CONFIRMED, however close
        # `value` and `actual_value` happen to be. Also covers a target
        # with no stated tolerance at all: there is then no yardstick to
        # compare narrowness against.
        return {
            "value": value,
            "tolerance": tolerance,
            "status": UNSCOREABLE,
            "residual": None,
            "provenance": INFERRED,
        }

    residual = value - actual_value
    status = CONFIRMED if abs(residual) <= tolerance else REFUTED
    return {
        "value": value,
        "tolerance": tolerance,
        "status": status,
        "residual": residual,
        "provenance": INFERRED,
    }


def _prior_best_from_design(
    design_id: int,
    scoreable_steps: list[DesignStep],
    score_specs: dict[str, dict[str, Any]],
    family: Any,
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

    `family` (issue #249) is this call's OWN design family (`state`'s
    ARCHITECTURE decision, resolved once by `run_candidate_search` via
    `_family_from_state`) -- used exactly like every OTHER `_score_step`
    call in this module, to resolve SIMULATION's scored field off the
    family's own declaration rather than a single hardcoded default. Per
    this function's own docstring above, `design_id` need not name a
    design of the SAME family as `state`; a caller seeding from a
    DIFFERENT, related design's history gets that history scored under
    THIS call's family regardless -- the identical simplifying assumption
    this module already made before #249 (one global default for every
    family), so this is not a new limitation introduced here.
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
                scores.append(
                    _score_step(step, spec, row.get("value") or {}, note=None, family=family)
                )
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
    mechanism_claim: str | None = None,
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
        whatever fields the steps actually driven need. ANALYSIS's own
        required fields (issue #249) come from the driven design family's
        own `analysis_model.required_fields` declaration (`designs/
        design_families.py`) -- e.g. `eps_r`/`w_m`/`h_m`/`l_m` for PATCH,
        `f_low_hz`/`f_high_hz`/`eps_r`/`tan_delta`/`thickness_m`/`period_
        m`/`gap_m`/`sheet_resistance_ohm_sq`/`squares` for ABSORBER/
        ABSORBER_TRANSMISSIVE. SIMULATION and OPTIMIZATION keep this
        module's own single, generic `_REQUIRED_FIELDS`/`_OPTIONAL_FIELDS`
        entries regardless of family: `geometry`/`frequency_hz`/
        `reference_impedance_ohms` for SIMULATION -- the last one stated
        explicitly per candidate, never assumed to be 50 ohms (issue
        #101) -- plus `target_frequency_hz`/`length_lower_m`/`length_
        upper_m` for OPTIMIZATION. An optional `"note"` key, if present,
        is forwarded to every scored
        step's `success_score(note=...)` call for that candidate. An
        optional `"prediction"` key -- `{"value": <float>, "tolerance":
        <float>}` -- states this candidate's expected value for its
        RELEVANT step (see "PREDICTION" in this module's docstring for
        which step that is and the full status rule); absent or malformed,
        it reads as no prediction stated, never raises, never blocks.
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
      - `mechanism_claim`: optional (default `None`). A single testable
        ordering statement for why this batch was proposed the way it was
        (e.g. "the shortest candidate scores worst") -- one claim for the
        whole batch, never per candidate (that is what each candidate's
        own `"prediction"` key is for; see `candidates` above and
        "PREDICTION" in this module's docstring). Carried straight through
        onto the result dict's own `mechanism_claim` field, verbatim,
        never parsed or scored by this module (ADR-0022; issue #253) --
        present on every return path, including the early
        `loop_completed`/`gated_step_pending_approval`/`out_of_scope_step`
        stops, since it is recorded before any candidate runs.

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
      - `mechanism_claim`: the `mechanism_claim` argument, verbatim, or
        `None` if omitted -- see that argument's own entry above.
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
        "all_targets_met", "prediction"}`. `"prediction"` is always
        present -- `{"value", "tolerance", "status" ("PREDICTED"/
        "CONFIRMED"/"REFUTED"/"UNSCOREABLE"), "residual", "provenance"
        (always "INFERRED")}` -- see "PREDICTION" in this module's
        docstring; it never affects any OTHER field in this dict.
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
        "mechanism_claim": mechanism_claim,
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

    # The design family this iteration's ARCHITECTURE decision named
    # (issue #249) -- resolved exactly HERE, never earlier: `state` is not
    # confirmed to be positioned past ARCHITECTURE until the gated/out-of-
    # scope/completed checks above have already passed, and a state
    # legitimately sitting at a gated ARCHITECTURE step has no family to
    # read yet (see `_family_from_state`'s own docstring).
    family = _family_from_state(state)

    # Eagerly resolve every score_specs entry's scored field NOW, against
    # THIS family, before any candidate is evaluated -- the same "a CALL-
    # level configuration mistake fails once, up front" contract
    # `_validate_score_specs` used to enforce by itself (see that
    # function's own comment), moved here because it needs `family`. Every
    # entry in score_specs is checked, not only the ones in
    # relevant_step_names, matching that function's own original scope
    # exactly.
    for step_name, spec in score_specs.items():
        _resolve_score_field(DesignStep(step_name), spec, family)

    # Which step a candidate's "prediction" is compared against -- the
    # FIRST step (in driven order) score_specs actually scores, fixed once
    # here for the whole call, before any candidate runs. See this
    # module's docstring, "PREDICTION", "WHICH STEP". The guard above
    # already guarantees at least one such step exists.
    prediction_step = next(step for step in steps_to_drive if step.value in score_specs)
    prediction_target = score_specs[prediction_step.value]["target"]

    effective_budget = (
        len(candidates) if evaluation_budget is None else min(evaluation_budget, len(candidates))
    )
    report["evaluation_budget"] = effective_budget

    best_so_far: list[float] = []
    if design_id is not None:
        scoreable_steps = [step for step in steps_to_drive if step.value in score_specs]
        prior_best_score, prior_iteration = _prior_best_from_design(
            design_id, scoreable_steps, score_specs, family
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
        driven = _drive_candidate(state, steps_to_drive, candidate, score_specs, family)
        overall, all_met = _overall_score(driven["steps"])
        failed = driven["failed_at_step"] is not None
        prediction = _score_prediction(
            candidate.get("prediction"), prediction_target, prediction_step, driven["steps"]
        )

        entry: dict[str, Any] = {
            "candidate_index": i,
            "candidate": dict(candidate),
            "status": "failed" if failed else "evaluated",
            "error": driven["error"],
            "failed_at_step": driven["failed_at_step"],
            "steps": driven["steps"],
            "overall_score_percent": overall,
            "all_targets_met": all_met,
            "prediction": prediction,
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
