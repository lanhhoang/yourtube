# Architecture Deepening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deepen the current worker, enqueue, preview, and stream-selection seams without changing user-visible behavior.

**Architecture:** Land four behavior-preserving refactors in order of rising coupling. First isolate claimed-job execution from `app.main`, then move browser enqueue parsing behind one module, then unify single and batch preview lookup behind one module, and only then make the stream-selection contract explicit once the earlier seams have stabilized. Keep queue state, route URLs, template behavior, persisted schema, and yt-dlp semantics unchanged.

**Tech Stack:** Python 3.12, FastAPI, Starlette `FormData`, Jinja2, SQLAlchemy 2.x, pytest, Alpine.js, yt-dlp

---

## File Structure

- Create: `app/services/job_runner.py`
  Purpose: Own claimed-job execution, including runtime resolution, progress persistence, cancellation polling, yt-dlp invocation, error mapping, and terminal queue release.
- Create: `app/services/enqueue_intake.py`
  Purpose: Own browser form parsing for single enqueue, raw batch URLs, and preview-backed batch enqueue rows.
- Create: `app/services/preview.py`
  Purpose: Own single and batch preview lookup using the existing yt-dlp helpers and stream-picker payload shaping.
- Create: `app/services/stream_selection.py`
  Purpose: Own the explicit stream-selection contract: field names, typed selection parsing, and application to `DownloadCreate`.
- Create: `tests/unit/test_job_runner.py`
  Purpose: Lock down success, cancellation, and mapped-failure behavior at the new claimed-job seam.
- Create: `tests/unit/test_enqueue_intake.py`
  Purpose: Lock down browser form parsing rules away from FastAPI route handlers.
- Create: `tests/unit/test_preview.py`
  Purpose: Lock down single and batch preview lookup through one module.
- Create: `tests/unit/test_stream_selection.py`
  Purpose: Lock down stream-selection field names and form parsing.
- Modify: `app/main.py`
  Purpose: Keep only worker orchestration, claiming, startup, and shutdown logic.
- Modify: `app/routes/pages.py`
  Purpose: Delegate enqueue parsing and preview lookup to the new service modules.
- Modify: `app/templates/partials/info_result.html`
  Purpose: Consume explicit stream field names instead of hard-coded hidden-input names when rendering the single preview form.
- Modify: `app/templates/partials/batch_preview_card.html`
  Purpose: Consume the same explicit stream field names for batch cards.
- Modify: `app/templates/partials/stream_picker_form.html`
  Purpose: Render hidden inputs and Alpine bindings from the shared stream-selection contract.
- Modify: `tests/integration/test_worker_pool.py`
  Purpose: Narrow this file to worker-pool orchestration and stale-thread behavior.
- Modify: `tests/integration/test_pages.py`
  Purpose: Keep end-to-end route coverage while dropping field-parsing assertions already covered by unit tests.

---

### Task 1: Extract claimed-job execution from `app.main`

**Files:**
- Create: `app/services/job_runner.py`
- Create: `tests/unit/test_job_runner.py`
- Modify: `app/main.py`
- Modify: `tests/integration/test_worker_pool.py`

- [ ] **Step 1: Write the failing claimed-job tests**

Create `tests/unit/test_job_runner.py` with:

```python
from __future__ import annotations

from pathlib import Path

from app.models import Download
from app.schemas import DownloadCreate
from app.services.downloader import DownloadCancelled, DownloadResult
from app.services.job_runner import run_claimed_job
from app.services.queue import enqueue_download
from app.services.settings import set_settings_batch


def test_run_claimed_job_marks_done_and_persists_progress(
    monkeypatch, db_session_visible, tmp_path: Path
) -> None:
    row = enqueue_download(db_session_visible, DownloadCreate(url="https://example.com/success"))
    db_session_visible.execute(
        Download.__table__.update().where(Download.id == row.id).values(status="active")
    )
    set_settings_batch(db_session_visible, {"downloads_dir": str(tmp_path)})
    db_session_visible.commit()

    def fake_run_download(**kwargs):
        progress_hook = kwargs["progress_hook"]
        progress_hook({"status": "downloading", "_percent_str": "55.0%"})
        progress_hook({"status": "finished", "filename": str(tmp_path / "video.mp4")})
        return DownloadResult(
            path=str(tmp_path / "video.mp4"),
            file_size=2048,
            media_format="mp4",
            resolution_height=720,
        )

    monkeypatch.setattr("app.services.job_runner.run_download", fake_run_download)

    run_claimed_job(row.id)

    db_session_visible.refresh(row)
    assert row.status == "done"
    assert row.progress == 55.0
    assert row.file_path == str(tmp_path / "video.mp4")
    assert row.file_size == 2048
    assert row.media_format == "mp4"
    assert row.resolution_height == 720


def test_run_claimed_job_marks_cancelled_when_download_is_cancelled(
    monkeypatch, db_session_visible, tmp_path: Path
) -> None:
    row = enqueue_download(db_session_visible, DownloadCreate(url="https://example.com/cancel"))
    db_session_visible.execute(
        Download.__table__.update()
        .where(Download.id == row.id)
        .values(status="active", cancel_requested=True)
    )
    set_settings_batch(db_session_visible, {"downloads_dir": str(tmp_path)})
    db_session_visible.commit()

    def fake_run_download(**_kwargs):
        raise DownloadCancelled("cancelled by user")

    monkeypatch.setattr("app.services.job_runner.run_download", fake_run_download)

    run_claimed_job(row.id)

    db_session_visible.refresh(row)
    assert row.status == "cancelled"


def test_run_claimed_job_maps_failures_to_error_rows(
    monkeypatch, db_session_visible, tmp_path: Path
) -> None:
    row = enqueue_download(db_session_visible, DownloadCreate(url="https://example.com/fail"))
    db_session_visible.execute(
        Download.__table__.update().where(Download.id == row.id).values(status="active")
    )
    set_settings_batch(db_session_visible, {"downloads_dir": str(tmp_path)})
    db_session_visible.commit()

    def fake_run_download(**_kwargs):
        raise RuntimeError("HTTP Error 403: Forbidden")

    monkeypatch.setattr("app.services.job_runner.run_download", fake_run_download)

    run_claimed_job(row.id)

    db_session_visible.refresh(row)
    assert row.status == "error"
    assert row.error_code == "http_forbidden"
```

- [ ] **Step 2: Run the new unit tests to verify they fail**

Run:

```bash
uv run pytest tests/unit/test_job_runner.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'app.services.job_runner'`.

- [ ] **Step 3: Write the minimal claimed-job runner**

Create `app/services/job_runner.py` with:

```python
from __future__ import annotations

from pathlib import Path

from app.db import SessionLocal
from app.models import Download
from app.services.downloader import DownloadCancelled, YtdlpProgress, run_download
from app.services.error_mapper import friendly_ytdlp_error
from app.services.queue import is_cancel_requested, release_job, update_progress
from app.services.settings import resolve_runtime_settings


def _persist_progress(job_id: int, percent: float) -> None:
    with SessionLocal() as session:
        update_progress(session, job_id, percent)


def _cancel_requested(job_id: int) -> bool:
    with SessionLocal() as session:
        return is_cancel_requested(session, job_id)


def run_claimed_job(job_id: int) -> None:
    with SessionLocal() as session:
        runtime = resolve_runtime_settings(session)
        Path(runtime.downloads_dir).mkdir(parents=True, exist_ok=True)
        job = session.get(Download, job_id)
        if job is None:
            return
        job_url = job.url
        job_video_format_id = job.video_format_id
        job_audio_format_id = job.audio_format_id
        job_output_template = job.output_template
        job_audio_bitrate = job.audio_bitrate
        job_subtitles = job.subtitles

    progress = YtdlpProgress(
        cancel_requested=lambda: _cancel_requested(job_id),
        on_progress=lambda percent: _persist_progress(job_id, percent),
    )

    try:
        result = run_download(
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
    except DownloadCancelled:
        with SessionLocal() as session:
            release_job(session, job_id, status="cancelled")
        return
    except Exception as exc:  # noqa: BLE001
        code, message = friendly_ytdlp_error(str(exc))
        with SessionLocal() as session:
            release_job(
                session,
                job_id,
                status="error",
                error_code=code,
                error_message=message,
            )
        return

    with SessionLocal() as session:
        release_job(
            session,
            job_id,
            status="done",
            file_path=result.path or None,
            file_size=result.file_size,
            media_format=result.media_format,
            resolution_height=result.resolution_height,
        )
```

