# Phase 7: Notifications Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Send Web Push and in-app toasts when a single download finishes or fails, and one summary when a playlist or multi-URL batch settles.

**Usable result:** Turn on "Notifications on this device" in Settings on the installed iPhone app. Queue a video, lock the phone, and get "Downloaded" with the title; tap it to open the player. A 50-video playlist sends one summary push, such as "Mix: 48 downloaded, 2 failed".

**Architecture:** Multi-job enqueues share a `batch_id`. An atomic `claim_batch_summary` update guarantees one summary per batch. `push.py` loads or creates VAPID keys, stores subscriptions, and sends with `pywebpush` after `release_job` (failures never fail a job). The web app adds push and click handlers to `sw.ts`, a Settings toggle, and toast variants driven by `QueueOut.batches`.

**Tech Stack:** FastAPI, SQLAlchemy + Alembic, pytest, Svelte 5, Playwright. New: `pywebpush` 2.5.x (pulls `py-vapid`).

**Spec:** `docs/superpowers/specs/2026-11-18-phone-pwa-notifications-design.md` (§9 Notifications, §10 Docs)

**Parent plan:** `docs/superpowers/plans/2026-11-18-phone-pwa-notifications.md`, Tasks 18, 19, 20, 21, 22, 23. The tasks below are copied from it verbatim; the parent plan wins if they ever differ. Phase index: `docs/superpowers/plans/2026-11-18-phone-pwa-notifications-phases.md`.

**Prerequisites:** Phase 5 merged (the service worker `src/sw.ts` exists and the app installs over HTTPS). Phase 4 merged (`playlist_title` names batches). Phase 6 is recommended first so the Settings toggle lands in the phone layout, but it is not required. All six are merged on `main` at `3c5a116`.

**Revised 2026-11-19 after a readiness review** (parent plan and spec updated to match). Each item was checked against the code, the `pywebpush` 2.5.0 source, or with a throwaway script:

- **The VAPID subject default is `mailto:yourtube@example.com`, not `@localhost`.** Apple's push service answers a `localhost` subject with `403 BadJwtToken`, so every iPhone push would fail. `py_vapid` also rejects an `https:` subject with a path, so the README asks for a real `mailto:`.
- **`webpush` writes `aud` and `exp` into the `vapid_claims` dict it gets.** One shared dict sent `https://web.push.apple.com` as the audience to an FCM endpoint. `send_to_all` builds a new dict per call, and a test covers two push services.
- **`webpush` defaults to `ttl=0`.** The push service may drop a TTL-0 message when the phone is locked or asleep, which is the usable result. Sends use `ttl=86400`.
- **The key formats are fixed.** The private key is the raw 32-byte scalar in base64url (round-trips through `Vapid01.from_string` and `webpush`). The public key is the 65-byte uncompressed point.
- **`load_vapid_keys` can't use `lru_cache`.** `Settings` is unhashable. A lock and a dict cache keyed by the dir and env values stop two threads from generating two key pairs on first start.
- **The batch mark goes on every row of the batch, not the lowest id.** With the lowest-id mark, retrying that row after the summary moved the mark out of the batch: the batch could be claimed a second time and dropped out of `recent_batch_summaries`. The new `UPDATE … WHERE NOT EXISTS (pending) AND NOT EXISTS (marked)` gave exactly one winner in 300 two-thread races, and retrying a row can't reopen a batch.
- **Stale-reaped jobs notify.** `detect_stale_jobs` returns the reaped ids and the stale loop calls `notify_settled`. Without this, a batch with a reaped job never sent its summary. The worker notifies only when `release_job` returns `True`, so a reaped job that finishes late doesn't notify twice.
- **`send=webpush` as a default argument is bound at import**, so monkeypatching `app.services.push.webpush` had no effect. The default is `None`, resolved at call time.
- **The e2e server stubs `webpush`.** The e2e subscribes a fake endpoint, and the workers would otherwise send real requests to it.
- **The "fail" e2e stubs `/api/queue`.** A real job waits about 20 s behind the seeded "Slow video" on the one worker. `phone.spec.ts`'s stubbed queue gains `batches: []`.
- **The cancel API notifies in a background task**, so the `204` doesn't wait on push services.
- **`urlBase64ToUint8Array` returns `Uint8Array<ArrayBuffer>`.** The plain type failed `svelte-check` as `applicationServerKey`.
- **iOS gesture rule:** Settings fetches the public key on mount, so `requestPermission()` runs straight from the tap with no network wait before it. `pushSupport` checks `install-first` before `unsupported`, because iOS Safari has no `PushManager` until the app is installed. Detection rules for iOS (including iPadOS) and standalone are spelled out.
- **The endpoint is a plain `https://` string**, not `HttpUrl`, which can rewrite it. Push bodies are cut to 200 characters (Apple caps the payload at 4 KB).
- **Small gaps closed:** `uv.lock` is committed (the Dockerfile uses `--frozen`). `db_session_visible` cleanup and `test_db.py` learn the new table. The switch is a native `role="switch"` checkbox with On/Off text, and `DESIGN.md` gets it in Task 21. The README already has `YT_HOST` and the phone user is already in `PRODUCT.md`, so Task 23 shrinks.
- **Not handled:** `pushsubscriptionchange`. Settings re-sends the current subscription on every visit, which covers a reset database. A subscription rotated by the browser recovers on the next Settings visit.
- Checked: `pnpm check` passes on `3c5a116` (335 tests, 96% coverage). Alembic head is `20261118120000`.

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
3. **A batch job is retried after its summary, or reaped as stale.** A retry never reopens the batch or sends a second summary. A reaped job still lets its batch settle, and a late finish from its worker sends nothing. Tasks 18 and 20 own the tests.

