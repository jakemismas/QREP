import { defineConfig } from "@playwright/test";

// SPIKE_BASE_URL overrides the local preview server so the same spec can run
// against the deployed Pages site (e.g. https://jakemismas.github.io/QREP/app/).
const externalBase = process.env.SPIKE_BASE_URL;

export default defineConfig({
  testDir: "./e2e",
  timeout: 600_000,
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [["list"]],
  use: {
    baseURL: externalBase ?? "http://127.0.0.1:4173/",
    browserName: "chromium",
  },
  webServer: externalBase
    ? undefined
    : {
        command: "npm run preview -- --host 127.0.0.1 --port 4173 --strictPort",
        url: "http://127.0.0.1:4173/",
        reuseExistingServer: !process.env.CI,
        timeout: 60_000,
      },
});
