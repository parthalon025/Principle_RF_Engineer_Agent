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

`.NET` TWO-PORT S/Y/Z/H-PARAMETER EXTRACTION (issue #287) -- SOURCES
CONSULTED (primary, fetched directly this session, 2026-09-09):
  - `.net [V(out[,ref])|I(Rout)] <Vin|Iin> [Rin=<val>] [Rout=<val>]` --
    the exact, complete syntax line for LTspice's `.NET` statement, fetched
    directly from https://ltwiki.org/LTspiceHelp/LTspiceHelp/_NET_Compute_
    Network_Parameters_in_a_AC_Analysis.htm. LTwiki hosts a direct HTML
    rendering of ADI's own bundled LTspiceHelp.chm content (ADI does not
    itself publish a separately browsable HTML copy of that help file) --
    this repo's own docs/tools/ltspice.md already treats an ltwiki.org URL
    as a "fetched directly" primary source for this exact reason (its
    License Agreement citation, source [8]), so this module does the same
    for `.NET`. This SUPERSEDES docs/tools/ltspice.md's PRIOR citation for
    `.net` (that doc's source [5], explicitly flagged there as "not fetched
    directly from ADI's own help pages" -- a search-engine summary of
    third-party tutorials/forum material) -- see this ticket's acceptance
    criteria on exactly this point.
  - Per that same fetched page: `.net` computes "input and output
    admittance, impedance, Y-parameters, Z-parameters, H-parameters, and
    S-parameters" of a 2-port network (or input admittance/impedance for a
    1-port network) TOGETHER, in one run -- there is NO LINTYPE=-style
    selector switch choosing S vs Y vs Z vs H the way Xyce's `.LIN`
    (LINTYPE=<S|Y|Z>, simulation/xyce.py) has one. The acceptance criteria
    asked this be verified rather than assumed; the primary source shows
    the assumption of a selector switch was wrong, not that verification
    was skipped -- generate_ltspice_net_netlist() below has no `lintype`-
    equivalent parameter for exactly this reason.
  - The network's input is named by referencing an already-declared
    independent voltage or current source (`<Vin|Iin>`); the output is
    named by referencing either a node (`V(out[,ref])`) or a resistor's
    current (`I(Rout)`) -- NOT a dedicated `Pname n1 n2 port=N` device card
    the way Xyce's Port Device works (Xyce Reference Guide section 2.3.11,
    cited in simulation/xyce.py). generate_ltspice_net_netlist()'s `ports`
    job-dict key below mirrors Xyce's `ports` key in NAME and in job-dict
    POSITION only; its per-entry SHAPE necessarily differs to match this
    real, documented `.net` addressing scheme instead of inventing a
    Port-device card LTspice's `.net` statement does not have.
  - `.ac <oct, dec, lin> <Nsteps> <StartFreq> <EndFreq>` -- the exact `.ac`
    syntax line, fetched directly from https://ltwiki.org/
    LTspiceHelpXVII/LTspiceHelp/html/AC_Analysis.htm (same LTwiki-mirrors-
    ADI's-own-help-content citation as above). `.net`'s own page states
    "This must be used with a .AC statement", confirming
    generate_ltspice_net_netlist() below requires analysis['type'] == 'ac'
    (no op/tran path exists for `.net`, unlike Xyce's `.LIN`, which at
    least shares its `.AC`-only requirement).
  - The worked example on the same `.net` help page (LTspice's own bundled
    `Educational/S-param` example): a voltage source with Rser as the
    driven port and a plain resistor as the output termination, with
    `.net I(Rout) V4` as the statement -- this module's own
    TWO_PORT_NET_JOB-shaped tests mirror that same V-source-plus-resistive-
    pad topology (see tests/test_ltspice.py).

  HONEST CONFIDENCE CAVEAT ON EXACT OUTPUT TRACE NAMES (distinct from the
  syntax/computed-parameters citations above, which ARE primary-sourced):
  the fetched ADI help-page text states WHAT `.net` computes but does not
  itself spell out the literal trace-name strings (e.g. "S11" vs "S(1,1)")
  that land in the resulting `.raw` file/waveform-viewer plot. Those exact
  names (S11/S12/S21/S22, and Zin/Zout/Yin/Yout) are corroborated by
  multiple independent LTspice-user community threads (including ADI's own
  EngineerZone forum) describing exactly these names appearing in the
  waveform viewer's "Add Traces" dialog after a `.net` run -- consistent
  with each other, but NOT independently confirmed against a real LTspice
  binary's actual `.raw` output in this pass (no real LTspice binary is
  installed in this environment -- see this module's HONEST CAVEAT above).
  extract_ltspice_network_parameters() below matches trace names
  case-insensitively against a fixed token list for exactly this reason --
  see that function's own docstring.
"""

import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import numpy as np

from .base import SimulationResult, Simulator, SimulatorError
from .spice_netlist import format_components, format_number

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


# ---------------------------------------------------------------------------
# `.net` two-port S/Y/Z/H-parameter extraction (issue #287) -- see module
# docstring's "`.NET` TWO-PORT S/Y/Z/H-PARAMETER EXTRACTION" section for the
# full primary-source citations this generator is built to.
# ---------------------------------------------------------------------------


def _net_ac_line(analysis: dict[str, Any]) -> str:
    """`.ac <oct, dec, lin> <Nsteps> <StartFreq> <EndFreq>` -- module
    docstring citation. `.net` requires this exact analysis type (its own
    help page: "This must be used with a .AC statement"); op/tran are not
    valid for a `.net` job, unlike Xyce's `.LIN` (which shares only the
    `.AC`-only restriction, not the general analysis-type menu -- see
    simulation/xyce.py's `_analysis_run_lines`, which this function
    deliberately does not import or reuse: that function's op/tran branches
    do not apply here, and duplicating just its 4-line `.ac` branch here
    was judged cheaper and less risky than extracting a 3rd, LTspice-
    specific-cased copy of it into simulation/spice_netlist.py -- ngspice.py
    and xyce.py each already carry their own independently-sourced copy of
    this same well-established SPICE3F5-lineage line; see that module's
    docstring for why only R/L/C/V/I card generation was judged worth
    sharing there.
    """
    required = ("sweep_type", "points", "start_freq_hz", "stop_freq_hz")
    missing = [f for f in required if f not in analysis]
    if missing:
        raise ValueError(f"analysis (type='ac') missing required field(s): {missing}")
    sweep_type = analysis["sweep_type"]
    if sweep_type not in ("lin", "oct", "dec"):
        raise ValueError(
            f"analysis['sweep_type'] must be 'lin', 'oct', or 'dec', got {sweep_type!r}"
        )
    return (
        f".ac {sweep_type} {int(analysis['points'])} "
        f"{format_number(analysis['start_freq_hz'])} {format_number(analysis['stop_freq_hz'])}"
    )


def _net_split_ports(ports: list[dict[str, Any]]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Validate and split `job['ports']` into (input_port, output_port).

    Unlike Xyce's `ports` (an N-entry list of numbered Port-device cards,
    simulation/xyce.py's `_port_card`), LTspice's `.net` statement always
    describes EXACTLY one input and one output (module docstring citation:
    the statement references one already-declared source as input and one
    node-or-resistor as output, it is not itself a repeatable device card)
    -- so this always requires exactly 2 entries, one of each role.
    """
    if len(ports) != 2:
        raise ValueError(
            "job['ports'] must have exactly 2 entries (one 'input', one 'output') "
            f"for LTspice's .net two-port statement, got {len(ports)}"
        )
    by_role: dict[str, dict[str, Any]] = {}
    for port in ports:
        role = port.get("role")
        if role not in ("input", "output"):
            raise ValueError(f"port['role'] must be 'input' or 'output', got {role!r}")
        if role in by_role:
            raise ValueError(
                f"job['ports'] must have exactly one 'input' and one 'output' entry, "
                f"got two {role!r} entries"
            )
        by_role[role] = port
    return by_role["input"], by_role["output"]


def _net_input_operand(input_port: dict[str, Any]) -> str:
    """`<Vin|Iin>` -- the driven port, named by referencing an already-
    declared independent voltage or current source (module docstring
    citation)."""
    if "name" not in input_port:
        raise ValueError("port (role='input') missing required field: 'name'")
    name = str(input_port["name"])
    if not name.upper().startswith(("V", "I")):
        raise ValueError(
            "port (role='input') 'name' must reference an independent voltage or "
            f"current source already in job['components'] (start with 'V' or 'I' -- "
            f"LTspice's .net <Vin|Iin> operand), got {name!r}"
        )
    return name


def _net_output_operand(output_port: dict[str, Any]) -> str:
    """`V(out[,ref])|I(Rout)` -- the loaded port, named by referencing a
    node voltage or a resistor's current (module docstring citation)."""
    kind = output_port.get("kind")
    if kind == "V":
        if "node" not in output_port:
            raise ValueError("port (role='output', kind='V') missing required field: 'node'")
        node = str(output_port["node"])
        if "ref" in output_port:
            return f"V({node},{output_port['ref']})"
        return f"V({node})"
    if kind == "I":
        if "name" not in output_port:
            raise ValueError("port (role='output', kind='I') missing required field: 'name'")
        name = str(output_port["name"])
        if not name.upper().startswith("R"):
            raise ValueError(
                "port (role='output', kind='I') 'name' must reference a resistor "
                f"already in job['components'] (start with 'R' -- LTspice's .net "
                f"I(Rout) operand), got {name!r}"
            )
        return f"I({name})"
    raise ValueError(f"port (role='output') 'kind' must be 'V' or 'I', got {kind!r}")


def _net_statement_line(job: dict[str, Any]) -> str:
    """`.net [V(out[,ref])|I(Rout)] <Vin|Iin> [Rin=<val>] [Rout=<val>]` --
    module docstring citation (exact syntax, fetched directly from ADI's
    own `.NET` help-page content mirrored at ltwiki.org)."""
    ports = job.get("ports") or []
    input_port, output_port = _net_split_ports(ports)
    fields = [".net", _net_output_operand(output_port), _net_input_operand(input_port)]
    if "rin" in job:
        fields.append(f"Rin={format_number(job['rin'])}")
    if "rout" in job:
        fields.append(f"Rout={format_number(job['rout'])}")
    return " ".join(fields)


def generate_ltspice_net_netlist(
    job: dict[str, Any],
    comment: str = "Generated by run_ltspice_simulation (.net)",
) -> str:
    """Generate a `.net`-based two-port netlist from a structured job dict
    (issue #287) -- LTspice's own native S-/Y-/Z-/H-parameter extraction,
    mirroring generate_xyce_netlist()'s `components`/`ports`/`analysis`
    job-dict shape as closely as LTspice's real, documented `.net` syntax
    allows (see module docstring for the full primary-source citations and
    exactly where this necessarily diverges from Xyce's shape -- LTspice's
    `.net` addresses its two ports by referencing existing sources/nodes,
    not via a repeatable Port-device card).

    `job` shape:
        {
          "components": [...],   # R/L/C/V/I -- see simulation/spice_netlist.py.
                                  # MUST include the source/resistor the
                                  # `ports` entries below reference by name.
          "ports": [              # required -- exactly one of each role
              {"role": "input", "name": "V1"},   # <Vin|Iin> operand:
                                                  # references a V/I source
                                                  # already in `components`
              {"role": "output", "kind": "V", "node": "out",   # V(out[,ref])
               "ref": "gnd"},                                  # ref optional
              # OR: {"role": "output", "kind": "I", "name": "Rout"},  # I(Rout):
              #     references an R component already in `components`
          ],
          "rin": float,    # optional -- Rin=<val> override on the .net line
          "rout": float,   # optional -- Rout=<val> override on the .net line
          "raw_cards": [str, ...],   # optional escape hatch -- see
                                      # simulation/spice_netlist.py's SCOPE note.
          "analysis": {
              "type": "ac",   # REQUIRED to be "ac" -- .net's own help page:
                               # "This must be used with a .AC statement"
              "sweep_type": "lin"|"oct"|"dec", "points": int,
              "start_freq_hz": float, "stop_freq_hz": float,
          },
        }

    Unlike Xyce's `.LIN` (LINTYPE=<S|Y|Z>, simulation/xyce.py), `.net` has
    no parameter-type selector: per the primary source cited in this
    module's docstring, it computes admittance/impedance/Y/Z/H/S-parameters
    together in one run, so there is no `lintype`-equivalent job-dict field
    here -- see extract_ltspice_network_parameters() for pulling the
    resulting traces back out of the parsed `.raw` file.
    """
    components = job.get("components", [])
    raw_cards = job.get("raw_cards", [])
    analysis = job.get("analysis")
    if not analysis:
        raise ValueError("job['analysis'] must be a dict with a 'type' key")
    if analysis.get("type") != "ac":
        raise ValueError(
            "job['analysis']['type'] must be 'ac' -- LTspice's .net statement "
            "requires a .AC analysis to sweep (module docstring citation: "
            "ADI's own .NET help page states 'This must be used with a .AC "
            f"statement'), got {analysis.get('type')!r}"
        )
    if not job.get("ports"):
        raise ValueError(
            "job['ports'] (the input/output two-port definition) is required "
            "for generate_ltspice_net_netlist()"
        )

    net_line = _net_statement_line(job)

    lines: list[str] = [f"* {comment}"]
    lines.extend(format_components(components))
    lines.extend(str(card) for card in raw_cards)
    lines.append(_net_ac_line(analysis))
    lines.append(net_line)
    lines.append(".end")
    return "\n".join(lines) + "\n"


_NETWORK_PARAMETER_TOKENS = (
    "S11",
    "S12",
    "S21",
    "S22",
    "Y11",
    "Y12",
    "Y21",
    "Y22",
    "Z11",
    "Z12",
    "Z21",
    "Z22",
    "H11",
    "H12",
    "H21",
    "H22",
    "Zin",
    "Zout",
    "Yin",
    "Yout",
)


def extract_ltspice_network_parameters(parsed: dict[str, Any]) -> dict[str, Any]:
    """Pull LTspice `.net`'s two-port network-parameter traces out of an
    ALREADY-PARSED `parse_ltspice_raw()` result -- a pure, I/O-free
    function operating on already-fetched data (this codebase's "caller
    fetches, pure function resolves" split; parse_ltspice_raw() does the
    actual file I/O, this function only inspects its `trace_names`/`traces`
    dicts).

    HONEST CAVEAT ON EXACT TRACE NAMES: see this module's docstring
    "`.NET` TWO-PORT S/Y/Z/H-PARAMETER EXTRACTION" section -- ADI's own
    fetched `.NET` help-page text confirms WHAT is computed (admittance/
    impedance/Y/Z/H/S-parameters, together, no selector) but does not
    itself spell out the literal trace-name strings; the token list below
    is corroborated by multiple independent LTspice-user community threads,
    not confirmed against a real LTspice binary in this pass. Matching is
    done case-insensitively against whatever `parse_ltspice_raw()` reports
    (preserving that result's own casing in the returned dict's keys) so a
    real run's exact casing, if it differs, is still picked up rather than
    silently missed.

    Returns `{"computed": True, "parameters": {trace_name: values, ...}}`
    for whichever tokens were found, or `{"computed": False, "note": ...}`
    if none were -- never fabricates a parameter that was not actually
    found in the file (this codebase's "warn, never silently apply the
    wrong tool" convention, e.g. simulation/xyce.py's
    `s_parameters["computed"] = False` path for a missing Touchstone file).
    """
    trace_names = parsed.get("trace_names") or []
    traces = parsed.get("traces") or {}
    by_upper = {name.upper(): name for name in trace_names}

    found: dict[str, Any] = {}
    for token in _NETWORK_PARAMETER_TOKENS:
        actual_name = by_upper.get(token.upper())
        if actual_name is not None:
            found[actual_name] = traces.get(actual_name)

    if not found:
        return {
            "computed": False,
            "note": (
                "No S/Y/Z/H-parameter or Zin/Zout/Yin/Yout trace names were found "
                "in the LTspice .raw output -- either the .net statement did not "
                "run (check the log), LTspice named the traces differently than "
                "this function expects (see its docstring HONEST CAVEAT), or "
                "run_ltspice_simulation()'s traces_to_read was narrowed to exclude "
                "them (its default '*' reads every trace; check what was passed)."
            ),
        }
    return {"computed": True, "parameters": found}


def run_ltspice_simulation(
    netlist: str | None = None,
    netlist_file: str | None = None,
    job: dict[str, Any] | None = None,
    cmd_line_switches: list[str] | None = None,
    timeout_s: int = 600,
    executable: str | None = None,
    workdir: str | None = None,
    traces_to_read: str | list[str] | None = "*",
) -> dict[str, Any]:
    """Run an LTspice circuit simulation and parse its `.raw` output.

    Takes EXACTLY ONE of:
      - `netlist` (a raw SPICE netlist as text -- e.g. exported from
        LTspice's own schematic via File > Export Netlist, or hand-
        written/generated elsewhere);
      - `netlist_file` (a path to an existing `.net`/`.cir` netlist, or a
        `.asc` schematic, already on disk);
      - `job` (a structured two-port job dict -- see
        generate_ltspice_net_netlist() for its shape -- templated into a
        `.net` netlist by this function, issue #287).
    Unlike simulation/nec2pp.py's `generate_nec2_deck` or simulation/
    openems.py's `generate_openems_xml`, this module does NOT generate a
    netlist from an arbitrary structured component-description dict for
    every analysis type: a SPICE netlist is already the natural structured/
    text format for a circuit (this is not a card-deck or XML format that
    needed inventing a generator for), so a caller with a validated LTspice
    design already has one to hand directly for the general case. `job` is
    the one carved-out exception -- LTspice's native `.net` two-port
    S/Y/Z/H-parameter extraction (module docstring citation), which is
    template-worthy for the same reason Xyce's `.LIN` is
    (simulation/xyce.py's `generate_xyce_netlist`): callers ask for it
    often enough, and its syntax is fiddly enough, that hand-writing it
    every time is the wrong default.

    Runs it via `LtspiceSimulator` (real batch-mode LTspice invocation
    through spicelib -- see module docstring), then parses the resulting
    `.raw` file via `parse_ltspice_raw`. When `job` was given, also runs
    `extract_ltspice_network_parameters()` over the parsed result and adds
    it under `network_parameters` -- omitted entirely for the `netlist`/
    `netlist_file` paths (mirrors simulation/xyce.py's own `s_parameters`
    key, present only when `job['ports']` was given). Returns "SIMULATED"
    provenance.

    Format/invocation verified against spicelib's own primary source (see
    module docstring for the full citation) but NOT against a real LTspice
    binary -- none is installed in this environment; treat any result as
    unverified end-to-end until it has been run against the real tool at
    least once.
    """
    candidates = (("netlist", netlist), ("netlist_file", netlist_file), ("job", job))
    given = [name for name, value in candidates if value]
    if len(given) != 1:
        raise ValueError(
            "run_ltspice_simulation requires exactly one of `netlist` (raw "
            "SPICE netlist text), `netlist_file` (path to an existing .net/"
            ".cir/.asc file on disk), or `job` (structured two-port job dict "
            f"for .net generation -- see generate_ltspice_net_netlist()), got: {given or 'none'}"
        )

    work_dir = Path(workdir) if workdir else Path(tempfile.mkdtemp(prefix="ltspice_"))
    work_dir.mkdir(parents=True, exist_ok=True)

    if netlist_file:
        input_file = Path(netlist_file).resolve()
    else:
        input_file = work_dir / "model.net"
        input_file.write_text(generate_ltspice_net_netlist(job) if job else netlist)

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

    output: dict[str, Any] = {
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
    if job:
        output["network_parameters"] = extract_ltspice_network_parameters(parsed)
    return output
