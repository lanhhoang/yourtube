# Library, Queue and Subtitle Improvements Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Playlist downloads stop warning about SABR and stop failing on subtitle 429s. The Queue can dismiss every failed job at once. The Watch page shows dynamic range and codecs, and plays the downloaded subtitles. The Library gains Select-mode bulk delete, sort and filter in place of the four chips.

**Architecture:** Server changes stay in the existing modules. `downloader.py` gets the player-client fix, a pure `pick_subtitle_langs`, the subtitle-failure retry, and codec/dynamic-range extraction. `queue.py` gets `dismiss_failed`. `library.py` gets sidecar-aware delete and `delete_many`. A new `subtitles.py` handles sidecar discovery and SRT→VTT. A new `media_probe.py` handles the ffprobe backfill. One Alembic revision adds `vcodec`, `acodec`, `dynamic_range` and `warning_message`. In the web app, `Watch.svelte` gains the new metadata line and `<track>`s. `Queue.svelte` gains "Dismiss all". `Library.svelte` swaps `Chips` for a toolbar (search · sort · filter · select), with pure helpers in `lib/library.ts` and a new `lib/codecs.ts`. Work ships in six phases, simplest first. Each phase is usable on its own (see the phase index).

**Tech Stack:** FastAPI, yt-dlp 2026.10.26 (`yt-dlp[default]`, yt-dlp-ejs 0.8.0), SQLAlchemy + Alembic (SQLite), Python 3.12 via `uv`, pytest; ffprobe (ships with ffmpeg in the Docker image). Svelte 5 runes, Vite, Tailwind 4, openapi-fetch, Vitest, Playwright. No new dependencies.

**Spec:** `docs/superpowers/specs/2026-11-19-library-queue-subtitles-design.md`

**Phase index:** `docs/superpowers/plans/2026-11-19-library-queue-subtitles-phases.md`

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

1. **A French video with auto captions only, on a cookie-authenticated session.** It downloads with `fr-orig` subtitles, never `en` (translated), and the log has no SABR warning. Tasks 3 and 4 own the tests (`test_pick_*`, `test_player_client_excludes_web_embedded`).
2. **A subtitle 429 mid-playlist.** The video still lands, the job is `done` with `warning_message`, and the next video goes on. A real media error (e.g. 403) still fails the job and is not retried. Task 5 owns `test_subtitle_failure_retries_without_subs` and `test_media_error_is_not_retried`.
3. **Bulk delete where one file is locked or gone.** The rest are deleted, the failing one stays in the library, and the toast says "Deleted 2, 1 failed". An `id` that isn't `done` (active, or already deleted) is reported, not deleted. Task 11 owns `test_delete_many_partial`.
4. **Subtitle lookup with a malicious or odd `lang`** (`../x`, `en.srt`, unknown). It returns 404 and never reads outside the media file's folder. A video whose title starts with another video's stem (`talk.mp4` and `talk-2.mp4`) must not show the other's tracks. Task 9 owns `test_vtt_unknown_lang_404` and `test_list_ignores_longer_stem`.
5. **The ffprobe backfill on a large library, with ffprobe missing or a file unreadable.** Startup and serving are not blocked, the bad row stays null and is retried next start, and audio files with cover art don't report a video codec. Task 7 owns `test_backfill_missing_ffprobe`, `test_backfill_skips_attached_pic` and `test_backfill_runs_off_thread`.

---

## File Structure

```
apps/server/
  app/models.py                          (modify: vcodec, acodec, dynamic_range, warning_message)
  app/schemas.py                         (modify: JobOut + playlist_title, playlist_channel, vcodec, acodec,
                                          dynamic_range, warning_message; SubtitleTrackOut; BulkDeleteIn/Out;
                                          DismissFailedOut)
  app/services/downloader.py             (modify: player_client, pick_subtitle_langs, subtitle retry,
                                          DownloadResult codec fields)
  app/services/queue.py                  (modify: release_job codec/warning kwargs, retry clears warning,
                                          dismiss_failed)
  app/services/job_runner.py             (modify: pass codec/warning fields through)
  app/services/media_probe.py            NEW: probe_media(), backfill_media_info()
  app/services/subtitles.py              NEW: subtitle_sidecars(), srt_to_vtt()
  app/services/library.py                (modify: delete removes sidecars; delete_many)
  app/api/jobs.py                        (modify: /queue/dismiss-failed, /downloads/{id}/subtitles[...])
  app/api/library.py                     (modify: POST /library/delete)
  app/main.py                            (modify: start backfill thread in lifespan)
  alembic/versions/20261119120000_add_media_info.py   NEW
  tests/e2e_server.py                    (modify: seed codecs, a subtitle sidecar, a second channel/playlist row)
  tests/unit/test_subtitle_langs.py      NEW
  tests/unit/test_downloader_subtitles.py NEW
  tests/unit/test_media_probe.py         NEW
  tests/unit/test_subtitles.py           NEW
  tests/api/test_subtitles_api.py        NEW
  (modify) tests/unit/test_downloader_runtime_resolution.py, test_downloader_progress.py,
           test_job_runner.py, test_queue_retry_dismiss.py, test_library.py; tests/api/test_queue_api.py,
           test_library_api.py; tests/test_db.py
apps/web/
  src/lib/api.gen.ts                     (regenerated)
  src/lib/codecs.ts                      NEW: shortCodec()
  src/lib/library.ts                     (modify: drop Chip/libraryItems; add watchMeta, LibraryView,
                                          sortItems, filterItems, facetOptions, readView/writeView)
  src/lib/subtitles.ts                   NEW: trackLabel()
  src/routes/Watch.svelte                (modify: meta line, warning, <track>s)
  src/routes/Queue.svelte                (modify: Dismiss all)
  src/routes/Library.svelte              (modify: toolbar, select mode, action bar, filters)
  src/components/JobCard.svelte          (modify: selectable mode)
  src/components/LibraryFilters.svelte   NEW: filter form (popover on desktop, BottomSheet on phone)
  src/components/Chips.svelte            DELETE (Task 13)
  test/codecs.test.ts, test/subtitles.test.ts       NEW
  test/library.test.ts                   (modify)
  e2e/library.spec.ts, e2e/queue.spec.ts, e2e/phone.spec.ts   (modify)
README.md                                (modify: subtitles, codecs, library tools)
```

---

## Phase 1 — Queue: dismiss all failed

### Task 1: `POST /api/queue/dismiss-failed`

**Files:**

- Modify: `apps/server/app/services/queue.py`, `apps/server/app/api/jobs.py`, `apps/server/app/schemas.py`
- Test: `apps/server/tests/unit/test_queue_retry_dismiss.py`, `apps/server/tests/api/test_queue_api.py`

**Interfaces:**

- Produces: `dismiss_failed(session: Session) -> int` (rows deleted). `class DismissFailedOut(BaseModel): dismissed: int`. Route `POST /api/queue/dismiss-failed -> DismissFailedOut` (200).

- [ ] **Step 1: Write the failing tests.**
  - `test_dismiss_failed_removes_only_error_rows` (unit): one row each in `error`, `error`, `done`, `queued`, `active` → returns `2`. The `done`/`queued`/`active` rows remain.
  - `test_dismiss_failed_endpoint` (api): two failed rows → `{"dismissed": 2}`, and `GET /api/queue` `failed == []`. Calling it again → `{"dismissed": 0}`.
