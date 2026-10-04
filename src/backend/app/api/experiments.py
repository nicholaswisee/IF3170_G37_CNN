from fastapi import APIRouter

from app.domain.state import State
from app.domain.truck import PackagePlacement
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
    """Return a schema-compatible preview; execution and persistence are pending."""
    initial_state = State(
        placements=[PackagePlacement(package_id=p.id) for p in request.problem.packages]
    )

    return ExperimentResult(
        id="scaffold-demo",
        problem=request.problem,
        algorithm=request.algorithm,
        variant=request.variant if request.algorithm == "hill_climbing" else None,
        objective_mode=request.objective_mode,
        seed=request.seed,
        parameters=request.parameters.model_dump(mode="json"),
        initial_state=initial_state,
        final_state=initial_state.model_copy(deep=True),
        best_state=initial_state.model_copy(deep=True),
        initial_score=0.0,
        final_score=0.0,
        best_score=0.0,
        runtime_ms=0,
        iterations=0,
        history=[],
        metadata={
            "placeholder": True,
            "persisted": False,
            "message": "Algorithm execution and persistence are not implemented.",
        },
    )
