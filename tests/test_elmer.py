"""Tests for the Elmer FEM (VectorHelmholtz module) simulation adapter
(issue #64).

None of gmsh, ElmerGrid, or ElmerSolver is installed in this environment
(matching this repo's existing NEC2++/openEMS/HFSS adapters), so this file
exercises the three subprocess-invocation contracts (run_gmsh_meshing,
run_elmergrid_conversion, ElmerSimulator.run) only against small fake
scripts checked in below -- argument shape, nonzero exit -> SimulatorError,
timeout -> SimulatorError -- per this repo's existing tests/test_nec2pp.py
pattern (see that file's own module docstring for the discipline this
mirrors). The .geo/.sif generation and SaveScalars-output-parsing tests
below check the exact keyword/format details cited in simulation/elmer.py's
module docstring, which is the source of truth for every citation.
"""

import os
from pathlib import Path

import pytest
from conftest import make_fake_executable

from simulation.base import SimulatorError
from simulation.elmer import (
    ElmerSimulator,
    generate_elmer_sif,
    generate_gmsh_geo_script,
    parse_elmer_output,
    run_elmer_simulation,
    run_elmergrid_conversion,
    run_gmsh_meshing,
)

DOMAIN_GEOMETRY = {
    "domain": {"p1_m": [0.0, 0.0, 0.0], "p2_m": [0.1, 0.08, 0.06]},
}

EXCITED_GEOMETRY = {
    "domain": {"p1_m": [0.0, 0.0, 0.0], "p2_m": [0.1, 0.08, 0.06]},
    "excitation": {
        "p1_m": [0.04, 0.03, 0.02],
        "p2_m": [0.06, 0.05, 0.04],
        "current_density_a_m2": [0.0, 0.0, 1.0e8],
        "current_density_im_a_m2": [0.0, 0.0, 0.0],
    },
}


def _make_fake_sh(tmp_path: Path, name: str, body: str) -> Path:
    """Write a small fake executable from a Python `body` (cross-platform --
    see conftest.make_fake_executable). `name` may carry a `.sh`/`.py`
    suffix from its caller's own naming convention; that suffix is
    cosmetic here, so it's stripped before delegating."""
    return make_fake_executable(tmp_path, body, name=Path(name).stem)


def _make_fake_py(tmp_path: Path, name: str, body: str) -> Path:
    """Write a small fake executable from a Python `body` (cross-platform --
    see conftest.make_fake_executable)."""
    return make_fake_executable(tmp_path, body, name=Path(name).stem)


# ---------------------------------------------------------------------------
# generate_gmsh_geo_script
# ---------------------------------------------------------------------------


def test_generate_gmsh_geo_script_domain_only():
    geo = generate_gmsh_geo_script(DOMAIN_GEOMETRY)
    assert 'SetFactory("OpenCASCADE");' in geo
    assert "Box(1) = {0, 0, 0, 0.1, 0.08, 0.06};" in geo
    assert 'Physical Volume("bulk", 1) = {1};' in geo
    # All six outer faces get their own explicit-tag Physical Surface.
    for face, tag in [
        ("x_min", 101),
        ("x_max", 102),
        ("y_min", 103),
        ("y_max", 104),
        ("z_min", 105),
        ("z_max", 106),
    ]:
        assert f"s_{face}() = Surface In BoundingBox" in geo
        assert f'Physical Surface("{face}", {tag}) = s_{face}();' in geo
    assert "Mesh.MeshSizeMax" in geo
    assert "Mesh 3;" in geo
    assert "BooleanFragments" not in geo


