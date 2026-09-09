"""Tests for Xyce netlist generation, execution, and result parsing
(issue #57).

The real `Xyce` binary is NOT installed in this environment (confirmed via
`which Xyce`/`which xyce` during implementation) so `XyceSimulator.run()`
is exercised here only against small fake "Xyce" scripts checked in below
(via `tmp_path`), the same subprocess-plumbing-only testing approach
tests/test_nec2pp.py and tests/test_openems.py use for their own
simulators: argument shape, nonzero exit, and timeout are tested; the
physics itself is out of scope for automated tests.

The netlist card format, `.PRINT`/`.LIN`/Port-Device syntax, and CLI
contract were verified against the primary Xyce Reference Guide (Sandia
SAND2023-13759, v7.8) -- see the header comment in simulation/xyce.py for
the full, per-fact citation list, INCLUDING that module's own honest
confidence caveat specifically about the `.LIN` S-parameter path (a
secondary source raised a conflicting claim about a *different*,
unrelated Xyce feature -- see that module's docstring). The sample CSV/
Touchstone text used below is hand-constructed to match the documented
format, not transcribed from a real Xyce run.
"""

import os
from pathlib import Path

import numpy as np
import pytest
from conftest import make_fake_executable

from simulation.base import SimulatorError
from simulation.xyce import (
    XyceSimulator,
    generate_xyce_netlist,
    parse_xyce_csv,
    run_xyce_simulation,
)

FILTER_COMPONENTS = [
    {"type": "L", "name": "L1", "n1": "in", "n2": "out", "value": 10e-9},
    {"type": "C", "name": "C1", "n1": "out", "n2": "0", "value": 5e-12},
]

TWO_PORT_JOB = {
    "components": FILTER_COMPONENTS,
    "ports": [
        {"name": "P1", "n1": "in", "n2": "0", "port": 1, "z0": 50.0},
        {"name": "P2", "n1": "out", "n2": "0", "port": 2, "z0": 50.0},
    ],
    "analysis": {
        "type": "ac",
        "sweep_type": "dec",
        "points": 10,
        "start_freq_hz": 1e8,
        "stop_freq_hz": 1e10,
    },
}

PRINT_ONLY_JOB = {
    "components": FILTER_COMPONENTS
    + [{"type": "V", "name": "V1", "n1": "in", "n2": "0", "dc": 0.0, "ac_mag": 1.0}],
    "analysis": {
        "type": "ac",
        "sweep_type": "dec",
        "points": 10,
        "start_freq_hz": 1e8,
        "stop_freq_hz": 1e10,
    },
    "outputs": ["VDB(out)", "VP(out)"],
}

HB_JOB = {
    "components": FILTER_COMPONENTS
    + [{"type": "V", "name": "V1", "n1": "in", "n2": "0", "dc": 0.0, "ac_mag": 1.0}],
    "analysis": {"type": "hb", "fundamental_freqs_hz": [2.4e9]},
    "outputs": ["VDB(out)", "VP(out)"],
}


def _make_fake_xyce(tmp_path: Path, body: str) -> Path:
    """Write a small fake 'Xyce' executable (a Python script body,
    launched cross-platform -- see conftest.make_fake_executable)."""
    return make_fake_executable(tmp_path, body, name="fake_xyce")


# ---------------------------------------------------------------------------
# Netlist generation
# ---------------------------------------------------------------------------


def test_generate_xyce_netlist_components_and_lin_line():
    netlist = generate_xyce_netlist(
        TWO_PORT_JOB, print_file=None, touchstone_file="xyce_s_parameters.s2p"
    )
    lines = netlist.strip("\n").split("\n")

    assert lines[0].startswith("* ")
    assert "L1 in out 1e-08" in lines
    assert "C1 out 0 5e-12" in lines
    assert "P1 in 0 port=1 z0=50" in lines
    assert "P2 out 0 port=2 z0=50" in lines
    assert ".AC DEC 10 1e+08 1e+10" in lines
    assert (
        ".LIN SPARCALC=1 FORMAT=TOUCHSTONE LINTYPE=S DATAFORMAT=RI "
        "FILE=xyce_s_parameters.s2p" in lines
    )
    assert lines[-1] == ".END"


def test_generate_xyce_netlist_print_line_for_outputs():
    netlist = generate_xyce_netlist(
        PRINT_ONLY_JOB, print_file="xyce_output.csv", touchstone_file=None
    )
    assert ".PRINT AC FORMAT=CSV FILE=xyce_output.csv VDB(out) VP(out)" in netlist
    assert ".LIN" not in netlist


def test_generate_xyce_netlist_no_print_line_when_print_file_is_none():
    netlist = generate_xyce_netlist(PRINT_ONLY_JOB, print_file=None, touchstone_file=None)
    assert ".PRINT" not in netlist


