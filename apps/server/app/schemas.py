"""Pydantic request and response contracts.

These schemas are the *only* types used in route signatures and responses.
ORM instances from ``app.models`` must never be returned directly to clients.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from app.models import Download


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
    subtitles: bool = False


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
        audio_only = (row.audio_format_id and not row.video_format_id) or (
            row.status == "done" and row.resolution_height is None
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


class QueueOut(BaseModel):
    active: list[JobOut]
    failed: list[JobOut]
    completed: list[JobOut]
