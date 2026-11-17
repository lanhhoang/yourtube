# Phase 4: Single video with quality cap Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Paste a single video URL in the new UI, see the watch-page layout, pick "Up to 1080p" (or another cap) or an exact format, toggle subtitles, set Advanced options, and add it to the queue; it downloads at the right quality (vertical videos are judged by their short side). A `watch?v=X&list=Y` URL opens the video, and adding it downloads only that video. Playlists still use the old UI.

**Parent plan:** `docs/superpowers/plans/2026-11-15-svelte-ui.md`, section "Phase 4: Single video with quality cap". The tasks below are copied from it verbatim. If they ever differ, the parent plan wins.

**Phase index:** `docs/superpowers/plans/2026-11-15-svelte-ui-phases.md`

**Spec:** `docs/superpowers/specs/2026-11-15-svelte-ui-design.md`

**Prerequisites:** Phase 3.

**Tasks:** Task 4.1 Quality cap in the database and the downloader, Task 4.2 Enqueue API, Task 4.3 Sources API (what a Fetch returns), Task 4.4 Fetch route and single-video screen.

## Architecture and stack (from the parent plan)

**Architecture:** The FastAPI backend moves to `apps/server` and gains JSON routes under `/api`. The Svelte app lives in `apps/web` and calls them through `openapi-fetch`, with types generated from FastAPI's OpenAPI schema and checked for drift. In production FastAPI also serves the built SPA, so it is still one process on one port. The work is built feature by feature: each phase adds the API and the screens for one feature, and the old UI keeps working until the last phase deletes it.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2, Alembic, yt-dlp, uv, ruff, ty, pytest. Node 24, pnpm 12.9.1, Svelte 5 (runes), Vite 8, `@sveltejs/vite-plugin-svelte` 7, Tailwind CSS 4 (`@tailwindcss/vite`), TypeScript (`svelte-check --tsgo`), Biome 2.6, Vitest 5, Playwright 1.65, `openapi-typescript` 7, `openapi-fetch` 0.17, `@fontsource`.

## Global Constraints (from the parent plan)

- **Old UI keeps working until Phase 6.** No phase before 6 removes or changes the behaviour of a Jinja page, an HTMX route or `/downloads/{id}/file`. The full old test suite stays green until Phase 6 deletes the old tests together with the old code.
- **Where the SPA is served:** in Phases 2–5 the built SPA is served at `/app` (hash routes such as `/app#/queue`), because the Jinja pages still own `/`, `/queue`, `/library` and `/settings`. Phase 6 serves it at `/`. Vite `base` stays `/`; assets live at `/assets/*` and do not collide with the old `/static/*`.
- **SPA serving rules (spec):** real files in `apps/web/dist` by path; `index.html` for app paths; 404 for a missing path that has a file extension; 404 JSON error for any unknown `/api/...` path. `/health` stays at `/health`.
- **Error body** for every `/api` error: `{"error": {"code": str, "message": str}}`. The web app may show `message`. Old HTML routes keep FastAPI's default errors.
- **Pydantic schemas in `app/schemas.py` are the only response models.** Routes never return ORM rows.
- **Quality caps:** exactly `best`, `2160`, `1440`, `1080`, `720`, `480`, `audio`. Default in the UI: `1080` ("Up to 1080p"). The cap compares against the **short side** (min of width and height). Exact format ids win over the cap.
- **Batch limit:** 500 entries per fetch; extra entries are dropped and counted in `skipped`, which the UI shows as "Skipped N".
- **Playlist checking:** from the browser, at most `CHECK_CONCURRENCY = 2` lookups at a time (the spec allows 2–3; 2 because playlist 403s were just fixed). Only selected entries are looked up. Leaving the page stops checking.
- **Theme:** `dark` (default) | `light` | `system`, in `localStorage` key `theme`, applied by an inline script in `index.html` before first paint. Not `system` by default.
- **Session storage key for completion toasts:** `yt-seen-completed-jobs` (same key as today, ids as strings).
- **No runtime CDN.** Fonts come from `@fontsource` packages; nothing loads from Google Fonts.
- **Red is the only accent.** Amber only for "below your cap"; an error tone for failures. Exact values come from `DESIGN.md` and must pass WCAG AA in both themes.
- **Computer only.** Design at 1280 and 1440 widths. Narrow windows may scroll but must not overlap or clip controls.
- **Not used:** Paraglide, PWA, SvelteKit, WebSocket/SSE, server-side playlist checking, taste-skill (`design-taste-frontend`) for app screens.
- **`.env` stays at the repo root.** `apps/server/app/config.py` reads it by absolute path. Relative `YT_DATA_DIR` / `YT_DOWNLOADS_DIR` / `YT_COOKIES_PATH` resolve against the repo root, so `./tmp/data` keeps meaning `<repo>/tmp/data`.
- **Checks before every commit (from Phase 2 on):** `pnpm check` must pass. In Phase 1 that is `pnpm check` with only server checks.
- **UI work:** before any edit to a `.svelte` file or `app.css`, read impeccable's `reference/craft-floor.md` (`/Users/lanh/.agents/skills/impeccable/`) and follow `PRODUCT.md` and `DESIGN.md` at the repo root.
- **Coverage gate:** `pytest --cov=app --cov-fail-under=50` stays in `pnpm check` and CI.

