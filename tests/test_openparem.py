"""Tests for the OpenParEM3D adapter: `.proj`/ports-file generation, subprocess
execution, and S-parameter/far-field result parsing (issue #62).

The real `OpenParEM3D` binary is NOT installed in this environment (confirmed via
`which OpenParEM3D` during implementation), and OpenParEM is a multi-tool flow (FreeCAD
+ gmsh + OpenParEM3D itself) rather than a single all-in-one binary, so
`OpenParemSimulator.run()` is exercised here only against small fake "OpenParEM3D"
scripts checked in below (via `tmp_path`), per the same fake-executable testing pattern
already used for NEC2++ (tests/test_nec2pp.py) and openEMS (tests/test_openems.py):
subprocess plumbing (argument shape, nonzero exit, timeout) and output-file parsing are
tested; real FEM physics is out of scope for automated tests.

The `.proj`/ports-file keyword syntax and the `*_results.csv`/`*_FarField_results.csv`
output formats were verified against OpenParEM's own primary GitHub source (grepped
directly out of src/OpenParEM3D/project.c's keyword-parsing switch, src/OpenParEM3D/
{results,pattern}.cpp's own CSV-writing code, and src/OpenParEM3D/port.cpp's/
src/OpenParEMCommon/{path,sourcefile}.cpp's block-parsing code) and a real worked
example (tutorials/OpenParEM3D/monopole_antenna/monopole_antenna_ports.txt) -- see the
header comment in simulation/openparem.py for the full, per-fact citation list. The
sample CSV text used below is hand-constructed to match that documented/verified format
byte-for-byte, NOT transcribed from a real OpenParEM3D run's actual output (no real
binary was available to produce one) -- see that module's HONEST CAVEAT.
"""

import os
from pathlib import Path

import pytest
from conftest import make_fake_executable

from simulation.base import SimulatorError
from simulation.openparem import (
    OpenParemSimulator,
    generate_openparem_ports_file,
    generate_openparem_project_config,
    parse_openparem_output,
    run_openparem_simulation,
)

# A monopole-antenna-like ports definition, structurally mirroring the real worked
# example tutorials/OpenParEM3D/monopole_antenna/monopole_antenna_ports.txt (see module
# docstring citation) -- a circular feed port plus six radiation boundaries forming a
# cubic domain.
MONOPOLE_PORTS = {
    "source_file": "/models/monopole_antenna.FCStd",
    "paths": [
        {
            "name": "port",
            "points": [[0.002, 0.0, -0.02], [0.0, 0.002, -0.02], [-0.002, 0.0, -0.02]],
            "closed": True,
        },
        {"name": "v", "points": [[0.0, 0.002, -0.02], [0.0, 0.0006, -0.02]], "closed": False},
        {
            "name": "front",
            "points": [[-0.1, -0.1, -0.1], [0.1, -0.1, -0.1], [0.1, -0.1, 0.1], [-0.1, -0.1, 0.1]],
            "closed": True,
        },
    ],
    "boundaries": [
        {"name": "front", "type": "radiation", "path": "+front"},
    ],
    "ports": [
        {
            "name": "in",
            "path": "+port",
            "impedance_definition": "PV",
            "impedance_calculation": "modal",
            "modes": [
                {"sport": 1, "integration_path": {"type": "voltage", "path": "+v"}},
            ],
        }
    ],
}

MONOPOLE_PROJECT = {
    "mesh_file": "monopole_antenna.msh",
    "frequency_plan": {"linear": [{"start_hz": 1e9, "stop_hz": 3e9, "step_hz": 1e9}]},
    "far_field": {"quantity": "G"},
}


# ---------------------------------------------------------------------------
# .proj project-control-file generation
# ---------------------------------------------------------------------------


def test_generate_openparem_project_config_header_and_required_keywords():
    text = generate_openparem_project_config(MONOPOLE_PROJECT | {"port_definition_file": "p.txt"})
    lines = text.split("\n")
    assert lines[0] == "#OpenParEM3Dproject 1.0"
    assert "mesh.file                       monopole_antenna.msh" in text
    assert "port.definition.file            p.txt" in text
    assert "mesh.order                      1" in text  # OpenParEM3D's own documented default
    assert "reference.impedance             50" in text  # OpenParEM3D's own documented default
    assert "touchstone.format               DB" in text  # OpenParEM3D's own documented default


