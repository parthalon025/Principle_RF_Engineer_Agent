# gprMax

gprMax is a free, open-source **FDTD** electromagnetic simulator — "FDTD"
(Finite-Difference Time-Domain) means it chops space into a 3-D grid of tiny
cells and time into tiny steps, then marches Maxwell's equations forward
cell-by-cell, step-by-step, the same brute-force-but-exact family of method
openEMS (also in this repo) uses [1][2]. It was built for Ground Penetrating
Radar (GPR) — simulating radar pulses bouncing off buried objects in lossy,
messy ground — but the solver itself is general-purpose electromagnetics, and
the maintainers now advertise it as running "from GPR to antennas and
bioelectromagnetics" [3]. This repo uses it for exactly the GPR-shaped part of
that range: NEC2++ (`simulation/nec2pp.py`) only offers idealized ground
models (free space, a perfect ground plane, or a one-parameter Sommerfeld
approximation), and openEMS's adapter here has no explicit ground-half-space
workflow either — so gprMax is this repo's only wired-up option for a real
volumetric lossy dielectric half-space (soil, concrete, a vehicle hull, human
tissue) that a near-ground or embedded antenna actually couples into
(`simulation/gprmax.py`, module docstring, "WHAT THIS ADAPTER IS FOR").

## What it is

gprMax is developed by researchers in the School of Engineering at the
University of Edinburgh and the School of Engineering, Physics, and
Mathematics at Northumbria University, led by Craig Warren and Antonis
Giannopoulos (copyright notice spans 2015–2026 on the project's own site,
implying continued maintenance) [3]. It is cited to Warren, Giannopoulos &
Giannakis (2016), *Computer Physics Communications* [2]. Its most recent
tagged GitHub release is **v.3.1.7** ("Big Smoke"), dated 3 January 2024;
public discussion also references a **v4 ("Carn Mor")** that was reportedly
near-ready as of mid-2024, but this research pass did not confirm a v4 tag on
the release list [4][5]. Development happens on GitHub under the `gprMax/gprMax`
org, with documentation split between a "latest" (stable) branch and an active
development branch [1].

## Full capabilities

- **FDTD solver**, written in Python 3 with performance-critical inner loops
  in Cython, solving full 3-D Maxwell's equations with PML absorbing
  boundaries [1][2].
- **Material models**: simple non-dispersive materials (`#material`: relative
  permittivity, conductivity in S/m, relative permeability, magnetic loss in
  Ω/m) plus three dispersive formulations — **Debye** (multi-pole relaxation,
  e.g. water), **Lorentz** (resonant/dielectric-resonance behavior), and
  **Drude** (free-electron conductive materials) — added via
  `#add_dispersion_debye/_lorentz/_drude` [6].
- **Soil/heterogeneous modelling**: `#soil_peplinski`, a published
  sand/clay/water-fraction soil-mixing model valid 0.3–1.3 GHz, composable
  with `#fractal_box` for spatially-randomized, geometrically realistic soil
  or rough-surface volumes [6].
- **Bundled antenna library** (`user_libs/antennas/`): ready-made models of
  specific commercial GPR antenna housings — GSSI 1.5 GHz and 400 MHz units,
  MALA 1.2 GHz unit — each a fixed geometry (casing, absorber, shielding,
  PCB, bowtie) calibrated to one real product, licensed separately under
  **Creative Commons Attribution-ShareAlike 4.0 International**, not gprMax's
  own core license [confirmed by fetching `user_libs/antennas/GSSI.py`
  directly] [7].
- **Acceleration**: OpenMP for shared-memory multi-core CPU; MPI as a task
  farm to distribute independent model runs (and combinable with GPU
  execution to spread jobs across multiple cards); and an NVIDIA
  CUDA-based GPU solver reported "up to 30 times faster" than the OpenMP CPU
  path on a typical desktop CPU [8].
- **Interfaces**: a plain-text `#command`-based `.in` input-file format, that
  same format extended with embedded Python (constants, variables, functions)
  for parametric/scripted model construction, and a direct Python API
  (`gprMax.gprMax.api(...)`) for programmatic model building [1].
