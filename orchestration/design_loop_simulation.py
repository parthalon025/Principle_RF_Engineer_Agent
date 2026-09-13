"""SIMULATION-step dispatch for the design loop (issue #516, split out of
`orchestration/design_loop.py` per issue #498).

This is a pure move: `_handle_simulation`, its three solver handlers
(`_simulate_nec2`, `_simulate_meep_floquet`, `_simulate_palace_floquet`), the
supporting helpers that read a family's declared solver and enforce its
preconditions before any solver time is spent (`_simulation_adapter_for`,
`_declared_adapter_name`, `_role_tagged_primitives`,
`_require_reflector_or_confirmed_host_ground_plane`,
`_require_transmission_monitor_for_two_port`), the two helpers that turn a
Meep run's raw powers into an absorption (`_meep_absorption_for_family`,
`_two_port_transmittance`), and the `_SIMULATION_ADAPTERS` dispatch table
they share, all moved here unchanged -- no function signature, dispatch
logic, or table contents changed as part of the split.
`orchestration/design_loop.py` imports this module and wires
`_handle_simulation` into its own `_STEP_HANDLERS` table, exactly the way it
already did before the names lived here (re-exported from
`orchestration.design_loop` so nothing that already imported them from there
needs to change -- `verification/meep_two_port_absorption_check.py` imports
`_simulate_meep_floquet` from `orchestration.design_loop` directly, and
`tests/test_design_loop.py` does the same for
`_require_reflector_or_confirmed_host_ground_plane` and
`_simulation_adapter_for`).

Deliberately imports its shared kernel (`_registry_family_of_record`,
`_family_of_record`, `_require_fields`, `_any_requirement_confirms_host_
ground_plane`, `DesignLoopValidationError`, `SIMULATE_NEC2_REQUIRED_FIELDS`,
`DesignLoopState`) FROM `orchestration.design_loop` rather than the other way
around -- those stay the state machine's own concern (issue #498's
"Implementation Decisions": the ledger/validation helpers, the family-of-
record lookup, and the host-ground-plane requirement reader are not one of
the four cited reasons to change, and this ticket does not relocate them).
`SIMULATE_NEC2_REQUIRED_FIELDS` in particular is the named constant issue
#510 already added to `design_loop.py` so `orchestration/solver.py` could
import it instead of restating the field set as its own literal; `_simulate_
nec2` below references that same constant rather than re-inlining it, and it
still lives in `design_loop.py` -- moving `_simulate_nec2` here does not move
the constant, since `solver.py`'s own `from .design_loop import
SIMULATE_NEC2_REQUIRED_FIELDS` must keep resolving unchanged.
`design_loop.py`, in turn, imports the names this module defines back out of
it to populate its own `_STEP_HANDLERS` table -- a genuine two-way
dependency between the two modules. The imports FROM `.design_loop` below
are therefore done lazily, inside each function that needs them, rather than
at this module's top level: a top-level `from .design_loop import ...` here
would deadlock against `design_loop.py`'s own top-level import of this
module whichever module a caller happened to import first (the one imported
first would still be mid-execution, with the name the other side wants not
yet bound, when the cycle closes). Deferring these lookups to call time
sidesteps the ordering question entirely -- by the time any handler here
actually RUNS, both modules have finished importing, in either order.

`_run_nec2_simulation`/`_run_meep_simulation`/`_run_palace_simulation` are
ALSO looked up lazily from `.design_loop` -- inside `_simulate_nec2`/
`_simulate_meep_floquet`/`_simulate_palace_floquet` respectively -- even
though importing them directly from `simulation.nec2pp`/`simulation.meep`/
`simulation.palace` at this module's top level would not create the cycle
above. The reason is `tests/test_design_loop.py`'s own fixtures, unchanged
by this split: they fake a solver run with `monkeypatch.setattr
(design_loop_module, "_run_nec2_simulation", fake_result)` (and the Meep/
Palace equivalents) -- i.e. they patch the name on `orchestration.design_
loop`, not here. A direct top-level import here would bind this module's
OWN copy of the name at import time, and the handler would keep calling
that copy forever after -- the monkeypatch would silently stop intercepting
anything. Reading the name back off `.design_loop` at call time, the same
way `_require_fields`/`DesignLoopValidationError` already are, means each
call sees whatever `design_loop.py` currently has bound to that name --
patched or not -- so the existing fixtures keep working unchanged.
`design_loop.py` keeps its own top-level import of these three names for
exactly this reason (see its own comment there), even though nothing in
that module calls them directly any more.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from designs.design_families import (
    UnsettledSimulationAdapterError as _UnsettledSimulationAdapterError,
)
from rf_tools.network_parameters import (
    reflection_coefficient_from_impedance as _reflection_coefficient_from_impedance,
)
from rf_tools.network_parameters import return_loss_db as _return_loss_db
from rf_tools.network_parameters import vswr_from_gamma as _vswr_from_gamma
from rf_tools.transmissive_absorber import (
    declared_port_count as _declared_port_count,
)
from rf_tools.transmissive_absorber import (
    energy_balance_violations as _energy_balance_violations,
)
from rf_tools.transmissive_absorber import (
    energy_balance_warning as _energy_balance_warning,
)
from rf_tools.transmissive_absorber import (
    one_port_absorption as _one_port_absorption,
)
from rf_tools.transmissive_absorber import (
    two_port_absorption as _two_port_absorption,
)
from simulation.base import SimulatorError as _SimulatorError
from simulation.base import solver_workdir_is_durable as _solver_workdir_is_durable
from simulation.meep import (
    PERIODIC_ABSORBER_VALIDITY as _MEEP_PERIODIC_ABSORBER_VALIDITY,
)
from simulation.meep import GeometryRole as _GeometryRole
from simulation.meep import (
    periodic_absorber_capability_gaps as _meep_periodic_absorber_capability_gaps,
)
from simulation.palace import (
    metasurface_capability_gaps as _palace_metasurface_capability_gaps,
)

if TYPE_CHECKING:
    # Type-only -- see the module docstring for why the runtime names this
    # module needs from `.design_loop` are imported lazily instead, inside
    # each function that uses them.
    from .design_loop import DesignLoopState


# There is no default simulation adapter, deliberately (issue #241). The
# `DEFAULT_SIMULATION_ADAPTER = "NEC2"` that used to sit here caught every
# family that declared no solver and sent it to a thin-wire method-of-moments
# code whose entire geometry vocabulary is wires over an optional ground
# plane. A periodic printed surface is not a hard case for NEC2 -- it is one
# you cannot write an input file for. Nothing else in this repo needed the
# constant, so it is gone rather than kept unused: a default nobody chose is
# precisely what #241 removed.


def _simulation_adapter_for(state: DesignLoopState) -> str:
    """The NAME of the solver this iteration's design family declares.

    Read off `simulation_adapter` in the Design family registry
    (`designs/design_families.py`), which holds either a settled
    `SimulationAdapter` or an explicit `UnsettledSimulationAdapter` saying
    the question is open -- never a bare `None`, and never a default. A
    family with no settled adapter, and an iteration that has not recorded an
    ARCHITECTURE decision at all, both raise here naming what is missing.
    """
    from .design_loop import _registry_family_of_record

    return _declared_adapter_name(_registry_family_of_record(state, "simulation"))


def _declared_adapter_name(family: Any) -> str:
    """The solver name a registry entry declares, or a raise saying the
    choice is still open. Split out from `_simulation_adapter_for` so
    `_handle_simulation` can read the family ONCE and pass it on: the
    handlers need the family itself, not only its solver's name -- since
    #243 the absorption arithmetic is selected from the family's declared
    `port_count`."""
    from .design_loop import DesignLoopValidationError

    try:
        return family.declared_simulation_adapter().name
    except _UnsettledSimulationAdapterError as exc:
        # Re-raised as this loop's own error type with the registry's message
        # intact, the same way _handle_architecture and _handle_analysis do.
        raise DesignLoopValidationError(str(exc)) from exc


def _role_tagged_primitives(geometry: Any) -> list[Any]:
    """Every raw, unvalidated `role` value across `geometry`'s combined
    `materials`+`conductors` lists (issue #486, reading #485's own tag back
    out). Deliberately NOT re-validating each value against `GeometryRole`
    -- that is `simulation/meep.py`'s `_validate_role`'s job, run for real
    when (and only when) a MEEP_FLOQUET candidate actually builds its
    geometry; this function only needs to know whether ANY primitive
    opted into role-tagging at all, and (via the caller) how many claim
    `REFLECTOR`.

    Tolerates `geometry` being `None` or not a dict at all -- returning `[]`
    rather than raising -- because this can run (from `_handle_simulation`)
    before a handler's own `_require_fields` has had a chance to say
    'geometry is missing'; this check must not pre-empt that with a
    different, confusing error of its own. A NEC2-shaped geometry (a
    `{'wires': [...]}` dict) also lands here safely: `.get('materials'/
    'conductors', [])` simply finds nothing, the same as no geometry at
    all -- which is exactly the "PATCH's own wire representation cannot
    carry a role tag in the first place" case this ticket's legacy
    exemption exists for.
    """
    if not isinstance(geometry, dict):
        return []
    primitives = list(geometry.get("materials") or []) + list(geometry.get("conductors") or [])
    return [
        prim.get("role")
        for prim in primitives
        if isinstance(prim, dict) and prim.get("role") is not None
    ]


def _require_reflector_or_confirmed_host_ground_plane(
    family: Any, geometry: Any, requirements: Any
) -> None:
    """ADR-0017's rule, finally read against itself (issue #486): a
    candidate whose family needs a ground plane must get one from
    somewhere -- its own bottom printed layer, or the surface it mounts
    on -- and until now nothing checked which. #484 gave a design a place
    to confirm the host is one; #485 gave a geometry primitive a `role` to
    say it IS one (`REFLECTOR`); this is the first thing that reads the
    two against each other.

    CHECKED IN THIS ORDER, and each step here is a deliberate pass, not
    an oversight:

    1. `family.requires_ground_plane` is falsy: exempt outright. A family
       whose physics never depends on a ground plane at all
       (ABSORBER_TRANSMISSIVE's own shape) has nothing here to check.
    2. `geometry` carries no `role` tag anywhere across its combined
       `materials`+`conductors` (`_role_tagged_primitives` above): exempt.
       This is a DELIBERATE decision carried over from the parent spec
       (#481), not a gap -- `role` (#485) is opt-in metadata, and PATCH's
       own NEC2 wire-geometry representation (the other family with
       requires_ground_plane=True) has no materials/conductors list to
       tag in the first place, so it can never satisfy a check phrased in
       terms of that tag. Legacy/pre-#485 MEEP_FLOQUET geometry gets the
       identical pass, for the identical reason: only geometry that opts
       into role-tagging is held to this check.
    3. At least one primitive claims `role=REFLECTOR`
       (`_build_geometry_list` itself caps this at exactly one across a
       geometry's combined materials+conductors): the candidate supplies
       its own reflector, ADR-0017's default. Passes.
    4. Otherwise, passes only if `_any_requirement_confirms_host_ground_
       plane` says this design has a CONFIRMED, is_ground_plane=True
       assertion (#484) -- ADR-0017's named escape hatch: a design may
       skip its own reflector layer and lean on the host instead, but
       only once a human has vouched the host actually is one.

    Raises `DesignLoopValidationError` otherwise, naming the family and
    exactly what to add -- mirroring `_require_transmission_monitor_for_
    two_port`'s own message shape and its own reason for checking here,
    before the solver runs: no length of a Meep run can supply a reflector
    the geometry never described, or a confirmation a human never gave.
    """
    from .design_loop import DesignLoopValidationError, _any_requirement_confirms_host_ground_plane

    if not getattr(family, "requires_ground_plane", False):
        return

    roles = _role_tagged_primitives(geometry)
    if not roles:
        return

    reflector_count = sum(1 for role in roles if role == _GeometryRole.REFLECTOR)
    if reflector_count >= 1:
        return

    if _any_requirement_confirms_host_ground_plane(requirements):
        return

    raise DesignLoopValidationError(
        f"Design family {getattr(family, 'name', family)!r} declares "
        "requires_ground_plane=True (ADR-0017), so this candidate needs a "
        "reflector from somewhere: its own bottom printed layer, or the "
        "surface it mounts on. This candidate's geometry has role-tagged "
        "layers (issue #485) but none of them is role=REFLECTOR, and no "
        "requirement on this design confirms the host is a reliable ground "
        "plane (issue #484). Add a REFLECTOR-role primitive to this "
        "candidate's geometry (materials or conductors), or confirm the "
        "host assertion via designs.requirement_targets."
        "confirm_requirement_host_ground_plane before retrying -- this is "
        "refused before the solver runs rather than after, because no "
        "length of run can supply a reflector the geometry never described "
        "or a confirmation a human never gave."
    )


def _handle_simulation(
    state: DesignLoopState, step_input: dict[str, Any]
) -> tuple[str, dict[str, Any], str | None]:
    """Dispatch SIMULATION to the solver this design family declares (#229).

    Before this, every family ran NEC2. NEC2 is a thin-wire method-of-
    moments code: it solves Maxwell's equations honestly, but the only
    geometry it can express is wires in free space over an optional ground.
    It has no periodic boundary, so it cannot represent a metamaterial unit
    cell at all -- and a unit cell is not a hard case for it, it is an
    inexpressible one. In plain terms: it was being asked to model an
    infinite repeating surface using a tool whose entire vocabulary is
    single wires.

    PATCH declares NEC2 by name and ABSORBER declares MEEP_FLOQUET, so both
    route exactly as they did. What changed at #241 is what happens to
    everything else: a family with no settled adapter raises (see
    `_simulation_adapter_for`) instead of quietly becoming a NEC2 run, and a
    family declaring a solver this loop has no handler for is reported by
    name below rather than answered by whichever handler happened to be
    last. Both refusals are deliberate: a solver that cannot represent the
    structure returns a confidently wrong number, not an uncertain one, and
    no caveat attached to it would tell a reader which it was.

    The registry entry itself -- not just its solver's name -- is handed to
    the handler, because since #243 the handler also has to know how many
    ports the family declares before it can turn the run into an absorption.

    WHY THE REFLECTOR-PROVENANCE CHECK (#486) LIVES HERE, NOT INSIDE A
    HANDLER. `_require_reflector_or_confirmed_host_ground_plane` needs both
    `state.requirements` (where a design's `host_ground_plane` assertion,
    #484, actually lives) and this step's own geometry -- and this function
    is the one place both are already in scope, with no per-handler
    signature change needed. `_simulate_meep_floquet`/`_simulate_nec2`/
    `_simulate_palace_floquet` all take `(family, step_input)` only, per
    `_SIMULATION_ADAPTERS`'s own dispatch contract; threading `requirements`
    through that contract for one check, when every handler's `family`
    argument already carries `requires_ground_plane`, would touch three
    handlers to give one of them one more fact. Checking here also means it
    runs for every adapter uniformly, with no adapter-name special-casing:
    NEC2's geometry is `{'wires': [...]}` and PALACE_FLOQUET's is
    `{'unit_cell', 'ground_backed', 'pec_patches', ...}` -- neither carries a
    `materials`/`conductors` list to tag a `role` onto in the first place
    (#485's tag exists only on `simulation/meep.py`'s own geometry shape),
    so `_role_tagged_primitives` finds nothing for either and the legacy
    exemption fires on its own. PATCH (NEC2, requires_ground_plane=True)
    is proof of this: it is never refused by this check, and never needed a
    line of code naming NEC2 to arrange that.
    """
    from .design_loop import _family_of_record, _registry_family_of_record

    family = _registry_family_of_record(state, "simulation")
    adapter = _declared_adapter_name(family)
    handler = _SIMULATION_ADAPTERS.get(adapter)
    if handler is None:
        raise _SimulatorError(
            f"Design family {_family_of_record(state)!r} declares "
            f"simulation_adapter {adapter!r}, and this loop has no handler wired "
            f"for it -- it can drive {sorted(_SIMULATION_ADAPTERS)}. Wire one in "
            "orchestration/design_loop.py's _SIMULATION_ADAPTERS, or correct the "
            "declaration in designs/design_families.py. Running a different "
            "solver instead is the exact defect issue #241 removed."
        )
    _require_reflector_or_confirmed_host_ground_plane(
        family, step_input.get("geometry"), state.requirements
    )
    return handler(family, step_input)


def _solver_workdir_durability_validity(workdir: str | None) -> list[dict[str, str]]:
    """Issue #466: a load-bearing warning, in the same shape as
    `simulation.meep.PERIODIC_ABSORBER_VALIDITY`, for exactly the case that
    ticket leaves as the exception rather than the rule -- a solver run
    whose `workdir` is NOT the durable, programme-owned directory
    `simulation.base.new_solver_workdir` hands out by default (an explicit
    `workdir` a caller supplied instead, e.g. still pointing into the OS's
    own scratch area). A run using the default durable path returns an
    empty list here, deliberately: firing this on every run regardless
    (issue #345's original, blanket version of this warning) is what
    CLAUDE.md's charter rules out -- "a warning is only useful if it is
    rare and specific" -- and the whole point of #466 is to make the
    non-durable case the rare one again.

    `workdir` is `None` exactly when the underlying solver call raised or
    returned nothing usable before recording one; that is a different
    failure with its own signal (the step itself never completes), not a
    durability question, so it is treated as durable here rather than
    manufacturing a second warning about an absent fact."""
    if workdir is None or _solver_workdir_is_durable(workdir):
        return []
    return [
        {
            "flag": "solver_workdir_not_durable",
            "assumed": (
                f"the solver's working directory ({workdir}) is NOT this programme's "
                "own durable solver_artifacts root -- it was supplied explicitly "
                "rather than left to the default"
            ),
            "costs": (
                "whatever governs that directory's lifetime is unknown here; a later "
                "reader (a Field bundle exporter, a human re-opening this decision) "
                "may find the mesh, config or output gone"
            ),
            "cheapest_test": (
                "re-run with no explicit workdir so the default durable path is used, "
                "or copy the directory under solver_artifacts_root() before anything "
                "might remove it"
            ),
        }
    ]


def _simulate_meep_floquet(
    family: Any,
    step_input: dict[str, Any],
) -> tuple[str, dict[str, Any], str | None]:
    """The Floquet unit-cell path, with the absorption sum chosen by the
    family's declared port count (#243).

    HOW A RUN BECOMES AN ABSORPTION. Meep returns how much power came back
    (reflectance, R) and -- on request -- how much went through
    (transmittance, T). Absorption is what is left:

        one port  (ground-backed, `port_count=1`):  A = 1 - R
        two ports (unbacked,      `port_count=2`):  A = 1 - R - T

    In plain terms: with metal behind the surface, anything that did not
    bounce back had nowhere to go but into heat. With free space behind it,
    some of it simply carried on out the far side, and that share has to be
    taken off. Using the one-port sum on an unbacked surface credits the
    design for power that escaped -- a stack absorbing 0.44 reported as
    1.00, with nothing in the number to say so, which reads as success. See
    docs/absorber-scoring-conventions.md section 1; both sums are the
    field's own, not a house convention.

    WHY THE PORT COUNT IS READ HERE. This is the one place a design family
    and a solver result are both in hand: the registry knows the ports, the
    adapter knows the powers, and neither knows the other. The arithmetic
    itself, and its refusal, live beside the two absorber models in
    rf_tools/transmissive_absorber.py -- a reader who opens either absorber
    module finds the rule; a reader who opens the loop finds the dispatch.

    A TWO-PORT RUN MUST ACTUALLY ASK FOR T, and is refused twice over if it
    cannot have it: once before the solver runs (no transmission monitor in
    the geometry -- the answer is unobtainable however long the run takes,
    and full-wave time is the expensive thing here) and once after (a
    monitor was asked for and the adapter could not measure through it).
    Quietly falling back to A = 1 - R in either case is the precise defect
    #243 exists to remove.

    Both are raises rather than warnings, for the same reason the analysis
    dispatch raises: they would produce a confidently wrong number, not an
    uncertain one, and no caveat attached to it would tell a reader which it
    was. This is not the charter's "warn, never block" being broken -- that
    rule governs withholding a CANDIDATE from a reader, and nothing is
    withheld: ANALYSIS's closed-form absorption is already recorded and
    survives this step's failure, exactly as #111's two-tier design intends.
    The genuinely uncertain case -- R + T summing to more than the power
    that arrived -- is warned about and the candidate is still returned and
    ranked; see `_meep_absorption_for_family` below.
    """
    from .design_loop import _require_fields, _run_meep_simulation

    gaps = _meep_periodic_absorber_capability_gaps()
    if gaps:
        detail = "; ".join(f"{gap['gap']}: {gap['costs']}" for gap in gaps)
        raise _SimulatorError(
            "MEEP_FLOQUET is the right adapter for a periodic absorber cell "
            "and simulation/meep.py cannot yet deliver one. Missing: "
            f"{detail}. ANALYSIS's closed-form absorption still stands as this "
            "candidate's evidence (rf_tools/absorber.py, provenance "
            "CALCULATED); what is unavailable is the full-wave confirmation "
            "that would raise it to SIMULATED. See simulation/meep.py's "
            "periodic_absorber_capability_gaps() for how to close each one."
        )

    _require_fields(step_input, {"geometry", "frequency_hz"}, "simulation")
    geometry = dict(step_input["geometry"])
    # A unit cell is periodic in the plane by definition. The caller may
    # override, but it must not have to remember: forgetting this is the
    # difference between an infinite surface and one lonely element, and it
    # fails silently rather than loudly.
    geometry.setdefault("periodic_axes", ["x", "y"])
    _require_transmission_monitor_for_two_port(family, geometry)

    result = _run_meep_simulation(
        geometry=geometry,
        characteristic_length_m=step_input.get("characteristic_length_m", 1e-3),
        nfreq=int(step_input.get("nfreq", 1)),
        workdir=step_input.get("workdir"),
    )

    s_parameters = result.get("s_parameters") or {}
    reflectance = s_parameters.get("reflectance") or []
    absorption_reading = _meep_absorption_for_family(family, s_parameters)

    recorded = {
        "function": "run_meep_simulation",
        "simulator": result.get("simulator"),
        "status": result.get("status"),
        "frequency_hz": s_parameters.get("frequency_hz"),
        "reflectance": reflectance,
        "absorption": absorption_reading["absorption"],
        "worst_absorption": (
            min(absorption_reading["absorption"]) if absorption_reading["absorption"] else None
        ),
        # What the arithmetic assumed, said out loud rather than inferred
        # from the family's name by whoever reads the result later.
        "port_count": absorption_reading["port_count"],
        "absorption_formula": absorption_reading["absorption_formula"],
        # The transmitted share, and separately the adapter's own three-state
        # account of whether it was even looked for (#240): "not asked",
        # "asked and could not be measured" and "measured, possibly zero" are
        # three different facts, and collapsing them is how a measured zero
        # becomes indistinguishable from silence.
        "transmittance": absorption_reading["transmittance"],
        "transmittance_measurement": absorption_reading["transmittance_measurement"],
        "energy_balance_violations": absorption_reading["energy_balance_violations"],
        "periodic_axes": geometry["periodic_axes"],
        "validity": [dict(entry) for entry in _MEEP_PERIODIC_ABSORBER_VALIDITY]
        + absorption_reading["validity"]
        + _solver_workdir_durability_validity(result.get("workdir")),
        # Where the solved geometry actually lives (issue #461, the #345
        # gap for MEEP): `run_meep_simulation` already returns its own
        # working directory; without recording it here a completed
        # ABSORBER/ABSORBER_TRANSMISSIVE decision names no directory once
        # persisted and reloaded, and a result can outlive the thing that
        # produced it -- the same defect #345 fixed for Palace.
        "workdir": result.get("workdir"),
        "provenance": result.get("provenance", "SIMULATED"),
    }
    return "simulation", recorded, recorded["provenance"]


def _require_transmission_monitor_for_two_port(family: Any, geometry: dict[str, Any]) -> None:
    """A two-port family's run must carry a transmission monitor, checked
    BEFORE the solver starts.

    The loop cannot supply the plane itself: where it goes depends on which
    side the source is on and where the absorbing boundary ends, and only
    whoever laid the cell out knows that. Guessing a plane would be worse
    than asking -- a monitor in the wrong place returns a number that looks
    like a measurement.

    Checked up front because the alternative is spending a full-wave run to
    discover something already knowable from the step_input, and because the
    message can then say exactly which key to add.
    """
    from .design_loop import DesignLoopValidationError

    if _declared_port_count(family) == 1:
        # One port: nothing gets through by construction, so asking for the
        # monitor would only buy solver time to confirm a structural zero.
        return
    if geometry.get("transmission_monitor_center_m") is not None:
        return
    raise DesignLoopValidationError(
        f"Design family {getattr(family, 'name', family)!r} declares "
        f"port_count={getattr(family, 'port_count', None)}, so its absorption is "
        "A = 1 - R - T and the run must measure how much power passes THROUGH "
        "the surface. This simulation step_input's geometry has no "
        "'transmission_monitor_center_m', so there is nothing to measure it "
        "with. Add that key -- a plane on the far side of the structure from "
        "the source, inside the cell and clear of the PML (see "
        "simulation/meep.py's run_meep_simulation geometry contract). This is "
        "refused before the solver runs rather than after, because no length "
        "of run can produce a quantity nothing was set up to record, and "
        "falling back to A = 1 - R would credit this candidate for every watt "
        "that escaped out the back -- the exact defect issue #243 removes."
    )


def _meep_absorption_for_family(family: Any, s_parameters: dict[str, Any]) -> dict[str, Any]:
    """Turn one Meep run's powers into an absorption, by the family's ports.

    Returns the absorption spectrum together with everything a reader needs
    to check it: which sum was used, the transmitted share (or None where
    the family has no such quantity), the adapter's own three-state
    transmittance entry verbatim, any frequency where the powers do not add
    up, and the warning that goes with those.
    """
    reflectance = s_parameters.get("reflectance") or []
    measurement = s_parameters.get("transmittance")
    ports = _declared_port_count(family)

    if ports == 1:
        # Ground-backed, so nothing is transmitted and every watt not
        # reflected was dissipated. That guarantee is the ONLY reason
        # A = 1 - R is legitimate, and one_port_absorption re-checks it
        # against the family rather than trusting this branch.
        return {
            "absorption": _one_port_absorption(family, reflectance),
            "port_count": ports,
            "absorption_formula": "A = 1 - R",
            "transmittance": None,
            "transmittance_measurement": measurement,
            "energy_balance_violations": [],
            "validity": [],
        }

    transmittance = _two_port_transmittance(family, measurement)
    frequency_hz = s_parameters.get("frequency_hz") or []
    violations = _energy_balance_violations(reflectance, transmittance, frequency_hz)
    return {
        "absorption": _two_port_absorption(family, reflectance, transmittance),
        "port_count": ports,
        "absorption_formula": "A = 1 - R - T",
        "transmittance": transmittance,
        "transmittance_measurement": measurement,
        "energy_balance_violations": violations,
        # More power leaving than arrived is impossible for a passive
        # surface, so it is a violated assumption surfacing -- uncertain,
        # not confidently wrong. The charter's "warn, never block" governs
        # exactly this: the candidate is returned and ranked with the
        # warning attached, never withheld to protect the reader from it.
        "validity": [_energy_balance_warning(violations)] if violations else [],
    }


def _two_port_transmittance(family: Any, measurement: Any) -> list[float]:
    """The measured transmitted-power spectrum, or a raise saying why there
    is none.

    `measurement` is simulation/meep.py's `s_parameters["transmittance"]`
    entry (#240), which always says which of three things happened: nobody
    asked, somebody asked and it could not be computed, or it was measured
    (possibly as zero). Only the third can be used here, and a measured zero
    is a real result -- it means this surface genuinely passes nothing at
    these frequencies, which is different from never having looked.
    """
    if isinstance(measurement, dict) and measurement.get("computed"):
        return [float(t) for t in measurement.get("transmittance") or []]
    name = getattr(family, "name", repr(family))
    if measurement is None:
        detail = (
            "the solver returned no 'transmittance' entry at all, so this "
            "adapter predates issue #240 or was bypassed"
        )
    elif not measurement.get("requested"):
        detail = (
            "the solver reports no transmittance because no transmission "
            "monitor was requested, even though this step asked for one -- the "
            "monitor plane did not reach the adapter"
        )
    else:
        detail = (
            "a transmission monitor was requested and the solver could not "
            f"compute a transmittance from it: {measurement.get('note', 'no reason given')}"
        )
    raise _SimulatorError(
        f"Design family {name!r} is two-port, so its absorption is "
        f"A = 1 - R - T, and T is missing: {detail}. No absorption is recorded "
        "for this run. Computing A = 1 - R instead would silently book every "
        "watt that passed through the surface as heat -- reporting 0.80 where "
        "the truth may be 0.50 -- and a too-high absorption reads as success, "
        "which is why this is refused rather than warned about (issue #243). "
        "ANALYSIS's closed-form two-port absorption "
        "(rf_tools/transmissive_absorber.py, provenance CALCULATED) still "
        "stands as this candidate's evidence."
    )


def _simulate_palace_floquet(
    family: Any,
    step_input: dict[str, Any],
) -> tuple[str, dict[str, Any], str | None]:
    """The Palace Floquet unit-cell path for REFLECTION_PHASE/DIFFUSIVE
    (#252 ticket 3), mirroring `_simulate_meep_floquet`'s own shape: check
    the capability gap BEFORE spending any solver time, raise a named
    `SimulatorError` if the candidate's geometry cannot pose the family's
    question, otherwise run the solver and record what it returned.

    `family` is accepted for the same reason every handler in
    `_SIMULATION_ADAPTERS` takes it -- the dispatch table's one shared
    signature -- but this handler needs no fact off it: unlike
    `_simulate_meep_floquet`'s port-count-dependent absorption arithmetic,
    Palace's own S-parameter/conservation-check output already IS the
    answer this family needs (a per-diffraction-order reflectance and
    phase), nothing here derives a second quantity from it.

    WHAT "capability gap" MEANS HERE, AND WHY IT IS CHECKED ON THE GEOMETRY
    RATHER THAN ON THE ADAPTER. Unlike MEEP_FLOQUET's gap check (three
    things the adapter itself cannot yet DO, checked with no arguments),
    both features REFLECTION_PHASE/DIFFUSIVE need -- an embedded PEC
    conductor patch, a ground-backed one-port cell -- are already
    implemented in simulation/palace.py (issue #252 tickets 1/2). What can
    still be wrong is a CANDIDATE's own geometry dict: nothing stops a
    caller from handing this handler the module's OTHER shape (an
    all-dielectric, two-port transmissive grating) by simply omitting
    "ground_backed"/"pec_patches", which would run Palace successfully and
    return a confidently wrong answer -- a bare dielectric grating's
    transmission standing in for a metal-backed metasurface's reflection
    phase. `simulation.palace.metasurface_capability_gaps()` is the probe
    that catches this, per candidate, before any solver time is spent. See
    that function's own docstring for the full reasoning.

    Refusing here is not the charter's "warn, never block" being broken:
    that rule governs withholding a CANDIDATE from a reader, and nothing is
    withheld -- REFLECTION_PHASE/DIFFUSIVE currently declare no closed-form
    ANALYSIS model at all (designs/design_families.py), so there is no
    earlier-stage evidence this refusal could erase; what is refused is
    manufacturing a SIMULATED number for a structure the candidate never
    actually described.
    """
    from .design_loop import _require_fields, _run_palace_simulation

    _require_fields(step_input, {"geometry", "frequency_hz"}, "simulation")
    geometry = dict(step_input["geometry"])

    gaps = _palace_metasurface_capability_gaps(geometry)
    if gaps:
        detail = "; ".join(f"{gap['gap']}: {gap['costs']}" for gap in gaps)
        raise _SimulatorError(
            "PALACE_FLOQUET is the right adapter for a ground-backed metasurface "
            "cell (REFLECTION_PHASE/DIFFUSIVE), and this candidate's geometry does "
            f"not yet describe one. Missing: {detail}. No SIMULATION result is "
            "recorded for this candidate. See simulation/palace.py's "
            "metasurface_capability_gaps() for how to close each gap -- this is "
            "checked in the geometry dict itself, before any solver time is spent."
        )

    result = _run_palace_simulation(
        geometry=geometry,
        frequency_hz=step_input["frequency_hz"],
        sweep=step_input.get("sweep"),
        num_processes=int(step_input.get("num_processes", 1)),
        timeout_s=int(step_input.get("timeout_s", 3600)),
        executable=step_input.get("executable"),
        workdir=step_input.get("workdir"),
        solver_order=int(step_input.get("solver_order", 1)),
    )

    s_parameters = result.get("s_parameters") or {}
    recorded = {
        "function": "run_palace_simulation",
        "simulator": result.get("simulator"),
        "status": result.get("status"),
        "frequency_hz": s_parameters.get("frequency_hz"),
        # Palace's own per-diffraction-order reflectance/phase output --
        # what this family actually needs to know (issue #252's user story
        # 6/7), not a quantity derived or borrowed from another family's
        # physics.
        "s_parameters": s_parameters,
        "specular": s_parameters.get("specular"),
        # Power-balance/passivity/reciprocity, carried through unmodified
        # (issue #221) -- warned on, never blocked on, per ADR-0028.
        "conservation_check": result.get("conservation_check"),
        # Where the solved geometry actually lives (issue #345): without
        # these, a completed decision names no mesh and no output
        # directory once it is persisted and reloaded, and a result can
        # outlive the thing that produced it. `run_palace_simulation`
        # already returns all four; this is the one place they were being
        # dropped on the way into the decision this loop records.
        "workdir": result.get("workdir"),
        "mesh_file": result.get("mesh_file"),
        "config_file": result.get("config_file"),
        "output_dir": result.get("output_dir"),
        "num_mesh_elements": result.get("num_mesh_elements"),
        # Issue #466: silent unless this run's workdir is NOT the durable
        # default -- see _solver_workdir_durability_validity's docstring.
        "validity": _solver_workdir_durability_validity(result.get("workdir")),
        "provenance": result.get("provenance", "SIMULATED"),
    }
    return "simulation", recorded, recorded["provenance"]


def _simulate_nec2(
    family: Any,
    step_input: dict[str, Any],
) -> tuple[str, dict[str, Any], str | None]:
    """Runs run_nec2_simulation, then (issue #101) derives VSWR and return
    loss from the feed-point impedance that call already returns, against
    an explicit `reference_impedance_ohms` step_input MUST state -- never
    silently assumed to be 50 ohms (CONTEXT.md's provenance discipline:
    every recorded number's inputs are stated, not guessed). This is
    deterministic arithmetic over SIMULATION's own already-computed
    impedance, not a second solver run -- no new evidence is manufactured,
    only a different reading of the same evidence, so the result still
    carries run_nec2_simulation's own SIMULATED provenance, not a fresh
    CALCULATED one.

    NEC2++'s adapter only ever solves at ONE frequency (the frequency_hz
    this step_input states) -- so the derived vswr/return_loss_db is
    inherently a single-frequency point prediction, honestly recorded as
    `single_frequency_prediction=True`: a requirement typically stated as
    a band (e.g. "VSWR <= 2.0 across 8-12 GHz") is not fully evaluated by
    one point. orchestration/lab_test_plan.py surfaces this flag alongside
    the traced expected value rather than silently presenting one
    frequency's answer as if it covered the whole band.

    vswr_from_gamma/return_loss_db are each undefined at one of the two
    physical extremes (|Gamma| == 0: perfect match, return loss is
    infinite; |Gamma| == 1: total mismatch, VSWR is infinite) -- each is
    caught independently so the whole step doesn't fail just because the
    OTHER quantity happens to be finite; a genuinely undefined value is
    recorded as None, never guessed at. impedance itself can also be None
    (run_nec2_simulation's own parser found no ANTENNA INPUT PARAMETERS
    block) -- nothing to derive from, so vswr/return_loss_db/
    reflection_coefficient_magnitude are all None, but the step still
    advances: the underlying simulation itself completed.
    """
    from .design_loop import (
        SIMULATE_NEC2_REQUIRED_FIELDS,
        _require_fields,
        _run_nec2_simulation,
    )

    del family  # a wire-antenna run needs no family fact; the signature is the dispatch's
    _require_fields(step_input, SIMULATE_NEC2_REQUIRED_FIELDS, "simulation")
    result = _run_nec2_simulation(
        geometry=step_input["geometry"],
        frequency_hz=step_input["frequency_hz"],
        timeout_s=step_input.get("timeout_s", 600),
        executable=step_input.get("executable"),
        workdir=step_input.get("workdir"),
    )

    reference_impedance_ohms = step_input["reference_impedance_ohms"]
    reflection_coefficient_magnitude: float | None = None
    vswr: float | None = None
    return_loss_db_value: float | None = None
    impedance = result.get("impedance")
    if impedance is not None:
        z_load = complex(impedance["resistance_ohms"], impedance["reactance_ohms"])
        gamma = _reflection_coefficient_from_impedance(z_load, reference_impedance_ohms)
        reflection_coefficient_magnitude = abs(gamma)
        try:
            vswr = _vswr_from_gamma(reflection_coefficient_magnitude)
        except ValueError:
            vswr = None  # |Gamma| == 1: total mismatch, VSWR is undefined (infinite)
        try:
            return_loss_db_value = _return_loss_db(reflection_coefficient_magnitude)
        except ValueError:
            return_loss_db_value = None  # |Gamma| == 0: perfect match, return loss undefined

    result = {
        **result,
        # Which function actually ran, stated on the result itself -- the
        # same key `_simulate_meep_floquet`/`_simulate_palace_floquet`
        # already record, and the one `orchestration/tooling.py`'s flush
        # reads for `engineering_results.tool_name` (issue #334). Without
        # it this branch would depend on a per-step default to be labelled
        # correctly, which is precisely how every Meep and Palace run came
        # to be filed under NEC2's name.
        "function": "run_nec2_simulation",
        "reference_impedance_ohms": reference_impedance_ohms,
        "reflection_coefficient_magnitude": reflection_coefficient_magnitude,
        "vswr": vswr,
        "return_loss_db": return_loss_db_value,
        "frequency_hz": step_input["frequency_hz"],
        "single_frequency_prediction": True,
    }
    return "simulation", result, result.get("provenance", "SIMULATED")


# The dispatch table `_handle_simulation` reads, keyed by the adapter name a
# family declares. Each handler takes (family, step_input): the family comes
# along because reading a solver's numbers can depend on what KIND of surface
# was simulated -- MEEP_FLOQUET's absorption sum is chosen by the declared
# port count (#243) -- and a handler that needs no family fact says so with a
# `del family` rather than the table carrying two shapes of callable.
# Every solver this loop can actually drive is listed here
# and nothing else runs: an adapter name with no entry is reported by name,
# never quietly served by another solver (issue #241). Palace is implemented
# in simulation/palace.py, validated against a real binary (#210), and wired
# here as PALACE_FLOQUET for REFLECTION_PHASE/DIFFUSIVE (#252 ticket 3).
_SIMULATION_ADAPTERS: dict[str, Any] = {
    "NEC2": _simulate_nec2,
    "MEEP_FLOQUET": _simulate_meep_floquet,
    "PALACE_FLOQUET": _simulate_palace_floquet,
}
