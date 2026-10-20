import math
import random

import pytest

from app.domain.package import PackageSpec
from app.domain.problem import Problem
from app.domain.state import State
from app.domain.truck import PackagePlacement, Position, TruckSpec
from app.optimization.algorithms import genetic_algorithm as ga
from app.optimization.algorithms.genetic_algorithm import (
    GeneticAlgorithm,
    _penalized_fitness,
    roulette_select,
    single_point_crossover,
)
from app.optimization.constraints import validate_state
from app.optimization.initializer import generate_random_feasible_state
from app.optimization.objective import ObjectiveMode, evaluate_objective
from app.schemas.experiment import GeneticAlgorithmParameters


def test_roulette_zero_fitness_samples_each_individual_by_identity() -> None:
    population = [
        State(placements=[PackagePlacement(package_id=str(i))]) for i in range(4)
    ]
    rng = random.Random(7)
    selected = [roulette_select(population, [0, 0, 0, 0], rng) for _ in range(100)]
    assert {id(state) for state in selected} == {id(state) for state in population}


def test_roulette_prefers_higher_fitness() -> None:
    population = [
        State(placements=[PackagePlacement(package_id=str(i))]) for i in range(3)
    ]
    rng = random.Random(7)
    selected = [roulette_select(population, [1, 0, 9], rng) for _ in range(1000)]
    assert sum(state is population[2] for state in selected) > 800
    assert all(state is not population[1] for state in selected)
    assert any(state is population[0] for state in selected)


def test_roulette_accepts_large_finite_fitness_without_overflow() -> None:
    population = [
        State(placements=[PackagePlacement(package_id=str(i))]) for i in range(2)
    ]
    selected = [
        roulette_select(population, [1e308, 1e308], random.Random(i)) for i in range(20)
    ]
    assert set(map(id, selected)) == set(map(id, population))


def test_run_mean_of_large_finite_fitness_remains_finite() -> None:
    problem = Problem(
        packages=[_package("p", value=1e308)], trucks=[_truck("t", 1, 1, 1)]
    )
    result = GeneticAlgorithm().run(
        problem,
        None,
        objective_mode=ObjectiveMode.TOTAL_VALUE,
        rng=random.Random(1),
        parameters=GeneticAlgorithmParameters(population_size=2, generations=1),
        include_state_history=False,
    )
    assert all(0 <= event.mean_score <= 1e308 for event in result.history)
    assert all(math.isfinite(event.mean_score) for event in result.history)


def test_run_mean_handles_max_float_population() -> None:
    problem = Problem(
        packages=[_package("p", value=float.fromhex("0x1.fffffffffffffp+1023"))],
        trucks=[_truck("t", 1, 1, 1)],
    )
    result = GeneticAlgorithm().run(
        problem,
        None,
        objective_mode=ObjectiveMode.TOTAL_VALUE,
        rng=random.Random(0),
        parameters=GeneticAlgorithmParameters(population_size=3, generations=1),
        include_state_history=False,
    )
    assert result.history[1].mean_score == pytest.approx(4 / 3)
    assert all(math.isfinite(event.mean_score) for event in result.history)


def test_roulette_endpoint_does_not_select_zero_fitness() -> None:
    population = [
        State(placements=[PackagePlacement(package_id=str(i))]) for i in range(4)
    ]

    class EndpointRng:
        @staticmethod
        def random() -> float:
            return 1 - 2**-53

    selected = roulette_select(population, [1.0, 0.2, 0.6, 0.0], EndpointRng())
    assert selected is population[2]


