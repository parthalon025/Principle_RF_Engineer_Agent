import math
from math import sin

import pytest

from rf_tools.calculations import (
    aperture_gain,
    curvature_exceeds_validity_box,
    curvature_length_correction_factor,
    curvature_shifted_resonant_frequency_hz,
    fractional_bandwidth_from_q,
    maxwell_garnett_effective_permeability,
    patch_effective_permittivity,
    patch_length_extension_m,
    patch_resonant_frequency_hz,
    quality_factor_from_fractional_bandwidth,
    wavelength,
)


def test_wavelength():
    assert wavelength(299_792_458.0) == pytest.approx(1.0)


# --- Conformal antenna: resonant frequency and bandwidth (issue #27) ---
#
# patch_effective_permittivity / patch_length_extension_m /
# patch_resonant_frequency_hz implement the standard microstrip patch
# transmission-line model (Balanis, "Antenna Theory: Analysis and Design").
# Following this module's established convention (see e.g. test_friis,
# test_cascade_output_ip3_two_stage, the Rollett-K-factor tests above) of
# independently evaluating the same published formula inside the test, each
# reference value below is computed directly from the formulas as stated
# in Balanis, using physically-reasonable substrate/geometry inputs (an
# FR4-like substrate, eps_r=4.4, h=1.6 mm, comparable to a common low-cost
# 2.4 GHz patch build) rather than a memorized textbook worked example.


def test_patch_effective_permittivity_matches_transmission_line_formula():
    eps_r, w_m, h_m = 4.4, 0.030, 0.0016
    expected = (eps_r + 1) / 2 + (eps_r - 1) / 2 * (1 + 12 * h_m / w_m) ** -0.5
    assert patch_effective_permittivity(eps_r, w_m, h_m) == pytest.approx(expected)
    # Sanity bound intrinsic to the formula: eps_eff always sits strictly
    # between 1 (air) and eps_r (fully in the dielectric).
    assert 1.0 < patch_effective_permittivity(eps_r, w_m, h_m) < eps_r


def test_patch_effective_permittivity_invalid_inputs_raise():
    with pytest.raises(ValueError):
        patch_effective_permittivity(1.0, 0.030, 0.0016)
    with pytest.raises(ValueError):
        patch_effective_permittivity(4.4, -0.030, 0.0016)
    with pytest.raises(ValueError):
        patch_effective_permittivity(4.4, 0.030, 0.0)
    with pytest.raises(ValueError):
        patch_effective_permittivity(4.4, 0.001, 0.0016)  # W/h <= 1


def test_patch_length_extension_matches_fringing_formula():
    eps_r, w_m, h_m = 4.4, 0.030, 0.0016
    eps_eff = patch_effective_permittivity(eps_r, w_m, h_m)
    w_over_h = w_m / h_m
    expected = (
        0.412 * h_m * (eps_eff + 0.3) * (w_over_h + 0.264) / ((eps_eff - 0.258) * (w_over_h + 0.8))
    )
    assert patch_length_extension_m(eps_eff, w_m, h_m) == pytest.approx(expected)
    assert patch_length_extension_m(eps_eff, w_m, h_m) > 0


def test_patch_length_extension_invalid_inputs_raise():
    with pytest.raises(ValueError):
        patch_length_extension_m(0.2, 0.030, 0.0016)
    with pytest.raises(ValueError):
        patch_length_extension_m(2.0, -0.030, 0.0016)
    with pytest.raises(ValueError):
        patch_length_extension_m(2.0, 0.030, 0.0)


def test_patch_resonant_frequency_matches_hand_calculation():
    eps_r, w_m, h_m, l_m = 4.4, 0.030, 0.0016, 0.0286
    c = 299_792_458.0

    eps_eff = (eps_r + 1) / 2 + (eps_r - 1) / 2 * (1 + 12 * h_m / w_m) ** -0.5
    w_over_h = w_m / h_m
    dl = 0.412 * h_m * (eps_eff + 0.3) * (w_over_h + 0.264) / ((eps_eff - 0.258) * (w_over_h + 0.8))
    l_eff = l_m + 2 * dl
    expected_f_r = c / (2 * l_eff * eps_eff**0.5)

    result = patch_resonant_frequency_hz(eps_r, w_m, h_m, l_m)
    assert result == pytest.approx(expected_f_r)
    # This build is sized in the right ballpark for a 2.4 GHz ISM patch
    # (sanity check on the worked example, not a formula assertion).
    assert 2.0e9 < result < 3.0e9


