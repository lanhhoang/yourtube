# Library, Queue and Subtitles: Phase Index

The parent plan `2026-11-19-library-queue-subtitles.md` is split into six phases, ordered from simplest to most complex. Each phase ends with something the owner can use, and each is executed, reviewed and merged on its own. The parent plan stays the reference: phase files copy its tasks verbatim and add a phase header (goal, usable result, prerequisites, phase review focus). No parent task is split.

**Spec:** `docs/superpowers/specs/2026-11-19-library-queue-subtitles-design.md`

| # | Phase | Plan | Parent tasks | Usable result |
|---|---|---|---|---|
| 1 | Queue: dismiss all failed | `…-phase-1-queue-dismiss-all.md` | 1, 2 | With two or more failed jobs, the Queue's Failed heading shows **Dismiss all**; one click empties the list. Files are untouched. |
| 2 | Quieter, sturdier downloads | `…-phase-2-downloads.md` | 3, 4, 5 | Download a playlist with subtitles on: no SABR warning in the log, no `HTTP Error 429` job failures; a French video gets `fr-orig` subtitles, and a subtitle failure leaves a finished video. |
| 3 | Watch metadata: dynamic range and codecs | `…-phase-3-watch-metadata.md` | 6, 7, 8 | Open any finished video: the line under the title shows resolution, SDR/HDR10/HLG, size, video and audio codec and container. Old items fill in after the next start (ffprobe). A video whose subtitles failed says "Subtitles couldn't be downloaded." |
| 4 | Subtitles in the player | `…-phase-4-player-subtitles.md` | 9, 10 | Open a video downloaded with subtitles: the player's captions menu lists e.g. "French (auto)" and "English"; picking one shows cues. Deleting the video removes its `.srt`/`.txt` files. |
| 5 | Library: Select mode and bulk delete | `…-phase-5-bulk-delete.md` | 11, 12 | Library → **Select** → tick videos (or **Select all**) → **Delete** → **Delete N?** → gone, with "Deleted N" (or "Deleted 2, 1 failed"). Works by tap on the phone, where per-card delete didn't exist before. |
| 6 | Library: sort and filter | `…-phase-6-sort-filter.md` | 13, 14, 15 | Library toolbar: search · Sort (Newest, Oldest, Title A–Z, Longest, Largest) · Filter (Type, Channel, Playlist; a bottom sheet on phones) · Select. Active filters show as removable pills; the choice survives a reload. |

## Order and dependencies

```
Phase 1 (independent)
Phase 2 ──► Phase 3 ──► Phase 4 ──► Phase 5 ──► Phase 6
              └──────────────────────────────────▲ (JobOut.playlist_*)
```

- Phase 1 is one endpoint and one button, so it ships first and can merge at any time.
- Phase 2 is server-only, with no schema change. It fixes the two reported errors and comes early because it unblocks playlist downloads.
- Phase 3 adds the only migration (codecs, dynamic range, warning, and `JobOut.playlist_*`), persists Phase 2's warning, and adds a background ffprobe pass. It's more moving parts than Phase 2, but it's still read-only for files.
- Phase 4 adds new endpoints and file discovery with path-safety concerns, and is the first change to delete behaviour (sidecars).
- Phase 5 is the first bulk destructive action. It reuses Phase 4's sidecar-aware delete.
- Phase 6 is the largest UI change (toolbar, popover/sheet, pills, persistence) and removes the chips. It needs Phase 3's `playlist_title` and Phase 5's selection. The chips are removed here, together with the Type filter that replaces them, so no phase leaves the Library without a Video/Audio filter.

## Spec coverage by phase

| Spec item | Phase |
|---|---|
| Goal 1 / §1 player_client `default,-web_embedded` | 2 |
| Goal 2 / §1 subtitle languages, translated skip, non-fatal subtitle failure | 2 (warning stored 3, shown 3) |
| Goal 3 / §7 dismiss all failed | 1 |
| Goal 6 / §2 codecs, dynamic range (HDR/SDR), backfill | 3 |
| Goal 7 / §3 subtitles in the player, off by default | 4 |
| §4 delete removes sidecars | 4 |
| Goal 4 / §5 bulk delete, Select mode | 5 |
| Goal 5 / §6 chips removed, sort, filter, pills, persistence | 6 |
| Anti-goal: hiding real failures | 2 |
| Anti-goal: data loss | 4, 5 |
| Anti-goal: UI slop | 1, 3, 5, 6 (skills read + screenshots) |
