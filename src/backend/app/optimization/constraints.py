"""Shared state-validation contract for every search algorithm."""

from pydantic import BaseModel

from app.domain.problem import Problem
from app.domain.state import State


class ValidationResult(BaseModel):
    valid: bool
    errors: list[str]
    truck_weights: dict[str, float]


def validate_state(problem: Problem, state: State) -> ValidationResult:
    """Validate a complete fleet state using the frozen global constraint rules."""
    raise NotImplementedError("Global constraint validation is not implemented yet.")
