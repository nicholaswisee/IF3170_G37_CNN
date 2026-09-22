"""Placeholder boundary for the future hill-climbing implementation."""

from app.domain.state import State
from app.optimization.algorithms.base import SearchAlgorithm
from app.schemas.experiment import ExperimentResult


class HillClimbing(SearchAlgorithm):
    def run(self, initial_state: State, **params: object) -> ExperimentResult:
        # TODO: Implement hill climbing after objective and neighbors are defined.
        raise NotImplementedError("Hill climbing not implemented yet.")
