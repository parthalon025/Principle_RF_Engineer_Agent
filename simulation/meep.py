"""MEEP FDTD full-wave EM simulation -- an independent-method cross-check
against openEMS (issue #60). Phase 12/ongoing-hardening ticket.

CRITICAL DIFFERENCE FROM NEC2++/openEMS (simulation/nec2pp.py,
simulation/openems.py): MEEP (github.com/NanoComp/meep) is driven here as a
Python LIBRARY (`import meep as mp`), not an external binary shelled out to
via subprocess -- confirmed from MEEP's own documentation (see SOURCES
CONSULTED below): its Python interface is `import meep as mp` followed by
constructing `mp.Simulation(...)` objects and calling methods/module
functions on them, not a CLI tool invoked with a generated input file. This
module therefore follows simulation/hfss.py's "guarded import + injectable
factory" shape (an `_import_meep()` guarded import and a
`meep_module`-injection constructor arg on MeepSimulator, mirroring
HfssSimulator's `hfss_factory`), NOT nec2pp.py's/openems.py's
subprocess+tempfile-input-file shape -- this is a deliberate, ticket-
mandated interface-shape difference, not an inconsistency with those two
modules.

SOURCES CONSULTED (primary; all fetched directly from meep.readthedocs.io
and github.com/NanoComp/meep during implementation, 2026-09 -- see the
per-fact citations below):

  - Dimensionless, scale-invariant unit system: meep.readthedocs.io/en/
    latest/Introduction/, quoted directly: "Meep uses dimensionless units
    where all these constants are unity" (i.e. c = 1, along with vacuum
    permittivity/permeability). The same page: "choosing some
    characteristic lengthscale in the system, a, and using that as the
    unit of distance" -- with c = 1, that same lengthscale a is also the
    unit of TIME, and frequency is expressed as a/lambda (equivalently, in
    units of c/a) where lambda is the vacuum wavelength. This module's
    `_m_to_meep`/`_hz_to_meep_freq`/`_meep_freq_to_hz` below implement
    exactly this relationship: a caller-chosen characteristic length
    `characteristic_length_m` (this module's own name for Meep's "a") is
    used to divide every meter-denominated coordinate before it reaches
    Meep, and `frequency_meep = frequency_hz * a_m / c` (c = the exact SI
    speed of light, 299_792_458.0 m/s, same constant rf_tools/
    calculations.py's own `wavelength()` uses) converts a real frequency
    into Meep's dimensionless units, per that same a/lambda relationship
    (lambda = c/frequency_hz, so a/lambda = frequency_hz * a / c).
    IMPORTANT: Meep itself does not mandate any particular value for `a`
    -- it is a free modeling choice ("choosing some characteristic
    lengthscale"). This module's own default, `_DEFAULT_CHARACTERISTIC_
    LENGTH_M = 1e-3` (1 mm), is THIS MODULE'S reasoned choice for
    RF/microwave-scale geometry (patch antennas etc. are typically
    mm-to-cm scale), not a documented Meep default -- callers may override
    it via `characteristic_length_m`.
  - `Simulation.__init__` parameters used here (cell_size, resolution,
    geometry, sources, boundary_layers, default_material): meep.
    readthedocs.io/en/latest/Python_User_Interface/, the `Simulation`
    class's full parameter list, fetched directly ("cell_size [Vector3]:
    Specifies the size of the cell centered on the origin", "resolution
    [number]: Computational grid resolution in pixels per unit distance",
    "boundary_layers [list of PML]: Absorbing boundary layers").
  - `Medium(epsilon=..., mu=...)`, `Block(material=, center=, size=)`,
    `Cylinder(material=, center=, radius=, height=, axis=)`, `PML
    (thickness=...)`: same Python_User_Interface page, same fetch.
  - `mp.metal` (aliased `mp.perfect_electric_conductor`) -- a predefined
    Medium representing an ideal perfect electric conductor, epsilon =
    -infinity: confirmed via a WebSearch synthesis of Meep's own Python
    interface docs and its "Local Density of States" tutorial (which
    builds a metal cavity via `material=mp.metal`), NOT independently
    re-fetched byte-for-byte from the primary page in this pass -- treat
    the exact alias spelling as reasoned-but-not-directly-quoted, same
    confidence-grading discipline simulation/hfss.py's module docstring
    already uses for `Hfss.lumped_port`'s unverified kwarg spelling.
  - `GaussianSource(frequency, fwidth=...)`, `Source(src, component=,
    center=, size=)`, `Vector3(x, y, z)`, `mp.Ex`/`mp.Ey`/`mp.Ez`/`mp.Hx`/
    `mp.Hy`/`mp.Hz` field-component constants, `mp.inf`: all directly
    quoted from the full worked code example on meep.readthedocs.io/en/
    latest/Python_Tutorials/Basics/ (the waveguide-bend reflectance/
    transmittance tutorial), fetched verbatim during implementation, e.g.
    `mp.Source(mp.GaussianSource(fcen,fwidth=df), component=mp.Ez,
    center=..., size=...)` and `mp.Block(size=mp.Vector3(mp.inf,w,mp.inf),
    ...)`.
  - `sim.add_flux(fcen, df, nfreq, FluxRegion(...))`, `mp.FluxRegion
    (center=, size=)`, `sim.run(until_after_sources=mp.stop_when_fields_
    decayed(dt, component, pt, decay_by))`, `sim.get_flux_data(flux)`,
    `sim.load_minus_flux_data(flux, data)`, `mp.get_fluxes(flux)`,
    `mp.get_flux_freqs(flux)`, `sim.reset_meep()`: ALL directly quoted,
    verbatim, from the SAME Basics-tutorial fetch above -- this is Meep's
    own officially-documented technique for computing reflectance/
    transmittance: run a canonical/reference structure first to record a
    baseline transmitted-power spectrum (`mp.get_fluxes`) and save the
    reflection-plane's own DFT field data (`sim.get_flux_data`), then run
    the real (perturbed) structure with that saved data subtracted out at
    the same reflection plane (`sim.load_minus_flux_data`) so the
    remaining flux there is the REFLECTED wave only, and finally divide by
    the baseline (`Rs = -bend_refl_flux/straight_tran_flux` in the
    tutorial's own code) to get a reflectance fraction. This module's own
    `_run_reflectance_cross_check` below follows that exact sequence
    (add_flux -> run -> get_flux_data/get_fluxes -> reset_meep -> add_flux
    again -> load_minus_flux_data -> run -> get_fluxes), with the same
    sign convention (`reflectance = -reflected_flux / baseline_flux`).
  - Installation / no PyPI wheel / no native Windows support: meep.
    readthedocs.io/en/latest/Installation/, quoted directly: "The
    recommended way to install PyMeep is using the Conda package manager"
    (`conda create -n mp -c conda-forge pymeep`) and "Native Windows
    installation is currently unsupported. The recommended procedure is
    to install Ubuntu using the Windows Subsystem for Linux (WSL)."
  - License: github.com/NanoComp/meep/blob/master/LICENSE, fetched
    directly, opening lines quoted verbatim: "GNU GENERAL PUBLIC LICENSE
    / Version 2, June 1991 / Copyright (C) 1989, 1991 Free Software
    Foundation, Inc." -- i.e. GPLv2 (recorded in docs/LICENSE_MATRIX.md).

HONEST CAVEAT -- read before trusting any of this end to end: MEEP is NOT
installed in this environment (confirmed via `import meep` failing at
implementation time; see tests/test_meep.py's
test_meep_is_genuinely_not_installed_in_this_environment) -- and unlike
NEC2++/openEMS, where "the binary just happens to be missing" is the whole
gap, this specific development sandbox is Windows, which MEEP's own
Installation docs say has NO native-install path at all (conda-forge only,
and only via WSL on Windows). This is NOT the same kind of structural block
as HFSS's licensing gate (simulation/hfss.py) -- MEEP is free/open-source
(GPLv2) and this project's own recommended deployment target is Ubuntu
24.04 LTS (README.md's Requirements section), where the documented
conda-forge install path is fully supported; there is no workstation-
confinement gate in this module, only the same "not installed here, install
it per its own docs before trusting a real run" honesty NEC2++/openEMS
already carry. NONE of the Meep API call shapes below have been exercised
against a real Meep install; they are built to the letter of the primary-
source citations above and exercised in tests only against a hand-written
fake object matching the subset of Meep's Python API this module actually
calls (see tests/test_meep.py). Treat any result as unverified end-to-end
until it has actually been run against a real Meep install at least once.

SCOPE OF THIS IMPLEMENTATION (explicitly narrower than a full Meep feature
set, and explicitly narrower than openEMS's own S-parameter extraction --
each limit below is a genuine, stated gap, not silently glossed over):

  - Geometry primitives: axis-aligned Box and Cylinder only (matching
    simulation/openems.py's/simulation/hfss.py's own primitive scope).
  - Materials: isotropic dielectric only (a single epsilon_r/mue_r applied
    identically to X/Y/Z, matching openems.py's own isotropic-only scope)
    -- no dispersion, conductivity, or Meep's real elemental-metal Drude
    fits. Conductors are modeled as `mp.metal` (an IDEAL, lossless PEC,
    epsilon = -infinity) -- a real copper/PEC structure's finite
    conductivity loss is not modeled, an explicit simplification.
  - PORT MODEL IS STRUCTURALLY DIFFERENT FROM openEMS/HFSS -- this is the
    single most important thing to understand before comparing results
    across solvers: Meep (a pure FDTD field solver) has no lumped-RLC-port
    concept the way openEMS's <LumpedElement>/<Excitation> or HFSS's
    lumped_port do. This module models a single "port" as (1) a Gaussian-
    pulse current source (`GaussianSource`+`Source`) on a caller-specified
    plane, and (2) a reflection-flux monitor (`FluxRegion`+`add_flux`) on
    a second caller-specified plane between the source and the structure
    under test. There is no reference-impedance (Z0) concept at all in
    this port model, unlike openEMS's/HFSS's Z0-normalized S-parameters.
  - S-parameters: ONLY power reflectance (|S11|^2, via the officially-
    documented flux-subtraction technique cited above) and its square
    root (`s11_magnitude`, a real, non-negative |S11|) are computed. NO
    complex phase, NO S21/multi-port transmission, and NO Touchstone
    export (Touchstone requires complex per-frequency S-data, which this
    pass does not produce) -- unlike openems.py's/hfss.py's computed=True
    complex S-parameters. A caller cross-checking against openEMS's
    complex S11 can only compare |S11| magnitude against this module's
    `s11_magnitude`, not phase.
  - THE "REFERENCE RUN" DESIGN CHOICE: this module's reflectance baseline
    is established by running the SAME source/cell/PML/materials/port-
    monitors but WITH the `conductors` geometry list omitted (i.e. the
    dielectric/background structure alone, without the metal structure
    under test) as the "canonical" run the tutorial's own straight-
    waveguide plays -- this is THIS MODULE'S OWN reasoned adaptation of
    the officially-documented straight-vs-bent-waveguide reflectance
    technique to an antenna-style single-port cross-check, NOT a
    documented Meep convention for antenna S11 extraction specifically.
    Flagged explicitly rather than presented as a verified fact.
  - Far-field/gain: NOT computed -- would require Meep's own separate
    near-to-far-field post-processing machinery, not invoked here (same
    honest gap simulation/openems.py's module docstring already carries
    for openEMS's separate nf2ff tool). `far_field` in this module's
    output always carries computed=False and an explanatory note, for
    structural parity with nec2pp.py's/openems.py's own result shape (so
    downstream code can treat every simulator's result uniformly).
  - No H5 field-dump files are requested or parsed -- this module's
    `SimulationResult.workdir` exists only to satisfy the Simulator
    contract (simulation/base.py) and is not otherwise populated.
"""

