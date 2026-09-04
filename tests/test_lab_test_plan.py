"""Tests for orchestration/lab_test_plan.py (issue #94).

Pure-function tests only, following tests/test_requirement_targets.py's/
tests/test_success_score.py's own precedent -- no database needed.
`compile_lab_test_plan` is exercised directly against hand-built
`DesignLoopState`/`LoopDecision` fixtures (built directly via their own
dataclass constructors for full control over `iteration`/`provenance`
tagging, and via a real `orchestration.design_loop.start_design_loop` call
for the one end-to-end test that wants a genuine loop state). Real
`designs.requirement_targets.propose_target`/`mark_unscoreable`/
`confirm_target` output is used to build test targets wherever possible,
matching tests/test_success_score.py's own "double as an integration
check" rationale.

`compile_lab_test_plan_for_loop` (the I/O wrapper that re-reads
`designs.requirements` fresh via `designs.db.read_design` when a
`design_id` is present) is NOT tested here: it needs a live Postgres via
DATABASE_URL, and there is no database in this sandbox (same constraint
tests/test_requirement_targets.py/tests/test_designs_service.py/tests/
test_tooling.py already document for themselves). Its fallback path (no
`design_id` at all) is pure and IS covered here, directly.
"""

from __future__ import annotations

import time

import pytest

from designs.requirement_targets import confirm_target, mark_unscoreable, propose_target
from orchestration.design_loop import DesignLoopState, LoopDecision
from orchestration.lab_test_plan import (
    LabTestPlanError,
    UnverifiableReason,
    compile_lab_test_plan,
)

# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


def _decision(
    step: str,
    result: dict,
    provenance: str | None,
    iteration: int | None = 1,
    kind: str = "calculation",
) -> LoopDecision:
    return LoopDecision(
        step=step,
        kind=kind,
        input={},
        result=result,
        provenance=provenance,
        approved_by=None,
        recorded_at=time.time(),
        iteration=iteration,
    )


def _state(
    requirements: dict, decisions: list[LoopDecision], iteration: int = 1
) -> DesignLoopState:
    now = time.time()
    return DesignLoopState(
        loop_id="loop-test",
        iteration=iteration,
        current_step="architecture",
        completed=False,
        requirements=requirements,
        decisions=decisions,
        created_at=now,
        updated_at=now,
    )


_ANALYSIS_DECISION = _decision(
    "analysis",
    {
        "function": "patch_resonant_frequency_hz",
        "resonant_frequency_hz": 2.45e9,
        "provenance": "CALCULATED",
    },
    "CALCULATED",
    kind="calculation",
)

_OPTIMIZATION_DECISION = _decision(
    "optimization",
    {
        "method": "bayesian",
        "best_length_m": 0.028,
        "achieved_frequency_hz": 2.451e9,
        "target_frequency_hz": 2.45e9,
        "provenance": "CALCULATED",
    },
    "CALCULATED",
    kind="optimization",
)

_SIMULATION_DECISION = _decision(
    "simulation",
    {
        "provenance": "SIMULATED",
        "impedance": [50.0, 0.0],
        "pattern": [],
        "gain_dbi": 6.2,
        "average_power_gain_linear": 0.9,
        "simulator": "nec2pp",
    },
    "SIMULATED",
    kind="simulation",
)

# A SIMULATION decision carrying the VSWR/return-loss fields
# orchestration/design_loop.py's _handle_simulation records since issue
# #101 -- _SIMULATION_DECISION above predates that and deliberately still
# lacks them (see test_vswr_requirement_with_no_traced_value_is_flagged_
# no_result below, which still needs a decision that legitimately carries
# no vswr value).
_SIMULATION_DECISION_WITH_VSWR = _decision(
    "simulation",
    {
        "provenance": "SIMULATED",
        "impedance": {"resistance_ohms": 82.6979, "reactance_ohms": 46.3060},
        "pattern": [],
        "gain_dbi": 6.2,
        "average_power_gain_linear": 0.9,
        "simulator": "nec2pp",
        "reference_impedance_ohms": 50.0,
        "reflection_coefficient_magnitude": 0.40333507086482756,
        "vswr": 2.35196506839923,
        "return_loss_db": 7.8866802699461624,
        "frequency_hz": 2.45e9,
        "single_frequency_prediction": True,
    },
    "SIMULATED",
    kind="simulation",
)


def _vswr_target(**overrides):
    kwargs = {"value": 2.0, "comparator": "AT_MOST", "unit": "VSWR"}
    kwargs.update(overrides)
    return propose_target(**kwargs)


