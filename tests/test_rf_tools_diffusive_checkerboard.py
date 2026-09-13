"""Tests for rf_tools/diffusive_checkerboard.py (issue #550).

Pure-function tests only -- every function here takes/returns plain data,
no database, no solver. `symbol_entries` fixtures are hand-built the same
way tests/test_element_alphabet.py's own fixtures are (via
`designs.element_alphabet.add_symbol_entry`, or a hand-built dict for a
SIMULATED entry that module cannot yet produce itself -- see
`weaker_provenance`'s own docstring for why this module never assumes
`add_symbol_entry`'s current MEASURED-only behaviour).
"""

from __future__ import annotations

import json
import math

import pytest

from designs.element_alphabet import add_symbol_entry
from geometry.unit_cell import block_size_from_sizing_rule, phase_budget_deg
from rf_tools.diffusive_checkerboard import (
    DEFAULT_RCS_REDUCTION_THRESHOLD_DB,
    InsufficientTilesError,
    checkerboard_supercell_period_m,
    diffracted_order_exists,
    diffracted_order_regime,
    materialize_checkerboard_unit_cell_array,
    phase_error_deg,
    rcs_reduction_db,
    resolve_checkerboard_tile_symbols,
    score_diffusive_checkerboard,
    weaker_provenance,
)

SPEED_OF_LIGHT_M_S = 299_792_458.0

_GEOMETRY = {"shape": "box", "p1_m": [0.0, 0.0, 0.0], "p2_m": [0.001, 0.001, 0.0]}


def _flat_response(phase_deg: float, frequencies_hz: tuple[float, ...]) -> list[dict]:
    return [{"frequency_hz": f, "magnitude": 0.99, "phase_deg": phase_deg} for f in frequencies_hz]


def _tile_entry(symbol: str, phase_deg: float, frequencies_hz: tuple[float, ...], **overrides):
    kwargs = {
        "element_family": "checkerboard_ring_pair",
        "symbol": symbol,
        "frequency_low_hz": 9.0e9,
        "frequency_high_hz": 15.0e9,
        "incidence_angle_low_deg": 0.0,
        "incidence_angle_high_deg": 10.0,
        "process_id": 1,
        "geometry": _GEOMETRY,
        "response": _flat_response(phase_deg, frequencies_hz),
    }
    kwargs.update(overrides)
    return add_symbol_entry(**kwargs)


# ---------------------------------------------------------------------------
# phase_error_deg / rcs_reduction_db -- the closed-form Step 2/3 formulas.
# ---------------------------------------------------------------------------