def test_generate_xyce_netlist_tran_line():
    job = {
        "components": FILTER_COMPONENTS,
        "analysis": {"type": "tran", "step_s": 1e-9, "stop_s": 1e-7, "start_s": 0.0},
        "outputs": ["V(out)"],
    }
    netlist = generate_xyce_netlist(job, print_file="out.csv", touchstone_file=None)
    assert ".TRAN 1e-09 1e-07 0" in netlist
    assert ".PRINT TRAN FORMAT=CSV FILE=out.csv V(out)" in netlist


def test_generate_xyce_netlist_op_line():
    job = {"components": FILTER_COMPONENTS, "analysis": {"type": "op"}}
    netlist = generate_xyce_netlist(job, print_file=None, touchstone_file=None)
    assert ".OP" in netlist.split("\n")


# ---------------------------------------------------------------------------
# .HB (Harmonic Balance) netlist generation (issue #282) -- see
# simulation/xyce.py's module docstring for the Reference Guide `.HB`
# citation (section 2.1.13, p.45) and the `.PRINT HB` two-output-file
# honest scope note.
# ---------------------------------------------------------------------------


def test_generate_xyce_netlist_hb_line():
    job = {
        "components": FILTER_COMPONENTS,
        "analysis": {"type": "hb", "fundamental_freqs_hz": [2.4e9]},
    }
    netlist = generate_xyce_netlist(job, print_file=None, touchstone_file=None)
    assert ".HB 2.4e+09" in netlist.split("\n")


def test_generate_xyce_netlist_hb_multitone_line():
    # Xyce's `.HB <fundamental frequencies>` general form (Reference Guide
    # section 2.1.13, p.45) takes one or more space-separated frequencies --
    # more than one selects multi-tone HB (e.g. an LO tone and an RF tone
    # driving a mixer).
    job = {
        "components": FILTER_COMPONENTS,
        "analysis": {"type": "hb", "fundamental_freqs_hz": [1e4, 2e2]},
    }
    netlist = generate_xyce_netlist(job, print_file=None, touchstone_file=None)
    assert ".HB 10000 200" in netlist.split("\n")


def test_generate_xyce_netlist_hb_print_line_for_outputs():
    netlist = generate_xyce_netlist(HB_JOB, print_file="xyce_output.csv", touchstone_file=None)
    assert ".PRINT HB FORMAT=CSV FILE=xyce_output.csv VDB(out) VP(out)" in netlist


def test_generate_xyce_netlist_hb_missing_fundamental_freqs_raises():
    job = {"components": FILTER_COMPONENTS, "analysis": {"type": "hb"}}
    with pytest.raises(ValueError, match="fundamental_freqs_hz"):
        generate_xyce_netlist(job, print_file=None, touchstone_file=None)


def test_generate_xyce_netlist_hb_empty_fundamental_freqs_raises():
    job = {
        "components": FILTER_COMPONENTS,
        "analysis": {"type": "hb", "fundamental_freqs_hz": []},
    }
    with pytest.raises(ValueError, match="fundamental_freqs_hz"):
        generate_xyce_netlist(job, print_file=None, touchstone_file=None)


def test_generate_xyce_netlist_raw_cards_inserted_verbatim():
    job = {
        "components": [{"type": "R", "name": "R1", "n1": "1", "n2": "0", "value": 1e3}],
        "raw_cards": ["Q1 2 3 4 QMOD", ".MODEL QMOD NPN(BF=100)"],
        "analysis": {"type": "op"},
    }
    netlist = generate_xyce_netlist(job, print_file=None, touchstone_file=None)
    assert "Q1 2 3 4 QMOD" in netlist
    assert ".MODEL QMOD NPN(BF=100)" in netlist


def test_generate_xyce_netlist_ports_without_ac_analysis_raises():
    job = {
        "components": FILTER_COMPONENTS,
        "ports": TWO_PORT_JOB["ports"],
        "analysis": {"type": "tran", "step_s": 1e-9, "stop_s": 1e-7},
    }
    with pytest.raises(ValueError, match="analysis\\['type'\\]"):
        generate_xyce_netlist(job, print_file=None, touchstone_file="out.s2p")


def test_generate_xyce_netlist_missing_analysis_raises():
    job = {"components": FILTER_COMPONENTS}
    with pytest.raises(ValueError, match="analysis"):
        generate_xyce_netlist(job, print_file=None, touchstone_file=None)


def test_generate_xyce_netlist_port_missing_field_raises():
    job = {
        "components": FILTER_COMPONENTS,
        "ports": [{"name": "P1", "n1": "in", "n2": "0"}],  # missing "port"
        "analysis": TWO_PORT_JOB["analysis"],
    }
    with pytest.raises(ValueError, match="port"):
        generate_xyce_netlist(job, print_file=None, touchstone_file="out.s1p")


