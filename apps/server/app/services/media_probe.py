"""ffprobe-based codec and dynamic-range detection for library items."""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
import threading
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.config import resolve_repo_path
from app.db import SessionLocal
from app.models import Download

logger = logging.getLogger("yourtube")

PROBE_TIMEOUT_SECONDS = 30


@dataclass(frozen=True)
class ProbeResult:
    """Codecs and dynamic range read from a media file."""

    vcodec: str | None
    acodec: str | None
    dynamic_range: str | None


def probe_media(path: Path) -> ProbeResult | None:
    """Probe ``path`` with ffprobe; ``None`` when probing is not possible."""
    ffprobe = shutil.which("ffprobe")
    if ffprobe is None:
        return None
    try:
        proc = subprocess.run(
            ["ffprobe", "-v", "error", "-show_streams", "-of", "json", str(path)],
            capture_output=True,
            timeout=PROBE_TIMEOUT_SECONDS,
            check=False,
        )
        if proc.returncode != 0:
            return None
        data = json.loads(proc.stdout)
    except (subprocess.TimeoutExpired, OSError, ValueError):
        return None
    streams = data.get("streams") if isinstance(data, dict) else None
    if not isinstance(streams, list):
        return None
    video = next(
        (
            s
            for s in streams
            if isinstance(s, dict)
            and s.get("codec_type") == "video"
            and (s.get("disposition") or {}).get("attached_pic") != 1
        ),
        None,
    )
    audio = next(
        (s for s in streams if isinstance(s, dict) and s.get("codec_type") == "audio"), None
    )
    dynamic_range = None
    if video is not None:
        transfer = video.get("color_transfer")
        dynamic_range = (
            "HDR10" if transfer == "smpte2084" else "HLG" if transfer == "arib-std-b67" else "SDR"
        )
    return ProbeResult(
        vcodec=video.get("codec_name") if video else None,
        acodec=audio.get("codec_name") if audio else None,
        dynamic_range=dynamic_range,
    )


def backfill_media_info(session: Session) -> int:
    """Probe finished downloads that lack codec info; return rows updated."""
    candidates = [
        (row_id, file_path)
        for row_id, file_path in session.execute(
            select(Download.id, Download.file_path).where(
                Download.status == "done",
                Download.vcodec.is_(None),
                Download.acodec.is_(None),
                Download.file_path.is_not(None),
            )
        ).all()
        if file_path
    ]
    updated = 0
    for row_id, file_path in candidates:
        path = resolve_repo_path(file_path)
        if not path.is_file():
            continue
        result = probe_media(path)
        if result is None:
            continue
        outcome = session.execute(
            update(Download)
            .where(
                Download.id == row_id,
                Download.status == "done",
                Download.vcodec.is_(None),
                Download.acodec.is_(None),
            )
            .values(
                vcodec=result.vcodec,
                acodec=result.acodec,
                dynamic_range=result.dynamic_range,
            )
        )
        session.commit()
        updated += outcome.rowcount
    return updated


def _run_backfill() -> None:
    try:
        with SessionLocal() as session:
            count = backfill_media_info(session)
        logger.info("media backfill updated %d item(s)", count)
    except Exception:  # noqa: BLE001 - a background failure must not surface
        logger.exception("media backfill failed")


def start_media_backfill() -> threading.Thread:
    """Run the backfill on a daemon thread so startup is never blocked."""
    thread = threading.Thread(target=_run_backfill, name="media-backfill", daemon=True)
    thread.start()
    return thread
