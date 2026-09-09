"""FreeCAD-driven curved/conformal host-surface mapping for a flat unit-cell
array (issue #66).

WHAT THIS SOLVES, IN PLAIN LANGUAGE: geometry/unit_cell.py (issue #55) tiles
one unit cell (a patch, an SRR, a Jerusalem cross, ...) across a flat,
perfectly planar grid -- exactly right for a PCB or a flat metasurface panel,
but wrong for a REAL conformal antenna, which almost never sits on a flat
surface: it is wrapped around an aircraft fuselage, a missile body, a vehicle
roofline, or a radome. A unit cell that looks correct laid out flat on paper
is physically stretched, tilted, and repositioned once it is actually
mounted on that curved host -- ignoring that is a real, common design error
(element spacing and orientation drift with curvature, which shifts the
array's resonant behavior). This module takes a flat unit-cell layout (this
repo's own box/polygon primitive-dict list, e.g. straight out of
geometry.unit_cell.generate_unit_cell_array()/generate_metamaterial_array())
plus a simple curvature description (a cylinder or a sphere, with a radius
and which way it curves), and produces two things:

  1. A pure-Python, always-available (no FreeCAD installation required)
     mapping of that flat layout onto the curved surface, re-expressed in
     THIS REPO'S OWN existing box/cylinder/polygon primitive-dict shape
     (see map_unit_cell_layout_to_curved_surface() below) -- so the result
     drops straight into simulation/openems.py's `geometry["conductors"]`/
     `geometry["materials"]` list exactly the way geometry/unit_cell.py's
     own flat output already does (see that module's own module docstring,
     "the FreeCAD geometry generation planned for issue #66, which this
     ticket is a blocker for").
  2. A headless FreeCAD (FreeCADCmd) Python macro that builds the SAME array
     as a real, exact 3D solid model (each unit cell as its own tilted,
     curvature-following Part::Feature, box primitives correctly extruded
     along the true LOCAL surface normal rather than the flat/global Z axis)
     and exports it to a STEP file -- a genuinely more accurate artifact
     than (1) can be, useful for a mechanical/manufacturing handoff or for
     importing into another CAD-driven meshing tool (e.g. Gmsh, which
     simulation/elmer.py already drives).

Both paths share ONE piece of pure math (surface_frame_at() below) computed
once in this module's own Python process -- the FreeCAD macro never re-
derives the curvature trigonometry itself, it just receives the already-
computed absolute 3D vertex coordinates as literal numbers, so the "exact"
FreeCAD model and the "faceted" geometry-dict below can never silently drift
out of sync with each other.

THIS MODULE IS A GEOMETRY GENERATOR, NOT A simulation.base.Simulator
SUBCLASS: it does not run a simulation and produces no SimulationResult --
it produces a geometry dict for another tool (an openEMS/Palace/Elmer/etc.
run) to consume, exactly like geometry/unit_cell.py. It therefore lives
under geometry/, mirrors that module's shape/placement in the repository
tree, and (like that module) does not import anything from simulation/ --
this module is deliberately simulator-agnostic. Unlike geometry/unit_cell.py
(pure gdstk library calls, no subprocess), this module DOES shell out to an
external tool (FreeCADCmd), so its subprocess-invocation half follows this
repo's other simulator-adapter shell-out pattern instead (see
simulation/elmer.py's run_gmsh_meshing/run_elmergrid_conversion and
simulation/gprmax.py's GprmaxSimulator.run for the closest analogs: generate
an input script, subprocess.run the external tool, parse whatever structured
output is available, raise a local error type on failure rather than
silently degrading).

SOURCES CONSULTED (primary; every citation below was fetched directly from
github.com/FreeCAD/FreeCAD during this pass -- FreeCAD's own wiki at
wiki.freecad.org could NOT be fetched in this environment, see "HONEST
CAVEAT" below -- so every fact here is read from FreeCAD's own C++/Python-
stub source, not from wiki prose):

  FREECADCMD IS A REAL, SEPARATE, NO-GUI-DEPENDENCY EXECUTABLE (this
  ticket's own headless-mode acceptance criterion):
  - `src/Main/CMakeLists.txt`'s `FreeCADMainCmd` target (which builds the
    `FreeCADCmd` executable) is `add_executable(FreeCADMainCmd
    ${FreeCADMainCmd_SRCS})` built from `MainCmd.cpp` and linked only
    against `FreeCADApp`, `${QtCore_LIBRARIES}`, `${QtXml_LIBRARIES}`, and
    (conditionally) `${Python3_LIBRARIES}` -- CRITICALLY, it is NOT linked
    against `FreeCADGui` at all (unlike the GUI `FreeCAD`/`FreeCADGui`
    executable's own CMake target in the same directory), confirming
    FreeCADCmd genuinely carries no GUI/Qt-Widgets dependency and is safe to
    run on a headless CI/agent host with no display -- fetched directly
    from `src/Main/CMakeLists.txt`.
  - `src/Main/MainCmd.cpp` is FreeCADCmd's own entry point: it configures
    `Application::Config()["RunMode"] = "Exit"` (the default "process what
    was given, then quit" behavior -- see the RunMode citation below), calls
    `App::Application::init(argc, argv)`, then `App::Application::
    runApplication()`, then closes all documents and calls
    `App::Application::destruct()`. Its own top-of-file header carries an
    SPDX `GNU Lesser General Public License ... version 2.1` notice --
    independent corroboration of the LICENSE-file finding below, straight
    from the one file that builds the exact FreeCADCmd binary this module
    invokes.
  - `("console,c", "Starts in console mode")` is the literal
    `boost::program_options` option registration string in
    `src/App/Application.cpp` for the GUI executable's own `--console`/`-c`
    flag (an alternate, single-binary way to get the same headless
    behavior: `freecad --console script.py`) -- this module defaults to the
    separate FreeCADCmd binary instead (matching this repo's other single-
    binary adapters' `<TOOL>_BIN`-env-var-overridable convention, e.g.
    `ELMERSOLVER_BIN`/`OPENEMS_BIN`), but the executable is fully caller-
    overridable, so `freecad --console` remains an equally valid choice for
    a caller who prefers it.
  - `Application::processFiles()` in `src/App/Application.cpp` (the SAME
    command-line-file-processing code both the GUI executable and
    FreeCADCmd share, since both link `FreeCADApp`) is what actually makes
    `FreeCADCmd myscript.py` run a script: for a positional command-line
    argument whose extension is `.py`, it calls `Base::Interpreter().
    loadModule(...)`, falling back to `Base::Interpreter().runFile(...,
    true)` (run in `__main__`) if `loadModule` raises a `Base::PyException`;
    for a `.FCScript`/`.FCMacro` extension it calls `runFile(...)` directly.
    `Application::processCmdLineFiles()` then calls this, and
    `Application::runApplication()` (MainCmd.cpp's own second call) checks
    `RunMode`: for `RunMode == "Exit"` (FreeCADCmd's own default, set in
    MainCmd.cpp above) it logs "Exiting on purpose" and returns -- i.e. `
    FreeCADCmd script.py` runs the script via `processFiles()` and then
    exits cleanly once it returns, with NO interactive prompt and no GUI at
    any point -- confirmed by reading `Application::processFiles`/
    `processCmdLineFiles`/`runApplication` directly, not inferred from
    documentation prose. This is the exact mechanism `run_freecad_curved_
    geometry()`'s `_run_freecadcmd()` below relies on: `[executable,
    str(script_path)]`, a single positional script-file argument, no flags.
  - Usage banner `"Usage: " << exe << " [options] File1 File2 ..."` in
    `src/App/Application.cpp` confirms the shared CLI parser accepts
    positional file arguments generally (of which a `.py` script is one
    documented case, per `processFiles()` above).

  LICENSE (LGPL-2.1-or-later, this ticket's own acceptance criterion):
  - `LICENSE` at the root of github.com/FreeCAD/FreeCAD's `main` branch is
    the verbatim FSF "GNU LESSER GENERAL PUBLIC LICENSE, Version 2.1,
    February 1999" text, fetched directly.
  - Independently corroborated by `src/Main/MainCmd.cpp`'s own SPDX header
    (cited above) -- the specific source file that builds the FreeCADCmd
    binary this module shells out to itself carries an LGPL-2.1 notice, not
    just the repo's root LICENSE file in the abstract.

  PYTHON API USED TO BUILD THE 3D MODEL (all fetched directly from their own
  `.pyi` type-stub files or `.h`/`.cpp` source in github.com/FreeCAD/FreeCAD,
  `main` branch -- these stub files are FreeCAD's own machine-generated,
  from-the-real-binding API surface, not third-party documentation):
  - `App.newDocument(name=None, label=None, hidden=False, temp=False) ->
    Document`: `src/App/FreeCAD.module.pyi`.
  - `Document.addObject(type: str, name: str = ..., ...) -> DocumentObject`
    ("type: the type of the document object to create") and
    `Document.recompute(objs=None, force=False, check_cycle=False) -> int`:
    `src/App/Document.pyi`.
  - `Part::Feature` (the type name passed to `addObject` below) is declared
    `class PartExport Feature: public App::GeoFeature` in
    `src/Mod/Part/App/PartFeature.h`, and `App::GeoFeature` (`src/App/
    GeoFeature.h`, "Base class of all geometric document objects") declares
    a `PropertyPlacement Placement;` member -- confirming a `Part::Feature`
    object genuinely exposes a settable `.Placement` property, which
    `_render_freecad_object()` below uses (as a pure translation, identity
    rotation -- see "WHY NOT A ROTATED PLACEMENT" below) to position each
    unit cell's already-fully-oriented local shape at its true 3D centroid.
  - `Base.Vector(x: float = 0, y: float = 0, z: float = 0)`:
    `src/Base/Vector.pyi`.
  - `Base.Rotation()` (identity, the zero-argument overload) and
    `Base.Placement(base: Vector, rotation: RotationPy)`: `src/Base/
    Rotation.pyi`, `src/Base/Placement.pyi`.
  - `Part.makePolygon(pcObj: Sequence[Vector], pclosed: bool = False) ->
    Wire` and `Part.makeCompound(shapes, ...) -> Compound`:
    `src/Mod/Part/App/Part.module.pyi`.
  - `TopoShapeFace.__init__(self, wires: Sequence[TopoShape], /)` (i.e.
    `Part.Face([wire])` builds a planar face from one closed wire):
    `src/Mod/Part/App/TopoShapeFace.pyi`.
  - `TopoShape.extrude(vector: Vector, /) -> TopoShape` ("Extrude the shape
    along a vector") and `TopoShape.exportStep(filename: str, /) -> None`
    ("Export the content of this shape to an STEP file"):
    `src/Mod/Part/App/TopoShape.pyi`.

  WHY NOT A ROTATED PLACEMENT (a design decision made and rejected during
  this pass, recorded honestly rather than silently doing the simpler-
  looking but subtly wrong thing): the obvious-looking way to place a flat
  local unit-cell shape onto a curved surface is to build it flat in its own
  local XY plane and then set `feature.Placement = App.Placement(base,
  App.Rotation(App.Vector(0, 0, 1), App.Vector(*normal)))` (rotate local +Z
  onto the true surface normal). `Rotation(vector_start, vector_end)`'s own
  two-vector constructor (`src/Base/Rotation.pyi`, cited above) picks the
  minimal-angle rotation about their cross product -- it pins down where
  local +Z ends up (the normal, as wanted) but leaves an UNCONSTRAINED
  in-plane twist for where local +X/+Y end up (worked through by hand for
  the cylinder case below: at the cylinder's theta=0 reference point, local
  +X maps to (0, 0, -1), not this module's own tangent_u=(0, 1, 0) --
  a 90-degree twist relative to the frame the geometry-dict flattening below
  actually uses). Shipping that would make the "exact" FreeCAD model's
  vertex positions silently disagree with the geometry-dict's own vertex
  positions for the nominally-same unit cell -- exactly the kind of quiet,
  hard-to-notice inconsistency this repo's conventions rule out. This module
  instead computes each vertex's absolute 3D position directly from the SAME
  surface_frame_at() tangent_u/tangent_v/normal basis both outputs share
  (see map_unit_cell_layout_to_curved_surface() and
  _exact_curved_geometry() below), and uses `Placement` only as a pure
  translation (`App.Rotation()`, the identity/no-argument overload) to move
  that already-correctly-oriented local shape to its true centroid -- a
  real, cited, but deliberately simpler use of the Placement API than the
  rotated form, chosen for correctness over showing off more of the API.

  CSXCAD POLYGON'S OWN (X1, X2) <-> GLOBAL-AXIS CONVENTION (needed to emit a
  geometry-dict polygon primitive that will actually attach to the right
  plane once simulation/openems.py's `generate_openems_xml` renders it):
  `CSPrimPolygon::GetBoundBox`/`IsInside` in github.com/thliebig/CSXCAD's
  `master`-branch `src/CSPrimPolygon.cpp` compute `int nP = (m_NormDir+1)%3;
  int nPP = (m_NormDir+2)%3;` and then read/compare `Coord[nP]`/`Coord[nPP]`
  against the polygon's own stored `vCoords` (X1, X2) pairs -- i.e. for
  NormDir=0 (x) the in-plane pair is (y, z); for NormDir=1 (y) it is (z, x);
  for NormDir=2 (z) it is (x, y). geometry/unit_cell.py's own output (always
  `normal_axis="z"`, `points_m=[x, y]` pairs) implicitly assumes exactly
  this z-normal case; this module is the first in this repo to actually
  exercise the x/y-normal cases, so `map_unit_cell_layout_to_curved_
  surface()` below reads this cyclic `(axis_index+1)%3, (axis_index+2)%3`
  rule directly from CSXCAD's own source rather than guessing by analogy.

CURVATURE MODEL (this module's own math, not itself drawn from a FreeCAD/
CSXCAD source -- standard cylindrical/spherical surface parameterization):
`surface_frame_at(u_m, v_m, curvature)` maps one point of the FLAT layout
(u_m, v_m -- the same local X/Y a flat geometry/unit_cell.py primitive
already carries) to a 3D position plus an orthonormal (position, normal,
tangent_u, tangent_v) frame on the chosen curved surface:
  - "cylinder": u_m is circumferential arc length (theta = theta0_rad +
    u_m / radius_m), v_m is the unchanged axial coordinate (a cylinder is a
    developable surface -- no distortion along its own axis).
  - "sphere": u_m is azimuthal arc length AT THE LAYOUT'S OWN REFERENCE
    LATITUDE (theta = theta0_rad + u_m / (radius_m * cos(phi0_rad))), v_m is
    polar/elevation arc length from that same reference latitude
    (phi = phi0_rad + v_m / radius_m). This is an honest, stated
    approximation (an "equirectangular"-style flattening, the same family of
    approximation every flat map projection of a sphere makes): it is exact
    arc length only along the phi0_rad reference latitude itself, and
    (like every such projection) breaks down entirely at phi = +/-90 degrees
    (the poles) -- surface_frame_at() raises ValueError rather than dividing
    by a near-zero cos(phi0_rad)/cos(phi) scale factor silently.

EMITTED PRIMITIVE SHAPE IS A FACETED, NEAREST-CARDINAL-AXIS-SNAPPED
APPROXIMATION -- READ BEFORE TRUSTING THE geometry-dict OUTPUT'S PRECISION:
CSXCAD's own Polygon primitive (see citation above and simulation/
openems.py's module docstring) can only lie in a plane perpendicular to a
GLOBAL x, y, or z axis -- it has no general 3-D-tilted-plane form. A flat
unit cell wrapped onto a curved surface, however, is naturally tangent to
whichever direction the surface curves at that exact point, which is
essentially NEVER exactly aligned with a global cardinal axis. This module
resolves that mismatch the same way FDTD solvers (openEMS included) already
resolve curved boundaries on their own inherently rectilinear Cartesian
grid: each unit cell becomes its own small flat FACET, individually snapped
to whichever global axis its own true local surface normal is closest to
(`_nearest_cardinal_axis()` below) -- a real, physically-motivated
"staircase" approximation, not a fabricated shortcut. Each emitted primitive
additionally carries a non-standard, purely informational `approx_sag_m`
field (the true circular sag -- `radius_m - sqrt(radius_m**2 - max_r**2)`,
`max_r` the unit cell's own half-diagonal -- between its true curved patch
and this flattened facet) so a caller can judge how much this approximation
actually cost for THIS cell size against THIS curvature radius; consumers
that only read the standard `shape`/`points_m`/`normal_axis`/`elevation_m`
fields (e.g. simulation/openems.py's `_polygon_primitive_xml`) simply ignore
the extra key. `map_unit_cell_layout_to_curved_surface()` raises ValueError
outright if a cell's own half-diagonal is >= the curvature radius (the facet
approximation stops meaning anything at that point, not just "gets worse").
THE FREECAD-BUILT 3D MODEL DOES NOT HAVE THIS LIMITATION -- it builds each
unit cell's true tilted plane exactly (see `_exact_curved_geometry()`
below), which is precisely why generating a real FreeCAD model has genuine
value beyond what the geometry-dict alone can represent.

SCOPE AND LIMITATIONS (explicit, not silently glossed over):
  - Only "box" and "polygon" flat input primitives are accepted (not
    "cylinder") -- same scope limit as geometry/unit_cell.py's own
    generate_unit_cell_array(), for the same reason (there is no
    well-defined way to curvature-map a cylindrical primitive's own axis
    without inventing new geometry, out of scope here).
  - An input "polygon" primitive must already have `normal_axis == "z"`:
    this module's whole job is mapping a FLAT (single-plane) layout onto a
    curved surface, and a primitive whose own local plane is already tilted
    to "x"/"y" does not fit that "flat layout" input contract.
  - A "box" primitive's Z-thickness (its own volume, not just its footprint)
    is collapsed to a single elevation at its Z-center for the geometry-dict
    output -- CSXCAD's Polygon primitive is inherently a zero-thickness
    sheet, so there is no lossless way to carry a volumetric box's full
    thickness through a Polygon primitive at all. The FreeCAD-built 3D model
    does NOT have this limitation: `_exact_curved_geometry()` extrudes a
    box's true thickness along the TRUE local surface normal (not the flat
    layout's own Z axis), a real, meaningful improvement the geometry-dict
    path cannot offer.
  - Curvature is single-axis (cylinder, whose axis must be a global
    cardinal x/y/z) or a sphere with the same cardinal-axis "pole" -- an
    arbitrarily-oriented or doubly-curved-with-an-off-axis host surface is
    out of scope for this pass.

FEM WORKBENCH MESHING (issue #288 -- generate_freecad_fem_mesh_macro() /
run_freecad_fem_mesh_geometry() below): docs/tools/freecad.md's "Capabilities
not yet used here" section named FreeCAD's own FEM workbench (meshing via
Netgen/Gmsh, driving CalculiX/Elmer/Mystran/Z88) as the clearest unused
capability, and asked whether it can mesh directly off the exact curved
solid `_exact_curved_geometry()`/`generate_freecad_macro()` already builds,
instead of that solid being exported to STEP and never touched again while
simulation/elmer.py separately rebuilds a much cruder flat-box domain from
scratch. IN PLAIN LANGUAGE: "meshing" means chopping a 3D shape into many
small tetrahedra a solver can crunch through one at a time -- like tiling an
oddly-curved garden bed with many small tiles instead of cutting one custom
slab. This repo already has two disconnected tiling steps (FreeCAD builds
the exact curved shape but never tiles it; Elmer's pipeline tiles a shape
but only ever a flat box); this section answers whether FreeCAD can do both
in one place. All facts below were fetched directly from
github.com/FreeCAD/FreeCAD's `main` branch during this pass (via GitHub's
contents/search APIs, same method as the rest of this module):

  THE REAL, MODERN (FreeCAD 1.x) API CALL SEQUENCE (NOT the older
  "FemGmshTools" name this ticket's own title suggests -- that class was
  renamed `GmshTools` at some point; reasoned from what the CURRENT source
  actually contains, not assumed from the ticket text):
  - `ObjectsFem.makeMeshGmsh(doc, name)` (`src/Mod/Fem/ObjectsFem.py`):
    `doc.addObject("Fem::FemMeshShapeBaseObjectPython", name)`, then attaches
    a `femobjects.mesh_gmsh.MeshGmsh(obj)` Python proxy which adds the
    Gmsh-specific properties (`CharacteristicLengthMax`/`Min`,
    `ElementDimension`, `ElementOrder`, algorithm choices, ...) and calls
    `obj.addExtension("Fem::WorkerExtensionPython")`.
  - `Shape` is an `App::PropertyLink Shape;` declared directly on the C++
    base class `Fem::FemMeshShapeBaseObject` (`src/Mod/Fem/App/
    FemMeshShapeObject.h`) -- i.e. `mesh_obj.Shape = <a Part::Feature>`
    (NOT `.Part`, an older, since-migrated property name --
    `femobjects/mesh_gmsh.py`'s own `onDocumentRestored()` migrates old
    documents' `Part` property to `Shape` for exactly this reason) links
    the mesh object to the geometry it will mesh. This module points it at
    a NEW `Part::Feature` wrapping `Part.makeCompound(built_shapes)` -- the
    same compound `generate_freecad_macro()` already builds, just kept as
    its own live document object here (instead of only exported to STEP)
    so the mesh object has something to `.Shape`-link to.
  - `WorkingDirectory` is an `App::PropertyPath WorkingDirectory;` declared
    on `Fem::WorkerExtension` (`src/Mod/Fem/App/WorkerExtension.h`, added by
    the `Fem::WorkerExtensionPython` extension above) -- this module sets it
    explicitly to the run's own (absolute) workdir so the produced mesh file
    lands somewhere this module's own Python-side code can find afterward,
    rather than relying on `femtools/objecttools.py`'s own
    `_create_working_directory()` fallback (a fresh `tempfile.mkdtemp(
    prefix="fem_")` -- yet another temp directory this run's own caller
    would not otherwise know about).
  - `femmesh/gmshtools.py`'s `GmshTools(mesh_obj)` (aliased to `FemGmshTools`
    in some FreeCAD forum/wiki write-ups, but `GmshTools` is the actual
    current class name) is the meshing driver: `load_properties()` reads
    `self.part_obj = self.obj.Shape` (confirming the `.Shape` link above is
    exactly what gets meshed); `get_tmp_file_paths()` computes
    `self.temp_file_mesh = <WorkingDirectory>/<ShapeObjName>_Mesh<ext>`
    where `<ext>` is **`.unv`** (the "Universal" mesh file format) UNLESS
    the specific FreeCAD build was compiled with the `BUILD_FEM_VTK` CMake
    option, in which case it is `.vtk` instead -- this module reads back
    whichever path `GmshTools` itself actually decided on (`tool.
    temp_file_mesh`) rather than assuming `.unv`, matching this repo's own
    "read back what actually happened, don't guess" convention; `
    get_gmsh_command()` resolves the real `gmsh` binary via a FreeCAD
    Preferences parameter or, if unset, `shutil.which("gmsh")` on `PATH` --
    NOT a `<TOOL>_BIN`-style environment variable the way every OTHER
    subprocess this repo drives is made overridable (nothing in this
    module's own `run_freecad_fem_mesh_geometry()` can change which `gmsh`
    FreeCAD's own FEM workbench code decides to invoke; only which
    `FreeCADCmd` is invoked is overridable, same as `generate_freecad_macro
    ()`'s own `FREECAD_BIN`).
  - `GmshTools.create_mesh()` ("for backward compatibility only") calls
    `self.run(True)`, inherited from the abstract base class
    `femtools/objecttools.py`'s `ObjectTools.run(blocking)`:
    `self.prepare(); self.compute(); if blocking: return self.process.
    waitForFinished(-1)` -- `prepare()` writes the shape to a `.brep` file
    and a Gmsh `.geo` script referencing it (the SAME `SetFactory(
    "OpenCASCADE")`-style Gmsh scripting simulation/elmer.py's own
    `generate_gmsh_geo_script()` hand-writes, but generated by FreeCAD's own
    code instead of this repo's), `compute()` launches the real `gmsh`
    binary via a `PySide.QtCore.QProcess` (async, not `subprocess.run`).
  - `Fem.FemMesh().read(self.temp_file_mesh)` (`update_properties()`) is
    what actually parses the mesh file back into `mesh_obj.FemMesh` (a
    `Fem::FemMesh` document-object property exposing `.NodeCount`/
    `.TetraCount`/`.TriangleCount`/etc.) -- but per `ObjectTools.
    _process_finished(code, status)`, this ONLY runs automatically if the
    QProcess signals a clean exit (`NormalExit` and code 0); a meshing
    FAILURE inside FreeCAD is otherwise a silent no-op (no exception, no
    populated `FemMesh`) unless the caller separately checks for it. This
    module's own macro therefore does NOT trust `run(True)`'s return value
    alone: it reads `tool.process.exitCode()`/`readAllStandardError()`
    itself, checks `os.path.exists(tool.temp_file_mesh)`, and calls `tool.
    update_properties()` again itself if the file exists but `FemMesh.
    NodeCount == 0` (idempotent -- it just re-reads the same file) rather
    than trusting the QProcess-signal callback fired correctly, since this
    pass could not verify PySide's signal/event-loop behavior inside a
    real, GUI-less `FreeCADCmd` process (`WorkerExtension`/`ObjectTools`
    both live in plain QtCore, which FreeCADCmd IS linked against per this
    module's own FreeCADCmd-linkage citation above -- so this SHOULD work,
    but "should" is doing real work in that sentence).
  - PRIMARY-SOURCE CONFIRMATION this exact call sequence already works
    without a GUI: FreeCAD's OWN test suite,
    `src/Mod/Fem/femtest/app/test_gmsh.py`, calls `gmshtools.GmshTools(
    obj).create_mesh()` directly and then reads `obj.FemMesh` back --
    every GUI-specific step in that same test file is separately guarded by
    `if FreeCAD.GuiUp:` checks, meaning the meshing call itself is written
    to not depend on a GUI being present. This pass did NOT independently
    confirm that FreeCAD's own CI test runner invokes the identical
    `FreeCADCmd` binary this repo's adapter shells out to (as opposed to
    the GUI executable's own `--console` mode, or a dedicated internal test
    driver) -- so this is strong, but not fully conclusive, evidence for
    THIS module's specific `FreeCADCmd <script>.py` invocation path.

  DOES THIS CLOSE simulation/elmer.py's OWN "no curved/cylindrical
  geometry" GAP (this ticket's own acceptance-criterion question)? Traced
  directly rather than guessed: `simulation/elmer.py`'s `
  run_elmergrid_conversion()` invokes `ElmerGrid 14 2 <stem> -out <name>`
  (format code 14 = Gmsh `.msh`). ElmerGrid's own format-name table
  (github.com/ElmerCSC/elmerfem's `devel` branch,
  `elmergrid/src/egnative.c`) lists format code **8 as `"UNV"`** ("Universal
  mesh file format"), and its own CLI dispatch switch
  (`elmergrid/src/fempre.c`, `case 8: ... LoadUniversalMesh(&(data[nofile]),
  boundaries[nofile], eg.filesin[nofile], TRUE)`) confirms ElmerGrid can
  read a `.unv` file DIRECTLY as an input mesh -- `LoadUniversalMesh()`
  itself lives in `elmergrid/src/egconvert.c` and opens the file exactly the
  way a real `.unv` mesh is shaped. CONCLUSION: since `GmshTools`' own
  default mesh-file format IS `.unv` (see above -- unless the install was
  built with `BUILD_FEM_VTK`), a FreeCAD-FEM-produced mesh of the curved
  solid this module builds could, in principle, be fed to ElmerGrid
  DIRECTLY by calling it with format code 8 instead of 14 -- genuinely
  closing simulation/elmer.py's own stated "no curved/cylindrical geometry"
  meshing gap, not merely reducing duplicated `.geo`-script logic (the
  weaker of the two outcomes this ticket's own acceptance criteria posed).
  THIS PASS DELIBERATELY DOES NOT WIRE THAT UP: `simulation/elmer.py`'s `
  run_elmergrid_conversion()` still hardcodes format 14 -- changing it is a
  small, well-scoped, real follow-up (add an `input_format` parameter
  defaulting to today's `"14"`) but is out of THIS ticket's own declared
  scope (a `geometry/freecad_curved.py` prototype), and this pass could not
  verify byte-for-byte that a REAL FreeCAD-Gmsh-produced `.unv` file's exact
  element/group tagging conventions line up with what `LoadUniversalMesh()`
  expects (both are read from source, not exercised against each other with
  a real file) -- recorded honestly as "structurally confirmed, not
  end-to-end verified," matching this module's own evidentiary standard
  throughout.

  UNIT CONVENTION THIS PATH INHERITS, NOT INTRODUCES: `generate_freecad_
  macro()`'s existing `App.Vector(*p)` calls already feed this module's own
  meters-scaled numbers into FreeCAD's Part-workbench geometry kernel as
  bare (unitless, by FreeCAD's own internal-always-mm convention) floats --
  whether that makes the resulting STEP file's real-world scale correct is
  a pre-existing question this ticket does not touch (fixing it would
  change `generate_freecad_macro()`'s own output, which this ticket's own
  acceptance criteria forbid). `mesh_max_size_m` below is embedded into
  `CharacteristicLengthMax` (an `App::PropertyLength`, i.e. millimeters by
  the same FreeCAD-internal convention) using that SAME bare-number
  convention -- deliberately, so the mesh-size number stays geometrically
  consistent with the ALREADY-built shape's own coordinate scale, even
  though this means neither number is a verified, correctly-scaled
  real-world quantity. Introducing a real mm-conversion here alone, without
  also fixing the vertex coordinates, would make the mismatch WORSE (a
  correctly-scaled mesh size next to a wrongly-scaled shape), not better.

HONEST CAVEAT: FreeCAD/FreeCADCmd is almost certainly NOT installed in this
environment (matching this repo's other manually-installed simulator tools
-- NEC2++, openEMS, Elmer, gprMax, etc.), and this pass could not fetch
wiki.freecad.org at all (every request returned an "Anubis" bot-challenge
"Access Denied" page, including the MediaWiki `action=raw`/`api.php` export
endpoints) -- every citation above is instead read directly from FreeCAD's
own C++/`.pyi` source on GitHub, which is a strictly more authoritative
primary source than wiki prose would have been, but it does mean no wiki
tutorial/example was available to sanity-check this module's macro against.
The pure curvature math (`surface_frame_at()`,
`map_unit_cell_layout_to_curved_surface()`) is exercised directly in tests
against real trigonometry -- no FreeCAD install is needed for it, or for any
of this ticket's own acceptance-criterion geometry-dict-shape tests.
`generate_freecad_macro()`'s subprocess invocation
(`_run_freecadcmd()`/`run_freecad_curved_geometry()`), however, is exercised
only against a small fake "FreeCADCmd" script (see
tests/test_freecad_curved.py), NOT a real FreeCADCmd binary. Treat any
FreeCAD-built-model result as unverified end-to-end until it has actually
been run against a real FreeCADCmd install at least once. The SAME applies,
with strictly MORE uncertainty (an additional real dependency -- `gmsh` --
plus the QProcess/no-GUI question above), to `generate_freecad_fem_mesh_
macro()`/`run_freecad_fem_mesh_geometry()`: this is a genuine prototype, not
a verified capability, per this ticket's own "investigate (and, if it holds
up, prototype)" framing.
"""

