"""Contract tests for the shared mandatory and bonus fleet objectives."""

from typing import cast

import pytest

from app.domain import Orientation, PackagePlacement, Position, Problem, State
from app.optimization.objective import (
    ObjectiveMode,
    evaluate_objective,
    objective_upper_bound,
)


def make_state(problem: Problem, loaded_ids: tuple[str, ...]) -> State:
    return State(
        placements=[
            PackagePlacement(
                package_id=package.id,
                truck_id=problem.trucks[0].id if package.id in loaded_ids else None,
                position=Position(x=index, y=0, z=0)
                if package.id in loaded_ids
                else None,
            )
            for index, package in enumerate(reversed(problem.packages))
        ]
    )


@pytest.mark.parametrize(
    ("loaded_ids", "total", "eta_weighted"),
    [
        ((), 0.0, 0.0),
        (("base",), 10.0, 5.0),
        (("top",), 5.0, 5.0 / 3.0),
        (("fragile",), 4.0, 4.0),
        (("base", "fragile"), 14.0, 9.0),
        (("base", "top", "fragile"), 19.0, 32.0 / 3.0),
    ],
)
def test_only_loaded_packages_contribute(
    single_truck_problem: Problem,
    loaded_ids: tuple[str, ...],
    total: float,
    eta_weighted: float,
) -> None:
    state = make_state(single_truck_problem, loaded_ids)
    assert evaluate_objective(
        single_truck_problem, state, ObjectiveMode.TOTAL_VALUE
    ) == pytest.approx(total)
    assert evaluate_objective(
        single_truck_problem, state, ObjectiveMode.ETA_WEIGHTED_VALUE
    ) == pytest.approx(eta_weighted)


@pytest.mark.parametrize("mode", list(ObjectiveMode))
def test_empty_problem_scores_float_zero(
    single_truck_problem: Problem, mode: ObjectiveMode
) -> None:
    problem = Problem(packages=[], trucks=single_truck_problem.trucks)
    score = evaluate_objective(problem, State(placements=[]), mode)
    assert score == 0.0
    assert isinstance(score, float)


@pytest.mark.parametrize(
    ("mode", "expected"),
    [(ObjectiveMode.TOTAL_VALUE, 19.0), (ObjectiveMode.ETA_WEIGHTED_VALUE, 32 / 3)],
)
def test_fleet_total_is_independent_of_order_and_does_not_mutate_inputs(
    multi_truck_problem: Problem, mode: ObjectiveMode, expected: float
) -> None:
    problem = multi_truck_problem
    state = make_state(problem, ("base", "top", "fragile"))
    # Base and fragile fill truck-a's capacity; top goes in truck-b.
    state.placements[1].truck_id = "truck-b"
    original_problem = problem.model_dump_json()
    original_state = state.model_dump_json()

    assert evaluate_objective(problem, state, mode) == pytest.approx(expected)
    assert evaluate_objective(problem, state, mode) == pytest.approx(expected)
    assert problem.model_dump_json() == original_problem
    assert state.model_dump_json() == original_state

    reordered_problem = Problem(
        packages=list(reversed(problem.packages)),
        trucks=list(reversed(problem.trucks)),
    )
    reordered_state = State(placements=list(reversed(state.placements)))
    assert evaluate_objective(
        reordered_problem, reordered_state, mode
    ) == pytest.approx(expected)


def test_total_value_has_no_eta_weight_fragility_or_geometry_tie_breaker(
    single_truck_problem: Problem,
) -> None:
    problem = single_truck_problem
    state = make_state(problem, ("base",))
    changed_problem = Problem(
        packages=[
            package.model_copy(
                update={
                    "eta": 99,
                    "weight": 0.5,
                    "is_fragile": True,
                    "width": 1,
                    "length": 1,
                    "height": 2,
                }
            )
            for package in problem.packages
        ],
        trucks=problem.trucks,
    )
    changed_state = state.model_copy(deep=True)
    changed_state.placements[-1].position = Position(x=0, y=1, z=0)
    changed_state.placements[-1].orientation = Orientation.HLW

    assert evaluate_objective(problem, state, ObjectiveMode.TOTAL_VALUE) == 10.0
    assert (
        evaluate_objective(changed_problem, changed_state, ObjectiveMode.TOTAL_VALUE)
        == 10.0
    )
    assert evaluate_objective(
        changed_problem, changed_state, ObjectiveMode.ETA_WEIGHTED_VALUE
    ) == pytest.approx(0.1)


@pytest.mark.parametrize("mode", list(ObjectiveMode))
def test_loaded_zero_value_packages_score_zero(
    single_truck_problem: Problem, mode: ObjectiveMode
) -> None:
    problem = Problem(
        packages=[
            package.model_copy(update={"value": 0.0})
            for package in single_truck_problem.packages
        ],
        trucks=single_truck_problem.trucks,
    )
    state = make_state(problem, ("base", "top", "fragile"))
    assert evaluate_objective(problem, state, mode) == 0.0


def test_unknown_mode_is_rejected_even_for_empty_state(
    single_truck_problem: Problem,
) -> None:
    state = make_state(single_truck_problem, ())
    with pytest.raises(ValueError):
        evaluate_objective(single_truck_problem, state, cast(ObjectiveMode, "unknown"))


def test_total_value_rejects_unrepresentable_finite_sum(
    single_truck_problem: Problem,
) -> None:
    problem = Problem(
        packages=[
            package.model_copy(update={"value": 1e308})
            for package in single_truck_problem.packages
        ],
        trucks=single_truck_problem.trucks,
    )
    state = make_state(problem, ("base", "top", "fragile"))
    with pytest.raises(ValueError, match="(?i)objective.*representable"):
        evaluate_objective(problem, state, ObjectiveMode.TOTAL_VALUE)


def test_eta_weighted_handles_huge_integer_eta(
    single_truck_problem: Problem,
) -> None:
    problem = Problem(
        packages=[
            package.model_copy(update={"eta": 10**309, "value": 1e308})
            for package in single_truck_problem.packages
        ],
        trucks=single_truck_problem.trucks,
    )
    state = make_state(problem, ("base",))
    score = evaluate_objective(problem, state, ObjectiveMode.ETA_WEIGHTED_VALUE)
    assert score == pytest.approx(0.1)


def test_mode_values_match_serialized_contract() -> None:
    assert ObjectiveMode("total_value") is ObjectiveMode.TOTAL_VALUE
    assert ObjectiveMode("eta_weighted_value") is ObjectiveMode.ETA_WEIGHTED_VALUE


def test_upper_bound_normalizes_serialized_total_value(
    single_truck_problem: Problem,
) -> None:
    assert objective_upper_bound(
        single_truck_problem, cast(ObjectiveMode, "total_value")
    ) == objective_upper_bound(single_truck_problem, ObjectiveMode.TOTAL_VALUE)


def test_upper_bound_rejects_unknown_mode_for_empty_problem(
    single_truck_problem: Problem,
) -> None:
    problem = Problem(packages=[], trucks=single_truck_problem.trucks)
    with pytest.raises(ValueError):
        objective_upper_bound(problem, cast(ObjectiveMode, "unknown"))
