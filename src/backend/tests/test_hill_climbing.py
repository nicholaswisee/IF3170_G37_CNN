"""Hill Climbing with Sideways Move on real and scripted neighborhoods."""

import random
from collections.abc import Iterator
from itertools import pairwise

import pytest
from pydantic import BaseModel, ValidationError

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
from app.optimization.algorithms import HillClimbing, SearchResult
from app.optimization.algorithms import hill_climbing as hc_module
from app.optimization.constraints import validate_state
from app.optimization.initializer import generate_random_feasible_state
from app.optimization.neighbors import NeighborCandidate, NeighborConfig
from app.optimization.objective import ObjectiveMode, evaluate_objective
from app.schemas.experiment import HillClimbingParameters, HillClimbingVariant

STEEPEST = HillClimbingVariant.STEEPEST_ASCENT
STOCHASTIC = HillClimbingVariant.STOCHASTIC
SIDEWAYS = HillClimbingVariant.SIDEWAYS
RANDOM_RESTART = HillClimbingVariant.RANDOM_RESTART


def unit_box(id_: str, value: float) -> PackageSpec:
    return PackageSpec(
        id=id_,
        width=1,
        length=1,
        height=1,
        value=value,
        weight=1,
        is_fragile=False,
        eta=0,
    )


def outside(problem: Problem) -> State:
    return State(
        placements=[PackagePlacement(package_id=p.id) for p in problem.packages]
    )


def run_hc(
    problem: Problem,
    initial: State,
    *,
    variant: HillClimbingVariant = SIDEWAYS,
    seed: int = 42,
    include_state_history: bool = True,
    objective_mode: ObjectiveMode = ObjectiveMode.TOTAL_VALUE,
    **parameters: int,
) -> SearchResult:
    # Tiny problems have fewer valid neighbors than the default batch size, so
    # each iteration spends the full proposal budget; keep plateaus short.
    parameters = {
        "candidates_per_iteration": 20,
        "max_sideways": 5,
        "max_restarts": 2,
        **parameters,
    }
    return HillClimbing(variant).run(
        problem,
        initial,
        objective_mode=objective_mode,
        rng=random.Random(seed),
        parameters=HillClimbingParameters(**parameters),
        include_state_history=include_state_history,
    )


# --- Real neighborhoods -----------------------------------------------------


@pytest.mark.parametrize(
    "problem_name", ["single_truck_problem", "multi_truck_problem"]
)
@pytest.mark.parametrize("seed", [42, 123, 2026])
def test_sideways_returns_feasible_non_worse_states(
    request: pytest.FixtureRequest, problem_name: str, seed: int
) -> None:
    problem: Problem = request.getfixturevalue(problem_name)
    initial = generate_random_feasible_state(problem, random.Random(seed))
    original = initial.model_dump_json()
    initial_score = evaluate_objective(problem, initial, ObjectiveMode.TOTAL_VALUE)

    result = run_hc(problem, initial, seed=seed, max_iterations=200)

    assert initial.model_dump_json() == original
    assert validate_state(problem, result.final_state).valid
    assert validate_state(problem, result.best_state).valid
    assert result.best_score == evaluate_objective(
        problem, result.best_state, ObjectiveMode.TOTAL_VALUE
    )
    assert result.final_score == evaluate_objective(
        problem, result.final_state, ObjectiveMode.TOTAL_VALUE
    )
    # Hill climbing never accepts a worse state, so final and best scores agree.
    assert result.final_score == result.best_score >= initial_score


def test_sideways_loads_packages_from_empty_state(
    single_truck_problem: Problem,
) -> None:
    result = run_hc(single_truck_problem, outside(single_truck_problem))
    # All three packages fit together under the 10-unit capacity.
    assert result.best_score == 19
    assert result.metadata["termination_reason"] in {"max_sideways", "local_optimum"}


