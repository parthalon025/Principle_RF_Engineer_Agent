"""Success score: how close a scoreable design-loop step's numeric result
sits to a confirmed-or-proposed requirement target (issue #93; CONTEXT.md
"Success score"; docs/adr/0014; direct input: designs/requirement_targets.py,
issue #92).

WHAT THIS MODULE ANSWERS. Once a requirement has been turned into a
`requirement target` (#92: a `value`/`comparator`/`unit`/optional
`tolerance`, tagged `target_status` and `provenance`) and a design-loop step
has produced a numeric result (an achieved resonant frequency from ANALYSIS,
a simulated gain, an optimized dimension, a verification measurement, a
correlation delta), an engineer wants one question answered without
re-deriving it by hand: how close is that number to what the requirement
actually asked for? `success_score` is that deterministic answer.
`ARCHITECTURE`/`REDESIGN_DECISION` are human judgment calls, not
measurements -- they get no score at all, per CONTEXT.md's "Success score"
entry and docs/adr/0014's own wording, which this module quotes rather than
reinterprets.

FOUNDATIONAL RULE THIS MODULE OBEYS: the LLM never does RF arithmetic
(`rf_tools/calculations.py`, `docs/adr/0003`, `docs/adr/0014`). Every branch
below is ordinary floating-point comparison; nothing here calls a model, and
every result is tagged `provenance="CALCULATED"` for exactly that reason.

------------------------------------------------------------------------
CRITICAL CORRECTION TO THE ORIGINAL TICKET TEXT -- read this before reusing
target["provenance"] alone anywhere downstream.

The ticket (and #87's spec behind it) says a score should "carry the
provenance of the target scored against", intending that a score computed
against an unconfirmed LLM guess must never read as a score against the
customer's real, human-vouched-for specification. Read literally, that
instruction is unsatisfiable: `designs/requirement_targets.py`'s own
docstring ("WHY PROVENANCE STAYS ASSUMED EVEN AFTER CONFIRMATION") argues at
length, and verifiably (`TargetStatus`/`propose_target`/`confirm_target`
below), that a requirement target's `provenance` is ALWAYS `"ASSUMED"` --
proposed or confirmed makes no difference, because CONTEXT.md's provenance
vocabulary has no `CONFIRMED` tier and confirming a reading changes how much
to trust it, not what kind of evidence it is. If this module carried only
`target["provenance"]`, a score against a raw, never-reviewed LLM proposal
and a score against an engineer-confirmed target would be *indistinguishable
strings* -- exactly the confusion the acceptance criterion exists to
prevent, reproduced by following its own literal wording.

The fix: this module's result carries BOTH `target_provenance` (always
`"ASSUMED"`, per #92) AND `target_status` (`"PROPOSED"` or `"CONFIRMED"` --
`"UNSCOREABLE"` never reaches a result, see below). `target_status` is the
field that actually carries the trust signal the criterion is protecting;
`target_provenance` is carried alongside it because the acceptance criterion
still names "provenance" explicitly and dropping it silently would look like
an oversight rather than the deliberate, documented substitution it is. A
downstream reader (#95's solver, or a human) that wants "was this vouched
for" must read `target_status`, not `target_provenance` -- both fields
travel with every score for exactly this reason, and
tests/test_success_score.py's
`test_score_carries_both_target_provenance_and_target_status_and_they_can_disagree_in_practice`
pins this down against a real PROPOSED-vs-CONFIRMED pair produced by #92's
own `propose_target`/`confirm_target`.

------------------------------------------------------------------------
DESIGN QUESTIONS THIS TICKET LEFT OPEN, AND WHAT WAS CHOSEN

1. THE POINT-TARGET FORMULA (`TargetComparator.EQUALS`, `score_point_target`).

   score_percent = clamp(1 - |actual - target| / scale, 0, 1) * 100

   where `scale` is `tolerance` when the caller supplied one, else
   `abs(target_value)` (a relative "percent of the target's own magnitude"
   fallback). Clamped to [0, 1] before scaling to a percentage so a result
   arbitrarily far from target reads as a flat 0%, never a nonsensical
   negative number that would misleadingly suggest "worse than completely
   missing." This is a continuous PROXIMITY metric, not a pass/fail line --
   deliberately: `EQUALS` is "a point target to hit" (#92's own
   `TargetComparator` docstring), and a caller wanting compliance did not
   ask a threshold question, so this function scores distance, not verdict.
   `tolerance`, when given, still yields a meaningful yes/no via the
   returned `target_met` field (`distance <= tolerance`) -- the score and
   the verdict are reported side by side rather than the verdict being
   thrown away.

   Rejected: scoring 100% for "anywhere inside tolerance" and only decaying
   outside it (a step-then-ramp shape). Rejected because that would make
   "dead on 2.45 GHz" and "2.499 GHz, right at the edge of a 50 MHz
   tolerance" score identically -- collapsing exactly the "how close" signal
   this ticket asks for into the same binary a threshold requirement already
   provides. `tolerance` here sets the DECAY SCALE, not a plateau.

   Tolerance-absent, target value zero: raises `SuccessScoreError` rather
   than dividing by zero or fabricating an epsilon scale. There is no
   "percent of the target's own magnitude" when that magnitude is exactly
   0 -- any nonzero deviation would be an undefined division, and inventing
   an arbitrary epsilon denominator would silently misrepresent a precision
   this function has no basis for choosing (the same refuse-rather-than-
   guess instinct `rf_tools/calculations.py`'s domain functions already
   apply to e.g. undefined ABCD/stability-circle conversions). A target
   truly centered on 0 (e.g. "phase error = 0 degrees") needs an explicit
   `tolerance` to be scoreable this way; #92's `propose_target` already
   accepts one.

2. THE THRESHOLD FORMULA (`AT_LEAST`/`AT_MOST`, `score_threshold`).

       AT_LEAST margin = actual - target_value   (positive == compliant)
       AT_MOST  margin = target_value - actual   (positive == compliant)

   `target_met = margin >= 0`. A met threshold SATURATES at 100% --
   deliberately, and regardless of how large the margin is. "Gain >= 5 dBi"
   met at 5.01 dBi and met at 20 dBi both score 100%: a threshold names a
   gate to clear, not a point to approach from above, and this ticket's own
   acceptance criteria says a threshold "met by a wide margin is not
   penalised for missing a point it never had" -- the flip side, made
   explicit here, is that it also gets no EXTRA credit for a margin nobody
   asked for. A threshold that is met AT ALL, even by the smallest possible
   positive margin, scores exactly the same 100% as one met by a mile --
   "not scored as if it barely scraped by."

   Rejected: letting score keep climbing above 100% (or an unbounded linear
   function of margin) for a large positive margin. Rejected because it
   implies a passing design is "more done" the further it overshoots a
   requirement it has already satisfied, which is not how spec compliance
   works, and would make two equally-compliant designs read as
   differently successful for a reason the requirement itself never stated.

   A threshold NOT met scores by the same clamped-proximity formula as the
   point-target case, applied to the shortfall (`-margin`) against the same
   `tolerance`-or-`abs(target_value)` scale -- reused, not reimplemented, via
   the shared `_clamped_proximity_percent` helper both formulas call. This
   gives partial credit that shrinks toward 0% as the shortfall grows,
   matching the "how close" spirit of the point-target case, rather than a
   flat 0% for every failing value regardless of how close it came --
   "margin" is exactly the acceptance criteria's own word, so it seemed
   wrong to compute one and then discard it back to a binary. The same
   zero-target-value-with-no-tolerance refusal from case 1 applies here too
   (see `_clamped_proximity_percent`).

3. UNIT HANDLING: REFUSE ON MISMATCH, NEVER GUESS A CONVERSION.

   `success_score` requires the caller's `actual_unit` to match
   `target["unit"]` by exact string equality, and raises
   `SuccessScoreError` naming both units on any mismatch -- it never
   attempts a unit conversion (Hz<->GHz, dBi<->linear, etc.). Consistent
   with this codebase's repeated refuse-rather-than-guess habit
   (`rf_tools/correlation.py`'s port-count/S-parameter-shape refusals,
   `designs/requirement_targets.py`'s validate-or-raise-naming-the-field
   convention): guessing a unit conversion is exactly the kind of RF
   domain judgment this project's foundational rule keeps out of
   deterministic code without an explicit, caller-supplied instruction. A
   caller comparing a result recorded in different units must convert it
   to the target's own unit (e.g. via this module's sibling
   `rf_tools/calculations.py` conversions where one exists) BEFORE calling
   `success_score` -- this module does not do that conversion silently on
   the caller's behalf. Rejected alternative: ignoring units entirely (score
   the raw numbers regardless of unit). Rejected because a target of
   "5 dBi" and an actual result of "5" (linear, dimensionless) would then
   silently score as a perfect match -- exactly the kind of unlabeled
   footgun the project's provenance/unit discipline exists to prevent.

------------------------------------------------------------------------
SCOREABLE STEPS: A DELIBERATELY DUPLICATED, NOT IMPORTED, CLOSED VOCABULARY.

CONTEXT.md's "Success score" entry and docs/adr/0014 both name the exact
same five steps as scoreable -- `ANALYSIS`/`SIMULATION`/`OPTIMIZATION`/
`VERIFICATION`/`CORRELATION` -- and both name `ARCHITECTURE`/
`REDESIGN_DECISION` as the human-judgment steps that get no score. Notably,
`MEASUREMENT` and `REQUIREMENTS` -- two of the loop's other seven steps --
appear in NEITHER list; this module honors that omission rather than
"fixing" it, since CONTEXT.md's own definition is the spec here, not this
module's opinion about what a `MEASUREMENT` result could in principle
support.

This module defines its own `SCOREABLE_STEPS`/`JUDGMENT_STEPS` string
frozensets (lower-case, matching `orchestration.design_loop.DesignStep`'s
own string values) rather than importing `DesignStep` from
`orchestration.design_loop`. This is deliberate, not an oversight:
`orchestration/design_loop.py` already imports `rf_tools.calculations` and
`rf_tools.correlation` -- `rf_tools` sits BELOW `orchestration` in this
project's dependency direction. Importing `DesignStep` back out of
`orchestration` into `rf_tools` would invert that direction and risk a
circular import the moment `orchestration/design_loop.py` (or anything it
imports) ever needed something from this module. A five-string set
duplicating five string literals that are already effectively frozen (a new
loop step is a rare, deliberate, whole-codebase change per
`orchestration/design_loop.py`'s own "NO MANUFACTURING-RELEASE PATH"
section) is a small, honestly-documented cost next to that risk.

`TargetComparator`/`TargetStatus`, by contrast, ARE imported directly from
`designs.requirement_targets` rather than re-declared here. That import
carries no such risk -- `designs/requirement_targets.py` imports only
`designs.db` (never `rf_tools`), and it is this module's direct, documented
input (#92's own docstring calls out #93 by name as the reader of its
output). Re-declaring a second, parallel `TargetComparator`/`TargetStatus`
here would risk exactly the vocabulary-fork CONTEXT.md's provenance section
warns against for its own enum; reusing the one #92 already defined and
tested is the safer, smaller choice.

------------------------------------------------------------------------
TOOL SURFACE: DELIBERATELY NOT WIRED AS AN AGENT/MCP TOOL.

`success_score` is a pure function, exported from `rf_tools/` for #95's
not-yet-built solver to import and call directly -- the ticket's own
placement guidance offers this as a defensible option ("A pure scoring
function is also defensible as internal-only, consumed by #95's solver
rather than called directly"), and this module takes it. Reasoning: nothing
in the current 9-step `orchestration/design_loop.py` state machine (as of
this ticket) ever calls a scoring function -- there is no recorded
`LoopDecision` result this function would read today, only whatever numbers
an agent typed into a raw tool call by hand, disconnected from any actual
evidence trail. That is precisely the kind of unanchored arithmetic surface
docs/adr/0014 describes #95's solver as existing to prevent: the solver, once
built, is the trusted caller that pulls `target` and `actual_value` from a
design's own recorded decisions before ever calling this function. Wiring a
standalone `success_score` tool now would hand an agent a shortcut around
that discipline before the caller meant to enforce it exists. `tests/
test_success_score.py` exercises this module directly, matching `tests/
test_calculations.py`'s own precedent of testing `rf_tools/` functions that
are not themselves individually exposed as tools.
"""