def test_generate_openparem_project_config_frequency_plan_linear():
    project = MONOPOLE_PROJECT | {"port_definition_file": "p.txt"}
    text = generate_openparem_project_config(project)
    assert "frequency.plan.linear    1e+09,3e+09,1e+09" in text


def test_generate_openparem_project_config_frequency_plan_point_and_log_and_refine():
    project = {
        "mesh_file": "m.msh",
        "port_definition_file": "p.txt",
        "frequency_plan": {
            "point": [{"frequency_hz": 2.45e9, "refine": True}],
            "log": [{"start_hz": 1e9, "stop_hz": 10e9, "points_per_decade": 10}],
        },
    }
    text = generate_openparem_project_config(project)
    assert "frequency.plan.point.refine     2.45e+09" in text
    assert "frequency.plan.log       1e+09,1e+10,10" in text


def test_generate_openparem_project_config_far_field_pattern_line():
    project = MONOPOLE_PROJECT | {"port_definition_file": "p.txt"}
    text = generate_openparem_project_config(project)
    assert "antenna.plot.3D.pattern         q=G" in text


def test_generate_openparem_project_config_no_far_field_omits_pattern_line():
    project = {k: v for k, v in MONOPOLE_PROJECT.items() if k != "far_field"}
    project = project | {"port_definition_file": "p.txt"}
    text = generate_openparem_project_config(project)
    assert "antenna.plot.3D.pattern" not in text


def test_generate_openparem_project_config_missing_mesh_file_raises():
    project = {k: v for k, v in MONOPOLE_PROJECT.items() if k != "mesh_file"}
    project = project | {"port_definition_file": "p.txt"}
    with pytest.raises(ValueError, match="mesh_file"):
        generate_openparem_project_config(project)


def test_generate_openparem_project_config_missing_port_definition_file_raises():
    with pytest.raises(ValueError, match="port_definition_file"):
        generate_openparem_project_config(MONOPOLE_PROJECT)


def test_generate_openparem_project_config_missing_frequency_plan_raises():
    project = {"mesh_file": "m.msh", "port_definition_file": "p.txt"}
    with pytest.raises(ValueError, match="frequency_plan"):
        generate_openparem_project_config(project)


def test_generate_openparem_project_config_invalid_touchstone_format_raises():
    project = MONOPOLE_PROJECT | {"port_definition_file": "p.txt", "touchstone_format": "XY"}
    with pytest.raises(ValueError, match="touchstone_format"):
        generate_openparem_project_config(project)


def test_generate_openparem_project_config_invalid_refinement_frequency_raises():
    project = MONOPOLE_PROJECT | {
        "port_definition_file": "p.txt",
        "refinement": {"frequency": "sometimes"},
    }
    with pytest.raises(ValueError, match="refinement"):
        generate_openparem_project_config(project)


def test_generate_openparem_project_config_invalid_far_field_quantity_raises():
    project = MONOPOLE_PROJECT | {"port_definition_file": "p.txt", "far_field": {"quantity": "X"}}
    with pytest.raises(ValueError, match="far_field"):
        generate_openparem_project_config(project)


# ---------------------------------------------------------------------------
# Ports/boundary/port definition file generation
# ---------------------------------------------------------------------------


def test_generate_openparem_ports_file_header_and_file_block():
    text = generate_openparem_ports_file(MONOPOLE_PORTS)
    lines = text.split("\n")
    assert lines[0] == "#OpenParEMports 1.0"
    assert "File" in lines
    assert "   name=/models/monopole_antenna.FCStd" in lines
    assert "EndFile" in lines


def test_generate_openparem_ports_file_path_points_and_closed():
    text = generate_openparem_ports_file(MONOPOLE_PORTS)
    assert "Path" in text
    assert "   name=port" in text
    assert "   point=(0.002,0,-0.02)" in text
    assert "   closed=true" in text
    assert "   name=v" in text
    assert "   closed=false" in text
    assert "EndPath" in text


def test_generate_openparem_ports_file_boundary_block():
    text = generate_openparem_ports_file(MONOPOLE_PORTS)
    assert "Boundary" in text
    assert "   name=front" in text
    assert "   type=radiation" in text
    assert "   path=+front" in text
    assert "EndBoundary" in text


