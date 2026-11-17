import type { components } from "./api.gen.ts";

export type JobOut = components["schemas"]["JobOut"];
export type QueueOut = components["schemas"]["QueueOut"];

// True when a job in `prev` is gone from `next` (it finished, failed or was cancelled).
export function leftActive(prev: JobOut[], next: JobOut[]): boolean {
  const ids = new Set(next.map((j) => j.id));
  return prev.some((j) => !ids.has(j.id));
}
