# MP4 downloads, channel folders, phone PWA and notifications — design

Date: 2026-11-18. Status: draft for owner approval.

## Intent

YourTube is used at a computer today. The owner wants to use it from their iPhone too: copy a video or playlist link in the YouTube app and paste it into YourTube to queue it, check progress, get notified when downloads finish or fail, and watch or save finished files. They also want files that play anywhere (MP4), a library on disk that is organised by channel and playlist, and two small shell fixes (a logo icon, an icon theme switch).

Success: copy a YouTube link, open the iPhone home-screen app, paste it and queue it, lock the phone, get a push when it lands, open it in the library and play or save it. On disk, the file sits at `downloads/<channel>/<playlist>/<title>.mp4`.

## Goals

1. Capped video downloads (`best`, `2160`, `1440`, `1080`, `720`, `480`) always produce `.mp4`, with the highest resolution up to the cap, H.264 + AAC wherever YouTube offers it at that resolution, and VP9 SDR + AAC above 1080p.
2. Default layout on disk: `<channel>/<title>.<ext>`, or `<channel>/<playlist>/<title>.<ext>` for videos queued from a playlist. Every segment is an ASCII slug: lowercase, transliterated, dashes. Existing library files are moved into this layout once.
3. The YourTube player mark sits next to the "yourtube" wordmark, and the favicon becomes the new play-circle.
4. The theme switch in the left rail is one icon button that cycles Dark → Light → System.
5. The app is reachable from the phone through Tailscale HTTPS, and the bind address is configurable for plain LAN http.
6. The app installs as a PWA on iPhone (and Android/desktop) and has a phone layout for every screen.
7. Web Push and in-app toasts for: single download finished, single download failed, playlist batch done.
8. A player for finished files, plus Save.

## Non-goals

- Offline use. The PWA caches the app shell only; no media or API data offline.
- Re-encoding. Streams are copied and remuxed, never transcoded.
- Login or multi-user accounts. Tailscale is the access boundary.
- Exposing the app to the public internet.
- HDR output unless the job asks for it (see 2026-11-18-hdr-option-design.md).
- Local macOS runs without ffmpeg. The owner runs YourTube in Docker/Podman or on Linux, where ffmpeg is installed. No ffmpeg diagnostic is added.

## Anti-goals (failure even if it works)

- A notification flood: a 500-video playlist must not send 500 pushes.
- Breaking or losing existing library files during the move.
- Generic "AI-made" UI, or phone screens that are just the desktop squeezed down.
- Anything that loads from a CDN at runtime.
- Silently downloading below the chosen cap (existing principle; unchanged).

## Constraints

- Stack stays: FastAPI + yt-dlp + SQLite (Alembic) + worker threads; Svelte 5 + Vite + Tailwind 4; one process, one port; Docker image ships everything.
- `DESIGN.md` is the visual contract; red is the only accent; WCAG AA in both themes; status never by colour alone.
- iOS rules: PWA install and Web Push need HTTPS and a home-screen install (iOS 16.4+). iOS has no Web Share Target for PWAs.
- yt-dlp 2026.10.26 behaviour (verified against YouTube on 2026-11-18, see Appendix).
- `PRODUCT.md` and `DESIGN.md` currently say "computer only" and list PWA, live push, notification bells and in-browser playback as out of scope. They are updated as part of this work.

## Approaches

### Push notifications

- **A. Server-sent Web Push (chosen).** The worker sends pushes with `pywebpush` and a VAPID key pair. Arrives with the app closed, including the iPhone home-screen app. Cost: one Python dependency, a subscriptions table, a small custom service worker.
- B. Browser notifications from the 2 s poll. No server work, but nothing arrives once the app is closed or suspended, which is the phone case. Rejected.
- C. Hosted relay (ntfy etc.). Needs another phone app and breaks "self-contained". Rejected.

### Moving existing files into channel folders

- **A. One-off step at startup, flagged in settings (chosen).** Automatic and idempotent; failures leave files in place and still served.
- B. A "Reorganise library" button in Settings. Owner controls timing but it is UI for a one-time event. Rejected.
- C. Alembic data migration. Migrations should not move files. Rejected.

