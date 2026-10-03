"""Shared neighbor engine: RELOCATE / ROTATE / SWAP semantics and sampling."""

import random

import pytest
from pydantic import ValidationError

from app.domain import (
    MoveType,
    Orientation,
    PackagePlacement,
    PackageSpec,
    Position,
    Problem,
    State,
    TruckSpec,
    get_oriented_dimensions,
)
from app.optimization.constraints import validate_state
from app.optimization.neighbors import (
    NeighborCandidate,
    NeighborConfig,
    generate_random_neighbor,
    propose_relocate,
    propose_rotate,
    sample_valid_neighbors,
    state_signature,
)

SEEDS = range(200)
ONLY_RELOCATE = NeighborConfig(
    relocate_probability=1, rotate_probability=0, swap_probability=0
)
ONLY_ROTATE = NeighborConfig(
    relocate_probability=0, rotate_probability=1, swap_probability=0
)
ONLY_SWAP = NeighborConfig(
    relocate_probability=0, rotate_probability=0, swap_probability=1
)


def box(
    id_: str, width: int, length: int, height: int, weight: float = 1
) -> PackageSpec:
    return PackageSpec(
        id=id_,
        width=width,
        length=length,
        height=height,
        value=1,
        weight=weight,
        is_fragile=False,
        eta=0,
    )


def truck(id_: str, width: int, length: int, height: int) -> TruckSpec:
    return TruckSpec(
        id=id_, width=width, length=length, height=height, max_capacity=100
    )


def loaded(
    package_id: str,
    truck_id: str,
    x: int,
    y: int,
    z: int,
    orientation: Orientation = Orientation.WLH,
) -> PackagePlacement:
    return PackagePlacement(
        package_id=package_id,
        truck_id=truck_id,
        position=Position(x=x, y=y, z=z),
        orientation=orientation,
    )


def outside(package_id: str) -> PackagePlacement:
    return PackagePlacement(package_id=package_id)


def placement_of(state: State, package_id: str) -> PackagePlacement:
    return next(p for p in state.placements if p.package_id == package_id)


def assert_only_moved_packages_changed(
    original: State, candidate: NeighborCandidate
) -> None:
    for before, after in zip(original.placements, candidate.state.placements):
        if before.package_id not in candidate.move.package_ids:
            assert before == after
    for package_id, before, after in zip(
        candidate.move.package_ids, candidate.move.before, candidate.move.after
    ):
        assert placement_of(original, package_id) == before
        assert placement_of(candidate.state, package_id) == after


def test_config_defaults_and_probability_sum() -> None:
    config = NeighborConfig()
    assert (config.relocate_probability, config.rotate_probability) == (0.5, 0.25)
    assert (config.swap_probability, config.max_attempts) == (0.25, 30)
    with pytest.raises(ValidationError, match="sum to 1.0"):
        NeighborConfig(relocate_probability=0.5, rotate_probability=0.5)
    with pytest.raises(ValidationError):
        NeighborConfig(max_attempts=0)


def test_relocate_outside_to_truck(single_truck_problem: Problem) -> None:
    state = State(placements=[outside(p.id) for p in single_truck_problem.packages])
    for seed in SEEDS:
        candidate = propose_relocate(single_truck_problem, state, random.Random(seed))
        # Outside is not a target for an outside package, and every package fits.
        assert candidate is not None
        assert candidate.move.type is MoveType.RELOCATE
        [before], [after] = candidate.move.before, candidate.move.after
        assert before.truck_id is None and after.truck_id == "truck-a"
        assert after.orientation == before.orientation
        assert_only_moved_packages_changed(state, candidate)


def test_relocate_truck_to_outside_when_no_other_coordinate_exists() -> None:
    problem = Problem(packages=[box("a", 1, 1, 1)], trucks=[truck("t", 1, 1, 1)])
    state = State(placements=[loaded("a", "t", 0, 0, 0)])
    for seed in SEEDS:
        candidate = generate_random_neighbor(
            problem, state, random.Random(seed), ONLY_RELOCATE
        )
        assert candidate is not None
        assert candidate.state.placements == [outside("a")]


