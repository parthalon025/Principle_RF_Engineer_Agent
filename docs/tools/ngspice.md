# ngspice

ngspice is a free, open-source circuit-level SPICE simulator — a program
that predicts voltage and current in an electronic circuit (a matching
network, an amplifier's bias network, a filter) from a text description of
its parts and wiring, before anything is built. This repo uses it as one of
two "solve the lumped-element circuitry around an EM surface" options
(alongside Xyce, `simulation/xyce.py`) so the agent can check a bias or
matching network without a paid tool like Keysight ADS.

## What it is

ngspice descends from Berkeley SPICE3f5 (1993) and merges three
originally-separate packages: the Spice3f5 analog engine itself, Cider (a
device-physics-level simulator from UC Berkeley), and XSPICE (Georgia Tech's
event-driven digital/mixed-signal extension) [1][2]. It is maintained by a
community team (credited on Wikipedia as "Holger Vogt, Giles Atkinson, Brian
Taylor, Dietmar Warning e.a.," over 67 contributors historically) and
distributed through SourceForge and a GitHub mirror, `ngspice/ngspice` [2].
The current stable release is **ngspice-47** (11 Aug 2026), which this
repo's own adapter has already run against a real binary end to end (see
below) [3]. There is no separate purchase or license fee — it is free to
download, modify and redistribute.

## Full capabilities

Beyond `.OP` (bias point), `.AC` (small-signal frequency sweep) and `.TRAN`
(time-domain/nonlinear transient) — the three this repo wires up — ngspice's
own `ANALYSES` file also lists `.DC` (parametric sweep), `.NOISE`
(small-signal and transient noise), `.DISTO` (small-signal distortion),
`.PZ` (pole-zero), `.SENS` (DC/AC sensitivity), `.TF` (transfer function),
and an experimental `.PSS` (periodic steady state) [4]. Device models cover
R/L/C/transmission lines through diodes, BJTs, JFETs and MOSFETs, plus
Verilog-A compact device models via the bundled ADMS compiler [2]. XSPICE
adds over 60 built-in behavioral "code models" (summers, multipliers,
integrators, limiters, S-domain transfer functions, digital gates/latches, a
generic digital state machine) and interfaces to external Verilog/VHDL
simulators (Icarus Verilog/Verilator, GHDL) for true mixed analog-digital
co-simulation [1][2]. Performance-wise, ngspice supports OpenMP
multi-threading for device-model evaluation (roughly a 2x speedup, since the
matrix solver itself is not parallelized) and an optional KLU sparse direct
solver reported to run up to ~100x faster than the older "Sparse 1.3" solver
on suitable netlists [5].

**S-parameters:** stable ngspice has **no built-in S-parameter analysis** —
confirmed both by this repo's own primary-source research (recorded in
`simulation/ngspice.py`'s docstring) and independently in this pass, via the
GitHub `master` branch's `ANALYSES` file (no `.SP` entry) and the Qucs-S
project's own documentation, which states plainly that "S-parameter two port
RF and microwave circuit simulation is not implemented in traditional SPICE
2g6 and 3f5 simulators" and works around it with AC-analysis probes instead
[4][6]. A native `.SP` command (S/Y/Z-parameter output, arbitrary port
count, syntax mirroring `.AC`) was discussed as an experimental
development-branch feature in 2022 ngspice-devel mailing-list threads, but
is not present in the mainline `ANALYSES` listing fetched directly here [7].
(Wikipedia's ngspice article states ngspice supports "S-parameter analysis"
[2]; that claim conflicts with both the primary `ANALYSES` file and the
Qucs-S documentation, so it is treated here as unconfirmed rather than
authoritative.)

## Integrations & interfaces

ngspice ships as a command-line binary with two modes: **batch** (`-b`,
non-interactive, everything driven from a netlist file, diagnostics to a log
file via `-o`) and **interactive**, plus a separate companion program,
**ngnutmeg**, that reads ngspice's raw output and plots/post-processes it on
a graphics display [8][9]. It has no native network-API or Python-library
binding of its own; third-party wrappers such as spicelib (used by this
repo's `simulation/ltspice.py`) can drive it as one of several supported
back ends, but this repo's own adapter shells out to the `ngspice` binary
directly instead.

## Licensing & cost

ngspice mixes licenses by subtree, preserved from each merged package's
original terms rather than collapsed into one blanket license: the core
Spice3f5 engine is **3-clause ("new") BSD**; Cider is **old BSD**; the
`numparam` and `adms` subtrees and `tclspice` are **LGPLv2**; XSPICE is
**public domain** — confirmed directly from the project's own `COPYING` file
on GitHub [10]. All of it is free of charge and free to redistribute; the
project's stated policy is to keep GPL-licensed contributions out of direct
linking (permitted only in separate shared libraries) to preserve this mix
[10].

## How this repo uses it today

`simulation/ngspice.py`'s `NgspiceSimulator.run()` shells out to
`ngspice -b -o <logfile> <netlist>` (batch mode), resolving the binary from
an explicit path, the `NGSPICE_BIN` env var, or the plain `ngspice` name,
and raises this repo's `SimulatorError` on a nonzero exit or timeout.
`generate_ngspice_netlist()` builds a netlist from a structured job dict —
R/L/C/V/I components via the shared `simulation/spice_netlist.py` helpers,
plus a `raw_cards` escape hatch for anything else (semiconductor devices,
subcircuits) since this repo deliberately does not generate SPICE
model-parameter syntax itself — and emits a `.control` block that runs
`op`/`ac`/`tran` and writes results with `wrdata` (one shared scale column,
via `set wr_singlescale`, plus one value column per output, or a
real/imaginary pair per output for AC). `parse_ngspice_wrdata()` reads that
plain-ASCII file back into a `{scale, scale_name, values}` dict, tolerating
stray non-numeric lines. `run_ngspice_simulation()` ties the three together
and returns a dict tagged `"provenance": "SIMULATED"`. Per the module's own
verification note, a real ngspice-47 binary was run end to end against a
plain RC low-pass filter's `.AC` sweep and matched the filter's known
physics; `.TRAN`/`.OP` and the `raw_cards` path remain format-verified
against documentation only, not yet run against a real binary. `.DC` sweep
and S-parameters are explicitly not implemented in this pass (Xyce's native
`.LIN` analysis, wired up in `simulation/xyce.py`, is this repo's actual
S-parameter path).

## Capabilities not yet used here

- **`.NOISE`, `.DISTO`, `.PZ`, `.SENS`, `.TF` analyses** [4] — noise figure
  and distortion analysis would be directly useful for an active
  amplifier/LNA sub-circuit behind an EM surface, but only `.OP`/`.AC`/`.TRAN`
  are wired up.
- **XSPICE behavioral code models and Verilog/VHDL co-simulation** [1][2] —
  useful for a controller driving a tunable/reconfigurable metasurface
  (e.g. varactor-bias switching logic), but this repo's adapter only
  generates plain R/L/C/V/I cards plus opaque `raw_cards`.
- **KLU sparse solver / OpenMP device-model parallelism** [5] — relevant
  mainly for large nonlinear networks, not the small matching/filter
  circuits this repo currently targets, so not yet exposed as a switch.
- **Interactive mode and `ngnutmeg` plotting** [8][9] — deliberately unused;
  this repo drives ngspice headlessly and does its own result plotting/
  interpretation downstream.

None of this is periodic/unit-cell metamaterial or full-wave field
capability — ngspice is a lumped-element circuit simulator with no notion of
periodic boundary conditions or curved/conformal geometry; that need is
covered elsewhere in this repo (openEMS, HFSS, etc.), not by ngspice.
Compared to its two circuit-sim siblings here: **Xyce** (`simulation/xyce.py`)
is Sandia's from-scratch, MPI-parallel rewrite built for large circuits
across many processors and natively computes S-parameters via `.LIN` [11];
**LTspice** (`simulation/ltspice.py`) is ADI's free-of-charge but
closed-source engine with a bundled vendor macro-model library and a `.net`
S/Y/Z/H-parameter statement, no native Linux build. ngspice's niche among
the three is: fully open source (unlike LTspice), simplest to script
directly without MPI/parallel infrastructure (unlike Xyce), and the widest
device/analysis-type coverage of small-to-medium single-machine circuits.

## Sources

- [1] https://ngspice.sourceforge.io/xspice.html and
  https://ngspice.sourceforge.io/presentation.html — attempted direct
  WebFetch, both returned HTTP 403 in this session; content corroborated via
  search-engine summary of the pages' own text instead.
- [2] https://en.wikipedia.org/wiki/Ngspice — fetched directly; corroborating
  secondary source for history/maintainers/license/capabilities, not a
  primary ngspice-project source, and its "S-parameter analysis" claim is
  flagged above as conflicting with the primary sources checked.
- [3] version/date via search-engine summary referencing ngspice's own
  SourceForge news feed and GitHub mirror (`github.com/ngspice/ngspice`'s
  Releases page itself returned "There aren't any releases here" on direct
  fetch — ngspice publishes releases via SourceForge, not GitHub Releases);
  also independently corroborated by `simulation/ngspice.py`'s own
  verification note (real ngspice-47 binary run 2026-09-04).
- [4] https://raw.githubusercontent.com/ngspice/ngspice/master/ANALYSES —
  fetched directly.
- [5] via search-engine summary of ngspice-devel mailing-list threads
  (sourceforge.net/p/ngspice/discussion) and academic papers on ngspice's
  OpenMP and KLU-solver work; not independently re-fetched as primary text
  in this pass.
- [6] https://qucs-s-help.readthedocs.io/en/legacy/RF.html — fetched
  directly.
- [7] via search-engine summary of ngspice-devel/SourceForge discussion
  threads on the experimental native `.SP` patch; not independently
  re-fetched as primary text in this pass.
- [8] https://ngspice.sourceforge.io — attempted direct WebFetch, returned
  HTTP 403; not independently re-verified by direct fetch this pass (this
  repo's own `simulation/ngspice.py` docstring separately cites the
  nmg.gitlab.io manual mirror directly for the `-b`/`-o` batch-mode flags).
- [9] via search-engine summary of ngspice/ngnutmeg documentation and
  third-party ngspice-usage pages (cppsim.com, layouteditor.org, Arch Linux
  man pages) describing ngnutmeg as ngspice's separate interactive
  plotting/post-processing companion program.
- [10] https://raw.githubusercontent.com/ngspice/ngspice/master/COPYING —
  fetched directly.
- [11] `docs/tools/ltspice.md` (this repo, already-researched sibling
  simulator) and `simulation/xyce.py`'s own module docstring, for the
  Xyce/LTspice comparison points.
- `simulation/ngspice.py`, `simulation/base.py`, `simulation/spice_netlist.py`
  and `policies/tool_policy.yaml` — read directly from this repo.
