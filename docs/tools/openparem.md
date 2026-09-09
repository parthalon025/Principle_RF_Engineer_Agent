# OpenParEM

OpenParEM3D is a free, open-source "full-wave" 3D electromagnetic solver —
"full-wave" meaning it solves Maxwell's equations directly on a mesh of the
actual 3D geometry, the same rigorous category as HFSS, rather than
approximating with a simplified circuit model. From one solve it produces
both the scattering parameters (S-parameters — how much signal reflects vs.
passes through, the standard number for a filter, port, or antenna feed)
between defined "wave ports," and, for antennas, the far-field numbers a
decision-maker actually cares about: gain, directivity, and radiation
efficiency [1][2]. This repo integrates it alongside NEC2++
(method-of-moments), openEMS (FDTD), Palace (periodic unit cells), and HFSS
(commercial) specifically to get antenna far-field metrics out of a free
FEM solver without an AEDT license.

## What it is

OpenParEM ("**Open** **Par**allel **E**lectro**m**agnetic") is a solver
suite of two programs — OpenParEM2D (2D waveguide/transmission-line
cross-sections: propagation constants, characteristic impedance, losses) and
OpenParEM3D (general 3D structures) — built by a single named author, Brian
Young, per the copyright header repeated atop every source file [3][4]. It
is young: the project's own revision log records "version 1.0.1 [9-18-24]:
Initial release," "version 2.0.0 [3-6-25]: Added antenna performance metrics
[and] upgraded adaptive mesh refinement," and the current "version 2.1.0
[5-1-25]: Re-organized the code base... Added a binary build... Upgraded
libraries" (Hypre, PETSc, Metis, MFEM) [5], with a matching `2.1.0` GitHub
tag [6]. That is roughly a year of public existence versus decades for
HFSS/openEMS/NEC2++ — a maturity gap this repo's adapter treats as a
first-class caveat, not a footnote (see below).

## Full capabilities