def test_generate_gmsh_geo_script_with_excitation_fragments_and_tags():
    geo = generate_gmsh_geo_script(EXCITED_GEOMETRY)
    assert "Box(2) = {0.04, 0.03, 0.02, 0.02, 0.02, 0.02};" in geo
    assert "BooleanFragments{ Volume{1}; Delete; }{ Volume{2}; Delete; };" in geo
    assert "v_exc() = Volume In BoundingBox{" in geo
    assert "v_dom() = Volume In BoundingBox{" in geo
    assert 'Physical Volume("bulk", 1) = v_dom();' in geo
    assert 'Physical Volume("bulk", 1) -= v_exc();' in geo
    assert 'Physical Volume("excitation", 2) = v_exc();' in geo


def test_generate_gmsh_geo_script_missing_domain_raises():
    with pytest.raises(ValueError, match="domain"):
        generate_gmsh_geo_script({})


def test_generate_gmsh_geo_script_degenerate_domain_raises():
    with pytest.raises(ValueError, match="non-degenerate"):
        generate_gmsh_geo_script({"domain": {"p1_m": [0, 0, 0], "p2_m": [0.1, 0.1, 0]}})


def test_generate_gmsh_geo_script_excitation_outside_domain_raises():
    geometry = {
        "domain": DOMAIN_GEOMETRY["domain"],
        "excitation": {"p1_m": [0.5, 0.5, 0.5], "p2_m": [0.6, 0.6, 0.6]},
    }
    with pytest.raises(ValueError, match="inside"):
        generate_gmsh_geo_script(geometry)


def test_generate_gmsh_geo_script_custom_mesh_size():
    geo = generate_gmsh_geo_script({**DOMAIN_GEOMETRY, "mesh_max_size_m": 0.005})
    assert "Mesh.MeshSizeMax = 0.005;" in geo


# ---------------------------------------------------------------------------
# generate_elmer_sif
# ---------------------------------------------------------------------------


def test_generate_elmer_sif_basic_structure():
    sif = generate_elmer_sif(DOMAIN_GEOMETRY, frequency_hz=2.45e9, mesh_dir_name="elmer_mesh")
    assert 'Mesh DB "." "elmer_mesh"' in sif
    assert "$ w = 2*pi*(2.45e+09)" in sif
    assert "Body 1" in sif
    assert 'Equation = "VectorHelmholtz"' in sif
    assert 'Procedure = "VectorHelmholtz" "VectorHelmholtzSolver"' in sif
    assert "Variable = E[E re:1 E im:1]" in sif
    assert 'Equation = "calcfields"' in sif
    assert 'Procedure = "VectorHelmholtz" "VectorHelmholtzCalcFields"' in sif
    assert 'Equation = "SaveScalars"' in sif
    assert 'FileName = "scalar_values.dat"' in sif
    assert "Angular Frequency = Real $w" in sif
    # Material uses "Relative Reluctivity", NOT "Relative Permeability" --
    # see simulation/elmer.py's module docstring citation on this exact
    # keyword (verified from VectorHelmholtz.F90's own source).
    assert "Relative Reluctivity = Real 1" in sif
    assert "Relative Permeability" not in sif
    # No excitation given -> only one Body block, no Body Force.
    assert "Body 2" not in sif
    assert "Body Force" not in sif


def test_generate_elmer_sif_default_boundary_is_absorbing_bc_on_all_six_faces():
    sif = generate_elmer_sif(DOMAIN_GEOMETRY, frequency_hz=2.45e9, mesh_dir_name="elmer_mesh")
    assert sif.count("Absorbing BC = Logical True") == 6
    assert "E Re = Real 0.0" not in sif
    for tag in (101, 102, 103, 104, 105, 106):
        assert f"Target Boundaries(1) = {tag}" in sif


def test_generate_elmer_sif_pec_faces_override_absorbing_bc():
    geometry = {**DOMAIN_GEOMETRY, "pec_faces": ["z_min"]}
    sif = generate_elmer_sif(geometry, frequency_hz=2.45e9, mesh_dir_name="elmer_mesh")
    assert sif.count("Absorbing BC = Logical True") == 5
    assert sif.count("E Re = Real 0.0") == 1
    assert sif.count("E Im = Real 0.0") == 1


