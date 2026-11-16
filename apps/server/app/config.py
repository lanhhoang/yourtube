"""Application configuration loaded from environment variables and .env files."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[3]

_RELATIVE_TO_ROOT = ("data_dir", "downloads_dir", "cookies_path")


def resolve_repo_path(value: str | Path) -> Path:
    """Return ``value`` as a path, joining relative paths onto ``REPO_ROOT``."""
    path = Path(value)
    return path if path.is_absolute() else REPO_ROOT / path


class Settings(BaseSettings):
    """Runtime configuration for the YourTube web app.

    Values are loaded from environment variables prefixed with ``YT_`` and may
    be overridden by a local ``.env`` file. The singleton ``settings`` below
    is imported by services, the FastAPI app, and tests.
    """

    model_config = SettingsConfigDict(
        env_prefix="YT_",
        env_file=REPO_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    host: str = "127.0.0.1"
    port: int = 8000
    data_dir: Path = REPO_ROOT / "tmp/data"
    downloads_dir: Path = REPO_ROOT / "tmp/downloads"
    cookies_path: Path | None = None
    proxy_url: str | None = None
    log_level: str = "INFO"
    workers: int = 1
    web_dist_dir: Path = REPO_ROOT / "apps/web/dist"
    database_url: str = ""
    # When False, the FastAPI lifespan skips starting the worker pool.
    # Tests set this so the lifespan can run without spawning threads
    # that would race with the test's own database assertions.
    workers_enabled: bool = True

    @model_validator(mode="before")
    @classmethod
    def default_database_url(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data

        for key in _RELATIVE_TO_ROOT:
            if data.get(key):
                data[key] = resolve_repo_path(data[key])

        if data.get("database_url"):
            return data

        data_dir = data.get("data_dir", REPO_ROOT / "tmp/data")
        data["database_url"] = f"sqlite:///{data_dir / 'yourtube.db'}"
        return data


settings = Settings()
