# Palace

Palace ("**PA**rallel **LA**rge-scale **C**omputational **E**lectromagnetics")
is a free, open-source full-wave 3D electromagnetics solver built by the AWS
Center for Quantum Computing (CQC) [1][2]. "Full-wave" means it solves
Maxwell's equations directly on a 3D mesh of the actual geometry, rather than
approximating with simplified circuit or ray models — the same category of
tool as HFSS or openEMS, just free and built to scale across many computer
cores. This repo uses it for one specific, load-bearing reason: it is the
first EM solver wired up here with native **Floquet/periodic boundary
conditions** — the standard way to simulate one repeating tile ("unit cell")
of an infinite periodic surface instead of the whole surface — which is
exactly what characterizing a metasurface, frequency-selective surface, or
periodic absorber unit cell requires, and neither of this repo's other two
full-wave adapters (NEC2++'s method-of-moments, openEMS's FDTD) expose that
capability (`simulation/palace.py`, module docstring, lines 1-5).

## What it is

Palace is developed and maintained by the Design and Simulation group inside
AWS CQC, reachable at palace-maint@amazon.com per the project's own
documentation [1]. It is a parallel finite-element (FEM) code built on the
MFEM finite-element discretization library and the libCEED library for
efficient high-order/exascale discretizations, using Hypre, SuperLU, and
similar linear-algebra libraries under the hood, and is described by AWS as
delivering "exascale-ready performance on commodity cloud nodes without
license cost" [3][1]. The latest tagged release is **v0.17.0** (29 June
2025); that release specifically added Floquet ports for periodic structures
and 2D simulation support [4].

## Full capabilities

Palace supports five main simulation modes, plus 2D waveguide analysis
[1][2]:

