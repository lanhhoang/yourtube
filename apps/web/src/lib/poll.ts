// Runs `task` now and then `intervalMs` after each run finishes (never overlapping).
// While `isHidden()` is true a tick skips the task. After stop() nothing more runs.
export function createPoller(
  task: () => Promise<void>,
  intervalMs: number,
  isHidden: () => boolean = () => document.hidden,
): { start(): void; stop(): void } {
  let timer: ReturnType<typeof setTimeout> | undefined;
  let running = false;

  async function tick(): Promise<void> {
    timer = undefined;
    if (!isHidden()) {
      try {
        await task();
      } catch {}
    }
    if (running) timer = setTimeout(tick, intervalMs);
  }

  return {
    start() {
      if (running) return;
      running = true;
      void tick();
    },
    stop() {
      running = false;
      if (timer !== undefined) clearTimeout(timer);
      timer = undefined;
    },
  };
}
