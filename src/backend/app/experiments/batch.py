import json
from pathlib import Path
from uuid import uuid4

from pydantic import TypeAdapter

from app.config import settings
from app.experiments.metrics import summarize_results
from app.experiments.presets import ga_mandatory_presets
from app.experiments.recorder import record_batch
from app.experiments.runner import (
    preflight_experiment,
    run_experiment,
)
from app.optimization.objective import ObjectiveMode
from app.schemas.experiment import (
    BatchExperimentRequest,
    BatchExperimentResult,
    BatchGroupResult,
    BatchRunSpec,
    ExperimentResult,
    HillClimbingRequest,
    RunExperimentRequest,
)

RUN_REQUEST_ADAPTER: TypeAdapter[RunExperimentRequest] = TypeAdapter(
    RunExperimentRequest.__value__
)


class BatchConfigurationError(ValueError):
    pass


def run_batch(request: BatchExperimentRequest) -> BatchExperimentResult:
    specs = request.runs
    if request.preset == "ga_mandatory":
        specs = [
            BatchRunSpec(
                label=preset.label,
                seed=preset.seed,
                parameters=preset.parameters.model_dump(mode="json"),
            )
            for preset in ga_mandatory_presets()
        ]
    assert specs is not None

    parsed: list[RunExperimentRequest] = []
    requested: list[BatchRunSpec] = []
    for spec in specs:
        raw: dict[str, object] = {
            "algorithm": spec.algorithm,
            "problem": request.problem,
            "objective_mode": spec.objective_mode or request.objective_mode,
            "seed": spec.seed,
            "parameters": spec.parameters,
            "persist": request.persist,
            "include_state_history": False,
        }
        if spec.variant is not None:
            raw["variant"] = spec.variant
        try:
            run = RUN_REQUEST_ADAPTER.validate_python(raw)
        except ValueError as error:
            raise BatchConfigurationError(str(error)) from error
        preflight_experiment(run)
        parsed.append(run)
        requested.append(
            BatchRunSpec(
                label=spec.label,
                algorithm=run.algorithm,
                variant=run.variant if isinstance(run, HillClimbingRequest) else None,
                seed=run.seed,
                objective_mode=run.objective_mode,
                parameters=run.parameters.model_dump(mode="json"),
            )
        )

    results: list[ExperimentResult] = []
    created_ids: list[str] = []
    try:
        for run in parsed:
            result = run_experiment(run)
            results.append(result)
            if request.persist:
                created_ids.append(result.id)
        groups = _group_results(requested, results)
        batch = BatchExperimentResult(
            id=str(uuid4()),
            requested_runs=requested,
            results=results,
            summary=summarize_results(results),
            groups=groups,
            persisted=request.persist,
        )
        if request.persist:
            record_batch(batch, Path(settings.output_dir) / "batches")
        return batch
    except Exception:
        for result_id in created_ids:
            (Path(settings.output_dir) / "experiments" / f"{result_id}.json").unlink(
                missing_ok=True
            )
        raise


def _group_results(
    specs: list[BatchRunSpec], results: list[ExperimentResult]
) -> list[BatchGroupResult]:
    groups: dict[str, tuple[BatchRunSpec, list[ExperimentResult]]] = {}
    for spec, result in zip(specs, results, strict=True):
        key = json.dumps(
            [
                spec.label,
                spec.algorithm,
                spec.variant,
                spec.objective_mode,
                spec.parameters,
            ],
            sort_keys=True,
            default=str,
        )
        groups.setdefault(key, (spec, []))[1].append(result)
    return [
        BatchGroupResult(
            label=spec.label,
            algorithm=spec.algorithm,
            variant=spec.variant,
            objective_mode=spec.objective_mode or ObjectiveMode.TOTAL_VALUE,
            parameters=spec.parameters,
            summary=summarize_results(results),
        )
        for spec, results in groups.values()
    ]