from __future__ import annotations

import json
import math
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import numpy as np

# x/y/z -> the same integer axis-index convention CSXCAD's own NormDir
# attribute uses (see simulation/openems.py's module docstring citation) and
# geometry/unit_cell.py's own _AXIS_INDEX. Duplicated here rather than
# imported from either module -- this module is deliberately simulator-
# agnostic (like geometry/unit_cell.py) and does not import simulation/.
_AXIS_INDEX = {"x": 0, "y": 1, "z": 2}
_AXIS_NAMES = ("x", "y", "z")
_UNIT_VECTORS = {
    "x": np.array([1.0, 0.0, 0.0]),
    "y": np.array([0.0, 1.0, 0.0]),
    "z": np.array([0.0, 0.0, 1.0]),
}

_DEFAULT_TIMEOUT_S = 600


class FreecadGeometryError(RuntimeError):
    """Raised when the headless FreeCADCmd subprocess step fails. Kept local
    to this module (NOT simulation.base.SimulatorError) since this module is
    a geometry generator, not a Simulator -- see module docstring."""


# ---------------------------------------------------------------------------
# Pure curvature math -- no FreeCAD, no subprocess. See module docstring
# "CURVATURE MODEL" for the cylinder/sphere parameterization this
# implements.
# ---------------------------------------------------------------------------


