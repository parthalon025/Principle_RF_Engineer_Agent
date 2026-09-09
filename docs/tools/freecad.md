# FreeCAD

FreeCAD is a free, open-source 3-D CAD ("computer-aided design") program —
the same category of tool as SolidWorks or Fusion 360 — used for building
precise, dimensioned 3-D models of physical parts [1]. It is "parametric,"
meaning a model is stored as a list of steps (sketch this rectangle, extrude
it this far, cut this hole) rather than as a frozen shape, so a designer can
go back and change one number (a radius, a thickness) and have the whole
model update automatically [1]. This repo uses FreeCAD for one narrow job:
taking a flat grid of unit cells (the repeating patches, slots, or rings that
make up a metasurface or frequency-selective surface) and building a
geometrically exact 3-D model of that same grid wrapped around a curved host
— a cylinder (a missile body, a pipe) or a sphere (a radome) — so the part
that eventually gets fabricated matches the part that was actually simulated,
instead of a flat approximation of it (`geometry/freecad_curved.py`).

## What it is

FreeCAD is developed and maintained as a community open-source project (no
single company owns it), currently on the `FreeCAD/FreeCAD` GitHub
repository, described in its own README as "an open-source parametric 3D
modeler made primarily to design real-life objects of any size" [1][2]. Its
release announcements credit "all contributors and developers" rather than a
formal corporate or foundation maintainer [3]. It is built on the
OpenCASCADE geometry kernel (the same industrial B-rep/solid-modeling engine
used by several commercial CAD tools), Coin3D for 3-D visualization, and Qt
for its GUI [1]. The current stable release is **1.1.1** (a patch release
on top of 1.1, dated 15 April 2026); 1.0, released November 2024, was the
milestone release that added FreeCAD's own built-in Assembly workbench [3][4].

## Full capabilities

- **Parametric solid modeling** — a history-based feature tree (sketch,
  pad/extrude, pocket/cut, fillet, pattern, ...) where any earlier step can
  be edited and everything downstream recomputes [1].
- **Sketcher** — 2-D profile drawing with geometric and dimensional
  constraints (parallel, tangent, equal-length, a specific length in mm),
  the normal starting point for a parametric feature [1].
