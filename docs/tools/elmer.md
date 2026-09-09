# Elmer FEM

Elmer is a free, open-source finite element method (FEM) suite — a numerical
technique that breaks a physical object into many small connected pieces
("elements") and solves the governing equations on that mesh — built to
handle many *kinds* of physics (structural mechanics, fluid flow, heat
transfer, electromagnetics, and more) on one common engine, not an
antenna-specific tool. This repo uses one narrow slice of it: the
`VectorHelmholtz` module, which solves the time-harmonic Maxwell equations (the
physics of an oscillating radio wave) using "edge elements," a finite-element
flavor built specifically so that the electric/magnetic field's direction
along an element's edge stays continuous the way real fields require. Elmer is
wired up here not to replace this repo's antenna-focused solvers for everyday
work, but as a placeholder for a job none of them can do: modeling one
physical part with electromagnetics *and* heat transfer coupled together in
the same run — relevant to a future check of a metasurface "skin" mounted on
a hot surface, not to routine antenna design [1][3].

## What it is

Elmer is developed and maintained by CSC – IT Center for Science (Finland),
with contributions from Finnish universities, research labs, industry, and an
international open-source community; its source lives at
github.com/ElmerCSC/elmerfem, whose `devel` branch is the active default with
over 10,000 commits [1]. Its four components are ElmerSolver (the solve
engine), ElmerGUI (graphical front end), ElmerGrid (mesh conversion/
partitioning), and ElmerPost/ParaView integration for visualization [1][2].
Copyright headers trace to 1995, and the project has run continuously since.
It recently moved from a traditional major.minor version scheme (e.g. `9.0`,
released May 2020) to calendar-based versioning: the latest tagged release is
**v26.2.1** (29 Apr 2026, a small fix to v26.2), with v26.1 (23 Jan 2026,
~3,500 commits since Nov 2020) introducing the new scheme [4]. It runs on
Linux, Windows and macOS and parallelizes via MPI from a laptop up to HPC
clusters [1][5].

## Full capabilities

Beyond electromagnetics, Elmer's solver library covers structural mechanics,
computational fluid dynamics, heat transfer, acoustics, and — as one of its
best-known specialties — glacier/ice-sheet dynamics under the "Elmer/Ice"
name, used by an international glaciology research community [1][6]. It ships
several distinct EM solver modules beyond VectorHelmholtz, including
MagnetoDynamics (low-frequency/quasi-static fields) and circuit-coupling
modules [3][7]. Its defining trait is **coupled multiphysics as a first-class
feature**: any of these solvers can run together against the same mesh in one
model, e.g. an EM solve's ohmic/dielectric losses feeding a heat-transfer
solve as a Joule-heating source, with published induction-heating tutorials
and a proof-of-concept combining current, Joule heating, transient heat and
fluid flow in one run [5][6]. `VectorHelmholtz` itself solves the curl-curl
form of the time-harmonic Maxwell equation, ∇×(1/μ)∇×**E** − iωσ**E** −
ω²ε**E** = iω**J**, using first- or second-degree curl-conforming ("edge" /
H(curl)) elements, with an optional A-V (vector+scalar potential)
formulation, a choice of gauge condition, a Piola-transform option for 2D
models, and Auxiliary-Space-Maxwell-Solver preconditioning for faster solves;
it was written by Juhani Kataja, Juha Ruokolainen, Mika Malinen and Peter
Råback [3].

## Integrations & interfaces

ElmerSolver is a standalone CLI binary, `ElmerSolver [file.sif]`, reading a
plain-text Solver Input File (`.sif`) of `Header`/`Simulation`/`Body`/
`Material`/`Equation`/`Solver`/`Boundary Condition` blocks plus a small MATC
scalar-expression language — no GUI or network service required for scripted
use [3]. Meshing is delegated to external tools this repo also drives: Gmsh
generates the mesh, and ElmerGrid converts it into ElmerSolver's native
format. There is no cloud service or vendor API — same local-binary
integration shape as this repo's other open FEM/FDTD adapters.

## Licensing & cost

