"""Tests for the Palace Floquet/periodic-port adapter (issue #61).

The real `palace` binary is NOT installed in this environment (no MPI-
parallel FEM solver install is present here) so `PalaceSimulator.run()` is
exercised here only against small fake "palace" scripts checked in below
(via `tmp_path`), per the same testing approach used for NEC2++/openEMS
(tests/test_nec2pp.py, tests/test_openems.py): subprocess plumbing (argument
shape, nonzero exit, timeout) and result parsing are tested; the physics
itself is out of scope for automated tests.

The config JSON schema, the MFEM ".mesh" v1.0 format, the Floquet/periodic
boundary config shape, and the "-np <N> config.json" CLI contract were
verified against Palace's/MFEM's own primary documentation -- see the header
comment in simulation/palace.py for the full, per-fact citation list
(several facts there are explicitly flagged as reasoned-by-analogy rather
than independently confirmed byte-for-byte -- see that module's HONEST
CAVEAT). The sample port-floquet-S.csv content used in
test_parse_palace_output_* below is a SYNTHETIC file this test suite
constructs itself (following the documented "S[P<port>(<m>,<n>)<pol>][<exc>]"
mode-label convention and the port-S.csv dB/phase convention cited above),
not a real Palace run's output -- it validates this module's parsing/
dB-phase-to-complex arithmetic against known values, not real FEM physics.
"""

import csv
import io
import json
import math
import os
import stat
import sys
from pathlib import Path

import pytest

from simulation.base import SimulatorError
from simulation.palace import (
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
    """Write a small fake 'palace' shell script and make it executable."""
    script = tmp_path / "fake_palace.sh"
    script.write_text("#!/bin/sh\n" + body)
    script.chmod(script.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return script


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


def test_generate_palace_config_is_json_serializable():
    config = generate_palace_config(
        GRATING_GEOMETRY, mesh_file="m.mesh", output_dir="postpro", frequency_hz=10e9
    )
    json.dumps(config)  # must not raise


# ---------------------------------------------------------------------------
# Output parsing (against synthetic port-floquet-S.csv content -- see
# module docstring for the honest not-verified-against-a-real-run caveat).
# ---------------------------------------------------------------------------

def _build_sample_floquet_csv() -> str:
    """Build a synthetic port-floquet-S.csv via Python's own csv.writer
    (which RFC4180-quotes any field containing a comma) rather than a
    hand-formatted string -- the documented mode label itself contains a
    literal comma ("(<m>,<n>)"), so a header cell like
    "|S[P1(0,0)TE][1]| (dB)" MUST be quoted for a comma-delimited row to
    parse back into the intended columns at all. This module's parser
    assumes Palace's own CSV writer does the same standard RFC4180 quoting
    -- REASONED (any correct CSV writer handling a comma-containing field
    would have to), not independently confirmed against a real Palace run;
    see simulation/palace.py's module docstring HONEST CAVEAT.

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
            "|S[P1(0,0)TE][1]| (dB)",
            "arg(S[P1(0,0)TE][1]) (deg.)",
            "|S[P2(0,0)TE][1]| (dB)",
            "arg(S[P2(0,0)TE][1]) (deg.)",
            "|S[P2(1,0)TE][1]| (dB)",
            "arg(S[P2(1,0)TE][1]) (deg.)",
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
    mode = result["modes"]["S[P1(0,0)TE][1]"]
    assert mode["port"] == 1
    assert mode["m"] == 0
    assert mode["n"] == 0
    assert mode["polarization"] == "TE"
    assert mode["excitation"] == 1


def test_parse_palace_output_converts_db_phase_to_complex():
    result = parse_palace_output(SAMPLE_FLOQUET_CSV)
    s11 = result["modes"]["S[P1(0,0)TE][1]"]["value_complex"][0]
    assert s11 is not None
    magnitude = math.hypot(*s11)
    assert magnitude == pytest.approx(0.5, rel=1e-3)
    assert s11[1] == pytest.approx(0.0, abs=1e-6)  # 0 deg phase -> purely real

    s21 = result["modes"]["S[P2(0,0)TE][1]"]["value_complex"][0]
    assert s21 is not None
    magnitude21 = math.hypot(*s21)
    assert magnitude21 == pytest.approx(0.8660254, rel=1e-3)
    assert s21[0] == pytest.approx(0.0, abs=1e-6)  # -90 deg phase -> purely imaginary
    assert s21[1] < 0


def test_parse_palace_output_nan_mode_is_none():
    result = parse_palace_output(SAMPLE_FLOQUET_CSV)
    higher_order = result["modes"]["S[P2(1,0)TE][1]"]
    assert higher_order["value_complex"] == [None, None]


def test_parse_palace_output_specular_convenience_view():
    result = parse_palace_output(SAMPLE_FLOQUET_CSV)
    assert "S11" in result["specular"]
    assert "S21" in result["specular"]
    assert "S[P2(1,0)TE][1]" not in result.get("specular", {})  # non-specular excluded


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
    script = _make_fake_palace(tmp_path, 'echo "$@"\n')
    config_file = tmp_path / "config.json"
    config_file.write_text("{}")

    simulator = PalaceSimulator(executable=str(script))
    result = simulator.run({"config_file": str(config_file), "num_processes": 4, "timeout_s": 10})

    tokens = result.outputs["stdout"].split()
    assert tokens == ["-np", "4", str(config_file)]
    assert result.status == "COMPLETED"
    assert result.provenance == "SIMULATED"


def test_palace_simulator_nonzero_exit_raises_simulator_error(tmp_path: Path):
    script = _make_fake_palace(tmp_path, 'echo "boom: bad config" >&2\nexit 1\n')
    config_file = tmp_path / "config.json"
    config_file.write_text("{}")

    simulator = PalaceSimulator(executable=str(script))
    with pytest.raises(SimulatorError, match="boom"):
        simulator.run({"config_file": str(config_file), "timeout_s": 10})


def test_palace_simulator_timeout_raises_simulator_error(tmp_path: Path):
    script = _make_fake_palace(tmp_path, "sleep 5\n")
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
    script = _make_fake_palace(tmp_path, "exit 0\n")
    monkeypatch.setenv("PALACE_BIN", str(script))
    simulator = PalaceSimulator()
    assert simulator.executable == str(script)


# ---------------------------------------------------------------------------
# run_palace_simulation end to end, against a fake executable that writes a
# realistic port-floquet-S.csv into the configured Output directory.
# ---------------------------------------------------------------------------

_FAKE_PALACE_PY = '''#!{python}
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
    script = tmp_path / "fake_palace_realistic.py"
    script.write_text(_FAKE_PALACE_PY.format(python=sys.executable, csv=sample_csv))
    script.chmod(script.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return script


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
    assert "S11" in result["s_parameters"]["specular"]
    assert os.path.exists(result["mesh_file"])
    assert os.path.exists(result["config_file"])
    # The generated mesh/config are on disk and inspectable.
    config_text = Path(result["config_file"]).read_text()
    parsed_config = json.loads(config_text)
    assert parsed_config["Problem"]["Type"] == "Driven"


def test_run_palace_simulation_propagates_simulator_error_on_failure(tmp_path: Path):
    script = _make_fake_palace(tmp_path, 'echo "mesh error" >&2\nexit 1\n')
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
    script = _make_fake_palace(tmp_path, "exit 0\n")
    result = run_palace_simulation(
        geometry=GRATING_GEOMETRY,
        frequency_hz=10e9,
        timeout_s=10,
        executable=str(script),
        workdir=str(tmp_path / "run3"),
    )
    assert result["s_parameters"]["computed"] is False
