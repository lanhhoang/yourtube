"""Pydantic request and response contracts.

These schemas are the *only* types used in route signatures and responses.
ORM instances from ``app.models`` must never be returned directly to clients.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class InfoRequest(BaseModel):
    """Request body for ``POST /api/info``."""

    url: str = Field(..., min_length=1)
    cookies: bool = False
    proxy: bool = False


class DownloadCreate(BaseModel):
    """Request body for ``POST /api/downloads``."""

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


class FormatInfo(BaseModel):
    """A single format entry returned by the format picker."""

    format_id: str
    ext: str
    stream_kind: Literal["video", "audio", "muxed"] = "muxed"
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


class InfoResponse(BaseModel):
    """Response body for ``POST /api/info``."""

    url: str
    title: str
    uploader: str | None = None
    duration: int | None = None
    thumbnail: str | None = None
    formats: list[FormatInfo] = Field(default_factory=list)
    captions: dict[str, list[dict]] = Field(default_factory=dict)


class DownloadResponse(BaseModel):
    """Response body for download endpoints."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    url: str
    title: str | None = None
    uploader: str | None = None
    duration: int | None = None
    thumbnail: str | None = None
    video_format_id: str | None = None
    audio_format_id: str | None = None
    audio_bitrate: str | None = None
    subtitles: bool = False
    status: str
    progress: float
    error_code: str | None = None
    error_message: str | None = None
    file_path: str | None = None
    file_size: int | None = None
    media_format: str | None = None
    resolution_height: int | None = None
    created_at: datetime
    updated_at: datetime
    finished_at: datetime | None = None


class ErrorResponse(BaseModel):
    """Stable error envelope returned by every error path."""

    code: str
    message: str


class SettingsResponse(BaseModel):
    """Response body for ``GET /api/settings``.

    Values are always strings because the settings table is
    string-valued; the router reads through the service's catalog.
    """

    max_concurrent: str
    proxy_url: str
    cookies_path: str
    downloads_dir: str


class MutationOkResponse(BaseModel):
    """Standard ``{"ok": true}`` body for write endpoints."""

    ok: bool = True
