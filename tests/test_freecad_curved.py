"""Tests for the FreeCAD headless curved/conformal host-surface geometry
generator (issue #66).

Mirrors tests/test_geometry_unit_cell.py's own testing approach (issue #55):
the pure curvature-mapping math (surface_frame_at()) and the geometry-dict
output shape (map_unit_cell_layout_to_curved_surface()) are exercised
directly, with NO FreeCAD/FreeCADCmd install required and no subprocess
involved at all -- these assert the correct geometry-dict shape for a given
curvature/unit-cell spec independent of any simulator (or, here, of FreeCAD
itself) consuming it, per this ticket's own acceptance criterion. A separate
cross-check (test_map_unit_cell_layout_polygon_output_feeds_openems_xml
below) confirms that output shape really is consumable by
simulation.openems.generate_openems_xml, without geometry/freecad_curved.py
itself depending on that module (it does not import simulation/ at all --
see its own module docstring).

The subprocess half (_run_freecadcmd/run_freecad_curved_geometry) is
exercised only against a small fake "FreeCADCmd" Python-shebang script,
following this repo's established fake-executable-script pattern used by
every subprocess-based adapter (see tests/test_elmer.py's module docstring
for the discipline this mirrors) -- FreeCADCmd is not installed in this
environment.
"""

import json
import math
import stat
import sys
from pathlib import Path

import pytest

from geometry.freecad_curved import (
    FreecadGeometryError,
    _nearest_cardinal_axis,
    generate_freecad_macro,
    map_unit_cell_layout_to_curved_surface,
    run_freecad_curved_geometry,
    surface_frame_at,
)

CYLINDER_Z = {"kind": "cylinder", "radius_m": 1.0, "axis": "z"}


