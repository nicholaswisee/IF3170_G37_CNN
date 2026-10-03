from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from app.domain.truck import PackagePlacement


class MoveType(StrEnum):
    SWAP = "SWAP"
    RELOCATE = "RELOCATE"
    ROTATE = "ROTATE"


class Move(BaseModel):
    """One neighbor transition with complete placements before and after.

    before[i] and after[i] describe package_ids[i], so truck assignment,
    position, and orientation changes are all recorded.
    """

    type: MoveType
    package_ids: list[str]
    before: list[PackagePlacement]
    after: list[PackagePlacement]
    metadata: dict[str, Any] = Field(default_factory=dict)
