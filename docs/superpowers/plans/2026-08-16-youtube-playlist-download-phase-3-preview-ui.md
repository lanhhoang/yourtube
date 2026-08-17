# YouTube Playlist Download — Phase 3: Paginated Preview UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this phase task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire the settings-aware preview service into the existing batch form and render paginated playlist results while preserving the current per-video and batch enqueue actions.

**Architecture:** Keep one HTMX route, `POST /info/batch/form`. The route reads the source text, page number, and saved-proxy/cookies flags, resolves the current `RuntimeSettings.playlist_page_size`, and swaps only `#batch-result`. `batch_result.html` owns page summary and navigation; the existing `batch_preview_card.html` remains responsible for ready/error cards and individual `/downloads/form` actions.

**Tech Stack:** FastAPI, Jinja2, HTMX, Alpine.js, pytest.

**Spec:** `docs/superpowers/specs/2026-08-16-youtube-playlist-download-design.md`

**Parent plan:** `docs/superpowers/plans/2026-08-16-youtube-playlist-download-parent.md`

**Current-repo state:** Phases 1 and 2 are merged at `HEAD`. `RuntimeSettings.playlist_page_size`, the paginated `BatchPreviewResult`, and both `resolve_batch_preview` interfaces already exist and have passing unit coverage. Phase 3 changes only the route/template wiring and integration coverage.

## Global Constraints

- Preserve the existing `POST /info/batch/form` entry point, `batch_preview_card.html` individual enqueue forms, and current-page “Enqueue all valid” form.
- Read the persisted `RuntimeSettings.playlist_page_size` on every preview request and pass it to the existing preview facade as `page_size`.
- Read `page` as an integer form field with default `1`; the service remains responsible for clamping values outside the available range.
- Every navigation request resubmits the original `sources` text and the requested page. Preserve the checked `proxy` and `cookies` choices as hidden fields so page navigation uses the same extraction settings.
- Pagination controls use HTMX `POST /info/batch/form`, target `#batch-result`, and use `innerHTML` replacement. Add no client-side playlist state, route family, dependency, or CSS rule; existing `.button-row` styling is sufficient.
- Counts and ready/error cards remain page-local. The service’s `total_count`, `total_pages`, `has_previous`, and `has_next` are the source of truth for the fragment.

## Files

- Modify: `app/routes/pages.py`
- Modify: `app/templates/partials/batch_result.html`
- Test: `tests/integration/test_pages.py`

Do not modify `app/services/batch_preview.py`, `app/services/preview.py`, `app/templates/partials/batch_preview_card.html`, or `app/static/css/app.css` in this phase.

## Interfaces

`info_batch_form` accepts the existing fields plus the page number:

```python
def info_batch_form(
    request: Request,
    sources: str = Form(...),
    page: int = Form(default=1),
    proxy: str | None = Form(default=None),
    cookies: str | None = Form(default=None),
    session: Session = Depends(get_session),
) -> HTMLResponse:
```

The route calls the existing facade with the resolved runtime setting:

```python
result = resolve_batch_preview(
    sources,
    extract_info=extract_info,
    proxy=proxy_url,
    cookies_file=cookies_file,
    page=page,
    page_size=runtime.playlist_page_size,
)
```

The fragment context contains `result`, the original `sources`, boolean `use_proxy` and `use_cookies` flags, `previous_page`, `next_page`, and `stream_fields`. Navigation forms use hidden `sources`, optional hidden `proxy`/`cookies` values of `on`, and hidden `page` values.

## Steps

