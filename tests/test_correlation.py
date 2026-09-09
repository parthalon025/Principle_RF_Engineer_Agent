from pathlib import Path

import numpy as np
import pytest
import skrf as rf

from rf_tools.correlation import CorrelationError, correlate_simulation_measurement

C0 = 299792458.0  # speed of light, m/s


def _lossless_line_s21(freqs_hz: np.ndarray, length_m: float, er: float = 1.0) -> np.ndarray:
    """Closed-form S21 of a matched, lossless transmission line -- same
    formula tests/test_touchstone.py uses, so the perturbation this module's
    tests apply is hand-computable the same way."""
    beta = 2 * np.pi * freqs_hz * np.sqrt(er) / C0
    return np.exp(-1j * beta * length_m)


def _matched_line_network(freqs_hz: np.ndarray, length_m: float, z0: float = 50.0) -> rf.Network:
    s = np.zeros((len(freqs_hz), 2, 2), dtype=complex)
    s21 = _lossless_line_s21(freqs_hz, length_m)
    s[:, 1, 0] = s21
    s[:, 0, 1] = s21
    freq = rf.Frequency.from_f(freqs_hz, unit="hz")
    return rf.Network(frequency=freq, s=s, z0=z0)


def _lossy_two_port(
    freqs_hz: np.ndarray,
    *,
    reflection: complex,
    insertion_loss_mag: float,
    length_m: float,
    z0: float = 50.0,
) -> rf.Network:
    s21 = insertion_loss_mag * _lossless_line_s21(freqs_hz, length_m)
    s = np.zeros((len(freqs_hz), 2, 2), dtype=complex)
    s[:, 0, 0] = reflection
    s[:, 1, 1] = reflection
    s[:, 1, 0] = s21
    s[:, 0, 1] = s21
    freq = rf.Frequency.from_f(freqs_hz, unit="hz")
    return rf.Network(frequency=freq, s=s, z0=z0)


# ---------------------------------------------------------------------------
# Core synthetic case: a known simulated network and a known, deliberate,
# hand-computable perturbation of it as the "measured" network -- ticket
# #45's acceptance criterion.
# ---------------------------------------------------------------------------


def test_correlate_known_loss_perturbation_matches_hand_computed_diff():
    freqs_hz = np.linspace(1e9, 5e9, 9)
    length_m = 0.05
    loss_mag = 0.95  # measured has an added small loss term vs. the sim

    simulated_network = _matched_line_network(freqs_hz, length_m)
    s_meas = np.zeros((len(freqs_hz), 2, 2), dtype=complex)
    s21_meas = loss_mag * _lossless_line_s21(freqs_hz, length_m)
    s_meas[:, 1, 0] = s21_meas
    s_meas[:, 0, 1] = s21_meas
    freq = rf.Frequency.from_f(freqs_hz, unit="hz")
    measured_network = rf.Network(frequency=freq, s=s_meas, z0=50.0)

    result = correlate_simulation_measurement(
        {"network": simulated_network, "provenance": "SIMULATED"},
        {"network": measured_network, "provenance": "MEASURED"},
    )

    assert result["provenance"] == "CALCULATED"
    assert result["simulated_provenance"] == "SIMULATED"
    assert result["measured_provenance"] == "MEASURED"

    comparison = result["comparison"]
    assert comparison["ports"] == 2

    # Hand-computable: S21 magnitude ratio is exactly loss_mag everywhere,
    # so the dB magnitude diff is 20*log10(loss_mag) at every frequency.
    expected_db_diff = 20 * np.log10(loss_mag)
    s21 = comparison["s21"]
    np.testing.assert_allclose(s21["magnitude_diff_db"], expected_db_diff, atol=1e-9)
    assert s21["max_magnitude_diff_db"] == pytest.approx(abs(expected_db_diff), abs=1e-9)

    # S11/S22 are unperturbed (both matched lines), so their diff is exactly
    # zero -- the perturbation only touched the insertion loss term.
    for key in ("s11", "s22"):
        assert comparison[key]["max_abs_diff"] == pytest.approx(0.0, abs=1e-9)

    assert "no renormalization needed" in result["reference_impedance_note"]
    assert "SKIPPED" in result["calibration_plane_note"]
    assert "NO-OP" in result["temperature_note"]
    assert result["temperature_detail"]["flagged"] is False


