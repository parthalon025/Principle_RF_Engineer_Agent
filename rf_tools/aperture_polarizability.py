"""Static electric polarizability of BANDPASS_FSS's own proposed aperture
shape -- a square-loop slot -- closing the one input
`rf_tools.physical_bounds.perforated_screen_min_polarizability_m3` /
`perforated_screen_max_wavelength_fractional_bandwidth` (#483) needs and
nothing computes from geometry (issue #547).

WHAT THIS COMPUTES, EXACTLY. Per
`docs/bandpass-fss-physical-bound-primary-source.md` sections 3.2-3.3 (itself
quoting Ludvig-Osipov et al. 2020's own derivation), the `gamma` that bound
needs is the electric polarizability of an isolated, flat, perfectly
conducting patch shaped exactly like the aperture's Babinet complement -- a
square-loop (picture-frame) PATCH, not the slot itself -- illuminated by a
uniform static field in its own plane. This module computes that quantity
for the family's own proposed geometry: a square outer boundary of side
`b_m`, with a uniform-width conducting frame of width `w_m` (equivalently, a
square hole of side `b_m - 2*w_m` cut from the centre).

METHOD. Sub-domain collocation boundary-element method: tile a quarter of
the conductor (the other three quadrants are symmetry images) with small
rectangular cells of unknown uniform charge density, use the closed-form
potential of a uniformly charged rectangle (exact, not a point-charge
approximation) to build the potential each cell induces at every other
cell's centre, solve for the charge density that makes the total potential
constant across the whole conductor, then integrate charge times position
for the induced dipole moment. Cells are graded toward the conductor's
edges to resolve the 1/sqrt(distance) edge-charge singularity.

PROVENANCE: `CALCULATED` -- deterministic numerical electrostatics on the
caller's own stated geometry (the METHOD above), no measurement, no
full-wave simulation. Validated against Mansfield, Douglas & Garboczi,
"Intrinsic viscosity and the electrical polarizability of arbitrarily
shaped objects," Phys. Rev. E 64:061401 (2001), Table IV -- the one point
on this shape's curve (`w_m == b_m / 2`, i.e. no hole at all) with an
independent published value -- and, for the periodic-array correction, also
against Ludvig-Osipov et al. 2020's own Fig. 4. See
`tests/test_aperture_polarizability.py` for the reproductions.

IN PLAIN TERMS: how wide a passband window a square-loop-slot radome can open
is set by how much electrical "bulk" the metal picture-frame left behind by
cutting that slot has, when you put it alone in a steady electric field.
`square_loop_polarizability_m3` answers that one question for a single,
isolated loop; `square_loop_periodic_array_polarizability_m3` adds back what
an isolated loop leaves out -- neighbouring loops in a real printed array
raise the true per-unit-cell value above the isolated one, and Ludvig-Osipov
et al.'s bound is stated per unit cell, not per isolated patch. Neither
function touches conductor loss: both are PEC calculations, and a printed
ink is not one -- that gap (`docs/bandpass-fss-physical-bound-primary-source.md`
Sec. 4.2) is still the caller's to close.
"""

from __future__ import annotations

import functools
import math

import numpy as np

__all__ = [
    "periodic_array_correction_is_reliable",
    "periodic_array_polarizability_correction_m3",
    "square_loop_periodic_array_polarizability_m3",
    "square_loop_polarizability_m3",
]

_FOUR_PI = 4.0 * math.pi

# Cells across the conductor's strip width (or, at the solid-plate limit,
# across the whole plate's half-width). Chosen so the solid-plate case
# reproduces Mansfield et al.'s published value
# (tests/test_aperture_polarizability.py) well inside its tolerance, while
# keeping the solve to a few seconds.
_CELLS_ACROSS_WIDTH = 40

