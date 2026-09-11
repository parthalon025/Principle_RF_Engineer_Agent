"""Tests for the design-family registry's own shape and membership
(ADR-0018, ADR-0045, ADR-0050; issues #453, #455, #452, #239, #241;
CONTEXT.md: Design family, Design family registry, Physical bound,
Simulation tier).

WHY THIS FILE EXISTS ALONGSIDE tests/test_physical_bounds.py. That file is
headed "Tests for rf_tools/physical_bounds.py and designs/design_families.py"
and already covers the registry's bound, analysis-model and simulation-adapter
slots -- the parts that are about a published bound or a solver. This file
covers what ADR-0050 added and what the registry is as a REGISTRY: the two
ADR-0045 axes (`postprocess`, `sweep_axes`), the two new members, and the
family-versus-letter test that decided them. Pure and DB-free, like
tests/test_material_families.py and tests/test_intended_effects.py.

SEVERAL TESTS HERE ARE TRIPWIRES RATHER THAN DESCRIPTIONS. They are written
to fail loudly on a future change rather than to record today's behaviour for
its own sake:

  * `test_every_family_declares_a_postprocess_and_at_least_one_sweep_axis`
    fails the day family number nine is added without either field.
  * `test_a_radome_and_an_absorber_do_not_want_the_same_thing_from_the_same
    _numbers` pins the 0.06-versus-0.900 arithmetic that made a near-ideal
    radome rank last, so the defect cannot silently return.
  * `test_minimising_absorptivity_is_not_the_same_instruction_as_maximising
    _transmission` pins the counterexample that killed the `objective_sense`
    alternative #453 raised.
"""

from __future__ import annotations

import dataclasses

import pytest

from designs.design_families import (
    ABSORBER,
    ABSORBER_TRANSMISSIVE,
    BANDPASS_FSS,
    DIFFUSIVE,
    FREQUENCY_AXIS,
    NO_POSTPROCESS_PHASE_READ_DIRECTLY,
    PATCH,
    POLARIZATION_CONVERTER,
    REFLECTION_PHASE,
    SHIELD,
    AnalysisModel,
    DesignFamily,
    PhysicalBound,
    PostProcess,
    SimulationTier,
    SweepAxis,
    UnbuiltPostProcess,
    UnbuiltPostProcessError,
    UndeclaredAnalysisModel,
    UnreadPhysicalBound,
    _NoPostProcess,
    get_design_family,
    known_family_names,
)
from rf_tools import physical_bounds

# ---------------------------------------------------------------------------
# ADR-0045's two missing axes: postprocess and sweep_axes
# ---------------------------------------------------------------------------


def test_every_family_declares_a_postprocess_and_at_least_one_sweep_axis():
    """The registry-wide sweep that fails when family number nine forgets.

    ADR-0045's Consequences: "Every design-family registry entry must carry a
    tier field (A/B) plus independent fields for port count, post-processing
    kind, and sweep axes." All four are asserted here across the whole
    registry rather than family by family, so a new member cannot be added
    with either of the two new ones left blank -- which is the whole reason
    they are required with no default (ADR-0050).
    """
    for name in known_family_names():
        family = get_design_family(name)
        # Tier and port count -- the two axes that already shipped.
        assert isinstance(family.simulation_tier, SimulationTier), name
        assert family.port_count in (1, 2), name
        # Post-processing kind: one of the three states, never a bare None,
        # and each state must say something.
        assert isinstance(family.postprocess, PostProcess | UnbuiltPostProcess | _NoPostProcess)
        if isinstance(family.postprocess, PostProcess):
            assert family.postprocess.name.strip(), name
            assert family.postprocess.consumes.strip(), name
            assert family.postprocess.produces.strip(), name
            assert family.postprocess.function.strip(), name
        elif isinstance(family.postprocess, UnbuiltPostProcess):
            assert family.postprocess.needed.strip(), name
            assert family.postprocess.reason.strip(), name
        else:
            assert family.postprocess.reason.strip(), name
        # Sweep axes: never empty, and every axis carries its own reason.
        assert family.sweep_axes, name
        for axis in family.sweep_axes:
            assert axis.name.strip(), name
            assert axis.why.strip(), name
            assert axis.supplied_by.strip(), name


