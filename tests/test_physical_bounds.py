"""Tests for rf_tools/physical_bounds.py and designs/design_families.py
(issue #109; ADR-0018).

The bounds here are not this programme's own derivations -- they are read
from published primary sources -- so the tests that matter most are the ones
that reproduce a number someone else published. Where a source states a
worked example, this file asserts against that example rather than against a
value produced by the implementation itself; where the repo derived a figure
by hand in a findings document, this file asserts against that too, so the
code and the prose cannot drift apart silently.
"""

import math

import pytest

from designs.design_families import (
    ABSORBER,
    ABSORBER_TRANSMISSIVE,
    DIFFUSIVE,
    FREQUENCY_AXIS,
    NO_PHYSICAL_BOUND,
    NO_POSTPROCESS_PHASE_READ_DIRECTLY,
    PATCH,
    POLARIZATION_CONVERTER,
    REFLECTION_PHASE,
    AnalysisModel,
    DesignFamily,
    PhysicalBound,
    SimulationAdapter,
    SimulationTier,
    UndeclaredAnalysisModel,
    UndeclaredAnalysisModelError,
    UnknownDesignFamilyError,
    UnreadPhysicalBound,
    UnsettledSimulationAdapter,
    UnsettledSimulationAdapterError,
    get_design_family,
    is_known_design_family,
    known_family_names,
)
from rf_tools.physical_bounds import (
    SPEED_OF_LIGHT_M_S,
    electrically_thin_ceiling_hz,
    patch_max_fractional_bandwidth,
    patch_q_factor_lower_bound,
    reflectivity_db_to_magnitude,
    rozanov_broadband_thickness_floor_m,
    rozanov_lowest_feasible_center_hz,
    rozanov_max_fractional_bandwidth,
    rozanov_min_thickness_m,
    thin_skin_absorber_window,
)

# ---------------------------------------------------------------------------
# Rozanov -- against the paper's own headline and the repo's own hand-derived
# figures in docs/five-paper-absorber-corpus-findings.md section 2.
# ---------------------------------------------------------------------------


def test_broadband_floor_matches_the_repos_designated_regression_constant():
    """`docs/absorber-thickness-bandwidth-bound.md` already derives this bound
    and names TWO constants as "the real regression tests ... which is what
    lets this document claim the bound is verified rather than recalled":

        d / lambda_max  >=  1.151293 / 19.739209  =  0.058325  =  1 / 17.15
        f_L = c * |Gamma_0| / (171.45 * d),   where 171.45 = 2*pi^2*20/ln(10)

    Those are the repo's anchors, so this test asserts against them rather
    than against a restatement of them. Both are tighter than the round
    numbers in circulation: Rozanov's own abstract says 1/17, and Sci Rep
    9:16359 writes 172 for the second.
    """
    lambda_max = 0.03
    floor = rozanov_broadband_thickness_floor_m(SPEED_OF_LIGHT_M_S / lambda_max, -10.0)

    # Constant 1: the thickness ratio, to the doc's own six decimal places.
    assert floor / lambda_max == pytest.approx(0.058325, abs=5e-7)
    assert lambda_max / floor == pytest.approx(17.15, abs=0.01)

    # Constant 2: the same inequality rearranged. The doc writes the lowest
    # usable frequency as f_L = c*|Gamma_0|/(171.45*d). Substituting
    # f_L = c/lambda_max and |Gamma_0| = 10 dB collapses that to
    # 171.45 = 10*lambda_max/d, so recovering it from the returned thickness
    # checks the arithmetic end to end rather than restating the constant.
    assert 10.0 * lambda_max / floor == pytest.approx(171.45, abs=0.01)
    assert 40 * math.pi**2 / math.log(10) == pytest.approx(171.45, abs=0.01)


def test_lowest_feasible_center_reproduces_the_hand_derived_thickness_budget_walls():
    """0.87 mm -> 8.37 GHz and 2.0 mm -> 3.64 GHz, at a 40 % band and -10 dB.

    These two numbers were derived by hand in the findings document before
    any of this code existed; if the implementation and the prose ever
    disagree, one of them is wrong and this test says so.
    """
    assert rozanov_lowest_feasible_center_hz(0.87e-3, 0.40, -10.0) == pytest.approx(
        8.37e9, rel=1e-3
    )
    assert rozanov_lowest_feasible_center_hz(2.0e-3, 0.40, -10.0) == pytest.approx(3.64e9, rel=1e-3)