def test_correlate_known_length_perturbation_matches_hand_computed_diff():
    """A second, distinct closed-form perturbation (a length delta rather
    than a loss term) -- exercises the same acceptance criterion with a
    different, independently hand-computable known difference."""
    freqs_hz = np.linspace(1e9, 5e9, 9)
    length_sim_m = 0.05
    length_meas_m = 0.0505  # measured line is 0.5 mm longer

    simulated_network = _matched_line_network(freqs_hz, length_sim_m)
    measured_network = _matched_line_network(freqs_hz, length_meas_m)

    result = correlate_simulation_measurement(
        simulated_network,
        measured_network,  # bare skrf.Network inputs
    )

    expected_s21_sim = _lossless_line_s21(freqs_hz, length_sim_m)
    expected_s21_meas = _lossless_line_s21(freqs_hz, length_meas_m)
    expected_diff = expected_s21_meas - expected_s21_sim

    s21 = result["comparison"]["s21"]
    np.testing.assert_allclose(np.asarray(s21["diff"]), expected_diff, atol=1e-9)
    assert s21["rms_diff"] == pytest.approx(
        float(np.sqrt(np.mean(np.abs(expected_diff) ** 2))), abs=1e-9
    )
    # Default input (no explicit "provenance" key) falls back to this
    # function's own SIMULATED/MEASURED convention for the two input kinds.
    assert result["simulated_provenance"] == "SIMULATED"
    assert result["measured_provenance"] == "MEASURED"


# ---------------------------------------------------------------------------
# Calibration-plane normalization: fixture de-embedding, reusing Phase 2's
# deembed_touchstone.
# ---------------------------------------------------------------------------


def test_correlate_with_fixture_deembeds_before_comparison(tmp_path: Path):
    freqs_hz = np.linspace(1e9, 5e9, 9)
    fixture = _lossy_two_port(
        freqs_hz, reflection=0.05 + 0.02j, insertion_loss_mag=0.9, length_m=0.01
    )
    dut = _lossy_two_port(freqs_hz, reflection=0.1 - 0.03j, insertion_loss_mag=0.3, length_m=0.03)
    # what a VNA actually measures: the fixture is physically in the path.
    measured_raw = fixture**dut

    fixture_path = tmp_path / "fixture.s2p"
    fixture.write_touchstone(str(fixture_path))

    result = correlate_simulation_measurement(
        {"network": dut}, {"network": measured_raw}, fixture_path=str(fixture_path)
    )

    assert "De-embedded fixture effects" in result["calibration_plane_note"]
    # Once de-embedded, measured == dut == simulated: diff should be ~0.
    for key in ("s11", "s21", "s12", "s22"):
        assert result["comparison"][key]["max_abs_diff"] == pytest.approx(0.0, abs=1e-6)


def test_correlate_without_fixture_documents_skip():
    freqs_hz = np.linspace(1e9, 5e9, 9)
    net = _matched_line_network(freqs_hz, 0.05)

    result = correlate_simulation_measurement({"network": net}, {"network": net})

    assert "SKIPPED" in result["calibration_plane_note"]
    assert "fixture_path" in result["calibration_plane_note"]


# ---------------------------------------------------------------------------
# Reference-impedance normalization: z0 mismatch handling.
# ---------------------------------------------------------------------------


def test_correlate_renormalizes_z0_mismatch_before_comparison():
    freqs_hz = np.linspace(1e9, 5e9, 9)
    simulated_network = _matched_line_network(freqs_hz, 0.05, z0=50.0)

    # Same physical network, but measured/reported at a different reference
    # impedance -- renormalizing it back to 50 ohm should recover an
    # (almost) exact match against the simulated network.
    measured_network = simulated_network.copy()
    measured_network.renormalize(75.0)
    assert not np.allclose(np.asarray(measured_network.z0[0]), 50.0)

    result = correlate_simulation_measurement(
        {"network": simulated_network}, {"network": measured_network}
    )

    assert "renormalized" in result["reference_impedance_note"]
    for key in ("s11", "s21", "s12", "s22"):
        assert result["comparison"][key]["max_abs_diff"] == pytest.approx(0.0, abs=1e-9)


