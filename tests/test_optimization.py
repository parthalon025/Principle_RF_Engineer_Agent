"""Tests for the optimization package (issue #41): the shared Parameter/
OptimizationResult interface, parameter_sweep, grid_search, and
bayesian_optimize, all exercised against synthetic objective functions with
a known closed-form optimum.

Every method in optimization/ MINIMIZES its objective by convention (see
optimization/base.py), so every synthetic objective below is a "bowl" (or
bowl-plus-ripple) shape with a known minimum, not a function to maximize.

Also covers optimization/combinatorial.py (issue #255): a categorical
symbol-placement search, exercised entirely against hand-built fake
candidate data since no real Element/Coding-Alphabet library exists yet
(issue #256) -- see that section below for details.
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
from optimization.combinatorial import (
    EmptyCandidateShelfError,
    SymbolOption,
    combinatorial_symbol_placement,
)
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
        bayesian_optimize(quadratic_bowl_1d, [Parameter("x", 0.0, 1.0)], n_initial_points=1)


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


# ---------------------------------------------------------------------------
# optimization/combinatorial.py (issue #255): a categorical "which
# already-characterised symbol goes in which grid position" search over a
# caller-supplied FAKE candidate-symbol set, exercised entirely with
# hand-built synthetic data -- no real Element/Coding-Alphabet library exists
# in this tree yet (issue #256), and this module's own contract
# (optimization/combinatorial.py's module docstring) is that it never
# assumes one does.
#
# Every test below builds its own small `candidates` dict by hand, standing
# in for what a real alphabet-library lookup would eventually supply -- the
# same role the stub `symbol_library` dict plays in
# tests/test_geometry_unit_cell.py's own generate_coded_unit_cell_array
# tests. The one cross-check test at the bottom confirms the returned
# `layout` really is that function's own `layout` argument, unmodified --
# it importorskip-guards gdstk INSIDE the test function (not at module
# level, unlike tests/test_geometry_unit_cell.py's own module-wide guard)
# so a missing optional extra skips only that one test, not this whole file.
# ---------------------------------------------------------------------------


def _exact_match_candidates() -> dict[tuple[int, int], list[SymbolOption]]:
    """A 2x1 grid (2 columns, 1 row) where every position has a candidate
    that exactly matches its target -- the "near-zero achieved error"
    case."""
    return {
        (0, 0): [
            SymbolOption(symbol_id="A_far", achieved_value=170.0),
            SymbolOption(symbol_id="A_exact", achieved_value=0.0),
        ],
        (1, 0): [
            SymbolOption(symbol_id="B_far", achieved_value=-160.0),
            SymbolOption(symbol_id="B_exact", achieved_value=10.0),
        ],
    }


_EXACT_MATCH_TARGET = [[0.0, 10.0]]  # target[j][i], one row (j=0), two columns


def test_combinatorial_symbol_placement_finds_exact_match_with_near_zero_error():
    result = combinatorial_symbol_placement(
        target=_EXACT_MATCH_TARGET,
        candidates=_exact_match_candidates(),
        delta_phi_max_deg=12.0,
        random_seed=1,
    )

    assert result.layout == [["A_exact", "B_exact"]]
    assert result.achieved_error == pytest.approx(0.0, abs=1e-9)
    assert result.provenance == "CALCULATED"
    assert result.method == "combinatorial_symbol_placement"
    assert result.warnings == []


def test_combinatorial_symbol_placement_records_full_evaluation_trace():
    result = combinatorial_symbol_placement(
        target=_EXACT_MATCH_TARGET,
        candidates=_exact_match_candidates(),
        delta_phi_max_deg=12.0,
        random_seed=1,
    )

    # More than just the winner: differential_evolution's population-based
    # search evaluates many candidate placements per generation (see
    # optimization/genetic.py) -- the trace must carry all of them, each
    # tagged with its own achieved error, not just the best one.
    assert len(result.evaluations) > 1
    for entry in result.evaluations:
        assert set(entry) == {"layout", "error", "feasible"}
        assert entry["layout"][0][0] in ("A_far", "A_exact")
        assert entry["layout"][0][1] in ("B_far", "B_exact")
        assert isinstance(entry["error"], float)
        assert isinstance(entry["feasible"], bool)
    # The winning layout must actually appear somewhere in its own trace.
    assert any(e["layout"] == result.layout for e in result.evaluations)


def test_combinatorial_symbol_placement_is_deterministic_given_a_seed():
    result_a = combinatorial_symbol_placement(
        target=_EXACT_MATCH_TARGET,
        candidates=_exact_match_candidates(),
        delta_phi_max_deg=12.0,
        random_seed=7,
    )
    result_b = combinatorial_symbol_placement(
        target=_EXACT_MATCH_TARGET,
        candidates=_exact_match_candidates(),
        delta_phi_max_deg=12.0,
        random_seed=7,
    )

    assert result_a.layout == result_b.layout
    assert result_a.achieved_error == result_b.achieved_error
    assert result_a.evaluations == result_b.evaluations


def test_combinatorial_symbol_placement_thin_shelf_warns_but_still_places():
    """A position with exactly one candidate has no choice at all -- the
    search must still place it (never skip or crash), but must say so."""
    candidates = {
        (0, 0): [SymbolOption(symbol_id="ONLY_A", achieved_value=5.0)],
        (1, 0): [
            SymbolOption(symbol_id="B_far", achieved_value=-160.0),
            SymbolOption(symbol_id="B_exact", achieved_value=10.0),
        ],
    }

    result = combinatorial_symbol_placement(
        target=_EXACT_MATCH_TARGET,
        candidates=candidates,
        delta_phi_max_deg=12.0,
        random_seed=1,
    )

    assert result.layout[0][0] == "ONLY_A"  # the only option, forced
    assert result.layout[0][1] == "B_exact"  # still searched and found
    assert len(result.warnings) == 1
    assert "i=0, j=0" in result.warnings[0]
    assert "one candidate" in result.warnings[0]


def test_combinatorial_symbol_placement_all_positions_thin_shelf_needs_no_search():
    """Every position pinned to a single candidate: nothing left to search,
    but the placement is still built, scored, and returned -- not skipped."""
    candidates = {
        (0, 0): [SymbolOption(symbol_id="ONLY_A", achieved_value=5.0)],
        (1, 0): [SymbolOption(symbol_id="ONLY_B", achieved_value=8.0)],
    }

    result = combinatorial_symbol_placement(
        target=_EXACT_MATCH_TARGET,
        candidates=candidates,
        delta_phi_max_deg=12.0,
        random_seed=1,
    )

    assert result.layout == [["ONLY_A", "ONLY_B"]]
    assert len(result.evaluations) == 1
    assert len(result.warnings) == 2


def test_combinatorial_symbol_placement_empty_shelf_raises_clear_error():
    """A position with ZERO candidates cannot be placed at all -- this must
    fail loudly and name the position, mirroring
    geometry.unit_cell.SymbolNotFoundError's "no plausible substitute, so
    refuse and name the gap" reasoning, not silently skip or crash."""
    candidates = {
        (0, 0): [SymbolOption(symbol_id="A_exact", achieved_value=0.0)],
        (1, 0): [],  # nothing characterised for this position yet
    }

    with pytest.raises(EmptyCandidateShelfError, match=r"\(1, 0\)"):
        combinatorial_symbol_placement(
            target=_EXACT_MATCH_TARGET,
            candidates=candidates,
            delta_phi_max_deg=12.0,
            random_seed=1,
        )


