"""Tests for rf_tools/aperture_polarizability.py (issue #547).

`rf_tools.physical_bounds.perforated_screen_min_polarizability_m3` and
`perforated_screen_max_wavelength_fractional_bandwidth` (#483) need `gamma`,
a `BANDPASS_FSS` candidate's static polarizability, as an input -- nothing
computed it from geometry. This module closes that gap for the family's own
proposed shape, a square-loop slot, by computing the electric polarizability
of the isolated, Babinet-complementary square-loop PATCH.

As with tests/test_physical_bounds.py, the tests that matter most are the
ones that reproduce a number someone else published -- never a value read
back from this module's own prior output. The solid-square-plate limit
(`w_m == b_m / 2`) is the one point on this shape's curve with an independent
published value: Mansfield, Douglas & Garboczi, "Intrinsic viscosity and the
electrical polarizability of arbitrarily shaped objects," Phys. Rev. E
64:061401 (2001), Table IV, n=4 row: `(alpha_e)_xx / r^3 = 2.943(1)` with
`r` the polygon's centre-to-vertex distance -- for a square, `r = b/sqrt(2)`,
so `gamma/b^3 = 2.943 / 2*sqrt(2) = 1.0405 +/- 0.0004`.
"""

import math

import numpy as np
import pytest
from scipy.integrate import quad
from scipy.special import ellipe, ellipkm1

from rf_tools.aperture_polarizability import (
    _graded_nodes_1d,
    _quarter_loop_mesh,
    _rect_cells,
    _rect_potential_from_corners,
    _solve_alpha_xx,
    periodic_array_correction_is_reliable,
    periodic_array_polarizability_correction_m3,
    square_loop_periodic_array_polarizability_m3,
    square_loop_polarizability_m3,
)
from rf_tools.physical_bounds import perforated_screen_max_wavelength_fractional_bandwidth

# Mansfield, Douglas & Garboczi (2001), Table IV, n=4 (square), converted
# from their r^3 (r = centre-to-vertex) normalisation to this module's b^3
# (b = outer side) normalisation: r = b/sqrt(2), so gamma/b^3 = (alpha/r^3) / (2*sqrt(2)).
_MANSFIELD_SQUARE_ALPHA_OVER_R3 = 2.943
_MANSFIELD_SQUARE_ALPHA_OVER_R3_UNCERTAINTY = 0.001
_MANSFIELD_SQUARE_GAMMA_OVER_B3 = _MANSFIELD_SQUARE_ALPHA_OVER_R3 / (2 * math.sqrt(2))
_MANSFIELD_SQUARE_GAMMA_OVER_B3_UNCERTAINTY = _MANSFIELD_SQUARE_ALPHA_OVER_R3_UNCERTAINTY / (
    2 * math.sqrt(2)
)


def test_rejects_non_positive_or_nonsensical_geometry():
    with pytest.raises(ValueError):
        square_loop_polarizability_m3(b_m=0.0, w_m=0.001)
    with pytest.raises(ValueError):
        square_loop_polarizability_m3(b_m=-0.009, w_m=0.001)
    with pytest.raises(ValueError):
        square_loop_polarizability_m3(b_m=0.009, w_m=0.0)
    with pytest.raises(ValueError):
        square_loop_polarizability_m3(b_m=0.009, w_m=-0.0002)
    # A gap this wide would enclose a negative-area hole -- the loop has
    # already become (more than) a solid square.
    with pytest.raises(ValueError):
        square_loop_polarizability_m3(b_m=0.009, w_m=0.0046)


def test_matches_mansfield_et_al_at_the_solid_square_plate_limit():
    """w_m == b_m/2 leaves no hole at all -- the loop degenerates to a solid
    square patch, the one point on this shape's curve with an independent
    published value (see module docstring). `b_m` is chosen as 1.0 so the
    returned value is directly `gamma/b^3`, matching Mansfield et al.'s own
    normalisation once converted from their r^3 (module docstring)."""
    b_m = 1.0
    gamma_over_b3 = square_loop_polarizability_m3(b_m=b_m, w_m=b_m / 2)
    assert gamma_over_b3 == pytest.approx(
        _MANSFIELD_SQUARE_GAMMA_OVER_B3, abs=3 * _MANSFIELD_SQUARE_GAMMA_OVER_B3_UNCERTAINTY
    )


