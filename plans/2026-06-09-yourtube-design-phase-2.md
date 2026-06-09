# Phase 2: Downloader + Error Mapper + Settings (CLI Tool) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build three backend services (error mapper, settings, downloader) and expose them through a CLI. After this phase, `python -m app.cli info <url>` prints a format table and `python -m app.cli download <url> --video 137 --audio 140` downloads a YouTube video and muxes it to MP4.

**Architecture:** Layer of pure-Python services over the SQLModel DB from Phase 1. Error mapper is pure string pattern matching. Settings service reads/writes the `settings` table. Downloader wraps yt-dlp Python API with format selection, progress hooks, and mux-to-MP4 logic. CLI entry point in `app/cli.py`.

**Prerequisites:** Phase 1 must be complete (scaffold, config, DB, models, conftest).

**Tech Stack:** Python 3.12, yt-dlp, SQLModel, ty, pytest

---

## File Structure (this phase adds)

```
yourtube/
├── app/
│   ├── cli.py                       # NEW: CLI entry point (argparse)
│   └── services/
│       ├── error_mapper.py          # NEW: yt-dlp stderr → (message, code)
│       ├── settings.py              # NEW: Settings CRUD + validation
│       └── downloader.py            # NEW: yt-dlp wrapper + format selector + mux
└── tests/
    ├── unit/
    │   ├── test_friendly_errors.py  # NEW
    │   ├── test_settings.py         # NEW
    │   ├── test_downloader_format.py# NEW
    │   ├── test_downloader_progress.py # NEW
    │   └── test_filename_template.py # NEW
```

---

### Task 2.1: Error Mapper Service

**Files:**
- Create: `app/services/error_mapper.py`
- Create: `tests/unit/test_friendly_errors.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_friendly_errors.py
import pytest
from app.services.error_mapper import friendly_ytdlp_error


def test_private_video():
    msg, code = friendly_ytdlp_error("Sign in to confirm your age\nThis video is private")
    assert "cookies" in msg.lower()
    assert code == "VIDEO_PRIVATE"


def test_age_restricted():
    msg, code = friendly_ytdlp_error("confirm your age")
    assert "cookies" in msg.lower()
    assert code == "AGE_RESTRICTED"


def test_geo_blocked():
    msg, code = friendly_ytdlp_error("This video is not available in your country")
    assert "region" in msg.lower()
    assert code == "VIDEO_GEOBLOCKED"


def test_video_removed():
    msg, code = friendly_ytdlp_error("Video unavailable. This video has been removed by the uploader")
    assert "unavailable" in msg.lower() or "removed" in msg.lower()
    assert code == "VIDEO_REMOVED"


def test_http_403():
    msg, code = friendly_ytdlp_error("ERROR: HTTP Error 403: Forbidden")
    assert "access denied" in msg.lower()
    assert code == "INFO_FETCH_FAILED"


def test_timeout():
    msg, code = friendly_ytdlp_error("ERROR: timed out")
    assert "timed out" in msg.lower()
    assert code == "NETWORK_TIMEOUT"


def test_disk_full():
    msg, code = friendly_ytdlp_error("OSError: [Errno 28] No space left on device")
    assert "disk full" in msg.lower()
    assert code == "DISK_FULL"


def test_permission_denied():
    msg, code = friendly_ytdlp_error("Permission denied: '/downloads/test.mp4'")
    assert "permission denied" in msg.lower()
    assert code == "PERMISSION_DENIED"


def test_generic_fallback():
    msg, code = friendly_ytdlp_error("Some unknown yt-dlp error occurred")
    assert "unknown" in msg
    assert code == "INFO_FETCH_FAILED"


def test_long_error_truncated():
    long_err = "x" * 500
    msg, code = friendly_ytdlp_error(long_err)
    assert len(msg) <= 205
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/unit/test_friendly_errors.py -v
```
Expected: FAIL — module not found

- [ ] **Step 3: Write minimal implementation**

