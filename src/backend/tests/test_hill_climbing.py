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

SIDEWAYS = HillClimbingVariant.SIDEWAYS


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


def run_sideways(
    problem: Problem,
    initial: State,
    *,
    seed: int = 42,
    include_state_history: bool = True,
    objective_mode: ObjectiveMode = ObjectiveMode.TOTAL_VALUE,
    **parameters: int,
) -> SearchResult:
    # Tiny problems have fewer valid neighbors than the default batch size, so
    # each iteration spends the full proposal budget; keep plateaus short.
    parameters = {"candidates_per_iteration": 20, "max_sideways": 5, **parameters}
    return HillClimbing(SIDEWAYS).run(
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

    result = run_sideways(problem, initial, seed=seed, max_iterations=200)

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
    result = run_sideways(single_truck_problem, outside(single_truck_problem))
    # All three packages fit together under the 10-unit capacity.
    assert result.best_score == 19
    assert result.metadata["termination_reason"] in {"max_sideways", "local_optimum"}


def test_sideways_moves_packages_between_trucks(multi_truck_problem: Problem) -> None:
    result = run_sideways(multi_truck_problem, outside(multi_truck_problem))
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
    first = run_sideways(
        multi_truck_problem, initial, include_state_history=include_state_history
    )
    second = run_sideways(
        multi_truck_problem, initial, include_state_history=include_state_history
    )
    assert first == second


def test_eta_weighted_objective_is_used(single_truck_problem: Problem) -> None:
    mode = ObjectiveMode.ETA_WEIGHTED_VALUE
    result = run_sideways(
        single_truck_problem, outside(single_truck_problem), objective_mode=mode
    )
    assert result.best_score == evaluate_objective(
        single_truck_problem, result.best_state, mode
    )
    assert result.best_score == pytest.approx(10 / 2 + 5 / 3 + 4 / 1)


def test_history_records_every_iteration(multi_truck_problem: Problem) -> None:
    result = run_sideways(multi_truck_problem, outside(multi_truck_problem))
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
    result = run_sideways(
        single_truck_problem,
        outside(single_truck_problem),
        include_state_history=False,
    )
    assert all(event.state_snapshot is None for event in result.history)


def test_returned_states_do_not_alias_input(single_truck_problem: Problem) -> None:
    initial = generate_random_feasible_state(single_truck_problem, random.Random(1))
    original = initial.model_dump_json()
    result = run_sideways(single_truck_problem, initial, max_iterations=1)
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
    result = run_sideways(
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
    result = run_sideways(
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
    ],
    trucks=[TruckSpec(id="t", width=4, length=1, height=1, max_capacity=10)],
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


def run_scripted(**parameters: int) -> SearchResult:
    return run_sideways(SCRIPTED_PROBLEM, outside(SCRIPTED_PROBLEM), **parameters)


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
        result = run_sideways(SCRIPTED_PROBLEM, outside(SCRIPTED_PROBLEM), seed=seed)
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


@pytest.mark.parametrize(
    "variant",
    [
        HillClimbingVariant.STEEPEST_ASCENT,
        HillClimbingVariant.STOCHASTIC,
        HillClimbingVariant.RANDOM_RESTART,
    ],
)
def test_remaining_variants_are_explicitly_pending(
    single_truck_problem: Problem, variant: HillClimbingVariant
) -> None:
    with pytest.raises(NotImplementedError, match="not implemented yet"):
        HillClimbing(variant).run(
            single_truck_problem,
            outside(single_truck_problem),
            objective_mode=ObjectiveMode.TOTAL_VALUE,
            rng=random.Random(0),
            parameters=HillClimbingParameters(),
            include_state_history=False,
        )
