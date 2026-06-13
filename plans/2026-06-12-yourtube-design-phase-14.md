# YourTube Implementation Plan — Phase 14: Hydrate file metadata after download

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Populate `file_size`, `media_format`, and `resolution_height` on
`Download` rows when a job finishes, instead of leaving them `NULL` forever.

**Architecture:** `run_download()` (`app/services/downloader.py`) starts
returning a small `DownloadResult` dataclass (`path`, `file_size`,
`media_format`, `resolution_height`) instead of a bare path string, populated
from yt-dlp's `info` dict plus the actual on-disk file size. `app/main.py`'s
`_run_job` passes these through to `release_job(...)`.

**Tech Stack:** Python 3.12, dataclasses, yt-dlp, pytest

---

## Background for the worker

- `Download` already has `file_size: int | None`, `media_format: str | None`,
  `resolution_height: int | None` columns (`app/models.py:54-56`), and
  `release_job()` (`app/services/queue.py:127-167`) already accepts all three
  as optional kwargs and writes them when present.
- `app/main.py:184` currently calls
  `release_job(session, job_id_local, status="done", file_path=output_path or None)`
  — the three metadata kwargs are never passed, so they stay `NULL`.
- `run_download()` (`app/services/downloader.py:452-507`) calls
  `info = ydl.extract_info(url, download=True)` (line 494) and currently
  discards `info` except for `requested_subtitles`. yt-dlp's `info` dict
  exposes `ext` (container/format), `height` (vertical resolution), and
  `filesize`/`filesize_approx` (often `None` for merged formats).
- This phase only changes what's *stored*. No template currently displays
  `file_size`/`media_format`/`resolution_height` (confirmed by grep) — adding
  UI for these is a separate, future change.
- `tests/integration/test_worker_lifecycle.py::test_enqueue_claim_release_to_done`
  already calls `release_job(..., file_size=1024, media_format="mp4",
  resolution_height=1080)` directly and asserts the columns are set — that
  test already passes today (it tests `release_job` in isolation, not the
  worker). This phase makes the *worker* populate those same kwargs from real
  download results.

---

### Task 1: Return a `DownloadResult` from `run_download`

**Files:**
- Modify: `app/services/downloader.py`
- Test: `tests/unit/test_downloader_progress.py`

- [ ] **Step 1: Update the existing `run_download` tests to expect `DownloadResult`**

In `tests/unit/test_downloader_progress.py`, every `result == expected_path`
assertion becomes `result.path == expected_path`. There are 4 such
assertions, in:
- `test_run_download_returns_output_path_on_success`
- `test_run_download_returns_output_path_without_progress_hook`
- `test_run_download_writes_transcript_sidecar_when_subtitles_present`
- `test_run_download_succeeds_when_requested_subtitles_are_absent`

For example:

```diff
-    assert result == expected_path
+    assert result.path == expected_path
     assert progress.filename == expected_path
```

(apply the equivalent one-line change in each of the 4 tests)

Then add two new tests at the end of the "run_download tests" section:

```python
def test_run_download_extracts_media_format_and_resolution(tmp_path: Path) -> None:
    """``run_download`` extracts ``ext`` and ``height`` from the yt-dlp info dict."""
    expected_path = tmp_path / "video.mp4"
    expected_path.write_bytes(b"x" * 2048)

    captured_opts: dict = {}

    def factory(opts):
        captured_opts.update(opts)
        fake_ydl = MagicMock()
        fake_ydl.__enter__.return_value = fake_ydl

        def fake_extract_info(url, download):  # noqa: ARG001
            for hook in captured_opts["progress_hooks"]:
                hook({"status": "finished", "filename": str(expected_path)})
            return {"ext": "mp4", "height": 1080}

        fake_ydl.extract_info.side_effect = fake_extract_info
        return fake_ydl

    with patch("yt_dlp.YoutubeDL", side_effect=factory):
        result = run_download(
            url="https://example.com/video",
            output_dir=str(tmp_path),
        )

    assert result.path == str(expected_path)
    assert result.media_format == "mp4"
    assert result.resolution_height == 1080
    assert result.file_size == 2048


def test_run_download_falls_back_to_info_filesize_when_file_missing(tmp_path: Path) -> None:
    """If the output file can't be stat'd, fall back to yt-dlp's reported filesize."""
    expected_path = tmp_path / "missing.mp4"

    captured_opts: dict = {}

    def factory(opts):
        captured_opts.update(opts)
        fake_ydl = MagicMock()
        fake_ydl.__enter__.return_value = fake_ydl

        def fake_extract_info(url, download):  # noqa: ARG001
            for hook in captured_opts["progress_hooks"]:
                hook({"status": "finished", "filename": str(expected_path)})
            return {"ext": "webm", "height": 720, "filesize": 4096}

        fake_ydl.extract_info.side_effect = fake_extract_info
        return fake_ydl

    with patch("yt_dlp.YoutubeDL", side_effect=factory):
        result = run_download(
            url="https://example.com/video",
            output_dir=str(tmp_path),
        )

    assert result.path == str(expected_path)
    assert result.media_format == "webm"
    assert result.resolution_height == 720
    assert result.file_size == 4096
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/unit/test_downloader_progress.py -v`

Expected: FAIL — `AttributeError: 'str' object has no attribute 'path'` on the
4 updated tests, and `AssertionError`/`AttributeError` on the 2 new tests.

- [ ] **Step 3: Implement `DownloadResult` and metadata extraction**

In `app/services/downloader.py`, add `os` to imports and add `dataclass`:

```diff
+import os
 import re
+from dataclasses import dataclass
 from collections.abc import Callable
```

(keep the existing import ordering conventions — place `import os` with the
other stdlib imports, `from dataclasses import dataclass` with the other
`from` imports)