class TestPhaseErrorAndReduction:
    def test_ideal_180_degree_pair_has_zero_dispersion(self):
        # phase_a - phase_b == 180 exactly -> dispersion term is 0.
        delta = phase_error_deg(180.0, 0.0, delta_phi_max_deg=0.0)
        assert delta == pytest.approx(0.0)

    def test_coupling_term_adds_delta_phi_max_at_the_plain_1_1_block(self):
        # boundary_fraction(1, 1) == 1.0 by construction, so the coupling
        # term is delta_phi_max_deg unscaled.
        delta = phase_error_deg(180.0, 0.0, delta_phi_max_deg=5.0)
        assert delta == pytest.approx(5.0)

    def test_in_phase_pair_is_the_worst_possible_dispersion(self):
        # phase_a - phase_b == 0 (both tiles reflect identically, like a
        # plain PEC sheet) -> dispersion is the full 180 degrees.
        delta = phase_error_deg(90.0, 90.0, delta_phi_max_deg=0.0)
        assert delta == pytest.approx(180.0)

    def test_rcs_reduction_db_is_zero_at_180_degree_error(self):
        # delta == 180 -> sin(90 deg) == 1 -> 20*log10(1) == 0 dB: no
        # reduction at all, the worst case.
        assert rcs_reduction_db(180.0) == pytest.approx(0.0)

    def test_rcs_reduction_db_is_very_negative_near_zero_error(self):
        # delta -> 0 -> the idealised, unbounded-cancellation limit.
        assert rcs_reduction_db(1e-6) < -90.0

    def test_rcs_reduction_db_exact_zero_delta_is_floored_not_infinite(self):
        # A literal -inf is not valid JSON (json.dumps emits "-Infinity",
        # which Postgres jsonb and any real JSON consumer reject) -- the
        # perfect-cancellation limit must be a large, finite floor instead.
        result = rcs_reduction_db(0.0)
        assert math.isfinite(result)
        assert result < -250.0
        json.dumps(result)  # must not raise

    def test_dispersion_is_symmetric_under_swapping_tile_a_and_tile_b(self):
        # Which symbol a caller happens to pass first is an arbitrary
        # labelling choice (resolve_checkerboard_tile_symbols picks it
        # alphabetically) -- the physical pair (180, 0) is identical to
        # (0, 180), so both orderings must give the same dispersion.
        forward = phase_error_deg(180.0, 0.0, delta_phi_max_deg=10.0)
        swapped = phase_error_deg(0.0, 180.0, delta_phi_max_deg=10.0)
        assert forward == pytest.approx(swapped)
        assert forward == pytest.approx(10.0)

    def test_a_negative_wrapped_phase_difference_is_handled_correctly(self):
        # phase_a - phase_b == -150 -- wraps to 210 degrees, 30 degrees
        # away from the ideal 180, not the 330 degrees a naive unwrapped
        # |180 - (-150)| would give.
        delta = phase_error_deg(-150.0, 0.0, delta_phi_max_deg=10.0)
        assert delta == pytest.approx(40.0)
        assert rcs_reduction_db(delta) == pytest.approx(-9.32, abs=0.01)

    def test_round_trips_against_phase_budget_deg_at_the_10db_point(self):
        # geometry.unit_cell.phase_budget_deg(10.0) is the delta at which
        # RCS_reduction_dB is exactly -10.0 dB -- the two functions are
        # algebraic inverses of each other at this point (module docstring).
        delta_budget_deg = phase_budget_deg(10.0)
        assert delta_budget_deg == pytest.approx(36.87, abs=0.01)
        assert rcs_reduction_db(delta_budget_deg) == pytest.approx(-10.0, abs=1e-9)

    def test_bigger_arrangement_style_reduction_is_more_negative(self):
        # Mirrors Cui et al.'s own Table I convention: a BETTER reduction is
        # a MORE NEGATIVE dB figure, never a smaller-magnitude one.
        better = rcs_reduction_db(10.0)
        worse = rcs_reduction_db(60.0)
        assert better < worse < 0.0


# ---------------------------------------------------------------------------
# The literature falsification target: 145-215 deg / "at least 10 dB
# guaranteed" (Cui et al. 2014; Haji-Ahmadi et al. 2017).
# ---------------------------------------------------------------------------


class TestLiteratureFalsificationWindow:
    def test_the_145_to_215_degree_window_guarantees_at_least_10db(self):
        # The window is phase DIFFERENCE 145-215 deg, i.e. delta = |180 -
        # phase_diff| up to 35 deg at the window's edge.
        delta_at_window_edge = 35.0
        reduction_db = rcs_reduction_db(delta_at_window_edge)
        assert reduction_db <= -10.0

    def test_just_outside_the_window_no_longer_guarantees_10db(self):
        delta_just_outside = 40.0
        reduction_db = rcs_reduction_db(delta_just_outside)
        assert reduction_db > -10.0


# ---------------------------------------------------------------------------
# resolve_checkerboard_tile_symbols -- the two-tile alphabet lookup.
# ---------------------------------------------------------------------------


