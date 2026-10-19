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


class TestGlobalValidator:
    def test_all_outside_has_zero_weight(self, multi_truck_problem: Problem) -> None:
        assert_valid(
            multi_truck_problem,
            state_with(multi_truck_problem),
            {"truck-a": 0.0, "truck-b": 0.0},
        )

    def test_empty_package_list_is_valid(self, multi_truck_problem: Problem) -> None:
        problem = Problem(packages=[], trucks=multi_truck_problem.trucks)
        assert_valid(problem, State(placements=[]), {"truck-a": 0.0, "truck-b": 0.0})

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
        [(-1, 0, 0), (0, -1, 0), (0, 0, -1), (3, 0, 0), (0, 3, 0), (0, 0, 3)],
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
        result = validate_state(multi_truck_problem, state)
        assert result.valid is False
        assert len(result.errors) == 1
        assert "capacity" in result.errors[0]
        assert result.truck_weights == {"truck-a": 5.0, "truck-b": 0.0}

    def test_capacity_equality_is_valid(self, multi_truck_problem: Problem) -> None:
        state = state_with(
            multi_truck_problem,
            placed("base", "truck-a", (0, 0, 0)),
            placed("fragile", "truck-a", (3, 3, 0)),
        )
        assert_valid(multi_truck_problem, state, {"truck-a": 4.0, "truck-b": 0.0})

    @pytest.mark.parametrize(
        ("second_weight", "expected_weight", "valid"),
        [
            (0.2, 0.3, True),
            (0.20000000000000004, 0.30000000000000004, False),
        ],
    )
    def test_decimal_capacity_boundary(
        self, second_weight: float, expected_weight: float, valid: bool
    ) -> None:
        problem = Problem(
            packages=[
                PackageSpec(
                    id=package_id,
                    width=1,
                    length=1,
                    height=1,
                    value=1,
                    weight=weight,
                    is_fragile=False,
                    eta=0,
                )
                for package_id, weight in [("first", 0.1), ("second", second_weight)]
            ],
            trucks=[
                TruckSpec(id="truck-a", width=2, length=1, height=1, max_capacity=0.3)
            ],
        )
        state = state_with(
            problem,
            placed("first", "truck-a", (0, 0, 0)),
            placed("second", "truck-a", (1, 0, 0)),
        )
        result = validate_state(problem, state)
        assert result.valid is valid
        assert result.truck_weights == {"truck-a": expected_weight}
        if valid:
            assert result.errors == []
        else:
            assert len(result.errors) == 1
            assert "capacity" in result.errors[0]

    def test_boundary_uses_assigned_truck_size(
        self, multi_truck_problem: Problem
    ) -> None:
        state = state_with(multi_truck_problem, placed("top", "truck-b", (2, 0, 0)))
        result = validate_state(multi_truck_problem, state)
        assert result.valid is False
        assert len(result.errors) == 1
        assert "out of bounds" in result.errors[0]

    @pytest.mark.parametrize("with_truck", [True, False])
    def test_inconsistent_assignment_after_mutation_is_invalid(
        self, single_truck_problem: Problem, with_truck: bool
    ) -> None:
        state = state_with(single_truck_problem, placed("base", "truck-a", (0, 0, 0)))
        if with_truck:
            state.placements[0].position = None
        else:
            state.placements[0].truck_id = None
        result = validate_state(single_truck_problem, state)
        assert result.valid is False
        assert len(result.errors) == 1
        assert "Inconsistent assignment" in result.errors[0]

    def test_duplicate_assignment_across_trucks_is_invalid(
        self, multi_truck_problem: Problem
    ) -> None:
        state = state_with(multi_truck_problem, placed("base", "truck-a", (0, 0, 0)))
        state.placements.append(placed("base", "truck-b", (0, 0, 0)))
        result = validate_state(multi_truck_problem, state)
        assert result.valid is False
        assert len(result.errors) == 1
        assert "Duplicate" in result.errors[0]
        assert result.truck_weights == {"truck-a": 0.0, "truck-b": 0.0}

    def test_fully_floating_package_is_invalid(
        self, single_truck_problem: Problem
    ) -> None:
        state = state_with(single_truck_problem, placed("top", "truck-a", (0, 0, 1)))
        assert_invalid(single_truck_problem, state)

    def test_support_cannot_come_from_another_truck(
        self, multi_truck_problem: Problem
    ) -> None:
        state = state_with(
            multi_truck_problem,
            placed("base", "truck-a", (0, 0, 0)),
            placed("top", "truck-b", (0, 0, 1)),
        )
        result = validate_state(multi_truck_problem, state)
        assert result.valid is False
        assert len(result.errors) == 1
        assert "top" in result.errors[0] and "floating" in result.errors[0]

    def test_support_uses_rotated_height(self, single_truck_problem: Problem) -> None:
        state = state_with(
            single_truck_problem,
            placed("base", "truck-a", (0, 0, 0), Orientation.WHL),
            placed("top", "truck-a", (0, 0, 2)),
        )
        assert_valid(single_truck_problem, state, {"truck-a": 5.0})

    @pytest.mark.parametrize("coordinates", [(3, 3, 0), (0, 0, 1)])
    def test_fragile_can_stand_on_floor_or_solid_package(
        self, single_truck_problem: Problem, coordinates: tuple[int, int, int]
    ) -> None:
        state = state_with(
            single_truck_problem,
            placed("base", "truck-a", (0, 0, 0)),
            placed("fragile", "truck-a", coordinates),
        )
        assert_valid(single_truck_problem, state, {"truck-a": 4.0})

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

    def test_independent_errors_accumulate_in_frozen_order(
        self, multi_truck_problem: Problem
    ) -> None:
        state = state_with(
            multi_truck_problem,
            placed("base", "truck-a", (0, 0, 0)),
            placed("top", "truck-a", (0, 0, 0)),
            placed("fragile", "truck-b", (0, 0, 1)),
        )
        result = validate_state(multi_truck_problem, state)
        assert result.valid is False
        assert len(result.errors) == 3
        assert "overlaps" in result.errors[0]
        assert "capacity" in result.errors[1]
        assert "floating" in result.errors[2]
        assert result.truck_weights == {"truck-a": 5.0, "truck-b": 1.0}

    def test_out_of_bounds_packages_still_contribute_to_truck_weight(
        self, multi_truck_problem: Problem
    ) -> None:
        state = state_with(
            multi_truck_problem,
            placed("base", "truck-a", (3, 0, 0)),
            placed("top", "truck-a", (3, 3, 0)),
        )
        result = validate_state(multi_truck_problem, state)
        assert result.valid is False
        assert len(result.errors) == 2
        assert "out of bounds" in result.errors[0]
        assert "capacity" in result.errors[1]
        assert result.truck_weights == {"truck-a": 5.0, "truck-b": 0.0}

    def test_structural_errors_allow_other_safe_checks(
        self, multi_truck_problem: Problem
    ) -> None:
        state = State(
            placements=[
                placed("unknown"),
                placed("top", "missing-truck", (0, 0, 0)),
                placed("fragile", "truck-b", (2, 0, 0)),
            ]
        )
        result = validate_state(multi_truck_problem, state)
        assert result.valid is False
        assert len(result.errors) == 4
        assert "Missing placement" in result.errors[0]
        assert "Unknown package" in result.errors[1]
        assert "Unknown truck" in result.errors[2]
        assert "out of bounds" in result.errors[3]

    def test_state_order_does_not_affect_result_or_mutate_input(
        self, single_truck_problem: Problem
    ) -> None:
        state = state_with(
            single_truck_problem,
            placed("base", "truck-a", (0, 0, 0)),
            placed("top", "truck-a", (0, 0, 1)),
        )
        reversed_state = state.model_copy(deep=True)
        reversed_state.placements.reverse()
        problem_before, state_before = (
            single_truck_problem.model_dump(),
            state.model_dump(),
        )
        reversed_before = reversed_state.model_dump()
        result = validate_state(single_truck_problem, state)
        assert result.valid is True
        assert result == validate_state(single_truck_problem, reversed_state)
        assert single_truck_problem.model_dump() == problem_before
        assert state.model_dump() == state_before
        assert reversed_state.model_dump() == reversed_before
