"""Issue #346: the plus/minus-90-degree in-phase reflection band -- the
bandwidth figure this programme's central claim (a magnetic-mirror surface,
CLAUDE.md's "The problem, physically") actually rests on.

WHAT THE NUMBER MEANS, PHYSICALLY. Ordinary metal reflects with a 180
degree phase flip; a surface engineered to reflect near 0 degrees instead
behaves as a magnetic mirror rather than a metal one. That 0 degree point
is a single frequency, not a band -- Sievenpiper's own artificial magnetic
conductor literature (the standard reference for this behaviour) defines
its usable bandwidth as the frequency range around that zero crossing over
which the reflection phase stays within +/-90 degrees of it, since a
quarter-wave-standoff antenna's classical cancellation problem (CLAUDE.md's
opening paragraph) is only meaningfully solved while the surface is closer
to "in phase" than to "out of phase" with the incident wave. Palace
(`simulation/palace.py`) already returns this phase, per Floquet mode, as
part of `s_parameters["specular"]`; nothing before this module turned that
phase curve into the one number a reader actually wants.

WHY UNWRAPPING MATTERS. A solver reports phase as a principal value in
(-180, 180] degrees at each swept frequency. A real AMC resonance sweeps
phase continuously from near +180 (metal-like, below resonance) down
through 0 (the magnetic-mirror point) to near -180 (metal-like again,
above resonance) -- and IF the raw samples ever fall on opposite sides of
the +/-180 seam (e.g. one sample at +179, the next at -179 -- a difference
of 2 degrees physically, reported as a jump of 358), naively interpolating
between the raw principal values would manufacture a false crossing or
miss a real one. `numpy.unwrap` removes exactly that artifact by adding/
subtracting whole turns wherever consecutive samples jump by more than
180 degrees, leaving one continuous curve to search for the true zero and
+/-90 degree crossings on.

WHY "NEVER CROSSES ZERO" MUST RETURN NO BAND, NOT A WRONG ONE (issue
#346 AC 3). This module's whole definition is "the region around the
zero-phase crossing." A candidate whose swept phase stays entirely on one
side of zero (e.g. a badly-detuned cell that never gets closer than 150
degrees to the magnetic-mirror point) has no such region to report --
returning `None` says exactly that, rather than fabricating a band from
whatever the +/-90 degree thresholds happen to bracket in a curve that was
never near an actual resonance.

ASSUMPTION THIS MODULE MAKES EXPLICIT (single-resonance sweep). A cell
with more than one zero-phase crossing in the swept range (a
multi-resonant or highly dispersive design) has more than one candidate
band; this module reports the band around the FIRST zero crossing found
(ascending frequency) and says so in its `validity` entry -- it does not
guess which crossing the caller actually wanted."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import numpy as np


def _threshold_crossings(
    frequency_hz: np.ndarray, phase_deg: np.ndarray, threshold_deg: float
) -> list[float]:
    """Every frequency (linearly interpolated between the bracketing
    samples) at which the unwrapped `phase_deg` curve equals
    `threshold_deg`, ascending. Assumes `frequency_hz` is already sorted
    ascending -- callers here always pre-sort once, rather than each
    threshold search re-sorting the same arrays."""
    crossings: list[float] = []
    shifted = phase_deg - threshold_deg
    for i in range(len(frequency_hz) - 1):
        left, right = shifted[i], shifted[i + 1]
        if left == 0.0:
            crossings.append(float(frequency_hz[i]))
        # `right != 0.0` guards against double-counting: a `right` that is
        # exactly on the threshold is this same physical crossing, and is
        # counted once already -- either by the NEXT iteration's own
        # `left == 0.0` branch (if it is an interior point) or by the
        # explicit last-point check below (if it is the final sample).
        # Treating an exact-zero `right` as merely "not > 0" here (the
        # naive `(left > 0) != (right > 0)` test) would count it twice.
        elif right != 0.0 and (left > 0) != (right > 0):
            fraction = -left / (right - left)
            span = frequency_hz[i + 1] - frequency_hz[i]
            crossings.append(float(frequency_hz[i] + fraction * span))
    if shifted[-1] == 0.0:
        crossings.append(float(frequency_hz[-1]))
    return crossings


def in_phase_reflection_band(
    frequency_hz: Sequence[float],
    reflection_phase_deg: Sequence[float],
) -> dict[str, Any] | None:
    """The +/-90 degree in-phase reflection band around the first
    zero-phase crossing in `reflection_phase_deg`, swept over
    `frequency_hz` (any order; sorted internally). Returns `None` --
    deliberately, per issue #346 AC 3 -- when the phase never crosses zero
    at all.

    Otherwise returns:
        {
            "center_frequency_hz": the zero-phase crossing frequency,
            "low_hz" / "high_hz": the band edges, each either an
                interpolated +/-90 degree crossing or, if the true edge
                lies outside the swept range, the nearest swept frequency
                (flagged in "validity" -- see below),
            "bandwidth_hz": high_hz - low_hz,
            "fractional_bandwidth_percent": 100 * bandwidth_hz /
                center_frequency_hz,
            "validity": a list of charter-shaped warnings (empty when
                none apply) -- at most two possible entries here:
                "band_edge_outside_swept_range" (one or both of low_hz/
                high_hz is the sweep's own edge, not a true +/-90 degree
                crossing -- the real edge could lie further out) and
                "multiple_zero_crossings_first_used" (see this module's
                docstring's single-resonance assumption).
        }

    Requires at least two frequency samples (a single point cannot define
    a crossing); raises ValueError on mismatched-length inputs, the same
    "fail loud on a caller mistake" discipline as this project's other
    rf_tools functions."""
    if len(frequency_hz) != len(reflection_phase_deg):
        raise ValueError(
            f"frequency_hz ({len(frequency_hz)} values) and reflection_phase_deg "
            f"({len(reflection_phase_deg)} values) must be the same length"
        )
    if len(frequency_hz) < 2:
        return None

    order = np.argsort(np.asarray(frequency_hz, dtype=float))
    freqs = np.asarray(frequency_hz, dtype=float)[order]
    phase_deg_unwrapped = np.rad2deg(
        np.unwrap(np.deg2rad(np.asarray(reflection_phase_deg, dtype=float)[order]))
    )

    zero_crossings = _threshold_crossings(freqs, phase_deg_unwrapped, 0.0)
    if not zero_crossings:
        return None
    center_frequency_hz = zero_crossings[0]

    validity: list[dict[str, str]] = []
    if len(zero_crossings) > 1:
        validity.append(
            {
                "flag": "multiple_zero_crossings_first_used",
                "assumed": (
                    f"the phase crosses zero {len(zero_crossings)} times in the swept "
                    f"range; the band reported is centred on the first ({center_frequency_hz:.6g} "
                    "Hz), ascending frequency"
                ),
                "costs": (
                    "a multi-resonant or highly dispersive design has more than one "
                    "candidate in-phase band, and this result names only one of them"
                ),
                "cheapest_test": (
                    "call in_phase_reflection_band again on the sub-range around each "
                    "other zero crossing"
                ),
            }
        )

    plus_90 = [
        f
        for f in _threshold_crossings(freqs, phase_deg_unwrapped, 90.0)
        if f <= center_frequency_hz
    ]
    minus_90 = [
        f
        for f in _threshold_crossings(freqs, phase_deg_unwrapped, -90.0)
        if f >= center_frequency_hz
    ]

    edge_outside_range = not plus_90 or not minus_90
    low_hz = max(plus_90) if plus_90 else float(freqs[0])
    high_hz = min(minus_90) if minus_90 else float(freqs[-1])
    if edge_outside_range:
        validity.append(
            {
                "flag": "band_edge_outside_swept_range",
                "assumed": (
                    f"the true +/-90 degree crossing lies at or beyond the swept range "
                    f"({freqs[0]:.6g}-{freqs[-1]:.6g} Hz) on at least one side"
                ),
                "costs": (
                    "the reported bandwidth is a lower bound, not the true bandwidth -- "
                    "the real in-phase band may be wider than this result states"
                ),
                "cheapest_test": "widen the frequency sweep past the reported edge and re-run",
            }
        )

    return {
        "center_frequency_hz": center_frequency_hz,
        "low_hz": low_hz,
        "high_hz": high_hz,
        "bandwidth_hz": high_hz - low_hz,
        "fractional_bandwidth_percent": 100.0 * (high_hz - low_hz) / center_frequency_hz,
        "validity": validity,
    }


def in_phase_reflection_bands(
    frequency_hz: Sequence[float],
    specular: dict[str, Sequence[complex]],
    provenance: str = "SIMULATED",
) -> dict[str, Any]:
    """`in_phase_reflection_band`, per Floquet mode (issue #346 AC 1) --
    `specular` is Palace's own per-mode complex-S11 shape
    (`simulation.palace.run_palace_simulation`'s `s_parameters["specular"]`,
    e.g. `{"S11_TE": [complex, ...]}`), so a caller with a raw Palace
    result needs no separate phase-extraction step. `provenance` (default
    "SIMULATED", matching this project's own SIMULATED-by-default solver
    results) rides on the returned dict per issue #346 AC 4 -- this is a
    deterministic reading of a solver's own already-recorded phase, so it
    inherits that phase's provenance rather than manufacturing a new one;
    a caller reading a MEASURED phase in future passes provenance="MEASURED"
    accordingly.

    Returns `{"bands": {mode_label: <in_phase_reflection_band result, or
    None>, ...}, "provenance": provenance}`."""
    bands = {
        mode_label: in_phase_reflection_band(
            frequency_hz, [float(np.angle(value, deg=True)) for value in values]
        )
        for mode_label, values in specular.items()
    }
    return {"bands": bands, "provenance": provenance}
