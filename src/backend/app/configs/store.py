"""One JSON file per configuration.

Uploads live in DATA_DIR/configs and can be deleted. Built-ins ship beside this
module in the upload file format, so they survive hosts with ephemeral disks.
"""

import re
from datetime import UTC, datetime
from functools import cache
from pathlib import Path
from uuid import uuid4

from pydantic import ValidationError

from app.config import settings
from app.experiments.recorder import record_config
from app.schemas.config import ConfigUpload, SavedConfig

BUILTIN_DIRECTORY = Path(__file__).parent / "builtin"
BUILTIN_PREFIX = "builtin-"
TEST_PREFIX = "test-"
# Uploaded IDs are generated here, so anything else never reaches the filesystem.
UPLOADED_ID = re.compile(r"[0-9a-f]{32}")


class ConfigNotFoundError(LookupError):
    pass


class DuplicateConfigNameError(ValueError):
    pass


class BuiltinConfigError(ValueError):
    pass


def _uploaded_directory() -> Path:
    return Path(settings.data_dir) / "configs"


def _test_configs() -> tuple[SavedConfig, ...]:
    configs = []
    for path in sorted(Path(settings.test_dir).glob("*.json")):
        if not re.fullmatch(r"[A-Za-z0-9_-]+", path.stem):
            continue
        try:
            upload = ConfigUpload.model_validate_json(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, ValidationError):
            continue
        configs.append(
            SavedConfig(
                id=TEST_PREFIX + path.stem,
                name=upload.name,
                description=upload.description,
                builtin=True,
                created_at=None,
                problem=upload.problem,
            )
        )
    return tuple(configs)


@cache
def builtin_configs() -> tuple[SavedConfig, ...]:
    configs = []
    for path in sorted(BUILTIN_DIRECTORY.glob("*.json")):
        upload = ConfigUpload.model_validate_json(path.read_text(encoding="utf-8"))
        configs.append(
            SavedConfig(
                id=BUILTIN_PREFIX + path.stem,
                name=upload.name,
                description=upload.description,
                builtin=True,
                created_at=None,
                problem=upload.problem,
            )
        )
    return tuple(configs)


def _read_uploaded(path: Path) -> SavedConfig | None:
    try:
        config = SavedConfig.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValidationError):
        return None
    return config.model_copy(update={"id": path.stem, "builtin": False})


def list_configs() -> list[SavedConfig]:
    """Built-ins first, then uploads newest first. Unreadable files are skipped."""
    uploaded = [
        config
        for path in _uploaded_directory().glob("*.json")
        if UPLOADED_ID.fullmatch(path.stem) and (config := _read_uploaded(path))
    ]
    uploaded.sort(
        key=lambda config: config.created_at or datetime.min.replace(tzinfo=UTC),
        reverse=True,
    )
    local = _test_configs() if Path(settings.test_dir).is_dir() else ()
    return [*builtin_configs(), *local, *uploaded]


def get_config(config_id: str) -> SavedConfig:
    if config_id.startswith(BUILTIN_PREFIX):
        for builtin in builtin_configs():
            if builtin.id == config_id:
                return builtin
    elif config_id.startswith(TEST_PREFIX):
        for config in _test_configs():
            if config.id == config_id:
                return config
    elif UPLOADED_ID.fullmatch(config_id):
        uploaded = _read_uploaded(_uploaded_directory() / f"{config_id}.json")
        if uploaded is not None:
            return uploaded
    raise ConfigNotFoundError(f"Configuration {config_id} was not found.")


def save_config(upload: ConfigUpload) -> SavedConfig:
    name = upload.name.casefold()
    if any(config.name.casefold() == name for config in list_configs()):
        raise DuplicateConfigNameError(
            f"A configuration named {upload.name} already exists."
        )
    config = SavedConfig(
        id=uuid4().hex,
        name=upload.name,
        description=upload.description,
        builtin=False,
        created_at=datetime.now(UTC),
        problem=upload.problem,
    )
    record_config(config, _uploaded_directory() / f"{config.id}.json")
    return config


def delete_config(config_id: str) -> None:
    if any(config.id == config_id for config in [*builtin_configs(), *_test_configs()]):
        raise BuiltinConfigError("Built-in configurations cannot be deleted.")
    if UPLOADED_ID.fullmatch(config_id):
        try:
            (_uploaded_directory() / f"{config_id}.json").unlink()
            return
        except FileNotFoundError:
            pass
    raise ConfigNotFoundError(f"Configuration {config_id} was not found.")