- **Geometry primitives**: `#box`, `#cylinder`, `#plate`, `#edge`, with later
  commands overwriting earlier ones' material in any overlapping cell (a
  "layered canvas" build order) [6].
- **Sources/probes**: `#hertzian_dipole`, `#voltage_source`, and
  `#transmission_line` excitations; `#rx` field probes reading any of
  Ex/Ey/Ez/Hx/Hy/Hz/Ix/Iy/Iz [6].

## Integrations & interfaces

gprMax has **no standalone console-script executable** — its own `setup.py`
defines no `console_scripts` entry point — so it is always invoked as
`python -m gprMax path/to/model.in [options]` through some Python interpreter
[9]. It is **not installable from PyPI**: a direct query to PyPI's JSON API
for both `gprMax` and `gprmax` returned HTTP 404 for both names during this
research pass, confirming the module's own documented finding. The official
install path is conda (`conda env create -f conda_env.yml`) plus a C compiler
with OpenMP support, then a local `setup.py build && setup.py install` step
that compiles Cython extensions — there is no pure-`pip install` route [9].
Results are written as an HDF5 `.out` file (input filename + `.out`
appended, not an extension swap), with root attributes (`dt`,
`Iterations`, grid spacing) plus per-receiver (`/rxs/rxN/`) and
per-transmission-line (`/tls/tlN/`: `Vinc`/`Iinc`/`Vtotal`/`Itotal`) datasets
[10].

## Licensing & cost

**GNU General Public License v3 or later (GPLv3+)**, confirmed by fetching
the repo's `LICENSE` file directly (opens "GNU GENERAL PUBLIC LICENSE,
Version 3, 29 June 2007") and matching the README's own statement and
`setup.py`'s OSI classifier [3][9]. It is free to use, modify, and
redistribute, including commercially, with no seat license or paid tier;
the official site explicitly labels it "Free under GPLv3" [3]. The bundled
GSSI/MALA antenna-housing models carry a separate CC-BY-SA-4.0 license,
distinct from the GPLv3+ core [7].

## How this repo uses it today

