"""Tests for the optimization package (issue #41): the shared Parameter/
OptimizationResult interface, parameter_sweep, grid_search, and
bayesian_optimize, all exercised against synthetic objective functions with
a known closed-form optimum.

Every method in optimization/ MINIMIZES its objective by convention (see
optimization/base.py), so every synthetic objective below is a "bowl" (or
bowl-plus-ripple) shape with a known minimum, not a function to maximize.
"""

import numpy as np
import pytest

from optimization.base import (
    OptimizationResult,
    Parameter,
    best_of,
    default_values,
    validate_parameters,
)
from optimization.bayesian import bayesian_optimize
from optimization.genetic import genetic_optimize
from optimization.gradient import gradient_optimize
from optimization.grid import grid_search
from optimization.rf_objectives import (
    optimize_patch_length_for_target_frequency,
    patch_length_objective,
)
from optimization.sweep import parameter_sweep
from rf_tools.calculations import patch_resonant_frequency_hz

# ---------------------------------------------------------------------------
# Synthetic objectives with known closed-form optima.
# ---------------------------------------------------------------------------


def quadratic_bowl_1d(params: dict) -> float:
    """(x - 3)^2 -- minimum 0.0 at x = 3.0."""
    return (params["x"] - 3.0) ** 2


def quadratic_bowl_2d(params: dict) -> float:
    """(x - 3)^2 + (y + 1)^2 -- minimum 0.0 at (x, y) = (3.0, -1.0)."""
    return (params["x"] - 3.0) ** 2 + (params["y"] + 1.0) ** 2


def rippled_bowl_1d(params: dict) -> float:
    """A quadratic bowl with a small sinusoidal ripple, one clear global
    minimum near x = 2.0 (the ripple's amplitude is small enough that it
    does not create a competing local minimum lower than the global one) --
    the "mildly multimodal, one clear global minimum" shape this ticket's
    design guidance suggests as an alternative to a plain bowl."""
    x = params["x"]
    return (x - 2.0) ** 2 + 0.3 * np.sin(3.0 * x)


def rastrigin(params: dict) -> float:
    """Rastrigin function, 6-dimensional -- a standard multimodal
    optimization benchmark (Rastrigin, 1974; popularized in the general
    n-dimensional form used here by Muhlenbein, Schomisch & Born, 1991):

        f(x) = 10n + sum_i (x_i^2 - 10*cos(2*pi*x_i))

    with a KNOWN global minimum of 0.0 at the origin, surrounded within its
    conventional [-5.12, 5.12] domain by a dense lattice of regularly
    spaced local minima (one roughly every unit step per dimension) --
    exactly the highly multimodal shape a genetic algorithm's
    population-based global search (issue #42) is chosen for, and exactly
    what makes an equivalent-resolution grid search impractical at this
    dimensionality (see test_genetic_optimize_finds_rastrigin_global_minimum
    below for the concrete evaluation-count comparison)."""
    x = np.array([params[f"x{i}"] for i in range(6)])
    return float(10 * len(x) + np.sum(x**2 - 10 * np.cos(2 * np.pi * x)))


def rosenbrock(params: dict) -> float:
    """Rosenbrock's function, 2-dimensional -- a standard, smooth,
    differentiable (but non-convex "banana valley") optimization benchmark
    (Rosenbrock, 1960): f(x, y) = 100*(y - x^2)^2 + (1 - x)^2, with a KNOWN
    global minimum of 0.0 at (x, y) = (1.0, 1.0)."""
    x0, x1 = params["x0"], params["x1"]
    return 100.0 * (x1 - x0**2) ** 2 + (1.0 - x0) ** 2


def rosenbrock_gradient(params: dict) -> dict:
    """Analytic gradient of rosenbrock() above, for gradient_optimize's
    optional `gradient` argument:
        d/dx0 = -400*x0*(x1 - x0^2) - 2*(1 - x0)
        d/dx1 =  200*(x1 - x0^2)
    """
    x0, x1 = params["x0"], params["x1"]
    return {
        "x0": -400.0 * x0 * (x1 - x0**2) - 2.0 * (1.0 - x0),
        "x1": 200.0 * (x1 - x0**2),
    }


# ---------------------------------------------------------------------------
# Parameter / OptimizationResult interface
# ---------------------------------------------------------------------------


def test_parameter_rejects_invalid_bounds():
    with pytest.raises(ValueError, match="upper bound"):
        Parameter("x", 5.0, 1.0)


