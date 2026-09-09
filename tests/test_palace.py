"""Tests for the Palace Floquet/periodic-port adapter (issues #61, #210).

No `palace` binary is assumed to exist on the machine running these tests,
so `PalaceSimulator.run()` is exercised here against small fake "palace"
scripts written into `tmp_path`, per the same testing approach used for
NEC2++/openEMS (tests/test_nec2pp.py, tests/test_openems.py): subprocess
plumbing (argument shape, nonzero exit, timeout) and result parsing are
tested; the physics itself is out of scope for automated tests.

Two kinds of sample CSV appear below, and the difference matters:

  - The `SAMPLE_FLOQUET_CSV` fixture is SYNTHETIC -- text this test suite
    writes itself, with round numbers chosen so the dB-and-phase to
    real-and-imaginary arithmetic has a known answer. It proves the
    arithmetic, not the format.
  - `PALACE_REFERENCE_FLOQUET_CSV` and
    `PALACE_REFERENCE_BOTH_POLARIZATIONS_CSV` are columns copied VERBATIM
    out of Palace's own published regression baseline for the "Floquet
    Ports for a Dielectric Grating" example (awslabs/palace commit
    43a5483). Those prove the format. Issue #210 exists because the format
    had only ever been transcribed from prose: the real mode label puts a
    SEMICOLON between the two diffraction-order indices ("S[P1(0;0)TE][1]")
    where the prose in Palace's boundaries.md shows a comma, and the parser
    matched the comma -- so it returned computed=False for every real
    Palace run while passing every synthetic test here.

The adapter has since been run end to end against a real Palace binary; the
record of that run, and the two defects it exposed, is in
docs/palace-floquet-validation.md and in simulation/palace.py's own
"VALIDATED AGAINST A REAL PALACE BINARY" section.
"""

import csv
import io
import json
import math
import os
from pathlib import Path

import pytest
from conftest import make_fake_executable

from simulation.base import SimulatorError
from simulation.palace import (
    BOUND_CONDUCTIVITY_BASE,
    BOUND_X_MAX,
    BOUND_X_MIN,
    BOUND_Y_MAX,
    BOUND_Y_MIN,
    BOUND_Z_MAX,
    BOUND_Z_MIN,
    PalaceSimulator,
    generate_palace_config,
    generate_palace_mesh,
    parse_palace_output,
    run_palace_simulation,
)

# A conductivity sheet (issue #289): a flat, zero-thickness, z-normal
# rectangle at z=0.02m (strictly between the unit cell's own z=0/z=0.08
# Floquet-port faces), representing a real printed-ink conductor, not an
# idealized PEC patch.
CONDUCTIVITY_SHEET_GEOMETRY = {
    "unit_cell": {"lx_m": 0.04, "ly_m": 0.02, "lz_m": 0.08},
    "materials": [
        {
            "name": "ink_patch",
            "p1_m": [0.01, 0.005, 0.02],
            "p2_m": [0.03, 0.015, 0.02],
            "kappa_s_m": 2.0e5,
            "thickness_m": 5e-6,
        }
    ],
    "mesh": {"nx": 1, "ny": 1, "nz": 1},
}

# A unit cell matching the shape of Palace's own "Floquet Ports for a
# Dielectric Grating" example cited in simulation/palace.py's module
# docstring (scaled down for a fast test): a small dielectric bar embedded
# in a vacuum background, periodic in x/y, Floquet ports on z=0/z=lz.
GRATING_GEOMETRY = {
    "unit_cell": {"lx_m": 0.04, "ly_m": 0.01, "lz_m": 0.08},
    "materials": [
        {
            "name": "dielectric_bar",
            "p1_m": [0.01, 0.0, 0.0375],
            "p2_m": [0.03, 0.01, 0.0425],
            "epsilon_r": 7.0,
        }
    ],
    "mesh": {"nx": 1, "ny": 1, "nz": 1},
}


def _make_fake_palace(tmp_path: Path, body: str) -> Path:
    """Write a small fake 'palace' executable (a Python script body,
    launched cross-platform -- see conftest.make_fake_executable)."""
    return make_fake_executable(tmp_path, body, name="fake_palace")


# ---------------------------------------------------------------------------
# Mesh generation
# ---------------------------------------------------------------------------


def test_generate_palace_mesh_header_and_section_shape():
    result = generate_palace_mesh(GRATING_GEOMETRY)
    text = result["mesh_text"]
    lines = text.split("\n")
    assert lines[0] == "MFEM mesh v1.0"
    assert "dimension" in lines
    assert lines[lines.index("dimension") + 1] == "3"
    assert "elements" in lines
    assert "boundary" in lines
    assert "vertices" in lines
    # Vertex section: count line, then "3" (space dimension) -- see module
    # docstring's MFEM v1.0 format citation.
    v_idx = lines.index("vertices")
    assert lines[v_idx + 2] == "3"


def test_generate_palace_mesh_element_and_vertex_counts_match_declared():
    result = generate_palace_mesh(GRATING_GEOMETRY)
    lines = result["mesh_text"].split("\n")
    elements_count_line = lines[lines.index("elements") + 1]
    assert int(elements_count_line) == result["num_elements"]
    boundary_count_line = lines[lines.index("boundary") + 1]
    assert int(boundary_count_line) == result["num_boundary_faces"]
    vertices_count_line = lines[lines.index("vertices") + 1]
    assert int(vertices_count_line) == result["num_vertices"]


def test_generate_palace_mesh_elements_use_cube_geometry_type_5():
    result = generate_palace_mesh(GRATING_GEOMETRY)
    lines = result["mesh_text"].split("\n")
    start = lines.index("elements") + 2
    for line in lines[start : start + result["num_elements"]]:
        fields = line.split()
        assert fields[1] == "5"  # CUBE, see module docstring citation
        assert len(fields) == 2 + 8  # attribute, geom_type, 8 vertex indices