def test_crossover_uses_one_package_order_cut_and_copies_genes(
    single_truck_problem: Problem,
) -> None:
    a = State(
        placements=[
            PackagePlacement(
                package_id="base", truck_id="truck-a", position=Position(x=0, y=0, z=0)
            ),
            PackagePlacement(package_id="top"),
            PackagePlacement(package_id="fragile"),
        ]
    )
    b = State(
        placements=[
            PackagePlacement(
                package_id="fragile",
                truck_id="truck-a",
                position=Position(x=3, y=3, z=0),
            ),
            PackagePlacement(package_id="base"),
            PackagePlacement(
                package_id="top", truck_id="truck-a", position=Position(x=3, y=0, z=0)
            ),
        ]
    )

    class CutRng:
        @staticmethod
        def randrange(start: int, stop: int) -> int:
            assert start == 1 and stop == len(single_truck_problem.packages)
            return 1

        @staticmethod
        def random() -> float:
            return 0.0

    child = single_point_crossover(single_truck_problem, a, b, CutRng())
    assert {p.package_id for p in child.placements} == {"base", "top", "fragile"}
    parents = {
        p.package_id: (p, next(q for q in b.placements if q.package_id == p.package_id))
        for p in a.placements
    }
    for index, placement in enumerate(child.placements):
        parent_a, parent_b = parents[placement.package_id]
        assert placement == (parent_a if index < 1 else parent_b)
        assert placement == parent_a or placement == parent_b
        assert placement is not parent_a and placement is not parent_b
        for parent in (parent_a, parent_b):
            if placement.position is not None and placement.position is parent.position:
                pytest.fail("crossover shared a mutable Position with a parent")


@pytest.mark.parametrize(
    ("raw", "upper", "violations", "expected"),
    [
        (50, 100, 0, 1.5),
        (50, 100, 1, 0.25),
        (50, 100, 3, 0.125),
        (0, 0, 0, 1.0),
        (0, 0, 1, 0.0),
        (100.00000000000001, 100, 0, 2.0),
        (5e-324, 1e-323, 0, 1.5),
    ],
)
def test_penalized_fitness_values(raw, upper, violations, expected) -> None:
    assert _penalized_fitness(raw, upper, violations) == expected


def test_invalid_maximum_is_ranked_below_feasible_zero() -> None:
    assert _penalized_fitness(100, 100, 1) < _penalized_fitness(0, 100, 0)


def test_impossible_package_search_terminates_with_feasible_history() -> None:
    problem = Problem(
        packages=[_package("too-large", width=3)], trucks=[_truck("truck-a", 1, 1, 1)]
    )
    result = GeneticAlgorithm().run(
        problem,
        None,
        objective_mode=ObjectiveMode.TOTAL_VALUE,
        rng=random.Random(1),
        parameters=GeneticAlgorithmParameters(population_size=2, generations=2),
        include_state_history=True,
    )
    assert len(result.history) == 3
    assert all(
        event.state_snapshot is not None
        and validate_state(problem, event.state_snapshot).valid
        for event in result.history
    )
    assert all(event.mean_score == 1 for event in result.history)


def test_run_is_seeded_feasible_and_records_initial_champion(
    multi_truck_problem: Problem,
) -> None:
    config = GeneticAlgorithmParameters(population_size=5, generations=3)
    algorithm = GeneticAlgorithm()
    results = [
        algorithm.run(
            multi_truck_problem,
            None,
            objective_mode=ObjectiveMode.TOTAL_VALUE,
            rng=random.Random(42),
            parameters=config,
            include_state_history=False,
        )
        for _ in range(2)
    ]
    result = results[0]
    assert result == results[1]
    assert validate_state(multi_truck_problem, result.final_state).valid
    assert len(result.history) == 4
    assert all(event.state_snapshot is None for event in result.history)
    initial_state = State.model_validate(result.metadata["initial_state"])
    assert validate_state(multi_truck_problem, initial_state).valid
    assert result.metadata["initial_score"] == evaluate_objective(
        multi_truck_problem, initial_state, ObjectiveMode.TOTAL_VALUE
    )
    assert result.final_score == evaluate_objective(
        multi_truck_problem, result.final_state, ObjectiveMode.TOTAL_VALUE
    )
    assert all(
        result.history[i + 1].best_score >= result.history[i].best_score
        for i in range(3)
    )


