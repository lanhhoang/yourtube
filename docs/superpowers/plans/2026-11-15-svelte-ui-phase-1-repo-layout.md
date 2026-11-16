# Phase 1: Repo layout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The existing app (old UI) runs from `apps/server` with `pnpm dev` / `pnpm start` from the repo root, on the latest versions of its Python dependencies, uses the same `.env` and `tmp/` data as before, `pnpm check` runs every server check, CI is green, and `docker compose up` still serves it on port 8000.

**Parent plan:** `docs/superpowers/plans/2026-11-15-svelte-ui.md`, section "Phase 1: Repo layout". The tasks below are copied from it verbatim. If they ever differ, the parent plan wins.

**Phase index:** `docs/superpowers/plans/2026-11-15-svelte-ui-phases.md`

**Spec:** `docs/superpowers/specs/2026-11-15-svelte-ui-design.md`

**Prerequisites:** none.

**Tasks:** Task 1.1 Move the server into `apps/server` with root-relative config, Task 1.2 Workspace root, scripts, CI and Docker for the new layout, Task 1.3 Bump the server's Python dependencies to latest.

## Architecture and stack (from the parent plan)

**Architecture:** The FastAPI backend moves to `apps/server` and gains JSON routes under `/api`. The Svelte app lives in `apps/web` and calls them through `openapi-fetch`, with types generated from FastAPI's OpenAPI schema and checked for drift. In production FastAPI also serves the built SPA, so it is still one process on one port. The work is built feature by feature: each phase adds the API and the screens for one feature, and the old UI keeps working until the last phase deletes it.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2, Alembic, yt-dlp, uv, ruff, ty, pytest. Node 24, pnpm 12.9.1, Svelte 5 (runes), Vite 8, `@sveltejs/vite-plugin-svelte` 7, Tailwind CSS 4 (`@tailwindcss/vite`), TypeScript (`svelte-check --tsgo`), Biome 2.6, Vitest 5, Playwright 1.65, `openapi-typescript` 7, `openapi-fetch` 0.17, `@fontsource`.

## Global Constraints (from the parent plan)

- **Old UI keeps working until Phase 6.** No phase before 6 removes or changes the behaviour of a Jinja page, an HTMX route or `/downloads/{id}/file`. The full old test suite stays green until Phase 6 deletes the old tests together with the old code.
- **Where the SPA is served:** in Phases 2–5 the built SPA is served at `/app` (hash routes such as `/app#/queue`), because the Jinja pages still own `/`, `/queue`, `/library` and `/settings`. Phase 6 serves it at `/`. Vite `base` stays `/`; assets live at `/assets/*` and do not collide with the old `/static/*`.
- **SPA serving rules (spec):** real files in `apps/web/dist` by path; `index.html` for app paths; 404 for a missing path that has a file extension; 404 JSON error for any unknown `/api/...` path. `/health` stays at `/health`.
- **Error body** for every `/api` error: `{"error": {"code": str, "message": str}}`. The web app may show `message`. Old HTML routes keep FastAPI's default errors.
- **Pydantic schemas in `app/schemas.py` are the only response models.** Routes never return ORM rows.
- **Quality caps:** exactly `best`, `2160`, `1440`, `1080`, `720`, `480`, `audio`. Default in the UI: `1080` ("Up to 1080p"). The cap compares against the **short side** (min of width and height). Exact format ids win over the cap.
- **Batch limit:** 500 entries per fetch; extra entries are dropped and counted in `skipped`, which the UI shows as "Skipped N".
- **Playlist checking:** from the browser, at most `CHECK_CONCURRENCY = 2` lookups at a time (the spec allows 2–3; 2 because playlist 403s were just fixed). Only selected entries are looked up. Leaving the page stops checking.
- **Theme:** `dark` (default) | `light` | `system`, in `localStorage` key `theme`, applied by an inline script in `index.html` before first paint. Not `system` by default.
- **Session storage key for completion toasts:** `yt-seen-completed-jobs` (same key as today, ids as strings).
- **No runtime CDN.** Fonts come from `@fontsource` packages; nothing loads from Google Fonts.
- **Red is the only accent.** Amber only for "below your cap"; an error tone for failures. Exact values come from `DESIGN.md` and must pass WCAG AA in both themes.
- **Computer only.** Design at 1280 and 1440 widths. Narrow windows may scroll but must not overlap or clip controls.
- **Not used:** Paraglide, PWA, SvelteKit, WebSocket/SSE, server-side playlist checking, taste-skill (`design-taste-frontend`) for app screens.
- **`.env` stays at the repo root.** `apps/server/app/config.py` reads it by absolute path. Relative `YT_DATA_DIR` / `YT_DOWNLOADS_DIR` / `YT_COOKIES_PATH` resolve against the repo root, so `./tmp/data` keeps meaning `<repo>/tmp/data`.
- **Checks before every commit (from Phase 2 on):** `pnpm check` must pass. In Phase 1 that is `pnpm check` with only server checks.
- **UI work:** before any edit to a `.svelte` file or `app.css`, read impeccable's `reference/craft-floor.md` (`/Users/lanh/.agents/skills/impeccable/`) and follow `PRODUCT.md` and `DESIGN.md` at the repo root.
- **Coverage gate:** `pytest --cov=app --cov-fail-under=50` stays in `pnpm check` and CI.

