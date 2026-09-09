"""Xyce circuit-level simulation (issue #57, part 2 of 2 -- see also
simulation/ngspice.py): a larger/parallel-circuit-capable nonlinear circuit
simulator for a matching network, amplifier bias network, or filter
sub-circuit, without needing a paid tool (Keysight ADS). Xyce (Sandia
National Laboratories) is free/open (GPLv3, see docs/LICENSE_MATRIX.md).

SOURCES CONSULTED (primary; the official Xyce Reference Guide, Sandia
report SAND2023-13759, version 7.8, fetched directly from
https://xyce.sandia.gov/files/xyce/Xyce_Reference_Guide_7.8.pdf and read
via `pdftotext -layout` during implementation -- page/section numbers
below are that PDF's own):
  - Command-line invocation ("Xyce [arguments] <netlist filename>", no
    flags required -- this module passes none, see SCOPE below for why):
    Chapter 3, "Command Line Arguments", Table 3-1 (p.769-770). Per that
    table's "-l" row, log output is sent to standard out by default (no
    "-l" needed) -- confirmed there, not assumed.
  - `.AC <sweep type> <points value> <start> <stop>` general form
    (LIN/OCT/DEC): section 2.1.1 (p.22-23).
  - `.TRAN <initial step> <final time> [<start time> [<step ceiling>]]`
    general form: section 2.1.38 (p.159).
  - `.OP` (bare, no arguments; bias-point data goes to the log file, NOT a
    `.PRINT`-able output -- see SCOPE below): section 2.1.24 (p.92-93).
  - `.HB <fundamental frequencies>` general form (issue #282) -- Harmonic
    Balance, Xyce's method for the periodic steady state of a nonlinear
    circuit (a driven mixer, or an amplifier/nonlinear periodic unit cell
    at its real large-signal operating power) rather than the small-signal
    linearization `.AC` computes around one fixed bias point: section
    2.1.13 (p.45). One or more space-separated fundamental frequencies in
    Hz -- one value is single-tone HB, several select multi-tone HB (e.g.
    an LO tone and an RF tone driving a mixer); the Reference Guide's own
    examples are bare `.HB 1e4` / `.hb 1e4 2e2`, no other argument is
    required on the `.HB` line itself (`.OPTIONS HBINT` tunes HB's internal
    solver but is optional and out of this module's SCOPE, same as every
    other `.OPTIONS` line -- supply it via `raw_cards` if needed).
  - `.PRINT <type> [FILE=<file>] [FORMAT=<STD|NOINDEX|...|CSV|...>]
    <output variable>*` general form, and the CSV format's own
    description ("a comma-separated value file with a header indicating
    the variables printed"): section 2.1.31 (p.126-128), and the
    AC-specific "Print AC Analysis" trigger/file/column table naming
    "FREQ" as the CSV format's leading (scale) column: section 2.1.31.1
    (p.133). The VR()/VI()/VM()/VP()/VDB() (and IR()/II()/IM()/IP()/IDB())
    explicit real/imag/mag/phase/dB output-variable forms for AC/HB/Noise
    analyses, plus the SR()/SI() S-parameter-column forms available after
    a `.LIN` run: same section, p.129 and p.130 (a bare `V(node)` under AC
    auto-splits into real+imag per that same page -- this module does not
    assume a specific auto-split column-header naming convention for that
    case; see parse_xyce_csv()'s docstring). A `.PRINT HB` line uses this
    same general form, per the "Print Harmonic Balance Analysis" section:
    section 2.1.31.3 (p.135-136) -- see the HONEST SCOPE NOTE ON `.PRINT
    HB`'s TWO OUTPUT FILES below for what that section says beyond the
    plain `.AC`/`.TRAN` one-file model this adapter already handles.
  - `.LIN [SPARCALC=<1|0>] [FORMAT=<TOUCHSTONE|TOUCHSTONE2>]
    [LINTYPE=<S|Y|Z>] [DATAFORMAT=<RI|MA|DB>] [FILE=<file>]` general form
    -- a native linear-network S-/Y-/Z-parameter extraction analysis
    (unlike ngspice, which has no such built-in analysis in its stable
    release -- see simulation/ngspice.py's module docstring), driven by
    the frequencies on a `.AC` line when SPARCALC=1 (the default):
    section 2.1.17 (p.49-51). Default Touchstone filename is
    "<netlistName>.sNp" (N = port count) when FILE= is omitted; passing
    the command-line "-o" flag together with `.LIN` makes Xyce ignore any
    FILE= and always emit Touchstone 2 -- this module never passes "-o"
    for exactly this reason (see SCOPE below).
  - `P<name> <(+) node> <(-) node> [[DC] <value>] port=<port number>
    [Z0=<value>] [AC [<magnitude> [<phase>]]] [<transient spec>]` Port
    Device instance form -- "identifies the ports used in .LIN analysis
    ... Numbered sequentially beginning with 1 ... default [Z0] is 50
    ohms": section 2.3.11 (p.230).
  - R/L/C/V/I element instance-card forms: see
    simulation/spice_netlist.py's module docstring (shared with
    simulation/ngspice.py).
  - Xyce's own license: the GPLv3 full text at
    https://raw.githubusercontent.com/Xyce/Xyce/master/COPYING (the
    official Xyce/Xyce GitHub repository), fetched and read directly --
    "GNU GENERAL PUBLIC LICENSE Version 3, 29 June 2007".

HONEST CONFIDENCE CAVEAT ON `.LIN` SPECIFICALLY (beyond the standard
no-real-binary caveat below): a secondary source (a ra3xdh/qucs_s GitHub
discussion, not a Xyce project source) reports that Qucs-S's own "SP
simulation" GUI block maps onto a *different* Xyce feature -- the YLIN
"Linear Device" (Reference Guide section 2.3.24, an N-port behavioral
model that reads pre-existing S/Y/Z-parameter data, e.g. from a
Touchstone file, into a circuit as a component) -- and that YLIN
"gives zero output" outside of Harmonic Balance analysis. That is a
different, unrelated Xyce feature from the `.LIN` *analysis* (section
2.1.17) plus Port *device* (section 2.3.11) this module actually
generates -- YLIN imports S-parameter data as a component; `.LIN`
extracts S-parameter data by simulating a netlist. The Reference Guide's
own `.LIN`/Port-device text above is unambiguous and internally
consistent (SPARCALC ties explicitly to the `.AC` line, not to `.HB`), so
this module is built to it. But since that Reference Guide text was not
independently cross-checked against a second primary Xyce source (e.g. a
worked example in the Xyce Users' Guide or the public Xyce_Regression
netlist suite) in this pass, and since no real Xyce binary was available
to run end-to-end (see below), treat the `.LIN`/Port-device path
specifically as carrying one extra notch of uncertainty beyond this
module's other, more routine (.AC/.TRAN/.PRINT) coverage.

HONEST SCOPE NOTE ON `.PRINT HB`'s TWO OUTPUT FILES (added for issue #282,
alongside the `.LIN` confidence caveat above): section 2.1.31.3 documents
that a single `.PRINT HB` statement generates TWO output files -- one
frequency-domain, one time-domain (`<netlist-name>.HB.FD.csv` and
`<netlist-name>.HB.TD.csv` under FORMAT=CSV) -- not the ONE file `.PRINT
AC`/`.PRINT TRAN` write via this module's own `FILE=` argument. This
module's generic `.PRINT {type} FORMAT=CSV FILE=<file>` line-generation and
run_xyce_simulation()'s single-`print_file`-readback (both left unchanged by
issue #282, which only wires up the `.HB` analysis line and job-dict
contract) assume the `.AC`/`.TRAN` one-file model; whether a real Xyce run
honors `FILE=` for the frequency-domain file specifically, ignores it and
uses the two `<netlist-name>.HB.*` names regardless, or something else, was
NOT independently verified against a second primary source (see the
Reference Guide's own pointer, in its `.PRINT` FILE= description, to "the
Xyce Users' Guide['s] 'Results Output and Evaluation Options' section...for
analysis types (e.g., AC and HB) that can produce multiple output files" --
that Users' Guide section was not fetched in this pass). Request explicit
frequency-domain output variables (VDB()/VP()/etc., matching this module's
existing `.AC` convention) and confirm the actual output filename against a
real Xyce run before relying on `.PRINT HB` for anything beyond this
ticket's netlist-generation/job-dict-plumbing scope.

SCOPE OF THIS IMPLEMENTATION:
  - Analyses: `.OP`, `.AC`, `.TRAN`, `.HB` (issue #282 added `.HB` --
    simulation/ngspice.py has no periodic large-signal HB-equivalent
    analysis wired up, so this is Xyce-only, same as `.LIN` below).
    `.OP`-only jobs get back the raw log text only (Xyce's own
    "Additional Output Available" table lists `.OP` data as going to the
    log file, not any `.PRINT`-able output -- section 2.1.31.1/2.1.31.2,
    p.133/134) -- no `.PRINT`/CSV parsing is attempted for that case.
  - Components: structured R/L/C/V/I via simulation/spice_netlist.py, plus
    a `raw_cards` escape hatch -- same SCOPE note as simulation/ngspice.py
    (no semiconductor-device/`.MODEL` generation here).
  - S-/Y-/Z-parameters ARE computed, via `.LIN` + Port devices, when the
    job dict's `ports` key is given (requires `analysis.type == "ac"`) --
    written to a real Touchstone file this module reads back with skrf
    (rf_tools/touchstone.py's own `skrf.Network(path)` pattern), surfaced
    as `touchstone_file`, matching how simulation/openems.py's own
    computed=True S-parameter path integrates with
    rf_tools/correlation.py. This is a genuine capability gap over
    simulation/ngspice.py (see that module's own honest S-parameter scope
    gap) -- Xyce is the S-parameter-capable member of this pair, subject
    to the confidence caveat immediately above.
  - This module never passes the `-o`/`-r`/`-a`/`-l` command-line flags:
    every output file this module reads is instead named explicitly via
    each dot-command's own `FILE=` argument (`.PRINT`/`.LIN`), and log
    diagnostics are read from captured subprocess stdout/stderr (Xyce's
    own documented default target for log output -- see the Table 3-1
    citation above) rather than a `-l` file. This sidesteps the
    documented `-o`-overrides-`.LIN`-`FILE=` interaction entirely instead
    of having to reason about it at every call site.

HONEST CAVEAT: the real `Xyce` binary is NOT installed in this environment
(confirmed via `which Xyce` and `which xyce`, both exit 1) and was not
available to run against these generated netlists. Netlist generation and
CSV/Touchstone output parsing are built to the documented format cited
above; tests exercise them only against a fake "Xyce" script (see
tests/test_xyce.py), not a real Xyce run. Treat any result -- and
especially the `.LIN` S-parameter path, per the confidence caveat above --
as unverified end-to-end until it has been run against the real binary at
least once.
"""

