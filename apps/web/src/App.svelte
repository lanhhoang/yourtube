<script lang="ts">
  import LeftRail from "./components/LeftRail.svelte";
  import Toasts, { type Toast } from "./components/Toasts.svelte";
  import TopBar from "./components/TopBar.svelte";
  import { api, call } from "./lib/api.ts";
  import { latest } from "./lib/latest.ts";
  import { createPoller } from "./lib/poll.ts";
  import type { QueueOut } from "./lib/queue.ts";
  import { router } from "./lib/router.svelte.ts";
  import { section } from "./lib/router.ts";
  import { watchSystemTheme } from "./lib/theme.ts";
  import { newCompletions, readSeen, SEEN_KEY } from "./lib/toasts.ts";
  import Library from "./routes/Library.svelte";
  import Queue from "./routes/Queue.svelte";

  const TOAST_MS = 5000;

  let queue = $state<QueueOut | null>(null);
  let toasts = $state<Toast[]>([]);
  let firstPoll = true;
  const ticket = latest();

  function closeToast(id: number) {
    toasts = toasts.filter((t) => t.id !== id);
  }

  async function refreshQueue(): Promise<void> {
    const current = ticket();
    let next: QueueOut;
    try {
      next = await call(api.GET("/api/queue"));
    } catch {
      return; // keep the last good data
    }
    if (!current()) return;
    queue = next;
    const result = newCompletions(
      readSeen(sessionStorage.getItem(SEEN_KEY)),
      next.completed,
      firstPoll,
    );
    firstPoll = false;
    sessionStorage.setItem(SEEN_KEY, JSON.stringify([...result.seen]));
    for (const job of result.toasts) {
      toasts = [...toasts, { id: job.id, title: job.title ?? job.url }];
      setTimeout(() => closeToast(job.id), TOAST_MS);
    }
  }

  $effect(() => watchSystemTheme());
  $effect(() => {
    const poller = createPoller(refreshQueue, 2000);
    poller.start();
    return () => poller.stop();
  });
</script>

<div class="flex h-screen flex-col">
  <TopBar />
  <div class="flex min-h-0 flex-1">
    <LeftRail active={section(router.route)} queueCount={queue?.active.length ?? 0} />
    <main class="min-w-0 flex-1 overflow-y-auto p-6">
      {#if router.route.name === "queue"}
        <Queue {queue} refresh={refreshQueue} />
      {:else if router.route.name === "settings"}
        <h1 class="m-0 text-xl font-bold">Settings</h1>
      {:else if router.route.name === "fetch"}
        <h1 class="m-0 text-xl font-bold">Fetch</h1>
      {:else}
        <Library {queue} />
      {/if}
    </main>
  </div>
  <Toasts {toasts} onclose={closeToast} />
</div>
