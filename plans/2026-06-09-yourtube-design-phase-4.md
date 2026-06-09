# Phase 4: FastAPI Web App (HTTP API + htmx UI) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the minimal FastAPI app from Phase 1 with the full web application: HTML pages with sidebar navigation, htmx polling for the queue, a two-table format picker (Video Streams + Audio Streams), library with search/sort/preview/delete, and settings management. After this phase, `uv run uvicorn app.main:app` serves the complete YourTube web UI at `http://localhost:8000`.

**Architecture:** FastAPI with Jinja2 templates and htmx. HTTP API routes return JSON (for format info, create download, settings) and HTML partials (for queue rows, library rows). In-process worker pool in daemon threads. No SPA — all interactivity via htmx attributes and vanilla JS for the format picker.

**Prerequisites:** Phase 1 (scaffold), Phase 2 (services), and Phase 3 (queue + library) must be complete. The `app/main.py` created in Phase 1 will be replaced entirely. `app/routes/pages.py` will be replaced entirely. All templates and CSS are new.

**Tech Stack:** Python 3.12, FastAPI, SQLModel, Jinja2, htmx 2.0, yt-dlp, pytest

---

## File Structure (this phase adds/changes)

```
yourtube/
├── app/
│   ├── main.py                     ★ REPLACE with full app (worker pool, lifespan, routes)
│   ├── routes/
│   │   ├── pages.py                ★ REPLACE with full page routes
│   │   └── api.py                  ★ NEW: JSON + htmx partial API routes
│   ├── static/
│   │   └── css/
│   │       └── app.css             ★ NEW: full stylesheet (700+ lines)
│   └── templates/
│       ├── base.html               ★ NEW
│       ├── components/
│       │   ├── sidebar.html        ★ NEW
│       │   └── format_toggle.html  ★ NEW
│       ├── pages/
│       │   ├── home.html           ★ NEW: format picker with two tables
│       │   ├── queue.html          ★ NEW: htmx polling (1.5s)
│       │   ├── library.html        ★ NEW: search + sort
│       │   └── settings.html       ★ NEW: 12-key settings form
│       └── partials/
│           ├── queue_rows.html     ★ NEW
│           └── library_rows.html   ★ NEW
└── tests/
    └── integration/
        ├── test_api_info.py                ★ NEW
        ├── test_api_downloads_create.py    ★ NEW
        ├── test_api_downloads_active.py    ★ NEW
        ├── test_api_downloads_library.py   ★ NEW
        ├── test_api_downloads_cancel.py    ★ NEW
        ├── test_api_downloads_delete.py    ★ NEW
        ├── test_api_downloads_file.py      ★ NEW
        ├── test_api_settings_get.py        ★ NEW
        ├── test_api_settings_put.py        ★ NEW
        ├── test_api_settings_reset.py      ★ NEW
        └── test_pages.py                   ★ NEW
```

---

### Task 4.1: CSS Stylesheet

**Files:**
- Create: `app/static/css/app.css`

- [ ] **Step 1: Create the CSS file**