def _return_loss_target(**overrides):
    kwargs = {"value": 10.0, "comparator": "AT_LEAST", "unit": "dB"}
    kwargs.update(overrides)
    return propose_target(**kwargs)


def _freq_target(**overrides):
    kwargs = {"value": 2.45e9, "comparator": "EQUALS", "unit": "Hz", "tolerance": 5e7}
    kwargs.update(overrides)
    return propose_target(**kwargs)


def _gain_target(**overrides):
    kwargs = {"value": 5.0, "comparator": "AT_LEAST", "unit": "dBi"}
    kwargs.update(overrides)
    return propose_target(**kwargs)


# ---------------------------------------------------------------------------
# Malformed-input refusals
# ---------------------------------------------------------------------------


def test_rejects_empty_requirements():
    state = _state({}, [])
    with pytest.raises(LabTestPlanError):
        compile_lab_test_plan(state)


def test_rejects_non_dict_requirements():
    state = _state({"r1": "not a dict"}, [])
    with pytest.raises(LabTestPlanError):
        compile_lab_test_plan(state)


def test_rejects_requirement_missing_requirement_text():
    state = _state({"r1": {"target": None}}, [])
    with pytest.raises(LabTestPlanError):
        compile_lab_test_plan(state)


def test_rejects_non_dict_target():
    state = _state({"r1": {"requirement": "Gain >= 5 dBi", "target": "not a dict"}}, [])
    with pytest.raises(LabTestPlanError):
        compile_lab_test_plan(state)


def test_rejects_target_with_unknown_target_status():
    bad_target = dict(_gain_target())
    bad_target["target_status"] = "SOMETHING_ELSE"
    state = _state({"r1": {"requirement": "Gain >= 5 dBi", "target": bad_target}}, [])
    with pytest.raises(LabTestPlanError):
        compile_lab_test_plan(state)


# ---------------------------------------------------------------------------
# DESIGN QUESTION 1, reason 1: NO_TARGET_RECORDED
# ---------------------------------------------------------------------------


def test_requirement_with_no_target_is_flagged_no_target_recorded():
    state = _state({"r1": {"requirement": "Operates at 2.45 GHz"}}, [_ANALYSIS_DECISION])
    plan = compile_lab_test_plan(state)
    item = plan["items"][0]
    assert item["flag"]["reason"] == UnverifiableReason.NO_TARGET_RECORDED.value
    assert item["status"] == "BLOCKED"
    assert item["method"] is None
    assert item["expected"] is None
    assert item["requirement_id"] in plan["flagged_requirement_ids"]


def test_requirement_with_explicit_none_target_key_is_also_flagged():
    state = _state(
        {"r1": {"requirement": "Operates at 2.45 GHz", "target": None}}, [_ANALYSIS_DECISION]
    )
    plan = compile_lab_test_plan(state)
    assert plan["items"][0]["flag"]["reason"] == UnverifiableReason.NO_TARGET_RECORDED.value


# ---------------------------------------------------------------------------
# DESIGN QUESTION 1, reason 2: UNSCOREABLE_TARGET
# ---------------------------------------------------------------------------


def test_unscoreable_target_is_flagged_with_its_own_reason_carried_through():
    unscoreable = mark_unscoreable("prose states a qualitative goal with no numeric bound")
    state = _state(
        {"r1": {"requirement": "Should feel robust when flexed", "target": unscoreable}},
        [_ANALYSIS_DECISION],
    )
    plan = compile_lab_test_plan(state)
    item = plan["items"][0]
    assert item["flag"]["reason"] == UnverifiableReason.UNSCOREABLE_TARGET.value
    assert "qualitative goal" in item["flag"]["detail"]
    assert item["status"] == "BLOCKED"


# ---------------------------------------------------------------------------
# DESIGN QUESTION 1, reason 3: QUANTITY_NOT_TOUCHSTONE_MEASURABLE
# ---------------------------------------------------------------------------


def test_gain_requirement_is_flagged_not_touchstone_measurable():
    state = _state(
        {"r1": {"requirement": "Gain >= 5 dBi over band", "target": _gain_target()}},
        [_ANALYSIS_DECISION],
    )
    plan = compile_lab_test_plan(state)
    item = plan["items"][0]
    assert item["flag"]["reason"] == UnverifiableReason.QUANTITY_NOT_TOUCHSTONE_MEASURABLE.value
    assert item["status"] == "BLOCKED"


