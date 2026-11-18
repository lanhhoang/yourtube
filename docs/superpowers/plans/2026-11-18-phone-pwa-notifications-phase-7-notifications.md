# Phase 7: Notifications Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Send Web Push and in-app toasts when a single download finishes or fails, and one summary when a playlist or multi-URL batch settles.

**Usable result:** Turn on "Notifications on this device" in Settings on the installed iPhone app. Queue a video, lock the phone, and get "Downloaded" with the title; tap it to open the player. A 50-video playlist sends one summary push, such as "Mix: 48 downloaded, 2 failed".

**Architecture:** Multi-job enqueues share a `batch_id`. An atomic `claim_batch_summary` update guarantees one summary per batch. `push.py` loads or creates VAPID keys, stores subscriptions, and sends with `pywebpush` after `release_job` (failures never fail a job). The web app adds push and click handlers to `sw.ts`, a Settings toggle, and toast variants driven by `QueueOut.batches`.

**Tech Stack:** FastAPI, SQLAlchemy + Alembic, pytest, Svelte 5, Playwright. New: `pywebpush` 2.5.x (pulls `py-vapid`).

**Spec:** `docs/superpowers/specs/2026-11-18-phone-pwa-notifications-design.md` (§9 Notifications, §10 Docs)

**Parent plan:** `docs/superpowers/plans/2026-11-18-phone-pwa-notifications.md`, Tasks 18, 19, 20, 21, 22, 23. The tasks below are copied from it verbatim; the parent plan wins if they ever differ. Phase index: `docs/superpowers/plans/2026-11-18-phone-pwa-notifications-phases.md`.

**Prerequisites:** Phase 5 merged (the service worker `src/sw.ts` exists and the app installs over HTTPS). Phase 4 merged (`playlist_title` names batches). Phase 6 is recommended first so the Settings toggle lands in the phone layout, but it is not required.

## Global Constraints

- Run `pnpm check` (repo root) before every commit. Run `pnpm format` to fix formatting. After any API schema change, run `pnpm typegen` and commit `apps/web/src/lib/api.gen.ts`.
- Stack stays: FastAPI + yt-dlp + SQLite (Alembic) + worker threads; Svelte 5 + Vite + Tailwind 4; one process, one port. The Docker image ships everything.
- `DESIGN.md` is the visual contract. Red is the only accent. WCAG AA in both themes. Status is never shown by colour alone.
- Nothing loads from a CDN at runtime.
- Streams are copied and remuxed, never transcoded. No HDR output unless the job asks for HDR.
- Never silently download below the chosen cap (existing principle, unchanged).
- Never break or lose existing library files. A failed move leaves the file and its row as they were.
- A 500-video playlist must not send 500 pushes: jobs in a batch send no per-job push and no per-job toast.
- No login, no multi-user accounts. Tailscale is the access boundary. Never expose the app to the public internet.
- iOS: PWA install and Web Push need HTTPS and a home-screen install (iOS 16.4+). iOS has no Web Share Target.
- Phone layout is below 768 px. Touch targets are at least 44 px.
- Database changes go through a new Alembic revision. Never edit an existing revision.
- Follow the existing test layout: pytest `tests/unit`, `tests/api`, `tests/integration`; Vitest `apps/web/test`; Playwright `apps/web/e2e` (stubbed server `tests/e2e_server.py`).

## Review Focus

1. **The last two jobs of a batch finish at the same moment on two workers.** Exactly one summary push must go out, never zero and never two. Task 18 owns the test.
2. **A push endpoint is dead (`410`), slow, or unreachable.** The job still ends `done`/`error`. The worker moves on within the timeout. A dead subscription is deleted. Task 20 owns the test.

---

### Task 18: Batches and the one-summary guarantee

**Files:**
- Create: `apps/server/alembic/versions/20261118130000_add_batches_and_push.py` (`downloads.batch_id` nullable string with an index, `downloads.batch_notified` boolean default false, and table `push_subscriptions(id, endpoint unique not null, p256dh, auth, user_agent, created_at)`)
- Modify: `apps/server/app/models.py` (`Download.batch_id`, `Download.batch_notified`, `PushSubscription`)
- Modify: `apps/server/app/services/queue.py`
- Modify: `apps/server/app/schemas.py` (`JobOut.batch_id: str | None`)
- Test: `apps/server/tests/unit/test_queue_batches.py`, `apps/server/tests/unit/test_queue_retry_dismiss.py`

