"""ASGI app for Playwright: the real app with yt-dlp calls stubbed out.

Sets nothing in the environment itself; Playwright's ``webServer.env`` does.
Later phases fill in the stubs and seed data.
"""

from __future__ import annotations

from typing import Any

from app.services import downloader, job_runner


def _not_stubbed(*_args: Any, **_kwargs: Any) -> Any:
    raise RuntimeError("not stubbed")


downloader.extract_info = _not_stubbed
downloader.extract_flat_info = _not_stubbed
job_runner.run_download = _not_stubbed

from app.main import app  # noqa: E402

__all__ = ["app"]
