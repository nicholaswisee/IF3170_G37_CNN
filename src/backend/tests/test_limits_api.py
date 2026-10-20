import asyncio
import json
from pathlib import Path

import pytest

from app import limits
from app.experiments.runner import ExecutionBudgetError, validate_execution_budget
from app.main import app
from app.schemas.experiment import (
    GeneticAlgorithmRequest,
    HillClimbingRequest,
    SimulatedAnnealingRequest,
)

PROBLEM = {
    "packages": [
        {
            "id": "P1",
            "width": 1,
            "length": 1,
            "height": 1,
            "value": 1,
            "weight": 1,
            "is_fragile": False,
            "eta": 0,
        }
    ],
    "trucks": [{"id": "T1", "width": 2, "length": 2, "height": 2, "max_capacity": 10}],
}

REQUESTS = {
    "hill_climbing": HillClimbingRequest,
    "simulated_annealing": SimulatedAnnealingRequest,
    "genetic_algorithm": GeneticAlgorithmRequest,
}


def get_json(path: str) -> tuple[int, dict]:
    messages = []

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        messages.append(message)

    asyncio.run(
        app(
            {
                "type": "http",
                "asgi": {"version": "3.0"},
                "http_version": "1.1",
                "method": "GET",
                "scheme": "http",
                "path": path,
                "raw_path": path.encode(),
                "query_string": b"",
                "headers": [],
                "server": ("test", 80),
                "client": ("test", 123),
            },
            receive,
            send,
        )
    )
    status = next(m["status"] for m in messages if m["type"] == "http.response.start")
    body = b"".join(
        m.get("body", b"") for m in messages if m["type"] == "http.response.body"
    )
    return status, json.loads(body)


def test_limits_endpoint_reports_problem_and_request_limits() -> None:
    status, body = get_json("/api/limits")
    assert status == 200
    assert body["problem"] == {
        "max_packages": limits.MAX_PACKAGES,
        "max_trucks": limits.MAX_TRUCKS,
        "max_id_length": limits.MAX_ID_LENGTH,
        "max_total_truck_volume": limits.MAX_TOTAL_TRUCK_VOLUME,
    }
    assert body["max_request_bytes"] == limits.MAX_REQUEST_BYTES
    assert body["seed"]["minimum"] == -limits.MAX_SAFE_SEED
    assert body["seed"]["maximum"] == limits.MAX_SAFE_SEED
    assert body["seed"]["integer"] is True


def test_frontend_limits_fixture_matches_the_endpoint() -> None:
    # The frontend tests read this fixture; regenerate it when limits change.
    fixture = Path(__file__).parent / "fixtures" / "limits.json"
    _, body = get_json("/api/limits")
    assert json.loads(fixture.read_text(encoding="utf-8")) == body


def test_limits_combine_schema_bounds_with_runner_budgets() -> None:
    _, body = get_json("/api/limits")
    hc = body["parameters"]["hill_climbing"]
    assert hc["max_iterations"] == {
        "integer": True,
        "nullable": False,
        "minimum": None,
        "exclusive_minimum": 0,
        "maximum": limits.HC_MAX_ITERATIONS,
        "exclusive_maximum": None,
        "default": 2000,
    }
    assert hc["max_sideways"]["minimum"] == 0
    assert hc["max_sideways"]["maximum"] is None
    sa = body["parameters"]["simulated_annealing"]
    assert sa["initial_temperature"]["nullable"] is True
    assert sa["initial_temperature"]["integer"] is False
    assert sa["initial_temperature"]["default"] is None
    assert sa["alpha"]["exclusive_minimum"] == 0
    assert sa["alpha"]["exclusive_maximum"] == 1
    ga = body["parameters"]["genetic_algorithm"]
    assert ga["population_size"]["minimum"] == 2
    assert ga["population_size"]["maximum"] == limits.GA_MAX_POPULATION
    assert ga["elite_count"]["minimum"] == ga["elite_count"]["maximum"] == 0
    assert ga["crossover_probability"]["maximum"] == 1


@pytest.mark.parametrize("algorithm", sorted(REQUESTS))
def test_reported_maximums_are_exactly_what_the_runner_accepts(algorithm) -> None:
    _, body = get_json("/api/limits")
    for name, bounds in body["parameters"][algorithm].items():
        if bounds["maximum"] is None or not bounds["integer"] or name == "elite_count":
            continue
        model = REQUESTS[algorithm]
        accepted = model.model_validate(
            {
                "algorithm": algorithm,
                "problem": PROBLEM,
                "seed": 1,
                "parameters": {name: bounds["maximum"]},
            }
        )
        validate_execution_budget(accepted)
        over = {"parameters": {name: bounds["maximum"] + 1}}
        try:
            rejected = model.model_validate(
                {"algorithm": algorithm, "problem": PROBLEM, "seed": 1, **over}
            )
        except ValueError:
            continue
        with pytest.raises(ExecutionBudgetError):
            validate_execution_budget(rejected)