def test_parameter_rejects_invalid_type():
    with pytest.raises(ValueError, match="param_type"):
        Parameter("x", 0.0, 1.0, param_type="categorical")  # type: ignore[arg-type]


def test_parameter_clip_rounds_integer_type():
    p = Parameter("n", 0.0, 10.0, param_type="integer")
    assert p.clip(3.6) == 4.0
    assert p.clip(-5.0) == 0.0  # clipped into bounds
    assert p.clip(99.0) == 10.0


def test_parameter_midpoint():
    assert Parameter("x", 0.0, 10.0).midpoint() == 5.0


def test_validate_parameters_rejects_empty_list():
    with pytest.raises(ValueError, match="At least one"):
        validate_parameters([])


def test_validate_parameters_rejects_duplicate_names():
    with pytest.raises(ValueError, match="unique"):
        validate_parameters([Parameter("x", 0.0, 1.0), Parameter("x", 0.0, 2.0)])


def test_default_values_uses_midpoints():
    params = [Parameter("x", 0.0, 10.0), Parameter("y", -4.0, 4.0)]
    assert default_values(params) == {"x": 5.0, "y": 0.0}


def test_best_of_selects_lowest_objective():
    evaluations = [
        {"parameters": {"x": 1.0}, "objective": 5.0},
        {"parameters": {"x": 2.0}, "objective": 1.0},
        {"parameters": {"x": 3.0}, "objective": 3.0},
    ]
    best_params, best_obj = best_of(evaluations)
    assert best_params == {"x": 2.0}
    assert best_obj == 1.0


def test_best_of_rejects_empty_evaluations():
    with pytest.raises(ValueError, match="empty"):
        best_of([])


def test_optimization_result_default_provenance_is_calculated():
    result = OptimizationResult(
        method="parameter_sweep",
        best_parameters={"x": 3.0},
        best_objective=0.0,
        evaluations=[],
        parameters=[Parameter("x", 0.0, 5.0)],
    )
    assert result.provenance == "CALCULATED"


# ---------------------------------------------------------------------------
# parameter_sweep
# ---------------------------------------------------------------------------


def test_parameter_sweep_finds_known_optimum():
    p = Parameter("x", -10.0, 10.0)
    result = parameter_sweep(quadratic_bowl_1d, p, n_points=41)
    assert result.method == "parameter_sweep"
    assert result.best_parameters["x"] == pytest.approx(3.0, abs=0.5)
    assert result.best_objective == pytest.approx(0.0, abs=0.25)
    assert len(result.evaluations) == 41


def test_parameter_sweep_holds_other_parameters_at_midpoint_by_default():
    def objective(params: dict) -> float:
        return (params["x"] - 3.0) ** 2 + (params["y"] - 100.0) ** 2

    px = Parameter("x", -10.0, 10.0)
    py = Parameter("y", -10.0, 10.0)  # midpoint 0.0
    result = parameter_sweep(objective, px, n_points=5, other_parameters=[py])
    # Every evaluated point should have carried y = py.midpoint() = 0.0.
    assert all(e["parameters"]["y"] == 0.0 for e in result.evaluations)


def test_parameter_sweep_respects_explicit_fixed_values():
    def objective(params: dict) -> float:
        return params["x"] + params["y"]

    px = Parameter("x", 0.0, 1.0)
    result = parameter_sweep(objective, px, n_points=3, fixed_values={"y": 42.0})
    assert all(e["parameters"]["y"] == 42.0 for e in result.evaluations)


def test_parameter_sweep_rejects_too_few_points():
    with pytest.raises(ValueError, match="n_points"):
        parameter_sweep(quadratic_bowl_1d, Parameter("x", 0.0, 1.0), n_points=1)


def test_parameter_sweep_tags_objective_name_and_constraints():
    p = Parameter("x", 0.0, 5.0)
    result = parameter_sweep(
        quadratic_bowl_1d,
        p,
        n_points=5,
        objective_name="quadratic_bowl_1d",
        constraints={"note": "box bounds only"},
    )
    assert result.objective_name == "quadratic_bowl_1d"
    assert result.constraints == {"note": "box bounds only"}


def test_parameter_sweep_integer_parameter_deduplicates_rounded_values():
    p = Parameter("n", 0.0, 3.0, param_type="integer")
    result = parameter_sweep(lambda params: params["n"], p, n_points=20)
    values = sorted(e["parameters"]["n"] for e in result.evaluations)
    assert values == [0.0, 1.0, 2.0, 3.0]


