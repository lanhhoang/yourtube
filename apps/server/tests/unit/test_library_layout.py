from __future__ import annotations

import os
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from app.models import Download
from app.services.library_layout import LayoutSummary, migrate_library_layout
from app.services.settings import get_setting


def _row(session: Session, file: Path | str, **fields) -> Download:
    row = Download(
        url=fields.pop("url", "https://www.youtube.com/watch?v=vid1"),
        title=fields.pop("title", "Old Name"),
        uploader=fields.pop("uploader", "Chan"),
        status="done",
        file_path=str(file),
        **fields,
    )
    session.add(row)
    session.commit()
    return row


def _touch(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"x")
    return path


def _summary(s: LayoutSummary | None) -> tuple[int, int, int]:
    assert s is not None
    return (s.moved, s.skipped, s.failed)


def test_moves_file_and_sidecars(db_session: Session, tmp_path: Path) -> None:
    video = _touch(tmp_path / "Old Name.mp4")
    _touch(tmp_path / "Old Name.en.srt")
    _touch(tmp_path / "Old Name.en.txt")
    row = _row(db_session, video)

    summary = migrate_library_layout(db_session, tmp_path)

    new = tmp_path / "chan" / "old-name.mp4"
    assert _summary(summary) == (1, 0, 0)
    assert row.file_path == str(new) and new.exists()
    assert (tmp_path / "chan" / "old-name.en.srt").exists()
    assert (tmp_path / "chan" / "old-name.en.txt").exists()
    assert not video.exists()


def test_does_not_take_other_videos_sidecars(db_session: Session, tmp_path: Path) -> None:
    foo = _touch(tmp_path / "Foo.mp4")
    bar = _touch(tmp_path / "Foo.bar.mp4")
    _touch(tmp_path / "Foo.bar.en.srt")
    _row(db_session, foo, title="Foo", url="https://www.youtube.com/watch?v=a")
    _row(db_session, bar, title="Foo.bar", url="https://www.youtube.com/watch?v=b")

    migrate_library_layout(db_session, tmp_path)

    assert (tmp_path / "chan" / "foo.mp4").exists()
    assert (tmp_path / "chan" / "foo-bar.mp4").exists()
    assert (tmp_path / "chan" / "foo-bar.en.srt").exists()
    assert not (tmp_path / "chan" / "foo.en.srt").exists()


def test_missing_and_outside_are_skipped(db_session: Session, tmp_path: Path) -> None:
    downloads = tmp_path / "downloads"
    downloads.mkdir()
    outside = _touch(tmp_path / "elsewhere" / "x.mp4")
    missing = _row(db_session, downloads / "gone.mp4")
    out_row = _row(db_session, outside, url="https://www.youtube.com/watch?v=o")

    summary = migrate_library_layout(db_session, downloads)

    assert _summary(summary) == (0, 2, 0)
    assert outside.exists() and out_row.file_path == str(outside)
    assert missing.file_path == str(downloads / "gone.mp4")


def test_collision_gets_suffix(db_session: Session, tmp_path: Path) -> None:
    a = _touch(tmp_path / "a" / "t.mp4")
    b = _touch(tmp_path / "b" / "t.mp4")
    _row(db_session, a, title="T", url="https://www.youtube.com/watch?v=one")
    second = _row(db_session, b, title="T", url="https://www.youtube.com/watch?v=two")

    migrate_library_layout(db_session, tmp_path)

    assert (tmp_path / "chan" / "t.mp4").exists()
    assert second.file_path == str(tmp_path / "chan" / "t-two.mp4")