def test_electrically_thin_ceiling_reproduces_the_hand_derived_upper_walls():
    assert electrically_thin_ceiling_hz(0.87e-3) == pytest.approx(34.46e9, rel=1e-3)
    assert electrically_thin_ceiling_hz(2.0e-3) == pytest.approx(14.99e9, rel=1e-3)


def test_thickness_bandwidth_and_center_are_mutually_consistent():
    """The three Rozanov entry points are one inequality asked three ways;
    a round trip through all of them must return the input."""
    d, fractional = 1.5e-3, 0.30
    f_c = rozanov_lowest_feasible_center_hz(d, fractional, -10.0)
    assert rozanov_max_fractional_bandwidth(d, f_c, -10.0) == pytest.approx(fractional, rel=1e-9)
    f_low, f_high = f_c * (1 - fractional / 2), f_c * (1 + fractional / 2)
    assert rozanov_min_thickness_m(f_low, f_high, -10.0) == pytest.approx(d, rel=1e-9)


def test_thickness_buys_bandwidth_and_magnetic_loading_buys_more():
    """The bound's whole content: thickness and mu_s are the only levers."""
    thin = rozanov_max_fractional_bandwidth(0.5e-3, 10e9, -10.0)
    thick = rozanov_max_fractional_bandwidth(2.0e-3, 10e9, -10.0)
    assert thick > thin
    magnetic = rozanov_max_fractional_bandwidth(0.5e-3, 10e9, -10.0, mu_s=4.0)
    assert magnetic > thin


def test_a_deeper_absorption_target_costs_bandwidth_at_fixed_thickness():
    shallow = rozanov_max_fractional_bandwidth(1.0e-3, 10e9, -10.0)
    deep = rozanov_max_fractional_bandwidth(1.0e-3, 10e9, -20.0)
    assert deep < shallow


def test_reflectivity_sign_convention_is_accepted_either_way():
    assert reflectivity_db_to_magnitude(-10.0) == pytest.approx(reflectivity_db_to_magnitude(10.0))
    assert reflectivity_db_to_magnitude(-10.0) == pytest.approx(0.3162278, rel=1e-6)


def test_zero_db_reflectivity_is_rejected_rather_than_passing_every_thickness():
    with pytest.raises(ValueError, match="non-zero"):
        reflectivity_db_to_magnitude(0.0)


def test_rozanov_rejects_an_inverted_band():
    with pytest.raises(ValueError, match="strictly greater"):
        rozanov_min_thickness_m(12e9, 8e9, -10.0)


# ---------------------------------------------------------------------------
# The two walls together
# ---------------------------------------------------------------------------


def test_the_thickness_budget_window_is_open_for_the_programmes_own_budget():
    window = thin_skin_absorber_window(2.0e-3, 0.40, -10.0)
    assert not window.is_empty
    assert window.lowest_feasible_center_hz < window.electrically_thin_ceiling_hz


def test_an_impossible_requirement_closes_the_window_at_both_ends():
    """A very wide, very deep band on a thin skin: Rozanov's wall rises above
    the electrical-thickness ceiling, so NO frequency works. The loop should
    be able to say that before spending a solver run."""
    window = thin_skin_absorber_window(0.87e-3, 1.20, -20.0)
    assert window.is_empty


# ---------------------------------------------------------------------------
# Patch Q-factor bound -- against the source paper's own worked example
# ---------------------------------------------------------------------------


def test_patch_q_bound_reproduces_the_papers_worked_example():
    """Nel/Skrivervik/Gustafsson section 5: Q_hw = 95.5 at f_hw = 3.665 GHz
    gives Q_lb ~ 715 at 2.45 GHz."""
    assert patch_q_factor_lower_bound(2.45e9, 3.665e9, 95.5) == pytest.approx(715, rel=5e-3)


def test_patch_bound_converts_to_the_papers_own_stated_bandwidth():
    """The same example continues: 'a -10 dB bandwidth of approximately
    2.3 MHz'. VSWR 1.92496 is the -10 dB return-loss definition."""
    fractional = patch_max_fractional_bandwidth(2.45e9, 3.665e9, 95.5, vswr=1.92496)
    assert fractional * 2.45e9 == pytest.approx(2.3e6, rel=0.02)