# Cells along the strip's length, capped independent of how thin the strip
# is. Refining this beyond a few dozen cells barely moves the result -- the
# charge distribution along a strip is smooth away from its ends -- but
# letting it scale with the width/length aspect ratio (as a fixed
# cells-per-aspect-ratio rule would) explodes the dense solve past minutes
# and gigabytes for BANDPASS_FSS's realistic thin gaps (period ~8-10 mm,
# gap ~120-360 um, aspect ratio up into the tens).
_MAX_CELLS_ALONG_STRIP = 20
_ALONG_STRIP_CELLS_PER_ASPECT_RATIO = 0.5


def _require_positive_finite(name: str, value: float, unit: str) -> float:
    if not math.isfinite(value) or value <= 0:
        raise ValueError(f"{name} must be a positive finite number of {unit}; got {value!r}.")
    return float(value)


def _require_positive_length(name: str, value: float) -> float:
    return _require_positive_finite(name, value, "metres")


def _require_valid_square_loop(b_m: float, w_m: float) -> tuple[float, float]:
    """Validate a square-loop's outer side and strip width, returning both
    as plain floats. Raises rather than silently clamping: a caller who
    passes a gap so wide the "hole" has zero or negative area has described
    a different shape (or a solid plate), not this one."""
    b = _require_positive_length("b_m", b_m)
    w = _require_positive_length("w_m", w_m)
    if w > b / 2:
        raise ValueError(
            f"w_m must be at most b_m/2 (a wider strip leaves no hole at all -- "
            f"b_m/2 is the solid-square-plate limit); got w_m={w!r}, b_m={b!r}."
        )
    return b, w


def _graded_nodes_1d(lo: float, hi: float, n: int, grade_lo: bool, grade_hi: bool) -> np.ndarray:
    """`n` cell boundaries on `[lo, hi]`, concentrated toward whichever ends
    are flagged (cosine grading at a flagged end, spacing shrinking like the
    square of distance from it) to resolve the edge-charge singularity
    there; an unflagged end gets uniform spacing."""
    u = np.linspace(0.0, 1.0, n + 1)
    if grade_lo and grade_hi:
        s = 0.5 * (1.0 - np.cos(np.pi * u))
    elif grade_hi:
        s = np.sin(0.5 * np.pi * u)
    elif grade_lo:
        s = 1.0 - np.cos(0.5 * np.pi * u)
    else:
        s = u
    return lo + (hi - lo) * s


def _rect_cells(xn: np.ndarray, yn: np.ndarray) -> np.ndarray:
    """Tensor-product rectangular cells from two 1D node vectors. Returns an
    `(M, 4)` array of each cell's `(x0, x1, y0, y1)` boundaries."""
    x0, x1 = xn[:-1], xn[1:]
    y0, y1 = yn[:-1], yn[1:]
    gx0, gy0 = np.meshgrid(x0, y0, indexing="ij")
    gx1, gy1 = np.meshgrid(x1, y1, indexing="ij")
    return np.column_stack([gx0.ravel(), gx1.ravel(), gy0.ravel(), gy1.ravel()])


def _quarter_loop_mesh(b_half: float, w: float, n_w: int = _CELLS_ACROSS_WIDTH) -> np.ndarray:
    """First-quadrant boundary-element mesh of the square-loop conductor
    `{max(|x|, |y|) <= b_half} \\ {max(|x|, |y|) < b_half - w}` -- or, when
    `w == b_half`, the solid square plate with no hole at all. Cells grade
    toward the conductor's edges (cosine grading across the strip width /
    plate half-width; sine grading along the strip toward its re-entrant
    inner corner). `n_w` defaults to the production resolution but is
    overridable so tests can cheaply check a *different*-resolution property
    (isotropy, mesh-independence) without paying for the full solve twice."""
    inner_half = b_half - w
    if inner_half <= 1e-12 * b_half:
        xn = _graded_nodes_1d(0.0, b_half, n_w, grade_lo=False, grade_hi=True)
        return _rect_cells(xn, xn)
    across_strip = _graded_nodes_1d(inner_half, b_half, n_w, grade_lo=True, grade_hi=True)
    n_l = min(
        _MAX_CELLS_ALONG_STRIP,
        max(4, math.ceil(_ALONG_STRIP_CELLS_PER_ASPECT_RATIO * n_w * inner_half / w)),
    )
    along_strip = _graded_nodes_1d(0.0, inner_half, n_l, grade_lo=False, grade_hi=True)
    vertical_arm = _rect_cells(across_strip, along_strip)
    corner_square = _rect_cells(across_strip, across_strip)
    horizontal_arm = _rect_cells(along_strip, across_strip)
    return np.vstack([vertical_arm, corner_square, horizontal_arm])


