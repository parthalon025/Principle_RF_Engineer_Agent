"""Interpret a prose customer requirement into a confirmable requirement
target (issue #92; CONTEXT.md: Customer requirement, Success score,
Provenance; docs/adr/0003, docs/adr/0014).

A **customer requirement** frequently arrives as prose -- "drops connection
when mounted on the curved fuselage", "needs to work at 2.4 GHz without
losing gain" -- not as a number. Something has to turn that into a
**requirement target** (a value, a comparator, a unit, an optional
tolerance) before the not-yet-built #93 Success score (docs/adr/0014) has
anything to measure a design's progress against. This module is that
something.

CRITICAL ARCHITECTURAL POINT (per the issue -- read this twice, it shapes
every function below): the LLM never runs inside this module. In this
codebase the agent itself *is* the LLM -- it reads the customer's prose and
proposes a structured interpretation of it (a `value`/`comparator`/`unit`/
`tolerance`, or a decision that no defensible target exists) as plain tool
*arguments*. This module's job is strictly deterministic: validate the
shape of whatever the agent proposed, tag it `ASSUMED` (never anything
stronger -- it is still a reading of prose, not the customer's own stated
number), store it alongside the original prose, and provide the confirm
step a human uses to vouch for that reading before anything is scored
against it. A hidden model call inside a function this module documents as
"deterministic" would violate the same foundational rule
`rf_tools/calculations.py` and `docs/adr/0003` already rely on: the LLM is
never trusted to do the arithmetic/judgment a tool's caller is supposed to
have already done before calling it.

WHY PROVENANCE STAYS `ASSUMED` EVEN AFTER CONFIRMATION -- a deliberate
choice, not an oversight. CONTEXT.md's provenance vocabulary is fixed:
`MEASURED`, `SIMULATED`, `CALCULATED`, `MANUFACTURER-SPECIFIED`,
`LITERATURE-SUPPORTED`, `INFERRED`, `ASSUMED`, `UNKNOWN` -- there is no
`CONFIRMED` tier, and inventing one here would fork that vocabulary for a
single feature. A human confirming a target does not change what kind of
evidence it is (still nobody's measurement, simulation, or calculation --
still just a reading of the customer's own words); it changes how much a
downstream reader should trust that reading. This module carries that
second, genuinely different signal as its own explicit `target_status`
(`PROPOSED`/`CONFIRMED`/`UNSCOREABLE`) plus `confirmed_by`/`confirmed_at`,
rather than overloading `provenance` to mean two things at once. This is
also this ticket's one deliberate departure from `docs/adr/0003`'s
"propose, tag by confidence, no review gate" precedent for datasheet
component extraction: that ADR's own rejected-alternatives section gives
the reason review was skipped there -- nobody on staff could judge an
extracted RF number better than the extractor already tried to. A
*customer's own prose statement of their problem* is different: the
engineer reading it is not being asked to out-judge an RF measurement, they
are being asked to confirm the LLM understood what the customer meant --
exactly the kind of judgment call ADR-0003 itself says a human legitimately
can make. Hence a confirm step here where ADR-0003 explicitly has none.

TARGETS ATTACH WITHOUT A SCHEMA MIGRATION. `designs.validation.
validate_requirements` (verified by reading it, not assumed) only checks
that `requirements` is a dict keyed by `requirement_id`, each value a dict
carrying a non-empty `requirement` string -- it never rejects extra keys.
`designs.requirements` is already a JSONB column. So a target is simply
another key -- `target` -- living next to `requirement` inside a
requirement's own dict entry: `requirements[req_id] = {"requirement":
<prose>, "target": {...}}`. Both `create_design`'s existing shape check and
the JSONB column already tolerate this; nothing about the `designs` table
needs to change. This also satisfies "the original prose is preserved
alongside every target" for free -- prose and target are siblings in the
same dict, and `attach_target` below never touches `requirement`.

MODULE SHAPE. Two layers, same pure/I-O seam `designs.validation`/
`designs.db` already establish elsewhere in this package:

  - Pure, DB-free functions (`propose_target`, `mark_unscoreable`,
    `confirm_target`, `attach_target`) -- these carry all of the ticket's
    actual validation/tagging logic and are exhaustively unit-tested in
    `tests/test_requirement_targets.py` with no database needed.
  - Thin I/O wrappers (`propose_requirement_target`,
    `mark_requirement_unscoreable`, `confirm_requirement_target`) -- these
    are what `agent/main.py`/`mcp_server/server.py` actually wire up as
    tools. They read/write `designs.requirements` directly with their own
    small amount of raw SQL, mirroring `designs.db`'s no-ORM style,
    *deliberately not* added to `designs/db.py` or `designs/service.py`
    themselves -- issue #92's own file-territory rule scopes this ticket to
    a new module plus tool wiring only, since another agent is editing
    `orchestration/design_loop.py` in this same checkout concurrently and
    `designs/db.py`/`designs/service.py` are outside this ticket's assigned
    territory. `designs.db.get_connection`/`designs.db.UnknownDesignError`
    are reused as-is (not modified) so a missing design still fails the
    same documented way every other `designs` write does.

REJECTED ALTERNATIVE: a separate `requirement_targets` table. Considered
and rejected for the same reason the ticket itself calls out "without a
schema migration" -- the JSONB `requirements` column already holds
everything a target needs, `validate_requirements` already tolerates the
extra key, and a new table would need its own migration, its own foreign
key back to `designs`, and would split one requirement's prose and its
target across two places a reader has to join back together instead of one
dict they can read directly.
"""