def test_sideways_moves_packages_between_trucks(multi_truck_problem: Problem) -> None:
    result = run_hc(multi_truck_problem, outside(multi_truck_problem))
    assert validate_state(multi_truck_problem, result.best_state).valid
    assert result.best_score == 19
    used_trucks = {p.truck_id for p in result.best_state.placements if p.truck_id}
    # truck-a's capacity of 4 cannot hold every package, so both trucks are needed.
    assert used_trucks == {"truck-a", "truck-b"}


@pytest.mark.parametrize("include_state_history", [False, True])
def test_same_seed_reproduces_search(
    multi_truck_problem: Problem, include_state_history: bool
) -> None:
    initial = generate_random_feasible_state(multi_truck_problem, random.Random(7))
    first = run_hc(
        multi_truck_problem, initial, include_state_history=include_state_history
    )
    second = run_hc(
        multi_truck_problem, initial, include_state_history=include_state_history
    )
    assert first == second


def test_eta_weighted_objective_is_used(single_truck_problem: Problem) -> None:
    mode = ObjectiveMode.ETA_WEIGHTED_VALUE
    result = run_hc(
        single_truck_problem, outside(single_truck_problem), objective_mode=mode
    )
    assert result.best_score == evaluate_objective(
        single_truck_problem, result.best_state, mode
    )
    assert result.best_score == pytest.approx(10 / 2 + 5 / 3 + 4 / 1)


def test_history_records_every_iteration(multi_truck_problem: Problem) -> None:
    result = run_hc(multi_truck_problem, outside(multi_truck_problem))
    history = result.history

    assert [event.iteration for event in history] == list(range(result.iterations + 1))
    assert history[0].current_score == 0
    assert history[0].accepted is None
    assert all(event.state_snapshot is not None for event in history)
    for event in history:
        assert event.state_snapshot is not None
        assert event.current_score == evaluate_objective(
            multi_truck_problem, event.state_snapshot, ObjectiveMode.TOTAL_VALUE
        )
    for previous, event in pairwise(history):
        assert event.best_score >= previous.best_score
        assert event.current_score >= previous.current_score
        assert (event.move is not None) == bool(event.accepted)
    assert history[-1].best_score == result.best_score


def test_history_omits_snapshots_when_disabled(single_truck_problem: Problem) -> None:
    result = run_hc(
        single_truck_problem,
        outside(single_truck_problem),
        include_state_history=False,
    )
    assert all(event.state_snapshot is None for event in result.history)


def test_returned_states_do_not_alias_input(single_truck_problem: Problem) -> None:
    initial = generate_random_feasible_state(single_truck_problem, random.Random(1))
    original = initial.model_dump_json()
    result = run_hc(single_truck_problem, initial, max_iterations=1)
    result.final_state.placements.clear()
    result.best_state.placements.clear()
    assert initial.model_dump_json() == original


def test_plateau_stops_at_sideways_cap() -> None:
    # One small package in a large truck: relocations and rotations keep the
    # score unchanged, so every iteration after loading is a sideways move.
    problem = Problem(
        packages=[unit_box("only", 5)],
        trucks=[TruckSpec(id="t", width=5, length=5, height=5, max_capacity=10)],
    )
    initial = State(
        placements=[
            PackagePlacement(
                package_id="only", truck_id="t", position=Position(x=0, y=0, z=0)
            )
        ]
    )
    result = run_hc(
        problem,
        initial,
        max_iterations=100,
        candidates_per_iteration=10,
        max_sideways=3,
    )
    assert result.metadata == {
        "sideways_moves": 3,
        "termination_reason": "max_sideways",
    }
    assert result.iterations == 4
    assert [event.accepted for event in result.history[1:]] == [True, True, True, False]
    assert result.final_state != initial
    # best_state keeps the first state that reached the best score.
    assert result.best_state == initial


def test_max_iterations_limit(single_truck_problem: Problem) -> None:
    result = run_hc(
        single_truck_problem, outside(single_truck_problem), max_iterations=1
    )
    assert result.iterations == 1
    assert result.metadata["termination_reason"] == "max_iterations"
    assert result.history[-1].accepted is True


