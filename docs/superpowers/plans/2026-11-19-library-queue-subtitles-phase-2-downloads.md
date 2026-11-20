# Phase 2: Quieter, sturdier downloads Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop the SABR `web_embedded` warning, never request auto-translated subtitles, and keep the video when a subtitle download fails.

**Usable result:** Download a playlist with subtitles on: no SABR warning in the log, no `HTTP Error 429` job failures; a French video gets `fr-orig` subtitles, and a subtitle failure leaves a finished video.

**Spec:** `docs/superpowers/specs/2026-11-19-library-queue-subtitles-design.md`

**Parent plan:** `docs/superpowers/plans/2026-11-19-library-queue-subtitles.md`, Tasks 3, 4, 5. The tasks below are copied from it verbatim; the parent plan wins if they ever differ. Phase index: `docs/superpowers/plans/2026-11-19-library-queue-subtitles-phases.md`.

**Prerequisites:** None. Server only (`downloader.py`). The warning is not stored until Phase 3.

## Global Constraints

- Run `pnpm check` (repo root) before every commit. Run `pnpm format` to fix formatting. After any API schema change, run `pnpm typegen` and commit `apps/web/src/lib/api.gen.ts`.
- Stack stays: FastAPI + yt-dlp + SQLite (Alembic) + worker threads; Svelte 5 + Vite + Tailwind 4; one process, one port. No new dependencies.
- `DESIGN.md` is the visual contract: red is the only accent, WCAG AA in both themes, 8 px control radius, pill buttons, 120–200 ms ease-out motion, 2 px `fg` focus outline, status never shown by colour alone. Phone is below 768 px: 44 px tap targets, 16 px inputs.
- UI tasks: before editing, read `~/.agents/skills/impeccable/reference/craft-floor.md` and `reference/operate.md` (this is an Operate surface: precision and restraint, known patterns). Use `~/.config/pi/skills/design-taste-frontend/SKILL.md` §6 "Never" as the anti-slop checklist. No new visual language, no decorative extras.
- yt-dlp never gets global `ignoreerrors`. Media failures must still fail the job.
- Never request an auto-translated subtitle track (any `automatic_captions` key except `<lang>-orig`).
- Bulk delete touches only `done` rows and their own files and sidecars, and always confirms first.
- Database changes go through one new Alembic revision, `20261119120000`, whose `down_revision` is `20261118130000`. Never edit an existing revision.
- Follow the existing test layout: pytest `tests/unit`, `tests/api`, `tests/test_db.py`; Vitest `apps/web/test`; Playwright `apps/web/e2e` (stubbed server `apps/server/tests/e2e_server.py`).

## Review Focus

1. A French video with auto captions only, on a cookie-authenticated session, gets `fr-orig`, never translated `en`, and no SABR warning.
2. A subtitle 429 retries once without subtitles and the job ends `done`; a media error (403) is not retried and still fails.
3. The `output_template` branch now resolves first; the output-dir guard (`match_filter`) still applies on both branches.

---

### Task 3: Drop `web_embedded` from the player clients

**Files:**
- Modify: `apps/server/app/services/downloader.py:230`
- Test: `apps/server/tests/unit/test_downloader_runtime_resolution.py:25-38`

**Interfaces:**
- Produces: `build_ytdlp_options(...)["extractor_args"] == {"youtube": {"player_client": ["default", "-web_embedded"]}}`

- [ ] **Step 1: Rewrite the failing test.** Rename `test_build_ytdlp_options_avoids_youtube_android_vr_403` to `test_player_client_excludes_web_embedded` and assert:

```python
assert options["extractor_args"] == {"youtube": {"player_client": ["default", "-web_embedded"]}}
assert options["js_runtimes"] == {"node": {"path": "node"}}
assert "remote_components" not in options
```

Add a docstring line: with cookies, yt-dlp's default set includes `web_embedded`, which YouTube now serves SABR-only (warning, issue 12482). `-web_embedded` removes it while keeping yt-dlp's age-gate fallback.

- [ ] **Step 2: Run it and see it fail.** `cd apps/server && uv run pytest tests/unit/test_downloader_runtime_resolution.py -k player_client -v`. Expect FAIL (`['web_embedded', 'default']`).
- [ ] **Step 3: Implement.** Set `"player_client": ["default", "-web_embedded"]` in `build_ytdlp_options`.
- [ ] **Step 4: Run it and see it pass.** Run the same command plus `-k accepted_by_ytdlp`. Expect PASS.
- [ ] **Step 5: Commit.** `git commit -m "fix: stop requesting the SABR-only web_embedded client"`

### Task 4: `pick_subtitle_langs` — original language and real English only

**Files:**
- Modify: `apps/server/app/services/downloader.py`
- Test: `apps/server/tests/unit/test_subtitle_langs.py` (new)

