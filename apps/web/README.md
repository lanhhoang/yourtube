# yourtube web

The Svelte app for yourtube. In production FastAPI serves the built files from `apps/web/dist`, so there is no separate web server.

Stack: Svelte 5 (runes), Vite, Tailwind CSS 4, TypeScript, `openapi-fetch`, Vitest, Playwright. Hash routing (`#/`, `#/queue`, `#/settings`). Design rules are in [`DESIGN.md`](../../DESIGN.md) and [`PRODUCT.md`](../../PRODUCT.md) at the repo root.

## Commands

Run from the repo root.

| Command          | What it does                                                                                      |
| ---------------- | ------------------------------------------------------------------------------------------------- |
| `pnpm dev`       | Vite on http://localhost:5173 plus the API on :8000. Vite proxies `/api` and `/health` to the API |
| `pnpm build`     | Build to `apps/web/dist`                                                                          |
| `pnpm test`      | Vitest unit tests (`test/`)                                                                       |
| `pnpm typecheck` | `svelte-check` and `tsc`                                                                          |
| `pnpm typegen`   | Regenerate `src/lib/api.gen.ts` from the server's OpenAPI schema                                  |
| `pnpm e2e`       | Playwright tests (`e2e/`)                                                                         |
| `pnpm check`     | Everything: format, lint, types, tests, typegen drift, server checks                              |

After you change a route or a Pydantic schema on the server, run `pnpm typegen` and commit `api.gen.ts`. `pnpm check` fails when it is out of date. Never edit it by hand.

## End-to-end tests

`pnpm e2e` builds the app and starts the real server on port 8100 through `apps/server/tests/e2e_server.py`. That file seeds two downloads and stubs yt-dlp, so the tests never reach YouTube. Install the browser once with `pnpm --filter @app/web exec playwright install chromium`, or set `PW_CHANNEL=chrome` to use an installed Google Chrome.

To look at the app with the same fake data, start that server by hand from the repo root. Keep the `YT_*` variables: without them it seeds rows and files into your real `tmp/data` and `tmp/downloads`.

```bash
pnpm build && rm -rf tmp/e2e && cd apps/server && \
  YT_DATA_DIR=$PWD/../../tmp/e2e/data YT_DOWNLOADS_DIR=$PWD/../../tmp/e2e/downloads \
  YT_DATABASE_URL=sqlite:///$PWD/../../tmp/e2e/data/yourtube.db \
  YT_PROXY_URL= YT_COOKIES_PATH= YT_WORKERS_ENABLED=1 \
  uv run uvicorn tests.e2e_server:app --host 127.0.0.1 --port 8100
```

Then open http://127.0.0.1:8100/ and fetch `https://e2e.test/video` for a single video or `https://e2e.test/playlist` for a playlist.

## Source layout

```
src/
├── main.ts          entry
├── App.svelte       shell: top bar, left rail, route switch, completion toasts
├── app.css          Tailwind theme tokens (see DESIGN.md)
├── routes/          Library, Queue, Settings, Fetch (single video or playlist)
├── components/      cards, quality select, override panel, toasts, rail, top bar
└── lib/             API client, router, theme, playlist checker, helpers
```

`lib/api.ts` wraps the typed client. Logic that can run without a browser lives in `lib/` with a matching test in `test/`.

## Conventions

- The theme (`dark`, `light`, `system`) is stored in `localStorage` under `theme` and applied by an inline script in `index.html` before first paint.
- Completion toasts remember what they have shown in `sessionStorage` under `yt-seen-completed-jobs`.
- Fonts come from `@fontsource-variable/inter`. Nothing loads from a CDN at runtime.
- Desktop only: designed at 1280 and 1440 px wide.
