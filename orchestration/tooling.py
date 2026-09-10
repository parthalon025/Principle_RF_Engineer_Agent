"""The design-iteration loop's agent/MCP tool surface (issue #46) -- three
focused, JSON-in/JSON-out functions, per this ticket's own scope guidance
("a reasonable, narrow agent/MCP tool surface is: a tool to start a new
loop, a tool to advance to the next step, and a tool to inspect current
state -- three focused tools, not one that tries to do everything"). See
agent/main.py's start_design_loop/advance_design_loop_step/
inspect_design_loop_state tools (principal role) and
mcp_server/server.py's mirrors of the same.

This module also owns `reevaluate_capability_verdicts` (issue #322) -- a
fourth, read-only query over a design's already-persisted Considered-and-
dropped ledger, not a design-loop step tool in the sense above (it neither
starts, advances, nor even needs an in-flight loop state, only a
`design_id`), so it is not itself surfaced as one more agent/MCP step tool
by this ticket -- see that function's own docstring. `reevaluate_capability_
warnings` (issue #324) is its counterpart for the wholly separate Capability
warning mechanism (CONTEXT.md), same "read-only query, not a step tool"
shape -- see that function's own docstring for why it additionally takes a
`capability_configuration` argument that `reevaluate_capability_verdicts`
has no equivalent of.

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

REQUIREMENTS-DOCUMENT GATE (issue #325, docs/adr/0031). `advance_design_
loop_step`'s `requirements_document_status` parameter is a straight pass-
through to `design_loop.advance_loop_step`'s own parameter of the same
name -- this module adds no database read for it (design_loop.py's own
docstring already explains why ARCHITECTURE gates on it: the design's
Requirements document, issue #321, must be `CONFIRMED`). A caller
obtains the value the same way it obtains `approval` -- from a prior,
separate call, here `designs.requirements_document.
read_requirements_document(design_id)`'s `document_status` -- and passes
it straight through; this module does not fetch it automatically, the
same "no other change needed" property `approval` already has: nothing
about this function's OWN inputs changes between a refused and a
succeeding ARCHITECTURE call, only the ground truth the caller reads and
forwards.

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

REQUIREMENTS FRESHNESS (issue #100). `DesignLoopState.requirements` is
captured once, by `start_design_loop`, and `orchestration/design_loop.py`
never touches it again -- deliberately, since that module stays DB-free
(docs/adr/0011). Meanwhile `designs.requirement_targets.
propose_requirement_target`/`confirm_requirement_target`/
`mark_requirement_unscoreable` (#92) write their `target` key straight onto
the *persisted* `designs.requirements` JSONB column, via `design_id` -- a
completely different write path. Left alone, a loop's own held state goes
stale the instant one of those runs: `state["requirements"]` keeps showing
whatever targets existed at `start_design_loop` time, not a target proposed
or confirmed since. This module is where that gap closes (option 2 of the
three the issue lays out -- "closest to the existing architecture"):
`advance_design_loop_step` and `inspect_design_loop_state`, the two
functions that ever hand a state dict back to a caller after loop start,
both call `_fresh_requirements` first and substitute its result for
whatever `state`/`new_loop_state` carried in, whenever a `design_id` is
present -- falling back to that already-carried value, not raising, if
`design_id` names no real row (found during integration: `tests/
test_solver.py` deliberately never persists a design, by design; see
`_fresh_requirements`'s own docstring). `orchestration/design_loop.py`
gains no database awareness for
this, same as PERSISTENCE below -- the read lives in this module, the
layer that already talks to Postgres. Only the top-level `requirements`
field is replaced; `state["decisions"][0]` (the REQUIREMENTS decision
`start_design_loop` recorded) is never touched, so it keeps showing exactly
what was originally stated at loop start, not a later interpretation of it
(issue #100 acceptance criteria).
`orchestration/lab_test_plan.py`'s own `_fetch_fresh_requirements` predates
this fix and re-reads the same column for the same reason; it stays,
documented there as deliberate belt-and-braces rather than removed -- see
that module's docstring, "REQUIREMENTS FRESHNESS".
"""

from __future__ import annotations

from dataclasses import dataclass, replace
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
    capability_verdict_holds,
    capability_warning_holds,
    start_design_loop,
)

