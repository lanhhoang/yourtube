"""yt-dlp integration: format parsing, progress hooks, and download entrypoint.

The module exposes helpers for the format picker UI (``extract_info``,
``normalize_formats``, ``build_format_selector``) and the actual
download driver (``run_download`` plus the ``YtdlpProgress`` hook and
``DownloadCancelled`` exception).
"""

from __future__ import annotations

import os
import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TypedDict

from app.schemas import FormatInfo, StreamKind


class DownloadCancelled(Exception):  # noqa: N818 - name fixed by plan contract
    """Raised inside the progress hook when cancellation is requested."""


@dataclass(frozen=True)
class DownloadResult:
    """Result of :func:`run_download`: the output path plus file metadata.

    ``file_size``, ``media_format``, and ``resolution_height`` are best-effort
    — any of them may be ``None`` if yt-dlp didn't report the value and the
    output file is unavailable for stat-ing.
    """

    path: str
    file_size: int | None
    media_format: str | None
    resolution_height: int | None


# Type alias for the yt-dlp progress hook. yt-dlp passes a dict to each
# ``progress_hooks`` entry; the schema mirrors what the project consumes.
ProgressHook = Callable[[dict[str, Any]], None]


class StreamPickerRow(TypedDict):
    """Serialized stream row consumed by the Alpine picker."""

    format_id: str
    ext: str
    resolution: str | None
    height: int | None
    vcodec: str | None
    acodec: str | None
    abr: float | None
    audio_channels: int | None
    container: str | None


class StreamPickerPayload(TypedDict):
    """Browser payload for the Alpine stream picker."""

    video_streams: list[StreamPickerRow]
    audio_streams: list[StreamPickerRow]
    has_muxed_streams: bool
    expected_container_by_pair: dict[str, str]


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


def _stream_kind(vcodec: str | None, acodec: str | None) -> StreamKind:
    """Classify a normalized format as ``"audio"``, ``"video"``, or ``"muxed"``.

    A format is ``"audio"`` when it has an audio codec and no video
    codec, ``"video"`` when it has a video codec and no audio codec, and
    ``"muxed"`` otherwise (combined streams, or streams where the codec
    metadata is missing).
    """
    if vcodec == "none" and acodec and acodec != "none":
        return "audio"
    if acodec == "none" and vcodec and vcodec != "none":
        return "video"
    return "muxed"


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
        vcodec = _format_codec(raw.get("vcodec"))
        acodec = _format_codec(raw.get("acodec"))
        out.append(
            FormatInfo(
                format_id=format_id,
                ext=_safe_str(raw.get("ext")) or "",
                stream_kind=_stream_kind(vcodec, acodec),
                audio_channels=_safe_int(raw.get("audio_channels")),
                resolution=_safe_str(raw.get("resolution")),
                height=_safe_int(raw.get("height")),
                width=_safe_int(raw.get("width")),
                fps=_safe_float(raw.get("fps")),
                vcodec=vcodec,
                acodec=acodec,
                abr=_safe_float(raw.get("abr")),
                vbr=_safe_float(raw.get("vbr")),
                filesize=_safe_int(raw.get("filesize")),
                tbr=_safe_float(raw.get("tbr")),
                format_note=_safe_str(raw.get("format_note")),
                container=_safe_str(raw.get("container")),
            )
        )
    return out


def build_ytdlp_options(
    *,
    skip_download: bool,
    output_dir: str,
    output_template: str | None = None,
    format_selector: str | None = None,
    proxy: str | None = None,
    cookies_file: str | None = None,
    subtitles: bool = False,
    progress_hooks: list[ProgressHook] | None = None,
    js_runtime: str = "node",
) -> dict[str, Any]:
    """Build a consistent ``yt_dlp`` options dict for info lookup and downloads.

    Centralising this keeps ``extract_info`` and ``run_download`` in lock
    step: both pin the same YouTube extractor args and the same explicit
    JS runtime. yt-dlp needs a JS runtime registered to solve YouTube's
    JS challenges on hosts that do not ship Node.js by default, so the
    runtime is configured here rather than relying on PATH discovery.

    When ``skip_download`` is true the function omits ``outtmpl`` because
    info lookups do not write any files; the directory argument is
    ignored in that case.

    When ``subtitles`` is true, options are added to fetch SRT-formatted
    captions in English-first order with auto-generated fallback. The
    resulting ``.srt`` files are normalised by yt-dlp so a downstream
    pass can derive sibling ``.txt`` transcripts.
    """
    options: dict[str, Any] = {
        "quiet": True,
        "noprogress": True,
        "skip_download": skip_download,
        "extractor_args": {"youtube": {"player_client": ["default"]}},
        "js_runtimes": {js_runtime: {"path": js_runtime}},
    }
    if not skip_download:
        options["outtmpl"] = _output_template(output_template, output_dir)
    if format_selector:
        options["format"] = format_selector
    if proxy:
        options["proxy"] = proxy
    if cookies_file:
        options["cookiefile"] = cookies_file
    if subtitles:
        options["writesubtitles"] = True
        options["writeautomaticsub"] = True
        options["subtitlesformat"] = "srt/best"
    if progress_hooks:
        options["progress_hooks"] = progress_hooks
    return options


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

    ydl_opts = build_ytdlp_options(
        skip_download=True,
        output_dir="",
        proxy=proxy,
        cookies_file=cookies_file,
    )
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        return ydl.extract_info(url, download=False)