---

### Task 18: Batches and the one-summary guarantee

**Files:**
- Create: `apps/server/alembic/versions/20261118130000_add_batches_and_push.py` (`down_revision = "20261118120000"`; `op.batch_alter_table` like that revision. `downloads.batch_id` nullable string with an index, `downloads.batch_notified` boolean not null `server_default=sa.false()`, and table `push_subscriptions(id, endpoint unique not null, p256dh not null, auth not null, user_agent nullable, created_at)`)
- Modify: `apps/server/app/models.py` (`Download.batch_id`, `Download.batch_notified`, `PushSubscription`)
- Modify: `apps/server/app/services/queue.py`, `apps/server/app/main.py` (stale loop reads ids)
- Modify: `apps/server/app/schemas.py` (`JobOut.batch_id: str | None`)
- Modify: `apps/server/tests/conftest.py` (`db_session_visible` cleanup also deletes `push_subscriptions`), `apps/server/tests/test_db.py` (expected tables)
- Modify: `apps/server/tests/unit/test_queue_stale.py`, `apps/server/tests/unit/test_queue_progress.py`, `apps/server/tests/integration/test_worker_lifecycle.py` (`detect_stale_jobs` now returns ids)
- Test: `apps/server/tests/unit/test_queue_batches.py`, `apps/server/tests/unit/test_queue_retry_dismiss.py`

**Interfaces:**
- Produces:
  - `enqueue_downloads(session, payloads)`: when `len(payloads) > 1`, every row gets the same `batch_id = str(uuid4())`. A single job gets `None`.
  - `retry_job` also sets `batch_id = None` and `batch_notified = False` (a retried job notifies as a single job).
  - `@dataclass(frozen=True) class BatchSummary: batch_id: str; name: str; done: int; failed: int; cancelled: int; finished_at: datetime | None`
    - `name` = the `playlist_title` of the batch's lowest-id row, else `f"{n} videos"` where `n` is the number of rows in the batch
  - `claim_batch_summary(session: Session, batch_id: str) -> BatchSummary | None`: one atomic `UPDATE downloads SET batch_notified = 1 WHERE batch_id = :b AND NOT EXISTS (row in batch with status in ('queued','active')) AND NOT EXISTS (row in batch with batch_notified = 1)`. Every row of the batch gets the mark, so retrying any one row (which leaves the batch) can't make the batch claimable again. When `rowcount > 0`, commit and return the counts from the DB. Otherwise roll back and return `None`.
  - `recent_batch_summaries(session: Session, limit: int = 5) -> list[BatchSummary]`: batches whose rows have `batch_notified = 1`, grouped by `batch_id`, newest `max(finished_at)` first.
  - `detect_stale_jobs(session, timeout_minutes) -> list[int]`: the same update with `RETURNING id`, so Task 20 can notify each reaped job. `WorkerPool._stale_check_loop` keeps working on the list.
