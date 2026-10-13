"""Acceptance boundaries, cooling, termination, and shared-core SA behavior."""

import math
import random
from unittest.mock import Mock, patch

import pytest
from pydantic import ValidationError

from app.domain import (
    Move,
    MoveType,
    PackagePlacement,
    PackageSpec,
    Position,
    Problem,
    State,
    TruckSpec,
)
from app.optimization.algorithms import SearchResult, SimulatedAnnealing
from app.optimization.algorithms import simulated_annealing as sa
from app.optimization.constraints import validate_state
from app.optimization.initializer import generate_random_feasible_state
from app.optimization.neighbors import NeighborCandidate
from app.optimization.objective import ObjectiveMode, evaluate_objective
from app.schemas import SimulatedAnnealingParameters


@pytest.fixture
def problem() -> Problem:
    return Problem(
        packages=[
            PackageSpec(
                id="p",
                width=1,
                length=1,
                height=1,
                value=10,
                weight=1,
                is_fragile=False,
                eta=1,
            )
        ],
        trucks=[TruckSpec(id="t", width=2, length=1, height=1, max_capacity=1)],
    )


def state_at(x: int | None) -> State:
    return State(
        placements=[
            PackagePlacement(
                package_id="p",
                truck_id="t" if x is not None else None,
                position=Position(x=x, y=0, z=0) if x is not None else None,
            )
        ]
    )


def neighbor(before: State, after: State) -> NeighborCandidate:
    return NeighborCandidate(
        state=after,
        move=Move(
            type=MoveType.RELOCATE,
            package_ids=["p"],
            before=before.placements,
            after=after.placements,
        ),
    )


def run(
    problem: Problem,
    initial: State | None,
    rng=None,
    mode=ObjectiveMode.TOTAL_VALUE,
    **parameters,
) -> SearchResult:
    return SimulatedAnnealing().run(
        problem,
        initial,
        objective_mode=mode,
        rng=rng if rng is not None else random.Random(42),
        parameters=SimulatedAnnealingParameters(**parameters),
        include_state_history=False,
    )


@pytest.mark.parametrize("initial_x", [None, 0])
def test_better_and_equal_candidates_are_accepted_without_acceptance_draw(
    problem: Problem, initial_x: int | None
) -> None:
    initial, target = state_at(initial_x), state_at(1)
    rng = Mock(spec=random.Random)
    with patch.object(
        sa, "generate_random_neighbor", return_value=neighbor(initial, target)
    ) as generate:
        result = run(problem, initial, rng, max_iterations=1)
    assert result.final_state == target
    assert result.final_score == result.best_score == 10
    rng.random.assert_not_called()
    assert generate.call_args.args[2] is rng


@pytest.mark.parametrize(
    "draw,accepted", [(0.1, True), (math.exp(-1), False), (0.9, False)]
)
def test_worse_candidate_uses_strict_probability_boundary_and_preserves_best(
    problem: Problem, draw: float, accepted: bool
) -> None:
    initial, target = state_at(0), state_at(None)
    original = initial.model_dump_json()
    rng = Mock(spec=random.Random)
    rng.random.return_value = draw
    with patch.object(
        sa, "generate_random_neighbor", return_value=neighbor(initial, target)
    ):
        result = run(problem, initial, rng, initial_temperature=10, max_iterations=1)
    assert result.final_state == (target if accepted else initial)
    assert result.best_state == initial
    assert result.best_score == 10
    assert result.final_score == (0 if accepted else 10)
    rng.random.assert_called_once_with()
    result.final_state.placements.clear()
    assert result.best_state == initial
    assert initial.model_dump_json() == original


def test_acceptance_uses_selected_objective(problem: Problem) -> None:
    initial, target = state_at(0), state_at(None)
    for mode, expected in [
        (ObjectiveMode.TOTAL_VALUE, 10),
        (ObjectiveMode.ETA_WEIGHTED_VALUE, 0),
    ]:
        rng = Mock(spec=random.Random)
        rng.random.return_value = 0.5
        with patch.object(
            sa, "generate_random_neighbor", return_value=neighbor(initial, target)
        ):
            result = run(
                problem, initial, rng, mode, initial_temperature=10, max_iterations=1
            )
        assert result.final_score == expected


@pytest.mark.parametrize("draw,expected", [(0.2, 10), (0.05, 0)])
def test_cooling_applies_after_rejected_iteration(
    problem: Problem, draw: float, expected: float
) -> None:
    initial, target = state_at(0), state_at(None)
    rng = Mock(spec=random.Random)
    rng.random.side_effect = [0.9, draw]
    with patch.object(
        sa, "generate_random_neighbor", return_value=neighbor(initial, target)
    ):
        result = run(
            problem, initial, rng, initial_temperature=10, alpha=0.5, max_iterations=2
        )
    assert result.final_score == expected
    assert result.metadata["final_temperature"] == 2.5
    assert result.metadata["termination_reason"] == "max_iterations"


