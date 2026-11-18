# MP4 Downloads, Channel Folders, Phone PWA and Notifications Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Capped downloads land as MP4 in `<channel>/<playlist>/<title>.mp4` folders, and YourTube installs on the iPhone as a PWA with a phone layout, a player, and push notifications for finished, failed and playlist downloads.

**Architecture:** Server changes stay in the existing service modules. `quality.py` gains the MP4 sort and the opt-in HDR sort. A new `library_paths.py` holds the slug and path rules, and a new `library_layout.py` holds the one-off move. A new `push.py` handles VAPID and sending; the worker calls it after `release_job`. The web app gains `vite-plugin-pwa` (injectManifest with a custom `src/sw.ts`), a `#/watch/<id>` route, a phone layout below 768 px, and push/toast helpers in `src/lib`. Work ships in seven phases, simplest first. Each phase is usable on its own (see the phase index).

**Tech Stack:** FastAPI, yt-dlp 2026.10.26, SQLAlchemy + Alembic (SQLite), Python 3.12 via `uv`, pytest. Svelte 5 runes, Vite 8, Tailwind 4, openapi-fetch, Vitest, Playwright. New: `anyascii` 0.3.x (transliteration), `pywebpush` 2.5.x (pulls `py-vapid`), `vite-plugin-pwa` ^2.0.0 with `workbox-precaching` / `workbox-routing` ^7.4. Icons are generated once with `pnpm dlx @vite-pwa/assets-generator`, which is not a dependency.

**Spec:** `docs/superpowers/specs/2026-11-18-phone-pwa-notifications-design.md`, plus `docs/superpowers/specs/2026-11-18-hdr-option-design.md` (Phase 3)

**Phase index:** `docs/superpowers/plans/2026-11-18-phone-pwa-notifications-phases.md`

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

1. **The last two jobs of a batch finish at the same moment on two workers.** Exactly one summary push must go out, never zero and never two. Task 18 owns the test.
2. **The startup move meets a missing file, an existing target, a file outside the downloads folder, sidecars, or a crash halfway.** Missing and outside files are skipped. Collisions get a suffix. Sidecars move with the video. A rerun after a crash finishes the job without touching files that already moved. Task 8 owns the tests.
3. **Titles and channel names with `%`, `/`, `..`, emoji only, non-Latin script, or 300 characters.** The path stays inside the downloads folder. `%` never reaches yt-dlp as template syntax. Every segment is a non-empty ASCII slug of at most 80 characters. Tasks 6 and 7 own the tests.
4. **A push endpoint is dead (`410`), slow, or unreachable.** The job still ends `done`/`error`. The worker moves on within the timeout. A dead subscription is deleted. Task 20 owns the test.
5. **iPhone playback of a large file.** The file endpoint answers `Range` requests with `206`. Save uses the share sheet only for files of 500 MB or less, and the download link above that. Task 10 owns the tests.

---

## File Structure

```
apps/server/
  pyproject.toml                         (modify: anyascii, pywebpush)
  package.json                           (modify: dev/start run `python -m app`)
  app/__main__.py                        uvicorn entry that honours YT_HOST / YT_PORT
  app/config.py                          (modify: vapid_* settings)
  app/models.py                          (modify: playlist_*, batch_*, PushSubscription)
  app/schemas.py                         (modify: JobCreate/JobOut/SourcesResult/QueueOut, push schemas)
  app/services/quality.py                (modify: CapFormat, MP4 sort, hdr)
  app/services/downloader.py             (modify: merge_output_format, default layout)
  app/services/library_paths.py          slugify, PlaylistFolder, default_stem, video_id_from_url
  app/services/library_layout.py         migrate_library_layout (one-off move)
  app/services/sources.py                (modify: playlist_channel, playlist_id)
  app/services/queue.py                  (modify: batch_id, retry clears it, batch summary/claim)
  app/services/job_runner.py             (modify: PlaylistFolder, notify after release)
  app/services/push.py                   VAPID keys, subscriptions, messages, sending
  app/api/jobs.py                        (modify: GET /downloads/{id}, ?inline, cancel notifies)
  app/api/push.py                        /api/push/key, /api/push/subscriptions
  app/main.py                            (modify: run the move in lifespan)
  alembic/versions/20261118110000_add_hdr.py
  alembic/versions/20261118120000_add_playlist_folder.py
  alembic/versions/20261118130000_add_batches_and_push.py
  tests/... (new tests named in each task)
apps/web/
  package.json                           (modify: vite-plugin-pwa, workbox-*)
  vite.config.ts                         (modify: VitePWA, host from YT_HOST)
  index.html                             (modify: viewport-fit, theme-color, Apple meta)
  public/favicon.svg (replace: new play-circle), icon.svg, pwa-*.png, maskable-icon-512x512.png, apple-touch-icon-180x180.png, favicon.ico
  src/sw.ts                              precache, navigation fallback, push, notificationclick
  src/lib/theme.ts                       (modify: nextTheme, themeLabel)
  src/lib/theme-state.svelte.ts          shared theme choice
  src/lib/router.ts                      (modify: watch route)
  src/lib/share.ts                       sharedUrl()
  src/lib/save.ts                        saveMode(), SHARE_LIMIT_BYTES
  src/lib/push.ts                        pushSupport(), subscribe/unsubscribe helpers
  src/lib/toasts.ts                      (modify: newEvents with kinds)
  src/lib/playlist.ts                    (modify: playlist fields on jobs)
  src/components/LogoMark.svelte         red player mark (top bar)
  src/components/ThemeToggle.svelte      rail tile button
  src/components/TabBar.svelte           phone bottom tab bar
  src/components/BottomSheet.svelte      phone override panel container
  src/components/Toasts.svelte           (modify: variants, phone position)
  src/routes/Watch.svelte                player + Save + Delete
  test/*.test.ts, e2e/*.spec.ts          (new tests named in each task)
docs: README.md, PRODUCT.md, DESIGN.md, .env.example
```

---

## Phase 1: Shell

### Task 1: Logo mark in the top bar, new favicon

The owner supplied two new marks (2026-11-18). Their cleaned markup is below, so you don't need the gitignored originals in `tmp/`.
- **Top-bar mark:** a red rounded screen with a white play triangle and a pale scrub bar. It's wide, about 1.44:1. Source: `tmp/icon.svg`.
- **Favicon:** a two-tone red play-circle with a white triangle. Source: `tmp/favicon.svg`. It replaces the old SVG Repo play-circle, and Phase 5 generates the PWA icons from it.

Both marks keep their own fixed colours in both themes. They don't use the `accent` token.

**Files:**
- Create: `apps/web/src/components/LogoMark.svelte`
- Modify: `apps/web/src/components/TopBar.svelte` (replace the red bar `<span class="block h-3 w-[18px] …">`)
- Replace: `apps/web/public/favicon.svg` (`index.html` already links it, so no change there)
- Modify: `DESIGN.md` (logo mark in Layout, `accent` row and colour rules)
- Test: `apps/web/e2e/shell.spec.ts`

**Interfaces:**
- Produces: `LogoMark.svelte`, with prop `size?: number` (height in px, default 20). Width is `Math.round(size * 90 / 62.583)`, which is 29 at 20 px. It has `aria-hidden="true"` and `focusable="false"`, and its colours are fixed in both themes. Phase 6 (phone top bar, mark only) reuses it.
- Produces: `public/favicon.svg`. Phase 5 builds `public/icon.svg` and the PWA PNGs from this mark.

