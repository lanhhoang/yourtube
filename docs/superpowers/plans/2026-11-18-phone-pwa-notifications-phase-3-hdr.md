# Phase 3: HDR option Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Each job gets an opt-in HDR choice (off by default). With it on, the server takes an HDR video stream when one exists at the resolution the cap picks anyway.

**Usable result:** On a 4K HDR video, tick HDR, queue at "Best available", and get a 2160p HDR `.mp4` (VP9.2 or AV1 + AAC) that plays in HDR in IINA/VLC. On a video with no HDR the checkbox is greyed out. Playlists get "HDR where available" and an `HDR` / `HDR ≤1080p` badge per video.

**Architecture:** Server: a `downloads.hdr` column carries the choice to `cap_format_options`, which swaps `hdr:sdr` for `hdr` in the Phase 2 sort (`res` stays first, so resolution wins). The lookup adds `dynamic_range` to each picker stream row. Web: pure helpers in `quality.ts` work out "HDR at this cap?" from those rows. `VideoView` and `ListView` render a checkbox, a note and a badge from them.

**Tech Stack:** yt-dlp 2026.10.26, FastAPI/Pydantic, Alembic, Svelte 5, Vitest, Playwright, pytest. No new dependencies.

**Spec:** `docs/superpowers/specs/2026-11-18-hdr-option-design.md`. It builds on `docs/superpowers/specs/2026-11-18-phone-pwa-notifications-design.md` §1.

**Parent plan:** `docs/superpowers/plans/2026-11-18-phone-pwa-notifications.md`, Tasks 4, 5. The tasks below are copied from it verbatim; the parent plan wins if they ever differ. Phase index: `docs/superpowers/plans/2026-11-18-phone-pwa-notifications-phases.md`.

**Prerequisites:** Phase 2 merged (`CapFormat`, `MP4_SORT`, `merge_output_format` and the `requested_downloads` path exist).

## Global Constraints

- Run `pnpm check` (repo root) before every commit. Run `pnpm format` to fix formatting. After any API schema change, run `pnpm typegen` and commit `apps/web/src/lib/api.gen.ts`.
- Stack stays: FastAPI + yt-dlp + SQLite (Alembic) + worker threads; Svelte 5 + Vite + Tailwind 4; one process, one port. The Docker image ships everything.
- `DESIGN.md` is the visual contract. Red is the only accent. WCAG AA in both themes. Status is never shown by colour alone.
- Nothing loads from a CDN at runtime.
- Streams are copied and remuxed, never transcoded. No HDR output unless the job asks for HDR.
- Never silently download below the chosen cap (existing principle, unchanged).
- Database changes go through a new Alembic revision. Never edit an existing revision.
- Phone layout is below 768 px. Touch targets are at least 44 px.
- Follow the existing test layout: pytest `tests/unit`, `tests/api`, `tests/integration`; Vitest `apps/web/test`; Playwright `apps/web/e2e` (stubbed server `tests/e2e_server.py`).

## Review Focus

