"""Saved truck and package configurations that the UI can import and reload."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app import limits
from app.domain.problem import Problem
from app.schemas.experiment import validate_problem_input


class ConfigUpload(BaseModel):
    """Body of POST /api/configs and the format of an exported configuration file."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    schema_version: Literal[1] = 1
    name: str = Field(min_length=1, max_length=limits.MAX_CONFIG_NAME_LENGTH)
    description: str = Field(
        default="", max_length=limits.MAX_CONFIG_DESCRIPTION_LENGTH
    )
    problem: Problem

    @field_validator("problem", mode="before")
    @classmethod
    def problem_within_request_limits(cls, value):
        return validate_problem_input(value)

    @field_validator("problem")
    @classmethod
    def fleet_volume_within_limit(cls, problem: Problem) -> Problem:
        volume = sum(
            truck.width * truck.length * truck.height for truck in problem.trucks
        )
        if volume > limits.MAX_TOTAL_TRUCK_VOLUME:
            raise ValueError(
                f"aggregate truck volume is {volume} cells; at most "
                f"{limits.MAX_TOTAL_TRUCK_VOLUME} are allowed"
            )
        return problem


class SavedConfig(BaseModel):
    id: str
    name: str
    description: str
    builtin: bool
    created_at: datetime | None
    problem: Problem


class ConfigSummary(BaseModel):
    id: str
    name: str
    description: str
    builtin: bool
    created_at: datetime | None
    truck_count: int
    package_count: int

    @classmethod
    def of(cls, config: SavedConfig) -> "ConfigSummary":
        return cls(
            id=config.id,
            name=config.name,
            description=config.description,
            builtin=config.builtin,
            created_at=config.created_at,
            truck_count=len(config.problem.trucks),
            package_count=len(config.problem.packages),
        )


class ConfigListResponse(BaseModel):
    configs: list[ConfigSummary]
