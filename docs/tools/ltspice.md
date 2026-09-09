# LTspice

LTspice is a free-of-charge circuit-level SPICE simulator, schematic-capture
editor, and waveform viewer from Analog Devices (ADI) — in plain terms, a
program that predicts what voltage and current will do in an electrical
circuit (a bias network, a matching network, a filter) before it is ever
built, given a text description of the parts and how they connect. This repo
does not use LTspice's own drawing/graphical part of the program; it drives
LTspice's separate "batch mode" — the same simulation engine run
non-interactively from the command line on a pre-written text netlist,
producing a binary results file — so the model can check the lumped-element
electronics (bias networks, matching sections) around an EM surface design
without a person opening a window.

## What it is

LTspice was created by Mike Engelhardt at Linear Technology Corporation and
has been developed and distributed by Analog Devices since ADI acquired
Linear Technology in 2017 [1][2]. It bundles three things: a SPICE
simulation engine with ADI's own performance and convergence enhancements
("enhancements to Spice have made simulating switching regulators extremely
fast"), a graphical schematic-capture front end, and an integrated waveform
viewer for exploring results (traces, math on traces, and Fourier/FFT
analysis) [1]. The latest release found via Analog Devices' own update feed
is version 26.0.2.1 (5 Jul 2026), part of the "LTspice 26" line that added
native Arm-processor support in 26.0.0 (1 Dec 2025) [3]. It ships native
installers for Windows and macOS; there is no native Linux build — Linux use
runs the Windows build under Wine, and ADI's own release notes and user
reports say newer LTspice24+ builds are no longer reliable under Wine [4].

## Full capabilities

Beyond basic transient/AC/DC-operating-point/DC-sweep/noise analyses, LTspice
supports a `.net` statement that extracts two-port Y-, Z-, H- and
S-parameters (reflection/transmission coefficients) directly from a
netlist built around a driven port and a loaded port [5] — the same kind of
network-parameter output this repo's Xyce adapter gets from Xyce's native
`.LIN` analysis. It ships a large bundled macro-model library of ADI/Linear
Technology op-amps, voltage regulators, references and MOSFETs, plus support
for arbitrary behavioral sources and `.MEAS` post-processing directives, and
its schematic editor can export a netlist directly (File > Export Netlist)
for use outside the GUI [1].

## Integrations & interfaces

This repo does not call LTspice directly; it goes through **spicelib**
(GPLv3, by Nuno Brum), a Python toolkit that drives LTspice, ngspice, QSPICE
and Xyce through one API and additionally offers netlist/schematic-file
editing (`SpiceEditor`, `AscEditor`), parallel batch-sweep orchestration
(`SimRunner`), Monte Carlo/worst-case analysis toolkits, `.asc`→`.qsch`
schematic conversion, and `.raw`/log-file readers [6]. **PyLTSpice**, the
older sibling package, is now "mostly based on the spicelib package,"
per its own README, and is a thin LTspice-only convenience wrapper over
spicelib rather than a separate toolchain [7] — which is why
`simulation/ltspice.py` depends on spicelib directly rather than PyLTSpice
(see that module's docstring for the full reasoning).

## Licensing & cost

LTspice is free to download and use but is **not open source**. It is
distributed under Analog Devices' "Click-Through Software License Agreement"
(doc ID `20191031-LTS-CTSLA`) [8][9]: a non-exclusive, non-transferable,
non-sublicensable grant to internally use and copy the software to evaluate
ADI/LTC products and to perform general circuit simulation, per-workstation
for a single concurrent user. It expressly prohibits reverse engineering,
decompiling or disassembling the executables or the bundled device models;
requires unmodified, entirety-only redistribution; carries a reciprocal
royalty-free patent license back to Analog Devices over anything the
licensee builds with it; and disclaims all warranties [8][9]. This makes it
the one non-open-source, non-OSI-approved item among this repo's simulator
integrations — everything else it wires up (ngspice: BSD/LGPL/public-domain
mix; Xyce: GPLv3) is open source, confirmed in `docs/LICENSE_MATRIX.md`.

## How this repo uses it today

`simulation/ltspice.py` wires up exactly LTspice's headless batch mode, not
its GUI. `LtspiceSimulator.run()` resolves an LTspice executable (an explicit
path, the `LTSPICE_BIN` environment variable, or spicelib's own
auto-detected default install location), checks `is_available()`, and shells
out via spicelib's `LTspice.run()`, which itself builds the real
`-Run -b <netlist> [switches]` command line (adding a `wine` wrapper
automatically on Linux/macOS). It reads back the `.raw` binary results file
and `.log` text file LTspice produces alongside the netlist, and raises this
repo's own `SimulatorError` on a nonzero exit code or a missing `.raw` file
rather than letting spicelib's differently-typed exception surface
unmodified. `parse_ltspice_raw()` parses that `.raw` file entirely through
spicelib's own `RawRead` class (trace names, axis, per-trace waveforms —
real or complex for AC results — converted to plain JSON-safe lists), never
re-implementing the binary format itself. `run_ltspice_simulation()` ties
both together end to end and returns a dict tagged `"provenance": "SIMULATED"`.
The module accepts only an already-written SPICE netlist (raw text or an
existing file) — unlike some of this repo's other simulator adapters, it
does not generate a netlist from a structured component-description dict,
on the reasoning that a SPICE netlist is already a natural hand-written or
externally-generated format. spicelib is an optional install extra
(`pip install '.[ltspice]'`), imported lazily so importing the module never
requires it. The module's own docstring records that no real LTspice binary
is installed in this environment, so the invocation mechanics are verified
against spicelib's own upstream source and exercised in tests against a
stub executable, but not yet end-to-end against a real LTspice binary.

## Capabilities not yet used here

- **`.net` two-port S/Y/Z/H-parameter extraction** [5] — the adapter passes
  through whatever netlist and switches the caller supplies, but nothing in
  this repo templates a `.net`-based netlist the way `simulation/xyce.py`
  templates Xyce's `.LIN` analysis, so LTspice's built-in equivalent of a
  filter/matching-network S-parameter sweep is reachable only if a caller
  hand-writes it.
- **spicelib's `SimRunner` parallel batch sweeps and Monte Carlo/worst-case
  toolkits** [6] — useful for a tolerance-sensitivity study of a matching
  network's component values feeding an FSS/absorber unit cell, but
  `run_ltspice_simulation()` only ever runs one netlist at a time.
- **spicelib's `SpiceEditor`/`AscEditor` netlist/schematic editing** [6] —
  not used; this adapter treats the netlist as an opaque, already-finished
  text blob rather than something it can parametrically edit between runs.
- **The bundled vendor macro-model library** (ADI/LTC op-amps, regulators,
  references, MOSFETs) [1] — a real capability of the tool, but this repo's
  component-sourcing tools (Digi-Key/Mouser/Nexar) are the actual part-data
  path; nothing here cross-references LTspice's bundled models against them.
- **Waveform viewer and interactive schematic capture** — deliberately
  unused by design: this repo drives LTspice headlessly.

None of these are periodic/unit-cell metamaterial capabilities — LTspice is
a lumped-element circuit simulator, not a full-wave field solver, so it has
no notion of periodic boundary conditions or curved/conformal geometry at
all; that gap is filled elsewhere in this repo (openEMS, HFSS, etc.), not by
LTspice.

## Sources

- [1] https://www.analog.com/en/resources/design-tools-and-calculators/ltspice-simulator.html — via search-engine summary of the page's own text (direct WebFetch returned HTTP 503 in this session; not independently re-verified by direct fetch)
- [2] https://en.wikipedia.org/wiki/LTspice — corroborating history only (Linear Technology origin, 2017 ADI acquisition); not a primary ADI source
- [3] https://ltspice.analog.com/download/updates.txt — ADI's own version/release-notes feed, fetched directly
- [4] https://ltwiki.org/LTspiceHelpXVII/LTspiceHelp/html/Running_Under_Linux.htm and community reports (WineHQ forum, groups.io LTspice list) on Wine/Linux status, via search-engine summary
- [5] LTspice `.net` two-port network-parameter statement, via search-engine summary of user tutorials/forum material referencing LTspice's own help documentation (not fetched directly from ADI's own help pages in this pass)
- [6] https://github.com/nunobrum/spicelib — fetched directly
- [7] PyLTSpice's own README/docs statement that it is "mostly based on the spicelib package" — as cited in `simulation/ltspice.py`'s module docstring, not independently re-fetched in this pass
- [8] https://ltwiki.org/LTspiceHelpXVII/LTspiceHelp/html/License_Agreement_Disclaimer.htm — fetched directly
- [9] https://ltwiki.org/files/LTspiceHelp.chm/html/License.pdf (doc ID `20191031-LTS-CTSLA`) — via search-engine summary (PDF, not directly fetchable by this session's tools); corroborated by `docs/LICENSE_MATRIX.md`'s own prior citation of the same document
- `simulation/ltspice.py` and `simulation/base.py` — read directly from this repo