# LoopDecision.step (a DesignStep value) -> the real function name that
# produced its result, for engineering_results.tool_name -- but ONLY for
# the steps whose dispatch genuinely cannot vary. Deliberately NOT reusing
# designs/provenance.py's tool-name table: these are the design loop's own
# internal function names (record_external_measurement,
# correlate_simulation_measurement, ...), a different vocabulary than the
# ~65 agent/MCP tool names that table maps, and provenance for every one of
# these is passed explicitly from the loop's own already-computed
# LoopDecision.provenance (docs/adr/0011), never looked up from this table.
#
# ISSUE #334: ANALYSIS, SIMULATION and OPTIMIZATION ARE NOT IN THIS TABLE,
# because each of them dispatches per design family and so has no single
# answer. `orchestration/design_loop.py`'s `_handle_simulation` (#229/#241)
# runs Meep for ABSORBER, Palace for REFLECTION_PHASE/DIFFUSIVE and NEC2
# for PATCH; `_handle_analysis` (#239) picks a different closed form per
# family; `_handle_optimization` (#255/#267) chooses between the continuous
# patch-length search and the combinatorial symbol placement. This table
# used to answer for all three anyway -- every SIMULATION row said
# "run_nec2_simulation" and every ANALYSIS row said
# "patch_resonant_frequency_hz", whatever had actually run. In plain terms:
# the database recorded the name of an instrument that never touched the
# measurement, so anything counting results per solver (the cross-run
# simulator-trust ledger scoped in #150, say) counted Meep and Palace runs
# as NEC2. `_tool_name_for` reads the answer off the result instead; see
# its own docstring.
#
# MEASUREMENT maps to record_external_measurement (issue #89/ADR-0013).
# Issue #89 briefly needed a result-inspecting discriminator here, because
# _handle_measurement could route to either the live instrument or an
# externally-obtained Touchstone file and the step alone no longer said
# which. Ticket #90 removed the instrument-control package, making the
# external path the ONLY one _handle_measurement can take, so a straight
# per-step lookup is once again sufficient. CORRELATION likewise has a
# single handler with a single call in it.
#
# OPTIMIZATION is the one dispatching step that keeps an entry, and it is a
# NARROW fallback, not a default for the step: the continuous patch-length
# search (`optimization.rf_objectives.
# optimize_patch_length_for_target_frequency` -- what an unset or
# "CONTINUOUS" optimizer_class runs) is the one path here whose result
# states no `function` of its own, because its `method` field names the
# SEARCH ("parameter_sweep"/"grid_search"/"bayesian_optimize"), not the tool.
# The combinatorial path states its own function and overrides this.
_STEP_TO_TOOL_NAME: dict[str, str] = {
    DesignStep.OPTIMIZATION.value: "optimize_patch_length_for_target_frequency",
    DesignStep.MEASUREMENT.value: "record_external_measurement",
    DesignStep.CORRELATION.value: "correlate_simulation_measurement",
}


