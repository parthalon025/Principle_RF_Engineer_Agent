"""Tests for the unbacked, two-port absorber model (issue #242,
rf_tools/transmissive_absorber.py).

WHY THESE PARTICULAR ASSERTIONS. A closed-form model is easy to write and
easy to write WRONG in a way no single number reveals -- a flipped sign or a
missing sqrt(Z0*ZL) normalisation still returns something between 0 and 1.
So the oracles here are all things that are true independently of this
implementation:

  * A bare resistive sheet in free space has an ELEMENTARY closed form
    (Gamma = -eta0/(2Rs + eta0), Tau = 2Rs/(2Rs + eta0)) that can be written
    on one line without any matrix algebra. If the ABCD chain disagrees with
    it, the chain is wrong.
  * That same sheet has an EXACT maximum: absorption peaks at exactly 0.5
    when Rs = eta0/2 = 188.365 ohm/sq. Not an approximation -- a theorem. In
    plain terms: a single thin resistive film hanging in air can never eat
    more than half the power that hits it, no matter what you make it out of.
    docs/meep-absorber-validation.md case 1 confirms this against an FDTD
    solver that knows nothing about this code.
  * Driving the back of the stack toward a short circuit (load impedance ->
    0) turns the two-port structure into a ground-backed one, so this model
    must converge on `rf_tools.absorber.absorptivity` -- a completely
    separate implementation by a completely separate method, itself
    cross-validated against Meep (docs/meep-absorber-validation.md case 2).
    That convergence is the assertion that catches a sign or normalisation
    error NEITHER model would reveal alone, because the two would have to be
    wrong in exactly the same way to agree.
"""

import json
import math

import pytest

from designs.design_families import ABSORBER, ABSORBER_TRANSMISSIVE, PATCH
from rf_tools.absorber import absorptivity as ground_backed_absorptivity
from rf_tools.transmissive_absorber import (
    ETA0_OHM,
    MATCHED_SHEET_RESISTANCE_OHM_SQ,
    GroundBackedModelMisappliedError,
    cascade,
    dielectric_slab_abcd,
    refuse_ground_backed_model,
    s_parameters,
    shunt_sheet_abcd,
    stack_response,
    transmissive_absorber_band_response,
)

SPEED_OF_LIGHT_M_S = 299_792_458.0

# A bare sheet: no slab at all, free space on both sides. `gap_m=None` is the
# unpatterned branch (a continuous film has no gaps between elements, so no
# grid capacitance), and `squares=1.0` because a continuous sheet is one
# square by definition.
BARE_SHEET = {
    "eps_r": 1.0,
    "tan_delta": 0.0,
    "thickness_m": None,
    "period_m": 3.0e-3,
    "gap_m": None,
    "squares": 1.0,
}

# The Salisbury screen: a sheet matched to free space, held a quarter of a
# wavelength off whatever is behind it. Ground-backed this is the canonical
# perfect absorber; unbacked it is not, and the gap between those two numbers
# is the whole reason issue #242 exists.
SALISBURY_QUARTER_WAVE_M = SPEED_OF_LIGHT_M_S / 10e9 / 4
SALISBURY = {
    "eps_r": 1.0,
    "tan_delta": 0.0,
    "thickness_m": SALISBURY_QUARTER_WAVE_M,
    "period_m": 3.0e-3,
    "gap_m": None,
    "sheet_resistance_ohm_sq": ETA0_OHM,
    "squares": 1.0,
}


# ---------------------------------------------------------------------------
# 1. The bare-sheet ground-truth table.
#
# Computed independently of this implementation (issue #242's own derivation)
# and cross-checkable against docs/meep-absorber-validation.md's "A (exact)"
# column, which lists 0.4445 / 0.5000 / 0.4443 / 0.3199 for these same four
# sheet resistances.
# ---------------------------------------------------------------------------

BARE_SHEET_GROUND_TRUTH = [
    # Rs (ohm/sq),  |S11|,     |S21|,     A
    (94.2, 0.666626, 0.333374, 0.444472),
    (188.365, 0.500000, 0.500000, 0.500000),
    (377.0, 0.333174, 0.666826, 0.444338),
    (754.0, 0.199886, 0.800114, 0.319863),
]