def test_patch_resonant_frequency_increases_as_length_decreases():
    # f_r ~ 1/L_eff: shortening the patch (all else equal) must raise f_r.
    eps_r, w_m, h_m = 4.4, 0.030, 0.0016
    f_long = patch_resonant_frequency_hz(eps_r, w_m, h_m, l_m=0.0300)
    f_short = patch_resonant_frequency_hz(eps_r, w_m, h_m, l_m=0.0250)
    assert f_short > f_long


def test_patch_resonant_frequency_invalid_inputs_raise():
    with pytest.raises(ValueError):
        patch_resonant_frequency_hz(4.4, 0.030, 0.0016, l_m=0.0)
    with pytest.raises(ValueError):
        patch_resonant_frequency_hz(4.4, 0.030, 0.0016, l_m=-0.02)
    with pytest.raises(ValueError):
        patch_resonant_frequency_hz(4.4, 0.030, 0.0016, l_m=0.02, c_m_s=0.0)


# --- Microstrip transmission-line synthesis moved to tests/test_microstrip_line.py ---
#
# microstrip_effective_permittivity, microstrip_characteristic_impedance_ohm,
# and microstrip_synthesize_width_m (issue #286) now live in
# rf_tools/microstrip_line.py, with their tests alongside in
# tests/test_microstrip_line.py.


# --- Fractional bandwidth <-> Q ---
#
# fractional_bandwidth_from_q / quality_factor_from_fractional_bandwidth use
# the standard VSWR-dependent antenna bandwidth relation
# FBW = (VSWR-1)/(Q*sqrt(VSWR)) (see module docstring in rf_tools/calculations.py
# for the source and why this form was chosen over the simpler FBW=1/Q).


def test_fractional_bandwidth_from_q_matches_formula():
    q, vswr = 50.0, 2.0
    expected = (vswr - 1) / (q * vswr**0.5)
    assert fractional_bandwidth_from_q(q, vswr) == pytest.approx(expected)


def test_fractional_bandwidth_from_q_default_vswr_is_two():
    q = 80.0
    assert fractional_bandwidth_from_q(q) == pytest.approx(fractional_bandwidth_from_q(q, 2.0))


def test_quality_factor_from_fractional_bandwidth_matches_formula():
    fbw, vswr = 0.02, 1.5
    expected = (vswr - 1) / (fbw * vswr**0.5)
    assert quality_factor_from_fractional_bandwidth(fbw, vswr) == pytest.approx(expected)


def test_fractional_bandwidth_and_q_round_trip():
    q = 65.0
    vswr = 1.8
    fbw = fractional_bandwidth_from_q(q, vswr)
    assert quality_factor_from_fractional_bandwidth(fbw, vswr) == pytest.approx(q)


def test_fractional_bandwidth_from_q_invalid_inputs_raise():
    with pytest.raises(ValueError):
        fractional_bandwidth_from_q(0.0)
    with pytest.raises(ValueError):
        fractional_bandwidth_from_q(-10.0)
    with pytest.raises(ValueError):
        fractional_bandwidth_from_q(50.0, vswr=1.0)
    with pytest.raises(ValueError):
        fractional_bandwidth_from_q(50.0, vswr=0.5)


def test_quality_factor_from_fractional_bandwidth_invalid_inputs_raise():
    with pytest.raises(ValueError):
        quality_factor_from_fractional_bandwidth(0.0)
    with pytest.raises(ValueError):
        quality_factor_from_fractional_bandwidth(-0.01)
    with pytest.raises(ValueError):
        quality_factor_from_fractional_bandwidth(0.02, vswr=1.0)


# --- Curvature-induced resonant-frequency shift ---
#
# curvature_length_correction_factor / curvature_shifted_resonant_frequency_hz
# implement the first-order geometric proxy model documented in
# rf_tools/calculations.py (NOT a settled textbook-precise formula -- see
# that module's "APPROXIMATION NOTICE" for the honest caveat and citation).
# Reference values below are the exact circular-arc chord-length geometry
# (chord = 2*R*sin(L/(2R))) the model is built from, computed independently
# in the test.


