import numpy as np
import pytest

from app.domain.package import Orientation, PackageSpec
from app.domain.problem import Problem
from app.domain.state import State
from app.domain.truck import PackagePlacement, Position, TruckSpec
from app.optimization.constraints import build_occupancies


def make_state(problem: Problem, *loaded: PackagePlacement) -> State:
    """Include an outside placement for every package not explicitly assigned."""
    by_id = {placement.package_id: placement for placement in loaded}
    return State(
        placements=[
            by_id.get(package.id, PackagePlacement(package_id=package.id))
            for package in problem.packages
        ]
    )


def loaded(package_id: str, truck_id: str, x: int, y: int, z: int) -> PackagePlacement:
    return PackagePlacement(
        package_id=package_id,
        truck_id=truck_id,
        position=Position(x=x, y=y, z=z),
    )


def test_single_truck_grid_uses_package_indices(single_truck_problem: Problem) -> None:
    state = make_state(
        single_truck_problem,
        loaded("base", "truck-a", 0, 0, 0),
        loaded("top", "truck-a", 0, 0, 1),
    )
    # Placement order has no semantic meaning; indices belong to problem.packages.
    state.placements.reverse()
    grids = build_occupancies(single_truck_problem, state)
    expected = np.full((4, 4, 3), -1, dtype=np.int32)
    expected[0:2, 0:2, 0:1] = 0
    expected[0, 0, 1] = 1
    assert set(grids) == {"truck-a"}
    assert grids["truck-a"].dtype == np.int32
    np.testing.assert_array_equal(grids["truck-a"], expected)
    assert not np.any(grids["truck-a"] == 2)  # Fragile package is outside.


def test_multi_truck_grids_are_independent(multi_truck_problem: Problem) -> None:
    state = make_state(
        multi_truck_problem,
        loaded("base", "truck-a", 0, 0, 0),
        loaded("top", "truck-b", 0, 0, 0),
    )
    grids = build_occupancies(multi_truck_problem, state)
    expected_a = np.full((4, 4, 3), -1, dtype=np.int32)
    expected_a[:2, :2, :1] = 0
    expected_b = np.full((2, 2, 2), -1, dtype=np.int32)
    expected_b[0, 0, 0] = 1
    assert set(grids) == {"truck-a", "truck-b"}
    np.testing.assert_array_equal(grids["truck-a"], expected_a)
    np.testing.assert_array_equal(grids["truck-b"], expected_b)
    assert not np.shares_memory(grids["truck-a"], grids["truck-b"])


def test_all_outside_keeps_all_trucks_empty(multi_truck_problem: Problem) -> None:
    grids = build_occupancies(multi_truck_problem, make_state(multi_truck_problem))
    for truck in multi_truck_problem.trucks:
        assert grids[truck.id].shape == (truck.width, truck.length, truck.height)
        assert grids[truck.id].dtype == np.int32
        assert np.all(grids[truck.id] == -1)


def test_problem_with_no_packages_still_has_truck_grids(
    multi_truck_problem: Problem,
) -> None:
    problem = Problem(packages=[], trucks=multi_truck_problem.trucks)
    grids = build_occupancies(problem, State(placements=[]))
    assert set(grids) == {"truck-a", "truck-b"}
    assert all(np.all(grid == -1) for grid in grids.values())


@pytest.mark.parametrize(
    ("orientation", "dimensions"),
    [
        (Orientation.WLH, (2, 3, 4)),
        (Orientation.LWH, (3, 2, 4)),
        (Orientation.WHL, (2, 4, 3)),
        (Orientation.HWL, (4, 2, 3)),
        (Orientation.LHW, (3, 4, 2)),
        (Orientation.HLW, (4, 3, 2)),
    ],
)
def test_oriented_cells_at_nonzero_origin(
    orientation: Orientation, dimensions: tuple[int, int, int]
) -> None:
    problem = Problem(
        packages=[
            PackageSpec(
                id="box",
                width=2,
                length=3,
                height=4,
                value=1,
                weight=1,
                is_fragile=False,
                eta=0,
            )
        ],
        trucks=[TruckSpec(id="t", width=6, length=7, height=8, max_capacity=10)],
    )
    placement = loaded("box", "t", 1, 2, 3)
    placement.orientation = orientation
    grid = build_occupancies(problem, make_state(problem, placement))["t"]
    w, l, h = dimensions
    expected = np.full((6, 7, 8), -1, dtype=np.int32)
    expected[1 : 1 + w, 2 : 2 + l, 3 : 3 + h] = 0
    np.testing.assert_array_equal(grid, expected)