def test_every_family_sweeps_frequency_because_every_family_is_scored_in_band():
    """ADR-0041 scores the single worst frequency in the required band, never
    the mean and never the peak, so a one-frequency evaluation cannot produce
    any family's number. All seven of ADR-0045's patent examples carry
    frequency for the same reason."""
    for name in known_family_names():
        family = get_design_family(name)
        assert "frequency" in family.sweep_axis_names(), name


def test_a_family_cannot_be_constructed_without_a_postprocess_or_sweep_axes():
    """Required with no default, the #239/#241 pattern. A family that forgets
    to say what happens to its solver's output, or what its evaluation has to
    be repeated over, cannot be constructed at all -- rather than quietly
    inheriting whichever answer happens to be modal."""
    common = {
        "name": "FORGOT_SOMETHING",
        "description": "a test fixture, not a real family",
        "simulation_tier": SimulationTier.TIER_A,
        "physical_bound": UnreadPhysicalBound(name="n/a", citation="a test fixture"),
        "analysis_model": UndeclaredAnalysisModel(reason="a test fixture"),
        "simulation_adapter": ABSORBER.simulation_adapter,
        "requires_ground_plane": True,
    }
    with pytest.raises(TypeError, match="postprocess"):
        DesignFamily(**common, sweep_axes=(FREQUENCY_AXIS,))
    with pytest.raises(TypeError, match="sweep_axes"):
        DesignFamily(**common, postprocess=NO_POSTPROCESS_PHASE_READ_DIRECTLY)


def test_an_empty_sweep_axes_tuple_is_refused_rather_than_read_as_a_point_evaluation():
    """An empty tuple is not a conservative description of a family, it is a
    family nobody finished describing -- so it raises at construction, the
    same way the #216 ground-plane/port-count disagreement does."""
    with pytest.raises(ValueError, match="sweep_axes"):
        dataclasses.replace(ABSORBER, sweep_axes=())


def test_a_sweep_axis_with_no_stated_reason_is_refused():
    """An axis nobody wrote a reason for is indistinguishable from one nobody
    chose -- the defect #239 and #241 exist to remove, one field over."""
    with pytest.raises(ValueError, match="SweepAxis"):
        dataclasses.replace(
            ABSORBER,
            sweep_axes=(SweepAxis(name="frequency", why="", supplied_by="the requirement"),),
        )


def test_sweep_axes_follow_neither_the_tier_nor_the_port_count():
    """ADR-0045's load-bearing claim about this field, checked rather than
    quoted: "none of the three is derivable from the tier or from each other."

    Two Tier A families sweep frequency alone; a third Tier A family also
    sweeps incidence angle; and the two Tier B families sweep completely
    different second and third axes from EACH OTHER. If the axes were
    recoverable from the tier, the last pair could not differ.
    """
    assert ABSORBER.simulation_tier is SimulationTier.TIER_A
    assert POLARIZATION_CONVERTER.simulation_tier is SimulationTier.TIER_A
    assert ABSORBER.sweep_axis_names() == ("frequency",)
    assert POLARIZATION_CONVERTER.sweep_axis_names() == ("frequency", "incidence angle")

    assert REFLECTION_PHASE.simulation_tier is DIFFUSIVE.simulation_tier is SimulationTier.TIER_B
    assert REFLECTION_PHASE.sweep_axis_names() != DIFFUSIVE.sweep_axis_names()

    # And two families with the SAME axes differ on tier and port count, so
    # the implication fails in that direction too.
    assert ABSORBER.sweep_axis_names() == ABSORBER_TRANSMISSIVE.sweep_axis_names()
    assert ABSORBER.port_count != ABSORBER_TRANSMISSIVE.port_count


def test_the_tunable_material_state_axis_is_recorded_where_adr_0045_puts_it():
    """ADR-0045's own worked assignment: Example 5's sweep axis is "frequency
    x material state", and #455 names it as precisely the axis the registry
    could not record. A tunable surface swept in frequency alone reports ONE
    bias state's response as though it were the whole answer."""
    axes = REFLECTION_PHASE.sweep_axis_names()
    assert "external material state" in axes
    (material,) = [a for a in REFLECTION_PHASE.sweep_axes if a.name == "external material state"]
    assert "material state" in material.why


