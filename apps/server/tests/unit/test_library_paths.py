from __future__ import annotations

import pytest

from app.services.library_paths import (
    PlaylistFolder,
    default_stem,
    slugify,
    video_id_from_url,
)


@pytest.mark.parametrize(
    ("raw", "slug"),
    [
        ("Linus Tech Tips", "linus-tech-tips"),
        ("Café Déjà Vu!", "cafe-deja-vu"),
        ("Привет мир", "privet-mir"),
        ("東京", "dongjing"),
        ("100% real / fake ..", "100-real-fake"),
        ("!!!", ""),
        (None, ""),
    ],
)
def test_slugify(raw, slug):
    assert slugify(raw) == slug


def test_slugify_caps_at_80_without_trailing_dash():
    s = slugify("a" * 79 + " b" * 50)
    assert len(s) <= 80 and not s.endswith("-")


def test_default_stem_single_video(tmp_path):
    info = {"id": "abc", "title": "Hello World", "channel": "Some Channel"}
    assert default_stem(info, None, tmp_path) == tmp_path / "some-channel" / "hello-world"


def test_default_stem_playlist_uses_owner(tmp_path):
    info = {"id": "abc", "title": "Ep 1", "channel": "Guest"}
    pl = PlaylistFolder(title="My Mix", channel="Owner", id="PL1")
    assert default_stem(info, pl, tmp_path) == tmp_path / "owner" / "my-mix" / "ep-1"


def test_default_stem_playlist_without_owner_uses_video_channel(tmp_path):
    pl = PlaylistFolder(title="Mix", channel=None, id="RD1")
    info = {"id": "abc", "title": "t", "channel": "Guest"}
    assert default_stem(info, pl, tmp_path) == tmp_path / "guest" / "mix" / "t"


def test_default_stem_fallbacks(tmp_path):
    info = {"id": "abc", "title": "!!!", "channel": "!!!", "channel_id": "UC1"}
    pl = PlaylistFolder(title="!!!", channel=None, id="PL1")
    assert default_stem(info, pl, tmp_path) == tmp_path / "uc1" / "pl1" / "abc"
    assert default_stem({"id": "x"}, None, tmp_path).parent.name == "unknown-channel"


def test_default_stem_collision_appends_id(tmp_path):
    (tmp_path / "c").mkdir()
    (tmp_path / "c" / "t.mp4").write_bytes(b"x")
    stem = default_stem({"id": "Ab_1", "title": "t", "channel": "c"}, None, tmp_path)
    assert stem.name == "t-ab-1"


def test_default_stem_stays_inside(tmp_path):
    info = {"id": "..", "title": "../../etc", "channel": ".."}
    stem = default_stem(info, None, tmp_path)
    assert stem.resolve().is_relative_to(tmp_path.resolve())


def test_video_id_from_url():
    assert video_id_from_url("https://www.youtube.com/watch?v=abc&list=x") == "abc"
    assert video_id_from_url("https://youtu.be/abc?t=1") == "abc"
    assert video_id_from_url("https://www.youtube.com/shorts/abc") == "abc"
    assert video_id_from_url("https://example.com/") is None
