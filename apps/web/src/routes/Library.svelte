<script lang="ts">
  import { untrack } from "svelte";
  import { MediaQuery } from "svelte/reactivity";
  import BottomSheet from "../components/BottomSheet.svelte";
  import JobCard from "../components/JobCard.svelte";
  import LibraryFilters from "../components/LibraryFilters.svelte";
  import { api, call } from "../lib/api.ts";
  import { messageFor } from "../lib/errors.ts";
  import { latest } from "../lib/latest.ts";
  import {
    activeFilterCount,
    bulkResultText,
    dropStale,
    type Facets,
    facets,
    filterItems,
    readView,
    SORT_OPTIONS,
    sameFilters,
    saveView,
    sortItems,
    toggle,
    VIEW_KEY,
  } from "../lib/library.ts";
  import type { Toast } from "../lib/toasts.ts";
  import { type JobOut, leftActive, newlyCompleted, type QueueOut } from "../lib/queue.ts";

  let { queue, ontoast }: { queue: QueueOut | null; ontoast: (t: Omit<Toast, "key">) => void } =
    $props();

  let q = $state("");
  let done = $state<JobOut[]>([]);
  // Facets of the unsearched list: a channel a search hides is not stale.
  let fullFacets = $state<Facets | null>(null);
  // Size of the unsearched list: gates the toolbar so an empty search keeps it.
  let total = $state(0);
  // Never mutate in place: readView can hand back the shared DEFAULT_VIEW.
  let view = $state(readView(localStorage.getItem(VIEW_KEY)));
  const wide = new MediaQuery("(min-width: 768px)");
  let loaded = $state(false);
  let error = $state("");
  const ticket = latest();

  async function load(query: string): Promise<void> {
    const current = ticket();
    try {
      const rows = await call(
        api.GET("/api/library", { params: { query: query.trim() ? { q: query } : {} } }),
      );
      if (!current()) return;
      done = rows;
      if (!query.trim()) {
        fullFacets = facets(rows);
        total = rows.length;
      }
      error = "";
    } catch (err) {
      if (!current()) return;
      error = messageFor(err);
    }
    loaded = true;
  }

  // Debounced search; the first run is immediate.
  let first = true;
  $effect(() => {
    const query = q;
    const delay = first ? 0 : 250;
    first = false;
    const id = setTimeout(() => void load(query), delay);
    return () => clearTimeout(id);
  });

  // Reload when a job leaves the active list, or when a new id shows up in `completed`
  // (a job that ran entirely between two polls never appears as active).
  let prevActive: JobOut[] = [];
  let prevCompleted: JobOut[] | null = null;
  $effect(() => {
    const active = queue?.active ?? [];
    const completed = queue?.completed ?? null;
    const finished =
      leftActive(prevActive, active) ||
      (prevCompleted !== null && completed !== null && newlyCompleted(prevCompleted, completed));
    if (finished) untrack(() => void load(q));
    prevActive = active;
    if (completed !== null) prevCompleted = completed;
  });

  const searching = $derived(q.trim() !== "");
  const items = $derived(sortItems(filterItems(done, view), view.sort));
  const filterCount = $derived(activeFilterCount(view));

  $effect(() => {
    saveView(view);
  });

  $effect(() => {
    if (!fullFacets) return;
    const next = dropStale(
      untrack(() => view),
      fullFacets,
    );
    if (next !== untrack(() => view)) view = next;
  });

  function removed(id: number) {
    done = done.filter((j) => j.id !== id);
    if (!searching) {
      fullFacets = facets(done);
      total = done.length;
    }
  }

  let filtersOpen = $state(false);
  let filterBtn = $state<HTMLButtonElement>();
  let popover = $state<HTMLDivElement>();

  function closeFilters(refocus = true) {
    filtersOpen = false;
    if (refocus) filterBtn?.focus();
  }

  function toggleFilters() {
    if (filtersOpen) closeFilters();
    else filtersOpen = true;
  }

  $effect(() => {
    if (!filtersOpen || !wide.current || !popover) return;
    popover.querySelector<HTMLElement>("input:checked, select, button")?.focus();
  });

  $effect(() => {
    if (!filtersOpen || !wide.current) return;
    const onDown = (e: PointerEvent) => {
      const t = e.target as Node;
      if (!popover?.contains(t) && !filterBtn?.contains(t)) closeFilters(false);
    };
    window.addEventListener("pointerdown", onDown);
    return () => window.removeEventListener("pointerdown", onDown);
  });

  let selecting = $state(false);
  let selected = $state(new Set<number>());
  let confirming = $state(false);
  let deleting = $state(false);
  let bulkError = $state("");
  let confirmTimer: ReturnType<typeof setTimeout> | undefined;

  // Rows can vanish on a reload, so only ids still in `done` count.
  const doneIds = $derived(new Set(done.map((j) => j.id)));
  const picked = $derived([...selected].filter((id) => doneIds.has(id)));
  const visibleDone = $derived(items.map((j) => j.id));
  const allPicked = $derived(visibleDone.length > 0 && visibleDone.every((id) => selected.has(id)));

  function resetConfirm() {
    clearTimeout(confirmTimer);
    confirming = false;
  }

  function endSelecting() {
    selecting = false;
    selected = new Set();
    bulkError = "";
    resetConfirm();
  }

  $effect(() => {
    void q;
    untrack(() => {
      selected = new Set();
    });
  });

  let seenView = untrack(() => view);
  $effect(() => {
    const now = view;
    if (sameFilters(seenView, now)) {
      seenView = now;
      return;
    }
    seenView = now;
    untrack(() => {
      selected = new Set();
    });
  });

  // Any change to the selection cancels a pending "Delete n?".
  $effect(() => {
    void selected;
    untrack(resetConfirm);
  });

  function toggleSelecting() {
    if (selecting) endSelecting();
    else selecting = true;
  }

  function onKey(e: KeyboardEvent) {
    if (e.key !== "Escape") return;
    if (filtersOpen) {
      if (wide.current) closeFilters();
      return;
    }
    if (selecting) endSelecting();
  }

  function pick(id: number) {
    selected = toggle(selected, id);
  }

  function selectAll() {
    selected = allPicked ? new Set() : new Set(visibleDone);
  }

  async function bulkDelete() {
    if (!confirming) {
      confirming = true;
      bulkError = "";
      confirmTimer = setTimeout(resetConfirm, 4000);
      return;
    }
    if (deleting) return;
    deleting = true;
    resetConfirm();
    const gone = new Set<number>();
    let failed = 0;
    let ok = false;
    try {
      const ids = [...picked];
      for (let i = 0; i < ids.length; i += 500) {
        const res = await call(
          api.POST("/api/library/delete", { body: { ids: ids.slice(i, i + 500) } }),
        );
        for (const id of res.deleted) gone.add(id);
        failed += res.failed.length;
      }
      ok = true;
    } catch (err) {
      bulkError = messageFor(err);
    }
    try {
      if (gone.size > 0) {
        done = done.filter((j) => !gone.has(j.id));
        selected = new Set([...selected].filter((id) => !gone.has(id)));
      }
      if (ok) {
        ontoast({
          kind: "deleted",
          title: "",
          body: bulkResultText(gone.size, failed),
        });
        if (picked.length === 0) endSelecting();
      }
      // Moves the ticket on (drops stale loads) and drops rows that were already gone.
      void load(q);
      if (!searching) {
        fullFacets = facets(done);
        total = done.length;
      }
    } finally {
      deleting = false;
    }
  }