def _cyclic_pair(axis: str) -> tuple[str, str]:
    """The two global axes other than `axis`, in CSXCAD's own cyclic
    (axis_index+1)%3, (axis_index+2)%3 order (see module docstring citation
    of CSPrimPolygon.cpp) -- used here as this module's own (self-
    consistent, not itself CSXCAD-mandated) choice of which two axes form a
    cylinder's/sphere's circular cross-section basis, for the SAME cyclic
    ordering the geometry-dict output below relies on anyway."""
    idx = _AXIS_INDEX[axis]
    return _AXIS_NAMES[(idx + 1) % 3], _AXIS_NAMES[(idx + 2) % 3]


def surface_frame_at(u_m: float, v_m: float, curvature: dict[str, Any]) -> dict[str, list[float]]:
    """Map one point (u_m, v_m) of a FLAT layout onto the curved surface
    `curvature` describes, returning {"position_m", "normal", "tangent_u",
    "tangent_v"} -- each a 3-element [x, y, z] list, "normal"/"tangent_u"/
    "tangent_v" forming a right-handed orthonormal frame (unit vectors,
    mutually perpendicular) at that point. See module docstring "CURVATURE
    MODEL" for the exact parameterization and its honest scope limits.

    `curvature`:
        {
          "kind": "cylinder" | "sphere",
          "radius_m": float (> 0),
          "axis": "x" | "y" | "z" (default "z") -- the cylinder's own axis
              of symmetry, or the sphere's "pole" axis,
          "center_m": [x, y, z] (default [0, 0, 0]),
          "theta0_rad": float (default 0.0) -- reference azimuth offset,
          "phi0_rad": float (default 0.0, sphere only) -- reference
              latitude; u_m is true arc length only at this latitude (see
              module docstring), and phi0_rad must not be within ~1 degree
              of +/-90 degrees (the poles) or ValueError is raised.
        }
    """
    kind = curvature.get("kind")
    radius = curvature.get("radius_m")
    if not radius or radius <= 0:
        raise ValueError("curvature['radius_m'] must be a positive number")
    axis = curvature.get("axis", "z")
    if axis not in _AXIS_INDEX:
        raise ValueError(f"curvature['axis'] must be 'x', 'y', or 'z', got {axis!r}")
    center = np.array(curvature.get("center_m", [0.0, 0.0, 0.0]), dtype=float)
    c1_name, c2_name = _cyclic_pair(axis)
    e_c1, e_c2, e_axis = _UNIT_VECTORS[c1_name], _UNIT_VECTORS[c2_name], _UNIT_VECTORS[axis]

    if kind == "cylinder":
        theta0 = curvature.get("theta0_rad", 0.0)
        theta = theta0 + u_m / radius
        position = (
            center
            + radius * math.cos(theta) * e_c1
            + radius * math.sin(theta) * e_c2
            + v_m * e_axis
        )
        normal = math.cos(theta) * e_c1 + math.sin(theta) * e_c2
        tangent_u = -math.sin(theta) * e_c1 + math.cos(theta) * e_c2
        tangent_v = e_axis.copy()
    elif kind == "sphere":
        theta0 = curvature.get("theta0_rad", 0.0)
        phi0 = curvature.get("phi0_rad", 0.0)
        scale = radius * math.cos(phi0)
        if abs(math.cos(phi0)) < 1e-3:
            raise ValueError(
                "curvature['phi0_rad'] is too close to a pole (+/-90 degrees) for "
                "this module's equirectangular-style sphere mapping -- u_m's arc-"
                "length scale factor (radius_m * cos(phi0_rad)) is degenerate there "
                "(see module docstring 'CURVATURE MODEL')"
            )
        theta = theta0 + u_m / scale
        phi = phi0 + v_m / radius
        cos_phi, sin_phi = math.cos(phi), math.sin(phi)
        if abs(cos_phi) < 1e-6:
            raise ValueError(
                f"(u_m={u_m}, v_m={v_m}) maps to phi={phi!r} rad, within ~0.0001 "
                "degrees of a pole -- the tangent-plane basis is degenerate there"
            )
        radial = (
            cos_phi * math.cos(theta) * e_c1 + cos_phi * math.sin(theta) * e_c2 + sin_phi * e_axis
        )
        position = center + radius * radial
        normal = radial
        tangent_u = (-cos_phi * math.sin(theta) * e_c1 + cos_phi * math.cos(theta) * e_c2) / cos_phi
        tangent_v = (
            -sin_phi * math.cos(theta) * e_c1 - sin_phi * math.sin(theta) * e_c2 + cos_phi * e_axis
        )
    else:
        raise ValueError(f"curvature['kind'] must be 'cylinder' or 'sphere', got {kind!r}")

    return {
        "position_m": position.tolist(),
        "normal": normal.tolist(),
        "tangent_u": tangent_u.tolist(),
        "tangent_v": tangent_v.tolist(),
    }


