import { resolve } from "node:path";
import { svelte } from "@sveltejs/vite-plugin-svelte";
import tailwindcss from "@tailwindcss/vite";
import { loadEnv } from "vite";
import { defineConfig } from "vitest/config";

export default defineConfig(({ mode }) => {
  // A shell variable wins over .env, as it does for the server's settings.
  const env = { ...loadEnv(mode, resolve(import.meta.dirname, "../.."), "YT_"), ...process.env };
  const target = `http://127.0.0.1:${env.YT_PORT ?? 8000}`;
  const lan = !!env.YT_HOST && env.YT_HOST !== "127.0.0.1" && env.YT_HOST !== "localhost";
  return {
    plugins: [tailwindcss(), svelte()],
    test: { include: ["test/**/*.test.ts"] },
    server: {
      host: lan ? true : undefined,
      proxy: { "/api": target, "/health": target },
    },
  };
});
