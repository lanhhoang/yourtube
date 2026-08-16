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
- Preserve atomic settings updates and all existing settings behavior.
- Do not add a migration or dependency.

## Files

- Modify: `app/services/settings.py`
- Modify: `app/routes/pages.py`
- Modify: `app/templates/pages/settings.html`
- Modify: `app/templates/partials/settings_form.html`
- Test: `tests/unit/test_settings_runtime_resolution.py`
- Test: `tests/integration/test_pages.py`

## Interfaces

- `RuntimeSettings.playlist_page_size: int`
- `SETTINGS_CATALOG["playlist_page_size"] == "20"`
- Existing `set_settings_batch()` remains the write boundary.

## Steps

- [ ] **Step 1: Write failing unit tests** for the default value, persisted values, accepted boundaries `1` and `50`, and rejected values `0`, `51`, and non-integers.
- [ ] **Step 2: Run** `uv run pytest tests/unit/test_settings_runtime_resolution.py -q`; confirm the new tests fail.
- [ ] **Step 3: Add the catalog key and validation** in `app/services/settings.py`; resolve the clamped integer into `RuntimeSettings.playlist_page_size`.
- [ ] **Step 4: Add the Settings form field and route update** using the existing settings form submission and atomic batch update.
- [ ] **Step 5: Add an integration assertion** that the persisted page-size value renders in the Settings page.
- [ ] **Step 6: Run** `uv run pytest tests/unit/test_settings_runtime_resolution.py tests/integration/test_pages.py -q`; confirm all focused tests pass.
- [ ] **Step 7: Commit** with `git add app/services/settings.py app/routes/pages.py app/templates/pages/settings.html app/templates/partials/settings_form.html tests/unit/test_settings_runtime_resolution.py tests/integration/test_pages.py && git commit -m "feat: configure playlist preview page size"`.

## Usable result

The Settings page persists a playlist page-size value and exposes it through `RuntimeSettings`; no playlist code is required to use it yet.
