"""Tests for rf_tools/success_score.py (issue #93).

Pure-function tests only, following tests/test_calculations.py's
deterministic in/out style -- no database needed. `score_point_target`/
`score_threshold` (the two formula halves) and `success_score` (the
dispatching, validating entry point) are all exercised directly.

Real `designs.requirement_targets.propose_target`/`confirm_target` output is
used to build test targets wherever possible (rather than hand-typed dicts)
so these tests double as an integration check that #93 actually consumes
#92's real return shape, not an assumption about it.
"""

from __future__ import annotations

import pytest

from designs.requirement_targets import confirm_target, mark_unscoreable, propose_target
from rf_tools.success_score import (
    JUDGMENT_STEPS,
    SCOREABLE_STEPS,
    SuccessScoreError,
    score_point_target,
    score_threshold,
    success_score,
)

# ---------------------------------------------------------------------------
# score_point_target -- EQUALS / point-target formula
# ---------------------------------------------------------------------------


def test_point_target_exact_match_scores_100_with_tolerance():
    result = score_point_target(target_value=2.45e9, actual_value=2.45e9, tolerance=5e7)
    assert result["score_percent"] == pytest.approx(100.0)
    assert result["target_met"] is True
    assert result["deviation"] == pytest.approx(0.0)


def test_point_target_halfway_to_tolerance_scores_50():
    result = score_point_target(target_value=2.45e9, actual_value=2.45e9 + 2.5e7, tolerance=5e7)
    assert result["score_percent"] == pytest.approx(50.0)
    assert result["target_met"] is True  # exactly at the tolerance boundary's half, still inside
    assert result["deviation"] == pytest.approx(2.5e7)


def test_point_target_at_tolerance_edge_scores_0_but_is_still_met():
    result = score_point_target(target_value=2.45e9, actual_value=2.45e9 + 5e7, tolerance=5e7)
    assert result["score_percent"] == pytest.approx(0.0)
    assert result["target_met"] is True  # distance <= tolerance, inclusive


def test_point_target_beyond_tolerance_clamps_to_0_not_negative():
    result = score_point_target(target_value=2.45e9, actual_value=2.45e9 + 5e8, tolerance=5e7)
    assert result["score_percent"] == pytest.approx(0.0)
    assert result["target_met"] is False


def test_point_target_undershoot_and_overshoot_are_symmetric():
    over = score_point_target(target_value=100.0, actual_value=110.0, tolerance=20.0)
    under = score_point_target(target_value=100.0, actual_value=90.0, tolerance=20.0)
    assert over["score_percent"] == pytest.approx(under["score_percent"])
    assert over["deviation"] == pytest.approx(10.0)
    assert under["deviation"] == pytest.approx(-10.0)


def test_point_target_zero_tolerance_is_binary_exact_match():
    exact = score_point_target(target_value=5.0, actual_value=5.0, tolerance=0.0)
    off = score_point_target(target_value=5.0, actual_value=5.0001, tolerance=0.0)
    assert exact["score_percent"] == pytest.approx(100.0)
    assert exact["target_met"] is True
    assert off["score_percent"] == pytest.approx(0.0)
    assert off["target_met"] is False


def test_point_target_no_tolerance_uses_relative_proximity_to_target_magnitude():
    # 10% off a nonzero target, no tolerance supplied -> 90% score.
    result = score_point_target(target_value=200.0, actual_value=220.0, tolerance=None)
    assert result["score_percent"] == pytest.approx(90.0)
    assert result["target_met"] is None  # no tolerance -> no defined pass/fail line


def test_point_target_no_tolerance_zero_target_value_raises():
    with pytest.raises(SuccessScoreError, match="zero-valued target"):
        score_point_target(target_value=0.0, actual_value=1.0, tolerance=None)