def test_polarizability_increases_with_strip_width_and_never_exceeds_solid_plate():
    """Ludvig-Osipov et al. 2020 Sec. IV, on the polarizability of an
    enclosed vs. an enclosing object: "the polarizability of an enclosed
    object cannot exceed the polarizability of an enclosing object... Thus,
    the polarizability of the square patches is the upper bound for the
    enclosed designs." A wider strip (smaller hole) is a strictly *more*
    enclosing shape at the same outer side `b_m`, so `gamma` must increase
    strictly with `w_m` and stay strictly below the solid-square-plate value
    at every `w_m < b_m / 2`."""
    b_m = 1.0
    solid_plate = square_loop_polarizability_m3(b_m=b_m, w_m=b_m / 2)
    values = [
        square_loop_polarizability_m3(b_m=b_m, w_m=w_m) for w_m in (0.02, 0.05, 0.1, 0.2, 0.3, 0.45)
    ]
    assert values == sorted(values)
    assert len(set(values)) == len(values)
    assert all(value < solid_plate for value in values)


# Isotropy-check-only machinery. Deliberately NOT part of
# rf_tools/aperture_polarizability.py's production surface (it is never
# called by either public function, only by the test below): a full-domain
# solve with an explicit floating-potential unknown and no quadrant symmetry
# assumed, so agreement with the production quadrant-symmetry-reduced solve
# is real evidence of isotropy, not an artefact of shared code. Reuses only
# `_rect_potential_from_corners` (the one place the module turns a
# rectangle's corners into a potential) -- everything about how the mesh is
# assembled into a linear system here is independent of `_solve_alpha_xx`.
def _reflect_quarter_mesh_to_full_domain(quarter_cells: np.ndarray) -> np.ndarray:
    x0, x1, y0, y1 = (quarter_cells[:, i] for i in range(4))
    quadrant_2 = np.column_stack([-x1, -x0, y0, y1])
    quadrant_3 = np.column_stack([-x1, -x0, -y1, -y0])
    quadrant_4 = np.column_stack([x0, x1, -y1, -y0])
    return np.vstack([quarter_cells, quadrant_2, quadrant_3, quadrant_4])


def _solve_alpha_full_domain(cells: np.ndarray, field_angle_rad: float) -> float:
    xc = 0.5 * (cells[:, 0] + cells[:, 1])
    yc = 0.5 * (cells[:, 2] + cells[:, 3])
    area = (cells[:, 1] - cells[:, 0]) * (cells[:, 3] - cells[:, 2])
    n = len(cells)
    x0, x1, y0, y1 = cells[:, 0], cells[:, 1], cells[:, 2], cells[:, 3]
    k = _rect_potential_from_corners(
        xc[:, None], yc[:, None], x0[None, :], x1[None, :], y0[None, :], y1[None, :]
    )
    # Unknowns: sigma_j (n of them) plus one floating-potential constant.
    # Equations: total potential zero on the conductor (n rows) plus overall
    # charge neutrality (1 row), since nothing grounds an isolated conductor.
    system = np.zeros((n + 1, n + 1))
    rhs = np.zeros(n + 1)
    system[:n, :n] = k
    system[:n, n] = 1.0
    system[n, :n] = area
    ex, ey = math.cos(field_angle_rad), math.sin(field_angle_rad)
    rhs[:n] = ex * xc + ey * yc
    solution = np.linalg.solve(system, rhs)
    sigma = solution[:n]
    dipole_x = np.sum(sigma * area * xc)
    dipole_y = np.sum(sigma * area * yc)
    return float(ex * dipole_x + ey * dipole_y)


