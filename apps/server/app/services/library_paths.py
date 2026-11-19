"""Slug and path rules for the channel/playlist library layout."""

from __future__ import annotations

import glob
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from anyascii import anyascii

SEGMENT_MAX = 80

_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def slugify(text: str | None) -> str:
    """ASCII, lowercase, dash-separated, at most ``SEGMENT_MAX`` characters; ``""`` if empty."""
    if not text:
        return ""
    slug = _NON_ALNUM.sub("-", anyascii(text).lower()).strip("-")
    return slug[:SEGMENT_MAX].rstrip("-")


def first_slug(*candidates: str | None, fallback: str) -> str:
    """The first candidate that slugs to something, else ``fallback``."""
    for candidate in candidates:
        slug = slugify(candidate)
        if slug:
            return slug
    return fallback


@dataclass(frozen=True)
class PlaylistFolder:
    title: str | None
    channel: str | None
    id: str | None


def video_id_from_url(url: str) -> str | None:
    """The video id from a ``v=`` parameter, a ``youtu.be/<id>`` or a ``/shorts/<id>`` URL."""
    parsed = urlparse(url)
    ids = parse_qs(parsed.query).get("v")
    if ids and ids[0]:
        return ids[0]
    parts = [p for p in parsed.path.split("/") if p]
    if parsed.netloc.lower() == "youtu.be" and parts:
        return parts[0]
    if len(parts) >= 2 and parts[0] == "shorts":
        return parts[1]
    return None


def _str(value: Any) -> str | None:
    return value if isinstance(value, str) else None


def default_stem(
    info: Mapping[str, Any], playlist: PlaylistFolder | None, downloads_dir: Path
) -> Path:
    """Absolute path, without extension, for a download under the default layout."""
    channel = first_slug(
        playlist.channel if playlist else None,
        _str(info.get("channel")),
        _str(info.get("uploader")),
        _str(info.get("channel_id")),
        _str(info.get("uploader_id")),
        fallback="unknown-channel",
    )
    folder = downloads_dir / channel
    if playlist is not None:
        folder = folder / first_slug(playlist.title, playlist.id, fallback="playlist")
    title = first_slug(_str(info.get("title")), _str(info.get("id")), fallback="video")
    stem = folder / title
    if glob.glob(glob.escape(str(stem)) + ".*"):
        stem = folder / f"{title}-{slugify(_str(info.get('id')))}"
    return stem
