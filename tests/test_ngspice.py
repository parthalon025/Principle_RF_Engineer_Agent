"""Tests for ngspice netlist generation, execution, and result parsing
(issue #57).

The real `ngspice` binary is NOT installed in this environment (confirmed
via `which ngspice` during implementation) so `NgspiceSimulator.run()` is
exercised here only against small fake "ngspice" scripts checked in below
(via `tmp_path`), the same subprocess-plumbing-only testing approach
tests/test_nec2pp.py and tests/test_openems.py use for their own
simulators: argument shape, nonzero exit, and timeout are tested; the
physics itself is out of scope for automated tests.

The netlist card format, `.control`/`wrdata` batch-output mechanics, and
CLI contract were verified against the primary ngspice manual -- see the
header comment in simulation/ngspice.py for the full, per-fact citation
list. The sample `wrdata` output text used in
test_parse_ngspice_wrdata_* below is hand-constructed to match that
documented column layout (one shared scale column via `set wr_singlescale`,
then a real value or a real/imag pair per requested output), not
transcribed from a real ngspice run -- see that module's honest caveat.
"""

import os
import stat
import sys
from pathlib import Path

import numpy as np
import pytest

from simulation.base import SimulatorError
from simulation.ngspice import (
    NgspiceSimulator,
    generate_ngspice_netlist,
    parse_ngspice_wrdata,
    run_ngspice_simulation,
)

MATCHING_NETWORK_JOB = {
    "components": [
        {"type": "R", "name": "Rsrc", "n1": "in", "n2": "src", "value": 50.0},
        {"type": "L", "name": "L1", "n1": "src", "n2": "out", "value": 10e-9},
        {"type": "C", "name": "C1", "n1": "out", "n2": "0", "value": 5e-12},
        {"type": "R", "name": "Rload", "n1": "out", "n2": "0", "value": 50.0},
        {
            "type": "V",
            "name": "Vin",
            "n1": "in",
            "n2": "0",
            "dc": 0.0,
            "ac_mag": 1.0,
            "ac_phase": 0.0,
        },
    ],
    "analysis": {
        "type": "ac",
        "sweep_type": "dec",
        "points": 20,
        "start_freq_hz": 1e8,
        "stop_freq_hz": 1e10,
    },
    "outputs": ["v(out)", "v(src)"],
}