def _make_fake_py(tmp_path: Path, name: str, body: str) -> Path:
    """Write a small fake Python-shebang executable, chmod'd executable --
    mirrors tests/test_elmer.py's own `_make_fake_py`."""
    script = tmp_path / name
    script.write_text(f"#!{sys.executable}\n" + body)
    script.chmod(script.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return script


# ---------------------------------------------------------------------------
# surface_frame_at: pure curvature math
# ---------------------------------------------------------------------------


def test_surface_frame_at_cylinder_reference_point():
    frame = surface_frame_at(0.0, 0.0, CYLINDER_Z)
    assert frame["position_m"] == pytest.approx([1.0, 0.0, 0.0])
    assert frame["normal"] == pytest.approx([1.0, 0.0, 0.0])
    assert frame["tangent_u"] == pytest.approx([0.0, 1.0, 0.0])
    assert frame["tangent_v"] == pytest.approx([0.0, 0.0, 1.0])


def test_surface_frame_at_cylinder_quarter_turn():
    radius = 2.0
    curvature = {"kind": "cylinder", "radius_m": radius, "axis": "z"}
    # A quarter of the circumference: theta = pi/2.
    frame = surface_frame_at(radius * math.pi / 2, 0.0, curvature)
    assert frame["position_m"] == pytest.approx([0.0, radius, 0.0], abs=1e-9)
    assert frame["normal"] == pytest.approx([0.0, 1.0, 0.0], abs=1e-9)
    assert frame["tangent_u"] == pytest.approx([-1.0, 0.0, 0.0], abs=1e-9)
    assert frame["tangent_v"] == pytest.approx([0.0, 0.0, 1.0], abs=1e-9)


def test_surface_frame_at_cylinder_axial_translation_is_linear():
    frame = surface_frame_at(0.0, 5.0, CYLINDER_Z)
    assert frame["position_m"] == pytest.approx([1.0, 0.0, 5.0])
    assert frame["normal"] == pytest.approx([1.0, 0.0, 0.0])


def test_surface_frame_at_cylinder_different_axis():
    curvature = {"kind": "cylinder", "radius_m": 1.0, "axis": "x"}
    # axis="x" -> cyclic pair is (y, z); theta=0 -> position along +y.
    frame = surface_frame_at(0.0, 0.0, curvature)
    assert frame["position_m"] == pytest.approx([0.0, 1.0, 0.0])
    assert frame["normal"] == pytest.approx([0.0, 1.0, 0.0])
    assert frame["tangent_v"] == pytest.approx([1.0, 0.0, 0.0])  # e_axis = x


def test_surface_frame_at_cylinder_frame_is_orthonormal():
    curvature = {"kind": "cylinder", "radius_m": 3.0, "axis": "y", "theta0_rad": 0.7}
    frame = surface_frame_at(1.234, -0.5, curvature)
    n = frame["normal"]
    tu = frame["tangent_u"]
    tv = frame["tangent_v"]
    for vec in (n, tu, tv):
        assert sum(c * c for c in vec) == pytest.approx(1.0)
    assert sum(a * b for a, b in zip(n, tu, strict=True)) == pytest.approx(0.0, abs=1e-9)
    assert sum(a * b for a, b in zip(n, tv, strict=True)) == pytest.approx(0.0, abs=1e-9)
    assert sum(a * b for a, b in zip(tu, tv, strict=True)) == pytest.approx(0.0, abs=1e-9)


def test_surface_frame_at_sphere_reference_point():
    frame = surface_frame_at(0.0, 0.0, {"kind": "sphere", "radius_m": 1.0, "axis": "z"})
    assert frame["position_m"] == pytest.approx([1.0, 0.0, 0.0])
    assert frame["normal"] == pytest.approx([1.0, 0.0, 0.0])
    assert frame["tangent_u"] == pytest.approx([0.0, 1.0, 0.0])
    assert frame["tangent_v"] == pytest.approx([0.0, 0.0, 1.0])


def test_surface_frame_at_sphere_frame_is_orthonormal_off_equator():
    curvature = {"kind": "sphere", "radius_m": 2.0, "axis": "z", "phi0_rad": 0.3}
    frame = surface_frame_at(0.4, 0.6, curvature)
    n = frame["normal"]
    tu = frame["tangent_u"]
    tv = frame["tangent_v"]
    for vec in (n, tu, tv):
        assert sum(c * c for c in vec) == pytest.approx(1.0)
    assert sum(a * b for a, b in zip(n, tu, strict=True)) == pytest.approx(0.0, abs=1e-9)
    assert sum(a * b for a, b in zip(n, tv, strict=True)) == pytest.approx(0.0, abs=1e-9)
    assert sum(a * b for a, b in zip(tu, tv, strict=True)) == pytest.approx(0.0, abs=1e-9)


def test_surface_frame_at_sphere_near_pole_raises():
    with pytest.raises(ValueError, match="pole"):
        surface_frame_at(0.0, 0.0, {"kind": "sphere", "radius_m": 1.0, "phi0_rad": math.pi / 2})


def test_surface_frame_at_missing_radius_raises():
    with pytest.raises(ValueError, match="radius_m"):
        surface_frame_at(0.0, 0.0, {"kind": "cylinder"})


def test_surface_frame_at_negative_radius_raises():
    with pytest.raises(ValueError, match="radius_m"):
        surface_frame_at(0.0, 0.0, {"kind": "cylinder", "radius_m": -1.0})


def test_surface_frame_at_invalid_axis_raises():
    with pytest.raises(ValueError, match="axis"):
        surface_frame_at(0.0, 0.0, {"kind": "cylinder", "radius_m": 1.0, "axis": "w"})


def test_surface_frame_at_invalid_kind_raises():
    with pytest.raises(ValueError, match="kind"):
        surface_frame_at(0.0, 0.0, {"kind": "cone", "radius_m": 1.0})


# ---------------------------------------------------------------------------
# _nearest_cardinal_axis
# ---------------------------------------------------------------------------


def test_nearest_cardinal_axis_picks_dominant_component():
    assert _nearest_cardinal_axis([0.9, 0.1, 0.0]) == "x"
    assert _nearest_cardinal_axis([0.0, -0.99, 0.05]) == "y"
    assert _nearest_cardinal_axis([0.1, 0.1, 0.98]) == "z"


# ---------------------------------------------------------------------------
# map_unit_cell_layout_to_curved_surface: box input
# ---------------------------------------------------------------------------


def test_map_box_primitive_at_reference_point():
    box = {
        "name": "patch",
        "shape": "box",
        "p1_m": [-0.001, -0.001, 0.0],
        "p2_m": [0.001, 0.001, 0.0],
    }
    result = map_unit_cell_layout_to_curved_surface([box], CYLINDER_Z)
    assert len(result) == 1
    prim = result[0]
    assert prim["name"] == "patch"
    assert prim["shape"] == "polygon"
    assert prim["normal_axis"] == "x"  # normal at theta=0 is +x
    assert prim["elevation_m"] == pytest.approx(1.0)
    assert len(prim["points_m"]) == 4
    # At theta=0 the tangent frame maps local x->y, local y->z 1:1, so the
    # footprint's own shape/size is preserved (just relabeled y,z).
    ys = [p[0] for p in prim["points_m"]]
    zs = [p[1] for p in prim["points_m"]]
    assert min(ys) == pytest.approx(-0.001)
    assert max(ys) == pytest.approx(0.001)
    assert min(zs) == pytest.approx(-0.001)
    assert max(zs) == pytest.approx(0.001)
    assert prim["approx_sag_m"] > 0.0


def test_map_box_primitive_default_name():
    box = {"shape": "box", "p1_m": [-0.001, -0.001, 0.0], "p2_m": [0.001, 0.001, 0.0]}
    result = map_unit_cell_layout_to_curved_surface([box], CYLINDER_Z, name_prefix="foo")
    assert result[0]["name"] == "foo_0"


def test_map_box_primitive_thickness_collapses_to_z_center_elevation():
    box = {
        "shape": "box",
        "p1_m": [-0.001, -0.001, 0.0014],
        "p2_m": [0.001, 0.001, 0.0018],
    }
    result = map_unit_cell_layout_to_curved_surface([box], CYLINDER_Z)
    # z-center of the box (0.0016) is added along the true local normal.
    assert result[0]["elevation_m"] == pytest.approx(1.0016)


def test_map_multiple_box_primitives_around_the_cylinder():
    radius = 1.0
    curvature = {"kind": "cylinder", "radius_m": radius, "axis": "z"}
    box = {"shape": "box", "p1_m": [-0.01, -0.01, 0.0], "p2_m": [0.01, 0.01, 0.0]}
    # Place three cells at u = 0, radius*pi/2, radius*pi (quarter turns).
    cells = []
    for i, u in enumerate([0.0, radius * math.pi / 2, radius * math.pi]):
        cell = dict(box)
        cell["p1_m"] = [u - 0.01, -0.01, 0.0]
        cell["p2_m"] = [u + 0.01, 0.01, 0.0]
        cell["name"] = f"cell{i}"
        cells.append(cell)
    result = map_unit_cell_layout_to_curved_surface(cells, curvature)
    assert len(result) == 3
    normal_axes = {p["name"]: p["normal_axis"] for p in result}
    # theta=0 -> normal +x; theta=pi/2 -> normal +y; theta=pi -> normal -x
    # (still nearest to the x axis).
    assert normal_axes["cell0"] == "x"
    assert normal_axes["cell1"] == "y"
    assert normal_axes["cell2"] == "x"


# ---------------------------------------------------------------------------
# map_unit_cell_layout_to_curved_surface: polygon input
# ---------------------------------------------------------------------------


def test_map_polygon_primitive_at_reference_point():
    poly = {
        "shape": "polygon",
        "points_m": [[-0.0005, -0.0005], [0.0005, -0.0005], [0.0, 0.0005]],
        "normal_axis": "z",
        "elevation_m": 0.0016,
    }
    result = map_unit_cell_layout_to_curved_surface([poly], CYLINDER_Z)
    prim = result[0]
    assert prim["shape"] == "polygon"
    assert prim["normal_axis"] == "x"
    assert prim["elevation_m"] == pytest.approx(1.0016)
    assert len(prim["points_m"]) == 3


def test_map_polygon_wrong_normal_axis_raises():
    poly = {
        "shape": "polygon",
        "points_m": [[0.0, 0.0], [0.001, 0.0], [0.0, 0.001]],
        "normal_axis": "x",
    }
    with pytest.raises(ValueError, match="normal_axis"):
        map_unit_cell_layout_to_curved_surface([poly], CYLINDER_Z)


def test_map_polygon_too_few_points_raises():
    poly = {"shape": "polygon", "points_m": [[0.0, 0.0], [1.0, 0.0]]}
    with pytest.raises(ValueError, match="at least 3"):
        map_unit_cell_layout_to_curved_surface([poly], CYLINDER_Z)


def test_map_polygon_missing_points_m_raises():
    with pytest.raises(ValueError, match="points_m"):
        map_unit_cell_layout_to_curved_surface([{"shape": "polygon"}], CYLINDER_Z)


# ---------------------------------------------------------------------------
# map_unit_cell_layout_to_curved_surface: validation
# ---------------------------------------------------------------------------


def test_map_empty_primitives_raises():
    with pytest.raises(ValueError, match="non-empty"):
        map_unit_cell_layout_to_curved_surface([], CYLINDER_Z)


def test_map_missing_radius_raises():
    box = {"shape": "box", "p1_m": [0, 0, 0], "p2_m": [0.001, 0.001, 0.0]}
    with pytest.raises(ValueError, match="radius_m"):
        map_unit_cell_layout_to_curved_surface([box], {"kind": "cylinder"})


def test_map_cell_too_large_for_curvature_raises():
    box = {"shape": "box", "p1_m": [-2.0, -2.0, 0.0], "p2_m": [2.0, 2.0, 0.0]}
    with pytest.raises(ValueError, match="curvature radius"):
        map_unit_cell_layout_to_curved_surface([box], CYLINDER_Z)


def test_map_cylinder_primitive_shape_rejected():
    prim = {"shape": "cylinder", "p1_m": [0, 0, 0], "p2_m": [0, 0, 0.001], "radius_m": 0.0005}
    with pytest.raises(ValueError, match="cylinder"):
        map_unit_cell_layout_to_curved_surface([prim], CYLINDER_Z)


def test_map_box_missing_field_raises():
    with pytest.raises(ValueError, match="p2_m"):
        map_unit_cell_layout_to_curved_surface([{"shape": "box", "p1_m": [0, 0, 0]}], CYLINDER_Z)


# ---------------------------------------------------------------------------
# Cross-check against simulation/openems.py's own polygon primitive
# consumer -- confirms the "same existing geometry-dict primitive shape"
# acceptance criterion without geometry/freecad_curved.py itself importing
# that module (mirrors tests/test_geometry_unit_cell.py's own cross-check).
# ---------------------------------------------------------------------------


def test_map_unit_cell_layout_polygon_output_feeds_openems_xml():
    import xml.etree.ElementTree as ET

    from simulation.openems import generate_openems_xml

    box = {
        "name": "patch",
        "shape": "box",
        "p1_m": [-0.001, -0.001, 0.0016],
        "p2_m": [0.001, 0.001, 0.0016],
    }
    curvature = {"kind": "cylinder", "radius_m": 0.05, "axis": "z"}
    curved = map_unit_cell_layout_to_curved_surface([box], curvature)

    geometry = {
        "conductors": curved,
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
            "x_lines_m": [0.0, 0.06],
            "y_lines_m": [0.0, 0.06],
            "z_lines_m": [0.0, 0.0016],
        },
        "frequency_hz": 10e9,
    }
    xml_text = generate_openems_xml(geometry)
    root = ET.fromstring(xml_text)
    polygons = root.findall(".//Polygon")
    assert len(polygons) == 1
    poly = polygons[0]
    assert poly.get("NormDir") == "0"  # snapped to the x axis at theta=0
    assert int(poly.get("QtyVertices")) == len(poly.findall("Vertex"))
    assert int(poly.get("QtyVertices")) == 4


