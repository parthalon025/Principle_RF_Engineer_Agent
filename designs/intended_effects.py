"""The Intended-effect reference library -- what each named effect is scored
on, on what fixture, against what physical bound, and by which design
families (ADR-0030, ADR-0047, ADR-0018; CONTEXT.md: Intended effect, Design
family, Design family registry, Physical bound, Capability warning).

WHAT THIS IS, AND -- LOUDLY -- WHAT IT IS NOT.

**ADR-0030 decides that `intended_effect` is an open-vocabulary KEY on a
Customer requirement, not a record of its own.** This module does not touch
that decision and must never be made to. It is a *reference lookup* over two
kinds of fact:

  * facts about physics -- which quantity an effect is scored on, on what
    measurement fixture, and which published bound (if any) governs it; and
  * facts about this repo's own registry -- which entries in
    `designs/design_families.py` serve that effect today, and which effects
    nothing in the registry serves at all.

Neither kind is a fact about any one requirement. So this module holds no
requirement records, mints no provenance rung, and is deliberately NOT
imported by `designs/requirement_targets.py`: `propose_intended_effect`
still accepts any non-empty string and still tags it `ASSUMED`, exactly as
ADR-0030 requires. Wiring this library in as an intake validator would
convert an open vocabulary into a closed enum and supersede ADR-0030; see
`docs/adr/0049-*.md` for why that was considered and rejected.

THE MISS GUARANTEE. `resolve_intended_effect` returns an `EffectMiss` for an
effect it does not recognise. It never raises, never rejects, never drops a
candidate, and the caller carries on with a requirement this library knows
nothing about -- which is the normal case for an open vocabulary, not an
error. `families_serving`, `scoring_quantity`, `objective_sense` and
`physical_bound_for` return the same `EffectMiss` rather than raising, so a
caller distinguishes "unknown effect" from "known effect, nothing to report"
by TYPE rather than by a bare `None` -- the same discipline
`designs/design_families.py`'s module docstring is built on.

ONLY PHYSICS BLOCKS ANYTHING. Nothing here gates. Where this library knows an
effect has no design family behind it, that is a `FamilyGap` handed to the
caller -- shaped like a **Capability warning** (a precise value/comparator/
unit statement rather than prose) but explicitly NOT one, and not a
`capability-verdict` either. See `FamilyGap`'s own docstring.

--------------------------------------------------------------------------
THE FOUR FINDINGS THIS LIBRARY EXISTS TO EXPOSE
--------------------------------------------------------------------------

**1. One of the eight effects here has no design family, and it stays that
way on purpose.** `effects_without_family()` is the live report; today it
returns exactly `low infrared emissivity`. Until ADR-0050 it returned three --
`transmitted` and `shielded against` were the other two, both named in
CONTEXT.md's own list of seven -- and closing those two is what this
docstring used to spend most of its words justifying. Both now resolve to a
registered family (`BANDPASS_FSS`, `SHIELD`); `low infrared emissivity` does
not, and ADR-0050 argued that case rather than merely leaving it open -- see
finding 3.

**The `transmitted` gap is closed, and the arithmetic that justified closing
it is worth keeping on record**, because it is the whole reason
`BANDPASS_FSS` exists rather than a flag on `ABSORBER_TRANSMISSIVE`. Before
ADR-0050, a radome or bandpass FSS -- a real, printable architecture in this
repo (ADR-0017's 2026-09-06 correction: "A bandpass needs **exactly one**
patterned layer and no backing at all") -- had no family to be filed under,
so it would have been forced into `ABSORBER_TRANSMISSIVE`, the only
ground-less two-port family that existed then. That family's
`analysis_model` scores worst-in-band ABSORPTIVITY, `A = 1 - |S11|^2 -
|S21|^2`. Take MIL-R-7705B Table 1's own sample electrical limits
(`docs/military-requirements-vocabulary.md` section 5): power reflection 2
percent, one-way power transmission 85-95 percent. A radome meeting them --
say 2 percent reflected and 92 percent transmitted -- scores
`A = 1 - 0.02 - 0.92 = 0.06` (`CALCULATED` from exactly those two stated
inputs), against ADR-0041's 0.90 default absorption threshold. **A part that
does its job nearly perfectly ranks last.** The same part scores 0.92 on
transmittance, which is what the requirement actually asked for. A second,
measured worked example carries the identical arithmetic and lives on
`TRANSMITTED.notes` now that there is no `FamilyGap` left to hold it: a
screen-printed Ti3C2Tx chessboard FSS reported at 78 percent transmittance
and 16 percent reflectivity has `A = 1 - 0.16 - 0.78 = 0.06`.

*In plain terms: a window and a sponge are graded on opposite things. Grade
the window as a sponge and the best window in the room comes bottom of the
class.* `objective_sense` and the per-quantity senses below are the field
that prevents this.

**The `shielded against` gap is also closed** -- `SHIELD` is now its family
-- but naming the family did not make it scoreable: `SHIELD` still carries
`UndeclaredAnalysisModel` and `UnbuiltPostProcess` (ADR-0050), so a
`shielded against` requirement still cannot be run through the loop today.
It is also still true, independent of the registry, that shielding
effectiveness is nearly informationless under this programme's default
ground-backed architecture -- see finding 2, which that architecture
question does not depend on which family, if any, is named.

**2. `shielded against` may not be a scoreable ask under this programme's own
default architecture.** Shielding effectiveness is a two-port transmission
quantity, `SE_dB = -20*log10|S21|`. ADR-0017 makes every skin here print its
own conductive reflector by default, and a ground-backed structure has zero
transmission by construction (`designs/design_families.py`'s `__post_init__`
states this as the reason `requires_ground_plane=True` forces
`port_count=1`). So `|S21| = 0`, `SE` is unbounded, and the number carries no
design information *for that architecture*. It discriminates only for an
unbacked stack -- one where a requirement has explicitly asserted that no
reflector is wanted, which ADR-0017's correction already provides for. This
is recorded, not resolved: whether "shielded against" is a distinct effect or
a restatement of "transmitted" with the sense flipped is a question for the
glossary, not for this file.

**3. Low infrared emissivity is a real behaviour and it is absent from
CONTEXT.md's seven.** The seven are, verbatim: absorbed, reflected in phase,
steered, transmitted, scattered diffusely, polarisation-converted, shielded
against. A radar-plus-infrared skin is live work here --
`docs/five-paper-absorber-corpus-findings.md` section 4 calls it "the
architecture the DEVCOM context makes live" and gives it a number: a
resistive infrared overlay must exceed **407 ohm/sq** to leave a 90 percent
microwave absorption floor intact, and **1,695 ohm/sq** for a 99 percent
floor (`CALCULATED`). That is a design rule about an effect the glossary does
not name. This module names it so the absence is visible and queryable. It
does **not** assert that it belongs in CONTEXT.md's list -- that is a
`/domain-modeling` decision with its own owner, and this file does not touch
CONTEXT.md.

**ADR-0050 went further than naming it: it examined registering a design
family for this effect and declined, in writing.** Applying ADR-0027 section
5's four-plug-in family test honestly returns four nothings -- no
`physical_bound`, no `analysis_model`, no `optimizer_class`, no
`simulation_adapter` -- and `DesignFamily.__post_init__` refuses the attempt
on physics regardless: it requires `requires_ground_plane=True` to pair with
`port_count=1` and `False` with `port_count=2`, and an infrared layer is not
an S-parameter measurement at all, so it has no ports to declare either way.
What ADR-0050 concludes instead is that low infrared emissivity is a
**co-design constraint on a candidate whose family is set by its radar
behaviour**, not a family of its own -- and the constraint already has a
number, usable today with no registry change: see
`LOW_INFRARED_EMISSIVITY.family_gap`, whose `status` now reads
`GapReason.DELIBERATELY_DECLINED` rather than `OUTSTANDING_WORK`, precisely
so a later reader cannot "helpfully" register a family here without
reopening that ADR.

**4. `PATCH` serves none of the eight effects, and that is a second gap in
the other direction.** `families_without_effect()` returns `("PATCH",)`. A
patch antenna does not do something to an arriving wave; it radiates one.
"Radiated" is not among CONTEXT.md's seven either. Recorded here as a finding
rather than fixed by minting a `radiated` profile, for the same reason as
finding 3: extending the glossary is not this module's job. The value of the
report is that adding a SEVENTH design family to the registry without wiring
it into this library will make `tests/test_intended_effects.py` fail loudly,
rather than silently leaving a family no effect can reach.

--------------------------------------------------------------------------
A DISCREPANCY THIS LIBRARY REPORTS AND DOES NOT ADJUDICATE
--------------------------------------------------------------------------

The Gustafsson & Sjoberg high-impedance-surface bound is carried by
`designs/design_families.py` as an `UnreadPhysicalBound` -- "primary source
NOT yet read by this programme". But `docs/absorber-thickness-bandwidth-
bound.md` section 7.1 quotes that paper's Eqs. (4.10), (4.11) and (5.1)
verbatim from the open-access Lund author manuscript, and ADR-0047 states the
resulting number (`B*lambda_0/d <= 2.6` at `Phi = pi/2`) as settled content.
Those two cannot both be true. Each `EffectBound` carries a `registry_state`
field recording what the registry says alongside `form`/`citation` recording
what the doc says, so a caller sees both rather than one silently winning.
Resolving it means either reading the paper first-hand and replacing the
marker, or correcting the doc -- and it belongs in `designs/design_families.py`
and on a ticket, not here.

--------------------------------------------------------------------------
MODULE SHAPE
--------------------------------------------------------------------------

A deep module: a small function surface (`resolve_intended_effect`,
`families_serving`, `effects_without_family`, `families_without_effect`,
`scoring_quantity`, `objective_sense`, `physical_bound_for`,
`known_effect_names`, `diffracted_order_min_period_m`) over a lot of content.
Pure and dependency-free apart from `designs.design_families`, which it reads
so the family mapping cannot name a family the registry does not hold -- a
rename there breaks this module at import, which is a code error a developer
sees immediately, never a runtime gate on somebody's requirement.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType
from typing import Any

from designs import design_families

# Speed of light in vacuum, m/s (CODATA exact). Used only by
# `diffracted_order_min_period_m`.
_C_M_S = 299_792_458.0


# --------------------------------------------------------------------------
# The vocabularies: what an effect is scored on, and which way is better
# --------------------------------------------------------------------------


class ScoringQuantity(StrEnum):
    """The quantity an intended effect is actually graded on.

    These are NOT interchangeable. They are different physical quantities,
    measured on different fixtures, with different units and different senses
    -- which is the whole reason this enum exists rather than one "score"
    float. Grading a radome on ABSORPTIVITY instead of TRANSMITTANCE is not a
    rougher answer to the same question; it is a precise answer to a
    different one, and it inverts the ranking (see this module's docstring,
    finding 1).

    ABSORPTIVITY and REFLECTION_LOSS collapse into one quantity ONLY on a
    metal-backed one-port fixture, where nothing transmits and therefore
    everything not reflected became heat: ADR-0041 states the identity
    directly -- "-10 dB reflectivity => |S11|^2 = 0.100 => A = 0.900 -- one
    quantity, not three". Off that fixture they come apart: a radome's
    reflection loss (MIL-R-7705B 3.4.1.2, "power reflected back into the
    antenna") says nothing about how much was absorbed versus transmitted.
    """

    ABSORPTIVITY = "absorptivity"
    REFLECTION_LOSS = "reflection loss"
    REFLECTION_PHASE = "reflection phase"
    TRANSMITTANCE = "transmittance"
    RCS_REDUCTION = "monostatic RCS reduction"
    CROSS_POLARISATION_RATIO = "cross-polarisation ratio"
    SHIELDING_EFFECTIVENESS = "shielding effectiveness"
    EMISSIVITY = "emissivity"


class ObjectiveSense(StrEnum):
    """Which direction is better for the quantity an effect is scored on.

    MAXIMISE and MINIMISE are the obvious two. HOLD_IN_WINDOW is the third
    and is not a hedge: a reflection phase has no "more is better" direction
    at all -- the design target is to keep it inside a stated window (the
    familiar +/-45 degree AMC criterion, `Phi = pi/2` in Gustafsson &
    Sjoberg's Eq. 5.1), and both too much and too little are equally wrong.
    Forcing it into MAXIMISE/MINIMISE would be the same category error this
    module exists to catch, one level down.
    """

    MAXIMISE = "maximise"
    MINIMISE = "minimise"
    HOLD_IN_WINDOW = "hold in window"


# --------------------------------------------------------------------------
# Fixture: the measurement setup a quantity is only meaningful on
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Fixture:
    """The measurement setup an effect's scoring quantity lives on.

    `port_count` is `None` when the fixture is not an RF S-parameter
    measurement at all (the infrared emittance case), rather than 0 -- 0
    would read as "a two-port measurement with no ports", which is a
    different and impossible thing. Same discipline as
    `designs/design_families.py`'s refusal of a bare `None` for
    `physical_bound`: distinct states get distinct representations.
    """

    name: str
    port_count: int | None
    plainly: str
    note: str = ""


ONE_PORT_METAL_BACKED = Fixture(
    name="one-port, metal-backed",
    port_count=1,
    plainly=(
        "the surface has a conductor behind it, so nothing gets through; the "
        "only thing to measure is what bounces back"
    ),
    note=(
        "This programme's default architecture (ADR-0017: the base printed layer "
        "always supplies its own reflector). Zero transmission by construction, "
        "so A = 1 - |S11|^2 closes the energy balance from the reflected wave "
        "alone -- and so Rozanov's own assumption (b), a slab 'overlying a "
        "perfectly reflecting plane', is satisfied. "
        "designs/design_families.py's DesignFamily.__post_init__ enforces the "
        "pairing requires_ground_plane=True <-> port_count=1."
    ),
)

TWO_PORT_TRANSMISSION = Fixture(
    name="two-port, unbacked",
    port_count=2,
    plainly=(
        "there is nothing solid behind the surface, so some of the wave goes "
        "through it; you have to measure both what bounces back and what comes "
        "out the far side"
    ),
    note=(
        "A = 1 - |S11|^2 - |S21|^2 (docs/absorber-scoring-conventions.md section "
        "1). The ground-backed collapse A = 1 - |S11|^2 would credit as absorbed "
        "every watt that merely escaped out the back. Any effect whose scored "
        "quantity is TRANSMITTANCE or SHIELDING_EFFECTIVENESS needs this "
        "fixture; on the one-port fixture those quantities are 0 and infinity "
        "respectively, by construction, and carry no design information."
    ),
)

ONE_PORT_METAL_BACKED_TWO_POLARISATIONS = Fixture(
    name="one-port, metal-backed, both polarisation channels",
    port_count=1,
    plainly=(
        "same single-sided measurement as a mirror-backed surface, but you have "
        "to record the wave's orientation as well as its strength -- the point "
        "is how much comes back turned sideways"
    ),
    note=(
        "One port, but a scalar reflectance is not enough: the scored quantity "
        "is the CROSS-polarised channel, and issue #210 found the hard way that "
        "the two channels are not interchangeable -- a 'specular' convenience "
        "view returned a cross-polarised channel at -158 dB (numerical noise) in "
        "place of a true -18.9 dB reflection. See POLARIZATION_CONVERTER's "
        "UnsettledSimulationAdapter in designs/design_families.py."
    ),
)

APERTURE_OVER_ONE_PORT_CELLS = Fixture(
    name="aperture-level, over a one-port unit-cell phase lookup",
    port_count=1,
    plainly=(
        "one tile on its own tells you nothing here -- you measure each tile's "
        "timing shift, then work out what the whole patch of tiles does to the "
        "beam"
    ),
    note=(
        "The Tier B shape (CONTEXT.md: Simulation tier; ADR-0045). The unit-cell "
        "solve only populates a phase-versus-parameter lookup; the designed-for "
        "behaviour -- a steered beam, a suppressed backscatter lobe -- does not "
        "exist at unit-cell level at all. No module in this repo performs the "
        "aperture-level step yet, which is why REFLECTION_PHASE and DIFFUSIVE "
        "both carry an UndeclaredAnalysisModel."
    ),
)

INFRARED_EMITTANCE = Fixture(
    name="infrared emittance / reflectance, not an RF fixture",
    port_count=None,
    plainly=(
        "measured with an infrared instrument, not a radio one -- how much heat "
        "the surface radiates compared with a perfect emitter at the same "
        "temperature"
    ),
    note=(
        "By Kirchhoff's law emissivity equals absorptivity AT THE SAME "
        "WAVELENGTH, so this is not the microwave absorptivity every other "
        "effect here is scored on -- it is three to four orders of magnitude "
        "away in frequency. That separation is exactly what makes a "
        "radar-plus-infrared skin designable rather than self-contradictory "
        "(docs/five-paper-absorber-corpus-findings.md section 4)."
    ),
)


# --------------------------------------------------------------------------
# Physical bound: four distinct states, never a bare None
# --------------------------------------------------------------------------


class BoundStatus(StrEnum):
    """Why an effect does or does not have a governing physical bound.

    Four states, kept apart for the reason ADR-0018 gives for keeping
    `NO_PHYSICAL_BOUND` and `UnreadPhysicalBound` apart: a single falsy value
    would make "we looked and there is nothing to find" indistinguishable
    from "nobody has looked", and those carry opposite instructions.

    PUBLISHED           -- a bound exists, is cited, and its form is recorded.
    NONE_PUBLISHED      -- searched, and the authors themselves say the bound
                           does not exist yet. A positive finding, not a gap.
    EXEMPT_BY_MECHANISM -- a bound of that shape does not govern this
                           mechanism at all, subject to stated preconditions.
    NOT_ESTABLISHED     -- nobody here has researched it. Absence of a
                           citation is not evidence that no bound exists.
    """

    PUBLISHED = "published"
    NONE_PUBLISHED = "none published"
    EXEMPT_BY_MECHANISM = "exempt by mechanism"
    NOT_ESTABLISHED = "not established"


@dataclass(frozen=True)
class BoundPrecondition:
    """One condition that must hold before a bound (or an exemption from one)
    may be relied on.

    `check` is a real callable where the condition is arithmetic and this
    module can compute it, and `None` where it is a statement about the
    design's mechanism that only the model can make. Recording `None` is
    informative rather than lazy: it says out loud that this precondition
    cannot be discharged by a calculation, which is exactly the kind of thing
    the charter's "when stuck, name the missing measurement" rule wants
    visible.

    Per ADR-0047 this ADVISES and never gates. A caller that cannot discharge
    a precondition reports that alongside the candidate; it never drops the
    candidate.
    """

    key: str
    question: str
    why_it_matters: str
    check: Callable[..., Any] | None = None
    check_signature: str = ""


def diffracted_order_min_period_m(
    frequency_hz: float,
    order: tuple[int, int] = (1, 1),
) -> float:
    """Smallest supercell period `D` at which the `(m, n)` diffracted order
    propagates rather than evanesces, at NORMAL incidence.

    The grating condition at normal incidence is
    `sqrt((m*lambda/D)^2 + (n*lambda/D)^2) <= 1`, so the order propagates
    only when `D >= sqrt(m^2 + n^2) * lambda`. The default `(1, 1)` is the
    checkerboard case: a checkerboard cancels the specular `(0, 0)` order by
    construction, so the first orders it can actually push power into are the
    DIAGONAL ones -- hence `sqrt(2) * lambda`, not `lambda`.

    *In plain terms: the tiles have to be laid out in a patch at least this
    big before the surface can genuinely throw the wave sideways instead of
    just muffling it. Below that size there is nowhere for the power to go,
    so it has to be absorbed -- and then the absorber's thickness bound is
    back in force.*

    Worked, at the two frequencies this repo's own band work uses:
    10 GHz gives 42.4 mm, 14 GHz gives 30.3 mm.

    Raises `ValueError` on a non-positive or non-finite frequency, and on a
    zero order (`(0, 0)` is the specular direction, which is not a
    diffracted order and has no cutoff). That is a programming error in the
    caller, not a judgment about anybody's design -- nothing here gates a
    candidate.
    """
    if not isinstance(frequency_hz, (int, float)) or isinstance(frequency_hz, bool):
        raise ValueError(f"frequency_hz must be a real number; got {frequency_hz!r}")
    if not math.isfinite(frequency_hz) or frequency_hz <= 0.0:
        raise ValueError(f"frequency_hz must be finite and positive; got {frequency_hz!r}")
    m, n = order
    radius = math.hypot(m, n)
    if radius == 0.0:
        raise ValueError(
            "order (0, 0) is the specular direction, not a diffracted order; it "
            "has no propagation cutoff. Pass (1, 1) for a checkerboard's diagonal "
            "orders or (1, 0) for the axial ones."
        )
    return radius * (_C_M_S / float(frequency_hz))


DIFFUSIVE_REDISTRIBUTION_PRECONDITION = BoundPrecondition(
    key="redistributes_rather_than_dissipates",
    question=(
        "Does this surface REDISTRIBUTE the incident power into other "
        "directions, rather than dissipating it as heat?"
    ),
    why_it_matters=(
        "The exemption is a statement about where the power goes, not about the "
        "geometry. docs/absorber-thickness-bandwidth-bound.md section 7.3: "
        "Rozanov's sum rule constrains |rho|, the SPECULAR reflection "
        "coefficient, and it binds only because below the first grating lobe the "
        "specular mode is the only channel -- so |rho| < 1 necessarily means "
        "absorption. A surface that reduces monostatic RCS by absorbing is the "
        "absorber case and Rozanov binds it; the exemption does not apply. In "
        "plain terms: if the wave was swallowed rather than deflected, the "
        "thickness bill still has to be paid."
    ),
    check=None,
    check_signature="",
)

DIFFUSIVE_PROPAGATING_ORDER_PRECONDITION = BoundPrecondition(
    key="period_launches_propagating_diffracted_orders",
    question=(
        "Is the supercell period large enough that a diffracted order actually "
        "propagates at the band's lowest frequency?"
    ),
    why_it_matters=(
        "Redistribution needs somewhere to redistribute TO. Below the first "
        "grating lobe there is no propagating channel but the specular one, so "
        "'redirected' power has nowhere to go and the surface is back inside "
        "Rozanov's premise. For a checkerboard at normal incidence the specular "
        "order is cancelled by construction and the first available channels are "
        "the DIAGONAL orders, which propagate only for supercell period "
        "D >= sqrt(2)*lambda -- 42.4 mm at 10 GHz, 30.3 mm at 14 GHz. Check it "
        "at the LOWEST frequency in the required band, since lambda is largest "
        "and the requirement hardest there."
    ),
    check=diffracted_order_min_period_m,
    check_signature="diffracted_order_min_period_m(frequency_hz, order=(1, 1)) -> metres",
)


@dataclass(frozen=True)
class EffectBound:
    """One physical bound (or one stated absence of a bound) governing one
    mechanism by which an effect can be delivered.

    An effect can carry SEVERAL of these, because the bound follows the
    mechanism, not the ask. Backscatter reduction is the load-bearing case
    and splits three ways (docs/absorber-thickness-bandwidth-bound.md section
    7.3): by absorption Rozanov binds it, by phase cancellation Gustafsson &
    Sjoberg binds each tile, and by diffusion no bound of that shape applies
    at all.

    `registry_state` records what `designs/design_families.py` currently
    carries for the serving family, alongside `form`/`citation` recording
    what the literature doc says. Where those two disagree, this field is how
    a caller sees both -- see this module's docstring, "A DISCREPANCY THIS
    LIBRARY REPORTS AND DOES NOT ADJUDICATE".

    Per ADR-0047 a bound ADVISES and never gates: a candidate that appears to
    beat its bound has violated one of the bound's own assumptions, and the
    flag is the useful output. Refusing the candidate throws the diagnostic
    away along with a design that may be perfectly buildable.
    """

    mechanism: str
    status: BoundStatus
    name: str
    form: str
    citation: str
    applies_when: str
    registry_state: str = ""
    preconditions: tuple[BoundPrecondition, ...] = ()
    caveat: str = ""


# --------------------------------------------------------------------------
# Default threshold: a convention where one exists, and a stated absence
# where it does not
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class DefaultThreshold:
    """A literature convention the loop may fall back on when the customer
    states no number -- stated as DATA, so the reversibility rule travels
    with the number rather than living in a comment somebody can miss.

    `rule` is not decoration. ADR-0041 point 2 settles the shape for the
    absorber case and it generalises: a default is "a reversible, one-pass
    default when the customer states no threshold -- never a hardcoded rule",
    it RECORDS that a gap was filled, any customer-stated figure overrides it
    without argument, and it is never used to redefine the band's own edges.
    ADR-0038's "silence is permissive" is the parent rule; a hardcoded,
    non-reversible threshold "would convert an unstated requirement into a
    hard prune on a literature figure the customer never cited".
    """

    value: float
    comparator: str
    unit: str
    rule: str
    citation: str


@dataclass(frozen=True)
class _NoDefaultThreshold:
    """Sentinel for an effect where the literature has NO convention to fall
    back on, with the reason recorded.

    A distinct type rather than `None`, for the reason
    `designs/design_families.py` gives for `NO_PHYSICAL_BOUND`: "we searched
    and the field has not settled a number" and "nobody has looked" are
    different states carrying different instructions, and a bare `None`
    collapses them.
    """

    reason: str


DefaultThresholdSlot = DefaultThreshold | _NoDefaultThreshold


# --------------------------------------------------------------------------
# The gap report
# --------------------------------------------------------------------------


class GapReason(StrEnum):
    """Why a registered design family does not serve this intended effect --
    kept apart for the same reason `BoundStatus`'s four states are kept
    apart, above: "nobody has built this yet" and "this was considered and
    refused, in writing" license opposite next actions, and a single
    `FamilyGap` shape with no way to say which one it is would let a later
    reader "helpfully" register a family that an ADR already argued against.

    ADR-0050 is the reason this exists rather than being one more prose
    sentence in `misfiling_cost`: it registered `BANDPASS_FSS` and `SHIELD`
    for two of this library's three gaps and, for the third
    (`low infrared emissivity`), argued a family BY NAME and declined it --
    a materially different fact from "nobody has gotten to this yet", and
    the whole point of recording it is that a `FamilyGap` for that effect
    must not read the same as a `FamilyGap` for ordinary outstanding work.

    OUTSTANDING_WORK      -- nothing here says a family should not exist;
                             registering one (or wiring an existing one in)
                             is the fix, and nobody has done it yet.
    DELIBERATELY_DECLINED -- a family was considered and refused. Reopening
                             it is a decision for whoever revisits the ADR
                             that declined it, not a routine registration.
    """

    OUTSTANDING_WORK = "outstanding work"
    DELIBERATELY_DECLINED = "deliberately declined"


@dataclass(frozen=True)
class FamilyGap:
    """A precise statement that no design family in the registry serves this
    intended effect, plus what happens today if a requirement asks for it
    anyway.

    SHAPED LIKE A CAPABILITY WARNING, AND NOT ONE. CONTEXT.md's Capability
    warning is "stated in the same value/comparator/unit shape as a
    Requirement target, so the gap is a precise, actionable spec rather than
    descriptive prose", and it "never removes the candidate from
    consideration". This borrows the first half of that -- the precision --
    because a gap stated as prose is a gap nobody can query. It is NOT a
    Capability warning: a Capability warning is about what the shop has
    loaded (equipment, ink, material), and this is about what this repo's own
    registry holds. Different fact, different owner, different fix.

    It is emphatically not a `capability-verdict` either. A
    `capability-verdict` DROPS a family from a batch (CONTEXT.md:
    Considered-and-dropped ledger). This drops nothing, refuses nothing, and
    gates nothing -- it is a finding handed to the caller, per ADR-0028's
    "warn and proceed" and the charter's "the search space is unbounded".

    `status` is a `GapReason`, never a bare bool: "not built yet" and
    "considered and refused" are different facts about the SAME emptiness
    and license different next actions, on the same reasoning
    `designs/design_families.py`'s module docstring gives for
    `NO_PHYSICAL_BOUND` versus `UnreadPhysicalBound`.

    `misfiled_as` and `misfiling_cost` are the load-bearing pair: naming a
    gap is cheap, and saying what it costs when the requirement arrives
    anyway is what makes it actionable.
    """

    effect: str
    status: GapReason
    needed_value: float
    comparator: str
    unit: str
    achieved_value: float
    misfiled_as: str
    misfiling_cost: str
    cheapest_fix: str

    def as_statement(self) -> str:
        """One line a human can read, in the value/comparator/unit shape."""
        return (
            f"{self.effect}: needs {self.comparator} {self.needed_value:g} "
            f"{self.unit}; the registry has {self.achieved_value:g}."
        )


# --------------------------------------------------------------------------
# The profile, and the miss
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class EffectProfile:
    """Everything this library knows about one intended effect.

    `found` is `True` here and `False` on `EffectMiss`, so a caller can
    branch on one attribute without an isinstance check when it does not care
    why.
    """

    name: str
    in_context_md_seven: bool
    gloss: str
    scoring_quantity: ScoringQuantity
    scoring_quantity_note: str
    objective_sense: ObjectiveSense
    fixtures: tuple[Fixture, ...]
    bounds: tuple[EffectBound, ...]
    families: tuple[str, ...]
    default_threshold: DefaultThresholdSlot
    aliases: tuple[str, ...] = ()
    cross_quantity_senses: tuple[tuple[ScoringQuantity, ObjectiveSense], ...] = ()
    family_gap: FamilyGap | None = None
    notes: tuple[str, ...] = field(default_factory=tuple)

    @property
    def found(self) -> bool:
        return True

    @property
    def senses_by_quantity(self) -> MappingProxyType[ScoringQuantity, ObjectiveSense]:
        """Which way is better, per quantity -- this effect's own scoring
        quantity first, plus any OTHER quantity it has a stated opinion about.

        This is the field that pins the radome defect. `absorbed` and
        `transmitted` do not merely score different quantities; they want
        OPPOSITE things from the same quantity. Both maximise their own
        (absorptivity, transmittance), but a radome asked about ABSORPTIVITY
        wants it MINIMISED, where an absorber wants it MAXIMISED. Score one
        with the other's model and the ranking inverts -- see this module's
        docstring, finding 1.
        """
        merged: dict[ScoringQuantity, ObjectiveSense] = {
            self.scoring_quantity: self.objective_sense
        }
        merged.update(dict(self.cross_quantity_senses))
        return MappingProxyType(merged)

    @property
    def has_family(self) -> bool:
        return bool(self.families)


@dataclass(frozen=True)
class EffectMiss:
    """A well-formed "I do not know this effect" -- returned, never raised.

    THIS IS THE ADR-0030 GUARANTEE IN CODE. An intended effect's vocabulary
    is open (CONTEXT.md: "Its vocabulary is **open, not a closed enum**"),
    which means an effect this library has never heard of is the EXPECTED
    case, not an error: ADR-0030's own worked example is a requirement asking
    the surface to "behave as a magnetic mirror", an effect no family served
    when that ADR was written. A raise here would climb the call stack into
    requirement intake and turn an open vocabulary into a closed one.

    So: the caller carries on. Nothing is rejected, nothing is dropped,
    nothing is gated. What the caller gets is a message naming what this
    library does know, so a typo is visible without being fatal.

    `could_mean` is populated when the asked-for string is a customer ASK
    that several distinct effects could serve -- "reduce radar return" is the
    canonical one, answerable by absorption, by diffusion, or by a
    checkerboard's phase cancellation. Deliberately reported rather than
    resolved: picking one would be this module inferring physics from prose,
    which `designs/design_families.py` line 58 forbids in the family case for
    exactly the same reason ("SELECTION STAYS HUMAN-AUTHORED"). One ask
    served by several effects IS the trade space; collapsing it silently
    would throw away the thing the charter promises to hand the reader.
    """

    asked: str
    normalised: str
    known_effects: tuple[str, ...]
    message: str
    could_mean: tuple[str, ...] = ()

    @property
    def found(self) -> bool:
        return False


# --------------------------------------------------------------------------
# The content
# --------------------------------------------------------------------------

_ROZANOV = EffectBound(
    mechanism="dissipation in a metal-backed lossy slab",
    status=BoundStatus.PUBLISHED,
    name="Rozanov thickness-to-bandwidth bound",
    form="|ln rho_0| * (lambda_max - lambda_min) <= 2*pi^2 * mu_s * d   (2*pi^2 = 19.739209)",
    citation=(
        "K. N. Rozanov, 'Ultimate thickness to bandwidth ratio of radar absorbers', "
        "IEEE Trans. Antennas Propag. 48(8):1230-1234, 2000, doi:10.1109/8.884491; "
        "read first-hand and recorded at docs/rozanov-bound-primary-source.md"
    ),
    applies_when=(
        "Metal-backed magnetodielectric slab, normal incidence, passive and causal "
        "materials, finite static permeability mu_s. mu_s > 1 needs a magnetic "
        "filler actually in the stack; a printed conductor on a dielectric host "
        "has mu_s = 1. Bounds the LOW-frequency end of a fixed thickness budget."
    ),
    registry_state=(
        "designs/design_families.py: ABSORBER.physical_bound is a live PhysicalBound "
        "wired to rf_tools.physical_bounds.rozanov_min_thickness_m."
    ),
    caveat=(
        "The integral is over the VOLTAGE reflection coefficient |rho|, not power "
        "|rho|^2. Getting it backward silently doubles every headroom figure "
        "(ADR-0047 Consequences; docs/absorber-thickness-bandwidth-bound.md "
        "section 8.1). Oblique incidence moves the allowed bandwidth by up to 43 "
        "percent, so an apparent violation is an assumption breaking, not physics "
        "breaking -- ADR-0047 point 2: never fail a candidate for appearing to "
        "beat its bound."
    ),
)

_GUSTAFSSON_SJOBERG = EffectBound(
    mechanism="phase held inside a window by a grounded periodic surface",
    status=BoundStatus.PUBLISHED,
    name="Gustafsson & Sjoberg high-impedance-surface sum rule",
    form=(
        "B * lambda_0 / d <= 2*pi*tan(Phi/4), which is 2.6 at Phi = pi/2 (the "
        "standard +/-45 degree window) and pi for the lossless non-magnetic case "
        "at max|Y| = 1/2"
    ),
    citation=(
        "M. Gustafsson & D. Sjoberg, 'Physical bounds and sum rules for "
        "high-impedance surfaces', Tech. Report LUTEDX/(TEAT-7198)/1-19/(2010), "
        "later IEEE Trans. Antennas Propag. 59(6):2196-2204, 2011; Eqs. (4.10), "
        "(4.11), (5.1) quoted verbatim at "
        "docs/absorber-thickness-bandwidth-bound.md section 7.1"
    ),
    applies_when=(
        "A periodic structure above a perfectly conducting ground plane, lossless "
        "and non-magnetic, operating below the first grating lobe. Roughly 5x "
        "harsher than the absorber bound at the same thickness: at 9.5 GHz, 2.0 mm "
        "allows 16.5 percent bandwidth here against 87.8 percent under Rozanov "
        "(ADR-0047 point 3). Published numerical designs already reach 82-99 "
        "percent of it, so it is tight in practice as well as in theory."
    ),
    registry_state=(
        "DISCREPANCY, reported not adjudicated: designs/design_families.py carries "
        "REFLECTION_PHASE.physical_bound as an UnreadPhysicalBound ('primary source "
        "NOT yet read by this programme'), while "
        "docs/absorber-thickness-bandwidth-bound.md section 7.1 quotes the paper's "
        "own equations verbatim from the open-access Lund manuscript and ADR-0047 "
        "states the 2.6 figure as settled. Calling the registry's slot still raises "
        "with the citation, by design. See this module's docstring."
    ),
    caveat=(
        "Stated for high-impedance (near-zero-phase) surfaces and, in Eq. (5.1), "
        "for an arbitrary phase window Phi. Applying it element-by-element to a "
        "beam-steering reflectarray is sound -- same physical object -- but NO "
        "retrieved source states a bound on beam-steering bandwidth AS SUCH "
        "(array factor, scan angle, aperture efficiency). The bound doc's own "
        "labels: element-level phase stability is LITERATURE-SUPPORTED, the step "
        "to array-level steering bandwidth is INFERRED."
    ),
)


_KNOWN_ASKS: dict[str, tuple[str, ...]] = {}


def _register_ask(ask: str, effects: tuple[str, ...]) -> None:
    _KNOWN_ASKS[_normalise(ask)] = effects


def _normalise(name: str) -> str:
    """Fold spelling, casing, hyphenation and spacing into one key.

    Deliberately conservative: it folds case, trims, turns hyphens,
    underscores and slashes into spaces, and collapses runs of whitespace. It
    does NOT stem, fuzzy-match or guess -- `designs/design_families.py`'s
    `_ALIASES` comment gives the reason ("Aliases are recorded here rather
    than silently accepted by fuzzy matching, so every accepted spelling is
    one a human can see and audit"), and an open vocabulary makes it worse:
    fuzzy matching would silently resolve a genuinely NEW effect onto an old
    one, which is the one outcome an open vocabulary must not produce.
    """
    if not isinstance(name, str):
        return ""
    folded = name.strip().casefold()
    for ch in ("-", "_", "/"):
        folded = folded.replace(ch, " ")
    return " ".join(folded.split())


ABSORBED = EffectProfile(
    name="absorbed",
    in_context_md_seven=True,
    gloss=(
        "turn the arriving wave into a small amount of heat inside the surface, "
        "so almost nothing comes back to whoever sent it"
    ),
    scoring_quantity=ScoringQuantity.ABSORPTIVITY,
    scoring_quantity_note=(
        "The fraction of incident power turned into heat, scored at the SINGLE "
        "WORST-absorbing frequency inside the required band -- a minimax, never "
        "the mean and never the peak (ADR-0041 point 1). A = 1 - |S11|^2 on the "
        "metal-backed fixture; A = 1 - |S11|^2 - |S21|^2 on the unbacked one. "
        "'-10 dB reflectivity', '90 percent absorption' and 'effective absorption "
        "bandwidth' are ONE quantity stated three ways, not three quantities."
    ),
    objective_sense=ObjectiveSense.MAXIMISE,
    cross_quantity_senses=(
        (ScoringQuantity.REFLECTION_LOSS, ObjectiveSense.MINIMISE),
        (ScoringQuantity.TRANSMITTANCE, ObjectiveSense.MINIMISE),
    ),
    fixtures=(ONE_PORT_METAL_BACKED, TWO_PORT_TRANSMISSION),
    bounds=(
        _ROZANOV,
        EffectBound(
            mechanism="dissipation in an unbacked, two-port absorbing screen",
            status=BoundStatus.NOT_ESTABLISHED,
            name="unbacked/transmissive absorber bandwidth bound",
            form="",
            citation=(
                "Rozanov (2000) is NOT this bound: its opening line fixes a slab "
                "'overlying a perfectly reflecting plane' "
                "(docs/rozanov-bound-primary-source.md section 3, assumption (b)), "
                "which an unbacked screen fails. Whether a published bound exists "
                "for this case has not been researched here."
            ),
            applies_when="No ground plane; transmission suppressed by the pattern itself.",
            registry_state=(
                "designs/design_families.py: ABSORBER_TRANSMISSIVE.physical_bound is "
                "an UnreadPhysicalBound -- recorded as unread rather than "
                "NO_PHYSICAL_BOUND, since absence of a citation is not evidence that "
                "no bound exists."
            ),
        ),
    ),
    families=(design_families.ABSORBER.name, design_families.ABSORBER_TRANSMISSIVE.name),
    default_threshold=DefaultThreshold(
        value=0.90,
        comparator=">=",
        unit="fraction of incident power absorbed, worst frequency in band",
        rule=(
            "REVERSIBLE ONE-PASS DEFAULT when the customer states no absorption "
            "threshold, never a hardcoded rule. The loop falls back to it, RECORDS "
            "that a gap was filled, and any customer-stated figure overrides it "
            "without argument (ADR-0041 point 2, on ADR-0038's 'silence is "
            "permissive'). It must never be used to redefine the band's own edges: "
            "the requirement states the band, and a -10 dB contour search is a "
            "device for comparing published designs to each other, not a definition "
            "of anybody's band."
        ),
        citation=(
            "ADR-0041 point 2. CALCULATED: -10 dB reflectivity => |S11|^2 = 0.100 "
            "=> A = 0.900. The literature itself is inconsistent (70-99 percent "
            "absorption, -6.99 to -20 dB all appear), which is precisely why this "
            "is a default and not a prune."
        ),
    ),
    aliases=(
        "absorb",
        "absorbs",
        "absorption",
        "absorptive",
        "absorber",
        "absorbed by the surface",
        "radar absorption",
        "rf absorption",
        "radar absorbing material",
        "ram",
    ),
    notes=(
        "Two families serve this one effect and they are NOT variants of each "
        "other: ABSORBER is metal-backed and one-port, ABSORBER_TRANSMISSIVE is "
        "unbacked and two-port, and issue #216 exists because conflating them "
        "credits as absorbed every watt that merely escaped out the back. Which "
        "one applies is settled by whether the requirement asserts a reflector, "
        "never inferred (ADR-0017).",
        "The customer ask 'reduce radar return' is NOT this effect. It is an ask "
        "served by absorption, by diffuse scattering, or by a checkerboard's phase "
        "cancellation -- three different physical routes with different costs and "
        "different confidence. That one-to-many mapping is the trade space "
        "(CONTEXT.md: Intended effect), and this library reports it rather than "
        "collapsing it.",
    ),
)


REFLECTED_IN_PHASE = EffectProfile(
    name="reflected in phase",
    in_context_md_seven=True,
    gloss=(
        "metal sends a wave back upside down, which cancels an antenna lying flat "
        "on it and makes the antenna deaf; a surface engineered to send it back "
        "the right way up makes the same antenna loud instead, while staying thin "
        "enough to bend around the thing it is stuck to"
    ),
    scoring_quantity=ScoringQuantity.REFLECTION_PHASE,
    scoring_quantity_note=(
        "The phase of the reflected wave relative to the incident one, in degrees, "
        "across the required band. A magnetic mirror is the 0-degree case; a bare "
        "conductor is the 180-degree case. Note that no closed form in rf_tools "
        "returns a phase at all -- rf_tools.calculations returns a patch resonant "
        "frequency, rf_tools.absorber an absorbed fraction -- which is why "
        "REFLECTION_PHASE carries an UndeclaredAnalysisModel."
    ),
    objective_sense=ObjectiveSense.HOLD_IN_WINDOW,
    fixtures=(ONE_PORT_METAL_BACKED,),
    bounds=(_GUSTAFSSON_SJOBERG,),
    families=(design_families.REFLECTION_PHASE.name,),
    default_threshold=DefaultThreshold(
        value=45.0,
        comparator="<=",
        unit="degrees of reflection phase away from the target phase (a +/-45 degree window)",
        rule=(
            "REVERSIBLE ONE-PASS DEFAULT when the customer states no phase window, "
            "recorded as a filled gap and overridden without argument by any "
            "customer-stated figure -- ADR-0041 point 2's shape applied to this "
            "quantity rather than to absorption. It is a genuine field convention, "
            "not an invented number, but it is still nobody's requirement."
        ),
        citation=(
            "The +/-45 degree AMC criterion, Phi = pi/2 in Gustafsson & Sjoberg's "
            "Eq. (5.1) -- 'The familiar +/-45 degree AMC criterion (Phi = pi/2) "
            "gives B <= 2.6 d/lambda_0' (docs/absorber-thickness-bandwidth-bound.md "
            "section 7.1). The window is what the bound is stated against, which is "
            "what makes it the defensible default here."
        ),
    ),
    aliases=(
        "reflect in phase",
        "reflected in phase",
        "in phase reflection",
        "in phase reflected",
        "reflection phase",
        "magnetic mirror",
        "amc",
        "artificial magnetic conductor",
        "high impedance surface",
        "zero degree reflection",
        "0 degree reflection",
        "behave as a magnetic mirror",
    ),
    notes=(
        "'Behave as a magnetic mirror' is ADR-0030's own worked example of an "
        "effect the registry did not serve when that ADR was written (#220). It "
        "resolves here because REFLECTION_PHASE is the family whose per-cell "
        "reflection phase IS the design variable -- but note what that family can "
        "and cannot do today: it has a settled solver (PALACE_FLOQUET, #252) and "
        "no analysis model at all.",
        "Doubling the signal is the payoff the patent states: a 0-degree "
        "reflection 'produces the same full reflection with 0 degree phase shift, "
        "with doubling the signal strength' (US12089385B2 [0058]), where the "
        "classical alternative is holding the antenna a quarter-wavelength clear "
        "-- which makes the standoff part of the design and the part no longer "
        "thin.",
    ),
)


STEERED = EffectProfile(
    name="steered",
    in_context_md_seven=True,
    gloss=(
        "send the reflected beam off in a direction you choose, instead of "
        "straight back the way it came"
    ),
    scoring_quantity=ScoringQuantity.REFLECTION_PHASE,
    scoring_quantity_note=(
        "DESIGNED on per-cell reflection phase, SCORED at aperture level on where "
        "the beam actually goes. These are two different quantities and the second "
        "one has no model in this repo: the designed-for behaviour does not exist "
        "at unit-cell level at all (CONTEXT.md: Simulation tier, Tier B), and no "
        "module here performs the aperture-level step that turns a phase lookup "
        "into a steered beam. The scoring quantity is recorded as REFLECTION_PHASE "
        "because that is the quantity anything in this repo can currently reach; "
        "the wanted steering angle is a human-only input (ADR-0045)."
    ),
    objective_sense=ObjectiveSense.HOLD_IN_WINDOW,
    fixtures=(APERTURE_OVER_ONE_PORT_CELLS, ONE_PORT_METAL_BACKED),
    bounds=(_GUSTAFSSON_SJOBERG,),
    families=(design_families.REFLECTION_PHASE.name,),
    default_threshold=_NoDefaultThreshold(
        reason=(
            "No convention. The steering angle is the requirement's own content -- "
            "ADR-0045 lists 'the wanted steering angle for #4/#5' among the "
            "human-only inputs the registry cannot supply -- so there is no "
            "field-standard number to fall back on, and inventing one would be "
            "scoring against a number the customer never asked for. The element-"
            "level phase window default belongs to 'reflected in phase' and is not "
            "silently borrowed here: a steering design wants its phase to TRACK a "
            "gradient across the aperture, not to sit near zero."
        )
    ),
    aliases=(
        "steer",
        "steers",
        "steering",
        "beam steering",
        "beam steered",
        "beam steer",
        "redirected",
        "redirect",
        "reflectarray",
        "anomalous reflection",
    ),
    notes=(
        "Shares REFLECTION_PHASE with 'reflected in phase' -- one family, two "
        "intended effects. That is the ordinary case, not an anomaly: CONTEXT.md "
        "keeps effect and family apart precisely because the mapping between them "
        "is many-to-many.",
        "The step from the element-level phase-stability bound to an array-level "
        "steering bandwidth is INFERRED, not stated by any retrieved source "
        "(docs/absorber-thickness-bandwidth-bound.md section 7.1). Report the "
        "element bound; do not present it as a bound on steering bandwidth.",
    ),
)


TRANSMITTED = EffectProfile(
    name="transmitted",
    in_context_md_seven=True,
    gloss=(
        "let the wanted band straight through the skin with as little loss and as "
        "little reflection back into the antenna as possible -- a radome, or a "
        "window that is transparent only at the frequencies you care about"
    ),
    scoring_quantity=ScoringQuantity.TRANSMITTANCE,
    scoring_quantity_note=(
        "One-way power transmission |S21|^2 through the surface, in band. "
        "MIL-R-7705B 3.4.1.1 states it as 'the minimum and average one-way power "
        "transmission through the radome shall not be less than the limits "
        "specified in table 1'. Its companion 3.4.1.2 scores REFLECTION_LOSS "
        "separately -- 'the power reflected back into the antenna by the radome "
        "shall not exceed' -- so a radome requirement carries two quantities, and "
        "absorptivity is neither of them."
    ),
    objective_sense=ObjectiveSense.MAXIMISE,
    cross_quantity_senses=(
        # THE RADOME DEFECT, PINNED. An absorber MAXIMISES absorptivity; a radome
        # MINIMISES it. Same quantity, opposite sense -- so scoring a radome with
        # the absorber family's model does not merely give a rough answer, it
        # inverts the ranking. See this module's docstring, finding 1.
        (ScoringQuantity.ABSORPTIVITY, ObjectiveSense.MINIMISE),
        (ScoringQuantity.REFLECTION_LOSS, ObjectiveSense.MINIMISE),
    ),
    fixtures=(TWO_PORT_TRANSMISSION,),
    bounds=(
        EffectBound(
            mechanism="transmission through a periodically perforated free-standing screen",
            status=BoundStatus.PUBLISHED,
            name="Ludvig-Osipov et al. perforated-screen transmission bandwidth bound",
            form="B <= gamma*pi*Delta/(A*lambda_0), Delta = sqrt(1-T0^2)/T0 (their Eq. 12)",
            citation=(
                "A. Ludvig-Osipov, J. Lundgren, C. Ehrenborg, Y. Ivanenko, "
                "A. Ericsson, M. Gustafsson, B. L. G. Jonsson & D. Sjoberg, "
                "'Fundamental Bounds on Transmission Through Periodically "
                "Perforated Metal Screens With Experimental Validation', IEEE "
                "Trans. Antennas Propag. 68(2):773-782, 2020, "
                "doi:10.1109/TAP.2019.2943430; read first-hand and recorded at "
                "docs/bandpass-fss-physical-bound-primary-source.md. Classical "
                "Bode-Fano was checked first and found vacuous for this mechanism "
                "(the far-side load is a pure resistance, Q=0 -- same document, "
                "section 2), which is why the bound below is this different "
                "member of the same passive-system sum-rule family rather than a "
                "Bode-Fano restatement."
            ),
            applies_when=(
                "No ground plane at all; one patterned layer (ADR-0017's "
                "2026-09-06 correction). Infinitely thin (or w/d >= 10) PEC "
                "screen, normal incidence only, single propagating Floquet mode, "
                "negligible cross-polarisation, ~30x30 unit cells. Bounds "
                "passband WIDTH only, not the insertion-loss floor inside it; "
                "the source explicitly declines to extend it to lossy impedance "
                "surfaces, and a printed conductor is not PEC."
            ),
            registry_state=(
                "designs/design_families.py: BANDPASS_FSS.physical_bound is a "
                "live PhysicalBound wired to "
                "rf_tools.physical_bounds.perforated_screen_min_polarizability_m3 "
                "/ perforated_screen_max_wavelength_fractional_bandwidth. It "
                "needs gamma, the aperture's static polarizability, supplied by "
                "the caller -- nothing in rf_tools or simulation computes it from "
                "geometry yet (an electrostatic solve, not a closed form)."
            ),
            caveat=(
                "B here is Ludvig-Osipov et al.'s own WAVELENGTH-domain "
                "fractional bandwidth, 2*(lambda2-lambda1)/(lambda1+lambda2) -- "
                "NOT the frequency-domain (f_high-f_low)/f_center this module "
                "uses for the Rozanov bound elsewhere, and not interchangeable "
                "with it except in the narrow-band limit."
            ),
        ),
    ),
    families=(design_families.BANDPASS_FSS.name,),
    family_gap=None,
    default_threshold=_NoDefaultThreshold(
        reason=(
            "No single convention exists, and the reason is structural rather than "
            "a gap in the search. MIL-R-7705B carries 'one limit per requirement "
            "per product class' -- Table 1's columns are radome TYPE (I, II, III, "
            "IIIA, IV, V, VI) and its sample values run 95/85, 85/75 and 85/70 "
            "percent minimum/average transmission depending on type "
            "(docs/military-requirements-vocabulary.md section 5). The number is "
            "decided by which class of product was bought, before the specification "
            "is applied, so there is no class-free figure to default to. Picking one "
            "would be inventing a product class on the customer's behalf."
        )
    ),
    aliases=(
        "transmit",
        "transmits",
        "transmission",
        "transmissive",
        "transmitted through",
        "radome",
        "bandpass",
        "band pass",
        "bandpass fss",
        "passband",
        "pass band",
        "rf transparent",
        "rf transparency",
        "frequency selective surface passband",
    ),
    notes=(
        "This effect HAD no design family until ADR-0050 registered BANDPASS_FSS "
        "for it. The gap was not subtle while it lasted, and the arithmetic that "
        "priced it is kept here, verbatim, now that there is no FamilyGap left to "
        "hold it -- so the defect this family exists to prevent cannot silently "
        "return once nobody remembers why it was added. Before ADR-0050, a radome "
        "had nowhere to go but ABSORBER_TRANSMISSIVE, the only ground-less "
        "two-port family that existed then, and that family's analysis model "
        "scores worst-in-band ABSORPTIVITY. A screen-printed Ti3C2Tx chessboard "
        "FSS reported at X-band average radar transmittance 78 percent and "
        "reflectivity 16 percent (J. Alloys Compd., PII S0925838826025946, "
        "recorded on issue #453; provenance UNVERIFIED -- the primary paper has "
        "not been read here) has A = 1 - 0.16 - 0.78 = 0.06 (CALCULATED from "
        "exactly those two stated figures), against ADR-0041's 0.90 default "
        "absorption threshold: a near-ideal radome scoring 6 percent of the bar. "
        "ADR-0017's own correction independently records a printable bandpass FSS "
        "and calls it 'the transmissive design ADR-0017 assumed did not exist'. "
        "In plain terms: a window and a sponge are graded on opposite things, and "
        "grading the window as a sponge put the best window in the room bottom of "
        "the class.",
        "A transmissive candidate must state that it needs no reflector, as an "
        "explicit requirement assertion -- ADR-0017's default is that the base "
        "printed layer always supplies its own reflector, and a printed reflector "
        "behind a radome is a contradiction, not a conservative choice.",
    ),
)


SCATTERED_DIFFUSELY = EffectProfile(
    name="scattered diffusely",
    in_context_md_seven=True,
    gloss=(
        "break the reflection up into many weak beams pointing in many directions, "
        "so that very little goes back towards whoever is looking -- nothing is "
        "swallowed, it is just sent somewhere else"
    ),
    scoring_quantity=ScoringQuantity.RCS_REDUCTION,
    scoring_quantity_note=(
        "Monostatic radar cross-section reduction in dB, relative to a same-sized "
        "flat conductor -- how much less comes back towards the transmitter. It is "
        "an APERTURE-level quantity over an arrangement of cells, not a per-cell "
        "one, which is a second missing model on top of the missing per-cell phase "
        "and is why DIFFUSIVE is Tier B with an UndeclaredAnalysisModel. Note the "
        "human-only input ADR-0045 flags: a checkerboard redirects rather than "
        "absorbs, so 'reduction' is only a success if the redirected lobes land "
        "somewhere the customer does not care about, and no solver can know that."
    ),
    objective_sense=ObjectiveSense.MAXIMISE,
    fixtures=(APERTURE_OVER_ONE_PORT_CELLS, ONE_PORT_METAL_BACKED),
    bounds=(
        EffectBound(
            mechanism="backscatter reduction by diffusion / redirection (coding, pixelated)",
            status=BoundStatus.EXEMPT_BY_MECHANISM,
            name="no bound of the Rozanov/Chu shape governs this mechanism",
            form="",
            citation=(
                "docs/absorber-thickness-bandwidth-bound.md section 7.3. The doc "
                "labels this INFERRED from the structure of the sum rule plus the "
                "grating-lobe restriction, NOT stated as such by any retrieved "
                "source, and flags it as needing confirmation before anything "
                "depends on it. The nearest formal statement retrieved is "
                "Gustafsson, Vakili, Bayer Keskin, Sjoberg & Larsson, 'Optical "
                "theorem and forward scattering sum rule for periodic structures', "
                "IEEE Trans. Antennas Propag. 60(8):3818-3826, 2012 -- which bounds "
                "TOTAL scattering, a quantity a diffusive surface satisfies while "
                "still redirecting freely."
            ),
            applies_when=(
                "Both preconditions below must hold. Where they do, such a surface "
                "'can achieve arbitrarily large monostatic reduction at arbitrarily "
                "small thickness, limited by fabrication and by scan/angle stability "
                "rather than by a causality sum rule'."
            ),
            registry_state=(
                "designs/design_families.py: DIFFUSIVE.physical_bound is "
                "NO_PHYSICAL_BOUND, whose stated reason is this exemption -- "
                "'redistributes backscatter rather than dissipating or radiating a "
                "bounded quantity'."
            ),
            preconditions=(
                DIFFUSIVE_REDISTRIBUTION_PRECONDITION,
                DIFFUSIVE_PROPAGATING_ORDER_PRECONDITION,
            ),
            caveat=(
                "This is an EXEMPTION, not a licence. If either precondition fails "
                "the surface is back inside a bound -- Rozanov's if it is really "
                "absorbing, Gustafsson & Sjoberg's if it is really a "
                "phase-cancellation checkerboard -- and the thickness bill is due. "
                "Per ADR-0047 this advises and never gates either way."
            ),
        ),
        EffectBound(
            mechanism="backscatter reduction by phase cancellation (AMC/PEC checkerboard)",
            status=BoundStatus.PUBLISHED,
            name="Gustafsson & Sjoberg, inherited per tile",
            form="B * lambda_0 / d <= 2*pi*tan(Phi/4), applied to each tile",
            citation=_GUSTAFSSON_SJOBERG.citation,
            applies_when=(
                "Each tile is itself a reflection-phase surface, so section 7.1 "
                "binds the band over which the two tiles keep their required phase "
                "difference. Published practice matches: a traditional PEC-AMC "
                "checkerboard achieves roughly 5 percent RCS-reduction bandwidth "
                "precisely because it inherits the AMC's in-phase bandwidth."
            ),
            registry_state=_GUSTAFSSON_SJOBERG.registry_state,
        ),
        EffectBound(
            mechanism="backscatter reduction by absorption",
            status=BoundStatus.PUBLISHED,
            name="Rozanov, inherited",
            form=_ROZANOV.form,
            citation=_ROZANOV.citation,
            applies_when=(
                "'By absorption: it IS the absorber case. Rozanov binds it.' "
                "(docs/absorber-thickness-bandwidth-bound.md section 7.3.) Listed "
                "here because the customer ask is the same one; the mechanism, and "
                "therefore the bound, is not."
            ),
            registry_state=_ROZANOV.registry_state,
        ),
    ),
    families=(design_families.DIFFUSIVE.name,),
    default_threshold=_NoDefaultThreshold(
        reason=(
            "No convention to adopt. The field reports several figures side by side "
            "rather than settling one -- ADR-0045 cites Murugesan & Selvan reporting "
            "'the 8 and 10 dB RCS reduction bandwidths' in the same sentence -- and "
            "this repo already treats the number as a per-requirement input rather "
            "than a constant: docs/supercell-sizing-rule.md derives the supercell's "
            "phase budget delta = 2*arcsin(10^(-RCSR_dB/20)) FROM the requirement's "
            "own stated RCS-reduction target. Defaulting RCSR_dB here would feed an "
            "invented number straight into a geometry decision."
        )
    ),
    aliases=(
        "scatter diffusely",
        "scattered diffusely",
        "diffuse scattering",
        "diffuse scatter",
        "diffusive",
        "diffusion",
        "coding",
        "coding surface",
        "coding metasurface",
        "pixelated metasurface",
        "checkerboard",
    ),
    notes=(
        "The three-way split above is the whole point of keeping bounds per "
        "MECHANISM rather than per ask. 'Reduce radar return' reaches all three, "
        "and they differ by more than a constant: one is bounded by thickness, one "
        "is bounded roughly 5x harder by thickness, and one is not bounded that way "
        "at all provided two preconditions hold.",
        "The exemption's second precondition has real teeth on a conformal part. At "
        "10 GHz a checkerboard needs a supercell period of at least 42.4 mm before "
        "its diagonal orders propagate; at 14 GHz, 30.3 mm. A skin too small to fit "
        "one supercell cannot claim the exemption at all.",
        "Curvature is a separate limit and it does drop this family from a batch: a "
        "coding surface tolerates only S <= 2*theta_max*R of arc before its cells "
        "sit outside their Validity box's incidence-angle range "
        "(docs/curvature-effects-on-em-surfaces.md). That exclusion is a "
        "capability-verdict in the Considered-and-dropped ledger and expires the "
        "moment the stated curvature changes -- it is not a Capability warning and "
        "not anything this library issues.",
    ),
)


POLARISATION_CONVERTED = EffectProfile(
    name="polarisation-converted",
    in_context_md_seven=True,
    gloss=(
        "turn the wave as it bounces -- send back a wave lying at right angles to "
        "the one that arrived, or turn a straight-line wave into a corkscrew one"
    ),
    scoring_quantity=ScoringQuantity.CROSS_POLARISATION_RATIO,
    scoring_quantity_note=(
        "How much of the returned power comes back with its field rotated -- the "
        "CROSS-polarised channel, a different quantity from the one that went in. "
        "Every closed form in rf_tools is scalar (one incident field in, one number "
        "out), so none can represent an anisotropic cell's two unequal "
        "principal-axis responses, which is why POLARIZATION_CONVERTER carries an "
        "UndeclaredAnalysisModel AND an UnsettledSimulationAdapter."
    ),
    objective_sense=ObjectiveSense.MAXIMISE,
    fixtures=(ONE_PORT_METAL_BACKED_TWO_POLARISATIONS,),
    bounds=(
        EffectBound(
            mechanism="cross-polarised reflection from an anisotropic surface, versus BANDWIDTH",
            status=BoundStatus.NONE_PUBLISHED,
            name="no thickness-versus-bandwidth bound exists for polarisation conversion",
            form="",
            citation=(
                "Abdelrahman & Monticone, arXiv:2208.05533, state it in their own "
                "conclusion: 'more work is needed to extend these results to the "
                "problem of broadband maximization of reflection, establishing "
                "fundamental tradeoffs between bandwidth, thickness, and "
                "reflectance.' Quoted at "
                "docs/absorber-thickness-bandwidth-bound.md section 7.2 and stated "
                "in ADR-0047 point 3."
            ),
            applies_when=(
                "Always, for a bandwidth objective. This is a POSITIVE finding -- "
                "the authors say the bound does not exist yet -- not an unsearched "
                "gap, which is what separates NONE_PUBLISHED from NOT_ESTABLISHED "
                "here."
            ),
            registry_state=(
                "designs/design_families.py: POLARIZATION_CONVERTER.physical_bound is "
                "an UnreadPhysicalBound whose own citation says 'whether a "
                "fundamental bound exists for it is itself an open question... "
                "absence of a citation is not evidence that no bound exists'. That "
                "is the conservative reading; this entry records the sharper one for "
                "the BANDWIDTH question specifically, on the authors' own words."
            ),
        ),
        EffectBound(
            mechanism="cross-polarised reflection versus EFFICIENCY at a single frequency",
            status=BoundStatus.PUBLISHED,
            name="Abdelrahman & Monticone universal reflection bound",
            form=(
                "A single-frequency thickness-versus-efficiency bound from energy "
                "conservation and passivity by Lagrangian duality; in the thin "
                "lossless limit the cross-polarised figure converges to "
                "U_PC -> 1/4, i.e. at most 25 percent of incident power converted "
                "by an infinitesimally thin passive lossless layer."
            ),
            citation=(
                "M. Abdelrahman & F. Monticone, 'How thin and efficient can a "
                "metasurface reflector be? Universal bounds on reflection for any "
                "direction and polarization', arXiv:2208.05533, Eq. (11)"
            ),
            applies_when=(
                "'The only assumptions are that the structure is passive, with a "
                "surface area much larger than its thickness, and is made of a "
                "single local, isotropic, and nonmagnetic material.' Answers 'can "
                "this efficiency be reached at this thickness at all, at one "
                "frequency' -- a different question from a bandwidth objective, and "
                "it cannot serve as a stopping condition for one."
            ),
            registry_state="Not wired into designs/design_families.py in any form.",
            caveat=(
                "The direction of this finding is the OPPOSITE of the absorber case "
                "and is easy to misread. For polarisation conversion the bound says "
                "a published 1.27 mm design at R_PC ~ 0.8 and 10 GHz is more than "
                "10x thicker than necessary (h_min = 0.003*lambda), where absorbers "
                "sit at 1.4-2x their limit. This is ADR-0047's own load-bearing "
                "reason for refusing one shared 'percent of limit' field: the same "
                "number would report roughly 8 percent for a good polarisation "
                "converter and roughly 70 percent for a good absorber and mean "
                "nothing set against either."
            ),
        ),
    ),
    families=(design_families.POLARIZATION_CONVERTER.name,),
    default_threshold=_NoDefaultThreshold(
        reason=(
            "No convention retrieved. The only quantitative figure this programme "
            "has read for polarisation conversion is Abdelrahman & Monticone's "
            "worked example, R_PC ~ 0.8 at 10 GHz -- one design's reported "
            "performance, not a threshold anybody adopted. ADR-0041's -10 dB "
            "default survives scrutiny because it is a recurring field convention "
            "with a standards-body relative; nothing of that weight exists here, and "
            "borrowing the absorber's number for a different quantity on a different "
            "fixture would be exactly the category error this module exists to catch."
        )
    ),
    aliases=(
        "polarisation converted",
        "polarization converted",
        "polarisation conversion",
        "polarization conversion",
        "polarisation convert",
        "polarization convert",
        "polarisation converter",
        "polarization converter",
        "cross polarisation",
        "cross polarization",
        "cross pol",
        "polarisation rotation",
        "polarization rotation",
        "polarisation rotator",
        "linear to circular",
        "linear to cross",
    ),
    notes=(
        "The one effect here whose bandwidth bound is known ABSENT rather than "
        "merely unread. Say that precisely: a single-frequency efficiency bound "
        "does exist and is cited above; what does not exist is a "
        "thickness-versus-bandwidth bound, on the authors' own statement.",
        "POLARIZATION_CONVERTER has no settled simulation adapter. Its "
        "cheapest_test is already written down in designs/design_families.py: hand "
        "simulation/palace.py an all-dielectric ANISOTROPIC cell it can already "
        "mesh, and check the cross-polarised specular channel climbs out of the "
        "noise floor when the cell's two axes are made unequal.",
    ),
)


SHIELDED_AGAINST = EffectProfile(
    name="shielded against",
    in_context_md_seven=True,
    gloss=(
        "stop the wave reaching whatever is behind the surface -- a barrier, not a "
        "sponge; where it goes instead (bounced back, or turned to heat) is not "
        "what this asks about"
    ),
    scoring_quantity=ScoringQuantity.SHIELDING_EFFECTIVENESS,
    scoring_quantity_note=(
        "SE_dB = -20*log10|S21|: how far the wave is knocked down on its way "
        "through. A TRANSMISSION quantity, so it needs a two-port fixture -- and "
        "see the note below on why that makes it nearly informationless under this "
        "programme's default architecture."
    ),
    objective_sense=ObjectiveSense.MAXIMISE,
    cross_quantity_senses=((ScoringQuantity.TRANSMITTANCE, ObjectiveSense.MINIMISE),),
    fixtures=(TWO_PORT_TRANSMISSION,),
    bounds=(
        EffectBound(
            mechanism="attenuation on the way through a barrier",
            status=BoundStatus.NOT_ESTABLISHED,
            name="shielding-effectiveness bound",
            form="",
            citation=(
                "None. Not in ADR-0047's per-family table, not researched here. "
                "Recorded as NOT_ESTABLISHED, not NONE_PUBLISHED -- nobody has "
                "looked, which is a different statement from having looked and "
                "found nothing."
            ),
            applies_when="",
            registry_state=(
                "designs/design_families.py: SHIELD.physical_bound is an "
                "UnreadPhysicalBound (ADR-0050). Nobody here has searched, though "
                "there is a structural reason to suspect no bound of the "
                "Rozanov/Chu shape governs a quantity that rises monotonically "
                "with thickness and conductivity with no bandwidth trade -- that "
                "suspicion is this programme's own and unconfirmed, so it is not "
                "enough to change the status. SHIELD.analysis_model and "
                "SHIELD.postprocess are also both still missing "
                "(UndeclaredAnalysisModel, UnbuiltPostProcess): a named family is "
                "not yet a scoreable one."
            ),
        ),
    ),
    families=(design_families.SHIELD.name,),
    family_gap=None,
    default_threshold=_NoDefaultThreshold(
        reason=(
            "No convention adopted here. The only SE figures this repo has read are "
            "reported performances, not thresholds -- '49.02 dB and 56.65 dB' at two "
            "peaks of one dual-band EMI-shielding design "
            "(docs/absorber-scoring-decision-confirmation.md section 3.3). "
            "Standards in this area exist (MIL-STD-461 and its relatives) and have "
            "NOT been retrieved or read here, so nothing is cited from them."
        )
    ),
    aliases=(
        "shield",
        "shields",
        "shielded",
        "shielded against",
        "shielding",
        "shielding effectiveness",
        "emi shielding",
        "emc shielding",
        "screened",
        "screening",
        "blocked",
    ),
    notes=(
        "ADR-0050 registered SHIELD as this effect's design family, resolving the "
        "registry-lookup half of the gap this profile used to carry as a "
        "FamilyGap. Named after the MECHANISM -- attenuation through a "
        "conductor's thickness against its skin depth, not a resonance -- rather "
        "than after the objective-flipped algebra that would have merged it into "
        "BANDPASS_FSS; see designs/design_families.py's own comment above SHIELD "
        "for why that merge does not work even though SE_dB = -10*log10(T) makes "
        "the two quantities mathematically equivalent (disjoint design inputs: a "
        "bandpass FSS is designed by resonant aperture geometry, a shield by "
        "conductor thickness and sheet resistance). Naming the family did not "
        "make it scoreable -- SHIELD still carries UndeclaredAnalysisModel and "
        "UnbuiltPostProcess, so nothing here can run a SHIELD design through the "
        "loop yet, which is a second, still-open gap this note keeps visible.",
        "THIS EFFECT MAY NOT BE SCOREABLE UNDER THIS PROGRAMME'S DEFAULT "
        "ARCHITECTURE, and that is the finding worth carrying regardless of "
        "whether a family names it. ADR-0017 makes the "
        "base printed layer supply its own conductive reflector by default; a "
        "ground-backed structure has zero transmission by construction "
        "(designs/design_families.py's __post_init__ states this as the reason "
        "requires_ground_plane=True forces port_count=1); so SE is effectively "
        "infinite and carries NO design information for that architecture. In plain "
        "terms: asking a solid metal-backed skin how well it blocks radio is like "
        "asking a brick wall how well it blocks daylight -- the answer is 'totally', "
        "every time, and it tells you nothing about how to build a better wall.",
        "Do not confuse SE with absorption. A perfect reflector shields perfectly "
        "and absorbs nothing; a good absorber may shield less well than a thin sheet "
        "of foil. They are different quantities answering different questions, which "
        "is why they are separate ScoringQuantity members.",
    ),
)


LOW_INFRARED_EMISSIVITY = EffectProfile(
    name="low infrared emissivity",
    in_context_md_seven=False,
    gloss=(
        "make the surface look cold to a thermal camera while it still does its "
        "radio job -- the heat-signature half of a multispectral skin"
    ),
    scoring_quantity=ScoringQuantity.EMISSIVITY,
    scoring_quantity_note=(
        "Emissivity in the infrared band -- how much heat the surface radiates "
        "compared with a perfect emitter at the same temperature, dimensionless, 0 "
        "to 1. By Kirchhoff's law it equals absorptivity AT THE SAME WAVELENGTH, "
        "which is why the unit looks familiar and the quantity is not: this is "
        "three to four orders of magnitude away in frequency from every other "
        "effect in this library."
    ),
    objective_sense=ObjectiveSense.MINIMISE,
    fixtures=(INFRARED_EMITTANCE,),
    bounds=(
        EffectBound(
            mechanism="infrared emittance of a surface layer",
            status=BoundStatus.NOT_ESTABLISHED,
            name="infrared emissivity bound",
            form="",
            citation="None retrieved or researched here.",
            applies_when="",
            registry_state="No design family serves this effect.",
            caveat=(
                "The binding constraint this programme HAS established for a "
                "radar-plus-infrared skin is not a bound at all -- it is a "
                "compatibility threshold between the two functions. A resistive "
                "infrared overlay must exceed 407 ohm/sq to leave a 90 percent "
                "microwave absorption floor intact, and 1,695 ohm/sq for a 99 "
                "percent floor (CALCULATED, "
                "docs/five-paper-absorber-corpus-findings.md section 4). Every "
                "CONTINUOUS infrared-functional conductor in that corpus fails it by "
                "one to three orders of magnitude; every PATTERNED one passes by two "
                "to three, because a metal grid of period p presents "
                "Y/Y_0 ~ 2*pi*k*(p/lambda) and an infrared-scale period is "
                "microscopic at 10 GHz. So the conflict is continuous-versus-"
                "patterned, and it is designable."
            ),
        ),
    ),
    families=(),
    family_gap=FamilyGap(
        effect="low infrared emissivity",
        status=GapReason.DELIBERATELY_DECLINED,
        needed_value=1.0,
        comparator=">=",
        unit="registered design families in designs/design_families.py serving this effect",
        achieved_value=0.0,
        misfiled_as=(
            "(none -- and none can be. ADR-0050 examined registering a family and "
            "found ADR-0027 section 5's four-plug-in test returns four nothings: "
            "no physical_bound, no analysis_model, no optimizer_class, no "
            "simulation_adapter. DesignFamily.__post_init__ refuses the attempt on "
            "physics regardless -- it requires requires_ground_plane=True to pair "
            "with port_count=1 and False with port_count=2, and an infrared layer "
            "is not an S-parameter measurement at all, so it has no ports to "
            "declare either way.)"
        ),
        misfiling_cost=(
            "Not the cost of an oversight -- the cost of the mechanism, and it is a "
            "real number rather than a shrug. ADR-0050's conclusion: low infrared "
            "emissivity is a CO-DESIGN CONSTRAINT on a candidate whose family is "
            "set by its radar behaviour, not a design family of its own, because a "
            "CONTINUOUS low-emissivity conductive layer laid over a radar absorber "
            "SHORTS IT OUT. rf_tools.calculations.min_overlay_sheet_resistance_"
            "ohm_sq returns 407.3 ohm/sq as the floor an overlay must clear to "
            "leave 90 percent microwave absorption intact (1,695.3 ohm/sq for 99 "
            "percent) -- VERIFIED by calling the function directly, not taken on "
            "trust. A dense, continuous MXene film at this repo's own "
            "best-evidenced as-printed conductivity (6.9e5 S/m, "
            "docs/mxene-voltera-nova-printability.md) has an RF sheet resistance of "
            "0.24 ohm/sq at 10 GHz and 20 um thickness "
            "(rf_tools.calculations.sheet_resistance_ohm_sq, likewise VERIFIED by "
            "calling the function), roughly 1,700 times too conductive to clear "
            "the 90 percent floor. In plain terms: a solid metal film on top ruins "
            "the radar absorber underneath, the way shorting a battery's terminals "
            "with a wire drains it instead of running the circuit it was meant "
            "for. So a requirement asking for BOTH a radar effect and low infrared "
            "emissivity on one candidate needs this threshold checked against the "
            "candidate's actual IR layer, or its radar half is silently wrong -- "
            "and only a PATTERNED infrared layer (a metal grid of period p, "
            "presenting Y/Y_0 ~ 2*pi*k*(p/lambda), microscopic at 10 GHz for an "
            "infrared-scale period) can pass the threshold while still doing an "
            "infrared job."
        ),
        cheapest_fix=(
            "There is no code fix, and writing one would be the mistake ADR-0050 "
            "exists to prevent: registering a family here would let "
            "families_serving('low infrared emissivity') return a name and make "
            "this FamilyGap vanish, so the gap report would say the gap was closed "
            "when it was not -- an honest, queryable gap is worth more than a "
            "family that appears to serve an effect and cannot. The 407 / 1,695.3 "
            "ohm/sq thresholds are usable TODAY with no registry change, as a "
            "stated co-design constraint on any overlay proposed above a microwave "
            "absorber. If a later reader wants to reconsider registering a family, "
            "ADR-0050's Consequences name the precondition: an infrared SOLVER and "
            "an infrared MODEL would have to exist here first -- until then the "
            "four plug-ins are four nothings and __post_init__ still refuses it. "
            "Reopening this is a decision for whoever revisits that ADR, not a "
            "routine registration -- which is what this FamilyGap's "
            "status=GapReason.DELIBERATELY_DECLINED is for."
        ),
    ),
    default_threshold=_NoDefaultThreshold(
        reason=(
            "No convention read here. Low-emissivity coating practice quotes figures "
            "in the 0.1-0.3 range, but this programme has retrieved no primary "
            "source for any of them and will not default to a number it has not "
            "read."
        )
    ),
    aliases=(
        "low infrared emissivity",
        "low ir emissivity",
        "low emissivity",
        "low e",
        "infrared emissivity",
        "ir emissivity",
        "emissivity",
        "multispectral",
        "multi spectral",
        "radar and ir",
        "infrared signature",
        "ir signature",
        "thermal signature",
    ),
    notes=(
        "NOT ONE OF CONTEXT.md'S SEVEN. The seven are, verbatim: absorbed, "
        "reflected in phase, steered, transmitted, scattered diffusely, "
        "polarisation-converted, shielded against. This one is named here because "
        "it is live work -- docs/five-paper-absorber-corpus-findings.md section 4 "
        "calls a radar-plus-infrared skin 'the architecture the DEVCOM context "
        "makes live' and gives it a numeric design rule -- and because an effect "
        "the glossary does not name is an effect no requirement can be filed "
        "under. Naming it here asserts nothing about whether it belongs in the "
        "glossary; that is a separate decision (docs/adr/0049).",
        "It is also the one effect here that is not an RF quantity at all, which is "
        "why its fixture carries port_count=None. Any design serving both this and "
        "a microwave effect is scoring two quantities in two bands on two "
        "instruments, and the compatibility threshold above is what connects them.",
        "ADR-0050 examined and declined a design family for this effect, in "
        "writing -- see this module's docstring, finding 3, and "
        "family_gap.status. That is a different fact from the other two effects "
        "this library used to report as gapped, both of which ADR-0050 resolved "
        "by registering a family (BANDPASS_FSS, SHIELD). Do not resolve this one "
        "the same way without reopening that ADR.",
    ),
)


_PROFILES: tuple[EffectProfile, ...] = (
    ABSORBED,
    REFLECTED_IN_PHASE,
    STEERED,
    TRANSMITTED,
    SCATTERED_DIFFUSELY,
    POLARISATION_CONVERTED,
    SHIELDED_AGAINST,
    LOW_INFRARED_EMISSIVITY,
)

# CONTEXT.md's seven, verbatim, in the order the glossary lists them. Held as
# data so `tests/test_intended_effects.py` can assert every one resolves, and
# so a drift between this module and the glossary is a test failure rather
# than a thing somebody notices.
CONTEXT_MD_SEVEN: tuple[str, ...] = (
    "absorbed",
    "reflected in phase",
    "steered",
    "transmitted",
    "scattered diffusely",
    "polarisation-converted",
    "shielded against",
)


def _build_index() -> dict[str, EffectProfile]:
    index: dict[str, EffectProfile] = {}
    for profile in _PROFILES:
        for spelling in (profile.name, *profile.aliases):
            key = _normalise(spelling)
            existing = index.get(key)
            if existing is not None and existing is not profile:
                raise AssertionError(
                    f"intended-effect alias {spelling!r} is claimed by both "
                    f"{existing.name!r} and {profile.name!r}. An alias that resolves "
                    "two ways would silently pick one effect's scoring quantity for "
                    "the other's requirement -- fix the table in "
                    "designs/intended_effects.py."
                )
            index[key] = profile
    return index


_INDEX: dict[str, EffectProfile] = _build_index()


# Customer ASKS that are not effects: phrases a requirement plausibly uses
# which several distinct effects could serve. Never resolved to one -- they
# only enrich a miss's message, so the caller sees the trade space instead of
# a silent pick. CONTEXT.md's Intended effect entry uses the first of these
# as its own worked example of exactly this.
_register_ask(
    "reduce radar return",
    ("absorbed", "scattered diffusely", "reflected in phase (as a checkerboard tile)"),
)
_register_ask(
    "reduce rcs",
    ("absorbed", "scattered diffusely", "reflected in phase (as a checkerboard tile)"),
)
_register_ask(
    "rcs reduction",
    ("absorbed", "scattered diffusely", "reflected in phase (as a checkerboard tile)"),
)
_register_ask(
    "radar cross section reduction",
    ("absorbed", "scattered diffusely", "reflected in phase (as a checkerboard tile)"),
)
_register_ask(
    "stealth",
    ("absorbed", "scattered diffusely", "low infrared emissivity"),
)
_register_ask(
    "low observable",
    ("absorbed", "scattered diffusely", "low infrared emissivity"),
)


# --------------------------------------------------------------------------
# The interface
# --------------------------------------------------------------------------


def known_effect_names() -> tuple[str, ...]:
    """Every effect name this library holds, sorted.

    NOT the legal set of intended effects. An intended effect's vocabulary is
    open (ADR-0030), so this is what this library happens to know today --
    useful for a message or a menu, never for validation.
    """
    return tuple(sorted(profile.name for profile in _PROFILES))


def resolve_intended_effect(name: str) -> EffectProfile | EffectMiss:
    """Look up one intended effect by any recorded spelling.

    Normalises case, hyphenation, underscores and spacing, then matches
    against the effect's canonical name and its recorded aliases. Both
    British and American spellings of polarisation resolve.

    **Returns an `EffectMiss` for anything unrecognised, and never raises.**
    That is the ADR-0030 guarantee: the vocabulary is open, so an unknown
    effect is the expected case rather than an error, and the caller carries
    on. Nothing is rejected and no candidate is dropped. A non-string
    argument returns a miss too, for the same reason -- this is a lookup, not
    a validator.
    """
    key = _normalise(name)
    profile = _INDEX.get(key)
    if profile is not None:
        return profile

    could_mean = _KNOWN_ASKS.get(key, ())
    if could_mean:
        message = (
            f"{name!r} is a customer ASK, not one intended effect: it could be "
            f"served by {', '.join(could_mean)}. Deliberately not resolved to one "
            "-- one ask served by several effects IS the trade space (CONTEXT.md: "
            "Intended effect), and picking one here would be code choosing physics. "
            "Nothing is blocked; carry on with the requirement as stated."
        )
    else:
        message = (
            f"No profile for intended effect {name!r}. This library knows: "
            f"{', '.join(known_effect_names())}. THIS IS NOT AN ERROR -- an "
            "intended effect's vocabulary is open, not a closed enum (ADR-0030), so "
            "an effect nobody has written a profile for is a legitimate "
            "requirement. Nothing is rejected, nothing is dropped, and the "
            "requirement's own provenance stays ASSUMED either way. Add a profile "
            "in designs/intended_effects.py if this effect is one this library "
            "should know."
        )
    return EffectMiss(
        asked=name if isinstance(name, str) else repr(name),
        normalised=key,
        known_effects=known_effect_names(),
        message=message,
        could_mean=could_mean,
    )


def families_serving(effect: str | EffectProfile) -> tuple[str, ...] | EffectMiss:
    """Which registered design families serve this effect today.

    Returns the family names (canonical, straight out of
    `designs/design_families.py`), or an `EffectMiss` for an effect this
    library does not know. An EMPTY tuple from a known effect is a real
    answer -- "nothing in the registry serves this" -- and is distinguishable
    from a miss by type rather than by a bare falsy value, which is the
    ambiguity `designs/design_families.py`'s docstring exists to refuse.

    Pair it with `resolve_intended_effect(...).family_gap` for the precise,
    value/comparator/unit statement of what that emptiness costs.
    """
    profile = effect if isinstance(effect, EffectProfile) else resolve_intended_effect(effect)
    if isinstance(profile, EffectMiss):
        return profile
    return profile.families


def effects_without_family() -> tuple[FamilyGap, ...]:
    """Every effect this library knows that NO registered design family
    serves -- the gap report this module exists to produce.

    Each entry is a `FamilyGap`: a precise value/comparator/unit statement
    plus what happens today if such a requirement arrives anyway and what the
    cheapest fix is. Shaped like a Capability warning; not one, and not a
    `capability-verdict` -- it refuses nothing and drops nothing (see
    `FamilyGap`'s docstring).
    """
    return tuple(
        profile.family_gap
        for profile in _PROFILES
        if not profile.families and profile.family_gap is not None
    )


def families_without_effect() -> tuple[str, ...]:
    """The gap in the OTHER direction: registered design families that no
    effect in this library claims.

    Today: `("PATCH",)`. A patch antenna does not do something to an arriving
    wave, it radiates one, and "radiated" is not among CONTEXT.md's seven --
    recorded as a finding, not fixed by minting vocabulary here (see this
    module's docstring, finding 4).

    The reason this function is worth its keep: it is what makes adding a
    SEVENTH design family to the registry without wiring it in here fail
    loudly in `tests/test_intended_effects.py`, instead of leaving a family
    no requirement can reach.
    """
    claimed = {name for profile in _PROFILES for name in profile.families}
    return tuple(sorted(set(design_families.known_family_names()) - claimed))


def scoring_quantity(effect: str | EffectProfile) -> ScoringQuantity | EffectMiss:
    """The quantity this effect is graded on -- or an `EffectMiss`.

    These are not interchangeable: absorptivity, transmittance, shielding
    effectiveness, reflection phase, RCS reduction, cross-polarisation ratio
    and emissivity are different quantities on different fixtures. Reading
    this before choosing an analysis model is what stops a radome being
    scored as a sponge.
    """
    profile = effect if isinstance(effect, EffectProfile) else resolve_intended_effect(effect)
    if isinstance(profile, EffectMiss):
        return profile
    return profile.scoring_quantity


def objective_sense(effect: str | EffectProfile) -> ObjectiveSense | EffectMiss:
    """Which direction is better for this effect's OWN scoring quantity --
    or an `EffectMiss`.

    For a cross-quantity answer ("what does a radome want from absorptivity?")
    read `EffectProfile.senses_by_quantity`, which is where the radome defect
    is actually pinned.
    """
    profile = effect if isinstance(effect, EffectProfile) else resolve_intended_effect(effect)
    if isinstance(profile, EffectMiss):
        return profile
    return profile.objective_sense


def physical_bound_for(effect: str | EffectProfile) -> tuple[EffectBound, ...] | EffectMiss:
    """Every physical bound (or stated absence of one) governing this effect
    -- or an `EffectMiss`.

    A TUPLE, not one bound, because the bound follows the MECHANISM and one
    effect can be delivered several ways. Backscatter reduction is the
    load-bearing case and splits three ways; absorption splits two, by
    whether there is a reflector behind it.

    Per ADR-0047 everything returned here ADVISES. Nothing in this module
    gates on a bound, and a candidate that appears to beat one has broken one
    of the bound's own assumptions -- the flag is the useful output.
    """
    profile = effect if isinstance(effect, EffectProfile) else resolve_intended_effect(effect)
    if isinstance(profile, EffectMiss):
        return profile
    return profile.bounds
