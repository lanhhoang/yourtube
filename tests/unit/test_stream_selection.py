from __future__ import annotations

from starlette.datastructures import FormData

import app.services.stream_selection as stream_selection
from app.services.stream_selection import (
    STREAM_FIELDS,
    StreamFieldNames,
    selection_from_form,
    selection_values_from_form,
)


def test_stream_fields_define_the_public_contract() -> None:
    assert STREAM_FIELDS.video_format_id == "video_format_id"
    assert STREAM_FIELDS.audio_format_id == "audio_format_id"
    assert STREAM_FIELDS.output_template == "output_template"
    assert STREAM_FIELDS.audio_bitrate == "audio_bitrate"
    assert STREAM_FIELDS.subtitles == "subtitles"


def test_selection_from_form_reads_existing_field_names() -> None:
    form = FormData(
        [
            ("video_format_id", "137"),
            ("audio_format_id", "140"),
            ("output_template", "%(title)s.%(ext)s"),
            ("audio_bitrate", "128"),
            ("subtitles", "on"),
        ]
    )

    selection = selection_from_form(form)

    assert selection.video_format_id == "137"
    assert selection.audio_format_id == "140"
    assert selection.output_template == "%(title)s.%(ext)s"
    assert selection.audio_bitrate == "128"
    assert selection.subtitles is True


def test_selection_from_form_normalizes_empty_stream_values() -> None:
    form = FormData(
        [
            ("video_format_id", ""),
            ("audio_format_id", ""),
            ("output_template", ""),
            ("audio_bitrate", ""),
        ]
    )

    selection = selection_from_form(form)

    assert selection.video_format_id is None
    assert selection.audio_format_id is None
    assert selection.output_template is None
    assert selection.audio_bitrate is None
    assert selection.subtitles is False


def test_selection_values_from_form_preserves_repeated_values_for_batch_alignment() -> None:
    form = FormData(
        [
            ("video_format_id", "137"),
            ("video_format_id", ""),
            ("audio_format_id", "140"),
            ("audio_format_id", "251"),
        ]
    )

    values = selection_values_from_form(form)

    assert values.video_format_ids == ["137", ""]
    assert values.audio_format_ids == ["140", "251"]


def test_selection_helpers_read_the_active_stream_field_contract(monkeypatch) -> None:
    monkeypatch.setattr(
        stream_selection,
        "STREAM_FIELDS",
        StreamFieldNames(
            video_format_id="picked_video",
            audio_format_id="picked_audio",
            output_template="picked_template",
            audio_bitrate="picked_bitrate",
            subtitles="picked_subtitles",
        ),
    )
    scalar_form = FormData(
        [
            ("picked_video", "137"),
            ("picked_audio", "140"),
            ("picked_template", "%(title)s.%(ext)s"),
            ("picked_bitrate", "128"),
            ("picked_subtitles", "on"),
        ]
    )
    repeated_form = FormData(
        [
            ("picked_video", "137"),
            ("picked_video", ""),
            ("picked_audio", "140"),
            ("picked_audio", "251"),
        ]
    )

    selection = selection_from_form(scalar_form)
    values = selection_values_from_form(repeated_form)

    assert selection.video_format_id == "137"
    assert selection.audio_format_id == "140"
    assert selection.output_template == "%(title)s.%(ext)s"
    assert selection.audio_bitrate == "128"
    assert selection.subtitles is True
    assert values.video_format_ids == ["137", ""]
    assert values.audio_format_ids == ["140", "251"]
