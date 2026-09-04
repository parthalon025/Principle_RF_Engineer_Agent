"""Bayesian optimization via a from-scratch Gaussian Process (GP) surrogate
and Expected Improvement (EI) acquisition function (issue #41).

No machine-learning library (scikit-learn, scikit-optimize, ...) is a
dependency of this project (see pyproject.toml), so this implements the
standard low-dimensional Bayesian-optimization recipe directly on top of
numpy/scipy, which already are:

  1. Fit a GP posterior over the objective from every point evaluated so
     far, using a squared-exponential (RBF) kernel -- the standard GP
     regression formulas (Rasmussen & Williams, "Gaussian Processes for
     Machine Learning", 2006, ch. 2 and 5): the posterior mean/covariance
     via the kernel-matrix/Cholesky formulas in `_gp_posterior` below, and
     the kernel's own length-scale/signal-variance hyperparameters fit by
     maximizing the log marginal likelihood (`_fit_gp_hyperparameters`),
     the standard GP hyperparameter-fitting approach (same reference, ch.
     5).
  2. Propose the next point to evaluate by maximizing Expected Improvement
     (EI) over that posterior -- the standard acquisition function from
     Jones, Schonlau & Welch, "Efficient Global Optimization of Expensive
     Black-Box Functions" (Journal of Global Optimization, 1998), adapted
     here for MINIMIZATION (this package's sign convention -- see
     optimization/base.py): `_expected_improvement` below measures
     improvement as `f_best - mu(x) - xi`, the mirror image of the
     maximization form the 1998 paper states (and of an equivalent
     scikit-optimize-style formula that instead negates the objective).
  3. Evaluate the true objective at that point, add it to the dataset, and
     repeat.

EI itself is maximized (via `scipy.optimize.differential_evolution`, one of
the two approaches this ticket's own design guidance names, chosen over
random-restart local search because EI landscapes are frequently
multimodal -- e.g. one lobe near the current best, another near a
high-uncertainty unexplored region -- which differential_evolution's global
population search handles without having to guess how many restarts is
enough) over the ANALYTICAL EI FORMULA, not the true (expensive) objective,
so this inner search costs nothing in terms of the *true* objective's
evaluation budget -- the count the ticket's grid-search-comparison test
cares about is `n_initial_points + n_iterations`, i.e. exactly how many
times `objective()` itself is called.

See optimization/base.py for the shared Parameter/ObjectiveFunction/
OptimizationResult contract and the minimize-by-convention sign rule every
method in this package follows.
"""

import numpy as np
from scipy.optimize import differential_evolution, minimize
from scipy.stats import norm

from optimization.base import (
    ObjectiveFunction,
    OptimizationResult,
    Parameter,
    best_of,
    record_evaluation,
    validate_parameters,
)

# Small diagonal "nugget" added to every GP kernel matrix for numerical
# stability (a standard GP-regression practice -- Rasmussen & Williams,
# ch. 2.2 and 2.3 -- that also doubles as an assumed-noiseless-observation
# regularizer here): keeps the Cholesky factorization well-conditioned even
# when two evaluated points end up very close together in normalized space.
_JITTER = 1e-6


def _rbf_kernel(
    x1: np.ndarray, x2: np.ndarray, length_scales: np.ndarray, signal_variance: float
) -> np.ndarray:
    """Squared-exponential (RBF) kernel matrix between x1 (n1, d) and x2
    (n2, d), one length scale per dimension:

        k(x, x') = signal_variance * exp(-0.5 * sum_d ((x_d - x'_d) / length_scales_d)^2)
    """
    diff = (x1[:, None, :] - x2[None, :, :]) / length_scales
    sq_dist = np.sum(diff**2, axis=-1)
    return signal_variance * np.exp(-0.5 * sq_dist)


def _neg_log_marginal_likelihood(
    log_hyperparameters: np.ndarray, x_train: np.ndarray, y_train: np.ndarray
) -> float:
    """Negative log marginal likelihood of a zero-mean GP with the given
    (log-transformed, so the optimizer can search an unconstrained space
    while length scale/signal variance stay positive) RBF hyperparameters,
    given training data -- the standard GP model-selection objective
    (Rasmussen & Williams, eq. 5.8)."""
    d = x_train.shape[1]
    length_scales = np.exp(log_hyperparameters[:d])
    signal_variance = np.exp(log_hyperparameters[d])
    k = _rbf_kernel(x_train, x_train, length_scales, signal_variance) + _JITTER * np.eye(
        len(x_train)
    )
    try:
        chol = np.linalg.cholesky(k)
    except np.linalg.LinAlgError:
        return 1e10
    alpha = np.linalg.solve(chol.T, np.linalg.solve(chol, y_train))
    n = len(y_train)
    nll = 0.5 * y_train @ alpha + np.sum(np.log(np.diagonal(chol))) + 0.5 * n * np.log(2 * np.pi)
    return float(nll)


