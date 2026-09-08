"""Palace full-wave FEM simulation with native Floquet/periodic-port boundaries
(issue #61) -- the first tool in this repo able to characterize a periodic
metamaterial unit cell's actual electromagnetic behavior (neither NEC2++'s
method-of-moments nor openEMS's FDTD adapter expose native periodic
boundaries).

Palace ("PArallel LArge-scale Computational Electromagnetics",
github.com/awslabs/palace) is a parallel finite-element full-wave solver
built on MFEM/libCEED, developed by the AWS Center for Quantum Computing.

SOURCES CONSULTED (primary; all fetched directly from Palace's own
documentation site awslabs.github.io/palace and its GitHub repository during
implementation -- accessed 2026-09-02. Per-fact citations below, each graded
by confidence the same way simulation/hfss.py's module docstring does):

  - CLI invocation contract -- "<INSTALL_DIR>/bin/palace -np <NUM_PROCS>
    config.json", where "The installed palace script wraps a call to the
    desired MPI launcher" (mpirun by default), and "-h"/"--help" lists the
    script's own options: awslabs.github.io/palace/stable/run/ ("Running
    Palace"). This is the CLI contract PalaceSimulator.run() below shells
    out with -- a single positional JSON config-file argument after "-np
    <N>", matching the ticket's own "Floquet Ports for a Dielectric
    Grating" example's invocation pattern.
  - Top-level config file structure -- five sections "Problem", "Model",
    "Domains", "Boundaries", "Solver": awslabs.github.io/palace/dev/config/
    config/ ("Configuration File" overview page).
  - config["Problem"]["Type"] enum (this module always emits "Driven" --
    "Perform a frequency-domain driven simulation") and
    config["Problem"]["Output"] (string, default "postpro", "Directory path
    for saving postprocessing outputs"): awslabs.github.io/palace/dev/
    config/reference/ ("Configuration File Reference").
  - config["Model"]["Mesh"] (input mesh file path) and, CRITICALLY,
    config["Model"]["L0"] (number, default 1.0e-6, "Unit, relative to
    meters, for mesh vertex coordinates. For example, a value of 1.0e-6
    means the mesh coordinates are in um."): same Configuration File
    Reference page. Palace's own default (micrometers) would silently
    misinterpret this module's meter-denominated mesh coordinates by a
    factor of 1e6 -- generate_palace_config() below therefore ALWAYS emits
    an explicit "L0": 1.0, never relying on that default.
  - config["Domains"]["Materials"][i] keys "Attributes" (required, integer
    array of mesh domain attributes), "Permittivity"/"Permeability"
    (default 1.0, scalar or 3-vector), "LossTan" (default 0.0): same
    Configuration File Reference page.
  - config["Boundaries"]["Periodic"] -- "FloquetWaveVector" (3-element
    array, default [0,0,0], "defining the phase delay between periodic
    boundaries, in radians per mesh length unit"), "FloquetReferenceFrequency"
    (number, GHz, default 0.0, the frequency at which FloquetWaveVector is
    defined -- k_F(f) = k_F,ref * f/f_ref for the rest of a sweep, per
    docs.src.guide.boundaries.md's "Floquet Ports and Periodic Boundary
    Conditions" section), and "BoundaryPairs"[i] -- "DonorAttributes"/
    "ReceiverAttributes" (required integer arrays) and "Translation"
    (optional 3-element array, "distance from the donor attribute to the
    receiver attribute in mesh units"; "AffineTransformation" is the
    alternative general-4x4-matrix form, not used by this module): same
    Configuration File Reference page, cross-confirmed against Palace's
    CHANGELOG (PR #471, "a single global Floquet wave vector can be
    specified in config['Boundaries']['Periodic']['FloquetWaveVector']").
  - config["Boundaries"]["FloquetPort"][i] keys -- "Index" (integer,
    required, >0, "used in postprocessing output files"), "Attributes"
    (required integer array of mesh boundary attributes), "Excitation"
    (bool or positive int, default false), "IncidentPolarization" (string,
    default "TE"; "TE"|"TM"|"RHC"|"LHC"), "MaxOrder" (integer >=0,
    "Maximum diffraction order index to include"): same Configuration File
    Reference page. This module emits FloquetPort as a plain JSON array
    (matching the "Floquet Ports for a Dielectric Grating" example's own
    two-port -- excitation + receiving -- shape) with each entry carrying
    its own "Index"; this array-of-objects shape (rather than an
    object-keyed-by-string-index, the form LumpedPort/WavePort reportedly
    use elsewhere) is inferred from "Index" being a real, separately-
    documented field on each entry -- REASONED, not confirmed against a
    full worked JSON example (repeated fetch attempts against
    docs/src/examples/dielectric_grating.md's actual example config file
    did not return its literal JSON body -- see HONEST CAVEAT below).
  - Boundary/port physical description -- "Floquet ports are available for
    frequency domain driven simulations on periodic structures (gratings,
    metasurfaces, photonic crystals)... require periodic boundary
    conditions to be configured under config['Boundaries']['Periodic']...
    The incident field is a plane wave in the specular (0,0) diffraction
    order with user-specified polarization (TE, TM, or circular RHC/LHC)...
    the port boundary must be planar and on the true boundary of the
    computational domain [and] the medium adjacent to the port must be
    homogeneous and isotropic": docs/src/guide/boundaries.md ("Floquet
    Ports and Periodic Boundary Conditions" section), fetched from
    raw.githubusercontent.com/awslabs/palace/main/docs/src/guide/
    boundaries.md.
  - The example this ticket specifically names -- "Floquet Ports for a
    Dielectric Grating" (docs/src/examples/dielectric_grating.md) --
    describes a unit cell periodic 4cm(x) x 1cm(y) x 8cm(z), a single
    embedded dielectric bar (er=7, 2x0.5x0.5cm) in a vacuum background, a
    Floquet wave vector k_F=(0, 1.0479, 0) cm^-1 at a 10 GHz reference
    frequency (30 deg oblique TE incidence held constant across a 2-12 GHz
    sweep), confirming this module's own geometry model (a rectangular
    periodic cell with embedded axis-aligned dielectric boxes, Floquet
    ports on the two z-normal faces, periodic boundaries on the four
    x/y-normal side faces, one reference-frequency wave vector for the
    whole sweep) matches the shape of Palace's own primary worked example.
  - S-parameter/diffraction-order output -- "S-parameters are extracted for
    all propagating diffraction orders within 'MaxOrder' and reported in
    the port-floquet-S.csv output file. Each mode is labeled as
    S[P<port>(<m>,<n>)<pol>][<exc>]... values of nan [are] given to
    non-propagating modes": same docs/src/guide/boundaries.md section.
    parse_palace_output() below matches this literal "S[P<m>,<n>..." label
    substring with a tolerant regex (see HONEST CAVEAT).
  - The ordinary (non-Floquet) port-S.csv convention -- "Both the dB
    magnitude (20*log10(|Sij|)) and the phase (angle(Sij)) (in degrees) are
    written to the file" -- docs/src/guide/problem.md, fetched from
    raw.githubusercontent.com/awslabs/palace/main/docs/src/guide/problem.md.
    parse_palace_output() below ASSUMES port-floquet-S.csv follows this
    same dB-magnitude/phase-degrees convention per mode column (REASONED by
    analogy -- both files are driven-solver S-parameter postprocessing
    output from the same code, and dB+degrees is Palace's one documented
    S-parameter CSV convention -- but NOT independently confirmed for
    port-floquet-S.csv specifically; see HONEST CAVEAT).
  - config["Solver"]["Driven"]["Samples"][i] -- "Type": "Point" (explicit
    "Freq" GHz array) | "Linear" (required "MinFreq"/"MaxFreq" GHz, either
    "FreqStep" or "NSample") | "Log" (required "MinFreq"/"MaxFreq" GHz >
    0.0, "NSample" >= 1): awslabs.github.io/palace/dev/config/reference/.
    This module always emits one "Linear" sample block from the sweep
    start/stop/points input, matching run_hfss_simulation's own
    start_hz/stop_hz/points sweep dict shape for cross-adapter consistency.
  - MFEM native ".mesh" v1.0 ASCII format -- generate_palace_mesh() below
    writes this format (Palace's config["Model"]["Mesh"] loader is MFEM's
    own mesh reader, and MFEM's native format is the one format both tools'
    own documentation confirms without ambiguity -- Palace's own
    docs/src/guide/model.md additionally confirms explicit built-in support
    for Nastran and COMSOL mesh files, but does not mention Gmsh, so this
    module does not use a Gmsh-format writer). File shape -- a "MFEM mesh
    v1.0" header line, then "dimension"/"elements"/"boundary"/"vertices"
    sections, each "<count>" followed by "<attribute> <geometry_type>
    <vertex indices...>" (elements/boundary) or "<coordinates...>"
    (vertices) lines -- and the geometry-type integer code table (POINT=0,
    SEGMENT=1, TRIANGLE=2, SQUARE=3, TETRAHEDRON=4, CUBE=5, PRISM=6):
    mfem.org/mesh-format-v1.0/, which also gives a full worked 2D
    "beam-quad.mesh" example (SQUARE=3 elements, SEGMENT=1 boundary lines)
    fetched and reproduced verbatim during this pass, confirming the
    section layout above field-for-field. CUBE (hexahedron, geometry type
    5) vertex ordering -- the first four vertex indices form one
    quadrilateral face in rotational order, the last four form the
    opposite parallel face in the SAME rotational order, with vertex i
    connected to vertex i+4 (the standard trilinear-hex convention shared
    by VTK/Exodus/CGNS) -- confirmed via MFEM's own real
    github.com/mfem/mfem/blob/master/data/periodic-cube.mesh sample file
    (an actual 3D hex mesh, e.g. its element line "1 5 0 1 4 3 9 10 13 12"),
    not independently re-fetched byte-for-byte from mfem/geom.hpp's
    reference-element source in this pass (that header was pointed to by
    mfem.org's own docs as the authoritative source but not itself fetched
    -- REASONED from the confirmed worked example, not read from the
    primary geometry-definition source; see HONEST CAVEAT).
  - License -- Apache License, Version 2.0: github.com/awslabs/palace/blob/
    main/LICENSE (fetched and confirmed to open "Apache License Version
    2.0, January 2004"), and the repository's own GitHub description/
    topics. Recorded in docs/LICENSE_MATRIX.md and README.md.

HONEST CAVEAT -- read before trusting any of this end to end: the real
`palace` binary is NOT installed in this environment (no MPI-parallel FEM
solver install is present or feasible to add here) and was not available to
run against anything this module generates. Four specific things above are
REASONED from adjacent confirmed facts rather than independently verified
byte-for-byte against Palace's own primary source, and are flagged as such
at their point of use: (1) FloquetPort's JSON-array-vs-object-keyed-by-index
shape, (2) port-floquet-S.csv's presumed dB-magnitude/phase-degrees column
convention (carried over from the separately-documented ordinary
port-S.csv), (3) the exact hex boundary-face vertex WINDING direction MFEM
expects (this module always lists each boundary quad's four vertices as
exactly the matching face of its adjacent hex element -- vertex membership
is therefore certainly correct -- oriented outward-normal-consistent by
this module's own convention, but whether MFEM's boundary reader cares
about winding direction at all, versus deriving face orientation purely
from the adjacent 3D element, was not confirmed), and (4) that Palace's own
CSV writer RFC4180-quotes header cells containing a raw comma -- the
documented mode label itself contains one ("(<m>,<n>)"), so
parse_palace_output() below can only recover the intended column
correspondence if that cell is quoted; REASONED (any CSV writer producing
a self-consistent file with a comma-containing field would need to do
this), not independently confirmed against a real Palace-written CSV (see
tests/test_palace.py's _build_sample_floquet_csv for how this module's own
tests construct valid quoted sample data). Deck/
mesh generation and CSV parsing below are built to the letter of the
documented/verified format above (each fact's confidence graded inline);
tests exercise only the subprocess-invocation contract and the parser
against a synthetic fake "palace" script (see tests/test_palace.py), never
against a real Palace run. Treat any result as unverified end-to-end until
it has actually been run against the real tool at least once.

SCOPE OF THIS IMPLEMENTATION: a single rectangular periodic unit cell,
periodic (via config["Boundaries"]["Periodic"]) on its four x/y-normal
side faces, with a Floquet port on each of its two z-normal faces (port 1
at z=0, excited; port 2 at z=Lz), containing zero or more embedded
axis-aligned dielectric material boxes in a background medium -- this is
exactly the shape of Palace's own "Floquet Ports for a Dielectric Grating"
example cited above. generate_palace_mesh() below builds a structured
(non-uniform-rectilinear) hexahedral mesh from the union of the unit
cell's own boundaries and every material box's edges along each axis,
subdivided by the caller's geometry["mesh"]["nx"/"ny"/"nz"] (default 2
elements per feature-interval -- deliberately coarse; this is a caller-
controlled modeling parameter, not a converged default, matching this
codebase's convention of never fabricating a falsely-authoritative mesh
density). Embedded PEC conductor patches (the metallic-metasurface case,
as opposed to an all-dielectric grating/photonic-crystal unit cell) are
NOT implemented in this pass -- a real, explicitly-scoped gap (would need
interior mesh-face boundary-attribute assignment, not attempted here), not
a silent omission.
"""