@pytest.mark.parametrize("w_over_b", [0.02, 0.1, 0.45])
def test_in_plane_response_is_isotropic(w_over_b):
    """A square loop is invariant under a 90-degree rotation, which forces
    its in-plane polarizability tensor to be isotropic (gamma_xx = gamma_yy,
    gamma_xy = 0): a 90-degree rotation R maps the loop onto itself, so
    R gamma R^T = gamma, and for R = [[0,-1],[1,0]] that identity gives
    gamma_yy = gamma_xx and gamma_xy = -gamma_xy, i.e. gamma_xy = 0. This
    checks that identity holds for the actual numerical solve -- not just
    the shape -- using a full-domain solve with an explicit floating-
    potential unknown and no quadrant symmetry assumed
    (`_solve_alpha_full_domain` above), a genuinely different linear system
    from the production solve (`_solve_alpha_xx`) it is checking. A small
    mesh resolution is enough: isotropy is an exact symmetry of any mesh
    built by reflecting one quarter into the other three (as both solves
    here do), not a convergence property, so it should hold to near machine
    precision regardless of resolution (confirmed during this feature's own
    research at n_w = 8-12; module docstring)."""
    n_w = 8
    quarter_cells = _quarter_loop_mesh(b_half=0.5, w=0.5 * w_over_b, n_w=n_w)
    alpha_xx_reduced = _solve_alpha_xx(quarter_cells)

    full_cells = _reflect_quarter_mesh_to_full_domain(quarter_cells)
    alpha_axis_aligned = _solve_alpha_full_domain(full_cells, field_angle_rad=0.0)
    alpha_diagonal = _solve_alpha_full_domain(full_cells, field_angle_rad=math.pi / 4)

    assert alpha_axis_aligned == pytest.approx(alpha_xx_reduced, rel=1e-9)
    assert alpha_diagonal == pytest.approx(alpha_xx_reduced, rel=1e-9)


def test_result_is_stable_across_two_internal_mesh_resolutions():
    """Guards against a future change silently coarsening the mesh: the
    boundary-element solve is a convergent numerical method (empirically
    second-order in the mesh spacing across the strip width -- this
    feature's own research, module docstring), so the value at the
    production resolution (`square_loop_polarizability_m3`, `n_w = 40`) and
    at a visibly coarser one must already agree to a modest tolerance, not
    just to each other's own noise floor."""
    b_m, w_m = 1.0, 0.05
    production_value = square_loop_polarizability_m3(b_m=b_m, w_m=w_m)
    coarse_cells = _quarter_loop_mesh(b_half=0.5, w=w_m / b_m, n_w=16)
    coarse_value = _solve_alpha_xx(coarse_cells) * b_m**3
    assert coarse_value == pytest.approx(production_value, rel=5e-3)


# Ludvig-Osipov et al. 2020, Fig. 4, "Square patch" curve: normalised
# per-unit-cell polarizability gamma_cell/l^3 of a periodic array of SOLID
# square patches (outer side a, period l) vs. normalised spacing
# (l - a)/l, read directly off the rendered figure
# (docs/bandpass-fss-physical-bound-primary-source.md; this feature's own
# research). Used here -- rather than a square-LOOP reading, which the paper
# does not provide -- because it isolates the periodic-array correction from
# the loop calculation: the isolated value it must be corrected from,
# 1.0404 (a/l)^3, is anchored on the same Mansfield et al. figure this
# module's solid-plate test already reproduces. Reading uncertainty grows
# toward the top of the plot, where there is no gridline above 1 to read
# against; the tightest-spacing point also sits where a first-order
# point-dipole correction is expected to under-predict most (module
# docstring).
_LUDVIG_OSIPOV_FIG4_SQUARE_PATCH = [
    # (l - a)/l, read gamma_cell/l^3, absolute tolerance
    #
    # The tightest-spacing point's tolerance is widened beyond its own
    # reading uncertainty to also cover the first-order correction's
    # documented under-prediction there (module docstring): this feature's
    # own research found the correction ~14% low at this exact spacing
    # (period/outer-side = 1.10), a real, expected property of a point-
    # dipole model at near-touching separation, not a bug to chase.
    (0.09, 1.27, 0.20),
    (0.32, 0.36, 0.04),
    (0.56, 0.09, 0.02),
]