- [ ] **Step 2: Run them and see them fail.**
- [ ] **Step 3: Implement.** One `delete(Download).where(Download.status == "error")` plus a commit. The route lives next to `dismiss`.
- [ ] **Step 4: Run them and see them pass. Run `pnpm typegen`.**
- [ ] **Step 5: Commit** (with `api.gen.ts`). `git commit -m "feat: dismiss all failed downloads endpoint"`

### Task 2: "Dismiss all" on the Queue page

**Files:**

- Modify: `apps/web/src/routes/Queue.svelte`
- Test: `apps/web/e2e/queue.spec.ts`

**Interfaces:**

- Consumes: `POST /api/queue/dismiss-failed` (Task 1)

UI: the "Failed" `<h2>` row becomes a flex row: `Failed` on the left and a `Dismiss all` button (same `btn` class) on the right. It's shown only when `queue.failed.length >= 2`. Click → disable it → call → `refresh()`. On error, show `messageFor(err)` under the heading (text-danger, `role="alert"`). There's no confirm, because dismissing removes no files. No toast either: the list emptying is the feedback.

- [ ] **Step 1: Write the failing e2e test** `"dismiss all clears failed downloads"`. Use `page.route("**/api/queue", …)` to serve two failed jobs (copy the job shape from the toasts test) until the dismiss call is seen, then `failed: []`. Use `page.route("**/api/queue/dismiss-failed", …)` and fulfil `{dismissed: 2}`. Click `Dismiss all` and expect both rows to have count 0. A second test, `"dismiss all is hidden for one failure"`, serves one failed job and expects the button to have count 0.
- [ ] **Step 2: Run it and see it fail.** `pnpm e2e queue.spec.ts`
- [ ] **Step 3: Implement.** Read `craft-floor.md` first (Global Constraints). The button must be a 44 px target on phones (the `btn` class already is).
- [ ] **Step 4: Run it and see it pass. Run `pnpm check`.**
- [ ] **Step 5: Commit.** `git commit -m "feat: Dismiss all on the queue page"`

---

## Phase 2 — Quieter, sturdier downloads

### Facts the design relies on (verified in yt-dlp 2026.10.26)

- `YoutubeDL._write_subtitles` (`YoutubeDL.py:4492`) wraps any subtitle error as `DownloadError("Unable to download video subtitles for '<lang>': …")`. `str(exc)` is prefixed with `ERROR: `, so match with `in`, not `startswith`.
- `process_info` writes subtitles (`:3387`) before media (`:3531`), so a subtitle failure means no media has been fetched yet, and the retry is the real media download. A real `YoutubeDL` was run offline: a second `process_ie_result(resolved, download=True)` with subtitles off succeeds.
- `process_subtitles` (`:3155`) reads `writesubtitles`, `writeautomaticsub` and `subtitleslangs` from `ydl.params` when `process_ie_result` runs, so setting them after `extract_info(download=False)` takes effect.
- `skip: ["translated_subs"]` only drops translations of _manual_ tracks (`extractor/youtube/_video.py:4244`, `:4305`). Auto-caption translations are still listed, which is why `pick_subtitle_langs` exists.
- Jobs are single videos: `sources.py` stores the canonical `webpage_url`, so `resolved` is a video info dict.

---

### Task 3: Drop `web_embedded` from the player clients

**Files:**

- Modify: `apps/server/app/services/downloader.py:230`
- Test: `apps/server/tests/unit/test_downloader_runtime_resolution.py:25-38`

**Interfaces:**

- Produces: `build_ytdlp_options(...)["extractor_args"] == {"youtube": {"player_client": ["default", "-web_embedded"]}}` (when `subtitles=False`)

- [ ] **Step 1: Rewrite the failing test.** Replace `test_build_ytdlp_options_avoids_youtube_android_vr_403` with:

```python
def test_player_client_excludes_web_embedded(tmp_path) -> None:
    """With cookies, yt-dlp's default set includes ``web_embedded``, which YouTube now
    serves SABR-only (warning, issue 12482). ``-web_embedded`` removes it while keeping
    yt-dlp's age-gate fallback."""
    options = build_ytdlp_options(
        skip_download=True,
        output_dir=str(tmp_path),
        js_runtime="node",
    )

    assert options["extractor_args"] == {"youtube": {"player_client": ["default", "-web_embedded"]}}
    assert options["js_runtimes"] == {"node": {"path": "node"}}
    assert "remote_components" not in options
```

- [ ] **Step 2: Run it and see it fail.** `uv run pytest tests/unit/test_downloader_runtime_resolution.py -k player_client -v`. Expect FAIL: the actual value is `['web_embedded', 'default']`.
- [ ] **Step 3: Implement.** In `build_ytdlp_options`, set `"player_client": ["default", "-web_embedded"]`.
- [ ] **Step 4: Run it and see it pass.** `uv run pytest tests/unit/test_downloader_runtime_resolution.py -k "player_client or accepted_by_ytdlp" -v`. Expect 2 passed. (Use one `-k` expression; pytest only keeps the last `-k` if you pass two.)
- [ ] **Step 5: Commit.** `pnpm check`, then `git commit -m "fix: stop requesting the SABR-only web_embedded client"`

### Task 4: `pick_subtitle_langs`: original language and real English only

**Files:**

- Modify: `apps/server/app/services/downloader.py`
- Test: `apps/server/tests/unit/test_subtitle_langs.py` (new)

**Interfaces:**

- Produces: `pick_subtitle_langs(info: dict) -> list[str]` in `app.services.downloader`

Rules (from the spec, §1):

- `orig` is the first `automatic_captions` key ending in `-orig`, with that suffix removed. Otherwise, it is the part of `info["language"]` before any `+` or `-`. Otherwise, it is `None`.
- `base(key)` = `key.split("-")[0]`.
- Manual picks are the `subtitles` keys, in dict order, whose `base` is `orig` or `"en"`. Skip `live_chat`.
- If no manual pick has `base == orig` and `f"{orig}-orig"` is in `automatic_captions`, append it.
- Take nothing else from `automatic_captions`. The result has no duplicates. Return an empty list if nothing qualifies.

- [ ] **Step 1: Write the failing tests** in `tests/unit/test_subtitle_langs.py`:

```python
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
```

- [ ] **Step 2: Run them and see them fail.** `uv run pytest tests/unit/test_subtitle_langs.py -v`. Expect an ImportError.
- [ ] **Step 3: Implement** `pick_subtitle_langs(info: dict) -> list[str]` just above `extract_info`, with a one-line docstring. About 10 lines; `re` is already imported. The dry run used this shape:

```python
auto = info.get("automatic_captions") or {}
manual = info.get("subtitles") or {}
orig = next((k.removesuffix("-orig") for k in auto if k.endswith("-orig")), None)
if orig is None and info.get("language"):
    orig = re.split(r"[+-]", info["language"])[0]
picks = [k for k in manual if k != "live_chat" and k.split("-")[0] in (orig, "en")]
if orig and not any(k.split("-")[0] == orig for k in picks) and f"{orig}-orig" in auto:
    picks.append(f"{orig}-orig")
return list(dict.fromkeys(picks))
```

- [ ] **Step 4: Run them and see them pass.** Expect 8 passed.
- [ ] **Step 5: Commit.** `pnpm check`, then `git commit -m "feat: pick original-language and real English subtitles only"`

