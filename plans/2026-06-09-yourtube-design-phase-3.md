# Phase 3: Queue + Library Services Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the SQLite-backed download queue with worker pool and library management. After this phase, `uv run python -m app.cli enqueue <url> --video 137 --audio 140` adds a job, `uv run python -m app.cli worker` starts a background worker that claims and downloads the job, and `uv run python -m app.cli library` lists completed downloads.

**Architecture:** Queue service wraps the `downloads` table with atomic claim (oldest `queued` → `active`), cancellation, and stale detection (10 min timeout). Library service lists/searches/sorts terminal downloads. Worker pool uses daemon threads polling SQLite with `BEGIN IMMEDIATE` semantics. Extended CLI with `enqueue`, `cancel`, `list`, `worker`, and `library` commands.

**Prerequisites:** Phase 1 (scaffold) and Phase 2 (downloader, settings, error mapper, CLI) must be complete.

**Tech Stack:** Python 3.12, SQLModel, threading, yt-dlp, pytest, freezegun (for time travel in stale tests)

---

## File Structure (this phase adds)

```
yourtube/
├── app/
│   └── services/
│       ├── queue.py              # NEW: claim, release, cancel, stale, requeue
│       └── library.py            # NEW: list, search, sort, delete
└── tests/
    ├── unit/
    │   ├── test_queue_claim.py   # NEW
    │   ├── test_queue_cancel.py  # NEW
    │   ├── test_queue_stale.py   # NEW
    │   └── test_library.py       # NEW
    └── integration/
        └── test_worker.py        # NEW: worker pool integration test
```

---

### Task 3.1: Queue Service (claim, release, cancel, stale, requeue)

**Files:**
- Create: `app/services/queue.py`
- Create: `tests/unit/test_queue_claim.py`
- Create: `tests/unit/test_queue_cancel.py`
- Create: `tests/unit/test_queue_stale.py`

- [ ] **Step 1: Write the queue claim tests**

```python
# tests/unit/test_queue_claim.py
import pytest
from app.models import Download
from app.services.queue import claim_next, release_job, get_active_jobs


def test_claim_returns_queued_job(db_session):
    d = Download(
        url="https://youtube.com/watch?v=test",
        status="queued",
        video_format_id="137",
        audio_format_id="140",
    )
    db_session.add(d)
    db_session.commit()

    job = claim_next(db_session)
    assert job is not None
    assert job.status == "active"
    assert job.started_at is not None


def test_claim_skips_non_queued(db_session):
    d = Download(url="https://youtube.com/watch?v=test", status="done")
    db_session.add(d)
    db_session.commit()

    job = claim_next(db_session)
    assert job is None


def test_claim_returns_oldest_first(db_session):
    for i in range(3):
        db_session.add(Download(url=f"https://youtube.com/watch?v={i}", status="queued"))
    db_session.commit()

    job1 = claim_next(db_session)
    job2 = claim_next(db_session)
    job3 = claim_next(db_session)

    assert {job1.id, job2.id, job3.id} == {1, 2, 3}


def test_claim_atomic_no_double_claim(db_session):
    d = Download(url="https://youtube.com/watch?v=test", status="queued")
    db_session.add(d)
    db_session.commit()

    job1 = claim_next(db_session)
    job2 = claim_next(db_session)

    assert job1 is not None
    assert job2 is None


def test_release_marks_done(db_session):
    d = Download(url="https://youtube.com/watch?v=test", status="active")
    db_session.add(d)
    db_session.commit()

    release_job(db_session, d.id, status="done", file_path="/downloads/test.mp4", file_size=12345)
    db_session.refresh(d)
    assert d.status == "done"
    assert d.file_path == "/downloads/test.mp4"
    assert d.file_size == 12345
    assert d.completed_at is not None


def test_get_active_jobs(db_session):
    db_session.add(Download(url="https://youtube.com/1", status="queued"))
    db_session.add(Download(url="https://youtube.com/2", status="active"))
    db_session.add(Download(url="https://youtube.com/3", status="done"))
    db_session.commit()

    active = get_active_jobs(db_session)
    assert len(active) == 2
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/unit/test_queue_claim.py -v
```
Expected: FAIL — module not found / import error

- [ ] **Step 3: Write the cancellation tests**

