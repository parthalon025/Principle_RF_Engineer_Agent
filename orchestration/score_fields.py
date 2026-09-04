"""The single source of truth for which raw result field a scoreable
design-loop step's numeric value lives at, and in what unit (issue #102).

WHY THIS EXISTS AS ITS OWN MODULE, NOT FOLDED INTO EITHER CONSUMER. Two
siblings in this package need the identical fact -- "ANALYSIS's
`resonant_frequency_hz` is Hz; SIMULATION's `gain_dbi` is dBi;
OPTIMIZATION's `achieved_frequency_hz` is Hz" -- for two different
purposes: `orchestration/solver.py` needs one `(result_field, unit)` pair
PER STEP, to know which key of that step's raw result dict is the number
being scored against a caller-stated target (its own docstring's
"SCORING" section). `orchestration/lab_test_plan.py` needs the SAME
triples grouped by PHYSICAL QUANTITY KIND (FREQUENCY, GAIN, ...), to trace
a pre-trip prediction back to the most-refined this-iteration decision of
a matching kind and unit (its own docstring's "DESIGN QUESTION 2"). Before
this ticket, each module wrote its own copy of the three triples down
independently -- #94 and #95 were implemented in parallel by different
agents, each of which needed this same wiring knowledge and each of which
wrote it down, with neither module's docstring acknowledging the other's
copy. That was a silent-staleness risk with no structural guard: renaming
a result field in one copy would leave the other matching its own tests
while quietly looking for a field the design loop no longer produces (see
issue #102's own body for the exact failure mode -- a lab test plan
reporting "no engineering result this iteration" for a requirement the
solver had, moments earlier, scored successfully). This module is now the
ONE place that fact is written down; `orchestration/solver.py` and
`orchestration/lab_test_plan.py` each build their own lookup SHAPE
(a flat per-step dict, and a per-quantity-kind grouped dict, respectively)
from `SCORE_FIELD_SOURCES` below, at import time, rather than restating
the literals -- see tests/test_score_fields.py for the direct proof both
derived lookups stay in lockstep with this table.

WHY NOT MERGE THIS INTO `orchestration/tooling.py`'s `_STEP_TO_TOOL_NAME`.
That table answers a different question: which real FUNCTION produced a
step's result (`patch_resonant_frequency_hz`, `run_nec2_simulation`, ...),
for `engineering_results.tool_name` provenance bookkeeping -- a fact about
WHICH TOOL RAN. This table answers which FIELD of that already-produced
result dict carries the scoreable number, and what UNIT it is in -- a
fact about the RESULT'S SHAPE, never about which tool produced it. The two
tables happen to share the same `DesignStep` keys (ANALYSIS/SIMULATION/
OPTIMIZATION overlap `_STEP_TO_TOOL_NAME`'s own five entries), because the
same three steps are both scoreable and tool-attributed, but conflating
them would mean a caller who only needs "what unit is `gain_dbi` in" also
has to carry `run_nec2_simulation`'s literal function name alongside it,
and vice versa -- two independent facts collapsed into one table for no
shared reason. Keeping them separate mirrors this codebase's own existing
precedent of one small, closed table per fact (`_STEP_TO_TOOL_NAME`,
`_REQUIRED_FIELDS`, `_TOUCHSTONE_UNIT_KINDS`, ...), not one growing table
that answers several unrelated questions.

NOT A GENERAL "PHYSICAL QUANTITY" OR "UNIT SYSTEM" MODULE. This is
narrowly the wiring between THIS loop's own step handlers
(`orchestration/design_loop.py`) and THIS loop's own currently-implemented
Phase 1/6/9 functions (`rf_tools/calculations.py`, `simulation/nec2pp.py`,
`optimization/rf_objectives.py`) -- mechanical fact about their already-
documented output shapes, not an RF judgment call and not a reusable units
library. A step with no entry here (REQUIREMENTS, ARCHITECTURE,
VERIFICATION, MEASUREMENT, CORRELATION, REDESIGN_DECISION) simply has no
row: none of those steps produces a single scoreable numeric scalar the
way ANALYSIS/SIMULATION/OPTIMIZATION do, so there is no fact to record for
them here.
"""

from __future__ import annotations

from typing import NamedTuple

from .design_loop import DesignStep


class ScoreFieldSource(NamedTuple):
    """One `(step, result_field, unit)` fact: `step`'s raw result dict
    carries its scoreable numeric value at key `result_field`, expressed in
    `unit`. A plain `NamedTuple` (not a heavier dataclass) so it unpacks
    exactly like the bare 3-tuples both consumers used to spell out by
    hand -- `for step, field, unit in sources` keeps working unchanged."""

    step: DesignStep
    result_field: str
    unit: str


# The one place these three triples are written down -- see this module's
# docstring. `orchestration/solver.py` and `orchestration/lab_test_plan.py`
# each derive their own lookup shape from this tuple; neither restates the
# literals. Order is not semantically load-bearing for either consumer
# (solver.py indexes by `step`, a unique key; lab_test_plan.py's own
# `_find_expected` already documents that list order within one quantity
# kind doesn't matter, since the LAST matching decision wins regardless).
SCORE_FIELD_SOURCES: tuple[ScoreFieldSource, ...] = (
    ScoreFieldSource(DesignStep.ANALYSIS, "resonant_frequency_hz", "Hz"),
    ScoreFieldSource(DesignStep.SIMULATION, "gain_dbi", "dBi"),
    ScoreFieldSource(DesignStep.OPTIMIZATION, "achieved_frequency_hz", "Hz"),
)
