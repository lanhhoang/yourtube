# Phase 5: Phone access, PWA and player Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reach YourTube from the iPhone over Tailscale HTTPS, install it as a PWA, paste links in, and play or save finished files in the app.

**Usable result:** On the iPhone: open the Tailscale URL, Add to Home Screen, paste a link with the Paste button, queue it, then open the finished file in the player and Save it (Photos or Files). Screens still use the desktop layout, scaled down; Phase 6 adds the phone layout.

**Architecture:** Server: an `app/__main__.py` entry honours `YT_HOST`/`YT_PORT`, plus `GET /api/downloads/{id}` and an `inline` flag on the file route. Web: a `#/watch/<id>` route with `Watch.svelte`, `vite-plugin-pwa` in injectManifest mode with `src/sw.ts` (app-shell precache only), a `share_target` handled by `src/share-redirect.ts` before the router loads, and a phone-only Paste button.

**Tech Stack:** FastAPI (Starlette 1.10), Svelte 5, Vite 8, Playwright. New dev dependencies: `vite-plugin-pwa` ^2.0.0, `workbox-core`, `workbox-precaching` and `workbox-routing` ^7.4.1. Icons are generated once with `pnpm dlx @vite-pwa/assets-generator@2.0.0` (not a dependency).

**Spec:** `docs/superpowers/specs/2026-11-18-phone-pwa-notifications-design.md` (§5 Network access, §6 PWA, §8 Player and Save, §10 Docs (PRODUCT/README parts))

**Parent plan:** `docs/superpowers/plans/2026-11-18-phone-pwa-notifications.md`, Tasks 9, 10, 11, 12. The tasks below are copied from it verbatim; the parent plan wins if they ever differ. Phase index: `docs/superpowers/plans/2026-11-18-phone-pwa-notifications-phases.md`.

**Prerequisites:** Phase 1 merged (the play-circle `public/favicon.svg` is the icon source). Phase 4 merged, so the README already has "Library layout" and the e2e seeded file sits at `e2e/seeded-video.mp4`. Both are true on `main` at `f9de708`.

**Revised 2026-11-18 after a readiness review** (parent plan and spec updated to match). Each item was checked against the code or with a throwaway build:

- **iPhone Save takes two taps (owner's choice).** iOS only opens the share sheet right after a tap, and fetching the file first uses up that tap. Save now fetches with progress, then shows a "Share file" button that opens the sheet. The download link stays the fallback.
- **The share redirect lives in its own module, `src/share-redirect.ts`, imported first in `main.ts`.** ES imports run before the body of `main.ts`, and `router.svelte.ts` reads `location.hash` when it loads. A `replaceState` in the body of `main.ts` ran too late, and the app opened the library (seen in e2e).
- **`workbox-core` is added.** `registerType: "autoUpdate"` with injectManifest needs `self.skipWaiting()` and `clientsClaim()` in `sw.ts` (vite-plugin-pwa docs). `cleanupOutdatedCaches()` is added too.
- **The icons come straight from `favicon.svg`, using a committed `pwa-assets.config.js`.** There is no `icon.svg`. The `--preset minimal-2023` CLI pads apple and maskable icons on white. The config pads them on `#0b0b0c` instead (checked visually).
- **The server tests use the existing `_add` helper in `tests/api/test_library_api.py`.** There is no `done_job` fixture.
- **`apps/server/README.md` says nothing reads `YT_HOST`.** Task 9 updates it.
- **The watch e2e tests go before "delete in library".** That test deletes the seeded video.
- Checked and working: vite-plugin-pwa 2.0.0 supports Vite 8 (peer range `^8.0.0`) and builds `sw.js` and `manifest.webmanifest`. `sw.ts` with `/// <reference lib="webworker" />` passes `svelte-check` and `tsc -p tsconfig.node.json`. The full e2e suite (21 tests) passed with the service worker active. `FileResponse(..., content_disposition_type="inline")` answers `Range` with `206`. `spa.py` serves `/sw.js` and `/manifest.webmanifest` (`application/manifest+json`).
- Local note: if Playwright's bundled headless shell is missing, run the e2e suite with `PW_CHANNEL=chrome`.

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

1. **iPhone playback and Save of a large file.** The file endpoint answers `Range` requests with `206`. Save uses the share sheet only for files of 500 MB or less, and the download link above that. The share sheet opens from a second tap, never straight after the `fetch`. If sharing fails with anything other than `AbortError`, the download link appears. Task 10 owns the tests.
2. **The service worker must never answer `/api/` or `/health` with `index.html`.** Task 11's e2e checks `/api/queue` from a page the worker controls. `?share=` must leave the URL before the router reads the hash, so the first render is the fetch route and a reload doesn't fetch again (Task 11).

---

### Task 9: Bind address and Tailscale access

**Files:**

- Create: `apps/server/app/__main__.py`
- Modify: `apps/server/package.json` (`dev`: `uv run python -m app --reload`; `start`: `uv run python -m app`)
- Modify: `apps/web/vite.config.ts` (`server.host`, proxy port)
- Modify: `.env.example`, `README.md` (new section "Use it from your phone"), `apps/server/README.md` (line 33 says nothing reads `YT_HOST`/`YT_PORT`; now `python -m app` does, and Docker still passes `--host 0.0.0.0`)
- Test: `apps/server/tests/test_main_entry.py`

**Interfaces:**

- Produces:
  - `uvicorn_options(s: Settings, *, reload: bool) -> dict[str, Any]` returns `{"app": "app.main:app", "host": s.host, "port": s.port, "reload": reload}`. `main(argv: list[str] | None = None) -> None` parses `--reload` with `argparse` and calls `uvicorn.run(**uvicorn_options(settings, reload=...))`. `if __name__ == "__main__": main()`.
  - Vite: `defineConfig(({ mode }) => …)`, and `loadEnv(mode, resolve(import.meta.dirname, "../.."), "YT_")`. Merge `process.env` over it, so a shell `YT_HOST` wins as it does for pydantic-settings. Set `server.host = true` when `YT_HOST` is set and is not `127.0.0.1` or `localhost`. Both proxy targets become `http://127.0.0.1:${YT_PORT ?? 8000}`.
  - The Dockerfile `CMD` and `compose.yaml` stay as they are. They already bind `0.0.0.0:8000`.

- [ ] **Step 1: Write the failing test**

```python
import uvicorn

from app import __main__ as entry
from app.__main__ import uvicorn_options
from app.config import Settings


def test_uvicorn_options_use_settings(monkeypatch):
    monkeypatch.setenv("YT_HOST", "0.0.0.0")
    monkeypatch.setenv("YT_PORT", "8123")
    opts = uvicorn_options(Settings(), reload=True)
    assert opts == {"app": "app.main:app", "host": "0.0.0.0", "port": 8123, "reload": True}


def test_default_host_is_loopback(monkeypatch):
    monkeypatch.delenv("YT_HOST", raising=False)
    assert uvicorn_options(Settings(_env_file=None), reload=False)["host"] == "127.0.0.1"


def test_main_passes_reload_flag(monkeypatch):
    calls = []
    monkeypatch.setattr(uvicorn, "run", lambda **kw: calls.append(kw))
    entry.main(["--reload"])
    entry.main([])
    assert [c["reload"] for c in calls] == [True, False]
```

- [ ] **Step 2: Run it and see it fail**, then implement `__main__.py`, the scripts and Vite.

Run: `cd apps/server && uv run pytest tests/test_main_entry.py -v`
Expected: first FAIL (`ModuleNotFoundError: app.__main__`), then PASS.

- [ ] **Step 3: Docs.**
  - `.env.example` gets `# YT_HOST=0.0.0.0  # listen on the LAN (plain http)`.
  - The README section "Use it from your phone" (after "Quick Start") covers:
    - Run `tailscale serve --bg 8000` on the host (Linux or the Docker host) to get `https://<host>.<tailnet>.ts.net`. Tailscale terminates TLS, and the app keeps speaking plain HTTP on loopback.
    - HTTPS is required for install, Save to Photos and (later) push. Plain LAN http (`YT_HOST=0.0.0.0`) works for browsing only.
    - Compose already binds `0.0.0.0`.
  - `apps/server/README.md`: `YT_HOST` and `YT_PORT` are read by `python -m app` (`pnpm start`/`pnpm dev`). Docker passes the uvicorn flags itself.

- [ ] **Step 4: Check by hand that `YT_HOST=0.0.0.0 pnpm start` listens on `0.0.0.0:8000`** (`lsof -iTCP:8000 -sTCP:LISTEN`), and that `pnpm start` with no `YT_HOST` listens on `127.0.0.1:8000`. Then run `pnpm check`.

- [ ] **Step 5: Commit** `feat: configurable bind address and Tailscale docs`

### Task 10: Player and Save

**Files:**

- Modify: `apps/server/app/api/jobs.py` (`GET /api/downloads/{job_id}` → `JobOut`; `inline: bool = False` on the file route)
- Modify: `apps/web/src/lib/router.ts` (`{ name: "watch"; id: number }`, `#/watch/<id>`, `section` → `"library"`)
- Create: `apps/web/src/lib/save.ts`, `apps/web/src/routes/Watch.svelte`
- Modify: `apps/web/src/App.svelte` (the route, wrapped in `{#key id}`), `apps/web/src/components/JobCard.svelte` (the thumbnail and title of a done job link to `#/watch/<id>`; the hover menu keeps "Download file" and "Delete"), `apps/web/src/lib/api.gen.ts`
- Modify: `DESIGN.md` (player)
- Test: `apps/server/tests/api/test_library_api.py` (next to the existing file-route tests), `apps/web/test/router.test.ts`, `apps/web/test/save.test.ts`, `apps/web/e2e/library.spec.ts`

**Interfaces:**

- Produces:
  - `GET /api/downloads/{job_id}` → `JobOut` for any status, or `404` `ApiError(404, "not_found", "Download not found.")`.
  - `GET /api/downloads/{job_id}/file?inline=1` → `FileResponse(path, filename=path.name, content_disposition_type="inline")`. The default stays `attachment`. Range support comes from Starlette's `FileResponse`.
  - `save.ts`:
    - `SHARE_LIMIT_BYTES = 500 * 1024 * 1024`
    - `saveMode(size: number | null, canShareFiles: boolean): "share" | "link"`. Returns `"share"` only when `canShareFiles` is true and `size` is between 1 and `SHARE_LIMIT_BYTES`, inclusive.
    - `canShareFiles(): boolean` is `typeof navigator.canShare === "function"` and `navigator.canShare({ files: [new File([], "x.mp4", { type: "video/mp4" })] })`, wrapped in `try`/`catch` → `false`.
    - `fileName(title: string | null, format: string | null): string` replaces each run of `/\:*?"<>|` and control characters with `-`, trims, and falls back to `"download"`. It appends `.${format}` when `format` is set.
    - `fetchBlob(url: string, onProgress: (fraction: number) => void, signal: AbortSignal): Promise<Blob>` reads `response.body` and reports `received / Content-Length` (it skips progress when the length is missing). It throws on a non-OK status. The blob keeps the response `Content-Type`.
  - `Watch.svelte` (prop `id: number`):
    - Loads the job with `GET /api/downloads/{id}`. Shows `<video controls playsinline preload="metadata">` (or `<audio controls>` when `media_kind === "audio"`) with `src="/api/downloads/{id}/file?inline=1"`, then the title (`h1`), and a meta line: uploader · quality · size · format (reuse `qualityLabel` and `formatSize`).
    - On the media `error` event it shows exactly: "This device can't play this file. Save it and open it in VLC."
    - Actions: Save and Delete. Delete uses the same two-step confirm as `JobCard` ("Delete" → "Confirm delete"), calls `DELETE /api/library/{id}`, and then goes to `#/`.
    - Save in `"link"` mode is `<a href="/api/downloads/{id}/file" download>Save</a>`.
    - Save in `"share"` mode (owner's choice: two taps):
      1. Tap "Save". The button turns into "Preparing… 42%" (`tabular`, disabled) while `fetchBlob` runs. Unmounting aborts the fetch.
      2. It then shows a "Share file" button. Tapping it calls `navigator.share({ files: [new File([blob], fileName(title, media_format), { type: blob.type })] })`.
      3. `AbortError` (the owner closed the sheet) keeps "Share file" so they can tap again.
      4. Any other error, or a failed fetch, shows "Couldn't open the share sheet." and the `"link"` Save in its place.
    - A `404` job shows "This download no longer exists." with a link to the library. A job that isn't `done` shows "This download isn't finished yet." with a link to the queue.
    - Layout: centred, `max-w-[960px]`, black 16:9 media box. The actions are pill buttons from the existing button styles. No new colours.

- [ ] **Step 1: Write the failing server tests** (in `tests/api/test_library_api.py`, using its `_add` helper)

```python
def test_file_inline_and_attachment(
    client: TestClient, db_session_visible: Session, tmp_path: Path
) -> None:
    f = tmp_path / "v.mp4"
    f.write_bytes(b"data")
    job = _add(db_session_visible, file_path=str(f))
    r = client.get(f"/api/downloads/{job}/file?inline=1")
    assert r.headers["content-disposition"].startswith("inline;")
    r = client.get(f"/api/downloads/{job}/file")
    assert r.headers["content-disposition"].startswith("attachment;")


def test_file_supports_range(
    client: TestClient, db_session_visible: Session, tmp_path: Path
) -> None:
    f = tmp_path / "v.mp4"
    f.write_bytes(b"data")
    job = _add(db_session_visible, file_path=str(f))
    r = client.get(f"/api/downloads/{job}/file?inline=1", headers={"Range": "bytes=0-1"})
    assert r.status_code == 206 and r.content == b"da"


def test_get_job(client: TestClient, db_session_visible: Session) -> None:
    job = _add(db_session_visible, "queued")
    r = client.get(f"/api/downloads/{job}")
    assert r.status_code == 200 and r.json()["id"] == job
    r = client.get("/api/downloads/999999")
    assert r.status_code == 404 and r.json()["error"]["code"] == "not_found"
```

- [ ] **Step 2: Write the failing web unit tests**

```ts
test("watch route", () => {
  expect(parseHash("#/watch/12")).toEqual({ name: "watch", id: 12 });
  expect(parseHash("#/watch/x")).toEqual({ name: "library" });
  expect(parseHash("#/watch/")).toEqual({ name: "library" });
  expect(parseHash("#/watch/1.5")).toEqual({ name: "library" });
  expect(href({ name: "watch", id: 12 })).toBe("#/watch/12");
  expect(section({ name: "watch", id: 12 })).toBe("library");
});
```

```ts
test("saveMode", () => {
  expect(saveMode(10, true)).toBe("share");
  expect(saveMode(SHARE_LIMIT_BYTES, true)).toBe("share");
  expect(saveMode(SHARE_LIMIT_BYTES + 1, true)).toBe("link");
  expect(saveMode(0, true)).toBe("link");
  expect(saveMode(null, true)).toBe("link");
  expect(saveMode(10, false)).toBe("link");
});
test("fileName", () => {
  expect(fileName("Seeded video", "mp4")).toBe("Seeded video.mp4");
  expect(fileName("a/b: c?", "webm")).toBe("a-b- c-.webm");
  expect(fileName("  ", "mp4")).toBe("download.mp4");
  expect(fileName(null, null)).toBe("download");
});
```

- [ ] **Step 3: Run them and see them fail**, then implement the server routes, the router, `save.ts`, `Watch.svelte`, the `JobCard` links and the `DESIGN.md` player note. Run `pnpm typegen`.

Run: `cd apps/server && uv run pytest tests/api/test_library_api.py -v` and `pnpm test`
Expected: first FAIL, then PASS.

- [ ] **Step 4: Add e2e tests in `library.spec.ts`, above "delete in library"** (that test deletes the seeded video, and tests in a file run in order):
  - **Player:** in the library, click the "Seeded video" title link. The URL matches `#/watch/\d+`. A `video` element's `src` ends in `file?inline=1`. "Save" and "Delete" are visible. Dispatch an `error` event on the video with `page.evaluate`, and expect the VLC message. (The seeded file is 4 bytes and not a real video, so the browser may fire `error` on its own. The test passes either way.)
  - **Save as a link:** `page.addInitScript(() => Object.defineProperty(navigator, "canShare", { value: undefined }))`. Save is a link with a `download` attribute and an `href` ending in `/file`.
  - **Save through the share sheet:** an init script stubs `navigator.canShare = () => true`. It also stubs `navigator.share = (d) => { window.__shared = d.files.map((f) => [f.name, f.size, f.type]); return Promise.resolve(); }`. Click "Save", then "Share file". `window.__shared` equals `[["Seeded video.mp4", 4, "video/mp4"]]`.
  - **Missing job:** `#/watch/999999` shows "This download no longer exists."

- [ ] **Step 5: Run `pnpm check && pnpm e2e`.** Expected: PASS.

- [ ] **Step 6: Commit** `feat: in-app player with Save`

### Task 11: Installable PWA

**Files:**

- Modify: `apps/web/package.json` (dev dependencies `vite-plugin-pwa` ^2.0.0, `workbox-core`, `workbox-precaching` and `workbox-routing` ^7.4.1), `pnpm-lock.yaml`
- Modify: `apps/web/vite.config.ts` (`VitePWA`)
- Create: `apps/web/src/sw.ts`, `apps/web/src/lib/share.ts`, `apps/web/src/share-redirect.ts`
- Create: `apps/web/pwa-assets.config.js`, plus the generated `apps/web/public/pwa-64x64.png`, `pwa-192x192.png`, `pwa-512x512.png`, `maskable-icon-512x512.png`, `apple-touch-icon-180x180.png`, `favicon.ico`
- Modify: `apps/web/index.html`, `apps/web/src/main.ts` (first import: `./share-redirect.ts`)
- Modify: `PRODUCT.md` (platform: web plus phone PWA; remove PWA and playback from out of scope), `README.md` (install on iPhone)
- Test: `apps/web/test/share.test.ts`, `apps/web/e2e/pwa.spec.ts`

**Interfaces:**

- Produces:
  - `VitePWA` options: `strategies: "injectManifest"`, `srcDir: "src"`, `filename: "sw.ts"`, `registerType: "autoUpdate"`, `injectRegister: "auto"`, `includeAssets: ["favicon.ico", "apple-touch-icon-180x180.png"]`. There are no `devOptions`, so the service worker runs only in the built app (`pnpm start`, e2e, Docker), not under `pnpm dev`.
  - Manifest:
    - `name` and `short_name` "YourTube", `display: "standalone"`, `start_url: "/"`, `scope: "/"`
    - `theme_color` and `background_color` `#0b0b0c`
    - icons `pwa-64x64.png`, `pwa-192x192.png`, `pwa-512x512.png`, plus `maskable-icon-512x512.png` with `purpose: "maskable"`
    - `share_target: { action: "/", method: "GET", params: { url: "share", text: "text", title: "title" } }`
  - `sw.ts` (verified in a throwaway build):

    ```ts
    /// <reference lib="webworker" />
    import { clientsClaim } from "workbox-core";
    import {
      cleanupOutdatedCaches,
      createHandlerBoundToURL,
      precacheAndRoute,
    } from "workbox-precaching";
    import { NavigationRoute, registerRoute } from "workbox-routing";

    declare let self: ServiceWorkerGlobalScope;

    self.skipWaiting();
    clientsClaim();
    cleanupOutdatedCaches();
    precacheAndRoute(self.__WB_MANIFEST);
    registerRoute(
      new NavigationRoute(createHandlerBoundToURL("index.html"), {
        denylist: [/^\/api\//, /^\/health/],
      }),
    );
    ```

    Push handlers come in Task 21.

  - `sharedUrl(search: string): string | null`: the first `http(s)` URL (`/https?:\/\/\S+/`) found in the `share`, then `text`, then `title` params. `text` may hold words around the URL.
  - `share-redirect.ts` is a side-effect module. When `sharedUrl(location.search)` returns a URL, it calls `history.replaceState(null, "", "/" + href({ name: "fetch", urls: url }))`. `main.ts` imports it **first**, before `App.svelte` (which pulls in `router.svelte.ts`, and that reads `location.hash` when it loads). Add a one-line comment saying why the order matters.
  - `pwa-assets.config.js` (a plain object; it has no import, because the generator isn't a dependency):

    ```js
    const dark = { fit: "contain", background: "#0b0b0c" };
    export default {
      headLinkOptions: { preset: "2023" },
      preset: {
        transparent: { sizes: [64, 192, 512], favicons: [[48, "favicon.ico"]] },
        maskable: { sizes: [512], resizeOptions: dark },
        apple: { sizes: [180], resizeOptions: dark },
      },
      images: ["public/favicon.svg"],
    };
    ```

  - `index.html`:
    - `<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">`
    - `theme-color` `#0b0b0c` (`media="(prefers-color-scheme: dark)"`) and `#ffffff` (`media="(prefers-color-scheme: light)"`)
    - `apple-mobile-web-app-capable` and `mobile-web-app-capable` `yes`, `apple-mobile-web-app-status-bar-style` `black-translucent`, `apple-mobile-web-app-title` "YourTube"
    - `<link rel="icon" href="/favicon.ico" sizes="48x48">` next to the existing SVG icon, and `<link rel="apple-touch-icon" href="/apple-touch-icon-180x180.png">`
    - Keep the inline theme script as the first `<script>` (`test/prepaint.test.ts` reads it). The plugin injects the manifest link and `registerSW.js` into the built `index.html` only.

- [ ] **Step 1: Write the failing unit tests**

```ts
test("sharedUrl", () => {
  expect(sharedUrl("?share=https%3A%2F%2Fyoutu.be%2Fa")).toBe(
    "https://youtu.be/a",
  );
  expect(sharedUrl("?text=Watch%20this%20https%3A%2F%2Fyoutu.be%2Fb%20!")).toBe(
    "https://youtu.be/b",
  );
  expect(sharedUrl("?title=x")).toBeNull();
  expect(sharedUrl("")).toBeNull();
});
```

- [ ] **Step 2: Run it and see it fail**, then implement `share.ts`, `share-redirect.ts`, the `main.ts` import, the plugin config, `sw.ts`, the icons and `index.html`. Generate the icons once with `cd apps/web && pnpm dlx @vite-pwa/assets-generator@2.0.0` (it reads `pwa-assets.config.js`). Commit the config, the PNGs and `favicon.ico`. Open `apple-touch-icon-180x180.png` and check that it is the red play-circle on near-black, not white.

- [ ] **Step 3: Write `e2e/pwa.spec.ts`**
  - `GET /manifest.webmanifest` is JSON with `name == "YourTube"` and `share_target.action == "/"`.
  - Opening `/?share=https%3A%2F%2Fe2e.test%2Fvideo` lands on `#/fetch/https%3A%2F%2Fe2e.test%2Fvideo` with no `?share` left in the URL, and the "E2E Video" heading is visible. That heading proves the first render was the fetch route.
  - `await page.evaluate(() => navigator.serviceWorker.ready.then((r) => !!r.active))` is `true`. Then `page.reload()`, and `navigator.serviceWorker.controller` is set.
  - From that controlled page, `page.goto("/api/queue")` has a `content-type` containing `application/json`, not `text/html`.

- [ ] **Step 4: Run `pnpm check && pnpm e2e`.** Expected: PASS (the whole suite, since every page now has a service worker).

- [ ] **Step 5: Docs.** In `PRODUCT.md`: the platform is web plus a phone PWA, and the phone joins the users. In-browser playback and PWA leave "Not in scope". Offline, live push and the rest stay. In `README.md`:
  - Install on iPhone: open the Tailscale URL in Safari → Share → Add to Home Screen.
  - Android and desktop: browser install. The installed app shows up as a share-sheet target.

- [ ] **Step 6: Commit** `feat(web): installable PWA with share target`

### Task 12: Paste button on phones

**Files:**

- Modify: `apps/web/src/components/TopBar.svelte`
- Modify: `README.md` (copy-paste flow; optional iOS Shortcut)
- Test: `apps/web/e2e/phone.spec.ts` (new file, `test.use({ viewport: { width: 390, height: 844 }, hasTouch: true })`), `apps/web/e2e/shell.spec.ts`

**Interfaces:**

- Produces: below 768 px (`md:hidden`), while the URL field is empty (`{#if !field}`), a "Paste" button sits beside the field (at least 44 px tall). On tap it calls `navigator.clipboard.readText()` and puts the text in the field. If that rejects, or the text is blank, it focuses the field. It never fetches by itself. At 768 px and above it is `display: none`, so it is not in the accessibility tree. (`body` still has `min-width: 960px` until Phase 6. The media query follows the viewport, so the button still shows at 390 px.)

- [ ] **Step 1: Write the failing e2e tests**

```ts
test("Paste fills the field without fetching", async ({ page, context }) => {
  await context.grantPermissions(["clipboard-read", "clipboard-write"]);
  await page.goto(`${APP}#/`);
  await page.evaluate(() =>
    navigator.clipboard.writeText("https://youtu.be/a"),
  );
  await page.getByRole("button", { name: "Paste" }).click();
  await expect(
    page.getByRole("textbox", { name: "Video or playlist URL" }),
  ).toHaveValue("https://youtu.be/a");
  await expect(page).toHaveURL(/#\/$/);
  await expect(page.getByRole("button", { name: "Paste" })).toBeHidden();
});
test("Paste falls back to focusing the field", async ({ page }) => {
  await page.addInitScript(() => {
    Object.defineProperty(navigator, "clipboard", {
      value: { readText: () => Promise.reject(new Error("denied")) },
    });
  });
  await page.goto(`${APP}#/`);
  await page.getByRole("button", { name: "Paste" }).click();
  await expect(
    page.getByRole("textbox", { name: "Video or playlist URL" }),
  ).toBeFocused();
});
```

Also add a desktop test in `shell.spec.ts`: at 1440 px, `page.getByRole("button", { name: "Paste" })` has count 0.

- [ ] **Step 2: Run them and see them fail**, then implement the button.

- [ ] **Step 3: README.** Describe the copy-paste flow. Add the optional iOS Shortcut "Send to YourTube": Receive URLs from Share Sheet → URL Encode → Open URL `https://<host>/#/fetch/<encoded>`. Say that no app code depends on it.

- [ ] **Step 4: Run `pnpm check && pnpm e2e`, then commit** `feat(web): Paste button for phones`

---

## Done when

- Every task above is committed and `pnpm check && pnpm e2e` pass on the branch.
- The usable result above works by hand on the iPhone over `https://<host>.<tailnet>.ts.net`, including Save to Photos for a file under 500 MB and the download link for one over it.