- **Workbenches** (FreeCAD's term for a bundled toolset aimed at one kind of
  work), including **Part** (basic solid primitives and boolean operations —
  the workbench this repo's adapter actually calls), **PartDesign**
  (feature-based solid modeling built on Sketcher), **Draft** (2-D drafting
  and simple 3-D primitives), **Surface** (freeform/NURBS surface modeling
  beyond solid primitives), **TechDraw** (2-D engineering drawings/
  documentation from a 3-D model), **BIM** (architecture/building modeling),
  **CAM** (toolpath generation for CNC machining), **Robot** (robot motion
  simulation), and **FEM** (finite element analysis pre/post-processing,
  meshing via Netgen or Gmsh, driving external structural/thermal/EM solvers
  — CalculiX by default, plus Elmer, Mystran, and Z88) [1][5].
- **Python scripting API and console** — nearly everything a user can do
  through the GUI (`App.newDocument`, `Document.addObject`, geometry
  construction, `Placement`) is exposed as a scriptable Python API, and
  FreeCAD ships an interactive Python console inside the GUI in addition to
  the fully headless `FreeCADCmd` executable this repo's adapter uses
  (`src/App/FreeCAD.module.pyi`, `src/App/Document.pyi`, cited directly in
  `geometry/freecad_curved.py`'s own module docstring).
- **File format import/export** — reads and writes STEP, IGES, STL, SVG,
  DXF, OBJ, IFC, DAE "and many others," per the project's own features page
  [1] — including the STEP export this repo's adapter actually invokes
  (`TopoShape.exportStep`).
- **Cross-platform** — Windows, macOS, and Linux [1].

## Integrations & interfaces

FreeCAD ships two ways to drive it without a person clicking a GUI: the
GUI executable's own `--console`/`-c` flag (`freecad --console script.py`),
and a fully separate, GUI-free executable, `FreeCADCmd`, whose own CMake
build target links against `FreeCADApp` but explicitly *not* `FreeCADGui` —
confirmed by reading `src/Main/CMakeLists.txt` and `src/Main/MainCmd.cpp`
directly rather than inferring it, per `geometry/freecad_curved.py`'s module
docstring. Either way, a positional `.py` (or `.FCMacro`/`.FCScript`)
argument is run as a script and the process exits cleanly with no
interactive prompt — the exact mechanism this repo's adapter relies on.
FreeCADCmd runs in its own separate Python interpreter, entirely independent
of this project's own Python virtual environment.

## Licensing & cost

**LGPL-2.1-or-later** (GNU Lesser General Public License), confirmed by
fetching the repository's own `LICENSE` file, whose text opens "GNU LESSER
GENERAL PUBLIC LICENSE, Version 2.1, February 1999" [2]. It is free to
download, use, modify, and redistribute, with no paid tier, seat license, or
commercial restriction.

## How this repo uses it today

`geometry/freecad_curved.py` is a geometry generator, not a
`simulation.base.Simulator` — it produces a geometry dict (and, optionally,
a 3-D model) for another tool to consume, and deliberately does not import
anything from `simulation/`. It does two things:

1. `map_unit_cell_layout_to_curved_surface()` is pure Python math (no
   FreeCAD at all) that curvature-maps a flat unit-cell layout onto a
   cylinder or sphere and re-expresses it as this repo's own flattened
   "polygon" primitive dicts, each snapped to the nearest global x/y/z axis
   (a "staircase" approximation) since the downstream EM solver's own
   polygon primitive cannot represent an arbitrarily tilted plane.
2. `generate_freecad_macro()` writes a self-contained, headless FreeCAD
   Python macro that builds the *same* array as an exact 3-D solid model —
   one `Part::Feature` per unit cell, each box correctly extruded along its
   true local surface normal (not the flat layout's Z axis) via
   `Part.makePolygon`/`Part.Face`/`TopoShape.extrude`, positioned with
   `Placement` as a pure translation, then combined with
   `Part.makeCompound(...)` and exported to a single STEP file via
   `TopoShape.exportStep`. `run_freecad_curved_geometry()` writes that macro
   to a temp workdir, shells out to `FreeCADCmd <macro>` (executable
   overridable via a `FREECAD_BIN` env var, matching this repo's other
   `<TOOL>_BIN`-convention adapters), and parses back a small JSON status
   file the macro itself writes (`objects_built`, per-object `errors`, the
   STEP file path) — raising `FreecadGeometryError` only for a subprocess-
   level failure (nonzero exit, timeout, executable not found), not for a
   per-object build failure inside a successful run.

**Explicitly not implemented/exercised here**: `run_freecad_curved_geometry()`
— the default, existing entry point — only uses the `Part` workbench's
lowest-level primitives (polygon wire → face → extrude) and `Placement`; no
Sketcher, PartDesign, Draft, Surface, TechDraw, BIM, CAM, or Robot workbench
code path is touched by it, and its own STEP-export-only behavior is
unchanged by the FEM-mesh prototype below. A SEPARATE, additive entry point,
`run_freecad_fem_mesh_geometry()`, now DOES drive the FEM workbench (see
"Capabilities not yet used here" below) — an existing caller of
`run_freecad_curved_geometry()` is unaffected either way. Only "box" and
"polygon" flat input
primitives are accepted (not "cylinder"), matching `geometry/unit_cell.py`'s
own scope. The module's own header states FreeCAD/FreeCADCmd is almost
certainly not installed in this environment, and that its subprocess path
(`_run_freecadcmd`) has only been exercised against a fake stand-in script in
`tests/test_freecad_curved.py`, not a real FreeCADCmd binary — the pure
curvature math is independently tested and needs no FreeCAD install.
`policies/tool_policy.yaml` places `generate_freecad_curved_geometry` under
`approval_required` (non-destructive: local-workdir-only, no network, no
credentials).

## Capabilities not yet used here

**FEM workbench meshing is now prototyped (issue #288), not implemented.**
`geometry/freecad_curved.py`'s `generate_freecad_fem_mesh_macro()` /
`run_freecad_fem_mesh_geometry()` drive the FEM workbench's real, current
(FreeCAD 1.x) Python API — `ObjectsFem.makeMeshGmsh()` to create a
`Fem::FemMeshShapeBaseObjectPython` mesh object, linking its `.Shape`
property directly to the SAME `Part.makeCompound(...)` curved solid
`generate_freecad_macro()` already builds (kept as a live `Part::Feature`
instead of only exported to STEP), then `femmesh.gmshtools.GmshTools(mesh_obj
).create_mesh()` to actually run Gmsh and read the resulting mesh (`.unv` by
default, `.vtk` if the install was compiled with `BUILD_FEM_VTK`) back into
`mesh_obj.FemMesh`. Traced directly from FreeCAD's own source (`ObjectsFem
.py`, `femmesh/gmshtools.py`, the C++ `Fem::FemMeshShapeBaseObject`/
`Fem::WorkerExtension` property declarations, and FreeCAD's own headless-
compatible `femtest/app/test_gmsh.py` test, which calls the identical
`GmshTools(obj).create_mesh()` sequence) — see `geometry/freecad_curved.py`'s
module docstring "FEM WORKBENCH MESHING" section for the full citation list.

Also traced (not just guessed at) during this pass: whether a FreeCAD-FEM-
produced mesh of the curved solid can close `simulation/elmer.py`'s own
stated "no curved/cylindrical geometry" meshing gap. It genuinely can, in
principle — ElmerGrid's own format-name table (`elmergrid/src/egnative.c`)
lists format code 8 as `"UNV"`, and its CLI dispatch (`elmergrid/src/
fempre.c`, `case 8: ... LoadUniversalMesh(...)`) confirms it reads a `.unv`
file directly, which is exactly the file format `GmshTools` writes by
default. `simulation/elmer.py`'s `run_elmergrid_conversion()` still
hardcodes Gmsh-format (code 14) and was NOT modified in this pass (out of
this ticket's own declared scope) — wiring format 8 through is a small,
well-scoped follow-up, not yet done, and this pass could not verify a real
FreeCAD-produced `.unv` file's element/group tagging against `
LoadUniversalMesh()`'s expectations end-to-end (both read from source, not
exercised against each other with a real file).

**Not registered as an agent/MCP tool (deliberately, same reason as the
paragraph above)**: unlike `run_freecad_curved_geometry()` (wired as
`generate_freecad_curved_geometry` in `agent/main.py`, `mcp_server/
server.py`, and `policies/tool_policy.yaml` — its geometry-dict output
drops straight into `run_openems_simulation`'s/`run_palace_simulation`'s
own geometry conductor/material lists even without FreeCAD installed),
`run_freecad_fem_mesh_geometry()`'s mesh file has no downstream consumer
anywhere in this repo yet: `run_elmergrid_conversion()` still hardcodes
Gmsh-format 14, not the UNV format 8 a FreeCAD-Gmsh mesh actually produces.
Wiring an agent-callable tool whose result nothing else can consume yet
would just expose a dead end — this is a natural follow-up once
`run_elmergrid_conversion()` gains that format-8 path, not before.

**Blocked on, honestly**: this prototype is exercised only against a fake
`FreeCADCmd` stand-in (`tests/test_freecad_curved.py`), same as every other
claim in this module — neither a real FreeCAD+Gmsh install nor a real
ElmerGrid was available to confirm any of this end-to-end. A second, real
dependency (`gmsh`) plus a genuine "does PySide's `QProcess` signal/event
delivery behave correctly inside a GUI-less `FreeCADCmd` process" question
(reasoned about, not independently confirmed against a real binary — see the
module docstring) make this strictly less-verified than the existing
STEP-export path.

Also unused: the **Surface workbench**
(true NURBS/freeform surfaces, which could represent a doubly-curved,
non-developable host surface more faithfully than this module's own
cylinder/sphere-only, cardinal-axis-aligned curvature model); **IGES import**
(so a real, externally supplied CAD host surface — an actual fuselage or
radome model — could be draped directly instead of only the cylinder/sphere
parameterizations this module derives by hand); and the **GUI/interactive
console** (irrelevant to this repo's headless, agent-driven use, but the
GUI's live 3-D preview is otherwise FreeCAD's main day-to-day interface for
a human).

## Sources

- [1] https://www.freecad.org/ — official site: what FreeCAD is, workbench list (Part, PartDesign, Sketcher, Draft, Surface, FEM, BIM, Geodata, CAM/CNC, Robot), file format support, OpenCASCADE/Coin3D/Qt
- [2] https://raw.githubusercontent.com/FreeCAD/FreeCAD/main/LICENSE — LGPL-2.1 license text, fetched directly from the repo root
- [3] https://blog.freecad.org/2026/04/15/freecad-1-1-1-released/ — 1.1.1 patch release announcement, community-contributor maintenance language
- [4] Web search (query: "FreeCAD 1.0 release version 2026 latest stable") surfacing https://blog.freecad.org/2026/03/25/freecad-version-1-1-released/ and the FreeCAD 1.0 (Nov 2024) Assembly-workbench milestone
- [5] https://raw.githubusercontent.com/FreeCAD/FreeCAD-documentation/main/wiki/FEM_Workbench.md — FEM workbench meshing (Netgen/Gmsh) and supported external solvers (CalculiX, Elmer, Mystran, Z88); fetched as a mirror of the live wiki.freecad.org content, which this pass (like `geometry/freecad_curved.py`'s own module docstring) could not fetch directly (Anubis bot-challenge access denial)
- `geometry/freecad_curved.py` (this repo) — adapter implementation, its own extensive primary-source citations to `github.com/FreeCAD/FreeCAD`'s `src/Main/CMakeLists.txt`, `src/Main/MainCmd.cpp`, `src/App/Application.cpp`, and the `.pyi` API stubs used
- `policies/tool_policy.yaml` (this repo) — `generate_freecad_curved_geometry` listed under `approval_required`, non-destructive/sandboxed rationale
- [6] https://raw.githubusercontent.com/FreeCAD/FreeCAD/main/src/Mod/Fem/ObjectsFem.py — `makeMeshGmsh()`'s real object-construction code (issue #288 research)
- [7] https://raw.githubusercontent.com/FreeCAD/FreeCAD/main/src/Mod/Fem/femmesh/gmshtools.py — `GmshTools` class: `load_properties()`/`get_tmp_file_paths()` (`.unv` default mesh format, `.vtk` under `BUILD_FEM_VTK`)/`get_gmsh_command()` (PATH-resolved `gmsh` binary, no env-var override)/`create_mesh()`→`ObjectTools.run()`
- [8] https://raw.githubusercontent.com/FreeCAD/FreeCAD/main/src/Mod/Fem/femtools/objecttools.py — `ObjectTools` base class: `run(blocking)`/`prepare()`/`compute()`/`_process_finished()` (a meshing failure is a silent no-op unless the caller checks itself)
- [9] https://raw.githubusercontent.com/FreeCAD/FreeCAD/main/src/Mod/Fem/App/FemMeshShapeObject.h and .../App/WorkerExtension.h — the C++-declared `Shape` (`App::PropertyLink`) and `WorkingDirectory` (`App::PropertyPath`) properties a Gmsh mesh object actually exposes
- [10] https://raw.githubusercontent.com/FreeCAD/FreeCAD/main/src/Mod/Fem/femexamples/boxanalysis_base.py and .../femtest/app/test_gmsh.py — a real worked example of the `makeMeshGmsh`/`.Shape =`/`CharacteristicLengthMin` idiom, and FreeCAD's own test suite calling `GmshTools(obj).create_mesh()` directly (the strongest available evidence this works without a GUI)
- [11] https://raw.githubusercontent.com/ElmerCSC/elmerfem/devel/elmergrid/src/egnative.c, .../src/fempre.c, .../src/egconvert.c — ElmerGrid's format-code table (8 = "UNV"), CLI dispatch (`case 8: ... LoadUniversalMesh(...)`), and the UNV-reading function itself — confirms ElmerGrid can ingest a FreeCAD-FEM-produced `.unv` mesh directly
