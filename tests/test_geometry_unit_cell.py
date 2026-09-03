"""Tests for gdstk-based unit-cell shape composition and periodic planar
array generation (issue #55).

Unlike this repo's simulator adapters (NEC2++/openEMS/HFSS), gdstk is a
small, freely pip-installable library with prebuilt wheels and no license
gate -- it is genuinely installed in this environment (see pyproject.toml's
`geometry` extra) and these tests exercise the REAL gdstk 1.0.1 library
directly, not a fake/stub. See geometry/unit_cell.py's module docstring for
the gdstk API citations (Polygon/rectangle/boolean, fetched from
heitzmann.github.io/gdstk and cross-checked empirically) and the
precision_m unit-conversion rationale.

The output primitive-dict shape (each with "shape": "box"/"polygon" plus
p1_m/p2_m/points_m/normal_axis/elevation_m) is checked independently of any
simulator -- these tests never import simulation/openems.py, matching this
module's own "independent of any simulator consuming it" design (see
geometry/unit_cell.py's module docstring). A separate cross-check
(test_generate_unit_cell_array_polygon_output_feeds_openems_xml below)
confirms that output shape really is consumable by
simulation.openems.generate_openems_xml, without geometry/unit_cell.py
itself depending on that module.

gdstk lives behind this project's new `geometry` optional extra (see
pyproject.toml, matching the existing hfss/measurement extras' pattern of
"most installs, including a bare `uv sync`, won't touch this by default").
This whole module is SKIPPED (not failed/errored) via the importorskip
below when gdstk isn't installed, so a plain `uv sync && uv run pytest`
does not newly break -- run `uv sync --extra geometry` first to actually
exercise these tests.
"""

import math

import pytest

gdstk = pytest.importorskip(
    "gdstk", reason="gdstk not installed -- run `uv sync --extra geometry` first"
)

from geometry.unit_cell import (  # noqa: E402 -- must follow the importorskip guard above
    combine_shapes,
    generate_metamaterial_array,
    generate_unit_cell_array,
)

# ---------------------------------------------------------------------------
# combine_shapes: single shape (no boolean op needed)
# ---------------------------------------------------------------------------


def test_combine_shapes_single_box_becomes_one_polygon():
    result = combine_shapes([{"kind": "box", "p1_m": [0.0, 0.0], "p2_m": [0.002, 0.001]}])
    assert len(result) == 1
    prim = result[0]
    assert prim["shape"] == "polygon"
    assert prim["normal_axis"] == "z"
    assert prim["elevation_m"] == pytest.approx(0.0)
    points = prim["points_m"]
    assert len(points) == 4
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    assert min(xs) == pytest.approx(0.0)
    assert max(xs) == pytest.approx(0.002)
    assert min(ys) == pytest.approx(0.0)
    assert max(ys) == pytest.approx(0.001)


def test_combine_shapes_single_polygon_passthrough():
    points = [[0.0, 0.0], [0.001, 0.0], [0.0005, 0.001]]
    result = combine_shapes([{"kind": "polygon", "points_m": points}])
    assert len(result) == 1
    out_points = {tuple(round(c, 9) for c in p) for p in result[0]["points_m"]}
    in_points = {tuple(p) for p in points}
    assert out_points == in_points


def test_combine_shapes_custom_normal_axis_and_elevation():
    result = combine_shapes(
        [{"kind": "box", "p1_m": [0.0, 0.0], "p2_m": [0.001, 0.001]}],
        normal_axis="x",
        elevation_m=0.0025,
    )
    assert result[0]["normal_axis"] == "x"
    assert result[0]["elevation_m"] == pytest.approx(0.0025)


# ---------------------------------------------------------------------------
# combine_shapes: boolean composition -- a split-ring resonator (SRR),
# the canonical non-rectilinear metamaterial unit-cell shape this ticket
# names explicitly.
# ---------------------------------------------------------------------------


def test_combine_shapes_srr_ring_via_subtract():
    """An SRR ring: an outer square minus a smaller concentric square ->
    one closed annulus outline (gdstk's own single-loop-with-seam
    representation, see module docstring citation)."""
    shapes = [
        {"kind": "box", "p1_m": [0.0, 0.0], "p2_m": [0.004, 0.004]},
        {
            "kind": "box",
            "p1_m": [0.0005, 0.0005],
            "p2_m": [0.0035, 0.0035],
            "operation": "subtract",
        },
    ]
    result = combine_shapes(shapes, name_prefix="srr")
    assert len(result) == 1
    prim = result[0]
    assert prim["name"] == "srr"
    assert prim["shape"] == "polygon"
    # A ring traced as one simple polygon needs more than 4 vertices (an
    # outer loop, an inner loop, and a connecting seam).
    assert len(prim["points_m"]) > 4
    # The outline must stay within the outer square's bounding box.
    xs = [p[0] for p in prim["points_m"]]
    ys = [p[1] for p in prim["points_m"]]
    assert min(xs) >= -1e-9
    assert max(xs) <= 0.004 + 1e-9
    assert min(ys) >= -1e-9
    assert max(ys) <= 0.004 + 1e-9