def _nearest_cardinal_axis(vec: list[float]) -> str:
    """Which global x/y/z axis `vec` (a unit vector) is closest to -- the
    "staircase" facet-snapping decision, see module docstring."""
    idx = int(np.argmax(np.abs(np.asarray(vec, dtype=float))))
    return _AXIS_NAMES[idx]


def _flat_footprint(prim: dict[str, Any], idx: int) -> tuple[list[tuple[float, float]], float]:
    """Extract a flat input primitive's own local 2D footprint (a list of
    (x, y) vertices) and its "elevation" (height above the flat layout's own
    z=0 reference plane) -- see module docstring "SCOPE AND LIMITATIONS" for
    how box/polygon are each handled, and why only normal_axis="z" polygon
    input is accepted."""
    shape = prim.get("shape", "box")
    if shape == "box":
        missing = [f for f in ("p1_m", "p2_m") if f not in prim]
        if missing:
            raise ValueError(f"primitive {idx} (shape='box') missing required field(s): {missing}")
        p1, p2 = prim["p1_m"], prim["p2_m"]
        x1, y1 = float(p1[0]), float(p1[1])
        x2, y2 = float(p2[0]), float(p2[1])
        footprint = [(x1, y1), (x2, y1), (x2, y2), (x1, y2)]
        elevation = (float(p1[2]) + float(p2[2])) / 2.0
        return footprint, elevation
    if shape == "polygon":
        if "points_m" not in prim:
            raise ValueError(f"primitive {idx} (shape='polygon') missing required field 'points_m'")
        normal_axis = prim.get("normal_axis", "z")
        if normal_axis != "z":
            raise ValueError(
                f"primitive {idx}: a flat unit-cell layout primitive must have "
                f"normal_axis == 'z' (this module maps a FLAT layout onto a curved "
                f"surface -- a primitive whose own local plane is already tilted to "
                f"'x'/'y' does not fit that input contract), got {normal_axis!r}"
            )
        points = prim["points_m"]
        if len(points) < 3:
            raise ValueError(
                f"primitive {idx} (shape='polygon') requires at least 3 points_m, got {len(points)}"
            )
        footprint = [(float(x), float(y)) for x, y in points]
        elevation = float(prim.get("elevation_m", 0.0))
        return footprint, elevation
    raise ValueError(
        f"primitive {idx} 'shape' must be 'box' or 'polygon' (this module does not "
        f"curvature-map 'cylinder' primitives, matching geometry.unit_cell.generate_"
        f"unit_cell_array's own scope), got {shape!r}"
    )


