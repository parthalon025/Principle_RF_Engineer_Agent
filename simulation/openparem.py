"""OpenParEM3D full-wave FEM adapter -- antenna-specific far-field gain/directivity/
radiation-efficiency computed from the same solve that produces S-parameters (issue #62).

OpenParEM is young (initial public release Sept. 18, 2024; antenna performance metrics
added in v2.0.0, Mar. 6, 2025) and considerably less battle-tested than HFSS/openEMS/
NEC2++ in this codebase -- treat any result from this adapter as unverified end-to-end
until it has actually been run against the real OpenParEM3D binary at least once, on top
of the "no real binary in this environment" caveat every simulator adapter here already
carries (see the HONEST CAVEAT section below).

SOURCES CONSULTED (primary; fetched directly from the upstream OpenParEM/OpenParEM
GitHub repository's `main` branch and openparem.org's own hosted PDFs during
implementation -- accessed 2026-09-02. Per-fact citations below):

  - Project identity/scope ("OpenParEM3D ... post-processes the fields to produce
    scattering parameters (S-parameters) between 2D wave ports and radiation patterns,
    gain, directivity, and radiation efficiency for antennas"), and that OpenParEM is a
    command-line-only tool ("OpenParEM is a command-line tool for running electromagnetic
    simulations only. Pre- and post-processing must be handled by other tools.") built
    around a FreeCAD + gmsh + ParaView flow the *user* assembles ("The user is responsible
    for pulling together the necessary tools to create the needed files. ... Assembling a
    tool flow is a very significant task."): github.com/OpenParEM/OpenParEM's own README,
    and openparem.org's "OpenParEM Installation Manual, Version 2.1, April 2025" (Brian
    Young), Secs. 1 and 4 (openparem.org/wp-content/uploads/2025/05/
    Installation_Execution-1.pdf).

  - EXACT CLI invocation contract -- quoted verbatim from the Installation Manual's own
    Sec. 6 "Execution":
        Serial:   `OpenParEM3D my_project.proj`
        Parallel: `mpirun -q --oversubscribe -np N OpenParEM3D my_project.proj`
    (`-q` suppresses MPI infrastructure messages; `--oversubscribe` is documented as
    "required with OpenParEM3D when N is more than half the number of available cores"
    since OpenParEM3D transiently runs N copies of itself plus N copies of OpenParEM2D
    while solving 2D wave ports). Independently corroborated by
    src/OpenParEM3D/OpenParEM3D.cpp's own argv parsing (see next item) -- a single
    required positional argument, no other required flags.
  - argv/usage contract, straight from source: OpenParEM3D.cpp's own help text is
    `"usage: OpenParEM3D [-h] filename\n"` / `"filename    : Filename of an OpenParEM
    setup file.\n"`; its main() does `if (argc <= 1) printHelp=1; else if
    (strcmp(argv[1],"-h")==0) printHelp=1; else projFile=argv[1];` then
    `PetscInitializeNoArguments()` -- confirming MPI/PETSc init takes no CLI flags of its
    own, matching the Installation Manual's plain positional-filename contract above.
    Exit codes: `exit(1)` on any parse/help error, `exit(0)` on a clean finish (both
    grepped directly from OpenParEM3D.cpp) -- the same "nonzero exit -> failure" contract
    this codebase's other adapters already assume.
    github.com/OpenParEM/OpenParEM/blob/main/src/OpenParEM3D/OpenParEM3D.cpp.

  - `.proj` project-control-file format -- keyword table, defaults, and accepted values
    ALL read directly out of src/OpenParEM3D/project.c's own keyword-parsing switch
    (`strcmp(keyword,"...")`) and its struct-default initializer:
      * Header line is the literal token pair the parser itself emits/expects:
        `#OpenParEM3Dproject 1.0` (`data->version_name=allocCopyString(
        "#OpenParEM3Dproject"); data->version_value=allocCopyString("1.0");`).
      * `project.save.fields` (bool, default false), `mesh.file` (path), `mesh.order`
        (int, default 1), `mesh.refinement.fraction` (float 0-1, sets the 3D-specific
        `mesh_3D_refinement_fraction`, default 0.005 -- confirmed distinct from
        OpenParEM2D's own 0.025 default), `mesh.quality.limit` (float, default 20),
        `mesh.save.refined` (bool, default false), `port.definition.file` (path),
        `materials.global.path`/`materials.global.name` (defaults "../"/
        "global_materials"), `materials.local.path`/`materials.local.name` (defaults
        "./"/"local_materials"), `refinement.frequency` (one of "all", "none", "high",
        "low", "highlow" (default), "lowhigh", "plan" -- exact list quoted from the
        parser's own ERROR3146/3147 message text), `refinement.iteration.min`/`.max`
        (int, defaults 1/10), `refinement.required.passes` (int, default 1),
        `refinement.relative.tolerance`/`.absolute.tolerance` (float, defaults
        0.02/1e-6), `refinement.variable` (string, default "SandH"),
        `frequency.plan.linear`/`.linear.refine` (comma-separated "start,stop,step" on
        one line), `frequency.plan.log`/`.log.refine` (comma-separated
        "start,stop,points_per_decade"), `frequency.plan.point`/`.point.refine`
        (a single frequency value), `reference.impedance` (float, default 50 -- 0 means
        "not renormalized", per ResultDatabase::saveCSV's own
        `if (projData->reference_impedance == 0) ss << "not renormalized";`),
        `touchstone.format` (one of "RI"/"MA"/"DB", default "DB"),
        `touchstone.frequency.unit` (one of "Hz"/"kHz"/"MHz"/"GHz", default "GHz").
      * `antenna.plot.3D.pattern` -- confirmed to take one `q=<quantity>` key/value pair
        on the same line, `quantity` validated by `is_valid_quantity1()`
        (project.c:416-423) against exactly `"G"` (gain), `"D"` (directivity), or a field
        component ("Etheta"/"Ephi"/"Htheta"/"Hphi", not used by this module). This is the
        keyword this module emits to request the far-field gain/directivity/efficiency
        this ticket is about; `antenna.plot.2D.pattern` (a 2D cut, needing
        q1/q2/plane/theta/phi sub-keys) exists but is NOT emitted by this module --
        out of scope, see SCOPE below.
    github.com/OpenParEM/OpenParEM/blob/main/src/OpenParEM3D/project.c.

  - Output file formats -- read directly out of the C++ code that WRITES them (not
    guessed from the .csv extension):
      * `<project_name>_results.csv` (S-parameters): ResultDatabase::saveCSV,
        results.cpp -- a `#`-commented header block (`#OpenParEM3D <ver>`,
        `#Touchstone format,<fmt>`, `#frequency unit,<unit>`, `#number of frequencies,
        <N>`, `#number of ports,<N>`, one `#S-port <n>,<net>,<Z0-or-"not
        renormalized">` line per port) followed by a `#Frequency(<Unit>)` column-header
        line whose remaining columns are `Re(S(row;col))`/`Im(S(row;col))` (format RI),
        `mag(S(row;col))`/`deg(S(row;col))` (format MA), or `dB(S(row;col))`/
        `deg(S(row;col))` (format DB) pairs, ordered driven-port-major (all rows for
        col=1, then all rows for col=2, ...) -- confirmed from the literal `while (col <
        portCount) { while (row < portCount) { ... row++ } col++ }` loop nesting. This
        module's parser reads the header line itself to map each column pair back to its
        (row,col) S-parameter and RI/MA/DB kind, rather than assuming a fixed column
        order.
      * `<project_name>.s<N>p` (Touchstone): ResultDatabase::saveTouchstone,
        results.cpp -- `ss << projData->project_name << ".s" << portCount << "p";`.
        Confirmed conditionally skipped (with an explicit INFO log line, not silently) for
        non-renormalized data (`reference.impedance 0`) and for modal port setups
        ("Do not output a Touchstone file for modal setups because the modes may or may
        not be mixed mode for Touchstone 2.0") -- this module therefore only *checks
        whether the file exists* after a run rather than assuming it was written, the
        same honest-absence handling simulation/openems.py already uses for its own
        conditional Touchstone output.
      * `<project_name>_FarField_results.csv` (the antenna metrics this ticket is about):
        PatternDatabase::saveCSV, pattern.cpp -- header
        `#S-port,frequency(<Unit>),gain,directivity,radiation efficiency`, one data row
        per (S-port, frequency) pair matching a `q=G` or `q=D` `antenna.plot.3D.pattern`
        request, `Sport,frequency,gain,directivity,radiation_efficiency` (plain,
        unlabeled-kind CSV, confirmed from the literal
        `out << Sport << "," << freq*scale << "," << get_gain() << "," <<
        get_directivity() << "," << get_radiationEfficiency() << endl;`). Only written
        (PatternDatabase::saveCSV's own `if (patternList.size() == 0) return false;`)
        when at least one 3D antenna pattern was actually computed -- which itself
        requires a radiation-type Boundary in the ports file (see next citation) --
        this module honestly reports computed=False with an explanatory note, not a
        guess, when the file is absent.
      * Units, confirmed from the functions that COMPUTE these fields, not just their
        CSV column labels: `Sphere::calculateIsotropicGain`/`Circle::
        calculateIsotropicGain` (pattern.cpp) compute `gaini_db=10*log10(real(gaini))`
        and `directivityi_db=10*log10(real(directivityi))` -- gain and directivity are
        dB (dBi, isotropic reference) values, NOT linear ratios. `Pattern::
        calculateRadiationEfficiency` (pattern.cpp) computes
        `radiationEfficiency=real(radiatedPower/acceptedPower)` -- a plain linear
        fraction (0-1), NOT dB. This module's parser surfaces
        `gain_dbi`/`directivity_dbi`/`radiation_efficiency` under those exact,
        unit-disambiguated key names rather than a bare "gain"/"directivity" that could
        be misread as linear.
        github.com/OpenParEM/OpenParEM/blob/main/src/OpenParEM3D/{results,pattern}.cpp.

  - Ports/boundary definition file (`port.definition.file`) format -- keyword-block
    syntax verified BOTH against a real, complete worked example
    (tutorials/OpenParEM3D/monopole_antenna/monopole_antenna_ports.txt, fetched
    verbatim: header `#OpenParEMports 1.0`; a `File`/`name=<path>`/`EndFile` block; one
    or more `Path`/`name=<name>`/`point=(x,y,z)` (repeated)/`closed=true|false`/`EndPath`
    blocks; `Boundary`/`name=<name>`/`type=radiation`/`path=+<pathname>`/`EndBoundary`
    blocks (the leading `+` on `path=` is the literal, verified syntax the real example
    uses to reference a named Path); a `Port`/`name=<name>`/`path=+<pathname>`/
    `impedance_definition=PV`/`impedance_calculation=modal`/`Mode`/`Sport=1`/
    `IntegrationPath`/`type=voltage`/`path=+<pathname>`/`EndIntegrationPath`/`EndMode`/
    `EndPort` block) AND against the C++ parser that reads these same tokens:
      * `Boundary`'s `type=` accepted values -- confirmed from is_boundary_type-style
        checks in src/OpenParEM3D/port.cpp: `type.get_value().compare("surface_
        impedance")`, `.compare("perfect_electric_conductor")`, `.compare("radiation")`.
      * `Port`'s `impedance_definition=` accepted values -- confirmed from port.cpp:
        `impedance_definition.get_value().compare("VI")`/`"PV"`/`"PI"`.
      * `Port`'s `impedance_calculation=` accepted values -- confirmed from port.cpp:
        `impedance_calculation.get_value().compare("modal")`/`"line"`.
      * The `File`/`EndFile`, `Path ... point=(...) ... closed=... EndPath` block
        structure -- confirmed from src/OpenParEMCommon/path.cpp's own alias
        registrations (`name.push_alias("name")`, `closed.push_alias("closed")`,
        `token.compare("point")`) and its own `PetscPrintf(...,"%sEndPath\n",...)` /
        `*out << "EndPath"` echo statements; `EndFile` similarly confirmed from
        src/OpenParEMCommon/sourcefile.cpp's own
        `PetscPrintf(PETSC_COMM_WORLD,"EndFile\n")`.
      * `Mode`/`Sport=`/`IntegrationPath`/`type=`/`path=`/`EndIntegrationPath`/`EndMode`
        block structure -- confirmed from port.cpp's own alias registrations
        (`Sport.push_alias("Sport")`) and echo statements (`*out << "Mode" << endl;`,
        `PetscPrintf(...,"%sEndIntegrationPath\n",...)`, `PetscPrintf(...,
        "%sEndMode\n",...)`, and the block-parsing call site naming
        `"IntegrationPath", "EndIntegrationPath"` / `"Mode", "EndMode"` directly).
    github.com/OpenParEM/OpenParEM/blob/main/tutorials/OpenParEM3D/monopole_antenna/
    monopole_antenna_ports.txt,
    github.com/OpenParEM/OpenParEM/blob/main/src/OpenParEM3D/port.cpp,
    github.com/OpenParEM/OpenParEM/blob/main/src/OpenParEMCommon/{path,sourcefile}.cpp.
    LOWER-CONFIDENCE NOTE: the `File` block's *functional* necessity to a solve (vs. it
    being purely informational metadata FreeCAD's own `OpenParEM3D_save.py` macro writes
    for its own round-tripping) was not independently confirmed by reading the parser's
    handling of a missing `File` block -- this module always emits one (see
    generate_openparem_ports_file's `source_file` parameter) to match the one real,
    working example available, rather than omit it and guess that is safe.

  - Mesh format constraint -- "Note that OpenParEM only works with the msh22 format of
    gmsh due to library limitations," and gmsh's own `-format msh22` invocation:
    Installation Manual Sec. 4.2. This module does not generate mesh files (see SCOPE).

  - License -- GPL-3.0-or-later, confirmed from the literal header comment repeated
    verbatim atop every OpenParEM3D source file (e.g. src/OpenParEM3D/project.c):
    "This program is free software: you can redistribute it and/or modify it under the
    terms of the GNU General Public License as published by the Free Software
    Foundation, either version 3 of the License, or (at your option) any later version."
    -- i.e. GPL-3.0-or-later, not a bare GPL-3.0-only; matches docs/LICENSE_MATRIX.md's
    new OpenParEM row. The repo's own top-level LICENSE file is the plain GPLv3 license
    text (github.com/OpenParEM/OpenParEM/blob/main/LICENSE).

SCOPE OF THIS IMPLEMENTATION (an explicit, honestly-documented narrowing, not a silently
missing feature -- OpenParEM's own architecture is a *multi-tool flow*, not a
single-file-format simulator like NEC2++/openEMS, so "generate everything from a
structured job dict" does not map onto it the same way):

  - Mesh generation (a real, valid Gmsh msh22 tetrahedral mesh of arbitrary 3D geometry)
    is NOT done by this module. OpenParEM's own Installation Manual is explicit that this
    is a separate, user-assembled step via FreeCAD + gmsh ("The user is responsible for
    pulling together the necessary tools to create the needed [mesh] files. Assembling a
    tool flow is a very significant task.") -- this module treats an already-meshed
    `mesh_file` (msh22 format) as a required, externally-supplied input, the same way
    simulation/hfss.py treats a licensed AEDT installation as an external precondition
    rather than something this codebase can fabricate.
  - The materials property library (`materials.global.name`/`materials.local.name` --
    separate text files mapping material NAMES baked into the mesh's physical groups to
    actual permittivity/conductivity values) is likewise NOT generated here; this module
    only emits the `.proj` keywords that POINT to these files (with OpenParEM3D's own
    documented path/name defaults), matching the "point to it, don't fabricate it"
    treatment given to `mesh_file` above.
  - What THIS module DOES generate, fully programmatically from a structured job dict
    (mirroring simulation/nec2pp.py's deck generation and simulation/openems.py's
    FDTD-XML generation): the `.proj` project-control file (frequency plan, mesh-order/
    refinement/quality settings, reference impedance, Touchstone format, and the
    `antenna.plot.3D.pattern q=G|D` far-field request this ticket is about), and the
    ports/boundary/port definition file (Path/Boundary/Port/Mode/IntegrationPath blocks)
    -- both plain-text, OpenParEM-specific formats fully within this module's own domain,
    verified against real source + a real worked example as cited above.
  - `antenna.plot.2D.pattern` (2D angular cuts/slices) and 3D pattern-mesh/current-plot
    export (`antenna.plot.3D.save`/`antenna.plot.raw.save`, ParaView-consumable outputs)
    are NOT exposed -- this ticket asks for scalar gain/directivity/efficiency, which
    `antenna.plot.3D.pattern` alone provides via the `_FarField_results.csv` this module
    parses; full pattern-shape data is a separate, larger feature.
  - Far-field metrics are only actually computed by OpenParEM3D when the ports file's
    Boundary blocks include at least one `type=radiation` boundary (confirmed by
    PatternDatabase's own gain/directivity dispatch code being reached only via
    fields solved under radiation boundary conditions) -- this module does not
    itself validate that the caller's `ports["boundaries"]` includes one; an absent
    `_FarField_results.csv` after a run (parsed as computed=False with a note) is the
    honest signal that either far-field wasn't requested or no radiation boundary was
    modeled.

HONEST CAVEAT: the real `OpenParEM3D` binary is NOT installed in this environment
(confirmed via `which OpenParEM3D`, exit 1) and was not available to run against these
generated `.proj`/ports files. `.proj`/ports-file generation and CSV/Touchstone-existence
parsing are built to the letter of the primary-source citations above (each fact grepped
directly out of OpenParEM's own C/C++ source, or quoted verbatim from its own
Installation Manual PDF and a real worked-example project file -- not reconstructed from
memory or "what seems plausible"), and exercised in tests only against a small fake
"OpenParEM3D" script that writes the documented output-file shapes (see
tests/test_openparem.py) -- NOT against real FEM physics or a real OpenParEM3D run.
Treat any result as unverified end-to-end until it has been run against the real tool at
least once. OpenParEM being young and comparatively unproven (vs. HFSS/openEMS/NEC2++,
each with a much longer track record) is an additional reason for caution beyond this
codebase's usual "no real binary in this sandbox" caveat.
"""

