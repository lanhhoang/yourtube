<script lang="ts">
  import type { Chip } from "../lib/library.ts";

  let { value = $bindable() }: { value: Chip } = $props();

  const CHIPS: { value: Chip; label: string }[] = [
    { value: "all", label: "All" },
    { value: "downloading", label: "Downloading" },
    { value: "video", label: "Video" },
    { value: "audio", label: "Audio only" },
  ];
</script>

<div role="radiogroup" aria-label="Filter" class="flex gap-2">
  {#each CHIPS as c (c.value)}
    <label
      class="cursor-pointer rounded-control bg-raised px-3 py-1.5 text-sm font-medium text-fg transition-colors duration-(--duration-fast) hover:bg-line has-checked:bg-action has-checked:text-on-action has-focus-visible:outline-2 has-focus-visible:outline-offset-2 has-focus-visible:outline-fg"
    >
      <input type="radio" name="chip" class="sr-only" value={c.value} bind:group={value}>
      {c.label}
    </label>
  {/each}
</div>
