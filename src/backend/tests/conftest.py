"""Small fleet problems reused by the validator contract tests."""

import pytest

from app.domain.package import PackageSpec
from app.domain.problem import Problem
from app.domain.truck import TruckSpec


@pytest.fixture
def single_truck_problem() -> Problem:
    return Problem(
        packages=[
            PackageSpec(
                id="base",
                width=2,
                length=2,
                height=1,
                value=10,
                weight=3,
                is_fragile=False,
                eta=1,
            ),
            PackageSpec(
                id="top",
                width=1,
                length=1,
                height=1,
                value=5,
                weight=2,
                is_fragile=False,
                eta=2,
            ),
            PackageSpec(
                id="fragile",
                width=1,
                length=1,
                height=1,
                value=4,
                weight=1,
                is_fragile=True,
                eta=0,
            ),
        ],
        trucks=[TruckSpec(id="truck-a", width=4, length=4, height=3, max_capacity=10)],
    )


@pytest.fixture
def multi_truck_problem(single_truck_problem: Problem) -> Problem:
    return Problem(
        packages=single_truck_problem.packages,
        trucks=[
            TruckSpec(id="truck-a", width=4, length=4, height=3, max_capacity=4),
            TruckSpec(id="truck-b", width=2, length=2, height=2, max_capacity=10),
        ],
    )