from __future__ import annotations

import copy
import datetime
import math
from enum import StrEnum
from typing import Any

from psycopg.rows import dict_row
from psycopg.types.json import Json

from designs import db

ASSUMED = "ASSUMED"


class TargetComparator(StrEnum):
    """The comparator vocabulary a requirement target's numeric value is
    checked against (issue #92 acceptance criteria -- "at least a point
    target to hit, a minimum bound, and a maximum bound"). Named
    descriptively rather than as bare `==`/`>=`/`<=` symbols so a stored
    target reads clearly on its own and so the not-yet-built #93 Success
    score (docs/adr/0014) can dispatch on it without re-parsing an operator
    string:

    - `EQUALS`: a point target to hit (resonant frequency = 2.45 GHz) --
      #93 scores this by proximity to `value`.
    - `AT_LEAST`: a minimum bound (gain >= 5 dBi) -- #93 scores this by
      satisfaction (actual >= value) plus margin above it.
    - `AT_MOST`: a maximum bound (VSWR <= 2.0) -- #93 scores this by
      satisfaction (actual <= value) plus margin below it.
    """

    EQUALS = "EQUALS"
    AT_LEAST = "AT_LEAST"
    AT_MOST = "AT_MOST"


class TargetStatus(StrEnum):
    """Lifecycle status of one requirement target, carried as
    `target["target_status"]` -- named `target_status`, not `status`, so it
    never collides with the wrapper functions' own top-level `status` key
    (`propose_requirement_target` returns `{"status": "proposed", ...,
    "target": {"target_status": "PROPOSED", ...}}`) -- the same
    disambiguation `designs.service.verify_requirement` already uses
    (`status` vs. `verification_status`) for exactly this reason.

    - `PROPOSED`: `propose_target`'s output -- an as-yet-unconfirmed
      reading of the customer's prose.
    - `CONFIRMED`: `confirm_target`'s output -- a human has vouched that
      the proposed reading matches what the customer meant.
    - `UNSCOREABLE`: `mark_unscoreable`'s output -- the prose yields no
      defensible numeric target; `reason` explains why, and `value`/
      `comparator`/`unit`/`tolerance` are all `None` rather than a
      fabricated number.
    """

    PROPOSED = "PROPOSED"
    CONFIRMED = "CONFIRMED"
    UNSCOREABLE = "UNSCOREABLE"


class InvalidRequirementTargetError(ValueError):
    """Raised by `propose_target`/`mark_unscoreable`/`confirm_target` when
    the shape they were handed is wrong -- a non-numeric `value`, a
    `comparator` outside `TargetComparator`, an empty `unit`, a negative
    `tolerance`, an empty `reason`/`confirmed_by`, or an attempt to confirm
    something that isn't a `PROPOSED` target. Named and raised the same way
    `designs.validation.InvalidRequirementsError` is -- naming exactly
    what's wrong rather than a bare `TypeError`/`KeyError` -- so a caller
    (human or agent) gets a message it can act on."""


