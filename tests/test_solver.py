# ruff: noqa: E501 -- this file transcribes fixed-column NEC2 output text
# verbatim, matching tests/test_design_loop.py's/tests/test_nec2pp.py's own
# header comment for why (reflowing it would break the exact fixed-column
# shape the parser under test reads).
"""Tests for orchestration/solver.py (issue #95, docs/adr/0014).

Pure-logic tests -- no database needed. `run_candidate_search` accepts a
TOOLING-shaped state dict (carrying `design_id`), but `design_id` is never
validated against a real `designs` row for any of the ungated ANALYSIS/
SIMULATION/OPTIMIZATION steps this module ever drives -- only a
REDESIGN_DECISION flush (`orchestration/tooling.py`'s `_flush_decisions`)
touches Postgres, and this module never reaches REDESIGN_DECISION (see
orchestration/solver.py's own docstring, "SCOPE"). So `_state_at_analysis`
below builds a tooling-shaped state by calling `orchestration.design_loop.
start_design_loop` directly and stamping on a synthetic `design_id`/
`design_key`/`persisted_decision_count` -- exactly the fields `orchestration.
tooling.start_new_design_loop` would have added, without that function's
real `designs.service.create_design` database write. This is legitimate
specifically because every test below only ever exercises this module's own
ANALYSIS/SIMULATION/OPTIMIZATION span; a DB-backed equivalent of the
persistence-readiness proof lives in tests/test_tooling.py instead (per
issue #95's own instructions -- that suite needs a live Postgres this
sandbox does not have, see tests/test_tooling.py's own module docstring).

Reuses tests/test_design_loop.py's fake-NEC2++-executable convention
(duplicated, not imported, matching that suite's own per-file convention)
and tests/test_nec2pp.py's RADIATION-PATTERNS-bearing GUIDE_SAMPLE_OUTPUT
(rather than tests/test_design_loop.py's own patternless one) specifically
because this file's SIMULATION-step scoring tests need a real, non-None
`gain_dbi` -- test_design_loop.py's own sample has no RADIATION PATTERNS
section, so `gain_dbi` parses to `None` there.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

import orchestration.solver as solver_module
from conftest import make_fake_executable
from designs.requirement_targets import mark_unscoreable, propose_target
from orchestration.approval import request_loop_step_approval
from orchestration.design_loop import DesignStep, start_design_loop
from orchestration.solver import SolverError, run_candidate_search
from orchestration.tooling import advance_design_loop_step
from rf_tools.calculations import patch_resonant_frequency_hz

REQUIREMENTS = {"R1": {"requirement": "resonant frequency near 2.45 GHz"}}

_ARCHITECTURE_INPUT = {
    "decision": "rectangular microstrip patch on FR4",
    "rationale": "meets band/gain target with a simple, low-cost fabrication",
    "design_family": "patch_antenna",
}

# Base patch parameters (matches tests/test_design_loop.py's own fixture) --
# individual tests override "l_m" to get a specific ANALYSIS score.
_BASE_CANDIDATE = {"eps_r": 4.4, "w_m": 0.03, "h_m": 0.0016, "l_m": 0.0286}

_DIPOLE_GEOMETRY = {
    "wires": [
        {
            "tag": 1,
            "segments": 7,
            "x1_m": 0.0,
            "y1_m": 0.0,
            "z1_m": -0.25,
            "x2_m": 0.0,
            "y2_m": 0.0,
            "z2_m": 0.25,
            "radius_m": 0.001,
        }
    ]
}

# Transcribed verbatim from the NEC-2 User's Guide's "Example 1" -- see
# tests/test_nec2pp.py's own module docstring for the citation. Unlike
# tests/test_design_loop.py's GUIDE_SAMPLE_OUTPUT, this one carries a
# RADIATION PATTERNS section, so gain_dbi parses to a real number (8.52) --
# needed for this file's SIMULATION-step scoring tests.
_GUIDE_SAMPLE_OUTPUT_WITH_PATTERN = """
                                          - - - ANTENNA INPUT PARAMETERS - - -
   TAG   SEG.    VOLTAGE (VOLTS)         CURRENT (AMPS)         IMPEDANCE (OHMS)        ADMITTANCE (MHOS)      POWER
   NO.   NO.    REAL        IMAG.       REAL        IMAG.       REAL        IMAG.       REAL        IMAG.     (WATTS)
     0     4 1.00000E+00 0.00000E+00 9.20585E-03-5.15474E-03 8.26979E+01 4.63060E+01 9.20585E-03-5.15474E-03 4.60292E-03
                                                - - - RADIATION PATTERNS - - -
  - - ANGLES - -           - POWER GAINS -       - - - POLARIZATION - - -    - - - E(THETA) - - -    - - - E(PHI) - - -
  THETA     PHI        VERT.   HOR.    TOTAL      AXIAL     TILT   SENSE     MAGNITUDE    PHASE     MAGNITUDE    PHASE
 DEGREES  DEGREES       DB      DB      DB        RATIO     DEG.              VOLTS/M    DEGREES      VOLTS/M    DEGREES
     .00      .00    -999.99 -999.99 -999.99     .00000      .00            0.00000E-01      .00    0.00000E-01      .00
   10.00      .00      -9.87 -999.99   -9.87     .00000      .00  LINEAR    1.69640E-01  -114.38    0.00000E-01      .00
   20.00      .00      -4.20 -999.99   -4.20     .00000      .00  LINEAR    3.25649E-01  -114.64    0.00000E-01      .00
   90.00      .00       8.52 -999.99    8.52     .00000      .00  LINEAR    1.40967E+00    62.47    0.00000E-01      .00
   AVERAGE POWER GAIN= 2.02793E+00       SOLID ANGLE USED IN AVERAGING=(  .5000)*PI STERADIANS.