def test_postprocess_is_not_analysis_model_wearing_a_hat():
    """#455's genuinely open reading, settled by the registry's own contents
    (ADR-0050).

    If the two fields were one thing, no family could carry two different
    values of it and no family could carry two different NOTHINGS. Both
    happen here:

      * ABSORBER_TRANSMISSIVE has a declared closed form (run on the design,
        before any solver) AND power arithmetic (run on the solver's output,
        after it).
      * REFLECTION_PHASE has neither -- and the two absences say opposite
        things. `UndeclaredAnalysisModel` means "nobody has established one";
        `_NoPostProcess` means "there is definitively nothing to compute".
    """
    assert isinstance(ABSORBER_TRANSMISSIVE.analysis_model, AnalysisModel)
    assert isinstance(ABSORBER_TRANSMISSIVE.postprocess, PostProcess)
    assert ABSORBER_TRANSMISSIVE.analysis_model.function.startswith("rf_tools.")
    assert ABSORBER_TRANSMISSIVE.postprocess.function.startswith("orchestration.")

    assert isinstance(REFLECTION_PHASE.analysis_model, UndeclaredAnalysisModel)
    assert isinstance(REFLECTION_PHASE.postprocess, _NoPostProcess)
    assert not REFLECTION_PHASE.has_analysis_model
    assert REFLECTION_PHASE.needs_no_postprocess


def test_the_three_postprocess_states_are_all_in_live_use_and_behave_differently():
    """Three distinct states, never a bare None -- and the accessor draws the
    line where the work is, not where the value is falsy.

    `declared_postprocess()` raises ONLY for the unbuilt case. "There is no
    sum to do" is an answer; "the sum has not been written" is not.
    """
    assert ABSORBER.has_postprocess
    assert ABSORBER.declared_postprocess() is ABSORBER.postprocess

    assert PATCH.needs_no_postprocess
    assert not PATCH.has_postprocess
    assert PATCH.declared_postprocess() is PATCH.postprocess

    assert isinstance(POLARIZATION_CONVERTER.postprocess, UnbuiltPostProcess)
    assert not POLARIZATION_CONVERTER.has_postprocess
    assert not POLARIZATION_CONVERTER.needs_no_postprocess
    with pytest.raises(UnbuiltPostProcessError) as excinfo:
        POLARIZATION_CONVERTER.declared_postprocess()
    message = str(excinfo.value)
    assert "POLARIZATION_CONVERTER" in message
    assert "polarisation-ellipse" in message
    assert "designs/design_families.py" in message


def test_the_two_one_port_absorption_postprocesses_are_the_arithmetic_243_wired():
    """The power arithmetic is real and already runs -- these two are the
    only built post-processes in the registry, and they differ by exactly the
    transmitted term that issue #216 was about."""
    assert "1 - R" in ABSORBER.postprocess.produces
    assert "1 - R - T" in ABSORBER_TRANSMISSIVE.postprocess.produces
    assert ABSORBER.postprocess.name != ABSORBER_TRANSMISSIVE.postprocess.name


def test_no_two_families_share_one_copy_pasted_unbuilt_postprocess_reason():
    """Writing the same plausible excuse on every open slot would reintroduce
    #241's defect one field over. Each family's reason has to be about that
    family's own missing arithmetic."""
    unbuilt = {family.name: family.postprocess for family in (POLARIZATION_CONVERTER, SHIELD)}
    assert len({pp.needed for pp in unbuilt.values()}) == len(unbuilt)
    assert len({pp.reason for pp in unbuilt.values()}) == len(unbuilt)
    assert "polarisation" in unbuilt["POLARIZATION_CONVERTER"].needed
    assert "S21" in unbuilt["SHIELD"].needed


# ---------------------------------------------------------------------------
# The two new members, and the four-plug-in test that decided them
# ---------------------------------------------------------------------------