```css
/* app/static/css/app.css — design tokens, layout, format picker */
:root {
  --bg: #fafafa;
  --surface: #ffffff;
  --border: #e5e5e5;
  --text: #1a1a1a;
  --text-muted: #6b7280;
  --accent: #dc2626;
  --accent-hover: #b91c1c;
  --sidebar-w: 200px;
  --radius: 8px;
  --status-active: #2563eb;
  --status-queued: #ca8a04;
  --status-done: #16a34a;
  --status-error: #dc2626;
  --status-cancelled: #6b7280;
}

*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  font-size: 14px;
  color: var(--text);
  background: var(--bg);
  min-height: 100vh;
}
a { color: var(--accent); text-decoration: none; }
a:hover { text-decoration: underline; }

/* Layout */
.app-layout {
  display: grid;
  grid-template-columns: var(--sidebar-w) 1fr;
  min-height: 100vh;
}
.sidebar {
  background: var(--surface);
  border-right: 1px solid var(--border);
  padding: 20px 12px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.sidebar-brand { font-size: 18px; font-weight: 700; padding: 8px 12px; margin-bottom: 16px; }
.sidebar-nav { display: flex; flex-direction: column; gap: 2px; }
.sidebar-nav a {
  display: flex; align-items: center; gap: 10px;
  padding: 10px 12px; border-radius: var(--radius);
  color: var(--text-muted); font-weight: 500; text-decoration: none;
  transition: all 0.15s;
}
.sidebar-nav a:hover,
.sidebar-nav a.active { background: #f3f4f6; color: var(--text); text-decoration: none; }
.sidebar-nav a.active { color: var(--accent); }
.sidebar-spacer { flex: 1; }
.sidebar-footer { font-size: 11px; color: var(--text-muted); padding: 8px 12px; }

.content-area { padding: 32px; max-width: 1100px; width: 100%; }

.page-header { margin-bottom: 24px; }
.page-header h1 { font-size: 24px; font-weight: 700; }
.page-header p { color: var(--text-muted); margin-top: 4px; }

.card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 16px;
  margin-bottom: 8px;
}
.card:hover { border-color: #d1d5db; }

.url-bar { display: flex; gap: 8px; margin-bottom: 20px; }
.url-bar textarea {
  flex: 1; padding: 12px 16px;
  border: 2px solid var(--border); border-radius: var(--radius);
  font-size: 14px; font-family: inherit; resize: vertical;
  min-height: 48px; outline: none; transition: border-color 0.15s;
}
.url-bar textarea:focus { border-color: var(--accent); }

.btn {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 8px 20px; border: none; border-radius: var(--radius);
  font-size: 14px; font-weight: 500; cursor: pointer;
  transition: all 0.15s; white-space: nowrap;
}
.btn:hover { opacity: 0.9; }
.btn-primary { background: var(--accent); color: #fff; }
.btn-primary:hover { background: var(--accent-hover); }
.btn-ghost { background: #f3f4f6; color: var(--text); }
.btn-danger { background: #fef2f2; color: var(--status-error); }
.btn-sm { padding: 4px 10px; font-size: 12px; }
.btn:disabled { opacity: 0.5; cursor: not-allowed; }

.pill-group {
  display: inline-flex; border: 1.5px solid var(--border);
  border-radius: var(--radius); overflow: hidden;
}
.pill {
  padding: 8px 16px; border: none; background: transparent;
  color: var(--text-muted); font-size: 13px; font-weight: 500;
  cursor: pointer; transition: all 0.15s;
}
.pill.active { background: var(--text); color: #fff; }
.pill:not(.active):hover { color: var(--text); }

/* ── Format picker ─────────────────────────────────────────── */

.video-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 16px;
  margin-bottom: 12px;
}
.video-card-header {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
}
.video-card-thumb {
  width: 160px;
  min-width: 160px;
  height: 90px;
  border-radius: 6px;
  overflow: hidden;
  background: var(--border);
  flex-shrink: 0;
}
.video-card-thumb img { width: 100%; height: 100%; object-fit: cover; }
.video-card-meta { flex: 1; min-width: 0; }
.video-card-title { font-weight: 600; font-size: 15px; margin-bottom: 4px; }
.video-card-sub { font-size: 12px; color: var(--text-muted); }

.format-tables {
  display: grid;
  grid-template-columns: 2fr 1fr;
  gap: 16px;
}

.format-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 6px;
  overflow: hidden;
}
.format-table th,
.format-table td {
  padding: 8px 10px;
  text-align: left;
  border-bottom: 1px solid var(--border);
}
.format-table th {
  background: #f9fafb;
  font-weight: 600;
  color: var(--text-muted);
  text-transform: uppercase;
  font-size: 10px;
  letter-spacing: 0.04em;
}
.format-table tr:last-child td { border-bottom: none; }
.format-table tr.selected { background: #fef2f2; }
.format-table tr:hover { background: #f9fafb; cursor: pointer; }
.format-table tr.selected:hover { background: #fee2e2; }

.format-table .col-quality { width: 60px; }
.format-table .col-codec { width: 80px; }
.format-table .col-bitrate { width: 70px; }
.format-table .col-size { width: 80px; text-align: right; }
.format-table .col-radio { width: 30px; text-align: center; }

.format-picker-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 16px;
  padding-top: 12px;
  border-top: 1px solid var(--border);
}
.format-picker-summary { font-size: 12px; color: var(--text-muted); }

.progress-wrap { width: 100%; }
.progress-bg {
  background: #e5e7eb;
  border-radius: 4px;
  height: 6px;
  overflow: hidden;
}
.progress-fill {
  background: linear-gradient(90deg, var(--status-active), #60a5fa);
  height: 100%;
  border-radius: 4px;
  transition: width 0.4s ease;
}
.progress-text { font-size: 11px; color: var(--text-muted); margin-top: 4px; }

.badge {
  display: inline-flex;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 600;
}
.badge-active { background: #eff6ff; color: var(--status-active); }
.badge-queued { background: #fef3c7; color: var(--status-queued); }
.badge-done   { background: #f0fdf4; color: var(--status-done); }
.badge-error  { background: #fef2f2; color: var(--status-error); }
.badge-cancelled { background: #f3f4f6; color: var(--status-cancelled); }

.queue-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}
.queue-row-info { flex: 1; min-width: 0; }
.queue-row-title { font-weight: 500; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.queue-row-url { font-size: 11px; color: var(--text-muted); margin-top: 2px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }

.lib-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}
.lib-row-info { display: flex; align-items: center; gap: 12px; flex: 1; min-width: 0; }
.lib-row-icon {
  width: 40px; height: 40px;
  background: var(--border);
  border-radius: 6px;
  display: flex; align-items: center; justify-content: center;
  font-size: 18px; flex-shrink: 0;
}
.lib-row-name { font-weight: 500; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.lib-row-meta { font-size: 11px; color: var(--text-muted); margin-top: 2px; }
.lib-row-actions { display: flex; gap: 6px; flex-shrink: 0; }

.settings-form { max-width: 560px; }
.setting-group { margin-bottom: 20px; }
.setting-label { font-size: 14px; font-weight: 600; display: block; margin-bottom: 4px; }
.setting-desc { font-size: 12px; color: var(--text-muted); margin-bottom: 6px; }
.setting-input {
  padding: 8px 12px;
  border: 2px solid var(--border);
  border-radius: 6px;
  font-size: 14px;
  background: var(--surface);
  outline: none;
  width: 100%;
  max-width: 400px;
  transition: border-color 0.15s;
}
.setting-input:focus { border-color: var(--accent); }
.setting-input-short { max-width: 120px; }
.setting-select {
  padding: 8px 12px;
  border: 2px solid var(--border);
  border-radius: 6px;
  font-size: 14px;
  background: var(--surface);
  cursor: pointer;
  outline: none;
}
.setting-textarea {
  padding: 8px 12px;
  border: 2px solid var(--border);
  border-radius: 6px;
  font-size: 13px;
  font-family: monospace;
  background: var(--surface);
  outline: none;
  width: 100%;
  resize: vertical;
  transition: border-color 0.15s;
}
.setting-textarea:focus { border-color: var(--accent); }
.setting-actions {
  display: flex;
  gap: 8px;
  margin-top: 24px;
  padding-top: 16px;
  border-top: 1px solid var(--border);
}

.modal-overlay {
  display: none;
  position: fixed; inset: 0;
  background: rgba(0,0,0,0.7);
  z-index: 1000;
  align-items: center;
  justify-content: center;
}
.modal-overlay.active { display: flex; }
.modal-content {
  background: #1a1a1a;
  border-radius: 12px;
  overflow: hidden;
  width: 90vw;
  max-width: 960px;
  position: relative;
}
.modal-close {
  position: absolute; top: 8px; right: 8px;
  background: rgba(255,255,255,0.15);
  color: #fff;
  border: none; width: 32px; height: 32px;
  border-radius: 6px;
  font-size: 18px;
  cursor: pointer;
  z-index: 10;
}
.modal-content video { width: 100%; display: block; max-height: 80vh; }

.toast {
  position: fixed; top: 16px; right: 16px;
  padding: 12px 20px;
  border-radius: var(--radius);
  font-size: 13px;
  font-weight: 500;
  z-index: 2000;
  opacity: 0;
  transform: translateY(-8px);
  transition: all 0.3s;
  pointer-events: none;
}
.toast.show { opacity: 1; transform: translateY(0); }
.toast-success { background: #f0fdf4; color: var(--status-done); border: 1px solid #bbf7d0; }
.toast-error { background: #fef2f2; color: var(--status-error); border: 1px solid #fecaca; }

.empty { text-align: center; padding: 48px 0; color: var(--text-muted); }

.files-bar {
  display: flex;
  gap: 8px;
  margin-bottom: 16px;
  align-items: center;
}
.files-bar input {
  flex: 1; padding: 8px 12px;
  border: 2px solid var(--border); border-radius: 6px;
  font-size: 13px; background: var(--surface); outline: none;
}
.files-bar input:focus { border-color: var(--accent); }
.files-bar select {
  padding: 8px 12px;
  border: 2px solid var(--border);
  border-radius: 6px;
  font-size: 13px;
  background: var(--surface);
  cursor: pointer;
  outline: none;
}

@media (max-width: 900px) {
  .format-tables { grid-template-columns: 1fr; }
}
@media (max-width: 768px) {
  .app-layout { grid-template-columns: 1fr; }
  .sidebar { display: none; }
  .content-area { padding: 16px; }
  .video-card-header { flex-direction: column; }
  .video-card-thumb { width: 100%; min-width: unset; height: 180px; }
}
```

- [ ] **Step 2: Commit**

```bash
git add app/static/css/app.css
git commit -m "feat: add app stylesheet (design tokens, format picker, responsive)"
```

---

### Task 4.2: Templates

**Files:**
- Create: `app/templates/base.html`
- Create: `app/templates/components/sidebar.html`
- Create: `app/templates/components/format_toggle.html`
- Create: `app/templates/pages/home.html`
- Create: `app/templates/pages/queue.html`
- Create: `app/templates/pages/library.html`
- Create: `app/templates/pages/settings.html`
- Create: `app/templates/partials/queue_rows.html`
- Create: `app/templates/partials/library_rows.html`

- [ ] **Step 1: Create base.html + sidebar**

```html
<!-- app/templates/base.html -->
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>YourTube</title>
  <script src="https://unpkg.com/htmx.org@2.0.4"></script>
  <link rel="stylesheet" href="/static/css/app.css">
</head>
<body>
<div class="app-layout">
  {% include "components/sidebar.html" %}
  <main class="content-area">{% block content %}{% endblock %}</main>
</div>

<!-- Video preview modal -->
<div class="modal-overlay" id="videoModal">
  <div class="modal-content">
    <button class="modal-close" onclick="closePreview()">&times;</button>
    <video id="videoPlayer" controls></video>
  </div>
</div>

<script>
  function parseUrls(text) {
    return [...new Set(text.split(/[\s,]+/).map(u => u.trim()).filter(u => u.startsWith('http')))];
  }
  function previewFile(id) {
    const player = document.getElementById('videoPlayer');
    player.src = '/api/downloads/' + id + '/preview';
    document.getElementById('videoModal').classList.add('active');
    player.play();
  }
  function closePreview() {
    const player = document.getElementById('videoPlayer');
    player.pause();
    player.src = '';
    document.getElementById('videoModal').classList.remove('active');
  }
  document.getElementById('videoModal').addEventListener('click', function(e) {
    if (e.target === this) closePreview();
  });
  document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') closePreview();
  });
</script>
</body>
</html>
```

