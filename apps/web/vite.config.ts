import { resolve } from "node:path";
import { svelte } from "@sveltejs/vite-plugin-svelte";
import tailwindcss from "@tailwindcss/vite";
import { loadEnv } from "vite";
import { VitePWA } from "vite-plugin-pwa";
import { defineConfig } from "vitest/config";

export default defineConfig(({ mode }) => {
  // A shell variable wins over .env, as it does for the server's settings.
  const env = { ...loadEnv(mode, resolve(import.meta.dirname, "../.."), "YT_"), ...process.env };
  const target = `http://127.0.0.1:${env.YT_PORT ?? 8000}`;
  const lan = !!env.YT_HOST && env.YT_HOST !== "127.0.0.1" && env.YT_HOST !== "localhost";
  return {
    plugins: [
      tailwindcss(),
      svelte(),
      VitePWA({
        strategies: "injectManifest",
        srcDir: "src",
        filename: "sw.ts",
        registerType: "autoUpdate",
        injectRegister: "auto",
        includeAssets: ["favicon.ico", "apple-touch-icon-180x180.png"],
        manifest: {
          name: "YourTube",
          short_name: "YourTube",
          display: "standalone",
          start_url: "/",
          scope: "/",
          theme_color: "#0b0b0c",
          background_color: "#0b0b0c",
          icons: [
            { src: "pwa-64x64.png", sizes: "64x64", type: "image/png" },
            { src: "pwa-192x192.png", sizes: "192x192", type: "image/png" },
            { src: "pwa-512x512.png", sizes: "512x512", type: "image/png" },
            {
              src: "maskable-icon-512x512.png",
              sizes: "512x512",
              type: "image/png",
              purpose: "maskable",
            },
          ],
          share_target: {
            action: "/",
            method: "GET",
            params: { url: "share", text: "text", title: "title" },
          },
        },
      }),
    ],
    test: { include: ["test/**/*.test.ts"] },
    server: {
      host: lan ? true : undefined,
      proxy: { "/api": target, "/health": target },
    },
  };
});
