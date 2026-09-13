# openEMS

openEMS is a free, open-source **FDTD** electromagnetic solver — "finite-difference
time-domain," meaning it chops 3D space into a grid of cells and marches
Maxwell's equations forward in tiny time steps, watching a pulse of energy
bounce through the structure, rather than solving one frequency at a time
[1][2]. This repo uses it as one of its full-wave solvers: given a patch
antenna, absorber, or frequency-selective-surface geometry, openEMS
predicts how it actually behaves (reflection, transmission, resonance)
before anything is printed — and because one time-domain run's output can
be Fourier-transformed to many frequencies at once, it's well suited to
sweeping a whole band in one shot.

## What it is

openEMS is the FDTD solver at the core of the "openEMS-Project," developed
and maintained primarily by Thorsten Liebig (`thliebig` on GitHub), with
copyright spanning 2010–2026 and open community contribution via pull
requests [2][3]. Geometry and materials are described by a companion C++
library, **CSXCAD** ("Continuous Structure XML CAD"), licensed separately
and reusable outside openEMS [4]. The project has no numbered 1.0 release:
its GitHub tags run from `v0.0.32` through a `v0.37.0-rc2` release
candidate dated 2026-09-07, i.e. mature but still pre-1.0 and under active
development [5].

## Full capabilities

- **Geometry**: arbitrary 3D structures via CSXCAD's primitives — boxes,
  cylinders, spheres, polyhedra, curves — meshed on a Cartesian or a
  cylindrical grid (the latter meshes a circularly symmetric part, e.g. a
  cylindrical antenna, without Cartesian staircasing) [2][6].
- **Materials**: isotropic or per-axis anisotropic epsilon/mue/conductivity
  (each written as an X/Y/Z vector, not one scalar), plus dispersive
  models — Drude, Lorentz, full multi-pole Debye — for properties that vary
  with frequency [2].
- **Excitation/boundaries**: Gaussian-pulse and total-field/scattered-field
  plane-wave excitation; absorbing boundaries via uniaxial PML or Mur ABC;
  lumped RLC elements [2].
- **Field analysis**: near-field-to-far-field (NF2FF) transform for
  antenna radiation patterns, and SAR calculation (1 g/10 g averaging) [2].
- **Performance**: SIMD (SSE2), multi-threaded, and optionally **MPI**-
  parallel engines — confirmed by dedicated source files
  `FDTD/engine_mpi.cpp`, `operator_mpi.cpp`, `openems_fdtd_mpi.cpp`, i.e.
  real domain-decomposed parallelism across machines, not just
  multithreading on one box [7].
- **Output**: HDF5/VTK field dumps, plus plain-ASCII per-port
  voltage/current time series [2].
- **Bindings**: Octave/MATLAB and Python (Cython) scripting are openEMS's
  primary interfaces; `AppCSXCAD` (built on the `QCSXCAD` Qt library) is a
  standalone GUI for viewing/building CSXCAD geometry [8][2].

**Periodic/Floquet boundaries — checked, not found as a built-in feature.**
Unlike this repo's Palace adapter (native Floquet ports for unit-cell
metasurface work), a GitHub code search of `thliebig/openEMS` for
"Floquet" turns up only one tutorial-comment hit, and openEMS's own
`SetBoundaryCond` documents only PML/Mur/PEC/PMC wall types — no periodic
type [9][10]. Its own `CRLH_Extraction.m` tutorial, which characterizes a
periodic metamaterial cell, uses PML/Mur/PEC walls and instead validates
the single-cell result against a separately computed Bloch-Floquet
dispersion relation — not a true phase-shifted periodic boundary [11].

## Integrations & interfaces

openEMS ships as a standalone CLI binary, `openEMS <FDTD_XML_FILE>
[options]`, reading a CSXCAD-generated XML file (geometry, materials, mesh,
settings) and writing result files (field dumps, port probe data) to the
working directory [2]. No cloud service or paid API — it's source-built or
package-installed software a caller shells out to.

## Licensing & cost