@pytest.mark.parametrize(("rs", "s11", "s21", "absorption"), BARE_SHEET_GROUND_TRUTH)
def test_bare_sheet_matches_the_ground_truth_table(rs, s11, s21, absorption):
    """The four hand-computed rows, to six decimal places."""
    result = stack_response(10e9, sheet_resistance_ohm_sq=rs, **BARE_SHEET)
    assert abs(result["s11"]) == pytest.approx(s11, abs=5e-7)
    assert abs(result["s21"]) == pytest.approx(s21, abs=5e-7)
    assert result["absorption"] == pytest.approx(absorption, abs=5e-7)


@pytest.mark.parametrize("rs", [1.0, 10.0, 94.2, 188.365, 377.0, 754.0, 5000.0])
def test_bare_sheet_agrees_with_the_elementary_closed_form(rs):
    """The ABCD chain must reproduce the one-line answer for the one case
    where a one-line answer exists.

    A shunt resistance Rs across a line of impedance eta0, free space on both
    sides, gives Gamma = -eta0/(2Rs + eta0) and Tau = 2Rs/(2Rs + eta0)
    directly. No matrices, no cascade, no port normalisation -- so if the
    matrix machinery has a sign or sqrt(Z0*ZL) error, this is where it shows.
    """
    gamma = -ETA0_OHM / (2 * rs + ETA0_OHM)
    tau = 2 * rs / (2 * rs + ETA0_OHM)

    result = stack_response(10e9, sheet_resistance_ohm_sq=rs, **BARE_SHEET)

    assert result["s11"].real == pytest.approx(gamma, abs=1e-9)
    assert result["s11"].imag == pytest.approx(0.0, abs=1e-9)
    assert result["s21"].real == pytest.approx(tau, abs=1e-9)
    assert result["s21"].imag == pytest.approx(0.0, abs=1e-9)
    assert result["absorption"] == pytest.approx(1 - gamma**2 - tau**2, abs=1e-9)


def test_a_bare_sheet_in_free_space_can_never_absorb_more_than_half():
    """The exact ceiling, swept: no sheet resistance beats 0.5, and the
    maximum sits exactly at eta0/2.

    In plain terms -- a single thin resistive film hanging in air throws away
    at least half the power that hits it, whatever it is made of. A
    requirement above 50 % cannot be met by this shape at any sheet
    resistance; it needs a different structure, not a different ink.
    """
    assert MATCHED_SHEET_RESISTANCE_OHM_SQ == pytest.approx(188.365156706, abs=1e-6)

    best_rs, best_a = None, -1.0
    for i in range(1, 4001):
        rs = i * 0.5  # 0.5 .. 2000 ohm/sq
        a = stack_response(10e9, sheet_resistance_ohm_sq=rs, **BARE_SHEET)["absorption"]
        assert a <= 0.5 + 1e-12, f"Rs={rs} absorbed {a}, above the exact 0.5 ceiling"
        if a > best_a:
            best_rs, best_a = rs, a

    assert best_a == pytest.approx(0.5, abs=1e-6)
    assert best_rs == pytest.approx(MATCHED_SHEET_RESISTANCE_OHM_SQ, abs=0.5)


def test_a_bare_sheet_is_frequency_flat():
    """A zero-thickness resistor has no frequency dependence -- there is no
    length anywhere in the stack for a wavelength to compare itself against.
    A model that drifts with frequency here has smuggled in a phase term."""
    at_1_ghz = stack_response(1e9, sheet_resistance_ohm_sq=377.0, **BARE_SHEET)
    at_40_ghz = stack_response(40e9, sheet_resistance_ohm_sq=377.0, **BARE_SHEET)
    assert at_1_ghz["absorption"] == pytest.approx(at_40_ghz["absorption"], abs=1e-12)


# ---------------------------------------------------------------------------
# 2. Energy bookkeeping.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("rs", [10.0, 188.365, 377.0, 2000.0])
@pytest.mark.parametrize("thickness_m", [None, 0.5e-3, SALISBURY_QUARTER_WAVE_M])
def test_reflection_plus_transmission_plus_absorption_is_exactly_one(rs, thickness_m):
    """A = 1 - R - T is the definition, not a derived quantity
    (docs/absorber-scoring-conventions.md section 1). This asserts the model
    never loses or invents a watt."""
    result = stack_response(
        10e9,
        eps_r=2.9,
        tan_delta=0.01,
        thickness_m=thickness_m,
        period_m=3.0e-3,
        gap_m=None,
        sheet_resistance_ohm_sq=rs,
        squares=1.0,
    )
    total = result["reflection"] + result["transmission"] + result["absorption"]
    assert total == pytest.approx(1.0, abs=1e-12)
    assert 0.0 <= result["absorption"] <= 1.0