## Review Focus for this phase

None of the parent plan's Review Focus items is owned by this phase. Still read the parent's list: earlier phases' tests must stay green.

## File Structure

See the parent plan's "File Structure" for the final layout. This phase touches only the files named in its tasks' **Files** blocks.

---

## Phase 1: Repo layout

**Usable result:** the existing app (old UI) runs from `apps/server` with `pnpm dev` / `pnpm start` from the repo root, on the latest versions of its Python dependencies, uses the same `.env` and `tmp/` data as before, `pnpm check` runs every server check, CI is green, and `docker compose up` still serves it on port 8000.

**Baseline before Phase 1:** `uv run pytest -q` → 240 passed. Phase 1 adds 7 tests, so the end state is 247 passed. (Dry-run of Tasks 1.1–1.3 on 2026-11-15 confirmed every step and count below.)

### Task 1.1: Move the server into `apps/server` with root-relative config

**Files:**

- Move (`git mv`): `app/`, `alembic/`, `alembic.ini`, `tests/`, `pyproject.toml`, `uv.lock` → `apps/server/`
- Modify: `apps/server/app/config.py`, `apps/server/app/services/settings.py`, `apps/server/app/services/library.py`, `apps/server/app/routes/pages.py`
- Modify (path fix): `apps/server/tests/unit/test_downloader_runtime_resolution.py`
- Test: `apps/server/tests/test_config.py`, `apps/server/tests/unit/test_settings_runtime_resolution.py`, `apps/server/tests/unit/test_library.py`, `apps/server/tests/integration/test_pages.py`

**Interfaces:**

- Produces: `app.config.REPO_ROOT: Path` (= `Path(__file__).resolve().parents[3]`); `app.config.resolve_repo_path(value: str | Path) -> Path` (absolute paths unchanged, relative paths joined onto `REPO_ROOT`); `Settings.web_dist_dir: Path` (default `REPO_ROOT / "apps/web/dist"`, env `YT_WEB_DIST_DIR`; unused until Phase 2).
- Behaviour: every relative path the app reads — from `.env`/environment (`YT_DATA_DIR`, `YT_DOWNLOADS_DIR`, `YT_COOKIES_PATH`), from the Settings page (`downloads_dir`, `cookies_path` rows in the `settings` table), and from `downloads.file_path` of older rows — resolves against the repo root, exactly as it did when the process ran from the repo root. Nothing is rewritten in the database.

- [ ] **Step 1: Move the files**

