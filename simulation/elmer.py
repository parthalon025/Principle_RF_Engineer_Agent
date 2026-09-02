"""Elmer FEM (VectorHelmholtz module) simulation adapter -- general
multiphysics-ready EM cross-check (issue #64).

WHY THIS ADAPTER EXISTS / WHY IT IS THE "LOWEST-FIT" ITEM IN ITS BATCH: Elmer
(github.com/ElmerCSC/elmerfem) is a general-purpose, multiphysics finite-
element suite whose primary user base is structural mechanics, CFD, and heat
transfer -- NOT electromagnetics. Its `VectorHelmholtz` solver module (a
curl-conforming edge-element solver for the time-harmonic Maxwell curl-curl
equation) is a genuine, real EM capability, but it is one physics module
among dozens, not an antenna/RF-focused tool. This adapter exists so the
agent has a general FEM cross-check option available for a FUTURE
multiphysics need (e.g. coupled EM/thermal analysis on a mounted "adaptive EM
skin"), not because it is expected to replace NEC2++/openEMS/HFSS for
everyday antenna work -- see "SCOPE AND LIMITATIONS" below for exactly what
that costs.

SOURCES CONSULTED (primary; all fetched directly from
github.com/ElmerCSC/elmerfem's `devel` branch -- the repository's default
branch -- via GitHub's contents/search APIs during implementation, plus
gmsh.info's own official texinfo reference manual for the Gmsh meshing
front-end. Accessed 2026-09-02):

  MESH GENERATION (Gmsh, a genuinely new dependency this repo has not used
  before -- see "MESHING DEPENDENCY" below):
  - Gmsh .geo scripting with the OpenCASCADE kernel: `SetFactory
    ("OpenCASCADE");` then `Box(tag) = {x, y, z, dx, dy, dz};` for an
    axis-aligned box primitive -- gmsh.info's own reference manual
    (gmsh.info/doc/texinfo/gmsh.txt) and its official `t16.geo`/`t18.geo`
    OpenCASCADE tutorials (gitlab.onelab.info/gmsh/gmsh, the project's own
    canonical repo).
  - `BooleanFragments{ Volume{a}; Delete; }{ Volume{b}; Delete; };` (list-
    returning form: `v() = BooleanFragments{...}{...};`) to conformally mesh
    two touching/overlapping OpenCASCADE volumes without duplicate
    interfaces -- gmsh.info reference manual, "Geometry commands" section,
    and the manual's own worked "spherical inclusions" example.
  - `Volume In BoundingBox{x1,y1,z1, x2,y2,z2}` / `Surface In BoundingBox
    {...}` (list-returning geometric selection queries) and the `Physical
    Volume(...)`/`Physical Surface(...)` grammar's `<+|->=` incremental
    add/remove operators -- gmsh.info reference manual, both the worked
    examples (`vin() = Volume In BoundingBox{...}; v() -= vin();`) and the
    formal grammar (`'Physical Volume ( EXPRESSION | STRING-EXPRESSION
    <, EXPRESSION> ) <+|->= { EXPRESSION-LIST };'`). Used here (see
    generate_gmsh_geo_script below) to robustly tag the excitation
    sub-region and the six outer faces of the simulation domain by their
    real geometric position rather than by an assumed/guessed OpenCASCADE
    entity-numbering convention.
  - `Mesh.MeshSizeMax = <value>;` as the current (non-deprecated) global
    maximum-element-size option -- gmsh.info reference manual, "Mesh
    options" section.
  - CLI invocation `gmsh file.geo -3 -format msh2 -o file.msh` -- gmsh.info
    reference manual's "Running Gmsh on your computer" section (`-3` for a
    3D mesh, `-format msh2`/`-o` for output format/file). The `-format
    msh2` flag is NOT optional for this pipeline -- see "MSH2, NOT MSH4"
    below.

  MESH CONVERSION (ElmerGrid):
  - Inline-mode CLI contract `ElmerGrid <in_format> <out_format>
    <in_file_stem> -out <out_name>`, with format code 14 = "Gmsh mesh
    format (.msh)" input and format code 2 = "ElmerSolver format (also
    partitioned .part format)" output: `Instructions()` in
    elmergrid/src/egnative.c, ElmerGrid's own built-in help text, fetched
    directly.
  - `-out str`: "name of the output file" per the same `Instructions()`
    text; confirmed (not just inferred from the help string) by reading
    `SaveElmerInput(struct FemType *data, ..., char *prefix, ...)` in
    elmergrid/src/egnative.c, whose body does `sprintf(directoryname,"%s",
    prefix)` then `mkdir(directoryname)`/`chdir(directoryname)` before
    writing `mesh.header`/`mesh.nodes`/`mesh.elements`/`mesh.boundary` --
    i.e. `-out`'s argument IS the ElmerSolver-native mesh output
    *directory* name, not a single-file name, for format code 2.
  - MSH2, NOT MSH4: ElmerGrid's own Gmsh-format-2 reader
    (`LoadGmshInput2` in elmergrid/src/egconvert.c) parses the legacy
    `$MeshFormat`/`$Nodes`/`$Elements` line-oriented sections (a plain
    "id x y z" line per node, "id type ntags tags... node-list" per
    element) -- NOT Gmsh's modern MSH4 default format's block-structured
    `$Entities`/`$Nodes`/`$Elements` layout. This is a real, easy-to-miss
    incompatibility (ElmerGrid predates MSH4): this module always passes
    `-format msh2` to gmsh (see run_gmsh_meshing below) rather than
    trusting gmsh's current default.
  - Physical-group tag numbers (from Gmsh's `Physical Volume(name, tag)`/
    `Physical Surface(name, tag)`) becoming Elmer's own Body/Boundary
    target indices (the numbers a .sif's `Body N`/`Target Boundaries`
    reference) is the standard, universally-documented ElmerGrid Gmsh-
    import workflow -- confirmed via `LoadGmshInput2`'s own per-element
    `tagphys` field read (elmergrid/src/egconvert.c), which is carried
    into the converted mesh's per-element body/boundary tag. This
    module's generate_gmsh_geo_script/generate_elmer_sif below therefore
    always assign an EXPLICIT numeric tag to every Physical Volume/Surface
    (never relying on Gmsh's auto-numbering) so the .sif's `Body`/`Target
    Boundaries` indices are deterministic and match by construction --
    reasoned from this standard convention and the `tagphys` read above,
    not independently re-traced through every line of ElmerGrid's mesh-
    writer to confirm byte-for-byte that tag N always becomes exactly
    index N with no renumbering; treat this specific mapping as
    reasoned-but-not-fully-source-verified (graded lower confidence than
    the CLI/format facts above, which were read directly).

  SOLVER INVOCATION (ElmerSolver):
  - `ElmerSolver [sif_filename]`: if a non-flag first CLI argument is
    given, it is used directly as the input .sif file's name (`ModelName =
    args(1) % astr`); otherwise ElmerSolver falls back to reading a file
    literally named `ELMERSOLVER_STARTINFO` in the current working
    directory, whose first line is the .sif filename -- `fem/src/
    ElmerSolver.F90`'s own `MAIN` program, fetched directly. This module
    always passes the .sif path as an explicit argument (see
    ElmerSimulator.run below), matching NEC2++'s/openEMS's own explicit-
    argument (not implicit-file) invocation style in this codebase.
  - The `*** Elmer Solver: ALL DONE ***` completion marker printed at the
    end of a normal run: `fem/src/ElmerSolver.F90`, `CALL Info( 'MAIN',
    '*** Elmer Solver: ALL DONE ***',Level=3 )`, fetched directly.
    parse_elmer_output() below matches this as a soft, non-authoritative
    completion signal (this module still trusts the process exit code as
    the primary success/failure signal, same as nec2pp.py/openems.py) --
    ElmerSolver's broader iteration/convergence log format was NOT
    independently traced byte-for-byte in this pass (unlike openEMS's
    progress-line regex, which cites specific transcribed sample text),
    so no attempt is made here to parse solver-iteration convergence
    detail from stdout.

  .SIF SOLVER-INPUT FORMAT AND VECTORHELMHOLTZ KEYWORDS:
  - Overall .sif block structure (`Header`/`Mesh DB "." "<dir>"`,
    `Simulation`, `Constants`, `Body N`, `Material N`, `Equation N`,
    `Solver N`, `Boundary Condition N`, MATC `$ name=expr` scalar
    definitions, and the `VectorHelmholtz`/`VectorHelmholtzCalcFields`
    Solver blocks' own keywords -- `Use Piola Transform`, `Use Gauss Law`,
    `Variable = E[E re:1 E im:1]`, the `Linear System *` settings,
    `Angular Frequency` on the Equation block, `Calculate Loads`/
    `Calculate Energy Inner Product`/`Calculate Magnetic Field Strength`/
    etc. on the Solver blocks): Elmer's OWN official test case for this
    exact solver, `fem/tests/VectorHelmholtzWaveguide/
    vectorhelmholtz_av.sif`, fetched directly and read verbatim -- the
    single most authoritative source available for this format (it is the
    Elmer developers' own worked example of driving VectorHelmholtz, not
    a third-party tutorial).
  - Exact Material/Body-Force/Boundary-Condition keyword spellings used by
    THIS solver specifically (as opposed to reasoning by analogy from the
    .sif example above, which comments some of these out): read directly
    from `fem/src/modules/VectorHelmholtz.F90`'s own `ListInitElementKeyword`
    registration calls --
      `ListInitElementKeyword(EpsCoeff_h,'Material','Relative Permittivity',
      InitIm=.TRUE.)`,
      `ListInitElementKeyword(MuCoeff_h,'Material','Relative Reluctivity',
      InitIm=.TRUE.)` -- NOTE: "Relative Reluctivity" (=1/mu_r), NOT
      "Relative Permeability" -- a real, easy-to-get-wrong detail this
      module would NOT have gotten right by analogy by openems.py's own
      "Mue" (relative permeability) convention; verified directly against
      VectorHelmholtz's own source rather than assumed,
      `ListInitElementKeyword(CondCoeff_h,'Material','Electric
      Conductivity')`,
      `ListInitElementKeyword(CurrDens_h,'Body Force','Current Density',
      InitIm=.TRUE.,InitVec3D=.TRUE.)` -- a 3-component vector keyword
      ("Current Density 1"/"2"/"3", each with a real and, per InitIm, an
      " im" imaginary companion) -- confirmed directly from source, not
      just from the .sif example's own commented-out (hence weaker)
      `!Current Density 2 = Real 1e8` line,
      `ListInitElementKeyword(Absorb_h,'Boundary Condition','Absorbing
      BC')` -- a standalone boolean flag (`ListGetElementLogical`), i.e.
      the solver computes its own default absorbing/impedance boundary
      term internally when this flag is set; this module uses this flag
      as-is for the default outer-boundary condition (see "PORTS ARE
      HAND-ASSEMBLED" below) rather than hand-deriving an "Electric Robin
      Coefficient" impedance value itself, since the flag's own internal
      formula was not independently traced in this pass,
      `ListInitElementKeyword(ElRobin_h,'Boundary Condition','Electric
      Robin Coefficient',InitIm=.TRUE.)` (used by the cited .sif example
      for its own waveguide-mode port, NOT used by this module -- see
      below).
  - `E Re`/`E Im` as Dirichlet boundary-condition keywords for a PEC
    (tangential-E=0) wall: this is Elmer's generic mechanism (any solver
    `Variable = Foo[Foo re:1 Foo im:1]` declaration gets Dirichlet-
    settable via `Foo Re`/`Foo Im` Boundary Condition keywords), used
    uncommented in the cited .sif example's own Boundary Condition 2
    (`E Re = Real 0.0` / `E Im = Real 0.0`).
  - `SaveScalars` output format: Solver block `Equation = "SaveScalars"`,
    `Procedure = "SaveData" "SaveScalars"`, `FileName = "..."` --
    confirmed both from the cited .sif example (Solver 3) and from
    `fem/src/modules/SaveData/SaveScalars.F90`'s own source, which also
    confirms (read directly) that it additionally writes a companion
    "<FileName>.names" file (`ScalarNamesFile = TRIM(ScalarsFile) //
    TRIM(".names")`) whose per-column lines are written as
    `WRITE(NamesUnit,'(I4,": ",A)') No+i, TRIM(ValueNames(No))` -- i.e.
    each line is a 4-column-wide integer, ": ", then the variable name,
    preceded by a literal "Variables in columns of matrix: " header line
    -- parse_elmer_output() below parses this exact, source-confirmed
    format to recover named scalar values.

  LICENSING (github.com/ElmerCSC/elmerfem, `devel` branch, read directly --
  see docs/LICENSE_MATRIX.md for the recorded rows):
  - A prior research pass found two primary sources disagreeing on LGPL
    v2.0 vs v2.1 for Elmer's core library. Resolved here by reading the
    actual license text files bundled in the repository (there is no
    single root `COPYING` file on the current `devel` branch -- only
    `LICENSE.md`, which is GPL-2 text, plus a `license_texts/` directory):
    `license_texts/LGPL-2.1.txt` is the verbatim FSF "GNU LESSER GENERAL
    PUBLIC LICENSE / Version 2.1, February 1999" text, and
    `license_texts/GPL-2.txt` is the verbatim "GNU GENERAL PUBLIC LICENSE
    / Version 2, June 1991" text. `license_texts/ElmerLicensePolicy.md`
    (Elmer's own "laymans description... in no way legally binding" of
    its licensing) states the two license VERSION NUMBERS BACKWARDS --
    "GPL (... v. 2.1) and LGPL license (... v. 2.0)" -- relative to every
    other primary source in the same repository, including the per-file
    SPDX-less header actually stamped on the VectorHelmholtz module
    itself: `fem/src/modules/VectorHelmholtz.F90`'s own header reads
    "GNU Lesser General Public License ... version 2.1 of the License",
    citing "../LGPL-2.1" by filename. The correct, source-confirmed
    answer is therefore: Elmer's core library (ElmerSolver,
    `libelmersolver`, `matc`, `fhutiter`, and most physical modules
    including VectorHelmholtz -- despite `license_texts/LICENSES`'s own
    summary text saying "most of the existing physical modules" are GPL,
    VectorHelmholtz.F90's own header says LGPL) is **LGPL v2.1**, and
    ElmerGUI/ElmerGrid (confirmed directly: `elmergrid/GPL-2` is a copy of
    the GPL-2 text, and `elmergrid/src/fempre.c`'s own header says "GNU
    General Public License ... version 2") are **GPL v2**. "ElmerParam"
    (named in this ticket alongside ElmerGUI/ElmerGrid) was NOT found as
    a present top-level component in the current elmerfem monorepo during
    this verification pass (a GitHub code search for "ElmerParam" in this
    repo returned no such directory) -- it may be historical/deprecated
    or folded elsewhere; recorded honestly as unconfirmed-present rather
    than assumed still GPL-licensed-and-shipping.
  - Gmsh itself (github.com/live-clones/gmsh, the project's own official
    GitHub mirror of its canonical gitlab.onelab.info repo) is GPL-2.0-
    or-later per its own `LICENSE.txt`, read directly ("Gmsh is provided
    under the terms of the GNU General Public License (GPL), Version 2 or
    later", with an explicit linking exception for Netgen/METIS/
    OpenCASCADE/ParaView).

SCOPE AND LIMITATIONS (read before trusting any result from this module):

  PORTS AND ANTENNA-SPECIFIC POST-PROCESSING ARE HAND-ASSEMBLED, NOT
  NATIVE. Unlike OpenParEM or Palace (or, in this codebase, HFSS/openEMS),
  Elmer's VectorHelmholtz module has NO native lumped/wave port object, no
  automatic S-parameter extraction, and no far-field/gain transform. This
  module builds two hand-assembled substitutes, both real, standard FEM
  techniques but genuinely narrower than a real port:
    - Excitation: an impressed volumetric electric current source
      ("Body Force" / "Current Density N", see citation above) inside a
      small user-specified sub-region -- not a calibrated, impedance-
      matched port with a known incident-wave normalization.
    - Outer boundary: either a PEC wall (tangential E=0, "E Re"/"E Im" =
      0 -- for a genuinely metallic boundary) or the solver's own
      "Absorbing BC = Logical True" flag (a generic impedance/radiation
      approximation, NOT the mode-specific waveguide "Electric Robin
      Coefficient" the cited .sif example computes for ITS OWN known
      waveguide cross-section/mode -- this module does not attempt that,
      since it requires geometry-specific mode parameters (beta0/kc) this
      module has no general way to compute).
  There is consequently NO S-parameter, far-field pattern, or antenna
  gain in this module's output -- `s_parameters`/`far_field` are always
  returned with `computed=False` and an explanatory note (matching
  openems.py's own honest-gap pattern), never fabricated. What IS real:
  the .sif/mesh generation and ElmerSolver invocation itself, and
  whatever named scalar values (e.g. "Energy Functional", if the
  VectorHelmholtzCalcFields solver's `Calculate Energy Functional` option
  computes one into a SaveScalars-written column) a real run's
  `scalar_values.dat`/`.names` files actually contain -- parsed
  best-effort, per-run, not guaranteed to contain any particular key.

  MESH GEOMETRY: a single rectangular domain (one bulk material, isotropic
  permittivity/reluctivity/conductivity) plus at most one rectangular
  excitation sub-region conformally fragmented out of it (see
  generate_gmsh_geo_script) -- no multi-material layering, no curved/
  cylindrical geometry, no multiple disjoint excitation regions. This is a
  narrower geometry model than openems.py's/hfss.py's own already-scoped-
  down box/cylinder primitive sets.

HONEST CAVEAT: none of gmsh, ElmerGrid, or ElmerSolver is installed in this
environment (this repo's existing NEC2++/openEMS/HFSS adapters are in the
same position). The .geo/.sif generation and subprocess-invocation
contracts above are built to the letter of the primary sources cited above;
they are exercised in tests only against small fake "gmsh"/"ElmerGrid"/
"ElmerSolver" scripts (see tests/test_elmer.py), NOT against real binaries.
Treat any result from this module as unverified end-to-end until it has
actually been run against real gmsh/ElmerGrid/ElmerSolver installations at
least once.
"""

