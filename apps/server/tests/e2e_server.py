"""ASGI app for Playwright: the real app with yt-dlp calls stubbed out.

Sets nothing in the environment itself; Playwright's ``webServer.env`` does.
Seeds two rows after migrations (by wrapping the lifespan) and fakes downloads.
Later phases fill in more stubs.
"""

from __future__ import annotations

import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI

from app.config import settings
from app.db import SessionLocal
from app.models import Download
from app.services import downloader, job_runner
from app.services.downloader import DownloadResult


def _not_stubbed(*_args: Any, **_kwargs: Any) -> Any:
    raise RuntimeError("not stubbed")


def _run_download(
    url: str, *, output_dir: str = "", progress_hook: Any = None, **_kwargs: Any
) -> DownloadResult:
    if "slow" in url:
        for p in range(1, 101):
            if progress_hook is not None:
                progress_hook({"status": "downloading", "_percent_str": f"{p}%"})
            time.sleep(0.2)
    path = Path(output_dir) / f"{url.rstrip('/').rsplit('/', 1)[-1]}.mp4"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"data")
    if progress_hook is not None:
        progress_hook({"status": "finished", "filename": str(path)})
    return DownloadResult(str(path), 4, "mp4", 1080)


_VIDEO_URLS = {"https://e2e.test/video", "https://e2e.test/watch?v=e2e&list=PLe2e"}


def _video_info(url: str) -> dict[str, Any]:
    def fmt(fid: str, w: int | None, h: int | None, v: str, a: str, ext: str) -> dict[str, Any]:
        return {
            "format_id": fid,
            "ext": ext,
            "width": w,
            "height": h,
            "vcodec": v,
            "acodec": a,
            "abr": 128 if v == "none" else None,
        }

    return {
        "id": "e2e",
        "title": "E2E Video",
        "uploader": "E2E",
        "duration": 61,
        "webpage_url": "https://e2e.test/video",
        "formats": [
            fmt("v1080", 1920, 1080, "avc1.640028", "none", "mp4"),
            fmt("v720", 1280, 720, "avc1.64001f", "none", "mp4"),
            fmt("a1", None, None, "none", "mp4a.40.2", "m4a"),
        ],
    }


def _stub_info(url: str, **_kwargs: Any) -> dict[str, Any]:
    if url in _VIDEO_URLS:
        return _video_info(url)
    return _not_stubbed(url)


downloader.extract_info = _stub_info
downloader.extract_flat_info = _stub_info
job_runner.run_download = _run_download

from app.main import app  # noqa: E402


def _seed() -> None:
    downloads = Path(settings.downloads_dir)
    downloads.mkdir(parents=True, exist_ok=True)
    seeded = downloads / "seeded.mp4"
    seeded.write_bytes(b"data")
    with SessionLocal() as session:
        session.add(
            Download(
                url="https://e2e.test/seeded",
                title="Seeded video",
                uploader="E2E",
                status="done",
                progress=100.0,
                file_path=str(seeded),
                file_size=4,
                media_format="mp4",
                resolution_height=1080,
                finished_at=datetime.now(),
            )
        )
        session.add(Download(url="https://e2e.test/slow", title="Slow video", status="queued"))
        session.commit()


_original = app.router.lifespan_context


@asynccontextmanager
async def _lifespan(a: FastAPI) -> AsyncIterator[None]:
    async with _original(a):
        _seed()
        yield


app.router.lifespan_context = _lifespan

__all__ = ["app"]