- [ ] **Step 1: Write the failing tests**
  - Enqueueing 3 jobs gives one shared UUID. Enqueueing 1 gives `None`.
  - `claim_batch_summary` returns `None` while any job is queued or active. Once all have settled (2 done, 1 error), it returns `BatchSummary(name="Mix", done=2, failed=1, cancelled=0, …)`. A second call returns `None`.
  - **Race:** two `SessionLocal()` sessions (the test DB is a file, use `db_session_visible` for setup) call `claim_batch_summary` for the same settled batch from two threads behind a `threading.Barrier(2)`. Run it 50 times. Every round has exactly one winner.
  - A multi-URL batch with no `playlist_title` is named `"3 videos"`.
  - Retry clears `batch_id` and `batch_notified`, and the remaining batch still settles and claims once.
  - **Retry after the summary:** claim a settled batch, then retry its lowest-id row. A second claim returns `None`, and `recent_batch_summaries` still lists the batch.
  - `detect_stale_jobs` returns the reaped ids (update the old `== 1` / `== 0` asserts to lists).
- [ ] **Step 2: Run them and see them fail**, then implement the migration, the model and the queue functions.
- [ ] **Step 3: Run `pnpm typegen && pnpm check`. Commit** `feat(server): download batches with a single settled summary`

### Task 19: VAPID keys and the subscriptions API

**Files:**
- Modify: `apps/server/pyproject.toml` and `apps/server/uv.lock` (`uv add pywebpush`, which resolves 2.5.0 with `py-vapid` 1.9.6. The Dockerfile runs `uv sync --frozen`, so commit the lock)
- Modify: `apps/server/app/config.py` (`vapid_private_key: str | None = None`, `vapid_public_key: str | None = None`, `vapid_subject: str = "mailto:yourtube@example.com"`. Apple rejects a `localhost` subject with `403 BadJwtToken`, and `py_vapid` rejects an `https:` subject that has a path)
- Create: `apps/server/app/services/push.py` (keys and subscription storage in this task)
- Create: `apps/server/app/api/push.py`; register it in `app/api/__init__.py` above the catch-all
- Modify: `apps/server/app/schemas.py`, `api.gen.ts`, `.env.example`
- Test: `apps/server/tests/unit/test_push_keys.py`, `apps/server/tests/api/test_push_api.py`