class TestResolveCheckerboardTileSymbols:
    _FREQS = (10.0e9, 12.0e9, 14.0e9)

    def test_resolves_the_two_symbols_present_across_the_whole_band(self):
        entries = [
            _tile_entry("0", phase_deg=180.0, frequencies_hz=self._FREQS),
            _tile_entry("1", phase_deg=0.0, frequencies_hz=self._FREQS),
        ]
        tile_a, tile_b = resolve_checkerboard_tile_symbols(
            entries, "checkerboard_ring_pair", self._FREQS, incidence_angle_deg=0.0, process_id=1
        )
        assert (tile_a, tile_b) == ("0", "1")

    def test_a_symbol_missing_at_one_band_point_is_not_usable(self):
        # "1"'s own declared band stops at 11 GHz -- lookup_symbol_entries
        # matches against that declared band, not against which points its
        # response curve happens to carry -- so it cannot match the third
        # requested frequency (14 GHz), even though "0" can.
        entries = [
            _tile_entry("0", phase_deg=180.0, frequencies_hz=self._FREQS),
            _tile_entry(
                "1",
                phase_deg=0.0,
                frequencies_hz=self._FREQS[:2],
                frequency_high_hz=11.0e9,
            ),
        ]
        with pytest.raises(InsufficientTilesError, match="checkerboard_ring_pair"):
            resolve_checkerboard_tile_symbols(
                entries,
                "checkerboard_ring_pair",
                self._FREQS,
                incidence_angle_deg=0.0,
                process_id=1,
            )

    def test_error_names_the_full_failing_key(self):
        entries = [_tile_entry("0", phase_deg=180.0, frequencies_hz=self._FREQS)]
        with pytest.raises(InsufficientTilesError) as exc_info:
            resolve_checkerboard_tile_symbols(
                entries,
                "checkerboard_ring_pair",
                self._FREQS,
                incidence_angle_deg=5.0,
                process_id=3,
            )
        message = str(exc_info.value)
        assert "checkerboard_ring_pair" in message
        assert "incidence_angle_deg=5.0" in message
        assert "process_id=3" in message
        assert "10000000000.0" in message

    def test_a_different_element_family_never_matches(self):
        entries = [
            _tile_entry("0", phase_deg=180.0, frequencies_hz=self._FREQS, element_family="other"),
            _tile_entry("1", phase_deg=0.0, frequencies_hz=self._FREQS, element_family="other"),
        ]
        with pytest.raises(InsufficientTilesError):
            resolve_checkerboard_tile_symbols(
                entries,
                "checkerboard_ring_pair",
                self._FREQS,
                incidence_angle_deg=0.0,
                process_id=1,
            )


# ---------------------------------------------------------------------------
# weaker_provenance
# ---------------------------------------------------------------------------


class TestWeakerProvenance:
    @pytest.mark.parametrize(
        ("a", "b", "expected"),
        [
            ("MEASURED", "MEASURED", "MEASURED"),
            ("MEASURED", "SIMULATED", "SIMULATED"),
            ("SIMULATED", "MEASURED", "SIMULATED"),
            ("SIMULATED", "SIMULATED", "SIMULATED"),
        ],
    )
    def test_combination_table(self, a, b, expected):
        assert weaker_provenance(a, b) == expected

    def test_unrecognised_provenance_raises(self):
        with pytest.raises(ValueError, match="unrecognised provenance"):
            weaker_provenance("MEASURED", "ASSUMED")


# ---------------------------------------------------------------------------
# score_diffusive_checkerboard -- worst-in-band, threshold, provenance.
# ---------------------------------------------------------------------------


