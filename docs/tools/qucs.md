# Qucs-S / qucsator_rf

Qucs-S is a free, open-source circuit simulator: draw a circuit as a netlist
(a text list of components and how they're wired together, no physical
3-D shape involved), tell it what to sweep, and it computes voltages,
currents, or — the thing this repo actually asks it for — S-parameters,
the standard way of describing how much of a signal a circuit reflects
back versus lets through, at every frequency in the sweep. It is the
free/GPL alternative to a paid tool like Keysight ADS for the
"how does this matching network or filter behave" question that sits
downstream of a full 3-D electromagnetic solve: once a metasurface
element's behavior is known (from `simulation/openems.py` or
`simulation/hfss.py`), Qucs-S/qucsator_rf is where a lumped-element
matching network or filter built around that element gets checked
cheaply, in a circuit-theory sense, before spending full-wave solver time.

## What it is

Qucs-S ("Quite Universal Circuit Simulator - with SPICE") is a Qt-based
graphical front end for circuit simulation, maintained by ra3xdh as a fork
of the original Qucs project [1][6]. It does not simulate anything itself;
it drives one of several simulation *kernels* (engines) and adds schematic
capture, plotting, and result-display tooling on top [1]. `qucsator_rf` is
one of those kernels: a "command line driven circuit simulator targeted for
RF and microwave circuits" that "accepts network lists as input and
produces Qucs XML datasets" [2] — it is the native, non-SPICE engine that
survives from the original pre-fork Qucs/Qucsator project, kept alive
specifically for RF/microwave work, while Qucs-S itself is "the recommended
GUI for both tools" [2]. The most recent tagged release is Qucs-S 26.1.1,
published 2026-04-26 [3].

## Full capabilities

Qucs-S can drive four simulation kernels: its own native `qucsator_rf`
(non-SPICE), and three SPICE-family engines — ngspice (the recommended
default), Xyce, and SpiceOpus [1][6]. Across these backends the documented
analysis types include DC operating point, AC (small-signal frequency
sweep), transient (time-domain), S-parameter, harmonic-balance (a
frequency-domain method for finding a circuit's steady-state response
under strong nonlinear drive — used for oscillators/mixers/amplifiers
driven hard enough that a simple AC sweep isn't valid), noise analysis,
parameter sweeps, and an interactive "tuning mode" for dragging a component
value and watching the plot update live [4][5]. `qucsator_rf` itself
natively supports multi-port S-parameter analysis (any number of ports in
one run, not just 1- or 2-port) and harmonic balance [2][4]. It ships a
library of transmission-line models — microstrip, coaxial, twisted-pair,
coplanar, and waveguide — that reference substrate material properties for
more realistic RF modeling than an ideal wire [4]. Qucs-S also includes a
Tools → Filter Synthesis wizard that computes LC/ladder/stepped-impedance/
microstrip/active filter element values from a target response and can
paste the resulting schematic straight onto the canvas [7][8], plus
dedicated RF result-display graph types — Smith chart, admittance Smith
chart, and polar/complex-plane plots — for reading reflection coefficients
and impedances directly instead of raw real/imaginary numbers [4].

## Integrations & interfaces

The GUI (Qucs-S) is schematic-driven: place components and a source, add
an "S-Parameter Simulation" block, simulate, and view results on a plot or
Smith chart [4]. Underneath, `qucsator_rf` is a plain command-line
program: it takes a text netlist and writes a "Qucs Dataset" text file,
with no GUI or config-file dependency required for a batch/scripted run
(confirmed directly from its `src/ucs.cpp` entry point) [2]. The netlist
format is line-oriented — one component per line as
`Type:InstanceName node1 node2 Key="Value" ...` — and the dataset output
format brackets each result vector as `<indep NAME COUNT>...</indep>` or
`<dep NAME dep-on...>...</dep>` blocks of numbers, one value per line.

## Licensing & cost

Both Qucs-S and qucsator_rf are free of charge and licensed GPL-2.0 (each
source file in ra3xdh/qucs_s carries the standard GPLv2 "or (at your
option) any later version" header; the repository's own `COPYING` file is
the plain GPLv2 text) [9]. There is no paid tier, seat license, or usage
restriction — unlike the licensed EM solvers this repo also wraps.

## How this repo uses it today

`simulation/qucs.py` wires up exactly one corner of `qucsator_rf`: the
native multi-port `.SP` (S-parameter) analysis, nothing else.

