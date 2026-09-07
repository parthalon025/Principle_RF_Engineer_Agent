# ruff: noqa: E501 -- some literal CSV/header lines here transcribe gerber2ems's
# own exact column layout verbatim (see simulation/kicad_gerber2ems.py's module
# docstring citation); reflowing them would obscure the exact shape under test.
"""Tests for the KiCad + gerber2ems PCB geometry pipeline (issue #65).

Neither kicad-python (kipy), a running KiCad/kicad-cli, gerbv, gerber2ems,
nor a real openEMS binary is installed in this environment (mirroring
tests/test_nec2pp.py's/tests/test_openems.py's own "the real tool isn't
here" premise). This file therefore splits into:

  1. Pure-Python unit tests (generate_gerber2ems_config, extract_kicad_
     stackup, export_kicad_fab_assets, parse_gerber2ems_port_csv,
     parse_gerber2ems_results) -- exercised directly, no subprocess, no
     kicad-python import, via hand-written fakes matching the subset of
     kicad-python's real, primary-source-verified API these functions call
     (see simulation/kicad_gerber2ems.py's module docstring for the exact
     citations each fake mirrors) -- injected through the same
     constructor-injection seam (`api=`) simulation/hfss.py's tests use
     for pyaedt.
  2. KicadGerber2emsSimulator.run() subprocess-plumbing tests against a
     small fake "gerber2ems" script (argument shape, nonzero exit ->
     SimulatorError, timeout -> SimulatorError) -- following
     tests/test_nec2pp.py's exact fake-executable pattern. The fake
     executable is built via conftest.make_fake_executable, so it launches
     correctly on native Windows as well as POSIX (issue #159) -- not a
     platform limitation of this module.
"""

import json
import math
import os
from pathlib import Path

import pytest

import simulation.kicad_gerber2ems as kicad_gerber2ems
from conftest import make_fake_executable
from simulation.base import SimulatorError
from simulation.kicad_gerber2ems import (
    KicadGerber2emsSimulator,
    export_kicad_fab_assets,
    extract_kicad_stackup,
    generate_gerber2ems_config,
    parse_gerber2ems_port_csv,
    parse_gerber2ems_results,
    run_kicad_gerber2ems_simulation,
)

# ---------------------------------------------------------------------------
# Fakes matching the subset of kicad-python's (kipy) real API this module
# calls -- see simulation/kicad_gerber2ems.py's module docstring for the
# primary-source citation each one mirrors.
# ---------------------------------------------------------------------------


class FakeJobResult:
    def __init__(self, output_paths, succeeded=True, message=""):
        self.output_paths = output_paths
        self.succeeded = succeeded
        self.message = message


class FakeDielectricProps:
    def __init__(self, material_name, epsilon_r, loss_tangent):
        self.material_name = material_name
        self.epsilon_r = epsilon_r
        self.loss_tangent = loss_tangent


class FakeDielectricLayer:
    def __init__(self, layers):
        self.layers = layers


class FakeStackupLayer:
    def __init__(self, thickness_nm, layer, kind, enabled=True, dielectric=None):
        self.thickness = thickness_nm
        self.layer = layer
        self.type = kind
        self.enabled = enabled
        self.dielectric = dielectric


class FakeStackup:
    def __init__(self, layers):
        self.layers = layers


class _FakeBoardStackupLayerType:
    BSLT_COPPER = "BSLT_COPPER"
    BSLT_DIELECTRIC = "BSLT_DIELECTRIC"
    BSLT_SOLDERMASK = "BSLT_SOLDERMASK"


class _FakeBoardPb2:
    BoardStackupLayerType = _FakeBoardStackupLayerType()


def _fake_canonical_name(layer):
    return {"BL_F_Cu": "F.Cu", "BL_In1_Cu": "In1.Cu", "BL_B_Cu": "B.Cu"}.get(layer, "Unknown")


class FakeDrillFormat:
    DF_EXCELLON = "DF_EXCELLON"


class FakePositionFormat:
    PF_CSV = "PF_CSV"


class FakePlotSettings:
    def __init__(self):
        self.layers = []


class FakePositionExportSettings:
    def __init__(self):
        self.format = None
        self.single_file = False