# ---------------------------------------------------------------------------
# generate_freecad_macro: pure string-content checks, no subprocess.
# ---------------------------------------------------------------------------


def test_generate_freecad_macro_contains_expected_api_calls():
    box = {
        "name": "patch",
        "shape": "box",
        "p1_m": [-0.001, -0.001, 0.0],
        "p2_m": [0.001, 0.001, 0.0016],
    }
    macro = generate_freecad_macro([box], CYLINDER_Z)
    assert "import FreeCAD as App" in macro
    assert "import Part" in macro
    assert 'App.newDocument("CurvedUnitCellArray")' in macro
    assert "Part.makePolygon(pts, True)" in macro
    assert "Part.Face([wire])" in macro
    assert ".extrude(" in macro
    assert 'doc.addObject("Part::Feature", \'patch\')' in macro
    assert "feature.Placement = App.Placement(App.Vector(*" in macro
    assert "App.Rotation())" in macro
    assert "Part.makeCompound(built_shapes)" in macro
    assert ".exportStep(step_file)" in macro
    assert "json.dump(status, _status_fh)" in macro
    assert "App.closeDocument(doc.Name)" in macro


def test_generate_freecad_macro_is_valid_python_syntax():
    box = {"shape": "box", "p1_m": [-0.001, -0.001, 0.0], "p2_m": [0.001, 0.001, 0.0]}
    poly = {
        "shape": "polygon",
        "points_m": [[0.0, 0.0], [0.001, 0.0], [0.0, 0.001]],
        "elevation_m": 0.0016,
    }
    macro = generate_freecad_macro([box, poly], CYLINDER_Z)
    compile(macro, "<freecad_macro>", "exec")


