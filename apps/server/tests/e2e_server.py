"""ASGI app for Playwright: the real app with yt-dlp calls stubbed out.

Sets nothing in the environment itself; Playwright's ``webServer.env`` does.
Seeds two rows after migrations, just before the startup library move, and fakes downloads.
Later phases fill in more stubs.
"""

from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path
from typing import Any

from app.config import settings
from app.db import SessionLocal
from app.models import Download
from app.services import downloader, job_runner
from app.services import push as push_module
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
    return DownloadResult(
        path=str(path),
        file_size=4,
        media_format="mp4",
        resolution_height=1080,
        vcodec="avc1.640028",
        acodec="mp4a.40.2",
        dynamic_range="SDR",
    )


_VIDEO_URLS = {
    "https://e2e.test/video",
    "https://e2e.test/v/lowhdr",
    "https://e2e.test/watch?v=e2e&list=PLe2e",
}


def _video_info(url: str) -> dict[str, Any]:
    def fmt(
        fid: str, w: int | None, h: int | None, v: str, a: str, ext: str, dr: str | None = None
    ) -> dict[str, Any]:
        return {
            "format_id": fid,
            "ext": ext,
            "width": w,
            "height": h,
            "vcodec": v,
            "acodec": a,
            "abr": 128 if v == "none" else None,
            "dynamic_range": dr,
        }

    formats = [
        fmt("v1080", 1920, 1080, "avc1.640028", "none", "mp4"),
        fmt("v720", 1280, 720, "avc1.64001f", "none", "mp4"),
        fmt("a1", None, None, "none", "mp4a.40.2", "m4a"),
    ]
    if url == "https://e2e.test/v/a":
        hdr10 = "vp09.02.51.10.01.09.16.09.00"
        formats.append(fmt("v2160hdr", 3840, 2160, hdr10, "none", "webm", "HDR10"))
    if url == "https://e2e.test/v/lowhdr":
        formats.append(
            fmt("v2160", 3840, 2160, "vp09.00.51.08.01.01.01.01.00", "none", "webm", "SDR")
        )
        formats.append(
            fmt("v1080hdr", 1920, 1080, "vp09.02.40.10.01.09.16.09.00", "none", "webm", "HDR10")
        )
    return {
        "id": "e2e",
        "title": "E2E Video",
        "uploader": "E2E",
        "duration": 61,
        "webpage_url": "https://e2e.test/video",
        "formats": formats,
    }


def _stub_flat(url: str, **_kwargs: Any) -> dict[str, Any]:
    if url == "https://e2e.test/playlist":
        return {
            "_type": "playlist",
            "title": "E2E Playlist",
            "entries": [
                {"url": f"https://e2e.test/v/{name}", "title": f"Video {name.title()}"}
                for name in ("a", "b", "gone")
            ],
        }
    return _stub_full(url)


def _stub_full(url: str, **_kwargs: Any) -> dict[str, Any]:
    if url in _VIDEO_URLS:
        return _video_info(url)
    if url.startswith("https://e2e.test/v/"):
        time.sleep(1.0)  # long enough for the test to see "Checking"
        name = url.rsplit("/", 1)[-1]
        if name == "gone":
            raise RuntimeError("Video unavailable")
        info = _video_info(url)
        info["webpage_url"] = url
        info["title"] = f"Video {name.title()}"
        if name == "b":
            info["formats"] = [f for f in info["formats"] if f["format_id"] != "v1080"]
        return info
    return _not_stubbed(url)


downloader.extract_info = _stub_full
downloader.extract_flat_info = _stub_flat
job_runner.run_download = _run_download
push_module.webpush = lambda **_kwargs: None  # fake subscriptions never reach the network

import app.main as app_main  # noqa: E402
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
                vcodec="avc1.640028",
                acodec="mp4a.40.2",
                dynamic_range="SDR",
                finished_at=datetime.now(),
            )
        )
        # Used only by e2e/phone.spec.ts, so it never races the seeded-video tests.
        phone = downloads / "phone.mp4"
        phone.write_bytes(b"data")
        session.add(
            Download(
                url="https://e2e.test/phone",
                title="Phone video",
                uploader="E2E",
                status="done",
                progress=100.0,
                file_path=str(phone),
                file_size=4,
                media_format="mp4",
                resolution_height=1080,
                finished_at=datetime.now(),
            )
        )
        session.add(Download(url="https://e2e.test/slow", title="Slow video", status="queued"))
        session.commit()


# The lifespan runs the one-off library move before workers start. Seed first, so the
# seeded file moves like a real library would (to ``e2e/seeded-video.mp4``).
_real_migrate = app_main.migrate_library_layout


def _seed_then_migrate(*args: Any, **kwargs: Any) -> Any:
    _seed()
    return _real_migrate(*args, **kwargs)


app_main.migrate_library_layout = _seed_then_migrate

__all__ = ["app"]
