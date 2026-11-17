<script lang="ts">
  import { api, call } from "../lib/api.ts";
  import { messageFor } from "../lib/errors.ts";
  import { formatSize, qualityLabel } from "../lib/library.ts";
  import type { JobOut } from "../lib/queue.ts";

  let { job, ondeleted }: { job: JobOut; ondeleted: (id: number) => void } = $props();

  let confirming = $state(false);
  let deleting = $state(false);
  let error = $state("");
  let timer: ReturnType<typeof setTimeout> | undefined;

  const inProgress = $derived(job.status !== "done");
  const meta = $derived(
    [job.uploader, qualityLabel(job), formatSize(job.file_size)].filter(Boolean).join(" · "),
  );

  function reset() {
    clearTimeout(timer);
    confirming = false;
  }

  async function remove() {
    if (!confirming) {
      confirming = true;
      error = "";
      timer = setTimeout(reset, 4000);
      return;
    }
    if (deleting) return;
    deleting = true;
    reset();
    try {
      await call(api.DELETE("/api/library/{job_id}", { params: { path: { job_id: job.id } } }));
      ondeleted(job.id);
    } catch (err) {
      error = messageFor(err);
    } finally {
      deleting = false;
    }
  }

  const item =
    "cursor-pointer rounded-control border-0 bg-transparent px-3 py-1.5 text-left text-sm font-medium text-fg no-underline transition-colors duration-(--duration-fast) hover:bg-raised disabled:opacity-50";
</script>

<article class="group relative flex min-w-0 flex-col gap-2">
  <div class="relative aspect-video overflow-hidden rounded-thumb bg-surface">
    {#if job.thumbnail}
      <img src={job.thumbnail} alt="" loading="lazy" class="size-full object-cover">
    {/if}
    {#if inProgress}
      <div class="absolute inset-x-0 bottom-0 h-1 bg-black/50">
        <div
          class="h-full bg-accent transition-[width] duration-(--duration-base) ease-(--ease-out)"
          style:width="{job.progress}%"
        ></div>
      </div>
    {:else}
      <div
        class="absolute top-2 right-2 flex flex-col rounded-control border border-line-strong bg-surface p-1 opacity-0 shadow-[0_8px_24px_rgb(0_0_0/0.4)] transition-opacity duration-(--duration-fast) group-focus-within:opacity-100 group-hover:opacity-100"
      >
        <a class={item} href="/api/downloads/{job.id}/file" download>Download file</a>
        <button type="button" class={item} disabled={deleting} onclick={remove} onblur={reset}>
          {confirming ? "Confirm delete" : "Delete"}
        </button>
      </div>
    {/if}
  </div>
  <div class="min-w-0">
    <h3 class="m-0 line-clamp-2 text-base font-semibold">{job.title ?? job.url}</h3>
    {#if inProgress}
      <p class="m-0 text-sm text-muted">
        {job.status === "active" ? "Downloading" : "Queued"}
        <span class="tabular"
          >{job.status === "active" ? ` ${Math.round(job.progress)}%` : ""}</span
        >
      </p>
    {:else if meta}
      <p class="m-0 truncate text-sm text-muted">{meta}</p>
    {/if}
    {#if error}
      <p class="m-0 text-sm text-danger">{error}</p>
    {/if}
  </div>
</article>