def test_generate_openparem_ports_file_port_and_mode_block():
    text = generate_openparem_ports_file(MONOPOLE_PORTS)
    assert "Port" in text
    assert "   name=in" in text
    assert "   path=+port" in text
    assert "   impedance_definition=PV" in text
    assert "   impedance_calculation=modal" in text
    assert "   Mode" in text
    assert "      Sport=1" in text
    assert "      IntegrationPath" in text
    assert "         type=voltage" in text
    assert "         path=+v" in text
    assert "      EndIntegrationPath" in text
    assert "   EndMode" in text
    assert "EndPort" in text


def test_generate_openparem_ports_file_omits_file_block_when_source_file_not_given():
    ports = {k: v for k, v in MONOPOLE_PORTS.items() if k != "source_file"}
    text = generate_openparem_ports_file(ports)
    assert "File" not in text.split("\n")
    assert "EndFile" not in text


def test_generate_openparem_ports_file_no_paths_raises():
    ports = {k: v for k, v in MONOPOLE_PORTS.items() if k != "paths"}
    with pytest.raises(ValueError, match="paths"):
        generate_openparem_ports_file(ports)


def test_generate_openparem_ports_file_no_ports_raises():
    ports = {k: v for k, v in MONOPOLE_PORTS.items() if k != "ports"}
    with pytest.raises(ValueError, match="ports"):
        generate_openparem_ports_file(ports)


def test_generate_openparem_ports_file_invalid_boundary_type_raises():
    ports = {**MONOPOLE_PORTS, "boundaries": [{"name": "x", "type": "not_real", "path": "+front"}]}
    with pytest.raises(ValueError, match="type"):
        generate_openparem_ports_file(ports)


def test_generate_openparem_ports_file_invalid_impedance_definition_raises():
    bad_port = {**MONOPOLE_PORTS["ports"][0], "impedance_definition": "XX"}
    ports = {**MONOPOLE_PORTS, "ports": [bad_port]}
    with pytest.raises(ValueError, match="impedance_definition"):
        generate_openparem_ports_file(ports)


def test_generate_openparem_ports_file_invalid_impedance_calculation_raises():
    bad_port = {**MONOPOLE_PORTS["ports"][0], "impedance_calculation": "XX"}
    ports = {**MONOPOLE_PORTS, "ports": [bad_port]}
    with pytest.raises(ValueError, match="impedance_calculation"):
        generate_openparem_ports_file(ports)


def test_generate_openparem_ports_file_port_missing_modes_raises():
    bad_port = {k: v for k, v in MONOPOLE_PORTS["ports"][0].items() if k != "modes"}
    ports = {**MONOPOLE_PORTS, "ports": [bad_port]}
    with pytest.raises(ValueError, match="modes"):
        generate_openparem_ports_file(ports)


def test_generate_openparem_ports_file_invalid_integration_path_type_raises():
    bad_port = {
        **MONOPOLE_PORTS["ports"][0],
        "modes": [{"sport": 1, "integration_path": {"type": "flux", "path": "+v"}}],
    }
    ports = {**MONOPOLE_PORTS, "ports": [bad_port]}
    with pytest.raises(ValueError, match="type"):
        generate_openparem_ports_file(ports)


# ---------------------------------------------------------------------------
# Output parsing -- against hand-constructed CSV text matching the verified
# ResultDatabase::saveCSV / PatternDatabase::saveCSV format (see module docstring).
# ---------------------------------------------------------------------------

RESULTS_CSV_RI = """#OpenParEM3D 2.1.0
#Touchstone format,RI
#frequency unit,GHz
#number of frequencies,2
#number of ports,1
#S-port 1,net1,50
#Frequency(GHz),Re(S(1;1)),Im(S(1;1))
2.4,-0.1,0.05
2.5,-0.12,0.04
"""

RESULTS_CSV_DB = """#OpenParEM3D 2.1.0
#Touchstone format,DB
#frequency unit,GHz
#number of frequencies,1
#number of ports,1
#S-port 1,net1,not renormalized
#Frequency(GHz),dB(S(1;1)),deg(S(1;1))
2.45,-20,90
"""

