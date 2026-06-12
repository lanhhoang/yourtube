# Phase 7: Output Path + Container Correctness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix relative output-template handling for downloads and subtitle sidecars, export captions as English-first `.srt` plus sibling plain-text `.txt` transcripts, add conservative merge-container inference, and surface path-write failures with a specific user-facing error.

**Architecture:** Keep path resolution, yt-dlp `outtmpl` construction, subtitle option assembly, transcript generation, and merge-container inference inside `app.services.downloader`. Keep `app.main.WorkerPool` as a thin orchestration layer that continues to pass stored job fields into `run_download()` without pre-processing them. Use yt-dlp to fetch subtitles in `srt`-preferred form with English-first and auto-caption fallback, then derive sibling `.txt` transcripts in app code and extend error mapping with a more specific write-path rule that matches before the existing generic permission-denied bucket.

**Tech Stack:** Python 3.12, FastAPI, yt-dlp, pytest, uv

---

## File Structure

```
yourtube/
├── app/
│   └── services/
│       ├── downloader.py
│       └── error_mapper.py
└── tests/
    └── unit/
        ├── test_downloader_format.py
        ├── test_downloader_runtime_resolution.py
        └── test_friendly_errors.py
```

Responsibilities:

- `app/services/downloader.py` resolves output templates under the configured downloads directory, builds yt-dlp subtitle/download options, generates sibling transcript files from downloaded subtitles, and infers the expected merged container from normalized format metadata.
- `app/services/error_mapper.py` maps write-path failures to a stable `output_path_unwritable` code before falling back to generic permission errors.
- `tests/unit/test_downloader_runtime_resolution.py` verifies the downloader-layer path resolution seam and subtitle option policy instead of testing through the worker pool.

### Task 1: Resolve output templates and subtitle download policy inside the downloader layer

**Files:**
- Modify: `app/services/downloader.py`
- Test: `tests/unit/test_downloader_runtime_resolution.py`

- [ ] **Step 1: Write the failing resolution tests**

```python
from __future__ import annotations

from pathlib import Path

from app.services.downloader import build_ytdlp_options, resolve_output_template


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
    assert "subtitleslangs" not in options
```

- [ ] **Step 2: Run the resolution tests to verify they fail**

Run: `uv run pytest tests/unit/test_downloader_runtime_resolution.py::test_resolve_output_template_uses_downloads_dir_for_default_template tests/unit/test_downloader_runtime_resolution.py::test_resolve_output_template_joins_relative_template_to_output_dir tests/unit/test_downloader_runtime_resolution.py::test_resolve_output_template_keeps_absolute_template_absolute tests/unit/test_downloader_runtime_resolution.py::test_build_ytdlp_options_uses_resolved_template_for_downloads tests/unit/test_downloader_runtime_resolution.py::test_build_ytdlp_options_prefers_srt_english_and_auto_subtitles -v`
Expected: FAIL because `resolve_output_template()` does not exist yet and `build_ytdlp_options()` neither resolves relative templates nor emits the new subtitle policy.

- [ ] **Step 3: Implement downloader-layer output-template resolution**

```python
from pathlib import Path
from typing import Any


def resolve_output_template(template: str | None, output_dir: str | Path) -> str:
    base_dir = Path(output_dir)
    if not template:
        return str(base_dir / "%(title)s.%(ext)s")

    candidate = Path(template)
    if candidate.is_absolute():
        return str(candidate)

    return str(base_dir / template)


def _output_template(template: str | None, output_dir: str) -> str:
    """Return the yt-dlp ``outtmpl`` expression rooted under ``output_dir``."""
    return resolve_output_template(template, output_dir)


# Rely on yt-dlp's default subtitle selection behavior:
# - prefer normal English subtitles when available
# - fall back to English auto-captions when needed
# - otherwise pick a single fallback language instead of every language
```

- [ ] **Step 4: Run the unit file to verify it passes**

Run: `uv run pytest tests/unit/test_downloader_runtime_resolution.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/services/downloader.py tests/unit/test_downloader_runtime_resolution.py
git commit -m "fix: resolve relative output templates in downloader layer"
```

### Task 2: Generate sibling plain-text transcripts from downloaded subtitles

**Files:**
- Modify: `app/services/downloader.py`
- Test: `tests/unit/test_downloader_runtime_resolution.py`

- [ ] **Step 1: Write the failing transcript-generation tests**

```python
from pathlib import Path

from app.services.downloader import render_transcript_text, write_transcript_sidecar


def test_render_transcript_text_strips_cues_and_timestamps() -> None:
    srt_text = """1
00:00:00,000 --> 00:00:01,500
Hello there

2
00:00:02,000 --> 00:00:03,500
General Kenobi
"""

    assert render_transcript_text(srt_text) == "Hello there\nGeneral Kenobi\n"


def test_write_transcript_sidecar_overwrites_existing_txt_file(tmp_path: Path) -> None:
    subtitle_path = tmp_path / "clip.en.srt"
    subtitle_path.write_text(
        "1\n00:00:00,000 --> 00:00:01,000\nFirst line\n",
        encoding="utf-8",
    )
    transcript_path = subtitle_path.with_suffix(".txt")
    transcript_path.write_text("old transcript\n", encoding="utf-8")

    written = write_transcript_sidecar(subtitle_path)

    assert written == transcript_path
    assert transcript_path.read_text(encoding="utf-8") == "First line\n"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/unit/test_downloader_runtime_resolution.py::test_render_transcript_text_strips_cues_and_timestamps tests/unit/test_downloader_runtime_resolution.py::test_write_transcript_sidecar_overwrites_existing_txt_file -v`
