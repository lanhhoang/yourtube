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
    assert result.path == expected_path
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
    assert result.path == expected_path


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

    assert result.path == expected_path
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

    assert result.path == expected_path


def test_run_download_extracts_media_format_and_resolution(tmp_path: Path) -> None:
    """``run_download`` extracts ``ext`` and ``height`` from the yt-dlp info dict."""
    expected_path = tmp_path / "video.mp4"
    expected_path.write_bytes(b"x" * 2048)

    captured_opts: dict = {}

    def factory(opts):
        captured_opts.update(opts)
        fake_ydl = MagicMock()
        fake_ydl.__enter__.return_value = fake_ydl

        def fake_extract_info(url, download):  # noqa: ARG001
            for hook in captured_opts["progress_hooks"]:
                hook({"status": "finished", "filename": str(expected_path)})
            return {"ext": "mp4", "height": 1080}

        fake_ydl.extract_info.side_effect = fake_extract_info
        return fake_ydl

    with patch("yt_dlp.YoutubeDL", side_effect=factory):
        result = run_download(
            url="https://example.com/video",
            output_dir=str(tmp_path),
        )

    assert result.path == str(expected_path)
    assert result.media_format == "mp4"
    assert result.resolution_height == 1080
    assert result.file_size == 2048


def test_run_download_falls_back_to_info_filesize_when_file_missing(tmp_path: Path) -> None:
    """If the output file can't be stat'd, fall back to yt-dlp's reported filesize."""
    expected_path = tmp_path / "missing.mp4"

    captured_opts: dict = {}

    def factory(opts):
        captured_opts.update(opts)
        fake_ydl = MagicMock()
        fake_ydl.__enter__.return_value = fake_ydl

        def fake_extract_info(url, download):  # noqa: ARG001
            for hook in captured_opts["progress_hooks"]:
                hook({"status": "finished", "filename": str(expected_path)})
            return {"ext": "webm", "height": 720, "filesize": 4096}

        fake_ydl.extract_info.side_effect = fake_extract_info
        return fake_ydl

    with patch("yt_dlp.YoutubeDL", side_effect=factory):
        result = run_download(
            url="https://example.com/video",
            output_dir=str(tmp_path),
        )

    assert result.path == str(expected_path)
    assert result.media_format == "webm"
    assert result.resolution_height == 720
    assert result.file_size == 4096


def test_metadata_uses_short_side(tmp_path: Path) -> None:
    from app.services.downloader import _extract_file_metadata

    _, _, height = _extract_file_metadata({"ext": "mp4", "width": 1080, "height": 1920}, "")
    assert height == 1080


def _captured_opts(monkeypatch, tmp_path: Path, **kwargs) -> dict:
    captured: dict = {}

    def factory(opts):
        captured.update(opts)
        ydl = MagicMock()
        ydl.__enter__.return_value = ydl
        ydl.extract_info.return_value = {"ext": "mp4", "height": 720}
        return ydl

    monkeypatch.setattr("yt_dlp.YoutubeDL", factory)
    run_download(url="https://example.com/v", output_dir=str(tmp_path), **kwargs)
    return captured


def test_run_download_exact_ids_win(monkeypatch, tmp_path: Path) -> None:
    opts = _captured_opts(
        monkeypatch, tmp_path, video_format_id="137", audio_format_id="140", quality_cap="720"
    )
    assert opts["format"] == "137+140"
    assert "format_sort" not in opts


def test_run_download_uses_cap(monkeypatch, tmp_path: Path) -> None:
    opts = _captured_opts(monkeypatch, tmp_path, quality_cap="720")
    assert opts["format"] == "bv*+ba/b"
    assert opts["format_sort"] == ["res:720"]


def test_run_download_no_cap_no_bitrate_unchanged(monkeypatch, tmp_path: Path) -> None:
    opts = _captured_opts(monkeypatch, tmp_path)
    assert "format" not in opts and "format_sort" not in opts


def test_output_guard_blocks_template_that_escapes_via_fallback(tmp_path: Path) -> None:
    import yt_dlp

    from app.services.downloader import output_dir_guard

    info = {
        "id": "x",
        "title": "t",
        "ext": "mp4",
        "extractor": "generic",
        "extractor_key": "Generic",
        "webpage_url": "https://x",
        "formats": [
            {
                "format_id": "f",
                "url": "https://x/f",
                "ext": "mp4",
                "vcodec": "avc1",
                "acodec": "mp4a",
                "protocol": "https",
            }
        ],
    }

    def run(template: str) -> None:
        guard = output_dir_guard(str(tmp_path))
        opts = {
            "quiet": True,
            "skip_download": True,
            "outtmpl": str(tmp_path / template),
            "match_filter": guard,
        }
        with yt_dlp.YoutubeDL(opts) as ydl:
            guard.ydl = ydl
            ydl.process_ie_result(dict(info), download=True)

    run("%(title)s.%(ext)s")  # inside: fine
    with pytest.raises(ValueError, match="downloads folder"):
        run("%(nope|..)s/%(nope|..)s/x.%(ext)s")


def test_run_download_guards_relative_templates_only(monkeypatch, tmp_path: Path) -> None:
    assert "match_filter" in _captured_opts(
        monkeypatch, tmp_path, output_template="a/%(title)s.%(ext)s"
    )
    assert "match_filter" in _captured_opts(monkeypatch, tmp_path)
    abs_t = str(tmp_path / "x.%(ext)s")
    assert "match_filter" not in _captured_opts(monkeypatch, tmp_path, output_template=abs_t)
