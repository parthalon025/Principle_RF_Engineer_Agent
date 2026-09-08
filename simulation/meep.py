"""MEEP FDTD full-wave EM simulation -- an independent-method cross-check
against openEMS (issue #60). Phase 12/ongoing-hardening ticket.

HOW MEEP IS DRIVEN (two paths, one implementation): MEEP
(github.com/NanoComp/meep) is a Python LIBRARY (`import meep as mp`), not a
CLI tool with an input file -- confirmed from its own documentation (see
SOURCES CONSULTED below): the interface is `import meep as mp` followed by
constructing `mp.Simulation(...)` objects and calling methods on them. So
this module follows simulation/hfss.py's "guarded import + injectable
factory" shape (an `_import_meep()` guarded import and a `meep_module`
injection arg on MeepSimulator, mirroring HfssSimulator's `hfss_factory`)
rather than nec2pp.py's/openems.py's generated-input-file shape.

That was the whole story until #231. It does not survive contact with this
repo's own container, where the Dockerfile installs pymeep into a conda
environment and the application runs under a separate uv venv: an
in-process `import meep` fails inside an image that genuinely has Meep in
it. So MeepSimulator now ALSO accepts a `python_executable` (default: the
MEEP_PYTHON environment variable the Dockerfile already exports) and, when
that names a different interpreter, delegates the run to it as a
subprocess -- exactly how simulation/gprmax.py resolves GPRMAX_PYTHON.

Crucially this is NOT a second implementation. The generated runner
(`_RUNNER_TEMPLATE`) imports THIS module's own
`_run_reflectance_cross_check` and calls it, so the physics exists once and
cannot drift between the two paths. Both this module and simulation/base.py
import only the standard library, which is what lets a foreign interpreter
holding none of the project's dependencies import them.

A side benefit worth naming: the subprocess boundary also keeps MEEP's
GPLv2 at arm's length, the same way every other GPL tool in
docs/LICENSE_MATRIX.md is invoked. That is a consequence, not the reason.

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
  - Materials: isotropic only (a single epsilon_r/mue_r applied identically
    to X/Y/Z, matching openems.py's own isotropic-only scope) -- no
    dispersion and no Meep elemental-metal Drude fits. LOSS IS SUPPORTED
    (#230): a material may state a `loss_tangent`, mapped to Meep's
    D_conductivity at the band-centre frequency, and a conductor may state
    `conductivity_s_m` or `sheet_resistance_ohm_sq` + `thickness_m` instead
    of being an ideal PEC. A conductor that states neither is still
    `mp.metal` -- an IDEAL, lossless PEC -- which remains the default and is
    correct for a genuine ground plane but WRONG for a printed resistive
    layer, which cannot dissipate anything if modelled that way.
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

import json
import math
import os
import subprocess
import sys
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

# All three were closed and verified against real Meep 1.34.0 (see the
# conversions section below for how each was checked). Kept as an empty tuple
# with its history rather than deleted: this is the list orchestration/
# design_loop.py consults before running an absorber, and a future change that
# reopens one of these should have an obvious place to say so.
#
#   * no_periodic_boundary  -> closed by `_boundaries_and_k_point`, which sets
#     Bloch-periodic boundaries and k_point on the named axes. Verified: a
#     uniform sheet is translation-invariant, so a periodic cell of one must
#     reproduce the 1-D answer, and it does.
#   * no_lossy_dielectric   -> closed by `loss_tangent` on a material, mapped
#     to Meep's D_conductivity at the band centre.
#   * no_resistive_sheet    -> closed by `conductivity_s_m` /
#     `sheet_resistance_ohm_sq` on a conductor. Verified against the exact
#     free-standing-sheet result (peak absorptance 0.5 at Rs = eta0/2) and
#     against rf_tools/absorber.py on a Salisbury screen.
PERIODIC_ABSORBER_CAPABILITY_GAPS: tuple[dict[str, str], ...] = ()


def periodic_absorber_capability_gaps() -> list[dict[str, str]]:
    """The reasons this adapter cannot simulate a printed periodic absorber.

    Empty since all three were closed and verified against real Meep 1.34.0
    -- see PERIODIC_ABSORBER_CAPABILITY_GAPS above for what they were, and
    PERIODIC_ABSORBER_VALIDITY below for what is approximate but present.
    Kept as a function rather than deleted because orchestration/
    design_loop.py asks it before running, and something that CAN go wrong
    again should keep being asked.
    """
    return [dict(gap) for gap in PERIODIC_ABSORBER_CAPABILITY_GAPS]


# What remains APPROXIMATE, as distinct from absent. These ride with every
# result rather than blocking one, per the charter's warn-never-block rule.
PERIODIC_ABSORBER_VALIDITY: tuple[dict[str, str], ...] = (
    {
        "flag": "normal_incidence_only",
        "assumed": ("k_point is Vector3() -- zero -- so the wave arrives square-on to the surface"),
        "costs": (
            "an absorber's response changes with the angle it is hit from, and "
            "this says nothing about any angle but straight-on"
        ),
        "cheapest_test": (
            "set a non-zero k_point for one oblique angle and compare; the "
            "machinery is here, the sweep is not"
        ),
    },
    {
        "flag": "loss_tangent_pinned_at_band_centre",
        "assumed": (
            "a dielectric's loss tangent is converted to Meep's single "
            "frequency-independent D_conductivity at the band-centre frequency"
        ),
        "costs": (
            "loss is exact at band centre and drifts slightly towards the "
            "edges; a real material's loss tangent drifts with frequency too, "
            "so this is the right shape of approximation, but it is one"
        ),
        "cheapest_test": ("narrow the band and confirm the answer at centre does not move"),
    },
)


# ---------------------------------------------------------------------------
# SI -> Meep material conversions.
#
# Meep is dimensionless: eps(w) = eps_inf * (1 + i*sigma_D/w), with w = 2*pi*f
# and f in units of c/a. Both conversions below were VERIFIED against real
# Meep 1.34.0, not derived on paper and trusted:
#
#   * A free-standing resistive sheet has an exact closed form (a shunt Rs
#     across free space, peak absorptance 0.5 at Rs = eta0/2 = 188.365).
#     Meep returns A = 0.4999 there, and puts the maximum at exactly that Rs.
#   * A Salisbury screen (377 ohm/sq at a quarter wave over a ground plane)
#     agrees with rf_tools/absorber.py to within 0.001 across 6-14 GHz, both
#     peaking at 1.0000 at the design frequency.
# ---------------------------------------------------------------------------

_EPS0_F_M = 8.8541878128e-12


def sigma_d_from_conductivity(sigma_s_m: float, a_m: float, eps_inf: float = 1.0) -> float:
    """Meep's dimensionless `D_conductivity` from an SI conductivity (S/m).

    Equating Meep's `eps_inf*(1 + i*sigma_D/w)` with SI's
    `eps_r + i*sigma_SI/(w_SI*eps0)`, using `f_meep = f_SI * a / c`, the
    frequency cancels and leaves

        sigma_D = sigma_SI * a / (c * eps0 * eps_inf)

    Frequency-independent, so this one is exact at every frequency.
    """
    if sigma_s_m < 0:
        raise ValueError(f"sigma_s_m must be non-negative; got {sigma_s_m!r}.")
    if eps_inf <= 0:
        raise ValueError(f"eps_inf must be positive; got {eps_inf!r}.")
    return sigma_s_m * a_m / (_SPEED_OF_LIGHT_M_S * _EPS0_F_M * eps_inf)


def sigma_d_from_loss_tangent(tan_delta: float, fcen_meep: float) -> float:
    """Meep's `D_conductivity` for a dielectric quoted as a loss tangent.

        tan_d = eps_imag/eps_real = sigma_D/w  =>  sigma_D = 2*pi*f * tan_d

    UNLIKE the conductivity conversion above, this one is frequency-
    dependent, and Meep's `D_conductivity` is a single constant. Pinning it
    at the band centre makes the loss tangent exact there and slightly off
    towards the band edges -- a real material's tan_d drifts with frequency
    anyway, so this is the right shape of approximation, but it is an
    approximation and callers are told so in the result's `validity`.
    """
    if tan_delta < 0:
        raise ValueError(f"tan_delta must be non-negative; got {tan_delta!r}.")
    return 2 * math.pi * fcen_meep * tan_delta


def conductivity_from_sheet_resistance(sheet_resistance_ohm_sq: float, thickness_m: float) -> float:
    """Bulk conductivity (S/m) of a film of given sheet resistance and
    thickness: `sigma = 1 / (R_s * t)`. This is how a printed layer's
    measurable property (ohms per square, from a four-point probe) becomes
    something a field solver can use."""
    if sheet_resistance_ohm_sq <= 0:
        raise ValueError(
            f"sheet_resistance_ohm_sq must be positive; got {sheet_resistance_ohm_sq!r}."
        )
    if thickness_m <= 0:
        raise ValueError(f"thickness_m must be positive; got {thickness_m!r}.")
    return 1.0 / (sheet_resistance_ohm_sq * thickness_m)


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
        # The container case, and the confusing one: this repo's Dockerfile
        # DOES install pymeep, into its own conda environment, and exports
        # MEEP_PYTHON pointing at that interpreter. But this adapter drives
        # Meep in-process, so a separate interpreter is unreachable to it and
        # the old message ("meep is not installed") was actively misleading
        # -- Meep is installed, just not here. Say which of the two it is.
        meep_python = os.getenv("MEEP_PYTHON")
        if meep_python:
            raise SimulatorError(
                "meep is installed, but not in THIS interpreter. MEEP_PYTHON "
                f"is set to {meep_python!r}, which is a different Python from "
                f"the one running this code ({sys.executable!r}) -- the "
                "Dockerfile installs pymeep into its own conda environment. "
                "This adapter imports meep in-process and has no subprocess "
                "handoff, so it cannot reach that interpreter; "
                "simulation/gprmax.py is the pattern it would need (it runs "
                "GPRMAX_PYTHON as a subprocess). Until that exists, either "
                "install pymeep into this environment or run this code under "
                "MEEP_PYTHON."
            ) from exc
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
    mp_module: Any,
    geometry: dict[str, Any],
    a_m: float,
    include_conductors: bool,
    fcen_meep: float | None = None,
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
            # A lossless Medium stays byte-for-byte what it was before loss
            # was supported, so existing callers see no change at all.
            tan_delta = float(mat.get("loss_tangent", 0.0))
            if tan_delta:
                if fcen_meep is None:
                    raise ValueError(
                        "loss_tangent needs the band-centre frequency to become a "
                        "Meep D_conductivity; this call supplied none"
                    )
                medium = mp_module.Medium(
                    epsilon=epsilon_r,
                    mu=mue_r,
                    D_conductivity=sigma_d_from_loss_tangent(tan_delta, fcen_meep),
                )
            else:
                medium = mp_module.Medium(epsilon=epsilon_r, mu=mue_r)
            objects.append(_primitive_to_meep(mp_module, mat, a_m, medium))
        except ValueError as exc:
            raise ValueError(f"materials[{idx}]: {exc}") from exc
    if include_conductors:
        for idx, cond in enumerate(geometry.get("conductors", [])):
            try:
                medium = _conductor_medium(mp_module, cond, a_m)
                objects.append(_primitive_to_meep(mp_module, cond, a_m, medium))
            except ValueError as exc:
                raise ValueError(f"conductors[{idx}]: {exc}") from exc
    return objects


def _conductor_medium(mp_module: Any, conductor: dict[str, Any], a_m: float) -> Any:
    """The material a conductor primitive is made of.

    Default stays `mp.metal` -- an ideal, lossless perfect electric
    conductor -- so nothing that worked before changes. A conductor that
    states either `conductivity_s_m` or `sheet_resistance_ohm_sq` (with its
    own `thickness_m`) instead becomes a finite-conductivity medium, which
    is what a PRINTED layer actually is.

    This is the difference between a mirror and an absorber: a perfect
    conductor reflects everything by definition, so a stack modelled with
    one cannot dissipate anything no matter what was designed.
    """
    sigma_s_m = conductor.get("conductivity_s_m")
    sheet_resistance = conductor.get("sheet_resistance_ohm_sq")
    if sigma_s_m is None and sheet_resistance is None:
        return mp_module.metal
    if sigma_s_m is not None and sheet_resistance is not None:
        raise ValueError(
            "state conductivity_s_m OR sheet_resistance_ohm_sq, not both -- they are "
            "two ways of saying the same thing and cannot be reconciled if they disagree"
        )
    if sheet_resistance is not None:
        thickness_m = conductor.get("thickness_m")
        if thickness_m is None:
            raise ValueError(
                "sheet_resistance_ohm_sq needs thickness_m alongside it: ohms per "
                "square is a property of a film OF SOME THICKNESS, and the "
                "conductivity a solver needs is 1/(R_s*t)"
            )
        sigma_s_m = conductivity_from_sheet_resistance(float(sheet_resistance), float(thickness_m))
    return mp_module.Medium(
        epsilon=1.0, D_conductivity=sigma_d_from_conductivity(float(sigma_s_m), a_m)
    )


def _boundaries_and_k_point(
    mp_module: Any, geometry: dict[str, Any], pml_thickness: float
) -> tuple[list[Any], Any | None]:
    """Boundary layers, and a Bloch k_point when the cell is periodic.

    Default (no `periodic_axes`) is PML on every side, exactly as before: a
    finite, isolated structure in free space.

    With `periodic_axes` (e.g. `["x", "y"]`) the named axes get NO absorbing
    layer and the simulation gets `k_point=Vector3()`, which is Meep's way
    of saying the fields repeat identically from one cell to the next. That
    turns one drawn cell into an infinite array of them -- which is what a
    metamaterial unit cell IS. Without it, a unit cell is simulated as a
    lone element between absorbing walls, and the coupling to its
    neighbours, which is what sets the resonance, is simply absent.

    `Vector3()` is zero, i.e. normal incidence. Oblique incidence needs a
    non-zero k_point and is deliberately not offered here rather than
    offered wrongly.
    """
    periodic = [str(axis).lower() for axis in geometry.get("periodic_axes", [])]
    if not periodic:
        return [mp_module.PML(pml_thickness)], None

    directions = {"x": mp_module.X, "y": mp_module.Y, "z": mp_module.Z}
    unknown = sorted(set(periodic) - set(directions))
    if unknown:
        raise ValueError(f"periodic_axes must be drawn from x/y/z; got {unknown}")
    layers = [
        mp_module.PML(pml_thickness, direction=directions[axis])
        for axis in ("x", "y", "z")
        if axis not in periodic
    ]
    if not layers:
        raise ValueError(
            "periodic_axes names every axis, leaving no absorbing boundary for the "
            "wave to leave through -- at least one axis must stay open"
        )
    return layers, mp_module.Vector3()


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

    def __init__(self, meep_module: Any | None = None, python_executable: str | None = None):
        """`meep_module`, if given, replaces the real guarded `import meep
        as mp` -- a test-only injection seam (mirroring HfssSimulator's
        `hfss_factory` constructor-injection pattern, see simulation/
        hfss.py) exercising this module's own geometry/unit-translation and
        flux-subtraction orchestration against a hand-written fake matching
        the subset of Meep's real Python API this module calls (see
        tests/test_meep.py). The real run_meep_simulation()/agent/MCP tool
        wiring never passes it, so a real call always goes through the
        real guarded import.

        `python_executable` (default: the MEEP_PYTHON environment variable,
        else None) names a DIFFERENT Python that has Meep installed. When
        set, the run is delegated to it as a subprocess instead of importing
        Meep here. That is not an optimisation -- it is the only way this
        adapter works in this repo's own container, where the Dockerfile
        installs pymeep into a conda environment and the application runs
        under a separate uv venv (#231). simulation/gprmax.py resolves
        GPRMAX_PYTHON exactly this way."""
        self._meep_module = meep_module
        self._python_executable = python_executable or os.getenv("MEEP_PYTHON")

    def _real_meep_module(self) -> Any:
        return _import_meep()

    def _delegates_to_another_interpreter(self) -> bool:
        """True when Meep lives in a different interpreter from this one.

        An injected `meep_module` always wins (that is the test seam), and
        MEEP_PYTHON pointing at the interpreter already running is not a
        delegation -- it is just a redundant way of naming this one."""
        if self._meep_module is not None or not self._python_executable:
            return False
        try:
            return Path(self._python_executable).resolve() != Path(sys.executable).resolve()
        except OSError:
            # An unresolvable path is still a stated intent to delegate; let
            # the subprocess call fail with the real reason rather than
            # silently importing a Meep the caller did not ask for.
            return True

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

        mp_module = (
            self._meep_module
            if (self._meep_module is not None or self._delegates_to_another_interpreter())
            else self._real_meep_module()
        )
        a_m = float(job.get("characteristic_length_m", _DEFAULT_CHARACTERISTIC_LENGTH_M))
        nfreq = int(job.get("nfreq", 1))

        workdir = Path(job.get("workdir") or tempfile.mkdtemp(prefix="meep_"))
        workdir.mkdir(parents=True, exist_ok=True)

        if self._delegates_to_another_interpreter():
            s_parameters = _run_in_meep_interpreter(
                str(self._python_executable), geometry, a_m, nfreq, job, workdir
            )
        else:
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


_RUNNER_TEMPLATE = '''\
"""Generated by simulation/meep.py -- runs one Meep job under an interpreter
that has Meep installed, and writes the result back as JSON.

Deliberately tiny: it imports the SAME `_run_reflectance_cross_check` the
in-process path uses, so there is exactly one implementation of the physics
and no second copy to drift out of step. simulation/meep.py and
simulation/base.py both import only the standard library, so this works
under a foreign interpreter that has none of the project's dependencies.
"""

import json
import sys

sys.path.insert(0, {repo_root!r})

import meep as mp

from simulation.meep import _run_reflectance_cross_check

with open(sys.argv[1]) as handle:
    payload = json.load(handle)

result = _run_reflectance_cross_check(
    mp, payload["geometry"], payload["a_m"], payload["nfreq"], payload["job"]
)

with open(sys.argv[2], "w") as handle:
    json.dump(result, handle)
'''


def _run_in_meep_interpreter(
    python_executable: str,
    geometry: dict[str, Any],
    a_m: float,
    nfreq: int,
    job: dict[str, Any],
    workdir: Path,
) -> dict[str, Any]:
    """Run one job under a different Python that has Meep installed.

    Why this exists: this repo's Dockerfile installs pymeep into its own
    conda environment and exports MEEP_PYTHON, while the application itself
    runs under a separate uv venv. An in-process `import meep` therefore
    fails inside an image that genuinely has Meep in it (#231).

    The subprocess boundary is also what keeps Meep's GPLv2 at arm's length,
    the same way every other GPL tool in docs/LICENSE_MATRIX.md is invoked
    -- a side benefit, not the reason.

    `job` is filtered to JSON-serialisable entries: `workdir` is passed
    separately and any injected object could not cross the boundary anyway.
    """
    repo_root = str(Path(__file__).resolve().parent.parent)
    runner = workdir / "_meep_runner.py"
    payload_path = workdir / "_meep_job.json"
    result_path = workdir / "_meep_result.json"

    serialisable_job = {
        key: value
        for key, value in job.items()
        if key in ("decay_by", "decay_check_interval", "stop_point_m")
    }
    payload_path.write_text(
        json.dumps({"geometry": geometry, "a_m": a_m, "nfreq": nfreq, "job": serialisable_job})
    )
    runner.write_text(_RUNNER_TEMPLATE.format(repo_root=repo_root))

    timeout_s = int(job.get("timeout_s", 3600))
    try:
        completed = subprocess.run(
            [python_executable, str(runner), str(payload_path), str(result_path)],
            capture_output=True,
            text=True,
            timeout=timeout_s,
            check=False,
        )
    except FileNotFoundError as exc:
        raise SimulatorError(
            f"MEEP_PYTHON points at {python_executable!r}, which does not exist. "
            "It must be a Python interpreter with meep installed -- in this repo's "
            "own image that is /opt/conda/envs/mp/bin/python3."
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise SimulatorError(f"MEEP timed out after {timeout_s}s: {exc}") from exc

    if completed.returncode != 0:
        raise SimulatorError(
            f"MEEP run under {python_executable!r} failed "
            f"({completed.returncode}): {completed.stderr[-4000:]}"
        )
    if not result_path.exists():
        raise SimulatorError(
            f"MEEP run under {python_executable!r} exited 0 but wrote no result to "
            f"{result_path}. stderr tail: {completed.stderr[-2000:]}"
        )
    return json.loads(result_path.read_text())


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
    boundary_layers, k_point = _boundaries_and_k_point(mp_module, geometry, pml_thickness)
    # k_point is only passed when the cell is actually periodic, so a
    # non-periodic run constructs Simulation with exactly the arguments it
    # always did (and the injected fake in tests needs no new kwarg).
    periodic_kwargs = {} if k_point is None else {"k_point": k_point}

    ref_sim = mp_module.Simulation(
        cell_size=cell_size,
        resolution=resolution,
        geometry=_build_geometry_list(
            mp_module, geometry, a_m, include_conductors=False, fcen_meep=fcen
        ),
        sources=[_build_source(mp_module, port, a_m)],
        boundary_layers=boundary_layers,
        **periodic_kwargs,
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
        geometry=_build_geometry_list(
            mp_module, geometry, a_m, include_conductors=True, fcen_meep=fcen
        ),
        sources=[_build_source(mp_module, port, a_m)],
        boundary_layers=boundary_layers,
        **periodic_kwargs,
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
