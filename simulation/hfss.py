"""HFSS/PyAEDT simulation on a controlled, licensed workstation (issue #40).
Phase 8 -- the last simulation-phase ticket (Phases 6-8 complete after this).

CRITICAL DIFFERENCE FROM NEC2++/openEMS (simulation/nec2pp.py,
simulation/openems.py): HFSS is commercial, licensed software (Ansys HFSS,
driven here via the PyAEDT Python package). This is NOT a "the binary
happens to be missing on this machine" situation -- HFSS fundamentally
cannot run without a paid license and a licensed workstation. Per
README.md's "Licensing" section ("PyAEDT: MIT; requires a legally licensed
AEDT installation") and docs/BUILD_PLAN.md's Phase 8 text ("On a controlled
licensed workstation"), execution here is confined to a configured,
explicitly-designated licensed workstation with NO path that dispatches an
HFSS run to arbitrary infrastructure -- see check_hfss_workstation_
confinement() below, which HfssSimulator.run() calls before doing anything
else.

SOURCES CONSULTED (primary; all fetched directly from the upstream
ansys/pyaedt GitHub repository's `main` branch during implementation, via
GitHub's code-search API and raw.githubusercontent.com -- see the
per-fact citations below. Accessed 2026-09-02):
  - Distribution vs. import name: the PyPI project is named "pyaedt"
    (`pyproject.toml`'s `[project] name = "pyaedt"`, ansys/pyaedt repo
    root), but the importable package is the `ansys.aedt.core` namespace
    (confirmed via every file path below, all under
    `src/ansys/aedt/core/...`, and via aedt.docs.pyansys.com's own quick-
    start example: `from ansys.aedt.core import Hfss`). This module
    therefore guards `import ansys.aedt.core`, not `import pyaedt`.
  - `Hfss.__init__` full parameter signature (project, design,
    solution_type, setup, version, non_graphical, new_desktop,
    close_on_exit, student_version, machine, port, aedt_process_id,
    remove_lock): `src/ansys/aedt/core/hfss.py`, the `Hfss` class
    definition (`class Hfss(FieldAnalysis3D, ScatteringMethods,
    CreateBoundaryMixin, PyAedtBase)`).
  - `Modeler3D.create_box(origin, sizes, name=None, material=None,
    **kwargs)`: `src/ansys/aedt/core/modeler/cad/primitives_3d.py`.
    aedt.docs.pyansys.com's own quick-start example shows this called with
    plain numeric origin values (`hfss.modeler.create_box([0, 0, 0], [10,
    "dim", 10], "mybox", "aluminum")`) -- i.e. bare numbers are accepted
    and interpreted in the design's current default length unit, which is
    why this module converts its own meter-denominated geometry to plain
    millimeter floats before calling it (see _m_to_mm below) rather than
    inventing an unverified unit-suffixed-string convention.
  - `Analysis3D.assign_material(assignment, material) -> bool`:
    `src/ansys/aedt/core/application/analysis_3d.py`.
  - `Hfss.lumped_port(self, assignment: str | int | list, reference:
    Object3d | int | list | None = None, ...)`: `src/ansys/aedt/core/
    hfss.py`. The full parameter list beyond `assignment`/`reference` was
    not independently re-verified byte-exact (GitHub's code-search API
    returns a bounded text fragment, and this file could not be fetched in
    full); `impedance` and a port-name parameter are inferred from this
    same file's sibling `_create_circuit_port(out, impedance, name,
    renormalize, deembed, renorm_impedance=...)` and `_create_lumped_
    driven(self, assignment, int_line_start, int_line_stop, impedance,
    port_name, renorm, deemb)` methods (same file), which establish that
    `impedance` and a port name are real, present concepts flowing through
    this file's port-creation methods -- treat the exact `lumped_port`
    kwarg spelling as reasoned-but-not-byte-verified.
  - `Mesh.assign_length_mesh(self, assignment: list | str,
    inside_selection: bool = True, maximum_length: int = 1,
    maximum_elements: int = 1000, name: str = None) -> "MeshOperation"`:
    `src/ansys/aedt/core/modules/mesh.py`, full signature and docstring
    fetched directly.
  - `Hfss.create_setup(self, name: str = "MySetupAuto", setup_type: str |
    None = None, **kwargs) -> "SetupHFSS | SetupHFSSAuto"`:
    `src/ansys/aedt/core/hfss.py`, full signature fetched directly. The
    exact `**kwargs` property-key spelling used for the driven-modal
    solution frequency (`Frequency="<f>GHz"`, passed by this module) is
    the standard AEDT setup-property convention documented informally
    across PyAEDT's own examples, not independently re-verified against
    this method's body (kwargs pass through to AEDT's native property
    API, which this fetch did not reach).
  - `Hfss.create_linear_count_sweep(self, setup: str, unit: str,
    start_frequency: float, stop_frequency: float, num_of_freq_points:
    int | None = None, name: str | None = None, save_fields: bool = True,
    save_rad_fields: bool = False, sweep_type: str = "Discrete",
    interpolation_tol: float = 0.5, interpolation_max_solutions: int =
    250) -> "SweepHFSS | bool"`: `src/ansys/aedt/core/hfss.py`, full
    signature fetched directly.
  - `Analysis.analyze(self, setup: str = None, cores: int = None, ...)`:
    `src/ansys/aedt/core/application/analysis.py` (the base class HFSS's
    setup-analysis inherits), confirmed present; full kwarg list beyond
    `setup`/`cores` not re-verified.
  - `PostProcessorCommon.get_solution_data(...)`: `src/ansys/aedt/core/
    visualization/post/common.py`, confirmed present (accessed via
    `hfss.post.get_solution_data(...)`).
  - `SolutionData.primary_sweep_values` (property, returns an np.array of
    "the primary sweep valid points for the expression") and
    `SolutionData.full_matrix_mag_phase` (property, returns `(Mag Dict,
    Phase Dict)`, "phase in radians"): `src/ansys/aedt/core/
    visualization/post/solution_data.py`, both fetched and quoted
    verbatim including docstrings. No `data_db20`/`data_phase`/`data_real`
    method-style accessors exist on this class (confirmed absent by the
    same fetch) -- this module therefore reads S-parameters via the two
    confirmed properties above, not via a guessed method name. This
    module does NOT independently verify what unit `primary_sweep_values`
    reports in (Hz vs. the sweep's configured unit); rather than guess, it
    stores the raw values under a `frequency_ghz` key with an explicit
    note (see _extract_hfss_results), since the sweep itself was created
    with `unit="GHz"`.
  - `AnalysisHF.export_touchstone(self, setup: str | None = None, sweep:
    str | None = None, output_file: str | None = None, variations: list |
    None = None, variations_value: list | None = None, renormalization:
    bool = False, impedance: float | None = None,
    gamma_impedance_comments: bool = False) -> str | bool`:
    `src/ansys/aedt/core/application/analysis_hf.py`, full signature and
    docstring opening fetched directly.
  - `Design.save_project(self, file_name: str | Path = None, overwrite:
    bool = True, refresh_ids: bool = False) -> bool` and `Design.
    release_desktop(self, close_projects: bool = True, close_desktop:
    bool = True) -> bool`: `src/ansys/aedt/core/application/design.py`,
    both confirmed present (the base class HFSS inherits both from).
  - `ANSYSEM_ROOT<version>` as the environment-variable marker AEDT's own
    installer sets (used as one of this module's workstation-confinement
    signals, per this ticket's own design guidance): confirmed across
    multiple files, most directly `src/ansys/aedt/core/internal/
    aedt_versions.py` ("Return a list of installed AEDT versions on
    ``ANSYSEM_ROOT``" / `aedt_env_var_prefix = "ANSYSEM_ROOT"`) and
    `src/ansys/aedt/core/generic/general_methods.py` (`os.getenv(
    f"ANSYSEM_ROOT{...}")`), plus this repo's own `.env.example`
    (`AEDT_VERSION=`) and README.md's Licensing section.

HONEST CAVEAT -- read before trusting any of this end to end: pyaedt is
NOT installed in this environment (confirmed via `import pyaedt` /
`import ansys.aedt.core` failing at implementation time) and no licensed
AEDT installation is present. Unlike NEC2++/openEMS (ticket #38/#39, where
"the binary just happens to be missing" is the only gap), this is
categorically different: HFSS/PyAEDT genuinely cannot run here even in
principle -- no license, and the workstation-confinement gate below is
*designed* to reject this sandboxed container. NONE of the PyAEDT call
shapes below have been exercised against a real HFSS/AEDT installation;
they are built to the letter of the primary-source method signatures cited
above (each fact graded by citation confidence, same discipline as
nec2pp.py/openems.py), and exercised in tests only against a hand-written
fake object matching the subset of the pyaedt API this module actually
calls (see tests/test_hfss.py). Treat any result from a real run as
unverified until this has actually been run against a real HFSS/AEDT
installation on a genuine licensed workstation at least once.
"""