def test_curvature_length_correction_factor_matches_chord_geometry():
    l_m, r_m = 0.02, 0.10  # L/R = 0.2, within the documented L/R < 0.5 validity range
    half_angle = l_m / (2 * r_m)
    chord = 2 * r_m * sin(half_angle)
    expected = l_m / chord
    assert curvature_length_correction_factor(l_m, r_m) == pytest.approx(expected)
    # Curvature always shortens the chord relative to the arc, so the
    # correction factor is always >= 1.
    assert curvature_length_correction_factor(l_m, r_m) >= 1.0


def test_curvature_length_correction_factor_approaches_one_for_large_radius():
    # As R -> infinity (host surface approaches flat), the curvature
    # correction must vanish -- this is the model's flat-design limit.
    l_m = 0.02
    factor = curvature_length_correction_factor(l_m, radius_of_curvature_m=1_000.0)
    assert factor == pytest.approx(1.0, abs=1e-6)


def test_curvature_length_correction_factor_grows_with_curvature():
    # Tighter curvature (smaller R, same L) must produce a larger (or
    # equal) correction -- monotonicity intrinsic to the chord/arc model.
    l_m = 0.02
    factor_mild = curvature_length_correction_factor(l_m, radius_of_curvature_m=0.5)
    factor_tight = curvature_length_correction_factor(l_m, radius_of_curvature_m=0.08)
    assert factor_tight > factor_mild > 1.0


def test_curvature_length_correction_factor_invalid_inputs_raise():
    with pytest.raises(ValueError):
        curvature_length_correction_factor(0.0, 0.10)
    with pytest.raises(ValueError):
        curvature_length_correction_factor(-0.02, 0.10)
    with pytest.raises(ValueError):
        curvature_length_correction_factor(0.02, 0.0)
    with pytest.raises(ValueError):
        curvature_length_correction_factor(0.02, -0.10)


def test_curvature_length_correction_factor_outside_validity_range_raises():
    # L/R = 0.5 sits exactly on the documented validity boundary (L/R < 0.5).
    with pytest.raises(ValueError):
        curvature_length_correction_factor(0.05, 0.10)
    with pytest.raises(ValueError):
        curvature_length_correction_factor(0.08, 0.10)  # L/R = 0.8, well outside


def test_curvature_shifted_resonant_frequency_matches_factor():
    f_flat_hz, l_m, r_m = 2.4e9, 0.02, 0.10
    factor = curvature_length_correction_factor(l_m, r_m)
    result = curvature_shifted_resonant_frequency_hz(f_flat_hz, l_m, r_m)
    assert result == pytest.approx(f_flat_hz * factor)
    # The model always predicts a shift upward from the flat design (see
    # module docstring for the honest caveat on direction/magnitude).
    assert result > f_flat_hz


# --- curvature_exceeds_validity_box: S <= 2*theta_max*R (issue #322) ---
#
# docs/curvature-effects-on-em-surfaces.md section 4.2's worked table:
# an angle-stable element (theta_max = 60 degrees) on a 100 mm host radius
# tolerates a 209 mm usable arc; a mushroom-type element (theta_max = 30
# degrees) on the same host tolerates only 105 mm.


def test_curvature_exceeds_validity_box_matches_worked_khan_example():
    # Khan et al.'s own worked result: a central angle of 90 degrees (full
    # arc S = 2*R for that angle) is exactly the bound for an element
    # stable to 45 degrees -- S == 2*theta_max*R sits ON the bound, not
    # past it, so this is NOT a violation.
    theta_max_deg = 45.0
    host_radius_m = 0.1
    bound_m = 2 * math.radians(theta_max_deg) * host_radius_m
    assert curvature_exceeds_validity_box(bound_m, host_radius_m, theta_max_deg) is False
    assert curvature_exceeds_validity_box(bound_m + 1e-6, host_radius_m, theta_max_deg) is True


def test_curvature_exceeds_validity_box_angle_stable_vs_mushroom_element():
    # docs/curvature-effects-on-em-surfaces.md's own worked table, R = 100 mm.
    host_radius_m = 0.100
    angle_stable_bound_m = 0.209  # theta_max = 60 degrees
    mushroom_bound_m = 0.105  # theta_max = 30 degrees
    arc_length_m = 0.15  # inside the angle-stable element's budget, past the mushroom's
    assert curvature_exceeds_validity_box(arc_length_m, host_radius_m, 60.0) is False
    assert curvature_exceeds_validity_box(arc_length_m, host_radius_m, 30.0) is True
    assert angle_stable_bound_m > arc_length_m > mushroom_bound_m  # sanity on the fixture


