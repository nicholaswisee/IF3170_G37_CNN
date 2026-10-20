from pathlib import Path

from fastapi import APIRouter, HTTPException

from app.config import settings
from app.experiments.batch import BatchConfigurationError
from app.experiments.batch import run_batch as execute_batch
from app.experiments.presets import ga_mandatory_presets
from app.experiments.runner import (
    ExecutionBudgetError,
    UnsupportedAlgorithmError,
)
from app.experiments.runner import run_experiment as execute_experiment
from app.optimization.objective import ObjectiveRangeError
from app.schemas.experiment import (
    BatchExperimentRequest,
    BatchExperimentResult,
    ExperimentListResponse,
    ExperimentResult,
    RunExperimentRequest,
)

router = APIRouter(prefix="/api/experiments", tags=["experiments"])


@router.get("", response_model=ExperimentListResponse)
def list_experiments() -> ExperimentListResponse:
    root = Path(settings.output_dir)
    files = []
    for directory in (root, root / "experiments"):
        try:
            files.extend(sorted(directory.iterdir()))
        except FileNotFoundError:
            continue
    experiments = []
    seen_ids = set()
    for path in files:
        if path.suffix != ".json" or path.name.endswith(".batch.json"):
            continue
        result = ExperimentResult.model_validate_json(path.read_text(encoding="utf-8"))
        if result.id not in seen_ids:
            seen_ids.add(result.id)
            experiments.append(result)
    return ExperimentListResponse(experiments=experiments)


@router.post("/run", response_model=ExperimentResult)
def run_experiment(request: RunExperimentRequest) -> ExperimentResult:
    try:
        return execute_experiment(request)
    except UnsupportedAlgorithmError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except ExecutionBudgetError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except ObjectiveRangeError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@router.get("/presets/genetic_algorithm")
def list_ga_presets() -> dict:
    return {
        "presets": [
            {
                "label": preset.label,
                "seed": preset.seed,
                "parameters": preset.parameters.model_dump(mode="json"),
            }
            for preset in ga_mandatory_presets()
        ]
    }


@router.post("/batch", response_model=BatchExperimentResult)
def run_batch(request: BatchExperimentRequest) -> BatchExperimentResult:
    try:
        return execute_batch(request)
    except (
        BatchConfigurationError,
        UnsupportedAlgorithmError,
        ExecutionBudgetError,
        ObjectiveRangeError,
    ) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
