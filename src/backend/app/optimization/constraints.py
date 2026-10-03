"""Fleet occupancy and the shared state-validation contract."""

import numpy as np
from pydantic import BaseModel

from app.domain.package import get_oriented_dimensions
from app.domain.problem import Problem
from app.domain.state import State


class ValidationResult(BaseModel):
    valid: bool
    errors: list[str]
    truck_weights: dict[str, float]


def build_occupancies(problem: Problem, state: State) -> dict[str, np.ndarray]:
    """Build fresh (width, length, height) grids keyed by truck ID.

    Empty cells contain -1; loaded cells contain the index in problem.packages.
    Outside packages occupy no cells. Inputs are never modified.

    Raise ValueError for incomplete/ambiguous assignments, unknown IDs,
    out-of-bounds placements, or overlaps instead of returning a misleading grid.
    Capacity, support, and fragile rules belong to validate_state.
    """
    package_indices = {
        package.id: index for index, package in enumerate(problem.packages)
    }
    placement_ids = [placement.package_id for placement in state.placements]
    if len(placement_ids) != len(set(placement_ids)):
        raise ValueError("Duplicate package placement IDs")
    if set(placement_ids) != set(package_indices):
        raise ValueError("State must contain exactly one placement for every package")

    occupancies = {
        truck.id: np.full((truck.width, truck.length, truck.height), -1, dtype=np.int32)
        for truck in problem.trucks
    }
    for placement in state.placements:
        truck_id, position = placement.truck_id, placement.position
        if (truck_id is None) != (position is None):
            raise ValueError(
                f"Inconsistent assignment for package {placement.package_id}"
            )
        if truck_id is None or position is None:
            continue
        if truck_id not in occupancies:
            raise ValueError(f"Unknown truck ID: {truck_id}")

        package_index = package_indices[placement.package_id]
        dimensions = get_oriented_dimensions(
            problem.packages[package_index], placement.orientation
        )
        origin = (position.x, position.y, position.z)
        grid = occupancies[truck_id]
        if any(
            start < 0 or start + size > limit
            for start, size, limit in zip(origin, dimensions, grid.shape, strict=True)
        ):
            raise ValueError(
                f"Package {placement.package_id} is out of bounds in truck {truck_id}"
            )

        region = tuple(
            slice(start, start + size)
            for start, size in zip(origin, dimensions, strict=True)
        )
        cells = grid[region]
        if np.any(cells != -1):
            raise ValueError(
                f"Package {placement.package_id} overlaps another in truck {truck_id}"
            )
        cells[...] = package_index

    return occupancies


def validate_state(problem: Problem, state: State) -> ValidationResult:
    """Validate a complete fleet state using the frozen global constraint rules."""
    raise NotImplementedError("Global constraint validation is not implemented yet.")
