"""Unit tests for ``app.services.library``."""

from __future__ import annotations

import logging
import os
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pytest
from sqlalchemy.orm import Session

from app.config import REPO_ROOT
from app.models import Download
from app.schemas import DownloadCreate
from app.services.library import (
    delete_from_library,
    delete_many,
    get_library,
    search_library,
)
from app.services.queue import enqueue_download


def _make(url: str, title: str = "T", uploader: str = "U") -> DownloadCreate:
    return DownloadCreate(url=url, title=title, uploader=uploader)


def _mark_done(row: Download, db_session: Session, *, finished_at: datetime | None = None) -> None:
    db_session.execute(
        Download.__table__.update()
        .where(Download.id == row.id)
        .values(status="done", finished_at=finished_at or datetime.now())
    )
    db_session.expire(row)


def test_get_library_returns_only_done_rows(db_session: Session) -> None:
    """``get_library`` returns only rows with status ``done``."""
    done_row = enqueue_download(db_session, _make("https://example.com/done", title="Done"))
    _mark_done(done_row, db_session)

    enqueue_download(db_session, _make("https://example.com/queued"))
    enqueue_download(db_session, _make("https://example.com/active"))

    library = get_library(db_session)
    assert len(library) == 1
    assert library[0].id == done_row.id


def test_get_library_returns_newest_first(db_session: Session) -> None:
    """``get_library`` orders by ``finished_at`` descending."""
    older = enqueue_download(db_session, _make("https://example.com/older", title="Older"))
    _mark_done(older, db_session, finished_at=datetime(2024, 1, 1, 12, 0, 0))
    newer = enqueue_download(db_session, _make("https://example.com/newer", title="Newer"))
    _mark_done(newer, db_session, finished_at=datetime(2024, 6, 1, 12, 0, 0))

    library = get_library(db_session)
    assert [r.id for r in library] == [newer.id, older.id]


def test_search_library_matches_title_and_uploader(db_session: Session) -> None:
    """``search_library`` matches title and uploader fields."""
    cooking = enqueue_download(
        db_session, _make("https://example.com/1", title="Cooking pasta", uploader="Chef A")
    )
    _mark_done(cooking, db_session)
    tech = enqueue_download(
        db_session, _make("https://example.com/2", title="Python tutorial", uploader="Dev B")
    )
    _mark_done(tech, db_session)

    by_title = search_library(db_session, "cooking")
    assert [r.id for r in by_title] == [cooking.id]

    by_uploader = search_library(db_session, "dev b")
    assert [r.id for r in by_uploader] == [tech.id]

    no_match = search_library(db_session, "nonexistent")
    assert no_match == []


def test_delete_from_library_removes_row_and_file(db_session: Session, tmp_path: Path) -> None:
    """``delete_from_library`` removes the DB row and the on-disk file."""
    file_path = tmp_path / "video.mp4"
    file_path.write_text("data")
    row = enqueue_download(db_session, _make("https://example.com/del", title="Del"))
    _mark_done(row, db_session)
    db_session.execute(
        Download.__table__.update().where(Download.id == row.id).values(file_path=str(file_path))
    )
    db_session.expire(row)

    success, message = delete_from_library(db_session, row.id)
    assert success is True
    assert message == ""
    assert not file_path.exists()
    assert db_session.get(Download, row.id) is None


def test_delete_from_library_tolerates_missing_file(db_session: Session, tmp_path: Path) -> None:
    """A missing on-disk file does not fail the delete."""
    file_path = tmp_path / "missing.mp4"  # never written
    row = enqueue_download(db_session, _make("https://example.com/missing", title="M"))
    _mark_done(row, db_session)
    db_session.execute(
        Download.__table__.update().where(Download.id == row.id).values(file_path=str(file_path))
    )
    db_session.expire(row)

    success, message = delete_from_library(db_session, row.id)
    assert success is True
    assert message == "file_missing"
    assert db_session.get(Download, row.id) is None


def test_delete_from_library_returns_not_found_for_unknown_id(db_session: Session) -> None:
    success, message = delete_from_library(db_session, 9999)
    assert success is False
    assert message == "not_found"


def test_delete_from_library_returns_not_done_for_active_row(db_session: Session) -> None:
    """A non-done row cannot be deleted from the library."""
    row = enqueue_download(db_session, _make("https://example.com/queued", title="Q"))
    success, message = delete_from_library(db_session, row.id)
    assert success is False
    assert message == "not_done"


def test_delete_from_library_returns_delete_failed_on_permission_error(
    db_session: Session, tmp_path: Path
) -> None:
    """Real file deletion failures do not masquerade as file-missing success."""
    file_path = tmp_path / "protected.mp4"
    file_path.write_text("data")
    row = enqueue_download(db_session, _make("https://example.com/protected", title="P"))
    _mark_done(row, db_session)
    db_session.execute(
        Download.__table__.update().where(Download.id == row.id).values(file_path=str(file_path))
    )
    db_session.expire(row)

    with patch("app.services.library.os.remove", side_effect=PermissionError("denied")):
        success, message = delete_from_library(db_session, row.id)

    assert success is False
    assert message == "delete_failed"
    assert db_session.get(Download, row.id) is not None


def test_delete_from_library_resolves_relative_file_path(db_session: Session) -> None:
    """A relative ``file_path`` from an older row is resolved against the repo root."""
    row = enqueue_download(db_session, _make("https://example.com/rel", title="Rel"))
    _mark_done(row, db_session)
    db_session.execute(
        Download.__table__.update()
        .where(Download.id == row.id)
        .values(file_path="tmp/downloads/rel.mp4")
    )
    db_session.expire(row)

    with patch("app.services.library.os.remove") as remove:
        success, _ = delete_from_library(db_session, row.id)

    assert success is True
    remove.assert_called_once_with(REPO_ROOT / "tmp" / "downloads" / "rel.mp4")


