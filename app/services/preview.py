from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from app.services.batch_preview import BatchPreviewResult, expand_playlist_entries
from app.services.downloader import (
    StreamPickerPayload,
    build_stream_picker_payload,
    extract_flat_info,
    normalize_formats,
)


@dataclass(frozen=True)
class SinglePreviewResult:
    url: str
    title: str
    uploader: str | None
    duration: int | None
    thumbnail: str | None
    picker_payload: StreamPickerPayload


def resolve_single_preview(
    url: str,
    *,
    extract_info: Callable[..., dict],
    proxy: str | None = None,
    cookies_file: str | None = None,
) -> SinglePreviewResult:
    info = extract_info(url, proxy=proxy, cookies_file=cookies_file)
    formats = normalize_formats(info)
    return SinglePreviewResult(
        url=url,
        title=info.get("title", ""),
        uploader=info.get("uploader"),
        duration=info.get("duration"),
        thumbnail=info.get("thumbnail"),
        picker_payload=build_stream_picker_payload(formats),
    )


def resolve_batch_preview(
    raw: str,
    *,
    extract_info: Callable[..., dict],
    proxy: str | None = None,
    cookies_file: str | None = None,
) -> BatchPreviewResult:
    from app.services.batch_preview import resolve_batch_preview as resolve_existing_batch_preview

    return resolve_existing_batch_preview(
        raw,
        extract_info=extract_info,
        expand_playlist=lambda url: expand_playlist_entries(
            url,
            extract_info=extract_flat_info,
            proxy=proxy,
            cookies_file=cookies_file,
        ),
        proxy=proxy,
        cookies_file=cookies_file,
    )
