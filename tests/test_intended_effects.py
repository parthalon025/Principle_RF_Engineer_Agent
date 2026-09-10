"""Tests for designs/intended_effects.py (ADR-0030, ADR-0047, ADR-0018;
CONTEXT.md: Intended effect, Design family, Physical bound).

Pure and DB-free, like tests/test_material_families.py and
tests/test_design_families.py -- this library is a lookup over physics and
over the repo's own registry, so it is exercised directly with no database
and no solver.

Two of the tests below are deliberately written to fail LOUDLY on a future
change rather than to describe today's behaviour for its own sake:
`test_effects_without_family_reports_shielded_against` fails the day someone
registers a shielding family and forgets this table, and
`test_every_registered_design_family_is_claimed_by_some_effect` fails the day
someone adds a seventh design family without wiring it in.
"""

from __future__ import annotations

import dataclasses
import math

import pytest

from designs import design_families
from designs.intended_effects import (
    CONTEXT_MD_SEVEN,
    BoundStatus,
    DefaultThreshold,
    EffectMiss,
    EffectProfile,
    ObjectiveSense,
    ScoringQuantity,
    diffracted_order_min_period_m,
    effects_without_family,
    families_serving,
    families_without_effect,
    known_effect_names,
    objective_sense,
    physical_bound_for,
    resolve_intended_effect,
    scoring_quantity,
)

# ---------------------------------------------------------------------------
# CONTEXT.md's seven, verbatim
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("effect", CONTEXT_MD_SEVEN)
def test_every_context_md_effect_resolves(effect):
    """All seven effects CONTEXT.md's Intended effect entry names, verbatim."""
    profile = resolve_intended_effect(effect)
    assert isinstance(profile, EffectProfile), f"{effect!r} did not resolve"
    assert profile.found is True
    assert profile.in_context_md_seven is True


def test_context_md_seven_is_exactly_seven_and_matches_the_glossary_wording():
    # Guards against this list drifting from CONTEXT.md's own sentence: "what
    # the requirement wants done to the wave -- absorbed, reflected in phase,
    # steered, transmitted, scattered diffusely, polarisation-converted,
    # shielded against."
    assert CONTEXT_MD_SEVEN == (
        "absorbed",
        "reflected in phase",
        "steered",
        "transmitted",
        "scattered diffusely",
        "polarisation-converted",
        "shielded against",
    )


def test_low_infrared_emissivity_resolves_and_is_marked_outside_the_seven():
    """The finding this library records: a real behaviour absent from the
    glossary's seven. Naming it here asserts nothing about whether it belongs
    in CONTEXT.md -- see docs/adr/0049."""
    profile = resolve_intended_effect("low infrared emissivity")
    assert isinstance(profile, EffectProfile)
    assert profile.in_context_md_seven is False
    assert profile.name not in CONTEXT_MD_SEVEN


def test_known_effect_names_covers_the_seven_plus_low_ir_emissivity():
    names = known_effect_names()
    assert len(names) == 8
    for effect in CONTEXT_MD_SEVEN:
        resolved = resolve_intended_effect(effect)
        assert resolved.name in names
    assert "low infrared emissivity" in names


# ---------------------------------------------------------------------------
# THE ADR-0030 GUARANTEE: an unknown effect is a miss, never a raise
# ---------------------------------------------------------------------------


def test_an_unknown_effect_returns_a_miss_and_does_not_raise():
    """ADR-0030's load-bearing guarantee, pinned.

    An intended effect's vocabulary is OPEN, not a closed enum. An effect this
    library has never heard of is therefore the expected case, not an error --
    ADR-0030's own worked example is a requirement asking a surface to "behave
    as a magnetic mirror" when no family served it. If this ever raises, the
    exception climbs into requirement intake and turns an open vocabulary into
    a closed one, which would supersede ADR-0030.
    """
    miss = resolve_intended_effect("teleported sideways through a wormhole")
    assert isinstance(miss, EffectMiss)
    assert miss.found is False
    assert miss.normalised == "teleported sideways through a wormhole"
    # The message must say out loud that this is not an error, so a reader of
    # a log does not treat it as one.
    assert "NOT AN ERROR" in miss.message
    assert "open" in miss.message
    # And it names what the library does know, so a typo is visible.
    for known in known_effect_names():
        assert known in miss.message