def test_point_target_zero_target_value_with_tolerance_does_not_raise():
    # tolerance supplied -> never divides by target_value, so 0 is fine.
    result = score_point_target(target_value=0.0, actual_value=0.5, tolerance=1.0)
    assert result["score_percent"] == pytest.approx(50.0)
    assert result["target_met"] is True


# ---------------------------------------------------------------------------
# score_threshold -- AT_LEAST / AT_MOST formula
# ---------------------------------------------------------------------------


def test_at_least_met_exactly_at_bound_scores_100():
    result = score_threshold(
        comparator="AT_LEAST", target_value=5.0, actual_value=5.0, tolerance=None
    )
    assert result["score_percent"] == pytest.approx(100.0)
    assert result["target_met"] is True
    assert result["margin"] == pytest.approx(0.0)


def test_at_least_met_by_a_mile_still_scores_exactly_100_no_bonus():
    barely = score_threshold(
        comparator="AT_LEAST", target_value=5.0, actual_value=5.01, tolerance=None
    )
    by_a_mile = score_threshold(
        comparator="AT_LEAST", target_value=5.0, actual_value=50.0, tolerance=None
    )
    assert barely["score_percent"] == pytest.approx(100.0)
    assert by_a_mile["score_percent"] == pytest.approx(100.0)
    assert barely["target_met"] is True
    assert by_a_mile["target_met"] is True
    # margin is still reported for a wide-margin pass, just never rewarded
    assert by_a_mile["margin"] == pytest.approx(45.0)


def test_at_least_not_met_scores_partial_credit_by_shortfall_with_tolerance():
    # target 5, tolerance 1: missing by 0.5 (half the tolerance) -> 50%.
    result = score_threshold(
        comparator="AT_LEAST", target_value=5.0, actual_value=4.5, tolerance=1.0
    )
    assert result["target_met"] is False
    assert result["margin"] == pytest.approx(-0.5)
    assert result["score_percent"] == pytest.approx(50.0)


def test_at_least_not_met_far_below_scores_0_not_negative():
    result = score_threshold(
        comparator="AT_LEAST", target_value=5.0, actual_value=-100.0, tolerance=1.0
    )
    assert result["target_met"] is False
    assert result["score_percent"] == pytest.approx(0.0)


def test_at_most_met_exactly_at_bound_scores_100():
    result = score_threshold(
        comparator="AT_MOST", target_value=2.0, actual_value=2.0, tolerance=None
    )
    assert result["score_percent"] == pytest.approx(100.0)
    assert result["target_met"] is True


def test_at_most_met_with_wide_margin_scores_100_no_penalty():
    result = score_threshold(
        comparator="AT_MOST", target_value=2.0, actual_value=1.0, tolerance=None
    )
    assert result["score_percent"] == pytest.approx(100.0)
    assert result["target_met"] is True
    assert result["margin"] == pytest.approx(1.0)


def test_at_most_not_met_scores_partial_credit_by_shortfall():
    # target VSWR <= 2.0, tolerance 0.5, actual 2.25 (0.25 over -> half the tolerance).
    result = score_threshold(
        comparator="AT_MOST", target_value=2.0, actual_value=2.25, tolerance=0.5
    )
    assert result["target_met"] is False
    assert result["margin"] == pytest.approx(-0.25)
    assert result["score_percent"] == pytest.approx(50.0)


def test_threshold_no_tolerance_zero_target_value_raises_only_when_not_met():
    # Met -> saturates at 100 without ever needing a scale, so no raise.
    met = score_threshold(comparator="AT_LEAST", target_value=0.0, actual_value=1.0, tolerance=None)
    assert met["score_percent"] == pytest.approx(100.0)
    with pytest.raises(SuccessScoreError, match="zero-valued target"):
        score_threshold(comparator="AT_LEAST", target_value=0.0, actual_value=-1.0, tolerance=None)


def test_threshold_rejects_equals_comparator():
    with pytest.raises(SuccessScoreError, match="EQUALS"):
        score_threshold(comparator="EQUALS", target_value=5.0, actual_value=5.0, tolerance=None)