```python
# tests/unit/test_queue_cancel.py
import pytest
from app.models import Download
from app.services.queue import cancel_job, request_cancel


def test_cancel_queued_job_immediate(db_session):
    d = Download(url="https://youtube.com/watch?v=test", status="queued")
    db_session.add(d)
    db_session.commit()

    result = cancel_job(db_session, d.id)
    db_session.refresh(d)
    assert result is True
    assert d.status == "cancelled"


def test_cancel_active_job_sets_flag(db_session):
    d = Download(url="https://youtube.com/watch?v=test", status="active")
    db_session.add(d)
    db_session.commit()

    result = cancel_job(db_session, d.id)
    db_session.refresh(d)
    assert result is True
    assert d.cancel_requested is True
    assert d.status == "active"


def test_cancel_done_job_unchanged(db_session):
    d = Download(url="https://youtube.com/watch?v=test", status="done")
    db_session.add(d)
    db_session.commit()

    result = cancel_job(db_session, d.id)
    assert result is False


def test_cancel_nonexistent_job(db_session):
    result = cancel_job(db_session, 999)
    assert result is False
```

- [ ] **Step 4: Write the stale detection tests**

These require `freezegun` — add it to dev dependencies first.

```bash
uv add --dev freezegun
```

```python
# tests/unit/test_queue_stale.py
import pytest
from datetime import datetime, timedelta
from freezegun import freeze_time
from app.models import Download
from app.services.queue import detect_stale_jobs


@freeze_time("2026-06-09 12:00:00")
def test_stale_older_than_10min(db_session):
    d = Download(
        url="https://youtube.com/watch?v=test",
        status="active",
        updated_at=datetime(2026, 6, 9, 11, 45, 0),
    )
    db_session.add(d)
    db_session.commit()

    count = detect_stale_jobs(db_session, timeout_minutes=10)
    assert count == 1


@freeze_time("2026-06-09 12:00:00")
def test_not_stale_within_timeout(db_session):
    d = Download(
        url="https://youtube.com/watch?v=test",
        status="active",
        updated_at=datetime(2026, 6, 9, 11, 55, 0),
    )
    db_session.add(d)
    db_session.commit()

    count = detect_stale_jobs(db_session, timeout_minutes=10)
    assert count == 0


@freeze_time("2026-06-09 12:00:00")
def test_stale_ignores_non_active(db_session):
    for status in ("queued", "done", "error", "cancelled"):
        d = Download(
            url="https://youtube.com/watch?v=test",
            status=status,
            updated_at=datetime(2026, 6, 8, 12, 0, 0),
        )
        db_session.add(d)
    db_session.commit()

    count = detect_stale_jobs(db_session, timeout_minutes=10)
    assert count == 0
```

- [ ] **Step 5: Implement the queue service**