def _rect_edge_potential_kernel(x: np.ndarray, y: np.ndarray) -> np.ndarray:
    """`G(x, y) = x*asinh(y/x) + y*asinh(x/y)`, odd in each argument with
    `G(0, y) = G(x, 0) = 0`: the antiderivative that gives the exact
    electrostatic potential of a uniformly charged rectangle in its own
    plane as a signed sum of `G` over its four corners. Computed via the
    equivalent log form `x*ln((y + r)/|x|)` to avoid the 0/0 that
    `asinh(y/x)` hits at `x = 0`."""
    ax = np.abs(x)
    ay = np.abs(y)
    r = np.sqrt(ax * ax + ay * ay)
    with np.errstate(divide="ignore", invalid="ignore"):
        t1 = np.where(ax > 0, ax * np.log((ay + r) / np.where(ax > 0, ax, 1.0)), 0.0)
        t2 = np.where(ay > 0, ay * np.log((ax + r) / np.where(ay > 0, ay, 1.0)), 0.0)
    return np.sign(x) * np.sign(y) * (t1 + t2)


def _rect_potential_from_corners(
    px: np.ndarray, py: np.ndarray, x0: np.ndarray, x1: np.ndarray, y0: np.ndarray, y1: np.ndarray
) -> np.ndarray:
    """Potential (with `eps0 = 1`, divided by `4*pi`) at field points `(px,
    py)` due to a unit surface charge density on the rectangle `[x0,
    x1]x[y0, y1]`: the inclusion-exclusion sum of `_rect_edge_potential_kernel`
    over the rectangle's four corners. The one place this module turns a
    rectangle's corners into a potential; both `_rect_potential_matrix`
    (mirrored across the axes) and the isotropy check in
    `tests/test_aperture_polarizability.py` (not mirrored) build on it."""
    return (
        _rect_edge_potential_kernel(x1 - px, y1 - py)
        - _rect_edge_potential_kernel(x0 - px, y1 - py)
        - _rect_edge_potential_kernel(x1 - px, y0 - py)
        + _rect_edge_potential_kernel(x0 - px, y0 - py)
    ) / _FOUR_PI


def _rect_potential_matrix(
    field_x: np.ndarray,
    field_y: np.ndarray,
    cells: np.ndarray,
    sign_x: int,
    sign_y: int,
    chunk: int = 512,
) -> np.ndarray:
    """`K[i, j]` = potential (with `eps0 = 1`) at field point `i` due to a
    unit surface charge density on first-quadrant cell `j` and its three
    mirror images across the axes -- signs `sign_x`, `sign_y`, `sign_x *
    sign_y` -- which stand in for the conductor's other three quadrants."""
    n_points = len(field_x)
    n_cells = len(cells)
    k = np.empty((n_points, n_cells), dtype=np.float64)
    x0, x1, y0, y1 = cells[:, 0], cells[:, 1], cells[:, 2], cells[:, 3]

    for i0 in range(0, n_points, chunk):
        i1 = min(n_points, i0 + chunk)
        px = field_x[i0:i1, None]
        py = field_y[i0:i1, None]
        total = _rect_potential_from_corners(
            px, py, x0[None, :], x1[None, :], y0[None, :], y1[None, :]
        )
        total += sign_x * _rect_potential_from_corners(
            px, py, -x1[None, :], -x0[None, :], y0[None, :], y1[None, :]
        )
        total += sign_y * _rect_potential_from_corners(
            px, py, x0[None, :], x1[None, :], -y1[None, :], -y0[None, :]
        )
        total += (
            sign_x
            * sign_y
            * _rect_potential_from_corners(
                px, py, -x1[None, :], -x0[None, :], -y1[None, :], -y0[None, :]
            )
        )
        k[i0:i1, :] = total
    return k