def test_threshold_rejects_unknown_comparator():
    with pytest.raises(SuccessScoreError):
        score_threshold(comparator="BETWEEN", target_value=5.0, actual_value=5.0, tolerance=None)


# ---------------------------------------------------------------------------
# success_score -- the full dispatching, validating entry point
# ---------------------------------------------------------------------------


def _confirmed_point_target(**overrides):
    proposed = propose_target(value=2.45e9, comparator="EQUALS", unit="Hz", tolerance=5e7)
    return confirm_target(
        proposed, confirmed_by="engineer_jane", confirmed_at="2026-01-01T00:00:00+00:00"
    )


def test_success_score_point_target_end_to_end_against_confirmed_92_target():
    target = _confirmed_point_target()
    result = success_score(step="analysis", target=target, actual_value=2.46e9, actual_unit="Hz")
    assert result["provenance"] == "CALCULATED"
    assert result["target_provenance"] == "ASSUMED"
    assert result["target_status"] == "CONFIRMED"
    assert result["step"] == "analysis"
    assert result["comparator"] == "EQUALS"
    assert result["target_met"] is True
    assert result["deviation"] == pytest.approx(1e7)
    assert result["margin"] is None
    assert result["score_percent"] == pytest.approx(80.0)  # 1e7/5e7 = 0.2 -> 80%


def test_success_score_threshold_end_to_end_against_proposed_92_target():
    target = propose_target(value=5.0, comparator="AT_LEAST", unit="dBi")
    result = success_score(step="simulation", target=target, actual_value=7.5, actual_unit="dBi")
    assert result["target_status"] == "PROPOSED"
    assert result["target_provenance"] == "ASSUMED"
    assert result["comparator"] == "AT_LEAST"
    assert result["deviation"] is None
    assert result["margin"] == pytest.approx(2.5)
    assert result["score_percent"] == pytest.approx(100.0)
    assert result["target_met"] is True


@pytest.mark.parametrize("step", sorted(SCOREABLE_STEPS))
def test_success_score_accepts_every_scoreable_step(step):
    target = propose_target(value=1.0, comparator="AT_LEAST", unit="V")
    result = success_score(step=step, target=target, actual_value=1.0, actual_unit="V")
    assert result["step"] == step


@pytest.mark.parametrize("step", sorted(JUDGMENT_STEPS))
def test_success_score_refuses_judgment_steps(step):
    target = propose_target(value=1.0, comparator="AT_LEAST", unit="V")
    with pytest.raises(SuccessScoreError, match="human-judgment step"):
        success_score(step=step, target=target, actual_value=1.0, actual_unit="V")


@pytest.mark.parametrize("step", ["measurement", "requirements", "bogus_step"])
def test_success_score_refuses_steps_outside_the_closed_scoreable_vocabulary(step):
    target = propose_target(value=1.0, comparator="AT_LEAST", unit="V")
    with pytest.raises(SuccessScoreError, match="scoreable design-loop"):
        success_score(step=step, target=target, actual_value=1.0, actual_unit="V")


def test_success_score_refuses_unscoreable_target_with_reason_in_message():
    target = mark_unscoreable(reason="prose states a qualitative goal with no numeric bound")
    with pytest.raises(SuccessScoreError, match="qualitative goal"):
        success_score(step="analysis", target=target, actual_value=1.0, actual_unit="V")


def test_success_score_refuses_unit_mismatch_without_guessing_a_conversion():
    target = propose_target(value=2.45, comparator="EQUALS", unit="GHz", tolerance=0.05)
    with pytest.raises(SuccessScoreError, match="does not match target unit"):
        success_score(step="analysis", target=target, actual_value=2.45e9, actual_unit="Hz")


def test_success_score_rejects_non_numeric_actual_value():
    target = propose_target(value=1.0, comparator="AT_LEAST", unit="V")
    with pytest.raises(SuccessScoreError):
        success_score(step="analysis", target=target, actual_value="not a number", actual_unit="V")