def _make_fake_api() -> kicad_gerber2ems._KipyBoardApi:
    return kicad_gerber2ems._KipyBoardApi(
        DrillFormat=FakeDrillFormat,
        PositionFormat=FakePositionFormat,
        PlotSettings=FakePlotSettings,
        PositionExportSettings=FakePositionExportSettings,
        board_pb2=_FakeBoardPb2,
        canonical_name=_fake_canonical_name,
    )


class FakeBoard:
    """Hand-written fake matching the subset of kipy.board.Board's real API
    this module calls (.name, .get_enabled_layers(), .export_gerbers(),
    .export_drill(), .export_position(), .get_stackup()) -- each verified
    against primary source, see simulation/kicad_gerber2ems.py's module
    docstring. Actually writes files to disk (like the real export jobs
    would) so export_kicad_fab_assets's own filesystem logic (drill
    rename, stackup.json write) is exercised for real."""

    def __init__(
        self,
        name="myboard.kicad_pcb",
        stackup_layers=None,
        combined_drill_name="myboard-PTH.drl",
        omit_cu_gerber=False,
        omit_edge_cuts=False,
    ):
        self.name = name
        self._stackup_layers = stackup_layers or []
        self._combined_drill_name = combined_drill_name
        self._omit_cu_gerber = omit_cu_gerber
        self._omit_edge_cuts = omit_edge_cuts
        self.export_gerbers_calls = []
        self.export_drill_calls = []
        self.export_position_calls = []

    def get_enabled_layers(self):
        return ["BL_F_Cu", "BL_B_Cu", "BL_Edge_Cuts"]

    def export_gerbers(
        self, output_path, plot_settings=None, use_protel_file_extensions=True, **kwargs
    ):
        self.export_gerbers_calls.append(
            {
                "output_path": output_path,
                "plot_settings": plot_settings,
                "use_protel_file_extensions": use_protel_file_extensions,
            }
        )
        out_dir = Path(output_path)
        out_dir.mkdir(parents=True, exist_ok=True)
        paths = []
        if not self._omit_cu_gerber:
            f_cu = out_dir / "myboard-F_Cu.gbr"
            f_cu.write_text("G04 fake F.Cu gerber*\n")
            paths.append(str(f_cu))
        if not self._omit_edge_cuts:
            edge = out_dir / "myboard-Edge_Cuts.gbr"
            edge.write_text("G04 fake edge cuts gerber*\n")
            paths.append(str(edge))
        return FakeJobResult(paths)

    def export_drill(self, output_path, format=None):
        self.export_drill_calls.append({"output_path": output_path, "format": format})
        out_dir = Path(output_path)
        out_dir.mkdir(parents=True, exist_ok=True)
        drill = out_dir / self._combined_drill_name
        drill.write_text("M48\n; fake excellon drill\nM30\n")
        return FakeJobResult([str(drill)])

    def export_position(self, output_path, settings=None):
        self.export_position_calls.append({"output_path": output_path, "settings": settings})
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        Path(output_path).write_text(
            "Ref,Val,Package,PosX,PosY,Rot,Side\n"
            '"SP1","Simulation_Port","Simulation_Port",1.000000,2.000000,90.000000,top\n'
        )
        return FakeJobResult([output_path])

    def get_stackup(self):
        return FakeStackup(self._stackup_layers)


DEFAULT_STACKUP_LAYERS = [
    FakeStackupLayer(35000, "BL_F_Cu", "BSLT_COPPER"),  # 35000 nm = 0.035 mm (1oz copper)
    FakeStackupLayer(
        120000,
        None,
        "BSLT_DIELECTRIC",
        dielectric=FakeDielectricLayer([FakeDielectricProps("FR4", 4.3, 0.02)]),
    ),
    FakeStackupLayer(35000, "BL_B_Cu", "BSLT_COPPER"),
    FakeStackupLayer(10000, None, "BSLT_SOLDERMASK"),  # ignored ("other") type
    FakeStackupLayer(999, "BL_In1_Cu", "BSLT_COPPER", enabled=False),  # disabled, must be skipped
]


# ---------------------------------------------------------------------------
# extract_kicad_stackup
# ---------------------------------------------------------------------------