def _centroid_and_frame(
    footprint: list[tuple[float, float]], curvature: dict[str, Any]
) -> tuple[float, float, dict[str, list[float]]]:
    cx = sum(p[0] for p in footprint) / len(footprint)
    cy = sum(p[1] for p in footprint) / len(footprint)
    return cx, cy, surface_frame_at(cx, cy, curvature)


def map_unit_cell_layout_to_curved_surface(
    primitives: list[dict[str, Any]],
    curvature: dict[str, Any],
    name_prefix: str = "cell",
) -> list[dict[str, Any]]:
    """Map a FLAT unit-cell layout (a list of this repo's own "box"/
    "polygon" primitive dicts, LOCAL x/y coordinates -- e.g. straight out of
    geometry.unit_cell.generate_unit_cell_array()/generate_metamaterial_
    array()) onto the curved host surface `curvature` describes, returning a
    list of "polygon" primitive dicts in this repo's EXISTING geometry-dict
    shape ("shape": "polygon", "points_m"/"normal_axis"/"elevation_m" --
    the same shape simulation/openems.py's `_polygon_primitive_xml` and
    geometry/unit_cell.py's own output already use).

    This is a pure function -- no FreeCAD, no subprocess -- always available
    and independently testable regardless of whether FreeCAD/FreeCADCmd is
    installed anywhere. See module docstring "EMITTED PRIMITIVE SHAPE IS A
    FACETED, NEAREST-CARDINAL-AXIS-SNAPPED APPROXIMATION" for exactly what
    approximation this makes and why (CSXCAD's own Polygon primitive cannot
    represent an arbitrarily-tilted 3D plane at all), and "SCOPE AND
    LIMITATIONS" for what box/polygon input each mean here.

    Each output primitive additionally carries a non-standard, purely
    informational `approx_sag_m` field -- the true circular sag between this
    cell's real curved patch and its flattened facet, `radius_m -
    sqrt(radius_m**2 - max_r**2)` where `max_r` is the cell's own half-
    diagonal. Raises ValueError if any cell's half-diagonal is >= the
    curvature radius (the facet approximation is meaningless past that
    point, not just "worse").

    See `curvature`'s shape in surface_frame_at()'s own docstring.
    """
    if not primitives:
        raise ValueError("primitives must be a non-empty list")
    radius = curvature.get("radius_m")
    if not radius or radius <= 0:
        raise ValueError("curvature['radius_m'] must be a positive number")

    results: list[dict[str, Any]] = []
    for idx, prim in enumerate(primitives):
        footprint, elevation = _flat_footprint(prim, idx)
        cx, cy, frame = _centroid_and_frame(footprint, curvature)
        position = np.array(frame["position_m"])
        normal = np.array(frame["normal"])
        tangent_u = np.array(frame["tangent_u"])
        tangent_v = np.array(frame["tangent_v"])

        max_r = max(math.hypot(px - cx, py - cy) for px, py in footprint)
        if max_r >= radius:
            raise ValueError(
                f"primitive {idx}: its footprint half-extent ({max_r:g} m) is >= the "
                f"curvature radius ({radius:g} m) -- this unit cell is too large "
                "relative to the host's curvature for a local-tangent-plane facet "
                "approximation to mean anything; shrink the cell or increase "
                "curvature['radius_m']"
            )
        sag_m = radius - math.sqrt(radius**2 - max_r**2)

        center_point = position + elevation * normal
        emitted_axis = _nearest_cardinal_axis(frame["normal"])
        axis_idx = _AXIS_INDEX[emitted_axis]
        c1_idx, c2_idx = (axis_idx + 1) % 3, (axis_idx + 2) % 3  # CSXCAD's own X1/X2 cyclic rule

        out_points: list[list[float]] = []
        for vx, vy in footprint:
            du, dv = vx - cx, vy - cy
            vertex_3d = center_point + du * tangent_u + dv * tangent_v
            out_points.append([float(vertex_3d[c1_idx]), float(vertex_3d[c2_idx])])

        results.append(
            {
                "name": prim.get("name", f"{name_prefix}_{idx}"),
                "shape": "polygon",
                "points_m": out_points,
                "normal_axis": emitted_axis,
                "elevation_m": float(center_point[axis_idx]),
                "approx_sag_m": sag_m,
            }
        )
    return results