def test_relocate_covers_same_truck_cross_truck_and_outside(
    multi_truck_problem: Problem,
) -> None:
    state = State(
        placements=[
            outside("base"),
            loaded("top", "truck-a", 0, 0, 0),
            outside("fragile"),
        ]
    )
    transitions = set()
    for seed in SEEDS:
        candidate = generate_random_neighbor(
            multi_truck_problem, state, random.Random(seed), ONLY_RELOCATE
        )
        assert candidate is not None
        assert validate_state(multi_truck_problem, candidate.state).valid
        assert_only_moved_packages_changed(state, candidate)
        [before], [after] = candidate.move.before, candidate.move.after
        assert after.orientation == before.orientation
        transitions.add((before.truck_id, after.truck_id))

    assert {
        ("truck-a", "truck-a"),
        ("truck-a", "truck-b"),
        ("truck-a", None),
        (None, "truck-a"),
        (None, "truck-b"),
    } <= transitions


def test_relocate_rejects_removing_support(single_truck_problem: Problem) -> None:
    state = State(
        placements=[
            loaded("base", "truck-a", 0, 0, 0),
            loaded("top", "truck-a", 0, 0, 1),
            outside("fragile"),
        ]
    )
    rejected = 0
    for seed in SEEDS:
        proposal = propose_relocate(single_truck_problem, state, random.Random(seed))
        if proposal is None or proposal.move.package_ids != ["base"]:
            continue
        if placement_of(proposal.state, "base").truck_id is None:
            result = validate_state(single_truck_problem, proposal.state)
            assert not result.valid
            assert any("top is floating" in error for error in result.errors)
            rejected += 1
    assert rejected > 0

    for seed in SEEDS:
        candidate = generate_random_neighbor(
            single_truck_problem, state, random.Random(seed), ONLY_RELOCATE
        )
        assert candidate is not None
        assert validate_state(single_truck_problem, candidate.state).valid


def test_rotate_changes_shape_but_keeps_truck_and_anchor() -> None:
    problem = Problem(packages=[box("a", 1, 2, 3)], trucks=[truck("t", 4, 4, 4)])
    state = State(placements=[loaded("a", "t", 0, 0, 0)])
    seen = set()
    for seed in SEEDS:
        candidate = generate_random_neighbor(
            problem, state, random.Random(seed), ONLY_ROTATE
        )
        assert candidate is not None
        assert candidate.move.type is MoveType.ROTATE
        [after] = candidate.state.placements
        assert (after.truck_id, after.position) == ("t", Position(x=0, y=0, z=0))
        dimensions = get_oriented_dimensions(problem.packages[0], after.orientation)
        assert dimensions != (1, 2, 3)
        seen.add(after.orientation)
    assert seen == set(Orientation) - {Orientation.WLH}


def test_rotate_rejects_out_of_bounds_shapes() -> None:
    problem = Problem(packages=[box("a", 1, 2, 3)], trucks=[truck("t", 1, 2, 3)])
    state = State(placements=[loaded("a", "t", 0, 0, 0)])
    assert propose_rotate(problem, state, random.Random(0)) is not None
    assert (
        generate_random_neighbor(problem, state, random.Random(0), ONLY_ROTATE) is None
    )