"""

_FAKE_NEC2PP_PY = '''
import sys

OUTPUT = """{sample}"""

args = sys.argv[1:]
assert "-i" in args, args
sys.stdout.write(OUTPUT)
sys.exit(0)
'''


def _make_fake_nec2pp(tmp_path: Path) -> Path:
    body = _FAKE_NEC2PP_PY.format(sample=_GUIDE_SAMPLE_OUTPUT_WITH_PATTERN)
    return make_fake_executable(tmp_path, body, name="fake_nec2pp")


def _fingerprint(state: dict, step: DesignStep, step_input: dict) -> dict:
    return {
        "loop_id": state["loop_id"],
        "iteration": state["iteration"],
        "step": step.value,
        "content": step_input,
    }


def _state_at_analysis(design_id: int = 1, design_key: str = "SOLVER-TEST") -> dict:
    """A tooling-shaped state positioned at ANALYSIS, inside an approved
    architecture -- see this module's own docstring for why a synthetic
    design_id (not a real designs.service.create_design row) is legitimate
    here."""
    state = start_design_loop(REQUIREMENTS).to_dict()
    state["design_id"] = design_id
    state["design_key"] = design_key
    state["persisted_decision_count"] = 0

    fields = _fingerprint(state, DesignStep.ARCHITECTURE, _ARCHITECTURE_INPUT)
    receipt = request_loop_step_approval(
        fields, approved_by="jane.engineer", approval_callback=lambda f: True
    )
    state = advance_design_loop_step(state, _ARCHITECTURE_INPUT, approval=receipt.to_dict())
    assert state["current_step"] == DesignStep.ANALYSIS.value
    return state


def _exact_frequency_target(candidate: dict, tolerance: float = 0.0) -> dict:
    """A PROPOSED target whose value is exactly the ANALYSIS-step frequency
    `candidate` produces -- guarantees a 100%-scoring candidate for tests
    that need one, without hand-computing patch_resonant_frequency_hz's
    output by hand."""
    achieved = patch_resonant_frequency_hz(
        candidate["eps_r"], candidate["w_m"], candidate["h_m"], candidate["l_m"]
    )
    return propose_target(value=achieved, comparator="EQUALS", unit="Hz", tolerance=tolerance)


def _full_candidate(tmp_path: Path, fake_nec2pp: Path, **overrides) -> dict:
    """A candidate carrying every field ANALYSIS/SIMULATION/OPTIMIZATION
    each need -- required whenever `state` starts at ANALYSIS, since
    steps_to_drive from ANALYSIS is the WHOLE span (this module drives
    every step in it for every candidate, scoring only whichever ones
    `score_specs` names -- see orchestration/solver.py's own docstring,
    "SCORING"). `overrides` replaces/adds individual fields (e.g. a
    different `l_m` to get a specific ANALYSIS score)."""
    candidate = {
        **_BASE_CANDIDATE,
        "geometry": _DIPOLE_GEOMETRY,
        "frequency_hz": 300e6,
        "reference_impedance_ohms": 50.0,
        "executable": str(fake_nec2pp),
        "workdir": str(tmp_path / "nec2_run"),
        "target_frequency_hz": 2.45e9,
        "length_lower_m": 0.02,
        "length_upper_m": 0.04,
        "method": "sweep",
        "n_evaluations": 5,
    }
    candidate.update(overrides)
    return candidate


# ---------------------------------------------------------------------------
# Group 1: call-level validation (SolverError) -- before any candidate runs.
# ---------------------------------------------------------------------------


def test_state_must_be_a_dict():
    with pytest.raises(SolverError, match="state must be a dict"):
        run_candidate_search("not a dict", [{"l_m": 0.02}], {"analysis": {"target": {}}})


def test_state_missing_required_keys_is_rejected():
    with pytest.raises(SolverError, match="missing required key"):
        run_candidate_search({"design_id": 1}, [{"l_m": 0.02}], {"analysis": {"target": {}}})


def test_state_with_none_design_id_is_rejected():
    state = _state_at_analysis(design_id=None)
    with pytest.raises(SolverError, match="design_id"):
        run_candidate_search(
            state,
            [_BASE_CANDIDATE],
            {"analysis": {"target": _exact_frequency_target(_BASE_CANDIDATE)}},
        )


def test_candidates_must_be_a_nonempty_list():
    state = _state_at_analysis()
    with pytest.raises(SolverError, match="non-empty list"):
        run_candidate_search(state, [], {"analysis": {"target": {}}})


def test_candidates_items_must_be_dicts():
    state = _state_at_analysis()
    with pytest.raises(SolverError, match="must be a dict"):
        run_candidate_search(state, ["not a dict"], {"analysis": {"target": {}}})


def test_score_specs_must_be_a_nonempty_dict():
    state = _state_at_analysis()
    with pytest.raises(SolverError, match="non-empty dict"):
        run_candidate_search(state, [_BASE_CANDIDATE], {})


def test_score_specs_step_name_must_be_drivable():
    state = _state_at_analysis()
    with pytest.raises(SolverError, match="drivable steps"):
        run_candidate_search(
            state,
            [_BASE_CANDIDATE],
            {"redesign_decision": {"target": _exact_frequency_target(_BASE_CANDIDATE)}},
        )


def test_score_specs_target_must_not_be_unscoreable():
    state = _state_at_analysis()
    unscoreable = mark_unscoreable("prose states no numeric bound")
    with pytest.raises(SolverError, match="UNSCOREABLE"):
        run_candidate_search(state, [_BASE_CANDIDATE], {"analysis": {"target": unscoreable}})


def test_score_specs_must_share_a_step_with_the_driven_span(tmp_path):
    # Drive to a state already positioned at OPTIMIZATION for real, then
    # ask for "analysis" to be scored -- steps_to_drive from OPTIMIZATION
    # is just [OPTIMIZATION], so "analysis" shares nothing with it.
    state = _state_at_analysis()
    state = advance_design_loop_step(state, _BASE_CANDIDATE)
    fake_nec2pp = _make_fake_nec2pp(tmp_path)
    state = advance_design_loop_step(
        state,
        {
            "geometry": _DIPOLE_GEOMETRY,
            "frequency_hz": 300e6,
            "reference_impedance_ohms": 50.0,
            "executable": str(fake_nec2pp),
            "workdir": str(tmp_path / "nec2_run"),
        },
    )
    assert state["current_step"] == DesignStep.OPTIMIZATION.value

    target = _exact_frequency_target(_BASE_CANDIDATE)
    with pytest.raises(SolverError, match="none of score_specs"):
        run_candidate_search(state, [_BASE_CANDIDATE], {"analysis": {"target": target}})


def test_plateau_window_must_be_positive():
    state = _state_at_analysis()
    target = _exact_frequency_target(_BASE_CANDIDATE)
    with pytest.raises(SolverError, match="plateau_window"):
        run_candidate_search(
            state, [_BASE_CANDIDATE], {"analysis": {"target": target}}, plateau_window=0
        )


def test_plateau_epsilon_must_be_nonnegative():
    state = _state_at_analysis()
    target = _exact_frequency_target(_BASE_CANDIDATE)
    with pytest.raises(SolverError, match="plateau_epsilon"):
        run_candidate_search(
            state, [_BASE_CANDIDATE], {"analysis": {"target": target}}, plateau_epsilon=-1.0
        )


def test_evaluation_budget_must_be_positive():
    state = _state_at_analysis()
    target = _exact_frequency_target(_BASE_CANDIDATE)
    with pytest.raises(SolverError, match="evaluation_budget"):
        run_candidate_search(
            state, [_BASE_CANDIDATE], {"analysis": {"target": target}}, evaluation_budget=0
        )


def test_design_id_argument_must_be_an_int_or_none():
    """The CALL-level `design_id` keyword argument (run_candidate_search's
    own parameter, checked directly against `isinstance(design_id, int)`) --
    distinct from `test_state_with_none_design_id_is_rejected` above, which
    exercises `state["design_id"]` (a different field, validated inside
    `_validate_state_shape`). `None` is the valid "no seeding" sentinel for
    this argument (see Group 6 below), so only a non-int, non-None value
    (e.g. a str) should trip this branch."""
    state = _state_at_analysis()
    target = _exact_frequency_target(_BASE_CANDIDATE)
    with pytest.raises(SolverError, match="design_id must be an int or None"):
        run_candidate_search(
            state,
            [_BASE_CANDIDATE],
            {"analysis": {"target": target}},
            design_id="not-an-int",
        )


def test_result_field_override_without_explicit_unit_is_rejected():
    state = _state_at_analysis()
    target = _exact_frequency_target(_BASE_CANDIDATE)
    with pytest.raises(SolverError, match="unit"):
        run_candidate_search(
            state,
            [_BASE_CANDIDATE],
            {"analysis": {"target": target, "result_field": "function"}},
        )


# ---------------------------------------------------------------------------
# Group 2: the non-negotiable gate proof (docs/adr/0014).
# ---------------------------------------------------------------------------


def test_module_never_imports_approval_receipt_machinery():
    """The structural half of the gate proof: this module cannot construct
    or accept a LoopStepApprovalReceipt because it never even imports the
    names that would let it -- not merely "doesn't call them today". Parses
    the AST's own import statements rather than substring-matching the raw
    source text, since this module's docstring legitimately DISCUSSES both
    names in prose (explaining exactly this property) without importing
    either."""
    import ast
    import inspect

    tree = ast.parse(inspect.getsource(solver_module))
    imported_names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            imported_names.update(alias.asname or alias.name for alias in node.names)
        elif isinstance(node, ast.Import):
            imported_names.update(alias.asname or alias.name for alias in node.names)

    assert "LoopStepApprovalReceipt" not in imported_names
    assert "request_loop_step_approval" not in imported_names
    assert not hasattr(solver_module, "LoopStepApprovalReceipt")
    assert not hasattr(solver_module, "request_loop_step_approval")


def test_solver_halts_at_a_gated_architecture_step_and_grants_no_receipt():
    state = start_design_loop(REQUIREMENTS).to_dict()
    state["design_id"] = 1
    state["design_key"] = "SOLVER-GATE-TEST"
    state["persisted_decision_count"] = 0
    assert state["current_step"] == DesignStep.ARCHITECTURE.value

    target = _exact_frequency_target(_BASE_CANDIDATE)
    result = run_candidate_search(state, [_BASE_CANDIDATE], {"analysis": {"target": target}})

    assert result["stop_reason"] == "gated_step_pending_approval"
    assert result["candidates_evaluated"] == 0
    assert result["trail"] == []
    assert result["best_candidate_state"] is None
    # The loop's own, untouched pending_approval report -- ARCHITECTURE
    # named, requires_approval True, no receipt anywhere in sight.
    assert result["pending_approval"]["step"] == DesignStep.ARCHITECTURE.value
    assert result["pending_approval"]["requires_approval"] is True
    assert "approved" not in str(result["pending_approval"]).lower().replace(
        "requires_approval", ""
    )


def test_solver_halts_at_measurement_with_pending_approval_reported(tmp_path):
    state = _state_at_analysis()
    state = advance_design_loop_step(state, _BASE_CANDIDATE)
    fake_nec2pp = _make_fake_nec2pp(tmp_path)
    state = advance_design_loop_step(
        state,
        {
            "geometry": _DIPOLE_GEOMETRY,
            "frequency_hz": 300e6,
            "reference_impedance_ohms": 50.0,
            "executable": str(fake_nec2pp),
            "workdir": str(tmp_path / "nec2_run"),
        },
    )
    state = advance_design_loop_step(
        state,
        {
            "eps_r": 4.4,
            "w_m": 0.03,
            "h_m": 0.0016,
            "target_frequency_hz": 2.45e9,
            "length_lower_m": 0.02,
            "length_upper_m": 0.04,
            "method": "sweep",
            "n_evaluations": 5,
        },
    )
    state = advance_design_loop_step(
        state,
        {
            "requirement_id": "R1",
            "requirement": "resonant frequency within band",
            "method": "analysis",
            "expected": 2.45e9,
            "actual": state["decisions"][-1]["result"]["achieved_frequency_hz"],
            "status": "PASS",
        },
    )
    assert state["current_step"] == DesignStep.MEASUREMENT.value

    target = _exact_frequency_target(_BASE_CANDIDATE)
    result = run_candidate_search(state, [_BASE_CANDIDATE], {"analysis": {"target": target}})

    assert result["stop_reason"] == "gated_step_pending_approval"
    assert result["candidates_evaluated"] == 0
    assert result["pending_approval"]["step"] == DesignStep.MEASUREMENT.value


def _write_measured_touchstone(tmp_path: Path, name: str = "measured") -> Path:
    """A real one-port Touchstone file, same construction as
    tests/test_design_loop.py's own helper of the same name (duplicated,
    not imported, matching this suite's per-file convention)."""
    import numpy as np
    import skrf as rf

    freqs_hz = [2.0e9, 2.5e9, 3.0e9]
    f = rf.Frequency.from_f(freqs_hz, unit="hz")
    s = np.zeros((3, 1, 1), dtype=complex)
    s[:, 0, 0] = 10 ** (-15 / 20)
    ntwk = rf.Network(frequency=f, s=s, z0=50)
    path = tmp_path / f"{name}.s1p"
    ntwk.write_touchstone(path.with_suffix(""))
    return path