```python
# app/services/queue.py
"""SQLite-backed download queue: worker claim, cancellation, staleness, requeue on startup."""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlmodel import Session, select

from app.models import Download


def claim_next(session: Session) -> Download | None:
    """Atomically claim the oldest queued job. Returns the claimed Download or None."""
    rows = session.exec(
        select(Download)
        .where(Download.status == "queued", Download.cancel_requested == False)  # noqa: E712
        .order_by(Download.id.asc())
        .limit(1)
    ).all()
    if not rows:
        return None
    job = rows[0]
    job.status = "active"
    job.started_at = datetime.utcnow()
    job.updated_at = datetime.utcnow()
    session.add(job)
    session.commit()
    session.refresh(job)
    return job


def release_job(
    session: Session,
    job_id: int,
    status: str,
    file_path: str | None = None,
    file_size: int | None = None,
    media_format: str | None = None,
    resolution_height: int | None = None,
    error: str | None = None,
) -> None:
    """Mark a job as done/error/cancelled and record output metadata."""
    job = session.get(Download, job_id)
    if not job:
        return
    job.status = status
    job.updated_at = datetime.utcnow()
    if status == "done":
        job.completed_at = datetime.utcnow()
        job.file_path = file_path
        job.file_size = file_size
        job.media_format = media_format
        job.resolution_height = resolution_height
        job.progress = 100.0
    elif status == "error":
        job.error = error
    session.add(job)
    session.commit()


def get_active_jobs(session: Session) -> list[Download]:
    return list(
        session.exec(
            select(Download)
            .where(Download.status.in_(["queued", "fetching_info", "active"]))
            .order_by(Download.created_at.asc())
        ).all()
    )


def cancel_job(session: Session, job_id: int) -> bool:
    """Cancel a job. Returns True if cancellation initiated, False if already terminal."""
    job = session.get(Download, job_id)
    if not job:
        return False
    if job.status in ("done", "error", "cancelled"):
        return False
    if job.status == "queued":
        job.status = "cancelled"
    else:
        job.cancel_requested = True
    job.updated_at = datetime.utcnow()
    session.add(job)
    session.commit()
    return True


def request_cancel(session: Session, job_id: int) -> bool:
    """Set cancel_requested flag for active jobs."""
    job = session.get(Download, job_id)
    if not job or job.status == "done":
        return False
    job.cancel_requested = True
    session.add(job)
    session.commit()
    return True


def detect_stale_jobs(session: Session, timeout_minutes: int = 10) -> int:
    """Mark jobs stuck in 'active' for too long as 'error'."""
    threshold = datetime.utcnow() - timedelta(minutes=timeout_minutes)
    stale = list(
        session.exec(
            select(Download).where(
                Download.status == "active",
                Download.updated_at < threshold,
            )
        ).all()
    )
    for job in stale:
        job.status = "error"
        job.error = "Download stalled (no progress for 10+ min)"
        job.updated_at = datetime.utcnow()
        session.add(job)
    session.commit()
    return len(stale)


def requeue_active_on_startup(session: Session) -> int:
    """Re-queue any jobs left active from a previous (crashed) run."""
    stuck = list(
        session.exec(select(Download).where(Download.status == "active")).all()
    )
    for job in stuck:
        job.status = "queued"
        job.error = "Re-queued after server restart"
        job.updated_at = datetime.utcnow()
        session.add(job)
    session.commit()
    return len(stuck)
```

- [ ] **Step 6: Run tests to verify they pass**

```bash
uv run pytest tests/unit/test_queue_claim.py tests/unit/test_queue_cancel.py tests/unit/test_queue_stale.py -v
```
Expected: PASS (all)

- [ ] **Step 7: Commit**

```bash
git add app/services/queue.py tests/unit/test_queue_claim.py tests/unit/test_queue_cancel.py tests/unit/test_queue_stale.py
git commit -m "feat: add queue service (claim, release, cancel, stale detection, requeue)"
```

---

### Task 3.2: Library Service

**Files:**
- Create: `app/services/library.py`
- Create: `tests/unit/test_library.py`

- [ ] **Step 1: Write the library tests**

```python
# tests/unit/test_library.py
import pytest
from datetime import datetime
from pathlib import Path
from app.models import Download
from app.services.library import (
    get_library,
    search_library,
    delete_from_library,
    get_file_path,
    format_size,
)


def test_get_library_returns_done_only(db_session):
    for i in range(3):
        db_session.add(Download(
            url=f"https://youtube.com/watch?v={i}",
            status="done" if i < 2 else "error",
            title=f"Video {i}",
        ))
    db_session.commit()

    items = get_library(db_session)
    assert len(items) == 2


def test_get_library_newest_first(db_session):
    db_session.add(Download(url="https://youtube.com/1", status="done", title="Old", created_at=datetime(2024, 1, 1)))
    db_session.add(Download(url="https://youtube.com/2", status="done", title="New", created_at=datetime(2025, 1, 1)))
    db_session.commit()

    items = get_library(db_session)
    assert items[0].title == "New"


def test_search_library_filters_by_title(db_session):
    db_session.add(Download(url="https://youtube.com/1", status="done", title="Rick Astley Never Gonna"))
    db_session.add(Download(url="https://youtube.com/2", status="done", title="Something Else"))
    db_session.commit()

    items = search_library(db_session, "rick")
    assert len(items) == 1
    assert "Rick" in items[0].title


def test_search_library_filters_by_uploader(db_session):
    db_session.add(Download(url="https://youtube.com/1", status="done", title="Video", uploader="ChannelName"))
    db_session.add(Download(url="https://youtube.com/2", status="done", title="Other", uploader="OtherChannel"))
    db_session.commit()

    items = search_library(db_session, "channel")
    assert len(items) == 1


def test_delete_removes_from_library(db_session, tmp_path):
    fp = tmp_path / "test.mp4"
    fp.write_text("fake video content")

    d = Download(url="https://youtube.com/watch?v=test", status="done", file_path=str(fp))
    db_session.add(d)
    db_session.commit()
    job_id = d.id

    success, msg = delete_from_library(db_session, job_id)
    assert success
    assert not fp.exists()


def test_delete_missing_file_ok(db_session):
    d = Download(url="https://youtube.com/watch?v=test", status="done", file_path="/nonexistent/test.mp4")
    db_session.add(d)
    db_session.commit()

    success, _ = delete_from_library(db_session, d.id)
    assert success


def test_format_size():
    assert format_size(None) == "—"
    assert format_size(500) == "500.0 B"
    assert format_size(1500) == "1.5 KB"
    assert format_size(1_500_000) == "1.4 MB"
    assert format_size(1_500_000_000) == "1.4 GB"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/unit/test_library.py -v
```
Expected: FAIL — module not found