def test_every_lookup_function_returns_a_miss_rather_than_raising():
    """Not just `resolve_intended_effect`: no entry point may raise on an
    unrecognised effect, or the guarantee leaks."""
    unknown = "sublimated"
    for call in (
        resolve_intended_effect,
        families_serving,
        scoring_quantity,
        objective_sense,
        physical_bound_for,
    ):
        result = call(unknown)
        assert isinstance(result, EffectMiss), f"{call.__name__} did not return a miss"


@pytest.mark.parametrize("bad", [None, 42, 3.5, [], {}, object()])
def test_a_non_string_argument_is_a_miss_not_a_type_error(bad):
    """This is a lookup, not a validator. A caller handing it the wrong type
    gets a miss and carries on -- nothing about a requirement is rejected."""
    miss = resolve_intended_effect(bad)
    assert isinstance(miss, EffectMiss)
    assert miss.found is False


def test_empty_and_whitespace_names_are_misses():
    for blank in ("", "   ", "\t\n"):
        assert isinstance(resolve_intended_effect(blank), EffectMiss)


def test_a_customer_ask_is_reported_as_ambiguous_never_resolved_to_one_effect():
    """ "Reduce radar return" is CONTEXT.md's own worked example of an ask
    served by several effects. Resolving it to one would be code choosing
    physics -- the same thing designs/design_families.py forbids for family
    selection. One ask served by several effects IS the trade space."""
    miss = resolve_intended_effect("reduce radar return")
    assert isinstance(miss, EffectMiss)
    assert "absorbed" in miss.could_mean
    assert "scattered diffusely" in miss.could_mean
    assert len(miss.could_mean) >= 3
    assert "trade space" in miss.message


# ---------------------------------------------------------------------------
# Spelling, casing, hyphenation, aliases
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("spelling", "canonical"),
    [
        ("absorb", "absorbed"),
        ("Absorption", "absorbed"),
        ("ABSORBED", "absorbed"),
        ("  absorptive  ", "absorbed"),
        ("radar absorbing material", "absorbed"),
        ("magnetic mirror", "reflected in phase"),
        ("behave as a magnetic mirror", "reflected in phase"),
        ("AMC", "reflected in phase"),
        ("Artificial-Magnetic-Conductor", "reflected in phase"),
        ("beam steering", "steered"),
        ("beam-steering", "steered"),
        ("Reflectarray", "steered"),
        ("radome", "transmitted"),
        ("bandpass", "transmitted"),
        ("band pass", "transmitted"),
        ("RF-transparent", "transmitted"),
        ("transmission", "transmitted"),
        ("coding surface", "scattered diffusely"),
        ("diffusive", "scattered diffusely"),
        ("Diffuse Scattering", "scattered diffusely"),
        ("polarisation-converted", "polarisation-converted"),
        ("polarization-converted", "polarisation-converted"),
        ("polarization conversion", "polarisation-converted"),
        ("cross-pol", "polarisation-converted"),
        ("shielding", "shielded against"),
        ("shielded against", "shielded against"),
        ("EMI shielding", "shielded against"),
        ("low IR emissivity", "low infrared emissivity"),
        ("multispectral", "low infrared emissivity"),
        ("thermal_signature", "low infrared emissivity"),
    ],
)
def test_aliases_casing_and_hyphenation_resolve(spelling, canonical):
    profile = resolve_intended_effect(spelling)
    assert isinstance(profile, EffectProfile), f"{spelling!r} did not resolve"
    assert profile.name == canonical


def test_an_alias_and_the_canonical_name_return_the_same_object():
    assert resolve_intended_effect("radome") is resolve_intended_effect("transmitted")
    assert resolve_intended_effect("AMC") is resolve_intended_effect("reflected in phase")


def test_no_alias_is_claimed_by_two_effects():
    """The index builder raises on a collision at import time, so reaching
    this test at all proves the table is unambiguous. Asserted explicitly
    anyway: an alias resolving two ways would silently hand one effect's
    scoring quantity to the other's requirement."""
    seen: dict[str, str] = {}
    for name in known_effect_names():
        profile = resolve_intended_effect(name)
        for spelling in (profile.name, *profile.aliases):
            key = " ".join(spelling.strip().casefold().replace("-", " ").split())
            assert seen.get(key, profile.name) == profile.name
            seen[key] = profile.name


