"""Unit tests for ``app.services.downloader`` format helpers.

These tests feed synthetic yt-dlp ``info_dict`` payloads into the parser
and assert that ``normalize_formats`` produces the right ``FormatInfo``
shapes for each variant, and that ``build_format_selector`` emits the
correct yt-dlp format selector expression.
"""

from __future__ import annotations

from app.schemas import FormatInfo
from app.services.downloader import (
    build_format_selector,
    build_stream_picker_payload,
    infer_expected_container,
    normalize_formats,
)


def _make_info(*formats: dict) -> dict:
    """Build a minimal yt-dlp info_dict around the supplied formats."""
    return {
        "id": "abc123",
        "title": "Sample",
        "formats": list(formats),
    }


def test_normalize_combined_format() -> None:
    """A format with both video and audio codecs is preserved as-is."""
    info = _make_info(
        {
            "format_id": "137+140",
            "ext": "mp4",
            "vcodec": "avc1.640028",
            "acodec": "mp4a.40.2",
            "height": 1080,
            "width": 1920,
            "fps": 30.0,
            "tbr": 5000.0,
            "filesize": 123_456_789,
        }
    )
    formats = normalize_formats(info)
    assert len(formats) == 1
    f = formats[0]
    assert isinstance(f, FormatInfo)
    assert f.format_id == "137+140"
    assert f.ext == "mp4"
    assert f.vcodec == "avc1.640028"
    assert f.acodec == "mp4a.40.2"
    assert f.height == 1080
    assert f.width == 1920
    assert f.fps == 30.0
    assert f.filesize == 123_456_789
    assert f.tbr == 5000.0


def test_normalize_video_only_format() -> None:
    """A video-only format has acodec ``"none"`` and is still normalised."""
    info = _make_info(
        {
            "format_id": "401",
            "ext": "mp4",
            "vcodec": "av01.0.08M.08",
            "acodec": "none",
            "height": 2160,
            "fps": 60.0,
        }
    )
    formats = normalize_formats(info)
    assert len(formats) == 1
    f = formats[0]
    assert f.vcodec == "av01.0.08M.08"
    assert f.acodec == "none"
    assert f.height == 2160
    assert f.fps == 60.0


def test_normalize_audio_only_format() -> None:
    """An audio-only format has vcodec ``"none"`` and abr set, no resolution."""
    info = _make_info(
        {
            "format_id": "140",
            "ext": "m4a",
            "vcodec": "none",
            "acodec": "mp4a.40.2",
            "abr": 128.0,
            "tbr": 128.0,
        }
    )
    formats = normalize_formats(info)
    assert len(formats) == 1
    f = formats[0]
    assert f.vcodec == "none"
    assert f.acodec == "mp4a.40.2"
    assert f.height is None
    assert f.width is None
    assert f.abr == 128.0


def test_normalize_handles_missing_codec_metadata() -> None:
    """Missing codec keys are tolerated and represented as ``None``."""
    info = _make_info(
        {
            "format_id": "999",
            "ext": "webm",
        }
    )
    formats = normalize_formats(info)
    assert len(formats) == 1
    f = formats[0]
    assert f.format_id == "999"
    assert f.ext == "webm"
    assert f.vcodec is None
    assert f.acodec is None
    assert f.height is None
    assert f.filesize is None


def test_normalize_skips_entries_without_format_id() -> None:
    """Format entries missing a ``format_id`` are silently dropped."""
    info = _make_info(
        {"format_id": "1", "ext": "mp4"},
        {"ext": "mp4"},  # missing format_id
    )
    formats = normalize_formats(info)
    assert len(formats) == 1
    assert formats[0].format_id == "1"


def test_normalize_combined_format_defaults_stream_kind_to_muxed() -> None:
    """A combined format with both codecs defaults to ``stream_kind="muxed"``."""
    info = _make_info(
        {
            "format_id": "137+140",
            "ext": "mp4",
            "vcodec": "avc1.640028",
            "acodec": "mp4a.40.2",
        }
    )

    f = normalize_formats(info)[0]

    assert f.stream_kind == "muxed"
    assert f.audio_channels is None


def test_normalize_video_only_format_sets_stream_kind() -> None:
    """A video-only format with ``acodec="none"`` classifies as ``"video"``."""
    info = _make_info(
        {
            "format_id": "401",
            "ext": "mp4",
            "vcodec": "av01.0.08M.08",
            "acodec": "none",
            "height": 2160,
        }
    )

    f = normalize_formats(info)[0]

    assert f.stream_kind == "video"


def test_normalize_audio_only_format_sets_stream_kind_and_channels() -> None:
    """An audio-only format classifies as ``"audio"`` and preserves channel count."""
    info = _make_info(
        {
            "format_id": "251",
            "ext": "webm",
            "vcodec": "none",
            "acodec": "opus",
            "abr": 160.0,
            "audio_channels": 2,
        }
    )

    f = normalize_formats(info)[0]

    assert f.stream_kind == "audio"
    assert f.audio_channels == 2


