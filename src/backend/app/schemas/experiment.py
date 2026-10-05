"""Frozen public experiment contracts shared with the algorithm and UI layers."""

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.domain.move import Move
from app.domain.problem import Problem
from app.domain.state import State
from app.optimization.objective import ObjectiveMode
from app.schemas.common import Metadata

type AlgorithmName = Literal[
    "hill_climbing",
    "simulated_annealing",
    "genetic_algorithm",
]


class HillClimbingVariant(StrEnum):
    STEEPEST_ASCENT = "steepest_ascent"
    STOCHASTIC = "stochastic"
    SIDEWAYS = "sideways"
    RANDOM_RESTART = "random_restart"


class _Parameters(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class HillClimbingParameters(_Parameters):
    max_iterations: int = Field(default=2000, gt=0)
    candidates_per_iteration: int = Field(default=50, gt=0)
    max_sideways: int = Field(default=100, ge=0)
    max_restarts: int = Field(default=10, ge=0)


class SimulatedAnnealingParameters(_Parameters):
    initial_temperature: float | None = Field(default=None, gt=0)
    alpha: float = Field(default=0.995, gt=0, lt=1)
    min_temperature: float = Field(default=0.001, gt=0)
    max_iterations: int = Field(default=5000, gt=0)
    stuck_patience: int = Field(default=50, gt=0)


class GeneticAlgorithmParameters(_Parameters):
    population_size: int = Field(default=50, ge=2)
    generations: int = Field(default=100, ge=1)
    crossover_probability: float = Field(default=0.80, ge=0, le=1)
    mutation_probability: float = Field(default=0.20, ge=0, le=1)
    # Freeze sections 36 and 41 fix elitism at one; population_size is at least two.
    elite_count: int = Field(default=1, ge=1, le=1)


class _RunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    problem: Problem
    objective_mode: ObjectiveMode = ObjectiveMode.TOTAL_VALUE
    seed: int
    include_state_history: bool = True
    persist: bool = True


class HillClimbingRequest(_RunRequest):
    algorithm: Literal["hill_climbing"]
    variant: HillClimbingVariant = HillClimbingVariant.SIDEWAYS
    parameters: HillClimbingParameters = Field(default_factory=HillClimbingParameters)


class SimulatedAnnealingRequest(_RunRequest):
    algorithm: Literal["simulated_annealing"]
    parameters: SimulatedAnnealingParameters = Field(
        default_factory=SimulatedAnnealingParameters
    )


class GeneticAlgorithmRequest(_RunRequest):
    algorithm: Literal["genetic_algorithm"]
    parameters: GeneticAlgorithmParameters = Field(
        default_factory=GeneticAlgorithmParameters
    )


# Parse this union outside FastAPI with TypeAdapter(RunExperimentRequest).
type RunExperimentRequest = Annotated[
    HillClimbingRequest | SimulatedAnnealingRequest | GeneticAlgorithmRequest,
    Field(discriminator="algorithm"),
]


class SearchEvent(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)

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
    model_config = ConfigDict(allow_inf_nan=False)

    id: str
    problem: Problem
    algorithm: AlgorithmName
    variant: HillClimbingVariant | None
    objective_mode: ObjectiveMode
    seed: int
    parameters: Metadata
    initial_state: State
    final_state: State
    best_state: State
    initial_score: float
    final_score: float
    best_score: float
    runtime_ms: int
    iterations: int
    history: list[SearchEvent]
    metadata: Metadata = Field(default_factory=dict)


class ExperimentListResponse(BaseModel):
    experiments: list[ExperimentResult] = Field(default_factory=list)
