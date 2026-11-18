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


def test_job_runner_passes_quality_cap(monkeypatch, db_session_visible, tmp_path: Path) -> None:
    row = enqueue_download(
        db_session_visible,
        DownloadCreate(url="https://example.com/cap", quality_cap="720", audio_bitrate="128"),
    )
    db_session_visible.execute(
        Download.__table__.update().where(Download.id == row.id).values(status="active")
    )
    set_settings_batch(db_session_visible, {"downloads_dir": str(tmp_path)})
    db_session_visible.commit()
    seen: dict = {}

    def fake_run_download(**kwargs):
        seen.update(kwargs)
        return DownloadResult(
            path=str(tmp_path / "v.mp4"), file_size=1, media_format="mp4", resolution_height=720
        )

    monkeypatch.setattr("app.services.job_runner.run_download", fake_run_download)
    run_claimed_job(row.id)
    assert seen["quality_cap"] == "720"
    assert seen["hdr"] is False


def test_old_enqueue_leaves_cap_null(db_session_visible) -> None:
    row = enqueue_download(db_session_visible, DownloadCreate(url="https://example.com/old"))
    assert row.quality_cap is None


def test_run_claimed_job_output_guard_refusal_fails_clearly(
    monkeypatch, db_session_visible, tmp_path: Path
) -> None:
    """An old row whose template now leaves the downloads folder gets a message that says so."""
    row = enqueue_download(
        db_session_visible,
        DownloadCreate(url="https://example.com/old", output_template="/elsewhere/x.%(ext)s"),
    )
    db_session_visible.execute(
        Download.__table__.update().where(Download.id == row.id).values(status="active")
    )
    set_settings_batch(db_session_visible, {"downloads_dir": str(tmp_path)})
    db_session_visible.commit()

    def refused(**_kwargs):
        # What the always-on output guard raises (see test_run_download_always_guards).
        raise ValueError("output template must stay within the downloads folder")

    monkeypatch.setattr("app.services.job_runner.run_download", refused)

    run_claimed_job(row.id)

    db_session_visible.refresh(row)
    assert row.status == "error"
    assert row.error_code == "output_outside_downloads"


def test_job_runner_passes_hdr(monkeypatch, db_session_visible, tmp_path: Path) -> None:
    row = enqueue_download(
        db_session_visible,
        DownloadCreate(url="https://example.com/hdr", quality_cap="best", hdr=True),
    )
    db_session_visible.execute(
        Download.__table__.update().where(Download.id == row.id).values(status="active")
    )
    set_settings_batch(db_session_visible, {"downloads_dir": str(tmp_path)})
    db_session_visible.commit()
    seen: dict = {}

    def fake_run_download(**kwargs):
        seen.update(kwargs)
        return DownloadResult(
            path=str(tmp_path / "v.mp4"), file_size=1, media_format="mp4", resolution_height=2160
        )

    monkeypatch.setattr("app.services.job_runner.run_download", fake_run_download)
    run_claimed_job(row.id)
    assert seen["hdr"] is True
