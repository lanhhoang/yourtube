# Phase 4: Subtitles in the player Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Offer the downloaded subtitle files as tracks in the native player (off until picked), and delete them with their video.

**Usable result:** Open a video downloaded with subtitles: the player's captions menu lists e.g. "French (auto)" and "English"; picking one shows cues. Deleting the video removes its `.srt`/`.vtt`/`.txt` files.

**Spec:** `docs/superpowers/specs/2026-11-19-library-queue-subtitles-design.md`

**Parent plan:** `docs/superpowers/plans/2026-11-19-library-queue-subtitles.md`, Tasks 9, 10. The tasks below match it; the parent plan wins if they ever differ. Phase index: `docs/superpowers/plans/2026-11-19-library-queue-subtitles-phases.md`.

**Prerequisites:** Phases 1–3 merged (`main` @ `998e04a`). Work on branch `20261120-library-queue-subtitles-phase-4-player-subtitles`. Existing `.srt` sidecars work without Phase 2.

**Revised 2026-11-20 after a readiness review against `main` @ `998e04a`.** Fixes:
- Svelte 5.57 only accepts a static `kind="captions"` track for `a11y_media_has_caption`, and biome's `useMediaCaption` flags the `{#each}` too. Verified with a scratch component: both still fire with `kind="subtitles"` tracks. So both ignore comments on `<video>` stay, with a new reason.
- The old longer-stem tests (`talk-2.en.srt`, `talk.2.en.srt`) were already excluded by the prefix and part-count checks, so they never exercised the rule. They're replaced with `talk.2.srt` next to `talk.2.mp4`.
- `library_layout._sidecars` gets its other stems from DB rows, not from the folder. Sharing it isn't worth the risk, so `library_layout.py` isn't touched.
- One sidecar finder (`media_sidecars`) is shared by the subtitle list and delete.
- `.vtt` files are passed through unchanged. Files are decoded as UTF-8 with `errors="replace"`.
- The e2e test now checks that the VTT is served and that delete removes the sidecars.
- There are no DB changes in this phase.

## Global Constraints

- Run `pnpm check` (repo root) before every commit. Run `pnpm format` to fix formatting. After any API schema change, run `pnpm typegen` and commit `apps/web/src/lib/api.gen.ts`.
- Stack stays: FastAPI + yt-dlp + SQLite (Alembic) + worker threads; Svelte 5 + Vite + Tailwind 4; one process, one port. No new dependencies.
- **No database changes in this phase.** No new Alembic revision.
- `DESIGN.md` is the visual contract. This phase adds no visible UI of our own: tracks show up in the browser's native captions menu. Don't add a custom captions control.
- Follow the existing test layout: pytest `apps/server/tests/unit`, `apps/server/tests/api`; Vitest `apps/web/test`; Playwright `apps/web/e2e` (stubbed server `apps/server/tests/e2e_server.py`). API tests use the `client` and `db_session_visible` fixtures and add rows the same way as `_add` in `tests/api/test_library_api.py`.
- Run the server tests from `apps/server` (`uv run pytest -q`).

## Review Focus

1. `lang` is a lookup key only. `../x`, `en.srt` and unknown langs all give 404. Files are only ever found by listing the media file's own folder.
2. `talk.mp4` never shows `talk.2.mp4`'s tracks (longer-stem rule).
3. Tracks have no `default` attribute. If the track list fails to load, playback still works.
4. Delete removes sidecars only after the media removal succeeded (or the media was already missing). It never touches another video's files.

---

### Task 9: Subtitle discovery and the VTT endpoint

**Files:**
- Create: `apps/server/app/services/subtitles.py`, `apps/server/tests/unit/test_subtitles.py`, `apps/server/tests/api/test_subtitles_api.py`
- Modify: `apps/server/app/api/jobs.py`, `apps/server/app/schemas.py`, `apps/web/src/lib/api.gen.ts` (typegen)
- Don't touch: `apps/server/app/services/library_layout.py`