import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from .base import SimulationResult, Simulator, SimulatorError

# Numeric Gmsh Physical Volume/Surface tags this module always assigns
# explicitly (never left to Gmsh's auto-numbering) so the .sif's own
# `Body N` / `Target Boundaries` indices are deterministic -- see this
# module's header comment on why an explicit tag is used everywhere.
_BULK_BODY_TAG = 1
_EXCITATION_BODY_TAG = 2
_FACE_TAGS = {
    "x_min": 101,
    "x_max": 102,
    "y_min": 103,
    "y_max": 104,
    "z_min": 105,
    "z_max": 106,
}


def _fmt(value: float) -> str:
    return f"{float(value):.6g}"


class ElmerSimulator(Simulator):
    """Wraps only the `ElmerSolver` binary invocation (the Simulator
    contract's one `run()` method) -- mesh generation (gmsh) and mesh
    conversion (ElmerGrid) are separate pipeline stages, run by
    run_elmer_simulation() below via run_gmsh_meshing()/
    run_elmergrid_conversion(), not part of this class. This mirrors
    nec2pp.py's Nec2ppSimulator (one binary, explicit CLI-argument
    invocation) rather than trying to fold three different binaries into
    one Simulator.run() call."""

    name = "Elmer/VectorHelmholtz"

    def __init__(self, executable: str | None = None):
        self.executable = executable or os.getenv("ELMERSOLVER_BIN", "ElmerSolver")

    def run(self, job: dict) -> SimulationResult:
        sif_file = Path(job["sif_file"]).resolve()
        workdir = Path(job.get("workdir", sif_file.parent)).resolve()
        if not sif_file.exists():
            raise SimulatorError(f"Elmer .sif file not found: {sif_file}")

        # ElmerSolver's own CLI contract (see module docstring citation):
        # a non-flag first argument is used directly as the input .sif
        # filename -- no implicit ELMERSOLVER_STARTINFO file needed (or
        # written) when the filename is passed explicitly like this.
        timeout_s = int(job.get("timeout_s", 1800))
        try:
            completed = subprocess.run(
                [self.executable, str(sif_file)],
                cwd=workdir,
                capture_output=True,
                text=True,
                timeout=timeout_s,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise SimulatorError(
                f"ElmerSolver timed out after {timeout_s}s: {exc}"
            ) from exc
        if completed.returncode != 0:
            raise SimulatorError(
                f"ElmerSolver failed ({completed.returncode}): {completed.stderr[-4000:]}"
            )

        return SimulationResult(
            simulator=self.name,
            status="COMPLETED",
            workdir=workdir,
            outputs={"stdout": completed.stdout[-8000:]},
        )


# ---------------------------------------------------------------------------
# Gmsh .geo generation and invocation (mesh generation stage).
# ---------------------------------------------------------------------------


def _face_bbox_selector(
    p1_m: list[float], p2_m: list[float], face: str, eps: float
) -> str:
    """Return a Gmsh `In BoundingBox{...}` argument list selecting a thin
    slab at the given outer face ("x_min"/"x_max"/"y_min"/"y_max"/
    "z_min"/"z_max") of the box spanned by p1_m/p2_m -- see module
    docstring citation for `Surface/Volume In BoundingBox{...}`."""
    x1, y1, z1 = (min(p1_m[i], p2_m[i]) for i in range(3))
    x2, y2, z2 = (max(p1_m[i], p2_m[i]) for i in range(3))
    if face == "x_min":
        lo, hi = (x1, y1, z1), (x1, y2, z2)
    elif face == "x_max":
        lo, hi = (x2, y1, z1), (x2, y2, z2)
    elif face == "y_min":
        lo, hi = (x1, y1, z1), (x2, y1, z2)
    elif face == "y_max":
        lo, hi = (x1, y2, z1), (x2, y2, z2)
    elif face == "z_min":
        lo, hi = (x1, y1, z1), (x2, y2, z1)
    elif face == "z_max":
        lo, hi = (x1, y1, z2), (x2, y2, z2)
    else:
        raise ValueError(f"face must be one of {sorted(_FACE_TAGS)}, got {face!r}")
    return (
        f"{_fmt(lo[0] - eps)},{_fmt(lo[1] - eps)},{_fmt(lo[2] - eps)}, "
        f"{_fmt(hi[0] + eps)},{_fmt(hi[1] + eps)},{_fmt(hi[2] + eps)}"
    )


def generate_gmsh_geo_script(geometry: dict[str, Any]) -> str:
    """Generate a Gmsh OpenCASCADE .geo script meshing `geometry`'s
    rectangular domain (plus, optionally, one rectangular excitation
    sub-region conformally fragmented out of it), tagging the bulk/
    excitation volumes and the domain's six outer faces with explicit
    numeric Physical Volume/Surface tags -- see this module's header
    comment for the full Gmsh-syntax citation and the tag-number scheme
    (_BULK_BODY_TAG/_EXCITATION_BODY_TAG/_FACE_TAGS above).

    `geometry` shape (meters, matching this codebase's established
    nec2pp.py/openems.py/hfss.py convention):
        {
          "domain": {"p1_m": [x,y,z], "p2_m": [x,y,z]},   # required
          "excitation": {                                  # optional
              "p1_m": [x,y,z], "p2_m": [x,y,z],   # must lie inside domain
          },
          "mesh_max_size_m": float,   # optional; default domain's
              smallest extent / 10 (a coarse heuristic, not a mesh-
              convergence-verified value -- override for real use).
        }
    """
    domain = geometry.get("domain")
    if not domain or "p1_m" not in domain or "p2_m" not in domain:
        raise ValueError("geometry['domain'] must supply p1_m/p2_m")
    dp1, dp2 = domain["p1_m"], domain["p2_m"]
    dx1, dy1, dz1 = (min(dp1[i], dp2[i]) for i in range(3))
    dx2, dy2, dz2 = (max(dp1[i], dp2[i]) for i in range(3))
    extents = (dx2 - dx1, dy2 - dy1, dz2 - dz1)
    if any(e <= 0 for e in extents):
        raise ValueError("geometry['domain'] p1_m/p2_m must span a non-degenerate box")
    eps = min(extents) * 1e-6

    mesh_max_size = geometry.get("mesh_max_size_m", min(extents) / 10.0)

    lines: list[str] = [
        '// Generated by simulation.elmer.generate_gmsh_geo_script',
        'SetFactory("OpenCASCADE");',
        f"eps = {_fmt(eps)};",
        f"Box(1) = {{{_fmt(dx1)}, {_fmt(dy1)}, {_fmt(dz1)}, "
        f"{_fmt(dx2 - dx1)}, {_fmt(dy2 - dy1)}, {_fmt(dz2 - dz1)}}};",
    ]

    excitation = geometry.get("excitation")
    has_excitation = bool(excitation)
    if has_excitation:
        ep1, ep2 = excitation["p1_m"], excitation["p2_m"]
        ex1, ey1, ez1 = (min(ep1[i], ep2[i]) for i in range(3))
        ex2, ey2, ez2 = (max(ep1[i], ep2[i]) for i in range(3))
        inside = (
            dx1 <= ex1 and ex2 <= dx2 and dy1 <= ey1 and ey2 <= dy2 and dz1 <= ez1 and ez2 <= dz2
        )
        if not inside:
            raise ValueError("geometry['excitation'] must lie inside geometry['domain']")
        lines.append(
            f"Box(2) = {{{_fmt(ex1)}, {_fmt(ey1)}, {_fmt(ez1)}, "
            f"{_fmt(ex2 - ex1)}, {_fmt(ey2 - ey1)}, {_fmt(ez2 - ez1)}}};"
        )
        lines.append("BooleanFragments{ Volume{1}; Delete; }{ Volume{2}; Delete; };")
        lines.append(
            "v_exc() = Volume In BoundingBox{"
            f"{_fmt(ex1 - eps)}, {_fmt(ey1 - eps)}, {_fmt(ez1 - eps)}, "
            f"{_fmt(ex2 + eps)}, {_fmt(ey2 + eps)}, {_fmt(ez2 + eps)}"
            "};"
        )
        lines.append(
            "v_dom() = Volume In BoundingBox{"
            f"{_fmt(dx1 - eps)}, {_fmt(dy1 - eps)}, {_fmt(dz1 - eps)}, "
            f"{_fmt(dx2 + eps)}, {_fmt(dy2 + eps)}, {_fmt(dz2 + eps)}"
            "};"
        )
        lines.append(f'Physical Volume("bulk", {_BULK_BODY_TAG}) = v_dom();')
        lines.append(f'Physical Volume("bulk", {_BULK_BODY_TAG}) -= v_exc();')
        lines.append(f'Physical Volume("excitation", {_EXCITATION_BODY_TAG}) = v_exc();')
    else:
        lines.append(f'Physical Volume("bulk", {_BULK_BODY_TAG}) = {{1}};')

    for face, tag in _FACE_TAGS.items():
        bbox = _face_bbox_selector([dx1, dy1, dz1], [dx2, dy2, dz2], face, eps)
        lines.append(f"s_{face}() = Surface In BoundingBox{{{bbox}}};")
        lines.append(f'Physical Surface("{face}", {tag}) = s_{face}();')

    lines.append(f"Mesh.MeshSizeMax = {_fmt(mesh_max_size)};")
    lines.append("Mesh 3;")
    return "\n".join(lines) + "\n"


def run_gmsh_meshing(
    geo_file: Path,
    msh_file: Path,
    workdir: Path,
    executable: str | None = None,
    timeout_s: int = 600,
) -> None:
    """Invoke gmsh to mesh `geo_file` into `msh_file`, forcing the legacy
    MSH2 ASCII format ElmerGrid's own Gmsh-format reader understands (see
    module docstring's "MSH2, NOT MSH4" citation) -- gmsh's own current
    default output format is newer MSH4, which ElmerGrid cannot read."""
    if not geo_file.exists():
        raise SimulatorError(f"gmsh .geo file not found: {geo_file}")
    exe = executable or os.getenv("GMSH_BIN", "gmsh")
    try:
        completed = subprocess.run(
            [exe, str(geo_file), "-3", "-format", "msh2", "-o", str(msh_file)],
            cwd=workdir,
            capture_output=True,
            text=True,
            timeout=timeout_s,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise SimulatorError(f"gmsh meshing timed out after {timeout_s}s: {exc}") from exc
    if completed.returncode != 0:
        raise SimulatorError(
            f"gmsh meshing failed ({completed.returncode}): "
            f"{(completed.stderr or completed.stdout)[-4000:]}"
        )


# ---------------------------------------------------------------------------
# ElmerGrid mesh conversion (Gmsh .msh -> ElmerSolver-native mesh directory).
# ---------------------------------------------------------------------------


def run_elmergrid_conversion(
    msh_file: Path,
    mesh_dir_name: str,
    workdir: Path,
    executable: str | None = None,
    timeout_s: int = 300,
) -> Path:
    """Convert `msh_file` (Gmsh MSH2 format) into an ElmerSolver-native
    mesh directory named `mesh_dir_name` inside `workdir`, via ElmerGrid's
    inline-mode CLI contract `ElmerGrid 14 2 <stem> -out <mesh_dir_name>`
    (format 14 = Gmsh input, format 2 = ElmerSolver output -- see module
    docstring citation for both the CLI contract and the `-out`-is-a-
    directory-name confirmation). Returns the resulting mesh directory
    path."""
    if not msh_file.exists():
        raise SimulatorError(f"Gmsh mesh file not found: {msh_file}")
    exe = executable or os.getenv("ELMERGRID_BIN", "ElmerGrid")
    stem = msh_file.with_suffix("").name
    try:
        completed = subprocess.run(
            [exe, "14", "2", stem, "-out", mesh_dir_name],
            cwd=workdir,
            capture_output=True,
            text=True,
            timeout=timeout_s,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise SimulatorError(f"ElmerGrid timed out after {timeout_s}s: {exc}") from exc
    if completed.returncode != 0:
        raise SimulatorError(
            f"ElmerGrid conversion failed ({completed.returncode}): "
            f"{(completed.stderr or completed.stdout)[-4000:]}"
        )
    return workdir / mesh_dir_name


# ---------------------------------------------------------------------------
# .sif solver-input generation.
# ---------------------------------------------------------------------------


def generate_elmer_sif(
    geometry: dict[str, Any],
    frequency_hz: float,
    mesh_dir_name: str,
    comment: str = "Generated by run_elmer_simulation",
) -> str:
    """Generate an Elmer .sif solver-input file driving the VectorHelmholtz
    module at `frequency_hz`, referencing the mesh directory
    `mesh_dir_name` (created by run_elmergrid_conversion, expected to live
    alongside the .sif file). See this module's header comment for the
    full block/keyword citation, and "SCOPE AND LIMITATIONS" for exactly
    what the excitation/boundary-condition modeling here does and does
    not represent.

    `geometry` shape adds, to generate_gmsh_geo_script's own "domain"/
    "excitation" keys:
        {
          "material": {                 # optional, defaults to vacuum
              "epsilon_r": float (default 1.0),
              "epsilon_r_im": float (default 0.0),
              "relative_reluctivity": float (default 1.0),   # = 1/mu_r;
                  VectorHelmholtz's own Material keyword -- see module
                  docstring citation -- NOT "Relative Permeability".
              "relative_reluctivity_im": float (default 0.0),
              "electric_conductivity_s_m": float (default 0.0),
          },
          "excitation": {                # optional; adds to the domain/
              ...                        # excitation keys already shown
              "current_density_a_m2": [Jx, Jy, Jz],   # real parts; at
                  least one component required if "excitation" is given
              "current_density_im_a_m2": [Jx, Jy, Jz],   # optional,
                  default [0, 0, 0]
          },
          "pec_faces": ["x_min", "x_max", "y_min", "y_max", "z_min",
              "z_max"],   # optional subset of the domain's outer faces;
              PEC (tangential E=0) instead of the default "Absorbing BC".
        }
    """
    if not geometry.get("domain"):
        raise ValueError("geometry['domain'] is required")

    material = geometry.get("material", {})
    eps_r = material.get("epsilon_r", 1.0)
    eps_r_im = material.get("epsilon_r_im", 0.0)
    reluc = material.get("relative_reluctivity", 1.0)
    reluc_im = material.get("relative_reluctivity_im", 0.0)
    sigma = material.get("electric_conductivity_s_m", 0.0)

    excitation = geometry.get("excitation")
    pec_faces = set(geometry.get("pec_faces", []))
    unknown_faces = pec_faces - set(_FACE_TAGS)
    if unknown_faces:
        raise ValueError(f"pec_faces contains unknown face name(s): {sorted(unknown_faces)}")

    lines: list[str] = [
        f"! {comment}",
        "Check Keywords \"Warn\"",
        "",
        "Header",
        f'  Mesh DB "." "{mesh_dir_name}"',
        "End",
        "",
        "Simulation",
        "  Max Output Level = 5",
        '  Coordinate System = "Cartesian"',
        "  Simulation Type = Steady",
        "  Steady State Max Iterations = 1",
        "  Output Intervals(1) = 1",
        "End",
        "",
        "Constants",
        "End",
        "",
        f"$ w = 2*pi*({_fmt(frequency_hz)})",
        "",
        f"Body {_BULK_BODY_TAG}",
        "  Equation = 1",
        "  Material = 1",
        "End",
    ]

    if excitation:
        lines += [
            "",
            f"Body {_EXCITATION_BODY_TAG}",
            "  Equation = 1",
            "  Material = 1",
            "  Body Force = 1",
            "End",
        ]

    lines += [
        "",
        "Material 1",
        f"  Relative Permittivity = Real {_fmt(eps_r)}",
        f"  Relative Permittivity im = Real {_fmt(eps_r_im)}",
        f"  Relative Reluctivity = Real {_fmt(reluc)}",
        f"  Relative Reluctivity im = Real {_fmt(reluc_im)}",
        f"  Electric Conductivity = Real {_fmt(sigma)}",
        "End",
        "",
        "Equation 1",
        "  Active Solvers(2) = 1 2",
        "  Angular Frequency = Real $w",
        "End",
    ]

    if excitation:
        j_re = excitation.get("current_density_a_m2")
        if not j_re or len(j_re) != 3:
            raise ValueError(
                "geometry['excitation']['current_density_a_m2'] must be a [Jx, Jy, Jz] list"
            )
        j_im = excitation.get("current_density_im_a_m2", [0.0, 0.0, 0.0])
        lines += ["", "Body Force 1"]
        for i in range(3):
            lines.append(f"  Current Density {i + 1} = Real {_fmt(j_re[i])}")
            lines.append(f"  Current Density {i + 1} im = Real {_fmt(j_im[i])}")
        lines.append("End")

    lines += [
        "",
        "Solver 1",
        '  Equation = "VectorHelmholtz"',
        "  Use Piola Transform = Logical True",
        '  Procedure = "VectorHelmholtz" "VectorHelmholtzSolver"',
        "  Variable = E[E re:1 E im:1]",
        "  Linear System Symmetric = False",
        '  Linear System Solver = String "Iterative"',
        "  Linear System Iterative Method = String GCR",
        '  Linear System Preconditioning = String "ILUT"',
        "  Linear System ILUT Tolerance = Real 3e-3",
        "  Linear System Max Iterations = Integer 4000",
        "  Linear System Convergence Tolerance = 1.0e-7",
        "  Linear System Abort Not Converged = False",
        "  Steady State Convergence Tolerance = 1e-09",
        "  Calculate Loads = Logical True",
        "  Calculate Energy Inner Product = Logical True",
        "End",
        "",
        "Solver 2",
        '  Equation = "calcfields"',
        '  Procedure = "VectorHelmholtz" "VectorHelmholtzCalcFields"',
        "  Calculate Elemental Fields = Logical True",
        "  Calculate Magnetic Field Strength = Logical True",
        "  Calculate Magnetic Flux Density = Logical True",
        "  Calculate Poynting vector = Logical True",
        "  Calculate Electric field = Logical True",
        "  Calculate Energy Functional = Logical True",
        "  Steady State Convergence Tolerance = 1",
        '  Linear System Solver = "Iterative"',
        "  Linear System Preconditioning = None",
        "  Linear System Max Iterations = 5000",
        "  Linear System Iterative Method = CG",
        "  Linear System Convergence Tolerance = 1.0e-9",
        "End",
        "",
        "Solver 3",
        '  Equation = "SaveScalars"',
        '  Procedure = "SaveData" "SaveScalars"',
        '  FileName = "scalar_values.dat"',
        "End",
    ]

    bc_index = 0
    for face, tag in _FACE_TAGS.items():
        bc_index += 1
        lines += ["", f"Boundary Condition {bc_index}", f"  Target Boundaries(1) = {tag}"]
        if face in pec_faces:
            lines += ["  E Re = Real 0.0", "  E Im = Real 0.0"]
        else:
            lines.append("  Absorbing BC = Logical True")
        lines.append("End")

    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Output parsing.
# ---------------------------------------------------------------------------

# The literal completion marker ElmerSolver prints on a normal finish -- see
# module docstring citation. Matched as a soft signal only; process exit
# code remains the authoritative success/failure check (ElmerSimulator.run).
_ALL_DONE_RE = re.compile(r"Elmer Solver:\s*ALL DONE", re.IGNORECASE)

# Matches one column line of a SaveScalars ".names" file, e.g.
#   "   3: res: VectorHelmholtz" -- see module docstring citation
# (SaveScalars.F90's own `WRITE(NamesUnit,'(I4,": ",A)') No+i,
# TRIM(ValueNames(No))`).
_SCALAR_NAME_LINE_RE = re.compile(r"^\s*(\d+):\s*(.+?)\s*$")


def _parse_save_scalars(workdir: Path, filename: str = "scalar_values.dat") -> dict[str, Any]:
    """Best-effort parse of a SaveScalars output (see module docstring
    citation for the exact ".names" companion-file format this reads).
    Returns {"computed": False, "note": ...} (never a guess) when either
    file is missing or the row/column counts don't line up cleanly --
    this is deliberately conservative, not defensive-and-silent."""
    data_path = workdir / filename
    names_path = workdir / f"{filename}.names"
    if not data_path.exists() or not names_path.exists():
        return {
            "computed": False,
            "note": (
                f"SaveScalars output ({filename!r} plus its {filename!r}.names "
                "companion, see simulation/elmer.py's module docstring citation "
                "for the exact format) was not found in the run's workdir -- "
                "either the run didn't reach Solver 3, or (for a fake test "
                "executable) the fake script doesn't emit these files."
            ),
        }

    names_text = names_path.read_text()
    names_lines = names_text.splitlines()
    try:
        header_idx = next(
            i for i, line in enumerate(names_lines) if "Variables in columns" in line
        )
    except StopIteration:
        return {
            "computed": False,
            "note": (
                f"{filename}.names does not contain the expected "
                "'Variables in columns of matrix:' header line -- see module "
                "docstring citation for the format this parser expects."
            ),
        }
    columns: dict[int, str] = {}
    for line in names_lines[header_idx + 1 :]:
        match = _SCALAR_NAME_LINE_RE.match(line)
        if match:
            columns[int(match.group(1))] = match.group(2)
    if not columns:
        return {
            "computed": False,
            "note": f"No '<N>: <name>' column lines found in {filename}.names.",
        }

    data_lines = [ln for ln in data_path.read_text().splitlines() if ln.strip()]
    if not data_lines:
        return {"computed": False, "note": f"{filename} has no data rows."}
    last_row = data_lines[-1].split()
    try:
        values = [float(tok) for tok in last_row]
    except ValueError:
        return {
            "computed": False,
            "note": f"Could not parse {filename}'s last row as numeric values: {last_row!r}",
        }

    max_col = max(columns)
    if max_col > len(values):
        return {
            "computed": False,
            "note": (
                f"{filename}.names declares {max_col} column(s) but {filename}'s "
                f"last row only has {len(values)} value(s) -- refusing to guess "
                "a misaligned mapping."
            ),
        }
    named_values = {columns[idx]: values[idx - 1] for idx in sorted(columns)}
    return {"computed": True, "values": named_values, "source_file": str(data_path)}


def parse_elmer_output(raw_output: str, workdir: str | Path | None = None) -> dict[str, Any]:
    """Parse ElmerSolver's stdout plus (when `workdir` is given) its
    SaveScalars output into a structured, honestly-gapped result. See
    this module's header comment "SCOPE AND LIMITATIONS": `s_parameters`
    and `far_field` are ALWAYS computed=False here -- VectorHelmholtz has
    no native antenna-specific post-processing for either, so this
    function never fabricates them, unlike (for real port-probe data)
    simulation/openems.py's S-parameter extraction."""
    completed_normally = bool(_ALL_DONE_RE.search(raw_output))

    if workdir is not None:
        raw_scalars = _parse_save_scalars(Path(workdir))
    else:
        raw_scalars = {
            "computed": False,
            "note": "No workdir given to parse_elmer_output() -- nothing was read.",
        }

    return {
        "completed_normally": completed_normally,
        "raw_scalars": raw_scalars,
        "s_parameters": {
            "computed": False,
            "note": (
                "Elmer's VectorHelmholtz module has no native S-parameter "
                "post-processing -- this module's own excitation/boundary "
                "modeling is a hand-assembled impressed-current-source "
                "approximation, not a calibrated port (see simulation/"
                "elmer.py's module docstring 'SCOPE AND LIMITATIONS')."
            ),
        },
        "far_field": {
            "computed": False,
            "note": (
                "Elmer's VectorHelmholtz module has no native far-field/gain "
                "post-processing tool (see simulation/elmer.py's module "
                "docstring 'SCOPE AND LIMITATIONS')."
            ),
        },
        "gain_dbi": None,
    }


# ---------------------------------------------------------------------------
# End-to-end orchestration.
# ---------------------------------------------------------------------------


def run_elmer_simulation(
    geometry: dict[str, Any],
    frequency_hz: float,
    timeout_s: int = 1800,
    gmsh_timeout_s: int = 600,
    elmergrid_timeout_s: int = 300,
    gmsh_executable: str | None = None,
    elmergrid_executable: str | None = None,
    elmersolver_executable: str | None = None,
    workdir: str | None = None,
) -> dict[str, Any]:
    """Generate a Gmsh .geo script from structured geometry, mesh it (gmsh),
    convert the mesh to ElmerSolver's native format (ElmerGrid), generate a
    VectorHelmholtz .sif from the same geometry, run it (ElmerSolver), and
    parse whatever raw output is available -- tagged with SIMULATED
    provenance. See this module's header comment for the full citation
    list and "SCOPE AND LIMITATIONS" for what is and is not computed
    (no S-parameters, no far-field/gain -- see parse_elmer_output)."""
    work_dir = Path(workdir) if workdir else Path(tempfile.mkdtemp(prefix="elmer_"))
    work_dir.mkdir(parents=True, exist_ok=True)

    geo_file = work_dir / "model.geo"
    geo_file.write_text(generate_gmsh_geo_script(geometry))

    msh_file = work_dir / "model.msh"
    run_gmsh_meshing(
        geo_file, msh_file, work_dir, executable=gmsh_executable, timeout_s=gmsh_timeout_s
    )

    mesh_dir_name = "elmer_mesh"
    mesh_dir = run_elmergrid_conversion(
        msh_file,
        mesh_dir_name,
        work_dir,
        executable=elmergrid_executable,
        timeout_s=elmergrid_timeout_s,
    )

    sif_file = work_dir / "case.sif"
    sif_file.write_text(generate_elmer_sif(geometry, frequency_hz, mesh_dir_name))

    simulator = ElmerSimulator(executable=elmersolver_executable)
    result = simulator.run(
        {"sif_file": str(sif_file), "workdir": str(work_dir), "timeout_s": timeout_s}
    )
    parsed = parse_elmer_output(result.outputs.get("stdout", ""), workdir=work_dir)

    return {
        "provenance": "SIMULATED",
        "simulator": result.simulator,
        "status": result.status,
        "workdir": str(result.workdir),
        "geo_file": str(geo_file),
        "msh_file": str(msh_file),
        "mesh_dir": str(mesh_dir),
        "sif_file": str(sif_file),
        "completed_normally": parsed["completed_normally"],
        "raw_scalars": parsed["raw_scalars"],
        "s_parameters": parsed["s_parameters"],
        "far_field": parsed["far_field"],
        "gain_dbi": parsed["gain_dbi"],
    }
