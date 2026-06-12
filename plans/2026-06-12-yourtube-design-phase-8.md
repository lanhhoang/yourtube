# Phase 8: Stream Metadata + Contract Enrichment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expose richer stream metadata so the UI can render separate video and audio tables without guessing from raw yt-dlp payloads in the template.

**Architecture:** Keep the existing `InfoResponse` contract but extend it additively. The downloader service remains the only place that translates yt-dlp formats into app-level metadata, and both `/api/info` and `/info/form` consume the same normalized shape.

**Tech Stack:** Python 3.12, FastAPI, Pydantic, Jinja2, yt-dlp, pytest, uv

---

## File Structure

```
yourtube/
├── app/
│   ├── schemas.py
│   ├── routes/
│   │   ├── api.py
│   │   └── pages.py
│   └── services/
│       └── downloader.py
└── tests/
    ├── unit/
    │   └── test_downloader_format.py
    └── integration/
        └── test_api_info.py
```

Responsibilities:

- `app.schemas.FormatInfo` grows additive fields for stream typing and audio channel counts.
- `app.services.downloader.normalize_formats()` becomes the only place that decides whether a format is `video`, `audio`, or `muxed`.
- `app.routes.api` and `app.routes.pages` pass the richer metadata through unchanged.

### Task 1: Add stream-kind and channel metadata to `FormatInfo`

**Files:**
- Modify: `app/schemas.py`
- Modify: `app/services/downloader.py`
- Test: `tests/unit/test_downloader_format.py`

- [ ] **Step 1: Write the failing normalization tests**

```python
def test_normalize_video_only_format_sets_stream_kind() -> None:
    info = _make_info(
        {
            "format_id": "401",
            "ext": "mp4",
            "vcodec": "av01.0.08M.08",
            "acodec": "none",
            "height": 2160,
        }
    )
    f = normalize_formats(info)[0]
    assert f.stream_kind == "video"


def test_normalize_audio_only_format_sets_channels() -> None:
    info = _make_info(
        {
            "format_id": "251",
            "ext": "webm",
            "vcodec": "none",
            "acodec": "opus",
            "abr": 160.0,
            "audio_channels": 2,
        }
    )
    f = normalize_formats(info)[0]
    assert f.stream_kind == "audio"
    assert f.audio_channels == 2
```

- [ ] **Step 2: Run the normalization tests to verify they fail**

Run: `uv run pytest tests/unit/test_downloader_format.py::test_normalize_video_only_format_sets_stream_kind tests/unit/test_downloader_format.py::test_normalize_audio_only_format_sets_channels -v`

Expected: FAIL because `FormatInfo` does not include `stream_kind` or `audio_channels`.

- [ ] **Step 3: Extend the schema and normalization logic**

```python
# app/schemas.py
class FormatInfo(BaseModel):
    format_id: str
    ext: str
    stream_kind: str = "muxed"
    audio_channels: int | None = None
    resolution: str | None = None
    height: int | None = None
    width: int | None = None
    fps: float | None = None
    vcodec: str | None = None
    acodec: str | None = None
    abr: float | None = None
    vbr: float | None = None
    filesize: int | None = None
    tbr: float | None = None
    format_note: str | None = None
    container: str | None = None
```

```python
# app/services/downloader.py
def _stream_kind(vcodec: str | None, acodec: str | None) -> str:
    if vcodec == "none" and acodec and acodec != "none":
        return "audio"
    if acodec == "none" and vcodec and vcodec != "none":
        return "video"
    return "muxed"
```

- [ ] **Step 4: Run the unit tests to verify they pass**

Run: `uv run pytest tests/unit/test_downloader_format.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/schemas.py app/services/downloader.py tests/unit/test_downloader_format.py
git commit -m "feat: enrich normalized formats with stream type metadata"
```

### Task 2: Pass enriched format metadata through the API and page routes

**Files:**
- Modify: `app/routes/api.py`
- Modify: `app/routes/pages.py`
- Test: `tests/integration/test_api_info.py`

- [ ] **Step 1: Write the failing API regression test**

```python
def test_fetch_info_returns_stream_kind_and_audio_channels(monkeypatch) -> None:
    def fake_extract_info(url: str, **_kwargs):
        return {
            "url": url,
            "title": "Example title",
            "formats": [
                {"format_id": "401", "ext": "mp4", "vcodec": "avc1", "acodec": "none", "height": 2160},
                {"format_id": "251", "ext": "webm", "vcodec": "none", "acodec": "opus", "audio_channels": 2},
            ],
            "captions": {},
        }

    monkeypatch.setattr("app.routes.api.extract_info", fake_extract_info)

    with TestClient(app) as client:
        response = client.post("/api/info", json={"url": "https://example.com/watch?v=1"})

    payload = response.json()
    assert payload["formats"][0]["stream_kind"] == "video"
    assert payload["formats"][1]["stream_kind"] == "audio"
    assert payload["formats"][1]["audio_channels"] == 2
    assert payload["formats"][1]["acodec"] == "opus"
```

- [ ] **Step 2: Run the API test to verify it fails**

Run: `uv run pytest tests/integration/test_api_info.py::test_fetch_info_returns_stream_kind_and_audio_channels -v`

Expected: FAIL because `InfoResponse` does not include the new fields yet.

- [ ] **Step 3: Keep route contracts additive and pass the richer formats through**

```python
# app/routes/api.py
return InfoResponse(
    url=raw.get("url") or body.url,
    title=raw.get("title", ""),
    uploader=raw.get("uploader"),
    duration=raw.get("duration"),
    thumbnail=raw.get("thumbnail"),
    formats=normalize_formats(raw),
    captions=raw.get("captions") or {},
)
```

```python
# app/routes/pages.py
formats = normalize_formats(raw)
return templates.TemplateResponse(
    request,
    "partials/info_result.html",
    {
        "url": url,
        "title": raw.get("title", ""),
        "uploader": raw.get("uploader"),
        "duration": raw.get("duration"),
        "thumbnail": raw.get("thumbnail"),
        "formats": formats,
    },
)
```

- [ ] **Step 4: Run the integration tests to verify they pass**

Run: `uv run pytest tests/integration/test_api_info.py -v`

Expected: PASS for enriched format metadata.

- [ ] **Step 5: Commit**

```bash
git add app/routes/api.py app/routes/pages.py tests/integration/test_api_info.py
git commit -m "feat: expose enriched stream metadata through info routes"
```