Add the result type near the top of the file, after the existing
`DownloadCancelled` class:

```python
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
```

Add a helper near `run_download`:

```python
def _extract_file_metadata(info: dict, output_path: str) -> tuple[int | None, str | None, int | None]:
    """Derive ``(file_size, media_format, resolution_height)`` for a finished download."""
    media_format = info.get("ext")
    resolution_height = info.get("height")
    file_size: int | None = None
    if output_path:
        try:
            file_size = os.path.getsize(output_path)
        except OSError:
            file_size = None
    if file_size is None:
        file_size = info.get("filesize") or info.get("filesize_approx")
    return file_size, media_format, resolution_height
```

Finally, change `run_download`'s return type and final return statement:

```diff
-) -> str:
+) -> DownloadResult:
     """Run yt-dlp and return the output file path.
```

and at the end of the function:

```diff
-    return captured_path["path"] or ""
+    output_path = captured_path["path"] or ""
+    file_size, media_format, resolution_height = _extract_file_metadata(info or {}, output_path)
+    return DownloadResult(
+        path=output_path,
+        file_size=file_size,
+        media_format=media_format,
+        resolution_height=resolution_height,
+    )
```

Update the docstring's first line too:

```diff
-    """Run yt-dlp and return the output file path.
+    """Run yt-dlp and return the output path plus file metadata.
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/unit/test_downloader_progress.py -v`

Expected: PASS (all tests, including the 2 new ones)

- [ ] **Step 5: Commit**

```bash
git add app/services/downloader.py tests/unit/test_downloader_progress.py
git commit -m "feat: extract file metadata from yt-dlp download results"
```

---

### Task 2: Pass extracted metadata to `release_job`

**Files:**
- Modify: `app/main.py`
- Modify: `tests/integration/test_worker_pool.py`

- [ ] **Step 1: Update `test_worker_pool.py` fakes and add a metadata assertion**

`test_worker_success_marks_job_done` currently has:

```python
    def fake_run_download(**kwargs):
        hook = kwargs["progress_hook"]
        hook({"status": "downloading", "_percent_str": "55.0%"})
        hook({"status": "finished", "filename": str(tmp_path / "video.mp4")})
        return str(tmp_path / "video.mp4")
```

Change the return value to a `DownloadResult` and add metadata assertions:

```python
    def fake_run_download(**kwargs):
        hook = kwargs["progress_hook"]
        hook({"status": "downloading", "_percent_str": "55.0%"})
        hook({"status": "finished", "filename": str(tmp_path / "video.mp4")})
        return DownloadResult(
            path=str(tmp_path / "video.mp4"),
            file_size=2048,
            media_format="mp4",
            resolution_height=720,
        )
```

and after the existing assertions:

```python
    assert row.file_size == 2048
    assert row.media_format == "mp4"
    assert row.resolution_height == 720
```

Add the import at the top of `tests/integration/test_worker_pool.py`:

```python
from app.services.downloader import DownloadCancelled, DownloadResult
```

(merge with the existing `from app.services.downloader import DownloadCancelled` import)

The other two fakes in this file
(`test_worker_cancelled_download_ends_cancelled`,
`test_worker_failure_maps_error`) raise exceptions and never reach the return
value — leave them unchanged.
`test_worker_loop_can_run_claimed_job_without_detached_instance`'s
`fake_run_download` returns `str(tmp_path / "safe.mp4")` and only checks
`row.status == "done"` — update its return to
`DownloadResult(path=str(tmp_path / "safe.mp4"), file_size=None, media_format=None, resolution_height=None)`
so `_run_job` doesn't break on `.path`.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/integration/test_worker_pool.py -v`

Expected: FAIL — `app.main._run_job` still does
`release_job(..., file_path=output_path or None)` where `output_path` is now
a `DownloadResult`, not a string; `row.file_size`/`media_format`/`resolution_height`
assertions fail (still `None`).

- [ ] **Step 3: Update `_run_job` in `app/main.py`**

```diff
         try:
-            output_path = run_download(
+            result = run_download(
                 url=job_url,
                 video_format_id=job_video_format_id,
                 audio_format_id=job_audio_format_id,
                 output_template=job_output_template,
                 output_dir=str(runtime.downloads_dir),
                 audio_bitrate=job_audio_bitrate,
                 proxy=runtime.proxy_url,
                 cookies_file=str(runtime.cookies_path) if runtime.cookies_path else None,
                 subtitles=job_subtitles,
                 progress_hook=progress,
             )
```

and:

```diff
         with SessionLocal() as session:
-            release_job(session, job_id_local, status="done", file_path=output_path or None)
+            release_job(
+                session,
+                job_id_local,
+                status="done",
+                file_path=result.path or None,
+                file_size=result.file_size,
+                media_format=result.media_format,
+                resolution_height=result.resolution_height,
+            )
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/integration/test_worker_pool.py -v`

Expected: PASS

- [ ] **Step 5: Run the full test suite**

Run: `uv run pytest tests/ -v`

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add app/main.py tests/integration/test_worker_pool.py
git commit -m "feat: persist file size, format, and resolution on completed downloads"
```

---

## Self-Review Notes

- **Spec coverage:** `run_download` now returns real metadata (Task 1) and
  `_run_job` forwards it to `release_job` (Task 2), closing the gap between
  the declared columns and what's actually written. Display of these fields
  in the library UI is explicitly out of scope (no template references them
  today).
- **Placeholder scan:** no TBD/TODO; all diffs and new code shown in full.
- **Type consistency:** `DownloadResult.path/file_size/media_format/resolution_height`
  used consistently in `downloader.py`, `main.py`, and both test files;
  `release_job`'s kwargs (`file_size`, `media_format`, `resolution_height`)
  already match the `Download` model column names.
