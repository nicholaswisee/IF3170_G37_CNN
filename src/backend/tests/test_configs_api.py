import asyncio
import json
from pathlib import Path

import pytest

from app import limits
from app.configs import store
from app.domain.problem import Problem
from app.main import app


def call(method: str, path: str, payload: object = None) -> tuple[int, object]:
    messages = []
    body = b"" if payload is None else json.dumps(payload).encode()

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
                "method": method,
                "scheme": "http",
                "path": path,
                "raw_path": path.encode(),
                "query_string": b"",
                "headers": [(b"content-type", b"application/json")],
                "server": ("test", 80),
                "client": ("test", 123),
            },
            receive,
            send,
        )
    )
    raw = b"".join(message.get("body", b"") for message in messages)
    return messages[0]["status"], json.loads(raw) if raw else None


@pytest.fixture(autouse=True)
def data_dir(tmp_path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(store.settings, "data_dir", str(tmp_path))
    return tmp_path


def upload(problem: Problem, name: str = "My fleet") -> dict:
    return {"name": name, "problem": problem.model_dump(mode="json")}


def uploaded_ids() -> list[str]:
    status, body = call("GET", "/api/configs")
    assert status == 200
    return [config["id"] for config in body["configs"] if not config["builtin"]]


def test_builtins_are_listed_and_loadable_without_uploads() -> None:
    status, body = call("GET", "/api/configs")
    assert status == 200
    builtins = [config for config in body["configs"] if config["builtin"]]
    assert {
        "builtin-example-fleet",
        "builtin-tight-capacity",
    } <= {config["id"] for config in builtins}
    for summary in builtins:
        status, config = call("GET", f"/api/configs/{summary['id']}")
        assert status == 200
        assert len(config["problem"]["trucks"]) == summary["truck_count"]
        assert len(config["problem"]["packages"]) == summary["package_count"]
        assert config["created_at"] is None


def test_root_testing_dataset_is_listed_loadable_and_read_only(monkeypatch) -> None:
    repository_root = Path(__file__).resolve().parents[3]
    monkeypatch.setattr(store.settings, "test_dir", str(repository_root / "test"))

    status, body = call("GET", "/api/configs")
    assert status == 200
    summary = next(
        config for config in body["configs"] if config["id"] == "test-testing-dataset"
    )
    assert summary["builtin"] is True
    assert summary["package_count"] == 9
    assert summary["truck_count"] == 1

    status, loaded = call("GET", "/api/configs/test-testing-dataset")
    assert status == 200
    assert len(loaded["problem"]["packages"]) == 9
    assert len(loaded["problem"]["trucks"]) == 1
    assert call("DELETE", "/api/configs/test-testing-dataset")[0] == 403


def test_root_testing_dataset_matches_shared_fixture() -> None:
    repository_root = Path(__file__).resolve().parents[3]
    assert (repository_root / "test/testing-dataset.json").read_bytes() == (
        repository_root / "data/testing/testing-dataset.json"
    ).read_bytes()


@pytest.mark.parametrize("contents", [b"\xff", b"not JSON", b"{}"])
def test_invalid_test_configs_do_not_hide_valid_configs(
    contents: bytes, tmp_path, monkeypatch
) -> None:
    monkeypatch.setattr(store.settings, "test_dir", str(tmp_path))
    source = Path(__file__).resolve().parents[3] / "test/testing-dataset.json"
    (tmp_path / "valid.json").write_bytes(source.read_bytes())
    (tmp_path / "invalid.json").write_bytes(contents)

    status, body = call("GET", "/api/configs")
    assert status == 200
    ids = {config["id"] for config in body["configs"]}
    assert "test-valid" in ids
    assert "test-invalid" not in ids
    assert call("GET", "/api/configs/test-valid")[0] == 200


def test_upload_saves_lists_loads_and_deletes(
    single_truck_problem: Problem, data_dir
) -> None:
    status, saved = call("POST", "/api/configs", upload(single_truck_problem))
    assert status == 201
    assert saved["name"] == "My fleet"
    assert saved["builtin"] is False
    assert saved["created_at"]
    assert (data_dir / "configs" / f"{saved['id']}.json").exists()

    assert uploaded_ids() == [saved["id"]]
    status, loaded = call("GET", f"/api/configs/{saved['id']}")
    assert status == 200
    assert Problem.model_validate(loaded["problem"]) == single_truck_problem

    assert call("DELETE", f"/api/configs/{saved['id']}") == (204, None)
    assert uploaded_ids() == []
    assert call("GET", f"/api/configs/{saved['id']}")[0] == 404
    assert call("DELETE", f"/api/configs/{saved['id']}")[0] == 404


def test_uploads_are_listed_newest_first(single_truck_problem: Problem) -> None:
    first = call("POST", "/api/configs", upload(single_truck_problem, "first"))[1]
    second = call("POST", "/api/configs", upload(single_truck_problem, "second"))[1]
    assert uploaded_ids() == [second["id"], first["id"]]


def test_accepts_the_full_file_envelope_and_trims_the_name(
    single_truck_problem: Problem,
) -> None:
    payload = {
        "schema_version": 1,
        "name": "  Padded  ",
        "description": "From a file",
        "problem": single_truck_problem.model_dump(mode="json"),
    }
    status, saved = call("POST", "/api/configs", payload)
    assert status == 201
    assert saved["name"] == "Padded"
    assert saved["description"] == "From a file"


@pytest.mark.parametrize("name", ["my FLEET", "Example Fleet"])
def test_rejects_duplicate_names_case_insensitively(
    single_truck_problem: Problem, name: str
) -> None:
    assert call("POST", "/api/configs", upload(single_truck_problem))[0] == 201
    status, body = call("POST", "/api/configs", upload(single_truck_problem, name))
    assert status == 409
    assert "already exists" in body["detail"]


def test_builtins_cannot_be_deleted() -> None:
    status, body = call("DELETE", "/api/configs/builtin-example-fleet")
    assert status == 403
    assert "cannot be deleted" in body["detail"]
    assert call("GET", "/api/configs/builtin-example-fleet")[0] == 200


@pytest.mark.parametrize(
    "config_id",
    [
        "..%2F..%2Fsecret",
        "test-..%2F..%2Fsecret",
        "builtin-missing",
        "ABC",
        "0" * 31,
        "0" * 32,
    ],
)
def test_unknown_or_malformed_ids_are_not_found(config_id: str) -> None:
    assert call("GET", f"/api/configs/{config_id}")[0] == 404
    assert call("DELETE", f"/api/configs/{config_id}")[0] == 404


@pytest.mark.parametrize(
    "change",
    [
        lambda payload: payload.update(name=""),
        lambda payload: payload.update(name="   "),
        lambda payload: payload.update(name="x" * (limits.MAX_CONFIG_NAME_LENGTH + 1)),
        lambda payload: payload.update(schema_version=2),
        lambda payload: payload.update(unexpected=True),
        lambda payload: payload["problem"].update(trucks=[]),
        lambda payload: payload["problem"]["packages"][0].update(width=0),
        lambda payload: payload["problem"]["packages"].append(
            payload["problem"]["packages"][0]
        ),
    ],
)
def test_rejects_invalid_uploads(single_truck_problem: Problem, change) -> None:
    payload = upload(single_truck_problem)
    change(payload)
    status, body = call("POST", "/api/configs", payload)
    assert status == 422
    assert body["detail"]
    assert uploaded_ids() == []


def test_rejects_problems_beyond_execution_limits(
    single_truck_problem: Problem,
) -> None:
    too_many = upload(single_truck_problem)
    package = too_many["problem"]["packages"][0]
    too_many["problem"]["packages"] = [
        {**package, "id": f"p{index}"} for index in range(limits.MAX_PACKAGES + 1)
    ]
    status, body = call("POST", "/api/configs", too_many)
    assert status == 422
    assert "at most" in body["detail"][0]["msg"]

    too_big = upload(single_truck_problem)
    too_big["problem"]["trucks"][0].update(width=100, length=100, height=11)
    status, body = call("POST", "/api/configs", too_big)
    assert status == 422
    assert "aggregate truck volume" in body["detail"][0]["msg"]
    assert uploaded_ids() == []


def test_rejects_oversized_upload_body(single_truck_problem: Problem) -> None:
    payload = upload(single_truck_problem)
    payload["description"] = " " * limits.MAX_REQUEST_BYTES
    status, body = call("POST", "/api/configs", payload)
    assert status == 422
    assert body == {"detail": f"Request body exceeds {limits.MAX_REQUEST_BYTES} bytes."}


def test_corrupt_or_foreign_files_do_not_break_the_list(
    single_truck_problem: Problem, data_dir
) -> None:
    saved = call("POST", "/api/configs", upload(single_truck_problem))[1]
    directory = data_dir / "configs"
    (directory / f"{'a' * 32}.json").write_text("{not json", encoding="utf-8")
    (directory / "notes.json").write_text(json.dumps(saved), encoding="utf-8")
    assert uploaded_ids() == [saved["id"]]
    assert call("GET", f"/api/configs/{'a' * 32}")[0] == 404