def test_combinatorial_symbol_placement_missing_position_key_treated_as_empty_shelf():
    """A position absent from `candidates` entirely is the same "nothing
    available here" situation as an explicit empty list -- both must raise
    the same clear error, not a silent default or a KeyError."""
    candidates = {(0, 0): [SymbolOption(symbol_id="A_exact", achieved_value=0.0)]}
    # (1, 0) is missing entirely.

    with pytest.raises(EmptyCandidateShelfError, match=r"\(1, 0\)"):
        combinatorial_symbol_placement(
            target=_EXACT_MATCH_TARGET,
            candidates=candidates,
            delta_phi_max_deg=12.0,
            random_seed=1,
        )


def test_combinatorial_symbol_placement_respects_delta_phi_max_budget():
    """A 1x2 grid (1 column, 2 rows) where the raw-lowest-error combination
    (error 0.0, both symbols hit their target exactly) puts two symbols 40
    degrees apart as vertical (E-plane) neighbours -- violating a
    12-degree Delta_phi_max budget -- while the best FEASIBLE combination
    scores a strictly higher raw error. The budget-respecting combination
    must win, even though it does not have the lowest raw error overall
    (User Story 7 / Testing Decisions).

    All four combinations, worked out by hand (mean absolute error over
    the 2 positions; neighbour gap = |top - bottom|):
      TOP_EXACT(0)+BOT_FAR(40):   error 0.0,  gap 40 -> INFEASIBLE (best raw error)
      TOP_EXACT(0)+BOT_CLOSE(5):  error 17.5, gap 5  -> feasible (best FEASIBLE)
      TOP_CLOSE(3)+BOT_FAR(40):   error 1.5,  gap 37 -> INFEASIBLE
      TOP_CLOSE(3)+BOT_CLOSE(5):  error 19.0, gap 2  -> feasible
    """
    candidates = {
        (0, 0): [
            SymbolOption(symbol_id="TOP_EXACT", achieved_value=0.0),
            SymbolOption(symbol_id="TOP_CLOSE", achieved_value=3.0),
        ],
        (0, 1): [
            SymbolOption(symbol_id="BOT_FAR", achieved_value=40.0),
            SymbolOption(symbol_id="BOT_CLOSE", achieved_value=5.0),
        ],
    }
    target = [[0.0], [40.0]]  # target[j][i]: row 0 wants 0 deg, row 1 wants 40 deg

    result = combinatorial_symbol_placement(
        target=target,
        candidates=candidates,
        delta_phi_max_deg=12.0,
        random_seed=3,
    )

    # TOP_EXACT + BOT_FAR scores the lowest raw error (0.0) of all four
    # combinations but violates the 12-degree budget (40-degree neighbour
    # gap); it must never win, even though nothing else beats its raw error.
    assert result.layout != [["TOP_EXACT"], ["BOT_FAR"]]
    assert result.layout == [["TOP_EXACT"], ["BOT_CLOSE"]]
    assert result.achieved_error == pytest.approx(17.5)
    # The winning placement's own trace entry must be marked feasible.
    winner_entries = [e for e in result.evaluations if e["layout"] == result.layout]
    assert winner_entries and all(e["feasible"] for e in winner_entries)
    # And the infeasible, lower-raw-error combination must still show up in
    # the trace, tagged infeasible -- evaluated, not hidden.
    violating_entries = [
        e for e in result.evaluations if e["layout"] == [["TOP_EXACT"], ["BOT_FAR"]]
    ]
    assert violating_entries and all(not e["feasible"] for e in violating_entries)


