# Library, Queue and subtitle improvements — design

Date: 2026-11-19 · Status: draft for approval

## Intent

YourTube is a single-user, self-hosted downloader. Playlist downloads are noisy (a SABR warning) and some fail outright on a subtitle 429 even though the video itself was fine. The Library can't be managed in bulk, sorted or filtered, so a growing library means deleting things one at a time and scrolling to find them. Subtitles are downloaded but you can't watch with them. The Watch page also doesn't say what codecs a file uses, which matters because HDR/AV1 files don't play everywhere.

Success: a playlist download finishes without errors or warnings caused by our options. You can find, sort and bulk-delete items in the Library on desktop and phone. The Watch page shows codecs and offers the downloaded subtitles in the player.

## Goals

1. Stop forcing the `web_embedded` player client (the source of the SABR warning).
2. Never request auto-translated subtitles. A subtitle failure must not fail a job.
3. Queue: one action dismisses all failed jobs.
4. Library: Select mode with multi-select delete.
5. Library: sort and filter controls. Remove the All / Downloading / Video / Audio only chips.
6. Watch: metadata line `Channel · 1080p · SDR · 300 MB · av1 · aac · mp4` (dynamic range added 2026-11-19 at the owner's request).
7. Watch: downloaded subtitles available in the native player, off by default.

## Non-goals

- Server-side sort/filter/pagination. The whole library is already sent to the client.
- Cancel-all for active or queued jobs.
- Upload date as a sort key (it isn't stored; could be added later).
- PO-token providers (bgutil), switching to Deno, cookie management changes.
- A custom video player. The native `<video controls>` stays.
- Embedding subtitles into media files.

## Anti-goals

- Hiding real failures. If the media download fails, the job still fails. Only subtitle failures become warnings.
- Data loss. Bulk delete always asks for confirmation and only touches `done` rows and their own files.
- UI slop. No new visual language: follow `DESIGN.md` tokens, no decorative extras. Use the impeccable and design-taste-frontend skills as a review lens.

## Constraints

- yt-dlp 2026.10.26 (`yt-dlp[default]`, yt-dlp-ejs 0.8.0), Node as the JS runtime.
- SQLite + Alembic. The latest revision is `20261118130000`.
- Svelte web app with hash routing. API types are generated (`pnpm typegen`, checked in CI via `typegen:check`).
- Phone layout below 768px: 44px tap targets, safe-area-aware bottom tab bar, `BottomSheet` component available.
- Checks: `pnpm check`, `pnpm test`, `pnpm e2e`. Server: ruff, ty, pytest with a coverage floor of 50%.

## Approaches considered

| Area | Chosen | Rejected and why |
|---|---|---|
| Sort/filter | **In the browser** over the `/api/library` list | Server-side SQL params: scales past ~10k items, but adds API/schema/test surface that a personal library doesn't need |
| Player subtitles | **Find them on disk** next to the media file; serve SRT converted to VTT | Recording them in the DB at download time needs a migration, and old downloads would show nothing unless backfilled |
| Codecs | **New `vcodec`/`acodec` columns**, filled at download time, ffprobe backfill on startup | ffprobe on every Watch page view: a subprocess per view, and no data for list views |
| Subtitle languages | **Original language + real English**, never auto-translated | Always English with a 60 s sleep (slow, still fragile). Original only (loses English when a real English track exists) |
| Library chips | **Remove all chips.** Type (video/audio) moves into Filter | Keep All/Video/Audio, or keep all four |
| Queue clear | **Dismiss all failed** | Also cancel queued; two buttons |
| Multi-select | **Select mode + sticky action bar** | Always-visible checkboxes (busy grid). Hover/long-press (hard to discover) |

All rows were picked by the user.

## Design

### 1. yt-dlp options (`apps/server/app/services/downloader.py`)

- `build_ytdlp_options`: `extractor_args.youtube.player_client` → `["default", "-web_embedded"]`. Plain `default` isn't enough: with cookies, yt-dlp's default set is `web_embedded, tv_samsung, web` (`_DEFAULT_AUTHED_CLIENTS`), so the warning would return for cookie users. The `-` exclusion only removes it from the requested list. yt-dlp's own age-gate/made-for-kids fallback (`append_client('web_embedded')`) still works. Verified 2026-11-19: 47 formats, 1080p, no warning. Also add `"skip": ["translated_subs"]` under `youtube` extractor args. This only drops translations of *manual* tracks. Auto-caption translations are still listed, which is why the language picking below is needed. Update `test_build_ytdlp_options_avoids_youtube_android_vr_403` to match (the yt-dlp default no longer uses android_vr).
  - Verified 2026-11-19: `QaVuJI6Mkv0` gives 1080p max with and without `web_embedded`.
- Subtitle language: when `subtitles=True`, pick exact keys from the resolved info so nothing auto-translated is ever requested. A pure function `pick_subtitle_langs(resolved) -> list[str]`:
  - `orig` = the language of the key ending in `-orig` in `resolved["automatic_captions"]` (yt-dlp marks the original-language auto caption this way). Fall back to `resolved["language"]` (note: that's the chosen audio format's language and may be `None` or `"en+fr"`-style; take the part before `+`/`-`).
  - Manual tracks (`resolved["subtitles"]`): include every key whose base language (before `-`) is `orig` or `en`. These are real, human-made tracks.
  - Auto: include `f"{orig}-orig"` if present, **only if** no manual track for `orig` was picked. Never include any other `automatic_captions` key: apart from `-orig`, they're machine translations carrying `tlang`, which is what gets rate-limited.
  - If nothing qualifies, request no subtitles (and add no warning).
  - Example: French video, auto captions only → `["fr-orig"]`. English video with manual `en` → `["en"]`. French video with manual `fr` and `en` → `["fr", "en"]`.
  - Set `ydl.params["subtitleslangs"]` after the existing `extract_info(download=False)` and before `process_ie_result`, the same way `outtmpl` is set today. The `output_template` branch (currently a single `extract_info(download=True)`) is split into resolve-then-process the same way, so both paths behave identically. Re-test the `match_filter` output guard on that branch.
- Subtitle failure is non-fatal. Do **not** use global `ignoreerrors` (that would hide media failures). Instead: catch `yt_dlp.utils.DownloadError` whose message **contains** `Unable to download video subtitles` (yt-dlp raises it via `report_error`, so the message is prefixed `ERROR: `). Retry the download once with `writesubtitles=False, writeautomaticsub=False`. Record a warning on the job.
  - Verified in yt-dlp 2026.10.26: `process_info` calls `_write_subtitles` (YoutubeDL.py:3387) before the media download (:3531), and a subtitle failure raises `DownloadError('Unable to download video subtitles for ...')` (:4493). So no media is on disk yet, and the retry is the real media download. Subtitle files that already downloaded for other languages stay on disk.
- Job warning: add a nullable `warning_message` column (same migration as codecs, below), surfaced in `JobOut`. Cleared by `retry_job` along with the error fields. When it's set, the Watch page shows "Subtitles couldn't be downloaded" under the metadata line. The job's status stays `done`.
- The transcript sidecar `OSError` stays fatal as it is today (no change requested).

### 2. Codecs

- Migration `20261119120000_add_codecs_and_warning`: add nullable `vcodec`, `acodec`, `warning_message` (String) to `downloads`. Use the `op.batch_alter_table` pattern.
- At download time: `_extract_file_metadata` also returns `vcodec`/`acodec` from the final `info` (for merged formats use `requested_formats`; `none` maps to null). The job runner stores them.
- Dynamic range: a nullable `dynamic_range` column next to the codecs, filled from yt-dlp's `dynamic_range` (`SDR`, `HDR10`, `HLG`, …; for merged downloads it comes from the video stream). Shown after the resolution for video items only: `1080p · SDR` or `2160p · HDR10`. yt-dlp's label is shown as stored, so HDR variants keep their name.
- `JobOut` gains `vcodec`, `acodec`, `dynamic_range` (raw strings) and `warning_message`. Run `pnpm typegen` afterwards.
- Display shortening happens on the client, in `apps/web/src/lib/codecs.ts`: `avc1*`→`h264`, `hev1|hvc1*`→`h265`, `vp09|vp9*`→`vp9`, `av01*`→`av1`, `mp4a*`→`aac`, `opus`→`opus`, `ac-3`→`ac3`, `ec-3`→`eac3`, `flac`, `mp3`; anything else passes through. **Note:** the user's example wrote `av01`. Showing `av1` is the builder's call; either is fine. Default: `av1`.
- Backfill: startup step `backfill_codecs(session)` next to `migrate_library_layout` in `main.py` lifespan. For `done` rows with null `vcodec` and `acodec` and an existing file, run `ffprobe -v error -show_streams -of json` and take the first video and audio `codec_name` (already short: `h264`, `av1`, `aac`…). Skip video streams with `disposition.attached_pic=1` (cover art in audio files). Dynamic range comes from the video stream's `color_transfer`: `smpte2084` → `HDR10`, `arib-std-b67` → `HLG`, anything else → `SDR`. Store ffprobe names. Map them through the same client table, which passes short names through.
  - Runs in the background thread or after startup so a large library doesn't block serving. A missing ffprobe or failure logs and leaves nulls, and it's retried next start. Rows with no file are skipped.

### 3. Subtitles in the player

- Discovery: reuse `library_layout._sidecars` logic (move it to `library_paths.py` if it needs to be shared). Subtitle files are `<stem>.<lang>.srt` (or `.vtt`) next to `file_path`.
- `GET /api/downloads/{id}/subtitles` → `[{lang, url}]`. The client builds the label with `Intl.DisplayNames` (e.g. `fr-orig` → "French (auto)"). Python's stdlib has no language-name table.
- `GET /api/downloads/{id}/subtitles/{lang}.vtt` → converts SRT→VTT on the fly (`WEBVTT\n\n` header, `,`→`.` in timestamp lines). Passes `.vtt` through. `Content-Type: text/vtt; charset=utf-8`. 404 for unknown lang. The lang is matched against discovered files, never joined into a path, so there's no traversal.
- `Watch.svelte`: fetch the list with the job. Render `<track kind="subtitles" src srclang label>` for each entry, with no `default` attribute (off until picked). Same origin, so no `crossorigin` is needed. Remove the comment saying files carry no captions.
- Audio-only items: no tracks.

### 4. Delete removes sidecars

- `delete_from_library` (`services/library.py`) also removes subtitle/transcript sidecars of the media file (same discovery as above). Sidecar removal errors are logged and ignored. **Builder's call** (not explicitly requested; prevents orphaned `.srt`/`.txt` files).

### 5. Bulk delete

- `POST /api/library/delete` body `{ids: number[]}` (max 500) → `{deleted: number[], failed: [{id, reason}]}`. Loops over `delete_from_library` and commits per item, so a partial failure keeps what succeeded.
- UI (`Library.svelte`, `JobCard.svelte`):
  - A "Select" button in the toolbar enters Select mode. Cards show a checkbox. Tapping a card toggles it instead of navigating. Esc / "Done" exits.
  - A sticky action bar shows `N selected · Select all · Delete`. "Select all" selects every item matching the current search+filter. On phones the bar sits above the tab bar (safe-area aware). On desktop it sits at the bottom of the content.
  - Delete asks once with a confirm ("Delete 3 videos and their files?"), using the existing two-step button pattern or a native `confirm()`. **Builder's call:** reuse the existing inline two-step "Confirm delete" pattern for consistency. Show a toast with the result ("Deleted 3" / "Deleted 2, 1 failed").
  - Selection clears when the search or filter changes so that it only covers items you can see.
- Single delete keeps working as today.

### 6. Library toolbar: search, sort, filter

- Remove `Chips.svelte` usage from Library, and the component if nothing else uses it. The Library shows **finished items only**. In-progress items live in the Queue (the tab bar badge already shows active work). Remove the Downloading/active merging from `lib/library.ts`.
- Toolbar: `[Search……] [Sort ▾] [Filter ▾] [Select]`.
- Sort (native `<select>` styled like `QualitySelect`):
  - Date added, newest (default) · Date added, oldest · Title A–Z · Duration, longest · File size, largest.
  - "Date added" = `finished_at`, falling back to `created_at`.
- Filter (desktop popover; phone `BottomSheet`):
  - Type: Any / Video / Audio.
  - Channel: options built from distinct `uploader` values with counts, sorted by name.
  - Playlist: options built from distinct `playlist_title` values, which means `JobOut` must expose `playlist_title` (and `playlist_channel`, for display). Add those fields.
  - Active filters show as removable pills under the toolbar ("Channel: X ✕"), plus "Clear filters".
- Sort and filter apply on the client after the server-side `q` search. They're stored in `localStorage` (`yt.library.view`). A stored channel or playlist that no longer exists is ignored.
- Empty state when filters match nothing: "No videos match these filters" + Clear filters.

### 7. Queue: dismiss all failed

- `POST /api/queue/dismiss-failed` → `{dismissed: n}`. Same semantics as per-job dismiss, applied to every `error` row.
- `Queue.svelte`: a "Dismiss all" button in the Failed section header, shown when there are 2+ failed jobs. One click, no confirm (dismiss isn't destructive: no files, and it can be re-queued from the URL). Toast "Dismissed N".

## Testing

- Server unit: player_client/skip args; `pick_subtitle_langs` table (fr auto-only → `fr-orig`; manual fr+en → `fr, en`; en manual → `en`; translated keys never picked; nothing available → `[]`); subtitle 429 → retry without subs → `done` + warning; media error still fails; SRT→VTT conversion; subtitle discovery; codec extraction incl. merged formats; ffprobe backfill (mock subprocess); bulk delete partial failure; dismiss-failed.
- API tests for the new endpoints. Migration upgrade/downgrade test if the existing pattern has one.
- Web unit: `codecs.ts` mapping; library sort/filter/selection functions in `lib/library.ts`.
- E2E: `library.spec.ts` (sort, filter, select-delete on desktop and phone viewports), `queue.spec.ts` (dismiss all), `video.spec.ts`/watch (metadata line with dynamic range and codecs; `<track>` elements present, none default).
- Manual: download playlist `QaVuJI6Mkv0`'s list. No SABR warning, no 429, French subs show in the player when picked.

## Left to the builder

The items marked **Builder's call** above, plus file/component boundaries within the existing structure, exact copy, and the visual details within `DESIGN.md` (checked against the impeccable / design-taste-frontend skills).
