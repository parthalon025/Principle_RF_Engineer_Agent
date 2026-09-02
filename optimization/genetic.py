"""Genetic-algorithm optimization via scipy.optimize.differential_evolution
(issue #42), wrapped to match this package's shared Parameter/
ObjectiveFunction/OptimizationResult interface.

WHY differential_evolution, AND NOT A HAND-ROLLED GA: `differential_evolution`
is a real, well-tested evolutionary/genetic-family global optimizer already
available via this project's existing scipy dependency (this repo's
established preference is reusing a trusted library over hand-rolling
numerics where a good one exists -- see how rf_tools/touchstone.py uses
scikit-rf). This is a DIFFERENT call from grid_search's deliberate avoidance
of scipy.optimize.brute (see grid.py's docstring): that reasoning was
specific to brute's opaque extra local-refinement evaluations being a poor
match for a *grid search* ticket. It doesn't apply here -- differential
evolution genuinely IS the genetic/evolutionary-family algorithm this
ticket calls for, not a mismatch like brute was. DE maintains a POPULATION
of candidate parameter vectors across GENERATIONS, combining mutation
(perturbing one candidate by the scaled difference of two others) and
crossover/recombination (mixing a mutant with the current candidate) -- the
two defining operators of a genetic/evolutionary algorithm -- which lets it
escape the many local optima a multimodal objective presents (e.g. the
Rastrigin function -- see
tests/test_optimization.py::test_genetic_optimize_finds_rastrigin_global_minimum
for a synthetic multimodal test with a known global optimum, and a concrete
evaluation-count comparison against an equivalent-resolution grid), unlike a
purely local descent method.

See optimization/base.py for the shared Parameter/ObjectiveFunction/
OptimizationResult contract and the minimize-by-convention sign rule every
method in this package follows. differential_evolution itself already
minimizes by convention, so no sign-flip is needed here (unlike
bayesian_optimize's Expected Improvement, which is a maximization internally
negated -- see optimization/bayesian.py).
"""

import numpy as np
from scipy.optimize import differential_evolution

from optimization.base import (
    ObjectiveFunction,
    OptimizationResult,
    Parameter,
    best_of,
    record_evaluation,
    validate_parameters,
)


def genetic_optimize(
    objective: ObjectiveFunction,
    parameters: list[Parameter],
    max_generations: int = 100,
    population_size: int = 15,
    tol: float = 1e-7,
    random_seed: int | None = None,
    objective_name: str | None = None,
    constraints: dict | None = None,
) -> OptimizationResult:
    """Minimize `objective` over `parameters`' box bounds with
    scipy.optimize.differential_evolution, a population-based genetic/
    evolutionary global optimizer -- see this module's docstring for why DE
    (not a hand-rolled GA) satisfies this ticket's "genetic algorithm"
    requirement, and why it's a good fit for a multimodal objective where
    grid_search would need a prohibitive number of evaluations to cover the
    same space at comparable resolution.

    - `max_generations` / `population_size`: DE's `maxiter`/`popsize`. DE
      stops as soon as its population converges within `tol` (below), so
      the actual number of evaluations recorded in `evaluations` is
      typically far fewer than `max_generations` would allow in the worst
      case -- exactly the "far fewer evaluations than an equivalent-
      resolution grid" value proposition a genetic algorithm is chosen for
      here (see tests/test_optimization.py for a concrete, asserted
      comparison against grid_search's evaluation count on the same
      dimensionality).
    - `tol`: DE's relative convergence tolerance (`differential_evolution`'s
      own `tol` argument) -- the population's cost standard deviation must
      fall below this relative to its mean before DE calls itself converged
      and stops early.
    - `random_seed`: seeds DE's population initialization and mutation, so a
      given seed reproduces the same evaluation trace -- the same
      determinism contract bayesian_optimize's `random_seed` gives (see
      optimization/bayesian.py).
    - Every candidate DE evaluates (across the whole population, every
      generation, plus its final polish step) is recorded in `evaluations`,
      via a wrapped copy of `objective` that both calls the real objective
      and records the point -- the "track all evaluations ... by wrapping
      the objective to record each call" approach this ticket's design
      guidance names. DE has no per-call hook the way bayesian_optimize's
      explicit per-iteration loop does, so wrapping is the only way to
      capture the full trace.
    - An "integer" Parameter is rounded to the nearest integer (via
      `Parameter.clip`) before each evaluation -- DE itself always searches
      continuous real vectors within `bounds`; rounding-then-evaluating is
      the same approximation bayesian_optimize uses for integer parameters
      (see optimization/bayesian.py's docstring), not a fully
      integer-aware GA.

    Returns an OptimizationResult with method="genetic_optimize",
    `evaluations` in the order DE actually called `objective` (population
    initialization first, then generation by generation, then any polish
    step), and best_parameters/best_objective independently re-derived from
    that trace via `best_of` -- the same "recompute best_of from the trace,
    don't just trust the underlying library's own reported optimum"
    convention every method in this package follows.
    """
    validate_parameters(parameters)
    if population_size < 1:
        raise ValueError("population_size must be >= 1.")
    if max_generations < 1:
        raise ValueError("max_generations must be >= 1.")

    bounds = [(p.lower, p.upper) for p in parameters]
    evaluations: list[dict] = []

    def wrapped(x: np.ndarray) -> float:
        point = {p.name: p.clip(v) for p, v in zip(parameters, x, strict=True)}
        objective_value = objective(point)
        record_evaluation(evaluations, point, objective_value)
        return objective_value

    differential_evolution(
        wrapped,
        bounds=bounds,
        maxiter=max_generations,
        popsize=population_size,
        tol=tol,
        seed=random_seed,
        polish=True,
    )

    best_parameters, best_objective = best_of(evaluations)
    return OptimizationResult(
        method="genetic_optimize",
        best_parameters=best_parameters,
        best_objective=best_objective,
        evaluations=evaluations,
        parameters=list(parameters),
        objective_name=objective_name,
        constraints=constraints,
    )
