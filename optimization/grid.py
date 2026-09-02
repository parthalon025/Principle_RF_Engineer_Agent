"""Grid search: full Cartesian-product grid over ALL parameters (issue #41).

COMPUTATIONAL COST WARNING: grid search is exponential in the number of
parameters -- `n_points_per_dim` values per dimension means
`n_points_per_dim ** len(parameters)` total objective evaluations (e.g. 10
points/dim over 4 parameters is 10,000 evaluations). It is the right choice
for a low-dimensional problem (1-3 free variables) where exhaustive coverage
matters more than evaluation budget, and the wrong choice as dimensionality
grows -- see bayesian_optimize for a method that spends far fewer
evaluations to find a comparably good optimum in that regime (this is
exactly what tests/test_optimization.py's grid-vs-Bayesian comparison
demonstrates).

Implemented as a hand-rolled Cartesian product (itertools.product) over each
parameter's own evenly-spaced grid, rather than scipy.optimize.brute:
brute's own local-refinement step (`finish=`, default `fmin`) adds extra,
uncounted objective evaluations beyond the grid itself, which would make its
evaluation count opaque to exactly the "fewer evaluations than grid search"
comparison this ticket's acceptance criteria requires (see
tests/test_optimization.py); a hand-rolled grid keeps the evaluation count
exactly `n_points_per_dim ** len(parameters)`, and keeps every evaluated
point directly in the shared OptimizationResult.evaluations shape without
having to reshape scipy's returned grid/Jout arrays back into per-parameter
dicts. See optimization/base.py for the shared Parameter/ObjectiveFunction/
OptimizationResult contract and the minimize-by-convention sign rule.
"""

import itertools

import numpy as np

from optimization.base import (
    ObjectiveFunction,
    OptimizationResult,
    Parameter,
    best_of,
    record_evaluation,
    validate_parameters,
)


def grid_search(
    objective: ObjectiveFunction,
    parameters: list[Parameter],
    n_points_per_dim: int = 10,
    objective_name: str | None = None,
    constraints: dict | None = None,
) -> OptimizationResult:
    """Evaluate `objective` over the full Cartesian-product grid of
    `n_points_per_dim` evenly-spaced values per parameter in `parameters`.

    See this module's docstring for the exponential cost warning:
    `n_points_per_dim ** len(parameters)` total evaluations. For an
    "integer" parameter, grid values are rounded to the nearest integer and
    de-duplicated within that one dimension before taking the product, so
    the actual evaluation count may be lower than the worst case when an
    integer range is narrower than `n_points_per_dim`.

    `objective_name` / `constraints` are recorded on the returned
    OptimizationResult for provenance; not enforced by this function --
    grid search only ever samples within each Parameter's own box bounds.

    Returns an OptimizationResult with method="grid_search", `evaluations`
    in grid (row-major Cartesian-product) order, and best_parameters/
    best_objective from the lowest-objective grid point (minimize-by-
    convention -- see optimization/base.py).
    """
    validate_parameters(parameters)
    if n_points_per_dim < 2:
        raise ValueError("n_points_per_dim must be >= 2 (at least the two range endpoints).")

    per_dim_values: list[list[float]] = []
    for p in parameters:
        raw = np.linspace(p.lower, p.upper, n_points_per_dim)
        if p.param_type == "integer":
            values = sorted({p.clip(v) for v in raw})
        else:
            values = [p.clip(v) for v in raw]
        per_dim_values.append(values)

    names = [p.name for p in parameters]
    evaluations: list[dict] = []
    for combo in itertools.product(*per_dim_values):
        point = dict(zip(names, combo, strict=True))
        objective_value = objective(point)
        record_evaluation(evaluations, point, objective_value)

    best_parameters, best_objective = best_of(evaluations)
    return OptimizationResult(
        method="grid_search",
        best_parameters=best_parameters,
        best_objective=best_objective,
        evaluations=evaluations,
        parameters=list(parameters),
        objective_name=objective_name,
        constraints=constraints,
    )