def test_generate_palace_mesh_boundary_faces_use_square_geometry_type_3():
    result = generate_palace_mesh(GRATING_GEOMETRY)
    lines = result["mesh_text"].split("\n")
    start = lines.index("boundary") + 2
    for line in lines[start : start + result["num_boundary_faces"]]:
        fields = line.split()
        assert fields[1] == "3"  # SQUARE, see module docstring citation
        assert len(fields) == 2 + 4  # attribute, geom_type, 4 vertex indices


def test_generate_palace_mesh_boundary_attributes_present():
    result = generate_palace_mesh(GRATING_GEOMETRY)
    lines = result["mesh_text"].split("\n")
    start = lines.index("boundary") + 2
    attrs = {int(line.split()[0]) for line in lines[start : start + result["num_boundary_faces"]]}
    assert attrs == {BOUND_X_MIN, BOUND_X_MAX, BOUND_Y_MIN, BOUND_Y_MAX, BOUND_Z_MIN, BOUND_Z_MAX}


def test_generate_palace_mesh_embedded_material_gets_its_own_domain_attribute():
    result = generate_palace_mesh(GRATING_GEOMETRY)
    lines = result["mesh_text"].split("\n")
    start = lines.index("elements") + 2
    attrs = {int(line.split()[0]) for line in lines[start : start + result["num_elements"]]}
    # 1 = background (vacuum), 2 = the one embedded dielectric bar.
    assert attrs == {1, 2}


def test_generate_palace_mesh_no_materials_is_background_only():
    geometry = {
        "unit_cell": {"lx_m": 0.01, "ly_m": 0.01, "lz_m": 0.01},
        "mesh": {"nx": 1, "ny": 1, "nz": 1},
    }
    result = generate_palace_mesh(geometry)
    lines = result["mesh_text"].split("\n")
    start = lines.index("elements") + 2
    attrs = {int(line.split()[0]) for line in lines[start : start + result["num_elements"]]}
    assert attrs == {1}
    assert result["num_elements"] == 1  # one feature-interval per axis, nx=ny=nz=1


def test_generate_palace_mesh_missing_unit_cell_raises():
    with pytest.raises(ValueError, match="unit_cell"):
        generate_palace_mesh({})


def test_generate_palace_mesh_missing_material_field_raises():
    geometry = {
        "unit_cell": {"lx_m": 0.01, "ly_m": 0.01, "lz_m": 0.01},
        "materials": [{"p1_m": [0, 0, 0]}],  # p2_m missing
    }
    with pytest.raises(ValueError, match="p2_m"):
        generate_palace_mesh(geometry)


# ---------------------------------------------------------------------------
# Embedded conductivity sheet (issue #289) -- mesh generation
# ---------------------------------------------------------------------------


def _sheet_boundary_faces(mesh_text: str, num_boundary_faces: int) -> list[list[str]]:
    lines = mesh_text.split("\n")
    start = lines.index("boundary") + 2
    return [
        line.split()
        for line in lines[start : start + num_boundary_faces]
        if int(line.split()[0]) == BOUND_CONDUCTIVITY_BASE
    ]


def test_generate_palace_mesh_conductivity_sheet_gets_interior_boundary_attribute():
    result = generate_palace_mesh(CONDUCTIVITY_SHEET_GEOMETRY)
    faces = _sheet_boundary_faces(result["mesh_text"], result["num_boundary_faces"])
    # A single grid cell's worth of footprint (nx=ny=1, one x-interval and
    # one y-interval span the patch exactly) -- one interior quad.
    assert len(faces) == 1
    assert len(faces[0]) == 2 + 4  # attribute, geom_type, 4 vertex indices
    assert faces[0][1] == "3"  # SQUARE, same as every other boundary face


def test_generate_palace_mesh_conductivity_sheet_vertices_sit_on_its_own_z_plane():
    result = generate_palace_mesh(CONDUCTIVITY_SHEET_GEOMETRY)
    lines = result["mesh_text"].split("\n")
    v_start = lines.index("vertices") + 3
    vertices = [tuple(float(c) for c in line.split()) for line in lines[v_start:]]
    faces = _sheet_boundary_faces(result["mesh_text"], result["num_boundary_faces"])
    for _, _, *verts in faces:
        for v in verts:
            assert vertices[int(v)][2] == pytest.approx(0.02)


def test_generate_palace_mesh_conductivity_sheet_excluded_from_domain_attributes():
    """A zero-thickness sheet has no volume, so no hex element's centroid
    can ever land inside it -- it must never consume a domain (material)
    attribute the way a real dielectric box does."""
    result = generate_palace_mesh(CONDUCTIVITY_SHEET_GEOMETRY)
    lines = result["mesh_text"].split("\n")
    start = lines.index("elements") + 2
    attrs = {int(line.split()[0]) for line in lines[start : start + result["num_elements"]]}
    assert attrs == {1}  # background only -- the sheet contributes no domain material


def test_generate_palace_mesh_conductivity_sheet_and_dielectric_material_coexist():
    substrate = {
        "name": "substrate",
        "p1_m": [0.0, 0.0, 0.0],
        "p2_m": [0.04, 0.02, 0.02],
        "epsilon_r": 3.5,
    }
    geometry = {
        **CONDUCTIVITY_SHEET_GEOMETRY,
        "materials": [*CONDUCTIVITY_SHEET_GEOMETRY["materials"], substrate],
    }
    result = generate_palace_mesh(geometry)
    lines = result["mesh_text"].split("\n")
    start = lines.index("elements") + 2
    attrs = {int(line.split()[0]) for line in lines[start : start + result["num_elements"]]}
    assert attrs == {1, 2}  # background + the one dielectric material
    faces = _sheet_boundary_faces(result["mesh_text"], result["num_boundary_faces"])
    assert len(faces) == 1  # the sheet still gets its own interior boundary face


