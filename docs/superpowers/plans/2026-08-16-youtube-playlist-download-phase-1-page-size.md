# YouTube Playlist Download — Phase 1: Page-Size Setting Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this phase task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a persisted and validated playlist preview page-size setting without changing download behavior.

**Architecture:** Extend the existing key/value settings catalog and runtime settings object. Render the setting in the existing Settings page so later phases can consume one typed value without adding configuration infrastructure.

**Tech Stack:** Python 3.12, FastAPI, Jinja2, SQLAlchemy, pytest.

**Spec:** `docs/superpowers/specs/2026-08-16-youtube-playlist-download-design.md`

**Parent plan:** `docs/superpowers/plans/2026-08-16-youtube-playlist-download-parent.md`

## Global Constraints

- Use settings key `playlist_page_size` with default string value `"20"`.
- Accept only integer values from `1` through `50`.
- Resolve the runtime value as an integer clamped to `1..50`; malformed persisted values fall back to `20`.
- Preserve atomic settings updates and all existing settings behavior.
- Do not add a migration or dependency.

## Files

- Modify: `app/services/settings.py`
- Modify: `app/routes/pages.py`
- Modify: `app/templates/partials/settings_form.html`
- Test: `tests/unit/test_settings.py`
- Test: `tests/unit/test_settings_runtime_resolution.py`
- Test: `tests/integration/test_pages.py`

## Interfaces

- `RuntimeSettings.playlist_page_size: int`
- `SETTINGS_CATALOG["playlist_page_size"] == "20"`
- Existing `set_settings_batch()` remains the write boundary.
- `PUT /settings/form` includes `playlist_page_size` in its atomic update.

## Steps

- [ ] **Step 1: Write failing tests**:
  - Update `tests/unit/test_settings.py` so the catalog default/reset coverage includes `playlist_page_size`, and cover accepted values `1` and `50` plus rejected values `0`, `51`, and non-integers through the existing setting write boundary.
  - Update `tests/unit/test_settings_runtime_resolution.py` to cover the default, a persisted value, and malformed/out-of-range persisted values falling back/clamping safely.
  - Update `tests/integration/test_pages.py` to assert the persisted value renders and `PUT /settings/form` saves the submitted page size.
- [ ] **Step 2: Run** `uv run pytest tests/unit/test_settings.py tests/unit/test_settings_runtime_resolution.py tests/integration/test_pages.py -q`; confirm the new tests fail.
- [ ] **Step 3: Add the catalog key, validation, and typed runtime resolution** in `app/services/settings.py`; preserve the existing atomic batch-update behavior.
- [ ] **Step 4: Add the Settings form field** in `app/templates/partials/settings_form.html` with native numeric bounds `1..50`, and pass it through `app/routes/pages.py` using the existing settings form submission.
- [ ] **Step 5: Run** `uv run pytest tests/unit/test_settings.py tests/unit/test_settings_runtime_resolution.py tests/integration/test_pages.py -q`; confirm all focused tests pass.
- [ ] **Step 6: Commit** with `git add app/services/settings.py app/routes/pages.py app/templates/partials/settings_form.html tests/unit/test_settings.py tests/unit/test_settings_runtime_resolution.py tests/integration/test_pages.py && git commit -m "feat: configure playlist preview page size"`.

## Usable result

The Settings page persists a playlist page-size value and exposes it through `RuntimeSettings`; no playlist code is required to use it yet.