def test_the_registry_now_holds_eight_families_including_the_two_new_ones():
    assert known_family_names() == (
        "ABSORBER",
        "ABSORBER_TRANSMISSIVE",
        "BANDPASS_FSS",
        "DIFFUSIVE",
        "PATCH",
        "POLARIZATION_CONVERTER",
        "REFLECTION_PHASE",
        "SHIELD",
    )


def test_both_new_families_are_unbacked_and_two_port():
    """A transmission quantity needs somewhere for the wave to go. Under
    ADR-0017's default every skin here prints its own reflector, and a
    ground-backed structure transmits nothing by construction -- so a radome
    or a shield built on that default would be scored on a quantity that is
    zero (or infinite) by construction and carries no design information."""
    for family in (BANDPASS_FSS, SHIELD):
        assert family.requires_ground_plane is False, family.name
        assert family.port_count == 2, family.name


def test_a_radome_is_a_family_because_its_analysis_model_differs_not_its_sense():
    """ADR-0027 section 5's four-plug-in test, applied to the case that
    forced the fourth plug-in to be named (#453).

    At the time ADR-0050 decided this, three of the four plug-ins were
    SHARED with ABSORBER_TRANSMISSIVE -- the unread bound, the Floquet
    adapter, and no optimizer class at all -- which is precisely why the
    three-plug-in version of the test filed a radome as a LETTER under the
    absorber family. The fourth (analysis_model) was what separated them,
    and that is still the fact this test exists to pin.

    The bound has since stopped being shared (#483 gave BANDPASS_FSS a read,
    cited PhysicalBound -- docs/bandpass-fss-physical-bound-primary-source.md
    -- while ABSORBER_TRANSMISSIVE's stays unread). That does not reopen
    ADR-0050's decision, which never rested on the bound being identical --
    it rested on analysis_model, checked below exactly as before.
    """
    # Same solver.
    assert (
        BANDPASS_FSS.declared_simulation_adapter().name
        == ABSORBER_TRANSMISSIVE.declared_simulation_adapter().name
        == "MEEP_FLOQUET"
    )
    # Same optimizer class -- neither declares one.
    assert BANDPASS_FSS.optimizer_class is ABSORBER_TRANSMISSIVE.optimizer_class is None
    # The bound is no longer shared -- see the docstring above -- but neither
    # is reached by Rozanov, which is the fact this test originally checked
    # here and which still holds for both.
    assert isinstance(BANDPASS_FSS.physical_bound, PhysicalBound)
    assert BANDPASS_FSS.has_physical_bound
    assert isinstance(ABSORBER_TRANSMISSIVE.physical_bound, UnreadPhysicalBound)
    assert "Rozanov" not in BANDPASS_FSS.physical_bound.citation

    # The fourth plug-in is where they part. ABSORBER_TRANSMISSIVE declares a
    # model that answers a question about HEAT; a radome is judged on what
    # gets through, so borrowing it would answer the wrong question -- which
    # is what AnalysisModel.answers exists to make visible.
    assert "heat" in ABSORBER_TRANSMISSIVE.declared_analysis_model().answers
    assert not BANDPASS_FSS.has_analysis_model
    assert "passband" in BANDPASS_FSS.analysis_model.reason

    # And the post-process differs too: same solver, same two monitors,
    # different arithmetic on the way out.
    assert isinstance(ABSORBER_TRANSMISSIVE.postprocess, PostProcess)
    assert BANDPASS_FSS.needs_no_postprocess