def _fit_gp_hyperparameters(
    x_train: np.ndarray, y_train: np.ndarray, rng: np.random.Generator, n_restarts: int = 2
) -> tuple[np.ndarray, float]:
    """Fit RBF length scales (one per dimension) and signal variance by
    minimizing the negative log marginal likelihood, with a few random
    restarts (log-hyperparameter space is non-convex) to reduce sensitivity
    to the starting point. Bounds keep length scale / signal variance in
    [exp(-3), exp(3)] ~ [0.05, 20], a sensible range given training inputs
    are normalized to [0,1]^d and targets are standardized to unit
    variance (see bayesian_optimize)."""
    d = x_train.shape[1]
    bounds = [(-3.0, 3.0)] * (d + 1)
    best_result = None
    for _ in range(n_restarts):
        x0 = rng.uniform(-1.0, 1.0, size=d + 1)
        result = minimize(
            _neg_log_marginal_likelihood,
            x0,
            args=(x_train, y_train),
            method="L-BFGS-B",
            bounds=bounds,
        )
        if best_result is None or result.fun < best_result.fun:
            best_result = result
    log_hyperparameters = best_result.x
    length_scales = np.exp(log_hyperparameters[:d])
    signal_variance = float(np.exp(log_hyperparameters[d]))
    return length_scales, signal_variance


def _gp_posterior(
    x_train: np.ndarray,
    y_train: np.ndarray,
    x_test: np.ndarray,
    length_scales: np.ndarray,
    signal_variance: float,
) -> tuple[np.ndarray, np.ndarray]:
    """GP posterior mean and standard deviation at x_test, given training
    data and RBF hyperparameters -- the standard GP regression formulas
    (Rasmussen & Williams, eq. 2.22-2.24), via a Cholesky solve rather than
    an explicit matrix inverse for numerical stability."""
    k_train = _rbf_kernel(x_train, x_train, length_scales, signal_variance) + _JITTER * np.eye(
        len(x_train)
    )
    k_star = _rbf_kernel(x_train, x_test, length_scales, signal_variance)
    k_star_star = _rbf_kernel(x_test, x_test, length_scales, signal_variance)

    chol = np.linalg.cholesky(k_train)
    alpha = np.linalg.solve(chol.T, np.linalg.solve(chol, y_train))
    mean = k_star.T @ alpha

    v = np.linalg.solve(chol, k_star)
    covariance = k_star_star - v.T @ v
    variance = np.clip(np.diag(covariance), 1e-12, None)
    return mean, np.sqrt(variance)


def _expected_improvement(
    x_test: np.ndarray,
    x_train: np.ndarray,
    y_train: np.ndarray,
    length_scales: np.ndarray,
    signal_variance: float,
    xi: float,
) -> np.ndarray:
    """Expected Improvement at each row of x_test, for MINIMIZING y_train
    (this package's sign convention -- see optimization/base.py):

        improvement(x) = f_best - mu(x) - xi
        Z(x)  = improvement(x) / sigma(x)        (0 where sigma(x) == 0)
        EI(x) = improvement(x) * Phi(Z(x)) + sigma(x) * phi(Z(x))   (0 where sigma(x) == 0)

    where f_best = min(y_train), mu/sigma are the GP posterior mean/std
    (_gp_posterior), and Phi/phi are the standard normal CDF/PDF. This is
    the Jones/Schonlau/Welch (1998) EI formula mirrored for minimization
    instead of maximization -- see this module's docstring. `xi` (>= 0) is
    the standard EI exploration margin: a larger xi favors exploring more
    uncertain regions over refining the current best."""
    mean, sigma = _gp_posterior(x_train, y_train, x_test, length_scales, signal_variance)
    f_best = np.min(y_train)
    improvement = f_best - mean - xi

    ei = np.zeros_like(improvement)
    explorable = sigma > 1e-9
    z = np.zeros_like(improvement)
    z[explorable] = improvement[explorable] / sigma[explorable]
    ei[explorable] = improvement[explorable] * norm.cdf(z[explorable]) + sigma[
        explorable
    ] * norm.pdf(z[explorable])
    return ei