def test_generate_freecad_macro_polygon_has_no_extrude_call_for_its_object():
    poly = {
        "name": "srr",
        "shape": "polygon",
        "points_m": [[0.0, 0.0], [0.001, 0.0], [0.0, 0.001]],
    }
    macro = generate_freecad_macro([poly], CYLINDER_Z)
    # The polygon object's own shape is the bare face -- no .extrude call.
    assert "shape = face\n" in macro
    assert ".extrude(" not in macro


def test_generate_freecad_macro_empty_primitives_raises():
    with pytest.raises(ValueError, match="non-empty"):
        generate_freecad_macro([], CYLINDER_Z)


# ---------------------------------------------------------------------------
# _run_freecadcmd / run_freecad_curved_geometry subprocess contract --
# fake-executable pattern, no real FreeCADCmd install required.
# ---------------------------------------------------------------------------

_FAKE_FREECADCMD_SUCCESS = """
import sys, json
script = sys.argv[1]
with open(script) as f:
    text = f.read()
assert "CurvedUnitCellArray" in text
status = {
    "objects_built": ["patch_0"],
    "errors": [],
    "step_file": "curved_unit_cell_array.step",
    "total_input": 1,
}
with open("curved_unit_cell_array_status.json", "w") as f:
    json.dump(status, f)
with open("curved_unit_cell_array.step", "w") as f:
    f.write("ISO-10303-21;\\nfake step file\\nEND-ISO-10303-21;\\n")
sys.stdout.write("FreeCAD fake run complete\\n")
sys.exit(0)
"""