def test_extract_kicad_stackup_translates_copper_and_dielectric_layers():
    stackup = extract_kicad_stackup(
        FakeBoard(stackup_layers=DEFAULT_STACKUP_LAYERS), api=_make_fake_api()
    )

    assert stackup["format_version"] == "1.0"
    layers = stackup["layers"]
    # The disabled In1.Cu entry must be skipped entirely.
    assert len(layers) == 4

    f_cu = layers[0]
    assert f_cu["name"] == "F.Cu"
    assert f_cu["type"] == "copper"
    assert f_cu["thickness"] == pytest.approx(0.035)  # nm -> mm
    assert f_cu["material"] is None

    dielectric = layers[1]
    assert dielectric["type"] == "core"
    assert dielectric["name"] == "dielectric_1"
    assert dielectric["thickness"] == pytest.approx(0.12)
    assert dielectric["material"] == "FR4"
    assert dielectric["epsilon"] == pytest.approx(4.3)
    assert dielectric["lossTangent"] == pytest.approx(0.02)

    b_cu = layers[2]
    assert b_cu["name"] == "B.Cu"
    assert b_cu["type"] == "copper"

    other = layers[3]
    assert other["type"] == "other"


def test_extract_kicad_stackup_empty_board_returns_empty_layers():
    stackup = extract_kicad_stackup(FakeBoard(stackup_layers=[]), api=_make_fake_api())
    assert stackup == {"format_version": "1.0", "layers": []}


# ---------------------------------------------------------------------------
# export_kicad_fab_assets
# ---------------------------------------------------------------------------


def test_export_kicad_fab_assets_happy_path(tmp_path: Path):
    board = FakeBoard(stackup_layers=DEFAULT_STACKUP_LAYERS, combined_drill_name="myboard-PTH.drl")
    fab_dir = tmp_path / "fab"

    result = export_kicad_fab_assets(board, fab_dir, api=_make_fake_api())

    # use_protel_file_extensions=False is REQUIRED (see module docstring) --
    # kipy's own default is True, which would break gerber2ems's glob.
    assert board.export_gerbers_calls[0]["use_protel_file_extensions"] is False
    assert any(p.endswith("F_Cu.gbr") for p in result["gerber_files"])
    assert any(p.endswith("Edge_Cuts.gbr") for p in result["gerber_files"])

    assert result["drill_file"].endswith("myboard-PTH.drl")
    assert Path(result["drill_file"]).exists()
    assert result["warnings"] == []  # already named *-PTH.drl -- no rename needed

    assert result["position_file"] == str(fab_dir / "myboard-pos.csv")
    assert Path(result["position_file"]).exists()
    position_settings = board.export_position_calls[0]["settings"]
    assert position_settings.format == "PF_CSV"
    assert position_settings.single_file is True

    stackup_on_disk = json.loads(Path(result["stackup_file"]).read_text())
    assert stackup_on_disk["layers"][0]["name"] == "F.Cu"


def test_export_kicad_fab_assets_renames_combined_drill_file_and_warns(tmp_path: Path):
    board = FakeBoard(stackup_layers=DEFAULT_STACKUP_LAYERS, combined_drill_name="myboard.drl")
    fab_dir = tmp_path / "fab"

    result = export_kicad_fab_assets(board, fab_dir, api=_make_fake_api())

    assert result["drill_file"] == str(fab_dir / "myboard-PTH.drl")
    assert Path(result["drill_file"]).exists()
    assert not (fab_dir / "myboard.drl").exists()  # renamed away, not copied
    assert len(result["warnings"]) == 1
    assert "plated" in result["warnings"][0]


def test_export_kicad_fab_assets_raises_when_no_copper_gerber(tmp_path: Path):
    board = FakeBoard(stackup_layers=DEFAULT_STACKUP_LAYERS, omit_cu_gerber=True)
    with pytest.raises(SimulatorError, match="_Cu.gbr"):
        export_kicad_fab_assets(board, tmp_path / "fab", api=_make_fake_api())


def test_export_kicad_fab_assets_raises_when_no_edge_cuts_gerber(tmp_path: Path):
    board = FakeBoard(stackup_layers=DEFAULT_STACKUP_LAYERS, omit_edge_cuts=True)
    with pytest.raises(SimulatorError, match="Edge_Cuts.gbr"):
        export_kicad_fab_assets(board, tmp_path / "fab", api=_make_fake_api())


