"""Find downloaded subtitle sidecars next to a media file and serve them as WebVTT."""

from __future__ import annotations

import re
from pathlib import Path

MEDIA_EXTS = {"mp4", "mkv", "webm", "m4a", "mp3", "opus", "ogg", "flac", "wav", "mov", "m4v"}
_SIDECAR_EXTS = {"srt", "vtt", "txt"}
_TIMESTAMP = re.compile(r"^(\d{2}:\d{2}:\d{2},\d{3}) --> (\d{2}:\d{2}:\d{2},\d{3})", re.ASCII)


def media_sidecars(media: Path) -> list[tuple[Path, str | None, str]]:
    """Return ``(path, lang, ext)`` for srt/vtt/txt files named after ``media``'s stem."""
    try:
        files = sorted((p for p in media.parent.iterdir() if p.is_file()), key=lambda p: p.name)
    except OSError:
        return []
    stem = media.stem
    longer_stems = [
        p.stem for p in files if p.suffix[1:].lower() in MEDIA_EXTS and len(p.stem) > len(stem)
    ]
    out: list[tuple[Path, str | None, str]] = []
    for p in files:
        if p == media or not p.name.startswith(stem + "."):
            continue
        parts = p.name[len(stem) + 1 :].split(".")
        ext = parts[-1].lower()
        if ext not in _SIDECAR_EXTS or len(parts) > 2:
            continue
        if any(p.name.startswith(s + ".") for s in longer_stems):
            continue
        out.append((p, parts[0] if len(parts) == 2 else None, ext))
    return out


def subtitle_sidecars(media: Path) -> dict[str, Path]:
    """Map language to subtitle file; ``.vtt`` wins over ``.srt``."""
    found: dict[str, Path] = {}
    for path, lang, ext in media_sidecars(media):
        if lang is None or ext not in {"srt", "vtt"}:
            continue
        if lang not in found or ext == "vtt":
            found[lang] = path
    return found


def srt_to_vtt(text: str) -> str:
    text = text.removeprefix("\ufeff").replace("\r\n", "\n").replace("\r", "\n")
    lines = []
    for line in text.split("\n"):
        m = _TIMESTAMP.match(line)
        if m:
            line = (
                m.group(1).replace(",", ".")
                + " --> "
                + m.group(2).replace(",", ".")
                + line[m.end() :]
            )
        lines.append(line)
    return "WEBVTT\n\n" + "\n".join(lines)


def read_vtt(path: Path) -> str:
    text = path.read_text(encoding="utf-8", errors="replace")
    if path.suffix.lower() == ".vtt":
        return text.removeprefix("\ufeff")
    return srt_to_vtt(text)
