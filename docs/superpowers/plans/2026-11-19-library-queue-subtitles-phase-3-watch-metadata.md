# Phase 3: Watch metadata: dynamic range and codecs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show `Channel · 1080p · SDR · 300 MB · av1 · aac · mp4` on the Watch page, including for videos downloaded before this change, and show the subtitle warning.

**Usable result:** Open any finished video: the line under the title shows resolution, SDR/HDR10/HLG, size, video and audio codec and container. Old items fill in after the next start (ffprobe). A video whose subtitles failed says "Subtitles couldn't be downloaded."

**Spec:** `docs/superpowers/specs/2026-11-19-library-queue-subtitles-design.md`

**Parent plan:** `docs/superpowers/plans/2026-11-19-library-queue-subtitles.md`, Tasks 6, 7, 8. The tasks below are copied from it verbatim; the parent plan wins if they ever differ. Phase index: `docs/superpowers/plans/2026-11-19-library-queue-subtitles-phases.md`.

**Prerequisites:** Phase 2 (Task 5 adds `DownloadResult.warning`, which Task 6 persists). If Phase 2 is not merged, Task 6 adds the `warning` field itself.

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

1. The ffprobe backfill never blocks startup; missing ffprobe or an unreadable file leaves nulls that are retried next start; cover art in audio files is not a video codec.
2. Merged downloads report the video stream's codec/dynamic range and the audio stream's codec, never `none`.
3. The migration downgrades cleanly to `20261118130000`.

---

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
  const v = { uploader: "Chan", media_kind: "video", resolution_height: 1080, dynamic_range: "SDR",
    file_size: 300 * 1024 ** 2, vcodec: "av01.0.08M.08", acodec: "mp4a.40.2", media_format: "mp4" } as JobOut;
  expect(watchMeta(v)).toBe("Chan · 1080p · SDR · 300.0 MB · av1 · aac · mp4");
  expect(watchMeta({ ...v, dynamic_range: "HDR10", resolution_height: 2160 })).toContain("2160p · HDR10");
  const a = { ...v, media_kind: "audio", resolution_height: null, dynamic_range: null, vcodec: null, acodec: "opus", media_format: "webm" } as JobOut;
  expect(watchMeta(a)).toBe("Chan · Audio · 300.0 MB · opus · webm");
  expect(watchMeta({ ...v, vcodec: null, acodec: null, dynamic_range: null })).toBe("Chan · 1080p · 300.0 MB · mp4");
});
```

  E2E: extend `"player opens from the library…"` with `await expect(page.getByText("E2E · 1080p · SDR · 4 B · h264 · aac · mp4")).toBeVisible()` (the seeded row from Task 6).
- [ ] **Step 2: Run them and see them fail.** `pnpm test`, `pnpm e2e -- library.spec.ts`
- [ ] **Step 3: Implement.** `Watch.svelte`: `meta = $derived(job ? watchMeta(job) : "")`. Under the meta line, when `job.warning_message`, add `<p class="m-0 mt-1 text-sm text-warn">{job.warning_message}</p>`, which is text, so it's never colour alone. Read `craft-floor.md` before editing.
- [ ] **Step 4: Run them and see them pass. Run `pnpm check`.**
- [ ] **Step 5: Commit.** `git commit -m "feat: show dynamic range and codecs on the watch page"`
