"""Unit tests for the yt-dlp options builder introduced in Phase 5.

``build_ytdlp_options`` centralises yt-dlp configuration so both
``extract_info`` (info lookup) and ``run_download`` (actual download)
pin the same JS runtime and YouTube extractor args. Without an
explicit ``js_runtimes`` entry, yt-dlp cannot solve YouTube's JS
challenges on a host that ships no Node.js by default.
"""

from __future__ import annotations

from pathlib import Path

from yt_dlp import YoutubeDL

from app.services.downloader import build_ytdlp_options, resolve_output_template


def test_build_ytdlp_options_sets_explicit_node_runtime(tmp_path) -> None:
    options = build_ytdlp_options(
        skip_download=True,
        output_dir=str(tmp_path),
        js_runtime="node",
    )

    assert options["extractor_args"]["youtube"]["player_client"] == ["default"]
    assert options["js_runtimes"] == {"node": {"path": "node"}}


def test_build_ytdlp_options_emits_output_template_only_for_downloads(tmp_path) -> None:
    info_options = build_ytdlp_options(
        skip_download=True,
        output_dir=str(tmp_path),
        js_runtime="node",
    )
    download_options = build_ytdlp_options(
        skip_download=False,
        output_dir=str(tmp_path),
        js_runtime="node",
    )

    assert "outtmpl" not in info_options
    assert download_options["outtmpl"].endswith("%(title)s.%(ext)s")


def test_build_ytdlp_options_propagates_proxy_cookies_and_subtitles(tmp_path) -> None:
    options = build_ytdlp_options(
        skip_download=False,
        output_dir=str(tmp_path),
        format_selector="best",
        proxy="http://proxy:8080",
        cookies_file="/tmp/cookies.txt",
        subtitles=True,
        js_runtime="node",
    )

    assert options["format"] == "best"
    assert options["proxy"] == "http://proxy:8080"
    assert options["cookiefile"] == "/tmp/cookies.txt"
    assert options["writesubtitles"] is True


def test_build_ytdlp_options_is_accepted_by_ytdlp(tmp_path) -> None:
    options = build_ytdlp_options(
        skip_download=True,
        output_dir=str(tmp_path),
        js_runtime="node",
    )

    ydl = YoutubeDL(options)

    assert ydl.params["js_runtimes"] == {"node": {"path": "node"}}


def test_resolve_output_template_uses_downloads_dir_for_default_template(tmp_path: Path) -> None:
    resolved = resolve_output_template(None, tmp_path)
    assert resolved == str(tmp_path / "%(title)s.%(ext)s")


def test_resolve_output_template_joins_relative_template_to_output_dir(tmp_path: Path) -> None:
    resolved = resolve_output_template("%(title)s.%(ext)s", tmp_path)
    assert resolved == str(tmp_path / "%(title)s.%(ext)s")


def test_resolve_output_template_keeps_absolute_template_absolute(tmp_path: Path) -> None:
    absolute = tmp_path / "nested" / "%(title)s.%(ext)s"
    resolved = resolve_output_template(str(absolute), tmp_path)
    assert resolved == str(absolute)


def test_build_ytdlp_options_uses_resolved_template_for_downloads(tmp_path: Path) -> None:
    options = build_ytdlp_options(
        skip_download=False,
        output_dir=str(tmp_path),
        output_template="%(title)s.%(ext)s",
        subtitles=True,
        js_runtime="node",
    )

    assert options["outtmpl"] == str(tmp_path / "%(title)s.%(ext)s")
    assert options["writesubtitles"] is True


def test_build_ytdlp_options_prefers_srt_english_and_auto_subtitles(tmp_path: Path) -> None:
    options = build_ytdlp_options(
        skip_download=False,
        output_dir=str(tmp_path),
        subtitles=True,
        js_runtime="node",
    )

    assert options["writesubtitles"] is True
    assert options["writeautomaticsub"] is True
    assert options["subtitlesformat"] == "srt/best"
    assert options["subtitleslangs"] == ["en.*", "en", ".*"]
