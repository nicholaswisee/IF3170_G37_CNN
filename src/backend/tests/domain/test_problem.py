import pytest
from pydantic import ValidationError

from app.domain.package import PackageSpec
from app.domain.problem import Problem
from app.domain.truck import TruckSpec


def package(package_id: str = "p1") -> PackageSpec:
    return PackageSpec(
        id=package_id,
        width=1,
        length=1,
        height=1,
        value=0,
        weight=0,
        is_fragile=False,
        eta=0,
    )


def truck(truck_id: str = "t1") -> TruckSpec:
    return TruckSpec(id=truck_id, width=1, length=1, height=1, max_capacity=0)


def test_problem_accepts_lists_and_serializes_nested_models() -> None:
    problem = Problem(packages=[package()], trucks=[truck()])
    assert problem.model_dump() == {
        "packages": [package().model_dump()],
        "trucks": [truck().model_dump()],
    }


def test_problem_requires_at_least_one_truck() -> None:
    with pytest.raises(ValidationError):
        Problem(packages=[], trucks=[])


def test_problem_accepts_multiple_trucks_and_separate_id_namespaces() -> None:
    problem = Problem(
        packages=[package("shared")], trucks=[truck("shared"), truck("t2")]
    )
    assert [item.id for item in problem.trucks] == ["shared", "t2"]


@pytest.mark.parametrize(
    ("packages", "trucks"),
    [
        ([package("p1"), package("p1")], [truck()]),
        ([package()], [truck("t1"), truck("t1")]),
    ],
)
def test_problem_requires_unique_ids(
    packages: list[PackageSpec], trucks: list[TruckSpec]
) -> None:
    with pytest.raises(ValidationError):
        Problem(packages=packages, trucks=trucks)
