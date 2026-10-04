"""Placeholder boundary for the future hill-climbing implementation."""

import random

from pydantic import BaseModel

from app.domain.problem import Problem
from app.domain.state import State
from app.optimization.algorithms.base import SearchAlgorithm, SearchResult
from app.optimization.objective import ObjectiveMode


class HillClimbing(SearchAlgorithm):
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
        raise NotImplementedError("Hill climbing not implemented yet.")
