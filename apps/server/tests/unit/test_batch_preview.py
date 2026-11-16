from __future__ import annotations

from app.services.batch_preview import (
    expand_playlist_entries,
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


def test_parse_source_urls_preserves_repeated_sources_when_dedupe_is_disabled() -> None:
    raw = "https://example.com/a https://example.com/a\nhttps://example.com/b,https://example.com/a"

    assert parse_source_urls(raw, dedupe=False) == [
        "https://example.com/a",
        "https://example.com/a",
        "https://example.com/b",
        "https://example.com/a",
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


def test_resolve_batch_preview_attaches_stream_picker_payload_to_ready_items() -> None:
    def fake_extract(
        url: str,
        *,
        proxy: str | None = None,
        cookies_file: str | None = None,
    ) -> dict:
        assert proxy is None
        assert cookies_file is None
        return {
            "title": "Ready",
            "formats": [
                {
                    "format_id": "137",
                    "ext": "mp4",
                    "vcodec": "avc1.640028",
                    "acodec": "none",
                    "resolution": "1080p",
                },
                {
                    "format_id": "140",
                    "ext": "m4a",
                    "vcodec": "none",
                    "acodec": "mp4a.40.2",
                    "abr": 128.0,
                    "audio_channels": 2,
                },
            ],
        }

    result = resolve_batch_preview("https://example.com/a", extract_info=fake_extract)

    payload = result.items[0].picker_payload
    assert payload["video_streams"][0]["format_id"] == "137"
    assert payload["audio_streams"][0]["format_id"] == "140"
    assert payload["expected_container_by_pair"]["137|140"] == "mp4"


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


def test_expand_playlist_entries_resolves_urls_in_priority_order() -> None:
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
                    {
                        "webpage_url": "https://example.com/watch?v=webpage",
                        "url": "https://example.com/watch?v=url",
                        "id": "webpage-id",
                        "title": "Webpage URL",
                    },
                    {
                        "webpage_url": "not-a-full-url",
                        "url": "https://example.com/watch?v=url",
                        "id": "url-id",
                        "title": "Full URL",
                    },
                    {
                        "url": "/watch?v=relative",
                        "id": "id-only",
                        "title": "ID fallback",
                    },
                ]
            }
        return {"title": "single"}

    entries = expand_playlist_entries("https://example.com/list", extract_info=fake_extract)

    assert [entry.source_url for entry in entries] == [
        "https://example.com/watch?v=webpage",
        "https://example.com/watch?v=url",
        "https://www.youtube.com/watch?v=id-only",
    ]
    assert [entry.title for entry in entries] == [
        "Webpage URL",
        "Full URL",
        "ID fallback",
    ]


def test_expand_playlist_entries_accepts_lazy_entry_iterables() -> None:
    def fake_extract(
        url: str,
        *,
        proxy: str | None = None,
        cookies_file: str | None = None,
    ) -> dict:
        return {"entries": ({"url": f"https://example.com/watch?v={index}"} for index in range(2))}

    entries = expand_playlist_entries("https://example.com/list", extract_info=fake_extract)

    assert [entry.source_url for entry in entries] == [
        "https://example.com/watch?v=0",
        "https://example.com/watch?v=1",
    ]


def test_expand_playlist_entries_keeps_invalid_entries_visible_with_positions() -> None:
    def fake_extract(
        url: str,
        *,
        proxy: str | None = None,
        cookies_file: str | None = None,
    ) -> dict:
        return {"entries": [{"id": "ready"}, {}, "not-a-dict"]}

    entries = expand_playlist_entries("https://example.com/list", extract_info=fake_extract)

    assert [entry.source_url for entry in entries] == [
        "https://www.youtube.com/watch?v=ready",
        "https://example.com/list",
        "https://example.com/list",
    ]
    assert [entry.title for entry in entries] == [None, "Playlist entry 2", "Playlist entry 3"]
    assert [entry.error_code for entry in entries] == [
        None,
        "invalid_playlist_entry",
        "invalid_playlist_entry",
    ]
    assert entries[1].error_message is not None
    assert entries[2].error_message is not None
    assert "Playlist entry 2" in entries[1].error_message
    assert "Playlist entry 3" in entries[2].error_message


def test_expand_playlist_entries_distinguishes_empty_and_malformed_results() -> None:
    def fake_extract(
        url: str,
        *,
        proxy: str | None = None,
        cookies_file: str | None = None,
    ) -> dict:
        if url.endswith("empty"):
            return {"entries": []}
        return {"entries": "not-an-entry-list"}

    assert expand_playlist_entries("https://example.com/empty", extract_info=fake_extract) == []

    malformed = expand_playlist_entries("https://example.com/malformed", extract_info=fake_extract)
    assert len(malformed) == 1
    assert malformed[0].source_url == "https://example.com/malformed"
    assert malformed[0].error_code == "invalid_playlist_entries"
    assert malformed[0].error_message == "Playlist entries could not be read."


