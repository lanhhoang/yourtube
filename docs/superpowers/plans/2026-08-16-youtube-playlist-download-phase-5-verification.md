# YouTube Playlist Download — Phase 5: Verification and Handoff Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this phase task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Verify the complete playlist workflow, document the user-visible capability, and hand off a clean implementation.

**Architecture:** Exercise the full stack after Phases 1–4: settings resolution, flat extraction, paginated rendering, indexed enqueue parsing, and independent queue jobs. Keep final changes limited to documentation or tests required by observed gaps.

**Tech Stack:** pytest, Ruff, ty, FastAPI TestClient, yt-dlp runtime.

**Spec:** `docs/superpowers/specs/2026-08-16-youtube-playlist-download-design.md`

**Parent plan:** `docs/superpowers/plans/2026-08-16-youtube-playlist-download-parent.md`

## Global Constraints

- Complete Phases 1–4 before starting this phase.
- Do not weaken tests or change the agreed page-local/no-total-cap behavior.
- Report any unavailable live-network smoke test separately from automated test results.

## Files

- Modify: `README.md` to add the completed paginated playlist workflow to the Current features list
- Test: all affected unit and integration test files

## Steps

- [ ] **Step 1: Run the full suite** with `uv run pytest`; fix only regressions introduced by the playlist implementation.
- [ ] **Step 2: Run static checks** with `uv run ruff check .` and `uv run ty check`.
- [ ] **Step 3: Add one README feature bullet** describing paginated YouTube playlist preview, page-local selection, and independent queue jobs.
- [ ] **Step 4: Run the full suite and static checks again** after the documentation change.
- [ ] **Step 5: Manually smoke-test** `https://www.youtube.com/playlist?list=PLJicmE8fK0EiKm0PfjNhjcUCZdJgYun3I`: preview page 1, navigate pages, deselect entries, choose per-video formats, enqueue selected rows, and verify independent queue jobs.
- [ ] **Step 6: Self-review the diff** for accidental schema changes, unindexed bulk fields, silent invalid-entry loss, direct URL regressions, and modifications to the original plan.
- [ ] **Step 7: Commit final documentation/test corrections** with `git add README.md tests app && git commit -m "test: verify playlist download workflow"`.

## Acceptance checklist

- [ ] Playlist preview works through the existing batch form.
- [ ] Page size defaults to 20 and respects Settings values from 1 through 50.
- [ ] Order and deduplication are stable; invalid entries remain visible.
- [ ] Only the current page performs full metadata extraction.
- [ ] Selected rows retain their individual format and advanced-option values.
- [ ] One queue job is created per selected video; unchecked rows are not queued.
- [ ] Direct URL and individual video behavior remains unchanged.
- [ ] Original plan file is unchanged.

## Usable result

The implementation is verified against automated checks and the supplied playlist flow, documented for users, and ready for execution handoff.