Other items have one sensible way (yt-dlp sort keys for MP4, `vite-plugin-pwa` as in the owner's `apprendre-le-francais` app, `tailscale serve` for HTTPS).

## Decisions

### 1. Format selection (server, `app/services/quality.py`)

For every numeric cap and `best`:

```
format         = "bv*+ba/b"
format_sort    = ["res[:N]", "hdr:sdr", "vcodec:h264", "acodec:aac", <abr:K if audio bitrate set>]
merge_output_format = "mp4"
```

- `res` with no number for `best`; `res:N` for a numeric cap (existing short-side rule).
- `hdr:sdr` must be explicit so a 4K HDR upload never yields HDR10.
- Verified picks on a 4K60 HDR test video: best → VP9 2160p60 SDR + AAC 129k, `.mp4`; 1440 → VP9 + AAC; 1080 → H.264 1080p60 + AAC.
- `audio` cap and exact format ids are unchanged (owner chose those streams deliberately). Exact ids keep the existing `expected_container_by_pair` rule.
- If the fallback `/b` is used (no separate streams), the file is whatever YouTube muxed (format 18 is MP4).
- Existing quality tests and `quality_cases.json` fixtures are updated.

### 2. Channel and playlist folders

Default template (no custom template):

- From a playlist: `<playlist-owner-channel>/<playlist>/<title>.<ext>` (owner's choice: the whole playlist lands in one folder even when it mixes channels)
- Otherwise: `<channel>/<title>.<ext>`

Slug rule (one function, server side): transliterate to ASCII (Unicode NFKD plus a transliteration library such as `Unidecode` / `anyascii`, builder's choice), lowercase, every run of non-`[a-z0-9]` becomes one `-`, trim dashes, cap each segment at 80 characters. If a segment is empty after slugging (e.g. `東京` with no transliteration), fall back: channel → `channel_id`, then `uploader_id`, then `unknown-channel`; playlist → `playlist_id`; title → video `id`.

- Channel name: for single videos, the video's yt-dlp `channel`, then `uploader`. For playlist videos, the playlist's `channel`, then `uploader` (from the flat playlist info the sources service already fetches); if the playlist has no owner (e.g. a mix), fall back to the video's channel.
- Playlist name: the playlist title the browser already shows on the playlist view. The sources response gains `playlist_channel` alongside the playlist title. Both are sent per job in new `playlist_title` and `playlist_channel` fields on `JobCreate` and stored on new nullable `downloads.playlist_title` / `downloads.playlist_channel` columns (one Alembic migration). `null` for single videos and multi-URL fetches.
- Implementation: the path is computed in the worker after yt-dlp resolves info (so `channel`/`id` are known) and passed to yt-dlp as the output template (e.g. via a `prepare_filename`-time hook or by pre-resolving info then downloading with a fixed template — builder's choice). The existing output guard still applies.
- Name collisions: if `<path>.mp4` already exists for a different job, append `-<video id>` to the title segment.
- Subtitle sidecars (`.srt`, `.txt`) follow the video file (yt-dlp does this when the template is shared).
- A custom output template on a job still overrides the default layout.

One-off move of existing files (lifespan, after migrations and before workers start):

- Runs once; a settings row `library_layout = "v2"` records completion. Skips if present.
- Only files under the current downloads folder are moved, and they are reorganised inside it (a move within one filesystem, so it is a rename). Files elsewhere (an older downloads folder, an absolute custom template) are left in place, counted as skipped, and logged (my call: avoids slow, risky cross-volume copies at startup).
- For each `done` row with a `file_path` that exists: compute the new path from `uploader` + `title` (no playlist info exists for old rows, so they go to `<channel>/<title>.<ext>`), move the file and any same-stem sidecars, update `file_path`. Missing files are skipped. A failed move is logged and the row keeps its old path (still served and deletable).
- Rows whose old file was produced by a relative custom template are moved too (owner asked for the whole library organised).
- Leaves empty old directories alone.
- Logs a one-line summary: moved / skipped / failed counts.

### 3. Logo icon

Two owner-supplied marks (2026-11-18):

- **Top-bar mark:** a red rounded screen with a white play triangle and a pale scrub bar (about 1.44:1). It replaces the red bar in the wordmark, 20 px tall (inline SVG, `aria-hidden`; the link keeps "yourtube" as its name).
- **Favicon:** a two-tone red play-circle with a white triangle. It replaces `apps/web/public/favicon.svg` and is the source for the PWA icons. The circle reads better than the wide player mark on a square home-screen tile.

Both are fixed brand artwork, the same in both themes, outside the `accent` token.

### 4. Theme switch

`ThemeSelect` in the rail becomes one rail-style tile button:

- Shows the current choice: moon (Dark), sun (Light), monitor (System).
- Click cycles Dark → Light → System → Dark.
- `aria-label` and `title`: "Theme: Dark. Switch to Light" (etc.).
- The Settings page keeps a labelled three-option control (it has room for words); both share the same module state as today.
- On phones the theme control lives in Settings only (no rail).

### 5. Network access

- New docs section: `tailscale serve --bg 8000` on the host (Linux, or the Docker host), giving `https://<host>.<tailnet>.ts.net`. The app keeps speaking plain HTTP; Tailscale terminates TLS.
- `pnpm start` / `pnpm dev` read `YT_HOST` (default stays `127.0.0.1`); `.env.example` documents `YT_HOST=0.0.0.0` for LAN http. Compose already binds `0.0.0.0`.
- Vite dev server: `host: true` only when `YT_HOST` is not localhost (builder's choice of mechanism).

### 6. PWA

- `vite-plugin-pwa` with `registerType: "autoUpdate"` and `injectManifest` strategy (needed for the custom push handlers), app-shell precache only, `navigateFallbackDenylist` for `/api/` and `/health`.
- Manifest: name "YourTube", short name "YourTube", `display: standalone`, `start_url: "/"`, theme/background colours from `bg` (dark `#0b0b0c`), icons 64/192/512, maskable 512, apple-touch-icon 180, generated from the play-circle favicon.
- `index.html`: viewport with `viewport-fit=cover`, `theme-color` (light and dark media variants), Apple web-app meta tags, `apple-touch-icon`.
- Android/desktop: `share_target` (GET) to `/?share=<url>` → app reads it and routes to fetch. Harmless on iOS.
- iOS: the main way in is copy and paste (owner's choice). Copy the link in the YouTube app, open YourTube, paste it into the top-bar field. On phones, while the field is empty, a Paste button sits beside it and calls `navigator.clipboard.readText()` on tap (iOS shows its own "Paste" confirmation); if reading fails, the field gets focus so the owner can long-press and paste. Pasting a URL does not auto-fetch; the owner taps Fetch (my call: keeps the existing behaviour and avoids surprise lookups).
- Optional extra, docs only: the README describes an iOS Shortcut "Send to YourTube" (Receive URLs from Share Sheet → Open URL `https://<host>/#/fetch/<url-encoded>`), which the existing `#/fetch/<urls>` route already handles. No app code depends on it.

### 7. Phone layout

Breakpoint: below 768 px is the phone layout. Every screen works there.

- Left rail becomes a bottom tab bar (Library, Queue with red count, Settings), respecting `safe-area-inset-bottom`.
- Top bar: logo mark only (wordmark hidden), URL field takes the remaining width, Fetch button, options menu. Multi-line paste still works.
- Library: single-column list, thumbnail left, title/meta right. Tap opens the player.
- Queue: single column; progress and actions reachable with the thumb (44 px targets).
- Fetch video view and playlist picker: stacked; the override panel becomes a bottom sheet.
- Settings: stacked form.
- Toasts: top of the screen on phones, below the status bar.
- `DESIGN.md` gains a "Phone" section (breakpoint, tab bar, target sizes, safe areas) and drops the 960 px minimum.

The design process follows the Impeccable skill (shape → build → critique → polish, using `DESIGN.md`/`PRODUCT.md` as context) and a final pass against taste-skill's anti-slop checks. Mockups for the phone layout are shown to the owner and approved before the phone layout is built (a hard stop inside Phase 3). The PWA, player and `inline` flag do not depend on the mockups and can go ahead first.

### 8. Player and Save

- Tapping or clicking a finished item opens a player view `#/watch/<id>`: native `<video controls playsinline>` (or `<audio>` for audio jobs) with `src=/api/downloads/<id>/file?inline=1`, title, channel, size/format meta, and actions Save and Delete.
- `/api/downloads/{id}/file` gains an `inline` query flag that serves `Content-Disposition: inline` (default stays `attachment`). Starlette's `FileResponse` already serves `Range` requests, which iOS needs for video.
- Save: on devices with `navigator.canShare({ files })`, Save fetches the file and opens the share sheet (Save to Files/Photos); otherwise it is the existing download link. Large files (over ~500 MB) skip share-sheet and use the download link (builder may tune the threshold).
- If the browser cannot play the codec (e.g. VP9 on some Apple devices), the player shows "This device can't play this file. Save it and open it in VLC." with Save.
- Desktop: the same view, centred, max width per `DESIGN.md`.

### 9. Notifications

Events:

| Event | Push | Toast (app open) |
|---|---|---|
| Single video done | "Downloaded" + title | yes (existing) |
| Single video failed | "Download failed" + title + friendly error | yes (new) |
| Playlist batch settled | "<playlist>: 12 downloaded, 1 failed" | yes (new) |

- Batch: jobs created by one `POST` enqueue request with more than one job share a new nullable `downloads.batch_id` (UUID). When the last job of a batch reaches `done`, `error` or `cancelled`, one summary push is sent. Jobs in a batch send no per-job push, and toasts for a batch are summary-only too (my call, to avoid noise). Retrying a failed batch job does not re-trigger a batch summary (the retried job notifies as a single job).
- Recipients: every subscribed device gets every push (owner's choice). A job queued from Safari still notifies the home-screen app.
- Summary counts come from the database (`batch_id` group), not from the queue endpoint, which only returns the 20 most recent finished jobs. A multi-URL batch is named "N videos" in its push.
- App in the foreground: the service worker always shows the push (iOS requires a visible notification for every push or it may revoke the subscription). The in-app toast still shows too. A duplicate on the device that is open is accepted (my call).
- Delivery: `pywebpush` from the worker thread after `release_job` commits. Failures are logged and never fail the job. `404/410` responses delete the subscription.
- VAPID keys: generated on first start and stored in `YT_DATA_DIR/vapid.json` (or overridden by `YT_VAPID_PRIVATE_KEY`/`YT_VAPID_PUBLIC_KEY`); subject `mailto:` from `YT_VAPID_SUBJECT`, default a placeholder.
- API: `GET /api/push/key`, `POST /api/push/subscriptions` (upsert by endpoint), `DELETE /api/push/subscriptions` (by endpoint).
- Table `push_subscriptions(id, endpoint unique, p256dh, auth, user_agent, created_at)` (Alembic).
- Settings page: "Notifications on this device" toggle. Turning it on asks permission (must be a user tap; iOS requirement) and subscribes. If the app isn't installed on iOS, the toggle explains "Add YourTube to your Home Screen first".
- Service worker: `push` handler shows the notification (title, body, icon, `tag` per job or batch); `notificationclick` focuses or opens the app at `#/watch/<id>` (done), `#/queue` (failed or batch).
- Toasts gain variants: done, failed (danger), batch summary. Today's toast logic (poll diff on completed) extends to failed jobs and batches.

### 10. Docs

- `PRODUCT.md`: platform web + phone PWA; users include the phone; remove PWA, push and playback from out-of-scope; keep "no recommendations, avatars, view counts" (a notification toggle is not a bell).
- `DESIGN.md`: phone section, logo mark, theme tile, toast variants, player.
- `README.md`: Tailscale setup, iOS install, copy-paste flow, optional Shortcut, notifications, new env vars, disk layout.

## Delivery phases

Each phase is shippable on its own.

1. **Downloads:** MP4 sort, slug + channel/playlist folders, `playlist_title` column, one-off move.
2. **Shell:** logo mark, theme tile.
3. **Phone:** phone layout for all screens, player + Save, `inline` file flag, PWA manifest/icons/service worker, phone Paste button, `YT_HOST`, Tailscale + install docs, PRODUCT/DESIGN updates.
4. **Notifications:** batches, VAPID, subscriptions, worker push, Settings toggle, toast variants.

## Left to the builder

- Transliteration library choice.
- How the worker injects the computed path into yt-dlp.
- Exact Save threshold, icon artwork export pipeline, VAPID subject default.
- Component structure in Svelte; test layout (follow existing patterns: pytest unit/api/integration, vitest, Playwright e2e).

## Appendix: verified format behaviour (yt-dlp 2026.10.26, 2026-11-18)

Test video `LXb3EKWsInQ` (4K60 HDR). Offered: H.264 up to 1080p60; VP9 SDR up to 2160p60; VP9.2/AV1 HDR up to 2160p60; audio AAC 140 (129k, 44.1 kHz), Opus 251 (133k, 48 kHz), plus DRC variants.

| Sort | Pick | Result |
|---|---|---|
| `res` (yt-dlp default) | 701+251 | AV1 2160p60 HDR10 + Opus |
| `res,hdr:sdr,vcodec:h264,acodec:aac` | 315+140 | VP9 2160p60 SDR + AAC, mp4 |
| `res:1440,...` | 308+140 | VP9 1440p60 + AAC, mp4 |
| `res:1080,...` | 299+140 | H.264 1080p60 + AAC, mp4 |

AAC vs Opus at YouTube bitrates: audibly equivalent; AAC chosen for Apple playback in MP4.