- [ ] **Step 1: Add failing integration coverage** in `tests/integration/test_pages.py`.
  - Update the existing route seam test to assert the default call includes `page == 1` and the resolved default `page_size == 20` while preserving the current proxy/cookies assertions.
  - Add a route test that persists `playlist_page_size == 2`, posts `page == 2`, `proxy`, and `cookies`, and asserts the resolver receives `page=2`, `page_size=2`, the saved proxy URL, and the saved cookies path.
  - Add rendering coverage for a multi-page `BatchPreviewResult`: assert `Page 2 of 3`, the total count, `hx-post="/info/batch/form"`, `hx-target="#batch-result"`, `hx-swap="innerHTML"`, hidden original source text, hidden page values `1` and `3`, and preserved proxy/cookies fields.
  - Assert the previous control is enabled and the next control is enabled on a middle page; assert the appropriate button is disabled at the first and last pages. The empty/default result keeps both controls disabled.
  - Keep the existing assertions for ready cards, visible error cards, the current-page enqueue form, and the active stream-field contract.

- [ ] **Step 2: Run the focused integration tests and confirm the new cases fail.**

  ```bash
  uv run pytest tests/integration/test_pages.py -q
  ```

  The pre-change route does not accept/forward `page`, does not pass the configured page size, and does not render pagination markup, so the new assertions must fail before implementation.

- [ ] **Step 3: Wire page and runtime settings through `app/routes/pages.py`.**

  Add `page: int = Form(default=1)`, pass `page` and `runtime.playlist_page_size` to `resolve_batch_preview`, and extend the template context:

  ```python
  {
      "result": result,
      "sources": sources,
      "use_proxy": bool(proxy),
      "use_cookies": bool(cookies),
      "previous_page": result.page - 1 if result.has_previous else result.page,
      "next_page": result.page + 1 if result.has_next else result.page,
      "stream_fields": STREAM_FIELDS,
  }
  ```

  Leave proxy/cookie runtime resolution and all other routes unchanged.

- [ ] **Step 4: Render the paginated fragment in `app/templates/partials/batch_result.html`.**

  Keep the existing summary, truncation compatibility notice, enqueue-all form, and item include. Add a page summary using `result.page`, `result.total_pages`, and `result.total_count`, then render a navigation block with two independent forms:

  ```html
  <nav aria-label="Batch preview pages" class="button-row">
    <form
      hx-post="/info/batch/form"
      hx-target="#batch-result"
      hx-swap="innerHTML"
    >
      <input type="hidden" name="sources" value="{{ sources }}" />
      <input type="hidden" name="page" value="{{ previous_page }}" />
      <button type="submit" {% if not result.has_previous %}disabled{% endif %}>
        Previous
      </button>
    </form>
    <span>Page {{ result.page }} of {{ result.total_pages }}</span>
    <form
      hx-post="/info/batch/form"
      hx-target="#batch-result"
      hx-swap="innerHTML"
    >
      <input type="hidden" name="sources" value="{{ sources }}" />
      <input type="hidden" name="page" value="{{ next_page }}" />
      <button type="submit" {% if not result.has_next %}disabled{% endif %}>
        Next
      </button>
    </form>
  </nav>
  ```

  Set `previous_page` to `result.page - 1` when `has_previous` is true, otherwise `result.page`; set `next_page` to `result.page + 1` when `has_next` is true, otherwise `result.page`. Include hidden `proxy` and `cookies` fields with value `on` when their context flags are true. Do not nest the navigation forms inside the existing enqueue form, and do not change `batch_preview_card.html`.

- [ ] **Step 5: Run the focused integration and regression checks.**

  ```bash
  uv run pytest tests/integration/test_pages.py tests/unit/test_preview.py tests/unit/test_batch_preview.py -q
  ```

  Confirm the existing direct-source, friendly-error, ready-card, individual enqueue, and current batch enqueue tests remain green alongside the new pagination cases.

- [ ] **Step 6: Commit the phase implementation.**

  ```bash
  git add app/routes/pages.py app/templates/partials/batch_result.html tests/integration/test_pages.py
  git commit -m "feat: add paginated playlist preview UI"
  ```

## Usable result

Users can paste a playlist or mixed sources into the existing batch form, inspect one configured-size page at a time, navigate with the original source and extraction settings intact, and individually add any ready video through the existing queue action.
