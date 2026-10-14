import asyncio
import json
from pathlib import Path

import pytest
from pydantic import TypeAdapter

from app.api.request_limits import RunBodyLimitMiddleware
from app.main import app
from app.schemas import ExperimentResult, RunExperimentRequest


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


def test_handoff_request_and_result_fixtures_remain_schema_compatible() -> None:
    fixtures = Path(__file__).parent / "fixtures"
    request = TypeAdapter(RunExperimentRequest).validate_json(
        (fixtures / "experiment_request.json").read_text()
    )
    result = ExperimentResult.model_validate_json(
        (fixtures / "experiment_result.json").read_text()
    )
    assert result.problem == request.problem


@pytest.mark.parametrize(
    ("collection", "field"),
    [("packages", "value"), ("packages", "weight"), ("trucks", "max_capacity")],
)
def test_http_rejects_overflow_with_serializable_422(
    collection: str, field: str
) -> None:
    data = json.loads(
        (Path(__file__).parent / "fixtures" / "experiment_request.json").read_text()
    )
    data["problem"][collection][0][field] = "OVERFLOW"
    body = json.dumps(data).replace('"OVERFLOW"', "1e400").encode()
    messages = []

    async def receive():
        return {"type": "http.request", "body": body, "more_body": False}

    async def send(message):
        messages.append(message)

    asyncio.run(
        app(
            {
                "type": "http",
                "asgi": {"version": "3.0"},
                "http_version": "1.1",
                "method": "POST",
                "scheme": "http",
                "path": "/api/experiments/run",
                "raw_path": b"/api/experiments/run",
                "query_string": b"",
                "headers": [(b"content-type", b"application/json")],
                "server": ("test", 80),
                "client": ("test", 123),
            },
            receive,
            send,
        )
    )
    assert messages[0]["status"] == 422
    content = json.loads(b"".join(message.get("body", b"") for message in messages))
    assert content["detail"][0]["type"] == "finite_number"
    assert content["detail"][0]["loc"][-1] == field


def test_request_limit_replays_body_then_delivers_disconnect() -> None:
    messages = iter(
        [
            {"type": "http.request", "body": b"payload", "more_body": False},
            {"type": "http.disconnect"},
        ]
    )
    observed = []

    async def receive():
        return next(messages)

    async def send(message):
        observed.append(message)

    async def downstream(scope, replay_receive, send):
        observed.append(await replay_receive())
        observed.append(await replay_receive())

    asyncio.run(
        RunBodyLimitMiddleware(downstream)(
            {"type": "http", "method": "POST", "path": "/api/experiments/run"},
            receive,
            send,
        )
    )

    assert observed[0] == {
        "type": "http.request",
        "body": b"payload",
        "more_body": False,
    }
    assert observed[1] == {"type": "http.disconnect"}