def test_gain_requirement_still_carries_expected_and_method_from_simulation():
    # A gain target CAN still trace an expected value (SIMULATION recorded
    # gain_dbi this iteration) even though it is flagged -- see this
    # module's docstring, "DESIGN QUESTION 1", reason 3.
    state = _state(
        {"r1": {"requirement": "Gain >= 5 dBi over band", "target": _gain_target()}},
        [_SIMULATION_DECISION],
    )
    plan = compile_lab_test_plan(state)
    item = plan["items"][0]
    assert item["flag"]["reason"] == UnverifiableReason.QUANTITY_NOT_TOUCHSTONE_MEASURABLE.value
    assert item["expected"]["value"] == pytest.approx(6.2)
    assert item["expected"]["unit"] == "dBi"
    assert item["expected"]["provenance"] == "SIMULATED"
    assert item["method"] == "simulation"


def test_pattern_and_efficiency_units_are_also_flagged_not_touchstone_measurable():
    for unit in ("deg", "degrees", "%", "percent", "dBd"):
        target = propose_target(value=1.0, comparator="AT_MOST", unit=unit)
        state = _state({"r1": {"requirement": "some requirement", "target": target}}, [])
        item = compile_lab_test_plan(state)["items"][0]
        assert (
            item["flag"]["reason"] == UnverifiableReason.QUANTITY_NOT_TOUCHSTONE_MEASURABLE.value
        ), f"unit {unit!r} should be flagged unmeasurable"


def test_unrecognized_unit_is_flagged_not_touchstone_measurable_not_raised():
    target = propose_target(value=1.0, comparator="AT_MOST", unit="furlongs_per_fortnight")
    state = _state({"r1": {"requirement": "some requirement", "target": target}}, [])
    item = compile_lab_test_plan(state)["items"][0]
    assert item["flag"]["reason"] == UnverifiableReason.QUANTITY_NOT_TOUCHSTONE_MEASURABLE.value
    assert "not one of this module's recognized" in item["flag"]["detail"]


# ---------------------------------------------------------------------------
# DESIGN QUESTION 1, reason 4: NO_ENGINEERING_RESULT_THIS_ITERATION
# ---------------------------------------------------------------------------


def test_frequency_requirement_with_no_analysis_decision_is_flagged_no_result():
    state = _state({"r1": {"requirement": "Resonates at 2.45 GHz", "target": _freq_target()}}, [])
    plan = compile_lab_test_plan(state)
    item = plan["items"][0]
    assert item["method"] == "measurement"  # still touchstone-measurable
    assert item["flag"]["reason"] == (UnverifiableReason.NO_ENGINEERING_RESULT_THIS_ITERATION.value)
    assert item["expected"] is None


def test_vswr_requirement_with_no_traced_value_is_flagged_no_result():
    # _SIMULATION_DECISION predates issue #101 and carries no vswr field at
    # all (e.g. as if NEC2's impedance parse had failed) -- still correctly
    # flagged, since nothing this iteration recorded a matching value.
    target = propose_target(value=2.0, comparator="AT_MOST", unit="VSWR")
    state = _state(
        {"r1": {"requirement": "VSWR <= 2.0", "target": target}},
        [_ANALYSIS_DECISION, _SIMULATION_DECISION, _OPTIMIZATION_DECISION],
    )
    item = compile_lab_test_plan(state)["items"][0]
    assert item["method"] == "measurement"
    assert item["flag"]["reason"] == (UnverifiableReason.NO_ENGINEERING_RESULT_THIS_ITERATION.value)


# ---------------------------------------------------------------------------
# DESIGN QUESTION 2, VSWR/return-loss closure (issue #101): SIMULATION's own
# derived vswr/return_loss_db fields ARE traceable expected values now, with
# their reference impedance and single-frequency status carried through.
# ---------------------------------------------------------------------------


def test_vswr_requirement_traces_expected_to_simulation_decision():
    state = _state(
        {"r1": {"requirement": "VSWR <= 2.0 across the band", "target": _vswr_target()}},
        [_SIMULATION_DECISION_WITH_VSWR],
    )
    item = compile_lab_test_plan(state)["items"][0]
    assert item["flag"] is None
    assert item["method"] == "measurement"
    assert item["expected"]["value"] == pytest.approx(2.35196506839923)
    assert item["expected"]["unit"] == "VSWR"
    assert item["expected"]["provenance"] == "SIMULATED"
    assert item["expected"]["source_step"] == "simulation"
    # The reference impedance is recorded alongside the value, never
    # assumed -- issue #101's own acceptance criterion.
    assert item["expected"]["reference_impedance_ohms"] == 50.0
    # A single-point NEC2 solve against what is usually a band requirement
    # ("across the band") -- explicitly marked as such, not silently
    # presented as if it covered the whole band.
    assert item["expected"]["single_frequency_prediction"] is True
    assert "Single-frequency" in item["notes"]


