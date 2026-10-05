"""Frozen request, parameter, result, and history contracts for the team handoff."""

import json
from pathlib import Path

import pytest
from pydantic import BaseModel, TypeAdapter, ValidationError

from app.domain import PackagePlacement, Problem, State
from app.optimization.algorithms.base import SearchResult
from app.optimization.objective import ObjectiveMode
from app.schemas import (
    ExperimentListResponse,
    ExperimentResult,
    GeneticAlgorithmParameters,
    GeneticAlgorithmRequest,
    HillClimbingParameters,
    HillClimbingRequest,
    HillClimbingVariant,
    RunExperimentRequest,
    SearchEvent,
    SimulatedAnnealingParameters,
    SimulatedAnnealingRequest,
)

REQUEST = TypeAdapter(RunExperimentRequest)
FIXTURES = Path(__file__).parent / "fixtures"
ALGORITHMS = ["hill_climbing", "simulated_annealing", "genetic_algorithm"]
MODELS_AND_DEFAULTS = [
    (
        "hill_climbing",
        HillClimbingRequest,
        HillClimbingParameters,
        {
            "max_iterations": 2000,
            "candidates_per_iteration": 50,
            "max_sideways": 100,
            "max_restarts": 10,
        },
    ),
    (
        "simulated_annealing",
        SimulatedAnnealingRequest,
        SimulatedAnnealingParameters,
        {
            "initial_temperature": None,
            "alpha": 0.995,
            "min_temperature": 0.001,
            "max_iterations": 5000,
            "stuck_patience": 50,
        },
    ),
    (
        "genetic_algorithm",
        GeneticAlgorithmRequest,
        GeneticAlgorithmParameters,
        {
            "population_size": 50,
            "generations": 100,
            "crossover_probability": 0.8,
            "mutation_probability": 0.2,
            "elite_count": 1,
        },
    ),
]


def payload(problem: Problem, algorithm: str) -> dict:
    return {
        "problem": problem.model_dump(mode="json"),
        "algorithm": algorithm,
        "seed": 42,
    }


@pytest.mark.parametrize("algorithm", ALGORITHMS)
@pytest.mark.parametrize(
    ("collection", "field"),
    [("packages", "value"), ("packages", "weight"), ("trucks", "max_capacity")],
)
@pytest.mark.parametrize("number", [float("inf"), float("-inf"), float("nan")])
def test_request_rejects_nonfinite_problem_numbers(
    single_truck_problem: Problem,
    algorithm: str,
    collection: str,
    field: str,
    number: float,
) -> None:
    data = payload(single_truck_problem, algorithm)
    data["problem"][collection][0][field] = number
    with pytest.raises(ValidationError):
        REQUEST.validate_python(data)


@pytest.mark.parametrize(
    ("collection", "field"),
    [("packages", "value"), ("packages", "weight"), ("trucks", "max_capacity")],
)
def test_request_rejects_json_exponent_overflow(
    single_truck_problem: Problem, collection: str, field: str
) -> None:
    data = payload(single_truck_problem, "genetic_algorithm")
    data["problem"][collection][0][field] = "OVERFLOW"
    raw = json.dumps(data).replace('"OVERFLOW"', "1e400")
    with pytest.raises(ValidationError):
        REQUEST.validate_json(raw)


@pytest.mark.parametrize("number", [float("inf"), float("-inf"), float("nan")])
def test_result_and_event_metrics_must_be_finite(number: float) -> None:
    for field in (
        "current_score",
        "best_score",
        "candidate_score",
        "mean_score",
        "temperature",
        "acceptance_probability",
    ):
        with pytest.raises(ValidationError):
            SearchEvent.model_validate(
                {"iteration": 0, "current_score": 0, "best_score": 0, field: number}
            )
    public = json.loads((FIXTURES / "experiment_result.json").read_text())
    for field in ("initial_score", "final_score", "best_score"):
        with pytest.raises(ValidationError):
            ExperimentResult.model_validate(public | {field: number})
    internal = {
        "final_state": public["final_state"],
        "best_state": public["best_state"],
        "final_score": 0,
        "best_score": 0,
        "iterations": 0,
        "history": [],
    }
    for field in ("final_score", "best_score"):
        with pytest.raises(ValidationError):
            SearchResult.model_validate(internal | {field: number})


