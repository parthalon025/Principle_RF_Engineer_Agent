"""LTspice circuit simulation adapter (issue #59).

LOWEST PRIORITY of this batch's "ADS alternative" tickets: LTspice is the
only non-open-source item in the batch (see docs/LICENSE_MATRIX.md) and is
capability-redundant with ngspice/Xyce/Qucs-S -- its value is vendor
device-model-library familiarity and universal engineer familiarity, not
new simulation capability. Built solidly but deliberately not over-invested
in, per the ticket's own guidance.

DEPENDENCY PICK -- PyLTSpice vs. spicelib (verified 2026-09-02):
Both are actively maintained by the same author (Nuno Brum) and published
to PyPI within the last few months of this writing (spicelib 1.6.3 / July
2026, PyLTSpice 6.0.1 / June 2026, per each project's own PyPI page).
PyLTSpice's own README/docs state it "is mostly based on the spicelib
package, being the main difference to it is the fact that LTSpice is
automatically selected to perform all simulations" -- i.e. PyLTSpice is now
a thin LTspice-only convenience wrapper OVER spicelib, which is the actual
multi-simulator (LTspice/NGspice/QSPICE/Xyce) toolchain and the one that
carries the `LTspice`/`Simulator`/`RawRead`/`RawWrite` classes this module
uses directly. This module depends on spicelib (not PyLTSpice) for that
reason: no functionality is lost (PyLTSpice's LTspice-selection convenience
isn't needed since this module already hard-codes LTspice), one fewer
transitive dependency layer, and consistency with this repo's other
simulation adapters is unaffected either way since none of them use either
package. See docs/LICENSE_MATRIX.md for spicelib's own license (GPLv3,
confirmed against github.com/nunobrum/spicelib's own LICENSE file).

spicelib is an OPTIONAL pyproject extra (`uv sync --extra ltspice` /
`pip install '.[ltspice]'`), not a hard dependency -- see pyproject.toml's
comment for why (mirrors the hfss/measurement extras: most installs,
including CI, will never touch LTspice). Every spicelib import in this
module is therefore lazy (inside a function, not at module top level), so
`import simulation.ltspice` itself always succeeds even when spicelib isn't
installed; only actually driving a simulation requires it, and does so
with a clear install hint rather than a bare ImportError traceback.

SOURCES CONSULTED (primary; all fetched directly from spicelib's own
upstream GitHub repository, github.com/nunobrum/spicelib, `main` branch,
2026-09-02 -- see the per-fact citations below):
  - LTspice's real batch-mode CLI contract -- `LTspice.run(netlist_file,
    cmd_line_switches=None, timeout=None, stdout=None, stderr=None,
    cwd=None, exe_log=False) -> int`, which on Windows (this repo's own
    dev/CI platform) builds `cls.spice_exe + ['-Run'] + ['-b'] +
    [netlist_file.as_posix()] + cmd_line_switches` (on Linux/macOS it
    additionally wraps with a `wine` loader and a `Z:`-prefixed path, since
    LTspice itself is Windows-native there) and shells out via
    `subprocess.run(...)` with NO `check=True` (a nonzero return code is
    returned, not raised) -- `spicelib/simulators/ltspice_simulator.py`'s
    `LTspice` class, and `spicelib/sim/simulator.py`'s `run_function()`
    helper it calls into.
  - "A raw file and a log file will be generated, with the same name as
    the netlist file, but with `.raw` and `.log` extension" -- `LTspice.
    run()`'s own docstring, same file. This module's own raw_file/log_file
    derivation (`netlist_file.with_suffix(...)`) below is taken directly
    from this documented contract, not guessed.
  - The set of switches LTspice's batch mode accepts (`-alt`, `-ascii`,
    `-ini <path>`, `-I<path>`, `-netlist`, `-norm`, `-SOI`, `-sync`, etc.)
    and that `-Run`/`-b` are ALREADY injected by spicelib and must not be
    passed again -- `LTspice.valid_switch()`'s docstring and the
    `ltspice_args` dict, same file.
  - `Simulator.create_from(path_to_exe, process_name=None)` -- the
    documented way to bind a non-default-install-location LTspice
    executable -- sets `cls.spice_exe`/`cls.process_name` as CLASS
    attributes on whatever class `cls` resolves to. Calling this on the
    shared `LTspice` class object itself would mutate that global,
    process-wide state for every other importer; this module always binds
    through a fresh private subclass instead (see `_bind_ltspice_executable`
    below) -- `spicelib/sim/simulator.py`'s `Simulator` base class.
  - `Simulator.is_available()` -- checks `Path(cls.spice_exe[0]).exists()`
    or `shutil.which(cls.spice_exe[0])`, returns bool -- same file, used
    here to raise this module's own `SimulatorError` with a clear message
    BEFORE ever invoking `.run()`, instead of letting spicelib's own
    `SpiceSimulatorError` (a different exception type than this codebase's
    `SimulatorError` contract) surface un-translated.
  - The `.raw` file format and `RawRead` class -- reads either dialect
    automatically, exposes `get_trace_names()`, `get_plot_name()` (e.g.
    "AC Analysis", "Transient Analysis"), `get_axis(step)`, `get_wave(
    trace_ref, step)` (returns a numpy array, real for a TRAN/DC axis or
    trace, complex for an AC analysis trace), and `has_axis` -- `spicelib/
    raw/raw_read.py`'s `RawRead` class and module docstring. This module
    does not re-implement or guess at the binary .raw layout; it reads
    everything through spicelib's own parser.
  - `RawWrite`/`Trace` -- used ONLY in this module's own test suite (see
    tests/test_ltspice.py), to have the fake/stub "LTspice" executable
    write a real, spicelib-produced `.raw` file rather than hand-rolling a
    guessed binary layout -- `spicelib/raw/raw_write.py`.

HONEST CAVEAT: no real LTspice binary is installed in this environment
(this repo's dev/CI sandbox has no Windows-native GUI-app install, and
running it under Wine was not attempted here either) -- mirroring NEC2++/
openEMS/HFSS, none of which are installed here either. Unlike those three
adapters, though, this one's actual subprocess-invocation mechanics
(argument construction, nonzero-exit/timeout handling) are NOT hand-rolled
here -- they are spicelib's own `LTspice.run()`/`Simulator.create_from()`
code, verified against spicelib's real upstream source as cited above and
exercised for real (not mocked away) in tests/test_ltspice.py against a
fake/stub Python script standing in for the LTspice executable. What is
NOT verified end-to-end is spicelib's own behavior against a REAL LTspice
binary's real output -- treat any result as unverified end-to-end until it
has actually been run against the real tool at least once. Log-file text
encoding is also not independently verified (LTspice's `.log` file
encoding was not confirmed against a primary source in this pass, unlike
the `.raw` format which spicelib's own `RawRead` already handles); this
module reads it permissively (UTF-8, `errors="replace"`) rather than
asserting a specific encoding it hasn't verified.
"""