## Review Focus for this phase

2. **An output template that escapes the downloads folder** (`../x.%(ext)s`) sent to the JSON enqueue. Today it fails only when the download starts. The API must reject it at enqueue with a 422 error body and create no row. Test: `test_enqueue_rejects_escaping_output_template` (Task 4.2).
3. **Duplicates and oversize lists in a fetch.** The same video pasted twice, or present in two pasted playlists, appears once. A list over 500 shows the first 500 and "Skipped N". Tests: `test_list_sources_dedupes_across_sources`, `test_list_sources_caps_at_500` (Task 4.3).

The numbers are the parent plan's Review Focus numbers. The tests that pin them are in this phase's tasks.

## File Structure

See the parent plan's "File Structure" for the final layout. This phase touches only the files named in its tasks' **Files** blocks.

---

## Phase 4: Single video with quality cap

**Usable result:** paste a single video URL in the new UI, see the watch-page layout, pick "Up to 1080p" (or another cap) or an exact format, toggle subtitles, set Advanced options, and add it to the queue; it downloads at the right quality (vertical videos are judged by their short side). A `watch?v=X&list=Y` URL opens the video, and adding it downloads only that video. Playlists still use the old UI.

**Decisions recorded for this phase (owner, 2026-11-16):**

- `resolution_height` stores the **short side** (`min(width, height)`) of the downloaded file, so a vertical 1080×1920 video is labelled 1080p in both UIs. The old UI's label for vertical videos changes; that is accepted and is not a breach of "old UI keeps working".
- The new JSON enqueue rejects **absolute** output templates as well as ones with `..` (422 `invalid_request`). The check lives in the `JobCreate` validator; `resolve_output_template` and the old UI keep allowing absolute templates until Phase 6.

### Task 4.1: Quality cap in the database and the downloader

**Files:**

- Create: `apps/server/app/services/quality.py`, `apps/server/alembic/versions/20261115120000_add_quality_cap.py`, `apps/server/tests/fixtures/quality_cases.json`
- Modify: `apps/server/app/models.py`, `apps/server/app/services/downloader.py`, `apps/server/app/services/job_runner.py`, `apps/server/app/services/queue.py` (`enqueue_download` stores the cap), `apps/server/app/schemas.py` (`QualityCap`, `DownloadCreate.quality_cap`, `JobOut.quality_cap`, `media_kind` rule)
- Test: `apps/server/tests/unit/test_quality.py`, `apps/server/tests/test_db.py`, `apps/server/tests/unit/test_job_runner.py`, `apps/server/tests/unit/test_downloader_progress.py` (short-side metadata)

**Interfaces:**