RESULTS_CSV_MA = """#OpenParEM3D 2.1.0
#Touchstone format,MA
#frequency unit,MHz
#number of frequencies,1
#number of ports,1
#S-port 1,net1,50
#Frequency(MHz),mag(S(1;1)),deg(S(1;1))
2450,2.0,180
"""

FARFIELD_CSV = """#S-port,frequency(GHz),gain,directivity,radiation efficiency
1,2.4,5.23,5.90,0.89
1,2.5,5.30,5.95,0.90
"""


def test_parse_openparem_output_results_csv_ri_format(tmp_path: Path):
    (tmp_path / "proj_results.csv").write_text(RESULTS_CSV_RI)
    result = parse_openparem_output(tmp_path, "proj")
    s_params = result["s_parameters"]
    assert s_params["computed"] is True
    assert s_params["port_count"] == 1
    assert s_params["frequency_hz"] == pytest.approx([2.4e9, 2.5e9])
    assert s_params["values"]["S11"][0] == pytest.approx([-0.1, 0.05])
    assert s_params["values"]["S11"][1] == pytest.approx([-0.12, 0.04])


def test_parse_openparem_output_results_csv_db_format(tmp_path: Path):
    (tmp_path / "proj_results.csv").write_text(RESULTS_CSV_DB)
    result = parse_openparem_output(tmp_path, "proj")
    s_params = result["s_parameters"]
    assert s_params["computed"] is True
    real, imag = s_params["values"]["S11"][0]
    # dB=-20 -> magnitude 0.1; deg=90 -> (mag*cos(90), mag*sin(90))
    assert real == pytest.approx(0.0, abs=1e-9)
    assert imag == pytest.approx(0.1, abs=1e-9)


def test_parse_openparem_output_results_csv_ma_format(tmp_path: Path):
    (tmp_path / "proj_results.csv").write_text(RESULTS_CSV_MA)
    result = parse_openparem_output(tmp_path, "proj")
    s_params = result["s_parameters"]
    assert s_params["computed"] is True
    real, imag = s_params["values"]["S11"][0]
    # mag=2.0, deg=180 -> (-2.0, ~0)
    assert real == pytest.approx(-2.0, abs=1e-9)
    assert imag == pytest.approx(0.0, abs=1e-9)
    # frequency unit MHz -> Hz scaling
    assert s_params["frequency_hz"][0] == pytest.approx(2450e6)


def test_parse_openparem_output_farfield_csv(tmp_path: Path):
    (tmp_path / "proj_results.csv").write_text(RESULTS_CSV_RI)
    (tmp_path / "proj_FarField_results.csv").write_text(FARFIELD_CSV)
    result = parse_openparem_output(tmp_path, "proj")
    far_field = result["far_field"]
    assert far_field["computed"] is True
    assert len(far_field["entries"]) == 2
    first = far_field["entries"][0]
    assert first["sport"] == 1
    assert first["frequency_hz"] == pytest.approx(2.4e9)
    assert first["gain_dbi"] == pytest.approx(5.23)
    assert first["directivity_dbi"] == pytest.approx(5.90)
    assert first["radiation_efficiency"] == pytest.approx(0.89)


def test_parse_openparem_output_missing_files_return_computed_false(tmp_path: Path):
    result = parse_openparem_output(tmp_path, "nonexistent_project")
    assert result["s_parameters"]["computed"] is False
    assert "note" in result["s_parameters"]
    assert result["far_field"]["computed"] is False
    assert "note" in result["far_field"]
    assert "touchstone_file" not in result


def test_parse_openparem_output_touchstone_file_detected_when_present(tmp_path: Path):
    (tmp_path / "proj_results.csv").write_text(RESULTS_CSV_RI)
    touchstone = tmp_path / "proj.s1p"
    touchstone.write_text("! fake touchstone\n# GHz S RI R 50\n2.4 -0.1 0.05\n")
    result = parse_openparem_output(tmp_path, "proj")
    assert result["touchstone_file"] == str(touchstone)


def test_parse_openparem_output_no_touchstone_file_when_absent(tmp_path: Path):
    (tmp_path / "proj_results.csv").write_text(RESULTS_CSV_RI)
    result = parse_openparem_output(tmp_path, "proj")
    assert "touchstone_file" not in result


# ---------------------------------------------------------------------------
# OpenParemSimulator.run() subprocess plumbing, against fake executables.
# ---------------------------------------------------------------------------