### Task 5: Apply the picks; a subtitle failure no longer fails the job

**Files:**

- Modify: `apps/server/app/services/downloader.py` (`DownloadResult`, the `build_ytdlp_options` subtitle block and docstring, `run_download`)
- Test: `apps/server/tests/unit/test_downloader_subtitles.py` (new)
- Update: `test_downloader_runtime_resolution.py::test_build_ytdlp_options_prefers_srt_english_and_auto_subtitles`, `test_downloader_layout.py::test_custom_template_skips_layout`, and the `_wire` docstring in `test_downloader_progress.py`

**Interfaces:**

- Consumes: `pick_subtitle_langs` (Task 4)
- Produces:
  - `DownloadResult.warning: str | None = None`. It is a new last field with a default, so the existing positional construction in `tests/e2e_server.py` and the keyword constructions in `test_job_runner.py` keep working.
  - `SUBTITLE_WARNING = "Subtitles couldn't be downloaded."` in `app.services.downloader`.

Behaviour:

- `build_ytdlp_options(subtitles=True)` adds `options["extractor_args"]["youtube"]["skip"] = ["translated_subs"]` and keeps `writesubtitles`, `writeautomaticsub` and `subtitlesformat="srt/best"`. It never sets `subtitleslangs` itself. Update its docstring: drop "English-first order with auto-generated fallback" and say that the languages are picked per video by `run_download` via `pick_subtitle_langs`.
- `run_download` always resolves first with `resolved = ydl.extract_info(url, download=False) or {}`. Only the default branch (`not output_template`) computes `default_stem` and rewrites `outtmpl`. Both branches then call `ydl.process_ie_result(resolved, download=True)`.
- When `subtitles` is true, set `ydl.params["subtitleslangs"] = pick_subtitle_langs(resolved)`. If that list is empty, set `writesubtitles` and `writeautomaticsub` to `False` instead.
- Wrap `process_ie_result` in `try/except yt_dlp.utils.DownloadError as exc`. If `"Unable to download video subtitles" in str(exc)`, set `writesubtitles` and `writeautomaticsub` to `False` on `ydl.params`, call `process_ie_result(resolved, download=True)` once more, and set `warning = SUBTITLE_WARNING`. Re-raise any other error.
- Pass `warning=warning` to the returned `DownloadResult`. Leave `match_filter` (the output guard), the progress hook and the transcript-sidecar loop untouched.
- `job_runner.py` is not changed. It ignores `result.warning` until Phase 3.

- [ ] **Step 1: Write the failing tests** in `tests/unit/test_downloader_subtitles.py`:

```python
"""``run_download`` subtitle picks and the subtitle-failure retry."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
import yt_dlp
from yt_dlp.utils import DownloadError

from app.services.downloader import SUBTITLE_WARNING, run_download

SUB_429 = (
    "ERROR: Unable to download video subtitles for 'fr-orig': HTTP Error 429: Too Many Requests"
)


@pytest.fixture()
def fake_ydl(monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    state = SimpleNamespace(info={}, calls=[], extract_downloads=[], raise_first=None)

    def extract_info(self, url, download=True, **_kwargs):
        state.extract_downloads.append(download)
        return dict(state.info)

    def process_ie_result(self, info, download=True, **_kwargs):
        state.calls.append(
            {
                "subtitleslangs": self.params.get("subtitleslangs"),
                "writesubtitles": self.params.get("writesubtitles"),
            }
        )
        if state.raise_first is not None:
            exc, state.raise_first = state.raise_first, None
            raise exc
        path = self.prepare_filename(info)
        for hook in self.params["progress_hooks"]:
            hook({"status": "finished", "filename": path})
        return info

    monkeypatch.setattr(yt_dlp.YoutubeDL, "extract_info", extract_info)
    monkeypatch.setattr(yt_dlp.YoutubeDL, "process_ie_result", process_ie_result)
    return state


def _french(**extra: Any) -> dict:
    return {"id": "a", "title": "t", "channel": "c", "ext": "mp4", "language": "fr", **extra}


def test_subtitle_langs_set_from_resolved_info(tmp_path: Path, fake_ydl: Any) -> None:
    fake_ydl.info = _french(automatic_captions={"fr-orig": [{}], "en": [{}]})
    run_download("u", output_dir=str(tmp_path), subtitles=True)
    assert fake_ydl.calls == [{"subtitleslangs": ["fr-orig"], "writesubtitles": True}]


def test_no_eligible_subtitles_turns_subs_off(tmp_path: Path, fake_ydl: Any) -> None:
    fake_ydl.info = {"id": "a", "title": "t", "channel": "c", "ext": "mp4"}
    fake_ydl.info["automatic_captions"] = {"en": [{}]}
    result = run_download("u", output_dir=str(tmp_path), subtitles=True)
    assert fake_ydl.calls[0]["writesubtitles"] is False
    assert result.warning is None


def test_subtitle_failure_retries_without_subs(tmp_path: Path, fake_ydl: Any) -> None:
    fake_ydl.info = _french(automatic_captions={"fr-orig": [{}]})
    fake_ydl.raise_first = DownloadError(SUB_429)
    result = run_download("u", output_dir=str(tmp_path), subtitles=True)
    assert [c["writesubtitles"] for c in fake_ydl.calls] == [True, False]
    assert result.warning == SUBTITLE_WARNING == "Subtitles couldn't be downloaded."
    assert result.path.endswith("t.mp4")


def test_media_error_is_not_retried(tmp_path: Path, fake_ydl: Any) -> None:
    fake_ydl.info = {"id": "a", "title": "t", "channel": "c", "ext": "mp4"}
    fake_ydl.raise_first = DownloadError("ERROR: HTTP Error 403: Forbidden")
    with pytest.raises(DownloadError):
        run_download("u", output_dir=str(tmp_path), subtitles=True)
    assert len(fake_ydl.calls) == 1


def test_custom_template_also_resolves_first(tmp_path: Path, fake_ydl: Any) -> None:
    fake_ydl.info = _french(automatic_captions={"fr-orig": [{}]})
    template = "%(title)s.%(ext)s"
    run_download("u", output_dir=str(tmp_path), output_template=template, subtitles=True)
    assert fake_ydl.extract_downloads == [False]
    assert fake_ydl.calls[0]["subtitleslangs"] == ["fr-orig"]
```

Update the existing tests:

- In `test_downloader_runtime_resolution.py`, rename `test_build_ytdlp_options_prefers_srt_english_and_auto_subtitles` to `test_build_ytdlp_options_subtitles_skip_translated`. Add `assert options["extractor_args"]["youtube"]["skip"] == ["translated_subs"]` and keep `assert "subtitleslangs" not in options`.
- In `test_downloader_layout.py::test_custom_template_skips_layout`, replace the last two asserts with:
  ```python
  assert fake_ydl.process_calls == 1
  assert fake_ydl.extract_downloads == [False]
  assert fake_ydl.outtmpl == str(tmp_path / "%(title)s.%(ext)s")
  ```
- In `test_downloader_progress.py`, change the `_wire` docstring. Both branches now resolve with `extract_info(download=False)` and then download with `process_ie_result`. The helper itself still works unchanged.

