"""Fleet occupancy and the shared state-validation contract."""

from collections import Counter
from decimal import Decimal

import numpy as np
from pydantic import BaseModel

from app.domain.package import get_oriented_dimensions
from app.domain.problem import Problem
from app.domain.state import State
from app.domain.truck import PackagePlacement


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
    loaded, errors = _check_assignments(problem, state)
    if errors:
        raise ValueError("; ".join(errors))
    occupancies, errors, _ = _collect_occupancies(problem, loaded)
    if errors:
        raise ValueError("; ".join(errors))
    return occupancies


def _check_assignments(
    problem: Problem, state: State
) -> tuple[list[PackagePlacement], list[str]]:
    """Return unambiguous loaded placements in problem order and structural errors."""
    package_indices = {package.id: i for i, package in enumerate(problem.packages)}
    truck_ids = {truck.id for truck in problem.trucks}
    counts = Counter(placement.package_id for placement in state.placements)

    # error validation
    errors = [
        f"Missing placement for package {package.id}"
        for package in problem.packages
        if counts[package.id] == 0
    ]
    errors.extend(
        f"Unknown package ID: {id_}"
        for id_ in sorted(counts.keys() - package_indices.keys())
    )
    errors.extend(
        f"Duplicate package placement ID: {id_}"
        for id_ in sorted(counts)
        if counts[id_] > 1
    )

    candidates = sorted(
        (
            placement
            for placement in state.placements
            if placement.package_id in package_indices
            and counts[placement.package_id] == 1
        ),
        key=lambda placement: package_indices[placement.package_id],
    )

    consistent = []
    for placement in candidates:
        if (placement.truck_id is None) != (placement.position is None):
            errors.append(f"Inconsistent assignment for package {placement.package_id}")
        elif placement.truck_id is not None:
            consistent.append(placement)

    loaded = []
    for placement in consistent:
        if placement.truck_id not in truck_ids:
            errors.append(f"Unknown truck ID: {placement.truck_id}")
        else:
            loaded.append(placement)
    return loaded, errors


def _collect_occupancies(
    problem: Problem, loaded: list[PackagePlacement]
) -> tuple[dict[str, np.ndarray], list[str], set[str]]:
    """Collect boundary/overlap errors; mark trucks unsafe for support checks."""

    package_indices = {package.id: i for i, package in enumerate(problem.packages)}

    occupancies = {
        truck.id: np.full((truck.width, truck.length, truck.height), -1, dtype=np.int32)
        for truck in problem.trucks
    }
    errors = []
    unsafe_trucks = set()
    regions = []

    for placement in loaded:
        truck_id, position = placement.truck_id, placement.position
        assert truck_id is not None and position is not None

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
            errors.append(
                f"Package {placement.package_id} is out of bounds in truck {truck_id}"
            )
            unsafe_trucks.add(truck_id)
            continue

        region = tuple(
            slice(start, start + size)
            for start, size in zip(origin, dimensions, strict=True)
        )
        regions.append((placement, package_index, region))

    # Finish all boundary checks before reporting overlaps.
    for placement, package_index, region in regions:
        truck_id = placement.truck_id
        assert truck_id is not None
        cells = occupancies[truck_id][region]
        if np.any(cells != -1):
            errors.append(
                f"Package {placement.package_id} overlaps another in truck {truck_id}"
            )
            unsafe_trucks.add(truck_id)
            continue
        cells[...] = package_index

    return occupancies, errors, unsafe_trucks


def validate_state(problem: Problem, state: State) -> ValidationResult:
    """Check all placements in the frozen order without modifying the inputs.

    Weights count unique known packages with consistent, known truck assignments,
    even when their geometry is invalid. Empty trucks have zero weight.
    Support needs complete assignments and unambiguous geometry; skip it where
    earlier errors prevent a reliable occupancy map.
    """
    loaded, assignment_errors = _check_assignments(problem, state)
    occupancies, geometry_errors, unsafe_trucks = _collect_occupancies(problem, loaded)
    errors = assignment_errors + geometry_errors
    packages = {package.id: package for package in problem.packages}
    # Compare decimal input values exactly at the capacity boundary. Binary
    # float addition would make 0.1 + 0.2 greater than a capacity of 0.3.
    exact_weights = {truck.id: Decimal(0) for truck in problem.trucks}
    for placement in loaded:
        assert placement.truck_id is not None
        exact_weights[placement.truck_id] += Decimal(
            str(packages[placement.package_id].weight)
        )
    truck_weights = {
        truck_id: float(weight) for truck_id, weight in exact_weights.items()
    }
    for truck in problem.trucks:
        if exact_weights[truck.id] > Decimal(str(truck.max_capacity)):
            errors.append(
                f"Truck {truck.id} exceeds capacity: "
                f"{truck_weights[truck.id]} > {truck.max_capacity}"
            )

    support_errors = []
    fragile_errors = []
    if not assignment_errors:
        for placement in loaded:
            truck_id, position = placement.truck_id, placement.position
            assert truck_id is not None and position is not None
            if truck_id in unsafe_trucks or position.z == 0:
                continue
            w, l, _ = get_oriented_dimensions(
                packages[placement.package_id], placement.orientation
            )
            x, y, z = position.x, position.y, position.z
            below = occupancies[truck_id][x : x + w, y : y + l, z - 1]
            supporters = np.unique(below[below >= 0])
            if supporters.size == 0:
                support_errors.append(
                    f"Package {placement.package_id} is floating in truck {truck_id}"
                )
            elif any(problem.packages[int(index)].is_fragile for index in supporters):
                fragile_errors.append(
                    f"Package {placement.package_id} rests on fragile support "
                    f"in truck {truck_id}"
                )
    errors.extend(support_errors)
    errors.extend(fragile_errors)
    return ValidationResult(
        valid=not errors, errors=errors, truck_weights=truck_weights
    )
