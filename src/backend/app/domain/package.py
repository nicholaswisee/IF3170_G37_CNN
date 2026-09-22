from enum import StrEnum

from pydantic import BaseModel


class Orientation(StrEnum):
    HORIZONTAL = "horizontal"
    VERTICAL = "vertical"


class Package(BaseModel):
    id: str
    width: int
    length: int
    height: int
    orientation: Orientation
    value: float
    weight: float
    is_fragile: bool
    eta: int
