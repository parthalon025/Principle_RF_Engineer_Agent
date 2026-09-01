from pathlib import Path
from typing import Any

import numpy as np
import skrf as rf


def analyze_touchstone(path: str) -> dict[str, Any]:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(path)

    network = rf.Network(str(p))
    # z0 (reference impedance) is complex in general (a lossy line's
    # characteristic impedance has a reactive part) -- a bare `complex`
    # isn't JSON-serializable, and this dict is returned as-is to callers
    # that do serialize it (ticket #19 writes it verbatim as an
    # `engineering_results.value` JSONB payload), so each entry is stored
    # as a JSON-safe [real, imag] pair rather than a Python complex.
    z0 = np.asarray(network.z0)
    result: dict[str, Any] = {
        "file": str(p.resolve()),
        "ports": int(network.nports),
        "frequency_start_hz": float(network.f[0]),
        "frequency_stop_hz": float(network.f[-1]),
        "points": int(len(network.f)),
        "z0": np.stack([z0.real, z0.imag], axis=-1).tolist(),
    }

    if network.nports >= 2:
        s11_db = 20 * np.log10(np.maximum(np.abs(network.s[:, 0, 0]), 1e-15))
        s21_db = 20 * np.log10(np.maximum(np.abs(network.s[:, 1, 0]), 1e-15))
        result["s11_min_db"] = float(np.min(s11_db))
        result["s21_max_db"] = float(np.max(s21_db))
        result["s11_min_frequency_hz"] = float(network.f[np.argmin(s11_db)])
        result["s21_max_frequency_hz"] = float(network.f[np.argmax(s21_db)])
    return result
