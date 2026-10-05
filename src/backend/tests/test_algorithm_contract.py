import inspect
import random
from typing import get_type_hints

import pytest
from pydantic import BaseModel

from app.domain.problem import Problem
from app.domain.state import State
from app.optimization.algorithms import (
    GeneticAlgorithm,
    HillClimbing,
    SearchAlgorithm,
    SearchResult,
    SimulatedAnnealing,
)
from app.optimization.initializer import generate_random_feasible_state
from app.optimization.objective import ObjectiveMode, evaluate_objective
from app.schemas.experiment import SearchEvent


class ContractParameters(BaseModel):
    max_iterations: int = 1


@pytest.mark.parametrize("include_snapshot", [False, True])
def test_search_result_round_trip(
    multi_truck_problem: Problem, include_snapshot: bool
) -> None:
    state = generate_random_feasible_state(multi_truck_problem, random.Random(42))
    score = evaluate_objective(multi_truck_problem, state, ObjectiveMode.TOTAL_VALUE)
    event = SearchEvent(
        iteration=0,
        current_score=score,
        best_score=score,
        state_snapshot=state if include_snapshot else None,
    )
    result = SearchResult(
        final_state=state,
        best_state=state.model_copy(deep=True),
        final_score=score,
        best_score=score,
        iterations=0,
        history=[event],
    )
    restored = SearchResult.model_validate_json(result.model_dump_json())
    assert restored == result
    assert restored.history[0].state_snapshot == (state if include_snapshot else None)
    assert restored.history[0].candidate_score is None
    assert restored.history[0].accepted is None
    assert result.metadata == {}
    assert set(type(result).model_fields) == {
        "final_state",
        "best_state",
        "final_score",
        "best_score",
        "iterations",
        "history",
        "metadata",
    }


@pytest.mark.parametrize(
    "algorithm_type",
    [SearchAlgorithm, HillClimbing, SimulatedAnnealing, GeneticAlgorithm],
)
def test_run_signature_matches_frozen_contract(
    algorithm_type: type[SearchAlgorithm],
) -> None:
    signature = inspect.signature(algorithm_type.run)
    assert list(signature.parameters) == [
        "self",
        "problem",
        "initial_state",
        "objective_mode",
        "rng",
        "parameters",
        "include_state_history",
    ]
    for name in ("objective_mode", "rng", "parameters", "include_state_history"):
        assert signature.parameters[name].kind is inspect.Parameter.KEYWORD_ONLY
        assert signature.parameters[name].default is inspect.Parameter.empty
    assert get_type_hints(algorithm_type.run) == {
        "problem": Problem,
        "initial_state": State | None,
        "objective_mode": ObjectiveMode,
        "rng": random.Random,
        "parameters": BaseModel,
        "include_state_history": bool,
        "return": SearchResult,
    }


@pytest.mark.parametrize("algorithm_type", [SimulatedAnnealing, GeneticAlgorithm])
def test_algorithm_placeholders_remain_explicitly_unimplemented(
    single_truck_problem: Problem, algorithm_type: type[SearchAlgorithm]
) -> None:
    rng = random.Random(42)
    initial_state = (
        None
        if algorithm_type is GeneticAlgorithm
        else generate_random_feasible_state(single_truck_problem, rng)
    )
    with pytest.raises(NotImplementedError, match="not implemented yet"):
        algorithm_type().run(
            single_truck_problem,
            initial_state,
            objective_mode=ObjectiveMode.TOTAL_VALUE,
            rng=rng,
            parameters=ContractParameters(),
            include_state_history=False,
        )


class ContractAlgorithm(SearchAlgorithm):
    def run(
        self,
        problem: Problem,
        initial_state: State | None,
        *,
        objective_mode: ObjectiveMode,
        rng: random.Random,
        parameters: BaseModel,
        include_state_history: bool,
    ) -> SearchResult:
        state = (
            generate_random_feasible_state(problem, rng)
            if initial_state is None
            else initial_state.model_copy(deep=True)
        )
        score = evaluate_objective(problem, state, objective_mode)
        return SearchResult(
            final_state=state,
            best_state=state.model_copy(deep=True),
            final_score=score,
            best_score=score,
            iterations=0,
            history=[
                SearchEvent(
                    iteration=0,
                    current_score=score,
                    best_score=score,
                    state_snapshot=state.model_copy(deep=True)
                    if include_state_history
                    else None,
                )
            ],
            metadata=parameters.model_dump(),
        )


@pytest.mark.parametrize("include_snapshot", [False, True])
@pytest.mark.parametrize("with_initial_state", [False, True])
def test_concrete_algorithm_uses_shared_contract(
    single_truck_problem: Problem, include_snapshot: bool, with_initial_state: bool
) -> None:
    initial = (
        generate_random_feasible_state(single_truck_problem, random.Random(7))
        if with_initial_state
        else None
    )
    original = initial.model_dump_json() if initial is not None else None
    algorithm: SearchAlgorithm = ContractAlgorithm()
    parameters = ContractParameters()
    result = algorithm.run(
        single_truck_problem,
        initial,
        objective_mode=ObjectiveMode.ETA_WEIGHTED_VALUE,
        rng=random.Random(42),
        parameters=parameters,
        include_state_history=include_snapshot,
    )
    replay = algorithm.run(
        single_truck_problem,
        initial,
        objective_mode=ObjectiveMode.ETA_WEIGHTED_VALUE,
        rng=random.Random(42),
        parameters=parameters,
        include_state_history=include_snapshot,
    )
    assert result == replay
    assert result.best_score == evaluate_objective(
        single_truck_problem, result.best_state, ObjectiveMode.ETA_WEIGHTED_VALUE
    )
    assert result.metadata == parameters.model_dump()
    assert (result.history[0].state_snapshot is not None) == include_snapshot
    if initial is not None:
        result.final_state.placements.clear()
        assert initial.model_dump_json() == original
