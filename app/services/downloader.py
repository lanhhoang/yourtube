"""yt-dlp integration: format parsing, progress hooks, and download entrypoint.

The module exposes helpers for the format picker UI (``extract_info``,
``normalize_formats``, ``build_format_selector``) and the actual
download driver (``run_download`` plus the ``YtdlpProgress`` hook and
``DownloadCancelled`` exception).
"""

from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

from app.schemas import FormatInfo


class DownloadCancelled(Exception):  # noqa: N818 - name fixed by plan contract
    """Raised inside the progress hook when cancellation is requested."""


# Type alias for the yt-dlp progress hook. yt-dlp passes a dict to each
# ``progress_hooks`` entry; the schema mirrors what the project consumes.
ProgressHook = Callable[[dict[str, Any]], None]


class YtdlpProgress:
    """Callback matching yt-dlp's progress hook interface.

    The hook stores the latest normalized percent in ``percent`` and the
    final output path in ``filename``. When ``cancel_requested`` is
    supplied and returns ``True``, calling the hook raises
    :class:`DownloadCancelled`.
    """

    def __init__(
        self,
        cancel_requested: Callable[[], bool] | None = None,
        on_progress: Callable[[float], None] | None = None,
    ) -> None:
        self.cancel_requested = cancel_requested
        self.on_progress = on_progress
        self.percent: float | None = None
        self.filename: str | None = None

    def __call__(self, d: dict[str, Any]) -> None:
        if self.cancel_requested is not None and self.cancel_requested():
            raise DownloadCancelled("cancelled by user")
        percent = parse_percent(d.get("_percent_str"))
        if percent is not None:
            self.percent = percent
            if self.on_progress is not None:
                self.on_progress(percent)
        if d.get("status") == "finished" and d.get("filename"):
            self.filename = str(d["filename"])


def _safe_int(value: Any) -> int | None:
    """Coerce ``value`` to ``int`` if possible, else return ``None``."""
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _safe_float(value: Any) -> float | None:
    """Coerce ``value`` to ``float`` if possible, else return ``None``."""
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_str(value: Any) -> str | None:
    """Return ``value`` only if it's a non-empty string, else ``None``."""
    if value is None:
        return None
    if not isinstance(value, str):
        return None
    return value or None


def _format_codec(value: Any) -> str | None:
    """Return the codec string unless it's the literal ``"none"``."""
    s = _safe_str(value)
    if s is None:
        return None
    if s == "none":
        return s
    return s


def normalize_formats(info: dict) -> list[FormatInfo]:
    """Convert a yt-dlp info_dict to a list of :class:`FormatInfo`.

    Entries missing a ``format_id`` are silently skipped because the UI
    can't reference them in a format-selector expression.
    """
    raw_formats = info.get("formats") or []
    out: list[FormatInfo] = []
    for raw in raw_formats:
        format_id = _safe_str(raw.get("format_id"))
        if format_id is None:
            continue
        out.append(
            FormatInfo(
                format_id=format_id,
                ext=_safe_str(raw.get("ext")) or "",
                resolution=_safe_str(raw.get("resolution")),
                height=_safe_int(raw.get("height")),
                width=_safe_int(raw.get("width")),
                fps=_safe_float(raw.get("fps")),
                vcodec=_format_codec(raw.get("vcodec")),
                acodec=_format_codec(raw.get("acodec")),
                abr=_safe_float(raw.get("abr")),
                vbr=_safe_float(raw.get("vbr")),
                filesize=_safe_int(raw.get("filesize")),
                tbr=_safe_float(raw.get("tbr")),
                format_note=_safe_str(raw.get("format_note")),
                container=_safe_str(raw.get("container")),
            )
        )
    return out


def extract_info(
    url: str,
    *,
    proxy: str | None = None,
    cookies_file: str | None = None,
) -> dict:
    """Call ``yt_dlp.YoutubeDL.extract_info`` for ``url`` and return the dict.

    Pass-through wrapper; the heavy lifting is delegated to yt-dlp. Kept
    as a function so tests can monkeypatch it without reaching into
    yt-dlp internals.
    """
    import yt_dlp  # local import to keep module import cheap

    ydl_opts: dict[str, Any] = {"quiet": True, "skip_download": True}
    if proxy:
        ydl_opts["proxy"] = proxy
    if cookies_file:
        ydl_opts["cookiefile"] = cookies_file
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        return ydl.extract_info(url, download=False)


_PERCENT_RE = re.compile(r"(-?[0-9]+(?:\.[0-9]+)?)\s*%")


def parse_percent(value: Any) -> float | None:
    """Parse yt-dlp's ``_percent_str`` (``"  45.2% "``) into a ``float`` 0-100."""
    if value is None:
        return None
    match = _PERCENT_RE.search(str(value))
    if not match:
        return None
    try:
        pct = float(match.group(1))
    except ValueError:
        return None
    return max(0.0, min(100.0, pct))


def build_format_selector(
    video_id: str | None,
    audio_id: str | None,
    *,
    audio_bitrate: str | None = None,
) -> str:
    """Return a yt-dlp format selector expression for the chosen ids."""
    if video_id and audio_id:
        base = f"{video_id}+{audio_id}"
        if audio_bitrate:
            return f"{base}/bestaudio[abr<={audio_bitrate}]/bestaudio"
        return base
    if video_id:
        return video_id
    if audio_id:
        return audio_id
    return "best"


def _format_selector(
    video_format_id: str | None,
    audio_format_id: str | None,
    *,
    audio_bitrate: str | None = None,
) -> str | None:
    """Return a yt-dlp ``format`` expression, or ``None`` to let yt-dlp pick."""
    if not video_format_id and not audio_format_id:
        return None
    return build_format_selector(video_format_id, audio_format_id, audio_bitrate=audio_bitrate)


def _output_template(template: str | None, output_dir: str) -> str:
    """Return the yt-dlp ``outtmpl`` expression, defaulting to ``output_dir/%(title)s.%(ext)s``."""
    if template:
        return template
    return str(Path(output_dir) / "%(title)s.%(ext)s")


def run_download(
    url: str,
    video_format_id: str | None = None,
    audio_format_id: str | None = None,
    output_template: str | None = None,
    output_dir: str = "",
    audio_bitrate: str | None = None,
    proxy: str | None = None,
    cookies_file: str | None = None,
    subtitles: bool = False,
    progress_hook: YtdlpProgress | None = None,
) -> str:
    """Run yt-dlp and return the output file path.

    Raises ``DownloadCancelled`` if the progress hook signals cancellation.
    Callers should map yt-dlp errors through ``friendly_ytdlp_error()``.
    """
    import yt_dlp  # local import to keep module import cheap

    fmt = _format_selector(video_format_id, audio_format_id, audio_bitrate=audio_bitrate)
    ydl_opts: dict[str, Any] = {
        "outtmpl": _output_template(output_template, output_dir),
        "quiet": True,
        "noprogress": True,
    }
    if fmt:
        ydl_opts["format"] = fmt
    if proxy:
        ydl_opts["proxy"] = proxy
    if cookies_file:
        ydl_opts["cookiefile"] = cookies_file
    if subtitles:
        ydl_opts["writesubtitles"] = True
    captured_path: dict[str, str | None] = {"path": None}

    def _wrapped(d: dict[str, Any]) -> None:
        if d.get("status") == "finished" and d.get("filename"):
            captured_path["path"] = str(d["filename"])
        if progress_hook is not None:
            progress_hook(d)

    ydl_opts["progress_hooks"] = [_wrapped]

    Path(output_dir).mkdir(parents=True, exist_ok=True)

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])

    return captured_path["path"] or ""