**Interfaces:**
- Produces:
  - `@dataclass(frozen=True) class VapidKeys: private_key: str; public_key: str`. Both are base64url without padding. `private_key` is the raw 32-byte P-256 scalar (`private_numbers().private_value.to_bytes(32, "big")`), which `webpush(vapid_private_key=…)` accepts. `public_key` is the uncompressed point (`public_bytes(X962, UncompressedPoint)`, 65 bytes starting `0x04`), ready for `applicationServerKey`.
  - `load_vapid_keys(data_dir: Path, s: Settings) -> VapidKeys`. Env overrides win when both are set. Otherwise it reads `data_dir / "vapid.json"` (`{"private_key", "public_key"}`). If that is missing, it generates keys with `py_vapid.Vapid01().generate_keys()` and writes the file through a temp file opened with mode `0600`, then `os.replace`. A module-level `threading.Lock` guards the load. The result is cached in a dict keyed by `(str(data_dir), s.vapid_private_key, s.vapid_public_key)`, because `Settings` is unhashable and `lru_cache` can't take it. The lock stops a worker and a request from generating two different key pairs on first start. Tests clear the cache with an autouse fixture.
  - `upsert_subscription(session, endpoint: str, p256dh: str, auth: str, user_agent: str | None) -> None`, `delete_subscription(session, endpoint: str) -> bool`, `list_subscriptions(session) -> list[PushSubscription]`
  - API:
    - `GET /api/push/key` → `PushKey { public_key: str }`
    - `POST /api/push/subscriptions` with body `PushSubscriptionIn { endpoint: str; keys: { p256dh: str; auth: str } }` → `204`. `endpoint` is a plain `str` with a validator that requires `https://`. `HttpUrl` would rewrite the URL, and the endpoint must stay byte-exact. The keys must be non-empty. The user agent comes from the request header.
    - `DELETE /api/push/subscriptions` with body `PushSubscriptionDelete { endpoint: str }` → `204` (also when nothing matched)
- [ ] **Step 1: Write the failing tests**
  - Keys: a first call creates `vapid.json` with mode `0o600`. A second call returns the same keys. Env overrides skip the file. `public_key` decodes to 65 bytes starting `0x04`. `Vapid01.from_string(private_key)` loads. Two threads calling it on an empty dir get the same keys.
  - API: `GET /api/push/key` is stable across calls. `POST` twice with the same endpoint leaves one row and updates its keys. `POST` with an `http://` endpoint returns `422`. `DELETE` removes the row.
- [ ] **Step 2: Run them and see them fail**, then implement. Document `YT_VAPID_PRIVATE_KEY`, `YT_VAPID_PUBLIC_KEY` and `YT_VAPID_SUBJECT` in `.env.example` (the subject should be a real `mailto:` address).
- [ ] **Step 3: Run `pnpm typegen && pnpm check`. Commit** `feat(server): VAPID keys and push subscription API`

### Task 20: Send pushes when jobs settle

**Files:**
- Modify: `apps/server/app/services/push.py`, `apps/server/app/services/job_runner.py`, `apps/server/app/main.py` (stale loop), `apps/server/app/api/jobs.py` (cancel)
- Test: `apps/server/tests/unit/test_push_send.py`, `apps/server/tests/unit/test_job_runner.py`, `apps/server/tests/api/test_queue_api.py`

**Interfaces:**
- Consumes: `claim_batch_summary`, `BatchSummary`, `detect_stale_jobs` (Task 18), `load_vapid_keys`, `list_subscriptions`, `delete_subscription` (Task 19).
- Produces:
  - `@dataclass(frozen=True) class PushMessage: title: str; body: str; tag: str; url: str`. It is sent as JSON `{"title","body","tag","url"}`. `body` is cut to 200 characters with "…" (Apple caps the payload at 4 KB).
  - `job_message(row: Download) -> PushMessage | None`:
    - done → `("Downloaded", row.title or row.url, f"job-{row.id}", f"/#/watch/{row.id}")`
    - error → `("Download failed", f"{title}: {row.error_message}", f"job-{row.id}", "/#/queue")`, where `title = row.title or row.url`
    - cancelled → `None`
  - `batch_message(s: BatchSummary) -> PushMessage`: title is `s.name`. The body joins the non-zero parts of `"{done} downloaded"`, `"{failed} failed"` and `"{cancelled} cancelled"` with ", " (when all are zero, `"0 downloaded"`). Tag `f"batch-{s.batch_id}"`, url `"/#/queue"`. Example: `"Mix"` / `"12 downloaded, 1 failed"`.
  - `send_to_all(session, message: PushMessage, *, send: Callable[..., Any] | None = None, timeout: float = 10) -> None`: `send = send or webpush`, looked up at call time so tests can monkeypatch `app.services.push.webpush`. It calls `send(subscription_info=…, data=json, vapid_private_key=…, vapid_claims={"sub": settings.vapid_subject}, ttl=86400, timeout=timeout)` once per subscription. Build a new claims dict for every call: `webpush` writes `aud` and `exp` into the dict it gets, and a shared dict would send the Apple audience to FCM. `ttl` defaults to `0` in pywebpush, which lets the push service drop the message when a locked phone can't take it right away. A day keeps it. On `WebPushException` whose `response.status_code` is 404 or 410, it deletes the subscription. Any other exception is logged and skipped.
  - `notify_settled(job_id: int) -> None`: opens its own session and never raises. If the row has no `batch_id`, it sends `job_message`. Otherwise it calls `claim_batch_summary` and sends `batch_message` when that returns a summary.
  - `run_claimed_job` calls `notify_settled(job_id)` only when `release_job` returns `True`. A job the stale reaper already failed returns `False`, so it never notifies twice.
  - `WorkerPool._stale_check_loop` calls `notify_settled` for each id from `detect_stale_jobs`, so a reaped job notifies as failed and its batch can still settle.
  - The cancel API takes `BackgroundTasks` and adds `notify_settled(job_id)` when the row is now `cancelled`. That covers a queued job cancelled from the UI, which can be the last of a batch. An active job is still `active` with `cancel_requested`, and its worker notifies. The `204` doesn't wait for the sends.
