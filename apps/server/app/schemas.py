"""Pydantic request and response contracts.

These schemas are the *only* types used in route signatures and responses.
ORM instances from ``app.models`` must never be returned directly to clients.
"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, Field, field_validator

if TYPE_CHECKING:
    from app.models import Download


type QualityCap = Literal["best", "2160", "1440", "1080", "720", "480", "audio"]


class DownloadCreate(BaseModel):
    """Request body for enqueuing a new download."""

    url: str = Field(..., min_length=1)
    title: str | None = None
    uploader: str | None = None
    duration: int | None = None
    thumbnail: str | None = None
    video_format_id: str | None = None
    audio_format_id: str | None = None
    output_template: str | None = None
    audio_bitrate: str | None = None
    quality_cap: QualityCap | None = None
    subtitles: bool = False

    @field_validator("audio_bitrate")
    @classmethod
    def _check_audio_bitrate(cls, value: str | None) -> str | None:
        return (value or "").strip() or None


type StreamKind = Literal["video", "audio", "muxed"]


class FormatInfo(BaseModel):
    """A single format entry returned by the format picker."""

    format_id: str
    ext: str
    stream_kind: StreamKind = "muxed"
    audio_channels: int | None = None
    resolution: str | None = None
    height: int | None = None
    width: int | None = None
    fps: float | None = None
    vcodec: str | None = None
    acodec: str | None = None
    abr: float | None = None
    vbr: float | None = None
    filesize: int | None = None
    tbr: float | None = None
    format_note: str | None = None
    container: str | None = None


type JobStatus = Literal["queued", "active", "done", "error", "cancelled"]
type MediaKind = Literal["video", "audio"]


class JobOut(BaseModel):
    """A download job as the web app sees it."""

    id: int
    url: str
    title: str | None
    uploader: str | None
    duration: int | None
    thumbnail: str | None
    status: JobStatus
    progress: float
    quality_cap: QualityCap | None
    error_code: str | None
    error_message: str | None
    media_kind: MediaKind
    file_size: int | None
    media_format: str | None
    resolution_height: int | None
    created_at: datetime
    finished_at: datetime | None

    @classmethod
    def from_row(cls, row: Download) -> JobOut:
        audio_only = (
            (row.audio_format_id and not row.video_format_id)
            or (row.quality_cap == "audio" and not row.video_format_id)
            or (row.status == "done" and row.resolution_height is None)
        )
        return cls.model_validate(
            {
                "id": row.id,
                "url": row.url,
                "title": row.title,
                "uploader": row.uploader,
                "duration": row.duration,
                "thumbnail": row.thumbnail,
                "status": row.status,
                "progress": row.progress,
                "quality_cap": row.quality_cap,
                "error_code": row.error_code,
                "error_message": row.error_message,
                "media_kind": "audio" if audio_only else "video",
                "file_size": row.file_size,
                "media_format": row.media_format,
                "resolution_height": row.resolution_height,
                "created_at": row.created_at,
                "finished_at": row.finished_at,
            }
        )


class JobCreate(DownloadCreate):
    """One job in an enqueue request; the template must stay inside the downloads folder."""

    @field_validator("audio_bitrate")
    @classmethod
    def _check_strict_bitrate(cls, value: str | None) -> str | None:
        # Only the JSON API is strict. Rows queued before it may hold free-form
        # bitrates; the worker reads those straight from the table, and
        # cap_format_options tolerates them.
        if value is not None and not re.fullmatch(r"\d+[kK]?", value):
            raise ValueError("Audio bitrate must be a number such as 192 or 192K.")
        return value

    @field_validator("output_template")
    @classmethod
    def _check_output_template(cls, value: str | None) -> str | None:
        from app.services.downloader import resolve_output_template

        if value is None or not value.strip():
            return None
        if Path(value).is_absolute():
            raise ValueError("Output template must be relative to the downloads folder.")
        resolve_output_template(value, "/tmp")
        return value


class EnqueueRequest(BaseModel):
    jobs: list[JobCreate] = Field(min_length=1, max_length=500)


class EnqueueResult(BaseModel):
    created: list[JobOut]


class StreamRow(BaseModel):
    format_id: str
    ext: str
    resolution: str | None
    height: int | None
    width: int | None
    vcodec: str | None
    acodec: str | None
    abr: float | None
    audio_channels: int | None
    container: str | None


class StreamPicker(BaseModel):
    video_streams: list[StreamRow]
    audio_streams: list[StreamRow]
    has_muxed_streams: bool
    expected_container_by_pair: dict[str, str]


class VideoDetails(BaseModel):
    url: str
    title: str
    uploader: str | None
    duration: int | None
    thumbnail: str | None
    picker: StreamPicker
    best_short_side: int | None
    playlist_url: str | None


class SourceEntry(BaseModel):
    index: int
    url: str
    title: str | None
    uploader: str | None
    duration: int | None
    thumbnail: str | None
    error_code: str | None = None
    error_message: str | None = None
    details: VideoDetails | None = None


class SourcesRequest(BaseModel):
    urls: str = Field(min_length=1)
    use_proxy: bool = False
    use_cookies: bool = False


class LookupRequest(BaseModel):
    url: str = Field(min_length=1)
    use_proxy: bool = False
    use_cookies: bool = False


class SourcesResult(BaseModel):
    kind: Literal["video", "list"]
    title: str | None
    video: VideoDetails | None
    entries: list[SourceEntry]
    skipped: int


class QueueOut(BaseModel):
    active: list[JobOut]
    failed: list[JobOut]
    completed: list[JobOut]


class SettingsOut(BaseModel):
    max_concurrent: int
    proxy_url: str
    cookies_path: str
    downloads_dir: str


class SettingsIn(BaseModel):
    max_concurrent: int = Field(ge=1, le=5)
    proxy_url: str = ""
    cookies_path: str = ""
    downloads_dir: str = ""


class DiagnosticsOut(BaseModel):
    level: Literal["ok", "warning"]
    messages: list[str]
    js_runtime_ready: bool
    workers_enabled: bool
