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
    directory = Path(settings.output_dir) / "experiments"
    try:
        files = sorted(directory.iterdir())
    except FileNotFoundError:
        files = []
    return ExperimentListResponse(
        experiments=[
            ExperimentResult.model_validate_json(path.read_text(encoding="utf-8"))
            for path in files
            if path.suffix == ".json"
        ]
    )


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
