# yourtube

> There are many video-sharing platforms, but this one is yours.

Self-hosted YouTube video downloader with a web UI, persistent queue, and library management.

## Status

Phase 1 (scaffold) complete:

- FastAPI skeleton with lifespan-managed startup
- SQLAlchemy 2.x ORM models (`Download`, `Setting`)
- Pydantic request/response schemas (`app/schemas.py`)
- Alembic-owned schema (baseline migration creates `downloads` and `settings` tables)
- `GET /health` — liveness probe with database reachability check
- Pytest fixtures backed by a migrated temporary SQLite database
- Configuration via environment variables / `.env` file (`YT_*` prefix)

## Quick Start

```bash
cp .env.example .env     # adjust paths as needed
uv sync                  # install dependencies
uv run uvicorn app.main:app --reload
```

Open [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health).

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
│   ├── routes/       — Route handlers (forthcoming)
│   └── services/     — Business logic (forthcoming)
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
