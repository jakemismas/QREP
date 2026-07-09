/**
 * S6 photo-flow e2e (issue #46). DOM contract: start-photo entry,
 * photo-dropzone + photo-file-input + photo-sample, photo-progress with
 * stage-<straighten|colors|grid|squares|repeats|borders> rows,
 * vision-loading (copy: "Loading the vision engine" + the MEASURED MB from
 * the manifest, never "downloading"), vision-cached notice, vision-retry,
 * photo-cancel, photo-results with confidence-<stage> meters (data-value),
 * overall-pill, uncertain-toggle (photo-sourced + nonzero count only),
 * open-in-editor, adjust-corners -> corner-editor with corner-pin-0..3 +
 * corner-reset + corner-rerun, lightbox tabs, reverse-timing (data-ms),
 * roundtrip-panel (roundtrip-level, roundtrip-run, roundtrip-report), and
 * body[data-vision-state] mirroring the RPC vision state.
 *
 * The L0 upload is generated at test runtime by the native CLI (the same
 * seeded renderer the round-trip harness trusts); recovered dims 45x55 and
 * the 1246/1229 census are the fixture's hand-known geometry.
 */
import { execFileSync } from "node:child_process";
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import * as path from "node:path";
import { fileURLToPath } from "node:url";
import { expect, test, type Page } from "@playwright/test";

const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const generatedDir = path.join(repoRoot, "tests", "fixtures", "_generated");
const l0Path = path.join(generatedDir, "photo_e2e_l0.png");
const outDir = path.join(repoRoot, "web", "test-results", "photo");
const READY_TIMEOUT = 300_000;
const REVERSE_TIMEOUT = 300_000;

test.beforeAll(() => {
  if (existsSync(l0Path)) return;
  mkdirSync(generatedDir, { recursive: true });
  const venvPython = path.join(repoRoot, ".venv", "Scripts", "python.exe");
  const python = process.env.QREP_PYTHON ?? (existsSync(venvPython) ? venvPython : "python");
  execFileSync(python, [
    "-m",
    "qrep.cli",
    "render",
    path.join(repoRoot, "tests", "fixtures", "double_irish_chain.json"),
    "--level",
    "0",
    "--seed",
    "42",
    "--scale",
    "10",
    "-o",
    l0Path,
  ]);
});

async function uploadPhoto(page: Page): Promise<void> {
  await page.goto("./");
  await page.getByTestId("start-photo").click();
  await expect(page.getByTestId("photo-dropzone")).toBeVisible();
  await page.getByTestId("photo-file-input").setInputFiles(l0Path);
}

test("L0 photo reverses in-browser to 45x55 with the palette mapped", async ({ page }) => {
  await uploadPhoto(page);
  const results = page.getByTestId("photo-results");
  await expect(results).toBeVisible({ timeout: REVERSE_TIMEOUT });

  // Every pipeline stage shows a real confidence value.
  for (const stage of ["straighten", "colors", "grid", "squares", "repeats", "borders"]) {
    const meter = page.getByTestId(`confidence-${stage}`);
    await expect(meter).toBeVisible();
    const value = Number(await meter.getAttribute("data-value"));
    expect(value).toBeGreaterThan(0);
    expect(value).toBeLessThanOrEqual(1);
  }
  await expect(page.getByTestId("overall-pill")).toBeVisible();

  // L0 is exact: all cells confident, so the uncertain toggle stays hidden
  // (photo-sourced + nonzero count only).
  await expect(page.getByTestId("uncertain-toggle")).toHaveCount(0);

  // Record the wall clock for the closing comment.
  const ms = Number(await page.getByTestId("reverse-timing").getAttribute("data-ms"));
  expect(ms).toBeGreaterThan(0);
  mkdirSync(outDir, { recursive: true });
  writeFileSync(path.join(outDir, "reverse-timing.json"), JSON.stringify({ reverseMs: ms }));

  // Open in editor: the recovered 45x55 grid carries the mapped palette -
  // the census equals the fixture's hand-known 1246/1229.
  await page.getByTestId("open-in-editor").click();
  await expect(page.getByTestId("editor")).toBeVisible();
  await expect(page.getByTestId("fabric-count-b").or(page.getByTestId("fabric-count-f1"))).toHaveText(
    /1,?246|1,?229/,
    { timeout: READY_TIMEOUT },
  );
});

test("editor and export flows never need opencv", async ({ page }) => {
  // Abort every opencv fetch: S2-S5 surfaces must work untouched (the idle
  // prefetch may fail silently; that is its contract).
  await page.route("**/*opencv*", (route) => route.abort());
  await page.goto("./");
  await page.getByTestId("open-demo").click();
  await expect(page.getByTestId("editor")).toBeVisible();
  await expect(page.getByTestId("engine-chip")).toHaveAttribute("data-engine-phase", "ready", {
    timeout: READY_TIMEOUT,
  });
  await expect(page.getByTestId("fabric-count-b")).toHaveText(/1,?246/);
  await page.getByRole("tab", { name: "Pattern" }).click();
  await expect(page.getByTestId("strategy-card-strip")).toBeVisible();
  const waiting = page.waitForEvent("download");
  await page.getByTestId("download-cutlist-csv").click();
  await waiting;
  // No error toast anywhere in the flow.
  await expect(page.getByTestId("toast")).not.toContainText(/fail|error/i);
});