# ---------------------------------------------------------------------------
# .PRINT CSV output parsing
# ---------------------------------------------------------------------------


def test_parse_xyce_csv_basic():
    text = (
        "FREQ,VDB(OUT),VP(OUT)\n"
        "100000000.000000,-3.010000,-45.000000\n"
        "1000000000.000000,-6.020000,-90.000000\n"
    )
    result = parse_xyce_csv(text)
    assert result["scale_name"] == "FREQ"
    assert result["scale"] == pytest.approx([1e8, 1e9])
    assert result["values"]["VDB(OUT)"] == pytest.approx([-3.01, -6.02])
    assert result["values"]["VP(OUT)"] == pytest.approx([-45.0, -90.0])


def test_parse_xyce_csv_skips_blank_lines():
    text = "FREQ,V(OUT)\n1.0,2.0\n\n2.0,3.0\n\n"
    result = parse_xyce_csv(text)
    assert result["scale"] == pytest.approx([1.0, 2.0])
    assert result["values"]["V(OUT)"] == pytest.approx([2.0, 3.0])


def test_parse_xyce_csv_empty_text_returns_empty():
    result = parse_xyce_csv("")
    assert result["scale"] == []
    assert result["values"] == {}


# ---------------------------------------------------------------------------
# XyceSimulator.run() subprocess plumbing, against fake executables.
# ---------------------------------------------------------------------------


def test_xyce_simulator_invokes_bare_netlist_path(tmp_path: Path):
    script = _make_fake_xyce(tmp_path, 'import sys\nsys.stdout.write(" ".join(sys.argv[1:]))\n')
    netlist_file = tmp_path / "model.cir"
    netlist_file.write_text("* test\n.END\n")

    simulator = XyceSimulator(executable=str(script))
    result = simulator.run({"netlist_file": str(netlist_file), "timeout_s": 10})

    tokens = result.outputs["stdout"].split()
    assert tokens == [str(netlist_file)]
    assert result.status == "COMPLETED"
    assert result.provenance == "SIMULATED"


def test_xyce_simulator_nonzero_exit_raises_simulator_error(tmp_path: Path):
    script = _make_fake_xyce(
        tmp_path, 'import sys\nsys.stderr.write("netlist parsing error\\n")\nsys.exit(1)\n'
    )
    netlist_file = tmp_path / "model.cir"
    netlist_file.write_text("* test\n.END\n")

    simulator = XyceSimulator(executable=str(script))
    with pytest.raises(SimulatorError, match="netlist parsing error"):
        simulator.run({"netlist_file": str(netlist_file), "timeout_s": 10})


def test_xyce_simulator_timeout_raises_simulator_error(tmp_path: Path):
    script = _make_fake_xyce(tmp_path, "import time\ntime.sleep(5)\n")
    netlist_file = tmp_path / "model.cir"
    netlist_file.write_text("* test\n.END\n")

    simulator = XyceSimulator(executable=str(script))
    with pytest.raises(SimulatorError, match="timed out"):
        simulator.run({"netlist_file": str(netlist_file), "timeout_s": 1})


def test_xyce_simulator_missing_netlist_file_raises(tmp_path: Path):
    simulator = XyceSimulator(executable="Xyce")
    with pytest.raises(SimulatorError, match="not found"):
        simulator.run({"netlist_file": str(tmp_path / "does_not_exist.cir")})


def test_xyce_simulator_picks_up_executable_from_env_var(tmp_path: Path, monkeypatch):
    script = _make_fake_xyce(tmp_path, "import sys\nsys.exit(0)\n")
    monkeypatch.setenv("XYCE_BIN", str(script))
    simulator = XyceSimulator()
    assert simulator.executable == str(script)


# ---------------------------------------------------------------------------
# run_xyce_simulation end to end, against fake executables that write the
# output file(s) a real Xyce run would produce (plumbing + parsing coverage
# only -- see module docstring for the not-verified-against-a-real-binary
# caveat, and its extra caveat specifically on the .LIN path).
# ---------------------------------------------------------------------------

_FAKE_XYCE_PY = """
import sys

netlist_path = sys.argv[1]
assert netlist_path.endswith(".cir"), sys.argv

OUTPUT_FILES = {output_files!r}
for name, content in OUTPUT_FILES.items():
    with open(name, "w") as f:
        f.write(content)

sys.exit(0)
"""


def _make_fake_xyce_py(tmp_path: Path, output_files: dict[str, str]) -> Path:
    body = _FAKE_XYCE_PY.format(output_files=output_files)
    return make_fake_executable(tmp_path, body, name="fake_xyce_realistic")


