from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    app_env: str = "development"
    frontend_origin: str = "http://localhost:5173"
    output_dir: str = str(
        (Path(__file__).resolve().parent / "../../../output").resolve()
    )
    data_dir: str = str((Path(__file__).resolve().parent / "../../../data").resolve())


settings = Settings()