```bash
mkdir -p apps/server
git mv app alembic alembic.ini tests pyproject.toml uv.lock apps/server/
rm -rf .venv && (cd apps/server && uv sync --dev --frozen)
```

The paths in `main.py`, `routes/pages.py`, `alembic/env.py`, `alembic.ini` (`%(here)s`) and `tests/conftest.py` are relative to their own file and need no change.

- [ ] **Step 2: Fix the one test that reads a repo-root file**

`tests/unit/test_downloader_runtime_resolution.py` (`test_dockerfile_bundles_supported_node_runtime`) reads the Dockerfile via `parents[2]`; after the move the Dockerfile is four levels up. Change `parents[2] / "Dockerfile"` → `parents[4] / "Dockerfile"`.

Run: `cd apps/server && uv run pytest -q | tail -1`
Expected: `240 passed`.

- [ ] **Step 3: Write the failing config tests** — append to `apps/server/tests/test_config.py` and extend its imports to `from pathlib import Path` and `from app.config import REPO_ROOT, Settings, resolve_repo_path, settings`:

```python
def test_env_file_is_repo_root():
    assert Settings.model_config["env_file"] == REPO_ROOT / ".env"
    assert (REPO_ROOT / "apps" / "server" / "app" / "config.py").exists()


def test_relative_dirs_resolve_against_repo_root(monkeypatch):
    monkeypatch.setenv("YT_DATA_DIR", "./tmp/data")
    monkeypatch.setenv("YT_DOWNLOADS_DIR", "tmp/downloads")
    monkeypatch.setenv("YT_COOKIES_PATH", "cookies.txt")
    monkeypatch.delenv("YT_DATABASE_URL", raising=False)
    s = Settings()
    assert s.data_dir == REPO_ROOT / "tmp" / "data"
    assert s.downloads_dir == REPO_ROOT / "tmp" / "downloads"
    assert s.cookies_path == REPO_ROOT / "cookies.txt"
    assert s.database_url == f"sqlite:///{REPO_ROOT / 'tmp' / 'data' / 'yourtube.db'}"


def test_absolute_dirs_are_kept(monkeypatch, tmp_path):
    monkeypatch.setenv("YT_DATA_DIR", str(tmp_path))
    assert Settings().data_dir == tmp_path


def test_resolve_repo_path():
    assert resolve_repo_path("tmp/downloads/a.mp4") == REPO_ROOT / "tmp/downloads/a.mp4"
    assert resolve_repo_path("/abs/a.mp4") == Path("/abs/a.mp4")
```

Run: `cd apps/server && uv run pytest tests/test_config.py -v`
Expected: FAIL (`ImportError: cannot import name 'REPO_ROOT'`).

- [ ] **Step 4: Update `apps/server/app/config.py`**

```python
REPO_ROOT = Path(__file__).resolve().parents[3]

_RELATIVE_TO_ROOT = ("data_dir", "downloads_dir", "cookies_path")


def resolve_repo_path(value: str | Path) -> Path:
    """Return ``value`` as a path, joining relative paths onto ``REPO_ROOT``."""
    path = Path(value)
    return path if path.is_absolute() else REPO_ROOT / path
```

In `Settings`: `env_file=REPO_ROOT / ".env"`; `data_dir: Path = REPO_ROOT / "tmp/data"`; `downloads_dir: Path = REPO_ROOT / "tmp/downloads"`; add `web_dist_dir: Path = REPO_ROOT / "apps/web/dist"`. In the existing `mode="before"` validator, before the `database_url` early return:

```python
        for key in _RELATIVE_TO_ROOT:
            if data.get(key):
                data[key] = resolve_repo_path(data[key])

        if data.get("database_url"):
            return data

        data_dir = data.get("data_dir", REPO_ROOT / "tmp/data")
        data["database_url"] = f"sqlite:///{data_dir / 'yourtube.db'}"
```

An explicit `YT_DATABASE_URL` stays untouched (tests rely on it).

