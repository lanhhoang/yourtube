# HDR option — design

Date: 2026-11-18. Status: draft for owner approval. Builder-check done; calls made during it are marked *(Builder's call)*.

Builds on: `2026-11-18-phone-pwa-notifications-design.md` §1 (MP4 format selection) and its Phase 2 plan (`plans/2026-11-18-phone-pwa-notifications-phase-2-mp4.md`). That spec lists "HDR output" as a non-goal; this design replaces that with "SDR unless the job asks for HDR".

## Intent

Some YouTube videos are offered in HDR. The owner wants to keep those in HDR when they choose to. They queue downloads from the computer or the iPhone, and they watch the files later on a computer in VLC or IINA. The iPhone only has to queue and download them, not play them. Everything else stays as Phase 2 left it: SDR MP4, H.264 + AAC up to 1080p, VP9 SDR + AAC above.

Success: on a 4K HDR video, tick HDR, queue at "Best available", and get a 2160p HDR `.mp4` that plays in HDR in IINA. On a video with no HDR, the HDR control is greyed out and nothing changes.

## Goals

1. Each job has an HDR choice, off by default. Off gives exactly the Phase 2 result.
2. With HDR on, the server picks an HDR video stream when one exists **at the resolution the cap would pick anyway**. Resolution comes first and HDR never costs resolution (owner's decision). If no HDR stream exists at that resolution, the job quietly gets the SDR pick.
3. Single video page: an "HDR" checkbox under Quality. It is disabled (greyed out) when the video has no HDR formats or the cap is "Audio only". When it is on and the cap is above the highest HDR resolution, a note reads `HDR only up to 1080p. This cap gets SDR.` (with the real number).
4. Playlist page: one "HDR where available" checkbox under Quality for the whole playlist, disabled only for "Audio only". Each checked entry that has HDR shows a badge: `HDR` when HDR exists at that entry's capped resolution, `HDR ≤1080p` when HDR stops below it.
5. The exact format picker labels HDR video rows, so the owner can pick an HDR stream by hand. This is the workaround the note in goal 3 points to.

## Non-goals

- Playing HDR files in the in-app player or on iPhone. Phase 4's "This device can't play this file. Save it and open it in VLC." message covers it.
- AV1 preference, or any per-codec choice for HDR (see Approaches: VP9.2 is accepted).
- Tone mapping, HDR→SDR conversion, special Dolby Vision handling. yt-dlp's `hdr` sort ranks DV above HDR10/HLG, and if YouTube ever offers DV at the capped size, it is taken like any other HDR stream. *(Builder's call, marked: YouTube serves HDR10/HLG in VP9.2/AV1 in practice, and IINA/VLC play DV profile 8 as HDR10.)* Streams are still copied and remuxed, never transcoded.
- Recording whether a finished file is actually HDR, or showing it in the queue or library.
- Remembering the HDR choice between visits. The cap doesn't persist either (`DEFAULT_CAP` on every mount).
- Changes to audio: AAC preference stays.

## Anti-goals

- Turning HDR on gives a lower resolution than leaving it off.
- Turning HDR off (the default) changes any Phase 2 pick.
- The checkbox looks clickable on a video that has no HDR.
- Showing HDR availability by colour alone (`DESIGN.md`): badges and the note are text.

## Constraints

- Phase 2 must be merged first. This builds on its `CapFormat`, `MP4_SORT` and `merge_output_format`.
- yt-dlp 2026.10.26. One `format_sort` list applies to every candidate. A codec preference added for HDR changes the SDR picks too (verified, see Appendix).
- Database change goes through a new Alembic revision.
- After the API schema change, run `pnpm typegen` and commit `apps/web/src/lib/api.gen.ts`.
- Exact format ids still override the cap and now the HDR choice too.

## Approaches

Considered for how the HDR choice is carried:

- **A. Separate `hdr` flag on the job (chosen).** One boolean column and API field. A checkbox under Quality. The server swaps one sort key. The lookup reports the highest HDR resolution. It keeps "cap" meaning resolution only and fits "default SDR, choosable when available".
- **B. HDR variants of the cap** (`2160-hdr`, …). No new column, but the cap list nearly doubles. The shared below-cap rule (`quality_cases.json`, `isBelowCap`) and every cap check would have to learn the variants, and you can't grey out entries in a `<select>` cleanly. Rejected.
- **C. Only label HDR rows in the exact picker.** No default and no playlist support. Rejected as the main mechanism; kept as goal 5.

Considered for which HDR codec:

- **VP9.2 HDR via the existing sort (chosen).** HDR on changes `hdr:sdr` to `hdr`, and the rest of `MP4_SORT` stays. `vcodec:h264` then ranks VP9 above AV1, so a video offering both picks VP9.2 HDR. The owner watches in VLC/IINA, which play it.
- **AV1 HDR via a two-step pick.** Would need the server to inspect formats and choose the sort per video, because adding `vcodec:av01` to the shared sort also makes 1080p SDR picks AV1 instead of H.264. Only buys QuickTime playback on M3+ Macs, which the owner doesn't need. Rejected.

## Decisions

### 1. Server: format selection (`app/services/quality.py`)

`cap_format_options(cap, audio_bitrate=None, hdr=False) -> CapFormat`.

- `hdr=False`: unchanged from Phase 2: `["res[:N]", "hdr:sdr", "vcodec:h264", "acodec:aac", <abr:K>]`.
- `hdr=True` and a video cap (`best`, numeric, or `None`): the same list with `"hdr"` in place of `"hdr:sdr"`. `res` stays first, which gives the "resolution first" rule.
- `cap == "audio"`: `hdr` is ignored.
- Exact format ids: `hdr` is ignored (the existing `_format_selector` path).

Verified offline picks with `hdr=True` (Appendix): 4K video with SDR VP9, HDR VP9.2 and HDR AV1 at 2160p → best picks `337+140` (VP9.2 HDR). Cap 1080 with no HDR at 1080p → `299+140` (H.264). A video with no HDR at all → the same picks as `hdr=False`.

### 2. Server: storing the choice

- New non-null boolean column `downloads.hdr`, default false (`server_default=sa.false()`), in a new Alembic revision. Existing rows read as false.
- `DownloadCreate.hdr: bool = False` (so `JobCreate` has it). `JobOut.hdr: bool`.
- `queue._row_from_payload` copies it; `job_runner` passes `hdr=job.hdr` to `run_download`; `run_download(..., hdr: bool = False)` passes it to `cap_format_options`.
- `tests/e2e_server.py`'s stub `_run_download` already takes `**_kwargs`; no change needed beyond what typegen requires.

### 3. Server: HDR availability in the lookup

- `FormatInfo` gains `dynamic_range: str | None` (from yt-dlp's `dynamic_range`, via `_safe_str`). `StreamRow` / the picker row gains it too (goal 5).
- A video stream counts as HDR when `dynamic_range` is set and is not `"SDR"`. That covers `HDR10`, `HDR12`, `HLG`, `DV` and `HDR10+`.
- No new top-level field. The browser already gets every separate video stream with its width and height in `picker.video_streams`, and now gets `dynamic_range` too, so it can work out everything in §4 exactly.

### 4. Web: the rule shared by both pages

`apps/web/src/lib/quality.ts` gains:

- `hdrSide(streams) -> number | null`: the largest short side among `video_streams` rows whose `dynamic_range` is set and not `"SDR"`. `null` means no HDR.
- `cappedSide(cap, streams) -> number | null`: the short side the server's `res[:N]` sort would pick. For `best` that's the largest side. For a numeric N it's the largest side ≤ N, or the smallest side above N when nothing is ≤ N. That's the same rule as `res:N`, documented in `quality.py`.
- `hdrAtCap(cap, streams) -> "none" | "yes" | "below"`: `"none"` when there's no HDR or the cap is `audio`; `"yes"` when some HDR row has exactly `cappedSide`; `"below"` when `hdrSide < cappedSide`, and the number to show is `hdrSide`. Any other mismatch (HDR only above the capped side, or a gap in the HDR sizes) also returns `"none"`: no note and no badge. *(Builder's call, marked: YouTube's HDR sizes normally run from the bottom up, so this is an edge case and silence is safer than a misleading number.)*

Videos that only offer muxed streams (no separate video rows) count as no HDR. YouTube's muxed formats are SDR.

`quality_cases.json` is unchanged. These helpers get their own Vitest cases, including cap 1440 on a 2160/1080 video with HDR at 1080 (`"yes"`: the cap picks 1080).

### 5. Web: single video page (`VideoView.svelte`)

```
Quality
[ Up to 1080p        ▾ ]
[✓] HDR
    HDR only up to 1080p. This cap gets SDR.   ← only when hdrAtCap = "below" and HDR is on
```

- Checkbox label `HDR`, below `QualitySelect`, at least 44 px tall touch target.
- Disabled when `hdrSide(video.picker.video_streams) === null` or the cap is `audio`. When disabled it reads `HDR (not offered)` for no HDR, or stays `HDR` for audio. It is always unticked while disabled, and the job sends `hdr: false`. If the cap goes to Audio only and back, the tick does not come back. *(Builder's call, marked: matches off-by-default.)*
- Dimmed together with Quality when an exact format is picked (same `dimmed` treatment and the existing "Exact format overrides this" text).
- Sends `hdr` on the job.

### 6. Web: playlist page (`ListView.svelte`, `playlist.ts`, `badges.ts`)

- `Header` gains `hdr: boolean`. `buildJobs` sends `hdr: header.hdr` for every job, including ones with an exact override, where the server ignores it.
- Checkbox `HDR where available` below `QualitySelect`. It is disabled only when the cap is `audio`.
- Badge: a second, independent badge next to the existing one. The existing `badgeFor` keeps returning the below-cap/custom/unavailable badge, and a new `hdrBadgeFor(e, cap)` returns `HDR`, `HDR ≤{side}p` or nothing. It is shown for checked-OK entries with HDR, without an exact override, and when the cap isn't audio, **whether or not the HDR box is ticked**, so the owner can see which videos have HDR before deciding. Neutral tone, text only.

### 7. Docs

- README "Quality caps": add one paragraph on HDR (off by default, resolution first, VP9.2/AV1 in `.mp4`, plays in VLC/IINA, not Safari/QuickTime/iPhone).
- The parent spec's non-goal "HDR output" → "HDR unless the job asks for it (see `2026-11-18-hdr-option-design.md`)". The "No HDR output" line in every phase plan's Global Constraints → "No HDR output unless the job asks for HDR."
- `PRODUCT.md`: add HDR to what a job can choose, if it lists job options.

### 8. Where it goes in the phases

Phase 3 of the phone PWA plan: `plans/2026-11-18-phone-pwa-notifications-phase-3-hdr.md` (parent plan Tasks 4 and 5). Channel folders and the later phases moved down one number. Its Alembic revision `20261118110000_add_hdr.py` sorts before the channel-folders revision `20261118120000`, which now revises it.

## Left to the builder

- Exact wording and placement details within `DESIGN.md` rules (badge tone, disabled styling).
- Whether `hdrAtCap` lives in `quality.ts` or a new small module.
- Test file names beyond the existing layout.

## Appendix: verified sort behaviour (yt-dlp 2026.10.26, offline, 2026-11-18)

Formats: 2160p VP9 SDR `315`, AV1 SDR `401`, VP9.2 HDR10 `337`, AV1 HDR10 `701`; 1080p H.264 `299`, VP9 `303`, AV1 SDR `399`; audio AAC `140`.

| Sort | Cap | With HDR formats | Without HDR formats |
|---|---|---|---|
| `res, hdr, vcodec:h264, acodec:aac` (chosen) | best | 337+140 | 315+140 |
| same | 1080 | 299+140 | 299+140 |
| `res, hdr, vcodec:av01, acodec:aac` (rejected) | best | 701+140 | 401+140 |
| same | 1080 | **399+140** (AV1 SDR, not H.264) | 399+140 |
| Phase 2 `res, hdr:sdr, vcodec:h264, acodec:aac` | best / 1080 | 315+140 / 299+140 | — |

With HDR only at 1080p and SDR at 2160p: `res, hdr, …` at best picks 2160p SDR (resolution first). `hdr, res, …` would pick 1080p HDR, which the owner rejected.
