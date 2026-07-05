from __future__ import annotations

import pytest
from starlette.datastructures import FormData

from app.services.enqueue_intake import build_batch_downloads, build_single_download


def test_build_single_download_returns_payload_and_target_id() -> None:
    form = FormData(
        [
            ("url", "https://example.com/watch?v=1"),
            ("title", "Example"),
            ("duration", "42"),
            ("target_id", "batch-status"),
            ("video_format_id", "137"),
            ("audio_format_id", "140"),
            ("subtitles", "on"),
        ]
    )

    payload, target_id = build_single_download(form)

    assert payload.url == "https://example.com/watch?v=1"
    assert payload.title == "Example"
    assert payload.duration == 42
    assert payload.video_format_id == "137"
    assert payload.audio_format_id == "140"
    assert payload.subtitles is True
    assert target_id == "batch-status"


def test_build_single_download_falls_back_to_info_status() -> None:
    form = FormData([("url", "https://example.com/watch?v=1"), ("target_id", "wrong")])

    _payload, target_id = build_single_download(form)

    assert target_id == "info-status"


def test_build_single_download_falls_back_to_info_status_when_target_is_missing() -> None:
    form = FormData([("url", "https://example.com/watch?v=1")])

    _payload, target_id = build_single_download(form)

    assert target_id == "info-status"


def test_build_single_download_rejects_non_numeric_duration() -> None:
    form = FormData([("url", "https://example.com/watch?v=1"), ("duration", "soon")])

    with pytest.raises(ValueError):
        build_single_download(form)


def test_build_batch_downloads_prefers_raw_sources_and_dedupes_urls() -> None:
    form = FormData(
        [
            (
                "sources",
                "https://example.com/a\nhttps://example.com/a\nhttps://example.com/b",
            )
        ]
    )

    payloads = build_batch_downloads(form)

    assert [payload.url for payload in payloads] == [
        "https://example.com/a",
        "https://example.com/b",
    ]


def test_build_batch_downloads_uses_preview_rows_when_sources_are_empty() -> None:
    form = FormData(
        [
            ("url", "https://example.com/a"),
            ("url", "https://example.com/b"),
            ("title", "Title A"),
            ("title", "Title B"),
            ("duration", "12"),
            ("duration", "24"),
            ("video_format_id", "137"),
            ("video_format_id", ""),
            ("audio_format_id", "140"),
            ("audio_format_id", "251"),
        ]
    )

    payloads = build_batch_downloads(form)

    assert len(payloads) == 2
    assert payloads[0].title == "Title A"
    assert payloads[0].duration == 12
    assert payloads[0].video_format_id == "137"
    assert payloads[0].audio_format_id == "140"
    assert payloads[1].title == "Title B"
    assert payloads[1].duration == 24
    assert payloads[1].video_format_id is None
    assert payloads[1].audio_format_id == "251"
