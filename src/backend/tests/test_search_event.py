from app.schemas.experiment import SearchEvent


def test_algorithm_neutral_history_preserves_metrics() -> None:
    event = SearchEvent(
        iteration=1,
        current_score=5,
        best_score=10,
        candidate_score=4,
        mean_score=3,
        accepted=False,
        temperature=2,
        acceptance_probability=0.5,
        metadata={"stuck_events": 1},
    )
    assert SearchEvent.model_validate_json(event.model_dump_json()) == event
    assert event.model_dump()["best_score"] == 10
    assert event.model_dump()["mean_score"] == 3
    assert event.model_dump()["temperature"] == 2
    assert event.model_dump()["acceptance_probability"] == 0.5
