from pathlib import Path

import app.config as config_module
from app.config import Settings


def test_default_directories_are_repository_relative_from_any_working_directory(
    monkeypatch, tmp_path
):
    monkeypatch.delenv("OUTPUT_DIR", raising=False)
    monkeypatch.delenv("DATA_DIR", raising=False)
    monkeypatch.delenv("TEST_DIR", raising=False)
    monkeypatch.chdir(tmp_path)

    settings = Settings(_env_file=None)
    repository_root = Path(__file__).resolve().parents[3]

    assert settings.output_dir == str(repository_root / "output")
    assert settings.data_dir == str(repository_root / "data")
    assert settings.test_dir == str(repository_root / "test")


def test_directory_environment_overrides_are_preserved(monkeypatch):
    monkeypatch.setenv("OUTPUT_DIR", "/workspace/output")
    monkeypatch.setenv("DATA_DIR", "/workspace/data")
    monkeypatch.setenv("TEST_DIR", "/workspace/test")

    settings = Settings(_env_file=None)

    assert settings.output_dir == "/workspace/output"
    assert settings.data_dir == "/workspace/data"
    assert settings.test_dir == "/workspace/test"


def test_module_loads_with_docker_paths_from_shallow_container_location(monkeypatch):
    monkeypatch.setenv("OUTPUT_DIR", "/workspace/output")
    monkeypatch.setenv("DATA_DIR", "/workspace/data")
    monkeypatch.setenv("TEST_DIR", "/workspace/test")
    module_path = "/app/app/config.py"
    namespace = {"__file__": module_path, "__name__": "config_regression"}

    exec(  # noqa: S102 - evaluate module with the simulated container __file__
        compile(Path(config_module.__file__).read_text(), module_path, "exec"),
        namespace,
    )

    assert namespace["settings"].output_dir == "/workspace/output"
    assert namespace["settings"].data_dir == "/workspace/data"
    assert namespace["settings"].test_dir == "/workspace/test"
