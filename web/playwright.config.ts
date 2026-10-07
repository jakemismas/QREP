import { existsSync, readFileSync } from "node:fs";
import * as path from "node:path";
import { fileURLToPath } from "node:url";
import { defineConfig } from "@playwright/test";

// SPIKE_BASE_URL overrides the local preview server so the same spec can run
// against the deployed Pages site (e.g. https://jakemismas.github.io/QREP/app/).
const externalBase = process.env.SPIKE_BASE_URL;

// Parallel sprint workers each own a port: scripts/worker_bootstrap.sh writes
// QREP_E2E_PORT to the worktree's .qrep-worker.env (an exported QREP_E2E_PORT
// wins). A run never reuses a server that already listens unless
// QREP_E2E_REUSE=1 asks for it outside CI and without a worker port, because
// whatever listens there may serve another checkout's build; without a port
// the run takes 4173 and fails loudly if something already holds it.
function readWorkerEnv(): Record<string, string> {
  const file = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", ".qrep-worker.env");
  if (!existsSync(file)) return {};
  const values: Record<string, string> = {};
  for (const line of readFileSync(file, "utf8").split(/\r?\n/)) {
    const match = /^\s*([A-Z0-9_]+)\s*=\s*(.*?)\s*$/.exec(line);
    if (match) values[match[1]] = match[2].replace(/^"(.*)"$/, "$1");
  }
  return values;
}

function workerPort(): number | undefined {
  const raw = process.env.QREP_E2E_PORT || readWorkerEnv().QREP_E2E_PORT;
  if (!raw) return undefined;
  const port = Number(raw);
  if (!Number.isInteger(port) || port < 1024 || port > 65535) {
    throw new Error(`QREP_E2E_PORT must be an integer from 1024 to 65535, got "${raw}"`);
  }
  return port;
}

const port = workerPort();
const localPort = port ?? 4173;
const localBase = `http://127.0.0.1:${localPort}/`;

export default defineConfig({
  testDir: "./e2e",
  timeout: 600_000,
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [["list"]],
  // Refuses a dist whose qrep wheel was built from other sources.
  globalSetup: externalBase ? undefined : "./scripts/wheel-hash.mjs",
  use: {
    baseURL: externalBase ?? localBase,
    browserName: "chromium",
  },
  webServer: externalBase
    ? undefined
    : {
        command: `npm run preview -- --host 127.0.0.1 --port ${localPort} --strictPort`,
        url: localBase,
        reuseExistingServer:
          port === undefined && process.env.QREP_E2E_REUSE === "1" && !process.env.CI,
        timeout: 60_000,
      },
});