import importlib
import json
import os
import shutil
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .base import SimulationResult, Simulator, SimulatorError

# ---------------------------------------------------------------------------
# Workstation confinement gate.
#
# This is the most important part of this ticket (per its own design
# guidance): it must be structurally impossible for HfssSimulator.run() to
# silently "succeed" on a random machine/container by flipping one boolean.
# Four independent signals are required, ALL of them, before anything else
# in run() executes:
#   1. HFSS_ENABLED == "true" (the pre-existing .env.example flag).
#   2. HFSS_WORKSTATION_ID (this host's own declared identity) is set AND
#      equals HFSS_ALLOWED_WORKSTATION_ID (the operator's configured
#      allow-listed value) -- i.e. an explicit, host-specific allow-list
#      match, not just "some string is present".
#   3. pyaedt (ansys.aedt.core) is actually importable on this host.
#   4. At least one ANSYSEM_ROOT* environment variable is present -- the
#      marker AEDT's own installer sets (see module docstring citation),
#      i.e. independent evidence of a real AEDT install, not just a Python
#      package.
#
# Signals 3 and 4 in particular are not things a careless "just flip
# HFSS_ENABLED=true to test something" operator would accidentally satisfy;
# they require a genuine PyAEDT install and a genuine AEDT install
# respectively. This sandboxed container satisfies none of the four -- see
# tests/test_hfss.py's test_check_hfss_workstation_confinement_rejects_this_
# sandbox for the real, unmockable proof.
# ---------------------------------------------------------------------------