def test_build_is_deterministic_and_does_not_mutate_inputs(
    single_truck_problem: Problem,
) -> None:
    state = make_state(single_truck_problem, loaded("base", "truck-a", 0, 0, 0))
    problem_before = single_truck_problem.model_dump()
    state_before = state.model_dump()
    first = build_occupancies(single_truck_problem, state)
    second = build_occupancies(single_truck_problem, state)
    np.testing.assert_array_equal(first["truck-a"], second["truck-a"])
    first["truck-a"].fill(99)
    assert not np.any(second["truck-a"] == 99)
    assert single_truck_problem.model_dump() == problem_before
    assert state.model_dump() == state_before


@pytest.mark.parametrize(
    "coordinates",
    [(-1, 0, 0), (0, -1, 0), (0, 0, -1), (3, 0, 0), (0, 3, 0), (0, 0, 3)],
)
def test_rejects_bounds_before_numpy_can_clip_or_wrap(
    single_truck_problem: Problem, coordinates: tuple[int, int, int]
) -> None:
    state = make_state(single_truck_problem, loaded("base", "truck-a", *coordinates))
    with pytest.raises(ValueError, match="out of bounds"):
        build_occupancies(single_truck_problem, state)


def test_package_can_touch_truck_boundary(single_truck_problem: Problem) -> None:
    state = make_state(single_truck_problem, loaded("base", "truck-a", 2, 2, 2))
    expected = np.full((4, 4, 3), -1, dtype=np.int32)
    expected[2:4, 2:4, 2:3] = 0
    np.testing.assert_array_equal(
        build_occupancies(single_truck_problem, state)["truck-a"], expected
    )


def test_boundary_uses_assigned_truck_dimensions(multi_truck_problem: Problem) -> None:
    # x=3 fits truck-a, but truck-b is only two cells wide.
    state = make_state(multi_truck_problem, loaded("top", "truck-b", 3, 0, 0))
    with pytest.raises(ValueError, match="out of bounds"):
        build_occupancies(multi_truck_problem, state)


def test_rejects_overlap_without_changing_state(single_truck_problem: Problem) -> None:
    state = make_state(
        single_truck_problem,
        loaded("base", "truck-a", 0, 0, 0),
        loaded("top", "truck-a", 1, 1, 0),
    )
    before = state.model_dump()
    with pytest.raises(ValueError, match="overlaps"):
        build_occupancies(single_truck_problem, state)
    assert state.model_dump() == before


@pytest.mark.parametrize(
    "package_ids",
    [
        ["base", "top"],
        ["base", "base", "top", "fragile"],
        ["base", "top", "unknown"],
    ],
    ids=["missing", "duplicate", "unknown"],
)
def test_rejects_incomplete_or_ambiguous_assignments(
    single_truck_problem: Problem, package_ids: list[str]
) -> None:
    state = State(placements=[PackagePlacement(package_id=id_) for id_ in package_ids])
    with pytest.raises(ValueError):
        build_occupancies(single_truck_problem, state)


def test_rejects_unknown_truck(single_truck_problem: Problem) -> None:
    state = make_state(single_truck_problem, loaded("base", "missing", 0, 0, 0))
    with pytest.raises(ValueError, match="Unknown truck"):
        build_occupancies(single_truck_problem, state)


@pytest.mark.parametrize("with_truck", [True, False])
def test_rejects_assignment_made_inconsistent_after_construction(
    single_truck_problem: Problem, with_truck: bool
) -> None:
    placement = loaded("base", "truck-a", 0, 0, 0)
    state = make_state(single_truck_problem, placement)
    # State objects are mutable, so callers can bypass construction validation.
    if with_truck:
        placement.position = None
    else:
        placement.truck_id = None
    with pytest.raises(ValueError, match="Inconsistent assignment"):
        build_occupancies(single_truck_problem, state)