def test_the_penalty_is_fifth_power_not_cubic():
    """Halving the frequency below resonance must cost 2^5, not 2^3 -- the
    paper attributes the difference to the ground plane and calls the result
    'orders of magnitude tighter than the Chu bound'."""
    at_resonance = patch_q_factor_lower_bound(4e9, 4e9, 50.0)
    at_half = patch_q_factor_lower_bound(2e9, 4e9, 50.0)
    assert at_half / at_resonance == pytest.approx(32.0)


def test_the_bound_refuses_to_extrapolate_above_the_half_wave_reference():
    """Eq. (5.1) is stated for the below-resonance regime; above it the same
    expression would return an optimistic number outside its derivation."""
    with pytest.raises(ValueError, match="above the half-wave reference"):
        patch_q_factor_lower_bound(5e9, 4e9, 50.0)


# ---------------------------------------------------------------------------
# The registry (ADR-0018)
# ---------------------------------------------------------------------------


def test_the_two_bounds_are_structurally_different_functions():
    """ADR-0018's deciding argument, asserted rather than assumed: the two
    families' bounds do not share a signature, so no single schema with a
    swapped constant could hold both."""
    absorber_metres = ABSORBER.physical_bound(f_low_hz=8e9, f_high_hz=12e9, reflectivity_db=-10.0)
    patch_q = PATCH.physical_bound(
        frequency_hz=2.45e9,
        half_wave_reference_frequency_hz=3.665e9,
        half_wave_reference_q=95.5,
    )
    assert 0 < absorber_metres < 0.01  # metres of stack-up
    assert patch_q > 100  # a dimensionless quality factor
    with pytest.raises(TypeError):
        # The absorber bound cannot even be CALLED with the patch bound's
        # inputs -- which is the point.
        ABSORBER.physical_bound(frequency_hz=2.45e9)


def test_absorber_families_ground_plane_and_port_count_do_not_disagree():
    """Issue #216: `ABSORBER` declared `requires_ground_plane=True` while
    carrying US12089385B2 Example 3 -- a two-port, ground-less structure --
    as its assigned reproduction anchor. A ground-backed absorber has zero
    transmission by construction (one port fully describes it); an unbacked
    one does not (a second port is required to close the energy balance,
    docs/absorber-scoring-conventions.md section 1). So the two properties
    are the same physical fact stated twice and must never disagree.

    This asserts the resolution directly: `ABSORBER` is the ground-backed,
    one-port family issue #216 says it should be, and `ABSORBER_TRANSMISSIVE`
    -- the shape Example 3 actually is -- is ground-less and two-port.
    """
    assert ABSORBER.requires_ground_plane is True
    assert ABSORBER.port_count == 1

    assert ABSORBER_TRANSMISSIVE.requires_ground_plane is False
    assert ABSORBER_TRANSMISSIVE.port_count == 2


def test_every_registered_family_agrees_with_itself_on_ground_plane_and_ports():
    """The general form of the same invariant, checked across the whole
    registry rather than just the two absorber families -- so a future
    family cannot reintroduce issue #216's contradiction under a different
    name."""
    for name in known_family_names():
        family = get_design_family(name)
        if family.requires_ground_plane:
            assert family.port_count == 1, (
                f"{family.name} requires a ground plane (zero transmission by "
                f"construction) but declares port_count={family.port_count}, "
                "not 1"
            )
        else:
            assert family.port_count != 1, (
                f"{family.name} has no ground plane (transmission not "
                "guaranteed zero) but declares port_count=1, which cannot "
                "close the absorption energy balance"
            )


