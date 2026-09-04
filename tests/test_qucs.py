# ruff: noqa: E501 -- this file transcribes Qucs Dataset text verbatim from
# the primary source cited below; reflowing it would break the exact
# numeric-line shape the parser under test reads.
"""Tests for Qucs-S/qucsator netlist generation, execution, and S-parameter
result parsing (issue #58).

The real `qucsator_rf` binary is NOT installed in this environment
(confirmed via `which qucsator_rf` / `which qucsator` during implementation,
both exit 1) so `QucsSimulator.run()` is exercised here only against small
fake "qucsator_rf" scripts checked in below (via `tmp_path`), per the same
Phase 6-8 fake-executable testing decision ticket #38/#39 used for
NEC2++/openEMS: subprocess plumbing (argument shape, nonzero exit, timeout,
missing-output-file) and result parsing are tested; real RF circuit physics
is out of scope for automated tests.

The netlist component/directive syntax and the "Qucs Dataset" output text
format were verified against qucsator_rf's own primary sources -- see the
header comment in simulation/qucs.py for the exact citations (a real
fixture from qucsator_rf's own test suite, tests/basic/u=ri/u=ri@sp.net;
src/ucs.cpp for the CLI contract; src/dataset.cpp for the dataset print
format; each component's own src/components/*.cpp for its property
schema). The sample dataset text used in test_parse_qucs_dataset_* below is
hand-constructed to match that documented/cited numeric-line format
(dataset.cpp's `printData()` fprintf calls) -- it has NOT been produced by,
or checked against, a real qucsator_rf run.
"""

import os
import stat
import sys
from pathlib import Path

import pytest

from simulation.base import SimulatorError
from simulation.qucs import (
    QucsSimulator,
    generate_qucs_netlist,
    parse_qucs_dataset,
    run_qucs_simulation,
)

# A 2-port, 2-frequency-point Qucs Dataset, hand-built to match the exact
# numeric-line shapes dataset.cpp's printData() emits (see module docstring
# for the citation): a real-only line ("  %+.20e"), and complex lines with
# both a positive and a negative imaginary sign ("  %+.20e%cj%.20e").
TWO_PORT_DATASET = """<Qucs Dataset 0.0.19>
<indep frequency 2>
  +1.00000000000000000000e+09
  +2.00000000000000000000e+09
</indep>
<dep S[1,1] frequency>
  +1.00000000000000000000e-01
  +5.00000000000000000000e-02-j2.00000000000000000000e-02
</dep>
<dep S[2,1] frequency>
  +9.00000000000000000000e-01+j1.00000000000000000000e-02
  +8.50000000000000000000e-01
</dep>
<dep S[1,2] frequency>
  +9.00000000000000000000e-01+j1.00000000000000000000e-02
  +8.50000000000000000000e-01
</dep>
<dep S[2,2] frequency>
  +1.00000000000000000000e-01
  +5.00000000000000000000e-02-j2.00000000000000000000e-02
</dep>
"""