**Interfaces:**
- Produces:
  - `enqueue_downloads(session, payloads)`: when `len(payloads) > 1`, every row gets the same `batch_id = str(uuid4())`. A single job gets `None`.
  - `retry_job` also sets `batch_id = None` (a retried job notifies as a single job).
  - `@dataclass(frozen=True) class BatchSummary: batch_id: str; name: str; done: int; failed: int; cancelled: int; finished_at: datetime | None`
    - `name` = the first row's `playlist_title`, else `f"{n} videos"` where `n` is the batch size
  - `claim_batch_summary(session: Session, batch_id: str) -> BatchSummary | None`: one atomic `UPDATE downloads SET batch_notified = 1 WHERE id = (lowest id in batch) AND batch_notified = 0 AND NOT EXISTS (row in batch with status in ('queued','active'))`. When `rowcount == 1`, commit and return the counts from the DB. Otherwise return `None`.
  - `recent_batch_summaries(session: Session, limit: int = 5) -> list[BatchSummary]`: batches whose marker row has `batch_notified = 1`, newest `finished_at` first.

- [ ] **Step 1: Write the failing tests**
  - Enqueueing 3 jobs gives one shared UUID. Enqueueing 1 gives `None`.
  - `claim_batch_summary` returns `None` while any job is queued or active. Once all have settled (2 done, 1 error), it returns `BatchSummary(name="Mix", done=2, failed=1, cancelled=0, …)`. A second call returns `None`.
  - **Race:** two `db_session_visible` sessions on a file-backed SQLite DB call `claim_batch_summary` for the same settled batch from two threads behind a `threading.Barrier(2)`. Exactly one gets a summary.
  - A multi-URL batch with no `playlist_title` is named `"3 videos"`.
  - Retry clears `batch_id`, and the remaining batch still settles and claims once.
- [ ] **Step 2: Run them and see them fail**, then implement the migration, the model and the queue functions.
- [ ] **Step 3: Run `pnpm typegen && pnpm check`. Commit** `feat(server): download batches with a single settled summary`

### Task 19: VAPID keys and the subscriptions API

**Files:**
- Modify: `apps/server/pyproject.toml` (`uv add pywebpush`)
- Modify: `apps/server/app/config.py` (`vapid_private_key: str | None = None`, `vapid_public_key: str | None = None`, `vapid_subject: str = "mailto:yourtube@localhost"`)
- Create: `apps/server/app/services/push.py` (keys and subscription storage in this task)
- Create: `apps/server/app/api/push.py`; register it in the API router
- Modify: `apps/server/app/schemas.py`, `api.gen.ts`, `.env.example`
- Test: `apps/server/tests/unit/test_push_keys.py`, `apps/server/tests/api/test_push_api.py`

**Interfaces:**
- Produces:
  - `@dataclass(frozen=True) class VapidKeys: private_key: str; public_key: str`. `public_key` is the uncompressed P-256 point, base64url without padding, ready for `applicationServerKey`.
  - `load_vapid_keys(data_dir: Path, s: Settings) -> VapidKeys`. Env overrides win when both are set. Otherwise it reads `data_dir / "vapid.json"`. If that is missing, it generates keys with `py_vapid.Vapid01().generate_keys()` and writes them with mode `0600`. The result is cached per process.
  - `upsert_subscription(session, endpoint: str, p256dh: str, auth: str, user_agent: str | None) -> None`, `delete_subscription(session, endpoint: str) -> bool`, `list_subscriptions(session) -> list[PushSubscription]`
  - API:
    - `GET /api/push/key` → `PushKey { public_key: str }`
    - `POST /api/push/subscriptions` with body `PushSubscriptionIn { endpoint: HttpUrl-like str (https only); keys: { p256dh: str; auth: str } }` → `204`. The user agent comes from the request header.
    - `DELETE /api/push/subscriptions` with body `PushSubscriptionDelete { endpoint: str }` → `204` (also when nothing matched)
- [ ] **Step 1: Write the failing tests**
  - Keys: a first call creates `vapid.json` with mode `0o600`. A second call returns the same keys. Env overrides skip the file. `public_key` decodes to 65 bytes starting `0x04`.
  - API: `GET /api/push/key` is stable across calls. `POST` twice with the same endpoint leaves one row and updates its keys. `POST` with an `http://` endpoint returns `422`. `DELETE` removes the row.
- [ ] **Step 2: Run them and see them fail**, then implement. Document `YT_VAPID_PRIVATE_KEY`, `YT_VAPID_PUBLIC_KEY` and `YT_VAPID_SUBJECT` in `.env.example`.
- [ ] **Step 3: Run `pnpm typegen && pnpm check`. Commit** `feat(server): VAPID keys and push subscription API`

### Task 20: Send pushes when jobs settle

