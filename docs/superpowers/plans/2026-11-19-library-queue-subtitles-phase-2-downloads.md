# Phase 2: Quieter, sturdier downloads Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop the SABR `web_embedded` warning, never request auto-translated subtitles, and keep the video when a subtitle download fails.

**Usable result:** Download a playlist with subtitles on: no SABR warning in the log, no `HTTP Error 429` job failures; a French video gets `fr-orig` subtitles, and a subtitle failure leaves a finished video.

**Spec:** `docs/superpowers/specs/2026-11-19-library-queue-subtitles-design.md`

**Parent plan:** `docs/superpowers/plans/2026-11-19-library-queue-subtitles.md`, Tasks 3, 4, 5. The tasks below are copied from it verbatim; the parent plan wins if they ever differ. Phase index: `docs/superpowers/plans/2026-11-19-library-queue-subtitles-phases.md`.

**Revised 2026-11-19 after a dry run** (parent plan updated to match). The whole plan was applied in a throwaway worktree: server suite 384 passed, and `ruff check`, `ruff format --check` and `ty check` were clean. A live download of `QaVuJI6Mkv0` showed no SABR warning and wrote `*.fr-orig.srt` plus `*.fr-orig.txt` with `warning=None`.

**Prerequisites:** None. Server only (`apps/server/app/services/downloader.py` and its unit tests). The warning is not stored until Phase 3. Baseline: `cd apps/server && uv run pytest -q` → 371 passed.

## Global Constraints

- Run `pnpm check` (repo root) before every commit. Run `pnpm format` to fix formatting. Server lint is `ruff` with line length 100; test files must pass it too. No API schema change in this phase, so no `pnpm typegen`.
- Stack stays: FastAPI + yt-dlp (pinned 2026.10.26) + SQLite (Alembic) + worker threads. No new dependencies.
- yt-dlp never gets global `ignoreerrors`. Media failures must still fail the job.
- Never request an auto-translated subtitle track (any `automatic_captions` key except `<lang>-orig`).
- No database change in this phase.
- Follow the existing test layout: pytest `tests/unit`.
- All server commands run from `apps/server`.

## Review Focus

1. A French video with auto captions only gets `fr-orig`, never translated `en`. `player_client` is `["default", "-web_embedded"]`, which also removes `web_embedded` from yt-dlp's cookie-authenticated default set (`_DEFAULT_AUTHED_CLIENTS = ('web_embedded', 'tv_samsung', 'web')`).
2. A subtitle failure retries once without subtitles and the job ends `done`. A media error (403) is not retried and still fails. `DownloadCancelled` raised during a subtitle download is not a `DownloadError`, so it still cancels (verified against yt-dlp 2026.10.26).
3. The `output_template` branch now resolves first. The output-dir guard (`match_filter`) still applies on both branches, because it runs inside `process_ie_result`.

## Facts the design relies on (verified in yt-dlp 2026.10.26)

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
