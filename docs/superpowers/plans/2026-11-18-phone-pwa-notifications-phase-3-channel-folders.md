# Phase 3: Channel and playlist folders Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Save downloads under `<channel>/<title>.<ext>` or `<playlist-owner>/<playlist>/<title>.<ext>` with ASCII slugs, and move the existing library into that layout once.

**Usable result:** New downloads land in channel and playlist folders. On the next start, the existing library moves into `<channel>/<title>.<ext>` once, and every file stays playable and deletable from the app.

**Architecture:** A pure `library_paths.py` holds the slug and path rules. The worker resolves info first, computes the path, then downloads with that fixed template (`run_download`'s two passes). Playlist name, owner and id travel from the sources response through `JobCreate` into new `downloads` columns. `library_layout.py` runs the one-off move in the lifespan, guarded by the `library_layout = v2` setting.

**Tech Stack:** FastAPI, SQLAlchemy + Alembic, yt-dlp, pytest, Svelte (playlist job fields only). New: `anyascii` 0.3.x.

**Spec:** `docs/superpowers/specs/2026-11-18-phone-pwa-notifications-design.md` (§2 Channel and playlist folders)

**Parent plan:** `docs/superpowers/plans/2026-11-18-phone-pwa-notifications.md`, Tasks 4, 5, 6. The tasks below are copied from it verbatim; the parent plan wins if they ever differ. Phase index: `docs/superpowers/plans/2026-11-18-phone-pwa-notifications-phases.md`.

**Prerequisites:** Phase 2 merged (Task 3 changed `run_download` and `build_ytdlp_options`; this phase builds on that signature).

## Global Constraints

- Run `pnpm check` (repo root) before every commit. Run `pnpm format` to fix formatting. After any API schema change, run `pnpm typegen` and commit `apps/web/src/lib/api.gen.ts`.
- Stack stays: FastAPI + yt-dlp + SQLite (Alembic) + worker threads; Svelte 5 + Vite + Tailwind 4; one process, one port. The Docker image ships everything.
- `DESIGN.md` is the visual contract. Red is the only accent. WCAG AA in both themes. Status is never shown by colour alone.
- Nothing loads from a CDN at runtime.
- Streams are copied and remuxed, never transcoded. No HDR output.
- Never silently download below the chosen cap (existing principle, unchanged).
- Never break or lose existing library files. A failed move leaves the file and its row as they were.
- A 500-video playlist must not send 500 pushes: jobs in a batch send no per-job push and no per-job toast.
- No login, no multi-user accounts. Tailscale is the access boundary. Never expose the app to the public internet.
- iOS: PWA install and Web Push need HTTPS and a home-screen install (iOS 16.4+). iOS has no Web Share Target.
- Phone layout is below 768 px. Touch targets are at least 44 px.
- Database changes go through a new Alembic revision. Never edit an existing revision.
- Follow the existing test layout: pytest `tests/unit`, `tests/api`, `tests/integration`; Vitest `apps/web/test`; Playwright `apps/web/e2e` (stubbed server `tests/e2e_server.py`).

## Review Focus

1. **The startup move meets a missing file, an existing target, a file outside the downloads folder, sidecars, or a crash halfway.** Missing and outside files are skipped. Collisions get a suffix. Sidecars move with the video. A rerun after a crash finishes the job without touching files that already moved. Task 6 owns the tests.
2. **Titles and channel names with `%`, `/`, `..`, emoji only, non-Latin script, or 300 characters.** The path stays inside the downloads folder. `%` never reaches yt-dlp as template syntax. Every segment is a non-empty ASCII slug of at most 80 characters. Tasks 4 and 5 own the tests.

---

### Task 4: Slug and path rules

**Files:**
- Create: `apps/server/app/services/library_paths.py`
- Modify: `apps/server/pyproject.toml` (`anyascii>=0.3.3`; run `uv add anyascii`)
- Test: `apps/server/tests/unit/test_library_paths.py`

**Interfaces:**
- Produces:
  - `SEGMENT_MAX = 80`
  - `slugify(text: str | None) -> str`: `anyascii`, lowercase, each run of non-`[a-z0-9]` becomes `-`, dashes trimmed, cut to 80 characters with trailing dashes trimmed again. Returns `""` when nothing is left.
  - `first_slug(*candidates: str | None, fallback: str) -> str`: the first non-empty slug, else `fallback`.
  - `@dataclass(frozen=True) class PlaylistFolder: title: str | None; channel: str | None; id: str | None`
  - `video_id_from_url(url: str) -> str | None`: `v=` query param, or the path of `youtu.be/<id>` / `/shorts/<id>`.
  - `default_stem(info: Mapping[str, Any], playlist: PlaylistFolder | None, downloads_dir: Path) -> Path`: an absolute path without extension.
    - channel = `first_slug(playlist.channel if playlist else None, info["channel"], info["uploader"], info["channel_id"], info["uploader_id"], fallback="unknown-channel")`
    - playlist segment (only when `playlist` is not None) = `first_slug(playlist.title, playlist.id, fallback="playlist")`
    - title = `first_slug(info["title"], info["id"], fallback="video")`
    - collision: if any file matches `glob.escape(str(stem)) + ".*"`, the title becomes `f"{title}-{slugify(info['id'])}"`.
    - Missing keys count as `None`.

- [ ] **Step 1: Write the failing tests**

```python
@pytest.mark.parametrize(("raw", "slug"), [
    ("Linus Tech Tips", "linus-tech-tips"),
    ("Café Déjà Vu!", "cafe-deja-vu"),
    ("Привет мир", "privet-mir"),
    ("東京", "dongjing"),
    ("100% real / fake ..", "100-real-fake"),
    ("!!!", ""),
    (None, ""),
])
def test_slugify(raw, slug): assert slugify(raw) == slug

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
    (tmp_path / "c").mkdir(); (tmp_path / "c" / "t.mp4").write_bytes(b"x")
    assert default_stem({"id": "Ab_1", "title": "t", "channel": "c"}, None, tmp_path).name == "t-ab-1"

def test_default_stem_stays_inside(tmp_path):
    info = {"id": "..", "title": "../../etc", "channel": ".."}
    stem = default_stem(info, None, tmp_path)
    assert stem.resolve().is_relative_to(tmp_path.resolve())

def test_video_id_from_url():
    assert video_id_from_url("https://www.youtube.com/watch?v=abc&list=x") == "abc"
    assert video_id_from_url("https://youtu.be/abc?t=1") == "abc"
    assert video_id_from_url("https://www.youtube.com/shorts/abc") == "abc"
    assert video_id_from_url("https://example.com/") is None
```

- [ ] **Step 2: Run them and see them fail**

Run: `cd apps/server && uv run pytest tests/unit/test_library_paths.py -v`
Expected: FAIL, module not found.

- [ ] **Step 3: Implement `library_paths.py`** to the interface above.

- [ ] **Step 4: Run the tests until they pass**, then run `pnpm check`.

- [ ] **Step 5: Commit** `feat(server): slug and default path rules for channel folders`

### Task 5: Downloads use the channel/playlist layout

**Files:**
- Create: `apps/server/alembic/versions/20261118120000_add_playlist_folder.py` (nullable `playlist_title`, `playlist_channel`, `playlist_id` on `downloads`)
- Modify: `apps/server/app/models.py`, `apps/server/app/schemas.py` (`DownloadCreate`, `SourcesResult`), `apps/server/app/services/queue.py` (`_row_from_payload`)
- Modify: `apps/server/app/services/sources.py` (`list_sources` fills `playlist_channel` = flat info `channel` then `uploader`, and `playlist_id` = flat info `id`, only when one URL is a playlist)
- Modify: `apps/server/app/services/downloader.py` (`run_download` gains `playlist`)
- Modify: `apps/server/app/services/job_runner.py`
- Modify: `apps/server/tests/e2e_server.py` (the stub keeps writing `<output_dir>/<last-url-part>.mp4`; it accepts the new kwarg)
- Modify: `apps/web/src/lib/playlist.ts` (`Header` gains `playlist: PlaylistFields | null`; `buildJobs` copies it onto each job), `apps/web/src/routes/ListView.svelte` (builds it from `result`), `apps/web/src/lib/api.gen.ts` (typegen)
- Modify: `README.md` (new "Library layout" section)
- Test: `tests/unit/test_downloader_layout.py`, `tests/unit/test_sources.py`, `tests/api/test_enqueue_api.py`, `tests/unit/test_job_runner.py`, `apps/web/test/playlist.test.ts`

**Interfaces:**
- Consumes: `PlaylistFolder`, `default_stem` (Task 4).
- Produces:
  - `DownloadCreate.playlist_title / playlist_channel / playlist_id: str | None = None` (so `JobCreate` has them too). Same nullable columns on `Download`.
  - `SourcesResult.playlist_channel: str | None`, `SourcesResult.playlist_id: str | None` (`None` for videos and multi-URL fetches, like `title`).
  - `run_download(..., playlist: PlaylistFolder | None = None)`. When `output_template` is empty, it runs two passes on one `YoutubeDL`:
    1. `info = ydl.extract_info(url, download=False, process=False)`
    2. `stem = default_stem(info, playlist, Path(output_dir))`, `stem.parent.mkdir(parents=True, exist_ok=True)`
    3. `ydl.params["outtmpl"]["default"] = str(stem).replace("%", "%%") + ".%(ext)s"`
    4. `info = ydl.process_ie_result(info, download=True)`

    A custom template keeps today's single `extract_info(url, download=True)`. The output guard stays on in both paths.
  - `job_runner` builds `PlaylistFolder(job.playlist_title, job.playlist_channel, job.playlist_id)` when any of the three is set, otherwise `None`.
  - Web: `type PlaylistFields = { playlist_title: string | null; playlist_channel: string | null; playlist_id: string | null }`.

- [ ] **Step 1: Write the failing downloader tests** in `tests/unit/test_downloader_layout.py`. Monkeypatch `yt_dlp.YoutubeDL.extract_info` to return a fake unprocessed info, and `process_ie_result` to record `ydl.params["outtmpl"]["default"]` and `ydl.prepare_filename(info)` and to call the progress hook with `{"status": "finished", "filename": prepare_filename}`.

```python
def test_default_layout_single(tmp_path, fake_ydl):
    fake_ydl.info = {"id": "abc", "title": "100% Real", "channel": "Chan", "ext": "mp4"}
    result = run_download("https://youtu.be/abc", output_dir=str(tmp_path), quality_cap="best")
    assert fake_ydl.outtmpl == str(tmp_path / "chan" / "100-real") + ".%(ext)s"
    assert result.path == str(tmp_path / "chan" / "100-real.mp4")

def test_default_layout_playlist(tmp_path, fake_ydl):
    fake_ydl.info = {"id": "abc", "title": "Ep", "channel": "Guest", "ext": "mp4"}
    run_download("u", output_dir=str(tmp_path), playlist=PlaylistFolder("Mix", "Owner", "PL1"))
    assert fake_ydl.outtmpl.startswith(str(tmp_path / "owner" / "mix" / "ep"))

def test_percent_in_downloads_dir_is_escaped(tmp_path, fake_ydl):
    root = tmp_path / "100%"
    fake_ydl.info = {"id": "abc", "title": "t", "channel": "c", "ext": "mp4"}
    result = run_download("u", output_dir=str(root))
    assert result.path == str(root / "c" / "t.mp4")

def test_custom_template_skips_layout(tmp_path, fake_ydl):
    run_download("u", output_dir=str(tmp_path), output_template="%(title)s.%(ext)s")
    assert fake_ydl.process_calls == 0
```

- [ ] **Step 2: Write the failing sources, API, runner and web tests**
  - `test_sources.py`: a single playlist URL whose flat info has `channel: "Owner"` and `id: "PL1"` returns `playlist_channel == "Owner"` and `playlist_id == "PL1"`. With `uploader` only, it falls back to the uploader. Two URLs give `None` for both.
  - `test_enqueue_api.py`: posting a job with the three playlist fields stores them on the row.
  - `test_job_runner.py`: a row with `playlist_title="Mix"` passes `playlist=PlaylistFolder("Mix", None, None)` to `run_download`. A row with none of the three passes `playlist=None`.
  - `playlist.test.ts`: `buildJobs(entries, { ...header, playlist: { playlist_title: "Mix", playlist_channel: "Owner", playlist_id: "PL1" } })` puts the three fields on every job. `playlist: null` gives `null` for all three.

- [ ] **Step 3: Run them and see them fail**

Run: `cd apps/server && uv run pytest tests/unit/test_downloader_layout.py tests/unit/test_sources.py tests/api/test_enqueue_api.py tests/unit/test_job_runner.py -q` and `pnpm vitest run apps/web/test/playlist.test.ts`
Expected: FAIL.

- [ ] **Step 4: Implement** the migration, model, schemas, sources, `run_download`, runner and web changes. Run `pnpm typegen`.

- [ ] **Step 5: Run the full checks**

Run: `pnpm check && pnpm e2e`
Expected: PASS.

- [ ] **Step 6: Write README "Library layout"**: `<channel>/<title>.<ext>` and `<playlist-owner>/<playlist>/<title>.<ext>`, the slug rule, the `-<video id>` collision suffix, and that a custom template overrides the layout.

- [ ] **Step 7: Commit** `feat: download into channel and playlist folders`

### Task 6: One-off move of existing files

**Files:**
- Create: `apps/server/app/services/library_layout.py`
- Modify: `apps/server/app/main.py` (lifespan: after `requeue_active_on_startup`, before workers start)
- Modify: `README.md` (one line under "Library layout")
- Test: `apps/server/tests/unit/test_library_layout.py`, `apps/server/tests/integration/test_startup_recovery.py`

**Interfaces:**
- Consumes: `slugify`, `first_slug`, `video_id_from_url` (Task 4).
- Produces:
  - `LAYOUT_KEY = "library_layout"`, `LAYOUT_VERSION = "v2"`
  - `@dataclass class LayoutSummary: moved: int = 0; skipped: int = 0; failed: int = 0`
  - `migrate_library_layout(session: Session, downloads_dir: Path) -> LayoutSummary | None`: returns `None` when the setting is already `v2`. Otherwise, for each `status == "done"` row with a `file_path`:
    - Skip (count `skipped`) when the file is missing, or not under `downloads_dir.resolve()`.
    - Target: `downloads_dir / first_slug(row.uploader, fallback="unknown-channel") / (first_slug(row.title, video_id_from_url(row.url), fallback=f"download-{row.id}") + suffix)`.
    - If the target is the current path, count it as `skipped`. If the target exists, append `-<video id or row id>` to the stem.
    - Move with `os.replace` after `mkdir(parents=True)`, together with sidecars in the same folder named `<old stem>.*` whose last suffix is `.srt`, `.vtt` or `.txt`. Update `row.file_path` and commit **per row**.
    - On `OSError`, log it, count `failed`, and leave the row as it was.
    - After the loop, `set_setting(session, LAYOUT_KEY, LAYOUT_VERSION)`, then log `library layout v2: moved=%d skipped=%d failed=%d`.
  - Old empty folders are left alone.

- [ ] **Step 1: Write the failing tests** (rows built with `db_session`, files in `tmp_path`):
  - `test_moves_file_and_sidecars`: `downloads/Old Name.mp4`, `Old Name.en.srt` and `Old Name.en.txt`, with uploader "Chan" and title "Old Name", end up in `downloads/chan/old-name.mp4` (plus `.en.srt` and `.en.txt`). `row.file_path` is updated. The summary is `(1, 0, 0)`.
  - `test_does_not_take_other_videos_sidecars`: `Foo.mp4` with a neighbouring `Foo.bar.mp4` (another row): only `Foo.mp4` moves with the first row.
  - `test_missing_and_outside_are_skipped`: a missing file, and a file under `tmp_path/elsewhere`, are both untouched and give `skipped == 2`.
  - `test_collision_gets_suffix`: two rows with the same uploader and title. The second becomes `title-<video id>.mp4`.
  - `test_failed_move_keeps_row`: monkeypatch `os.replace` to raise `OSError` for one row. That row keeps its `file_path`, and the others still move.
  - `test_runs_once`: a second call returns `None` and moves nothing.
  - `test_rerun_after_partial_move`: one row already points to its new path, the other doesn't, and the flag is unset. The second run moves only the second row and leaves the first in place (`skipped` counts it).
  - Integration: `test_startup_moves_library` boots the app with `TestClient(app)` and a seeded done row, then asserts the file moved and `library_layout == "v2"`.

- [ ] **Step 2: Run them and see them fail**

Run: `cd apps/server && uv run pytest tests/unit/test_library_layout.py tests/integration/test_startup_recovery.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement `library_layout.py` and call it from `lifespan`.** Wrap the call so that an unexpected exception is logged and startup continues.

- [ ] **Step 4: Run `pnpm check && pnpm e2e`** (the e2e seeded file moves to `e2e/seeded-video.mp4`; library download must still work). Expected: PASS.

- [ ] **Step 5: Commit** `feat(server): move existing library files into channel folders once`

---

## Done when

- Every task above is committed and `pnpm check && pnpm e2e` pass on the branch.
- The usable result above works by hand.