def test_correlate_z0_already_matched_skips_renormalization():
    freqs_hz = np.linspace(1e9, 5e9, 9)
    net = _matched_line_network(freqs_hz, 0.05, z0=50.0)

    result = correlate_simulation_measurement({"network": net}, {"network": net})

    assert "no renormalization needed" in result["reference_impedance_note"]


def test_correlate_port_count_mismatch_raises():
    freqs_hz = np.linspace(1e9, 5e9, 9)
    two_port = _matched_line_network(freqs_hz, 0.05)
    freq = rf.Frequency.from_f(freqs_hz, unit="hz")
    one_port = rf.Network(frequency=freq, s=np.zeros((9, 1, 1), dtype=complex), z0=50)

    with pytest.raises(CorrelationError, match="port"):
        correlate_simulation_measurement({"network": two_port}, {"network": one_port})


# ---------------------------------------------------------------------------
# Temperature: documented no-op unless data is actually present, plus a
# flagged-difference case.
# ---------------------------------------------------------------------------


def test_correlate_temperature_flags_significant_difference():
    freqs_hz = np.linspace(1e9, 5e9, 9)
    net = _matched_line_network(freqs_hz, 0.05)

    result = correlate_simulation_measurement(
        {"network": net, "temperature_c": 22.0},
        {"network": net, "temperature_c": 45.0},
    )

    assert result["temperature_detail"]["flagged"] is True
    assert "FLAGGED" in result["temperature_note"]
    assert result["temperature_detail"]["delta_c"] == pytest.approx(23.0)


def test_correlate_temperature_within_tolerance_not_flagged():
    freqs_hz = np.linspace(1e9, 5e9, 9)
    net = _matched_line_network(freqs_hz, 0.05)

    result = correlate_simulation_measurement(
        {"network": net, "temperature_c": 22.0},
        {"network": net, "temperature_c": 23.0},
    )

    assert result["temperature_detail"]["flagged"] is False
    assert "agree within" in result["temperature_note"]


def test_correlate_temperature_one_sided_not_flagged():
    freqs_hz = np.linspace(1e9, 5e9, 9)
    net = _matched_line_network(freqs_hz, 0.05)

    result = correlate_simulation_measurement(
        {"network": net, "temperature_c": 22.0}, {"network": net}
    )

    assert result["temperature_detail"]["flagged"] is False
    assert "present on one side only" in result["temperature_note"]


# ---------------------------------------------------------------------------
# known_tolerance_db (issue #254): a mechanical, per-S-parameter comparison
# of the already-computed max_magnitude_diff_db against a caller-supplied
# bound (see correlate_simulation_measurement's docstring and docs/adr/0009
# for what this field is and isn't). Mirrors the temperature-tolerance test
# triad above: supplied-and-within, supplied-and-exceeds, not-supplied-at-
# all, and a per-parameter dict case.
# ---------------------------------------------------------------------------


def _known_loss_perturbation_result(**kwargs):
    """Same synthetic simulated/measured pair as
    test_correlate_known_loss_perturbation_matches_hand_computed_diff:
    s21 has a known, hand-computable ~0.445 dB diff (20*log10(0.95));
    s11/s22 are exactly 0 dB apart (both unperturbed matched lines)."""
    freqs_hz = np.linspace(1e9, 5e9, 9)
    length_m = 0.05
    loss_mag = 0.95

    simulated_network = _matched_line_network(freqs_hz, length_m)
    s_meas = np.zeros((len(freqs_hz), 2, 2), dtype=complex)
    s21_meas = loss_mag * _lossless_line_s21(freqs_hz, length_m)
    s_meas[:, 1, 0] = s21_meas
    s_meas[:, 0, 1] = s21_meas
    freq = rf.Frequency.from_f(freqs_hz, unit="hz")
    measured_network = rf.Network(frequency=freq, s=s_meas, z0=50.0)

    return correlate_simulation_measurement(
        {"network": simulated_network}, {"network": measured_network}, **kwargs
    )


