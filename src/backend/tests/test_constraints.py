"""Expected behavior of the shared validator in architecture freeze §§11–15."""

import pytest
from pydantic import ValidationError

from app.domain.package import Orientation, PackageSpec
from app.domain.problem import Problem
from app.domain.state import State
from app.domain.truck import PackagePlacement, Position, TruckSpec
from app.optimization.constraints import ValidationResult, validate_state


def placed(
    package_id: str,
    truck_id: str | None = None,
    coordinates: tuple[int, int, int] | None = None,
    orientation: Orientation = Orientation.WLH,
) -> PackagePlacement:
    position = (
        Position(x=coordinates[0], y=coordinates[1], z=coordinates[2])
        if coordinates is not None
        else None
    )
    return PackagePlacement(
        package_id=package_id,
        truck_id=truck_id,
        position=position,
        orientation=orientation,
    )


def state_with(problem: Problem, *placements: PackagePlacement) -> State:
    by_id = {placement.package_id: placement for placement in placements}
    return State(
        placements=[
            by_id.get(package.id, placed(package.id)) for package in problem.packages
        ]
    )


def assert_valid(problem: Problem, state: State, weights: dict[str, float]) -> None:
    result = validate_state(problem, state)
    assert isinstance(result, ValidationResult)
    assert result.valid is True
    assert result.errors == []
    assert result.truck_weights == weights


def assert_invalid(problem: Problem, state: State) -> None:
    result = validate_state(problem, state)
    assert isinstance(result, ValidationResult)
    assert result.valid is False
    assert result.errors


def test_placement_requires_truck_and_position_together() -> None:
    with pytest.raises(ValidationError):
        PackagePlacement(package_id="base", truck_id="truck-a")
    with pytest.raises(ValidationError):
        PackagePlacement(package_id="base", position=Position(x=0, y=0, z=0))


