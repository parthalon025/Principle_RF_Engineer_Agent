"""Tests for the LTspice circuit-simulation adapter (issue #59).

spicelib is an OPTIONAL pyproject extra (`uv sync --extra ltspice` --
see pyproject.toml's comment on why), not installed by default, so every
test in this file is gated by `pytest.importorskip("spicelib")` -- unlike
tests/test_nec2pp.py / tests/test_openems.py, whose adapters have zero
Python-library dependencies (subprocess + stdlib only) and so never faced
this concern. Under a plain `uv sync && uv run pytest` (no `--extra`) this
whole file is SKIPPED, not failed; under `uv sync --extra ltspice` it runs
for real. It was run for real (not just skipped) during this ticket's own
implementation, confirming every test below genuinely passes against
spicelib's real code -- see the PR description for that run's results.

UNLIKE tests/test_hfss.py (whose pyaedt talks to a paid-license COM/DLL
interface that can never exist in CI, so that file tests adapter logic
against a hand-written fake object standing in for the WHOLE library
instead), this file exercises
spicelib's REAL `LTspice.run()`/`Simulator.create_from()` code for real --
the actual argument-construction and subprocess-invocation logic this
ticket cares about ("format/invocation tested against ... LTspice's own
documented batch-mode behavior") -- against a fake/stub Python script
standing in only for the LTSPICE EXECUTABLE itself, exactly mirroring
tests/test_nec2pp.py's/tests/test_openems.py's own fake-executable pattern.
This is possible, and was already portable to native Windows before
issue #159 fixed the same underlying problem for every other solver
adapter's fake executable, because spicelib's own `Simulator.create_from()`
natively supports a space-separated "<interpreter> <script>" executable
string (the same mechanism it uses for wrapping LTspice with a `wine`
loader on Linux/macOS) -- see `_bind_fake_ltspice()` below. This file's
own `chmod(... S_IEXEC ...)` calls are therefore a POSIX-only no-op
convenience, not load-bearing on Windows: every fake here is launched via
an explicit `[sys.executable, script_path]` argv, never via shebang
resolution, so it never depended on Windows honoring a `#!` line the way
tests/test_nec2pp.py's/tests/test_openems.py's fakes used to (see
tests/conftest.py's `make_fake_executable()` for how those now do the
same "launch through the interpreter explicitly" thing on Windows).

FINDING (spicelib itself, not this module): spicelib 1.6.3's `RawWrite`
default (`fastacces=True`) writes a corrupted/transposed binary layout when
the traces are complex-typed (as an AC Analysis plot's are) -- round-
tripping a synthetic 3-point, 3-trace complex RawWrite/RawRead pair with
the default came back with trace values interleaved across traces instead
of within one trace (verified by hand during this implementation pass, not
guessed). `fastacces=False` round-trips correctly and is what every fixture
below uses. This is a spicelib bug report candidate, not a bug in this
repo's own code, and does not affect `parse_ltspice_raw()` itself (which
only ever READS a .raw file, via spicelib's RawRead, and does not write
one) -- it only affects how this test file's own synthetic .raw fixtures
must be constructed.
"""

import stat
import sys
from pathlib import Path

import pytest

pytest.importorskip("spicelib")

from spicelib.simulators.ltspice_simulator import LTspice  # noqa: E402

from simulation.base import SimulatorError  # noqa: E402
from simulation.ltspice import (  # noqa: E402
    LtspiceSimulator,
    _bind_ltspice_executable,
    parse_ltspice_raw,
    run_ltspice_simulation,
)

AC_NETLIST = (
    "* RC low-pass, AC analysis\n"
    "V1 in 0 AC 1\n"
    "R1 in out 50\n"
    "C1 out 0 1n\n"
    ".ac dec 10 1meg 10meg\n"
    ".end\n"
)


# ---------------------------------------------------------------------------
# Fake "LTspice" executables -- Python scripts run as `[sys.executable,
# script_path]`, mimicking real LTspice batch-mode behavior: argv is
# `-Run -b <netlist_file> [switches...]` (spicelib's own documented
# contract, see simulation/ltspice.py's module docstring), and on success a
# `<netlist>.raw` + `<netlist>.log` pair is written next to the netlist.
# ---------------------------------------------------------------------------


