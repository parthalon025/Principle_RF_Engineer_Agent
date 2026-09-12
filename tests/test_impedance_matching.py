import pytest

from rf_tools.impedance_matching import l_network_match, quarter_wave_transformer_impedance

# --- Impedance matching ---
#
# quarter_wave_transformer_impedance uses the standard real-impedance
# quarter-wave transformer formula Z_t = sqrt(Z_source*Z_load) (Pozar).
#
# l_network_match uses the standard Pozar sec. 5.1 two-solution L-network
# synthesis. Rather than re-deriving its closed-form output values, each
# test case below independently verifies the *physical claim* the function
# makes: that assembling the returned (X, B) pair into the L-network
# topology its own docstring specifies (shunt-then-series for
# Re(z_load) >= z_source, series-then-shunt otherwise) reduces the network's
# input impedance to exactly z_source -- i.e. impedance-combination algebra
# independent of the closed-form formula used to derive X and B. The two
# all-real cases below (Z0=50, Zl=100 and Z0=50, Zl=25) were additionally
# hand-verified against that same reconstruction offline with exact
# fractions, so the expected (X, B) literals are known-good, not just
# self-consistent.


def _reconstruct_shunt_at_load_then_series(z_load: complex, x: float, b: float) -> complex:
    y_shunt = 1 / z_load + 1j * b
    z_after_shunt = 1 / y_shunt
    return z_after_shunt + 1j * x


def _reconstruct_series_at_load_then_shunt(z_load: complex, x: float, b: float) -> complex:
    z_after_series = z_load + 1j * x
    y_total = 1 / z_after_series + 1j * b
    return 1 / y_total


def test_quarter_wave_transformer_round_numbers():
    assert quarter_wave_transformer_impedance(50.0, 200.0) == pytest.approx(100.0)


def test_quarter_wave_transformer_invalid_inputs_raise():
    with pytest.raises(ValueError):
        quarter_wave_transformer_impedance(0.0, 200.0)
    with pytest.raises(ValueError):
        quarter_wave_transformer_impedance(-50.0, 200.0)
    with pytest.raises(ValueError):
        quarter_wave_transformer_impedance(50.0, 0.0)
    with pytest.raises(ValueError):
        quarter_wave_transformer_impedance(50.0, -200.0)


def test_l_network_match_shunt_first_topology_real_load():
    # Z0=50, Zl=100 (Rl > Z0): hand-verified exact solutions.
    solutions = sorted(l_network_match(50.0, 100.0 + 0j), key=lambda pair: pair[0])
    expected = [(-50.0, -0.01), (50.0, 0.01)]
    assert len(solutions) == len(expected)
    for (x, b), (expected_x, expected_b) in zip(solutions, expected, strict=True):
        assert x == pytest.approx(expected_x)
        assert b == pytest.approx(expected_b)
        z_in = _reconstruct_shunt_at_load_then_series(100.0 + 0j, x, b)
        assert z_in == pytest.approx(50.0 + 0j, abs=1e-9)


def test_l_network_match_series_first_topology_real_load():
    # Z0=50, Zl=25 (Rl < Z0): hand-verified exact solutions.
    solutions = sorted(l_network_match(50.0, 25.0 + 0j), key=lambda pair: pair[0])
    expected = [(-25.0, -0.02), (25.0, 0.02)]
    assert len(solutions) == len(expected)
    for (x, b), (expected_x, expected_b) in zip(solutions, expected, strict=True):
        assert x == pytest.approx(expected_x)
        assert b == pytest.approx(expected_b)
        z_in = _reconstruct_series_at_load_then_shunt(25.0 + 0j, x, b)
        assert z_in == pytest.approx(50.0 + 0j, abs=1e-9)


def test_l_network_match_complex_load_reconstructs_to_source():
    z0 = 50.0
    z_load = 100.0 + 50.0j
    solutions = l_network_match(z0, z_load)
    assert len(solutions) == 2
    for x, b in solutions:
        z_in = _reconstruct_shunt_at_load_then_series(z_load, x, b)
        assert z_in == pytest.approx(complex(z0), abs=1e-9)


def test_l_network_match_boundary_rl_equals_z0_reconstructs_to_source():
    # Rl == Z0 exactly, with a nonzero load reactance: still two distinct
    # solutions (one of which is the trivial X=-Xl, B=0 cancellation).
    z0 = 50.0
    z_load = 50.0 + 30.0j
    solutions = l_network_match(z0, z_load)
    assert len(solutions) == 2
    trivial = [pair for pair in solutions if pair[1] == pytest.approx(0.0, abs=1e-9)]
    assert len(trivial) == 1
    assert trivial[0][0] == pytest.approx(-30.0)
    for x, b in solutions:
        z_in = _reconstruct_shunt_at_load_then_series(z_load, x, b)
        assert z_in == pytest.approx(complex(z0), abs=1e-9)


def test_l_network_match_invalid_inputs_raise():
    with pytest.raises(ValueError):
        l_network_match(0.0, 100.0 + 0j)
    with pytest.raises(ValueError):
        l_network_match(-50.0, 100.0 + 0j)
    with pytest.raises(ValueError):
        l_network_match(50.0, 0.0 + 10j)
    with pytest.raises(ValueError):
        l_network_match(50.0, -10.0 + 10j)
