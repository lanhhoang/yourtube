<script lang="ts">
  import { api, call } from "../lib/api.ts";
  import { messageFor } from "../lib/errors.ts";
  import type { JobOut, QueueOut } from "../lib/queue.ts";

  let { queue, refresh }: { queue: QueueOut | null; refresh: () => Promise<void> } = $props();

  let busy = $state<Set<number>>(new Set());
  let errors = $state<Record<number, string>>({});

  async function act(job: JobOut, run: () => Promise<unknown>) {
    if (busy.has(job.id)) return;
    busy = new Set(busy).add(job.id);
    delete errors[job.id];
    try {
      await run();
      await refresh();
    } catch (err) {
      errors[job.id] = messageFor(err);
    } finally {
      const next = new Set(busy);
      next.delete(job.id);
      busy = next;
    }
  }

  let dismissingAll = $state(false);
  let dismissAllError = $state("");

  async function dismissAll() {
    if (dismissingAll) return;
    dismissingAll = true;
    dismissAllError = "";
    try {
      await call(api.POST("/api/queue/dismiss-failed"));
      await refresh();
    } catch (err) {
      dismissAllError = messageFor(err);
    } finally {
      dismissingAll = false;
    }
  }

  const params = (job: JobOut) => ({ params: { path: { job_id: job.id } } });
  const cancel = (j: JobOut) =>
    act(j, () => call(api.POST("/api/downloads/{job_id}/cancel", params(j))));
  const retry = (j: JobOut) =>
    act(j, () => call(api.POST("/api/downloads/{job_id}/retry", params(j))));
  const dismiss = (j: JobOut) =>
    act(j, () => call(api.POST("/api/downloads/{job_id}/dismiss", params(j))));

  const btn =
    "min-h-[44px] min-w-[44px] cursor-pointer rounded-pill border border-line-strong bg-transparent px-3 py-1 text-sm md:min-h-0 md:min-w-0 font-medium text-fg transition-colors duration-(--duration-fast) hover:bg-raised disabled:cursor-default disabled:opacity-50";
</script>

{#snippet thumb(job: JobOut)}
  <div class="aspect-video w-28 shrink-0 md:w-40 overflow-hidden rounded-thumb bg-surface">
    {#if job.thumbnail}
      <img src={job.thumbnail} alt="" loading="lazy" class="size-full object-cover">
    {/if}
  </div>
{/snippet}

<h1 class="m-0 text-xl font-bold tracking-[-0.01em]">Queue</h1>

{#if queue}
  {#if queue.active.length === 0 && queue.failed.length === 0}
    <p class="mt-6 text-muted">Nothing in the queue.</p>
  {/if}

  {#if queue.active.length > 0}
    <ul class="m-0 mt-6 flex list-none flex-col gap-4 p-0">
      {#each queue.active as job (job.id)}
        <li class="flex flex-wrap items-center gap-x-4 gap-y-2 md:flex-nowrap">
          {@render thumb(job)}
          <div class="min-w-0 flex-1 basis-40">
            <p class="m-0 truncate text-base font-semibold">{job.title ?? job.url}</p>
            <p class="m-0 truncate text-sm text-muted">
              {job.uploader ?? ""}{job.uploader ? " · " : ""}{job.status === "active"
                ? "Downloading"
                : "Queued"}
            </p>
            <div class="mt-2 flex items-center gap-3">
              <div
                class="h-1 flex-1 overflow-hidden rounded-pill bg-raised"
                role="progressbar"
                aria-label="Progress"
                aria-valuemin="0"
                aria-valuemax="100"
                aria-valuenow={Math.round(job.progress)}
              >
                <div
                  class="h-full bg-accent transition-[width] duration-(--duration-base) ease-(--ease-out)"
                  style:width="{job.progress}%"
                ></div>
              </div>
              <span class="tabular w-10 text-right text-xs text-muted"
                >{Math.round(job.progress)}%</span
              >
            </div>
            {#if errors[job.id]}
              <p class="m-0 mt-1 text-sm text-danger">{errors[job.id]}</p>
            {/if}
          </div>
          <button
            type="button"
            class="{btn} ml-auto"
            disabled={busy.has(job.id)}
            onclick={() => cancel(job)}
          >
            Cancel
          </button>
        </li>
      {/each}
    </ul>
  {/if}

  {#if queue.failed.length > 0}
    <div class="mt-8 mb-3 flex items-center justify-between gap-3">
      <h2 class="m-0 text-lg font-semibold">Failed</h2>
      {#if queue.failed.length >= 2}
        <button type="button" class={btn} disabled={dismissingAll} onclick={dismissAll}>
          Dismiss all
        </button>
      {/if}
    </div>
    {#if dismissAllError}
      <p class="m-0 mb-3 text-sm text-danger" role="alert">{dismissAllError}</p>
    {/if}
    <ul class="m-0 flex list-none flex-col gap-4 p-0">
      {#each queue.failed as job (job.id)}
        <li class="flex flex-wrap items-center gap-x-4 gap-y-2 md:flex-nowrap">
          {@render thumb(job)}
          <div class="min-w-0 flex-1 basis-40">
            <p class="m-0 truncate text-base font-semibold">{job.title ?? job.url}</p>
            <p class="m-0 text-sm text-danger">{job.error_message ?? "The download failed."}</p>
            {#if errors[job.id]}
              <p class="m-0 mt-1 text-sm text-danger">{errors[job.id]}</p>
            {/if}
          </div>
          <div class="ml-auto flex gap-2">
            <button
              type="button"
              class={btn}
              disabled={busy.has(job.id)}
              onclick={() => retry(job)}
            >
              Retry
            </button>
            <button
              type="button"
              class={btn}
              disabled={busy.has(job.id)}
              onclick={() => dismiss(job)}
            >
              Dismiss
            </button>
          </div>
        </li>
      {/each}
    </ul>
  {/if}
{/if}
