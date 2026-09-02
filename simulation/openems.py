import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from .base import SimulationResult, Simulator, SimulatorError


class OpenemsSimulator(Simulator):
    name = "openEMS"

    def __init__(self, executable: str | None = None):
        self.executable = executable or os.getenv("OPENEMS_BIN", "openEMS")

    def run(self, job: dict) -> SimulationResult:
        xml_file = Path(job["xml_file"]).resolve()
        workdir = Path(job.get("workdir", xml_file.parent)).resolve()
        if not xml_file.exists():
            raise SimulatorError(f"openEMS FDTD XML file not found: {xml_file}")

        # openEMS's own CLI contract (see module docstring citation): "Usage:
        # openEMS <FDTD_XML_FILE> [<options>...]" -- a single positional XML
        # file argument, then flags. --disable-dumps is passed by default
        # since this adapter does not read/parse the H5 field-dump files
        # openEMS would otherwise write (out of scope, see module docstring);
        # suppressing them keeps a run's on-disk footprint and runtime down.
        # An empty extra_args list restores the plain default invocation.
        extra_args = job.get("extra_args", ["--disable-dumps"])
        timeout_s = int(job.get("timeout_s", 3600))
        try:
            completed = subprocess.run(
                [self.executable, str(xml_file), *extra_args],
                cwd=workdir,
                capture_output=True,
                text=True,
                timeout=timeout_s,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise SimulatorError(
                f"openEMS timed out after {timeout_s}s: {exc}"
            ) from exc
        if completed.returncode != 0:
            raise SimulatorError(
                f"openEMS failed ({completed.returncode}): {completed.stderr[-4000:]}"
            )

        # openEMS's per-timestep progress/energy log (parsed below for
        # convergence metadata) is printed throughout a run and can be long
        # for a real simulation, but the lines this module's parser actually
        # needs -- the final progress line, the "Time for N iterations..."
        # summary, and any max-timesteps warning -- are always at the *end*
        # of stdout, so (like the old pre-#38 stub) this tail-truncates
        # rather than keeping the full text; unlike NEC2++'s output (kept in
        # full in nec2pp.py, see that module for why), nothing this parser
        # reads lives earlier in the stream.
        return SimulationResult(
            simulator=self.name,
            status="COMPLETED",
            workdir=workdir,
            outputs={"stdout": completed.stdout[-8000:]},
        )


# ---------------------------------------------------------------------------
# openEMS FDTD-XML geometry/materials/ports/mesh generation, execution, and
# result parsing (issue #39).
#
# SOURCES CONSULTED (primary; all fetched directly from the upstream
# openEMS/CSXCAD GitHub repositories during implementation -- see the
# per-fact citations below):
#   - CLI invocation contract ("Usage: openEMS <FDTD_XML_FILE>
#     [<options>...]", and the --disable-dumps/--debug-material/
#     --debug-PEC/--debug-operator/--engine/--numThreads/--no-simulation/
#     --dump-statistics option set): openEMS's own showUsage()/
#     collectCommandLineArguments() in
#     github.com/thliebig/openEMS/blob/master/openems.cpp.
#   - End-criteria/timestep convergence semantics: the same openems.cpp --
#     RunFDTD()'s loop condition is
#     `(FDTD_Eng->GetNumberOfTimesteps()<NrTS) && (change>endCrit) &&
#     !CheckAbortCond()`, i.e. a run stops on *either* the max-timestep
#     count (NrTS, XML attribute "NumberOfTimesteps") or the energy decay
#     dropping below endCriteria (XML attribute "endCriteria" on the same
#     <FDTD> element, default 1e-5 per matlab/InitFDTD.m at the same repo,
#     1e-6 per the C++ Reset() default if the XML omits it).
#   - Console log formats used by parse_openems_output() below -- the
#     per-timestep progress line ("[@ TIME] Timestep: N || Speed: X MC/s
#     (Y s/TS) || Energy: ~Z (- WdB)"), the closing summary line ("Time for
#     N iterations with M.00 cells : S sec" / "Speed: R MCells/s"), and the
#     "Max. number of timesteps was reached before the end-criteria of
#     -NNdB was reached" warning: real sample output transcribed in
#     thliebig/openEMS-Project GitHub discussions/issues and a public
#     openEMS/pyEMS run-log gist (gist.github.com/biergaizi/
#     7f45c243f6e17b509bd1ea785a6af9e7), cross-referenced against the
#     endCriteria/NrTS semantics above from openems.cpp itself. NOT
#     re-verified against a real openEMS run in this environment (see the
#     HONEST CAVEAT below) -- unlike the NEC-2 guide's output, this text
#     was not read out of one single official reference document, so the
#     parser below matches these forms with tolerant regexes rather than
#     assuming byte-exact formatting.
#   - FDTD-XML file shape -- root element <openEMS> wrapping sibling <FDTD>
#     and <ContinuousStructure> elements: matlab/WriteOpenEMS.m in the
#     openEMS repo (`openEMS.FDTD = FDTD; openEMS.ContinuousStructure =
#     CSX; struct_2_xml(filename, openEMS, 'openEMS')`).
#   - <FDTD> attributes NumberOfTimesteps / endCriteria: matlab/InitFDTD.m
#     (`FDTD.ATTRIBUTE.NumberOfTimesteps=NrTS`, `FDTD.ATTRIBUTE.
#     endCriteria=endCrit`), confirming these are direct XML attributes of
#     the <FDTD> element (matching the QueryDoubleAttribute("endCriteria",
#     ...) read in openems.cpp).
#   - <ContinuousStructure CoordSystem="..."> and its <Properties>
#     container (children named after the property's own C++ class --
#     "Material", "Metal", "Excitation", "LumpedElement", "ProbeBox",
#     etc.) each holding a <Primitives> container (children "Box",
#     "Cylinder", etc.): ContinuousStructure::Write2XML/ReadFromXML in
#     github.com/thliebig/CSXCAD/blob/master/src/ContinuousStructure.cpp.
#   - <RectilinearGrid CoordSystem="..." DeltaUnit="..."> with child
#     <XLines Qty="N">v1,v2,...</XLines> (and Y/ZLines, comma-separated
#     text content): CSRectGrid::Write2XML in
#     github.com/thliebig/CSXCAD/blob/master/src/CSRectGrid.cpp.
#   - <Box>/<Cylinder> primitive geometry -- corner/axis points as child
#     elements <P1 .../><P2 .../> (not attributes of the primitive itself),
#     Cylinder additionally carrying a plain "Radius" attribute:
#     CSPrimBox.cpp and CSPrimCylinder.cpp Write2XML, same CSXCAD repo.
#     P1/P2's own X/Y/Z attribute form corroborated independently by a
#     third-party post-processing script description in
#     rdmontoya.wordpress.com/2020/06/17/ (decimal-locale fixups applied to
#     "P1/P2 coordinates (X, Y, Z)" and "Excitation Delay/Frequency"
#     attributes in real generated openEMS XML files).
#   - <Material> Epsilon/Mue/Kappa/Sigma vector terms and <Excitation>
#     Type/Excite/Frequency/Delay terms: CSPropMaterial.cpp and
#     CSPropExcitation.cpp Write2XML, same CSXCAD repo -- WriteTerm(...)
#     (used for Radius, Frequency, Delay, R/C/L below) writes a plain
#     attribute on the element passed to it; WriteVectorTerm(...) (used for
#     Epsilon/Mue/Kappa/Sigma/Excite) writes a *child* element (named after
#     the term) carrying X/Y/Z attributes -- inferred from the P1/P2
#     child-element pattern above and the third-party script's own
#     independent read of real generated XML, not from reading
#     WriteVectorTerm's body directly (not fetched in this pass).
#   - <LumpedElement Direction="..." Caps="..." R="..." C="..." L="..."
#     LEtype="...">: CSPropLumpedElement.cpp Write2XML, same CSXCAD repo.
#   - AddLumpedPort(port_nr, R, start, stop, p_dir, excite) /
#     SetGaussExcite(f0, fc) call shapes (informing this module's job/
#     geometry dict shape, not its XML output): openEMS's own Python
#     interface docs and worked examples (docs.openems.de /
#     openems.readthedocs.io, "openEMS Python Interface"; thliebig/
#     openEMS-Project GitHub discussions #64 and #231).
#
# SCOPE OF THIS IMPLEMENTATION (explicitly narrower than a full openEMS
# feature set, per this ticket's own guidance to scope down rather than
# claim full parity):
#   - Geometry primitives: axis-aligned Box and Cylinder only (no Sphere/
#     Polygon/Polyhedron/etc, though CSXCAD supports more).
#   - Materials: isotropic only (a single epsilon_r/mue_r/kappa applied
#     identically to X/Y/Z) -- CSXCAD's real per-axis anisotropic tensors
#     are not exposed here.
#   - Ports: modeled as one <Excitation> property (the drive signal) plus
#     one <LumpedElement> property (the R-ohm termination) sharing the same
#     box, one Gaussian-pulse Frequency term per port. openEMS's own
#     AddLumpedPort() Python helper additionally attaches a pair of
#     <ProbeBox> voltage/current-recording properties to the same box for
#     later post-processing; this module does NOT generate those ProbeBox
#     elements, because it also does not implement the FFT-based S-
#     parameter extraction that would consume their output (see below) --
#     adding unconsumed probe boxes would be XML for its own sake.
#   - S-parameters and far-field/gain: NOT computed from real field/port
#     data in this pass. A real S11/S21 extraction requires FFT-processing
#     the port voltage/current *time-domain* data openEMS writes during the
#     run, and a real far-field/gain pattern requires openEMS's separate
#     nf2ff near-field-to-far-field post-processing tool -- both are
#     explicitly out of scope per this ticket's guidance ("far-field/nf2ff
#     post-processing is stubbed/simplified"). parse_openems_output()
#     still returns "s_parameters" and "far_field" keys, structurally
#     parallel to NEC2++'s "impedance"/"pattern"/"gain_dbi" keys (so
#     downstream code can treat both simulators' results uniformly without
#     per-simulator branching), but each carries computed=False and a note
#     explaining why, rather than fabricated numbers.
#   - Convergence metadata (this ticket's other acceptance criterion) IS
#     real: it is parsed from openEMS's own progress/summary log text
#     (format cited above) to report whether a run's exit was end-criteria-
#     driven (energy decayed below endCriteria -- the mesh/excitation
#     converged) or hit max timesteps (NrTS reached first -- a signal the
#     mesh/excitation setup may need revision, per openEMS's own logged
#     warning), which is the signal actually available from a run's exit
#     condition.
#
# HONEST CAVEAT: the real `openEMS` binary is NOT installed in this
# environment (confirmed via `which openEMS`, exit 1) and was not available
# to run against these generated FDTD-XML files. XML generation follows the
# element/attribute names verified against CSXCAD/openEMS source as cited
# above; the console-log parser is exercised in tests only against a fake
# "openEMS" script (see tests/test_openems.py) whose sample log lines were
# transcribed from the third-party run logs cited above, not from output
# this implementation produced by actually running the real tool. Treat any
# result -- and in particular the exact wording match on the max-timesteps
# warning -- as unverified end-to-end until run against the real binary.
# ---------------------------------------------------------------------------


def _fmt(value: float) -> str:
    return f"{float(value):.6g}"


def _p_element(tag: str, xyz: tuple[float, float, float]) -> str:
    x, y, z = xyz
    return f'<{tag} X="{_fmt(x)}" Y="{_fmt(y)}" Z="{_fmt(z)}"/>'


def _primitive_xml(prim: dict[str, Any]) -> str:
    """Render one Box or Cylinder primitive (see module docstring citation
    for the P1/P2 child-element and Cylinder "Radius" attribute forms)."""
    shape = prim.get("shape", "box")
    p1 = (prim["p1_m"][0], prim["p1_m"][1], prim["p1_m"][2])
    p2 = (prim["p2_m"][0], prim["p2_m"][1], prim["p2_m"][2])
    if shape == "box":
        return "<Box>" + _p_element("P1", p1) + _p_element("P2", p2) + "</Box>"
    if shape == "cylinder":
        if "radius_m" not in prim:
            raise ValueError("cylinder primitive requires 'radius_m'")
        return (
            f'<Cylinder Radius="{_fmt(prim["radius_m"])}">'
            + _p_element("P1", p1)
            + _p_element("P2", p2)
            + "</Cylinder>"
        )
    raise ValueError(f"shape must be 'box' or 'cylinder', got {shape!r}")


def generate_openems_xml(
    geometry: dict[str, Any],
    fdtd: dict[str, Any] | None = None,
    comment: str = "Generated by run_openems_simulation",
) -> str:
    """Generate an openEMS FDTD-XML simulation-description file from
    structured geometry/materials/ports/mesh input.

    `geometry` shape:
        {
          "materials": [                 # dielectric/lossy layers, optional
              {
                "name": str,
                "shape": "box" (default) | "cylinder",
                "p1_m", "p2_m": [x, y, z],   # corner/axis-endpoint points
                "radius_m": float,           # cylinder only
                "epsilon_r": float (default 1.0),
                "mue_r": float (default 1.0),
                "kappa_s_m": float (default 0.0),   # electric conductivity
              }, ...
          ],
          "conductors": [                # PEC layers (patch, ground, etc.)
              {"name": str, "shape": "box"|"cylinder", "p1_m", "p2_m",
               "radius_m" (cylinder only)}, ...
          ],
          "ports": [                     # at least one required
              {
                "name": str,
                "p1_m", "p2_m": [x, y, z],   # the port gap box
                "direction": "x" | "y" | "z",
                "resistance_ohms": float (default 50.0),
                "excite": bool (default True for the first port, else
                    False -- only one active/driven port is typical for a
                    single-port S11 sweep),
                "frequency_hz": float,   # Gaussian-pulse center frequency;
                    defaults to the top-level frequency_hz passed to
                    run_openems_simulation.
              }, ...
          ],
          "mesh": {                      # rectilinear mesh lines, meters
              "x_lines_m": [float, ...], "y_lines_m": [...], "z_lines_m": [...],
          },
        }

    `fdtd` shape (all optional): {"max_timesteps": int (default 30000),
    "end_criteria": float (default 1e-5, the openEMS-documented default --
    see module docstring citation)}.

    Geometry is in meters; DeltaUnit is fixed at 1.0 (i.e. the mesh line
    values above are the actual meter coordinates, not scaled) since this
    module always emits already-metric mesh/primitive coordinates.
    """
    materials = geometry.get("materials", [])
    conductors = geometry.get("conductors", [])
    ports = geometry.get("ports")
    if not ports:
        raise ValueError("geometry['ports'] must be a non-empty list")
    mesh = geometry.get("mesh")
    if not mesh or not all(
        mesh.get(k) for k in ("x_lines_m", "y_lines_m", "z_lines_m")
    ):
        raise ValueError(
            "geometry['mesh'] must supply non-empty 'x_lines_m'/'y_lines_m'/'z_lines_m'"
        )

    fdtd = fdtd or {}
    max_timesteps = int(fdtd.get("max_timesteps", 30000))
    end_criteria = float(fdtd.get("end_criteria", 1e-5))

    parts: list[str] = ["<openEMS>"]
    parts.append(
        f'<FDTD NumberOfTimesteps="{max_timesteps}" endCriteria="{_fmt(end_criteria)}">'
        f"<!-- {comment} --></FDTD>"
    )
    parts.append('<ContinuousStructure CoordSystem="0">')

    def _lines(values: list[float]) -> str:
        return ",".join(_fmt(v) for v in values)

    x_lines = mesh["x_lines_m"]
    y_lines = mesh["y_lines_m"]
    z_lines = mesh["z_lines_m"]
    parts.append(
        '<RectilinearGrid CoordSystem="0" DeltaUnit="1">'
        f'<XLines Qty="{len(x_lines)}">{_lines(x_lines)}</XLines>'
        f'<YLines Qty="{len(y_lines)}">{_lines(y_lines)}</YLines>'
        f'<ZLines Qty="{len(z_lines)}">{_lines(z_lines)}</ZLines>'
        "</RectilinearGrid>"
    )

    parts.append("<Properties>")

    for idx, mat in enumerate(materials):
        required = ("p1_m", "p2_m")
        missing = [f for f in required if f not in mat]
        if missing:
            raise ValueError(f"material {idx} missing required field(s): {missing}")
        name = mat.get("name", f"material_{idx + 1}")
        eps = mat.get("epsilon_r", 1.0)
        mue = mat.get("mue_r", 1.0)
        kappa = mat.get("kappa_s_m", 0.0)
        parts.append(
            f'<Material Name="{name}">'
            + _p_element("Epsilon", (eps, eps, eps))
            + _p_element("Mue", (mue, mue, mue))
            + _p_element("Kappa", (kappa, kappa, kappa))
            + _p_element("Sigma", (0.0, 0.0, 0.0))
            + "<Primitives>"
            + _primitive_xml(mat)
            + "</Primitives>"
            + "</Material>"
        )

    for idx, cond in enumerate(conductors):
        required = ("p1_m", "p2_m")
        missing = [f for f in required if f not in cond]
        if missing:
            raise ValueError(f"conductor {idx} missing required field(s): {missing}")
        name = cond.get("name", f"conductor_{idx + 1}")
        parts.append(
            f'<Metal Name="{name}"><Primitives>'
            + _primitive_xml(cond)
            + "</Primitives></Metal>"
        )

    default_frequency_hz = geometry.get("frequency_hz")
    direction_axis = {"x": 0, "y": 1, "z": 2}
    for idx, port in enumerate(ports):
        required = ("p1_m", "p2_m", "direction")
        missing = [f for f in required if f not in port]
        if missing:
            raise ValueError(f"port {idx} missing required field(s): {missing}")
        direction = port["direction"]
        if direction not in direction_axis:
            raise ValueError(f"port {idx} direction must be 'x', 'y', or 'z', got {direction!r}")
        ny = direction_axis[direction]
        name = port.get("name", f"port_{idx + 1}")
        resistance = port.get("resistance_ohms", 50.0)
        excite = port.get("excite", idx == 0)
        frequency_hz = port.get("frequency_hz", default_frequency_hz)
        if excite and frequency_hz is None:
            raise ValueError(
                f"port {idx} is active (excite=True) but no frequency_hz was given "
                "(neither on the port nor as geometry['frequency_hz'])"
            )
        excite_vec = tuple(1.0 if a == ny else 0.0 for a in range(3))

        if excite:
            parts.append(
                f'<Excitation Name="{name}_exc" Type="0" '
                f'Frequency="{_fmt(frequency_hz)}" Delay="0">'
                + _p_element("Excite", excite_vec)
                + "<Primitives>"
                + _primitive_xml(port)
                + "</Primitives></Excitation>"
            )
        parts.append(
            f'<LumpedElement Name="{name}_R" Direction="{ny}" Caps="0" '
            f'R="{_fmt(resistance)}" C="0" L="0" LEtype="0">'
            + "<Primitives>"
            + _primitive_xml(port)
            + "</Primitives></LumpedElement>"
        )

    parts.append("</Properties>")
    parts.append("</ContinuousStructure>")
    parts.append("</openEMS>")
    return "\n".join(parts) + "\n"


# Matches openEMS's per-timestep progress line, e.g.
#   "[@ 4s] Timestep: 1326 || Speed: 88.8 MC/s (3.040e-03 s/TS) || Energy: ~7.06e-17 (- 0.00dB)"
# Tolerant of the exact whitespace/sign formatting since this was not
# verified byte-exact against a real binary (see module docstring caveat).
_PROGRESS_RE = re.compile(
    r"Timestep:\s*(\d+)\s*\|\|\s*Speed:\s*([\d.]+)\s*MC/s.*?\|\|\s*"
    r"Energy:\s*~?([\d.eE+-]+)\s*\(\s*-?\s*([\d.]+)\s*dB\)"
)

# Matches the closing summary line, e.g.
#   "Time for 14178 iterations with 269780.00 cells : 32.41 sec"
_SUMMARY_RE = re.compile(
    r"Time for\s*(\d+)\s*iterations with\s*([\d.]+)\s*cells\s*:\s*([\d.]+)\s*sec"
)

# Matches openEMS's speed report, e.g. "Speed: 118.02 MCells/s".
_SPEED_RE = re.compile(r"Speed:\s*([\d.]+)\s*MCells/s")

# Matches the warning openEMS logs when NrTS is hit before endCriteria is
# satisfied, e.g. "Max. number of timesteps was reached before the
# end-criteria of -50dB was reached". Matched loosely (not a fixed string)
# per the module docstring's caveat about this text's exact wording.
_MAX_TS_WARNING_RE = re.compile(
    r"max\.?\s*number of timesteps.*?(?:end.?criteria|end criteria)", re.IGNORECASE
)


def parse_openems_output(
    raw_output: str,
    end_criteria: float = 1e-5,
    max_timesteps: int | None = None,
) -> dict[str, Any]:
    """Parse openEMS console/log text into convergence metadata plus
    (stubbed, see module docstring "SCOPE") S-parameter and far-field keys.

    Convergence metadata is real, parsed from the progress/summary log
    lines and max-timesteps warning cited in this module's header comment.
    `terminated_reason` is:
      - "max_timesteps" if the logged max-timesteps warning is present, or
        (as a fallback signal) the final logged timestep is at/above
        max_timesteps;
      - "end_criteria" if a final progress line was found and the run
        stopped short of max_timesteps (the ordinary, converged case);
      - "unknown" if no progress line could be parsed at all (e.g. an
        empty or unrecognized log -- this is the honest fallback, not a
        guess dressed up as a signal).
    """
    progress_matches = list(_PROGRESS_RE.finditer(raw_output))
    final_timestep: int | None = None
    final_energy_linear: float | None = None
    final_energy_db: float | None = None
    if progress_matches:
        last = progress_matches[-1]
        final_timestep = int(last.group(1))
        final_energy_linear = float(last.group(3))
        final_energy_db = -float(last.group(4))

    summary_match = _SUMMARY_RE.search(raw_output)
    total_timesteps = int(summary_match.group(1)) if summary_match else final_timestep
    total_cells = float(summary_match.group(2)) if summary_match else None
    elapsed_s = float(summary_match.group(3)) if summary_match else None

    speed_match = _SPEED_RE.search(raw_output)
    speed_mcells_per_s = float(speed_match.group(1)) if speed_match else None

    hit_max_warning = bool(_MAX_TS_WARNING_RE.search(raw_output))
    if hit_max_warning or (
        max_timesteps is not None
        and total_timesteps is not None
        and total_timesteps >= max_timesteps
    ):
        terminated_reason = "max_timesteps"
    elif total_timesteps is not None:
        terminated_reason = "end_criteria"
    else:
        terminated_reason = "unknown"

    convergence = {
        "terminated_reason": terminated_reason,
        "final_timestep": total_timesteps,
        "max_timesteps": max_timesteps,
        "end_criteria": end_criteria,
        "final_energy_linear": final_energy_linear,
        "final_energy_db": final_energy_db,
        "total_cells": total_cells,
        "elapsed_s": elapsed_s,
        "speed_mcells_per_s": speed_mcells_per_s,
    }

    s_parameters = {
        "computed": False,
        "note": (
            "S-parameter extraction requires FFT post-processing of openEMS's "
            "port voltage/current time-domain output, which this implementation "
            "does not perform -- see simulation/openems.py's module docstring "
            "'SCOPE OF THIS IMPLEMENTATION'."
        ),
    }
    far_field = {
        "computed": False,
        "note": (
            "Far-field/gain pattern extraction requires openEMS's separate "
            "nf2ff near-field-to-far-field post-processing tool, which this "
            "implementation does not invoke -- see simulation/openems.py's "
            "module docstring 'SCOPE OF THIS IMPLEMENTATION'."
        ),
    }

    return {
        "convergence": convergence,
        "s_parameters": s_parameters,
        "far_field": far_field,
        "gain_dbi": None,
    }


def run_openems_simulation(
    geometry: dict[str, Any],
    fdtd: dict[str, Any] | None = None,
    timeout_s: int = 3600,
    executable: str | None = None,
    workdir: str | None = None,
) -> dict[str, Any]:
    """Generate an openEMS FDTD-XML file from structured geometry/materials/
    ports/mesh, run it via OpenemsSimulator, and parse convergence metadata
    plus (stubbed, see this module's header "SCOPE") S-parameter/far-field
    results tagged with SIMULATED provenance.

    See this module's header comment for the format-verification citations
    and the honest caveat: XML generation and log parsing are built to the
    documented/verified openEMS FDTD-XML and console-log formats, not to a
    real openEMS binary run in this environment.
    """
    work_dir = Path(workdir) if workdir else Path(tempfile.mkdtemp(prefix="openems_"))
    work_dir.mkdir(parents=True, exist_ok=True)
    xml_file = work_dir / "model.xml"
    fdtd = fdtd or {}
    xml_file.write_text(generate_openems_xml(geometry, fdtd))

    simulator = OpenemsSimulator(executable=executable)
    result = simulator.run(
        {"xml_file": str(xml_file), "workdir": str(work_dir), "timeout_s": timeout_s}
    )
    parsed = parse_openems_output(
        result.outputs.get("stdout", ""),
        end_criteria=float(fdtd.get("end_criteria", 1e-5)),
        max_timesteps=int(fdtd.get("max_timesteps", 30000)),
    )

    return {
        "provenance": "SIMULATED",
        "convergence": parsed["convergence"],
        "s_parameters": parsed["s_parameters"],
        "far_field": parsed["far_field"],
        "gain_dbi": parsed["gain_dbi"],
        "simulator": result.simulator,
        "status": result.status,
        "workdir": str(result.workdir),
        "xml_file": str(xml_file),
    }
