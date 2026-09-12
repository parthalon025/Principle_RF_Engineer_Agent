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

AND NOW ON TWO MORE AGAIN (ADR-0050, issues #455 and #453). `postprocess` and
`sweep_axes` are ADR-0045's two remaining required registry axes -- it names
four, "a tier field (A/B) plus independent fields for port count,
post-processing kind, and sweep axes", and only the first two had shipped.
Both are required at construction for the same reason as the two slots above,
with one refinement worth stating because it is the argument, not a
formality: `port_count` is allowed a default precisely because
`__post_init__` cross-checks it against `requires_ground_plane` and CATCHES a
wrong one. Nothing in the registry implies a post-processing kind or a sweep
axis -- ADR-0045 says so in terms, "none of the three is derivable from the
tier or from each other" -- so a wrong default in either would be
undetectable, and an undetectable wrong default is exactly what #239 and #241
were.

WHAT THE REGISTRY COULD NOT SAY, AND CAN NOW. Two of CONTEXT.md's seven
intended effects had no family at all. `transmitted` -- a radome -- would have
landed in `ABSORBER_TRANSMISSIVE` by elimination, the only ground-less
two-port family there was, and been scored on worst-in-band ABSORPTIVITY: a
real measured screen-printed chessboard FSS at 78 percent transmittance and 16
percent reflectivity has A = 1 - 0.16 - 0.78 = 0.06, which against the field's
-10 dB / A >= 0.900 default reads as 6 percent of the bar. The best radome in
the corpus would have ranked last. `shielded against` had nowhere to go at
all. `BANDPASS_FSS` and `SHIELD` below are those two, each with the
four-plug-in test of ADR-0027 section 5 (as corrected on 2026-09-10 to name
`analysis_model` as the fourth) applied and shown in the comment above it.

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
    """A bound this programme cannot yet stand behind: either it exists in the
    literature and the primary source has not been read to this repo's
    standard, or nobody here has searched for one at all. Distinct from
    `NO_PHYSICAL_BOUND`, and distinct from a bound that is merely uncomputed
    for one design.

    Both readings are deliberately carried by one type, because they license
    the same behaviour -- refuse to return a number, name what to go and read
    -- and because collapsing THEM would be harmless where collapsing either
    into `NO_PHYSICAL_BOUND` would not. The `citation` field is where each
    instance says which of the two it is; `ABSORBER_TRANSMISSIVE` and
    `POLARIZATION_CONVERTER` below are the "nobody has searched" reading, and
    both say so in terms, on the rule that absence of a citation is not
    evidence that no bound exists.

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
        "bound at all'). THIS EXEMPTION IS CONDITIONAL, NOT UNCONDITIONAL -- two "
        "preconditions, both load-bearing, per "
        "docs/absorber-thickness-bandwidth-bound.md section 7.3: "
        "(a) the surface must actually REDISTRIBUTE rather than dissipate -- a "
        "cell that also absorbs is scored as an absorber for that portion of "
        "its loss, and that portion IS Rozanov-bounded (section 7.3: 'by "
        "absorption: it IS the absorber case. Rozanov binds it'); and "
        "(b) the surface's period must be large enough to actually launch a "
        "propagating diffracted order (section 7.3: 'a surface with a period "
        "large enough to launch propagating diffracted orders redistributes "
        "power ... without absorbing it') -- for a checkerboard at normal "
        "incidence the diagonal (+/-1,+/-1) orders propagate only when the "
        "supercell period D >= sqrt(2)*lambda (42.4 mm at 10 GHz, 30.3 mm at "
        "14 GHz); BELOW that period there is no diffracted channel at all and "
        "every dB of specular/monostatic reduction must come from absorption, "
        "which IS fully Rozanov-bounded -- a small-period 'coding' cell does "
        "not actually clear this exemption. Section 7.3 itself flags this "
        "whole argument as INFERRED ('from the structure of the sum rule plus "
        "the grating-lobe restriction, not stated as such by any retrieved "
        "source') and 'needing confirmation before anything depends on it' -- "
        "and the CODING alias below now depends on it, unconfirmed (see the "
        "comment there)."
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

    `required_fields` (issue #249) names exactly the `step_input` keys this
    model's own dispatched handler requires (`orchestration/design_loop.py`'s
    own `_require_fields` call for it, plus `eps_r` where `_resolve_eps_r_
    bounds` needs one) -- the fact `orchestration/solver.py`'s candidate
    driver reads to know which of a proposed candidate's fields to keep for
    ANALYSIS, instead of the single hardcoded patch-antenna shape
    (`eps_r`/`w_m`/`h_m`/`l_m`) it used to project every family's candidate
    through. Defaults to an empty tuple, never `None`, matching this
    module's own "never a bare ambiguous absence" discipline -- a family
    that has not stated one yet strips every field for its ANALYSIS
    step_input, which reads as "no analysis to run" every bit as loudly as
    an `UndeclaredAnalysisModel` would, rather than as a hidden fallback.
    """

    name: str
    function: str
    answers: str
    required_fields: tuple[str, ...] = ()


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
    handler table (currently "NEC2", "MEEP_FLOQUET" and "PALACE_FLOQUET").
    `reason` says why
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
# Simulation scored field: which raw result key SIMULATION is judged on
# --------------------------------------------------------------------------
#
# WHY THIS SLOT EXISTS (issue #249). `orchestration/solver.py`'s candidate
# driver used to score every family's SIMULATION result on ONE hardcoded
# default field, `gain_dbi` -- a patch antenna's peak radiated gain, read
# straight out of NEC2's own parsed output. ABSORBER's SIMULATION result (from
# `orchestration/design_loop.py`'s `_simulate_meep_floquet`) carries no such
# key at all -- it reports `worst_absorption` instead, the family's actual
# figure of merit -- so scoring it against the patch default silently read a
# missing field rather than the real one. In plain terms: every family's
# SIMULATION result was being graded on a patch antenna's report card no
# matter what kind of surface it actually was.
#
# The same three-state discipline as `physical_bound` and `analysis_model`
# above applies here for the identical reason: a bare `None` would make "this
# family's SIMULATION result carries no settled figure of merit yet"
# indistinguishable from "nobody has said". `ScoredField` is a settled
# declaration; `UndeclaredScoredField` says the question is still open, and
# asking for it raises rather than falling back to another family's field.


@dataclass(frozen=True)
class ScoredField:
    """The raw result key a family's SIMULATION step is scored on, and its
    unit -- the fact `orchestration/solver.py` reads instead of its own
    single hardcoded default (`gain_dbi`/dBi, issue #249).

    `result_field` names a key of the SIMULATION decision's own raw result
    dict (e.g. ABSORBER's `worst_absorption`, PATCH's `gain_dbi`); `unit` is
    that field's unit, passed straight through to
    `designs.success_score.success_score`'s own `actual_unit`, which
    requires it to match the scoring target's stated unit by exact string
    equality.
    """

    result_field: str
    unit: str


@dataclass(frozen=True)
class UndeclaredScoredField:
    """No result field has been declared as this family's SIMULATION scored
    quantity -- distinct from a bare `None`, and from silently reusing
    another family's field (PATCH's `gain_dbi`), which is the exact defect
    issue #249 removes from `orchestration/solver.py`.

    Asking for it raises `UndeclaredScoredFieldError` naming the family and
    this reason, rather than a caller guessing at a field or a candidate
    reading as a confusing per-step failure for a field that was simply never
    named.
    """

    reason: str


ScoredFieldSlot = ScoredField | UndeclaredScoredField


UNDECLARED_SIMULATION_SCORED_FIELD = UndeclaredScoredField(
    reason=(
        "no SIMULATION scored field has been declared for this family in "
        "designs/design_families.py. Declare a ScoredField naming the raw "
        "result key and its unit once this family's SIMULATION result "
        "carries a settled figure of merit to score candidates on -- until "
        "then orchestration.solver.run_candidate_search refuses to score "
        "this step by default rather than falling back to another family's "
        "field (issue #249)."
    )
)


class UndeclaredScoredFieldError(ValueError):
    """Raised when `orchestration.solver` asks a family which field its
    SIMULATION result is scored on and the family declares none (issue
    #249)."""


# --------------------------------------------------------------------------
# Post-processing: the arithmetic between the solver's output and the score
# --------------------------------------------------------------------------
#
# WHY THIS SLOT EXISTS AND WHY IT IS NOT `analysis_model` (issues #455, #109).
# ADR-0045's Consequences require every registry entry to carry, alongside the
# tier, "independent fields for port count, post-processing kind, and sweep
# axes -- none of the three is derivable from the tier or from each other."
# Two of those three shipped (`simulation_tier`, `port_count`); this slot and
# `sweep_axes` below are the other two, and #455 asked the fair question
# first: is ADR-0045's "post-processing" just `analysis_model` under another
# name, in which case the requirement narrows to three fields and no new slot
# is needed?
#
# It is not, and three independent facts say so.
#
#   1. DIFFERENT INPUT, DIFFERENT STEP. `analysis_model` names a CLOSED-FORM
#      calculation the ANALYSIS step runs on the DESIGN -- geometry and
#      material constants in, a predicted number out, no solver anywhere
#      (`rf_tools.absorber.absorber_band_response`,
#      `rf_tools.patch_synthesis.patch_resonant_frequency_hz`). This slot names
#      arithmetic the SIMULATION step runs on a SOLVER'S OUTPUT -- reflectance
#      and transmittance in, absorptivity out. Cheap tier and expensive tier
#      (CLAUDE.md: "Evaluate cheap before expensive"), two different steps of
#      the loop, two different inputs.
#   2. ONE FAMILY CARRIES BOTH, AND ANOTHER CARRIES NEITHER.
#      `ABSORBER_TRANSMISSIVE` has a declared closed form AND power arithmetic
#      on the solver's S-parameters; `REFLECTION_PHASE` has no closed form and
#      no post-processing at all, because Palace hands back the phase it is
#      designed by. One field cannot hold two values for the first family or
#      two distinct nothings for the second.
#   3. "NONE" IS A REAL ANSWER HERE AND IS NOT A REAL ANSWER THERE.
#      ADR-0045 assigns post-processing "none" to three of the seven patent
#      examples -- the solver returns the scored quantity itself and there is
#      nothing to compute. `analysis_model` has no such value: its second
#      state is `UndeclaredAnalysisModel`, which means "nobody has established
#      one", the opposite statement. Collapsing the two fields would make
#      "nothing needs doing" indistinguishable from "nobody has worked out
#      what to do" -- the exact ambiguity this module's docstring exists to
#      refuse.
#
# *In plain terms: one is the sum you do on paper before you run anything; the
# other is the sum you do on the simulator's answer afterwards. A surface can
# need both, either, or neither, so they cannot be one field.*
#
# So the slot holds one of three things, never a bare `None`, on the same
# reasoning as `physical_bound` above.


@dataclass(frozen=True)
class PostProcess:
    """The named arithmetic a family runs on its solver's raw output to reach
    the quantity it is scored on.

    `consumes` names the solver outputs it reads and `produces` the quantity
    it yields, both in plain language, because ADR-0045's own enumeration of
    post-processing kinds ("power arithmetic", "effective-medium retrieval",
    "polarisation-ellipse arithmetic") is a description of what goes in and
    what comes out, not of an implementation. `function` records the repo
    function the arithmetic actually lives in, so a reader can go and read it
    rather than take the name on trust -- the same reason `AnalysisModel`
    carries one.
    """

    name: str
    consumes: str
    produces: str
    function: str


@dataclass(frozen=True)
class UnbuiltPostProcess:
    """The arithmetic this family needs after its solver is IDENTIFIED, and
    nothing in this repo performs it.

    Distinct from `NO_POSTPROCESS`, which says no arithmetic is needed at all.
    This says a specific calculation is needed and is missing, and names it --
    which is what makes it a piece of scoped work rather than a shrug. Issue
    #220 states the live instance in the same terms for the Mie-resonant
    examples: effective-medium retrieval "is a post-process, and there is no
    code for it anywhere in the repo".
    """

    needed: str
    reason: str


@dataclass(frozen=True)
class _NoPostProcess:
    """Sentinel for a family whose solver hands back the scored quantity
    directly, so there is nothing to compute afterwards.

    A POSITIVE statement, not a gap. ADR-0045 assigns exactly this to
    Examples 4, 5 and 7 -- they "read phase directly"
    (docs/seven-example-design-unknowns.md section 5) -- and NEC2 parses a
    patch's gain and feed-point impedance straight out of its own output.
    Kept as its own type rather than as an empty `PostProcess` so that
    "nothing to do" can never be misread as "nobody filled this in".
    """

    reason: str


NO_POSTPROCESS_PHASE_READ_DIRECTLY = _NoPostProcess(
    reason=(
        "the solver returns this family's scored quantity itself -- a per-cell "
        "complex reflection coefficient, whose phase IS the design variable -- so "
        "there is no arithmetic between the solver's output and the number this "
        "family is judged on (ADR-0045: post-processing 'none' for Examples 4, 5 "
        "and 7, which 'read phase directly'). The aperture-level step that turns a "
        "per-cell phase lookup into a steered beam or a scattering pattern is a "
        "second EVALUATION STAGE, not post-processing of the first one -- that "
        "distinction is what `simulation_tier=TIER_B` records, and it is why these "
        "two fields stay independent."
    )
)

PostProcessSlot = PostProcess | UnbuiltPostProcess | _NoPostProcess


class UnbuiltPostProcessError(ValueError):
    """Raised when a step asks a family what to run on its solver's output and
    the family names a calculation nothing in this repo performs (#455)."""


# --------------------------------------------------------------------------
# Sweep axes: what an evaluation has to be repeated over
# --------------------------------------------------------------------------
#
# ADR-0045's third cross-cutting axis, and the one whose absence had a named
# victim. Its own enumeration: "frequency only (1, 2, 3); x geometry (4);
# x material state (5); x incidence angle (6); x tile assignment x aperture
# size (7)."
#
# WHY IT IS NOT DERIVABLE FROM ANYTHING ELSE ALREADY IN THE REGISTRY. Two
# Tier A families here sweep frequency alone (ABSORBER, PATCH) and a third
# Tier A family sweeps frequency AND incidence angle (POLARIZATION_CONVERTER);
# two Tier B families sweep completely different second and third axes from
# each other (REFLECTION_PHASE: cell geometry and external material state;
# DIFFUSIVE: tile assignment and aperture size). So the axes follow neither
# the tier, nor the port count, nor the post-processing kind -- exactly what
# ADR-0045 asserts and what `tests/test_design_families.py` now pins.
#
# WHAT COST THE MISSING FIELD. ADR-0045 assigns Example 5 -- the tunable,
# bias-controlled surface -- the axis "frequency x material state". A registry
# that cannot record that axis would sweep frequency, report the surface's
# response at ONE bias state, and present it as the whole answer for a device
# whose entire point is that the answer moves when you change the bias. *In
# plain terms: measuring a dimmer switch at one setting and writing down "this
# is how bright the lamp is."*
#
# A NOTE ON THE WORD "SWEEP", BECAUSE IT IS DOING TWO JOBS.
# docs/seven-example-design-unknowns.md section 5 heads this axis "Excitation
# sweep", but the list under that heading contains geometry, tile assignment
# and aperture size -- which are DESIGN variables, not excitations. Both
# readings are meant: an axis here is anything the family's evaluation must be
# repeated over before its scored quantity exists, whether that is the wave
# you send in (frequency, incidence angle) or the thing you are varying to
# build a lookup (a cell dimension, a tile assignment). `supplied_by` is where
# each axis says which of the two it is, and who provides its values.


@dataclass(frozen=True)
class SweepAxis:
    """One axis a family's evaluation must be repeated over.

    `why` says what breaks if the axis is collapsed to a single point --
    stated per axis rather than once for the field, because the answer differs
    and the cost differs: collapsing frequency loses a bandwidth, collapsing
    material state loses an entire tuning mechanism, collapsing aperture size
    loses the finite-array effect that Murugesan & Selvan measured (ADR-0045:
    "the 8 and 10 dB RCS reduction bandwidths drop as array size increases").

    `supplied_by` records where the axis's values come from -- the
    requirement, the design's own parameterisation, or a human. ADR-0045
    deliberately left "how human-only inputs are captured in the registry's
    structure" undecided, and this field does not decide it either; it records
    which axes have that problem so they are visible rather than assumed
    solved.
    """

    name: str
    why: str
    supplied_by: str


FREQUENCY_AXIS = SweepAxis(
    name="frequency",
    why=(
        "every family here is scored across a BAND, not at a point, and at the "
        "single worst frequency inside it rather than the mean or the peak "
        "(ADR-0041's minimax rule). A one-frequency evaluation cannot produce a "
        "worst-in-band number at all, and a design tuned to one frequency is the "
        "classic way to look excellent and be useless."
    ),
    supplied_by="the requirement's own stated band (ADR-0043: band is a per-requirement input)",
)


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
    `simulation_adapter`, `postprocess`) are declared
    as open values, never closed two-literal enums, per ADR-0018's
    Consequences: both have a credible third value on the horizon.

    ADR-0045's four required registry axes are `simulation_tier`,
    `port_count`, `postprocess` and `sweep_axes`, and all four are here. The
    first two shipped with the registry; the last two landed at ADR-0050 after
    #455 asked whether `analysis_model` already was one of them. It is not --
    see the comment above `PostProcess`.
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
    # Required, no default, and this one had no defect to point at yet --
    # which is the argument for it, not against (ADR-0050). `port_count` gets
    # away with a default because `__post_init__` cross-checks it against
    # `requires_ground_plane`: a wrong default there is CAUGHT. Nothing in the
    # registry implies a post-processing kind -- ADR-0045 says so in terms,
    # "none of the three is derivable from the tier or from each other" -- so
    # a wrong default here would be undetectable, and an undetectable wrong
    # default is exactly the #239/#241 shape.
    postprocess: PostProcessSlot
    # Required, no default, same argument. Defaulting to frequency-only would
    # be right for four of the eight families here and silently wrong for the
    # rest -- and the family it would be most wrong about is the tunable one,
    # whose whole point is that its answer moves when you change the bias.
    sweep_axes: tuple[SweepAxis, ...]
    requires_ground_plane: bool
    spine_fields: frozenset[str] = field(default_factory=frozenset)
    optimizer_class: str | None = None
    port_count: int = 1
    # Defaults to the explicit "nobody has said" sentinel, never a bare
    # None (issue #249) -- unlike analysis_model/simulation_adapter/
    # postprocess above, a default is safe here rather than a repeat of
    # their own #239/#241 defect: the earlier three each had a WRONG
    # implicit answer silently standing in (the patch model, NEC2, a
    # borrowed post-process) when nobody declared one, and this default is
    # never mistaken for a real field -- asking for it raises by name (see
    # `declared_simulation_scored_field` below) rather than a caller ever
    # reading `UNDECLARED_SIMULATION_SCORED_FIELD` as though it were a
    # settled `ScoredField`.
    simulation_scored_field: ScoredFieldSlot = UNDECLARED_SIMULATION_SCORED_FIELD

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

    @property
    def has_simulation_scored_field(self) -> bool:
        """True only when this family has declared which field its
        SIMULATION result is scored on (issue #249)."""
        return isinstance(self.simulation_scored_field, ScoredField)

    def declared_simulation_scored_field(self) -> ScoredField:
        """The `ScoredField` this family's SIMULATION result is judged on --
        or a raise naming the family and why none is declared (issue #249).

        Never a fallback to another family's field. In plain terms: if this
        family's SIMULATION result carries no settled figure of merit yet,
        the honest answer is "nothing is declared", not PATCH's `gain_dbi`
        standing in because it happened to be the only field anybody wrote
        down first.
        """
        if isinstance(self.simulation_scored_field, ScoredField):
            return self.simulation_scored_field
        undeclared = self.simulation_scored_field
        raise UndeclaredScoredFieldError(
            f"Design family {self.name!r} declares no simulation_scored_field, so "
            "orchestration.solver has no field to score its SIMULATION result on "
            f"by default. Why not: {undeclared.reason} Declare a ScoredField for "
            "this family in designs/design_families.py, naming the raw result key "
            "and its unit, once its SIMULATION result carries a settled figure of "
            "merit. Until then this raises rather than falling back to another "
            "family's field (e.g. PATCH's gain_dbi), which would score the wrong "
            "quantity entirely (issue #249)."
        )

    @property
    def has_postprocess(self) -> bool:
        """True only when a BUILT post-solver arithmetic exists to run.

        False both for a family that needs none and for one whose arithmetic
        nobody has written -- which is why those are separate types: a caller
        that needs to explain WHY gets a different answer from each, and the
        two carry opposite instructions ("carry on" versus "somebody has to
        write this").
        """
        return isinstance(self.postprocess, PostProcess)

    @property
    def needs_no_postprocess(self) -> bool:
        """True when the solver hands back the scored quantity itself.

        A positive statement about the family, not an absence.
        """
        return isinstance(self.postprocess, _NoPostProcess)

    def declared_postprocess(self) -> PostProcess | _NoPostProcess:
        """What this family runs on its solver's output -- a named arithmetic,
        or the explicit "nothing, read it straight off" -- or a raise naming
        the calculation nobody here has written (#455).

        The raise is deliberately narrow: it fires ONLY for
        `UnbuiltPostProcess`, never for a family that genuinely needs no
        post-processing, because those are opposite states and only one of
        them is missing work. In plain terms: "there is no sum to do" is an
        answer; "the sum has not been written" is not.
        """
        if isinstance(self.postprocess, PostProcess | _NoPostProcess):
            return self.postprocess
        unbuilt = self.postprocess
        raise UnbuiltPostProcessError(
            f"Design family {self.name!r} needs {unbuilt.needed} after its solver "
            f"runs, and nothing in this repo performs it. Why not: {unbuilt.reason} "
            "Write it and record it as a PostProcess on this family in "
            "designs/design_families.py. Until then this raises rather than "
            "returning the solver's raw output as though it were the scored "
            "quantity -- which would report a number in the wrong units and the "
            "wrong sense, the confidently-wrong shape issue #239 exists to "
            "prevent (ADR-0050)."
        )

    def sweep_axis_names(self) -> tuple[str, ...]:
        """This family's sweep axes by name, in declared order -- for a report
        or an error message, never for dispatch."""
        return tuple(axis.name for axis in self.sweep_axes)

    def __post_init__(self) -> None:
        """Guard two invariants.

        THE FIRST is the one issue #216 found broken: `requires_ground_plane`
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

        THE SECOND is that `sweep_axes` cannot be empty, and each axis has to
        say what it is and why. No family in this programme is evaluated at a
        single point of anything: every one of them is scored across a band
        (ADR-0041's worst-in-band minimax), so an empty tuple is not a
        conservative reading of a family, it is a family nobody finished
        describing. Both checks raise at construction rather than at use --
        this is a programming error in whoever added the family, not a
        judgment about anybody's design, and nothing here gates a candidate.
        """
        if not self.sweep_axes:
            raise ValueError(
                f"DesignFamily {self.name!r} declares no sweep_axes. Every family "
                "here is scored across a band rather than at a point, so at least "
                "the frequency axis is always present -- see FREQUENCY_AXIS in "
                "this module, and ADR-0045's own per-example enumeration."
            )
        for axis in self.sweep_axes:
            if not axis.name.strip() or not axis.why.strip() or not axis.supplied_by.strip():
                raise ValueError(
                    f"DesignFamily {self.name!r} declares a SweepAxis with an empty "
                    f"name, why or supplied_by: {axis!r}. An axis nobody wrote a "
                    "reason for is indistinguishable from one nobody chose, which "
                    "is the defect issues #239 and #241 exist to remove."
                )
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
    postprocess=PostProcess(
        name="ONE_PORT_POWER_ABSORPTIVITY",
        consumes="the solver's power reflectance R = |S11|^2, per frequency",
        produces=(
            "absorptivity A = 1 - R, per frequency, which the score then reduces to "
            "its worst value in band"
        ),
        function="orchestration.design_loop._one_port_absorption",
    ),
    sweep_axes=(FREQUENCY_AXIS,),
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
        # issue #249: orchestration/design_loop.py's own
        # _handle_analysis_absorber requires exactly these eight fields
        # (its own _require_fields call), plus eps_r for
        # _resolve_eps_r_bounds -- matching tests/test_design_loop.py's own
        # _ABSORBER_ANALYSIS_INPUT fixture field-for-field. Before this,
        # orchestration/solver.py stripped every one of them, keeping only
        # the patch antenna's eps_r/w_m/h_m/l_m.
        required_fields=(
            "f_low_hz",
            "f_high_hz",
            "eps_r",
            "tan_delta",
            "thickness_m",
            "period_m",
            "gap_m",
            "sheet_resistance_ohm_sq",
            "squares",
        ),
    ),
    # issue #249: this family's SIMULATION result (orchestration/
    # design_loop.py's _simulate_meep_floquet, via _meep_absorption_for_
    # family) carries "worst_absorption", a dimensionless 0-1 fraction --
    # never "gain_dbi", which orchestration/solver.py used to score by
    # default regardless of family and which this result has no such key
    # for at all.
    simulation_scored_field=ScoredField(result_field="worst_absorption", unit="fraction"),
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
    postprocess=PostProcess(
        name="TWO_PORT_POWER_ABSORPTIVITY",
        consumes=(
            "the solver's power reflectance R = |S11|^2 AND its power transmittance "
            "T = |S21|^2, per frequency -- both, never one"
        ),
        produces=(
            "absorptivity A = 1 - R - T, per frequency. ADR-0045's 'power arithmetic' "
            "for Example 3, and the reason #243 makes the loop refuse to run this "
            "family without a measured transmittance: with only R in hand the "
            "arithmetic would credit as absorbed every watt that merely escaped out "
            "the back."
        ),
        function="orchestration.design_loop._two_port_absorption",
    ),
    sweep_axes=(FREQUENCY_AXIS,),
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
        # issue #249: orchestration/design_loop.py's own
        # _handle_analysis_transmissive_absorber requires the identical
        # field set ABSORBER's own handler does (rf_tools/
        # transmissive_absorber.py's signature matches rf_tools/absorber.py's
        # exactly) -- only the arithmetic differs, not the inputs.
        required_fields=(
            "f_low_hz",
            "f_high_hz",
            "eps_r",
            "tan_delta",
            "thickness_m",
            "period_m",
            "gap_m",
            "sheet_resistance_ohm_sq",
            "squares",
        ),
    ),
    # issue #249: same MEEP_FLOQUET absorption path as ABSORBER
    # (_meep_absorption_for_family dispatches on port_count, not on family
    # identity), so the same "worst_absorption" fraction is this family's
    # own SIMULATION scored field too.
    simulation_scored_field=ScoredField(result_field="worst_absorption", unit="fraction"),
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
    postprocess=_NoPostProcess(
        reason=(
            "NEC2 reports this family's scored quantities itself. "
            "simulation/nec2pp.py's parser reads a feed-point impedance and a peak "
            "gain straight out of the solver's own output "
            "(`parse_nec2_output` returns 'impedance' and 'gain_dbi'), and #101's "
            "VSWR and return loss are one-line conversions of that impedance that "
            "rf_tools.network_parameters already provides "
            "(`vswr_from_gamma`, `return_loss_db`). There is no retrieval, no "
            "energy-balance sum and no polarisation decomposition between the "
            "solver and the score. Recorded as a positive statement, not as a "
            "blank: 'nothing to compute' and 'nobody wrote the computation' are "
            "different facts."
        )
    ),
    sweep_axes=(FREQUENCY_AXIS,),
    analysis_model=AnalysisModel(
        name="PATCH_RESONANT_FREQUENCY",
        function="rf_tools.patch_synthesis.patch_resonant_frequency_hz",
        answers=(
            "the frequency at which this patch radiates -- the transmission-line "
            "resonance of a rectangular microstrip patch, from its length, width, "
            "substrate height and permittivity. A question about a RADIATOR, "
            "which is why it must never be asked of a surface whose whole job is "
            "to transmit nothing (issue #191)."
        ),
        # issue #249: orchestration/design_loop.py's own
        # _handle_analysis_patch requires exactly w_m/h_m/l_m (its own
        # _require_fields call), plus eps_r for _resolve_eps_r_bounds --
        # the exact shape orchestration/solver.py's own _REQUIRED_FIELDS
        # already hardcoded for every family until this fix; kept
        # identical here so PATCH's own scoring is byte-for-byte
        # unchanged.
        required_fields=("eps_r", "w_m", "h_m", "l_m"),
    ),
    # issue #249: NEC2's own parser reads a peak gain straight off its
    # output as "gain_dbi" (simulation/nec2pp.py's parse_nec2_output) --
    # the exact field orchestration/solver.py's own _DEFAULT_SCORE_FIELDS
    # already hardcoded for every family until this fix; kept identical
    # here so PATCH's own scoring is byte-for-byte unchanged.
    simulation_scored_field=ScoredField(result_field="gain_dbi", unit="dBi"),
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
    simulation_adapter=SimulationAdapter(
        name="PALACE_FLOQUET",
        reason=(
            "settled at issue #252, closing the two gaps that kept this family "
            "unsettled: this family is designed by its per-cell reflection PHASE "
            "-- how far a bounce off one cell shifts the wave's timing -- and "
            "simulation/meep.py still cannot pose that question at all (its own "
            "scope section says 'NO complex phase'), so it remains the wrong "
            "adapter no matter what a candidate's geometry looks like. "
            "simulation/palace.py DOES return phase, validated against a real "
            "Palace binary to within 0.91 degrees on Palace's own "
            "dielectric-grating example (issue #210, "
            "docs/palace-floquet-validation.md), and #252 ticket 1 taught it to "
            "mesh an embedded PEC conductor patch -- a real printed metasurface "
            "element, not just an all-dielectric grating -- and #252 ticket 2 "
            "taught it to emit a ground-backed, one-port cell (a PEC termination "
            "in place of the second, non-excited Floquet port) matching this "
            "family's own requires_ground_plane=True/port_count=1. A settled "
            "adapter is not a promise every candidate's geometry is ready to "
            "hand it, though: simulation/palace.py's "
            "metasurface_capability_gaps() checks, per candidate, that its "
            "geometry actually sets ground_backed=True and carries at least one "
            "pec_patches entry, and refuses by name rather than quietly running "
            "Palace's OTHER (transmissive, all-dielectric) shape instead."
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
    postprocess=NO_POSTPROCESS_PHASE_READ_DIRECTLY,
    sweep_axes=(
        FREQUENCY_AXIS,
        SweepAxis(
            name="cell geometry parameter",
            why=(
                "a Tier B family's unit-cell solve does not answer the question -- it "
                "BUILDS A LOOKUP, phase against the dimension that sets it, which the "
                "aperture-level stage then reads to decide which cell goes where. One "
                "geometry gives one point of that lookup and no design. ADR-0045 "
                "assigns Example 4 exactly this axis: 'frequency x geometry'."
            ),
            supplied_by=(
                "the design's own element parameterisation -- one scalar for Example 4, "
                "four to nine dimensions for the others (ADR-0045 Decision point 3)"
            ),
        ),
        SweepAxis(
            name="external material state",
            why=(
                "a tunable member of this family (Example 5) shifts its reflection "
                "phase under an external control variable -- a bias, an intercalation "
                "state -- rather than by changing shape. Sweeping frequency alone "
                "would report ONE state's response and present it as the whole answer "
                "for a device whose entire point is that the answer moves. ADR-0045: "
                "'frequency x material state'. Declared on the family because the "
                "family must be able to EXPRESS it; a candidate carrying no control "
                "variable simply has one value on this axis, which is a fact about "
                "that candidate rather than a different family."
            ),
            supplied_by=(
                "the design's own declared control variable, where it has one; ADR-0045 "
                "left how such human-only inputs are captured undecided and this field "
                "does not decide it either -- it makes the axis visible"
            ),
        ),
    ),
    # Issue #109/CONTEXT.md's own name for this family's Tier B OPTIMIZATION
    # search: which already-characterised symbol goes in which grid square,
    # not a continuous-dimension search -- orchestration/design_loop.py's
    # _handle_optimization dispatches on this field (issue #255 tickets 1-3;
    # #267 is the ticket that finally gave this branch somewhere real to go).
    optimizer_class="COMBINATORIAL",
    # Deliberately nothing to declare, not an omission (#239). What this
    # family needs is a per-cell reflection PHASE -- by how much a bounce off
    # one cell shifts the wave's timing -- and no closed form in this repo
    # returns a phase at all: rf_tools.patch_synthesis offers a patch resonance,
    # rf_tools.absorber a magnitude. Its Tier B evaluation then needs an
    # aperture-level step on top of that per-cell lookup, which no module here
    # performs either. The patch resonant frequency is not a weaker answer to
    # this question; it is the answer to a different one.
    analysis_model=UndeclaredAnalysisModel(
        reason=(
            "a reflection-phase surface is designed by its per-cell reflection "
            "PHASE, and no closed form in rf_tools returns a phase "
            "(rf_tools.patch_synthesis returns a patch resonant frequency; "
            "rf_tools.absorber returns an absorbed fraction). The Tier B "
            "aperture-level step that would turn a per-cell phase lookup into a "
            "steered beam does not exist here either. Both are open work, not "
            "settled models -- see issue #109 for the family and ADR-0022 for "
            "the mechanism-before-prediction rule any new model owes."
        ),
    ),
    # THE DISCREPANCY ADR-0049 REPORTED AND DELIBERATELY DID NOT ADJUDICATE,
    # ADJUDICATED HERE (ADR-0050). ADR-0049's Consequences state that this
    # marker's "primary source NOT yet read" and
    # docs/absorber-thickness-bandwidth-bound.md section 7.1's verbatim quotes
    # of the same paper's Eqs. (4.10), (4.11) and (5.1) "cannot both be true",
    # and send the resolution here. Checking the doc first-hand shows the two
    # were never in contradiction -- they answer different questions:
    #
    #   * The doc QUOTED the paper. Section 7.1 reproduces the abstract, three
    #     displayed equations, and the section-6 tightness figures from the
    #     open-access Lund author manuscript, and ADR-0047 states the
    #     resulting B*lambda_0/d <= 2.6 at Phi = pi/2 as settled. So the
    #     FORMULA is on the record and is not in doubt.
    #   * This marker's own error message defines what "read" means in this
    #     repo, and it is a higher bar than quoting: "Read it first-hand and
    #     record it the way docs/rozanov-bound-primary-source.md and
    #     docs/patch-q-factor-bound-primary-source.md do." Those two are
    #     dedicated primary-source read-throughs recording each bound's
    #     derivation, assumptions and validity box. No
    #     docs/gustafsson-sjoberg-bound-primary-source.md exists.
    #
    # And a second, independent reason the slot cannot become a callable
    # PhysicalBound today: rf_tools/physical_bounds.py implements Rozanov and
    # the Nel/Skrivervik/Gustafsson patch bound and NOTHING for this one, so
    # there is no `feasibility` function to point at. Reading the paper is
    # necessary and not sufficient.
    #
    # *In plain terms: somebody copied the formula out of the paper. Nobody
    # has yet sat down with the paper to write out where it comes from and
    # when it stops applying, and nobody has coded it -- and this programme's
    # rule is that a bound is read to that standard before it is relied on,
    # because the Rozanov "lambda/17 versus 17.2" slip is what happens when a
    # round number is taken from an abstract instead of a derivation.*
    #
    # So the marker STAYS, and the citation below now says which of the two
    # things is missing instead of implying both are. The phrase
    # designs/intended_effects.py quotes is kept verbatim so that quotation
    # stays true.
    physical_bound=UnreadPhysicalBound(
        name="Gustafsson & Sjoberg phase-window bound",
        citation=(
            "M. Gustafsson & D. Sjoberg, 'Physical bounds and sum rules for "
            "high-impedance surfaces', Tech. Report LUTEDX/(TEAT-7198)/1-19/(2010), "
            "later IEEE Trans. Antennas Propag. 59(6):2196-2204, 2011 -- bound on "
            "reflection-phase range versus bandwidth/thickness, as named in issue "
            "#109 -- primary source NOT yet read by this programme. Precisely: its "
            "Eqs. (4.10), (4.11) and (5.1) ARE quoted verbatim, from the "
            "open-access Lund author manuscript, at "
            "docs/absorber-thickness-bandwidth-bound.md section 7.1 -- giving "
            "B*lambda_0/d <= 2*pi*tan(Phi/4), i.e. 2.6 at the standard +/-45 degree "
            "window, which ADR-0047 states as settled. What has NOT happened is a "
            "primary-source read-through of the kind "
            "docs/rozanov-bound-primary-source.md and "
            "docs/patch-q-factor-bound-primary-source.md are, recording the "
            "derivation and the validity box; and no function in "
            "rf_tools/physical_bounds.py evaluates it, so there is nothing to "
            "call. Both are needed before this becomes a PhysicalBound (ADR-0050 "
            "resolving the discrepancy ADR-0049 reported)."
        ),
    ),
)


DIFFUSIVE = DesignFamily(
    name="DIFFUSIVE",
    simulation_adapter=SimulationAdapter(
        name="PALACE_FLOQUET",
        reason=(
            "settled at issue #252, alongside REFLECTION_PHASE, which this "
            "family's unit-cell physics matches exactly: a coding/diffusive cell "
            "IS its reflection phase -- a '0' and a '1' are two cells 180 "
            "degrees apart -- so it needs the same per-cell phase, and hits the "
            "same wall with simulation/meep.py, which still returns no phase at "
            "all ('NO complex phase', its own scope section) no matter what a "
            "candidate's geometry looks like. #252 ticket 1 taught "
            "simulation/palace.py to mesh an embedded PEC conductor patch and "
            "ticket 2 taught it to emit a ground-backed, one-port cell (a PEC "
            "termination in place of the second, non-excited Floquet port) "
            "matching this family's own requires_ground_plane=True/port_count=1. "
            "What this family is actually SCORED on -- how much backscatter the "
            "whole ARRANGEMENT redistributes away from the radar -- still lives "
            "above the unit cell and no module here performs that aperture-level "
            "step (that is what keeps this family Tier B); PALACE_FLOQUET is "
            "settled here only as the unit-cell phase-lookup solver that feeds "
            "it, not as an answer to that separate, still-open question. A "
            "settled adapter is not a promise every candidate's geometry is "
            "ready to hand it, though: simulation/palace.py's "
            "metasurface_capability_gaps() checks, per candidate, that its "
            "geometry actually sets ground_backed=True and carries at least one "
            "pec_patches entry."
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
    postprocess=NO_POSTPROCESS_PHASE_READ_DIRECTLY,
    sweep_axes=(
        FREQUENCY_AXIS,
        SweepAxis(
            name="tile assignment",
            why=(
                "this family's design variable is WHICH letter goes in WHICH square, "
                "not a dimension -- a '0' and a '1' are two cells 180 degrees apart, "
                "and the scored quantity is a property of the arrangement. Sweeping "
                "assignments is what the COMBINATORIAL optimizer_class below "
                "searches over. ADR-0045 assigns Example 7 'frequency x tile "
                "assignment x aperture size'."
            ),
            supplied_by=(
                "the Element/Coding-Alphabet library's characterised letters, placed by "
                "the combinatorial search (ADR-0040)"
            ),
        ),
        SweepAxis(
            name="aperture size",
            why=(
                "a MEASURED finite-size effect, not a modelling nicety: ADR-0045 quotes "
                "Murugesan & Selvan finding that 'the 8 and 10 dB RCS reduction "
                "bandwidths drop as array size increases... attributable to mutual "
                "coupling', and Haji-Ahmadi et al. run a full finite 4x4-tile solve on "
                "top of their Floquet cells precisely because it 'accounts for edge "
                "effects and finite-size interactions absent in periodic assumptions'. "
                "So a periodic unit-cell answer OVERSTATES what a real, bounded patch "
                "of this surface does, and the size is a design variable here in a way "
                "it is not for any Tier A family. It also has a hard floor: a "
                "checkerboard's diagonal orders only propagate at supercell period "
                "D >= sqrt(2)*lambda (42.4 mm at 10 GHz), below which there is nowhere "
                "for the redirected power to go -- see NO_PHYSICAL_BOUND's reason above."
            ),
            supplied_by=(
                "the requirement's coverage area, which ADR-0045 lists among the "
                "human-only inputs no solver can supply"
            ),
        ),
    ),
    # Same COMBINATORIAL Tier B search as REFLECTION_PHASE, and for the same
    # reason -- see that family's own comment just above its declaration.
    optimizer_class="COMBINATORIAL",
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
            "to read. Palace's adapter CAN now mesh a printed metal cell -- "
            "'Embedded PEC conductor patches can now be meshed' (simulation/"
            "palace.py, issue #252 tickets 1/2) -- and an anisotropic printed "
            "pattern is what a polarisation converter IS, so the meshing gap "
            "this reason once cited is closed. What is still missing is the "
            "orchestration wiring: orchestration/design_loop.py's PALACE_FLOQUET "
            "handler is wired for REFLECTION_PHASE/DIFFUSIVE only (#252 ticket "
            "3) and has no dispatch path that asks for or scores the "
            "cross-polarised channel this family needs, and this DesignFamily "
            "still declares UnsettledSimulationAdapter rather than naming "
            "PALACE_FLOQUET. So the destination is clearer here than for "
            "REFLECTION_PHASE and DIFFUSIVE -- Palace is the only adapter with "
            "the observable -- but it is still one unbuilt dispatch path away, "
            "so this is recorded as unsettled rather than declared."
        ),
        candidates=(
            "PALACE_FLOQUET -- the only adapter reporting a cross-polarised "
            "channel; can already mesh an embedded metal patch (simulation/"
            "palace.py SCOPE, issue #252 tickets 1/2) but has no orchestration "
            "dispatch path yet that reads the cross-polarised channel for this "
            "family (orchestration/design_loop.py wires PALACE_FLOQUET for "
            "REFLECTION_PHASE/DIFFUSIVE only)",
        ),
        cheapest_test=(
            "hand simulation/palace.py an all-dielectric ANISOTROPIC cell -- a "
            "geometry it can already mesh -- and check that the cross-polarised "
            "specular channel climbs out of the noise floor when the cell's two "
            "axes are made unequal and sinks back into it when they are equal. "
            "That settles whether the observable is usable at all before anyone "
            "spends effort wiring the orchestration dispatch path for an "
            "embedded-PEC anisotropic cell."
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
    postprocess=UnbuiltPostProcess(
        needed=(
            "polarisation-ellipse arithmetic -- the co- versus cross-polarised split "
            "of the reflected wave (and, for a linear-to-circular design, its axial "
            "ratio) computed from the solver's two polarisation channels"
        ),
        reason=(
            "ADR-0045 names this as Example 6's post-processing kind and it exists "
            "nowhere in this repo. simulation/palace.py reports both polarisations of "
            "every diffraction order, so the RAW MATERIAL is there in principle, but "
            "no module turns those two channels into the cross-polarisation ratio "
            "this family is judged on -- and issue #210 found the hard way that the "
            "channels are not interchangeable: a 'specular' convenience view silently "
            "returned a cross-polarised channel at -158 dB, numerical noise, in place "
            "of a true -18.9 dB reflection. That is the exact failure an unwritten "
            "post-process invites, which is why this is recorded as unbuilt-and-named "
            "rather than left blank. Its sibling gap is the analysis_model below; "
            "they are different missing pieces on different sides of the solver."
        ),
    ),
    sweep_axes=(
        FREQUENCY_AXIS,
        SweepAxis(
            name="incidence angle",
            why=(
                "ADR-0045 assigns Example 6 'frequency x incidence angle', and the "
                "reason is physical rather than bookkeeping: this family's whole "
                "mechanism is an ANISOTROPIC cell with two unequal principal-axis "
                "responses, and how much of the wave a cell turns depends on how the "
                "arriving field is oriented relative to those axes. Tilt the wave and "
                "the projection onto each axis changes, so the conversion ratio "
                "changes -- a normal-incidence-only sweep answers for one geometry of "
                "illumination and says nothing about the rest of the envelope the "
                "spine's `incidence_envelope` field exists to state."
            ),
            supplied_by=(
                "the requirement's incidence and polarisation envelope -- a spine field, "
                "and one ADR-0045 lists among the human-only inputs"
            ),
        ),
    ),
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


# ISSUE #453 -- WHY A RADOME IS ITS OWN FAMILY AND NOT ABSORBER_TRANSMISSIVE
# WITH THE OBJECTIVE TURNED ROUND.
#
# ADR-0027 section 5 gives the test: an import is a new FAMILY, rather than a
# new letter, if and only if it needs a different `physical_bound`,
# `analysis_model`, `optimizer_class` or `simulation_adapter` -- four
# plug-ins, the fourth added by that ADR's 2026-09-10 correction after #453
# found the three-plug-in version filing this exact architecture as a letter.
# Applied here, one at a time, against ABSORBER_TRANSMISSIVE (the only
# ground-less two-port family that existed before this one):
#
#   physical_bound      SAME SHAPE. Both are unread: Rozanov does not reach
#                       either, since its derivation opens by fixing a slab
#                       "overlying a perfectly reflecting plane". Different
#                       bounds are NAMED (an absorbing screen's bandwidth
#                       versus a passband's) but neither has been read, so
#                       this test does not decide it.
#   simulation_adapter  SAME. A periodic unit cell needs a Floquet boundary
#                       either way, and simulation/meep.py returns both the
#                       reflected and the transmitted share since #240.
#   optimizer_class     SAME. Neither declares one.
#   analysis_model      DIFFERENT, and this is what decides it.
#                       ABSORBER_TRANSMISSIVE's is
#                       TRANSMISSIVE_ABSORBER_BAND_RESPONSE, which answers
#                       "what fraction of the arriving power does this surface
#                       turn into HEAT at its worst frequency in band". A
#                       radome is judged on what fraction goes THROUGH.
#
# WHAT IT COSTS TO GET THIS WRONG, ON A REAL MEASURED PART. A screen-printed
# Ti3C2Tx chessboard FSS reported at X-band average radar transmittance 78%
# and reflectivity as low as 16% (J. Alloys Compd., PII S0925838826025946,
# recorded on #453; provenance UNVERIFIED -- the primary paper has not been
# read here) has absorptivity A = 1 - 0.16 - 0.78 = 0.06. Scored against
# ADR-0041's -10 dB / A >= 0.900 default that is 6% of the bar: a catastrophic
# failure. It is in fact a near-ideal radome, because 78% of the radar energy
# going straight through is the entire point of the part. *In plain terms: a
# see-through window and a sponge want opposite things. Measure the window
# with the sponge's ruler and the best window in the room comes bottom of the
# class.*
#
# THE ALTERNATIVE #453 RAISES, AND WHY IT IS REJECTED. The other candidate fix
# is an `objective_sense` field on ABSORBER_TRANSMISSIVE -- one family, one
# model, a flag saying which direction is better. It does not work, and the
# refutation is arithmetic rather than taste. Flipping the sense gives
# "minimise absorptivity". Under that rule a PERFECT MIRROR (R = 1, T = 0,
# A = 0.00) beats the 78%-transmitting radome (A = 0.06) -- and a perfect
# mirror is the worst possible radome. Minimising absorption is not the same
# instruction as maximising transmission, because a third term (reflection)
# absorbs the difference. **The quantity is wrong, not just its direction.**
#
# AND THE REGISTRY DELIBERATELY DOES NOT CARRY OBJECTIVE SENSE AT ALL.
# designs/intended_effects.py already holds it, per quantity rather than per
# effect (ADR-0049 point 4), which is where the radome-versus-absorber
# opposition is actually pinned: both MAXIMISE their own quantity, and the
# defect lives one level down, in what each wants from ABSORPTIVITY. Putting a
# second copy on the family would create two places that can disagree about
# the same fact -- and it cannot be done by import in any case, because
# intended_effects.py reads THIS module, so the dependency only runs one way.
# A family declares what quantity it COMPUTES; which direction is better
# belongs to the requirement's intended effect.
BANDPASS_FSS = DesignFamily(
    name="BANDPASS_FSS",
    simulation_adapter=SimulationAdapter(
        name="MEEP_FLOQUET",
        reason=(
            "the same case ABSORBER_TRANSMISSIVE makes, reaching a different "
            "quantity out of the same run: a periodic unit cell needs a periodic "
            "boundary and NEC2's thin-wire formulation cannot express one, and "
            "simulation/meep.py can build what this family is made of -- a single "
            "patterned conductor layer on a thin host with free space on both "
            "sides. What makes the adapter usable HERE specifically is #240's "
            "transmission-side monitor (opt-in via geometry's "
            "'transmission_monitor_center_m'): before it, simulation/meep.py "
            "computed power reflectance only, which for an absorber is half the "
            "answer and for a radome is none of it. A settled adapter is not a "
            "promise a given run will deliver -- simulation/meep.py reports its "
            "own capability gaps (#229/#230) and orchestration/design_loop.py "
            "refuses a two-port family with no measured transmittance (#243) "
            "rather than filling the gap with reflectance."
        ),
    ),
    description=(
        "A radar-transparent bandpass frequency-selective surface -- a radome, or "
        "a window that is deliberately see-through only at the frequencies the "
        "system cares about. One patterned conductor layer, no spacer, no "
        "reflector behind it; the pattern's apertures resonate and open a "
        "passband, and away from that passband the same sheet reflects. It is "
        "scored on how much power gets THROUGH in band, and it must never be "
        "scored on how much it swallows: a part that absorbs 6 percent and "
        "transmits 78 percent is an excellent radome and would read as a failing "
        "absorber. "
        "\n\n"
        "PROBABLY THE MOST FABRICABLE ARCHITECTURE THIS PROGRAMME HAS. ADR-0017's "
        "2026-09-06 correction records it as flat printed conductor -- square-loop "
        "slots in a ~15 um metal layer, every feature clearing the 0.2 mm floor, "
        "modelled at a 62-80 percent passband with about 0 dB insertion loss -- "
        "and calls it 'the one architecture with no registration risk whatsoever', "
        "because a bandpass needs exactly one patterned layer and no backing at "
        "all. That is the opposite of what ADR-0017's reflector default was "
        "protecting against, which is why that ADR had to be amended: it had "
        "assumed the transmissive class was empty. #188 reached the same finding "
        "independently -- 'flat printed conductor and trivially printable'. Its "
        "tuning handle is a gap swept 120-360 um, and the useful end of that "
        "sweep clears the Voltera NOVA's ~100-120 um line floor about three times "
        "over -- though 120 um itself sits AT that floor, which is a Capability "
        "warning on the narrow end rather than an exclusion (ADR-0028: warn and "
        "proceed; equipment shapes the ranking, never the search). "
        "\n\n"
        "A CANDIDATE IN THIS FAMILY MUST STATE THAT IT NEEDS NO REFLECTOR. "
        "ADR-0017's standing default is that the base printed layer supplies its "
        "own ground plane; a printed reflector behind a radome is a "
        "contradiction, not a conservative choice, so the requirement has to "
        "assert the absence explicitly -- exactly as that ADR already provides "
        "for a confirmed host ground plane."
    ),
    simulation_tier=SimulationTier.TIER_A,
    requires_ground_plane=False,
    port_count=2,
    spine_fields=SPINE_FIELDS,
    postprocess=_NoPostProcess(
        reason=(
            "the solver returns this family's scored quantity itself. "
            "simulation/meep.py's transmission monitor reports POWER transmittance "
            "T = |S21|^2 per frequency, which is what MIL-R-7705B 3.4.1.1 calls "
            "'one-way power transmission' and is the number this family is judged "
            "on -- there is no sum between the two. Worth stating rather than "
            "leaving blank, because it is a real difference from "
            "ABSORBER_TRANSMISSIVE, which reads the SAME two solver outputs and "
            "must then compute A = 1 - R - T from them. Same run, same monitors, "
            "different arithmetic afterwards -- which is ADR-0045's point that "
            "post-processing kind is its own registry axis."
        )
    ),
    sweep_axes=(
        FREQUENCY_AXIS,
        SweepAxis(
            name="incidence angle",
            why=(
                "a radome is a curved skin over an antenna that SCANS, so the same "
                "surface is struck at a different angle for every beam position, and "
                "a resonant aperture's passband walks with incidence. MIL-R-7705B "
                "3.4.1.1 asks for 'the minimum AND average one-way power "
                "transmission' -- an average is an average over something, and for a "
                "radome that something is the scan volume -- and its companions "
                "3.4.1.7/3.4.1.8 specify beam deflection and deflection RATE, "
                "quantities that only exist because the beam moves. Reading the "
                "specification that way is this programme's own inference, not a "
                "verbatim statement in it; what is verbatim is that a single "
                "boresight number does not satisfy 3.4.1.1 on its own."
            ),
            supplied_by=(
                "the requirement's incidence and polarisation envelope (a spine field), "
                "or the scan volume of the antenna the radome covers -- a human-only "
                "input in ADR-0045's sense"
            ),
        ),
    ),
    # Deliberately nothing to declare (#239), and NOT the same nothing as
    # ABSORBER_TRANSMISSIVE's declared model reused with a flipped sign. The
    # calculation this family needs is a PASSBAND synthesis -- where the
    # resonance of a slot of given dimensions and period sits, how wide the
    # passband is, and how much insertion loss the conductor's finite
    # conductivity costs inside it. rf_tools has nothing of that shape:
    # rf_tools.absorber and rf_tools.transmissive_absorber return absorbed
    # fractions, rf_tools.patch_synthesis a patch resonance, and
    # rf_tools.filter_synthesis a stepped-impedance LOWPASS realisation in
    # transmission line (ADR-0031), which is a circuit on a board rather than
    # a periodic aperture in free space. In plain terms: nobody here has
    # written the sum for "which frequencies does this pattern of holes let
    # through", so the honest answer is that nobody has written it.
    analysis_model=UndeclaredAnalysisModel(
        reason=(
            "a bandpass FSS is designed by where its aperture resonance sits and "
            "how wide it is, and no closed form in rf_tools computes a passband: "
            "rf_tools.absorber and rf_tools.transmissive_absorber return absorbed "
            "fractions, rf_tools.patch_synthesis a patch's radiating resonance, and "
            "rf_tools.filter_synthesis a stepped-impedance LOWPASS transmission-line "
            "realisation (ADR-0031), which is a different object in a different "
            "medium. ABSORBER_TRANSMISSIVE's model is NOT a weaker answer to this "
            "question -- it answers how much of the wave is turned into heat, and a "
            "good radome turns almost none of it into heat while passing most of it "
            "through, so that model rates the best radome in the corpus at 6 percent "
            "of an absorber's bar. The equivalent-LC-circuit route the reported "
            "Ti3C2Tx chessboard used is the obvious thing to write here, and #453 "
            "carries the reference; until somebody writes it, this raises."
        ),
    ),
    physical_bound=PhysicalBound(
        name="perforated-screen transmission bandwidth bound",
        citation=(
            "A. Ludvig-Osipov, J. Lundgren, C. Ehrenborg, Y. Ivanenko, "
            "A. Ericsson, M. Gustafsson, B. L. G. Jonsson & D. Sjoberg, "
            "'Fundamental Bounds on Transmission Through Periodically "
            "Perforated Metal Screens With Experimental Validation', IEEE "
            "Trans. Antennas Propag. 68(2):773-782, 2020, "
            "doi:10.1109/TAP.2019.2943430 (open author manuscript "
            "arXiv:1810.07669). Their Eq. (12): B <= gamma*pi*Delta/(A*lambda_0) "
            "-- a sum rule on the static polarizability of the aperture's "
            "Babinet-complementary patch shape, derived for 'arbitrary "
            "periodic apertures in thin screens' in free space at normal "
            "incidence -- the BANDPASS_FSS geometry in the source's own "
            "words. Read in full and quoted verbatim in "
            "docs/bandpass-fss-physical-bound-primary-source.md, which also "
            "records why classical Bode-Fano does NOT apply here (section 2: "
            "the far-side load is a pure resistance with Q=0, so the "
            "criterion is vacuous for a physically correct reason -- do not "
            "reintroduce one) and what became of the still-STRANDED Zheng, "
            "Hao & Li (2025) lead this search superseded (section 5)."
        ),
        primary_source_doc="docs/bandpass-fss-physical-bound-primary-source.md",
        feasibility=physical_bounds.perforated_screen_min_polarizability_m3,
        validity=(
            "Infinitely thin (or w/d >= 10, within 2% of the thin-screen "
            "result -- this family's own ~15 um conductor against its "
            "120-360 um gap sweep gives w/d 8-24, holding for all but the "
            "narrowest end of the sweep) PEC screen, normal incidence ONLY "
            "(says nothing about the family's own declared incidence-angle "
            "sweep axis), single propagating Floquet mode (below the "
            "grating-lobe onset -- the same limit "
            "rf_tools/transmissive_absorber.py already states), negligible "
            "cross-polarisation, and enough unit cells (~30x30) that "
            "finite-array truncation is negligible. Bounds passband WIDTH "
            "only -- it says nothing about the insertion-loss FLOOR inside "
            "that width, and its authors explicitly decline to extend it to "
            "lossy impedance surfaces; a printed conductor is not PEC, and "
            "verification/fss_bandpass_circuit_check.py already measured a "
            "lossless reconstruction understating insertion loss by 1.3 dB "
            "on a real paste-printed part. Needs gamma, the aperture's "
            "static polarizability, supplied by the caller -- for this "
            "family's own square-loop-slot shape, "
            "rf_tools.aperture_polarizability.square_loop_polarizability_m3 "
            "(isolated patch) and "
            "square_loop_periodic_array_polarizability_m3 (the periodic-"
            "array-corrected per-unit-cell value Eq. (12) actually needs) "
            "now compute it (issue #547); no other aperture shape has a "
            "solve yet (docs/bandpass-fss-physical-bound-primary-source.md "
            "section 6)."
        ),
    ),
)


# ISSUE #453 / CONTEXT.md's SEVENTH INTENDED EFFECT -- WHY SHIELDING IS ITS OWN
# FAMILY, AND WHY THE ARGUMENT IS NOT THE ONE IT LOOKS LIKE.
#
# "Shielded against" is one of CONTEXT.md's seven intended effects and had no
# family, no analysis_model and no physical_bound anywhere. It is also the
# best-EVIDENCED microwave behaviour available to this programme: the bulk of
# the published Ti3C2Tx microwave measurement corpus reports shielding
# effectiveness rather than absorptivity or reflection phase. So the registry
# could not express the one thing the material literature mostly measures.
#
# THE TEMPTING ARGUMENT, WHICH DOES NOT WORK. It looks obvious that a shield
# is "a radome with the objective flipped". Resist it -- and notice that it is
# exactly the move rejected for BANDPASS_FSS above, so accepting it here would
# be inconsistent. It is worse than that: for BANDPASS_FSS the flip was
# refutable by a counterexample (a mirror beats a radome at minimising
# absorption), and HERE NO SUCH COUNTEREXAMPLE EXISTS. Shielding effectiveness
# is SE_dB = -20*log10|S21| and transmittance is T = |S21|^2, so
# SE_dB = -10*log10(T) exactly: a strictly decreasing function of T. Ranking
# candidates by "most SE" is the precise reverse of ranking them by "most
# transmission", with no exceptions. On the SCORED QUANTITY alone, these two
# really are one quantity read two ways.
#
# THE ARGUMENT THAT DOES WORK IS ABOUT THE MODEL, NOT THE SCORE. ADR-0027
# section 5 asks whether a different `analysis_model` is NEEDED, and an
# analysis model is a calculation from a design's OWN VARIABLES to a predicted
# number -- so the test is about the inputs, not the output. The two
# calculations have disjoint inputs:
#
#   * A bandpass FSS is designed by RESONANT APERTURE GEOMETRY -- slot length,
#     gap, period. Its published tuning handle is a gap swept 120-360 um.
#     Make the conductor thicker and, past a few skin depths, the passband
#     does not move.
#   * A shield is designed by CONDUCTOR THICKNESS AGAINST SKIN DEPTH and by
#     sheet resistance. Make it thicker and SE rises. Cut a gap in it and you
#     have made a hole, which is the one thing a shield must not have.
#
# They are opposite constructions: the best bandpass FSS is a PATTERNED
# conductor (a solid sheet has no passband at all), and the best shield is an
# UNPATTERNED continuous one (every aperture leaks). No single
# parameterisation and no single closed form covers both. *In plain terms: a
# window and a wall are both judged on how much gets past them, but you design
# a window by choosing the size of the holes and a wall by choosing how thick
# to make it -- and there is no setting of one dial that turns one into the
# other.*
#
# WHAT THIS DOES NOT DECIDE. ADR-0049 left open whether "shielded against" is
# a distinct INTENDED EFFECT or "transmitted" with the sense flipped, and
# called it a glossary question. Nothing here answers it, and nothing here
# needs to: a family is a MECHANISM and an effect is an ASK, the mapping
# between them is many-to-many by design, and this family exists because
# attenuation-through-a-conductive-layer is a different mechanism from a
# resonant passband however the glossary resolves the ask. If a later reader
# writes ONE transmission-line model that covers both constructions, that is
# the evidence that would merge these two families -- and it should.
SHIELD = DesignFamily(
    name="SHIELD",
    simulation_adapter=SimulationAdapter(
        name="MEEP_FLOQUET",
        reason=(
            "this family is scored on how far the wave is knocked down on its way "
            "THROUGH, so the run has to report what came out the far side -- which "
            "simulation/meep.py has done since #240 added the transmission-side "
            "monitor, and which orchestration/design_loop.py refuses to substitute "
            "reflectance for since #243. The rest of the case is "
            "ABSORBER_TRANSMISSIVE's: NEC2's thin-wire formulation cannot express a "
            "periodic surface at all, and a printed shield IS one -- even an "
            "unpatterned film is modelled here as a periodic cell with a sheet "
            "impedance. simulation/meep.py's single scalar power reflectance was "
            "the whole obstacle, and it is the transmission side, not the "
            "reflection side, that this family needs."
        ),
    ),
    description=(
        "A barrier: a surface whose job is to stop the wave reaching whatever is "
        "behind it, scored on shielding effectiveness SE_dB = -20*log10|S21| -- "
        "how many decibels the wave loses on the way through. Where the stopped "
        "power goes is NOT what this asks about, which is the difference between "
        "a shield and an absorber and is easy to lose: a perfect reflector "
        "shields perfectly and absorbs nothing, and a good absorber may shield "
        "worse than a sheet of kitchen foil. Its mechanism is attenuation in a "
        "conductive layer -- thickness against skin depth, and sheet resistance -- "
        "not a resonance, which is why it is a different family from BANDPASS_FSS "
        "even though both are judged on |S21|. "
        "\n\n"
        "THE ADR-0017 CONSEQUENCE, AND IT IS SEVERE. ADR-0017 makes every skin "
        "this programme designs print its own conductive reflector by default. A "
        "ground-backed structure transmits nothing by construction -- that is the "
        "reason DesignFamily.__post_init__ forces requires_ground_plane=True to "
        "pair with port_count=1 -- so |S21| = 0, SE is effectively infinite, and "
        "the number carries NO design information for that architecture. *In plain "
        "terms: asking a metal-backed skin how well it blocks radio is like asking "
        "a brick wall how well it blocks daylight. The answer is 'completely', "
        "every time, and it tells you nothing about how to build a better wall.* "
        "So this family is for a requirement that genuinely wants transmission "
        "stopped through an UNBACKED stack -- one where the requirement has "
        "explicitly asserted that no reflector is wanted, exactly as ADR-0017's "
        "2026-09-06 correction provides for -- and NOT for this programme's own "
        "reflector-backed skins, which satisfy any SE requirement trivially and "
        "learn nothing from doing so. "
        "\n\n"
        "WHY IT IS WORTH REGISTERING ANYWAY. It is one of CONTEXT.md's own seven "
        "intended effects, and shielding effectiveness is what a large share of "
        "the published Ti3C2Tx microwave measurements report where an absorber "
        "paper would report reflection loss "
        "(docs/absorber-scoring-decision-confirmation.md section 3.3 records the "
        "field instrumenting its bands this way). A precise share -- roughly 56 "
        "percent of the microwave evidence in this programme's MXene corpus -- was "
        "quoted to the work that added this family and is NOT verified here; the "
        "argument does not depend on the exact figure. Either way a registry that "
        "cannot express shielding cannot reach a large part of the material "
        "evidence this programme already holds."
    ),
    simulation_tier=SimulationTier.TIER_A,
    requires_ground_plane=False,
    port_count=2,
    spine_fields=SPINE_FIELDS,
    postprocess=UnbuiltPostProcess(
        needed=(
            "the decibel transform of the transmitted share, SE_dB = -20*log10|S21| "
            "= -10*log10(T), from the solver's power transmittance"
        ),
        reason=(
            "it is one line of arithmetic and nobody has written it down anywhere "
            "it can be run. "
            "rf_tools.link_noise_budget has linear_to_db and rf_tools.network_parameters "
            "has return_loss_db but neither has a "
            "shielding-effectiveness function, and orchestration/design_loop.py's "
            "post-solver arithmetic computes absorption from reflectance and "
            "transmittance (_one_port_absorption / _two_port_absorption) and stops "
            "there. Recorded as unbuilt-and-named rather than assumed trivial "
            "because the two traps here are the kind that produce a confident "
            "number: it is 20*log10 of the FIELD magnitude, equivalently 10*log10 "
            "of the POWER, and taking 20*log10 of a power transmittance doubles "
            "every answer -- the same voltage-versus-power factor of two that "
            "docs/absorber-thickness-bandwidth-bound.md section 8.1 records "
            "corrupting a published Rozanov comparison; and SE is unbounded above, "
            "so a solver noise floor reads as a spectacular shield rather than as "
            "no signal."
        ),
    ),
    sweep_axes=(FREQUENCY_AXIS,),
    # Deliberately nothing to declare (#239). The calculation this family
    # needs -- Schelkunoff's decomposition of shielding effectiveness into
    # reflection, absorption and multiple-internal-reflection terms, or, for a
    # film thin against a skin depth, the shunt-sheet form that reads SE
    # straight off a sheet resistance -- does not exist in rf_tools. The
    # PIECES are there and that is worth saying, because it makes this a small
    # piece of scoped work rather than a research problem:
    # rf_tools.sheet_impedance already has skin_depth_m, sheet_resistance_ohm_sq
    # (with its own frequency gate on the DC formula) and
    # min_overlay_sheet_resistance_ohm_sq, which is the same shunt-sheet
    # algebra pointed at a different question. Nobody has assembled them into
    # a function that returns SE, and until somebody does, this raises rather
    # than borrowing a model that answers about a different device.
    analysis_model=UndeclaredAnalysisModel(
        reason=(
            "shielding effectiveness is predicted from a conductor's thickness "
            "against its skin depth and its sheet resistance -- Schelkunoff's "
            "reflection + absorption + multiple-reflection decomposition, or the "
            "thin shunt-sheet limit -- and no closed form in rf_tools returns it. "
            "The ingredients exist (rf_tools.sheet_impedance.skin_depth_m, "
            "sheet_resistance_ohm_sq, min_overlay_sheet_resistance_ohm_sq) and "
            "nobody has assembled them. Borrowing BANDPASS_FSS's model is not an "
            "option even once that one is written: a passband synthesis is a "
            "calculation over aperture dimensions, and a shield has no apertures "
            "by construction. Borrowing an absorber's is worse -- a perfect "
            "reflector shields perfectly and absorbs nothing."
        ),
    ),
    physical_bound=UnreadPhysicalBound(
        name="shielding-effectiveness thickness/bandwidth bound",
        citation=(
            "None named for this family in issue #109 or in ADR-0047's per-family "
            "table, and nobody here has searched. Recorded as unread rather than "
            "NO_PHYSICAL_BOUND, deliberately, even though there is a structural "
            "reason to SUSPECT no bound of the Rozanov/Chu shape governs it -- SE "
            "rises monotonically with conductor thickness and conductivity with no "
            "bandwidth penalty, so there is no thickness-versus-bandwidth TRADE for "
            "a sum rule to constrain. That reasoning is this programme's own, "
            "unread and unconfirmed, and it is not enough: DIFFUSIVE's "
            "NO_PHYSICAL_BOUND rests on a documented argument from Rozanov's own "
            "derivation (docs/absorber-thickness-bandwidth-bound.md section 7.3), "
            "and even that is labelled INFERRED and 'needing confirmation'. Absence "
            "of a citation is not evidence that no bound exists. Note for whoever "
            "searches: Schelkunoff's decomposition is a MODEL, not a bound, and "
            "MIL-STD-461 and its relatives are REQUIREMENT standards, not bounds -- "
            "neither has been retrieved here and neither would settle this."
        ),
    ),
)


_REGISTRY: dict[str, DesignFamily] = {
    fam.name: fam
    for fam in (
        ABSORBER,
        ABSORBER_TRANSMISSIVE,
        BANDPASS_FSS,
        PATCH,
        REFLECTION_PHASE,
        DIFFUSIVE,
        POLARIZATION_CONVERTER,
        SHIELD,
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
#
# RE-RUN FOR ADR-0050, at commit 315219864c9b0a9f65e1815d176ec631c3529fb3 (the
# merge of feat/intended-effects-library into this branch), exactly as the
# paragraph above demands rather than by reasoning about what names probably
# exist. The harvest yields: ABSORBER, PATCH, absorbre (the deliberately
# invalid one tests/test_physical_bounds.py exempts by name), diffusive,
# microstrip_patch, patch_antenna, reflection_phase. Every one of those
# already resolves, so adding BANDPASS_FSS and SHIELD needed no new harvested
# entry -- nothing in the tree spells either of them yet, because neither
# existed until now.
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
    # LEFT ALONE ON PURPOSE (#452). "CODING" routing to DIFFUSIVE sends a
    # candidate to NO_PHYSICAL_BOUND, whose reason is conditional in its own
    # text on TWO preconditions -- see that reason string above for both, and
    # for the D >= sqrt(2)*lambda arithmetic (42.4 mm at 10 GHz). It holds
    # only for a surface that REDISTRIBUTES rather than dissipates, and only
    # above a supercell period large enough to launch a propagating
    # diffracted order. A coding checkerboard whose cells are also lossy
    # voids the first precondition; one whose period sits below the
    # grating-lobe onset voids the second and is fully Rozanov-bounded like
    # an absorber. This alias checks neither, so it can route a candidate
    # onto an exemption its own geometry may void. ADR-0047's own table
    # assigns AMC-checkerboard backscatter reduction to Gustafsson &
    # Sjoberg, which REFLECTION_PHASE carries -- so the right routing may
    # well be elsewhere. Re-routing is a DECISION, ticketed at #452, and
    # ADR-0050 does not take it: neither family added there is a backscatter
    # mechanism, so nothing about the two new members changes the answer.
    "CODING": DIFFUSIVE.name,
    "POLARIZATION_CONVERTOR": POLARIZATION_CONVERTER.name,
    "POLARISATION_CONVERTER": POLARIZATION_CONVERTER.name,
    # Near-spellings for the two families added at ADR-0050. Convenience only
    # -- the harvest above found no tree spelling of either, because neither
    # family existed before this commit -- but a reader writing an ARCHITECTURE
    # decision is far more likely to type "radome" than "BANDPASS_FSS", and an
    # accepted spelling recorded here is one a human can audit, which is the
    # whole reason this table exists rather than fuzzy matching.
    "RADOME": BANDPASS_FSS.name,
    "BANDPASS": BANDPASS_FSS.name,
    "BAND_PASS_FSS": BANDPASS_FSS.name,
    "TRANSMISSIVE_FSS": BANDPASS_FSS.name,
    "RADAR_TRANSPARENT": BANDPASS_FSS.name,
    "FREQUENCY_SELECTIVE_SURFACE_PASSBAND": BANDPASS_FSS.name,
    "SHIELDING": SHIELD.name,
    "EMI_SHIELD": SHIELD.name,
    "SHIELDING_SURFACE": SHIELD.name,
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