import math
import tempfile
from pathlib import Path
from typing import Any

from .base import SimulationResult, Simulator, SimulatorError

# Exact SI-defined speed of light, m/s -- same constant rf_tools/
# calculations.py's own wavelength() uses, for consistency across this
# codebase's unit conversions.
_SPEED_OF_LIGHT_M_S = 299_792_458.0

# This module's own default characteristic lengthscale ("a" in Meep's own
# unit-system terminology -- see module docstring citation). NOT a Meep-
# mandated value; Meep leaves this entirely to the caller. 1 mm is a
# reasonable default for RF/microwave-scale (patch antenna, mm-to-cm)
# geometry; override via job/geometry's `characteristic_length_m`.
_DEFAULT_CHARACTERISTIC_LENGTH_M = 1e-3

# Field components Meep's Python interface exposes as module-level
# constants (mp.Ex/mp.Ey/mp.Ez/mp.Hx/mp.Hy/mp.Hz) -- see module docstring
# citation (Basics tutorial, `component=mp.Ez`). Validated against this
# whitelist (raising ValueError, not a bare getattr AttributeError) so a
# typo'd component name fails with a clear message.
_FIELD_COMPONENTS = frozenset({"Ex", "Ey", "Ez", "Hx", "Hy", "Hz"})


# ---------------------------------------------------------------------------
# What this adapter CANNOT yet do for a periodic printed absorber (#229).
#
# #111 chose Meep over NEC2 for metamaterial unit cells and was right about
# the direction: Meep the SIMULATOR supports Bloch-periodic boundaries,
# complex permittivity and conductivity, all of which a unit cell needs and
# NEC2's thin-wire formulation cannot express at all. But THIS ADAPTER is a
# narrow slice of Meep (see SCOPE above), and three of the things it leaves
# out are precisely an absorber's whole mechanism.
#
# Kept here, next to the code whose limits they describe, rather than in the
# design loop -- an adapter is the only honest place to state what it can do.
# ---------------------------------------------------------------------------