- `schemas.py` gains `type QualityCap = Literal["best", "2160", "1440", "1080", "720", "480", "audio"]` next to `StreamKind`, so OpenAPI emits a named `QualityCap` component. `quality.py` imports it from `schemas` (it already imports `FormatInfo` from there).
- `quality.py`:
  ```python
  QUALITY_CAPS: tuple[QualityCap, ...]  # derived with typing.get_args(QualityCap.__value__)
  def short_side(width: int | None, height: int | None) -> int | None      # min of the non-null values; None if both null
  def best_short_side(formats: list[FormatInfo]) -> int | None            # max short side over stream_kind "video" or "muxed"
  def is_below_cap(cap: QualityCap, best: int | None) -> bool            # cap is numeric and best is not None and best < int(cap)
  def bitrate_kbps(audio_bitrate: str | None) -> int | None              # "192" / "192k" / "192K" → 192; None/"" → None
  def cap_format_options(cap: QualityCap | None, audio_bitrate: str | None = None) -> tuple[str | None, list[str] | None]   # (format, format_sort)
  ```
  `cap_format_options`: `None`/`"best"` → `(None, sort)`; numeric N → `("bv*+ba/b", [f"res:{N}", *abr])`; `"audio"` → `("ba/b", abr or None)`, where `abr = [f"abr:{bitrate_kbps(audio_bitrate)}"]` when a bitrate is set, else `[]`, and `sort` is `abr or None`. The bitrate must be passed as bare digits: yt-dlp misreads `abr:192K` (checked: it picks the 256k stream).
  Module docstring records why `format_sort`: yt-dlp's `res` sort field is `min(height, width)` (`yt_dlp/utils/_utils.py`), so `res:N` prefers the largest short side ≤ N and never fails; if a video has nothing ≤ N it takes the closest above. A `ba[abr<=N]` filter was rejected because it picks the _worst_ matching audio. All of this was checked offline against yt-dlp 2026.10.26.
- Migration `20261115120000` (down `20260609233000`): `with op.batch_alter_table("downloads") as batch: batch.add_column(sa.Column("quality_cap", sa.String(), nullable=True))`; downgrade drops it the same way.
- `Download.quality_cap: Mapped[str | None]`. `DownloadCreate.quality_cap: QualityCap | None = None`; `DownloadCreate.audio_bitrate` gains a validator: blank → `None`, otherwise it must match `^\d+[kK]?$` (old form posts already send values like `192K`). `JobOut.quality_cap: QualityCap | None`. `media_kind` is `"audio"` when (audio id and no video id) **or** (`quality_cap == "audio"` and no video id) **or** (`done` and `resolution_height is None`).
- `downloader.py`:
  - `build_ytdlp_options(..., format_sort: list[str] | None = None)` sets `options["format_sort"]` only when not `None`.
  - `run_download(..., quality_cap: QualityCap | None = None)`: when either exact id is set → today's selector and no `format_sort`; otherwise `cap_format_options(quality_cap, audio_bitrate)`. So an old-UI job (no ids, no cap) with a bitrate now gets `format_sort=["abr:N"]`, which is what its bitrate field always promised; with no bitrate it behaves exactly as today.
  - `_extract_file_metadata`: `resolution_height = short_side(info.get("width"), info.get("height"))` (owner decision above). yt-dlp keeps `width`/`height` on a merged result (checked), so this is right for `bv*+ba` downloads.
- `job_runner.run_claimed_job` reads `job.quality_cap` and passes it to `run_download`.
- `quality_cases.json`: list of `{ "name", "formats": [{"width", "height", "kind"}], "cap", "best_short_side", "below_cap" }`, `kind` one of `video` / `audio` / `muxed`. Include at least: landscape 1920×1080 cap 1080 (1080, false); vertical 1080×1920 cap 1080 (1080, false); 1280×720 only, cap 1080 (720, true); 3840×2160 cap 1440 (2160, false); audio-only formats (null, false); cap `best` with 720 (720, false); cap `audio` with 720 (720, false); muxed 640×360 only, cap 480 (360, true). Task 4.4's web tests read the same file.

- [ ] **Step 1: Write the failing tests**

