"""Batched lab-test plan (issue #94; CONTEXT.md: Customer requirement, Test
iteration, Success score, Verification item, Engineering result, Provenance,
Evidence hierarchy; ADR-0012/ADR-0013 -- physical instrument control is
gone, the design loop's MEASUREMENT step accepts only an externally-obtained
Touchstone file; ADR-0014 -- the not-yet-built solver this module's output
is meant to feed).

WHAT THIS ANSWERS. Issue #87's whole premise is that a lab trip is too slow
and expensive to be the iteration mechanism -- fast iteration happens in
software (ANALYSIS/SIMULATION/OPTIMIZATION), and the bench is a rare,
deliberate confirmation step. That makes one question worth answering in
one document, before an engineer drives to the lab: for every requirement
on this design, what should be measured, by what method, and what value is
this iteration's own recorded evidence already predicting -- so the trip
confirms or refutes a stated prediction instead of being a fishing
expedition, and so a requirement nothing on hand can confirm is flagged
*before* the trip, not discovered at the bench. `compile_lab_test_plan`
(pure) and `compile_lab_test_plan_for_loop` (its dict-in/dict-out, tool-
facing wrapper) are that compile step. Read-only end to end: no database
write, no loop-state mutation, no `LoopStepApprovalReceipt` -- see "WHY NO
APPROVAL GATE" below.

------------------------------------------------------------------------
PLACEMENT: `orchestration/`, not `designs/` -- and why the pure core takes
a `DesignLoopState`, not a `design_id`.

`orchestration/design_loop.py`'s own `LoopDecision.iteration` docstring
says this outright: that field was added "specifically so a consumer like
you [...] can filter `DesignLoopState.decisions` by `iteration` directly
against this pure state machine's own state -- without reaching into
`orchestration/tooling.py`'s `persisted_decision_count`" and names, as its
own example, "a batched lab-test-plan ticket." That is this ticket. The
whole reason this plan can say "traced to *this iteration's* engineering
results" without touching `persisted_decision_count` (a different question
-- how much of `decisions` has been flushed to Postgres, docs/adr/0011) is
that `DesignLoopState`/`LoopDecision` are `orchestration/design_loop.py`'s
own types, carrying their own `iteration` tag already. A `designs/`-rooted
version of this module would have to either import those types anyway
(inverting `designs/success_score.py`'s own hard-won dependency-direction
rule -- `orchestration/tooling.py` already imports `designs.db`/
`designs.service`, so `designs` sits below `orchestration`, and a `designs`
module reaching back up for `DesignLoopState` would be exactly the circular
risk that module's docstring calls out) or re-derive "this iteration's
decisions" from `engineering_results` rows filtered by `created_at`, which
is a strictly worse signal than the field the loop already carries for
this exact purpose.

TWO LAYERS, SAME PURE/I-O SEAM `designs/requirement_targets.py` ALREADY
ESTABLISHES (this ticket follows that precedent one package over):

  - `compile_lab_test_plan(state, requirements=None)` -- pure, DB-free,
    directly unit-tested against hand-built `DesignLoopState`/
    `LoopDecision` fixtures (`tests/test_lab_test_plan.py`). Takes the
    loop's own `requirements` unless an override is supplied.
  - `compile_lab_test_plan_for_loop(state)` -- the dict-in/dict-out,
    tool-facing wrapper `agent/main.py`/`mcp_server/server.py` actually
    call, mirroring `orchestration/tooling.py`'s existing
    `advance_design_loop_step`/`inspect_design_loop_state` shape (state
    crosses the JSON tool boundary as a plain dict, extended with
    `design_id`). Its ONE piece of real work: read section "REQUIREMENTS
    FRESHNESS" below for why it prefers a fresh `designs.requirements`
    read over the loop's own frozen snapshot when `design_id` is present.
    Deliberately kept in this file rather than added to
    `orchestration/tooling.py` -- `compile_lab_test_plan_for_loop` is this
    ticket's own new capability, and `orchestration/tooling.py`'s existing
    functions do not compose with it (they mutate/persist; this only
    reads), so nothing is gained by intermingling this ticket's small,
    reviewable diff into that file over keeping it self-contained here,
    the same "each new capability's I/O wrapper gets its own module"
    choice `designs/requirement_targets.py` made for its own three I/O
    wrappers rather than adding them to `designs/service.py`.

REQUIREMENTS FRESHNESS -- A REAL GAP THIS MODULE WORKS AROUND, NOT
INVENTS. `DesignLoopState.requirements` is set exactly once, in
`start_design_loop`, and NOTHING in `orchestration/design_loop.py` or
`orchestration/tooling.py` ever updates it again -- not even
`advance_design_loop_step`'s own REDESIGN_DECISION flush. Meanwhile
`designs.requirement_targets.propose_requirement_target`/
`confirm_requirement_target`/`mark_requirement_unscoreable` (#92) write
their `target` key straight onto the *persisted* `designs.requirements`
JSONB column via `design_id` -- a completely different storage location
from the loop-state dict an agent is holding. Call one of those after a
loop is already past ARCHITECTURE and the loop's own `state["requirements"]`
is now stale: it still reflects whatever targets existed at
`start_design_loop` time, not the confirmed target an engineer proposed
five minutes ago. `compile_lab_test_plan_for_loop` closes that gap the
only honest way available without changing `design_loop.py`/`tooling.py`'s
own state design (out of this ticket's territory): when the extended state
dict carries a `design_id` (i.e., it came from `start_new_design_loop`/
`advance_design_loop_step`, not bare `orchestration.design_loop.
start_design_loop`), it re-reads `designs.requirements` fresh via
`designs.db.read_design` and passes THAT to the pure core instead of the
loop's own frozen copy; `state.decisions`/`state.iteration`/`state.loop_id`
still come from the loop state itself, since those are the loop's own
authoritative history and nothing else recomputes them. This is exactly
the "(or a design's requirements plus recorded decisions)" alternative
this ticket's own placement guidance names -- `requirements`, as a plain
override parameter on the pure core, is how both phrasings of that
guidance are satisfied by one function rather than two competing ones. A
bare pure-state caller (no `design_id`) falls back to `state.requirements`
verbatim, honestly stale-if-stale, since there is nowhere fresher to read
from.

WHY NO APPROVAL GATE, NO DATABASE WRITE, NO STATE MUTATION. This ticket's
own acceptance criteria says so directly ("Requesting the plan advances
nothing, writes nothing, and needs no approval receipt; it can be asked
for at any point in the loop"), and the code honors it structurally, not
just by convention: `compile_lab_test_plan` never calls
`orchestration.approval.check_loop_step_approval_gate`, never calls
`advance_loop_step`, and returns a freshly-built dict with no reference
back into `state.decisions`' own list identity. `compile_lab_test_plan_
for_loop` opens a database connection only to *read* (`designs.db.
read_design`) -- never `designs.db.record_engineering_result`/
`update_design_status`/anything else that writes.

------------------------------------------------------------------------
DESIGN QUESTION 1 -- WHAT MAKES A REQUIREMENT "NOT VERIFIABLE BY THE
MEASUREMENT AVAILABLE," AND WHY FOUR DISTINGUISHABLE REASONS, NOT ONE
BOOLEAN.

Collapsing every blocked requirement into one `verifiable: bool` would
throw away exactly the information that tells an engineer what to do
next -- "propose a target," "this needs a chamber, not a bench VNA," and
"run ANALYSIS before you drive out there" are three completely different
remedies. `UnverifiableReason` is a closed, four-member vocabulary
(`StrEnum`, matching `designs.requirement_targets.TargetStatus`'s own
style), checked in this fixed priority order per requirement (a
requirement can trip more than one; only the first, most-actionable one is
reported -- fixing it is what actually needs doing, and the later reasons
in the list would frequently stop applying once the earlier one is fixed):

  1. `NO_TARGET_RECORDED` -- the requirement carries no `target` key at
     all. Distinct from `UNSCOREABLE_TARGET` below: nobody has assessed
     this requirement yet, versus an engineer having explicitly judged it
     has no defensible numeric target. Not one of the ticket's three named
     "honest cases," but a real, common state (every requirement the loop
     starts with, before anyone calls `propose_requirement_target`) that
     collapsing into `UNSCOREABLE_TARGET` would misrepresent as a judgment
     nobody made.
  2. `UNSCOREABLE_TARGET` -- `designs.requirement_targets.mark_unscoreable`
     already ran for this requirement: `target["target_status"] ==
     "UNSCOREABLE"`, `target["reason"]` explaining why. This module reuses
     `designs.requirement_targets.TargetStatus` directly (imported, not
     re-declared -- same choice `designs/success_score.py` already made for
     the identical reason: it is that module's own vocabulary and a
     second, parallel enum would risk exactly the fork CONTEXT.md's
     provenance section warns against).
  3. `QUANTITY_NOT_TOUCHSTONE_MEASURABLE` -- the target's stated `unit`
     names a physical quantity a Touchstone S-parameter sweep, this
     project's ONLY measurement method since ticket #90 (ADR-0012/
     ADR-0013), cannot report: antenna gain (dBi/dBd -- needs a range or
     chamber, not a VNA port), radiation pattern (deg/degrees -- same),
     efficiency (%). VSWR, return loss, insertion loss (dB), and
     frequency/bandwidth (Hz and its prefixes) CAN be read off an S11/S21
     sweep and are treated as measurable. See "DESIGN QUESTION 3" for the
     closed unit vocabulary this checks against and what an unrecognized
     unit does. This reason fires regardless of whether an expected value
     was traced (see `_compile_item`) -- a predicted gain from SIMULATION
     is still not something THIS lab trip's Touchstone read will confirm,
     even though it is honestly reported as already-evidenced-elsewhere.
  4. `NO_ENGINEERING_RESULT_THIS_ITERATION` -- the target IS scoreable and
     IS Touchstone-measurable, but nothing this iteration's ANALYSIS/
     SIMULATION/OPTIMIZATION recorded a matching numeric quantity to
     predict from (see DESIGN QUESTION 2). Per this ticket's own guidance:
     "that is itself useful information ('run ANALYSIS before going to the
     bench')" -- reported, not papered over with the requirement's raw
     target value standing in for a prediction nobody computed.

A fifth near-miss, deliberately NOT its own reason: a matching-quantity
engineering result WAS found this iteration, but in a different unit
string than the target's own (`resonant_frequency_hz` is always `"Hz"`;
a target proposed in `"GHz"` will not match by exact string, and this
module -- like `designs/success_score.py` -- never guesses a conversion).
This is folded into `NO_ENGINEERING_RESULT_THIS_ITERATION`'s own `detail`
text (distinguishing "nothing of this quantity kind was recorded" from
"something was recorded, but in a unit this module won't silently
convert") rather than becoming a fifth top-level reason -- the remedy is
the same in both cases from the plan-reader's point of view ("no expected
value could be traced as stated"), and a fifth code would fork the closed
vocabulary for what is, underneath, a units-discipline detail rather than
a structurally different kind of gap.

------------------------------------------------------------------------
DESIGN QUESTION 2 -- WHERE THE EXPECTED VALUE COMES FROM, AND WHY THIS
MODULE NEVER CALLS `designs.success_score.success_score`.

An expected value must trace to a REAL `CALCULATED`/`SIMULATED`
`LoopDecision` recorded this iteration (`decision.iteration ==
state.iteration`) -- never the requirement's own target value restated as
if it were a prediction, and never a number this module computes fresh.
`_FIELD_SOURCES` is a small, closed table: quantity kind -> the ordered
list of (step, result-field, canonical unit) this loop's OWN, currently
wired tool set can produce that kind of number from --

  - FREQUENCY: `ANALYSIS`'s `resonant_frequency_hz`
    (`rf_tools.calculations.patch_resonant_frequency_hz`), then
    `OPTIMIZATION`'s `achieved_frequency_hz`
    (`optimization.rf_objectives.optimize_patch_length_for_target_
    frequency`) -- both `Hz`.
  - GAIN: `SIMULATION`'s `gain_dbi` (`simulation.nec2pp.
    run_nec2_simulation`'s NEC2 radiation-pattern parse) -- `dBi`.

`_find_expected` walks this iteration's decisions in their recorded
(= `STEP_ORDER`) order and keeps overwriting its candidate on every match,
so the LAST matching decision wins -- i.e. the most-refined one, since
`STEP_ORDER` always runs ANALYSIS before OPTIMIZATION within one iteration
and an `OPTIMIZATION` result is a refinement of what `ANALYSIS` first
computed. This falls out of `STEP_ORDER`'s own ordering for free; no
separate step-priority table was needed or written.

A NAMED, HONEST GAP: VSWR/return-loss/insertion-loss (`dB`,
"S_PARAMETER_DB" quantity kind) has NO entry in `_FIELD_SOURCES` at all,
even though it is touchstone-measurable (DESIGN QUESTION 1, reason 3
above never fires for it) and even though `SIMULATION`'s own result
carries an `impedance` value that VSWR/return loss could, in principle, be
derived from. It is not derived here. Doing so would be exactly the
"fresh calculation this module must not perform" this ticket's own design
guidance rules out ("not a fresh calculation you perform") -- computing a
number `run_nec2_simulation` never itself returned would mean this
module's `expected` field no longer traces to a decision the loop actually
recorded, silently reintroducing the "an LLM/deterministic layer invents a
number nobody asked it to compute" problem this whole codebase's
provenance discipline exists to prevent (`rf_tools/calculations.py`,
`docs/adr/0003`). A requirement stated in VSWR/dB today always falls
through to `NO_ENGINEERING_RESULT_THIS_ITERATION` -- correctly, since
nothing in this loop's current tool set computes that scalar. Closing this
gap needs a real ANALYSIS/SIMULATION step that records a VSWR or
return-loss number as part of its own output (a future ticket's job, not
a silent addition here).

WHY NOT CALL `designs.success_score.success_score()` HERE. That function
scores a recorded `actual_value` against a target -- but before the lab
trip there is no `actual_value` yet; that is the entire point of a
*pre-trip* plan. Calling it against a `SIMULATED`/`CALCULATED` stand-in
would either report a trivially-perfect self-comparison (scoring
`gain_dbi` against a target proposed FROM that same number) or, far more
often, raise `SuccessScoreError` on the very unit-string mismatches
DESIGN QUESTION 1's "fifth near-miss" paragraph already describes as an
expected, non-blocking limitation here -- turning an honest "no exact-unit
match to trace" case into a hard exception this module would then have to
catch and paper over anyway. `designs.requirement_targets.TargetStatus`
IS imported directly (not re-declared) for the identical reason
`designs/success_score.py` imports `TargetComparator`/`TargetStatus`
rather than duplicating them: it is #92's own vocabulary, this module's
direct, documented input. `designs.success_score.SCOREABLE_STEPS`/
`JUDGMENT_STEPS`, by contrast, are NOT imported: that pair answers "which
design-loop STEP gets a Success score at all" (a five-step vocabulary
including VERIFICATION/CORRELATION, which are compiled/comparison steps,
not fresh single-quantity numeric results), a materially different
question from "which step recorded a number matching THIS requirement's
own physical quantity this iteration" -- reusing that pair here would
imply a scoring relationship this module never establishes.

------------------------------------------------------------------------
DESIGN QUESTION 3 -- METHOD SELECTION.

`verification/README.md`'s `method` vocabulary is closed: analysis /
simulation / measurement / inspection / test. This module never emits
`inspection` or `test` -- nothing in this loop's current, closed tool set
(ANALYSIS/SIMULATION/OPTIMIZATION/MEASUREMENT, per `orchestration/
design_loop.py`'s own module docstring) produces evidence that would
honestly earn either label (a fixture-inspection or environmental-test
tool would need to exist first; a known gap, not an oversight). The rule
actually applied, per requirement, follows directly from what evidence
genuinely exists for it, never a generic guess at what "should" verify a
given quantity:

  1. Touchstone-measurable quantity (DESIGN QUESTION 1, reason 3's
     allow-list) -> `method = "measurement"`, unconditionally -- this is
     the lab trip this plan exists to prepare for; regardless of whether
     an expected value could be traced (a `NO_ENGINEERING_RESULT_THIS_
     ITERATION` flag can still coexist with `method = "measurement"`: the
     bench VNA CAN read this quantity even when nothing has predicted a
     value for it yet).
  2. Not Touchstone-measurable, but a matching-quantity `CALCULATED`/
     `SIMULATED` decision WAS found this iteration -> `method =
     "analysis"` (provenance `CALCULATED`) or `"simulation"` (provenance
     `SIMULATED`) -- naming the step that ALREADY produced this
     requirement's best available evidence, honestly documenting that
     this requirement will not be confirmed on the upcoming trip.
  3. Neither -> `method = None`. Nothing defensible to recommend; refusing
     to name a method here is the same refuse-rather-than-guess instinct
     `designs/success_score.py`'s unit-mismatch refusal and `rf_tools/
     correlation.py`'s port-count refusal already apply elsewhere in this
     codebase.

------------------------------------------------------------------------
OUTPUT SHAPE. One dict per call:

  - `loop_id` / `iteration`: `state.loop_id`/`state.iteration`, so a plan
    is traceable back to the exact loop/iteration it was compiled for.
  - `items`: one entry per key in the resolved `requirements` dict, each
    shaped to `verification/README.md`'s own field set --
    `requirement_id`/`requirement`/`method`/`expected`/`actual`/`status`/
    `evidence`/`notes` -- plus this module's own `flag` (`None`, or
    `{"reason": <UnverifiableReason value>, "detail": <str>}`).
    `actual`/`evidence` are always `None`: nothing has been measured yet
    (this document exists to be brought TO the bench, not to record what
    happened there). `status` is always one of design_loop.py's own
    `VERIFICATION_STATUSES` -- `"NOT VERIFIED"` (a real plan item, pending
    the trip) or `"BLOCKED"` (any flagged item -- verification/README.md's
    own status vocabulary already has a word for "cannot presently be
    verified"; reusing it here, rather than inventing a fifth status
    string, keeps this module's output a strict subset of the existing
    vocabulary its docstring headline promises ("shaped to the existing
    verification-matrix fields"), not a new parallel one). `expected`,
    when traced, carries its own `value`/`unit`/`provenance`/
    `source_step`/`source_iteration` alongside the target's own
    `target_value`/`target_unit`/`comparator`/`tolerance` -- enough for a
    reader to see both numbers side by side without re-deriving anything.
  - `flagged_requirement_ids`: every `requirement_id` whose item carries a
    `flag` -- the acceptance criterion's "flagged... before travelling"
    made directly queryable without filtering `items` by hand.
  - `how_to_return_results`: fixed guidance (not per-requirement) on what
    to physically bring back (a Touchstone file per DUT/sweep, optionally
    a lab-report reference and notes) and how to feed it into MEASUREMENT
    (`advance_design_loop_step` with `step_input={"touchstone_file":
    ..., "lab_report": ..., "notes": ...}`, once the loop is parked at its
    MEASUREMENT step and a `LoopStepApprovalReceipt` for that exact step
    has been obtained -- MEASUREMENT is one of `GATED_STEPS`, and this
    plan does not, and structurally cannot, bypass that gate).
  - `provenance`: always `None`. This dict compiles MANY decisions'
    evidence into one document; it is not itself a single measured/
    simulated/calculated reading, so no single provenance tag from
    CONTEXT.md's vocabulary honestly describes the WHOLE dict (each
    `expected` sub-dict that exists DOES carry its own, real, per-item
    `provenance`). This mirrors `orchestration/design_loop.py`'s own
    `_handle_verification`/`_handle_architecture`/`_handle_redesign_
    decision`, whose `LoopDecision.provenance` is `None` for exactly the
    same reason (a compiled record, not a single evidentiary result).
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from designs.requirement_targets import TargetStatus

from .design_loop import VERIFICATION_STATUSES, DesignLoopState, DesignStep, LoopDecision

_TOUCHSTONE = "measurement"
_ANALYSIS_METHOD = "analysis"
_SIMULATION_METHOD = "simulation"

_NOT_VERIFIED = "NOT VERIFIED"
_BLOCKED = "BLOCKED"
assert {_NOT_VERIFIED, _BLOCKED} <= VERIFICATION_STATUSES


class LabTestPlanError(ValueError):
    """Raised when `compile_lab_test_plan`/`compile_lab_test_plan_for_loop`
    is handed something too malformed to honestly compile a plan from: a
    `requirements` dict that isn't a non-empty dict, a requirement entry
    that isn't itself a dict, a requirement with no non-empty `requirement`
    text, a `target` that isn't a dict, or a `target["target_status"]`
    outside `designs.requirement_targets.TargetStatus`'s three values. A
    `ValueError` subclass, matching `rf_tools.correlation.CorrelationError`/
    `designs.success_score.SuccessScoreError`'s own convention, so an
    existing `except ValueError` caller still catches it. Deliberately NOT
    raised for a requirement this module simply cannot verify (no target,
    an UNSCOREABLE target, an unmeasurable quantity, no traced expected
    value) -- those are the entire, expected subject matter of this
    module's `flag` output, not malformed input; see this module's
    docstring, "DESIGN QUESTION 1"."""


class UnverifiableReason(StrEnum):
    """The closed vocabulary `compile_lab_test_plan` tags a blocked plan
    item's `flag["reason"]` with -- see this module's docstring, "DESIGN
    QUESTION 1", for what each one means, why there are four (not one
    boolean), and the fixed priority order they are checked in."""

    NO_TARGET_RECORDED = "NO_TARGET_RECORDED"
    UNSCOREABLE_TARGET = "UNSCOREABLE_TARGET"
    QUANTITY_NOT_TOUCHSTONE_MEASURABLE = "QUANTITY_NOT_TOUCHSTONE_MEASURABLE"
    NO_ENGINEERING_RESULT_THIS_ITERATION = "NO_ENGINEERING_RESULT_THIS_ITERATION"


# Quantity kinds this module recognizes -- see this module's docstring,
# "DESIGN QUESTION 1" (reason 3) and "DESIGN QUESTION 2".
_FREQUENCY = "FREQUENCY"
_GAIN = "GAIN"
_PATTERN = "PATTERN"
_EFFICIENCY = "EFFICIENCY"
_S_PARAMETER = "S_PARAMETER"

# unit string (lower-cased, stripped) -> quantity kind, for units a
# Touchstone S-parameter sweep CAN report. VSWR/return-loss/insertion-loss
# are all read directly off S11/S21 magnitude; frequency/bandwidth off the
# sweep's own frequency axis.
_TOUCHSTONE_UNIT_KINDS: dict[str, str] = {
    "hz": _FREQUENCY,
    "khz": _FREQUENCY,
    "mhz": _FREQUENCY,
    "ghz": _FREQUENCY,
    "vswr": _S_PARAMETER,
    "db": _S_PARAMETER,
}

# unit string -> quantity kind, for units named in this ticket's own
# example as things "a Touchstone S-parameter file simply cannot report."
_NON_TOUCHSTONE_UNIT_KINDS: dict[str, str] = {
    "dbi": _GAIN,
    "dbd": _GAIN,
    "deg": _PATTERN,
    "degrees": _PATTERN,
    "°": _PATTERN,
    "%": _EFFICIENCY,
    "percent": _EFFICIENCY,
}

# quantity kind -> ordered (step, result-field, canonical unit) candidates
# this loop's own currently-wired tools can supply a same-quantity number
# for. See this module's docstring, "DESIGN QUESTION 2", including the
# named VSWR/S-parameter gap this table deliberately leaves open.
_FIELD_SOURCES: dict[str, list[tuple[DesignStep, str, str]]] = {
    _FREQUENCY: [
        (DesignStep.ANALYSIS, "resonant_frequency_hz", "Hz"),
        (DesignStep.OPTIMIZATION, "achieved_frequency_hz", "Hz"),
    ],
    _GAIN: [
        (DesignStep.SIMULATION, "gain_dbi", "dBi"),
    ],
}

_METHOD_FOR_PROVENANCE: dict[str, str] = {
    "CALCULATED": _ANALYSIS_METHOD,
    "SIMULATED": _SIMULATION_METHOD,
}

_HOW_TO_RETURN_RESULTS: dict[str, str] = {
    "bring_back": (
        "A Touchstone (.sNp) file per DUT/frequency sweep, taken on "
        "independent bench equipment this system never touches (a VNA, "
        "range, or chamber -- CONTEXT.md's 'Test iteration'). A lab-report "
        "reference (file path, URL, or document id) and free-text notes "
        "(test date, chamber/range, calibration standard, ambient "
        "conditions) may ride along but are never required."
    ),
    "feed_into_measurement": (
        "Once the loop is parked at its MEASUREMENT step, call "
        "advance_design_loop_step with step_input={'touchstone_file': "
        "<path>, 'lab_report': <optional>, 'notes': <optional>} -- "
        "delegated unmodified to measurement.external."
        "record_external_measurement (issue #89). MEASUREMENT is one of "
        "this loop's GATED_STEPS: a LoopStepApprovalReceipt from a prior, "
        "separate orchestration.approval.request_loop_step_approval() call "
        "for this exact loop/iteration/step/step_input combination is "
        "required before advance_design_loop_step accepts it -- this plan "
        "does not, and cannot, bypass that gate. lab_report/notes are "
        "stored verbatim and never parsed for numbers (ADR-0013): only the "
        "Touchstone file's own structured data enters this system as "
        "evidence."
    ),
}


def _classify_unit(unit: Any) -> tuple[str | None, bool]:
    """Return `(quantity_kind, touchstone_measurable)` for a target's
    `unit` string. `quantity_kind` is `None` when `unit` isn't a
    recognized string in either closed vocabulary (still honestly reported
    as not-touchstone-measurable -- see this module's docstring, "DESIGN
    QUESTION 1": refusing to claim measurability for a quantity this
    module does not recognize is the same refuse-rather-than-guess
    instinct as everywhere else in this codebase)."""
    if not isinstance(unit, str):
        return None, False
    normalized = unit.strip().lower()
    if normalized in _TOUCHSTONE_UNIT_KINDS:
        return _TOUCHSTONE_UNIT_KINDS[normalized], True
    if normalized in _NON_TOUCHSTONE_UNIT_KINDS:
        return _NON_TOUCHSTONE_UNIT_KINDS[normalized], False
    return None, False


def _find_expected(
    kind: str, target_unit: Any, iteration_decisions: list[LoopDecision]
) -> tuple[LoopDecision, float, str] | None:
    """Return `(decision, value, unit)` for the LAST (= most-refined --
    see this module's docstring, "DESIGN QUESTION 2") this-iteration
    decision whose `result` carries a numeric field `_FIELD_SOURCES[kind]`
    names, AND whose canonical unit matches `target_unit` by exact string
    equality -- `_classify_unit` groups "Hz"/"kHz"/"MHz"/"GHz" into one
    `FREQUENCY` kind for the (broader) touchstone-measurability question,
    but tracing an actual expected VALUE is held to the same no-silent-
    conversion discipline `designs.success_score.success_score` applies:
    `resonant_frequency_hz`'s own canonical unit is always `"Hz"`, so a
    target stated in `"GHz"` does not match here even though both are
    frequencies -- see this module's docstring, "DESIGN QUESTION 1"'s
    "fifth near-miss" paragraph. Returns `None` if nothing matches on both
    counts."""
    candidate: tuple[LoopDecision, float, str] | None = None
    sources = _FIELD_SOURCES.get(kind, [])
    for decision in iteration_decisions:
        if decision.provenance not in ("CALCULATED", "SIMULATED"):
            continue
        for step, field_name, unit in sources:
            if decision.step != step.value or unit != target_unit:
                continue
            value = decision.result.get(field_name)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                continue
            candidate = (decision, float(value), unit)
    return candidate


def _flag(reason: UnverifiableReason, detail: str) -> dict[str, Any]:
    return {"reason": reason.value, "detail": detail}


def _compile_item(
    requirement_id: str,
    requirement_text: str,
    target: Any,
    iteration_decisions: list[LoopDecision],
) -> dict[str, Any]:
    """Compile one requirement's plan item -- see this module's docstring,
    "OUTPUT SHAPE", for the returned field set, and "DESIGN QUESTION 1"
    for the reasons checked, in order, below."""
    item: dict[str, Any] = {
        "requirement_id": requirement_id,
        "requirement": requirement_text,
        "method": None,
        "expected": None,
        "actual": None,
        "status": _NOT_VERIFIED,
        "evidence": None,
        "notes": None,
        "flag": None,
    }

    if target is None:
        detail = (
            "no target has been proposed for this requirement yet -- call "
            "propose_requirement_target (designs.requirement_targets, "
            "issue #92), and confirm_requirement_target once reviewed, "
            "before this plan can name an expected value or a measurement "
            "method for it."
        )
        item["status"] = _BLOCKED
        item["flag"] = _flag(UnverifiableReason.NO_TARGET_RECORDED, detail)
        item["notes"] = detail
        return item

    if not isinstance(target, dict):
        raise LabTestPlanError(
            f"requirement {requirement_id!r}'s target must be a dict shaped like "
            f"designs.requirement_targets.propose_target's own return value, got "
            f"{type(target).__name__}"
        )

    target_status = target.get("target_status")
    if target_status == TargetStatus.UNSCOREABLE.value:
        detail = (
            f"this requirement's target was recorded UNSCOREABLE (reason: "
            f"{target.get('reason')!r}) -- no defensible numeric target exists "
            "to measure against."
        )
        item["status"] = _BLOCKED
        item["flag"] = _flag(UnverifiableReason.UNSCOREABLE_TARGET, detail)
        item["notes"] = detail
        return item

    if target_status not in (TargetStatus.PROPOSED.value, TargetStatus.CONFIRMED.value):
        raise LabTestPlanError(
            f"requirement {requirement_id!r}'s target.target_status must be one "
            f"of {TargetStatus.PROPOSED.value!r}/{TargetStatus.CONFIRMED.value!r}/"
            f"{TargetStatus.UNSCOREABLE.value!r}, got {target_status!r}"
        )

    kind, touchstone_measurable = _classify_unit(target.get("unit"))
    found = (
        _find_expected(kind, target.get("unit"), iteration_decisions) if kind is not None else None
    )

    expected: dict[str, Any] | None = None
    if found is not None:
        source_decision, value, unit = found
        expected = {
            "value": value,
            "unit": unit,
            "target_value": target.get("value"),
            "target_unit": target.get("unit"),
            "comparator": target.get("comparator"),
            "tolerance": target.get("tolerance"),
            "target_status": target_status,
            "provenance": source_decision.provenance,
            "source_step": source_decision.step,
            "source_iteration": source_decision.iteration,
        }

    if not touchstone_measurable:
        if kind is None:
            detail = (
                f"target unit {target.get('unit')!r} is not one of this module's "
                "recognized quantity units -- neither confirmed Touchstone-"
                "measurable (Hz/kHz/MHz/GHz, VSWR, dB) nor a known non-"
                "Touchstone quantity (dBi/dBd gain, deg/degrees pattern, "
                "% efficiency). Refusing to claim measurability for an "
                "unrecognized unit rather than guessing."
            )
        else:
            detail = (
                f"target unit {target.get('unit')!r} names a quantity a "
                "Touchstone S-parameter sweep -- this project's only "
                "measurement method (ADR-0012/ADR-0013) -- cannot report "
                "(e.g. antenna gain or radiation pattern need a range/"
                "chamber, not a bench VNA port)."
            )
        item["status"] = _BLOCKED
        item["flag"] = _flag(UnverifiableReason.QUANTITY_NOT_TOUCHSTONE_MEASURABLE, detail)
        if expected is not None:
            item["expected"] = expected
            item["method"] = _METHOD_FOR_PROVENANCE.get(expected["provenance"])
            item["notes"] = (
                f"{detail} Already evidenced this iteration via its "
                f"{expected['source_step']} decision ({expected['provenance']}); "
                "not part of this lab trip."
            )
        else:
            item["notes"] = detail
        return item

    # Touchstone-measurable from here on -- this requirement belongs on the
    # bench trip, regardless of whether a prediction was traced for it.
    item["method"] = _TOUCHSTONE
    if expected is None:
        if _FIELD_SOURCES.get(kind):
            detail = (
                "no ANALYSIS/SIMULATION/OPTIMIZATION decision recorded this "
                f"iteration produced a numeric value matching this "
                f"requirement's unit ({target.get('unit')!r}) -- either "
                "nothing of this quantity kind was computed yet, or it was "
                "computed in a different unit string than the target's own "
                "(this module never guesses a conversion, matching "
                "designs.success_score's own refusal). Run ANALYSIS/"
                "SIMULATION for this quantity before the bench trip if a "
                "prediction is wanted going in."
            )
        else:
            detail = (
                f"this requirement's unit ({target.get('unit')!r}) is "
                "Touchstone-measurable, but no step in this loop's current "
                "tool set computes that scalar yet (a known gap -- see this "
                "module's docstring, 'DESIGN QUESTION 2', VSWR/S-parameter "
                "gap). The bench measurement can still be taken; there is "
                "simply no expected value to compare it against going in."
            )
        item["status"] = _BLOCKED
        item["flag"] = _flag(UnverifiableReason.NO_ENGINEERING_RESULT_THIS_ITERATION, detail)
        item["notes"] = detail
    else:
        item["expected"] = expected
        item["notes"] = (
            f"expected value traced to this iteration's {expected['source_step']} "
            f"decision ({expected['provenance']})."
        )
    return item


def compile_lab_test_plan(
    state: DesignLoopState,
    requirements: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Compile a batched lab-test plan for `state` -- see this module's
    docstring for the full design rationale. Pure and read-only: takes
    `requirements` from `state.requirements` unless an explicit override is
    given (the tool-facing `compile_lab_test_plan_for_loop` passes a
    freshly-read one -- see "REQUIREMENTS FRESHNESS"), reads
    `state.decisions`/`state.iteration`/`state.loop_id`, and returns a new
    dict. Never mutates `state`, never writes to a database, never checks
    or requires an approval receipt -- safe to call at any point in the
    loop, on any `current_step`, including before a single step past
    REQUIREMENTS has been recorded.

    Raises `LabTestPlanError` for a malformed `requirements`/`target`
    shape (see that class's docstring) -- never for a requirement this
    module simply cannot verify, which is reported via each item's `flag`
    instead (see "DESIGN QUESTION 1")."""
    resolved_requirements = state.requirements if requirements is None else requirements
    if not isinstance(resolved_requirements, dict) or not resolved_requirements:
        raise LabTestPlanError(
            "requirements must be a non-empty dict keyed by requirement_id -- "
            f"got {resolved_requirements!r}"
        )

    iteration_decisions = [d for d in state.decisions if d.iteration == state.iteration]

    items: list[dict[str, Any]] = []
    for requirement_id, entry in resolved_requirements.items():
        if not isinstance(entry, dict):
            raise LabTestPlanError(
                f"requirement {requirement_id!r}'s entry must be a dict, got {type(entry).__name__}"
            )
        requirement_text = entry.get("requirement")
        if not isinstance(requirement_text, str) or not requirement_text.strip():
            raise LabTestPlanError(
                f"requirement {requirement_id!r} has no non-empty 'requirement' text field"
            )
        items.append(
            _compile_item(
                requirement_id, requirement_text, entry.get("target"), iteration_decisions
            )
        )

    flagged_requirement_ids = [item["requirement_id"] for item in items if item["flag"] is not None]

    return {
        "loop_id": state.loop_id,
        "iteration": state.iteration,
        "items": items,
        "flagged_requirement_ids": flagged_requirement_ids,
        "how_to_return_results": dict(_HOW_TO_RETURN_RESULTS),
        # Always None -- this dict compiles many decisions' worth of
        # evidence, it is not itself one MEASURED/SIMULATED/CALCULATED
        # reading. See this module's docstring, "OUTPUT SHAPE".
        "provenance": None,
    }


def _fetch_fresh_requirements(design_id: int) -> dict[str, Any]:
    """Read `designs.requirements` fresh for `design_id` -- see this
    module's docstring, "REQUIREMENTS FRESHNESS", for why
    `compile_lab_test_plan_for_loop` prefers this over the loop's own
    frozen `state["requirements"]` snapshot whenever a `design_id` is
    available. Read-only: opens a connection, reads, closes -- no
    transaction, nothing to commit or roll back."""
    # Imported lazily (function-local) so importing this module never
    # requires a live database driver to be configured -- the pure
    # `compile_lab_test_plan` above has no database dependency at all, and
    # every test that exercises it stays that way (tests/test_lab_test_
    # plan.py). Only this one I/O path touches designs.db.
    import designs.db as designs_db

    conn = designs_db.get_connection()
    try:
        design = designs_db.read_design(conn, design_id)
    finally:
        conn.close()
    if design is None:
        raise designs_db.UnknownDesignError(design_id)
    return design["requirements"]


def compile_lab_test_plan_for_loop(state: dict[str, Any]) -> dict[str, Any]:
    """The dict-in/dict-out, tool-facing entry point `agent/main.py`/
    `mcp_server/server.py` call -- see this module's docstring for the
    full design. `state` is a state dict from `start_new_design_loop`/
    `advance_design_loop_step`/`inspect_design_loop_state`
    (`orchestration.tooling`), or a bare `DesignLoopState.to_dict()` from
    `orchestration.design_loop.start_design_loop`/`advance_loop_step`
    directly.

    When `state` carries a `design_id` (i.e. it came from the `orchestration.
    tooling` wrappers, which back a loop with a real `designs` row), this
    re-reads that design's `requirements` fresh from the database rather
    than trusting the loop's own frozen `state['requirements']` snapshot --
    see "REQUIREMENTS FRESHNESS". Without a `design_id`, falls back to the
    loop's own `requirements` verbatim, honestly stale-if-stale.

    Read-only in every case: no write, no mutation of `state`, no approval
    receipt. Raises `LabTestPlanError` for the same malformed-input cases
    `compile_lab_test_plan` does, or `designs.db.UnknownDesignError` if
    `design_id` names no real `designs` row (should not happen for a state
    dict this project's own tools produced; a bug-shaped state deserves a
    loud failure, not a silently stale plan)."""
    loop_state = DesignLoopState.from_dict(state)
    design_id = state.get("design_id")
    requirements = _fetch_fresh_requirements(design_id) if design_id is not None else None
    return compile_lab_test_plan(loop_state, requirements=requirements)