def bayesian_optimize(
    objective: ObjectiveFunction,
    parameters: list[Parameter],
    n_iterations: int = 20,
    n_initial_points: int = 5,
    xi: float = 0.01,
    random_seed: int | None = None,
    objective_name: str | None = None,
    constraints: dict | None = None,
) -> OptimizationResult:
    """Minimize `objective` over `parameters`' box bounds with a
    from-scratch GP + Expected Improvement Bayesian optimizer.

    Total evaluations of `objective` = `n_initial_points + n_iterations`
    -- exactly (no hidden extra evaluations from e.g. a local-refinement
    step), so this count is directly comparable to grid_search's
    `n_points_per_dim ** len(parameters)`.

    - `n_initial_points`: random-uniform "space-filling" points evaluated
      before the GP has any data to fit (>= 2, so there is at least a pair
      of points to fit a GP to before the first proposal).
    - `n_iterations`: GP-fit + EI-maximize + evaluate cycles run after the
      initial design.
    - `xi`: EI's exploration margin (see `_expected_improvement`); the
      standard default of 0.01 balances exploration/exploitation for a
      target normalized to unit variance internally (see below).
    - `random_seed`: seeds every stochastic step (initial-design sampling,
      GP hyperparameter-fit restarts, and the differential_evolution EI
      maximizer) so a given seed reproduces exactly the same evaluation
      trace -- required for a deterministic test of the "converges in
      fewer evaluations than grid search" claim.

    Internally, parameters are normalized to [0,1]^d (so one length-scale
    prior works regardless of each parameter's own physical units/range)
    and objective values are standardized to zero mean/unit variance before
    every GP fit (both are undone before points/values are recorded in the
    returned OptimizationResult, which is entirely in the caller's original
    units). An "integer" Parameter is still modeled as continuous inside
    the GP -- for the low-dimensional, modest-evaluation-count regime this
    method targets, rounding EI's proposed point to the nearest integer
    (Parameter.clip) before evaluating `objective` is an acceptable
    approximation, not a fully integer-aware GP.

    Returns an OptimizationResult with method="bayesian_optimize",
    `evaluations` in the order they were actually evaluated (initial design
    first, then one per iteration), and best_parameters/best_objective from
    the single best point across the whole trace.
    """
    validate_parameters(parameters)
    if n_initial_points < 2:
        raise ValueError("n_initial_points must be >= 2 (a GP needs at least two points to fit).")
    if n_iterations < 0:
        raise ValueError("n_iterations must be >= 0.")

    rng = np.random.default_rng(random_seed)
    lowers = np.array([p.lower for p in parameters])
    uppers = np.array([p.upper for p in parameters])
    span = uppers - lowers
    d = len(parameters)

    def to_point(x_raw: np.ndarray) -> dict[str, float]:
        return {p.name: p.clip(v) for p, v in zip(parameters, x_raw, strict=True)}

    def normalize(point: dict[str, float]) -> np.ndarray:
        raw = np.array([point[p.name] for p in parameters])
        return (raw - lowers) / span

    evaluations: list[dict] = []
    x_normalized: list[np.ndarray] = []
    y_values: list[float] = []

    initial_design = rng.uniform(0.0, 1.0, size=(n_initial_points, d))
    for x_norm in initial_design:
        x_raw = lowers + x_norm * span
        point = to_point(x_raw)
        objective_value = objective(point)
        record_evaluation(evaluations, point, objective_value)
        x_normalized.append(normalize(point))
        y_values.append(objective_value)

    x_train = np.array(x_normalized)
    y_train = np.array(y_values)

    for _ in range(n_iterations):
        y_mean, y_std = float(np.mean(y_train)), float(np.std(y_train))
        if y_std < 1e-12:
            y_std = 1.0
        y_standardized = (y_train - y_mean) / y_std

        length_scales, signal_variance = _fit_gp_hyperparameters(x_train, y_standardized, rng)

        def neg_ei(
            x_norm: np.ndarray,
            _x_train=x_train,
            _y_standardized=y_standardized,
            _length_scales=length_scales,
            _signal_variance=signal_variance,
        ) -> float:
            x_row = np.clip(x_norm, 0.0, 1.0).reshape(1, -1)
            ei = _expected_improvement(
                x_row, _x_train, _y_standardized, _length_scales, _signal_variance, xi
            )
            return float(-ei[0])

        proposal = differential_evolution(
            neg_ei,
            bounds=[(0.0, 1.0)] * d,
            seed=int(rng.integers(0, 2**31 - 1)),
            maxiter=100,
            popsize=15,
            tol=1e-8,
            polish=True,
        )

        x_next_raw = lowers + np.clip(proposal.x, 0.0, 1.0) * span
        point = to_point(x_next_raw)
        objective_value = objective(point)
        record_evaluation(evaluations, point, objective_value)

        x_train = np.vstack([x_train, normalize(point)])
        y_train = np.append(y_train, objective_value)

    best_parameters, best_objective = best_of(evaluations)
    return OptimizationResult(
        method="bayesian_optimize",
        best_parameters=best_parameters,
        best_objective=best_objective,
        evaluations=evaluations,
        parameters=list(parameters),
        objective_name=objective_name,
        constraints=constraints,
    )