class TestScoreDiffusiveCheckerboard:
    _FREQS = (10.0e9, 12.0e9, 14.0e9)

    def test_worst_in_band_is_the_true_worst_point_not_an_average(self):
        # Tile "0" carries a big dispersion swing across the band -- ideal
        # at 10 GHz, badly off by 12 GHz -- so the average would look
        # decent while the worst point does not.
        entries = [
            add_symbol_entry(
                element_family="fam",
                symbol="0",
                frequency_low_hz=9.0e9,
                frequency_high_hz=15.0e9,
                incidence_angle_low_deg=0.0,
                incidence_angle_high_deg=10.0,
                process_id=1,
                geometry=_GEOMETRY,
                response=[
                    {"frequency_hz": 10.0e9, "magnitude": 0.99, "phase_deg": 180.0},
                    {"frequency_hz": 12.0e9, "magnitude": 0.99, "phase_deg": 130.0},
                    {"frequency_hz": 14.0e9, "magnitude": 0.99, "phase_deg": 180.0},
                ],
            ),
            _tile_entry("1", phase_deg=0.0, frequencies_hz=self._FREQS, element_family="fam"),
        ]
        report = score_diffusive_checkerboard(
            entries,
            "fam",
            self._FREQS,
            incidence_angle_deg=0.0,
            process_id=1,
            delta_phi_max_deg=0.0,
        )
        assert report["worst_frequency_hz"] == 12.0e9
        # The worst point's own reduction, not an average across the band.
        expected_worst = rcs_reduction_db(abs(180.0 - 130.0))
        assert report["worst_rcs_reduction_db"] == pytest.approx(expected_worst)
        # Confirm this really is worse (closer to 0) than the other points.
        other_points_db = [
            p["rcs_reduction_db"] for p in report["curve"] if p["frequency_hz"] != 12.0e9
        ]
        assert all(report["worst_rcs_reduction_db"] > db for db in other_points_db)

    def test_default_threshold_only_fires_when_caller_is_silent(self):
        entries = [
            _tile_entry("0", phase_deg=180.0, frequencies_hz=self._FREQS),
            _tile_entry("1", phase_deg=0.0, frequencies_hz=self._FREQS),
        ]
        report = score_diffusive_checkerboard(
            entries,
            "checkerboard_ring_pair",
            self._FREQS,
            incidence_angle_deg=0.0,
            process_id=1,
            delta_phi_max_deg=0.0,
        )
        assert report["threshold_is_default"] is True
        assert report["threshold_db"] == DEFAULT_RCS_REDUCTION_THRESHOLD_DB

    def test_an_explicit_customer_threshold_always_overrides(self):
        entries = [
            _tile_entry("0", phase_deg=180.0, frequencies_hz=self._FREQS),
            _tile_entry("1", phase_deg=0.0, frequencies_hz=self._FREQS),
        ]
        report = score_diffusive_checkerboard(
            entries,
            "checkerboard_ring_pair",
            self._FREQS,
            incidence_angle_deg=0.0,
            process_id=1,
            delta_phi_max_deg=0.0,
            threshold_db=25.0,
        )
        assert report["threshold_is_default"] is False
        assert report["threshold_db"] == 25.0
        # An ideal pair (delta == 0 at every point) trivially beats even a
        # strict, explicit 25 dB requirement.
        assert report["meets_threshold"] is True

    def test_meets_threshold_is_false_when_the_worst_point_falls_short(self):
        entries = [
            _tile_entry("0", phase_deg=170.0, frequencies_hz=self._FREQS),
            _tile_entry("1", phase_deg=0.0, frequencies_hz=self._FREQS),
        ]
        # delta == 10 deg everywhere -> reduction_db == rcs_reduction_db(10)
        # ~= -20.6 dB, well inside a 10 dB guarantee...
        report = score_diffusive_checkerboard(
            entries,
            "checkerboard_ring_pair",
            self._FREQS,
            incidence_angle_deg=0.0,
            process_id=1,
            delta_phi_max_deg=0.0,
            threshold_db=25.0,
        )
        # ...but NOT a stricter, explicit 25 dB one.
        assert report["meets_threshold"] is False

    def test_provenance_is_the_weakest_seen_across_every_point(self):
        simulated_entry = _tile_entry("0", phase_deg=180.0, frequencies_hz=self._FREQS)
        simulated_entry["provenance"] = "SIMULATED"
        measured_entry = _tile_entry("1", phase_deg=0.0, frequencies_hz=self._FREQS)
        report = score_diffusive_checkerboard(
            [simulated_entry, measured_entry],
            "checkerboard_ring_pair",
            self._FREQS,
            incidence_angle_deg=0.0,
            process_id=1,
            delta_phi_max_deg=0.0,
        )
        assert report["provenance"] == "SIMULATED"

    def test_empty_frequency_points_is_rejected(self):
        entries = [
            _tile_entry("0", phase_deg=180.0, frequencies_hz=self._FREQS),
            _tile_entry("1", phase_deg=0.0, frequencies_hz=self._FREQS),
        ]
        with pytest.raises(ValueError, match="at least one frequency"):
            score_diffusive_checkerboard(
                entries,
                "checkerboard_ring_pair",
                (),
                incidence_angle_deg=0.0,
                process_id=1,
                delta_phi_max_deg=0.0,
            )


# ---------------------------------------------------------------------------
# diffracted_order_exists / diffracted_order_regime -- the D >= sqrt(2)*lambda
# precondition, at this project's own 10 GHz / 14 GHz band edges.
# ---------------------------------------------------------------------------


