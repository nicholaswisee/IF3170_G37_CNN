from pydantic import BaseModel

from app.domain.package import Orientation


class Truck(BaseModel):
    width: int
    length: int
    height: int
    max_capacity: float


class Position(BaseModel):
    x: int
    y: int
    z: int


class PackagePlacement(BaseModel):
    package_id: str
    position: Position
    orientation: Orientation
    inside: bool
