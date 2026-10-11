import csv
import io
import json
import os
import tempfile
from pathlib import Path
from typing import IO

from app.schemas.experiment import BatchExperimentResult, ExperimentResult


def _write_persistence_temp(file: IO[str], payload: str) -> None:
    file.write(payload)
    file.flush()


def record_result(result: ExperimentResult, destination: Path) -> None:
    _publish(destination, result.model_dump_json())


def record_batch(batch: BatchExperimentResult, directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    csv_path = directory / f"{batch.id}.csv"
    json_path = directory / f"{batch.id}.json"
    csv_written = False
    published = False
    try:
        _publish(csv_path, _csv_payload(batch))
        csv_written = True
        # Publish JSON last so its presence means both batch artifacts are complete.
        _publish(json_path, batch.model_dump_json())
        published = True
    finally:
        if not published and csv_written:
            csv_path.unlink(missing_ok=True)


def _csv_payload(batch: BatchExperimentResult) -> str:
    output = io.StringIO(newline="")
    writer = csv.DictWriter(
        output,
        fieldnames=[
            "label",
            "id",
            "algorithm",
            "variant",
            "objective_mode",
            "seed",
            "runtime_ms",
            "initial_score",
            "final_score",
            "best_score",
            "parameters",
        ],
    )
    writer.writeheader()
    for spec, result in zip(batch.requested_runs, batch.results, strict=True):
        writer.writerow(
            {
                "label": _csv_safe_label(spec.label),
                "id": result.id,
                "algorithm": result.algorithm,
                "variant": result.variant.value if result.variant else "",
                "objective_mode": result.objective_mode.value,
                "seed": result.seed,
                "runtime_ms": result.runtime_ms,
                "initial_score": result.initial_score,
                "final_score": result.final_score,
                "best_score": result.best_score,
                "parameters": json.dumps(result.parameters, sort_keys=True),
            }
        )
    return output.getvalue()


def _csv_safe_label(label: str) -> str:
    if label.startswith(("\t", "\r", "\n")) or label.lstrip().startswith(
        ("=", "+", "-", "@")
    ):
        return "'" + label
    return label


def _publish(destination: Path, payload: str) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=destination.parent,
            prefix=".experiment-",
            suffix=".tmp",
            delete=False,
        ) as output:
            temporary_path = Path(output.name)
            _write_persistence_temp(output.file, payload)
        os.link(temporary_path, destination)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
