from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domain.package import Orientation


class TruckSpec(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    width: int = Field(gt=0)
    length: int = Field(gt=0)
    height: int = Field(gt=0)
    max_capacity: float = Field(ge=0)


class Position(BaseModel):
    """Left-bottom-back corner: x is width, y is depth, z is height."""

    x: int
    y: int
    z: int


class PackagePlacement(BaseModel):
    package_id: str
    truck_id: str | None = None
    position: Position | None = None
    orientation: Orientation = Orientation.WLH

    @model_validator(mode="after")
    def validate_assignment(self) -> "PackagePlacement":
        if (self.truck_id is None) != (self.position is None):
            raise ValueError("truck_id and position must both be set or both be None")
        return self
