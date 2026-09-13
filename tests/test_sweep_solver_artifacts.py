"""Issue #466's retention policy: scripts/sweep_solver_artifacts.py must
actually find and (only when told to) remove expired solver run
directories, and must never touch anything not old enough yet."""

from __future__ import annotations

import os
import time

from scripts.sweep_solver_artifacts import find_expired_solver_artifacts, sweep


def _make_run_dir(root, name, age_days):
    run_dir = root / name
    run_dir.mkdir(parents=True)
    (run_dir / "unit_cell.mesh").write_text("fake mesh")
    stale_time = time.time() - age_days * 86400
    os.utime(run_dir, (stale_time, stale_time))
    return run_dir


def test_find_expired_solver_artifacts_only_names_old_enough_directories(tmp_path):
    old_run = _make_run_dir(tmp_path, "palace_old", age_days=45)
    fresh_run = _make_run_dir(tmp_path, "palace_fresh", age_days=1)

    expired = find_expired_solver_artifacts(tmp_path, retention_days=30)

    assert expired == [old_run]
    assert fresh_run not in expired


def test_find_expired_solver_artifacts_on_missing_root_is_empty(tmp_path):
    missing = tmp_path / "does_not_exist"
    assert find_expired_solver_artifacts(missing, retention_days=30) == []


def test_sweep_dry_run_reports_but_does_not_delete(tmp_path):
    old_run = _make_run_dir(tmp_path, "palace_old", age_days=45)

    expired = sweep(tmp_path, retention_days=30, delete=False)

    assert expired == [old_run]
    assert old_run.exists()  # dry run: nothing was actually removed


def test_sweep_with_delete_removes_only_expired_directories(tmp_path):
    old_run = _make_run_dir(tmp_path, "palace_old", age_days=45)
    fresh_run = _make_run_dir(tmp_path, "palace_fresh", age_days=1)

    expired = sweep(tmp_path, retention_days=30, delete=True)

    assert expired == [old_run]
    assert not old_run.exists()
    assert fresh_run.exists()