def test_run_xyce_simulation_end_to_end_print_only(tmp_path: Path):
    csv_text = (
        "FREQ,VDB(OUT),VP(OUT)\n"
        "100000000.000000,-3.010000,-45.000000\n"
        "1000000000.000000,-6.020000,-90.000000\n"
    )
    script = _make_fake_xyce_py(tmp_path, {"xyce_output.csv": csv_text})

    result = run_xyce_simulation(
        job=PRINT_ONLY_JOB,
        timeout_s=10,
        executable=str(script),
        workdir=str(tmp_path / "run"),
    )

    assert result["provenance"] == "SIMULATED"
    assert result["simulator"] == "Xyce"
    assert result["status"] == "COMPLETED"
    assert result["scale_name"] == "FREQ"
    assert result["scale"] == pytest.approx([1e8, 1e9])
    assert result["values"]["VDB(OUT)"] == pytest.approx([-3.01, -6.02])
    assert "s_parameters" not in result
    assert os.path.exists(result["netlist_file"])


_TOUCHSTONE_S2P = """# GHz S RI R 50
0.1 0.99 0.01 0.02 0.10 0.02 0.10 0.99 0.01
1.0 0.90 0.05 0.10 0.20 0.10 0.20 0.90 0.05
"""


def test_run_xyce_simulation_end_to_end_lin_touchstone(tmp_path: Path):
    script = _make_fake_xyce_py(tmp_path, {"xyce_s_parameters.s2p": _TOUCHSTONE_S2P})

    result = run_xyce_simulation(
        job=TWO_PORT_JOB,
        timeout_s=10,
        executable=str(script),
        workdir=str(tmp_path / "run"),
    )

    assert result["provenance"] == "SIMULATED"
    s_params = result["s_parameters"]
    assert s_params["computed"] is True
    assert len(s_params["frequency_hz"]) == 2
    assert s_params["z0_ohms"] == pytest.approx(50.0)
    assert "touchstone_file" in result
    assert os.path.exists(result["touchstone_file"])

    import skrf as rf

    network = rf.Network(result["touchstone_file"])
    assert network.nports == 2
    assert np.allclose(network.f, np.array([0.1e9, 1.0e9]))


def test_run_xyce_simulation_end_to_end_hb_print(tmp_path: Path):
    # (issue #282) `.PRINT HB FORMAT=CSV` round-trips through the same
    # parse_xyce_csv() path as `.AC`/`.TRAN` -- `_ANALYSIS_TYPES` accepting "hb" is the only
    # thing this needed; `want_print` and the generic
    # `.PRINT {type} FORMAT=CSV FILE=...` line-generation already handled
    # any accepted analysis type unmodified (see simulation/xyce.py's
    # header docstring for the honest caveat on a real Xyce run's actual
    # `.PRINT HB` file-output shape, which was not independently verified).
    csv_text = "FREQ,VDB(OUT),VP(OUT)\n2400000000.000000,-3.010000,-45.000000\n"
    script = _make_fake_xyce_py(tmp_path, {"xyce_output.csv": csv_text})

    result = run_xyce_simulation(
        job=HB_JOB,
        timeout_s=10,
        executable=str(script),
        workdir=str(tmp_path / "run"),
    )

    assert result["provenance"] == "SIMULATED"
    assert result["scale_name"] == "FREQ"
    assert result["scale"] == pytest.approx([2.4e9])
    assert result["values"]["VDB(OUT)"] == pytest.approx([-3.01])
    assert result["values"]["VP(OUT)"] == pytest.approx([-45.0])
    assert "s_parameters" not in result


def test_run_xyce_simulation_missing_touchstone_file_stays_uncomputed(tmp_path: Path):
    # The fake executable exits 0 but doesn't write the expected Touchstone
    # file -- must stay honestly uncomputed, not fabricate results.
    script = _make_fake_xyce_py(tmp_path, {})

    result = run_xyce_simulation(
        job=TWO_PORT_JOB,
        timeout_s=10,
        executable=str(script),
        workdir=str(tmp_path / "run"),
    )
    assert result["s_parameters"]["computed"] is False
    assert "touchstone_file" not in result


def test_run_xyce_simulation_op_analysis_has_no_print_values(tmp_path: Path):
    job = {"components": FILTER_COMPONENTS, "analysis": {"type": "op"}, "outputs": ["V(out)"]}
    script = _make_fake_xyce_py(tmp_path, {})

    result = run_xyce_simulation(
        job=job, timeout_s=10, executable=str(script), workdir=str(tmp_path / "run")
    )
    assert "values" not in result
    assert "scale" not in result


def test_run_xyce_simulation_propagates_simulator_error_on_failure(tmp_path: Path):
    script = _make_fake_xyce(
        tmp_path, 'import sys\nsys.stderr.write("netlist error\\n")\nsys.exit(1)\n'
    )
    with pytest.raises(SimulatorError):
        run_xyce_simulation(
            job=PRINT_ONLY_JOB,
            timeout_s=10,
            executable=str(script),
            workdir=str(tmp_path / "run2"),
        )
