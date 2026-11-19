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
  let input = $state<HTMLTextAreaElement>();
  let options = $state<FetchOptions>(readFetchOptions(localStorage.getItem(FETCH_OPTIONS_KEY)));
  let menuOpen = $state(false);

  const lines = $derived(Math.min(6, Math.max(1, field.split("\n").length)));

  function submit() {
    const urls = field.trim();
    if (!urls) return;
    navigate({ name: "fetch", urls });
  }

  async function paste() {
    let text = "";
    try {
      text = (await navigator.clipboard.readText()).trim();
    } catch {
      // Blocked or unavailable: fall through and focus the field for a manual paste.
    }
    if (text) field = text;
    else input?.focus();
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

<header
  class="flex min-h-14 shrink-0 items-center gap-3 px-3 pt-[env(safe-area-inset-top)] md:px-4"
>
  <a
    href="#/"
    class="flex shrink-0 items-center gap-2 text-lg md:w-[120px] font-bold tracking-[-0.01em] text-fg no-underline"
  >
    <LogoMark />
    <span class="sr-only md:not-sr-only">yourtube</span>
  </a>

  <div class="mx-auto flex w-full min-w-0 max-w-[560px] items-start gap-2">
    <textarea
      bind:this={input}
      bind:value={field}
      onkeydown={onKeydown}
      rows={lines}
      aria-label="Video or playlist URL"
      placeholder="Paste a link…"
      class="min-h-[44px] min-w-0 flex-1 resize-none rounded-[22px] border border-line-strong bg-surface px-4 py-[11px] text-[16px] leading-[1.3] md:min-h-9 md:rounded-[18px] md:py-[7px] md:text-sm md:leading-[1.4] text-fg placeholder:text-muted"
    ></textarea>

    {#if !field}
      <button
        type="button"
        onclick={paste}
        class="h-[44px] shrink-0 cursor-pointer rounded-pill border border-line-strong bg-transparent px-4 text-sm font-semibold text-fg hover:bg-raised md:hidden"
      >
        Paste
      </button>
    {/if}

    <button
      type="button"
      onclick={submit}
      class="h-[44px] shrink-0 cursor-pointer rounded-pill border-0 bg-action md:h-9 px-4 text-sm font-semibold text-on-action transition-opacity duration-(--duration-fast) hover:opacity-90"
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
        class="grid size-[44px] cursor-pointer md:size-9 place-items-center rounded-pill border-0 bg-raised text-fg"
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
  <div class="hidden w-[120px] md:block" aria-hidden="true"></div>
</header>
