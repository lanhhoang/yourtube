"""Map raw yt-dlp error strings to stable codes and user-facing messages.

The mapping is intentionally simple and regex-free for readability: each
rule lowercases the raw message and checks for a stable substring. The
returned ``code`` is a stable, machine-friendly identifier that callers
persist on the ``downloads`` row and surface in API responses. The
``message`` is a short, human-friendly sentence that the UI can show to
end users.
"""

from __future__ import annotations

import re

# Pre-compiled substring patterns. Order matters: more specific rules
# (e.g. "permission denied" matching "no permission") come before
# generic ones (e.g. "denied").
_RULES: list[tuple[str, str, re.Pattern[str]]] = [
    (
        "private_or_age_restricted",
        "This video is private or age-restricted.",
        re.compile(r"private|age[- ]?restrict|sign in to confirm your age", re.IGNORECASE),
    ),
    (
        "geo_blocked",
        "This video is not available in your country.",
        re.compile(
            r"geo[- ]?blocked|not available in your country|not available in your region",
            re.IGNORECASE,
        ),
    ),
    (
        "http_forbidden",
        "The server returned a 403 Forbidden response.",
        re.compile(r"\b403\b|forbidden", re.IGNORECASE),
    ),
    (
        "timeout",
        "The download timed out. Check your network connection and try again.",
        re.compile(r"timed?\s*out|timeout", re.IGNORECASE),
    ),
    (
        "disk_full",
        "There is not enough free disk space to save the file.",
        re.compile(r"no space left|disk full", re.IGNORECASE),
    ),
    (
        "permission_denied",
        "The app does not have permission to write the output file.",
        re.compile(r"permission denied", re.IGNORECASE),
    ),
]


def friendly_ytdlp_error(raw: str) -> tuple[str, str]:
    """Map a raw yt-dlp error string to a ``(code, message)`` pair.

    Returns the first matching rule's code and message, or a generic
    fallback ``("ytdlp_error", ...)`` when no rule matches.
    """
    for code, message, pattern in _RULES:
        if pattern.search(raw):
            return code, message
    return "ytdlp_error", "The download failed for an unknown reason."
