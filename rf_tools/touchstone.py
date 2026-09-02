from collections.abc import Sequence
from pathlib import Path
from typing import Any

import numpy as np
import skrf as rf


def analyze_touchstone(path: str) -> dict[str, Any]:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(path)

    network = rf.Network(str(p))
    result: dict[str, Any] = {
        "file": str(p.resolve()),
        "ports": int(network.nports),
        "frequency_start_hz": float(network.f[0]),
        "frequency_stop_hz": float(network.f[-1]),
        "points": int(len(network.f)),
        "z0": np.asarray(network.z0).tolist(),
    }

    if network.nports >= 2:
        s11_db = 20 * np.log10(np.maximum(np.abs(network.s[:, 0, 0]), 1e-15))
        s21_db = 20 * np.log10(np.maximum(np.abs(network.s[:, 1, 0]), 1e-15))
        result["s11_min_db"] = float(np.min(s11_db))
        result["s21_max_db"] = float(np.max(s21_db))
        result["s11_min_frequency_hz"] = float(network.f[np.argmin(s11_db)])
        result["s21_max_frequency_hz"] = float(network.f[np.argmax(s21_db)])
    return result


def interpolate_touchstone(path: str, target_freqs_hz: Sequence[float]) -> rf.Network:
    """Interpolate a Touchstone network's S-parameters onto a new frequency grid.

    Loads the network at `path` and returns a new `skrf.Network` with its
    S-parameters interpolated onto `target_freqs_hz` (in Hz). Interpolation
    is done in polar coordinates (magnitude / unwrapped phase), which is
    exact for the common case of a matched, lossless network whose phase
    is linear in frequency, and is returned as an `skrf.Network` rather
    than summary statistics so downstream tools (cascading, comparison
    against another network) can operate on it directly.

    Every `target_freqs_hz` point must fall within the source network's
    original frequency range -- extrapolation is rejected with a
    `ValueError` rather than silently produced.
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(path)

    network = rf.Network(str(p))

    targets = np.asarray(target_freqs_hz, dtype=float)
    if targets.size == 0:
        raise ValueError("target_freqs_hz must contain at least one frequency")

    f_min = float(network.f[0])
    f_max = float(network.f[-1])
    out_of_range = targets[(targets < f_min) | (targets > f_max)]
    if out_of_range.size:
        raise ValueError(
            "target_freqs_hz contains frequencies outside the source "
            f"network's range [{f_min:g}, {f_max:g}] Hz (extrapolation is "
            f"not supported): {sorted(out_of_range.tolist())}"
        )

    return network.interpolate(targets, coords="polar", f_kwargs={"unit": "hz"})


def _load_network(path: str) -> rf.Network:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(path)
    return rf.Network(str(p))


def _invert_fixture(fixture: rf.Network, path: str) -> rf.Network:
    try:
        return fixture.inv
    except np.linalg.LinAlgError as exc:
        raise ValueError(
            f"fixture network at {path!r} is singular (non-invertible) at "
            "one or more frequency points -- a physical fixture must pass "
            "signal through (nonzero S21); check for S21 == 0 or another "
            "non-physical fixture response"
        ) from exc


def deembed_touchstone(
    measured_path: str,
    fixture_path: str,
    output_fixture_path: str | None = None,
) -> rf.Network:
    """De-embed a test fixture's effect from a measured Touchstone network.

    Recovers the device-under-test's (DUT's) true response from a raw
    measurement that includes a test fixture in the signal path, by
    undoing the network cascade that produced the measurement.

    With a single fixture (e.g. present only on the input side):
        `measured = fixture ** dut`
    so de-embedding is the inverse cascade:
        `dut = fixture.inv ** measured`

    With `output_fixture_path` also given (a fixture on each side --
    pass the same path as `fixture_path` for a symmetric fixture used
    on both sides):
        `measured = fixture ** dut ** output_fixture`
        `dut = fixture.inv ** measured ** output_fixture.inv`

    Uses skrf's own `Network.inv` (ABCD-matrix inverse per frequency
    point) and `**` (network cascade) rather than re-deriving ABCD-matrix
    inversion by hand.

    Raises `ValueError` if a fixture network is singular (non-invertible)
    at any frequency point -- e.g. a fixture with zero transmission
    (S21 == 0), which is non-physical for a fixture meant to pass a
    signal through to the DUT -- instead of letting a cryptic linear
    algebra error or silent NaN/inf propagate.
    """
    measured = _load_network(measured_path)
    fixture = _load_network(fixture_path)

    dut = _invert_fixture(fixture, fixture_path) ** measured

    if output_fixture_path is not None:
        output_fixture = _load_network(output_fixture_path)
        dut = dut ** _invert_fixture(output_fixture, output_fixture_path)

    return dut
