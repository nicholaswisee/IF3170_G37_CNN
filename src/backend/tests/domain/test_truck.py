import json

import pytest
from pydantic import ValidationError

from app.domain.package import Orientation
from app.domain.truck import PackagePlacement, Position, TruckSpec


def test_truck_spec_fields_serialization_and_frozen() -> None:
    truck = TruckSpec(id="t1", width=2, length=3, height=4, max_capacity=10)
    assert set(TruckSpec.model_fields) == {
        "id",
        "width",
        "length",
        "height",
        "max_capacity",
    }
    assert truck.model_dump() == {
        "id": "t1",
        "width": 2,
        "length": 3,
        "height": 4,
        "max_capacity": 10.0,
    }
    with pytest.raises(ValidationError):
        truck.max_capacity = 1


@pytest.mark.parametrize(
    ("field", "value"),
    [("width", 0), ("length", -1), ("height", 0), ("max_capacity", -0.1)],
)
def test_truck_spec_rejects_invalid_ranges(field: str, value: float) -> None:
    data = {"id": "t1", "width": 1, "length": 1, "height": 1, "max_capacity": 0}
    data[field] = value
    with pytest.raises(ValidationError):
        TruckSpec(**data)


def test_position_accepts_integer_coordinates_without_boundary_checks() -> None:
    assert Position(x=-2, y=100, z=0).model_dump() == {"x": -2, "y": 100, "z": 0}
    with pytest.raises(ValidationError):
        Position(x=1.5, y=0, z=0)


def test_placement_defaults_and_exact_fields() -> None:
    placement = PackagePlacement(package_id="p1")
    assert placement.model_dump() == {
        "package_id": "p1",
        "truck_id": None,
        "position": None,
        "orientation": Orientation.WLH,
    }
    assert set(PackagePlacement.model_fields) == {
        "package_id",
        "truck_id",
        "position",
        "orientation",
    }
    assert (
        PackagePlacement(
            package_id="p1", truck_id="t1", position=Position(x=0, y=0, z=0)
        ).truck_id
        == "t1"
    )


@pytest.mark.parametrize(
    ("truck_id", "position"),
    [("t1", None), (None, Position(x=0, y=0, z=0))],
)
def test_placement_rejects_inconsistent_assignment(
    truck_id: str | None, position: Position | None
) -> None:
    with pytest.raises(ValidationError):
        PackagePlacement(package_id="p1", truck_id=truck_id, position=position)


@pytest.mark.parametrize("orientation", list(Orientation))
@pytest.mark.parametrize("loaded", [False, True])
def test_placement_json_round_trip(orientation: Orientation, loaded: bool) -> None:
    position = Position(x=1, y=2, z=3) if loaded else None
    placement = PackagePlacement(
        package_id="p1",
        truck_id="t1" if loaded else None,
        position=position,
        orientation=orientation,
    )
    payload = placement.model_dump_json()
    assert json.loads(payload) == {
        "package_id": "p1",
        "truck_id": "t1" if loaded else None,
        "position": {"x": 1, "y": 2, "z": 3} if loaded else None,
        "orientation": orientation.value,
    }
    assert PackagePlacement.model_validate_json(payload) == placement
