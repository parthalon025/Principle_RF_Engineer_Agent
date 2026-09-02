"""Differentiable (gradient-based) optimization via scipy.optimize.minimize's
L-BFGS-B method (issue #42), wrapped to match this package's shared
Parameter/ObjectiveFunction/OptimizationResult interface.

WHY L-BFGS-B: it is a bounded quasi-Newton method -- it natively accepts a
per-variable `bounds=[(lower, upper), ...]` argument, which maps directly
onto this module's `Parameter.lower`/`Parameter.upper` box-bounds concept
(unlike plain unbounded BFGS/CG), and is one of the gradient-based methods
this ticket's own design guidance names. It is appropriate specifically for
a SMOOTH, genuinely differentiable objective with a well-defined gradient
(e.g. a convex bowl, or a benchmark like Rosenbrock -- see
tests/test_optimization.py::test_gradient_optimize_finds_rosenbrock_global_minimum)
-- NOT for the sweep/grid/bayesian/genetic methods' black-box, possibly
noisy or discontinuous objectives, which is exactly why this is a separate
method rather than a variant of one of those.

Gradient handling: if the caller supplies an analytic `gradient` callable,
it is used directly (fastest, most robust). If not, scipy's own automatic
finite-difference gradient approximation is used -- a reasonable default for
wrapping an arbitrary differentiable black-box objective the caller hasn't
hand-differentiated, though slower and less numerically robust than an
analytic gradient (this tradeoff, and the option to supply an analytic
gradient instead, is exactly what this ticket's design guidance describes).

`Parameter.param_type == "integer"` is not a natural fit for a gradient
method -- a discrete variable has no well-defined derivative -- so, unlike
every other method in this package, `gradient_optimize` does NOT round
proposed points to the nearest integer; it is intended for continuous
parameters only (this is a deliberate, documented difference from
sweep/grid/bayesian/genetic's shared integer-rounding-via-`Parameter.clip`
behavior).

See optimization/base.py for the shared Parameter/ObjectiveFunction/
OptimizationResult contract and the minimize-by-convention sign rule every
method in this package follows. L-BFGS-B itself already minimizes by
convention, so no sign-flip is needed here.
"""

from collections.abc import Callable

import numpy as np
from scipy.optimize import minimize

from optimization.base import (
    ObjectiveFunction,
    OptimizationResult,
    Parameter,
    best_of,
    default_values,
    record_evaluation,
    validate_parameters,
)

# An optional analytic gradient: the same {parameter_name: value} dict shape
# ObjectiveFunction takes in, one partial derivative per parameter name out.
GradientFunction = Callable[[dict[str, float]], dict[str, float]]


def gradient_optimize(
    objective: ObjectiveFunction,
    parameters: list[Parameter],
    gradient: GradientFunction | None = None,
    initial_point: dict[str, float] | None = None,
    max_iterations: int = 200,
    tol: float = 1e-9,
    objective_name: str | None = None,
    constraints: dict | None = None,
) -> OptimizationResult:
    """Minimize `objective` over `parameters`' box bounds with
    scipy.optimize.minimize's bounded L-BFGS-B method -- see this module's
    docstring for why L-BFGS-B, and why this method (unlike the rest of this
    package) assumes a genuinely differentiable objective.

    - `gradient`: an optional analytic gradient, `{parameter_name: value}`
      in (same shape as `objective`'s own input), `{parameter_name:
      d(objective)/d(parameter_name)}` out. When omitted (the default),
      scipy approximates the gradient via finite differences automatically
      -- see this module's docstring for the tradeoff.
    - `initial_point`: the starting point L-BFGS-B descends from,
      `{parameter_name: value}`. Any parameter not given a value here falls
      back to that Parameter's own midpoint (`Parameter.midpoint`) -- the
      same "fixed value or midpoint default" convention parameter_sweep's
      `fixed_values` uses (see optimization/sweep.py). Gradient descent from
      a single starting point is inherently LOCAL -- unlike genetic_optimize
      or bayesian_optimize's global search, L-BFGS-B converges to whichever
      local optimum is downhill of `initial_point`, which is the known
      global optimum only for a genuinely convex (or otherwise
      well-behaved) objective; this is precisely why this method targets
      smooth differentiable objectives, not multimodal ones.
    - `max_iterations`: L-BFGS-B's own `maxiter` option.
    - `tol`: scipy's overall convergence tolerance (`minimize`'s own `tol`
      argument).
    - Only calls to the true objective (the original point, plus every
      finite-difference perturbation scipy makes when `gradient` is None)
      are recorded in `evaluations`, via a wrapped copy of `objective` that
      both calls the real objective and records the point -- the same
      wrapping technique genetic_optimize and bayesian_optimize's EI
      maximizer use. When an analytic `gradient` is supplied, scipy calls it
      separately from `objective`; those gradient calls are NOT themselves
      recorded as `evaluations` entries, since an `evaluations` entry
      records one (parameters, objective value) pair, not a gradient
      vector.

    Returns an OptimizationResult with method="gradient_optimize",
    `evaluations` in the order `objective` was actually called, and
    best_parameters/best_objective independently re-derived from that trace
    via `best_of` -- the same "recompute best_of from the trace, don't just
    trust the underlying library's own reported optimum" convention every
    method in this package follows.
    """
    validate_parameters(parameters)
    if max_iterations < 1:
        raise ValueError("max_iterations must be >= 1.")
    if tol <= 0:
        raise ValueError("tol must be > 0.")

    baseline = default_values(parameters)
    if initial_point:
        baseline.update(initial_point)
    x0 = np.array([baseline[p.name] for p in parameters])
    bounds = [(p.lower, p.upper) for p in parameters]

    evaluations: list[dict] = []

    def wrapped(x: np.ndarray) -> float:
        point = {p.name: float(v) for p, v in zip(parameters, x, strict=True)}
        objective_value = objective(point)
        record_evaluation(evaluations, point, objective_value)
        return objective_value

    def wrapped_jac(x: np.ndarray) -> np.ndarray:
        point = {p.name: float(v) for p, v in zip(parameters, x, strict=True)}
        grad = gradient(point)  # type: ignore[misc]
        return np.array([grad[p.name] for p in parameters])

    minimize(
        wrapped,
        x0=x0,
        method="L-BFGS-B",
        jac=wrapped_jac if gradient is not None else None,
        bounds=bounds,
        tol=tol,
        options={"maxiter": max_iterations},
    )

    best_parameters, best_objective = best_of(evaluations)
    return OptimizationResult(
        method="gradient_optimize",
        best_parameters=best_parameters,
        best_objective=best_objective,
        evaluations=evaluations,
        parameters=list(parameters),
        objective_name=objective_name,
        constraints=constraints,
    )