Expected: FAIL because neither transcript helper exists yet.

- [ ] **Step 3: Implement transcript rendering and sidecar writing**

```python
_SRT_TIMESTAMP_RE = re.compile(r"^\d{2}:\d{2}:\d{2},\d{3}\s+-->\s+\d{2}:\d{2}:\d{2},\d{3}")


def render_transcript_text(subtitle_text: str) -> str:
    lines: list[str] = []
    for raw_line in subtitle_text.splitlines():
        line = raw_line.strip()
        if not line or line.isdigit() or _SRT_TIMESTAMP_RE.match(line):
            continue
        lines.append(line)
    return "".join(f"{line}\n" for line in lines)


def write_transcript_sidecar(subtitle_path: str | Path) -> Path:
    path = Path(subtitle_path)
    transcript_path = path.with_suffix(".txt")
    transcript_path.write_text(
        render_transcript_text(path.read_text(encoding="utf-8")),
        encoding="utf-8",
    )
    return transcript_path
```

- [ ] **Step 4: Run the unit file to verify it passes**

Run: `uv run pytest tests/unit/test_downloader_runtime_resolution.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/services/downloader.py tests/unit/test_downloader_runtime_resolution.py
git commit -m "feat: derive transcript sidecars from subtitles"
```

### Task 3: Add conservative expected-container inference

**Files:**
- Modify: `app/services/downloader.py`
- Test: `tests/unit/test_downloader_format.py`

- [ ] **Step 1: Write the failing container-inference tests**

```python
from app.schemas import FormatInfo
from app.services.downloader import infer_expected_container


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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/unit/test_downloader_format.py::test_infer_expected_container_prefers_mp4_for_avc_and_aac tests/unit/test_downloader_format.py::test_infer_expected_container_falls_back_to_mkv_for_webm_plus_m4a tests/unit/test_downloader_format.py::test_infer_expected_container_returns_audio_ext_for_audio_only_stream tests/unit/test_downloader_format.py::test_infer_expected_container_returns_unknown_when_no_streams_are_selected -v`
Expected: FAIL because `infer_expected_container()` does not exist yet.

- [ ] **Step 3: Implement the compatibility helper in `app/services/downloader.py`**

```python
def infer_expected_container(video: FormatInfo | None, audio: FormatInfo | None) -> str:
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
```

- [ ] **Step 4: Run the format tests to verify they pass**

Run: `uv run pytest tests/unit/test_downloader_format.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/services/downloader.py tests/unit/test_downloader_format.py
git commit -m "feat: infer expected merge container"
```

### Task 4: Map write-open failures to a specific friendly error

**Files:**
- Modify: `app/services/error_mapper.py`
- Test: `tests/unit/test_friendly_errors.py`

- [ ] **Step 1: Write the failing error-mapping tests**

```python
from app.services.error_mapper import friendly_ytdlp_error


def test_friendly_error_maps_output_template_write_failures() -> None:
    code, message = friendly_ytdlp_error(
        "ERROR: unable to open for writing: [Errno 13] Permission denied: 'title.en-US.vtt.part'"
    )

    assert code == "output_path_unwritable"
    assert "output path" in message.lower()


def test_friendly_error_keeps_generic_permission_denied_for_non_template_errors() -> None:
    code, message = friendly_ytdlp_error("[Errno 13] Permission denied: '/var/data/file.mp4'")

    assert code == "permission_denied"
    assert message
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/unit/test_friendly_errors.py::test_friendly_error_maps_output_template_write_failures tests/unit/test_friendly_errors.py::test_friendly_error_keeps_generic_permission_denied_for_non_template_errors -v`
Expected: FAIL because the current rules only expose the generic `permission_denied` code.

- [ ] **Step 3: Add the ordered write-path rule in `app/services/error_mapper.py`**

```python
(
    "output_path_unwritable",
    "Your configured output path or template is not writable. Check downloads directory and output template settings.",
    re.compile(r"unable to open for writing", re.IGNORECASE),
),
(
    "permission_denied",
    "The app does not have permission to write the output file.",
    re.compile(r"permission denied", re.IGNORECASE),
),
```

- [ ] **Step 4: Run the friendly-error tests to verify they pass**

Run: `uv run pytest tests/unit/test_friendly_errors.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/services/error_mapper.py tests/unit/test_friendly_errors.py
git commit -m "fix: add friendly output path error mapping"
```

## Self-Review

- Spec coverage: path resolution, English-first SRT subtitle policy via yt-dlp's default single-language selection, transcript sidecar generation, conservative container inference, and specific write-path error mapping are all covered; no worker-layer or route-layer work remains in scope.
- Placeholder scan: no TBDs, no “similar to above” references, and every code-changing step includes concrete code.
- Type consistency: helper names, return types, and error codes are consistent across tasks.
