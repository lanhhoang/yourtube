# Phase 2: MP4 downloads Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make capped video downloads (`best` and numeric caps) produce `.mp4`, preferring H.264 + AAC and never HDR.

**Usable result:** Queue any video with a numeric cap or `best` and get an `.mp4` that plays on Apple devices: H.264 + AAC up to 1080p where offered, VP9 SDR + AAC above.

**Architecture:** One change in `app/services/quality.py`: `cap_format_options` returns a `CapFormat` with a fixed sort tail and `merge_output_format="mp4"`. `downloader.py` threads the merge format through. Audio-only and exact format picks are untouched.

**Tech Stack:** yt-dlp 2026.10.26, pytest. No new dependencies.

**Spec:** `docs/superpowers/specs/2026-11-18-phone-pwa-notifications-design.md` (§1 Format selection, Appendix)

**Parent plan:** `docs/superpowers/plans/2026-11-18-phone-pwa-notifications.md`, Task 3. The tasks below are copied from it verbatim; the parent plan wins if they ever differ. Phase index: `docs/superpowers/plans/2026-11-18-phone-pwa-notifications-phases.md`.

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

1. 4K HDR uploads must pick SDR (the offline tests in Task 3 mirror the verified video). A cap below the best available must still never silently drop below the cap's rule (the existing `res:N` tests stay green).

---

### Task 3: MP4 sort for `best` and numeric caps

**Files:**
- Modify: `apps/server/app/services/quality.py` (`cap_format_options`, module docstring)
- Modify: `apps/server/app/services/downloader.py` (`build_ytdlp_options`, `run_download`)
- Modify: `apps/server/tests/unit/test_quality.py`, `apps/server/tests/fixtures/quality_cases.json` (only where cases assert sort output)
- Modify: `README.md` ("Quality caps")

**Interfaces:**
- Produces:
  - `class CapFormat(NamedTuple): format: str | None; format_sort: list[str] | None; merge_output_format: str | None`
  - `cap_format_options(cap: QualityCap | None, audio_bitrate: str | None = None) -> CapFormat`
  - `MP4_SORT = ["hdr:sdr", "vcodec:h264", "acodec:aac"]`
  - `build_ytdlp_options(..., merge_output_format: str | None = None)`: sets `options["merge_output_format"]` when given.
- `run_download` passes `merge_output_format` from `CapFormat`. Exact format ids keep the current path (`_format_selector`, no merge format).

- [ ] **Step 1: Rewrite `test_cap_format_options`**

```python
def test_cap_format_options() -> None:
    sort = ["hdr:sdr", "vcodec:h264", "acodec:aac"]
    assert cap_format_options(None) == ("bv*+ba/b", ["res", *sort], "mp4")
    assert cap_format_options("best") == ("bv*+ba/b", ["res", *sort], "mp4")
    assert cap_format_options("720") == ("bv*+ba/b", ["res:720", *sort], "mp4")
    assert cap_format_options("720", "192K") == ("bv*+ba/b", ["res:720", *sort, "abr:192"], "mp4")
    assert cap_format_options("audio") == ("ba/b", None, None)
    assert cap_format_options("audio", "128") == ("ba/b", ["abr:128"], None)
```

- [ ] **Step 2: Add offline selection tests** that use the existing `_select` helper (it unpacks `CapFormat`; update it to read `.format` and `.format_sort`). They mirror the verified 4K HDR video:

```python
HDR_SET = [
    _fmt("315", 3840, 2160, "vp9", "none", "webm"),
    _fmt("701", 3840, 2160, "av01.0.13M.10.0.110.09.16.09.0", "none", "mp4"),  # HDR
    _fmt("308", 2560, 1440, "vp9", "none", "webm"),
    _fmt("299", 1920, 1080, "avc1.64002a", "none", "mp4"),
    _fmt("303", 1920, 1080, "vp9", "none", "webm"),
    _fmt("140", None, None, "none", "mp4a.40.2", "m4a", 129),
    _fmt("251", None, None, "none", "opus", "webm", 133),
]
# give 701 "dynamic_range": "HDR10" and the others "SDR" in the helper data

def test_best_prefers_sdr_and_aac() -> None:
    assert _select(HDR_SET, "best") == "315+140"

def test_1440_takes_vp9_sdr() -> None:
    assert _select(HDR_SET, "1440") == "308+140"

def test_1080_prefers_h264() -> None:
    assert _select(HDR_SET, "1080") == "299+140"
```

- [ ] **Step 3: Run them and see them fail**

Run: `cd apps/server && uv run pytest tests/unit/test_quality.py -v`
Expected: FAIL. `best` still returns `(None, None)`, and the old picks are AV1/Opus.

- [ ] **Step 4: Implement `CapFormat` and the new rule** in `quality.py`. `None` and `best` use bare `res`, and numeric caps use `res:N`. Both append `MP4_SORT`, then `abr:K`. `audio` is unchanged. Update the module docstring with the verified picks from the spec appendix. Thread `merge_output_format` through `build_ytdlp_options` and `run_download`.

- [ ] **Step 5: Run the server suite**

Run: `cd apps/server && uv run pytest -q`
Expected: PASS. Fix `quality_cases.json` only where it asserts the old `(None, None)` for `best`.

- [ ] **Step 6: Update README "Quality caps"**: capped video is MP4 (H.264 + AAC up to 1080p where offered, VP9 SDR + AAC above). Audio-only and exact format picks are unchanged.

- [ ] **Step 7: `pnpm check`, then commit** `feat(server): capped downloads produce MP4 with H.264/AAC first and SDR only`

---

## Done when

- Every task above is committed and `pnpm check && pnpm e2e` pass on the branch.
- The usable result above works by hand.
