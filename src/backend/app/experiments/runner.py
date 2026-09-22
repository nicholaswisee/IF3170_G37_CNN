"""Placeholder boundary for future experiment orchestration."""

from app.schemas.experiment import ExperimentResult, RunExperimentRequest


def run_experiment(request: RunExperimentRequest) -> ExperimentResult:
    # TODO: Select and execute an algorithm in a later implementation phase.
    raise NotImplementedError("Experiment runner not implemented yet.")