def test_a_design_family_refuses_to_construct_with_disagreeing_flags():
    """The invariant is enforced at construction time, not just satisfied by
    the shipped families -- so a future edit that reintroduces issue #216's
    contradiction fails immediately, at import time, rather than shipping
    silently until a test happens to notice."""
    with pytest.raises(ValueError, match="port_count"):
        DesignFamily(
            name="BROKEN_GROUND_BACKED_TWO_PORT",
            description="a ground-backed family wrongly declaring two ports",
            simulation_tier=SimulationTier.TIER_A,
            physical_bound=NO_PHYSICAL_BOUND,
            analysis_model=UndeclaredAnalysisModel(reason="a test fixture, not a real family"),
            simulation_adapter=UnsettledSimulationAdapter(
                reason="a test fixture, not a real family"
            ),
            postprocess=NO_POSTPROCESS_PHASE_READ_DIRECTLY,
            sweep_axes=(FREQUENCY_AXIS,),
            requires_ground_plane=True,
            port_count=2,
        )
    with pytest.raises(ValueError, match="port_count"):
        DesignFamily(
            name="BROKEN_UNBACKED_ONE_PORT",
            description="an unbacked family wrongly declaring one port",
            simulation_tier=SimulationTier.TIER_A,
            physical_bound=NO_PHYSICAL_BOUND,
            analysis_model=UndeclaredAnalysisModel(reason="a test fixture, not a real family"),
            simulation_adapter=UnsettledSimulationAdapter(
                reason="a test fixture, not a real family"
            ),
            postprocess=NO_POSTPROCESS_PHASE_READ_DIRECTLY,
            sweep_axes=(FREQUENCY_AXIS,),
            requires_ground_plane=False,
            port_count=1,
        )


def test_absorber_transmissive_bound_is_unread_not_rozanov():
    """Rozanov's own derivation opens on a slab 'overlying a perfectly
    reflecting plane' (docs/rozanov-bound-primary-source.md assumption (b)),
    so it cannot be the bound cited for the ground-less
    `ABSORBER_TRANSMISSIVE` family -- that would just relocate issue #216's
    category error one field over."""
    assert isinstance(ABSORBER_TRANSMISSIVE.physical_bound, UnreadPhysicalBound)
    assert not ABSORBER_TRANSMISSIVE.has_physical_bound
    with pytest.raises(NotImplementedError) as exc:
        ABSORBER_TRANSMISSIVE.physical_bound(anything=1)
    assert "not been read" in str(exc.value)


def test_an_unread_bound_is_distinct_from_no_bound_at_all():
    """ADR-0018 rejected a fixed dataclass because 'a None would be ambiguous
    between "not yet computed" and "doesn't exist for this family"'. Both
    states exist in the registry today and must not collapse."""
    assert isinstance(REFLECTION_PHASE.physical_bound, UnreadPhysicalBound)
    assert DIFFUSIVE.physical_bound is NO_PHYSICAL_BOUND
    assert not REFLECTION_PHASE.has_physical_bound
    assert not DIFFUSIVE.has_physical_bound


def test_an_unread_bound_raises_with_its_citation_rather_than_guessing():
    with pytest.raises(NotImplementedError) as exc:
        REFLECTION_PHASE.physical_bound(anything=1)
    assert "Gustafsson" in str(exc.value)
    assert "primary source" in str(exc.value)


def test_a_family_with_no_bound_says_so_differently():
    with pytest.raises(TypeError) as exc:
        DIFFUSIVE.physical_bound()
    assert "no physical bound" in str(exc.value)


def test_every_available_bound_carries_a_citation_and_a_validity_box():
    """A bound with no stated assumptions is the failure mode this whole
    module exists to prevent -- citing a lossless radiation bound against a
    lossy absorber, or vice versa."""
    for family in (ABSORBER, PATCH):
        bound = family.physical_bound
        assert isinstance(bound, PhysicalBound)
        assert bound.citation.strip()
        assert bound.primary_source_doc.startswith("docs/")
        assert len(bound.validity) > 100


def test_the_patch_validity_box_warns_against_the_absorber_category_error():
    assert "absorber" in PATCH.physical_bound.validity.lower()
    assert "lossless" in PATCH.physical_bound.validity.lower()


def test_lookup_is_case_insensitive_and_resolves_the_established_alias():
    """ADR-0018 made retrofitting the existing patch code the registry's own
    validation test. `patch_antenna` is the string already used across this
    repo, so it must resolve -- to the canonical PATCH family."""
    assert get_design_family("patch_antenna") is PATCH
    assert get_design_family("PATCH") is PATCH
    assert get_design_family("absorber") is ABSORBER
    assert get_design_family("  Absorber  ") is ABSORBER


def test_an_unknown_family_raises_and_lists_the_known_ones():
    with pytest.raises(UnknownDesignFamilyError) as exc:
        get_design_family("absorbre")
    message = str(exc.value)
    assert "ABSORBER" in message and "PATCH" in message
    assert not is_known_design_family("absorbre")


def test_every_registered_family_declares_a_tier_and_a_bound_slot():
    for name in known_family_names():
        family = get_design_family(name)
        assert isinstance(family, DesignFamily)
        assert isinstance(family.simulation_tier, SimulationTier)
        assert family.physical_bound is not None
        assert family.description.strip()


