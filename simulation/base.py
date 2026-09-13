import os
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class SimulationResult:
    simulator: str
    status: str
    workdir: Path
    outputs: dict[str, Any]
    provenance: str = "SIMULATED"


class SimulatorError(RuntimeError):
    pass


class Simulator:
    name = "base"

    def run(self, job: dict[str, Any]) -> SimulationResult:
        raise NotImplementedError


# Issue #466: where a full-wave solver's working directory lives when the
# caller does not supply one. Before this, `run_palace_simulation` and
# `run_meep_simulation` each fell back to `tempfile.mkdtemp` -- the
# operating system's own scratch area, which the OS is free to sweep on
# reboot with no notice to this programme. Issue #345/#461 started
# recording that path on the decision so a later reader (the planned Field
# bundle exporter, #353/#356) could find the mesh, config and output a run
# left behind; a path under `tempfile.mkdtemp` makes that recording an
# eventual lie, not a fix. `REPO_ROOT` is this file's own grandparent
# directory rather than the process CWD, so this works the same whether
# the caller's CWD is the repo root (the common case) or not -- and inside
# the `app` container in docker-compose.yml, the whole repo is bind-mounted
# at /app (`.:/app`), so a directory created here is backed by the HOST
# filesystem and survives a container restart or rebuild with no separate
# Docker volume needed.
REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SOLVER_ARTIFACTS_ROOT = REPO_ROOT / "solver_artifacts"

# RETENTION POLICY (issue #466's own acceptance criterion: "durable" must
# not mean "grows without bound"). Nothing in this module, or in
# `run_palace_simulation`/`run_meep_simulation`, ever deletes a run
# directory: a bundle exporter that has not yet read one must never find it
# gone out from under it, and neither adapter can know whether that read has
# happened yet. Cleanup is instead a deliberate, out-of-band step:
# `scripts/sweep_solver_artifacts.py` removes run directories older than
# `SOLVER_ARTIFACTS_RETENTION_DAYS` days (default below), meant to be run
# periodically by a human or a schedule (cron, CI) -- never invoked from
# inside a solver adapter, where "how old is too old" is not yet knowable.
SOLVER_ARTIFACTS_RETENTION_DAYS = 30


def solver_artifacts_root() -> Path:
    """The directory solver run directories are created under by default.
    Overridable via the `SOLVER_ARTIFACTS_DIR` environment variable, for a
    deployment that wants runs on a different disk (a larger one, or one
    outside the bind-mounted repo tree). Not created here -- callers create
    their own run subdirectory (and, transitively, this root) via
    `new_solver_workdir` below."""
    override = os.environ.get("SOLVER_ARTIFACTS_DIR")
    return Path(override) if override else DEFAULT_SOLVER_ARTIFACTS_ROOT


def new_solver_workdir(solver_name: str) -> Path:
    """A fresh, durable working-directory path for one solver run:
    `<solver_artifacts_root()>/<solver_name>_<uuid4 hex>`. This is the
    default `workdir` every full-wave adapter that writes artifacts to disk
    (Palace, MEEP) uses when the caller supplies none, in place of
    `tempfile.mkdtemp`. The directory itself is not created here -- each
    adapter already does `Path(workdir).mkdir(parents=True, exist_ok=True)`
    once it has a path, durable or not, and creating it twice would only
    invite the two to drift.

    A caller that supplies its own `workdir` explicitly is untouched by
    this function entirely -- #345's tests, and any other caller with its
    own storage policy, keep working exactly as before."""
    root = solver_artifacts_root()
    root.mkdir(parents=True, exist_ok=True)
    return root / f"{solver_name}_{uuid.uuid4().hex}"


def solver_workdir_is_durable(workdir: str | Path) -> bool:
    """Whether `workdir` lives under `solver_artifacts_root()` -- i.e.
    whether it is a directory this programme's own retention policy
    governs, rather than one the OS (or an unrelated caller) may remove
    without notice. Used to decide whether a SIMULATION decision needs
    issue #466's non-durability warning at all: a run that used the
    default, durable workdir needs none, and firing on every run
    regardless (issue #345's original, blanket warning) is exactly what
    CLAUDE.md's charter rules out -- "a warning is only useful if it is
    rare and specific."

    Resolves both sides symlinks-and-all before comparing, so a `workdir`
    reached through a symlinked path is still recognised. Any path that
    fails to resolve (e.g. one naming a filesystem this process cannot
    stat) is conservatively treated as NOT durable -- the honest warning is
    the safe failure mode here, not silence."""
    try:
        return Path(workdir).resolve().is_relative_to(solver_artifacts_root().resolve())
    except (OSError, ValueError):
        return False