@pytest.mark.parametrize(
    ("override", "match"),
    [
        ({"p2_m": [0.03, 0.015, 0.03]}, "zero-thickness"),  # z mismatch
        ({"p2_m": [0.01, 0.015, 0.02]}, "non-zero extent"),  # degenerate x
        ({"p1_m": [0.01, 0.005, 0.0], "p2_m": [0.03, 0.015, 0.0]}, "z=0.0"),  # z=0 port face
        ({"p1_m": [0.01, 0.005, 0.08], "p2_m": [0.03, 0.015, 0.08]}, "z=0.08"),  # z=lz port face
        ({"p2_m": [0.05, 0.015, 0.02]}, "must lie within"),  # x extends past lx=0.04
        ({"kappa_s_m": 0.0}, "kappa_s_m must be > 0"),
        ({"kappa_s_m": -1.0}, "kappa_s_m must be > 0"),
        ({"thickness_m": 0.0}, "thickness_m must be > 0"),
        ({"thickness_m": -1e-6}, "thickness_m must be > 0"),
    ],
)
def test_generate_palace_mesh_conductivity_sheet_validation_errors(override, match):
    sheet = {**CONDUCTIVITY_SHEET_GEOMETRY["materials"][0], **override}
    geometry = {**CONDUCTIVITY_SHEET_GEOMETRY, "materials": [sheet]}
    with pytest.raises(ValueError, match=match):
        generate_palace_mesh(geometry)


def test_generate_palace_mesh_conductivity_sheet_missing_field_raises():
    geometry = {
        **CONDUCTIVITY_SHEET_GEOMETRY,
        "materials": [{"p1_m": [0.01, 0.005, 0.02], "p2_m": [0.03, 0.015, 0.02], "kappa_s_m": 2e5}],
    }
    with pytest.raises(ValueError, match="thickness_m"):
        generate_palace_mesh(geometry)


# ---------------------------------------------------------------------------
# Config generation
# ---------------------------------------------------------------------------


def test_generate_palace_config_top_level_sections():
    config = generate_palace_config(
        GRATING_GEOMETRY, mesh_file="unit_cell.mesh", output_dir="postpro", frequency_hz=10e9
    )
    assert set(config.keys()) == {"Problem", "Model", "Domains", "Boundaries", "Solver"}
    assert config["Problem"]["Type"] == "Driven"
    assert config["Model"]["Mesh"] == "unit_cell.mesh"


def test_generate_palace_config_l0_always_explicit_one():
    """L0 must NEVER be omitted -- Palace's own default (1e-6, micrometers)
    would silently misinterpret this module's meter-denominated mesh
    coordinates by 1e6x. See module docstring citation."""
    config = generate_palace_config(
        GRATING_GEOMETRY, mesh_file="m.mesh", output_dir="postpro", frequency_hz=10e9
    )
    assert config["Model"]["L0"] == 1.0


def test_generate_palace_config_materials_include_background_and_embedded():
    config = generate_palace_config(
        GRATING_GEOMETRY, mesh_file="m.mesh", output_dir="postpro", frequency_hz=10e9
    )
    materials = config["Domains"]["Materials"]
    assert len(materials) == 2
    assert materials[0]["Attributes"] == [1]
    assert materials[0]["Permittivity"] == 1.0  # background defaults to vacuum
    assert materials[1]["Attributes"] == [2]
    assert materials[1]["Permittivity"] == 7.0  # the dielectric bar


def test_generate_palace_config_periodic_boundary_pairs():
    config = generate_palace_config(
        GRATING_GEOMETRY, mesh_file="m.mesh", output_dir="postpro", frequency_hz=10e9
    )
    periodic = config["Boundaries"]["Periodic"]
    pairs = periodic["BoundaryPairs"]
    assert len(pairs) == 2
    assert pairs[0]["DonorAttributes"] == [BOUND_X_MIN]
    assert pairs[0]["ReceiverAttributes"] == [BOUND_X_MAX]
    assert pairs[0]["Translation"] == pytest.approx([0.04, 0.0, 0.0])
    assert pairs[1]["DonorAttributes"] == [BOUND_Y_MIN]
    assert pairs[1]["ReceiverAttributes"] == [BOUND_Y_MAX]
    assert pairs[1]["Translation"] == pytest.approx([0.0, 0.01, 0.0])


def test_generate_palace_config_floquet_wave_vector_default_normal_incidence():
    config = generate_palace_config(
        GRATING_GEOMETRY, mesh_file="m.mesh", output_dir="postpro", frequency_hz=10e9
    )
    periodic = config["Boundaries"]["Periodic"]
    assert periodic["FloquetWaveVector"] == [0.0, 0.0, 0.0]
    assert periodic["FloquetReferenceFrequency"] == pytest.approx(10.0)  # GHz


def test_generate_palace_config_floquet_wave_vector_oblique_incidence():
    geometry = {
        **GRATING_GEOMETRY,
        "floquet": {
            "wave_vector_1_per_m": [0.0, 104.79, 0.0],
            "reference_frequency_hz": 10e9,
            "polarization": "TE",
        },
    }
    config = generate_palace_config(
        geometry, mesh_file="m.mesh", output_dir="postpro", frequency_hz=10e9
    )
    periodic = config["Boundaries"]["Periodic"]
    assert periodic["FloquetWaveVector"] == pytest.approx([0.0, 104.79, 0.0])


