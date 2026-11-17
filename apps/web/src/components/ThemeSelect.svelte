<script module lang="ts">
  import { currentTheme, type ThemeChoice } from "../lib/theme.ts";

  // Shared by every copy on the page so the rail and Settings always agree.
  let choice = $state<ThemeChoice>(currentTheme());
</script>

<script lang="ts">
  import { applyTheme } from "../lib/theme.ts";

  let { label = "Theme" }: { label?: string } = $props();
  const id = $props.id();

  const CHOICES: { value: ThemeChoice; label: string }[] = [
    { value: "dark", label: "Dark" },
    { value: "light", label: "Light" },
    { value: "system", label: "System" },
  ];

  function pick(value: ThemeChoice) {
    choice = value;
    applyTheme(value);
  }
</script>

<div role="radiogroup" aria-label={label} class="flex flex-col gap-1">
  {#each CHOICES as c (c.value)}
    <label
      class="cursor-pointer rounded-control px-2 py-1 text-center text-xs font-medium transition-colors duration-(--duration-fast) has-checked:bg-raised has-checked:text-fg has-focus-visible:outline-2 has-focus-visible:outline-offset-2 has-focus-visible:outline-fg text-muted hover:text-fg"
    >
      <input
        type="radio"
        name="theme-{id}"
        class="sr-only"
        value={c.value}
        checked={choice === c.value}
        onchange={() => pick(c.value)}
      >
      {c.label}
    </label>
  {/each}
</div>
