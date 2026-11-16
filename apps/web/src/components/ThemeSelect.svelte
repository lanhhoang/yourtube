<script lang="ts">
  import { applyTheme, currentTheme, type ThemeChoice } from "../lib/theme.ts";

  const CHOICES: { value: ThemeChoice; label: string }[] = [
    { value: "dark", label: "Dark" },
    { value: "light", label: "Light" },
    { value: "system", label: "System" },
  ];

  let choice = $state<ThemeChoice>(currentTheme());

  function pick(value: ThemeChoice) {
    choice = value;
    applyTheme(value);
  }
</script>

<div role="radiogroup" aria-label="Theme" class="flex flex-col gap-1">
  {#each CHOICES as c (c.value)}
    <label
      class="cursor-pointer rounded-control px-2 py-1 text-center text-xs font-medium transition-colors duration-(--duration-fast) has-checked:bg-raised has-checked:text-fg has-focus-visible:outline-2 has-focus-visible:outline-offset-2 has-focus-visible:outline-fg text-muted hover:text-fg"
    >
      <input
        type="radio"
        name="theme"
        class="sr-only"
        value={c.value}
        checked={choice === c.value}
        onchange={() => pick(c.value)}
      >
      {c.label}
    </label>
  {/each}
</div>
