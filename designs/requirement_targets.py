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
    `propose_intended_effect`/`attach_intent` (issue #323, ADR-0030) join
    this same pure layer: `attach_target`'s direct sibling for the other
    key ADR-0030 puts "beside `requirement` and `target`" on a requirement
    entry, called only from `designs.requirements_document.
    extract_requirement_fields` once a Requirements document reaches
    `CONFIRMED` (docs/adr/0034) -- never as a standalone tool argument.
    `propose_host_ground_plane`/`confirm_host_ground_plane`/
    `attach_host_ground_plane` (issue #484, ADR-0017) join the pure layer
    as a third sibling, living at `requirements[requirement_id]
    ["host_ground_plane"]`: ADR-0017 lets a design skip the base printed
    layer's own reflector only when a Customer requirement *explicitly
    asserts* the host surface is a confirmed, reliable ground plane --
    "asserted, never inferred" -- so this key is modelled on `target`'s
    PROPOSED-then-CONFIRMED lifecycle, not `intended_effect`'s one-shot
    shape: a bare, unconfirmed assertion is not enough to skip anything.
  - Thin I/O wrappers (`propose_requirement_target`,
    `mark_requirement_unscoreable`, `confirm_requirement_target`,
    `propose_requirement_host_ground_plane`,
    `confirm_requirement_host_ground_plane`) -- these
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


class GroundPlaneStatus(StrEnum):
    """Lifecycle status of one host ground-plane assertion, carried as
    `host_ground_plane["ground_plane_status"]` -- named `ground_plane_status`,
    not `status`, for the identical reason `TargetStatus` is carried as
    `target_status`: so it never collides with the wrapper functions' own
    top-level `status` key (`propose_requirement_host_ground_plane` returns
    `{"status": "proposed", ..., "host_ground_plane": {"ground_plane_status":
    "PROPOSED", ...}}`).

    - `PROPOSED`: `propose_host_ground_plane`'s output -- an as-yet-
      unconfirmed reading of the customer's prose ("the platform is a solid
      aluminum wing" read as "host asserts confirmed ground plane").
    - `CONFIRMED`: `confirm_host_ground_plane`'s output -- a human has
      vouched that the proposed reading matches what the customer meant.
      Per ADR-0017 ("asserted, never inferred"), only a `CONFIRMED`
      assertion may ever let the design loop skip the base printed layer's
      own reflector; a bare `PROPOSED` reading is not enough.

    There is no `UNSCOREABLE`-equivalent third state here the way
    `TargetStatus` has one: a requirement's prose either does or doesn't
    assert something about the host's ground-plane reliability, and
    "doesn't" is simply never calling `propose_host_ground_plane` for that
    requirement at all -- the same way a requirement with no stated
    `intended_effect` just never gets one attached, and ADR-0017's own
    default (the base layer supplies its own reflector) already covers
    silence without needing a stored value to say so.
    """

    PROPOSED = "PROPOSED"
    CONFIRMED = "CONFIRMED"


class InvalidHostGroundPlaneAssertionError(ValueError):
    """Raised by `propose_host_ground_plane`/`confirm_host_ground_plane`
    when the shape they were handed is wrong -- a non-`bool` `is_ground_plane`,
    an empty `confirmed_by`, or an attempt to confirm something that isn't a
    `PROPOSED` assertion. Named and raised the same way
    `InvalidRequirementTargetError` is for `target` -- a distinct exception
    class per validated field, so a caller can tell which sibling rejected
    its input without string-matching a shared message."""


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


def _require_nonempty_string(
    field_name: str,
    value: Any,
    error_cls: type[Exception] = InvalidRequirementTargetError,
) -> str:
    """Shared by every sibling in this module that validates a non-empty
    string field (`unit`, `reason`, `confirmed_by`, `effect`). Raises
    `error_cls` -- defaulting to `InvalidRequirementTargetError` for the
    `target`/`intended_effect` callers already relying on that default, and
    passed explicitly as `InvalidHostGroundPlaneAssertionError` by
    `confirm_host_ground_plane` -- so each sibling's caller still sees only
    its own named exception class, never a different sibling's."""
    if not isinstance(value, str) or not value.strip():
        raise error_cls(f"{field_name} must be a non-empty string, got {value!r}")
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


def propose_intended_effect(effect: str) -> dict[str, Any]:
    """Validate and tag one requirement's intended effect -- ADR-0030's
    "another key inside a requirement's own entry, beside `requirement` and
    `target`" (issue #323). Mirrors `propose_target`'s own validate-then-tag
    shape for the open-vocabulary effect prose ("behave as a magnetic
    mirror", "absorb the wave") rather than a numeric value: `effect` must
    be a non-empty string; `InvalidRequirementTargetError` names the field
    if it isn't.

    Always returns `provenance="ASSUMED"` -- per ADR-0030's own reasoning
    (restated in CONTEXT.md's Intended effect entry): a Requirements
    document (docs/adr/0034) reaching `CONFIRMED` is a trust signal about
    the reading, never a stronger kind of evidence, so there is no
    stronger provenance tier to promote to -- the identical "WHY
    PROVENANCE STAYS ASSUMED" reasoning this module's own docstring
    already gives for `propose_target`.

    A requirement that asks nothing of the wave (a bend radius, a mass
    budget, a cure ceiling) legitimately has no intended effect at all
    (ADR-0030's "having none is a legal answer") -- that case is simply
    never calling this function for that requirement, the same way a
    requirement entry with no `target` key yet is legal before
    `propose_target` is ever called for it.
    """
    resolved_effect = _require_nonempty_string("effect", effect)
    return {"effect": resolved_effect, "provenance": ASSUMED}


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


def attach_intent(
    requirements: dict[str, Any],
    requirement_id: str,
    intended_effect: dict[str, Any],
) -> dict[str, Any]:
    """Return a new `requirements` dict (never mutates its input) with
    `intended_effect` attached under
    `requirements[requirement_id]["intended_effect"]` -- `attach_target`'s
    direct sibling (ADR-0030, issue #323), leaving every other key on that
    requirement entry -- `requirement` and `target` included -- exactly as
    it was.

    Same shape/validation posture as `attach_target`: this function does
    not itself validate `intended_effect`'s shape (`propose_intended_effect`'s
    job, mirroring how `propose_target` -- not `attach_target` -- validates
    a target), and tolerates any extra keys already on the requirement
    entry.

    Raises `UnknownRequirementError` if `requirement_id` is not already a
    key in `requirements` -- the identical error class `attach_target`
    raises for the same reason, so a caller sees one consistent failure
    mode regardless of which of the two sibling `attach_*` functions it
    called.
    """
    if requirement_id not in requirements or not isinstance(requirements[requirement_id], dict):
        raise UnknownRequirementError(requirement_id)
    updated = copy.deepcopy(requirements)
    updated[requirement_id]["intended_effect"] = intended_effect
    return updated


def propose_host_ground_plane(is_ground_plane: bool) -> dict[str, Any]:
    """Validate and tag one proposed host ground-plane assertion (issue
    #484, ADR-0017) -- `attach_target`'s/`attach_intent`'s third sibling,
    living at `requirements[requirement_id]["host_ground_plane"]`. Mirrors
    `propose_target`'s validate-then-tag shape rather than
    `propose_intended_effect`'s one-shot shape, because ADR-0017's whole
    point is "asserted, never inferred": a bare unconfirmed reading is not
    enough to let a design skip its own printed reflector, so this field
    needs the same PROPOSED-then-CONFIRMED lifecycle `target` has.

    `is_ground_plane` must be an actual `bool` -- `True` if the requirement's
    prose asserts the host surface is a confirmed, reliable conductive
    backing (e.g. "the platform is a solid aluminum wing"), `False` if it
    explicitly asserts the opposite (a legitimate, distinct statement from
    silence, which already defaults to `False`'s behaviour per ADR-0017
    without anyone having to say so). Raises
    `InvalidHostGroundPlaneAssertionError` naming the field if it isn't a
    `bool` -- `None` and any other type are both rejected the same way, and
    `bool` is not silently coerced from a truthy/falsy value.

    Always returns `ground_plane_status="PROPOSED"`, `provenance="ASSUMED"`
    -- this function has no way to know whether the reading it was handed
    correctly reflects the customer's prose, only that it is *shaped* like a
    legitimate assertion; that is exactly why the result is unconfirmed,
    never something a caller can skip `confirm_host_ground_plane` for.

    Calling this again for the same requirement (via
    `propose_requirement_host_ground_plane`, its I/O-layer counterpart) is
    how a proposal gets corrected or replaced before confirmation, the same
    as `propose_target`.
    """
    if not isinstance(is_ground_plane, bool):
        raise InvalidHostGroundPlaneAssertionError(
            f"is_ground_plane must be a bool, got {is_ground_plane!r}"
        )
    return {
        "ground_plane_status": GroundPlaneStatus.PROPOSED.value,
        "provenance": ASSUMED,
        "is_ground_plane": is_ground_plane,
        "confirmed_by": None,
        "confirmed_at": None,
    }


def confirm_host_ground_plane(
    assertion: dict[str, Any],
    confirmed_by: str,
    confirmed_at: str | None = None,
) -> dict[str, Any]:
    """Confirm a proposed host ground-plane assertion, recording that it was
    confirmed and by whom -- `confirm_target`'s direct sibling (issue #484,
    ADR-0017). `assertion` must be a dict shaped like
    `propose_host_ground_plane`'s own return value with
    `ground_plane_status == "PROPOSED"` -- confirming something not shaped
    that way (nothing proposed yet) or an already-`CONFIRMED` assertion
    (re-propose it first if it needs correcting -- confirming a stale
    confirmation again would silently discard whoever confirmed it
    originally) both raise `InvalidHostGroundPlaneAssertionError`, naming
    what was found instead. `confirmed_by` must be a non-empty string
    identifying who confirmed it, the same trust boundary `confirm_target`
    already has.

    `confirmed_at` defaults to the real current UTC time (ISO-8601) and is
    only ever exposed as an explicit parameter for this function's own
    tests to get deterministic timestamps --
    `confirm_requirement_host_ground_plane` (the tool-facing I/O wrapper)
    never accepts it as an argument, so an agent can never fabricate a
    confirmation timestamp.

    Returns a new dict (the input `assertion` is not mutated) with
    `ground_plane_status="CONFIRMED"`; `is_ground_plane`/`provenance` are
    carried over unchanged -- see this module's docstring for why
    `provenance` deliberately stays `ASSUMED` even once confirmed. Per
    ADR-0017, only the `CONFIRMED` result of this function may ever let the
    design loop treat the host as its own reflector.
    """
    if (
        not isinstance(assertion, dict)
        or assertion.get("ground_plane_status") != GroundPlaneStatus.PROPOSED.value
    ):
        found = (
            assertion.get("ground_plane_status")
            if isinstance(assertion, dict)
            else type(assertion).__name__
        )
        raise InvalidHostGroundPlaneAssertionError(
            "confirm_host_ground_plane requires an assertion dict with "
            f"ground_plane_status {GroundPlaneStatus.PROPOSED.value!r} "
            f"(propose_host_ground_plane's own return shape) -- got "
            f"ground_plane_status={found!r}. Nothing proposed yet should be "
            "proposed first; an already-CONFIRMED assertion should be "
            "re-proposed (corrected), not re-confirmed."
        )
    resolved_confirmed_by = _require_nonempty_string(
        "confirmed_by", confirmed_by, error_cls=InvalidHostGroundPlaneAssertionError
    )
    resolved_confirmed_at = confirmed_at or datetime.datetime.now(datetime.UTC).isoformat()

    confirmed = dict(assertion)
    confirmed["ground_plane_status"] = GroundPlaneStatus.CONFIRMED.value
    confirmed["confirmed_by"] = resolved_confirmed_by
    confirmed["confirmed_at"] = resolved_confirmed_at
    return confirmed


def attach_host_ground_plane(
    requirements: dict[str, Any],
    requirement_id: str,
    host_ground_plane: dict[str, Any],
) -> dict[str, Any]:
    """Return a new `requirements` dict (never mutates its input) with
    `host_ground_plane` attached under
    `requirements[requirement_id]["host_ground_plane"]` --
    `attach_target`'s/`attach_intent`'s third sibling (issue #484,
    ADR-0017), leaving every other key on that requirement entry --
    `requirement`, `target`, and `intended_effect` included -- exactly as
    it was.

    Same shape/validation posture as `attach_target`/`attach_intent`: this
    function does not itself validate `host_ground_plane`'s shape
    (`propose_host_ground_plane`'s job), and tolerates any extra keys
    already on the requirement entry.

    Raises `UnknownRequirementError` if `requirement_id` is not already a
    key in `requirements` -- the identical error class `attach_target`/
    `attach_intent` raise for the same reason, so a caller sees one
    consistent failure mode regardless of which of the three sibling
    `attach_*` functions it called.
    """
    if requirement_id not in requirements or not isinstance(requirements[requirement_id], dict):
        raise UnknownRequirementError(requirement_id)
    updated = copy.deepcopy(requirements)
    updated[requirement_id]["host_ground_plane"] = host_ground_plane
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
    is a primary key.

    The row is read `FOR UPDATE` (issue #389), same as
    `designs.db.update_design_status`'s own status read -- every caller of
    this function fetches, merges a change in Python, and writes the whole
    `requirements` payload back (`_store_requirements`) on the same
    connection before committing, and without the lock two callers
    proposing targets on different `requirement_id`s of the same design at
    the same time can each read the payload before either writes, so the
    second write silently discards the first's change (a lost update, not a
    conflict either side is told about).
    """
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT requirements FROM designs WHERE id = %s FOR UPDATE", (design_id,))
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


def propose_requirement_host_ground_plane(
    design_id: int,
    requirement_id: str,
    is_ground_plane: bool,
) -> dict[str, Any]:
    """Propose (or correct/replace an existing proposal for) one
    requirement's host ground-plane assertion on a stored design (issue
    #484, ADR-0017) -- `propose_requirement_target`'s direct sibling, and
    the tool-facing entry point `agent/main.py`/`mcp_server/server.py` wire
    up for it. Validates the proposed shape via `propose_host_ground_plane`,
    then attaches it to the design's `requirements[requirement_id]` via
    `attach_host_ground_plane`, replacing whatever `host_ground_plane` (if
    any -- `PROPOSED` or `CONFIRMED`) was there before.

    Returns a structured `status`-tagged result rather than raising for
    every caller-facing failure mode: `"invalid_host_ground_plane"` (bad
    shape -- `propose_host_ground_plane`'s own error), `"not_found"` (no
    such `design_id`), or `"unknown_requirement"` (`requirement_id` isn't
    one of this design's own requirement keys). On success: `{"status":
    "proposed", "design_id": ..., "requirement_id": ..., "host_ground_plane":
    {...}}`. A write that fails for any other reason still raises -- matches
    every other function in this package.
    """
    try:
        assertion = propose_host_ground_plane(is_ground_plane)
    except InvalidHostGroundPlaneAssertionError as exc:
        return {"status": "invalid_host_ground_plane", "message": str(exc)}

    conn = db.get_connection()
    try:
        try:
            requirements = _fetch_requirements(conn, design_id)
            updated = attach_host_ground_plane(requirements, requirement_id, assertion)
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
        "host_ground_plane": assertion,
    }


def confirm_requirement_host_ground_plane(
    design_id: int,
    requirement_id: str,
    confirmed_by: str,
) -> dict[str, Any]:
    """Confirm the currently-proposed host ground-plane assertion on one of
    a design's requirements, recording that it was confirmed and by whom
    (issue #484, ADR-0017) -- `confirm_requirement_target`'s direct sibling.
    `confirmed_at` is always the real current time -- deliberately not a
    parameter here (see `confirm_host_ground_plane`'s docstring) so an agent
    can never supply a fabricated confirmation timestamp.

    Returns a structured `status`-tagged result: `"not_found"` (no such
    `design_id`), `"unknown_requirement"` (`requirement_id` isn't one of
    this design's requirement keys), `"no_proposal"` (this requirement has
    no `host_ground_plane` yet at all -- propose one first),
    `"invalid_host_ground_plane"` (the existing assertion is already
    `CONFIRMED` -- `confirm_host_ground_plane`'s own error, naming which),
    or on success `{"status": "confirmed", "design_id": ..., "requirement_id":
    ..., "host_ground_plane": {...}}` with `host_ground_plane["confirmed_by"]`/
    `host_ground_plane["confirmed_at"]` set.
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

        existing_assertion = requirement_entry.get("host_ground_plane")
        if existing_assertion is None:
            conn.rollback()
            return {
                "status": "no_proposal",
                "design_id": design_id,
                "requirement_id": requirement_id,
                "message": (
                    f"requirement_id {requirement_id!r} has no proposed host "
                    "ground-plane assertion yet -- call "
                    "propose_requirement_host_ground_plane before confirming one"
                ),
            }

        try:
            confirmed = confirm_host_ground_plane(existing_assertion, confirmed_by=confirmed_by)
        except InvalidHostGroundPlaneAssertionError as exc:
            conn.rollback()
            return {"status": "invalid_host_ground_plane", "message": str(exc)}

        updated = attach_host_ground_plane(requirements, requirement_id, confirmed)
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
        "host_ground_plane": confirmed,
    }
