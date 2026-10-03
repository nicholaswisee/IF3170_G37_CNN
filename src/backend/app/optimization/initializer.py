"""Seeded random feasible initial states shared by the search algorithms."""

import random

from app.domain.package import get_unique_orientations
from app.domain.problem import Problem
from app.domain.state import State
from app.domain.truck import PackagePlacement
from app.optimization.constraints import validate_state
from app.optimization.neighbors import sample_position


def generate_random_feasible_state(
    problem: Problem,
    rng: random.Random,
    max_attempts_per_target: int = 30,
) -> State:
    """Construct a feasible fleet state using only the supplied RNG.

    Encountering the outside target ends the search for that package. Each
    truck gets at most ``max_attempts_per_target`` coordinate proposals, cycling
    through its shuffled unique orientations. Non-fitting orientations also
    consume an attempt. Failed candidates never change the accepted state.
    """
    if max_attempts_per_target <= 0:
        raise ValueError("max_attempts_per_target must be positive")

    state = State(
        placements=[PackagePlacement(package_id=p.id) for p in problem.packages]
    )
    indices = list(range(len(problem.packages)))
    rng.shuffle(indices)

    for index in indices:
        package = problem.packages[index]
        targets: list[str | None] = [None] + [truck.id for truck in problem.trucks]
        rng.shuffle(targets)
        for truck_id in targets:
            if truck_id is None:
                break
            orientations = get_unique_orientations(package)
            rng.shuffle(orientations)
            for attempt in range(max_attempts_per_target):
                orientation = orientations[attempt % len(orientations)]
                position = sample_position(
                    problem, state, rng, package.id, truck_id, orientation
                )
                if position is None:
                    continue
                candidate = state.model_copy(deep=True)
                candidate.placements[index] = PackagePlacement(
                    package_id=package.id,
                    truck_id=truck_id,
                    position=position,
                    orientation=orientation,
                )
                if validate_state(problem, candidate).valid:
                    state = candidate
                    break
            if state.placements[index].truck_id is not None:
                break

    result = validate_state(problem, state)
    if not result.valid:
        raise RuntimeError(
            "Initializer produced an invalid state: " + "; ".join(result.errors)
        )
    return state
