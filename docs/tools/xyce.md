# Xyce

Xyce (pronounced "zice," rhyming with "spice") is a free, open-source circuit
simulator from Sandia National Laboratories — the U.S. national lab that
built it starting in 1999 to run huge circuit models (think: an entire power
grid or millions of transistors) split across many computers at once, the
way a weather model is split across a supercomputer [1][2]. In plain terms:
it does the same basic job as the well-known SPICE simulators (predicting
voltages and currents in a circuit made of resistors, capacitors, inductors,
sources and — elsewhere in Xyce's own library, though not yet wired into
this repo — transistors and diodes), but it was built from scratch to keep
working, and keep being fast, on circuits too large for a laptop to chew
through in one thread. This repo uses it, alongside the smaller/simpler
ngspice adapter, to simulate the lumped-element circuits behind an antenna
design — an impedance-matching network, a bias network for an amplifier, a
filter — without needing a paid tool like Keysight ADS, and specifically to
extract S-parameters (a standard way of describing how a component reflects
and passes a signal at each frequency) natively, which ngspice's stable
release cannot do on its own.

## What it is

Xyce is "an open source, SPICE-compatible, high-performance analog circuit
simulator... capable of solving extremely large circuit problems by
supporting large-scale parallel computing platforms" [1]. It is developed
and maintained by Sandia National Laboratories, funded by the National
Nuclear Security Administration's Advanced Simulation and Computing program,
and — despite SPICE compatibility as "a primary design goal" — it "is not a
derivative of SPICE" but was "designed and written from scratch in C++,"
built on Sandia's own Trilinos solver library and a differential-algebraic
equation (DAE) formulation that decouples device models from analysis type
[2]. The current release is **7.10** (GitHub, released 21 Jul, per the
project's release page) [3].

## Full capabilities

- **Analyses**: DC operating point, transient, AC (frequency-domain small
  signal), noise, Harmonic Balance (HB, for periodic steady-state/nonlinear
  RF problems), Multi-Time PDE, and model-order reduction methods [2]; plus
  sensitivity analysis, uncertainty-propagation/random-sampling analysis,
  and post-processing via `.FOUR` (Fourier) and `.MEASURE` [3].
- **Native linear-network analysis**: a `.LIN` analysis extracts
  S-/Y-/Z-parameters directly from a netlist via Port devices, writing a
  Touchstone file — a capability ngspice's stable release lacks (this
  module's own docstring, citing Xyce Reference Guide §2.1.17/§2.3.11).
- **Parallel/large-scale**: MPI-based, running on "serial, shared-memory and
  distributed-memory parallel systems" with demonstrated scaling "out to
  hundreds of processors" for circuits with up to millions of devices [1][2].
  This is Xyce's stated differentiator versus ngspice and LTspice — neither
  is built for multi-machine parallel solves [4].
- **Device models**: SPICE3f5-compatible model set plus VBIC and FBH bipolar
  transistor models, several BSIM and PSP MOSFET generations, VDMOS power
  MOSFETs, neuron and reaction-network behavioral models, and custom
  Verilog-A models compiled via ADMS [2][3].
- **Netlist compatibility**: SPICE-like syntax with Xyce-specific extensions
  (e.g. `.LIN`, `YLIN` behavioral N-port import, `.HB`); an XDM netlist
  translator converts between SPICE dialects for PDK portability [3].
- Applications documented beyond conventional circuits include neural
  networks and power-grid modeling [1][3].

## Integrations & interfaces

Xyce is invoked as a standalone command-line binary (`Xyce <netlist>`), the
same invocation model as ngspice/LTspice. It is distributed as binary
installers for Mac, Windows and Linux (the installers additionally bundle
some proprietary device models not present in the open-source GitHub
version) and via the Spack package manager; source is on GitHub with
development discussed on a Google Group and GitHub Discussions [3]. No
Python/TCL scripting interface was found documented on the pages fetched for
this report.

## Licensing & cost

GNU General Public License, version 3 (GPLv3), confirmed by fetching the
license text directly from the official repository — "GNU GENERAL PUBLIC
LICENSE Version 3, 29 June 2007" [5]. Free to use, modify and redistribute
under GPLv3 terms; no purchase cost.

## How this repo uses it today

`simulation/xyce.py` wires up:

- **`XyceSimulator.run()`** — a thin `Simulator` subclass (per
  `simulation/base.py`'s common interface) that shells out to
  `Xyce <netlist_file>` (via `subprocess.run`, no CLI flags), captures
  stdout/stderr, and raises `SimulatorError` on nonzero exit or timeout.
  Deliberately passes no `-o`/`-r`/`-a`/`-l` flags — every output file is
  instead named via each dot-command's own `FILE=` argument, sidestepping a
  documented `-o`-overrides-`.LIN`-`FILE=` interaction (module docstring).
- **`generate_xyce_netlist()`** — builds a netlist from a structured job
  dict: R/L/C/V/I components (via `simulation/spice_netlist.py`, shared with
  the ngspice adapter), optional Port devices plus a `.LIN` line (triggers
  S-parameter extraction when `job["ports"]` is given and
  `analysis.type == "ac"`), a `raw_cards` escape hatch, and one of
  `.OP`/`.AC`/`.TRAN`/`.HB` plus an optional `.PRINT ... FORMAT=CSV` line.
  `.HB` (Harmonic Balance — the periodic steady-state of a nonlinear
  circuit, e.g. a driven mixer or an amplifier at real large-signal power,
  rather than the small-signal wiggle `.AC` linearizes around one bias
  point) takes a job dict `analysis["fundamental_freqs_hz"]` list of one or
  more frequencies (Hz) — one value for single-tone HB, several for
  multi-tone. `.PRINT HB FORMAT=CSV` round-trips through the same
  `parse_xyce_csv()` path as `.AC`/`.TRAN` output (issue #282) — though a
  real Xyce run's `.PRINT HB` documents writing TWO output files
  (frequency- and time-domain) where `.AC`/`.TRAN` write one, a nuance this
  adapter does not yet model (see `simulation/xyce.py`'s header docstring
  "HONEST SCOPE NOTE ON `.PRINT HB`'s TWO OUTPUT FILES").
- **`parse_xyce_csv()`** — parses `.PRINT`'s CSV output into
  `{scale_name, scale, values}`.
- **`run_xyce_simulation()`** — the end-to-end entry point: writes the
  netlist, runs it, parses the `.PRINT` CSV and/or reads the `.LIN`
  Touchstone file back with `skrf.Network()` (mirroring how
  `simulation/openems.py` surfaces computed S-parameters), and returns a
  dict tagged `"provenance": "SIMULATED"`.

Explicitly NOT implemented: `.OP`-only results (Xyce sends bias-point data
to the log only, not a `.PRINT`-able output, per the Reference Guide, so no
CSV parsing is attempted for that case); any semiconductor-device/`.MODEL`
generation (structured support is R/L/C/V/I only, same scope note as the
ngspice adapter); noise, sensitivity, or Multi-Time PDE analyses (only
`op`/`ac`/`tran`/`hb` are exposed). The module's own docstring additionally
flags that the real `Xyce` binary was not installed in the dev environment
(`which Xyce` / `which xyce` both exit 1), so netlist generation and output
parsing — especially the `.LIN` S-parameter path — are built to the
documented format but unverified end-to-end against a real run.

## Capabilities not yet used here

- **Noise analysis** — relevant to amplifier bias-network trade studies but
  not wired up.
- **Sensitivity / uncertainty-propagation (random sampling) analysis** —
  could support the program's "what if this assumed value is wrong"
  warnings (CLAUDE.md's warning discipline) on a matching-network parameter,
  but isn't invoked.
- **Semiconductor device models** (BSIM/PSP MOSFETs, VBIC/FBH bipolars,
  Verilog-A via ADMS) — the adapter only emits passive R/L/C/V/I plus Port
  devices; an active-device amplifier bias network can't be modeled through
  this adapter today.
- **MPI parallel execution** — the adapter always invokes the plain
  `Xyce <netlist>` serial form; nothing here launches `mpirun`/`mpiexec`,
  so Xyce's core stated differentiator (large-scale parallel solves) is
  unused. For the circuit sizes this repo deals with (matching/bias/filter
  sub-circuits, not million-device systems) this is likely a reasonable
  scope choice rather than a gap.
- **XDM netlist translator** — for pulling in PDK/foundry SPICE netlists in
  other dialects — not used; this repo builds netlists from its own
  structured job dicts instead.

## Sources

- [1] https://xyce.sandia.gov (Xyce homepage — what it is, license, current
  version, platforms, purpose)
- [2] https://xyce.sandia.gov/about-xyce/ (About Xyce — analysis methods,
  device models, parallel computing, SPICE-compatibility design philosophy)
- [3] https://github.com/Xyce/Xyce (official GitHub repo — capabilities incl.
  `.HB`, sensitivity/sampling analysis, `.FOUR`/`.MEASURE`, device models,
  XDM translator, distribution channels, current release 7.10)
- [4] Web search results summarizing Xyce's parallel/large-scale niche vs.
  ngspice and LTspice (search: "Xyce Sandia circuit simulator parallel
  large-scale niche compared to ngspice LTspice")
- [5] https://raw.githubusercontent.com/Xyce/Xyce/master/COPYING (official
  GPLv3 license text)
- `simulation/xyce.py` (this repo's adapter, read in full for "How this repo
  uses it today" and its own cited Xyce Reference Guide SAND2023-13759 v7.8
  section/page references)