```python
CASES = json.loads((Path(__file__).parents[1] / "fixtures" / "quality_cases.json").read_text())

@pytest.mark.parametrize("case", CASES, ids=lambda c: c["name"])
def test_shared_quality_cases(case):
    formats = [FormatInfo(format_id=str(i), ext="mp4", stream_kind=f["kind"], width=f["width"], height=f["height"]) for i, f in enumerate(case["formats"])]
    assert best_short_side(formats) == case["best_short_side"]
    assert is_below_cap(case["cap"], case["best_short_side"]) is case["below_cap"]

def test_cap_format_options():
    assert cap_format_options(None) == (None, None) and cap_format_options("best") == (None, None)
    assert cap_format_options("720") == ("bv*+ba/b", ["res:720"])
    assert cap_format_options("720", "192K") == ("bv*+ba/b", ["res:720", "abr:192"])
    assert cap_format_options("audio") == ("ba/b", None)
    assert cap_format_options("audio", "128") == ("ba/b", ["abr:128"])
    assert cap_format_options(None, "128k") == (None, ["abr:128"])

# Offline yt-dlp selection: build an info dict (extractor "generic", formats with url/protocol "https") and run
# ydl.process_ie_result(info, download=False) with the cap's format/format_sort. No network.
def test_cap_selects_vertical_1080_offline(): ...      # v1080 (1080x1920), v1440 (1440x2560), a1 → cap "1080" picks "v1080+a1"
def test_cap_falls_back_above_when_nothing_below(): ... # only v720 and a1, cap "480" → "v720+a1" (never fails)
def test_cap_with_bitrate_offline(): ...               # a50/a128/a160 + v720/v1080, cap "720", bitrate "128" → "v720+a128"

def test_audio_bitrate_validator(): ...                # "192K" ok, "" → None, "loud" → ValidationError
def test_media_kind_audio_for_audio_cap(): ...         # quality_cap "audio", no ids, queued → "audio"; with video id → "video"
def test_metadata_uses_short_side(): ...               # test_downloader_progress style: info width 1080 height 1920 → resolution_height 1080
def test_run_download_exact_ids_win(monkeypatch): ...  # capture ydl_opts: format "137+140", no "format_sort"
def test_run_download_uses_cap(monkeypatch): ...       # quality_cap="720" → format "bv*+ba/b", format_sort ["res:720"]
def test_run_download_no_cap_no_bitrate_unchanged(monkeypatch): ...  # neither "format" nor "format_sort" in ydl_opts
def test_job_runner_passes_quality_cap(...): ...       # extend test_job_runner: stored cap reaches run_download
def test_old_enqueue_leaves_cap_null(db_session): ...  # enqueue_download(DownloadCreate(url=U)) → row.quality_cap is None
def test_downloads_has_quality_cap_column(db_inspector): assert "quality_cap" in {c["name"] for c in db_inspector.get_columns("downloads")}
def test_migration_downgrade_and_upgrade(tmp_path, monkeypatch):
    # alembic/env.py replaces sqlalchemy.url with settings.database_url, so point settings at a fresh file:
    monkeypatch.setattr(settings, "database_url", f"sqlite:///{tmp_path / 'm.db'}")
    # command.upgrade(cfg, "head"); command.downgrade(cfg, "-1") → column gone; command.upgrade(cfg, "head") → column back
```

- [ ] **Step 2:** `cd apps/server && uv run pytest tests/unit/test_quality.py tests/test_db.py tests/unit/test_job_runner.py tests/unit/test_downloader_progress.py -v` → FAIL.
- [ ] **Step 3: Implement.** The offline checks above already pass with `format_sort` on yt-dlp 2026.10.26. If a future yt-dlp breaks them, fall back to `bv*[height<=N]+ba/b` and record why in `quality.py` (spec allows it).
- [ ] **Step 4:** `pnpm typegen && pnpm check` → PASS (old UI tests included: old enqueue leaves `quality_cap` null and behaves as before; existing landscape metadata tests still read 1080/720).
- [ ] **Step 5: Commit** `git add -A && git commit -m "feat: quality cap column, migration and cap-to-format mapping"`

### Task 4.2: Enqueue API

**Files:**

- Modify: `apps/server/app/schemas.py`, `apps/server/app/api/jobs.py`, `apps/server/app/services/queue.py` (`enqueue_downloads`)
- Test: `apps/server/tests/api/test_enqueue_api.py`, `apps/server/tests/unit/test_queue.py` (or the existing queue test module)