PERIODIC_ABSORBER_CAPABILITY_GAPS: tuple[dict[str, str], ...] = (
    {
        "gap": "no_periodic_boundary",
        "assumed": (
            "the structure is finite and isolated: _run_reflectance_cross_check "
            "sets boundary_layers=[mp.PML(...)] on every side and never sets a "
            "k_point, so there is no Bloch-periodic boundary anywhere in this "
            "adapter"
        ),
        "costs": (
            "a unit cell IS an infinite periodic array represented by one cell; "
            "simulated between absorbing walls it is a lone element in free "
            "space instead, and the coupling to its neighbours -- which is what "
            "sets the resonance -- is absent"
        ),
        "cheapest_test": (
            "add k_point=mp.Vector3() and periodic boundaries on the two "
            "in-plane axes, then reproduce a published unit-cell reflectance"
        ),
    },
    {
        "gap": "no_lossy_dielectric",
        "assumed": (
            "substrates are lossless: _build_geometry_list builds "
            "mp.Medium(epsilon=<real>, mu=<real>) with no D_conductivity and no "
            "imaginary part"
        ),
        "costs": (
            "the spacer's own dissipation is discarded, and on a printed "
            "silicone or TPU stack that is 20-36 % of the loss budget, not a "
            "rounding term"
        ),
        "cheapest_test": (
            "map a loss tangent onto Meep's D_conductivity and check the slab's "
            "reflectance against the closed form in rf_tools/absorber.py"
        ),
    },
    {
        "gap": "no_resistive_sheet",
        "assumed": (
            "conductors are mp.metal -- an IDEAL, lossless perfect electric "
            "conductor (see SCOPE above)"
        ),
        "costs": (
            "a printed absorber dissipates in a RESISTIVE patterned layer; "
            "modelled as a perfect conductor that layer cannot absorb anything, "
            "so the run reports a near-perfect reflector no matter what was "
            "designed -- a confidently wrong answer rather than a noisy one"
        ),
        "cheapest_test": (
            "give conductors a finite conductivity and confirm a sheet at "
            "377 ohm/sq absorbs rather than reflects"
        ),
    },
)


