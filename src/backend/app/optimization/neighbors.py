"""Shared RELOCATE / ROTATE / SWAP neighbor engine for every search algorithm.

Two levels are exposed:

- ``propose_*`` and ``propose_random_move`` build one candidate without
  validating it, so GA mutation can feed the result into repair;
- ``generate_random_neighbor`` and ``sample_valid_neighbors`` return only
  candidates that pass the shared global validator (HC and SA).

Every function deep-copies the input state and never modifies it. All
randomness comes from the caller's seeded ``random.Random``.
"""

import math
import random
from collections.abc import Callable

from pydantic import BaseModel, Field, model_validator

from app.domain.move import Move, MoveType
from app.domain.package import (
    Orientation,
    get_oriented_dimensions,
    get_unique_orientations,
)
from app.domain.problem import Problem
from app.domain.state import State
from app.domain.truck import PackagePlacement, Position
from app.optimization.constraints import validate_state

type StateSignature = tuple[tuple[str, str, int, int, int, int], ...]
type Proposal = Callable[[Problem, State, random.Random], NeighborCandidate | None]


class NeighborConfig(BaseModel):
    relocate_probability: float = Field(default=0.50, ge=0, le=1)
    rotate_probability: float = Field(default=0.25, ge=0, le=1)
    swap_probability: float = Field(default=0.25, ge=0, le=1)
    max_attempts: int = Field(default=30, gt=0)

    @model_validator(mode="after")
    def validate_probabilities(self) -> "NeighborConfig":
        total = (
            self.relocate_probability + self.rotate_probability + self.swap_probability
        )
        if not math.isclose(total, 1.0):
            raise ValueError(f"move probabilities must sum to 1.0, got {total}")
        return self


class NeighborCandidate(BaseModel):
    state: State
    move: Move


def state_signature(state: State) -> StateSignature:
    """Order-independent key; outside placements use empty truck and -1 coords."""
    return tuple(
        sorted(
            (
                placement.package_id,
                placement.truck_id or "",
                *(
                    (placement.position.x, placement.position.y, placement.position.z)
                    if placement.position is not None
                    else (-1, -1, -1)
                ),
                int(placement.orientation),
            )
            for placement in state.placements
        )
    )


def sample_position(
    problem: Problem,
    state: State,
    rng: random.Random,
    package_id: str,
    truck_id: str,
    orientation: Orientation,
) -> Position | None:
    """Sample an in-bounds anchor for a package in a truck, or None if it cannot fit.

    x and y are uniform over the valid range. z is drawn from the truck floor
    plus the top surfaces of other packages already in that truck, which makes
    supported candidates likely without a packing heuristic. Feasibility is
    still decided by the validator.
    """
    packages = {package.id: package for package in problem.packages}
    truck = next(truck for truck in problem.trucks if truck.id == truck_id)
    width, length, height = get_oriented_dimensions(packages[package_id], orientation)
    if width > truck.width or length > truck.length or height > truck.height:
        return None

    levels = {0}
    for placement in state.placements:
        if (
            placement.truck_id == truck_id
            and placement.package_id != package_id
            and placement.position is not None
        ):
            other_height = get_oriented_dimensions(
                packages[placement.package_id], placement.orientation
            )[2]
            levels.add(placement.position.z + other_height)
    z_levels = sorted(z for z in levels if z + height <= truck.height)

    return Position(
        x=rng.randint(0, truck.width - width),
        y=rng.randint(0, truck.length - length),
        z=rng.choice(z_levels),
    )


def propose_relocate(
    problem: Problem, state: State, rng: random.Random
) -> NeighborCandidate | None:
    """Move one package to outside, a new coordinate, or another truck.

    Orientation is retained. Returns None when the sampled target cannot hold
    the package or the result would be identical to the current placement.
    """
    if not state.placements:
        return None
    index = rng.randrange(len(state.placements))
    placement = state.placements[index]

    targets: list[str | None] = [truck.id for truck in problem.trucks]
    if placement.truck_id is not None:
        targets.insert(0, None)
    target = rng.choice(targets)

    if target is None:
        moved = PackagePlacement(
            package_id=placement.package_id, orientation=placement.orientation
        )
    else:
        position = sample_position(
            problem, state, rng, placement.package_id, target, placement.orientation
        )
        if position is None or (
            target == placement.truck_id and position == placement.position
        ):
            return None
        moved = PackagePlacement(
            package_id=placement.package_id,
            truck_id=target,
            position=position,
            orientation=placement.orientation,
        )
    return _apply(state, MoveType.RELOCATE, {index: moved})