Run: `cd apps/server && uv run pytest tests/test_config.py -v`
Expected: PASS (6 tests).

- [ ] **Step 5: Write the failing tests for stored relative paths**

`tests/unit/test_settings_runtime_resolution.py` (add `from app.config import REPO_ROOT`):

```python
def test_resolve_runtime_settings_resolves_relative_paths_against_repo_root(db_session) -> None:
    set_settings_batch(db_session, {"downloads_dir": "tmp/saved", "cookies_path": "./cookies.txt"})

    resolved = resolve_runtime_settings(db_session)

    assert resolved.downloads_dir == REPO_ROOT / "tmp" / "saved"
    assert resolved.cookies_path == REPO_ROOT / "cookies.txt"
```

`tests/unit/test_library.py` (add `from app.config import REPO_ROOT`):

```python
def test_delete_from_library_resolves_relative_file_path(db_session: Session) -> None:
    """A relative ``file_path`` from an older row is resolved against the repo root."""
    row = enqueue_download(db_session, _make("https://example.com/rel", title="Rel"))
    _mark_done(row, db_session)
    db_session.execute(
        Download.__table__.update()
        .where(Download.id == row.id)
        .values(file_path="tmp/downloads/rel.mp4")
    )
    db_session.expire(row)

    with patch("app.services.library.os.remove") as remove:
        success, _ = delete_from_library(db_session, row.id)

    assert success is True
    remove.assert_called_once_with(REPO_ROOT / "tmp" / "downloads" / "rel.mp4")
```

`tests/integration/test_pages.py`:

```python
def test_download_file_resolves_relative_path_against_repo_root(
    db_session_visible, monkeypatch, tmp_path: Path
) -> None:
    (tmp_path / "tmp" / "downloads").mkdir(parents=True)
    (tmp_path / "tmp" / "downloads" / "rel.mp4").write_bytes(b"rel")
    monkeypatch.setattr("app.config.REPO_ROOT", tmp_path)
    row = Download(
        url="https://example.com/rel",
        status="done",
        progress=100.0,
        file_path="tmp/downloads/rel.mp4",
    )
    db_session_visible.add(row)
    db_session_visible.commit()
    db_session_visible.refresh(row)

    with TestClient(app) as client:
        response = client.get(f"/downloads/{row.id}/file")

    assert response.status_code == 200
    assert response.content == b"rel"
```

Run: `cd apps/server && uv run pytest -q tests/unit/test_settings_runtime_resolution.py tests/unit/test_library.py tests/integration/test_pages.py -k relative`
Expected: 3 FAIL.

- [ ] **Step 6: Resolve stored paths with `resolve_repo_path`**

- `app/services/settings.py` `resolve_runtime_settings`: `Path(stored["downloads_dir"])` → `resolve_repo_path(stored["downloads_dir"])`, same for `cookies_path`. Import `resolve_repo_path` from `app.config`.
- `app/services/library.py` `delete_from_library`: `os.remove(row.file_path)` → `os.remove(resolve_repo_path(row.file_path))`.
- `app/routes/pages.py` `/downloads/{job_id}/file`: `Path(row.file_path)` → `resolve_repo_path(row.file_path)`.

No other code reads a stored path (checked: `grep -rn "file_path\|downloads_dir\|cookies_path" app`). New downloads already store absolute paths, because `downloads_dir` is now absolute.

- [ ] **Step 7: Run the whole server suite**

Run: `cd apps/server && uv run ruff check . && uv run ruff format --check . && uv run ty check app tests && uv run pytest --cov=app --cov-fail-under=50`
Expected: all pass, `247 passed`. Run `uv run ruff check --fix . && uv run ruff format .` first if import order or line length is flagged.

- [ ] **Step 8: Commit**

```bash
git add -A apps/server && git commit -m "refactor: move server into apps/server with repo-root config"
```

### Task 1.2: Workspace root, scripts, CI and Docker for the new layout

**Files:**