def test_export_kicad_fab_assets_raises_on_failed_gerber_job(tmp_path: Path):
    class FailingBoard(FakeBoard):
        def export_gerbers(self, *args, **kwargs):
            return FakeJobResult([], succeeded=False, message="plot job crashed")

    with pytest.raises(SimulatorError, match="plot job crashed"):
        export_kicad_fab_assets(FailingBoard(), tmp_path / "fab", api=_make_fake_api())


# ---------------------------------------------------------------------------
# generate_gerber2ems_config
# ---------------------------------------------------------------------------


def test_generate_gerber2ems_config_requires_frequency():
    with pytest.raises(ValueError, match="frequency"):
        generate_gerber2ems_config({})


def test_generate_gerber2ems_config_requires_frequency_start_and_stop():
    with pytest.raises(ValueError, match="frequency"):
        generate_gerber2ems_config({"frequency": {"start": 1e6}})


def test_generate_gerber2ems_config_sets_format_version_and_passes_through():
    config = {
        "frequency": {"start": 200e6, "stop": 6e9},
        "max_steps": 50000,
        "ports": [{"width": 185, "length": 500, "impedance": 50, "excite": True}],
        "traces": [{"start": 0, "stop": 1}],
    }
    cfg = generate_gerber2ems_config(config)
    assert cfg["format_version"] == "1.2"
    assert cfg["frequency"] == {"start": 200e6, "stop": 6e9}
    assert cfg["max_steps"] == 50000
    assert cfg["ports"] == config["ports"]
    assert cfg["traces"] == config["traces"]
    assert "differential_pairs" not in cfg  # omitted key stays omitted, not defaulted to []


def test_generate_gerber2ems_config_minimal_frequency_only():
    cfg = generate_gerber2ems_config({"frequency": {"start": 1e6, "stop": 6e9}})
    assert cfg == {"format_version": "1.2", "frequency": {"start": 1e6, "stop": 6e9}}


# ---------------------------------------------------------------------------
# parse_gerber2ems_port_csv / parse_gerber2ems_results
# ---------------------------------------------------------------------------

# Transcribed to match gerber2ems's own Postprocesor.save_port_to_file()
# header/row shape exactly (see simulation/kicad_gerber2ems.py's module
# docstring citation) for a 2-port file where port 0 was excited: a
# frequency-independent S00=0.5+0.5j (mag=0.7071, phase=pi/4), S10=1.0+0.0j
# (mag=1.0, phase=0), delays 0>0=0 / 0>1=1.5e-9 s, Z0 = 25+25j Ohm.
_MAG_00 = math.hypot(0.5, 0.5)
_ARG_00 = math.atan2(0.5, 0.5)
_PORT0_CSV = (
    "Frequency [MHz],|S0-0| [-],|S1-0| [-],Arg(S0-0) [rad],Arg(S1-0) [rad],"
    "Delay 0>0 [s],Delay 0>1 [s],|Z0| [Ohm],Arg(Z0) [rad]\n"
    f"100.000000e+00, {_MAG_00:.6e}, 1.000000e+00, {_ARG_00:.6e}, 0.000000e+00, "
    "0.000000e+00, 1.500000e-09, 35.355339e+00, 0.785398e+00\n"
    f"200.000000e+00, {_MAG_00:.6e}, 1.000000e+00, {_ARG_00:.6e}, 0.000000e+00, "
    "0.000000e+00, 1.500000e-09, 35.355339e+00, 0.785398e+00\n"
)