def test_a_radome_and_an_absorber_do_not_want_the_same_thing_from_the_same_numbers():
    """THE DEFECT, PINNED IN ARITHMETIC SO IT CANNOT SILENTLY RETURN.

    A screen-printed Ti3C2Tx chessboard FSS reported at X-band average radar
    transmittance 78 percent and reflectivity as low as 16 percent (J. Alloys
    Compd., PII S0925838826025946, recorded on issue #453; provenance
    UNVERIFIED -- the primary paper has not been read here) has absorptivity

        A = 1 - |S11|^2 - |S21|^2 = 1 - 0.16 - 0.78 = 0.06

    Scored against ADR-0041's -10 dB / A >= 0.900 default that is 6 percent of
    the bar, a catastrophic failure -- for what is in fact a near-ideal
    radome, because 78 percent of the radar energy going straight through is
    the entire point of the part.

    *In plain terms: a see-through window and a sponge want opposite things.
    Measure the window with the sponge's ruler and the best window in the room
    comes bottom of the class.*
    """
    reflectivity = 0.16
    transmittance = 0.78
    absorptivity = 1.0 - reflectivity - transmittance
    assert absorptivity == pytest.approx(0.06, abs=1e-12)

    absorber_default_threshold = 0.900  # ADR-0041 point 2, from -10 dB.
    assert absorptivity < absorber_default_threshold
    assert absorptivity / absorber_default_threshold == pytest.approx(0.0667, abs=5e-4)

    # The same part, scored on what was actually asked for.
    assert transmittance > absorptivity
    assert transmittance == pytest.approx(0.78)

    # The registry now has somewhere for it to go that is not the absorber
    # family, which is the whole point of ADR-0050.
    assert BANDPASS_FSS.name in known_family_names()
    assert get_design_family("radome") is BANDPASS_FSS


def test_minimising_absorptivity_is_not_the_same_instruction_as_maximising_transmission():
    """WHY AN `objective_sense` FIELD ON ABSORBER_TRANSMISSIVE WOULD NOT HAVE
    FIXED IT -- the alternative #453 raises, refuted by arithmetic.

    Flip the sense and the rule becomes "minimise absorptivity". Under that
    rule a PERFECT MIRROR beats the radome, and a perfect mirror is the worst
    possible radome: it reflects everything straight back into the antenna it
    is supposed to be transparent to. The quantity is wrong, not just its
    direction, because a third term -- reflection -- absorbs the difference.
    """
    radome = {"R": 0.16, "T": 0.78}
    mirror = {"R": 1.00, "T": 0.00}
    absorptivity = lambda part: 1.0 - part["R"] - part["T"]  # noqa: E731

    # Under "minimise absorptivity", the mirror wins.
    assert absorptivity(mirror) < absorptivity(radome)
    # Under "maximise transmittance", the radome wins -- the right answer.
    assert radome["T"] > mirror["T"]

    # Which is why the registry carries no objective_sense field at all: the
    # sense lives per QUANTITY in designs/intended_effects.py (ADR-0049 point
    # 4), and putting a second copy on the family would create two places
    # that can disagree about one fact.
    assert not hasattr(BANDPASS_FSS, "objective_sense")
    assert not hasattr(ABSORBER_TRANSMISSIVE, "objective_sense")


def test_a_shield_is_a_family_on_its_model_not_on_its_score():
    """SHIELD's case is deliberately NOT the one that carried the radome.

    Shielding effectiveness and transmittance are monotone transforms of each
    other -- SE_dB = -20*log10|S21| and T = |S21|^2, so SE_dB =
    -10*log10(T) -- which means ranking by "most SE" is the exact reverse of
    ranking by "most transmission" and no counterexample of the mirror kind
    can exist. On the scored quantity alone these two ARE one quantity read
    two ways, so that argument is unavailable here and is not used.

    What separates them is the calculation from the design's own variables:
    a bandpass FSS is designed by aperture geometry (a gap swept 120-360 um),
    a shield by conductor thickness against skin depth. Opposite
    constructions -- a solid sheet has no passband, and an aperture is the one
    thing a shield must not have.
    """
    # The monotone relation, so a later reader cannot mistake this for the
    # radome's argument.
    import math

    for t in (0.78, 0.10, 0.01):
        se_from_t = -10.0 * math.log10(t)
        se_from_s21 = -20.0 * math.log10(math.sqrt(t))
        assert se_from_t == pytest.approx(se_from_s21)

    # The argument that is actually used: different missing closed forms,
    # each naming its own variables.
    assert not SHIELD.has_analysis_model
    assert not BANDPASS_FSS.has_analysis_model
    assert SHIELD.analysis_model.reason != BANDPASS_FSS.analysis_model.reason
    assert "skin depth" in SHIELD.analysis_model.reason
    assert "aperture resonance" in BANDPASS_FSS.analysis_model.reason


