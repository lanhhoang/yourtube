<script lang="ts">
  import { untrack } from "svelte";
  import Chips from "../components/Chips.svelte";
  import JobCard from "../components/JobCard.svelte";
  import { api, call } from "../lib/api.ts";
  import { messageFor } from "../lib/errors.ts";
  import { latest } from "../lib/latest.ts";
  import { type Chip, libraryItems } from "../lib/library.ts";
  import { type JobOut, leftActive, newlyCompleted, type QueueOut } from "../lib/queue.ts";

  let { queue }: { queue: QueueOut | null } = $props();

  let q = $state("");
  let chip = $state<Chip>("all");
  let done = $state<JobOut[]>([]);
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
  const items = $derived(libraryItems(done, searching ? [] : (queue?.active ?? []), chip));
  const noJobs = $derived(done.length === 0 && (searching || (queue?.active.length ?? 0) === 0));

  function removed(id: number) {
    done = done.filter((j) => j.id !== id);
  }
</script>

<div class="flex items-center gap-4">
  <h1 class="m-0 text-xl font-bold tracking-[-0.01em]">Library</h1>
  <input
    type="search"
    bind:value={q}
    aria-label="Search library"
    placeholder="Search title or uploader"
    class="ml-auto w-72 rounded-pill border border-line-strong bg-surface px-4 py-1.5 text-base text-fg placeholder:text-muted"
  >
</div>
<div class="mt-4"><Chips bind:value={chip} /></div>

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
      {:else if noJobs}
        No downloads yet. Paste a URL above.
      {:else}
        Nothing here yet.
      {/if}
    </p>
  {:else}
    <div class="mt-6 grid grid-cols-[repeat(auto-fill,minmax(240px,1fr))] gap-x-4 gap-y-6">
      {#each items as job (job.id)}
        <JobCard {job} ondeleted={removed} />
      {/each}
    </div>
  {/if}
{/if}