class TestDiffractedOrderRegime:
    _WAVELENGTH_10GHZ_M = SPEED_OF_LIGHT_M_S / 10.0e9
    _WAVELENGTH_14GHZ_M = SPEED_OF_LIGHT_M_S / 14.0e9

    def test_42_4mm_boundary_matches_10ghz(self):
        threshold_m = math.sqrt(2.0) * self._WAVELENGTH_10GHZ_M
        assert threshold_m == pytest.approx(0.0424, abs=1e-4)

    def test_30_3mm_boundary_matches_14ghz(self):
        threshold_m = math.sqrt(2.0) * self._WAVELENGTH_14GHZ_M
        assert threshold_m == pytest.approx(0.0303, abs=1e-4)

    def test_same_period_is_rozanov_bounded_at_10ghz_but_exempt_at_14ghz(self):
        # A 35 mm supercell period sits between the two band edges' onset
        # thresholds (42.4 mm at 10 GHz, 30.3 mm at 14 GHz): too small to
        # diffract at the bottom of the band, big enough at the top.
        tile_pitch_m = 0.0175  # supercell period = 2 * pitch = 35 mm

        at_10ghz = diffracted_order_regime(tile_pitch_m, self._WAVELENGTH_10GHZ_M)
        assert at_10ghz["diffracted_order_exists"] is False
        assert at_10ghz["bound_regime"] == "ROZANOV_BOUNDED"

        at_14ghz = diffracted_order_regime(tile_pitch_m, self._WAVELENGTH_14GHZ_M)
        assert at_14ghz["diffracted_order_exists"] is True
        assert at_14ghz["bound_regime"] == "NO_PHYSICAL_BOUND"

    def test_supercell_period_is_twice_the_tile_pitch(self):
        assert checkerboard_supercell_period_m(0.02) == pytest.approx(0.04)

    def test_exactly_at_the_boundary_counts_as_existing(self):
        wavelength_m = 0.01
        boundary_period_m = math.sqrt(2.0) * wavelength_m
        assert diffracted_order_exists(boundary_period_m, wavelength_m) is True


# ---------------------------------------------------------------------------
# materialize_checkerboard_unit_cell_array -- chains block_size_from_
# sizing_rule + generate_coded_unit_cell_array, no new geometry logic.
# ---------------------------------------------------------------------------


class TestMaterializeCheckerboardUnitCellArray:
    _SIZING = {
        "delta_phi_max_deg": 12.0,
        "rcsr_db": 10.0,
        "pitch_m": (0.015, 0.015),
        "wavelength_m": 0.03,
        "panel_size_m": (0.18, 0.18),
    }
    _SYMBOL_0 = {"shape": "box", "p1_m": [0.0, 0.0, 0.0], "p2_m": [0.005, 0.005, 0.001]}
    _SYMBOL_1 = {"shape": "box", "p1_m": [0.0, 0.0, 0.0], "p2_m": [0.006, 0.004, 0.001]}

    def test_matches_the_independently_computed_block_size(self):
        expected_block = block_size_from_sizing_rule(**self._SIZING)
        symbol_library = {"0": self._SYMBOL_0, "1": self._SYMBOL_1}

        result = materialize_checkerboard_unit_cell_array("0", "1", symbol_library, **self._SIZING)

        # 2x2 checkerboard blocks, each expected_block[0] x expected_block[1]
        # cells, one primitive per cell.
        expected_count = 2 * 2 * expected_block[0] * expected_block[1]
        assert len(result) == expected_count

    def test_the_array_actually_alternates_by_lattice_parity(self):
        symbol_library = {"0": self._SYMBOL_0, "1": self._SYMBOL_1}
        result = materialize_checkerboard_unit_cell_array("0", "1", symbol_library, **self._SIZING)
        by_name = {p["name"]: p for p in result}

        # Block (0, 0) -> symbol "0"'s own footprint (5mm square).
        block_0_0 = by_name["block_0_0_0_0"]
        assert block_0_0["p2_m"][0] - block_0_0["p1_m"][0] == pytest.approx(0.005)

        # Block (1, 0) -> symbol "1"'s own footprint (6mm x 4mm), a
        # DIFFERENT shape, confirming the (i + j) % 2 alternation actually
        # switched symbols rather than repeating the same one.
        block_1_0 = by_name["block_1_0_0_0"]
        assert block_1_0["p2_m"][0] - block_1_0["p1_m"][0] == pytest.approx(0.006)

        # Block (1, 1) -> back to symbol "0" (parity returns to even).
        block_1_1 = by_name["block_1_1_0_0"]
        assert block_1_1["p2_m"][0] - block_1_1["p1_m"][0] == pytest.approx(0.005)
