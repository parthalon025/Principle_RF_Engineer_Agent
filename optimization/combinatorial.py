"""Combinatorial symbol-placement search over a caller-supplied,
pre-characterised symbol set (issue #255): the OPTIMIZATION-step search a
Tier B design family (`REFLECTION_PHASE`, `DIFFUSIVE` -- CONTEXT.md's own
`optimizer_class == "COMBINATORIAL"` families) needs, and that nothing in
this package provided before this module.

WHAT PROBLEM THIS SOLVES, AND WHAT IT DOES NOT: a Tier B family's tile-level
solve measures how one candidate shape ("symbol") reflects a wave; turning
"steer the beam this far" or "scatter this return" into a required
per-position value is a separate, upstream calculation (out of this
module's scope -- see issue #255's Out of Scope). What THIS module does is
the placement/selection problem that comes after that target exists: given
that per-position target and a resolved set of already-characterised
candidate symbols per grid position, decide which symbol goes where to get
as close to target as possible, without ever exceeding the alphabet's own
Delta_phi_max unlike-neighbour phase-coupling budget (CONTEXT.md:
`Delta_phi_max`) that `geometry.unit_cell.block_size_from_sizing_rule`
already derives elsewhere in this project from the same requirement.

THIS MODULE STILL NEVER FETCHES CANDIDATE SYMBOLS ITSELF (issue #256):
`candidates` is a plain argument the caller supplies -- in production,
`orchestration.design_loop._optimize_combinatorial_symbol_placement`/
`_combinatorial_candidate_options` is that caller, resolving it via
`designs.element_alphabet.lookup_symbol_entries` against the real,
persistent Element/Coding-Alphabet library (CONTEXT.md: Element/
Coding-Alphabet library; `symbol_alphabet_entries`/`process_records`,
db/schema.sql) that issue #256 has since built -- ADR-0027 is explicit that
only a PRINTED AND MEASURED shape is a letter. Every test in
tests/test_optimization.py's own combinatorial section supplies its own
small, hand-built FAKE `candidates` dict instead, for exactly the same
"caller fetches, this function only resolves" seam
`designs.material_properties.resolve_material_property` and
`geometry.unit_cell.generate_coded_unit_cell_array`'s own `symbol_library`
argument already use for their own accumulate-once-and-reuse libraries --
this module remains fully buildable and testable without a live alphabet
lookup on hand, but no longer because none exists in this tree. A placement
this module returns is only as real as the `candidates` it was given; a
caller-supplied option built from a hand-picked or fictitious symbol (not a
real alphabet-library lookup) is still, by this project's own admission
rule, not a letter at all (see this module's docstring; nothing here
loosens that).

HOW THE SEARCH WORKS: each grid position's symbol choice is encoded as an
ORDINAL INTEGER INDEX into that position's own resolved candidate list (an
`optimization/base.py`-style integer `Parameter`, bounded `0` to
`len(candidates_at_this_position) - 1`), and `optimization/genetic.py`'s
already-tested `genetic_optimize` (itself a `scipy.optimize.
differential_evolution` wrapper) is reused directly to search that encoded
space -- this module's only genuinely new code is building one integer
Parameter per free position and one decode-then-score objective, per issue
#255's own steer away from hand-rolling a categorical GA. A position with
only ONE candidate carries no search freedom at all (a `Parameter` requires
`upper > lower` -- see `optimization/base.py`) and is held fixed instead of
being given to `genetic_optimize`, with a `warnings` entry recording that
the search had no choice there (CONTEXT.md/CLAUDE.md's "warn, never block":
a thin candidate shelf is a reason to say so loudly, not a reason to refuse
a result). If EVERY position is pinned this way, there is nothing left for
`genetic_optimize` to search (it requires at least one `Parameter`) and the
single possible placement is built and scored directly, with one entry in
the evaluations trace.

A position with ZERO candidates is a different situation, not a thin
shelf: there is no symbol at all to place there, so no placement can be
built. Mirroring `geometry.unit_cell.SymbolNotFoundError`'s own reasoning
("there is no plausible geometry to substitute ... silently drawing
*something* in its place would misrepresent a hypothesis as a printable
design"), this module raises `EmptyCandidateShelfError` naming every such
position at once, rather than warning past it or crashing on a `KeyError`.

RESPECTING Delta_phi_max: every evaluated placement is scored for its raw
error against target AND checked for feasibility -- no pair of 4-connected
grid neighbours (one shared edge; CONTEXT.md's own "unlike-neighbour"
notion) may differ by more than `delta_phi_max_deg`. An infeasible
placement is never returned as the winner, even when its raw error is
lower than every feasible placement's (issue #255 User Story 7 /
Testing Decisions) -- enforced by adding a large, fixed penalty to an
infeasible placement's objective value before `genetic_optimize`'s own
`best_of` picks the minimum, so feasibility always dominates raw error in
the ordering. Every evaluated placement -- feasible or not -- still appears
in `CombinatorialPlacementResult.evaluations`, tagged with its own
(unpenalised) raw error and its `feasible` flag: the full search trace,
not just the winner, mirrors every other method in this package
(`optimization/base.py`'s `OptimizationResult.evaluations`).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from optimization.base import Parameter
from optimization.genetic import genetic_optimize

# One grid position, matching `geometry.unit_cell.generate_coded_unit_cell_
# array`'s own `(i, j)` naming: `i` is the column (x) index, `j` is the row
# (y) index -- `layout[j][i]` names the symbol at position `(i, j)`.
Position = tuple[int, int]

# A placement judged infeasible (violates delta_phi_max_deg somewhere) is
# always penalised past this constant before feasible placements are ever
# scored -- see module docstring's "RESPECTING Delta_phi_max". Every target/
# achieved value in this project's actual use (a reflection phase in
# degrees) is bounded well below this, so the ordering guarantee holds for
# any physically plausible input.
_INFEASIBLE_PENALTY = 1.0e6

# Floating-point slack when comparing a neighbour phase gap against
# delta_phi_max_deg, so a gap that is exactly at budget is not flagged
# infeasible by rounding noise alone.
_FEASIBILITY_TOL = 1.0e-9


@dataclass(frozen=True)
class SymbolOption:
    """One candidate symbol available at a grid position: just enough to
    score and place it in this module's own search, without pulling in the
    real Element/Coding-Alphabet library this ticket does not have (see
    module docstring).

    `symbol_id`: the id this candidate is placed under -- a key that, once
    resolved against a real `symbol_library`, `geometry.unit_cell.
    generate_coded_unit_cell_array` can turn into actual unit-cell geometry.
    `achieved_value`: this symbol's own measured (or, in a test, hand-built
    fake) response at this position -- whatever quantity the per-position
    `target` array is stated in (e.g. an achieved reflection phase in
    degrees). Generic on purpose: this module never assumes the quantity is
    phase specifically, only that lower `abs(achieved_value - target)` is
    better and that `delta_phi_max_deg` bounds how far apart two
    neighbours' `achieved_value`s may be.
    `entry_id`: the matched `symbol_alphabet_entries.id` (db/schema.sql)
    this candidate resolved from, when a real caller resolved it against
    the Element/Coding-Alphabet library (issue #400) --
    `orchestration.design_loop._combinatorial_candidate_options` is that
    caller in production, populating this from the matched row's own `id`.
    `None` is the honest default for a hand-built option (every fixture in
    this module's own tests) with no backing database row to point at.
    `symbol_id` ALONE cannot disambiguate between several measured entries
    sharing the same family/symbol/band/incidence-angle-range/process --
    ADR-0027 point 4's own worked example is exactly this: "two runs on
    nominally identical settings are still two distinct,
    independently-referenceable letters," never merged. `entry_id` is what
    lets a later reader answer "which measured process (machine/ink/cure)
    backed this exact cell", not merely "which symbol".
    """

    symbol_id: str
    achieved_value: float
    entry_id: int | None = None


class EmptyCandidateShelfError(ValueError):
    """Raised by `combinatorial_symbol_placement` when one or more grid
    positions have ZERO candidate symbols to choose from -- either an empty
    list, or the position missing from `candidates` entirely (the same
    "nothing available here" situation either way).

    Named and raised the same way this repo's other "there is nothing
    correct to substitute" cases are
    (`geometry.unit_cell.SymbolNotFoundError`): a `ValueError` subclass
    naming exactly which positions have no candidate, all together rather
    than one at a time.

    Deliberately a hard error, not a warning -- unlike a THIN shelf (one
    candidate, still placeable, only lacking choice; see this module's
    `warnings` field), a position with zero candidates has no symbol at all
    to place there. Silently skipping it, or filling it with a placeholder,
    would produce a `layout` that is not actually a complete, printable
    placement -- the same reasoning `SymbolNotFoundError` already gives for
    refusing rather than guessing past a missing symbol.
    """


@dataclass
class CombinatorialPlacementResult:
    """Shared result shape for `combinatorial_symbol_placement`, mirroring
    `optimization.base.OptimizationResult`'s own "method name, best result,
    full trace, self-describing metadata" shape (issue #255 Implementation
    Decisions) closely enough that a caller already familiar with
    `genetic_optimize`'s return shape recognises this one, even though the
    search space here is categorical (which symbol goes where) rather than
    a box-bounded real vector.

    - `method`: always `"combinatorial_symbol_placement"`.
    - `layout`: the winning symbol-id grid, `layout[j][i]` naming the
      symbol at block position `(i, j)` -- EXACTLY
      `geometry.unit_cell.generate_coded_unit_cell_array`'s own `layout`
      argument shape, so it plugs directly into that function with no
      reshaping step in between (issue #255 User Story 16).
    - `entry_id_layout`: the SAME `[j][i]` grid, but each cell holds the
      winning `SymbolOption.entry_id` placed there instead of its
      `symbol_id` (issue #400) -- `None` at a cell whose winning option
      never carried a real `entry_id` (a hand-built test fixture). This is
      what lets a later query answer "which specific measured
      `symbol_alphabet_entries` row -- and therefore which process/
      machine/ink -- backed cell (i, j)", which `layout` alone cannot: two
      entries can share a `symbol_id` (ADR-0027 point 4). Defaults to
      `None` (not computed) rather than a same-shaped grid of `None`s, so a
      caller building a `CombinatorialPlacementResult` directly (this
      module's own tests' `test_combinatorial_result_to_dict_orders_
      candidate_snapshot_row_major`-style fakes) is not forced to supply
      it just to exercise an unrelated field.
    - `achieved_error`: the winning placement's own raw (unpenalised) error
      against `target` -- see `_placement_error` for exactly what this
      aggregates.
    - `evaluations`: EVERY placement actually evaluated, in evaluation
      order, each as `{"layout": [[...]], "error": float, "feasible":
      bool}` -- the full search trace (issue #255 User Story 8), not just
      the winner.
    - `target`: a snapshot of the per-position target grid this result was
      searched against, `target[j][i]`.
    - `candidate_snapshot`: a snapshot of the resolved candidate-symbol set
      this result searched over, `{(i, j): [SymbolOption, ...]}` -- a copy,
      not a live reference to the caller's own `candidates` dict, so later
      mutating the caller's dict never changes what this result already
      recorded (issue #255 User Story 18: "calculated from *what*").
    - `delta_phi_max_deg`, `random_seed`: the budget and seed this result
      was produced with, recorded for the same reproducibility/provenance
      reasons `OptimizationResult` records its own inputs.
    - `warnings`: human-readable notes on anything load-bearing this result
      assumed -- a thin (one-candidate) shelf at some position, or (if
      every combination available is infeasible) that even the winning
      placement exceeds `delta_phi_max_deg` -- this project's "warn, never
      block" convention (CLAUDE.md), matching the plain `warnings: list[str]`
      shape `simulation/conservation_checks.py` and
      `simulation/kicad_gerber2ems.py` already use for the same purpose.
    - `objective_name`: as `OptimizationResult.objective_name` -- a
      human-readable name for what this placement was optimizing, if the
      caller gave one.
    - `provenance`: `"CALCULATED"` -- see `optimization/base.py`'s module
      docstring for why every method in this package uses this, not
      `"SIMULATED"`: the search procedure is a deterministic
      (seeded-deterministic, given `random_seed`) numerical search over
      whatever symbol responses `candidates` supplied, exactly the
      reasoning that docstring gives for every other optimizer here.
    """

    method: str
    layout: list[list[str]]
    achieved_error: float
    evaluations: list[dict[str, Any]]
    target: list[list[float]]
    candidate_snapshot: dict[Position, list[SymbolOption]]
    delta_phi_max_deg: float
    random_seed: int | None
    entry_id_layout: list[list[int | None]] | None = None
    warnings: list[str] = field(default_factory=list)
    objective_name: str | None = None
    provenance: str = "CALCULATED"


def _validate_target(target: list[list[float]]) -> tuple[int, int]:
    """Validate `target` is a non-empty, rectangular 2D grid and return its
    `(n_cols, n_rows)` -- the same "non-empty, non-ragged" check
    `generate_coded_unit_cell_array` already applies to its own `layout`
    argument, applied here to the target grid this module's `layout` output
    must match the shape of."""
    if not target or not target[0]:
        raise ValueError("target must be a non-empty, non-ragged 2D grid of target values")
    n_rows = len(target)
    n_cols = len(target[0])
    if any(len(row) != n_cols for row in target):
        raise ValueError(
            f"target must be rectangular: row lengths were {[len(row) for row in target]}"
        )
    return n_cols, n_rows


def _placement_error(
    achieved: dict[Position, float], target: list[list[float]], n_cols: int, n_rows: int
) -> float:
    """Mean absolute error between `achieved` (one value per position) and
    `target[j][i]`, across every grid position -- the "how close is this
    placement to what was asked for" quantity `CombinatorialPlacementResult.
    achieved_error` and each trace entry's `"error"` report. Mean absolute
    error (not squared) is used because `achieved_value`/`target` are
    physically-meaningful units (e.g. degrees of phase); this keeps the
    reported error in that same unit."""
    total = sum(abs(achieved[(i, j)] - target[j][i]) for j in range(n_rows) for i in range(n_cols))
    return total / (n_cols * n_rows)


def _neighbour_violation(
    achieved: dict[Position, float], delta_phi_max_deg: float, n_cols: int, n_rows: int
) -> float:
    """Total amount by which this placement's 4-connected neighbour pairs
    exceed `delta_phi_max_deg` -- `0.0` exactly when every such pair is
    within budget (feasible). Only the two neighbour directions that don't
    double-count a pair (right, down) are walked; CONTEXT.md's
    `Delta_phi_max` entry defines the budget over the unlike-neighbour
    relationship itself, which is symmetric."""
    violation = 0.0
    for j in range(n_rows):
        for i in range(n_cols):
            here = achieved[(i, j)]
            if i + 1 < n_cols:
                gap = abs(here - achieved[(i + 1, j)])
                if gap > delta_phi_max_deg + _FEASIBILITY_TOL:
                    violation += gap - delta_phi_max_deg
            if j + 1 < n_rows:
                gap = abs(here - achieved[(i, j + 1)])
                if gap > delta_phi_max_deg + _FEASIBILITY_TOL:
                    violation += gap - delta_phi_max_deg
    return violation


def _layout_from_choices(
    choices: dict[Position, SymbolOption], n_cols: int, n_rows: int
) -> list[list[str]]:
    """Build a `layout[j][i]` grid of symbol ids from a resolved
    per-position `SymbolOption` choice -- exactly
    `generate_coded_unit_cell_array`'s own `layout` shape."""
    return [[choices[(i, j)].symbol_id for i in range(n_cols)] for j in range(n_rows)]


def _entry_id_layout_from_choices(
    choices: dict[Position, SymbolOption], n_cols: int, n_rows: int
) -> list[list[int | None]]:
    """The SAME `[j][i]` grid `_layout_from_choices` builds, but each cell
    holds the winning `SymbolOption.entry_id` instead of its `symbol_id`
    (issue #400) -- `CombinatorialPlacementResult.entry_id_layout`'s own
    docstring explains why a bare symbol id cannot answer "which measured
    process backed this cell" on its own."""
    return [[choices[(i, j)].entry_id for i in range(n_cols)] for j in range(n_rows)]


def combinatorial_symbol_placement(
    target: list[list[float]],
    candidates: dict[Position, list[SymbolOption]],
    delta_phi_max_deg: float,
    random_seed: int | None = None,
    max_generations: int = 100,
    population_size: int = 15,
    objective_name: str | None = None,
) -> CombinatorialPlacementResult:
    """Search for the assignment of candidate symbols to grid positions that
    comes closest to `target`, without ever placing two 4-connected
    neighbours more than `delta_phi_max_deg` apart -- the combinatorial
    OPTIMIZATION-step search issue #255 adds for Tier B
    (`optimizer_class == "COMBINATORIAL"`) design families. See this
    module's own docstring for the full design (why `genetic_optimize`'s
    `differential_evolution` wrapper is reused via ordinal-integer encoding,
    how a thin vs. an empty candidate shelf are each handled, and how
    `delta_phi_max_deg` is enforced).

    `target`: the required per-position value, `target[j][i]` -- row `j`
    (outer list), column `i` (inner list), the SAME axis convention
    `generate_coded_unit_cell_array`'s own `layout` uses. Must be
    non-empty and rectangular.

    `candidates`: the caller-resolved set of available symbols per
    position, `{(i, j): [SymbolOption, ...]}` -- see module docstring for
    why this is never fetched by this module itself. A position named in
    `target`'s implied grid (every `(i, j)` for `i` in `range(n_cols)`,
    `j` in `range(n_rows)`) that is missing from `candidates`, or maps to
    an empty list, raises `EmptyCandidateShelfError` naming every such
    position. A position with exactly one candidate is held fixed (no
    search freedom there) and recorded in `warnings`.

    `delta_phi_max_deg`: the unlike-neighbour phase-coupling budget
    (CONTEXT.md: `Delta_phi_max`) no placement may exceed and still be
    returned as the winner -- see module docstring's "RESPECTING
    Delta_phi_max". Must be a positive, finite number.

    `random_seed`: forwarded to `genetic_optimize`'s own `random_seed` --
    the identical seed reproduces the identical `layout` and evaluation
    trace on a repeat call with the same inputs (issue #255 User Story 10).

    `max_generations`, `population_size`: forwarded to `genetic_optimize`
    unchanged (see that function's own docstring) when there is at least
    one free (multi-candidate) position to search; unused when every
    position is pinned by a thin shelf (see module docstring).

    `objective_name`: recorded on the result, as
    `OptimizationResult.objective_name` already is for every other method
    in this package.

    Returns a `CombinatorialPlacementResult` -- see that dataclass's own
    docstring for its full shape.

    Raises `ValueError` if `target` is empty or ragged, or if
    `delta_phi_max_deg` is not a positive finite number, and
    `EmptyCandidateShelfError` (a `ValueError` subclass) if any grid
    position has no candidate symbol at all.
    """
    n_cols, n_rows = _validate_target(target)
    if (
        not isinstance(delta_phi_max_deg, (int, float))
        or isinstance(delta_phi_max_deg, bool)
        or delta_phi_max_deg <= 0
        or delta_phi_max_deg != delta_phi_max_deg  # NaN check without importing math
    ):
        raise ValueError(
            f"delta_phi_max_deg must be a positive, finite number, got {delta_phi_max_deg!r}"
        )

    positions = [(i, j) for j in range(n_rows) for i in range(n_cols)]

    empty = sorted(pos for pos in positions if len(candidates.get(pos, [])) == 0)
    if empty:
        raise EmptyCandidateShelfError(
            f"position(s) {empty} have zero candidate symbols to search over. "
            "A grid position with no characterised symbol available cannot be "
            "placed -- this is a gap to go resolve (characterise a symbol for "
            "this family/band/process/incidence-angle range in the Element/"
            "Coding-Alphabet library, or narrow the requirement), not something "
            "to silently skip or fill with a placeholder."
        )

    candidate_snapshot: dict[Position, list[SymbolOption]] = {
        pos: list(candidates[pos]) for pos in positions
    }

    warnings: list[str] = []
    fixed_choices: dict[Position, SymbolOption] = {}
    free_positions: list[Position] = []
    for pos in positions:
        options = candidate_snapshot[pos]
        if len(options) == 1:
            fixed_choices[pos] = options[0]
            i, j = pos
            warnings.append(
                f"position (i={i}, j={j}) has only one candidate symbol "
                f"({options[0].symbol_id!r}); the search had no choice there."
            )
        else:
            free_positions.append(pos)

    def _score(choices: dict[Position, SymbolOption]) -> tuple[float, bool]:
        achieved = {pos: choices[pos].achieved_value for pos in positions}
        raw_error = _placement_error(achieved, target, n_cols, n_rows)
        violation = _neighbour_violation(achieved, delta_phi_max_deg, n_cols, n_rows)
        feasible = violation == 0.0
        return raw_error, feasible

    if not free_positions:
        # Every position pinned by a thin (one-candidate) shelf: nothing
        # left for genetic_optimize to search (it requires >= 1 Parameter --
        # see optimization/base.py's validate_parameters). Build and score
        # the single possible placement directly.
        raw_error, feasible = _score(fixed_choices)
        layout = _layout_from_choices(fixed_choices, n_cols, n_rows)
        entry_id_layout = _entry_id_layout_from_choices(fixed_choices, n_cols, n_rows)
        evaluations = [{"layout": layout, "error": raw_error, "feasible": feasible}]
        if not feasible:
            warnings.append(
                "no candidate combination was available to search -- every position "
                "was pinned by a thin shelf, and the only possible placement exceeds "
                f"the delta_phi_max_deg={delta_phi_max_deg} budget."
            )
        return CombinatorialPlacementResult(
            method="combinatorial_symbol_placement",
            layout=layout,
            achieved_error=raw_error,
            evaluations=evaluations,
            target=[list(row) for row in target],
            candidate_snapshot=candidate_snapshot,
            delta_phi_max_deg=delta_phi_max_deg,
            random_seed=random_seed,
            entry_id_layout=entry_id_layout,
            warnings=warnings,
            objective_name=objective_name,
        )

    parameters = [
        Parameter(
            name=f"pos_{i}_{j}",
            lower=0,
            upper=len(candidate_snapshot[(i, j)]) - 1,
            param_type="integer",
        )
        for (i, j) in free_positions
    ]

    def _decode(params: dict[str, float]) -> dict[Position, SymbolOption]:
        choices = dict(fixed_choices)
        for i, j in free_positions:
            index = int(round(params[f"pos_{i}_{j}"]))
            choices[(i, j)] = candidate_snapshot[(i, j)][index]
        return choices

    def objective(params: dict[str, float]) -> float:
        choices = _decode(params)
        raw_error, feasible = _score(choices)
        return raw_error if feasible else _INFEASIBLE_PENALTY + raw_error

    ga_result = genetic_optimize(
        objective=objective,
        parameters=parameters,
        max_generations=max_generations,
        population_size=population_size,
        random_seed=random_seed,
        objective_name=objective_name,
        constraints={"delta_phi_max_deg": delta_phi_max_deg},
    )

    evaluations: list[dict[str, Any]] = []
    for raw_eval in ga_result.evaluations:
        choices = _decode(raw_eval["parameters"])
        raw_error, feasible = _score(choices)
        evaluations.append(
            {
                "layout": _layout_from_choices(choices, n_cols, n_rows),
                "error": raw_error,
                "feasible": feasible,
            }
        )

    best_choices = _decode(ga_result.best_parameters)
    best_layout = _layout_from_choices(best_choices, n_cols, n_rows)
    best_entry_id_layout = _entry_id_layout_from_choices(best_choices, n_cols, n_rows)
    best_error, best_feasible = _score(best_choices)

    if not best_feasible:
        warnings.append(
            "no candidate combination satisfies delta_phi_max_deg="
            f"{delta_phi_max_deg}; the best placement found still exceeds it. "
            "This is the closest achievable placement from the candidates "
            "supplied, not a claim that it meets the coupling budget."
        )

    return CombinatorialPlacementResult(
        method="combinatorial_symbol_placement",
        layout=best_layout,
        achieved_error=best_error,
        evaluations=evaluations,
        target=[list(row) for row in target],
        candidate_snapshot=candidate_snapshot,
        delta_phi_max_deg=delta_phi_max_deg,
        random_seed=random_seed,
        entry_id_layout=best_entry_id_layout,
        warnings=warnings,
        objective_name=objective_name,
    )