def _real_pyaedt_importable() -> tuple[bool, str]:
    """Actually attempt `import ansys.aedt.core` (pyaedt's real import
    namespace -- see module docstring citation). Returns (importable,
    detail) rather than raising, so the confinement check below can report
    it alongside every other missing signal in one message."""
    try:
        importlib.import_module("ansys.aedt.core")
    except ImportError as exc:
        return False, str(exc)
    return True, ""


def check_hfss_workstation_confinement(
    env: dict[str, str] | None = None,
    pyaedt_importable: bool | None = None,
) -> None:
    """Raise SimulatorError naming exactly what's missing unless this host
    presents all four workstation-confinement signals documented above.
    Called by HfssSimulator.run() before it does anything else.

    `env` defaults to the real process environment (os.environ); pass an
    explicit dict to test individual signal combinations without touching
    the real environment. `pyaedt_importable` defaults to None, meaning
    "actually attempt the import" (_real_pyaedt_importable above); pass
    True/False to test the gate's logic in isolation from whether pyaedt
    happens to be installed in the current interpreter -- this parameter
    exists ONLY for that kind of isolated unit test. The property this
    ticket cares about most -- that this gate rejects a real, unmodified
    call in this actual sandboxed environment -- is proven by calling this
    function with NO arguments at all; see tests/test_hfss.py.
    """
    env = os.environ if env is None else env
    missing: list[str] = []

    enabled = str(env.get("HFSS_ENABLED", "")).strip().lower()
    if enabled != "true":
        missing.append(f"HFSS_ENABLED must be 'true' (got {env.get('HFSS_ENABLED', '<unset>')!r})")

    workstation_id = str(env.get("HFSS_WORKSTATION_ID", "")).strip()
    allowed_id = str(env.get("HFSS_ALLOWED_WORKSTATION_ID", "")).strip()
    if not workstation_id:
        missing.append("HFSS_WORKSTATION_ID is not set on this host")
    elif not allowed_id:
        missing.append(
            "HFSS_ALLOWED_WORKSTATION_ID is not configured -- there is no "
            "allowed workstation id to check HFSS_WORKSTATION_ID against"
        )
    elif workstation_id != allowed_id:
        missing.append(
            f"HFSS_WORKSTATION_ID ({workstation_id!r}) does not match the "
            f"configured HFSS_ALLOWED_WORKSTATION_ID ({allowed_id!r})"
        )

    if pyaedt_importable is None:
        importable, detail = _real_pyaedt_importable()
    else:
        importable, detail = pyaedt_importable, ""
    if not importable:
        missing.append(
            "pyaedt is not importable on this host (import ansys.aedt.core "
            "failed" + (f": {detail}" if detail else "") + ")"
        )

    ansysem_markers = sorted(k for k in env if k.startswith("ANSYSEM_ROOT"))
    if not ansysem_markers:
        missing.append(
            "no ANSYSEM_ROOT* environment variable is set -- this is the "
            "marker AEDT's own installer sets (see module docstring "
            "citation), and its absence means no real AEDT installation "
            "was detected on this host"
        )

    if missing:
        raise SimulatorError(
            "HFSS execution refused: this host is not confirmed as the "
            "designated, licensed HFSS workstation. HFSS is commercial, "
            "licensed software (Ansys HFSS via PyAEDT) that fundamentally "
            "cannot run without a paid license and a licensed workstation "
            "-- unlike NEC2++/openEMS, this is not a 'binary happens to be "
            "missing' situation, so this gate requires multiple "
            "independent, hard-to-fake-by-accident signals of a real, "
            "intentional, licensed setup rather than one flag. "
            "Missing/failed checks:\n" + "\n".join(f"  - {m}" for m in missing)
        )