`LogoMark.svelte` body (the viewBox is cropped to the screen shape, so there's no empty band above or below):

```svelte
<script lang="ts">
  let { size = 20 }: { size?: number } = $props();
</script>

<svg
  viewBox="0 13.708 90 62.583"
  width={Math.round((size * 90) / 62.583)}
  height={size}
  aria-hidden="true"
  focusable="false"
  class="block shrink-0"
>
  <path fill="#ff0000" d="M 83.494 76.291 H 6.506 C 2.913 76.291 0 73.379 0 69.786 V 20.214 c 0 -3.593 2.913 -6.506 6.506 -6.506 h 76.988 c 3.593 0 6.506 2.913 6.506 6.506 v 49.571 C 90 73.379 87.087 76.291 83.494 76.291 z" />
  <path fill="#ffffff" d="M 36.457 53.756 L 54.9 43.107 c 0.904 -0.522 0.904 -1.828 0 -2.35 l -18.443 -10.65 c -0.904 -0.522 -2.035 0.13 -2.035 1.175 v 21.299 C 34.422 53.626 35.552 54.278 36.457 53.756 z" />
  <path fill="#ff7c7c" d="M 81.317 67.598 h -6.608 c -0.565 0 -1.023 -0.457 -1.023 -1.023 c 0 -0.565 0.457 -1.023 1.023 -1.023 h 6.608 c 0.565 0 1.023 0.457 1.023 1.023 C 82.34 67.14 81.882 67.598 81.317 67.598 z" />
  <path fill="#ff7c7c" d="M 65.764 67.598 H 21.513 c -0.565 0 -1.023 -0.457 -1.023 -1.023 c 0 -0.565 0.458 -1.023 1.023 -1.023 h 44.251 c 0.565 0 1.023 0.457 1.023 1.023 C 66.787 67.14 66.329 67.598 65.764 67.598 z" />
  <path fill="#ff7c7c" d="M 14.992 67.598 H 8.684 c -0.565 0 -1.023 -0.457 -1.023 -1.023 c 0 -0.565 0.458 -1.023 1.023 -1.023 h 6.309 c 0.565 0 1.023 0.457 1.023 1.023 C 16.015 67.14 15.557 67.598 14.992 67.598 z" />
  <circle fill="#ff7c7c" cx="18.25" cy="66.58" r="3.26" />
</svg>
```

New `public/favicon.svg` (the full file):

```svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 90 90">
  <title>YourTube</title>
  <path fill="#bb1a1a" d="M 45 90 C 20.187 90 0 69.813 0 45 c 31.16 -8.812 61.257 -9.555 90 0 C 90 69.813 69.813 90 45 90 z" />
  <path fill="#dd2222" d="M 45 0 C 20.187 0 0 20.187 0 45 h 90 C 90 20.187 69.813 0 45 0 z" />
  <path fill="#f0f0f0" d="M 63.885 47.325 l -14.816 8.554 l -14.816 8.554 c -1.79 1.033 -4.026 -0.258 -4.026 -2.325 V 45 c 10.606 -4.196 22.359 -3.855 35 0 C 65.227 45.904 64.78 46.808 63.885 47.325 z" />
  <path fill="#ffffff" d="M 63.885 42.675 l -14.816 -8.554 l -14.816 -8.554 c -1.79 -1.033 -4.026 0.258 -4.026 2.325 V 45 h 35 C 65.227 44.096 64.78 43.192 63.885 42.675 z" />
</svg>
```

- [ ] **Step 1: Write the failing e2e test**

```ts
test("wordmark shows the player mark", async ({ page }) => {
  await page.goto(`${APP}#/`);
  const home = page.getByRole("link", { name: "yourtube" });
  const mark = home.locator("svg[aria-hidden='true']");
  await expect(mark).toBeVisible();
  const box = await mark.boundingBox();
  expect(box?.height).toBeGreaterThanOrEqual(17);
  expect(box?.height).toBeLessThanOrEqual(22);
  expect(box?.width).toBeGreaterThan(box?.height ?? 0);
});
```

- [ ] **Step 2: Run it and see it fail**

Run: `pnpm --filter @app/web e2e shell.spec.ts -g "player mark"`
Expected: FAIL, no `svg` inside the link.

- [ ] **Step 3: Add `LogoMark.svelte`, use it in `TopBar.svelte` in place of the red bar, and replace `public/favicon.svg`** (markup above). Keep the link's `w-[120px]` and `gap-2`. A 29 px mark plus "yourtube" fits in 120 px; this was measured in the built app. The link's accessible name stays "yourtube". Update `DESIGN.md`:
  - Layout: change "wordmark (red mark + "yourtube")" to "wordmark (player mark, 20 px tall, + "yourtube")".
  - Colour table, `accent` row: drop "logo mark" from its uses.
  - Rules line: change "red marks the logo mark, progress bars, …" to "red marks progress bars, …". Then add one sentence: "The logo mark and favicon are fixed brand artwork in their own reds (`#ff0000` mark, `#dd2222`/`#bb1a1a` favicon). They are the same in both themes and are not tokens."

- [ ] **Step 4: Run the e2e file and `pnpm check`**

Run: `pnpm --filter @app/web e2e shell.spec.ts && pnpm check`
Expected: all pass.

- [ ] **Step 5: Commit** `feat(web): player logo mark in the top bar and new favicon`

### Task 2: Theme tile that cycles Dark → Light → System

**Files:**
- Modify: `apps/web/src/lib/theme.ts`
- Create: `apps/web/src/lib/theme-state.svelte.ts`
- Create: `apps/web/src/components/ThemeToggle.svelte`
- Modify: `apps/web/src/components/ThemeSelect.svelte` (read and write the shared state instead of its own module `$state`)
- Modify: `apps/web/src/components/LeftRail.svelte` (footer uses `ThemeToggle`)
- Modify: `DESIGN.md` (theme tile)
- Test: `apps/web/test/theme.test.ts`, `apps/web/e2e/shell.spec.ts`

**Interfaces:**
- Consumes: `ThemeChoice`, `applyTheme`, `currentTheme` from `lib/theme.ts`.
- Produces:
  - `nextTheme(choice: ThemeChoice): ThemeChoice` (dark → light → system → dark)
  - `themeLabel(choice: ThemeChoice): string`, e.g. `"Theme: Dark. Switch to Light"`
  - `theme-state.svelte.ts`: `export const themeState: { choice: ThemeChoice }` (a `$state` object) and `setTheme(choice: ThemeChoice): void` (sets the state and calls `applyTheme`). `ThemeSelect` (Settings) and `ThemeToggle` (rail) both use it.

- [ ] **Step 1: Write the failing unit tests** in `test/theme.test.ts`

Extend the existing import to `import { isDark, nextTheme, readTheme, themeLabel } from "../src/lib/theme.ts";` and add:

```ts
test("nextTheme cycles", () => {
  expect(nextTheme("dark")).toBe("light");
  expect(nextTheme("light")).toBe("system");
  expect(nextTheme("system")).toBe("dark");
});
test("themeLabel names current and next", () => {
  expect(themeLabel("dark")).toBe("Theme: Dark. Switch to Light");
  expect(themeLabel("light")).toBe("Theme: Light. Switch to System");
  expect(themeLabel("system")).toBe("Theme: System. Switch to Dark");
});
```

- [ ] **Step 2: Run them and see them fail**

Run: `pnpm vitest run apps/web/test/theme.test.ts`
Expected: FAIL, because `nextTheme` and `themeLabel` don't exist yet.

- [ ] **Step 3: Implement `nextTheme`, `themeLabel`, `theme-state.svelte.ts`, `ThemeToggle.svelte`**

- `theme-state.svelte.ts`: `export const themeState = $state({ choice: currentTheme() })`. `setTheme` assigns `themeState.choice` and calls `applyTheme`. Export an object, because Svelte doesn't allow exporting a reassigned `$state` primitive.
- `ThemeSelect.svelte`: delete the `<script module>` block and its module `$state`. `checked` reads `themeState.choice`, and `onchange` calls `setTheme(c.value)`. Keep the `label` prop and markup.
- `ThemeToggle.svelte`: a `<button type="button">` built like the rail links (`w-16` with `py-1.5`, around a `size-7` `bg-raised` tile holding a `size-4` stroke icon), so the hit area is at least 44 px tall. It shows the moon (dark), sun (light) or monitor (system) as inline SVG with `aria-hidden`. There is no visible text label. `aria-label` and `title` are `themeLabel(themeState.choice)`, and a click calls `setTheme(nextTheme(themeState.choice))`. Keep the existing focus-visible outline style.
- `LeftRail.svelte`: swap `<div class="px-1"><ThemeSelect /></div>` for a centred `ThemeToggle`. Settings keeps `ThemeSelect` (its "Theme (settings)" label can stay).
- `DESIGN.md` → Layout: change "theme switch in the rail footer" to "theme tile in the rail footer (moon/sun/monitor, cycles Dark → Light → System; Settings keeps the three-option control)".

- [ ] **Step 4: Update the e2e theme test** in `shell.spec.ts`. Replace "dark by default, theme switch persists" with the test below. It runs on Settings so both controls are on screen. That way it checks the sync in both directions without a reload, then checks that the choice persists.

```ts
test("rail theme tile cycles, persists and stays in sync with Settings", async ({ page }) => {
  await page.goto(`${APP}#/settings`);
  await expect(page.locator("html")).toHaveClass(/dark/);
  await page.getByRole("button", { name: "Theme: Dark. Switch to Light" }).click();
  await expect(page.locator("html")).not.toHaveClass(/dark/);
  await expect(page.getByRole("radio", { name: "Light" })).toBeChecked();
  await page.getByText("System", { exact: true }).click();
  await expect(page.getByRole("button", { name: "Theme: System. Switch to Dark" })).toBeVisible();
  await page.reload();
  await expect(page.getByRole("radio", { name: "System" })).toBeChecked();
  await expect(page.getByRole("button", { name: "Theme: System. Switch to Dark" })).toBeVisible();
});
```

- [ ] **Step 5: Run unit, e2e and `pnpm check`** (`pnpm check` includes `vitest run`)

Run: `pnpm --filter @app/web e2e shell.spec.ts && pnpm check`
Expected: all pass.

- [ ] **Step 6: Commit** `feat(web): one-button theme tile in the rail`

## Phase 2: MP4 downloads

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
  - `run_download` result `path`: the last `requested_downloads[*].filepath` from the returned info, falling back to the last `finished` hook filename when `requested_downloads` is missing or has no `filepath`. (Phase 4's fake `YoutubeDL` reports the path only through the hook, so the fallback must stay.)
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

## Phase 3: HDR option

### Task 4: HDR on the job, in the sort and in the lookup (server)

**Files:**
- Create: `apps/server/alembic/versions/20261118110000_add_hdr.py` (`down_revision = "20261115120000"`; non-null boolean `hdr`, `server_default=sa.false()`)
- Modify: `apps/server/app/models.py` (`Download.hdr`), `apps/server/app/schemas.py` (`DownloadCreate.hdr`, `JobOut.hdr`, `FormatInfo.dynamic_range`, `StreamRow.dynamic_range`), `apps/server/app/services/queue.py` (`_row_from_payload`)
- Modify: `apps/server/app/services/quality.py` (`cap_format_options`, docstring), `apps/server/app/services/downloader.py` (`normalize_formats`, `StreamPickerRow`, `_row` in `build_stream_picker_payload`, `run_download`), `apps/server/app/services/job_runner.py`
- Modify: `apps/server/tests/e2e_server.py` (`_video_info`'s `fmt` takes an optional `dr`; add a 2160p HDR10 stream `v2160hdr` only for URL `https://e2e.test/v/a`, and nothing else changes)
- Modify: `apps/web/src/lib/api.gen.ts` (typegen)
- Modify: `README.md` ("Quality caps": the HDR paragraph from spec §7), `PRODUCT.md`, `docs/superpowers/specs/2026-11-18-phone-pwa-notifications-design.md` (non-goal line)
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
Also: in `docs/superpowers/specs/2026-11-18-phone-pwa-notifications-design.md`, change the non-goal `- HDR output.` to `- HDR output unless the job asks for it (see 2026-11-18-hdr-option-design.md).` In `PRODUCT.md`, append to the "Quality is a per-job cap" line: ` An opt-in HDR choice keeps HDR where the video offers it at the capped resolution; off by default.`
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

## Phase 4: Channel and playlist folders

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
- Modify: `apps/server/tests/e2e_server.py` (the stub keeps writing `<output_dir>/<last-url-part>.mp4`; it accepts the new kwarg)
- Modify: `apps/web/src/lib/playlist.ts` (`Header` gains `playlist: PlaylistFields | null`; `buildJobs` copies it onto each job), `apps/web/src/routes/ListView.svelte` (builds it from `result`), `apps/web/src/lib/api.gen.ts` (typegen)
- Modify: `README.md` (new "Library layout" section)
- Test: `tests/unit/test_downloader_layout.py`, `tests/unit/test_sources.py`, `tests/api/test_enqueue_api.py`, `tests/unit/test_job_runner.py`, `apps/web/test/playlist.test.ts`

**Interfaces:**
- Consumes: `PlaylistFolder`, `default_stem` (Task 6).
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

### Task 8: One-off move of existing files

**Files:**
- Create: `apps/server/app/services/library_layout.py`
- Modify: `apps/server/app/main.py` (lifespan: after `requeue_active_on_startup`, before workers start)
- Modify: `README.md` (one line under "Library layout")
- Test: `apps/server/tests/unit/test_library_layout.py`, `apps/server/tests/integration/test_startup_recovery.py`

**Interfaces:**
- Consumes: `slugify`, `first_slug`, `video_id_from_url` (Task 6).
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

## Phase 5: Phone access, PWA and player

### Task 9: Bind address and Tailscale access

**Files:**
- Create: `apps/server/app/__main__.py`
- Modify: `apps/server/package.json` (`dev`: `uv run python -m app --reload`; `start`: `uv run python -m app`)
- Modify: `apps/web/vite.config.ts` (`server.host`)
- Modify: `.env.example`, `README.md` (new section "Use it from your phone")
- Test: `apps/server/tests/test_main_entry.py`

