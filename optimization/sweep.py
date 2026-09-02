"""Parameter sweep: vary ONE parameter across its range, others held fixed
(issue #41).

The "see how each parameter affects performance" use case: e.g. sweep a
patch antenna's length across its plausible range at a fixed width/
substrate, to see how the objective (e.g. negated resonant-frequency error,
or negated gain) responds to that one variable, all others held at a
baseline. See optimization/base.py for the shared Parameter/
ObjectiveFunction/OptimizationResult contract and the minimize-by-convention
sign rule every method in this package follows.
"""

import numpy as np

from optimization.base import (
    ObjectiveFunction,
    OptimizationResult,
    Parameter,
    best_of,
    default_values,
    record_evaluation,
    validate_parameters,
)


def parameter_sweep(
    objective: ObjectiveFunction,
    parameter: Parameter,
    n_points: int = 20,
    fixed_values: dict[str, float] | None = None,
    other_parameters: list[Parameter] | None = None,
    objective_name: str | None = None,
    constraints: dict | None = None,
) -> OptimizationResult:
    """Evaluate `objective` at `n_points` evenly spaced values of `parameter`
    across its [lower, upper] range, holding every other parameter fixed.

    - `parameter`: the ONE Parameter to vary this sweep.
    - `n_points`: how many evenly-spaced values to sample across
      `parameter`'s range (>= 2; endpoints are always included). For an
      "integer" parameter, values are rounded to the nearest integer and
      de-duplicated, so the actual evaluation count may be less than
      `n_points` for a narrow integer range.
    - `fixed_values`: explicit `{name: value}` overrides for any OTHER
      parameter the objective needs but this sweep is not varying. Any
      parameter named in `other_parameters` but not in `fixed_values` falls
      back to that Parameter's own midpoint (see Parameter.midpoint) --
      this is the "others fixed at a default/midpoint" behavior described in
      the ticket. `fixed_values` may also carry keys `other_parameters`
      doesn't describe as a Parameter at all (e.g. a constant the objective
      needs that isn't itself a free variable being swept in this project) --
      those pass through unchanged.
    - `other_parameters`: the OTHER free variables `objective` expects,
      used only to compute their midpoint default when `fixed_values`
      doesn't already specify a value. Omit if `fixed_values` alone fully
      determines every other input the objective needs (or if `parameter`
      is the objective's only input).
    - `objective_name` / `constraints`: recorded on the returned
      OptimizationResult for provenance; not enforced by this function.

    Returns an OptimizationResult with method="parameter_sweep",
    `evaluations` in sweep order, and best_parameters/best_objective from
    whichever swept point had the lowest objective value (minimize-by-
    convention -- see optimization/base.py).
    """
    validate_parameters([parameter])
    if n_points < 2:
        raise ValueError("n_points must be >= 2 (at least the two range endpoints).")

    baseline = default_values(other_parameters) if other_parameters else {}
    if fixed_values:
        baseline.update(fixed_values)

    raw_values = np.linspace(parameter.lower, parameter.upper, n_points)
    if parameter.param_type == "integer":
        swept_values = sorted({parameter.clip(v) for v in raw_values})
    else:
        swept_values = [parameter.clip(v) for v in raw_values]

    evaluations: list[dict] = []
    for value in swept_values:
        point = dict(baseline)
        point[parameter.name] = value
        objective_value = objective(point)
        record_evaluation(evaluations, point, objective_value)

    best_parameters, best_objective = best_of(evaluations)
    return OptimizationResult(
        method="parameter_sweep",
        best_parameters=best_parameters,
        best_objective=best_objective,
        evaluations=evaluations,
        parameters=[parameter, *(other_parameters or [])],
        objective_name=objective_name,
        constraints=constraints,
    )