def test_run_includes_valid_supplied_state_without_mutating_it(
    single_truck_problem: Problem,
) -> None:
    initial = generate_random_feasible_state(single_truck_problem, random.Random(8))
    before = initial.model_dump_json()
    result = GeneticAlgorithm().run(
        single_truck_problem,
        initial,
        objective_mode=ObjectiveMode.TOTAL_VALUE,
        rng=random.Random(9),
        parameters=GeneticAlgorithmParameters(population_size=2, generations=1),
        include_state_history=True,
    )
    assert initial.model_dump_json() == before
    assert result.metadata["initial_score"] == evaluate_objective(
        single_truck_problem, initial, ObjectiveMode.TOTAL_VALUE
    )
    assert State.model_validate(result.metadata["initial_state"]) == initial


def test_run_rejects_invalid_supplied_state(single_truck_problem: Problem) -> None:
    with pytest.raises(ValueError, match="initial_state"):
        GeneticAlgorithm().run(
            single_truck_problem,
            State(placements=[]),
            objective_mode=ObjectiveMode.TOTAL_VALUE,
            rng=random.Random(1),
            parameters=GeneticAlgorithmParameters(population_size=2, generations=1),
            include_state_history=False,
        )


def test_empty_problem_run_terminates() -> None:
    problem = Problem(packages=[], trucks=[_truck("truck-a", 2, 2, 2)])
    result = GeneticAlgorithm().run(
        problem,
        None,
        objective_mode=ObjectiveMode.TOTAL_VALUE,
        rng=random.Random(1),
        parameters=GeneticAlgorithmParameters(population_size=2, generations=1),
        include_state_history=False,
    )
    assert result.final_state.placements == []
    assert len(result.history) == 2


@pytest.mark.parametrize(
    "violation", ["bounds", "overlap", "floating", "fragile", "capacity"]
)
def test_physical_constraint_offspring_remain_unchanged_and_are_penalized(
    monkeypatch, violation
):
    problem, invalid = _physical_violation(violation)
    valid_archive = State(
        placements=[PackagePlacement(package_id=p.id) for p in problem.packages]
    )
    monkeypatch.setattr(
        ga,
        "generate_random_feasible_state",
        lambda *_: valid_archive.model_copy(deep=True),
    )
    monkeypatch.setattr(
        ga, "single_point_crossover", lambda *_: invalid.model_copy(deep=True)
    )
    real_validate = ga.validate_state
    scored_population = []

    def observe_validation(problem_arg, state):
        result = real_validate(problem_arg, state)
        if state != valid_archive and state.model_dump(
            mode="json"
        ) == invalid.model_dump(mode="json"):
            scored_population.append((state.model_dump(mode="json"), result))
        return result

    monkeypatch.setattr(ga, "validate_state", observe_validation)
    result = GeneticAlgorithm().run(
        problem,
        valid_archive,
        objective_mode=ObjectiveMode.TOTAL_VALUE,
        rng=random.Random(3),
        parameters=GeneticAlgorithmParameters(
            population_size=2,
            generations=1,
            mutation_probability=0,
        ),
        include_state_history=True,
    )
    assert len(scored_population) == 2
    assert all(
        state_json == invalid.model_dump(mode="json")
        for state_json, _ in scored_population
    )
    assert all(not validation.valid for _, validation in scored_population)
    expected_error = {
        "bounds": "out of bounds",
        "overlap": "overlaps another",
        "floating": "floating",
        "fragile": "fragile support",
        "capacity": "exceeds capacity",
    }[violation]
    assert any(expected_error in error for error in scored_population[0][1].errors)
    errors = len(scored_population[0][1].errors)
    assert result.history[1].metadata["infeasible_count"] == 2
    assert result.history[1].metadata["max_fitness"] == pytest.approx(1 / (1 + errors))
    assert result.history[1].mean_score == pytest.approx(1 / (1 + errors))
    assert result.history[1].state_snapshot == valid_archive
    assert result.metadata["final_state_fallback"] is True
    assert result.final_state == valid_archive