# ---------------------------------------------------------------------------
# The gap report, both directions
# ---------------------------------------------------------------------------


def test_effects_without_family_reports_shielded_against():
    """`shielded against` is one of CONTEXT.md's own seven and NOTHING in
    designs/design_families.py serves it -- no family, no analysis_model, no
    physical_bound.

    This test fails loudly the day somebody registers a shielding family and
    forgets to wire it into designs/intended_effects.py. That is the point of
    asserting it rather than merely reporting it.
    """
    gaps = effects_without_family()
    gapped = {gap.effect for gap in gaps}
    assert "shielded against" in gapped


def test_effects_without_family_reports_the_transmitted_radome_gap():
    """The other CONTEXT.md-named effect with no family, and the one with a
    worked cost attached."""
    gaps = {gap.effect: gap for gap in effects_without_family()}
    assert "transmitted" in gaps
    radome = gaps["transmitted"]
    assert radome.misfiled_as == "ABSORBER_TRANSMISSIVE"
    assert "0.06" in radome.misfiling_cost
    assert radome.cheapest_fix


def test_the_gap_report_is_exactly_the_three_known_gaps_today():
    gapped = {gap.effect for gap in effects_without_family()}
    assert gapped == {"transmitted", "shielded against", "low infrared emissivity"}


def test_a_family_gap_states_itself_in_value_comparator_unit_shape():
    """Capability-warning-SHAPED (precise, queryable), and explicitly not a
    Capability warning and not a capability-verdict: it drops nothing."""
    gaps = {gap.effect: gap for gap in effects_without_family()}
    gap = gaps["shielded against"]
    assert gap.needed_value == 1.0
    assert gap.comparator == ">="
    assert gap.achieved_value == 0.0
    assert "design families" in gap.unit
    statement = gap.as_statement()
    assert "shielded against" in statement
    assert ">=" in statement


def test_families_serving_distinguishes_a_miss_from_a_known_effect_with_no_family():
    """An empty tuple and a miss are different answers and must not collapse
    into one falsy value -- the ambiguity designs/design_families.py's own
    docstring exists to refuse."""
    no_family = families_serving("shielded against")
    assert no_family == ()
    assert not isinstance(no_family, EffectMiss)

    miss = families_serving("nonexistent effect")
    assert isinstance(miss, EffectMiss)


def test_families_serving_names_real_registry_entries():
    for name in known_effect_names():
        for family in families_serving(name):
            assert design_families.is_known_design_family(family), family


def test_absorbed_is_served_by_both_absorber_families():
    served = families_serving("absorbed")
    assert design_families.ABSORBER.name in served
    assert design_families.ABSORBER_TRANSMISSIVE.name in served


def test_one_family_can_serve_two_effects():
    """REFLECTION_PHASE serves both `reflected in phase` and `steered`. The
    effect-to-family mapping is many-to-many, which is why CONTEXT.md keeps
    the two terms apart."""
    assert design_families.REFLECTION_PHASE.name in families_serving("reflected in phase")
    assert design_families.REFLECTION_PHASE.name in families_serving("steered")


def test_every_registered_design_family_is_claimed_by_some_effect():
    """The gap in the other direction.

    PATCH is the one unclaimed family and that is a finding, not an oversight:
    a patch antenna radiates a wave rather than doing something to an arriving
    one, and "radiated" is not among CONTEXT.md's seven either.

    This assertion fails loudly the day a SEVENTH design family is registered
    without being wired into designs/intended_effects.py -- which would
    otherwise leave a family no intended effect can reach.
    """
    assert families_without_effect() == (design_families.PATCH.name,)


# ---------------------------------------------------------------------------
# THE RADOME DEFECT, PINNED
# ---------------------------------------------------------------------------