def test_tier_b_families_are_the_aperture_level_ones():
    """Tier B is the family whose designed-for behaviour does not exist at
    unit-cell level (#107) -- a steered beam, a suppressed lobe."""
    assert REFLECTION_PHASE.simulation_tier is SimulationTier.TIER_B
    assert DIFFUSIVE.simulation_tier is SimulationTier.TIER_B
    assert ABSORBER.simulation_tier is SimulationTier.TIER_A
    assert PATCH.simulation_tier is SimulationTier.TIER_A


def test_no_bound_returns_infinity_nowhere_and_never_silently_zero():
    """A bound that returns 0 or inf where it should raise would read as
    'anything is achievable', the most dangerous possible failure."""
    assert math.isfinite(rozanov_min_thickness_m(8e9, 12e9, -10.0))
    assert rozanov_min_thickness_m(8e9, 12e9, -10.0) > 0


# ---------------------------------------------------------------------------
# Issue #239: every family DECLARES which analysis it needs, in writing
# ---------------------------------------------------------------------------


def test_every_family_states_an_analysis_model_or_states_why_it_has_none():
    """No family may be silent about this. In plain terms: either it says
    which sum works this kind of surface out, or it says why nobody can."""
    for name in known_family_names():
        family = get_design_family(name)
        assert isinstance(family.analysis_model, AnalysisModel | UndeclaredAnalysisModel)
        if family.has_analysis_model:
            assert family.analysis_model.name.strip()
            assert family.analysis_model.function.strip()
            # `answers` exists because the defect this field removed was a
            # valid number answering a question about a different device.
            assert family.analysis_model.answers.strip()
        else:
            assert family.analysis_model.reason.strip()


def test_the_two_families_with_a_model_declare_the_ones_they_already_ran():
    """#239 changes HOW the model is chosen, never WHICH one these two get."""
    assert ABSORBER.declared_analysis_model().name == "ABSORBER_BAND_RESPONSE"
    assert ABSORBER.declared_analysis_model().function == "rf_tools.absorber.absorber_band_response"
    assert PATCH.declared_analysis_model().name == "PATCH_RESONANT_FREQUENCY"
    assert (
        PATCH.declared_analysis_model().function
        == "rf_tools.calculations.patch_resonant_frequency_hz"
    )


def test_asking_a_family_with_no_model_raises_naming_the_family_and_the_file():
    """The message has to be actionable on its own: which family, what is
    missing, where to put it -- the standard UnknownDesignFamilyError and
    UnreadPhysicalBound already set."""
    for family in (DIFFUSIVE, POLARIZATION_CONVERTER, REFLECTION_PHASE):
        assert not family.has_analysis_model
        with pytest.raises(UndeclaredAnalysisModelError) as exc:
            family.declared_analysis_model()
        message = str(exc.value)
        assert family.name in message
        assert "analysis_model" in message
        assert "designs/design_families.py" in message
        # The family's own recorded reason travels with the refusal -- a
        # reader should not have to open this file to learn why.
        assert family.analysis_model.reason[:40] in message


def test_the_transmissive_absorber_declares_the_two_port_model():
    """#239 removed the wrong dispatch and left this family with nothing to
    declare; #242 gave it the unbacked two-port model. What the declaration
    must NOT be is the ground-backed one -- that model's sum is legitimate
    only because a ground plane guarantees nothing gets through."""
    model = ABSORBER_TRANSMISSIVE.declared_analysis_model()
    assert model.name == "TRANSMISSIVE_ABSORBER_BAND_RESPONSE"
    assert model.function == ("rf_tools.transmissive_absorber.transmissive_absorber_band_response")
    assert model.name != ABSORBER.declared_analysis_model().name
    # The plain-language statement has to say what makes this family
    # different: power leaves out the back and is not absorbed.
    assert "S21" in model.answers


def test_a_family_cannot_be_constructed_without_stating_its_analysis():
    """Required with no default: forgetting is impossible rather than
    invisible."""
    with pytest.raises(TypeError, match="analysis_model"):
        DesignFamily(
            name="FORGOT_TO_SAY",
            description="a family that never stated which analysis it needs",
            simulation_tier=SimulationTier.TIER_A,
            physical_bound=NO_PHYSICAL_BOUND,
            simulation_adapter=UnsettledSimulationAdapter(reason="a test fixture"),
            requires_ground_plane=True,
        )