def test_parse_gerber2ems_port_csv(tmp_path: Path):
    path = tmp_path / "Port_0_data.csv"
    path.write_text(_PORT0_CSV)

    parsed = parse_gerber2ems_port_csv(path)

    assert parsed["excited_port"] == 0
    assert parsed["frequency_hz"] == pytest.approx([100e6, 200e6])
    assert set(parsed["s_parameters"].keys()) == {"S00", "S10"}
    s00 = parsed["s_parameters"]["S00"][0]
    assert s00 == pytest.approx([0.5, 0.5], abs=1e-4)
    s10 = parsed["s_parameters"]["S10"][0]
    assert s10 == pytest.approx([1.0, 0.0], abs=1e-4)
    assert parsed["trace_delay_s"]["0>0"] == pytest.approx([0.0, 0.0])
    assert parsed["trace_delay_s"]["0>1"] == pytest.approx([1.5e-9, 1.5e-9])
    z0 = parsed["impedance_ohms"][0]
    assert z0 == pytest.approx([25.0, 25.0], abs=1e-3)


def test_parse_gerber2ems_results_no_files_returns_computed_false(tmp_path: Path):
    result = parse_gerber2ems_results(tmp_path / "does_not_exist")
    assert result["computed"] is False
    assert result["ports"] == {}
    assert "Port_*_data.csv" in result["note"]


def test_parse_gerber2ems_results_aggregates_all_ports(tmp_path: Path):
    results_dir = tmp_path / "results"
    results_dir.mkdir()
    (results_dir / "Port_0_data.csv").write_text(_PORT0_CSV)

    result = parse_gerber2ems_results(results_dir)

    assert result["computed"] is True
    assert set(result["ports"].keys()) == {"0"}
    assert result["note"] is None


# ---------------------------------------------------------------------------
# KicadGerber2emsSimulator.run() -- workdir precondition checks (no
# subprocess involved).
# ---------------------------------------------------------------------------


def test_kicad_gerber2ems_simulator_requires_fab_dir(tmp_path: Path):
    (tmp_path / "simulation.json").write_text("{}")
    simulator = KicadGerber2emsSimulator(executable="gerber2ems")
    with pytest.raises(SimulatorError, match="fab"):
        simulator.run({"workdir": str(tmp_path)})


def test_kicad_gerber2ems_simulator_requires_config_file(tmp_path: Path):
    (tmp_path / "fab").mkdir()
    simulator = KicadGerber2emsSimulator(executable="gerber2ems")
    with pytest.raises(SimulatorError, match="simulation.json"):
        simulator.run({"workdir": str(tmp_path)})


def test_kicad_gerber2ems_simulator_picks_up_executable_from_env_var(monkeypatch):
    monkeypatch.setenv("GERBER2EMS_BIN", "/opt/gerber2ems/bin/gerber2ems")
    simulator = KicadGerber2emsSimulator()
    assert simulator.executable == "/opt/gerber2ems/bin/gerber2ems"


# ---------------------------------------------------------------------------
# KicadGerber2emsSimulator.run() subprocess plumbing, against fake
# executables -- following tests/test_nec2pp.py's exact pattern. Per this
# ticket's instructions, the same Windows-only fake-executable subprocess
# limitation already documented as pre-existing/expected for
# tests/test_nec2pp.py/tests/test_openems.py on this platform applies here
# too -- not a defect in this module.
# ---------------------------------------------------------------------------


def _make_fake_gerber2ems(tmp_path: Path, body: str) -> Path:
    return make_fake_executable(tmp_path, body, name="fake_gerber2ems")


def _make_workdir(tmp_path: Path) -> Path:
    workdir = tmp_path / "run"
    (workdir / "fab").mkdir(parents=True)
    (workdir / "simulation.json").write_text(json.dumps({"format_version": "1.2"}))
    return workdir


def test_kicad_gerber2ems_simulator_invokes_dash_a(tmp_path: Path):
    script = _make_fake_gerber2ems(tmp_path, "import sys\nsys.stdout.write(' '.join(sys.argv[1:]))\n")
    workdir = _make_workdir(tmp_path)

    simulator = KicadGerber2emsSimulator(executable=str(script))
    result = simulator.run({"workdir": str(workdir), "timeout_s": 10})

    assert result.outputs["stdout"].split() == ["-a"]
    assert result.status == "COMPLETED"
    assert result.provenance == "SIMULATED"


def test_kicad_gerber2ems_simulator_nonzero_exit_raises_simulator_error(tmp_path: Path):
    script = _make_fake_gerber2ems(
        tmp_path, 'import sys\nsys.stderr.write("boom: bad fab fileset\\n")\nsys.exit(1)\n'
    )
    workdir = _make_workdir(tmp_path)

    simulator = KicadGerber2emsSimulator(executable=str(script))
    with pytest.raises(SimulatorError, match="boom"):
        simulator.run({"workdir": str(workdir), "timeout_s": 10})


