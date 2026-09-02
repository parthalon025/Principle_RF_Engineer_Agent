import json
from pathlib import Path

import numpy as np
import pytest
import skrf as rf

from rf_tools.touchstone import analyze_touchstone


def test_touchstone(tmp_path: Path):
    f = rf.Frequency(1, 3, 3, unit="ghz")
    s = np.zeros((3, 2, 2), dtype=complex)
    s[:, 0, 0] = 10 ** (-20 / 20)
    s[:, 1, 0] = 10 ** (-3 / 20)
    ntwk = rf.Network(frequency=f, s=s, z0=50)
    path = tmp_path / "test.s2p"
    ntwk.write_touchstone(path.with_suffix(""))

    result = analyze_touchstone(str(path))
    assert result["ports"] == 2
    assert result["s11_min_db"] == pytest.approx(-20.0)


def test_touchstone_result_is_json_serializable(tmp_path: Path):
    # z0 is complex in general (lossy reference impedance); a bare `complex`
    # isn't JSON-serializable, and this result is written verbatim as an
    # `engineering_results.value` JSONB payload (ticket #19) -- so the whole
    # dict, z0 included, must round-trip through `json.dumps` cleanly.
    f = rf.Frequency(1, 3, 3, unit="ghz")
    s = np.zeros((3, 2, 2), dtype=complex)
    s[:, 0, 0] = 10 ** (-20 / 20)
    s[:, 1, 0] = 10 ** (-3 / 20)
    ntwk = rf.Network(frequency=f, s=s, z0=50)
    path = tmp_path / "test.s2p"
    ntwk.write_touchstone(path.with_suffix(""))

    result = analyze_touchstone(str(path))
    json.dumps(result)  # raises TypeError if anything isn't JSON-safe
    assert result["z0"][0][0] == pytest.approx([50.0, 0.0])
