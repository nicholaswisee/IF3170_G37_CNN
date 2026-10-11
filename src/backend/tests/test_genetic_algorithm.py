import math
import random
from types import SimpleNamespace

import pytest

from app.domain.package import PackageSpec
from app.domain.problem import Problem
from app.domain.state import State
from app.domain.truck import PackagePlacement, Position, TruckSpec
from app.optimization.algorithms import genetic_algorithm as ga
from app.optimization.algorithms.genetic_algorithm import (
    GeneticAlgorithm,
    repair_state,
    roulette_select,
    uniform_crossover,
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
    assert result.history[1].mean_score == float.fromhex("0x1.fffffffffffffp+1023")
    assert all(math.isfinite(event.mean_score) for event in result.history)


def test_run_mean_handles_mixed_maximum_fitnesses(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    problem = Problem(packages=[_package("p")], trucks=[_truck("t", 1, 1, 1)])
    maximum = float.fromhex("0x1.fffffffffffffp+1023")
    fitnesses = iter([maximum, maximum / 2, 0.0, maximum, 0.0, maximum / 2])
    monkeypatch.setattr(ga, "evaluate_objective", lambda *_args: next(fitnesses))
    result = GeneticAlgorithm().run(
        problem,
        None,
        objective_mode=ObjectiveMode.TOTAL_VALUE,
        rng=random.Random(0),
        parameters=GeneticAlgorithmParameters(
            population_size=3, generations=1, mutation_probability=0
        ),
        include_state_history=False,
    )
    assert result.history[0].mean_score == pytest.approx(maximum / 2)
    assert math.isfinite(result.history[0].mean_score)


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


def test_crossover_uses_package_ids_and_copies_genes(
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
    expected_choices_rng = random.Random(3)
    expected_choices = [
        expected_choices_rng.random() < 0.5 for _ in single_truck_problem.packages
    ]
    child = uniform_crossover(single_truck_problem, a, b, random.Random(3))
    assert {p.package_id for p in child.placements} == {"base", "top", "fragile"}
    parents = {
        p.package_id: (p, next(q for q in b.placements if q.package_id == p.package_id))
        for p in a.placements
    }
    for placement, choose_a in zip(child.placements, expected_choices, strict=True):
        parent_a, parent_b = parents[placement.package_id]
        assert placement == (parent_a if choose_a else parent_b)
        assert placement == parent_a or placement == parent_b
        assert placement is not parent_a and placement is not parent_b
        for parent in (parent_a, parent_b):
            if placement.position is not None and placement.position is parent.position:
                pytest.fail("crossover shared a mutable Position with a parent")


def test_repair_relocates_overlap_to_requested_truck(
    single_truck_problem: Problem,
) -> None:
    candidate = State(
        placements=[
            PackagePlacement(
                package_id="base", truck_id="truck-a", position=Position(x=0, y=0, z=0)
            ),
            PackagePlacement(
                package_id="top", truck_id="truck-a", position=Position(x=0, y=0, z=0)
            ),
            PackagePlacement(package_id="fragile"),
        ]
    )
    repaired = repair_state(single_truck_problem, candidate, random.Random(11))
    assert validate_state(single_truck_problem, repaired).valid
    assert repaired.placements[1].truck_id == "truck-a"
    assert repaired.placements[1].position != Position(x=0, y=0, z=0)


def test_repair_falls_back_to_alternative_truck_and_keeps_outside(
    multi_truck_problem: Problem,
) -> None:
    candidate = State(
        placements=[
            PackagePlacement(
                package_id="base", truck_id="truck-a", position=Position(x=0, y=0, z=0)
            ),
            PackagePlacement(
                package_id="top", truck_id="truck-a", position=Position(x=0, y=0, z=0)
            ),
            PackagePlacement(package_id="fragile"),
        ]
    )
    repaired = repair_state(multi_truck_problem, candidate, random.Random(11))
    assert validate_state(multi_truck_problem, repaired).valid
    assert repaired.placements[1].truck_id == "truck-b"
    assert repaired.placements[2].truck_id is None


def test_repair_leaves_impossible_package_outside() -> None:
    problem = Problem(
        packages=[
            PackageSpec(
                id="too-large",
                width=10,
                length=10,
                height=10,
                value=1,
                weight=1,
                is_fragile=False,
                eta=0,
            )
        ],
        trucks=[_truck("truck-a", 2, 2, 2)],
    )
    repaired = repair_state(
        problem,
        State(
            placements=[
                PackagePlacement(
                    package_id="too-large",
                    truck_id="truck-a",
                    position=Position(x=0, y=0, z=0),
                )
            ]
        ),
        random.Random(4),
    )
    assert repaired.placements[0].truck_id is None
    assert validate_state(problem, repaired).valid


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
) -> PackageSpec:
    return PackageSpec(
        id=package_id,
        width=width,
        length=length,
        height=height,
        value=value,
        weight=1,
        is_fragile=fragile,
        eta=0,
    )


def test_repair_rotates_when_requested_orientation_cannot_fit() -> None:
    problem = Problem(
        packages=[_package("wide", width=2, length=1)],
        trucks=[_truck("truck-a", 1, 2, 1)],
    )
    candidate = State(
        placements=[
            PackagePlacement(
                package_id="wide",
                truck_id="truck-a",
                position=Position(x=0, y=0, z=0),
            )
        ]
    )
    repaired = repair_state(problem, candidate, random.Random(1))
    assert validate_state(problem, repaired).valid
    assert repaired.placements[0].orientation != candidate.placements[0].orientation
    assert candidate.placements[0].orientation.value == 0


def test_repair_moves_floating_and_fragile_supported_requests_to_feasible_cells() -> (
    None
):
    problem = Problem(
        packages=[_package("fragile", fragile=True), _package("top")],
        trucks=[_truck("truck-a", 2, 1, 2)],
    )
    candidate = State(
        placements=[
            PackagePlacement(
                package_id="fragile",
                truck_id="truck-a",
                position=Position(x=0, y=0, z=0),
            ),
            PackagePlacement(
                package_id="top",
                truck_id="truck-a",
                position=Position(x=0, y=0, z=1),
            ),
        ]
    )
    before = candidate.model_dump_json()
    repaired = repair_state(problem, candidate, random.Random(5))
    assert validate_state(problem, repaired).valid
    assert repaired.placements[1].position != Position(x=0, y=0, z=1)
    assert candidate.model_dump_json() == before


def test_repair_preserves_exact_feasible_request_without_mutating_candidate() -> None:
    problem = Problem(packages=[_package("p")], trucks=[_truck("truck-a", 2, 2, 1)])
    candidate = State(
        placements=[
            PackagePlacement(
                package_id="p",
                truck_id="truck-a",
                position=Position(x=1, y=1, z=0),
            )
        ]
    )
    before = candidate.model_dump_json()
    repaired = repair_state(problem, candidate, random.Random(3))
    assert repaired == candidate
    assert repaired is not candidate
    assert repaired.placements[0] is not candidate.placements[0]
    assert candidate.model_dump_json() == before


def test_repair_shuffles_alternative_orientations_with_seeded_rng(monkeypatch) -> None:
    problem = Problem(
        packages=[_package("p", width=2, length=3, height=4)],
        trucks=[_truck("t", 4, 4, 4)],
    )
    package = problem.packages[0]
    gene = PackagePlacement(
        package_id="p", truck_id="t", position=Position(x=9, y=9, z=0)
    )
    orders = []

    def record(_problem, _state, _index, placement):
        if not orders or orders[-1] != placement.orientation:
            orders.append(placement.orientation)
        return False

    monkeypatch.setattr(ga, "_try_placement", record)

    def orientations(seed):
        orders.clear()
        ga._scan_truck(
            problem,
            State(placements=[PackagePlacement(package_id="p")]),
            0,
            package,
            gene,
            _truck("t", 4, 4, 4),
            random.Random(seed),
        )
        return orders[:]

    first = orientations(17)
    expected = [
        orientation
        for orientation in ga.get_unique_orientations(package)
        if orientation != gene.orientation
    ]
    random.Random(17).shuffle(expected)
    expected.insert(0, gene.orientation)
    assert first == expected
    assert first[0] == gene.orientation
    assert set(first) == set(ga.get_unique_orientations(package))


def test_repair_scan_uses_z_then_y_then_x_order(monkeypatch) -> None:
    problem = Problem(packages=[_package("p")], trucks=[_truck("t", 2, 2, 2)])
    attempted = []

    def probe(_problem, _state, _index, placement):
        attempted.append(placement.position)
        return placement.position == Position(x=1, y=1, z=1)

    monkeypatch.setattr(ga, "_try_placement", probe)
    assert ga._scan_truck(
        problem,
        State(placements=[PackagePlacement(package_id="p")]),
        0,
        problem.packages[0],
        PackagePlacement(
            package_id="p", truck_id="t", position=Position(x=9, y=9, z=9)
        ),
        problem.trucks[0],
        random.Random(1),
    )
    assert attempted[:5] == [
        Position(x=0, y=0, z=0),
        Position(x=1, y=0, z=0),
        Position(x=0, y=1, z=0),
        Position(x=1, y=1, z=0),
        Position(x=0, y=0, z=1),
    ]
    assert attempted[-1] == Position(x=1, y=1, z=1)


def test_repair_recovers_out_of_bounds_and_floating_requests() -> None:
    problem = Problem(packages=[_package("p")], trucks=[_truck("truck-a", 1, 1, 2)])
    candidate = State(
        placements=[
            PackagePlacement(
                package_id="p",
                truck_id="truck-a",
                position=Position(x=9, y=9, z=1),
            )
        ]
    )
    repaired = repair_state(problem, candidate, random.Random(2))
    assert validate_state(problem, repaired).valid
    assert repaired.placements[0].position == Position(x=0, y=0, z=0)


def test_repair_moves_floating_package_to_floor() -> None:
    problem = Problem(packages=[_package("p")], trucks=[_truck("truck-a", 1, 1, 2)])
    candidate = State(
        placements=[
            PackagePlacement(
                package_id="p",
                truck_id="truck-a",
                position=Position(x=0, y=0, z=1),
            )
        ]
    )
    repaired = repair_state(problem, candidate, random.Random(2))
    assert validate_state(problem, repaired).valid
    assert repaired.placements[0].position == Position(x=0, y=0, z=0)


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
    assert all(event.mean_score == 0 for event in result.history)


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


def test_population_admission_elite_and_metrics_are_exact(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    problem = Problem(
        packages=[_package("p", value=8)], trucks=[_truck("truck-a", 1, 1, 1)]
    )
    loaded = State(
        placements=[
            PackagePlacement(
                package_id="p",
                truck_id="truck-a",
                position=Position(x=0, y=0, z=0),
            )
        ]
    )
    outside = State(placements=[PackagePlacement(package_id="p")])
    initializer_states = iter([loaded, outside, outside])
    monkeypatch.setattr(
        ga,
        "generate_random_feasible_state",
        lambda _problem, _rng: next(initializer_states),
    )

    repair_outputs = iter([loaded, loaded, outside, outside])
    repair_inputs: list[State] = []

    def scripted_repair(
        _problem: Problem, candidate: State, _rng: random.Random
    ) -> State:
        repair_inputs.append(candidate.model_copy(deep=True))
        return next(repair_outputs).model_copy(deep=True)

    monkeypatch.setattr(ga, "repair_state", scripted_repair)
    mutation_calls: list[State] = []

    def record_mutation(_problem: Problem, state: State, _rng: random.Random) -> None:
        mutation_calls.append(state.model_copy(deep=True))

    monkeypatch.setattr(ga, "propose_relocate", record_mutation)
    monkeypatch.setattr(ga, "propose_rotate", record_mutation)
    monkeypatch.setattr(ga, "propose_swap", record_mutation)
    evaluated_batches: list[list[State]] = []
    real_validate = validate_state

    def scored_state(_problem: Problem, state: State, _mode: ObjectiveMode) -> float:
        assert real_validate(problem, state).valid
        if not evaluated_batches or len(evaluated_batches[-1]) == 3:
            evaluated_batches.append([])
        evaluated_batches[-1].append(state.model_copy(deep=True))
        return 8.0 if state.placements[0].truck_id is not None else 0.0

    monkeypatch.setattr(ga, "evaluate_objective", scored_state)
    result = GeneticAlgorithm().run(
        problem,
        None,
        objective_mode=ObjectiveMode.TOTAL_VALUE,
        rng=random.Random(5),
        parameters=GeneticAlgorithmParameters(
            population_size=3,
            generations=2,
            crossover_probability=0,
            mutation_probability=1,
        ),
        include_state_history=True,
    )

    assert [len(batch) for batch in evaluated_batches] == [3, 3, 3]
    assert [
        sum(state.placements[0].truck_id is not None for state in batch)
        for batch in evaluated_batches
    ] == [1, 3, 1]
    assert [event.current_score for event in result.history] == [8, 8, 8]
    assert [event.best_score for event in result.history] == [8, 8, 8]
    assert [event.mean_score for event in result.history] == pytest.approx(
        [8 / 3, 8, 8 / 3]
    )
    assert len(repair_inputs) == 4
    assert all(batch[0] == loaded for batch in evaluated_batches[1:])
    assert len(mutation_calls) == 4
    assert result.metadata["initial_score"] == 8
    assert State.model_validate(result.metadata["initial_state"]) == loaded


def test_non_none_mutation_state_reaches_repair_and_elite_survives(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    problem = Problem(packages=[_package("p")], trucks=[_truck("t", 1, 1, 1)])
    loaded = State(
        placements=[
            PackagePlacement(
                package_id="p", truck_id="t", position=Position(x=0, y=0, z=0)
            )
        ]
    )
    outside = State(placements=[PackagePlacement(package_id="p")])
    monkeypatch.setattr(ga, "generate_random_feasible_state", lambda *_args: loaded)
    monkeypatch.setattr(
        ga, "roulette_select", lambda population, _fitnesses, _rng: population[0]
    )

    class ScriptedRng:
        draws = iter([1.0, 0.0])

        @classmethod
        def random(cls):
            return next(cls.draws)

        @staticmethod
        def choice(items):
            return items[0]

    proposal_inputs = []

    def propose(_problem, state, _rng):
        proposal_inputs.append(state.model_copy(deep=True))
        return SimpleNamespace(state=outside)

    monkeypatch.setattr(ga, "propose_relocate", propose)
    repair_inputs = []

    def record_repair(_problem, candidate, _rng):
        repair_inputs.append(candidate.model_copy(deep=True))
        return candidate

    monkeypatch.setattr(ga, "repair_state", record_repair)
    result = GeneticAlgorithm().run(
        problem,
        None,
        objective_mode=ObjectiveMode.TOTAL_VALUE,
        rng=ScriptedRng(),
        parameters=GeneticAlgorithmParameters(
            population_size=2,
            generations=1,
            crossover_probability=0,
            mutation_probability=1,
        ),
        include_state_history=True,
    )
    assert proposal_inputs == [loaded]
    assert repair_inputs == [outside]
    assert [event.state_snapshot for event in result.history] == [loaded, loaded]


def test_history_snapshots_and_returned_states_are_independent_copies(
    single_truck_problem: Problem,
) -> None:
    result = GeneticAlgorithm().run(
        single_truck_problem,
        None,
        objective_mode=ObjectiveMode.TOTAL_VALUE,
        rng=random.Random(42),
        parameters=GeneticAlgorithmParameters(population_size=2, generations=1),
        include_state_history=True,
    )
    first_snapshot = result.history[0].state_snapshot
    assert first_snapshot is not None
    assert first_snapshot is not result.final_state
    assert first_snapshot is not result.best_state
    first_snapshot.placements.clear()
    assert result.final_state.placements
    assert result.best_state.placements
