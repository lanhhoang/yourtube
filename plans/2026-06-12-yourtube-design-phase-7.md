# Phase 7: Output Path + Container Correctness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix subtitle/download write failures caused by relative output templates and surface honest merge-container expectations for selected stream pairs.

**Architecture:** Keep all filesystem and merge-policy logic in the downloader layer so worker code only consumes resolved values. Add a small output-resolution helper, a small container-inference helper, and explicit path-oriented error mapping instead of spreading path decisions across routes, templates, and worker code.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.x, yt-dlp, ffmpeg, pytest, uv

---

## File Structure

```
yourtube/
├── app/
│   ├── main.py
│   └── services/
│       ├── downloader.py
│       └── error_mapper.py
└── tests/
    ├── unit/
    │   ├── test_downloader_runtime_resolution.py
    │   └── test_friendly_errors.py
    └── integration/
        └── test_worker_pool.py
```

Responsibilities:

- `app/services/downloader.py` resolves user-facing output templates against the configured downloads directory and infers the expected merged container.
- `app/main.py` uses the resolved template instead of passing raw user input directly to yt-dlp.
- `app/services/error_mapper.py` turns path/template failures into a stable user-facing error code and message.

### Task 1: Resolve relative output templates under `downloads_dir`

**Files:**
- Modify: `app/services/downloader.py`
- Modify: `app/main.py`
- Test: `tests/unit/test_downloader_runtime_resolution.py`
- Test: `tests/integration/test_worker_pool.py`

- [ ] **Step 1: Write the failing resolution tests**

```python
from pathlib import Path

from app.services.downloader import resolve_output_template


def test_resolve_output_template_joins_relative_template_to_output_dir(tmp_path: Path) -> None:
    resolved = resolve_output_template("%(title)s.%(ext)s", tmp_path)
    assert resolved == str(tmp_path / "%(title)s.%(ext)s")


def test_resolve_output_template_keeps_absolute_template_absolute(tmp_path: Path) -> None:
    absolute = tmp_path / "nested" / "%(title)s.%(ext)s"
    resolved = resolve_output_template(str(absolute), tmp_path)
    assert resolved == str(absolute)
```

- [ ] **Step 2: Run the resolution tests to verify they fail**

Run: `uv run pytest tests/unit/test_downloader_runtime_resolution.py::test_resolve_output_template_joins_relative_template_to_output_dir tests/unit/test_downloader_runtime_resolution.py::test_resolve_output_template_keeps_absolute_template_absolute -v`

Expected: FAIL because `resolve_output_template()` does not exist yet.

- [ ] **Step 3: Implement `resolve_output_template()` and route worker usage through it**

```python
# app/services/downloader.py
from pathlib import Path


def resolve_output_template(template: str | None, output_dir: str | Path) -> str:
    base_dir = Path(output_dir)
    if not template:
        return str(base_dir / "%(title)s.%(ext)s")
    candidate = Path(template)
    if candidate.is_absolute():
        return str(candidate)
    return str(base_dir / template)
```

```python
# app/main.py
from app.services.downloader import resolve_output_template, run_download

resolved_template = resolve_output_template(job_output_template, runtime.downloads_dir)
output_path = run_download(
    url=job_url,
    video_format_id=job_video_format_id,
    audio_format_id=job_audio_format_id,
    output_template=resolved_template,
    output_dir=str(runtime.downloads_dir),
    audio_bitrate=job_audio_bitrate,
    proxy=runtime.proxy_url,
    cookies_file=str(runtime.cookies_path) if runtime.cookies_path else None,
    subtitles=job_subtitles,
    progress_hook=progress,
)
```

- [ ] **Step 4: Add the worker regression test for relative templates with subtitles**

```python
def test_worker_resolves_relative_output_template_before_subtitle_download(
    monkeypatch, db_session_visible, tmp_path: Path
) -> None:
    row = enqueue_download(
        db_session_visible,
        DownloadCreate(
            url="https://example.com/subtitles",
            output_template="%(title)s.%(ext)s",
            subtitles=True,
        ),
    )
    db_session_visible.execute(
        Download.__table__.update().where(Download.id == row.id).values(status="active")
    )
    set_settings_batch(db_session_visible, {"downloads_dir": str(tmp_path)})
    db_session_visible.commit()

    captured: dict[str, object] = {}

    def fake_run_download(**kwargs):
        captured["output_template"] = kwargs["output_template"]
        captured["subtitles"] = kwargs["subtitles"]
        return str(tmp_path / "video.mp4")

    monkeypatch.setattr("app.main.run_download", fake_run_download)

    from app.main import WorkerPool

    WorkerPool()._run_job(row.id)

    assert captured["output_template"] == str(tmp_path / "%(title)s.%(ext)s")
    assert captured["subtitles"] is True
```

