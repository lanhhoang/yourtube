# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

The owner and the few people they share the server with (inferred from "self-hosted" and "this one is yours"). They sit at a computer, paste a YouTube video or playlist URL, choose a quality, and expect the file to be in their library later. They come back to the library to get files they already downloaded. Computer only for now; phone layouts are out of scope.

## Product Purpose

YourTube is a self-hosted YouTube downloader with a web UI, a persistent queue and a library. It exists so the owner can keep their own copies of videos and playlists without a third-party site. Success: paste a URL from anywhere, see what will be downloaded and at what quality before queueing, and find the finished files in the library.

## Positioning

"There are many video-sharing platforms, but this one is yours." It runs on the owner's machine, keeps its data in their folders, and loads nothing from a CDN at runtime.

## Operating Context

- One container, one process, one port (`docker compose up`, or `pnpm dev` / `pnpm start` locally).
- FastAPI backend with yt-dlp and ffmpeg; a SQLite-backed queue with worker threads; the Svelte app is built and served by FastAPI.
- Playlists can be large (up to 500 entries per fetch). YouTube has returned 403s for bursts of lookups, so the browser checks at most two videos at a time.
- The old HTMX UI keeps working at `/` until Phase 6; the new app is at `/app` until then.

## Capabilities and Constraints

- Single video, playlist and multi-URL fetch from a top-bar field; Library, Queue (with retry and dismiss for failed jobs) and Settings screens.
- Quality is a per-job cap: `best`, `2160`, `1440`, `1080`, `720`, `480`, `audio`. Default "Up to 1080p". The cap compares the short side of the video. Exact format ids override the cap.
- Playlists: one cap for all selected videos, per-video override, every selected video checked before "Add to queue" is enabled. A video must never silently download below the chosen quality without being flagged first.
- Terms: "cap" (quality limit), "Library" (finished downloads), "Queue" (queued, active and failed jobs).
- Not in scope: in-browser playback, translation, PWA/offline, live push, server-side playlist checking.

## Brand Commitments

Name: YourTube. Tagline: "There are many video-sharing platforms, but this one is yours." Layout grammar borrowed from YouTube (top bar, left rail, chips, thumbnail grid) without its clutter: no recommendations, avatars, view counts or notification bells. Red is the only accent.

## Evidence on Hand

Approved mockups, local and gitignored: `.superpowers/brainstorm/11221-1794783582/content/direction-v2.html` and `playlist-quality.html`. The existing logo asset is `apps/server/app/static/assets/favicon.svg`. There are no user testimonials or usage data; none should be invented.

## Product Principles

1. **Show before you commit.** Quality and availability are visible before anything is queued.
2. **Fewer elements, not grey boxes.** Minimal means removing things; thumbnails carry the colour.
3. **Be gentle with YouTube.** Few parallel lookups; no work in the background after leaving a page.
4. **Self-contained.** Everything ships in the image; no runtime CDN.
5. **Say what went wrong.** Failures show a plain message and a way forward (retry, dismiss).

## Accessibility & Inclusion

Text and controls must meet WCAG AA contrast in both dark and light themes. All controls are reachable by keyboard. Status is never conveyed by colour alone (badges carry text).
