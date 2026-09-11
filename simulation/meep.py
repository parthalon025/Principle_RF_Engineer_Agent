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
  - Near-to-far-field transform (#270): `sim.add_near2far(fcen, df, nfreq,
    *Near2FarRegion)` and `mp.Near2FarRegion(center=, size=, weight=)`
    ("identical to FluxRegion except for the name", weight of +-1 marking
    each region's outward-normal direction so opposite faces of a closed
    box net to the OUTWARD total): meep.readthedocs.io/en/latest/
    Python_User_Interface/, near2far section, fetched directly during
    implementation. `sim.get_farfield(near2far, x)` -- a METHOD on the
    Simulation instance, not a module-level `mp.get_farfield` (confirmed by
    fetching github.com/NanoComp/meep/blob/master/doc/docs/
    Python_Tutorials/Near_to_Far_Field_Spectra.md directly and reading its
    own worked code, `far_field = sim.get_farfield(n2f_mon, mp.Vector3(...))`)
    -- returns far-field E/H at one point as a flat list of length 6*nfreq
    (Ex,Ey,Ez,Hx,Hy,Hz per frequency, Cartesian coordinates). The Poynting-
    vector cross-product this module's own `_compute_far_field` uses to
    turn those E/H into a radiation intensity (`flux_x = Re(Ey*conj(Hz) -
    Ez*conj(Hy))`, etc.) matches Meep's own `examples/antenna-radiation.py`
    /Near-to-Far-Field-Spectra tutorial, same fetch. Meep's own docs warn
    far fields "cannot be directly compared to time-domain fields" and are
    "easiest to use... where overall scaling... cancel[s] out" -- this
    module's gain_dbi leans on exactly that cancellation (dividing by a
    total radiated power built from the SAME run's ordinary flux monitors),
    which is THIS MODULE'S OWN reasoned application, not something the
    tutorial itself computes end to end -- see FAR_FIELD_VALIDITY.
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

HONEST CAVEAT -- read before trusting any of this end to end. Two separate
questions get confused here, so they are answered separately.

IS MEEP INSTALLED? Not in the interpreter this application normally runs
under: tests/test_meep.py's
test_meep_is_genuinely_not_installed_in_this_environment is a real, failing
`import meep`, not a mock, and CI has no solver at all. There is no PyPI
wheel and no native Windows install path (conda-forge only; WSL on Windows)
-- see the Installation citation above. That is NOT the structural block
HFSS's licensing gate is (simulation/hfss.py): Meep is free software, and
this repo's own Dockerfile installs pymeep into a separate conda
environment, which is exactly why the MEEP_PYTHON/`python_executable`
subprocess delegation exists (#231).

HAS ANY OF THIS BEEN RUN FOR REAL? Partly, and the parts differ:

  - The physics recipe and the SI->Meep conversions below HAVE been run
    against real pymeep 1.34.0 and agree with published/closed-form answers
    -- a free-standing resistive sheet against its exact 0.5 absorptance
    maximum, and a Salisbury screen against rf_tools/absorber.py's
    independent equivalent-circuit model to within 0.001 across 6-14 GHz.
    Recorded in docs/meep-absorber-validation.md, reproducible via
    verification/meep_absorber_validation.py -- which deliberately builds
    its own Meep objects rather than calling this adapter, so the
    validation does not assume the thing it is validating.
  - THIS ADAPTER's own call shapes have been driven end to end under a real
    pymeep 1.34.0 during development -- the periodic/lossy path (#231, the
    "verified" notes in the capability-gap and conversion sections below)
    and the optional transmission monitor (#240, which reproduced the
    closed-form reflectance AND transmittance of a resolved lossy slab to
    within 0.005). Two of those checks ARE now committed as repeatable
    artifacts and drive this adapter's public entry point through the real
    MEEP_PYTHON subprocess handoff: verification/
    meep_adapter_transmittance_check.py (a conductive slab, exact R and T)
    and verification/meep_two_port_absorption_check.py (a free-standing
    sheet, through the loop's two-port sum as well). CI runs neither -- it
    has no solver -- so they are a standing check someone must run, not an
    automatic one.
  - Everything else -- any geometry unlike those cases, and every API
    detail not touched by them -- rests on the primary-source citations
    above and on tests against a hand-written fake matching the subset of
    Meep's Python API this module calls (tests/test_meep.py). Those tests
    prove the adapter says what it means to say to Meep; they cannot prove
    Meep answered correctly.
  - The optional far-field/gain transform (#270) is squarely in that last,
    less-verified bucket: it rests on the primary-source API citations
    above and on tests/test_meep.py's fake, but has NOT been run against a
    real pymeep install the way the reflectance/transmittance recipe has
    -- there is no verification/meep_*.py script for it yet. Treat
    `gain_dbi`/`far_field` as unverified end to end until one exists; see
    FAR_FIELD_VALIDITY for the specific assumption this rests on.

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
  - S-parameters: POWER quantities only. Power reflectance (|S11|^2, via
    the officially-documented flux-subtraction technique cited above) and
    its square root (`s11_magnitude`, a real, non-negative |S11|) are
    always computed. Power TRANSMITTANCE -- the share of the arriving
    power that goes straight through and out the far side -- is computed
    TOO, but only when the caller asks for it by naming a
    `transmission_monitor_center_m` in `geometry` (#240); without that key
    no transmission monitor is built and the result says so explicitly
    rather than reporting a silent zero. Still NO complex phase, so no
    complex S21 and no multi-port S-matrix, and NO Touchstone export
    (Touchstone requires complex per-frequency S-data, which this pass
    does not produce) -- unlike openems.py's/hfss.py's computed=True
    complex S-parameters. A caller cross-checking against openEMS's
    complex S11 can only compare |S11| magnitude against this module's
    `s11_magnitude`, not phase. And this module does NOT compute
    absorption: `1 - R - T` is a reading of these numbers, not a
    measurement, and belongs to the caller that knows both were measured
    on the same structure (issue #243).
  - THE "REFERENCE RUN" DESIGN CHOICE: this module's reflectance baseline
    is established by running the SAME source/cell/PML/materials/port-
    monitors but WITH the `conductors` geometry list omitted (i.e. the
    dielectric/background structure alone, without the metal structure
    under test) as the "canonical" run the tutorial's own straight-
    waveguide plays -- this is THIS MODULE'S OWN reasoned adaptation of
    the officially-documented straight-vs-bent-waveguide reflectance
    technique to an antenna-style single-port cross-check, NOT a
    documented Meep convention for antenna S11 extraction specifically.
    Flagged explicitly rather than presented as a verified fact. The
    optional transmittance is normalized the same way, against the forward
    flux this same conductor-free reference run delivers to the
    TRANSMISSION plane -- so both numbers are "relative to the structure
    without its conductors", not relative to empty vacuum. On a
    conductors-only geometry the two are the same thing; with a thick
    lossy substrate they are not, and the difference is the substrate's
    own loss.
  - Far-field/gain: OPTIONAL, via Meep's own near-to-far-field transform
    (#270) -- ask for it by naming a `far_field_monitor` in `geometry`
    (`enclosing_regions`, a closed box of Near2FarRegion-equivalent planes
    around the source and structure, plus `directions`, the far-field
    points to report gain at); leave it out and `far_field` still always
    carries `computed=False` and an explanatory note (structural parity
    with nec2pp.py's/openems.py's own result shape, so downstream code can
    treat every simulator's result uniformly), same three-state discipline
    as the optional transmission monitor above. `sim.add_near2far`/`mp.
    Near2FarRegion` build the monitor on the FULL run (conductors present
    -- gain describes the real structure, not the conductor-free
    baseline); `sim.get_farfield` projects the recorded near fields out to
    each requested direction, and `gain_dbi = 10*log10(4*pi*U/P_rad)`
    combines the resulting radiation intensity with total radiated power
    read from ordinary flux monitors on that SAME enclosing surface. This
    is genuinely less battle-tested than the reflectance/transmittance
    recipe above: it has NOT been run against real pymeep the way that one
    has (docs/meep-absorber-validation.md) -- see `_compute_far_field`'s
    own docstring and this result's own `validity` entries for what
    remains a reasoned assumption (the near2far/flux normalization match)
    rather than a verified fact, and for the peak-of-requested-directions-
    only caveat (not a full-sphere scan).
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
from enum import StrEnum
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


class GeometryRole(StrEnum):
    """The physical-layer-role vocabulary a materials/conductors primitive's
    optional `role` field is validated against (issue #485). This module is
    the single source of truth for the five values -- named and cased the
    same way `designs/requirement_targets.py`'s `TargetComparator`/
    `TargetStatus` are (a `StrEnum`, member name equal to its value), the
    closed-vocabulary convention already established elsewhere in this
    codebase.

    CONTEXT.md's domain glossary already distinguishes a design's **Host
    surface** from its **Substrate** ("a skin has both a substrate and a
    host"), and docs/adr/0033 records a real stack as a table -- a
    resonant+lossy PATTERN layer on top, a SPACER in the middle, an
    unpatterned REFLECTOR on the bottom. None of that was representable on
    a geometry primitive before this; `role` is purely additive metadata
    that says which of those five physical jobs one primitive is playing.

    - `HOST`: the surface the whole skin mounts on (CONTEXT.md's Host
      surface) -- present in a geometry only when the host itself needs to
      be modelled (e.g. to represent an asserted conductive backing), not a
      universal layer.
    - `SUBSTRATE`: the antenna's own dielectric carrier (CONTEXT.md's
      Substrate) -- distinct from the host per that entry's own _Avoid_
      line.
    - `REFLECTOR`: the ground-plane/mirror layer -- at most ONE primitive
      across a geometry's combined materials+conductors may carry this role
      (`_build_geometry_list` enforces the cap); a design has one reflector
      by construction.
    - `SPACER`: the dielectric standoff between the reflector and the
      radiating pattern (docs/adr/0033's middle table row).
    - `PATTERN`: the radiating/resonant printed layer -- UNLIKE `REFLECTOR`,
      any number of primitives may carry this role: docs/adr/0033's own
      absorber design coplanar-prints two different-function inks (silver
      resonant plates, a carbon lossy bridge) in one pattern layer, and a
      design may legitimately carry more than one patterned/resonant layer.

    Deliberately NOT attached to `Medium`/conductor construction anywhere:
    `role` is pure metadata for a human or downstream tool to read, and must
    never change what `_primitive_to_meep`/`_conductor_medium` actually
    builds (issue #485's own point 6) -- an identically-shaped primitive
    tagged `REFLECTOR` and one left untagged must simulate byte-for-byte the
    same object.
    """

    HOST = "HOST"
    SUBSTRATE = "SUBSTRATE"
    REFLECTOR = "REFLECTOR"
    SPACER = "SPACER"
    PATTERN = "PATTERN"


def _validate_role(role: Any) -> "GeometryRole | None":
    """Validate one primitive's optional `role` field against
    `GeometryRole` -- issue #485's rule 1. `None` (the field absent, or
    explicitly `None`) is always legal and returns `None` unchanged: role is
    purely additive, so a primitive that never mentions it must stay exactly
    as legal as it always was. Anything else must name one of the five
    `GeometryRole` values, or this raises `ValueError` naming what was given
    -- `_build_geometry_list` wraps this in its own `materials[{idx}]:`/
    `conductors[{idx}]:` context, matching that function's existing
    shape/required-field error style."""
    if role is None:
        return None
    try:
        return GeometryRole(role)
    except ValueError:
        legal = ", ".join(r.value for r in GeometryRole)
        raise ValueError(f"role must be one of {legal}, got {role!r}") from None


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
#
# A fourth limit was never on this list, because a GROUND-BACKED absorber
# does not have it: with metal behind the cell nothing passes through, so
# "how much got through" is structurally zero and how much was absorbed is
# just 1 - R. An absorber with free space behind it is a different problem
# -- there, some power leaves out the back, and calling everything that did
# not come back "absorbed" would flatter the design. #240 gives this adapter
# an OPTIONAL transmission monitor for exactly that case
# (`transmission_monitor_center_m`; see the SCOPE section). It stays
# optional because measuring a structural zero costs solver time for
# nothing, and the arithmetic that combines the two (A = 1 - R - T) is
# deliberately NOT done here -- see #243.
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


# What remains APPROXIMATE about the optional far-field/gain transform
# (#270), same warn-never-block discipline as PERIODIC_ABSORBER_VALIDITY
# above. Rides alongside every far_field result that DID compute, rather
# than blocking one.
FAR_FIELD_VALIDITY: tuple[dict[str, str], ...] = (
    {
        "flag": "gain_is_peak_of_requested_directions_only",
        "assumed": (
            "outputs['gain_dbi'] is the largest value found among the "
            "caller's own 'directions' entries -- not a full-sphere scan"
        ),
        "costs": (
            "a real antenna's true peak gain can sit in a direction nobody "
            "asked about; a coarse or one-sided set of directions can under- "
            "or over-state the antenna's actual peak"
        ),
        "cheapest_test": (
            "add more directions (a denser angular sweep) and confirm the "
            "reported peak stops moving"
        ),
    },
    {
        "flag": "near2far_scale_matches_flux_monitors_by_assumption",
        "assumed": (
            "the total radiated power (from ordinary flux monitors, "
            "mp.get_fluxes) and the far-field intensity (from sim."
            "get_farfield's E/H) share the same absolute scale, so their "
            "ratio in gain_dbi's 4*pi*U/P_rad is meaningful -- reasoned from "
            "Meep's own documented near2far/flux internals (both derive "
            "from the same per-run DFT field accumulation), NOT "
            "independently reproduced against a real pymeep run the way "
            "the reflectance/transmittance recipe was "
            "(docs/meep-absorber-validation.md)"
        ),
        "costs": (
            "if that assumption is wrong, gain_dbi is off by a fixed "
            "multiplicative factor (an additive dB offset) at every "
            "direction and frequency -- the SHAPE of the radiation pattern "
            "across directions would still be trustworthy even if the "
            "absolute number were not"
        ),
        "cheapest_test": (
            "run one known case (e.g. a resonant half-wave dipole, textbook "
            "gain 2.15 dBi) through a real pymeep install and compare"
        ),
    },
    {
        "flag": "periodic_far_field_uses_a_finite_transform",
        "assumed": (
            "when geometry['periodic_axes'] is also set, the near2far "
            "transform is still built with Meep's default nperiods=1 (no "
            "lattice summation across the infinite array Bloch boundaries "
            "imply)"
        ),
        "costs": (
            "a periodic unit cell's true far field is an array pattern, not "
            "a single element's; nperiods=1 answers 'what would one element "
            "radiate in isolation', which is a different, usually smaller, "
            "number"
        ),
        "cheapest_test": (
            "Meep documents an nperiods argument on add_near2far specifically "
            "for this case; wiring it through is future work, not done here"
        ),
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
#     Meep returns A = 0.4999 there, and puts the maximum at exactly that
#     Rs. (That is the 80 px/mm, 0.2 mm sweep; the committed runner uses a
#     coarser mesh and returns 0.4971. Both pass, and both are quoted in
#     the document -- the difference is the sheet's own discretisation.)
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
    design-choice caveat.

    Also validates each primitive's optional `role` (issue #485,
    `GeometryRole`) and enforces its one cross-cutting rule -- at most one
    `REFLECTOR` across this call's combined materials+conductors -- entirely
    as metadata bookkeeping alongside the existing per-primitive build.
    `role` is never read by `_primitive_to_meep`/`_conductor_medium` and
    never changes the `Medium`/conductor object either function returns
    (issue #485 point 6)."""
    objects: list[Any] = []
    reflector_locations: list[str] = []
    for idx, mat in enumerate(geometry.get("materials", [])):
        try:
            if _validate_role(mat.get("role")) is GeometryRole.REFLECTOR:
                reflector_locations.append(f"materials[{idx}]")
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
                if _validate_role(cond.get("role")) is GeometryRole.REFLECTOR:
                    reflector_locations.append(f"conductors[{idx}]")
                medium = _conductor_medium(mp_module, cond, a_m)
                objects.append(_primitive_to_meep(mp_module, cond, a_m, medium))
            except ValueError as exc:
                raise ValueError(f"conductors[{idx}]: {exc}") from exc
    if len(reflector_locations) > 1:
        raise ValueError(
            f"at most one primitive may carry role={GeometryRole.REFLECTOR.value!r} "
            f"across materials+conductors combined -- a design has one reflector by "
            f"construction; got {len(reflector_locations)}: {reflector_locations}"
        )
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


def _validate_far_field_monitor(far_field_monitor: dict[str, Any]) -> None:
    """Nested-within-geometry field validation -> ValueError, matching
    _validate_port's own convention above (SimulatorError is reserved for
    job-dict-top-level required keys, checked directly in
    MeepSimulator.run()).

    geometry['far_field_monitor'] (#270) is optional at the top level --
    absent, no near2far monitor is built and nothing else here runs. Present,
    it needs a CLOSED surface ('enclosing_regions', at least one region) to
    read total radiated power from and at least one 'directions' point to
    project the far field at -- a near-to-far-field transform with nothing
    enclosed or nowhere to look is not a request for anything. Each
    direction's own 'point_m' also has to be off the coordinate origin (no
    radius to project the transform out to) -- caught here, up front, same
    as every other structural defect in this dict, so a malformed request
    fails before the FDTD run it would otherwise pay for, not after."""
    required = ("enclosing_regions", "directions")
    missing = [f for f in required if f not in far_field_monitor]
    if missing:
        raise ValueError(f"geometry['far_field_monitor'] missing required field(s): {missing}")

    regions = far_field_monitor["enclosing_regions"]
    if not regions:
        raise ValueError(
            "geometry['far_field_monitor']['enclosing_regions'] must not be empty -- "
            "a near-to-far-field transform needs a closed surface enclosing the "
            "source and the structure under test to read total radiated power from"
        )
    for idx, region in enumerate(regions):
        missing_region = [f for f in ("center_m", "size_m") if f not in region]
        if missing_region:
            raise ValueError(
                f"geometry['far_field_monitor']['enclosing_regions'][{idx}] missing "
                f"required field(s): {missing_region}"
            )

    directions = far_field_monitor["directions"]
    if not directions:
        raise ValueError(
            "geometry['far_field_monitor']['directions'] must not be empty -- name at "
            "least one far-field point to project the near2far transform onto and "
            "report gain at"
        )
    for idx, direction in enumerate(directions):
        if "point_m" not in direction:
            raise ValueError(
                f"geometry['far_field_monitor']['directions'][{idx}] missing "
                "required field(s): ['point_m']"
            )
        point_m = direction["point_m"]
        if math.sqrt(sum(c * c for c in point_m)) == 0:
            raise ValueError(
                "geometry['far_field_monitor']['directions'] point_m must not be "
                "the coordinate origin -- a far-field direction needs a radius to "
                "project the near2far transform out to"
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
            "complex phase, and so no complex S21 and no multi-port "
            "S-matrix, no Touchstone export (see module docstring SCOPE "
            "section). Suitable for comparing against the magnitude of "
            "openEMS's/HFSS's own complex S11, not a full complex "
            "cross-check. How much power goes THROUGH the structure is a "
            "separate, optional measurement -- see this result's own "
            "'transmittance' entry, which says whether it was asked for."
        ),
    }


def _transmittance_not_requested() -> dict[str, Any]:
    """The "nobody asked" state -- said out loud, never left blank.

    Transmittance is the share of the arriving power that goes STRAIGHT
    THROUGH the surface and carries on out the far side (as opposed to
    reflectance, the share that bounces back). Measuring it costs a second
    monitor plane in both runs, and for a ground-backed surface -- one with
    metal behind it -- the answer is structurally zero, so it is opt-in.

    Three states have to stay apart, and the middle one is why a bare `None`
    or a bare `0.0` will not do:

      * not requested          -> computed False, requested False (here)
      * requested, uncomputable-> computed False, requested True  (below)
      * measured, maybe zero   -> computed True, with the numbers

    A measured zero and an unmeasured silence look identical if the absence
    is left implicit -- the same failure `designs/design_families.py` guards
    against with `UnreadPhysicalBound` vs `NO_PHYSICAL_BOUND` ("a silent
    `None` would have made 'we never looked' indistinguishable from 'there
    is nothing to look for'").
    """
    return {
        "computed": False,
        "requested": False,
        "note": (
            "No transmission monitor was requested, so how much power passes "
            "THROUGH this structure was never measured -- this is silence, "
            "not a measured zero. Ask for it by giving geometry a "
            "'transmission_monitor_center_m' (a plane on the far side of the "
            "structure from the source). Leaving it out is the right choice "
            "for a ground-backed surface, where nothing gets through by "
            "construction and measuring it would only cost solver time."
        ),
    }


def _compute_transmittance(
    frequency_hz_points: list[float],
    transmitted_flux: list[float],
    incident_forward_flux: list[float],
) -> dict[str, Any]:
    """Power transmittance at the requested monitor plane.

        transmittance = transmitted_flux / incident_forward_flux

    Both fluxes are read at the SAME plane: the numerator from the full run
    (structure present), the denominator from the reference run at that same
    plane, which is what the wave delivered there with the conductors
    absent. Normalising against the reflection monitor's own baseline
    instead would be wrong -- that baseline belongs to a different plane
    (`reference_monitor_center_m`), and the two only coincide by accident.
    `verification/meep_absorber_validation.py`'s `_reflectance_1d` is the
    reference implementation of this recipe.

    NOTE the reference run here is materials-only, NOT empty vacuum (see the
    module docstring's REFERENCE RUN design-choice caveat) -- so this number
    is transmittance RELATIVE TO the same structure without its conductors,
    exactly as reflectance already is. On a bare dielectric that is the
    familiar absolute transmittance; with a thick lossy substrate it is not,
    and the difference is the substrate's own loss.

    Unlike the reflected wave, the transmitted one needs no field
    subtraction: nothing of the source's own outgoing pulse is cancelled at
    a plane BEHIND the structure, so the total forward flux there already is
    what got through.
    """
    if not incident_forward_flux or any(b == 0 for b in incident_forward_flux):
        return {
            "computed": False,
            "requested": True,
            "note": (
                "A transmission monitor was requested, but the reference "
                "run's forward-flux spectrum at that same plane is empty or "
                "contains a zero -- there is nothing to normalize the "
                "transmitted power against, so no transmittance is reported "
                "(this is a failed measurement, not a measured zero). Check "
                "that 'transmission_monitor_center_m' sits inside the cell, "
                "clear of the PML, and on the far side of the structure from "
                "the source, so the reference run's wave actually crosses it."
            ),
        }
    transmittance = [t / b for t, b in zip(transmitted_flux, incident_forward_flux, strict=True)]
    return {
        "computed": True,
        "requested": True,
        "method": (
            "Power transmittance via the same documented flux machinery as "
            "reflectance (sim.add_flux/FluxRegion, mp.get_fluxes): "
            "transmittance = full-run forward flux at "
            "geometry['transmission_monitor_center_m'] / reference-run "
            "forward flux at that SAME plane. No load_minus_flux_data is "
            "applied there -- behind the structure the total forward flux "
            "already is the transmitted wave. Matches the recipe in "
            "verification/meep_absorber_validation.py's _reflectance_1d."
        ),
        "frequency_hz": frequency_hz_points,
        "transmittance": transmittance,
        "note": (
            "Power transmittance ONLY -- the fraction of arriving power that "
            "passes through, with no complex phase and so no complex S21 "
            "(see the module docstring's SCOPE section). Normalized against "
            "this module's own reference run (materials present, conductors "
            "omitted), so it is transmittance relative to that structure, "
            "not against empty vacuum. This module deliberately does NOT "
            "compute absorption: A = 1 - R - T belongs to whoever knows "
            "these two numbers were measured on the same structure at the "
            "same frequencies, and an adapter reports what it measured, not "
            "what it means."
        ),
    }


# ---------------------------------------------------------------------------
# Far-field / gain (#270) -- Meep's own documented near-to-far-field
# transform, opt-in via geometry['far_field_monitor'], same "give it and the
# extra work happens, leave it out and nothing changes" shape #240's
# transmission_monitor_center_m established for the analogous second-monitor
# case. See module docstring citations for add_near2far/Near2FarRegion/
# get_farfield's real API shapes (all fetched directly from meep.
# readthedocs.io/en/latest/Python_User_Interface/ and the Near-to-Far-Field-
# Spectra tutorial during implementation).
# ---------------------------------------------------------------------------


def _region_weight(region: dict[str, Any]) -> float:
    """A far_field_monitor['enclosing_regions'] entry's own 'weight' (+-1,
    default 1.0) -- shared by _add_near2far_monitor (building each
    Near2FarRegion) and _compute_far_field (signing that same region's flux
    into radiated_power) so the default and its coercion live in one place,
    matching real Meep's own Near2FarRegion default."""
    return float(region.get("weight", 1.0))


def _add_near2far_monitor(
    mp_module: Any,
    sim: Any,
    fcen: float,
    fwidth: float,
    nfreq: int,
    regions: list[dict[str, Any]],
    a_m: float,
) -> Any:
    """sim.add_near2far(fcen, df, nfreq, *Near2FarRegion) -- built on the
    FULL run only (conductors present): gain describes the actual radiating
    structure, not the conductor-free reference baseline the reflectance/
    transmittance recipe uses for normalization. There is no "gain of the
    empty background" concept to normalize against here."""
    near2far_regions = [
        mp_module.Near2FarRegion(
            center=_vector3(mp_module, region["center_m"], a_m),
            size=_vector3(mp_module, region["size_m"], a_m),
            weight=_region_weight(region),
        )
        for region in regions
    ]
    return sim.add_near2far(fcen, fwidth, nfreq, *near2far_regions)


def _far_field_not_requested() -> dict[str, Any]:
    """The "nobody asked" state -- said out loud, never left blank. Same
    three-state discipline _transmittance_not_requested() already documents
    for the analogous optional-second-monitor shape:

      * not requested           -> computed False, requested False (here)
      * requested, uncomputable -> computed False, requested True  (below)
      * measured, maybe a null  -> computed True, with the numbers (a real
            radiation-pattern null in one direction is a genuine answer)
    """
    return {
        "computed": False,
        "requested": False,
        "note": (
            "No far-field monitor was requested, so this structure's "
            "radiation pattern and antenna gain were never measured -- this "
            "is silence, not a measured value. Ask for it by giving "
            "geometry a 'far_field_monitor' dict with 'enclosing_regions' "
            "(a closed box of Near2FarRegion-equivalent planes around the "
            "source and structure) and 'directions' (far-field points, in "
            "meters, to report gain at)."
        ),
    }


def _compute_far_field(
    frequency_hz_points: list[float],
    enclosing_regions: list[dict[str, Any]],
    region_fluxes: list[list[float]],
    directions: list[dict[str, Any]],
    direction_fields: list[list[complex]],
    a_m: float,
) -> dict[str, Any]:
    """Pure function: turns already-fetched Meep data (flux spectra, raw
    far-field E/H) into a far_field result -- no mp_module/sim access here,
    per this repo's "caller fetches, pure function resolves" convention
    (CLAUDE.md; designs/element_alphabet.py and designs/material_
    properties.py are the clearest existing examples).

    RADIATED POWER: sum over enclosing_regions of weight * mp.get_fluxes(...)
    at that region -- Near2FarRegion "is identical to FluxRegion except for
    the name" (module docstring citation), and Meep's own near-to-far-field
    tutorial computes total radiated power BOTH this way (a near-field flux
    box) and by integrating the far field over a full sphere specifically to
    demonstrate the two agree -- so this reads the cheaper one. Each
    region's own weight (+1/-1, the caller's responsibility, same as real
    Meep) is what makes opposite faces of a closed box net to the OUTWARD
    total instead of cancelling to zero.

    GAIN AT ONE DIRECTION: gain_dbi = 10*log10(4*pi*U/P_rad), where
    U = r**2 * S_r is the radiation intensity (power per solid angle,
    Balanis-style antenna-gain definition) and S_r is the radial component
    of the time-averaged Poynting vector, 0.5*Re(E x conj(H)) -- the same
    cross-product Meep's own antenna-radiation-pattern example computes
    (flux_x = Re(Ey*conj(Hz) - Ez*conj(Hy)) etc., fetched during
    implementation), with the textbook leading 0.5 restored (that example
    only normalizes its pattern by its own peak, so an overall factor never
    mattered to it; it matters here because gain_dbi divides by a
    SEPARATELY-scaled quantity, P_rad).

    r MUST be in MEEP's own dimensionless distance units (point_m / a_m),
    NOT raw meters: the far field decays as 1/r in Meep's own coordinate
    system, so r**2*S_r is r-independent (the defining property of a correct
    radiation intensity) only when r matches the units S_r was computed in.
    Using meters instead would leak the caller's arbitrary
    characteristic_length_m choice into gain_dbi as a spurious a_m**2 factor
    inside the logarithm -- exactly the kind of modeling-choice leak this
    module's unit conversions are designed to avoid everywhere else.

    See FAR_FIELD_VALIDITY for what remains an assumption rather than a
    verified fact (this recipe has NOT been run against real pymeep the way
    the reflectance/transmittance one has -- docs/meep-absorber-
    validation.md)."""
    num_freqs = len(frequency_hz_points)
    radiated_power = [0.0] * num_freqs
    for region, flux in zip(enclosing_regions, region_fluxes, strict=True):
        weight = _region_weight(region)
        for i, value in enumerate(flux):
            radiated_power[i] += weight * value

    if not radiated_power or any(p <= 0 for p in radiated_power):
        return {
            "computed": False,
            "requested": True,
            "note": (
                "the enclosing surface's own net outward flux -- the "
                "denominator gain is measured against -- was zero or "
                "negative at at least one frequency, so no gain can be "
                "reported there (this is a failed measurement, not a "
                "measured zero). Check that 'enclosing_regions' truly forms "
                "a CLOSED box around the source and structure with "
                "outward-facing 'weight's (+1 on faces whose normal points "
                "away from the enclosed volume, -1 on the opposite ones) -- "
                "the same convention Meep's own Near2FarRegion uses."
            ),
        }

    direction_results: list[dict[str, Any]] = []
    for direction, fields in zip(directions, direction_fields, strict=True):
        # point_m off the coordinate origin is a precondition checked by
        # _validate_far_field_monitor before this pure function ever runs
        # (same trust boundary as the other 'directions'/'enclosing_regions'
        # structural checks it owns) -- not re-checked here.
        point_m = direction["point_m"]
        r_m = math.sqrt(sum(c * c for c in point_m))
        r_hat = [c / r_m for c in point_m]
        r_meep = _m_to_meep(r_m, a_m)  # see docstring: MUST be meep units, not meters

        gains: list[float | None] = []
        for f_idx in range(num_freqs):
            ex, ey, ez, hx, hy, hz = fields[6 * f_idx : 6 * f_idx + 6]
            sx = 0.5 * (ey * hz.conjugate() - ez * hy.conjugate()).real
            sy = 0.5 * (ez * hx.conjugate() - ex * hz.conjugate()).real
            sz = 0.5 * (ex * hy.conjugate() - ey * hx.conjugate()).real
            s_r = sx * r_hat[0] + sy * r_hat[1] + sz * r_hat[2]
            u = (r_meep**2) * s_r
            p_rad = radiated_power[f_idx]
            gains.append(None if u <= 0 else 10.0 * math.log10(4.0 * math.pi * u / p_rad))
        direction_results.append(
            {"label": direction.get("label"), "point_m": list(point_m), "gain_dbi": gains}
        )

    return {
        "computed": True,
        "requested": True,
        "method": (
            "Near-to-far-field gain via Meep's own documented near2far "
            "machinery: sim.add_near2far/mp.Near2FarRegion builds the "
            "monitor on the full run, sim.get_farfield projects the "
            "recorded near fields out to each requested direction, and "
            "gain_dbi = 10*log10(4*pi*U/P_rad) combines that with total "
            "radiated power read from ordinary flux monitors on the SAME "
            "enclosing surface (mp.get_fluxes, signed by each region's own "
            "weight). See simulation/meep.py's module docstring for the "
            "full citation and this result's own 'validity' entries."
        ),
        "frequency_hz": frequency_hz_points,
        "radiated_power": radiated_power,
        "directions": direction_results,
        "validity": [dict(flag) for flag in FAR_FIELD_VALIDITY],
        "note": (
            "gain_dbi at each direction/frequency is the antenna gain in "
            "dBi AT THAT ONE caller-chosen direction (decibels relative to "
            "a hypothetical isotropic radiator -- one that spreads its "
            "power equally in every direction) -- a null (None) at some "
            "direction/frequency means the far field genuinely radiated "
            "nothing measurable that way, not that the measurement failed. "
            "outputs['gain_dbi'] at the top level is the MAXIMUM of every "
            "computed value here -- see 'validity' for why that is a peak "
            "among the requested directions only, not a full-sphere scan."
        ),
    }


def _peak_gain_dbi(far_field_result: dict[str, Any]) -> float | None:
    """The single headline number outputs['gain_dbi'] carries: the largest
    gain found among every requested direction/frequency, or None when
    far_field was never requested or came back uncomputable (see
    _compute_far_field's own docstring for why this is a peak among
    REQUESTED directions, not a full-sphere scan)."""
    if not far_field_result.get("computed"):
        return None
    values = [
        gain
        for direction in far_field_result["directions"]
        for gain in direction["gain_dbi"]
        if gain is not None
    ]
    return max(values) if values else None


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
        far_field_monitor = geometry.get("far_field_monitor")
        if far_field_monitor is not None:
            _validate_far_field_monitor(far_field_monitor)

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
            result = _run_in_meep_interpreter(
                str(self._python_executable), geometry, a_m, nfreq, job, workdir
            )
        else:
            result = _run_reflectance_cross_check(mp_module, geometry, a_m, nfreq, job)

        return SimulationResult(
            simulator=self.name,
            status="COMPLETED",
            workdir=workdir,
            outputs={
                "s_parameters": result["s_parameters"],
                "far_field": result["far_field"],
                "gain_dbi": result["gain_dbi"],
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
    # Optional third monitor (#240): the forward flux this same reference run
    # delivers to the TRANSMISSION plane, which is what the full run's flux
    # there has to be divided by. Absent when no transmission plane was
    # asked for, so a run that does not want transmittance builds exactly the
    # Simulation and monitors it always did -- and a ground-backed cell, whose
    # transmission is structurally zero, pays nothing to learn that.
    transmission_center_m = geometry.get("transmission_monitor_center_m")
    incident_forward_monitor = (
        None
        if transmission_center_m is None
        else _add_flux_monitor(
            mp_module, ref_sim, fcen, fwidth, nfreq, transmission_center_m, monitor_size_m, a_m
        )
    )
    _run_until_decayed(
        mp_module, ref_sim, component_name, stop_point_m, a_m, decay_by, check_interval
    )
    saved_refl_data = ref_sim.get_flux_data(refl_flux_ref)
    baseline_flux = mp_module.get_fluxes(baseline_flux_monitor)
    incident_forward_flux = (
        None if incident_forward_monitor is None else mp_module.get_fluxes(incident_forward_monitor)
    )
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
    transmission_monitor = (
        None
        if transmission_center_m is None
        else _add_flux_monitor(
            mp_module, full_sim, fcen, fwidth, nfreq, transmission_center_m, monitor_size_m, a_m
        )
    )
    # Optional far-field monitor (#270): built on the FULL run only, since
    # gain describes the actual radiating structure, not the conductor-free
    # reference baseline. Absent geometry['far_field_monitor'], nothing here
    # runs and the full run builds exactly the monitors it always did.
    far_field_monitor = geometry.get("far_field_monitor")
    near2far_monitor = None
    radiated_power_monitors: list[Any] = []
    if far_field_monitor is not None:
        near2far_monitor = _add_near2far_monitor(
            mp_module, full_sim, fcen, fwidth, nfreq, far_field_monitor["enclosing_regions"], a_m
        )
        radiated_power_monitors = [
            _add_flux_monitor(
                mp_module, full_sim, fcen, fwidth, nfreq, region["center_m"], region["size_m"], a_m
            )
            for region in far_field_monitor["enclosing_regions"]
        ]
    # Only the REFLECTION monitor gets the reference fields subtracted. That
    # subtraction is what cancels the source's own outgoing pulse so the
    # remainder is the reflected wave; applied behind the structure it would
    # cancel the very thing being measured.
    full_sim.load_minus_flux_data(refl_flux_full, saved_refl_data)
    _run_until_decayed(
        mp_module, full_sim, component_name, stop_point_m, a_m, decay_by, check_interval
    )
    reflected_flux = mp_module.get_fluxes(refl_flux_full)
    transmitted_flux = (
        None if transmission_monitor is None else mp_module.get_fluxes(transmission_monitor)
    )
    # Near2far/flux data must be pulled out before reset_meep() discards it,
    # same as every other monitor above -- but the actual Poynting-vector/
    # gain arithmetic is pure and happens below, after the reset, per this
    # repo's "caller fetches, pure function resolves" convention.
    region_fluxes = (
        None
        if far_field_monitor is None
        else [mp_module.get_fluxes(monitor) for monitor in radiated_power_monitors]
    )
    direction_fields = (
        None
        if far_field_monitor is None
        else [
            full_sim.get_farfield(near2far_monitor, _vector3(mp_module, direction["point_m"], a_m))
            for direction in far_field_monitor["directions"]
        ]
    )
    full_sim.reset_meep()

    frequency_hz_points = [_meep_freq_to_hz(f, a_m) for f in flux_freqs_meep]
    s_parameters = _compute_reflectance(frequency_hz_points, reflected_flux, baseline_flux)
    # Always present, in every branch: a reader must be able to ask "what
    # about transmission?" and get an answer, even when reflectance itself
    # could not be computed.
    s_parameters["transmittance"] = (
        _transmittance_not_requested()
        if transmitted_flux is None or incident_forward_flux is None
        else _compute_transmittance(frequency_hz_points, transmitted_flux, incident_forward_flux)
    )

    far_field_result = (
        _far_field_not_requested()
        if far_field_monitor is None
        else _compute_far_field(
            frequency_hz_points,
            far_field_monitor["enclosing_regions"],
            region_fluxes,
            far_field_monitor["directions"],
            direction_fields,
            a_m,
        )
    )
    return {
        "s_parameters": s_parameters,
        "far_field": far_field_result,
        "gain_dbi": _peak_gain_dbi(far_field_result),
    }


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
               1.0), "mue_r": float (default 1.0), "loss_tangent": float
               (optional, #230 -- how lossy the dielectric is, pinned at
               the band-centre frequency)}, ...
          ],
          "conductors": [                  # optional; ideal PEC (mp.metal)
              same shape as materials, minus epsilon_r/mue_r -- but a
              conductor may instead state "conductivity_s_m", or
              "sheet_resistance_ohm_sq" with its own "thickness_m" (#230),
              which is what a PRINTED resistive layer actually is. Stating
              neither leaves it an ideal, lossless perfect conductor, which
              is right for a ground plane and wrong for anything meant to
              absorb.
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
          "transmission_monitor_center_m": [x,y,z],  # OPTIONAL (#240) -- a
              plane on the far side of the structure from the source. Give
              it and the result also reports power transmittance (how much
              of the arriving power went straight through and out the
              back); leave it out and no transmission monitor is built at
              all. Leaving it out is right for a ground-backed surface,
              where nothing gets through by construction.
          "far_field_monitor": {              # OPTIONAL (#270) -- ask for
              antenna gain/radiation-pattern via Meep's own near-to-far-
              field transform. Leave it out and no near2far monitor is
              built at all (no extra solver cost).
              "enclosing_regions": [           # required if given: a
                  {"center_m": [x,y,z], "size_m": [x,y,z],
                   "weight": 1.0 (default, +-1)},  # CLOSED box of planes
                  ...                          # around the source AND the
              ],                               # structure -- opposite faces
                                                # need opposite 'weight' so
                                                # their net flux is the
                                                # OUTWARD total (this is
                                                # THE caller's own
                                                # responsibility, same as
                                                # real Meep's Near2FarRegion).
              "directions": [                  # required if given: far-
                  {"point_m": [x,y,z],          # field points (meters, same
                   "label": str (optional)},    # coordinate space as
                  ...                           # everything else here) to
              ],                                # project the field to and
                                                 # report gain at. Should be
                                                 # far from the structure;
                                                 # this module does not
                                                 # check that.
          },
        }

    Result: `s_parameters` carries reflectance/s11_magnitude as it always
    did, plus a `transmittance` entry that is ALWAYS present and says which
    of three things happened -- never a bare None and never a bare 0.0:

        {"computed": False, "requested": False, "note": ...}  # nobody asked
        {"computed": False, "requested": True,  "note": ...}  # asked, but
            #   there was no forward flux to normalize against
        {"computed": True,  "requested": True,  "transmittance": [...],
         "frequency_hz": [...], "method": ..., "note": ...}   # measured,
            #   possibly measured as (near) zero, which is a real answer

    Absorption is deliberately NOT computed here: `1 - R - T` is a reading
    of two measurements, and this adapter reports what it measured, not
    what it means (issue #243).

    `far_field` (#270) follows the exact same three-state shape, keyed off
    `far_field_monitor` instead:

        {"computed": False, "requested": False, "note": ...}  # nobody asked
        {"computed": False, "requested": True,  "note": ...}  # asked, but
            #   the enclosing surface's own net radiated power was <= 0
        {"computed": True, "requested": True, "frequency_hz": [...],
         "radiated_power": [...], "directions": [{"label": ..., "point_m":
         [...], "gain_dbi": [...]}, ...], "validity": [...], "note": ...}

    `gain_dbi` at the top level is the single largest value found across
    every requested direction/frequency (None when far_field was not
    requested or came back uncomputable) -- see FAR_FIELD_VALIDITY (module-
    level) for what this number does and does not cover: it is a peak
    among the CALLER'S OWN requested directions, not a full-sphere scan,
    and its absolute scale rests on a reasoned (not independently pymeep-
    verified) assumption that Meep's near2far and flux machinery share one
    normalization -- see `_compute_far_field`'s own docstring for the
    physics and unit-conversion reasoning.

    See this module's header comment for the format-verification citations
    (Meep's own dimensionless unit system and Python API) and its honest
    caveat/SCOPE sections. In short: POWER quantities only -- |S11|
    magnitude and, on request, power transmittance, with no phase and so no
    complex S21. The physics recipe and unit conversions have been checked
    against real pymeep 1.34.0 on two reference cases with known answers
    (docs/meep-absorber-validation.md), and THIS adapter's own path -- deck
    emission, subprocess handoff and result parsing -- is checked against a
    conductive slab whose R and T are both exactly known, by
    verification/meep_adapter_transmittance_check.py. CI runs neither: both
    need a solver it does not have, so it exercises this module only against
    a hand-written fake. Treat a result on a geometry unlike those reference
    cases as unverified.
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
