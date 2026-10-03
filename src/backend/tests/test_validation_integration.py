"""Exercise the serialized domain contract across validation and occupancy."""

import numpy as np
import pytest

from app.domain import Position, Problem, State
from app.optimization.constraints import (
    ValidationResult,
    build_occupancies,
    validate_state,
)


@pytest.fixture
def serialized_fleet(multi_truck_problem: Problem) -> tuple[Problem, State]:
    problem = Problem.model_validate_json(multi_truck_problem.model_dump_json())
    # The state uses integer orientations, nullable outside placements, and an
    # order different from problem.packages. Base is rotated to height two.
    state = State.model_validate_json("""{
        "placements": [
            {"package_id": "fragile", "truck_id": "truck-a",
             "position": {"x": 1, "y": 0, "z": 2}, "orientation": 0},
            {"package_id": "top", "truck_id": null,
             "position": null, "orientation": 0},
            {"package_id": "base", "truck_id": "truck-a",
             "position": {"x": 0, "y": 0, "z": 0}, "orientation": 2}
        ]
    }""")
    return problem, state


def test_json_round_trip_preserves_validation_and_occupancy(
    serialized_fleet: tuple[Problem, State],
) -> None:
    problem, state = serialized_fleet
    result = validate_state(problem, state)
    assert result.valid is True
    assert result.errors == []
    assert result.truck_weights == {"truck-a": 4.0, "truck-b": 0.0}
    assert ValidationResult.model_validate_json(result.model_dump_json()) == result

    grids = build_occupancies(problem, state)
    expected_a = np.full((4, 4, 3), -1, dtype=np.int32)
    expected_a[:2, :1, :2] = 0
    expected_a[1, 0, 2] = 2
    np.testing.assert_array_equal(grids["truck-a"], expected_a)
    np.testing.assert_array_equal(grids["truck-b"], np.full((2, 2, 2), -1))

    restored = State.model_validate_json(state.model_dump_json())
    assert validate_state(problem, restored) == result
    for truck_id, grid in build_occupancies(problem, restored).items():
        np.testing.assert_array_equal(grid, grids[truck_id])
    # Occupancy, validity, and weights stay derived rather than entering State.
    assert set(restored.model_dump()) == {"placements"}


def test_cross_truck_candidate_revalidates_support_and_preserves_original(
    serialized_fleet: tuple[Problem, State],
) -> None:
    problem, original = serialized_fleet
    original_json = original.model_dump_json()
    original_grids = build_occupancies(problem, original)
    candidate = original.model_copy(deep=True)
    base = next(p for p in candidate.placements if p.package_id == "base")
    base.truck_id = "truck-b"
    base.position = Position(x=0, y=0, z=0)

    result = validate_state(problem, candidate)
    assert result.valid is False
    assert result.truck_weights == {"truck-a": 1.0, "truck-b": 3.0}
    assert len(result.errors) == 1
    assert "fragile" in result.errors[0] and "floating" in result.errors[0]

    # Geometry is representable even though support makes the candidate invalid.
    candidate_grids = build_occupancies(problem, candidate)
    assert np.count_nonzero(candidate_grids["truck-a"] == 0) == 0
    assert np.count_nonzero(candidate_grids["truck-b"] == 0) == 4
    assert original.model_dump_json() == original_json
    assert validate_state(problem, original).valid is True
    for truck_id, grid in build_occupancies(problem, original).items():
        np.testing.assert_array_equal(grid, original_grids[truck_id])


@pytest.mark.parametrize(
    ("x", "error_fragment"), [(0, "overlaps"), (-1, "out of bounds")]
)
def test_invalid_geometry_returns_validation_errors_and_no_occupancy(
    serialized_fleet: tuple[Problem, State], x: int, error_fragment: str
) -> None:
    problem, state = serialized_fleet
    candidate = state.model_copy(deep=True)
    top = next(p for p in candidate.placements if p.package_id == "top")
    top.truck_id = "truck-a"
    top.position = Position(x=x, y=0, z=0)
    restored = State.model_validate_json(candidate.model_dump_json())

    result = validate_state(problem, restored)
    assert result.valid is False
    assert any(error_fragment in error for error in result.errors)
    with pytest.raises(ValueError, match=error_fragment):
        build_occupancies(problem, restored)