def periodic_absorber_capability_gaps() -> list[dict[str, str]]:
    """The reasons this adapter cannot yet simulate a printed periodic
    absorber, each naming what is assumed, what it costs, and the cheapest
    way to close it. Empty list would mean it can."""
    return [dict(gap) for gap in PERIODIC_ABSORBER_CAPABILITY_GAPS]


def _import_meep() -> Any:
    """Guarded `import meep as mp` -- deferred to inside this function
    (rather than a top-of-module `import`) because Meep genuinely will not
    be installed in most environments, including this one (see module
    docstring: conda-forge only, no PyPI wheel, no native Windows support).
    Only ever called from MeepSimulator._real_meep_module, itself only
    reached when no `meep_module` was injected for testing."""
    try:
        import meep as mp  # see module docstring citation
    except ImportError as exc:
        raise SimulatorError(
            "meep is not installed. MEEP is used as a Python library "
            "(import meep), not an external binary -- install it per its "
            "own docs (meep.readthedocs.io/en/latest/Installation/), e.g. "
            "via conda: `conda create -n mp -c conda-forge pymeep`. There "
            "is no PyPI wheel and no native Windows install path (WSL is "
            "required on Windows); see README.md's Optional tools list."
        ) from exc
    return mp


# ---------------------------------------------------------------------------
# Unit conversion -- Meep's dimensionless, scale-invariant unit system (see
# module docstring citation).
# ---------------------------------------------------------------------------


def _m_to_meep(value_m: float, a_m: float) -> float:
    """Convert a meter-denominated coordinate to Meep's dimensionless
    distance units (coordinate / a) -- see module docstring citation."""
    return float(value_m) / a_m