**Interfaces:**
- Produces:
  - `uvicorn_options(s: Settings, *, reload: bool) -> dict[str, Any]` returns `{"app": "app.main:app", "host": s.host, "port": s.port, "reload": reload}`. `main(argv: list[str] | None = None) -> None` parses `--reload` and calls `uvicorn.run(**uvicorn_options(settings, reload=...))`.
  - Vite: `loadEnv(mode, <repo root>, "YT_")`. Set `server.host = true` when `YT_HOST` is set and is not `127.0.0.1` or `localhost`. The proxy target stays `http://127.0.0.1:${YT_PORT ?? 8000}`.

- [ ] **Step 1: Write the failing test**

```python
def test_uvicorn_options_use_settings(monkeypatch):
    monkeypatch.setenv("YT_HOST", "0.0.0.0"); monkeypatch.setenv("YT_PORT", "8123")
    opts = uvicorn_options(Settings(), reload=True)
    assert opts == {"app": "app.main:app", "host": "0.0.0.0", "port": 8123, "reload": True}

def test_default_host_is_loopback(monkeypatch):
    monkeypatch.delenv("YT_HOST", raising=False)
    assert uvicorn_options(Settings(_env_file=None), reload=False)["host"] == "127.0.0.1"
```

- [ ] **Step 2: Run it and see it fail**, then implement `__main__.py`, the scripts and Vite.

Run: `cd apps/server && uv run pytest tests/test_main_entry.py -v`
Expected: first FAIL, then PASS.

- [ ] **Step 3: Docs.** `.env.example` gets `# YT_HOST=0.0.0.0  # listen on the LAN (plain http)`. The README section covers:
  - Run `tailscale serve --bg 8000` on the host (Linux or the Docker host) to get `https://<host>.<tailnet>.ts.net`.
  - HTTPS is required for install and push. Plain LAN http works for browsing only.
  - Compose already binds `0.0.0.0`.

- [ ] **Step 4: Manually check that `pnpm start` with `YT_HOST=0.0.0.0` in `.env` listens on `0.0.0.0:8000`** (`lsof -iTCP:8000 -sTCP:LISTEN`). Then run `pnpm check`.

- [ ] **Step 5: Commit** `feat: configurable bind address and Tailscale docs`

### Task 10: Player and Save

**Files:**
- Modify: `apps/server/app/api/jobs.py` (`GET /api/downloads/{job_id}` → `JobOut`; `inline: bool = False` on the file route)
- Modify: `apps/web/src/lib/router.ts` (`{ name: "watch"; id: number }`, `#/watch/<id>`, `section` → `"library"`)
- Create: `apps/web/src/lib/save.ts`, `apps/web/src/routes/Watch.svelte`
- Modify: `apps/web/src/App.svelte` (route), `apps/web/src/components/JobCard.svelte` (thumbnail and title of a done job link to `#/watch/<id>`; the menu keeps "Download file" and "Delete"), `api.gen.ts`
- Modify: `DESIGN.md` (player)
- Test: `tests/api/test_queue_api.py` (or a new `tests/api/test_file_api.py`), `apps/web/test/router.test.ts`, `apps/web/test/save.test.ts`, `apps/web/e2e/library.spec.ts`

**Interfaces:**
- Produces:
  - `GET /api/downloads/{job_id}` → `JobOut`, or `404` (`ApiError`, same shape as today).
  - `GET /api/downloads/{job_id}/file?inline=1` → `FileResponse(path, filename=path.name, content_disposition_type="inline")`. The default stays `attachment`.
  - `SHARE_LIMIT_BYTES = 500 * 1024 * 1024`
  - `saveMode(size: number | null, canShareFiles: boolean): "share" | "link"`. Returns `"share"` only when `canShareFiles` is true and `size` is between 1 and `SHARE_LIMIT_BYTES`, inclusive.
  - `Watch.svelte` (prop `id: number`):
    - Loads the job. Shows `<video controls playsinline>` (or `<audio controls>` when `media_kind === "audio"`) with `src="/api/downloads/{id}/file?inline=1"`, plus title, uploader and size/format meta.
    - Actions: Save and Delete. Delete reuses `DELETE /api/library/{id}` and then goes to `#/`.
    - On the media `error` event it shows exactly: "This device can't play this file. Save it and open it in VLC."
    - Save with `"share"`: fetch the blob, then `navigator.share({ files: [new File([blob], name, { type })] })`. With `"link"`: an `<a href=…/file download>`.
    - A missing job shows "This download no longer exists." with a link to the library.

- [ ] **Step 1: Write the failing server tests**

```python
def test_file_inline_and_attachment(client, done_job):
    r = client.get(f"/api/downloads/{done_job.id}/file?inline=1")
    assert r.headers["content-disposition"].startswith("inline;")
    r = client.get(f"/api/downloads/{done_job.id}/file")
    assert r.headers["content-disposition"].startswith("attachment;")

def test_file_supports_range(client, done_job):
    r = client.get(f"/api/downloads/{done_job.id}/file?inline=1", headers={"Range": "bytes=0-1"})
    assert r.status_code == 206 and len(r.content) == 2

def test_get_job(client, done_job):
    assert client.get(f"/api/downloads/{done_job.id}").json()["id"] == done_job.id
    assert client.get("/api/downloads/999999").status_code == 404
```

- [ ] **Step 2: Write the failing web unit tests**

```ts
test("watch route", () => {
  expect(parseHash("#/watch/12")).toEqual({ name: "watch", id: 12 });
  expect(parseHash("#/watch/x")).toEqual({ name: "library" });
  expect(href({ name: "watch", id: 12 })).toBe("#/watch/12");
  expect(section({ name: "watch", id: 12 })).toBe("library");
});
test("saveMode", () => {
  expect(saveMode(10, true)).toBe("share");
  expect(saveMode(SHARE_LIMIT_BYTES, true)).toBe("share");
  expect(saveMode(SHARE_LIMIT_BYTES + 1, true)).toBe("link");
  expect(saveMode(null, true)).toBe("link");
  expect(saveMode(10, false)).toBe("link");
});
```

- [ ] **Step 3: Run them and see them fail**, then implement the server routes, router, `save.ts`, `Watch.svelte`, the `JobCard` links and the `DESIGN.md` player note. Run `pnpm typegen`.

- [ ] **Step 4: Add an e2e test** in `library.spec.ts`: click the seeded video's title. The URL matches `#/watch/\d+`, a `video` element has `src` ending in `file?inline=1`, and "Save" and "Delete" buttons are visible. Then call `page.evaluate` to dispatch an `error` event on the video and expect the VLC message.

- [ ] **Step 5: Run `pnpm check && pnpm e2e`.** Expected: PASS.

- [ ] **Step 6: Commit** `feat: in-app player with Save`

### Task 11: Installable PWA

