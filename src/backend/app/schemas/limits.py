from pydantic import BaseModel


class NumericRange(BaseModel):
    """Bounds of one numeric input; unset bounds are open."""

    integer: bool
    nullable: bool = False
    minimum: float | None = None
    exclusive_minimum: float | None = None
    maximum: float | None = None
    exclusive_maximum: float | None = None
    default: float | None = None


class ProblemLimits(BaseModel):
    max_packages: int
    max_trucks: int
    max_id_length: int
    max_total_truck_volume: int


class LimitsResponse(BaseModel):
    problem: ProblemLimits
    seed: NumericRange
    max_request_bytes: int
    parameters: dict[str, dict[str, NumericRange]]