def test_the_shield_family_records_the_adr_0017_consequence_that_guts_it_by_default():
    """A ground-backed skin transmits nothing by construction, so |S21| = 0,
    SE is effectively infinite, and the number carries no design information
    at all for this programme's own default architecture. The family is for a
    requirement that genuinely wants transmission stopped through an UNBACKED
    stack. Recorded on the family so a reader meets it before using it."""
    assert "ADR-0017" in SHIELD.description
    assert "brick wall" in SHIELD.description
    assert "UNBACKED" in SHIELD.description


def test_the_bandpass_family_records_what_makes_it_the_most_fabricable_architecture_here():
    """ADR-0017's 2026-09-06 correction and #188: one patterned layer, no
    backing, no layer-to-layer registration risk at all -- the opposite of
    what the printed-reflector default was protecting against."""
    assert "registration risk" in BANDPASS_FSS.description
    assert "one patterned layer" in BANDPASS_FSS.description
    assert "120" in BANDPASS_FSS.description  # the gap sweep's narrow end


def test_shield_still_declares_a_bound_it_has_not_read():
    """SHIELD's bound is UnreadPhysicalBound -- "read but unimplemented" is
    the one reading it does not carry. Calling it raises with the citation
    rather than returning a plausible number. Its citation still reads
    "nobody here has searched": #453's structural-suspicion argument stops
    short of an actual literature search.

    BANDPASS_FSS used to be filed alongside SHIELD here, on the same
    UnreadPhysicalBound footing -- see
    test_the_bandpass_bound_is_now_a_real_read_physical_bound below for
    where its state actually is now.
    """
    assert isinstance(SHIELD.physical_bound, UnreadPhysicalBound)
    assert not SHIELD.has_physical_bound
    with pytest.raises(NotImplementedError):
        SHIELD.physical_bound()
    assert "nobody here has searched" in SHIELD.physical_bound.citation


def test_the_bandpass_bound_is_now_a_real_read_physical_bound():
    """BANDPASS_FSS's bound moved past "unread" entirely: #483 read
    Ludvig-Osipov et al. (2020) in full and found it derives exactly the sum
    rule this family needed -- a bound on passband width from the aperture's
    static polarizability, for a periodic aperture array in free space at
    normal incidence, not a Bode-Fano bound (which is vacuous here -- see the
    citation and docs/bandpass-fss-physical-bound-primary-source.md section
    2). The citation must name the source precisely enough that the next
    reader can go straight to it, and must record that classical Bode-Fano
    was checked and rejected rather than merely never tried.
    """
    bound = BANDPASS_FSS.physical_bound
    assert isinstance(bound, PhysicalBound)
    assert BANDPASS_FSS.has_physical_bound
    assert bound.primary_source_doc == "docs/bandpass-fss-physical-bound-primary-source.md"
    citation = bound.citation
    assert "Ludvig-Osipov" in citation
    assert "10.1109/TAP.2019.2943430" in citation
    assert "arbitrary periodic apertures in thin screens" in citation
    assert "Bode-Fano" in citation
    assert "Q=0" in citation
    assert "Zheng" in citation  # the superseded lead is still named, not dropped
    # The feasibility function actually resolves and is callable.
    assert bound.feasibility is physical_bounds.perforated_screen_min_polarizability_m3
    gamma_min = bound(
        f_low_hz=8e9, f_high_hz=12e9, cell_area_m2=(9e-3) ** 2, power_transmittance_threshold=0.8
    )
    assert gamma_min > 0.0
    # Bounds passband WIDTH only -- the validity box must say so, and must
    # name the conductor-loss gap this repo already measured from the other
    # direction (fss_bandpass_circuit_check.py's 1.3 dB finding).
    assert "insertion-loss" in bound.validity
    assert "1.3 dB" in bound.validity
    assert "gamma" in bound.validity