# ---------------------------------------------------------------------------
# grid_search
# ---------------------------------------------------------------------------


def test_grid_search_finds_known_optimum_1d():
    p = Parameter("x", -10.0, 10.0)
    result = grid_search(quadratic_bowl_1d, [p], n_points_per_dim=41)
    assert result.method == "grid_search"
    assert result.best_parameters["x"] == pytest.approx(3.0, abs=0.5)
    assert len(result.evaluations) == 41


def test_grid_search_finds_known_optimum_2d():
    px = Parameter("x", -10.0, 10.0)
    py = Parameter("y", -10.0, 10.0)
    result = grid_search(quadratic_bowl_2d, [px, py], n_points_per_dim=21)
    assert result.best_parameters["x"] == pytest.approx(3.0, abs=1.0)
    assert result.best_parameters["y"] == pytest.approx(-1.0, abs=1.0)
    assert len(result.evaluations) == 21 * 21


def test_grid_search_evaluation_count_is_exponential_in_dimension():
    px = Parameter("x", 0.0, 1.0)
    py = Parameter("y", 0.0, 1.0)
    result_1d = grid_search(lambda p: p["x"], [px], n_points_per_dim=10)
    result_2d = grid_search(lambda p: p["x"] + p["y"], [px, py], n_points_per_dim=10)
    assert len(result_1d.evaluations) == 10
    assert len(result_2d.evaluations) == 100


def test_grid_search_rejects_too_few_points():
    with pytest.raises(ValueError, match="n_points_per_dim"):
        grid_search(quadratic_bowl_1d, [Parameter("x", 0.0, 1.0)], n_points_per_dim=1)


def test_grid_search_rejects_empty_parameter_list():
    with pytest.raises(ValueError, match="At least one"):
        grid_search(quadratic_bowl_1d, [], n_points_per_dim=5)


# ---------------------------------------------------------------------------
# bayesian_optimize
# ---------------------------------------------------------------------------


def test_bayesian_optimize_finds_known_optimum_1d():
    p = Parameter("x", -10.0, 10.0)
    result = bayesian_optimize(
        quadratic_bowl_1d, [p], n_iterations=15, n_initial_points=5, random_seed=1
    )
    assert result.method == "bayesian_optimize"
    assert result.best_parameters["x"] == pytest.approx(3.0, abs=1.0)
    assert len(result.evaluations) == 20


def test_bayesian_optimize_handles_rippled_multimodal_objective():
    p = Parameter("x", -5.0, 5.0)
    result = bayesian_optimize(
        rippled_bowl_1d, [p], n_iterations=20, n_initial_points=5, random_seed=3
    )
    assert result.best_parameters["x"] == pytest.approx(2.0, abs=1.0)


def test_bayesian_optimize_is_deterministic_given_a_seed():
    p = Parameter("x", -10.0, 10.0)
    result_a = bayesian_optimize(
        quadratic_bowl_1d, [p], n_iterations=8, n_initial_points=5, random_seed=99
    )
    result_b = bayesian_optimize(
        quadratic_bowl_1d, [p], n_iterations=8, n_initial_points=5, random_seed=99
    )
    assert result_a.best_parameters == result_b.best_parameters
    assert result_a.best_objective == result_b.best_objective
    assert result_a.evaluations == result_b.evaluations


def test_bayesian_optimize_rejects_too_few_initial_points():
    with pytest.raises(ValueError, match="n_initial_points"):
        bayesian_optimize(
            quadratic_bowl_1d, [Parameter("x", 0.0, 1.0)], n_initial_points=1
        )


def test_bayesian_optimize_tags_objective_name_and_constraints():
    p = Parameter("x", 0.0, 5.0)
    result = bayesian_optimize(
        quadratic_bowl_1d,
        [p],
        n_iterations=3,
        n_initial_points=3,
        random_seed=5,
        objective_name="quadratic_bowl_1d",
        constraints={"note": "box bounds only"},
    )
    assert result.objective_name == "quadratic_bowl_1d"
    assert result.constraints == {"note": "box bounds only"}


# ---------------------------------------------------------------------------
# Acceptance criterion: bayesian_optimize converges toward the known optimum
# in fewer evaluations than grid_search on the same 2D problem.
#
# grid_search runs a 5x5 grid (25 evaluations); bayesian_optimize runs 5
# initial + 15 iterations = 20 evaluations -- FEWER than grid_search's 25 --
# and still lands closer to the true optimum (3.0, -1.0). random_seed fixes
# every stochastic step in bayesian_optimize so this assertion is not flaky.
# ---------------------------------------------------------------------------