**Interfaces (all in `app/services/subtitles.py` unless noted):**
- `MEDIA_EXTS = {"mp4", "mkv", "webm", "m4a", "mp3", "opus", "ogg", "flac", "wav", "mov", "m4v"}`
- `media_sidecars(media: Path) -> list[tuple[Path, str | None, str]]` returns `(path, lang, ext)` for every regular file in `media.parent` named `<stem>.<ext>` (lang `None`) or `<stem>.<lang>.<ext>`, where `ext` (lower-cased) is `srt`, `vtt` or `txt`. It skips `media` itself and names with more dot-parts after the stem. **Longer-stem rule:** skip a file if another file in the folder has a media extension and a longer stem `s`, and the file's name starts with `s + "."`. Return `[]` on `OSError` (folder missing). Sort the result by name.
- `subtitle_sidecars(media: Path) -> dict[str, Path]` maps lang to file, built from `media_sidecars` entries with a lang and ext `srt`/`vtt`. When a lang has both, `.vtt` wins.
- `srt_to_vtt(text: str) -> str` strips a leading BOM, turns `\r\n` and `\r` into `\n`, prepends `WEBVTT\n\n`, and turns `,` into `.` only in the two timestamps of a timestamp line (`HH:MM:SS,mmm --> HH:MM:SS,mmm`, anything after them kept). Cue numbers stay (VTT allows them as cue identifiers).
- `read_vtt(path: Path) -> str` reads the file as UTF-8 with `errors="replace"`. `.vtt` files are returned as-is, after stripping a BOM. `.srt` files go through `srt_to_vtt`.
- `app/schemas.py`: `class SubtitleTrackOut(BaseModel): lang: str; url: str`
- `GET /api/downloads/{job_id}/subtitles -> list[SubtitleTrackOut]` gives 404 `not_found` when the job is missing. It returns `[]` when the job isn't `done`, has no `file_path`, or is audio (use `JobOut.from_row(row).media_kind == "audio"` so the rule matches the rest of the app). Each URL is `/api/downloads/{id}/subtitles/{lang}.vtt`. Sort `-orig` tracks first, then by lang.
- `GET /api/downloads/{job_id}/subtitles/{lang}.vtt` returns 200 with `media_type="text/vtt; charset=utf-8"` and the `read_vtt` body. It gives 404 `not_found` when the job is missing, not done, has no file, or `lang` isn't a key of `subtitle_sidecars(resolve_repo_path(row.file_path))`. `lang` is only a dict key and is never joined into a path. Use `ApiError` the same way the `/file` route does.

- [ ] **Step 1: Write the failing tests.**
  - unit `test_srt_to_vtt`: `"\ufeff1\r\n00:00:01,000 --> 00:00:02,500\r\nHi, there\r\n"` gives `"WEBVTT\n\n1\n00:00:01.000 --> 00:00:02.500\nHi, there\n"`. The BOM is stripped and the comma in the text is kept.
  - unit `test_read_vtt_passes_vtt_through`: a `.vtt` file with `WEBVTT\n\n00:00.000 --> 00:01.000\nx\n` comes back unchanged.
  - unit `test_sidecars_found_and_vtt_wins`: `talk.mp4`, `talk.fr-orig.srt`, `talk.en.srt`, `talk.en.vtt`, `talk.txt`, `talk.en.txt` gives `subtitle_sidecars` = `{"fr-orig": …srt, "en": …vtt}`. `media_sidecars` returns all five non-media files.
  - unit `test_sidecars_ignore_longer_stem`: `talk.mp4`, `talk.2.mp4`, `talk.2.srt`, `talk.2.en.srt`, `talk-2.mp4`, `talk-2.en.srt` gives `media_sidecars(talk.mp4) == []`. `talk.2.srt` is the case the longer-stem rule must catch (without it, it reads as lang `"2"`). Also `subtitle_sidecars(talk.2.mp4) == {"en": …}`.
  - unit `test_sidecars_missing_folder`: a media path in a folder that doesn't exist gives `[]` / `{}`.
  - api `test_list_subtitles`: a done row whose `file_path` is `tmp_path/a.mp4`, with `resolution_height=1080` so it counts as video, plus `a.en.srt` and `a.fr-orig.srt`, gives `[{"lang":"fr-orig","url":f"/api/downloads/{id}/subtitles/fr-orig.vtt"},{"lang":"en","url":…"en.vtt"}]`.
  - api `test_list_subtitles_audio_is_empty`: done row, `resolution_height=None`, gives `[]`.
  - api `test_subtitles_not_done_is_empty`: a `queued` row gives `[]`.
  - api `test_subtitles_missing_job_404`: both routes with id `999999` give 404.
  - api `test_vtt_served`: `GET …/subtitles/en.vtt` gives 200, `content-type == "text/vtt; charset=utf-8"`, and a body that starts with `WEBVTT\n\n`.
  - api `test_vtt_unknown_lang_404`: `GET …/subtitles/de.vtt`, `…/subtitles/..%2Fx.vtt` and `…/subtitles/en.srt.vtt` all give 404. Assert status only: `..%2Fx` is caught by the API catch-all route, which is fine.
- [ ] **Step 2: Run them and see them fail.** `cd apps/server && uv run pytest -q tests/unit/test_subtitles.py tests/api/test_subtitles_api.py`
- [ ] **Step 3: Implement** the service, schema and two routes in `jobs.py`. Put the routes after `get_job`/`download_file`. Read `row.file_path` with `resolve_repo_path`, as the `/file` route does.
- [ ] **Step 4: Verify.** `uv run pytest -q` is green, `tests/unit/test_library_layout.py` included. Then `pnpm typegen` from the repo root.
- [ ] **Step 5: Commit** after `pnpm check`: `git commit -m "feat: list downloaded subtitles and serve them as WebVTT"`

### Task 10: Tracks in the player; delete removes sidecars

**Files:**
- Create: `apps/web/src/lib/subtitles.ts`, `apps/web/test/subtitles.test.ts`
- Modify: `apps/web/src/routes/Watch.svelte`, `apps/server/app/services/library.py`, `apps/server/tests/unit/test_library.py`, `apps/server/tests/e2e_server.py`, `apps/web/e2e/library.spec.ts`