openEMS is licensed under **GNU GPL v3.0** (confirmed by fetching its
`COPYING` file directly) [3]: free to use, modify, redistribute, with
copyleft applying to distributed derivatives of its own code (this repo
only shells out to the binary, so that obligation doesn't reach this
repo's source). Its companion library CSXCAD carries the more permissive
LGPLv3, which allows linking from non-GPL code [4].

## How this repo uses it today

`simulation/openems.py` implements `OpenemsSimulator(Simulator)` —
`simulation/base.py`'s shared `run(job) -> SimulationResult` interface.
**`generate_openems_xml()`** builds a full FDTD-XML file from a structured
geometry/materials/ports/mesh dict: `Box`, `Cylinder`, or (issue #55)
planar `Polygon` primitives (the last covering arbitrary unit-cell outlines
like split-ring resonators), a rectilinear mesh, per-port `Excitation`
(Gaussian pulse), `LumpedElement` termination, and voltage/current
`ProbeBox` pairs, and (issue #269) an optional `nf2ff` recording-box
definition — a dozen per-face `DumpBox` field-dump properties, one E and
one H frequency-domain dump per enclosing-box face, following openEMS's
own `CreateNF2FFBox.m` naming convention. **`OpenemsSimulator.run()`**
shells out to the real `openEMS` binary via `subprocess` (default
`--disable-dumps`, since ordinarily this adapter doesn't parse H5 field
dumps — dropped automatically for a run that requests an `nf2ff` box, so
its dumps actually get written). **`parse_openems_output()`** reads that
log for convergence metadata (energy-decay end-criteria vs. max-timesteps
termination), then, given the workdir and port list,
**`_compute_s_parameters_from_probes()`** FFTs each port's voltage/current
dump, decomposes incident/reflected waves per openEMS's own
`calcLumpedPort.m` formula, and computes real S-parameters — for a single
port, the full S11, also written as a Touchstone `.s1p` via `skrf`. Given
the workdir and an `nf2ff` box definition,
**`_compute_far_field_from_nf2ff()`** shells out to openEMS's own
*separate* `nf2ff` command-line tool (a distinct binary from `openEMS`
itself, built from the same source tree) against the FD field dumps just
written, then parses its result HDF5 (`/nf2ff/E_theta`, `/nf2ff/E_phi`,
`/nf2ff/P_rad`, `/nf2ff` `Prad` attribute) into a real per-angle `pattern`
table and `gain_dbi` — structurally parallel to `simulation/nec2pp.py`'s
own `pattern`/`gain_dbi` keys. **`run_openems_simulation()`** orchestrates
all of the above, tagging results `provenance: "SIMULATED"`.

The module's own header states the real `openEMS` binary (and the
separate `nf2ff` binary) are **built into this project's own Docker image
(Dockerfile)** but **absent on a bare host**, and even inside the image
neither has ever actually been driven by this code (issue #480), so none
of this has been exercised end-to-end against a real run — an
explicitly-flagged gap, not a silent one.

## Capabilities not yet used here

- **Dispersive/anisotropic materials**: the adapter only emits isotropic,
  non-dispersive values, though CSXCAD's XML already supports per-axis
  tensors and openEMS supports Drude/Lorentz/Debye dispersion.
- **Multi-port N×N S-matrices**: only the excited port's column is
  computed per run; a full matrix needs one run per port, unorchestrated.
- **MPI/cylindrical mesh**: both real openEMS features (large-structure
  speedup; staircase-free curved-geometry meshing) not exposed here.
- **Periodic/Floquet unit cells**: not a built-in openEMS capability at
  all (Palace fills that role in this repo), so not a gap in this adapter
  specifically.

## Sources

- [1] https://www.openems.de/ — official project site ("openEMS is a free and open electromagnetic field solver using the FDTD method")
- [2] https://raw.githubusercontent.com/thliebig/openEMS/master/README.md — official README (features, dependencies, bindings, license statement)
- [3] https://raw.githubusercontent.com/thliebig/openEMS/master/COPYING — GPLv3 license text, fetched directly
- [4] https://raw.githubusercontent.com/thliebig/CSXCAD/master/README.md — CSXCAD README (what it is, LGPLv3 license, relation to openEMS)
- [5] https://github.com/thliebig/openEMS/tags — tag list (v0.0.32 … v0.37.0-rc2, dated 2026-09-07), fetched directly
- [6] https://docs.openems.de/ — official docs index (CSXCAD primitive list, Python/Octave/AppCSXCAD interfaces, NF2FF, port types)
- [7] GitHub code search (`mcp__github__search_code`) for `MPI repo:thliebig/openEMS extension:cpp` — confirms `FDTD/engine_mpi.cpp`, `FDTD/operator_mpi.cpp`, `FDTD/openems_fdtd_mpi.cpp`
- [8] https://github.com/thliebig/AppCSXCAD and https://manpages.ubuntu.com/manpages/focal/man1/AppCSXCAD.1.html — AppCSXCAD description ("GUI for looking at geometries for openEMS", built on QCSXCAD)
- [9] GitHub code search for `Floquet repo:thliebig/openEMS` — single tutorial-comment match, no dedicated Floquet-port implementation found
- [10] https://github.com/thliebig/openEMS/blob/master/matlab/SetBoundaryCond.m — boundary-condition setter; documented types are PML/MUR/PEC/PMC, no periodic type
- [11] https://raw.githubusercontent.com/thliebig/openEMS/master/matlab/Tutorials/CRLH_Extraction.m — periodic-metamaterial tutorial using PML/MUR/PEC walls plus a separately-computed Bloch-Floquet dispersion check, not a true periodic boundary
- [12] https://raw.githubusercontent.com/thliebig/openEMS/master/matlab/CreateNF2FFBox.m — the NF2FF recording-box convention (12 per-face DumpBox properties, "\<name\>\_E\_\<face\>"/"\<name\>\_H\_\<face\>" naming), fetched directly
- [13] https://raw.githubusercontent.com/thliebig/CSXCAD/master/src/CSPropDumpBox.cpp, `.h`, and `matlab/AddDump.m` — the `DumpBox` property's XML attribute shape (DumpType/DumpMode/FileType) and its numeric-code meanings, fetched directly
- [14] https://raw.githubusercontent.com/thliebig/openEMS/master/nf2ff/main.cpp and `nf2ff/nf2ff.cpp` — the standalone `nf2ff` command-line tool's CLI contract (`nf2ff <xml-file>`) and its own input-XML/result-HDF5 schemas, fetched directly
- [15] https://raw.githubusercontent.com/thliebig/openEMS/master/nf2ff/nf2ff_calc.cpp — the Directivity(theta,phi) = 4·π·r²·P_rad(theta,phi)/Prad_total formula this adapter's own gain_dbi is computed from, fetched directly
- [16] https://raw.githubusercontent.com/thliebig/openEMS/master/python/openEMS/nf2ff.py — openEMS's own Python NF2FF result reader; confirms h5py reads the result HDF5's complex fields as native numpy complex arrays with no manual real/imag reassembly, fetched directly
- `simulation/openems.py` and `simulation/base.py` (this repo) — current adapter implementation and `Simulator` interface, including its own extensive source citations for the FDTD-XML format
- Not independently confirmed in this pass: GitHub's Releases page for `thliebig/openEMS` reports no formal releases (project is tagged but not "Released" in GitHub's UI sense); version history above is read from tags only
