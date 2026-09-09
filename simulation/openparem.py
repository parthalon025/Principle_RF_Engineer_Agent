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
    Installation Manual Sec. 4.2. This module now generates a mesh via
    `run_openparem_gmsh_meshing()` (issue #278) when the caller supplies `geometry`
    instead of a pre-meshed `mesh_file` -- reusing `simulation.elmer.
    generate_gmsh_geo_script()` for the geometry-dict-to-`.geo` translation (identical
    primitive-dict shape; see that function's own citations) and shelling out to gmsh
    with `-3 -format msh22 -o <msh_file>` instead of Elmer's `-format msh2` (`simulation/
    elmer.py`'s `run_gmsh_meshing()`, which this mirrors down to the `GMSH_BIN` env-var
    convention -- the SAME external `gmsh` binary either adapter invokes, so a second,
    OpenParEM-specific env var name was deliberately not introduced).

  - Materials-file (`materials.global.name`/`materials.local.name`) keyword syntax --
    read directly out of BOTH OpenParEM3D_Users_Manual.tex's own "Materials File
    Specification" appendix (its literal `Verbatim` block, quoting the Debye-model and
    frequency-list `Material`/`Temperature`/`Frequency`/`Source` grammar) AND
    src/OpenParEMCommon/OpenParEMmaterials.cpp/.hpp -- the C++ parser that actually reads
    it (`push_alias()` calls for every keyword synonym, `check()` for what's mandatory):
      * Header line, confirmed from OpenParEMmaterials.hpp's own default-initializer
        (`string version_name="#OpenParEMmaterials"; string version_value="1.0";`),
        matching the manual's own worked examples verbatim: `#OpenParEMmaterials 1.0`.
      * `Material`/`name=`/`EndMaterial` outer block; inside it, one or more `Temperature`
        blocks (`temperature`/`temp`/`t`, a double or the literal string `"any"` -- meaning
        "applies at all temperatures"), each containing EITHER a Debye-model keyword set
        OR one or more `Frequency` sub-blocks (mutually exclusive -- confirmed from
        Temperature::load's own dispatch: Debye keywords are only even recognized when
        `frequencyList.size()==0`, and OpenParEMmaterials.cpp's ERROR1058 explicitly
        rejects a Debye keyword found alongside a Frequency block); one or more `Source`/
        `EndSource` blocks (plain, unparsed text lines -- confirmed from `Source::load`,
        which just collects every line between the markers verbatim, no keyword=value
        parsing at all).
      * Debye-model keywords -- confirmed from Temperature's own `push_alias()` calls:
        `er_infinity`/`epsr_infinity`, `delta_er`/`delta_epsr`, `m1`, `m2`,
        `relative_permeability`/`mur`, `loss_tangent`/`tand`/`tandel`/`conductivity`/
        `sigma`. Temperature::check()'s ERROR1061-1067 confirm ALL of temperature,
        er_infinity, delta_er, m1, m2, relative_permeability, and a loss value
        (tand/conductivity) are mandatory for a Debye-model Temperature block.
      * Frequency-list keywords -- confirmed from Frequency's own `push_alias()` calls:
        `frequency`/`freq`/`f` (a double or `"any"`), `relative_permittivity`/`er`/`epsr`,
        `relative_permeability`/`mur`, `loss_tangent`/`tand`/`tandel`/`conductivity`/
        `sigma`, `Rz`. Frequency::check()'s ERROR1053-1057 confirm ALL FIVE of frequency,
        er, mur, a loss value, AND Rz are mandatory on EVERY Frequency block -- including
        for a pure dielectric with no conductor at all. This is a load-bearing,
        non-obvious finding: the manual's own inline comment on `Rz` reads
        "// for surface roughness if a conductor", which reads like Rz is conditional,
        but the actual C++ validator requires it unconditionally on every entry (and the
        manual's OWN worked "air" example, a pure dielectric, sets `Rz=0` rather than
        omitting it) -- this module follows the code (and the worked example) over the
        comment's looser wording, defaulting `Rz=0.0` rather than treating it as optional.
      * Linear interpolation between declared Frequency points, with extrapolation
        outside the declared range explicitly NOT supported -- confirmed from an
        inline C++ comment repeated identically in THREE places,
        `Temperature::get_eps()`/`get_mu()`/`get_Rs()` (all three, OpenParEMmaterials.cpp):
        "// for linear interpolation - extrapolation is not supported". This is a CODE
        comment, NOT a manual claim: OpenParEM3D_Users_Manual.tex,
        OpenParEM3D_Theory_Methodology_Accuracy.tex, and OpenParEM2D_Users_Manual.tex
        were each searched directly for "interpolat"/"extrapolat" and none describes
        materials-frequency behavior at all (the one Users-Manual hit is an unrelated
        ParaView-rendering setting). `generate_openparem_materials_file`'s own handling
        of a cited validity BAND (`frequency_low_hz`/`frequency_high_hz`) as two
        identical-valued Frequency points bracketing that band, rather than one, rests
        on this code-level fact -- see that function's own docstring.
      * Real worked examples, transcribed verbatim from the manual's "Materials Files"
        section (not reconstructed from the grammar alone): the "air" Material
        (`er=1.0006, mur=1, tand=0, Rz=0`, cited to Balanis's "Advanced Engineering
        Electromagnetics") and the "copper_prepreg" Material (`er=1, mur=1,
        conductivity=5.813e7, Rz=4.445e-6`, cited to an IPC spec + a named paper) --
        `generate_openparem_materials_file`'s own default `relative_permittivity=1.0` for
        a conductivity-only entry (no matching `eps_r`) mirrors copper_prepreg's own
        `er=1` exactly, and the default `relative_permeability=1.0`/`surface_roughness_
        rz_m=0.0` mirror both worked examples' shared mur=1 and air's own Rz=0.
    github.com/OpenParEM/OpenParEM/blob/main/doc/OpenParEM3D_Users_Manual.tex (Sec.
    "Materials Files" and Appendix "Materials File Specification"),
    github.com/OpenParEM/OpenParEM/blob/main/src/OpenParEMCommon/OpenParEMmaterials.{cpp,hpp}.

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

  - Mesh generation: `run_openparem_simulation()` can now (issue #278) drive meshing
    itself when given `geometry` (this repo's own primitive-dict shape) instead of a
    pre-supplied `mesh_file` -- `generate_gmsh_geo_script()` (reused from
    `simulation.elmer`, not reimplemented) turns `geometry` into a Gmsh `.geo` script,
    and `run_openparem_gmsh_meshing()` shells out to the real `gmsh` binary with
    `-3 -format msh22 -o <msh_file>` to produce the msh22 mesh OpenParEM3D itself
    requires (see the mesh-format-constraint citation above). A pre-supplied `mesh_file`
    remains fully supported (and required if `geometry` is not given) -- OpenParEM's own
    Installation Manual's FreeCAD+gmsh flow is still the richer, curved/multi-material
    path this module does NOT replace (see "Capabilities not yet used here" in
    docs/tools/openparem.md for what `generate_gmsh_geo_script()` itself does not cover:
    curved surfaces, non-box geometry, per-physical-group material tagging beyond a
    single bulk/excitation split).
  - The materials property library (`materials.global.name`/`materials.local.name` --
    separate text files mapping material NAMES baked into the mesh's physical groups to
    actual permittivity/conductivity values) can now (issue #278) be generated too, via
    `generate_openparem_materials_file()` (from a structured per-material dict) and
    `openparem_materials_from_property_entries()` (converting `designs/
    material_properties.py`-shaped rows into that per-material shape). This module still
    does NOT resolve disagreeing citations for the same material+property -- that
    remains `designs.material_properties.resolve_material_property()`'s job; the
    converter here requires an already-decided ONE eps_r + ONE loss (tan_delta OR
    conductivity_s_per_m) entry per material and raises rather than guessing which
    citation to trust if more than one is handed to it (see that function's own
    docstring). A caller-supplied materials library on disk (`project["materials"]`
    pointing at an existing file) remains fully supported as an alternative to the
    `materials` argument.
  - What THIS module DOES generate, fully programmatically from a structured job dict
    (mirroring simulation/nec2pp.py's deck generation and simulation/openems.py's
    FDTD-XML generation): the `.proj` project-control file (frequency plan, mesh-order/
    refinement/quality settings, reference impedance, Touchstone format, and the
    `antenna.plot.3D.pattern q=G|D` far-field request this ticket is about), the
    ports/boundary/port definition file (Path/Boundary/Port/Mode/IntegrationPath blocks),
    the Gmsh `.geo`→msh22 mesh (from `geometry`), and the materials-library text file
    (from `materials`) -- all plain-text, OpenParEM-specific formats fully within this
    module's own domain, verified against real source + real worked examples as cited
    above.
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
generated `.proj`/ports/materials files, nor is the real `gmsh` binary available to
verify a generated `.geo` script actually meshes cleanly. `.proj`/ports/materials-file
generation and CSV/Touchstone-existence parsing are built to the letter of the
primary-source citations above (each fact grepped directly out of OpenParEM's own C/C++
source, or quoted verbatim from its own Installation Manual PDF, Users Manual PDF, and a
real worked-example project file -- not reconstructed from memory or "what seems
plausible"), and exercised in tests only against small fake "OpenParEM3D"/"gmsh" scripts
that write the documented output-file shapes (see tests/test_openparem.py) -- NOT against
real FEM physics, a real mesh, or a real OpenParEM3D run. Treat any result as unverified
end-to-end until it has been run against the real tools at least once. OpenParEM being
young and comparatively unproven (vs. HFSS/openEMS/NEC2++, each with a much longer track
record) is an additional reason for caution beyond this codebase's usual "no real binary
in this sandbox" caveat.
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
from .elmer import generate_gmsh_geo_script
from .elmer import run_gmsh_meshing as _elmer_run_gmsh_meshing

# ---------------------------------------------------------------------------
# OpenParemSimulator: the Simulator contract (simulation/base.py, unchanged) --
# shells out to the real OpenParEM3D binary against an already-written .proj file.
# See module docstring for the CLI-contract citation.
# ---------------------------------------------------------------------------


class OpenParemSimulator(Simulator):
    name = "OpenParEM3D"

    def __init__(self, executable: str | None = None):
        self.executable = executable or os.getenv("OPENPAREM3D_BIN") or "OpenParEM3D"

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
            "project['frequency_plan'] must supply a non-empty 'linear', 'log', or 'point' list"
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
    lines.append(f"mesh.quality.limit              {_fmt(project.get('mesh_quality_limit', 20.0))}")
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
                f"port {idx}['impedance_definition'] must be one of {_VALID_IMPEDANCE_DEFINITION}"
            )
        impedance_calculation = port.get("impedance_calculation", "modal")
        if impedance_calculation not in _VALID_IMPEDANCE_CALCULATION:
            raise ValueError(
                f"port {idx}['impedance_calculation'] must be one of {_VALID_IMPEDANCE_CALCULATION}"
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
                    f"port {idx} ({name!r}) mode {mode_idx} missing 'sport' or 'integration_path'"
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
                    f"port {idx} ({name!r}) mode {mode_idx} missing integration_path['path']"
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
# Gmsh msh22 mesh generation (issue #278) -- reuses simulation.elmer's
# geometry-dict-to-.geo translation (identical primitive-dict shape) and
# shells out to gmsh with OpenParEM3D's own required mesh format. See module
# docstring's mesh-format-constraint citation for why this is `msh22`, not
# Elmer's `msh2`.
# ---------------------------------------------------------------------------


def run_openparem_gmsh_meshing(
    geo_file: Path,
    msh_file: Path,
    workdir: Path,
    executable: str | None = None,
    timeout_s: int = 600,
) -> None:
    """Invoke gmsh to mesh `geo_file` into `msh_file`, forcing the msh22 ASCII
    format OpenParEM3D's own parser requires ("OpenParEM only works with the
    msh22 format of gmsh due to library limitations" -- Installation Manual
    Sec. 4.2, quoted in this module's docstring) -- unlike
    `simulation.elmer.run_gmsh_meshing`'s own default, which forces the OLDER
    msh2 format ElmerGrid's own reader expects.

    A thin, format-pinned wrapper around `simulation.elmer.run_gmsh_meshing`
    itself (rather than a second copy of its subprocess-invocation/error-
    handling body) -- both adapters invoke the SAME external `gmsh` binary
    under the SAME `GMSH_BIN` env-var/executable-override convention, so this
    only supplies the one thing that differs: `mesh_format="msh22"`.
    `SimulatorError` on a missing `.geo` file, nonzero exit, or timeout is
    `run_gmsh_meshing`'s own behavior, inherited unchanged."""
    _elmer_run_gmsh_meshing(
        geo_file,
        msh_file,
        workdir,
        executable=executable,
        timeout_s=timeout_s,
        mesh_format="msh22",
    )


# ---------------------------------------------------------------------------
# Materials-file generation (issue #278). See module docstring for the full
# keyword/default/mandatory-field citation list (verified against both
# OpenParEM3D_Users_Manual.tex's own Verbatim spec AND
# src/OpenParEMCommon/OpenParEMmaterials.cpp's push_alias()/check() calls).
# ---------------------------------------------------------------------------


def _material_temperature_token(value: Any) -> str:
    return "any" if value == "any" else _fmt(value)


def _material_citation_lines(material: dict[str, Any]) -> list[str]:
    """Return one or more Source/EndSource blocks -- OpenParEM3D's own
    materials-file spec requires at least one per Material (`MaterialDatabase`'s
    ERROR1083, "must specify at least one Source block"), and this repo never
    emits an uncited material property (ADR-0015's citation discipline,
    already enforced by designs/material_properties.py's own `add_entry`)."""
    name = material.get("name", "<unnamed>")
    citations = material.get("citations")
    if citations is None:
        single = material.get("citation")
        citations = [single] if single else []
    elif isinstance(citations, str):
        citations = [citations]
    citations = [c for c in citations if c]
    if not citations:
        raise ValueError(
            f"material {name!r} requires a non-empty 'citations' list (or 'citation' "
            "string) -- OpenParEM's own materials-file spec requires a Source/EndSource "
            "block per Material, and this repo never emits an uncited material property "
            "(ADR-0015)"
        )
    lines: list[str] = []
    for citation in citations:
        lines.append("   Source")
        lines += [f"      {text_line}" for text_line in str(citation).splitlines()]
        lines.append("   EndSource")
    return lines


def _frequency_point_tokens(material: dict[str, Any]) -> list[str]:
    """Return the `frequency=` value(s) for one Temperature block's Frequency
    sub-blocks -- see generate_openparem_materials_file's own docstring for
    why a cited validity BAND (frequency_low_hz != frequency_high_hz) becomes
    TWO identical-valued points bracketing that band, rather than one."""
    if "frequency_hz" in material:
        value = material["frequency_hz"]
        return ["any"] if value == "any" else [_fmt(value)]
    low = material.get("frequency_low_hz")
    high = material.get("frequency_high_hz")
    if low is None or high is None:
        return ["any"]
    if low == high:
        return [_fmt(low)]
    return [_fmt(low), _fmt(high)]


def _resolve_loss(container: dict[str, Any], name: str) -> tuple[str, float]:
    loss_tangent = container.get("loss_tangent")
    conductivity = container.get("conductivity_s_per_m")
    if (loss_tangent is None) == (conductivity is None):
        raise ValueError(
            f"material {name!r} must supply exactly one of 'loss_tangent' or "
            "'conductivity_s_per_m' -- OpenParEM's own Temperature/Frequency blocks "
            f"require exactly one loss mechanism, got loss_tangent={loss_tangent!r}, "
            f"conductivity_s_per_m={conductivity!r}"
        )
    if loss_tangent is not None:
        return "loss_tangent", loss_tangent
    return "conductivity", conductivity


def _build_frequency_list_material(material: dict[str, Any]) -> list[str]:
    name = material.get("name")
    if not name:
        raise ValueError(f"material entry missing non-empty 'name': {material!r}")

    relative_permittivity = material.get("relative_permittivity", 1.0)
    relative_permeability = material.get("relative_permeability", 1.0)
    loss_keyword, loss_value = _resolve_loss(material, name)
    rz = material.get("surface_roughness_rz_m", 0.0)

    temperature_token = _material_temperature_token(material.get("temperature_c", "any"))
    lines = ["Material", f"   name={name}", "   Temperature"]
    lines.append(f"      temperature={temperature_token}")
    for freq_token in _frequency_point_tokens(material):
        lines.append("      Frequency")
        lines.append(f"         frequency={freq_token}")
        lines.append(f"         er={_fmt(relative_permittivity)}")
        lines.append(f"         mur={_fmt(relative_permeability)}")
        lines.append(f"         {loss_keyword}={_fmt(loss_value)}")
        lines.append(f"         Rz={_fmt(rz)}")
        lines.append("      EndFrequency")
    lines.append("   EndTemperature")
    lines += _material_citation_lines(material)
    lines.append("EndMaterial")
    return lines


_DEBYE_REQUIRED_FIELDS = ("epsr_infinity", "delta_epsr", "m1", "m2")


def _build_debye_material(material: dict[str, Any]) -> list[str]:
    name = material.get("name")
    if not name:
        raise ValueError(f"material entry missing non-empty 'name': {material!r}")
    debye = material["debye"]
    missing = [field for field in _DEBYE_REQUIRED_FIELDS if debye.get(field) is None]
    if missing:
        raise ValueError(
            f"material {name!r}'s 'debye' block is missing required field(s) {missing} "
            "-- OpenParEM3D's own Temperature::check() requires epsr_infinity/"
            "delta_epsr/m1/m2 for a Debye-model Material (see module docstring citation)"
        )
    relative_permeability = debye.get("relative_permeability", 1.0)
    loss_keyword, loss_value = _resolve_loss(debye, name)

    temperature_token = _material_temperature_token(debye.get("temperature_c", "any"))
    lines = ["Material", f"   name={name}", "   Temperature"]
    lines.append(f"      temperature={temperature_token}")
    lines.append(f"      epsr_infinity={_fmt(debye['epsr_infinity'])}")
    lines.append(f"      delta_epsr={_fmt(debye['delta_epsr'])}")
    lines.append(f"      m1={_fmt(debye['m1'])}")
    lines.append(f"      m2={_fmt(debye['m2'])}")
    lines.append(f"      mur={_fmt(relative_permeability)}")
    lines.append(f"      {loss_keyword}={_fmt(loss_value)}")
    lines.append("   EndTemperature")
    lines += _material_citation_lines(material)
    lines.append("EndMaterial")
    return lines


def generate_openparem_materials_file(materials: list[dict[str, Any]]) -> str:
    """Generate an OpenParEM3D materials-library text file (usable as either the
    `materials.global.name` or `materials.local.name` file -- both share this
    identical format; see module docstring) from a list of structured
    per-material dicts.

    Each entry in `materials` is EITHER a frequency-list material:
        {
          "name": str,                       # required
          "relative_permittivity": float,    # optional, default 1.0 (OpenParEM's own
              "copper_prepreg" worked example uses er=1 for a conductivity-only
              material -- see module docstring citation)
          "relative_permeability": float,    # optional, default 1.0 (non-magnetic --
              every material this repo's library models is)
          "loss_tangent": float,             # exactly one of these two required
          "conductivity_s_per_m": float,
          "surface_roughness_rz_m": float,   # optional, default 0.0 (OpenParEM's own
              "air" worked example; unconditionally required by the real parser
              regardless of whether the material is a conductor -- see module
              docstring's Rz citation)
          "temperature_c": float | "any",    # optional, default "any"
          "frequency_hz": float | "any",     # a single point or "any" -- mutually
              exclusive with the next two keys
          "frequency_low_hz": float, "frequency_high_hz": float,  # a cited validity
              BAND -- emitted as ONE Frequency point if they're equal, or TWO
              identical-valued points bracketing the band if not (see
              _frequency_point_tokens's docstring for why: OpenParEM3D's own C++
              source -- an inline comment repeated identically in
              Temperature::get_eps()/get_mu()/get_Rs(), OpenParEMmaterials.cpp,
              NOT either manual PDF, see module docstring's Materials-file citation
              -- documents linear interpolation between declared points and
              explicitly "extrapolation is not supported", so two points at the
              citation's own validated range edges is the most literal, honest
              translation of "flat across this exact band, unclaimed outside it").
              Neither this pair nor `frequency_hz` given -> "any".
          "citations": list[str] | "citation": str,  # required, non-empty
        }
    OR a Debye-model material (mutually exclusive with the frequency-list keys above,
    matching OpenParEM's own ERROR1058 "Debye variable ... not allowed with frequency
    blocks defined"):
        {
          "name": str,
          "debye": {
              "epsr_infinity": float, "delta_epsr": float, "m1": float, "m2": float,
                  # all four required
              "relative_permeability": float,  # optional, default 1.0
              "loss_tangent": float, "conductivity_s_per_m": float,  # exactly one
              "temperature_c": float | "any",  # optional, default "any"
          },
          "citations": list[str] | "citation": str,
        }

    This function does not resolve disagreeing citations for the same material --
    see `openparem_materials_from_property_entries` for the converter that turns
    `designs/material_properties.py`-shaped rows (which CAN disagree across several
    citations; that library's own `resolve_material_property` is what picks one) into
    this function's single-value-per-material input shape.
    """
    if not materials:
        raise ValueError("materials must be a non-empty list")

    lines: list[str] = ["#OpenParEMmaterials 1.0", ""]
    for idx, material in enumerate(materials):
        if not isinstance(material, dict):
            raise ValueError(f"materials[{idx}] must be a dict, got {type(material).__name__}")
        if material.get("debye") is not None:
            lines += _build_debye_material(material)
        else:
            lines += _build_frequency_list_material(material)
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


# ---------------------------------------------------------------------------
# designs/material_properties.py -> generate_openparem_materials_file() bridge
# (issue #278). "Caller fetches, pure function resolves": resolving WHICH
# citation to trust when several disagree is designs.material_properties.
# resolve_material_property()'s job (already built); this function only
# reshapes an already-decided set of per-material rows into OpenParEM's
# materials-file input shape -- it never picks a winner among disagreeing
# citations itself.
# ---------------------------------------------------------------------------

_SUPPORTED_MATERIAL_PROPERTY_NAMES = frozenset({"eps_r", "tan_delta", "conductivity_s_per_m"})


def openparem_materials_from_property_entries(
    entries: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Convert a flat list of `designs/material_properties.py`-shaped entries
    (whatever `lookup_entries()`, or a caller's own already-resolved
    `resolve_material_property()` call, returned -- each carrying `material`,
    `property`, `frequency_low_hz`, `frequency_high_hz`, `value`, `citation`)
    into `generate_openparem_materials_file`'s per-material dict shape, one
    dict per distinct `material` name.

    Deliberately narrow scope (this codebase's "warn, never silently apply the
    wrong tool" convention): each material must contribute EXACTLY ONE `eps_r`
    entry and EXACTLY ONE of a `tan_delta` or `conductivity_s_per_m` entry, and
    the two must share the IDENTICAL frequency_low_hz/frequency_high_hz band --
    this function does not resolve disagreeing citations (several eps_r entries
    at different bands is this library's own documented norm, see
    designs/material_properties.py's "WHY EVERY MATCHING CITATION..." section);
    a caller with more than one candidate must call `resolve_material_property`
    (or otherwise pick one) FIRST, then hand this function one already-decided
    entry per property per material. A missing pair, a mismatched band, more
    than one entry for the same material+property, or a property name this
    function does not know how to map onto an OpenParEM keyword all raise
    `ValueError` naming exactly what's wrong rather than guessing.

    `relative_permeability` (`mur`) and `surface_roughness_rz_m` (`Rz`) are left
    at `generate_openparem_materials_file`'s own defaults (1.0/0.0) for every
    material this produces -- `designs/material_properties.py` tracks neither
    property today (only eps_r/tan_delta/conductivity_s_per_m are ever seeded
    there), and those defaults are exactly OpenParEM's own worked "air"
    example's values for a non-magnetic, non-conductor material (see
    generate_openparem_materials_file's own docstring citation); every material
    this repo's library actually models (FR4, Rogers laminates, polymers,
    copper) is likewise non-magnetic.
    """
    by_material: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for entry in entries:
        material = entry.get("material")
        property_name = entry.get("property")
        if not material:
            raise ValueError(f"entry missing non-empty 'material': {entry!r}")
        if property_name not in _SUPPORTED_MATERIAL_PROPERTY_NAMES:
            raise ValueError(
                f"material {material!r} has unsupported property {property_name!r} -- "
                "generate_openparem_materials_file only knows how to map "
                f"{sorted(_SUPPORTED_MATERIAL_PROPERTY_NAMES)} onto OpenParEM materials-"
                "file keywords; add a mapping here rather than silently dropping it"
            )
        by_material.setdefault(material, {}).setdefault(property_name, []).append(entry)

    materials: list[dict[str, Any]] = []
    for material, by_property in by_material.items():
        eps_entries = by_property.get("eps_r", [])
        if len(eps_entries) != 1:
            raise ValueError(
                f"material {material!r} has {len(eps_entries)} 'eps_r' entries -- "
                "generate_openparem_materials_file needs exactly one already-resolved "
                "permittivity value per material (call resolve_material_property first "
                "to pick one if several citations disagree)"
            )
        eps_entry = eps_entries[0]

        tand_entries = by_property.get("tan_delta", [])
        cond_entries = by_property.get("conductivity_s_per_m", [])
        if len(tand_entries) + len(cond_entries) != 1:
            raise ValueError(
                f"material {material!r} needs exactly one loss entry (a single "
                f"'tan_delta' or 'conductivity_s_per_m'), found {len(tand_entries)} "
                f"tan_delta and {len(cond_entries)} conductivity_s_per_m entries"
            )
        loss_entry = tand_entries[0] if tand_entries else cond_entries[0]
        loss_field = "loss_tangent" if tand_entries else "conductivity_s_per_m"

        if (
            eps_entry["frequency_low_hz"] != loss_entry["frequency_low_hz"]
            or eps_entry["frequency_high_hz"] != loss_entry["frequency_high_hz"]
        ):
            raise ValueError(
                f"material {material!r}'s eps_r validity band "
                f"({eps_entry['frequency_low_hz']:g}-{eps_entry['frequency_high_hz']:g} Hz) "
                "does not match its loss-property validity band "
                f"({loss_entry['frequency_low_hz']:g}-{loss_entry['frequency_high_hz']:g} Hz)"
                " -- refusing to pair values from different citations/bands"
            )

        citations: list[str] = []
        for source in (eps_entry, loss_entry):
            citation = source.get("citation")
            if citation and citation not in citations:
                citations.append(citation)

        materials.append(
            {
                "name": material,
                "relative_permittivity": eps_entry["value"],
                loss_field: loss_entry["value"],
                "frequency_low_hz": eps_entry["frequency_low_hz"],
                "frequency_high_hz": eps_entry["frequency_high_hz"],
                "citations": citations,
            }
        )
    return materials


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
    ports: dict[str, Any],
    mesh_file: str | None = None,
    geometry: dict[str, Any] | None = None,
    project: dict[str, Any] | None = None,
    project_name: str = "openparem_project",
    materials: list[dict[str, Any]] | None = None,
    mpi_processes: int | None = None,
    timeout_s: int = 3600,
    executable: str | None = None,
    workdir: str | None = None,
    gmsh_executable: str | None = None,
    gmsh_timeout_s: int = 600,
) -> dict[str, Any]:
    """Generate an OpenParEM3D `.proj` file and ports/boundary file from structured
    settings/geometry, run OpenParEM3D via OpenParemSimulator, and parse S-parameter
    and far-field gain/directivity/radiation-efficiency results tagged with SIMULATED
    provenance.

    Exactly one of `mesh_file` (an already-generated Gmsh msh22 mesh) or `geometry`
    (this repo's own primitive-dict shape, e.g. `{"domain": {"p1_m": ..., "p2_m":
    ...}}` -- see `simulation.elmer.generate_gmsh_geo_script`'s own docstring for the
    full shape) must be given (issue #278). When `geometry` is given, this function
    drives `generate_gmsh_geo_script()` -> `run_openparem_gmsh_meshing()` (forcing
    OpenParEM3D's required msh22 format) to produce the mesh itself, before invoking
    `OpenParemSimulator`.

    `materials` is optional: a list of `generate_openparem_materials_file`'s
    per-material dicts (or `openparem_materials_from_property_entries`'s output) --
    when given, a local materials file is generated and wired into `project['materials']`
    (`materials.local.name`/`.local.path`). Mutually exclusive with a caller-supplied
    `project['materials']` (which still works unchanged when `materials` is omitted,
    pointing at a pre-existing library file exactly as before).

    `ports` is `generate_openparem_ports_file`'s input shape; `project` is
    `generate_openparem_project_config`'s input shape minus `mesh_file`/
    `port_definition_file`/`materials` (all filled in here).

    See this module's header comment for the format-verification citations and the
    honest caveat: generation and parsing are built to the documented/verified
    OpenParEM3D `.proj`/ports/materials-file/output-file formats, not to a real
    OpenParEM3D (or gmsh) binary run in this environment.
    """
    if (mesh_file is None) == (geometry is None):
        raise ValueError(
            "run_openparem_simulation requires exactly one of 'mesh_file' (an "
            "already-meshed msh22 file) or 'geometry' (drive meshing internally via "
            "generate_gmsh_geo_script + run_openparem_gmsh_meshing) -- got "
            f"mesh_file={mesh_file!r}, geometry given={geometry is not None}"
        )

    work_dir = Path(workdir) if workdir else Path(tempfile.mkdtemp(prefix="openparem_"))
    work_dir.mkdir(parents=True, exist_ok=True)

    output: dict[str, Any] = {}

    if geometry is not None:
        geo_file = work_dir / f"{project_name}.geo"
        geo_file.write_text(generate_gmsh_geo_script(geometry))
        mesh_filename = f"{project_name}.msh"
        msh_path = work_dir / mesh_filename
        run_openparem_gmsh_meshing(
            geo_file, msh_path, work_dir, executable=gmsh_executable, timeout_s=gmsh_timeout_s
        )
        mesh_file = mesh_filename
        output["geo_file"] = str(geo_file)
        output["msh_file"] = str(msh_path)

    ports_filename = f"{project_name}_ports.txt"
    ports_path = work_dir / ports_filename
    ports_path.write_text(generate_openparem_ports_file(ports))

    project_settings = dict(project or {})

    # This function's own docstring documents `project` as `generate_openparem_
    # project_config`'s input shape MINUS mesh_file/port_definition_file/materials
    # -- all three are filled in here, below, from the `mesh_file`/`geometry`,
    # `ports`, and `materials` arguments respectively. Guard all three the same
    # way (a named ValueError, not a silent overwrite) so a caller who puts one
    # of these keys in `project` by mistake is told, rather than having it
    # quietly discarded -- this codebase's "warn, never silently fall through to
    # the wrong tool" discipline (see module docstring).
    if "mesh_file" in project_settings:
        raise ValueError(
            "run_openparem_simulation got project['mesh_file'] set explicitly -- "
            "this key is always filled in here from the 'mesh_file' argument (or "
            "the mesh generated from 'geometry') -- pass the mesh via 'mesh_file'/"
            "'geometry' instead of inside 'project'"
        )
    if "port_definition_file" in project_settings:
        raise ValueError(
            "run_openparem_simulation got project['port_definition_file'] set "
            "explicitly -- this key is always filled in here from the 'ports' "
            "argument -- do not set it inside 'project'"
        )
    if materials is not None:
        if "materials" in project_settings:
            raise ValueError(
                "run_openparem_simulation got both a 'materials' argument and "
                "project['materials'] -- supply exactly one materials source (a "
                "caller-written library via project['materials'], or a generated "
                "local library via 'materials')"
            )
        materials_filename = f"{project_name}_materials.txt"
        materials_path = work_dir / materials_filename
        materials_path.write_text(generate_openparem_materials_file(materials))
        project_settings["materials"] = {"local_path": "./", "local_name": materials_filename}
        output["materials_file"] = str(materials_path)

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

    output.update(
        {
            "provenance": "SIMULATED",
            "s_parameters": parsed["s_parameters"],
            "far_field": parsed["far_field"],
            "simulator": result.simulator,
            "status": result.status,
            "workdir": str(result.workdir),
            "project_file": str(project_file),
            "ports_file": str(ports_path),
        }
    )
    if "touchstone_file" in parsed:
        # Surfaced at top level, matching simulation/openems.py's/simulation/hfss.py's
        # own "touchstone_file" convention for rf_tools.correlation integration.
        output["touchstone_file"] = parsed["touchstone_file"]
    return output
