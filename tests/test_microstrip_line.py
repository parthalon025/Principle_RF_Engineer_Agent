"""Microstrip transmission-line synthesis (issue #286).

microstrip_effective_permittivity is the identical Hammerstad fringing-field
fit patch_effective_permittivity (rf_tools/patch_synthesis.py's-to-be, still
rf_tools/calculations.py for now) already checks, restated with no
W/h > 1 floor (Pozar's general line treatment, not Balanis's patch one --
see the module note in rf_tools/microstrip_line.py). The impedance formulas
are independently re-typed from Pozar's Table 3.2 here, not re-derived from
this implementation, matching this file's own convention elsewhere
(test_patch_resonant_frequency_matches_hand_calculation, etc.).
"""

import math

import pytest

from rf_tools.calculations import patch_effective_permittivity
from rf_tools.microstrip_line import (
    microstrip_characteristic_impedance_ohm,
    microstrip_effective_permittivity,
    microstrip_synthesize_width_m,
)


def test_microstrip_effective_permittivity_matches_the_patch_formula():
    """Same closed form as patch_effective_permittivity -- same number for
    the same (eps_r, w, h), for any input the patch formula also accepts."""
    eps_r, w_m, h_m = 4.4, 0.030, 0.0016
    assert microstrip_effective_permittivity(eps_r, w_m, h_m) == pytest.approx(
        patch_effective_permittivity(eps_r, w_m, h_m)
    )


def test_microstrip_effective_permittivity_allows_narrow_lines():
    """Unlike patch_effective_permittivity, W/h < 1 is squarely in scope --
    a narrow, high-impedance stepped-impedance line section is exactly
    W/h < 1 (see test_microstrip_synthesize_width_uses_the_correct_branch)."""
    eps_r, w_m, h_m = 4.4, 0.0005, 0.0016  # W/h = 0.3125
    expected = (eps_r + 1) / 2 + (eps_r - 1) / 2 * (1 + 12 * h_m / w_m) ** -0.5
    assert microstrip_effective_permittivity(eps_r, w_m, h_m) == pytest.approx(expected)
    with pytest.raises(ValueError):
        patch_effective_permittivity(eps_r, w_m, h_m)  # confirms this case is patch-invalid


def test_microstrip_effective_permittivity_invalid_inputs_raise():
    with pytest.raises(ValueError):
        microstrip_effective_permittivity(1.0, 0.001, 0.0016)
    with pytest.raises(ValueError):
        microstrip_effective_permittivity(4.4, -0.001, 0.0016)
    with pytest.raises(ValueError):
        microstrip_effective_permittivity(4.4, 0.001, 0.0)


def test_microstrip_characteristic_impedance_matches_hand_calculation_narrow_line():
    """W/h < 1 branch (Pozar Table 3.2)."""
    eps_r, w_m, h_m = 4.4, 0.0007, 0.0016  # W/h = 0.4375
    eps_eff = microstrip_effective_permittivity(eps_r, w_m, h_m)
    w_over_h = w_m / h_m
    expected = (60.0 / eps_eff**0.5) * math.log(8.0 / w_over_h + w_over_h / 4.0)
    assert microstrip_characteristic_impedance_ohm(eps_r, w_m, h_m) == pytest.approx(expected)


def test_microstrip_characteristic_impedance_matches_hand_calculation_wide_line():
    """W/h > 1 branch (Pozar Table 3.2)."""
    eps_r, w_m, h_m = 4.4, 0.011, 0.0016  # W/h = 6.875
    eps_eff = microstrip_effective_permittivity(eps_r, w_m, h_m)
    w_over_h = w_m / h_m
    expected = (120.0 * math.pi / eps_eff**0.5) / (
        w_over_h + 1.393 + 0.667 * math.log(w_over_h + 1.444)
    )
    assert microstrip_characteristic_impedance_ohm(eps_r, w_m, h_m) == pytest.approx(expected)


def test_microstrip_characteristic_impedance_invalid_inputs_raise():
    with pytest.raises(ValueError):
        microstrip_characteristic_impedance_ohm(1.0, 0.001, 0.0016)
    with pytest.raises(ValueError):
        microstrip_characteristic_impedance_ohm(4.4, -0.001, 0.0016)
    with pytest.raises(ValueError):
        microstrip_characteristic_impedance_ohm(4.4, 0.001, 0.0)


def test_microstrip_synthesize_width_matches_the_classic_50_ohm_fr4_result():
    """A widely repeated rule-of-thumb figure in microstrip references: a 50
    ohm line on 1.6 mm FR4 (eps_r ~ 4.4) comes out to roughly 3 mm wide."""
    width_m = microstrip_synthesize_width_m(50.0, 4.4, 0.0016)
    assert width_m == pytest.approx(0.003, rel=0.05)


@pytest.mark.parametrize("z0_ohm", [20.0, 24.0, 50.0, 100.0, 120.0])
def test_microstrip_synthesize_width_round_trips_through_characteristic_impedance(z0_ohm):
    """The textbook check for this approximate synthesis pair: solving for a
    width from a target Z0 and analyzing that width back recovers the
    target to within Pozar's own stated accuracy (about 1%)."""
    eps_r, h_m = 4.4, 0.0016
    width_m = microstrip_synthesize_width_m(z0_ohm, eps_r, h_m)
    recovered = microstrip_characteristic_impedance_ohm(eps_r, width_m, h_m)
    assert recovered == pytest.approx(z0_ohm, rel=0.015)


def test_microstrip_synthesize_width_uses_the_correct_branch_for_narrow_and_wide_lines():
    """A high target impedance synthesizes a narrow (W/h < 1) line and a low
    target impedance a wide (W/h > 1) one -- the two regimes the
    stepped-impedance Hi-Z/Lo-Z method actually needs on opposite sides."""
    eps_r, h_m = 4.4, 0.0016
    narrow = microstrip_synthesize_width_m(120.0, eps_r, h_m)
    wide = microstrip_synthesize_width_m(20.0, eps_r, h_m)
    assert narrow / h_m < 1.0
    assert wide / h_m > 2.0


def test_microstrip_synthesize_width_invalid_inputs_raise():
    with pytest.raises(ValueError):
        microstrip_synthesize_width_m(0.0, 4.4, 0.0016)
    with pytest.raises(ValueError):
        microstrip_synthesize_width_m(50.0, 1.0, 0.0016)
    with pytest.raises(ValueError):
        microstrip_synthesize_width_m(50.0, 4.4, 0.0)
