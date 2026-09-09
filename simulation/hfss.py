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

  Periodic/Floquet-port unit-cell characterization (issue #273 -- see
  _apply_floquet_boundaries_and_port and _extract_hfss_floquet_results
  below), fetched directly from `src/ansys/aedt/core/hfss.py` on
  ansys/pyaedt's `main` branch via the same raw.githubusercontent.com/
  GitHub-code-search-API route as above (accessed 2026-09-09):
  - `Hfss.auto_assign_lattice_pairs(self, assignment: str | Object3d,
    coordinate_system: str | None = "Global", coordinate_plane: str | None
    = "XY") -> list[str]`: full signature, docstring, and body fetched
    directly. Auto-detects and assigns the periodic ("lattice pair")
    boundary on a whole object's side faces in one call -- chosen over the
    two other real candidates this module evaluated for the ticket's
    "master/slave" boundary (both also fetched and byte-verified from the
    same file): `Hfss.assign_lattice_pair(assignment: list, reverse_v=False,
    phase_delay="UseScanAngle", phase_delay_param1="0deg",
    phase_delay_param2="0deg", name=None)`, which needs a list of exactly
    two already-known FacePrimitive objects, and the older explicit pair
    `Hfss.assign_primary(assignment, u_start, u_end, reverse_v=False,
    coordinate_system="Global", name=None)` /
    `Hfss.assign_secondary(assignment, primary, u_start, u_end, ...)`,
    HFSS's original "master"/"slave" boundary UI terminology (no
    `assign_master`/`assign_slave` method exists in current pyaedt --
    confirmed absent by the same fetch). All three need a face reference
    into the created box, but this module's own `_create_box` (see below)
    already discards the `Object3d` `Modeler3D.create_box` returns and
    keeps only its name string, and ansys/pyaedt's own test suite
    (`tests/system/general/test_hfss.py`) hedges box-face-index numbering
    with an `if DESKTOP_VERSION > "2022.2"` branch -- i.e. even PyAEDT's
    own maintainers do not treat a box's face-index ordering as stable
    across AEDT versions. `auto_assign_lattice_pairs` needs no face index
    at all (just the object itself), so this module uses it instead of
    guessing an index this module has no way to verify against a real
    install.
  - `Hfss.create_floquet_port(self, assignment: str | list, lattice_origin:
    list | None = None, lattice_a_end: list | None = None, lattice_b_end:
    list | None = None, modes: int = 2, name: str | None = None,
    renormalize: bool = True, deembed_distance: int | float | str = 0,
    reporter_filter: bool | list = True, lattice_cs: str = "Global") ->
    BoundaryObject`: full signature, docstring, and body fetched directly.
    `assignment` accepts a sheet/object name string (not just a face id) --
    confirmed from the body's own
    `if isinstance(face_id[0], int): props["Faces"] = ... else:
    props["Objects"] = ...` branch -- so this module passes the same kind
    of thin-box "sheet" name it already uses for the lumped port (see
    `_apply_hfss_geometry`'s `port["sheet"]`), not a face id.
    `lattice_origin`/`lattice_a_end`/`lattice_b_end` default to `None`, in
    which case the real method defers to
    `Modeler3D._find_perpendicular_points` -- an internal, underscore-
    prefixed method this module has NOT fetched or verified. Rather than
    depend on that unverified internal auto-detection for a value that
    directly sets the unit cell's own periodicity, this module computes and
    passes all three explicitly from the same `period_x_m`/`period_y_m`
    the caller already supplied (see _apply_floquet_boundaries_and_port).
    `deembed_distance` is documented as "in millimeters" and its exact
    unit-suffixing (`self.value_with_units(deembed_distance)`, not
    independently fetched) is assumed to follow the same "bare number ==
    the design's default length unit (mm)" convention as `create_box`
    (see `_m_to_mm`'s own citation above) -- this module therefore passes
    a bare mm float here too, not an unverified unit-suffixed string.
  - Floquet-port S-parameter naming, `S(<port_name>:<mode_number>,
    <port_name>:<mode_number>)` (1-indexed mode number): confirmed
    byte-verbatim from `Hfss.create_fresnel_variables`'s real body
    (`_create_var("r_te", f"S({floquet_ports[0]}:1,{floquet_ports[0]}:1)")`
    for mode 1, `f"S({floquet_ports[0]}:2,{floquet_ports[0]}:2)"` for mode
    2) and from `Hfss.get_fresnel_floquet_ports`'s real body, which parses
    `self.excitation_names` entries by splitting on ":" into
    `(port_name, mode)` -- i.e. a multi-mode port's own excitation names
    are genuinely `"<PortName>:<ModeNumber>"` strings, not a guess. This
    module reads the raw per-mode self-reflection S-parameter this way
    (see _extract_hfss_floquet_results) but deliberately does NOT replicate
    `create_fresnel_variables`'s own extra "-" sign flip on the mode-2 (TM)
    term (`f"-S(...:2,...:2)")` -- that sign is specific to pyaedt's own
    SBR+ `.rttbl` Fresnel-table convention (`get_fresnel_coefficients`),
    not a generic S-parameter reading.

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
from dataclasses import dataclass
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


@dataclass
class _AppliedGeometry:
    """What `_apply_hfss_geometry` built, and how to solve/extract it --
    replaces the old `(conductor_names, port_name)` tuple return so a
    periodic/Floquet job can additionally report `port_type` and its mode
    count without `HfssSimulator.run()` guessing which extraction function
    to call. `port_type` is `"lumped"` (the original, unchanged path) or
    `"floquet"` (issue #273); `floquet_modes` is meaningless for `"lumped"`
    (left at its default of 1, matching a lumped port's single quantity)."""

    conductor_names: list[str]
    port_name: str
    port_type: str = "lumped"
    floquet_modes: int = 1


def _apply_floquet_boundaries_and_port(hfss: Any, periodic: dict[str, Any]) -> tuple[str, int, str]:
    """Build the periodic unit-cell's bounding/background box, auto-assign
    its side-wall periodic ("lattice pair") boundaries, and create a
    Floquet port on a thin sheet at the top of the cell -- the periodic
    counterpart of the single lumped port `_apply_hfss_geometry` builds
    from `geometry["port"]`.

    `periodic` shape (`geometry["periodic"]`, mutually exclusive with
    `geometry["port"]` -- see `_apply_hfss_geometry`). Its key vocabulary
    (`period_x_m`/`period_y_m` plus explicit `z_min_m`/`z_max_m`/
    `origin_m`) deliberately does not reuse simulation/palace.py's
    analogous `geometry["unit_cell"] = {"lx_m", "ly_m", "lz_m"}` shape:
    Palace's box has an implicit origin, so three side lengths fully
    describe it, while HFSS's box here is built from absolute `p1_m`/
    `p2_m` corners (see `_create_box`) and needs an explicit z-range and
    xy origin to place it -- a genuinely richer shape, not just a
    differently-spelled copy of Palace's:
        {
          "period_x_m": float,      # required -- unit-cell period along x
          "period_y_m": float,      # required -- unit-cell period along y
          "origin_m": [x, y] (default [0.0, 0.0]) -- xy origin (lower-left
              corner) of the cell's footprint,
          "z_min_m": float (default 0.0),
          "z_max_m": float,         # required -- top of the bounding box;
              the Floquet port sheet sits here,
          "name": str (default "unit_cell") -- name of the bounding
              background box `auto_assign_lattice_pairs` is called on,
          "material": str (default "vacuum") -- the bounding box's material,
          "floquet": {                            # optional
              "name": str (default "floquet1"),
              "modes": int (default 2) -- TE + TM fundamental Floquet
                  modes at normal incidence, matching
                  Hfss.create_floquet_port's own `modes=2` default,
              "deembed_distance_m": float (default 0.0),
              "renormalize": bool (default True),
          },
        }

    SCOPE: exactly one Floquet port, on the cell's top face (z_max_m) --
    matching this ticket's own framing ("a Floquet port on its top face",
    singular). This characterizes a REFLECTION-ONLY unit cell (the
    dominant case this repo cares about -- CLAUDE.md's 0-vs-180-degree
    reflection-phase framing). A caller wanting a ground-backed cell gets
    that for free by putting a full-footprint conductor box in
    `geometry["conductors"]` at z_min_m (same mechanism the lumped-port
    path already uses for a ground plane) -- no separate "ground_backed"
    flag exists here, unlike simulation/palace.py's, because HFSS's own
    per-object-face boundary model doesn't need one: not creating a second
    Floquet port is enough. If NEITHER a full-footprint conductor NOR a
    second port is supplied, the cell's bottom face is left with no
    boundary this module assigns explicitly -- what HFSS does with that
    face by default is NOT verified here (see module docstring's HONEST
    CAVEAT); a two-port transmissive Floquet setup (a second port at
    z_min_m, for an all-dielectric/non-ground-backed structure -- the
    shape simulation/palace.py's own `ground_backed=False` already
    supports) is out of scope for this pass.

    This module still does not do CSG boolean union/subtraction (see
    `_apply_hfss_geometry`'s own docstring) -- the bounding box built here
    sits alongside, and generally overlapping, whatever `geometry
    ["materials"]`/`["conductors"]` boxes the caller also supplied, exactly
    as those already overlap each other in the lumped-port path today.

    See module docstring's citation block for the primary-source signatures
    of `Hfss.auto_assign_lattice_pairs`/`Hfss.create_floquet_port` this
    function calls, and why `auto_assign_lattice_pairs` (over
    `assign_lattice_pair`/`assign_primary`+`assign_secondary`) and explicit
    `lattice_origin`/`lattice_a_end`/`lattice_b_end` (over leaving them
    `None`) were chosen.

    Returns (floquet_port_name, modes, sheet_name) -- `sheet_name` is
    returned (rather than left for the caller to re-derive from
    `floquet_port_name`) so `_apply_hfss_geometry`'s mesh-assignment
    default can reuse the exact name this function actually created the
    sheet under, instead of both functions independently encoding the
    same `f"{port_name}_sheet"` naming convention.
    """
    required = ("period_x_m", "period_y_m", "z_max_m")
    missing = [f for f in required if f not in periodic]
    if missing:
        raise ValueError(f"geometry['periodic'] missing required field(s): {missing}")

    period_x_m = float(periodic["period_x_m"])
    period_y_m = float(periodic["period_y_m"])
    origin_xy_m = periodic.get("origin_m", [0.0, 0.0])
    if len(origin_xy_m) != 2:
        raise ValueError("geometry['periodic']['origin_m'] must have exactly 2 components")
    origin_x_m, origin_y_m = float(origin_xy_m[0]), float(origin_xy_m[1])
    z_min_m = float(periodic.get("z_min_m", 0.0))
    z_max_m = float(periodic["z_max_m"])
    x_max_m = origin_x_m + period_x_m
    y_max_m = origin_y_m + period_y_m

    cell_name = periodic.get("name", "unit_cell")
    _create_box(
        hfss,
        {
            "p1_m": [origin_x_m, origin_y_m, z_min_m],
            "p2_m": [x_max_m, y_max_m, z_max_m],
        },
        cell_name,
    )
    hfss.assign_material(cell_name, periodic.get("material", "vacuum"))
    hfss.auto_assign_lattice_pairs(cell_name, coordinate_plane="XY")

    floquet = periodic.get("floquet", {})
    port_name = floquet.get("name", "floquet1")
    modes = int(floquet.get("modes", 2))
    sheet_name = f"{port_name}_sheet"
    _create_box(
        hfss,
        {
            "p1_m": [origin_x_m, origin_y_m, z_max_m],
            "p2_m": [x_max_m, y_max_m, z_max_m],
        },
        sheet_name,
    )
    lattice_origin = [_m_to_mm(origin_x_m), _m_to_mm(origin_y_m), _m_to_mm(z_max_m)]
    lattice_a_end = [_m_to_mm(x_max_m), _m_to_mm(origin_y_m), _m_to_mm(z_max_m)]
    lattice_b_end = [_m_to_mm(origin_x_m), _m_to_mm(y_max_m), _m_to_mm(z_max_m)]
    hfss.create_floquet_port(
        assignment=sheet_name,
        lattice_origin=lattice_origin,
        lattice_a_end=lattice_a_end,
        lattice_b_end=lattice_b_end,
        modes=modes,
        name=port_name,
        renormalize=bool(floquet.get("renormalize", True)),
        deembed_distance=_m_to_mm(float(floquet.get("deembed_distance_m", 0.0))),
    )

    return port_name, modes, sheet_name


def _apply_hfss_geometry(hfss: Any, geometry: dict[str, Any]) -> _AppliedGeometry:
    """Create material/conductor box primitives, assign materials, create
    either the lumped port or (issue #273) a periodic Floquet-port unit
    cell, and apply a length-based mesh operation on `hfss`.

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
          "port": {                      # exactly one of "port"/"periodic"
                                          # is required
              "name": str (default "port1"),
              "sheet": {"p1_m": [x,y,z], "p2_m": [x,y,z]},   # thin box
                  modeling the lumped-port excitation sheet
              "reference": str | list[str] | None (default: the last
                  conductor created, typically the ground plane),
              "impedance_ohms": float (default 50.0),
          },
          "periodic": {                  # exactly one of "port"/"periodic"
                                          # is required -- see
                                          # _apply_floquet_boundaries_and_
                                          # port's own docstring for its
                                          # full shape (issue #273)
              "period_x_m": float, "period_y_m": float, "z_max_m": float,
              ...
          },
          "mesh": {                      # optional
              "assignment": list[str] (default: the created conductor
                  names, or the port/Floquet sheet if there are none),
              "max_length_mm": float (default 1.0),
          },
        }

    Geometry is in meters (this codebase's established convention, matching
    generate_nec2_deck/generate_openems_xml); box-only primitives in this
    pass -- cylinder support would follow the same create-then-assign_
    material pattern once Modeler3D.create_cylinder's exact signature is
    verified against primary source (not done here, out of scope -- see
    module docstring's citation-confidence discipline).

    Returns an _AppliedGeometry.
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
    periodic = geometry.get("periodic")
    if port and periodic:
        raise ValueError(
            "geometry['port'] and geometry['periodic'] are mutually exclusive "
            "-- a job builds either a single lumped-port box or a periodic "
            "Floquet-port unit cell, not both"
        )
    if not port and not periodic:
        raise ValueError("geometry['port'] or geometry['periodic'] is required")

    if periodic:
        port_name, floquet_modes, floquet_sheet_name = _apply_floquet_boundaries_and_port(
            hfss, periodic
        )
        port_type = "floquet"
        mesh_default_targets = conductor_names or [floquet_sheet_name]
    else:
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
        port_type = "lumped"
        floquet_modes = 1
        mesh_default_targets = conductor_names or [sheet_name]

    mesh = geometry.get("mesh", {})
    mesh_targets = mesh.get("assignment") or mesh_default_targets
    max_length_mm = mesh.get("max_length_mm", 1.0)
    hfss.mesh.assign_length_mesh(
        assignment=mesh_targets,
        maximum_length=max_length_mm,
        name="length_mesh",
    )

    return _AppliedGeometry(conductor_names, port_name, port_type, floquet_modes)


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


def _extract_hfss_floquet_results(
    hfss: Any,
    setup_name: str,
    sweep_name: str,
    touchstone_path: Path,
    floquet_port_name: str,
    modes: int,
) -> dict[str, Any]:
    """Extract each Floquet mode's self-reflection S-parameter vs.
    frequency via Hfss.post.get_solution_data(...), and export a Touchstone
    file via Hfss.export_touchstone(...) -- the periodic-unit-cell
    counterpart of _extract_hfss_results above, for a job built by
    _apply_floquet_boundaries_and_port (issue #273). Returns per-unit-cell
    reflection data keyed by mode, NOT a single S(1,1) against a lumped
    port.

    HFSS names a multi-mode port's terminals "<PortName>:<ModeNumber>"
    (1-indexed) and reads S-parameters between them as
    "S(<PortName>:<ModeNumber>,<PortName>:<ModeNumber>)" -- both confirmed
    byte-verbatim against Hfss.get_fresnel_floquet_ports's and
    Hfss.create_fresnel_variables's real bodies (see module docstring
    citation). This function reads that same expression for each mode
    (mode 1 = TE, mode 2 = TM at normal incidence, per
    Hfss.create_floquet_port's own `modes=2` default) but -- unlike
    create_fresnel_variables/get_fresnel_coefficients -- does NOT apply
    their extra "-" sign flip on the mode-2 (TM) term: that sign is
    specific to pyaedt's own SBR+ .rttbl Fresnel-table convention, not a
    generic S-parameter reading, and this function reads the raw
    self-reflection coefficient, not a Fresnel table.

    Like _extract_hfss_results, this does not independently verify what
    unit primary_sweep_values reports in, so raw values are returned under
    an explicit "frequency_ghz" key (the sweep was created with
    unit="GHz") rather than silently assumed-converted.
    """
    modes_by_index: dict[str, Any] = {}
    for mode in range(1, modes + 1):
        expression = f"S({floquet_port_name}:{mode},{floquet_port_name}:{mode})"
        solution_data = hfss.post.get_solution_data(
            expressions=[expression],
            setup_sweep_name=f"{setup_name} : {sweep_name}",
        )
        mag_by_expr, phase_by_expr = solution_data.full_matrix_mag_phase
        modes_by_index[f"mode_{mode}"] = {
            "expression": expression,
            "frequency_ghz": list(solution_data.primary_sweep_values),
            "magnitude_linear": list(mag_by_expr.get(expression, [])),
            "phase_rad": list(phase_by_expr.get(expression, [])),
        }

    s_parameters = {
        "computed": True,
        "port_type": "floquet",
        "floquet_port": floquet_port_name,
        "modes": modes_by_index,
        "note": (
            "Each entry under 'modes' is one Floquet mode's own "
            "self-reflection S-parameter (mode_1 = TE, mode_2 = TM at "
            "normal incidence), read via "
            f"S({floquet_port_name}:<mode>,{floquet_port_name}:<mode>) -- "
            "frequency_ghz is SolutionData.primary_sweep_values from a "
            "sweep created with unit='GHz'; magnitude_linear/phase_rad are "
            "SolutionData.full_matrix_mag_phase, phase in radians -- see "
            "simulation/hfss.py's module docstring for the primary-source "
            "citation on both properties and on the "
            "S(<port>:<mode>,<port>:<mode>) expression convention."
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
            applied = _apply_hfss_geometry(hfss, geometry)
            _create_setup_and_solve(hfss, frequency_hz, job.get("sweep"), setup_name, sweep_name)
            # Touchstone's legacy ".sNp" extension names N = the number of
            # excitations/ports the file's S-matrix actually holds (skrf's
            # rf.Network(...) legacy-format reader determines port count
            # from this extension) -- a lumped-port job excites exactly one
            # port, but a Floquet job excites `floquet_modes` of them (2 by
            # Hfss.create_floquet_port's own default), so the extension
            # must track applied.floquet_modes for the periodic path rather
            # than being hardcoded to ".s1p" for both.
            num_ports = applied.floquet_modes if applied.port_type == "floquet" else 1
            touchstone_path = self.archive_dir / f"{project_name}.s{num_ports}p"
            if applied.port_type == "floquet":
                extracted = _extract_hfss_floquet_results(
                    hfss,
                    setup_name,
                    sweep_name,
                    touchstone_path,
                    applied.port_name,
                    applied.floquet_modes,
                )
            else:
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
                "conductor_names": applied.conductor_names,
                "port_name": applied.port_name,
                "port_type": applied.port_type,
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