def _solve_alpha_xx(cells: np.ndarray) -> float:
    """`alpha_xx` of the full (four-quadrant) conductor described by its
    first-quadrant `cells`, for a unit field along x (`eps0 = 1`). The
    conductor is grounded (total potential zero); antisymmetry of the
    x-directed excitation across `x = 0` makes charge neutrality automatic,
    so no separate floating-potential unknown is needed."""
    xc = 0.5 * (cells[:, 0] + cells[:, 1])
    yc = 0.5 * (cells[:, 2] + cells[:, 3])
    area = (cells[:, 1] - cells[:, 0]) * (cells[:, 3] - cells[:, 2])
    k = _rect_potential_matrix(xc, yc, cells, sign_x=-1, sign_y=+1)
    # Total potential (applied field + induced charge) is zero everywhere on
    # the conductor: phi_sigma = -phi_ext = +E0 * x, with E0 = 1.
    sigma = np.linalg.solve(k, xc)
    return float(4.0 * np.sum(sigma * area * xc))


def square_loop_polarizability_m3(b_m: float, w_m: float) -> float:
    """Electric polarizability (m^3) of an isolated square-loop patch of
    outer side `b_m` and uniform strip width `w_m`, for a uniform field in
    the loop's own plane. See the module docstring for exactly what this
    is, and what it is not (a periodic-array value; a lossy conductor).

    PROVENANCE: `CALCULATED`, `w_m/b_m` in `(0, 0.5]`.

    VALIDITY BOX. Validated (`tests/test_aperture_polarizability.py`) at
    `w_m/b_m` from 0.02 to 0.5 -- the solid-square-plate limit itself
    (`w_m/b_m = 0.5`) against Mansfield, Douglas & Garboczi (2001)'s
    published value to within their stated uncertainty, and every ratio in
    between against the enclosing-object monotonicity Ludvig-Osipov et al.
    2020 state explicitly (Sec. IV). A caller with `w_m/b_m` well below 0.02
    (a much thinner strip than tested) is extrapolating: this "warns, never
    blocks" (ADR-0047) by still returning the boundary-element solve's best
    estimate rather than raising, but the caller should treat a very thin
    loop's result as less certain than one inside the validated range.

    CONVERGENCE. The boundary-element solve is empirically second-order in
    the mesh spacing across the strip width (this feature's own research);
    at the production mesh resolution, the solid-plate anchor above agrees
    with Mansfield et al.'s value to about 1 part in 10^4, and
    `tests/test_aperture_polarizability.py`'s own two-resolution regression
    test bounds the production value's remaining mesh-dependence to under
    0.5% at a representative thin-strip ratio. No closed-form error bar
    exists for an arbitrary `w_m/b_m`; these two checks are the precision
    evidence, not a per-call Richardson extrapolation (the production
    resolution is fixed, for speed -- module-level `_CELLS_ACROSS_WIDTH`
    comment).
    """
    b, w = _require_valid_square_loop(b_m, w_m)
    # Solve at outer side 1 and rescale: alpha scales as length^3, so the
    # normalised solve only depends on the shape (w/b), not its absolute
    # size.
    cells = _quarter_loop_mesh(b_half=0.5, w=w / b)
    alpha_over_b3 = _solve_alpha_xx(cells)
    return alpha_over_b3 * b**3