def test_combine_shapes_srr_with_gap_notch():
    """A full SRR: ring (outer minus inner) minus a thin gap-notch rectangle
    -- exercises a THIRD shape in the composition chain."""
    shapes = [
        {"kind": "box", "p1_m": [0.0, 0.0], "p2_m": [0.004, 0.004]},
        {
            "kind": "box",
            "p1_m": [0.0005, 0.0005],
            "p2_m": [0.0035, 0.0035],
            "operation": "subtract",
        },
        {
            "kind": "box",
            "p1_m": [0.0019, 0.0035],
            "p2_m": [0.0021, 0.004],
            "operation": "subtract",
        },
    ]
    result = combine_shapes(shapes, name_prefix="srr_gapped")
    assert len(result) == 1
    # Cutting the gap notch splits the annulus's closed loop open, which
    # must strictly increase the vertex count vs. the ungapped ring.
    ungapped = combine_shapes(shapes[:2])
    assert len(result[0]["points_m"]) > len(ungapped[0]["points_m"])


def test_combine_shapes_jerusalem_cross_via_union():
    """A Jerusalem cross: a central square unioned with two crossing bars --
    exercises the "add" (union/or) operation across multiple shapes."""
    shapes = [
        {"kind": "box", "p1_m": [0.0015, 0.0015], "p2_m": [0.0025, 0.0025]},
        {"kind": "box", "p1_m": [0.0, 0.0018], "p2_m": [0.004, 0.0022], "operation": "add"},
        {"kind": "box", "p1_m": [0.0018, 0.0], "p2_m": [0.0022, 0.004], "operation": "add"},
    ]
    result = combine_shapes(shapes, name_prefix="jerusalem")
    assert len(result) == 1
    xs = [p[0] for p in result[0]["points_m"]]
    ys = [p[1] for p in result[0]["points_m"]]
    # The union spans the full width of the horizontal bar.
    assert min(xs) == pytest.approx(0.0, abs=1e-9)
    assert max(xs) == pytest.approx(0.004, abs=1e-9)
    assert min(ys) == pytest.approx(0.0, abs=1e-9)
    assert max(ys) == pytest.approx(0.004, abs=1e-9)


def test_combine_shapes_intersect_operation():
    shapes = [
        {"kind": "box", "p1_m": [0.0, 0.0], "p2_m": [0.003, 0.003]},
        {"kind": "box", "p1_m": [0.001, 0.001], "p2_m": [0.004, 0.004], "operation": "intersect"},
    ]
    result = combine_shapes(shapes)
    xs = [p[0] for p in result[0]["points_m"]]
    ys = [p[1] for p in result[0]["points_m"]]
    assert min(xs) == pytest.approx(0.001)
    assert max(xs) == pytest.approx(0.003)
    assert min(ys) == pytest.approx(0.001)
    assert max(ys) == pytest.approx(0.003)


def test_combine_shapes_xor_operation_disjoint_regions():
    """XOR of two overlapping squares leaves two disjoint L-ish regions --
    checks the multi-polygon-result naming path (name_prefix + index)."""
    shapes = [
        {"kind": "box", "p1_m": [0.0, 0.0], "p2_m": [0.002, 0.002]},
        {"kind": "box", "p1_m": [0.001, 0.001], "p2_m": [0.003, 0.003], "operation": "xor"},
    ]
    result = combine_shapes(shapes, name_prefix="xor_shape")
    assert len(result) == 2
    names = {p["name"] for p in result}
    assert names == {"xor_shape_0", "xor_shape_1"}
    for prim in result:
        assert prim["shape"] == "polygon"


# ---------------------------------------------------------------------------
# combine_shapes: validation
# ---------------------------------------------------------------------------


def test_combine_shapes_empty_list_raises():
    with pytest.raises(ValueError, match="non-empty"):
        combine_shapes([])


def test_combine_shapes_first_shape_operation_must_be_add():
    with pytest.raises(ValueError, match="operation"):
        combine_shapes(
            [{"kind": "box", "p1_m": [0, 0], "p2_m": [1, 1], "operation": "subtract"}]
        )


