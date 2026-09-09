# MEEP (Meep FDTD)

Meep is a free, open-source full-wave electromagnetics simulator: it solves
Maxwell's equations directly, step by step in time, on a fine 3D grid laid
over the actual geometry, rather than approximating a structure with a
circuit or ray model [1]. "FDTD" (finite-difference time-domain) is the name
for that time-stepping technique. This repo uses Meep as a second, physically
independent way of checking a design's reflection behaviour — chiefly, how
much of a radio wave bounces back off a metasurface (|S11|, "power
reflectance") — computed with a different numerical method (time-domain,
grid-based) than this repo's other full-wave adapter, openEMS, so the two can
catch each other's mistakes rather than repeating the same one
(`simulation/meep.py`, module docstring, line 1: "an independent-method
cross-check against openEMS").

## What it is

Meep — an acronym for "MIT Electromagnetic Equation Propagation" — began as
graduate research at MIT in the mid-2000s (initial contributors Steven G.
Johnson, Ardavan Oskooi, David Roundy, Mihai Ibanescu and Peter Bermel) [2].
It is now maintained by the developer community on GitHub under the
`NanoComp` organization, with Simpetus (a company founded around the
project) providing continued stewardship [1][2]. The current tagged release
is **v1.34.0** (9 July 2026) [3] — the same version this repo's own
validation work (`docs/meep-absorber-validation.md`) was checked against,
per `simulation/meep.py`'s own module docstring. Funding history includes
the U.S. National Science Foundation (including SBIR awards), the Army
Research Office and DARPA [4].

## Full capabilities

Per Meep's own documentation [1][2]: arbitrary material geometry with
anisotropic permittivity ε and permeability μ; dispersive ε(ω)/μ(ω)
including loss or gain; nonlinear (Kerr and Pockels) and gyrotropic media; a
library of predefined broadband complex refractive indices; simulation in
1D/2D/3D and cylindrical coordinates; geometry import from GDS files and, as
of the current release, 3D triangular surface meshes [3]; perfectly matched
layer (PML) absorbing boundaries; Bloch-periodic boundaries (for simulating
one repeating tile of an infinite periodic surface, the technique a
metasurface or frequency-selective-surface unit cell needs) and
perfect-conductor boundaries; near-to-far-field transformation (projecting
computed near fields outward to predict far-field radiation pattern/antenna
gain); mode decomposition; local density of states calculations; a
frequency-domain solver; an adjoint solver for inverse design and topology
optimization; and distributed-memory parallelism over MPI (splitting one
simulation across many CPU cores or machines) [1][2]. A sister project from
the same team, **MPB** (MIT Photonic Bands), is an eigenmode solver — it
finds a periodic structure's resonant frequencies and field patterns
directly in the frequency domain, complementary to Meep's time-domain
approach — also GPLv2, maintained by Simpetus and the GitHub community [5].

## Integrations & interfaces

Meep is a Python **library**, not a command-line tool driven by an input
file: the documented interface is `import meep as mp`, then constructing
`mp.Simulation(...)` objects and calling methods on them
(`simulation/meep.py` docstring, confirmed against
meep.readthedocs.io/en/latest/Python_User_Interface/). It has no PyPI wheel;
the recommended install path is Conda (`conda create -n mp -c conda-forge
pymeep`), with precompiled binaries for Linux/macOS only — native Windows is
unsupported, and Windows users are directed to WSL [6]. It can also be built
from source via GNU Autotools, requiring MPB, Libctl and HDF5 [6].

## Licensing & cost

Meep is licensed under the **GNU GPL version 2** — confirmed directly from
`github.com/NanoComp/meep/blob/master/LICENSE`, opening "GNU GENERAL PUBLIC
LICENSE / Version 2, June 1991 / Copyright (C) 1989, 1991 Free Software
Foundation, Inc." [7]. It is free to use, no licensing fee; this repo
records that GPLv2 status in `docs/LICENSE_MATRIX.md` and, per
`simulation/meep.py`'s docstring, keeps Meep at arm's length via a
subprocess boundary partly for that reason (a side benefit, not the reason
it exists).

## How this repo uses it today (cite `simulation/meep.py`'s functions/behavior)

`MeepSimulator.run()` takes a structured `geometry` dict (cell size, PML
thickness, mesh spacing, up to two axis-aligned primitives — `Block`/box or
`Cylinder` — per material/conductor, a single Gaussian-pulse "port," and
named monitor planes) and calls `_run_reflectance_cross_check()`, which
follows Meep's own documented two-run flux-subtraction recipe: a "reference"
run with only dielectrics (conductors omitted) records a baseline spectrum
and the reflection-plane's field data (`sim.get_flux_data`/
`mp.get_fluxes`); the real run subtracts that data at the same plane
(`sim.load_minus_flux_data`) so the remaining flux is the reflected wave
alone, giving power reflectance `-reflected_flux/baseline_flux` and its
square root, `s11_magnitude`. Materials are isotropic only, with an optional
`loss_tangent` (mapped to Meep's `D_conductivity` at band-centre frequency)
or a conductor stated as `conductivity_s_m`/`sheet_resistance_ohm_sq` +
`thickness_m` instead of the default ideal PEC (`mp.metal`) — `#229`/`#230`
(`_conductor_medium`, `_build_geometry_list`). `periodic_axes` in `geometry`
turns on Bloch-periodic boundaries with `k_point=Vector3()` (normal
incidence only) via `_boundaries_and_k_point`, so unit-cell simulation is
wired up. An optional `transmission_monitor_center_m` (`#240`) adds a
second, non-subtracted flux monitor behind the structure and reports power
transmittance; `1 - R - T` (absorption) is deliberately left uncomputed
(`#243`) — "an adapter reports what it measured, not what it means." An
optional `far_field_monitor` (`#270`) — a closed box of enclosing regions
plus a list of far-field directions — builds Meep's own near-to-far-field
transform (`sim.add_near2far`/`mp.Near2FarRegion`) on the full run and
projects the recorded near fields outward (`sim.get_farfield`) to report
`gain_dbi` (peak antenna gain in dBi among the requested directions) and a
`far_field` result, combining that projection with total radiated power
read from ordinary flux monitors on the same enclosing surface; leaving the
key out builds no near2far monitor at all, same opt-in shape as the
transmission monitor.
Because Meep is imported in-process (`_import_meep()`) but this repo's own
Docker image installs `pymeep` into a separate conda environment from the
application's `uv` venv, `MeepSimulator` also accepts a
`python_executable`/`MEEP_PYTHON` interpreter and, when it differs from the
running one, delegates the whole run as a subprocess via a generated runner
script (`_run_in_meep_interpreter`, `_RUNNER_TEMPLATE`) that calls the
*same* `_run_reflectance_cross_check` function, so the physics exists once
regardless of which path executes it (`#231`). `tests/test_meep.py`
documents that real Meep is genuinely not installed in the application's
normal interpreter and CI runs no solver at all; two verification scripts
have been run against real pymeep 1.34.0 during development but not
automatically.

## Capabilities not yet used here

Against the adapter's own stated `SCOPE`, several documented Meep features
are unused: **complex S-parameters** (only power magnitude is extracted, so
no phase, no complex S21, no multi-port S-matrix, no Touchstone export);
**dispersive material fits** (Meep can fit measured ε(ω) with multiple
poles; this adapter supports only one frequency-independent loss tangent or
conductivity); **nonlinear/gyrotropic materials**; **GDS/mesh geometry
import** (only box/cylinder primitives here); **oblique-incidence k_point
sweeps** (normal incidence only — the module docstring names this
explicitly as an open, approximate flag); **mode decomposition** and **the
adjoint solver for inverse design/topology optimization** (which could let a
unit cell's own geometry be optimized directly against a target
reflectance, rather than only scored after a human proposes it); and
**MPB**, the companion eigenmode solver, is not integrated. Component-
sourcing, filter-synthesis, and literature-ingestion functionality is not
applicable to Meep's category (a field solver).

**Near-to-far-field transformation** — previously this repo's single
biggest gap, since it is exactly the machinery needed to predict antenna
gain/radiation pattern — is now wired up as an opt-in `far_field_monitor`
key (`#270`; see "How this repo uses it today" above), but narrower than
Meep's full capability: gain is reported only at the caller's own requested
directions (not a full-sphere scan, so a true pattern peak the caller never
asked about can be missed), a periodic unit cell's near2far transform uses
Meep's default `nperiods=1` (an infinite array's own lattice-summed pattern
is not computed), and — unlike the reflectance/transmittance recipe, which
has been checked against a real pymeep install — this gain arithmetic rests
on a reasoned-but-not-yet-independently-verified assumption that Meep's
near2far and flux machinery share one absolute scale (see
`simulation/meep.py`'s `FAR_FIELD_VALIDITY`).

## Sources

- [1] https://meep.readthedocs.io/en/latest/ — overview, feature list, maintenance statement
- [2] https://github.com/NanoComp/meep — README overview, maintainer (NanoComp), feature list
- [3] https://github.com/NanoComp/meep/releases — current release v1.34.0 (9 July 2026), release notes
- [4] https://meep.readthedocs.io/en/latest/Acknowledgements/ — maintenance/funding (NSF, Army Research Office, DARPA)
- [5] https://mpb.readthedocs.io/en/latest/ — MPB description, maintainer, license, relationship to Meep
- [6] https://meep.readthedocs.io/en/latest/Installation/ — Conda-first install, no PyPI wheel, no native Windows support
- [7] https://github.com/NanoComp/meep/blob/master/LICENSE — GPLv2 license text
- `/home/user/Principle_RF_Engineer_Agent/simulation/meep.py` — this repo's adapter (module docstring and code read in full)
- `/home/user/Principle_RF_Engineer_Agent/simulation/base.py` — the `Simulator`/`SimulationResult` contract `MeepSimulator` implements