def _hz_to_meep_freq(frequency_hz: float, a_m: float) -> float:
    """Convert a real frequency in Hz to Meep's dimensionless frequency
    units (a/lambda = frequency_hz * a / c) -- see module docstring
    citation."""
    return float(frequency_hz) * a_m / _SPEED_OF_LIGHT_M_S


def _meep_freq_to_hz(frequency_meep: float, a_m: float) -> float:
    """Inverse of _hz_to_meep_freq -- converts a Meep dimensionless
    frequency back to Hz for this module's output."""
    return float(frequency_meep) * _SPEED_OF_LIGHT_M_S / a_m


def _vector3(mp_module: Any, xyz_m: list[float], a_m: float) -> Any:
    x_m, y_m, z_m = xyz_m
    return mp_module.Vector3(_m_to_meep(x_m, a_m), _m_to_meep(y_m, a_m), _m_to_meep(z_m, a_m))


# ---------------------------------------------------------------------------
# Geometry primitive construction -- Box/Cylinder only (see module
# docstring SCOPE section).
# ---------------------------------------------------------------------------


def _primitive_to_meep(mp_module: Any, prim: dict[str, Any], a_m: float, material: Any) -> Any:
    """Build one mp.Block or mp.Cylinder from a {"shape": "box"|"cylinder",
    ...} primitive dict -- see module docstring citation for both classes'
    constructor signatures."""
    shape = prim.get("shape", "box")
    if shape == "box":
        required = ("p1_m", "p2_m")
        missing = [f for f in required if f not in prim]
        if missing:
            raise ValueError(f"box primitive missing required field(s): {missing}")
        p1 = prim["p1_m"]
        p2 = prim["p2_m"]
        center_m = [(p1[i] + p2[i]) / 2.0 for i in range(3)]
        size_m = [abs(p2[i] - p1[i]) for i in range(3)]
        return mp_module.Block(
            material=material,
            center=_vector3(mp_module, center_m, a_m),
            size=_vector3(mp_module, size_m, a_m),
        )
    if shape == "cylinder":
        required = ("center_m", "radius_m")
        missing = [f for f in required if f not in prim]
        if missing:
            raise ValueError(f"cylinder primitive missing required field(s): {missing}")
        axis = prim.get("axis", [0.0, 0.0, 1.0])
        height_m = prim.get("height_m")
        height = mp_module.inf if height_m is None else _m_to_meep(height_m, a_m)
        return mp_module.Cylinder(
            material=material,
            center=_vector3(mp_module, prim["center_m"], a_m),
            radius=_m_to_meep(prim["radius_m"], a_m),
            height=height,
            axis=mp_module.Vector3(*axis),
        )
    raise ValueError(f"shape must be 'box' or 'cylinder', got {shape!r}")


def _build_geometry_list(
    mp_module: Any, geometry: dict[str, Any], a_m: float, include_conductors: bool
) -> list[Any]:
    """Materials (dielectric, always present) plus, when include_conductors
    is True, conductors (mapped to mp.metal -- an ideal PEC, see module
    docstring citation). include_conductors=False is this module's own
    "reference run" baseline -- see module docstring's REFERENCE RUN
    design-choice caveat."""
    objects: list[Any] = []
    for idx, mat in enumerate(geometry.get("materials", [])):
        try:
            epsilon_r = float(mat.get("epsilon_r", 1.0))
            mue_r = float(mat.get("mue_r", 1.0))
            medium = mp_module.Medium(epsilon=epsilon_r, mu=mue_r)
            objects.append(_primitive_to_meep(mp_module, mat, a_m, medium))
        except ValueError as exc:
            raise ValueError(f"materials[{idx}]: {exc}") from exc
    if include_conductors:
        for idx, cond in enumerate(geometry.get("conductors", [])):
            try:
                objects.append(_primitive_to_meep(mp_module, cond, a_m, mp_module.metal))
            except ValueError as exc:
                raise ValueError(f"conductors[{idx}]: {exc}") from exc
    return objects


# ---------------------------------------------------------------------------
# Port: one Gaussian-pulse source + one reflection-flux monitor plane (see
# module docstring's PORT MODEL caveat).
# ---------------------------------------------------------------------------


