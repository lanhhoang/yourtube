<script lang="ts">
  import type { Snippet } from "svelte";

  let {
    open,
    title,
    onclose,
    children,
  }: { open: boolean; title: string; onclose: () => void; children: Snippet } = $props();

  const titleId = $props.id();
  let el = $state<HTMLDialogElement>();

  // showModal() gives the focus trap and inert background; closing returns focus to the opener.
  $effect(() => {
    if (!open || !el) return;
    const dialog = el;
    const opener = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    dialog.showModal();
    return () => {
      dialog.close();
      opener?.focus();
    };
  });
</script>

{#if open}
  <!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_noninteractive_element_interactions -->
  <!-- biome-ignore lint/a11y/useKeyWithClickEvents: Escape and the Close button cover keyboards -->
  <dialog
    bind:this={el}
    aria-labelledby={titleId}
    oncancel={(e) => {
      e.preventDefault();
      onclose();
    }}
    onclick={(e) => {
      if (e.target === el) onclose();
    }}
    class="m-0 mt-auto max-h-[85dvh] w-full max-w-none overflow-y-auto rounded-t-control border-0 bg-surface p-4 pb-[calc(1rem+env(safe-area-inset-bottom))] text-fg backdrop:bg-black/60"
  >
    <div class="mb-3 flex items-start justify-between gap-3">
      <h2 id={titleId} class="m-0 line-clamp-2 text-lg font-semibold">{title}</h2>
      <button
        type="button"
        onclick={onclose}
        class="min-h-[44px] min-w-[44px] cursor-pointer rounded-pill border-0 bg-raised px-4 text-sm font-medium text-fg"
      >
        Close
      </button>
    </div>
    {@render children()}
  </dialog>
{/if}