def test_a_lossless_stack_absorbs_nothing():
    """No resistance anywhere -- an enormous sheet resistance is effectively
    no sheet at all -- and a lossless slab. Every watt must either bounce or
    pass through. If this returns absorption, the model is manufacturing
    heat out of nothing."""
    result = stack_response(
        10e9,
        eps_r=2.9,
        tan_delta=0.0,
        thickness_m=1.0e-3,
        period_m=3.0e-3,
        gap_m=None,
        sheet_resistance_ohm_sq=1e12,
        squares=1.0,
    )
    assert result["absorption"] == pytest.approx(0.0, abs=1e-9)


# ---------------------------------------------------------------------------
# 3. The consistency check: two independent models must meet at the short.
# ---------------------------------------------------------------------------


def test_the_unbacked_and_ground_backed_answers_differ_by_the_amount_that_escapes():
    """The identical Salisbury stack scores 1.00 backed by metal and 0.44
    unbacked. That gap IS issue #242.

    The unbacked number, 4/9 = 0.4444, is not a small correction -- it says
    more than half the power the old sum credited as absorbed actually left
    out the back of the part.
    """
    unbacked = stack_response(10e9, **SALISBURY)["absorption"]
    backed = ground_backed_absorptivity(10e9, **SALISBURY)

    assert unbacked == pytest.approx(4 / 9, abs=1e-6)
    assert backed == pytest.approx(1.0, abs=1e-6)


@pytest.mark.parametrize("frequency_hz", [6e9, 8e9, 10e9, 12e9, 14e9])
@pytest.mark.parametrize(
    ("load_impedance_ohm", "tolerance"),
    [
        (ETA0_OHM / 10, 2e-1),
        (ETA0_OHM / 100, 2e-2),
        (ETA0_OHM / 1_000, 2e-3),
        (ETA0_OHM / 10_000, 2e-4),
        (ETA0_OHM / 1e9, 1e-8),
    ],
)
def test_two_port_model_converges_on_the_ground_backed_one_at_a_short(
    frequency_hz, load_impedance_ohm, tolerance
):
    """THE load-bearing test. Terminate the two-port stack in a short and it
    IS a ground-backed stack, so it must reproduce `rf_tools.absorber`'s
    answer -- an independent implementation by an independent method, itself
    agreeing with Meep FDTD to 0.001 across this exact band
    (docs/meep-absorber-validation.md case 2).

    Asserted across the WHOLE band, not only at the 10 GHz resonance where
    the answer is trivially 1.0. At 6 and 14 GHz the target is 0.8834 and at
    8 and 12 GHz it is 0.9743 -- the same numbers that document tabulates --
    so agreement here cannot be an accident of both models saturating.

    The tolerance tightens in step with the load impedance because the
    remaining disagreement is not error: it is the real power still being
    delivered into a finite load, which the two-port model correctly counts
    as transmitted rather than absorbed. It falls off linearly with the
    load, which is itself a check -- a sign error would not converge at all.
    """
    backed = ground_backed_absorptivity(frequency_hz, **SALISBURY)
    unbacked = stack_response(frequency_hz, load_impedance_ohm=load_impedance_ohm, **SALISBURY)[
        "absorption"
    ]
    assert unbacked == pytest.approx(backed, abs=tolerance)
    # One-sided: a finite load can only steal absorption, never add it.
    assert unbacked <= backed + 1e-9


def test_the_convergence_is_to_the_full_band_shape_not_just_the_peak():
    """The published closed-form column, reproduced from the other side.
    docs/meep-absorber-validation.md case 2 lists 0.8834 / 0.9391 / 0.9743 /
    0.9938 / 1.0000 at 6-10 GHz. A two-port stack shorted at the back must
    land on all five."""
    published = {
        6e9: 0.8834,
        7e9: 0.9391,
        8e9: 0.9743,
        9e9: 0.9938,
        10e9: 1.0000,
    }
    for frequency_hz, expected in published.items():
        got = stack_response(frequency_hz, load_impedance_ohm=ETA0_OHM / 1e9, **SALISBURY)[
            "absorption"
        ]
        assert got == pytest.approx(expected, abs=1e-4), f"at {frequency_hz / 1e9} GHz"