def test_absorbed_and_transmitted_want_opposite_things_from_absorptivity():
    """The field that prevents the radome defect.

    Both effects MAXIMISE their own scoring quantity, so comparing the two
    `objective_sense` values alone would look harmless. The defect lives one
    level down: asked about ABSORPTIVITY, an absorber wants it maximised and a
    radome wants it minimised. Score a radome with the absorber family's model
    and the ranking inverts -- a near-perfect radome comes last.
    """
    absorbed = resolve_intended_effect("absorbed")
    transmitted = resolve_intended_effect("radome")

    assert absorbed.senses_by_quantity[ScoringQuantity.ABSORPTIVITY] is ObjectiveSense.MAXIMISE
    assert transmitted.senses_by_quantity[ScoringQuantity.ABSORPTIVITY] is ObjectiveSense.MINIMISE
    assert (
        absorbed.senses_by_quantity[ScoringQuantity.ABSORPTIVITY]
        is not transmitted.senses_by_quantity[ScoringQuantity.ABSORPTIVITY]
    )


def test_absorbed_and_transmitted_are_scored_on_different_quantities():
    assert scoring_quantity("absorbed") is ScoringQuantity.ABSORPTIVITY
    assert scoring_quantity("transmitted") is ScoringQuantity.TRANSMITTANCE
    assert scoring_quantity("absorbed") is not scoring_quantity("transmitted")


def test_absorbed_and_transmitted_also_disagree_about_transmittance():
    absorbed = resolve_intended_effect("absorbed")
    transmitted = resolve_intended_effect("transmitted")
    assert absorbed.senses_by_quantity[ScoringQuantity.TRANSMITTANCE] is ObjectiveSense.MINIMISE
    assert transmitted.senses_by_quantity[ScoringQuantity.TRANSMITTANCE] is ObjectiveSense.MAXIMISE


def test_senses_by_quantity_always_contains_the_effects_own_quantity():
    for name in known_effect_names():
        profile = resolve_intended_effect(name)
        assert profile.senses_by_quantity[profile.scoring_quantity] is profile.objective_sense


def test_emissivity_is_the_one_effect_that_minimises_its_own_quantity():
    assert objective_sense("low infrared emissivity") is ObjectiveSense.MINIMISE
    minimisers = [
        name for name in known_effect_names() if objective_sense(name) is ObjectiveSense.MINIMISE
    ]
    assert minimisers == ["low infrared emissivity"]


def test_reflection_phase_holds_a_window_rather_than_maximising_anything():
    """A reflection phase has no "more is better" direction; forcing it into
    MAXIMISE/MINIMISE would be the same category error one level down."""
    assert objective_sense("reflected in phase") is ObjectiveSense.HOLD_IN_WINDOW
    assert objective_sense("steered") is ObjectiveSense.HOLD_IN_WINDOW


# ---------------------------------------------------------------------------
# Fixtures: the port count is part of the quantity's meaning
# ---------------------------------------------------------------------------


def test_shielding_effectiveness_needs_a_two_port_fixture():
    profile = resolve_intended_effect("shielded against")
    assert profile.scoring_quantity is ScoringQuantity.SHIELDING_EFFECTIVENESS
    assert [fixture.port_count for fixture in profile.fixtures] == [2]


def test_shielded_against_records_the_adr_0017_consequence():
    """A skin that prints its own reflector transmits nothing by construction,
    so SE is effectively infinite and carries no design information for that
    architecture. That has to be written down where a caller will see it."""
    profile = resolve_intended_effect("shielded against")
    joined = " ".join(profile.notes)
    assert "ADR-0017" in joined
    assert "zero transmission" in joined
    assert "NO design information" in joined


def test_transmitted_is_two_port_only_and_absorbed_admits_both_fixtures():
    transmitted = resolve_intended_effect("transmitted")
    assert [fixture.port_count for fixture in transmitted.fixtures] == [2]

    absorbed = resolve_intended_effect("absorbed")
    assert sorted(fixture.port_count for fixture in absorbed.fixtures) == [1, 2]


def test_infrared_emissivity_is_not_an_rf_fixture_at_all():
    """port_count is None, not 0: "a two-port measurement with no ports" is a
    different and impossible thing."""
    profile = resolve_intended_effect("low infrared emissivity")
    assert [fixture.port_count for fixture in profile.fixtures] == [None]


