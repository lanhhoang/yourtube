from __future__ import annotations

import re
from collections.abc import Callable
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


def resolve_batch_preview(
    raw: str,
    *,
    extract_info: Callable[..., dict],
    proxy: str | None = None,
    cookies_file: str | None = None,
) -> BatchPreviewResult:
    items: list[BatchPreviewItem] = []

    for url in parse_source_urls(raw):
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
    )