Free and open source, no fee, no seat license. Licensing is split: the
ElmerSolver core library and most physical solver modules — including
`VectorHelmholtz.F90` itself, confirmed by its own file header — are
**LGPL v2.1 or later**; ElmerGUI and ElmerGrid are **GPL v2** [2][3]. Note
that Elmer's own plain-language "license policy" page states these two
version numbers backwards ("GPL v2.1 / LGPL v2.0"); the version numbers above
come from the actual bundled license texts and per-file headers, not that
summary [2][3].

## How this repo uses it today

`simulation/elmer.py` implements a mesh-to-solve-to-parse pipeline around
this one module (issue #64): `generate_gmsh_geo_script()` builds a Gmsh
OpenCASCADE script for a single rectangular domain plus an optional
rectangular excitation sub-region; `run_gmsh_meshing()` and
`run_elmergrid_conversion()` shell out to `gmsh` and `ElmerGrid` to produce an
ElmerSolver-native mesh; `generate_elmer_sif()` writes a `.sif` driving
`VectorHelmholtz`/`VectorHelmholtzCalcFields` at one frequency with isotropic
material properties, an impressed-current-source excitation, and either a PEC
wall or the solver's generic absorbing-boundary flag; `ElmerSimulator.run()`
(the `simulation/base.py` `Simulator.run(job) -> SimulationResult` contract)
invokes `ElmerSolver` as a subprocess; and `parse_elmer_output()` reads the
"ALL DONE" completion marker plus any `SaveScalars` output, but *always*
returns `s_parameters`/`far_field` as `computed=False` since VectorHelmholtz
has no native port model or far-field/gain post-processing.
`run_elmer_simulation()` orchestrates the whole pipeline, tagged
`provenance: "SIMULATED"`.

**Coupled EM+thermal (issue #281) is now built.** An optional
`geometry["thermal"]` block (bulk heat conductivity/density/heat capacity,
plus per-face fixed-temperature or convective boundary conditions) makes
`generate_elmer_sif()` add a `Heat Equation` (`HeatSolve`/`HeatSolver`) solver
block alongside the existing `VectorHelmholtz` ones, on the same mesh. The EM
solve's local ohmic/dielectric loss density is wired into the heat solver's
source term with two real Elmer keywords, both confirmed directly from
Elmer's own source rather than guessed by analogy: `Calculate Div of
Poynting Vector = Logical True` on `VectorHelmholtzCalcFields` (which makes
VectorHelmholtz itself export a `"Joule Heating"` field — confirmed in
`VectorHelmholtz.F90`'s own `CalcFieldsLocalAssembly`) and `Joule Heat =
Logical True` on a `Body Force` block (Elmer's own EM-module-agnostic
heat-source flag, confirmed in `Differentials.F90`'s `JouleHeat()` function
and cross-checked against Elmer's own `InductionHeating2`/`3`/`4` tutorial
`.sif` files). `parse_elmer_output()`/`run_elmer_simulation()` surface a
coupled run's peak temperature as a new `thermal_result` field
(`computed=True` with a `max_temperature_k` value when a coupled run's
`SaveScalars` output has a `"max: Temperature"` column, `computed=False` +
an explanatory note otherwise) — the same honestly-gapped shape as
`s_parameters`/`far_field`. Calling the existing entry points with no
`geometry["thermal"]` key is unchanged: no `Heat Equation` block, no `Joule
Heat` keyword, EM-only output. See `simulation/elmer.py`'s module docstring
"COUPLED EM+THERMAL" section for the full citation trail.

Still not implemented: calibrated ports, S-parameters or far-field; curved,
multi-material, or multi-region geometry; periodic/Floquet unit-cell
boundaries; and any non-EM, non-heat Elmer solver (structural, CFD,
MagnetoDynamics, circuit coupling). None of gmsh/ElmerGrid/ElmerSolver is
installed in this environment; the pipeline (EM-only and coupled) is
exercised only against fake test scripts, per the module's own "HONEST
CAVEAT."

## Capabilities not yet used here

Coupled EM+thermal multiphysics — the single biggest gap named in earlier
research passes, and the actual stated reason this adapter exists — is now
implemented (see above); this section covers what is still unused. Elmer's
other EM modules (MagnetoDynamics, circuit coupling) go unused; its
structural and CFD solvers are irrelevant to RF work but relevant to a
genuine mechanical cross-check of a mounted skin. No periodic/Floquet
unit-cell boundary condition is wired up, so — unlike this repo's Palace
adapter — Elmer cannot today characterize a metasurface/FSS unit cell, this
repo's core use case. Curved/conformal geometry, multi-material layering,
and calibrated port/S-parameter extraction remain absent from both the
geometry model and the post-processing, gaps the module's own docstring
already names. The new thermal boundary-condition model itself is limited to
two types (a fixed-temperature Dirichlet face, or a convective/Robin face
with a heat-transfer coefficient and ambient temperature) — Elmer's
radiation boundary condition (`Radiation = Diffuse Gray`, used in its own
`InductionHeating2` tutorial) is not wired up here. Also unbuilt: iterative/
transient coupling for temperature-dependent material properties (this
module's coupled mode runs one steady-state iteration, EM then heat, in that
order — correct when material properties don't depend on temperature, but
not a general two-way-coupled solve).

## Sources

- [1] https://github.com/ElmerCSC/elmerfem — official repository (README: what Elmer is, capabilities, maintenance, commit history)
- [2] https://raw.githubusercontent.com/ElmerCSC/elmerfem/devel/license_texts/ElmerLicensePolicy.md — Elmer's own license-policy summary (GPL vs. LGPL component breakdown; version numbers here are stated backwards relative to [3])
- [3] https://github.com/ElmerCSC/elmerfem/blob/devel/fem/src/modules/VectorHelmholtz.F90 — VectorHelmholtz source (LGPL v2.1 file header; curl-curl equation, edge elements, A-V/Piola/AMS details, authorship; `.sif` block structure)
- [4] https://github.com/ElmerCSC/elmerfem/releases — release history (v26.2.1, v26.2, v26.1, 9.0 versions and dates)
- [5] https://www.csc.fi/en/web/elmer — CSC's own Elmer page (maintainer identity, applications, webinar program)
- [6] https://csc.fi/en/news/elmer-versatile-multiphysical-modeling/ — CSC news piece (module list including Elmer/Ice, multiphysics framing)
- [7] https://github.com/ElmerCSC/elmerfem/blob/devel/fem/src/modules/EMWaveSolver.F90 — sibling EM solver module (confirms VectorHelmholtz is one of several distinct EM modules, not Elmer's only one)
- [8] https://github.com/ElmerCSC/elmerfem/blob/devel/fem/src/Differentials.F90 — `JouleHeat()` function (issue #281): confirms the `Joule Heat = Logical True` Body Force flag and its `'Joule Heating e'` field-name lookup, EM-module-agnostic
- [9] https://github.com/ElmerCSC/elmerfem/blob/devel/fem/src/DiffuseConvectiveGeneralAnisotropic.F90 — confirms `JouleHeat()` is called from the generic diffusion-convection RHS assembly `HeatSolve.F90` itself uses
- [10] https://github.com/ElmerCSC/elmerfem/blob/devel/fem/src/modules/HeatSolve.F90 — `Heat Conductivity`/`Density`/`Heat Capacity` Material keywords and `Temperature`/`Heat Transfer Coefficient`/`External Temperature` boundary-condition keywords, read directly (issue #281)
- [11] https://github.com/ElmerCSC/elmerfem/blob/devel/fem/src/modules/SaveData/SaveScalars.F90 — `Variable N`/`Operator N` keywords and the `TRIM(Oper0)//': '//TRIM(VariableName)` column-naming rule that produces `"max: Temperature"` (issue #281)
- [12] https://github.com/ElmerCSC/elmerfem/blob/devel/fem/tests/InductionHeating2/crucible.sif (and `InductionHeating3`/`InductionHeating4`, same directory pattern) — Elmer's own worked induction-heating tutorial cases, cross-checked to confirm `Joule Heat = Logical True` is Elmer's standard, EM-module-independent coupling idiom (issue #281)
- `simulation/elmer.py`, `simulation/base.py` (this repo) — current adapter implementation and `Simulator` interface
- Note: https://elmerfem.org/ and https://elmerfem.org/blog/ (Elmer's official project site) returned HTTP 403 Forbidden when fetched directly during this research pass and could not be consulted; the claims above rely on the GitHub and CSC sources instead.