- Create: `package.json`, `pnpm-workspace.yaml`, `.nvmrc`, `apps/server/package.json`
- Rename: `docker-compose.yml` → `compose.yaml`
- Modify: `Dockerfile`, `.dockerignore`, `.github/workflows/quality.yml`, `.gitignore`, `README.md` (paths and commands only)

**Interfaces:**

- Root `package.json`: `"private": true`, `"type": "module"`, `"packageManager": "pnpm@12.9.1"`, `"engines": {"node": ">=24.15.0"}`. Phase 1 scripts (Phase 2 replaces them with the final set):
  ```json
  {
    "dev": "pnpm --filter @app/server dev",
    "start": "pnpm --filter @app/server start",
    "check": "pnpm --filter @app/server check"
  }
  ```
- `apps/server/package.json` (name `@app/server`, private), final scripts:
  ```json
  {
    "dev": "uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000",
    "start": "uv run uvicorn app.main:app --host 127.0.0.1 --port 8000",
    "check": "uv run ruff check . && uv run ruff format --check . && uv run ty check app tests && uv run pytest --cov=app --cov-fail-under=50",
    "openapi": "uv run python -m app.openapi_export"
  }
  ```
  (`openapi` works from Task 2.1.)
- `pnpm-workspace.yaml`: `packages: ["apps/*"]`, `allowBuilds: { esbuild: true }`.
- `.nvmrc`: `24`.
- `.gitignore`: add `node_modules/` now (before the first `pnpm install`), so Step 7's `git add -A` cannot commit it. Phase 2 adds the remaining web entries.

- [ ] **Step 1: Create the root files, `apps/server/package.json`, and the `.gitignore` entry**, then `pnpm install` (writes `pnpm-lock.yaml`).

Run: `git status --short | grep node_modules`
Expected: no output.

- [ ] **Step 2: Verify the scripts**

Run: `pnpm check`
Expected: ruff, ty and pytest pass, `247 passed`, coverage ≥ 50.
Run: `pnpm start` then `curl -s localhost:8000/health` and open `http://localhost:8000/`
Expected: `{"status":"ok"}` and the old home page; the database is the one under `<repo>/tmp/data` (or whatever `.env` names), and `apps/server/tmp/` is **not** created.

- [ ] **Step 3: Update CI.** In `quality.yml` keep the ubuntu/macOS matrix, run `uv sync --dev --frozen` and every uv step with `working-directory: apps/server` (set `defaults.run.working-directory: apps/server` on the job). Point `setup-uv`'s cache at the moved lockfile: `cache-dependency-glob: apps/server/uv.lock`. (Phase 2 switches CI to `pnpm check`.)

- [ ] **Step 4: Update Docker.** Runtime `WORKDIR /app/apps/server`; copy `apps/server/{pyproject.toml,uv.lock,alembic.ini,alembic,app}` there; `uv sync --frozen --no-dev`; `ENV PATH="/app/apps/server/.venv/bin:${PATH}"`; CMD unchanged (`uvicorn app.main:app …`). `REPO_ROOT` resolves to `/app`. Keep the user's home at `/app` and `chown -R yourtube:yourtube /app`. `.dockerignore`: `tests/` → `apps/server/tests/`, add `**/node_modules/` and `**/.venv/`, `apps/web/dist/` stays allowed. Rename `docker-compose.yml` to `compose.yaml` and update its usage comment (and the `docker-compose.yml` mention in `README.md`). Compose sets absolute `YT_DATA_DIR=/data` / `YT_DOWNLOADS_DIR=/downloads`, so containers are unaffected by `REPO_ROOT`.

- [ ] **Step 5: Verify Docker**

Run: `docker compose build && docker compose up -d && sleep 5 && curl -fs localhost:8000/health && docker compose down`
Expected: `{"status":"ok"}`.

- [ ] **Step 6: README** — replace `uv run …` commands with `pnpm dev` / `pnpm check` / `cd apps/server && uv run …` and update paths. Note that relative `YT_*` paths in `.env` are resolved against the repo root. No other README changes.

