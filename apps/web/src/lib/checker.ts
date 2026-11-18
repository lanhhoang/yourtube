import type { components } from "./api.gen.ts";
import { messageFor } from "./errors.ts";

type VideoDetails = components["schemas"]["VideoDetails"];

export const CHECK_CONCURRENCY = 2;

export type CheckResult = { ok: true; details: VideoDetails } | { ok: false; message: string };

export function createChecker(opts: {
  lookup: (url: string) => Promise<VideoDetails>;
  onResult: (index: number, result: CheckResult) => void;
  concurrency?: number;
}): { want(index: number, url: string): void; drop(index: number): void; stop(): void } {
  const limit = opts.concurrency ?? CHECK_CONCURRENCY;
  const queue = new Map<number, string>();
  const seen = new Set<number>(); // running or done
  let running = 0;
  let stopped = false;

  function pump() {
    while (!stopped && running < limit) {
      const next = queue.entries().next();
      if (next.done) return;
      const [index, url] = next.value;
      queue.delete(index);
      seen.add(index);
      running++;
      opts
        .lookup(url)
        .then(
          (details): CheckResult => ({ ok: true, details }),
          (err): CheckResult => ({ ok: false, message: messageFor(err) }),
        )
        .then((result) => {
          running--;
          if (stopped) return;
          opts.onResult(index, result);
          pump();
        });
    }
  }

  return {
    want(index, url) {
      if (stopped || seen.has(index) || queue.has(index)) return;
      queue.set(index, url);
      pump();
    },
    drop(index) {
      queue.delete(index);
    },
    stop() {
      stopped = true;
      queue.clear();
    },
  };
}