def _grant_and_advance(state: dict, step: DesignStep, step_input: dict) -> dict:
    fields = _fingerprint(state, step, step_input)
    receipt = request_loop_step_approval(
        fields, approved_by="jane.engineer", approval_callback=lambda f: True
    )
    return advance_design_loop_step(state, step_input, approval=receipt.to_dict())


def test_solver_halts_at_a_gated_redesign_decision_step_with_no_receipt_ever_created(tmp_path):
    """The single most load-bearing test in this file: drives a state all
    the way to REDESIGN_DECISION (gated) via the REAL loop functions
    (including a real MEASUREMENT approval and a real Touchstone file),
    then proves run_candidate_search neither raises, nor advances, nor
    produces (or requires) any LoopStepApprovalReceipt for THAT gate --
    it just reports the pending approval."""
    state = _state_at_analysis()
    state = advance_design_loop_step(state, _BASE_CANDIDATE)
    fake_nec2pp = _make_fake_nec2pp(tmp_path)
    state = advance_design_loop_step(
        state,
        {
            "geometry": _DIPOLE_GEOMETRY,
            "frequency_hz": 300e6,
            "reference_impedance_ohms": 50.0,
            "executable": str(fake_nec2pp),
            "workdir": str(tmp_path / "nec2_run"),
        },
    )
    state = advance_design_loop_step(
        state,
        {
            "eps_r": 4.4,
            "w_m": 0.03,
            "h_m": 0.0016,
            "target_frequency_hz": 2.45e9,
            "length_lower_m": 0.02,
            "length_upper_m": 0.04,
            "method": "sweep",
            "n_evaluations": 5,
        },
    )
    state = advance_design_loop_step(
        state,
        {
            "requirement_id": "R1",
            "requirement": "resonant frequency within band",
            "method": "analysis",
            "expected": 2.45e9,
            "actual": state["decisions"][-1]["result"]["achieved_frequency_hz"],
            "status": "PASS",
        },
    )
    touchstone_path = _write_measured_touchstone(tmp_path, name="solver-gate-test")
    state = _grant_and_advance(
        state, DesignStep.MEASUREMENT, {"touchstone_file": str(touchstone_path)}
    )
    state = advance_design_loop_step(
        state,
        {
            "simulated": {
                "frequency_hz": [2.0e9, 2.5e9, 3.0e9],
                "s_parameters": {"S11": ["0.1+0.01j", "0.2+0.02j", "0.3+0.03j"]},
                "z0": 50.0,
            }
        },
    )
    assert state["current_step"] == DesignStep.REDESIGN_DECISION.value

    target = _exact_frequency_target(_BASE_CANDIDATE)
    before = dict(state)
    result = run_candidate_search(state, [_BASE_CANDIDATE], {"analysis": {"target": target}})

    # state is untouched (this module never mutates its input).
    assert state == before
    assert result["stop_reason"] == "gated_step_pending_approval"
    assert result["candidates_evaluated"] == 0
    assert result["best_candidate_state"] is None
    assert result["pending_approval"]["step"] == DesignStep.REDESIGN_DECISION.value