def test_reflection_only_reading_matches_the_tickets_stated_convergence_numbers():
    """Issue #242's brief quotes 0.997729 and 0.999975 for load impedances of
    37.7 and 3.77 ohm. Those are the REFLECTION-ONLY reading, 1 - R -- the
    one-port form the ground-backed model uses -- not this model's
    A = 1 - R - T, which is 0.906968 and 0.990067 at the same two loads.

    Both are recorded here because the difference is not a discrepancy in the
    physics but exactly the quantity this ticket exists to separate: at a
    37.7 ohm termination roughly 9 % of the power is still being delivered
    out the back, and 1 - R credits the stack for all of it while 1 - R - T
    does not. The two readings meet, as they must, only when the termination
    is a true short.
    """
    for load_impedance_ohm, reflection_only, two_port in (
        (37.7, 0.997729, 0.906968),
        (3.77, 0.999975, 0.990067),
    ):
        result = stack_response(10e9, load_impedance_ohm=load_impedance_ohm, **SALISBURY)
        assert 1.0 - result["reflection"] == pytest.approx(reflection_only, abs=5e-7)
        assert result["absorption"] == pytest.approx(two_port, abs=5e-7)


# ---------------------------------------------------------------------------
# 4. The ABCD primitives.
# ---------------------------------------------------------------------------


def test_a_zero_length_slab_is_the_identity_matrix():
    """Nothing between the ports is nothing. A slab matrix that is not the
    identity at zero thickness would silently bias every stack."""
    (a, b), (c, d) = dielectric_slab_abcd(10e9, eps_r=4.0, tan_delta=0.02, thickness_m=0.0)
    assert a == pytest.approx(1.0)
    assert abs(b) == pytest.approx(0.0, abs=1e-12)
    assert abs(c) == pytest.approx(0.0, abs=1e-12)
    assert d == pytest.approx(1.0)


def test_an_air_slab_of_any_thickness_is_invisible_between_free_space_ports():
    """Air matched to air reflects nothing, however thick. Only the phase
    moves, so |S21| must stay 1 and |S11| must stay 0."""
    s11, s21 = s_parameters(
        dielectric_slab_abcd(10e9, eps_r=1.0, tan_delta=0.0, thickness_m=17.3e-3),
        ETA0_OHM,
        ETA0_OHM,
    )
    assert abs(s11) == pytest.approx(0.0, abs=1e-9)
    assert abs(s21) == pytest.approx(1.0, abs=1e-9)


def test_a_half_wave_slab_is_transparent_whatever_its_permittivity():
    """The half-wave window: a slab exactly half a wavelength thick IN THE
    MATERIAL transforms its load to itself, so a lossless slab of any eps_r
    vanishes. A textbook result this model has no excuse to miss."""
    f, eps_r = 10e9, 6.25
    half_wave_m = SPEED_OF_LIGHT_M_S / (f * math.sqrt(eps_r)) / 2
    s11, s21 = s_parameters(
        dielectric_slab_abcd(f, eps_r=eps_r, tan_delta=0.0, thickness_m=half_wave_m),
        ETA0_OHM,
        ETA0_OHM,
    )
    assert abs(s11) == pytest.approx(0.0, abs=1e-6)
    assert abs(s21) == pytest.approx(1.0, abs=1e-6)


def test_a_perfectly_conducting_shunt_sheet_is_a_mirror():
    """Infinite admittance short-circuits the line: everything comes back,
    nothing gets through, nothing is absorbed. Metal, in other words."""
    s11, s21 = s_parameters(shunt_sheet_abcd(1e12), ETA0_OHM, ETA0_OHM)
    assert abs(s11) == pytest.approx(1.0, abs=1e-6)
    assert abs(s21) == pytest.approx(0.0, abs=1e-6)


def test_cascade_of_nothing_is_the_identity_and_order_is_preserved():
    """Matrix multiplication does not commute, and neither does a stack: a
    sheet in front of a slab is a different part from a slab in front of a
    sheet."""
    sheet = shunt_sheet_abcd(1 / 377.0)
    slab = dielectric_slab_abcd(10e9, eps_r=4.0, tan_delta=0.0, thickness_m=1e-3)
    assert cascade() == ((1, 0), (0, 1))
    assert cascade(sheet) == sheet
    assert cascade(sheet, slab) != cascade(slab, sheet)


# ---------------------------------------------------------------------------
# 5. The band response: minimax scoring, provenance, validity, bound.
# ---------------------------------------------------------------------------