**Interfaces:**

- Schemas:
  ```python
  class JobCreate(DownloadCreate):   # quality_cap and the audio_bitrate rule come from DownloadCreate (Task 4.1)
      @field_validator("output_template")
      # blank → None; an absolute path (Path(v).is_absolute()) → ValueError("Output template must be relative to the downloads folder.");
      # then resolve_output_template(v, "/tmp") so ".." raises ValueError → 422
  class EnqueueRequest(BaseModel): jobs: list[JobCreate] = Field(min_length=1, max_length=500)
  class EnqueueResult(BaseModel): created: list[JobOut]
  ```
- `queue.enqueue_downloads(session, payloads: list[DownloadCreate]) -> list[Download]`: adds every row, one `commit()`, refreshes and returns them. `enqueue_download` is unchanged (the old UI keeps using it).
- `POST /api/downloads` (`EnqueueRequest`) → 201 `EnqueueResult`. Pydantic validates every job before the handler runs, and `enqueue_downloads` writes them in one transaction, so a bad job creates nothing. Used for both one video and many. Each created row has the same `title`/`uploader`/`duration`/`thumbnail` the client sent.

- [ ] **Step 1: Write the failing tests**

```python
def test_enqueue_single_with_cap(client, ...): r = post({"jobs": [{"url": U, "quality_cap": "720"}]}); assert r.status_code == 201 and r.json()["created"][0]["quality_cap"] == "720"
def test_enqueue_mixed_cap_and_exact(client, ...): ...  # job A cap "1080", job B video_format_id "137" + audio "140"; both stored as sent
def test_enqueue_rejects_escaping_output_template(client, ...):
    r = post({"jobs": [{"url": U, "output_template": "../x.%(ext)s"}]})
    assert r.status_code == 422 and r.json()["error"]["code"] == "invalid_request" and count_rows() == 0
def test_enqueue_rejects_absolute_output_template(client, ...): ...  # "/tmp/x.%(ext)s" → 422, 0 rows
def test_enqueue_rejects_bad_bitrate(client): assert post({"jobs": [{"url": U, "audio_bitrate": "loud"}]}).status_code == 422
def test_enqueue_rejects_unknown_cap(client): assert post({"jobs": [{"url": U, "quality_cap": "999"}]}).status_code == 422
def test_enqueue_rejects_empty_jobs(client): assert post({"jobs": []}).status_code == 422
def test_enqueue_one_bad_job_creates_nothing(client, ...): ...  # second job has url "" → 422, 0 rows
def test_enqueue_downloads_single_commit(db_session): ...      # two payloads → two rows, both visible after one call
```

- [ ] **Step 2:** run → FAIL. **Step 3:** implement. **Step 4:** `pnpm typegen && pnpm check` → PASS.
- [ ] **Step 5: Commit** `git add -A && git commit -m "feat(api): enqueue endpoint with quality cap"`

### Task 4.3: Sources API (what a Fetch returns)

**Files:**

- Create: `apps/server/app/services/sources.py`, `apps/server/app/api/fetch.py`
- Modify: `apps/server/app/services/downloader.py` (`noplaylist`; `width` in picker rows), `apps/server/app/services/batch_preview.py` (import `parse_source_urls` and `entry_url` from `sources`; behaviour unchanged), `apps/server/app/services/enqueue_intake.py` (import `parse_source_urls` from `sources`), `apps/server/app/schemas.py`, `apps/server/app/api/__init__.py`
- Move tests: the `parse_source_urls` tests from `tests/unit/test_batch_preview.py` to `tests/unit/test_sources.py`
- Test: `apps/server/tests/unit/test_sources.py`, `apps/server/tests/api/test_sources_api.py`

**Interfaces:**