# ---------------------------------------------------------------------------
# Issue #241: every family states a solver, or states that it is unsettled
# ---------------------------------------------------------------------------


def test_every_family_states_a_solver_or_states_that_the_choice_is_open():
    """No family may be silently unset. In plain terms: either it names the
    simulator that can describe this kind of surface, or it says out loud
    that nobody has worked out which one can."""
    for name in known_family_names():
        family = get_design_family(name)
        assert isinstance(family.simulation_adapter, SimulationAdapter | UnsettledSimulationAdapter)
        assert family.simulation_adapter.reason.strip()
        if family.has_settled_simulation_adapter:
            assert family.simulation_adapter.name.strip()
        else:
            # An open question is only useful if it says what was considered
            # and how to close it -- the charter's warning shape.
            assert family.simulation_adapter.candidates
            assert family.simulation_adapter.cheapest_test.strip()


def test_the_settled_families_keep_the_solvers_they_already_routed_to():
    """#241 changes what happens to families with nothing declared. It must
    not move ABSORBER or PATCH. ABSORBER_TRANSMISSIVE joined them at #243,
    once the adapter could report what passes THROUGH the surface as well as
    what bounces off it."""
    assert ABSORBER.declared_simulation_adapter().name == "MEEP_FLOQUET"
    assert PATCH.declared_simulation_adapter().name == "NEC2"
    assert ABSORBER_TRANSMISSIVE.declared_simulation_adapter().name == "MEEP_FLOQUET"


def test_reflection_phase_and_diffusive_now_declare_palace_floquet():
    """#252 ticket 3: both Tier B unit-cell families settle on the adapter
    that returns a phase at all -- simulation/meep.py never did ('NO complex
    phase', its own scope section), no matter what a candidate's geometry
    looked like. No other field on either family changes."""
    assert REFLECTION_PHASE.has_settled_simulation_adapter
    assert DIFFUSIVE.has_settled_simulation_adapter
    assert REFLECTION_PHASE.declared_simulation_adapter().name == "PALACE_FLOQUET"
    assert DIFFUSIVE.declared_simulation_adapter().name == "PALACE_FLOQUET"
    # Untouched: simulation_tier, requires_ground_plane, physical_bound and
    # analysis_model are unaffected by settling the solver.
    assert REFLECTION_PHASE.simulation_tier is SimulationTier.TIER_B
    assert DIFFUSIVE.simulation_tier is SimulationTier.TIER_B
    assert REFLECTION_PHASE.requires_ground_plane is True
    assert DIFFUSIVE.requires_ground_plane is True
    assert not REFLECTION_PHASE.has_analysis_model
    assert not DIFFUSIVE.has_analysis_model


def test_asking_an_unsettled_family_for_a_solver_raises_with_the_reason_and_the_way_out():
    """POLARIZATION_CONVERTER is the only family left with no settled
    solver: it needs the cross-polarised channel, which simulation/palace.py
    can already report, but that adapter still cannot mesh an anisotropic
    printed cell -- a different gap from the one #252 closed for
    REFLECTION_PHASE/DIFFUSIVE."""
    family = POLARIZATION_CONVERTER
    assert not family.has_settled_simulation_adapter
    with pytest.raises(UnsettledSimulationAdapterError) as exc:
        family.declared_simulation_adapter()
    message = str(exc.value)
    assert family.name in message
    assert "simulation_adapter" in message
    assert "designs/design_families.py" in message
    # The candidates and the cheapest test travel with the refusal: a
    # reader is told what was considered and how to settle it.
    for candidate in family.simulation_adapter.candidates:
        assert candidate in message
    assert family.simulation_adapter.cheapest_test in message


def test_the_transmissive_absorbers_settled_solver_still_records_what_was_missing():
    """#243 settled this family on MEEP_FLOQUET. The reason has to keep
    saying WHY it was open until then -- that reflectance alone is half an
    answer for a surface power can pass through -- or the next reader has no
    way to tell a considered choice from a copied one."""
    assert ABSORBER_TRANSMISSIVE.has_settled_simulation_adapter
    reason = ABSORBER_TRANSMISSIVE.simulation_adapter.reason
    assert "243" in reason
    assert "S21" in reason


