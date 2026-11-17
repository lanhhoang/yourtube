"""Sources: turn pasted URLs into one video or a list of entries for the web app."""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable
from typing import Any, cast
from urllib.parse import parse_qs, urlparse

from app.schemas import SourceEntry, SourcesResult, StreamPicker, VideoDetails
from app.services.downloader import build_stream_picker_payload, normalize_formats
from app.services.error_mapper import friendly_ytdlp_error
from app.services.quality import best_short_side

MAX_ENTRIES = 500
_MAX_REDIRECTS = 2

_YT_HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com", "youtu.be"}


def parse_source_urls(raw: str, *, dedupe: bool = True) -> list[str]:
    seen: set[str] = set()
    urls: list[str] = []
    for part in re.split(r"\s+|,\s*(?=https?://)", raw):
        url = part.strip()
        if not url or not url.startswith("http"):
            continue
        if dedupe and url in seen:
            continue
        seen.add(url)
        urls.append(url)
    return urls


def entry_url(entry: dict[str, object]) -> str | None:
    for key in ("webpage_url", "url"):
        value = entry.get(key)
        if isinstance(value, str):
            parsed = urlparse(value)
            if parsed.scheme in {"http", "https"} and parsed.netloc:
                return value
    entry_id = entry.get("id")
    if isinstance(entry_id, str) and entry_id:
        return f"https://www.youtube.com/watch?v={entry_id}"
    return None


def playlist_url_for(url: str) -> str | None:
    """The playlist page for a YouTube video URL that carries a ``list`` parameter."""
    parsed = urlparse(url)
    if parsed.netloc.lower() not in _YT_HOSTS:
        return None
    ids = parse_qs(parsed.query).get("list")
    return f"https://www.youtube.com/playlist?list={ids[0]}" if ids and ids[0] else None


def _int_or_none(value: object) -> int | None:
    return int(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _str_or_none(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def video_details(info: dict, url: str) -> VideoDetails:
    # The job stores this URL and the downloader does not set ``noplaylist``,
    # so prefer yt-dlp's canonical URL over a pasted ``watch?v=X&list=Y``.
    formats = normalize_formats(info)
    return VideoDetails(
        url=_str_or_none(info.get("webpage_url")) or url,
        title=_str_or_none(info.get("title")) or url,
        uploader=_str_or_none(info.get("uploader")) or _str_or_none(info.get("channel")),
        duration=_int_or_none(info.get("duration")),
        thumbnail=_thumbnail(info),
        picker=StreamPicker.model_validate(build_stream_picker_payload(formats)),
        best_short_side=best_short_side(formats),
        playlist_url=playlist_url_for(url),
    )


def _thumbnail(info: dict) -> str | None:
    thumb = _str_or_none(info.get("thumbnail"))
    if thumb:
        return thumb
    thumbs = info.get("thumbnails")
    if isinstance(thumbs, list) and thumbs:
        last = thumbs[-1]
        if isinstance(last, dict):
            return _str_or_none(last.get("url"))
    return None


def _is_playlist(info: dict) -> bool:
    return info.get("entries") is not None or info.get("_type") == "playlist"


def _entry(index: int, url: str, info: dict, details: VideoDetails | None = None) -> SourceEntry:
    return SourceEntry(
        index=index,
        url=url,
        title=_str_or_none(info.get("title")),
        uploader=_str_or_none(info.get("uploader")) or _str_or_none(info.get("channel")),
        duration=_int_or_none(info.get("duration")),
        thumbnail=_thumbnail(info),
        details=details,
    )


def _error_entry(url: str, title: str | None, code: str, message: str) -> SourceEntry:
    return SourceEntry(
        index=0,
        url=url,
        title=title,
        uploader=None,
        duration=None,
        thumbnail=None,
        error_code=code,
        error_message=message,
    )


def _expand(info: dict, source_url: str) -> list[SourceEntry]:
    raw_entries = info.get("entries")
    if isinstance(raw_entries, (str, bytes)) or not isinstance(raw_entries, Iterable):
        return [
            _error_entry(
                source_url,
                None,
                "invalid_playlist_entries",
                "Playlist entries could not be read.",
            )
        ]
    out: list[SourceEntry] = []
    for position, raw in enumerate(raw_entries, start=1):
        url = entry_url(cast(dict[str, object], raw)) if isinstance(raw, dict) else None
        if url is None:
            label = f"Playlist entry {position}"
            out.append(
                _error_entry(
                    source_url, label, "invalid_playlist_entry", f"{label} has no usable video URL."
                )
            )
            continue
        out.append(_entry(0, url, cast(dict[str, Any], raw)))
    return out


def list_sources(
    raw: str,
    *,
    extract_flat: Callable[..., dict],
    extract_full: Callable[..., dict],
    proxy: str | None,
    cookies_file: str | None,
) -> SourcesResult:
    urls = parse_source_urls(raw)
    if not urls:
        raise ValueError("No URLs found.")
    kw = {"noplaylist": True, "proxy": proxy, "cookies_file": cookies_file}

    collected: list[SourceEntry] = []
    playlist_title: str | None = None
    single_video: VideoDetails | None = None
    for url in urls:
        try:
            info = extract_flat(url, **kw)
            # A redirect (channel root, ``watch?list=`` without ``v``) comes back as a bare
            # ``url`` result; follow it so we never treat a playlist as one video.
            current, hops = url, 0
            while (
                info.get("_type") in ("url", "url_transparent")
                and info.get("entries") is None
                and isinstance(info.get("url"), str)
                and info["url"] != current
                and hops < _MAX_REDIRECTS
            ):
                current, hops = info["url"], hops + 1
                info = extract_flat(current, **kw)
            if not _is_playlist(info) and not info.get("formats"):
                info = extract_full(current, **kw)
            if _is_playlist(info):
                playlist_title = _str_or_none(info.get("title"))
                collected.extend(_expand(info, url))
                continue
            details = video_details(info, url)
            single_video = details
            collected.append(_entry(0, details.url, info, details))
        except Exception as exc:  # noqa: BLE001
            if len(urls) == 1:
                raise
            code, message = friendly_ytdlp_error(str(exc))
            collected.append(_error_entry(url, None, code, message))

    if len(urls) == 1 and single_video is not None:
        return SourcesResult(kind="video", title=None, video=single_video, entries=[], skipped=0)

    seen: set[str] = set()
    unique: list[SourceEntry] = []
    for entry in collected:
        if entry.error_code is None:
            if entry.url in seen:
                continue
            seen.add(entry.url)
        unique.append(entry)
    kept = unique[:MAX_ENTRIES]
    for index, entry in enumerate(kept):
        entry.index = index
    return SourcesResult(
        kind="list",
        title=playlist_title if len(urls) == 1 else None,
        video=None,
        entries=kept,
        skipped=len(unique) - len(kept),
    )
