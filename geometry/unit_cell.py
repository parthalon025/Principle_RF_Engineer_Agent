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

HONEST CAVEAT: this module's gdstk usage has been exercised against the
real, installed gdstk 1.0.1 library (see tests/test_geometry_unit_cell.py)
-- so, unlike this repo's simulator adapters, there is no "not verified
against a real binary" gap here for gdstk itself. What has NOT been
verified end-to-end is the far side of the pipeline: the polygon/box
primitive dicts this module emits have not been run through a real openEMS
binary (openEMS itself is not installed in this environment -- see
simulation/openems.py's own honest caveat), so while the <Polygon> XML
shape they feed into is verified against CSXCAD's own source, an actual
openEMS FDTD run consuming a gdstk-generated unit-cell array has not been
performed.
"""

from __future__ import annotations

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
