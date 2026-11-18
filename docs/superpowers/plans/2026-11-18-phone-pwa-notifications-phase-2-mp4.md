# Phase 2: MP4 downloads Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make capped video downloads (`best` and numeric caps) produce `.mp4`, preferring H.264 + AAC and never HDR, and make the library point at the merged file.

**Usable result:** Queue any video with a numeric cap or `best` and get an `.mp4` that plays on Apple devices: H.264 + AAC up to 1080p where offered, VP9 SDR + AAC above. The library row's file link opens that `.mp4`.

**Architecture:** Two server changes. (A) `run_download` takes the final path from yt-dlp's `requested_downloads` instead of the last `finished` progress event, which today is a deleted part file (`<title>.f140.m4a`) whenever streams are merged. (B) `cap_format_options` in `app/services/quality.py` returns a `CapFormat` with a fixed sort tail and `merge_output_format="mp4"`; `downloader.py` threads the merge format through. Audio-only and exact format picks are untouched.

**Tech Stack:** yt-dlp 2026.10.26, pytest. No new dependencies.

**Spec:** `docs/superpowers/specs/2026-11-18-phone-pwa-notifications-design.md` (§1 Format selection, Appendix)

**Parent plan:** `docs/superpowers/plans/2026-11-18-phone-pwa-notifications.md`, Task 3. The task below is copied from it verbatim (both were revised together on 2026-11-18 after the path bug was found); the parent plan wins if they ever differ. Phase index: `docs/superpowers/plans/2026-11-18-phone-pwa-notifications-phases.md`.

**Prerequisites:** Phase 1 is not required. This phase only touches the server.

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

1. 4K HDR uploads must pick SDR. `test_hdr_vp9_loses_to_sdr_av1` is the test that fails without `hdr:sdr`; the HDR_SET picks hold either way. A cap below the best available must still never silently drop below the cap's rule (the existing `res:N` tests stay green).
2. A merged download's `file_path` is the merged `.mp4` that exists on disk, never a `.fNNN.*` part file.

## Verified facts this plan relies on (2026-11-18)

- **Path bug (exists today):** `run_download` keeps the last `status == "finished"` hook filename. On a merge, yt-dlp fires that hook once per stream (`<title>.f160.mp4`, then `<title>.f140.m4a`) and deletes both after merging. Running `run_download(url="https://www.youtube.com/watch?v=jNQXAC9IVRw", quality_cap="480")` in the `yourtube` Docker image returned `path='/out/Me at the zoo.f251.webm'`, but only `Me at the zoo.webm` was on disk. `info["requested_downloads"][0]["filepath"]` holds the real final path (checked with `LXb3EKWsInQ`, `bv+ba`, merge `mp4`: hook gave the two part files, `requested_downloads` gave `<title>.mp4`). For a single muxed stream (format 18) the hook and `requested_downloads` agree.
- **Offline picks** (installed yt-dlp, `format="bv*+ba/b"`, sort `[res…, hdr:sdr, vcodec:h264, acodec:aac]`): HDR_SET below gives best → `315+140`, 1440 → `308+140`, 1080 → `299+140`, all with `ext == "mp4"` when `merge_output_format="mp4"` (without it, best/1440 merge to `mkv`). The current code picks best → `701+251`, 1080 → `303+251`, 1440 → `308+251`, so the new tests fail first.
- **`hdr:sdr` is load-bearing** only when the HDR stream would otherwise win, e.g. VP9.2 HDR `337` vs AV1 SDR `401` at 2160p: with `hdr:sdr` → `401+140`; without → `337+140`.
- The existing offline tests (vertical 1080, fall back above, `abr:128`) still pass with the new sort tail.
- `quality_cases.json` never asserts sort output (it covers `best_short_side`/`is_below_cap` and is shared with `apps/web/test/quality.test.ts`). It does not change.

---

### Task 3: MP4 sort for `best` and numeric caps

**Files:**

- Modify: `apps/server/app/services/downloader.py` (`build_ytdlp_options`, `run_download`)
- Modify: `apps/server/app/services/quality.py` (`cap_format_options`, module docstring)
- Modify: `apps/server/tests/unit/test_quality.py`
- Modify: `apps/server/tests/unit/test_downloader_progress.py` (`_captured_opts` and the cap tests)
- Modify: `README.md` ("Quality caps")

**Interfaces:**

