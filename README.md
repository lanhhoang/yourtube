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
- yt-dlp JS runtime pinned to Node.js (Phase 5): the shipped Docker
  image bundles `nodejs` and `npm` so YouTube extraction works out of
  the box
- Lightweight runtime diagnostics (Phase 5): the settings page shows a
  warning panel when the environment is degraded (missing Node.js,
  workers disabled)
- Docker and Docker Compose packaging for local deployment

## Quick Start

```bash
cp .env.example .env     # adjust paths as needed
uv sync                  # install dependencies
uv run uvicorn app.main:app --reload
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

Use absolute paths or `${HOME}` when setting these variables. Do not put a raw `~/...` path directly into `docker-compose.yml`.

If you switch to host UID/GID overrides for bind mounts, rebuild and recreate
the container so the latest image startup command is used:

```bash
YT_UID="$(id -u)" YT_GID="$(id -g)" YT_HOST_DATA_DIR="$HOME/Downloads/YouTube/data" YT_HOST_DOWNLOADS_DIR="$HOME/Downloads/YouTube/downloads" docker compose up -d --build --force-recreate
```

## Configuration

All settings are loaded from environment variables prefixed with `YT_`
(see `app/config.py`):

| Variable           | Default                        | Description                         |
| ------------------ | ------------------------------ | ----------------------------------- |
| `YT_HOST`          | `127.0.0.1`                    | Bind address                        |
| `YT_PORT`          | `8000`                         | Bind port                           |
| `YT_DATA_DIR`      | `./tmp/data`                   | Database and runtime data directory |
| `YT_DOWNLOADS_DIR` | `./tmp/downloads`              | Completed download output directory |
| `YT_DATABASE_URL`  | _(derived from `YT_DATA_DIR`)_ | SQLAlchemy database URL             |
| `YT_LOG_LEVEL`     | `INFO`                         | Logging level                       |
| `YT_WORKERS`       | `1`                            | Worker thread count                 |

## Project Structure

```
yourtube/
├── app/
│   ├── main.py       — FastAPI app, lifespan, /health endpoint
│   ├── config.py     — pydantic-settings model
│   ├── db.py         — Engine, session factory, SQLite pragmas
│   ├── models.py     — SQLAlchemy ORM models
│   ├── schemas.py    — Pydantic request/response contracts
│   ├── routes/       — JSON API and page route handlers
│   └── services/     — Queue, downloader, library, and settings logic
├── alembic/
│   ├── env.py
│   └── versions/     — Schema migrations
└── tests/
    ├── conftest.py   — Migrated DB fixtures
    ├── test_config.py
    ├── test_db.py
    └── test_health.py
```

## Testing

```bash
uv run pytest
```

Tests use a temporary SQLite database built by Alembic migrations — no manual
setup required.

## License

MIT
