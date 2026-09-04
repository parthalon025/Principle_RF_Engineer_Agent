"""Design-status transition rules (issue #145).

These are pure functions over `DesignStatus`, so unlike the `designs.db`
write-path tests they need no Postgres and run everywhere.

ADR-0007 fixed the nine legal values and explicitly deferred "how a design
moves between them" to future work. This is that work: the ordering, and the
one gate on it.
"""

import pytest

from designs.lifecycle import (
    LEGAL_TRANSITIONS,
    TERMINAL_STATUSES,
    IllegalStatusTransitionError,
    check_transition,
    legal_transitions_from,
    transition_requires_release_approval,
)
from designs.models import DesignStatus

S = DesignStatus


def test_every_status_is_a_key_in_the_transition_map():
    """A status missing from the map would raise KeyError at write time
    rather than refusing the transition with a readable message."""
    assert set(LEGAL_TRANSITIONS) == set(DesignStatus)


def test_transition_targets_are_all_real_statuses():
    for source, targets in LEGAL_TRANSITIONS.items():
        for target in targets:
            assert isinstance(target, DesignStatus), (source, target)


def test_the_operations_happy_path_walks_end_to_end():
    """docs/OPERATIONS.md's stated order, one step at a time."""
    path = [
        S.DRAFT,
        S.ANALYSIS,
        S.SIMULATION,
        S.OPTIMIZATION,
        S.VERIFICATION,
        S.PASS,
        S.RELEASED,
    ]
    for current, target in zip(path[:-1], path[1:], strict=True):
        check_transition(current, target)


def test_a_design_cannot_skip_straight_from_draft_to_released():
    """The transition the whole ticket exists to prevent."""
    with pytest.raises(IllegalStatusTransitionError) as exc:
        check_transition(S.DRAFT, S.RELEASED)
    assert "DRAFT" in str(exc.value)
    assert "RELEASED" in str(exc.value)


@pytest.mark.parametrize(
    "skipped",
    [
        (S.DRAFT, S.SIMULATION),
        (S.ANALYSIS, S.VERIFICATION),
        (S.SIMULATION, S.PASS),
        (S.OPTIMIZATION, S.RELEASED),
    ],
)
def test_forward_jumps_that_skip_a_stage_are_refused(skipped):
    current, target = skipped
    with pytest.raises(IllegalStatusTransitionError):
        check_transition(current, target)


def test_verification_can_reach_all_four_outcome_states():
    for outcome in (S.CONDITIONAL_PASS, S.PASS, S.FAIL, S.BLOCKED):
        check_transition(S.VERIFICATION, outcome)


@pytest.mark.parametrize("outcome", [S.PASS, S.CONDITIONAL_PASS])
def test_only_pass_and_conditional_pass_can_be_released(outcome):
    check_transition(outcome, S.RELEASED)


@pytest.mark.parametrize("bad", [S.FAIL, S.BLOCKED, S.VERIFICATION, S.ANALYSIS])
def test_a_design_that_did_not_pass_cannot_be_released(bad):
    with pytest.raises(IllegalStatusTransitionError):
        check_transition(bad, S.RELEASED)


def test_released_is_terminal():
    """A released design is not edited back into engineering -- it gets a new
    revision instead (`designs.revision`), so nothing leaves RELEASED."""
    assert legal_transitions_from(S.RELEASED) == frozenset()
    assert S.RELEASED in TERMINAL_STATUSES
    for target in DesignStatus:
        with pytest.raises(IllegalStatusTransitionError):
            check_transition(S.RELEASED, target)


@pytest.mark.parametrize("failed", [S.FAIL, S.BLOCKED, S.CONDITIONAL_PASS])
def test_rework_returns_to_analysis(failed):
    """Rework re-enters at the front of the engineering cycle, not wherever it
    left off -- the system does not track where a design was before it
    stopped, and guessing would be worse than restating it."""
    check_transition(failed, S.ANALYSIS)


@pytest.mark.parametrize(
    "working", [S.DRAFT, S.ANALYSIS, S.SIMULATION, S.OPTIMIZATION, S.VERIFICATION]
)
def test_anything_in_progress_can_become_blocked(working):
    """Work can stall at any stage, for reasons outside the design."""
    check_transition(working, S.BLOCKED)


def test_a_status_cannot_transition_to_itself():
    """A no-op write is almost always a bug in the caller, not an intent."""
    for status in DesignStatus:
        with pytest.raises(IllegalStatusTransitionError):
            check_transition(status, status)


def test_only_the_released_transition_is_approval_gated():
    assert transition_requires_release_approval(S.PASS, S.RELEASED)
    assert transition_requires_release_approval(S.CONDITIONAL_PASS, S.RELEASED)
    assert not transition_requires_release_approval(S.DRAFT, S.ANALYSIS)
    assert not transition_requires_release_approval(S.VERIFICATION, S.PASS)


def test_check_transition_accepts_plain_strings():
    """Callers cross a JSON tool boundary, where a status is a bare string."""
    check_transition("DRAFT", "ANALYSIS")
    with pytest.raises(IllegalStatusTransitionError):
        check_transition("DRAFT", "RELEASED")


def test_an_unknown_status_is_rejected_by_name():
    with pytest.raises(ValueError, match="ACTIVE"):
        check_transition("DRAFT", "ACTIVE")
    with pytest.raises(ValueError, match="ACTIVE"):
        check_transition("ACTIVE", "DRAFT")


def test_the_error_names_what_was_legal_instead():
    """A refusal a caller can act on without reading the source."""
    with pytest.raises(IllegalStatusTransitionError) as exc:
        check_transition(S.DRAFT, S.PASS)
    assert "ANALYSIS" in str(exc.value)