def test_temperature_equal_to_minimum_is_still_processed(problem: Problem) -> None:
    initial, target = state_at(0), state_at(1)
    with patch.object(
        sa, "generate_random_neighbor", return_value=neighbor(initial, target)
    ) as generate:
        result = run(
            problem,
            initial,
            initial_temperature=4,
            min_temperature=1,
            alpha=0.5,
            max_iterations=10,
        )
    assert generate.call_count == result.iterations == 3
    assert result.metadata == {
        "final_temperature": 0.5,
        "termination_reason": "temperature_minimum",
    }


def test_initial_temperature_below_minimum_does_not_search(problem: Problem) -> None:
    with patch.object(sa, "generate_random_neighbor") as generate:
        result = run(problem, state_at(0), initial_temperature=0.5, min_temperature=1)
    generate.assert_not_called()
    assert result.iterations == 0
    assert result.final_state == result.best_state == state_at(0)


@pytest.mark.parametrize("value,expected", [(0, 1), (0.2, 1), (10, 10)])
def test_default_temperature_and_safe_floor(
    problem: Problem, value: float, expected: float
) -> None:
    problem.packages[0] = problem.packages[0].model_copy(update={"value": value})
    with patch.object(sa, "generate_random_neighbor", return_value=None):
        result = run(problem, state_at(None))
    assert result.metadata["final_temperature"] == expected
    assert result.metadata["termination_reason"] == "no_valid_neighbor"
    assert result.iterations == 1


def test_default_temperature_mean_handles_large_finite_values(problem: Problem) -> None:
    problem.packages = [
        problem.packages[0].model_copy(update={"id": str(i), "value": 1e308})
        for i in range(2)
    ]
    initial = State(
        placements=[PackagePlacement(package_id=p.id) for p in problem.packages]
    )
    with patch.object(sa, "generate_random_neighbor", return_value=None):
        result = run(problem, initial)
    assert result.metadata["final_temperature"] == 1e308


def test_empty_problem_terminates_with_finite_temperature(problem: Problem) -> None:
    problem.packages = []
    result = run(problem, State(placements=[]))
    assert result.best_score == result.final_score == 0
    assert result.metadata == {
        "final_temperature": 1.0,
        "termination_reason": "no_valid_neighbor",
    }


def test_tiny_temperature_rejects_worse_candidate_without_division_by_zero(
    problem: Problem,
) -> None:
    initial, target = state_at(0), state_at(None)
    with patch.object(
        sa, "generate_random_neighbor", return_value=neighbor(initial, target)
    ):
        result = run(
            problem,
            initial,
            initial_temperature=5e-324,
            min_temperature=5e-324,
            alpha=0.1,
            max_iterations=2,
        )
    assert result.final_score == 10
    assert result.iterations == 1
    assert result.metadata["termination_reason"] == "temperature_minimum"


@pytest.mark.parametrize("initial", [None, State(placements=[]), state_at(2)])
def test_missing_or_infeasible_initial_state_is_rejected(
    problem: Problem, initial: State | None
) -> None:
    with (
        patch.object(sa, "generate_random_neighbor") as generate,
        pytest.raises(ValueError, match="initial state"),
    ):
        run(problem, initial)
    generate.assert_not_called()


def test_mutated_parameters_are_revalidated_before_search(problem: Problem) -> None:
    parameters = SimulatedAnnealingParameters()
    parameters.alpha = 1
    with pytest.raises(ValidationError):
        SimulatedAnnealing().run(
            problem,
            state_at(0),
            objective_mode=ObjectiveMode.TOTAL_VALUE,
            rng=random.Random(42),
            parameters=parameters,
            include_state_history=False,
        )


@pytest.mark.parametrize("mode", list(ObjectiveMode))
def test_real_neighbors_return_feasible_reproducible_states(
    single_truck_problem: Problem, mode: ObjectiveMode
) -> None:
    problem = single_truck_problem
    initial = generate_random_feasible_state(problem, random.Random(7))
    original = initial.model_dump_json()
    result = run(problem, initial, mode=mode, max_iterations=10)
    replay = run(problem, initial, mode=mode, max_iterations=10)
    assert result == replay
    assert 0 < result.iterations <= 10
    for state, score in [
        (result.final_state, result.final_score),
        (result.best_state, result.best_score),
    ]:
        assert validate_state(problem, state).valid
        assert evaluate_objective(problem, state, mode) == score
    assert result.best_score >= result.final_score
    assert initial.model_dump_json() == original
