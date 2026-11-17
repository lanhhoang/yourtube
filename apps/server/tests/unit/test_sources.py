from __future__ import annotations

from typing import cast

import pytest

from app.services.sources import (
    MAX_ENTRIES,
    list_sources,
    parse_source_urls,
    playlist_url_for,
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


def _formats() -> list[dict]:
    return [
        {
            "format_id": "v1080",
            "ext": "mp4",
            "width": 1920,
            "height": 1080,
            "vcodec": "avc1",
            "acodec": "none",
        },
        {"format_id": "a1", "ext": "m4a", "vcodec": "none", "acodec": "mp4a", "abr": 128},
    ]


def _video_info(url: str = "https://e.test/v", **extra: object) -> dict:
    return {
        "id": "v",
        "title": "Vid",
        "uploader": "Up",
        "duration": 61.5,
        "webpage_url": url,
        "formats": _formats(),
        **extra,
    }


class Stubs:
    def __init__(self, flat: dict | Exception | list, full: dict | None = None) -> None:
        self.flat_calls: list[tuple] = []
        self.full_calls: list[tuple] = []
        self._flat = flat
        self._full = full

    def flat(self, url: str, **kw: object) -> dict:
        self.flat_calls.append((url, kw))
        value = self._flat
        if isinstance(value, dict) and url in value and isinstance(value[url], (dict, Exception)):
            value = value[url]
        if isinstance(value, Exception):
            raise value
        return cast(dict, value)

    def full(self, url: str, **kw: object) -> dict:
        self.full_calls.append((url, kw))
        assert self._full is not None
        return self._full


def _run(raw: str, stubs: Stubs):
    return list_sources(
        raw, extract_flat=stubs.flat, extract_full=stubs.full, proxy=None, cookies_file=None
    )


def test_single_video_returns_video_kind() -> None:
    s = Stubs(_video_info())
    r = _run("https://e.test/v", s)
    assert r.kind == "video" and r.entries == [] and r.skipped == 0 and r.title is None
    assert r.video is not None and r.video.best_short_side == 1080 and r.video.duration == 61
    assert s.full_calls == []


def test_flat_without_formats_falls_back_to_full() -> None:
    flat = {"id": "v", "title": "Vid"}
    s = Stubs(flat, full=_video_info())
    r = _run("https://e.test/v", s)
    assert r.kind == "video" and r.video is not None
    assert len(s.full_calls) == 1 and s.full_calls[0][1]["noplaylist"] is True


def test_watch_with_list_opens_video() -> None:
    pasted = "https://www.youtube.com/watch?v=abc&list=PL1"
    s = Stubs(_video_info("https://www.youtube.com/watch?v=abc"))
    r = _run(pasted, s)
    assert s.flat_calls[0][1]["noplaylist"] is True
    assert r.video is not None
    assert r.video.url == "https://www.youtube.com/watch?v=abc"
    assert r.video.playlist_url == "https://www.youtube.com/playlist?list=PL1"


def test_video_url_falls_back_to_pasted() -> None:
    info = _video_info()
    del info["webpage_url"]
    r = _run("https://e.test/pasted", Stubs(info))
    assert r.video is not None and r.video.url == "https://e.test/pasted"


def _playlist(n: int, prefix: str = "a", title: str = "PL") -> dict:
    return {
        "title": title,
        "entries": [
            {"url": f"https://e.test/{prefix}{i}", "title": f"T{i}", "duration": 61.5}
            for i in range(n)
        ],
    }


def test_playlist_returns_all_entries_no_paging() -> None:
    r = _run("https://e.test/pl", Stubs(_playlist(120)))
    assert r.kind == "list" and len(r.entries) == 120 and r.skipped == 0 and r.title == "PL"
    assert r.entries[0].index == 0 and r.entries[0].details is None


def test_list_sources_dedupes_across_sources() -> None:
    stubs = Stubs({"https://e.test/p1": _playlist(3, "x"), "https://e.test/p2": _playlist(3, "x")})
    r = _run("https://e.test/p1 https://e.test/p2", stubs)
    assert [e.url for e in r.entries] == [
        "https://e.test/x0",
        "https://e.test/x1",
        "https://e.test/x2",
    ]
    assert [e.index for e in r.entries] == [0, 1, 2] and r.title is None


def test_list_sources_caps_at_500() -> None:
    r = _run("https://e.test/pl", Stubs(_playlist(650)))
    assert len(r.entries) == MAX_ENTRIES == 500 and r.skipped == 150 and r.entries[-1].index == 499


def test_float_duration_becomes_int() -> None:
    r = _run("https://e.test/pl", Stubs(_playlist(1)))
    assert r.entries[0].duration == 61


def test_invalid_entry_becomes_error_entry() -> None:
    r = _run("https://e.test/pl", Stubs({"title": "PL", "entries": [{"title": "no url"}]}))
    assert r.entries[0].error_code == "invalid_playlist_entry"


def test_multi_url_failure_becomes_error_entry() -> None:
    stubs = Stubs(
        {"https://e.test/ok": _playlist(2), "https://e.test/bad": RuntimeError("HTTP Error 403")}
    )
    r = _run("https://e.test/ok https://e.test/bad", stubs)
    assert r.kind == "list" and len(r.entries) == 3
    bad = r.entries[-1]
    assert bad.error_code is not None and bad.url == "https://e.test/bad"


def test_single_url_failure_raises() -> None:
    with pytest.raises(RuntimeError):
        _run("https://e.test/bad", Stubs(RuntimeError("boom")))


def test_no_urls_raises() -> None:
    with pytest.raises(ValueError, match="No URLs found"):
        _run("hello", Stubs({}))


def test_playlist_url_for_ignores_non_youtube() -> None:
    assert playlist_url_for("https://example.com/watch?v=1&list=2") is None
    assert (
        playlist_url_for("https://youtu.be/abc?list=PL9")
        == "https://www.youtube.com/playlist?list=PL9"
    )
    assert playlist_url_for("https://www.youtube.com/watch?v=abc") is None


def test_flat_redirect_is_followed_to_the_video() -> None:
    redirect = {"_type": "url", "url": "https://e.test/real"}
    s = Stubs(
        {
            "https://e.test/short": redirect,
            "https://e.test/real": _video_info("https://e.test/real"),
        }
    )
    r = _run("https://e.test/short", s)
    assert r.kind == "video" and r.video is not None and r.video.url == "https://e.test/real"
    assert s.full_calls == []


def test_flat_redirect_to_playlist_is_a_list() -> None:
    s = Stubs(
        {
            "https://e.test/chan": {"_type": "url", "url": "https://e.test/chan/videos"},
            "https://e.test/chan/videos": _playlist(3, "c"),
        }
    )
    r = _run("https://e.test/chan", s)
    assert r.kind == "list" and len(r.entries) == 3


def test_full_lookup_that_returns_a_playlist_is_a_list() -> None:
    # flat gives no entries and no formats, but the full lookup resolves a whole playlist
    s = Stubs({"id": "x"}, full=_playlist(4, "f"))
    r = _run("https://e.test/odd", s)
    assert r.kind == "list" and len(r.entries) == 4
