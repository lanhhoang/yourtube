# yourtube server

FastAPI backend for yourtube: lifespan-managed Alembic migrations, a SQLite-backed queue and library, worker-thread downloads with yt-dlp, a JSON API under `/api`, and the built Svelte app from `apps/web/dist`.

Run everything from the repo root with `pnpm` (see the [root README](../../README.md)), or from this directory with `uv`.

## Commands

| From the repo root | From `apps/server`                                 | What it does                                     |
| ------------------ | -------------------------------------------------- | ------------------------------------------------ |
| `pnpm dev`         | `uv run uvicorn app.main:app --reload`             | Dev server on http://127.0.0.1:8000              |
| `pnpm start`       | `uv run uvicorn app.main:app`                      | Server without reload                            |
| `pnpm check`       | `uv run pytest --cov=app --cov-fail-under=50` etc. | ruff, ruff format, ty, pytest with coverage gate |

First-time setup: `uv sync --dev` in this directory.

## Configuration

All settings are environment variables prefixed with `YT_`, read from the process environment and from `.env` at the **repo root** (see `app/config.py`). Relative paths resolve against the repo root, not the working directory, so `./tmp/data` always means `<repo>/tmp/data`. An empty value means "use the default".

| Variable            | Default                        | Description                                       |
| ------------------- | ------------------------------ | ------------------------------------------------- |
| `YT_HOST`           | `127.0.0.1`                    | Bind address                                      |
| `YT_PORT`           | `8000`                         | Bind port                                         |
| `YT_DATA_DIR`       | `./tmp/data`                   | Database and runtime data directory               |
| `YT_DOWNLOADS_DIR`  | `./tmp/downloads`              | Completed download output directory               |
| `YT_COOKIES_PATH`   | _(unset)_                      | Cookies file passed to yt-dlp                     |
| `YT_PROXY_URL`      | _(unset)_                      | Proxy passed to yt-dlp                            |
| `YT_DATABASE_URL`   | _(derived from `YT_DATA_DIR`)_ | SQLAlchemy URL; relative `sqlite:///` paths resolve against the repo root |
| `YT_WEB_DIST_DIR`   | `apps/web/dist`                | Built web app directory                         |
| `YT_LOG_LEVEL`      | `INFO`                         | Logging level                                     |
| `YT_WORKERS`        | `1`                            | Worker thread count                               |

Downloads folder, cookies path and proxy can also be changed on the Settings page; saved relative paths resolve against the repo root too.

## Layout

```
apps/server/
├── app/
│   ├── main.py       — FastAPI app, lifespan, /health endpoint
│   ├── config.py     — pydantic-settings model, REPO_ROOT, resolve_repo_path()
│   ├── db.py         — Engine, session factory, SQLite pragmas
│   ├── models.py     — SQLAlchemy ORM models
│   ├── schemas.py    — Pydantic request/response contracts
│   ├── api/          — JSON routes under /api, SPA serving, error bodies
│   └── services/     — Queue, downloader, library, and settings logic
├── alembic/          — Schema migrations (env.py, versions/)
├── alembic.ini
├── pyproject.toml    — Dependencies and ruff / ty / pytest config
├── uv.lock
└── tests/            — api/, unit/ and integration/, plus conftest.py with migrated DB fixtures
```

## Testing

```bash
uv run pytest
```

Tests use a temporary SQLite database built by Alembic migrations, so no setup is needed. `YT_WORKERS_ENABLED=0` is set by `tests/conftest.py` so the worker pool doesn't race with test assertions.