def test_generate_elmer_sif_unknown_pec_face_raises():
    geometry = {**DOMAIN_GEOMETRY, "pec_faces": ["not_a_face"]}
    with pytest.raises(ValueError, match="pec_faces"):
        generate_elmer_sif(geometry, frequency_hz=2.45e9, mesh_dir_name="elmer_mesh")


def test_generate_elmer_sif_excitation_adds_body_force_and_current_density():
    sif = generate_elmer_sif(EXCITED_GEOMETRY, frequency_hz=2.45e9, mesh_dir_name="elmer_mesh")
    assert "Body 2" in sif
    assert "Body Force = 1" in sif
    assert "Body Force 1" in sif
    assert "Current Density 3 = Real 1e+08" in sif
    assert "Current Density 3 im = Real 0" in sif
    assert "Current Density 1 = Real 0" in sif


def test_generate_elmer_sif_excitation_missing_current_density_raises():
    geometry = {
        "domain": DOMAIN_GEOMETRY["domain"],
        "excitation": {"p1_m": [0.04, 0.03, 0.02], "p2_m": [0.06, 0.05, 0.04]},
    }
    with pytest.raises(ValueError, match="current_density_a_m2"):
        generate_elmer_sif(geometry, frequency_hz=2.45e9, mesh_dir_name="elmer_mesh")


# ---------------------------------------------------------------------------
# run_gmsh_meshing subprocess contract
# ---------------------------------------------------------------------------


def test_run_gmsh_meshing_invokes_dash_3_format_msh2(tmp_path: Path):
    script = _make_fake_sh(
        tmp_path,
        "fake_gmsh.sh",
        'import sys\nwith open("argv.txt", "w") as f:\n    f.write(" ".join(sys.argv[1:]))\n',
    )
    geo_file = tmp_path / "model.geo"
    geo_file.write_text('SetFactory("OpenCASCADE");\n')
    msh_file = tmp_path / "model.msh"

    run_gmsh_meshing(geo_file, msh_file, tmp_path, executable=str(script), timeout_s=10)

    argv = (tmp_path / "argv.txt").read_text().split()
    assert str(geo_file) in argv
    assert "-3" in argv
    assert "-format" in argv
    assert argv[argv.index("-format") + 1] == "msh2"
    assert "-o" in argv
    assert argv[argv.index("-o") + 1] == str(msh_file)


def test_run_gmsh_meshing_nonzero_exit_raises_simulator_error(tmp_path: Path):
    script = _make_fake_sh(
        tmp_path, "fake_gmsh.sh", 'import sys\nsys.stderr.write("bad geo script\\n")\nsys.exit(1)\n'
    )
    geo_file = tmp_path / "model.geo"
    geo_file.write_text("bad")
    with pytest.raises(SimulatorError, match="bad geo script"):
        run_gmsh_meshing(geo_file, tmp_path / "model.msh", tmp_path, executable=str(script))


def test_run_gmsh_meshing_missing_geo_file_raises(tmp_path: Path):
    with pytest.raises(SimulatorError, match="not found"):
        run_gmsh_meshing(
            tmp_path / "does_not_exist.geo", tmp_path / "model.msh", tmp_path, executable="gmsh"
        )


def test_run_gmsh_meshing_timeout_raises_simulator_error(tmp_path: Path):
    script = _make_fake_sh(tmp_path, "fake_gmsh.sh", "import time\ntime.sleep(5)\n")
    geo_file = tmp_path / "model.geo"
    geo_file.write_text("x")
    with pytest.raises(SimulatorError, match="timed out"):
        run_gmsh_meshing(
            geo_file, tmp_path / "model.msh", tmp_path, executable=str(script), timeout_s=1
        )


# ---------------------------------------------------------------------------
# run_elmergrid_conversion subprocess contract
# ---------------------------------------------------------------------------


