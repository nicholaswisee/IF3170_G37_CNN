"""Placeholder boundary for the future genetic-algorithm implementation."""

from app.domain.state import State
from app.optimization.algorithms.base import SearchAlgorithm
from app.schemas.experiment import ExperimentResult


class GeneticAlgorithm(SearchAlgorithm):
    def run(self, initial_state: State, **params: object) -> ExperimentResult:
        # TODO: Implement a genetic algorithm after the model is finalized.
        raise NotImplementedError("Genetic algorithm not implemented yet.")