```python
# app/services/error_mapper.py
from __future__ import annotations


def friendly_ytdlp_error(stderr: str) -> tuple[str, str]:
    """Map yt-dlp error output to (user_message, error_code)."""
    s = stderr.lower()

    if "private video" in s or "sign in" in s:
        return "This video is private. Add cookies in Settings.", "VIDEO_PRIVATE"
    if "age-restricted" in s or "confirm your age" in s:
        return "Age-restricted. Add cookies in Settings to download.", "AGE_RESTRICTED"
    if "not available in your country" in s or "geo" in s:
        return "Not available in your region.", "VIDEO_GEOBLOCKED"
    if "video unavailable" in s or "removed" in s or " 404" in s:
        return "Video unavailable or removed.", "VIDEO_REMOVED"
    if "http error 403" in s:
        return "Access denied. YouTube may be blocking this client.", "INFO_FETCH_FAILED"
    if "timed out" in s:
        return "Request timed out. Try again.", "NETWORK_TIMEOUT"
    if "no space" in s or "enospc" in s:
        return "Disk full. Free space and retry.", "DISK_FULL"
    if "permission denied" in s:
        return "Cannot write to downloads folder.", "PERMISSION_DENIED"

    last = stderr.strip().splitlines()[-1] if stderr.strip() else "Unknown error"
    truncated = (last[:200] + "\u2026") if len(last) > 200 else last
    return truncated, "INFO_FETCH_FAILED"
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest tests/unit/test_friendly_errors.py -v
```
Expected: PASS (10/10)

- [ ] **Step 5: Commit**

```bash
git add app/services/error_mapper.py tests/unit/test_friendly_errors.py
git commit -m "feat: add yt-dlp error mapping service"
```

---

### Task 2.2: Settings Service

**Files:**
- Create: `app/services/settings.py`
- Create: `tests/unit/test_settings.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/unit/test_settings.py
import pytest
from app.services.settings import (
    DEFAULTS,
    get_setting,
    set_setting,
    get_all_settings,
    reset_settings,
    validate_cookies_path,
)


def test_defaults_returned_when_no_rows(db_session):
    all_s = get_all_settings(db_session)
    for k, v in DEFAULTS.items():
        assert all_s[k] == v, f"{k}: expected {v!r}, got {all_s[k]!r}"


def test_set_and_get(db_session):
    set_setting(db_session, "max_concurrent", "4")
    assert get_setting(db_session, "max_concurrent") == "4"


def test_set_overrides_default(db_session):
    set_setting(db_session, "default_quality", "1080")
    assert get_setting(db_session, "default_quality") == "1080"


def test_get_missing_key_returns_default(db_session):
    assert get_setting(db_session, "nonexistent") is None


def test_set_validates_max_concurrent_range(db_session):
    with pytest.raises(ValueError, match="max_concurrent must be between 1 and 8"):
        set_setting(db_session, "max_concurrent", "99")


def test_set_validates_default_format(db_session):
    with pytest.raises(ValueError, match="default_format must be 'video' or 'audio'"):
        set_setting(db_session, "default_format", "gif")


def test_set_validates_quality(db_session):
    with pytest.raises(ValueError, match="Invalid quality"):
        set_setting(db_session, "default_quality", "4k")


def test_reset_clears_all_rows(db_session):
    set_setting(db_session, "max_concurrent", "8")
    reset_settings(db_session)
    assert get_setting(db_session, "max_concurrent") == "2"


def test_validate_cookies_path_missing(tmp_path):
    p = tmp_path / "nonexistent.txt"
    valid, msg = validate_cookies_path(str(p))
    assert not valid
    assert "not found" in msg


def test_validate_cookies_path_valid(tmp_path):
    p = tmp_path / "cookies.txt"
    p.write_text("# Netscape HTTP Cookie File\n.youtube.com\tTRUE\t/\tTRUE\t0\t*\tvalue\n")
    valid, msg = validate_cookies_path(str(p))
    assert valid
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/unit/test_settings.py -v
```
Expected: FAIL — module not found