def test_rotate_revalidates_support_of_other_packages() -> None:
    # Base spans x=0..1; rotating it to width 1 leaves top at x=1 floating.
    problem = Problem(
        packages=[box("base", 2, 1, 1), box("top", 1, 1, 1)],
        trucks=[truck("t", 2, 2, 3)],
    )
    state = State(
        placements=[loaded("base", "t", 0, 0, 0), loaded("top", "t", 1, 0, 1)]
    )
    rejected = 0
    for seed in SEEDS:
        # Top is a cube, so only base rotations are proposed.
        proposal = propose_rotate(problem, state, random.Random(seed))
        if proposal is not None:
            assert proposal.move.package_ids == ["base"]
            result = validate_state(problem, proposal.state)
            assert any("top is floating" in error for error in result.errors)
            rejected += 1
    assert rejected > 0
    # Every distinct base shape strands top, so no valid rotation exists.
    assert (
        generate_random_neighbor(problem, state, random.Random(0), ONLY_ROTATE) is None
    )


def test_rotate_skips_outside_packages_and_cubes() -> None:
    problem = Problem(
        packages=[box("cube", 2, 2, 2), box("bar", 1, 1, 3)],
        trucks=[truck("t", 4, 4, 4)],
    )
    all_outside = State(placements=[outside("cube"), outside("bar")])
    only_cube = State(placements=[loaded("cube", "t", 0, 0, 0), outside("bar")])
    for seed in SEEDS:
        assert propose_rotate(problem, all_outside, random.Random(seed)) is None
        assert propose_rotate(problem, only_cube, random.Random(seed)) is None


@pytest.mark.parametrize(
    ("trucks", "placements"),
    [
        pytest.param(
            [truck("t", 4, 1, 1)],
            [loaded("a", "t", 0, 0, 0), loaded("b", "t", 2, 0, 0, Orientation.HLW)],
            id="same-truck",
        ),
        pytest.param(
            [truck("t", 2, 1, 1), truck("u", 2, 1, 1)],
            [loaded("a", "t", 0, 0, 0), loaded("b", "u", 0, 0, 0, Orientation.HLW)],
            id="cross-truck",
        ),
        pytest.param(
            [truck("t", 2, 1, 2)],
            [loaded("a", "t", 0, 0, 0), outside("b")],
            id="loaded-outside",
        ),
    ],
)
def test_swap_exchanges_assignment_and_keeps_orientation(
    trucks: list[TruckSpec], placements: list[PackagePlacement]
) -> None:
    problem = Problem(packages=[box("a", 1, 1, 1), box("b", 1, 1, 2)], trucks=trucks)
    state = State(placements=placements)
    assert validate_state(problem, state).valid

    candidate = generate_random_neighbor(problem, state, random.Random(0), ONLY_SWAP)
    assert candidate is not None
    assert candidate.move.type is MoveType.SWAP
    assert sorted(candidate.move.package_ids) == ["a", "b"]
    a_before, b_before = placements
    a_after = placement_of(candidate.state, "a")
    b_after = placement_of(candidate.state, "b")
    assert (a_after.truck_id, a_after.position) == (
        b_before.truck_id,
        b_before.position,
    )
    assert (b_after.truck_id, b_after.position) == (
        a_before.truck_id,
        a_before.position,
    )
    assert a_after.orientation == a_before.orientation
    assert b_after.orientation == b_before.orientation
    assert_only_moved_packages_changed(state, candidate)


def test_swap_rejects_geometric_misfit_and_double_outside() -> None:
    problem = Problem(
        packages=[box("small", 1, 1, 1), box("big", 3, 3, 3), box("other", 1, 1, 1)],
        trucks=[truck("t", 1, 1, 1)],
    )
    misfit = State(placements=[loaded("small", "t", 0, 0, 0), outside("big")])
    problem_pair = Problem(packages=problem.packages[:2], trucks=problem.trucks)
    assert (
        generate_random_neighbor(problem_pair, misfit, random.Random(0), ONLY_SWAP)
        is None
    )

    both_outside = Problem(
        packages=[problem.packages[1], problem.packages[2]], trucks=problem.trucks
    )
    empty = State(placements=[outside("big"), outside("other")])
    assert (
        generate_random_neighbor(both_outside, empty, random.Random(0), ONLY_SWAP)
        is None
    )