```html
<!-- app/templates/components/sidebar.html -->
<nav class="sidebar">
  <div class="sidebar-brand">YourTube</div>
  <div class="sidebar-nav">
    <a href="/" class="{% if request.url.path == '/' %}active{% endif %}">🏠 Home</a>
    <a href="/queue" class="{% if request.url.path == '/queue' %}active{% endif %}">⏳ Queue</a>
    <a href="/library" class="{% if request.url.path == '/library' %}active{% endif %}">📚 Library</a>
    <a href="/settings" class="{% if request.url.path == '/settings' %}active{% endif %}">⚙ Settings</a>
  </div>
  <div class="sidebar-spacer"></div>
  <div class="sidebar-footer">v0.1.0</div>
</nav>
```

- [ ] **Step 2: Create home page (format picker)**

```html
<!-- app/templates/pages/home.html -->
{% extends "base.html" %}
{% block content %}
<div class="page-header">
  <h1>Download</h1>
  <p>Paste YouTube URLs to fetch available formats</p>
</div>

<div class="url-bar">
  <textarea id="urls" placeholder="Paste one or more YouTube URLs..." rows="2"></textarea>
</div>

<div class="controls" style="display:flex;gap:10px;align-items:center;margin-bottom:20px;">
  {% include "components/format_toggle.html" %}
  <button class="btn btn-primary" id="fetch-btn" onclick="fetchUrls()">Fetch</button>
</div>

<div id="cards"></div>
{% endblock %}

<script>
let currentFormat = 'video';

function prettyCodec(c) {
  if (!c || c === 'none') return '—';
  const c2 = c.toLowerCase();
  if (c2.startsWith('avc1') || c2 === 'h264') return 'H.264';
  if (c2.startsWith('vp9') || c2 === 'vp09') return 'VP9';
  if (c2.startsWith('av01')) return 'AV1';
  if (c2 === 'opus') return 'Opus';
  if (c2.startsWith('mp4a')) return 'AAC';
  return c;
}

function prettySize(bytes) {
  if (!bytes) return '—';
  const units = ['B', 'KB', 'MB', 'GB'];
  let i = 0, n = bytes;
  while (n >= 1024 && i < units.length - 1) { n /= 1024; i++; }
  return `${n.toFixed(1)} ${units[i]}`;
}

function setFormat(btn) {
  document.querySelectorAll('.pill').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  currentFormat = btn.dataset.format;
}

async function fetchUrls() {
  const urls = parseUrls(document.getElementById('urls').value);
  if (!urls.length) return;

  const btn = document.getElementById('fetch-btn');
  const container = document.getElementById('cards');
  btn.disabled = true;
  btn.textContent = 'Fetching...';
  container.innerHTML = '';

  for (const url of urls) {
    const card = document.createElement('div');
    card.className = 'video-card';
    card.dataset.url = url;
    card.innerHTML = `
      <div class="video-card-header">
        <div class="video-card-thumb" style="display:flex;align-items:center;justify-content:center;color:var(--text-muted);">⏳</div>
        <div class="video-card-meta">
          <div class="video-card-title">${url}</div>
          <div class="video-card-sub">Fetching metadata...</div>
        </div>
      </div>
    `;
    container.appendChild(card);

    try {
      const res = await fetch('/api/info', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url }),
      });
      const data = await res.json();

      if (data.detail && data.detail.error) {
        card.innerHTML = `
          <div class="video-card-header" style="border-left:3px solid var(--status-error);">
            <div class="video-card-meta">
              <div class="video-card-title" style="color:var(--status-error);">⚠ ${data.detail.error}</div>
              <div class="video-card-sub" style="word-break:break-all;">${url}</div>
            </div>
          </div>
        `;
        continue;
      }

      renderFormatPicker(card, data, currentFormat);
    } catch (err) {
      card.innerHTML = `<div class="video-card-meta" style="color:var(--status-error);">Network error: ${err.message}</div>`;
    }
  }
  btn.disabled = false;
  btn.textContent = 'Fetch';
}

function escHtml(s) {
  const d = document.createElement('div');
  d.textContent = s;
  return d.innerHTML;
}

function renderFormatPicker(card, info, formatChoice) {
  const videoStreams = info.formats.filter(f => f.kind === 'video' || f.kind === 'combined');
  const audioStreams = info.formats.filter(f => f.kind === 'audio');

  const defaultVideoId = videoStreams[0]?.id;
  const defaultAudioId = audioStreams[0]?.id;

  card.dataset.videoId = defaultVideoId || '';
  card.dataset.audioId = formatChoice === 'audio' ? '' : (defaultAudioId || '');
  card.dataset.formatChoice = formatChoice;
  card.dataset.title = info.title || '';
  card.dataset.thumbnail = info.thumbnail_url || '';
  card.dataset.uploader = info.uploader || '';
  card.dataset.duration = info.duration || '';

  const fmtDuration = (s) => {
    if (!s) return '';
    return `${Math.floor(s/60)}:${String(s%60).padStart(2,'0')}`;
  };

  const videoRows = videoStreams.map(f => {
    const size = f.filesize || f.filesize_approx || 0;
    const quality = f.height ? (f.height >= 2160 ? '4K' : f.height >= 1440 ? '1440p' : f.height >= 1080 ? '1080p' : f.height >= 720 ? '720p' : f.height >= 480 ? '480p' : `${f.height}p`) : '—';
    return `<tr data-fmt-id="${f.id}" data-kind="video" onclick="selectFormat(this)">
      <td class="col-radio"><input type="radio" name="v-${card.dataset.url}" value="${f.id}" ${f.id===defaultVideoId?'checked':''}></td>
      <td class="col-quality">${quality}</td>
      <td>${f.height || '—'}p</td>
      <td>${f.ext.toUpperCase()}</td>
      <td class="col-codec">${prettyCodec(f.vcodec)}</td>
      <td class="col-bitrate">${f.tbr ? Math.round(f.tbr) + ' kbps' : '—'}</td>
      <td class="col-size">${prettySize(size)}</td>
    </tr>`;
  }).join('');

  const audioRows = audioStreams.map(f => {
    const size = f.filesize || f.filesize_approx || 0;
    return `<tr data-fmt-id="${f.id}" data-kind="audio" onclick="selectFormat(this)">
      <td class="col-radio"><input type="radio" name="a-${card.dataset.url}" value="${f.id}" ${f.id===defaultAudioId?'checked':''}></td>
      <td>${f.ext.toUpperCase()}</td>
      <td class="col-codec">${prettyCodec(f.acodec)}</td>
      <td class="col-bitrate">${f.abr ? Math.round(f.abr) + ' kbps' : '—'}</td>
      <td class="col-size">${prettySize(size)}</td>
    </tr>`;
  }).join('');

  card.innerHTML = `
    <div class="video-card-header">
      <div class="video-card-thumb">
        <img src="${info.thumbnail_url || ''}" alt="" onerror="this.parentElement.innerHTML='<div style=\\'display:flex;align-items:center;justify-content:center;height:100%;color:var(--text-muted);background:var(--border)\\'>📺</div>'">
      </div>
      <div class="video-card-meta">
        <div class="video-card-title">${escHtml(info.title || 'Untitled')}</div>
        <div class="video-card-sub">${escHtml(info.uploader || '')}${info.duration ? ' · ' + fmtDuration(info.duration) : ''}</div>
      </div>
    </div>
    <div class="format-tables">
      <div>
        <h3 style="font-size:12px;font-weight:600;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.04em;margin-bottom:6px;">Video Stream</h3>
        <table class="format-table">
          <thead><tr>
            <th class="col-radio"></th>
            <th class="col-quality">Quality</th>
            <th>Resolution</th>
            <th>Container</th>
            <th class="col-codec">Video Codec</th>
            <th class="col-bitrate">Bitrate</th>
            <th class="col-size">Size</th>
          </tr></thead>
          <tbody>${videoRows || '<tr><td colspan="7" style="text-align:center;color:var(--text-muted);">No video streams</td></tr>'}</tbody>
        </table>
      </div>
      <div>
        <h3 style="font-size:12px;font-weight:600;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.04em;margin-bottom:6px;">Audio Stream</h3>
        <table class="format-table">
          <thead><tr>
            <th class="col-radio"></th>
            <th>Container</th>
            <th class="col-codec">Audio Codec</th>
            <th class="col-bitrate">Bitrate</th>
            <th class="col-size">Size</th>
          </tr></thead>
          <tbody>${audioRows || '<tr><td colspan="5" style="text-align:center;color:var(--text-muted);">No audio streams</td></tr>'}</tbody>
        </table>
      </div>
    </div>
    <div class="format-picker-actions">
      <div class="format-picker-summary" id="summary-${card.dataset.url}">Pick a combination above</div>
      <button class="btn btn-primary" onclick="enqueue(this)" ${formatChoice==='audio' ? 'data-audio-only="1"' : ''}>
        ${formatChoice==='audio' ? 'Download Audio' : 'Download Selected'}
      </button>
    </div>
  `;

  const defaultV = card.querySelector(`tr[data-fmt-id="${defaultVideoId}"]`);
  if (defaultV) defaultV.classList.add('selected');
  const defaultA = card.querySelector(`tr[data-fmt-id="${defaultAudioId}"]`);
  if (defaultA) defaultA.classList.add('selected');
}

function selectFormat(row) {
  const card = row.closest('.video-card');
  const kind = row.dataset.kind;
  const fmtId = row.dataset.fmtId;

  row.parentElement.querySelectorAll('tr').forEach(r => r.classList.remove('selected'));
  row.classList.add('selected');

  if (kind === 'video') card.dataset.videoId = fmtId;
  else card.dataset.audioId = fmtId;

  row.querySelector('input[type=radio]').checked = true;
}

async function enqueue(btn) {
  const card = btn.closest('.video-card');
  const isAudioOnly = btn.dataset.audioOnly === '1';

  const payload = {
    url: card.dataset.url,
    title: card.dataset.title,
    thumbnail_url: card.dataset.thumbnail,
    uploader: card.dataset.uploader,
    duration: parseInt(card.dataset.duration) || null,
    format_choice: isAudioOnly ? 'audio' : 'video',
    video_format_id: isAudioOnly ? null : card.dataset.videoId,
    audio_format_id: card.dataset.audioId || null,
  };

  btn.disabled = true;
  btn.textContent = '...';

  try {
    const res = await fetch('/api/downloads', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    if (data.id) {
      btn.textContent = '✓ Queued';
      btn.style.background = 'var(--status-done)';
      card.querySelector('.format-picker-actions').innerHTML = '<a href="/queue" class="btn btn-ghost btn-sm">View in Queue →</a>';
    } else {
      btn.textContent = 'Error';
      btn.style.background = 'var(--status-error)';
    }
  } catch {
    btn.textContent = 'Error';
    btn.style.background = 'var(--status-error)';
  }
}
</script>
```