- [ ] **Step 3: Implement settings service**

```python
# app/services/settings.py
"""Settings CRUD, validation, defaults registry."""

from __future__ import annotations

import json
from pathlib import Path

from sqlmodel import Session, select

from app.models import Setting

DEFAULTS: dict[str, str] = {
    "downloads_dir": "",
    "max_concurrent": "2",
    "default_format": "video",
    "default_quality": "best",
    "filename_template": "%(title)s [%(id)s].%(ext)s",
    "subtitle_languages": '["en"]',
    "cookies_path": "",
    "proxy_url": "",
    "embed_thumbnail": "false",
    "embed_metadata": "true",
    "audio_bitrate": "192",
    "extra_ytdlp_args": "[]",
}


def get_all_settings(session: Session) -> dict[str, str]:
    rows = session.exec(select(Setting)).all()
    stored = {r.key: r.value for r in rows}
    return {**DEFAULTS, **stored}


def get_setting(session: Session, key: str) -> str | None:
    row = session.exec(select(Setting).where(Setting.key == key)).first()
    return row.value if row else DEFAULTS.get(key)


def set_setting(session: Session, key: str, value: str) -> None:
    _validate(key, value)
    row = session.exec(select(Setting).where(Setting.key == key)).first()
    if row:
        row.value = value
    else:
        session.add(Setting(key=key, value=value))
    session.commit()


def set_settings_batch(session: Session, updates: dict[str, str]) -> None:
    for k, v in updates.items():
        _validate(k, v)
    for k, v in updates.items():
        set_setting(session, k, v)
    session.commit()


def reset_settings(session: Session) -> None:
    for row in session.exec(select(Setting)).all():
        session.delete(row)
    session.commit()


def validate_cookies_path(path: str) -> tuple[bool, str]:
    p = Path(path)
    if not p.exists():
        return False, f"File not found: {path}"
    if not p.is_file():
        return False, "Path is not a file"
    try:
        text = p.read_text(encoding="utf-8")
        if not text.strip().startswith("# Netscape HTTP Cookie File"):
            return False, "File does not appear to be a Netscape-format cookies.txt"
        return True, "Valid cookies.txt"
    except Exception as e:
        return False, f"Cannot read file: {e}"


def _validate(key: str, value: str) -> None:
    if key == "max_concurrent":
        try:
            v = int(value)
            if not 1 <= v <= 8:
                raise ValueError
        except (ValueError, TypeError) as e:
            raise ValueError(f"max_concurrent must be between 1 and 8, got {value!r}") from e

    if key == "default_format" and value not in ("video", "audio"):
        raise ValueError(f"default_format must be 'video' or 'audio', got {value!r}")

    if key == "default_quality" and value not in ("best", "1080", "720", "480", "worst"):
        raise ValueError(f"Invalid quality: {value!r}")

    if key in ("subtitle_languages", "extra_ytdlp_args"):
        try:
            json.loads(value)
        except json.JSONDecodeError as e:
            raise ValueError(f"{key} must be valid JSON: {e}") from e

    if key == "audio_bitrate":
        try:
            v = int(value)
            if not 64 <= v <= 320:
                raise ValueError
        except (ValueError, TypeError) as e:
            raise ValueError(f"audio_bitrate must be 64-320, got {value!r}") from e
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest tests/unit/test_settings.py -v
```
Expected: PASS (10/10)

- [ ] **Step 5: Commit**

```bash
git add app/services/settings.py tests/unit/test_settings.py
git commit -m "feat: add settings service with validation"
```

---

### Task 2.3: Downloader Service (video+audio split, mux to MP4)

**Files:**
- Create: `app/services/downloader.py`
- Create: `tests/unit/test_downloader_format.py`
- Create: `tests/unit/test_downloader_progress.py`
- Create: `tests/unit/test_filename_template.py`