def test_bayesian_optimize_converges_faster_than_grid_search():
    px = Parameter("x", -10.0, 10.0)
    py = Parameter("y", -10.0, 10.0)
    true_optimum = np.array([3.0, -1.0])

    def distance_to_optimum(params: dict) -> float:
        return float(np.linalg.norm(np.array([params["x"], params["y"]]) - true_optimum))

    grid_result = grid_search(quadratic_bowl_2d, [px, py], n_points_per_dim=5)
    bayes_result = bayesian_optimize(
        quadratic_bowl_2d,
        [px, py],
        n_iterations=15,
        n_initial_points=5,
        random_seed=7,
    )

    assert len(bayes_result.evaluations) < len(grid_result.evaluations)
    assert distance_to_optimum(bayes_result.best_parameters) < distance_to_optimum(
        grid_result.best_parameters
    )
    # Bayesian optimization should also land close to the true optimum in
    # absolute terms, not merely "closer than a coarse grid".
    assert distance_to_optimum(bayes_result.best_parameters) < 0.5


# ---------------------------------------------------------------------------
# genetic_optimize (issue #42): scipy.optimize.differential_evolution
# wrapped to this package's shared interface.
# ---------------------------------------------------------------------------


def test_genetic_optimize_finds_known_optimum_1d():
    p = Parameter("x", -10.0, 10.0)
    result = genetic_optimize(
        quadratic_bowl_1d, [p], max_generations=50, population_size=15, random_seed=2
    )
    assert result.method == "genetic_optimize"
    assert result.best_parameters["x"] == pytest.approx(3.0, abs=0.1)
    assert result.best_objective == pytest.approx(0.0, abs=0.05)
    assert result.provenance == "CALCULATED"


def test_genetic_optimize_is_deterministic_given_a_seed():
    p = Parameter("x", -5.0, 5.0)
    result_a = genetic_optimize(
        quadratic_bowl_1d, [p], max_generations=20, population_size=10, random_seed=11
    )
    result_b = genetic_optimize(
        quadratic_bowl_1d, [p], max_generations=20, population_size=10, random_seed=11
    )
    assert result_a.best_parameters == result_b.best_parameters
    assert result_a.best_objective == result_b.best_objective
    assert result_a.evaluations == result_b.evaluations


def test_genetic_optimize_tags_objective_name_and_constraints():
    p = Parameter("x", 0.0, 5.0)
    result = genetic_optimize(
        quadratic_bowl_1d,
        [p],
        max_generations=20,
        population_size=10,
        random_seed=1,
        objective_name="quadratic_bowl_1d",
        constraints={"note": "box bounds only"},
    )
    assert result.objective_name == "quadratic_bowl_1d"
    assert result.constraints == {"note": "box bounds only"}


def test_genetic_optimize_rejects_invalid_population_size():
    with pytest.raises(ValueError, match="population_size"):
        genetic_optimize(quadratic_bowl_1d, [Parameter("x", 0.0, 1.0)], population_size=0)


def test_genetic_optimize_rejects_invalid_max_generations():
    with pytest.raises(ValueError, match="max_generations"):
        genetic_optimize(quadratic_bowl_1d, [Parameter("x", 0.0, 1.0)], max_generations=0)


def test_genetic_optimize_rejects_empty_parameter_list():
    with pytest.raises(ValueError, match="At least one"):
        genetic_optimize(quadratic_bowl_1d, [])


# ---------------------------------------------------------------------------
# Acceptance criterion: genetic_optimize finds the known global minimum of a
# highly multimodal, higher-dimensional objective (6D Rastrigin -- see
# rastrigin()'s docstring) where an equivalent-resolution grid search is
# genuinely impractical.
#
# grid_search's own cost is n_points_per_dim ** len(parameters) (see
# grid.py's docstring): even a COARSE 10-points-per-dimension grid at 6
# dimensions is 10**6 == 1,000,000 evaluations. genetic_optimize instead
# finds the known global minimum (0.0 at the origin) in well under 1% of
# that evaluation budget.
# ---------------------------------------------------------------------------