@pytest.mark.parametrize("spacing_fraction,read_value,tolerance", _LUDVIG_OSIPOV_FIG4_SQUARE_PATCH)
def test_periodic_array_correction_tracks_ludvig_osipov_fig4_square_patch_curve(
    spacing_fraction, read_value, tolerance
):
    period_m = 1.0
    a_m = period_m * (1.0 - spacing_fraction)
    corrected = square_loop_periodic_array_polarizability_m3(
        b_m=a_m, w_m=a_m / 2, period_m=period_m
    )
    assert corrected == pytest.approx(read_value, abs=tolerance)


def test_periodic_array_correction_exceeds_isolated_value():
    """Neighbouring loops only ever raise gamma above the isolated value
    (the lattice sum is positive -- Ludvig-Osipov et al. 2020's own
    monotonic-growth-with-packing statement, Fig. 4)."""
    b_m, w_m, period_m = 0.009, 0.0002, 0.010
    isolated = square_loop_polarizability_m3(b_m=b_m, w_m=w_m)
    corrected = square_loop_periodic_array_polarizability_m3(b_m=b_m, w_m=w_m, period_m=period_m)
    assert corrected > isolated


def test_periodic_array_correction_rejects_overlapping_geometry():
    with pytest.raises(ValueError):
        # period_m < b_m: adjacent loops would physically overlap.
        square_loop_periodic_array_polarizability_m3(b_m=0.009, w_m=0.001, period_m=0.008)


def test_periodic_array_correction_stays_finite_even_at_the_touching_limit():
    """The correction's denominator never reaches zero for this shape over
    its whole valid domain (module docstring: gamma is bounded above by the
    solid-plate value, and period_m can't be smaller than b_m), so even the
    worst case -- a solid plate (w_m = b_m/2) at the smallest legal period
    (period_m == b_m, loops touching) -- must return a finite, positive
    number rather than raise or blow up."""
    corrected = square_loop_periodic_array_polarizability_m3(b_m=1.0, w_m=0.5, period_m=1.0)
    assert math.isfinite(corrected)
    assert corrected > 0


def test_periodic_array_correction_is_reliable_threshold():
    """Matches the reliability threshold this module's own docstring and
    test above cite (period/b_m >= 1.4, Ludvig-Osipov et al. Fig. 4)."""
    assert periodic_array_correction_is_reliable(patch_size_m=1.0, period_m=1.4) is True
    assert periodic_array_correction_is_reliable(patch_size_m=1.0, period_m=1.39) is False


def test_shape_agnostic_correction_matches_the_square_loop_convenience_wrapper():
    """`square_loop_periodic_array_polarizability_m3` is documented as a
    convenience wrapper: computing the isolated value by hand and passing it
    to the shape-agnostic `periodic_array_polarizability_correction_m3`
    (issue #547's Implementation Decisions: the correction should take "the
    isolated value... or the same geometry inputs") must give the identical
    number."""
    b_m, w_m, period_m = 0.009, 0.0002, 0.010
    via_wrapper = square_loop_periodic_array_polarizability_m3(b_m=b_m, w_m=w_m, period_m=period_m)
    isolated = square_loop_polarizability_m3(b_m=b_m, w_m=w_m)
    via_shape_agnostic = periodic_array_polarizability_correction_m3(
        isolated_gamma_m3=isolated, period_m=period_m
    )
    assert via_wrapper == via_shape_agnostic


def test_shape_agnostic_correction_rejects_nonsensical_input():
    with pytest.raises(ValueError):
        periodic_array_polarizability_correction_m3(isolated_gamma_m3=0.0, period_m=0.01)
    with pytest.raises(ValueError):
        periodic_array_polarizability_correction_m3(isolated_gamma_m3=-1e-9, period_m=0.01)
    with pytest.raises(ValueError):
        periodic_array_polarizability_correction_m3(isolated_gamma_m3=1e-9, period_m=0.0)


