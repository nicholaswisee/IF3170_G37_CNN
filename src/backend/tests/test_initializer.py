"""Feasibility, seeded randomness, and bounded initial-state construction."""

import random
from unittest.mock import patch

import pytest

from app.domain import PackageSpec, Problem, TruckSpec, get_oriented_dimensions
from app.optimization import initializer
from app.optimization.constraints import ValidationResult, validate_state
from app.optimization.initializer import generate_random_feasible_state


class OutsideFirstRandom(random.Random):
    """Preserve order to exercise the explicit outside target."""

    def shuffle(self, values):
        pass


class TruckFirstRandom(OutsideFirstRandom):
    """Try trucks in order, at the origin of the highest candidate surface."""

    def shuffle(self, values):
        if None in values:
            values.remove(None)
            values.append(None)

    def randint(self, a, b):
        return a

    def choice(self, values):
        return values[-1]


def box(id_: str, **updates) -> PackageSpec:
    values = {
        "id": id_,
        "width": 1,
        "length": 1,
        "height": 1,
        "value": 1,
        "weight": 1,
        "is_fragile": False,
        "eta": 0,
    }
    return PackageSpec.model_validate(values | updates)


def truck(id_: str, **updates) -> TruckSpec:
    values = {"id": id_, "width": 1, "length": 1, "height": 1, "max_capacity": 10}
    return TruckSpec.model_validate(values | updates)


@pytest.mark.parametrize("seed", [0, 1, 2, 7, 42, 100])
@pytest.mark.parametrize(
    "fixture_name", ["single_truck_problem", "multi_truck_problem"]
)
def test_seeded_states_are_valid_complete_and_reproducible(
    request: pytest.FixtureRequest, fixture_name: str, seed: int
) -> None:
    problem = request.getfixturevalue(fixture_name)
    original = problem.model_dump_json()
    rng = random.Random(seed)
    state = generate_random_feasible_state(problem, rng)
    replay_rng = random.Random(seed)
    replay = generate_random_feasible_state(problem, replay_rng)

    assert validate_state(problem, state).valid
    assert sorted(p.package_id for p in state.placements) == sorted(
        p.id for p in problem.packages
    )
    assert state.model_dump_json() == replay.model_dump_json()
    assert rng.getstate() == replay_rng.getstate()
    assert problem.model_dump_json() == original
    assert all((p.truck_id is None) == (p.position is None) for p in state.placements)


def test_different_seeds_produce_variety(single_truck_problem: Problem) -> None:
    states = {
        generate_random_feasible_state(
            single_truck_problem, random.Random(seed)
        ).model_dump_json()
        for seed in range(20)
    }
    assert len(states) > 1


def test_does_not_use_module_global_randomness(
    single_truck_problem: Problem, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail(*args, **kwargs):
        pytest.fail("Initializer used module-global randomness")

    for name in ("random", "shuffle", "choice", "randint", "randrange", "seed"):
        monkeypatch.setattr(random, name, fail)
    state = generate_random_feasible_state(single_truck_problem, random.Random(42))
    assert validate_state(single_truck_problem, state).valid


def test_outside_target_stops_before_sampling(single_truck_problem: Problem) -> None:
    with patch.object(initializer, "sample_position") as sampler:
        state = generate_random_feasible_state(
            single_truck_problem, OutsideFirstRandom()
        )
    sampler.assert_not_called()
    assert all(p.truck_id is None and p.position is None for p in state.placements)


def test_empty_problem_still_gets_final_validation() -> None:
    problem = Problem(packages=[], trucks=[truck("a")])
    with patch.object(initializer, "validate_state", wraps=validate_state) as validator:
        state = generate_random_feasible_state(problem, random.Random(0))
    assert state.placements == []
    validator.assert_called_once_with(problem, state)


def test_multi_truck_fallback_after_first_truck_is_full() -> None:
    problem = Problem(packages=[box("p"), box("q")], trucks=[truck("a"), truck("b")])
    state = generate_random_feasible_state(problem, TruckFirstRandom(), 2)
    assert [p.truck_id for p in state.placements] == ["a", "b"]
    assert validate_state(problem, state).valid


@pytest.mark.parametrize(
    "package",
    [box("oversized", width=2, length=2, height=2), box("overweight", weight=11)],
)
def test_impossible_package_remains_outside(package: PackageSpec) -> None:
    problem = Problem(packages=[package], trucks=[truck("a"), truck("b")])
    state = generate_random_feasible_state(problem, TruckFirstRandom(), 2)
    assert state.placements[0].truck_id is None
    assert state.placements[0].position is None
    assert validate_state(problem, state).valid


def test_rotates_to_the_only_fitting_dimensions() -> None:
    package = box("p", width=3, length=2, height=1)
    problem = Problem(packages=[package], trucks=[truck("a", length=2, height=3)])
    state = generate_random_feasible_state(problem, TruckFirstRandom())
    placement = state.placements[0]
    assert placement.truck_id == "a"
    assert get_oriented_dimensions(package, placement.orientation) == (1, 2, 3)
    assert validate_state(problem, state).valid


@pytest.mark.parametrize("fragile", [False, True])
def test_samples_top_surfaces_and_rejects_fragile_support(fragile: bool) -> None:
    problem = Problem(
        packages=[box("base", is_fragile=fragile), box("top")],
        trucks=[truck("a", height=2)],
    )
    state = generate_random_feasible_state(problem, TruckFirstRandom(), 2)
    base, top = state.placements
    assert base.position is not None and base.position.z == 0
    if fragile:
        assert top.truck_id is None and top.position is None
    else:
        assert top.position is not None and top.position.z == 1
    assert validate_state(problem, state).valid


def test_rejected_candidates_have_bounded_attempts_per_truck() -> None:
    # All orientations fit geometrically, but every candidate is overweight.
    problem = Problem(
        packages=[box("p", width=1, length=2, height=3, weight=11)],
        trucks=[
            truck("a", width=3, length=3, height=3),
            truck("b", width=3, length=3, height=3),
        ],
    )
    with (
        patch.object(
            initializer, "sample_position", wraps=initializer.sample_position
        ) as sampler,
        patch.object(initializer, "validate_state", wraps=validate_state) as validator,
    ):
        state = generate_random_feasible_state(problem, TruckFirstRandom(), 7)
    assert sampler.call_count == 14
    assert validator.call_count == 15  # 14 rejected candidates plus final state.
    assert state.placements[0].truck_id is None


@pytest.mark.parametrize("attempts", [0, -1])
def test_rejects_nonpositive_attempt_limit(attempts: int) -> None:
    problem = Problem(packages=[], trucks=[truck("a")])
    with pytest.raises(ValueError, match="max_attempts_per_target must be positive"):
        generate_random_feasible_state(problem, random.Random(0), attempts)


def test_never_returns_state_that_fails_final_validation() -> None:
    problem = Problem(packages=[], trucks=[truck("a")])
    failure = ValidationResult(
        valid=False, errors=["unexpected invalid state"], truck_weights={}
    )
    with (
        patch.object(initializer, "validate_state", return_value=failure),
        pytest.raises(RuntimeError, match="unexpected invalid state"),
    ):
        generate_random_feasible_state(problem, random.Random(0))