def _make_fake_openparem(tmp_path: Path, body: str, name: str = "fake_openparem") -> Path:
    return make_fake_executable(tmp_path, body, name=name)


def test_openparem_simulator_invokes_project_file_positionally_serial(tmp_path: Path):
    """Confirm the real OpenParEM3D CLI contract (a single positional .proj filename,
    no other required flags -- see module docstring citation) when mpi_processes is
    not given."""
    script = _make_fake_openparem(
        tmp_path, "import sys\nsys.stdout.write(' '.join(sys.argv[1:]))\n"
    )
    project_file = tmp_path / "model.proj"
    project_file.write_text("#OpenParEM3Dproject 1.0\n")

    simulator = OpenParemSimulator(executable=str(script))
    result = simulator.run({"project_file": str(project_file), "timeout_s": 10})

    assert result.outputs["stdout"].split() == [str(project_file)]
    assert result.status == "COMPLETED"
    assert result.provenance == "SIMULATED"


def test_openparem_simulator_uses_mpirun_when_mpi_processes_given(tmp_path: Path, monkeypatch):
    """Confirm the real parallel CLI contract quoted verbatim from OpenParEM's own
    Installation Manual: `mpirun -q --oversubscribe -np N OpenParEM3D my_project.proj`
    -- see module docstring citation. mpirun itself is not assumed to be installed in
    this environment, so subprocess.run is monkeypatched to capture the argv without
    actually invoking a real mpirun."""
    import subprocess as subprocess_module

    captured = {}

    class _FakeCompleted:
        returncode = 0
        stdout = ""
        stderr = ""

    def _fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        return _FakeCompleted()

    monkeypatch.setattr(subprocess_module, "run", _fake_run)

    project_file = tmp_path / "model.proj"
    project_file.write_text("#OpenParEM3Dproject 1.0\n")

    simulator = OpenParemSimulator(executable="OpenParEM3D")
    simulator.run({"project_file": str(project_file), "timeout_s": 10, "mpi_processes": 4})

    assert captured["cmd"] == [
        "mpirun",
        "-q",
        "--oversubscribe",
        "-np",
        "4",
        "OpenParEM3D",
        str(project_file),
    ]


def test_openparem_simulator_mpi_processes_of_1_uses_serial_form(tmp_path: Path):
    script = _make_fake_openparem(
        tmp_path, "import sys\nsys.stdout.write(' '.join(sys.argv[1:]))\n"
    )
    project_file = tmp_path / "model.proj"
    project_file.write_text("#OpenParEM3Dproject 1.0\n")

    simulator = OpenParemSimulator(executable=str(script))
    result = simulator.run({"project_file": str(project_file), "timeout_s": 10, "mpi_processes": 1})
    assert result.outputs["stdout"].split() == [str(project_file)]


def test_openparem_simulator_nonzero_exit_raises_simulator_error(tmp_path: Path):
    script = _make_fake_openparem(
        tmp_path, 'import sys\nsys.stderr.write("ERROR3143: bad mesh\\n")\nsys.exit(1)\n'
    )
    project_file = tmp_path / "model.proj"
    project_file.write_text("#OpenParEM3Dproject 1.0\n")

    simulator = OpenParemSimulator(executable=str(script))
    with pytest.raises(SimulatorError, match="ERROR3143"):
        simulator.run({"project_file": str(project_file), "timeout_s": 10})


def test_openparem_simulator_timeout_raises_simulator_error(tmp_path: Path):
    script = _make_fake_openparem(tmp_path, "import time\ntime.sleep(5)\n")
    project_file = tmp_path / "model.proj"
    project_file.write_text("#OpenParEM3Dproject 1.0\n")

    simulator = OpenParemSimulator(executable=str(script))
    with pytest.raises(SimulatorError, match="timed out"):
        simulator.run({"project_file": str(project_file), "timeout_s": 1})


def test_openparem_simulator_missing_project_file_raises(tmp_path: Path):
    simulator = OpenParemSimulator(executable="OpenParEM3D")
    with pytest.raises(SimulatorError, match="not found"):
        simulator.run({"project_file": str(tmp_path / "does_not_exist.proj")})


