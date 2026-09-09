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
  - `.NOISE OUTVAR SRC dec|oct|lin ND FSTART FSTOP <pts_per_summary>` general
    form; `onoise_spectrum`/`inoise_spectrum` as the real-valued (not
    complex) output vectors ngspice's own noise analysis creates on its
    "noise1" plot, and that running the lowercase interactive `noise ...`
    command (mirroring chapter 13's other interactive analysis commands --
    `ac`, `dc`, `op`, `sens`, `tf`, `tran` are explicitly documented there)
    makes that plot current so `wrdata file onoise_spectrum
    inoise_spectrum` reads it back without a plot-qualified name: (issue
    #283) nmg.gitlab.io/ngspice-manual/analysesandoutputcontrol_batchmode/
    analyses/noise_noiseanalysis.html for the dot-command syntax and vector
    names; a real worked ngspice-KiCad noise-analysis tutorial
    (melonkinenbi.f5.si/.../Tutor4_OpAmpNoise, corroborated by a second,
    independent copy of the same tutorial at freeplanets.ship.jp) for the
    literal ".control { run; setplot noise1; wrdata noise.dat
    noise1.onoise_spectrum noise1.inoise_spectrum }" worked example
    confirming both the vector names and that they are readable
    unqualified once "noise1" is the current plot -- fetched via
    search-engine summary of these pages, not independently re-fetched as
    primary text in this pass.
  - `.DISTO dec|oct|lin ND|NO|NP FSTART FSTOP <f2overf1>` general form
    (issue #283): nmg.gitlab.io/ngspice-manual/
    analysesandoutputcontrol_batchmode/analyses/disto_distortionanalysis.html
    -- fetched directly; its own text states the fundamental-frequency
    sweep runs "exactly as in the .ac command" (hence this module reuses
    ac's sweep_type/points/start_freq_hz/stop_freq_hz field names for
    disto too) and that results are "AC values of all node voltages and
    branch currents at the harmonic frequencies 2F1 and 3F1" (hence they
    are parsed as complex, the same wrdata shape as `.AC`). That running
    `disto ...` makes a "disto1" plot current (2nd harmonic; 3rd harmonic
    needs the qualified "disto2.<expr>" name) is corroborated by a real
    ngspice-users forum worked example
    (sourceforge.net/p/ngspice/discussion/ngspice-tips/thread/e58621f6,
    "Min. w. example for disto analysis" -- `disto dec 10 10 30k / setplot
    disto1 / ... hardcopy ... V(4) ... / hardcopy ... disto2.V(4) ...`),
    fetched via search-engine summary of that thread, not independently
    re-fetched as primary text in this pass.
  - `.PZ node1 node2 node3 node4 cur|vol pol|zer|pz` general form (issue
    #283): nmg.gitlab.io/ngspice-manual/analysesandoutputcontrol_batchmode/
    analyses/pz_pole-zeroanalysis.html -- fetched directly, and this exact
    page states "in interactive mode, the command syntax is the same
    except that the first field is pz instead of .pz" and "to print the
    results, one should use the command print all" (hence this module's
    pz/sens `.control` blocks end with "print all", not `wrdata`, and pz's
    interactive command is confirmed rather than assumed-by-analogy the
    way disto's is above). The `<name> = <real>,<imag>` per-vector "print
    all" line shape (e.g. "pole(1) = -2.618033988749895e+00,
    0.000000000000000e+00") is corroborated by two independent real
    ngspice-forum `.PZ` worked-output examples (sourceforge.net/p/ngspice/
    discussion/127605/thread/14338e7e and electronics-lab.com/forums/
    threads/how-to-plot-pole-zero-results-in-ngspice.72612), fetched via
    search-engine summary, not independently re-fetched as primary text in
    this pass -- see parse_ngspice_print_values()'s own docstring for the
    same caveat repeated where it is actually relied on.
  - `.SENS OUTVAR` (DC) / `.SENS OUTVAR AC dec|oct|lin ND|NO|NP FSTART
    FSTOP` (AC) general form (issue #283): nmg.gitlab.io/ngspice-manual/
    analysesandoutputcontrol_batchmode/analyses/
    sens_dcorsmall-signalacsensitivityanalysis.html -- fetched directly
    (note this page's own URL drops the hyphen ngspice's table of contents
    implies -- "dcorsmall-signalac", not "dcorsmallsignalac" -- confirmed
    by testing both). Per-parameter sensitivities are reported as "change
    in output per unit change of input" (absolute, not normalized). This
    module's own SENS "print all" line-shape parsing is an HONEST
    EXTRAPOLATION from `.PZ`'s confirmed "line" layout for length-1
    vectors (see parse_ngspice_print_values()'s own docstring) -- no
    literal `.SENS` "print all" worked-output example could be found in
    this pass to independently confirm it carries the identical
    "name = value" shape.
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
    `.TRAN` (transient), `.NOISE` (noise figure), `.DISTO` (harmonic
    distortion), `.PZ` (pole-zero), and `.SENS` (DC/AC sensitivity) --
    covering the matching-network/filter (AC), amplifier-nonlinearity
    (TRAN/DISTO), and amplifier/LNA-noise (NOISE) use cases named across
    the original ticket (#57) and this one (#283), plus PZ/SENS's
    stability/parameter-sensitivity use case. `.NOISE`/`.DISTO` results are
    parsed into the same structured `{scale, scale_name, values}` shape as
    `.AC`/`.TRAN`/`.OP` via parse_ngspice_wrdata() (noise's spectral-
    density vectors real-valued; disto's harmonic-distortion vectors
    complex, like AC). `.PZ`/`.SENS` do NOT fit that shape -- neither
    analysis sweeps anything, so there is no frequency/time axis to
    report -- and are instead parsed by the sibling
    parse_ngspice_print_values() from the interactive `print all` command's
    text output; see that function's own docstring for the citation and
    the one still-open honest gap (`.SENS`'s "print all" line shape is an
    extrapolation from `.PZ`'s confirmed one, not independently
    re-verified against a real `.SENS` "print all" worked example). `.DC`
    sweep and `.TF` (transfer function) are NOT implemented (`.DC` was not
    named in the original ticket's acceptance criteria; `.TF` is
    explicitly out of #283's scope per that ticket's own text -- both
    remain a gap the same generate_ngspice_netlist()/parse_ngspice_wrdata()
    shape could close in a future pass).
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

VERIFIED END TO END 2026-09-04: a real ngspice-47 binary (portable Windows
build, sha256 59225971bd68cdd1199443649aa4615a9e6d684933f205ab49006a3942518f5a
-- see scripts/install_ngspice_windows.ps1) was run through
run_ngspice_simulation() against a plain RC low-pass filter (R=1kOhm,
C=1uF, cutoff ~159Hz), `.AC dec 5 1 1e6`. Real ngspice accepted the
generated netlist and `wrdata` output unmodified; the parsed AC result
matched the filter's known physics (near-unity |v(out)| at 1Hz, rolled off
to ~1.6e-4 by 1MHz) -- see tests/test_ngspice.py's real-binary test for the
reproducible version of this same check. This covers the `.AC` analysis
path, plain R/L/C/V components, and wrdata parsing end to end. NOT yet
verified against a real binary: `.TRAN`/`.OP` analyses, the `raw_cards`
escape hatch, and (added issue #283) `.NOISE`/`.DISTO`/`.PZ`/`.SENS` --
those remain format-verified-against-documentation only, same caveat as
before. A second real binary (ngspice-42, Ubuntu 24.04's
apt package -- see this repo's Dockerfile) was also confirmed to exist at
the adapter's plain default executable name "ngspice" with no NGSPICE_BIN
override needed on Linux, unlike Windows where the portable build's
console binary is named "ngspice_con.exe".
"""

from __future__ import annotations

import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from .base import SimulationResult, Simulator, SimulatorError
from .spice_netlist import format_components, format_number

# Single source of truth for how each analysis type is generated and parsed
# (see generate_ngspice_netlist()'s per-type branches and
# parse_ngspice_wrdata()'s docstring for what each flag controls below).
# Previously these were four separate parallel tuples that a new analysis
# type had to be added to by hand, independently, and get right in all four
# (Fowler's "Repeated Switches" smell) -- this collapses that bookkeeping
# into one table so adding an 8th analysis type means editing one entry
# here instead of hunting down four tuples that must agree with each other.
#   wrdata: its ".control"-block interactive command leaves a frequency- or
#     time-swept vector readable by `wrdata` (pz/sens do NOT -- see
#     print_value below).
#   print_value: reports a small, unswept set of complex values (poles/
#     zeros, per-parameter sensitivities) via the interactive `print all`
#     command instead -- see parse_ngspice_print_values() and this module's
#     SCOPE docstring section for the citation and honest caveat.
#   complex: `wrdata` writes a (real, imag) pair per requested output for
#     this analysis's vectors (AC small-signal quantities); every other
#     wrdata-shaped analysis writes one real value per output. `.DISTO`'s
#     harmonic-distortion vectors are themselves AC quantities at the swept
#     fundamental frequency, so they are complex too -- see this module's
#     docstring for the citation.
#   frequency_scale: this wrdata-shaped analysis's scale column is
#     frequency rather than time.
_ANALYSIS_TYPE_INFO: dict[str, dict[str, bool]] = {
    "op": {"wrdata": True, "print_value": False, "complex": False, "frequency_scale": False},
    "ac": {"wrdata": True, "print_value": False, "complex": True, "frequency_scale": True},
    "tran": {"wrdata": True, "print_value": False, "complex": False, "frequency_scale": False},
    "noise": {"wrdata": True, "print_value": False, "complex": False, "frequency_scale": True},
    "disto": {"wrdata": True, "print_value": False, "complex": True, "frequency_scale": True},
    "pz": {"wrdata": False, "print_value": True, "complex": False, "frequency_scale": False},
    "sens": {"wrdata": False, "print_value": True, "complex": False, "frequency_scale": False},
}

_ANALYSIS_TYPES = tuple(_ANALYSIS_TYPE_INFO)
_WRDATA_ANALYSIS_TYPES = tuple(t for t, info in _ANALYSIS_TYPE_INFO.items() if info["wrdata"])
_PRINT_VALUE_ANALYSIS_TYPES = tuple(
    t for t, info in _ANALYSIS_TYPE_INFO.items() if info["print_value"]
)
_COMPLEX_WRDATA_ANALYSIS_TYPES = tuple(
    t for t, info in _ANALYSIS_TYPE_INFO.items() if info["complex"]
)
_FREQUENCY_SCALE_ANALYSIS_TYPES = tuple(
    t for t, info in _ANALYSIS_TYPE_INFO.items() if info["frequency_scale"]
)


class NgspiceSimulator(Simulator):
    name = "ngspice"

    def __init__(self, executable: str | None = None):
        self.executable = executable or os.getenv("NGSPICE_BIN") or "ngspice"

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
            # "log" is a short diagnostic convenience only -- capped to its
            # last 8000 characters, same rationale as the SimulatorError
            # diagnostic two lines above. "log_file" is the untruncated file
            # on disk (see simulation/ltspice.py's NgspiceSimulator-sibling
            # for the same "log" + "log_file" pairing) -- a caller that needs
            # the FULL batch-mode text (e.g. run_ngspice_simulation()'s
            # `.PZ`/`.SENS` print-all parsing below, where the meaningful
            # lines could otherwise fall outside the last 8000 characters)
            # must re-read it from here rather than trust the capped string.
            outputs={"log": log_text[-8000:], "log_file": str(log_file)},
        )


# Shared by "ac", "disto" (whose fundamental-frequency sweep is documented
# as "exactly as in the .ac command"), and "sens"'s optional AC form.
_AC_SWEEP_FIELDS = ("sweep_type", "points", "start_freq_hz", "stop_freq_hz")


def _require_fields(analysis: dict[str, Any], type_label: str, required: tuple[str, ...]) -> None:
    """Raise the same 'analysis (type=...) missing required field(s): [...]'
    ValueError every analysis-type branch below uses, naming exactly what is
    absent rather than failing generically -- this repo's CLAUDE.md has a
    "Warn, never block" section on being specific about what a warning
    assumes and costs; the same specificity applies to a hard validation
    error (name exactly what's missing, don't just say "invalid job")."""
    missing = [f for f in required if f not in analysis]
    if missing:
        raise ValueError(f"analysis (type={type_label!r}) missing required field(s): {missing}")


def _require_allowed(analysis: dict[str, Any], field: str, allowed: tuple[str, ...]) -> str:
    """Raise a 'must be one of (...)' ValueError naming the field, the
    allowed values, and what was actually given if analysis[field] isn't
    one of `allowed` -- the same "value not in an allowed set" shape used
    for sweep_type/tf_type/analysis_mode below, and the phrasing this
    codebase already uses elsewhere for the same kind of check (e.g.
    simulation/spice_netlist.py, simulation/xyce.py, simulation/meep.py).
    Returns the validated value so a caller can use it inline."""
    value = analysis[field]
    if value not in allowed:
        raise ValueError(f"analysis[{field!r}] must be one of {allowed}, got {value!r}")
    return value


_SWEEP_TYPES = ("dec", "oct", "lin")


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
              "type": "op" | "ac" | "tran" | "noise" | "disto" | "pz" | "sens",
              # ac:
              "sweep_type": "dec"|"oct"|"lin", "points": int,
              "start_freq_hz": float, "stop_freq_hz": float,
              # tran:
              "step_s": float, "stop_s": float,
              "start_s": float (optional), "max_step_s": float (optional),
              # noise -- OUTVAR/SRC per ngspice's ".noise" dot-command form;
              # "sweep_type"/"points"/"start_freq_hz"/"stop_freq_hz" as ac:
              "output_node": str,   # e.g. "v(5)" or "v(5,3)" -- node the
                                     # total output noise is measured at
              "src": str,            # independent source used as input ref
              "pts_per_summary": int (optional),
              # disto -- fundamental-frequency sweep "exactly as in the .ac
              # command" per ngspice's own docs, so it reuses ac's
              # "sweep_type"/"points"/"start_freq_hz"/"stop_freq_hz" fields:
              "f2overf1": float (optional, 0 < value < 1 -- two-tone/
                                  spectral mode instead of single-tone/
                                  harmonic mode),
              # pz:
              "node1": node, "node2": node,   # input node pair
              "node3": node, "node4": node,   # output node pair
              "tf_type": "cur" | "vol",       # input current or voltage
              "analysis_mode": "pol" | "zer" | "pz",
              # sens -- DC form needs only "outvar"; AC form additionally
              # needs the same 4 ac-style sweep fields as "ac"/"disto":
              "outvar": str,   # node voltage or V-source branch current
          },
          "outputs": [str, ...],   # meaning is analysis-type-specific, passed
                                    # verbatim to ngspice's `wrdata` (ignored
                                    # for pz/sens, which report their results
                                    # via `print all` instead -- see below):
                                    #   op/ac/tran: node-voltage/branch-current
                                    #     expressions, e.g. "v(out)", "i(vin)".
                                    #   noise: the fixed vector names ngspice's
                                    #     own noise analysis creates, i.e. some
                                    #     of "onoise_spectrum"/"inoise_spectrum"
                                    #     (real-valued spectral density) -- NOT
                                    #     arbitrary node expressions.
                                    #   disto: node-voltage/branch-current
                                    #     expressions read from the harmonic-
                                    #     distortion analysis's current plot
                                    #     (2nd-harmonic values; the 3rd-harmonic
                                    #     plot needs the qualified form, e.g.
                                    #     "disto2.v(out)" -- see this module's
                                    #     docstring for the citation).
        }

    `output_file` is the path `wrdata` writes its plain-ASCII results to
    (read back by parse_ngspice_wrdata()) for every analysis type except
    `.PZ`/`.SENS`, which report a small set of poles/zeros or per-parameter
    sensitivities via the interactive `print all` command instead -- see
    parse_ngspice_print_values(). Node/frequency/time values are in
    ohms/farads/henries/volts/amps/Hz/seconds throughout -- no unit-suffix
    shorthand is generated (see simulation/spice_netlist.py's
    format_number citation).
    """
    components = job.get("components", [])
    raw_cards = job.get("raw_cards", [])
    outputs = job.get("outputs")
    analysis = job.get("analysis")
    if not analysis or "type" not in analysis:
        raise ValueError("job['analysis'] must be a dict with a 'type' key")
    analysis_type = analysis["type"]
    if analysis_type not in _ANALYSIS_TYPES:
        raise ValueError(
            f"analysis['type'] must be one of {_ANALYSIS_TYPES}, got {analysis_type!r}"
        )
    if analysis_type in _WRDATA_ANALYSIS_TYPES and not outputs:
        raise ValueError("job['outputs'] must be a non-empty list of node/branch expressions")

    lines: list[str] = [f"* {comment}"]
    lines.extend(format_components(components))
    lines.extend(str(card) for card in raw_cards)

    if analysis_type == "op":
        run_command = "op"
    elif analysis_type == "ac":
        _require_fields(analysis, "ac", _AC_SWEEP_FIELDS)
        _require_allowed(analysis, "sweep_type", _SWEEP_TYPES)
        run_command = (
            f"ac {analysis['sweep_type']} {int(analysis['points'])} "
            f"{format_number(analysis['start_freq_hz'])} {format_number(analysis['stop_freq_hz'])}"
        )
    elif analysis_type == "tran":
        _require_fields(analysis, "tran", ("step_s", "stop_s"))
        tran_fields = [format_number(analysis["step_s"]), format_number(analysis["stop_s"])]
        if "start_s" in analysis:
            tran_fields.append(format_number(analysis["start_s"]))
            if "max_step_s" in analysis:
                tran_fields.append(format_number(analysis["max_step_s"]))
        run_command = "tran " + " ".join(tran_fields)
    elif analysis_type == "noise":
        _require_fields(analysis, "noise", ("output_node", "src", *_AC_SWEEP_FIELDS))
        _require_allowed(analysis, "sweep_type", _SWEEP_TYPES)
        run_command = (
            f"noise {analysis['output_node']} {analysis['src']} {analysis['sweep_type']} "
            f"{int(analysis['points'])} {format_number(analysis['start_freq_hz'])} "
            f"{format_number(analysis['stop_freq_hz'])}"
        )
        if "pts_per_summary" in analysis:
            run_command += f" {int(analysis['pts_per_summary'])}"
    elif analysis_type == "disto":
        _require_fields(analysis, "disto", _AC_SWEEP_FIELDS)
        _require_allowed(analysis, "sweep_type", _SWEEP_TYPES)
        run_command = (
            f"disto {analysis['sweep_type']} {int(analysis['points'])} "
            f"{format_number(analysis['start_freq_hz'])} {format_number(analysis['stop_freq_hz'])}"
        )
        if "f2overf1" in analysis:
            run_command += f" {format_number(analysis['f2overf1'])}"
    elif analysis_type == "pz":
        _require_fields(
            analysis, "pz", ("node1", "node2", "node3", "node4", "tf_type", "analysis_mode")
        )
        tf_type = _require_allowed(analysis, "tf_type", ("cur", "vol"))
        analysis_mode = _require_allowed(analysis, "analysis_mode", ("pol", "zer", "pz"))
        run_command = (
            f"pz {analysis['node1']} {analysis['node2']} {analysis['node3']} "
            f"{analysis['node4']} {tf_type} {analysis_mode}"
        )
    else:  # sens
        _require_fields(analysis, "sens", ("outvar",))
        run_command = f"sens {analysis['outvar']}"
        if any(f in analysis for f in _AC_SWEEP_FIELDS):
            _require_fields(analysis, "sens", _AC_SWEEP_FIELDS)
            _require_allowed(analysis, "sweep_type", _SWEEP_TYPES)
            run_command += (
                f" ac {analysis['sweep_type']} {int(analysis['points'])} "
                f"{format_number(analysis['start_freq_hz'])} "
                f"{format_number(analysis['stop_freq_hz'])}"
            )

    lines.append(".control")
    if analysis_type in _WRDATA_ANALYSIS_TYPES:
        # One shared scale column across every requested output vector (see
        # this module's docstring wrdata citation) -- otherwise each output
        # gets its own repeated scale column, complicating column-count-based
        # parsing in parse_ngspice_wrdata() below for no benefit (the scale
        # values are identical across vectors from the same analysis run).
        lines.append("set wr_singlescale")
        lines.append(run_command)
        lines.append(f"wrdata {output_file} " + " ".join(outputs))
    else:  # pz, sens -- a handful of unswept complex values, not a vector
        # `wrdata` can write; ngspice's own `.PZ` manual page states plainly
        # "to print the results, one should use the command `print all`"
        # (see this module's docstring citation) -- `.SENS` has no
        # documented `wrdata`-compatible form either, so the same mechanism
        # is reused for it. Read back by parse_ngspice_print_values().
        lines.append(run_command)
        lines.append("print all")
    lines.append(".endc")
    lines.append(".end")
    return "\n".join(lines) + "\n"


def parse_ngspice_wrdata(text: str, outputs: list[str], analysis_type: str) -> dict[str, Any]:
    """Parse a `wrdata` output file (see generate_ngspice_netlist()) into
    structured per-output data, aligned with either a frequency (AC) or
    time (TRAN/OP) axis.

    With `set wr_singlescale` always set by generate_ngspice_netlist(),
    each data row is: <scale> then, per requested output in order, either
    one real value (TRAN/OP/NOISE -- noise's onoise_spectrum/inoise_spectrum
    are real-valued spectral densities, not complex) or a (real, imag) pair
    (AC, and DISTO -- whose harmonic-distortion vectors are themselves AC
    small-signal quantities at the swept fundamental frequency) -- see this
    module's docstring wrdata citation. Lines that don't tokenize entirely
    as floats (e.g. a header ngspice may or may not emit) are skipped
    rather than assumed absent, the same tolerant-parsing approach
    simulation/nec2pp.py's parse_nec2_output() uses for its own text
    output.

    Returns `{"scale": [...], "scale_name": "frequency_hz"|"time_s",
    "values": {output_name: [[real, imag], ...] | [float, ...]}}`.
    """
    width_per_output = 2 if analysis_type in _COMPLEX_WRDATA_ANALYSIS_TYPES else 1
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
        if analysis_type in _COMPLEX_WRDATA_ANALYSIS_TYPES:
            values[name] = [[row[col], row[col + 1]] for row in rows]
        else:
            values[name] = [row[col] for row in rows]

    is_frequency_scaled = analysis_type in _FREQUENCY_SCALE_ANALYSIS_TYPES
    return {
        "scale": scale,
        "scale_name": "frequency_hz" if is_frequency_scaled else "time_s",
        "values": values,
    }


# Matches one "<name> = <real>[,<imag>]" line from `print all`'s output --
# see parse_ngspice_print_values()'s docstring for the citation and caveat.
_PRINT_VALUE_LINE_RE = re.compile(
    r"^\s*(?P<name>\S+)\s*=\s*(?P<real>[-+]?[0-9.]+(?:[eE][-+]?[0-9]+)?)"
    r"(?:\s*,\s*(?P<imag>[-+]?[0-9.]+(?:[eE][-+]?[0-9]+)?))?\s*$"
)


def parse_ngspice_print_values(text: str) -> dict[str, Any]:
    """Parse the interactive `print all` command's text output for an
    analysis whose result is a small, unswept set of values -- `.PZ`
    (poles/zeros) and `.SENS` (per-parameter sensitivities) -- rather than
    a frequency/time-swept vector `wrdata` can emit (see
    generate_ngspice_netlist()'s SCOPE note on why these two analyses end
    their `.control` block with `print all` instead of a `wrdata` line).

    ngspice's own `print` command documentation states that when every
    named vector has length 1 -- true for both `.PZ`'s poles/zeros and
    `.SENS`'s DC-operating-point sensitivities, since neither analysis
    sweeps anything -- "line" is the default display layout rather than
    the columnar SPICE2-style table `print col all` uses for a swept
    result. Independent ngspice-forum worked examples of real `.PZ` output
    (see this module's docstring citation) show that "line" layout as one
    `<name> = <value>` line per vector, a complex value written as
    `<real>,<imag>` -- confirmed against real `.PZ` output; NOT
    independently re-fetched against a literal official-manual worked
    example for `.SENS`'s own line shape, since none could be found in this
    pass -- an honest gap, the same not-yet-independently-confirmed
    discipline this module's other citations already use. This parser is
    intentionally generic (any `name = value[,value]` line, not specific to
    "pole"/"zero" names) so the same function serves both analyses.

    Returns `{name: [real, imag]}` for a `<name> = <real>,<imag>` line, or
    `{name: real}` for a `<name> = <real>` line with no imaginary part.
    Lines that don't match this shape (log/diagnostic text, circuit-summary
    lines, blank lines) are skipped rather than assumed absent -- the same
    tolerant-parsing approach parse_ngspice_wrdata() uses for its own text.
    """
    values: dict[str, Any] = {}
    for line in text.splitlines():
        match = _PRINT_VALUE_LINE_RE.match(line)
        if not match:
            continue
        real = float(match.group("real"))
        imag = match.group("imag")
        values[match.group("name")] = [real, float(imag)] if imag is not None else real
    return values


def run_ngspice_simulation(
    job: dict[str, Any],
    timeout_s: int = 600,
    executable: str | None = None,
    workdir: str | None = None,
) -> dict[str, Any]:
    """Generate an ngspice netlist from a structured job dict (matching
    network / filter / amplifier-bias sub-circuit -- see
    generate_ngspice_netlist() for the full job shape), run it via
    NgspiceSimulator, and parse the requested outputs' data back out.
    Returns "SIMULATED" provenance.

    For every analysis type except `.PZ`/`.SENS` (see
    _PRINT_VALUE_ANALYSIS_TYPES), the result's data comes from `wrdata`'s
    output file via parse_ngspice_wrdata(): `scale`/`scale_name` are the
    swept frequency or time axis, and `values` is `{output_name:
    [float, ...] | [[real, imag], ...]}`. For `.PZ`/`.SENS`, there is no
    swept axis to report at all (`scale`/`scale_name` are `None`) --
    `values` instead comes from parse_ngspice_print_values() reading the
    `print all` text out of ngspice's own batch-mode log file, re-read in
    full from disk via NgspiceSimulator.run()'s "log_file" output rather
    than its "log" output -- "log" is capped to its last 8000 characters
    (a diagnostic convenience only; see that method's own citation), and a
    real run's netlist echo, convergence warnings, or ngspice's own
    end-of-run summary text can push the `print all` lines outside that
    trailing window, silently starving parse_ngspice_print_values() of the
    very data it exists to parse. The same untruncated-file-read approach
    the `wrdata` path below already uses for its own output file.

    See this module's header comment for the format-verification citations
    and the honest caveats: netlist generation and result parsing are
    built to the documented ngspice format, not verified against a real
    ngspice binary run in this environment (`.AC` is the one exception --
    see the VERIFIED END TO END note); and S-parameters are not computed at
    all in this pass (use simulation/xyce.py's `.LIN` support, or
    correlate_simulated_and_measured against a "values"-shaped AC result
    directly, for that need).
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

    if analysis_type in _PRINT_VALUE_ANALYSIS_TYPES:
        scale_name = None
        scale = None
        values = parse_ngspice_print_values(_read_full_ngspice_log(result))
        output_file_str = None
    else:
        output_text = output_file.read_text() if output_file.exists() else ""
        parsed = parse_ngspice_wrdata(output_text, outputs, analysis_type)
        scale_name = parsed["scale_name"]
        scale = parsed["scale"]
        values = parsed["values"]
        output_file_str = str(output_file)

    return {
        "provenance": "SIMULATED",
        "scale_name": scale_name,
        "scale": scale,
        "values": values,
        "simulator": result.simulator,
        "status": result.status,
        "workdir": str(result.workdir),
        "netlist_file": str(netlist_file),
        "output_file": output_file_str,
    }


def _read_full_ngspice_log(result: SimulationResult) -> str:
    """Return the complete text of the batch-mode log NgspiceSimulator.run()
    already wrote to disk, re-reading it from "log_file" rather than trusting
    "log" (capped to its last 8000 characters -- see that method's own
    citation) -- see run_ngspice_simulation()'s own docstring for why this
    matters for `.PZ`/`.SENS`. Falls back to the capped "log" text only if
    "log_file" is somehow absent or has since been removed."""
    log_file = result.outputs.get("log_file")
    if log_file and Path(log_file).exists():
        return Path(log_file).read_text(errors="replace")
    return result.outputs.get("log", "")
