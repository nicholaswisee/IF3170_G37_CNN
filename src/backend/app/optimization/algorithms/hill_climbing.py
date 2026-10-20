import random

from pydantic import BaseModel

from app.domain.problem import Problem
from app.domain.state import State
from app.optimization.algorithms.base import SearchAlgorithm, SearchResult
from app.optimization.initializer import generate_random_feasible_state
from app.optimization.neighbors import (
    NeighborConfig,
    generate_random_neighbor,
    sample_valid_neighbors,
)
from app.optimization.objective import ObjectiveMode, evaluate_objective
from app.schemas.experiment import (
    HillClimbingParameters,
    HillClimbingVariant,
    SearchEvent,
)


class HillClimbing(SearchAlgorithm):
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

        if self.variant is HillClimbingVariant.RANDOM_RESTART:
            return self._random_restart(
                problem,
                initial_state,
                objective_mode=objective_mode,
                rng=rng,
                config=config,
                include_state_history=include_state_history,
            )
        return self._climb(
            problem,
            initial_state,
            variant=self.variant,
            objective_mode=objective_mode,
            rng=rng,
            config=config,
            include_state_history=include_state_history,
        )

    def _random_restart(
        self,
        problem: Problem,
        initial_state: State,
        *,
        objective_mode: ObjectiveMode,
        rng: random.Random,
        config: HillClimbingParameters,
        include_state_history: bool,
    ) -> SearchResult:
        climbs: list[SearchResult] = []
        history: list[SearchEvent] = []
        running_best = float("-inf")
        start = initial_state
        for restart in range(config.max_restarts + 1):
            if restart > 0:
                start = generate_random_feasible_state(problem, rng)
            climb = self._climb(
                problem,
                start,
                variant=HillClimbingVariant.STEEPEST_ASCENT,
                objective_mode=objective_mode,
                rng=rng,
                config=config,
                include_state_history=include_state_history,
            )
            climbs.append(climb)
            offset = history[-1].iteration + 1 if history else 0
            for event in climb.history:
                running_best = max(running_best, event.best_score)
                history.append(
                    event.model_copy(
                        update={
                            "iteration": event.iteration + offset,
                            "best_score": running_best,
                            "metadata": {**event.metadata, "restart": restart},
                        }
                    )
                )

        # max() keeps the earliest climb among equal best scores.
        best = max(climbs, key=lambda climb: climb.best_score)
        return SearchResult(
            final_state=climbs[-1].final_state,
            best_state=best.best_state,
            final_score=climbs[-1].final_score,
            best_score=best.best_score,
            iterations=sum(climb.iterations for climb in climbs),
            history=history,
            metadata={
                "restarts_performed": len(climbs) - 1,  # Banyak restart
                "iterations_per_restart": [
                    climb.iterations for climb in climbs
                ],  # Banyak iterasi per restart
                "best_score_per_restart": [climb.best_score for climb in climbs],
                "termination_reason": "max_restarts",
            },
        )

    def _climb(
        self,
        problem: Problem,
        initial_state: State,
        *,
        variant: HillClimbingVariant,
        objective_mode: ObjectiveMode,
        rng: random.Random,
        config: HillClimbingParameters,
        include_state_history: bool,
    ) -> SearchResult:
        """Run one local climb with the selected variant's neighbor policy.

        Steepest-Ascent and Sideways move to a random equal-best candidate;
        Sideways also accepts equal-score moves up to ``max_sideways``
        consecutive times. Stochastic evaluates one random neighbor per
        iteration and accepts it only when its score strictly improves.
        """
        is_sideways = variant is HillClimbingVariant.SIDEWAYS
        is_stochastic = variant is HillClimbingVariant.STOCHASTIC
        max_sideways = (
            config.max_sideways if is_sideways else 0
        )  # parameter max_sideways
        current = initial_state.model_copy(deep=True)
        current_score = evaluate_objective(problem, current, objective_mode)
        best_state, best_score = current, current_score
        consecutive_sideways = 0
        sideways_moves = 0
        iterations = 0  # Banyak iterasi hingga proses pencarian berhenti
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
            if is_stochastic:
                candidate = generate_random_neighbor(
                    problem, current, rng, self.neighbor_config
                )
                if candidate is None:
                    history.append(
                        SearchEvent(
                            iteration=iteration,
                            current_score=current_score,
                            best_score=best_score,
                            accepted=False,
                            state_snapshot=current if include_state_history else None,
                            metadata={
                                "sampled_neighbors": 0,
                                "improving_candidates": 0,
                            },
                        )
                    )
                    continue

                candidate_score = evaluate_objective(
                    problem, candidate.state, objective_mode
                )
                accepted = candidate_score > current_score
                if accepted:
                    current, current_score = candidate.state, candidate_score
                    if current_score > best_score:
                        best_state, best_score = current, current_score
                history.append(
                    SearchEvent(
                        iteration=iteration,
                        current_score=current_score,
                        best_score=best_score,
                        candidate_score=candidate_score,
                        accepted=accepted,
                        move=candidate.move,
                        state_snapshot=current if include_state_history else None,
                        metadata={
                            "sampled_neighbors": 1,
                            "improving_candidates": int(accepted),
                        },
                    )
                )
                continue

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
            if top_score > current_score or (
                top_score == current_score and consecutive_sideways < max_sideways
            ):
                pool = [
                    (n, score)
                    for n, score in zip(neighbors, scores)
                    if score == top_score
                ]
            else:
                pool = []
            if not pool:
                if top_score == current_score and max_sideways > 0:
                    termination_reason = "max_sideways"  # terminasi kalau udah lewat dari jumlah max sideways
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

            selected, selected_score = rng.choice(pool)
            improved = selected_score > current_score
            current, current_score = selected.state, selected_score
            if improved:
                consecutive_sideways = 0
            else:
                consecutive_sideways += 1
                sideways_moves += 1
            if current_score > best_score:
                best_state, best_score = current, current_score

            event_metadata: dict[str, object] = {"sampled_neighbors": len(neighbors)}
            if is_sideways:
                event_metadata["sideways"] = not improved
                event_metadata["consecutive_sideways"] = consecutive_sideways
            history.append(
                SearchEvent(
                    iteration=iteration,
                    current_score=current_score,
                    best_score=best_score,
                    candidate_score=selected_score,
                    accepted=True,
                    move=selected.move,
                    state_snapshot=current if include_state_history else None,
                    metadata=event_metadata,
                )
            )

        metadata: dict[str, object]
        if is_sideways:
            metadata = {
                "sideways_moves": sideways_moves,
                "termination_reason": termination_reason,
            }
        else:
            metadata = {
                "termination_reason": termination_reason,
                "sampled_neighbors": 1
                if is_stochastic
                else config.candidates_per_iteration,
            }
        return SearchResult(
            final_state=current.model_copy(deep=True),
            best_state=best_state.model_copy(deep=True),
            final_score=current_score,
            best_score=best_score,
            iterations=iterations,
            history=history,
            metadata=metadata,
        )