# Remove this marker when implementing the validator in the next schedule block.
# strict=True makes an unexpected pass visible instead of silently leaving stale markers.
@pytest.mark.xfail(
    raises=NotImplementedError,
    strict=True,
    reason="global validator is scheduled for afternoon–day 2",
)
class TestGlobalValidator:
    def test_valid_state_and_outside_package(
        self, single_truck_problem: Problem
    ) -> None:
        state = state_with(
            single_truck_problem,
            placed("base", "truck-a", (0, 0, 0)),
            placed("top", "truck-a", (0, 0, 1)),
        )
        assert_valid(single_truck_problem, state, {"truck-a": 5.0})

    @pytest.mark.parametrize(
        "invalid_ids",
        [
            ["base"],
            ["base", "base", "top", "fragile"],
            ["base", "top", "fragile", "unknown"],
        ],
    )
    def test_state_needs_exactly_one_known_placement_per_package(
        self, single_truck_problem: Problem, invalid_ids: list[str]
    ) -> None:
        state = State(placements=[placed(package_id) for package_id in invalid_ids])
        assert_invalid(single_truck_problem, state)

    def test_unknown_truck_is_invalid(self, single_truck_problem: Problem) -> None:
        state = state_with(
            single_truck_problem, placed("base", "missing-truck", (0, 0, 0))
        )
        assert_invalid(single_truck_problem, state)

    @pytest.mark.parametrize(
        "coordinates",
        [(-1, 0, 0), (3, 0, 0), (0, 3, 0), (0, 0, 3)],
    )
    def test_out_of_bounds_is_invalid(
        self, single_truck_problem: Problem, coordinates: tuple[int, int, int]
    ) -> None:
        state = state_with(single_truck_problem, placed("base", "truck-a", coordinates))
        assert_invalid(single_truck_problem, state)

    def test_boundary_uses_oriented_dimensions(
        self, single_truck_problem: Problem
    ) -> None:
        state = state_with(
            single_truck_problem,
            placed("base", "truck-a", (2, 3, 0), Orientation.WHL),
        )
        assert_valid(single_truck_problem, state, {"truck-a": 3.0})

    def test_same_truck_overlap_is_invalid(self, single_truck_problem: Problem) -> None:
        state = state_with(
            single_truck_problem,
            placed("base", "truck-a", (0, 0, 0)),
            placed("top", "truck-a", (1, 1, 0)),
        )
        assert_invalid(single_truck_problem, state)

    def test_same_coordinates_in_different_trucks_are_valid(
        self, multi_truck_problem: Problem
    ) -> None:
        state = state_with(
            multi_truck_problem,
            placed("base", "truck-a", (0, 0, 0)),
            placed("top", "truck-b", (0, 0, 0)),
        )
        assert_valid(multi_truck_problem, state, {"truck-a": 3.0, "truck-b": 2.0})

    def test_capacity_is_checked_per_truck(self, multi_truck_problem: Problem) -> None:
        state = state_with(
            multi_truck_problem,
            placed("base", "truck-a", (0, 0, 0)),
            placed("top", "truck-a", (3, 3, 0)),
        )
        assert_invalid(multi_truck_problem, state)

    def test_fully_floating_package_is_invalid(
        self, single_truck_problem: Problem
    ) -> None:
        state = state_with(single_truck_problem, placed("top", "truck-a", (0, 0, 1)))
        assert_invalid(single_truck_problem, state)

    def test_one_support_cell_is_enough(self) -> None:
        problem = Problem(
            packages=[
                PackageSpec(
                    id="pillar",
                    width=1,
                    length=1,
                    height=1,
                    value=1,
                    weight=1,
                    is_fragile=False,
                    eta=0,
                ),
                PackageSpec(
                    id="bridge",
                    width=2,
                    length=1,
                    height=1,
                    value=1,
                    weight=1,
                    is_fragile=False,
                    eta=0,
                ),
            ],
            trucks=[
                TruckSpec(id="truck-a", width=2, length=1, height=2, max_capacity=2)
            ],
        )
        state = state_with(
            problem,
            placed("pillar", "truck-a", (0, 0, 0)),
            placed("bridge", "truck-a", (0, 0, 1)),
        )
        assert_valid(problem, state, {"truck-a": 2.0})

    def test_fragile_package_cannot_support_another(
        self, single_truck_problem: Problem
    ) -> None:
        state = state_with(
            single_truck_problem,
            placed("fragile", "truck-a", (0, 0, 0)),
            placed("top", "truck-a", (0, 0, 1)),
        )
        assert_invalid(single_truck_problem, state)

    def test_any_fragile_contact_is_invalid_even_with_other_support(self) -> None:
        problem = Problem(
            packages=[
                PackageSpec(
                    id="fragile",
                    width=1,
                    length=1,
                    height=1,
                    value=1,
                    weight=1,
                    is_fragile=True,
                    eta=0,
                ),
                PackageSpec(
                    id="solid",
                    width=1,
                    length=1,
                    height=1,
                    value=1,
                    weight=1,
                    is_fragile=False,
                    eta=0,
                ),
                PackageSpec(
                    id="bridge",
                    width=2,
                    length=1,
                    height=1,
                    value=1,
                    weight=1,
                    is_fragile=False,
                    eta=0,
                ),
            ],
            trucks=[
                TruckSpec(id="truck-a", width=2, length=1, height=2, max_capacity=3)
            ],
        )
        state = state_with(
            problem,
            placed("fragile", "truck-a", (0, 0, 0)),
            placed("solid", "truck-a", (1, 0, 0)),
            placed("bridge", "truck-a", (0, 0, 1)),
        )
        assert_invalid(problem, state)

    def test_removing_support_invalidates_upper_package(
        self, single_truck_problem: Problem
    ) -> None:
        supported = state_with(
            single_truck_problem,
            placed("base", "truck-a", (0, 0, 0)),
            placed("top", "truck-a", (0, 0, 1)),
        )
        assert_valid(single_truck_problem, supported, {"truck-a": 5.0})
        unsupported = state_with(
            single_truck_problem, placed("top", "truck-a", (0, 0, 1))
        )
        assert_invalid(single_truck_problem, unsupported)
