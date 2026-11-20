from app.services.downloader import pick_subtitle_langs


def auto(*keys: str) -> dict:
    return {k: [{"ext": "srt"}] for k in keys}


def test_pick_auto_only_french() -> None:
    info = {"language": "fr", "subtitles": {}, "automatic_captions": auto("fr-orig", "fr", "en")}
    assert pick_subtitle_langs(info) == ["fr-orig"]


def test_pick_manual_english_on_english_video() -> None:
    info = {"subtitles": auto("en"), "automatic_captions": auto("en-orig", "en", "fr")}
    assert pick_subtitle_langs(info) == ["en"]


def test_pick_manual_french_and_english() -> None:
    info = {"subtitles": auto("fr", "en-GB", "de"), "automatic_captions": auto("fr-orig", "en")}
    assert pick_subtitle_langs(info) == ["fr", "en-GB"]


def test_pick_manual_english_plus_auto_original() -> None:
    info = {"subtitles": auto("en"), "automatic_captions": auto("ja-orig", "ja", "en")}
    assert pick_subtitle_langs(info) == ["en", "ja-orig"]


def test_pick_never_takes_translated_auto() -> None:
    info = {"language": "fr", "subtitles": {}, "automatic_captions": auto("en", "fr")}
    assert pick_subtitle_langs(info) == []


def test_pick_language_fallback_strips_merge_and_region() -> None:
    info = {"language": "pt-BR+pt-BR", "subtitles": auto("pt-BR"), "automatic_captions": {}}
    assert pick_subtitle_langs(info) == ["pt-BR"]


def test_pick_skips_live_chat() -> None:
    info = {"language": "en", "subtitles": auto("live_chat", "en")}
    assert pick_subtitle_langs(info) == ["en"]


def test_pick_nothing_available() -> None:
    assert pick_subtitle_langs({}) == []
