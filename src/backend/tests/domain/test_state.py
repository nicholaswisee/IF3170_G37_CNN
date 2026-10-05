import pytest
from pydantic import ValidationError

from app.domain.state import State
from app.domain.truck import PackagePlacement, Position


def test_state_contains_only_placements() -> None:
    state = State(placements=[])
    assert state.model_dump() == {"placements": []}
    assert set(State.model_fields) == {"placements"}


def test_state_requires_placements() -> None:
    with pytest.raises(ValidationError):
        State.model_validate({})


def test_state_does_not_require_problem_completeness() -> None:
    assert State(placements=[]).placements == []
    assert (
        State(placements=[PackagePlacement(package_id="unknown")])
        .placements[0]
        .package_id
        == "unknown"
    )


def test_deep_model_copy_does_not_share_nested_objects_or_lists() -> None:
    original = State(
        placements=[
            PackagePlacement(
                package_id="p1", truck_id="t1", position=Position(x=1, y=2, z=3)
            )
        ]
    )
    duplicate = original.model_copy(deep=True)
    assert duplicate.placements is not original.placements
    assert duplicate.placements[0] is not original.placements[0]
    assert duplicate.placements[0].position is not original.placements[0].position
    assert duplicate.placements[0].position is not None
    duplicate.placements[0].position.x = 99
    duplicate.placements[0].package_id = "p2"
    duplicate.placements.append(PackagePlacement(package_id="p3"))
    assert original.placements[0].position == Position(x=1, y=2, z=3)
    assert original.placements[0].package_id == "p1"
    assert len(original.placements) == 1
