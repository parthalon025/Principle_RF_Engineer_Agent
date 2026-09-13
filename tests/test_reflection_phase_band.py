"""Issue #346: the +/-90 degree in-phase reflection band computed from a
Palace reflection-phase sweep."""

from __future__ import annotations

import cmath

import pytest

from rf_tools.reflection_phase_band import (
    in_phase_reflection_band,
    in_phase_reflection_bands,
)


def test_hand_worked_linear_phase_curve():
    """A hand-worked case: phase(f_ghz) = 300 - 60*f_ghz is linear, crosses
    zero exactly at 5 GHz, +90 degrees at 3.5 GHz and -90 degrees at 6.5
    GHz -- every value here is checkable by hand, with no wrap-around
    involved (the raw samples never leave (-180, 180])."""
    frequency_hz = [3e9, 4e9, 5e9, 6e9, 7e9]
    phase_deg = [120.0, 60.0, 0.0, -60.0, -120.0]

    band = in_phase_reflection_band(frequency_hz, phase_deg)

    assert band is not None
    assert band["center_frequency_hz"] == pytest.approx(5e9)
    assert band["low_hz"] == pytest.approx(3.5e9)
    assert band["high_hz"] == pytest.approx(6.5e9)
    assert band["bandwidth_hz"] == pytest.approx(3e9)
    assert band["fractional_bandwidth_percent"] == pytest.approx(60.0)
    assert band["validity"] == []


def test_hand_worked_phase_curve_wraps_past_180_degrees():
    """Hand-worked, and specifically exercising phase wrap-around (issue
    #346 AC 2): the true underlying phase is the linear ramp
    phase(f_ghz) = 180 - 60*f_ghz, which passes through -180 degrees
    between 6 and 7 GHz. A solver reports phase as a principal value in
    (-180, 180], so the 7 GHz sample is reported as -240 + 360 = 120
    degrees -- a raw jump from -180 to +120 that is NOT a real
    discontinuity. Without unwrapping, a naive threshold search would
    invent a spurious +90 degree crossing between 6 and 7 GHz (the raw
    values -180 and 120 straddle +90); unwrapping recovers the true
    continuous curve, which never returns anywhere near +90 after 2 GHz.
    Hand-computed correct answer: zero crossing at 3 GHz (exact sample),
    +90 at 1.5 GHz, -90 at 4.5 GHz."""
    frequency_hz = [1e9, 2e9, 3e9, 4e9, 5e9, 6e9, 7e9]
    raw_principal_value_phase_deg = [120.0, 60.0, 0.0, -60.0, -120.0, -180.0, 120.0]

    band = in_phase_reflection_band(frequency_hz, raw_principal_value_phase_deg)

    assert band is not None
    assert band["center_frequency_hz"] == pytest.approx(3e9)
    assert band["low_hz"] == pytest.approx(1.5e9)
    assert band["high_hz"] == pytest.approx(4.5e9)
    assert band["bandwidth_hz"] == pytest.approx(3e9)
    assert band["fractional_bandwidth_percent"] == pytest.approx(100.0)


def test_phase_never_crossing_zero_reports_no_band():
    """#346 AC 3: a candidate whose phase never gets near the
    magnetic-mirror point must report no band, not a wrong one."""
    frequency_hz = [8e9, 9e9, 10e9, 11e9, 12e9]
    phase_deg = [150.0, 140.0, 130.0, 120.0, 110.0]

    assert in_phase_reflection_band(frequency_hz, phase_deg) is None


def test_band_edge_outside_swept_range_is_flagged():
    """A sweep that only captures the descending side of the curve (never
    reaching -90 degrees) must still report the visible partial band, but
    flag that the true edge could lie further out."""
    frequency_hz = [4e9, 4.5e9, 5e9]
    phase_deg = [60.0, 30.0, 0.0]  # crosses zero at 5 GHz; sweep stops there

    band = in_phase_reflection_band(frequency_hz, phase_deg)

    assert band is not None
    assert band["center_frequency_hz"] == pytest.approx(5e9)
    assert band["low_hz"] == pytest.approx(4e9)  # true +90 edge is before the sweep start
    assert band["high_hz"] == pytest.approx(5e9)  # sweep ends exactly at center; no -90 edge seen
    flags = [entry["flag"] for entry in band["validity"]]
    assert "band_edge_outside_swept_range" in flags


def test_unordered_frequencies_are_sorted_internally():
    frequency_hz = [7e9, 3e9, 5e9, 4e9, 6e9]
    phase_deg = [-120.0, 120.0, 0.0, 60.0, -60.0]

    band = in_phase_reflection_band(frequency_hz, phase_deg)

    assert band["center_frequency_hz"] == pytest.approx(5e9)
    assert band["low_hz"] == pytest.approx(3.5e9)
    assert band["high_hz"] == pytest.approx(6.5e9)


def test_mismatched_lengths_raise():
    with pytest.raises(ValueError, match="same length"):
        in_phase_reflection_band([1e9, 2e9], [0.0])


def test_single_sample_returns_no_band():
    assert in_phase_reflection_band([5e9], [0.0]) is None


def test_in_phase_reflection_bands_reads_palace_specular_shape_per_mode():
    """#346 AC 1: the per-Floquet-mode wrapper takes Palace's own
    `s_parameters["specular"]` shape directly -- one complex reflection
    coefficient per frequency, per mode label -- and derives phase from it
    itself."""
    frequency_hz = [3e9, 4e9, 5e9, 6e9, 7e9]

    def polar(mag, deg):
        return complex(mag * cmath.exp(1j * cmath.pi * deg / 180))

    specular = {
        "S11_TE": [polar(0.9, deg) for deg in (120.0, 60.0, 0.0, -60.0, -120.0)],
        # Never near zero: no band for this mode.
        "S11_TM": [polar(0.9, deg) for deg in (150.0, 140.0, 130.0, 120.0, 110.0)],
    }

    result = in_phase_reflection_bands(frequency_hz, specular)

    assert result["provenance"] == "SIMULATED"
    assert result["bands"]["S11_TE"]["center_frequency_hz"] == pytest.approx(5e9)
    assert result["bands"]["S11_TM"] is None


def test_in_phase_reflection_bands_provenance_passthrough():
    result = in_phase_reflection_bands(
        [5e9, 6e9], {"S11_TE": [complex(1, 0), complex(-1, 0)]}, provenance="MEASURED"
    )
    assert result["provenance"] == "MEASURED"
