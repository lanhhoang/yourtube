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