def test_run_elmergrid_conversion_invokes_14_2_stem_out(tmp_path: Path):
    script = _make_fake_sh(
        tmp_path,
        "fake_elmergrid.sh",
        'import sys\nwith open("argv.txt", "w") as f:\n    f.write(" ".join(sys.argv[1:]))\n',
    )
    msh_file = tmp_path / "model.msh"
    msh_file.write_text("$MeshFormat\n2.2 0 8\n$EndMeshFormat\n")

    result_dir = run_elmergrid_conversion(
        msh_file, "elmer_mesh", tmp_path, executable=str(script), timeout_s=10
    )

    argv = (tmp_path / "argv.txt").read_text().split()
    assert argv[:3] == ["14", "2", "model"]
    assert "-out" in argv
    assert argv[argv.index("-out") + 1] == "elmer_mesh"
    assert result_dir == tmp_path / "elmer_mesh"


def test_run_elmergrid_conversion_nonzero_exit_raises_simulator_error(tmp_path: Path):
    script = _make_fake_sh(
        tmp_path, "fake_elmergrid.sh", 'import sys\nsys.stderr.write("bad mesh\\n")\nsys.exit(1)\n'
    )
    msh_file = tmp_path / "model.msh"
    msh_file.write_text("junk")
    with pytest.raises(SimulatorError, match="bad mesh"):
        run_elmergrid_conversion(msh_file, "elmer_mesh", tmp_path, executable=str(script))


def test_run_elmergrid_conversion_missing_msh_file_raises(tmp_path: Path):
    with pytest.raises(SimulatorError, match="not found"):
        run_elmergrid_conversion(
            tmp_path / "does_not_exist.msh", "elmer_mesh", tmp_path, executable="ElmerGrid"
        )


def test_run_elmergrid_conversion_timeout_raises_simulator_error(tmp_path: Path):
    script = _make_fake_sh(tmp_path, "fake_elmergrid.sh", "import time\ntime.sleep(5)\n")
    msh_file = tmp_path / "model.msh"
    msh_file.write_text("junk")
    with pytest.raises(SimulatorError, match="timed out"):
        run_elmergrid_conversion(
            msh_file, "elmer_mesh", tmp_path, executable=str(script), timeout_s=1
        )


# ---------------------------------------------------------------------------
# ElmerSimulator.run() subprocess contract
# ---------------------------------------------------------------------------


def test_elmer_simulator_invokes_sif_path_directly(tmp_path: Path):
    script = _make_fake_sh(
        tmp_path, "fake_elmersolver.sh", "import sys\nsys.stdout.write(' '.join(sys.argv[1:]))\n"
    )
    sif_file = tmp_path / "case.sif"
    sif_file.write_text("Header\nEnd\n")

    simulator = ElmerSimulator(executable=str(script))
    result = simulator.run({"sif_file": str(sif_file), "timeout_s": 10})

    assert result.outputs["stdout"].split() == [str(sif_file)]
    assert result.status == "COMPLETED"
    assert result.provenance == "SIMULATED"


def test_elmer_simulator_nonzero_exit_raises_simulator_error(tmp_path: Path):
    script = _make_fake_sh(
        tmp_path,
        "fake_elmersolver.sh",
        'import sys\nsys.stderr.write("ERROR: bad sif\\n")\nsys.exit(1)\n',
    )
    sif_file = tmp_path / "case.sif"
    sif_file.write_text("Header\nEnd\n")
    simulator = ElmerSimulator(executable=str(script))
    with pytest.raises(SimulatorError, match="bad sif"):
        simulator.run({"sif_file": str(sif_file), "timeout_s": 10})