def test_original_state_is_never_mutated(multi_truck_problem: Problem) -> None:
    state = State(
        placements=[
            loaded("base", "truck-b", 0, 0, 0, Orientation.WLH),
            loaded("top", "truck-a", 0, 0, 0),
            outside("fragile"),
        ]
    )
    snapshot = state.model_dump_json()
    for seed in SEEDS:
        rng = random.Random(seed)
        candidates = sample_valid_neighbors(
            multi_truck_problem, state, rng, 5, NeighborConfig()
        )
        candidate = generate_random_neighbor(
            multi_truck_problem, state, rng, NeighborConfig()
        )
        if candidate is not None:
            candidates.append(candidate)
        for candidate in candidates:
            assert_only_moved_packages_changed(state, candidate)
            # Candidates must not share mutable placement objects with the input.
            for placement in candidate.state.placements + candidate.move.after:
                if placement.position is not None:
                    placement.position.x += 100
                placement.orientation = Orientation.HLW
    assert state.model_dump_json() == snapshot


def test_retry_terminates_without_valid_neighbor() -> None:
    problem = Problem(packages=[box("huge", 5, 5, 5)], trucks=[truck("t", 2, 2, 2)])
    state = State(placements=[outside("huge")])
    config = NeighborConfig(max_attempts=5)
    assert generate_random_neighbor(problem, state, random.Random(0), config) is None
    assert sample_valid_neighbors(problem, state, random.Random(0), 10, config) == []


def test_same_seed_reproduces_neighbors(multi_truck_problem: Problem) -> None:
    state = State(
        placements=[
            outside("base"),
            loaded("top", "truck-a", 1, 1, 0),
            outside("fragile"),
        ]
    )

    def run(seed: int) -> list[str]:
        rng = random.Random(seed)
        batch = sample_valid_neighbors(
            multi_truck_problem, state, rng, 8, NeighborConfig()
        )
        single = generate_random_neighbor(
            multi_truck_problem, state, rng, NeighborConfig()
        )
        return [c.model_dump_json() for c in batch] + [
            single.model_dump_json() if single else ""
        ]

    assert run(42) == run(42)
    assert run(42) != run(123)


def test_sample_valid_neighbors_are_valid_distinct_and_new(
    multi_truck_problem: Problem,
) -> None:
    state = State(
        placements=[
            outside("base"),
            loaded("top", "truck-a", 0, 0, 0),
            outside("fragile"),
        ]
    )
    neighbors = sample_valid_neighbors(
        multi_truck_problem, state, random.Random(7), 20, NeighborConfig()
    )
    signatures = [state_signature(n.state) for n in neighbors]
    assert 0 < len(neighbors) <= 20
    assert len(set(signatures)) == len(signatures)
    assert state_signature(state) not in signatures
    assert all(validate_state(multi_truck_problem, n.state).valid for n in neighbors)


def test_sample_valid_neighbors_stops_when_neighborhood_is_small() -> None:
    problem = Problem(packages=[box("a", 1, 1, 1)], trucks=[truck("t", 1, 1, 1)])
    state = State(placements=[loaded("a", "t", 0, 0, 0)])
    neighbors = sample_valid_neighbors(
        problem, state, random.Random(0), 10, NeighborConfig()
    )
    assert [n.state.placements for n in neighbors] == [[outside("a")]]


def test_state_signature_ignores_placement_order(single_truck_problem: Problem) -> None:
    placements = [
        loaded("base", "truck-a", 0, 0, 0),
        outside("top"),
        loaded("fragile", "truck-a", 3, 3, 0, Orientation.LWH),
    ]
    forward = State(placements=placements)
    backward = State(placements=list(reversed(placements)))
    assert state_signature(forward) == state_signature(backward)
    moved = State(placements=[*placements[:2], loaded("fragile", "truck-a", 3, 3, 0)])
    assert state_signature(moved) != state_signature(forward)
