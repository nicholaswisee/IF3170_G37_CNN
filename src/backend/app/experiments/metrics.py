import statistics

from app.schemas.common import Metadata
from app.schemas.experiment import ExperimentResult


def calculate_metrics(result: ExperimentResult) -> Metadata:
    return {
        "max_fitness_history": [event.current_score for event in result.history],
        "avg_fitness_history": [event.mean_score for event in result.history],
        "population_size": result.parameters.get("population_size"),
        "generations": result.parameters.get("generations"),
        "duration_ms": result.runtime_ms,
        "seed": result.seed,
        "objective_mode": result.objective_mode.value,
    }


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