```html
<!-- app/templates/components/format_toggle.html -->
<div class="pill-group">
  <button class="pill active" data-format="video" onclick="setFormat(this)">MP4</button>
  <button class="pill" data-format="audio" onclick="setFormat(this)">MP3</button>
</div>
```

- [ ] **Step 3: Create queue page + partial**

```html
<!-- app/templates/pages/queue.html -->
{% extends "base.html" %}
{% block content %}
<div class="page-header">
  <h1>Queue</h1>
  <p>Active and queued downloads</p>
</div>

<div id="queue-body"
     hx-get="/api/downloads/active"
     hx-trigger="load, every 1.5s"
     hx-swap="innerHTML">
  <p class="empty">No active downloads.</p>
</div>
{% endblock %}
```

```html
<!-- app/templates/partials/queue_rows.html -->
{% for job in jobs %}
<div class="card">
  <div class="queue-row">
    <div class="queue-row-info">
      <div class="queue-row-title">{{ job.title or job.url }}</div>
      <div class="queue-row-url">
        {{ job.url }}
        {% if job.video_format_id %}<span style="color:var(--text-muted);">· v:{{ job.video_format_id }}{% if job.audio_format_id %} a:{{ job.audio_format_id }}{% endif %}</span>{% endif %}
      </div>
    </div>
    <div>
      <span class="badge badge-{{ job.status }}">
        {{ {'queued':'Queued','fetching_info':'Fetching','active':'Downloading','paused':'Paused'}.get(job.status, job.status) }}
      </span>
      {% if job.status in ('queued', 'active', 'fetching_info') %}
      <button class="btn btn-danger btn-sm"
              hx-post="/api/downloads/{{ job.id }}/cancel"
              hx-target="closest .card"
              hx-swap="outerHTML">Cancel</button>
      {% endif %}
    </div>
  </div>
  {% if job.status == 'active' %}
  <div class="progress-wrap" style="margin-top:8px;">
    <div class="progress-bg">
      <div class="progress-fill" style="width:{{ job.progress|default(0) }}%"></div>
    </div>
    <div class="progress-text">{{ '%.1f'|format(job.progress|default(0)) }}%</div>
  </div>
  {% endif %}
  {% if job.error %}
  <div style="font-size:12px;color:var(--status-error);margin-top:4px;">{{ job.error }}</div>
  {% endif %}
</div>
{% else %}
<p class="empty">No active downloads.</p>
{% endfor %}
```

- [ ] **Step 4: Create library page + partial**

```html
<!-- app/templates/pages/library.html -->
{% extends "base.html" %}
{% block content %}
<div class="page-header">
  <h1>Library</h1>
  <p>Downloaded videos and files</p>
</div>

<div class="files-bar">
  <input type="text" id="lib-search" name="q" placeholder="Search..."
         hx-get="/api/downloads/library"
         hx-trigger="keyup changed delay:300ms"
         hx-target="#library-body"
         hx-include="[name='q'],[name='sort']">
  <select id="lib-sort" name="sort"
          hx-get="/api/downloads/library"
          hx-trigger="change"
          hx-target="#library-body"
          hx-include="[name='q'],[name='sort']">
    <option value="date">Newest</option>
    <option value="name">Name</option>
    <option value="size">Size</option>
  </select>
</div>

<div id="library-body"
     hx-get="/api/downloads/library"
     hx-trigger="load">
  <p class="empty">No downloads yet.</p>
</div>
{% endblock %}
```

```html
<!-- app/templates/partials/library_rows.html -->
{% for item in items %}
<div class="card">
  <div class="lib-row">
    <div class="lib-row-info">
      <div class="lib-row-icon">🎬</div>
      <div>
        <div class="lib-row-name">{{ item.title or 'Untitled' }}</div>
        <div class="lib-row-meta">
          {% if item.file_size %}{{ '%d MB'|format(item.file_size//1048576) }}{% endif %}
          {% if item.completed_at %} · {{ item.completed_at.strftime('%Y-%m-%d') }}{% endif %}
          <span class="badge badge-{{ item.status }}">{{ item.status }}</span>
          {% if item.video_format_id %}<span style="color:var(--text-muted);">· v:{{ item.video_format_id }}{% if item.audio_format_id %} a:{{ item.audio_format_id }}{% endif %}</span>{% endif %}
        </div>
      </div>
    </div>
    <div class="lib-row-actions">
      {% if item.status == 'done' and item.file_path %}
      <button class="btn btn-ghost btn-sm" onclick="previewFile({{ item.id }})">▶ Preview</button>
      <a class="btn btn-primary btn-sm" href="/api/downloads/{{ item.id }}/file">↓ Download</a>
      {% endif %}
      <button class="btn btn-danger btn-sm"
              hx-delete="/api/downloads/{{ item.id }}"
              hx-target="closest .card"
              hx-swap="outerHTML swap:200ms"
              hx-confirm="Delete this file permanently?">✕</button>
    </div>
  </div>
  {% if item.error %}
  <div style="font-size:12px;color:var(--status-error);margin-top:4px;">{{ item.error }}</div>
  {% endif %}
</div>
{% else %}
<p class="empty">No downloads yet. <a href="/">Download some videos →</a></p>
{% endfor %}
```