# --- Scripted neighborhoods -------------------------------------------------


SCRIPTED_PROBLEM = Problem(
    packages=[
        unit_box("zero-1", 0),
        unit_box("zero-2", 0),
        unit_box("zero-3", 0),
        unit_box("valuable", 5),
        unit_box("small", 2),
    ],
    trucks=[TruckSpec(id="t", width=5, length=1, height=1, max_capacity=10)],
)


def loaded(*package_ids: str) -> NeighborCandidate:
    placements = [
        PackagePlacement(
            package_id=package.id,
            truck_id="t",
            position=Position(x=index, y=0, z=0),
        )
        if package.id in package_ids
        else PackagePlacement(package_id=package.id)
        for index, package in enumerate(SCRIPTED_PROBLEM.packages)
    ]
    move = Move(type=MoveType.RELOCATE, package_ids=[], before=[], after=[])
    return NeighborCandidate(state=State(placements=placements), move=move)


def script(
    monkeypatch: pytest.MonkeyPatch, batches: list[list[NeighborCandidate]]
) -> None:
    remaining: Iterator[list[NeighborCandidate]] = iter(batches)

    def fake_sample(
        problem: Problem,
        state: State,
        rng: random.Random,
        count: int,
        config: NeighborConfig,
    ) -> list[NeighborCandidate]:
        return next(remaining)

    monkeypatch.setattr(hc_module, "sample_valid_neighbors", fake_sample)


def run_scripted(
    variant: HillClimbingVariant = SIDEWAYS, seed: int = 42, **parameters: int
) -> SearchResult:
    return run_hc(
        SCRIPTED_PROBLEM,
        outside(SCRIPTED_PROBLEM),
        variant=variant,
        seed=seed,
        **parameters,
    )