- `extract_info(url, *, proxy=None, cookies_file=None, noplaylist=False)` and `extract_flat_info(..., noplaylist=False)` set `ydl_opts["noplaylist"] = True` when asked.
- Schemas:
  ```python
  class StreamRow(BaseModel): format_id: str; ext: str; resolution: str | None; height: int | None; width: int | None; vcodec: str | None; acodec: str | None; abr: float | None; audio_channels: int | None; container: str | None
  class StreamPicker(BaseModel): video_streams: list[StreamRow]; audio_streams: list[StreamRow]; has_muxed_streams: bool; expected_container_by_pair: dict[str, str]
  class VideoDetails(BaseModel): url: str; title: str; uploader: str | None; duration: int | None; thumbnail: str | None; picker: StreamPicker; best_short_side: int | None; playlist_url: str | None
  class SourceEntry(BaseModel): index: int; url: str; title: str | None; uploader: str | None; duration: int | None; thumbnail: str | None; error_code: str | None = None; error_message: str | None = None; details: VideoDetails | None = None
  class SourcesRequest(BaseModel): urls: str = Field(min_length=1); use_proxy: bool = False; use_cookies: bool = False
  class SourcesResult(BaseModel): kind: Literal["video", "list"]; title: str | None; video: VideoDetails | None; entries: list[SourceEntry]; skipped: int
  ```
  `StreamRow` gains `width` versus today's `StreamPickerRow` TypedDict; `build_stream_picker_payload` adds it (the old templates ignore the extra key).
- `sources.py`:
  ```python
  MAX_ENTRIES = 500
  def parse_source_urls(raw: str, *, dedupe: bool = True) -> list[str]   # moved verbatim
  def entry_url(entry: dict[str, object]) -> str | None                    # moved from batch_preview._entry_url
  def playlist_url_for(url: str) -> str | None   # YouTube watch / youtu.be / shorts URL with a `list` param → "https://www.youtube.com/playlist?list=<id>"; else None
  def video_details(info: dict, url: str) -> VideoDetails
  def list_sources(raw: str, *, extract_flat: Callable[..., dict], extract_full: Callable[..., dict], proxy: str | None, cookies_file: str | None) -> SourcesResult
  ```
  `video_details` rules: `url` = `info["webpage_url"]` when it is a non-empty string, else the pasted `url`. This matters: the job stores this URL and `run_download` does not set `noplaylist`, so storing a pasted `watch?v=X&list=Y` would download the whole playlist. `playlist_url = playlist_url_for(<pasted url>)`. `picker` from `normalize_formats` + `build_stream_picker_payload`; `best_short_side` from the normalized formats; `duration` coerced with `int()` when numeric (yt-dlp may give a float).
  `list_sources` rules:
  - No URLs → `ValueError("No URLs found.")` (route → 422 `no_urls`).
  - Each URL: `info = extract_flat(url, noplaylist=True, proxy=..., cookies_file=...)`. With `entries` → one `SourceEntry` per entry (`entry_url`, `title`, `uploader` or `channel`, `duration` as `int` or `None`, thumbnail = `thumbnail` or last `thumbnails[].url`); invalid entries become error entries ("Playlist entry N has no usable video URL."). Without `entries` → it's a video: if `info` has no `formats`, `info = extract_full(url, noplaylist=True, ...)`; becomes one entry with `details = video_details(info, url)` and `url = details.url`.
  - Exactly one URL that is a video → `kind="video"`, `video=details`, `entries=[]`, `title=None`, `skipped=0`.
  - Otherwise `kind="list"`, `title` = the playlist title when there was one URL, else `None`; entries deduped by URL across all sources (first wins), `index` 0..n-1 after dedupe, capped at `MAX_ENTRIES` with `skipped` = number dropped. Error entries without a URL are never deduped away.
  - One URL that fails → raise; the route maps it through `friendly_ytdlp_error` → 502 with that code and message. With several URLs a failing URL becomes an error entry (its `url` is the pasted URL) and the rest still load.
- `POST /api/sources` (`SourcesRequest`) → `SourcesResult`; proxy/cookies from `resolve_runtime_settings` only when the flags are set (as `info_form` does today). Calls `downloader.extract_flat_info` / `downloader.extract_info` through the module (e2e patch point).

- [ ] **Step 1: Write the failing tests**