import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import numpy as np

from .base import SimulationResult, Simulator, SimulatorError

_INSTALL_HINT = (
    "spicelib is not installed. Install it with `pip install '.[ltspice]'` "
    "(or `uv sync --extra ltspice`) to use LtspiceSimulator / "
    "run_ltspice_simulation / parse_ltspice_raw. See simulation/ltspice.py's "
    "module docstring and docs/LICENSE_MATRIX.md for why spicelib is an "
    "optional extra, not a hard dependency."
)


def _ltspice_class():
    """Lazily import and return spicelib's real `LTspice` class (see module
    docstring's citation on why every spicelib import in this module is
    lazy, not at module top level)."""
    try:
        from spicelib.simulators.ltspice_simulator import LTspice
    except ImportError as exc:
        raise SimulatorError(_INSTALL_HINT) from exc
    return LTspice


def _raw_read_class():
    """Lazily import and return spicelib's `RawRead` class."""
    try:
        from spicelib.raw.raw_read import RawRead
    except ImportError as exc:
        raise SimulatorError(_INSTALL_HINT) from exc
    return RawRead


def _bind_ltspice_executable(executable: str):
    """Return a LTspice-derived class bound to `executable`, via a FRESH
    private subclass rather than `LTspice.create_from(executable)` called
    directly on spicelib's own shared `LTspice` class object -- see this
    module's docstring citation on `Simulator.create_from()` mutating
    class-level (i.e. process-wide) state on whatever class it's called on.
    """
    ltspice_cls = _ltspice_class()
    bound = type(f"_BoundLTspice_{abs(hash(executable))}", (ltspice_cls,), {})
    bound.create_from(executable)
    return bound


