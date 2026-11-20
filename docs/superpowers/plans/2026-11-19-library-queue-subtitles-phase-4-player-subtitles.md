# Phase 4: Subtitles in the player Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Offer the downloaded subtitle files as tracks in the native player (off until picked), and delete them with their video.

**Usable result:** Open a video downloaded with subtitles: the player's captions menu lists e.g. "French (auto)" and "English"; picking one shows cues. Deleting the video removes its `.srt`/`.txt` files.

**Spec:** `docs/superpowers/specs/2026-11-19-library-queue-subtitles-design.md`

**Parent plan:** `docs/superpowers/plans/2026-11-19-library-queue-subtitles.md`, Tasks 9, 10. The tasks below are copied from it verbatim; the parent plan wins if they ever differ. Phase index: `docs/superpowers/plans/2026-11-19-library-queue-subtitles-phases.md`.

**Prerequisites:** Phase 2 recommended (new downloads have the right subtitle languages). Existing `.srt` sidecars work without it.

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

1. `lang` is a lookup key only: `../x`, `en.srt`, unknown → 404; nothing outside the media's folder is read.
2. `talk.mp4` never shows `talk-2.mp4`'s tracks (longer-stem rule).
3. Tracks have no `default` attribute; a failed track list never breaks playback.

---

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