- [ ] **Step 1: Write the failing tests** (with a fake `send` that records a copy of its kwargs):
  - Done and error rows give the exact titles, bodies, tags and urls above. A cancelled row gives `None`. A 500-character error body is cut to 200.
  - `batch_message(BatchSummary(..., name="Mix", done=12, failed=1, cancelled=0))` gives body `"12 downloaded, 1 failed"`.
  - **Two push services:** with subscriptions on `https://web.push.apple.com/…` and `https://fcm.googleapis.com/…`, each call gets its own `vapid_claims` dict (`is not`), and `ttl=86400`.
  - **Dead endpoint:** the fake raises `WebPushException("gone", response=<410>)` for subscription A and succeeds for B. A is deleted, and B got the message.
  - **Unreachable:** the fake raises `requests.Timeout` for A. B is still sent, nothing raises, and A is kept.
  - Runner (monkeypatch `app.services.push.webpush`, seed one subscription): a single job that finishes calls `send` once with "Downloaded". A batch of 3 calls `send` once (the summary), only after the third settles. A raise inside `notify_settled` still leaves the job `done`. A job reaped as stale before its worker finishes sends nothing from the worker.
  - Stale loop: one reaped single job sends "Download failed".
  - Cancel API: cancelling the last queued job of a batch sends one summary (`TestClient` runs background tasks before it returns).
- [ ] **Step 2: Run them and see them fail**, then implement.
- [ ] **Step 3: Run `pnpm check`. Commit** `feat(server): web push for finished, failed and settled batches`

### Task 21: Notifications on this device