class LtspiceSimulator(Simulator):
    name = "LTspice"

    def __init__(self, executable: str | None = None, simulator_cls: type | None = None):
        """`executable`, if given (else the `LTSPICE_BIN` env var, else
        spicelib's own auto-detected default install location -- see
        `LTspice`'s class-body search logic, cited in this module's
        docstring), binds a private LTspice-derived subclass to that path.

        `simulator_cls`, if given, is used AS-IS instead of resolving
        anything through spicelib at all -- a test-only constructor-
        injection seam (mirrors simulation/hfss.py's `hfss_factory`) so
        tests can supply a class whose `run()`/`is_available()` already
        point at a fake/stub executable, or (as tests/test_ltspice.py
        mostly does instead) a REAL spicelib-derived class pre-bound to
        one -- see that file for why the latter is preferred here, unlike
        that other adapter.
        """
        self.executable = executable or os.getenv("LTSPICE_BIN")
        if simulator_cls is not None:
            self._simulator_cls = simulator_cls
        elif self.executable:
            self._simulator_cls = _bind_ltspice_executable(self.executable)
        else:
            self._simulator_cls = _ltspice_class()

    def run(self, job: dict) -> SimulationResult:
        netlist_file = Path(job["netlist_file"]).resolve()
        workdir = Path(job.get("workdir", netlist_file.parent)).resolve()
        if not netlist_file.exists():
            raise SimulatorError(f"Netlist file not found: {netlist_file}")

        if not self._simulator_cls.is_available():
            raise SimulatorError(
                "No LTspice executable available (spice_exe="
                f"{getattr(self._simulator_cls, 'spice_exe', None)!r}); set "
                "LTSPICE_BIN, pass LtspiceSimulator(executable=...), or "
                "install LTspice at one of spicelib's default search "
                "locations (see this module's docstring)."
            )

        cmd_line_switches = job.get("cmd_line_switches") or []
        timeout_s = int(job.get("timeout_s", 600))
        # LTspice.run() (spicelib) builds the real '-Run -b <netlist>
        # [switches...]' command itself and shells out via subprocess.run()
        # with no check=True -- a nonzero return code comes back as a
        # plain int, it does not raise (see module docstring citation).
        try:
            returncode = self._simulator_cls.run(
                netlist_file,
                cmd_line_switches=cmd_line_switches,
                timeout=timeout_s,
                cwd=workdir,
            )
        except subprocess.TimeoutExpired as exc:
            raise SimulatorError(f"LTspice timed out after {timeout_s}s: {exc}") from exc

        # Same name as the netlist file, '.raw'/'.log' extension -- per
        # LTspice.run()'s own documented contract (module docstring
        # citation), not guessed.
        raw_file = netlist_file.with_suffix(".raw")
        log_file = netlist_file.with_suffix(".log")
        log_text = ""
        if log_file.exists():
            log_text = log_file.read_text(encoding="utf-8", errors="replace")

        if returncode != 0:
            raise SimulatorError(
                f"LTspice failed (exit code {returncode}) on {netlist_file}."
                + (f" Log:\n{log_text[-4000:]}" if log_text else " No log file was produced.")
            )
        if not raw_file.exists():
            raise SimulatorError(
                f"LTspice exited 0 but produced no .raw output at {raw_file}."
                + (f" Log:\n{log_text[-4000:]}" if log_text else " No log file was produced.")
            )

        return SimulationResult(
            simulator=self.name,
            status="COMPLETED",
            workdir=workdir,
            outputs={
                "raw_file": str(raw_file),
                "log_file": str(log_file) if log_file.exists() else None,
                "log_text": log_text,
            },
        )


def _to_jsonable(wave: Any) -> list[Any] | None:
    """Convert a spicelib trace/axis wave (a numpy array, real or complex --
    see module docstring's RawRead citation) into plain JSON-safe Python:
    a list of floats, or a list of [real, imag] pairs for a complex (e.g.
    AC analysis) trace."""
    if wave is None:
        return None
    arr = np.asarray(wave)
    if np.iscomplexobj(arr):
        return [[float(v.real), float(v.imag)] for v in arr]
    return [float(v) for v in arr]