1. **HDR off is byte-for-byte Phase 2.** Every Phase 2 sort/pick test stays green unchanged, and `hdr=False` is the default everywhere (`DownloadCreate`, `run_download`, `cap_format_options`, the column's server default). Pinned by Task 4 Step 1 (`cap_format_options(..., hdr=False)` equality) and the untouched Phase 2 tests.
2. **HDR never costs resolution.** The HDR stream exists only at 1080p, the SDR one at 2160p, and the cap is best: the pick must be 2160p SDR. Pinned by `test_hdr_on_resolution_first` in Task 4.
3. **Exact format picks and audio ignore HDR.** A job with `video_format_id` and `hdr=True` gets no sort and no merge format. `audio` with `hdr=True` gives `ba/b`. Pinned in Task 4 Step 1 and Step 2.
4. **Old rows and old clients.** Rows from before the migration read `hdr = false`. A POST without `hdr` stores false. Pinned by the migration test and `test_enqueue_hdr_defaults_false` in Task 4.
5. **The note and the badge never claim HDR the cap won't get.** Cap 1440 on a 2160/1080 ladder with HDR at 1080 is `"yes"` (the cap lands on 1080). HDR only above the capped side is `"none"`. A muxed-only video is `"none"`. Pinned by the `hdrAtCap` cases in Task 5.

## Verified facts this plan relies on (2026-11-18, installed yt-dlp, offline)

Sort `[res[:N], "hdr", "vcodec:h264", "acodec:aac"]` with `format="bv*+ba/b"`, `merge_output_format="mp4"`:

- Phase 2's `HDR_SET` (SDR VP9 2160/1440/1080, H.264 1080, **AV1 HDR10 `701` at 2160**): best → `701+140`, 1440 → `308+140`, 1080 → `299+140`. All `.mp4`.
- `BOTH_SET` (2160: VP9 SDR `315`, VP9.2 HDR10 `337`, AV1 HDR10 `701`; 1080: H.264 `299`; AAC `140`): best → `337+140` (VP9.2 wins via `vcodec:h264`'s ranking, as the spec accepts).
- `LOW_SET` (2160: VP9 SDR `315`; 1080: AV1 HDR10 `699`, H.264 `299`; AAC `140`): best → `315+140` (resolution first), 1440 → `699+140`, 1080 → `699+140`.

---

### Task 4: HDR on the job, in the sort and in the lookup (server)

**Files:**
- Create: `apps/server/alembic/versions/20261118110000_add_hdr.py` (`down_revision = "20261115120000"`; non-null boolean `hdr`, `server_default=sa.false()`)
- Modify: `apps/server/app/models.py` (`Download.hdr`), `apps/server/app/schemas.py` (`DownloadCreate.hdr`, `JobOut.hdr`, `FormatInfo.dynamic_range`, `StreamRow.dynamic_range`), `apps/server/app/services/queue.py` (`_row_from_payload`)
- Modify: `apps/server/app/services/quality.py` (`cap_format_options`, docstring), `apps/server/app/services/downloader.py` (`normalize_formats`, `StreamPickerRow`, `_row` in `build_stream_picker_payload`, `run_download`), `apps/server/app/services/job_runner.py`
- Modify: `apps/server/tests/e2e_server.py` (`_video_info`'s `fmt` takes an optional `dr`; add a 2160p HDR10 stream `v2160hdr` only for URL `https://e2e.test/v/a`, and nothing else changes)
- Modify: `apps/web/src/lib/api.gen.ts` (typegen)
- Modify: `README.md` ("Quality caps": the HDR paragraph from spec §7)
- Test: `tests/unit/test_quality.py`, `tests/unit/test_downloader_progress.py`, `tests/unit/test_downloader_format.py`, `tests/unit/test_job_runner.py`, `tests/api/test_enqueue_api.py`, `tests/test_db.py`

**Interfaces:**
- Consumes (Phase 2): `CapFormat`, `MP4_SORT = ["hdr:sdr", "vcodec:h264", "acodec:aac"]`, `cap_format_options(cap, audio_bitrate=None) -> CapFormat`, `build_ytdlp_options(..., merge_output_format=None)`.
- Produces:
  - `cap_format_options(cap: QualityCap | None, audio_bitrate: str | None = None, hdr: bool = False) -> CapFormat`. For video caps with `hdr=True`, the sort is `MP4_SORT` with `"hdr"` in place of `"hdr:sdr"`. `audio` ignores `hdr`.
  - `run_download(..., hdr: bool = False)`. It is passed only to `cap_format_options` and ignored on the exact-ids branch.
  - `Download.hdr: Mapped[bool]` (non-null, default false). `DownloadCreate.hdr: bool = False`. `JobOut.hdr: bool`.
  - `FormatInfo.dynamic_range: str | None = None`, plus the picker row field `dynamic_range: str | None`, read through `_safe_str(raw.get("dynamic_range"))`.

- [ ] **Step 1: Write the failing quality tests** in `tests/unit/test_quality.py`. The `_select` helper gains `hdr: bool = False` and passes it to `cap_format_options`. Add `BOTH_SET` and `LOW_SET` from "Verified facts", built with `_fmt(..., dr=...)`.

```python
def test_cap_format_options_hdr() -> None:
    on = ["hdr", "vcodec:h264", "acodec:aac"]
    assert cap_format_options("best", hdr=True) == ("bv*+ba/b", ["res", *on], "mp4")
    assert cap_format_options("1080", "128", hdr=True) == ("bv*+ba/b", ["res:1080", *on, "abr:128"], "mp4")
    assert cap_format_options(None, hdr=True) == ("bv*+ba/b", ["res", *on], "mp4")
    assert cap_format_options("audio", hdr=True) == ("ba/b", None, None)
    assert cap_format_options("720", hdr=False) == cap_format_options("720")

def test_hdr_on_picks_hdr_at_top() -> None:
    assert _select(HDR_SET, "best", hdr=True) == ("701+140", "mp4")
    assert _select(BOTH_SET, "best", hdr=True) == ("337+140", "mp4")

def test_hdr_on_keeps_sdr_picks_where_no_hdr() -> None:
    assert _select(HDR_SET, "1440", hdr=True) == ("308+140", "mp4")
    assert _select(HDR_SET, "1080", hdr=True) == ("299+140", "mp4")

def test_hdr_on_resolution_first() -> None:
    assert _select(LOW_SET, "best", hdr=True) == ("315+140", "mp4")
    assert _select(LOW_SET, "1440", hdr=True) == ("699+140", "mp4")
```

- [ ] **Step 2: Write the failing plumbing tests**
  - `test_downloader_progress.py`: `test_run_download_hdr_sort`: `quality_cap="best", hdr=True` → `format_sort == ["res", "hdr", "vcodec:h264", "acodec:aac"]`. `test_run_download_exact_ids_ignore_hdr`: `video_format_id="137", audio_format_id="140", hdr=True` → `"format_sort" not in opts and "merge_output_format" not in opts`.
  - `test_downloader_format.py`: `normalize_formats` on a raw format with `"dynamic_range": "HDR10"` gives `dynamic_range == "HDR10"`, a missing key gives `None`, and `build_stream_picker_payload` rows carry it.
  - `test_job_runner.py`: copy `test_job_runner_passes_quality_cap` as `test_job_runner_passes_hdr` with `DownloadCreate(..., quality_cap="best", hdr=True)` → `seen["hdr"] is True`. In the existing test, assert `seen["hdr"] is False`.
  - `test_enqueue_api.py`: `test_enqueue_hdr_roundtrip`: posting `{"url": U, "quality_cap": "best", "hdr": True}` gives `created[0]["hdr"] is True`. `test_enqueue_hdr_defaults_false`: no `hdr` key gives `False`.
  - `tests/test_db.py`: `test_downloads_has_hdr_column`. Rewrite `test_migration_downgrade_and_upgrade` so it targets revisions by id rather than `-1` (later phases add revisions on top): upgrade to `head` and assert `hdr` is in the columns; downgrade to `"20261115120000"` and assert `hdr` is gone and `quality_cap` is still there; upgrade to `head` again and assert `hdr` is back.

- [ ] **Step 3: Run them and see them fail**

Run: `cd apps/server && uv run pytest tests/unit/test_quality.py tests/unit/test_downloader_progress.py tests/unit/test_downloader_format.py tests/unit/test_job_runner.py tests/api/test_enqueue_api.py tests/test_db.py -q`
Expected: FAIL (`unexpected keyword argument 'hdr'`, missing column/field).

- [ ] **Step 4: Implement** to the interfaces above: the migration, model, schemas, `_row_from_payload`, `normalize_formats` + picker row, `cap_format_options`, `run_download`, and `job_runner` (read `job.hdr` with the other fields and pass `hdr=`). Update the `quality.py` docstring: `hdr` on means `"hdr"` in place of `"hdr:sdr"`, `res` first means resolution wins, and VP9.2 beats AV1 HDR because of `vcodec:h264` (accepted; see spec Approaches).

- [ ] **Step 5: Run the server suite**

Run: `cd apps/server && uv run pytest -q`
Expected: PASS.

- [ ] **Step 6: Typegen, README, check, commit**

Run: `pnpm typegen && pnpm check`. README "Quality caps" gains: "HDR: off by default. When ticked, a video that offers HDR at the resolution your cap picks downloads in HDR (VP9.2 or AV1 + AAC, `.mp4`); otherwise you get the normal SDR file. HDR files play in VLC, IINA and mpv, not in Safari, QuickTime or on iPhone."
Commit: `feat(server): opt-in HDR per job, resolution first`

### Task 5: HDR checkbox, note and badge (web)

**Files:**
- Modify: `apps/web/src/lib/quality.ts`, `apps/web/src/lib/playlist.ts` (`Header.hdr`, `buildJobs`), `apps/web/src/lib/badges.ts` (`hdrBadgeFor`)
- Modify: `apps/web/src/routes/VideoView.svelte`, `apps/web/src/routes/ListView.svelte`, `apps/web/src/components/EntryCard.svelte` (render the second badge), `apps/web/src/components/FormatPicker.svelte` (an `HDR` tag in `detail()` for HDR rows)
- Test: `apps/web/test/quality.test.ts`, `apps/web/test/badges.test.ts`, `apps/web/test/playlist.test.ts`, `apps/web/e2e/video.spec.ts`, `apps/web/e2e/playlist.spec.ts`

**Interfaces:**
- Consumes: `StreamRow.dynamic_range`, `JobCreate.hdr` (Task 4, via `api.gen.ts`).
- Produces (`quality.ts`; `Row = components["schemas"]["StreamRow"]`):
  - `isHdr(row: Row): boolean`: `dynamic_range` is set and is not `"SDR"`.
  - `hdrSide(rows: Row[]): number | null`: the largest short side among HDR rows.
  - `cappedSide(cap: QualityCap, rows: Row[]): number | null`: the server's `res[:N]` rule. `best` gives the largest side. N gives the largest side ≤ N, else the smallest side above N. `audio` or no rows gives `null`.
  - `hdrAtCap(cap: QualityCap, rows: Row[]): { kind: "none" } | { kind: "yes" } | { kind: "below"; side: number }`.
  - `badges.ts`: `hdrBadgeFor(e: EntryState, cap: QualityCap): { label: string } | null`.
  - `playlist.ts`: `Header.hdr: boolean`. `buildJobs` sets `hdr: header.hdr` on every job.

- [ ] **Step 1: Write the failing helper tests** in `quality.test.ts`. Use a `row(w, h, dr?)` builder.

```ts
const S = [row(3840, 2160, "SDR"), row(1920, 1080, "SDR"), row(1920, 1080, "HDR10")];
test("cappedSide follows res:N", () => {
  expect(cappedSide("best", S)).toBe(2160);
  expect(cappedSide("1440", S)).toBe(1080);
  expect(cappedSide("480", S)).toBe(1080);
  expect(cappedSide("audio", S)).toBeNull();
});
test("hdrAtCap", () => {
  expect(hdrAtCap("best", S)).toEqual({ kind: "below", side: 1080 });
  expect(hdrAtCap("1440", S)).toEqual({ kind: "yes" });
  expect(hdrAtCap("1080", S)).toEqual({ kind: "yes" });
  expect(hdrAtCap("audio", S)).toEqual({ kind: "none" });
  expect(hdrAtCap("best", [row(1920, 1080, "SDR")])).toEqual({ kind: "none" });
  expect(hdrAtCap("720", [row(1280, 720, "SDR"), row(3840, 2160, "HDR10")])).toEqual({ kind: "none" });
  expect(hdrAtCap("best", [row(1080, 1920, "HLG")])).toEqual({ kind: "yes" }); // vertical: short side
  expect(hdrAtCap("best", [])).toEqual({ kind: "none" }); // muxed-only
});
```

- [ ] **Step 2: Write the failing badge and job tests**
  - `badges.test.ts`: `hdrBadgeFor` returns `{ label: "HDR" }` for `"yes"`, `{ label: "HDR ≤1080p" }` for `"below"`, and `null` for: no HDR, cap `audio`, an entry with an override, a failed check, and `"checking"`.
  - `playlist.test.ts`: add `hdr: false` to the shared `header`. A new test: `buildJobs(entries, { ...header, hdr: true })` puts `hdr: true` on every job, including the one with an override.

- [ ] **Step 3: Run them and see them fail**

Run: `pnpm vitest run apps/web/test/quality.test.ts apps/web/test/badges.test.ts apps/web/test/playlist.test.ts`
Expected: FAIL (missing exports / `hdr` not on jobs).

- [ ] **Step 4: Implement the helpers, `hdrBadgeFor` and `buildJobs`** to the interfaces above.

- [ ] **Step 5: Implement the UI** (spec §5, §6; exact copy below):
  - `VideoView`: below `QualitySelect`, add `<label>` + checkbox `HDR`, with the row at least 44 px tall. Disabled when `hdrSide(video.picker.video_streams) === null` (label text `HDR (not offered)`) or `cap === "audio"` (label `HDR`). An `$effect` clears `hdr` when it becomes disabled; it does not restore it. When an exact format is picked, the checkbox dims with Quality (same `opacity-50` as `QualitySelect`'s `dimmed`). When `hdr` is ticked and `hdrAtCap` is `"below"`, a `text-sm text-muted` note reads `HDR only up to {side}p. This cap gets SDR.` The job body sends `hdr` (`false` while disabled).
  - `ListView`: a checkbox `HDR where available` next to Subtitles, disabled when `cap === "audio"` (and cleared then). `header` gets `hdr`.
  - `EntryCard`: render `hdrBadgeFor(item, cap)` next to the existing badge, in the neutral tone (the existing non-danger badge tone in `EntryCard`'s `tone` map).
  - `FormatPicker`: `detail()` appends `HDR` when `isHdr(r)` (e.g. `av01 · mp4 · HDR`).

- [ ] **Step 6: Write the e2e tests.** The Task 4 stub gives `https://e2e.test/v/a` a 2160p HDR10 stream; `/video` and `/v/b` have none.
  - `video.spec.ts` "HDR is disabled when the video has no HDR": fetch `https://e2e.test/video` → `getByRole("checkbox", { name: "HDR (not offered)" })` is disabled.
  - `video.spec.ts` "HDR can be ticked on an HDR video": fetch `https://e2e.test/v/a` → `getByRole("checkbox", { name: "HDR" })` is enabled. Tick it and add to queue. Check the request body: capture the POST with `page.waitForRequest` and assert `jobs[0].hdr === true`.
  - `playlist.spec.ts` "HDR badge follows the cap": after checks finish, select cap `best`. Video A's card shows `HDR` (exact text) and Video B's doesn't. Switch back to `1080`: Video A shows no HDR badge, because its HDR exists only above the capped side (`"none"`, spec §4).

- [ ] **Step 7: Run everything**

Run: `pnpm check && pnpm e2e`
Expected: PASS.

- [ ] **Step 8: Commit** `feat(web): HDR checkbox, note and per-video HDR badge`

- [ ] **Step 9: Check by hand in Docker** (ffmpeg is in the image only):

```bash
docker build -t yourtube . && mkdir -p /tmp/ythdr && rm -rf /tmp/ythdr/*
docker run --rm -v /tmp/ythdr:/out --entrypoint sh yourtube -c 'cd /app/apps/server && python -c "
from app.services.downloader import run_download
print(run_download(url=\"https://www.youtube.com/watch?v=LXb3EKWsInQ\", output_dir=\"/out\", quality_cap=\"best\", hdr=True))
" && ffprobe -v error -select_streams v:0 -show_entries stream=codec_name,color_transfer -of csv=p=0 /out/*.mp4'
```

Expected: the path ends in `.mp4`. ffprobe prints `vp9` or `av1` with `smpte2084` (PQ) or `arib-std-b67` (HLG). It's a ~2 GB download; run it once.

---

## Done when

- Both tasks are committed and `pnpm check && pnpm e2e` pass on the branch.
- Step 9 shows an HDR transfer on the downloaded file, and the same video with HDR off (Phase 2's check) shows `bt709`.
