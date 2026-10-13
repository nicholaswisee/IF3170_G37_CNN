"""Simulated annealing using the shared feasible neighbor and objective functions."""

import math
import random
from statistics import mean

from pydantic import BaseModel

from app.domain.problem import Problem
from app.domain.state import State
from app.optimization.algorithms.base import SearchAlgorithm, SearchResult
from app.optimization.constraints import validate_state
from app.optimization.neighbors import NeighborConfig, generate_random_neighbor
from app.optimization.objective import ObjectiveMode, evaluate_objective
from app.schemas.experiment import SimulatedAnnealingParameters


class SimulatedAnnealing(SearchAlgorithm):
    def __init__(self, neighbor_config: NeighborConfig | None = None) -> None:
        self.neighbor_config = neighbor_config or NeighborConfig()

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
        """Search from a feasible initial state without mutating the caller's state.

        The core returns final/best states and termination metadata. Per-iteration
        history, optional snapshots, and stuck metrics are added in the next stage.
        """
        if initial_state is None:
            raise ValueError(
                "Simulated annealing requires an initial state from the runner."
            )
        config = SimulatedAnnealingParameters.model_validate(parameters.model_dump())
        validity = validate_state(problem, initial_state)
        if not validity.valid:
            raise ValueError("Invalid initial state: " + "; ".join(validity.errors))

        temperature = config.initial_temperature
        if temperature is None:
            temperature = (
                max(mean(p.value for p in problem.packages), 1.0)
                if problem.packages
                else 1.0
            )

        current = initial_state.model_copy(deep=True)
        current_score = evaluate_objective(problem, current, objective_mode)
        best_state = current.model_copy(deep=True)
        best_score = current_score
        iterations = 0
        termination_reason = "max_iterations"

        for iteration in range(1, config.max_iterations + 1):
            if temperature < config.min_temperature:
                termination_reason = "temperature_minimum"
                break
            iterations = iteration
            candidate = generate_random_neighbor(
                problem, current, rng, self.neighbor_config
            )
            if candidate is None:
                termination_reason = "no_valid_neighbor"
                break

            candidate_score = evaluate_objective(
                problem, candidate.state, objective_mode
            )
            delta = candidate_score - current_score
            if delta >= 0 or rng.random() < math.exp(delta / temperature):
                current = candidate.state.model_copy(deep=True)
                current_score = candidate_score
                if current_score > best_score:
                    best_state = current.model_copy(deep=True)
                    best_score = current_score
            temperature *= config.alpha

        return SearchResult(
            final_state=current,
            best_state=best_state,
            final_score=current_score,
            best_score=best_score,
            iterations=iterations,
            history=[],
            metadata={
                "final_temperature": temperature,
                "termination_reason": termination_reason,
            },
        )