def test_generate_palace_config_floquet_ports_excitation_and_polarization():
    config = generate_palace_config(
        GRATING_GEOMETRY, mesh_file="m.mesh", output_dir="postpro", frequency_hz=10e9
    )
    ports = config["Boundaries"]["FloquetPort"]
    assert len(ports) == 2
    assert ports[0]["Index"] == 1
    assert ports[0]["Attributes"] == [BOUND_Z_MIN]
    assert ports[0]["Excitation"] is True
    assert ports[0]["IncidentPolarization"] == "TE"
    assert ports[1]["Index"] == 2
    assert ports[1]["Attributes"] == [BOUND_Z_MAX]
    assert ports[1]["Excitation"] is False


def test_generate_palace_config_invalid_polarization_raises():
    geometry = {**GRATING_GEOMETRY, "floquet": {"polarization": "not_a_real_polarization"}}
    with pytest.raises(ValueError, match="polarization"):
        generate_palace_config(
            geometry, mesh_file="m.mesh", output_dir="postpro", frequency_hz=10e9
        )


def test_generate_palace_config_driven_sweep_defaults():
    config = generate_palace_config(
        GRATING_GEOMETRY, mesh_file="m.mesh", output_dir="postpro", frequency_hz=10e9
    )
    samples = config["Solver"]["Driven"]["Samples"]
    assert len(samples) == 1
    assert samples[0]["Type"] == "Linear"
    assert samples[0]["MinFreq"] == pytest.approx(9.0)  # GHz, 0.9x default
    assert samples[0]["MaxFreq"] == pytest.approx(11.0)  # GHz, 1.1x default
    assert samples[0]["NSample"] == 51


def test_generate_palace_config_driven_sweep_explicit():
    config = generate_palace_config(
        GRATING_GEOMETRY,
        mesh_file="m.mesh",
        output_dir="postpro",
        frequency_hz=10e9,
        sweep={"start_hz": 2e9, "stop_hz": 12e9, "points": 6},
    )
    samples = config["Solver"]["Driven"]["Samples"][0]
    assert samples["MinFreq"] == pytest.approx(2.0)
    assert samples["MaxFreq"] == pytest.approx(12.0)
    assert samples["NSample"] == 6


def test_generate_palace_config_emits_explicit_finite_element_order():
    """Palace's own default finite-element order is 1, which is too coarse
    to reproduce its own dielectric-grating example at any practical mesh
    size (issue #210). The order is emitted explicitly, never left to the
    default, and is caller-settable."""
    config = generate_palace_config(
        GRATING_GEOMETRY, mesh_file="m.mesh", output_dir="postpro", frequency_hz=10e9
    )
    assert config["Solver"]["Order"] == 1

    config2 = generate_palace_config(
        GRATING_GEOMETRY,
        mesh_file="m.mesh",
        output_dir="postpro",
        frequency_hz=10e9,
        solver_order=2,
    )
    assert config2["Solver"]["Order"] == 2


def test_generate_palace_config_rejects_finite_element_order_below_one():
    with pytest.raises(ValueError, match="solver_order"):
        generate_palace_config(
            GRATING_GEOMETRY,
            mesh_file="m.mesh",
            output_dir="postpro",
            frequency_hz=10e9,
            solver_order=0,
        )


def test_generate_palace_config_is_json_serializable():
    config = generate_palace_config(
        GRATING_GEOMETRY, mesh_file="m.mesh", output_dir="postpro", frequency_hz=10e9
    )
    json.dumps(config)  # must not raise


# ---------------------------------------------------------------------------
# Embedded conductivity sheet (issue #289) -- config generation
# ---------------------------------------------------------------------------


def test_generate_palace_config_emits_conductivity_boundary():
    config = generate_palace_config(
        CONDUCTIVITY_SHEET_GEOMETRY, mesh_file="m.mesh", output_dir="postpro", frequency_hz=10e9
    )
    conductivity = config["Boundaries"]["Conductivity"]
    assert conductivity == [
        {
            "Attributes": [BOUND_CONDUCTIVITY_BASE],
            "Conductivity": 2.0e5,
            "Permeability": 1.0,
            "Thickness": 5e-6,
        }
    ]


def test_generate_palace_config_conductivity_boundary_key_absent_without_a_sheet():
    """Backward compatible: a geometry with no conductivity sheet must not
    grow a new, always-empty "Conductivity" key."""
    config = generate_palace_config(
        GRATING_GEOMETRY, mesh_file="m.mesh", output_dir="postpro", frequency_hz=10e9
    )
    assert "Conductivity" not in config["Boundaries"]


def test_generate_palace_config_conductivity_sheet_excluded_from_domain_materials():
    config = generate_palace_config(
        CONDUCTIVITY_SHEET_GEOMETRY, mesh_file="m.mesh", output_dir="postpro", frequency_hz=10e9
    )
    materials = config["Domains"]["Materials"]
    assert len(materials) == 1  # background only -- the sheet is a boundary, not a domain material
    assert materials[0]["Attributes"] == [1]


def test_generate_palace_config_conductivity_sheet_custom_permeability():
    geometry = {
        **CONDUCTIVITY_SHEET_GEOMETRY,
        "materials": [{**CONDUCTIVITY_SHEET_GEOMETRY["materials"][0], "mue_r": 2.5}],
    }
    config = generate_palace_config(
        geometry, mesh_file="m.mesh", output_dir="postpro", frequency_hz=10e9
    )
    assert config["Boundaries"]["Conductivity"][0]["Permeability"] == 2.5


