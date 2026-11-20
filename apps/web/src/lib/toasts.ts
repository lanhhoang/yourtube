import type { QueueOut } from "./queue.ts";

export const SEEN_KEY = "yt-seen-completed-jobs";

export function readSeen(stored: string | null): Set<string> {
  if (!stored) return new Set();
  try {
    const parsed: unknown = JSON.parse(stored);
    return Array.isArray(parsed) ? new Set(parsed.map(String)) : new Set();
  } catch {
    return new Set();
  }
}

export type ToastKind = "done" | "failed" | "batch";
export type Toast = { key: string; kind: ToastKind; title: string; body: string };

type BatchOut = QueueOut["batches"][number];

// Same words as the push body (app/services/push.py batch_message).
function batchBody(b: BatchOut): string {
  const parts = [
    b.done ? `${b.done} downloaded` : "",
    b.failed ? `${b.failed} failed` : "",
    b.cancelled ? `${b.cancelled} cancelled` : "",
  ].filter(Boolean);
  return parts.length ? parts.join(", ") : "0 downloaded";
}

// Every event key joins `seen`. Events not seen before become toasts, unless `silent`.
// Jobs in a batch never toast on their own; the batch does.
export function newEvents(
  seen: Set<string>,
  queue: QueueOut,
  silent: boolean,
): { toasts: Toast[]; seen: Set<string> } {
  const next = new Set(seen);
  const toasts: Toast[] = [];
  const add = (toast: Toast) => {
    if (!next.has(toast.key) && !silent) toasts.push(toast);
    next.add(toast.key);
  };
  for (const job of queue.completed) {
    if (job.batch_id != null) continue;
    add({
      key: `done:${job.id}`,
      kind: "done",
      title: "Downloaded",
      body: job.title ?? job.url,
    });
  }
  for (const job of queue.failed) {
    if (job.batch_id != null) continue;
    add({
      key: `failed:${job.id}`,
      kind: "failed",
      title: "Download failed",
      body: `${job.title ?? job.url}: ${job.error_message ?? "Unknown error"}`,
    });
  }
  for (const b of queue.batches) {
    add({ key: `batch:${b.batch_id}`, kind: "batch", title: b.name, body: batchBody(b) });
  }
  return { toasts, seen: next };
}
