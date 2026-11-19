"""One-off move of existing library files into ``<channel>/<title>.<ext>``."""

from __future__ import annotations

import logging
import os
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import resolve_repo_path
from app.models import Download
from app.services.library_paths import first_slug, video_id_from_url
from app.services.settings import get_setting, set_setting

logger = logging.getLogger("yourtube")

LAYOUT_KEY = "library_layout"
LAYOUT_VERSION = "v2"
# Highest row id at the first attempt. A retry ignores newer rows, which the new downloader
# already saved in their final folders (playlist folders included).
CUTOFF_KEY = "library_layout_cutoff"

_SIDECAR_EXTS = {"srt", "vtt", "txt"}


@dataclass
class LayoutSummary:
    moved: int = 0
    skipped: int = 0
    failed: int = 0


def _sidecars(video: Path, other_stems: set[tuple[Path, str]]) -> list[tuple[Path, str]]:
    """Sidecars of ``video`` as ``(path, rest)``, where ``rest`` follows ``<stem>.``.

    A sidecar is ``<stem>.<ext>`` or ``<stem>.<lang>.<ext>``. Files that start with another
    row's longer stem belong to that row's video.
    """
    found: list[tuple[Path, str]] = []
    prefix = video.stem + "."
    try:
        names = sorted(video.parent.iterdir())
    except OSError:
        return found
    for path in names:
        if path == video or not path.name.startswith(prefix) or not path.is_file():
            continue
        rest = path.name[len(prefix) :]
        parts = rest.split(".")
        if len(parts) > 2 or parts[-1].lower() not in _SIDECAR_EXTS:
            continue
        if any(
            parent == video.parent
            and len(stem) > len(video.stem)
            and path.name.startswith(stem + ".")
            for parent, stem in other_stems
        ):
            continue
        found.append((path, rest))
    return found


def migrate_library_layout(session: Session, downloads_dir: Path) -> LayoutSummary | None:
    """Move done rows' files into channel folders. ``None`` when already done."""
    if get_setting(session, LAYOUT_KEY) == LAYOUT_VERSION:
        return None

    root = downloads_dir.resolve()
    cutoff_raw = get_setting(session, CUTOFF_KEY)
    if cutoff_raw is None:
        cutoff = session.scalar(select(func.max(Download.id))) or 0
        set_setting(session, CUTOFF_KEY, str(cutoff))
    else:
        cutoff = int(cutoff_raw)
    rows = session.scalars(
        select(Download)
        .where(Download.status == "done", Download.file_path.is_not(None), Download.id <= cutoff)
        .order_by(Download.id)
    ).all()
    groups: dict[Path, list[Download]] = defaultdict(list)
    for row in rows:
        if row.file_path:
            groups[resolve_repo_path(row.file_path).resolve()].append(row)

    summary = LayoutSummary()
    claimed: set[Path] = set()
    for src, members in groups.items():
        _move_group(session, downloads_dir, root, src, members, groups, claimed, summary)

    logger.info(
        "library layout %s: moved=%d skipped=%d failed=%d",
        LAYOUT_VERSION,
        summary.moved,
        summary.skipped,
        summary.failed,
    )
    # A failed move leaves the flag unset so the next start retries it.
    if summary.failed == 0:
        set_setting(session, LAYOUT_KEY, LAYOUT_VERSION)
    return summary


def _move_group(
    session: Session,
    downloads_dir: Path,
    root: Path,
    src: Path,
    members: list[Download],
    groups: dict[Path, list[Download]],
    claimed: set[Path],
    summary: LayoutSummary,
) -> None:
    if not src.is_relative_to(root):
        logger.info("library layout: %s is outside the downloads folder, skipped", src)
        summary.skipped += 1
        return

    row = members[0]
    video_id = video_id_from_url(row.url)
    title = first_slug(row.title, video_id, fallback=f"download-{row.id}")
    suffix = src.suffix
    folder = downloads_dir / first_slug(row.uploader, fallback="unknown-channel")
    target = folder / (title + suffix)
    alt_title = f"{title}-{first_slug(video_id, fallback=str(row.id))}"
    alternative = folder / (alt_title + suffix)
    others = {path for path in groups if path != src}

    def point_rows_at(path: Path) -> None:
        for member in members:
            member.file_path = str(path)
        session.commit()
        claimed.add(path.resolve())
        summary.moved += 1

    if not src.exists():
        # A crash after ``os.replace`` but before the commit leaves the file at its target.
        for candidate in (target, alternative):
            resolved = candidate.resolve()
            if candidate.exists() and resolved not in others and resolved not in claimed:
                point_rows_at(candidate)
                return
        summary.skipped += 1
        return

    if src in (target.resolve(), alternative.resolve()):
        summary.skipped += 1
        return

    other_stems = {(path.parent, path.stem) for path in others}
    sidecars = _sidecars(src, other_stems)
    dest: Path | None = None
    for candidate in (target, alternative):
        names = [
            candidate,
            *(candidate.with_name(f"{candidate.stem}.{rest}") for _, rest in sidecars),
        ]
        if not any(name.exists() for name in names):
            dest = candidate
            break
    if dest is None:
        logger.warning("library layout: no free target for %s, skipped", src)
        summary.skipped += 1
        return

    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
        os.replace(src, dest)
    except OSError:
        logger.exception("library layout: could not move %s", src)
        summary.failed += 1
        return
    for old, rest in sidecars:
        try:
            os.replace(old, dest.with_name(f"{dest.stem}.{rest}"))
        except OSError:
            logger.exception("library layout: could not move sidecar %s", old)
    point_rows_at(dest)