**Files:**
- Modify: `apps/server/app/services/push.py`, `apps/server/app/services/job_runner.py`, `apps/server/app/api/jobs.py` (cancel)
- Test: `apps/server/tests/unit/test_push_send.py`, `apps/server/tests/unit/test_job_runner.py`

**Interfaces:**
- Consumes: `claim_batch_summary`, `BatchSummary` (Task 18), `load_vapid_keys`, `list_subscriptions`, `delete_subscription` (Task 19).
- Produces:
  - `@dataclass(frozen=True) class PushMessage: title: str; body: str; tag: str; url: str`. It is sent as JSON `{"title","body","tag","url"}`.
  - `job_message(row: Download) -> PushMessage | None`:
    - done → `("Downloaded", row.title or row.url, f"job-{row.id}", f"/#/watch/{row.id}")`
    - error → `("Download failed", f"{title}: {row.error_message}", f"job-{row.id}", "/#/queue")`
    - cancelled → `None`
  - `batch_message(s: BatchSummary) -> PushMessage`: title is `s.name`. The body joins the non-zero parts of `"{done} downloaded"`, `"{failed} failed"` and `"{cancelled} cancelled"` with ", " (when all are zero, `"0 downloaded"`). Tag `f"batch-{s.batch_id}"`, url `"/#/queue"`. Example: `"Mix"` / `"12 downloaded, 1 failed"`.
  - `send_to_all(session, message: PushMessage, *, send: Callable[..., Any] = webpush, timeout: float = 10) -> None`: calls `send(subscription_info=…, data=json, vapid_private_key=…, vapid_claims={"sub": settings.vapid_subject}, timeout=timeout)` per subscription. On `WebPushException` whose `response.status_code` is 404 or 410, it deletes the subscription. Any other exception is logged and skipped.
  - `notify_settled(job_id: int) -> None`: opens its own session and never raises. If the row has no `batch_id`, it sends `job_message`. Otherwise it calls `claim_batch_summary` and sends `batch_message` when that returns a summary.
  - `run_claimed_job` calls `notify_settled(job_id)` after each `release_job`. The cancel API calls it after a successful `cancel_job` when the row has a `batch_id` (a queued job cancelled from the UI can be the last of a batch).
- [ ] **Step 1: Write the failing tests** (with a fake `send` that records calls):
  - Done and error rows give the exact titles, bodies, tags and urls above. A cancelled row gives `None`.
  - `batch_message(BatchSummary(..., name="Mix", done=12, failed=1, cancelled=0))` gives body `"12 downloaded, 1 failed"`.
  - **Dead endpoint:** the fake raises `WebPushException` with a 410 response for subscription A and succeeds for B. A is deleted, and B got the message.
  - **Unreachable:** the fake raises `requests.Timeout` for A. B is still sent, nothing raises, and A is kept.
  - Runner: a single job that finishes calls `send` once with "Downloaded". A batch of 3 calls `send` once (the summary), only after the third settles. A raise inside `notify_settled` still leaves the job `done`.
  - Cancel API: cancelling the last queued job of a batch sends one summary.
- [ ] **Step 2: Run them and see them fail**, then implement.
- [ ] **Step 3: Run `pnpm check`. Commit** `feat(server): web push for finished, failed and settled batches`

### Task 21: Notifications on this device

**Files:**
- Modify: `apps/web/src/sw.ts` (`push` and `notificationclick` handlers)
- Create: `apps/web/src/lib/push.ts`
- Modify: `apps/web/src/routes/Settings.svelte` (toggle section)
- Modify: `README.md` (notifications on iPhone: install first, then turn on in Settings)
- Test: `apps/web/test/push.test.ts`, `apps/web/e2e/notifications.spec.ts`