def _physical_violation(kind):
    truck = _truck("t", 3, 1, 3)
    packages = [_package("a"), _package("b")]
    placements = [
        PackagePlacement(
            package_id="a", truck_id="t", position=Position(x=0, y=0, z=0)
        ),
        PackagePlacement(
            package_id="b", truck_id="t", position=Position(x=1, y=0, z=0)
        ),
    ]
    if kind == "bounds":
        packages, placements = packages[:1], placements[:1]
        placements[0] = PackagePlacement(
            package_id="a", truck_id="t", position=Position(x=3, y=0, z=0)
        )
    elif kind == "overlap":
        placements[1] = PackagePlacement(
            package_id="b", truck_id="t", position=Position(x=0, y=0, z=0)
        )
    elif kind == "floating":
        packages, placements = packages[:1], placements[:1]
        placements[0] = PackagePlacement(
            package_id="a", truck_id="t", position=Position(x=0, y=0, z=1)
        )
    elif kind == "fragile":
        packages[0] = _package("a", fragile=True)
        placements[1] = PackagePlacement(
            package_id="b", truck_id="t", position=Position(x=0, y=0, z=1)
        )
    elif kind == "capacity":
        packages = [_package("a", weight=2), _package("b", weight=2)]
        truck = TruckSpec(id="t", width=3, length=1, height=3, max_capacity=3)
    return Problem(packages=packages, trucks=[truck]), State(placements=placements)


def test_generation_produces_population_size_without_elite_insertion(monkeypatch):
    problem = Problem(packages=[_package("p")], trucks=[_truck("t", 1, 1, 1)])
    valid = State(placements=[PackagePlacement(package_id="p")])
    init = iter([valid, valid])
    monkeypatch.setattr(ga, "generate_random_feasible_state", lambda *_: next(init))
    children = []

    def crossover(_problem, a, b, _rng):
        children.append(1)
        return a.model_copy(deep=True)

    monkeypatch.setattr(ga, "single_point_crossover", crossover)
    GeneticAlgorithm().run(
        problem,
        None,
        objective_mode=ObjectiveMode.TOTAL_VALUE,
        rng=random.Random(3),
        parameters=GeneticAlgorithmParameters(
            population_size=2, generations=1, mutation_probability=0
        ),
        include_state_history=False,
    )
    assert len(children) == 2


def test_one_gene_crossover_does_not_request_cut():
    problem = Problem(packages=[_package("p")], trucks=[_truck("t", 1, 1, 1)])
    state = State(placements=[PackagePlacement(package_id="p")])

    class NoCutRandom:
        def random(self):
            return 0.0

        def randrange(self, *_):
            raise AssertionError("single gene has no cut")

    assert single_point_crossover(problem, state, state, NoCutRandom()) == state


def test_relocation_mutation_changes_at_most_one_gene_and_keeps_noop_copy(monkeypatch):
    problem = Problem(
        packages=[_package("a"), _package("b"), _package("c")],
        trucks=[_truck("t", 3, 1, 1)],
    )
    parent = State(
        placements=[PackagePlacement(package_id=p.id) for p in problem.packages]
    )
    monkeypatch.setattr(
        ga, "generate_random_feasible_state", lambda *_: parent.model_copy(deep=True)
    )
    real_relocate = ga.propose_relocate
    observed = []

    def observe_relocate(problem_arg, state, rng):
        before = state.model_dump(mode="json")
        proposal = real_relocate(problem_arg, state, rng)
        observed.append(
            (
                before,
                None if proposal is None else proposal.state.model_dump(mode="json"),
            )
        )
        return proposal

    monkeypatch.setattr(ga, "propose_relocate", observe_relocate)
    result = GeneticAlgorithm().run(
        problem,
        parent,
        objective_mode=ObjectiveMode.TOTAL_VALUE,
        rng=random.Random(11),
        parameters=GeneticAlgorithmParameters(
            population_size=4,
            generations=1,
            crossover_probability=0,
            mutation_probability=1,
        ),
        include_state_history=False,
    )
    assert len(observed) == 4
    assert any(child is not None and before != child for before, child in observed)
    for before_json, child_json in observed:
        if child_json is None:
            continue
        before = State.model_validate(before_json)
        child = State.model_validate(child_json)
        assert (
            sum(
                a != b for a, b in zip(before.placements, child.placements, strict=True)
            )
            <= 1
        )
    assert parent == State(
        placements=[PackagePlacement(package_id=p.id) for p in problem.packages]
    )
    assert validate_state(problem, result.final_state).valid