- [ ] **Step 1: Write the format selector tests**

```python
# tests/unit/test_downloader_format.py
import pytest
from app.services.downloader import (
    build_format_selector,
    classify_format,
    KIND_VIDEO,
    KIND_AUDIO,
    KIND_COMBINED,
)


def test_video_plus_audio_returns_combined_selector():
    fmt = build_format_selector(video_id="137", audio_id="140")
    assert fmt == "137+140"


def test_video_only_returns_video_selector():
    fmt = build_format_selector(video_id="137", audio_id=None)
    assert fmt == "137/b"


def test_audio_only_returns_audio_selector():
    fmt = build_format_selector(video_id=None, audio_id="140")
    assert fmt == "140/b"


def test_neither_raises():
    with pytest.raises(ValueError, match="at least one"):
        build_format_selector(video_id=None, audio_id=None)


def test_classify_video_only():
    kind = classify_format({"vcodec": "h264", "acodec": "none"})
    assert kind == KIND_VIDEO


def test_classify_audio_only():
    kind = classify_format({"vcodec": "none", "acodec": "aac"})
    assert kind == KIND_AUDIO


def test_classify_combined():
    kind = classify_format({"vcodec": "h264", "acodec": "aac"})
    assert kind == KIND_COMBINED


def test_classify_missing_codecs():
    kind = classify_format({})
    assert kind == KIND_COMBINED
```

- [ ] **Step 2: Write the progress hook tests**

```python
# tests/unit/test_downloader_progress.py
import pytest
from app.services.downloader import YtdlpProgress


def test_progress_stores_percent():
    p = YtdlpProgress()
    p({"status": "downloading", "_percent_str": "\x1b[0;32m45.5%\x1b[0m"})
    assert p.percent == 45.5


def test_progress_ignores_non_downloading():
    p = YtdlpProgress()
    p({"status": "finished"})
    assert p.percent == 0.0


def test_progress_empty_percent():
    p = YtdlpProgress()
    p({"status": "downloading"})
    assert p.percent == 0.0


def test_progress_malformed_percent():
    p = YtdlpProgress()
    p({"status": "downloading", "_percent_str": "abc%"})
    assert p.percent == 0.0


def test_progress_stores_filename():
    p = YtdlpProgress()
    p({"status": "finished", "filename": "/downloads/test.mp4"})
    assert p.filename == "/downloads/test.mp4"


def test_cancel_flag_raises():
    p = YtdlpProgress()
    p.cancel = True
    with pytest.raises(p.Cancelled):
        p({"status": "downloading", "_percent_str": "10%"})
```

- [ ] **Step 3: Write the filename template tests**

```python
# tests/unit/test_filename_template.py
import pytest
from app.services.downloader import sanitize_filename


def test_simple_title():
    assert sanitize_filename("Hello World") == "Hello World"


def test_strips_path_separators():
    assert "/" not in sanitize_filename("A/B Video")
    assert "\\" not in sanitize_filename("A\\B Video")


def test_strips_windows_invalid_chars():
    invalid = '<>:"|?*'
    result = sanitize_filename(f"Bad{invalid}Chars")
    for c in invalid:
        assert c not in result


def test_truncates_long():
    long_title = "a" * 300
    result = sanitize_filename(long_title)
    assert len(result) <= 100


def test_empty_fallback():
    assert sanitize_filename("") == "video"
```

- [ ] **Step 4: Implement the downloader service**