- **Eigenmode** solves — finds a structure's resonant modes, with optional
  material/radiative loss and lumped-impedance boundaries, plus built-in
  energy-participation-ratio (EPR) postprocessing for circuit quantization
  (relevant to superconducting-qubit work, AWS CQC's home domain).
- **Electrostatic** solves — extracts lumped capacitance matrices.
- **Magnetostatic** solves — extracts lumped inductance matrices.
- **Frequency-domain driven** solves — wideband S-parameter response from a
  surface-current excitation, with uniform or adaptive frequency sweeps.
- **Time-domain (transient)** solves — explicit or fully implicit.
- **2D waveguide mode analysis** — propagation constant and characteristic
  impedance of a 2D cross-section.

Numerically it offers arbitrary high-order finite elements, curvilinear
(curved) mesh support, adaptive mesh refinement (AMR) across most modes, and
GPU acceleration on NVIDIA/AMD hardware (CUDA, HIP, MAGMA) with multi-GPU
parallelism, on top of CPU-side matrix-free p-multigrid, sparse direct, and
algebraic-multigrid solvers [2][3]. Boundary conditions include the periodic
and Floquet-port pair this repo uses, plus PEC (now also used here, for
embedded conductor patches — see below) and, not used here, lumped/wave
ports, PMC, absorbing/PML, and surface-impedance boundaries [3][5]. Mesh input
supports MFEM's native format plus Nastran and COMSOL formats, driven by a
JSON configuration file with five top-level sections — Problem, Model,
Domains, Boundaries, Solver — validated against a published JSON Schema
before it runs [6].

## Integrations & interfaces

Palace is a standalone binary/CLI tool, run as
`<INSTALL_DIR>/bin/palace -np <NUM_PROCS> config.json`; the installed
`palace` script wraps whichever MPI launcher is configured (`mpirun` by
default), or the underlying `palace-<arch>.bin` binary can be invoked
directly under a custom MPI launcher [7]. There is no vendor GUI, cloud
service, or paid API — it is source-built or container-installed software
that a caller shells out to and reads result files back from.

## Licensing & cost

Apache License, Version 2.0, confirmed by fetching
`github.com/awslabs/palace/blob/main/LICENSE` directly [8]. Free to use,
modify and redistribute, including commercially; no seat license, unlike
HFSS.

## How this repo uses it today

`simulation/palace.py` implements `PalaceSimulator(Simulator)`
(`simulation/base.py`'s common adapter interface — a `run(job) ->
SimulationResult` contract shared with the NEC2++/openEMS/HFSS adapters).
Concretely, wired up:

- **`generate_palace_mesh()`** builds a structured hexahedral mesh (MFEM
  `.mesh` v1.0 ASCII) of a single rectangular periodic unit cell, with zero
  or more embedded axis-aligned dielectric material boxes, plus zero or more
  embedded axis-aligned PEC conductor patches (`geometry["pec_patches"]`,
  issue #252) — the patterned-metal-on-dielectric case (a patch, slot, or
  ring on/in a substrate) — each meshed as its own interior boundary-attribute
  assignment, distinct from the dielectric material boxes and the six
  unit-cell faces.
- **`generate_palace_config()`** emits the JSON config for a frequency-domain
  **Driven** solve only, with `config["Boundaries"]["Periodic"]` (the
  x/y-normal side faces), two `FloquetPort` entries (the z-normal faces,
  port 1 excited; or one Floquet port plus a PEC-backed ground plane via
  `geometry["ground_backed"]`), and a `config["Boundaries"]["PEC"]` entry
  referencing any `pec_patches` attributes.
- **`PalaceSimulator.run()`** shells out to the real `palace` binary
  (`-np <N> config.json`) via `subprocess`, matching Palace's documented CLI
  contract.
- **`parse_palace_output()`** parses `port-floquet-S.csv`, and
  `run_palace_simulation()` orchestrates mesh + config + run + parse,
  returning results tagged `provenance: "SIMULATED"` plus a power-balance/
  passivity/reciprocity `conservation_check`.

This has been validated against a real built `palace` binary (commit
`43a5483`) on Palace's own "Floquet Ports for a Dielectric Grating" example,
matching Palace's published reference output to within 0.056 dB / 0.91° on
the propagating modes (module docstring, "VALIDATED AGAINST A REAL PALACE
BINARY" section).

Embedded PEC conductor patches (`geometry["pec_patches"]`, issue #252) are
also implemented — meshed as an interior boundary attribute and referenced
by a `config["Boundaries"]["PEC"]` entry — but that geometry has never itself
been run through a real Palace binary, so the exact `"PEC"` config key
name/shape is confirmed only against Palace's own documented schema, not
against a real solve the way `FloquetPort`/`Periodic` were (issue #210).
Validating it against a real binary is tracked separately (issue #347).

**Explicitly NOT implemented**: eigenmode, electrostatic, magnetostatic, and
time-domain solves; non-periodic ports (lumped/wave); adaptive mesh
refinement; GPU execution; curvilinear (curved) mesh elements; and
multi-process values above `num_processes=1` are plumbed through but not
exercised in the validated run.

## Capabilities not yet used here

**Embedded PEC conductor support in the periodic unit cell** — the case most
real metasurface/FSS unit cells actually need (patterned metal: patches,
slots, or rings on or in a dielectric, rather than a bare grating) — used to
be the single biggest gap here; it is now implemented
(`geometry["pec_patches"]`, issue #252) rather than a gap. What remains is
that it has never met a real Palace binary: the only run this module has
validated end to end is an all-dielectric grating with no metal, so whether
the inferred `"PEC"` boundary config actually works is still open (issue
#347). Beyond that: **eigenmode solves** could characterize a
unit cell's resonant behavior directly (useful for absorber/FSS resonance
design) instead of only reading it off a driven S-parameter sweep;
**electrostatic/magnetostatic** solves are irrelevant to this repo's RF work;
**adaptive mesh refinement** and **curvilinear meshing** would let a curved,
conformal (as opposed to flat, axis-aligned-box) unit-cell geometry be
represented and converged automatically rather than by the caller's coarse
manual `nx`/`ny`/`nz` subdivision; and **GPU acceleration** would speed up
larger sweeps but is orthogonal to physical capability.

## Sources

- [1] https://awslabs.github.io/palace/stable/ — "Home" page (what Palace is, who maintains it, capability list)
- [2] https://github.com/awslabs/palace — repo README (capabilities, dependencies, GPU support)
- [3] AWS/search-indexed summary of Palace's FEM stack (MFEM/libCEED/Hypre/SuperLU) and "exascale-ready ... without license cost" framing, surfaced via web search of awslabs.github.io content
- [4] https://github.com/awslabs/palace/releases — release list (v0.17.0, 29 Jun 2025, added Floquet ports)
- [5] https://awslabs.github.io/palace/dev/guide/boundaries/ — Boundary Conditions guide (Floquet ports, periodic BCs, other boundary types)
- [6] https://awslabs.github.io/palace/dev/config/config/ — Configuration File overview (five top-level sections, JSON Schema validation, comment/range syntax)
- [7] https://awslabs.github.io/palace/stable/run/ — "Running Palace" (CLI invocation, MPI launcher wrapping, `-h`/`--help`)
- [8] https://raw.githubusercontent.com/awslabs/palace/main/LICENSE — Apache License, Version 2.0 (fetched and confirmed)
- `simulation/palace.py` and `simulation/base.py` (this repo) — current adapter implementation and Simulator interface
