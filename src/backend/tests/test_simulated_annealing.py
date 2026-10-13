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
    include_state_history=False,
    **parameters,
) -> SearchResult:
    return SimulatedAnnealing().run(
        problem,
        initial,
        objective_mode=mode,
        rng=rng if rng is not None else random.Random(42),
        parameters=SimulatedAnnealingParameters(**parameters),
        include_state_history=include_state_history,
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


@pytest.mark.parametrize("include_snapshots", [False, True])
def test_history_records_decisions_and_pre_cooling_temperature(
    problem: Problem, include_snapshots: bool
) -> None:
    initial, loaded, moved = state_at(None), state_at(0), state_at(1)
    candidates = [
        neighbor(initial, loaded),
        neighbor(loaded, moved),
        neighbor(moved, initial),
        neighbor(moved, initial),
    ]
    rng = Mock(spec=random.Random)
    rng.random.side_effect = [0.9, 0.01]
    with patch.object(sa, "generate_random_neighbor", side_effect=candidates):
        result = run(
            problem,
            initial,
            rng,
            include_state_history=include_snapshots,
            initial_temperature=20,
            alpha=0.5,
            max_iterations=4,
        )
    assert [event.iteration for event in result.history] == [0, 1, 2, 3, 4]
    assert [event.temperature for event in result.history] == [20, 20, 10, 5, 2.5]
    assert [event.current_score for event in result.history] == [0, 10, 10, 10, 0]
    assert [event.best_score for event in result.history] == [0, 10, 10, 10, 10]
    assert [event.candidate_score for event in result.history] == [None, 10, 10, 0, 0]
    assert [event.accepted for event in result.history] == [
        None,
        True,
        True,
        False,
        True,
    ]
    assert result.history[0].acceptance_probability is None
    assert [
        event.acceptance_probability for event in result.history[1:]
    ] == pytest.approx([1, 1, math.exp(-2), math.exp(-4)])
    assert result.metadata["final_temperature"] == 1.25
    assert [event.move for event in result.history[1:]] == [c.move for c in candidates]
    expected_states = [initial, loaded, moved, moved, initial]
    assert [event.state_snapshot for event in result.history] == (
        expected_states if include_snapshots else [None] * 5
    )
    assert SearchResult.model_validate_json(result.model_dump_json()) == result


@pytest.mark.parametrize(
    "count,expected", [(2, 1), (3, 1), (4, 1), (6, 2), (7, 2), (8, 2), (10, 3)]
)
def test_stuck_latch_resets_only_on_new_best(
    problem: Problem, count: int, expected: int
) -> None:
    problem.packages.append(
        problem.packages[0].model_copy(update={"id": "q", "value": 5.0})
    )
    problem.trucks[0] = problem.trucks[0].model_copy(update={"max_capacity": 2.0})

    def state_for(score: int) -> State:
        return State(
            placements=[
                PackagePlacement(
                    package_id="p",
                    truck_id="t" if score >= 10 else None,
                    position=Position(x=0, y=0, z=0) if score >= 10 else None,
                ),
                PackagePlacement(
                    package_id="q",
                    truck_id="t" if score == 15 else None,
                    position=Position(x=1, y=0, z=0) if score == 15 else None,
                ),
            ]
        )

    initial = state_for(0)
    previous = initial
    candidates = []
    scores = [0, 0, 0, 10, 0, 0, 10, 15, 15, 15]
    for score in scores[:count]:
        target = state_for(score)
        candidates.append(
            NeighborCandidate(
                state=target,
                move=Move(
                    type=MoveType.RELOCATE,
                    package_ids=["p", "q"],
                    before=previous.placements,
                    after=target.placements,
                ),
            )
        )
        previous = target
    rng = Mock(spec=random.Random)
    rng.random.return_value = 0
    with patch.object(sa, "generate_random_neighbor", side_effect=candidates):
        result = run(
            problem,
            initial,
            rng,
            stuck_patience=2,
            max_iterations=count,
            initial_temperature=100,
            alpha=0.99,
        )
    assert result.metadata["stuck_events"] == expected
    assert [e.best_score for e in result.history] == [0] + [
        max(scores[:i]) for i in range(1, count + 1)
    ]
    assert result.best_score == evaluate_objective(
        problem, result.best_state, ObjectiveMode.TOTAL_VALUE
    )


def test_rejected_candidates_count_towards_stuck(problem: Problem) -> None:
    initial, outside = state_at(0), state_at(None)
    rng = Mock(spec=random.Random)
    rng.random.return_value = 0.99
    with patch.object(
        sa, "generate_random_neighbor", return_value=neighbor(initial, outside)
    ):
        result = run(
            problem,
            initial,
            rng,
            initial_temperature=1,
            max_iterations=5,
            stuck_patience=2,
        )
    assert result.metadata["stuck_events"] == 1
    assert all(event.accepted is False for event in result.history[1:])


def test_no_neighbor_records_terminal_state_without_fabricated_probability(
    problem: Problem,
) -> None:
    initial = state_at(0)
    with patch.object(sa, "generate_random_neighbor", return_value=None):
        result = run(problem, initial, include_state_history=True, stuck_patience=1)
    assert len(result.history) == result.iterations + 1 == 2
    event = result.history[-1]
    assert event.state_snapshot == initial
    assert event.current_score == event.best_score == 10
    assert event.candidate_score is event.acceptance_probability is event.move is None
    assert event.accepted is False
    assert result.metadata["stuck_events"] == 1


def test_zero_iterations_still_records_initial_state(problem: Problem) -> None:
    initial = state_at(0)
    result = run(
        problem,
        initial,
        initial_temperature=0.5,
        min_temperature=1,
        include_state_history=True,
    )
    assert result.iterations == 0
    assert len(result.history) == 1
    assert result.history[0].state_snapshot == initial
    assert result.history[0].temperature == 0.5
    assert result.metadata["stuck_events"] == 0


def test_snapshots_moves_best_and_final_states_are_independent(
    problem: Problem,
) -> None:
    initial, target = state_at(0), state_at(1)
    candidate = neighbor(initial, target)
    with patch.object(sa, "generate_random_neighbor", return_value=candidate):
        result = run(problem, initial, include_state_history=True, max_iterations=2)
    first = result.history[1]
    assert first.state_snapshot is not None and first.move is not None
    others = [result.history[0], result.history[2]]
    original = [event.model_dump_json() for event in others]
    first.state_snapshot.placements[0].position.x = 99
    first.move.after[0].position.x = 99
    assert [event.model_dump_json() for event in others] == original
    assert result.final_state == target == state_at(1)
    assert result.best_state == initial == state_at(0)
    result.final_state.placements.clear()
    result.best_state.placements.clear()
    assert [event.model_dump_json() for event in others] == original
    assert initial == state_at(0)


@pytest.mark.parametrize("mode", list(ObjectiveMode))
@pytest.mark.parametrize(
    "fixture_name", ["single_truck_problem", "multi_truck_problem"]
)
def test_snapshot_flag_preserves_seeded_search_and_rng_sequence(
    request: pytest.FixtureRequest, fixture_name: str, mode: ObjectiveMode
) -> None:
    problem = request.getfixturevalue(fixture_name)
    problem_json = problem.model_dump_json()
    initial = generate_random_feasible_state(problem, random.Random(7))
    initial_json = initial.model_dump_json()
    rng, replay_rng, metrics_rng = (
        random.Random(42),
        random.Random(42),
        random.Random(42),
    )
    result = run(
        problem, initial, rng, mode, include_state_history=True, max_iterations=20
    )
    replay = run(
        problem,
        initial,
        replay_rng,
        mode,
        include_state_history=True,
        max_iterations=20,
    )
    metrics = run(
        problem,
        initial,
        metrics_rng,
        mode,
        include_state_history=False,
        max_iterations=20,
    )
    assert result == replay
    assert rng.getstate() == replay_rng.getstate() == metrics_rng.getstate()
    assert result.final_state == metrics.final_state
    assert result.best_state == metrics.best_state
    assert result.metadata == metrics.metadata
    assert len(result.history) == result.iterations + 1
    for event, without_snapshot in zip(result.history, metrics.history, strict=True):
        assert event.state_snapshot is not None
        assert validate_state(problem, event.state_snapshot).valid
        assert (
            evaluate_objective(problem, event.state_snapshot, mode)
            == event.current_score
        )
        assert event.model_dump(
            exclude={"state_snapshot"}
        ) == without_snapshot.model_dump(exclude={"state_snapshot"})
        assert without_snapshot.state_snapshot is None
    assert result.best_score >= result.final_score
    assert problem.model_dump_json() == problem_json
    assert initial.model_dump_json() == initial_json


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
        "stuck_events": 0,
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
        "stuck_events": 0,
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
