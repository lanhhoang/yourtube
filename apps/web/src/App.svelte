<script lang="ts">
  import { router } from "./lib/router.svelte.ts";
</script>

{#if router.route.name === "queue"}
  <h1>Queue</h1>
{:else if router.route.name === "settings"}
  <h1>Settings</h1>
{:else if router.route.name === "fetch"}
  <h1>Fetch</h1>
{:else}
  <h1>Library</h1>
{/if}
