from __future__ import annotations

import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass

from app.services.error_mapper import friendly_ytdlp_error


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


@dataclass(frozen=True)
class BatchPreviewResult:
    items: list[BatchPreviewItem]
    valid_count: int
    invalid_count: int
    truncated_count: int = 0


def parse_source_urls(raw: str) -> list[str]:
    seen: set[str] = set()
    urls: list[str] = []
    for part in re.split(r"\s+|,\s*(?=https?://)", raw):
        url = part.strip()
        if not url or not url.startswith("http"):
            continue
        if url in seen:
            continue
        seen.add(url)
        urls.append(url)
    return urls


def expand_playlist_entries(
    url: str,
    *,
    extract_info: Callable[..., dict],
    proxy: str | None = None,
    cookies_file: str | None = None,
) -> list[str]:
    info = extract_info(url, proxy=proxy, cookies_file=cookies_file)
    entries = info.get("entries")
    if isinstance(entries, (str, bytes)) or not isinstance(entries, Iterable):
        return [url]

    urls: list[str] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        for key in ("webpage_url", "url"):
            entry_url = entry.get(key)
            if isinstance(entry_url, str) and entry_url.startswith("http"):
                urls.append(entry_url)
                break
    return urls or [url]


def expand_source_urls(
    source_urls: list[str],
    *,
    expand_playlist: Callable[[str], list[str]],
    limit: int = 50,
) -> tuple[list[str], int]:
    seen: set[str] = set()
    expanded: list[str] = []
    truncated_count = 0

    for source_url in source_urls:
        try:
            resolved_urls = expand_playlist(source_url)
        except Exception:  # noqa: BLE001
            resolved_urls = [source_url]

        for resolved_url in resolved_urls:
            if resolved_url in seen:
                continue
            seen.add(resolved_url)
            if len(expanded) >= limit:
                truncated_count += 1
                continue
            expanded.append(resolved_url)

    return expanded, truncated_count


def resolve_batch_preview(
    raw: str,
    *,
    extract_info: Callable[..., dict],
    expand_playlist: Callable[[str], list[str]] | None = None,
    proxy: str | None = None,
    cookies_file: str | None = None,
) -> BatchPreviewResult:
    items: list[BatchPreviewItem] = []
    source_urls = parse_source_urls(raw)
    expanded_urls, truncated_count = expand_source_urls(
        source_urls,
        expand_playlist=expand_playlist or (lambda url: [url]),
    )

    for url in expanded_urls:
        try:
            info = extract_info(url, proxy=proxy, cookies_file=cookies_file)
        except Exception as exc:  # noqa: BLE001
            code, message = friendly_ytdlp_error(str(exc))
            items.append(
                BatchPreviewItem(
                    source_url=url,
                    status="error",
                    title=None,
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
                    source_url=url,
                    status="error",
                    title=None,
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
                source_url=url,
                status="ready",
                title=info.get("title"),
                uploader=info.get("uploader"),
                duration=info.get("duration"),
                thumbnail=info.get("thumbnail"),
                error_code=None,
                error_message=None,
            )
        )

    valid_count = sum(1 for item in items if item.status == "ready")
    return BatchPreviewResult(
        items=items,
        valid_count=valid_count,
        invalid_count=len(items) - valid_count,
        truncated_count=truncated_count,
    )
