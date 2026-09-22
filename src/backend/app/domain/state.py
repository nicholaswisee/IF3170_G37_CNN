from pydantic import BaseModel

from app.domain.truck import PackagePlacement


class State(BaseModel):
    placements: list[PackagePlacement]
    objective_value: float
    total_weight: float