def _row_with_file(db_session: Session, file_path: Path) -> Download:
    row = enqueue_download(db_session, _make("https://example.com/sc", title="Sc"))
    _mark_done(row, db_session)
    db_session.execute(
        Download.__table__.update().where(Download.id == row.id).values(file_path=str(file_path))
    )
    db_session.expire(row)
    return row


def test_delete_removes_subtitle_sidecars(db_session: Session, tmp_path: Path) -> None:
    """Deleting ``v`` removes its sidecars but not those of ``v.2`` or ``v-2``."""
    names = [
        "v.mp4",
        "v.en.srt",
        "v.en.txt",
        "v.txt",
        "v.2.mp4",
        "v.2.srt",
        "v-2.mp4",
        "v-2.en.srt",
    ]
    for name in names:
        (tmp_path / name).write_text("x")
    row = _row_with_file(db_session, tmp_path / "v.mp4")

    assert delete_from_library(db_session, row.id) == (True, "")
    assert sorted(p.name for p in tmp_path.iterdir()) == [
        "v-2.en.srt",
        "v-2.mp4",
        "v.2.mp4",
        "v.2.srt",
    ]


def test_delete_keeps_sidecars_when_media_delete_fails(db_session: Session, tmp_path: Path) -> None:
    media = tmp_path / "v.mp4"
    media.write_text("x")
    (tmp_path / "v.en.srt").write_text("x")
    row = _row_with_file(db_session, media)
    real_remove = os.remove

    def fake_remove(path: str | Path) -> None:
        if Path(path) == media:
            raise PermissionError
        real_remove(path)

    with patch("app.services.library.os.remove", fake_remove):
        assert delete_from_library(db_session, row.id) == (False, "delete_failed")
    assert (tmp_path / "v.en.srt").exists()


def test_delete_removes_sidecars_when_media_missing(db_session: Session, tmp_path: Path) -> None:
    (tmp_path / "v.en.srt").write_text("x")
    row = _row_with_file(db_session, tmp_path / "v.mp4")

    assert delete_from_library(db_session, row.id) == (True, "file_missing")
    assert not (tmp_path / "v.en.srt").exists()


def test_delete_ignores_sidecar_removal_failure(
    db_session: Session,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    media = tmp_path / "v.mp4"
    media.write_text("x")
    sidecar = tmp_path / "v.en.srt"
    sidecar.write_text("x")
    row = _row_with_file(db_session, media)
    row_id = row.id
    real_remove = os.remove
    # Alembic's fileConfig (run by other tests) can leave this logger disabled.
    monkeypatch.setattr(logging.getLogger("yourtube"), "disabled", False)

    def fake_remove(path: str | Path) -> None:
        if Path(path) == sidecar:
            raise OSError("boom")
        real_remove(path)

    with (
        caplog.at_level(logging.WARNING, logger="yourtube"),
        patch("app.services.library.os.remove", fake_remove),
    ):
        assert delete_from_library(db_session, row_id) == (True, "")
    assert db_session.get(Download, row_id) is None
    assert not media.exists()
    assert any("could not remove sidecar" in r.getMessage() for r in caplog.records)


def test_delete_many_partial(db_session: Session, tmp_path: Path) -> None:
    a_file = tmp_path / "a.mp4"
    a_file.write_text("a")
    a_srt = tmp_path / "a.en.srt"
    a_srt.write_text("s")
    d_file = tmp_path / "d.mp4"
    d_file.write_text("d")
    a = _row_with_file(db_session, a_file)
    b = _row_with_file(db_session, tmp_path / "b.mp4")  # never written
    c = enqueue_download(db_session, _make("https://example.com/c"))
    d = _row_with_file(db_session, d_file)

    real_remove = os.remove

    def fake_remove(path: str | Path) -> None:
        if Path(path) == d_file:
            raise PermissionError("nope")
        real_remove(path)

    with patch("app.services.library.os.remove", fake_remove):
        deleted, failed = delete_many(db_session, [a.id, b.id, c.id, d.id, 999999])

    assert deleted == [a.id, b.id]
    assert failed == [(c.id, "not_done"), (d.id, "delete_failed"), (999999, "not_found")]
    assert not a_file.exists()
    assert not a_srt.exists()
    assert d_file.exists()
    assert db_session.get(Download, d.id) is not None
    assert db_session.get(Download, c.id) is not None


def test_delete_many_dedupes(db_session: Session, tmp_path: Path) -> None:
    f = tmp_path / "a.mp4"
    f.write_text("a")
    a = _row_with_file(db_session, f)
    assert delete_many(db_session, [a.id, a.id]) == ([a.id], [])


def test_delete_many_survives_unexpected_exception(db_session: Session, tmp_path: Path) -> None:
    files = [tmp_path / f"{n}.mp4" for n in "abc"]
    for f in files:
        f.write_text("x")
    a, b, c = (_row_with_file(db_session, f).id for f in files)
    real = delete_from_library

    def flaky(session: Session, job_id: int) -> tuple[bool, str]:
        if job_id == b:
            raise RuntimeError("boom")
        return real(session, job_id)

    with patch("app.services.library.delete_from_library", flaky):
        deleted, failed = delete_many(db_session, [a, b, c])

    assert deleted == [a, c]
    assert failed == [(b, "delete_failed")]
    assert db_session.get(Download, b) is not None