def test_generate_palace_config_multiple_conductivity_sheets_get_distinct_attributes():
    geometry = {
        **CONDUCTIVITY_SHEET_GEOMETRY,
        "materials": [
            CONDUCTIVITY_SHEET_GEOMETRY["materials"][0],
            {
                "name": "second_patch",
                "p1_m": [0.01, 0.005, 0.04],
                "p2_m": [0.03, 0.015, 0.04],
                "kappa_s_m": 1.0e6,
                "thickness_m": 1e-5,
            },
        ],
    }
    config = generate_palace_config(
        geometry, mesh_file="m.mesh", output_dir="postpro", frequency_hz=10e9
    )
    conductivity = config["Boundaries"]["Conductivity"]
    assert [c["Attributes"] for c in conductivity] == [
        [BOUND_CONDUCTIVITY_BASE],
        [BOUND_CONDUCTIVITY_BASE + 1],
    ]
    assert conductivity[1]["Conductivity"] == 1.0e6


def test_generate_palace_config_conductivity_sheet_missing_field_raises():
    """generate_palace_config validates independently of generate_palace_mesh
    -- a caller building a config directly (skipping mesh generation, e.g.
    reusing a previously-written mesh file) must not silently get a null
    Conductivity/Thickness value in the emitted JSON."""
    geometry = {
        **CONDUCTIVITY_SHEET_GEOMETRY,
        "materials": [{"p1_m": [0.01, 0.005, 0.02], "p2_m": [0.03, 0.015, 0.02], "kappa_s_m": 2e5}],
    }
    with pytest.raises(ValueError, match="thickness_m"):
        generate_palace_config(
            geometry, mesh_file="m.mesh", output_dir="postpro", frequency_hz=10e9
        )


def test_generate_palace_config_conductivity_sheet_is_json_serializable():
    config = generate_palace_config(
        CONDUCTIVITY_SHEET_GEOMETRY, mesh_file="m.mesh", output_dir="postpro", frequency_hz=10e9
    )
    json.dumps(config)  # must not raise


# ---------------------------------------------------------------------------
# Output parsing (against synthetic port-floquet-S.csv content -- see
# module docstring for the honest not-verified-against-a-real-run caveat).
# ---------------------------------------------------------------------------


def _build_sample_floquet_csv() -> str:
    """Build a synthetic port-floquet-S.csv, using the real mode-label
    spelling "S[P<port>(<m>;<n>)<pol>][<exc>]" -- semicolon between the two
    diffraction-order indices, so the label never collides with the file's
    own comma delimiter and never needs quoting. That spelling is confirmed
    against Palace's own published reference output for the dielectric
    grating example (see PALACE_REFERENCE_FLOQUET_CSV at the bottom of this
    file, and issue #210).

    Values: a matched, lossless, frequency-independent reflection/
    transmission pair with a known closed-form answer -- |S11|=0.5
    (-6.0206dB) at 0 deg, |S21|=sqrt(1-0.25)=0.8660254 (-1.2494dB) at
    -90 deg -- plus one non-propagating higher order (nan). Exercises
    magnitude/phase-to-complex conversion and the nan->None handling
    documented in simulation/palace.py's module docstring citation.
    """
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        [
            "f (GHz)",
            "|S[P1(0;0)TE][1]| (dB)",
            "arg(S[P1(0;0)TE][1]) (deg.)",
            "|S[P2(0;0)TE][1]| (dB)",
            "arg(S[P2(0;0)TE][1]) (deg.)",
            "|S[P2(1;0)TE][1]| (dB)",
            "arg(S[P2(1;0)TE][1]) (deg.)",
        ]
    )
    writer.writerow(["8.000000e+00", "-6.0206", "0.0", "-1.2494", "-90.0", "nan", "nan"])
    writer.writerow(["10.000000e+00", "-6.0206", "0.0", "-1.2494", "-90.0", "nan", "nan"])
    return buf.getvalue()


SAMPLE_FLOQUET_CSV = _build_sample_floquet_csv()


def test_parse_palace_output_extracts_frequency_hz():
    result = parse_palace_output(SAMPLE_FLOQUET_CSV)
    assert result["computed"] is True
    assert result["frequency_hz"] == pytest.approx([8e9, 10e9])


def test_parse_palace_output_extracts_mode_metadata():
    result = parse_palace_output(SAMPLE_FLOQUET_CSV)
    mode = result["modes"]["S[P1(0;0)TE][1]"]
    assert mode["port"] == 1
    assert mode["m"] == 0
    assert mode["n"] == 0
    assert mode["polarization"] == "TE"
    assert mode["excitation"] == 1


def test_parse_palace_output_converts_db_phase_to_complex():
    result = parse_palace_output(SAMPLE_FLOQUET_CSV)
    s11 = result["modes"]["S[P1(0;0)TE][1]"]["value_complex"][0]
    assert s11 is not None
    magnitude = math.hypot(*s11)
    assert magnitude == pytest.approx(0.5, rel=1e-3)
    assert s11[1] == pytest.approx(0.0, abs=1e-6)  # 0 deg phase -> purely real

    s21 = result["modes"]["S[P2(0;0)TE][1]"]["value_complex"][0]
    assert s21 is not None
    magnitude21 = math.hypot(*s21)
    assert magnitude21 == pytest.approx(0.8660254, rel=1e-3)
    assert s21[0] == pytest.approx(0.0, abs=1e-6)  # -90 deg phase -> purely imaginary
    assert s21[1] < 0


def test_parse_palace_output_nan_mode_is_none():
    result = parse_palace_output(SAMPLE_FLOQUET_CSV)
    higher_order = result["modes"]["S[P2(1;0)TE][1]"]
    assert higher_order["value_complex"] == [None, None]


def test_parse_palace_output_specular_convenience_view():
    result = parse_palace_output(SAMPLE_FLOQUET_CSV)
    assert "S11_TE" in result["specular"]
    assert "S21_TE" in result["specular"]
    assert "S[P2(1;0)TE][1]" not in result.get("specular", {})  # non-specular excluded


def test_parse_palace_output_empty_text_returns_computed_false():
    result = parse_palace_output("")
    assert result["computed"] is False


