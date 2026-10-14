from fastapi import APIRouter

from app.domain.problem import Problem
from app.schemas.problem import ProblemValidationResponse

router = APIRouter(prefix="/api/problems", tags=["problems"])


@router.post("/validate", response_model=ProblemValidationResponse)
def validate_problem(problem: Problem) -> ProblemValidationResponse:
    return ProblemValidationResponse(valid=True)