- [ ] **Step 5: Run the phase tests to verify they pass**

Run: `uv run pytest tests/unit/test_downloader_runtime_resolution.py tests/integration/test_worker_pool.py::test_worker_resolves_relative_output_template_before_subtitle_download -v`

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add app/main.py app/services/downloader.py tests/unit/test_downloader_runtime_resolution.py tests/integration/test_worker_pool.py
git commit -m "fix: resolve relative output templates under downloads dir"
```

### Task 2: Infer expected merge container for stream pairs

**Files:**
- Modify: `app/services/downloader.py`
- Test: `tests/unit/test_downloader_format.py`

- [ ] **Step 1: Write the failing container-inference tests**

```python
from app.services.downloader import infer_expected_container
from app.schemas import FormatInfo


def test_infer_expected_container_prefers_mp4_for_avc_and_aac() -> None:
    video = FormatInfo(format_id="137", ext="mp4", container="mp4_dash", vcodec="avc1", acodec="none")
    audio = FormatInfo(format_id="140", ext="m4a", container="m4a_dash", vcodec="none", acodec="mp4a.40.2")
    assert infer_expected_container(video, audio) == "mp4"


def test_infer_expected_container_falls_back_to_mkv_for_webm_plus_m4a() -> None:
    video = FormatInfo(format_id="400", ext="webm", container="webm_dash", vcodec="vp9", acodec="none")
    audio = FormatInfo(format_id="140", ext="m4a", container="m4a_dash", vcodec="none", acodec="mp4a.40.2")
    assert infer_expected_container(video, audio) == "mkv"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/unit/test_downloader_format.py::test_infer_expected_container_prefers_mp4_for_avc_and_aac tests/unit/test_downloader_format.py::test_infer_expected_container_falls_back_to_mkv_for_webm_plus_m4a -v`

Expected: FAIL because `infer_expected_container()` does not exist yet.

- [ ] **Step 3: Implement a narrow compatibility helper**

```python
def infer_expected_container(video: FormatInfo | None, audio: FormatInfo | None) -> str:
    if video is None and audio is None:
        return "unknown"
    if video is None:
        return "m4a" if audio and (audio.ext == "m4a" or (audio.acodec or "").startswith("mp4a")) else (audio.ext if audio else "unknown")
    if audio is None:
        return "mp4" if video.ext == "mp4" and (video.vcodec or "").startswith(("avc", "av01")) else (video.ext or "unknown")

    video_codec = (video.vcodec or "").lower()
    audio_codec = (audio.acodec or "").lower()
    if video.ext == "mp4" and audio.ext in {"m4a", "mp4"} and video_codec.startswith(("avc", "av01")) and audio_codec.startswith("mp4a"):
        return "mp4"
    return "mkv"
```

- [ ] **Step 4: Run the format tests to verify they pass**

Run: `uv run pytest tests/unit/test_downloader_format.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/services/downloader.py tests/unit/test_downloader_format.py
git commit -m "feat: infer expected merge container for stream pairs"
```

### Task 3: Map path/template failures to a stable friendly error

**Files:**
- Modify: `app/services/error_mapper.py`
- Test: `tests/unit/test_friendly_errors.py`

- [ ] **Step 1: Write the failing error-mapping test**

```python
from app.services.error_mapper import friendly_ytdlp_error


def test_friendly_error_maps_permission_denied_output_template_failures() -> None:
    code, message = friendly_ytdlp_error(
        "ERROR: unable to open for writing: [Errno 13] Permission denied: 'title.en-US.vtt.part'"
    )
    assert code == "output_path_unwritable"
    assert "output path" in message.lower()
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/unit/test_friendly_errors.py::test_friendly_error_maps_permission_denied_output_template_failures -v`

Expected: FAIL because permission-denied template errors currently fall through to a generic error bucket.

- [ ] **Step 3: Implement the new error branch**

```python
if "unable to open for writing" in detail_lower or "permission denied" in detail_lower:
    return (
        "output_path_unwritable",
        "Your configured output path or template is not writable. Check downloads directory and output template settings.",
    )
```

- [ ] **Step 4: Run the friendly-error tests to verify they pass**

Run: `uv run pytest tests/unit/test_friendly_errors.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/services/error_mapper.py tests/unit/test_friendly_errors.py
git commit -m "fix: map unwritable output path failures to friendly errors"
```