@pytest.mark.parametrize(
    "fixture_name", ["single_truck_problem", "multi_truck_problem"]
)
@pytest.mark.parametrize("explicit_parameters", [False, True])
@pytest.mark.parametrize(
    ("algorithm", "request_model", "parameter_model", "defaults"), MODELS_AND_DEFAULTS
)
def test_request_dispatch_defaults_and_json_round_trip(
    request: pytest.FixtureRequest,
    fixture_name: str,
    explicit_parameters: bool,
    algorithm: str,
    request_model: type[BaseModel],
    parameter_model: type[BaseModel],
    defaults: dict,
) -> None:
    problem = request.getfixturevalue(fixture_name)
    data = payload(problem, algorithm)
    if explicit_parameters:
        data["parameters"] = {}
    parsed = REQUEST.validate_python(data)
    assert isinstance(parsed, request_model)
    assert isinstance(parsed.parameters, parameter_model)
    assert parsed.parameters.model_dump() == defaults
    assert parsed.problem == problem
    assert parsed.objective_mode is ObjectiveMode.TOTAL_VALUE
    assert parsed.include_state_history is True
    assert parsed.persist is True
    if isinstance(parsed, HillClimbingRequest):
        assert parsed.variant is HillClimbingVariant.SIDEWAYS
    assert REQUEST.validate_json(parsed.model_dump_json()) == parsed


@pytest.mark.parametrize("variant", list(HillClimbingVariant))
def test_all_hc_variants_and_optional_features(
    single_truck_problem: Problem, variant: HillClimbingVariant
) -> None:
    data = payload(single_truck_problem, "hill_climbing") | {
        "variant": variant.value,
        "objective_mode": "eta_weighted_value",
        "include_state_history": False,
        "persist": False,
        "seed": -1,
        "parameters": {"max_sideways": 0, "max_restarts": 0},
    }
    parsed = REQUEST.validate_python(data)
    assert isinstance(parsed, HillClimbingRequest)
    assert parsed.variant is variant
    assert parsed.objective_mode is ObjectiveMode.ETA_WEIGHTED_VALUE
    assert parsed.include_state_history is False and parsed.persist is False
    assert parsed.seed == -1
    assert parsed.parameters.max_sideways == parsed.parameters.max_restarts == 0


@pytest.mark.parametrize(
    ("algorithm", "parameters"),
    [
        (
            "simulated_annealing",
            {
                "initial_temperature": 5,
                "alpha": 0.9,
                "min_temperature": 0.1,
                "max_iterations": 10,
                "stuck_patience": 1,
            },
        ),
        (
            "genetic_algorithm",
            {
                "population_size": 2,
                "generations": 1,
                "crossover_probability": 0,
                "mutation_probability": 1,
            },
        ),
    ],
)
def test_valid_parameter_overrides(
    single_truck_problem: Problem, algorithm: str, parameters: dict
) -> None:
    parsed = REQUEST.validate_python(
        payload(single_truck_problem, algorithm) | {"parameters": parameters}
    )
    for name, value in parameters.items():
        assert getattr(parsed.parameters, name) == value


@pytest.mark.parametrize(
    ("algorithm", "field", "value"),
    [
        ("hill_climbing", "max_iterations", 0),
        ("hill_climbing", "candidates_per_iteration", 0),
        ("hill_climbing", "max_sideways", -1),
        ("hill_climbing", "max_restarts", -1),
        ("hill_climbing", "max_iterations", 1.5),
        ("hill_climbing", "alpha", 0.9),
        ("simulated_annealing", "initial_temperature", 0),
        ("simulated_annealing", "initial_temperature", -1),
        ("simulated_annealing", "initial_temperature", float("inf")),
        ("simulated_annealing", "alpha", 0),
        ("simulated_annealing", "alpha", 1),
        ("simulated_annealing", "alpha", float("nan")),
        ("simulated_annealing", "min_temperature", 0),
        ("simulated_annealing", "min_temperature", float("inf")),
        ("simulated_annealing", "max_iterations", 0),
        ("simulated_annealing", "stuck_patience", 0),
        ("simulated_annealing", "population_size", 20),
        ("genetic_algorithm", "population_size", 1),
        ("genetic_algorithm", "generations", 0),
        ("genetic_algorithm", "crossover_probability", -0.1),
        ("genetic_algorithm", "crossover_probability", 1.1),
        ("genetic_algorithm", "mutation_probability", -0.1),
        ("genetic_algorithm", "mutation_probability", 1.1),
        ("genetic_algorithm", "elite_count", 0),
        ("genetic_algorithm", "elite_count", 2),
        ("genetic_algorithm", "elite_count", 50),
        ("genetic_algorithm", "max_iterations", 10),
    ],
)
def test_invalid_or_foreign_parameters_are_rejected_at_request_boundary(
    single_truck_problem: Problem, algorithm: str, field: str, value: object
) -> None:
    data = payload(single_truck_problem, algorithm) | {"parameters": {field: value}}
    with pytest.raises(ValidationError) as error:
        REQUEST.validate_python(data)
    assert any(
        e["loc"] == (algorithm, "parameters", field) for e in error.value.errors()
    )


