<script lang="ts">
  import { api, call } from "../lib/api.ts";
  import { messageFor } from "../lib/errors.ts";
  import { formatSize, qualityLabel } from "../lib/library.ts";
  import type { JobOut } from "../lib/queue.ts";

  let {
    job,
    ondeleted,
    selecting = false,
    selected = false,
    ontoggle,
  }: {
    job: JobOut;
    ondeleted: (id: number) => void;
    selecting?: boolean;
    selected?: boolean;
    ontoggle?: (id: number) => void;
  } = $props();

  let confirming = $state(false);
  let deleting = $state(false);
  let error = $state("");
  let timer: ReturnType<typeof setTimeout> | undefined;

  const inProgress = $derived(job.status !== "done");
  const picking = $derived(selecting && job.status === "done");
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

<article class="group relative flex min-w-0 flex-row gap-3 md:flex-col md:gap-2">
  {#if picking}
    <!-- biome-ignore lint/a11y/noLabelWithoutControl: the input inside has its own aria-label; the label widens the tap area to the whole card -->
    <label class="absolute inset-0 z-10 cursor-pointer">
      <div
        class="absolute top-0 left-0 grid size-[44px] place-items-center md:top-2 md:left-2 md:size-6 md:rounded-control md:bg-black/60"
      >
        <input
          type="checkbox"
          checked={selected}
          aria-label={job.title ?? job.url}
          onchange={() => ontoggle?.(job.id)}
          class="size-4 accent-(--color-action)"
        >
      </div>
    </label>
  {/if}
  <div
    class="relative aspect-video w-2/5 shrink-0 overflow-hidden rounded-thumb bg-surface md:w-auto md:shrink {selected
      ? "ring-2 ring-fg"
      : ""}"
  >
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
    {:else if !picking}
      <div
        class="absolute top-2 right-2 z-10 hidden flex-col md:flex rounded-control border border-line-strong bg-surface p-1 opacity-0 shadow-[0_8px_24px_rgb(0_0_0/0.4)] transition-opacity duration-(--duration-fast) group-focus-within:opacity-100 group-hover:opacity-100"
      >
        <a class={item} href="/api/downloads/{job.id}/file" download>Download file</a>
        <button type="button" class={item} disabled={deleting} onclick={remove} onblur={reset}>
          {confirming ? "Confirm delete" : "Delete"}
        </button>
      </div>
    {/if}
  </div>
  <div class="min-w-0 flex-1">
    <h3 class="m-0 line-clamp-2 text-base font-semibold">
      {#if inProgress || picking}
        {job.title ?? job.url}
      {:else}
        <a
          href="#/watch/{job.id}"
          class="text-fg no-underline after:absolute after:inset-0 after:content-[''] hover:underline"
          >{job.title ?? job.url}</a
        >
      {/if}
    </h3>
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
