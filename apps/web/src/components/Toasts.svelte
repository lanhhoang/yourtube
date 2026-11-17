<script lang="ts">
  export type Toast = { id: number; title: string };

  let { toasts, onclose }: { toasts: Toast[]; onclose: (id: number) => void } = $props();
</script>

<div aria-live="polite" class="fixed right-6 bottom-6 z-20 flex w-80 flex-col gap-2">
  {#each toasts as t (t.id)}
    <div
      class="flex items-start gap-3 rounded-control border border-line-strong bg-raised p-3 shadow-[0_8px_24px_rgb(0_0_0/0.4)]"
    >
      <div class="min-w-0 flex-1">
        <p class="m-0 text-sm text-muted">Downloaded</p>
        <p class="m-0 truncate text-base font-semibold">{t.title}</p>
      </div>
      <button
        type="button"
        aria-label="Close"
        class="grid size-6 shrink-0 cursor-pointer place-items-center rounded-control border-0 bg-transparent text-muted transition-colors duration-(--duration-fast) hover:text-fg"
        onclick={() => onclose(t.id)}
      >
        <svg
          aria-hidden="true"
          viewBox="0 0 24 24"
          class="size-4"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
          stroke-linecap="round"
        >
          <path d="M6 6l12 12M18 6L6 18" />
        </svg>
      </button>
    </div>
  {/each}
</div>
