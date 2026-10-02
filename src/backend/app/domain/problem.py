from pydantic import BaseModel, model_validator

from app.domain.package import PackageSpec
from app.domain.truck import TruckSpec


class Problem(BaseModel):
    packages: list[PackageSpec]
    trucks: list[TruckSpec]

    @model_validator(mode="after")
    def validate_ids_and_trucks(self) -> "Problem":
        if not self.trucks:
            raise ValueError("at least one truck is required")
        if len({package.id for package in self.packages}) != len(self.packages):
            raise ValueError("package IDs must be unique")
        if len({truck.id for truck in self.trucks}) != len(self.trucks):
            raise ValueError("truck IDs must be unique")
        return self