# ---------------------------------------------------------------------------
# Physical bounds, per ADR-0047's per-family table
# ---------------------------------------------------------------------------


def test_absorbed_carries_rozanov_as_a_published_bound():
    bounds = physical_bound_for("absorbed")
    rozanov = [b for b in bounds if "Rozanov" in b.name]
    assert len(rozanov) == 1
    assert rozanov[0].status is BoundStatus.PUBLISHED
    assert "2*pi^2" in rozanov[0].form
    # The trap ADR-0047 says the implementation must carry forward.
    assert "VOLTAGE" in rozanov[0].caveat


def test_reflection_phase_and_steering_carry_gustafsson_sjoberg():
    for effect in ("reflected in phase", "steered"):
        bounds = physical_bound_for(effect)
        assert any("Gustafsson" in b.name for b in bounds), effect
        assert any("2.6" in b.form for b in bounds), effect


def test_the_gustafsson_sjoberg_registry_discrepancy_is_reported_not_hidden():
    """designs/design_families.py carries this bound as UnreadPhysicalBound
    while docs/absorber-thickness-bandwidth-bound.md quotes the paper's own
    equations verbatim. Both are recorded; neither is silently preferred."""
    (bound,) = [b for b in physical_bound_for("reflected in phase") if "Gustafsson" in b.name]
    assert "DISCREPANCY" in bound.registry_state
    assert "UnreadPhysicalBound" in bound.registry_state


def test_steering_bandwidth_extrapolation_is_flagged_as_inferred():
    (bound,) = [b for b in physical_bound_for("steered") if "Gustafsson" in b.name]
    assert "INFERRED" in bound.caveat


def test_polarisation_conversion_has_no_published_bandwidth_bound():
    """ADR-0047 point 3: "no bandwidth bound exists in the literature". That
    is a POSITIVE finding on the authors' own words, distinct from an
    unsearched gap."""
    bounds = physical_bound_for("polarisation-converted")
    bandwidth = [b for b in bounds if "BANDWIDTH" in b.mechanism]
    assert len(bandwidth) == 1
    assert bandwidth[0].status is BoundStatus.NONE_PUBLISHED
    assert "more work is needed" in bandwidth[0].citation

    # And the different bound that DOES exist, answering a different question.
    efficiency = [b for b in bounds if "EFFICIENCY" in b.mechanism]
    assert len(efficiency) == 1
    assert efficiency[0].status is BoundStatus.PUBLISHED
    assert "2208.05533" in efficiency[0].citation


def test_effects_with_no_researched_bound_say_not_established_not_none_published():
    """ "Nobody has looked" and "we looked and there is nothing" carry opposite
    instructions and must not collapse into one state."""
    for effect in ("transmitted", "shielded against", "low infrared emissivity"):
        bounds = physical_bound_for(effect)
        assert all(b.status is BoundStatus.NOT_ESTABLISHED for b in bounds), effect


def test_every_bound_entry_carries_a_citation_or_says_why_there_is_none():
    for name in known_effect_names():
        for bound in physical_bound_for(name):
            assert bound.citation.strip(), f"{name}: {bound.name} has no citation field"


# ---------------------------------------------------------------------------
# The diffusive exemption and its two preconditions
# ---------------------------------------------------------------------------


def test_backscatter_reduction_splits_three_ways_by_mechanism():
    """docs/absorber-thickness-bandwidth-bound.md section 7.3: by absorption
    Rozanov binds it; by phase cancellation Gustafsson & Sjoberg binds each
    tile; by diffusion no bound of that shape applies."""
    bounds = physical_bound_for("scattered diffusely")
    assert len(bounds) == 3
    statuses = {b.status for b in bounds}
    assert statuses == {
        BoundStatus.EXEMPT_BY_MECHANISM,
        BoundStatus.PUBLISHED,
    }
    assert sum(1 for b in bounds if b.status is BoundStatus.PUBLISHED) == 2
    assert any("Rozanov" in b.name for b in bounds)
    assert any("Gustafsson" in b.name for b in bounds)


