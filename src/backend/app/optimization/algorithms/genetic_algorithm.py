import random
from math import fsum

from pydantic import BaseModel

from app.domain.package import (
    PackageSpec,
    get_oriented_dimensions,
    get_unique_orientations,
)
from app.domain.problem import Problem
from app.domain.state import State
from app.domain.truck import PackagePlacement, Position, TruckSpec
from app.optimization.algorithms.base import SearchAlgorithm, SearchResult
from app.optimization.constraints import validate_state
from app.optimization.initializer import generate_random_feasible_state
from app.optimization.neighbors import (
    propose_relocate,
    propose_rotate,
    propose_swap,
)
from app.optimization.objective import ObjectiveMode, evaluate_objective
from app.schemas.experiment import GeneticAlgorithmParameters, SearchEvent


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


def uniform_crossover(
    problem: Problem, parent_a: State, parent_b: State, rng: random.Random
) -> State:
    by_id_a = {placement.package_id: placement for placement in parent_a.placements}
    by_id_b = {placement.package_id: placement for placement in parent_b.placements}
    return State(
        placements=[
            (by_id_a if rng.random() < 0.5 else by_id_b)[package.id].model_copy(
                deep=True
            )
            for package in problem.packages
        ]
    )


def repair_state(problem: Problem, candidate: State, rng: random.Random) -> State:
    repaired = State(
        placements=[
            PackagePlacement(package_id=package.id) for package in problem.packages
        ]
    )
    indices = {
        placement.package_id: i for i, placement in enumerate(repaired.placements)
    }
    packages = {package.id: package for package in problem.packages}
    trucks = {truck.id: truck for truck in problem.trucks}
    loaded = [
        placement
        for placement in candidate.placements
        if placement.truck_id is not None and placement.position is not None
    ]
    loaded.sort(
        key=lambda placement: (
            placement.position.z if placement.position is not None else -1,
            placement.package_id,
        )
    )

    for gene in loaded:
        assert gene.truck_id is not None and gene.position is not None
        package = packages[gene.package_id]
        requested_truck = trucks.get(gene.truck_id)
        if requested_truck is not None:
            exact = gene.model_copy(deep=True)
            if _try_placement(problem, repaired, indices[gene.package_id], exact):
                continue

        other_trucks = [truck for truck in problem.trucks if truck.id != gene.truck_id]
        rng.shuffle(other_trucks)
        for truck in ([requested_truck] if requested_truck else []) + other_trucks:
            if _scan_truck(
                problem, repaired, indices[gene.package_id], package, gene, truck, rng
            ):
                break

    result = validate_state(problem, repaired)
    if not result.valid:
        raise RuntimeError(
            "Repair produced an invalid state: " + "; ".join(result.errors)
        )
    return repaired


def _try_placement(
    problem: Problem, state: State, index: int, placement: PackagePlacement
) -> bool:
    trial = state.model_copy(deep=True)
    trial.placements[index] = placement.model_copy(deep=True)
    if not validate_state(problem, trial).valid:
        return False
    state.placements[index] = placement.model_copy(deep=True)
    return True


def _scan_truck(
    problem: Problem,
    state: State,
    index: int,
    package: PackageSpec,
    gene: PackagePlacement,
    truck: TruckSpec,
    rng: random.Random,
) -> bool:
    alternatives = [
        orientation
        for orientation in get_unique_orientations(package)
        if orientation != gene.orientation
    ]
    rng.shuffle(alternatives)
    orientations = [gene.orientation, *alternatives]
    for orientation in orientations:
        width, length, height = get_oriented_dimensions(package, orientation)
        if width > truck.width or length > truck.length or height > truck.height:
            continue
        for z in range(truck.height - height + 1):
            for y in range(truck.length - length + 1):
                for x in range(truck.width - width + 1):
                    placement = PackagePlacement(
                        package_id=gene.package_id,
                        truck_id=truck.id,
                        position=Position(x=x, y=y, z=z),
                        orientation=orientation,
                    )
                    if _try_placement(problem, state, index, placement):
                        return True
    return False


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
        fitnesses = [
            evaluate_objective(problem, state, objective_mode) for state in population
        ]
        champion, initial_score = max(
            zip(population, fitnesses, strict=True), key=lambda pair: pair[1]
        )
        initial_champion = champion.model_copy(deep=True)
        best_state = initial_champion.model_copy(deep=True)
        best_score = initial_score
        history: list[SearchEvent] = []

        for generation in range(config.generations + 1):
            champion, generation_max = max(
                zip(population, fitnesses, strict=True), key=lambda pair: pair[1]
            )
            if generation_max > best_score:
                best_state = champion.model_copy(deep=True)
                best_score = generation_max
            history.append(
                SearchEvent(
                    iteration=generation,
                    current_score=generation_max,
                    best_score=best_score,
                    mean_score=(
                        0.0
                        if (scale := max(fitnesses, default=0.0)) == 0
                        else scale
                        * (
                            fsum(fitness / scale for fitness in fitnesses)
                            / len(population)
                        )
                    ),
                    state_snapshot=champion.model_copy(deep=True)
                    if include_state_history
                    else None,
                )
            )
            if generation == config.generations:
                break
            next_population = [champion.model_copy(deep=True)]
            while len(next_population) < config.population_size:
                parent_a = roulette_select(population, fitnesses, rng)
                parent_b = roulette_select(population, fitnesses, rng)
                if rng.random() < config.crossover_probability:
                    child = uniform_crossover(problem, parent_a, parent_b, rng)
                else:
                    child = rng.choice((parent_a, parent_b)).model_copy(deep=True)
                if rng.random() < config.mutation_probability:
                    proposal = rng.choice(
                        (propose_relocate, propose_rotate, propose_swap)
                    )(problem, child, rng)
                    if proposal is not None:
                        child = proposal.state
                next_population.append(repair_state(problem, child, rng))
            population = next_population
            fitnesses = [
                evaluate_objective(problem, state, objective_mode)
                for state in population
            ]

        return SearchResult(
            final_state=champion.model_copy(deep=True),
            best_state=best_state.model_copy(deep=True),
            final_score=generation_max,
            best_score=best_score,
            iterations=config.generations,
            history=history,
            metadata={
                "population_size": config.population_size,
                "generations": config.generations,
                "termination_reason": "generation_limit",
                "initial_state": initial_champion.model_dump(mode="json"),
                "initial_score": initial_score,
            },
        )
