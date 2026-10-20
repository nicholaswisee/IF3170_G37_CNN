import random
from math import fsum

from pydantic import BaseModel

from app.domain.problem import Problem
from app.domain.state import State
from app.optimization.algorithms.base import SearchAlgorithm, SearchResult
from app.optimization.constraints import validate_state
from app.optimization.initializer import generate_random_feasible_state
from app.optimization.neighbors import propose_relocate
from app.optimization.objective import (
    ObjectiveMode,
    evaluate_objective,
    objective_upper_bound,
)
from app.schemas.experiment import GeneticAlgorithmParameters, SearchEvent


def _penalized_fitness(
    raw_score: float, upper_bound: float, violation_count: int
) -> float:
    q = min(1.0, max(0.0, raw_score / upper_bound)) if upper_bound > 0 else 0.0
    return 1.0 + q if violation_count == 0 else q / (1 + violation_count)


def roulette_select(
    population: list[State], fitnesses: list[float], rng: random.Random
) -> State:
    scale = max(fitnesses, default=0)
    if scale <= 0:
        return rng.choice(population)
    weights = [fitness / scale for fitness in fitnesses]
    total = fsum(weights)
    threshold = rng.random() * total
    cumulative = 0.0
    for state, weight in zip(population, weights, strict=True):
        cumulative += weight
        if threshold < cumulative:
            return state
    return next(
        state
        for state, fitness in zip(
            reversed(population), reversed(fitnesses), strict=True
        )
        if fitness > 0
    )


def single_point_crossover(
    problem: Problem, parent_a: State, parent_b: State, rng: random.Random
) -> State:
    by_id_a = {placement.package_id: placement for placement in parent_a.placements}
    by_id_b = {placement.package_id: placement for placement in parent_b.placements}
    count = len(problem.packages)
    cut = rng.randrange(1, count) if count > 1 else count
    source_a = rng.random() < 0.5
    return State(
        placements=[
            (by_id_a if (index < cut) == source_a else by_id_b)[package.id].model_copy(
                deep=True
            )
            for index, package in enumerate(problem.packages)
        ]
    )


class GeneticAlgorithm(SearchAlgorithm):
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
        config = GeneticAlgorithmParameters.model_validate(parameters.model_dump())
        if config.elite_count != 0:
            raise ValueError("elite_count must be 0")
        if (
            initial_state is not None
            and not validate_state(problem, initial_state).valid
        ):
            raise ValueError("initial_state is invalid")
        population = (
            [initial_state.model_copy(deep=True)] if initial_state is not None else []
        )
        population.extend(
            generate_random_feasible_state(problem, rng)
            for _ in range(config.population_size - len(population))
        )
        upper_bound = objective_upper_bound(problem, objective_mode)
        best_state = max(
            population,
            key=lambda state: evaluate_objective(problem, state, objective_mode),
        ).model_copy(deep=True)
        initial_state = best_state.model_copy(deep=True)
        initial_score = evaluate_objective(problem, initial_state, objective_mode)
        best_score = initial_score
        history: list[SearchEvent] = []
        final_fallback = False
        for generation in range(config.generations + 1):
            validated = [validate_state(problem, state) for state in population]
            raw_scores = [
                evaluate_objective(problem, state, objective_mode)
                for state in population
            ]
            fitnesses = [
                _penalized_fitness(score, upper_bound, len(validation.errors))
                for score, validation in zip(raw_scores, validated, strict=True)
            ]
            feasible = [i for i, validation in enumerate(validated) if validation.valid]
            if feasible:
                current_index = max(feasible, key=lambda i: raw_scores[i])
                current_state = population[current_index]
                current_score = raw_scores[current_index]
                if current_score > best_score:
                    best_state = current_state.model_copy(deep=True)
                    best_score = current_score
                fallback = False
            else:
                current_state, current_score, fallback = best_state, best_score, True
            history.append(
                SearchEvent(
                    iteration=generation,
                    current_score=current_score,
                    best_score=best_score,
                    mean_score=fsum(fitnesses) / len(fitnesses),
                    state_snapshot=current_state.model_copy(deep=True)
                    if include_state_history
                    else None,
                    metadata={
                        "max_fitness": max(fitnesses),
                        "infeasible_count": len(population) - len(feasible),
                        "feasible_fallback": fallback,
                    },
                )
            )
            if generation == config.generations:
                final_fallback = not bool(feasible)
                final_state = current_state
                final_score = current_score
                break
            next_population: list[State] = []
            for _ in range(config.population_size):
                a = roulette_select(population, fitnesses, rng)
                b = roulette_select(population, fitnesses, rng)
                child = (
                    single_point_crossover(problem, a, b, rng)
                    if rng.random() < config.crossover_probability
                    else rng.choice((a, b)).model_copy(deep=True)
                )
                if rng.random() < config.mutation_probability:
                    proposal = propose_relocate(problem, child, rng)
                    if proposal is not None:
                        child = proposal.state
                next_population.append(child)
            population = next_population
        return SearchResult(
            final_state=final_state.model_copy(deep=True),
            best_state=best_state.model_copy(deep=True),
            final_score=final_score,
            best_score=best_score,
            iterations=config.generations,
            history=history,
            metadata={
                "population_size": config.population_size,
                "generations": config.generations,
                "termination_reason": "generation_limit",
                "initial_state": initial_state.model_dump(mode="json"),
                "initial_score": initial_score,
                "final_state_fallback": final_fallback,
            },
        )
