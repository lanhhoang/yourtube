# Architecture Deepening Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract claimed-job execution from `app.main` into a dedicated module without changing queue or worker behavior.

**Architecture:** Keep `WorkerPool` responsible only for thread orchestration, claiming, and stale-job polling. Move runtime settings resolution, progress persistence, cancellation polling, yt-dlp invocation, error mapping, and terminal queue release into `app/services/job_runner.py`, then retarget tests to the new seam.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.x, pytest, yt-dlp

---

## File Structure

- Create: `app/services/job_runner.py`
  Purpose: Own claimed-job execution for a previously claimed queue row.
- Create: `tests/unit/test_job_runner.py`
  Purpose: Lock down success, cancellation, and mapped-failure behavior at the new seam.
- Modify: `app/main.py`
  Purpose: Keep only worker orchestration, startup, shutdown, and claim-loop logic.
- Modify: `tests/integration/test_worker_pool.py`
  Purpose: Keep integration coverage for orchestration while dropping direct execution-path assertions.

---

### Task 1: Add a dedicated claimed-job runner module

**Files:**

- Create: `app/services/job_runner.py`
- Create: `tests/unit/test_job_runner.py`

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

- [ ] **Step 2: Run the new tests and verify they fail**

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

- [ ] **Step 4: Run the new tests and verify they pass**

Run:

```bash
uv run pytest tests/unit/test_job_runner.py -v
```

Expected: PASS.

---

### Task 2: Delegate `WorkerPool` execution to the new seam

**Files:**

- Modify: `app/main.py`
- Modify: `tests/integration/test_worker_pool.py`

- [ ] **Step 1: Replace the inlined `_run_job` implementation**

In `app/main.py`, add:

```python
from app.services.job_runner import run_claimed_job
```

Replace:

```python
    def _run_job(self, job_id: int) -> None:
        """Run a single claimed job to completion.

        Pulls the job row and runtime settings in one session, executes
        ``run_download`` (which may raise :class:`DownloadCancelled`),
        and writes the terminal state through :func:`release_job`.
        """
        ...
```

with:

```python
    def _run_job(self, job_id: int) -> None:
        """Run a single claimed job to completion."""
        run_claimed_job(job_id)
```

Remove these unused imports:

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

- [ ] **Step 2: Replace direct execution-path integration tests with delegation tests**

In `tests/integration/test_worker_pool.py`, remove the three tests that patch `app.main.run_download` and add:

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

Rewrite the detached-claim test so it also patches the new `app.main.run_claimed_job` seam instead of the removed `app.main.run_download` import:

```python
def test_worker_loop_can_run_claimed_job_without_detached_instance(
    monkeypatch, db_session_visible
) -> None:
    row = enqueue_download(db_session_visible, DownloadCreate(url="https://example.com/safe"))
    db_session_visible.commit()

    seen: list[int] = []

    def fake_run_claimed_job(job_id: int) -> None:
        seen.append(job_id)

    monkeypatch.setattr("app.main.run_claimed_job", fake_run_claimed_job)

    from app.main import WorkerPool

    pool = WorkerPool()
    claimed = pool._claim_once_for_test()
    assert claimed == row.id
    pool._run_job(claimed)

    assert seen == [row.id]
```

Keep the stale-thread test unchanged.

- [ ] **Step 3: Run the focused orchestration tests**

Run:

```bash
uv run pytest tests/integration/test_worker_pool.py -v
```

Expected: PASS.

---

### Task 3: Verify the phase is atomic and usable

**Files:**

- Modify: none expected

- [ ] **Step 1: Run the phase-local verification**

Run:

```bash
uv run pytest tests/unit/test_job_runner.py tests/integration/test_worker_pool.py tests/integration/test_worker_lifecycle.py -v
```

Expected: PASS.

- [ ] **Step 2: Commit the phase**

```bash
git add app/services/job_runner.py app/main.py tests/unit/test_job_runner.py tests/integration/test_worker_pool.py
git commit -m "refactor: extract claimed job runner"
```

- [ ] **Step 3: Confirm the worktree is clean**

Run:

```bash
git status --short
```

Expected: clean worktree.