# ---------------------------------------------------------------------------
# Cross-check on the DISCRETISATION STRATEGY (piecewise-constant charge,
# edge-graded toward every singular edge, centre collocation) against the one
# other loop-shaped, doubly-edged conductor with a published static
# polarizability: Kurennoy, S. S., "Polarizabilities of an annular cut in the
# wall of an arbitrary thickness," IEEE Trans. MTT 44(7):1109-1114 (1996),
# read from arXiv:acc-phys/9510002. This is deliberately an INDEPENDENT
# solver (1-D in radius, using the exact cos(phi) Fourier component of the
# Coulomb kernel for a circular geometry) rather than a reuse of
# rf_tools/aperture_polarizability.py's rectangle-kernel machinery, which
# cannot represent a curved boundary -- so agreement here checks the general
# approach (piecewise-constant collocation with edge grading resolves a
# 1/sqrt(distance) charge singularity correctly), not this module's own code.
# Per the module's own out-of-scope note, no circular shape is added to the
# production module itself; this lives only in the test suite.
#
# Kurennoy's own convention (Eq. 1) is one-sided (his psi for a full circular
# hole is 8b^3/3); the full-space value needed here is 2*psi (settled via the
# disk, 16b^3/3, and confirmed against Mansfield et al. 2001's disk row in
# this feature's own research -- module docstring).
def _annulus_kernel_cos_phi_component(r: np.ndarray, r_prime: np.ndarray) -> np.ndarray:
    """The cos(phi) Fourier component of 1/|r - r'| on a circle:
    `K1(r, r') = (4 / (k*sqrt(r*r'))) * [(1 - k^2/2)*K(k) - E(k)]`,
    `k^2 = 4*r*r'/(r + r')^2`. Computed via `1 - k^2 = ((r-r')/(r+r'))^2`
    and `ellipkm1`, which stay accurate as `r' -> r` (`k -> 1`) where a
    naive `ellipk(k**2)` loses precision.
    """
    one_minus_m = ((r - r_prime) / (r + r_prime)) ** 2
    m = 1.0 - one_minus_m
    k = np.sqrt(m)
    complete_elliptic_terms = (1.0 - 0.5 * m) * ellipkm1(one_minus_m) - ellipe(m)
    return (4.0 / (k * np.sqrt(r * r_prime))) * complete_elliptic_terms


def test_annulus_kernel_matches_direct_quadrature():
    """Confirms the closed-form Fourier-component kernel above (not
    reproduced from anywhere, but a standard result) actually equals the
    integral it claims to be, before trusting it for the annulus solve."""
    for r, r_prime in [(0.3, 0.7), (0.5, 0.52), (1.0, 0.1)]:

        def integrand(phi, r=r, r_prime=r_prime):
            return math.cos(phi) / math.sqrt(
                r * r + r_prime * r_prime - 2 * r * r_prime * math.cos(phi)
            )

        numeric, _ = quad(integrand, 0, 2 * math.pi, limit=200)
        analytic = _annulus_kernel_cos_phi_component(np.array(r), np.array(r_prime))
        assert numeric == pytest.approx(float(analytic), abs=1e-8)


_GL_NODES, _GL_WEIGHTS = np.polynomial.legendre.leggauss(48)


def _gauss_legendre_on_interval(f, p, q, singular_at_p=False, singular_at_q=False):
    """48-point Gauss-Legendre on `[p, q]`; when an endpoint carries the
    kernel's own log singularity, the substitution `r' = end + (other -
    end)*u**2` turns it into an integrable `u*log(u)`, which plain
    Gauss-Legendre converges quickly on."""
    if singular_at_p or singular_at_q:
        end, other = (p, q) if singular_at_p else (q, p)
        u = 0.5 * (_GL_NODES + 1.0)
        weights = 0.5 * _GL_WEIGHTS
        r_prime = end + (other - end) * u * u
        return np.sum(weights * f(r_prime) * 2.0 * abs(q - p) * u)
    r_prime = 0.5 * (q - p) * _GL_NODES + 0.5 * (q + p)
    return 0.5 * (q - p) * np.sum(_GL_WEIGHTS * f(r_prime))


