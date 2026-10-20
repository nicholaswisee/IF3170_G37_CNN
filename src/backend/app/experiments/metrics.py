import statistics
from decimal import Decimal
from math import fsum, isfinite

from app.schemas.common import Metadata
from app.schemas.experiment import ExperimentResult


def _report_sum(values: list[float]) -> float | str:
    try:
        return fsum(values)
    except OverflowError:
        return str(sum((Decimal.from_float(value) for value in values), Decimal()))


def calculate_metrics(result: ExperimentResult) -> Metadata:
    max_fitness_history = []
    for event in result.history:
        max_fitness = event.metadata.get("max_fitness")
        max_fitness_history.append(
            max_fitness
            if isinstance(max_fitness, (int, float))
            and not isinstance(max_fitness, bool)
            and isfinite(max_fitness)
            else event.current_score
        )
    metrics: Metadata = {
        "max_fitness_history": max_fitness_history,
        "avg_fitness_history": [event.mean_score for event in result.history],
        "population_size": result.parameters.get("population_size"),
        "generations": result.parameters.get("generations"),
        "duration_ms": result.runtime_ms,
        "seed": result.seed,
        "objective_mode": result.objective_mode.value,
        "initial_score": result.initial_score,
        "final_score": result.final_score,
        "best_score": result.best_score,
        "runtime_ms": result.runtime_ms,
        "iterations": result.iterations,
        "loaded_count": sum(
            placement.truck_id is not None
            for placement in result.final_state.placements
        ),
        "total_weight": _report_sum(
            [
                package.weight
                for package in result.problem.packages
                if any(
                    placement.package_id == package.id
                    and placement.truck_id is not None
                    for placement in result.final_state.placements
                )
            ]
        ),
        "state_summaries": {},
    }
    if "termination_reason" in result.metadata:
        metrics["termination_reason"] = result.metadata["termination_reason"]
    for key in ("sideways_moves", "restarts_performed", "stuck_events"):
        if key in result.metadata:
            metrics[key] = result.metadata[key]

    for name, state in (
        ("initial", result.initial_state),
        ("final", result.final_state),
        ("best", result.best_state),
    ):
        trucks = {}
        for truck in result.problem.trucks:
            package_ids = [
                placement.package_id
                for placement in state.placements
                if placement.truck_id == truck.id
            ]
            loaded = [
                package
                for package in result.problem.packages
                if package.id in package_ids
            ]
            trucks[truck.id] = {
                "package_ids": package_ids,
                "count": len(package_ids),
                "loaded_weight": _report_sum([package.weight for package in loaded]),
                "loaded_value": _report_sum([package.value for package in loaded]),
                "max_capacity": truck.max_capacity,
            }
        outside = [
            placement.package_id
            for placement in state.placements
            if placement.truck_id is None
        ]
        metrics["state_summaries"][name] = {
            "trucks": trucks,
            "outside_package_ids": outside,
            "outside_count": len(outside),
        }
    return metrics


def summarize_results(results: list[ExperimentResult]) -> dict[str, int | float | None]:
    scores = [result.best_score for result in results]
    runtimes = [result.runtime_ms for result in results]
    if not scores:
        return {
            "run_count": 0,
            "mean_best_score": None,
            "std_best_score": None,
            "min_best_score": None,
            "max_best_score": None,
            "mean_runtime_ms": None,
            "min_runtime_ms": None,
            "max_runtime_ms": None,
        }
    mean_score = statistics.mean(scores)
    std_score = statistics.pstdev(scores)
    return {
        "run_count": len(results),
        "mean_best_score": mean_score,
        "std_best_score": std_score,
        "min_best_score": min(scores),
        "max_best_score": max(scores),
        "mean_runtime_ms": statistics.mean(runtimes),
        "min_runtime_ms": min(runtimes),
        "max_runtime_ms": max(runtimes),
    }