- [ ] **Step 7: Commit**

```bash
git add -A && git commit -m "build: pnpm workspace root, CI and Docker for apps/server layout"
```

### Task 1.3: Bump the server's Python dependencies to latest

Done here, before any `/api` code exists, so the old test suite proves behaviour is unchanged and Phase 2's generated OpenAPI types are built on the versions that ship.

**Files:**

- Modify: `apps/server/pyproject.toml`, `apps/server/uv.lock`, `Dockerfile` (uv image tag)
- Modify only if the upgrade requires it: files under `apps/server/app/` and `apps/server/tests/` flagged by the checks

**Interfaces:**

- No interface changes. Every `>=` floor in `[project].dependencies` and `[dependency-groups].dev` is raised to the latest release on PyPI at execution time. For reference, latest on 2026-11-15 (re-verified): `fastapi 0.163.1`, `pydantic 2.14.3`, `pydantic-settings 2.16.3`, `sqlalchemy 2.1.8`, `alembic 1.20.1`, `uvicorn 0.54.0`, `yt-dlp 2026.10.26`, `httpx2 2.16.0`, `curl-cffi 0.17.0`, `jinja2 3.1.6`, `python-multipart 0.0.33`, `pytest 9.2.0`, `pytest-cov 7.1.0`, `ruff 0.17.5`, `ty 0.0.104`; uv `0.13.8`.
- `requires-python` stays `>=3.12,<4.0`; extras (`fastapi[standard]`, `uvicorn[standard]`, `yt-dlp[default]`) stay.
- `jinja2` and `python-multipart` are bumped too (the old UI needs them until Phase 6 removes them).
- Known break (found in dry run): `ty 0.0.104` renamed the rule `unresolved-attribute` to `missing-attribute` and fails on the old name. Rename it in `[tool.ty.rules]`; keep it `"ignore"`.

- [ ] **Step 1: Record the baseline**

Run: `cd apps/server && uv run pytest -q | tail -1`
Expected: `247 passed`.

- [ ] **Step 2: Raise the floors and relock**

Edit the floors in `pyproject.toml` (look each one up with `curl -s https://pypi.org/pypi/<name>/json`), rename the `ty` rule above, then:

```bash
cd apps/server && uv lock --upgrade && uv sync --dev
```

Expected: `uv tree --depth 1` shows each direct dependency at or above its new floor.

- [ ] **Step 3: Run the checks**

Run: `pnpm check`
Expected: PASS, `247 passed`. Fix what fails at its cause:

- New ruff rules or formatting: apply `uv run ruff check --fix . && uv run ruff format .`, review the diff.
- New ty diagnostics: fix the types; add to `[tool.ty.rules]` only with a one-line comment saying why.
- SQLAlchemy 2.1 / FastAPI / Pydantic deprecations or behaviour changes: follow their changelogs; don't pin a dependency back unless a fix isn't possible, and if you pin, write the reason next to it in `pyproject.toml`.
- Run `uv run pytest -W error::DeprecationWarning -q` once and fix warnings that come from our code (not third-party internals). (Dry run: clean.)

- [ ] **Step 4: Update uv in Docker and verify the image**

Change `COPY --from=ghcr.io/astral-sh/uv:0.7.21` to the latest uv tag (`0.13.8` on 2026-11-15). Fix the comment above it: CI does not pin uv, so say the tag tracks the latest release instead of "matches CI".

Run: `docker compose build && docker compose up -d && sleep 5 && curl -fs localhost:8000/health && docker compose down`
Expected: `{"status":"ok"}`.

- [ ] **Step 5: Smoke against real yt-dlp** (network, not in CI)

Run `pnpm start`, open `http://localhost:8000/`, fetch a short real video and download it.
Expected: it lands in the library, and the library's download link serves the file.

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "build(server): bump Python dependencies to latest"
```
