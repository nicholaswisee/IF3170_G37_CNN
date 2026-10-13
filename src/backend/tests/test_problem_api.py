import asyncio
import json

import pytest

from app.domain.problem import Problem
from app.main import app


def post_problem(body: bytes) -> tuple[int, dict]:
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
                "path": "/api/problems/validate",
                "raw_path": b"/api/problems/validate",
                "query_string": b"",
                "headers": [(b"content-type", b"application/json")],
                "server": ("test", 80),
                "client": ("test", 123),
            },
            receive,
            send,
        )
    )
    return messages[0]["status"], json.loads(
        b"".join(message.get("body", b"") for message in messages)
    )


def test_accepts_single_and_multi_truck_problems(
    single_truck_problem: Problem, multi_truck_problem: Problem
) -> None:
    for problem in (single_truck_problem, multi_truck_problem):
        status, content = post_problem(problem.model_dump_json().encode())
        assert status == 200
        assert content == {"valid": True}


def test_accepts_empty_packages_and_zero_capacity(
    single_truck_problem: Problem,
) -> None:
    payload = single_truck_problem.model_dump(mode="json")
    payload["packages"] = []
    payload["trucks"][0]["max_capacity"] = 0
    assert post_problem(json.dumps(payload).encode()) == (200, {"valid": True})


def test_accepts_packages_that_must_remain_outside(
    single_truck_problem: Problem,
) -> None:
    payload = single_truck_problem.model_dump(mode="json")
    payload["packages"][0].update(width=100, length=100, height=100, weight=100)
    payload["packages"][1].update(value=0, weight=0, eta=0)
    assert post_problem(json.dumps(payload).encode()) == (200, {"valid": True})


@pytest.mark.parametrize("collection", ["packages", "trucks"])
def test_rejects_duplicate_ids(single_truck_problem: Problem, collection: str) -> None:
    payload = single_truck_problem.model_dump(mode="json")
    payload[collection].append(payload[collection][0].copy())
    status, content = post_problem(json.dumps(payload).encode())
    assert status == 422
    error = content["detail"][0]
    assert error["loc"] == ["body"]
    assert "IDs must be unique" in error["msg"]
    assert set(error) == {"type", "loc", "msg"}


def test_rejects_empty_fleet(single_truck_problem: Problem) -> None:
    payload = single_truck_problem.model_dump(mode="json")
    payload["trucks"] = []
    status, content = post_problem(json.dumps(payload).encode())
    assert status == 422
    assert "at least one truck" in content["detail"][0]["msg"]


@pytest.mark.parametrize("collection", ["packages", "trucks"])
@pytest.mark.parametrize("field", ["width", "length", "height"])
@pytest.mark.parametrize("value", [0, -1, 1.5])
def test_rejects_invalid_dimensions(
    single_truck_problem: Problem, collection: str, field: str, value: float
) -> None:
    payload = single_truck_problem.model_dump(mode="json")
    payload[collection][0][field] = value
    status, content = post_problem(json.dumps(payload).encode())
    assert status == 422
    assert content["detail"][0]["loc"] == ["body", collection, 0, field]


@pytest.mark.parametrize(
    ("collection", "field"),
    [
        ("packages", "value"),
        ("packages", "weight"),
        ("packages", "eta"),
        ("trucks", "max_capacity"),
    ],
)
def test_rejects_negative_metrics(
    single_truck_problem: Problem, collection: str, field: str
) -> None:
    payload = single_truck_problem.model_dump(mode="json")
    payload[collection][0][field] = -1
    status, content = post_problem(json.dumps(payload).encode())
    assert status == 422
    assert content["detail"][0]["loc"] == ["body", collection, 0, field]


@pytest.mark.parametrize(
    ("collection", "field"),
    [("packages", "value"), ("packages", "weight"), ("trucks", "max_capacity")],
)
@pytest.mark.parametrize("value", ["NaN", "Infinity", "1e400"])
def test_rejects_nonfinite_metrics_with_serializable_errors(
    single_truck_problem: Problem, collection: str, field: str, value: str
) -> None:
    payload = single_truck_problem.model_dump(mode="json")
    payload[collection][0][field] = "NONFINITE"
    body = json.dumps(payload).replace('"NONFINITE"', value).encode()
    status, content = post_problem(body)
    assert status == 422
    assert content["detail"][0] == {
        "type": "finite_number",
        "loc": ["body", collection, 0, field],
        "msg": "Input should be a finite number",
    }


@pytest.mark.parametrize("body", [b"", b"{", b"null", b"[]", b"{}", b'{"problem": {}}'])
def test_rejects_malformed_or_missing_problem(body: bytes) -> None:
    status, content = post_problem(body)
    assert status == 422
    assert content["detail"]
    for error in content["detail"]:
        assert set(error) == {"type", "loc", "msg"}
        assert error["loc"][0] == "body"


def test_rejects_missing_package_field(single_truck_problem: Problem) -> None:
    payload = single_truck_problem.model_dump(mode="json")
    del payload["packages"][0]["is_fragile"]
    status, content = post_problem(json.dumps(payload).encode())
    assert status == 422
    assert content["detail"][0]["loc"] == ["body", "packages", 0, "is_fragile"]
    assert content["detail"][0]["type"] == "missing"


def test_rejects_oversized_body(single_truck_problem: Problem) -> None:
    body = single_truck_problem.model_dump_json().encode() + b" " * (256 * 1024)
    status, content = post_problem(body)
    assert status == 422
    assert content == {"detail": "Request body exceeds 262144 bytes."}


def test_openapi_exposes_problem_body_and_validation_response() -> None:
    operation = app.openapi()["paths"]["/api/problems/validate"]["post"]
    body = operation["requestBody"]["content"]["application/json"]["schema"]
    assert body["$ref"] == "#/components/schemas/Problem"
    response = operation["responses"]["200"]["content"]["application/json"]["schema"]
    assert response["$ref"] == "#/components/schemas/ProblemValidationResponse"
    assert "422" in operation["responses"]