</script>

<svelte:window onkeydown={onKey} />

<div class="flex min-h-full flex-col">
  <div class="flex flex-wrap items-center gap-x-4 gap-y-3">
    <h1 class="m-0 text-xl font-bold tracking-[-0.01em]">Library</h1>
    <input
      type="search"
      bind:value={q}
      aria-label="Search library"
      placeholder="Search title or uploader"
      class="min-h-[44px] w-full rounded-pill border border-line-strong bg-surface px-4 py-1.5 text-[16px] text-fg placeholder:text-muted md:ml-auto md:min-h-0 md:w-72 md:text-base"
    >
    <div class="flex w-full items-center gap-2 md:w-auto md:gap-4">
      {#if total > 0}
        <label for="library-sort" class="sr-only">Sort</label>
        <select
          id="library-sort"
          value={view.sort}
          onchange={(e) => (view = { ...view, sort: e.currentTarget.value as typeof view.sort })}
          class="min-h-[44px] min-w-0 flex-1 cursor-pointer rounded-control border border-line-strong bg-surface px-3 py-1 text-[16px] text-fg md:min-h-0 md:flex-none md:text-base"
        >
          {#each SORT_OPTIONS as o (o.value)}
            <option value={o.value}>{o.label}</option>
          {/each}
        </select>
        <div class="relative">
          <button
            type="button"
            bind:this={filterBtn}
            aria-expanded={filtersOpen}
            aria-haspopup="dialog"
            class="min-h-[44px] cursor-pointer rounded-pill border border-line-strong bg-transparent px-5 py-1 text-[16px] font-medium whitespace-nowrap text-fg hover:bg-raised md:min-h-0 md:text-sm"
            onclick={toggleFilters}
          >
            {filterCount > 0 ? `Filter · ${filterCount}` : "Filter"}
          </button>
          {#if filtersOpen && wide.current}
            <div
              bind:this={popover}
              role="dialog"
              aria-label="Filters"
              class="absolute top-[calc(100%+8px)] right-0 z-20 rounded-control transition-[opacity,translate] duration-(--duration-fast) ease-(--ease-out) starting:-translate-y-1 starting:opacity-0 border border-line-strong bg-surface p-4 shadow-[0_8px_24px_rgb(0_0_0/0.4)]"
            >
              <LibraryFilters
                bind:view
                channels={fullFacets?.channels ?? []}
                playlists={fullFacets?.playlists ?? []}
              />
            </div>
          {/if}
        </div>
      {/if}
      {#if total > 0 || selecting}
        <button
          type="button"
          class="min-h-[44px] cursor-pointer rounded-pill border border-line-strong bg-transparent px-5 py-1 text-[16px] font-medium text-fg hover:bg-raised md:min-h-0 md:text-sm"
          onclick={toggleSelecting}
        >
          {selecting ? "Done" : "Select"}
        </button>
      {/if}
    </div>
  </div>

  {#if !wide.current}
    <BottomSheet open={filtersOpen} title="Filters" onclose={() => closeFilters(false)}>
      <LibraryFilters
        bind:view
        channels={fullFacets?.channels ?? []}
        playlists={fullFacets?.playlists ?? []}
      />
    </BottomSheet>
  {/if}

  {#if filterCount > 0}
    {@const pill =
      "inline-flex items-center gap-1 rounded-pill border border-line-strong py-1 pr-1 pl-3 text-sm text-fg"}
    {@const pills = [
      ...(view.kind !== "any"
        ? [
            {
              text: view.kind === "audio" ? "Audio" : "Video",
              clear: () => (view = { ...view, kind: "any" as const }),
            },
          ]
        : []),
      ...(view.channel
        ? [{ text: `Channel: ${view.channel}`, clear: () => (view = { ...view, channel: null }) }]
        : []),
      ...(view.playlist
        ? [
            {
              text: `Playlist: ${view.playlist}`,
              clear: () => (view = { ...view, playlist: null }),
            },
          ]
        : []),
    ]}
    <div class="mt-3 flex flex-wrap items-center gap-2">
      {#each pills as p (p.text)}
        <span class={pill}>
          <span>{p.text}</span>
          <button
            type="button"
            aria-label="Remove filter {p.text}"
            class="grid size-[44px] cursor-pointer place-items-center rounded-pill border-0 bg-transparent text-fg hover:bg-raised md:size-6"
            onclick={p.clear}
          >
            <span aria-hidden="true">✕</span>
          </button>
        </span>
      {/each}
      <button
        type="button"
        class="min-h-[44px] cursor-pointer rounded-pill border-0 bg-transparent px-3 py-1 text-sm text-muted underline hover:text-fg md:min-h-0"
        onclick={() => (view = { ...view, kind: "any", channel: null, playlist: null })}
      >
        Clear filters
      </button>
    </div>
  {/if}

  {#if error}
    <p class="mt-6 text-danger">
      {error}
      <button
        type="button"
        class="ml-2 cursor-pointer rounded-pill border border-line-strong bg-transparent px-3 py-1 text-sm text-fg hover:bg-raised"
        onclick={() => load(q)}
      >
        Try again
      </button>
    </p>
  {:else if loaded}
    {#if items.length === 0}
      <p class="mt-6 text-muted">
        {#if searching && done.length === 0}
          Nothing matches “{q.trim()}”.
        {:else if done.length === 0}
          No downloads yet. Paste a URL above.
        {:else}
          No videos match these filters.
        {/if}
      </p>
      {#if done.length > 0}
        <button
          type="button"
          class="mt-3 min-h-[44px] cursor-pointer rounded-pill border border-line-strong bg-transparent px-5 py-1 text-sm font-medium text-fg hover:bg-raised md:min-h-9"
          onclick={() => (view = { ...view, kind: "any", channel: null, playlist: null })}
        >
          Clear filters
        </button>
      {/if}
    {:else}
      <div
        class="mt-4 flex flex-col gap-3 md:mt-6 md:grid md:grid-cols-[repeat(auto-fill,minmax(240px,1fr))] md:gap-x-4 md:gap-y-6"
      >
        {#each items as job (job.id)}
          <JobCard
            {job}
            ondeleted={removed}
            {selecting}
            selected={selected.has(job.id)}
            ontoggle={pick}
          />
        {/each}
      </div>
    {/if}
  {/if}

  {#if selecting}
    {@const barButton =
      "min-h-[44px] cursor-pointer rounded-pill border border-line-strong bg-transparent px-5 py-1 text-sm font-medium text-fg hover:bg-raised disabled:opacity-50 md:min-h-9"}
    <!-- biome-ignore lint/a11y/useSemanticElements: the spec asks for a labelled region div -->
    <div
      role="region"
      aria-label="Selection"
      class="sticky -bottom-4 z-10 mt-auto -mx-4 -mb-4 md:-bottom-6 md:-mx-6 md:-mb-6 flex flex-wrap items-center gap-3 border-t border-line bg-surface p-3"
    >
      <span class="tabular text-sm" aria-live="polite">{picked.length} selected</span>
      <button
        type="button"
        class={barButton}
        disabled={visibleDone.length === 0}
        onclick={selectAll}
      >
        {allPicked ? "Clear" : "Select all"}
      </button>
      <button
        type="button"
        class="{barButton} ml-auto"
        disabled={picked.length === 0 || deleting}
        onclick={bulkDelete}
        onblur={resetConfirm}
      >
        {confirming ? `Delete ${picked.length}?` : "Delete"}
      </button>
      {#if bulkError}
        <p role="alert" class="m-0 w-full text-sm text-danger">{bulkError}</p>
      {/if}
    </div>
  {/if}
</div>
