from enum import IntEnum

from pydantic import BaseModel, ConfigDict, Field


class Orientation(IntEnum):
    WLH = 0
    LWH = 1
    WHL = 2
    HWL = 3
    LHW = 4
    HLW = 5


class PackageSpec(BaseModel):
    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    id: str
    width: int = Field(gt=0)
    length: int = Field(gt=0)
    height: int = Field(gt=0)
    value: float = Field(ge=0)
    weight: float = Field(ge=0)
    is_fragile: bool
    eta: int = Field(ge=0)


def get_oriented_dimensions(
    package: PackageSpec, orientation: Orientation
) -> tuple[int, int, int]:
    w, l, h = package.width, package.length, package.height
    return (
        (w, l, h),
        (l, w, h),
        (w, h, l),
        (h, w, l),
        (l, h, w),
        (h, l, w),
    )[Orientation(orientation)]


def get_unique_orientations(package: PackageSpec) -> list[Orientation]:
    seen: set[tuple[int, int, int]] = set()
    unique = []
    for orientation in Orientation:
        dimensions = get_oriented_dimensions(package, orientation)
        if dimensions not in seen:
            seen.add(dimensions)
            unique.append(orientation)
    return unique