# ---------------------------------------------------------------------------
# Exact 3D geometry (for the FreeCAD macro) -- same tangent frame as above,
# but WITHOUT the nearest-axis-snap/flattening step, so the FreeCAD model
# can represent each cell's true tilted plane exactly.
# ---------------------------------------------------------------------------


def _exact_curved_geometry(
    prim: dict[str, Any], curvature: dict[str, Any], idx: int
) -> dict[str, Any]:
    """One primitive's exact (unflattened) curved placement -- a local shape
    (`local_offsets_m`, 3D offsets from `center_m`, already fully oriented
    via the true tangent_u/tangent_v/normal frame) plus `center_m` and
    `normal`, and `thickness_m` (box primitives only, None for polygon) --
    see module docstring "WHY NOT A ROTATED PLACEMENT" for why this is
    absolute-offset shaped rather than a to-be-rotated flat local shape."""
    footprint, elevation = _flat_footprint(prim, idx)
    cx, cy, frame = _centroid_and_frame(footprint, curvature)
    position = np.array(frame["position_m"])
    normal = np.array(frame["normal"])
    tangent_u = np.array(frame["tangent_u"])
    tangent_v = np.array(frame["tangent_v"])
    center_point = position + elevation * normal

    local_offsets = [
        tuple(((vx - cx) * tangent_u + (vy - cy) * tangent_v).tolist()) for vx, vy in footprint
    ]
    thickness = None
    if prim.get("shape", "box") == "box":
        thickness = abs(float(prim["p2_m"][2]) - float(prim["p1_m"][2]))

    return {
        "name": str(prim.get("name", f"cell_{idx}")),
        "center_m": tuple(center_point.tolist()),
        "local_offsets_m": local_offsets,
        "normal": tuple(normal.tolist()),
        "thickness_m": thickness,
    }


def _macro_object_build_lines(objects: list[dict[str, Any]]) -> list[str]:
    """The per-unit-cell `Part::Feature`-building macro lines -- extracted
    so BOTH `generate_freecad_macro()` (STEP-export path) and
    `generate_freecad_fem_mesh_macro()` (FEM-mesh path, issue #288) build
    the exact same tilted-plane solid for the exact same input, and can
    never silently drift apart on how a unit cell's true 3D shape is
    constructed (see module docstring "WHY NOT A ROTATED PLACEMENT").
    Assumes the caller's own macro preamble has already initialized `doc`
    plus the three list variables `objects_built`, `built_shapes`, `errors`
    (those exact names -- this function's emitted lines reference them)."""
    lines: list[str] = []
    for obj in objects:
        name = obj["name"]
        lines.append(f"# --- {name} ---")
        lines.append("try:")
        lines.append(f"    pts = [App.Vector(*p) for p in {obj['local_offsets_m']!r}]")
        lines.append("    wire = Part.makePolygon(pts, True)")
        lines.append("    face = Part.Face([wire])")
        if obj["thickness_m"] is not None:
            extrude_vec = tuple(n * obj["thickness_m"] for n in obj["normal"])
            lines.append(f"    shape = face.extrude(App.Vector(*{extrude_vec!r}))")
        else:
            lines.append("    shape = face")
        lines.append(f'    feature = doc.addObject("Part::Feature", {name!r})')
        lines.append("    feature.Shape = shape")
        lines.append(
            f"    feature.Placement = App.Placement("
            f"App.Vector(*{obj['center_m']!r}), App.Rotation())"
        )
        lines.append(f"    objects_built.append({name!r})")
        lines.append("    built_shapes.append(shape)")
        lines.append("except Exception as exc:")
        lines.append(f"    errors.append({{'name': {name!r}, 'error': str(exc)}})")
    return lines


def generate_freecad_macro(
    primitives: list[dict[str, Any]],
    curvature: dict[str, Any],
    step_filename: str = "curved_unit_cell_array.step",
    status_filename: str = "curved_unit_cell_array_status.json",
    comment: str = "Generated by geometry.freecad_curved.generate_freecad_macro",
) -> str:
    """Generate a headless, self-contained FreeCAD Python macro (no
    dependency on this repo's own package -- FreeCADCmd runs a completely
    separate Python environment from this project's own venv, so nothing
    here can `import` anything from this repo) that builds `primitives`
    curvature-mapped onto `curvature` as a real Part::Feature per unit cell
    (box primitives correctly extruded along their TRUE local surface normal
    -- see module docstring), exports the whole array to a single STEP file
    via a Part.makeCompound(...), and writes a small JSON status file
    ({"objects_built": [...names...], "errors": [{"name", "error"}, ...],
    "step_file": <name> or null, "total_input": N}) so the calling Python
    process (run_freecad_curved_geometry() below) can read back what
    actually happened without parsing FreeCAD's own console log text.

    Run headlessly via `FreeCADCmd <this file>` (or `freecad --console
    <this file>`) -- see module docstring's FreeCADCmd/Application.cpp
    citations for exactly why a positional .py argument runs as a script
    with no GUI and no interactive prompt.
    """
    if not primitives:
        raise ValueError("primitives must be a non-empty list")
    objects = [_exact_curved_geometry(prim, curvature, idx) for idx, prim in enumerate(primitives)]

    lines: list[str] = [
        f"# {comment}",
        "# Headless FreeCAD macro -- run via `FreeCADCmd <this file>`.",
        "# See geometry/freecad_curved.py's module docstring for the FreeCAD",
        "# API citations (App.newDocument/Document.addObject/Part.makePolygon/",
        "# Part.Face/TopoShape.extrude/TopoShape.exportStep/Part.makeCompound).",
        "import json",
        "",
        "import FreeCAD as App",
        "import Part",
        "",
        'doc = App.newDocument("CurvedUnitCellArray")',
        "objects_built = []",
        "built_shapes = []",
        "errors = []",
    ]

    lines += _macro_object_build_lines(objects)

    lines += [
        "",
        "doc.recompute()",
        "",
        f"step_file = {step_filename!r}",
        "if built_shapes:",
        "    compound = Part.makeCompound(built_shapes)",
        "    compound.exportStep(step_file)",
        "else:",
        "    step_file = None",
        "",
        "status = {",
        '    "objects_built": objects_built,',
        '    "errors": errors,',
        '    "step_file": step_file,',
        f'    "total_input": {len(objects)},',
        "}",
        f"with open({status_filename!r}, 'w') as _status_fh:",
        "    json.dump(status, _status_fh)",
        "",
        "App.closeDocument(doc.Name)",
    ]
    return "\n".join(lines) + "\n"