def _validate_port(port: dict[str, Any]) -> None:
    # Nested-within-geometry field validation -> ValueError, matching
    # simulation/hfss.py's/simulation/openems.py's own convention (only
    # job-dict-top-level required keys, checked directly in
    # MeepSimulator.run() below, raise SimulatorError).
    required = ("center_m", "size_m", "direction", "frequency_hz")
    missing = [f for f in required if f not in port]
    if missing:
        raise ValueError(f"geometry['port'] missing required field(s): {missing}")
    if port["direction"] not in ("x", "y", "z"):
        raise ValueError(
            f"geometry['port']['direction'] must be 'x', 'y', or 'z', got {port['direction']!r}"
        )
    axis_index = {"x": 0, "y": 1, "z": 2}[port["direction"]]
    if port["size_m"][axis_index] != 0:
        raise ValueError(
            "geometry['port']['size_m'] must be zero along the port's own "
            f"'direction' axis ({port['direction']!r}, index {axis_index}) -- "
            "a source/flux plane is one dimension lower than the cell, per "
            "Meep's own FluxRegion/Source convention (see module docstring "
            "citation); got size_m="
            f"{port['size_m']!r}"
        )
    component = port.get("component", "Ez")
    if component not in _FIELD_COMPONENTS:
        raise ValueError(
            f"geometry['port']['component'] must be one of {sorted(_FIELD_COMPONENTS)}, "
            f"got {component!r}"
        )


def _build_source(mp_module: Any, port: dict[str, Any], a_m: float) -> Any:
    frequency_hz = float(port["frequency_hz"])
    fcen = _hz_to_meep_freq(frequency_hz, a_m)
    fractional_bw = float(port.get("fractional_bandwidth", 0.2))
    fwidth = fcen * fractional_bw
    component_name = port.get("component", "Ez")
    component = getattr(mp_module, component_name)
    return mp_module.Source(
        mp_module.GaussianSource(frequency=fcen, fwidth=fwidth),
        component=component,
        center=_vector3(mp_module, port["center_m"], a_m),
        size=_vector3(mp_module, port["size_m"], a_m),
    )


def _add_flux_monitor(
    mp_module: Any,
    sim: Any,
    fcen: float,
    fwidth: float,
    nfreq: int,
    center_m: list[float],
    size_m: list[float],
    a_m: float,
) -> Any:
    region = mp_module.FluxRegion(
        center=_vector3(mp_module, center_m, a_m), size=_vector3(mp_module, size_m, a_m)
    )
    return sim.add_flux(fcen, fwidth, nfreq, region)


def _run_until_decayed(
    mp_module: Any,
    sim: Any,
    component_name: str,
    stop_point_m: list[float],
    a_m: float,
    decay_by: float,
    check_interval: float,
) -> None:
    component = getattr(mp_module, component_name)
    pt = _vector3(mp_module, stop_point_m, a_m)
    sim.run(
        until_after_sources=mp_module.stop_when_fields_decayed(
            check_interval, component, pt, decay_by
        )
    )


# ---------------------------------------------------------------------------
# S-parameter (power reflectance) extraction via the officially-documented
# two-run flux-subtraction technique -- see module docstring citation.
# ---------------------------------------------------------------------------


def _compute_reflectance(
    frequency_hz_points: list[float], reflected_flux: list[float], baseline_flux: list[float]
) -> dict[str, Any]:
    if not baseline_flux or any(b == 0 for b in baseline_flux):
        return {
            "computed": False,
            "note": (
                "the reference run's baseline transmitted-flux spectrum is "
                "empty or contains a zero -- nothing to normalize "
                "reflectance against (check the reference-run source "
                "actually radiated past the reference monitor plane)."
            ),
        }
    reflectance = [-r / b for r, b in zip(reflected_flux, baseline_flux, strict=True)]
    s11_magnitude = [math.sqrt(abs(r)) for r in reflectance]
    return {
        "computed": True,
        "method": (
            "Power reflectance via Meep's own documented flux-subtraction "
            "technique (sim.add_flux/FluxRegion, sim.get_flux_data + "
            "sim.load_minus_flux_data to isolate the reflected wave at a "
            "monitor plane, mp.get_fluxes for the resulting spectrum) -- "
            "see simulation/meep.py's module docstring for the full "
            "citation and this module's REFERENCE RUN design-choice "
            "caveat. reflectance = -reflected_flux / baseline_flux "
            "(the tutorial's own sign convention); s11_magnitude = "
            "sqrt(|reflectance|). NO phase is extracted -- see module "
            "docstring's SCOPE section."
        ),
        "frequency_hz": frequency_hz_points,
        "reflectance": reflectance,
        "s11_magnitude": s11_magnitude,
        "note": (
            "s11_magnitude is |S11| power-reflectance magnitude ONLY -- no "
            "complex phase, no S21/multi-port transmission, no Touchstone "
            "export (see module docstring SCOPE section). Suitable for "
            "comparing against the magnitude of openEMS's/HFSS's own "
            "complex S11, not a full complex cross-check."
        ),
    }


