<script lang="ts">
  import { api, call } from "../lib/api.ts";
  import { ApiError, messageFor } from "../lib/errors.ts";
  import { formatSize, qualityLabel } from "../lib/library.ts";
  import type { JobOut } from "../lib/queue.ts";
  import { navigate } from "../lib/router.svelte.ts";
  import { canShareFiles, fetchBlob, fileName, saveMode } from "../lib/save.ts";

  let { id }: { id: number } = $props();

  let job = $state<JobOut | null>(null);
  let phase = $state<"loading" | "ready" | "missing" | "error">("loading");
  let error = $state("");
  let playError = $state(false);
  let confirming = $state(false);
  let deleting = $state(false);
  // Save in share mode: idle -> preparing (fetching) -> ready (blob in hand) -> idle, or failed.
  let save = $state<"idle" | "preparing" | "ready" | "failed">("idle");
  let progress = $state(0);
  let blob: Blob | null = null;
  let confirmTimer: ReturnType<typeof setTimeout> | undefined;
  const abort = new AbortController();

  const src = $derived(`/api/downloads/${id}/file?inline=1`);
  const meta = $derived(
    job
      ? [job.uploader, qualityLabel(job), formatSize(job.file_size), job.media_format]
          .filter(Boolean)
          .join(" · ")
      : "",
  );
  const mode = $derived(
    job && save !== "failed"
      ? saveMode(job.file_size, canShareFiles() && matchMedia("(pointer: coarse)").matches)
      : "link",
  );

  $effect(() => {
    void (async () => {
      try {
        job = await call(api.GET("/api/downloads/{job_id}", { params: { path: { job_id: id } } }));
        phase = "ready";
      } catch (err) {
        if (err instanceof ApiError && err.code === "not_found") phase = "missing";
        else {
          error = messageFor(err);
          phase = "error";
        }
      }
    })();
    return () => {
      abort.abort();
      clearTimeout(confirmTimer);
    };
  });

  async function prepare() {
    if (save === "preparing") return;
    save = "preparing";
    progress = 0;
    try {
      blob = await fetchBlob(`/api/downloads/${id}/file`, (f) => (progress = f), abort.signal);
      save = "ready";
    } catch {
      if (!abort.signal.aborted) save = "failed";
    }
  }

  async function share() {
    if (!job || !blob) return;
    const file = new File([blob], fileName(job.title, job.media_format), { type: blob.type });
    try {
      await navigator.share({ files: [file] });
    } catch (err) {
      // Closing the sheet is not a failure; the button stays so it can be tapped again.
      if (!(err instanceof DOMException && err.name === "AbortError")) save = "failed";
    }
  }

  async function remove() {
    if (!confirming) {
      confirming = true;
      confirmTimer = setTimeout(() => (confirming = false), 4000);
      return;
    }
    if (deleting) return;
    deleting = true;
    clearTimeout(confirmTimer);
    try {
      await call(api.DELETE("/api/library/{job_id}", { params: { path: { job_id: id } } }));
      navigate({ name: "library" });
    } catch (err) {
      error = messageFor(err);
      confirming = false;
    } finally {
      deleting = false;
    }
  }

  const button =
    "inline-flex min-h-9 cursor-pointer items-center rounded-pill border border-line-strong bg-transparent px-5 py-2 text-sm font-medium text-fg no-underline hover:bg-raised disabled:opacity-50";
  const primary =
    "inline-flex min-h-9 cursor-pointer items-center rounded-pill border-0 bg-action px-5 py-2 text-sm font-semibold text-on-action no-underline hover:opacity-90 disabled:opacity-50";
</script>

{#if phase === "missing"}
  <p class="m-0 text-base">
    This download no longer exists. <a href="#/" class="text-fg">Back to the library</a>
  </p>
{:else if phase === "error"}
  <p class="m-0 text-danger" role="alert">{error}</p>
{:else if job && job.status !== "done"}
  <p class="m-0 text-base">
    This download isn't finished yet. <a href="#/queue" class="text-fg">Open the queue</a>
  </p>
{:else if job}
  <div class="mx-auto flex max-w-[960px] flex-col gap-4">
    <div class="overflow-hidden rounded-thumb bg-black">
      {#if job.media_kind === "audio"}
        <!-- biome-ignore lint/a11y/useMediaCaption: downloaded files carry no caption track -->
        <audio controls {src} class="w-full" onerror={() => (playError = true)}></audio>
      {:else}
        <!-- svelte-ignore a11y_media_has_caption -->
        <!-- biome-ignore lint/a11y/useMediaCaption: downloaded files carry no caption track -->
        <video
          controls
          playsinline
          preload="metadata"
          {src}
          class="aspect-video w-full bg-black"
          onerror={() => (playError = true)}
        ></video>
      {/if}
    </div>
    {#if playError}
      <p class="m-0 text-warn" role="alert">
        This device can't play this file. Save it and open it in VLC.
      </p>
    {/if}
    <div class="min-w-0">
      <h1 class="m-0 text-xl font-bold tracking-[-0.01em]">{job.title ?? job.url}</h1>
      {#if meta}
        <p class="m-0 mt-1 text-sm text-muted">{meta}</p>
      {/if}
    </div>
    <div class="flex flex-wrap items-center gap-2">
      {#if mode === "share" && save === "idle"}
        <button type="button" class={primary} onclick={prepare}>Save</button>
      {:else if mode === "share" && save === "preparing"}
        <button type="button" class={primary} disabled>
          Preparing… <span class="tabular ml-1">{Math.round(progress * 100)}%</span>
        </button>
      {:else if mode === "share" && save === "ready"}
        <button type="button" class={primary} onclick={share}>Share file</button>
      {:else}
        <a class={primary} href="/api/downloads/{id}/file" download>Save</a>
      {/if}
      <button
        type="button"
        class={button}
        disabled={deleting}
        onclick={remove}
        onblur={() => (confirming = false)}
      >
        {confirming ? "Confirm delete" : "Delete"}
      </button>
    </div>
    {#if save === "failed"}
      <p class="m-0 text-sm text-danger" role="alert">Couldn't open the share sheet.</p>
    {/if}
    {#if error}
      <p class="m-0 text-sm text-danger" role="alert">{error}</p>
    {/if}
  </div>
{/if}
