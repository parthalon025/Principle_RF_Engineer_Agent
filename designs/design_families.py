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
which is precisely the failure the Provenance ladder exists to prevent -- and
a silent `None` would have made "we never looked" indistinguishable from
"there is nothing to look for".

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
        raise TypeError(
            "This design family has no physical bound to evaluate: " + self.reason
        )


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
    (`physical_bound`, `optimizer_class`, `simulation_adapter`) are declared
    as open values, never closed two-literal enums, per ADR-0018's
    Consequences: both have a credible third value on the horizon.
    """

    name: str
    description: str
    simulation_tier: SimulationTier
    physical_bound: PhysicalBoundSlot
    requires_ground_plane: bool
    spine_fields: frozenset[str] = field(default_factory=frozenset)
    optimizer_class: str | None = None
    simulation_adapter: str | None = None

    @property
    def has_physical_bound(self) -> bool:
        """True only when a bound is available to CALL.

        False for both an unread bound and a family with no bound -- which is
        why the two are separate types rather than one falsy value: a caller
        that needs to explain WHY gets a different answer from each.
        """
        return isinstance(self.physical_bound, PhysicalBound)


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


ABSORBER = DesignFamily(
    name="ABSORBER",
    description=(
        "A ground-backed surface that dissipates incident power as heat. "
        "Bandwidth comes from loss, so its bound is a thickness-versus-"
        "bandwidth inequality."
    ),
    simulation_tier=SimulationTier.TIER_A,
    requires_ground_plane=True,
    spine_fields=SPINE_FIELDS,
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


PATCH = DesignFamily(
    name="PATCH",
    description=(
        "A plain microstrip patch antenna: a radiator, not an absorber. "
        "Bandwidth comes from radiated power, so its bound is a quality-factor "
        "floor on a lossless substrate."
    ),
    simulation_tier=SimulationTier.TIER_A,
    requires_ground_plane=True,
    spine_fields=SPINE_FIELDS,
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
    description=(
        "A reflection-phase steering surface: a ground-backed array whose "
        "per-cell reflection phase steers or shapes the reflected beam. The "
        "designed-for behaviour exists only at aperture level, so the unit-cell "
        "solve populates a phase lookup rather than answering the question."
    ),
    simulation_tier=SimulationTier.TIER_B,
    requires_ground_plane=True,
    spine_fields=SPINE_FIELDS,
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
    description=(
        "A coding/diffusive backscatter-reduction surface. It redistributes "
        "scattered power into many directions rather than absorbing it, so "
        "monostatic reduction is achieved without dissipation."
    ),
    simulation_tier=SimulationTier.TIER_B,
    requires_ground_plane=True,
    spine_fields=SPINE_FIELDS,
    physical_bound=NO_PHYSICAL_BOUND,
)


POLARIZATION_CONVERTER = DesignFamily(
    name="POLARIZATION_CONVERTER",
    description=(
        "A surface that rotates or converts the polarisation of the reflected "
        "wave (e.g. linear-to-cross, linear-to-circular), typically via an "
        "anisotropic cell with two unequal principal-axis responses."
    ),
    simulation_tier=SimulationTier.TIER_A,
    requires_ground_plane=True,
    spine_fields=SPINE_FIELDS,
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
    for fam in (ABSORBER, PATCH, REFLECTION_PHASE, DIFFUSIVE, POLARIZATION_CONVERTER)
}


# Names already written into this repo's ARCHITECTURE decisions before the
# registry existed, mapped to their canonical family. ADR-0018 named the
# canonical key for the patch family as `PATCH` and made retrofitting the
# existing patch code the registry's own validation test -- "if the existing
# patch code doesn't fit, the shape is wrong." It fits; what it needed was
# this alias, because `patch_antenna` is the string seven existing call
# sites and tests already use. Aliases are recorded here rather than
# silently accepted by fuzzy matching, so every accepted spelling is one a
# human can see and audit.
_ALIASES: dict[str, str] = {
    "PATCH_ANTENNA": PATCH.name,
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
