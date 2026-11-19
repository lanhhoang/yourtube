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

<div
  role="radiogroup"
  aria-label="Filter"
  class="-mx-4 flex gap-2 overflow-x-auto px-4 md:mx-0 md:overflow-visible md:px-0"
>
  {#each CHIPS as c (c.value)}
    <label
      class="grid min-h-[44px] shrink-0 cursor-pointer place-items-center rounded-control bg-raised px-3 py-1.5 text-sm md:block md:min-h-0 font-medium text-fg transition-colors duration-(--duration-fast) hover:bg-line has-checked:bg-action has-checked:text-on-action has-focus-visible:outline-2 has-focus-visible:outline-offset-2 has-focus-visible:outline-fg"
    >
      <input type="radio" name="chip" class="sr-only" value={c.value} bind:group={value}>
      {c.label}
    </label>
  {/each}
</div>
