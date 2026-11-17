<script lang="ts">
  import { CAP_OPTIONS, type QualityCap } from "../lib/quality.ts";

  let { value = $bindable(), dimmed = false }: { value: QualityCap; dimmed?: boolean } = $props();
</script>

<div
  class="flex flex-col gap-1 transition-opacity duration-(--duration-fast) {dimmed
    ? "opacity-50"
    : ""}"
>
  <label for="quality" class="text-sm font-medium">Quality</label>
  <select
    id="quality"
    bind:value
    class="w-full cursor-pointer rounded-control border border-line-strong bg-surface px-3 py-2 text-base text-fg"
  >
    {#each CAP_OPTIONS as o (o.value)}
      <option value={o.value}>{o.label}</option>
    {/each}
  </select>
  {#if dimmed}
    <p class="m-0 text-sm text-muted">Exact format overrides this</p>
  {/if}
</div>
