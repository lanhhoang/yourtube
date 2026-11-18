<script lang="ts">
  import type { components } from "../lib/api.gen.ts";
  import { type Selection, toggle } from "../lib/format-picker.ts";
  import { isHdr } from "../lib/quality.ts";

  type Row = components["schemas"]["StreamRow"];

  let {
    kind,
    rows,
    selection = $bindable(),
  }: { kind: "video" | "audio"; rows: Row[]; selection: Selection } = $props();

  const selectedId = $derived(kind === "video" ? selection.videoId : selection.audioId);

  function label(r: Row): string {
    if (kind === "audio") return r.abr ? `${Math.round(r.abr)} kbps` : "Audio";
    return r.resolution ?? (r.height ? `${r.height}p` : r.format_id);
  }

  function detail(r: Row): string {
    const codec = kind === "video" ? r.vcodec : r.acodec;
    return [codec?.split(".")[0], r.ext, kind === "video" && isHdr(r) ? "HDR" : null]
      .filter(Boolean)
      .join(" · ");
  }
</script>

{#if rows.length === 0}
  <p class="m-0 text-sm text-muted">No separate {kind} streams for this video.</p>
{:else}
  <ul class="m-0 flex list-none flex-col gap-1 p-0">
    {#each rows as r (r.format_id)}
      {@const on = selectedId === r.format_id}
      <li>
        <button
          type="button"
          aria-pressed={on}
          onclick={() => (selection = toggle(selection, kind, r.format_id))}
          class="flex w-full cursor-pointer items-center justify-between rounded-control border-0 px-3 py-2 text-left text-base text-fg transition-colors duration-(--duration-fast) hover:bg-raised {on
            ? "bg-raised"
            : "bg-transparent"}"
        >
          <span class="flex items-center gap-2">
            <span class="size-2 rounded-full {on ? "bg-accent" : "bg-transparent"}"></span>
            <span class="tabular font-semibold">{label(r)}</span>
          </span>
          <span class="text-sm text-muted">{detail(r)}</span>
        </button>
      </li>
    {/each}
  </ul>
{/if}