def test_return_loss_requirement_traces_expected_to_simulation_decision():
    state = _state(
        {"r1": {"requirement": "Return loss >= 10 dB", "target": _return_loss_target()}},
        [_SIMULATION_DECISION_WITH_VSWR],
    )
    item = compile_lab_test_plan(state)["items"][0]
    assert item["flag"] is None
    assert item["expected"]["value"] == pytest.approx(7.8866802699461624)
    assert item["expected"]["unit"] == "dB"
    assert item["expected"]["provenance"] == "SIMULATED"
    assert item["expected"]["source_step"] == "simulation"
    assert item["expected"]["reference_impedance_ohms"] == 50.0
    assert item["expected"]["single_frequency_prediction"] is True


def test_vswr_and_return_loss_targets_each_trace_their_own_field_not_each_others():
    # A "VSWR" target must not accidentally pick up the return_loss_db
    # value (or vice versa) -- exact-unit-string matching keeps the two
    # S-parameter quantities distinct even though both are touchstone-
    # measurable "S_PARAMETER"-kind units.
    state = _state(
        {
            "vswr_req": {"requirement": "VSWR <= 2.0", "target": _vswr_target()},
            "rl_req": {"requirement": "Return loss >= 10 dB", "target": _return_loss_target()},
        },
        [_SIMULATION_DECISION_WITH_VSWR],
    )
    plan = compile_lab_test_plan(state)
    by_id = {item["requirement_id"]: item for item in plan["items"]}
    assert by_id["vswr_req"]["expected"]["value"] == pytest.approx(2.35196506839923)
    assert by_id["rl_req"]["expected"]["value"] == pytest.approx(7.8866802699461624)


def test_frequency_expected_value_carries_no_single_frequency_prediction_flag():
    # single_frequency_prediction is read straight off the recorded
    # decision's own result -- ANALYSIS/OPTIMIZATION never set it, so it is
    # honestly absent (None), not defaulted to True/False by this module.
    state = _state(
        {"r1": {"requirement": "Resonates at 2.45 GHz", "target": _freq_target()}},
        [_ANALYSIS_DECISION],
    )
    item = compile_lab_test_plan(state)["items"][0]
    assert item["expected"]["single_frequency_prediction"] is None
    assert item["expected"]["reference_impedance_ohms"] is None


def test_frequency_requirement_stated_in_ghz_does_not_match_hz_field_by_unit_string():
    # No silent conversion -- resonant_frequency_hz's canonical unit is
    # "Hz"; a target proposed in "GHz" does not match by exact string.
    target = propose_target(value=2.45, comparator="EQUALS", unit="GHz", tolerance=0.05)
    state = _state(
        {"r1": {"requirement": "Resonates at 2.45 GHz", "target": target}}, [_ANALYSIS_DECISION]
    )
    item = compile_lab_test_plan(state)["items"][0]
    assert item["flag"]["reason"] == (UnverifiableReason.NO_ENGINEERING_RESULT_THIS_ITERATION.value)
    assert "different unit string" in item["flag"]["detail"]


# ---------------------------------------------------------------------------
# The happy path: a real, traceable expected value
# ---------------------------------------------------------------------------


def test_frequency_requirement_traces_expected_to_analysis_decision():
    state = _state(
        {"r1": {"requirement": "Resonates at 2.45 GHz", "target": _freq_target()}},
        [_ANALYSIS_DECISION],
    )
    item = compile_lab_test_plan(state)["items"][0]
    assert item["flag"] is None
    assert item["status"] == "NOT VERIFIED"
    assert item["method"] == "measurement"
    assert item["actual"] is None
    assert item["evidence"] is None
    assert item["expected"]["value"] == pytest.approx(2.45e9)
    assert item["expected"]["unit"] == "Hz"
    assert item["expected"]["provenance"] == "CALCULATED"
    assert item["expected"]["source_step"] == "analysis"
    assert item["expected"]["target_value"] == pytest.approx(2.45e9)
    assert item["expected"]["comparator"] == "EQUALS"


