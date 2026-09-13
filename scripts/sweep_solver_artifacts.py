"""Issue #466's retention half of the durable solver working directory.

`simulation/base.py`'s `new_solver_workdir` gives every Palace/MEEP run a
directory under `solver_artifacts_root()` (by default, `solver_artifacts/`
inside this repository checkout) instead of the OS's own scratch area, so
that a run's mesh, config and output are still there when a later reader
-- a human re-opening a decision, or the planned Field bundle exporter
(#353/#356) -- goes looking. Nothing in that adapter code ever deletes one
of those directories: an adapter has no way to know whether the thing it
just wrote has been read yet, so it must never guess "probably not needed
anymore" on its own. "Durable" must not become "grows without bound"
either (#466's own acceptance criterion) -- this script is the deliberate,
out-of-band answer to that: run it by hand, or on a schedule (cron, a CI
job), never from inside a solver adapter or the design loop itself.

POLICY: a run directory is eligible for removal once its OWN modification
time (the directory entry's mtime, updated by the exporter that made it and
by every file written under it afterward -- Path.stat().st_mtime) is older
than `SOLVER_ARTIFACTS_RETENTION_DAYS` (simulation/base.py; 30 by default).
Age is measured from the directory's own mtime rather than from a parsed
run id, deliberately: it needs no format assumption about what any adapter
names its run directories, so a directory this script does not recognise is
still swept correctly rather than silently kept forever.

Defaults to a dry run -- printing what WOULD be removed and why, without
touching disk -- so it is safe to run experimentally on a shared host
before ever passing `--delete`.
"""

from __future__ import annotations

import argparse
import shutil
import time
from pathlib import Path

from simulation.base import SOLVER_ARTIFACTS_RETENTION_DAYS, solver_artifacts_root


def find_expired_solver_artifacts(
    root: Path, retention_days: float, now: float | None = None
) -> list[Path]:
    """Every immediate subdirectory of `root` whose own mtime is older than
    `retention_days` days, oldest first. `now` is injectable so a test can
    fix "the present" instead of racing the wall clock; production callers
    leave it as `None` and get `time.time()`."""
    if not root.is_dir():
        return []
    cutoff = (now if now is not None else time.time()) - retention_days * 86400
    expired = [
        entry for entry in root.iterdir() if entry.is_dir() and entry.stat().st_mtime < cutoff
    ]
    return sorted(expired, key=lambda entry: entry.stat().st_mtime)


def sweep(
    root: Path,
    retention_days: float,
    *,
    delete: bool,
    now: float | None = None,
) -> list[Path]:
    """Find and (only if `delete` is True) remove expired run directories
    under `root`, returning the list acted on either way -- a dry run
    (`delete=False`) reports exactly what a real run would have removed."""
    expired = find_expired_solver_artifacts(root, retention_days, now=now)
    if delete:
        for entry in expired:
            shutil.rmtree(entry, ignore_errors=True)
    return expired


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--retention-days",
        type=float,
        default=SOLVER_ARTIFACTS_RETENTION_DAYS,
        help=(
            "Age in days beyond which a run directory is swept "
            f"(default: {SOLVER_ARTIFACTS_RETENTION_DAYS})."
        ),
    )
    parser.add_argument(
        "--delete",
        action="store_true",
        help="Actually remove expired directories; otherwise only report what would be removed.",
    )
    args = parser.parse_args(argv)

    root = solver_artifacts_root()
    expired = sweep(root, args.retention_days, delete=args.delete)

    if not expired:
        print(f"No solver run directories under {root} are older than {args.retention_days} days.")
        return 0

    verb = "Removed" if args.delete else "Would remove (pass --delete to actually remove)"
    for entry in expired:
        print(f"{verb}: {entry}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