def _annulus_cell_integral(r_i: float, r0: float, r1: float) -> float:
    """`int_{r0}^{r1} r' K1(r_i, r') dr'`, log-singular at `r' = r_i` when
    that point falls inside the cell (the self term) and handled by the
    singular substitution above whenever `r_i` is at or near a cell edge."""

    def integrand(r_prime):
        return r_prime * _annulus_kernel_cos_phi_component(r_i, r_prime)

    if r0 < r_i < r1:
        return _gauss_legendre_on_interval(
            integrand, r0, r_i, singular_at_q=True
        ) + _gauss_legendre_on_interval(integrand, r_i, r1, singular_at_p=True)
    cell_width = r1 - r0
    if abs(r_i - r0) < 3 * cell_width or abs(r_i - r1) < 3 * cell_width:
        if abs(r_i - r0) <= abs(r_i - r1):
            return _gauss_legendre_on_interval(integrand, r0, r1, singular_at_p=True)
        return _gauss_legendre_on_interval(integrand, r0, r1, singular_at_q=True)
    return _gauss_legendre_on_interval(integrand, r0, r1)


def _solve_annulus_polarizability(inner_radius: float, outer_radius: float, n_cells: int) -> float:
    """Full-space electric polarizability (b = outer_radius = 1 units) of an
    isolated, flat, PEC circular annulus (or, at `inner_radius = 0`, a
    disk), for a uniform in-plane field, by 1-D piecewise-constant
    collocation in radius (exact by the `sigma(r, phi) = s(r)*cos(phi)`
    symmetry -- the 2-D electrostatic problem reduces to this 1-D one)."""
    u = np.linspace(0.0, 1.0, n_cells + 1)
    if inner_radius > 0:
        radial_nodes = inner_radius + (outer_radius - inner_radius) * 0.5 * (1 - np.cos(np.pi * u))
    else:
        radial_nodes = outer_radius * np.sin(0.5 * np.pi * u)
    radial_centres = 0.5 * (radial_nodes[:-1] + radial_nodes[1:])
    k = np.empty((n_cells, n_cells))
    for i in range(n_cells):
        for j in range(n_cells):
            k[i, j] = _annulus_cell_integral(
                radial_centres[i], radial_nodes[j], radial_nodes[j + 1]
            ) / (4 * math.pi)
    # Total potential zero on the conductor (E0 = 1): phi_sigma = E0 * r.
    surface_charge = np.linalg.solve(k, radial_centres)
    dipole_moment = math.pi * np.sum(
        surface_charge * (radial_nodes[1:] ** 3 - radial_nodes[:-1] ** 3) / 3.0
    )
    return dipole_moment


def test_annulus_solver_matches_disk_polarizability():
    """The `inner_radius = 0` limit is a disk, whose full-space in-plane
    polarizability is the settled `16/3` result (Mansfield, Douglas &
    Garboczi 2001, Table IV, n=infinity row; this module's own
    solid-square-plate test docstring)."""
    alpha_over_b3 = _solve_annulus_polarizability(inner_radius=0.0, outer_radius=1.0, n_cells=64)
    assert alpha_over_b3 == pytest.approx(16.0 / 3.0, rel=2e-3)


