<script lang="ts">
  import ThemeSelect from "../components/ThemeSelect.svelte";
  import { api, call } from "../lib/api.ts";
  import type { components } from "../lib/api.gen.ts";
  import { messageFor } from "../lib/errors.ts";

  type SettingsOut = components["schemas"]["SettingsOut"];
  type DiagnosticsOut = components["schemas"]["DiagnosticsOut"];

  let form = $state<SettingsOut | null>(null);
  let diagnostics = $state<DiagnosticsOut | null>(null);
  let loadError = $state("");
  let saving = $state(false);
  let status = $state<{ ok: boolean; text: string } | null>(null);
  let confirmReset = $state(false);

  async function load() {
    loadError = "";
    try {
      [form, diagnostics] = await Promise.all([
        call(api.GET("/api/settings")),
        call(api.GET("/api/diagnostics")),
      ]);
    } catch (err) {
      loadError = messageFor(err);
    }
  }
  void load();

  async function save(e: SubmitEvent) {
    e.preventDefault();
    if (!form || saving) return;
    saving = true;
    status = null;
    try {
      form = await call(api.PUT("/api/settings", { body: form }));
      status = { ok: true, text: "Settings saved." };
    } catch (err) {
      status = { ok: false, text: messageFor(err) };
    } finally {
      saving = false;
    }
  }

  async function reset() {
    if (!confirmReset) {
      confirmReset = true;
      return;
    }
    confirmReset = false;
    status = null;
    try {
      form = await call(api.POST("/api/settings/reset"));
      status = { ok: true, text: "Settings reset to defaults." };
    } catch (err) {
      status = { ok: false, text: messageFor(err) };
    }
  }

  const input =
    "w-full rounded-control border border-line-strong bg-surface px-3 py-2 text-[16px] text-fg placeholder:text-muted md:text-base min-h-[44px] md:min-h-0";
  const btn =
    "min-h-[44px] cursor-pointer rounded-pill border border-line-strong bg-transparent px-4 py-2 text-sm md:min-h-0 font-medium text-fg transition-colors duration-(--duration-fast) hover:bg-raised disabled:cursor-default disabled:opacity-50";
</script>

<h1 class="m-0 text-xl font-bold tracking-[-0.01em]">Settings</h1>

{#if loadError}
  <p class="mt-6 text-danger">
    {loadError}
    <button type="button" class="{btn} ml-2" onclick={load}>Try again</button>
  </p>
{:else if form}
  {#if diagnostics?.level === "warning"}
    <div class="mt-6 max-w-xl rounded-control border border-warn p-3 text-sm" role="status">
      <p class="m-0 font-semibold text-warn">Heads up</p>
      <ul class="m-0 mt-1 list-disc pl-5">
        {#each diagnostics.messages as m (m)}
          <li>{m}</li>
        {/each}
      </ul>
    </div>
  {/if}

  <form class="mt-6 flex max-w-xl flex-col gap-5" onsubmit={save}>
    <div>
      <label for="max_concurrent" class="mb-1 block text-sm font-medium"
        >Max concurrent downloads</label
      >
      <input
        id="max_concurrent"
        type="number"
        min="1"
        max="5"
        class="{input} w-24"
        bind:value={form.max_concurrent}
      >
      <p class="m-0 mt-1 text-sm text-muted">Applies after restart.</p>
    </div>
    <div>
      <label for="proxy_url" class="mb-1 block text-sm font-medium">Proxy URL</label>
      <input id="proxy_url" type="text" class={input} bind:value={form.proxy_url}>
    </div>
    <div>
      <label for="cookies_path" class="mb-1 block text-sm font-medium">Cookies file path</label>
      <input id="cookies_path" type="text" class={input} bind:value={form.cookies_path}>
    </div>
    <div>
      <label for="downloads_dir" class="mb-1 block text-sm font-medium">Downloads folder</label>
      <input
        id="downloads_dir"
        type="text"
        class={input}
        placeholder="Default from server config"
        bind:value={form.downloads_dir}
      >
    </div>
    <div class="flex flex-wrap items-center gap-3">
      <button
        type="submit"
        disabled={saving}
        class="min-h-[44px] cursor-pointer rounded-pill border-0 bg-action px-5 py-2 md:min-h-0 text-sm font-semibold text-on-action disabled:opacity-50"
      >
        Save
      </button>
      <button type="button" class={btn} onclick={reset} onblur={() => (confirmReset = false)}>
        {confirmReset ? "Confirm reset" : "Reset to defaults"}
      </button>
      {#if status}
        <p class="m-0 text-sm {status.ok ? "text-muted" : "text-danger"}" role="status">
          {status.text}
        </p>
      {/if}
    </div>
  </form>

  <div class="mt-8 max-w-xl">
    <h2 class="m-0 mb-2 text-lg font-semibold">Theme</h2>
    <div class="w-32 md:w-24"><ThemeSelect label="Theme (settings)" /></div>
  </div>
{/if}
