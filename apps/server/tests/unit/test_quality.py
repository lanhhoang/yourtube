from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import yt_dlp
from pydantic import ValidationError

from app.models import Download
from app.schemas import DownloadCreate, FormatInfo, JobOut
from app.services.quality import (
    best_short_side,
    bitrate_kbps,
    cap_format_options,
    is_below_cap,
    short_side,
)

CASES = json.loads((Path(__file__).parents[1] / "fixtures" / "quality_cases.json").read_text())


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["name"])
def test_shared_quality_cases(case: dict[str, Any]) -> None:
    formats = [
        FormatInfo(
            format_id=str(i),
            ext="mp4",
            stream_kind=f["kind"],
            width=f["width"],
            height=f["height"],
        )
        for i, f in enumerate(case["formats"])
    ]
    assert best_short_side(formats) == case["best_short_side"]
    assert is_below_cap(case["cap"], case["best_short_side"]) is case["below_cap"]


def test_short_side() -> None:
    assert short_side(1080, 1920) == 1080
    assert short_side(None, 720) == 720
    assert short_side(None, None) is None


def test_bitrate_kbps() -> None:
    assert [bitrate_kbps(v) for v in ("192", "192k", "192K", "", None)] == [
        192,
        192,
        192,
        None,
        None,
    ]


def test_cap_format_options() -> None:
    sort = ["hdr:sdr", "vcodec:h264", "acodec:aac"]
    assert cap_format_options(None) == ("bv*+ba/b", ["res", *sort], "mp4")
    assert cap_format_options("best") == ("bv*+ba/b", ["res", *sort], "mp4")
    assert cap_format_options("720") == ("bv*+ba/b", ["res:720", *sort], "mp4")
    assert cap_format_options("720", "192K") == ("bv*+ba/b", ["res:720", *sort, "abr:192"], "mp4")
    assert cap_format_options("best", "128k") == ("bv*+ba/b", ["res", *sort, "abr:128"], "mp4")
    assert cap_format_options("audio") == ("ba/b", None, None)
    assert cap_format_options("audio", "128") == ("ba/b", ["abr:128"], None)


def _fmt(
    fid: str,
    w: int | None,
    h: int | None,
    v: str,
    a: str,
    ext: str = "mp4",
    abr: float | None = None,
    dr: str | None = None,
) -> dict:
    return {
        "format_id": fid,
        "url": f"https://x/{fid}",
        "ext": ext,
        "width": w,
        "height": h,
        "vcodec": v,
        "acodec": a,
        "abr": abr,
        "protocol": "https",
        **({"dynamic_range": dr} if dr else {}),
    }


def _select(formats: list[dict], cap: Any, bitrate: str | None = None) -> tuple[str, str]:
    info = {
        "id": "x",
        "title": "t",
        "extractor": "generic",
        "extractor_key": "Generic",
        "webpage_url": "https://x",
        "formats": formats,
    }
    fmt, sort, merge = cap_format_options(cap, bitrate)
    opts: dict[str, Any] = {"quiet": True}
    if fmt:
        opts["format"] = fmt
    if sort:
        opts["format_sort"] = sort
    if merge:
        opts["merge_output_format"] = merge
    with yt_dlp.YoutubeDL(opts) as ydl:
        picked = ydl.process_ie_result(info, download=False)
    return picked["format_id"], picked["ext"]


A1 = _fmt("a1", None, None, "none", "mp4a", "m4a", 128)


def test_cap_selects_vertical_1080_offline() -> None:
    formats = [
        _fmt("v1080", 1080, 1920, "avc1", "none"),
        _fmt("v1440", 1440, 2560, "avc1", "none"),
        A1,
    ]
    assert _select(formats, "1080")[0] == "v1080+a1"


def test_cap_falls_back_above_when_nothing_below() -> None:
    assert _select([_fmt("v720", 1280, 720, "avc1", "none"), A1], "480")[0] == "v720+a1"


def test_cap_with_bitrate_offline() -> None:
    formats = [
        _fmt("v720", 1280, 720, "avc1", "none"),
        _fmt("v1080", 1920, 1080, "avc1", "none"),
        _fmt("a50", None, None, "none", "opus", "webm", 50),
        _fmt("a128", None, None, "none", "mp4a", "m4a", 128),
        _fmt("a160", None, None, "none", "opus", "webm", 160),
    ]
    assert _select(formats, "720", "128")[0] == "v720+a128"


HDR_SET = [
    _fmt("315", 3840, 2160, "vp9", "none", "webm", dr="SDR"),
    _fmt("701", 3840, 2160, "av01.0.13M.10.0.110.09.16.09.0", "none", "mp4", dr="HDR10"),
    _fmt("308", 2560, 1440, "vp9", "none", "webm", dr="SDR"),
    _fmt("299", 1920, 1080, "avc1.64002a", "none", "mp4", dr="SDR"),
    _fmt("303", 1920, 1080, "vp9", "none", "webm", dr="SDR"),
    _fmt("140", None, None, "none", "mp4a.40.2", "m4a", 129),
    _fmt("251", None, None, "none", "opus", "webm", 133),
]


def test_best_prefers_sdr_and_aac() -> None:
    assert _select(HDR_SET, "best") == ("315+140", "mp4")


def test_1440_takes_vp9_sdr() -> None:
    assert _select(HDR_SET, "1440") == ("308+140", "mp4")


def test_1080_prefers_h264() -> None:
    assert _select(HDR_SET, "1080") == ("299+140", "mp4")


def test_hdr_vp9_loses_to_sdr_av1() -> None:
    formats = [
        _fmt("337", 3840, 2160, "vp09.02.51.10.01.09.16.09.00", "none", "webm", dr="HDR10"),
        _fmt("401", 3840, 2160, "av01.0.12M.08", "none", "mp4", dr="SDR"),
        _fmt("140", None, None, "none", "mp4a.40.2", "m4a", 129),
    ]
    assert _select(formats, "best")[0] == "401+140"


def test_audio_bitrate_validator() -> None:
    from app.schemas import JobCreate

    assert JobCreate(url="https://x", audio_bitrate="192K").audio_bitrate == "192K"
    assert JobCreate(url="https://x", audio_bitrate="").audio_bitrate is None
    with pytest.raises(ValidationError):
        JobCreate(url="https://x", audio_bitrate="loud")


def test_stored_free_form_bitrate_is_tolerated() -> None:
    # Rows queued before the strict API may hold free-form bitrates; the worker must not crash.
    assert DownloadCreate(url="https://x", audio_bitrate="192 kbps").audio_bitrate == "192 kbps"
    assert cap_format_options(None, "192 kbps")[1] == [
        "res",
        "hdr:sdr",
        "vcodec:h264",
        "acodec:aac",
    ]


def test_media_kind_audio_for_audio_cap() -> None:
    def kind(**kw: Any) -> str:
        row = Download(url="https://x", status="queued", **kw)
        row.id = 1
        from datetime import datetime

        row.created_at = datetime.now()
        row.progress = 0.0
        return JobOut.from_row(row).media_kind

    assert kind(quality_cap="audio") == "audio"
    assert kind(quality_cap="audio", video_format_id="137") == "video"
    assert kind(quality_cap="720") == "video"