def _tool_name_for(decision: LoopDecision) -> str:
    """The real function name that produced `decision`'s result, for
    `engineering_results.tool_name` (issue #334).

    Read off the RESULT first -- `decision.result["function"]`, which every
    family-dispatching handler in `orchestration/design_loop.py` already
    records (`run_meep_simulation`, `run_palace_simulation`,
    `run_nec2_simulation`, `absorber_band_response`,
    `transmissive_absorber_band_response`, `patch_resonant_frequency_hz`,
    `combinatorial_symbol_placement`). The dispatching step itself is the
    only thing that knows which solver or closed form it reached for, so
    the flush asks it rather than re-deriving the answer from the step's
    name -- which is what it used to do, and what filed every Meep and
    Palace run under NEC2's name (see _STEP_TO_TOOL_NAME above).

    Falls back to the per-step table only for the steps listed there, whose
    dispatch cannot vary. A step that is neither in the table nor states its
    own `function` raises `DesignLoopPersistenceError` rather than guessing:
    that combination means a new per-family path was wired into
    design_loop.py without saying what it ran, the same "the flush mapping
    was never updated" bug `_flush_target_for`'s unknown-kind branch already
    fails loud for. Guessing is exactly the defect this function was fixed
    for, and a wrong `tool_name` is unrecoverable once committed, whereas
    this raise happens while `_flush_decisions` is still computing targets
    -- before it opens a connection -- so nothing is half-written and the
    caller's pre-call state stays the only valid one (docs/adr/0011).

    The one honest way an ordinary run can reach that raise is a state dict
    recorded by a revision that predates this fix and flushed by one that
    has it: a pre-#334 SIMULATION decision is a NEC2 run whose result never
    stated its function (every Meep/Palace result has carried the key since
    #229/#252). Such a state is held by its caller as JSON -- on disk via
    `orchestration/approval_cli.py`'s `--state`/`--out`, or in a
    `pending_approvals` row -- so the message below names the repair: add
    the key to the held decision rather than re-driving the loop. Inferring
    "no function stated" back to "must have been NEC2" is not done here,
    however historically true it happens to be: that inference IS the
    defect's shape, and the next path to forget the key would inherit it."""
    result = decision.result if isinstance(decision.result, dict) else {}
    stated = result.get("function")
    if isinstance(stated, str) and stated.strip():
        return stated
    table_name = _STEP_TO_TOOL_NAME.get(decision.step)
    if table_name is not None:
        return table_name
    raise DesignLoopPersistenceError(
        f"no tool name known for a {decision.step!r} decision: its result states no "
        "'function', and this step dispatches per design family (a different solver "
        "or closed form per family), so there is no single per-step name to fall back "
        "on. Nothing has been written -- this raise happens before the flush opens its "
        "connection, so the caller's pre-call state is still the only valid one. "
        "Either the orchestration/design_loop.py handler that produced this result "
        'does not record the function it ran (add e.g. "function": '
        '"run_meep_simulation" there), or this decision was recorded before issue '
        "#334 and the held state can be repaired by adding that key to it. Filing it "
        "under another solver's name is the defect #334 removed."
    )


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
    decision: LoopDecision,
    design_id: int,
    design_key: str,
    loop_id: str,
    iteration: int,
    design_family: str | None,
    design_family_canonical: str | None,
) -> _FlushTarget | None:
    """The designs.db call one LoopDecision translates to, or None for a
    decision kind with nothing to persist (`requirements` -- it already
    became the design's own `requirements`/`verification_items` at
    creation time, via start_new_design_loop's create_design call, not a
    decision_records/engineering_results/verification_items row).

    `design_family` (issue #167) is NOT read from `decision.input` here --
    it is computed once by `_flush_decisions`, across the whole batch being
    flushed, and handed down; see that function's own comment for why. It
    is passed through for every decision.kind unconditionally (harmless:
    only the architecture_decision/redesign_decision branch below actually
    uses it) so this function stays a straight decision-in/target-out
    mapping, matching every other branch here.

    `design_family_canonical` (issue #408; ADR-0037) is `design_family`'s
    companion, computed and carried forward by `_flush_decisions` the exact
    same way -- see that function's own "DESIGN_FAMILY CARRY-FORWARD"
    comment, which now covers both fields.
    """
    record_key = f"{design_key}-{loop_id}-iter{iteration}-{decision.step}"

    if decision.kind in ("architecture_decision", "redesign_decision"):
        return _FlushTarget(
            designs_db.record_decision,
            {
                "design_id": design_id,
                "record_key": record_key,
                "decision": decision.input["decision"],
                # issue #205: read the caller's actual alternatives instead
                # of hardcoding an empty list -- every other field on this
                # call reads from decision.input, this one silently didn't,
                # discarding the data at the flush with nothing downstream
                # able to recover it later. `.get`, not `[...]`: "decision"
                # and "rationale" are required keys on this decision kind,
                # "alternatives" is not, so a direct index would turn a
                # caller that legitimately supplied none into a KeyError.
                "alternatives": decision.input.get("alternatives", []),
                "rationale": decision.input["rationale"],
                "evidence": [],
                "design_family": design_family,
                "design_family_canonical": design_family_canonical,
                # Issue #322: the Considered-and-dropped ledger (ADR-0025),
                # already validated (reason_kind="capability-verdict"'s
                # issue #322 narrowing included) at the step that recorded
                # it -- orchestration.design_loop's
                # _validate_considered_and_dropped -- so this flush only
                # ever carries it through, the same ".get(..., [])" default
                # `alternatives` immediately above already established for
                # a caller who legitimately supplied none.
                "considered_and_dropped": decision.input.get("considered_and_dropped", []),
                # Issue #324: the Capability warning mechanism (CONTEXT.md) --
                # a WHOLLY SEPARATE key from considered_and_dropped
                # immediately above, already shape-validated at the step
                # that recorded it (orchestration.design_loop's
                # _validate_capability_warnings), so this flush only ever
                # carries it through, same ".get(..., [])" default as
                # `alternatives`/`considered_and_dropped` for a caller who
                # legitimately supplied none.
                "capability_warnings": decision.input.get("capability_warnings", []),
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
                "tool_name": _tool_name_for(decision),
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

    DESIGN_FAMILY CARRY-FORWARD (issue #167). `design_family` is a required
    field on `_handle_architecture`'s step_input (issue #161) but is NOT a
    field `_handle_redesign_decision` asks for at all -- the two handlers
    disagree on whether it's present in `decision.input` at flush time.
    Rather than reading `decision.input.get("design_family")` independently
    per-decision (which would leave every redesign_decision row's
    design_family permanently NULL, since nothing ever puts it in that
    step_input), this loop tracks the MOST RECENTLY STATED design_family as
    it walks `decisions` in their recorded order, and uses that running
    value for every architecture_decision/redesign_decision row. This is
    the conservative, information-preserving reading of what a
    REDESIGN_DECISION row's design_family means: STEP_ORDER (design_loop.py)
    puts ARCHITECTURE immediately before ANALYSIS..REDESIGN_DECISION in
    every iteration and routes `next_action="iterate"` back to ARCHITECTURE
    (never anywhere else), so by construction every decisions batch this
    function ever receives starts with that iteration's own
    architecture_decision -- the redesign_decision closing the SAME
    iteration is a decision about that already-declared family, not about
    an unrelated or unknown one, and recording it as NULL would silently
    discard information this module already has in hand. Two things this
    is NOT: (1) a cross-flush registry lookup -- nothing here reads a prior
    flush's persisted decision_records rows, only the batch already being
    flushed; a batch with no architecture_decision in it (not reachable
    today, per the paragraph above) simply carries `None` through, honestly
    reflecting that nothing in this flush says what family it was; (2) a
    silent override -- if design_loop.py ever grows a way for a
    REDESIGN_DECISION step_input to state its OWN `design_family` (an
    explicit change, not merely "no change"), that value wins over the
    carried-forward one for every decision recorded after it, same as an
    architecture_decision would.

    ISSUE #408 (ADR-0037) extends this SAME carry-forward to
    `design_family_canonical`. `_handle_architecture` (design_loop.py)
    stashes the registry's resolved name at
    `recorded["design_family_registry"]["canonical_name"]`, where `recorded`
    is that handler's `result` -- NOT its `input` (`advance_loop_step`
    stamps `LoopDecision.input` from the caller's own raw `step_input`
    unmodified; `design_family_registry` is a value `_handle_architecture`
    computes and echoes back, which is why it lands on `result` instead,
    same as every other handler's computed fields). So this reads
    `decision.result`, not `decision.input`, unlike the `design_family`
    carry-forward immediately above (a raw field the caller supplied, and
    therefore already present on `input`). `design_family_registry` is
    never present on a redesign_decision's `result` for the same reason
    `design_family` itself isn't on its `input`
    (`_handle_redesign_decision` doesn't ask for or compute either).
    Tracking it as its own running value, updated only when an
    architecture_decision's result actually carries the registry payload,
    keeps the two fields moving together without re-deriving the canonical
    name here: this loop only ever forwards what `_handle_architecture`
    already computed.
    """
    targets: list[_FlushTarget] = []
    current_design_family: str | None = None
    current_design_family_canonical: str | None = None
    for decision in decisions:
        stated_family = decision.input.get("design_family")
        if stated_family is not None:
            current_design_family = stated_family
        registry = decision.result.get("design_family_registry")
        if isinstance(registry, dict) and registry.get("canonical_name") is not None:
            current_design_family_canonical = registry["canonical_name"]
        target = _flush_target_for(
            decision,
            design_id,
            design_key,
            loop_id,
            iteration,
            current_design_family,
            current_design_family_canonical,
        )
        if target is not None:
            targets.append(target)

    conn = designs_db.get_connection()
    try:
        try:
            for target in targets:
                target.call(conn, **target.kwargs)
            # allow_nonsequential: the loop has walked ANALYSIS -> SIMULATION
            # -> OPTIMIZATION -> VERIFICATION in memory during this iteration
            # but persists only at the iteration boundary (ADR-0011), so the
            # column moves in one step where the lifecycle expects several.
            # The ordering check is relaxed for that; the RELEASED gate is not,
            # and this flush never writes RELEASED (final_status below is
            # ANALYSIS to iterate, PASS when done), nor may it move a design
            # out of a terminal status -- update_design_status enforces both
            # regardless of this flag.
            designs_db.update_design_status(
                conn,
                design_id=design_id,
                status=final_status.value,
                allow_nonsequential=True,
            )
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


def _fresh_requirements(design_id: int, fallback: dict[str, Any]) -> dict[str, Any]:
    """Re-read `designs.requirements` fresh from the database for
    `design_id` -- see this module's docstring, "REQUIREMENTS FRESHNESS"
    (issue #100). Reuses `designs_db.read_design` (the same function
    `orchestration/lab_test_plan.py`'s own belt-and-braces re-read already
    calls) rather than a new, leaner single-column query -- one already-
    open connection per step-advancing/inspecting call is not a real cost
    for a locally run, interactive design loop, and a second, parallel
    "just the requirements column" read path would be a second place to
    keep in sync with `read_design`'s own.

    Returns `fallback` -- the caller's own already-known requirements --
    instead of raising when `design_id` names no real `designs` row.
    Originally this raised `designs_db.UnknownDesignError` unconditionally,
    reasoning a missing row "should not happen for a state dict this
    module's own functions produced." That was wrong: `tests/test_solver.py`
    (issue #95, predating this ticket) deliberately builds a TOOLING-shaped
    state with a synthetic, never-persisted `design_id` specifically so its
    suite needs no live database -- an intentional, documented pattern this
    function cannot tell apart from a genuinely corrupted design_id, since
    both look identical from here (no matching row). Crashing an unrelated
    step-advance/inspect call over a side-channel freshness read finding
    nothing to refresh from is a worse failure mode than quietly keeping
    what the caller already had -- there is nowhere fresher to read from
    either way, and the caller's own value is not being asserted stale, only
    left exactly as honest as it was before this function ran."""
    conn = designs_db.get_connection()
    try:
        design = designs_db.read_design(conn, design_id)
    finally:
        conn.close()
    if design is None:
        return fallback
    return design["requirements"]


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
    requirements_document_status: str | None = None,
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

    `requirements_document_status` is REQUIRED (equal to `"CONFIRMED"`)
    whenever the loop's current step is ARCHITECTURE (issue #325, docs/
    adr/0031) -- the caller's own freshest read of `designs.
    requirements_document.read_requirements_document(design_id)`'s
    `document_status`. Passed straight through to `design_loop.
    advance_loop_step` unchanged; this module does not read that row
    itself (it stays exactly as DB-aware as design_loop.py's own docstring
    already says design_loop.py is not -- see that function's own
    docstring's "REQUIREMENTS-DOCUMENT GATE" section). Ignored for every
    other step.

    A `REDESIGN_DECISION` transition (docs/adr/0011) additionally flushes
    every decision recorded since the last flush to the database and
    moves `designs.status` -- see this module's docstring's "PERSISTENCE"
    section. This flush runs LAST, after the fresh-`requirements` read
    below succeeds, specifically so that a raise from EITHER step -- the
    read or the flush -- leaves `state` (which the caller still holds) as
    the only valid state, exactly as if the step had never advanced: no
    call to this function ever raises after writing something the caller
    has no way to know landed.

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

    new_loop_state = advance_loop_step(
        loop_state,
        step_input=step_input,
        approval=approval,
        requirements_document_status=requirements_document_status,
    )

    # issue #100: substitute the persisted designs.requirements column
    # fresh, rather than handing back new_loop_state's own carried copy --
    # see this module's docstring, "REQUIREMENTS FRESHNESS". design_id is
    # guaranteed non-None here (checked above), and only the top-level
    # `requirements` field changes -- `decisions[0]` (the REQUIREMENTS
    # decision) is untouched.
    #
    # Deliberately done BEFORE the REDESIGN_DECISION flush below (code
    # review on issue #100): _fresh_requirements has no data dependency on
    # the flush -- it neither reads nor writes designs.requirements -- so
    # reading it first means a failure here (e.g. the read's own DB
    # connection dying) happens before _flush_decisions ever runs, keeping
    # this function's "the caller's pre-call state remains the only valid
    # state" guarantee true for this failure mode too, not just a flush
    # failure. Reading it after, as a prior version of this function did,
    # meant a failure here could follow an already-committed flush: the
    # caller sees this call raise, retries with their still-held pre-call
    # state, and replays _flush_decisions with the same persisted_count --
    # which then fails on a record_key collision against the writes their
    # first, "failed" call actually made, with nothing in that error
    # pointing back at what really happened.
    new_loop_state = replace(
        new_loop_state,
        requirements=_fresh_requirements(design_id, fallback=new_loop_state.requirements),
    )

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
    advance the loop.

    When `state` carries a `design_id`, `requirements` is substituted with
    a fresh read of the persisted `designs.requirements` column (issue
    #100: see this module's docstring, "REQUIREMENTS FRESHNESS") -- so a
    target proposed or confirmed via `designs.requirement_targets` after
    `state` was captured is reflected here without the caller re-reading
    the design themselves. Everything else -- `decisions`, `current_step`,
    `design_id`/`design_key`/`persisted_decision_count` -- is passed
    through unchanged, read-only. Without a `design_id` (a bare
    `orchestration.design_loop.DesignLoopState.to_dict()`), this never
    touches the database and `requirements` is returned exactly as given,
    honestly stale-if-stale, since there is nowhere fresher to read from."""
    loop_state = DesignLoopState.from_dict(state)
    design_id = state.get("design_id")
    if design_id is not None:
        loop_state = replace(
            loop_state,
            requirements=_fresh_requirements(design_id, fallback=loop_state.requirements),
        )
    result = loop_state.to_dict()
    result["design_id"] = design_id
    result["design_key"] = state.get("design_key")
    result["persisted_decision_count"] = state.get("persisted_decision_count", 0)
    return result


def reevaluate_capability_verdicts(design_id: int) -> list[dict[str, Any]]:
    """Re-check every persisted `reason_kind="capability-verdict"`
    Considered-and-dropped ledger entry for `design_id` against that
    design's CURRENT `requirements` -- issue #322 acceptance criterion 2:
    "re-evaluated every run against the requirement's own current stated
    properties ... never against shop equipment." Not one of this module's
    three JSON-in/JSON-out design-loop tools (see this module's own
    docstring) -- a read-only query a caller runs whenever it wants a fresh
    view (e.g. before proposing a new ARCHITECTURE decision), same "fresh
    read, never a frozen snapshot" spirit as `_fresh_requirements` above,
    which this function reuses the same connection/read pattern from.

    Scans every `decision_records` row this design has -- ARCHITECTURE and
    REDESIGN_DECISION rows are the only ones that ever carry a
    `considered_and_dropped` ledger (orchestration.design_loop's step
    handlers), but this reads whatever is actually there rather than
    assuming which record_key suffixes exist. Non-capability-verdict
    entries (human-decision/engineering-judgment) are skipped entirely --
    ADR-0025's own rule is that only a capability-verdict ever expires.

    Returns one dict per capability-verdict entry found, `{"record_key",
    "family", "requirement_id", "validity_box_property", "status"}` where
    `status` is `"excluded"` (the entry's own violation still holds against
    the CURRENT requirement) or `"reconsiderable"` (it no longer does --
    the requirement's stated property changed, or vanished, since the
    entry was written). The actual check is `orchestration.design_loop.
    capability_verdict_holds` -- the SAME function that validated the entry
    at write time, reused rather than re-derived, so this re-evaluation
    cannot silently drift from the rule that justified writing it.

    Raises `DesignLoopPersistenceError` if `design_id` names no real
    `designs` row -- unlike `_fresh_requirements`'s deliberately tolerant
    "no fresher source, keep what the caller had" fallback (for a
    synthetic, never-persisted `design_id` in tests), there is no
    fallback value here for a caller who asked to re-evaluate a specific
    design's own persisted ledger and named one that does not exist.
    """
    conn = designs_db.get_connection()
    try:
        design = designs_db.read_design(conn, design_id)
    finally:
        conn.close()
    if design is None:
        raise DesignLoopPersistenceError(
            f"reevaluate_capability_verdicts: no design found for design_id={design_id!r}"
        )

    requirements = design["requirements"]
    results: list[dict[str, Any]] = []
    for row in design["decision_records"]:
        for entry in row.get("considered_and_dropped") or []:
            if entry.get("reason_kind") != "capability-verdict":
                continue
            still_holds = capability_verdict_holds(entry, requirements)
            status = "excluded" if still_holds else "reconsiderable"
            results.append(
                {
                    "record_key": row["record_key"],
                    "family": entry.get("family"),
                    "requirement_id": entry.get("requirement_id"),
                    "validity_box_property": entry.get("validity_box_property"),
                    "status": status,
                }
            )
    return results


def reevaluate_capability_warnings(
    design_id: int, capability_configuration: dict[str, Any]
) -> list[dict[str, Any]]:
    """Re-check every persisted `capability_warnings` entry for `design_id`
    against `capability_configuration` -- issue #324 acceptance criterion 2:
    "re-evaluated every run against the current manufacturing configuration
    and clears automatically when the configuration improves enough." A
    WHOLLY SEPARATE query from `reevaluate_capability_verdicts` above (issue
    #324 acceptance criterion 3): reads a different column
    (`capability_warnings`, never `considered_and_dropped`) and checks
    against a different axis entirely.

    Unlike `reevaluate_capability_verdicts`, which re-reads the design's own
    `requirements` straight from the database (a per-design fact this
    codebase already persists), `capability_configuration` is a caller-
    supplied dict of the CURRENT shop configuration -- e.g.
    `{"fabrication": {"min_feature_size_mm": 0.5}, "ink": {...}, "material":
    {...}}` -- because no Fabrication capability/Ink-property library/
    Material-property library "current selection" store exists in this
    codebase yet (see CONTEXT.md's entries for all three; `docs/
    fabrication-capability-and-ink-library-spec.md` is a future ticket's
    scope, not this one's). This is the deliberate reason this function's
    signature differs from its capability-verdict counterpart -- not an
    oversight.

    Scans every `decision_records` row this design has, same "read whatever
    is actually there" approach as `reevaluate_capability_verdicts`.

    Returns one dict per `capability_warnings` entry found, `{"record_key",
    "family", "capability_kind", "capability_property", "status"}` where
    `status` is `"unresolved"` (the entry's own gap still holds against
    `capability_configuration`) or `"resolved"` (the current configuration
    now meets the stated need). The actual check is `orchestration.
    design_loop.capability_warning_holds` -- reused, not re-derived, same
    "one place, not two" discipline as `reevaluate_capability_verdicts`'s
    own reuse of `capability_verdict_holds`.

    Raises `DesignLoopPersistenceError` if `design_id` names no real
    `designs` row -- same contract as `reevaluate_capability_verdicts`.
    """
    conn = designs_db.get_connection()
    try:
        design = designs_db.read_design(conn, design_id)
    finally:
        conn.close()
    if design is None:
        raise DesignLoopPersistenceError(
            f"reevaluate_capability_warnings: no design found for design_id={design_id!r}"
        )

    results: list[dict[str, Any]] = []
    for row in design["decision_records"]:
        for entry in row.get("capability_warnings") or []:
            still_holds = capability_warning_holds(entry, capability_configuration)
            status = "unresolved" if still_holds else "resolved"
            results.append(
                {
                    "record_key": row["record_key"],
                    "family": entry.get("family"),
                    "capability_kind": entry.get("capability_kind"),
                    "capability_property": entry.get("capability_property"),
                    "status": status,
                }
            )
    return results