def test_curvature_exceeds_validity_box_invalid_inputs_raise():
    with pytest.raises(ValueError):
        curvature_exceeds_validity_box(0.0, 0.10, 45.0)
    with pytest.raises(ValueError):
        curvature_exceeds_validity_box(-0.1, 0.10, 45.0)
    with pytest.raises(ValueError):
        curvature_exceeds_validity_box(0.1, 0.0, 45.0)
    with pytest.raises(ValueError):
        curvature_exceeds_validity_box(0.1, -0.10, 45.0)
    with pytest.raises(ValueError):
        curvature_exceeds_validity_box(0.1, 0.10, 0.0)
    with pytest.raises(ValueError):
        curvature_exceeds_validity_box(0.1, 0.10, 91.0)


def test_curvature_shifted_resonant_frequency_invalid_f_flat_raises():
    with pytest.raises(ValueError):
        curvature_shifted_resonant_frequency_hz(0.0, 0.02, 0.10)
    with pytest.raises(ValueError):
        curvature_shifted_resonant_frequency_hz(-2.4e9, 0.02, 0.10)


def test_curvature_shifted_resonant_frequency_end_to_end_with_patch_formula():
    # Full pipeline: size a flat patch, then estimate its curved-mount shift.
    eps_r, w_m, h_m, l_m = 4.4, 0.030, 0.0016, 0.0286
    f_flat = patch_resonant_frequency_hz(eps_r, w_m, h_m, l_m)
    r_m = 0.15  # L/R ~ 0.19, within validity range
    f_curved = curvature_shifted_resonant_frequency_hz(f_flat, l_m, r_m)
    assert f_curved == pytest.approx(f_flat * curvature_length_correction_factor(l_m, r_m))
    assert f_curved > f_flat


# --- Metamaterial unit-cell effective medium (Maxwell-Garnett) ---
#
# Reference: Maxwell Garnett, 1904 mixing formula, as used throughout the
# metamaterial/effective-medium homogenization literature:
#
#     (mu_eff - mu_host) / (mu_eff + 2*mu_host)
#         = f * (mu_r - mu_host) / (mu_r + 2*mu_host)
#
# The f=0 limiting case (mu_eff == mu_host exactly, for any mu_r) is
# analytically exact and independent of any implementation detail -- it
# follows directly from the mixing formula above (LHS must be zero when
# f=0, and mu_eff=mu_host is the unique real solution). The mid-range
# fill-fraction case below is independently hand-derived from that same
# published mixing formula (no memorized textbook worked example is
# available with high confidence for this specific f/mu_r pair).


def test_maxwell_garnett_effective_permeability_zero_fill_fraction_is_host_exactly():
    assert maxwell_garnett_effective_permeability(0.0, mu_r=25.0, mu_host=1.0) == pytest.approx(1.0)
    assert maxwell_garnett_effective_permeability(0.0, mu_r=3.0, mu_host=2.5) == pytest.approx(2.5)


def test_maxwell_garnett_effective_permeability_default_host_is_free_space():
    with_default = maxwell_garnett_effective_permeability(0.1, mu_r=5.0)
    with_explicit = maxwell_garnett_effective_permeability(0.1, mu_r=5.0, mu_host=1.0)
    assert with_default == pytest.approx(with_explicit)


def test_maxwell_garnett_effective_permeability_matches_hand_derived_mid_range_value():
    # f=0.1, mu_r=5.0, mu_host=1.0 (dilute regime, f well under the 0.3
    # rule-of-thumb bound documented on the function):
    #   beta = (5-1)/(5+2) = 4/7
    #   mu_eff = 1 * (1 + 2*0.1*4/7) / (1 - 0.1*4/7)
    #          = (1 + 8/70) / (1 - 4/70) = (78/70) / (66/70) = 78/66 = 13/11
    f, mu_r, mu_host = 0.1, 5.0, 1.0
    beta = (mu_r - mu_host) / (mu_r + 2 * mu_host)
    expected = mu_host * (1 + 2 * f * beta) / (1 - f * beta)
    assert expected == pytest.approx(13 / 11)
    assert maxwell_garnett_effective_permeability(f, mu_r, mu_host) == pytest.approx(expected)