def test_combine_shapes_invalid_kind_raises():
    with pytest.raises(ValueError, match="kind"):
        combine_shapes([{"kind": "circle", "p1_m": [0, 0], "p2_m": [1, 1]}])


def test_combine_shapes_invalid_operation_raises():
    with pytest.raises(ValueError, match="operation"):
        combine_shapes(
            [
                {"kind": "box", "p1_m": [0, 0], "p2_m": [1, 1]},
                {"kind": "box", "p1_m": [0, 0], "p2_m": [1, 1], "operation": "melt"},
            ]
        )


def test_combine_shapes_invalid_normal_axis_raises():
    with pytest.raises(ValueError, match="normal_axis"):
        combine_shapes(
            [{"kind": "box", "p1_m": [0, 0], "p2_m": [1, 1]}], normal_axis="w"
        )


def test_combine_shapes_box_missing_field_raises():
    with pytest.raises(ValueError, match="p2_m"):
        combine_shapes([{"kind": "box", "p1_m": [0, 0]}])


def test_combine_shapes_polygon_too_few_points_raises():
    with pytest.raises(ValueError, match="at least 3"):
        combine_shapes([{"kind": "polygon", "points_m": [[0, 0], [1, 1]]}])


def test_combine_shapes_subtract_everything_raises():
    shapes = [
        {"kind": "box", "p1_m": [0.0, 0.0], "p2_m": [0.001, 0.001]},
        {"kind": "box", "p1_m": [-1.0, -1.0], "p2_m": [1.0, 1.0], "operation": "subtract"},
    ]
    with pytest.raises(ValueError, match="removed the entire outline"):
        combine_shapes(shapes)


# ---------------------------------------------------------------------------
# generate_unit_cell_array: box unit cell tiling
# ---------------------------------------------------------------------------


def test_generate_unit_cell_array_box_count_and_names():
    unit_cell = {
        "name": "patch",
        "shape": "box",
        "p1_m": [0.0, 0.0, 0.0016],
        "p2_m": [0.002, 0.002, 0.0016],
    }
    result = generate_unit_cell_array(
        unit_cell, spacing_m=(0.003, 0.0035), count=(3, 2)
    )
    assert len(result) == 6
    names = {p["name"] for p in result}
    assert names == {
        "cell_0_0", "cell_0_1", "cell_1_0", "cell_1_1", "cell_2_0", "cell_2_1",
    }
    for p in result:
        assert p["shape"] == "box"


def test_generate_unit_cell_array_box_translates_xy_only_z_unchanged():
    unit_cell = {
        "shape": "box",
        "p1_m": [0.0, 0.0, 0.001],
        "p2_m": [0.001, 0.0005, 0.0016],
    }
    result = generate_unit_cell_array(unit_cell, spacing_m=(0.002, 0.001), count=(2, 2))
    by_name = {p["name"]: p for p in result}

    cell00 = by_name["cell_0_0"]
    assert cell00["p1_m"] == pytest.approx([0.0, 0.0, 0.001])
    assert cell00["p2_m"] == pytest.approx([0.001, 0.0005, 0.0016])

    cell11 = by_name["cell_1_1"]
    assert cell11["p1_m"] == pytest.approx([0.002, 0.001, 0.001])
    assert cell11["p2_m"] == pytest.approx([0.003, 0.0015, 0.0016])
    # Z (thickness) carried through unchanged for every element.
    assert cell11["p1_m"][2] == pytest.approx(0.001)
    assert cell11["p2_m"][2] == pytest.approx(0.0016)


def test_generate_unit_cell_array_box_honors_origin_m():
    unit_cell = {"shape": "box", "p1_m": [0.0, 0.0, 0.0], "p2_m": [0.001, 0.001, 0.001]}
    result = generate_unit_cell_array(
        unit_cell, spacing_m=(0.002, 0.002), count=(1, 1), origin_m=(0.01, 0.02)
    )
    assert result[0]["p1_m"] == pytest.approx([0.01, 0.02, 0.0])
    assert result[0]["p2_m"] == pytest.approx([0.011, 0.021, 0.001])


# ---------------------------------------------------------------------------
# generate_unit_cell_array: polygon unit cell tiling
# ---------------------------------------------------------------------------


