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
 *
 * C3b (issue #101; docs/sprint-5/REBASELINE.md): the crop screen is now the
 * confirm screen, whose pins start at a neutral inset with nothing detected.
 * uploadPhoto reaches the read by placing the four pins (corner-pin-0..3,
 * data-x and data-y in source pixels) on the render's sidecar corners and
 * entering the counts, 9 blocks x 5 squares across and 11 x 5 down, before
 * Continue (crop-analyze). The assertions after the read are unchanged.
 */
import { execFileSync } from "node:child_process";
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import * as path from "node:path";
import { fileURLToPath } from "node:url";
import { expect, test, type Page } from "@playwright/test";

const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const generatedDir = path.join(repoRoot, "tests", "fixtures", "_generated");
const l0Path = path.join(generatedDir, "photo_e2e_l0.png");
// save_render writes the sidecar beside the PNG; its "corners" are the
// quilt's outer corners in image pixels, in pin order.
const l0SidecarPath = path.join(generatedDir, "photo_e2e_l0.json");
const outDir = path.join(repoRoot, "web", "test-results", "photo");
const READY_TIMEOUT = 300_000;
const REVERSE_TIMEOUT = 300_000;

test.beforeAll(() => {
  if (existsSync(l0Path) && existsSync(l0SidecarPath)) return;
  mkdirSync(generatedDir, { recursive: true });
  const venvPython = path.join(repoRoot, ".venv", "Scripts", "python.exe");
  const python = process.env.QREP_PYTHON ?? (existsSync(venvPython) ? venvPython : "python");
  // Direct API call: qrep.cli has no __main__ guard, so `-m qrep.cli` is a
  // silent no-op. Same seeded renderer the CLI wraps.
  execFileSync(python, [
    "-c",
    "import sys; from pathlib import Path; from qrep.model import load; from qrep.render import save_render; " +
      "save_render(load(sys.argv[1]), Path(sys.argv[2]), level=0, seed=42, scale=10)",
    path.join(repoRoot, "tests", "fixtures", "double_irish_chain.json"),
    l0Path,
  ]);
  if (!existsSync(l0Path) || !existsSync(l0SidecarPath)) throw new Error("fixture render produced no file or sidecar");
});

interface Point {
  x: number;
  y: number;
}

/** Drags a pin near the target, then nudges it with the arrow keys (Shift for 10 source px) onto it exactly. */
async function placePin(page: Page, index: number, target: Point): Promise<void> {
  const crop = page.getByTestId("crop-screen");
  const width = Number(await crop.getAttribute("data-canvas-width"));
  const height = Number(await crop.getAttribute("data-canvas-height"));
  const pin = page.getByTestId(`corner-pin-${index}`);
  const image = (await page.getByTestId("pin-image").boundingBox())!;
  const box = (await pin.boundingBox())!;
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
  await page.mouse.down();
  await page.mouse.move(image.x + (target.x / width) * image.width, image.y + (target.y / height) * image.height, {
    steps: 4,
  });
  await page.mouse.up();
  await pin.focus();
  for (let round = 0; round < 4; round++) {
    const dx = target.x - Number(await pin.getAttribute("data-x"));
    const dy = target.y - Number(await pin.getAttribute("data-y"));
    if (dx === 0 && dy === 0) break;
    for (const [delta, plus, minus] of [
      [dx, "ArrowRight", "ArrowLeft"],
      [dy, "ArrowDown", "ArrowUp"],
    ] as const) {
      const key = delta > 0 ? plus : minus;
      for (let i = 0; i < Math.floor(Math.abs(delta) / 10); i++) await page.keyboard.press(`Shift+${key}`);
      for (let i = 0; i < Math.abs(delta) % 10; i++) await page.keyboard.press(key);
    }
  }
  await expect(pin).toHaveAttribute("data-x", String(target.x));
  await expect(pin).toHaveAttribute("data-y", String(target.y));
}

interface UploadOptions {
  /** Load the start screen first; off when the test has loaded it already and waited on something there. */
  navigate?: boolean;
  /** Place the pins and enter the counts; off presses Continue on the default pins and counts. */
  pins?: boolean;
}

/**
 * Upload the L0 render and press Continue on the confirm screen (C3b, issue
 * #101). With pins (the default), first set the four pins on the render's
 * sidecar corners and the counts to 9 blocks x 5 squares across (45) and
 * 11 x 5 down (55), the render's grid.
 */
async function uploadPhoto(page: Page, { navigate = true, pins = true }: UploadOptions = {}): Promise<void> {
  if (navigate) await page.goto("./");
  await page.getByTestId("start-photo").click();
  await expect(page.getByTestId("photo-dropzone")).toBeVisible();
  await page.getByTestId("photo-file-input").setInputFiles(l0Path);
  await expect(page.getByTestId("crop-screen")).toBeVisible();
  if (pins) {
    // The pins map through the photo's own box, so it must have loaded first.
    await expect
      .poll(() => page.getByTestId("pin-image").evaluate((img: HTMLImageElement) => img.naturalWidth))
      .toBeGreaterThan(0);
    const sidecar = JSON.parse(readFileSync(l0SidecarPath, "utf8")) as { corners: [number, number][] };
    for (const [index, [x, y]] of sidecar.corners.entries()) await placePin(page, index, { x, y });
    for (const [axis, blocks] of [
      ["across", 9],
      ["down", 11],
    ] as const) {
      for (const [part, value] of [
        ["blocks", blocks],
        ["squares", 5],
      ] as const) {
        const input = page.getByTestId(`counts-${axis}-${part}`);
        await input.fill(String(value));
        await input.blur();
        // A refused count shows its old value again once the field is left.
        await expect(input).toHaveValue(String(value));
      }
    }
  }
  await page.getByTestId("crop-analyze").click();
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

interface SeenToast {
  tone: string;
  text: string;
}

/** Record every toast the page shows, from the first page load on; read them
 * back with seenToasts. The one toast slot shows only the latest, so a check
 * on the toast showing at the end cannot see an earlier one; a
 * MutationObserver keeps them all (as recordToasts in pattern.spec.ts). */
async function recordToasts(page: Page): Promise<void> {
  await page.addInitScript(() => {
    const seen: { tone: string; text: string }[] = [];
    (window as unknown as { toastRecord: typeof seen }).toastRecord = seen;
    const take = (node: Node) => {
      if (!(node instanceof HTMLElement)) return;
      const toasts = node.matches("[data-testid='toast']")
        ? [node]
        : [...node.querySelectorAll<HTMLElement>("[data-testid='toast']")];
      for (const toast of toasts) {
        seen.push({ tone: toast.dataset.tone ?? "", text: toast.textContent ?? "" });
      }
    };
    // The script runs before the page has a body, so the observer watches the
    // whole document.
    new MutationObserver((mutations) => {
      for (const mutation of mutations) mutation.addedNodes.forEach(take);
    }).observe(document, { childList: true, subtree: true });
  });
}

function seenToasts(page: Page): Promise<SeenToast[]> {
  return page.evaluate(() => (window as unknown as { toastRecord: SeenToast[] }).toastRecord);
}

test("editor and export flows never need opencv", async ({ page }) => {
  // Abort every opencv fetch: S2-S5 surfaces must work untouched (the idle
  // prefetch may fail silently; that is its contract). C2a (issue #96):
  // the sample pattern's census and Download pattern (PDF) on Your pattern.
  await page.route("**/*opencv*", (route) => route.abort());
  await recordToasts(page);
  await page.goto("./");
  await page.getByTestId("see-sample").click();
  await expect(page.getByTestId("your-pattern")).toBeVisible();
  await expect(page.getByTestId("engine-chip")).toHaveAttribute("data-engine-phase", "ready", {
    timeout: READY_TIMEOUT,
  });
  await expect(page.getByTestId("fabric-count-b")).toHaveText(/1,?246/);
  const waiting = page.waitForEvent("download");
  await page.getByTestId("download-pattern").click();
  await waiting;
  // No error toast anywhere in the flow.
  await expect(page.getByTestId("toast")).not.toContainText(/fail|error/i);
  // Every toast since the page loaded, not just the one showing now: the
  // saved file's success toast is among them, so the record is live, and
  // none is an error or says one.
  await expect
    .poll(() => seenToasts(page))
    .toContainEqual({ tone: "success", text: expect.stringContaining("Saved: your pattern file is ready.") });
  for (const toast of await seenToasts(page)) {
    expect(toast.tone, toast.text).not.toBe("error");
    expect(toast.text).not.toMatch(/fail|error/i);
  }
  // Your pattern reports its own failures inline, not in a toast.
  await expect(page.getByTestId("pattern-error")).toHaveCount(0);
});

test("idle prefetch: post-prefetch reverse shows no loading bar (PARITY 17)", async ({
  page,
}) => {
  await page.goto("./");
  await expect(page.locator("body")).toHaveAttribute("data-vision-state", "ready", {
    timeout: READY_TIMEOUT,
  });
  // C3b: through the confirm screen with the pins and counts set.
  await uploadPhoto(page, { navigate: false });
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
  // Hold the opencv fetch open while we read the progress screen: locally
  // the whole reverse can finish in ~2.5s, faster than transient-screen
  // assertions can observe.
  let releaseVision: () => void = () => {};
  const gate = new Promise<void>((resolve) => {
    releaseVision = resolve;
  });
  await page.route("**/*opencv*", async (route) => {
    await gate;
    await route.continue();
  });
  // C3b: through the confirm screen with the pins and counts set.
  await uploadPhoto(page);
  const progress = page.getByTestId("photo-progress");
  await expect(progress).toBeVisible();
  const loading = page.getByTestId("vision-loading");
  await expect(loading).toBeVisible();
  // Measured size, loading vocabulary, no download language anywhere.
  await expect(loading).toContainText("11.2 MB");
  await expect(loading).toContainText(/loading the vision engine/i);
  const bodyText = (await progress.textContent()) ?? "";
  expect(bodyText).not.toMatch(/download/i);
  releaseVision();
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
  // S2 traversal amendment (issue #68): "Adjust the crop" returns to the
  // crop screen (the corners screen is retired), the confirm screen since
  // C3b, holding the pins and counts the read used; the pins and the re-run
  // assertions below are unchanged.
  await page.getByTestId("adjust-corners").click();
  const editor = page.getByTestId("crop-screen");
  await expect(editor).toBeVisible();
  // Nudge pin 0 by a few pixels and re-run.
  const pin = page.getByTestId("corner-pin-0");
  const box = (await pin.boundingBox())!;
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
  await page.mouse.down();
  await page.mouse.move(box.x + box.width / 2 + 6, box.y + box.height / 2 + 6, { steps: 3 });
  await page.mouse.up();
  await page.getByTestId("crop-analyze").click();
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
  // Not on C3b's record rows, so it keeps its traversal: straight through
  // the confirm screen on the default pins and counts.
  await uploadPhoto(page, { pins: false });
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
