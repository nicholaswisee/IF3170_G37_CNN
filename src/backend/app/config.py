from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    app_env: str = "development"
    frontend_origin: str = "http://localhost:5173"
    output_dir: str = "/workspace/output"
    data_dir: str = "/workspace/data"


settings = Settings()
