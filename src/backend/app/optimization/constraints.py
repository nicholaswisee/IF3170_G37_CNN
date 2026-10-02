"""Placeholder boundary for future state-constraint validation."""

from app.domain.package import PackageSpec
from app.domain.state import State
from app.domain.truck import TruckSpec


def validate_state(state: State, truck: TruckSpec, packages: list[PackageSpec]) -> bool:
    # TODO: Validate physical and assignment constraints in a later milestone.
    raise NotImplementedError("Constraint validation not implemented yet.")