def _import_pyaedt_hfss_class() -> Any:
    """Guarded import of pyaedt's Hfss class -- deferred to inside this
    function (rather than a top-of-module `import`) precisely because
    pyaedt genuinely will not be installed in most environments, including
    this one (see module docstring). Only ever called from
    HfssSimulator._real_hfss_factory, itself only reached after
    check_hfss_workstation_confinement has already passed."""
    try:
        from ansys.aedt.core import Hfss  # see module docstring citation
    except ImportError as exc:
        raise SimulatorError(
            "pyaedt is not installed. On the licensed HFSS workstation, "
            "install the optional 'hfss' dependency group, e.g. "
            "`uv sync --extra hfss` or `pip install '.[hfss]'`."
        ) from exc
    return Hfss


# ---------------------------------------------------------------------------
# Geometry/materials/ports/mesh application, solve, report extraction, and
# archival -- each written to take an already-constructed `hfss` object
# (real pyaedt.Hfss instance, or a hand-written fake matching the subset of
# its API used here) rather than constructing one itself. This is the seam
# the ticket's testing guidance calls for: "tested against the
# Simulator.run() seam with PyAEDT/HFSS invocation substituted by a fake for
# CI" -- these functions ARE that invocation, substitutable independently of
# the workstation-confinement gate (see HfssSimulator below for how the two
# compose).
# ---------------------------------------------------------------------------


def _m_to_mm(value_m: float) -> float:
    """Convert a meter-denominated geometry coordinate to a plain
    millimeter float -- see module docstring citation on why this module
    uses bare numeric values (matching pyaedt's own quick-start example)
    rather than unit-suffixed strings, and why millimeters (AEDT's
    overwhelmingly common default modeler length unit) rather than meters."""
    return float(value_m) * 1000.0


def _create_box(hfss: Any, prim: dict[str, Any], name: str) -> str:
    """Create one axis-aligned box primitive on `hfss.modeler` from a
    {"p1_m": [x,y,z], "p2_m": [x,y,z]} corner-pair, per
    Modeler3D.create_box(origin, sizes, name=...) -- see module docstring
    citation."""
    p1 = prim["p1_m"]
    p2 = prim["p2_m"]
    origin = [_m_to_mm(p1[i]) for i in range(3)]
    sizes = [_m_to_mm(p2[i]) - _m_to_mm(p1[i]) for i in range(3)]
    hfss.modeler.create_box(origin, sizes, name=name)
    return name


