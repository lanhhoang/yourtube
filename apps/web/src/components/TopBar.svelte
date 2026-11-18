<script lang="ts">
  import LogoMark from "./LogoMark.svelte";
  import {
    FETCH_OPTIONS_KEY,
    readFetchOptions,
    saveFetchOptions,
    type FetchOptions,
  } from "../lib/fetch-options.ts";
  import { navigate } from "../lib/router.svelte.ts";

  let field = $state("");
  let options = $state<FetchOptions>(readFetchOptions(localStorage.getItem(FETCH_OPTIONS_KEY)));
  let menuOpen = $state(false);

  const lines = $derived(Math.min(6, Math.max(1, field.split("\n").length)));

  function submit() {
    const urls = field.trim();
    if (!urls) return;
    navigate({ name: "fetch", urls });
  }

  function onKeydown(e: KeyboardEvent) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  }

  function toggle(key: keyof FetchOptions) {
    options = { ...options, [key]: !options[key] };
    saveFetchOptions(options);
  }

  function onWindowKeydown(e: KeyboardEvent) {
    if (e.key === "Escape" && menuOpen) menuOpen = false;
  }
</script>

<svelte:window onkeydown={onWindowKeydown} />

<header class="flex h-14 shrink-0 items-center gap-3 px-4">
  <a
    href="#/"
    class="flex w-[120px] items-center gap-2 text-lg font-bold tracking-[-0.01em] text-fg no-underline"
  >
    <LogoMark />
    yourtube
  </a>

  <div class="mx-auto flex w-full max-w-[560px] items-start gap-2">
    <textarea
      bind:value={field}
      onkeydown={onKeydown}
      rows={lines}
      aria-label="Video or playlist URL"
      placeholder="Paste a video or playlist URL…"
      class="min-h-9 flex-1 resize-none rounded-[18px] border border-line-strong bg-surface px-4 py-[7px] text-sm leading-[1.4] text-fg placeholder:text-muted"
    ></textarea>

    <button
      type="button"
      onclick={submit}
      class="h-9 shrink-0 cursor-pointer rounded-pill border-0 bg-action px-4 text-sm font-semibold text-on-action transition-opacity duration-(--duration-fast) hover:opacity-90"
    >
      Fetch
    </button>

    <div class="relative">
      <button
        type="button"
        aria-label="Fetch options"
        aria-expanded={menuOpen}
        aria-haspopup="true"
        onclick={() => (menuOpen = !menuOpen)}
        class="grid size-9 cursor-pointer place-items-center rounded-pill border-0 bg-raised text-fg"
      >
        <svg
          viewBox="0 0 24 24"
          class="size-4"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
          stroke-linecap="round"
          aria-hidden="true"
        >
          <path d="M5 8l7 8 7-8" />
        </svg>
      </button>
      {#if menuOpen}
        <div
          class="absolute top-11 right-0 z-10 flex w-52 flex-col gap-1 rounded-control border border-line bg-surface p-2 shadow-[0_8px_24px_rgb(0_0_0/0.4)]"
        >
          <label
            class="flex cursor-pointer items-center gap-2 rounded-control px-2 py-1.5 text-sm hover:bg-raised"
          >
            <input
              type="checkbox"
              checked={options.useProxy}
              onchange={() => toggle("useProxy")}
              class="accent-accent"
            >
            Use saved proxy
          </label>
          <label
            class="flex cursor-pointer items-center gap-2 rounded-control px-2 py-1.5 text-sm hover:bg-raised"
          >
            <input
              type="checkbox"
              checked={options.useCookies}
              onchange={() => toggle("useCookies")}
              class="accent-accent"
            >
            Use saved cookies
          </label>
        </div>
      {/if}
    </div>
  </div>
  <div class="w-[120px]" aria-hidden="true"></div>
</header>