def generate_freecad_fem_mesh_macro(
    primitives: list[dict[str, Any]],
    curvature: dict[str, Any],
    working_directory: str,
    mesh_max_size_m: float | None = None,
    status_filename: str = "curved_unit_cell_fem_mesh_status.json",
    comment: str = "Generated by geometry.freecad_curved.generate_freecad_fem_mesh_macro",
) -> str:
    """Generate a headless FreeCAD Python macro (issue #288) that builds the
    exact same tilted-plane curved solid `generate_freecad_macro()` builds
    (via the SAME `_macro_object_build_lines()` helper -- the two can never
    silently drift apart), keeps it as a live `Part::Feature` compound
    (instead of only exporting it to STEP), and drives FreeCAD's own FEM
    workbench meshing API (`ObjectsFem.makeMeshGmsh` +
    `femmesh.gmshtools.GmshTools`) against that exact compound -- see module
    docstring "FEM WORKBENCH MESHING" for the full primary-source citation
    list, the honest QProcess/no-GUI caveat, and why this does NOT also
    export STEP (a distinct, additive path from `generate_freecad_macro()`,
    which this ticket's own acceptance criteria require stay unchanged).

    `working_directory`: absolute path the mesh object's own `WorkingDirectory`
    property is set to -- this is where FreeCAD's FEM workbench actually
    writes the `.brep`/`.geo`/mesh files, so the caller (`run_freecad_fem_
    mesh_geometry()` below) must pass the SAME directory `FreeCADCmd` itself
    runs in, and must know it up front (unlike `generate_freecad_macro()`'s
    `step_filename`, which stays a bare relative name FreeCAD resolves
    against its own subprocess cwd).

    `mesh_max_size_m`: if given, sets `CharacteristicLengthMax` -- see module
    docstring's "UNIT CONVENTION THIS PATH INHERITS, NOT INTRODUCES" for why
    this is embedded as the SAME bare (unconverted) number `generate_
    freecad_macro()`'s own vertex coordinates already use, not a real
    meters-to-FreeCAD-internal-mm conversion. If omitted, `Characteristic
    LengthMax` is left at FreeCAD's own default (0.0, meaning "no cap" --
    Gmsh picks its own default sizing from the geometry alone).

    The written JSON status file's shape:
        {
          "objects_built": [...names...],
          "errors": [{"name", "error"}, ...],
          "mesh": {
              "mesh_ok": bool,
              "mesh_file": <absolute path> | None,
              "node_count": int,
              "element_counts": {"edge"/"triangle"/"quadrangle"/"tetra"/
                  "hexa"/"prism"/"pyramid": int, ...},
              "gmsh_exit_code": int | None,
              "gmsh_stderr": str,
              "note": str | None,   # set on ANY failure (GmshError, a
                  missing mesh file, or an unexpected exception) --
                  `mesh_ok=False` is never silent.
          },
          "total_input": N,
        }
    A per-object solid-build failure (same as `generate_freecad_macro()`) or
    a meshing failure are BOTH reported honestly in this status rather than
    raised -- the FreeCADCmd process itself still ran to completion (see
    module docstring's `ObjectTools._process_finished` citation for why a
    meshing failure needs this module's own explicit exit-code/file-
    existence check rather than trusting `FemMesh` being populated).
    """
    if not primitives:
        raise ValueError("primitives must be a non-empty list")
    objects = [_exact_curved_geometry(prim, curvature, idx) for idx, prim in enumerate(primitives)]

    lines: list[str] = [
        f"# {comment}",
        "# Headless FreeCAD FEM-workbench meshing macro -- run via `FreeCADCmd <this file>`.",
        "# See geometry/freecad_curved.py's module docstring 'FEM WORKBENCH MESHING'",
        "# section for the FreeCAD FEM API citations (ObjectsFem.makeMeshGmsh /",
        "# femmesh.gmshtools.GmshTools) this macro drives.",
        "import json",
        "import os",
        "",
        "import FreeCAD as App",
        "import Part",
        "",
        'doc = App.newDocument("CurvedUnitCellArray")',
        "objects_built = []",
        "built_shapes = []",
        "errors = []",
    ]
    lines += _macro_object_build_lines(objects)

    lines += [
        "",
        "doc.recompute()",
        "",
        "mesh_status = {",
        "    'mesh_ok': False,",
        "    'mesh_file': None,",
        "    'node_count': 0,",
        "    'element_counts': {},",
        "    'gmsh_exit_code': None,",
        "    'gmsh_stderr': '',",
        "    'note': None,",
        "}",
        "if built_shapes:",
        "    compound = Part.makeCompound(built_shapes)",
        '    compound_feature = doc.addObject("Part::Feature", "CurvedArrayCompound")',
        "    compound_feature.Shape = compound",
        "    doc.recompute()",
        "    try:",
        "        import ObjectsFem",
        "        from femmesh.gmshtools import GmshTools, GmshError",
        "",
        '        mesh_obj = ObjectsFem.makeMeshGmsh(doc, "CurvedArrayMesh")',
        "        mesh_obj.Shape = compound_feature",
        f"        mesh_obj.WorkingDirectory = {working_directory!r}",
        '        mesh_obj.ElementDimension = "3D"',
    ]
    if mesh_max_size_m is not None:
        lines.append(f"        mesh_obj.CharacteristicLengthMax = {mesh_max_size_m!r}")
    lines += [
        "        doc.recompute()",
        "        tool = GmshTools(mesh_obj)",
        "        tool.create_mesh()",
        "        mesh_status['gmsh_exit_code'] = tool.process.exitCode()",
        "        mesh_status['gmsh_stderr'] = bytes(",
        "            tool.process.readAllStandardError()",
        "        ).decode('utf-8', 'replace')",
        "        mesh_file = tool.temp_file_mesh",
        "        if os.path.exists(mesh_file):",
        "            if mesh_obj.FemMesh.NodeCount == 0:",
        "                # _process_finished only populates FemMesh on a clean",
        "                # QProcess exit signal -- re-read defensively (idempotent).",
        "                tool.update_properties()",
        "            mesh_status['mesh_ok'] = True",
        "            mesh_status['mesh_file'] = mesh_file",
        "            mesh_status['node_count'] = mesh_obj.FemMesh.NodeCount",
        "            mesh_status['element_counts'] = {",
        "                'edge': mesh_obj.FemMesh.EdgeCount,",
        "                'triangle': mesh_obj.FemMesh.TriangleCount,",
        "                'quadrangle': mesh_obj.FemMesh.QuadrangleCount,",
        "                'tetra': mesh_obj.FemMesh.TetraCount,",
        "                'hexa': mesh_obj.FemMesh.HexaCount,",
        "                'prism': mesh_obj.FemMesh.PrismCount,",
        "                'pyramid': mesh_obj.FemMesh.PyramidCount,",
        "            }",
        "        else:",
        "            mesh_status['note'] = (",
        "                'gmsh did not produce a mesh file at ' + mesh_file",
        "            )",
        "    except GmshError as exc:",
        "        mesh_status['note'] = 'GmshError: ' + str(exc)",
        "    except Exception as exc:",
        "        mesh_status['note'] = 'unexpected FEM meshing failure: ' + str(exc)",
        "else:",
        "    mesh_status['note'] = 'no unit-cell object built successfully -- see errors'",
        "",
        "status = {",
        '    "objects_built": objects_built,',
        '    "errors": errors,',
        '    "mesh": mesh_status,',
        f'    "total_input": {len(objects)},',
        "}",
        f"with open({status_filename!r}, 'w') as _status_fh:",
        "    json.dump(status, _status_fh)",
        "",
        "App.closeDocument(doc.Name)",
    ]
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Subprocess invocation -- follows simulation/elmer.py's/simulation/
# gprmax.py's own shell-out pattern (generate a script, subprocess.run the
# external tool, raise a local error type on failure, parse whatever
# structured output the tool actually wrote).
# ---------------------------------------------------------------------------


def _run_freecadcmd(
    script_path: Path,
    workdir: Path,
    executable: str | None = None,
    timeout_s: int = _DEFAULT_TIMEOUT_S,
) -> subprocess.CompletedProcess:
    """Invoke FreeCADCmd (or an equivalent headless FreeCAD executable) on
    `script_path` -- a single positional .py argument, no flags, per this
    module's own Application::processFiles()/runApplication() citation."""
    if not script_path.exists():
        raise FreecadGeometryError(f"FreeCAD macro file not found: {script_path}")
    exe = executable or os.getenv("FREECAD_BIN") or "FreeCADCmd"
    try:
        completed = subprocess.run(
            [exe, str(script_path)],
            cwd=workdir,
            capture_output=True,
            text=True,
            timeout=timeout_s,
            check=False,
        )
    except FileNotFoundError as exc:
        raise FreecadGeometryError(f"FreeCADCmd executable not found: {exe!r} ({exc})") from exc
    except subprocess.TimeoutExpired as exc:
        raise FreecadGeometryError(f"FreeCADCmd timed out after {timeout_s}s: {exc}") from exc
    if completed.returncode != 0:
        raise FreecadGeometryError(
            f"FreeCADCmd failed ({completed.returncode}): "
            f"{(completed.stderr or completed.stdout)[-4000:]}"
        )
    return completed