def test_kicad_gerber2ems_simulator_timeout_raises_simulator_error(tmp_path: Path):
    script = _make_fake_gerber2ems(tmp_path, "import time\ntime.sleep(5)\n")
    workdir = _make_workdir(tmp_path)

    simulator = KicadGerber2emsSimulator(executable=str(script))
    with pytest.raises(SimulatorError, match="timed out"):
        simulator.run({"workdir": str(workdir), "timeout_s": 1})


# ---------------------------------------------------------------------------
# run_kicad_gerber2ems_simulation end to end, against a fake KiCad
# connection (connect_fn/kipy_api injection seams) and a fake "gerber2ems"
# executable that mimics gerber2ems's own postprocessing output shape.
# ---------------------------------------------------------------------------

_FAKE_GERBER2EMS_PY = '''
import sys
import os

args = sys.argv[1:]
assert args == ["-a"], args
assert os.path.isdir("fab"), "fab/ directory must exist in cwd"
assert os.path.isfile("simulation.json"), "simulation.json must exist in cwd"

os.makedirs(os.path.join("ems", "results"), exist_ok=True)
with open(os.path.join("ems", "results", "Port_0_data.csv"), "w") as f:
    f.write("""{sample}""")
sys.exit(0)
'''


def _make_fake_gerber2ems_py(tmp_path: Path) -> Path:
    body = _FAKE_GERBER2EMS_PY.format(sample=_PORT0_CSV)
    return make_fake_executable(tmp_path, body, name="fake_gerber2ems_realistic")


class FakeKicadConnection:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


def test_run_kicad_gerber2ems_simulation_end_to_end_with_fakes(tmp_path: Path):
    script = _make_fake_gerber2ems_py(tmp_path)
    fake_conn = FakeKicadConnection()
    fake_board = FakeBoard(stackup_layers=DEFAULT_STACKUP_LAYERS)
    connect_calls = []

    def fake_connect(board_file, kicad_cli_path=None):
        connect_calls.append({"board_file": board_file, "kicad_cli_path": kicad_cli_path})
        return fake_conn, fake_board

    result = run_kicad_gerber2ems_simulation(
        board_file="my_antenna_feed.kicad_pcb",
        config={"frequency": {"start": 1e8, "stop": 6e9}},
        workdir=str(tmp_path / "run"),
        timeout_s=10,
        executable=str(script),
        connect_fn=fake_connect,
        kipy_api=_make_fake_api(),
    )

    assert connect_calls[0]["board_file"] == "my_antenna_feed.kicad_pcb"
    assert fake_conn.closed is True  # always closed, even though nothing failed

    assert result["provenance"] == "SIMULATED"
    assert "PCB signal-integrity" in result["scope"]
    assert "far-field" in result["scope"] or "far_field" not in result
    assert result["simulator"] == "gerber2ems"
    assert result["status"] == "COMPLETED"
    assert result["computed"] is True
    assert set(result["ports"].keys()) == {"0"}
    assert result["fab_assets"]["warnings"] == []
    assert os.path.exists(result["config_file"])
    written_config = json.loads(Path(result["config_file"]).read_text())
    assert written_config["format_version"] == "1.2"
    assert written_config["frequency"] == {"start": 1e8, "stop": 6e9}


def test_run_kicad_gerber2ems_simulation_closes_connection_even_on_export_failure(tmp_path: Path):
    fake_conn = FakeKicadConnection()
    failing_board = FakeBoard(omit_cu_gerber=True)

    def fake_connect(board_file, kicad_cli_path=None):
        return fake_conn, failing_board

    with pytest.raises(SimulatorError, match="_Cu.gbr"):
        run_kicad_gerber2ems_simulation(
            board_file="broken.kicad_pcb",
            config={"frequency": {"start": 1e8, "stop": 6e9}},
            workdir=str(tmp_path / "run2"),
            connect_fn=fake_connect,
            kipy_api=_make_fake_api(),
        )

    assert fake_conn.closed is True