_FAKE_FREECADCMD_FAILURE = """
import sys
sys.stderr.write("ERROR: FreeCAD initialization failed\\n")
sys.exit(1)
"""

_FAKE_FREECADCMD_NO_STATUS_FILE = """
import sys
sys.stdout.write("ran but wrote nothing\\n")
sys.exit(0)
"""

_BOX = {"name": "patch", "shape": "box", "p1_m": [-0.001, -0.001, 0.0], "p2_m": [0.001, 0.001, 0.0]}


def test_run_freecad_curved_geometry_end_to_end_with_fake_executable(tmp_path: Path):
    script = _make_fake_py(tmp_path, "fake_freecadcmd.py", _FAKE_FREECADCMD_SUCCESS)

    result = run_freecad_curved_geometry(
        [_BOX],
        CYLINDER_Z,
        workdir=str(tmp_path / "run"),
        executable=str(script),
        timeout_s=10,
    )

    assert result["provenance"] == "SIMULATED"
    assert result["simulator"] == "FreeCADCmd"
    assert result["status"] == "COMPLETED"
    # The geometry-dict mapping is real and computed regardless of the fake
    # tool's own output.
    assert len(result["primitives"]) == 1
    assert result["primitives"][0]["shape"] == "polygon"
    assert result["freecad"]["objects_built"] == ["patch_0"]
    assert result["freecad"]["errors"] == []
    assert result["freecad"]["step_file"] is not None
    assert Path(result["freecad"]["step_file"]).exists()
    assert Path(result["macro_file"]).exists()


def test_run_freecad_curved_geometry_propagates_error_on_nonzero_exit(tmp_path: Path):
    script = _make_fake_py(tmp_path, "fake_freecadcmd_fail.py", _FAKE_FREECADCMD_FAILURE)

    with pytest.raises(FreecadGeometryError, match="initialization failed"):
        run_freecad_curved_geometry(
            [_BOX],
            CYLINDER_Z,
            workdir=str(tmp_path / "run2"),
            executable=str(script),
            timeout_s=10,
        )


