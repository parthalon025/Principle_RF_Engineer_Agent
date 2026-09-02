"""ngspice circuit-level simulation (issue #57, part 1 of 2 -- see also
simulation/xyce.py): a nonlinear/linear circuit-level simulator for a
matching network, amplifier bias network, or filter sub-circuit, without
needing a paid tool (Keysight ADS). ngspice is free/open, no license.

SOURCES CONSULTED (primary; ngspice's own documentation, fetched directly
during implementation -- both the official ngspice.sourceforge.io PDF/HTML
manual and its chapter-split mirror at nmg.gitlab.io/ngspice-manual, which
tracks the same official manual content chapter-for-chapter and was used
where it made a specific page fetchable that the single-file XHTML manual's
sheer size did not):
  - Command-line batch-mode invocation ("ngspice -b -o outfile netlist",
    "-b"/"--batch": "run in batch mode"; "-o"/"--output=outfile": "All logs
    generated during a batch run (-b) will be saved in outfile"):
    nmg.gitlab.io/ngspice-manual/startingngspice/
    commandlineoptionsforstartingngspiceandngnutmeg.html, which is the
    HTML rendering of the official manual's "Command line options for
    starting ngspice and ngnutmeg" section (chapter 12 in the numbered
    PDF/XHTML manual at ngspice.sourceforge.io/docs/ngspice-html-manual/
    manual.xhtml).
  - `.AC <sweep type> <points> <fstart> <fstop>` general form (dec/oct/lin,
    ND/NO/NP, frequency in Hz, no unit suffix required):
    nmg.gitlab.io/ngspice-manual/analysesandoutputcontrol_batchmode/
    analyses/ac_small-signalacanalysis.html.
  - `.TRAN tstep tstop <tstart <tmax>> <UIC>` general form:
    nmg.gitlab.io/ngspice-manual/analysesandoutputcontrol_batchmode/
    analyses/tran_transientanalysis.html.
  - `.OP` (bare, no arguments) and the interactive-command equivalents
    (`op`, `ac dec ...`, `tran ...`) used inside a `.control`/`.endc`
    block to actually run an analysis in batch mode: same manual, chapter
    11 (Analyses) for the dot-command forms and chapter 13
    (Interactive Interpreter / control language) for the lowercase
    interactive-command forms used inside `.control`; the "ac lin 10001 0
    10001 ... print ... > results.txt" and similar worked `.control`-block
    examples confirming the lowercase-command-inside-`.control` pattern
    are from ngspice-users mailing-list/forum threads
    (sourceforge.net/p/ngspice/discussion) referencing this same manual
    section, not independently invented here.
  - `wrdata [file] [vecs]` control command -- writes each requested vector
    as a (scale, value) column pair, or (scale, real, imag) triple for a
    complex (AC) vector; the `set wr_singlescale` control variable, when
    set before `wrdata` is called, collapses the scale column to appear
    only once instead of once per vector (this module always sets it, so
    every wrdata output file this module reads has exactly one shared
    leading scale column, followed by 1 real value column per requested
    output for a real analysis (TRAN/OP) or 2 (real, imag) columns per
    requested output for AC): nmg.gitlab.io/ngspice-manual/
    interactiveinterpreter/commands/
    wrdata_writedatatoafile_simpletable.html.
  - R/L/C/V/I element instance-card forms and `.SUBCKT`/`.ENDS`/`X<name>`
    subcircuit forms: see simulation/spice_netlist.py's module docstring
    (this module imports its component-card generation from there, shared
    with simulation/xyce.py once both were written and the overlap was
    confirmed real).
  - ngspice's own per-subtree license mix (used for docs/LICENSE_MATRIX.md,
    NOT assumed to be one blanket license per this repo's own discipline):
    the actual COPYING file at
    https://raw.githubusercontent.com/ngspice/ngspice/master/COPYING
    (the official ngspice.sourceforge.io project's GitHub mirror), fetched
    and read directly -- core spice3f5 code is "new" (3-clause) BSD;
    numparam and adms subtrees are LGPL; tclspice is LGPLv2.1 (full license
    text quoted in that COPYING file); cider is a UC Berkeley "Research
    Software Agreement" (a custom, BSD-like-but-distinct non-commercial-
    redistribution license, not literally BSD text); xspice is public
    domain.

SCOPE OF THIS IMPLEMENTATION:
  - Analyses: `.OP` (bias point), `.AC` (small-signal frequency sweep),
    `.TRAN` (transient) -- covering the matching-network/filter (AC) and
    amplifier-nonlinearity (TRAN) use cases the ticket names. `.DC` sweep
    is NOT implemented (not named in the ticket's acceptance criteria; the
    same generate_ngspice_netlist()/parse_ngspice_wrdata() shape could
    support it in a future pass).
  - Components: structured R/L/C/V/I via simulation/spice_netlist.py, plus
    a `raw_cards` escape hatch for anything else (semiconductor devices,
    subcircuits, controlled sources) -- see that module's docstring SCOPE
    note for why this module does not generate SPICE model-parameter
    syntax itself.
  - S-parameters are NOT computed. Stable-release ngspice has no built-in
    `.SP`/S-parameter dot-command analysis (confirmed absent from the
    manual sections fetched above) -- real S-parameter extraction in
    ngspice instead requires porting its own bundled
    `examples/control_structs/s-param.cir` control-block script (a
    specific bias/port/de-embedding technique using the `wrs2p` command to
    emit a Touchstone file, per ngspice-users/ngspice-devel mailing-list
    discussion of that script) or its experimental (non-mainline,
    "RFSPICE"-flag-gated) native PORT-on-voltage-source syntax -- neither
    was implemented in this pass; see simulation/xyce.py for a real,
    natively-documented S-parameter path (Xyce's `.LIN` analysis) instead.
    This is an honest scope gap, not a fabricated result -- the same
    "computed=False plus an explanatory note" discipline
    simulation/openems.py uses for its own still-unimplemented far-field
    extraction.

HONEST CAVEAT: the real `ngspice` binary is NOT installed in this
environment (confirmed via `which ngspice`, exit 1) and was not available
to run against these generated netlists. Netlist generation and `wrdata`
output parsing are built to the documented format cited above; tests
exercise them only against a fake "ngspice" script (see
tests/test_ngspice.py), not a real ngspice run. Treat any result as
unverified end-to-end until it has been run against the real binary at
least once.
"""

