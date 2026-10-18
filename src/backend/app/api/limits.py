from typing import Any, get_args

from annotated_types import Ge, Gt, Le, Lt
from fastapi import APIRouter
from pydantic import BaseModel

from app import limits
from app.schemas.experiment import (
    GeneticAlgorithmParameters,
    HillClimbingParameters,
    SimulatedAnnealingParameters,
)
from app.schemas.limits import LimitsResponse, NumericRange, ProblemLimits

router = APIRouter(prefix="/api", tags=["limits"])

PARAMETER_MODELS: dict[str, type[BaseModel]] = {
    "hill_climbing": HillClimbingParameters,
    "simulated_annealing": SimulatedAnnealingParameters,
    "genetic_algorithm": GeneticAlgorithmParameters,
}


def describe_parameters(
    model: type[BaseModel], budgets: dict[str, int]
) -> dict[str, NumericRange]:
    """Read schema bounds from the model and tighten them with runner budgets."""
    ranges: dict[str, NumericRange] = {}
    for name, field in model.model_fields.items():
        bounds: dict[str, Any] = {}
        for constraint in field.metadata:
            if isinstance(constraint, Ge):
                bounds["minimum"] = constraint.ge
            elif isinstance(constraint, Gt):
                bounds["exclusive_minimum"] = constraint.gt
            elif isinstance(constraint, Le):
                bounds["maximum"] = constraint.le
            elif isinstance(constraint, Lt):
                bounds["exclusive_maximum"] = constraint.lt
        if name in budgets:
            bounds["maximum"] = min(bounds.get("maximum", budgets[name]), budgets[name])
        options = get_args(field.annotation) or (field.annotation,)
        ranges[name] = NumericRange(
            integer=int in options,
            nullable=type(None) in options,
            default=field.default,
            **bounds,
        )
    return ranges


@router.get("/limits", response_model=LimitsResponse)
def get_limits() -> LimitsResponse:
    return LimitsResponse(
        problem=ProblemLimits(
            max_packages=limits.MAX_PACKAGES,
            max_trucks=limits.MAX_TRUCKS,
            max_id_length=limits.MAX_ID_LENGTH,
            max_total_truck_volume=limits.MAX_TOTAL_TRUCK_VOLUME,
        ),
        seed=NumericRange(
            integer=True,
            minimum=-limits.MAX_SAFE_SEED,
            maximum=limits.MAX_SAFE_SEED,
            default=42,
        ),
        max_request_bytes=limits.MAX_REQUEST_BYTES,
        parameters={
            algorithm: describe_parameters(model, limits.PARAMETER_BUDGETS[algorithm])
            for algorithm, model in PARAMETER_MODELS.items()
        },
    )
