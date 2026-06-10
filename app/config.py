"""Application configuration loaded from environment variables and .env files."""

from __future__ import annotations

from pathlib import Path
from typing import Any

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
    database_url: str = ""

    @model_validator(mode="before")
    @classmethod
    def default_database_url(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data

        if data.get("database_url"):
            return data

        raw_data_dir = data.get("data_dir", "./tmp/data")
        data_dir = raw_data_dir if isinstance(raw_data_dir, Path) else Path(raw_data_dir)
        data["database_url"] = f"sqlite:///{data_dir / 'yourtube.db'}"
        return data


settings = Settings()
