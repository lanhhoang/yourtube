"""Quality caps: judge video quality by the short side and map a cap to yt-dlp options.

A cap is a numeric short-side limit (``"1080"``), ``"best"`` or ``"audio"``.
Numeric caps become ``format="bv*+ba/b"`` plus ``format_sort=["res:N"]``.
yt-dlp's ``res`` sort field is ``min(height, width)`` (``yt_dlp/utils/_utils.py``),
so ``res:N`` prefers the largest short side <= N and never fails: when a video
has nothing <= N it takes the closest quality above. A ``ba[abr<=N]`` filter was
rejected for the audio bitrate because it picks the *worst* matching stream;
``abr:N`` in ``format_sort`` picks the closest. The bitrate must be bare digits:
yt-dlp misreads ``abr:192K``. All checked offline against yt-dlp 2026.10.26.

If a future yt-dlp breaks that, fall back to ``bv*[height<=N]+ba/b``.
"""

from __future__ import annotations

from typing import get_args

from app.schemas import FormatInfo, QualityCap

QUALITY_CAPS: tuple[QualityCap, ...] = get_args(QualityCap.__value__)


def short_side(width: int | None, height: int | None) -> int | None:
    values = [v for v in (width, height) if v]
    return min(values) if values else None


def best_short_side(formats: list[FormatInfo]) -> int | None:
    sides = [
        s
        for f in formats
        if f.stream_kind in ("video", "muxed")
        if (s := short_side(f.width, f.height)) is not None
    ]
    return max(sides) if sides else None


def is_below_cap(cap: QualityCap, best: int | None) -> bool:
    return cap.isdigit() and best is not None and best < int(cap)


def bitrate_kbps(audio_bitrate: str | None) -> int | None:
    digits = (audio_bitrate or "").strip().lower().removesuffix("k")
    return int(digits) if digits.isdigit() else None


def cap_format_options(
    cap: QualityCap | None, audio_bitrate: str | None = None
) -> tuple[str | None, list[str] | None]:
    kbps = bitrate_kbps(audio_bitrate)
    abr = [f"abr:{kbps}"] if kbps else []
    if cap == "audio":
        return "ba/b", abr or None
    if cap is None or cap == "best":
        return None, abr or None
    return "bv*+ba/b", [f"res:{cap}", *abr]