- [ ] **Step 2: Run them and see them fail.** `uv run pytest tests/unit/test_downloader_subtitles.py tests/unit/test_downloader_layout.py tests/unit/test_downloader_runtime_resolution.py -v`. Expect an ImportError for `SUBTITLE_WARNING`. After stubbing it, expect the 5 new tests, the renamed subtitles test and `test_custom_template_skips_layout` to fail.
- [ ] **Step 3: Implement** the behaviour above in `DownloadResult`, `build_ytdlp_options` and `run_download`.
- [ ] **Step 4: Run the whole server check.** `pnpm --filter @app/server check` (ruff, ruff format, ty and pytest with coverage). Expect 384 passed, including the output-guard tests in `test_downloader_progress.py` (`test_run_download_always_guards`, `test_run_download_refuses_absolute_template_outside_downloads`).
- [ ] **Step 5: Manual check (needs network).** From `apps/server`, without `-I` because it would drop `app` from `sys.path`. `quality_cap="audio"` avoids needing ffmpeg locally; use `"480"` if ffmpeg is installed. If a cookies file is set in Settings, also pass `cookies_file="<path>"` to exercise the authenticated client set.

```bash
uv run python -c "
import os, tempfile
from app.services.downloader import run_download
r = run_download('https://www.youtube.com/watch?v=QaVuJI6Mkv0', output_dir=tempfile.mkdtemp(), subtitles=True, quality_cap='audio')
print(r); print(sorted(os.listdir(os.path.dirname(r.path))))
"
```

Expect no `SABR` line in the output, `warning=None`, and `<stem>.fr-orig.srt` plus `<stem>.fr-orig.txt` next to the media file. The dry run on 2026-11-19 matched this.

- [ ] **Step 6: Commit.** `pnpm check`, then `git commit -m "fix: never request translated subtitles; a subtitle failure keeps the video"`

> Task 5 doesn't store `result.warning` anywhere yet; Phase 3 (Task 6) persists it. Until then the job is simply `done` and the video is kept, which is the user-visible fix.

---

## Phase 3 — Watch metadata: dynamic range and codecs

### Task 6: Store vcodec, acodec, dynamic range and the job warning

**Files:**

- Create: `apps/server/alembic/versions/20261119120000_add_media_info.py`
- Modify: `apps/server/app/models.py`, `app/schemas.py` (`JobOut`), `app/services/downloader.py` (`DownloadResult`, `_extract_file_metadata`, `run_download` return), `app/services/queue.py` (`release_job`, `retry_job`), `app/services/job_runner.py` (`_release_and_notify`, `run_claimed_job`), `apps/server/tests/e2e_server.py` (`_run_download` stub, `_seed`)
- Test: `tests/test_db.py`, `tests/unit/test_downloader_progress.py`, `tests/unit/test_job_runner.py`, `tests/unit/test_queue_retry_dismiss.py`, `tests/api/test_library_api.py`

**Interfaces:**

- Produces:
  - Columns `downloads.vcodec`, `acodec`, `dynamic_range`, `warning_message`: `String`, nullable.
  - `DownloadResult(path, file_size, media_format, resolution_height, vcodec: str | None = None, acodec: str | None = None, dynamic_range: str | None = None, warning: str | None = None)`. Task 5's `warning` field moves to the end of this order.
  - `_extract_file_metadata(info, output_path) -> MediaMeta`, where `MediaMeta` is a frozen dataclass `(file_size, media_format, resolution_height, vcodec, acodec, dynamic_range)`.
  - `release_job(..., vcodec=None, acodec=None, dynamic_range=None, warning_message=None)`. Same kwargs on `_release_and_notify`.
  - `JobOut` new fields: `playlist_title: str | None`, `playlist_channel: str | None`, `vcodec: str | None`, `acodec: str | None`, `dynamic_range: str | None`, `warning_message: str | None`.

Extraction rules: `vcodec`/`acodec` come from the final info. yt-dlp's merge already lifts the video stream's `vcodec`/`dynamic_range` and the audio stream's `acodec` to the top level (`YoutubeDL._merge`), and `requested_formats` is the fallback. The value `"none"` maps to `None`. `dynamic_range` is only kept when `vcodec` is not `None`.

- [ ] **Step 1: Write the failing tests.**
  - `test_db.py::test_downloads_has_media_info_columns`: all four columns exist. Extend `test_migration_downgrade_and_upgrade`: downgrade to `20261118130000` removes `vcodec`, and upgrading again restores it.
  - `test_downloader_progress.py::test_extract_file_metadata_codecs`: `{"ext":"mp4","width":1920,"height":1080,"vcodec":"av01.0.08M.08","acodec":"mp4a.40.2","dynamic_range":"SDR"}` → `vcodec="av01.0.08M.08", acodec="mp4a.40.2", dynamic_range="SDR"`. Audio-only `{"vcodec":"none","acodec":"opus","dynamic_range":None}` → `vcodec=None, acodec="opus", dynamic_range=None`. Merged info with top-level codecs missing but `requested_formats=[{"vcodec":"vp09.00.51.08","dynamic_range":"HDR10","acodec":"none"},{"vcodec":"none","acodec":"opus"}]` → `vp09.00.51.08`, `opus`, `HDR10`.
  - `test_job_runner.py`: extend the done-path test so the fake returns `vcodec="avc1.640028", acodec="mp4a.40.2", dynamic_range="SDR", warning="Subtitles couldn't be downloaded."`, and assert all four land on the row (`warning_message`).
  - `test_queue_retry_dismiss.py::test_retry_resets_failed_job`: seed `warning_message="w"` and assert it's `None` after the retry.
  - `test_library_api.py::test_get_job` (extend): a row with `vcodec`, `acodec`, `dynamic_range`, `warning_message`, `playlist_title` and `playlist_channel` round-trips through `GET /api/downloads/{id}`.
- [ ] **Step 2: Run them and see them fail.**
- [ ] **Step 3: Implement.** The migration copies the `20261118120000_add_playlist_folder.py` pattern (a `_COLUMNS` tuple, `batch_alter_table`). Add `warning_message=None` to `retry_job`'s `.values(...)`. Update the e2e stub `_run_download` to return `DownloadResult(str(path), 4, "mp4", 1080, "avc1.640028", "mp4a.40.2", "SDR")`. Seed the `Seeded video` row with the same three values.
- [ ] **Step 4: Run `uv run pytest -q`, then `pnpm typegen`.**
- [ ] **Step 5: Commit.** `git commit -m "feat: store codecs, dynamic range and job warnings"`

### Task 7: ffprobe backfill for existing library items

**Files:**

- Create: `apps/server/app/services/media_probe.py`
- Modify: `apps/server/app/main.py` (lifespan)
- Test: `apps/server/tests/unit/test_media_probe.py` (new)

**Interfaces:**

- Consumes: the columns from Task 6
- Produces:
  - `probe_media(path: Path) -> ProbeResult | None`, where `ProbeResult` is a frozen dataclass `(vcodec: str | None, acodec: str | None, dynamic_range: str | None)`. It returns `None` when ffprobe is missing, exits non-zero, times out (30 s) or prints invalid JSON.
  - `backfill_media_info(session: Session) -> int` (rows updated).
  - `start_media_backfill() -> threading.Thread`: a daemon thread that opens its own `SessionLocal()` and logs the count or the exception.

