"""Design-status transition rules (issue #145; docs/adr/0015).

ADR-0007 settled which nine values `designs.status` may hold, and said
outright that "how a design moves between them ... remains future work".
This module is that work: the legal ordering, and the one gate on it.

In plain terms: a design record has a field saying which stage of review it
has reached. Before this module, that field could be set to anything from
anything -- a brand-new draft could be marked RELEASED in a single write,
with no engineering in between. Now each stage names which stages may follow
it, and the one transition that matters most -- into RELEASED -- additionally
requires a signed human-approval receipt.

The lifecycle is `docs/OPERATIONS.md`'s, not a set invented here:

    DRAFT -> ANALYSIS -> SIMULATION -> OPTIMIZATION -> VERIFICATION ->
    CONDITIONAL-PASS/PASS/FAIL/BLOCKED -> RELEASED

with three additions that the linear reading leaves out but real work needs:

- **BLOCKED from anywhere in progress.** Work stalls for reasons outside the
  design -- a part goes end-of-life, a facility is unavailable. Any in-progress
  stage can go BLOCKED.
- **Rework returns to ANALYSIS.** A design that FAILed, got BLOCKED, or landed
  at CONDITIONAL-PASS re-enters at the front of the engineering cycle. It does
  not resume where it stopped: nothing records where that was, and guessing
  would be worse than restating it.
- **RELEASED is terminal.** A released design is not edited back into
  engineering; it gets a new `designs.revision` instead. So nothing leaves
  RELEASED, and only PASS or CONDITIONAL-PASS may enter it.

Pure functions over `DesignStatus` -- no database, no I/O. `designs.db.
update_design_status` is the enforcement point that calls into here.
"""

from __future__ import annotations

from designs.models import DesignStatus

__all__ = [
    "LEGAL_TRANSITIONS",
    "TERMINAL_STATUSES",
    "IllegalStatusTransitionError",
    "check_transition",
    "coerce_status",
    "legal_transitions_from",
    "transition_requires_release_approval",
]

_S = DesignStatus

#: Which statuses may directly follow each status. A status with an empty set
#: is terminal. Every `DesignStatus` is a key -- a missing one would raise
#: KeyError at write time instead of refusing the transition readably, so
#: `test_every_status_is_a_key_in_the_transition_map` guards that.
LEGAL_TRANSITIONS: dict[DesignStatus, frozenset[DesignStatus]] = {
    _S.DRAFT: frozenset({_S.ANALYSIS, _S.BLOCKED}),
    _S.ANALYSIS: frozenset({_S.SIMULATION, _S.FAIL, _S.BLOCKED}),
    _S.SIMULATION: frozenset({_S.OPTIMIZATION, _S.FAIL, _S.BLOCKED}),
    _S.OPTIMIZATION: frozenset({_S.VERIFICATION, _S.FAIL, _S.BLOCKED}),
    _S.VERIFICATION: frozenset(
        {_S.CONDITIONAL_PASS, _S.PASS, _S.FAIL, _S.BLOCKED}
    ),
    # Only these two may be released, and both may also be sent back for
    # rework -- a CONDITIONAL-PASS especially, since the condition is
    # usually "fix this one thing first".
    _S.PASS: frozenset({_S.RELEASED, _S.ANALYSIS}),
    _S.CONDITIONAL_PASS: frozenset({_S.RELEASED, _S.ANALYSIS, _S.FAIL, _S.BLOCKED}),
    _S.FAIL: frozenset({_S.ANALYSIS, _S.BLOCKED}),
    _S.BLOCKED: frozenset({_S.ANALYSIS, _S.FAIL}),
    _S.RELEASED: frozenset(),
}

#: Statuses nothing leaves. See the module docstring for why RELEASED is one.
TERMINAL_STATUSES: frozenset[DesignStatus] = frozenset(
    status for status, targets in LEGAL_TRANSITIONS.items() if not targets
)


class IllegalStatusTransitionError(ValueError):
    """Raised for a transition the lifecycle does not allow.

    A `ValueError` subclass so existing callers that already catch
    `ValueError` around `update_design_status` -- `orchestration/tooling.py`'s
    design-loop flush among them -- keep treating a refused write as a refusal
    rather than an unhandled crash.
    """

    def __init__(self, current: DesignStatus, target: DesignStatus) -> None:
        allowed = sorted(s.value for s in LEGAL_TRANSITIONS[current])
        allowed_text = ", ".join(allowed) if allowed else "(none -- terminal)"
        super().__init__(
            f"illegal design-status transition {current.value!r} -> "
            f"{target.value!r}; legal next statuses from {current.value!r} "
            f"are: {allowed_text}"
        )
        self.current = current
        self.target = target


def coerce_status(status: DesignStatus | str) -> DesignStatus:
    """Accept a `DesignStatus` or its string value, rejecting anything else.

    Callers reach this across an agent/MCP JSON tool boundary, where a status
    is a bare string. An unknown value names itself in the error rather than
    raising a bare enum `ValueError`.
    """
    if isinstance(status, DesignStatus):
        return status
    try:
        return DesignStatus(status)
    except ValueError:
        legal = ", ".join(sorted(s.value for s in DesignStatus))
        raise ValueError(
            f"unknown design status {status!r}; legal values are: {legal}"
        ) from None


def legal_transitions_from(status: DesignStatus | str) -> frozenset[DesignStatus]:
    """The statuses `status` may move to directly. Empty for a terminal one."""
    return LEGAL_TRANSITIONS[coerce_status(status)]


def transition_requires_release_approval(
    current: DesignStatus | str, target: DesignStatus | str
) -> bool:
    """Whether this transition needs a signed release-approval receipt.

    Only entering `RELEASED` does. That is the single transition ADR-0007
    calls out as requiring human approval, and `docs/OPERATIONS.md` states it
    outright.
    """
    del current  # only the destination decides; kept for a readable call site
    return coerce_status(target) is DesignStatus.RELEASED


def check_transition(
    current: DesignStatus | str, target: DesignStatus | str
) -> None:
    """Raise `IllegalStatusTransitionError` unless `current -> target` is legal.

    A status may not transition to itself: a no-op write is far more often a
    caller bug than an intent, and letting it through would make "the design
    advanced" indistinguishable from "nothing happened" in the audit trail.
    """
    current_status = coerce_status(current)
    target_status = coerce_status(target)
    if target_status not in LEGAL_TRANSITIONS[current_status]:
        raise IllegalStatusTransitionError(current_status, target_status)
