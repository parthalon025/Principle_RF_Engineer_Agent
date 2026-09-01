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
