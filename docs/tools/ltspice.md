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
The module accepts an already-written SPICE netlist (raw text or an
existing file) for the general case — unlike some of this repo's other
simulator adapters, it does not generate a netlist from a structured
component-description dict for every analysis type, on the reasoning that a
SPICE netlist is already a natural hand-written or externally-generated
format. spicelib is an optional install extra (`pip install '.[ltspice]'`),
imported lazily so importing the module never requires it. The module's own
docstring records that no real LTspice binary is installed in this
environment, so the invocation mechanics are verified against spicelib's
own upstream source and exercised in tests against a stub executable, but
not yet end-to-end against a real LTspice binary.

One structured-job-dict generator is carved out of that "hand it a finished
netlist" rule: `generate_ltspice_net_netlist()` templates LTspice's own
`.net` statement — the same two-port S-/Y-/Z-/H-parameter extraction this
file's "Full capabilities" section describes — from a job dict shaped like
`{"components": [...], "ports": [...], "analysis": {...}}`, mirroring
`simulation/xyce.py`'s `generate_xyce_netlist()` job shape as closely as
`.net`'s real syntax allows (each `ports` entry names either the driven
source, `{"role": "input", "name": "V1"}`, or the loaded node/resistor,
`{"role": "output", "kind": "V"|"I", ...}` — `.net` addresses its two ports
by reference to an already-declared source/node/resistor, not via a
repeatable Port-device card the way Xyce's `.LIN` does). `run_ltspice_
simulation()` accepts this job dict through a `job=` parameter (mutually
exclusive with `netlist`/`netlist_file`), generates the netlist, runs it
through the same `LtspiceSimulator` path, and surfaces whatever S11/S21/
S12/S22/Zin/Zout/etc. traces come back via `extract_ltspice_network_
parameters()` — a pure function reading `parse_ltspice_raw()`'s already-
parsed trace dict, added to the result under `network_parameters`. Per the
primary source now cited below, `.net` has no `LINTYPE=`-style selector the
way Xyce's `.LIN` does: one run computes admittance/impedance/Y-/Z-/H-/
S-parameters together, so this generator's job dict has no parameter-type
field to select one. The job dict's `analysis` key must set `"type": "ac"` —
`.net`'s own help page requires it be paired with a `.AC` sweep, and the
generator's `_net_ac_line()` reproduces that statement's exact `lin`/`oct`/
`dec` syntax from ADI's own help content [10].

## Capabilities not yet used here

- **`.net` two-port S/Y/Z/H-parameter extraction — partially closed** [5]:
  `generate_ltspice_net_netlist()` / `run_ltspice_simulation(job=...)` now
  template and run this (see "How this repo uses it today" above), but the
  exact trace-name strings LTspice writes into the `.raw` file for each
  parameter (S11/S21/S12/S22, Zin/Zout/Yin/Yout, and the Y/Z/H equivalents)
  are corroborated only by community sources, not confirmed against a real
  LTspice binary's actual output (none is installed in this environment —
  see "How this repo uses it today" above) — see
  `extract_ltspice_network_parameters()`'s own docstring for the honest
  caveat. What remains genuinely unsupported: 1-port (`Zin`/`Yin`-only)
  jobs are not specifically validated (the generator only checks for an
  input/output pair), and `.net`'s `list`-frequency `.AC` variant
  (`.ac list <freq> [<freq> ...]`) is not exposed — only `lin`/`oct`/`dec`
  sweeps [10], matching `simulation/xyce.py`'s own `.AC` support.
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
- [5] `.net` two-port network-parameter statement — UPDATED (issue #287, 2026-09-09): exact syntax (`.net [V(out[,ref])|I(Rout)] <Vin|Iin> [Rin=<val>] [Rout=<val>]`) and the "computes Y/Z/H/S-parameters together, no selector switch" fact now fetched directly from https://ltwiki.org/LTspiceHelp/LTspiceHelp/_NET_Compute_Network_Parameters_in_a_AC_Analysis.htm (LTwiki's direct HTML mirror of ADI's own bundled LTspiceHelp.chm content — the same "ltwiki.org counts as fetched-directly-primary" precedent source [8] below already relies on). The exact output *trace-name* strings (S11/S21/S12/S22, Zin/Zout/Yin/Yout) are NOT stated on that page; those are corroborated only by several independent LTspice-user community threads (ADI's own EngineerZone forum among them, plus edaboard.com and a sci.electronics.design/Google Groups thread, both via search-engine summary — direct fetch returned HTTP 403 and 429 respectively in this session) describing exactly those names in LTspice's waveform-viewer "Add Traces" dialog after a `.net` run — see `simulation/ltspice.py`'s module docstring and `extract_ltspice_network_parameters()`'s own docstring for the full citation and honest caveat. Superseded the prior citation here, which was a search-engine summary of tutorials/forum material never fetched directly.
- [6] https://github.com/nunobrum/spicelib — fetched directly
- [7] PyLTSpice's own README/docs statement that it is "mostly based on the spicelib package" — as cited in `simulation/ltspice.py`'s module docstring, not independently re-fetched in this pass
- [8] https://ltwiki.org/LTspiceHelpXVII/LTspiceHelp/html/License_Agreement_Disclaimer.htm — fetched directly
- [9] https://ltwiki.org/files/LTspiceHelp.chm/html/License.pdf (doc ID `20191031-LTS-CTSLA`) — via search-engine summary (PDF, not directly fetchable by this session's tools); corroborated by `docs/LICENSE_MATRIX.md`'s own prior citation of the same document
- [10] `.ac <oct, dec, lin> <Nsteps> <StartFreq> <EndFreq>` — fetched directly from https://ltwiki.org/LTspiceHelpXVII/LTspiceHelp/html/AC_Analysis.htm (same LTwiki-mirrors-ADI's-help-content basis as [5]).
- `simulation/ltspice.py` and `simulation/base.py` — read directly from this repo
