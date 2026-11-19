<script lang="ts">
  import { href, type Section } from "../lib/router.ts";

  let { active, queueCount = 0 }: { active: Section; queueCount?: number } = $props();

  const LINKS = [
    { section: "library", label: "Library", route: { name: "library" } },
    { section: "queue", label: "Queue", route: { name: "queue" } },
    { section: "settings", label: "Settings", route: { name: "settings" } },
  ] as const;
</script>

<nav
  aria-label="Tabs"
  class="flex shrink-0 border-t border-line bg-bg pb-[env(safe-area-inset-bottom)] md:hidden"
>
  {#each LINKS as l (l.section)}
    <a
      href={href(l.route)}
      aria-current={active === l.section ? "page" : undefined}
      class="flex min-h-[56px] flex-1 flex-col items-center justify-center gap-0.5 text-xs font-medium text-muted no-underline aria-[current=page]:font-semibold aria-[current=page]:text-fg"
    >
      <span class="relative grid">
        <svg
          aria-hidden="true"
          viewBox="0 0 24 24"
          class="size-5.5"
          fill="none"
          stroke="currentColor"
          stroke-width="1.8"
          stroke-linecap="round"
          stroke-linejoin="round"
        >
          {#if l.section === "library"}
            <rect x="3" y="5" width="18" height="14" rx="2" />
            <path d="M10 9.5l5 2.5-5 2.5z" />
          {:else if l.section === "queue"}
            <path d="M12 4v11m0 0l-4-4m4 4l4-4M5 20h14" />
          {:else}
            <circle cx="12" cy="12" r="3" />
            <path
              d="M12 3v3M12 18v3M3 12h3M18 12h3M5.6 5.6l2.1 2.1M16.3 16.3l2.1 2.1M18.4 5.6l-2.1 2.1M7.7 16.3l-2.1 2.1"
            />
          {/if}
        </svg>
        {#if l.section === "queue" && queueCount > 0}
          <span
            class="tabular absolute -top-1.5 left-3.5 min-w-4.5 rounded-pill bg-accent-fill px-1 text-center text-[11px] leading-[18px] font-bold text-on-accent"
            >{queueCount}<span class="sr-only"> in queue</span></span
          >
        {/if}
      </span>
      {l.label}
    </a>
  {/each}
</nav>