def test_resolve_batch_preview_dedupes_expanded_urls_without_a_cap() -> None:
    def fake_expand(url: str) -> list[str]:
        if url == "https://example.com/list":
            return [f"https://example.com/watch?v={index}" for index in range(60)]
        return [url]

    def fake_extract(
        url: str,
        *,
        proxy: str | None = None,
        cookies_file: str | None = None,
    ) -> dict:
        return {
            "title": url,
            "uploader": "Uploader",
            "duration": 12,
            "thumbnail": "https://example.com/thumb.jpg",
        }

    result = resolve_batch_preview(
        "https://example.com/list https://example.com/watch?v=1 https://example.com/after",
        extract_info=fake_extract,
        expand_playlist=fake_expand,
    )

    assert len(result.items) == 20
    assert result.items[0].source_url == "https://example.com/watch?v=0"
    assert result.items[-1].source_url == "https://example.com/watch?v=19"
    assert result.total_count == 61
    assert result.total_pages == 4
    assert result.has_next is True
    assert result.truncated_count == 0


def test_resolve_batch_preview_extracts_metadata_only_for_the_clamped_page() -> None:
    looked_up: list[str] = []

    def fake_expand(url: str) -> list[str]:
        if url == "https://example.com/list":
            return [
                "https://example.com/watch?v=1",
                "https://example.com/watch?v=2",
                "https://example.com/watch?v=3",
            ]
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
        page=99,
        page_size=2,
    )

    assert looked_up == ["https://example.com/watch?v=3"]
    assert [item.source_url for item in result.items] == looked_up
    assert result.page == 2
    assert result.page_size == 2
    assert result.total_count == 3
    assert result.total_pages == 2
    assert result.has_previous is True
    assert result.has_next is False
    assert result.valid_count == 1
    assert result.invalid_count == 0
    assert result.truncated_count == 0


def test_resolve_batch_preview_keeps_expanded_error_candidates_on_their_page() -> None:
    def fake_expand(url: str):
        return expand_playlist_entries(url, extract_info=fake_flat_extract)

    def fake_flat_extract(
        url: str,
        *,
        proxy: str | None = None,
        cookies_file: str | None = None,
    ) -> dict:
        if url.endswith("list"):
            return {"entries": [{"id": "ready"}, {}]}
        return {}

    looked_up: list[str] = []

    def fake_extract(
        url: str,
        *,
        proxy: str | None = None,
        cookies_file: str | None = None,
    ) -> dict:
        looked_up.append(url)
        return {"title": url, "formats": []}

    result = resolve_batch_preview(
        "https://example.com/list https://example.com/direct",
        extract_info=fake_extract,
        expand_playlist=fake_expand,
        page_size=3,
    )

    assert [item.status for item in result.items] == ["ready", "error", "ready"]
    assert result.items[1].title == "Playlist entry 2"
    assert result.items[1].error_code == "invalid_playlist_entry"
    assert looked_up == ["https://www.youtube.com/watch?v=ready", "https://example.com/direct"]
    assert result.valid_count == 2
    assert result.invalid_count == 1


def test_resolve_batch_preview_keeps_invalid_entries_from_repeated_playlists() -> None:
    def fake_expand(url: str):
        return expand_playlist_entries(url, extract_info=fake_flat_extract)

    def fake_flat_extract(
        url: str,
        *,
        proxy: str | None = None,
        cookies_file: str | None = None,
    ) -> dict:
        return {"entries": [{"id": "ready"}, {}]}

    looked_up: list[str] = []

    def fake_extract(
        url: str,
        *,
        proxy: str | None = None,
        cookies_file: str | None = None,
    ) -> dict:
        looked_up.append(url)
        return {"title": url, "formats": []}

    result = resolve_batch_preview(
        "https://example.com/list https://example.com/list",
        extract_info=fake_extract,
        expand_playlist=fake_expand,
    )

    assert [item.status for item in result.items] == ["ready", "error", "error"]
    assert looked_up == ["https://www.youtube.com/watch?v=ready"]
    assert result.valid_count == 1
    assert result.invalid_count == 2


def test_resolve_batch_preview_normalizes_empty_pages() -> None:
    result = resolve_batch_preview(
        "",
        extract_info=lambda _url, **_kwargs: {},
        page=7,
        page_size=0,
    )

    assert result.items == []
    assert result.page == 1
    assert result.page_size == 1
    assert result.total_count == 0
    assert result.total_pages == 1
    assert result.has_previous is False
    assert result.has_next is False


def test_resolve_batch_preview_continues_after_playlist_expansion_fallback_fails() -> None:
    def fake_expand(url: str) -> list[str]:
        if url.endswith("bad-list"):
            raise RuntimeError("HTTP Error 403: Forbidden")
        return [url]

    def fake_extract(
        url: str,
        *,
        proxy: str | None = None,
        cookies_file: str | None = None,
    ) -> dict:
        if url.endswith("bad-list"):
            raise RuntimeError("HTTP Error 403: Forbidden")
        return {"title": "Good", "formats": []}

    result = resolve_batch_preview(
        "https://example.com/bad-list https://example.com/good",
        extract_info=fake_extract,
        expand_playlist=fake_expand,
    )

    assert result.valid_count == 1
    assert result.invalid_count == 1
    assert result.items[0].source_url == "https://example.com/bad-list"
    assert result.items[0].status == "error"
    assert result.items[0].error_code == "http_forbidden"
    assert result.items[0].error_message == "The server returned a 403 Forbidden response."
    assert result.items[1].source_url == "https://example.com/good"
    assert result.items[1].status == "ready"
