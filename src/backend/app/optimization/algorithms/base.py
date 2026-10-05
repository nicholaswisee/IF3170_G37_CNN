import random
from abc import ABC, abstractmethod

from pydantic import BaseModel, ConfigDict, Field

from app.domain.problem import Problem
from app.domain.state import State
from app.optimization.objective import ObjectiveMode
from app.schemas.common import Metadata
from app.schemas.experiment import SearchEvent


class SearchResult(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)

    final_state: State
    best_state: State
    final_score: float
    best_score: float
    iterations: int
    history: list[SearchEvent]
    metadata: Metadata = Field(default_factory=dict)


class SearchAlgorithm(ABC):
    """HC/SA receive an initial state; GA may receive None to create its population.

    The caller owns seeded RNG creation, timing, result wrapping, and persistence.
    """

    @abstractmethod
    def run(
        self,
        problem: Problem,
        initial_state: State | None,
        *,
        objective_mode: ObjectiveMode,
        rng: random.Random,
        parameters: BaseModel,
        include_state_history: bool,
    ) -> SearchResult:
        raise NotImplementedError("Search algorithm not implemented yet.")