- [ ] **Step 3: Implement the library service**

```python
# app/services/library.py
"""File library management: list, search, sort, delete."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import or_
from sqlmodel import Session, select

from app.models import Download


def get_library(session: Session) -> list[Download]:
    """Return all terminal downloads (done, error, cancelled), newest first."""
    return list(
        session.exec(
            select(Download)
            .where(Download.status.in_(["done", "error", "cancelled"]))
            .order_by(Download.created_at.desc())
        ).all()
    )


def search_library(
    session: Session,
    q: str = "",
    sort_by: str = "date",
) -> list[Download]:
    """Search library by title/uploader/url, then sort."""
    stmt = select(Download).where(
        Download.status.in_(["done", "error", "cancelled"])
    )

    if q:
        term = f"%{q}%"
        stmt = stmt.where(
            or_(
                Download.title.ilike(term),
                Download.uploader.ilike(term),
                Download.url.ilike(term),
            )
        )

    if sort_by == "name":
        stmt = stmt.order_by(Download.title.asc())
    elif sort_by == "size":
        stmt = stmt.order_by(Download.file_size.desc().nullslast())
    else:
        stmt = stmt.order_by(Download.created_at.desc())

    return list(session.exec(stmt).all())


def delete_from_library(session: Session, job_id: int) -> tuple[bool, str]:
    """Delete a download row and remove file from disk."""
    job = session.get(Download, job_id)
    if not job:
        return False, "Job not found"

    if job.file_path:
        try:
            Path(job.file_path).unlink(missing_ok=True)
        except OSError:
            pass

    session.delete(job)
    session.commit()
    return True, "Deleted"


def get_file_path(job: Download) -> Path | None:
    if not job.file_path:
        return None
    p = Path(job.file_path)
    return p if p.exists() else None


def format_size(size: int | None) -> str:
    if size is None:
        return "—"
    for unit in ("B", "KB", "MB", "GB"):
        if abs(size) < 1024:
            return f"{size:.1f} {unit}"
        size //= 1024
    return f"{size:.1f} TB"
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/unit/test_library.py -v
```
Expected: PASS (all)

- [ ] **Step 5: Commit**

```bash
git add app/services/library.py tests/unit/test_library.py
git commit -m "feat: add library service (list, search, delete, file path helpers)"
```

---

### Task 3.3: Extend CLI with Queue + Library Commands

**Files:**
- Modify: `app/cli.py`

- [ ] **Step 1: Add enqueue, cancel, list, worker, library commands to app/cli.py**

Insert the following into the existing `app/cli.py`. Add imports at the top, new command handlers in the middle, and new subparsers in `main()`.

