<script lang="ts">
  import { href, type Section } from "../lib/router.ts";
  import ThemeToggle from "./ThemeToggle.svelte";

  let { active, queueCount = 0 }: { active: Section; queueCount?: number } = $props();

  const LINKS = [
    { section: "library", label: "Library", route: { name: "library" } },
    { section: "queue", label: "Queue", route: { name: "queue" } },
    { section: "settings", label: "Settings", route: { name: "settings" } },
  ] as const;
</script>

<nav
  aria-label="Main"
  class="hidden h-full w-[72px] shrink-0 flex-col justify-between py-2 md:flex"
>
  <ul class="m-0 flex list-none flex-col items-center gap-3 p-0">
    {#each LINKS as l (l.section)}
      <li>
        <a
          href={href(l.route)}
          aria-current={active === l.section ? "page" : undefined}
          class="group relative flex w-16 flex-col items-center gap-1 rounded-control py-1.5 text-xs font-medium text-muted no-underline transition-colors duration-(--duration-fast) hover:text-fg aria-[current=page]:text-fg"
        >
          <span
            class="grid size-7 place-items-center rounded-control bg-raised transition-colors duration-(--duration-fast) group-aria-[current=page]:bg-action group-aria-[current=page]:text-on-action"
            aria-hidden="true"
          >
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
              {#if l.section === "library"}
                <rect x="3" y="3" width="7" height="7" rx="1" />
                <rect x="14" y="3" width="7" height="7" rx="1" />
                <rect x="3" y="14" width="7" height="7" rx="1" />
                <rect x="14" y="14" width="7" height="7" rx="1" />
              {:else if l.section === "queue"}
                <path d="M4 6h16M4 12h16M4 18h10" />
              {:else}
                <circle cx="12" cy="12" r="3" />
                <path
                  d="M12 2v3M12 19v3M2 12h3M19 12h3M4.9 4.9l2.1 2.1M17 17l2.1 2.1M4.9 19.1 7 17M17 7l2.1-2.1"
                />
              {/if}
            </svg>
          </span>
          {#if l.section === "queue" && queueCount > 0}
            <span
              class="tabular absolute top-0 right-1 min-w-4 rounded-pill bg-accent-fill px-1 text-center text-[11px] leading-4 font-semibold text-on-accent"
              >{queueCount}<span class="sr-only"> in queue</span></span
            >
          {/if}
          {l.label}
        </a>
      </li>
    {/each}
  </ul>
  <div class="flex justify-center"><ThemeToggle /></div>
</nav>
