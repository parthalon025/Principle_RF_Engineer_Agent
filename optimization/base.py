"""Shared objective/parameter interface for design optimization (issue #41).

Every optimization method in this package -- parameter_sweep, grid_search,
bayesian_optimize, and any future method -- is implemented against this same
contract, mirroring how simulation/base.py's SimulationResult/Simulator gives
every simulator backend a shared result shape:

  - `Parameter` describes ONE free design variable: a name, an inclusive
    lower/upper bound, and whether it is continuous or integer-valued.
  - The objective function itself is a plain `Callable[[dict[str, float]],
    float]`: parameters in as a `{name: value}` dict (keyed by each
    `Parameter.name`), a single scalar objective value out. EVERY method in
    this package MINIMIZES that scalar by convention -- to maximize a
    quantity (e.g. antenna gain), pass an objective that returns its
    negation. This sign convention is the single most common source of
    optimizer bugs, so it is asserted here once, loudly, rather than left
    implicit in each method's docstring.
  - `OptimizationResult` is the shared result shape: which method produced
    it, the best parameters/objective found, every point actually evaluated
    (so a caller can plot convergence or audit the search), and the
    objective/constraints that produced it -- so every result is
    self-describing without needing to consult the call site that made it.

Provenance: `OptimizationResult.provenance` defaults to "CALCULATED" (this
project's rf_tools domain-module convention, e.g. rf_tools/sheet_impedance.py),
not "SIMULATED"
(simulation/base.py's SimulationResult convention). Optimization here is a
deterministic (or, for bayesian_optimize, seeded-deterministic) numerical
procedure applied to whatever objective function the caller supplies -- it
does not itself run a physics simulation. If the supplied objective is
itself a simulation (e.g. wrapping run_nec2_simulation), that simulation's
own SIMULATED-provenance result is what backs each evaluated point; the
*optimization procedure*'s own contribution -- which points it chose to
evaluate and why -- is a calculated/deterministic search over that
objective, which is what this module's "CALCULATED" tag describes.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal

ParameterType = Literal["continuous", "integer"]

# The objective function contract every method in this package is written
# against: a dict of {parameter_name: value} in, one scalar out, minimized
# by convention (see module docstring).
ObjectiveFunction = Callable[[dict[str, float]], float]


@dataclass(frozen=True)
class Parameter:
    """One free design variable: a name, inclusive bounds, and a type.

    `name` is the key an objective function's input dict uses for this
    variable. `lower`/`upper` are inclusive bounds (upper > lower).
    `param_type` is "continuous" (default) or "integer" -- an integer
    parameter is always presented to the objective as a whole-number float
    (e.g. 3.0, not 3), rounded to the nearest integer within [lower, upper]
    by whichever method is sampling it (e.g. a Bayesian proposal that lands
    at 2.6 is rounded to 3.0 before the objective ever sees it).
    """

    name: str
    lower: float
    upper: float
    param_type: ParameterType = "continuous"

    def __post_init__(self) -> None:
        if self.upper <= self.lower:
            raise ValueError(
                f"Parameter {self.name!r}: upper bound ({self.upper}) must be "
                f"greater than lower bound ({self.lower})."
            )
        if self.param_type not in ("continuous", "integer"):
            raise ValueError(
                f"Parameter {self.name!r}: param_type must be 'continuous' or "
                f"'integer', got {self.param_type!r}."
            )

    def clip(self, value: float) -> float:
        """Clip `value` into [lower, upper], rounding to the nearest integer
        first when param_type is "integer"."""
        v = round(value) if self.param_type == "integer" else value
        return float(min(max(v, self.lower), self.upper))

    def midpoint(self) -> float:
        """The parameter's midpoint, used as the default fixed value for any
        parameter a method (e.g. parameter_sweep) is not currently varying."""
        return self.clip((self.lower + self.upper) / 2)


@dataclass
class OptimizationResult:
    """Shared result shape for every optimization method in this package.

    - `method`: the method name that produced this result, e.g.
      "parameter_sweep", "grid_search", "bayesian_optimize".
    - `best_parameters` / `best_objective`: the single best (lowest
      objective, per this package's minimize-by-convention) point found.
    - `evaluations`: EVERY point actually evaluated, in evaluation order,
      each as `{"parameters": {name: value, ...}, "objective": float}` --
      the full search trace, not just the winner. Lets a caller plot
      convergence, audit how many evaluations a method used, or re-derive
      `best_parameters`/`best_objective` independently.
    - `parameters`: the `Parameter` bounds/types the search ran over.
    - `objective_name`: a human-readable name/description of the objective
      function, if the caller provided one (e.g. "aperture_gain
      (maximize, negated for minimization)"). None if not provided.
    - `constraints`: any constraints the caller declared beyond the plain
      per-parameter box bounds already captured in `parameters` (e.g. a
      relationship between two parameters), recorded here for provenance
      even though none of the methods in this package currently enforce
      anything beyond box bounds -- see each method's docstring.
    - `provenance`: "CALCULATED" -- see module docstring for why this
      differs from simulation/base.py's "SIMULATED" default.
    """

    method: str
    best_parameters: dict[str, float]
    best_objective: float
    evaluations: list[dict[str, Any]]
    parameters: list[Parameter]
    objective_name: str | None = None
    constraints: dict[str, Any] | None = None
    provenance: str = "CALCULATED"


def validate_parameters(parameters: list[Parameter]) -> None:
    """Validate a parameter list shared by every method: non-empty and no
    duplicate names (each Parameter validates its own bounds/type in
    __post_init__)."""
    if not parameters:
        raise ValueError("At least one Parameter is required.")
    names = [p.name for p in parameters]
    if len(names) != len(set(names)):
        raise ValueError(f"Parameter names must be unique, got: {names}")


def default_values(parameters: list[Parameter]) -> dict[str, float]:
    """Each parameter's midpoint, keyed by name -- the default "everything
    else held fixed" baseline parameter_sweep uses for the parameters it is
    not currently varying."""
    return {p.name: p.midpoint() for p in parameters}


def record_evaluation(
    evaluations: list[dict[str, Any]], values: dict[str, float], objective_value: float
) -> None:
    """Append one evaluated point to an evaluations trace, in the shared
    `OptimizationResult.evaluations` shape."""
    evaluations.append({"parameters": dict(values), "objective": float(objective_value)})


def best_of(evaluations: list[dict[str, Any]]) -> tuple[dict[str, float], float]:
    """The (parameters, objective) of the lowest-objective point in an
    evaluations trace (minimize-by-convention, see module docstring)."""
    if not evaluations:
        raise ValueError("Cannot select a best point from an empty evaluations trace.")
    best = min(evaluations, key=lambda e: e["objective"])
    return dict(best["parameters"]), float(best["objective"])
