from fastapi import APIRouter

from app.domain.state import State
from app.schemas.experiment import (
    ExperimentListResponse,
    ExperimentResult,
    RunExperimentRequest,
)

router = APIRouter(prefix="/api/experiments", tags=["experiments"])


@router.get("", response_model=ExperimentListResponse)
def list_experiments() -> ExperimentListResponse:
    return ExperimentListResponse()


@router.post("/run", response_model=ExperimentResult)
def run_experiment(request: RunExperimentRequest) -> ExperimentResult:
    initial_state = State(placements=[], objective_value=100.0, total_weight=0.0)
    final_state = State(placements=[], objective_value=120.0, total_weight=0.0)

    return ExperimentResult(
        id="scaffold-demo",
        algorithm=request.algorithm,
        seed=request.seed,
        initial_state=initial_state,
        final_state=final_state,
        initial_score=100.0,
        final_score=120.0,
        runtime_ms=1,
        iterations=0,
        history=[],
    )