class UnknownRequirementError(Exception):
    """Raised by `attach_target` when `requirement_id` does not match any
    key already present in the `requirements` dict it was handed. A target
    can only attach to a requirement that already exists -- creating a
    stray requirement entry as a side effect of proposing a target would
    silently disagree with whatever `create_design` originally recorded as
    this design's requirement set."""

    def __init__(self, requirement_id: str):
        self.requirement_id = requirement_id
        super().__init__(
            f"requirement_id {requirement_id!r} does not match any key in this "
            "design's requirements -- a target can only attach to a requirement "
            "that already exists"
        )


def _require_finite_number(field_name: str, value: Any) -> float:
    """Return `value` as a `float`, raising `InvalidRequirementTargetError`
    naming `field_name` if it isn't a real, finite number. `bool` is
    explicitly excluded even though `isinstance(True, int)` is `True` in
    Python -- the same guard `designs.validation._iter_component_refs`
    already applies to `component_id`, for the same reason: a caller
    passing `True`/`False` almost certainly made a mistake, not a
    deliberate 1.0/0.0."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise InvalidRequirementTargetError(f"{field_name} must be a real number, got {value!r}")
    numeric = float(value)
    if not math.isfinite(numeric):
        raise InvalidRequirementTargetError(f"{field_name} must be finite, got {value!r}")
    return numeric


def _require_nonempty_string(field_name: str, value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise InvalidRequirementTargetError(
            f"{field_name} must be a non-empty string, got {value!r}"
        )
    return value


def propose_target(
    value: float,
    comparator: str,
    unit: str,
    tolerance: float | None = None,
) -> dict[str, Any]:
    """Validate and tag one proposed requirement target -- the deterministic
    half of "the agent reads the prose, this module validates and tags what
    it read." `value` must be a real, finite number; `comparator` must be
    one of `TargetComparator`'s three values; `unit` must be a non-empty
    string; `tolerance`, if given, must be a real, finite, non-negative
    number. Raises `InvalidRequirementTargetError` naming exactly which
    field is wrong -- never coerces or guesses a fixed-up value.

    Always returns a `target_status="PROPOSED"`, `provenance="ASSUMED"`
    dict -- this function has no way to know whether the value it was
    handed correctly reflects the customer's prose, only that it is
    *shaped* like a legitimate target; that is exactly why the result is
    `ASSUMED` and unconfirmed, never something a caller can skip
    `confirm_target` for.

    Calling this again for the same requirement (via
    `propose_requirement_target`, its I/O-layer counterpart) is how a
    proposal gets corrected or replaced before confirmation -- there is no
    separate "correct" function, since a correction is just a fresh
    proposal that `attach_target` fully replaces the requirement's previous
    `target` with (issue #92 acceptance criteria).
    """
    numeric_value = _require_finite_number("value", value)
    try:
        comparator_enum = TargetComparator(comparator)
    except ValueError:
        legal = ", ".join(c.value for c in TargetComparator)
        raise InvalidRequirementTargetError(
            f"comparator must be one of {legal}, got {comparator!r}"
        ) from None
    resolved_unit = _require_nonempty_string("unit", unit)

    numeric_tolerance: float | None = None
    if tolerance is not None:
        numeric_tolerance = _require_finite_number("tolerance", tolerance)
        if numeric_tolerance < 0:
            raise InvalidRequirementTargetError(
                f"tolerance must be >= 0 (a negative tolerance is not meaningful), "
                f"got {tolerance!r}"
            )

    return {
        "target_status": TargetStatus.PROPOSED.value,
        "provenance": ASSUMED,
        "value": numeric_value,
        "comparator": comparator_enum.value,
        "unit": resolved_unit,
        "tolerance": numeric_tolerance,
        "reason": None,
        "confirmed_by": None,
        "confirmed_at": None,
    }


def mark_unscoreable(reason: str) -> dict[str, Any]:
    """Record that a requirement's prose yields no defensible numeric
    target -- issue #92's "a requirement whose prose yields no defensible
    target is recorded as unscoreable with the reason stated; nothing is
    optimized toward an invented number." `reason` must be a non-empty
    string explaining why (e.g. "prose states a qualitative goal
    ('should feel robust when flexed') with no numeric bound of any kind");
    raises `InvalidRequirementTargetError` if it is missing or blank --
    `unscoreable` must always be explained, never a bare status flag.

    `value`/`comparator`/`unit`/`tolerance` are all `None` in the returned
    dict, deliberately -- this is the function that exists precisely so
    nothing downstream ever sees a fabricated number standing in for "we
    couldn't tell." `provenance` is still `ASSUMED`: the *decision* that
    this prose is unscoreable is itself a reading of that prose, carrying
    the same honest evidence tier as a successful proposal would.
    """
    resolved_reason = _require_nonempty_string("reason", reason)
    return {
        "target_status": TargetStatus.UNSCOREABLE.value,
        "provenance": ASSUMED,
        "value": None,
        "comparator": None,
        "unit": None,
        "tolerance": None,
        "reason": resolved_reason,
        "confirmed_by": None,
        "confirmed_at": None,
    }


def confirm_target(
    target: dict[str, Any],
    confirmed_by: str,
    confirmed_at: str | None = None,
) -> dict[str, Any]:
    """Confirm a proposed target, recording that it was confirmed and by
    whom (issue #92 acceptance criteria). `target` must be a dict shaped
    like `propose_target`'s own return value with
    `target_status == "PROPOSED"` -- confirming an `UNSCOREABLE` target (no
    number to confirm) or an already-`CONFIRMED` one (re-propose it first
    if it needs correcting -- confirming a stale confirmation again would
    silently discard whoever confirmed it originally) both raise
    `InvalidRequirementTargetError`, naming what was found instead.
    `confirmed_by` must be a non-empty string identifying who confirmed it
    (a person's name/handle -- this module does not defend against a caller
    passing something else, the same trust boundary `record_decision`'s
    caller-supplied fields already have).

    `confirmed_at` defaults to the real current UTC time (ISO-8601) and is
    only ever exposed as an explicit parameter for this function's own
    tests to get deterministic timestamps -- `confirm_requirement_target`
    (the tool-facing I/O wrapper) never accepts it as an argument, so an
    agent can never fabricate a confirmation timestamp.

    Returns a new dict (the input `target` is not mutated) with
    `target_status="CONFIRMED"`; every other field (`value`/`comparator`/
    `unit`/`tolerance`/`provenance`) is carried over unchanged -- see this
    module's docstring for why `provenance` deliberately stays `ASSUMED`
    even once confirmed.
    """
    if not isinstance(target, dict) or target.get("target_status") != TargetStatus.PROPOSED.value:
        found = target.get("target_status") if isinstance(target, dict) else type(target).__name__
        raise InvalidRequirementTargetError(
            "confirm_target requires a target dict with target_status "
            f"{TargetStatus.PROPOSED.value!r} (propose_target's own return shape) -- "
            f"got target_status={found!r}. An UNSCOREABLE target has no number to "
            "confirm; an already-CONFIRMED target should be re-proposed (corrected), "
            "not re-confirmed."
        )
    resolved_confirmed_by = _require_nonempty_string("confirmed_by", confirmed_by)
    resolved_confirmed_at = confirmed_at or datetime.datetime.now(datetime.UTC).isoformat()

    confirmed = dict(target)
    confirmed["target_status"] = TargetStatus.CONFIRMED.value
    confirmed["confirmed_by"] = resolved_confirmed_by
    confirmed["confirmed_at"] = resolved_confirmed_at
    return confirmed


def attach_target(
    requirements: dict[str, Any],
    requirement_id: str,
    target: dict[str, Any],
) -> dict[str, Any]:
    """Return a new `requirements` dict (never mutates its input) with
    `target` attached under `requirements[requirement_id]["target"]`,
    leaving every other key on that requirement entry -- `requirement`
    (the original prose) included -- exactly as it was. This is how "the
    original prose is preserved alongside every target" and "targets attach
    without a schema migration" both hold: `target` is just another key in
    the same dict `create_design` already validated and stored, sitting
    beside `requirement` rather than replacing or duplicating it.

    Raises `UnknownRequirementError` if `requirement_id` is not already a
    key in `requirements` -- a target can only attach to a requirement
    `create_design` actually recorded; this function never invents a new
    requirement entry as a side effect. Pure and DB-free, so it is directly
    testable against a hand-built `requirements` fixture -- the I/O wrapper
    functions below are the only callers that also touch a database.
    """
    if requirement_id not in requirements or not isinstance(requirements[requirement_id], dict):
        raise UnknownRequirementError(requirement_id)
    updated = copy.deepcopy(requirements)
    updated[requirement_id]["target"] = target
    return updated


# ---------------------------------------------------------------------------
# I/O layer: read/write a live design's `requirements` column directly.
#
# Deliberately NOT added to designs/db.py or designs/service.py -- see this
# module's docstring ("MODULE SHAPE") for why. Same connection-lifecycle
# discipline as designs/service.py: open a connection, validate, write,
# translate a domain exception into a structured `status`-tagged result,
# commit-or-rollback, always close.
# ---------------------------------------------------------------------------


def _fetch_requirements(conn: Any, design_id: int) -> dict[str, Any]:
    """Return the current `requirements` JSONB payload for `design_id`.
    Raises `designs.db.UnknownDesignError` (reused as-is, not redefined) if
    no `designs` row matches -- the same "no row matched is unambiguous"
    reasoning that class's own docstring already gives, since `designs.id`
    is a primary key."""
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT requirements FROM designs WHERE id = %s", (design_id,))
        row = cur.fetchone()
    if row is None:
        raise db.UnknownDesignError(design_id)
    return row["requirements"]


def _store_requirements(conn: Any, design_id: int, requirements: dict[str, Any]) -> None:
    """Overwrite `designs.requirements` for `design_id` with `requirements`
    and bump `updated_at` -- same pattern `designs.db.update_design_status`
    already uses for its own single-column update. Caller-owned transaction
    boundary: never commits itself."""
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE designs SET requirements = %s, updated_at = now() WHERE id = %s",
            (Json(requirements), design_id),
        )


def propose_requirement_target(
    design_id: int,
    requirement_id: str,
    value: float,
    comparator: str,
    unit: str,
    tolerance: float | None = None,
) -> dict[str, Any]:
    """Propose (or correct/replace an existing proposal for) one
    requirement's target on a stored design -- the tool-facing entry point
    `agent/main.py`/`mcp_server/server.py` wire up. Validates the proposed
    shape via `propose_target`, then attaches it to the design's
    `requirements[requirement_id]` via `attach_target`, replacing whatever
    `target` (if any -- `PROPOSED` or `CONFIRMED`) was there before. A
    design's requirements dict is the only place a target lives; re-calling
    this is how a proposal gets corrected before confirmation.

    Returns a structured `status`-tagged result rather than raising for
    every caller-facing failure mode: `"invalid_target"` (bad shape --
    `propose_target`'s own error), `"not_found"` (no such `design_id`), or
    `"unknown_requirement"` (`requirement_id` isn't one of this design's
    own requirement keys). On success: `{"status": "proposed", "design_id":
    ..., "requirement_id": ..., "target": {...}}`. A write that fails for
    any other reason still raises -- matches every other function in this
    package (`designs.service.create_design`, etc.).
    """
    try:
        target = propose_target(value=value, comparator=comparator, unit=unit, tolerance=tolerance)
    except InvalidRequirementTargetError as exc:
        return {"status": "invalid_target", "message": str(exc)}

    conn = db.get_connection()
    try:
        try:
            requirements = _fetch_requirements(conn, design_id)
            updated = attach_target(requirements, requirement_id, target)
        except db.UnknownDesignError as exc:
            conn.rollback()
            return {"status": "not_found", "design_id": exc.design_id}
        except UnknownRequirementError as exc:
            conn.rollback()
            return {
                "status": "unknown_requirement",
                "design_id": design_id,
                "requirement_id": requirement_id,
                "message": str(exc),
            }
        _store_requirements(conn, design_id, updated)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    return {
        "status": "proposed",
        "design_id": design_id,
        "requirement_id": requirement_id,
        "target": target,
    }


def mark_requirement_unscoreable(
    design_id: int,
    requirement_id: str,
    reason: str,
) -> dict[str, Any]:
    """Record that a requirement's prose yields no defensible target --
    the tool-facing counterpart to `propose_requirement_target` for the
    "unscoreable" outcome (issue #92 acceptance criteria). Same structured-
    result and connection-lifecycle contract as
    `propose_requirement_target`: `"invalid_target"` (empty/missing
    `reason`), `"not_found"`, `"unknown_requirement"`, or on success
    `{"status": "unscoreable", "design_id": ..., "requirement_id": ...,
    "target": {...}}` with `target["reason"]` carrying the stated reason.
    """
    try:
        target = mark_unscoreable(reason)
    except InvalidRequirementTargetError as exc:
        return {"status": "invalid_target", "message": str(exc)}

    conn = db.get_connection()
    try:
        try:
            requirements = _fetch_requirements(conn, design_id)
            updated = attach_target(requirements, requirement_id, target)
        except db.UnknownDesignError as exc:
            conn.rollback()
            return {"status": "not_found", "design_id": exc.design_id}
        except UnknownRequirementError as exc:
            conn.rollback()
            return {
                "status": "unknown_requirement",
                "design_id": design_id,
                "requirement_id": requirement_id,
                "message": str(exc),
            }
        _store_requirements(conn, design_id, updated)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    return {
        "status": "unscoreable",
        "design_id": design_id,
        "requirement_id": requirement_id,
        "target": target,
    }


def confirm_requirement_target(
    design_id: int,
    requirement_id: str,
    confirmed_by: str,
) -> dict[str, Any]:
    """Confirm the currently-proposed target on one of a design's
    requirements, recording that it was confirmed and by whom (issue #92
    acceptance criteria). `confirmed_at` is always the real current time --
    deliberately not a parameter here (see `confirm_target`'s docstring) so
    an agent can never supply a fabricated confirmation timestamp.

    Returns a structured `status`-tagged result: `"not_found"` (no such
    `design_id`), `"unknown_requirement"` (`requirement_id` isn't one of
    this design's requirement keys), `"no_proposal"` (this requirement has
    no `target` yet at all -- propose one first), `"invalid_target"` (the
    existing target is `UNSCOREABLE` or already `CONFIRMED` --
    `confirm_target`'s own error, naming which), or on success
    `{"status": "confirmed", "design_id": ..., "requirement_id": ...,
    "target": {...}}` with `target["confirmed_by"]`/`target["confirmed_at"]`
    set.
    """
    conn = db.get_connection()
    try:
        try:
            requirements = _fetch_requirements(conn, design_id)
        except db.UnknownDesignError as exc:
            conn.rollback()
            return {"status": "not_found", "design_id": exc.design_id}

        requirement_entry = requirements.get(requirement_id)
        if not isinstance(requirement_entry, dict):
            conn.rollback()
            return {
                "status": "unknown_requirement",
                "design_id": design_id,
                "requirement_id": requirement_id,
            }

        existing_target = requirement_entry.get("target")
        if existing_target is None:
            conn.rollback()
            return {
                "status": "no_proposal",
                "design_id": design_id,
                "requirement_id": requirement_id,
                "message": (
                    f"requirement_id {requirement_id!r} has no proposed target yet -- "
                    "call propose_requirement_target before confirming one"
                ),
            }

        try:
            confirmed = confirm_target(existing_target, confirmed_by=confirmed_by)
        except InvalidRequirementTargetError as exc:
            conn.rollback()
            return {"status": "invalid_target", "message": str(exc)}

        updated = attach_target(requirements, requirement_id, confirmed)
        _store_requirements(conn, design_id, updated)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    return {
        "status": "confirmed",
        "design_id": design_id,
        "requirement_id": requirement_id,
        "target": confirmed,
    }