`simulation/gprmax.py` implements `GprmaxSimulator(Simulator)`
(`simulation/base.py`'s shared `run(job) -> SimulationResult` interface).
Concretely wired up:

- **`GprmaxSimulator.run()`** shells out to `python -m gprMax <input_file>
  [extra_args]` via `subprocess` (never a "gprmax" binary, since none
  exists), keeping stdout tail-truncated for diagnostics only — gprMax's own
  console output is just a progress bar and timing lines, not something this
  adapter parses.
- **`generate_gprmax_input()`** builds a `.in` deck from structured
  geometry/materials/port/receivers input: `#domain`, `#dx_dy_dz`,
  `#time_window`, optional `#pml_cells`/`#num_threads`, an optional
  **`half_space`** field emitting a uniform lossy-dielectric ground fill
  (`#material` + full-footprint `#box`) — the feature this adapter exists
  for — plus caller-supplied `materials` (dielectric bodies) and
  `conductors` (PEC, via gprMax's reserved `pec` identifier), and exactly
  **one** `#transmission_line`-fed port with its Gaussian `#waveform`. Both
  `half_space` and any `materials` entry may also carry an optional
  `dispersion` field (issue #277), emitted as the matching
  `#add_dispersion_debye`/`_lorentz`/`_drude` command immediately after
  that material's `#material` line — the frequency-dependent counterpart
  to the plain-`#material` case, for absorber/ferrite/FSS-substrate
  modelling.
- **`parse_gprmax_output()`** reads the `.out` HDF5 file's `/tls/tl1/`
  Vinc/Vtotal/Itotal dumps and computes S11(f) and Zin(f) by FFT
  (`_compute_s_and_z_from_tl()`), reproducing gprMax's own official
  `tools/plot_antenna_params.py` formula (Vref = Vtotal − Vinc,
  S11 = FFT(Vref)/FFT(Vinc), Zin = FFT(Vtotal)·delaycorrection/FFT(Itotal)),
  and optionally writes a Touchstone `.s1p` via `skrf`.
- **`run_gprmax_simulation()`** orchestrates deck generation, the run, and
  parsing, returning `provenance: "SIMULATED"` results.

**Explicitly NOT implemented/stubbed**: gprMax's bundled GSSI/MALA antenna
models (deliberately — this repo simulates the caller's own geometry, not one
commercial housing); `#soil_peplinski`/`#fractal_box` randomized-soil
modelling (`half_space` is uniform only); B-scans (`-n` > 1,
`#src_steps`/`#rx_steps`) and GPU/MPI execution (always a single CPU run);
multi-port S-parameter extraction or `#hertzian_dipole`/`#voltage_source`
excitation (only one `#transmission_line` port); and any near-field-to-far-
field transform or gain/pattern extraction (`far_field` is always
`{"computed": False, ...}` — gprMax has no such tool at all, unlike openEMS's
separate nf2ff utility). The module's own header also flags that gprMax is
not installed in this environment and cannot be via a simple `pip`/`uv`
command (it needs conda plus a C/OpenMP compiler), so this adapter is
exercised only against a fake `python -m gprMax` script and hand-built
synthetic `.out` files, not a real gprMax run.

## Capabilities not yet used here

**Dispersive material models** (`#add_dispersion_debye/_lorentz/_drude`) [6]
were this section's single most significant gap as of this report's original
research pass, and are now wired up (issue #277): both the `half_space`
ground fill and any `materials` entry accept an optional `dispersion` field,
emitted as the matching `#add_dispersion_*` command right after that
material's `#material` line, letting the adapter model an absorber, ferrite,
or frequency-selective-surface substrate that is lossy at one band and
nearly transparent at another — instead of only the flat, frequency-
independent `#material` approximation. Still unused: **GPU (CUDA) and MPI
acceleration**, which could speed up or parallelize the sweeps this repo's
scoring loop needs; **`#soil_peplinski` + `#fractal_box`** for a realistic
(non-uniform) lossy ground, useful for buried/embedded antenna work closer
to gprMax's original GPR domain than this repo's flat-surface metasurface
focus; and multi-port/`#hertzian_dipole` excitation for coupling or array
studies. None of gprMax's own capabilities address periodic/unit-cell
metamaterial characterization, filter synthesis, component sourcing, or
literature ingestion — those are out of this tool's category and are
handled by other adapters (e.g. Palace for Floquet/periodic boundaries) in
this repo.

## Sources

- [1] https://docs.gprmax.com/en/latest/ — official documentation home (architecture, interfaces, application scope)
- [2] https://github.com/gprMax/gprMax — repo README summary (what it is, FDTD method, citation: Warren, Giannopoulos & Giannakis 2016, *Computer Physics Communications*)
- [3] https://gprmax.org/ (redirected from https://www.gprmax.com/) — official site (maintainers: University of Edinburgh / Northumbria University, "Free under GPLv3", "from GPR to antennas and bioelectromagnetics", copyright 2015-2026)
- [4] https://github.com/gprMax/gprMax/tags — release tag list (latest: v.3.1.7, 3 Jan 2024)
- [5] Web search on gprMax v4 "Carn Mor" release status (June 2024 near-ready reference; no confirmed v4 tag found in this pass)
- [6] https://github.com/gprMax/gprMax/blob/master/docs/source/input.rst — input-file command reference (`#material`, dispersion commands, `#soil_peplinski`, `#fractal_box`, geometry primitives, sources/receivers)
- [7] https://raw.githubusercontent.com/gprMax/gprMax/master/user_libs/antennas/GSSI.py — bundled GSSI antenna models and their CC-BY-SA-4.0 license header
- [8] Web search of https://github.com/gprMax/gprMax/blob/master/docs/source/openmp_mpi.rst and https://docs.gprmax.com/en/latest/gpu.html content — OpenMP/MPI/CUDA acceleration details
- [9] https://raw.githubusercontent.com/gprMax/gprMax/master/README.rst — installation (conda + C/OpenMP compiler, no pip package), invocation (`python -m gprMax`), license statement
- [10] `simulation/gprmax.py` module docstring — HDF5 `.out` structure and S-parameter/impedance extraction formula, citing `docs/source/output.rst` and `tools/plot_antenna_params.py` (not independently re-fetched in this pass; cited as already verified in the adapter's own header)
- `simulation/gprmax.py` and `simulation/base.py` (this repo) — current adapter implementation and Simulator interface