def test_generate_unit_cell_array_polygon_translates_all_vertices():
    unit_cell = {
        "shape": "polygon",
        "points_m": [[0.0, 0.0], [0.001, 0.0], [0.0005, 0.001]],
        "normal_axis": "z",
        "elevation_m": 0.0016,
    }
    result = generate_unit_cell_array(unit_cell, spacing_m=(0.002, 0.0025), count=(2, 1))
    by_name = {p["name"]: p for p in result}

    cell10 = by_name["cell_1_0"]
    assert cell10["shape"] == "polygon"
    assert cell10["normal_axis"] == "z"
    assert cell10["elevation_m"] == pytest.approx(0.0016)
    expected = [[0.002, 0.0], [0.003, 0.0], [0.0025, 0.001]]
    for actual_pt, expected_pt in zip(cell10["points_m"], expected, strict=True):
        assert actual_pt == pytest.approx(expected_pt)


def test_generate_unit_cell_array_multi_primitive_unit_cell_gets_indexed_names():
    """A unit cell built from combine_shapes() output that stayed split
    into multiple disjoint polygons (or any multi-primitive unit cell) gets
    a per-primitive index suffix on top of the per-cell (i, j) suffix."""
    unit_cell = [
        {"shape": "polygon", "points_m": [[0.0, 0.0], [0.001, 0.0], [0.0005, 0.001]]},
        {"shape": "box", "p1_m": [0.0, 0.0, 0.0], "p2_m": [0.0002, 0.0002, 0.0002]},
    ]
    result = generate_unit_cell_array(unit_cell, spacing_m=(0.002, 0.002), count=(1, 1))
    names = {p["name"] for p in result}
    assert names == {"cell_0_0_0", "cell_0_0_1"}


# ---------------------------------------------------------------------------
# generate_unit_cell_array: validation
# ---------------------------------------------------------------------------


def test_generate_unit_cell_array_empty_unit_cell_raises():
    with pytest.raises(ValueError, match="non-empty"):
        generate_unit_cell_array([], spacing_m=(0.001, 0.001), count=(2, 2))


def test_generate_unit_cell_array_zero_count_raises():
    unit_cell = {"shape": "box", "p1_m": [0, 0, 0], "p2_m": [1, 1, 1]}
    with pytest.raises(ValueError, match="count"):
        generate_unit_cell_array(unit_cell, spacing_m=(0.001, 0.001), count=(0, 2))


def test_generate_unit_cell_array_cylinder_shape_rejected():
    unit_cell = {
        "shape": "cylinder",
        "p1_m": [0, 0, 0],
        "p2_m": [0, 0, 0.001],
        "radius_m": 0.0005,
    }
    with pytest.raises(ValueError, match="cylinder"):
        generate_unit_cell_array(unit_cell, spacing_m=(0.001, 0.001), count=(2, 2))


def test_generate_unit_cell_array_box_missing_field_raises():
    unit_cell = {"shape": "box", "p1_m": [0, 0, 0]}
    with pytest.raises(ValueError, match="p2_m"):
        generate_unit_cell_array(unit_cell, spacing_m=(0.001, 0.001), count=(2, 2))


def test_generate_unit_cell_array_polygon_missing_field_raises():
    unit_cell = {"shape": "polygon"}
    with pytest.raises(ValueError, match="points_m"):
        generate_unit_cell_array(unit_cell, spacing_m=(0.001, 0.001), count=(2, 2))


# ---------------------------------------------------------------------------
# generate_metamaterial_array: end-to-end combine_shapes + array convenience
# wrapper.
# ---------------------------------------------------------------------------


def test_generate_metamaterial_array_srr_10x10():
    shapes = [
        {"kind": "box", "p1_m": [0.0, 0.0], "p2_m": [0.004, 0.004]},
        {
            "kind": "box",
            "p1_m": [0.0005, 0.0005],
            "p2_m": [0.0035, 0.0035],
            "operation": "subtract",
        },
    ]
    result = generate_metamaterial_array(
        shapes,
        spacing_m=(0.005, 0.005),
        count=(10, 10),
        elevation_m=0.0016,
    )
    assert len(result) == 100
    names = {p["name"] for p in result}
    assert len(names) == 100  # every element uniquely named
    assert all(p["shape"] == "polygon" for p in result)
    assert all(p["elevation_m"] == pytest.approx(0.0016) for p in result)

    # Spot-check element (5, 7)'s outline is the base SRR shifted by
    # (5*0.005, 7*0.005), by comparing bounding boxes.
    cell = next(p for p in result if p["name"] == "cell_5_7")
    xs = [pt[0] for pt in cell["points_m"]]
    ys = [pt[1] for pt in cell["points_m"]]
    assert min(xs) == pytest.approx(5 * 0.005)
    assert max(xs) == pytest.approx(5 * 0.005 + 0.004)
    assert min(ys) == pytest.approx(7 * 0.005)
    assert max(ys) == pytest.approx(7 * 0.005 + 0.004)