**Interfaces:**
- Produces: `pick_subtitle_langs(info: dict) -> list[str]` in `app.services.downloader`

Rules (from the spec, §1):
- `orig` = the first `automatic_captions` key ending in `-orig`, with that suffix removed. Otherwise, the part of `info["language"]` before any `+` or `-`. Otherwise `None`.
- `base(key)` = `key.split("-")[0]`.
- Manual picks = `subtitles` keys (in dict order) whose `base` is `orig` or `"en"`. Skip `live_chat`.
- Then, if no manual pick has `base == orig` and `f"{orig}-orig"` is in `automatic_captions`, append it.
- Nothing else from `automatic_captions`, ever. Result has no duplicates. Empty list if nothing qualifies.

- [ ] **Step 1: Write the failing tests.**

```python
from app.services.downloader import pick_subtitle_langs

def auto(*keys): return {k: [{"ext": "srt"}] for k in keys}

def test_pick_auto_only_french():
    info = {"language": "fr", "subtitles": {}, "automatic_captions": auto("fr-orig", "fr", "en", "de")}
    assert pick_subtitle_langs(info) == ["fr-orig"]

def test_pick_manual_english_on_english_video():
    info = {"subtitles": auto("en"), "automatic_captions": auto("en-orig", "en", "fr")}
    assert pick_subtitle_langs(info) == ["en"]

def test_pick_manual_french_and_english():
    info = {"subtitles": auto("fr", "en-GB", "de"), "automatic_captions": auto("fr-orig", "en")}
    assert pick_subtitle_langs(info) == ["fr", "en-GB"]

def test_pick_manual_english_plus_auto_original():
    info = {"subtitles": auto("en"), "automatic_captions": auto("ja-orig", "ja", "en")}
    assert pick_subtitle_langs(info) == ["en", "ja-orig"]

def test_pick_never_takes_translated_auto():
    info = {"language": "fr", "subtitles": {}, "automatic_captions": auto("en", "fr")}
    assert pick_subtitle_langs(info) == []

def test_pick_language_fallback_strips_merge_and_region():
    info = {"language": "pt-BR+pt-BR", "subtitles": auto("pt-BR"), "automatic_captions": {}}
    assert pick_subtitle_langs(info) == ["pt-BR"]

def test_pick_nothing_available():
    assert pick_subtitle_langs({}) == []
```

- [ ] **Step 2: Run them and see them fail.** `uv run pytest tests/unit/test_subtitle_langs.py -v`. Expect ImportError.
- [ ] **Step 3: Implement** `pick_subtitle_langs(info: dict) -> list[str]` next to `build_ytdlp_options`.
- [ ] **Step 4: Run them and see them pass.**
- [ ] **Step 5: Commit.** `git commit -m "feat: pick original-language and real English subtitles only"`

### Task 5: Apply the picks; a subtitle failure no longer fails the job

**Files:**
- Modify: `apps/server/app/services/downloader.py` (`build_ytdlp_options` subtitle block, `run_download`)
- Test: `apps/server/tests/unit/test_downloader_subtitles.py` (new); update `test_downloader_runtime_resolution.py::test_build_ytdlp_options_prefers_srt_english_and_auto_subtitles` and `test_downloader_layout.py::test_custom_template_skips_layout`

**Interfaces:**
- Consumes: `pick_subtitle_langs` (Task 4)
- Produces: `DownloadResult.warning: str | None = None` (new last field with a default, so existing positional constructions keep working). `SUBTITLE_WARNING = "Subtitles couldn't be downloaded."` in `app.services.downloader`.

Behaviour:
- `build_ytdlp_options(subtitles=True)` adds `"youtube": {"skip": ["translated_subs"], ...}` to the extractor args and keeps `writesubtitles`, `writeautomaticsub` and `subtitlesformat="srt/best"`. It never sets `subtitleslangs` itself.
- `run_download` always resolves first: `resolved = ydl.extract_info(url, download=False)`. Both the default layout and `output_template` branches then call `ydl.process_ie_result(resolved, download=True)`. Only the default branch rewrites `outtmpl`. When `subtitles`, set `ydl.params["subtitleslangs"] = pick_subtitle_langs(resolved)`. If that list is empty, set `writesubtitles` and `writeautomaticsub` to `False` instead.
- Wrap `process_ie_result` in `try/except yt_dlp.utils.DownloadError as exc`. If `"Unable to download video subtitles" in str(exc)` (yt-dlp prefixes the message with `ERROR: `), set `writesubtitles = writeautomaticsub = False` on `ydl.params`, call `process_ie_result(resolved, download=True)` once more, and set `warning = SUBTITLE_WARNING`. Re-raise any other error.
- yt-dlp writes subtitles before media (`YoutubeDL.process_info`: `_write_subtitles` at :3387, media at :3531), so the retry is the real media download.