def test_parse_palace_output_no_matching_header_returns_computed_false():
    result = parse_palace_output("f (GHz),SomethingElse\n1.0,2.0\n")
    assert result["computed"] is False
    assert "mode label" in result["note"]


# ---------------------------------------------------------------------------
# PalaceSimulator.run() subprocess plumbing, against fake executables.
# ---------------------------------------------------------------------------


def test_palace_simulator_invokes_dash_np_and_positional_config(tmp_path: Path):
    """Confirm the real palace CLI contract (-np <N> config.json, see
    module docstring citation) is what actually gets shelled out."""
    script = _make_fake_palace(tmp_path, "import sys\nsys.stdout.write(' '.join(sys.argv[1:]))\n")
    config_file = tmp_path / "config.json"
    config_file.write_text("{}")

    simulator = PalaceSimulator(executable=str(script))
    result = simulator.run({"config_file": str(config_file), "num_processes": 4, "timeout_s": 10})

    tokens = result.outputs["stdout"].split()
    assert tokens == ["-np", "4", str(config_file)]
    assert result.status == "COMPLETED"
    assert result.provenance == "SIMULATED"


def test_palace_simulator_nonzero_exit_raises_simulator_error(tmp_path: Path):
    script = _make_fake_palace(
        tmp_path, 'import sys\nsys.stderr.write("boom: bad config\\n")\nsys.exit(1)\n'
    )
    config_file = tmp_path / "config.json"
    config_file.write_text("{}")

    simulator = PalaceSimulator(executable=str(script))
    with pytest.raises(SimulatorError, match="boom"):
        simulator.run({"config_file": str(config_file), "timeout_s": 10})


def test_palace_simulator_timeout_raises_simulator_error(tmp_path: Path):
    script = _make_fake_palace(tmp_path, "import time\ntime.sleep(5)\n")
    config_file = tmp_path / "config.json"
    config_file.write_text("{}")

    simulator = PalaceSimulator(executable=str(script))
    with pytest.raises(SimulatorError, match="timed out"):
        simulator.run({"config_file": str(config_file), "timeout_s": 1})


def test_palace_simulator_missing_config_file_raises(tmp_path: Path):
    simulator = PalaceSimulator(executable="palace")
    with pytest.raises(SimulatorError, match="not found"):
        simulator.run({"config_file": str(tmp_path / "does_not_exist.json")})


def test_palace_simulator_picks_up_executable_from_env_var(tmp_path: Path, monkeypatch):
    script = _make_fake_palace(tmp_path, "import sys\nsys.exit(0)\n")
    monkeypatch.setenv("PALACE_BIN", str(script))
    simulator = PalaceSimulator()
    assert simulator.executable == str(script)


# ---------------------------------------------------------------------------
# run_palace_simulation end to end, against a fake executable that writes a
# realistic port-floquet-S.csv into the configured Output directory.
# ---------------------------------------------------------------------------

_FAKE_PALACE_PY = '''
import json
import sys
from pathlib import Path

CSV = """{csv}"""

args = sys.argv[1:]
assert args[0] == "-np", args
config_path = Path(args[2])
config = json.loads(config_path.read_text())
output_dir = Path(config["Problem"]["Output"])
output_dir.mkdir(parents=True, exist_ok=True)
(output_dir / "port-floquet-S.csv").write_text(CSV)
sys.exit(0)
'''


def _make_fake_palace_py(tmp_path: Path, sample_csv: str) -> Path:
    body = _FAKE_PALACE_PY.format(csv=sample_csv)
    return make_fake_executable(tmp_path, body, name="fake_palace_realistic")


def test_run_palace_simulation_end_to_end_with_fake_executable(tmp_path: Path):
    script = _make_fake_palace_py(tmp_path, SAMPLE_FLOQUET_CSV)

    result = run_palace_simulation(
        geometry=GRATING_GEOMETRY,
        frequency_hz=10e9,
        sweep={"start_hz": 8e9, "stop_hz": 10e9, "points": 2},
        timeout_s=10,
        executable=str(script),
        workdir=str(tmp_path / "run"),
    )

    assert result["provenance"] == "SIMULATED"
    assert result["simulator"] == "Palace"
    assert result["status"] == "COMPLETED"
    assert result["s_parameters"]["computed"] is True
    assert result["s_parameters"]["frequency_hz"] == pytest.approx([8e9, 10e9])
    assert "S11_TE" in result["s_parameters"]["specular"]
    assert os.path.exists(result["mesh_file"])
    assert os.path.exists(result["config_file"])
    # The generated mesh/config are on disk and inspectable.
    config_text = Path(result["config_file"]).read_text()
    parsed_config = json.loads(config_text)
    assert parsed_config["Problem"]["Type"] == "Driven"


def test_run_palace_simulation_propagates_simulator_error_on_failure(tmp_path: Path):
    script = _make_fake_palace(
        tmp_path, 'import sys\nsys.stderr.write("mesh error\\n")\nsys.exit(1)\n'
    )
    with pytest.raises(SimulatorError):
        run_palace_simulation(
            geometry=GRATING_GEOMETRY,
            frequency_hz=10e9,
            timeout_s=10,
            executable=str(script),
            workdir=str(tmp_path / "run2"),
        )


def test_run_palace_simulation_missing_output_csv_is_honestly_computed_false(tmp_path: Path):
    """A run that 'succeeds' (exit 0) but never writes port-floquet-S.csv
    (e.g. no ports actually propagated, or a real-tool behavior this
    module's fake script doesn't model) must not fabricate S-parameters."""
    script = _make_fake_palace(tmp_path, "import sys\nsys.exit(0)\n")
    result = run_palace_simulation(
        geometry=GRATING_GEOMETRY,
        frequency_hz=10e9,
        timeout_s=10,
        executable=str(script),
        workdir=str(tmp_path / "run3"),
    )
    assert result["s_parameters"]["computed"] is False


