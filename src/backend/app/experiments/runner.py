import math
import random
from pathlib import Path
from time import perf_counter
from uuid import uuid4

from app.config import settings
from app.domain.state import State
from app.experiments.metrics import calculate_metrics
from app.experiments.recorder import record_result
from app.optimization.algorithms import (
    GeneticAlgorithm,
    HillClimbing,
    SimulatedAnnealing,
)
from app.optimization.constraints import validate_state
from app.optimization.initializer import generate_random_feasible_state
from app.optimization.objective import (
    evaluate_objective,
    objective_upper_bound,
)
from app.schemas.experiment import (
    ExperimentResult,
    GeneticAlgorithmRequest,
    HillClimbingRequest,
    RunExperimentRequest,
    SimulatedAnnealingRequest,
)


class UnsupportedAlgorithmError(ValueError):
    pass


class ExecutionBudgetError(ValueError):
    pass


def validate_execution_budget(request: RunExperimentRequest) -> None:
    problem = request.problem
    if len(problem.packages) > 100 or len(problem.trucks) > 20:
        raise ExecutionBudgetError(
            "Execution limit exceeded: at most 100 packages and 20 trucks."
        )
    if abs(request.seed) > 2**53 - 1:
        raise ExecutionBudgetError(
            "Execution limit exceeded: seed must be a JavaScript safe integer."
        )
    if any(len(package.id) > 128 for package in problem.packages) or any(
        len(truck.id) > 128 for truck in problem.trucks
    ):
        raise ExecutionBudgetError(
            "Execution limit exceeded: IDs must be at most 128 characters."
        )
    if (
        sum(truck.width * truck.length * truck.height for truck in problem.trucks)
        > 100_000
    ):
        raise ExecutionBudgetError(
            "Execution limit exceeded: aggregate truck volume is 100000 cells."
        )
    if isinstance(request, GeneticAlgorithmRequest) and (
        request.parameters.population_size > 100 or request.parameters.generations > 200
    ):
        raise ExecutionBudgetError(
            "Execution limit exceeded: GA population <= 100 and generations <= 200."
        )
    if isinstance(request, HillClimbingRequest) and (
        request.parameters.max_iterations > 2_000
        or request.parameters.candidates_per_iteration > 50
        or request.parameters.max_restarts > 20
    ):
        raise ExecutionBudgetError(
            "Execution limit exceeded: Hill Climbing iterations <= 2000, candidates <= 50, and restarts <= 20."
        )
    if (
        isinstance(request, SimulatedAnnealingRequest)
        and request.parameters.max_iterations > 5_000
    ):
        raise ExecutionBudgetError("Execution limit exceeded: SA iterations <= 5000.")


def preflight_experiment(request: RunExperimentRequest) -> None:
    validate_execution_budget(request)
    objective_upper_bound(request.problem, request.objective_mode)


def run_experiment(request: RunExperimentRequest) -> ExperimentResult:
    preflight_experiment(request)
    rng = random.Random(request.seed)
    started = perf_counter()

    if isinstance(request, GeneticAlgorithmRequest):
        search = GeneticAlgorithm().run(
            request.problem,
            None,
            objective_mode=request.objective_mode,
            rng=rng,
            parameters=request.parameters,
            include_state_history=request.include_state_history,
        )
        initial_state = State.model_validate(search.metadata["initial_state"])
        initial_score = search.metadata["initial_score"]
    elif isinstance(request, HillClimbingRequest):
        initial_state = generate_random_feasible_state(request.problem, rng)
        search = HillClimbing(request.variant).run(
            request.problem,
            initial_state,
            objective_mode=request.objective_mode,
            rng=rng,
            parameters=request.parameters,
            include_state_history=request.include_state_history,
        )
        initial_score = evaluate_objective(
            request.problem, initial_state, request.objective_mode
        )
    elif isinstance(request, SimulatedAnnealingRequest):
        initial_state = generate_random_feasible_state(request.problem, rng)
        search = SimulatedAnnealing().run(
            request.problem,
            initial_state,
            objective_mode=request.objective_mode,
            rng=rng,
            parameters=request.parameters,
            include_state_history=request.include_state_history,
        )
        initial_score = evaluate_objective(
            request.problem, initial_state, request.objective_mode
        )
    else:
        raise UnsupportedAlgorithmError(
            f"Algorithm '{request.algorithm}' is not implemented."
        )

    runtime_ms = int((perf_counter() - started) * 1000)
    scores = (
        (initial_state, initial_score),
        (search.final_state, search.final_score),
        (search.best_state, search.best_score),
    )
    for state, score in scores:
        if not math.isfinite(score):
            raise ValueError("Algorithm returned a non-finite score.")
        validity = validate_state(request.problem, state)
        if not validity.valid:
            raise ValueError(
                "Algorithm returned an invalid state: " + "; ".join(validity.errors)
            )
        actual = evaluate_objective(request.problem, state, request.objective_mode)
        if not math.isclose(score, actual, rel_tol=1e-9, abs_tol=1e-9):
            raise ValueError(
                f"Algorithm score {score} does not match state score {actual}."
            )

    result = ExperimentResult(
        id=str(uuid4()),
        problem=request.problem,
        algorithm=request.algorithm,
        variant=request.variant if isinstance(request, HillClimbingRequest) else None,
        objective_mode=request.objective_mode,
        seed=request.seed,
        parameters=request.parameters.model_dump(mode="json"),
        initial_state=initial_state,
        final_state=search.final_state,
        best_state=search.best_state,
        initial_score=initial_score,
        final_score=search.final_score,
        best_score=search.best_score,
        runtime_ms=runtime_ms,
        iterations=search.iterations,
        history=search.history,
        metadata={**search.metadata, "persisted": False},
    )
    if isinstance(request, GeneticAlgorithmRequest):
        result.metadata["metrics"] = calculate_metrics(result)
    if request.persist:
        destination = Path(settings.output_dir) / "experiments" / f"{result.id}.json"
        result.metadata["persisted"] = True
        record_result(result, destination)
    return result