def test_combinatorial_symbol_placement_rejects_ragged_target():
    with pytest.raises(ValueError, match="rectangular"):
        combinatorial_symbol_placement(
            target=[[0.0, 10.0], [5.0]],
            candidates=_exact_match_candidates(),
            delta_phi_max_deg=12.0,
            random_seed=1,
        )


def test_combinatorial_symbol_placement_rejects_empty_target():
    with pytest.raises(ValueError):
        combinatorial_symbol_placement(
            target=[],
            candidates={},
            delta_phi_max_deg=12.0,
            random_seed=1,
        )


def test_combinatorial_symbol_placement_tags_target_and_candidate_snapshot():
    result = combinatorial_symbol_placement(
        target=_EXACT_MATCH_TARGET,
        candidates=_exact_match_candidates(),
        delta_phi_max_deg=12.0,
        random_seed=1,
        objective_name="reflection_phase_placement",
    )

    assert result.target == _EXACT_MATCH_TARGET
    assert result.objective_name == "reflection_phase_placement"
    assert result.delta_phi_max_deg == 12.0
    assert result.random_seed == 1
    assert set(result.candidate_snapshot) == {(0, 0), (1, 0)}
    assert result.candidate_snapshot[(0, 0)] == _exact_match_candidates()[(0, 0)]
    # A snapshot, not a live reference -- mutating the caller's dict
    # afterward must not change what the result already recorded.
    fresh_candidates = _exact_match_candidates()
    fresh_candidates[(0, 0)].append(SymbolOption(symbol_id="NEW", achieved_value=999.0))
    result2 = combinatorial_symbol_placement(
        target=_EXACT_MATCH_TARGET,
        candidates=fresh_candidates,
        delta_phi_max_deg=12.0,
        random_seed=1,
    )
    fresh_candidates[(0, 0)].append(SymbolOption(symbol_id="EVEN_NEWER", achieved_value=1.0))
    assert len(result2.candidate_snapshot[(0, 0)]) == 3  # unaffected by the later append


# ---------------------------------------------------------------------------
# Issue #400: SymbolOption.entry_id / CombinatorialPlacementResult.
# entry_id_layout -- a bare symbol_id in `layout` cannot say WHICH measured
# symbol_alphabet_entries row (and therefore which process/machine/ink)
# backed a cell, because several entries can share one symbol/band/
# incidence-angle-range/process (ADR-0027 point 4's "two runs are still two
# distinct rows" rule). `entry_id_layout` is the same [j][i] grid as
# `layout`, but naming the winning entry_id at each cell instead.
# ---------------------------------------------------------------------------


