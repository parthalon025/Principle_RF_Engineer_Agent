"""The Design family registry -- the open interface every design family
implements (ADR-0018; issue #109; CONTEXT.md: Design family, Design family
registry, Physical bound, Simulation tier).

WHY THIS EXISTS. `orchestration/design_loop.py`'s `_handle_architecture`
already requires a `design_family` on every ARCHITECTURE decision (#161), but
accepts any bare string, and says so in its own comment: the registry "is a
separate, not-yet-landed ticket; this field only names the family, it doesn't
validate the name against one." So the loop could record `design_family =
"absorbre"`, or `"antenna"` meaning either of two families with structurally
different feasibility physics, and nothing downstream would notice. This
module is that registry.

WHY AN OPEN INTERFACE RATHER THAN ONE SCHEMA. ADR-0018's deciding argument is
`physical_bound`: the absorber family's Rozanov bound takes a thickness and a
band and returns metres; the patch family's Nel/Skrivervik/Gustafsson bound
takes a reference half-wave simulation and returns a dimensionless Q. They are
different functions, not one function with a swapped constant -- see
`rf_tools/physical_bounds.py`, which implements both and is the evidence.
Every family therefore satisfies a thin common SPINE (the #107 fields) and
then carries its own heterogeneous parts.

THE AMBIGUITY THIS REGISTRY HAD TO RESOLVE. ADR-0018 rejected a fixed
dataclass with optional fields specifically because "a `None` would be
ambiguous between 'not yet computed' and 'doesn't exist for this family'".
Those are genuinely different states and the registry holds both, distinctly:

  * `NO_PHYSICAL_BOUND` -- this family HAS no fundamental bound. The
    diffusive/coding backscatter family is the real instance: ADR-0018 names
    it as "one family [that] has no bound at all".
  * `UnreadPhysicalBound` -- a bound EXISTS and is named in the literature,
    but this programme has not read its primary source, so no formula is
    offered. Calling it raises with the citation to go read. The
    reflection-phase family is the live instance: #109 names Gustafsson &
    Sjoberg, and unlike Rozanov and Nel it has not been read first-hand.

The second is the load-bearing one. Guessing a plausible-looking formula for
an unread bound would produce a confident number with no source behind it,
which is precisely the failure Provenance exists to prevent -- and
a silent `None` would have made "we never looked" indistinguishable from
"there is nothing to look for".

THE SAME DISCIPLINE, NOW ON TWO MORE SLOTS. `analysis_model` (issue #239)
and `simulation_adapter` (issue #241) are built exactly this way, and for
exactly this reason. Both used to be answered by a default: ANALYSIS picked
its model by comparing the family's NAME against the string "ABSORBER" and
gave everything else the patch-antenna resonant-frequency formula, and
SIMULATION sent any family that declared no solver to NEC2 -- a thin-wire
code that cannot express a periodic surface at all. In plain terms, one read
the label on the box to decide which instrument to reach for, and the other
handed a repeating printed surface to a tool whose whole vocabulary is single
wires. Neither is a conservative default; each is a wrong answer waiting to be
produced confidently, and a reader cannot tell such a number from a right one
by looking at it. Both slots are now required at construction, so a family
cannot be added without saying which model and which solver it needs -- or
saying, in writing, that nobody has established one.

SELECTION STAYS HUMAN-AUTHORED. Per CONTEXT.md, "the loop does not attempt to
infer a family from a requirement's prose." This module validates a family a
human named; it never picks one.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from rf_tools import physical_bounds


class SimulationTier(StrEnum):
    """Whether a family's whole evaluation is one unit-cell solve (#107).

    TIER_A -- the unit-cell solve IS the answer (absorbers, polarization
    converters: uniform surfaces whose designed-for behaviour exists at one
    cell).

    TIER_B -- the unit-cell solve only populates a phase-versus-parameter
    lookup that an aperture-level evaluation then consumes, because the
    designed-for behaviour (a steered beam, a suppressed backscatter lobe)
    does not exist at unit-cell level at all. Only Tier B families carry a
    symbol alphabet (#130).
    """

    TIER_A = "TIER_A"
    TIER_B = "TIER_B"


# --------------------------------------------------------------------------
# Physical bound: three distinct states, never a bare None
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class PhysicalBound:
    """A family's feasibility predicate, with the citation it was read from
    and the assumptions that decide whether it applies.

    `feasibility` is deliberately NOT a shared signature -- it is whatever
    that family's bound actually needs, called with keyword arguments the
    family's own caller supplies. ADR-0018 is explicit that forcing these
    into one signature is the mistake; `validity` is the free-text validity
    box a caller must check before trusting a returned number.
    """

    name: str
    citation: str
    primary_source_doc: str
    feasibility: Callable[..., Any]
    validity: str

    def __call__(self, **kwargs: Any) -> Any:
        return self.feasibility(**kwargs)


@dataclass(frozen=True)
class UnreadPhysicalBound:
    """A bound that exists in the literature but whose primary source this
    programme has not read. Distinct from `NO_PHYSICAL_BOUND`, and distinct
    from a bound that is merely uncomputed for one design.

    Calling it raises rather than returning a plausible number: the repo's
    own rule is that a bound is read first-hand before it is relied on (the
    Rozanov "lambda/17 vs 17.2" discrepancy is what that rule is for -- the
    round number everyone quotes comes from an abstract, not a derivation).
    """

    name: str
    citation: str

    def __call__(self, **kwargs: Any) -> Any:
        raise NotImplementedError(
            f"The {self.name} has not been read from its primary source "
            f"({self.citation}), so no formula is offered. Read it first-hand and "
            "record it the way docs/rozanov-bound-primary-source.md and "
            "docs/patch-q-factor-bound-primary-source.md do, then replace this "
            "marker with a PhysicalBound. Do NOT substitute a similar-looking "
            "formula from another family."
        )


@dataclass(frozen=True)
class _NoPhysicalBound:
    """Sentinel type for a family that genuinely has no fundamental bound."""

    reason: str

    def __call__(self, **kwargs: Any) -> Any:
        raise TypeError("This design family has no physical bound to evaluate: " + self.reason)


NO_PHYSICAL_BOUND = _NoPhysicalBound(
    reason=(
        "a diffusive/coding surface redistributes backscatter rather than "
        "dissipating or radiating a bounded quantity, so no thickness- or "
        "size-versus-performance inequality of the Rozanov/Chu kind governs it "
        "(ADR-0018: 'one family (diffusive/coding backscatter reduction) has no "
        "bound at all')."
    )
)

PhysicalBoundSlot = PhysicalBound | UnreadPhysicalBound | _NoPhysicalBound


# --------------------------------------------------------------------------
# Analysis model: which closed-form calculation this family's ANALYSIS runs
# --------------------------------------------------------------------------
#
# WHY THIS FIELD EXISTS (issue #239). `orchestration/design_loop.py`'s
# ANALYSIS step used to choose its model by comparing the family's NAME
# against the single string "ABSORBER"; everything else got the patch-antenna
# resonant-frequency formula. That is not a default, it is an accident
# waiting for the next family: `ABSORBER_TRANSMISSIVE` (#216) was analysed as
# a transmitting antenna from the moment it was created, purely because its
# name is not the word "ABSORBER".
#
# In plain terms: the loop was reading the label on the box to decide which
# instrument to reach for. It now reads what the box says it needs.
#
# The two states below stay apart for the same reason the physical-bound slot
# keeps three apart (see the module docstring): a bare `None` would make
# "this family has no closed-form model in this repo" indistinguishable from
# "nobody has said". Every family states one or the other, in writing.


@dataclass(frozen=True)
class AnalysisModel:
    """The ONE named calculation a family's ANALYSIS step runs.

    `name` is the dispatch key the design loop matches against its own
    handler table -- one named calculation per family, never an arbitrary
    callable crossing the tool boundary (the same reasoning
    `optimization/rf_objectives.py` gives for wiring one named objective).
    `function` is the repo function that key resolves to, recorded so a
    reader can go and read the physics rather than take the name on trust.
    `answers` says in plain language what question the returned number is an
    answer to -- because the defect this field exists to remove produced a
    perfectly valid number that answered a question about a different device.
    """

    name: str
    function: str
    answers: str


@dataclass(frozen=True)
class UndeclaredAnalysisModel:
    """A family for which this programme has no closed-form ANALYSIS model.

    Asking such a family which analysis to run raises, naming the family and
    this file. That is not the charter's "warn, never block" being broken:
    that rule governs withholding a candidate design from a reader, and no
    candidate is withheld here. What is refused is manufacturing a number the
    programme cannot stand behind -- an analysis that answers the wrong
    question is a CONFIDENTLY WRONG number, not an uncertain one, and a
    reader cannot tell the two apart by looking at them.
    """

    reason: str


AnalysisModelSlot = AnalysisModel | UndeclaredAnalysisModel


class UndeclaredAnalysisModelError(ValueError):
    """Raised when a step asks a family which analysis to run and the family
    declares none (issue #239)."""


# --------------------------------------------------------------------------
# Simulation adapter: which solver can even POSE this family's question
# --------------------------------------------------------------------------
#
# WHY THIS SLOT IS A TYPE AND NOT A STRING-OR-NONE (issue #241).
# `orchestration/design_loop.py` used to fall back to NEC2 whenever a family
# declared no adapter. NEC2 is a thin-wire method-of-moments solver: its
# entire geometry vocabulary is wires over an optional ground plane -- no
# dielectrics, no sheet impedance, no periodicity. A periodic surface is not
# a HARD case for it, it is one you cannot write an input file for at all.
# In plain terms: the fallback handed a repeating printed surface to a tool
# that can only describe single wires, and then reported the answer. That is
# not a conservative default; it is a wrong answer waiting to be produced
# confidently.
#
# So the slot holds one of two things, and never a bare `None` -- the same
# reasoning the physical-bound slot above is built on:
#
#   * `SimulationAdapter` -- a settled choice, carrying WHY that solver is
#     the right one for this family.
#   * `UnsettledSimulationAdapter` -- nobody has established which solver can
#     pose this family's question, and this says so out loud, naming the
#     candidates, what each one is missing, and the cheapest way to settle
#     it. Asking for its name raises.
#
# A settled choice does NOT promise the adapter can deliver a run today:
# `ABSORBER` declared MEEP_FLOQUET while simulation/meep.py still had three
# open capability gaps, and the adapter reported those itself (#229/#230).
# Which solver is right, and whether that solver is finished, are different
# questions and are answered in different files.


@dataclass(frozen=True)
class SimulationAdapter:
    """The solver a family's SIMULATION step routes to, with its reason.

    `name` is the dispatch key the design loop matches against its own
    handler table (currently "NEC2" and "MEEP_FLOQUET"). `reason` says why
    that solver can pose THIS family's question -- recorded because a solver
    choice nobody wrote a reason for is indistinguishable from a default
    nobody chose, which is what issue #241 exists to remove.
    """

    name: str
    reason: str


@dataclass(frozen=True)
class UnsettledSimulationAdapter:
    """A family whose correct solver is genuinely not established.

    Distinct from "we forgot": this is a written statement that the question
    is open, with `candidates` naming each solver considered and what it is
    missing, and `cheapest_test` naming the smallest experiment that would
    settle it -- the same three-part shape the charter requires of a warning
    (what is assumed, what it costs, the cheapest way to find out).

    Asking such a family for an adapter name raises. As with an undeclared
    analysis model, that is not "warn, never block" being broken -- no
    candidate design is withheld from a reader. What is refused is running a
    solver that cannot represent the structure or return the quantity being
    scored, because that produces a confidently wrong number rather than an
    uncertain one.
    """

    reason: str
    candidates: tuple[str, ...] = ()
    cheapest_test: str = ""


SimulationAdapterSlot = SimulationAdapter | UnsettledSimulationAdapter


class UnsettledSimulationAdapterError(ValueError):
    """Raised when a step asks a family which solver to run and the family
    has no settled adapter (issue #241)."""


# --------------------------------------------------------------------------
# The spine, and the family objects
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class DesignFamily:
    """One design family: the thin #107 spine plus its heterogeneous parts.

    The spine fields (band, host thickness, both cell periods, host
    eps_r/tan_delta, conductor sigma, incidence/polarisation envelope,
    ground-plane presence, R = 3T, T <= 2mm) are properties of a DESIGN, not
    of a family -- what a family declares is which of them it *requires* be
    supplied, which is `spine_fields` here. The family-specific parts
    (`physical_bound`, `analysis_model`, `optimizer_class`,
    `simulation_adapter`) are declared
    as open values, never closed two-literal enums, per ADR-0018's
    Consequences: both have a credible third value on the horizon.
    """

    name: str
    description: str
    simulation_tier: SimulationTier
    physical_bound: PhysicalBoundSlot
    # Required, with no default, deliberately (#239): a family that forgets
    # to state which analysis it needs cannot be constructed at all, rather
    # than quietly inheriting another family's model.
    analysis_model: AnalysisModelSlot
    # Required too, and for the same reason (#241): the fallback this
    # replaced sent anything that forgot to state a solver to NEC2, a
    # thin-wire code that cannot express a periodic surface at all.
    simulation_adapter: SimulationAdapterSlot
    requires_ground_plane: bool
    spine_fields: frozenset[str] = field(default_factory=frozenset)
    optimizer_class: str | None = None
    port_count: int = 1

    @property
    def has_physical_bound(self) -> bool:
        """True only when a bound is available to CALL.

        False for both an unread bound and a family with no bound -- which is
        why the two are separate types rather than one falsy value: a caller
        that needs to explain WHY gets a different answer from each.
        """
        return isinstance(self.physical_bound, PhysicalBound)

    @property
    def has_analysis_model(self) -> bool:
        """True only when a closed-form ANALYSIS model is available to run."""
        return isinstance(self.analysis_model, AnalysisModel)

    def declared_analysis_model(self) -> AnalysisModel:
        """The analysis this family declares -- or a raise naming the family
        and what is missing (issue #239).

        Never a fallback to another family's model. In plain terms: if nobody
        has said how to work this kind of surface out on paper, the honest
        answer is "nobody has said", not the arithmetic for a different
        device that happens to be lying around.
        """
        if isinstance(self.analysis_model, AnalysisModel):
            return self.analysis_model
        raise UndeclaredAnalysisModelError(
            f"Design family {self.name!r} declares no analysis_model, so there is "
            f"no ANALYSIS to run for it. Why not: {self.analysis_model.reason} "
            "Declare an AnalysisModel for this family in "
            "designs/design_families.py once there is one to declare, naming the "
            "calculation it runs. Until then this raises rather than falling "
            "through to another family's model: an analysis that answers a "
            "question about a different device is a confidently wrong number, "
            "not an uncertain one (issue #239)."
        )

    @property
    def has_settled_simulation_adapter(self) -> bool:
        """True only when a solver has actually been chosen for this family."""
        return isinstance(self.simulation_adapter, SimulationAdapter)

    def declared_simulation_adapter(self) -> SimulationAdapter:
        """The solver this family declares -- or a raise naming the family,
        what is missing, and what would settle it (issue #241).

        Never a fallback. In plain terms: if nobody has established which
        simulator can even describe this kind of surface, the honest answer
        is "nobody has established that", not whichever solver the loop
        happens to have wired first.
        """
        if isinstance(self.simulation_adapter, SimulationAdapter):
            return self.simulation_adapter
        unsettled = self.simulation_adapter
        candidates = "; ".join(unsettled.candidates) if unsettled.candidates else "none identified"
        raise UnsettledSimulationAdapterError(
            f"Design family {self.name!r} has no settled simulation_adapter, so "
            f"there is no solver to run for it. Why not: {unsettled.reason} "
            f"Candidates considered: {candidates}. Cheapest way to settle it: "
            f"{unsettled.cheapest_test or 'not yet identified'}. Record the "
            "choice on this family in designs/design_families.py once it is "
            "settled. Until then this raises rather than falling back: a solver "
            "that cannot represent this structure returns a confidently wrong "
            "number, not an uncertain one (issue #241)."
        )

    def __post_init__(self) -> None:
        """Guard the invariant issue #216 found broken: `requires_ground_plane`
        and `port_count` must agree, because in this programme's physics they
        are the SAME fact stated twice, not two independent knobs.

        A ground-backed (metal-backed) structure has zero transmission by
        construction, so its reflection coefficient alone -- one port -- tells
        the whole story: A = 1 - |S11|^2. A structure with no ground plane has
        no such guarantee; power can leave out the back, so a second port
        (S21) is required to close the energy balance: A = 1 - |S11|^2 -
        |S21|^2 (docs/absorber-scoring-conventions.md section 1). This is not
        a bookkeeping convention -- it is what makes the Rozanov bound's own
        derivation valid or invalid in the first place
        (docs/rozanov-bound-primary-source.md assumption (b)): a metal
        backing is what lets "everything that didn't reflect became heat"
        hold. Take the backing away and a one-port measurement can no longer
        tell absorption from transmission, so `requires_ground_plane=True`
        paired with `port_count=2` (or the reverse) is not a looser or
        stricter description of the same design -- it is two designs' worth
        of physics conflated into one family. That is exactly the
        contradiction issue #216 found: `ABSORBER` declared
        `requires_ground_plane=True` while carrying US12089385B2 Example 3 --
        the ground-less, two-port reproduction anchor -- as its assigned
        instance. See `ABSORBER_TRANSMISSIVE` below for the resolution.
        """
        if self.requires_ground_plane and self.port_count != 1:
            raise ValueError(
                f"DesignFamily {self.name!r} declares requires_ground_plane=True "
                f"with port_count={self.port_count}; a ground-backed family has "
                "zero transmission by construction and must be port_count=1. "
                "See this method's docstring and issue #216."
            )
        if not self.requires_ground_plane and self.port_count == 1:
            raise ValueError(
                f"DesignFamily {self.name!r} declares requires_ground_plane=False "
                "with port_count=1; without a ground plane, transmission is not "
                "guaranteed zero, so a one-port reflection-only measurement "
                "cannot close the absorption energy balance -- this family needs "
                "port_count=2 (or a stated reason this shape genuinely does not "
                "apply). See this method's docstring and issue #216."
            )


# The #107 spine, shared by every family. Named once here so a family that
# adds a required field does it visibly rather than by convention.
SPINE_FIELDS = frozenset(
    {
        "band",
        "host_thickness_m",
        "cell_period_x_m",
        "cell_period_y_m",
        "host_eps_r",
        "host_tan_delta",
        "conductor_sigma_s_m",
        "incidence_envelope",
        "polarisation_envelope",
        "has_ground_plane",
    }
)


# ISSUE #216 -- WHY THERE ARE TWO ABSORBER FAMILIES, NOT ONE WITH A FLAG.
#
# `ABSORBER` below is a GROUND-BACKED (one-port) absorber, and that is the
# only kind ADR-0017 makes this programme build by default: the base printed
# layer always supplies its own reflector, so T = 0 and A = 1 - |S11|^2.
# Rozanov's bound applies to it directly (docs/rozanov-bound-primary-source.md).
#
# US12089385B2's Example 3 -- this programme's blind reproduction anchor --
# is NOT that. It is two-port and transmissive (no ground plane; a cut wire
# suppresses transmission instead), so A = 1 - |S11|^2 - |S21|^2
# (docs/absorber-scoring-conventions.md section 1) and Rozanov's bound does
# NOT apply at all: its derivation opens by fixing a slab "overlying a
# perfectly reflecting plane" (docs/rozanov-bound-primary-source.md section
# 3, assumption (b)) -- take the plane away and the bookkeeping that makes
# the bound's integral finite no longer closes.
#
# That is a different physical_bound, a different absorptivity formula, and
# a different port count -- exactly the kind of "different function, not a
# swapped constant" split ADR-0018 already uses to justify separate families
# (see the module docstring above). Bolting a per-instance
# `requires_ground_plane` override onto one `ABSORBER` family would let a
# single family answer both "the whole reflected wave either bounces or
# heats" and "a third of it is free to leave out the back" -- which is what
# produced issue #216 in the first place: `ABSORBER.requires_ground_plane =
# True` asserted for a design that ISN'T. Two families, not one flag.
# `ABSORBER_TRANSMISSIVE` is the ground-less, two-port sibling; see below.
ABSORBER = DesignFamily(
    name="ABSORBER",
    simulation_adapter=SimulationAdapter(
        name="MEEP_FLOQUET",
        reason=(
            "#109 named it and #229 wired it: a unit cell needs a periodic "
            "boundary and NEC2's thin-wire formulation cannot express one. "
            "simulation/meep.py can build what this family is made of -- a "
            "printed pattern over a ground plane, a lossy dielectric spacer, a "
            "resistive sheet -- and returns power reflectance, which for this "
            "family is the whole answer: a ground-backed surface transmits "
            "nothing, so A = 1 - |S11|^2 and no phase or transmission term is "
            "needed. Whether that adapter can yet DELIVER a given run is its "
            "own question, answered honestly in simulation/meep.py rather than "
            "guessed at here."
        ),
    ),
    description=(
        "A ground-backed surface that dissipates incident power as heat. "
        "Bandwidth comes from loss, so its bound is a thickness-versus-"
        "bandwidth inequality."
    ),
    simulation_tier=SimulationTier.TIER_A,
    requires_ground_plane=True,
    port_count=1,
    spine_fields=SPINE_FIELDS,
    analysis_model=AnalysisModel(
        name="ABSORBER_BAND_RESPONSE",
        function="rf_tools.absorber.absorber_band_response",
        answers=(
            "how much of the arriving wave this surface swallows at its WORST "
            "frequency in the required band -- the Costa/Luukkonen equivalent-"
            "circuit stack adopted at #111, scored on the single worst-absorbing "
            "frequency rather than the mean or the peak (#110's minimax rule). "
            "Legitimate for this family only because a ground-backed surface "
            "transmits nothing, so everything not reflected became heat: "
            "A = 1 - |S11|^2."
        ),
    ),
    physical_bound=PhysicalBound(
        name="Rozanov thickness-to-bandwidth bound",
        citation=(
            "K. N. Rozanov, 'Ultimate thickness to bandwidth ratio of radar "
            "absorbers', IEEE Trans. Antennas Propag. 48(8):1230-1234, 2000, "
            "doi:10.1109/8.884491"
        ),
        primary_source_doc="docs/rozanov-bound-primary-source.md",
        feasibility=physical_bounds.rozanov_min_thickness_m,
        validity=(
            "Metal-backed magnetodielectric slab at normal incidence, passive "
            "and causal materials, finite static permeability mu_s. Bounds a "
            "GROUND-BACKED reflector only -- it says nothing about a "
            "transmitting two-port structure. mu_s > 1 requires a magnetic "
            "filler actually present in the stack; a printed conductor on a "
            "dielectric host has mu_s = 1. Rozanov bounds the LOW-frequency "
            "end of a fixed thickness budget; the high end is a separate model-"
            "validity limit -- see physical_bounds.electrically_thin_ceiling_hz."
        ),
    ),
)


ABSORBER_TRANSMISSIVE = DesignFamily(
    name="ABSORBER_TRANSMISSIVE",
    simulation_adapter=SimulationAdapter(
        name="MEEP_FLOQUET",
        reason=(
            "settled at issue #243, and unsettled until then for a reason worth "
            "keeping: closing this family's energy balance needs BOTH the "
            "reflected and the transmitted wave -- A = 1 - |S11|^2 - |S21|^2 "
            "(docs/absorber-scoring-conventions.md section 1) -- and "
            "simulation/meep.py computed power reflectance only, so it could "
            "say how much bounced back but not how much went through, which "
            "here is half the answer. Issue #240 added the transmission-side "
            "monitor (opt-in via geometry's 'transmission_monitor_center_m'), "
            "and #243 made orchestration/design_loop.py select the sum from "
            "this family's declared port_count and refuse to run without a "
            "measured transmittance. The rest of the case is ABSORBER's: a "
            "unit cell needs a periodic boundary and NEC2's thin-wire "
            "formulation cannot express one. Reflectance alone would still be "
            "the wrong answer for this family -- so the adapter is named here "
            "only because it now returns the second quantity too."
        ),
    ),
    description=(
        "An unbacked, two-port absorbing surface: power that is not "
        "reflected is not guaranteed to be dissipated, since some of it may "
        "pass through. Absorptivity is A = 1 - |S11|^2 - |S21|^2, not the "
        "ground-backed collapse A = 1 - |S11|^2. This is the shape of "
        "US12089385B2's Example 3 (Landy et al.'s cut-wire absorber), this "
        "programme's blind reproduction anchor -- see the comment above "
        "ABSORBER for why that structure cannot be scored as a member of "
        "the ground-backed family."
    ),
    simulation_tier=SimulationTier.TIER_A,
    requires_ground_plane=False,
    port_count=2,
    spine_fields=SPINE_FIELDS,
    analysis_model=AnalysisModel(
        name="TRANSMISSIVE_ABSORBER_BAND_RESPONSE",
        function="rf_tools.transmissive_absorber.transmissive_absorber_band_response",
        answers=(
            "what fraction of the incident power this surface turns into heat at "
            "the single worst frequency in the required band, counting SEPARATELY "
            "the fraction that passes straight through it: A = 1 - |S11|^2 - "
            "|S21|^2 (docs/absorber-scoring-conventions.md section 1). With no "
            "metal behind it, power can leave out the back, so the ground-backed "
            "collapse A = 1 - |S11|^2 would credit as absorbed every watt that "
            "merely escaped. In plain terms: this one is a tinted window rather "
            "than a mirror, and the model says how much light gets out the far "
            "side instead of crediting the design for it. Issue #242."
        ),
    ),
    physical_bound=UnreadPhysicalBound(
        name="unbacked/transmissive absorber bandwidth bound",
        citation=(
            "Rozanov (2000) is NOT this bound -- its own opening line fixes a "
            "slab 'overlying a perfectly reflecting plane' "
            "(docs/rozanov-bound-primary-source.md section 3, assumption (b)), "
            "which Example 3 fails. Whether a published thickness-versus-"
            "bandwidth (or thickness-versus-insertion-loss) bound exists for a "
            "transmissive/unbacked absorbing screen is an open question this "
            "programme has not yet researched -- recorded as unread rather than "
            "NO_PHYSICAL_BOUND, per the same reasoning POLARIZATION_CONVERTER "
            "uses below: absence of a citation here is not evidence that no "
            "bound exists."
        ),
    ),
)


PATCH = DesignFamily(
    name="PATCH",
    simulation_adapter=SimulationAdapter(
        name="NEC2",
        reason=(
            "a wire-antenna method-of-moments solver is the RIGHT tool here, "
            "not a leftover default: a patch is a radiator over a ground plane, "
            "which is exactly NEC2's vocabulary, and simulation/nec2pp.py "
            "returns the feed-point impedance this family is scored on (#101's "
            "VSWR and return loss). Stated so it is a choice somebody made "
            "rather than a default nobody chose."
        ),
    ),
    description=(
        "A plain microstrip patch antenna: a radiator, not an absorber. "
        "Bandwidth comes from radiated power, so its bound is a quality-factor "
        "floor on a lossless substrate."
    ),
    simulation_tier=SimulationTier.TIER_A,
    requires_ground_plane=True,
    spine_fields=SPINE_FIELDS,
    analysis_model=AnalysisModel(
        name="PATCH_RESONANT_FREQUENCY",
        function="rf_tools.calculations.patch_resonant_frequency_hz",
        answers=(
            "the frequency at which this patch radiates -- the transmission-line "
            "resonance of a rectangular microstrip patch, from its length, width, "
            "substrate height and permittivity. A question about a RADIATOR, "
            "which is why it must never be asked of a surface whose whole job is "
            "to transmit nothing (issue #191)."
        ),
    ),
    physical_bound=PhysicalBound(
        name="Nel/Skrivervik/Gustafsson patch Q-factor bound",
        citation=(
            "D. Nel, A. K. Skrivervik & M. Gustafsson, 'Q-factor Bounds for "
            "Microstrip Patch Antennas', IEEE Trans. Antennas Propag., 2023, "
            "doi:10.1109/TAP.2023.3243726 (preprint: Lund TEAT-7275)"
        ),
        primary_source_doc="docs/patch-q-factor-bound-primary-source.md",
        feasibility=physical_bounds.patch_q_factor_lower_bound,
        validity=(
            "Infinite PEC ground plane, infinite LOSSLESS dielectric, PEC "
            "patch, no ohmic losses -- the denominator is radiated power plus "
            "surface-wave leakage, NOT dissipation, so this bound must never be "
            "cited against a lossy absorber. Assumes ONE dominant resonance "
            "over the bandwidth; shorting pins, stacked patches and miniaturised "
            "ground planes are explicitly excluded; two-resonance widening is "
            "listed in the source's own conclusion as future work, so the bound "
            "cannot forbid a multi-resonance design. Fifth-power scaling holds "
            "BELOW the half-wave resonance."
        ),
    ),
)


REFLECTION_PHASE = DesignFamily(
    name="REFLECTION_PHASE",
    simulation_adapter=UnsettledSimulationAdapter(
        reason=(
            "this family is designed by its per-cell reflection PHASE -- how far "
            "a bounce off one cell shifts the wave's timing -- and neither "
            "adapter in this repo can pose that question for the structure this "
            "family is made of. simulation/meep.py can BUILD the structure (a "
            "printed conductor over a ground plane, repeating in the plane) but "
            "returns power reflectance only: its own scope section says 'NO "
            "complex phase'. simulation/palace.py DOES return phase, validated "
            "against a real Palace binary to within 0.91 degrees on Palace's own "
            "dielectric-grating example (issue #210, "
            "docs/palace-floquet-validation.md) -- but its scope section says "
            "'Embedded PEC conductor patches (the metallic-metasurface case ...) "
            "are NOT implemented', and a printed metal cell over a ground plane "
            "is exactly that case. Each candidate is one named, unbuilt "
            "capability away, and nothing read here establishes which is the "
            "route; the design loop has no Palace handler wired either. Writing "
            "a plausible-looking name down today would reintroduce the very "
            "defect #241 removed, one layer up."
        ),
        candidates=(
            "PALACE_FLOQUET -- has the phase, cannot yet mesh an embedded metal "
            "patch (simulation/palace.py SCOPE)",
            "MEEP_FLOQUET -- has the structure, extracts no phase (simulation/meep.py SCOPE)",
        ),
        cheapest_test=(
            "take one cell whose reflection-phase curve is published -- a square "
            "patch over a grounded spacer, whose phase passes through zero at a "
            "stated frequency -- and try to reproduce that curve. Whichever "
            "candidate reproduces it once its missing capability is added is the "
            "adapter; until one does, neither name is more than a guess."
        ),
    ),
    description=(
        "A reflection-phase steering surface: a ground-backed array whose "
        "per-cell reflection phase steers or shapes the reflected beam. The "
        "designed-for behaviour exists only at aperture level, so the unit-cell "
        "solve populates a phase lookup rather than answering the question."
    ),
    simulation_tier=SimulationTier.TIER_B,
    requires_ground_plane=True,
    spine_fields=SPINE_FIELDS,
    # Deliberately nothing to declare, not an omission (#239). What this
    # family needs is a per-cell reflection PHASE -- by how much a bounce off
    # one cell shifts the wave's timing -- and no closed form in this repo
    # returns a phase at all: rf_tools.calculations offers a patch resonance,
    # rf_tools.absorber a magnitude. Its Tier B evaluation then needs an
    # aperture-level step on top of that per-cell lookup, which no module here
    # performs either. The patch resonant frequency is not a weaker answer to
    # this question; it is the answer to a different one.
    analysis_model=UndeclaredAnalysisModel(
        reason=(
            "a reflection-phase surface is designed by its per-cell reflection "
            "PHASE, and no closed form in rf_tools returns a phase "
            "(rf_tools.calculations returns a patch resonant frequency; "
            "rf_tools.absorber returns an absorbed fraction). The Tier B "
            "aperture-level step that would turn a per-cell phase lookup into a "
            "steered beam does not exist here either. Both are open work, not "
            "settled models -- see issue #109 for the family and ADR-0022 for "
            "the mechanism-before-prediction rule any new model owes."
        ),
    ),
    physical_bound=UnreadPhysicalBound(
        name="Gustafsson & Sjoberg phase-window bound",
        citation=(
            "M. Gustafsson & D. Sjoberg, bound on reflection-phase range versus "
            "bandwidth/thickness, as named in issue #109 -- primary source NOT "
            "yet read by this programme"
        ),
    ),
)


DIFFUSIVE = DesignFamily(
    name="DIFFUSIVE",
    simulation_adapter=UnsettledSimulationAdapter(
        reason=(
            "a coding/diffusive cell IS its reflection phase -- a '0' and a '1' "
            "are two cells 180 degrees apart -- so this family needs exactly the "
            "per-cell phase REFLECTION_PHASE needs, and hits the same wall: "
            "simulation/meep.py can build a printed cell over a ground plane but "
            "extracts no phase ('NO complex phase', its own scope section), and "
            "simulation/palace.py returns phase (validated against a real binary, "
            "issue #210) but cannot yet mesh an embedded metal patch ('Embedded "
            "PEC conductor patches ... are NOT implemented'). On top of that, "
            "what this family is actually scored on -- how much backscatter the "
            "whole ARRANGEMENT redistributes away from the radar -- lives above "
            "the unit cell (that is what makes it Tier B), and no module here "
            "performs that aperture-level step. Two unbuilt capabilities, no "
            "established route: recorded as unsettled rather than guessed."
        ),
        candidates=(
            "PALACE_FLOQUET -- has the phase, cannot yet mesh an embedded metal "
            "patch (simulation/palace.py SCOPE)",
            "MEEP_FLOQUET -- has the structure, extracts no phase (simulation/meep.py SCOPE)",
        ),
        cheapest_test=(
            "the same per-cell reflection-phase reproduction REFLECTION_PHASE "
            "names -- both families are blocked on the same missing quantity, so "
            "one experiment settles the unit-cell half for both. The "
            "aperture-level scattering step is separate work and would still be "
            "unbuilt afterwards."
        ),
    ),
    description=(
        "A coding/diffusive backscatter-reduction surface. It redistributes "
        "scattered power into many directions rather than absorbing it, so "
        "monostatic reduction is achieved without dissipation."
    ),
    simulation_tier=SimulationTier.TIER_B,
    requires_ground_plane=True,
    spine_fields=SPINE_FIELDS,
    # Deliberately nothing to declare (#239), for the same reason as
    # REFLECTION_PHASE and one more. A coding cell IS its reflection phase --
    # a "0" and a "1" differ by 180 degrees of it -- so this family needs the
    # same per-cell phase no closed form here returns; and what it is scored
    # on, how much backscatter the whole arrangement redistributes away from
    # the radar, exists only at aperture level, above any unit cell.
    analysis_model=UndeclaredAnalysisModel(
        reason=(
            "a coding/diffusive cell is DEFINED by its reflection phase (a '0' "
            "and a '1' are cells 180 degrees apart), and no closed form in "
            "rf_tools returns a phase. Its figure of merit -- monostatic "
            "backscatter reduction -- is an aperture-level scattering pattern "
            "over an arrangement of those cells, which is a second missing "
            "model on top of the first, and is why this family is Tier B."
        ),
    ),
    physical_bound=NO_PHYSICAL_BOUND,
)


POLARIZATION_CONVERTER = DesignFamily(
    name="POLARIZATION_CONVERTER",
    simulation_adapter=UnsettledSimulationAdapter(
        reason=(
            "this family is scored on the CROSS-polarised reflection: how much "
            "of the wave comes back with its field turned, which is a different "
            "quantity from the one that went in. Only one adapter here can even "
            "express it -- simulation/palace.py reports both polarisations of "
            "every diffraction order, and issue #210 found the hard way that "
            "they are not interchangeable (its 'specular' convenience view "
            "silently returned a cross-polarised channel at -158 dB, numerical "
            "noise, in place of a true -18.9 dB reflection). simulation/meep.py "
            "cannot: it computes a single scalar power reflectance with no "
            "polarisation channels at all, so there is no cross-polarised term "
            "to read. But Palace's adapter cannot yet build a printed metal cell "
            "('Embedded PEC conductor patches ... are NOT implemented'), and an "
            "anisotropic printed pattern is what a polarisation converter IS. So "
            "the destination is clearer here than for REFLECTION_PHASE and "
            "DIFFUSIVE -- Palace is the only adapter with the observable -- but "
            "it is still one unbuilt capability away and the loop has no Palace "
            "handler wired, so this is recorded as unsettled rather than "
            "declared."
        ),
        candidates=(
            "PALACE_FLOQUET -- the only adapter reporting a cross-polarised "
            "channel; cannot yet mesh an embedded metal patch "
            "(simulation/palace.py SCOPE)",
        ),
        cheapest_test=(
            "hand simulation/palace.py an all-dielectric ANISOTROPIC cell -- a "
            "geometry it can already mesh -- and check that the cross-polarised "
            "specular channel climbs out of the noise floor when the cell's two "
            "axes are made unequal and sinks back into it when they are equal. "
            "That settles whether the observable is usable at all before anyone "
            "spends effort building embedded-PEC meshing."
        ),
    ),
    description=(
        "A surface that rotates or converts the polarisation of the reflected "
        "wave (e.g. linear-to-cross, linear-to-circular), typically via an "
        "anisotropic cell with two unequal principal-axis responses."
    ),
    simulation_tier=SimulationTier.TIER_A,
    requires_ground_plane=True,
    spine_fields=SPINE_FIELDS,
    # Deliberately nothing to declare (#239). This family is scored on the
    # CROSS-polarised reflection: how much of the wave comes back with its
    # field turned, which is a different quantity from the one that went in.
    # Every closed form in rf_tools is scalar -- one incident field, one
    # returned number -- so none of them can express two principal axes with
    # unequal responses, let alone the difference between them.
    analysis_model=UndeclaredAnalysisModel(
        reason=(
            "polarisation conversion is scored on the CROSS-polarised reflection "
            "(the part of the wave that comes back with its field rotated), and "
            "every closed form in rf_tools is scalar -- one incident field in, "
            "one number out. None of them can represent an anisotropic cell's "
            "two principal-axis responses, so none can produce the co- versus "
            "cross-polarised split this family is judged on. No such model has "
            "been read or written here yet."
        ),
    ),
    physical_bound=UnreadPhysicalBound(
        name="polarization-conversion bandwidth bound",
        citation=(
            "No bound named for this family in issue #109 and none read by this "
            "programme. CONTEXT.md lists polarization converter as a design "
            "family; whether a fundamental bound exists for it is itself an open "
            "question, so this is recorded as unread rather than as "
            "NO_PHYSICAL_BOUND -- absence of a citation is not evidence that no "
            "bound exists."
        ),
    ),
)


_REGISTRY: dict[str, DesignFamily] = {
    fam.name: fam
    for fam in (
        ABSORBER,
        ABSORBER_TRANSMISSIVE,
        PATCH,
        REFLECTION_PHASE,
        DIFFUSIVE,
        POLARIZATION_CONVERTER,
    )
}


# Names already written into this repo's ARCHITECTURE decisions before the
# registry existed, mapped to their canonical family. ADR-0018 named the
# canonical key for the patch family as `PATCH` and made retrofitting the
# existing patch code the registry's own validation test -- "if the existing
# patch code doesn't fit, the shape is wrong." It fits; what it needed was
# these aliases. Aliases are recorded here rather than silently accepted by
# fuzzy matching, so every accepted spelling is one a human can see and
# audit.
#
# HOW THIS LIST WAS DERIVED, AND WHY THAT IS RECORDED. Because
# `get_design_family` REJECTS what it does not recognise, every family
# spelling already in the tree is something this registry can newly break.
# The list below is therefore not a guess at plausible spellings -- an
# earlier revision was exactly that, and it broke
# tests/test_tooling.py::test_flush_design_family_carry_forward_is_scoped_to
# _its_own_iteration, which uses "reflection_phase_surface". It is harvested
# from the tree:
#
#   grep -rhoE 'design_family[[:space:]]*[=:][[:space:]]*"[^"]+"' \
#       --include=*.py --include=*.md --include=*.json . | ...
#
# run at commit d0a38fe (merge of origin/main 03cf1fd), which yields exactly
# `patch_antenna` and `reflection_phase_surface` as pre-existing spellings.
# ANY future addition to this file should re-run that harvest against a
# NAMED commit rather than reasoning about what names probably exist -- a
# stale checkout is what produced the earlier miss, and a "that string isn't
# in the repo" claim is only as good as the commit it was checked at.
_ALIASES: dict[str, str] = {
    # Harvested from the tree (see above).
    "PATCH_ANTENNA": PATCH.name,
    "REFLECTION_PHASE_SURFACE": REFLECTION_PHASE.name,
    # Near-spellings of the harvested and canonical names. These are
    # convenience only -- nothing in the tree uses them -- and they are the
    # part of this table that may be dropped without breaking anything.
    "MICROSTRIP_PATCH": PATCH.name,
    "REFLECTION_PHASE_STEERING_SURFACE": REFLECTION_PHASE.name,
    "STEERING_SURFACE": REFLECTION_PHASE.name,
    "DIFFUSIVE_BACKSCATTER_SURFACE": DIFFUSIVE.name,
    "CODING": DIFFUSIVE.name,
    "POLARIZATION_CONVERTOR": POLARIZATION_CONVERTER.name,
    "POLARISATION_CONVERTER": POLARIZATION_CONVERTER.name,
}


class UnknownDesignFamilyError(ValueError):
    """Raised when an ARCHITECTURE decision names a family the registry does
    not hold."""


def known_family_names() -> tuple[str, ...]:
    """Every registered family name, sorted -- for error messages and for a
    caller offering a choice."""
    return tuple(sorted(_REGISTRY))


def get_design_family(name: str) -> DesignFamily:
    """Look up a family by name, case-insensitively.

    Raises `UnknownDesignFamilyError` naming the known families, rather than
    returning None: a design loop that recorded an unrecognised family string
    has recorded something #150 and #151 cannot group by, and the failure
    should surface at the ARCHITECTURE step rather than three steps later.
    """
    if not isinstance(name, str) or not name.strip():
        raise UnknownDesignFamilyError(
            f"design_family must be a non-empty string; got {name!r}. "
            f"Known families: {', '.join(known_family_names())}."
        )
    key = name.strip().upper().replace("-", "_").replace(" ", "_")
    family = _REGISTRY.get(key) or _REGISTRY.get(_ALIASES.get(key, ""))
    if family is None:
        raise UnknownDesignFamilyError(
            f"Unknown design_family {name!r}. Known families: "
            f"{', '.join(known_family_names())}. Selection stays human-authored "
            "(CONTEXT.md: the loop does not infer a family from a requirement's "
            "prose), so this is a typo or a family that needs registering in "
            "designs/design_families.py -- not something to guess past."
        )
    return family


def is_known_design_family(name: str) -> bool:
    """Non-raising form of `get_design_family`."""
    try:
        get_design_family(name)
    except UnknownDesignFamilyError:
        return False
    return True
