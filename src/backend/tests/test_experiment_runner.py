import asyncio
import csv
import io
import json
import random

import pytest
from pydantic import TypeAdapter, ValidationError

from app.domain import Problem, State
from app.experiments import recorder, runner
from app.optimization.algorithms import SimulatedAnnealing
from app.optimization.initializer import generate_random_feasible_state
from app.optimization.objective import ObjectiveMode, evaluate_objective
from app.schemas import BatchExperimentResult, ExperimentResult, RunExperimentRequest


def _asgi_post(path: str, payload: dict, method: str = "POST") -> tuple[int, dict]:
    from app.main import app

    messages = []
    body = json.dumps(payload).encode()

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
    return messages[0]["status"], json.loads(
        b"".join(message.get("body", b"") for message in messages)
    )


def _asgi_chunks(
    path: str,
    chunks: list[bytes],
    origin: bytes | None = None,
    content_length: int | None = None,
) -> list[dict]:
    from app.main import app

    messages = []
    pending = iter(enumerate(chunks))

    async def receive():
        try:
            index, body = next(pending)
            return {
                "type": "http.request",
                "body": body,
                "more_body": index < len(chunks) - 1,
            }
        except StopIteration:
            return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        messages.append(message)

    headers = [(b"content-type", b"application/json")]
    if origin:
        headers.append((b"origin", origin))
    if content_length is not None:
        headers.append((b"content-length", str(content_length).encode()))
    asyncio.run(
        app(
            {
                "type": "http",
                "asgi": {"version": "3.0"},
                "http_version": "1.1",
                "method": "POST",
                "scheme": "http",
                "path": path,
                "raw_path": path.encode(),
                "query_string": b"",
                "headers": headers,
                "server": ("test", 80),
                "client": ("test", 123),
            },
            receive,
            send,
        )
    )
    return messages


def _request(request_problem: Problem, **updates: object) -> dict:
    algorithm = updates.get("algorithm", "genetic_algorithm")
    parameters = (
        {"population_size": 4, "generations": 2}
        if algorithm == "genetic_algorithm"
        else {}
    )
    return {
        "algorithm": algorithm,
        "problem": request_problem.model_dump(mode="json"),
        "seed": 42,
        "persist": False,
        "parameters": parameters,
        **updates,
    }