# ---------------------------------------------------------------------------
# MeepSimulator: the Simulator contract (simulation/base.py, unchanged).
# ---------------------------------------------------------------------------


class MeepSimulator(Simulator):
    name = "MEEP"

    def __init__(self, meep_module: Any | None = None):
        """`meep_module`, if given, replaces the real guarded `import meep
        as mp` -- a test-only injection seam (mirroring HfssSimulator's
        `hfss_factory` constructor-injection pattern, see simulation/
        hfss.py) exercising this module's own geometry/unit-translation and
        flux-subtraction orchestration against a hand-written fake matching
        the subset of Meep's real Python API this module calls (see
        tests/test_meep.py). The real run_meep_simulation()/agent/MCP tool
        wiring never passes it, so a real call always goes through the
        real guarded import."""
        self._meep_module = meep_module

    def _real_meep_module(self) -> Any:
        return _import_meep()

    def run(self, job: dict) -> SimulationResult:
        geometry = job.get("geometry")
        if not geometry:
            raise SimulatorError("job['geometry'] is required")
        for required_key in (
            "cell_size_m",
            "pml_thickness_m",
            "mesh_cell_size_m",
            "port",
            "reflection_monitor_center_m",
            "reference_monitor_center_m",
        ):
            if required_key not in geometry:
                raise SimulatorError(f"geometry[{required_key!r}] is required")
        port = geometry["port"]
        _validate_port(port)

        mp_module = self._meep_module or self._real_meep_module()
        a_m = float(job.get("characteristic_length_m", _DEFAULT_CHARACTERISTIC_LENGTH_M))
        nfreq = int(job.get("nfreq", 1))

        workdir = Path(job.get("workdir") or tempfile.mkdtemp(prefix="meep_"))
        workdir.mkdir(parents=True, exist_ok=True)

        s_parameters = _run_reflectance_cross_check(mp_module, geometry, a_m, nfreq, job)

        return SimulationResult(
            simulator=self.name,
            status="COMPLETED",
            workdir=workdir,
            outputs={
                "s_parameters": s_parameters,
                "far_field": {
                    "computed": False,
                    "note": (
                        "Far-field/gain pattern extraction requires Meep's "
                        "own separate near-to-far-field post-processing "
                        "machinery, not invoked here -- see simulation/"
                        "meep.py's module docstring 'SCOPE OF THIS "
                        "IMPLEMENTATION'."
                    ),
                },
                "gain_dbi": None,
            },
        )


