"""Shared fleet objectives defined by the frozen architecture."""

from collections.abc import Iterable
from enum import StrEnum
from math import fsum, isfinite

from app.domain.package import PackageSpec
from app.domain.problem import Problem
from app.domain.state import State


class ObjectiveMode(StrEnum):
    TOTAL_VALUE = "total_value"
    ETA_WEIGHTED_VALUE = "eta_weighted_value"


class ObjectiveRangeError(ValueError):
    pass


def objective_contributions(
    problem: Problem, state: State, mode: ObjectiveMode
) -> list[float]:
    mode = ObjectiveMode(mode)
    packages = {package.id: package for package in problem.packages}
    return [
        _package_contribution(packages[placement.package_id], mode)
        for placement in state.placements
        if placement.truck_id is not None
    ]


def objective_upper_bound(problem: Problem, mode: ObjectiveMode) -> float:
    mode = ObjectiveMode(mode)
    return _sum_contributions(
        _package_contribution(package, mode) for package in problem.packages
    )


def _package_contribution(package: PackageSpec, mode: ObjectiveMode) -> float:
    if mode is ObjectiveMode.TOTAL_VALUE:
        return package.value
    numerator, denominator = package.value.as_integer_ratio()
    return numerator / (denominator * (package.eta + 1))


def _sum_contributions(contributions: Iterable[float]) -> float:
    try:
        score = fsum(contributions)
    except OverflowError as error:
        raise ObjectiveRangeError(
            "Objective score is not representable as a finite float."
        ) from error
    if not isfinite(score):
        raise ObjectiveRangeError(
            "Objective score is not representable as a finite float."
        )
    return score


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
    return _sum_contributions(objective_contributions(problem, state, mode))