@pytest.mark.parametrize("field", ["algorithm", "problem", "seed"])
def test_required_request_fields(single_truck_problem: Problem, field: str) -> None:
    data = payload(single_truck_problem, "hill_climbing")
    del data[field]
    with pytest.raises(ValidationError):
        REQUEST.validate_python(data)


@pytest.mark.parametrize(
    "updates",
    [
        {"algorithm": "unknown"},
        {"objective_mode": "unknown"},
        {"parameters": None},
        {"variant": "unknown"},
        {"unexpected": True},
        {"algorithm": "simulated_annealing", "variant": "sideways"},
        {"algorithm": "genetic_algorithm", "variant": "sideways"},
    ],
)
def test_invalid_request_fields(single_truck_problem: Problem, updates: dict) -> None:
    with pytest.raises(ValidationError):
        REQUEST.validate_python(
            payload(single_truck_problem, "hill_climbing") | updates
        )


@pytest.mark.parametrize(
    "fault", ["no_trucks", "duplicate_truck", "duplicate_package", "invalid_dimension"]
)
def test_requests_reuse_domain_validation(
    single_truck_problem: Problem, fault: str
) -> None:
    data = payload(single_truck_problem, "hill_climbing")
    problem = data["problem"]
    if fault == "no_trucks":
        problem["trucks"] = []
    elif fault == "duplicate_truck":
        problem["trucks"].append(problem["trucks"][0])
    elif fault == "duplicate_package":
        problem["packages"].append(problem["packages"][0])
    else:
        problem["trucks"][0]["width"] = 0
    with pytest.raises(ValidationError):
        REQUEST.validate_python(data)


@pytest.mark.parametrize("algorithm", ALGORITHMS)
@pytest.mark.parametrize("include_snapshot", [False, True])
@pytest.mark.parametrize(
    "fixture_name", ["single_truck_problem", "multi_truck_problem"]
)
def test_public_result_and_history_round_trip(
    request: pytest.FixtureRequest,
    algorithm: str,
    include_snapshot: bool,
    fixture_name: str,
) -> None:
    problem = request.getfixturevalue(fixture_name)
    parsed = REQUEST.validate_python(payload(problem, algorithm))
    state = State(
        placements=[PackagePlacement(package_id=p.id) for p in problem.packages]
    )
    event = SearchEvent(
        iteration=1,
        current_score=0,
        best_score=0,
        state_snapshot=state if include_snapshot else None,
    )
    if algorithm == "genetic_algorithm":
        event.mean_score = 0
    else:
        event.candidate_score = 0
        event.accepted = True
        if algorithm == "simulated_annealing":
            event.temperature = 5
            event.acceptance_probability = 1
    result = ExperimentResult(
        id="contract-example",
        problem=problem,
        algorithm=parsed.algorithm,
        variant=parsed.variant if isinstance(parsed, HillClimbingRequest) else None,
        objective_mode=parsed.objective_mode,
        seed=parsed.seed,
        parameters=parsed.parameters.model_dump(mode="json"),
        initial_state=state,
        final_state=state,
        best_state=state,
        initial_score=0,
        final_score=0,
        best_score=0,
        runtime_ms=0,
        iterations=1,
        history=[event],
    )
    restored = ExperimentResult.model_validate_json(result.model_dump_json())
    assert restored == result
    assert restored.history[0].state_snapshot == (state if include_snapshot else None)
    if algorithm == "genetic_algorithm":
        assert restored.history[0].candidate_score is None
        assert restored.history[0].accepted is None
    listing = ExperimentListResponse(experiments=[restored])
    assert (
        ExperimentListResponse.model_validate_json(listing.model_dump_json()) == listing
    )


def test_event_optional_fields_and_metadata_are_independent() -> None:
    first = SearchEvent(iteration=0, current_score=0, best_score=0)
    second = SearchEvent(iteration=0, current_score=0, best_score=0)
    for field in (
        "candidate_score",
        "mean_score",
        "accepted",
        "move",
        "temperature",
        "acceptance_probability",
        "state_snapshot",
    ):
        assert getattr(first, field) is None
    first.metadata["note"] = "test"
    assert second.metadata == {}
    with pytest.raises(ValidationError):
        SearchEvent.model_validate({"iteration": 0, "current_score": 0})


def test_handoff_json_examples_match_the_frozen_contract() -> None:
    request = REQUEST.validate_json((FIXTURES / "experiment_request.json").read_text())
    result = ExperimentResult.model_validate_json(
        (FIXTURES / "experiment_result.json").read_text()
    )
    assert result.problem == request.problem
    assert len(request.problem.trucks) == 2
    assert result.algorithm == request.algorithm
    assert result.parameters == request.parameters.model_dump(mode="json")
    assert result.objective_mode == request.objective_mode
    assert result.seed == request.seed
    assert result.metadata["placeholder"] is True
    assert json.loads(result.model_dump_json())["variant"] is None
