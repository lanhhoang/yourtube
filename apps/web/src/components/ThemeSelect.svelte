<script lang="ts">
  import type { ThemeChoice } from "../lib/theme.ts";
  import { setTheme, themeState } from "../lib/theme-state.svelte.ts";

  let { label = "Theme" }: { label?: string } = $props();
  const id = $props.id();

  const CHOICES: { value: ThemeChoice; label: string }[] = [
    { value: "dark", label: "Dark" },
    { value: "light", label: "Light" },
    { value: "system", label: "System" },
  ];
</script>

<div role="radiogroup" aria-label={label} class="flex flex-col gap-1">
  {#each CHOICES as c (c.value)}
    <label
      class="grid min-h-[44px] cursor-pointer place-items-center rounded-control px-2 py-1 text-center text-xs md:block md:min-h-0 font-medium transition-colors duration-(--duration-fast) has-checked:bg-raised has-checked:text-fg has-focus-visible:outline-2 has-focus-visible:outline-offset-2 has-focus-visible:outline-fg text-muted hover:text-fg"
    >
      <input
        type="radio"
        name="theme-{id}"
        class="sr-only"
        value={c.value}
        checked={themeState.choice === c.value}
        onchange={() => setTheme(c.value)}
      >
      {c.label}
    </label>
  {/each}
</div>
