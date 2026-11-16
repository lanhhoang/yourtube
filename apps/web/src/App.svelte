<script lang="ts">
  import LeftRail from "./components/LeftRail.svelte";
  import TopBar from "./components/TopBar.svelte";
  import { watchSystemTheme } from "./lib/theme.ts";
  import { router } from "./lib/router.svelte.ts";
  import { section } from "./lib/router.ts";

  $effect(() => watchSystemTheme());
</script>

<div class="flex h-screen flex-col">
  <TopBar />
  <div class="flex min-h-0 flex-1">
    <LeftRail active={section(router.route)} />
    <main class="min-w-0 flex-1 overflow-y-auto p-6">
      {#if router.route.name === "queue"}
        <h1 class="m-0 text-xl font-bold">Queue</h1>
      {:else if router.route.name === "settings"}
        <h1 class="m-0 text-xl font-bold">Settings</h1>
      {:else if router.route.name === "fetch"}
        <h1 class="m-0 text-xl font-bold">Fetch</h1>
      {:else}
        <h1 class="m-0 text-xl font-bold">Library</h1>
      {/if}
    </main>
  </div>
</div>