def test_symbol_option_entry_id_defaults_to_none():
    """A hand-built option (every fixture above) has no backing database
    row -- `entry_id` must default to `None`, not force every existing
    caller to start passing one."""
    option = SymbolOption(symbol_id="A_exact", achieved_value=0.0)
    assert option.entry_id is None


def test_combinatorial_symbol_placement_entry_id_layout_matches_the_winning_choice():
    """The all-thin-shelf path (no genetic_optimize search at all -- see
    module docstring): entry_id_layout must report exactly the entry_id
    each pinned SymbolOption carried, in the SAME [j][i] shape as layout."""
    candidates = {
        (0, 0): [SymbolOption(symbol_id="ONLY_A", achieved_value=5.0, entry_id=101)],
        (1, 0): [SymbolOption(symbol_id="ONLY_B", achieved_value=8.0, entry_id=202)],
    }

    result = combinatorial_symbol_placement(
        target=_EXACT_MATCH_TARGET,
        candidates=candidates,
        delta_phi_max_deg=12.0,
        random_seed=1,
    )

    assert result.layout == [["ONLY_A", "ONLY_B"]]
    assert result.entry_id_layout == [[101, 202]]


def test_combinatorial_symbol_placement_entry_id_layout_disambiguates_same_symbol_id():
    """Two measured entries sharing the SAME symbol id (e.g. two separate
    print runs under the same process -- ADR-0027's own "still two distinct
    rows" rule) must still be told apart in entry_id_layout, even though
    `layout` alone reports the identical symbol id either way. Exercises
    the genetic_optimize search path (position (0, 0) has two candidates
    to choose between), not just the thin-shelf shortcut above."""
    candidates = {
        (0, 0): [
            SymbolOption(symbol_id="A", achieved_value=170.0, entry_id=11),
            SymbolOption(symbol_id="A", achieved_value=0.0, entry_id=12),
        ],
        (1, 0): [SymbolOption(symbol_id="B", achieved_value=10.0, entry_id=21)],
    }

    result = combinatorial_symbol_placement(
        target=_EXACT_MATCH_TARGET,  # target[j][i] == [[0.0, 10.0]]
        candidates=candidates,
        delta_phi_max_deg=12.0,
        random_seed=1,
    )

    assert result.layout == [["A", "B"]]
    # entry_id=12 (achieved_value=0.0) is the exact match; entry_id=11
    # (achieved_value=170.0, a 160-degree gap from B) is both a worse raw
    # error AND infeasible against the 12-degree budget -- entry_id_layout
    # must name the winner, not merely "some entry named A".
    assert result.entry_id_layout == [[12, 21]]


def test_combinatorial_symbol_placement_layout_feeds_generate_coded_unit_cell_array():
    """Cross-check: the returned layout is directly usable as
    generate_coded_unit_cell_array's own `layout` argument, per this
    module's whole reason for matching that function's shape (issue #255
    User Story 16). Skipped (not failed) when gdstk isn't installed --
    guarded inside this one test, not at module level, so the rest of this
    file still runs without the optional geometry extra."""
    pytest.importorskip(
        "gdstk", reason="gdstk not installed -- run `uv sync --extra geometry` first"
    )
    from geometry.unit_cell import generate_coded_unit_cell_array

    result = combinatorial_symbol_placement(
        target=_EXACT_MATCH_TARGET,
        candidates=_exact_match_candidates(),
        delta_phi_max_deg=12.0,
        random_seed=1,
    )

    # Real unit-cell primitive geometry, keyed by the same symbol ids this
    # module's own placement chose -- standing in for a real
    # Element/Coding-Alphabet library lookup (#256), same as
    # tests/test_geometry_unit_cell.py's own hand-built symbol_library.
    symbol_library = {
        "A_exact": {"shape": "box", "p1_m": [0.0, 0.0, 0.0], "p2_m": [0.005, 0.005, 0.001]},
        "B_exact": {"shape": "box", "p1_m": [0.0, 0.0, 0.0], "p2_m": [0.006, 0.004, 0.001]},
    }

    primitives = generate_coded_unit_cell_array(
        result.layout,
        symbol_library,
        pitch_m=(0.015, 0.015),
        delta_phi_max_deg=12.0,
        rcsr_db=10.0,
        wavelength_m=0.03,
        panel_size_m=(0.18, 0.18),
        name_prefix="block",
    )

    assert len(primitives) > 0
    assert all(p["shape"] == "box" for p in primitives)
