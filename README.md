# yourtube

> There are many video-sharing platforms, but this one is yours.

Self-hosted YouTube video downloader with a web UI, persistent queue, and library management.

## Status

Current features:

- FastAPI app with lifespan-managed Alembic migrations and `/health`
- HTMX server-rendered web UI for lookup, queue, library, and settings
- Persistent SQLite-backed queue and library state
- Worker-thread download execution with cancellation and startup recovery
- Detached-safe queue claiming (Phase 5): the worker pool never holds a
  session-bound ORM `Download` instance across the claim boundary
- yt-dlp JS runtime pinned to Node.js 22 (Phase 5): the shipped Docker
  image bundles a supported Node runtime and packaged EJS solver so
  YouTube extraction works out of the box
- Lightweight runtime diagnostics (Phase 5): the settings page shows a
  warning panel when the environment is degraded (missing Node.js,
  workers disabled)
- Paginated YouTube playlist preview with page-local selection, per-video
  formats, and independent queue jobs
- Docker and Docker Compose packaging for local deployment

## Quick Start

```bash
cp .env.example .env     # adjust paths as needed
pnpm install             # workspace root
(cd apps/server && uv sync --dev)   # install Python dependencies
pnpm dev                 # http://127.0.0.1:8000
```

Open [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health).

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
pnpm check               # ruff, ty, pytest with coverage
```

## License

MIT