from __future__ import annotations

import math
from typing import Any

from designs.requirement_targets import TargetComparator, TargetStatus

CALCULATED = "CALCULATED"
INFERRED = "INFERRED"

# Mirrors orchestration.design_loop.DesignStep's own string values --
# deliberately duplicated, not imported. See this module's docstring
# ("SCOREABLE STEPS") for why.
SCOREABLE_STEPS = frozenset(
    {"analysis", "simulation", "optimization", "verification", "correlation"}
)
JUDGMENT_STEPS = frozenset({"architecture", "redesign_decision"})


class SuccessScoreError(ValueError):
    """Raised by `success_score`/`score_point_target`/`score_threshold` when
    a Success score genuinely cannot be produced: a human-judgment step
    (`ARCHITECTURE`/`REDESIGN_DECISION`) or any step outside this project's
    closed scoreable-step vocabulary, a target recorded `UNSCOREABLE`, a
    malformed target shape (bad `comparator`, non-numeric `value`/
    `tolerance`), a non-numeric `actual_value`, an `actual_unit` that does
    not match the target's own `unit`, or an attempt to score
    tolerance-absent proximity against a zero-valued target. A `ValueError`
    subclass, matching `rf_tools.correlation.CorrelationError`'s and
    `orchestration.design_loop.DesignLoopValidationError`'s own convention
    of a domain-specific `ValueError` subclass naming exactly what's wrong,
    rather than a bare `TypeError`/`KeyError`/`ZeroDivisionError`."""