def test_elmer_simulator_timeout_raises_simulator_error(tmp_path: Path):
    script = _make_fake_sh(tmp_path, "fake_elmersolver.sh", "import time\ntime.sleep(5)\n")
    sif_file = tmp_path / "case.sif"
    sif_file.write_text("Header\nEnd\n")
    simulator = ElmerSimulator(executable=str(script))
    with pytest.raises(SimulatorError, match="timed out"):
        simulator.run({"sif_file": str(sif_file), "timeout_s": 1})


def test_elmer_simulator_missing_sif_file_raises(tmp_path: Path):
    simulator = ElmerSimulator(executable="ElmerSolver")
    with pytest.raises(SimulatorError, match="not found"):
        simulator.run({"sif_file": str(tmp_path / "does_not_exist.sif")})


def test_elmer_simulator_picks_up_executable_from_env_var(tmp_path: Path, monkeypatch):
    script = _make_fake_sh(tmp_path, "fake_elmersolver.sh", "import sys\nsys.exit(0)\n")
    monkeypatch.setenv("ELMERSOLVER_BIN", str(script))
    simulator = ElmerSimulator()
    assert simulator.executable == str(script)


# ---------------------------------------------------------------------------
# parse_elmer_output
# ---------------------------------------------------------------------------

_ALL_DONE_STDOUT = "MAIN: Solving equation VectorHelmholtz\n*** Elmer Solver: ALL DONE ***\n"

_NAMES_FILE_TEXT = """Metadata for SaveScalars file: scalar_values.dat
Elmer version: 26.1

Variables in columns of matrix:
   1: Line Marker
   2: res: VectorHelmholtz
   3: res: energy functional
"""


def test_parse_elmer_output_detects_all_done_marker():
    result = parse_elmer_output(_ALL_DONE_STDOUT)
    assert result["completed_normally"] is True


def test_parse_elmer_output_missing_all_done_marker():
    result = parse_elmer_output("MAIN: some other log line\n")
    assert result["completed_normally"] is False


def test_parse_elmer_output_always_honestly_gaps_s_parameters_and_far_field():
    result = parse_elmer_output(_ALL_DONE_STDOUT)
    assert result["s_parameters"]["computed"] is False
    assert result["far_field"]["computed"] is False
    assert result["gain_dbi"] is None


def test_parse_elmer_output_no_workdir_gives_uncomputed_raw_scalars():
    result = parse_elmer_output(_ALL_DONE_STDOUT)
    assert result["raw_scalars"]["computed"] is False


def test_parse_elmer_output_parses_save_scalars_files(tmp_path: Path):
    (tmp_path / "scalar_values.dat.names").write_text(_NAMES_FILE_TEXT)
    (tmp_path / "scalar_values.dat").write_text("1 1.62980066e+00 2.32743791e-03\n")

    result = parse_elmer_output(_ALL_DONE_STDOUT, workdir=tmp_path)

    raw = result["raw_scalars"]
    assert raw["computed"] is True
    assert raw["values"]["res: VectorHelmholtz"] == pytest.approx(1.62980066e00)
    assert raw["values"]["res: energy functional"] == pytest.approx(2.32743791e-03)


def test_parse_elmer_output_missing_save_scalars_files_is_honestly_uncomputed(tmp_path: Path):
    result = parse_elmer_output(_ALL_DONE_STDOUT, workdir=tmp_path)
    assert result["raw_scalars"]["computed"] is False
    assert "not found" in result["raw_scalars"]["note"]


def test_parse_elmer_output_names_file_without_header_is_honestly_uncomputed(tmp_path: Path):
    (tmp_path / "scalar_values.dat.names").write_text("garbage, no header line here\n")
    (tmp_path / "scalar_values.dat").write_text("1 2 3\n")
    result = parse_elmer_output(_ALL_DONE_STDOUT, workdir=tmp_path)
    assert result["raw_scalars"]["computed"] is False


# ---------------------------------------------------------------------------
# run_elmer_simulation end to end, against fake gmsh/ElmerGrid/ElmerSolver
# executables chained together (mirrors tests/test_nec2pp.py's
# test_run_nec2_simulation_end_to_end_with_fake_executable).
# ---------------------------------------------------------------------------