def test_genetic_optimize_finds_rastrigin_global_minimum():
    equivalent_grid_evaluations = 10**6  # 10 points/dim ** 6 dimensions
    assert equivalent_grid_evaluations == 1_000_000

    parameters = [Parameter(f"x{i}", -5.12, 5.12) for i in range(6)]
    result = genetic_optimize(
        rastrigin,
        parameters,
        max_generations=200,
        population_size=20,
        random_seed=42,
        objective_name="rastrigin_6d",
        constraints={"domain": "standard [-5.12, 5.12] Rastrigin bounds"},
    )

    assert result.method == "genetic_optimize"
    assert result.best_objective == pytest.approx(0.0, abs=1e-4)
    for i in range(6):
        assert result.best_parameters[f"x{i}"] == pytest.approx(0.0, abs=1e-3)

    # Orders of magnitude fewer evaluations than the impractical equivalent
    # grid -- the concrete "why grid search doesn't scale here" comparison.
    assert len(result.evaluations) < equivalent_grid_evaluations / 10

    assert result.objective_name == "rastrigin_6d"
    assert result.constraints == {"domain": "standard [-5.12, 5.12] Rastrigin bounds"}
    assert result.provenance == "CALCULATED"


# ---------------------------------------------------------------------------
# gradient_optimize (issue #42): scipy.optimize.minimize's bounded L-BFGS-B
# wrapped to this package's shared interface.
# ---------------------------------------------------------------------------


def test_gradient_optimize_finds_known_optimum_1d_from_default_midpoint():
    p = Parameter("x", -10.0, 10.0)  # midpoint 0.0
    result = gradient_optimize(quadratic_bowl_1d, [p])
    assert result.method == "gradient_optimize"
    assert result.best_parameters["x"] == pytest.approx(3.0, abs=1e-4)
    assert result.best_objective == pytest.approx(0.0, abs=1e-6)
    assert result.provenance == "CALCULATED"


def test_gradient_optimize_uses_supplied_initial_point_not_the_midpoint():
    def objective(params: dict) -> float:
        return (params["x"] - 3.0) ** 2

    p = Parameter("x", -10.0, 10.0)  # midpoint 0.0
    result = gradient_optimize(objective, [p], initial_point={"x": 7.0}, max_iterations=1)
    # The very first call the wrapped objective receives is at x0 itself.
    assert result.evaluations[0]["parameters"]["x"] == 7.0


def test_gradient_optimize_tags_objective_name_and_constraints():
    p = Parameter("x", 0.0, 5.0)
    result = gradient_optimize(
        quadratic_bowl_1d,
        [p],
        objective_name="quadratic_bowl_1d",
        constraints={"note": "box bounds only"},
    )
    assert result.objective_name == "quadratic_bowl_1d"
    assert result.constraints == {"note": "box bounds only"}


def test_gradient_optimize_rejects_too_few_iterations():
    with pytest.raises(ValueError, match="max_iterations"):
        gradient_optimize(quadratic_bowl_1d, [Parameter("x", 0.0, 1.0)], max_iterations=0)


def test_gradient_optimize_rejects_non_positive_tol():
    with pytest.raises(ValueError, match="tol"):
        gradient_optimize(quadratic_bowl_1d, [Parameter("x", 0.0, 1.0)], tol=0.0)


def test_gradient_optimize_rejects_empty_parameter_list():
    with pytest.raises(ValueError, match="At least one"):
        gradient_optimize(quadratic_bowl_1d, [])


def test_gradient_optimize_analytic_gradient_matches_finite_difference_result():
    parameters = [Parameter("x0", -2.0, 2.0), Parameter("x1", -2.0, 2.0)]
    initial_point = {"x0": -1.5, "x1": 2.0}

    finite_difference_result = gradient_optimize(
        rosenbrock, parameters, initial_point=initial_point
    )
    analytic_result = gradient_optimize(
        rosenbrock, parameters, gradient=rosenbrock_gradient, initial_point=initial_point
    )

    for key in ("x0", "x1"):
        assert analytic_result.best_parameters[key] == pytest.approx(
            finite_difference_result.best_parameters[key], abs=1e-3
        )
    # Supplying the analytic gradient (no finite-difference perturbation
    # calls needed) uses meaningfully fewer objective evaluations.
    assert len(analytic_result.evaluations) < len(finite_difference_result.evaluations)


# ---------------------------------------------------------------------------
# Acceptance criterion: gradient_optimize converges to the known optimum of
# a smooth differentiable benchmark (2D Rosenbrock -- see rosenbrock()'s
# docstring) using meaningfully fewer evaluations than a comparable grid
# search, and lands closer to the true optimum than that grid does.
# ---------------------------------------------------------------------------


