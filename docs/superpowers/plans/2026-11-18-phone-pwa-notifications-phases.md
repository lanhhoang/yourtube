# Phone PWA and Notifications: Phase Index

The parent plan `2026-11-18-phone-pwa-notifications.md` is split into seven phases, ordered from simplest to most complex. Each phase ends with something the owner can use, and each is executed, reviewed and merged on its own. The parent plan stays the reference: phase files copy its tasks verbatim and add a phase header (goal, usable result, prerequisites, phase review focus). No parent task is split.

**Spec:** `docs/superpowers/specs/2026-11-18-phone-pwa-notifications-design.md`. Phase 3 also implements `docs/superpowers/specs/2026-11-18-hdr-option-design.md`.

| # | Phase | Plan | Parent tasks | Usable result |
|---|---|---|---|---|
| 1 | Shell | `…-phase-1-shell.md` | 1, 2 | Player mark next to the wordmark, new play-circle favicon; one rail tile cycles Dark → Light → System |
| 2 | MP4 downloads | `…-phase-2-mp4.md` | 3 | `best` and numeric caps give `.mp4` (H.264/AAC first, VP9 SDR above 1080p, never HDR), and the library points at the merged file |
| 3 | HDR option | `…-phase-3-hdr.md` | 4, 5 | Opt-in HDR per job (resolution first); greyed out when the video has no HDR; playlist "HDR where available" with per-video badges |
| 4 | Channel and playlist folders | `…-phase-4-channel-folders.md` | 6, 7, 8 | New downloads land in `<channel>/[<playlist>/]<title>.<ext>`; the existing library moves there once |
| 5 | Phone access, PWA and player | `…-phase-5-phone-access.md` | 9, 10, 11, 12 | Installable on the iPhone over Tailscale HTTPS; Paste to queue; play and Save finished files |
| 6 | Phone layout | `…-phase-6-phone-layout.md` | 13–17 | Every screen has an owner-approved phone layout: tab bar, single column, bottom sheet |
| 7 | Notifications | `…-phase-7-notifications.md` | 18–23 | Push and toasts for finished, failed and settled batches (one summary per playlist) |

## Order and dependencies

```
Phase 1 ──► Phase 2 ──► Phase 3 ──► Phase 4 ──► Phase 5 ──► Phase 6 ──► Phase 7
                                                   └─────────────────────────▲ (sw.ts, HTTPS install)
```

- Phase 1 is web only, and Phase 2 is one server module. They come first because they are the smallest and the owner sees the effect at once.
- Phase 3 builds on Phase 2's `CapFormat` sort and adds the `hdr` column and argument. It comes before the folders work because it is small and reuses Phase 2's tests while they are fresh.
- Phase 4 builds on the `run_download` and `build_ytdlp_options` signatures from Phases 2 and 3 (`hdr` is already a keyword argument). Its startup move touches real files, so it ships alone with its own review.
- Phase 5 needs Phase 1's new play-circle `favicon.svg` as the icon source. It assumes Phase 4's README section and e2e seeded path.
- Phase 6 starts with a hard stop: Task 13's mockups need the owner's approval before Tasks 14–17. Phase 5 runs before it because the PWA, player and Paste button don't depend on the mockups (the spec says so), and the phone layout then covers the player too.
- Phase 7 needs Phase 5's service worker and the HTTPS install. It is last because it has the most moving parts: a migration, a concurrency guarantee, a new dependency, a service worker, a manual check on the iPhone. Phase 6 before it is recommended, so the Settings toggle lands in the phone layout, but it is not required.

## Spec coverage by phase

| Spec item | Phase |
|---|---|
| Goal 1 / §1 MP4 format selection | 2 |
| HDR option spec (all) | 3 |
| Goal 2 / §2 channel and playlist folders, one-off move | 4 |
| Goal 3 / §3 logo | 1 (PWA icons: 5) |
| Goal 4 / §4 theme tile | 1 (phone: Settings only, 6) |
| Goal 5 / §5 network access | 5 |
| Goal 6 / §6 PWA, share target, Paste, Shortcut docs | 5 |
| Goal 6 / §7 phone layout | 6 |
| Goal 8 / §8 player and Save | 5 |
| Goal 7 / §9 notifications | 7 |
| §10 docs | each phase updates its own part; 7 closes out |
| Anti-goal: notification flood | 7 (Task 18 race test, Task 22 batch toasts) |
| Anti-goal: losing library files | 4 (Task 8) |
| Anti-goal: generic UI | 6 (Tasks 13, 17) |
| Anti-goal: CDN at runtime | all (Global Constraints) |
