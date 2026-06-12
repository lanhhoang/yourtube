# Phase 8: Stream Metadata Contract Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expose additive stream metadata so later UI work can split video and audio streams without guessing from raw yt-dlp payloads.

**Architecture:** Keep `InfoResponse` stable and extend only `FormatInfo`. The downloader service remains the sole place that derives app-level stream metadata from yt-dlp fields, and the existing info routes continue forwarding `normalize_formats(raw)` unchanged.

**Tech Stack:** Python 3.12, FastAPI, Pydantic, yt-dlp, pytest, uv

---

## File Structure

```text
yourtube/
├── app/
│   ├── schemas.py
│   └── services/
│       └── downloader.py
└── tests/
    ├── unit/
    │   └── test_downloader_format.py
    └── integration/
        └── test_api_info.py
```

Responsibilities:

- `app.schemas.FormatInfo` owns the public metadata contract for each normalized stream.
- `app.services.downloader.normalize_formats()` decides whether each stream is `video`, `audio`, or `muxed`, and preserves audio channel counts when present.
- `tests/unit/test_downloader_format.py` verifies normalization behavior at the service seam.
- `tests/integration/test_api_info.py` verifies the new fields serialize through `POST /api/info` without route refactors.

## Contract Rules

- Add `stream_kind` as `Literal["video", "audio", "muxed"]`, defaulting to `"muxed"`.
- Add `audio_channels` as `int | None`.
- Classify a normalized format as:
  - `audio` when `vcodec == "none"` and `acodec` is present and not `"none"`.
  - `video` when `acodec == "none"` and `vcodec` is present and not `"none"`.
  - `muxed` for all other cases, including combined streams and missing codec metadata.
- Do not add template-facing grouping, `picker_payload`, or route-level transformation in this phase.

### Task 1: Extend the normalized format contract

**Files:**
- Modify: `app/schemas.py`
- Modify: `app/services/downloader.py`
- Test: `tests/unit/test_downloader_format.py`

- [ ] **Step 1: Write the failing unit tests**

```python
def test_normalize_combined_format_defaults_stream_kind_to_muxed() -> None:
    info = _make_info(
        {
            "format_id": "137+140",
            "ext": "mp4",
            "vcodec": "avc1.640028",
            "acodec": "mp4a.40.2",
        }
    )

    f = normalize_formats(info)[0]

    assert f.stream_kind == "muxed"
    assert f.audio_channels is None


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


def test_normalize_audio_only_format_sets_stream_kind_and_channels() -> None:
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


def test_normalize_missing_codecs_falls_back_to_muxed() -> None:
    info = _make_info(
        {
            "format_id": "999",
            "ext": "webm",
        }
    )

    f = normalize_formats(info)[0]

    assert f.stream_kind == "muxed"
    assert f.audio_channels is None
```

- [ ] **Step 2: Run the targeted unit tests to verify they fail**

Run: `uv run pytest tests/unit/test_downloader_format.py::test_normalize_combined_format_defaults_stream_kind_to_muxed tests/unit/test_downloader_format.py::test_normalize_video_only_format_sets_stream_kind tests/unit/test_downloader_format.py::test_normalize_audio_only_format_sets_stream_kind_and_channels tests/unit/test_downloader_format.py::test_normalize_missing_codecs_falls_back_to_muxed -v`

Expected: FAIL because `FormatInfo` does not yet define `stream_kind` or `audio_channels`.

- [ ] **Step 3: Implement the additive schema and normalization fields**

```python
# app/schemas.py
from typing import Literal


class FormatInfo(BaseModel):
    """A single format entry returned by the format picker."""

    format_id: str
    ext: str
    stream_kind: Literal["video", "audio", "muxed"] = "muxed"
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


def normalize_formats(info: dict) -> list[FormatInfo]:
    raw_formats = info.get("formats") or []
    out: list[FormatInfo] = []
    for raw in raw_formats:
        format_id = _safe_str(raw.get("format_id"))
        if format_id is None:
            continue
        vcodec = _format_codec(raw.get("vcodec"))
        acodec = _format_codec(raw.get("acodec"))
        out.append(
            FormatInfo(
                format_id=format_id,
                ext=_safe_str(raw.get("ext")) or "",
                stream_kind=_stream_kind(vcodec, acodec),
                audio_channels=_safe_int(raw.get("audio_channels")),
                resolution=_safe_str(raw.get("resolution")),
                height=_safe_int(raw.get("height")),
                width=_safe_int(raw.get("width")),
                fps=_safe_float(raw.get("fps")),
                vcodec=vcodec,
                acodec=acodec,
                abr=_safe_float(raw.get("abr")),
                vbr=_safe_float(raw.get("vbr")),
                filesize=_safe_int(raw.get("filesize")),
                tbr=_safe_float(raw.get("tbr")),
                format_note=_safe_str(raw.get("format_note")),
                container=_safe_str(raw.get("container")),
            )
        )
    return out
```

- [ ] **Step 4: Run the unit test file to verify it passes**

Run: `uv run pytest tests/unit/test_downloader_format.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/schemas.py app/services/downloader.py tests/unit/test_downloader_format.py
git commit -m "feat: enrich normalized formats with stream metadata"
```

### Task 2: Verify the new fields serialize through the API contract

**Files:**
- Modify: `tests/integration/test_api_info.py`
- Read-only context: `app/routes/api.py`

- [ ] **Step 1: Write the failing API regression test**

```python
def test_fetch_info_returns_stream_kind_and_audio_channels(monkeypatch) -> None:
    def fake_extract_info(url: str, **_kwargs):
        return {
            "url": url,
            "title": "Example title",
            "formats": [
                {
                    "format_id": "401",
                    "ext": "mp4",
                    "vcodec": "avc1",
                    "acodec": "none",
                    "height": 2160,
                },
                {
                    "format_id": "251",
                    "ext": "webm",
                    "vcodec": "none",
                    "acodec": "opus",
                    "audio_channels": 2,
                },
            ],
            "captions": {},
        }

    monkeypatch.setattr("app.routes.api.extract_info", fake_extract_info)

    with TestClient(app) as client:
        response = client.post("/api/info", json={"url": "https://example.com/watch?v=1"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["formats"][0]["stream_kind"] == "video"
    assert payload["formats"][1]["stream_kind"] == "audio"
    assert payload["formats"][1]["audio_channels"] == 2
```

- [ ] **Step 2: Run the targeted API test to verify it fails**

Run: `uv run pytest tests/integration/test_api_info.py::test_fetch_info_returns_stream_kind_and_audio_channels -v`

Expected: FAIL because the response model does not yet expose the new fields.

- [ ] **Step 3: Confirm no route code changes are needed**

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

Implementation note: do not edit `app/routes/api.py` or `app/routes/pages.py` unless the repo has diverged. The existing routes already forward normalized formats unchanged, which is the intended contract for this phase.

- [ ] **Step 4: Run the API test file to verify it passes**

Run: `uv run pytest tests/integration/test_api_info.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/integration/test_api_info.py app/schemas.py app/services/downloader.py
git commit -m "test: cover enriched info response metadata"
```

## Verification

- `uv run pytest tests/unit/test_downloader_format.py -v`
- `uv run pytest tests/integration/test_api_info.py -v`

## Out Of Scope

- Reworking `partials/info_result.html`
- Adding Alpine.js or `picker_payload`
- Splitting streams into separate collections on the server
- Changing `POST /downloads/form` request semantics