def _apply_hfss_geometry(hfss: Any, geometry: dict[str, Any]) -> tuple[list[str], str]:
    """Create material/conductor box primitives, assign materials, create
    the lumped port, and apply a length-based mesh operation on `hfss`.

    `geometry` shape:
        {
          "materials": [                 # dielectric/lossy layers, optional
              {"name": str (optional), "p1_m": [x,y,z], "p2_m": [x,y,z],
               "material": str (AEDT material-library name, default
               "vacuum")}, ...
          ],
          "conductors": [                # PEC-ish layers (patch, ground)
              {"name": str (optional), "p1_m", "p2_m",
               "material": str (default "copper")}, ...
          ],
          "port": {                      # required
              "name": str (default "port1"),
              "sheet": {"p1_m": [x,y,z], "p2_m": [x,y,z]},   # thin box
                  modeling the lumped-port excitation sheet
              "reference": str | list[str] | None (default: the last
                  conductor created, typically the ground plane),
              "impedance_ohms": float (default 50.0),
          },
          "mesh": {                      # optional
              "assignment": list[str] (default: the created conductor
                  names, or the port sheet if there are none),
              "max_length_mm": float (default 1.0),
          },
        }

    Geometry is in meters (this codebase's established convention, matching
    generate_nec2_deck/generate_openems_xml); box-only primitives in this
    pass -- cylinder support would follow the same create-then-assign_
    material pattern once Modeler3D.create_cylinder's exact signature is
    verified against primary source (not done here, out of scope -- see
    module docstring's citation-confidence discipline).

    Returns (conductor_names, port_name).
    """
    conductor_names: list[str] = []

    for idx, mat in enumerate(geometry.get("materials", [])):
        required = ("p1_m", "p2_m")
        missing = [f for f in required if f not in mat]
        if missing:
            raise ValueError(f"material {idx} missing required field(s): {missing}")
        name = mat.get("name", f"material_{idx + 1}")
        _create_box(hfss, mat, name)
        hfss.assign_material(name, mat.get("material", "vacuum"))

    for idx, cond in enumerate(geometry.get("conductors", [])):
        required = ("p1_m", "p2_m")
        missing = [f for f in required if f not in cond]
        if missing:
            raise ValueError(f"conductor {idx} missing required field(s): {missing}")
        name = cond.get("name", f"conductor_{idx + 1}")
        _create_box(hfss, cond, name)
        hfss.assign_material(name, cond.get("material", "copper"))
        conductor_names.append(name)

    port = geometry.get("port")
    if not port:
        raise ValueError("geometry['port'] is required")
    sheet = port.get("sheet")
    if not sheet or "p1_m" not in sheet or "p2_m" not in sheet:
        raise ValueError("geometry['port']['sheet'] must supply p1_m/p2_m")
    port_name = port.get("name", "port1")
    sheet_name = f"{port_name}_sheet"
    _create_box(hfss, sheet, sheet_name)
    reference = port.get("reference") or (conductor_names[-1] if conductor_names else None)
    impedance_ohms = port.get("impedance_ohms", 50.0)
    hfss.lumped_port(
        assignment=sheet_name,
        reference=reference,
        impedance=impedance_ohms,
        name=port_name,
    )

    mesh = geometry.get("mesh", {})
    mesh_targets = mesh.get("assignment") or conductor_names or [sheet_name]
    max_length_mm = mesh.get("max_length_mm", 1.0)
    hfss.mesh.assign_length_mesh(
        assignment=mesh_targets,
        maximum_length=max_length_mm,
        name="length_mesh",
    )

    return conductor_names, port_name


def _create_setup_and_solve(
    hfss: Any,
    frequency_hz: float,
    sweep: dict[str, Any] | None,
    setup_name: str,
    sweep_name: str,
) -> None:
    """Create a driven-modal solve setup at frequency_hz, a linear-count
    frequency sweep around it, and run the solve -- via
    Hfss.create_setup/create_linear_count_sweep/Analysis.analyze (see
    module docstring citations)."""
    freq_ghz = frequency_hz / 1e9
    hfss.create_setup(name=setup_name, setup_type="HFSSDriven", Frequency=f"{freq_ghz:.6g}GHz")

    sweep = sweep or {}
    start_hz = sweep.get("start_hz", frequency_hz * 0.9)
    stop_hz = sweep.get("stop_hz", frequency_hz * 1.1)
    points = int(sweep.get("points", 51))
    hfss.create_linear_count_sweep(
        setup=setup_name,
        unit="GHz",
        start_frequency=start_hz / 1e9,
        stop_frequency=stop_hz / 1e9,
        num_of_freq_points=points,
        name=sweep_name,
        save_fields=False,
    )

    hfss.analyze(setup=setup_name)