def _make_fake_qucsator(tmp_path: Path, body: str) -> Path:
    """Write a small fake 'qucsator_rf' shell script and make it executable."""
    script = tmp_path / "fake_qucsator_rf.sh"
    script.write_text("#!/bin/sh\n" + body)
    script.chmod(script.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return script


ONE_PORT_CIRCUIT = {
    "ports": [{"node": "n1", "num": 1, "z_ohms": 50.0}],
    "components": [
        {"type": "R", "name": "Rload", "nodes": ["n1", "gnd"], "properties": {"R": 50.0}}
    ],
}

TWO_PORT_CIRCUIT = {
    "ports": [
        {"node": "n1", "num": 1, "z_ohms": 50.0},
        {"node": "n2", "num": 2, "z_ohms": 50.0},
    ],
    "components": [
        {"type": "R", "name": "Rseries", "nodes": ["n1", "n2"], "properties": {"R": 10.0}}
    ],
}

LIN_ANALYSIS = {"sweep_type": "lin", "start_hz": 1e9, "stop_hz": 2e9, "points": 2}


# ---------------------------------------------------------------------------
# Netlist generation
# ---------------------------------------------------------------------------


def test_generate_qucs_netlist_one_port_card_order_and_fields():
    netlist = generate_qucs_netlist(ONE_PORT_CIRCUIT, LIN_ANALYSIS)
    lines = netlist.strip("\n").split("\n")

    assert lines[0].startswith("#")
    assert lines[1] == 'Pac:P1 n1 gnd Num="1" Z="50" P="0" f="1000000000"'
    assert lines[2] == 'R:Rload n1 gnd R="50"'
    assert (
        lines[-1] == '.SP:SP1 Type="lin" Start="1000000000" Stop="2000000000" Points="2" Noise="no"'
    )


def test_generate_qucs_netlist_two_port_pac_lines_use_num_property():
    netlist = generate_qucs_netlist(TWO_PORT_CIRCUIT, LIN_ANALYSIS)
    lines = netlist.split("\n")
    assert 'Pac:P1 n1 gnd Num="1" Z="50" P="0" f="1000000000"' in lines
    assert 'Pac:P2 n2 gnd Num="2" Z="50" P="0" f="1000000000"' in lines
    assert 'R:Rseries n1 n2 R="10"' in lines


def test_generate_qucs_netlist_log_sweep():
    analysis = {"sweep_type": "log", "start_hz": 1e6, "stop_hz": 1e9, "points": 50}
    netlist = generate_qucs_netlist(ONE_PORT_CIRCUIT, analysis)
    sp_line = next(line for line in netlist.split("\n") if line.startswith(".SP"))
    assert 'Type="log"' in sp_line
    assert 'Points="50"' in sp_line


def test_generate_qucs_netlist_empty_ports_raises():
    with pytest.raises(ValueError, match="ports"):
        generate_qucs_netlist({"ports": []}, LIN_ANALYSIS)


def test_generate_qucs_netlist_port_missing_node_raises():
    with pytest.raises(ValueError, match="node"):
        generate_qucs_netlist({"ports": [{"num": 1}]}, LIN_ANALYSIS)


def test_generate_qucs_netlist_duplicate_port_nums_raises():
    circuit = {
        "ports": [
            {"node": "n1", "num": 1},
            {"node": "n2", "num": 1},
        ]
    }
    with pytest.raises(ValueError, match="unique"):
        generate_qucs_netlist(circuit, LIN_ANALYSIS)


def test_generate_qucs_netlist_unknown_component_type_raises():
    circuit = {
        "ports": [{"node": "n1", "num": 1}],
        "components": [{"type": "MLIN", "nodes": ["n1", "gnd"], "properties": {}}],
    }
    with pytest.raises(ValueError, match="MLIN"):
        generate_qucs_netlist(circuit, LIN_ANALYSIS)


def test_generate_qucs_netlist_component_missing_required_property_raises():
    circuit = {
        "ports": [{"node": "n1", "num": 1}],
        "components": [{"type": "TLIN", "nodes": ["n1", "gnd"], "properties": {"Z": 50.0}}],
    }
    with pytest.raises(ValueError, match="L"):
        generate_qucs_netlist(circuit, LIN_ANALYSIS)


def test_generate_qucs_netlist_component_wrong_node_count_raises():
    circuit = {
        "ports": [{"node": "n1", "num": 1}],
        "components": [{"type": "R", "nodes": ["n1"], "properties": {"R": 50.0}}],
    }
    with pytest.raises(ValueError, match="2 'nodes'"):
        generate_qucs_netlist(circuit, LIN_ANALYSIS)


def test_generate_qucs_netlist_invalid_sweep_type_raises():
    with pytest.raises(ValueError, match="sweep_type"):
        generate_qucs_netlist(
            ONE_PORT_CIRCUIT, {"start_hz": 1e9, "stop_hz": 2e9, "sweep_type": "const"}
        )


def test_generate_qucs_netlist_missing_start_stop_raises():
    with pytest.raises(ValueError, match="start_hz"):
        generate_qucs_netlist(ONE_PORT_CIRCUIT, {"points": 10})


# ---------------------------------------------------------------------------
# Output dataset parsing (against the hand-built-to-spec sample -- see
# module docstring for the honest not-verified-against-a-real-binary
# caveat).
# ---------------------------------------------------------------------------


def test_parse_qucs_dataset_extracts_frequency():
    result = parse_qucs_dataset(TWO_PORT_DATASET)
    assert result["frequency_hz"] == pytest.approx([1e9, 2e9])


def test_parse_qucs_dataset_extracts_real_only_value():
    result = parse_qucs_dataset(TWO_PORT_DATASET)
    s11 = result["s_parameters"]["values"]["S11"]
    assert s11[0] == pytest.approx([0.1, 0.0])


def test_parse_qucs_dataset_extracts_negative_imaginary():
    result = parse_qucs_dataset(TWO_PORT_DATASET)
    s11 = result["s_parameters"]["values"]["S11"]
    assert s11[1] == pytest.approx([0.05, -0.02])


def test_parse_qucs_dataset_extracts_positive_imaginary():
    result = parse_qucs_dataset(TWO_PORT_DATASET)
    s21 = result["s_parameters"]["values"]["S21"]
    assert s21[0] == pytest.approx([0.9, 0.01])


def test_parse_qucs_dataset_all_four_sparams_present():
    result = parse_qucs_dataset(TWO_PORT_DATASET)
    assert set(result["s_parameters"]["values"]) == {"S11", "S12", "S21", "S22"}


def test_parse_qucs_dataset_computed_true_with_method_note():
    result = parse_qucs_dataset(TWO_PORT_DATASET)
    assert result["s_parameters"]["computed"] is True
    assert "spsolver" in result["s_parameters"]["method"]


def test_parse_qucs_dataset_missing_sections_returns_honest_false():
    result = parse_qucs_dataset("NOTHING USEFUL HERE\n")
    assert result["frequency_hz"] == []
    assert result["s_parameters"]["computed"] is False
    assert "note" in result["s_parameters"]


# ---------------------------------------------------------------------------
# QucsSimulator.run() subprocess plumbing, against fake executables.
# ---------------------------------------------------------------------------


def test_qucs_simulator_invokes_dash_i_and_dash_o_with_real_paths(tmp_path: Path):
    """Confirm the real qucsator_rf CLI contract (-i FILENAME -o FILENAME,
    both real file paths -- see module docstring citation) is what actually
    gets shelled out, and that -o's target is read back as the dataset
    (unlike NEC2++'s "-o -" stdout convention)."""
    output_marker = "<Qucs Dataset fake>\n"
    script = _make_fake_qucsator(
        tmp_path,
        f'echo "$@" >&2\n'
        f'out=""\n'
        f'while [ "$#" -gt 0 ]; do\n'
        f'  if [ "$1" = "-o" ]; then shift; out="$1"; fi\n'
        f"  shift\n"
        f"done\n"
        f"printf %s '{output_marker}' > \"$out\"\n",
    )
    input_file = tmp_path / "model.net"
    input_file.write_text('# test\n.SP:SP1 Type="lin" Start="1e9" Stop="2e9" Points="2"\n')

    simulator = QucsSimulator(executable=str(script))
    result = simulator.run({"input_file": str(input_file), "timeout_s": 10})

    assert result.status == "COMPLETED"
    assert result.provenance == "SIMULATED"
    assert result.outputs["dataset"] == output_marker
    assert "-i" in result.outputs["stderr"]
    assert str(input_file) in result.outputs["stderr"]


def test_qucs_simulator_nonzero_exit_raises_simulator_error(tmp_path: Path):
    script = _make_fake_qucsator(tmp_path, 'echo "line 3: syntax error" >&2\nexit 1\n')
    input_file = tmp_path / "model.net"
    input_file.write_text("# test\n")

    simulator = QucsSimulator(executable=str(script))
    with pytest.raises(SimulatorError, match="syntax error"):
        simulator.run({"input_file": str(input_file), "timeout_s": 10})


def test_qucs_simulator_timeout_raises_simulator_error(tmp_path: Path):
    script = _make_fake_qucsator(tmp_path, "sleep 5\n")
    input_file = tmp_path / "model.net"
    input_file.write_text("# test\n")

    simulator = QucsSimulator(executable=str(script))
    with pytest.raises(SimulatorError, match="timed out"):
        simulator.run({"input_file": str(input_file), "timeout_s": 1})


def test_qucs_simulator_missing_input_file_raises(tmp_path: Path):
    simulator = QucsSimulator(executable="qucsator_rf")
    with pytest.raises(SimulatorError, match="not found"):
        simulator.run({"input_file": str(tmp_path / "does_not_exist.net")})


def test_qucs_simulator_zero_exit_but_no_output_file_raises(tmp_path: Path):
    """A 0 exit with no dataset on disk must not be silently treated as a
    successful, empty run."""
    script = _make_fake_qucsator(tmp_path, "exit 0\n")
    input_file = tmp_path / "model.net"
    input_file.write_text("# test\n")

    simulator = QucsSimulator(executable=str(script))
    with pytest.raises(SimulatorError, match="did not produce"):
        simulator.run({"input_file": str(input_file), "timeout_s": 10})


def test_qucs_simulator_picks_up_executable_from_env_var(tmp_path: Path, monkeypatch):
    script = _make_fake_qucsator(tmp_path, "exit 0\n")
    monkeypatch.setenv("QUCSATOR_BIN", str(script))
    simulator = QucsSimulator()
    assert simulator.executable == str(script)


def test_qucs_simulator_default_executable_name_is_qucsator_rf(monkeypatch):
    monkeypatch.delenv("QUCSATOR_BIN", raising=False)
    simulator = QucsSimulator()
    assert simulator.executable == "qucsator_rf"


# ---------------------------------------------------------------------------
# run_qucs_simulation end to end, against a fake executable that mimics the
# documented dataset shape (per the ticket's fake-executable testing
# approach). This is plumbing + parsing coverage only -- see module
# docstring for the not-verified-against-a-real-binary caveat.
# ---------------------------------------------------------------------------

_FAKE_QUCSATOR_PY = '''#!{python}
import sys

DATASET = """{dataset}"""

args = sys.argv[1:]
assert "-i" in args, args
in_idx = args.index("-i")
assert args[in_idx + 1], args
out_idx = args.index("-o")
outfile = args[out_idx + 1]
with open(outfile, "w") as f:
    f.write(DATASET)
sys.exit(0)
'''


def _make_fake_qucsator_py(tmp_path: Path, dataset_text: str) -> Path:
    script = tmp_path / "fake_qucsator_rf_realistic.py"
    script.write_text(_FAKE_QUCSATOR_PY.format(python=sys.executable, dataset=dataset_text))
    script.chmod(script.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return script


def test_run_qucs_simulation_end_to_end_with_fake_executable(tmp_path: Path):
    script = _make_fake_qucsator_py(tmp_path, TWO_PORT_DATASET)

    result = run_qucs_simulation(
        circuit=TWO_PORT_CIRCUIT,
        analysis=LIN_ANALYSIS,
        timeout_s=10,
        executable=str(script),
        workdir=str(tmp_path / "run"),
    )

    assert result["provenance"] == "SIMULATED"
    assert result["simulator"] == "Qucs-S/qucsator"
    assert result["status"] == "COMPLETED"
    assert result["frequency_hz"] == pytest.approx([1e9, 2e9])
    assert result["s_parameters"]["computed"] is True
    assert set(result["s_parameters"]["values"]) == {"S11", "S12", "S21", "S22"}
    assert os.path.exists(result["input_file"])
    netlist_text = Path(result["input_file"]).read_text()
    assert "Pac:P1" in netlist_text
    assert ".SP:SP1" in netlist_text


def test_run_qucs_simulation_writes_full_nport_touchstone_file(tmp_path: Path):
    """Unlike simulation/openems.py (one S-matrix column per run), a single
    qucsator_rf .SP run yields the FULL N-port matrix -- confirm a real
    .s2p Touchstone file is written and loadable."""
    script = _make_fake_qucsator_py(tmp_path, TWO_PORT_DATASET)

    result = run_qucs_simulation(
        circuit=TWO_PORT_CIRCUIT,
        analysis=LIN_ANALYSIS,
        timeout_s=10,
        executable=str(script),
        workdir=str(tmp_path / "run"),
    )

    assert "touchstone_file" in result
    touchstone_path = Path(result["touchstone_file"])
    assert touchstone_path.exists()
    assert touchstone_path.suffix == ".s2p"

    import skrf as rf

    network = rf.Network(str(touchstone_path))
    assert network.number_of_ports == 2
    assert network.f == pytest.approx([1e9, 2e9])
    assert network.s[0, 0, 0] == pytest.approx(complex(0.1, 0.0))
    assert network.s[1, 0, 0] == pytest.approx(complex(0.05, -0.02))


def test_run_qucs_simulation_propagates_simulator_error_on_failure(tmp_path: Path):
    script = _make_fake_qucsator(tmp_path, 'echo "netlist error" >&2\nexit 1\n')
    with pytest.raises(SimulatorError):
        run_qucs_simulation(
            circuit=ONE_PORT_CIRCUIT,
            analysis=LIN_ANALYSIS,
            timeout_s=10,
            executable=str(script),
            workdir=str(tmp_path / "run2"),
        )