def test_the_shield_bound_records_the_structural_suspicion_without_acting_on_it():
    """The honest half of the bound question, and the one worth guarding.

    There IS a structural reason to suspect no bound of the Rozanov shape
    governs a shield -- SE rises monotonically with thickness with no
    bandwidth penalty, so there is no trade for a sum rule to constrain. That
    reasoning is this programme's own, unread and unconfirmed, so it is
    recorded as a reason to SEARCH and explicitly not used to claim
    NO_PHYSICAL_BOUND. DIFFUSIVE's exemption rests on a documented argument
    from Rozanov's own derivation and even that is labelled INFERRED.
    """
    citation = SHIELD.physical_bound.citation
    assert "NO_PHYSICAL_BOUND" in citation
    assert "unread and unconfirmed" in citation
    assert "MODEL, not a bound" in citation


# ---------------------------------------------------------------------------
# The Gustafsson & Sjoberg discrepancy ADR-0049 reported and did not adjudicate
# ---------------------------------------------------------------------------


def test_the_gustafsson_sjoberg_marker_stays_and_now_says_which_half_is_missing():
    """ADR-0049 called this a discrepancy that "cannot both be true" and sent
    the resolution here. Checking the doc first-hand shows the two were never
    in contradiction, and the marker is right to stay for TWO reasons, both
    now stated on it:

      1. The doc QUOTED the paper -- section 7.1 reproduces Eqs. (4.10),
         (4.11) and (5.1) verbatim from the open-access Lund manuscript -- but
         this marker's own error message defines "read" as a primary-source
         read-through of the kind docs/rozanov-bound-primary-source.md is, and
         no docs/gustafsson-sjoberg-bound-primary-source.md exists.
      2. Independently, rf_tools/physical_bounds.py implements Rozanov and the
         patch Q bound and nothing for this one, so there is no feasibility
         function to point a PhysicalBound at.

    The phrase designs/intended_effects.py quotes is kept verbatim so that
    quotation stays true -- which is also why this test asserts it.
    """
    bound = REFLECTION_PHASE.physical_bound
    assert isinstance(bound, UnreadPhysicalBound)
    # The quoted phrase, unchanged.
    assert "primary source NOT yet read by this programme" in bound.citation
    # And the two things that are now said out loud.
    assert "quoted verbatim" in bound.citation
    assert "rf_tools/physical_bounds.py" in bound.citation
    assert "2.6" in bound.citation


def test_no_function_in_physical_bounds_implements_the_reflection_phase_bound():
    """The second half of the reason above, asserted against the module
    rather than trusted from a comment -- so the day somebody writes it, this
    fails and the marker gets revisited."""
    from rf_tools import physical_bounds

    names = [n for n in dir(physical_bounds) if not n.startswith("_")]
    assert not [n for n in names if "gustafsson" in n.lower() or "sjoberg" in n.lower()]
    # The two that ARE implemented, so a rename cannot make this pass vacuously.
    assert "rozanov_min_thickness_m" in names
    assert "patch_q_factor_lower_bound" in names


# ---------------------------------------------------------------------------
# The CODING alias, deliberately untouched (#452)
# ---------------------------------------------------------------------------


def test_the_coding_alias_still_routes_to_diffusive_and_that_is_a_ticketed_decision():
    """#452 asks what bound a surface reducing backscatter by TWO mechanisms
    at once carries, and observes that "CODING" routing to DIFFUSIVE lands a
    candidate on an exemption its own mechanism may void -- NO_PHYSICAL_BOUND
    holds only for a surface that redistributes rather than dissipates, and
    only above a supercell period of sqrt(2)*lambda.

    ADR-0050 leaves the routing alone: that is a decision with its own
    ticket, and neither family added there is a backscatter mechanism, so
    nothing about the two new members changes what the right routing would
    be. Asserted so the untouched state is deliberate and visible rather than
    an oversight.
    """
    assert get_design_family("CODING") is DIFFUSIVE
    assert not DIFFUSIVE.has_physical_bound
    reason = DIFFUSIVE.physical_bound.reason
    # Both preconditions are on the exemption's own text, as a previous agent
    # left them.
    assert "rather than" in reason
    for family in (BANDPASS_FSS, SHIELD):
        assert "backscatter" not in family.description.lower(), family.name
