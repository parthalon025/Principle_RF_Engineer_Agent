"""One concrete, named optimization use case wired against this repo's own
Phase 1 calculation tools (issue #41's tool-wiring answer).

WHY A NAMED OBJECTIVE, NOT AN ARBITRARY CALLABLE: `parameter_sweep`,
`grid_search`, and `bayesian_optimize` (optimization/{sweep,grid,bayesian}.py)
all take a plain Python `Callable[[dict[str, float]], float]` objective (see
optimization/base.py) -- exactly the shape another Python module calling
into this package directly should use. But an MCP tool call / agent tool
call crosses a JSON-RPC boundary: its arguments are JSON-serializable data,
not a Python function object, so a generic "optimize this arbitrary
callable" tool cannot be represented over that boundary at all. This
ticket's own design guidance names two ways to close that gap -- optimize
ONE of this repo's existing calculation tools by name, or a small fixed
menu of named objectives reachable by name. This module takes the first,
narrower option (one concrete case, not a speculative menu abstraction for
objectives that do not exist yet): it optimizes a microstrip patch
antenna's length (the one free geometric variable
patch_resonant_frequency_hz's transmission-line model is most directly
invertible in) to hit a target resonant frequency, composing this ticket's
optimization methods with the Phase 1 antenna-synthesis calculation
(rf_tools.calculations.patch_resonant_frequency_hz) exactly as the ticket's
own context describes ("calling into Phase 1 calculations ... as the
objective function"). See mcp_server/server.py's
optimize_patch_length_for_target_frequency and agent/main.py's matching
agent tool for how this crosses the MCP/agent-tool boundary: a target
frequency, a substrate/width, and a length search range -- all plain
numbers -- go in; the optimizer's own OptimizationResult (method,
best/all-evaluated points, objective description, constraints) comes back.

A future ticket adding a second named objective (e.g. "maximize
aperture_gain subject to an area bound") should follow this same shape:
one small `..._objective()` factory below plus one small
`optimize_...()` entry point, not a generic registry -- there is exactly
one concrete case earning that generality today.
"""

from optimization.base import ObjectiveFunction, OptimizationResult, Parameter
from optimization.bayesian import bayesian_optimize
from optimization.grid import grid_search
from optimization.sweep import parameter_sweep
from rf_tools.calculations import patch_resonant_frequency_hz

_METHODS = ("sweep", "grid", "bayesian")


def patch_length_objective(
    eps_r: float, w_m: float, h_m: float, target_frequency_hz: float
) -> ObjectiveFunction:
    """Build an objective minimized (by this package's convention) when a
    microstrip patch's TM010 resonant frequency (patch_resonant_frequency_hz,
    at fixed substrate eps_r/h_m and patch width w_m) is closest to
    target_frequency_hz, as a function of patch length alone (parameter key
    "length_m"):

        objective(length_m) = ((f_r(length_m) - target_frequency_hz) / target_frequency_hz) ** 2

    The squared FRACTIONAL error (not raw Hz^2) keeps the objective's scale
    independent of target_frequency_hz's own magnitude (MHz vs. GHz targets
    behave the same way), which matters in particular for
    bayesian_optimize's internal standardization/length-scale fitting (see
    optimization/bayesian.py).
    """
    if target_frequency_hz <= 0:
        raise ValueError("target_frequency_hz must be positive.")

    def objective(params: dict[str, float]) -> float:
        f_r = patch_resonant_frequency_hz(eps_r, w_m, h_m, params["length_m"])
        return ((f_r - target_frequency_hz) / target_frequency_hz) ** 2

    return objective


def optimize_patch_length_for_target_frequency(
    eps_r: float,
    w_m: float,
    h_m: float,
    target_frequency_hz: float,
    length_lower_m: float,
    length_upper_m: float,
    method: str = "bayesian",
    n_evaluations: int = 20,
) -> dict:
    """Search patch length in [length_lower_m, length_upper_m] (substrate
    eps_r/h_m and patch width w_m held fixed) for the value whose TM010
    resonant frequency (patch_resonant_frequency_hz) is closest to
    target_frequency_hz.

    `method` selects which of this package's methods runs the search:
    "sweep" (parameter_sweep, n_evaluations evenly-spaced points),
    "grid" (grid_search, n_evaluations points -- equivalent to a sweep in
    this single-parameter case, offered for interface consistency with a
    future multi-parameter version of this objective), or "bayesian"
    (bayesian_optimize, n_evaluations split as roughly 1/4 initial
    space-filling points and 3/4 GP-guided iterations).

    Returns a flat dict (JSON-friendly for the MCP/agent tool boundary --
    see this module's docstring): method, best_length_m, the resulting
    achieved_frequency_hz (recomputed directly from
    patch_resonant_frequency_hz at best_length_m, not merely
    inferred from the objective's own value), target_frequency_hz,
    best_objective, n_evaluations actually used, objective_name,
    constraints (the fixed eps_r/w_m/h_m the search held constant), and
    "CALCULATED" provenance -- the same fields OptimizationResult carries,
    flattened for a JSON tool return.
    """
    if method not in _METHODS:
        raise ValueError(f"method must be one of {_METHODS}, got {method!r}.")

    parameter = Parameter("length_m", length_lower_m, length_upper_m)
    objective = patch_length_objective(eps_r, w_m, h_m, target_frequency_hz)
    objective_name = (
        f"squared fractional error between patch_resonant_frequency_hz(length_m) "
        f"and target_frequency_hz={target_frequency_hz:g} Hz"
    )
    constraints = {"eps_r": eps_r, "w_m": w_m, "h_m": h_m}

    result: OptimizationResult
    if method == "sweep":
        result = parameter_sweep(
            objective,
            parameter,
            n_points=n_evaluations,
            objective_name=objective_name,
            constraints=constraints,
        )
    elif method == "grid":
        result = grid_search(
            objective,
            [parameter],
            n_points_per_dim=n_evaluations,
            objective_name=objective_name,
            constraints=constraints,
        )
    else:
        n_initial_points = max(2, n_evaluations // 4)
        n_iterations = max(0, n_evaluations - n_initial_points)
        result = bayesian_optimize(
            objective,
            [parameter],
            n_iterations=n_iterations,
            n_initial_points=n_initial_points,
            objective_name=objective_name,
            constraints=constraints,
        )

    best_length_m = result.best_parameters["length_m"]
    achieved_frequency_hz = patch_resonant_frequency_hz(eps_r, w_m, h_m, best_length_m)
    return {
        "method": result.method,
        "best_length_m": best_length_m,
        "achieved_frequency_hz": achieved_frequency_hz,
        "target_frequency_hz": target_frequency_hz,
        "best_objective": result.best_objective,
        "n_evaluations": len(result.evaluations),
        "objective_name": result.objective_name,
        "constraints": result.constraints,
        "provenance": result.provenance,
    }
