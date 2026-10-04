"""Keep the placeholder API importable and explicit about its pending execution."""

from pathlib import Path

import pytest
from pydantic import TypeAdapter

from app.api.experiments import list_experiments, run_experiment
from app.domain import Problem
from app.main import app
from app.optimization.constraints import validate_state
from app.optimization.objective import ObjectiveMode, evaluate_objective
from app.schemas import ExperimentResult, RunExperimentRequest


@pytest.mark.parametrize(
    "algorithm", ["hill_climbing", "simulated_annealing", "genetic_algorithm"]
)
@pytest.mark.parametrize("mode", list(ObjectiveMode))
def test_placeholder_returns_canonical_zero_score_preview(
    multi_truck_problem: Problem, algorithm: str, mode: ObjectiveMode
) -> None:
    request = TypeAdapter(RunExperimentRequest).validate_python(
        {
            "algorithm": algorithm,
            "problem": multi_truck_problem,
            "objective_mode": mode,
            "seed": 42,
            "persist": True,
        }
    )
    original = request.model_dump_json()
    result = run_experiment(request)
    assert result.metadata["placeholder"] is True
    assert result.metadata["persisted"] is False
    assert "not implemented" in result.metadata["message"]
    assert result.problem == request.problem
    assert result.parameters == request.parameters.model_dump(mode="json")
    assert result.objective_mode is mode
    assert result.algorithm == algorithm
    assert result.variant == ("sideways" if algorithm == "hill_climbing" else None)
    assert result.runtime_ms == result.iterations == 0
    assert result.history == []
    for state, score in [
        (result.initial_state, result.initial_score),
        (result.final_state, result.final_score),
        (result.best_state, result.best_score),
    ]:
        assert validate_state(request.problem, state).valid
        assert all(p.truck_id is None for p in state.placements)
        assert evaluate_objective(request.problem, state, mode) == score == 0
    assert ExperimentResult.model_validate_json(result.model_dump_json()) == result
    assert request.model_dump_json() == original
    result.final_state.placements[0].package_id = "changed-by-test"
    assert result.initial_state.placements[0].package_id != "changed-by-test"
    assert result.best_state.placements[0].package_id != "changed-by-test"


def test_api_openapi_exposes_discriminated_body_and_new_response() -> None:
    schema = app.openapi()
    operation = schema["paths"]["/api/experiments/run"]["post"]
    body = operation["requestBody"]["content"]["application/json"]["schema"]
    assert body["discriminator"]["propertyName"] == "algorithm"
    assert len(body["oneOf"]) == 3
    models = schema["components"]["schemas"]
    for reference in body["oneOf"]:
        model = models[reference["$ref"].rsplit("/", 1)[1]]
        assert {"algorithm", "problem", "seed"} <= set(model["required"])
        assert model["properties"]["parameters"]["$ref"].endswith("Parameters")
    response = operation["responses"]["200"]["content"]["application/json"]["schema"]
    result_model = models[response["$ref"].rsplit("/", 1)[1]]
    assert {"problem", "best_state", "best_score", "variant", "objective_mode"} <= set(
        result_model["required"]
    )
    assert list_experiments().experiments == []


def test_handoff_result_is_the_actual_placeholder_response() -> None:
    fixtures = Path(__file__).parent / "fixtures"
    request = TypeAdapter(RunExperimentRequest).validate_json(
        (fixtures / "experiment_request.json").read_text()
    )
    result = ExperimentResult.model_validate_json(
        (fixtures / "experiment_result.json").read_text()
    )
    assert run_experiment(request) == result