def test_a_confirmed_target_traces_the_same_way_as_a_proposed_one():
    confirmed = confirm_target(_freq_target(), confirmed_by="engineer_a")
    state = _state(
        {"r1": {"requirement": "Resonates at 2.45 GHz", "target": confirmed}},
        [_ANALYSIS_DECISION],
    )
    item = compile_lab_test_plan(state)["items"][0]
    assert item["flag"] is None
    assert item["expected"]["target_status"] == "CONFIRMED"


def test_optimization_decision_overrides_analysis_as_most_refined():
    # STEP_ORDER runs ANALYSIS before OPTIMIZATION within one iteration;
    # _find_expected keeps the LAST match -- see "DESIGN QUESTION 2".
    state = _state(
        {"r1": {"requirement": "Resonates at 2.45 GHz", "target": _freq_target()}},
        [_ANALYSIS_DECISION, _OPTIMIZATION_DECISION],
    )
    item = compile_lab_test_plan(state)["items"][0]
    assert item["expected"]["value"] == pytest.approx(2.451e9)
    assert item["expected"]["source_step"] == "optimization"


# ---------------------------------------------------------------------------
# Iteration scoping (issue #88's LoopDecision.iteration, per this ticket's
# own hint in orchestration/design_loop.py)
# ---------------------------------------------------------------------------


def test_a_decision_from_a_prior_iteration_is_not_used_as_this_iterations_expected():
    stale_analysis = _decision(
        "analysis",
        {"function": "patch_resonant_frequency_hz", "resonant_frequency_hz": 2.40e9},
        "CALCULATED",
        iteration=1,
    )
    state = _state(
        {"r1": {"requirement": "Resonates at 2.45 GHz", "target": _freq_target()}},
        [stale_analysis],
        iteration=2,
    )
    item = compile_lab_test_plan(state)["items"][0]
    assert item["expected"] is None
    assert item["flag"]["reason"] == (UnverifiableReason.NO_ENGINEERING_RESULT_THIS_ITERATION.value)


def test_a_decision_with_unknown_iteration_is_not_used_as_this_iterations_expected():
    """A decision loaded from a pre-#88 dump carries `iteration=None`
    (issue #135) -- "nobody recorded which round this came from," not
    "round 1." It must not be mistaken for evidence belonging to the
    loop's current round, the same way a genuinely-stale prior-iteration
    decision (the sibling test above) is excluded."""
    unknown_round_analysis = _decision(
        "analysis",
        {"function": "patch_resonant_frequency_hz", "resonant_frequency_hz": 2.40e9},
        "CALCULATED",
        iteration=None,
    )
    state = _state(
        {"r1": {"requirement": "Resonates at 2.45 GHz", "target": _freq_target()}},
        [unknown_round_analysis],
        iteration=1,
    )
    item = compile_lab_test_plan(state)["items"][0]
    assert item["expected"] is None
    assert item["flag"]["reason"] == (UnverifiableReason.NO_ENGINEERING_RESULT_THIS_ITERATION.value)


def test_mixed_unknown_and_current_iteration_decisions_only_the_current_one_is_used():
    """A mixed old/new decisions list -- one decision with no recorded
    round at all (`iteration=None`) alongside a real current-iteration one
    -- traces the expected value only to the current-iteration decision,
    never the unknown one, and never conflates the two."""
    unknown_round_analysis = _decision(
        "analysis",
        {"function": "patch_resonant_frequency_hz", "resonant_frequency_hz": 2.40e9},
        "CALCULATED",
        iteration=None,
    )
    current_iteration_analysis = _decision(
        "analysis",
        {"function": "patch_resonant_frequency_hz", "resonant_frequency_hz": 2.46e9},
        "CALCULATED",
        iteration=1,
    )
    state = _state(
        {"r1": {"requirement": "Resonates at 2.45 GHz", "target": _freq_target()}},
        [unknown_round_analysis, current_iteration_analysis],
        iteration=1,
    )
    item = compile_lab_test_plan(state)["items"][0]
    assert item["expected"]["value"] == pytest.approx(2.46e9)
    assert item["expected"]["source_iteration"] == 1


def test_a_decision_from_the_current_iteration_is_used_even_if_not_the_latest_overall():
    current_iteration_analysis = _decision(
        "analysis",
        {"function": "patch_resonant_frequency_hz", "resonant_frequency_hz": 2.46e9},
        "CALCULATED",
        iteration=2,
    )
    later_but_irrelevant = _decision(
        "architecture", {"decision": "iterate again", "rationale": "..."}, None, iteration=2
    )
    state = _state(
        {"r1": {"requirement": "Resonates at 2.45 GHz", "target": _freq_target()}},
        [current_iteration_analysis, later_but_irrelevant],
        iteration=2,
    )
    item = compile_lab_test_plan(state)["items"][0]
    assert item["expected"]["value"] == pytest.approx(2.46e9)