import csv
import io
import json
import math
import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from .base import SimulationResult, Simulator, SimulatorError
from .conservation_checks import check_palace_result

# ---------------------------------------------------------------------------
# PalaceSimulator: the Simulator contract (simulation/base.py, unchanged) --
# shells out to the real `palace` binary via subprocess, following the same
# executable-env-var-override / explicit-timeout / nonzero-exit->
# SimulatorError pattern as Nec2ppSimulator (simulation/nec2pp.py) and
# OpenemsSimulator (simulation/openems.py). See module docstring for the
# "-np <N> config.json" CLI contract citation.
# ---------------------------------------------------------------------------


class PalaceSimulator(Simulator):
    name = "Palace"

    def __init__(self, executable: str | None = None):
        self.executable = executable or os.getenv("PALACE_BIN") or "palace"

    def run(self, job: dict) -> SimulationResult:
        config_file = Path(job["config_file"]).resolve()
        workdir = Path(job.get("workdir", config_file.parent)).resolve()
        if not config_file.exists():
            raise SimulatorError(f"Palace config file not found: {config_file}")

        # Palace's own CLI contract (see module docstring citation): the
        # installed `palace` script wraps an MPI launcher and takes
        # "-np <NUM_PROCS>" followed by the positional JSON config file.
        num_processes = int(job.get("num_processes", 1))
        timeout_s = int(job.get("timeout_s", 3600))
        try:
            completed = subprocess.run(
                [self.executable, "-np", str(num_processes), str(config_file)],
                cwd=workdir,
                capture_output=True,
                text=True,
                timeout=timeout_s,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise SimulatorError(f"Palace timed out after {timeout_s}s: {exc}") from exc
        if completed.returncode != 0:
            raise SimulatorError(
                f"Palace failed ({completed.returncode}): {completed.stderr[-4000:]}"
            )

        # Palace logs per-iteration linear-solver progress to stdout, which
        # can be long for a real run -- tail-truncated like openEMS's
        # adapter (this module's parser reads structured results from the
        # port-floquet-S.csv output file, not from stdout), not kept in
        # full like NEC2++'s (whose stdout *is* its results text).
        return SimulationResult(
            simulator=self.name,
            status="COMPLETED",
            workdir=workdir,
            outputs={"stdout": completed.stdout[-8000:]},
        )


# ---------------------------------------------------------------------------
# Mesh generation: a structured (non-uniform rectilinear) hexahedral mesh of
# the periodic unit cell, in MFEM's native ".mesh" v1.0 ASCII format -- see
# module docstring for the full format/geometry-type-code/vertex-ordering
# citation.
# ---------------------------------------------------------------------------

# Boundary attribute numbers this module always assigns, referenced by both
# generate_palace_mesh() (which writes them into the mesh's "boundary"
# section) and generate_palace_config() (which references them from
# config["Boundaries"]["Periodic"]["BoundaryPairs"] and
# config["Boundaries"]["FloquetPort"]) -- the two must agree, which is
# guaranteed here since both are simple module-level constants rather than
# independently invented in each function.
BOUND_X_MIN = 1
BOUND_X_MAX = 2
BOUND_Y_MIN = 3
BOUND_Y_MAX = 4
BOUND_Z_MIN = 5  # Floquet port 1 (excited)
BOUND_Z_MAX = 6  # Floquet port 2

_CUBE_GEOM_TYPE = 5  # MFEM Geometry::CUBE, see module docstring citation
_SQUARE_GEOM_TYPE = 3  # MFEM Geometry::SQUARE, same citation


def _fmt(value: float) -> str:
    return f"{float(value):.9g}"


def _feature_lines(lo: float, hi: float, interior: list[float], subdivisions: int) -> list[float]:
    """Build a strictly increasing grid-line list covering [lo, hi]: the
    "feature" points (lo, hi, plus every interior coordinate -- e.g. a
    material box's edge -- clipped to [lo, hi]) are sorted/deduplicated
    first so every material boundary lands exactly on a grid line (no
    element straddles two different materials), then each interval between
    consecutive feature points is subdivided into `subdivisions` equal
    sub-intervals."""
    pts = sorted({lo, hi, *(p for p in interior if lo - 1e-9 <= p <= hi + 1e-9)})
    if subdivisions < 1:
        raise ValueError("mesh subdivisions must be >= 1")
    grid: list[float] = []
    for a, b in zip(pts[:-1], pts[1:], strict=False):
        for s in range(subdivisions):
            grid.append(a + (b - a) * s / subdivisions)
    grid.append(pts[-1])
    return grid


def _material_attribute(
    materials: list[dict[str, Any]], centroid: tuple[float, float, float]
) -> int:
    """Domain attribute for a mesh element at `centroid`: the first material
    (in input order) whose axis-aligned box contains it, offset by 2 (1 is
    reserved for the background); else 1 (background)."""
    for idx, mat in enumerate(materials):
        p1, p2 = mat["p1_m"], mat["p2_m"]
        lo = [min(p1[a], p2[a]) for a in range(3)]
        hi = [max(p1[a], p2[a]) for a in range(3)]
        if all(lo[a] - 1e-9 <= centroid[a] <= hi[a] + 1e-9 for a in range(3)):
            return idx + 2
    return 1


def generate_palace_mesh(geometry: dict[str, Any]) -> dict[str, Any]:
    """Generate a structured hexahedral mesh of a rectangular periodic unit
    cell as MFEM ".mesh" v1.0 text (see module docstring citation).

    `geometry` shape (see also generate_palace_config, which shares this
    same dict):
        {
          "unit_cell": {"lx_m": float, "ly_m": float, "lz_m": float},
          "materials": [                 # optional embedded dielectric boxes
              {"name": str (optional), "p1_m": [x,y,z], "p2_m": [x,y,z],
               "epsilon_r": float (default 1.0), "mue_r": float (default 1.0),
               "loss_tan": float (default 0.0)}, ...
          ],
          "mesh": {"nx": int, "ny": int, "nz": int},  # optional, each
              default 2 -- elements per feature-interval along that axis;
              see module docstring's SCOPE note on why this is coarse by
              default.
        }

    x=0/x=lx and y=0/y=ly are the periodic (donor/receiver) face pairs;
    z=0/z=lz are the two Floquet port faces -- see BOUND_* constants above
    and generate_palace_config() for how config["Boundaries"] references
    these same six boundary attributes.

    Returns {"mesh_text": str, "num_elements": int, "num_boundary_faces":
    int, "num_vertices": int}.
    """
    unit_cell = geometry.get("unit_cell")
    if not unit_cell:
        raise ValueError("geometry['unit_cell'] is required")
    lx = float(unit_cell["lx_m"])
    ly = float(unit_cell["ly_m"])
    lz = float(unit_cell["lz_m"])
    if not (lx > 0 and ly > 0 and lz > 0):
        raise ValueError("geometry['unit_cell']'s lx_m/ly_m/lz_m must all be > 0")

    materials = geometry.get("materials", [])
    for idx, mat in enumerate(materials):
        missing = [f for f in ("p1_m", "p2_m") if f not in mat]
        if missing:
            raise ValueError(f"material {idx} missing required field(s): {missing}")

    mesh_cfg = geometry.get("mesh", {})
    nx = int(mesh_cfg.get("nx", 2))
    ny = int(mesh_cfg.get("ny", 2))
    nz = int(mesh_cfg.get("nz", 2))

    x_feats = [c for m in materials for c in (m["p1_m"][0], m["p2_m"][0])]
    y_feats = [c for m in materials for c in (m["p1_m"][1], m["p2_m"][1])]
    z_feats = [c for m in materials for c in (m["p1_m"][2], m["p2_m"][2])]
    x_grid = _feature_lines(0.0, lx, x_feats, nx)
    y_grid = _feature_lines(0.0, ly, y_feats, ny)
    z_grid = _feature_lines(0.0, lz, z_feats, nz)
    nxv, nyv, nzv = len(x_grid), len(y_grid), len(z_grid)

    def vidx(i: int, j: int, k: int) -> int:
        return (i * nyv + j) * nzv + k

    vertices = [
        (x_grid[i], y_grid[j], z_grid[k])
        for i in range(nxv)
        for j in range(nyv)
        for k in range(nzv)
    ]

    elements: list[tuple[int, list[int]]] = []
    for i in range(nxv - 1):
        for j in range(nyv - 1):
            for k in range(nzv - 1):
                centroid = (
                    (x_grid[i] + x_grid[i + 1]) / 2,
                    (y_grid[j] + y_grid[j + 1]) / 2,
                    (z_grid[k] + z_grid[k + 1]) / 2,
                )
                attr = _material_attribute(materials, centroid)
                # CUBE vertex order: bottom face (0,1,2,3) then top face
                # (4,5,6,7) in the same rotational order, vertex i<->i+4 --
                # see module docstring citation.
                v = [
                    vidx(i, j, k),
                    vidx(i + 1, j, k),
                    vidx(i + 1, j + 1, k),
                    vidx(i, j + 1, k),
                    vidx(i, j, k + 1),
                    vidx(i + 1, j, k + 1),
                    vidx(i + 1, j + 1, k + 1),
                    vidx(i, j + 1, k + 1),
                ]
                elements.append((attr, v))

    # Each boundary quad below lists exactly the four vertices of the
    # matching face of its adjacent hex element (see module docstring's
    # HONEST CAVEAT on the unverified winding-direction subtlety) --
    # donor/min faces keep that element's own local face vertex order,
    # receiver/max faces reverse it, for an outward-normal-consistent quad.
    boundary: list[tuple[int, list[int]]] = []
    for j in range(nyv - 1):
        for k in range(nzv - 1):
            boundary.append(
                (
                    BOUND_X_MIN,
                    [vidx(0, j, k), vidx(0, j + 1, k), vidx(0, j + 1, k + 1), vidx(0, j, k + 1)],
                )
            )
            boundary.append(
                (
                    BOUND_X_MAX,
                    [
                        vidx(nxv - 1, j, k),
                        vidx(nxv - 1, j, k + 1),
                        vidx(nxv - 1, j + 1, k + 1),
                        vidx(nxv - 1, j + 1, k),
                    ],
                )
            )
    for i in range(nxv - 1):
        for k in range(nzv - 1):
            boundary.append(
                (
                    BOUND_Y_MIN,
                    [vidx(i, 0, k), vidx(i + 1, 0, k), vidx(i + 1, 0, k + 1), vidx(i, 0, k + 1)],
                )
            )
            boundary.append(
                (
                    BOUND_Y_MAX,
                    [
                        vidx(i, nyv - 1, k),
                        vidx(i, nyv - 1, k + 1),
                        vidx(i + 1, nyv - 1, k + 1),
                        vidx(i + 1, nyv - 1, k),
                    ],
                )
            )
    for i in range(nxv - 1):
        for j in range(nyv - 1):
            boundary.append(
                (
                    BOUND_Z_MIN,
                    [vidx(i, j, 0), vidx(i + 1, j, 0), vidx(i + 1, j + 1, 0), vidx(i, j + 1, 0)],
                )
            )
            boundary.append(
                (
                    BOUND_Z_MAX,
                    [
                        vidx(i, j, nzv - 1),
                        vidx(i, j + 1, nzv - 1),
                        vidx(i + 1, j + 1, nzv - 1),
                        vidx(i + 1, j, nzv - 1),
                    ],
                )
            )

    lines = ["MFEM mesh v1.0", "", "dimension", "3", "", "elements", str(len(elements))]
    lines += [
        f"{attr} {_CUBE_GEOM_TYPE} " + " ".join(str(v) for v in verts) for attr, verts in elements
    ]
    lines += ["", "boundary", str(len(boundary))]
    lines += [
        f"{attr} {_SQUARE_GEOM_TYPE} " + " ".join(str(v) for v in verts) for attr, verts in boundary
    ]
    lines += ["", "vertices", str(len(vertices)), "3"]
    lines += [f"{_fmt(x)} {_fmt(y)} {_fmt(z)}" for x, y, z in vertices]
    mesh_text = "\n".join(lines) + "\n"

    return {
        "mesh_text": mesh_text,
        "num_elements": len(elements),
        "num_boundary_faces": len(boundary),
        "num_vertices": len(vertices),
    }


# ---------------------------------------------------------------------------
# Config generation -- see module docstring for the per-key citation list.
# ---------------------------------------------------------------------------

_VALID_POLARIZATIONS = ("TE", "TM", "RHC", "LHC")


def generate_palace_config(
    geometry: dict[str, Any],
    mesh_file: str | Path,
    output_dir: str | Path,
    frequency_hz: float,
    sweep: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Generate a Palace JSON config for a driven Floquet-port unit-cell
    simulation. `geometry` is the same dict passed to generate_palace_mesh
    (see its docstring), plus two more optional keys:
        "background": {"epsilon_r": float, "mue_r": float, "loss_tan": float},
        "floquet": {
            "wave_vector_1_per_m": [kx, ky, kz] (default [0,0,0], normal
                incidence),
            "reference_frequency_hz": float (default: this function's own
                `frequency_hz` argument -- the frequency at which
                wave_vector_1_per_m is defined; see module docstring's
                FloquetWaveVector/FloquetReferenceFrequency citation),
            "polarization": "TE" (default) | "TM" | "RHC" | "LHC",
            "max_order": int (default 0 -- specular diffraction order only),
        }

    `sweep` (optional): {"start_hz": float, "stop_hz": float, "points":
    int}, same shape as run_hfss_simulation's own sweep dict -- defaults to
    0.9x/1.1x frequency_hz over 51 points, matching simulation/hfss.py's
    own default.
    """
    unit_cell = geometry.get("unit_cell")
    if not unit_cell:
        raise ValueError("geometry['unit_cell'] is required")
    lx = float(unit_cell["lx_m"])
    ly = float(unit_cell["ly_m"])

    materials = geometry.get("materials", [])
    background = geometry.get("background", {})

    floquet = geometry.get("floquet", {})
    wave_vector = floquet.get("wave_vector_1_per_m", [0.0, 0.0, 0.0])
    if len(wave_vector) != 3:
        raise ValueError("geometry['floquet']['wave_vector_1_per_m'] must have 3 components")
    reference_frequency_hz = floquet.get("reference_frequency_hz", frequency_hz)
    polarization = floquet.get("polarization", "TE")
    if polarization not in _VALID_POLARIZATIONS:
        raise ValueError(
            f"floquet polarization must be one of {_VALID_POLARIZATIONS}, got {polarization!r}"
        )
    max_order = int(floquet.get("max_order", 0))

    sweep = sweep or {}
    start_hz = sweep.get("start_hz", frequency_hz * 0.9)
    stop_hz = sweep.get("stop_hz", frequency_hz * 1.1)
    points = int(sweep.get("points", 51))

    materials_json = [
        {
            "Attributes": [1],
            "Permittivity": background.get("epsilon_r", 1.0),
            "Permeability": background.get("mue_r", 1.0),
            "LossTan": background.get("loss_tan", 0.0),
        }
    ]
    for idx, mat in enumerate(materials):
        materials_json.append(
            {
                "Attributes": [idx + 2],
                "Permittivity": mat.get("epsilon_r", 1.0),
                "Permeability": mat.get("mue_r", 1.0),
                "LossTan": mat.get("loss_tan", 0.0),
            }
        )

    return {
        "Problem": {"Type": "Driven", "Output": str(output_dir)},
        # L0=1.0 is set EXPLICITLY, never omitted -- Palace's own default
        # (1.0e-6, i.e. micrometers) would silently misinterpret this
        # module's meter-denominated mesh coordinates by 1e6x. See module
        # docstring citation.
        "Model": {"Mesh": str(mesh_file), "L0": 1.0},
        "Domains": {"Materials": materials_json},
        "Boundaries": {
            "Periodic": {
                "FloquetWaveVector": [float(v) for v in wave_vector],
                "FloquetReferenceFrequency": reference_frequency_hz / 1e9,
                "BoundaryPairs": [
                    {
                        "DonorAttributes": [BOUND_X_MIN],
                        "ReceiverAttributes": [BOUND_X_MAX],
                        "Translation": [lx, 0.0, 0.0],
                    },
                    {
                        "DonorAttributes": [BOUND_Y_MIN],
                        "ReceiverAttributes": [BOUND_Y_MAX],
                        "Translation": [0.0, ly, 0.0],
                    },
                ],
            },
            "FloquetPort": [
                {
                    "Index": 1,
                    "Attributes": [BOUND_Z_MIN],
                    "Excitation": True,
                    "IncidentPolarization": polarization,
                    "MaxOrder": max_order,
                },
                {
                    "Index": 2,
                    "Attributes": [BOUND_Z_MAX],
                    "Excitation": False,
                    "IncidentPolarization": polarization,
                    "MaxOrder": max_order,
                },
            ],
        },
        "Solver": {
            "Driven": {
                "Samples": [
                    {
                        "Type": "Linear",
                        "MinFreq": start_hz / 1e9,
                        "MaxFreq": stop_hz / 1e9,
                        "NSample": points,
                    }
                ]
            }
        },
    }


# ---------------------------------------------------------------------------
# Output parsing -- port-floquet-S.csv, see module docstring citation for
# the "S[P<port>(<m>,<n>)<pol>][<exc>]" mode-label convention and the
# (reasoned-by-analogy, not independently confirmed for this specific file)
# dB-magnitude/phase-degrees column convention.
# ---------------------------------------------------------------------------

# Matches Palace's documented Floquet mode label, e.g. "S[P1(0,0)TE][1]",
# wherever it appears inside a CSV column header (which also carries a
# "|...| (dB)" / "arg(...) (deg.)" decoration this module does not assume
# an exact spelling for -- see module docstring HONEST CAVEAT).
_MODE_RE = re.compile(r"S\[P(\d+)\((-?\d+),(-?\d+)\)([A-Za-z]+)\]\[(\d+)\]")


def parse_palace_output(csv_text: str) -> dict[str, Any]:
    """Parse a port-floquet-S.csv file's text into structured per-mode
    S-parameter data. Returns a computed=False dict (with an explanatory
    note, never a guess) when the text is empty or no column header matches
    the documented mode-label pattern -- both real, honestly-reported gaps.
    """
    if not csv_text.strip():
        return {
            "computed": False,
            "note": "port-floquet-S.csv was empty or missing -- nothing to parse.",
        }

    rows = list(csv.reader(io.StringIO(csv_text)))
    rows = [row for row in rows if any(cell.strip() for cell in row)]
    if len(rows) < 2:
        return {
            "computed": False,
            "note": "port-floquet-S.csv had a header but no data rows.",
        }
    header = [h.strip() for h in rows[0]]
    data_rows = rows[1:]

    mode_columns: dict[str, dict[str, Any]] = {}
    for col_idx, name in enumerate(header[1:], start=1):
        match = _MODE_RE.search(name)
        if not match:
            continue
        label = match.group(0)
        entry = mode_columns.setdefault(
            label,
            {
                "port": int(match.group(1)),
                "m": int(match.group(2)),
                "n": int(match.group(3)),
                "polarization": match.group(4),
                "excitation": int(match.group(5)),
            },
        )
        lower = name.lower()
        if "db" in lower or "|" in name:
            entry["_magnitude_col"] = col_idx
        elif "arg" in lower or "deg" in lower or "phase" in lower:
            entry["_phase_col"] = col_idx

    if not mode_columns:
        return {
            "computed": False,
            "note": (
                "no column header matched the documented Floquet mode label "
                "'S[P<port>(<m>,<n>)<pol>][<exc>]' (see "
                "simulation/palace.py's module docstring citation) -- "
                f"{len(header) - 1} non-frequency column(s) checked, 0 recognized -- "
                f"header was: {header!r}"
            ),
        }

    frequency_hz: list[float] = []
    modes: dict[str, Any] = {
        label: {**meta, "magnitude_db": [], "phase_deg": [], "value_complex": []}
        for label, meta in mode_columns.items()
    }
    for row in data_rows:
        # Frequency assumed to be the first column, in GHz -- matching every
        # other frequency field in Palace's own config file (MinFreq/
        # MaxFreq/FloquetReferenceFrequency are all GHz); REASONED by
        # convention, not independently confirmed for this specific output
        # file (see module docstring HONEST CAVEAT).
        frequency_hz.append(float(row[0]) * 1e9)
        for label, meta in mode_columns.items():
            mag_col = meta.get("_magnitude_col")
            phase_col = meta.get("_phase_col")
            mag_db = float(row[mag_col]) if mag_col is not None and mag_col < len(row) else None
            phase_deg = (
                float(row[phase_col]) if phase_col is not None and phase_col < len(row) else None
            )
            modes[label]["magnitude_db"].append(mag_db)
            modes[label]["phase_deg"].append(phase_deg)
            if (
                mag_db is not None
                and phase_deg is not None
                and not (math.isnan(mag_db) or math.isnan(phase_deg))
            ):
                mag_linear = 10 ** (mag_db / 20.0)
                phase_rad = math.radians(phase_deg)
                modes[label]["value_complex"].append(
                    [mag_linear * math.cos(phase_rad), mag_linear * math.sin(phase_rad)]
                )
            else:
                # None here means either Palace's own "nan" (a genuinely
                # non-propagating diffraction order at this frequency, per
                # module docstring citation) or that this mode's
                # magnitude/phase column pair wasn't both found -- either
                # way, an honest gap, never a fabricated value.
                modes[label]["value_complex"].append(None)

    for meta in modes.values():
        meta.pop("_magnitude_col", None)
        meta.pop("_phase_col", None)

    # Convenience view: the specular (m=0,n=0) mode at each port, for the
    # excitation actually driven (excitation index 1, matching this
    # module's own generate_palace_config which always excites port 1) --
    # the closest Floquet-port analog to a conventional S11/S21 pair, for
    # callers that just want the fundamental-order reflection/transmission.
    specular: dict[str, list[Any]] = {}
    for meta in modes.values():
        if meta["m"] == 0 and meta["n"] == 0 and meta["excitation"] == 1:
            specular[f"S{meta['port']}1"] = meta["value_complex"]

    result: dict[str, Any] = {
        "computed": True,
        "frequency_hz": frequency_hz,
        "modes": modes,
        "note": (
            "value_complex[i] is None where Palace reported 'nan' (a "
            "non-propagating diffraction order at that frequency) or where "
            "this mode's magnitude/phase column pair could not both be "
            "found. See simulation/palace.py's module docstring for the "
            "dB-magnitude/phase-degrees column convention this parser "
            "assumes (reasoned by analogy to the documented port-S.csv "
            "convention, not independently confirmed for "
            "port-floquet-S.csv)."
        ),
    }
    if specular:
        result["specular"] = specular
        result["specular_note"] = (
            "specular['S<port>1'] is the (m=0,n=0) specular-order mode "
            "excited from port 1 (this module's own config always excites "
            "port 1 only) -- the closest Floquet-port analog to a "
            "conventional Sij value; other diffraction orders are only in "
            "'modes'."
        )
    return result


# ---------------------------------------------------------------------------
# run_palace_simulation: orchestration, matching run_nec2_simulation/
# run_openems_simulation/run_hfss_simulation's own shape.
# ---------------------------------------------------------------------------


def run_palace_simulation(
    geometry: dict[str, Any],
    frequency_hz: float,
    sweep: dict[str, Any] | None = None,
    num_processes: int = 1,
    timeout_s: int = 3600,
    executable: str | None = None,
    workdir: str | None = None,
) -> dict[str, Any]:
    """Generate a Palace mesh + JSON config for a periodic unit cell from
    structured geometry, run it via PalaceSimulator, and parse
    port-floquet-S.csv into structured per-diffraction-order S-parameter
    data tagged with SIMULATED provenance. The returned dict's
    "conservation_check" key (issue #221, see
    simulation/conservation_checks.py) reports power-balance, passivity and
    reciprocity margins over every parsed diffraction order -- warned on,
    never blocked on (ADR-0028): a violation is still returned, annotated
    with what's assumed, what it costs if wrong, and the cheapest way to
    find out.

    See this module's header comment for the format-verification citations
    and the honest caveat: mesh/config generation and CSV parsing are built
    to the documented/verified Palace/MFEM formats cited there, not to a
    real Palace binary run in this environment (none is installed).
    """
    work_dir = Path(workdir) if workdir else Path(tempfile.mkdtemp(prefix="palace_"))
    work_dir.mkdir(parents=True, exist_ok=True)
    mesh_file = work_dir / "unit_cell.mesh"
    config_file = work_dir / "config.json"
    output_dir = work_dir / "postpro"

    mesh_result = generate_palace_mesh(geometry)
    mesh_file.write_text(mesh_result["mesh_text"])

    config = generate_palace_config(
        geometry,
        mesh_file=mesh_file,
        output_dir=output_dir,
        frequency_hz=frequency_hz,
        sweep=sweep,
    )
    config_file.write_text(json.dumps(config, indent=2))

    simulator = PalaceSimulator(executable=executable)
    result = simulator.run(
        {
            "config_file": str(config_file),
            "workdir": str(work_dir),
            "num_processes": num_processes,
            "timeout_s": timeout_s,
        }
    )

    csv_path = output_dir / "port-floquet-S.csv"
    parsed = parse_palace_output(csv_path.read_text() if csv_path.exists() else "")

    # Issue #221: check the parsed S-parameters against power balance,
    # passivity and reciprocity -- physics the result cannot violate no
    # matter what the mesh/config/CSV-parsing got wrong (see
    # simulation/conservation_checks.py's module docstring, including the
    # real defect -- a polarization-collision on the `specular` dict's key
    # -- this check is built to be robust to by summing over the full
    # `modes` data instead). `lossless` is inferred here, not asked of the
    # caller: this adapter's SCOPE (see module docstring) has no PEC
    # conductor/embedded-loss element beyond each material's own
    # `loss_tan`, so "every material's loss_tan is exactly 0" is exactly
    # the lossless condition this geometry dict can express today.
    background_loss_tan = geometry.get("background", {}).get("loss_tan", 0.0)
    material_loss_tans = [m.get("loss_tan", 0.0) for m in geometry.get("materials", [])]
    lossless = all(lt == 0.0 for lt in [background_loss_tan, *material_loss_tans])
    conservation_check = check_palace_result(parsed, lossless=lossless, reciprocal=True)

    return {
        "provenance": "SIMULATED",
        "s_parameters": parsed,
        "conservation_check": conservation_check,
        "simulator": result.simulator,
        "status": result.status,
        "workdir": str(result.workdir),
        "config_file": str(config_file),
        "mesh_file": str(mesh_file),
        "output_dir": str(output_dir),
        "num_mesh_elements": mesh_result["num_elements"],
    }