Rules: run `["ffprobe", "-v", "error", "-show_streams", "-of", "json", str(path)]` via `subprocess.run(capture_output=True, timeout=30, check=False)`, looked up with `shutil.which("ffprobe")`. `vcodec` is the first `codec_type == "video"` stream whose `disposition.attached_pic != 1`. `acodec` is the first `codec_type == "audio"`. `dynamic_range` is only set when there's a video stream, from its `color_transfer`: `smpte2084` → `HDR10`, `arib-std-b67` → `HLG`, else `SDR`. Backfill selects `done` rows where `vcodec IS NULL AND acodec IS NULL AND file_path IS NOT NULL`. It resolves the path with `resolve_repo_path` and skips missing files. On `None` from the probe it leaves the row alone (retried next start), and it commits per row.

- [ ] **Step 1: Write the failing tests.** Monkeypatch `subprocess.run` and `shutil.which` in `app.services.media_probe`:
  - `test_probe_video_sdr`: streams `[{codec_type:video, codec_name:h264, color_transfer:bt709}, {codec_type:audio, codec_name:aac}]` → `("h264","aac","SDR")`
  - `test_probe_hdr10_and_hlg`: `smpte2084` → `HDR10`, `arib-std-b67` → `HLG`
  - `test_backfill_skips_attached_pic`: `[{codec_type:video, codec_name:mjpeg, disposition:{attached_pic:1}}, {codec_type:audio, codec_name:opus}]` → `(None,"opus",None)`
  - `test_backfill_missing_ffprobe`: `which` → `None`. A `done` row with an existing file stays all-null, and the return is `0`.
  - `test_backfill_updates_only_unprobed_done_rows`: rows = done+null+file (updated), done+already `vcodec` (untouched), done+missing file (untouched), error+file (untouched) → returns `1`.
  - `test_backfill_runs_off_thread`: `start_media_backfill()` returns a started daemon `Thread`. Join it with a timeout.
- [ ] **Step 2: Run them and see them fail.**
- [ ] **Step 3: Implement** `media_probe.py`. In `lifespan`, after the layout move's `try` block, call `start_media_backfill()` inside `try/except Exception: logger.exception("media backfill failed to start")`. It runs whether or not workers are enabled, because it doesn't depend on them. No test-only guard is needed: the API test DB has no `done` rows with files at startup, so the thread finds nothing to do.
- [ ] **Step 4: Run `uv run pytest -q`.**
- [ ] **Step 5: Commit.** `git commit -m "feat: backfill codecs and dynamic range with ffprobe on startup"`

### Task 8: Watch metadata line and subtitle warning

**Files:**

- Create: `apps/web/src/lib/codecs.ts`; `apps/web/test/codecs.test.ts`
- Modify: `apps/web/src/lib/library.ts` (add `watchMeta`), `apps/web/src/routes/Watch.svelte`, `apps/web/test/library.test.ts`, `apps/web/e2e/library.spec.ts`

**Interfaces:**

- Consumes: `JobOut.vcodec`, `acodec`, `dynamic_range`, `warning_message` (Task 6)
- Produces: `shortCodec(codec: string | null): string` and `watchMeta(job: JobOut): string`

`shortCodec` table (prefix match, case-insensitive, `null` → `""`): `avc1|avc3|h264` → `h264`; `hev1|hvc1|h265|hevc` → `h265`; `vp09|vp9` → `vp9`; `vp8` → `vp8`; `av01|av1` → `av1`; `mp4a|aac` → `aac`; `opus` → `opus`; `vorbis` → `vorbis`; `ac-3|ac3` → `ac3`; `ec-3|eac3` → `eac3`; `flac` → `flac`; `mp3` → `mp3`; anything else passes through unchanged.

`watchMeta` order: `uploader · qualityLabel · dynamic_range · size · shortCodec(vcodec) · shortCodec(acodec) · media_format`. Empty parts are dropped, and `dynamic_range` is only shown when `media_kind === "video"`.

- [ ] **Step 1: Write the failing tests.**

```ts
test("shortCodec", () => {
  expect(shortCodec("av01.0.08M.08")).toBe("av1");
  expect(shortCodec("avc1.640028")).toBe("h264");
  expect(shortCodec("vp09.00.51.08")).toBe("vp9");
  expect(shortCodec("mp4a.40.2")).toBe("aac");
  expect(shortCodec("hev1.2.4.L153")).toBe("h265");
  expect(shortCodec("opus")).toBe("opus");
  expect(shortCodec("h264")).toBe("h264");
  expect(shortCodec("prores")).toBe("prores");
  expect(shortCodec(null)).toBe("");
});
test("watchMeta", () => {
  const v = {
    uploader: "Chan",
    media_kind: "video",
    resolution_height: 1080,
    dynamic_range: "SDR",
    file_size: 300 * 1024 ** 2,
    vcodec: "av01.0.08M.08",
    acodec: "mp4a.40.2",
    media_format: "mp4",
  } as JobOut;
  expect(watchMeta(v)).toBe("Chan · 1080p · SDR · 300.0 MB · av1 · aac · mp4");
  expect(
    watchMeta({ ...v, dynamic_range: "HDR10", resolution_height: 2160 }),
  ).toContain("2160p · HDR10");
  const a = {
    ...v,
    media_kind: "audio",
    resolution_height: null,
    dynamic_range: null,
    vcodec: null,
    acodec: "opus",
    media_format: "webm",
  } as JobOut;
  expect(watchMeta(a)).toBe("Chan · Audio · 300.0 MB · opus · webm");
  expect(
    watchMeta({ ...v, vcodec: null, acodec: null, dynamic_range: null }),
  ).toBe("Chan · 1080p · 300.0 MB · mp4");
});
```

E2E: extend `"player opens from the library…"` with `await expect(page.getByText("E2E · 1080p · SDR · 4 B · h264 · aac · mp4")).toBeVisible()` (the seeded row from Task 6).

- [ ] **Step 2: Run them and see them fail.** `pnpm test`, `pnpm e2e -- library.spec.ts`
- [ ] **Step 3: Implement.** `Watch.svelte`: `meta = $derived(job ? watchMeta(job) : "")`. Under the meta line, when `job.warning_message`, add `<p class="m-0 mt-1 text-sm text-warn">{job.warning_message}</p>`, which is text, so it's never colour alone. Read `craft-floor.md` before editing.
- [ ] **Step 4: Run them and see them pass. Run `pnpm check`.**
- [ ] **Step 5: Commit.** `git commit -m "feat: show dynamic range and codecs on the watch page"`

---

## Phase 4 — Subtitles in the player

### Task 9: Subtitle discovery and the VTT endpoint

**Files:**

- Create: `apps/server/app/services/subtitles.py`; `tests/unit/test_subtitles.py`; `tests/api/test_subtitles_api.py`
- Modify: `apps/server/app/api/jobs.py`, `app/schemas.py`, `app/services/library_layout.py` (reuse the sidecar rule, no behaviour change)

**Interfaces:**