# ---------------------------------------------------------------------------
# Group 3: out-of-scope (ungated but undriven) steps, and a completed loop.
# ---------------------------------------------------------------------------


def test_solver_halts_out_of_scope_at_verification(tmp_path):
    state = _state_at_analysis()
    state = advance_design_loop_step(state, _BASE_CANDIDATE)
    fake_nec2pp = _make_fake_nec2pp(tmp_path)
    state = advance_design_loop_step(
        state,
        {
            "geometry": _DIPOLE_GEOMETRY,
            "frequency_hz": 300e6,
            "reference_impedance_ohms": 50.0,
            "executable": str(fake_nec2pp),
            "workdir": str(tmp_path / "nec2_run"),
        },
    )
    state = advance_design_loop_step(
        state,
        {
            "eps_r": 4.4,
            "w_m": 0.03,
            "h_m": 0.0016,
            "target_frequency_hz": 2.45e9,
            "length_lower_m": 0.02,
            "length_upper_m": 0.04,
            "method": "sweep",
            "n_evaluations": 5,
        },
    )
    assert state["current_step"] == DesignStep.VERIFICATION.value

    target = _exact_frequency_target(_BASE_CANDIDATE)
    result = run_candidate_search(state, [_BASE_CANDIDATE], {"analysis": {"target": target}})

    assert result["stop_reason"] == "out_of_scope_step"
    assert result["candidates_evaluated"] == 0
    assert result["pending_approval"] is None


def test_solver_halts_when_loop_already_completed():
    state = _state_at_analysis()
    state = advance_design_loop_step(state, _BASE_CANDIDATE)
    state["completed"] = True  # simulate an already-finished loop

    target = _exact_frequency_target(_BASE_CANDIDATE)
    result = run_candidate_search(state, [_BASE_CANDIDATE], {"analysis": {"target": target}})

    assert result["stop_reason"] == "loop_completed"
    assert result["candidates_evaluated"] == 0


# ---------------------------------------------------------------------------
# Group 4: real candidate driving -- ANALYSIS only.
# ---------------------------------------------------------------------------


def test_single_candidate_scores_analysis_and_drives_the_whole_ungated_span(tmp_path):
    """From ANALYSIS, steps_to_drive is the WHOLE span (ANALYSIS/
    SIMULATION/OPTIMIZATION) -- see orchestration/solver.py's docstring,
    "SCORING" -- so even a caller who only wants ANALYSIS scored must
    supply a candidate carrying every field the later steps need too."""
    state = _state_at_analysis()
    fake_nec2pp = _make_fake_nec2pp(tmp_path)
    candidate = _full_candidate(tmp_path, fake_nec2pp)
    target = _exact_frequency_target(candidate, tolerance=5e7)
    result = run_candidate_search(state, [candidate], {"analysis": {"target": target}})

    assert result["provenance"] == "CALCULATED"
    assert result["candidates_requested"] == 1
    assert result["candidates_evaluated"] == 1
    # A single, exactly-on-target candidate satisfies the target -- this
    # is not the evaluation_budget test (see test_evaluation_budget_* below).
    assert result["stop_reason"] == "target_satisfaction"
    entry = result["trail"][0]
    assert entry["status"] == "evaluated"
    assert entry["failed_at_step"] is None
    assert [s["step"] for s in entry["steps"]] == ["analysis", "simulation", "optimization"]
    step_entry = entry["steps"][0]
    assert step_entry["decision_provenance"] == "CALCULATED"
    assert step_entry["score"]["score_percent"] == pytest.approx(100.0)
    assert step_entry["score"]["target_status"] == "PROPOSED"
    assert step_entry["score"]["target_provenance"] == "ASSUMED"
    # Only "analysis" was in score_specs -- simulation/optimization were
    # still driven (recorded) but never scored.
    assert entry["steps"][1]["score"] is None
    assert entry["steps"][2]["score"] is None
    assert entry["overall_score_percent"] == pytest.approx(100.0)
    assert entry["all_targets_met"] is True
    assert result["best_candidate_index"] == 0
    assert result["best_candidate_state"]["current_step"] == DesignStep.VERIFICATION.value
    assert result["best_candidate_state"]["design_id"] == state["design_id"]
    # The winning candidate's decisions are on the returned state, ready
    # for the existing REDESIGN_DECISION flush once this design continues
    # that far (docs/adr/0011) -- this module itself never flushes
    # anything.
    assert [d["step"] for d in result["best_candidate_state"]["decisions"][-3:]] == [
        "analysis",
        "simulation",
        "optimization",
    ]