def extract_flat_info(
    url: str,
    *,
    proxy: str | None = None,
    cookies_file: str | None = None,
) -> dict:
    """Return yt-dlp metadata with playlist entries flattened."""
    import yt_dlp  # local import to keep module import cheap

    ydl_opts = build_ytdlp_options(
        skip_download=True,
        output_dir="",
        proxy=proxy,
        cookies_file=cookies_file,
    )
    ydl_opts["extract_flat"] = True
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        return ydl.extract_info(url, download=False)


_PERCENT_RE = re.compile(r"(-?[0-9]+(?:\.[0-9]+)?)\s*%")
_SRT_TIMESTAMP_RE = re.compile(r"^\d{2}:\d{2}:\d{2},\d{3}\s+-->\s+\d{2}:\d{2}:\d{2},\d{3}")


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


def infer_expected_container(video: FormatInfo | None, audio: FormatInfo | None) -> str:
    """Return the container yt-dlp is most likely to produce after merging.

    The rule is intentionally conservative: we only declare ``mp4`` when
    the video stream is H.264/AV1 inside an MP4 container and the audio
    stream is AAC inside an MP4/M4A container, because those are the
    codecs the MP4 muxer can ingest without remuxing failures. Anything
    else (WebM video, Opus audio, mismatched containers, or unknown
    codecs) falls back to ``mkv`` so the merge container matches what
    yt-dlp would pick. Audio-only downloads return the audio stream's
    own extension. Missing both streams returns ``"unknown"``.
    """
    if video is None and audio is None:
        return "unknown"

    if video is None:
        return audio.ext if audio and audio.ext else "unknown"

    if audio is None:
        return video.ext if video.ext else "unknown"

    video_ext = (video.ext or "").lower()
    audio_ext = (audio.ext or "").lower()
    video_codec = (video.vcodec or "").lower()
    audio_codec = (audio.acodec or "").lower()

    if (
        video_ext == "mp4"
        and audio_ext in {"m4a", "mp4"}
        and video_codec.startswith(("avc", "av01"))
        and audio_codec.startswith("mp4a")
    ):
        return "mp4"

    return "mkv"


def build_stream_picker_payload(formats: list[FormatInfo]) -> StreamPickerPayload:
    """Shape normalized formats into a browser payload for the Alpine picker.

    Splits the stream tables by ``stream_kind`` (``video`` vs. ``audio``),
    records whether the source exposes any ``muxed`` combined streams so
    the UI can show a fallback hint, and pre-computes the expected merge
    container for every ``<video_id>|<audio_id>`` pair (including the
    "no video" and "no audio" sentinel pairs) so the canonical Python
    rules stay the single source of truth.
    """
    video_streams = [f for f in formats if f.stream_kind == "video"]
    audio_streams = [f for f in formats if f.stream_kind == "audio"]
    has_muxed_streams = any(f.stream_kind == "muxed" for f in formats)

    def _row(item: FormatInfo) -> StreamPickerRow:
        return {
            "format_id": item.format_id,
            "ext": item.ext,
            "resolution": item.resolution,
            "height": item.height,
            "vcodec": item.vcodec,
            "acodec": item.acodec,
            "abr": item.abr,
            "audio_channels": item.audio_channels,
            "container": item.container,
        }

    expected_container_by_pair: dict[str, str] = {"|": "unknown"}
    for video in video_streams:
        expected_container_by_pair[f"{video.format_id}|"] = infer_expected_container(video, None)
    for audio in audio_streams:
        expected_container_by_pair[f"|{audio.format_id}"] = infer_expected_container(None, audio)
    for video in video_streams:
        for audio in audio_streams:
            key = f"{video.format_id}|{audio.format_id}"
            expected_container_by_pair[key] = infer_expected_container(video, audio)

    return {
        "video_streams": [_row(item) for item in video_streams],
        "audio_streams": [_row(item) for item in audio_streams],
        "has_muxed_streams": has_muxed_streams,
        "expected_container_by_pair": expected_container_by_pair,
    }


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
    """Return the yt-dlp ``outtmpl`` expression rooted under ``output_dir``."""
    return resolve_output_template(template, output_dir)