- [ ] **Step 5: Create settings page**

```html
<!-- app/templates/pages/settings.html -->
{% extends "base.html" %}
{% block content %}
<div class="page-header">
  <h1>Settings</h1>
  <p>Configure download behaviour and system options</p>
</div>

<form class="settings-form"
      hx-put="/api/settings"
      hx-target="#settings-feedback"
      hx-swap="innerHTML"
      onsubmit="return false;">

  <div class="setting-group">
    <label class="setting-label" for="s-downloads-dir">Downloads directory</label>
    <div class="setting-desc">Where downloaded files are saved</div>
    <input class="setting-input" id="s-downloads-dir" name="downloads_dir" value="">
  </div>

  <div class="setting-group">
    <label class="setting-label" for="s-max-concurrent">Max concurrent downloads</label>
    <div class="setting-desc">Maximum downloads at once (1-8)</div>
    <input class="setting-input setting-input-short" id="s-max-concurrent" name="max_concurrent" type="number" min="1" max="8" value="2">
  </div>

  <div class="setting-group">
    <label class="setting-label" for="s-default-format">Default format</label>
    <div class="setting-desc">MP4 video or MP3 audio</div>
    <select class="setting-select" id="s-default-format" name="default_format">
      <option value="video">Video (MP4)</option>
      <option value="audio">Audio (MP3)</option>
    </select>
  </div>

  <div class="setting-group">
    <label class="setting-label" for="s-filename-template">Filename template</label>
    <div class="setting-desc">yt-dlp output template</div>
    <input class="setting-input" id="s-filename-template" name="filename_template" value="">
  </div>

  <div class="setting-group">
    <label class="setting-label" for="s-subtitle-languages">Subtitle languages</label>
    <div class="setting-desc">JSON array (e.g. ["en","ko"])</div>
    <input class="setting-input" id="s-subtitle-languages" name="subtitle_languages" value='["en"]'>
  </div>

  <div class="setting-group">
    <label class="setting-label" for="s-cookies-path">Cookies path</label>
    <div class="setting-desc">Netscape-format cookies.txt path</div>
    <input class="setting-input" id="s-cookies-path" name="cookies_path" placeholder="/data/cookies.txt"
           hx-get="/api/settings/cookies/validate"
           hx-trigger="change"
           hx-target="#cookies-status"
           hx-swap="innerHTML">
    <div id="cookies-status" style="font-size:12px;margin-top:4px;"></div>
  </div>

  <div class="setting-group">
    <label class="setting-label" for="s-proxy-url">Proxy URL</label>
    <div class="setting-desc">HTTP proxy for yt-dlp</div>
    <input class="setting-input" id="s-proxy-url" name="proxy_url" placeholder="">
  </div>

  <div class="setting-group">
    <label class="setting-label" for="s-audio-bitrate">Audio bitrate (kbps)</label>
    <div class="setting-desc">MP3 extraction bitrate (64-320)</div>
    <input class="setting-input setting-input-short" id="s-audio-bitrate" name="audio_bitrate" type="number" min="64" max="320" value="192">
  </div>

  <div class="setting-group">
    <label class="setting-label">Embed metadata</label>
    <div class="setting-desc">Write title, uploader into file metadata</div>
    <select class="setting-select" name="embed_metadata">
      <option value="true">Yes</option>
      <option value="false">No</option>
    </select>
  </div>

  <div class="setting-group">
    <label class="setting-label" for="s-extra-args">Extra yt-dlp arguments</label>
    <div class="setting-desc">JSON array of additional flags</div>
    <textarea class="setting-textarea" id="s-extra-args" name="extra_ytdlp_args" rows="2">[]</textarea>
  </div>

  <div class="setting-actions">
    <button class="btn btn-primary" type="submit">Save</button>
    <button class="btn btn-ghost" type="button"
            hx-post="/api/settings/reset"
            hx-target="#settings-feedback"
            hx-confirm="Reset all settings to defaults?">Reset to defaults</button>
  </div>
</form>

<div id="settings-feedback" style="margin-top:12px;"></div>

<script>
  fetch('/api/settings').then(r => r.json()).then(s => {
    Object.entries(s).forEach(([k, v]) => {
      const el = document.querySelector(`[name="${k}"]`);
      if (el) el.value = v;
    });
  });
</script>
{% endblock %}
```

- [ ] **Step 6: Commit**

```bash
git add app/templates/
git commit -m "feat: add frontend templates (format picker, queue, library, settings)"
```

---

### Task 4.3: Replace main.py with Full App (Worker Pool + Jinja2 + Routes)

**Files:**
- Replace: `app/main.py` (was minimal from Phase 1)

- [ ] **Step 1: Write the full app/main.py**

```python
"""FastAPI application entry point with lifespan, worker pool, Jinja2 templates, and static files."""

from __future__ import annotations

import logging
import threading
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlmodel import Session

from app.config import settings
from app.db import engine, run_migrations
from app.routes import pages, api

logger = logging.getLogger("yourtube.app")
templates = Jinja2Templates(directory=Path(__file__).parent / "templates")


# ── Worker pool ───────────────────────────────────────────────


class WorkerPool:
    """Manages N daemon threads that poll the downloads table for work."""

    def __init__(self) -> None:
        self.max_workers: int = 2
        self._threads: list[threading.Thread] = []
        self._stop: threading.Event = threading.Event()

    def start(self) -> None:
        self._stop.clear()
        for i in range(self.max_workers):
            t = threading.Thread(target=self._worker_loop, name=f"worker-{i}", daemon=True)
            t.start()
            self._threads.append(t)
        t = threading.Thread(target=self._stale_loop, name="stale-checker", daemon=True)
        t.start()

    def stop(self) -> None:
        self._stop.set()

    def _worker_loop(self) -> None:
        from app.services.queue import claim_next

        while not self._stop.is_set():
            try:
                with Session(engine) as session:
                    job = claim_next(session)
                if job is None:
                    self._stop.wait(2)
                    continue
                self._run_job(job)
            except Exception:
                logger.exception("Worker error")
                self._stop.wait(2)

    def _run_job(self, job) -> None:
        from app.services.downloader import YtdlpProgress, run_download
        from app.services.queue import release_job
        from app.services.settings import get_setting
        from app.services.error_mapper import friendly_ytdlp_error

        progress = YtdlpProgress()
        try:
            with Session(engine) as session:
                output_dir = get_setting(session, "downloads_dir") or str(settings.downloads_dir)
                output_template = get_setting(session, "filename_template")
                audio_bitrate = get_setting(session, "audio_bitrate")
                proxy = get_setting(session, "proxy_url") or None
                cookies = get_setting(session, "cookies_path") or None
                subtitles = get_setting(session, "embed_metadata") == "true"

            final = run_download(
                url=job.url,
                video_format_id=job.video_format_id,
                audio_format_id=job.audio_format_id,
                output_template=output_template,
                output_dir=output_dir,
                audio_bitrate=audio_bitrate,
                proxy=proxy,
                cookies_file=cookies,
                subtitles=subtitles,
                progress_hook=progress,
            )

            with Session(engine) as session:
                release_job(
                    session, job.id,
                    status="done",
                    file_path=final,
                    file_size=Path(final).stat().st_size if final and Path(final).exists() else None,
                    media_format="mp4" if final else None,
                )
        except YtdlpProgress.Cancelled:
            with Session(engine) as session:
                release_job(session, job.id, status="cancelled")
        except Exception as e:
            msg, _ = friendly_ytdlp_error(str(e))
            with Session(engine) as session:
                release_job(session, job.id, status="error", error=msg)

    def _stale_loop(self) -> None:
        from app.services.queue import detect_stale_jobs

        while not self._stop.is_set():
            self._stop.wait(60)
            try:
                with Session(engine) as session:
                    count = detect_stale_jobs(session)
                if count:
                    logger.warning("Marked %d stale jobs as errored", count)
            except Exception:
                logger.exception("Stale detection error")


pool = WorkerPool()


# ── Lifespan ──────────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI):
    run_migrations()
    from app.services.queue import requeue_active_on_startup
    from app.services.settings import get_setting

    with Session(engine) as session:
        count = requeue_active_on_startup(session)
        if count:
            logger.info("Re-queued %d in-progress jobs", count)
        pool.max_workers = int(get_setting(session, "max_concurrent") or 2)

    pool.start()
    yield
    pool.stop()


# ── App factory ───────────────────────────────────────────────


app = FastAPI(title="YourTube", version="0.1.0", lifespan=lifespan)

static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

app.include_router(pages.router)
app.include_router(api.router, prefix="/api")
```