import cmath
import math
import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from .base import SimulationResult, Simulator, SimulatorError

# ---------------------------------------------------------------------------
# OpenParemSimulator: the Simulator contract (simulation/base.py, unchanged) --
# shells out to the real OpenParEM3D binary against an already-written .proj file.
# See module docstring for the CLI-contract citation.
# ---------------------------------------------------------------------------


class OpenParemSimulator(Simulator):
    name = "OpenParEM3D"

    def __init__(self, executable: str | None = None):
        self.executable = executable or os.getenv("OPENPAREM3D_BIN", "OpenParEM3D")

    def run(self, job: dict) -> SimulationResult:
        project_file = Path(job["project_file"]).resolve()
        workdir = Path(job.get("workdir", project_file.parent)).resolve()
        if not project_file.exists():
            raise SimulatorError(f"OpenParEM3D project file not found: {project_file}")

        # OpenParEM3D's own documented CLI contract (see module docstring citation):
        # serial "OpenParEM3D <project>.proj", or parallel "mpirun -q --oversubscribe
        # -np N OpenParEM3D <project>.proj" -- a single positional project-file
        # argument either way, no other required flags. mpi_processes<=1 (including the
        # default None) uses the plain serial form, matching the Installation Manual's
        # own "Running on a single core is sometimes convenient when getting a new
        # project up-and-running."
        mpi_processes = job.get("mpi_processes")
        if mpi_processes and int(mpi_processes) > 1:
            cmd = [
                "mpirun",
                "-q",
                "--oversubscribe",
                "-np",
                str(int(mpi_processes)),
                self.executable,
                str(project_file),
            ]
        else:
            cmd = [self.executable, str(project_file)]

        timeout_s = int(job.get("timeout_s", 3600))
        try:
            completed = subprocess.run(
                cmd,
                cwd=workdir,
                capture_output=True,
                text=True,
                timeout=timeout_s,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise SimulatorError(f"OpenParEM3D timed out after {timeout_s}s: {exc}") from exc
        if completed.returncode != 0:
            # OpenParEM3D reports its own ERRORNNNN diagnostics via PetscPrintf, which
            # (unlike a typical Unix tool) is not guaranteed to land on stderr rather
            # than stdout -- both are included so a real failure message isn't dropped.
            detail = (completed.stderr + completed.stdout)[-4000:]
            raise SimulatorError(f"OpenParEM3D failed ({completed.returncode}): {detail}")

        return SimulationResult(
            simulator=self.name,
            status="COMPLETED",
            workdir=workdir,
            outputs={"stdout": completed.stdout[-8000:]},
        )


# ---------------------------------------------------------------------------
# .proj project-control-file generation. See module docstring for the full
# keyword/default/accepted-value citation list.
# ---------------------------------------------------------------------------


def _fmt(value: float) -> str:
    return f"{float(value):.6g}"


def _bool(value: bool) -> str:
    return "true" if value else "false"


_VALID_REFINEMENT_FREQUENCY = ("all", "none", "high", "low", "highlow", "lowhigh", "plan")
_VALID_TOUCHSTONE_FORMAT = ("RI", "MA", "DB")
_VALID_FREQUENCY_UNIT = ("Hz", "kHz", "MHz", "GHz")
_VALID_FAR_FIELD_QUANTITY = ("G", "D")


def generate_openparem_project_config(
    project: dict[str, Any], comment: str = "Generated by run_openparem_simulation"
) -> str:
    """Generate an OpenParEM3D `.proj` project-control file from structured settings.

    `project` shape:
        {
          "mesh_file": str,               # required -- a pre-meshed Gmsh msh22 file
              (see module docstring SCOPE -- NOT generated by this module)
          "port_definition_file": str,    # required -- filename of the ports/boundary
              file (see generate_openparem_ports_file), relative to the run's workdir
          "frequency_plan": {             # required, at least one of the three lists
              "linear": [{"start_hz", "stop_hz", "step_hz", "refine": bool=False}, ...],
              "log": [{"start_hz", "stop_hz", "points_per_decade", "refine": bool=False}, ...],
              "point": [{"frequency_hz", "refine": bool=False}, ...],
          },
          "mesh_order": int (default 1),
          "mesh_refinement_fraction": float, 0-1 (default 0.005),
          "mesh_quality_limit": float (default 20.0),
          "mesh_save_refined": bool (default False),
          "project_save_fields": bool (default False),
          "refinement": {                 # all optional, OpenParEM3D's own defaults used
              "frequency": one of "all"/"none"/"high"/"low"/"highlow"/"lowhigh"/"plan"
                  (default "highlow"),
              "iteration_min": int (default 1), "iteration_max": int (default 10),
              "required_passes": int (default 1),
              "relative_tolerance": float (default 0.02),
              "absolute_tolerance": float (default 1e-6),
              "variable": str (default "SandH"),
          },
          "materials": {                  # all optional -- see module docstring SCOPE;
              "global_path": str (default "../"), "global_name": str (default "global_materials"),
              "local_path": str (default "./"), "local_name": str (default "local_materials"),
          },
          "reference_impedance_ohms": float (default 50.0; 0 means "not renormalized"),
          "touchstone_format": one of "RI"/"MA"/"DB" (default "DB"),
          "touchstone_frequency_unit": one of "Hz"/"kHz"/"MHz"/"GHz" (default "GHz"),
          "far_field": {"quantity": "G" (gain, default) | "D" (directivity)} | None,
              # when given, emits antenna.plot.3D.pattern -- see module docstring for
              # why this is the request that produces the *_FarField_results.csv this
              # ticket is about, and its dependency on a radiation-type Boundary.
        }

    Geometry itself lives in `mesh_file`/`port_definition_file`, not here -- this
    function only emits solver/reporting settings, per the module docstring's SCOPE.
    """
    mesh_file = project.get("mesh_file")
    if not mesh_file:
        raise ValueError(
            "project['mesh_file'] is required -- a pre-meshed Gmsh msh22 file "
            "(mesh generation is out of scope for this module, see its docstring)"
        )
    port_definition_file = project.get("port_definition_file")
    if not port_definition_file:
        raise ValueError("project['port_definition_file'] is required")
    frequency_plan = project.get("frequency_plan") or {}
    if not any(frequency_plan.get(k) for k in ("linear", "log", "point")):
        raise ValueError(
            "project['frequency_plan'] must supply a non-empty 'linear', 'log', or "
            "'point' list"
        )

    lines: list[str] = ["#OpenParEM3Dproject 1.0", f"# {comment}"]

    lines.append(
        f"project.save.fields             {_bool(project.get('project_save_fields', False))}"
    )
    lines.append(f"mesh.file                       {mesh_file}")
    lines.append(f"mesh.order                      {int(project.get('mesh_order', 1))}")
    lines.append(
        f"mesh.refinement.fraction        {_fmt(project.get('mesh_refinement_fraction', 0.005))}"
    )
    lines.append(
        f"mesh.quality.limit              {_fmt(project.get('mesh_quality_limit', 20.0))}"
    )
    lines.append(
        f"mesh.save.refined               {_bool(project.get('mesh_save_refined', False))}"
    )
    lines.append(f"port.definition.file            {port_definition_file}")

    materials = project.get("materials", {})
    lines.append(f"materials.global.path           {materials.get('global_path', '../')}")
    lines.append(
        f"materials.global.name           {materials.get('global_name', 'global_materials')}"
    )
    lines.append(f"materials.local.path            {materials.get('local_path', './')}")
    lines.append(
        f"materials.local.name            {materials.get('local_name', 'local_materials')}"
    )

    refinement = project.get("refinement", {})
    refinement_frequency = refinement.get("frequency", "highlow")
    if refinement_frequency not in _VALID_REFINEMENT_FREQUENCY:
        raise ValueError(
            f"refinement['frequency'] must be one of {_VALID_REFINEMENT_FREQUENCY}, "
            f"got {refinement_frequency!r}"
        )
    lines.append(f"refinement.frequency            {refinement_frequency}")
    lines.append(f"refinement.iteration.min        {int(refinement.get('iteration_min', 1))}")
    lines.append(f"refinement.iteration.max        {int(refinement.get('iteration_max', 10))}")
    lines.append(f"refinement.required.passes      {int(refinement.get('required_passes', 1))}")
    lines.append(
        f"refinement.relative.tolerance   {_fmt(refinement.get('relative_tolerance', 0.02))}"
    )
    lines.append(
        f"refinement.absolute.tolerance   {_fmt(refinement.get('absolute_tolerance', 1e-6))}"
    )
    lines.append(f"refinement.variable             {refinement.get('variable', 'SandH')}")

    for entry in frequency_plan.get("linear", []):
        keyword = "frequency.plan.linear.refine" if entry.get("refine") else "frequency.plan.linear"
        lines.append(
            f"{keyword}    "
            f"{_fmt(entry['start_hz'])},{_fmt(entry['stop_hz'])},{_fmt(entry['step_hz'])}"
        )
    for entry in frequency_plan.get("log", []):
        keyword = "frequency.plan.log.refine" if entry.get("refine") else "frequency.plan.log"
        lines.append(
            f"{keyword}       "
            f"{_fmt(entry['start_hz'])},{_fmt(entry['stop_hz'])},{int(entry['points_per_decade'])}"
        )
    for entry in frequency_plan.get("point", []):
        keyword = "frequency.plan.point.refine" if entry.get("refine") else "frequency.plan.point"
        lines.append(f"{keyword}     {_fmt(entry['frequency_hz'])}")

    lines.append(
        f"reference.impedance             {_fmt(project.get('reference_impedance_ohms', 50.0))}"
    )

    touchstone_format = project.get("touchstone_format", "DB")
    if touchstone_format not in _VALID_TOUCHSTONE_FORMAT:
        raise ValueError(f"touchstone_format must be one of {_VALID_TOUCHSTONE_FORMAT}")
    lines.append(f"touchstone.format               {touchstone_format}")

    touchstone_frequency_unit = project.get("touchstone_frequency_unit", "GHz")
    if touchstone_frequency_unit not in _VALID_FREQUENCY_UNIT:
        raise ValueError(f"touchstone_frequency_unit must be one of {_VALID_FREQUENCY_UNIT}")
    lines.append(f"touchstone.frequency.unit       {touchstone_frequency_unit}")

    far_field = project.get("far_field")
    if far_field:
        quantity = far_field.get("quantity", "G")
        if quantity not in _VALID_FAR_FIELD_QUANTITY:
            raise ValueError(
                f"far_field['quantity'] must be one of {_VALID_FAR_FIELD_QUANTITY} "
                "('G'=gain, 'D'=directivity)"
            )
        lines.append(f"antenna.plot.3D.pattern         q={quantity}")

    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Ports/boundary definition file generation. See module docstring for the full
# block-syntax citation (verified against both a real worked example and the
# C++ parser's own alias/echo statements).
# ---------------------------------------------------------------------------

_VALID_BOUNDARY_TYPE = ("radiation", "perfect_electric_conductor", "surface_impedance")
_VALID_IMPEDANCE_DEFINITION = ("PV", "PI", "VI")
_VALID_IMPEDANCE_CALCULATION = ("modal", "line")
_VALID_INTEGRATION_PATH_TYPE = ("voltage", "current")


def generate_openparem_ports_file(ports: dict[str, Any]) -> str:
    """Generate an OpenParEM3D ports/boundary/port definition file from structured
    path/boundary/port geometry.

    `ports` shape:
        {
          "source_file": str,      # optional -- informational path to the source CAD
              file the path points were taken from (see module docstring's
              lower-confidence note on whether this block is functionally required)
          "paths": [               # required, non-empty
              {"name": str, "points": [[x, y, z], ...], "closed": bool=False}, ...
          ],
          "boundaries": [          # optional
              {"name": str, "type": "radiation"|"perfect_electric_conductor"|
                  "surface_impedance", "path": str},   # path e.g. "+front" -- the
                  literal '+'-prefixed reference-by-name syntax the real example uses
              ...
          ],
          "ports": [               # required, non-empty
              {
                "name": str, "path": str,
                "impedance_definition": "PV" (default) | "PI" | "VI",
                "impedance_calculation": "modal" (default) | "line",
                "modes": [         # required, non-empty
                    {"sport": int, "integration_path": {
                        "type": "voltage" | "current", "path": str}},
                    ...
                ],
              }, ...
          ],
        }

    Points are in the same coordinate units as `mesh_file` (whatever the source CAD/mesh
    used -- OpenParEM3D itself is unit-agnostic here, unlike simulation/nec2pp.py's
    meters-only convention).
    """
    paths = ports.get("paths")
    if not paths:
        raise ValueError("ports['paths'] must be a non-empty list")
    port_list = ports.get("ports")
    if not port_list:
        raise ValueError("ports['ports'] must be a non-empty list")

    lines: list[str] = ["#OpenParEMports 1.0", ""]

    source_file = ports.get("source_file")
    if source_file:
        lines += ["File", f"   name={source_file}", "EndFile", ""]

    for idx, path in enumerate(paths):
        name = path.get("name")
        points = path.get("points")
        if not name or not points:
            raise ValueError(f"path {idx} missing 'name' or non-empty 'points'")
        lines.append("Path")
        lines.append(f"   name={name}")
        for point in points:
            x, y, z = point
            lines.append(f"   point=({_fmt(x)},{_fmt(y)},{_fmt(z)})")
        lines.append(f"   closed={_bool(path.get('closed', False))}")
        lines += ["EndPath", ""]

    for idx, boundary in enumerate(ports.get("boundaries", [])):
        name = boundary.get("name")
        boundary_type = boundary.get("type")
        path_ref = boundary.get("path")
        if not name or not path_ref:
            raise ValueError(f"boundary {idx} missing 'name' or 'path'")
        if boundary_type not in _VALID_BOUNDARY_TYPE:
            raise ValueError(f"boundary {idx}['type'] must be one of {_VALID_BOUNDARY_TYPE}")
        lines += [
            "Boundary",
            f"   name={name}",
            f"   type={boundary_type}",
            f"   path={path_ref}",
            "EndBoundary",
            "",
        ]

    for idx, port in enumerate(port_list):
        name = port.get("name")
        path_ref = port.get("path")
        if not name or not path_ref:
            raise ValueError(f"port {idx} missing 'name' or 'path'")
        impedance_definition = port.get("impedance_definition", "PV")
        if impedance_definition not in _VALID_IMPEDANCE_DEFINITION:
            raise ValueError(
                f"port {idx}['impedance_definition'] must be one of "
                f"{_VALID_IMPEDANCE_DEFINITION}"
            )
        impedance_calculation = port.get("impedance_calculation", "modal")
        if impedance_calculation not in _VALID_IMPEDANCE_CALCULATION:
            raise ValueError(
                f"port {idx}['impedance_calculation'] must be one of "
                f"{_VALID_IMPEDANCE_CALCULATION}"
            )
        modes = port.get("modes")
        if not modes:
            raise ValueError(f"port {idx} ({name!r}) needs a non-empty 'modes' list")

        lines.append("Port")
        lines.append(f"   name={name}")
        lines.append(f"   path={path_ref}")
        lines.append(f"   impedance_definition={impedance_definition}")
        lines.append(f"   impedance_calculation={impedance_calculation}")
        for mode_idx, mode in enumerate(modes):
            sport = mode.get("sport")
            integration_path = mode.get("integration_path")
            if sport is None or not integration_path:
                raise ValueError(
                    f"port {idx} ({name!r}) mode {mode_idx} missing 'sport' or "
                    "'integration_path'"
                )
            ip_type = integration_path.get("type")
            ip_path = integration_path.get("path")
            if ip_type not in _VALID_INTEGRATION_PATH_TYPE:
                raise ValueError(
                    f"port {idx} ({name!r}) mode {mode_idx}'s integration_path['type'] "
                    f"must be one of {_VALID_INTEGRATION_PATH_TYPE}"
                )
            if not ip_path:
                raise ValueError(
                    f"port {idx} ({name!r}) mode {mode_idx} missing "
                    "integration_path['path']"
                )
            lines.append("   Mode")
            lines.append(f"      Sport={int(sport)}")
            lines.append("      IntegrationPath")
            lines.append(f"         type={ip_type}")
            lines.append(f"         path={ip_path}")
            lines.append("      EndIntegrationPath")
            lines.append("   EndMode")
        lines += ["EndPort", ""]

    return "\n".join(lines).rstrip() + "\n"


# ---------------------------------------------------------------------------
# Output parsing -- reads the *_results.csv / *_FarField_results.csv / .sNp files
# OpenParEM3D itself writes (see module docstring for the writer-side citations),
# never stdout, since (unlike NEC2++) OpenParEM3D's numeric results live only in
# these files.
# ---------------------------------------------------------------------------

_S_HEADER_RE = re.compile(r"^(Re|Im|mag|deg|dB)\(S\((\d+);(\d+)\)\)$")
_FREQ_UNIT_SCALE = {"Hz": 1.0, "kHz": 1e3, "MHz": 1e6, "GHz": 1e9}


def _parse_results_csv(text: str) -> dict[str, Any]:
    """Parse a `<project_name>_results.csv` S-parameter file -- see module docstring's
    ResultDatabase::saveCSV citation for the exact header/column format this reads."""
    port_count: int | None = None
    frequency_unit = "GHz"
    header_tokens: list[str] | None = None
    data_rows: list[str] = []

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("#number of ports,"):
            port_count = int(line.split(",")[1])
        elif line.startswith("#frequency unit,"):
            frequency_unit = line.split(",", 1)[1].strip()
        elif line.startswith("#Frequency("):
            header_tokens = line.lstrip("#").split(",")
        elif not line.startswith("#"):
            data_rows.append(line)

    if header_tokens is None or not data_rows:
        return {
            "computed": False,
            "note": (
                "no '#Frequency(...)' column-header line or data rows found in the "
                "*_results.csv file -- the run may not have completed a frequency sweep"
            ),
        }

    column_specs: list[tuple[str, int, int]] = []
    for token in header_tokens[1:]:
        match = _S_HEADER_RE.match(token.strip())
        if not match:
            return {
                "computed": False,
                "note": f"unrecognized *_results.csv column header {token!r}",
            }
        column_specs.append((match.group(1), int(match.group(2)), int(match.group(3))))
    if len(column_specs) % 2 != 0:
        return {
            "computed": False,
            "note": (
                "*_results.csv has an odd number of S-parameter columns (expected "
                "Re/Im, mag/deg, or dB/deg pairs)"
            ),
        }

    scale = _FREQ_UNIT_SCALE.get(frequency_unit, 1e9)
    frequency_hz: list[float] = []
    values: dict[str, list[list[float]]] = {}

    for row in data_rows:
        tokens = row.split(",")
        try:
            frequency_hz.append(float(tokens[0]) * scale)
        except (ValueError, IndexError):
            return {"computed": False, "note": f"unparseable *_results.csv data row: {row!r}"}

        for pair_idx in range(0, len(column_specs), 2):
            kind_a, row_a, col_a = column_specs[pair_idx]
            kind_b, row_b, col_b = column_specs[pair_idx + 1]
            if row_a != row_b or col_a != col_b:
                return {
                    "computed": False,
                    "note": (
                        "*_results.csv column pairing does not match expected "
                        "(Re/Im or mag/deg or dB/deg) layout"
                    ),
                }
            try:
                val_a = float(tokens[1 + pair_idx])
                val_b = float(tokens[2 + pair_idx])
            except (ValueError, IndexError):
                return {"computed": False, "note": f"unparseable *_results.csv data row: {row!r}"}

            if kind_a == "Re":
                s_value = complex(val_a, val_b)
            elif kind_a == "mag":
                s_value = cmath.rect(val_a, math.radians(val_b))
            else:  # kind_a == "dB"
                s_value = cmath.rect(10 ** (val_a / 20), math.radians(val_b))
            s_name = f"S{row_a}{col_a}"
            values.setdefault(s_name, []).append([s_value.real, s_value.imag])

    return {
        "computed": True,
        "port_count": port_count,
        "frequency_hz": frequency_hz,
        "values": values,
        "note": "values[name] holds [real, imag] pairs per frequency_hz point.",
    }


def _parse_farfield_csv(text: str) -> dict[str, Any]:
    """Parse a `<project_name>_FarField_results.csv` file -- see module docstring's
    PatternDatabase::saveCSV citation for the exact header/column format, and the
    calculateIsotropicGain/calculateRadiationEfficiency citations for units
    (gain_dbi/directivity_dbi in dB, radiation_efficiency a linear 0-1 fraction)."""
    header: str | None = None
    rows: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("#S-port,frequency"):
            header = line
        elif not line.startswith("#"):
            rows.append(line)

    if header is None or not rows:
        return {
            "computed": False,
            "note": (
                "no '#S-port,frequency...' header or data rows found in the "
                "*_FarField_results.csv file"
            ),
        }

    unit_match = re.search(r"frequency\(([A-Za-z]+)\)", header)
    scale = _FREQ_UNIT_SCALE.get(unit_match.group(1), 1e9) if unit_match else 1e9

    entries: list[dict[str, Any]] = []
    for row in rows:
        tokens = row.split(",")
        if len(tokens) != 5:
            continue
        sport, freq, gain, directivity, efficiency = tokens
        entries.append(
            {
                "sport": int(sport),
                "frequency_hz": float(freq) * scale,
                "gain_dbi": float(gain),
                "directivity_dbi": float(directivity),
                "radiation_efficiency": float(efficiency),
            }
        )

    if not entries:
        return {
            "computed": False,
            "note": "*_FarField_results.csv had a header but no parseable data rows",
        }

    return {
        "computed": True,
        "entries": entries,
        "note": (
            "gain_dbi/directivity_dbi are OpenParEM3D's own 10*log10(...) isotropic-"
            "reference dB values; radiation_efficiency is the linear radiatedPower/"
            "acceptedPower ratio (0-1) -- see module docstring's pattern.cpp citation."
        ),
    }


def parse_openparem_output(workdir: str | Path, project_name: str) -> dict[str, Any]:
    """Read `<project_name>_results.csv`, `<project_name>_FarField_results.csv`, and
    (if present) `<project_name>.s<N>p` from `workdir` -- OpenParEM3D's own output
    files (see module docstring citations) -- into structured, honestly-flagged
    S-parameter and far-field results."""
    workdir = Path(workdir)

    results_path = workdir / f"{project_name}_results.csv"
    if results_path.exists():
        s_parameters = _parse_results_csv(results_path.read_text())
    else:
        s_parameters = {
            "computed": False,
            "note": f"'{results_path.name}' not found in workdir -- the run may not have completed",
        }

    farfield_path = workdir / f"{project_name}_FarField_results.csv"
    if farfield_path.exists():
        far_field = _parse_farfield_csv(farfield_path.read_text())
    else:
        far_field = {
            "computed": False,
            "note": (
                f"'{farfield_path.name}' not found in workdir -- far-field wasn't "
                "requested (project['far_field'] omitted) or no radiation-type "
                "Boundary was modeled in the ports file, see module docstring SCOPE"
            ),
        }

    result: dict[str, Any] = {"s_parameters": s_parameters, "far_field": far_field}

    port_count = s_parameters.get("port_count")
    if port_count:
        touchstone_path = workdir / f"{project_name}.s{port_count}p"
        if touchstone_path.exists():
            result["touchstone_file"] = str(touchstone_path)

    return result


def run_openparem_simulation(
    mesh_file: str,
    ports: dict[str, Any],
    project: dict[str, Any] | None = None,
    project_name: str = "openparem_project",
    mpi_processes: int | None = None,
    timeout_s: int = 3600,
    executable: str | None = None,
    workdir: str | None = None,
) -> dict[str, Any]:
    """Generate an OpenParEM3D `.proj` file and ports/boundary file from structured
    settings/geometry, run OpenParEM3D via OpenParemSimulator, and parse S-parameter
    and far-field gain/directivity/radiation-efficiency results tagged with SIMULATED
    provenance.

    `mesh_file` must be an already-generated Gmsh msh22 mesh (see module docstring
    SCOPE -- not produced by this function). `ports` is generate_openparem_ports_file's
    input shape; `project` is generate_openparem_project_config's input shape minus
    `mesh_file`/`port_definition_file` (filled in here).

    See this module's header comment for the format-verification citations and the
    honest caveat: generation and parsing are built to the documented/verified
    OpenParEM3D `.proj`/ports-file/output-file formats, not to a real OpenParEM3D
    binary run in this environment.
    """
    work_dir = Path(workdir) if workdir else Path(tempfile.mkdtemp(prefix="openparem_"))
    work_dir.mkdir(parents=True, exist_ok=True)

    ports_filename = f"{project_name}_ports.txt"
    ports_path = work_dir / ports_filename
    ports_path.write_text(generate_openparem_ports_file(ports))

    project_settings = dict(project or {})
    project_settings["mesh_file"] = mesh_file
    project_settings["port_definition_file"] = ports_filename
    project_file = work_dir / f"{project_name}.proj"
    project_file.write_text(generate_openparem_project_config(project_settings))

    simulator = OpenParemSimulator(executable=executable)
    result = simulator.run(
        {
            "project_file": str(project_file),
            "workdir": str(work_dir),
            "timeout_s": timeout_s,
            "mpi_processes": mpi_processes,
        }
    )

    parsed = parse_openparem_output(work_dir, project_name)

    output: dict[str, Any] = {
        "provenance": "SIMULATED",
        "s_parameters": parsed["s_parameters"],
        "far_field": parsed["far_field"],
        "simulator": result.simulator,
        "status": result.status,
        "workdir": str(result.workdir),
        "project_file": str(project_file),
        "ports_file": str(ports_path),
    }
    if "touchstone_file" in parsed:
        # Surfaced at top level, matching simulation/openems.py's/simulation/hfss.py's
        # own "touchstone_file" convention for rf_tools.correlation integration.
        output["touchstone_file"] = parsed["touchstone_file"]
    return output
