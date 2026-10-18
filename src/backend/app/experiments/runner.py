import math
import random
from pathlib import Path
from time import perf_counter
from uuid import uuid4

from app import limits
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
    if len(problem.packages) > limits.MAX_PACKAGES or len(problem.trucks) > (
        limits.MAX_TRUCKS
    ):
        raise ExecutionBudgetError(
            f"Execution limit exceeded: at most {limits.MAX_PACKAGES} packages "
            f"and {limits.MAX_TRUCKS} trucks."
        )
    if abs(request.seed) > limits.MAX_SAFE_SEED:
        raise ExecutionBudgetError(
            "Execution limit exceeded: seed must be a JavaScript safe integer."
        )
    if any(len(package.id) > limits.MAX_ID_LENGTH for package in problem.packages) or (
        any(len(truck.id) > limits.MAX_ID_LENGTH for truck in problem.trucks)
    ):
        raise ExecutionBudgetError(
            "Execution limit exceeded: IDs must be at most "
            f"{limits.MAX_ID_LENGTH} characters."
        )
    if (
        sum(truck.width * truck.length * truck.height for truck in problem.trucks)
        > limits.MAX_TOTAL_TRUCK_VOLUME
    ):
        raise ExecutionBudgetError(
            "Execution limit exceeded: aggregate truck volume is "
            f"{limits.MAX_TOTAL_TRUCK_VOLUME} cells."
        )
    if isinstance(request, GeneticAlgorithmRequest) and (
        request.parameters.population_size > limits.GA_MAX_POPULATION
        or request.parameters.generations > limits.GA_MAX_GENERATIONS
    ):
        raise ExecutionBudgetError(
            f"Execution limit exceeded: GA population <= {limits.GA_MAX_POPULATION} "
            f"and generations <= {limits.GA_MAX_GENERATIONS}."
        )
    if isinstance(request, HillClimbingRequest) and (
        request.parameters.max_iterations > limits.HC_MAX_ITERATIONS
        or request.parameters.candidates_per_iteration > limits.HC_MAX_CANDIDATES
        or request.parameters.max_restarts > limits.HC_MAX_RESTARTS
    ):
        raise ExecutionBudgetError(
            "Execution limit exceeded: Hill Climbing iterations <= "
            f"{limits.HC_MAX_ITERATIONS}, candidates <= {limits.HC_MAX_CANDIDATES}, "
            f"and restarts <= {limits.HC_MAX_RESTARTS}."
        )
    if (
        isinstance(request, SimulatedAnnealingRequest)
        and request.parameters.max_iterations > limits.SA_MAX_ITERATIONS
    ):
        raise ExecutionBudgetError(
            f"Execution limit exceeded: SA iterations <= {limits.SA_MAX_ITERATIONS}."
        )


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
