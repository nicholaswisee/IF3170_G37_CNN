"""Placeholder boundary for the future simulated-annealing implementation."""

from app.domain.state import State
from app.optimization.algorithms.base import SearchAlgorithm
from app.schemas.experiment import ExperimentResult


class SimulatedAnnealing(SearchAlgorithm):
    def run(self, initial_state: State, **params: object) -> ExperimentResult:
        # TODO: Implement simulated annealing after objective and neighbors are defined.
        raise NotImplementedError("Simulated annealing not implemented yet.")