```python
def test_single_video_returns_video_kind(): ...          # flat stub returns formats → kind "video", video.best_short_side == 1080, extract_full not called
def test_flat_without_formats_falls_back_to_full(): ...  # flat stub returns no formats → extract_full called once with noplaylist=True
def test_watch_with_list_opens_video(): ...              # url "https://www.youtube.com/watch?v=abc&list=PL1", stub info webpage_url "https://www.youtube.com/watch?v=abc"
                                                         # → stub called with noplaylist=True; video.url == "https://www.youtube.com/watch?v=abc";
                                                         #   video.playlist_url == "https://www.youtube.com/playlist?list=PL1"
def test_video_url_falls_back_to_pasted(): ...           # info without webpage_url → video.url == pasted url
def test_playlist_returns_all_entries_no_paging(): ...   # 120 entries → 120 entries, skipped 0, title == playlist title
def test_list_sources_dedupes_across_sources(): ...      # two playlists sharing one video → appears once
def test_list_sources_caps_at_500(): ...                 # 650 entries → 500 entries, skipped 150, last index 499
def test_float_duration_becomes_int(): ...               # entry duration 61.5 → 61
def test_multi_url_failure_becomes_error_entry(): ...    # second URL raises → entry with error_code, others fine
def test_playlist_url_for_ignores_non_youtube(): assert playlist_url_for("https://example.com/watch?v=1&list=2") is None
def test_extract_flat_info_passes_noplaylist(monkeypatch): ...  # capture ydl_opts → noplaylist True only when asked
# api
def test_sources_endpoint_single_failure_is_502(client, monkeypatch): ...  # error body code from friendly_ytdlp_error
def test_sources_endpoint_no_urls_422(client): assert post({"urls": "hello"}).json()["error"]["code"] == "no_urls"
```

- [ ] **Step 2:** run → FAIL. **Step 3:** implement. **Step 4:** `pnpm typegen && pnpm check` → PASS (old batch preview and enqueue intake tests still pass).
- [ ] **Step 5: Smoke against real yt-dlp** (network, not in CI): `cd apps/server && uv run python -c "from app.services import downloader; i = downloader.extract_flat_info('<a real video URL>', noplaylist=True); print(bool(i.get('formats')), i.get('webpage_url'))"`. Also try a `watch?v=X&list=Y` URL and confirm `webpage_url` has no `list`. Note the results in the commit message; either way the fallbacks keep it correct.
- [ ] **Step 6: Commit** `git add -A && git commit -m "feat(api): sources endpoint for single videos and lists"`

### Task 4.4: Fetch route and single-video screen

**Files:**

- Create: `apps/web/src/lib/{quality.ts,format-picker.ts}`, `apps/web/src/routes/{Fetch,VideoView}.svelte`, `apps/web/src/components/{QualitySelect,FormatPicker}.svelte`, `apps/web/e2e/video.spec.ts`
- Modify: `apps/web/src/App.svelte` (replace the `<h1>Fetch</h1>` placeholder with `Fetch`), `apps/server/tests/e2e_server.py`
- Test: `apps/web/test/{quality,format-picker}.test.ts`

**Interfaces:**

