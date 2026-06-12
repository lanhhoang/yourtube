"""Unit tests for ``app.services.downloader`` progress and cancellation."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.services.downloader import DownloadCancelled, YtdlpProgress, parse_percent, run_download

# --- parse_percent tests ---------------------------------------------------


def test_parse_percent_handles_decimal_string() -> None:
    assert parse_percent("  45.2% ") == 45.2


def test_parse_percent_clamps_to_100() -> None:
    assert parse_percent("150%") == 100.0


def test_parse_percent_clamps_to_zero() -> None:
    assert parse_percent("-5%") == 0.0


def test_parse_percent_returns_none_for_garbage() -> None:
    assert parse_percent("not a percent") is None
    assert parse_percent(None) is None


# --- Progress callback tests -----------------------------------------------


def test_progress_callback_extracts_percent() -> None:
    progress = YtdlpProgress()
    progress({"status": "downloading", "_percent_str": "12.5%"})
    assert progress.percent == 12.5


def test_progress_callback_calls_on_progress_with_normalized_percent() -> None:
    seen: list[float] = []
    progress = YtdlpProgress(on_progress=seen.append)

    progress({"status": "downloading", "_percent_str": "12.5%"})

    assert seen == [12.5]


def test_progress_callback_records_finished_filename() -> None:
    progress = YtdlpProgress()
    progress({"status": "finished", "filename": "/tmp/video.mp4"})
    assert progress.filename == "/tmp/video.mp4"


def test_progress_callback_raises_on_cancellation() -> None:
    progress = YtdlpProgress(cancel_requested=lambda: True)
    with pytest.raises(DownloadCancelled):
        progress({"status": "downloading", "_percent_str": "10.0%"})


# --- run_download tests ----------------------------------------------------


def test_run_download_raises_when_hook_cancels(tmp_path: Path) -> None:
    """``run_download`` propagates ``DownloadCancelled`` from the progress hook."""
    progress = YtdlpProgress(cancel_requested=lambda: True)

    captured_opts: dict = {}

    def factory(opts):
        captured_opts.update(opts)
        fake_ydl = MagicMock()
        fake_ydl.__enter__.return_value = fake_ydl

        def fake_extract_info(url, download):  # noqa: ARG001
            assert download is True
            for hook in captured_opts["progress_hooks"]:
                hook({"status": "downloading", "_percent_str": "10.0%"})
            return {}

        fake_ydl.extract_info.side_effect = fake_extract_info
        return fake_ydl

    with patch("yt_dlp.YoutubeDL", side_effect=factory):
        with pytest.raises(DownloadCancelled):
            run_download(
                url="https://example.com/video",
                output_dir=str(tmp_path),
                progress_hook=progress,
            )


def test_run_download_returns_output_path_on_success(tmp_path: Path) -> None:
    """``run_download`` returns the filename recorded on the ``finished`` hook."""
    progress = YtdlpProgress()
    expected_path = str(tmp_path / "video.mp4")

    captured_opts: dict = {}

    def factory(opts):
        captured_opts.update(opts)
        fake_ydl = MagicMock()
        fake_ydl.__enter__.return_value = fake_ydl

        def fake_extract_info(url, download):  # noqa: ARG001
            assert download is True
            for hook in captured_opts["progress_hooks"]:
                hook({"status": "finished", "filename": expected_path})
            return {}

        fake_ydl.extract_info.side_effect = fake_extract_info
        return fake_ydl

    with patch("yt_dlp.YoutubeDL", side_effect=factory):
        result = run_download(
            url="https://example.com/video",
            output_dir=str(tmp_path),
            progress_hook=progress,
        )
    assert result == expected_path
    assert progress.filename == expected_path


def test_run_download_returns_output_path_without_progress_hook(tmp_path: Path) -> None:
    """``run_download`` still returns the final path when no external hook is supplied."""
    expected_path = str(tmp_path / "no-hook.mp4")

    captured_opts: dict = {}

    def factory(opts):
        captured_opts.update(opts)
        fake_ydl = MagicMock()
        fake_ydl.__enter__.return_value = fake_ydl

        def fake_extract_info(url, download):  # noqa: ARG001
            assert download is True
            for hook in captured_opts["progress_hooks"]:
                hook({"status": "finished", "filename": expected_path})
            return {}

        fake_ydl.extract_info.side_effect = fake_extract_info
        return fake_ydl

    with patch("yt_dlp.YoutubeDL", side_effect=factory):
        result = run_download(
            url="https://example.com/video",
            output_dir=str(tmp_path),
        )
    assert result == expected_path


def test_run_download_writes_transcript_sidecar_when_subtitles_present(tmp_path: Path) -> None:
    """Subtitle downloads produce sibling plain-text transcript sidecars."""
    expected_path = str(tmp_path / "video.mp4")
    subtitle_path = tmp_path / "video.en.srt"
    subtitle_path.write_text(
        "1\n00:00:00,000 --> 00:00:01,000\nFirst line\n",
        encoding="utf-8",
    )

    captured_opts: dict = {}

    def factory(opts):
        captured_opts.update(opts)
        fake_ydl = MagicMock()
        fake_ydl.__enter__.return_value = fake_ydl

        def fake_extract_info(url, download):  # noqa: ARG001
            for hook in captured_opts["progress_hooks"]:
                hook({"status": "finished", "filename": expected_path})
            return {
                "requested_subtitles": {
                    "en": {
                        "ext": "srt",
                        "filepath": str(subtitle_path),
                    }
                }
            }

        fake_ydl.extract_info.side_effect = fake_extract_info
        return fake_ydl

    with patch("yt_dlp.YoutubeDL", side_effect=factory):
        result = run_download(
            url="https://example.com/video",
            output_dir=str(tmp_path),
            subtitles=True,
        )

    assert result == expected_path
    assert subtitle_path.with_suffix(".txt").read_text(encoding="utf-8") == "First line\n"


def test_run_download_succeeds_when_requested_subtitles_are_absent(tmp_path: Path) -> None:
    """Missing subtitles stay best-effort and do not fail the media download."""
    expected_path = str(tmp_path / "video.mp4")

    captured_opts: dict = {}

    def factory(opts):
        captured_opts.update(opts)
        fake_ydl = MagicMock()
        fake_ydl.__enter__.return_value = fake_ydl

        def fake_extract_info(url, download):  # noqa: ARG001
            for hook in captured_opts["progress_hooks"]:
                hook({"status": "finished", "filename": expected_path})
            return {"requested_subtitles": {}}

        fake_ydl.extract_info.side_effect = fake_extract_info
        return fake_ydl

    with patch("yt_dlp.YoutubeDL", side_effect=factory):
        result = run_download(
            url="https://example.com/video",
            output_dir=str(tmp_path),
            subtitles=True,
        )

    assert result == expected_path
