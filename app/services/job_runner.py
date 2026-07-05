from __future__ import annotations

from pathlib import Path

from app.db import SessionLocal
from app.models import Download
from app.services.downloader import DownloadCancelled, YtdlpProgress, run_download
from app.services.error_mapper import friendly_ytdlp_error
from app.services.queue import is_cancel_requested, release_job, update_progress
from app.services.settings import resolve_runtime_settings


def _persist_progress(job_id: int, percent: float) -> None:
    with SessionLocal() as session:
        update_progress(session, job_id, percent)


def _cancel_requested(job_id: int) -> bool:
    with SessionLocal() as session:
        return is_cancel_requested(session, job_id)


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
        )
    except DownloadCancelled:
        with SessionLocal() as session:
            release_job(session, job_id, status="cancelled")
        return
    except Exception as exc:  # noqa: BLE001
        code, message = friendly_ytdlp_error(str(exc))
        with SessionLocal() as session:
            release_job(
                session,
                job_id,
                status="error",
                error_code=code,
                error_message=message,
            )
        return

    with SessionLocal() as session:
        release_job(
            session,
            job_id,
            status="done",
            file_path=result.path or None,
            file_size=result.file_size,
            media_format=result.media_format,
            resolution_height=result.resolution_height,
        )
