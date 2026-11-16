import { resolve } from "node:path";
import { defineConfig, devices } from "@playwright/test";

const repo = resolve(import.meta.dirname, "../..");

export default defineConfig({
  testDir: "e2e",
  use: {
    ...devices["Desktop Chrome"],
    viewport: { width: 1440, height: 900 },
    // Set PW_CHANNEL=chrome to use an installed Google Chrome.
    channel: process.env.PW_CHANNEL,
    baseURL: "http://127.0.0.1:8100",
  },
  webServer: {
    command:
      "pnpm build && rm -rf ../../tmp/e2e && cd ../server && uv run uvicorn tests.e2e_server:app --host 127.0.0.1 --port 8100",
    url: "http://127.0.0.1:8100/health",
    timeout: 180_000,
    reuseExistingServer: false,
    env: {
      YT_DATA_DIR: `${repo}/tmp/e2e/data`,
      YT_DOWNLOADS_DIR: `${repo}/tmp/e2e/downloads`,
      YT_DATABASE_URL: `sqlite:///${repo}/tmp/e2e/data/yourtube.db`,
      YT_PROXY_URL: "",
      YT_COOKIES_PATH: "",
      YT_WORKERS_ENABLED: "1",
      YT_SKIP_MIGRATIONS: "0",
    },
  },
});
