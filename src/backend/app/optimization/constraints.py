"""Placeholder boundary for future state-constraint validation."""

from app.domain.package import Package
from app.domain.state import State
from app.domain.truck import Truck


def validate_state(state: State, truck: Truck, packages: list[Package]) -> bool:
    # TODO: Validate physical and assignment constraints in a later milestone.
    raise NotImplementedError("Constraint validation not implemented yet.")
