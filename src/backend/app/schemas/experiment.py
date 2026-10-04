from typing import Literal

from pydantic import BaseModel, Field

from app.domain.move import Move
from app.domain.state import State
from app.schemas.common import Metadata

type AlgorithmName = Literal[
    "hill_climbing",
    "simulated_annealing",
    "genetic_algorithm",
]


class RunExperimentRequest(BaseModel):
    algorithm: AlgorithmName
    seed: int
    parameters: Metadata


class SearchEvent(BaseModel):
    iteration: int
    current_score: float
    best_score: float
    candidate_score: float | None = None
    mean_score: float | None = None
    accepted: bool | None = None
    move: Move | None = None
    temperature: float | None = None
    acceptance_probability: float | None = None
    state_snapshot: State | None = None
    metadata: Metadata = Field(default_factory=dict)


class ExperimentResult(BaseModel):
    id: str
    algorithm: AlgorithmName
    seed: int
    initial_state: State
    final_state: State
    initial_score: float
    final_score: float
    runtime_ms: int
    iterations: int
    history: list[SearchEvent]
    metadata: Metadata = Field(default_factory=dict)


class ExperimentListResponse(BaseModel):
    experiments: list[ExperimentResult] = Field(default_factory=list)