from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from .base import SimulationResult, Simulator, SimulatorError
from .spice_netlist import format_components, format_number

_ANALYSIS_TYPES = ("op", "ac", "tran")


class NgspiceSimulator(Simulator):
    name = "ngspice"

    def __init__(self, executable: str | None = None):
        self.executable = executable or os.getenv("NGSPICE_BIN", "ngspice")

    def run(self, job: dict) -> SimulationResult:
        netlist_file = Path(job["netlist_file"]).resolve()
        workdir = Path(job.get("workdir", netlist_file.parent)).resolve()
        if not netlist_file.exists():
            raise SimulatorError(f"Input netlist not found: {netlist_file}")

        # "-b" (batch mode) + "-o <logfile>" is the documented ngspice batch
        # invocation (see this module's docstring citation) -- "-o" directs
        # all of batch mode's log/diagnostic text to that file rather than
        # (undocumented, not relied on here) stdout, so this reads the log
        # file back rather than trusting captured stdout for diagnostics.
        log_file = workdir / "ngspice.log"
        timeout_s = int(job.get("timeout_s", 600))
        try:
            completed = subprocess.run(
                [self.executable, "-b", "-o", str(log_file), str(netlist_file)],
                cwd=workdir,
                capture_output=True,
                text=True,
                timeout=timeout_s,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise SimulatorError(f"ngspice timed out after {timeout_s}s: {exc}") from exc

        log_text = log_file.read_text(errors="replace") if log_file.exists() else ""
        if completed.returncode != 0:
            diagnostic = log_text or completed.stderr or completed.stdout
            raise SimulatorError(f"ngspice failed ({completed.returncode}): {diagnostic[-4000:]}")

        return SimulationResult(
            simulator=self.name,
            status="COMPLETED",
            workdir=workdir,
            outputs={"log": log_text[-8000:]},
        )


def generate_ngspice_netlist(
    job: dict[str, Any],
    output_file: str,
    comment: str = "Generated by run_ngspice_simulation",
) -> str:
    """Generate an ngspice netlist from a structured job dict.

    `job` shape:
        {
          "components": [       # R/L/C/V/I -- see simulation/spice_netlist.py
              {"type": "R"|"C"|"L"|"V"|"I", "name": str, "n1": node,      # for the exact
               "n2": node, "value": float,                               # per-type shape
               "dc": float, "ac_mag": float, "ac_phase": float},   # (dc/ac_* -> V/I only)
              ...
          ],
          "raw_cards": [str, ...],       # optional: already-valid SPICE cards
                                          # (nonlinear devices, .SUBCKT/X, etc.)
                                          # inserted verbatim -- see
                                          # simulation/spice_netlist.py's SCOPE note.
          "analysis": {
              "type": "op" | "ac" | "tran",
              # ac:
              "sweep_type": "dec"|"oct"|"lin", "points": int,
              "start_freq_hz": float, "stop_freq_hz": float,
              # tran:
              "step_s": float, "stop_s": float,
              "start_s": float (optional), "max_step_s": float (optional),
          },
          "outputs": [str, ...],   # node-voltage/branch-current expressions,
                                    # e.g. "v(out)", "v(in)", "i(vin)" -- passed
                                    # verbatim to ngspice's `wrdata`.
        }

    `output_file` is the path `wrdata` writes its plain-ASCII results to
    (read back by parse_ngspice_wrdata()). Node/frequency/time values are in
    ohms/farads/henries/volts/amps/Hz/seconds throughout -- no unit-suffix
    shorthand is generated (see simulation/spice_netlist.py's
    format_number citation).
    """
    components = job.get("components", [])
    raw_cards = job.get("raw_cards", [])
    outputs = job.get("outputs")
    if not outputs:
        raise ValueError("job['outputs'] must be a non-empty list of node/branch expressions")
    analysis = job.get("analysis")
    if not analysis or "type" not in analysis:
        raise ValueError("job['analysis'] must be a dict with a 'type' key")
    analysis_type = analysis["type"]
    if analysis_type not in _ANALYSIS_TYPES:
        raise ValueError(
            f"analysis['type'] must be one of {_ANALYSIS_TYPES}, got {analysis_type!r}"
        )

    lines: list[str] = [f"* {comment}"]
    lines.extend(format_components(components))
    lines.extend(str(card) for card in raw_cards)

    if analysis_type == "op":
        run_command = "op"
    elif analysis_type == "ac":
        required = ("sweep_type", "points", "start_freq_hz", "stop_freq_hz")
        missing = [f for f in required if f not in analysis]
        if missing:
            raise ValueError(f"analysis (type='ac') missing required field(s): {missing}")
        sweep_type = analysis["sweep_type"]
        if sweep_type not in ("dec", "oct", "lin"):
            raise ValueError(
                f"analysis['sweep_type'] must be 'dec', 'oct', or 'lin', got {sweep_type!r}"
            )
        run_command = (
            f"ac {sweep_type} {int(analysis['points'])} "
            f"{format_number(analysis['start_freq_hz'])} {format_number(analysis['stop_freq_hz'])}"
        )
    else:  # tran
        required = ("step_s", "stop_s")
        missing = [f for f in required if f not in analysis]
        if missing:
            raise ValueError(f"analysis (type='tran') missing required field(s): {missing}")
        tran_fields = [format_number(analysis["step_s"]), format_number(analysis["stop_s"])]
        if "start_s" in analysis:
            tran_fields.append(format_number(analysis["start_s"]))
            if "max_step_s" in analysis:
                tran_fields.append(format_number(analysis["max_step_s"]))
        run_command = "tran " + " ".join(tran_fields)

    lines.append(".control")
    # One shared scale column across every requested output vector (see
    # this module's docstring wrdata citation) -- otherwise each output
    # gets its own repeated scale column, complicating column-count-based
    # parsing in parse_ngspice_wrdata() below for no benefit (the scale
    # values are identical across vectors from the same analysis run).
    lines.append("set wr_singlescale")
    lines.append(run_command)
    lines.append(f"wrdata {output_file} " + " ".join(outputs))
    lines.append(".endc")
    lines.append(".end")
    return "\n".join(lines) + "\n"


def parse_ngspice_wrdata(
    text: str, outputs: list[str], analysis_type: str
) -> dict[str, Any]:
    """Parse a `wrdata` output file (see generate_ngspice_netlist()) into
    structured per-output data, aligned with either a frequency (AC) or
    time (TRAN/OP) axis.

    With `set wr_singlescale` always set by generate_ngspice_netlist(),
    each data row is: <scale> then, per requested output in order, either
    one real value (TRAN/OP) or a (real, imag) pair (AC) -- see this
    module's docstring wrdata citation. Lines that don't tokenize entirely
    as floats (e.g. a header ngspice may or may not emit) are skipped
    rather than assumed absent, the same tolerant-parsing approach
    simulation/nec2pp.py's parse_nec2_output() uses for its own text
    output.

    Returns `{"scale": [...], "scale_name": "frequency_hz"|"time_s",
    "values": {output_name: [[real, imag], ...] | [float, ...]}}`.
    """
    width_per_output = 2 if analysis_type == "ac" else 1
    expected_columns = 1 + width_per_output * len(outputs)

    rows: list[list[float]] = []
    for line in text.splitlines():
        tokens = line.split()
        if len(tokens) != expected_columns:
            continue
        try:
            rows.append([float(tok) for tok in tokens])
        except ValueError:
            continue

    scale = [row[0] for row in rows]
    values: dict[str, Any] = {}
    for i, name in enumerate(outputs):
        col = 1 + i * width_per_output
        if analysis_type == "ac":
            values[name] = [[row[col], row[col + 1]] for row in rows]
        else:
            values[name] = [row[col] for row in rows]

    return {
        "scale": scale,
        "scale_name": "frequency_hz" if analysis_type == "ac" else "time_s",
        "values": values,
    }


def run_ngspice_simulation(
    job: dict[str, Any],
    timeout_s: int = 600,
    executable: str | None = None,
    workdir: str | None = None,
) -> dict[str, Any]:
    """Generate an ngspice netlist from a structured job dict (matching
    network / filter / amplifier-bias sub-circuit -- see
    generate_ngspice_netlist() for the full job shape), run it via
    NgspiceSimulator, and parse the requested outputs' AC/TRAN/OP data back
    out. Returns "SIMULATED" provenance.

    See this module's header comment for the format-verification citations
    and the honest caveats: netlist generation and `wrdata` parsing are
    built to the documented ngspice format, not verified against a real
    ngspice binary run in this environment; and S-parameters are not
    computed at all in this pass (use simulation/xyce.py's `.LIN` support,
    or correlate_simulated_and_measured against a "values"-shaped AC
    result directly, for that need).
    """
    work_dir = Path(workdir) if workdir else Path(tempfile.mkdtemp(prefix="ngspice_"))
    work_dir.mkdir(parents=True, exist_ok=True)
    netlist_file = work_dir / "model.cir"
    output_file = work_dir / "ngspice_output.dat"
    outputs = job.get("outputs", [])
    analysis_type = (job.get("analysis") or {}).get("type")
    netlist_file.write_text(generate_ngspice_netlist(job, output_file.name))

    simulator = NgspiceSimulator(executable=executable)
    result = simulator.run(
        {
            "netlist_file": str(netlist_file),
            "workdir": str(work_dir),
            "timeout_s": timeout_s,
        }
    )

    output_text = output_file.read_text() if output_file.exists() else ""
    parsed = parse_ngspice_wrdata(output_text, outputs, analysis_type)

    return {
        "provenance": "SIMULATED",
        "scale_name": parsed["scale_name"],
        "scale": parsed["scale"],
        "values": parsed["values"],
        "simulator": result.simulator,
        "status": result.status,
        "workdir": str(result.workdir),
        "netlist_file": str(netlist_file),
        "output_file": str(output_file),
    }