def _run_reflectance_cross_check(
    mp_module: Any, geometry: dict[str, Any], a_m: float, nfreq: int, job: dict[str, Any]
) -> dict[str, Any]:
    port = geometry["port"]
    frequency_hz = float(port["frequency_hz"])
    fcen = _hz_to_meep_freq(frequency_hz, a_m)
    fractional_bw = float(port.get("fractional_bandwidth", 0.2))
    fwidth = fcen * fractional_bw
    component_name = port.get("component", "Ez")
    monitor_size_m = geometry.get("monitor_size_m", port["size_m"])
    decay_by = float(job.get("decay_by", 1e-3))
    check_interval = float(job.get("decay_check_interval", 50))
    stop_point_m = job.get("stop_point_m", geometry["reflection_monitor_center_m"])
    cell_size = _vector3(mp_module, geometry["cell_size_m"], a_m)
    pml_thickness = _m_to_meep(float(geometry["pml_thickness_m"]), a_m)
    resolution = a_m / float(geometry["mesh_cell_size_m"])

    # --- Reference run: materials only, conductors omitted (see module
    # docstring's REFERENCE RUN design-choice caveat) ------------------
    ref_sim = mp_module.Simulation(
        cell_size=cell_size,
        resolution=resolution,
        geometry=_build_geometry_list(mp_module, geometry, a_m, include_conductors=False),
        sources=[_build_source(mp_module, port, a_m)],
        boundary_layers=[mp_module.PML(pml_thickness)],
    )
    refl_flux_ref = _add_flux_monitor(
        mp_module,
        ref_sim,
        fcen,
        fwidth,
        nfreq,
        geometry["reflection_monitor_center_m"],
        monitor_size_m,
        a_m,
    )
    baseline_flux_monitor = _add_flux_monitor(
        mp_module,
        ref_sim,
        fcen,
        fwidth,
        nfreq,
        geometry["reference_monitor_center_m"],
        monitor_size_m,
        a_m,
    )
    _run_until_decayed(
        mp_module, ref_sim, component_name, stop_point_m, a_m, decay_by, check_interval
    )
    saved_refl_data = ref_sim.get_flux_data(refl_flux_ref)
    baseline_flux = mp_module.get_fluxes(baseline_flux_monitor)
    flux_freqs_meep = mp_module.get_flux_freqs(refl_flux_ref)
    ref_sim.reset_meep()

    # --- Full run: materials + conductors -- the structure under test -
    full_sim = mp_module.Simulation(
        cell_size=cell_size,
        resolution=resolution,
        geometry=_build_geometry_list(mp_module, geometry, a_m, include_conductors=True),
        sources=[_build_source(mp_module, port, a_m)],
        boundary_layers=[mp_module.PML(pml_thickness)],
    )
    refl_flux_full = _add_flux_monitor(
        mp_module,
        full_sim,
        fcen,
        fwidth,
        nfreq,
        geometry["reflection_monitor_center_m"],
        monitor_size_m,
        a_m,
    )
    full_sim.load_minus_flux_data(refl_flux_full, saved_refl_data)
    _run_until_decayed(
        mp_module, full_sim, component_name, stop_point_m, a_m, decay_by, check_interval
    )
    reflected_flux = mp_module.get_fluxes(refl_flux_full)
    full_sim.reset_meep()

    frequency_hz_points = [_meep_freq_to_hz(f, a_m) for f in flux_freqs_meep]
    return _compute_reflectance(frequency_hz_points, reflected_flux, baseline_flux)


def run_meep_simulation(
    geometry: dict[str, Any],
    characteristic_length_m: float = _DEFAULT_CHARACTERISTIC_LENGTH_M,
    nfreq: int = 1,
    workdir: str | None = None,
    meep_module: Any | None = None,
) -> dict[str, Any]:
    """Run a MEEP FDTD power-reflectance cross-check from structured
    geometry via MeepSimulator, and return a SIMULATED-provenance result.

    `geometry` shape:
        {
          "cell_size_m": [sx, sy, sz],    # required; sz=0 for a 2D cell
          "pml_thickness_m": float,        # required
          "mesh_cell_size_m": float,       # required real-world grid
              spacing in meters -- converted to Meep's own `resolution`
              (pixels per characteristic-length unit `a`) internally.
          "materials": [                   # optional, dielectric
              {"name": str (optional), "shape": "box" (default) |
               "cylinder", "p1_m"/"p2_m" (box) or "center_m"/"radius_m"/
               "height_m"/"axis" (cylinder), "epsilon_r": float (default
               1.0), "mue_r": float (default 1.0)}, ...
          ],
          "conductors": [                  # optional, ideal PEC (mp.metal)
              same shape as materials, minus epsilon_r/mue_r
          ],
          "port": {                        # required
              "center_m": [x,y,z], "size_m": [x,y,z] (zero along
                  'direction'), "direction": "x"|"y"|"z",
              "component": "Ez" (default) | "Ex"|"Ey"|"Hx"|"Hy"|"Hz",
              "frequency_hz": float, "fractional_bandwidth": float
                  (default 0.2, the Gaussian pulse's fwidth/fcen ratio),
          },
          "reflection_monitor_center_m": [x,y,z],   # required
          "reference_monitor_center_m": [x,y,z],     # required
          "monitor_size_m": [x,y,z],   # optional, defaults to port size_m
        }

    See this module's header comment for the format-verification citations
    (Meep's own dimensionless unit system and Python API) and the honest
    caveat/SCOPE sections: this is a POWER-REFLECTANCE-ONLY (|S11|
    magnitude, no phase, no S21) cross-check against a real Meep run, built
    to the documented API but not run against a real Meep install in this
    environment.
    """
    simulator = MeepSimulator(meep_module=meep_module)
    result = simulator.run(
        {
            "geometry": geometry,
            "characteristic_length_m": characteristic_length_m,
            "nfreq": nfreq,
            "workdir": workdir,
        }
    )
    return {
        "provenance": "SIMULATED",
        "simulator": result.simulator,
        "status": result.status,
        "workdir": str(result.workdir),
        **result.outputs,
    }