def test_reflection_phase_and_diffusives_settled_solvers_still_record_what_closed_them():
    """#252 settled both families on PALACE_FLOQUET. The reason has to keep
    saying WHICH quantity each one actually needs -- REFLECTION_PHASE's own
    words about phase, DIFFUSIVE's about the 180-degree '0'/'1' cells -- and
    both must name the issue and stay distinct from each other, or the next
    reader cannot tell a considered choice from a copied one."""
    reflection_reason = REFLECTION_PHASE.simulation_adapter.reason
    diffusive_reason = DIFFUSIVE.simulation_adapter.reason
    assert reflection_reason != diffusive_reason
    assert "252" in reflection_reason
    assert "252" in diffusive_reason
    assert "phase" in reflection_reason
    assert "180 degrees" in diffusive_reason


def test_the_unsettled_families_do_not_all_share_one_copy_pasted_reason():
    """Writing the same plausible name (or the same excuse) on every open
    family would reintroduce #241's defect one layer up. Each family's
    reason has to be about that family's own missing quantity."""
    reasons = {
        family.name: family.simulation_adapter.reason for family in (POLARIZATION_CONVERTER,)
    }
    assert len(set(reasons.values())) == len(reasons)
    # The quantity it actually needs, named in its own words.
    assert "CROSS-polarised" in reasons["POLARIZATION_CONVERTER"]


def test_a_family_cannot_be_constructed_without_stating_a_solver():
    with pytest.raises(TypeError, match="simulation_adapter"):
        DesignFamily(
            name="FORGOT_THE_SOLVER",
            description="a family that never stated which simulator can pose it",
            simulation_tier=SimulationTier.TIER_A,
            physical_bound=NO_PHYSICAL_BOUND,
            analysis_model=UndeclaredAnalysisModel(reason="a test fixture"),
            requires_ground_plane=True,
        )


# ---------------------------------------------------------------------------
# The alias table guards itself against the tree
# ---------------------------------------------------------------------------


def test_every_design_family_string_written_anywhere_in_the_tree_resolves():
    """`get_design_family` REJECTS what it does not recognise, so every family
    spelling already written in this repo is something the registry can newly
    break -- and one did break: an earlier revision guessed at plausible
    aliases instead of harvesting real ones, and missed
    "reflection_phase_surface" in tests/test_tooling.py.

    This test replaces that guess with a scan. It walks the tree for every
    `design_family = "..."` / `"design_family": "..."` literal and asserts the
    registry resolves it, so adding a new spelling anywhere fails HERE rather
    than in whichever suite happens to use it.

    The one deliberate exception is a string a test uses precisely BECAUSE it
    is invalid, which is listed rather than pattern-matched so a genuine typo
    cannot hide behind the exemption.

    THE SCAN MUST SEE THE SAME TREE CI SEES. It skips `.venv`/site-packages
    for the obvious reason, and `.claude/worktrees` for a much less obvious
    one: a git worktree checked out INSIDE the repo puts a second copy of
    every .py file under the scan root. That copy is at whatever commit the
    worktree sits on, so the scan silently reads spellings that the branch
    under test does not contain. This is not hypothetical -- it is exactly how
    this test passed locally and failed in CI at #239: the spelling asserted
    below had been deleted from the branch and survived only in a worktree.

    That skip must be matched against the path RELATIVE to the repo root. The
    first version compared absolute parts, which works from the main checkout
    and breaks the moment the suite is RUN FROM a worktree: the root is then
    itself `.../.claude/worktrees/agent-x/`, every file matches the skip, and
    the scan finds nothing at all. The `assert found` below is what catches
    that, and it is why that assertion is here rather than being obvious
    belt-and-braces -- a scan that silently narrows to nothing still passes
    every other assertion in this test.
    """
    import re
    from pathlib import Path

    deliberately_invalid = {"absorbre"}
    pattern = re.compile(r"""design_family["']?\s*[=:]\s*["']([A-Za-z0-9_ -]+)["']""")
    repo_root = Path(__file__).resolve().parent.parent

    found: dict[str, list[str]] = {}
    for path in repo_root.rglob("*.py"):
        # Match on the path RELATIVE to the repo root, never its absolute
        # parts: when this test itself runs from inside a worktree, the root
        # is `.../.claude/worktrees/agent-x/`, so an absolute match skips
        # every file in the tree and the scan silently finds nothing. See the
        # docstring.
        relative = path.relative_to(repo_root)
        if {".venv", "site-packages", "worktrees"} & set(relative.parts):
            continue
        for name in pattern.findall(path.read_text(encoding="utf-8", errors="ignore")):
            found.setdefault(name, []).append(str(relative))

    assert found, "the scan found no design_family literals at all -- it has stopped working"
    # Canaries: spellings that ARE in the tree and are not the canonical
    # registry names, so if either stops being found the scan has silently
    # narrowed -- the failure mode that let the first miss through.
    #
    # "reflection_phase_surface" used to be the second canary. #239 removed
    # the last use of it: REFLECTION_PHASE declares no analysis model, so the
    # loop can no longer be driven end to end with it and the test that did
    # so now uses a second PATCH alias. "reflection_phase" (a non-canonical
    # spelling still live in tests/test_design_loop.py) replaces it.
    assert "patch_antenna" in found
    assert "reflection_phase" in found

    unresolvable = {
        name: sites
        for name, sites in found.items()
        if name not in deliberately_invalid and not is_known_design_family(name)
    }
    assert not unresolvable, (
        "these design_family strings are written in the tree but the registry "
        f"rejects them: {unresolvable}. Either register the spelling in "
        "designs/design_families.py's _ALIASES or fix the call site -- do not "
        "add it to this test's exemption list unless the string is meant to be "
        "invalid."
    )