def test_ga_runner_uses_initial_population_handoff_and_persists(
    single_truck_problem: Problem, tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(runner.settings, "output_dir", str(tmp_path))
    request = TypeAdapter(RunExperimentRequest).validate_python(
        _request(single_truck_problem, persist=True, include_state_history=False)
    )
    result = runner.run_experiment(request)

    assert result.algorithm == "genetic_algorithm"
    assert result.variant is None
    assert result.runtime_ms >= 0
    assert result.iterations == 2
    assert len(result.history) == 3
    assert all(event.state_snapshot is None for event in result.history)
    initial = State.model_validate(result.metadata["initial_state"])
    assert initial == result.initial_state
    assert result.initial_score == result.metadata["initial_score"]
    for state, score in (
        (result.initial_state, result.initial_score),
        (result.final_state, result.final_score),
        (result.best_state, result.best_score),
    ):
        assert runner.validate_state(single_truck_problem, state).valid
        assert runner.evaluate_objective(
            single_truck_problem, state, request.objective_mode
        ) == pytest.approx(score)
    assert result.metadata["persisted"] is True
    saved = tmp_path / "experiments" / f"{result.id}.json"
    assert json.loads(saved.read_text()) == json.loads(result.model_dump_json())


def test_persist_false_does_not_create_output(
    single_truck_problem: Problem, tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(runner.settings, "output_dir", str(tmp_path))
    request = TypeAdapter(RunExperimentRequest).validate_python(
        _request(single_truck_problem, persist=False)
    )
    result = runner.run_experiment(request)
    assert result.metadata["persisted"] is False
    assert not (tmp_path / "experiments").exists()


def test_runner_rejects_search_score_that_does_not_match_state(
    single_truck_problem: Problem, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.optimization.algorithms import GeneticAlgorithm

    original_run = GeneticAlgorithm.run

    def mismatched(self, *args, **kwargs):
        result = original_run(self, *args, **kwargs)
        return result.model_copy(update={"final_score": result.final_score + 1})

    monkeypatch.setattr(GeneticAlgorithm, "run", mismatched)
    request = TypeAdapter(RunExperimentRequest).validate_python(
        _request(single_truck_problem)
    )
    with pytest.raises(ValueError, match="does not match state score"):
        runner.run_experiment(request)


def test_runner_rejects_invalid_search_state(
    single_truck_problem: Problem, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.optimization.algorithms import GeneticAlgorithm

    original_run = GeneticAlgorithm.run

    def invalid_state(self, *args, **kwargs):
        result = original_run(self, *args, **kwargs)
        return result.model_copy(update={"final_state": State(placements=[])})

    monkeypatch.setattr(GeneticAlgorithm, "run", invalid_state)
    request = TypeAdapter(RunExperimentRequest).validate_python(
        _request(single_truck_problem)
    )
    with pytest.raises(ValueError, match="invalid state"):
        runner.run_experiment(request)


def test_persistence_never_overwrites_existing_id(
    single_truck_problem: Problem, tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(runner.settings, "output_dir", str(tmp_path))
    request = TypeAdapter(RunExperimentRequest).validate_python(
        _request(single_truck_problem, persist=True)
    )
    first = runner.run_experiment(request)
    path = tmp_path / "experiments" / f"{first.id}.json"
    original = path.read_bytes()
    monkeypatch.setattr(
        runner, "uuid4", lambda: type("UUID", (), {"__str__": lambda _: first.id})()
    )
    with pytest.raises(FileExistsError):
        runner.run_experiment(request)
    assert path.read_bytes() == original


def test_list_endpoint_reads_saved_result(
    single_truck_problem: Problem, tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.api.experiments import list_experiments

    monkeypatch.setattr(runner.settings, "output_dir", str(tmp_path))
    request = TypeAdapter(RunExperimentRequest).validate_python(
        _request(single_truck_problem, persist=True)
    )
    result = runner.run_experiment(request)
    assert list_experiments().experiments == [result]


def test_list_endpoint_uses_empty_only_for_missing_directory(
    tmp_path, monkeypatch
) -> None:
    from app.api.experiments import list_experiments

    monkeypatch.setattr(runner.settings, "output_dir", str(tmp_path))
    assert list_experiments().experiments == []
    (tmp_path / "experiments").write_text("not a directory")
    with pytest.raises(NotADirectoryError):
        list_experiments()


def test_list_endpoint_reads_utf8_experiment(
    single_truck_problem, tmp_path, monkeypatch
) -> None:
    from app.api.experiments import list_experiments

    monkeypatch.setattr(runner.settings, "output_dir", str(tmp_path))
    request = TypeAdapter(RunExperimentRequest).validate_python(
        _request(single_truck_problem, persist=True)
    )
    result = runner.run_experiment(request)
    path = tmp_path / "experiments" / f"{result.id}.json"
    path.write_text(result.model_dump_json().replace("base", "café"), encoding="utf-8")
    assert list_experiments().experiments[0].problem.packages[0].id == "café"


def test_persistence_does_not_publish_json_until_writer_finishes(
    single_truck_problem: Problem, tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(runner.settings, "output_dir", str(tmp_path))
    original = recorder._write_persistence_temp
    observed = []

    def observe_then_write(file, payload):
        from app.api.experiments import list_experiments

        observed.append(list_experiments().experiments)
        original(file, payload)

    monkeypatch.setattr(recorder, "_write_persistence_temp", observe_then_write)
    request = TypeAdapter(RunExperimentRequest).validate_python(
        _request(single_truck_problem, persist=True)
    )
    result = runner.run_experiment(request)
    assert observed == [[]]
    assert result.metadata["persisted"] is True
    assert json.loads(
        (tmp_path / "experiments" / f"{result.id}.json").read_text()
    ) == json.loads(result.model_dump_json())
    assert list((tmp_path / "experiments").glob("*.tmp")) == []


def test_persistence_writer_failure_leaves_no_final_or_temp_file(
    single_truck_problem: Problem, tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(runner.settings, "output_dir", str(tmp_path))

    def fail_after_write(file, payload):
        file.write(payload)
        raise OSError("simulated close/write failure")

    monkeypatch.setattr(recorder, "_write_persistence_temp", fail_after_write)
    request = TypeAdapter(RunExperimentRequest).validate_python(
        _request(single_truck_problem, persist=True)
    )
    with pytest.raises(OSError, match="simulated"):
        runner.run_experiment(request)
    directory = tmp_path / "experiments"
    assert list(directory.glob("*.json")) == []
    assert list(directory.glob(".*.tmp")) == []


def test_persistence_close_failure_leaves_no_final_or_temp_file(
    single_truck_problem: Problem, tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(runner.settings, "output_dir", str(tmp_path))
    real_named_temporary_file = recorder.tempfile.NamedTemporaryFile

    class CloseFailure:
        def __init__(self, **kwargs):
            self.file = real_named_temporary_file(**kwargs)

        def __enter__(self):
            return self.file

        def __exit__(self, *_args):
            self.file.close()
            raise OSError("simulated close failure")

    monkeypatch.setattr(recorder.tempfile, "NamedTemporaryFile", CloseFailure)
    request = TypeAdapter(RunExperimentRequest).validate_python(
        _request(single_truck_problem, persist=True)
    )
    with pytest.raises(OSError, match="close"):
        runner.run_experiment(request)
    directory = tmp_path / "experiments"
    assert list(directory.glob("*.json")) == []
    assert list(directory.glob(".*.tmp")) == []


def test_http_executes_ga_and_serializes_result(
    single_truck_problem: Problem, tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(runner.settings, "output_dir", str(tmp_path))
    status, body = _asgi_post("/api/experiments/run", _request(single_truck_problem))
    assert status == 200
    assert "placeholder" not in body["metadata"]
    assert body["metadata"]["persisted"] is False
    for state_field, score_field in (
        ("initial_state", "initial_score"),
        ("final_state", "final_score"),
        ("best_state", "best_score"),
    ):
        state = State.model_validate(body[state_field])
        assert runner.validate_state(single_truck_problem, state).valid
        assert evaluate_objective(
            single_truck_problem,
            state,
            body["objective_mode"],
        ) == pytest.approx(body[score_field])
    assert len(body["history"]) == 3
    assert all(event["state_snapshot"] is not None for event in body["history"])


@pytest.mark.parametrize("objective_mode", ["total_value", "eta_weighted_value"])
@pytest.mark.parametrize("algorithm", ["genetic_algorithm", "hill_climbing"])
def test_http_searches_multi_truck_with_each_objective(
    multi_truck_problem: Problem, objective_mode: str, algorithm: str
) -> None:
    parameters = (
        {"population_size": 2, "generations": 2}
        if algorithm == "genetic_algorithm"
        else {"max_iterations": 2, "candidates_per_iteration": 2, "max_sideways": 1}
    )
    payload = _request(
        multi_truck_problem,
        algorithm=algorithm,
        objective_mode=objective_mode,
        parameters=parameters,
    )
    if algorithm == "hill_climbing":
        payload["variant"] = "sideways"
    status, body = _asgi_post("/api/experiments/run", payload)
    assert status == 200
    assert body["objective_mode"] == objective_mode
    for state_field, score_field in (
        ("initial_state", "initial_score"),
        ("final_state", "final_score"),
        ("best_state", "best_score"),
    ):
        state = State.model_validate(body[state_field])
        assert runner.validate_state(multi_truck_problem, state).valid
        assert evaluate_objective(
            multi_truck_problem, state, objective_mode
        ) == pytest.approx(body[score_field])
    assert all(event["state_snapshot"] is not None for event in body["history"])


def test_http_runs_sideways_hill_climbing(single_truck_problem: Problem) -> None:
    status, body = _asgi_post(
        "/api/experiments/run",
        _request(
            single_truck_problem,
            algorithm="hill_climbing",
            variant="sideways",
            objective_mode="eta_weighted_value",
        ),
    )
    assert status == 200
    assert body["algorithm"] == "hill_climbing"
    assert body["variant"] == "sideways"
    assert body["initial_score"] == evaluate_objective(
        single_truck_problem,
        State.model_validate(body["initial_state"]),
        "eta_weighted_value",
    )


@pytest.mark.parametrize("algorithm", ["genetic_algorithm", "hill_climbing"])
def test_http_accepts_maximum_finite_values_and_huge_eta(algorithm: str) -> None:
    from app.domain import PackageSpec, TruckSpec

    maximum = float.fromhex("0x1.fffffffffffffp+1023")
    problem = Problem(
        packages=[
            PackageSpec(
                id="p",
                width=1,
                length=1,
                height=1,
                value=maximum,
                weight=1,
                is_fragile=False,
                eta=10**300,
            )
        ],
        trucks=[TruckSpec(id="t", width=1, length=1, height=1, max_capacity=maximum)],
    )
    parameters = (
        {"population_size": 3, "generations": 2}
        if algorithm == "genetic_algorithm"
        else {"max_iterations": 2, "candidates_per_iteration": 2, "max_sideways": 1}
    )
    payload = _request(
        problem, algorithm=algorithm, seed=2**53 - 1, parameters=parameters
    )
    payload["objective_mode"] = "eta_weighted_value"
    if algorithm == "hill_climbing":
        payload["variant"] = "sideways"
    assert _asgi_post("/api/experiments/run", payload)[0] == 200


def test_preflight_preserves_weighted_finite_bound_but_rejects_total_overflow() -> None:
    from app.domain import PackageSpec, TruckSpec

    maximum = float.fromhex("0x1.fffffffffffffp+1023")
    problem = Problem(
        packages=[
            PackageSpec(
                id=f"p{i}",
                width=1,
                length=1,
                height=1,
                value=maximum,
                weight=1,
                is_fragile=False,
                eta=10**300,
            )
            for i in range(2)
        ],
        trucks=[TruckSpec(id="t", width=2, length=1, height=1, max_capacity=maximum)],
    )
    weighted = TypeAdapter(RunExperimentRequest).validate_python(
        _request(
            problem,
            objective_mode="eta_weighted_value",
            parameters={"population_size": 2, "generations": 1},
        )
    )
    result = runner.run_experiment(weighted)
    assert result.best_score > 0 and result.best_score < float("inf")
    total = TypeAdapter(RunExperimentRequest).validate_python(
        _request(
            problem,
            objective_mode="total_value",
            parameters={"population_size": 2, "generations": 1},
        )
    )
    with pytest.raises(ValueError, match="representable"):
        runner.run_experiment(total)


def test_ga_runner_eta_objective_on_multitruck_problem(
    multi_truck_problem: Problem,
) -> None:
    request = TypeAdapter(RunExperimentRequest).validate_python(
        _request(
            multi_truck_problem,
            objective_mode="eta_weighted_value",
            parameters={"population_size": 3, "generations": 1},
        )
    )
    result = runner.run_experiment(request)
    assert result.initial_score == evaluate_objective(
        multi_truck_problem, result.initial_state, "eta_weighted_value"
    )
    assert result.best_score == evaluate_objective(
        multi_truck_problem, result.best_state, "eta_weighted_value"
    )


def test_metrics_and_summary_use_generation_history_and_population_statistics(
    single_truck_problem: Problem,
) -> None:
    from app.experiments.metrics import calculate_metrics, summarize_results

    request = TypeAdapter(RunExperimentRequest).validate_python(
        _request(
            single_truck_problem, parameters={"population_size": 4, "generations": 2}
        )
    )
    result = runner.run_experiment(request)
    metrics = calculate_metrics(result)
    assert metrics["max_fitness_history"] == [
        event.current_score for event in result.history
    ]
    assert "metrics" in result.metadata
    assert metrics["avg_fitness_history"] == [
        event.mean_score for event in result.history
    ]
    summary = summarize_results([result])
    assert summary["run_count"] == 1
    assert summary["mean_best_score"] == result.best_score
    assert summary["std_best_score"] == 0
    assert summary["mean_runtime_ms"] == result.runtime_ms


def test_summary_empty_and_extreme_finite_values() -> None:
    from app.experiments.metrics import summarize_results

    assert summarize_results([]) == {
        "run_count": 0,
        "mean_best_score": None,
        "std_best_score": None,
        "min_best_score": None,
        "max_best_score": None,
        "mean_runtime_ms": None,
        "min_runtime_ms": None,
        "max_runtime_ms": None,
    }
    maximum = float.fromhex("0x1.fffffffffffffp+1023")
    assert (
        maximum
        == summarize_results([_minimal_result(maximum), _minimal_result(maximum)])[
            "mean_best_score"
        ]
    )
    assert (
        summarize_results([_minimal_result(maximum), _minimal_result(-maximum)])[
            "std_best_score"
        ]
        == maximum
    )
    assert (
        summarize_results([_minimal_result(1), _minimal_result(3)])["std_best_score"]
        == 1
    )


def _minimal_result(score: float):
    from app.domain import Problem, State
    from app.schemas.experiment import ExperimentResult

    return ExperimentResult(
        id="summary",
        problem=Problem(
            packages=[],
            trucks=[
                {"id": "t", "width": 1, "length": 1, "height": 1, "max_capacity": 1}
            ],
        ),
        algorithm="genetic_algorithm",
        variant=None,
        objective_mode="total_value",
        seed=1,
        parameters={},
        initial_state=State(placements=[]),
        final_state=State(placements=[]),
        best_state=State(placements=[]),
        initial_score=score,
        final_score=score,
        best_score=score,
        runtime_ms=3,
        iterations=1,
        history=[],
    )


def test_mandatory_presets_keep_two_sweeps_separate() -> None:
    from app.experiments.presets import ga_mandatory_presets

    presets = ga_mandatory_presets()
    assert len(presets) == 18
    groups = {preset.label for preset in presets}
    assert groups == {"generations", "population_size"}
    assert (
        len(
            {
                (
                    preset.label,
                    preset.parameters.population_size,
                    preset.parameters.generations,
                    preset.seed,
                )
                for preset in presets
            }
        )
        == 18
    )


def test_batch_api_runs_two_labeled_runs_and_persists_json_csv(
    single_truck_problem: Problem, tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.api import experiments

    monkeypatch.setattr(experiments.settings, "output_dir", str(tmp_path))
    payload = {
        "problem": single_truck_problem.model_dump(mode="json"),
        "persist": True,
        "runs": [
            {
                "label": "same-label",
                "seed": seed,
                "algorithm": "genetic_algorithm",
                "parameters": {"population_size": 3, "generations": 1},
            }
            for seed in (42, 123)
        ],
    }
    status, body = _asgi_post("/api/experiments/batch", payload)
    assert status == 200
    assert body["summary"]["run_count"] == 2
    assert [spec["label"] for spec in body["requested_runs"]] == [
        "same-label",
        "same-label",
    ]
    assert len(body["groups"]) == 1
    directory = tmp_path / "experiments"
    batch_directory = tmp_path / "batches"
    assert len(list(directory.glob("*.json"))) == 2
    assert (batch_directory / f"{body['id']}.csv").exists()
    saved_batch = json.loads(
        (batch_directory / f"{body['id']}.json").read_text(encoding="utf-8")
    )
    assert len(saved_batch["requested_runs"]) == len(saved_batch["results"]) == 2
    assert saved_batch["groups"] == body["groups"]
    csv_header = (batch_directory / f"{body['id']}.csv").read_text().splitlines()[0]
    assert "objective_mode" in csv_header and "variant" in csv_header
    csv_rows = list(
        csv.DictReader(
            io.StringIO(
                (batch_directory / f"{body['id']}.csv").read_text(encoding="utf-8"),
                newline="",
            )
        )
    )
    assert [row["label"] for row in csv_rows] == ["same-label", "same-label"]


def test_batch_csv_escapes_formula_labels_but_json_keeps_original(
    single_truck_problem: Problem, tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.api import experiments

    monkeypatch.setattr(experiments.settings, "output_dir", str(tmp_path))
    label = " \t=1+1"
    status, body = _asgi_post(
        "/api/experiments/batch",
        {
            "problem": single_truck_problem.model_dump(mode="json"),
            "persist": True,
            "runs": [
                {
                    "label": label,
                    "seed": 42,
                    "parameters": {"population_size": 2, "generations": 1},
                }
            ],
        },
    )
    assert status == 200
    directory = tmp_path / "batches"
    stored = json.loads((directory / f"{body['id']}.json").read_text(encoding="utf-8"))
    assert stored["requested_runs"][0]["label"] == label
    csv_rows = list(
        csv.DictReader(
            io.StringIO(
                (directory / f"{body['id']}.csv").read_text(encoding="utf-8"),
                newline="",
            )
        )
    )
    assert csv_rows[0]["label"] == "'" + label


def test_ga_mandatory_preset_rejects_objective_override_before_dispatch(
    single_truck_problem: Problem, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.experiments import batch

    monkeypatch.setattr(
        batch,
        "run_experiment",
        lambda *_a, **_k: pytest.fail("preset dispatched"),
    )
    status, body = _asgi_post(
        "/api/experiments/batch",
        {
            "problem": single_truck_problem.model_dump(mode="json"),
            "preset": "ga_mandatory",
            "objective_mode": "eta_weighted_value",
            "persist": False,
        },
    )
    assert status == 422
    assert "total_value" in str(body["detail"]).lower()


def test_batch_saved_results_remain_listable_as_individual_runs(
    single_truck_problem: Problem, tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.api import experiments

    monkeypatch.setattr(experiments.settings, "output_dir", str(tmp_path))
    payload = {
        "problem": single_truck_problem.model_dump(mode="json"),
        "persist": True,
        "runs": [
            {
                "label": "one",
                "seed": seed,
                "parameters": {"population_size": 2, "generations": 1},
            }
            for seed in (1, 2)
        ],
    }
    status, batch = _asgi_post("/api/experiments/batch", payload)
    assert status == 200
    status, listed = _asgi_post("/api/experiments", {}, method="GET")
    assert status == 200
    assert len(listed["experiments"]) == 2
    assert (tmp_path / "batches" / f"{batch['id']}.json").exists()


def test_batch_preflights_every_run_before_executing(
    single_truck_problem: Problem, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.experiments import batch

    monkeypatch.setattr(
        batch,
        "run_experiment",
        lambda *_a, **_k: pytest.fail("batch dispatched"),
    )
    payload = {
        "problem": single_truck_problem.model_dump(mode="json"),
        "persist": False,
        "runs": [
            {
                "label": "ok",
                "seed": 42,
                "parameters": {"population_size": 2, "generations": 1},
            },
            {
                "label": "bad",
                "seed": 43,
                "parameters": {"population_size": 101, "generations": 1},
            },
        ],
    }
    status, body = _asgi_post("/api/experiments/batch", payload)
    assert status == 422
    assert "execution limit" in str(body["detail"]).lower()


def test_batch_internal_search_event_validation_is_not_reported_as_422(
    single_truck_problem: Problem, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.optimization.algorithms import GeneticAlgorithm
    from app.schemas.experiment import SearchEvent

    def fail_with_invalid_search_event(*_args, **_kwargs):
        SearchEvent(iteration=0, current_score=float("nan"), best_score=0)

    monkeypatch.setattr(GeneticAlgorithm, "run", fail_with_invalid_search_event)
    payload = {
        "problem": single_truck_problem.model_dump(mode="json"),
        "persist": False,
        "runs": [
            {
                "label": "internal-error",
                "seed": 42,
                "parameters": {"population_size": 2, "generations": 1},
            }
        ],
    }

    with pytest.raises(ValidationError):
        _asgi_post("/api/experiments/batch", payload)


def test_batch_persist_false_creates_no_files(
    single_truck_problem: Problem, tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.api import experiments

    monkeypatch.setattr(experiments.settings, "output_dir", str(tmp_path))
    payload = {
        "problem": single_truck_problem.model_dump(mode="json"),
        "persist": False,
        "runs": [
            {
                "label": "one",
                "seed": 42,
                "parameters": {"population_size": 2, "generations": 1},
            }
        ],
    }
    status, body = _asgi_post("/api/experiments/batch", payload)
    assert status == 200 and body["persisted"] is False
    assert not (tmp_path / "experiments").exists()


def test_batch_storage_failure_propagates_as_server_error(
    single_truck_problem: Problem, tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.api import experiments
    from app.experiments import batch
    from app.schemas.experiment import BatchExperimentRequest

    monkeypatch.setattr(experiments.settings, "output_dir", str(tmp_path))
    monkeypatch.setattr(
        batch,
        "record_batch",
        lambda *_a: (_ for _ in ()).throw(OSError("disk")),
    )
    payload = {
        "problem": single_truck_problem.model_dump(mode="json"),
        "persist": True,
        "runs": [
            {
                "label": "one",
                "seed": 1,
                "parameters": {"population_size": 2, "generations": 1},
            }
        ],
    }
    with pytest.raises(OSError, match="disk"):
        experiments.run_batch(BatchExperimentRequest.model_validate(payload))
    assert list((tmp_path / "experiments").glob("*.json")) == []


def test_mandatory_preset_executes_all_eighteen_runs() -> None:
    from app.domain import Problem

    status, body = _asgi_post(
        "/api/experiments/batch",
        {
            "problem": Problem(
                packages=[],
                trucks=[
                    {"id": "t", "width": 1, "length": 1, "height": 1, "max_capacity": 1}
                ],
            ).model_dump(mode="json"),
            "preset": "ga_mandatory",
            "persist": False,
        },
    )
    assert status == 200
    assert body["summary"]["run_count"] == 18
    assert len(body["groups"]) == 6
    assert {group["summary"]["run_count"] for group in body["groups"]} == {3}
    assert (
        len(
            {
                (group["label"], json.dumps(group["parameters"], sort_keys=True))
                for group in body["groups"]
            }
        )
        == 6
    )


def test_batch_recorder_collision_preserves_existing_data(tmp_path) -> None:
    from app.experiments.recorder import record_batch
    from app.schemas.experiment import BatchExperimentResult, BatchRunSpec

    directory = tmp_path / "experiments"
    directory.mkdir()
    marker = directory / "batch.csv"
    marker.write_text("keep", encoding="utf-8")
    batch = BatchExperimentResult(
        id="batch",
        requested_runs=[BatchRunSpec(label="label", seed=1)],
        results=[_minimal_result(1)],
        summary={},
        groups=[],
        persisted=True,
    )
    with pytest.raises(FileExistsError):
        record_batch(batch, directory)
    assert marker.read_text(encoding="utf-8") == "keep"


def test_batch_recorder_json_collision_removes_only_new_csv(tmp_path) -> None:
    from app.experiments.recorder import record_batch
    from app.schemas.experiment import BatchExperimentResult, BatchRunSpec

    directory = tmp_path / "experiments"
    directory.mkdir()
    marker = directory / "batch.json"
    marker.write_text("keep", encoding="utf-8")
    batch = BatchExperimentResult(
        id="batch",
        requested_runs=[BatchRunSpec(label="label", seed=1)],
        results=[_minimal_result(1)],
        summary={},
        groups=[],
        persisted=True,
    )
    with pytest.raises(FileExistsError):
        record_batch(batch, directory)
    assert marker.read_text(encoding="utf-8") == "keep"
    assert not (directory / "batch.csv").exists()


def test_execution_budget_accepts_ga_limits_and_rejects_next_value(
    single_truck_problem: Problem,
) -> None:
    within = TypeAdapter(RunExperimentRequest).validate_python(
        _request(
            single_truck_problem,
            parameters={"population_size": 100, "generations": 200},
        )
    )
    runner.validate_execution_budget(within)
    too_many_generations = TypeAdapter(RunExperimentRequest).validate_python(
        _request(
            single_truck_problem, parameters={"population_size": 2, "generations": 201}
        )
    )
    with pytest.raises(runner.ExecutionBudgetError):
        runner.validate_execution_budget(too_many_generations)


@pytest.mark.parametrize(
    ("algorithm", "variant", "detail"),
    [
        ("hill_climbing", "steepest_ascent", "not implemented"),
        ("hill_climbing", "random_restart", "not implemented"),
        ("hill_climbing", "stochastic", "not implemented"),
    ],
)
def test_http_returns_clear_422_for_unsupported_algorithm(
    single_truck_problem: Problem, algorithm: str, variant: str | None, detail: str
) -> None:
    payload = _request(single_truck_problem, algorithm=algorithm)
    if variant is not None:
        payload["variant"] = variant
    status, body = _asgi_post("/api/experiments/run", payload)
    assert status == 422
    assert detail in body["detail"].lower()


def test_http_invalid_parameters_return_422(single_truck_problem: Problem) -> None:
    status, body = _asgi_post(
        "/api/experiments/run",
        _request(single_truck_problem, parameters={"population_size": 1}),
    )
    assert status == 422
    assert body["detail"]


def test_http_rejects_oversized_work_before_initializer(
    single_truck_problem: Problem, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.optimization.algorithms import GeneticAlgorithm

    monkeypatch.setattr(
        GeneticAlgorithm, "run", lambda *_a, **_k: pytest.fail("GA dispatched")
    )
    payload = _request(single_truck_problem)
    payload["problem"]["trucks"][0].update(width=2000, length=2000, height=2000)
    status, body = _asgi_post("/api/experiments/run", payload)
    assert status == 422
    assert "execution limit" in body["detail"].lower()


def test_http_rejects_oversized_ga_parameters_before_initializer(
    single_truck_problem: Problem, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.optimization.algorithms import GeneticAlgorithm

    monkeypatch.setattr(
        GeneticAlgorithm, "run", lambda *_a, **_k: pytest.fail("GA dispatched")
    )
    status, body = _asgi_post(
        "/api/experiments/run",
        _request(single_truck_problem, parameters={"population_size": 101}),
    )
    assert status == 422
    assert "execution limit" in body["detail"].lower()


def test_http_rejects_chunked_oversized_run_body_with_cors(
    single_truck_problem: Problem,
) -> None:
    body = json.dumps(_request(single_truck_problem)).encode() + b" " * 262145
    messages = _asgi_chunks(
        "/api/experiments/run", [body[:140000], body[140000:]], b"http://localhost:5173"
    )
    assert messages[0]["status"] == 422
    headers = dict(messages[0]["headers"])
    assert headers[b"access-control-allow-origin"] == b"http://localhost:5173"


def test_http_body_cap_accepts_chunked_body_with_and_without_length(
    single_truck_problem: Problem,
) -> None:
    body = json.dumps(_request(single_truck_problem)).encode()
    for content_length in (None, len(body)):
        messages = _asgi_chunks(
            "/api/experiments/run",
            [body[:17], body[17:]],
            content_length=content_length,
        )
        assert messages[0]["status"] == 200


def test_http_body_cap_rejects_without_calling_downstream_app() -> None:
    from app.api.request_limits import RunBodyLimitMiddleware

    async def downstream(*_args, **_kwargs):
        pytest.fail("downstream app called")

    middleware = RunBodyLimitMiddleware(downstream)
    messages = []

    async def receive():
        return {"type": "http.request", "body": b"x" * 262145, "more_body": False}

    async def send(message):
        messages.append(message)

    asyncio.run(
        middleware(
            {"type": "http", "method": "POST", "path": "/api/experiments/run"},
            receive,
            send,
        )
    )
    assert messages[0]["status"] == 422


@pytest.mark.parametrize("seed", [2**53, -(2**53)])
def test_http_rejects_unsafe_seed(single_truck_problem: Problem, seed: int) -> None:
    status, body = _asgi_post(
        "/api/experiments/run", _request(single_truck_problem, seed=seed)
    )
    assert status == 422
    assert body["detail"]


def test_http_rejects_overlong_ids_before_parsing(
    single_truck_problem: Problem,
) -> None:
    data = single_truck_problem.model_dump(mode="json")
    data["packages"][0]["id"] = "p" * 129
    status, body = _asgi_post(
        "/api/experiments/run",
        _request(single_truck_problem, problem=data),
    )
    assert status == 422
    assert body["detail"]


@pytest.mark.parametrize(
    "overage",
    ["packages", "trucks", "package_id", "truck_id"],
)
def test_http_rejects_problem_count_and_id_limits_before_ga(
    single_truck_problem: Problem,
    monkeypatch: pytest.MonkeyPatch,
    overage: str,
) -> None:
    from app.optimization.algorithms import GeneticAlgorithm

    monkeypatch.setattr(
        GeneticAlgorithm, "run", lambda *_a, **_k: pytest.fail("GA dispatched")
    )
    problem = single_truck_problem.model_dump(mode="json")
    if overage == "packages":
        problem["packages"] = [
            {**problem["packages"][0], "id": f"p{index}"} for index in range(101)
        ]
    elif overage == "trucks":
        problem["trucks"] = [
            {**problem["trucks"][0], "id": f"t{index}"} for index in range(21)
        ]
    elif overage == "package_id":
        problem["packages"][0]["id"] = "p" * 129
    else:
        problem["trucks"][0]["id"] = "t" * 129
    status, body = _asgi_post(
        "/api/experiments/run", _request(single_truck_problem, problem=problem)
    )
    assert status == 422
    assert body["detail"]


@pytest.mark.parametrize("invalid_id", [None, 7])
def test_http_rejects_malformed_ids_as_validation_errors(
    single_truck_problem: Problem, invalid_id: object
) -> None:
    data = single_truck_problem.model_dump(mode="json")
    data["packages"][0]["id"] = invalid_id
    status, body = _asgi_post(
        "/api/experiments/run",
        _request(single_truck_problem, problem=data),
    )
    assert status == 422
    assert body["detail"]


def test_http_rejects_unrepresentable_objective_before_ga(
    single_truck_problem: Problem, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.optimization.algorithms import GeneticAlgorithm

    monkeypatch.setattr(
        GeneticAlgorithm, "run", lambda *_a, **_k: pytest.fail("GA dispatched")
    )
    data = single_truck_problem.model_dump(mode="json")
    for package in data["packages"]:
        package["value"] = 1e308
    status, body = _asgi_post(
        "/api/experiments/run", _request(Problem.model_validate(data))
    )
    assert status == 422
    assert "representable" in body["detail"]


def _sa_request(problem: Problem, **updates: object) -> dict:
    return (
        _request(
            problem,
            algorithm="simulated_annealing",
            parameters={
                "max_iterations": 6,
                "initial_temperature": 10,
                "alpha": 0.8,
                "stuck_patience": 2,
            },
        )
        | updates
    )


@pytest.mark.parametrize(
    "fixture_name", ["single_truck_problem", "multi_truck_problem"]
)
@pytest.mark.parametrize("mode", list(ObjectiveMode))
@pytest.mark.parametrize("snapshots", [False, True])
def test_sa_runner_matches_direct_execution_and_replays_seed(
    request: pytest.FixtureRequest,
    fixture_name: str,
    mode: ObjectiveMode,
    snapshots: bool,
) -> None:
    problem = request.getfixturevalue(fixture_name)
    parsed = TypeAdapter(RunExperimentRequest).validate_python(
        _sa_request(problem, objective_mode=mode, include_state_history=snapshots)
    )
    original = parsed.model_dump_json()
    rng = random.Random(parsed.seed)
    initial = generate_random_feasible_state(problem, rng)
    direct = SimulatedAnnealing().run(
        problem,
        initial,
        objective_mode=mode,
        rng=rng,
        parameters=parsed.parameters,
        include_state_history=snapshots,
    )
    result = runner.run_experiment(parsed)
    replay = runner.run_experiment(parsed)
    assert result.algorithm == "simulated_annealing"
    assert result.variant is None
    assert result.problem == problem
    assert result.parameters == parsed.parameters.model_dump(mode="json")
    assert result.initial_state == initial
    assert result.initial_score == evaluate_objective(problem, initial, mode)
    assert result.final_state == direct.final_state
    assert result.best_state == direct.best_state
    assert result.final_score == direct.final_score
    assert result.best_score == direct.best_score
    assert result.iterations == direct.iterations
    assert result.history == direct.history
    assert result.metadata == direct.metadata | {"persisted": False}
    assert result.runtime_ms >= 0
    assert result.model_dump(exclude={"id", "runtime_ms"}) == replay.model_dump(
        exclude={"id", "runtime_ms"}
    )
    assert parsed.model_dump_json() == original
    assert ExperimentResult.model_validate_json(result.model_dump_json()) == result


@pytest.mark.parametrize("mode", list(ObjectiveMode))
@pytest.mark.parametrize("snapshots", [False, True])
def test_http_sa_persists_and_lists_valid_multitruck_results(
    multi_truck_problem: Problem,
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
    mode: ObjectiveMode,
    snapshots: bool,
) -> None:
    monkeypatch.setattr(runner.settings, "output_dir", str(tmp_path))
    status, body = _asgi_post(
        "/api/experiments/run",
        _sa_request(
            multi_truck_problem,
            objective_mode=mode.value,
            include_state_history=snapshots,
            persist=True,
        ),
    )
    assert status == 200
    result = ExperimentResult.model_validate(body)
    assert result.metadata["persisted"] is True
    assert len(result.history) == result.iterations + 1
    assert result.best_score >= result.final_score
    for state, score in [
        (result.initial_state, result.initial_score),
        (result.final_state, result.final_score),
        (result.best_state, result.best_score),
    ]:
        assert runner.validate_state(multi_truck_problem, state).valid
        assert evaluate_objective(multi_truck_problem, state, mode) == score
    for event in result.history:
        assert (event.state_snapshot is not None) is snapshots
        if event.state_snapshot is not None:
            assert runner.validate_state(
                multi_truck_problem, event.state_snapshot
            ).valid
            assert (
                evaluate_objective(multi_truck_problem, event.state_snapshot, mode)
                == event.current_score
            )
    saved = tmp_path / "experiments" / f"{result.id}.json"
    assert ExperimentResult.model_validate_json(saved.read_text()) == result
    list_status, listing = _asgi_post("/api/experiments", {}, method="GET")
    assert list_status == 200
    assert listing["experiments"] == [body]


def test_sa_persist_false_creates_no_files(
    single_truck_problem: Problem, tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(runner.settings, "output_dir", str(tmp_path))
    status, body = _asgi_post("/api/experiments/run", _sa_request(single_truck_problem))
    assert status == 200
    assert body["metadata"]["persisted"] is False
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize(
    "parameters",
    [
        {"alpha": 0},
        {"alpha": 1},
        {"initial_temperature": 0},
        {"min_temperature": 0},
        {"max_iterations": 0},
        {"stuck_patience": 0},
    ],
)
def test_http_sa_invalid_parameters_are_rejected_before_dispatch(
    single_truck_problem: Problem,
    monkeypatch: pytest.MonkeyPatch,
    parameters: dict,
) -> None:
    monkeypatch.setattr(
        SimulatedAnnealing, "run", lambda *_a, **_k: pytest.fail("SA dispatched")
    )
    status, body = _asgi_post(
        "/api/experiments/run", _sa_request(single_truck_problem, parameters=parameters)
    )
    assert status == 422
    assert body["detail"]


def test_sa_execution_budget_boundary_and_http_rejection(
    single_truck_problem: Problem, monkeypatch: pytest.MonkeyPatch
) -> None:
    allowed = TypeAdapter(RunExperimentRequest).validate_python(
        _sa_request(single_truck_problem, parameters={"max_iterations": 5000})
    )
    runner.preflight_experiment(allowed)
    monkeypatch.setattr(
        runner,
        "generate_random_feasible_state",
        lambda *_a, **_k: pytest.fail("Initializer called"),
    )
    status, body = _asgi_post(
        "/api/experiments/run",
        _sa_request(single_truck_problem, parameters={"max_iterations": 5001}),
    )
    assert status == 422
    assert "SA iterations <= 5000" in body["detail"]


@pytest.mark.parametrize("mode", list(ObjectiveMode))
@pytest.mark.parametrize("persist", [False, True])
def test_http_sa_batch_runs_seed_set_and_writes_metrics_only_results(
    multi_truck_problem: Problem,
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
    mode: ObjectiveMode,
    persist: bool,
) -> None:
    monkeypatch.setattr(runner.settings, "output_dir", str(tmp_path))
    seeds = [42, 123, 2026]
    status, body = _asgi_post(
        "/api/experiments/batch",
        {
            "problem": multi_truck_problem.model_dump(mode="json"),
            "objective_mode": mode.value,
            "persist": persist,
            "runs": [
                {
                    "label": "SA",
                    "algorithm": "simulated_annealing",
                    "seed": seed,
                    "parameters": {"max_iterations": 4, "stuck_patience": 2},
                }
                for seed in seeds
            ],
        },
    )
    assert status == 200
    batch = BatchExperimentResult.model_validate(body)
    assert batch.persisted is persist
    assert [r.seed for r in batch.results] == seeds
    assert batch.summary["run_count"] == 3
    assert len(batch.groups) == 1
    assert batch.groups[0].summary == batch.summary
    assert batch.summary["mean_best_score"] == pytest.approx(
        sum(r.best_score for r in batch.results) / 3
    )
    for result in batch.results:
        assert result.algorithm == "simulated_annealing"
        assert result.objective_mode is mode
        assert result.history
        assert all(e.state_snapshot is None for e in result.history)
        assert "stuck_events" in result.metadata
        assert result.metadata["persisted"] is persist
        assert runner.validate_state(result.problem, result.best_state).valid
        assert (
            evaluate_objective(result.problem, result.best_state, mode)
            == result.best_score
        )
        if persist:
            saved = tmp_path / "experiments" / f"{result.id}.json"
            assert ExperimentResult.model_validate_json(saved.read_text()) == result
    if persist:
        directory = tmp_path / "batches"
        assert (
            BatchExperimentResult.model_validate_json(
                (directory / f"{batch.id}.json").read_text()
            )
            == batch
        )
        rows = list(
            csv.DictReader(io.StringIO((directory / f"{batch.id}.csv").read_text()))
        )
        assert [int(row["seed"]) for row in rows] == seeds
        assert all(row["algorithm"] == "simulated_annealing" for row in rows)
    else:
        assert list(tmp_path.iterdir()) == []


def test_http_mixed_batch_dispatches_sa_hc_and_ga(
    single_truck_problem: Problem,
) -> None:
    status, body = _asgi_post(
        "/api/experiments/batch",
        {
            "problem": single_truck_problem.model_dump(mode="json"),
            "persist": False,
            "runs": [
                {
                    "label": "SA",
                    "algorithm": "simulated_annealing",
                    "seed": 42,
                    "parameters": {"max_iterations": 2},
                },
                {
                    "label": "HC",
                    "algorithm": "hill_climbing",
                    "seed": 42,
                    "parameters": {"max_iterations": 2},
                },
                {
                    "label": "GA",
                    "algorithm": "genetic_algorithm",
                    "seed": 42,
                    "parameters": {"population_size": 2, "generations": 1},
                },
            ],
        },
    )
    assert status == 200
    assert [r["algorithm"] for r in body["results"]] == [
        "simulated_annealing",
        "hill_climbing",
        "genetic_algorithm",
    ]
    assert body["summary"]["run_count"] == 3