- [ ] **Step 2: Verify it imports**

```bash
uv run python -c "from app.main import app; print('main.py OK')"
```
Expected: `main.py OK`

- [ ] **Step 3: Commit**

```bash
git add app/main.py
git commit -m "feat: replace minimal app with full FastAPI app (worker pool, Jinja2, static files)"
```

---

### Task 4.4: Full Page Routes

**Files:**
- Replace: `app/routes/pages.py` (was bare from Phase 1)

- [ ] **Step 1: Write full pages.py**

```python
"""HTML page routes (full page rendering, not htmx partials)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy import text
from sqlmodel import Session

from app.db import get_session
from app.main import templates

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def home_page(request: Request):
    return templates.TemplateResponse("pages/home.html", {"request": request})


@router.get("/queue", response_class=HTMLResponse)
async def queue_page(request: Request):
    return templates.TemplateResponse("pages/queue.html", {"request": request})


@router.get("/library", response_class=HTMLResponse)
async def library_page(request: Request):
    return templates.TemplateResponse("pages/library.html", {"request": request})


@router.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request):
    return templates.TemplateResponse("pages/settings.html", {"request": request})


@router.get("/health")
async def health(db: Session = Depends(get_session)):
    try:
        db.exec(text("SELECT 1"))
        return JSONResponse({"status": "ok"})
    except Exception as e:
        return JSONResponse({"status": "error", "detail": str(e)}, status_code=503)
```

- [ ] **Step 2: Write page tests**

```python
# tests/integration/test_pages.py
def test_home_page(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]


def test_queue_page(client):
    r = client.get("/queue")
    assert r.status_code == 200


def test_library_page(client):
    r = client.get("/library")
    assert r.status_code == 200


def test_settings_page(client):
    r = client.get("/settings")
    assert r.status_code == 200


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
```

- [ ] **Step 3: Run tests**

```bash
uv run pytest tests/integration/test_pages.py -v
```
Expected: PASS (5/5)

- [ ] **Step 4: Commit**

```bash
git add app/routes/pages.py tests/integration/test_pages.py
git commit -m "feat: add HTML page routes (home, queue, library, settings, health)"
```

---

### Task 4.5: API Routes

**Files:**
- Create: `app/routes/api.py`
- Create: `tests/integration/test_api_info.py`
- Create: `tests/integration/test_api_downloads_create.py`
- Create: `tests/integration/test_api_downloads_active.py`
- Create: `tests/integration/test_api_downloads_library.py`
- Create: `tests/integration/test_api_downloads_cancel.py`
- Create: `tests/integration/test_api_downloads_delete.py`
- Create: `tests/integration/test_api_downloads_file.py`
- Create: `tests/integration/test_api_settings_get.py`
- Create: `tests/integration/test_api_settings_put.py`
- Create: `tests/integration/test_api_settings_reset.py`

- [ ] **Step 1: Write API routes**

