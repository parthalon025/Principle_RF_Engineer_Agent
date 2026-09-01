import os
import subprocess
from pathlib import Path

from .base import SimulationResult, Simulator, SimulatorError


class OpenEMSSimulator(Simulator):
    name = "openEMS"

    def __init__(self, executable: str | None = None):
        self.executable = executable or os.getenv("OPENEMS_BIN", "openEMS")

    def run(self, job: dict) -> SimulationResult:
        script = Path(job["script"]).resolve()
        workdir = Path(job.get("workdir", script.parent)).resolve()
        if not script.exists():
            raise SimulatorError(f"openEMS script not found: {script}")

        completed = subprocess.run(
            [self.executable, str(script)],
            cwd=workdir,
            capture_output=True,
            text=True,
            timeout=int(job.get("timeout_s", 3600)),
            check=False,
        )
        if completed.returncode != 0:
            raise SimulatorError(
                f"openEMS failed ({completed.returncode}): {completed.stderr[-4000:]}"
            )

        return SimulationResult(
            simulator=self.name,
            status="COMPLETED",
            workdir=workdir,
            outputs={"stdout": completed.stdout[-4000:]},
        )
