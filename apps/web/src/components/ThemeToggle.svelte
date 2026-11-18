<script lang="ts">
  import { nextTheme, themeLabel } from "../lib/theme.ts";
  import { setTheme, themeState } from "../lib/theme-state.svelte.ts";

  const label = $derived(themeLabel(themeState.choice));
</script>

<button
  type="button"
  aria-label={label}
  title={label}
  onclick={() => setTheme(nextTheme(themeState.choice))}
  class="group flex w-16 cursor-pointer flex-col items-center rounded-control border-0 bg-transparent py-2.5 text-muted transition-colors duration-(--duration-fast) hover:text-fg focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-fg"
>
  <span class="grid size-7 place-items-center rounded-control bg-raised" aria-hidden="true">
    <svg
      aria-hidden="true"
      viewBox="0 0 24 24"
      class="size-4"
      fill="none"
      stroke="currentColor"
      stroke-width="2"
      stroke-linecap="round"
      stroke-linejoin="round"
    >
      {#if themeState.choice === "dark"}
        <path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z" />
      {:else if themeState.choice === "light"}
        <circle cx="12" cy="12" r="4" />
        <path
          d="M12 2v2M12 20v2M2 12h2M20 12h2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"
        />
      {:else}
        <rect x="3" y="4" width="18" height="12" rx="2" />
        <path d="M8 20h8M12 16v4" />
      {/if}
    </svg>
  </span>
</button>
