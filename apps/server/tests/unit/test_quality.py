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
    assert cap_format_options(None) == (None, None)
    assert cap_format_options("best") == (None, None)
    assert cap_format_options("720") == ("bv*+ba/b", ["res:720"])
    assert cap_format_options("720", "192K") == ("bv*+ba/b", ["res:720", "abr:192"])
    assert cap_format_options("audio") == ("ba/b", None)
    assert cap_format_options("audio", "128") == ("ba/b", ["abr:128"])
    assert cap_format_options(None, "128k") == (None, ["abr:128"])


def _fmt(
    fid: str,
    w: int | None,
    h: int | None,
    v: str,
    a: str,
    ext: str = "mp4",
    abr: float | None = None,
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
    }


def _select(formats: list[dict], cap: Any, bitrate: str | None = None) -> str:
    info = {
        "id": "x",
        "title": "t",
        "extractor": "generic",
        "extractor_key": "Generic",
        "webpage_url": "https://x",
        "formats": formats,
    }
    fmt, sort = cap_format_options(cap, bitrate)
    opts: dict[str, Any] = {"quiet": True}
    if fmt:
        opts["format"] = fmt
    if sort:
        opts["format_sort"] = sort
    with yt_dlp.YoutubeDL(opts) as ydl:
        return ydl.process_ie_result(info, download=False)["format_id"]


A1 = _fmt("a1", None, None, "none", "mp4a", "m4a", 128)


def test_cap_selects_vertical_1080_offline() -> None:
    formats = [
        _fmt("v1080", 1080, 1920, "avc1", "none"),
        _fmt("v1440", 1440, 2560, "avc1", "none"),
        A1,
    ]
    assert _select(formats, "1080") == "v1080+a1"


def test_cap_falls_back_above_when_nothing_below() -> None:
    assert _select([_fmt("v720", 1280, 720, "avc1", "none"), A1], "480") == "v720+a1"


def test_cap_with_bitrate_offline() -> None:
    formats = [
        _fmt("v720", 1280, 720, "avc1", "none"),
        _fmt("v1080", 1920, 1080, "avc1", "none"),
        _fmt("a50", None, None, "none", "opus", "webm", 50),
        _fmt("a128", None, None, "none", "mp4a", "m4a", 128),
        _fmt("a160", None, None, "none", "opus", "webm", 160),
    ]
    assert _select(formats, "720", "128") == "v720+a128"


def test_audio_bitrate_validator() -> None:
    from app.schemas import JobCreate

    assert JobCreate(url="https://x", audio_bitrate="192K").audio_bitrate == "192K"
    assert JobCreate(url="https://x", audio_bitrate="").audio_bitrate is None
    with pytest.raises(ValidationError):
        JobCreate(url="https://x", audio_bitrate="loud")


def test_old_ui_payload_accepts_free_form_bitrate() -> None:
    # The old HTML routes build DownloadCreate without catching errors; they must never 500.
    assert DownloadCreate(url="https://x", audio_bitrate="192 kbps").audio_bitrate == "192 kbps"
    assert cap_format_options(None, "192 kbps") == (None, None)


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