_FAKE_GMSH_PY = """
import sys
args = sys.argv[1:]
assert "-format" in args and args[args.index("-format") + 1] == "msh2", args
out = args[args.index("-o") + 1]
with open(out, "w") as f:
    f.write("$MeshFormat\\n2.2 0 8\\n$EndMeshFormat\\n")
sys.exit(0)
"""

_FAKE_ELMERGRID_PY = """
import sys, os
args = sys.argv[1:]
assert args[0] == "14" and args[1] == "2", args
out_dir = args[args.index("-out") + 1]
os.makedirs(out_dir, exist_ok=True)
with open(os.path.join(out_dir, "mesh.header"), "w") as f:
    f.write("fake mesh header\\n")
sys.exit(0)
"""

_FAKE_ELMERSOLVER_PY = """
import sys
sif_path = sys.argv[1]
with open("scalar_values.dat.names", "w") as f:
    f.write("Variables in columns of matrix:\\n   1: Line Marker\\n   2: res: energy functional\\n")
with open("scalar_values.dat", "w") as f:
    f.write("1 4.2\\n")
sys.stdout.write("*** Elmer Solver: ALL DONE ***\\n")
sys.exit(0)
"""


def test_run_elmer_simulation_end_to_end_with_fake_executables(tmp_path: Path):
    gmsh = _make_fake_py(tmp_path, "fake_gmsh.py", _FAKE_GMSH_PY)
    elmergrid = _make_fake_py(tmp_path, "fake_elmergrid.py", _FAKE_ELMERGRID_PY)
    elmersolver = _make_fake_py(tmp_path, "fake_elmersolver.py", _FAKE_ELMERSOLVER_PY)

    result = run_elmer_simulation(
        geometry=DOMAIN_GEOMETRY,
        frequency_hz=2.45e9,
        timeout_s=10,
        gmsh_timeout_s=10,
        elmergrid_timeout_s=10,
        gmsh_executable=str(gmsh),
        elmergrid_executable=str(elmergrid),
        elmersolver_executable=str(elmersolver),
        workdir=str(tmp_path / "run"),
    )

    assert result["provenance"] == "SIMULATED"
    assert result["simulator"] == "Elmer/VectorHelmholtz"
    assert result["status"] == "COMPLETED"
    assert result["completed_normally"] is True
    assert result["raw_scalars"]["computed"] is True
    assert result["raw_scalars"]["values"]["res: energy functional"] == pytest.approx(4.2)
    assert result["s_parameters"]["computed"] is False
    assert result["far_field"]["computed"] is False
    assert os.path.exists(result["geo_file"])
    assert os.path.exists(result["sif_file"])
    assert os.path.exists(os.path.join(result["mesh_dir"], "mesh.header"))


def test_run_elmer_simulation_propagates_simulator_error_on_solver_failure(tmp_path: Path):
    gmsh = _make_fake_py(tmp_path, "fake_gmsh.py", _FAKE_GMSH_PY)
    elmergrid = _make_fake_py(tmp_path, "fake_elmergrid.py", _FAKE_ELMERGRID_PY)
    failing_solver = _make_fake_sh(
        tmp_path,
        "fake_elmersolver_fail.sh",
        'import sys\nsys.stderr.write("ERROR: divergence\\n")\nsys.exit(1)\n',
    )

    with pytest.raises(SimulatorError, match="divergence"):
        run_elmer_simulation(
            geometry=DOMAIN_GEOMETRY,
            frequency_hz=2.45e9,
            timeout_s=10,
            gmsh_timeout_s=10,
            elmergrid_timeout_s=10,
            gmsh_executable=str(gmsh),
            elmergrid_executable=str(elmergrid),
            elmersolver_executable=str(failing_solver),
            workdir=str(tmp_path / "run2"),
        )
