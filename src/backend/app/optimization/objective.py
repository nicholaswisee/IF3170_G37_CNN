"""Shared fleet objectives defined by the frozen architecture."""

from enum import StrEnum
from math import fsum

from app.domain.problem import Problem
from app.domain.state import State


class ObjectiveMode(StrEnum):
    TOTAL_VALUE = "total_value"
    ETA_WEIGHTED_VALUE = "eta_weighted_value"


def evaluate_objective(
    problem: Problem,
    state: State,
    mode: ObjectiveMode,
) -> float:
    """Score loaded packages across the fleet without changing the inputs.

    Callers are responsible for checking feasibility with ``validate_state``.
    This function assumes the canonical one-placement-per-package contract;
    it adds no constraint penalties or tie-breakers to either objective.
    """
    mode = ObjectiveMode(mode)
    packages = {package.id: package for package in problem.packages}
    loaded = (
        packages[placement.package_id]
        for placement in state.placements
        if placement.truck_id is not None
    )
    if mode is ObjectiveMode.TOTAL_VALUE:
        return fsum(package.value for package in loaded)
    return fsum(package.value / (package.eta + 1) for package in loaded)
