<script lang="ts">
  import { activeFilterCount, DEFAULT_VIEW, type Facet, type LibraryView } from "../lib/library.ts";

  let {
    view = $bindable(),
    channels,
    playlists,
  }: { view: LibraryView; channels: Facet[]; playlists: Facet[] } = $props();

  const id = $props.id();
  const KINDS: { value: LibraryView["kind"]; label: string }[] = [
    { value: "any", label: "Any" },
    { value: "video", label: "Video" },
    { value: "audio", label: "Audio" },
  ];
  const field =
    "w-full cursor-pointer rounded-control border border-line-strong bg-surface min-h-[44px] px-3 py-2 text-[16px] text-fg md:min-h-0 md:text-base";
</script>

<div class="flex flex-col gap-4 md:w-64">
  <div class="flex flex-col gap-1">
    <span id="{id}-type" class="text-sm font-medium">Type</span>
    <div role="radiogroup" aria-labelledby="{id}-type" class="flex gap-1">
      {#each KINDS as k (k.value)}
        <label
          class="grid min-h-[44px] min-w-[44px] flex-1 cursor-pointer place-items-center rounded-control bg-raised px-3 py-1 text-sm font-medium text-fg transition-colors duration-(--duration-fast) has-checked:bg-action has-checked:text-on-action has-focus-visible:outline-2 has-focus-visible:outline-offset-2 has-focus-visible:outline-fg md:min-h-9"
        >
          <input
            type="radio"
            name="kind-{id}"
            class="sr-only"
            value={k.value}
            checked={view.kind === k.value}
            onchange={() => (view = { ...view, kind: k.value })}
          >
          {k.label}
        </label>
      {/each}
    </div>
  </div>
  <div class="flex flex-col gap-1">
    <label for="{id}-channel" class="text-sm font-medium">Channel</label>
    <select
      id="{id}-channel"
      class={field}
      value={view.channel ?? ""}
      onchange={(e) => (view = { ...view, channel: e.currentTarget.value || null })}
    >
      <option value="">Any channel</option>
      {#each channels as c (c.value)}
        <option value={c.value}>{c.value} ({c.count})</option>
      {/each}
    </select>
  </div>
  {#if playlists.length > 0}
    <div class="flex flex-col gap-1">
      <label for="{id}-playlist" class="text-sm font-medium">Playlist</label>
      <select
        id="{id}-playlist"
        class={field}
        value={view.playlist ?? ""}
        onchange={(e) => (view = { ...view, playlist: e.currentTarget.value || null })}
      >
        <option value="">Any playlist</option>
        {#each playlists as p (p.value)}
          <option value={p.value}>{p.value} ({p.count})</option>
        {/each}
      </select>
    </div>
  {/if}
  <button
    type="button"
    class="min-h-[44px] cursor-pointer self-start rounded-pill border border-line-strong bg-transparent px-5 py-1 text-sm font-medium text-fg hover:bg-raised disabled:cursor-default disabled:opacity-50 md:min-h-9"
    disabled={activeFilterCount(view) === 0}
    onclick={() => (view = { ...view, kind: DEFAULT_VIEW.kind, channel: null, playlist: null })}
  >
    Clear filters
  </button>
</div>
