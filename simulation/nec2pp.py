import os
import subprocess
from pathlib import Path

from .base import SimulationResult, Simulator, SimulatorError


class Nec2ppSimulator(Simulator):
    name = "NEC2++"

    def __init__(self, executable: str | None = None):
        self.executable = executable or os.getenv("NEC2PP_BIN", "nec2++")

    def run(self, job: dict) -> SimulationResult:
        input_file = Path(job["input_file"]).resolve()
        workdir = Path(job.get("workdir", input_file.parent)).resolve()
        if not input_file.exists():
            raise SimulatorError(f"Input file not found: {input_file}")

        completed = subprocess.run(
            [self.executable, str(input_file)],
            cwd=workdir,
            capture_output=True,
            text=True,
            timeout=int(job.get("timeout_s", 600)),
            check=False,
        )
        if completed.returncode != 0:
            raise SimulatorError(
                f"NEC2++ failed ({completed.returncode}): {completed.stderr[-4000:]}"
            )

        return SimulationResult(
            simulator=self.name,
            status="COMPLETED",
            workdir=workdir,
            outputs={"stdout": completed.stdout[-4000:]},
        )
