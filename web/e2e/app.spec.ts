/**
 * S2 app-shell e2e (issue #42). These tests define the DOM contract the UI
 * implements (test ids, data attributes) and encode the acceptance criteria:
 *
 *  - demo quilt renders true to scale with 75" x 90" ruler extents
 *    (hand-derived from the fixture: 600/720 eighths finished dims)
 *  - engine chip lifecycle incl. network-kill -> failed -> retry -> ready
 *  - project JSON upload: valid renders, corrupt shows the error envelope's
 *    message (never a traceback)
 *  - fabric summary census from bridge data: 1246 blue / 1229 cream
 *    (design-doc census literals)
 *  - the editor is interactive before the engine finishes booting
 *  - theme toggle persists across reload
 *
 * No screenshot/snapshot assertions (banned); everything is semantic.
 */
import { expect, test, type Page } from "@playwright/test";
import { readFileSync } from "node:fs";
import * as path from "node:path";
import { fileURLToPath } from "node:url";

const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const fixturePath = path.join(repoRoot, "tests", "fixtures", "double_irish_chain.json");

const READY_TIMEOUT = 300_000;

async function openDemo(page: Page): Promise<void> {
  await page.goto("./");
  await page.getByTestId("open-demo").click();
  await expect(page.getByTestId("editor")).toBeVisible();
}

function chip(page: Page) {
  return page.getByTestId("engine-chip");
}

test("demo quilt renders true to scale with correct rulers", async ({ page }) => {
  await openDemo(page);
  // #58: the app page carries the product title, not the S0 spike's.
  await expect(page).toHaveTitle("QREP");
  // Fixture finished dims: 600 x 720 eighths = 75" x 90" (design doc).
  await expect(page.getByTestId("quilt-canvas")).toHaveAttribute("data-finished-width", "600");
  await expect(page.getByTestId("quilt-canvas")).toHaveAttribute("data-finished-height", "720");
  await expect(page.getByTestId("ruler-x-end")).toHaveText('75"');
  await expect(page.getByTestId("ruler-y-end")).toHaveText('90"');
});

test("engine chip reaches ready on a healthy load", async ({ page }) => {
  await page.goto("./");
  await expect(chip(page)).toHaveAttribute("data-engine-phase", "ready", {
    timeout: READY_TIMEOUT,
  });
});

test("killing the network surfaces retry and recovery works", async ({ page }) => {
  // Abort every pyodide asset fetch: boot must fail visibly with a retry
  // action, never an opaque hang.
  await page.route("**/pyodide/**", (route) => route.abort());
  await page.goto("./");
  await expect(chip(page)).toHaveAttribute("data-engine-phase", "failed", {
    timeout: 120_000,
  });
  await page.unroute("**/pyodide/**");
  await page.getByTestId("engine-retry").click();
  await expect(chip(page)).toHaveAttribute("data-engine-phase", "ready", {
    timeout: READY_TIMEOUT,
  });
});

test("uploading a valid project JSON renders it", async ({ page }) => {
  await page.goto("./");
  await page.getByTestId("open-project").click();
  await expect(page.getByTestId("open-modal")).toBeVisible();
  await page.getByTestId("open-file-input").setInputFiles({
    name: "double_irish_chain.json",
    mimeType: "application/json",
    buffer: readFileSync(fixturePath),
  });
  await expect(page.getByTestId("editor")).toBeVisible();
  await expect(page.getByTestId("ruler-x-end")).toHaveText('75"');
});

test("corrupted JSON shows the error envelope message, not a traceback", async ({ page }) => {
  await page.goto("./");
  await expect(chip(page)).toHaveAttribute("data-engine-phase", "ready", {
    timeout: READY_TIMEOUT,
  });
  await page.getByTestId("open-project").click();
  await page.getByTestId("open-file-input").setInputFiles({
    name: "broken.json",
    mimeType: "application/json",
    buffer: Buffer.from("{this is not json", "utf8"),
  });
  const toast = page.getByTestId("toast");
  await expect(toast).toBeVisible();
  const text = (await toast.textContent()) ?? "";
  expect(text).toMatch(/malformed JSON|couldn't read/i);
  expect(text).not.toContain("Traceback");
});

test("fabric summary counts match the fixture census via bridge data", async ({ page }) => {
  await openDemo(page);
  await expect(chip(page)).toHaveAttribute("data-engine-phase", "ready", {
    timeout: READY_TIMEOUT,
  });
  // Census literals from the design doc: 1246 blue, 1229 cream.
  await expect(page.getByTestId("fabric-count-b")).toHaveText(/1,?246/);
  await expect(page.getByTestId("fabric-count-c")).toHaveText(/1,?229/);
});

test("the editor is interactive before the engine finishes booting", async ({ page }) => {
  // Stall (never fulfill) the biggest pyodide asset so boot cannot finish,
  // then prove the demo opens and renders anyway: rendering is pure JS.
  await page.route("**/pyodide/pyodide.asm.wasm", () => {
    /* never fulfil, never abort: boot hangs */
  });
  await page.goto("./");
  await page.getByTestId("open-demo").click();
  await expect(page.getByTestId("editor")).toBeVisible();
  await expect(page.getByTestId("quilt-canvas")).toBeVisible();
  const phase = await chip(page).getAttribute("data-engine-phase");
  expect(phase).toBe("booting");
  // No blocking loading UI outside the photo flow: the canvas is on screen
  // while the chip still says booting, and nothing says download/install.
  const bodyText = (await page.locator("body").textContent()) ?? "";
  expect(bodyText).not.toMatch(/download|install/i);
});

test("theme toggle persists across reload", async ({ page }) => {
  await page.goto("./");
  const html = page.locator("html");
  await expect(html).toHaveAttribute("data-skin", "light");
  await page.getByTestId("theme-toggle").click();
  await expect(html).toHaveAttribute("data-skin", "dark");
  await page.reload();
  await expect(html).toHaveAttribute("data-skin", "dark");
});