**Files:**
- Modify: `apps/web/package.json` (`vite-plugin-pwa` ^2.0.0, `workbox-precaching` and `workbox-routing` ^7.4.1)
- Modify: `apps/web/vite.config.ts` (`VitePWA`)
- Create: `apps/web/src/sw.ts`, `apps/web/src/lib/share.ts`
- Create: `apps/web/public/icon.svg` (same mark as `favicon.svg` on a square `#0b0b0c` background with safe padding), plus generated `pwa-64x64.png`, `pwa-192x192.png`, `pwa-512x512.png`, `maskable-icon-512x512.png`, `apple-touch-icon-180x180.png`, `favicon.ico`
- Modify: `apps/web/index.html`, `apps/web/src/main.ts` (share handling before the router starts)
- Modify: `PRODUCT.md` (platform: web + phone PWA; remove PWA and playback from out-of-scope), `README.md` (install on iPhone)
- Test: `apps/web/test/share.test.ts`, `apps/web/e2e/pwa.spec.ts`

**Interfaces:**
- Produces:
  - `VitePWA` options: `strategies: "injectManifest"`, `srcDir: "src"`, `filename: "sw.ts"`, `registerType: "autoUpdate"`, `injectRegister: "auto"`, `includeAssets: ["favicon.ico", "apple-touch-icon-180x180.png"]`
  - Manifest:
    - `name` and `short_name` "YourTube", `display: "standalone"`, `start_url: "/"`, `scope: "/"`
    - `theme_color` and `background_color` `#0b0b0c`
    - icons 64/192/512 plus maskable 512
    - `share_target: { action: "/", method: "GET", params: { url: "share", text: "text", title: "title" } }`
  - `sw.ts`: `precacheAndRoute(self.__WB_MANIFEST)`, plus `NavigationRoute(createHandlerBoundToURL("index.html"), { denylist: [/^\/api\//, /^\/health/] })`. Push handlers come in Task 21.
  - `sharedUrl(search: string): string | null`: the first `http(s)` URL found in the `share`, then `text`, then `title` params (`text` may hold words around the URL).
  - `main.ts`: when `sharedUrl(location.search)` returns a URL, `history.replaceState(null, "", "/" + href({ name: "fetch", urls: url }))` before mounting.
  - `index.html`:
    - `<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">`
    - `theme-color` `#0b0b0c` (dark media) and `#ffffff` (light media)
    - `apple-mobile-web-app-capable` and `mobile-web-app-capable` `yes`, `apple-mobile-web-app-status-bar-style` `black-translucent`, `apple-mobile-web-app-title` "YourTube"
    - `<link rel="apple-touch-icon" href="/apple-touch-icon-180x180.png">`

- [ ] **Step 1: Write the failing unit tests**

```ts
test("sharedUrl", () => {
  expect(sharedUrl("?share=https%3A%2F%2Fyoutu.be%2Fa")).toBe("https://youtu.be/a");
  expect(sharedUrl("?text=Watch%20this%20https%3A%2F%2Fyoutu.be%2Fb%20!")).toBe("https://youtu.be/b");
  expect(sharedUrl("?title=x")).toBeNull();
  expect(sharedUrl("")).toBeNull();
});
```

- [ ] **Step 2: Run it and see it fail**, then implement `share.ts`, the `main.ts` hook, the plugin config, `sw.ts`, the icons and `index.html`. Generate the icons once with `pnpm dlx @vite-pwa/assets-generator --preset minimal-2023 public/icon.svg` and commit the PNGs and `favicon.ico`.

- [ ] **Step 3: Write `e2e/pwa.spec.ts`**
  - `GET /manifest.webmanifest` is JSON with `name == "YourTube"` and `share_target.action == "/"`.
  - Opening `/?share=https%3A%2F%2Fe2e.test%2Fvideo` lands on `#/fetch/https%3A%2F%2Fe2e.test%2Fvideo` with no `?share` left in the URL.
  - After load, `await page.evaluate(() => navigator.serviceWorker.ready.then(r => !!r.active))` is `true`.
  - `GET /api/queue` is still JSON, not `index.html`, after the SW is active.

- [ ] **Step 4: Run `pnpm check && pnpm e2e`.** Expected: PASS.

- [ ] **Step 5: Docs.** In `PRODUCT.md`: the platform is web plus a phone PWA, and PWA and playback leave out-of-scope. In `README.md`: install on iPhone (open the Tailscale URL in Safari → Share → Add to Home Screen) and on Android/desktop (browser install, share sheet target).

- [ ] **Step 6: Commit** `feat(web): installable PWA with share target`

### Task 12: Paste button on phones

**Files:**
- Modify: `apps/web/src/components/TopBar.svelte`
- Modify: `README.md` (copy-paste flow; optional iOS Shortcut)
- Test: `apps/web/e2e/phone.spec.ts` (new file, `test.use({ viewport: { width: 390, height: 844 }, hasTouch: true })`)

**Interfaces:**
- Produces: below 768 px (`md:hidden`), while the URL field is empty, a "Paste" button sits beside the field. On tap it calls `navigator.clipboard.readText()` and puts the text in the field. If that rejects, or the text is empty, it focuses the field. It never auto-fetches. Above 768 px it is not rendered.

- [ ] **Step 1: Write the failing e2e tests**

```ts
test("Paste fills the field without fetching", async ({ page, context }) => {
  await context.grantPermissions(["clipboard-read", "clipboard-write"]);
  await page.goto(`${APP}#/`);
  await page.evaluate(() => navigator.clipboard.writeText("https://youtu.be/a"));
  await page.getByRole("button", { name: "Paste" }).click();
  await expect(page.getByRole("textbox", { name: "Video or playlist URL" })).toHaveValue("https://youtu.be/a");
  await expect(page).toHaveURL(/#\/$/);
  await expect(page.getByRole("button", { name: "Paste" })).toBeHidden();
});
test("Paste falls back to focusing the field", async ({ page }) => {
  await page.addInitScript(() => {
    Object.defineProperty(navigator, "clipboard", { value: { readText: () => Promise.reject(new Error("denied")) } });
  });
  await page.goto(`${APP}#/`);
  await page.getByRole("button", { name: "Paste" }).click();
  await expect(page.getByRole("textbox", { name: "Video or playlist URL" })).toBeFocused();
});
```

Also add a desktop test in `shell.spec.ts`: no "Paste" button at 1440 px.

- [ ] **Step 2: Run them and see them fail**, then implement the button.

- [ ] **Step 3: README.** Describe the copy-paste flow. Add the optional iOS Shortcut "Send to YourTube": Receive URLs from Share Sheet → URL Encode → Open URL `https://<host>/#/fetch/<encoded>`. Say that no app code depends on it.

- [ ] **Step 4: Run `pnpm check && pnpm e2e`, then commit** `feat(web): Paste button for phones`

---

## Phase 6: Phone layout

### Task 13: Phone mockups and owner approval (hard stop)