@pytest.mark.parametrize(
    "w_over_b,asymptotic_formula_deviation",
    [
        # w/b, and the |deviation| this feature's own research already found
        # between the converged solve and Kurennoy's Eq. (19) at that ratio
        # -- Kurennoy's own formula is asymptotic ("neglected terms
        # O(delta*ln(delta))"), so it is expected, not a bug, that the
        # converged solve pulls away from it as w/b grows; the tolerance
        # below is that expected deviation plus headroom.
        (0.02, 0.01),
        (0.04, 0.02),
        (0.10, 0.03),
    ],
)
def test_annulus_solver_tracks_kurennoy_1996_eq19_for_narrow_gaps(
    w_over_b, asymptotic_formula_deviation
):
    outer_radius = 1.0
    inner_radius = outer_radius - w_over_b * outer_radius
    # Kurennoy 1996 Eq. (19), psi = pi^2*b^2*a/(ln(32*b/w) - 2), doubled to
    # this module's full-space convention (module-level comment above).
    kurennoy_full_space = (
        2
        * math.pi**2
        * outer_radius**2
        * inner_radius
        / (math.log(32 * outer_radius / (w_over_b * outer_radius)) - 2)
    )
    solved = _solve_annulus_polarizability(inner_radius, outer_radius, n_cells=48)
    relative_deviation = abs(solved - kurennoy_full_space) / kurennoy_full_space
    assert relative_deviation < asymptotic_formula_deviation