def run_freecad_curved_geometry(
    primitives: list[dict[str, Any]],
    curvature: dict[str, Any],
    workdir: str | None = None,
    executable: str | None = None,
    timeout_s: int = _DEFAULT_TIMEOUT_S,
    name_prefix: str = "cell",
) -> dict[str, Any]:
    """End-to-end: map `primitives` (a flat unit-cell layout) onto
    `curvature` (see map_unit_cell_layout_to_curved_surface()'s docstring
    for both shapes), generate a headless FreeCAD macro building the same
    array as a real, exact 3D solid model (see generate_freecad_macro()),
    run it via FreeCADCmd, and parse whatever status the macro wrote.

    The geometry-dict mapping happens FIRST, in pure Python, before any
    subprocess is invoked -- so a malformed/oversized unit-cell spec is
    rejected immediately (ValueError) rather than only failing deep inside a
    FreeCADCmd subprocess run.

    Returns:
        {
          "provenance": "SIMULATED",
          "simulator": "FreeCADCmd",
          "status": "COMPLETED",
          "workdir": str,
          "macro_file": str,
          "primitives": [...the geometry-dict "polygon" primitives...],
          "freecad": {
              "objects_built": [...names...],
              "errors": [...],
              "step_file": str | None,
              "total_input": int,
          } | {"objects_built": [], "errors": [], "step_file": None,
               "note": "<status file missing after a clean exit>"},
          "stdout": str,
        }

    Raises FreecadGeometryError if the FreeCADCmd subprocess itself fails
    (nonzero exit, timeout, or executable not found) -- matching this
    repo's other subprocess-based adapters (e.g. simulation.elmer.
    run_elmer_simulation), which propagate a subprocess failure rather than
    silently returning a degraded result. A per-object build failure INSIDE
    a successfully-run FreeCADCmd process (e.g. a self-intersecting polygon
    Part.Face() rejects) is NOT such a failure -- it is reported honestly in
    `freecad["errors"]` instead, since the process itself still ran to
    completion and other objects may have built successfully.
    """
    curved_primitives = map_unit_cell_layout_to_curved_surface(
        primitives, curvature, name_prefix=name_prefix
    )

    work_dir = Path(workdir) if workdir else Path(tempfile.mkdtemp(prefix="freecad_curved_"))
    work_dir.mkdir(parents=True, exist_ok=True)

    step_filename = "curved_unit_cell_array.step"
    status_filename = "curved_unit_cell_array_status.json"
    macro_file = work_dir / "build_curved_geometry.py"
    macro_file.write_text(
        generate_freecad_macro(
            primitives, curvature, step_filename=step_filename, status_filename=status_filename
        )
    )

    completed = _run_freecadcmd(macro_file, work_dir, executable=executable, timeout_s=timeout_s)

    status_path = work_dir / status_filename
    if status_path.exists():
        status = json.loads(status_path.read_text())
        step_file = status.get("step_file")
        freecad_result: dict[str, Any] = {
            "objects_built": status.get("objects_built", []),
            "errors": status.get("errors", []),
            "step_file": str(work_dir / step_file) if step_file else None,
            "total_input": status.get("total_input"),
        }
    else:
        freecad_result = {
            "objects_built": [],
            "errors": [],
            "step_file": None,
            "note": (
                f"{status_filename!r} was not found in the run's workdir after "
                "FreeCADCmd exited 0 -- either the macro's own final JSON-write step "
                "didn't execute (check stdout below), or (for a fake test executable "
                "standing in for FreeCADCmd) the fake script doesn't emit this file."
            ),
        }

    return {
        "provenance": "SIMULATED",
        "simulator": "FreeCADCmd",
        "status": "COMPLETED",
        "workdir": str(work_dir),
        "macro_file": str(macro_file),
        "primitives": curved_primitives,
        "freecad": freecad_result,
        "stdout": completed.stdout[-4000:],
    }


def run_freecad_fem_mesh_geometry(
    primitives: list[dict[str, Any]],
    curvature: dict[str, Any],
    workdir: str | None = None,
    executable: str | None = None,
    timeout_s: int = _DEFAULT_TIMEOUT_S,
    name_prefix: str = "cell",
    mesh_max_size_m: float | None = None,
) -> dict[str, Any]:
    """End-to-end: map `primitives` onto `curvature` (same pure-Python step
    `run_freecad_curved_geometry()` does), generate a headless FreeCAD macro
    that builds the same curved solid AND drives FreeCAD's own FEM workbench
    meshing API against it (`generate_freecad_fem_mesh_macro()` -- see that
    function's docstring and this module's docstring "FEM WORKBENCH
    MESHING" section), run it via FreeCADCmd, and parse whatever status the
    macro wrote.

    A SEPARATE function from `run_freecad_curved_geometry()` (not a flag on
    it) precisely so THAT function's existing STEP-export-only default
    behavior is untouched -- this ticket's own acceptance criteria require
    it, and this also means an existing caller of `run_freecad_curved_
    geometry()` is never affected by this function even existing.

    Returns:
        {
          "provenance": "SIMULATED",
          "simulator": "FreeCADCmd",
          "status": "COMPLETED",
          "workdir": str,
          "macro_file": str,
          "primitives": [...the geometry-dict "polygon" primitives...],
          "freecad": {
              "objects_built": [...names...],
              "errors": [...],
              "total_input": int | None,
              "mesh": {"mesh_ok": bool, "mesh_file": <absolute path> | None,
                  "node_count": int, "element_counts": {...},
                  "gmsh_exit_code": int | None, "gmsh_stderr": str,
                  "note": str | None},
          },
          "stdout": str,
        }

    Raises FreecadGeometryError only for a subprocess-level FreeCADCmd
    failure (nonzero exit, timeout, executable not found) -- matching
    `run_freecad_curved_geometry()`. A per-object solid-build failure or a
    FEM-meshing failure INSIDE a successfully-run FreeCADCmd process (e.g.
    gmsh not installed on the machine FreeCADCmd itself runs on) is NOT such
    a failure -- both are reported honestly in `freecad["errors"]`/
    `freecad["mesh"]` instead, never raised and never silently guessed.
    """
    curved_primitives = map_unit_cell_layout_to_curved_surface(
        primitives, curvature, name_prefix=name_prefix
    )

    work_dir = Path(workdir) if workdir else Path(tempfile.mkdtemp(prefix="freecad_fem_mesh_"))
    work_dir.mkdir(parents=True, exist_ok=True)
    work_dir = work_dir.resolve()

    status_filename = "curved_unit_cell_fem_mesh_status.json"
    macro_file = work_dir / "build_curved_fem_mesh.py"
    macro_file.write_text(
        generate_freecad_fem_mesh_macro(
            primitives,
            curvature,
            working_directory=str(work_dir),
            mesh_max_size_m=mesh_max_size_m,
            status_filename=status_filename,
        )
    )

    completed = _run_freecadcmd(macro_file, work_dir, executable=executable, timeout_s=timeout_s)

    status_path = work_dir / status_filename
    _no_mesh: dict[str, Any] = {
        "mesh_ok": False,
        "mesh_file": None,
        "node_count": 0,
        "element_counts": {},
        "gmsh_exit_code": None,
        "gmsh_stderr": "",
        "note": None,
    }
    if status_path.exists():
        status = json.loads(status_path.read_text())
        freecad_result: dict[str, Any] = {
            "objects_built": status.get("objects_built", []),
            "errors": status.get("errors", []),
            "total_input": status.get("total_input"),
            "mesh": status.get("mesh", {**_no_mesh, "note": "status file has no 'mesh' key"}),
        }
    else:
        missing_status_note = (
            f"{status_filename!r} was not found in the run's workdir after "
            "FreeCADCmd exited 0 -- either the macro's own final JSON-write step "
            "didn't execute (check stdout below), or (for a fake test executable "
            "standing in for FreeCADCmd) the fake script doesn't emit this file."
        )
        freecad_result = {
            "objects_built": [],
            "errors": [],
            "mesh": {**_no_mesh, "note": missing_status_note},
            "note": missing_status_note,
        }

    return {
        "provenance": "SIMULATED",
        "simulator": "FreeCADCmd",
        "status": "COMPLETED",
        "workdir": str(work_dir),
        "macro_file": str(macro_file),
        "primitives": curved_primitives,
        "freecad": freecad_result,
        "stdout": completed.stdout[-4000:],
    }
