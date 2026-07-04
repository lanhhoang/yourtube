from __future__ import annotations

from app.services.batch_preview import parse_source_urls


def test_parse_source_urls_splits_on_whitespace_commas_and_newlines() -> None:
    raw = """
    https://example.com/a
    https://example.com/b, https://example.com/c

    https://example.com/d
    """

    assert parse_source_urls(raw) == [
        "https://example.com/a",
        "https://example.com/b",
        "https://example.com/c",
        "https://example.com/d",
    ]


def test_parse_source_urls_dedupes_exact_urls_in_first_seen_order() -> None:
    raw = "https://example.com/a https://example.com/a\nhttps://example.com/b,https://example.com/a"

    assert parse_source_urls(raw) == [
        "https://example.com/a",
        "https://example.com/b",
    ]


def test_parse_source_urls_preserves_commas_inside_urls() -> None:
    raw = "https://example.com/a,b https://example.com/c"

    assert parse_source_urls(raw) == [
        "https://example.com/a,b",
        "https://example.com/c",
    ]


def test_resolve_batch_preview_returns_ready_items_for_valid_direct_urls() -> None:
    from app.services.batch_preview import BatchPreviewResult, resolve_batch_preview

    def fake_extract(
        url: str,
        *,
        proxy: str | None = None,
        cookies_file: str | None = None,
    ) -> dict:
        assert proxy is None
        assert cookies_file is None
        return {
            "title": f"title for {url}",
            "uploader": "Uploader",
            "duration": 12,
            "thumbnail": "https://example.com/thumb.jpg",
        }

    result = resolve_batch_preview(
        "https://example.com/a\nhttps://example.com/b",
        extract_info=fake_extract,
    )

    assert isinstance(result, BatchPreviewResult)
    assert result.valid_count == 2
    assert result.invalid_count == 0
    assert [item.source_url for item in result.items] == [
        "https://example.com/a",
        "https://example.com/b",
    ]
    assert [item.status for item in result.items] == ["ready", "ready"]
    assert result.items[0].title == "title for https://example.com/a"


def test_resolve_batch_preview_marks_lookup_failures_without_stopping_batch() -> None:
    from app.services.batch_preview import resolve_batch_preview

    def fake_extract(
        url: str,
        *,
        proxy: str | None = None,
        cookies_file: str | None = None,
    ) -> dict:
        if url.endswith("bad"):
            raise RuntimeError("HTTP Error 403: Forbidden")
        return {
            "title": f"title for {url}",
            "uploader": "Uploader",
            "duration": 12,
            "thumbnail": "https://example.com/thumb.jpg",
        }

    result = resolve_batch_preview(
        "https://example.com/good\nhttps://example.com/bad",
        extract_info=fake_extract,
    )

    assert result.valid_count == 1
    assert result.invalid_count == 1
    assert result.items[0].status == "ready"
    assert result.items[0].title == "title for https://example.com/good"
    assert result.items[1].status == "error"
    assert result.items[1].error_code == "http_forbidden"
    assert result.items[1].error_message == "The server returned a 403 Forbidden response."


def test_resolve_batch_preview_rejects_playlist_results_for_direct_only_phase() -> None:
    from app.services.batch_preview import resolve_batch_preview

    def fake_extract(
        url: str,
        *,
        proxy: str | None = None,
        cookies_file: str | None = None,
    ) -> dict:
        return {
            "_type": "playlist",
            "title": "Playlist",
            "entries": [{"url": "https://example.com/watch?v=1"}],
        }

    result = resolve_batch_preview("https://example.com/playlist", extract_info=fake_extract)

    assert result.valid_count == 0
    assert result.invalid_count == 1
    assert result.items[0].status == "error"
    assert result.items[0].error_code == "unsupported_playlist"
    assert result.items[0].error_message == "Playlist previews are not supported yet."
