<script lang="ts">
  import { badgeFor } from "../lib/badges.ts";
  import { formatDuration } from "../lib/duration.ts";
  import { type EntryState, isUnavailable } from "../lib/playlist.ts";
  import type { QualityCap } from "../lib/quality.ts";

  let {
    item,
    cap,
    active = false,
    ontoggle,
    onopen,
  }: {
    item: EntryState;
    cap: QualityCap;
    active?: boolean;
    ontoggle: (selected: boolean) => void;
    onopen: () => void;
  } = $props();

  let showMessage = $state(false);

  const details = $derived(
    typeof item.check === "object" && item.check.ok ? item.check.details : null,
  );
  const title = $derived(item.entry.title ?? details?.title ?? item.entry.url);
  const thumbnail = $derived(item.entry.thumbnail ?? details?.thumbnail ?? null);
  const duration = $derived(item.entry.duration ?? details?.duration ?? null);
  const badge = $derived(badgeFor(item, cap));
  const unavailable = $derived(isUnavailable(item));

  function open() {
    if (unavailable) showMessage = !showMessage;
    else onopen();
  }

  const tone = {
    below: "bg-raised text-warn",
    custom: "bg-accent-fill text-on-accent",
    unavailable: "bg-raised text-danger",
  } as const;
</script>

<article class="relative flex min-w-0 flex-col gap-2 {unavailable ? "opacity-70" : ""}">
  <button
    type="button"
    onclick={open}
    aria-label={unavailable ? `${title}: show why it is unavailable` : `${title}: customise`}
    class="flex w-full cursor-pointer flex-col gap-2 rounded-control border-0 bg-transparent p-0 text-left text-fg {active
      ? "outline-2 outline-offset-2 outline-fg"
      : ""}"
  >
    <span class="relative block aspect-video w-full overflow-hidden rounded-thumb bg-surface">
      {#if thumbnail}
        <img src={thumbnail} alt="" loading="lazy" class="size-full object-cover">
      {/if}
      {#if duration !== null}
        <span
          class="tabular absolute right-2 bottom-2 rounded-control bg-black/80 px-1.5 py-0.5 text-xs font-medium text-white"
        >
          {formatDuration(duration)}
        </span>
      {/if}
    </span>
    <span class="line-clamp-2 text-base font-semibold">{title}</span>
  </button>

  <span
    class="absolute top-2 left-2 grid size-6 cursor-pointer place-items-center rounded-control bg-black/60"
  >
    <input
      type="checkbox"
      checked={item.selected}
      disabled={unavailable}
      aria-label="Select {title}"
      onchange={(e) => ontoggle(e.currentTarget.checked)}
      class="size-4 accent-(--color-action)"
    >
  </span>

  <div class="flex min-h-5 items-center gap-2">
    {#if item.check === "checking"}
      <span
        role="status"
        aria-label="Checking"
        class="size-4 animate-spin rounded-full border-2 border-line-strong border-t-fg motion-reduce:animate-none"
      ></span>
    {/if}
    {#if badge}
      <span
        class="rounded-control px-2 py-0.5 text-xs font-medium {tone[badge.kind]}"
        title={badge.kind === "unavailable" ? badge.message : undefined}
      >
        {badge.label}
      </span>
    {/if}
  </div>
  {#if showMessage && badge?.kind === "unavailable"}
    <p class="m-0 text-sm text-danger" role="status">{badge.message}</p>
  {/if}
</article>