def resolve_output_template(template: str | None, output_dir: str | Path) -> str:
    """Return the yt-dlp ``outtmpl`` expression rooted under ``output_dir``.

    A ``None`` template falls back to ``<output_dir>/%(title)s.%(ext)s``.
    Relative templates are joined to ``output_dir`` so a UI-supplied
    template never escapes the configured downloads directory. Absolute
    templates are returned untouched so advanced users can target a
    fully-qualified path.
    """
    base_dir = Path(output_dir)
    if not template:
        return str(base_dir / "%(title)s.%(ext)s")
    candidate = Path(template)
    if candidate.is_absolute():
        return str(candidate)
    if ".." in candidate.parts:
        raise ValueError("output template must stay within the configured downloads directory")
    return str(base_dir / candidate)


def render_transcript_text(subtitle_text: str) -> str:
    """Convert SRT-formatted subtitles to a plain-text transcript.

    SRT cues consist of a numeric index, a ``-->`` timestamp line, and
    one or more caption lines. This helper drops the index, the
    timestamp line, and blank separators, joining the remaining text
    lines with a trailing newline each so the transcript reads as a
    continuous paragraph-per-cue document.
    """
    lines: list[str] = []
    raw_lines = subtitle_text.splitlines()
    index = 0
    while index < len(raw_lines):
        line = raw_lines[index].strip()
        next_line = raw_lines[index + 1].strip() if index + 1 < len(raw_lines) else ""
        if not line:
            index += 1
            continue
        if line.isdigit() and _SRT_TIMESTAMP_RE.match(next_line):
            index += 2
            continue
        if _SRT_TIMESTAMP_RE.match(line):
            index += 1
            continue
        lines.append(line)
        index += 1
    return "".join(f"{line}\n" for line in lines)


def write_transcript_sidecar(subtitle_path: str | Path) -> Path:
    """Write a sibling ``.txt`` transcript next to ``subtitle_path``.

    The transcript is derived from the subtitle text by
    :func:`render_transcript_text` and written to ``<stem>.txt``,
    overwriting any existing file. Returns the path of the written
    transcript file.
    """
    path = Path(subtitle_path)
    transcript_path = path.with_suffix(".txt")
    transcript_path.write_text(
        render_transcript_text(path.read_text(encoding="utf-8")),
        encoding="utf-8",
    )
    return transcript_path


def _extract_file_metadata(
    info: dict, output_path: str
) -> tuple[int | None, str | None, int | None]:
    """Derive ``(file_size, media_format, resolution_height)`` for a finished download.

    Prefers the on-disk file size for accuracy (yt-dlp's ``filesize`` is
    often missing for merged formats). Falls back to ``filesize`` or
    ``filesize_approx`` from the info dict only when stat-ing the output
    fails. ``media_format`` and ``resolution_height`` come straight from
    the info dict and may be ``None`` when not reported.
    """
    media_format = _safe_str(info.get("ext"))
    height_raw = info.get("height")
    resolution_height = _safe_int(height_raw)
    file_size: int | None = None
    if output_path:
        try:
            file_size = os.path.getsize(output_path)
        except OSError:
            file_size = None
    if file_size is None:
        file_size = _safe_int(info.get("filesize") or info.get("filesize_approx"))
    return file_size, media_format, resolution_height


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
) -> DownloadResult:
    """Run yt-dlp and return the output path plus file metadata.

    Raises ``DownloadCancelled`` if the progress hook signals cancellation.
    Callers should map yt-dlp errors through ``friendly_ytdlp_error()``.
    """
    import yt_dlp  # local import to keep module import cheap

    fmt = _format_selector(video_format_id, audio_format_id, audio_bitrate=audio_bitrate)
    ydl_opts = build_ytdlp_options(
        skip_download=False,
        output_dir=output_dir,
        output_template=output_template,
        format_selector=fmt,
        proxy=proxy,
        cookies_file=cookies_file,
        subtitles=subtitles,
    )
    captured_path: dict[str, str | None] = {"path": None}

    def _wrapped(d: dict[str, Any]) -> None:
        if d.get("status") == "finished" and d.get("filename"):
            captured_path["path"] = str(d["filename"])
        if progress_hook is not None:
            progress_hook(d)

    ydl_opts["progress_hooks"] = [_wrapped]

    Path(output_dir).mkdir(parents=True, exist_ok=True)

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)

    if subtitles:
        requested_subtitles = (info or {}).get("requested_subtitles") or {}
        for subtitle in requested_subtitles.values():
            subtitle_path = subtitle.get("filepath")
            if not subtitle_path:
                continue
            try:
                write_transcript_sidecar(subtitle_path)
            except OSError as exc:
                raise RuntimeError(f"unable to open for writing: {exc}") from exc

    output_path = captured_path["path"] or ""
    file_size, media_format, resolution_height = _extract_file_metadata(info or {}, output_path)
    return DownloadResult(
        path=output_path,
        file_size=file_size,
        media_format=media_format,
        resolution_height=resolution_height,
    )
