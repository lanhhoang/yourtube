from __future__ import annotations

from app.services.batch_preview import (
    expand_playlist_entries,
    expand_source_urls,
    parse_source_urls,
    resolve_batch_preview,
)


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


def test_expand_playlist_entries_returns_entry_urls_from_flat_playlist() -> None:
    def fake_extract(
        url: str,
        *,
        proxy: str | None = None,
        cookies_file: str | None = None,
    ) -> dict:
        assert proxy is None
        assert cookies_file is None
        if url == "https://example.com/list":
            return {
                "entries": [
                    {"url": "https://example.com/watch?v=1"},
                    {"webpage_url": "https://example.com/watch?v=2"},
                    {"url": "not-a-full-url"},
                ]
            }
        return {"title": "single"}

    assert expand_playlist_entries("https://example.com/list", extract_info=fake_extract) == [
        "https://example.com/watch?v=1",
        "https://example.com/watch?v=2",
    ]
    assert expand_playlist_entries("https://example.com/watch?v=3", extract_info=fake_extract) == [
        "https://example.com/watch?v=3",
    ]


def test_expand_source_urls_dedupes_and_caps_after_playlist_expansion() -> None:
    def fake_expand(url: str) -> list[str]:
        if url == "https://example.com/list":
            return [f"https://example.com/watch?v={index}" for index in range(60)]
        return [url]

    urls, truncated_count = expand_source_urls(
        ["https://example.com/list", "https://example.com/watch?v=1", "https://example.com/after"],
        expand_playlist=fake_expand,
        limit=50,
    )

    assert len(urls) == 50
    assert urls[0] == "https://example.com/watch?v=0"
    assert urls[-1] == "https://example.com/watch?v=49"
    assert truncated_count == 11


def test_expand_source_urls_falls_back_to_source_when_expansion_fails() -> None:
    def fake_expand(url: str) -> list[str]:
        if url == "https://example.com/bad-list":
            raise RuntimeError("HTTP Error 403: Forbidden")
        return [url]

    urls, truncated_count = expand_source_urls(
        ["https://example.com/bad-list"],
        expand_playlist=fake_expand,
    )

    assert urls == ["https://example.com/bad-list"]
    assert truncated_count == 0


def test_resolve_batch_preview_expands_playlist_before_metadata_lookup() -> None:
    looked_up: list[str] = []

    def fake_expand(url: str) -> list[str]:
        if url == "https://example.com/list":
            return ["https://example.com/watch?v=1", "https://example.com/watch?v=2"]
        return [url]

    def fake_extract(
        url: str,
        *,
        proxy: str | None = None,
        cookies_file: str | None = None,
    ) -> dict:
        looked_up.append(url)
        return {
            "title": f"title for {url}",
            "uploader": "Uploader",
            "duration": 12,
            "thumbnail": "https://example.com/thumb.jpg",
        }

    result = resolve_batch_preview(
        "https://example.com/list",
        extract_info=fake_extract,
        expand_playlist=fake_expand,
    )

    assert looked_up == ["https://example.com/watch?v=1", "https://example.com/watch?v=2"]
    assert [item.source_url for item in result.items] == looked_up
    assert result.valid_count == 2
    assert result.invalid_count == 0
    assert result.truncated_count == 0
