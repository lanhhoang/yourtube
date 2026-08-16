from __future__ import annotations

import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from typing import TypeGuard, cast
from urllib.parse import urlparse

from app.services.downloader import (
    StreamPickerPayload,
    build_stream_picker_payload,
    normalize_formats,
)
from app.services.error_mapper import friendly_ytdlp_error


def _empty_picker_payload() -> StreamPickerPayload:
    return {
        "video_streams": [],
        "audio_streams": [],
        "has_muxed_streams": False,
        "expected_container_by_pair": {"|": "unknown"},
    }


@dataclass(frozen=True)
class BatchPreviewItem:
    source_url: str
    status: str
    title: str | None
    uploader: str | None
    duration: int | None
    thumbnail: str | None
    error_code: str | None
    error_message: str | None
    picker_payload: StreamPickerPayload = field(default_factory=_empty_picker_payload)


@dataclass(frozen=True)
class BatchPreviewResult:
    items: list[BatchPreviewItem]
    valid_count: int
    invalid_count: int
    truncated_count: int = 0
    page: int = 1
    page_size: int = 20
    total_count: int = 0
    total_pages: int = 1
    has_previous: bool = False
    has_next: bool = False


@dataclass(frozen=True)
class _ExpandedEntry:
    source_url: str
    title: str | None = None
    error_code: str | None = None
    error_message: str | None = None


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


def _is_full_http_url(value: object) -> TypeGuard[str]:
    if not isinstance(value, str):
        return False
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _entry_url(entry: dict[str, object]) -> str | None:
    for key in ("webpage_url", "url"):
        value = entry.get(key)
        if _is_full_http_url(value):
            return value
    entry_id = entry.get("id")
    if isinstance(entry_id, str) and entry_id:
        return f"https://www.youtube.com/watch?v={entry_id}"
    return None


def _invalid_entry(source_url: str, position: int) -> _ExpandedEntry:
    label = f"Playlist entry {position}"
    return _ExpandedEntry(
        source_url=source_url,
        title=label,
        error_code="invalid_playlist_entry",
        error_message=f"{label} has no usable video URL.",
    )


def expand_playlist_entries(
    url: str,
    *,
    extract_info: Callable[..., dict],
    proxy: str | None = None,
    cookies_file: str | None = None,
) -> list[_ExpandedEntry]:
    info = extract_info(url, proxy=proxy, cookies_file=cookies_file)
    if "entries" not in info or info["entries"] is None:
        return [_ExpandedEntry(source_url=url)]
    entries = info["entries"]
    if isinstance(entries, (str, bytes)) or not isinstance(entries, Iterable):
        return [
            _ExpandedEntry(
                source_url=url,
                error_code="invalid_playlist_entries",
                error_message="Playlist entries could not be read.",
            )
        ]

    expanded: list[_ExpandedEntry] = []
    for position, entry in enumerate(entries, start=1):
        if not isinstance(entry, dict):
            expanded.append(_invalid_entry(url, position))
            continue
        entry_data = cast(dict[str, object], entry)
        entry_url = _entry_url(entry_data)
        if entry_url is None:
            expanded.append(_invalid_entry(url, position))
            continue
        title = entry_data.get("title")
        expanded.append(
            _ExpandedEntry(
                source_url=entry_url,
                title=title if isinstance(title, str) else None,
            )
        )
    return expanded


def resolve_batch_preview(
    raw: str,
    *,
    extract_info: Callable[..., dict],
    expand_playlist: Callable[[str], Iterable[str | _ExpandedEntry]] | None = None,
    proxy: str | None = None,
    cookies_file: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> BatchPreviewResult:
    items: list[BatchPreviewItem] = []
    seen: set[str] = set()
    expanded_entries: list[_ExpandedEntry] = []
    expand = expand_playlist or (lambda url: [url])

    for source_url in parse_source_urls(raw, dedupe=False):
        try:
            resolved_entries = [
                entry if isinstance(entry, _ExpandedEntry) else _ExpandedEntry(source_url=entry)
                for entry in expand(source_url)
            ]
        except Exception:  # noqa: BLE001
            resolved_entries = [_ExpandedEntry(source_url=source_url)]

        for entry in resolved_entries:
            if entry.error_code is not None:
                expanded_entries.append(entry)
                continue
            if entry.source_url in seen:
                continue
            seen.add(entry.source_url)
            expanded_entries.append(entry)

    page_size = max(1, page_size)
    total_count = len(expanded_entries)
    total_pages = max(1, (total_count + page_size - 1) // page_size)
    page = min(max(1, page), total_pages)
    start = (page - 1) * page_size

    for entry in expanded_entries[start : start + page_size]:
        if entry.error_code is not None:
            items.append(
                BatchPreviewItem(
                    source_url=entry.source_url,
                    status="error",
                    title=entry.title,
                    uploader=None,
                    duration=None,
                    thumbnail=None,
                    error_code=entry.error_code,
                    error_message=entry.error_message,
                )
            )
            continue

        try:
            info = extract_info(entry.source_url, proxy=proxy, cookies_file=cookies_file)
        except Exception as exc:  # noqa: BLE001
            code, message = friendly_ytdlp_error(str(exc))
            items.append(
                BatchPreviewItem(
                    source_url=entry.source_url,
                    status="error",
                    title=entry.title,
                    uploader=None,
                    duration=None,
                    thumbnail=None,
                    error_code=code,
                    error_message=message,
                )
            )
            continue

        if info.get("_type") == "playlist" or isinstance(info.get("entries"), list):
            items.append(
                BatchPreviewItem(
                    source_url=entry.source_url,
                    status="error",
                    title=entry.title,
                    uploader=None,
                    duration=None,
                    thumbnail=None,
                    error_code="unsupported_playlist",
                    error_message="Playlist previews are not supported yet.",
                )
            )
            continue

        items.append(
            BatchPreviewItem(
                source_url=entry.source_url,
                status="ready",
                title=info.get("title") or entry.title,
                uploader=info.get("uploader"),
                duration=info.get("duration"),
                thumbnail=info.get("thumbnail"),
                error_code=None,
                error_message=None,
                picker_payload=build_stream_picker_payload(normalize_formats(info)),
            )
        )

    valid_count = sum(1 for item in items if item.status == "ready")
    return BatchPreviewResult(
        items=items,
        valid_count=valid_count,
        invalid_count=len(items) - valid_count,
        page=page,
        page_size=page_size,
        total_count=total_count,
        total_pages=total_pages,
        has_previous=page > 1,
        has_next=page < total_pages,
    )
