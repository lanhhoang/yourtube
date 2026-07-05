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


@dataclass(frozen=True)
class StreamSelectionValues:
    video_format_ids: list[str]
    audio_format_ids: list[str]


STREAM_FIELDS = StreamFieldNames()


def _str_value(form: FormData, key: str) -> str | None:
    value = form.get(key)
    if value is None or isinstance(value, UploadFile):
        return None
    return str(value) or None


def _str_values(form: FormData, key: str) -> list[str]:
    return [str(value) for value in form.getlist(key) if not isinstance(value, UploadFile)]


def selection_from_form(form: FormData) -> StreamSelection:
    return StreamSelection(
        video_format_id=_str_value(form, STREAM_FIELDS.video_format_id),
        audio_format_id=_str_value(form, STREAM_FIELDS.audio_format_id),
        output_template=_str_value(form, STREAM_FIELDS.output_template),
        audio_bitrate=_str_value(form, STREAM_FIELDS.audio_bitrate),
        subtitles=form.get(STREAM_FIELDS.subtitles) == "on",
    )


def selection_values_from_form(form: FormData) -> StreamSelectionValues:
    return StreamSelectionValues(
        video_format_ids=_str_values(form, STREAM_FIELDS.video_format_id),
        audio_format_ids=_str_values(form, STREAM_FIELDS.audio_format_id),
    )