- `QucsSimulator.run()` (lines 19-76) is the common `Simulator` interface
  (`simulation/base.py`'s `run(job) -> SimulationResult`) implementation:
  it shells out to the `qucsator_rf` binary (`QUCSATOR_BIN` env var or
  `qucsator_rf` on `PATH`) as `qucsator_rf -i <netlist> -o <dataset>`,
  raises `SimulatorError` on a nonzero exit or a missing output file, and
  returns the raw dataset text plus captured stdout/stderr.
- `generate_qucs_netlist()` (lines 276-381) builds a netlist from a
  structured Python dict — only four component types are supported:
  `R`, `L`, `C`, and `TLIN` (an *ideal*, non-dispersive transmission line;
  its phase is computed from vacuum light-speed, so it does not model a
  real microstrip trace's slower effective velocity). Ports become `Pac`
  (AC power source) components. Only the linear/logarithmic swept `.SP`
  directive is generated — the list/constant sweep forms qucsator_rf also
  supports are not.
  Nothing else — transistors, `qucsator_rf`'s own microstrip/MLIN element,
  transformers, transient, harmonic balance, DC, AC, or noise analysis
  (`Noise="no"` is always hardcoded) — is generated.
- `parse_qucs_dataset()` (lines 403-470) parses only the `frequency`
  independent vector and `S[i,j]` dependent vectors out of the dataset
  text; any other result vector a real run might contain is ignored.
- `run_qucs_simulation()` (lines 522-579) chains the three steps above,
  tags the result `"provenance": "SIMULATED"`, and — when every S[i,j] for
  a contiguous 1..N port numbering was recovered — writes a Touchstone
  `.sNp` file via `skrf` for downstream tools like
  `rf_tools/correlation.py`.

The module's own header comment is explicit that the real `qucsator_rf`
binary was not installed in the implementing environment, so this parsing
and generation logic is verified against the tool's cited source files and
a real sample netlist fixture, not against an actual run — "treat any
result as unverified end-to-end until it has been run against the real
tool at least once."

`policies/tool_policy.yaml` lists `run_qucs_simulation` as free/open-source
software needing no per-run approval gate, alongside NEC2++ and openEMS.

## Capabilities not yet used here

The adapter uses one analysis (`.SP`) out of qucsator_rf's documented set
(DC, AC, transient, harmonic balance, S-parameter, noise) [4][5], and four
component types out of dozens the engine ships. Most relevant to this
repo's actual work — thin conformal EM surfaces, patch antennas,
frequency-selective surfaces, absorbers:

- **Filter synthesis wizard** — Qucs-S's Tools → Filter Synthesis
  generates a filter schematic (LC, ladder, stepped-impedance, microstrip,
  active) from a target response [7][8]; this repo hand-builds R/L/C/TLIN
  netlists in Python instead of driving this synthesis directly.
- **qucsator_rf's own dispersive microstrip/MLIN and other real
  transmission-line models** (coaxial, coplanar, waveguide, substrate-aware)
  [4] — the adapter's `TLIN` is an ideal, non-dispersive line, so any real
  microstrip matching-network trace currently needs its electrical length
  pre-computed outside this module.
- **Transistors, transformers, and other active/nonlinear device models**
  qucsator_rf ships — useful for active-circuit designs this repo does not
  yet target, but out of scope for the passive matching/filter work the
  adapter currently does.
- **Harmonic balance and noise analysis** — not generated or parsed at
  all; relevant if a future requirement needs a nonlinear (active) surface
  element or a noise-figure figure of merit.
- **Smith-chart / polar result display** [4] — a GUI-only feature with no
  batch-mode analogue, not applicable to this repo's headless use.

## Sources

- [1] https://github.com/ra3xdh/qucs_s — repository README (fetched)
- [2] https://github.com/ra3xdh/qucsator_rf — repository README (fetched)
- [3] https://api.github.com/repos/ra3xdh/qucs_s/releases/latest — latest release metadata (fetched)
- [4] https://qucs-s-help.readthedocs.io/en/latest/overview/simulation-types/rf.html — official Qucs-S docs, RF simulation page (fetched)
- [5] https://qucs-s-help.readthedocs.io/en/latest/overview/simulation-types/index.html — official Qucs-S docs, simulation types overview (fetched)
- [6] https://raw.githubusercontent.com/ra3xdh/qucs_s/master/README.md — repository README raw text (fetched)
- [7] WebSearch results for `"Qucs-S" filter synthesis wizard matching circuit Smith chart tool`, including https://github.com/ra3xdh/qucs_s/releases/tag/2.1.0 (fetched via search)
- [8] https://denki-sim.blog/en/filter-synthesis_guide_en/ — third-party Qucs filter-synthesis walkthrough, corroborating the Tools → Filter Synthesis wizard (via search snippet, not independently fetched)
- [9] https://raw.githubusercontent.com/ra3xdh/qucs_s/master/COPYING — repository license file (fetched)
- `simulation/qucs.py` (this repo) — adapter source and its own inline citations to `ra3xdh/qucsator_rf` source files (`src/ucs.cpp`, `src/spsolver.cpp`, `src/dataset.cpp`, `src/components/*.cpp`)