- Produces:
  - `subtitle_sidecars(media: Path, siblings: Iterable[Path] | None = None) -> dict[str, Path]`: lang → file, for `<stem>.<lang>.srt|vtt` next to `media`. When both exist for a lang, `.vtt` wins. Skips files that belong to a longer sibling stem: same rule as `library_layout._sidecars` (a file is excluded if another media file in the folder has a longer stem that the file's name starts with, followed by `.`). `siblings` defaults to the folder's other files whose suffix is a media extension (`mp4, mkv, webm, m4a, mp3, opus, ogg, flac, wav`).
  - `srt_to_vtt(text: str) -> str`: strips a BOM, normalises `\r\n`, prepends `WEBVTT\n\n`, and replaces `,` with `.` only on timestamp lines (`HH:MM:SS,mmm --> HH:MM:SS,mmm`). Cue numbers are kept (VTT allows them as identifiers).
  - `class SubtitleTrackOut(BaseModel): lang: str; url: str`
  - `GET /api/downloads/{job_id}/subtitles -> list[SubtitleTrackOut]`: `[]` for audio/no-file/not-done. 404 if the job is missing. Sorted with the `-orig` track(s) first, then by lang.
  - `GET /api/downloads/{job_id}/subtitles/{lang}.vtt`: 200 `text/vtt; charset=utf-8`. 404 `not_found` when the job or the lang isn't in `subtitle_sidecars(...)`. `lang` is only ever used as a dict key, never joined into a path.

- [ ] **Step 1: Write the failing tests.**
  - unit `test_srt_to_vtt`: `"1\r\n00:00:01,000 --> 00:00:02,500\r\nHi, there\r\n"` → `"WEBVTT\n\n1\n00:00:01.000 --> 00:00:02.500\nHi, there\n"` (the comma in the text is kept).
  - unit `test_sidecars_found_and_vtt_wins`: `talk.mp4`, `talk.fr-orig.srt`, `talk.en.srt`, `talk.en.vtt`, `talk.txt` → `{"fr-orig": …srt, "en": …vtt}`.
  - unit `test_list_ignores_longer_stem`: `talk.mp4`, `talk-2.mp4`, `talk-2.en.srt` → `talk.mp4` has `{}`. Also `talk.mp4`, `talk.2.mp4`, `talk.2.en.srt` → `talk.mp4` has `{}`.
  - api `test_list_subtitles`: done row with `file_path` at `tmp/a.mp4` and `a.fr-orig.srt`, `a.en.srt` → `[{"lang":"fr-orig","url":"/api/downloads/{id}/subtitles/fr-orig.vtt"},{"lang":"en",…}]`.
  - api `test_vtt_served`: body starts with `WEBVTT`, content-type `text/vtt; charset=utf-8`.
  - api `test_vtt_unknown_lang_404`: `de`, `..%2Fx`, `en.srt` → 404.
  - api `test_subtitles_missing_job_404`, `test_subtitles_not_done_is_empty`.
- [ ] **Step 2: Run them and see them fail.**
- [ ] **Step 3: Implement.** Resolve `file_path` with `resolve_repo_path`, as the file route does. Move the longer-stem rule into a helper in `subtitles.py` that `library_layout._sidecars` can call without changing its behaviour; if that's awkward, leave `library_layout` alone and duplicate the 6-line check. `test_library_layout.py` must stay green either way.
- [ ] **Step 4: Run `uv run pytest -q`, then `pnpm typegen`.**
- [ ] **Step 5: Commit.** `git commit -m "feat: list downloaded subtitles and serve them as WebVTT"`

### Task 10: Tracks in the player; delete removes sidecars

**Files:**

- Create: `apps/web/src/lib/subtitles.ts`; `apps/web/test/subtitles.test.ts`
- Modify: `apps/web/src/routes/Watch.svelte`, `apps/server/app/services/library.py`, `apps/server/tests/unit/test_library.py`, `apps/server/tests/e2e_server.py` (seed `seeded.en.srt` and `seeded.fr-orig.srt` next to `seeded.mp4`, before the layout move, which carries them along), `apps/web/e2e/library.spec.ts`

**Interfaces:**

- Consumes: `GET /api/downloads/{id}/subtitles` and `subtitle_sidecars` (Task 9)
- Produces: `trackLabel(lang: string, locale?: string): string`

`trackLabel`: `base = lang.replace(/-orig$/, "")`, `name = new Intl.DisplayNames([locale ?? navigator.language], { type: "language" }).of(base) ?? base`. Return `"<name> (auto)"` when it ends in `-orig`, else `name`. Invalid codes (`of` throws) fall back to `lang`.

Server: `delete_from_library` also removes `subtitle_sidecars(media)` files plus `<stem>.txt` and `<stem>.<lang>.txt` transcripts. It only does this after the media removal succeeded (or the media was already missing). Sidecar `OSError`s are logged and ignored, and the return value is unchanged.

- [ ] **Step 1: Write the failing tests.**
  - `subtitles.test.ts`: `trackLabel("fr-orig","en")` → `"French (auto)"`. `trackLabel("en","en")` → `"English"`. `trackLabel("pt-BR","en")` → `"Brazilian Portuguese"`. `trackLabel("zz-invalid!","en")` → `"zz-invalid!"`.
  - `test_library.py::test_delete_removes_subtitle_sidecars`: `v.mp4`, `v.en.srt`, `v.en.txt`, `v.txt`, `v-2.mp4`, `v-2.en.srt` → deleting `v` leaves only `v-2.*`.
  - e2e (extend the `"player opens…"` test): `page.locator("video track")` has count 2. Neither has the `default` attribute. The labels are `French (auto)` and `English`, with the `-orig` track first. `srclang` for `fr-orig` is `fr`.
- [ ] **Step 2: Run them and see them fail.**
- [ ] **Step 3: Implement.**
  - `Watch.svelte` fetches `/api/downloads/{job_id}/subtitles` after the job loads, but only for `media_kind === "video"`. A failure → no tracks (silent; the video still plays). It renders `<track kind="subtitles" src={t.url} srclang={t.lang.replace(/-orig$/, "")} label={trackLabel(t.lang)}>` inside `<video>`, with no `default`.
  - Remove the two `biome-ignore … carry no caption track` comments and the `svelte-ignore a11y_media_has_caption` comment on `<video>` when tracks exist. If biome or svelte-check still flag a `<video>` with zero tracks, keep the ignore comment with a new reason: "captions only exist when subtitles were downloaded". Keep the `<audio>` one.
  - `library.py` sidecar removal as above.
- [ ] **Step 4: Run them and see them pass. Run `pnpm check`.** Manually: open a seeded/real video in Safari and Chrome, pick a track in the native captions menu, and confirm the cues render.
- [ ] **Step 5: Commit.** `git commit -m "feat: downloaded subtitles in the player; delete removes sidecars"`

---

## Phase 5 — Library: Select mode and bulk delete

### Task 11: `POST /api/library/delete`

**Files:**

- Modify: `apps/server/app/services/library.py`, `apps/server/app/api/library.py`, `apps/server/app/schemas.py`
- Test: `tests/unit/test_library.py`, `tests/api/test_library_api.py`

**Interfaces:**

- Consumes: `delete_from_library(session, job_id) -> tuple[bool, str]` (with Task 10's sidecar removal)
- Produces:
  - `delete_many(session: Session, ids: list[int]) -> tuple[list[int], list[tuple[int, str]]]`: `(deleted, failed)`. It deduplicates while keeping order, calls `delete_from_library` per id (that function commits per row), and puts `ok` ids, including `file_missing`, in `deleted`.
  - `class BulkDeleteIn(BaseModel): ids: list[int] = Field(min_length=1, max_length=500)`
  - `class BulkDeleteFailure(BaseModel): id: int; reason: str`
  - `class BulkDeleteOut(BaseModel): deleted: list[int]; failed: list[BulkDeleteFailure]`
  - Route `POST /api/library/delete -> BulkDeleteOut` (200, even with failures).

- [ ] **Step 1: Write the failing tests.**
  - unit `test_delete_many_partial`: rows A (done, file exists), B (done, file missing), C (active), D (done, `os.remove` raises `PermissionError` via monkeypatch), 9999 (unknown) → `deleted == [A, B]`, `failed == [(C,"not_done"),(D,"delete_failed"),(9999,"not_found")]`. D's row still exists.
  - unit `test_delete_many_dedupes`: `[A, A]` → `deleted == [A]`.
  - api `test_bulk_delete`: 200 with that shape. `{"ids": []}` → 422 with the standard error body. 501 ids → 422.
- [ ] **Step 2: Run them and see them fail.**
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run `uv run pytest -q`, then `pnpm typegen`.**
- [ ] **Step 5: Commit.** `git commit -m "feat: bulk delete endpoint for the library"`

### Task 12: Select mode, action bar and bulk delete UI

**Files:**

- Modify: `apps/web/src/routes/Library.svelte`, `apps/web/src/components/JobCard.svelte`, `apps/web/src/lib/library.ts`
- Test: `apps/web/test/library.test.ts`, `apps/web/e2e/library.spec.ts`, `apps/web/e2e/phone.spec.ts`

**Interfaces:**

- Consumes: `POST /api/library/delete` (Task 11)
- Produces:
  - `JobCard` props: `{ job, ondeleted, selecting?: boolean = false, selected?: boolean = false, ontoggle?: (id: number) => void }`
  - `lib/library.ts`: `toggle(selected: Set<number>, id: number): Set<number>`, `bulkResultText(deleted: number, failed: number): string` → `"Deleted 3"`, `"Deleted 2, 1 failed"`, `"Couldn't delete 2"` (when `deleted === 0`)

Behaviour:

- The toolbar gets a `Select` button (pill, same style as other secondary buttons), shown when `done.length > 0`. In Select mode it reads `Done`, and `Esc` also exits. Exiting clears the selection.
- In Select mode, each card renders a visible checkbox at the top-left of the thumbnail (a native `<input type="checkbox">`, `accent-(--color-action)`, inside a ≥44 px label on phone). The whole card toggles: the title link's `after:` overlay is replaced by a `<label>` overlay for the checkbox, so tapping anywhere toggles and nothing navigates. The hover menu is hidden. A selected card gets a 2 px `fg` ring on the thumbnail. Selection is shown by the checkbox and the ring, never colour alone.
- Sticky action bar (`role="region"`, `aria-label="Selection"`): `sticky bottom-0` inside `main`, so on phones it sits above the tab bar. `bg-surface border-t border-line`, padding `p-3`, plus `pb-[calc(0.75rem+env(safe-area-inset-bottom))]` only if it ever ends up at the screen edge (it doesn't, because the tab bar is below). Contents: `{n} selected` (tabular, `aria-live="polite"`) · `Select all` (selects every visible item; reads `Clear` when all visible are selected) · `Delete` (primary danger style used elsewhere: check `Watch.svelte`'s `button`; disabled at 0).
- Delete uses the existing two-step pattern. First click → label `Delete {n}?` for 4 s. Second click → call the API → remove the `deleted` ids from `done` → show `bulkResultText` in the bar for 4 s (`role="status"`). The ids that failed stay selected. Exit Select mode when nothing is left selected.
- Changing the search or the chip clears the selection (Task 15 extends this to sort and filter changes). The chips still exist in this phase, so in-progress cards may be in the list: they get no checkbox, are never selectable, and `Select all` takes only `status === "done"` items.

- [ ] **Step 1: Write the failing tests.**
  - unit: `toggle` adds then removes. `bulkResultText(3,0)` → `"Deleted 3"`, `(2,1)` → `"Deleted 2, 1 failed"`, `(0,2)` → `"Couldn't delete 2"`.
  - e2e desktop `"select and delete several"`: create two done rows via the seeded data. Add a second seeded row `Bulk A`/`Bulk B` in `e2e_server._seed`, with files `bulk-a.mp4`/`bulk-b.mp4` (uploader `E2E`). Click `Select`, check `Bulk A` and `Bulk B` (by `getByRole("checkbox", { name: "Bulk A" })`). Expect `2 selected`. Click `Delete`, then `Delete 2?`. Both articles disappear and the files are gone (poll `existsSync`). `Deleted 2` is visible.
  - e2e desktop `"select mode does not navigate"`: in Select mode, clicking a card's title leaves the URL at `#/`.
  - e2e phone (`phone.spec.ts`) `"select mode on phone"`: tap `Select`. The checkbox target is ≥ 44 px (`expectTarget`). The action bar is visible above the tab bar (its bottom ≤ the tab bar's top). No sideways scroll.
- [ ] **Step 2: Run them and see them fail.**
- [ ] **Step 3: Implement.** Read `craft-floor.md` and `operate.md` first, and the taste skill's §6 "Never" list. Keep the copy plain. The checkbox's accessible name is the video title.
- [ ] **Step 4: Run `pnpm check` and `pnpm e2e`.** Then screenshot desktop at 1440 and phone at 390 in both themes, with Select mode on and two selected, and check against `DESIGN.md`.
- [ ] **Step 5: Commit.** `git commit -m "feat: select several library items and delete them together"`

---

## Phase 6 — Library: sort and filter

### Task 13: Library shows finished items only; chips removed

**Files:**

- Modify: `apps/web/src/lib/library.ts`, `apps/web/src/routes/Library.svelte`, `apps/web/test/library.test.ts`
- Delete: `apps/web/src/components/Chips.svelte`

**Interfaces:**

- Produces: `lib/library.ts` no longer exports `Chip` or `libraryItems`. `qualityLabel`, `formatSize` and `watchMeta` stay.

`Library.svelte` keeps the `queue` prop and its reload-on-finish effect (that's how new downloads appear), but renders `done` only. Empty states: `searching && done.length === 0` → `Nothing matches “q”.` `done.length === 0` → `No downloads yet. Paste a URL above.` In-progress work is in the Queue tab (badge count), so nothing replaces "Downloading".

- [ ] **Step 1: Update tests.** Delete the `libraryItems` tests. Add an e2e assertion in `library.spec.ts`: on `#/`, `page.getByRole("radiogroup", { name: "Filter" })` has count 0, and `Slow video` (seeded `queued`) is not shown in the library.
- [ ] **Step 2: Run them and see them fail.**
- [ ] **Step 3: Implement.** Remove `Chips` and `libraryItems`.
- [ ] **Step 4: Run `pnpm check` and `pnpm e2e -- library.spec.ts phone.spec.ts`.**
- [ ] **Step 5: Commit.** `git commit -m "refactor: library lists finished downloads only; drop the chips"`

### Task 14: Sort and filter logic

**Files:**

- Modify: `apps/web/src/lib/library.ts`; `apps/web/test/library.test.ts`

**Interfaces:**

- Consumes: `JobOut.playlist_title`, `playlist_channel`, `uploader`, `media_kind`, `finished_at`, `created_at`, `title`, `duration`, `file_size`
- Produces:

```ts
export type SortKey =
  | "added-desc"
  | "added-asc"
  | "title"
  | "duration"
  | "size";
export type KindFilter = "any" | "video" | "audio";
export type LibraryView = {
  sort: SortKey;
  kind: KindFilter;
  channel: string | null;
  playlist: string | null;
};
export const DEFAULT_VIEW: LibraryView; // { sort: "added-desc", kind: "any", channel: null, playlist: null }
export const SORT_OPTIONS: { value: SortKey; label: string }[];
// labels: "Newest first", "Oldest first", "Title A–Z", "Longest first", "Largest first"
export function sortItems(items: JobOut[], sort: SortKey): JobOut[]; // new array, stable
export function filterItems(items: JobOut[], view: LibraryView): JobOut[];
export type Facet = { value: string; count: number };
export function facets(items: JobOut[]): {
  channels: Facet[];
  playlists: Facet[];
};
export function activeFilterCount(view: LibraryView): number;
export const VIEW_KEY = "yt.library.view";
export function readView(raw: string | null): LibraryView; // tolerant: bad JSON or unknown values → defaults per field
```

Rules:

- "added" = `finished_at ?? created_at`. Title sort uses `localeCompare(…, undefined, { sensitivity: "base", numeric: true })`, with a null title sorting last. Duration and size sort descending, with nulls last. Ties keep the input order.
- Channel = `uploader`. Playlist = `playlist_title`. Facets are distinct, non-empty values with counts, sorted by `localeCompare`, and built from the **unfiltered** list so options never vanish while picking.
- `filterItems` applies kind, channel and playlist (AND). A channel or playlist value not present in the items is ignored (stale stored value), so `filterItems` returns the kind-filtered list as if that field were null. The component also drops it from the view.

- [ ] **Step 1: Write the failing tests:** one per sort key (including nulls last and stable ties); a kind/channel/playlist AND combination; a stale channel ignored; facet counts and order; `activeFilterCount`; `readView` with `null`, `"{bad"`, `{"sort":"nope","kind":"audio"}` → `{...DEFAULT_VIEW, kind:"audio"}`.
- [ ] **Step 2: Run them and see them fail.** `pnpm test`
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run them and see them pass.**
- [ ] **Step 5: Commit.** `git commit -m "feat: library sort and filter helpers"`

### Task 15: Toolbar, filter panel, pills and persistence

**Files:**

- Create: `apps/web/src/components/LibraryFilters.svelte`
- Modify: `apps/web/src/routes/Library.svelte`, `apps/server/tests/e2e_server.py` (seed one audio row and one playlist row with a different uploader), `apps/web/e2e/library.spec.ts`, `apps/web/e2e/phone.spec.ts`, `README.md`

**Interfaces:**

- Consumes: Task 14's exports; `BottomSheet` (`{ open, title, onclose, children }`)
- Produces: `LibraryFilters` props `{ view: LibraryView (bindable), channels: Facet[], playlists: Facet[] }`. It renders the form fields only. The container (popover or sheet) belongs to `Library.svelte`.

Layout:

- Desktop toolbar row: `Library` heading · (right side) search · `Sort` select (labelled visually-hidden "Sort", native `<select>` styled like `QualitySelect`) · `Filter` button (pill; shows `Filter · 2` when filters are active) · `Select`. The Filter button opens a popover anchored under it (`<div role="dialog" aria-label="Filters">`, `bg-surface border border-line-strong rounded-control p-4`, closes on Esc or an outside click, focus moves into it and back).
- Phone: the search fills the first row. The second row is `Sort` select · `Filter` · `Select`, each ≥ 44 px. `Filter` opens `BottomSheet` titled "Filters".
- `LibraryFilters` fields: Type as a radiogroup (Any / Video / Audio). Channel as a `<select>` ("Any channel" plus `name (count)`). Playlist as a `<select>` ("Any playlist" plus `name (count)`), hidden when there are no playlists. Changes apply immediately (no Apply button), and `Clear filters` resets kind, channel and playlist.
- Under the toolbar, when filters are active: removable pills `Video`, `Channel: X`, `Playlist: Y`, each with a ✕ button (`aria-label="Remove filter Channel: X"`), plus a `Clear filters` text button.
- Results: `items = sortItems(filterItems(done, view), view.sort)`. When filters hide everything: `No videos match these filters.` plus `Clear filters`.
- Persistence: `readView(localStorage.getItem(VIEW_KEY))` on mount. An `$effect` writes it on change. A stale channel or playlist gets reset to `null` after the first load.
- Selection (Task 12) clears whenever `view` or `q` changes.
- README: a short "Library" paragraph covering Sort/Filter/Select, plus the subtitle languages rule and the player tracks, and codecs/HDR on the Watch page.

- [ ] **Step 1: Write the failing e2e tests.** Tests in one spec file share the e2e server, and `"delete in library"` and `"select and delete several"` remove rows. Seed dedicated rows for these tests (`Sort A`, `Sort B`, an audio row, a playlist row under uploader `Other`) and assert only on those.
  - desktop `"sort by title"`: pick `Title A–Z`. The first article title is alphabetically first among the seeded rows.
  - desktop `"filter by channel and clear"`: open Filter, pick the second channel → only its rows. A pill `Channel: <name>` is visible. Click its ✕ → all rows are back.
  - desktop `"filter by type audio"`: Type = Audio → only the seeded audio row.
  - desktop `"view persists"`: set sort `Oldest first`, reload, and the select still shows `Oldest first`.
  - phone `"filters open in a sheet"`: tap `Filter`, `getByRole("dialog", { name: "Filters" })` is visible, controls ≥ 44 px, no sideways scroll.
- [ ] **Step 2: Run them and see them fail.**
- [ ] **Step 3: Implement.** Read `craft-floor.md`, `operate.md` and the taste skill's §6 first. Use only existing tokens. Popover motion is opacity/translate at 150 ms ease-out, removed under `prefers-reduced-motion`.
- [ ] **Step 4: Run `pnpm check` and `pnpm e2e`.** Screenshot desktop 1440 and phone 390 in both themes: default, filters active (pills), the sheet open, and the empty filtered state. Fix anything that breaks `DESIGN.md`.
- [ ] **Step 5: Commit.** `git commit -m "feat: sort and filter the library"`

---

## Spec coverage

| Spec item                                                   | Task                                     |
| ----------------------------------------------------------- | ---------------------------------------- |
| Goal 1 / §1 player_client                                   | 3                                        |
| Goal 2 / §1 subtitle languages, translated skip             | 4, 5                                     |
| Goal 2 / §1 subtitle failure non-fatal, warning             | 5 (behaviour), 6 (stored), 8 (shown)     |
| Goal 3 / §7 dismiss all failed                              | 1, 2                                     |
| Goal 6 / §2 codecs, dynamic range, backfill                 | 6, 7, 8                                  |
| Goal 7 / §3 subtitles in player, off by default             | 9, 10                                    |
| §4 delete removes sidecars                                  | 10                                       |
| Goal 4 / §5 bulk delete, Select mode                        | 11, 12                                   |
| Goal 5 / §6 chips removed, sort, filter, pills, persistence | 13, 14, 15                               |
| `JobOut.playlist_title/playlist_channel`                    | 6                                        |
| Anti-goal: hiding real failures                             | 5 (`test_media_error_is_not_retried`)    |
| Anti-goal: data loss                                        | 11, 12 (two-step confirm, done-only)     |
| Anti-goal: UI slop                                          | 2, 8, 12, 15 (skills read + screenshots) |