# ---------------------------------------------------------------------------
# RUNNING-LISTS.md section 3 item 33: the MXene skin-depth disagreement
# ---------------------------------------------------------------------------


def test_skin_depth_converts_the_mxene_disagreement_into_a_stated_conductivity():
    """`docs/RUNNING-LISTS.md` section 3 item 33 records a live, unresolved
    ~1.8x disagreement about MXene's skin depth at 10 GHz, and says exactly
    what it needs to settle: *"it needs one stated conductivity at one stated
    frequency."*

    Neither side states one -- they state skin depths. But skin depth and
    conductivity are the same fact in two dresses, so `skin_depth_m` inverts
    each claim into the conductivity it implies, which is the form item 33
    asks for:

      * Correction 7: a 10 um film is "already ~1.65 skin depths at 10 GHz"
        -> delta = 6.06 um -> sigma ~ 6.90e5 S/m
      * Map #104:     "MXene's 3*delta is ~33 um"
        -> delta = 11.0 um -> sigma ~ 2.09e5 S/m

    This does NOT resolve the disagreement -- deciding which conductivity is
    right needs a measurement, and item 33 notes printed MXene genuinely
    spans that range between grades and ages. What it does is check item 33's
    own reasoning about the size of the discrepancy, and put both claims in
    comparable units so a single four-point-probe reading can settle them.
    """
    from rf_tools.calculations import skin_depth_m

    def implied_sigma(delta_m: float) -> float:
        # delta = 1/sqrt(pi*f*mu*sigma)  =>  sigma = 1/(pi*f*mu*delta^2)
        return 1.0 / (math.pi * 10e9 * 4e-7 * math.pi * delta_m**2)

    delta_correction_7 = 10e-6 / 1.65
    delta_map_104 = 33e-6 / 3

    assert delta_correction_7 == pytest.approx(6.06e-6, rel=1e-2)
    assert delta_map_104 == pytest.approx(11.0e-6, rel=1e-2)

    sigma_correction_7 = implied_sigma(delta_correction_7)
    sigma_map_104 = implied_sigma(delta_map_104)
    assert sigma_correction_7 == pytest.approx(6.90e5, rel=1e-2)
    assert sigma_map_104 == pytest.approx(2.09e5, rel=1e-2)

    # Item 33's own arithmetic, checked: "a 1.8x disagreement in delta is a
    # ~3.3x disagreement in the assumed conductivity" -- because delta goes
    # as 1/sqrt(sigma), so the conductivity ratio is the delta ratio squared.
    assert delta_map_104 / delta_correction_7 == pytest.approx(1.8, abs=0.05)
    assert sigma_correction_7 / sigma_map_104 == pytest.approx(3.3, abs=0.05)

    # And the round trip: each implied conductivity reproduces its own claim.
    assert skin_depth_m(10e9, sigma_correction_7) == pytest.approx(delta_correction_7, rel=1e-9)
    assert skin_depth_m(10e9, sigma_map_104) == pytest.approx(delta_map_104, rel=1e-9)