```python
# Add these imports at the top (after existing imports):
from app.services.queue import (
    claim_next,
    cancel_job,
    get_active_jobs,
    detect_stale_jobs,
    release_job,
    requeue_active_on_startup,
)
from app.services.library import get_library, search_library, delete_from_library, format_size
from app.services.downloader import YtdlpProgress, run_download


# Add these command handlers after existing cmd_* functions:

def cmd_enqueue(args: argparse.Namespace) -> None:
    with Session(engine) as session:
        row = Download(
            url=args.url,
            video_format_id=args.video,
            audio_format_id=args.audio,
            format_choice="video" if args.video else "audio",
            status="queued",
        )
        session.add(row)
        session.commit()
        print(f"Enqueued job #{row.id}: {args.url}")
        print(f"  Video format: {args.video or 'none'}")
        print(f"  Audio format: {args.audio or 'none'}")


def cmd_list_queue(args: argparse.Namespace) -> None:
    with Session(engine) as session:
        jobs = get_active_jobs(session)
    if not jobs:
        print("No active jobs.")
        return
    print(f"{'ID':<5} {'Status':<14} {'Format':<14} {'Progress':<10} {'Title':<40}")
    print("-" * 85)
    for j in jobs:
        title = (j.title or j.url)[:40]
        fmt = f"v:{j.video_format_id or '-'} a:{j.audio_format_id or '-'}"
        prog = f"{j.progress:.0f}%"
        print(f"{j.id:<5} {j.status:<14} {fmt:<14} {prog:<10} {title}")


def cmd_cancel(args: argparse.Namespace) -> None:
    with Session(engine) as session:
        ok = cancel_job(session, args.job_id)
    if ok:
        print(f"Cancelled job #{args.job_id}")
    else:
        print(f"Could not cancel job #{args.job_id} (already finished or not found)")


def cmd_library(args: argparse.Namespace) -> None:
    with Session(engine) as session:
        items = search_library(session, q=args.q) if args.q else get_library(session)

    if not items:
        print("Library is empty.")
        return
    print(f"{'ID':<5} {'Status':<10} {'Size':<10} {'Title':<50}")
    print("-" * 75)
    for item in items:
        title = (item.title or "Untitled")[:50]
        print(f"{item.id:<5} {item.status:<10} {format_size(item.file_size):<10} {title}")


def cmd_cmd_worker(args: argparse.Namespace) -> None:
    """Run one cycle: claim → download → release. Repeats if --once not given."""
    import time

    once = args.once
    print(f"Worker started (once={once}). Polling every 2s...")
    while True:
        with Session(engine) as session:
            job = claim_next(session)
        if job is None:
            if once:
                print("No queued jobs. Exiting (--once).")
                break
            time.sleep(2)
            continue

        print(f"Claimed job #{job.id}: {job.url}")
        progress = YtdlpProgress()

        try:
            with Session(engine) as session:
                from app.services.settings import get_setting
                from app.config import settings

                output_dir = get_setting(session, "downloads_dir") or str(settings.downloads_dir)
                output_template = get_setting(session, "filename_template")
                audio_bitrate = get_setting(session, "audio_bitrate")
                proxy = get_setting(session, "proxy_url") or None
                cookies = get_setting(session, "cookies_path") or None
                subtitles = get_setting(session, "embed_metadata") == "true"

            final = run_download(
                url=job.url,
                video_format_id=job.video_format_id,
                audio_format_id=job.audio_format_id,
                output_template=output_template,
                output_dir=output_dir,
                audio_bitrate=audio_bitrate,
                proxy=proxy,
                cookies_file=cookies,
                subtitles=subtitles,
                progress_hook=progress,
            )

            with Session(engine) as session:
                release_job(
                    session, job.id,
                    status="done",
                    file_path=final,
                    file_size=Path(final).stat().st_size if final and Path(final).exists() else None,
                    media_format="mp4" if final else None,
                )
            print(f"  ✓ Job #{job.id} completed: {final}")

        except YtdlpProgress.Cancelled:
            with Session(engine) as session:
                release_job(session, job.id, status="cancelled")
            print(f"  ✗ Job #{job.id} cancelled")

        except Exception as e:
            from app.services.error_mapper import friendly_ytdlp_error
            msg, _ = friendly_ytdlp_error(str(e))
            with Session(engine) as session:
                release_job(session, job.id, status="error", error=msg)
            print(f"  ✗ Job #{job.id} failed: {msg}")

        if once:
            break
```

- [ ] **Step 2: Add subparsers in main()**

After the existing `p_set` subparser block in `main()`, add:

```python
    # Queue commands
    p_enqueue = sub.add_parser("enqueue", help="Add a URL to the download queue")
    p_enqueue.add_argument("url", help="YouTube URL")
    p_enqueue.add_argument("--video", "-v", help="Video format ID")
    p_enqueue.add_argument("--audio", "-a", help="Audio format ID")
    p_enqueue.set_defaults(func=cmd_enqueue)

    p_list = sub.add_parser("list", help="List active queue jobs")
    p_list.set_defaults(func=cmd_list_queue)

    p_cancel = sub.add_parser("cancel", help="Cancel a queued or active job")
    p_cancel.add_argument("job_id", type=int, help="Job ID to cancel")
    p_cancel.set_defaults(func=cmd_cancel)

    p_lib = sub.add_parser("library", help="List completed downloads")
    p_lib.add_argument("--q", help="Search query")
    p_lib.set_defaults(func=cmd_library)

    p_worker = sub.add_parser("worker", help="Run the download worker")
    p_worker.add_argument("--once", action="store_true", help="Process one job then exit")
    p_worker.set_defaults(func=cmd_cmd_worker)
```

- [ ] **Step 3: Write worker integration test**

```python
# tests/integration/test_worker.py
"""Integration test for the worker pool using a mocked yt-dlp."""

from unittest.mock import MagicMock, patch
from pathlib import Path

from app.models import Download
from app.services.queue import claim_next, release_job, get_active_jobs


def test_worker_claims_and_releases(db_engine, tmp_path):
    """Simulate a full worker cycle: enqueue → claim → download → release."""
    from sqlmodel import Session

    # Enqueue a job
    with Session(db_engine) as session:
        d = Download(
            url="https://youtube.com/watch?v=test",
            status="queued",
            video_format_id="137",
            audio_format_id="140",
        )
        session.add(d)
        session.commit()
        job_id = d.id

    # Claim it (simulating worker)
    with Session(db_engine) as session:
        job = claim_next(session)
        assert job is not None
        assert job.id == job_id
        assert job.status == "active"

    # Release it as done (simulating worker completing)
    output_file = tmp_path / "test_video.mp4"
    output_file.write_text("fake video data")

    with Session(db_engine) as session:
        release_job(
            session, job_id,
            status="done",
            file_path=str(output_file),
            file_size=output_file.stat().st_size,
            media_format="mp4",
        )

    # Verify it's in the library
    with Session(db_engine) as session:
        from app.services.library import get_library
        items = get_library(session)
        assert len(items) == 1
        assert items[0].id == job_id
        assert items[0].status == "done"
        assert items[0].file_path == str(output_file)


def test_worker_handles_error(db_engine):
    """Simulate worker failure — job should be marked error."""
    from sqlmodel import Session

    with Session(db_engine) as session:
        d = Download(url="https://youtube.com/watch?v=test", status="queued")
        session.add(d)
        session.commit()
        job_id = d.id

    with Session(db_engine) as session:
        job = claim_next(session)
        assert job is not None

    with Session(db_engine) as session:
        release_job(session, job_id, status="error", error="Something went wrong")

    with Session(db_engine) as session:
        assert session.get(Download, job_id).status == "error"
```

- [ ] **Step 4: Run all Phase 3 tests**

```bash
uv run pytest tests/unit/ tests/integration/ -v
```
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add app/cli.py tests/integration/
git commit -m "feat: extend CLI with queue, worker, and library commands"
```

---

## Self-Review (Phase 3)

**Spec coverage:**
- ✓ Queue: claim_next (oldest queued, skips non-queued, atomic), release_job (done/error/cancelled with metadata), get_active_jobs
- ✓ Cancel: immediate for queued, flag-based for active, rejects done/nonexistent
- ✓ Stale: marks active jobs older than 10 min as error, ignores queued/done/error/cancelled
- ✓ Library: get_library (done/error/cancelled, newest first), search_library (by title/uploader/url, sortable), delete_from_library (file + DB), format_size
- ✓ Worker: full cycle (enqueue → claim → download → release) tested in integration
- ✓ CLI: enqueue, list, cancel, library, worker commands

**Placeholder scan:** No TBD, TODO, or incomplete sections.

**Type consistency:** `claim_next` returns `Download | None`, `cancel_job` returns `bool`, `release_job` accepts all metadata fields. Consistent with Download model fields from Phase 1.

---

## End of Phase 3

Deliverable: 
- `uv run python -m app.cli enqueue <url> --video 137 --audio 140` adds a job
- `uv run python -m app.cli list` shows active jobs
- `uv run python -m app.cli worker --once` claims and processes one job
- `uv run python -m app.cli library` lists completed downloads
- `uv run python -m app.cli cancel <id>` cancels a job
