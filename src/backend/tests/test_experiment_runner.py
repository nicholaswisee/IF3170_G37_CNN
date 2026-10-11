def test_summary_empty_and_extreme_finite_values() -> None:
    from app.experiments.metrics import summarize_results

    assert summarize_results([]) == {
        "run_count": 0,
        "mean_best_score": None,
        "std_best_score": None,
        "min_best_score": None,
        "max_best_score": None,
        "mean_runtime_ms": None,
        "min_runtime_ms": None,
        "max_runtime_ms": None,
    }
    maximum = float.fromhex("0x1.fffffffffffffp+1023")
    assert (
        maximum
        == summarize_results([_minimal_result(maximum), _minimal_result(maximum)])[
            "mean_best_score"
        ]
    )
    assert (
        summarize_results([_minimal_result(maximum), _minimal_result(-maximum)])[
            "std_best_score"
        ]
        == maximum
    )
    assert (
        summarize_results([_minimal_result(1), _minimal_result(3)])["std_best_score"]
        == 1
    )


def _minimal_result(score: float):
    from app.domain import Problem, State
    from app.schemas.experiment import ExperimentResult

    return ExperimentResult(
        id="summary",
        problem=Problem(
            packages=[],
            trucks=[
                {"id": "t", "width": 1, "length": 1, "height": 1, "max_capacity": 1}
            ],
        ),
        algorithm="genetic_algorithm",
        variant=None,
        objective_mode="total_value",
        seed=1,
        parameters={},
        initial_state=State(placements=[]),
        final_state=State(placements=[]),
        best_state=State(placements=[]),
        initial_score=score,
        final_score=score,
        best_score=score,
        runtime_ms=3,
        iterations=1,
        history=[],
    )
