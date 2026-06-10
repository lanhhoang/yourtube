"""Application configuration loaded from environment variables and .env files."""

from __future__ import annotations

from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration for the YourTube web app.

    Values are loaded from environment variables prefixed with ``YT_`` and may
    be overridden by a local ``.env`` file. The singleton ``settings`` below
    is imported by services, the FastAPI app, and tests.
    """

    model_config = SettingsConfigDict(
        env_prefix="YT_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    host: str = "127.0.0.1"
    port: int = 8000
    data_dir: Path = Path("./tmp/data")
    downloads_dir: Path = Path("./tmp/downloads")
    cookies_path: Path | None = None
    proxy_url: str | None = None
    log_level: str = "INFO"
    workers: int = 1
    database_url: str | None = None

    @model_validator(mode="after")
    def default_database_url(self) -> "Settings":
        if self.database_url is None:
            self.database_url = f"sqlite:///{self.data_dir / 'yourtube.db'}"
        return self


settings = Settings()