# ---------------------------------------------------------------------------
# Reproduction of Ludvig-Osipov et al. 2020's own "cross potent" worked
# example (issue #552, following #547's deferred literature reproduction).
#
# Source: Ludvig-Osipov, Lundgren, Ehrenborg, Ivanenko, Ericsson, Gustafsson,
# Jonsson & Sjoberg, "Fundamental bounds on transmission through periodically
# perforated metal screens with experimental validation," arXiv:1810.07669v3
# (2019) -- Sec. IV, p. 4, Fig. 3 and its caption, read from the rendered PDF
# page image. Verbatim: "the array of cross-potent (sometimes referred to as
# Jerusalem cross) [...] shaped apertures [...] The unit cell geometry is
# given, with l_x = l_y = l, slot width w = l/20, and parameters a = 0.9l and
# b = 0.4l. [...] The results show the main transmission band (transmittance
# threshold level T_0^2 = 0.8) centered at lambda = 2.9l, with the fractional
# bandwidth B = 0.24. This accounts for 86% of the upper bound limit in (12)."
#
# Fig. 3's own inset diagram (not its Fig. 4, which is a different figure for
# a different set of designs) shows the aperture is a "+"-shaped slot of
# width w, each arm reaching length a/2 from the centre, capped at every tip
# by a perpendicular bar of length b and width w (a classic Jerusalem
# cross/cross-potent). The Babinet-complementary PEC PATCH this module's
# gamma always means (module docstring) is that same cross shape in metal --
# decomposable into 4 axis-aligned rectangles per quadrant (2 half-arms, 2
# T-cap quarters), so it reuses this module's own rectangle-kernel BEM
# machinery (`_graded_nodes_1d`, `_rect_cells`, `_solve_alpha_xx`) directly --
# no new numerical method, only a new mesh, matching issue #547's own point
# that a future shape should be able to reuse this machinery (US12).
#
# This is a periodic array at a = 0.9l, i.e. period/patch-size = 1/0.9 = 1.11
# -- deep inside the range `periodic_array_correction_is_reliable` already
# flags as unreliable (this module's own Fig. 4 cross-check found the
# first-order point-dipole correction under-predicts by ~13-15% at a
# comparably tight spacing). So this reproduction is expected to be loose,
# not tight -- and is reported as such below, not tuned to look closer than
# it is.
def _jerusalem_cross_quarter_mesh(
    arm_half_length: float, cap_length: float, width: float, n: int = 40
) -> np.ndarray:
    """First-quadrant mesh of a cross-potent (Jerusalem cross) patch: a
    "+"-shaped stem of width `width` reaching `arm_half_length` from the
    centre in x and y, with a perpendicular bar of length `cap_length` and
    width `width` capping each tip. Four non-overlapping rectangular pieces
    per quadrant: the two half-stems (split so neither double-counts the
    centre corner) and the two cap quarters. Cells grade toward the
    conductor's genuinely free (slot-facing) edges, same strategy as
    `_quarter_loop_mesh`; the grading at `stem_end` (where a stem piece
    meets its cap) targets a smooth internal butt-joint, not a real
    singularity -- harmless extra resolution there, not a claim of an edge
    that isn't one."""
    half_width = width / 2.0
    cap_half_length = cap_length / 2.0
    stem_end = arm_half_length - half_width  # where the stem meets its cap

    stem_x = _graded_nodes_1d(0.0, half_width, max(4, n // 4), grade_lo=False, grade_hi=True)
    stem_y = _graded_nodes_1d(0.0, stem_end, n, grade_lo=False, grade_hi=True)
    vertical_stem = _rect_cells(stem_x, stem_y)

    arm_x = _graded_nodes_1d(half_width, stem_end, n, grade_lo=False, grade_hi=True)
    arm_y = _graded_nodes_1d(0.0, half_width, max(4, n // 4), grade_lo=False, grade_hi=True)
    horizontal_stem = _rect_cells(arm_x, arm_y)

    cap_x = _graded_nodes_1d(0.0, cap_half_length, n, grade_lo=False, grade_hi=True)
    cap_y = _graded_nodes_1d(
        stem_end, stem_end + width, max(4, n // 4), grade_lo=True, grade_hi=True
    )
    top_cap = _rect_cells(cap_x, cap_y)

    cap_x2 = _graded_nodes_1d(
        stem_end, stem_end + width, max(4, n // 4), grade_lo=True, grade_hi=True
    )
    cap_y2 = _graded_nodes_1d(0.0, cap_half_length, n, grade_lo=False, grade_hi=True)
    right_cap = _rect_cells(cap_x2, cap_y2)

    return np.vstack([vertical_stem, horizontal_stem, top_cap, right_cap])


def test_periodic_array_correction_reproduces_ludvig_osipov_cross_potent_example():
    """Reproduces Fig. 3's own worked example end to end: compute the
    cross-potent patch's isolated polarizability from its stated geometry
    (this test's own BEM mesh, not a value read off any figure), apply this
    module's periodic-array correction, then feed the result into the
    unmodified, already-tested `perforated_screen_max_wavelength_fractional_bandwidth`
    (#483) to get a predicted bound -- and check it against the paper's own
    reported bandwidth the same two ways the paper itself frames the result:
    the physical requirement B <= bound must hold, and the ratio should be
    in the same ballpark as the paper's stated 86% (loosely, given the
    known tight-packing bias documented above)."""
    period = 1.0
    a = 0.9 * period
    b = 0.4 * period
    w = period / 20.0

    quarter_cells = _jerusalem_cross_quarter_mesh(arm_half_length=a / 2.0, cap_length=b, width=w)
    isolated_gamma = _solve_alpha_xx(quarter_cells)

    assert periodic_array_correction_is_reliable(patch_size_m=a, period_m=period) is False

    corrected_gamma = periodic_array_polarizability_correction_m3(
        isolated_gamma_m3=isolated_gamma, period_m=period
    )
    predicted_bound = perforated_screen_max_wavelength_fractional_bandwidth(
        gamma_m3=corrected_gamma,
        cell_area_m2=period**2,
        center_wavelength_m=2.9 * period,
        power_transmittance_threshold=0.8,
    )

    reported_bandwidth = 0.24
    # The physical requirement Eq. (12) exists to guarantee: a real
    # transmission band can never be wider than the bound. If this failed,
    # either this module's chain (mesh, kernel, periodic correction) or the
    # paper's own bound would be wrong.
    assert reported_bandwidth <= predicted_bound
    # The paper states B is 86% of its own bound, so its own bound is
    # reported_bandwidth / 0.86 -- compare this prediction against THAT
    # number directly, rather than against the loosely related 86% figure
    # itself. The tolerance is not arbitrary: this module's own correction
    # is known to under-predict by ~13-15% at a comparably tight packing
    # (the Fig. 4 cross-check above), and this prediction's actual
    # deviation here (~5%) sits well inside that ceiling with real margin
    # to spare -- a tolerance tight enough to fail on a wrong mesh or
    # kernel, loose enough to allow for the correction's own documented bias.
    paper_implied_bound = reported_bandwidth / 0.86
    assert predicted_bound == pytest.approx(paper_implied_bound, rel=0.08)
