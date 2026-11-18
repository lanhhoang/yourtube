<script lang="ts">
  import { api, call } from "../lib/api.ts";
  import type { components } from "../lib/api.gen.ts";
  import { messageFor } from "../lib/errors.ts";
  import { FETCH_OPTIONS_KEY, readFetchOptions } from "../lib/fetch-options.ts";
  import { latest } from "../lib/latest.ts";
  import ListView from "./ListView.svelte";
  import VideoView from "./VideoView.svelte";

  type SourcesResult = components["schemas"]["SourcesResult"];

  let { urls }: { urls: string } = $props();

  let result = $state<SourcesResult | null>(null);
  let loading = $state(true);
  let error = $state("");
  const ticket = latest();

  async function load(raw: string) {
    const current = ticket();
    const options = readFetchOptions(localStorage.getItem(FETCH_OPTIONS_KEY));
    loading = true;
    error = "";
    result = null;
    try {
      const data = await call(
        api.POST("/api/sources", {
          body: { urls: raw, use_proxy: options.useProxy, use_cookies: options.useCookies },
        }),
      );
      if (!current()) return;
      result = data;
    } catch (err) {
      if (!current()) return;
      error = messageFor(err);
    } finally {
      if (current()) loading = false;
    }
  }

  $effect(() => {
    void load(urls);
  });
</script>

{#if loading}
  <p class="m-0 text-muted" role="status">Fetching…</p>
{:else if error}
  <p class="m-0 text-danger" role="alert">
    {error}
    <button
      type="button"
      class="ml-2 cursor-pointer rounded-pill border border-line-strong bg-transparent px-4 py-2 text-sm font-medium text-fg hover:bg-raised"
      onclick={() => load(urls)}
    >
      Try again
    </button>
  </p>
{:else if result?.kind === "video" && result.video}
  {#key result.video.url}
    <VideoView video={result.video} />
  {/key}
{:else if result}
  {#key result}
    <ListView {result} />
  {/key}
{/if}