def test_run_freecad_curved_geometry_missing_status_file_is_honestly_noted(tmp_path: Path):
    script = _make_fake_py(tmp_path, "fake_freecadcmd_nostatus.py", _FAKE_FREECADCMD_NO_STATUS_FILE)

    result = run_freecad_curved_geometry(
        [_BOX],
        CYLINDER_Z,
        workdir=str(tmp_path / "run3"),
        executable=str(script),
        timeout_s=10,
    )

    assert result["status"] == "COMPLETED"
    assert result["freecad"]["objects_built"] == []
    assert result["freecad"]["step_file"] is None
    assert "note" in result["freecad"]


def test_run_freecad_curved_geometry_rejects_bad_geometry_before_subprocess(tmp_path: Path):
    # An oversized cell is rejected by map_unit_cell_layout_to_curved_surface
    # before any subprocess is even attempted -- use a nonexistent
    # executable to prove the subprocess step is never reached.
    big_box = {"shape": "box", "p1_m": [-2.0, -2.0, 0.0], "p2_m": [2.0, 2.0, 0.0]}
    with pytest.raises(ValueError, match="curvature radius"):
        run_freecad_curved_geometry(
            [big_box],
            CYLINDER_Z,
            workdir=str(tmp_path / "run4"),
            executable="definitely_not_a_real_executable_xyz",
            timeout_s=10,
        )


def test_run_freecadcmd_missing_executable_raises(tmp_path: Path):
    with pytest.raises(FreecadGeometryError, match="not found"):
        run_freecad_curved_geometry(
            [_BOX],
            CYLINDER_Z,
            workdir=str(tmp_path / "run5"),
            executable="definitely_not_a_real_executable_xyz",
            timeout_s=10,
        )


def test_run_freecad_curved_geometry_timeout_raises(tmp_path: Path):
    script = _make_fake_py(tmp_path, "fake_freecadcmd_slow.py", "import time\ntime.sleep(5)\n")
    with pytest.raises(FreecadGeometryError, match="timed out"):
        run_freecad_curved_geometry(
            [_BOX],
            CYLINDER_Z,
            workdir=str(tmp_path / "run6"),
            executable=str(script),
            timeout_s=1,
        )


def test_run_freecadcmd_picks_up_executable_from_env_var(tmp_path: Path, monkeypatch):
    script = _make_fake_py(tmp_path, "fake_freecadcmd_env.py", _FAKE_FREECADCMD_SUCCESS)
    monkeypatch.setenv("FREECAD_BIN", str(script))

    result = run_freecad_curved_geometry(
        [_BOX], CYLINDER_Z, workdir=str(tmp_path / "run7"), timeout_s=10
    )
    assert result["freecad"]["objects_built"] == ["patch_0"]


def test_run_freecad_curved_geometry_step_file_read_back(tmp_path: Path):
    script = _make_fake_py(tmp_path, "fake_freecadcmd2.py", _FAKE_FREECADCMD_SUCCESS)
    result = run_freecad_curved_geometry(
        [_BOX],
        CYLINDER_Z,
        workdir=str(tmp_path / "run8"),
        executable=str(script),
        timeout_s=10,
    )
    step_text = Path(result["freecad"]["step_file"]).read_text()
    assert "ISO-10303-21" in step_text


def test_run_freecad_curved_geometry_status_json_is_read_not_guessed(tmp_path: Path):
    """Directly confirms the status file the fake tool wrote round-trips
    through json.loads unchanged (total_input matches what was requested)."""
    script = _make_fake_py(tmp_path, "fake_freecadcmd3.py", _FAKE_FREECADCMD_SUCCESS)
    result = run_freecad_curved_geometry(
        [_BOX],
        CYLINDER_Z,
        workdir=str(tmp_path / "run9"),
        executable=str(script),
        timeout_s=10,
    )
    status_path = Path(result["workdir"]) / "curved_unit_cell_array_status.json"
    on_disk = json.loads(status_path.read_text())
    assert on_disk["total_input"] == 1
    assert result["freecad"]["total_input"] == 1
