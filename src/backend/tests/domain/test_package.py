from enum import IntEnum
from typing import cast

import pytest
from pydantic import ValidationError

from app.domain.package import (
    Orientation,
    PackageSpec,
    get_oriented_dimensions,
    get_unique_orientations,
)


def test_orientation_values_and_exact_package_fields() -> None:
    assert [(item.name, item.value) for item in Orientation] == [
        ("WLH", 0),
        ("LWH", 1),
        ("WHL", 2),
        ("HWL", 3),
        ("LHW", 4),
        ("HLW", 5),
    ]
    assert issubclass(Orientation, IntEnum)
    package = PackageSpec(
        id="p1",
        width=2,
        length=3,
        height=4,
        value=5,
        weight=6,
        is_fragile=False,
        eta=0,
    )
    assert set(PackageSpec.model_fields) == {
        "id",
        "width",
        "length",
        "height",
        "value",
        "weight",
        "is_fragile",
        "eta",
    }
    assert package.model_dump() == {
        "id": "p1",
        "width": 2,
        "length": 3,
        "height": 4,
        "value": 5.0,
        "weight": 6.0,
        "is_fragile": False,
        "eta": 0,
    }


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("width", 0),
        ("length", -1),
        ("height", 0),
        ("value", -0.1),
        ("weight", -1.0),
        ("eta", -1),
    ],
)
def test_package_rejects_invalid_ranges(field: str, value: float) -> None:
    data = {
        "id": "p1",
        "width": 1,
        "length": 1,
        "height": 1,
        "value": 0,
        "weight": 0,
        "is_fragile": False,
        "eta": 0,
    }
    data[field] = value
    with pytest.raises(ValidationError):
        PackageSpec(**data)


def test_package_is_frozen() -> None:
    package = PackageSpec(
        id="p1",
        width=2,
        length=3,
        height=4,
        value=5,
        weight=6,
        is_fragile=False,
        eta=0,
    )
    with pytest.raises(ValidationError):
        package.width = 9


def test_oriented_dimensions_match_enum_contract() -> None:
    package = PackageSpec(
        id="p1",
        width=2,
        length=3,
        height=4,
        value=0,
        weight=0,
        is_fragile=False,
        eta=0,
    )
    assert [
        get_oriented_dimensions(package, orientation) for orientation in Orientation
    ] == [
        (2, 3, 4),
        (3, 2, 4),
        (2, 4, 3),
        (4, 2, 3),
        (3, 4, 2),
        (4, 3, 2),
    ]
    for invalid in (-1, 6):
        with pytest.raises(ValueError):
            get_oriented_dimensions(package, cast(Orientation, invalid))


@pytest.mark.parametrize(
    ("dimensions", "expected"),
    [
        ((2, 2, 3), [Orientation.WLH, Orientation.WHL, Orientation.HWL]),
        ((2, 3, 2), [Orientation.WLH, Orientation.LWH, Orientation.WHL]),
        ((3, 2, 2), [Orientation.WLH, Orientation.LWH, Orientation.LHW]),
        ((2, 2, 2), [Orientation.WLH]),
        ((3, 4, 1), list(Orientation)),
    ],
)
def test_unique_orientations_keep_first_enum_occurrence(
    dimensions: tuple[int, int, int], expected: list[Orientation]
) -> None:
    package = PackageSpec(
        id="p1",
        width=dimensions[0],
        length=dimensions[1],
        height=dimensions[2],
        value=0,
        weight=0,
        is_fragile=False,
        eta=0,
    )
    assert get_unique_orientations(package) == expected
    assert get_unique_orientations(package) == expected
