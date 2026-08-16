# YouTube Playlist Extraction and Download

## Goal

Allow the existing batch source form to accept YouTube playlist URLs, preview playlist videos in pages, and enqueue selected videos as independent download jobs.

## Approved behavior

- The existing “Queue many sources” form accepts mixed direct video URLs and YouTube playlist URLs.
- Playlist entries are expanded with yt-dlp flat extraction. Order is preserved and exact duplicate video URLs are removed in first-seen order.
- Entry URL resolution prefers `webpage_url`, then a full `url`, then a YouTube watch URL built from the entry ID.
- Entries without a usable URL remain visible as error rows; they are not silently discarded.
- Full metadata and format extraction runs only for the current page. The default page size is 20 and is configurable from Settings with a valid range of 1–50. There is no playlist-wide cap.
- Pagination is page-local. Navigation resubmits the source text and page number; selections and format choices do not persist across pages.
- Ready rows are selected by default. Each row keeps the existing per-video format picker and individual enqueue action. A bulk action queues only selected rows from the current page.
- Each selected video becomes an existing independent `Download` job. A failed extraction or download does not abort other entries.
- Playlist extraction errors use the existing friendly yt-dlp error mapping.

## Interfaces

Extend `BatchPreviewResult` with `page`, `page_size`, `total_count`, `total_pages`, `has_previous`, and `has_next`. Existing `valid_count` and `invalid_count` describe the current page.

Extend `resolve_batch_preview` with `page: int = 1` and `page_size: int = 20`. The existing `extract_info`, proxy, cookies, and optional playlist-expansion seams remain injectable for tests.

Add `playlist_page_size: int` to `RuntimeSettings` and the persisted settings catalog. Use the key `playlist_page_size`, default value `20`, and reject values outside `1..50`.

`POST /info/batch/form` accepts `sources` and optional `page`; it returns the existing batch HTML fragment with pagination controls. Pagination controls submit the original source text and target page through HTMX.

Bulk enqueue submits `selected_index` values plus indexed row fields such as `url_0`, `title_0`, `video_format_id_0`, and `subtitles_0`. `build_batch_downloads` filters rows by selected index. Existing single-item and raw direct-URL paths remain supported.

## Failure and consistency rules

- A playlist flat-extraction exception produces one error item for that source and does not stop other sources.
- A missing or invalid playlist entry URL produces an error item labeled with its playlist position.
- Metadata extraction failures are rendered as error items and counted in the current page.
- A page outside the available range is clamped to the last page; an empty result remains page 1 with no navigation.
- Re-expanding on every page request intentionally avoids server-side playlist session state. Playlist changes between requests may shift page boundaries.

## Out of scope

- A playlist database/session model.
- Background playlist extraction.
- Cross-page selection persistence.
- Playlist grouping metadata in the download database.
- New dependencies, migrations, or public JSON APIs.

## Acceptance criteria

1. Pasting `https://www.youtube.com/playlist?list=PLJicmE8fK0EiKm0PfjNhjcUCZdJgYun3I` into the existing batch form returns a paginated preview.
2. No page renders more than the configured page size, and navigation reaches later entries.
3. Users can choose formats per video, deselect entries, and enqueue only selected rows.
4. Invalid entries remain visible while valid entries can still be queued.
5. Direct video batch behavior and individual video downloads remain unchanged.
