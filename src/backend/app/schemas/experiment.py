"""Frozen public experiment contracts shared with the algorithm and UI layers."""

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app import limits
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
    crossover_probability: float = Field(default=1.0, ge=0, le=1)
    mutation_probability: float = Field(default=0.20, ge=0, le=1)
    elite_count: int = Field(default=0, ge=0, le=0)


class _RunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    problem: Problem
    objective_mode: ObjectiveMode = ObjectiveMode.TOTAL_VALUE
    seed: int
    include_state_history: bool = True
    persist: bool = True

    @field_validator("seed")
    @classmethod
    def seed_is_safe_integer(cls, value: int) -> int:
        if abs(value) > limits.MAX_SAFE_SEED:
            raise ValueError("seed must be a JavaScript safe integer")
        return value

    @field_validator("problem", mode="before")
    @classmethod
    def problem_within_request_limits(cls, value):
        return validate_problem_input(value)


def validate_problem_input(value):
    if isinstance(value, dict):
        packages = value.get("packages")
        trucks = value.get("trucks")
        if (isinstance(packages, list) and len(packages) > limits.MAX_PACKAGES) or (
            isinstance(trucks, list) and len(trucks) > limits.MAX_TRUCKS
        ):
            raise ValueError(
                f"at most {limits.MAX_PACKAGES} packages and "
                f"{limits.MAX_TRUCKS} trucks are allowed"
            )
        for collection in (packages, trucks):
            if isinstance(collection, list) and any(
                isinstance(item, dict)
                and isinstance(item.get("id"), str)
                and len(item["id"]) > limits.MAX_ID_LENGTH
                for item in collection
            ):
                raise ValueError(
                    f"IDs must be at most {limits.MAX_ID_LENGTH} characters"
                )
    return value


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


class BatchRunSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str = Field(min_length=1, max_length=128)
    algorithm: AlgorithmName = "genetic_algorithm"
    variant: HillClimbingVariant | None = None
    seed: int
    objective_mode: ObjectiveMode | None = None
    parameters: Metadata = Field(default_factory=dict)


class BatchExperimentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    problem: Problem
    runs: list[BatchRunSpec] | None = Field(default=None, min_length=1, max_length=100)
    preset: Literal["ga_mandatory"] | None = None
    objective_mode: ObjectiveMode = ObjectiveMode.TOTAL_VALUE
    persist: bool = True

    @field_validator("problem", mode="before")
    @classmethod
    def problem_within_batch_limits(cls, value):
        return validate_problem_input(value)

    @model_validator(mode="after")
    def batch_selection_is_exclusive(self):
        if (self.runs is None) == (self.preset is None):
            raise ValueError("provide either runs or preset, not both")
        if (
            self.preset == "ga_mandatory"
            and self.objective_mode != ObjectiveMode.TOTAL_VALUE
        ):
            raise ValueError("ga_mandatory preset requires objective_mode total_value")
        return self


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


class BatchGroupResult(BaseModel):
    label: str
    algorithm: AlgorithmName
    variant: HillClimbingVariant | None
    objective_mode: ObjectiveMode
    parameters: Metadata
    summary: Metadata


class BatchExperimentResult(BaseModel):
    id: str
    requested_runs: list[BatchRunSpec]
    results: list[ExperimentResult]
    summary: Metadata
    groups: list[BatchGroupResult]
    persisted: bool