BAND = {"f_low_hz": 8e9, "f_high_hz": 12e9}

# A plausible printed X-band stack, the same one tests/test_absorber.py uses:
# silicone spacer, 3 mm cell, 0.2 mm gap. Unlike the Salisbury screen above it
# is genuinely dispersive across the band -- the gap capacitance between
# neighbouring printed elements gives it a resonance -- which is what a
# worst-in-band rule needs in order to have a worst in band at all.
PRINTED_STACK = {
    "eps_r": 2.9,
    "tan_delta": 0.10,
    "thickness_m": 2.0e-3,
    "period_m": 3.0e-3,
    "gap_m": 0.2e-3,
    "sheet_resistance_ohm_sq": 500.0,
    "squares": 0.1,
}


def test_band_response_scores_the_single_worst_frequency_not_the_mean_or_peak():
    """#110's minimax rule, the same one `absorber_band_response` follows: a
    customer asking for 90 % across a band is asking for 90 % at every
    frequency in it, and a mean lets one lucky peak hide a design that fails
    everywhere else."""
    result = transmissive_absorber_band_response(**BAND, **PRINTED_STACK, points=41)

    absorptions = [point["absorption"] for point in result["curve"]]
    assert result["worst_absorption"] == pytest.approx(min(absorptions))
    assert result["best_absorption"] == pytest.approx(max(absorptions))
    assert result["worst_absorption"] < result["best_absorption"]
    mean = sum(absorptions) / len(absorptions)
    assert result["worst_absorption"] < mean
    assert 8e9 <= result["worst_frequency_hz"] <= 12e9


def test_band_response_carries_calculated_provenance():
    result = transmissive_absorber_band_response(**BAND, **PRINTED_STACK)
    assert result["provenance"] == "CALCULATED"
    assert result["function"] == "transmissive_absorber_band_response"


def test_band_response_reports_reflection_and_transmission_not_just_absorption():
    """The reader is making a decision. "44 % absorbed" and "44 % absorbed,
    44 % straight through the part" are different decisions."""
    result = transmissive_absorber_band_response(**BAND, **PRINTED_STACK)
    worst = min(result["curve"], key=lambda p: p["absorption"])
    assert set(worst) >= {"frequency_hz", "reflection", "transmission", "absorption"}
    assert result["transmission_at_worst"] == pytest.approx(worst["transmission"])
    assert result["reflection_at_worst"] == pytest.approx(worst["reflection"])


def test_band_response_reports_the_physical_bound_as_unread_never_absent():
    """Absence of a citation is not evidence that no bound exists
    (designs/design_families.py's own reasoning). The output must say "we
    have not read one", which is a different claim from "there isn't one" --
    and a different claim again from ABSORBER's "here is the number"."""
    result = transmissive_absorber_band_response(**BAND, **SALISBURY)
    bound = result["physical_bound"]
    assert bound["status"] == "unread_primary_source"
    assert bound["applies"] is False
    assert "not" in bound["why_no_number"].lower()


def test_the_output_never_mentions_rozanov():
    """Rozanov's derivation opens by fixing a slab over a perfectly
    reflecting plane. This family has no such plane, so the bound does not
    apply -- and the failure mode issue #216 recorded is that somebody greps
    a transmissive result, finds the familiar name beside it, and reapplies
    it. The name is therefore kept out of this model's output entirely,
    including out of any explanation of why it does not apply. That
    explanation belongs in the family registry and in
    docs/absorber-scoring-conventions.md, where it is attached to the
    comparison rather than to a number.
    """
    result = transmissive_absorber_band_response(**BAND, **SALISBURY)
    serialised = json.dumps(result, default=str).lower()
    assert "rozanov" not in serialised
    assert "rozanov_min_thickness_m" not in result


def test_every_validity_entry_carries_the_charters_three_parts():
    """CLAUDE.md: a warning must say what is assumed, what it costs if that
    is wrong, and the cheapest way to find out. An entry missing any of the
    three is not a warning, it is a noise."""
    result = transmissive_absorber_band_response(
        f_low_hz=8e9, f_high_hz=80e9, **PRINTED_STACK, load_impedance_ohm=1.0
    )
    assert result["validity"], "this stack should trip at least one warning"
    for entry in result["validity"]:
        assert set(entry) == {"flag", "assumed", "costs", "cheapest_test"}
        assert all(isinstance(v, str) and v.strip() for v in entry.values())