def test_the_diffusive_exemption_carries_both_preconditions_as_checkable_data():
    (exemption,) = [
        b
        for b in physical_bound_for("scattered diffusely")
        if b.status is BoundStatus.EXEMPT_BY_MECHANISM
    ]
    keys = {p.key for p in exemption.preconditions}
    assert keys == {
        "redistributes_rather_than_dissipates",
        "period_launches_propagating_diffracted_orders",
    }

    by_key = {p.key: p for p in exemption.preconditions}

    # Precondition 1 is a statement about the MECHANISM that only the model
    # can make. Recording `check=None` says so out loud rather than pretending
    # a calculation can discharge it.
    mechanism = by_key["redistributes_rather_than_dissipates"]
    assert mechanism.check is None
    assert mechanism.why_it_matters

    # Precondition 2 IS arithmetic, and is wired to the function that does it.
    period = by_key["period_launches_propagating_diffracted_orders"]
    assert period.check is diffracted_order_min_period_m
    assert "42.4 mm at 10 GHz" in period.why_it_matters
    assert "30.3 mm at 14 GHz" in period.why_it_matters


def test_the_exemption_is_labelled_inferred_and_not_asserted_as_published():
    (exemption,) = [
        b
        for b in physical_bound_for("scattered diffusely")
        if b.status is BoundStatus.EXEMPT_BY_MECHANISM
    ]
    assert "INFERRED" in exemption.citation
    assert "needing confirmation" in exemption.citation
    assert "EXEMPTION, not a licence" in exemption.caveat


# ---------------------------------------------------------------------------
# sqrt(2)*lambda: the diagonal-order cutoff, verified
# ---------------------------------------------------------------------------


def test_checkerboard_diagonal_order_cutoff_is_42_4_mm_at_10_ghz():
    """A checkerboard cancels the specular (0,0) order by construction, so the
    first channels it can push power into are the DIAGONAL (+/-1,+/-1) ones,
    which propagate at normal incidence only for D >= sqrt(2)*lambda."""
    d = diffracted_order_min_period_m(10e9)
    assert round(d * 1000.0, 1) == 42.4


def test_checkerboard_diagonal_order_cutoff_is_30_3_mm_at_14_ghz():
    d = diffracted_order_min_period_m(14e9)
    assert round(d * 1000.0, 1) == 30.3


def test_the_cutoff_is_exactly_sqrt_two_lambda():
    for frequency_hz in (8.5e9, 10e9, 12e9, 14e9, 18e9):
        wavelength_m = 299_792_458.0 / frequency_hz
        assert diffracted_order_min_period_m(frequency_hz) == pytest.approx(
            math.sqrt(2.0) * wavelength_m
        )


def test_the_axial_order_cuts_off_at_one_wavelength_not_sqrt_two():
    """The (1,0) order propagates at D >= lambda. The checkerboard needs the
    harsher diagonal figure because its specular order is already cancelled --
    getting this wrong would under-size a supercell by 41 percent."""
    axial = diffracted_order_min_period_m(10e9, order=(1, 0))
    diagonal = diffracted_order_min_period_m(10e9, order=(1, 1))
    assert round(axial * 1000.0, 1) == 30.0
    assert diagonal / axial == pytest.approx(math.sqrt(2.0))


def test_the_cutoff_grows_as_frequency_falls_so_check_the_band_edge():
    assert diffracted_order_min_period_m(8e9) > diffracted_order_min_period_m(12e9)


@pytest.mark.parametrize("bad", [0.0, -1.0, float("nan"), float("inf"), "10e9", None, True])
def test_diffracted_order_min_period_rejects_a_nonsense_frequency(bad):
    with pytest.raises(ValueError):
        diffracted_order_min_period_m(bad)


def test_the_specular_order_has_no_cutoff():
    with pytest.raises(ValueError, match="specular"):
        diffracted_order_min_period_m(10e9, order=(0, 0))


# ---------------------------------------------------------------------------
# Default thresholds: a convention where one exists, explicitly none elsewhere
# ---------------------------------------------------------------------------


