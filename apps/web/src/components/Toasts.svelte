<script lang="ts">
  import type { Toast, ToastKind } from "../lib/toasts.ts";

  let { toasts, onclose }: { toasts: Toast[]; onclose: (key: string) => void } = $props();

  const LABEL: Record<ToastKind, string> = {
    done: "Downloaded",
    failed: "Download failed",
    batch: "Batch finished",
    deleted: "Bulk delete",
  };
</script>

<div
  aria-live="polite"
  class="fixed inset-x-4 top-[calc(env(safe-area-inset-top)+4rem)] z-20 flex flex-col gap-2 md:inset-x-auto md:top-auto md:right-6 md:bottom-6 md:w-80"
>
  {#each toasts as t (t.key)}
    <div
      class="flex items-start gap-3 rounded-control border border-line-strong bg-raised p-3 shadow-[0_8px_24px_rgb(0_0_0/0.4)]"
    >
      <div class="min-w-0 flex-1">
        <p
          class="m-0 flex items-center gap-1.5 text-sm {t.kind === "failed"
            ? "text-danger"
            : "text-muted"}"
        >
          <svg
            aria-hidden="true"
            viewBox="0 0 24 24"
            class="size-4 shrink-0"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            {#if t.kind === "failed"}
              <circle cx="12" cy="12" r="9" />
              <path d="M12 7v6M12 16.5v.01" />
            {:else if t.kind === "batch"}
              <path d="M4 7l8-4 8 4-8 4zM4 12l8 4 8-4M4 17l8 4 8-4" />
            {:else if t.kind === "deleted"}
              <path d="M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13M10 11v5M14 11v5" />
            {:else}
              <path d="M5 12l5 5L20 7" />
            {/if}
          </svg>
          {LABEL[t.kind]}
        </p>
        <p class="m-0 truncate text-base font-semibold">
          {t.kind === "batch" ? t.title : t.body}
        </p>
        {#if t.kind === "batch"}
          <p class="m-0 truncate text-sm text-muted">{t.body}</p>
        {/if}
      </div>
      <button
        type="button"
        aria-label="Close"
        class="grid size-[44px] shrink-0 md:size-6 cursor-pointer place-items-center rounded-control border-0 bg-transparent text-muted transition-colors duration-(--duration-fast) hover:text-fg"
        onclick={() => onclose(t.key)}
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
