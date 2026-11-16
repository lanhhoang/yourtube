"""Pydantic request and response contracts.

These schemas are the *only* types used in route signatures and responses.
ORM instances from ``app.models`` must never be returned directly to clients.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


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