@functools.lru_cache(maxsize=1)
def _square_lattice_inplane_dipole_sum() -> float:
    """The lattice sum `S` in `gamma_cell = gamma / (1 - gamma*S/(4*pi*l**3))`
    (`square_loop_periodic_array_polarizability_m3`) for identical in-plane
    point dipoles on a square lattice of unit spacing: each neighbour's
    field back at the origin, resolved along the dipole direction, summed
    over every other site --
        `S = sum_{(m, n) != (0, 0)} (3*m**2 - (m**2 + n**2)) / (m**2 + n**2)**2.5`.
    This 2-D dipole sum is only *conditionally* convergent (each shell's
    terms fall off as `1/r`, exactly cancelling the shell's growing
    circumference on average, so the running total settles slowly rather
    than absolutely), so a symmetric, growing-square truncation converges
    to it like `1/N` in the truncation half-width `N` (checked empirically:
    doubling `N` from 400 to 800 to 1600 to 4000 roughly halves the residual
    each time, consistent with `S(N) = S_infinity - C/N`); two truncations
    `N` and `2N` are enough to Richardson-extrapolate that leading error
    away. `CALCULATED` -- this constant depends only on the lattice being
    square, never on a caller's own geometry or period, so it is computed
    once (`lru_cache`) rather than on every call.
    """

    def truncated_sum(n: int) -> float:
        m = np.arange(-n, n + 1, dtype=np.float64)
        grid_m, grid_n = np.meshgrid(m, m, indexing="ij")
        r2 = grid_m * grid_m + grid_n * grid_n
        nonzero = r2 > 0
        grid_m, r2 = grid_m[nonzero], r2[nonzero]
        r = np.sqrt(r2)
        return float(np.sum((3.0 * grid_m * grid_m - r2) / (r2 * r2 * r)))

    n, n_doubled = 800, 1600
    sum_n, sum_2n = truncated_sum(n), truncated_sum(n_doubled)
    return sum_2n + (sum_2n - sum_n)


# Ludvig-Osipov et al. 2020 Fig. 4's own "Square patch" curve -- read directly
# off the rendered figure (`docs/bandpass-fss-physical-bound-primary-source.md`;
# this feature's own research) -- tracks this correction to within about 10%
# for period/outer-side ratios down to 1.4, and under-predicts by more
# (~15% at the tightest spacing checked, period/outer-side = 1.10) below
# that: the correction is a first-order, point-dipole approximation, and
# Ludvig-Osipov et al.'s own patches are not point dipoles once they are
# nearly touching. See `tests/test_aperture_polarizability.py` for the
# reproduction.
_PERIODIC_CORRECTION_RELIABLE_PERIOD_OVER_SIDE = 1.4


def periodic_array_correction_is_reliable(patch_size_m: float, period_m: float) -> bool:
    """Whether `periodic_array_polarizability_correction_m3`'s first-order
    point-dipole correction is expected to track Ludvig-Osipov et al.
    2020's own per-unit-cell values (their Fig. 4, "Square patch" curve) to
    within about 10%, for a patch whose own outer size is `patch_size_m`
    (for the square loop, its outer side `b_m`) on a period `period_m`. See
    the module-level comment above for the reliability threshold's own
    source and the size of the error below it. This never blocks
    `periodic_array_polarizability_correction_m3` itself (ADR-0047, "warn,
    never block") -- it is a caller-facing check, so a design loop or a
    human can decide how much to trust a candidate whose patches are packed
    tightly enough that the correction's own accuracy is in doubt.
    """
    size, period = (
        _require_positive_length("patch_size_m", patch_size_m),
        _require_positive_length("period_m", period_m),
    )
    return period / size >= _PERIODIC_CORRECTION_RELIABLE_PERIOD_OVER_SIDE


