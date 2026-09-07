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
    DIFFUSIVE,
    NO_PHYSICAL_BOUND,
    PATCH,
    REFLECTION_PHASE,
    DesignFamily,
    PhysicalBound,
    SimulationTier,
    UnknownDesignFamilyError,
    UnreadPhysicalBound,
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


def test_broadband_floor_reproduces_the_papers_derivation_value_not_its_abstract():
    """Rozanov Eq. (10) gives lambda_max/17.2; the ABSTRACT rounds it to 17.

    Asserting 17.2 rather than 17 is the point: the round number is what
    reaches most secondary sources, and the repo's rule is that a bound is
    read from its derivation.
    """
    lambda_max = 0.03
    floor = rozanov_broadband_thickness_floor_m(SPEED_OF_LIGHT_M_S / lambda_max, -10.0)
    assert lambda_max / floor == pytest.approx(17.2, abs=0.06)


def test_lowest_feasible_center_reproduces_the_hand_derived_thickness_budget_walls():
    """0.87 mm -> 8.37 GHz and 2.0 mm -> 3.64 GHz, at a 40 % band and -10 dB.

    These two numbers were derived by hand in the findings document before
    any of this code existed; if the implementation and the prose ever
    disagree, one of them is wrong and this test says so.
    """
    assert rozanov_lowest_feasible_center_hz(0.87e-3, 0.40, -10.0) == pytest.approx(
        8.37e9, rel=1e-3
    )
    assert rozanov_lowest_feasible_center_hz(2.0e-3, 0.40, -10.0) == pytest.approx(
        3.64e9, rel=1e-3
    )


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
    absorber_metres = ABSORBER.physical_bound(
        f_low_hz=8e9, f_high_hz=12e9, reflectivity_db=-10.0
    )
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
