from .base import SimulationResult, Simulator


class HfssSimulator(Simulator):
    name = "HFSS"

    def run(self, job: dict) -> SimulationResult:
        raise NotImplementedError(
            "HFSS adapter is disabled in the reference build. "
            "Implement with PyAEDT on an approved licensed host."
        )