def periodic_array_polarizability_correction_m3(isolated_gamma_m3: float, period_m: float) -> float:
    """`gamma` per unit cell of a square-lattice array of identical patches,
    given the ISOLATED-patch polarizability `isolated_gamma_m3` of any
    shape (not just a square loop -- issue #547's Implementation Decisions
    explicitly leave this input as "the isolated value... or the same
    geometry inputs") and the array's period `period_m`. Neighbouring
    patches only ever *raise* a patch's polarizability above its isolated
    value (the underlying lattice sum is positive; see
    `_square_lattice_inplane_dipole_sum`), via the classical first-order
    (point-dipole) correction
    `gamma_cell = isolated_gamma_m3 / (1 - isolated_gamma_m3*S/(4*pi*period_m**3))`.
    `square_loop_periodic_array_polarizability_m3` is a convenience wrapper
    over this specifically for the square-loop shape; call this function
    directly for any other isolated `gamma` this module has no solve for --
    a literature value or a hand calculation, the same way
    `rf_tools.physical_bounds.perforated_screen_min_polarizability_m3`
    itself takes `gamma` as a caller-supplied argument.

    Call `periodic_array_correction_is_reliable` (with the patch's own
    outer size) to check whether this packing density is inside the range
    this correction was validated for; this function still returns its
    best estimate outside that range rather than raising (ADR-0047, "warn,
    never block").

    PROVENANCE: `CALCULATED`. Validated against Ludvig-Osipov et al. 2020's
    own Fig. 4 "Square patch" curve; see `periodic_array_correction_is_reliable`'s
    docstring and `tests/test_aperture_polarizability.py` for how well and
    over what range.

    Raises `ValueError` for a non-positive or non-finite `isolated_gamma_m3`
    or `period_m`.
    """
    isolated = _require_positive_finite("isolated_gamma_m3", isolated_gamma_m3, "cubic metres")
    period = _require_positive_length("period_m", period_m)
    lattice_sum = _square_lattice_inplane_dipole_sum()
    denominator = 1.0 - isolated * lattice_sum / (_FOUR_PI * period**3)
    return isolated / denominator


def square_loop_periodic_array_polarizability_m3(b_m: float, w_m: float, period_m: float) -> float:
    """`gamma` per unit cell of a square-lattice array of square-loop
    patches -- outer side `b_m`, strip width `w_m`, array period `period_m`
    -- the quantity Ludvig-Osipov et al. 2020 Eq. (12) actually needs
    (module docstring), as opposed to `square_loop_polarizability_m3`'s
    isolated-patch value. A convenience wrapper over
    `periodic_array_polarizability_correction_m3` (see its docstring for
    the correction formula itself, its validated range and known bias) that
    also validates the square-loop-specific geometry and the physical
    constraint a shape-agnostic period alone cannot check: adjacent loops
    must not overlap.

    PROVENANCE: `CALCULATED`. See `periodic_array_polarizability_correction_m3`.

    The correction's denominator, `1 - gamma*S/(4*pi*period_m**3)`, stays
    bounded well away from zero (>= ~0.63) over the entire physically valid
    domain: `gamma` itself can never exceed the solid-square-plate value at
    the same `b_m` (Ludvig-Osipov et al.'s own enclosing-object bound,
    `tests/test_aperture_polarizability.py`), and `period_m` can never be
    smaller than `b_m` (checked below) -- so this first-order model, unlike
    some periodic corrections, never predicts an outright divergence for
    this shape; it only loses accuracy (see `periodic_array_correction_is_reliable`).

    Raises `ValueError` for `period_m < b_m` -- the loops would physically
    overlap.
    """
    b, w = _require_valid_square_loop(b_m, w_m)
    period = _require_positive_length("period_m", period_m)
    if period < b:
        raise ValueError(
            f"period_m must be at least b_m -- a smaller period would make "
            f"adjacent loops overlap; got period_m={period!r} < b_m={b!r}."
        )
    isolated = square_loop_polarizability_m3(b_m=b, w_m=w)
    return periodic_array_polarizability_correction_m3(isolated_gamma_m3=isolated, period_m=period)