OpenParEM3D solves "the frequency-dependent vector electric and magnetic
fields of general 3D structures and post-processes the fields to produce
scattering parameters (S-parameters) between 2D wave ports and radiation
patterns, gain, directivity, and radiation efficiency for antennas" [1].
Boundary conditions: perfect electric/magnetic conductor (PEC/PMC), surface
impedance (with a surface-roughness correction for how a rough real-world
metal loses more power than a mathematically smooth one), and 1st-order
radiation (an open-space boundary for antenna problems) [1][7]. It uses
arbitrary-order finite elements (the polynomial degree approximating the
field inside each mesh element — higher order needs a coarser mesh for the
same accuracy), adaptive mesh refinement (the mesh automatically densifies
where the solver's own error estimate is high) driven by relative-S and
absolute-H error tolerances, and MPI parallel processing across CPU cores
[1][7]. Materials are frequency-dependent text entries — a Debye dispersion
model or explicit permittivity/loss-tangent/conductivity per frequency
point, each required to cite its source in a "Source/EndSource" block [7] —
a provenance habit this repo's own evidence-tier system will recognize.
Explicitly *not* supported: GPU computing, "so OpenParEM3D is not configured
for GPU processing" since its methodology uses fully populated matrices
[7]. Its published validation cases include a dipole, a square monopole,
and a conductor-backed patch antenna, compared against published
measurements — not just internal self-consistency [7].

## Integrations & interfaces

OpenParEM3D is command-line only: `OpenParEM3D my_project.proj` (serial) or
`mpirun -q --oversubscribe -np N OpenParEM3D my_project.proj` (parallel), a
single positional `.proj` file argument [8]. Critically, it is *not* a
self-contained tool: "OpenParEM is a command-line tool for running
electromagnetic simulations only. Pre- and post-processing must be handled
by other tools... Assembling a tool flow is a very significant task" [8].
Its documented flow is FreeCAD (CAD) + gmsh (meshing, msh22 format only —
"OpenParEM only works with the msh22 format of gmsh due to library
limitations") + ParaView (viewing) [8]. Results land in plain-text/CSV
files the caller reads back (`_results.csv` for S-parameters,
`_FarField_results.csv` for antenna metrics, `.s<N>p` Touchstone) — no
library API. A separate helper, `builder`, can generate some setup files
from a simpler keyword description, though gmsh meshing stays manual [7].

## Licensing & cost

GPL-3.0-or-later, confirmed from the identical header on every source file
and the repository's own `LICENSE` file (standard GPLv3 text) [3][9]. Free
to use, modify, and redistribute, including commercially; no seat license
or subscription, unlike HFSS or CST. The project's own site, openparem.org,
was attempted for this doc but returned only a bot-verification
interstitial ("One moment, please... Please wait while your request is
being verified") on every fetch — no additional cost/support/roadmap claims
from that source could be confirmed either way.

## How this repo uses it today

`simulation/openparem.py` implements `OpenParemSimulator(Simulator)`, the
same `run(job) -> SimulationResult` contract as this repo's other simulator
adapters (`simulation/base.py`). Concretely: **`OpenParemSimulator.run()`**
shells out to the real `OpenParEM3D` binary (serial or `mpirun`, matching
the CLI contract above) and treats a nonzero exit as failure;
**`generate_openparem_project_config()`** writes the `.proj` file
(frequency plan, mesh order/refinement/quality, reference impedance,
Touchstone format, and the `antenna.plot.3D.pattern q=G|D` line that
requests far-field gain or directivity); **`generate_openparem_ports_file()`**
writes the ports/boundary definition file (`Path`/`Boundary`/`Port`/
`Mode`/`IntegrationPath` blocks); **`parse_openparem_output()`** reads back
`_results.csv` (S-parameters, from whichever of RI/mag-deg/dB-deg column
format was requested) and `_FarField_results.csv` (`gain_dbi`/
`directivity_dbi`/`radiation_efficiency`, unit-labeled since gain/
directivity are dB but efficiency is a linear 0-1 fraction); and
**`run_openparem_simulation()`** orchestrates all of it, returning results
tagged `provenance: "SIMULATED"`.

What it does **not** do: generate the 3D mesh (an externally supplied msh22
file is required — matching OpenParEM's own "user assembles a tool flow"
architecture), generate materials property files (only the `.proj` keywords
pointing to them), or emit 2D angular-cut patterns or ParaView pattern
exports (`antenna.plot.2D.pattern`, `antenna.plot.3D.save`) — only the
scalar gain/directivity/efficiency request is wired up. The module's own
docstring states plainly that the real `OpenParEM3D` binary is not
installed in this environment (`which OpenParEM3D` exits 1) and that
generation/parsing has only been exercised against a fake stand-in script
in tests, never a real FEM solve — every result from this adapter is
unverified end-to-end until it is run against the real tool at least once,
a caution this repo weighs more heavily here given OpenParEM's roughly
one-year public history.

## Capabilities not yet used here

The single biggest gap for this repo's purpose (thin conformal
metasurfaces, patch antennas, absorbers) is **mesh and materials-file
generation itself**: a caller must hand this adapter an already-meshed
msh22 file and already-written materials library, both produced entirely
outside this codebase via a manually assembled FreeCAD+gmsh flow — no
design this program proposes can reach an OpenParEM3D result without a
human doing that assembly by hand first. Beyond that: **`antenna.plot.2D.pattern`**
(a full angular radiation-pattern cut, not just scalar peak numbers) and
the ParaView-consumable 3D pattern/current exports would let a candidate's
actual radiation shape be inspected rather than only its summary numbers;
and the **`builder`** helper (keyword-driven generation of some setup
files) is unused — this adapter regenerates `.proj`/ports-file text
directly. OpenParEM has no periodic/Floquet unit-cell capability at all
(Palace fills that gap in this repo; see `docs/tools/palace.md`).

## Sources

- [1] https://github.com/OpenParEM/OpenParEM — repository README (project
  identity, OpenParEM2D/3D scope, capability summary, license statement)
- [2] https://github.com/OpenParEM/OpenParEM/blob/main/doc/OpenParEM3D_Theory_Methodology_Accuracy.tex
  — "Introduction" (FEM/MFEM methodology, GPU-processing statement, boundary
  conditions, validation cases against published measurements)
- [3] https://github.com/OpenParEM/OpenParEM/blob/main/src/OpenParEM3D/project.c
  — verbatim GPL-3.0-or-later header, author/copyright attribution
- [4] https://github.com/OpenParEM/OpenParEM/blob/main/README.md — project
  description, OpenParEM2D/3D split
- [5] https://github.com/OpenParEM/OpenParEM/blob/main/doc/OpenParEM_revisions.tex
  — dated version history (1.0.1 initial release 9-18-24; 2.0.0 antenna
  metrics 3-6-25; 2.1.0 current, 5-1-25)
- [6] https://github.com/OpenParEM/OpenParEM/releases/tag/2.1.0 — current
  release tag (GitHub-recorded publish date differs slightly from the
  revisions log's 5-1-25 date; the revisions log is treated as authoritative
  here as the project's own dated record)
- [7] https://github.com/OpenParEM/OpenParEM/blob/main/doc/OpenParEM3D_Users_Manual.tex
  — materials file format (Debye/frequency-list, Source/EndSource
  citation requirement), mesh-order/AMR/GPU statements, tool-flow
  description, validation-case descriptions (dipole, monopole, patch)
- [8] https://github.com/OpenParEM/OpenParEM/blob/main/doc/Installation_Execution.tex
  — CLI invocation contract, "command-line tool... pre/post-processing
  must be handled by other tools," FreeCAD+gmsh+ParaView flow, msh22 mesh
  format constraint
- [9] https://github.com/OpenParEM/OpenParEM/blob/main/LICENSE — GPLv3
  license text
- https://openparem.org/ — attempted directly; returned only a
  bot-verification interstitial on every fetch during this research, so no
  claims are sourced from it
- `simulation/openparem.py` and `simulation/base.py` (this repo) — current
  adapter implementation, module docstring's own citation trail, and
  Simulator interface