- [ ] **Step 4: Make `WorkerPool` delegate to the new module**

In `app/main.py`, replace the inlined `_run_job` body and imports with:

```python
from app.services.job_runner import run_claimed_job
```

and:

```python
    def _run_job(self, job_id: int) -> None:
        """Run a single claimed job to completion."""
        run_claimed_job(job_id)
```

Remove these now-unused imports from `app/main.py`:

```python
from app.models import Download
from app.services.downloader import DownloadCancelled, YtdlpProgress, run_download
from app.services.error_mapper import friendly_ytdlp_error
from app.services.queue import (
    claim_next,
    detect_stale_jobs,
    is_cancel_requested,
    release_job,
    requeue_active_on_startup,
    update_progress,
)
```

Replace them with:

```python
from app.services.queue import claim_next, detect_stale_jobs, requeue_active_on_startup
```

- [ ] **Step 5: Narrow worker-pool integration tests to orchestration**

In `tests/integration/test_worker_pool.py`, replace the three direct outcome tests with one delegation test:

```python
def test_worker_pool_delegates_claimed_job_to_job_runner(monkeypatch, db_session_visible) -> None:
    row = enqueue_download(db_session_visible, DownloadCreate(url="https://example.com/safe"))
    db_session_visible.execute(
        Download.__table__.update().where(Download.id == row.id).values(status="active")
    )
    db_session_visible.commit()

    seen: list[int] = []

    def fake_run_claimed_job(job_id: int) -> None:
        seen.append(job_id)

    monkeypatch.setattr("app.main.run_claimed_job", fake_run_claimed_job)

    from app.main import WorkerPool

    WorkerPool()._run_job(row.id)

    assert seen == [row.id]
```

Keep the detached-claim test and the stale-thread test unchanged.

- [ ] **Step 6: Run the focused verification**

Run:

```bash
uv run pytest tests/unit/test_job_runner.py tests/integration/test_worker_pool.py -v
```

Expected: PASS.

- [ ] **Step 7: Commit the worker refactor**

```bash
git add app/services/job_runner.py app/main.py tests/unit/test_job_runner.py tests/integration/test_worker_pool.py
git commit -m "refactor: extract claimed job runner"
```

---

### Task 2: Move browser enqueue parsing behind one module

**Files:**
- Create: `app/services/enqueue_intake.py`
- Create: `tests/unit/test_enqueue_intake.py`
- Modify: `app/routes/pages.py`

- [ ] **Step 1: Write the failing enqueue-intake tests**

Create `tests/unit/test_enqueue_intake.py` with:

```python
from __future__ import annotations

from starlette.datastructures import FormData

from app.services.enqueue_intake import build_batch_downloads, build_single_download


def test_build_single_download_returns_payload_and_target_id() -> None:
    form = FormData(
        [
            ("url", "https://example.com/watch?v=1"),
            ("title", "Example"),
            ("duration", "42"),
            ("target_id", "batch-status"),
            ("video_format_id", "137"),
            ("audio_format_id", "140"),
            ("subtitles", "on"),
        ]
    )

    payload, target_id = build_single_download(form)

    assert payload.url == "https://example.com/watch?v=1"
    assert payload.title == "Example"
    assert payload.duration == 42
    assert payload.video_format_id == "137"
    assert payload.audio_format_id == "140"
    assert payload.subtitles is True
    assert target_id == "batch-status"


def test_build_single_download_falls_back_to_info_status() -> None:
    form = FormData([("url", "https://example.com/watch?v=1"), ("target_id", "wrong")])

    _payload, target_id = build_single_download(form)

    assert target_id == "info-status"


def test_build_batch_downloads_prefers_raw_sources_and_dedupes_urls() -> None:
    form = FormData([("sources", "https://example.com/a\nhttps://example.com/a\nhttps://example.com/b")])

    payloads = build_batch_downloads(form)

    assert [payload.url for payload in payloads] == [
        "https://example.com/a",
        "https://example.com/b",
    ]


def test_build_batch_downloads_uses_preview_rows_when_sources_are_empty() -> None:
    form = FormData(
        [
            ("url", "https://example.com/a"),
            ("url", "https://example.com/b"),
            ("title", "Title A"),
            ("title", "Title B"),
            ("duration", "12"),
            ("duration", "24"),
            ("video_format_id", "137"),
            ("video_format_id", ""),
            ("audio_format_id", "140"),
            ("audio_format_id", "251"),
        ]
    )

    payloads = build_batch_downloads(form)

    assert len(payloads) == 2
    assert payloads[0].title == "Title A"
    assert payloads[0].duration == 12
    assert payloads[0].video_format_id == "137"
    assert payloads[0].audio_format_id == "140"
    assert payloads[1].title == "Title B"
    assert payloads[1].duration == 24
    assert payloads[1].video_format_id is None
    assert payloads[1].audio_format_id == "251"
```

- [ ] **Step 2: Run the new unit tests to verify they fail**

Run:

```bash
uv run pytest tests/unit/test_enqueue_intake.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'app.services.enqueue_intake'`.

- [ ] **Step 3: Write the minimal enqueue-intake module**

Create `app/services/enqueue_intake.py` with:

```python
from __future__ import annotations

from itertools import zip_longest

from starlette.datastructures import FormData, UploadFile

from app.schemas import DownloadCreate
from app.services.batch_preview import parse_source_urls


def _form_str(form: FormData, key: str) -> str | None:
    value = form.get(key)
    if value is None or isinstance(value, UploadFile):
        return None
    return str(value)


def _form_values(form: FormData, key: str) -> list[str]:
    return [str(value) for value in form.getlist(key) if not isinstance(value, UploadFile)]


def build_single_download(form: FormData) -> tuple[DownloadCreate, str]:
    duration_raw = _form_str(form, "duration")
    target_id = _form_str(form, "target_id")
    if target_id != "batch-status":
        target_id = "info-status"
    payload = DownloadCreate(
        url=_form_str(form, "url") or "",
        title=_form_str(form, "title"),
        uploader=_form_str(form, "uploader"),
        duration=int(duration_raw) if duration_raw else None,
        thumbnail=_form_str(form, "thumbnail"),
        video_format_id=_form_str(form, "video_format_id"),
        audio_format_id=_form_str(form, "audio_format_id"),
        output_template=_form_str(form, "output_template"),
        audio_bitrate=_form_str(form, "audio_bitrate"),
        subtitles=form.get("subtitles") == "on",
    )
    return payload, target_id


def build_batch_downloads(form: FormData) -> list[DownloadCreate]:
    raw_sources = _form_str(form, "sources") or ""
    urls = parse_source_urls(raw_sources)
    if urls:
        return [DownloadCreate(url=url) for url in urls]

    payloads: list[DownloadCreate] = []
    for url, title, uploader, duration, thumbnail, video_id, audio_id in zip_longest(
        _form_values(form, "url"),
        _form_values(form, "title"),
        _form_values(form, "uploader"),
        _form_values(form, "duration"),
        _form_values(form, "thumbnail"),
        _form_values(form, "video_format_id"),
        _form_values(form, "audio_format_id"),
        fillvalue="",
    ):
        if not url:
            continue
        payloads.append(
            DownloadCreate(
                url=url,
                title=title or None,
                uploader=uploader or None,
                duration=int(duration) if duration else None,
                thumbnail=thumbnail or None,
                video_format_id=video_id or None,
                audio_format_id=audio_id or None,
            )
        )
    return payloads
```

