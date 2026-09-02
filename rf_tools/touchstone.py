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
