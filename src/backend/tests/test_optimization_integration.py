"""Exercise the shared optimization core through its public interfaces."""

import random

import numpy as np
import pytest

from app.domain import MoveType, Problem, State
from app.optimization.constraints import build_occupancies, validate_state
from app.optimization.initializer import generate_random_feasible_state
from app.optimization.neighbors import (
    NeighborCandidate,
    NeighborConfig,
    generate_random_neighbor,
    sample_valid_neighbors,
    state_signature,
)
from app.optimization.objective import ObjectiveMode, evaluate_objective

# Independently calculated contributions for the shared three-package fixtures.
CONTRIBUTIONS = {
    ObjectiveMode.TOTAL_VALUE: {"base": 10.0, "top": 5.0, "fragile": 4.0},
    ObjectiveMode.ETA_WEIGHTED_VALUE: {"base": 5.0, "top": 5 / 3, "fragile": 4.0},
}
WEIGHTS = {"base": 3.0, "top": 2.0, "fragile": 1.0}


def assert_core_consistent(problem: Problem, state: State) -> None:
    """Cross-check placement, occupancy, weight, and both objective views."""
    result = validate_state(problem, state)
    assert result.valid, result.errors
    grids = build_occupancies(problem, state)
    occupied_ids = set()
    for truck in problem.trucks:
        indices = set(np.unique(grids[truck.id])) - {-1}
        ids = {problem.packages[int(index)].id for index in indices}
        assert ids == {p.package_id for p in state.placements if p.truck_id == truck.id}
        assert occupied_ids.isdisjoint(ids)
        occupied_ids.update(ids)
        assert result.truck_weights[truck.id] == pytest.approx(
            sum(WEIGHTS[id_] for id_ in ids)
        )
    for mode, contributions in CONTRIBUTIONS.items():
        assert evaluate_objective(problem, state, mode) == pytest.approx(
            sum(contributions[id_] for id_ in occupied_ids)
        )


def assert_move_score_consistent(
    problem: Problem, source: State, candidate: NeighborCandidate
) -> None:
    before = {p.package_id: p for p in source.placements}
    after = {p.package_id: p for p in candidate.state.placements}
    for old, new in zip(candidate.move.before, candidate.move.after, strict=True):
        assert old == before[old.package_id]
        assert new == after[new.package_id]
    for mode, values in CONTRIBUTIONS.items():
        delta = sum(
            values[new.package_id] * (new.truck_id is not None)
            - values[old.package_id] * (old.truck_id is not None)
            for old, new in zip(
                candidate.move.before, candidate.move.after, strict=True
            )
        )
        assert evaluate_objective(problem, candidate.state, mode) == pytest.approx(
            evaluate_objective(problem, source, mode) + delta
        )


@pytest.mark.parametrize(
    "fixture_name", ["single_truck_problem", "multi_truck_problem"]
)
@pytest.mark.parametrize("seed", [0, 7, 42])
def test_seeded_initializer_neighbor_pipeline_replays_after_json_round_trip(
    request: pytest.FixtureRequest, fixture_name: str, seed: int
) -> None:
    problem = request.getfixturevalue(fixture_name)
    problem_json = problem.model_dump_json()
    restored_problem = Problem.model_validate_json(problem_json)
    rng, replay_rng = random.Random(seed), random.Random(seed)
    state = generate_random_feasible_state(problem, rng)
    replay = generate_random_feasible_state(restored_problem, replay_rng)
    assert state == replay
    assert_core_consistent(problem, state)

    config = NeighborConfig()
    for _ in range(8):
        original = state.model_dump_json()
        # A serialized state must remain usable by all shared core functions.
        replay = State.model_validate_json(replay.model_dump_json())
        candidate = generate_random_neighbor(problem, state, rng, config)
        replay_candidate = generate_random_neighbor(
            restored_problem, replay, replay_rng, config
        )
        assert candidate is not None
        assert replay_candidate is not None
        assert candidate.model_dump_json() == replay_candidate.model_dump_json()
        assert rng.getstate() == replay_rng.getstate()
        assert state.model_dump_json() == original
        assert_core_consistent(problem, candidate.state)
        assert_move_score_consistent(problem, state, candidate)
        state, replay = candidate.state, replay_candidate.state
    assert problem.model_dump_json() == problem_json


@pytest.mark.parametrize(
    ("move_type", "config"),
    [
        (
            MoveType.RELOCATE,
            NeighborConfig(
                relocate_probability=1, rotate_probability=0, swap_probability=0
            ),
        ),
        (
            MoveType.ROTATE,
            NeighborConfig(
                relocate_probability=0, rotate_probability=1, swap_probability=0
            ),
        ),
        (
            MoveType.SWAP,
            NeighborConfig(
                relocate_probability=0, rotate_probability=0, swap_probability=1
            ),
        ),
    ],
)
def test_each_move_type_accepts_initialized_fleet_without_changing_source(
    multi_truck_problem: Problem, move_type: MoveType, config: NeighborConfig
) -> None:
    problem = multi_truck_problem
    rng = random.Random(7)
    state = generate_random_feasible_state(problem, rng)
    # Check that consumers identify packages by ID, regardless of placement order.
    state.placements.reverse()
    original = state.model_dump_json()
    candidates = sample_valid_neighbors(problem, state, rng, 8, config)
    assert candidates
    signatures = {state_signature(candidate.state) for candidate in candidates}
    assert len(signatures) == len(candidates)
    assert state_signature(state) not in signatures
    for candidate in candidates:
        assert candidate.move.type is move_type
        assert_core_consistent(problem, candidate.state)
        assert_move_score_consistent(problem, state, candidate)
        if move_type is MoveType.ROTATE:
            for mode in ObjectiveMode:
                assert evaluate_objective(problem, candidate.state, mode) == (
                    evaluate_objective(problem, state, mode)
                )
    assert state.model_dump_json() == original

    # A caller may modify one candidate without corrupting its source or siblings.
    snapshots = [candidate.model_dump_json() for candidate in candidates[1:]]
    candidates[0].state.placements[0].package_id = "changed-by-caller"
    assert state.model_dump_json() == original
    assert [candidate.model_dump_json() for candidate in candidates[1:]] == snapshots


@pytest.mark.parametrize("empty", [False, True])
def test_no_feasible_loading_produces_zero_scores_and_no_neighbors(
    single_truck_problem: Problem, empty: bool
) -> None:
    problem = Problem(
        packages=[] if empty else single_truck_problem.packages,
        trucks=[
            truck.model_copy(update={"max_capacity": 0.0})
            for truck in single_truck_problem.trucks
        ],
    )
    rng = random.Random(42)
    state = generate_random_feasible_state(problem, rng)
    original = state.model_dump_json()
    assert_core_consistent(problem, state)
    assert all(p.truck_id is None for p in state.placements)
    for mode in ObjectiveMode:
        assert evaluate_objective(problem, state, mode) == 0.0
    assert generate_random_neighbor(problem, state, rng, NeighborConfig()) is None
    assert sample_valid_neighbors(problem, state, rng, 3, NeighborConfig()) == []
    assert state.model_dump_json() == original
