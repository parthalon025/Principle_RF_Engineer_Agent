"""Issue #466: the durable, programme-owned working-directory helpers in
simulation/base.py that every full-wave adapter's default `workdir` now
resolves through, in place of `tempfile.mkdtemp`."""

from __future__ import annotations

from simulation.base import (
    new_solver_workdir,
    solver_artifacts_root,
    solver_workdir_is_durable,
)


def test_solver_artifacts_root_honours_env_override(monkeypatch, tmp_path):
    override = tmp_path / "custom_artifacts"
    monkeypatch.setenv("SOLVER_ARTIFACTS_DIR", str(override))
    assert solver_artifacts_root() == override


def test_new_solver_workdir_is_unique_and_under_the_root(monkeypatch, tmp_path):
    monkeypatch.setenv("SOLVER_ARTIFACTS_DIR", str(tmp_path))

    first = new_solver_workdir("palace")
    second = new_solver_workdir("palace")

    assert first != second
    assert first.parent == tmp_path
    assert first.name.startswith("palace_")
    # Issue #466's own AC: the root exists once a workdir is requested from
    # it, but the LEAF run directory itself is left to the adapter (which
    # already does `Path(workdir).mkdir(parents=True, exist_ok=True)`).
    assert tmp_path.is_dir()
    assert not first.exists()


def test_solver_workdir_is_durable_true_under_the_root(monkeypatch, tmp_path):
    monkeypatch.setenv("SOLVER_ARTIFACTS_DIR", str(tmp_path))
    workdir = new_solver_workdir("meep")
    assert solver_workdir_is_durable(workdir) is True


def test_solver_workdir_is_durable_false_outside_the_root(monkeypatch, tmp_path):
    monkeypatch.setenv("SOLVER_ARTIFACTS_DIR", str(tmp_path / "artifacts"))
    elsewhere = tmp_path / "not_the_artifacts_root" / "palace_run"
    assert solver_workdir_is_durable(elsewhere) is False


def test_solver_workdir_is_durable_false_for_unresolvable_path(monkeypatch, tmp_path):
    monkeypatch.setenv("SOLVER_ARTIFACTS_DIR", str(tmp_path))
    # A null byte is rejected by the OS on every path syscall Path.resolve()
    # touches -- this exercises the conservative "not durable" fallback for
    # any path that cannot be resolved at all.
    assert solver_workdir_is_durable("not\x00a\x00path") is False


def test_default_solver_artifacts_root_lives_under_the_repository(monkeypatch):
    monkeypatch.delenv("SOLVER_ARTIFACTS_DIR", raising=False)
    from simulation.base import DEFAULT_SOLVER_ARTIFACTS_ROOT, REPO_ROOT

    assert solver_artifacts_root() == DEFAULT_SOLVER_ARTIFACTS_ROOT
    assert DEFAULT_SOLVER_ARTIFACTS_ROOT == REPO_ROOT / "solver_artifacts"
    assert (REPO_ROOT / "pyproject.toml").is_file()