def test_target_satisfaction_stops_the_search_early(tmp_path):
    state = _state_at_analysis()
    fake_nec2pp = _make_fake_nec2pp(tmp_path)
    good = _full_candidate(tmp_path, fake_nec2pp)
    target = _exact_frequency_target(good, tolerance=5e7)
    candidates = [
        _full_candidate(tmp_path, fake_nec2pp, l_m=0.02),  # far off target
        good,  # exact hit
        _full_candidate(tmp_path, fake_nec2pp, l_m=0.025),  # would never be reached
    ]
    result = run_candidate_search(state, candidates, {"analysis": {"target": target}})

    assert result["stop_reason"] == "target_satisfaction"
    assert result["candidates_evaluated"] == 2
    assert len(result["trail"]) == 2
    assert result["best_candidate_index"] == 1
    assert result["best_candidate_overall_score_percent"] == pytest.approx(100.0)


def test_evaluation_budget_caps_a_larger_batch(tmp_path):
    state = _state_at_analysis()
    fake_nec2pp = _make_fake_nec2pp(tmp_path)
    off_target_candidates = [
        _full_candidate(tmp_path, fake_nec2pp, l_m=0.02 + 0.0001 * i) for i in range(10)
    ]
    # A target none of these will exactly satisfy.
    target = propose_target(value=1.0e9, comparator="EQUALS", unit="Hz", tolerance=1.0)
    result = run_candidate_search(
        state, off_target_candidates, {"analysis": {"target": target}}, evaluation_budget=3
    )

    assert result["evaluation_budget"] == 3
    assert result["candidates_evaluated"] == 3
    assert result["candidates_requested"] == 10
    assert result["stop_reason"] == "evaluation_budget"


def test_evaluation_budget_is_capped_at_the_supplied_candidate_count(tmp_path):
    state = _state_at_analysis()
    fake_nec2pp = _make_fake_nec2pp(tmp_path)
    candidate = _full_candidate(tmp_path, fake_nec2pp)
    target = propose_target(value=1.0e9, comparator="EQUALS", unit="Hz", tolerance=1.0)
    result = run_candidate_search(
        state, [candidate], {"analysis": {"target": target}}, evaluation_budget=99
    )
    assert result["evaluation_budget"] == 1


def test_a_failing_candidate_is_recorded_and_the_search_continues(tmp_path):
    state = _state_at_analysis()
    fake_nec2pp = _make_fake_nec2pp(tmp_path)
    good = _full_candidate(tmp_path, fake_nec2pp)
    target = _exact_frequency_target(good, tolerance=5e7)
    broken_candidate = {"eps_r": 4.4, "w_m": 0.03, "h_m": 0.0016}  # missing "l_m"
    result = run_candidate_search(state, [broken_candidate, good], {"analysis": {"target": target}})

    assert result["candidates_evaluated"] == 2
    first, second = result["trail"]
    assert first["status"] == "failed"
    assert first["failed_at_step"] == "analysis"
    assert "l_m" in first["error"]
    assert first["steps"] == []  # ANALYSIS is the first step -- nothing ran
    assert first["overall_score_percent"] is None
    assert second["status"] == "evaluated"
    assert second["overall_score_percent"] == pytest.approx(100.0)
    # The failed candidate never becomes the winner, and never breaks the
    # run for the candidate after it.
    assert result["best_candidate_index"] == 1
    assert result["stop_reason"] == "target_satisfaction"


def test_a_candidate_failing_partway_through_keeps_its_earlier_steps_scores(tmp_path):
    """A candidate whose ANALYSIS succeeds but SIMULATION fails (a missing
    field, standing in for issue #95's own "a missing NEC2 binary" example)
    still reports its ANALYSIS score -- see orchestration/solver.py's
    docstring, "DESIGN QUESTION 4"."""
    state = _state_at_analysis()
    analysis_target = _exact_frequency_target(_BASE_CANDIDATE, tolerance=5e7)
    candidate = dict(_BASE_CANDIDATE)  # no geometry/frequency_hz at all
    result = run_candidate_search(state, [candidate], {"analysis": {"target": analysis_target}})

    entry = result["trail"][0]
    assert entry["status"] == "failed"
    assert entry["failed_at_step"] == "simulation"
    assert [s["step"] for s in entry["steps"]] == ["analysis"]
    assert entry["steps"][0]["score"]["score_percent"] == pytest.approx(100.0)
    assert entry["overall_score_percent"] == pytest.approx(100.0)
    # Still never becomes the winner -- its state is stuck mid-span.
    assert result["best_candidate_index"] is None
    assert result["best_candidate_state"] is None


def test_score_plateau_stops_after_the_window(tmp_path):
    state = _state_at_analysis()
    fake_nec2pp = _make_fake_nec2pp(tmp_path)
    # An unreachable target so no candidate ever satisfies it outright --
    # isolates plateau detection from target_satisfaction.
    target = propose_target(value=1.0e9, comparator="EQUALS", unit="Hz", tolerance=1.0)
    same_candidate = _full_candidate(tmp_path, fake_nec2pp)
    candidates = [same_candidate] * 6  # identical score every time -> flat
    result = run_candidate_search(
        state,
        candidates,
        {"analysis": {"target": target}},
        plateau_window=3,
        plateau_epsilon=0.5,
    )

    assert result["stop_reason"] == "score_plateau"
    # plateau_window + 1 identical-score evaluations are needed before the
    # comparison has both endpoints (see orchestration/solver.py's own
    # docstring, "DESIGN QUESTION 2").
    assert result["candidates_evaluated"] == 4


def test_note_is_forwarded_to_every_scored_step(tmp_path):
    state = _state_at_analysis()
    fake_nec2pp = _make_fake_nec2pp(tmp_path)
    candidate = _full_candidate(
        tmp_path, fake_nec2pp, note="FR4 tolerance is +/-10% on eps_r -- treat with caution"
    )
    target = _exact_frequency_target(candidate, tolerance=5e7)
    result = run_candidate_search(state, [candidate], {"analysis": {"target": target}})

    score = result["trail"][0]["steps"][0]["score"]
    assert score["note"] == candidate["note"]
    assert score["note_provenance"] == "INFERRED"


def test_logs_are_emitted_per_step_and_per_candidate(tmp_path, caplog):
    state = _state_at_analysis()
    fake_nec2pp = _make_fake_nec2pp(tmp_path)
    candidate = _full_candidate(tmp_path, fake_nec2pp)
    target = _exact_frequency_target(candidate, tolerance=5e7)
    with caplog.at_level(logging.INFO, logger="orchestration.solver"):
        run_candidate_search(state, [candidate], {"analysis": {"target": target}})

    messages = [r.message for r in caplog.records]
    assert any("step scored" in m for m in messages)
    assert any("candidate 0 evaluated" in m for m in messages)


