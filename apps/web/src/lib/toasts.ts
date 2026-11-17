import type { JobOut } from "./queue.ts";

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

// Every completed id joins `seen`. Jobs not seen before become toasts, unless `silent`.
export function newCompletions(
  seen: Set<string>,
  completed: JobOut[],
  silent: boolean,
): { toasts: JobOut[]; seen: Set<string> } {
  const next = new Set(seen);
  const toasts: JobOut[] = [];
  for (const job of completed) {
    const id = String(job.id);
    if (!next.has(id) && !silent) toasts.push(job);
    next.add(id);
  }
  return { toasts, seen: next };
}
