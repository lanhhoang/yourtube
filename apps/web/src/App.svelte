<script lang="ts">
  import LeftRail from "./components/LeftRail.svelte";
  import TabBar from "./components/TabBar.svelte";
  import Toasts from "./components/Toasts.svelte";
  import TopBar from "./components/TopBar.svelte";
  import { api, call } from "./lib/api.ts";
  import { latest } from "./lib/latest.ts";
  import { createPoller } from "./lib/poll.ts";
  import type { QueueOut } from "./lib/queue.ts";
  import { router } from "./lib/router.svelte.ts";
  import { section } from "./lib/router.ts";
  import { watchSystemTheme } from "./lib/theme.ts";
  import { newEvents, readSeen, SEEN_KEY, type Toast } from "./lib/toasts.ts";
  import Fetch from "./routes/Fetch.svelte";
  import Library from "./routes/Library.svelte";
  import Queue from "./routes/Queue.svelte";
  import Settings from "./routes/Settings.svelte";
  import Watch from "./routes/Watch.svelte";

  const TOAST_MS = 5000;

  let queue = $state<QueueOut | null>(null);
  let toasts = $state<Toast[]>([]);
  let firstPoll = true;
  const ticket = latest();

  function closeToast(key: string) {
    toasts = toasts.filter((t) => t.key !== key);
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
    const result = newEvents(readSeen(sessionStorage.getItem(SEEN_KEY)), next, firstPoll);
    firstPoll = false;
    sessionStorage.setItem(SEEN_KEY, JSON.stringify([...result.seen]));
    for (const toast of result.toasts) {
      toasts = [...toasts, toast];
      setTimeout(() => closeToast(toast.key), TOAST_MS);
    }
  }

  $effect(() => watchSystemTheme());
  $effect(() => {
    const poller = createPoller(refreshQueue, 2000);
    poller.start();
    return () => poller.stop();
  });
</script>

<div class="flex h-dvh flex-col">
  <TopBar />
  <div class="flex min-h-0 flex-1">
    <LeftRail active={section(router.route)} queueCount={queue?.active.length ?? 0} />
    <main class="min-w-0 flex-1 overflow-y-auto p-4 md:p-6">
      {#if router.route.name === "queue"}
        <Queue {queue} refresh={refreshQueue} />
      {:else if router.route.name === "settings"}
        <Settings />
      {:else if router.route.name === "watch"}
        {#key router.route.id}
          <Watch id={router.route.id} />
        {/key}
      {:else if router.route.name === "fetch"}
        <Fetch urls={router.route.urls} />
      {:else}
        <Library {queue} />
      {/if}
    </main>
  </div>
  <TabBar active={section(router.route)} queueCount={queue?.active.length ?? 0} />
  <Toasts {toasts} onclose={closeToast} />
</div>