def test_failed_move_keeps_row(
    db_session: Session, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bad = _touch(tmp_path / "bad.mp4")
    good = _touch(tmp_path / "good.mp4")
    bad_row = _row(db_session, bad, title="Bad", url="https://www.youtube.com/watch?v=bad")
    good_row = _row(db_session, good, title="Good", url="https://www.youtube.com/watch?v=good")
    real = os.replace

    def replace(src, dst):
        if str(src).endswith("bad.mp4"):
            raise OSError("nope")
        return real(src, dst)

    monkeypatch.setattr(os, "replace", replace)

    summary = migrate_library_layout(db_session, tmp_path)

    assert _summary(summary) == (1, 0, 1)
    assert bad_row.file_path == str(bad) and bad.exists()
    assert good_row.file_path == str(tmp_path / "chan" / "good.mp4")


def test_runs_once(db_session: Session, tmp_path: Path) -> None:
    _row(db_session, _touch(tmp_path / "Old Name.mp4"))
    assert migrate_library_layout(db_session, tmp_path) is not None
    later = _touch(tmp_path / "Later.mp4")
    row = _row(db_session, later, title="Later", url="https://www.youtube.com/watch?v=l")

    assert migrate_library_layout(db_session, tmp_path) is None
    assert later.exists() and row.file_path == str(later)
    assert get_setting(db_session, "library_layout") == "v2"


def test_failure_retries_on_next_start(
    db_session: Session, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bad = _touch(tmp_path / "bad.mp4")
    good = _touch(tmp_path / "good.mp4")
    bad_row = _row(db_session, bad, title="Bad", url="https://www.youtube.com/watch?v=bad")
    _row(db_session, good, title="Good", url="https://www.youtube.com/watch?v=good")
    real = os.replace

    def replace(src, dst):
        if str(src).endswith("bad.mp4"):
            raise OSError("nope")
        return real(src, dst)

    with monkeypatch.context() as m:
        m.setattr(os, "replace", replace)
        first = migrate_library_layout(db_session, tmp_path)
    assert _summary(first) == (1, 0, 1)
    assert get_setting(db_session, "library_layout") is None

    second = migrate_library_layout(db_session, tmp_path)

    assert _summary(second) == (1, 1, 0)
    assert bad_row.file_path == str(tmp_path / "chan" / "bad.mp4")
    assert get_setting(db_session, "library_layout") == "v2"


def test_rerun_after_partial_move(db_session: Session, tmp_path: Path) -> None:
    moved = _touch(tmp_path / "chan" / "first.mp4")
    todo = _touch(tmp_path / "Second.mp4")
    first = _row(db_session, moved, title="First", url="https://www.youtube.com/watch?v=f")
    second = _row(db_session, todo, title="Second", url="https://www.youtube.com/watch?v=s")

    summary = migrate_library_layout(db_session, tmp_path)

    assert _summary(summary) == (1, 1, 0)
    assert first.file_path == str(moved)
    assert second.file_path == str(tmp_path / "chan" / "second.mp4")


def test_relative_file_path_is_resolved(
    db_session: Session, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("app.config.REPO_ROOT", tmp_path)
    downloads = tmp_path / "downloads"
    _touch(downloads / "Old.mp4")
    row = _row(db_session, "downloads/Old.mp4", title="Old")

    summary = migrate_library_layout(db_session, downloads)

    assert _summary(summary) == (1, 0, 0)
    assert row.file_path == str(downloads / "chan" / "old.mp4")


def test_rows_sharing_a_file_move_together(db_session: Session, tmp_path: Path) -> None:
    video = _touch(tmp_path / "Old Name.mp4")
    one = _row(db_session, video)
    two = _row(db_session, video)

    summary = migrate_library_layout(db_session, tmp_path)

    new = str(tmp_path / "chan" / "old-name.mp4")
    assert _summary(summary) == (1, 0, 0)
    assert one.file_path == new and two.file_path == new


def test_recovers_move_without_commit(db_session: Session, tmp_path: Path) -> None:
    target = _touch(tmp_path / "chan" / "old-name.mp4")
    row = _row(db_session, tmp_path / "Old Name.mp4")

    summary = migrate_library_layout(db_session, tmp_path)

    assert _summary(summary) == (1, 0, 0)
    assert row.file_path == str(target)


def test_missing_source_does_not_take_a_file_moved_this_run(
    db_session: Session, tmp_path: Path
) -> None:
    kept = _touch(tmp_path / "Foo.mp4")
    first = _row(db_session, kept, title="Foo", url="https://www.youtube.com/watch?v=a")
    stale = _row(
        db_session, tmp_path / "Foo (old).mp4", title="Foo", url="https://www.youtube.com/watch?v=b"
    )

    summary = migrate_library_layout(db_session, tmp_path)

    assert _summary(summary) == (1, 1, 0)
    assert first.file_path == str(tmp_path / "chan" / "foo.mp4")
    assert stale.file_path == str(tmp_path / "Foo (old).mp4")


def test_retry_only_touches_rows_that_failed(
    db_session: Session, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bad = _touch(tmp_path / "bad.mp4")
    bad_row = _row(db_session, bad, title="Bad", url="https://www.youtube.com/watch?v=bad")
    real = os.replace

    def replace(src, dst):
        raise OSError("nope")

    with monkeypatch.context() as m:
        m.setattr(os, "replace", replace)
        migrate_library_layout(db_session, tmp_path)
    # A playlist download made after the failed run must stay in its playlist folder.
    new = _touch(tmp_path / "owner" / "mix" / "ep-1.mp4")
    new_row = _row(
        db_session, new, title="Ep 1", uploader="Guest", url="https://www.youtube.com/watch?v=e"
    )
    assert real is os.replace

    summary = migrate_library_layout(db_session, tmp_path)

    assert _summary(summary) == (1, 0, 0)
    assert bad_row.file_path == str(tmp_path / "chan" / "bad.mp4")
    assert new_row.file_path == str(new) and new.exists()
