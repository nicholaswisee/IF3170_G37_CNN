"""Hill-Climbing family over the shared bounded sampled neighborhood.

One class dispatches by variant (freeze section 26). Every variant uses the
shared neighbor engine, validator, and objective evaluator. Only Sideways, the
mandatory default variant, is implemented so far.
"""

import random

from pydantic import BaseModel

from app.domain.problem import Problem
from app.domain.state import State
from app.optimization.algorithms.base import SearchAlgorithm, SearchResult
from app.optimization.neighbors import NeighborConfig, sample_valid_neighbors
from app.optimization.objective import ObjectiveMode, evaluate_objective
from app.schemas.experiment import (
    HillClimbingParameters,
    HillClimbingVariant,
    SearchEvent,
)


class HillClimbing(SearchAlgorithm):
    """The runner selects the variant here because the frozen run() has no variant."""

    def __init__(
        self,
        variant: HillClimbingVariant = HillClimbingVariant.SIDEWAYS,
        neighbor_config: NeighborConfig | None = None,
    ) -> None:
        self.variant = HillClimbingVariant(variant)
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
        if initial_state is None:
            raise ValueError("Hill climbing requires an initial state from the runner.")
        config = HillClimbingParameters.model_validate(parameters.model_dump())

        if self.variant is HillClimbingVariant.SIDEWAYS:
            return self._climb(
                problem,
                initial_state,
                objective_mode=objective_mode,
                rng=rng,
                config=config,
                max_sideways=config.max_sideways,
                include_state_history=include_state_history,
            )
        raise NotImplementedError(
            f"Hill climbing variant {self.variant.value} not implemented yet."
        )

    def _climb(
        self,
        problem: Problem,
        initial_state: State,
        *,
        objective_mode: ObjectiveMode,
        rng: random.Random,
        config: HillClimbingParameters,
        max_sideways: int,
        include_state_history: bool,
    ) -> SearchResult:
        """Move to a random equal-best sampled neighbor while it is not worse.

        Improvements are always taken and reset the consecutive sideways
        counter. Equal-best moves are taken while the counter is below
        max_sideways; zero disables them. History holds the initial state as
        iteration 0, then one event per iteration, including the final
        iteration that rejects every candidate.
        """
        current = initial_state.model_copy(deep=True)
        current_score = evaluate_objective(problem, current, objective_mode)
        best_state, best_score = current, current_score
        consecutive_sideways = 0
        sideways_moves = 0
        iterations = 0
        termination_reason = "max_iterations"
        history = [
            SearchEvent(
                iteration=0,
                current_score=current_score,
                best_score=best_score,
                state_snapshot=current if include_state_history else None,
            )
        ]

        for iteration in range(1, config.max_iterations + 1):
            iterations = iteration
            neighbors = sample_valid_neighbors(
                problem,
                current,
                rng,
                config.candidates_per_iteration,
                self.neighbor_config,
            )
            if not neighbors:
                termination_reason = "no_valid_neighbor"
                history.append(
                    SearchEvent(
                        iteration=iteration,
                        current_score=current_score,
                        best_score=best_score,
                        accepted=False,
                        state_snapshot=current if include_state_history else None,
                        metadata={"sampled_neighbors": 0},
                    )
                )
                break

            scores = [
                evaluate_objective(problem, neighbor.state, objective_mode)
                for neighbor in neighbors
            ]
            top_score = max(scores)
            improved = top_score > current_score
            sideways = (
                top_score == current_score and consecutive_sideways < max_sideways
            )
            if not (improved or sideways):
                if top_score == current_score and max_sideways > 0:
                    termination_reason = "max_sideways"
                else:
                    termination_reason = "local_optimum"
                history.append(
                    SearchEvent(
                        iteration=iteration,
                        current_score=current_score,
                        best_score=best_score,
                        candidate_score=top_score,
                        accepted=False,
                        state_snapshot=current if include_state_history else None,
                        metadata={"sampled_neighbors": len(neighbors)},
                    )
                )
                break

            selected = rng.choice(
                [n for n, score in zip(neighbors, scores) if score == top_score]
            )
            current, current_score = selected.state, top_score
            if improved:
                consecutive_sideways = 0
            else:
                consecutive_sideways += 1
                sideways_moves += 1
            if current_score > best_score:
                best_state, best_score = current, current_score

            history.append(
                SearchEvent(
                    iteration=iteration,
                    current_score=current_score,
                    best_score=best_score,
                    candidate_score=top_score,
                    accepted=True,
                    move=selected.move,
                    state_snapshot=current if include_state_history else None,
                    metadata={
                        "sampled_neighbors": len(neighbors),
                        "sideways": not improved,
                        "consecutive_sideways": consecutive_sideways,
                    },
                )
            )

        return SearchResult(
            final_state=current.model_copy(deep=True),
            best_state=best_state.model_copy(deep=True),
            final_score=current_score,
            best_score=best_score,
            iterations=iterations,
            history=history,
            metadata={
                "sideways_moves": sideways_moves,
                "termination_reason": termination_reason,
            },
        )