**Interfaces:**
- Consumes `GET /api/downloads/{job_id}/subtitles` and `media_sidecars` (Task 9).
- Produces `trackLabel(lang: string, locale?: string): string` in `apps/web/src/lib/subtitles.ts`: `base = lang.replace(/-orig$/, "")`, then `name = new Intl.DisplayNames([locale ?? navigator.language], { type: "language" }).of(base) ?? base`. Return `` `${name} (auto)` `` when `lang` ends in `-orig`, otherwise `name`. If `of` throws (a `RangeError` for invalid codes), return `lang`.

**Server:** in `delete_from_library`, after the media `os.remove` succeeded or raised `FileNotFoundError`, and before deleting the row, remove every path from `media_sidecars(media)`. Catch `OSError` for each file, log it with `logger.warning` (add `logger = logging.getLogger("yourtube")`), and carry on. On `delete_failed` nothing is removed. The return value doesn't change.

- [ ] **Step 1: Write the failing tests.**
  - `apps/web/test/subtitles.test.ts`: `trackLabel("fr-orig","en")` is `"French (auto)"`. `trackLabel("en","en")` is `"English"`. `trackLabel("pt-BR","en")` is `"Brazilian Portuguese"`. `trackLabel("zz-invalid!","en")` is `"zz-invalid!"`.
  - `test_library.py::test_delete_removes_subtitle_sidecars`: `v.mp4`, `v.en.srt`, `v.en.txt`, `v.txt`, `v.2.mp4`, `v.2.srt`, `v-2.mp4`, `v-2.en.srt`. Deleting `v` leaves exactly `v.2.mp4`, `v.2.srt`, `v-2.mp4` and `v-2.en.srt`. Set up the row like `test_delete_from_library_removes_row_and_file`.
  - `test_library.py::test_delete_keeps_sidecars_when_media_delete_fails`: monkeypatch `os.remove` to raise `PermissionError` for the media path only. The result is `(False, "delete_failed")` and `v.en.srt` still exists.
  - `test_library.py::test_delete_removes_sidecars_when_media_missing`: `v.mp4` absent, `v.en.srt` present. The result is `(True, "file_missing")` and `v.en.srt` is gone.
  - e2e `apps/server/tests/e2e_server.py`: in `_seed`, write `seeded.en.srt` and `seeded.fr-orig.srt` (a one-cue SRT each) next to `seeded.mp4`. The startup layout move carries them to `e2e/seeded-video.en.srt` / `.fr-orig.srt`, because `_sidecars` moves `<stem>.<lang>.srt`.
  - e2e `library.spec.ts`, extending `"player opens from the library…"`: `page.locator("video track")` has count 2. Track 0 has label `French (auto)` and `srclang` `fr`, track 1 has label `English` and `srclang` `en`. Neither has the `default` attribute (`not.toHaveAttribute("default")`). `kind` is `subtitles`. `page.request.get(<track 0 src>)` gives 200 and a body that starts with `WEBVTT`.
  - e2e `library.spec.ts`, extending `"delete in library"`: before the delete, `e2e/seeded-video.en.srt` exists. After it, poll until both `.srt` files are gone.
- [ ] **Step 2: Run them and see them fail.** `pnpm test`, `cd apps/server && uv run pytest -q tests/unit/test_library.py`, `pnpm e2e library` (filters go without `--`).
- [ ] **Step 3: Implement.**
  - `Watch.svelte`: add `let tracks = $state<SubtitleTrackOut[]>([])`, typed from `api.gen.ts` `components["schemas"]["SubtitleTrackOut"]`. After `job` loads in the existing effect, if `job.status === "done" && job.media_kind === "video"`, call `call(api.GET("/api/downloads/{job_id}/subtitles", { params: { path: { job_id: id } } }))` and set `tracks`. Wrap it in its own `try/catch {}`, so a failure leaves `tracks = []`, sets no `error`, and doesn't block `phase = "ready"`. Set `phase = "ready"` before awaiting subtitles so the player isn't delayed.
  - Inside `<video>`: `{#each tracks as t (t.lang)}<track kind="subtitles" src={t.url} srclang={t.lang.replace(/-orig$/, "")} label={trackLabel(t.lang)} />{/each}`. No `default`, no `crossorigin` (same origin).
  - Keep both `<!-- svelte-ignore a11y_media_has_caption -->` and `<!-- biome-ignore lint/a11y/useMediaCaption: … -->` on `<video>`, and change the reason to `subtitle tracks are kind="subtitles" and only exist when they were downloaded`. Keep the `<audio>` one as it is.
  - `library.py`: sidecar removal as described above.
- [ ] **Step 4: Verify.** The new tests pass. Run `pnpm check` and `pnpm e2e`. Manual check: put a real `.srt` next to a library video (or download one with subtitles), open it in Chrome and in Safari, pick each track in the native captions menu, and confirm the cues render. Then delete the video and confirm the `.srt`/`.txt` files are gone.
- [ ] **Step 5: Commit.** `git commit -m "feat: downloaded subtitles in the player; delete removes sidecars"`