**Interfaces:**
- Consumes: `/api/push/key`, `/api/push/subscriptions` (Task 19), the `PushMessage` JSON (Task 20).
- Produces:
  - `urlBase64ToUint8Array(s: string): Uint8Array`
  - `pushSupport(env: { hasPushManager: boolean; isIOS: boolean; standalone: boolean; permission: NotificationPermission | "unsupported" }): "ready" | "install-first" | "blocked" | "unsupported"`. iOS and not standalone → `"install-first"`. No PushManager → `"unsupported"`. Permission `"denied"` → `"blocked"`.
  - `enablePush(): Promise<void>` (called from the toggle's click handler only): `Notification.requestPermission()`, then `registration.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey })`, then `POST` the subscription. `disablePush(): Promise<void>`: unsubscribe and `DELETE`.
  - `sw.ts` `push`: parse the JSON and always call `showNotification(title, { body, tag, icon: "/pwa-192x192.png", data: { url } })`. Fall back to `{ title: "YourTube", body: "" }` when parsing fails. `notificationclick`: close it, focus an open client and navigate it to `data.url`, otherwise `clients.openWindow(data.url)`.
  - Settings section "Notifications" shows a switch labelled "Notifications on this device". Its state comes from `pushManager.getSubscription()`. Under it, depending on the support status:
    - `install-first`: "Add YourTube to your Home Screen first."
    - `blocked`: "Notifications are blocked for YourTube in your browser settings."
    - `unsupported`: "This browser can't show notifications."
- [ ] **Step 1: Write the failing unit tests** for `urlBase64ToUint8Array` (a known vector) and every `pushSupport` branch.
- [ ] **Step 2: Write the failing e2e test.** With `addInitScript`, stub `PushManager.prototype.subscribe`/`getSubscription` and `Notification.requestPermission` to return a fake subscription with `toJSON()`. Toggling on sends `POST /api/push/subscriptions` (wait for the request) and the switch is checked after a reload. Toggling off sends `DELETE`.
- [ ] **Step 3: Implement, run `pnpm check && pnpm e2e`. Commit** `feat(web): turn on notifications per device`
- [ ] **Step 4: Manual check on the owner's iPhone over Tailscale:** install, turn on, queue a short video, lock the phone, get the push, tap it, and land on the player. Record the result in the PR description.

### Task 22: Toast variants for failed jobs and batches

**Files:**
- Modify: `apps/server/app/schemas.py` (`QueueOut.batches: list[BatchOut]`, where `BatchOut` mirrors `BatchSummary`), `apps/server/app/api/jobs.py` (`get_queue` fills it from `recent_batch_summaries`), `api.gen.ts`
- Modify: `apps/web/src/lib/toasts.ts`, `apps/web/src/components/Toasts.svelte`, `apps/web/src/App.svelte`
- Modify: `apps/server/tests/e2e_server.py` (a URL containing `fail` raises in the stubbed download)
- Modify: `DESIGN.md` (toast variants)
- Test: `tests/api/test_queue_api.py`, `apps/web/test/toasts.test.ts`, `apps/web/e2e/queue.spec.ts`

**Interfaces:**
- Consumes: `recent_batch_summaries` (Task 18), `JobOut.batch_id`, `batch_message` copy (Task 20). Toasts reuse the same words as pushes.
- Produces:
  - `type ToastKind = "done" | "failed" | "batch"`; `type Toast = { key: string; kind: ToastKind; title: string; body: string }`
  - `newEvents(seen: Set<string>, queue: QueueOut, silent: boolean): { toasts: Toast[]; seen: Set<string> }`. Keys are `done:<id>` (completed, `batch_id` null), `failed:<id>` (failed, `batch_id` null) and `batch:<uuid>` (`queue.batches`). Batch jobs never toast on their own. Copy: done `"Downloaded"` / title; failed `"Download failed"` / `"<title>: <error_message>"`; batch name / summary body.
  - `Toasts.svelte` renders `kind` as an icon plus a text label (never by colour alone). `failed` uses the danger token.
  - `newCompletions` is removed (replaced by `newEvents`), and `SEEN_KEY` stays.
- [ ] **Step 1: Write the failing tests**
  - API: after a batch of 2 settles and is claimed, `GET /api/queue` returns `batches[0]` with its name and counts.
  - Vitest: first poll silent → no toasts, but all keys are seen. A new failed single job → one `failed` toast. A completed job with a `batch_id` → no toast. A new batch → one `batch` toast with body `"2 downloaded"`. The same queue again → no toasts.
  - e2e: enqueue `https://e2e.test/fail` → a toast "Download failed" appears.
- [ ] **Step 2: Run them and see them fail**, then implement and run `pnpm typegen`.
- [ ] **Step 3: Run `pnpm check && pnpm e2e`. Commit** `feat: toasts for failed downloads and settled batches`

### Task 23: Product and design docs close-out

**Files:** `PRODUCT.md`, `DESIGN.md`, `README.md`

- [ ] **Step 1: Bring the docs up to date.**
  - `PRODUCT.md`: remove live push from out-of-scope, add the phone user, and keep "no recommendations, avatars, view counts". A notification toggle is not a bell.
  - `DESIGN.md`: check that the logo mark, theme tile, phone section, player and toast variants all match what shipped.
  - `README.md`: list the new env vars (`YT_HOST`, `YT_VAPID_*`).
- [ ] **Step 2: Run `pnpm check`. Commit** `docs: product, design and README for phone, PWA and notifications`

---

## Done when

- Every task above is committed and `pnpm check && pnpm e2e` pass on the branch.
- The usable result above works by hand.
