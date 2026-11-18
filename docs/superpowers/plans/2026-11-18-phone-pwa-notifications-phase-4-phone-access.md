# Phase 4: Phone access, PWA and player Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reach YourTube from the iPhone over Tailscale HTTPS, install it as a PWA, paste links in, and play or save finished files in the app.

**Usable result:** On the iPhone: open the Tailscale URL, Add to Home Screen, paste a link with the Paste button, queue it, then open the finished file in the player and Save it to Files. Screens still use the desktop layout, scaled down; Phase 5 adds the phone layout.

**Architecture:** Server: an `app/__main__.py` entry honours `YT_HOST`/`YT_PORT`, plus `GET /api/downloads/{id}` and an `inline` flag on the file route. Web: a `#/watch/<id>` route with `Watch.svelte`, `vite-plugin-pwa` in injectManifest mode with `src/sw.ts` (app-shell precache only), a `share_target` handled in `main.ts`, and a phone-only Paste button.

**Tech Stack:** FastAPI, Svelte 5, Vite 8, Playwright. New: `vite-plugin-pwa` ^2.0.0, `workbox-precaching` / `workbox-routing` ^7.4.1. Icons generated once with `pnpm dlx @vite-pwa/assets-generator` (not a dependency).

**Spec:** `docs/superpowers/specs/2026-11-18-phone-pwa-notifications-design.md` (§5 Network access, §6 PWA, §8 Player and Save, §10 Docs (PRODUCT/README parts))

**Parent plan:** `docs/superpowers/plans/2026-11-18-phone-pwa-notifications.md`, Tasks 7, 8, 9, 10. The tasks below are copied from it verbatim; the parent plan wins if they ever differ. Phase index: `docs/superpowers/plans/2026-11-18-phone-pwa-notifications-phases.md`.

**Prerequisites:** Phase 1 merged (the new play-circle `public/favicon.svg` is the icon source). Phase 3 merged, so the README already has "Library layout" and the e2e seeded file sits at `e2e/seeded-video.mp4`.

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

1. **iPhone playback of a large file.** The file endpoint answers `Range` requests with `206`. Save uses the share sheet only for files of 500 MB or less, and the download link above that. Task 8 owns the tests.
2. The service worker must never answer `/api/` or `/health` with `index.html` (Task 9's e2e checks `/api/queue`). `?share=` must leave the URL once handled, so a reload doesn't re-fetch (Task 9).

---

### Task 7: Bind address and Tailscale access

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

### Task 8: Player and Save

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

### Task 9: Installable PWA

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
  - `sw.ts`: `precacheAndRoute(self.__WB_MANIFEST)`, plus `NavigationRoute(createHandlerBoundToURL("index.html"), { denylist: [/^\/api\//, /^\/health/] })`. Push handlers come in Task 19.
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

### Task 10: Paste button on phones

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

## Done when

- Every task above is committed and `pnpm check && pnpm e2e` pass on the branch.
- The usable result above works by hand.