**Files:**
- Modify: `apps/web/src/sw.ts` (`push` and `notificationclick` handlers)
- Create: `apps/web/src/lib/push.ts`
- Modify: `apps/web/src/routes/Settings.svelte` (Notifications section with a switch)
- Modify: `apps/server/tests/e2e_server.py` (replace `app.services.push.webpush` with a no-op, so the e2e's fake subscriptions never reach the network)
- Modify: `DESIGN.md` (the switch), `README.md` (notifications on iPhone: install first, then turn on in Settings; set `YT_VAPID_SUBJECT`)
- Test: `apps/web/test/push.test.ts`, `apps/web/e2e/notifications.spec.ts`

**Interfaces:**
- Consumes: `/api/push/key`, `/api/push/subscriptions` (Task 19), the `PushMessage` JSON (Task 20).
- Produces:
  - `urlBase64ToUint8Array(s: string): Uint8Array<ArrayBuffer>`. The plain `Uint8Array` return type fails `svelte-check` as `applicationServerKey` under TS 6.
  - `pushSupport(env: { hasPushManager: boolean; isIOS: boolean; standalone: boolean; permission: NotificationPermission | "unsupported" }): "ready" | "install-first" | "blocked" | "unsupported"`. Checked in this order: iOS and not standalone → `"install-first"` (iOS Safari has no `PushManager` outside the installed app, so this must come first). No PushManager or permission `"unsupported"` → `"unsupported"`. Permission `"denied"` → `"blocked"`. Otherwise → `"ready"`.
  - `pushEnv()` reads the real browser: `isIOS` = `/iPad|iPhone|iPod/` in the user agent, or `navigator.platform === "MacIntel"` with `maxTouchPoints > 1` (iPadOS). `standalone` = `navigator.standalone === true` or `matchMedia("(display-mode: standalone)")`. `hasPushManager` = `"PushManager" in window && "serviceWorker" in navigator`. `permission` = `Notification.permission`, or `"unsupported"` when `Notification` is missing.
  - `currentSubscription(): Promise<PushSubscription | null>` (through `navigator.serviceWorker.ready`).
  - `enablePush(publicKey: string): Promise<"on" | "blocked">`. It is called from the switch's change handler only, and the key is fetched when Settings mounts. iOS needs `Notification.requestPermission()` to come straight from the tap, so nothing awaits the network before it. Not `"granted"` → `"blocked"`. Then `registration.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey })`, then `POST` the subscription's `toJSON()`.
  - `disablePush(): Promise<void>`: `DELETE` the endpoint, then `unsubscribe()`.
  - On mount, when a subscription exists, Settings `POST`s it again (an upsert). That restores the server row after a database reset.
  - `sw.ts` `push`: parse the JSON and always call `showNotification(title, { body, tag, icon: "/pwa-192x192.png", data: { url } })` inside `event.waitUntil`. Fall back to `{ title: "YourTube", body: "" }` when parsing fails. `notificationclick`: close it, resolve `data.url` against `self.location.origin`, find a window client (`matchAll({ type: "window", includeUncontrolled: true })`), `focus()` it and `navigate(url)`. Otherwise, or when `navigate` fails, `clients.openWindow(url)`.
  - Settings section "Notifications" (after Theme, as in the phone mockup) shows a switch labelled "Notifications on this device". It is a native `<input type="checkbox" role="switch">` inside a 44 px label row. It shows "On"/"Off" as text, not only the knob position. Its state comes from `currentSubscription()`. It is disabled unless the status is `ready` and the key has loaded. Under it, depending on the support status:
    - `install-first`: "Add YourTube to your Home Screen first."
    - `blocked`: "Notifications are blocked for YourTube in your browser settings."
    - `unsupported`: "This browser can't show notifications."
    - A failed subscribe or request: "Couldn't turn on notifications. Try again."
  - `DESIGN.md` gains the switch: track, knob, focus ring, the on state in the accent, the On/Off text, and the 44 px row.
- [ ] **Step 1: Write the failing unit tests** for `urlBase64ToUint8Array` (a known vector) and every `pushSupport` branch, including iOS not installed with no PushManager → `"install-first"`.
- [ ] **Step 2: Write the failing e2e tests.** An `addInitScript` stubs `Notification.requestPermission` (→ `"granted"`), `Notification.permission`, `PushManager.prototype.subscribe`, and `PushManager.prototype.getSubscription`. The fake subscription has an `https://push.example.test/…` endpoint, `toJSON()` with keys, and `unsubscribe()`. Its state lives in `localStorage`, so it survives a reload. Toggling on sends `POST /api/push/subscriptions` (wait for the `204`), and the switch is checked after a reload. Toggling off sends `DELETE`. A second test with an iPhone user agent (not standalone) shows "Add YourTube to your Home Screen first." and a disabled switch.
- [ ] **Step 3: Implement, run `pnpm check && pnpm e2e`. Commit** `feat(web): turn on notifications per device`
- [ ] **Step 4: Manual check on the owner's iPhone over Tailscale:** install, turn on, queue a short video, lock the phone, get the push, tap it, and land on the player. Also queue a 2-video playlist and get one summary. Record the result in the PR description. If the tap opens the start page instead of the player, record that too. iOS has had bugs with `navigate` from a notification. That is a follow-up, not a blocker.

### Task 22: Toast variants for failed jobs and batches

**Files:**
- Modify: `apps/server/app/schemas.py` (`QueueOut.batches: list[BatchOut]`, where `BatchOut` mirrors `BatchSummary`), `apps/server/app/api/jobs.py` (`get_queue` fills it from `recent_batch_summaries`), `api.gen.ts`
- Modify: `apps/web/src/lib/toasts.ts`, `apps/web/src/components/Toasts.svelte`, `apps/web/src/App.svelte`
- Modify: `apps/web/e2e/phone.spec.ts` (its stubbed `/api/queue` gains `batches: []` and its job `batch_id: null`)
- Modify: `DESIGN.md` (toast variants)
- Test: `tests/api/test_queue_api.py`, `apps/web/test/toasts.test.ts`, `apps/web/e2e/queue.spec.ts`

**Interfaces:**
- Consumes: `recent_batch_summaries` (Task 18), `JobOut.batch_id`, `batch_message` copy (Task 20). Toasts reuse the same words as pushes.
- Produces:
  - `type ToastKind = "done" | "failed" | "batch"`; `type Toast = { key: string; kind: ToastKind; title: string; body: string }`
  - `newEvents(seen: Set<string>, queue: QueueOut, silent: boolean): { toasts: Toast[]; seen: Set<string> }`. Keys are `done:<id>` (completed, `batch_id == null`), `failed:<id>` (failed, `batch_id == null`) and `batch:<uuid>` (`queue.batches`). Batch jobs never toast on their own. Copy: done `"Downloaded"` / title; failed `"Download failed"` / `"<title>: <error_message>"`; batch name / summary body. Old unprefixed ids in session storage are harmless, because the first poll is silent and marks everything seen.
  - `Toasts.svelte` renders `kind` as an icon plus a text label (never by colour alone). `failed` uses the danger token. Toasts close by `key`.
  - `newCompletions` is removed (replaced by `newEvents`), and `SEEN_KEY` stays.
- [ ] **Step 1: Write the failing tests**
  - API: after a batch of 2 settles and is claimed, `GET /api/queue` returns `batches[0]` with its name and counts.
  - Vitest: first poll silent → no toasts, but all keys are seen. A new failed single job → one `failed` toast. A completed job with a `batch_id` → no toast. A new batch → one `batch` toast with body `"2 downloaded"`. The same queue again → no toasts.
  - e2e: `page.route` stubs `/api/queue`. The first response is empty and later ones carry one failed single job and one batch. A "Download failed" toast and a batch toast appear. A real job would wait about 20 s behind the seeded "Slow video" (one worker), so the e2e doesn't enqueue one.
- [ ] **Step 2: Run them and see them fail**, then implement and run `pnpm typegen`.
- [ ] **Step 3: Run `pnpm check && pnpm e2e`. Commit** `feat: toasts for failed downloads and settled batches`

### Task 23: Product and design docs close-out

**Files:** `PRODUCT.md`, `DESIGN.md`, `README.md`

- [ ] **Step 1: Bring the docs up to date.**
  - `PRODUCT.md`: remove live push from out-of-scope (the phone user and platform are already there from Phase 5), and keep "no recommendations, avatars, view counts". A notification toggle is not a bell, so change "no … notification bells" to say so rather than delete it.
  - `DESIGN.md`: check that the logo mark, theme tile, phone section, player, switch and toast variants all match what shipped.
  - `README.md`: list the new env vars (`YT_VAPID_*`; `YT_HOST` is already there) and replace "later, push notifications" with the real notifications section.
- [ ] **Step 2: Run `pnpm check`. Commit** `docs: product, design and README for phone, PWA and notifications`

---

## Done when

- Every task above is committed and `pnpm check && pnpm e2e` pass on the branch.
- The usable result above works by hand.
