import pytest

from rf_tools.calculations import (
    maxwell_garnett_effective_permeability,
)

# --- Patch antenna synthesis tests moved to tests/test_patch_synthesis.py ---
#
# wavelength, patch_effective_permittivity, patch_length_extension_m,
# patch_resonant_frequency_hz, fractional_bandwidth_from_q,
# quality_factor_from_fractional_bandwidth, curvature_length_correction_factor,
# curvature_shifted_resonant_frequency_hz, curvature_exceeds_validity_box, and
# aperture_gain (issue #522) now live in rf_tools/patch_synthesis.py, with
# their tests alongside in tests/test_patch_synthesis.py. Microstrip
# transmission-line synthesis (issue #286) lives in
# rf_tools/microstrip_line.py, with its tests in tests/test_microstrip_line.py.


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