# ---------------------------------------------------------------------------
# Output parsing against Palace's OWN published reference output (issue #210).
#
# Everything above this line parses text this test suite invented. The block
# below parses columns copied verbatim (cell for cell, including the leading
# space padding Palace's CSV writer emits) out of Palace's own checked-in
# regression baseline for the "Floquet Ports for a Dielectric Grating"
# example --
# test/data/regression/ref/dielectric_grating/uniform/port-floquet-S.csv at
# awslabs/palace commit 43a5483 -- reduced to the f column plus the specular
# (0;0)TE and first-order (-1;0)TE reflection/transmission column pairs so it
# fits here. That file is the ground truth for the real spelling of the mode
# label, which is "S[P<port>(<m>;<n>)<pol>][<exc>]" with a SEMICOLON between
# the two diffraction-order indices, not the comma this module's parser was
# originally written against.
# ---------------------------------------------------------------------------

PALACE_REFERENCE_FLOQUET_CSV = (
    "        f (GHz),    |S[P1(-1;0)TE][1]| (dB),arg(S[P1(-1;0)TE][1]) (deg.),"
    "     |S[P1(0;0)TE][1]| (dB),arg(S[P1(0;0)TE][1]) (deg.),"
    "    |S[P2(-1;0)TE][1]| (dB),arg(S[P2(-1;0)TE][1]) (deg.),"
    "     |S[P2(0;0)TE][1]| (dB),arg(S[P2(0;0)TE][1]) (deg.)\n"
    " 2.00000000e+00,                       +nan,                        +nan,"
    "        -1.895484400956e+01,        +9.707838147826e+01,"
    "                       +nan,                        +nan,"
    "        -5.560025422477e-02,        +7.078380823648e+00\n"
    " 4.00000000e+00,                       +nan,                        +nan,"
    "        -1.298955891900e+01,        -7.617254883785e+01,"
    "                       +nan,                        +nan,"
    "        -2.238582338362e-01,        -1.661725502428e+02\n"
    " 6.00000000e+00,                       +nan,                        +nan,"
    "        -9.271287457121e+00,        +1.091475553056e+02,"
    "                       +nan,                        +nan,"
    "        -5.466392958824e-01,        +1.914755575339e+01\n"
    " 8.00000000e+00,                       +nan,                        +nan,"
    "        -1.606377748701e+00,        -9.628124039262e+01,"
    "                       +nan,                        +nan,"
    "        -5.097960699491e+00,        +1.737193476250e+02\n"
    " 1.00000000e+01,        -1.535155055903e+01,         +1.071923457487e+02,"
    "        -8.959593343531e+00,        +1.040495087235e+02,"
    "        -1.429624565164e+01,         -5.933868353774e+01,"
    "        -2.187835210722e+00,        +3.997227066998e+01\n"
    " 1.20000000e+01,        -1.688735328348e+01,         -1.266988626996e+02,"
    "        -1.037783889469e+01,        -7.783956943716e+01,"
    "        -1.272037520041e+01,         +8.814889854213e+01,"
    "        -2.728281827842e+00,        -1.338939407403e+02\n"
)


def test_parse_palace_reference_output_is_parsed_at_all():
    """The whole parser hinges on recognising Palace's real mode label. If
    this returns computed=False, every downstream number is silently absent."""
    result = parse_palace_output(PALACE_REFERENCE_FLOQUET_CSV)
    assert result["computed"] is True, result.get("note")


def test_parse_palace_reference_output_frequencies_are_the_published_sweep():
    result = parse_palace_output(PALACE_REFERENCE_FLOQUET_CSV)
    assert result["frequency_hz"] == pytest.approx([2e9, 4e9, 6e9, 8e9, 10e9, 12e9])


def test_parse_palace_reference_output_specular_matches_published_values():
    """|S11| and |S21| in the specular (0,0) order at 2 GHz, straight off
    Palace's own published baseline: -18.9548 dB reflection (about 11% of
    the wave's voltage amplitude comes back) and -0.0556 dB transmission
    (essentially all of it goes through)."""
    result = parse_palace_output(PALACE_REFERENCE_FLOQUET_CSV)
    s11 = result["specular"]["S11_TE"][0]
    s21 = result["specular"]["S21_TE"][0]
    assert 20 * math.log10(math.hypot(*s11)) == pytest.approx(-18.954844009, rel=1e-9)
    assert 20 * math.log10(math.hypot(*s21)) == pytest.approx(-0.0556002542, rel=1e-9)
    # Phases, in degrees, back out of the real/imaginary pair the parser built.
    assert math.degrees(math.atan2(s11[1], s11[0])) == pytest.approx(97.07838147826, rel=1e-9)
    assert math.degrees(math.atan2(s21[1], s21[0])) == pytest.approx(7.078380823648, rel=1e-9)


def test_parse_palace_reference_output_mode_metadata_uses_semicolon_label():
    result = parse_palace_output(PALACE_REFERENCE_FLOQUET_CSV)
    mode = result["modes"]["S[P1(-1;0)TE][1]"]
    assert mode["port"] == 1
    assert mode["m"] == -1
    assert mode["n"] == 0
    assert mode["polarization"] == "TE"
    assert mode["excitation"] == 1


def test_parse_palace_reference_output_non_propagating_orders_are_none():
    """Below the 8.66 GHz Rayleigh anomaly the (-1,0) diffraction order
    carries no power -- Palace writes '+nan' there, and the parser must
    hand back None rather than a number."""
    result = parse_palace_output(PALACE_REFERENCE_FLOQUET_CSV)
    first_order = result["modes"]["S[P1(-1;0)TE][1]"]["value_complex"]
    assert first_order[:4] == [None, None, None, None]  # 2, 4, 6, 8 GHz
    assert first_order[4] is not None  # 10 GHz, above the anomaly
    assert first_order[5] is not None  # 12 GHz


