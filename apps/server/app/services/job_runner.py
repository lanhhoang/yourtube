from __future__ import annotations

import logging
from pathlib import Path
from typing import cast

from app.db import SessionLocal
from app.models import Download
from app.schemas import QualityCap
from app.services.downloader import DownloadCancelled, YtdlpProgress, run_download
from app.services.error_mapper import friendly_ytdlp_error
from app.services.library_paths import PlaylistFolder
from app.services.push import notify_settled
from app.services.queue import is_cancel_requested, release_job, update_progress
from app.services.settings import resolve_runtime_settings

logger = logging.getLogger(__name__)


def _persist_progress(job_id: int, percent: float) -> None:
    with SessionLocal() as session:
        update_progress(session, job_id, percent)


def _cancel_requested(job_id: int) -> bool:
    with SessionLocal() as session:
        return is_cancel_requested(session, job_id)


def _release_and_notify(
    job_id: int,
    *,
    status: str,
    error_code: str | None = None,
    error_message: str | None = None,
    file_path: str | None = None,
    file_size: int | None = None,
    media_format: str | None = None,
    resolution_height: int | None = None,
) -> None:
    with SessionLocal() as session:
        released = release_job(
            session,
            job_id,
            status=status,
            error_code=error_code,
            error_message=error_message,
            file_path=file_path,
            file_size=file_size,
            media_format=media_format,
            resolution_height=resolution_height,
        )
    if released:
        try:
            notify_settled(job_id)
        except Exception:  # noqa: BLE001 - a push failure never changes the job outcome
            logger.exception("push notification failed for job %s", job_id)


def run_claimed_job(job_id: int) -> None:
    with SessionLocal() as session:
        runtime = resolve_runtime_settings(session)
        Path(runtime.downloads_dir).mkdir(parents=True, exist_ok=True)
        job = session.get(Download, job_id)
        if job is None:
            return
        job_url = job.url
        job_video_format_id = job.video_format_id
        job_audio_format_id = job.audio_format_id
        job_output_template = job.output_template
        job_audio_bitrate = job.audio_bitrate
        job_subtitles = job.subtitles
        job_hdr = job.hdr
        job_playlist = (
            PlaylistFolder(job.playlist_title, job.playlist_channel, job.playlist_id)
            if job.playlist_title or job.playlist_channel or job.playlist_id
            else None
        )
        job_quality_cap = cast("QualityCap | None", job.quality_cap)

    progress = YtdlpProgress(
        cancel_requested=lambda: _cancel_requested(job_id),
        on_progress=lambda percent: _persist_progress(job_id, percent),
    )

    try:
        result = run_download(
            url=job_url,
            video_format_id=job_video_format_id,
            audio_format_id=job_audio_format_id,
            output_template=job_output_template,
            output_dir=str(runtime.downloads_dir),
            audio_bitrate=job_audio_bitrate,
            proxy=runtime.proxy_url,
            cookies_file=str(runtime.cookies_path) if runtime.cookies_path else None,
            subtitles=job_subtitles,
            progress_hook=progress,
            quality_cap=job_quality_cap,
            hdr=job_hdr,
            playlist=job_playlist,
        )
    except DownloadCancelled:
        _release_and_notify(job_id, status="cancelled")
        return
    except Exception as exc:  # noqa: BLE001
        code, message = friendly_ytdlp_error(str(exc))
        _release_and_notify(job_id, status="error", error_code=code, error_message=message)
        return

    _release_and_notify(
        job_id,
        status="done",
        file_path=result.path or None,
        file_size=result.file_size,
        media_format=result.media_format,
        resolution_height=result.resolution_height,
    )