# ---------------------------------------------------------------------------
# Batching -- one document, every requirement, mixed outcomes
# ---------------------------------------------------------------------------


def test_plan_covers_every_requirement_in_one_document_with_mixed_outcomes():
    requirements = {
        "freq_req": {"requirement": "Resonates at 2.45 GHz", "target": _freq_target()},
        "gain_req": {"requirement": "Gain >= 5 dBi", "target": _gain_target()},
        "vague_req": {"requirement": "Should feel robust when flexed"},
        "unscoreable_req": {
            "requirement": "Should look nice",
            "target": mark_unscoreable("no numeric bound stated"),
        },
    }
    state = _state(requirements, [_ANALYSIS_DECISION, _SIMULATION_DECISION])
    plan = compile_lab_test_plan(state)

    assert len(plan["items"]) == 4
    by_id = {item["requirement_id"]: item for item in plan["items"]}
    assert by_id["freq_req"]["flag"] is None
    assert by_id["gain_req"]["flag"]["reason"] == (
        UnverifiableReason.QUANTITY_NOT_TOUCHSTONE_MEASURABLE.value
    )
    assert by_id["vague_req"]["flag"]["reason"] == UnverifiableReason.NO_TARGET_RECORDED.value
    assert by_id["unscoreable_req"]["flag"]["reason"] == (
        UnverifiableReason.UNSCOREABLE_TARGET.value
    )
    assert set(plan["flagged_requirement_ids"]) == {"gain_req", "vague_req", "unscoreable_req"}
    assert plan["loop_id"] == "loop-test"
    assert plan["iteration"] == 1
    assert plan["provenance"] is None


def test_how_to_return_results_names_touchstone_file_and_measurement_step():
    state = _state({"r1": {"requirement": "Resonates at 2.45 GHz", "target": _freq_target()}}, [])
    plan = compile_lab_test_plan(state)
    guidance = plan["how_to_return_results"]
    assert "touchstone_file" in guidance["feed_into_measurement"]
    assert "advance_design_loop_step" in guidance["feed_into_measurement"]
    assert ".sNp" in guidance["bring_back"]


# ---------------------------------------------------------------------------
# Read-only / no-mutation guarantee
# ---------------------------------------------------------------------------


def test_compiling_a_plan_does_not_mutate_the_state_or_its_requirements():
    requirements = {"r1": {"requirement": "Resonates at 2.45 GHz", "target": _freq_target()}}
    state = _state(requirements, [_ANALYSIS_DECISION])
    before_decisions = list(state.decisions)
    before_requirements = dict(state.requirements)

    compile_lab_test_plan(state)

    assert state.decisions == before_decisions
    assert state.requirements == before_requirements
    assert state.completed is False


def test_compile_lab_test_plan_accepts_a_requirements_override():
    # Exercises the seam compile_lab_test_plan_for_loop uses to pass a
    # freshly-read designs.requirements payload instead of the loop's own
    # frozen snapshot -- see this module's docstring, "REQUIREMENTS
    # FRESHNESS".
    state = _state({"stale": {"requirement": "stale prose"}}, [_ANALYSIS_DECISION])
    fresh_requirements = {"r1": {"requirement": "Resonates at 2.45 GHz", "target": _freq_target()}}
    plan = compile_lab_test_plan(state, requirements=fresh_requirements)
    assert [item["requirement_id"] for item in plan["items"]] == ["r1"]


# ---------------------------------------------------------------------------
# Real end-to-end loop state, driven through start_design_loop/advance_loop_step
# ---------------------------------------------------------------------------


def test_compiles_against_a_real_loop_state_mid_loop_with_no_approval_needed():
    from orchestration.design_loop import start_design_loop

    requirements = {"r1": {"requirement": "Resonates at 2.45 GHz", "target": _freq_target()}}
    state = start_design_loop(requirements)

    # Safe to call before a single step past REQUIREMENTS has advanced --
    # no approval, no mutation, no exception.
    plan = compile_lab_test_plan(state)
    assert plan["items"][0]["flag"]["reason"] == (
        UnverifiableReason.NO_ENGINEERING_RESULT_THIS_ITERATION.value
    )
    assert state.current_step == "architecture"
