"""API configuration, read from environment variables."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(case_sensitive=False)

    model_uri: str = "file:///app/artifacts/local"
    port: int = 8080
    log_level: str = "INFO"


settings = Settings()
