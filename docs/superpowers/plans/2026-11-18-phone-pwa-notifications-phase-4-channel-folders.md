# Phase 4: Channel and playlist folders Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Save downloads under `<channel>/<title>.<ext>` or `<playlist-owner>/<playlist>/<title>.<ext>` with ASCII slugs, and move the existing library into that layout once.

**Usable result:** New downloads land in channel and playlist folders. On the next start, the existing library moves into `<channel>/<title>.<ext>` once, and every file stays playable and deletable from the app.

**Architecture:** A pure `library_paths.py` holds the slug and path rules. The worker resolves info first, computes the path, then downloads with that fixed template (`run_download`'s two passes). Playlist name, owner and id travel from the sources response through `JobCreate` into new `downloads` columns. `library_layout.py` runs the one-off move in the lifespan, guarded by the `library_layout = v2` setting.

**Tech Stack:** FastAPI, SQLAlchemy + Alembic, yt-dlp, pytest, Svelte (playlist job fields only). New: `anyascii` 0.3.x.

**Spec:** `docs/superpowers/specs/2026-11-18-phone-pwa-notifications-design.md` (§2 Channel and playlist folders)

**Parent plan:** `docs/superpowers/plans/2026-11-18-phone-pwa-notifications.md`, Tasks 6, 7, 8. The tasks below are copied from it verbatim; the parent plan wins if they ever differ. Phase index: `docs/superpowers/plans/2026-11-18-phone-pwa-notifications-phases.md`.

**Prerequisites:** Phase 2 merged (Task 3 changed `run_download` and `build_ytdlp_options`; this phase builds on that signature). Phase 3 merged (its HDR revision is this phase's `down_revision`, and `run_download` already takes `hdr`).

**Revised 2026-11-18 after a readiness review** (parent plan updated to match):

- Pass 1 resolves info fully (`extract_info(url, download=False)`). With `process=False`, yt-dlp 2026.10.26 returns a bare `url` result with no `channel` for `watch?v=…&list=…` under `noplaylist`, and many non-YouTube extractors do the same.
- The existing `run_download` fakes in `test_downloader_progress.py` break on the two-pass call, so Task 7 now updates them.
- The web tests' `Header` and `SourcesResult` fixtures gain the new fields. Otherwise `pnpm typecheck` fails.
- The e2e stub seeded its row after the startup move had already run, so the seeded file never moved. Task 8 now seeds before the move, which Phase 5 relies on.
- The startup move now resolves relative `file_path` values (older rows) against the repo root. Rows that share one file move together. A crash between the move and the commit is recovered on the next run. Sidecars match `<stem>.<lang>.<ext>` only. The suffix check compares the final target.

## Global Constraints

- Run `pnpm check` (repo root) before every commit. Run `pnpm format` to fix formatting. After any API schema change, run `pnpm typegen` and commit `apps/web/src/lib/api.gen.ts`.
- Stack stays: FastAPI + yt-dlp + SQLite (Alembic) + worker threads; Svelte 5 + Vite + Tailwind 4; one process, one port. The Docker image ships everything.
- `DESIGN.md` is the visual contract. Red is the only accent. WCAG AA in both themes. Status is never shown by colour alone.
- Nothing loads from a CDN at runtime.
- Streams are copied and remuxed, never transcoded. No HDR output unless the job asks for HDR.
- Never silently download below the chosen cap (existing principle, unchanged).
- Never break or lose existing library files. A failed move leaves the file and its row as they were.
- A 500-video playlist must not send 500 pushes: jobs in a batch send no per-job push and no per-job toast.
- No login, no multi-user accounts. Tailscale is the access boundary. Never expose the app to the public internet.
- iOS: PWA install and Web Push need HTTPS and a home-screen install (iOS 16.4+). iOS has no Web Share Target.
- Phone layout is below 768 px. Touch targets are at least 44 px.
- Database changes go through a new Alembic revision. Never edit an existing revision.
- Follow the existing test layout: pytest `tests/unit`, `tests/api`, `tests/integration`; Vitest `apps/web/test`; Playwright `apps/web/e2e` (stubbed server `tests/e2e_server.py`).

## Review Focus

1. **The startup move meets a missing file, an existing target, a file outside the downloads folder, a relative `file_path`, two rows on one file, sidecars, or a crash halfway.** Missing and outside files are skipped. Collisions get a suffix. Sidecars move with their own video only. Relative paths resolve the way the library resolves them. A rerun after a crash, even one between `os.replace` and the commit, finishes the job without touching files that already moved. Task 8 owns the tests.
2. **Titles and channel names with `%`, `/`, `..`, emoji only, non-Latin script, or 300 characters.** The path stays inside the downloads folder. `%` never reaches yt-dlp as template syntax. Every segment is a non-empty ASCII slug of at most 80 characters. Tasks 6 and 7 own the tests.

---

### Task 6: Slug and path rules

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

### Task 7: Downloads use the channel/playlist layout

**Files:**

- Create: `apps/server/alembic/versions/20261118120000_add_playlist_folder.py` (`down_revision = "20261118110000"`, Phase 3's HDR revision; nullable `playlist_title`, `playlist_channel`, `playlist_id` on `downloads`)
- Modify: `apps/server/app/models.py`, `apps/server/app/schemas.py` (`DownloadCreate`, `SourcesResult`), `apps/server/app/services/queue.py` (`_row_from_payload`)
- Modify: `apps/server/app/services/sources.py` (`list_sources` fills `playlist_channel` = flat info `channel` then `uploader`, and `playlist_id` = flat info `id`, only when one URL is a playlist)
- Modify: `apps/server/app/services/downloader.py` (`run_download` gains `playlist`)
- Modify: `apps/server/app/services/job_runner.py`
- Modify: `apps/server/tests/unit/test_downloader_progress.py` (existing fakes follow the two-pass call; see Step 1)
- No change: `apps/server/tests/e2e_server.py`. Its `_run_download` stub already takes `**_kwargs` and keeps writing `<output_dir>/<last-url-part>.mp4`.
- Modify: `apps/web/src/lib/playlist.ts` (`Header` gains `playlist: PlaylistFields | null`; `buildJobs` copies it onto each job), `apps/web/src/routes/ListView.svelte` (`playlist` is `{ playlist_title: result.title, playlist_channel: result.playlist_channel, playlist_id: result.playlist_id }` when any of the three is non-null, else `null`), `apps/web/src/lib/api.gen.ts` (typegen)
- Modify: `README.md` (new "Library layout" section)
- Test: `tests/unit/test_downloader_layout.py`, `tests/unit/test_sources.py`, `tests/api/test_enqueue_api.py`, `tests/unit/test_job_runner.py`, `apps/web/test/playlist.test.ts`

**Interfaces:**

- Consumes: `PlaylistFolder`, `default_stem` (Task 6).
- Produces:
  - `DownloadCreate.playlist_title / playlist_channel / playlist_id: str | None = None` (so `JobCreate` has them too). Same nullable columns on `Download`.
  - `SourcesResult.playlist_channel: str | None`, `SourcesResult.playlist_id: str | None` (`None` for videos and multi-URL fetches, like `title`).
  - `run_download(..., playlist: PlaylistFolder | None = None)`. When `output_template` is empty, it runs two passes on one `YoutubeDL`:
    1. `info = ydl.extract_info(url, download=False)`. Fully resolved. Do not use `process=False`: it returns a bare `url` result without `channel` for some URLs. The `_real_download_through_guard` test helper and a live run (`watch?v=jNQXAC9IVRw&list=…`, `skip_download`) both confirm that `process_ie_result(info, download=True)` on this info downloads to the new template.
    2. `stem = default_stem(info, playlist, Path(output_dir))`, `stem.parent.mkdir(parents=True, exist_ok=True)`
    3. `ydl.params["outtmpl"]["default"] = str(stem).replace("%", "%%") + ".%(ext)s"`
    4. `info = ydl.process_ie_result(info, download=True)`

    A custom template keeps today's single `extract_info(url, download=True)`. The output guard stays on in both paths. Pass 1 also runs it, against the default `<root>/%(title)s.%(ext)s`, which is inside the root. Read missing info keys as `None` (`info.get`); the existing fakes return `{}`.

  - `job_runner` builds `PlaylistFolder(job.playlist_title, job.playlist_channel, job.playlist_id)` when any of the three is set, otherwise `None`.
  - Web: `type PlaylistFields = { playlist_title: string | null; playlist_channel: string | null; playlist_id: string | null }`.

- [ ] **Step 1: Write the failing downloader tests** in `tests/unit/test_downloader_layout.py`. Monkeypatch `yt_dlp.YoutubeDL.extract_info` to return the fake info (for `download=False`). Monkeypatch `process_ie_result` to record `ydl.params["outtmpl"]["default"]` and `ydl.prepare_filename(info)`, and to call the progress hook with `{"status": "finished", "filename": prepare_filename}`. For the custom-template test, `extract_info(download=True)` returns the info and `process_ie_result` counts calls.

  Then update the existing fakes in `tests/unit/test_downloader_progress.py`. The seven `MagicMock` factories (lines ~71–290) and `_captured_opts` currently do their hook-and-return work in `extract_info(url, download)`, and some assert `download is True`. Move that work to whichever call downloads:
  - `process_ie_result(info, download=True)` in the default layout. Set `fake_ydl.process_ie_result.side_effect`.
  - `extract_info(url, download=True)` when a custom template is set.

  `extract_info(url, download=False)` returns `{"id": "v", "title": "t", "channel": "c"}`. Keep the `result.path` assertions as they are; they come from the hook or `requested_downloads`. `_real_download_through_guard` needs no change, because its `extract_info` already calls the real `process_ie_result`.

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
  - `playlist.test.ts`: `buildJobs(entries, { ...header, playlist: { playlist_title: "Mix", playlist_channel: "Owner", playlist_id: "PL1" } })` puts the three fields on every job. `playlist: null` gives `null` for all three. Update the existing fixtures so `tsc -p tsconfig.node.json` passes: the shared `header` gains `playlist: null`, and the two `SourcesResult` literals in the `initialEntries` tests gain `playlist_channel: null, playlist_id: null`.

- [ ] **Step 3: Run them and see them fail**

Run: `cd apps/server && uv run pytest tests/unit/test_downloader_layout.py tests/unit/test_downloader_progress.py tests/unit/test_sources.py tests/api/test_enqueue_api.py tests/unit/test_job_runner.py -q` and `pnpm vitest run apps/web/test/playlist.test.ts`
Expected: FAIL.

- [ ] **Step 4: Implement** the migration, model, schemas, sources, `run_download`, runner and web changes. Run `pnpm typegen`.

- [ ] **Step 5: Run the full checks**

Run: `pnpm check && pnpm e2e`
Expected: PASS.

- [ ] **Step 6: Write README "Library layout"**: `<channel>/<title>.<ext>` and `<playlist-owner>/<playlist>/<title>.<ext>`, the slug rule, the `-<video id>` collision suffix, and that a custom template overrides the layout.

- [ ] **Step 7: Commit** `feat: download into channel and playlist folders`

### Task 8: One-off move of existing files

**Files:**

- Create: `apps/server/app/services/library_layout.py`
- Modify: `apps/server/app/main.py` (lifespan: after `requeue_active_on_startup`, before workers start; `from app.services.library_layout import migrate_library_layout` so the e2e stub can wrap `app.main.migrate_library_layout`)
- Modify: `apps/server/tests/e2e_server.py`. Today `_seed()` runs after the whole lifespan, after the move and after workers start, so the seeded file would never move. Wrap `app.main.migrate_library_layout` so it calls `_seed()` first, then the real function. Remove the post-lifespan `_seed()` wrapper. The seeded row keeps `uploader="E2E"`, `title="Seeded video"` and file `seeded.mp4`, so it lands at `e2e/seeded-video.mp4`. Phase 5 assumes this path.
- Modify: `README.md` (one line under "Library layout")
- Test: `apps/server/tests/unit/test_library_layout.py`, `apps/server/tests/integration/test_startup_recovery.py`

**Interfaces:**

- Consumes: `slugify`, `first_slug`, `video_id_from_url` (Task 6).
- Produces:
  - `LAYOUT_KEY = "library_layout"`, `LAYOUT_VERSION = "v2"`
  - `@dataclass class LayoutSummary: moved: int = 0; skipped: int = 0; failed: int = 0`
  - `migrate_library_layout(session: Session, downloads_dir: Path) -> LayoutSummary | None`: returns `None` when the setting is already `v2` (`get_setting` returns `None` for this non-catalog key until it is set). Otherwise, take every `status == "done"` row with a `file_path` (ordered by `id`) and **group the rows by resolved path**, `resolve_repo_path(file_path).resolve()`, the same resolution the library uses. Older rows store paths relative to the repo root, and a re-download can leave two rows on one file. Each group is one unit; summary counts are per group. Use the lowest row id in the group for the target.
    - Skip (count `skipped`) when the path is not under `downloads_dir.resolve()`.
    - Target: `downloads_dir / first_slug(row.uploader, fallback="unknown-channel") / (first_slug(row.title, video_id_from_url(row.url), fallback=f"download-{row.id}") + suffix)`. The alternative is the same path with `-<video id or row id>` appended to the stem.
    - **Missing source (crash recovery):** `os.replace` can succeed and then the process can die before the commit. If the source is missing, but the target or the alternative exists and no other done row points to it, point the group's rows at it, commit, and count `moved`. Otherwise count `skipped`.
    - If the current path equals the target or the alternative, count `skipped`. This covers reruns, including rows that got the suffix on the first run. If the target, or any of its sidecar targets, exists, use the alternative. If that is taken too, log it and count `skipped`.
    - Sidecars: files in the same folder named `<old stem>.<ext>` or `<old stem>.<lang>.<ext>`, where `<ext>` is `srt`, `vtt` or `txt` and `<lang>` has no dot. Leave out any file whose name starts with another done row's stem plus `.`. Example: `Foo.bar.en.srt` belongs to `Foo.bar.mp4`, not to `Foo.mp4`.
    - Move the video, then its sidecars, with `os.replace` after `mkdir(parents=True, exist_ok=True)`. Set every row in the group to the new absolute path, and commit **per group**.
    - On `OSError`, log it, count `failed`, and leave the rows as they were. If the video moved but a sidecar failed, the video's rows still update; log the sidecar.
    - After the loop, `set_setting(session, LAYOUT_KEY, LAYOUT_VERSION)`, then log `library layout v2: moved=%d skipped=%d failed=%d`.
  - Old empty folders are left alone.

- [ ] **Step 1: Write the failing tests** (rows built with `db_session`, files in `tmp_path`):
  - `test_moves_file_and_sidecars`: `downloads/Old Name.mp4`, `Old Name.en.srt` and `Old Name.en.txt`, with uploader "Chan" and title "Old Name", end up in `downloads/chan/old-name.mp4` (plus `.en.srt` and `.en.txt`). `row.file_path` is updated. The summary is `(1, 0, 0)`.
  - `test_does_not_take_other_videos_sidecars`: `Foo.mp4` sits next to `Foo.bar.mp4` and `Foo.bar.en.srt`, which belong to another row. Only `Foo.mp4` moves with the first row; `Foo.bar.en.srt` moves with `Foo.bar.mp4`.
  - `test_relative_file_path_is_resolved`: monkeypatch `app.config.REPO_ROOT` to `tmp_path`. A row with `file_path="downloads/Old.mp4"` and `downloads_dir = tmp_path / "downloads"` moves, and gets an absolute `file_path`.
  - `test_rows_sharing_a_file_move_together`: two done rows point to the same file. After the run, both point to the one new path, and the summary is `(1, 0, 0)`.
  - `test_recovers_move_without_commit`: the file already sits at its target, the row still has the old path, and the flag is unset. The run points the row at the target and counts `moved`.
  - `test_missing_and_outside_are_skipped`: a missing file, and a file under `tmp_path/elsewhere`, are both untouched and give `skipped == 2`.
  - `test_collision_gets_suffix`: two rows with the same uploader and title. The second becomes `title-<video id>.mp4`.
  - `test_failed_move_keeps_row`: monkeypatch `os.replace` to raise `OSError` for one row. That row keeps its `file_path`, and the others still move.
  - `test_runs_once`: a second call returns `None` and moves nothing.
  - `test_rerun_after_partial_move`: one row already points to its new path, the other doesn't, and the flag is unset. The second run moves only the second row and leaves the first in place (`skipped` counts it).
  - Integration: `test_startup_moves_library` uses `db_session_visible`. It sets `downloads_dir` to `tmp_path` with `set_settings_batch`, seeds a done row with a file in `tmp_path`, boots the app with `TestClient(app)`, then asserts the file moved and `library_layout == "v2"`. Every `client` fixture runs the move too. That is harmless, because the fixture boots before the test adds its rows, and `db_session_visible` deletes the settings rows afterwards.

- [ ] **Step 2: Run them and see them fail**

Run: `cd apps/server && uv run pytest tests/unit/test_library_layout.py tests/integration/test_startup_recovery.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement `library_layout.py` and call it from `lifespan`.** Wrap the call so that an unexpected exception is logged and startup continues.

- [ ] **Step 4: Update `tests/e2e_server.py`** (seed inside the wrapped `migrate_library_layout`, see Files). Then run `pnpm check && pnpm e2e`. The e2e seeded file moves to `tmp/e2e/downloads/e2e/seeded-video.mp4`, and library delete must still work. Expected: PASS.

- [ ] **Step 5: Commit** `feat(server): move existing library files into channel folders once`

---

## Done when

- Every task above is committed and `pnpm check && pnpm e2e` pass on the branch.
- The usable result above works by hand.