def _bind_fake(tmp_path: Path, script_body: str) -> type:
    """Write `script_body` as a fake LTspice executable and bind a private
    LTspice-derived class to `[sys.executable, script_path]` directly
    (bypassing create_from()'s single-path-string parsing, which does not
    cleanly support a two-part "interpreter + script" form on every
    platform) -- see _bind_ltspice_executable_via_string below for the
    alternate, create_from()-driven path this module's own public API
    actually uses."""
    script = tmp_path / "fake_ltspice.py"
    script.write_text(script_body)
    script.chmod(script.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    bound = type("_TestBoundLTspice", (LTspice,), {})
    bound.spice_exe = [sys.executable, str(script)]
    bound.process_name = "python"
    return bound


_FAKE_SUCCESS_BODY = """
import sys
from pathlib import Path
from spicelib import RawWrite
from spicelib.raw.raw_write import Trace

args = sys.argv[1:]
assert args[0] == "-Run", args
assert args[1] == "-b", args
# spicelib's own LTspice.run() (non-macOS-native branch -- the one this
# fake executable is bound into on Linux) always prepends "Z:" to the
# netlist path, treating this fake executable as if it were the real
# LTspice.exe running under wine (see ltspice_simulator.py's own "Drive
# letter 'Z' is the link from wine to the host platform's root directory"
# comment) -- strip it back off, exactly as wine itself would resolve it.
netlist_arg = args[2][2:] if args[2].startswith("Z:") else args[2]
netlist_path = Path(netlist_arg)
netlist_path.with_suffix(".log").write_text(
    "Fake LTspice run OK\\nDirect Newton iteration for .op point succeeded.\\n"
)

freq = [1e6, 2e6, 3e6]
vin = [complex(1.0, 0.0)] * 3
vout = [complex(0.5, -0.1), complex(0.4, -0.2), complex(0.3, -0.3)]

# fastacces=False -- see this file's module docstring "FINDING" note.
writer = RawWrite(plot_name="AC Analysis", fastacces=False)
writer.add_trace(Trace("frequency", freq, numerical_type="complex"))
writer.add_trace(Trace("V(in)", vin))
writer.add_trace(Trace("V(out)", vout))
writer.save(str(netlist_path.with_suffix(".raw")))
sys.exit(0)
"""

_FAKE_FAILURE_BODY = """
import sys
from pathlib import Path

args = sys.argv[1:]
# See _FAKE_SUCCESS_BODY's comment above on stripping spicelib's own
# wine-style "Z:" netlist-path prefix.
netlist_arg = args[2][2:] if args[2].startswith("Z:") else args[2]
netlist_path = Path(netlist_arg)
netlist_path.with_suffix(".log").write_text("Fatal error: circuit does not converge\\n")
sys.exit(1)
"""

_FAKE_SLOW_BODY = """
import sys
import time

time.sleep(5)
sys.exit(0)
"""


# ---------------------------------------------------------------------------
# LtspiceSimulator.run() subprocess plumbing, against fake executables.
# ---------------------------------------------------------------------------


def test_ltspice_simulator_invokes_run_and_dash_b_and_parses_raw(tmp_path: Path):
    """Confirms the real spicelib LTspice.run() batch-mode contract
    (-Run -b <netlist>, see module docstring citation) is what actually
    gets shelled out, and that a resulting real .raw file is produced and
    reported back."""
    workdir = tmp_path / "run"
    workdir.mkdir()
    netlist = workdir / "model.net"
    netlist.write_text(AC_NETLIST)

    bound = _bind_fake(tmp_path, _FAKE_SUCCESS_BODY)
    simulator = LtspiceSimulator(simulator_cls=bound)
    result = simulator.run({"netlist_file": str(netlist), "workdir": str(workdir), "timeout_s": 15})

    assert result.status == "COMPLETED"
    assert result.simulator == "LTspice"
    assert result.provenance == "SIMULATED"
    assert Path(result.outputs["raw_file"]).exists()
    assert result.outputs["raw_file"] == str(netlist.with_suffix(".raw"))
    assert "Fake LTspice run OK" in result.outputs["log_text"]


def test_ltspice_simulator_nonzero_exit_raises_simulator_error_with_log(tmp_path: Path):
    workdir = tmp_path / "run"
    workdir.mkdir()
    netlist = workdir / "model.net"
    netlist.write_text(AC_NETLIST)

    bound = _bind_fake(tmp_path, _FAKE_FAILURE_BODY)
    simulator = LtspiceSimulator(simulator_cls=bound)
    with pytest.raises(SimulatorError, match="does not converge"):
        simulator.run({"netlist_file": str(netlist), "workdir": str(workdir), "timeout_s": 15})


def test_ltspice_simulator_missing_raw_after_success_exit_raises(tmp_path: Path):
    """A fake executable that exits 0 but writes no .raw file (the real
    LTspice binary would never do this, but the adapter must not silently
    report success without the promised output either)."""
    workdir = tmp_path / "run"
    workdir.mkdir()
    netlist = workdir / "model.net"
    netlist.write_text(AC_NETLIST)

    bound = _bind_fake(tmp_path, "import sys\nsys.exit(0)\n")
    simulator = LtspiceSimulator(simulator_cls=bound)
    with pytest.raises(SimulatorError, match="no .raw output"):
        simulator.run({"netlist_file": str(netlist), "workdir": str(workdir), "timeout_s": 15})


def test_ltspice_simulator_timeout_raises_simulator_error(tmp_path: Path):
    workdir = tmp_path / "run"
    workdir.mkdir()
    netlist = workdir / "model.net"
    netlist.write_text(AC_NETLIST)

    bound = _bind_fake(tmp_path, _FAKE_SLOW_BODY)
    simulator = LtspiceSimulator(simulator_cls=bound)
    with pytest.raises(SimulatorError, match="timed out"):
        simulator.run({"netlist_file": str(netlist), "workdir": str(workdir), "timeout_s": 1})


def test_ltspice_simulator_missing_netlist_file_raises(tmp_path: Path):
    bound = _bind_fake(tmp_path, _FAKE_SUCCESS_BODY)
    simulator = LtspiceSimulator(simulator_cls=bound)
    with pytest.raises(SimulatorError, match="not found"):
        simulator.run({"netlist_file": str(tmp_path / "does_not_exist.net")})


def test_ltspice_simulator_not_available_raises_clear_simulator_error(tmp_path: Path):
    """No spice_exe at all -- e.g. no LTspice installed and no override
    given -- must raise this codebase's own SimulatorError, not spicelib's
    own differently-typed SpiceSimulatorError leaking through un-translated."""
    unavailable = type("_Unavailable", (LTspice,), {"spice_exe": [], "process_name": None})
    netlist = tmp_path / "model.net"
    netlist.write_text(AC_NETLIST)

    simulator = LtspiceSimulator(simulator_cls=unavailable)
    with pytest.raises(SimulatorError, match="No LTspice executable available"):
        simulator.run({"netlist_file": str(netlist)})


# ---------------------------------------------------------------------------
# Executable resolution -- LTSPICE_BIN env var, and the private-subclass
# binding that must not mutate spicelib's own shared LTspice class.
# ---------------------------------------------------------------------------


def test_ltspice_simulator_picks_up_executable_from_env_var(monkeypatch):
    # sys.executable always exists on this host, so is_available() can
    # confirm the binding actually took without needing a real LTspice.
    monkeypatch.setenv("LTSPICE_BIN", sys.executable)
    simulator = LtspiceSimulator()
    assert simulator.executable == sys.executable
    assert simulator._simulator_cls.spice_exe == [Path(sys.executable).as_posix()]
    assert simulator._simulator_cls.is_available()


def test_bind_ltspice_executable_does_not_mutate_shared_ltspice_class():
    """create_from()'s cls.spice_exe = ... assignment (spicelib/sim/
    simulator.py, cited in simulation/ltspice.py's module docstring) would
    mutate the real, shared `LTspice` class object for the whole process if
    called on it directly -- _bind_ltspice_executable must sink that onto a
    private subclass instead. A real regression here would silently make
    every LtspiceSimulator(executable=...) call in the same process share
    one one executable path, last-write-wins."""
    before = list(LTspice.spice_exe)
    bound = _bind_ltspice_executable(sys.executable)
    assert bound.spice_exe == [Path(sys.executable).as_posix()]
    assert bound is not LTspice
    assert LTspice.spice_exe == before  # unchanged


def test_bind_ltspice_executable_two_calls_are_independent():
    fake_a = _bind_ltspice_executable(sys.executable)
    # A second, different path -- if binding mutated shared state, this
    # would also silently change fake_a's spice_exe.
    other = str(Path(sys.executable).parent)  # any other existing path
    fake_b = _bind_ltspice_executable(other)
    assert fake_a.spice_exe != fake_b.spice_exe


# ---------------------------------------------------------------------------
# parse_ltspice_raw() -- against real spicelib-written .raw fixtures (see
# module docstring's fastacces=False finding).
# ---------------------------------------------------------------------------


def _write_ac_raw_fixture(path: Path) -> None:
    from spicelib import RawWrite
    from spicelib.raw.raw_write import Trace

    writer = RawWrite(plot_name="AC Analysis", fastacces=False)
    writer.add_trace(Trace("frequency", [1e6, 2e6, 3e6], numerical_type="complex"))
    writer.add_trace(Trace("V(in)", [complex(1.0, 0.0)] * 3))
    writer.add_trace(Trace("V(out)", [complex(0.5, -0.1), complex(0.4, -0.2), complex(0.3, -0.3)]))
    writer.save(str(path))


def _write_tran_raw_fixture(path: Path) -> None:
    from spicelib import RawWrite
    from spicelib.raw.raw_write import Trace

    writer = RawWrite(plot_name="Transient Analysis", fastacces=False)
    writer.add_trace(Trace("time", [0.0, 1e-9, 2e-9]))
    writer.add_trace(Trace("V(out)", [0.0, 0.63, 0.86]))
    writer.save(str(path))


def test_parse_ltspice_raw_ac_analysis_returns_complex_traces(tmp_path: Path):
    raw_file = tmp_path / "ac.raw"
    _write_ac_raw_fixture(raw_file)

    result = parse_ltspice_raw(raw_file)

    assert result["plot_name"] == "AC Analysis"
    assert result["trace_names"] == ["frequency", "V(in)", "V(out)"]
    assert result["has_axis"] is True
    assert result["n_points"] == 3
    assert result["axis"] == [[1e6, 0.0], [2e6, 0.0], [3e6, 0.0]]
    assert result["traces"]["V(out)"] == [[0.5, -0.1], [0.4, -0.2], [0.3, -0.3]]


def test_parse_ltspice_raw_transient_analysis_returns_real_traces(tmp_path: Path):
    raw_file = tmp_path / "tran.raw"
    _write_tran_raw_fixture(raw_file)

    result = parse_ltspice_raw(raw_file)

    assert result["plot_name"] == "Transient Analysis"
    assert result["has_axis"] is True
    assert result["axis"] == pytest.approx([0.0, 1e-9, 2e-9])
    assert result["traces"]["V(out)"] == pytest.approx([0.0, 0.63, 0.86])
    # Real-valued traces are plain floats, not [re, im] pairs.
    assert all(isinstance(v, float) for v in result["traces"]["V(out)"])


# ---------------------------------------------------------------------------
# run_ltspice_simulation() end to end, through the public executable=
# string parameter (an "<interpreter> <script>" form -- see this file's
# module docstring for why this is a real, spicelib-supported invocation
# shape, not a test-only shortcut).
# ---------------------------------------------------------------------------


def test_run_ltspice_simulation_end_to_end_with_netlist_text(tmp_path: Path):
    script = tmp_path / "fake_ltspice.py"
    script.write_text(_FAKE_SUCCESS_BODY)
    exe = Path(sys.executable).as_posix() + " " + script.as_posix()

    result = run_ltspice_simulation(
        netlist=AC_NETLIST,
        executable=exe,
        workdir=str(tmp_path / "run"),
        timeout_s=15,
    )

    assert result["provenance"] == "SIMULATED"
    assert result["status"] == "COMPLETED"
    assert result["simulator"] == "LTspice"
    assert result["plot_name"] == "AC Analysis"
    assert result["traces"]["V(out)"] == [[0.5, -0.1], [0.4, -0.2], [0.3, -0.3]]
    assert Path(result["netlist_file"]).read_text() == AC_NETLIST
    assert Path(result["raw_file"]).exists()


def test_run_ltspice_simulation_accepts_existing_netlist_file(tmp_path: Path):
    script = tmp_path / "fake_ltspice.py"
    script.write_text(_FAKE_SUCCESS_BODY)
    exe = Path(sys.executable).as_posix() + " " + script.as_posix()

    netlist_file = tmp_path / "existing.net"
    netlist_file.write_text(AC_NETLIST)

    result = run_ltspice_simulation(
        netlist_file=str(netlist_file),
        executable=exe,
        workdir=str(tmp_path / "run2"),
        timeout_s=15,
    )
    assert result["netlist_file"] == str(netlist_file.resolve())
    assert result["status"] == "COMPLETED"


def test_run_ltspice_simulation_propagates_simulator_error_on_failure(tmp_path: Path):
    script = tmp_path / "fake_ltspice.py"
    script.write_text(_FAKE_FAILURE_BODY)
    exe = Path(sys.executable).as_posix() + " " + script.as_posix()

    with pytest.raises(SimulatorError):
        run_ltspice_simulation(
            netlist=AC_NETLIST,
            executable=exe,
            workdir=str(tmp_path / "run3"),
            timeout_s=15,
        )


def test_run_ltspice_simulation_requires_netlist_or_netlist_file():
    with pytest.raises(ValueError, match="requires either"):
        run_ltspice_simulation()