def test_a_bare_sheet_is_warned_about_its_own_half_power_ceiling():
    """The one warning that changes a decision outright: no amount of
    tuning gets this shape past 50 %."""
    result = transmissive_absorber_band_response(
        **BAND, sheet_resistance_ohm_sq=188.365, **BARE_SHEET
    )
    flags = {entry["flag"] for entry in result["validity"]}
    assert "single_sheet_half_power_ceiling" in flags
    assert result["best_absorption"] <= 0.5 + 1e-9


def test_a_thick_salisbury_stack_is_not_warned_about_the_half_power_ceiling():
    """The counterpart, and the reason the warning is worth having: a
    quarter-wave stack is a different structure and the ceiling does not
    bind it. A flag that fires on everything says nothing."""
    result = transmissive_absorber_band_response(**BAND, **SALISBURY)
    flags = {entry["flag"] for entry in result["validity"]}
    assert "single_sheet_half_power_ceiling" not in flags


def test_a_diagnostic_load_impedance_is_flagged_as_not_the_families_answer():
    """`load_impedance_ohm` exists for the ground-backed cross-check, not as
    a second public model. Any value other than free space must say so in the
    output, so a shorted run can never be mistaken for a candidate's score."""
    result = transmissive_absorber_band_response(
        **BAND, **SALISBURY, load_impedance_ohm=ETA0_OHM / 1e6
    )
    flags = {entry["flag"] for entry in result["validity"]}
    assert "load_impedance_is_not_free_space" in flags

    at_free_space = transmissive_absorber_band_response(**BAND, **SALISBURY)
    assert "load_impedance_is_not_free_space" not in {
        entry["flag"] for entry in at_free_space["validity"]
    }


def test_a_patterned_sheet_is_flagged_for_the_unvalidated_grid_capacitance():
    """docs/meep-absorber-validation.md's own "what this does not establish":
    both validated cases are UNIFORM sheets, and the grid capacitance those
    cases deliberately switch off is exactly what a patterned cell relies on.
    """
    patterned = transmissive_absorber_band_response(**BAND, **PRINTED_STACK)
    uniform = transmissive_absorber_band_response(**BAND, **SALISBURY)
    assert "grid_capacitance_unvalidated" in {e["flag"] for e in patterned["validity"]}
    assert "grid_capacitance_unvalidated" not in {e["flag"] for e in uniform["validity"]}


def test_band_response_rejects_an_inverted_or_degenerate_band():
    with pytest.raises(ValueError, match="f_high_hz"):
        transmissive_absorber_band_response(f_low_hz=12e9, f_high_hz=8e9, **SALISBURY)
    with pytest.raises(ValueError, match="points"):
        transmissive_absorber_band_response(**BAND, **SALISBURY, points=1)


# ---------------------------------------------------------------------------
# 6. The guard: the ground-backed model must refuse a transmissive stack.
# ---------------------------------------------------------------------------


def test_the_ground_backed_model_refuses_a_transmissive_family():
    """The failure this guards against is silent, which is why it must
    raise: `rf_tools.absorber` would happily return 1.00 for a stack that
    lets 44 % of the power straight through, and nothing in the number says
    so."""
    with pytest.raises(GroundBackedModelMisappliedError, match="ABSORBER_TRANSMISSIVE"):
        refuse_ground_backed_model(ABSORBER_TRANSMISSIVE)


def test_the_guard_passes_a_genuinely_ground_backed_family():
    assert refuse_ground_backed_model(ABSORBER) is None
    assert refuse_ground_backed_model(PATCH) is None


def test_the_guards_message_names_the_model_to_use_instead():
    """A refusal that does not say what to do instead is a dead end."""
    with pytest.raises(GroundBackedModelMisappliedError) as excinfo:
        refuse_ground_backed_model(ABSORBER_TRANSMISSIVE)
    message = str(excinfo.value)
    assert "transmissive_absorber_band_response" in message
    assert "#242" in message or "#216" in message


def test_the_guard_reads_the_declared_ports_not_the_family_name():
    """Duck-typed on purpose: the guard asks what the family DECLARES, so a
    family added later is covered without editing this function."""

    class _Fake:
        name = "SOMETHING_NEW"
        requires_ground_plane = False
        port_count = 2

    with pytest.raises(GroundBackedModelMisappliedError, match="SOMETHING_NEW"):
        refuse_ground_backed_model(_Fake())
