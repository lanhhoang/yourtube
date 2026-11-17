<script lang="ts">
  import FormatPicker from "../components/FormatPicker.svelte";
  import QualitySelect from "../components/QualitySelect.svelte";
  import { api, call } from "../lib/api.ts";
  import type { components } from "../lib/api.gen.ts";
  import { messageFor } from "../lib/errors.ts";
  import { expectedContainer, hasExact, type Selection } from "../lib/format-picker.ts";
  import { DEFAULT_CAP, type QualityCap } from "../lib/quality.ts";
  import { href } from "../lib/router.ts";

  type Video = components["schemas"]["VideoDetails"];
  type Tab = "video" | "audio" | "advanced";

  let { video }: { video: Video } = $props();

  let cap = $state<QualityCap>(DEFAULT_CAP);
  let selection = $state<Selection>({ videoId: null, audioId: null });
  let subtitles = $state(false);
  let tab = $state<Tab>("video");
  let template = $state("");
  let bitrate = $state("");
  let adding = $state(false);
  let added = $state(false);
  let error = $state("");

  const TABS: { id: Tab; label: string }[] = [
    { id: "video", label: "Video" },
    { id: "audio", label: "Audio" },
    { id: "advanced", label: "Advanced" },
  ];

  const exact = $derived(hasExact(selection));
  const container = $derived(expectedContainer(video.picker, selection));
  const minutes = $derived(video.duration === null ? "" : formatDuration(video.duration));

  function formatDuration(total: number): string {
    const h = Math.floor(total / 3600);
    const m = Math.floor((total % 3600) / 60);
    const s = String(total % 60).padStart(2, "0");
    return h > 0 ? `${h}:${String(m).padStart(2, "0")}:${s}` : `${m}:${s}`;
  }

  async function add() {
    if (adding) return;
    adding = true;
    error = "";
    added = false;
    try {
      await call(
        api.POST("/api/downloads", {
          body: {
            jobs: [
              {
                url: video.url,
                title: video.title,
                uploader: video.uploader,
                duration: video.duration,
                thumbnail: video.thumbnail,
                quality_cap: cap,
                video_format_id: selection.videoId,
                audio_format_id: selection.audioId,
                subtitles,
                output_template: template.trim() || null,
                audio_bitrate: bitrate.trim() || null,
              },
            ],
          },
        }),
      );
      added = true;
    } catch (err) {
      error = messageFor(err);
    } finally {
      adding = false;
    }
  }

  const input =
    "w-full rounded-control border border-line-strong bg-surface px-3 py-2 text-base text-fg placeholder:text-muted";
</script>

<div class="grid max-w-6xl grid-cols-[minmax(0,1fr)_22rem] gap-8">
  <section class="flex min-w-0 flex-col gap-3">
    <div class="aspect-video overflow-hidden rounded-thumb bg-surface">
      {#if video.thumbnail}
        <img src={video.thumbnail} alt="" class="size-full object-cover">
      {/if}
    </div>
    <h1 class="m-0 text-xl font-bold tracking-[-0.01em]">{video.title}</h1>
    <p class="m-0 text-sm text-muted">
      {[video.uploader, minutes].filter(Boolean).join(" · ")}
    </p>
    {#if video.playlist_url}
      <p class="m-0 text-sm text-muted">
        Part of a playlist ·
        <a class="text-fg" href={href({ name: "fetch", urls: video.playlist_url })}
          >Open playlist</a
        >
      </p>
    {/if}
    <label class="flex items-center gap-2 text-base">
      <input type="checkbox" bind:checked={subtitles} class="size-4 accent-(--color-action)">
      Subtitles
    </label>
    <div class="flex items-center gap-3">
      <button
        type="button"
        disabled={adding}
        onclick={add}
        class="cursor-pointer rounded-pill border-0 bg-action px-5 py-2 text-sm font-semibold text-on-action disabled:opacity-50"
      >
        Add to queue
      </button>
      {#if added}
        <p class="m-0 text-sm text-muted" role="status">
          Added to queue. <a class="text-fg" href="#/queue">Open queue</a>
        </p>
      {/if}
      {#if error}
        <p class="m-0 text-sm text-danger" role="alert">{error}</p>
      {/if}
    </div>
  </section>

  <aside class="flex min-w-0 flex-col gap-4">
    <QualitySelect bind:value={cap} dimmed={exact} />

    <div
      role="tablist"
      aria-label="Format"
      class="flex gap-1 self-start rounded-pill bg-raised p-1"
    >
      {#each TABS as t (t.id)}
        <button
          type="button"
          role="tab"
          id="tab-{t.id}"
          aria-selected={tab === t.id}
          aria-controls="panel"
          onclick={() => (tab = t.id)}
          class="cursor-pointer rounded-pill border-0 px-4 py-1.5 text-sm font-medium transition-colors duration-(--duration-fast) {tab ===
          t.id
            ? "bg-action text-on-action"
            : "bg-transparent text-fg"}"
        >
          {t.label}
        </button>
      {/each}
    </div>

    <div id="panel" role="tabpanel" aria-labelledby="tab-{tab}" class="flex flex-col gap-3">
      {#if tab === "video"}
        <FormatPicker kind="video" rows={video.picker.video_streams} bind:selection />
      {:else if tab === "audio"}
        <FormatPicker kind="audio" rows={video.picker.audio_streams} bind:selection />
      {:else}
        <div>
          <label for="template" class="mb-1 block text-sm font-medium">Output template</label>
          <input
            id="template"
            type="text"
            class={input}
            placeholder="%(title)s.%(ext)s"
            bind:value={template}
          >
        </div>
        <div>
          <label for="bitrate" class="mb-1 block text-sm font-medium">Audio bitrate</label>
          <input id="bitrate" type="text" class={input} placeholder="192K" bind:value={bitrate}>
        </div>
      {/if}
    </div>

    {#if tab !== "advanced"}
      <p class="m-0 text-sm text-muted">
        Container: <span class="tabular text-fg">{exact ? container : "chosen automatically"}</span>
      </p>
    {/if}
  </aside>
</div>