def test_normalize_missing_codecs_falls_back_to_muxed() -> None:
    """A format with no codec metadata falls back to ``"muxed"``."""
    info = _make_info(
        {
            "format_id": "999",
            "ext": "webm",
        }
    )

    f = normalize_formats(info)[0]

    assert f.stream_kind == "muxed"
    assert f.audio_channels is None


def test_build_format_selector_video_only() -> None:
    """A single video id becomes ``<id>``."""
    assert build_format_selector("401", None) == "401"


def test_build_format_selector_audio_only() -> None:
    """A single audio id becomes ``<id>``."""
    assert build_format_selector(None, "140") == "140"


def test_build_format_selector_combined() -> None:
    """Video and audio ids combine as ``<video>+<audio>``."""
    assert build_format_selector("401", "140") == "401+140"


def test_build_format_selector_best_default() -> None:
    """No ids -> yt-dlp's ``best`` placeholder."""
    assert build_format_selector(None, None) == "best"


def test_build_format_selector_with_audio_bitrate() -> None:
    """An audio bitrate emits ``<video>+<audio>/bestaudio[abr<=<bitrate>]``."""
    selector = build_format_selector("401", "140", audio_bitrate="128")
    assert "401+140" in selector
    assert "bestaudio" in selector
    assert "abr<=128" in selector


def test_infer_expected_container_prefers_mp4_for_avc_and_aac() -> None:
    video = FormatInfo(
        format_id="137",
        ext="mp4",
        container="mp4_dash",
        vcodec="avc1.640028",
        acodec="none",
    )
    audio = FormatInfo(
        format_id="140",
        ext="m4a",
        container="m4a_dash",
        vcodec="none",
        acodec="mp4a.40.2",
    )

    assert infer_expected_container(video, audio) == "mp4"


def test_infer_expected_container_falls_back_to_mkv_for_webm_plus_m4a() -> None:
    video = FormatInfo(
        format_id="400",
        ext="webm",
        container="webm_dash",
        vcodec="vp9",
        acodec="none",
    )
    audio = FormatInfo(
        format_id="140",
        ext="m4a",
        container="m4a_dash",
        vcodec="none",
        acodec="mp4a.40.2",
    )

    assert infer_expected_container(video, audio) == "mkv"


def test_infer_expected_container_returns_audio_ext_for_audio_only_stream() -> None:
    audio = FormatInfo(
        format_id="251",
        ext="webm",
        container="webm_dash",
        vcodec="none",
        acodec="opus",
    )

    assert infer_expected_container(None, audio) == "webm"


def test_infer_expected_container_returns_unknown_when_no_streams_are_selected() -> None:
    assert infer_expected_container(None, None) == "unknown"


def test_build_stream_picker_payload_groups_video_and_audio_rows() -> None:
    formats = [
        FormatInfo(
            format_id="401",
            ext="mp4",
            stream_kind="video",
            height=2160,
            resolution="2160p",
            vcodec="av01.0.08M.08",
            acodec="none",
            container="mp4_dash",
        ),
        FormatInfo(
            format_id="140",
            ext="m4a",
            stream_kind="audio",
            abr=128.0,
            audio_channels=2,
            vcodec="none",
            acodec="mp4a.40.2",
            container="m4a_dash",
        ),
        FormatInfo(
            format_id="18",
            ext="mp4",
            stream_kind="muxed",
            resolution="360p",
            vcodec="avc1.42001E",
            acodec="mp4a.40.2",
            container="mp4",
        ),
    ]

    payload = build_stream_picker_payload(formats)

    assert [row["format_id"] for row in payload["video_streams"]] == ["401"]
    assert [row["format_id"] for row in payload["audio_streams"]] == ["140"]
    assert payload["has_muxed_streams"] is True


def test_build_stream_picker_payload_serializes_expected_container_pairs() -> None:
    formats = [
        FormatInfo(
            format_id="137",
            ext="mp4",
            stream_kind="video",
            resolution="1080p",
            vcodec="avc1.640028",
            acodec="none",
            container="mp4_dash",
        ),
        FormatInfo(
            format_id="140",
            ext="m4a",
            stream_kind="audio",
            abr=128.0,
            audio_channels=2,
            vcodec="none",
            acodec="mp4a.40.2",
            container="m4a_dash",
        ),
    ]

    payload = build_stream_picker_payload(formats)

    assert payload["expected_container_by_pair"]["|"] == "unknown"
    assert payload["expected_container_by_pair"]["137|"] == "mp4"
    assert payload["expected_container_by_pair"]["|140"] == "m4a"
    assert payload["expected_container_by_pair"]["137|140"] == "mp4"
