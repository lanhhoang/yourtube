from __future__ import annotations

from itertools import zip_longest

from starlette.datastructures import FormData, UploadFile

from app.schemas import DownloadCreate
from app.services.batch_preview import parse_source_urls
from app.services.stream_selection import selection_from_form, selection_values_from_form


def _form_str(form: FormData, key: str) -> str | None:
    value = form.get(key)
    if value is None or isinstance(value, UploadFile):
        return None
    return str(value)


def _form_values(form: FormData, key: str) -> list[str]:
    return [str(value) for value in form.getlist(key) if not isinstance(value, UploadFile)]


def _selected_indices(form: FormData) -> list[int]:
    indices: list[int] = []
    seen: set[int] = set()
    for value in _form_values(form, "selected_index"):
        if not value.isdecimal():
            continue
        try:
            index = int(value)
        except ValueError:
            continue
        if index in seen:
            continue
        seen.add(index)
        indices.append(index)
    return indices


def build_single_download(form: FormData) -> tuple[DownloadCreate, str]:
    duration_raw = _form_str(form, "duration")
    target_id = _form_str(form, "target_id")
    selection = selection_from_form(form)
    if target_id != "batch-status":
        target_id = "info-status"
    payload = DownloadCreate(
        url=_form_str(form, "url") or "",
        title=_form_str(form, "title"),
        uploader=_form_str(form, "uploader"),
        duration=int(duration_raw) if duration_raw else None,
        thumbnail=_form_str(form, "thumbnail"),
        video_format_id=selection.video_format_id,
        audio_format_id=selection.audio_format_id,
        output_template=selection.output_template,
        audio_bitrate=selection.audio_bitrate,
        subtitles=selection.subtitles,
    )
    return payload, target_id


def build_batch_downloads(form: FormData) -> list[DownloadCreate]:
    selected_values = _form_values(form, "selected_index")
    if selected_values:
        payloads: list[DownloadCreate] = []
        for index in _selected_indices(form):
            url = _form_str(form, f"url_{index}")
            if not url:
                continue
            duration_raw = _form_str(form, f"duration_{index}")
            selection = selection_from_form(form, suffix=f"_{index}")
            payloads.append(
                DownloadCreate(
                    url=url,
                    title=_form_str(form, f"title_{index}") or None,
                    uploader=_form_str(form, f"uploader_{index}") or None,
                    duration=int(duration_raw) if duration_raw else None,
                    thumbnail=_form_str(form, f"thumbnail_{index}") or None,
                    video_format_id=selection.video_format_id,
                    audio_format_id=selection.audio_format_id,
                    output_template=selection.output_template,
                    audio_bitrate=selection.audio_bitrate,
                    subtitles=selection.subtitles,
                )
            )
        return payloads

    raw_sources = _form_str(form, "sources") or ""
    urls = parse_source_urls(raw_sources)
    if urls:
        return [DownloadCreate(url=url) for url in urls]

    selection_values = selection_values_from_form(form)
    payloads: list[DownloadCreate] = []
    for url, title, uploader, duration, thumbnail, video_id, audio_id in zip_longest(
        _form_values(form, "url"),
        _form_values(form, "title"),
        _form_values(form, "uploader"),
        _form_values(form, "duration"),
        _form_values(form, "thumbnail"),
        selection_values.video_format_ids,
        selection_values.audio_format_ids,
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