# ---------------------------------------------------------------------------
# Group 5: full ANALYSIS -> SIMULATION -> OPTIMIZATION drive, real fake-
# NEC2++ SIMULATION scoring, and continuing the winning state onward.
# ---------------------------------------------------------------------------


def test_full_span_drives_and_scores_all_three_ungated_steps(tmp_path):
    state = _state_at_analysis()
    fake_nec2pp = _make_fake_nec2pp(tmp_path)
    candidate = {
        **_BASE_CANDIDATE,
        "geometry": _DIPOLE_GEOMETRY,
        "frequency_hz": 300e6,
        "reference_impedance_ohms": 50.0,
        "executable": str(fake_nec2pp),
        "workdir": str(tmp_path / "nec2_run"),
        "target_frequency_hz": 2.45e9,
        "length_lower_m": 0.02,
        "length_upper_m": 0.04,
        "method": "sweep",
        "n_evaluations": 5,
    }
    analysis_target = _exact_frequency_target(candidate, tolerance=5e7)
    gain_target = propose_target(value=5.0, comparator="AT_LEAST", unit="dBi")
    optimization_target = propose_target(
        value=2.45e9, comparator="EQUALS", unit="Hz", tolerance=5e7
    )
    score_specs = {
        "analysis": {"target": analysis_target},
        "simulation": {"target": gain_target},
        "optimization": {"target": optimization_target},
    }

    result = run_candidate_search(state, [candidate], score_specs)

    entry = result["trail"][0]
    assert [s["step"] for s in entry["steps"]] == ["analysis", "simulation", "optimization"]
    sim_score = entry["steps"][1]["score"]
    assert sim_score["actual_value"] == pytest.approx(8.52)  # GUIDE_SAMPLE_OUTPUT's max gain
    assert sim_score["target_met"] is True  # 8.52 >= 5.0 dBi
    opt_score = entry["steps"][2]["score"]
    assert opt_score["step"] == "optimization"
    # overall_score_percent is the WORST of the three scored steps -- see
    # orchestration/solver.py's docstring, "DESIGN QUESTION 3".
    assert entry["overall_score_percent"] == pytest.approx(
        min(s["score"]["score_percent"] for s in entry["steps"])
    )
    assert result["convergence_rule"] == "worst_of_scored_steps"
    assert result["best_candidate_state"]["current_step"] == DesignStep.VERIFICATION.value


def test_winning_candidate_state_continues_cleanly_past_optimization(tmp_path):
    """The persistence-readiness proof this DB-less suite CAN make: the
    winning candidate's returned state is a real, continuable tooling-shaped
    state -- advancing it through VERIFICATION (itself not a flush point,
    so no database is needed here either) succeeds with no special
    handling, exactly as if an engineer had typed the same calls by hand,
    landing at the next gated step (MEASUREMENT) with the loop's own
    pending_approval report -- still no receipt in sight."""
    state = _state_at_analysis()
    fake_nec2pp = _make_fake_nec2pp(tmp_path)
    candidate = _full_candidate(tmp_path, fake_nec2pp)
    target = _exact_frequency_target(candidate, tolerance=5e7)
    result = run_candidate_search(state, [candidate], {"analysis": {"target": target}})
    won_state = result["best_candidate_state"]
    assert won_state["current_step"] == DesignStep.VERIFICATION.value

    # Continue by hand, exactly like tests/test_design_loop.py's end-to-end
    # test does -- no DB write happens until REDESIGN_DECISION.
    won_state = advance_design_loop_step(
        won_state,
        {
            "requirement_id": "R1",
            "requirement": "resonant frequency near 2.45 GHz",
            "method": "analysis",
            "expected": 2.45e9,
            "actual": won_state["decisions"][-1]["result"]["achieved_frequency_hz"],
            "status": "PASS",
        },
    )
    assert won_state["current_step"] == DesignStep.MEASUREMENT.value
    assert won_state["design_id"] == state["design_id"]
    assert won_state["pending_approval"]["step"] == DesignStep.MEASUREMENT.value
    assert [d["step"] for d in won_state["decisions"]][-4:] == [
        "analysis",
        "simulation",
        "optimization",
        "verification",
    ]


def test_result_field_override_with_explicit_unit_scores_a_different_field(tmp_path):
    state = _state_at_analysis()
    fake_nec2pp = _make_fake_nec2pp(tmp_path)
    candidate = _full_candidate(tmp_path, fake_nec2pp)
    target = propose_target(value=2.0, comparator="AT_LEAST", unit="linear")
    optimization_target = _exact_frequency_target(candidate, tolerance=5e7)
    score_specs = {
        "simulation": {
            "target": target,
            "result_field": "average_power_gain_linear",
            "unit": "linear",
        },
        # scoring "optimization" too only to prove the override didn't
        # disturb the DEFAULT-field lookup for a sibling step in the same
        # call -- not this test's main point.
        "optimization": {"target": optimization_target},
    }
    result = run_candidate_search(state, [candidate], score_specs)
    score = result["trail"][0]["steps"][1]["score"]
    assert score["actual_value"] == pytest.approx(2.02793)
    assert score["unit"] == "linear"


# ---------------------------------------------------------------------------
# Group 6: optional design_id -- seeding the plateau baseline from a
# design's own prior-recorded scores (issue #87's cross-run-learning
# follow-up to issue #95's own user story #21, "a design's score history
# across iterations"). Still no live database: run_candidate_search's own
# design_id-seeding code path talks to designs.db.read_engineering_
# results_for_scoring, which THIS suite fakes -- the same "fakes for the
# seam only" precedent this file's fake NEC2++ executable already
# establishes for the simulator seam -- so a design_id here never needs to
# be a real designs row, matching this whole file's existing conceit for
# every OTHER design_id used above.
# ---------------------------------------------------------------------------


class _FakeConn:
    """Stands in for designs.db.get_connection()'s real psycopg.Connection
    -- run_candidate_search only ever calls .close() on it once
    designs.db.read_engineering_results_for_scoring (also faked below) has
    already been monkeypatched to ignore the connection object entirely."""

    def close(self):
        pass


def test_design_id_defaults_to_no_seeding_and_never_touches_the_database(monkeypatch):
    # _state_at_analysis() built first, and unpatched: its own bootstrap
    # through tooling.advance_design_loop_step legitimately touches the
    # database now (issue #100's fresh-requirements read), which is
    # unrelated to what THIS test checks -- that run_candidate_search
    # itself never touches it when design_id is not supplied. The
    # monkeypatch below is installed only around that call.
    state = _state_at_analysis()

    def _must_not_be_called(*args, **kwargs):
        raise AssertionError(
            "designs_db.get_connection must not be called when design_id is not supplied"
        )

    monkeypatch.setattr(solver_module.designs_db, "get_connection", _must_not_be_called)

    target = _exact_frequency_target(_BASE_CANDIDATE)
    result = run_candidate_search(state, [_BASE_CANDIDATE], {"analysis": {"target": target}})

    assert result["prior_best_score"] is None
    assert result["prior_iteration"] is None


