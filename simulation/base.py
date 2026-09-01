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