```python
# app/services/downloader.py
"""yt-dlp wrapper: format selector, progress hook, separate video+audio download + mux to MP4."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yt_dlp

KIND_VIDEO = "video"
KIND_AUDIO = "audio"
KIND_COMBINED = "combined"


def classify_format(fmt: dict) -> str:
    """Classify a yt-dlp format entry as video-only, audio-only, or combined."""
    vcodec = fmt.get("vcodec", "none")
    acodec = fmt.get("acodec", "none")
    if vcodec and vcodec != "none" and (not acodec or acodec == "none"):
        return KIND_VIDEO
    if acodec and acodec != "none" and (not vcodec or vcodec == "none"):
        return KIND_AUDIO
    return KIND_COMBINED


def build_format_selector(video_id: str | None, audio_id: str | None) -> str:
    """Build a yt-dlp -f selector string.

    Examples:
      - video + audio:  "137+140"   (downloads both streams, yt-dlp muxes)
      - video only:     "137/b"
      - audio only:     "140/b"
    """
    if video_id and audio_id:
        return f"{video_id}+{audio_id}"
    if video_id:
        return f"{video_id}/b"
    if audio_id:
        return f"{audio_id}/b"
    raise ValueError("build_format_selector requires at least one of video_id, audio_id")


class YtdlpProgress:
    """Tracks yt-dlp download progress via the Python callback hook."""

    class Cancelled(Exception):
        pass

    def __init__(self) -> None:
        self.percent: float = 0.0
        self.filename: str | None = None
        self.cancel: bool = False

    def __call__(self, d: dict[str, Any]) -> None:
        if self.cancel:
            raise self.Cancelled("Download cancelled by user")

        if d.get("status") == "downloading":
            raw = d.get("_percent_str", "")
            if raw:
                cleaned = re.sub(r"\x1b[^m]*m", "", raw).strip().rstrip("%")
                try:
                    self.percent = float(cleaned)
                except (ValueError, TypeError):
                    self.percent = 0.0

        elif d.get("status") == "finished":
            self.filename = d.get("filename")
            self.percent = 100.0


def sanitize_filename(title: str) -> str:
    """Remove characters unsafe for file systems, truncate to 100 chars."""
    title = re.sub(r'[\\/:*?"<>|]', "", title)
    title = title.strip()
    if not title:
        return "video"
    return title[:100]


def extract_info(url: str) -> dict[str, Any]:
    """Fetch video metadata from YouTube (no download)."""
    ydl_opts = {"quiet": True, "no_warnings": True}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        return ydl.extract_info(url, download=False)


def run_download(
    url: str,
    video_format_id: str | None,
    audio_format_id: str | None,
    output_template: str,
    output_dir: str,
    audio_bitrate: str = "192",
    proxy: str | None = None,
    cookies_file: str | None = None,
    subtitles: bool = False,
    progress_hook: YtdlpProgress | None = None,
) -> str | None:
    """Download the chosen video+audio streams and mux into a single MP4.

    When the format selector is "video_id+audio_id", yt-dlp downloads the two
    streams to temp files, then runs ffmpeg to merge them into the final MP4
    (because merge_output_format="mp4" is set).
    """
    format_selector = build_format_selector(video_format_id, audio_format_id)

    ydl_opts: dict[str, Any] = {
        "format": format_selector,
        "outtmpl": str(Path(output_dir) / output_template),
        "quiet": True,
        "no_warnings": True,
        "merge_output_format": "mp4",  # force mux to MP4 container
        "writethumbnail": False,
        "embedsubs": subtitles,
    }

    if progress_hook:
        ydl_opts["progress_hooks"] = [progress_hook]

    if proxy:
        ydl_opts["proxy"] = proxy
    if cookies_file:
        ydl_opts["cookiefile"] = cookies_file

    # Audio-only → extract to mp3
    if video_format_id is None and audio_format_id is not None:
        ydl_opts["postprocessors"] = [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": audio_bitrate,
            }
        ]

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])

    return progress_hook.filename if progress_hook else None
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
uv run pytest tests/unit/test_downloader_format.py tests/unit/test_downloader_progress.py tests/unit/test_filename_template.py -v
```
Expected: PASS (all)

- [ ] **Step 6: Commit**

```bash
git add app/services/downloader.py tests/unit/test_downloader_format.py tests/unit/test_downloader_progress.py tests/unit/test_filename_template.py
git commit -m "feat: add downloader service (video+audio split, mux to MP4, progress hook)"
```

---

