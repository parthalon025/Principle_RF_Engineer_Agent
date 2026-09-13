"""Tests for simulation/convergence.py (issue #540).

Pure-function tests only -- `convergence_report` takes a list of
`(knob, {field: value})` samples and returns a dict; no solver, no I/O, no
database. The parity tests reproduce
`prototype/mesh-convergence/mesh_convergence_prototype.py`'s own
`fake_solver` at its default `--pixels 6 12 24` and check the numbers
against the prototype's README table verbatim, to prove this module is a
faithful lift of the prototype's pure core, not a rewrite that drifted.
"""

from __future__ import annotations

import pytest

from simulation.convergence import convergence_report


def _fake_solver(pixels_across_sheet: float) -> dict[str, float]:
    """Copied from the prototype's own `fake_solver` (invented signature,
    R biased high / T biased low, both first-order in pixels-across-sheet).
    """
    bias = 1.0 / pixels_across_sheet
    reflectance = 0.25 + 0.95 * bias
    transmittance = 0.25 - 0.90 * bias
    return {
        "reflectance": reflectance,
        "transmittance": transmittance,
        "absorptance": 1.0 - reflectance - transmittance,
    }


class TestConvergenceReportParityWithThePrototype:
    """Reproduces the prototype README's own worked example: `--pixels 6 12
    24` through `fake_solver`, defaults otherwise. Every number below is
    quoted from prototype/mesh-convergence/README.md's table.
    """

    def setup_method(self) -> None:
        self.samples = [(k, _fake_solver(k)) for k in (6, 12, 24)]
        self.report = convergence_report(self.samples)

    def test_reflectance_matches_the_prototypes_documented_table(self) -> None:
        r = self.report["per_field"]["reflectance"]
        assert r["finest_value"] == pytest.approx(0.2896, abs=1e-4)
        assert r["error_bar"] == pytest.approx(0.0396, abs=1e-4)
        assert r["still_shrinking"] is True
        assert r["converged"] is False

    def test_transmittance_matches_the_prototypes_documented_table(self) -> None:
        t = self.report["per_field"]["transmittance"]
        assert t["finest_value"] == pytest.approx(0.2125, abs=1e-4)
        assert t["error_bar"] == pytest.approx(0.0375, abs=1e-4)
        assert t["still_shrinking"] is True
        assert t["converged"] is False

    def test_absorptance_matches_the_prototypes_documented_table(self) -> None:
        a = self.report["per_field"]["absorptance"]
        assert a["finest_value"] == pytest.approx(0.4979, abs=1e-4)
        assert a["error_bar"] == pytest.approx(0.0021, abs=1e-4)
        assert a["still_shrinking"] is True
        assert a["converged"] is True

    def test_recovers_the_split_is_not_converged_but_the_total_is(self) -> None:
        # docs/meep-absorber-validation.md's own finding, arrived at
        # mechanically instead of by a person reading the numbers.
        assert self.report["converged_fields"] == ["absorptance"]
        assert self.report["unconverged_fields"] == ["reflectance", "transmittance"]

    def test_claim_limit_names_the_unconverged_fields_and_not_absorptance(self) -> None:
        claim_limit = self.report["claim_limit"]
        assert "reflectance" in claim_limit
        assert "transmittance" in claim_limit
        assert "absorptance did settle" in claim_limit

    def test_provenance_note_states_discretisation_error_only(self) -> None:
        assert "DISCRETISATION error only" in self.report["provenance_note"]
        assert "converged wrong answer is still wrong" in self.report["provenance_note"]

    def test_knob_values_are_sorted_and_carried_through(self) -> None:
        assert self.report["knob_values"] == [6, 12, 24]


class TestConvergenceReportGeneralBehaviour:
    def test_a_monotonically_converging_sequence_is_reported_converged(self) -> None:
        samples = [
            (1.0, {"gain_dbi": 5.0}),
            (2.0, {"gain_dbi": 5.5}),
            (4.0, {"gain_dbi": 5.52}),
        ]
        report = convergence_report(samples, tolerance=0.05)
        gain = report["per_field"]["gain_dbi"]
        assert gain["successive_deltas"] == [pytest.approx(0.5), pytest.approx(0.02)]
        assert gain["still_shrinking"] is True
        assert gain["error_bar"] == pytest.approx(0.02)
        assert gain["converged"] is True
        assert report["converged_fields"] == ["gain_dbi"]
        assert report["unconverged_fields"] == []

    def test_a_still_moving_sequence_is_reported_unconverged(self) -> None:
        samples = [
            (1.0, {"return_loss_db": 10.0}),
            (2.0, {"return_loss_db": 10.5}),
            (4.0, {"return_loss_db": 11.3}),
        ]
        report = convergence_report(samples, tolerance=0.05)
        rl = report["per_field"]["return_loss_db"]
        # the movement is GROWING, not shrinking -- still worth reporting
        assert rl["successive_deltas"] == [pytest.approx(0.5), pytest.approx(0.8)]
        assert rl["still_shrinking"] is False
        assert rl["converged"] is False
        assert report["unconverged_fields"] == ["return_loss_db"]

    def test_a_field_present_in_only_one_sample_is_skipped_not_none(self) -> None:
        samples = [
            (1.0, {"shared": 1.0, "only_at_coarsest": 9.9}),
            (2.0, {"shared": 1.0}),
        ]
        report = convergence_report(samples)
        assert "only_at_coarsest" not in report["per_field"]
        assert "shared" in report["per_field"]

    def test_two_samples_give_a_movement_but_no_still_shrinking_verdict(self) -> None:
        samples = [(1.0, {"x": 1.0}), (2.0, {"x": 1.2})]
        report = convergence_report(samples)
        assert report["per_field"]["x"]["still_shrinking"] is None
        assert report["per_field"]["x"]["error_bar"] == pytest.approx(0.2)

    def test_fewer_than_two_samples_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="at least two"):
            convergence_report([(1.0, {"x": 1.0})])

    def test_samples_out_of_increasing_order_are_rejected(self) -> None:
        with pytest.raises(ValueError, match="increasing refinement order"):
            convergence_report([(2.0, {"x": 1.0}), (1.0, {"x": 1.1})])

    def test_a_zero_length_sample_list_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="at least two"):
            convergence_report([])