def test_noop_relocation_keeps_an_independent_child(monkeypatch):
    problem = Problem(packages=[_package("a")], trucks=[_truck("t", 1, 1, 1)])
    parent = State(placements=[PackagePlacement(package_id="a")])
    monkeypatch.setattr(
        ga, "generate_random_feasible_state", lambda *_: parent.model_copy(deep=True)
    )
    monkeypatch.setattr(ga, "propose_relocate", lambda *_: None)
    real_validate = ga.validate_state
    offspring = []

    def observe_state(problem_arg, state):
        if state is not parent and state.model_dump(mode="json") == parent.model_dump(
            mode="json"
        ):
            offspring.append(state)
        return real_validate(problem_arg, state)

    monkeypatch.setattr(ga, "validate_state", observe_state)
    GeneticAlgorithm().run(
        problem,
        parent,
        objective_mode=ObjectiveMode.TOTAL_VALUE,
        rng=random.Random(1),
        parameters=GeneticAlgorithmParameters(
            population_size=2,
            generations=1,
            crossover_probability=0,
            mutation_probability=1,
        ),
        include_state_history=False,
    )
    children = offspring[-2:]
    assert len(children) == 2
    assert all(child == parent and child is not parent for child in children)
    assert children[0] is not children[1]
    assert all(child.placements[0] is not parent.placements[0] for child in children)


def test_eta_weighted_result_scores_remain_raw_and_history_fitness_finite():
    problem = Problem(
        packages=[_package("early", value=10, eta=1), _package("late", value=9, eta=8)],
        trucks=[_truck("t", 2, 1, 1)],
    )
    result = GeneticAlgorithm().run(
        problem,
        None,
        objective_mode=ObjectiveMode.ETA_WEIGHTED_VALUE,
        rng=random.Random(13),
        parameters=GeneticAlgorithmParameters(
            population_size=3,
            generations=2,
            mutation_probability=0,
        ),
        include_state_history=True,
    )
    initial = State.model_validate(result.metadata["initial_state"])
    assert result.metadata["initial_score"] == evaluate_objective(
        problem, initial, ObjectiveMode.ETA_WEIGHTED_VALUE
    )
    assert result.final_score == evaluate_objective(
        problem, result.final_state, ObjectiveMode.ETA_WEIGHTED_VALUE
    )
    assert result.best_score == evaluate_objective(
        problem, result.best_state, ObjectiveMode.ETA_WEIGHTED_VALUE
    )
    for event in result.history:
        assert 0 <= event.mean_score <= 2 and math.isfinite(event.mean_score)
        assert 0 <= event.metadata["max_fitness"] <= 2
        assert math.isfinite(event.metadata["max_fitness"])
        assert (
            event.state_snapshot is not None
            and validate_state(problem, event.state_snapshot).valid
        )


def _truck(truck_id: str, width: int, length: int, height: int) -> TruckSpec:
    return TruckSpec(
        id=truck_id, width=width, length=length, height=height, max_capacity=10
    )


def _package(
    package_id: str,
    width: int = 1,
    length: int = 1,
    height: int = 1,
    *,
    fragile: bool = False,
    value: float = 1,
    weight: float = 1,
    eta: int = 0,
) -> PackageSpec:
    return PackageSpec(
        id=package_id,
        width=width,
        length=length,
        height=height,
        value=value,
        weight=weight,
        is_fragile=fragile,
        eta=eta,
    )