def test_gradient_optimize_converges_faster_than_grid_search_on_rosenbrock():
    parameters = [Parameter("x0", -2.0, 2.0), Parameter("x1", -2.0, 2.0)]
    true_optimum = np.array([1.0, 1.0])

    def distance_to_optimum(params: dict) -> float:
        return float(np.linalg.norm(np.array([params["x0"], params["x1"]]) - true_optimum))

    grid_result = grid_search(rosenbrock, parameters, n_points_per_dim=50)
    assert len(grid_result.evaluations) == 2500  # 50 ** 2, the comparison baseline

    gradient_result = gradient_optimize(
        rosenbrock,
        parameters,
        gradient=rosenbrock_gradient,
        initial_point={"x0": -1.5, "x1": 2.0},
    )

    # An order of magnitude fewer evaluations than the 2,500-point grid...
    assert len(gradient_result.evaluations) < len(grid_result.evaluations) / 10
    # ...yet closer to the true optimum, and within a tight absolute tolerance.
    assert distance_to_optimum(gradient_result.best_parameters) < distance_to_optimum(
        grid_result.best_parameters
    )
    assert gradient_result.best_objective == pytest.approx(0.0, abs=1e-6)


# ---------------------------------------------------------------------------
# optimization/rf_objectives.py: the one concrete tool-wiring case (issue
# #41), composing this package's methods with the Phase 1
# patch_resonant_frequency_hz calculation.
# ---------------------------------------------------------------------------

# Substrate/width chosen so the search range below actually brackets the
# 2.4 GHz target (see the module's own worked example): a wide FR4-like
# patch antenna whose resonant frequency crosses 2.4 GHz somewhere inside
# [20mm, 40mm] of length.
_EPS_R = 4.4
_W_M = 0.038
_H_M = 0.0016
_TARGET_HZ = 2.4e9


def test_patch_length_objective_rejects_non_positive_target():
    with pytest.raises(ValueError, match="target_frequency_hz"):
        patch_length_objective(_EPS_R, _W_M, _H_M, target_frequency_hz=0.0)


def test_patch_length_objective_is_zero_at_the_true_length():
    # Find a length whose resonant frequency IS the target (to float
    # precision) by construction, then confirm the objective is ~0 there.
    true_length_m = 0.0295
    true_frequency_hz = patch_resonant_frequency_hz(_EPS_R, _W_M, _H_M, true_length_m)
    objective = patch_length_objective(_EPS_R, _W_M, _H_M, true_frequency_hz)
    assert objective({"length_m": true_length_m}) == pytest.approx(0.0, abs=1e-12)


@pytest.mark.parametrize("method", ["sweep", "grid", "bayesian"])
def test_optimize_patch_length_for_target_frequency_finds_a_close_length(method):
    result = optimize_patch_length_for_target_frequency(
        eps_r=_EPS_R,
        w_m=_W_M,
        h_m=_H_M,
        target_frequency_hz=_TARGET_HZ,
        length_lower_m=0.02,
        length_upper_m=0.04,
        method=method,
        n_evaluations=20,
    )
    assert 0.02 <= result["best_length_m"] <= 0.04
    # Within 2% of the target frequency for every method at this budget.
    relative_error = abs(result["achieved_frequency_hz"] - _TARGET_HZ) / _TARGET_HZ
    assert relative_error < 0.02
    assert result["target_frequency_hz"] == _TARGET_HZ
    assert result["n_evaluations"] == 20
    assert result["provenance"] == "CALCULATED"
    assert result["constraints"] == {"eps_r": _EPS_R, "w_m": _W_M, "h_m": _H_M}


def test_optimize_patch_length_for_target_frequency_achieved_frequency_matches_calculation():
    result = optimize_patch_length_for_target_frequency(
        eps_r=_EPS_R,
        w_m=_W_M,
        h_m=_H_M,
        target_frequency_hz=_TARGET_HZ,
        length_lower_m=0.02,
        length_upper_m=0.04,
        method="grid",
        n_evaluations=15,
    )
    recomputed = patch_resonant_frequency_hz(_EPS_R, _W_M, _H_M, result["best_length_m"])
    assert result["achieved_frequency_hz"] == pytest.approx(recomputed)


def test_optimize_patch_length_for_target_frequency_rejects_unknown_method():
    with pytest.raises(ValueError, match="method"):
        optimize_patch_length_for_target_frequency(
            eps_r=_EPS_R,
            w_m=_W_M,
            h_m=_H_M,
            target_frequency_hz=_TARGET_HZ,
            length_lower_m=0.02,
            length_upper_m=0.04,
            method="not_a_real_method",
        )