def _require_finite_number(field_name: str, value: Any) -> float:
    """Same guard `designs.requirement_targets._require_finite_number` uses
    (`bool` excluded even though `isinstance(True, int)` is `True` in
    Python) -- reimplemented locally rather than importing that module's
    private helper across a module boundary, matching
    `rf_tools/correlation.py`'s own precedent of small, module-local
    validation helpers (its `_parse_complex` is not shared with
    `rf_tools/touchstone.py` either)."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise SuccessScoreError(f"{field_name} must be a real number, got {value!r}")
    numeric = float(value)
    if not math.isfinite(numeric):
        raise SuccessScoreError(f"{field_name} must be finite, got {value!r}")
    return numeric


def _require_nonempty_string(field_name: str, value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SuccessScoreError(f"{field_name} must be a non-empty string, got {value!r}")
    return value


def _clamped_proximity_percent(
    *, distance: float, tolerance: float | None, target_value: float
) -> float:
    """Shared core of both formulas above: `clamp(1 - distance/scale, 0, 1)
    * 100`, where `scale` is `tolerance` when supplied, else
    `abs(target_value)`. `distance` must already be non-negative (an
    absolute deviation for the point-target case, a shortfall for the
    threshold case). See this module's docstring ("DESIGN QUESTIONS") for
    why `tolerance` sets a decay scale rather than a plateau, and why a
    zero-valued target with no `tolerance` raises instead of dividing.
    """
    if tolerance is not None:
        # tolerance == 0 means "must hit the target exactly" -- handled
        # explicitly rather than via 1/0.0, since Python's float division
        # raises ZeroDivisionError rather than producing IEEE infinity.
        ratio = (0.0 if distance == 0 else math.inf) if tolerance == 0 else distance / tolerance
    else:
        if target_value == 0:
            raise SuccessScoreError(
                "cannot score proximity against a zero-valued target without an "
                "explicit tolerance -- there is no 'percent of the target's own "
                "magnitude' scale to normalize distance against when that "
                "magnitude is exactly 0 (dividing by it is undefined, and an "
                "arbitrary epsilon denominator would misrepresent a precision "
                "this function has no basis for choosing). Supply an explicit "
                "tolerance for a requirement target whose value is 0."
            )
        ratio = distance / abs(target_value)
    return max(0.0, min(1.0, 1.0 - ratio)) * 100.0


def score_point_target(
    target_value: float,
    actual_value: float,
    tolerance: float | None,
) -> dict[str, Any]:
    """Score a point-target (`TargetComparator.EQUALS`) requirement --
    "resonant frequency = 2.45 GHz" -- by proximity. See this module's
    docstring ("THE POINT-TARGET FORMULA") for the formula and what was
    considered and rejected. Pure function of its three numeric arguments;
    raises `SuccessScoreError` if `tolerance` is `None` and `target_value`
    is exactly 0 (no scale to normalize against).

    Returns `{"score_percent": float in [0, 100], "target_met": bool |
    None, "deviation": float}`. `deviation` is the signed `actual_value -
    target_value` (positive means the actual result overshot the target;
    negative means it undershot). `target_met` is `distance <= tolerance`
    when `tolerance` was supplied, else `None` -- a point target with no
    stated tolerance has a proximity score but no defined pass/fail line.
    """
    deviation = actual_value - target_value
    distance = abs(deviation)
    score_percent = _clamped_proximity_percent(
        distance=distance, tolerance=tolerance, target_value=target_value
    )
    target_met = None if tolerance is None else distance <= tolerance
    return {"score_percent": score_percent, "target_met": target_met, "deviation": deviation}


def score_threshold(
    comparator: str,
    target_value: float,
    actual_value: float,
    tolerance: float | None,
) -> dict[str, Any]:
    """Score a threshold requirement -- `AT_LEAST` ("gain >= 5 dBi") or
    `AT_MOST` ("VSWR <= 2.0") -- by satisfaction plus margin. See this
    module's docstring ("THE THRESHOLD FORMULA") for the formula and what
    was considered and rejected. Pure function of its four arguments;
    raises `SuccessScoreError` if `comparator` is not `"AT_LEAST"`/
    `"AT_MOST"` (`EQUALS` is a point target -- use `score_point_target`
    instead), or (when the threshold is not met and `tolerance` is `None`)
    if `target_value` is exactly 0.

    Returns `{"score_percent": float in [0, 100], "target_met": bool,
    "margin": float}`. `margin` is signed so that a POSITIVE value always
    means "compliant" regardless of direction: `actual - target_value` for
    `AT_LEAST`, `target_value - actual` for `AT_MOST`. A met threshold
    (`margin >= 0`) always scores exactly 100%, however large `margin` is
    -- see the docstring for why overshoot earns no extra credit.
    """
    try:
        comparator_enum = TargetComparator(comparator)
    except ValueError:
        raise SuccessScoreError(
            f"score_threshold requires comparator to be one of "
            f"{TargetComparator.AT_LEAST.value!r}/{TargetComparator.AT_MOST.value!r}, "
            f"got {comparator!r}"
        ) from None

    if comparator_enum is TargetComparator.AT_LEAST:
        margin = actual_value - target_value
    elif comparator_enum is TargetComparator.AT_MOST:
        margin = target_value - actual_value
    else:
        raise SuccessScoreError(
            f"score_threshold only scores {TargetComparator.AT_LEAST.value!r}/"
            f"{TargetComparator.AT_MOST.value!r} comparators -- "
            f"{TargetComparator.EQUALS.value!r} is a point target, scored by "
            "score_point_target instead."
        )

    target_met = margin >= 0
    if target_met:
        score_percent = 100.0
    else:
        score_percent = _clamped_proximity_percent(
            distance=-margin, tolerance=tolerance, target_value=target_value
        )
    return {"score_percent": score_percent, "target_met": target_met, "margin": margin}


def _require_scoreable_step(step: Any) -> str:
    if not isinstance(step, str) or not step.strip():
        raise SuccessScoreError(f"step must be a non-empty string, got {step!r}")
    normalized = step.strip().lower()
    if normalized in JUDGMENT_STEPS:
        raise SuccessScoreError(
            f"step {step!r} is a human-judgment step (ARCHITECTURE/"
            "REDESIGN_DECISION) -- these record a decision, not a measurement, "
            "so there is no numeric result to be close to and none is scored "
            "(CONTEXT.md 'Success score'; docs/adr/0014)."
        )
    if normalized not in SCOREABLE_STEPS:
        raise SuccessScoreError(
            f"step {step!r} is not one of this project's scoreable design-loop "
            f"steps ({sorted(SCOREABLE_STEPS)}, per CONTEXT.md's 'Success score' "
            "entry and docs/adr/0014) -- only a step whose result is numeric "
            "and directly comparable to a stated requirement target is scored "
            "this way."
        )
    return normalized


def _require_scoreable_target(target: Any) -> dict[str, Any]:
    if not isinstance(target, dict):
        raise SuccessScoreError(
            "target must be a dict shaped like designs.requirement_targets's "
            f"propose_target/confirm_target output, got {type(target).__name__}"
        )
    status = target.get("target_status")
    if status == TargetStatus.UNSCOREABLE.value:
        raise SuccessScoreError(
            f"target is recorded UNSCOREABLE (reason: {target.get('reason')!r}) -- "
            "no defensible numeric target was ever recorded for this requirement "
            "(designs.requirement_targets.mark_unscoreable), so nothing is scored "
            "against it. Fabricating a number here would be worse than reporting "
            "none, per this ticket's own acceptance criteria."
        )
    if status not in (TargetStatus.PROPOSED.value, TargetStatus.CONFIRMED.value):
        raise SuccessScoreError(
            "target.target_status must be one of "
            f"{TargetStatus.PROPOSED.value!r}/{TargetStatus.CONFIRMED.value!r}/"
            f"{TargetStatus.UNSCOREABLE.value!r} (designs.requirement_targets."
            f"TargetStatus), got {status!r}"
        )
    return target


def success_score(
    step: str,
    target: dict[str, Any],
    actual_value: float,
    actual_unit: str,
    note: str | None = None,
) -> dict[str, Any]:
    """Score a scoreable design-loop step's numeric result against a
    (proposed or confirmed) requirement target. This is the function
    `rf_tools/success_score.py` exists for -- see the module docstring for
    the formulas, the unit-mismatch refusal, the closed step vocabulary, and
    (most importantly) why the returned result carries BOTH
    `target_provenance` and `target_status` rather than provenance alone.

    Arguments:
      - `step`: the design-loop step name (`orchestration.design_loop.
        DesignStep`'s own lower-case string values, e.g. `"analysis"`)
        whose result produced `actual_value`. Raises `SuccessScoreError`
        for a human-judgment step (`"architecture"`/`"redesign_decision"`)
        or any step outside `SCOREABLE_STEPS`.
      - `target`: a dict shaped like `designs.requirement_targets.
        propose_target`/`confirm_target`'s own return value. Raises
        `SuccessScoreError` if `target["target_status"]` is `"UNSCOREABLE"`
        (no number was ever recorded) or malformed.
      - `actual_value` / `actual_unit`: the scoreable step's own numeric
        result and its unit. `actual_unit` must equal `target["unit"]`
        exactly, or `SuccessScoreError` is raised -- see the module
        docstring's "UNIT HANDLING" section for why this never silently
        converts.
      - `note`: an optional narrative string (e.g. a manufacturability
        caveat a formula can't capture). When given, it is tagged
        `note_provenance="INFERRED"` in the result -- an LLM-authored aside,
        never a substitute for `score_percent` (docs/adr/0014's own
        wording). `None` when omitted; never a fabricated placeholder note.

    Returns a dict:
      - `provenance`: always `"CALCULATED"` -- this score is deterministic
        arithmetic over already-recorded numbers, never an LLM estimate
        (docs/adr/0014).
      - `target_provenance`: `target["provenance"]`, always `"ASSUMED"` per
        #92 -- carried for the acceptance criterion's literal wording; see
        the module docstring's "CRITICAL CORRECTION" section for why this
        alone is NOT the trust signal to read.
      - `target_status`: `target["target_status"]` (`"PROPOSED"` or
        `"CONFIRMED"` -- `"UNSCOREABLE"` never reaches this point) -- THIS
        is the field that says whether a human vouched for the target this
        score was computed against.
      - `step`: the normalized (lower-cased) step name.
      - `comparator`: `target["comparator"]`.
      - `unit` / `target_value` / `tolerance`: carried straight from
        `target`, for a reader who has only this result dict at hand.
      - `actual_value`: the value that was scored.
      - `score_percent`: the Success score itself, `float` in `[0, 100]`.
      - `target_met`: `bool | None` -- see `score_point_target`/
        `score_threshold` for exactly when this is `None`.
      - `deviation`: signed `actual - target_value`, only for `EQUALS`
        (`None` for threshold comparators).
      - `margin`: signed compliance margin, only for `AT_LEAST`/`AT_MOST`
        (`None` for `EQUALS`) -- see `score_threshold` for its sign
        convention.
      - `note` / `note_provenance`: the optional narrative note and its
        `"INFERRED"` tag, or `None`/`None` when no note was given.

    Raises `SuccessScoreError` for every refusal case named above. A pure
    function of its arguments -- no database, no loop state, no I/O -- so
    calling it twice with the same arguments always returns an equal dict
    (see `tests/test_success_score.py`'s determinism test).
    """
    normalized_step = _require_scoreable_step(step)
    scoreable_target = _require_scoreable_target(target)

    target_value = _require_finite_number("target.value", scoreable_target.get("value"))
    try:
        comparator_enum = TargetComparator(scoreable_target.get("comparator"))
    except ValueError:
        legal = ", ".join(c.value for c in TargetComparator)
        raise SuccessScoreError(
            f"target.comparator must be one of {legal}, got {scoreable_target.get('comparator')!r}"
        ) from None
    unit = _require_nonempty_string("target.unit", scoreable_target.get("unit"))

    raw_tolerance = scoreable_target.get("tolerance")
    tolerance: float | None = None
    if raw_tolerance is not None:
        tolerance = _require_finite_number("target.tolerance", raw_tolerance)
        if tolerance < 0:
            raise SuccessScoreError(
                f"target.tolerance must be >= 0 (a negative tolerance is not "
                f"meaningful), got {raw_tolerance!r}"
            )

    resolved_actual_value = _require_finite_number("actual_value", actual_value)
    resolved_actual_unit = _require_nonempty_string("actual_unit", actual_unit)
    if resolved_actual_unit != unit:
        raise SuccessScoreError(
            f"actual_unit {resolved_actual_unit!r} does not match target unit "
            f"{unit!r} -- refusing to score across mismatched units rather than "
            "guessing at a conversion. Convert actual_value to the target's own "
            "unit before calling success_score (see this module's docstring, "
            "'UNIT HANDLING', for why)."
        )

    resolved_note = None if note is None else _require_nonempty_string("note", note)

    if comparator_enum is TargetComparator.EQUALS:
        formula = score_point_target(
            target_value=target_value, actual_value=resolved_actual_value, tolerance=tolerance
        )
        deviation: float | None = formula["deviation"]
        margin: float | None = None
    else:
        formula = score_threshold(
            comparator=comparator_enum.value,
            target_value=target_value,
            actual_value=resolved_actual_value,
            tolerance=tolerance,
        )
        deviation = None
        margin = formula["margin"]

    return {
        "provenance": CALCULATED,
        "target_provenance": scoreable_target.get("provenance"),
        "target_status": scoreable_target.get("target_status"),
        "step": normalized_step,
        "comparator": comparator_enum.value,
        "unit": unit,
        "target_value": target_value,
        "tolerance": tolerance,
        "actual_value": resolved_actual_value,
        "score_percent": formula["score_percent"],
        "target_met": formula["target_met"],
        "deviation": deviation,
        "margin": margin,
        "note": resolved_note,
        "note_provenance": INFERRED if resolved_note is not None else None,
    }