def test_maxwell_garnett_effective_permeability_increases_with_mu_r():
    # Physically, a more strongly magnetic element (larger mu_r) should
    # raise the effective medium's permeability above the host's, for a
    # fixed dilute fill fraction -- monotonicity sanity check.
    low = maxwell_garnett_effective_permeability(0.1, mu_r=2.0)
    high = maxwell_garnett_effective_permeability(0.1, mu_r=20.0)
    assert 1.0 < low < high


def test_maxwell_garnett_effective_permeability_increases_with_fill_fraction():
    sparse = maxwell_garnett_effective_permeability(0.05, mu_r=10.0)
    denser = maxwell_garnett_effective_permeability(0.25, mu_r=10.0)
    assert 1.0 < sparse < denser


def test_maxwell_garnett_effective_permeability_invalid_inputs_raise():
    with pytest.raises(ValueError):
        maxwell_garnett_effective_permeability(-0.1, mu_r=5.0)
    with pytest.raises(ValueError):
        maxwell_garnett_effective_permeability(1.0, mu_r=5.0)
    with pytest.raises(ValueError):
        maxwell_garnett_effective_permeability(1.5, mu_r=5.0)
    with pytest.raises(ValueError):
        maxwell_garnett_effective_permeability(0.1, mu_r=0.0)
    with pytest.raises(ValueError):
        maxwell_garnett_effective_permeability(0.1, mu_r=-5.0)
    with pytest.raises(ValueError):
        maxwell_garnett_effective_permeability(0.1, mu_r=5.0, mu_host=0.0)
    with pytest.raises(ValueError):
        maxwell_garnett_effective_permeability(0.1, mu_r=5.0, mu_host=-1.0)


# --- Aperture antenna gain ---
#
# Reference: standard aperture-antenna gain formula (Balanis, "Antenna
# Theory: Analysis and Design"): G = 4*pi*A_eff/lambda^2 * eta_ap.
# The clean-wavelength case below (freq = c, so lambda = 1 m exactly, per
# this module's own wavelength() function) lets G be checked against a
# hand-computed value using only elementary arithmetic.


def test_aperture_gain_ideal_efficiency_one_square_metre_at_clean_wavelength():
    # freq = c => lambda = 1 m exactly; area = 1 m^2; eta_ap = 1.0 (ideal,
    # 100%-efficient aperture) => G = 4*pi*1/1^2*1 = 4*pi.
    freq_hz = 299_792_458.0
    assert wavelength(freq_hz) == pytest.approx(1.0)
    result = aperture_gain(1.0, freq_hz, aperture_efficiency=1.0)
    assert result == pytest.approx(4 * math.pi)


def test_aperture_gain_matches_hand_computation_with_default_efficiency():
    # freq = c/2 => lambda = 2 m; area = 4 m^2; default eta_ap = 0.55.
    # G = 4*pi*4/2^2*0.55 = 4*pi*0.55.
    freq_hz = 299_792_458.0 / 2
    lambda_m = wavelength(freq_hz)
    assert lambda_m == pytest.approx(2.0)
    expected = 4 * math.pi * 4.0 / lambda_m**2 * 0.55
    assert aperture_gain(4.0, freq_hz) == pytest.approx(expected)
    assert aperture_gain(4.0, freq_hz) == pytest.approx(4 * math.pi * 0.55)


def test_aperture_gain_scales_linearly_with_area_and_efficiency():
    freq_hz = 2.4e9
    base = aperture_gain(1.0, freq_hz, aperture_efficiency=0.5)
    double_area = aperture_gain(2.0, freq_hz, aperture_efficiency=0.5)
    double_eta = aperture_gain(1.0, freq_hz, aperture_efficiency=1.0)
    assert double_area == pytest.approx(2 * base)
    assert double_eta == pytest.approx(2 * base)


def test_aperture_gain_invalid_inputs_raise():
    with pytest.raises(ValueError):
        aperture_gain(0.0, 2.4e9)
    with pytest.raises(ValueError):
        aperture_gain(-1.0, 2.4e9)
    with pytest.raises(ValueError):
        aperture_gain(1.0, 0.0)
    with pytest.raises(ValueError):
        aperture_gain(1.0, -2.4e9)
    with pytest.raises(ValueError):
        aperture_gain(1.0, 2.4e9, aperture_efficiency=0.0)
    with pytest.raises(ValueError):
        aperture_gain(1.0, 2.4e9, aperture_efficiency=1.5)
