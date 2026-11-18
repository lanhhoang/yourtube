# Phone PWA and Notifications: Phase Index

The parent plan `2026-11-18-phone-pwa-notifications.md` is split into six phases, ordered from simplest to most complex. Each phase ends with something the owner can use, and each is executed, reviewed and merged on its own. The parent plan stays the reference: phase files copy its tasks verbatim and add a phase header (goal, usable result, prerequisites, phase review focus). No parent task is split.

**Spec:** `docs/superpowers/specs/2026-11-18-phone-pwa-notifications-design.md`

| # | Phase | Plan | Parent tasks | Usable result |
|---|---|---|---|---|
| 1 | Shell | `…-phase-1-shell.md` | 1, 2 | Play-circle mark next to the wordmark; one rail tile cycles Dark → Light → System |
| 2 | MP4 downloads | `…-phase-2-mp4.md` | 3 | `best` and numeric caps give `.mp4` (H.264/AAC first, VP9 SDR above 1080p, never HDR) |
| 3 | Channel and playlist folders | `…-phase-3-channel-folders.md` | 4, 5, 6 | New downloads land in `<channel>/[<playlist>/]<title>.<ext>`; the existing library moves there once |
| 4 | Phone access, PWA and player | `…-phase-4-phone-access.md` | 7, 8, 9, 10 | Installable on the iPhone over Tailscale HTTPS; Paste to queue; play and Save finished files |
| 5 | Phone layout | `…-phase-5-phone-layout.md` | 11–15 | Every screen has an owner-approved phone layout: tab bar, single column, bottom sheet |
| 6 | Notifications | `…-phase-6-notifications.md` | 16–21 | Push and toasts for finished, failed and settled batches (one summary per playlist) |

## Order and dependencies

```
Phase 1 ──► Phase 2 ──► Phase 3 ──► Phase 4 ──► Phase 5 ──► Phase 6
                                       └─────────────────────────▲ (sw.ts, HTTPS install)
```

- Phase 1 is web only, and Phase 2 is one server module. They come first because they are the smallest and the owner sees the effect at once.
- Phase 3 builds on Phase 2's `run_download` and `build_ytdlp_options` signatures. Its startup move touches real files, so it ships alone with its own review.
- Phase 4 needs Phase 1's `LogoMark` as the icon source. It assumes Phase 3's README section and e2e seeded path.
- Phase 5 starts with a hard stop: Task 11's mockups need the owner's approval before Tasks 12–15. Phase 4 runs before it because the PWA, player and Paste button don't depend on the mockups (the spec says so), and the phone layout then covers the player too.
- Phase 6 needs Phase 4's service worker and the HTTPS install. It is last because it has the most moving parts: a migration, a concurrency guarantee, a new dependency, a service worker, a manual check on the iPhone. Phase 5 before it is recommended, so the Settings toggle lands in the phone layout, but it is not required.

## Spec coverage by phase

| Spec item | Phase |
|---|---|
| Goal 1 / §1 MP4 format selection | 2 |
| Goal 2 / §2 channel and playlist folders, one-off move | 3 |
| Goal 3 / §3 logo | 1 (PWA icons: 4) |
| Goal 4 / §4 theme tile | 1 (phone: Settings only, 5) |
| Goal 5 / §5 network access | 4 |
| Goal 6 / §6 PWA, share target, Paste, Shortcut docs | 4 |
| Goal 6 / §7 phone layout | 5 |
| Goal 8 / §8 player and Save | 4 |
| Goal 7 / §9 notifications | 6 |
| §10 docs | each phase updates its own part; 6 closes out |
| Anti-goal: notification flood | 6 (Task 16 race test, Task 20 batch toasts) |
| Anti-goal: losing library files | 3 (Task 6) |
| Anti-goal: generic UI | 5 (Tasks 11, 15) |
| Anti-goal: CDN at runtime | all (Global Constraints) |