- [ ] **Step 4: Make the routes delegate to the intake module**

In `app/routes/pages.py`, add:

```python
from app.services.enqueue_intake import build_batch_downloads, build_single_download
```

Then replace the single enqueue route body with:

```python
    payload, target_id = build_single_download(form)
    enqueue_download(session, payload)
```

and replace the batch enqueue route body with:

```python
    payloads = build_batch_downloads(form)
    for payload in payloads:
        enqueue_download(session, payload)

    return templates.TemplateResponse(
        request,
        "partials/status_message.html",
        {
            "message": f"Added {len(payloads)} items to queue.",
            "target_id": "batch-status",
        },
    )
```

Delete the now-redundant route-local helpers and imports:

```python
from itertools import zip_longest
from starlette.datastructures import FormData, UploadFile
```

and:

```python
def _form_str(...):
    ...

def _form_values(...):
    ...
```

- [ ] **Step 5: Run the focused verification**

Run:

```bash
uv run pytest tests/unit/test_enqueue_intake.py tests/integration/test_pages.py::test_batch_enqueue_route_creates_one_queued_download_per_unique_url tests/integration/test_pages.py::test_batch_enqueue_route_creates_one_queued_download_per_valid_preview_item tests/integration/test_pages.py::test_batch_enqueue_route_preserves_preview_selected_stream_ids tests/integration/test_pages.py::test_batch_preview_card_enqueue_posts_metadata_to_queue -v
```

Expected: PASS.

- [ ] **Step 6: Commit the enqueue-intake refactor**

```bash
git add app/services/enqueue_intake.py app/routes/pages.py tests/unit/test_enqueue_intake.py
git commit -m "refactor: extract enqueue intake parsing"
```

---

### Task 3: Unify single and batch preview lookup

**Files:**
- Create: `app/services/preview.py`
- Create: `tests/unit/test_preview.py`
- Modify: `app/routes/pages.py`
- Modify: `tests/integration/test_pages.py`

- [ ] **Step 1: Write the failing preview tests**

Create `tests/unit/test_preview.py` with:

```python
from __future__ import annotations

from app.services.preview import resolve_batch_preview, resolve_single_preview


def test_resolve_single_preview_builds_picker_payload() -> None:
    def fake_extract_info(url: str, **_kwargs) -> dict:
        return {
            "title": "Example title",
            "uploader": "Uploader",
            "duration": 123,
            "thumbnail": "https://example.com/thumb.jpg",
            "formats": [
                {"format_id": "137", "ext": "mp4", "vcodec": "avc1", "acodec": "none"},
                {"format_id": "140", "ext": "m4a", "vcodec": "none", "acodec": "mp4a.40.2"},
            ],
        }

    result = resolve_single_preview(
        "https://example.com/watch?v=1",
        extract_info=fake_extract_info,
    )

    assert result.url == "https://example.com/watch?v=1"
    assert result.title == "Example title"
    assert result.picker_payload["video_streams"][0]["format_id"] == "137"
    assert result.picker_payload["audio_streams"][0]["format_id"] == "140"


def test_resolve_batch_preview_keeps_existing_batch_behavior() -> None:
    def fake_extract_info(url: str, **_kwargs) -> dict:
        if url.endswith("bad"):
            raise RuntimeError("HTTP Error 403: Forbidden")
        return {
            "title": f"title for {url}",
            "uploader": "Uploader",
            "duration": 12,
            "thumbnail": "https://example.com/thumb.jpg",
            "formats": [
                {"format_id": "137", "ext": "mp4", "vcodec": "avc1", "acodec": "none"},
                {"format_id": "140", "ext": "m4a", "vcodec": "none", "acodec": "mp4a.40.2"},
            ],
        }

    result = resolve_batch_preview(
        "https://example.com/good\nhttps://example.com/bad",
        extract_info=fake_extract_info,
    )

    assert result.valid_count == 1
    assert result.invalid_count == 1
    assert result.items[0].picker_payload["video_streams"][0]["format_id"] == "137"
    assert result.items[1].error_code == "http_forbidden"


def test_resolve_batch_preview_expands_playlists_with_flat_lookup() -> None:
    def fake_extract_info(url: str, **_kwargs) -> dict:
        return {
            "title": "Episode 1",
            "uploader": "Uploader",
            "duration": 10,
            "thumbnail": "https://example.com/1.jpg",
            "formats": [],
        }

    result = resolve_batch_preview(
        "https://example.com/list",
        extract_info=fake_extract_info,
        expand_playlist_entries=lambda url, **_kwargs: ["https://example.com/watch?v=1"],
        extract_flat_info=lambda url, **_kwargs: {"entries": [{"url": "https://example.com/watch?v=1"}]},
    )

    assert result.valid_count == 1
    assert result.items[0].source_url == "https://example.com/watch?v=1"
```