def test_openparem_simulator_picks_up_executable_from_env_var(tmp_path: Path, monkeypatch):
    script = _make_fake_openparem(tmp_path, "import sys\nsys.exit(0)\n")
    monkeypatch.setenv("OPENPAREM3D_BIN", str(script))
    simulator = OpenParemSimulator()
    assert simulator.executable == str(script)


# ---------------------------------------------------------------------------
# run_openparem_simulation end to end, against a fake executable that writes the
# documented output files (per the ticket's fake-executable testing approach). This
# is plumbing + parsing coverage only -- see module docstring for the
# not-verified-against-a-real-binary caveat.
# ---------------------------------------------------------------------------

_FAKE_OPENPAREM3D_PY = '''
import sys

RESULTS_CSV = """{results_csv}"""
FARFIELD_CSV = """{farfield_csv}"""

args = sys.argv[1:]
assert len(args) == 1 and args[0].endswith(".proj"), args

with open("{project_name}_results.csv", "w") as f:
    f.write(RESULTS_CSV)
with open("{project_name}_FarField_results.csv", "w") as f:
    f.write(FARFIELD_CSV)

sys.exit(0)
'''


def _make_fake_openparem3d_py(tmp_path: Path, project_name: str) -> Path:
    body = _FAKE_OPENPAREM3D_PY.format(
        results_csv=RESULTS_CSV_RI,
        farfield_csv=FARFIELD_CSV,
        project_name=project_name,
    )
    return make_fake_executable(tmp_path, body, name="fake_openparem3d_realistic")


def test_run_openparem_simulation_end_to_end_with_fake_executable(tmp_path: Path):
    script = _make_fake_openparem3d_py(tmp_path, "monopole")

    result = run_openparem_simulation(
        mesh_file="monopole_antenna.msh",
        ports=MONOPOLE_PORTS,
        project={
            "frequency_plan": {"linear": [{"start_hz": 1e9, "stop_hz": 3e9, "step_hz": 1e9}]},
            "far_field": {"quantity": "G"},
        },
        project_name="monopole",
        timeout_s=10,
        executable=str(script),
        workdir=str(tmp_path / "run"),
    )

    assert result["provenance"] == "SIMULATED"
    assert result["simulator"] == "OpenParEM3D"
    assert result["status"] == "COMPLETED"
    assert result["s_parameters"]["computed"] is True
    assert result["far_field"]["computed"] is True
    assert len(result["far_field"]["entries"]) == 2
    assert os.path.exists(result["project_file"])
    assert os.path.exists(result["ports_file"])

    project_text = Path(result["project_file"]).read_text()
    assert project_text.startswith("#OpenParEM3Dproject 1.0")
    assert "mesh.file                       monopole_antenna.msh" in project_text

    ports_text = Path(result["ports_file"]).read_text()
    assert ports_text.startswith("#OpenParEMports 1.0")


def test_run_openparem_simulation_propagates_simulator_error_on_failure(tmp_path: Path):
    script = _make_fake_openparem(
        tmp_path, 'import sys\nsys.stderr.write("ERROR3999: fake failure\\n")\nsys.exit(1)\n'
    )
    with pytest.raises(SimulatorError):
        run_openparem_simulation(
            mesh_file="m.msh",
            ports=MONOPOLE_PORTS,
            project={"frequency_plan": {"point": [{"frequency_hz": 2.45e9}]}},
            project_name="monopole",
            timeout_s=10,
            executable=str(script),
            workdir=str(tmp_path / "run2"),
        )


def test_run_openparem_simulation_no_far_field_when_not_requested(tmp_path: Path):
    """Without project['far_field'], the fake tool below (mirroring the real
    PatternDatabase::saveCSV -- see module docstring) never writes a
    *_FarField_results.csv, and this stays honestly uncomputed=False."""
    script = _make_fake_openparem(
        tmp_path,
        f"with open('monopole_results.csv', 'w') as f:\n    f.write({RESULTS_CSV_RI!r})\n",
    )
    result = run_openparem_simulation(
        mesh_file="m.msh",
        ports=MONOPOLE_PORTS,
        project={"frequency_plan": {"point": [{"frequency_hz": 2.45e9}]}},
        project_name="monopole",
        timeout_s=10,
        executable=str(script),
        workdir=str(tmp_path / "run3"),
    )
    assert result["s_parameters"]["computed"] is True
    assert result["far_field"]["computed"] is False