def parse_ltspice_raw(
    raw_file: str | Path, traces_to_read: str | list[str] | None = "*"
) -> dict[str, Any]:
    """Parse an LTspice `.raw` file into structured trace data via
    spicelib's `RawRead` (module docstring citation) -- this function does
    not re-implement or guess at the binary .raw format itself.

    Returns a dict with `plot_name` (e.g. "AC Analysis", "Transient
    Analysis" -- spicelib's own `Plotname` header field), `trace_names`
    (every variable in the file, axis included), `has_axis`, `axis` (the
    step-0 X axis wave, JSON-safe, or None if `has_axis` is False -- true
    for Operating Point/Transfer Function/Integrated Noise plots), `traces`
    (dict of every trace name -> its step-0 wave, JSON-safe), and
    `n_points`.
    """
    raw_read_cls = _raw_read_class()
    reader = raw_read_cls(str(raw_file), traces_to_read=traces_to_read)

    trace_names = reader.get_trace_names()
    axis = reader.get_axis(0) if reader.has_axis else None

    return {
        "plot_name": reader.get_plot_name(),
        "trace_names": trace_names,
        "has_axis": reader.has_axis,
        "axis": _to_jsonable(axis),
        "traces": {name: _to_jsonable(reader.get_wave(name, 0)) for name in trace_names},
        "n_points": reader.nPoints,
    }


def run_ltspice_simulation(
    netlist: str | None = None,
    netlist_file: str | None = None,
    cmd_line_switches: list[str] | None = None,
    timeout_s: int = 600,
    executable: str | None = None,
    workdir: str | None = None,
    traces_to_read: str | list[str] | None = "*",
) -> dict[str, Any]:
    """Run an LTspice circuit simulation and parse its `.raw` output.

    Takes EITHER `netlist` (a raw SPICE netlist as text -- e.g. exported
    from LTspice's own schematic via File > Export Netlist, or hand-
    written/generated elsewhere) or `netlist_file` (a path to an existing
    `.net`/`.cir` netlist, or a `.asc` schematic, already on disk) --
    exactly one is required. Unlike simulation/nec2pp.py's `generate_nec2_
    deck` or simulation/openems.py's `generate_openems_xml`, this module
    does NOT generate a netlist from a structured component-description
    dict: a SPICE netlist is already the natural structured/text format for
    a circuit (this is not a card-deck or XML format that needed inventing
    a generator for), so a caller with a validated LTspice design already
    has one to hand directly.

    Runs it via `LtspiceSimulator` (real batch-mode LTspice invocation
    through spicelib -- see module docstring), then parses the resulting
    `.raw` file via `parse_ltspice_raw`. Returns "SIMULATED" provenance.

    Format/invocation verified against spicelib's own primary source (see
    module docstring for the full citation) but NOT against a real LTspice
    binary -- none is installed in this environment; treat any result as
    unverified end-to-end until it has been run against the real tool at
    least once.
    """
    if not netlist and not netlist_file:
        raise ValueError(
            "run_ltspice_simulation requires either `netlist` (raw SPICE "
            "netlist text) or `netlist_file` (path to an existing .net/"
            ".cir/.asc file on disk)."
        )

    work_dir = Path(workdir) if workdir else Path(tempfile.mkdtemp(prefix="ltspice_"))
    work_dir.mkdir(parents=True, exist_ok=True)

    if netlist_file:
        input_file = Path(netlist_file).resolve()
    else:
        input_file = work_dir / "model.net"
        input_file.write_text(netlist)

    simulator = LtspiceSimulator(executable=executable)
    result = simulator.run(
        {
            "netlist_file": str(input_file),
            "workdir": str(work_dir),
            "timeout_s": timeout_s,
            "cmd_line_switches": cmd_line_switches or [],
        }
    )

    parsed = parse_ltspice_raw(result.outputs["raw_file"], traces_to_read=traces_to_read)

    return {
        "provenance": "SIMULATED",
        "plot_name": parsed["plot_name"],
        "trace_names": parsed["trace_names"],
        "has_axis": parsed["has_axis"],
        "axis": parsed["axis"],
        "traces": parsed["traces"],
        "n_points": parsed["n_points"],
        "simulator": result.simulator,
        "status": result.status,
        "workdir": str(result.workdir),
        "netlist_file": str(input_file),
        "raw_file": result.outputs["raw_file"],
        "log_file": result.outputs.get("log_file"),
    }