def _make_fake_ngspice(tmp_path: Path, body: str) -> Path:
    """Write a small fake 'ngspice' shell script and make it executable."""
    script = tmp_path / "fake_ngspice.sh"
    script.write_text("#!/bin/sh\n" + body)
    script.chmod(script.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return script


# ---------------------------------------------------------------------------
# Netlist generation
# ---------------------------------------------------------------------------


def test_generate_ngspice_netlist_components_and_ac_control_block():
    netlist = generate_ngspice_netlist(MATCHING_NETWORK_JOB, "out.dat")
    lines = netlist.strip("\n").split("\n")

    assert lines[0].startswith("* ")
    assert "Rsrc in src 50" in lines
    assert "L1 src out 1e-08" in lines
    assert "C1 out 0 5e-12" in lines
    assert "Rload out 0 50" in lines
    assert "Vin in 0 DC 0 AC 1 0" in lines
    assert ".control" in lines
    assert "set wr_singlescale" in lines
    assert "ac dec 20 1e+08 1e+10" in lines
    assert "wrdata out.dat v(out) v(src)" in lines
    assert ".endc" in lines
    assert lines[-1] == ".end"


def test_generate_ngspice_netlist_tran_control_block():
    job = {
        "components": MATCHING_NETWORK_JOB["components"],
        "analysis": {"type": "tran", "step_s": 1e-9, "stop_s": 1e-7, "start_s": 0.0},
        "outputs": ["v(out)"],
    }
    netlist = generate_ngspice_netlist(job, "tran_out.dat")
    assert "tran 1e-09 1e-07 0" in netlist


def test_generate_ngspice_netlist_op_control_block():
    job = {
        "components": MATCHING_NETWORK_JOB["components"],
        "analysis": {"type": "op"},
        "outputs": ["v(out)"],
    }
    netlist = generate_ngspice_netlist(job, "op_out.dat")
    lines = netlist.split("\n")
    assert "op" in lines
    assert "wrdata op_out.dat v(out)" in lines


def test_generate_ngspice_netlist_raw_cards_inserted_verbatim():
    job = {
        "components": [{"type": "R", "name": "R1", "n1": "1", "n2": "0", "value": 1e3}],
        "raw_cards": ["Q1 2 3 4 QMOD", ".MODEL QMOD NPN(BF=100)"],
        "analysis": {"type": "op"},
        "outputs": ["v(1)"],
    }
    netlist = generate_ngspice_netlist(job, "out.dat")
    assert "Q1 2 3 4 QMOD" in netlist
    assert ".MODEL QMOD NPN(BF=100)" in netlist


def test_generate_ngspice_netlist_missing_outputs_raises():
    job = {"components": MATCHING_NETWORK_JOB["components"], "analysis": {"type": "op"}}
    with pytest.raises(ValueError, match="outputs"):
        generate_ngspice_netlist(job, "out.dat")


def test_generate_ngspice_netlist_missing_analysis_raises():
    job = {"components": MATCHING_NETWORK_JOB["components"], "outputs": ["v(out)"]}
    with pytest.raises(ValueError, match="analysis"):
        generate_ngspice_netlist(job, "out.dat")


def test_generate_ngspice_netlist_invalid_sweep_type_raises():
    job = {
        "components": MATCHING_NETWORK_JOB["components"],
        "analysis": {
            "type": "ac",
            "sweep_type": "bogus",
            "points": 10,
            "start_freq_hz": 1e6,
            "stop_freq_hz": 1e9,
        },
        "outputs": ["v(out)"],
    }
    with pytest.raises(ValueError, match="sweep_type"):
        generate_ngspice_netlist(job, "out.dat")


def test_generate_ngspice_netlist_unknown_component_type_raises():
    job = {
        "components": [{"type": "Q", "name": "Q1", "n1": "1", "n2": "0", "value": 1.0}],
        "analysis": {"type": "op"},
        "outputs": ["v(1)"],
    }
    with pytest.raises(ValueError, match="raw_cards"):
        generate_ngspice_netlist(job, "out.dat")


# ---------------------------------------------------------------------------
# wrdata output parsing
# ---------------------------------------------------------------------------


def test_parse_ngspice_wrdata_ac_real_imag_pairs():
    # One shared scale column (set wr_singlescale), then (real, imag) per
    # output, for 2 outputs at 2 frequency points.
    text = "1e+08 1.0 0.0 0.5 -0.1\n1e+09 0.8 -0.2 0.3 -0.4\n"
    result = parse_ngspice_wrdata(text, ["v(out)", "v(src)"], "ac")
    assert result["scale_name"] == "frequency_hz"
    assert result["scale"] == pytest.approx([1e8, 1e9])
    assert np.allclose(result["values"]["v(out)"], [[1.0, 0.0], [0.8, -0.2]])
    assert np.allclose(result["values"]["v(src)"], [[0.5, -0.1], [0.3, -0.4]])


def test_parse_ngspice_wrdata_tran_real_values():
    text = "0.0 1.0\n1e-09 0.9\n2e-09 0.7\n"
    result = parse_ngspice_wrdata(text, ["v(out)"], "tran")
    assert result["scale_name"] == "time_s"
    assert result["scale"] == pytest.approx([0.0, 1e-9, 2e-9])
    assert result["values"]["v(out)"] == pytest.approx([1.0, 0.9, 0.7])


def test_parse_ngspice_wrdata_skips_non_numeric_lines():
    text = "Some header text\n0.0 1.0\n\n1e-09 0.9\n"
    result = parse_ngspice_wrdata(text, ["v(out)"], "tran")
    assert result["scale"] == pytest.approx([0.0, 1e-9])


def test_parse_ngspice_wrdata_skips_mismatched_column_count_lines():
    # A stray line with a different token count than the expected
    # (1 scale + 1 per output for tran) must be skipped, not misparsed.
    text = "0.0 1.0 2.0 3.0\n1e-09 0.9\n"
    result = parse_ngspice_wrdata(text, ["v(out)"], "tran")
    assert result["scale"] == pytest.approx([1e-9])
    assert result["values"]["v(out)"] == pytest.approx([0.9])


def test_parse_ngspice_wrdata_empty_text_returns_empty():
    result = parse_ngspice_wrdata("", ["v(out)"], "tran")
    assert result["scale"] == []
    assert result["values"]["v(out)"] == []


# ---------------------------------------------------------------------------
# NgspiceSimulator.run() subprocess plumbing, against fake executables.
# ---------------------------------------------------------------------------


def test_ngspice_simulator_invokes_dash_b_dash_o_and_netlist(tmp_path: Path):
    script = _make_fake_ngspice(tmp_path, 'echo "$@" > "$3"\n')
    netlist_file = tmp_path / "model.cir"
    netlist_file.write_text("* test\n.end\n")

    simulator = NgspiceSimulator(executable=str(script))
    result = simulator.run({"netlist_file": str(netlist_file), "timeout_s": 10})

    tokens = result.outputs["log"].split()
    assert tokens[0] == "-b"
    assert tokens[1] == "-o"
    assert tokens[2].endswith("ngspice.log")
    assert tokens[3] == str(netlist_file)
    assert result.status == "COMPLETED"
    assert result.provenance == "SIMULATED"


def test_ngspice_simulator_nonzero_exit_raises_simulator_error_with_log_content(tmp_path: Path):
    script = _make_fake_ngspice(tmp_path, 'echo "Error: bad netlist card" > "$3"\nexit 1\n')
    netlist_file = tmp_path / "model.cir"
    netlist_file.write_text("* test\n.end\n")

    simulator = NgspiceSimulator(executable=str(script))
    with pytest.raises(SimulatorError, match="bad netlist card"):
        simulator.run({"netlist_file": str(netlist_file), "timeout_s": 10})


def test_ngspice_simulator_timeout_raises_simulator_error(tmp_path: Path):
    script = _make_fake_ngspice(tmp_path, "sleep 5\n")
    netlist_file = tmp_path / "model.cir"
    netlist_file.write_text("* test\n.end\n")

    simulator = NgspiceSimulator(executable=str(script))
    with pytest.raises(SimulatorError, match="timed out"):
        simulator.run({"netlist_file": str(netlist_file), "timeout_s": 1})


def test_ngspice_simulator_missing_netlist_file_raises(tmp_path: Path):
    simulator = NgspiceSimulator(executable="ngspice")
    with pytest.raises(SimulatorError, match="not found"):
        simulator.run({"netlist_file": str(tmp_path / "does_not_exist.cir")})


def test_ngspice_simulator_picks_up_executable_from_env_var(tmp_path: Path, monkeypatch):
    script = _make_fake_ngspice(tmp_path, "exit 0\n")
    monkeypatch.setenv("NGSPICE_BIN", str(script))
    simulator = NgspiceSimulator()
    assert simulator.executable == str(script)


# ---------------------------------------------------------------------------
# run_ngspice_simulation end to end, against a fake executable that writes a
# wrdata-shaped output file (plumbing + parsing coverage only -- see module
# docstring for the not-verified-against-a-real-binary caveat).
# ---------------------------------------------------------------------------

_FAKE_NGSPICE_PY = """#!{python}
import sys

args = sys.argv[1:]
assert args[0] == "-b", args
assert args[1] == "-o", args
log_path = args[2]
netlist_path = args[3]
assert netlist_path.endswith(".cir"), args

with open(log_path, "w") as f:
    f.write("")

with open({output_name!r}, "w") as f:
    f.write({output_content!r})

sys.exit(0)
"""


def _make_fake_ngspice_py(tmp_path: Path, output_name: str, output_content: str) -> Path:
    script = tmp_path / "fake_ngspice_realistic.py"
    script.write_text(
        _FAKE_NGSPICE_PY.format(
            python=sys.executable, output_name=output_name, output_content=output_content
        )
    )
    script.chmod(script.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return script


def test_run_ngspice_simulation_end_to_end_ac(tmp_path: Path):
    wrdata_text = "1e+08 2.0 0.0 1.0 0.0\n1e+09 1.5 -0.5 0.8 -0.2\n"
    script = _make_fake_ngspice_py(tmp_path, "ngspice_output.dat", wrdata_text)

    result = run_ngspice_simulation(
        job=MATCHING_NETWORK_JOB,
        timeout_s=10,
        executable=str(script),
        workdir=str(tmp_path / "run"),
    )

    assert result["provenance"] == "SIMULATED"
    assert result["simulator"] == "ngspice"
    assert result["status"] == "COMPLETED"
    assert result["scale_name"] == "frequency_hz"
    assert result["scale"] == pytest.approx([1e8, 1e9])
    assert np.allclose(result["values"]["v(out)"], [[2.0, 0.0], [1.5, -0.5]])
    assert os.path.exists(result["netlist_file"])
    deck_text = Path(result["netlist_file"]).read_text()
    assert deck_text.startswith("* ")
    assert ".end" in deck_text


def test_run_ngspice_simulation_propagates_simulator_error_on_failure(tmp_path: Path):
    script = _make_fake_ngspice(tmp_path, 'echo "netlist error" > "$3"\nexit 1\n')
    with pytest.raises(SimulatorError):
        run_ngspice_simulation(
            job=MATCHING_NETWORK_JOB,
            timeout_s=10,
            executable=str(script),
            workdir=str(tmp_path / "run2"),
        )
