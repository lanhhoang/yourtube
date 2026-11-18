# yourtube

> There are many video-sharing platforms, but this one is yours.

Self-hosted YouTube video downloader with a web UI, persistent queue, and library management.

## Features

- Svelte web app: paste a video or playlist URL, pick a quality, queue it, and find the file in the library
- Persistent SQLite-backed queue and library, with retry and dismiss for failed jobs
- Worker-thread downloads with cancellation and startup recovery
- Runtime diagnostics on the settings page when the environment is degraded (missing Node.js, workers disabled)
- One process, one port: FastAPI serves the JSON API under `/api` and the built web app
- Docker and Docker Compose packaging for local deployment

### Quality caps

Each job has a quality cap: `best`, `2160`, `1440`, `1080`, `720`, `480` or `audio`. The default is "Up to 1080p". The cap compares the short side of the video, so a vertical 1080×1920 video counts as 1080p. Choosing an exact format overrides the cap.

Capped video is saved as MP4: H.264 + AAC up to 1080p where YouTube offers it, VP9 SDR + AAC above, never HDR. Audio-only and exact format picks are unchanged.

### Playlists

A playlist fetch lists up to 500 entries. The browser checks each selected video against the cap, two lookups at a time, and flags any video that would download below it ("720p max") or is unavailable. "Add to queue" waits until every selected video has been checked. Leaving the page stops checking.

## Quick Start

```bash
cp .env.example .env                # adjust paths as needed
pnpm install                        # workspace root
(cd apps/server && uv sync --dev)   # Python dependencies
pnpm dev                            # UI on http://localhost:5173, API on http://127.0.0.1:8000
```

For one process on one port, build the web app and start the server:

```bash
pnpm build && pnpm start            # everything on http://127.0.0.1:8000
```

`pnpm dev` and `pnpm start` listen on localhost only. `.env` lives at the repo root. Details for each app: [`apps/web/README.md`](apps/web/README.md) and [`apps/server/README.md`](apps/server/README.md).

## Layout

```
apps/server/   FastAPI, yt-dlp, SQLite (see apps/server/README.md)
apps/web/      Svelte 5 + Vite + Tailwind app (see apps/web/README.md)
docs/          specs and plans
PRODUCT.md     who it is for and what it does
DESIGN.md      colours, type and layout rules for the web app
```

## Docker

Build and run with the bundled Docker setup:

```bash
docker compose up -d --build
curl -fsS http://localhost:8000/health
```

By default, Compose uses named volumes for `/data` and `/downloads`.

If you want to store data on your host, bind-mount directories explicitly:

```bash
mkdir -p "$HOME/Downloads/YouTube/data" "$HOME/Downloads/YouTube/downloads"

YT_UID="$(id -u)" YT_GID="$(id -g)" YT_HOST_DATA_DIR="$HOME/Downloads/YouTube/data" YT_HOST_DOWNLOADS_DIR="$HOME/Downloads/YouTube/downloads" docker compose up -d --build
```

This maps:

- `YT_DATA_DIR=/data` inside the container to `$HOME/Downloads/YouTube/data` on the host
- `YT_DOWNLOADS_DIR=/downloads` inside the container to `$HOME/Downloads/YouTube/downloads` on the host

Use absolute paths or `${HOME}` when setting these variables. Do not put a raw `~/...` path directly into `compose.yaml`.

If you switch to host UID/GID overrides for bind mounts, rebuild and recreate
the container so the latest image startup command is used:

```bash
YT_UID="$(id -u)" YT_GID="$(id -g)" YT_HOST_DATA_DIR="$HOME/Downloads/YouTube/data" YT_HOST_DOWNLOADS_DIR="$HOME/Downloads/YouTube/downloads" docker compose up -d --build --force-recreate
```

## Configuration

Settings are `YT_*` environment variables, read from `.env` at the repo root. Relative paths resolve against the repo root. See [`apps/server/README.md`](apps/server/README.md) for the full table, commands and project layout.

## Testing

```bash
pnpm check               # biome, svelte-check, vitest, typegen drift, ruff, ty, pytest with coverage
pnpm e2e                 # Playwright against the real server with yt-dlp stubbed
pnpm typegen             # regenerate the API types after changing a route or schema
```

`pnpm e2e` uses Playwright's Chromium (`pnpm --filter @app/web exec playwright install chromium`). Set `PW_CHANNEL=chrome` to use an installed Google Chrome instead.

## License

MIT