def test_success_score_rejects_bool_actual_value():
    # bool is an int subclass in Python -- explicitly excluded, matching
    # designs.requirement_targets's own _require_finite_number convention.
    target = propose_target(value=1.0, comparator="AT_LEAST", unit="V")
    with pytest.raises(SuccessScoreError):
        success_score(step="analysis", target=target, actual_value=True, actual_unit="V")


def test_success_score_with_note_tags_it_inferred_and_keeps_score_authoritative():
    target = propose_target(value=1.0, comparator="AT_LEAST", unit="V")
    result = success_score(
        step="analysis",
        target=target,
        actual_value=1.5,
        actual_unit="V",
        note="Manufacturing tolerance on this component may erode this margin.",
    )
    assert result["note"] == "Manufacturing tolerance on this component may erode this margin."
    assert result["note_provenance"] == "INFERRED"
    # the note never substitutes for the number
    assert result["score_percent"] == pytest.approx(100.0)


def test_success_score_without_note_carries_no_fabricated_note_or_tag():
    target = propose_target(value=1.0, comparator="AT_LEAST", unit="V")
    result = success_score(step="analysis", target=target, actual_value=1.0, actual_unit="V")
    assert result["note"] is None
    assert result["note_provenance"] is None


def test_success_score_rejects_blank_note():
    target = propose_target(value=1.0, comparator="AT_LEAST", unit="V")
    with pytest.raises(SuccessScoreError):
        success_score(step="analysis", target=target, actual_value=1.0, actual_unit="V", note="   ")


def test_success_score_is_deterministic_pure_function():
    target = _confirmed_point_target()
    first = success_score(step="verification", target=target, actual_value=2.42e9, actual_unit="Hz")
    second = success_score(
        step="verification", target=target, actual_value=2.42e9, actual_unit="Hz"
    )
    assert first == second


# ---------------------------------------------------------------------------
# Both target_provenance and target_status travel with every score, and can
# genuinely disagree in the sense that matters: PROPOSED vs CONFIRMED, while
# provenance stays identically "ASSUMED" either way (see #92's own docstring
# and this module's "CRITICAL CORRECTION" section for why provenance alone
# cannot carry the trust signal the acceptance criterion is protecting).
# ---------------------------------------------------------------------------


def test_score_carries_both_target_provenance_and_target_status_and_they_can_disagree_in_practice():
    proposed = propose_target(value=2.45e9, comparator="EQUALS", unit="Hz", tolerance=5e7)
    confirmed = confirm_target(
        proposed, confirmed_by="engineer_jane", confirmed_at="2026-01-01T00:00:00+00:00"
    )

    score_against_proposed = success_score(
        step="analysis", target=proposed, actual_value=2.45e9, actual_unit="Hz"
    )
    score_against_confirmed = success_score(
        step="analysis", target=confirmed, actual_value=2.45e9, actual_unit="Hz"
    )

    # provenance is identical -- #92's own point: it is ALWAYS "ASSUMED",
    # proposed or confirmed makes no difference to it.
    assert score_against_proposed["target_provenance"] == "ASSUMED"
    assert score_against_confirmed["target_provenance"] == "ASSUMED"
    assert (
        score_against_proposed["target_provenance"] == score_against_confirmed["target_provenance"]
    )

    # target_status is what actually distinguishes an unconfirmed guess from
    # a human-vouched-for target -- this is the field a reader must check.
    assert score_against_proposed["target_status"] == "PROPOSED"
    assert score_against_confirmed["target_status"] == "CONFIRMED"
    assert score_against_proposed["target_status"] != score_against_confirmed["target_status"]

    # the underlying arithmetic itself is unaffected by target_status -- a
    # score is a score; only the trust label riding alongside it changes.
    assert score_against_proposed["score_percent"] == pytest.approx(
        score_against_confirmed["score_percent"]
    )
