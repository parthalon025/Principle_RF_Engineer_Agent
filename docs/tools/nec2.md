# NEC2++

NEC2++ is a free, open-source rewrite in C++ of NEC-2 (the "Numerical
Electromagnetics Code," version 2) — a 1981 US-government-funded program that
solves for the currents induced on thin wires and predicts the antenna
patterns, feed-point impedance, and gain that result, using a technique
called the **method of moments** (MoM): instead of meshing a 3D volume like a
full-wave field solver, MoM turns the antenna's geometry into a 1D current
problem along wire segments and solves a matrix equation for how much current
flows in each segment [3][6]. This repo uses it as its lightest-weight
full-wave-accurate check: MoM is exact for the thin-wire structures it
supports and orders of magnitude cheaper than a 3D mesh solver like openEMS
or Palace, so it is the "fast solver" step called for in this project's
evaluate-cheap-before-expensive method for wire-like elements (dipoles,
loops, patch feed probes modeled as wires, meander-line unit-cell edges).

## What it is

The original NEC2 was written in FORTRAN by Gerald Burke and Andrew Poggio
at Lawrence Livermore National Laboratory under US Navy funding and
documented in a three-part 1981 technical report — "Numerical
Electromagnetics Code (NEC)-Method of Moments: Part 1, Program
Description-Theory; Part 2, Program Description-Code; Part 3, User's Guide"
[1][2]. NEC2++ ("necpp") is a from-scratch C++ port of that program,
maintained by Timothy C.A. Molteno (University of Otago) at
`github.com/tmolteno/necpp` [4]. The repo's own `CMakeLists.txt` currently
declares version **2.3.4** [4], and its `README.md`/`CHANGELOG.md` show
ongoing maintenance (37 KB of changelog history as of this research).

## Full capabilities

Confirmed by reading the necpp source directly (cloned from GitHub for this
research): geometry cards cover straight wires (`GW`), arcs (`GA`), helices
(`GH`), structure move/replicate (`GM`), rotation into a surface of
revolution (`GR`), mirror symmetry (`GX`), and flat conducting surface
patches (`SP`/`SM`/`SC`) — not just wires [4, `src/c_geometry.cpp`]. Ground
modeling (`GN` card) supports free space, an ideal/perfect-conductor ground,
a fast reflection-coefficient approximation for finite ground, and a full
numerical **Sommerfeld/Norton ground-wave integral** (the physically exact
but slow way of accounting for a lossy real-earth ground), plus an optional
radial-wire ground screen and a second ground medium — the Sommerfeld
integral routines (`gshank`, `rom1`, `saoa`) are implemented in
`src/c_evlcom.cpp`/`src/c_ggrid.cpp` [4]. Excitation (`EX` card) is not
limited to a voltage-fed antenna: it also supports an incident **plane wave**
(linear, or right/left circular polarization) and an elementary current
source [4, `src/common.h`] — i.e. it can illuminate a structure and read off
scattered/reflected fields, not only drive it as a transmitter. Loading
(`LD`) adds lumped or distributed R/L/C and finite wire conductivity;
`TL`/`NT` cards model transmission lines and lumped networks. Outputs include
near-field E/H at arbitrary points, far-field radiation patterns (vertical/
horizontal/total gain, axial ratio, tilt, complex E-theta/E-phi), per-segment
current and feed-point impedance/admittance, and a power budget. It scales to
tens of thousands of segments (64-bit address space limit) and does its own
geometry-error checking (throws on intersecting/too-close wires) [4].

## Integrations & interfaces

Standalone CLI binary (`nec2++`), a C library (`libnecpp.h`), a C++ API
(`nec_context.h`), and SWIG-generated Python/Ruby bindings (a separate
`python-necpp` package, itself wrapped by a third-party Julia package) [4,
`docs/mainpage.dox`]. This repo only uses the CLI binary.

## Licensing & cost

Free. The cloned repository's `COPYING` file is the **GNU General Public
License, version 2** (June 1991) verbatim [4] — confirmed by reading the file
directly rather than trusting a secondary summary (a PyPI listing for the
separate `necpp` Python wrapper package states "GPL-3.0-only" [5], a
discrepancy worth flagging since it does not match the core engine's own
`COPYING`).

## How this repo uses it today

`simulation/nec2pp.py` implements `Nec2ppSimulator(Simulator)` — the shared
`run(job) -> SimulationResult` interface in `simulation/base.py` — plus three
free functions. `Nec2ppSimulator.run()` shells out to `nec2++ -i <file> -o -`,
a CLI contract verified against necpp's own `nec2cpp.cpp` (`-i` is mandatory;
`-o -` is required to get results on stdout instead of a `.out` file) (lines
24-59). `generate_nec2_deck()` emits only `GW` wire geometry, `GN`/`GE` ground
(free-space, perfect, or reflection-coefficient finite — never the Sommerfeld
option), a single `EX` card (voltage-source, the default, or a linear-polarized
plane wave — see below), one `FR` frequency point, and one `RP` pattern request
(lines 115-263, `EX` card selection issue #271). `parse_nec2_output()` reads
back the "ANTENNA INPUT PARAMETERS" (impedance/admittance/power at the fed
segment) and "RADIATION PATTERNS" tables into structured dicts (lines 279-359).
`run_nec2_simulation()` orchestrates deck-write, run, and parse, tagging the
result `SIMULATED` (lines 362-399). The module's own header comment states
plainly that no real `nec2++` binary was available in the dev environment, so
this path is verified against the documented output format and a fake test
binary, not against a real run — "unverified end-to-end until it has been run
against the real tool at least once" (lines 95-102).

## Capabilities not yet used here

**Plane-wave excitation, linear polarization, is now implemented** (issue
#271): `generate_nec2_deck()`'s `geometry["excitation"]` dict takes an
optional `"type"` of `"voltage"` (default, unchanged) or `"plane_wave"`,
emitting an `EX 1 ...` card (necpp's `EXCITATION_LINEAR`) with theta/phi
angle counts and first-theta/first-phi/polarization-eta/theta-step/phi-step
fields, skipping the voltage path's feed-segment defaulting (a plane wave
has no feed segment). This closes the most consequential prior gap: since
the whole program exists to predict a surface's *reflection phase*,
plane-wave illumination plus the far-field phase readback
`parse_nec2_output()` already extracted is now producible from a single
`generate_nec2_deck()`/`run_nec2_simulation()` call, for a wire-grid model
characterized as a passive reflector/scatterer rather than only as a driven
antenna. Still open: right/left circular plane-wave polarization (`I1=2`/
`3`, the axial-ratio field) — out of scope for #271. Also unused: the
Sommerfeld ground option (only the cheap approximation is wired up);
arc/helix/patch geometry cards (only straight wires); `LD` loading (no
lossy/finite-conductivity wires or matching networks); `TL`/`NT` networks;
true multi-point frequency sweeps (the deck generator always emits
`NFRQ=1`); and the full per-segment current-distribution/near-field
outputs, which the parser never reads.

## Sources

- [1] https://ui.adsabs.harvard.edu/abs/1981STIN...8122263B/abstract — ADS record for Burke & Poggio's original 1981 NEC report (title, parts, authorship)
- [2] https://ntrl.ntis.gov/NTRL/dashboard/searchResults/titleDetail/ADA956129.xhtml — NTIS technical-report record for the same 1981 NEC document
- [3] https://www.nec2.org/ — nec2.org, "What is NEC2?" (method-of-moments description, LLNL/Navy origin, 1981)
- [4] https://github.com/tmolteno/necpp — necpp repository, cloned locally for this research (`README.md`, `COPYING`, `CMakeLists.txt`, `nec2++.1`, `docs/mainpage.dox`, and `src/*.cpp`/`*.h` read directly)
- [5] https://pypi.org/project/necpp/ — PyPI listing for the `necpp` Python wrapper package (version, stated license)
- [6] https://en.wikipedia.org/wiki/Method_of_moments_(electromagnetics) — general description of the method-of-moments technique NEC2 implements
- `simulation/nec2pp.py` and `simulation/base.py` (this repo) — current adapter implementation and `Simulator` interface