def test_design_id_with_no_prior_recorded_rows_leaves_prior_best_score_none(monkeypatch):
    # _state_at_analysis() built first, and unpatched -- see the identical
    # note on test_design_id_defaults_to_no_seeding_and_never_touches_the_
    # database above; its bootstrap now legitimately touches the database
    # (issue #100), and must not be caught by the fake connection below,
    # which is shaped only for run_candidate_search's own seeding read.
    state = _state_at_analysis()

    monkeypatch.setattr(solver_module.designs_db, "get_connection", lambda: _FakeConn())
    monkeypatch.setattr(
        solver_module.designs_db,
        "read_engineering_results_for_scoring",
        lambda conn, design_id, tool_names: {name: [] for name in tool_names},
    )

    target = _exact_frequency_target(_BASE_CANDIDATE)
    result = run_candidate_search(
        state, [_BASE_CANDIDATE], {"analysis": {"target": target}}, design_id=42
    )

    assert result["prior_best_score"] is None
    assert result["prior_iteration"] is None


def test_design_id_reports_the_best_prior_score_and_its_recording_ordinal(monkeypatch):
    """Three canned prior ANALYSIS rows for design_id=99, closest-to-target
    in the MIDDLE -- proves both that the correct one is picked (not just
    the first or the last) and that prior_iteration is that row's own
    1-based position among this design's recorded rows for the step, not
    its database id."""
    # _state_at_analysis() built first, and unpatched -- see the identical
    # note earlier in this Group 6 block; its bootstrap now legitimately
    # touches the database (issue #100) and must not be caught by the fake
    # connection below.
    state = _state_at_analysis()

    target = propose_target(value=2.45e9, comparator="EQUALS", unit="Hz", tolerance=5e7)
    prior_rows = [
        {"id": 101, "value": {"resonant_frequency_hz": 2.20e9}, "created_at": "2026-01-01"},
        {"id": 102, "value": {"resonant_frequency_hz": 2.451e9}, "created_at": "2026-01-02"},
        {"id": 103, "value": {"resonant_frequency_hz": 2.10e9}, "created_at": "2026-01-03"},
    ]
    monkeypatch.setattr(solver_module.designs_db, "get_connection", lambda: _FakeConn())
    monkeypatch.setattr(
        solver_module.designs_db,
        "read_engineering_results_for_scoring",
        lambda conn, design_id, tool_names: {"patch_resonant_frequency_hz": prior_rows},
    )

    from designs.success_score import success_score

    expected_score_percent = success_score(
        step="analysis", target=target, actual_value=2.451e9, actual_unit="Hz"
    )["score_percent"]

    result = run_candidate_search(
        state, [_BASE_CANDIDATE], {"analysis": {"target": target}}, design_id=99
    )

    assert result["prior_best_score"] == pytest.approx(expected_score_percent)
    assert result["prior_iteration"] == 2


def test_design_id_seed_shortens_the_plateau_window(tmp_path, monkeypatch):
    """Mirrors test_score_plateau_stops_after_the_window's own unreachable-
    target/identical-candidate setup exactly, but seeds one prior recorded
    ANALYSIS row scoring identically to every new candidate here -- so the
    plateau-window list starts with 1 entry already in it (the seed)
    instead of 0. plateau_window=3 needs 4 entries to compare; with the
    seed occupying one, only 3 NEW candidates are needed (candidates_
    evaluated == 3) where the unseeded sibling test needs 4 -- the seed
    genuinely shortens the search, not just changes its reported numbers.
    """
    state = _state_at_analysis()
    fake_nec2pp = _make_fake_nec2pp(tmp_path)
    same_candidate = _full_candidate(tmp_path, fake_nec2pp)
    # Unreachable target, matching test_score_plateau_stops_after_the_window
    # -- isolates plateau detection from target_satisfaction.
    target = propose_target(value=1.0e9, comparator="EQUALS", unit="Hz", tolerance=1.0)

    seed_frequency_hz = patch_resonant_frequency_hz(
        same_candidate["eps_r"], same_candidate["w_m"], same_candidate["h_m"], same_candidate["l_m"]
    )
    # NOTE: unlike its sibling seeding tests, this one is the only one that
    # both seeds from a fake AND needs its candidates to really evaluate --
    # so `get_connection` is deliberately NOT faked here. `designs.db` is one
    # module object shared by orchestration/solver.py and orchestration/
    # tooling.py (both `import designs.db as designs_db`), so faking
    # `get_connection` on it is global: it would also intercept the real read
    # that driving each candidate now performs, via advance_design_loop_step
    # -> _fresh_requirements -> read_design (issue #100), which calls
    # .cursor() on the connection. _FakeConn has no .cursor, so every
    # candidate would fail at ANALYSIS, score None, never reach
    # best_so_far.append(), and the plateau could never fire -- the search
    # would run the full budget and stop with "evaluation_budget".
    #
    # Faking only the read below is sufficient and safe: _prior_best_from_
    # design does nothing with the connection except hand it to this function
    # (which ignores it) and close it, so a real connection serves the seed
    # path unchanged while leaving candidate driving its real database.
    monkeypatch.setattr(
        solver_module.designs_db,
        "read_engineering_results_for_scoring",
        lambda conn, design_id, tool_names: {
            "patch_resonant_frequency_hz": [
                {"id": 1, "value": {"resonant_frequency_hz": seed_frequency_hz}, "created_at": "x"}
            ]
        },
    )

    candidates = [same_candidate] * 6
    result = run_candidate_search(
        state,
        candidates,
        {"analysis": {"target": target}},
        plateau_window=3,
        plateau_epsilon=0.5,
        design_id=7,
    )

    assert result["prior_best_score"] is not None
    assert result["prior_iteration"] == 1
    assert result["stop_reason"] == "score_plateau"
    assert result["candidates_evaluated"] == 3


