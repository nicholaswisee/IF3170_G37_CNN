from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from app.domain.truck import Position


class MoveType(StrEnum):
    SWAP = "SWAP"
    RELOCATE = "RELOCATE"
    ROTATE = "ROTATE"


class Move(BaseModel):
    type: MoveType
    package_ids: list[str]
    source: Position | None = None
    destination: Position | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