**Files:**
- Create: `docs/design/phone-mockups.html` (static, self-contained, no CDN, uses `DESIGN.md` tokens)
- Create: `docs/superpowers/specs/2026-11-18-phone-layout-mockups.md` (one section per screen: what changes and why, plus the owner's decision)

**Interfaces:**
- Produces: approved mockups at 390×844 for the shell (top bar, bottom tab bar, toasts at the top), Library list, Queue, Fetch video view with the override bottom sheet, playlist picker, Settings (theme control and the future notification toggle) and Watch. Tasks 14–17 build to them.

- [ ] **Step 1: Load the Impeccable skill (shape) with `DESIGN.md` and `PRODUCT.md` as context.** Draft the mockups, then check them against the taste-skill anti-slop rules.
- [ ] **Step 2: Render every screen in both themes** (a Playwright screenshot or a browser) and look at each one.
- [ ] **Step 3: Show the owner the screenshots and the notes. STOP until the owner approves.** Record the approval and any requested changes in the mockups doc.
- [ ] **Step 4: Commit** `docs: approved phone layout mockups`

### Task 14: Phone shell

**Files:**
- Create: `apps/web/src/components/TabBar.svelte`
- Modify: `apps/web/src/App.svelte`, `apps/web/src/app.css` (drop `min-width: 960px`, add safe-area padding), `apps/web/src/components/LeftRail.svelte` (`hidden md:flex`), `apps/web/src/components/TopBar.svelte` (below md: mark only, wordmark text visually hidden, field fills the width), `apps/web/src/components/Toasts.svelte` (top on phones, below `safe-area-inset-top`)
- Modify: `DESIGN.md` (Phone section: 768 px breakpoint, tab bar, 44 px targets, safe areas; remove the 960 px minimum)
- Test: `apps/web/e2e/phone.spec.ts`

**Interfaces:**
- Consumes: `section(route)`, the queue count from `App.svelte`, `LogoMark` (Task 1).
- Produces: `TabBar.svelte` with props `{ active: Section; queueCount: number }`. It renders links Library, Queue (red count badge with the number in text) and Settings, each at least 44 px tall. It pads `env(safe-area-inset-bottom)` and is `md:hidden`.

- [ ] **Step 1: Write the failing e2e tests** (390×844):
  - The tab bar's links navigate and set `aria-current="page"`. The rail is hidden.
  - `document.documentElement.scrollWidth <= innerWidth` on `#/`, `#/queue` and `#/settings`.
  - Every tab link's bounding box is at least 44 px tall.
  - The theme tile is not visible, and Settings has the theme radios.
- [ ] **Step 2: Run them and see them fail**, then build to the approved mockup.
- [ ] **Step 3: Run `pnpm check && pnpm e2e`** (desktop specs must still pass at 1440 px). **Commit** `feat(web): phone shell with bottom tab bar`

### Task 15: Phone Library, Queue, Settings and Watch

**Files:**
- Modify: `apps/web/src/routes/Library.svelte` (single-column list below md: thumbnail left, title/meta right, tap opens `#/watch/<id>`), `apps/web/src/components/JobCard.svelte` (a list variant, or responsive classes), `apps/web/src/routes/Queue.svelte` (single column, actions 44 px), `apps/web/src/routes/Settings.svelte` (stacked form), `apps/web/src/routes/Watch.svelte` (full-width player, actions in thumb reach)
- Test: `apps/web/e2e/phone.spec.ts`

- [ ] **Step 1: Write the failing e2e tests** (390×844, seeded library and the slow queued job):
  - Library: no horizontal overflow. Tapping the seeded item opens `#/watch/<id>`.
  - Queue: no horizontal overflow. The Cancel button is at least 44 px.
  - Settings: no horizontal overflow, and every input is visible without sideways scrolling.
  - Watch: the video width is at most the viewport width. Save and Delete are at least 44 px.
- [ ] **Step 2: Run them and see them fail**, then build to the mockups.
- [ ] **Step 3: Run `pnpm check && pnpm e2e`. Commit** `feat(web): phone layout for library, queue, settings and player`

### Task 16: Phone Fetch views and override bottom sheet

**Files:**
- Create: `apps/web/src/components/BottomSheet.svelte`
- Modify: `apps/web/src/routes/VideoView.svelte`, `apps/web/src/routes/ListView.svelte`, `apps/web/src/components/EntryCard.svelte`, `apps/web/src/components/OverridePanel.svelte` (rendered inside `BottomSheet` below md, unchanged above)
- Test: `apps/web/e2e/phone.spec.ts`

**Interfaces:**
- Produces: `BottomSheet.svelte` with props `{ open: boolean; title: string; onclose: () => void; children: Snippet }`. It is a modal `<dialog>` docked to the bottom, max height 85vh, scrolls inside, closes on Escape, backdrop tap and a Close button, and returns focus to the opener. It pads `safe-area-inset-bottom`.

- [ ] **Step 1: Write the failing e2e tests** (390×844, stubbed `https://e2e.test/video` and the playlist URL used in `playlist.spec.ts`):
  - Video view: no horizontal overflow. "Download" is reachable and queues the job.
  - Playlist: no horizontal overflow. Opening an entry's override shows a `dialog` named after the panel title. Escape closes it and focus returns to the opener.
- [ ] **Step 2: Run them and see them fail**, then build to the mockups.
- [ ] **Step 3: Run `pnpm check && pnpm e2e`. Commit** `feat(web): phone fetch views with bottom-sheet overrides`

### Task 17: Critique and polish pass

**Files:** whichever phone views the critique flags. Also `DESIGN.md` if a rule changes.

- [ ] **Step 1: Run the Impeccable skill's critique and audit on every phone screen in both themes**, plus the taste-skill anti-slop checks. List the findings in the mockups doc.
- [ ] **Step 2: Fix each finding in its own small commit,** with a test where the finding is behavioural.
- [ ] **Step 3: Check contrast (AA) for the tab bar, the badges and the toasts in both themes.** Check that the phone e2e suite passes.
- [ ] **Step 4: Show the owner the final screenshots.** Commit `polish(web): phone layout critique fixes`

---

## Phase 7: Notifications

### Task 18: Batches and the one-summary guarantee

**Files:**
- Create: `apps/server/alembic/versions/20261118130000_add_batches_and_push.py` (`downloads.batch_id` nullable string with an index, `downloads.batch_notified` boolean default false, and table `push_subscriptions(id, endpoint unique not null, p256dh, auth, user_agent, created_at)`)
- Modify: `apps/server/app/models.py` (`Download.batch_id`, `Download.batch_notified`, `PushSubscription`)
- Modify: `apps/server/app/services/queue.py`
- Modify: `apps/server/app/schemas.py` (`JobOut.batch_id: str | None`)
- Test: `apps/server/tests/unit/test_queue_batches.py`, `apps/server/tests/unit/test_queue_retry_dismiss.py`

**Interfaces:**
- Produces:
  - `enqueue_downloads(session, payloads)`: when `len(payloads) > 1`, every row gets the same `batch_id = str(uuid4())`. A single job gets `None`.
  - `retry_job` also sets `batch_id = None` (a retried job notifies as a single job).
  - `@dataclass(frozen=True) class BatchSummary: batch_id: str; name: str; done: int; failed: int; cancelled: int; finished_at: datetime | None`
    - `name` = the first row's `playlist_title`, else `f"{n} videos"` where `n` is the batch size
  - `claim_batch_summary(session: Session, batch_id: str) -> BatchSummary | None`: one atomic `UPDATE downloads SET batch_notified = 1 WHERE id = (lowest id in batch) AND batch_notified = 0 AND NOT EXISTS (row in batch with status in ('queued','active'))`. When `rowcount == 1`, commit and return the counts from the DB. Otherwise return `None`.
  - `recent_batch_summaries(session: Session, limit: int = 5) -> list[BatchSummary]`: batches whose marker row has `batch_notified = 1`, newest `finished_at` first.

- [ ] **Step 1: Write the failing tests**
  - Enqueueing 3 jobs gives one shared UUID. Enqueueing 1 gives `None`.
  - `claim_batch_summary` returns `None` while any job is queued or active. Once all have settled (2 done, 1 error), it returns `BatchSummary(name="Mix", done=2, failed=1, cancelled=0, …)`. A second call returns `None`.
  - **Race:** two `db_session_visible` sessions on a file-backed SQLite DB call `claim_batch_summary` for the same settled batch from two threads behind a `threading.Barrier(2)`. Exactly one gets a summary.
  - A multi-URL batch with no `playlist_title` is named `"3 videos"`.
  - Retry clears `batch_id`, and the remaining batch still settles and claims once.
- [ ] **Step 2: Run them and see them fail**, then implement the migration, the model and the queue functions.
- [ ] **Step 3: Run `pnpm typegen && pnpm check`. Commit** `feat(server): download batches with a single settled summary`

### Task 19: VAPID keys and the subscriptions API

**Files:**
- Modify: `apps/server/pyproject.toml` (`uv add pywebpush`)
- Modify: `apps/server/app/config.py` (`vapid_private_key: str | None = None`, `vapid_public_key: str | None = None`, `vapid_subject: str = "mailto:yourtube@localhost"`)
- Create: `apps/server/app/services/push.py` (keys and subscription storage in this task)
- Create: `apps/server/app/api/push.py`; register it in the API router
- Modify: `apps/server/app/schemas.py`, `api.gen.ts`, `.env.example`
- Test: `apps/server/tests/unit/test_push_keys.py`, `apps/server/tests/api/test_push_api.py`

**Interfaces:**
- Produces:
  - `@dataclass(frozen=True) class VapidKeys: private_key: str; public_key: str`. `public_key` is the uncompressed P-256 point, base64url without padding, ready for `applicationServerKey`.
  - `load_vapid_keys(data_dir: Path, s: Settings) -> VapidKeys`. Env overrides win when both are set. Otherwise it reads `data_dir / "vapid.json"`. If that is missing, it generates keys with `py_vapid.Vapid01().generate_keys()` and writes them with mode `0600`. The result is cached per process.
  - `upsert_subscription(session, endpoint: str, p256dh: str, auth: str, user_agent: str | None) -> None`, `delete_subscription(session, endpoint: str) -> bool`, `list_subscriptions(session) -> list[PushSubscription]`
  - API:
    - `GET /api/push/key` → `PushKey { public_key: str }`
    - `POST /api/push/subscriptions` with body `PushSubscriptionIn { endpoint: HttpUrl-like str (https only); keys: { p256dh: str; auth: str } }` → `204`. The user agent comes from the request header.
    - `DELETE /api/push/subscriptions` with body `PushSubscriptionDelete { endpoint: str }` → `204` (also when nothing matched)
- [ ] **Step 1: Write the failing tests**
  - Keys: a first call creates `vapid.json` with mode `0o600`. A second call returns the same keys. Env overrides skip the file. `public_key` decodes to 65 bytes starting `0x04`.
  - API: `GET /api/push/key` is stable across calls. `POST` twice with the same endpoint leaves one row and updates its keys. `POST` with an `http://` endpoint returns `422`. `DELETE` removes the row.
- [ ] **Step 2: Run them and see them fail**, then implement. Document `YT_VAPID_PRIVATE_KEY`, `YT_VAPID_PUBLIC_KEY` and `YT_VAPID_SUBJECT` in `.env.example`.
- [ ] **Step 3: Run `pnpm typegen && pnpm check`. Commit** `feat(server): VAPID keys and push subscription API`

### Task 20: Send pushes when jobs settle

**Files:**
- Modify: `apps/server/app/services/push.py`, `apps/server/app/services/job_runner.py`, `apps/server/app/api/jobs.py` (cancel)
- Test: `apps/server/tests/unit/test_push_send.py`, `apps/server/tests/unit/test_job_runner.py`

**Interfaces:**
- Consumes: `claim_batch_summary`, `BatchSummary` (Task 18), `load_vapid_keys`, `list_subscriptions`, `delete_subscription` (Task 19).
- Produces:
  - `@dataclass(frozen=True) class PushMessage: title: str; body: str; tag: str; url: str`. It is sent as JSON `{"title","body","tag","url"}`.
  - `job_message(row: Download) -> PushMessage | None`:
    - done → `("Downloaded", row.title or row.url, f"job-{row.id}", f"/#/watch/{row.id}")`
    - error → `("Download failed", f"{title}: {row.error_message}", f"job-{row.id}", "/#/queue")`
    - cancelled → `None`
  - `batch_message(s: BatchSummary) -> PushMessage`: title is `s.name`. The body joins the non-zero parts of `"{done} downloaded"`, `"{failed} failed"` and `"{cancelled} cancelled"` with ", " (when all are zero, `"0 downloaded"`). Tag `f"batch-{s.batch_id}"`, url `"/#/queue"`. Example: `"Mix"` / `"12 downloaded, 1 failed"`.
  - `send_to_all(session, message: PushMessage, *, send: Callable[..., Any] = webpush, timeout: float = 10) -> None`: calls `send(subscription_info=…, data=json, vapid_private_key=…, vapid_claims={"sub": settings.vapid_subject}, timeout=timeout)` per subscription. On `WebPushException` whose `response.status_code` is 404 or 410, it deletes the subscription. Any other exception is logged and skipped.
  - `notify_settled(job_id: int) -> None`: opens its own session and never raises. If the row has no `batch_id`, it sends `job_message`. Otherwise it calls `claim_batch_summary` and sends `batch_message` when that returns a summary.
  - `run_claimed_job` calls `notify_settled(job_id)` after each `release_job`. The cancel API calls it after a successful `cancel_job` when the row has a `batch_id` (a queued job cancelled from the UI can be the last of a batch).
- [ ] **Step 1: Write the failing tests** (with a fake `send` that records calls):
  - Done and error rows give the exact titles, bodies, tags and urls above. A cancelled row gives `None`.
  - `batch_message(BatchSummary(..., name="Mix", done=12, failed=1, cancelled=0))` gives body `"12 downloaded, 1 failed"`.
  - **Dead endpoint:** the fake raises `WebPushException` with a 410 response for subscription A and succeeds for B. A is deleted, and B got the message.
  - **Unreachable:** the fake raises `requests.Timeout` for A. B is still sent, nothing raises, and A is kept.
  - Runner: a single job that finishes calls `send` once with "Downloaded". A batch of 3 calls `send` once (the summary), only after the third settles. A raise inside `notify_settled` still leaves the job `done`.
  - Cancel API: cancelling the last queued job of a batch sends one summary.
- [ ] **Step 2: Run them and see them fail**, then implement.
- [ ] **Step 3: Run `pnpm check`. Commit** `feat(server): web push for finished, failed and settled batches`

### Task 21: Notifications on this device

**Files:**
- Modify: `apps/web/src/sw.ts` (`push` and `notificationclick` handlers)
- Create: `apps/web/src/lib/push.ts`
- Modify: `apps/web/src/routes/Settings.svelte` (toggle section)
- Modify: `README.md` (notifications on iPhone: install first, then turn on in Settings)
- Test: `apps/web/test/push.test.ts`, `apps/web/e2e/notifications.spec.ts`

**Interfaces:**
- Consumes: `/api/push/key`, `/api/push/subscriptions` (Task 19), the `PushMessage` JSON (Task 20).
- Produces:
  - `urlBase64ToUint8Array(s: string): Uint8Array`
  - `pushSupport(env: { hasPushManager: boolean; isIOS: boolean; standalone: boolean; permission: NotificationPermission | "unsupported" }): "ready" | "install-first" | "blocked" | "unsupported"`. iOS and not standalone → `"install-first"`. No PushManager → `"unsupported"`. Permission `"denied"` → `"blocked"`.
  - `enablePush(): Promise<void>` (called from the toggle's click handler only): `Notification.requestPermission()`, then `registration.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey })`, then `POST` the subscription. `disablePush(): Promise<void>`: unsubscribe and `DELETE`.
  - `sw.ts` `push`: parse the JSON and always call `showNotification(title, { body, tag, icon: "/pwa-192x192.png", data: { url } })`. Fall back to `{ title: "YourTube", body: "" }` when parsing fails. `notificationclick`: close it, focus an open client and navigate it to `data.url`, otherwise `clients.openWindow(data.url)`.
  - Settings section "Notifications" shows a switch labelled "Notifications on this device". Its state comes from `pushManager.getSubscription()`. Under it, depending on the support status:
    - `install-first`: "Add YourTube to your Home Screen first."
    - `blocked`: "Notifications are blocked for YourTube in your browser settings."
    - `unsupported`: "This browser can't show notifications."
- [ ] **Step 1: Write the failing unit tests** for `urlBase64ToUint8Array` (a known vector) and every `pushSupport` branch.
- [ ] **Step 2: Write the failing e2e test.** With `addInitScript`, stub `PushManager.prototype.subscribe`/`getSubscription` and `Notification.requestPermission` to return a fake subscription with `toJSON()`. Toggling on sends `POST /api/push/subscriptions` (wait for the request) and the switch is checked after a reload. Toggling off sends `DELETE`.
- [ ] **Step 3: Implement, run `pnpm check && pnpm e2e`. Commit** `feat(web): turn on notifications per device`
- [ ] **Step 4: Manual check on the owner's iPhone over Tailscale:** install, turn on, queue a short video, lock the phone, get the push, tap it, and land on the player. Record the result in the PR description.

### Task 22: Toast variants for failed jobs and batches

**Files:**
- Modify: `apps/server/app/schemas.py` (`QueueOut.batches: list[BatchOut]`, where `BatchOut` mirrors `BatchSummary`), `apps/server/app/api/jobs.py` (`get_queue` fills it from `recent_batch_summaries`), `api.gen.ts`
- Modify: `apps/web/src/lib/toasts.ts`, `apps/web/src/components/Toasts.svelte`, `apps/web/src/App.svelte`
- Modify: `apps/server/tests/e2e_server.py` (a URL containing `fail` raises in the stubbed download)
- Modify: `DESIGN.md` (toast variants)
- Test: `tests/api/test_queue_api.py`, `apps/web/test/toasts.test.ts`, `apps/web/e2e/queue.spec.ts`

**Interfaces:**
- Consumes: `recent_batch_summaries` (Task 18), `JobOut.batch_id`, `batch_message` copy (Task 20). Toasts reuse the same words as pushes.
- Produces:
  - `type ToastKind = "done" | "failed" | "batch"`; `type Toast = { key: string; kind: ToastKind; title: string; body: string }`
  - `newEvents(seen: Set<string>, queue: QueueOut, silent: boolean): { toasts: Toast[]; seen: Set<string> }`. Keys are `done:<id>` (completed, `batch_id` null), `failed:<id>` (failed, `batch_id` null) and `batch:<uuid>` (`queue.batches`). Batch jobs never toast on their own. Copy: done `"Downloaded"` / title; failed `"Download failed"` / `"<title>: <error_message>"`; batch name / summary body.
  - `Toasts.svelte` renders `kind` as an icon plus a text label (never by colour alone). `failed` uses the danger token.
  - `newCompletions` is removed (replaced by `newEvents`), and `SEEN_KEY` stays.
- [ ] **Step 1: Write the failing tests**
  - API: after a batch of 2 settles and is claimed, `GET /api/queue` returns `batches[0]` with its name and counts.
  - Vitest: first poll silent → no toasts, but all keys are seen. A new failed single job → one `failed` toast. A completed job with a `batch_id` → no toast. A new batch → one `batch` toast with body `"2 downloaded"`. The same queue again → no toasts.
  - e2e: enqueue `https://e2e.test/fail` → a toast "Download failed" appears.
- [ ] **Step 2: Run them and see them fail**, then implement and run `pnpm typegen`.
- [ ] **Step 3: Run `pnpm check && pnpm e2e`. Commit** `feat: toasts for failed downloads and settled batches`

### Task 23: Product and design docs close-out

**Files:** `PRODUCT.md`, `DESIGN.md`, `README.md`

- [ ] **Step 1: Bring the docs up to date.**
  - `PRODUCT.md`: remove live push from out-of-scope, add the phone user, and keep "no recommendations, avatars, view counts". A notification toggle is not a bell.
  - `DESIGN.md`: check that the logo mark, theme tile, phone section, player and toast variants all match what shipped.
  - `README.md`: list the new env vars (`YT_HOST`, `YT_VAPID_*`).
- [ ] **Step 2: Run `pnpm check`. Commit** `docs: product, design and README for phone, PWA and notifications`

---

## Spec coverage

| Spec item | Task |
|---|---|
| Goal 1 / §1 MP4 format selection | 3 |
| HDR option spec (`2026-11-18-hdr-option-design.md`) | 4, 5 |
| Goal 2 / §2 slug rule, fallbacks, 80 chars | 6 |
| §2 playlist fields, sources `playlist_channel`, worker path, collisions, sidecars, custom template wins | 7 |
| §2 one-off move | 8 |
| Goal 3 / §3 logo | 1 (icons from the favicon: 11) |
| Goal 4 / §4 theme tile | 2 (phone: Settings only, 14) |
| Goal 5 / §5 network | 9 |
| Goal 6 / §6 PWA, share target, Paste, Shortcut docs | 11, 12 |
| Goal 6 / §7 phone layout, mockups hard stop | 13–17 |
| Goal 8 / §8 player, `inline`, Range, Save, unplayable message | 10 |
| Goal 7 / §9 batches, single summary, retry | 18 |
| §9 VAPID, subscriptions, API, table | 19 |
| §9 delivery, 404/410, failures never fail the job | 20 |
| §9 Settings toggle, iOS hint, SW handlers | 21 |
| §9 toast variants | 22 |
| §10 docs | 1, 2, 3, 4, 7, 9, 10, 11, 12, 14, 21, 22, 23 |

**Plan decisions beyond the spec** (each follows from a spec rule):
- The spec's `playlist_id` fallback needs the id, so `playlist_id` travels with `playlist_title` and `playlist_channel` (Task 7).
- The rows moved at startup don't store a video id, so the title and collision fallbacks parse it from the row URL, then fall back to the row id (Task 8).
- A queued job cancelled from the UI can be the last of a batch, so the cancel API also checks for a settled batch (Task 20).
- Batch toasts need server data that survives the 20-row completed list, so `QueueOut` gains `batches` (Task 22).