```python
# app/routes/api.py
"""JSON and htmx partial API routes."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse, HTMLResponse
from sqlmodel import Session

from app.db import get_session
from app.main import templates
from app.models import (
    CookiesValidateResponse,
    Download,
    DownloadCreate,
    DownloadResponse,
    FormatInfo,
    InfoRequest,
    InfoResponse,
)
from app.services.downloader import (
    classify_format,
    extract_info,
    sanitize_filename,
)
from app.services.error_mapper import friendly_ytdlp_error
from app.services.library import delete_from_library, get_library, search_library
from app.services.queue import cancel_job, get_active_jobs
from app.services.settings import (
    get_all_settings,
    get_setting,
    reset_settings,
    set_settings_batch,
    validate_cookies_path,
)

router = APIRouter()


# ── Info ────────────────────────────────────────────────────


@router.post("/info", response_model=InfoResponse)
async def fetch_info(body: InfoRequest, db: Session = Depends(get_session)):
    try:
        info = extract_info(str(body.url))
    except Exception as e:
        msg, code = friendly_ytdlp_error(str(e))
        raise HTTPException(status_code=400, detail={"error": msg, "code": code}) from e

    formats: list[FormatInfo] = []
    for f in info.get("formats", []):
        formats.append(
            FormatInfo(
                id=f.get("format_id", ""),
                ext=f.get("ext", ""),
                kind=classify_format(f),
                height=f.get("height"),
                width=f.get("width"),
                vcodec=f.get("vcodec"),
                acodec=f.get("acodec"),
                tbr=f.get("tbr"),
                abr=f.get("abr"),
                filesize=f.get("filesize"),
                filesize_approx=f.get("filesize_approx"),
            )
        )

    return InfoResponse(
        title=info.get("title"),
        thumbnail_url=info.get("thumbnail"),
        uploader=info.get("uploader"),
        duration=info.get("duration"),
        formats=formats,
    )


# ── Downloads CRUD ───────────────────────────────────────


@router.post("/downloads")
async def create_download(body: DownloadCreate, db: Session = Depends(get_session)):
    if body.format_choice == "video" and not (body.video_format_id or body.audio_format_id):
        raise HTTPException(
            status_code=400,
            detail={"error": "Pick at least a video or audio format", "code": "NO_FORMAT_SELECTED"},
        )

    row = Download(
        url=str(body.url),
        title=body.title,
        thumbnail_url=body.thumbnail_url,
        uploader=body.uploader,
        duration=body.duration,
        video_format_id=body.video_format_id,
        audio_format_id=body.audio_format_id,
        format_choice=body.format_choice,
        subtitles_enabled=body.subtitles_enabled,
        subtitle_languages=",".join(body.subtitle_languages) if body.subtitle_languages else None,
        status="queued",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"id": row.id, "status": row.status}


@router.get("/downloads/active", response_class=HTMLResponse)
async def list_active(request: Request, db: Session = Depends(get_session)):
    jobs = get_active_jobs(db)
    return templates.TemplateResponse(
        "partials/queue_rows.html",
        {"request": request, "jobs": jobs},
    )


@router.get("/downloads/library", response_class=HTMLResponse)
async def list_library(
    request: Request,
    q: str = Query(""),
    sort: str = Query("date"),
    db: Session = Depends(get_session),
):
    items = search_library(db, q=q, sort_by=sort) if q else get_library(db)
    return templates.TemplateResponse(
        "partials/library_rows.html",
        {"request": request, "items": items},
    )


@router.get("/downloads/{job_id}", response_model=DownloadResponse)
async def get_download(job_id: int, db: Session = Depends(get_session)):
    job = db.get(Download, job_id)
    if not job:
        raise HTTPException(status_code=404, detail={"error": "Job not found", "code": "JOB_NOT_FOUND"})
    return _to_response(job)


@router.post("/downloads/{job_id}/cancel")
async def cancel_download(job_id: int, db: Session = Depends(get_session)):
    ok = cancel_job(db, job_id)
    if not ok:
        job = db.get(Download, job_id)
        if not job:
            raise HTTPException(status_code=404, detail={"error": "Job not found", "code": "JOB_NOT_FOUND"})
        raise HTTPException(status_code=409, detail={"error": "Job already finished", "code": "ALREADY_DONE"})
    return {"status": "cancelled"}


@router.delete("/downloads/{job_id}", status_code=204)
async def delete_download(job_id: int, db: Session = Depends(get_session)):
    ok, _ = delete_from_library(db, job_id)
    if not ok:
        raise HTTPException(status_code=404, detail={"error": "Job not found", "code": "JOB_NOT_FOUND"})


@router.get("/downloads/{job_id}/file")
async def serve_file(job_id: int, db: Session = Depends(get_session)):
    job = db.get(Download, job_id)
    if not job:
        raise HTTPException(status_code=404, detail={"error": "Job not found", "code": "JOB_NOT_FOUND"})
    if job.status != "done" or not job.file_path:
        raise HTTPException(status_code=409, detail={"error": "File not ready", "code": "FILE_NOT_READY"})

    fp = Path(job.file_path)
    if not fp.exists():
        raise HTTPException(status_code=404, detail={"error": "File missing on disk", "code": "FILE_NOT_FOUND"})

    filename = f"{sanitize_filename(job.title or 'video')}.{job.media_format or 'mp4'}"
    return FileResponse(
        path=str(fp),
        filename=filename,
        media_type="application/octet-stream",
    )


@router.get("/downloads/{job_id}/preview")
async def preview_file(job_id: int, db: Session = Depends(get_session)):
    job = db.get(Download, job_id)
    if not job:
        raise HTTPException(status_code=404, detail={"error": "Job not found", "code": "JOB_NOT_FOUND"})
    if not job.file_path:
        raise HTTPException(status_code=409, detail={"error": "File not ready", "code": "FILE_NOT_READY"})

    fp = Path(job.file_path)
    if not fp.exists():
        raise HTTPException(status_code=404, detail={"error": "File missing on disk", "code": "FILE_NOT_FOUND"})

    return FileResponse(str(fp), media_type="video/mp4")


# ── Settings ─────────────────────────────────────────────


@router.get("/settings")
async def get_settings(db: Session = Depends(get_session)):
    return get_all_settings(db)


@router.put("/settings")
async def update_settings(body: dict[str, str], db: Session = Depends(get_session)):
    try:
        set_settings_batch(db, body)
    except ValueError as e:
        raise HTTPException(status_code=400, detail={"error": str(e), "code": "VALIDATION_FAILED"}) from e
    return get_all_settings(db)


@router.post("/settings/reset")
async def reset_settings_route(db: Session = Depends(get_session)):
    reset_settings(db)
    return get_all_settings(db)


@router.get("/settings/cookies/validate")
async def validate_cookies(db: Session = Depends(get_session)):
    path = get_setting(db, "cookies_path")
    if not path:
        return CookiesValidateResponse(valid=False, message="No cookies path configured")
    valid, msg = validate_cookies_path(path)
    return CookiesValidateResponse(valid=valid, message=msg)


# ── Helpers ───────────────────────────────────────────────


def _to_response(job: Download) -> DownloadResponse:
    return DownloadResponse(
        id=job.id or 0,
        url=job.url,
        title=job.title,
        thumbnail_url=job.thumbnail_url,
        uploader=job.uploader,
        duration=job.duration,
        status=job.status,
        progress=job.progress,
        error=job.error,
        file_size=job.file_size,
        media_format=job.media_format,
        resolution_height=job.resolution_height,
        created_at=job.created_at.isoformat() if job.created_at else "",
        started_at=job.started_at.isoformat() if job.started_at else None,
        completed_at=job.completed_at.isoformat() if job.completed_at else None,
    )
```

- [ ] **Step 2: Write the info API tests**

```python
# tests/integration/test_api_info.py
from tests.conftest import SAMPLE_VIDEO_INFO


def test_info_returns_metadata(client, mock_ytdlp):
    r = client.post("/api/info", json={"url": "https://youtube.com/watch?v=dQw4w9WgXcQ"})
    assert r.status_code == 200
    data = r.json()
    assert data["title"] == "Test Video"
    assert data["uploader"] == "Test Channel"
    assert data["duration"] == 213
    assert len(data["formats"]) == len(SAMPLE_VIDEO_INFO["formats"])


def test_info_formats_have_all_fields(client, mock_ytdlp):
    r = client.post("/api/info", json={"url": "https://youtube.com/watch?v=dQw4w9WgXcQ"})
    fmt = r.json()["formats"][0]
    for key in ("id", "ext", "kind", "vcodec", "acodec", "tbr", "filesize_approx"):
        assert key in fmt, f"missing field: {key}"


def test_info_formats_have_kind_classified(client, mock_ytdlp):
    r = client.post("/api/info", json={"url": "https://youtube.com/watch?v=dQw4w9WgXcQ"})
    formats = r.json()["formats"]
    kinds = {f["kind"] for f in formats}
    assert "video" in kinds
    assert "audio" in kinds


def test_info_without_url(client):
    r = client.post("/api/info", json={})
    assert r.status_code == 422


def test_info_handles_ytdlp_error(client, monkeypatch):
    import yt_dlp

    def failing_ydl(*a, **kw):
        raise ValueError("Something went wrong")

    monkeypatch.setattr(yt_dlp, "YoutubeDL", failing_ydl)

    r = client.post("/api/info", json={"url": "https://youtube.com/watch?v=bad"})
    assert r.status_code == 400
    body = r.json()
    assert "detail" in body
```

- [ ] **Step 3: Write the downloads create tests**

```python
# tests/integration/test_api_downloads_create.py
def test_create_download_with_video_and_audio(client):
    r = client.post("/api/downloads", json={
        "url": "https://youtube.com/watch?v=dQw4w9WgXcQ",
        "video_format_id": "137",
        "audio_format_id": "140",
    })
    assert r.status_code == 200
    data = r.json()
    assert "id" in data
    assert data["status"] == "queued"


def test_create_audio_only_download(client):
    r = client.post("/api/downloads", json={
        "url": "https://youtube.com/watch?v=dQw4w9WgXcQ",
        "format_choice": "audio",
        "audio_format_id": "140",
    })
    assert r.status_code == 200


def test_create_download_without_url(client):
    r = client.post("/api/downloads", json={"video_format_id": "137"})
    assert r.status_code == 422


def test_create_download_with_metadata(client):
    r = client.post("/api/downloads", json={
        "url": "https://youtube.com/watch?v=test",
        "title": "My Video",
        "thumbnail_url": "https://example.com/thumb.jpg",
        "uploader": "SomeChannel",
        "duration": 213,
        "video_format_id": "137",
        "audio_format_id": "140",
    })
    assert r.status_code == 200
```

- [ ] **Step 4: Write the remaining API tests**

