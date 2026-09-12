"""Tests for orchestration/solver.py's two lookup tables (issue #497/#510).

`orchestration/solver.py` keeps two small tables it must not silently drift
from their real sources -- see that module's own comments above
`_REQUIRED_FIELDS` and `_STEP_TOOL_NAME` for the full story:

  1. `_REQUIRED_FIELDS[SIMULATION]`/`[OPTIMIZATION]` are no longer restated
     literals -- they import `orchestration/design_loop.py`'s own named
     constants `SIMULATE_NEC2_REQUIRED_FIELDS`/
     `OPTIMIZE_CONTINUOUS_PATCH_LENGTH_REQUIRED_FIELDS`, the same field sets
     `_simulate_nec2`/`_optimize_continuous_patch_length`'s own
     `_require_fields(...)` calls use.
  2. `_STEP_TOOL_NAME[OPTIMIZATION]` is a genuine duplicate of a real,
     static fact in `orchestration/tooling.py`'s `_STEP_TO_TOOL_NAME`, so it
     now imports that entry instead of hand-copying it. ANALYSIS/SIMULATION
     stay solver.py's own literals -- there is no static table in
     tooling.py to import them from (tooling.py resolves those two
     dynamically, per family) -- and are NOT checked here for that reason.

Following tests/test_score_fields.py's precedent exactly: reach into the
private module attributes on both sides and assert equality, so a future
edit to either side's real table fails this test immediately and loudly
rather than leaving solver.py's copy silently stale.
"""

from __future__ import annotations

import orchestration.design_loop as design_loop_module
import orchestration.solver as solver_module
import orchestration.tooling as tooling_module
from orchestration.design_loop import DesignStep


def test_solver_simulation_required_fields_matches_design_loop_constant():
    assert (
        solver_module._REQUIRED_FIELDS[DesignStep.SIMULATION]
        == design_loop_module.SIMULATE_NEC2_REQUIRED_FIELDS
    )


def test_solver_optimization_required_fields_matches_design_loop_constant():
    assert (
        solver_module._REQUIRED_FIELDS[DesignStep.OPTIMIZATION]
        == design_loop_module.OPTIMIZE_CONTINUOUS_PATCH_LENGTH_REQUIRED_FIELDS
    )


def test_solver_optimization_tool_name_matches_toolings_real_table():
    assert (
        solver_module._STEP_TOOL_NAME[DesignStep.OPTIMIZATION]
        == tooling_module._STEP_TO_TOOL_NAME[DesignStep.OPTIMIZATION.value]
    )
