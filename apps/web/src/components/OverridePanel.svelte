<script lang="ts">
  import type { EntryState, Header, Override } from "../lib/playlist.ts";
  import FormatPicker from "./FormatPicker.svelte";

  let {
    item,
    header,
    onchange,
    onclose,
  }: {
    item: EntryState;
    header: Header;
    onchange: (o: Override | null) => void;
    onclose: () => void;
  } = $props();

  const details = $derived(
    typeof item.check === "object" && item.check.ok ? item.check.details : null,
  );
  const override = $derived(item.override);
  const title = $derived(item.entry.title ?? details?.title ?? item.entry.url);

  function useCustom() {
    onchange({
      selection: { videoId: null, audioId: null },
      subtitles: header.subtitles,
      outputTemplate: header.outputTemplate,
      audioBitrate: header.audioBitrate,
    });
  }

  function patch(p: Partial<Override>) {
    if (override) onchange({ ...override, ...p });
  }

  const input =
    "w-full rounded-control border border-line-strong bg-surface px-3 py-2 text-base text-fg placeholder:text-muted";
  const seg =
    "cursor-pointer rounded-pill border-0 px-4 py-1.5 text-sm font-medium transition-colors duration-(--duration-fast)";
</script>

<svelte:window onkeydown={(e) => e.key === "Escape" && onclose()} />

<aside
  aria-label="Settings for {title}"
  class="sticky top-0 flex max-h-[calc(100vh-7rem)] w-[22rem] shrink-0 flex-col gap-4 self-start overflow-y-auto rounded-control border border-line bg-surface p-4"
>
  <div class="flex items-start justify-between gap-3">
    <h2 class="m-0 line-clamp-2 text-lg font-semibold">{title}</h2>
    <button
      type="button"
      onclick={onclose}
      class="cursor-pointer rounded-pill border-0 bg-raised px-3 py-1 text-sm font-medium text-fg"
    >
      Close
    </button>
  </div>

  {#if !details}
    <p class="m-0 text-sm text-muted" role="status">Still checking…</p>
  {:else}
    <fieldset class="m-0 flex gap-1 self-start rounded-pill border-0 bg-raised p-1">
      <legend class="sr-only">Settings source</legend>
      <button
        type="button"
        aria-pressed={override === null}
        onclick={() => onchange(null)}
        class="{seg} {override === null ? "bg-action text-on-action" : "bg-transparent text-fg"}"
      >
        Playlist setting
      </button>
      <button
        type="button"
        aria-pressed={override !== null}
        onclick={() => override === null && useCustom()}
        class="{seg} {override !== null ? "bg-action text-on-action" : "bg-transparent text-fg"}"
      >
        Custom
      </button>
    </fieldset>

    {#if override}
      <h3 class="m-0 text-base font-semibold">Video</h3>
      <FormatPicker
        kind="video"
        rows={details.picker.video_streams}
        bind:selection={() => override.selection, (selection) => patch({ selection })}
      />
      <h3 class="m-0 text-base font-semibold">Audio</h3>
      <FormatPicker
        kind="audio"
        rows={details.picker.audio_streams}
        bind:selection={() => override.selection, (selection) => patch({ selection })}
      />
      <label class="flex items-center gap-2 text-base">
        <input
          type="checkbox"
          checked={override.subtitles}
          onchange={(e) => patch({ subtitles: e.currentTarget.checked })}
          class="size-4 accent-(--color-action)"
        >
        Subtitles
      </label>
      <div>
        <label for="ov-template" class="mb-1 block text-sm font-medium">Output template</label>
        <input
          id="ov-template"
          type="text"
          class={input}
          placeholder="%(title)s.%(ext)s"
          value={override.outputTemplate}
          oninput={(e) => patch({ outputTemplate: e.currentTarget.value })}
        >
      </div>
      <div>
        <label for="ov-bitrate" class="mb-1 block text-sm font-medium">Audio bitrate</label>
        <input
          id="ov-bitrate"
          type="text"
          class={input}
          placeholder="192K"
          value={override.audioBitrate}
          oninput={(e) => patch({ audioBitrate: e.currentTarget.value })}
        >
      </div>
    {:else}
      <p class="m-0 text-sm text-muted">
        This video follows the quality and options at the top of the list.
      </p>
    {/if}
  {/if}
</aside>