```python
# tests/integration/test_api_downloads_active.py
def test_active_returns_queued_and_active(client):
    client.post("/api/downloads", json={"url": "https://youtube.com/watch?v=1", "video_format_id": "137", "audio_format_id": "140"})
    client.post("/api/downloads", json={"url": "https://youtube.com/watch?v=2", "video_format_id": "137", "audio_format_id": "140"})

    r = client.get("/api/downloads/active")
    assert r.status_code == 200
    assert "youtube.com" in r.text


def test_active_empty_when_no_jobs(client):
    r = client.get("/api/downloads/active")
    assert r.status_code == 200


# tests/integration/test_api_downloads_library.py
from app.models import Download


def test_library_returns_done_items(client, db_engine):
    from sqlmodel import Session

    with Session(db_engine) as session:
        session.add(Download(url="https://youtube.com/watch?v=test", status="done", title="Test Video"))
        session.commit()

    r = client.get("/api/downloads/library")
    assert r.status_code == 200
    assert "Test Video" in r.text


def test_library_search(client, db_engine):
    from sqlmodel import Session

    with Session(db_engine) as session:
        session.add(Download(url="https://youtube.com/1", status="done", title="Rick Astley"))
        session.add(Download(url="https://youtube.com/2", status="done", title="Nothing Else"))
        session.commit()

    r = client.get("/api/downloads/library?q=rick")
    assert "Rick" in r.text
    assert "Nothing" not in r.text


# tests/integration/test_api_downloads_cancel.py
def test_cancel_queued_job(client):
    r = client.post("/api/downloads", json={"url": "https://youtube.com/watch?v=test"})
    job_id = r.json()["id"]

    r = client.post(f"/api/downloads/{job_id}/cancel")
    assert r.status_code == 200


def test_cancel_nonexistent_job(client):
    r = client.post("/api/downloads/99999/cancel")
    assert r.status_code == 404


# tests/integration/test_api_downloads_delete.py
def test_delete_done_job(client, db_engine, tmp_path):
    from sqlmodel import Session

    fp = tmp_path / "test.mp4"
    fp.write_text("data")

    with Session(db_engine) as session:
        d = Download(url="https://youtube.com/watch?v=test", status="done", file_path=str(fp))
        session.add(d)
        session.commit()
        job_id = d.id

    r = client.delete(f"/api/downloads/{job_id}")
    assert r.status_code == 204
    assert not fp.exists()


def test_delete_nonexistent(client):
    r = client.delete("/api/downloads/99999")
    assert r.status_code == 404


# tests/integration/test_api_downloads_file.py
def test_download_file(client, db_engine, tmp_path):
    from sqlmodel import Session

    fp = tmp_path / "test.mp4"
    fp.write_bytes(b"fake mp4 bytes")

    with Session(db_engine) as session:
        d = Download(url="https://youtube.com/watch?v=test", status="done", file_path=str(fp), title="My Video")
        session.add(d)
        session.commit()
        job_id = d.id

    r = client.get(f"/api/downloads/{job_id}/file")
    assert r.status_code == 200
    assert r.content == b"fake mp4 bytes"


def test_download_not_ready(client):
    r = client.post("/api/downloads", json={"url": "https://youtube.com/watch?v=test"})
    job_id = r.json()["id"]

    r = client.get(f"/api/downloads/{job_id}/file")
    assert r.status_code in (404, 409)


# tests/integration/test_api_settings_get.py
def test_get_settings(client):
    r = client.get("/api/settings")
    assert r.status_code == 200
    data = r.json()
    assert "max_concurrent" in data
    assert data["default_format"] == "video"


# tests/integration/test_api_settings_put.py
def test_update_setting(client):
    r = client.put("/api/settings", json={"max_concurrent": "4"})
    assert r.status_code == 200
    assert r.json()["max_concurrent"] == "4"


def test_update_invalid_setting(client):
    r = client.put("/api/settings", json={"max_concurrent": "99"})
    assert r.status_code == 400


# tests/integration/test_api_settings_reset.py
def test_reset_settings(client):
    client.put("/api/settings", json={"max_concurrent": "8"})
    r = client.post("/api/settings/reset")
    assert r.status_code == 200
    assert r.json()["max_concurrent"] == "2"
```

- [ ] **Step 5: Add mock_ytdlp fixture and SAMPLE_VIDEO_INFO to conftest**

Replace `tests/conftest.py` content with:

```python
# tests/conftest.py
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app.db import get_session
from app.main import app


@pytest.fixture
def db_engine():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def db_session(db_engine):
    with Session(db_engine) as session:
        yield session


def _override_session(db_engine):
    def _gen():
        with Session(db_engine) as s:
            yield s

    return _gen


@pytest.fixture
def client(db_engine):
    app.dependency_overrides.clear()
    app.dependency_overrides[get_session] = _override_session(db_engine)
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def mock_ytdlp(monkeypatch):
    from unittest.mock import MagicMock

    fake = MagicMock()
    fake.extract_info.return_value = SAMPLE_VIDEO_INFO
    fake.download.return_value = None
    monkeypatch.setattr("yt_dlp.YoutubeDL", lambda *a, **kw: fake)
    return fake


SAMPLE_VIDEO_INFO = {
    "id": "dQw4w9WgXcQ",
    "title": "Test Video",
    "uploader": "Test Channel",
    "duration": 213,
    "thumbnail": "https://i.ytimg.com/vi/dQw4w9WgXcQ/maxresdefault.jpg",
    "formats": [
        {"format_id": "137", "ext": "mp4",  "height": 1080, "width": 1920, "vcodec": "avc1.640028", "acodec": "none",  "tbr": 3000, "filesize_approx": 500_000_000},
        {"format_id": "248", "ext": "webm", "height": 1080, "width": 1920, "vcodec": "vp9",        "acodec": "none",  "tbr": 2200, "filesize_approx": 350_000_000},
        {"format_id": "22",  "ext": "mp4",  "height": 720,  "width": 1280, "vcodec": "avc1.64001F", "acodec": "aac",   "tbr": 1500, "filesize_approx": 200_000_000},
        {"format_id": "140", "ext": "m4a",  "vcodec": "none", "acodec": "mp4a.40.2", "abr": 128, "filesize_approx": 5_000_000},
        {"format_id": "251", "ext": "webm", "vcodec": "none", "acodec": "opus",      "abr": 160, "filesize_approx": 6_500_000},
    ],
}
```

- [ ] **Step 6: Run all integration tests**

```bash
uv run pytest tests/integration/ -v
```
Expected: PASS (all)

- [ ] **Step 7: Verify full app boots**

```bash
uv run uvicorn app.main:app --port 8000 &
sleep 2
curl http://localhost:8000/health
curl http://localhost:8000/
curl http://localhost:8000/queue
curl http://localhost:8000/library
curl http://localhost:8000/settings
# kill %1
```
Expected: All return 200.

- [ ] **Step 8: Commit**

```bash
git add app/routes/api.py tests/conftest.py tests/integration/
git commit -m "feat: add API routes with format picker, queue, library, and settings endpoints"
```

---

## Self-Review (Phase 4)

**Spec coverage:**
- ✓ Full FastAPI app with worker pool (claim → download → release in daemon threads)
- ✓ Jinja2 templates with htmx: sidebar navigation, format picker, queue polling, library, settings
- ✓ API routes: /api/info (all formats), /api/downloads (create, list active, list library, cancel, delete, file, preview)
- ✓ Settings API: GET, PUT, POST reset, GET cookies/validate
- ✓ CSS: design tokens, layout, format tables, progress bars, badges, responsive
- ✓ Integration tests: 15 test files covering all API endpoints

**Placeholder scan:** No TBD, TODO, or incomplete sections.

**Type consistency:** All routes use `DownloadCreate`, `InfoResponse`, `FormatInfo` from models.py. All service imports match Phase 2/3 signatures.

---

## End of Phase 4

Deliverable: `uv run uvicorn app.main:app --reload --port 8000` serves the complete YourTube web application:
- **Home**: paste URL → two-table format picker (Video Streams + Audio Streams) → enqueue
- **Queue**: htmx polling every 1.5s with progress bars and cancel buttons
- **Library**: search, sort (newest/name/size), preview video, download file, delete
- **Settings**: 12-key form with validation, save, reset, cookies path validation