- [ ] **Step 1: Write the failing tests** in `test_downloader_subtitles.py`. Reuse the `fake_ydl` fixture pattern from `test_downloader_layout.py`, extended so `process_ie_result` records `self.params.get("subtitleslangs")` and `self.params.get("writesubtitles")` per call, and can raise a queued exception on its first call.

```python
def test_subtitle_langs_set_from_resolved_info(tmp_path, fake_ydl):
    fake_ydl.info = {"id": "a", "title": "t", "channel": "c", "ext": "mp4", "language": "fr",
                     "automatic_captions": {"fr-orig": [{}], "en": [{}]}}
    run_download("u", output_dir=str(tmp_path), subtitles=True)
    assert fake_ydl.calls == [{"subtitleslangs": ["fr-orig"], "writesubtitles": True}]

def test_no_eligible_subtitles_turns_subs_off(tmp_path, fake_ydl):
    fake_ydl.info = {"id": "a", "title": "t", "channel": "c", "ext": "mp4", "automatic_captions": {"en": [{}]}}
    result = run_download("u", output_dir=str(tmp_path), subtitles=True)
    assert fake_ydl.calls[0]["writesubtitles"] is False
    assert result.warning is None

def test_subtitle_failure_retries_without_subs(tmp_path, fake_ydl):
    fake_ydl.info = {"id": "a", "title": "t", "channel": "c", "ext": "mp4", "language": "fr",
                     "automatic_captions": {"fr-orig": [{}]}}
    fake_ydl.raise_first = DownloadError("ERROR: Unable to download video subtitles for 'fr-orig': HTTP Error 429: Too Many Requests")
    result = run_download("u", output_dir=str(tmp_path), subtitles=True)
    assert [c["writesubtitles"] for c in fake_ydl.calls] == [True, False]
    assert result.warning == "Subtitles couldn't be downloaded."
    assert result.path.endswith("t.mp4")

def test_media_error_is_not_retried(tmp_path, fake_ydl):
    fake_ydl.info = {"id": "a", "title": "t", "channel": "c", "ext": "mp4"}
    fake_ydl.raise_first = DownloadError("ERROR: HTTP Error 403: Forbidden")
    with pytest.raises(DownloadError):
        run_download("u", output_dir=str(tmp_path), subtitles=True)
    assert len(fake_ydl.calls) == 1

def test_custom_template_also_resolves_first(tmp_path, fake_ydl):
    fake_ydl.info = {"id": "a", "title": "t", "ext": "mp4", "language": "fr", "automatic_captions": {"fr-orig": [{}]}}
    run_download("u", output_dir=str(tmp_path), output_template="%(title)s.%(ext)s", subtitles=True)
    assert fake_ydl.extract_downloads == [False]
    assert fake_ydl.calls[0]["subtitleslangs"] == ["fr-orig"]
```

Update the existing tests:
- `test_build_ytdlp_options_prefers_srt_english_and_auto_subtitles` → rename to `test_build_ytdlp_options_subtitles_skip_translated`, and also assert `options["extractor_args"]["youtube"]["skip"] == ["translated_subs"]` and `"subtitleslangs" not in options`.
- `test_custom_template_skips_layout` → assert `fake_ydl.process_calls == 1` and `fake_ydl.extract_downloads == [False]`, and that `outtmpl` is still the custom template.

- [ ] **Step 2: Run them and see them fail.** `uv run pytest tests/unit/test_downloader_subtitles.py tests/unit/test_downloader_layout.py tests/unit/test_downloader_runtime_resolution.py -v`
- [ ] **Step 3: Implement** the behaviour above in `build_ytdlp_options` and `run_download`. Keep `match_filter` (the output guard) and the progress hook untouched. The guard runs inside `process_ie_result`, so it still covers both branches.
- [ ] **Step 4: Run the whole server suite.** `uv run pytest -q`. Expect PASS, including `test_downloader_progress.py`'s output-guard tests.
- [ ] **Step 5: Manual check (needs network).** Probe the video from the report, with a scratch script outside the repo:

```bash
uv run python -I -c "from app.services.downloader import *; import tempfile; r=run_download('https://www.youtube.com/watch?v=QaVuJI6Mkv0', output_dir=tempfile.mkdtemp(), subtitles=True, quality_cap='480'); print(r)"
```

Expect: no SABR warning, a `*.fr-orig.srt` next to the file, and `warning=None`.

- [ ] **Step 6: Commit.** `git commit -m "fix: never request translated subtitles; a subtitle failure keeps the video"`

> Task 5 stores `result.warning` nowhere yet. Phase 3 (Task 6) persists it. Until then the job is simply `done` and the video is kept, which is the user-visible fix.
