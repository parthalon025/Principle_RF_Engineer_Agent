"""gdstk-based metamaterial/frequency-selective-surface unit-cell shape
composition and periodic planar array generation (issue #55).

This module is a pure in-memory geometry generator: it never reads or
writes a GDSII/OASIS file. It produces plain primitive dicts in EXACTLY the
same "shape": "box"/"polygon" + p1_m/p2_m/points_m/radius_m/normal_axis/
elevation_m shape simulation/openems.py's _primitive_xml (see that module's
own docstring/header comment) consumes -- so its output can be dropped
straight into an openEMS `geometry["conductors"]`/`geometry["materials"]`
list, or handed to any other consumer of that same primitive-dict
vocabulary (e.g. the FreeCAD geometry generation planned for issue #66,
which this ticket is a blocker for). This module itself does NOT import
simulation/openems.py or any other simulator -- it is deliberately
simulator-agnostic, per issue #55's acceptance criterion that its output
shape be "independent of any simulator consuming it".

WHAT THIS SOLVES: hand-authoring a geometry dict for, say, a 10x10
Jerusalem-cross frequency-selective surface means writing out 100 near-
identical polygon primitives by hand, one per element, each with its own
hand-shifted vertex coordinates -- tedious and error-prone, and it has to
be redone from scratch for every different array size. `combine_shapes()`
builds one arbitrary unit-cell outline (e.g. a split-ring resonator's
C-shaped outline, built from a rectangle minus a smaller rectangle minus a
gap notch) from simple box/polygon shape descriptors via gdstk's boolean
operations; `generate_unit_cell_array()` then tiles ONE unit cell (a single
primitive dict, or the small list combine_shapes() returns) across an
NxM planar grid purely by translating coordinates, given only the unit
cell's own dimensions, a lattice spacing, and an element count.

SOURCES CONSULTED (primary; the gdstk Python API was fetched directly from
its own official documentation at heitzmann.github.io/gdstk during
implementation, and cross-checked empirically against gdstk 1.0.1 actually
imported and exercised in this environment -- gdstk, unlike NEC2++/openEMS/
HFSS/CSXCAD, is a small, freely pip-installable library with prebuilt
wheels and no license gate, so (unlike those adapters' honest "not verified
against a real binary" caveats) this module's gdstk usage IS exercised
against the real library in tests, not a fake/stub):
  - gdstk.Polygon(points, layer=0, datatype=0) -- constructed from a
    sequence of (x, y) coordinate pairs; its own `.points` attribute
    (read-only, confirmed empirically to be an (N, 2) numpy.float64 array)
    is read back after each transform to extract this module's own
    "points_m" primitive field: heitzmann.github.io/gdstk/geometry/
    gdstk.Polygon.html.
  - Polygon.copy() -> gdstk.Polygon (returns an independent copy; confirmed
    empirically that mutating the copy via .translate() below leaves the
    original's .points unchanged) and Polygon.translate(dx, dy) -> self
    (in-place, mutating translation): same page.
  - gdstk.rectangle(corner1, corner2, layer=0, datatype=0) -> gdstk.Polygon
    -- builds an axis-aligned rectangle from any two opposite corners (order
    -independent, confirmed empirically): heitzmann.github.io/gdstk/
    geometry/gdstk.rectangle.html.
  - gdstk.boolean(operand1, operand2, operation, precision=1e-3, layer=0,
    datatype=0) -> list[gdstk.Polygon] -- operation is one of "or" (union),
    "and" (intersection), "xor", or "not" (operand1 minus operand2);
    operand1/operand2 may each be a single Polygon or a sequence of them;
    confirmed empirically that a "not" of two concentric rectangles returns
    a single closed polygon tracing both the outer and inner boundary plus
    a connecting seam -- gdstk's standard technique for representing a ring
    (an annulus, the basis of a split-ring resonator) as one simple,
    non-self-crossing polygon rather than two nested loops, which is
    exactly the shape CSXCAD's own single-loop Polygon primitive (see
    simulation/openems.py's module docstring citation) requires:
    heitzmann.github.io/gdstk/geometry/gdstk.boolean.html.
  - `precision` UNIT CAVEAT (an explicit, deliberate deviation from
    gdstk's own documented default, not an oversight): gdstk's 1e-3 default
    is calibrated for GDSII files, which conventionally use micrometers, so
    that default corresponds to 1 nanometer of vertex-snapping tolerance in
    THAT unit system. This module's coordinates are meters (matching every
    other geometry dict in this repo, e.g. simulation/openems.py's own
    p1_m/p2_m), so blindly keeping gdstk's raw 1e-3 default would snap
    vertices to a 1 MILLIMETER grid -- large enough to visibly deform a
    typical mm-scale RF metamaterial unit cell (e.g. an SRR gap of a few
    tens of microns would vanish entirely). This module instead defaults
    `precision_m` to 1e-9 (nanometer resolution in meters), three orders of
    magnitude finer than gdstk's own micrometer-file convention and many
    orders finer than any realistic RF feature size, and always passes it
    explicitly to gdstk.boolean() rather than relying on gdstk's own
    default.

CODED (HETEROGENEOUS-SYMBOL) PLACEMENT (issue #212). Both functions above
tile ONE unit cell identically across the whole grid -- the right primitive
for a Supercell (CONTEXT.md: "a block of identical Symbols repeated side by
side"), but structurally incapable of a coded surface, which by definition
mixes unlike Symbols (`docs/supercell-sizing-rule.md` line 108: "Real coded
surfaces mix letters"). `generate_coded_unit_cell_array` (below) is the new
function issue #104 named this needs -- per-position symbol selection, not a
parameter on the existing tiler. It places BLOCKS (each an N x M run of one
Symbol, per `docs/supercell-sizing-rule.md` Sec 5.5's sizing rule -- see
`block_size_from_sizing_rule`), resolves each layout entry through an
injected Element/Coding-Alphabet symbol library rather than accepting raw
geometry inline (#109), and reports a cache miss as a hard `SymbolNotFoundError`
rather than silently substituting a default (CONTEXT.md: a Symbol not in the
library isn't drawable, full stop -- there is no plausible substitute
geometry). Both compose `generate_unit_cell_array` for their actual
per-block/per-cell tiling rather than duplicating its translation logic;
`generate_unit_cell_array` itself is unchanged by this addition.

HONEST CAVEAT: this module's gdstk usage has been exercised against the
real, installed gdstk 1.0.1 library (see tests/test_geometry_unit_cell.py)
-- so, unlike this repo's simulator adapters, there is no "not verified
against a real binary" gap here for gdstk itself. What has NOT been
verified end-to-end is the far side of the pipeline: the polygon/box
primitive dicts this module emits have not been run through a real openEMS
binary (openEMS is built into this project's own Docker image, absent on a
bare host -- see simulation/openems.py's own honest caveat, issue #480), so
while the <Polygon> XML
shape they feed into is verified against CSXCAD's own source, an actual
openEMS FDTD run consuming a gdstk-generated unit-cell array has not been
performed.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import gdstk

# x/y/z -> the same integer axis-index convention CSXCAD's own NormDir
# attribute uses (see simulation/openems.py's module docstring citation).
# Duplicated here rather than imported from simulation.openems -- this
# module is deliberately simulator-agnostic (issue #55 acceptance
# criterion: output "independent of any simulator consuming it").
_AXIS_INDEX = {"x": 0, "y": 1, "z": 2}

# combine_shapes()'s own operation vocabulary -> gdstk.boolean()'s own
# "or"/"and"/"xor"/"not" operation strings (see module docstring citation).
_BOOLEAN_OP = {"add": "or", "subtract": "not", "intersect": "and", "xor": "xor"}


def _shape_to_gdstk_polygon(shape: dict[str, Any], idx: int) -> gdstk.Polygon:
    """Build one local (cell-relative) box or polygon shape descriptor into
    a gdstk.Polygon -- see combine_shapes()'s docstring for the `shapes`
    entry format."""
    kind = shape.get("kind", "polygon")
    if kind == "box":
        missing = [f for f in ("p1_m", "p2_m") if f not in shape]
        if missing:
            raise ValueError(f"shape {idx} (kind='box') missing required field(s): {missing}")
        p1 = shape["p1_m"]
        p2 = shape["p2_m"]
        return gdstk.rectangle((float(p1[0]), float(p1[1])), (float(p2[0]), float(p2[1])))
    if kind == "polygon":
        if "points_m" not in shape:
            raise ValueError(f"shape {idx} (kind='polygon') missing required field 'points_m'")
        points = shape["points_m"]
        if len(points) < 3:
            raise ValueError(
                f"shape {idx} (kind='polygon') requires at least 3 points_m, got {len(points)}"
            )
        return gdstk.Polygon([(float(x), float(y)) for x, y in points])
    raise ValueError(f"shape {idx} 'kind' must be 'box' or 'polygon', got {kind!r}")


def combine_shapes(
    shapes: list[dict[str, Any]],
    precision_m: float = 1e-9,
    normal_axis: str = "z",
    elevation_m: float = 0.0,
    name_prefix: str = "shape",
) -> list[dict[str, Any]]:
    """Boolean-combine a sequence of simple local box/polygon shapes into an
    arbitrary unit-cell outline -- the way an SRR (a rectangle minus a
    smaller concentric rectangle, minus a thin gap-notch rectangle), a
    Jerusalem cross (a union of a square and two crossing bars), or any
    other non-rectilinear frequency-selective-surface element is naturally
    expressed, rather than requiring the caller to hand-derive one single
    polygon vertex list themselves.

    `shapes`: a non-empty list of
        {
          "kind": "box" | "polygon" (default "polygon"),
          "p1_m", "p2_m": [x, y],       # box only -- local 2D corner coords
          "points_m": [[x, y], ...],    # polygon only -- >=3 local 2D coords
          "operation": "add" | "subtract" | "intersect" | "xor"
              (default "add"; "add"=union, "subtract"=this shape removed
              from the running result, "intersect"=set intersection,
              "xor"=symmetric difference -- mapped to gdstk.boolean()'s own
              "or"/"not"/"and"/"xor", see module docstring citation),
        }
    shapes[0]'s own `operation` must be "add" (or omitted) -- there is
    nothing yet to subtract/intersect/xor against for the first shape.
    Each subsequent shape is boolean-combined into the running result in
    list order.

    All coordinates are LOCAL to the unit cell's own (0, 0) origin, in
    meters -- this function does not know about, or care about, the
    lattice spacing/count/origin generate_unit_cell_array() places the
    result at.

    Returns a list of "polygon" primitive dicts (see
    simulation/openems.py's generate_openems_xml docstring for the shape:
    "shape", "points_m", "normal_axis", "elevation_m", "name") -- normally
    exactly one, but a boolean op (e.g. "subtract" carving a shape in two,
    or "xor") can legitimately split the outline into several disjoint
    polygons, in which case each gets its own dict with a numbered
    `name_prefix`-based name.

    Raises ValueError if `shapes` is empty, shapes[0]'s operation isn't
    "add", an unknown "kind"/"operation" is given, a shape is missing its
    required field(s), or a boolean op removes the entire outline (nothing
    left to combine further).
    """
    if not shapes:
        raise ValueError("shapes must be a non-empty list")
    if normal_axis not in _AXIS_INDEX:
        raise ValueError(f"normal_axis must be 'x', 'y', or 'z', got {normal_axis!r}")

    first_op = shapes[0].get("operation", "add")
    if first_op != "add":
        raise ValueError(
            "shapes[0]'s operation must be 'add' (or omitted) -- there is "
            f"nothing yet to combine {first_op!r} against"
        )

    current: list[gdstk.Polygon] = [_shape_to_gdstk_polygon(shapes[0], 0)]
    for idx, shape in enumerate(shapes[1:], start=1):
        operation = shape.get("operation", "add")
        if operation not in _BOOLEAN_OP:
            raise ValueError(
                f"shape {idx} 'operation' must be one of {sorted(_BOOLEAN_OP)}, got {operation!r}"
            )
        next_poly = _shape_to_gdstk_polygon(shape, idx)
        current = gdstk.boolean(current, next_poly, _BOOLEAN_OP[operation], precision=precision_m)
        if not current:
            raise ValueError(
                f"shape {idx}'s {operation!r} operation removed the entire "
                "outline -- nothing left to combine further"
            )

    primitives: list[dict[str, Any]] = []
    for k, poly in enumerate(current):
        suffix = f"_{k}" if len(current) > 1 else ""
        primitives.append(
            {
                "name": f"{name_prefix}{suffix}",
                "shape": "polygon",
                "points_m": poly.points.tolist(),
                "normal_axis": normal_axis,
                "elevation_m": elevation_m,
            }
        )
    return primitives


def generate_unit_cell_array(
    unit_cell: dict[str, Any] | list[dict[str, Any]],
    spacing_m: tuple[float, float],
    count: tuple[int, int],
    origin_m: tuple[float, float] = (0.0, 0.0),
    name_prefix: str = "cell",
) -> list[dict[str, Any]]:
    """Tile one unit cell across a periodic rectangular NxM planar grid,
    producing one translated copy of the unit cell's primitive(s) per grid
    position -- the programmatic alternative to hand-authoring a repeated-
    element geometry dict for every array size.

    `unit_cell`: a single "box" or "polygon" primitive dict, or a list of
    them (e.g. combine_shapes()'s own return value, for a unit cell with a
    non-trivial boolean-composed outline, possibly split across several
    disjoint polygons) -- each already in simulation/openems.py's own
    primitive-dict shape ("shape": "box" with "p1_m"/"p2_m", or "shape":
    "polygon" with "points_m"/"normal_axis"/"elevation_m"), with X/Y
    coordinates LOCAL to the unit cell's own (0, 0) origin (Z, and any
    normal_axis/elevation_m, are carried through unchanged -- this
    generator only tiles in the X/Y plane, per issue #55's "periodic
    *planar* unit-cell array" scope). Only "box" and "polygon" primitives
    are supported here (not "cylinder") -- see module docstring "WHAT THIS
    SOLVES".

    `spacing_m`: (dx, dy) lattice pitch in meters between adjacent cells.
    `count`: (nx, ny) element counts, each >= 1.
    `origin_m`: (x, y) offset added to every generated primitive's
    coordinates, positioning the whole array's (0, 0) grid cell.

    Box primitives are translated by plain coordinate arithmetic
    (mathematically identical to routing an axis-aligned rectangle's two
    corner points through gdstk's own Polygon.translate() -- translation is
    linear, so there is nothing gdstk's heavier polygon machinery adds for
    a two-point box). Polygon primitives ARE translated via a real
    gdstk.Polygon(...).copy().translate(dx, dy) call per grid position,
    exercising gdstk's actual transform API for the case (arbitrary vertex
    counts) that genuinely needs it -- see module docstring citation.

    Returns a flat list of primitive dicts, `len(cell_primitives) * nx *
    ny` entries, each with a unique "name"
    (f"{name_prefix}_{i}_{j}[_{k}]").

    Raises ValueError if `unit_cell` is empty, `count` has a dimension < 1,
    or any unit-cell primitive is missing its shape-required field(s) or
    uses an unsupported shape.
    """
    cell_primitives = [unit_cell] if isinstance(unit_cell, dict) else list(unit_cell)
    if not cell_primitives:
        raise ValueError("unit_cell must be a non-empty primitive dict or list of primitive dicts")

    nx, ny = count
    nx, ny = int(nx), int(ny)
    if nx < 1 or ny < 1:
        raise ValueError(f"count must be >= 1 in both dimensions, got {count!r}")
    dx_pitch, dy_pitch = spacing_m
    ox, oy = origin_m

    for k, prim in enumerate(cell_primitives):
        shape = prim.get("shape", "box")
        if shape not in ("box", "polygon"):
            raise ValueError(
                f"unit_cell primitive {k} 'shape' must be 'box' or 'polygon' "
                f"(this generator does not tile 'cylinder' primitives), got {shape!r}"
            )
        if shape == "box":
            missing = [f for f in ("p1_m", "p2_m") if f not in prim]
            if missing:
                raise ValueError(
                    f"unit_cell primitive {k} (shape='box') missing required field(s): {missing}"
                )
        else:
            if "points_m" not in prim:
                raise ValueError(
                    f"unit_cell primitive {k} (shape='polygon') missing required field 'points_m'"
                )

    multi_cell = len(cell_primitives) > 1
    primitives: list[dict[str, Any]] = []
    for i in range(nx):
        for j in range(ny):
            dx = ox + i * dx_pitch
            dy = oy + j * dy_pitch
            for k, prim in enumerate(cell_primitives):
                translated = dict(prim)
                suffix = f"_{k}" if multi_cell else ""
                translated["name"] = f"{name_prefix}_{i}_{j}{suffix}"
                if prim.get("shape", "box") == "polygon":
                    gpoly = gdstk.Polygon([(float(x), float(y)) for x, y in prim["points_m"]])
                    gpoly = gpoly.copy().translate(dx, dy)
                    translated["points_m"] = gpoly.points.tolist()
                else:
                    p1 = prim["p1_m"]
                    p2 = prim["p2_m"]
                    translated["p1_m"] = [p1[0] + dx, p1[1] + dy, p1[2]]
                    translated["p2_m"] = [p2[0] + dx, p2[1] + dy, p2[2]]
                primitives.append(translated)
    return primitives


def generate_metamaterial_array(
    shapes: list[dict[str, Any]],
    spacing_m: tuple[float, float],
    count: tuple[int, int],
    origin_m: tuple[float, float] = (0.0, 0.0),
    normal_axis: str = "z",
    elevation_m: float = 0.0,
    precision_m: float = 1e-9,
    name_prefix: str = "cell",
) -> list[dict[str, Any]]:
    """Convenience wrapper: combine_shapes(shapes, ...) to build one
    unit-cell outline, then generate_unit_cell_array(...) to tile it --
    the one-call path from "here's how my SRR/Jerusalem-cross/FSS element
    is built out of simple shapes" to "here's the whole array's worth of
    Polygon primitives", for the common case where the unit cell itself
    needs boolean composition (see combine_shapes docstring) rather than
    being a single already-final box/polygon. See both functions'
    docstrings for the full parameter/return shape.
    """
    unit_cell = combine_shapes(
        shapes,
        precision_m=precision_m,
        normal_axis=normal_axis,
        elevation_m=elevation_m,
        name_prefix="unit_cell",
    )
    return generate_unit_cell_array(
        unit_cell,
        spacing_m=spacing_m,
        count=count,
        origin_m=origin_m,
        name_prefix=name_prefix,
    )


# ---------------------------------------------------------------------------
# Coded (heterogeneous-symbol) placement -- issue #212.
#
# A Supercell (CONTEXT.md) is a block of IDENTICAL Symbols; generate_unit_
# cell_array above is exactly that primitive and stays untouched. A coded
# surface is built from several DIFFERENT Symbol blocks laid out next to each
# other (docs/supercell-sizing-rule.md: "Real coded surfaces mix letters"),
# which needs (a) a per-position symbol assignment, (b) each symbol's
# geometry resolved from the Element/Coding-Alphabet library rather than
# handed in as raw shapes (#109), and (c) a block size derived from the
# requirement rather than guessed (docs/supercell-sizing-rule.md Sec 5.5).
# The two functions below are that support, in that order.
# ---------------------------------------------------------------------------


class SymbolNotFoundError(ValueError):
    """Raised by `generate_coded_unit_cell_array` when a layout names a
    symbol id with no matching entry in the `symbol_library` mapping it was
    given.

    Named and raised the same way this repo's other "the name given doesn't
    resolve" cases are (`designs.design_families.UnknownDesignFamilyError`):
    a `ValueError` subclass naming exactly what was looked for and what IS
    available, never a bare `KeyError`.

    Deliberately a hard error, not a warning. CLAUDE.md's "warn, never
    block" convention covers a judgment call the model can make with a
    caveat attached (a provisional value, an unread bound); it does not
    cover this case, because there is no plausible geometry to substitute
    for a symbol that was never characterised -- CONTEXT.md's Element/
    Coding-Alphabet library entry is explicit that "only a printed letter is
    in the library" (ADR-0027), so a miss here means the shape genuinely
    does not exist yet. Silently drawing *something* in its place would
    misrepresent a hypothesis as a printable design; refusing and naming the
    gap is what lets a human go print and measure the missing symbol.
    """


def _resolve_symbol_library(
    symbol_ids: Sequence[str],
    symbol_library: Mapping[str, dict[str, Any] | list[dict[str, Any]]],
) -> dict[str, dict[str, Any] | list[dict[str, Any]]]:
    """Look up every distinct symbol id a layout uses, all at once, so one
    `generate_coded_unit_cell_array` call reports every missing symbol in a
    single `SymbolNotFoundError` rather than failing on the first miss,
    forcing a fix-one-run-again-fix-the-next loop through a large layout."""
    missing = sorted({sid for sid in symbol_ids if sid not in symbol_library})
    if missing:
        known = sorted(symbol_library) if symbol_library else []
        raise SymbolNotFoundError(
            f"symbol id(s) {missing} have no entry in the Element/Coding-Alphabet "
            f"symbol_library given to generate_coded_unit_cell_array. "
            f"Known symbol ids: {known if known else '(symbol_library is empty)'}. "
            "A symbol enters this library only once it has been printed and "
            "measured (ADR-0027) -- this is a cache miss to go resolve (print "
            "and characterise the symbol, or fix the layout's spelling), not "
            "something to guess past with placeholder geometry."
        )
    return {sid: symbol_library[sid] for sid in set(symbol_ids)}


def _require_positive_finite(field_name: str, value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field_name} must be a real number, got {value!r}")
    numeric = float(value)
    if not math.isfinite(numeric) or numeric <= 0:
        raise ValueError(f"{field_name} must be finite and > 0, got {value!r}")
    return numeric


def boundary_fraction(nx: int, ny: int) -> float:
    """docs/supercell-sizing-rule.md Sec 5.5 Amendment 1: the fraction of an
    Nx x Ny block's cells that touch a foreign (unlike-symbol) block --
    `f(Nx, Ny) = 1 - (Nx-2)(Ny-2)/(Nx*Ny)` for Nx, Ny >= 2, or 1.0 (every
    cell is a boundary cell) if either is 1. Verified in that document to
    reduce to the square-cell `(4N-4)/N**2` when Nx == Ny; reproduced here:
    1 - (N-2)**2/N**2 == (N**2 - (N-2)**2)/N**2 == (4N-4)/N**2.

    Promoted from a private `_boundary_fraction` (issue #550) so `rf_tools.
    diffusive_checkerboard` can call it directly for a plain 1:1 alternating
    checkerboard's own coupling-error term, rather than duplicating the
    formula."""
    if nx < 1 or ny < 1:
        raise ValueError(f"nx and ny must be >= 1, got ({nx!r}, {ny!r})")
    if nx == 1 or ny == 1:
        return 1.0
    return 1.0 - (nx - 2) * (ny - 2) / (nx * ny)


def phase_budget_deg(rcsr_db: float) -> float:
    """docs/supercell-sizing-rule.md Sec 2.2: the unlike-neighbour phase
    error a coding block's two symbols can tolerate and still deliver a
    stated RCS-reduction requirement -- `delta_budget = 2*arcsin(10**(-RCSR_dB
    / 20))`. E.g. RCSR_dB=10 -> 36.9 degrees, the "180 +/- 37 degrees"
    criterion from the chessboard RCS-reduction literature the document
    cites as a cross-check.

    Promoted from a private `_phase_budget_deg` (issue #550) for the same
    reason as `boundary_fraction` above."""
    ratio = 10.0 ** (-rcsr_db / 20.0)
    ratio = min(ratio, 1.0)  # guard a pathological rcsr_db < 0 from asin(>1)
    return 2.0 * math.degrees(math.asin(ratio))


def _diffraction_sin_theta(
    nx: int, ny: int, pitch_m: tuple[float, float], wavelength_m: float
) -> float:
    """docs/supercell-sizing-rule.md Sec 5.5 Amendment 2: the sine of the
    angle the chessboard pattern's dominant diffraction lobe leaves at,
    `sin(theta) = (lambda/2) * sqrt(1/ax**2 + 1/ay**2)` with `ax = Nx*px`,
    `ay = Ny*py`. Reduces to `lambda/(a*sqrt(2))` when ax == ay (the
    document's own square-cell check). A value > 1 means no propagating
    diffraction order exists at all at this block size (Amendment 3) --
    the block redirects nothing, so this cannot satisfy the ceiling."""
    px_m, py_m = pitch_m
    ax_m = nx * px_m
    ay_m = ny * py_m
    return (wavelength_m / 2.0) * math.sqrt(1.0 / ax_m**2 + 1.0 / ay_m**2)


def block_size_from_sizing_rule(
    delta_phi_max_deg: float,
    rcsr_db: float,
    pitch_m: tuple[float, float],
    wavelength_m: float,
    panel_size_m: tuple[float, float],
    theta_min_deg: float | None = None,
    max_n: int = 32,
) -> tuple[int, int]:
    """Derive a coding super-cell's block size `(Nx, Ny)`, in cells, from the
    requirement -- docs/supercell-sizing-rule.md Sec 5.5's two-index sizing
    rule -- rather than a hardcoded constant (issue #212's acceptance
    criterion).

    Four constraints, all from that document, must hold simultaneously:

      - **Hard floor N >= 2** (Sec 3): a 1x1 "checkerboard" has no
        propagating diffraction order at all, so no block dimension may be
        1 (this function never returns 1 in either axis).
      - **Propagates at all** (Sec 5.5 Amendment 3): the diffraction sine
        `_diffraction_sin_theta(...)` must be <= 1 -- otherwise the block
        redirects nothing and the whole cancellation mechanism this rule
        exists for does not apply.
      - **The floor** (Sec 2): unlike-neighbour coupling error, bounded by
        `delta_phi_max_deg * boundary_fraction(Nx, Ny)`, must not exceed
        the phase budget `phase_budget_deg(rcsr_db)` the stated RCS-
        reduction requirement implies -- a small block whose symbols are too
        different from each other won't cancel down to the target dB.
      - **The ceiling** (Sec 3 and Sec 5.5 Amendment 4): the redirected lobe
        (`_diffraction_sin_theta`, converted to an angle) must clear
        `theta_min_deg` -- the panel's own specular lobe, defaulted here
        from the SMALLER of `panel_size_m`'s two sides via the document's
        `theta_min ~= lambda / (2 * L)` (Sec 3's "how far off is far
        enough", using the more binding of the two panel dimensions, per
        that section's own "the coupon is the hard case" reading) unless
        the caller states a different bistatic-angle requirement -- AND the
        block must physically fit on the panel at least twice per axis
        (Amendment 4: `2*Nx*px <= Lx`, `2*Ny*py <= Ly`), which Sec 5.5 shows
        is the constraint that actually binds on a small coupon.

    Among every `(Nx, Ny)` satisfying all four (searched over `2..max_n` in
    both axes), returns the SMALLEST by cell count (ties broken by the
    smaller Nx, then Ny) -- the finest spatial control over the coded
    pattern the requirement allows (Sec 4: "an N=2 design can vary its
    pattern twice as finely in each direction as N=4").

    Raises `ValueError` naming the phase budget, ceiling angle and panel-fit
    numbers actually computed if no block size up to `max_n` x `max_n`
    satisfies all four -- Sec 4/5.5's "no N works" outcome, which that
    document shows is conditional on panel size and alphabet, not a fixed
    verdict, so the message says as much rather than presenting the miss as
    final.
    """
    delta_phi_max_deg = _require_positive_finite("delta_phi_max_deg", delta_phi_max_deg)
    wavelength_m = _require_positive_finite("wavelength_m", wavelength_m)
    px_m = _require_positive_finite("pitch_m[0]", pitch_m[0])
    py_m = _require_positive_finite("pitch_m[1]", pitch_m[1])
    lx_m = _require_positive_finite("panel_size_m[0]", panel_size_m[0])
    ly_m = _require_positive_finite("panel_size_m[1]", panel_size_m[1])
    if (
        not isinstance(rcsr_db, (int, float))
        or isinstance(rcsr_db, bool)
        or not math.isfinite(rcsr_db)
    ):
        raise ValueError(f"rcsr_db must be a finite real number, got {rcsr_db!r}")
    if not isinstance(max_n, int) or max_n < 2:
        raise ValueError(f"max_n must be an int >= 2, got {max_n!r}")

    delta_budget_deg = phase_budget_deg(rcsr_db)
    if theta_min_deg is None:
        theta_min_deg = math.degrees(wavelength_m / (2.0 * min(lx_m, ly_m)))
    else:
        theta_min_deg = _require_positive_finite("theta_min_deg", theta_min_deg)

    best: tuple[int, int] | None = None
    best_area: int | None = None
    for nx in range(2, max_n + 1):
        if 2 * nx * px_m > lx_m:
            break  # panel-fit only gets tighter as nx grows further
        for ny in range(2, max_n + 1):
            if 2 * ny * py_m > ly_m:
                break
            sin_theta = _diffraction_sin_theta(nx, ny, (px_m, py_m), wavelength_m)
            if sin_theta > 1.0:
                continue  # evanescent -- this block redirects nothing
            if delta_phi_max_deg * boundary_fraction(nx, ny) > delta_budget_deg:
                continue  # coupling error exceeds what the requirement allows
            theta_deg = math.degrees(math.asin(sin_theta))
            if theta_deg < theta_min_deg:
                continue  # lobe would fall back inside the panel's own specular return
            area = nx * ny
            if best_area is None or area < best_area:
                best_area = area
                best = (nx, ny)

    if best is None:
        raise ValueError(
            "no block size up to "
            f"{max_n}x{max_n} cells satisfies docs/supercell-sizing-rule.md Sec 5.5's "
            f"floor and ceiling together: phase budget from rcsr_db={rcsr_db!r} dB is "
            f"{delta_budget_deg:.1f} deg (needs delta_phi_max_deg={delta_phi_max_deg!r} "
            f"* boundary_fraction(Nx, Ny) <= this), ceiling theta_min={theta_min_deg:.2f} "
            f"deg, panel_size_m={panel_size_m!r}, pitch_m={pitch_m!r}, "
            f"wavelength_m={wavelength_m!r}. Per that document Sec 5.5 this is "
            "conditional on panel size and alphabet, not a fixed verdict -- a larger "
            "panel_size_m, a lower rcsr_db target, or an alphabet with a smaller "
            "delta_phi_max_deg may admit a feasible block."
        )
    return best


def generate_coded_unit_cell_array(
    layout: Sequence[Sequence[str]],
    symbol_library: Mapping[str, dict[str, Any] | list[dict[str, Any]]],
    pitch_m: tuple[float, float],
    delta_phi_max_deg: float,
    rcsr_db: float,
    wavelength_m: float,
    panel_size_m: tuple[float, float],
    theta_min_deg: float | None = None,
    max_block_n: int = 32,
    origin_m: tuple[float, float] = (0.0, 0.0),
    name_prefix: str = "block",
) -> list[dict[str, Any]]:
    """Place a coded surface: a grid of super-cell BLOCKS, each holding one
    Symbol from `symbol_library` tiled `block_size_from_sizing_rule(...)`
    cells across, laid out per `layout` -- the function issue #212 (and Map
    #104 before it) says `generate_unit_cell_array` structurally cannot be,
    because that function copies ONE unit cell to every position and a coded
    surface by definition mixes unlike symbols.

    `layout`: a non-empty, rectangular 2D sequence of symbol ids, one row
    per outer entry -- `layout[j][i]` naming the symbol placed at BLOCK
    position `(i, j)`, where `i` is the column (x) index within a row and
    `j` is the row (y, outer-list) index, so `layout[0]` is the row of
    blocks at y-index 0 and so on. `(i, j)` is the same axis convention
    `generate_unit_cell_array`'s own per-cell naming uses. Every row must be
    the same length. Each entry is a symbol id (a key into
    `symbol_library`), never raw geometry -- placement is selection, not
    authoring (CONTEXT.md: Symbol alphabet).

    `symbol_library`: the Element/Coding-Alphabet library entries this call
    may draw from, as `{symbol_id: unit_cell_primitives}` -- each value
    already in `generate_unit_cell_array`'s own `unit_cell` shape (a single
    "box"/"polygon" primitive dict, or a list of them, e.g.
    `combine_shapes()`'s return value). This function never invents or
    assumes a symbol's geometry inline (#109): every id `layout` names is
    looked up here, and every id with no entry raises `SymbolNotFoundError`
    (all misses reported together, not one at a time -- see
    `_resolve_symbol_library`) rather than silently substituting a default.
    In production this mapping is expected to come from a real Element/
    Coding-Alphabet library lookup (no such persistent store exists in this
    tree yet -- see this module's module docstring and CONTEXT.md's Element/
    Coding-Alphabet library entry); a caller wires that source in here, the
    same "caller fetches, this function only resolves" seam
    `designs.material_properties.resolve_material_property` already uses for
    its own accumulate-once-and-reuse library.

    `pitch_m`: the FINE (single-cell) lattice pitch within a block --
    `generate_unit_cell_array`'s own `spacing_m`, not the block pitch.

    `delta_phi_max_deg`, `rcsr_db`, `wavelength_m`, `panel_size_m`,
    `theta_min_deg`, `max_block_n`: forwarded to
    `block_size_from_sizing_rule` to derive the block size actually used --
    see that function's docstring. The requirement drives the block size;
    nothing here hardcodes one (issue #212's acceptance criterion).

    `origin_m`, `name_prefix`: as `generate_unit_cell_array`.

    Each block is generated by ONE `generate_unit_cell_array` call (that
    block's resolved symbol geometry, `spacing_m=pitch_m`,
    `count=block_size`, `origin_m` offset to that block's own corner,
    `name_prefix=f"{name_prefix}_{i}_{j}"`) -- this function places blocks
    and resolves symbols; `generate_unit_cell_array` still does every bit of
    the actual per-cell coordinate translation, unchanged.

    Returns a flat list of primitive dicts covering the whole coded surface,
    each uniquely named `f"{name_prefix}_{i}_{j}_..."` (the block's own
    per-cell/per-primitive suffix from `generate_unit_cell_array`
    appended).

    Raises `ValueError` if `layout` is empty or ragged, `SymbolNotFoundError`
    (a `ValueError` subclass) if `layout` names a symbol id absent from
    `symbol_library`, and whatever `block_size_from_sizing_rule` /
    `generate_unit_cell_array` themselves raise for invalid sizing-rule
    inputs or invalid resolved symbol geometry.
    """
    rows = [list(row) for row in layout]
    if not rows or not rows[0]:
        raise ValueError("layout must be a non-empty, non-ragged 2D sequence of symbol ids")
    row_len = len(rows[0])
    if any(len(row) != row_len for row in rows):
        raise ValueError(
            "layout must be rectangular -- every row must name the same number of "
            f"block columns, got row lengths {[len(row) for row in rows]}"
        )

    # layout[j][i] holds the symbol for block column i, row j (see this
    # function's own docstring); flatten to validate and resolve every
    # distinct id in one pass regardless of grid shape.
    all_ids = [sid for row in rows for sid in row]
    resolved = _resolve_symbol_library(all_ids, symbol_library)

    block_size = block_size_from_sizing_rule(
        delta_phi_max_deg=delta_phi_max_deg,
        rcsr_db=rcsr_db,
        pitch_m=pitch_m,
        wavelength_m=wavelength_m,
        panel_size_m=panel_size_m,
        theta_min_deg=theta_min_deg,
        max_n=max_block_n,
    )
    block_nx, block_ny = block_size
    px_m, py_m = pitch_m
    ox_m, oy_m = origin_m

    primitives: list[dict[str, Any]] = []
    for j, row in enumerate(rows):
        for i, symbol_id in enumerate(row):
            block_origin = (
                ox_m + i * block_nx * px_m,
                oy_m + j * block_ny * py_m,
            )
            primitives.extend(
                generate_unit_cell_array(
                    resolved[symbol_id],
                    spacing_m=pitch_m,
                    count=block_size,
                    origin_m=block_origin,
                    name_prefix=f"{name_prefix}_{i}_{j}",
                )
            )
    return primitives


# ---------------------------------------------------------------------------
# Printable artwork export (issue #348): combine_shapes()/
# generate_unit_cell_array()/generate_coded_unit_cell_array()'s own "box"/
# "polygon" primitive-dict output, written as SVG or GDSII -- the two
# formats this project's printer software accepts (Gerber is already
# emitted elsewhere, by simulation/kicad_gerber2ems.py's KiCad path; gdstk
# writes SVG directly, and GDSII is its native format).
# ---------------------------------------------------------------------------

# GDSII's own official point-per-polygon ceiling (Polygon.fracture's own
# docstring: "Official GDSII documentation requires that all polygons have
# at most 199 vertices, but 8190 is usually supported by most software").
# 199 is the conservative, universally-safe default; a caller whose printer
# software is confirmed to accept the wider convention can pass 8190
# explicitly.
GDSII_STRICT_MAX_POINTS = 199


def _primitive_footprint_polygon(prim: Mapping[str, Any], idx: int) -> gdstk.Polygon:
    """The flat XY footprint of one output primitive dict (combine_shapes/
    generate_unit_cell_array/generate_coded_unit_cell_array's own "shape":
    "box"/"polygon" vocabulary) as a gdstk.Polygon -- what the artwork
    exporters below actually draw. A "box" primitive's z-extent is not
    printable artwork: the printed pattern is a flat conductor trace (see
    simulation/openems.py's module docstring on sheet-resistance-only
    thickness), so only its XY footprint is kept, exactly as
    generate_unit_cell_array() already treats a box's z coordinate as
    carried-through-unchanged rather than tiled."""
    shape = prim.get("shape", "box")
    if shape == "polygon":
        if "points_m" not in prim:
            raise ValueError(f"primitive {idx} (shape='polygon') missing required field 'points_m'")
        return gdstk.Polygon([(float(x), float(y)) for x, y in prim["points_m"]])
    if shape == "box":
        missing = [f for f in ("p1_m", "p2_m") if f not in prim]
        if missing:
            raise ValueError(f"primitive {idx} (shape='box') missing required field(s): {missing}")
        p1, p2 = prim["p1_m"], prim["p2_m"]
        return gdstk.rectangle((float(p1[0]), float(p1[1])), (float(p2[0]), float(p2[1])))
    raise ValueError(
        f"primitive {idx} 'shape' must be 'box' or 'polygon' for artwork export, got {shape!r}"
    )


def _build_polygon_cell(
    primitives: Sequence[Mapping[str, Any]],
    cell_name: str,
    precision_m: float,
    max_points: int,
) -> gdstk.Cell:
    """One gdstk.Cell holding every primitive's flat footprint, ready for
    either exporter below to write out. Shared so SVG and GDSII export of
    the same element are built from identical geometry, never two
    independently-drifting code paths.

    FRACTURING IS DONE HERE, EXPLICITLY, NOT LEFT TO `Library.write_gds`'s
    OWN AUTO-FRACTURE (issue #348's "does not silently fracture on the
    polygon point limit"). `Library.write_gds` does auto-fracture an
    oversized polygon, but `Polygon.fracture`'s own default `precision` is
    `1e-3` -- calibrated for GDSII's conventional micrometer file unit, the
    exact same trap this module's own docstring already documents for
    `gdstk.boolean`'s default precision. This module's coordinates are
    meters; blindly trusting that auto-fracture would silently apply a
    1-MILLIMETER fracturing tolerance to geometry whose real features can
    be a few tens of microns -- exactly the "silent" failure mode the
    acceptance criterion names, and it would only show up as a visibly
    deformed complex outline, never an error. Fracturing each oversized
    polygon here first, with this project's own fine `precision_m`, means
    `write_gds` never has anything left to auto-fracture."""
    if not primitives:
        raise ValueError("primitives must be a non-empty list")
    cell = gdstk.Cell(cell_name)
    for idx, prim in enumerate(primitives):
        polygon = _primitive_footprint_polygon(prim, idx)
        if len(polygon.points) > max_points:
            cell.add(*polygon.fracture(max_points=max_points, precision=precision_m))
        else:
            cell.add(polygon)
    return cell


def export_polygon_gds(
    primitives: Sequence[Mapping[str, Any]],
    path: str | Path,
    *,
    cell_name: str = "element",
    unit_m: float = 1.0,
    precision_m: float = 1e-9,
    max_points: int = GDSII_STRICT_MAX_POINTS,
) -> str:
    """Write `primitives` (combine_shapes()'s own return value, or any
    other list of this module's "box"/"polygon" primitive dicts) as a
    GDSII file at `path`.

    UNITS, HANDLED EXPLICITLY (issue #348 acceptance criterion): gdstk's
    own `Library` defaults to `unit=1e-6` (micrometers) -- silently
    interpreting this project's meter-valued coordinates as micrometers
    would misrepresent every dimension by a factor of 1e6. `unit_m`
    defaults to `1.0` instead: "1 user unit = 1 meter", so a primitive's
    raw `points_m`/`p1_m`/`p2_m` values are written to the file completely
    unscaled. `precision_m` (default `1e-9`, matching this module's own
    `combine_shapes`/`generate_unit_cell_array` default) is the finest
    representable step, in meters -- also passed explicitly for the
    identical reason, and reused as the fracturing precision (see
    `_build_polygon_cell`'s docstring).

    `max_points` (default `GDSII_STRICT_MAX_POINTS` = 199, the official
    GDSII ceiling) is enforced by fracturing any oversized polygon before
    it ever reaches `Library.write_gds` -- see `_build_polygon_cell`'s
    docstring for why that fracturing cannot be left to `write_gds`'s own
    auto-fracture. Pass `max_points=8190` if the target printer software is
    confirmed to accept the wider, non-strict convention instead.

    Returns `str(path)`. Raises `ValueError` if `primitives` is empty or
    any entry is missing its shape-required field(s), the same discipline
    `combine_shapes`/`generate_unit_cell_array` already apply.
    """
    cell = _build_polygon_cell(primitives, cell_name, precision_m, max_points)
    library = gdstk.Library(name=cell_name, unit=unit_m, precision=precision_m)
    library.add(cell)
    library.write_gds(str(path), max_points=max_points)
    return str(path)


def export_polygon_svg(
    primitives: Sequence[Mapping[str, Any]],
    path: str | Path,
    *,
    cell_name: str = "element",
    precision_m: float = 1e-9,
    max_points: int = GDSII_STRICT_MAX_POINTS,
    scaling: float = 1e4,
) -> str:
    """Write `primitives` (combine_shapes()'s own return value, or any
    other list of this module's "box"/"polygon" primitive dicts) as an SVG
    image at `path` -- the second of the two artwork formats issue #348
    names as what this project's printer software accepts.

    SVG has no physical-unit metadata the way a GDSII file does (gdstk's
    own `Cell.write_svg` takes a plain `scaling` multiplier on raw
    coordinate values, nothing more) -- so unlike `export_polygon_gds`,
    there is no unit trap to avoid here, only a sizing one: this project's
    coordinates are meters, and gdstk's own `scaling` default (10) would
    draw a millimeter-scale RF element as a sub-pixel dot. `scaling`
    defaults to `1e4` instead (1 mm -> 10 px, a legible on-screen size for
    the sub-centimeter unit cells this project actually draws), stated
    explicitly here rather than left to a default calibrated for a
    different unit convention -- pass a different value for a much
    larger/smaller element.

    Still fractures any polygon over `max_points` first (default
    `GDSII_STRICT_MAX_POINTS`, see `_build_polygon_cell`'s docstring) even
    though SVG itself has no vertex-count ceiling -- this keeps the SVG and
    GDSII exports of the same `primitives` drawing IDENTICAL geometry
    rather than one silently differing from the other.

    Returns `str(path)`. Raises `ValueError` under the same conditions as
    `export_polygon_gds`.
    """
    cell = _build_polygon_cell(primitives, cell_name, precision_m, max_points)
    cell.write_svg(str(path), scaling=scaling)
    return str(path)
