from __future__ import annotations

from app.services.preview import resolve_batch_preview, resolve_single_preview


def test_resolve_single_preview_builds_picker_payload() -> None:
    def fake_extract_info(url: str, **_kwargs) -> dict:
        return {
            "title": "Example title",
            "uploader": "Uploader",
            "duration": 123,
            "thumbnail": "https://example.com/thumb.jpg",
            "formats": [
                {"format_id": "137", "ext": "mp4", "vcodec": "avc1", "acodec": "none"},
                {"format_id": "140", "ext": "m4a", "vcodec": "none", "acodec": "mp4a.40.2"},
            ],
        }

    result = resolve_single_preview(
        "https://example.com/watch?v=1",
        extract_info=fake_extract_info,
    )

    assert result.url == "https://example.com/watch?v=1"
    assert result.title == "Example title"
    assert result.picker_payload["video_streams"][0]["format_id"] == "137"
    assert result.picker_payload["audio_streams"][0]["format_id"] == "140"


def test_resolve_batch_preview_keeps_existing_batch_behavior() -> None:
    def fake_extract_info(url: str, **_kwargs) -> dict:
        if url.endswith("bad"):
            raise RuntimeError("HTTP Error 403: Forbidden")
        return {
            "title": f"title for {url}",
            "uploader": "Uploader",
            "duration": 12,
            "thumbnail": "https://example.com/thumb.jpg",
            "formats": [
                {"format_id": "137", "ext": "mp4", "vcodec": "avc1", "acodec": "none"},
                {"format_id": "140", "ext": "m4a", "vcodec": "none", "acodec": "mp4a.40.2"},
            ],
        }

    result = resolve_batch_preview(
        "https://example.com/good\nhttps://example.com/bad",
        extract_info=fake_extract_info,
    )

    assert result.valid_count == 1
    assert result.invalid_count == 1
    assert result.items[0].picker_payload["video_streams"][0]["format_id"] == "137"
    assert result.items[1].error_code == "http_forbidden"


def test_resolve_batch_preview_expands_playlists_with_flat_lookup(monkeypatch) -> None:
    def fake_extract_info(url: str, **_kwargs) -> dict:
        return {
            "title": "Episode 1",
            "uploader": "Uploader",
            "duration": 10,
            "thumbnail": "https://example.com/1.jpg",
            "formats": [],
        }

    fake_extract_flat_info = object()

    def fake_expand_playlist_entries(url: str, **kwargs) -> list[str]:
        assert url == "https://example.com/list"
        assert kwargs["extract_info"] is fake_extract_flat_info
        assert kwargs["proxy"] == "http://proxy.internal:8080"
        assert kwargs["cookies_file"] == "/tmp/cookies.txt"
        return ["https://example.com/watch?v=1"]

    monkeypatch.setattr("app.services.preview.extract_flat_info", fake_extract_flat_info)
    monkeypatch.setattr(
        "app.services.preview.expand_playlist_entries", fake_expand_playlist_entries
    )

    result = resolve_batch_preview(
        "https://example.com/list",
        extract_info=fake_extract_info,
        proxy="http://proxy.internal:8080",
        cookies_file="/tmp/cookies.txt",
    )

    assert result.valid_count == 1
    assert result.items[0].source_url == "https://example.com/watch?v=1"