def test_absorbed_defaults_to_ninety_percent_as_a_reversible_one_pass_default():
    """ADR-0041 point 2. The reversibility rule lives in the DATA, not in a
    comment: -10 dB / 90 percent is a default when the customer is silent,
    never a hardcoded rule and never used to redefine the band's edges."""
    profile = resolve_intended_effect("absorbed")
    default = profile.default_threshold
    assert isinstance(default, DefaultThreshold)
    assert default.value == 0.90
    assert default.comparator == ">="
    assert "REVERSIBLE ONE-PASS DEFAULT" in default.rule
    assert "overrides it without argument" in default.rule
    assert "never be used to redefine the band" in default.rule
    assert "ADR-0041" in default.citation


def test_reflected_in_phase_defaults_to_the_forty_five_degree_amc_window():
    profile = resolve_intended_effect("reflected in phase")
    default = profile.default_threshold
    assert isinstance(default, DefaultThreshold)
    assert default.value == 45.0
    assert default.comparator == "<="
    assert "REVERSIBLE ONE-PASS DEFAULT" in default.rule


@pytest.mark.parametrize(
    "effect",
    [
        "steered",
        "transmitted",
        "scattered diffusely",
        "polarisation-converted",
        "shielded against",
        "low infrared emissivity",
    ],
)
def test_effects_with_no_convention_say_so_explicitly_with_a_reason(effect):
    """Explicitly NONE, with the reason recorded -- never a borrowed number
    from a different quantity on a different fixture."""
    default = resolve_intended_effect(effect).default_threshold
    assert not isinstance(default, DefaultThreshold)
    assert default.reason.strip()


def test_the_rcs_reduction_non_default_names_the_repo_rule_it_would_break():
    """docs/supercell-sizing-rule.md derives a supercell's phase budget FROM
    the requirement's own stated RCS-reduction target, so defaulting that
    number would feed an invented figure straight into a geometry decision."""
    default = resolve_intended_effect("scattered diffusely").default_threshold
    assert "supercell-sizing-rule" in default.reason


def test_the_radome_non_default_names_the_mil_spec_reason():
    """MIL-R-7705B carries one limit per requirement per product CLASS, so
    there is no class-free figure to default to."""
    default = resolve_intended_effect("transmitted").default_threshold
    assert "MIL-R-7705B" in default.reason


# ---------------------------------------------------------------------------
# Shape invariants
# ---------------------------------------------------------------------------


def test_every_profile_has_a_plain_language_gloss():
    """CLAUDE.md: the jargon is unavoidable in the work, not in the
    explanation of it."""
    for name in known_effect_names():
        profile = resolve_intended_effect(name)
        assert len(profile.gloss.split()) >= 8, name


def test_every_profile_states_a_fixture_and_a_scoring_quantity_note():
    for name in known_effect_names():
        profile = resolve_intended_effect(name)
        assert profile.fixtures, name
        assert profile.scoring_quantity_note.strip(), name


def test_every_effect_with_no_family_carries_a_family_gap_and_vice_versa():
    for name in known_effect_names():
        profile = resolve_intended_effect(name)
        assert profile.has_family == (profile.family_gap is None), name


def test_profiles_are_frozen_so_a_caller_cannot_edit_the_library_in_place():
    profile = resolve_intended_effect("absorbed")
    with pytest.raises(dataclasses.FrozenInstanceError):
        profile.objective_sense = ObjectiveSense.MINIMISE  # type: ignore[misc]


def test_the_library_holds_no_provenance_vocabulary_of_its_own():
    """This library holds facts about physics and about the repo's own
    registry -- never a fact about one requirement. An `intended_effect`'s
    provenance stays ASSUMED, owned by designs/requirement_targets.py, and
    nothing here may mint a rung of its own (ADR-0030)."""
    import designs.intended_effects as module

    assert not hasattr(module, "ASSUMED")
    for name in known_effect_names():
        profile = resolve_intended_effect(name)
        assert not hasattr(profile, "provenance")


def test_requirement_targets_does_not_import_this_library():
    """The ADR-0030 seam, asserted structurally.

    `propose_intended_effect` must keep accepting any non-empty string. If
    this library ever becomes an intake validator, the open vocabulary
    ADR-0030 decided on becomes a closed enum -- so the absence of that
    coupling is worth a test rather than a comment.
    """
    from pathlib import Path

    source = Path(__file__).resolve().parents[1] / "designs" / "requirement_targets.py"
    text = source.read_text(encoding="utf-8")
    assert "intended_effects" not in text
