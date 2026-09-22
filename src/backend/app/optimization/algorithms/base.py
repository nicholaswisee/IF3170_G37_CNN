from abc import ABC, abstractmethod

from app.domain.state import State
from app.schemas.experiment import ExperimentResult


class SearchAlgorithm(ABC):
    @abstractmethod
    def run(self, initial_state: State, **params: object) -> ExperimentResult:
        raise NotImplementedError("Search algorithm not implemented yet.")