- Produces:
  - `class CapFormat(NamedTuple): format: str | None; format_sort: list[str] | None; merge_output_format: str | None`
  - `cap_format_options(cap: QualityCap | None, audio_bitrate: str | None = None) -> CapFormat`
  - `MP4_SORT = ["hdr:sdr", "vcodec:h264", "acodec:aac"]`
  - `build_ytdlp_options(..., merge_output_format: str | None = None)`: sets `options["merge_output_format"]` when given.
  - `run_download` result `path`: the last `requested_downloads[*].filepath` from the returned info, falling back to the last `finished` hook filename when `requested_downloads` is missing or has no `filepath`. (Phase 3's fake `YoutubeDL` reports the path only through the hook, so the fallback must stay.)
- `run_download` passes `merge_output_format` from `CapFormat`. Exact format ids keep the current path (`_format_selector`, no merge format, no sort).

#### Part A: record the merged file's path

- [ ] **Step 1: Write the failing path tests** in `tests/unit/test_downloader_progress.py`. Extend `_captured_opts` so a test can set the fake info and hook calls. Simplest shape: give it `info: dict | None = None` and `hook_files: list[str] = ()` kwargs. The factory returns `info` from `extract_info` (default `{"ext": "mp4", "height": 720}`). Before returning, it calls each `opts["progress_hooks"][0]({"status": "finished", "filename": f})`. Return `(opts, result)` or stash the result. Keep existing callers working.

```python
def test_run_download_path_is_merged_file(monkeypatch, tmp_path: Path) -> None:
    merged = tmp_path / "t.mp4"
    merged.write_bytes(b"x" * 10)
    _, result = _captured_opts(
        monkeypatch, tmp_path,
        info={"ext": "mp4", "requested_downloads": [{"filepath": str(merged)}]},
        hook_files=[str(tmp_path / "t.f299.mp4"), str(tmp_path / "t.f140.m4a")],
    )
    assert result.path == str(merged)
    assert result.file_size == 10


def test_run_download_path_falls_back_to_hook(monkeypatch, tmp_path: Path) -> None:
    _, result = _captured_opts(
        monkeypatch, tmp_path, info={"ext": "mp4"}, hook_files=[str(tmp_path / "t.mp4")]
    )
    assert result.path == str(tmp_path / "t.mp4")
```

- [ ] **Step 2: Run them and see the first fail**

Run: `cd apps/server && uv run pytest tests/unit/test_downloader_progress.py -v`
Expected: `test_run_download_path_is_merged_file` FAILS (path is `t.f140.m4a`). The fallback test passes.

- [ ] **Step 3: Implement.** After `extract_info` in `run_download`:

```python
requested = (info or {}).get("requested_downloads") or []
final = next((d["filepath"] for d in reversed(requested) if d.get("filepath")), None)
output_path = final or captured_path["path"] or ""
```

Keep the hook capture for the fallback.

- [ ] **Step 4: `uv run pytest -q`, `pnpm check`, then commit** `fix(server): record the merged file, not the last part file`

#### Part B: MP4 sort

- [ ] **Step 5: Rewrite `test_cap_format_options`** and fix the free-form bitrate assert. `None` now behaves like `best`, so the old `cap_format_options(None, "128k") == (None, ["abr:128"])` line goes away. The `"192 kbps"` tolerance test becomes `== ("bv*+ba/b", ["res", *MP4_SORT], "mp4")`, which still proves it doesn't crash and the bad bitrate is ignored:

```python
def test_cap_format_options() -> None:
    sort = ["hdr:sdr", "vcodec:h264", "acodec:aac"]
    assert cap_format_options(None) == ("bv*+ba/b", ["res", *sort], "mp4")
    assert cap_format_options("best") == ("bv*+ba/b", ["res", *sort], "mp4")
    assert cap_format_options("720") == ("bv*+ba/b", ["res:720", *sort], "mp4")
    assert cap_format_options("720", "192K") == ("bv*+ba/b", ["res:720", *sort, "abr:192"], "mp4")
    assert cap_format_options("best", "128k") == ("bv*+ba/b", ["res", *sort, "abr:128"], "mp4")
    assert cap_format_options("audio") == ("ba/b", None, None)
    assert cap_format_options("audio", "128") == ("ba/b", ["abr:128"], None)
```

- [ ] **Step 6: Add offline selection tests.** Give `_fmt` a keyword `dr: str | None = None` that sets `"dynamic_range"` when given. Change `_select` to read `.format`, `.format_sort` and `.merge_output_format` from `CapFormat` (set `merge_output_format` in opts when present) and return `(format_id, ext)`. Update the three existing `_select` asserts to compare `[0]`, or add a small `_pick` wrapper. These sets mirror the verified 4K HDR video:

```python
HDR_SET = [
    _fmt("315", 3840, 2160, "vp9", "none", "webm", dr="SDR"),
    _fmt("701", 3840, 2160, "av01.0.13M.10.0.110.09.16.09.0", "none", "mp4", dr="HDR10"),
    _fmt("308", 2560, 1440, "vp9", "none", "webm", dr="SDR"),
    _fmt("299", 1920, 1080, "avc1.64002a", "none", "mp4", dr="SDR"),
    _fmt("303", 1920, 1080, "vp9", "none", "webm", dr="SDR"),
    _fmt("140", None, None, "none", "mp4a.40.2", "m4a", 129),
    _fmt("251", None, None, "none", "opus", "webm", 133),
]

def test_best_prefers_sdr_and_aac() -> None:
    assert _select(HDR_SET, "best") == ("315+140", "mp4")

def test_1440_takes_vp9_sdr() -> None:
    assert _select(HDR_SET, "1440") == ("308+140", "mp4")

def test_1080_prefers_h264() -> None:
    assert _select(HDR_SET, "1080") == ("299+140", "mp4")

def test_hdr_vp9_loses_to_sdr_av1() -> None:
    formats = [
        _fmt("337", 3840, 2160, "vp09.02.51.10.01.09.16.09.00", "none", "webm", dr="HDR10"),
        _fmt("401", 3840, 2160, "av01.0.12M.08", "none", "mp4", dr="SDR"),
        _fmt("140", None, None, "none", "mp4a.40.2", "m4a", 129),
    ]
    assert _select(formats, "best")[0] == "401+140"
```

- [ ] **Step 7: Update the `run_download` option tests** in `test_downloader_progress.py`:
  - `test_run_download_uses_cap`: `format_sort == ["res:720", "hdr:sdr", "vcodec:h264", "acodec:aac"]`, `merge_output_format == "mp4"`.
  - Replace `test_run_download_no_cap_no_bitrate_unchanged` with `test_run_download_no_cap_is_best`: `format == "bv*+ba/b"`, `format_sort == ["res", "hdr:sdr", "vcodec:h264", "acodec:aac"]`, `merge_output_format == "mp4"`.
  - `test_run_download_exact_ids_win`: also assert `"merge_output_format" not in opts`.
  - Add `test_run_download_audio_cap_no_merge`: `quality_cap="audio"` gives `format == "ba/b"` and no `merge_output_format`.

- [ ] **Step 8: Run them and see them fail**

Run: `cd apps/server && uv run pytest tests/unit/test_quality.py tests/unit/test_downloader_progress.py -v`
Expected: FAIL. `best` still returns `(None, None)`, and the old picks are AV1/VP9 + Opus (`701+251`, `303+251`, `308+251`).

- [ ] **Step 9: Implement `CapFormat` and the new rule** in `quality.py`. `None` and `best` use bare `res`, and numeric caps use `res:N`. Both append `MP4_SORT`, then `abr:K`. `audio` is unchanged except it now returns `CapFormat("ba/b", abr or None, None)`. In `run_download`, unpack `CapFormat` and pass `merge_output_format` to `build_ytdlp_options`. The exact-ids branch passes `None`.

- [ ] **Step 10: Update the `quality.py` module docstring.** Video caps (and `None`/`best`) use `format="bv*+ba/b"` and `format_sort=[res[:N], hdr:sdr, vcodec:h264, acodec:aac, abr:K?]` with `merge_output_format="mp4"`. Explain why `hdr:sdr` is explicit (HDR VP9.2 beats SDR AV1 without it). Add the verified picks from the spec appendix: best → 315+140, 1440 → 308+140, 1080 → 299+140. Keep the existing `res`/`abr` notes.

- [ ] **Step 11: Run the server suite**

Run: `cd apps/server && uv run pytest -q`
Expected: PASS.

- [ ] **Step 12: Update README "Quality caps"**: capped video is MP4 (H.264 + AAC up to 1080p where offered, VP9 SDR + AAC above, never HDR). Audio-only and exact format picks are unchanged.

- [ ] **Step 13: `pnpm check`, then commit** `feat(server): capped downloads produce MP4 with H.264/AAC first and SDR only`

- [ ] **Step 14: Check by hand in Docker** (ffmpeg is only in the image; local macOS has none):

```bash
docker build -t yourtube . && mkdir -p /tmp/ytcheck && rm -rf /tmp/ytcheck/*
docker run --rm -v /tmp/ytcheck:/out --entrypoint sh yourtube -c 'cd /app/apps/server && python -c "
from app.services.downloader import run_download
print(run_download(url=\"https://www.youtube.com/watch?v=LXb3EKWsInQ\", output_dir=\"/out\", quality_cap=\"480\"))
" && ls /out && ffprobe -v error -show_entries stream=codec_name -of csv=p=0 /out/*.mp4'
```

Expected: `path` ends in `.mp4` with no `.fNNN`, and `ls` shows that same file. ffprobe prints `h264` and `aac`.

---

## Done when

- Every step above is committed and `pnpm check && pnpm e2e` pass on the branch.
- Step 14 shows a merged `.mp4` whose path matches the file on disk.