def test_correlate_tolerance_not_supplied_records_no_data():
    result = _known_loss_perturbation_result()

    for key in ("s11", "s21", "s12", "s22"):
        assert result["comparison"][key]["tolerance_comparison"] == "NO_TOLERANCE_ON_RECORD"
    assert "no known_tolerance_db" in result["tolerance_comparison_note"].lower()


def test_correlate_tolerance_within_known_bound_not_flagged():
    result = _known_loss_perturbation_result(known_tolerance_db=1.0)

    comparison = result["comparison"]
    # s21's known diff is ~0.445 dB, well inside a 1.0 dB bound.
    assert comparison["s21"]["max_magnitude_diff_db"] == pytest.approx(0.445, abs=1e-2)
    for key in ("s11", "s21", "s12", "s22"):
        assert comparison[key]["tolerance_comparison"] == "WITHIN_KNOWN_TOLERANCE"
    assert "1" in result["tolerance_comparison_note"]


def test_correlate_tolerance_exceeds_known_bound_flagged():
    result = _known_loss_perturbation_result(known_tolerance_db=0.1)

    comparison = result["comparison"]
    assert comparison["s21"]["tolerance_comparison"] == "EXCEEDS_KNOWN_TOLERANCE"
    # s11/s22 are exactly 0 dB apart -- still inside even a tight 0.1 dB bound.
    for key in ("s11", "s22"):
        assert comparison[key]["tolerance_comparison"] == "WITHIN_KNOWN_TOLERANCE"


def test_correlate_tolerance_dict_applies_per_parameter_independently():
    result = _known_loss_perturbation_result(known_tolerance_db={"s21": 0.1})

    comparison = result["comparison"]
    assert comparison["s21"]["tolerance_comparison"] == "EXCEEDS_KNOWN_TOLERANCE"
    # s11/s12/s22 weren't named in the dict -- no tolerance on record for
    # them, not a fabricated pass borrowed from s21's bound.
    for key in ("s11", "s12", "s22"):
        assert comparison[key]["tolerance_comparison"] == "NO_TOLERANCE_ON_RECORD"


def test_correlate_tolerance_comparison_never_names_model_or_design():
    """See docs/adr/0009: exactly three mechanical values, never a
    model-vs-design verdict."""
    result = _known_loss_perturbation_result(known_tolerance_db={"s21": 0.1})

    allowed = {"WITHIN_KNOWN_TOLERANCE", "EXCEEDS_KNOWN_TOLERANCE", "NO_TOLERANCE_ON_RECORD"}
    for key in ("s11", "s21", "s12", "s22"):
        assert result["comparison"][key]["tolerance_comparison"] in allowed
    note_lower = result["tolerance_comparison_note"].lower()
    for banned in ("model was wrong", "design was wrong", "model_wrong", "design_wrong"):
        assert banned not in note_lower


def test_correlate_tolerance_dict_with_uppercase_key_raises():
    """Issue #254's spec text says the dict is 'keyed the same way
    s_parameters already is' (upper-case, e.g. "S11"), but comparison's own
    keys are lower-case -- a caller following the spec's literal words who
    passes {"S11": ...} must get a clear error, not a silent
    NO_TOLERANCE_ON_RECORD for every parameter."""
    with pytest.raises(CorrelationError, match="S11"):
        _known_loss_perturbation_result(known_tolerance_db={"S11": 0.1})


def test_correlate_tolerance_dict_with_unrecognized_key_raises():
    with pytest.raises(CorrelationError, match="s99"):
        _known_loss_perturbation_result(known_tolerance_db={"s99": 0.1})


# ---------------------------------------------------------------------------
# Bridging the type gap: input shapes, and honest failure on the shapes
# today's NEC2++/openEMS adapters actually produce.
# ---------------------------------------------------------------------------