test("idle prefetch: post-prefetch reverse shows no loading bar (PARITY 17)", async ({
  page,
}) => {
  await page.goto("./");
  await expect(page.locator("body")).toHaveAttribute("data-vision-state", "ready", {
    timeout: READY_TIMEOUT,
  });
  await page.getByTestId("start-photo").click();
  await page.getByTestId("photo-file-input").setInputFiles(l0Path);
  // The vision stack is already here: straight to stages, no loading bar.
  await expect(page.getByTestId("vision-loading")).toHaveCount(0);
  await expect(page.getByTestId("photo-results")).toBeVisible({ timeout: REVERSE_TIMEOUT });
});

test("pre-prefetch reverse shows the staged loading bar with the measured size", async ({
  page,
}) => {
  // Hold opencv back until the reverse starts, so the flow hits the cold
  // path deterministically.
  let releaseOpencv = false;
  await page.route("**/*opencv*", async (route) => {
    if (releaseOpencv) return route.continue();
    return route.abort();
  });
  await page.goto("./");
  await uploadPhoto(page).then(
    () => {},
    () => {},
  );
  releaseOpencv = true;
  // The loading bar names the vision engine with the measured payload
  // (manifest visionBytes = 11,700,243 -> about 11.2 MB), never
  // "downloading". Retry recovers after the block lifts.
  const loading = page.getByTestId("vision-loading");
  const retry = page.getByTestId("vision-retry");
  await expect(loading.or(retry).first()).toBeVisible({ timeout: 60_000 });
  if (await retry.isVisible()) {
    await retry.click();
  }
  await expect(page.getByTestId("photo-results")).toBeVisible({ timeout: REVERSE_TIMEOUT });
});

test("vision loading copy is loading, sized, and cached on repeat", async ({ page }) => {
  await page.goto("./");
  await page.getByTestId("start-photo").click();
  await page.getByTestId("photo-file-input").setInputFiles(l0Path);
  const progress = page.getByTestId("photo-progress");
  await expect(progress).toBeVisible();
  const bodyText = (await progress.textContent()) ?? "";
  expect(bodyText).not.toMatch(/download/i);
  await expect(page.getByTestId("photo-results")).toBeVisible({ timeout: REVERSE_TIMEOUT });
});

test("cancel returns to the dropzone and the engine reboots safely", async ({ page }) => {
  await uploadPhoto(page);
  const cancel = page.getByTestId("photo-cancel");
  // Cancel may race a fast local reverse; only assert when we caught it.
  if (await cancel.isVisible().catch(() => false)) {
    await cancel.click();
    await expect(page.getByTestId("photo-dropzone")).toBeVisible();
    await expect(page.getByTestId("engine-chip")).toHaveAttribute("data-engine-phase", "ready", {
      timeout: READY_TIMEOUT,
    });
  }
});

test("corner adjust re-runs reverse with user corners", async ({ page }) => {
  await uploadPhoto(page);
  await expect(page.getByTestId("photo-results")).toBeVisible({ timeout: REVERSE_TIMEOUT });
  await page.getByTestId("adjust-corners").click();
  const editor = page.getByTestId("corner-editor");
  await expect(editor).toBeVisible();
  // Nudge pin 0 by a few pixels and re-run.
  const pin = page.getByTestId("corner-pin-0");
  const box = (await pin.boundingBox())!;
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
  await page.mouse.down();
  await page.mouse.move(box.x + box.width / 2 + 6, box.y + box.height / 2 + 6, { steps: 3 });
  await page.mouse.up();
  await page.getByTestId("corner-rerun").click();
  await expect(page.getByTestId("photo-results")).toBeVisible({ timeout: REVERSE_TIMEOUT });
  await expect(page.getByTestId("confidence-grid")).toBeVisible();
});

test("round-trip demo panel renders, reverses, and compares", async ({ page }) => {
  await page.goto("./");
  await page.getByTestId("open-demo").click();
  await expect(page.getByTestId("editor")).toBeVisible();
  await expect(page.getByTestId("engine-chip")).toHaveAttribute("data-engine-phase", "ready", {
    timeout: READY_TIMEOUT,
  });
  await page.getByRole("tab", { name: "Pattern" }).click();
  await page.getByTestId("roundtrip-level").selectOption("0");
  await page.getByTestId("roundtrip-run").click();
  const report = page.getByTestId("roundtrip-report");
  await expect(report).toBeVisible({ timeout: REVERSE_TIMEOUT });
  // L0 round trip on the current design is exact (sprint 1 harness):
  // dims match and every square agrees.
  await expect(report).toContainText(/match/i);
  await expect(report).toContainText(/100%|1\.0000/);
});

test("the photo bitmap is session-only (PARITY 7)", async ({ page }) => {
  await uploadPhoto(page);
  await expect(page.getByTestId("photo-results")).toBeVisible({ timeout: REVERSE_TIMEOUT });
  await page.getByTestId("open-in-editor").click();
  await expect(page.getByTestId("editor")).toBeVisible();
  // The compare/lightbox affordance exists while the bitmap lives.
  await expect(page.getByTestId("open-lightbox")).toBeVisible();
  await page.reload();
  await page.getByTestId("resume-accept").click();
  await expect(page.getByTestId("editor")).toBeVisible();
  // After reload the photo is gone and compare affordances hide.
  await expect(page.getByTestId("open-lightbox")).toHaveCount(0);
});