def _extract_hfss_results(
    hfss: Any, setup_name: str, sweep_name: str, touchstone_path: Path
) -> dict[str, Any]:
    """Extract S11 vs. frequency via Hfss.post.get_solution_data(...) and
    export a Touchstone file via Hfss.export_touchstone(...) -- both real,
    verified pyaedt methods (see module docstring citations).

    S-parameter values are read from SolutionData.primary_sweep_values and
    SolutionData.full_matrix_mag_phase (both fetched/quoted verbatim from
    primary source -- see module docstring), NOT from a guessed
    data_db20()/data_phase()-style accessor method (confirmed absent from
    this class). This module does not independently verify what unit
    primary_sweep_values reports in, so the raw values are returned under
    an explicitly-named "frequency_ghz" key (the sweep itself was created
    with unit="GHz") rather than silently assumed-converted to Hz.
    """
    solution_data = hfss.post.get_solution_data(
        expressions=["S(1,1)"],
        setup_sweep_name=f"{setup_name} : {sweep_name}",
    )
    frequency_ghz = list(solution_data.primary_sweep_values)
    mag_by_expr, phase_by_expr = solution_data.full_matrix_mag_phase
    magnitude_linear = list(mag_by_expr.get("S(1,1)", []))
    phase_rad = list(phase_by_expr.get("S(1,1)", []))

    s_parameters = {
        "computed": True,
        "expression": "S(1,1)",
        "frequency_ghz": frequency_ghz,
        "magnitude_linear": magnitude_linear,
        "phase_rad": phase_rad,
        "note": (
            "frequency_ghz is SolutionData.primary_sweep_values from a "
            "sweep created with unit='GHz'; magnitude_linear/phase_rad are "
            "SolutionData.full_matrix_mag_phase for S(1,1), phase in "
            "radians -- see simulation/hfss.py's module docstring for the "
            "primary-source citation."
        ),
    }

    export_result = hfss.export_touchstone(
        setup=setup_name, sweep=sweep_name, output_file=str(touchstone_path)
    )

    return {
        "s_parameters": s_parameters,
        "touchstone_file": str(touchstone_path),
        "touchstone_export_result": export_result,
    }


def _archive_hfss_run(
    hfss: Any,
    archive_dir: Path,
    project_name: str,
    project_path: Path,
    report: dict[str, Any],
) -> Path:
    """Save the solved project (Design.save_project(), see module
    docstring citation) and archive the project file plus the extracted
    report (S-parameters, Touchstone file path) as JSON under archive_dir,
    for later reproducibility/audit -- this ticket's archival acceptance
    criterion. Returns the per-run archive directory."""
    timestamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    run_dir = archive_dir / f"{project_name}_{timestamp}"
    run_dir.mkdir(parents=True, exist_ok=True)

    hfss.save_project()
    if project_path.exists():
        shutil.copy2(project_path, run_dir / project_path.name)

    (run_dir / "report.json").write_text(json.dumps(report, indent=2, default=str))
    return run_dir


# ---------------------------------------------------------------------------
# HfssSimulator: the Simulator contract (simulation/base.py, unchanged) --
# creates a project, applies geometry/materials/ports/mesh, solves, extracts
# reports, exports Touchstone, and archives the run, ALL gated behind
# check_hfss_workstation_confinement().
# ---------------------------------------------------------------------------