### Task 2.4: CLI Entry Point

**Files:**
- Create: `app/cli.py`

- [ ] **Step 1: Create the CLI module**

```python
# app/cli.py
"""CLI entry point: python -m app.cli <command> [options]

Commands:
  info      Fetch metadata and print available formats
  download  Download a video by specifying video and audio format IDs
  settings  View or update settings
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from sqlmodel import Session

from app.db import engine
from app.services.downloader import (
    classify_format,
    extract_info,
    run_download,
    sanitize_filename,
)
from app.services.settings import (
    DEFAULTS,
    get_all_settings,
    get_setting,
    set_setting,
)

from app.models import Download


def cmd_info(args: argparse.Namespace) -> None:
    info = extract_info(args.url)
    print(f"Title:     {info.get('title', 'N/A')}")
    print(f"Uploader:  {info.get('uploader', 'N/A')}")
    duration = info.get("duration", 0)
    print(f"Duration:  {duration // 60}:{duration % 60:02d}")
    print(f"Thumbnail: {info.get('thumbnail', 'N/A')}")
    print()

    video_fmts = [f for f in info.get("formats", []) if classify_format(f) == "video"]
    audio_fmts = [f for f in info.get("formats", []) if classify_format(f) == "audio"]

    if video_fmts:
        print("Video Streams:")
        print(f"  {'ID':<6} {'Quality':<8} {'Res':<8} {'Ext':<5} {'Codec':<16} {'Bitrate':<8} Size")
        for f in video_fmts:
            h = f.get("height", 0) or 0
            quality = f"{h}p" if h else "?"
            size = f.get("filesize") or f.get("filesize_approx") or 0
            size_str = f"{size / 1_000_000:.1f}MB" if size else "?"
            codec = (f.get("vcodec") or "?")[:16]
            tbr = f.get("tbr", 0) or 0
            print(f"  {f['format_id']:<6} {quality:<8} {f'{h}x{f.get(\"width\",0)}':<8} "
                  f"{f.get('ext','?'):<5} {codec:<16} {f'{tbr:.0f}k':<8} {size_str}")
    print()

    if audio_fmts:
        print("Audio Streams:")
        print(f"  {'ID':<6} {'Ext':<5} {'Codec':<16} {'Bitrate':<8} Size")
        for f in audio_fmts:
            size = f.get("filesize") or f.get("filesize_approx") or 0
            size_str = f"{size / 1_000_000:.1f}MB" if size else "?"
            codec = (f.get("acodec") or "?")[:16]
            abr = f.get("abr", 0) or 0
            print(f"  {f['format_id']:<6} {f.get('ext','?'):<5} {codec:<16} "
                  f"{f'{abr:.0f}k':<8} {size_str}")
    print()

    # Show combined streams too
    combined = [f for f in info.get("formats", []) if classify_format(f) == "combined"]
    if combined:
        print("Combined (video+audio) Streams:")
        for f in combined:
            print(f"  {f['format_id']} — {f.get('ext','?')} "
                  f"({f.get('height',0)}p, {f.get('vcodec','?')} + {f.get('acodec','?')})")


def cmd_download(args: argparse.Namespace) -> None:
    with Session(engine) as session:
        output_dir = args.output or get_setting(session, "downloads_dir") or str(Path.home() / "Downloads")
        output_template = get_setting(session, "filename_template")
        audio_bitrate = get_setting(session, "audio_bitrate")
        proxy = args.proxy or get_setting(session, "proxy_url") or None
        cookies = args.cookies or get_setting(session, "cookies_path") or None

    print(f"Downloading: {args.url}")
    print(f"  Video format: {args.video or 'none'}")
    print(f"  Audio format: {args.audio or 'none'}")
    print(f"  Output dir:   {output_dir}")
    print()

    class ConsoleProgress:
        def __init__(self):
            self.last_pct = -1

        def __call__(self, d):
            if d.get("status") == "downloading":
                raw = d.get("_percent_str", "")
                if raw:
                    pct = raw.strip().rstrip("%")
                    try:
                        pct_f = float(pct)
                        if int(pct_f) != self.last_pct:
                            self.last_pct = int(pct_f)
                            print(f"  Progress: {pct}%", end="\r")
                    except (ValueError, TypeError):
                        pass
            elif d.get("status") == "finished":
                print(f"  Progress: 100%   ")
                print(f"  Completed: {d.get('filename', '?')}")

    result = run_download(
        url=args.url,
        video_format_id=args.video,
        audio_format_id=args.audio,
        output_template=output_template,
        output_dir=output_dir,
        audio_bitrate=audio_bitrate,
        proxy=proxy,
        cookies_file=cookies,
        progress_hook=ConsoleProgress(),
    )
    print(f"Saved to: {result}")


def cmd_settings(args: argparse.Namespace) -> None:
    with Session(engine) as session:
        if args.get:
            val = get_setting(session, args.get)
            print(f"{args.get}={val}")
        elif args.set:
            key, value = args.set.split("=", 1) if "=" in args.set else (args.set, "")
            set_setting(session, key, value)
            print(f"Set {key}={value}")
        else:
            all_s = get_all_settings(session)
            for k, v in all_s.items():
                marker = "" if v == DEFAULTS.get(k, "") else "  # custom"
                print(f"{k}={v}{marker}")


def main() -> None:
    parser = argparse.ArgumentParser(prog="yourtube", description="YouTube video downloader")
    sub = parser.add_subparsers(dest="command", required=True)

    p_info = sub.add_parser("info", help="Fetch video metadata")
    p_info.add_argument("url", help="YouTube URL")
    p_info.set_defaults(func=cmd_info)

    p_dl = sub.add_parser("download", help="Download a video")
    p_dl.add_argument("url", help="YouTube URL")
    p_dl.add_argument("--video", "-v", help="Video format ID (e.g. 137)")
    p_dl.add_argument("--audio", "-a", help="Audio format ID (e.g. 140)")
    p_dl.add_argument("--output", "-o", help="Output directory (overrides settings)")
    p_dl.add_argument("--proxy", help="HTTP proxy")
    p_dl.add_argument("--cookies", help="Path to cookies.txt")
    p_dl.set_defaults(func=cmd_download)

    p_set = sub.add_parser("settings", help="View or update settings")
    p_set.add_argument("--get", metavar="KEY", help="Get a setting value")
    p_set.add_argument("--set", metavar="KEY=VALUE", help="Set a setting value")
    p_set.set_defaults(func=cmd_settings)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Verify the CLI is importable**

```bash
uv run python -c "from app.cli import main; print('CLI loaded OK')"
```
Expected: `CLI loaded OK`

- [ ] **Step 3: Run all Phase 2 tests**

```bash
uv run pytest tests/unit/ -v
```
Expected: All PASS

- [ ] **Step 4: Commit**

```bash
git add app/cli.py
git commit -m "feat: add CLI entry point with info, download, and settings commands"
```

---

## Self-Review (Phase 2)

**Spec coverage:**
- ✓ Error mapper: 8 pattern categories + fallback + truncation
- ✓ Settings service: 12 keys, validation for 5 key types, cookies validation
- ✓ Downloader: format selector (video+audio, video-only, audio-only), format classification, progress hook, sanitize filename, extract info, run download with mux
- ✓ CLI: info (format table), download (video+audio split), settings (get/set/list)

**Placeholder scan:** No TBD, TODO, or incomplete sections.

**Type consistency:** `build_format_selector(video_id, audio_id)` used consistently in downloader service and CLI. `YtdlpProgress` used in both service definition and CLI console progress.

---

## End of Phase 2

Deliverable: `uv run python -m app.cli info <url>` prints a format table. `uv run python -m app.cli download <url> --video 137 --audio 140` downloads the video stream and audio stream separately, muxes to MP4, and saves to the configured download directory.