- [ ] **Step 2: Run the new unit tests to verify they fail**

Run:

```bash
uv run pytest tests/unit/test_preview.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'app.services.preview'`.

- [ ] **Step 3: Write the shared preview module**

Create `app/services/preview.py` with:

```python
from __future__ import annotations

from dataclasses import dataclass

from app.services.batch_preview import BatchPreviewResult, expand_playlist_entries
from app.services.downloader import (
    StreamPickerPayload,
    build_stream_picker_payload,
    extract_flat_info,
    normalize_formats,
)


@dataclass(frozen=True)
class SinglePreviewResult:
    url: str
    title: str
    uploader: str | None
    duration: int | None
    thumbnail: str | None
    picker_payload: StreamPickerPayload


def resolve_single_preview(
    url: str,
    *,
    extract_info,
    proxy: str | None = None,
    cookies_file: str | None = None,
) -> SinglePreviewResult:
    info = extract_info(url, proxy=proxy, cookies_file=cookies_file)
    formats = normalize_formats(info)
    return SinglePreviewResult(
        url=url,
        title=info.get("title", ""),
        uploader=info.get("uploader"),
        duration=info.get("duration"),
        thumbnail=info.get("thumbnail"),
        picker_payload=build_stream_picker_payload(formats),
    )


def resolve_batch_preview(
    raw: str,
    *,
    extract_info,
    expand_playlist_entries=expand_playlist_entries,
    extract_flat_info=extract_flat_info,
    proxy: str | None = None,
    cookies_file: str | None = None,
) -> BatchPreviewResult:
    from app.services.batch_preview import resolve_batch_preview as resolve_existing_batch_preview

    return resolve_existing_batch_preview(
        raw,
        extract_info=extract_info,
        expand_playlist=lambda url: expand_playlist_entries(
            url,
            extract_info=extract_flat_info,
            proxy=proxy,
            cookies_file=cookies_file,
        ),
        proxy=proxy,
        cookies_file=cookies_file,
    )
```

- [ ] **Step 4: Make routes use the shared preview seam**

In `app/routes/pages.py`, replace:

```python
from app.services.batch_preview import (
    expand_playlist_entries,
    parse_source_urls,
    resolve_batch_preview,
)
from app.services.downloader import (
    build_stream_picker_payload,
    extract_flat_info,
    extract_info,
    normalize_formats,
)
```

with:

```python
from app.services.downloader import extract_info
from app.services.preview import resolve_batch_preview, resolve_single_preview
```

Then replace the single preview route body with:

```python
    result = resolve_single_preview(
        url,
        extract_info=extract_info,
        proxy=runtime.proxy_url if proxy else None,
        cookies_file=str(runtime.cookies_path) if cookies and runtime.cookies_path else None,
    )
```

and update the template context to use:

```python
        {
            "url": result.url,
            "title": result.title,
            "uploader": result.uploader,
            "duration": result.duration,
            "thumbnail": result.thumbnail,
            "picker_payload": result.picker_payload,
        },
```

Replace the batch preview route body with:

```python
    result = resolve_batch_preview(
        sources,
        extract_info=extract_info,
        proxy=proxy_url,
        cookies_file=cookies_file,
    )
```

- [ ] **Step 5: Update route tests to patch the new seam**

In `tests/integration/test_pages.py`, keep the existing batch-preview route patches as-is and add a new single-preview route seam test:

```python
def test_info_lookup_route_uses_preview_service(monkeypatch) -> None:
    from app.services.preview import SinglePreviewResult

    def fake_resolve_single_preview(url: str, **_kwargs):
        assert url == "https://example.com/watch?v=1"
        return SinglePreviewResult(
            url=url,
            title="Example title",
            uploader="Uploader",
            duration=123,
            thumbnail="https://example.com/thumb.jpg",
            picker_payload={
                "video_streams": [],
                "audio_streams": [],
                "has_muxed_streams": True,
                "expected_container_by_pair": {"|": "unknown"},
            },
        )

    monkeypatch.setattr("app.routes.pages.resolve_single_preview", fake_resolve_single_preview)

    with TestClient(app) as client:
        response = client.post("/info/form", data={"url": "https://example.com/watch?v=1"})

    assert response.status_code == 200
    assert "Example title" in response.text
```

- [ ] **Step 6: Run the focused verification**

Run:

```bash
uv run pytest tests/unit/test_preview.py tests/unit/test_batch_preview.py tests/integration/test_pages.py::test_info_lookup_route_uses_preview_service tests/integration/test_pages.py::test_batch_lookup_fragment_renders_ready_and_error_cards -v
```

Expected: PASS.

- [ ] **Step 7: Commit the preview refactor**

```bash
git add app/services/preview.py app/routes/pages.py tests/unit/test_preview.py tests/integration/test_pages.py
git commit -m "refactor: unify preview lookup"
```

---

### Task 4: Make the stream-selection contract explicit

**Files:**
- Create: `app/services/stream_selection.py`
- Create: `tests/unit/test_stream_selection.py`
- Modify: `app/services/enqueue_intake.py`
- Modify: `app/routes/pages.py`
- Modify: `app/templates/partials/info_result.html`
- Modify: `app/templates/partials/batch_preview_card.html`
- Modify: `app/templates/partials/stream_picker_form.html`

- [ ] **Step 1: Write the failing stream-selection tests**

Create `tests/unit/test_stream_selection.py` with:

```python
from __future__ import annotations

from starlette.datastructures import FormData

from app.services.stream_selection import STREAM_FIELDS, selection_from_form


def test_stream_fields_define_the_public_contract() -> None:
    assert STREAM_FIELDS.video_format_id == "video_format_id"
    assert STREAM_FIELDS.audio_format_id == "audio_format_id"
    assert STREAM_FIELDS.output_template == "output_template"
    assert STREAM_FIELDS.audio_bitrate == "audio_bitrate"
    assert STREAM_FIELDS.subtitles == "subtitles"


def test_selection_from_form_reads_existing_field_names() -> None:
    form = FormData(
        [
            ("video_format_id", "137"),
            ("audio_format_id", "140"),
            ("output_template", "%(title)s.%(ext)s"),
            ("audio_bitrate", "128"),
            ("subtitles", "on"),
        ]
    )

    selection = selection_from_form(form)

    assert selection.video_format_id == "137"
    assert selection.audio_format_id == "140"
    assert selection.output_template == "%(title)s.%(ext)s"
    assert selection.audio_bitrate == "128"
    assert selection.subtitles is True
```

- [ ] **Step 2: Run the new unit tests to verify they fail**

Run:

```bash
uv run pytest tests/unit/test_stream_selection.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'app.services.stream_selection'`.

- [ ] **Step 3: Write the stream-selection contract module**

Create `app/services/stream_selection.py` with:

```python
from __future__ import annotations

from dataclasses import dataclass

from starlette.datastructures import FormData, UploadFile


@dataclass(frozen=True)
class StreamFieldNames:
    video_format_id: str = "video_format_id"
    audio_format_id: str = "audio_format_id"
    output_template: str = "output_template"
    audio_bitrate: str = "audio_bitrate"
    subtitles: str = "subtitles"


@dataclass(frozen=True)
class StreamSelection:
    video_format_id: str | None
    audio_format_id: str | None
    output_template: str | None
    audio_bitrate: str | None
    subtitles: bool


STREAM_FIELDS = StreamFieldNames()


def _str_value(form: FormData, key: str) -> str | None:
    value = form.get(key)
    if value is None or isinstance(value, UploadFile):
        return None
    return str(value) or None


def selection_from_form(form: FormData) -> StreamSelection:
    return StreamSelection(
        video_format_id=_str_value(form, STREAM_FIELDS.video_format_id),
        audio_format_id=_str_value(form, STREAM_FIELDS.audio_format_id),
        output_template=_str_value(form, STREAM_FIELDS.output_template),
        audio_bitrate=_str_value(form, STREAM_FIELDS.audio_bitrate),
        subtitles=form.get(STREAM_FIELDS.subtitles) == "on",
    )
```

- [ ] **Step 4: Make enqueue intake consume the typed stream selection**

In `app/services/enqueue_intake.py`, add:

```python
from app.services.stream_selection import selection_from_form
```

Then replace the stream-related fields in `build_single_download()` with:

```python
    selection = selection_from_form(form)
```

and:

```python
        video_format_id=selection.video_format_id,
        audio_format_id=selection.audio_format_id,
        output_template=selection.output_template,
        audio_bitrate=selection.audio_bitrate,
        subtitles=selection.subtitles,
```

- [ ] **Step 5: Pass the explicit field contract into the preview templates**

In `app/routes/pages.py`, add:

```python
from app.services.stream_selection import STREAM_FIELDS
```

Then include `stream_fields` in the single-preview and batch-preview template contexts:

```python
            "stream_fields": STREAM_FIELDS,
```

Update `app/templates/partials/info_result.html`, `app/templates/partials/batch_preview_card.html`, and `app/templates/partials/stream_picker_form.html` so every stream field reference uses the shared names. Replace literal names like:

```html
name="video_format_id"
```

with:

```html
name="{{ stream_fields.video_format_id }}"
```

Replace:

```html
name="audio_format_id"
```

with:

```html
name="{{ stream_fields.audio_format_id }}"
```

Replace:

```html
name="output_template"
name="audio_bitrate"
name="subtitles"
```

with:

```html
name="{{ stream_fields.output_template }}"
name="{{ stream_fields.audio_bitrate }}"
name="{{ stream_fields.subtitles }}"
```

- [ ] **Step 6: Run the focused verification**

Run:

```bash
uv run pytest tests/unit/test_stream_selection.py tests/unit/test_enqueue_intake.py tests/integration/test_pages.py::test_info_lookup_fragment_renders_stream_picker_markup tests/integration/test_pages.py::test_batch_lookup_fragment_renders_collapsed_format_picker tests/integration/test_pages.py::test_batch_enqueue_route_preserves_preview_selected_stream_ids -v
```

Expected: PASS.

- [ ] **Step 7: Commit the explicit stream contract**

```bash
git add app/services/stream_selection.py app/services/enqueue_intake.py app/routes/pages.py app/templates/partials/info_result.html app/templates/partials/batch_preview_card.html app/templates/partials/stream_picker_form.html tests/unit/test_stream_selection.py
git commit -m "refactor: make stream selection contract explicit"
```

---

### Task 5: Full-suite verification and cleanup

**Files:**
- Modify: none expected

- [ ] **Step 1: Run the full test suite**

Run:

```bash
uv run pytest -v
```

Expected: PASS.

- [ ] **Step 2: Review the diff for accidental behavior changes**

Run:

```bash
git diff --stat HEAD~4..HEAD
```

Expected: only the planned service, route, template, and test files changed.

- [ ] **Step 3: Confirm the worktree is ready for review**

Run:

```bash
git status --short
```

Expected: clean worktree.