from __future__ import annotations

import csv
import io
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from .base import SimulationResult, Simulator, SimulatorError
from .spice_netlist import format_components, format_number

_ANALYSIS_TYPES = ("op", "ac", "tran", "hb")


class XyceSimulator(Simulator):
    name = "Xyce"

    def __init__(self, executable: str | None = None):
        self.executable = executable or os.getenv("XYCE_BIN") or "Xyce"

    def run(self, job: dict) -> SimulationResult:
        netlist_file = Path(job["netlist_file"]).resolve()
        workdir = Path(job.get("workdir", netlist_file.parent)).resolve()
        if not netlist_file.exists():
            raise SimulatorError(f"Input netlist not found: {netlist_file}")

        # "Xyce <netlist filename>", no flags -- every output file this
        # adapter reads is named via each dot-command's own FILE= argument
        # instead (see this module's docstring SCOPE note on why "-o" is
        # deliberately never passed), and log output defaults to stdout
        # (Table 3-1, cited in this module's docstring), captured below.
        timeout_s = int(job.get("timeout_s", 600))
        try:
            completed = subprocess.run(
                [self.executable, str(netlist_file)],
                cwd=workdir,
                capture_output=True,
                text=True,
                timeout=timeout_s,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise SimulatorError(f"Xyce timed out after {timeout_s}s: {exc}") from exc
        if completed.returncode != 0:
            diagnostic = completed.stderr or completed.stdout
            raise SimulatorError(f"Xyce failed ({completed.returncode}): {diagnostic[-4000:]}")

        return SimulationResult(
            simulator=self.name,
            status="COMPLETED",
            workdir=workdir,
            outputs={"stdout": completed.stdout[-8000:]},
        )


def _analysis_run_lines(analysis: dict[str, Any]) -> list[str]:
    analysis_type = analysis.get("type")
    if analysis_type not in _ANALYSIS_TYPES:
        raise ValueError(
            f"analysis['type'] must be one of {_ANALYSIS_TYPES}, got {analysis_type!r}"
        )

    if analysis_type == "op":
        return [".OP"]
    if analysis_type == "ac":
        required = ("sweep_type", "points", "start_freq_hz", "stop_freq_hz")
        missing = [f for f in required if f not in analysis]
        if missing:
            raise ValueError(f"analysis (type='ac') missing required field(s): {missing}")
        sweep_type = analysis["sweep_type"]
        if sweep_type not in ("lin", "oct", "dec"):
            raise ValueError(
                f"analysis['sweep_type'] must be 'lin', 'oct', or 'dec', got {sweep_type!r}"
            )
        return [
            f".AC {sweep_type.upper()} {int(analysis['points'])} "
            f"{format_number(analysis['start_freq_hz'])} {format_number(analysis['stop_freq_hz'])}"
        ]
    if analysis_type == "hb":
        required = ("fundamental_freqs_hz",)
        missing = [f for f in required if f not in analysis]
        if missing:
            raise ValueError(f"analysis (type='hb') missing required field(s): {missing}")
        freqs = analysis["fundamental_freqs_hz"]
        if not freqs:
            raise ValueError(
                "analysis['fundamental_freqs_hz'] must be a non-empty list of one or "
                "more fundamental frequency values (Hz) -- Xyce's `.HB <fundamental "
                "frequencies>` general form (Reference Guide section 2.1.13, p.45) "
                "takes one value for single-tone HB or several for multi-tone HB"
            )
        return [".HB " + " ".join(format_number(freq) for freq in freqs)]
    # tran
    required = ("step_s", "stop_s")
    missing = [f for f in required if f not in analysis]
    if missing:
        raise ValueError(f"analysis (type='tran') missing required field(s): {missing}")
    fields = [format_number(analysis["step_s"]), format_number(analysis["stop_s"])]
    if "start_s" in analysis:
        fields.append(format_number(analysis["start_s"]))
        if "max_step_s" in analysis:
            fields.append(format_number(analysis["max_step_s"]))
    return [".TRAN " + " ".join(fields)]


def _port_card(port: dict[str, Any]) -> str:
    required = ("name", "n1", "n2", "port")
    missing = [f for f in required if f not in port]
    if missing:
        raise ValueError(f"port missing required field(s): {missing}")
    name = str(port["name"])
    if not name.upper().startswith("P"):
        raise ValueError(
            f"port 'name' must start with 'P' (Xyce's Port Device prefix), got {name!r}"
        )
    fields = [name, str(port["n1"]), str(port["n2"]), f"port={int(port['port'])}"]
    if "z0" in port:
        fields.append(f"z0={format_number(port['z0'])}")
    return " ".join(fields)


def generate_xyce_netlist(
    job: dict[str, Any],
    print_file: str | None,
    touchstone_file: str | None,
    comment: str = "Generated by run_xyce_simulation",
) -> str:
    """Generate a Xyce netlist from a structured job dict.

    `job` shape:
        {
          "components": [...],   # R/L/C/V/I -- see simulation/spice_netlist.py
          "ports": [              # optional -- triggers `.LIN` S-parameter
              {"name": "P1", "n1": node, "n2": node, "port": int,   # extraction; requires
               "z0": float (default 50.0)},                        # analysis['type'] == "ac"
              ...
          ],
          "raw_cards": [str, ...],   # optional escape hatch -- see
                                      # simulation/spice_netlist.py's SCOPE note.
          "analysis": {
              "type": "op" | "ac" | "tran" | "hb",
              # ac:   "sweep_type": "lin"|"oct"|"dec", "points": int,
              #       "start_freq_hz": float, "stop_freq_hz": float,
              # tran: "step_s": float, "stop_s": float,
              #       "start_s": float (optional), "max_step_s": float (optional),
              # hb:   "fundamental_freqs_hz": list[float] -- one or more Hz
              #       values (`.HB <fundamental frequencies>`, Reference
              #       Guide section 2.1.13, p.45 -- see this module's header
              #       docstring); one value for single-tone HB, several for
              #       multi-tone HB.
          },
          "outputs": [str, ...],   # optional -- Xyce output-variable tokens
                                    # for `.PRINT` (e.g. "V(out)", "VDB(out)",
                                    # "I(V1)"); ignored/unavailable for
                                    # analysis['type'] == "op" (see module
                                    # docstring SCOPE note).
          "lin": {                 # optional overrides for the `.LIN` line
              "lintype": "S"|"Y"|"Z" (default "S"),
              "dataformat": "RI"|"MA"|"DB" (default "RI"),
          },
        }

    `print_file` is the FILE= target for `.PRINT ... FORMAT=CSV` (read back
    by parse_xyce_csv()); pass None to skip generating a `.PRINT` line
    (e.g. no `outputs` given, or analysis type is "op"). `touchstone_file`
    is the FILE= target for `.LIN` (read back with skrf); pass None to
    skip generating ports/`.LIN` entirely.
    """
    components = job.get("components", [])
    raw_cards = job.get("raw_cards", [])
    ports = job.get("ports", [])
    analysis = job.get("analysis")
    if not analysis:
        raise ValueError("job['analysis'] must be a dict with a 'type' key")

    if ports and analysis.get("type") != "ac":
        raise ValueError(
            "job['ports'] (native `.LIN` S-parameter extraction) requires "
            "analysis['type'] == 'ac' -- `.LIN`'s SPARCALC=1 default runs at "
            "the frequencies on the `.AC` line (see this module's docstring citation)"
        )

    lines: list[str] = [f"* {comment}"]
    lines.extend(format_components(components))
    lines.extend(_port_card(port) for port in ports)
    lines.extend(str(card) for card in raw_cards)
    lines.extend(_analysis_run_lines(analysis))

    outputs = job.get("outputs")
    if print_file is not None and outputs:
        print_type = analysis["type"].upper()
        lines.append(f".PRINT {print_type} FORMAT=CSV FILE={print_file} " + " ".join(outputs))

    if touchstone_file is not None and ports:
        lin_opts = job.get("lin", {})
        lintype = lin_opts.get("lintype", "S")
        dataformat = lin_opts.get("dataformat", "RI")
        # FORMAT=TOUCHSTONE (v1), not Xyce's own TOUCHSTONE2 default: this
        # is the classic, universally-supported .sNp shape rf_tools/
        # touchstone.py's skrf.Network(path) (and every other tool in this
        # repo) already reads -- a deliberate override of Xyce's default,
        # not an oversight.
        lines.append(
            f".LIN SPARCALC=1 FORMAT=TOUCHSTONE LINTYPE={lintype} "
            f"DATAFORMAT={dataformat} FILE={touchstone_file}"
        )

    lines.append(".END")
    return "\n".join(lines) + "\n"


def parse_xyce_csv(text: str) -> dict[str, Any]:
    """Parse a `.PRINT ... FORMAT=CSV` output file into a
    `{"scale_name": ..., "scale": [...], "values": {column_name: [float, ...]}}`
    dict. The CSV format's own header row (see this module's docstring
    citation -- "a comma-separated value file with a header indicating the
    variables printed") is read as-is and used verbatim as each column's
    key: this module does NOT assume a specific naming convention for the
    real/imaginary columns Xyce auto-generates from a bare `V(node)`/
    `I(device)` request under AC analysis (that convention was not
    independently verified against a real run -- see module docstring). Ask
    for explicit `VR()`/`VI()`/`VM()`/`VP()`/`VDB()` (or `IR()`/`II()`/etc.)
    output-variable tokens in the job dict's `outputs` list instead of a
    bare `V()`/`I()` under AC analysis if you need predictable column keys.
    The first column is always treated as the scale (FREQ/TIME/INDEX,
    whatever Xyce's own CSV header names it) and returned separately;
    every other column becomes one entry in `values`.
    """
    rows = list(csv.reader(io.StringIO(text)))
    rows = [row for row in rows if row and any(cell.strip() for cell in row)]
    if not rows:
        return {"scale_name": None, "scale": [], "values": {}}

    header = [cell.strip() for cell in rows[0]]
    data_rows = [[float(cell) for cell in row] for row in rows[1:]]

    scale_name = header[0]
    scale = [row[0] for row in data_rows]
    values = {
        column_name: [row[col] for row in data_rows]
        for col, column_name in enumerate(header)
        if col > 0
    }
    return {"scale_name": scale_name, "scale": scale, "values": values}


def run_xyce_simulation(
    job: dict[str, Any],
    timeout_s: int = 600,
    executable: str | None = None,
    workdir: str | None = None,
) -> dict[str, Any]:
    """Generate a Xyce netlist from a structured job dict (matching network
    / filter / amplifier-bias sub-circuit -- see generate_xyce_netlist()
    for the full job shape), run it via XyceSimulator, and parse the
    requested outputs (`.PRINT` CSV, when `outputs` is given and analysis
    type isn't "op") and/or S-parameters (`.LIN` Touchstone, when `ports`
    is given) back out. Returns "SIMULATED" provenance.

    See this module's header comment for the format-verification citations
    and honest caveats -- in particular, the `.LIN`/S-parameter path
    carries one extra notch of uncertainty beyond this module's `.AC`/
    `.TRAN`/`.PRINT` coverage (see the "HONEST CONFIDENCE CAVEAT ON `.LIN`
    SPECIFICALLY" section there) on top of the standard not-run-against-a-
    real-binary caveat every adapter in this codebase carries.
    """
    work_dir = Path(workdir) if workdir else Path(tempfile.mkdtemp(prefix="xyce_"))
    work_dir.mkdir(parents=True, exist_ok=True)
    netlist_file = work_dir / "model.cir"

    analysis_type = (job.get("analysis") or {}).get("type")
    ports = job.get("ports", [])
    want_print = bool(job.get("outputs")) and analysis_type != "op"
    want_lin = bool(ports)

    print_file = work_dir / "xyce_output.csv" if want_print else None
    touchstone_file = work_dir / f"xyce_s_parameters.s{len(ports)}p" if want_lin else None

    netlist_file.write_text(
        generate_xyce_netlist(
            job,
            print_file=print_file.name if print_file else None,
            touchstone_file=touchstone_file.name if touchstone_file else None,
        )
    )

    simulator = XyceSimulator(executable=executable)
    result = simulator.run(
        {
            "netlist_file": str(netlist_file),
            "workdir": str(work_dir),
            "timeout_s": timeout_s,
        }
    )

    output: dict[str, Any] = {
        "provenance": "SIMULATED",
        "simulator": result.simulator,
        "status": result.status,
        "workdir": str(result.workdir),
        "netlist_file": str(netlist_file),
        "log": result.outputs.get("stdout", ""),
    }

    if print_file is not None:
        parsed = parse_xyce_csv(print_file.read_text() if print_file.exists() else "")
        output["scale_name"] = parsed["scale_name"]
        output["scale"] = parsed["scale"]
        output["values"] = parsed["values"]

    if touchstone_file is not None:
        if touchstone_file.exists():
            import skrf as rf

            network = rf.Network(str(touchstone_file))
            output["s_parameters"] = {
                "computed": True,
                "frequency_hz": network.f.tolist(),
                "z0_ohms": complex(network.z0[0, 0]).real,
                "touchstone_file": str(touchstone_file),
            }
            output["touchstone_file"] = str(touchstone_file)
        else:
            output["s_parameters"] = {
                "computed": False,
                "note": (
                    f"Xyce did not produce the expected Touchstone file "
                    f"({touchstone_file.name}) -- see this module's docstring "
                    "HONEST CONFIDENCE CAVEAT on `.LIN`."
                ),
            }

    return output