def test_correlate_accepts_generic_vna_shaped_measured_result():
    freqs_hz = np.linspace(1e9, 5e9, 9)
    simulated_network = _matched_line_network(freqs_hz, 0.05)

    s21 = _lossless_line_s21(freqs_hz, 0.05)
    measured_like_vna_output = {
        "provenance": "MEASURED",
        "frequency_hz": freqs_hz.tolist(),
        "z0": 50.0,
        "s_parameters": {
            "S11": [str(complex(v)) for v in np.zeros(len(freqs_hz), dtype=complex)],
            "S12": [str(complex(v)) for v in s21],
            "S21": [str(complex(v)) for v in s21],
            "S22": [str(complex(v)) for v in np.zeros(len(freqs_hz), dtype=complex)],
        },
    }

    result = correlate_simulation_measurement(
        {"network": simulated_network}, measured_like_vna_output
    )

    assert result["comparison"]["s21"]["max_abs_diff"] == pytest.approx(0.0, abs=1e-9)


def test_correlate_accepts_touchstone_file_path(tmp_path: Path):
    freqs_hz = np.linspace(1e9, 5e9, 9)
    net = _matched_line_network(freqs_hz, 0.05)
    path = tmp_path / "measured.s2p"
    net.write_touchstone(str(path))

    result = correlate_simulation_measurement({"network": net}, {"touchstone_file": str(path)})

    assert result["comparison"]["s21"]["max_abs_diff"] == pytest.approx(0.0, abs=1e-9)


def test_correlate_rejects_nec2_style_result_without_s_parameters():
    freqs_hz = np.linspace(1e9, 5e9, 9)
    net = _matched_line_network(freqs_hz, 0.05)

    # simulation.nec2pp.run_nec2_simulation's real output shape: a
    # single-frequency feed-point impedance, no S-parameter sweep at all.
    nec2_like_result = {
        "provenance": "SIMULATED",
        "impedance": {
            "resistance_ohms": 72.0,
            "reactance_ohms": 5.0,
        },
        "pattern": [],
        "gain_dbi": 2.1,
    }

    with pytest.raises(CorrelationError, match="S-parameter"):
        correlate_simulation_measurement(nec2_like_result, {"network": net})


def test_correlate_rejects_openems_style_result_with_stubbed_s_parameters():
    freqs_hz = np.linspace(1e9, 5e9, 9)
    net = _matched_line_network(freqs_hz, 0.05)

    # simulation.openems.run_openems_simulation's real output shape:
    # s_parameters is present but explicitly stubbed (computed=False).
    openems_like_result = {
        "provenance": "SIMULATED",
        "convergence": {"terminated_reason": "end_criteria"},
        "s_parameters": {"computed": False, "note": "not computed in this pass"},
        "far_field": {"computed": False},
        "gain_dbi": None,
    }

    with pytest.raises(CorrelationError, match="S-parameter"):
        correlate_simulation_measurement(openems_like_result, {"network": net})


def test_correlate_rejects_unsupported_s_parameter_set():
    freqs_hz = np.linspace(1e9, 5e9, 9)
    net = _matched_line_network(freqs_hz, 0.05)

    bad_result = {
        "frequency_hz": freqs_hz.tolist(),
        "z0": 50.0,
        "s_parameters": {"S11": ["0j"] * len(freqs_hz)},  # missing S12/S21/S22 for 2-port
    }
    # bad_result parses as a valid 1-port; mismatch against net's 2 ports
    # should raise a port-count error, not silently compare mismatched data.
    with pytest.raises(CorrelationError, match="port"):
        correlate_simulation_measurement({"network": net}, bad_result)


def test_correlate_rejects_missing_touchstone_file():
    freqs_hz = np.linspace(1e9, 5e9, 9)
    net = _matched_line_network(freqs_hz, 0.05)

    with pytest.raises(CorrelationError, match="does not exist"):
        correlate_simulation_measurement(
            {"network": net}, {"touchstone_file": "/nonexistent/path/measured.s2p"}
        )