def propose_rotate(
    problem: Problem, state: State, rng: random.Random
) -> NeighborCandidate | None:
    """Give one loaded package a different effective shape at the same anchor.

    Outside packages are never selected. Returns None when nothing is loaded
    or the chosen package has no other distinct orientation (a cube).
    """
    loaded = [
        index
        for index, placement in enumerate(state.placements)
        if placement.truck_id is not None
    ]
    if not loaded:
        return None
    index = rng.choice(loaded)
    placement = state.placements[index]

    package = next(p for p in problem.packages if p.id == placement.package_id)
    current = get_oriented_dimensions(package, placement.orientation)
    options = [
        orientation
        for orientation in get_unique_orientations(package)
        if get_oriented_dimensions(package, orientation) != current
    ]
    if not options:
        return None
    rotated = placement.model_copy(update={"orientation": rng.choice(options)})
    return _apply(state, MoveType.ROTATE, {index: rotated})


def propose_swap(
    problem: Problem, state: State, rng: random.Random
) -> NeighborCandidate | None:
    """Exchange the truck assignment and anchor of two packages.

    Covers same-truck, cross-truck, and loaded-outside swaps; each package keeps
    its own orientation. Returns None when both chosen packages are outside.
    """
    if len(state.placements) < 2:
        return None
    first, second = rng.sample(range(len(state.placements)), 2)
    a, b = state.placements[first], state.placements[second]
    if a.truck_id is None and b.truck_id is None:
        return None
    return _apply(
        state,
        MoveType.SWAP,
        {
            first: PackagePlacement(
                package_id=a.package_id,
                truck_id=b.truck_id,
                position=b.position,
                orientation=a.orientation,
            ),
            second: PackagePlacement(
                package_id=b.package_id,
                truck_id=a.truck_id,
                position=a.position,
                orientation=b.orientation,
            ),
        },
    )


def propose_random_move(
    problem: Problem,
    state: State,
    rng: random.Random,
    config: NeighborConfig,
) -> NeighborCandidate | None:
    """Pick one move type by a seeded threshold and propose it, unvalidated."""
    threshold = rng.random()
    proposal: Proposal
    if threshold < config.relocate_probability:
        proposal = propose_relocate
    elif threshold < config.relocate_probability + config.rotate_probability:
        proposal = propose_rotate
    else:
        proposal = propose_swap
    return proposal(problem, state, rng)


def generate_random_neighbor(
    problem: Problem,
    state: State,
    rng: random.Random,
    config: NeighborConfig,
) -> NeighborCandidate | None:
    """Return one globally valid neighbor, or None after max_attempts proposals."""
    for _ in range(config.max_attempts):
        candidate = propose_random_move(problem, state, rng, config)
        if candidate is not None and validate_state(problem, candidate.state).valid:
            return candidate
    return None


def sample_valid_neighbors(
    problem: Problem,
    state: State,
    rng: random.Random,
    count: int,
    config: NeighborConfig,
) -> list[NeighborCandidate]:
    """Return up to count distinct valid neighbors, none equal to the input state.

    The proposal budget is count * max_attempts, so the call always terminates
    even when the neighborhood holds fewer than count valid states.
    """
    seen = {state_signature(state)}
    neighbors: list[NeighborCandidate] = []
    for _ in range(count * config.max_attempts):
        if len(neighbors) >= count:
            break
        candidate = propose_random_move(problem, state, rng, config)
        if candidate is None:
            continue
        signature = state_signature(candidate.state)
        if signature in seen:
            continue
        # Remember invalid signatures too so they are not revalidated.
        seen.add(signature)
        if validate_state(problem, candidate.state).valid:
            neighbors.append(candidate)
    return neighbors


def _apply(
    state: State, move_type: MoveType, changes: dict[int, PackagePlacement]
) -> NeighborCandidate:
    # Copy changed placements too: they may share Position objects with state.
    candidate = state.model_copy(deep=True)
    for index, placement in changes.items():
        candidate.placements[index] = placement.model_copy(deep=True)
    indices = list(changes)
    return NeighborCandidate(
        state=candidate,
        move=Move(
            type=move_type,
            package_ids=[state.placements[i].package_id for i in indices],
            before=[state.placements[i].model_copy(deep=True) for i in indices],
            after=[changes[i].model_copy(deep=True) for i in indices],
        ),
    )