def test_improvement_resets_consecutive_sideways(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    script(
        monkeypatch,
        [
            [loaded("zero-1")],  # 0: sideways 1
            [loaded("zero-1", "zero-2")],  # 0: sideways 2
            [loaded("zero-1", "zero-2", "valuable")],  # 5: improvement, reset
            [loaded("zero-1", "zero-2", "zero-3", "valuable")],  # 5: sideways 1
            [loaded("zero-2", "zero-3", "valuable")],  # 5: sideways 2
            [loaded("zero-3", "valuable")],  # 5: cap reached, stop
        ],
    )
    result = run_scripted(max_sideways=2)

    assert result.metadata == {
        "sideways_moves": 4,
        "termination_reason": "max_sideways",
    }
    assert result.iterations == 6
    assert [e.metadata.get("consecutive_sideways") for e in result.history[1:]] == [
        1,
        2,
        0,
        1,
        2,
        None,
    ]
    assert result.final_state == loaded("zero-2", "zero-3", "valuable").state
    assert result.best_state == loaded("zero-1", "zero-2", "valuable").state
    assert result.best_score == 5


def test_worse_candidates_are_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    script(
        monkeypatch,
        [
            [loaded("valuable")],
            [loaded(), loaded("zero-1")],
        ],
    )
    result = run_scripted()
    assert result.metadata["termination_reason"] == "local_optimum"
    assert result.iterations == 2
    assert result.final_state == loaded("valuable").state
    assert result.history[-1].accepted is False
    assert result.history[-1].candidate_score == 0


def test_zero_sideways_stops_on_plateau(monkeypatch: pytest.MonkeyPatch) -> None:
    script(monkeypatch, [[loaded("zero-1")]])
    result = run_scripted(max_sideways=0)
    assert result.metadata["termination_reason"] == "local_optimum"
    assert result.final_state == outside(SCRIPTED_PROBLEM)


def test_empty_neighborhood_terminates(monkeypatch: pytest.MonkeyPatch) -> None:
    script(monkeypatch, [[]])
    result = run_scripted()
    assert result.metadata["termination_reason"] == "no_valid_neighbor"
    assert result.iterations == 1
    assert result.history[-1].metadata == {"sampled_neighbors": 0}


def test_equal_best_ties_are_chosen_randomly(monkeypatch: pytest.MonkeyPatch) -> None:
    ties = [loaded("valuable", "zero-1"), loaded("valuable", "zero-2")]
    chosen = set()
    for seed in range(20):
        script(monkeypatch, [[loaded("zero-1"), *ties], []])
        result = run_hc(SCRIPTED_PROBLEM, outside(SCRIPTED_PROBLEM), seed=seed)
        assert result.history[1].current_score == 5
        chosen.add(result.history[1].state_snapshot.model_dump_json())  # type: ignore[union-attr]
    assert chosen == {tie.state.model_dump_json() for tie in ties}


# --- Inputs -----------------------------------------------------------------


def test_requires_initial_state(single_truck_problem: Problem) -> None:
    with pytest.raises(ValueError, match="initial state"):
        HillClimbing().run(
            single_truck_problem,
            None,
            objective_mode=ObjectiveMode.TOTAL_VALUE,
            rng=random.Random(0),
            parameters=HillClimbingParameters(),
            include_state_history=False,
        )


class GenericParameters(BaseModel):
    max_iterations: int = 1


class UnknownParameters(BaseModel):
    temperature: float = 1.0


def test_parameters_are_validated_as_hill_climbing_parameters(
    single_truck_problem: Problem,
) -> None:
    initial = outside(single_truck_problem)
    result = HillClimbing().run(
        single_truck_problem,
        initial,
        objective_mode=ObjectiveMode.TOTAL_VALUE,
        rng=random.Random(0),
        parameters=GenericParameters(),
        include_state_history=False,
    )
    assert result.iterations == 1
    with pytest.raises(ValidationError):
        HillClimbing().run(
            single_truck_problem,
            initial,
            objective_mode=ObjectiveMode.TOTAL_VALUE,
            rng=random.Random(0),
            parameters=UnknownParameters(),
            include_state_history=False,
        )


def test_default_variant_is_sideways() -> None:
    assert HillClimbing().variant is HillClimbingVariant.SIDEWAYS
    assert HillClimbing("sideways").variant is HillClimbingVariant.SIDEWAYS  # type: ignore[arg-type]


# --- All variants on real neighborhoods ------------------------------------


@pytest.mark.parametrize("variant", list(HillClimbingVariant))
@pytest.mark.parametrize(
    "problem_name", ["single_truck_problem", "multi_truck_problem"]
)
def test_every_variant_returns_feasible_reproducible_results(
    request: pytest.FixtureRequest,
    problem_name: str,
    variant: HillClimbingVariant,
) -> None:
    problem: Problem = request.getfixturevalue(problem_name)
    initial = generate_random_feasible_state(problem, random.Random(5))
    original = initial.model_dump_json()
    initial_score = evaluate_objective(problem, initial, ObjectiveMode.TOTAL_VALUE)

    result = run_hc(problem, initial, variant=variant, max_iterations=100)

    assert initial.model_dump_json() == original
    assert validate_state(problem, result.final_state).valid
    assert validate_state(problem, result.best_state).valid
    assert result.best_score == evaluate_objective(
        problem, result.best_state, ObjectiveMode.TOTAL_VALUE
    )
    assert result.best_score >= initial_score
    assert result.history[-1].best_score == result.best_score
    for previous, event in pairwise(result.history):
        assert event.iteration > previous.iteration
        assert event.best_score >= previous.best_score
    assert result == run_hc(problem, initial, variant=variant, max_iterations=100)


@pytest.mark.parametrize("variant", [STEEPEST, STOCHASTIC])
def test_steepest_and_stochastic_metadata(
    single_truck_problem: Problem, variant: HillClimbingVariant
) -> None:
    result = run_hc(
        single_truck_problem, outside(single_truck_problem), variant=variant
    )
    assert result.best_score == 19
    assert result.final_score == result.best_score
    assert result.metadata == {
        "termination_reason": "max_iterations"
        if variant is STOCHASTIC
        else "local_optimum",
        "sampled_neighbors": 1 if variant is STOCHASTIC else 20,
    }
    assert all("sideways" not in event.metadata for event in result.history)


# --- Steepest-Ascent --------------------------------------------------------


def test_steepest_moves_to_best_sampled_candidate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    script(monkeypatch, [[loaded("small"), loaded("valuable")], []])
    result = run_scripted(STEEPEST)
    assert result.history[1].current_score == 5
    assert result.history[1].candidate_score == 5
    assert result.metadata["termination_reason"] == "no_valid_neighbor"


def test_steepest_terminates_on_plateau(monkeypatch: pytest.MonkeyPatch) -> None:
    # Steepest-Ascent ignores max_sideways: an equal-best sample ends the climb.
    script(
        monkeypatch,
        [[loaded("valuable")], [loaded("valuable", "zero-1"), loaded("zero-2")]],
    )
    result = run_scripted(STEEPEST, max_sideways=50)
    assert result.metadata["termination_reason"] == "local_optimum"
    assert result.iterations == 2
    assert result.final_state == loaded("valuable").state
    assert result.history[-1].accepted is False
    assert result.history[-1].candidate_score == 5


# --- Stochastic -------------------------------------------------------------


def test_stochastic_uses_one_neighbor_and_continues_after_rejections(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    problem = Problem(
        packages=[unit_box(f"p{i}", 10) for i in range(3)],
        trucks=[TruckSpec(id="t", width=10, length=1, height=1, max_capacity=10)],
    )

    def candidate(package_count: int) -> NeighborCandidate:
        state = State(
            placements=[
                PackagePlacement(
                    package_id=package.id,
                    truck_id="t" if i < package_count else None,
                    position=Position(x=i, y=0, z=0) if i < package_count else None,
                )
                for i, package in enumerate(problem.packages)
            ]
        )
        return NeighborCandidate(
            state=state,
            move=Move(type=MoveType.RELOCATE, package_ids=[], before=[], after=[]),
        )

    initial = candidate(1).state
    proposed = [candidate(0), candidate(1), candidate(2), None, candidate(3)]
    calls = 0

    def fake_random_neighbor(
        problem_: Problem, state: State, rng: random.Random, config: NeighborConfig
    ) -> NeighborCandidate | None:
        nonlocal calls
        result = proposed[calls]
        calls += 1
        return result

    def unexpected_sample(*args: object, **kwargs: object) -> list[NeighborCandidate]:
        pytest.fail("stochastic HC must request one random neighbor")

    monkeypatch.setattr(
        hc_module, "generate_random_neighbor", fake_random_neighbor, raising=False
    )
    monkeypatch.setattr(hc_module, "sample_valid_neighbors", unexpected_sample)

    result = run_hc(
        problem,
        initial,
        variant=STOCHASTIC,
        max_iterations=5,
        candidates_per_iteration=99,
    )

    assert calls == 5
    assert [event.current_score for event in result.history] == [10, 10, 10, 20, 20, 30]
    assert [event.accepted for event in result.history[1:]] == [
        False,
        False,
        True,
        False,
        True,
    ]
    assert [event.candidate_score for event in result.history[1:]] == [
        0,
        10,
        20,
        None,
        30,
    ]
    assert [event.move is not None for event in result.history[1:]] == [
        True,
        True,
        True,
        False,
        True,
    ]
    assert [event.state_snapshot for event in result.history[1:]] == [
        initial,
        initial,
        candidate(2).state,
        candidate(2).state,
        candidate(3).state,
    ]
    assert [event.metadata for event in result.history[1:]] == [
        {"sampled_neighbors": 1, "improving_candidates": 0},
        {"sampled_neighbors": 1, "improving_candidates": 0},
        {"sampled_neighbors": 1, "improving_candidates": 1},
        {"sampled_neighbors": 0, "improving_candidates": 0},
        {"sampled_neighbors": 1, "improving_candidates": 1},
    ]
    assert result.iterations == 5
    assert len(result.history) == 6
    assert result.metadata == {
        "termination_reason": "max_iterations",
        "sampled_neighbors": 1,
    }


def test_stochastic_all_none_attempts_consume_iteration_budget(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0

    def no_neighbor(
        problem: Problem, state: State, rng: random.Random, config: NeighborConfig
    ) -> None:
        nonlocal calls
        calls += 1

    monkeypatch.setattr(
        hc_module, "generate_random_neighbor", no_neighbor, raising=False
    )
    result = run_scripted(STOCHASTIC, max_iterations=4)

    assert calls == 4
    assert result.iterations == 4
    assert result.metadata["termination_reason"] == "max_iterations"
    assert [event.metadata for event in result.history[1:]] == [
        {"sampled_neighbors": 0, "improving_candidates": 0}
    ] * 4
    assert all(event.accepted is False for event in result.history[1:])


# --- Random restart ---------------------------------------------------------


@pytest.mark.parametrize("max_restarts", [0, 1, 3])
def test_random_restart_count(multi_truck_problem: Problem, max_restarts: int) -> None:
    initial = generate_random_feasible_state(multi_truck_problem, random.Random(3))
    result = run_hc(
        multi_truck_problem,
        initial,
        variant=RANDOM_RESTART,
        max_restarts=max_restarts,
    )
    metadata = result.metadata
    assert metadata["restarts_performed"] == max_restarts
    assert metadata["termination_reason"] == "max_restarts"
    assert len(metadata["iterations_per_restart"]) == max_restarts + 1
    assert len(metadata["best_score_per_restart"]) == max_restarts + 1
    assert result.iterations == sum(metadata["iterations_per_restart"])
    assert result.best_score == max(metadata["best_score_per_restart"])
    restarts = [event.metadata["restart"] for event in result.history]
    assert sorted(set(restarts)) == list(range(max_restarts + 1))


def test_random_restart_uses_steepest_ascent_first(
    multi_truck_problem: Problem,
) -> None:
    initial = generate_random_feasible_state(multi_truck_problem, random.Random(3))
    restart = run_hc(
        multi_truck_problem, initial, variant=RANDOM_RESTART, max_restarts=0
    )
    steepest = run_hc(multi_truck_problem, initial, variant=STEEPEST)
    assert restart.best_state == steepest.best_state
    assert restart.final_state == steepest.final_state
    assert restart.iterations == steepest.iterations


def test_random_restart_keeps_best_across_restarts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    script(
        monkeypatch,
        [
            [loaded("valuable")],  # restart 0: climbs to 5
            [],  # restart 0: no neighbor, stop
            [],  # restart 1: fresh start has no neighbor
        ],
    )
    fresh_starts: list[State] = []

    def fake_initializer(
        problem: Problem, rng: random.Random, max_attempts_per_target: int = 30
    ) -> State:
        fresh_starts.append(outside(problem))
        return fresh_starts[-1]

    monkeypatch.setattr(hc_module, "generate_random_feasible_state", fake_initializer)
    result = run_scripted(RANDOM_RESTART, max_restarts=1)

    assert len(fresh_starts) == 1
    assert result.final_state == outside(SCRIPTED_PROBLEM)
    assert result.final_score == 0
    assert result.best_state == loaded("valuable").state
    assert result.best_score == 5
    assert result.metadata == {
        "restarts_performed": 1,
        "iterations_per_restart": [2, 1],
        "best_score_per_restart": [5, 0],
        "termination_reason": "max_restarts",
    }
    history = result.history
    assert [e.iteration for e in history] == [0, 1, 2, 3, 4]
    assert [e.metadata["restart"] for e in history] == [0, 0, 0, 1, 1]
    assert [e.current_score for e in history] == [0, 5, 5, 0, 0]
    assert [e.best_score for e in history] == [0, 5, 5, 5, 5]
