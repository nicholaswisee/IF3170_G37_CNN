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
from app.schemas.experiment import SearchEvent, SimulatedAnnealingParameters


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
        """Search from a feasible initial state without mutating the caller's state."""
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
        stuck_events = 0
        iterations_without_improvement = 0
        stuck_latched = False
        history = [
            SearchEvent(
                iteration=0,
                current_score=current_score,
                best_score=best_score,
                temperature=temperature,
                state_snapshot=current.model_copy(deep=True)
                if include_state_history
                else None,
            )
        ]

        for iteration in range(1, config.max_iterations + 1):
            if temperature < config.min_temperature:
                termination_reason = "temperature_minimum"
                break
            iterations = iteration
            candidate = generate_random_neighbor(
                problem, current, rng, self.neighbor_config
            )
            candidate_score = None
            acceptance_probability = None
            accepted = False
            if candidate is not None:
                candidate_score = evaluate_objective(
                    problem, candidate.state, objective_mode
                )
                delta = candidate_score - current_score
                acceptance_probability = (
                    1.0 if delta >= 0 else math.exp(delta / temperature)
                )
                accepted = delta >= 0 or rng.random() < acceptance_probability
                if accepted:
                    current = candidate.state.model_copy(deep=True)
                    current_score = candidate_score

            if current_score > best_score:
                best_state = current.model_copy(deep=True)
                best_score = current_score
                iterations_without_improvement = 0
                stuck_latched = False
            else:
                iterations_without_improvement += 1
                if (
                    iterations_without_improvement >= config.stuck_patience
                    and not stuck_latched
                ):
                    stuck_events += 1
                    stuck_latched = True

            history.append(
                SearchEvent(
                    iteration=iteration,
                    current_score=current_score,
                    best_score=best_score,
                    candidate_score=candidate_score,
                    accepted=accepted,
                    move=candidate.move.model_copy(deep=True)
                    if candidate is not None
                    else None,
                    temperature=temperature,
                    acceptance_probability=acceptance_probability,
                    state_snapshot=current.model_copy(deep=True)
                    if include_state_history
                    else None,
                )
            )
            if candidate is None:
                termination_reason = "no_valid_neighbor"
                break
            temperature *= config.alpha

        return SearchResult(
            final_state=current,
            best_state=best_state,
            final_score=current_score,
            best_score=best_score,
            iterations=iterations,
            history=history,
            metadata={
                "stuck_events": stuck_events,
                "final_temperature": temperature,
                "termination_reason": termination_reason,
            },
        )
