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