- `lib/quality.ts`: `type QualityCap = components["schemas"]["QualityCap"]`; `CAP_OPTIONS: { value: QualityCap; label: string }[]` = Best available, Up to 2160p, Up to 1440p, Up to 1080p, Up to 720p, Up to 480p, Audio only; `DEFAULT_CAP: QualityCap = "1080"`; `isBelowCap(cap, best: number | null): boolean` (same rule as the server).
- `lib/format-picker.ts`: `type Selection = { videoId: string | null; audioId: string | null }`; `toggle(sel, kind: "video" | "audio", id): Selection` (picking the selected id again clears it); `expectedContainer(picker: StreamPicker, sel): string` (key `${videoId ?? ""}|${audioId ?? ""}`, missing → "unknown"); `hasExact(sel): boolean`.
- `Fetch.svelte`: on `route.urls` change, `POST /api/sources` with `readFetchOptions()` (`use_proxy`, `use_cookies`), guarded by `latest()`; loading state "Fetching…"; error → `messageFor(err)` with a "Try again" button; `kind === "video"` → `VideoView`; `kind === "list"` → in this phase a short note "Playlists open in the classic UI for now." with a link to `/` (Phase 5 replaces it with `ListView`).
- `VideoView.svelte` (watch-page layout): left — large thumbnail, title as a heading, uploader, duration, Subtitles toggle, **Add to queue**; if `video.playlist_url` → "Part of a playlist · Open playlist" (link to `href({ name: "fetch", urls: playlist_url })`). Right — `QualitySelect` (a `<select>` labelled "Quality", default `DEFAULT_CAP`), then a Video / Audio / Advanced segmented control: Video and Audio tabs list `picker.video_streams` / `audio_streams` (resolution or bitrate, codec, ext; selected row marked red), expected container shown under the tabs; Advanced has output template and audio bitrate fields. When `hasExact(sel)`, the quality select shows "Exact format overrides this" and is dimmed. Add → `POST /api/downloads` with one job: `video.url` (the canonical URL, never the pasted one), title/uploader/duration/thumbnail, `quality_cap`, ids, subtitles, template, bitrate (blank strings → null). Success: "Added to queue." with a link to the Queue; error → `messageFor(err)` (e.g. the bad-template 422).
- e2e stubs in `e2e_server.py`: `extract_flat_info(url, *, proxy=None, cookies_file=None, noplaylist=False)` returns, for `https://e2e.test/video` and `https://e2e.test/watch?v=e2e&list=PLe2e`, a video info dict titled "E2E Video" with `webpage_url` `https://e2e.test/video` and formats 1920×1080 video `v1080`, 1280×720 `v720`, audio `a1`; other URLs keep calling `_not_stubbed`. `extract_info` gets the same signature. (`playlist_url_for` returns `None` for these non-YouTube URLs; the server tests cover the YouTube case.)

- [ ] **Step 1: Write the failing tests**

```ts
// quality.test.ts — tsconfig.node.json has no resolveJsonModule, so read the shared fixture from disk
import { readFileSync } from "node:fs";
const cases = JSON.parse(
  readFileSync(
    new URL("../../server/tests/fixtures/quality_cases.json", import.meta.url),
    "utf8",
  ),
) as {
  name: string;
  cap: QualityCap;
  best_short_side: number | null;
  below_cap: boolean;
}[];
for (const c of cases)
  it(c.name, () =>
    expect(isBelowCap(c.cap, c.best_short_side)).toBe(c.below_cap),
  );
// format-picker.test.ts
expect(toggle({ videoId: "137", audioId: null }, "video", "137")).toEqual({
  videoId: null,
  audioId: null,
});
expect(expectedContainer(picker, { videoId: "137", audioId: "140" })).toBe(
  "mp4",
);
expect(expectedContainer(picker, { videoId: "zzz", audioId: null })).toBe(
  "unknown",
);
```

```ts
// e2e/video.spec.ts
test("fetch single video and add to queue", async ({ page }) => {
  await page.goto(`${APP}#/`);
  await page
    .getByRole("textbox", { name: "Video or playlist URL" })
    .fill("https://e2e.test/video");
  await page.getByRole("button", { name: "Fetch", exact: true }).click();
  await expect(page.getByRole("heading", { name: "E2E Video" })).toBeVisible();
  await page.getByRole("combobox", { name: "Quality" }).selectOption("720");
  await page.getByRole("button", { name: "Add to queue" }).click();
  await expect(page.getByText("Added to queue.")).toBeVisible();
  await page.goto(`${APP}#/`);
  await expect(
    page.getByRole("article").filter({ hasText: "E2E Video" }),
  ).toBeVisible();
});
```

- [ ] **Step 2:** `pnpm test && pnpm e2e` → FAIL.
- [ ] **Step 3: Implement** (craft floor first; follow `DESIGN.md`).
- [ ] **Step 4:** `pnpm check && pnpm e2e` → PASS. With `pnpm dev`, fetch a real short video, add it at "Up to 480p", confirm the library shows 480p (or the short side for a vertical video). Also fetch a real `watch?v=X&list=Y` URL, add it, and confirm only one file downloads.
- [ ] **Step 5: Commit** `git add -A && git commit -m "feat(web): fetch and single-video screen with quality cap"`