def test_design_id_pairs_two_scoreable_steps_by_matching_ordinal(monkeypatch):
    """_prior_best_from_design's most assumption-laden step, exercised for
    real: TWO scoreable steps (analysis + simulation), each with its own
    two prior rows. Ordinal 1 pairs a 90%-analysis row with a 50%-
    simulation row -> worst_of_scored_steps overall 50%; ordinal 2 pairs a
    60%-analysis row with a 95%-simulation row -> overall 60%. The
    correctly-paired winner is ordinal 2 (60% > 50%). A function that
    mismatched the pairing -- e.g. zipped analysis's Nth row against
    simulation's (len-1-N)th, or combined each step's own INDIVIDUAL best
    rather than same-ordinal rows -- would instead surface ordinal 1's
    cross-combination (90% analysis & 95% simulation -> 90%), a different
    prior_best_score/prior_iteration this test would catch.
    """
    # _state_at_analysis() built first, and unpatched -- see the identical
    # note earlier in this Group 6 block; its bootstrap now legitimately
    # touches the database (issue #100) and must not be caught by the fake
    # connection below.
    state = _state_at_analysis()

    analysis_target = propose_target(value=2.45e9, comparator="EQUALS", unit="Hz", tolerance=5e7)
    simulation_target = propose_target(value=8.0, comparator="EQUALS", unit="dBi", tolerance=2.0)

    analysis_rows = [
        {"id": 201, "value": {"resonant_frequency_hz": 2.455e9}, "created_at": "2026-01-01"},  # 90%
        {"id": 202, "value": {"resonant_frequency_hz": 2.43e9}, "created_at": "2026-01-02"},  # 60%
    ]
    simulation_rows = [
        {"id": 301, "value": {"gain_dbi": 7.0}, "created_at": "2026-01-01"},  # 50%
        {"id": 302, "value": {"gain_dbi": 8.1}, "created_at": "2026-01-02"},  # 95%
    ]
    monkeypatch.setattr(solver_module.designs_db, "get_connection", lambda: _FakeConn())
    monkeypatch.setattr(
        solver_module.designs_db,
        "read_engineering_results_for_scoring",
        lambda conn, design_id, tool_names: {
            "patch_resonant_frequency_hz": analysis_rows,
            "run_nec2_simulation": simulation_rows,
        },
    )

    from designs.success_score import success_score

    def _overall_at(analysis_hz: float, gain_dbi: float) -> float:
        a = success_score(
            step="analysis", target=analysis_target, actual_value=analysis_hz, actual_unit="Hz"
        )["score_percent"]
        s = success_score(
            step="simulation", target=simulation_target, actual_value=gain_dbi, actual_unit="dBi"
        )["score_percent"]
        return min(a, s)

    ordinal1_overall = _overall_at(2.455e9, 7.0)
    ordinal2_overall = _overall_at(2.43e9, 8.1)
    mismatched_cross_overall = _overall_at(2.455e9, 8.1)  # what a wrong pairing would surface
    # Sanity check on the test's own setup: the correct pairing (ordinal 2)
    # must differ from what a wrong, cross-ordinal pairing would produce --
    # otherwise this test could pass even with a pairing bug.
    assert ordinal2_overall != mismatched_cross_overall

    result = run_candidate_search(
        state,
        [_BASE_CANDIDATE],
        {"analysis": {"target": analysis_target}, "simulation": {"target": simulation_target}},
        design_id=55,
    )

    assert result["prior_best_score"] == pytest.approx(ordinal2_overall)
    assert result["prior_best_score"] == pytest.approx(max(ordinal1_overall, ordinal2_overall))
    assert result["prior_iteration"] == 2


def test_design_id_skips_an_ordinal_when_only_one_step_scores_there(monkeypatch):
    """Three prior rows per step; the MIDDLE ordinal (2, 1-based) has an
    unscoreable analysis row (empty `value` -- no `resonant_frequency_hz`
    at all) paired with a very-high-scoring simulation row at that SAME
    ordinal -- exercising _prior_best_from_design's skip-this-ordinal
    branch (`if any(entry["score"] is None ...): continue`). If that
    branch were removed and the missing analysis score just silently
    dropped out of the worst_of_scored_steps computation instead (leaving
    a partial, simulation-only "worst"), ordinal 2's ~99% simulation-only
    score would wrongly win; correctly skipped, ordinal 3's fully-paired
    80%/80% (overall 80%) wins instead.
    """
    # _state_at_analysis() built first, and unpatched -- see the identical
    # note earlier in this Group 6 block; its bootstrap now legitimately
    # touches the database (issue #100) and must not be caught by the fake
    # connection below.
    state = _state_at_analysis()

    analysis_target = propose_target(value=2.45e9, comparator="EQUALS", unit="Hz", tolerance=5e7)
    simulation_target = propose_target(value=8.0, comparator="EQUALS", unit="dBi", tolerance=2.0)

    analysis_rows = [
        {"id": 401, "value": {"resonant_frequency_hz": 2.465e9}, "created_at": "d1"},  # 70%
        {"id": 402, "value": {}, "created_at": "d2"},  # missing field -> unscoreable
        {"id": 403, "value": {"resonant_frequency_hz": 2.46e9}, "created_at": "d3"},  # 80%
    ]
    simulation_rows = [
        {"id": 501, "value": {"gain_dbi": 8.6}, "created_at": "d1"},  # 70%
        {"id": 502, "value": {"gain_dbi": 8.02}, "created_at": "d2"},  # ~99%
        {"id": 503, "value": {"gain_dbi": 8.4}, "created_at": "d3"},  # 80%
    ]
    monkeypatch.setattr(solver_module.designs_db, "get_connection", lambda: _FakeConn())
    monkeypatch.setattr(
        solver_module.designs_db,
        "read_engineering_results_for_scoring",
        lambda conn, design_id, tool_names: {
            "patch_resonant_frequency_hz": analysis_rows,
            "run_nec2_simulation": simulation_rows,
        },
    )

    from designs.success_score import success_score

    ordinal1_overall = min(
        success_score(
            step="analysis", target=analysis_target, actual_value=2.465e9, actual_unit="Hz"
        )["score_percent"],
        success_score(
            step="simulation", target=simulation_target, actual_value=8.6, actual_unit="dBi"
        )["score_percent"],
    )
    ordinal2_simulation_only = success_score(
        step="simulation", target=simulation_target, actual_value=8.02, actual_unit="dBi"
    )["score_percent"]
    ordinal3_overall = min(
        success_score(
            step="analysis", target=analysis_target, actual_value=2.46e9, actual_unit="Hz"
        )["score_percent"],
        success_score(
            step="simulation", target=simulation_target, actual_value=8.4, actual_unit="dBi"
        )["score_percent"],
    )
    # Sanity check on the test's own setup: the skipped ordinal's
    # simulation-only score must be the highest of the three, or a broken
    # skip branch could accidentally still land on the right answer.
    assert ordinal2_simulation_only > ordinal3_overall > ordinal1_overall

    result = run_candidate_search(
        state,
        [_BASE_CANDIDATE],
        {"analysis": {"target": analysis_target}, "simulation": {"target": simulation_target}},
        design_id=56,
    )

    assert result["prior_best_score"] == pytest.approx(ordinal3_overall)
    assert result["prior_iteration"] == 3
