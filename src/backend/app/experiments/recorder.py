"""Placeholder boundary for future search-event recording."""

from app.schemas.experiment import SearchEvent


def record_event(event: SearchEvent) -> None:
    # TODO: Store events and serialize experiment history in a later milestone.
    raise NotImplementedError("Experiment recorder not implemented yet.")
