"""Placeholder boundary for future experiment metrics."""

from app.schemas.common import Metadata
from app.schemas.experiment import ExperimentResult


def calculate_metrics(result: ExperimentResult) -> Metadata:
    # TODO: Calculate summary statistics after experiments can execute.
    raise NotImplementedError("Experiment metrics not implemented yet.")
