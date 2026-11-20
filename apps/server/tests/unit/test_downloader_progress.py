"""Unit tests for ``app.services.downloader`` progress and cancellation."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.services.downloader import (
    DownloadCancelled,
    DownloadResult,
    YtdlpProgress,
    parse_percent,
    run_download,
)

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


def _wire(ydl: MagicMock, download_fn) -> None:
    """Route a fake download through the call shape ``run_download`` uses.

    Both the default layout and a custom template resolve info first
    (``extract_info(download=False)``) and then download with ``process_ie_result``.
    """

    def extract(url, download=True, **_kwargs):
        if download:
            return download_fn(url, download)
        return {"id": "v", "title": "t", "channel": "c"}

    ydl.extract_info.side_effect = extract
    ydl.process_ie_result.side_effect = lambda _info, download=True: download_fn("", download)


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

        _wire(fake_ydl, fake_extract_info)
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

        _wire(fake_ydl, fake_extract_info)
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

        _wire(fake_ydl, fake_extract_info)
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

        _wire(fake_ydl, fake_extract_info)
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

        _wire(fake_ydl, fake_extract_info)
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

        _wire(fake_ydl, fake_extract_info)
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

        _wire(fake_ydl, fake_extract_info)
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


def _captured_opts(
    monkeypatch, tmp_path: Path, info: dict | None = None, hook_files=(), **kwargs
) -> tuple[dict, DownloadResult]:
    captured: dict = {}

    def factory(opts):
        captured.update(opts)
        ydl = MagicMock()
        ydl.__enter__.return_value = ydl

        def extract(*_a, **_k):
            for f in hook_files:
                opts["progress_hooks"][0]({"status": "finished", "filename": f})
            return info if info is not None else {"ext": "mp4", "height": 720}

        _wire(ydl, extract)
        return ydl

    monkeypatch.setattr("yt_dlp.YoutubeDL", factory)
    result = run_download(url="https://example.com/v", output_dir=str(tmp_path), **kwargs)
    return captured, result


def test_run_download_exact_ids_win(monkeypatch, tmp_path: Path) -> None:
    opts, _ = _captured_opts(
        monkeypatch, tmp_path, video_format_id="137", audio_format_id="140", quality_cap="720"
    )
    assert opts["format"] == "137+140"
    assert "format_sort" not in opts
    assert "merge_output_format" not in opts


def test_run_download_hdr_sort(monkeypatch, tmp_path: Path) -> None:
    opts, _ = _captured_opts(monkeypatch, tmp_path, quality_cap="best", hdr=True)
    assert opts["format_sort"] == ["res", "hdr", "vcodec:h264", "acodec:aac"]


def test_run_download_exact_ids_ignore_hdr(monkeypatch, tmp_path: Path) -> None:
    opts, _ = _captured_opts(
        monkeypatch, tmp_path, video_format_id="137", audio_format_id="140", hdr=True
    )
    assert "format_sort" not in opts and "merge_output_format" not in opts


def test_run_download_uses_cap(monkeypatch, tmp_path: Path) -> None:
    opts, _ = _captured_opts(monkeypatch, tmp_path, quality_cap="720")
    assert opts["format"] == "bv*+ba/b"
    assert opts["format_sort"] == ["res:720", "hdr:sdr", "vcodec:h264", "acodec:aac"]
    assert opts["merge_output_format"] == "mp4"


def test_run_download_no_cap_is_best(monkeypatch, tmp_path: Path) -> None:
    opts, _ = _captured_opts(monkeypatch, tmp_path)
    assert opts["format"] == "bv*+ba/b"
    assert opts["format_sort"] == ["res", "hdr:sdr", "vcodec:h264", "acodec:aac"]
    assert opts["merge_output_format"] == "mp4"


def test_run_download_audio_cap_no_merge(monkeypatch, tmp_path: Path) -> None:
    opts, _ = _captured_opts(monkeypatch, tmp_path, quality_cap="audio")
    assert opts["format"] == "ba/b"
    assert "merge_output_format" not in opts


def test_run_download_path_is_merged_file(monkeypatch, tmp_path: Path) -> None:
    merged = tmp_path / "t.mp4"
    merged.write_bytes(b"x" * 10)
    _, result = _captured_opts(
        monkeypatch,
        tmp_path,
        info={"ext": "mp4", "requested_downloads": [{"filepath": str(merged)}]},
        hook_files=[str(tmp_path / "t.f299.mp4"), str(tmp_path / "t.f140.m4a")],
    )
    assert result.path == str(merged)
    assert result.file_size == 10


def test_run_download_path_falls_back_to_hook(monkeypatch, tmp_path: Path) -> None:
    _, result = _captured_opts(
        monkeypatch, tmp_path, info={"ext": "mp4"}, hook_files=[str(tmp_path / "t.mp4")]
    )
    assert result.path == str(tmp_path / "t.mp4")


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


def test_run_download_always_guards(monkeypatch, tmp_path: Path) -> None:
    assert (
        "match_filter"
        in _captured_opts(monkeypatch, tmp_path, output_template="a/%(title)s.%(ext)s")[0]
    )
    assert "match_filter" in _captured_opts(monkeypatch, tmp_path)[0]
    abs_t = str(tmp_path / "x.%(ext)s")
    assert "match_filter" in _captured_opts(monkeypatch, tmp_path, output_template=abs_t)[0]


def _real_download_through_guard(monkeypatch, tmp_path: Path, output_template: str | None) -> None:
    """Run ``run_download`` with a real YoutubeDL that resolves the filename but skips the fetch."""
    import yt_dlp

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
    real_init = yt_dlp.YoutubeDL.__init__

    def init(self, params=None, *args, **kwargs):
        real_init(self, {**(params or {}), "skip_download": True}, *args, **kwargs)

    def extract_info(self, url, download=True, **_kwargs):
        return self.process_ie_result(dict(info), download=download)

    monkeypatch.setattr(yt_dlp.YoutubeDL, "__init__", init)
    monkeypatch.setattr(yt_dlp.YoutubeDL, "extract_info", extract_info)
    run_download(url="https://x", output_dir=str(tmp_path), output_template=output_template)


def test_run_download_refuses_absolute_template_outside_downloads(
    monkeypatch, tmp_path: Path
) -> None:
    """Owner decision: absolute templates are no longer exempt from the downloads-folder guard."""
    downloads = tmp_path / "downloads"
    _real_download_through_guard(monkeypatch, downloads, None)  # default template: allowed
    with pytest.raises(ValueError, match="downloads folder"):
        _real_download_through_guard(
            monkeypatch, downloads, str(tmp_path / "elsewhere" / "x.%(ext)s")
        )