def test_run_palace_simulation_passes_solver_order_into_the_config(tmp_path: Path):
    script = _make_fake_palace_py(tmp_path, SAMPLE_FLOQUET_CSV)
    result = run_palace_simulation(
        geometry=GRATING_GEOMETRY,
        frequency_hz=10e9,
        sweep={"start_hz": 8e9, "stop_hz": 10e9, "points": 2},
        timeout_s=10,
        executable=str(script),
        workdir=str(tmp_path / "run_order"),
        solver_order=2,
    )
    config = json.loads(Path(result["config_file"]).read_text())
    assert config["Solver"]["Order"] == 2


def test_run_palace_simulation_lossless_declared_false_with_conductivity_sheet(tmp_path: Path):
    """Issue #289: a geometry with an embedded conductivity sheet is a real,
    absorbing structure by construction (kappa_s_m > 0 is required), so
    check_palace_result's own `lossless` assumption must flip to False even
    though every material's loss_tan is still 0 -- otherwise a real power
    deficit would be flagged as a violation instead of the loss it is."""
    script = _make_fake_palace_py(tmp_path, SAMPLE_FLOQUET_CSV)
    result = run_palace_simulation(
        geometry=CONDUCTIVITY_SHEET_GEOMETRY,
        frequency_hz=10e9,
        sweep={"start_hz": 8e9, "stop_hz": 10e9, "points": 2},
        timeout_s=10,
        executable=str(script),
        workdir=str(tmp_path / "run_lossy"),
    )
    power_balance = result["conservation_check"]["power_balance"]
    assert all(pb["lossless_declared"] is False for pb in power_balance)


def test_run_palace_simulation_lossless_declared_true_without_a_conductivity_sheet(
    tmp_path: Path,
):
    """The pre-existing, all-dielectric-and-lossless case must be unaffected
    by issue #289's addition."""
    script = _make_fake_palace_py(tmp_path, SAMPLE_FLOQUET_CSV)
    result = run_palace_simulation(
        geometry=GRATING_GEOMETRY,
        frequency_hz=10e9,
        sweep={"start_hz": 8e9, "stop_hz": 10e9, "points": 2},
        timeout_s=10,
        executable=str(script),
        workdir=str(tmp_path / "run_lossless"),
    )
    power_balance = result["conservation_check"]["power_balance"]
    assert all(pb["lossless_declared"] is True for pb in power_balance)


# ---------------------------------------------------------------------------
# The specular convenience view, against real Palace output (issue #210).
#
# Palace writes BOTH polarizations for every diffraction order -- for a TE
# excitation, the co-polarized "TE" columns carry the answer and the "TM"
# columns carry the cross-polarized leakage, which for this symmetric
# grating is numerical noise near -275 dB. Both are (0,0) specular modes of
# the same excitation, so a convenience view keyed on port number alone
# cannot tell them apart. Below are the f, (0;0)TE and (0;0)TM column pairs
# copied verbatim (again, padding included) from the same published
# baseline, first two frequency rows.
# ---------------------------------------------------------------------------

PALACE_REFERENCE_BOTH_POLARIZATIONS_CSV = (
    "        f (GHz),     |S[P1(0;0)TE][1]| (dB),arg(S[P1(0;0)TE][1]) (deg.),"
    "     |S[P1(0;0)TM][1]| (dB),arg(S[P1(0;0)TM][1]) (deg.),"
    "     |S[P2(0;0)TE][1]| (dB),arg(S[P2(0;0)TE][1]) (deg.),"
    "     |S[P2(0;0)TM][1]| (dB),arg(S[P2(0;0)TM][1]) (deg.)\n"
    " 2.00000000e+00,        -1.895484400956e+01,        +9.707838147826e+01,"
    "        -2.784127923123e+02,        -1.316188402480e+02,"
    "        -5.560025422477e-02,        +7.078380823648e+00,"
    "        -2.749564046281e+02,        -1.107121947054e+02\n"
    " 4.00000000e+00,        -1.298955891900e+01,        -7.617254883785e+01,"
    "        -2.741310951283e+02,        +1.739541804703e+02,"
    "        -2.238582338362e-01,        -1.661725502428e+02,"
    "        -2.785632211121e+02,        -7.903485125874e+01\n"
)


def _specular_db(result, key, row=0):
    value = result["specular"][key][row]
    assert value is not None
    return 20 * math.log10(math.hypot(*value))


def test_specular_view_keeps_both_polarizations_apart():
    """The co-polarized TE answer must not be overwritten by the
    cross-polarized TM one. In plain terms: the grating sends back about
    11% of the wave it was given (-18.95 dB); the cross-polarized channel
    is dead (-278 dB, i.e. nothing). A view that reported the second number
    as 'S11' would say the structure swallows everything, which is the
    opposite of the truth."""
    result = parse_palace_output(PALACE_REFERENCE_BOTH_POLARIZATIONS_CSV)
    assert _specular_db(result, "S11_TE") == pytest.approx(-18.954844009, rel=1e-9)
    assert _specular_db(result, "S11_TM") == pytest.approx(-278.4127923, rel=1e-9)
    assert _specular_db(result, "S21_TE") == pytest.approx(-0.0556002542, rel=1e-9)
    assert _specular_db(result, "S21_TM") == pytest.approx(-274.9564046, rel=1e-9)


def test_specular_view_keys_are_polarization_qualified():
    result = parse_palace_output(PALACE_REFERENCE_BOTH_POLARIZATIONS_CSV)
    assert set(result["specular"]) == {"S11_TE", "S11_TM", "S21_TE", "S21_TM"}
