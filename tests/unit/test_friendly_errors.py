"""Unit tests for ``app.services.error_mapper.friendly_ytdlp_error``.

Each test feeds a representative raw yt-dlp error string and asserts that
the mapper returns a stable error code plus a user-facing message.
"""

from __future__ import annotations

import pytest

from app.services.error_mapper import friendly_ytdlp_error


@pytest.mark.parametrize(
    "raw",
    [
        "Private video",
        "Sign in to confirm your age",
        "This video is private",
    ],
)
def test_private_or_age_restricted_video(raw: str) -> None:
    code, message = friendly_ytdlp_error(raw)
    assert code == "private_or_age_restricted"
    assert message  # non-empty user-facing text


@pytest.mark.parametrize(
    "raw",
    [
        "Video unavailable. This video is not available in your country",
        "Video not available in your region",
        "This video is geo-blocked in your country",
    ],
)
def test_geo_blocked_video(raw: str) -> None:
    code, message = friendly_ytdlp_error(raw)
    assert code == "geo_blocked"
    assert message


@pytest.mark.parametrize(
    "raw",
    [
        "HTTP Error 403: Forbidden",
        "403 Forbidden",
        "Got error 403 from server",
    ],
)
def test_http_403(raw: str) -> None:
    code, message = friendly_ytdlp_error(raw)
    assert code == "http_forbidden"
    assert message


@pytest.mark.parametrize(
    "raw",
    [
        "Connection timed out",
        "Read timed out",
        "HTTPSConnectionPool(host='example.com', port=443): Read timed out.",
    ],
)
def test_timeout(raw: str) -> None:
    code, message = friendly_ytdlp_error(raw)
    assert code == "timeout"
    assert message


@pytest.mark.parametrize(
    "raw",
    [
        "No space left on device",
        "Disk full; cannot write to /tmp/output.mp4",
    ],
)
def test_disk_full(raw: str) -> None:
    code, message = friendly_ytdlp_error(raw)
    assert code == "disk_full"
    assert message


@pytest.mark.parametrize(
    "raw",
    [
        "Permission denied",
        "[Errno 13] Permission denied: '/var/data/file.mp4'",
    ],
)
def test_permission_denied(raw: str) -> None:
    code, message = friendly_ytdlp_error(raw)
    assert code == "permission_denied"
    assert message


def test_generic_fallback() -> None:
    """Unrecognised errors fall back to a stable generic code."""
    code, message = friendly_ytdlp_error("Something weird happened that we don't recognise")
    assert code == "ytdlp_error"
    assert message


def test_friendly_error_maps_output_template_write_failures() -> None:
    code, message = friendly_ytdlp_error(
        "ERROR: unable to open for writing: [Errno 13] Permission denied: 'title.en-US.vtt.part'"
    )

    assert code == "output_path_unwritable"
    assert "output path" in message.lower()


def test_friendly_error_keeps_generic_permission_denied_for_non_template_errors() -> None:
    code, message = friendly_ytdlp_error("[Errno 13] Permission denied: '/var/data/file.mp4'")

    assert code == "permission_denied"
    assert message