def test_generate_metamaterial_array_no_overlap_between_adjacent_cells():
    """A basic physical sanity check: adjacent array elements' bounding
    boxes must not overlap when spacing exceeds the unit cell's own size."""
    shapes = [{"kind": "box", "p1_m": [0.0, 0.0], "p2_m": [0.001, 0.001]}]
    result = generate_metamaterial_array(shapes, spacing_m=(0.002, 0.002), count=(4, 4))
    cell00 = next(p for p in result if p["name"] == "cell_0_0")
    cell10 = next(p for p in result if p["name"] == "cell_1_0")
    max_x_00 = max(pt[0] for pt in cell00["points_m"])
    min_x_10 = min(pt[0] for pt in cell10["points_m"])
    assert max_x_00 < min_x_10


# ---------------------------------------------------------------------------
# Cross-check against simulation/openems.py's own polygon primitive
# consumer -- confirms the "in that same shape" acceptance criterion
# without geometry/unit_cell.py itself importing that module.
# ---------------------------------------------------------------------------


def test_generate_unit_cell_array_polygon_output_feeds_openems_xml():
    import xml.etree.ElementTree as ET

    from simulation.openems import generate_openems_xml

    shapes = [
        {"kind": "box", "p1_m": [0.0, 0.0], "p2_m": [0.004, 0.004]},
        {
            "kind": "box",
            "p1_m": [0.0005, 0.0005],
            "p2_m": [0.0035, 0.0035],
            "operation": "subtract",
        },
    ]
    array = generate_metamaterial_array(
        shapes, spacing_m=(0.005, 0.005), count=(2, 2), elevation_m=0.0016
    )

    geometry = {
        "conductors": array,
        "ports": [
            {
                "name": "feed",
                "p1_m": [0.0, 0.0, 0.0],
                "p2_m": [0.0, 0.0, 0.0016],
                "direction": "z",
                "resistance_ohms": 50.0,
            }
        ],
        "mesh": {
            "x_lines_m": [0.0, 0.01],
            "y_lines_m": [0.0, 0.01],
            "z_lines_m": [0.0, 0.0016],
        },
        "frequency_hz": 10e9,
    }
    xml_text = generate_openems_xml(geometry)
    root = ET.fromstring(xml_text)
    polygons = root.findall(".//Polygon")
    assert len(polygons) == 4  # 2x2 array
    for poly in polygons:
        assert poly.get("Elevation") == "0.0016"
        assert int(poly.get("QtyVertices")) == len(poly.findall("Vertex"))
        assert int(poly.get("QtyVertices")) > 4  # ring outline, not a plain box


def test_generate_unit_cell_array_box_output_feeds_openems_xml():
    from simulation.openems import generate_openems_xml

    unit_cell = {
        "shape": "box",
        "p1_m": [0.0, 0.0, 0.0016],
        "p2_m": [0.001, 0.001, 0.0016],
    }
    array = generate_unit_cell_array(unit_cell, spacing_m=(0.002, 0.002), count=(3, 3))
    geometry = {
        "conductors": array,
        "ports": [
            {
                "name": "feed",
                "p1_m": [0.0, 0.0, 0.0],
                "p2_m": [0.0, 0.0, 0.0016],
                "direction": "z",
                "resistance_ohms": 50.0,
            }
        ],
        "mesh": {
            "x_lines_m": [0.0, 0.01],
            "y_lines_m": [0.0, 0.01],
            "z_lines_m": [0.0, 0.0016],
        },
        "frequency_hz": 10e9,
    }
    xml_text = generate_openems_xml(geometry)
    # 9 conductor <Metal> properties, one per array element (the port's own
    # Excitation/LumpedElement/ProbeBox primitives also render as <Box>, so
    # count <Metal Name="cell_...">, not raw <Box> tags, to isolate these).
    assert xml_text.count('<Metal Name="cell_') == 9  # 3x3 array


# Guard against an accidental math regression (nx*ny grid, not nx+ny etc.).
def test_generate_unit_cell_array_grid_size_is_product_not_sum():
    unit_cell = {"shape": "box", "p1_m": [0, 0, 0], "p2_m": [1, 1, 1]}
    result = generate_unit_cell_array(unit_cell, spacing_m=(2, 2), count=(4, 5))
    assert len(result) == math.prod((4, 5))
