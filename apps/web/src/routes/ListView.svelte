<script lang="ts">
  import EntryCard from "../components/EntryCard.svelte";
  import OverridePanel from "../components/OverridePanel.svelte";
  import QualitySelect from "../components/QualitySelect.svelte";
  import { api, call } from "../lib/api.ts";
  import { createChecker } from "../lib/checker.ts";
  import { messageFor } from "../lib/errors.ts";
  import { FETCH_OPTIONS_KEY, readFetchOptions } from "../lib/fetch-options.ts";
  import {
    addState,
    applyResult,
    buildJobs,
    type Header,
    initialEntries,
    type Override,
    selectAll,
    setOverride,
    setSelected,
    type SourcesResult,
  } from "../lib/playlist.ts";
  import { DEFAULT_CAP, type QualityCap } from "../lib/quality.ts";

  let { result }: { result: SourcesResult } = $props();

  // One list per mount; Fetch remounts this component for each new result.
  // svelte-ignore state_referenced_locally
  let entries = $state(initialEntries(result));
  let cap = $state<QualityCap>(DEFAULT_CAP);
  let hdr = $state(false);
  let subtitles = $state(false);
  let template = $state("");
  let bitrate = $state("");
  let advanced = $state(false);
  let open = $state<number | null>(null);
  let adding = $state(false);
  let addedCount = $state(0);
  let error = $state("");

  const header = $derived<Header>({
    cap,
    subtitles,
    hdr,
    outputTemplate: template,
    audioBitrate: bitrate,
  });
  $effect(() => {
    if (cap === "audio") hdr = false;
  });
  const add = $derived(addState(entries));
  const selectedCount = $derived(entries.filter((e) => e.selected).length);
  const title = $derived(result.title ?? `${entries.length} sources`);

  const options = readFetchOptions(localStorage.getItem(FETCH_OPTIONS_KEY));
  const checker = createChecker({
    lookup: (url) =>
      call(
        api.POST("/api/lookup", {
          body: { url, use_proxy: options.useProxy, use_cookies: options.useCookies },
        }),
      ),
    onResult: (index, r) => {
      entries = applyResult(entries, index, r);
    },
  });

  $effect(() => {
    for (const [i, e] of entries.entries()) {
      if (e.check === "checking") checker.want(i, e.entry.url);
      else if (e.check === "idle") checker.drop(i);
    }
  });
  $effect(() => () => checker.stop());

  function changeOverride(index: number, o: Override | null) {
    entries = setOverride(entries, index, o);
  }

  async function addAll() {
    if (adding || add.kind !== "ready") return;
    adding = true;
    error = "";
    addedCount = 0;
    try {
      const jobs = buildJobs(entries, header);
      await call(api.POST("/api/downloads", { body: { jobs } }));
      addedCount = jobs.length;
    } catch (err) {
      error = messageFor(err);
    } finally {
      adding = false;
    }
  }

  const input =
    "w-full rounded-control border border-line-strong bg-surface px-3 py-2 text-base text-fg placeholder:text-muted";
  const pill =
    "cursor-pointer rounded-pill border border-line-strong bg-transparent px-4 py-1.5 text-sm font-medium text-fg hover:bg-raised";
</script>

<div class="flex items-start gap-6">
  <section class="flex min-w-0 flex-1 flex-col gap-4">
    <header class="flex flex-col gap-3">
      <div class="flex items-baseline gap-3">
        <h1 class="m-0 text-xl font-bold tracking-[-0.01em]">{title}</h1>
        <p class="tabular m-0 text-sm text-muted">
          {entries.length}
          videos · {selectedCount} selected
        </p>
      </div>
      {#if result.skipped > 0}
        <p class="m-0 text-sm text-muted">Skipped {result.skipped}</p>
      {/if}
      <div class="flex flex-wrap items-end gap-4">
        <div class="flex gap-2">
          <button type="button" class={pill} onclick={() => (entries = selectAll(entries, true))}>
            Select all
          </button>
          <button type="button" class={pill} onclick={() => (entries = selectAll(entries, false))}>
            Select none
          </button>
        </div>
        <QualitySelect bind:value={cap} />
        <label class="flex items-center gap-2 pb-2 text-base">
          <input type="checkbox" bind:checked={subtitles} class="size-4 accent-(--color-action)">
          Subtitles
        </label>
        <label
          class="flex min-h-11 items-center gap-2 text-base {cap === "audio" ? "text-muted" : ""}"
        >
          <input
            type="checkbox"
            bind:checked={hdr}
            disabled={cap === "audio"}
            class="size-4 accent-(--color-action)"
          >
          HDR where available
        </label>
        <button
          type="button"
          class={pill}
          aria-expanded={advanced}
          onclick={() => (advanced = !advanced)}
        >
          Advanced
        </button>
        <button
          type="button"
          disabled={add.kind !== "ready" || adding}
          onclick={addAll}
          class="cursor-pointer rounded-pill border-0 bg-action px-5 py-2 text-sm font-semibold text-on-action disabled:opacity-50"
        >
          {#if add.kind === "checking"}
            Checking <span class="tabular">{add.done} / {add.total}</span>…
          {:else if add.kind === "ready"}
            Add {add.count} to queue
          {:else}
            Add to queue
          {/if}
        </button>
      </div>
      {#if advanced}
        <div class="grid max-w-xl grid-cols-2 gap-3">
          <div>
            <label for="list-template" class="mb-1 block text-sm font-medium"
              >Output template</label
            >
            <input
              id="list-template"
              type="text"
              class={input}
              placeholder="%(title)s.%(ext)s"
              bind:value={template}
            >
          </div>
          <div>
            <label for="list-bitrate" class="mb-1 block text-sm font-medium">Audio bitrate</label>
            <input
              id="list-bitrate"
              type="text"
              class={input}
              placeholder="192K"
              bind:value={bitrate}
            >
          </div>
        </div>
      {/if}
      {#if addedCount > 0}
        <p class="m-0 text-sm text-muted" role="status">
          Added {addedCount} to queue. <a class="text-fg" href="#/queue">Open queue</a>
        </p>
      {/if}
      {#if error}
        <p class="m-0 text-sm text-danger" role="alert">{error}</p>
      {/if}
    </header>

    <div class="grid grid-cols-[repeat(auto-fill,minmax(15rem,1fr))] gap-x-4 gap-y-6">
      {#each entries as item, i (i)}
        <EntryCard
          {item}
          {cap}
          active={open === i}
          ontoggle={(on) => (entries = setSelected(entries, i, on))}
          onopen={() => (open = i)}
        />
      {/each}
    </div>
  </section>

  {#if open !== null && entries[open]}
    <OverridePanel
      item={entries[open]}
      {header}
      onchange={(o) => open !== null && changeOverride(open, o)}
      onclose={() => (open = null)}
    />
  {/if}
</div>