class HfssSimulator(Simulator):
    name = "HFSS"

    def __init__(
        self,
        hfss_factory: Callable[..., Any] | None = None,
        confinement_check: Callable[..., None] | None = None,
        archive_dir: str | None = None,
    ):
        """`hfss_factory` and `confinement_check` are constructor-injection
        seams for tests ONLY (mirroring Nec2ppSimulator(executable=...)/
        OpenemsSimulator(executable=...)'s own injection pattern) -- the
        real convenience function run_hfss_simulation() below and the
        agent/MCP tool wiring never pass them, so a real call always goes
        through the real confinement gate and a real pyaedt.Hfss instance.
        `hfss_factory`, if given, is called with the same keyword arguments
        pyaedt.Hfss(...) accepts (project, design, solution_type, version,
        non_graphical, new_desktop) and must return an object implementing
        the subset of pyaedt's Hfss API this module calls (see
        tests/test_hfss.py's fake for the exact shape). `confinement_check`
        defaults to the real check_hfss_workstation_confinement."""
        self._hfss_factory = hfss_factory
        self._confinement_check = confinement_check or check_hfss_workstation_confinement
        self.archive_dir = Path(archive_dir or os.getenv("HFSS_ARCHIVE_DIR") or "hfss_archive")

    def _real_hfss_factory(self, **kwargs: Any) -> Any:
        Hfss = _import_pyaedt_hfss_class()
        return Hfss(**kwargs)

    def run(self, job: dict) -> SimulationResult:
        # Workstation confinement -- checked BEFORE anything else, per this
        # ticket's design guidance. See check_hfss_workstation_confinement's
        # own docstring for exactly what it requires and why.
        self._confinement_check()

        geometry = job.get("geometry")
        if not geometry:
            raise SimulatorError("job['geometry'] is required")
        frequency_hz = job.get("frequency_hz")
        if not frequency_hz:
            raise SimulatorError("job['frequency_hz'] is required")

        project_name = job.get("project_name", "hfss_project")
        design_name = job.get("design_name", "hfss_design")
        setup_name = job.get("setup_name", "Setup1")
        sweep_name = job.get("sweep_name", "Sweep1")

        self.archive_dir.mkdir(parents=True, exist_ok=True)
        project_path = Path(
            job.get("project_path", self.archive_dir / f"{project_name}.aedt")
        ).resolve()

        hfss_factory = self._hfss_factory or self._real_hfss_factory
        hfss = hfss_factory(
            project=str(project_path),
            design=design_name,
            solution_type="Modal",
            version=job.get("aedt_version") or os.getenv("AEDT_VERSION") or None,
            non_graphical=job.get("non_graphical", True),
            new_desktop=job.get("new_desktop", True),
        )

        try:
            conductor_names, port_name = _apply_hfss_geometry(hfss, geometry)
            _create_setup_and_solve(hfss, frequency_hz, job.get("sweep"), setup_name, sweep_name)
            touchstone_path = self.archive_dir / f"{project_name}.s1p"
            extracted = _extract_hfss_results(hfss, setup_name, sweep_name, touchstone_path)
            run_dir = _archive_hfss_run(
                hfss,
                self.archive_dir,
                project_name,
                project_path,
                {
                    "provenance": "SIMULATED",
                    "simulator": self.name,
                    "project_path": str(project_path),
                    **extracted,
                },
            )
        finally:
            release = getattr(hfss, "release_desktop", None)
            if callable(release):
                release()

        return SimulationResult(
            simulator=self.name,
            status="COMPLETED",
            workdir=run_dir,
            outputs={
                "project_path": str(project_path),
                "touchstone_file": extracted["touchstone_file"],
                "s_parameters": extracted["s_parameters"],
                "conductor_names": conductor_names,
                "port_name": port_name,
                "archive_dir": str(run_dir),
            },
        )


def run_hfss_simulation(
    geometry: dict[str, Any],
    frequency_hz: float,
    sweep: dict[str, Any] | None = None,
    project_name: str = "hfss_project",
    design_name: str = "hfss_design",
    archive_dir: str | None = None,
    hfss_factory: Callable[..., Any] | None = None,
    confinement_check: Callable[..., None] | None = None,
) -> dict[str, Any]:
    """Create/solve/archive an HFSS project from structured geometry via
    HfssSimulator, and return a SIMULATED-provenance result structured the
    same way as run_nec2_simulation/run_openems_simulation.

    `hfss_factory`/`confinement_check` are the same test-only injection
    seams documented on HfssSimulator.__init__ -- omit both for a real call
    (the agent/MCP tool wiring always omits them, so a real invocation
    always goes through the real workstation-confinement gate).

    See this module's header comment for the full pyaedt API citation list
    and the honest caveat: NONE of this has been run against a real
    HFSS/AEDT installation -- pyaedt genuinely cannot run in this
    environment even in principle (no license, and the confinement gate is
    designed to reject this sandboxed container).
    """
    simulator = HfssSimulator(
        hfss_factory=hfss_factory,
        confinement_check=confinement_check,
        archive_dir=archive_dir,
    )
    result = simulator.run(
        {
            "geometry": geometry,
            "frequency_hz": frequency_hz,
            "sweep": sweep,
            "project_name": project_name,
            "design_name": design_name,
        }
    )
    return {
        "provenance": "SIMULATED",
        "simulator": result.simulator,
        "status": result.status,
        "workdir": str(result.workdir),
        **result.outputs,
    }
