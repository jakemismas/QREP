/**
 * Your pattern e2e (C2a, issue #96). DOM contract: see-sample (start
 * screen) and see-pattern (results) open your-pattern (data-source sample
 * or photo), which holds pattern-photo beside or above pattern-quilt
 * (data-zoomed), open-lightbox (Compare with your photo), method-line or
 * pattern-working while the summary loads, download-pattern (aria-busy,
 * data-state idle, busy or failed), pattern-error with pattern-retry,
 * flagged-count (data-count) with flagged-toggle, and the census rows
 * fabric-letter-<id> and fabric-count-<id> inside fabric-census.
 *
 * The photo is generated at test runtime by the native renderer, as in
 * photo.spec.ts, under its own name: save_render writes the PNG and a
 * sidecar JSON whose "corners" are the quilt's outer corners in image
 * pixels (top left, top right, bottom right, bottom left), the order of
 * corner-pin-0 to corner-pin-3.
 *
 * No screenshot or snapshot assertions; layout checks read element boxes.
 */
import { execFileSync } from "node:child_process";
import { existsSync, mkdirSync, readFileSync } from "node:fs";
import * as path from "node:path";
import { fileURLToPath } from "node:url";
import { devices, expect, test, type Download, type Page } from "@playwright/test";
import { expectNoHorizontalOverflow } from "./helpers/layout";

const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const generatedDir = path.join(repoRoot, "tests", "fixtures", "_generated");
const photoPath = path.join(generatedDir, "pattern_e2e_l0.png");
const sidecarPath = path.join(generatedDir, "pattern_e2e_l0.json");
const READY_TIMEOUT = 300_000;
const REVERSE_TIMEOUT = 300_000;
const ENGINE_IMPORT = "**/pyodide/pyodide.mjs";
const PHONE = { width: 390, height: 844 };
const iPhone = devices["iPhone 13"];
const DESKTOP_OPTIONS = { viewport: { width: 1440, height: 900 }, isMobile: false, hasTouch: false };

test.beforeAll(() => {
  if (existsSync(photoPath) && existsSync(sidecarPath)) return;
  mkdirSync(generatedDir, { recursive: true });
  const venvPython = path.join(repoRoot, ".venv", "Scripts", "python.exe");
  const python = process.env.QREP_PYTHON ?? (existsSync(venvPython) ? venvPython : "python");
  // Direct API call, as photo.spec.ts does: qrep.cli has no __main__ guard.
  execFileSync(python, [
    "-c",
    "import sys; from pathlib import Path; from qrep.model import load; from qrep.render import save_render; " +
      "save_render(load(sys.argv[1]), Path(sys.argv[2]), level=0, seed=42, scale=10)",
    path.join(repoRoot, "tests", "fixtures", "double_irish_chain.json"),
    photoPath,
  ]);
  if (!existsSync(photoPath) || !existsSync(sidecarPath)) {
    throw new Error("fixture render produced no photo or no sidecar");
  }
});

/** Width and height from the PNG's IHDR chunk (bytes 16 to 23, big endian). */
function pngSize(file: string): { width: number; height: number } {
  const bytes = readFileSync(file);
  return { width: bytes.readUInt32BE(16), height: bytes.readUInt32BE(20) };
}

/** The sidecar's quilt corners as fractions of the photo, in pin order. */
function cornerFractions(): [number, number][] {
  const { width, height } = pngSize(photoPath);
  const sidecar = JSON.parse(readFileSync(sidecarPath, "utf8")) as { corners: [number, number][] };
  return sidecar.corners.map(([x, y]) => [x / width, y / height]);
}

async function openSample(page: Page): Promise<void> {
  await page.goto("./");
  await page.getByTestId("see-sample").click();
  await expect(page.getByTestId("your-pattern")).toBeVisible();
}

async function waitForEngine(page: Page): Promise<void> {
  await expect(page.getByTestId("engine-chip")).toHaveAttribute("data-engine-phase", "ready", {
    timeout: READY_TIMEOUT,
  });
}

/** Upload the render, set the four pins on its corners, analyze, open Your pattern. */
async function photoToPattern(page: Page): Promise<void> {
  await page.goto("./");
  await page.getByTestId("start-photo").click();
  await expect(page.getByTestId("photo-dropzone")).toBeVisible();
  await page.getByTestId("photo-file-input").setInputFiles(photoPath);
  const crop = page.getByTestId("crop-screen");
  await expect(crop).toBeVisible();
  // The box settles once the photo has loaded and the corner search has
  // finished (its status line sits above the box); a pin the search moves
  // after a drag would also undo that drag.
  await expect
    .poll(() => crop.locator("img.pf-corner-img").evaluate((img: HTMLImageElement) => img.naturalWidth))
    .toBeGreaterThan(0);
  await expect(page.getByTestId("crop-detecting")).toHaveCount(0, { timeout: REVERSE_TIMEOUT });
  // PinOverlay places each pin at left/top percent of .pf-corner-box, and a
  // drag stores the pointer's fraction of that same box.
  const targets = cornerFractions();
  for (const [index, [fx, fy]] of targets.entries()) {
    const box = (await crop.locator(".pf-corner-box").boundingBox())!;
    const pin = page.getByTestId(`corner-pin-${index}`);
    const pinBox = (await pin.boundingBox())!;
    await page.mouse.move(pinBox.x + pinBox.width / 2, pinBox.y + pinBox.height / 2);
    await page.mouse.down();
    await page.mouse.move(box.x + fx * box.width, box.y + fy * box.height, { steps: 4 });
    await page.mouse.up();
  }
  for (const [index, [fx, fy]] of targets.entries()) {
    const style = (await page.getByTestId(`corner-pin-${index}`).getAttribute("style")) ?? "";
    const left = Number(/left:\s*([\d.]+)%/.exec(style)?.[1]);
    const top = Number(/top:\s*([\d.]+)%/.exec(style)?.[1]);
    // A drag lands within a pixel of its target; the box is at least 300 px.
    expect(Math.abs(left / 100 - fx), `pin ${index} left`).toBeLessThan(0.005);
    expect(Math.abs(top / 100 - fy), `pin ${index} top`).toBeLessThan(0.005);
  }
  await page.getByTestId("crop-analyze").click();
  await expect(page.getByTestId("photo-results")).toBeVisible({ timeout: REVERSE_TIMEOUT });
  await page.getByTestId("see-pattern").click();
  await expect(page.getByTestId("your-pattern")).toHaveAttribute("data-source", "photo");
}

async function savePattern(page: Page): Promise<{ bytes: Buffer; name: string }> {
  const waiting = page.waitForEvent("download");
  await page.getByTestId("download-pattern").click();
  const download: Download = await waiting;
  const stream = await download.createReadStream();
  const chunks: Buffer[] = [];
  for await (const chunk of stream) chunks.push(Buffer.from(chunk as Buffer));
  return { bytes: Buffer.concat(chunks), name: download.suggestedFilename() };
}

test("a photo becomes a pattern PDF with only GET requests and no stored photo", async ({
  page,
}) => {
  const requests: string[] = [];
  page.on("request", (request) => requests.push(`${request.method()} ${request.url()}`));

  await photoToPattern(page);
  await waitForEngine(page);
  const pdf = await savePattern(page);
  expect(pdf.bytes.subarray(0, 5).toString("latin1")).toBe("%PDF-");

  // Nothing leaves the browser: every request from the first page load to
  // the saved file only reads.
  expect(requests.length).toBeGreaterThan(0);
  expect(requests.filter((line) => !line.startsWith("GET "))).toEqual([]);

  // No photo data in any browser storage. IndexedDB holds no database at
  // all, which is stricter than scanning one for the markers below.
  const stored = await page.evaluate(async () => {
    const values: string[] = [];
    for (const store of [localStorage, sessionStorage]) {
      for (let i = 0; i < store.length; i++) {
        const key = store.key(i) ?? "";
        values.push(`${key}=${store.getItem(key) ?? ""}`);
      }
    }
    const databases = await indexedDB.databases();
    return { values, databases: databases.map((db) => db.name ?? "") };
  });
  for (const value of stored.values) {
    for (const marker of ["data:image", "blob:", "iVBORw0KGgo", "/9j/"]) {
      expect(value, `stored value holds ${marker}`).not.toContain(marker);
    }
  }
  expect(stored.databases).toEqual([]);
});

test("See a sample pattern shows the method, the census and no photo, and saves the PDF by name", async ({
  page,
}) => {
  await openSample(page);
  const screen = page.getByTestId("your-pattern");
  await expect(screen).toHaveAttribute("data-source", "sample");
  await waitForEngine(page);

  // qrep/export/pattern.py:50 with the fixture's block size: 55 rows and 45
  // columns share gcd 5, the only period tried, and the fixture's two
  // 5 x 5 block types repeat, so the method is strip piecing.
  await expect(page.getByTestId("method-line")).toHaveText(
    "Blocks of 5 x 5 squares repeat across the quilt, so it is strip pieced.",
  );
  await expect(page.getByTestId("pattern-working")).toHaveCount(0);

  // Interim letters equal the fabric ids (qrep/export/pattern.py); names are
  // the fixture palette's; counts are the design doc's census literals.
  const census = page.getByTestId("fabric-census");
  await expect(page.getByTestId("fabric-letter-b")).toHaveText("b");
  await expect(page.getByTestId("fabric-letter-c")).toHaveText("c");
  await expect(census).toContainText("Chain blue");
  await expect(census).toContainText("Background cream");
  await expect(page.getByTestId("fabric-count-b")).toHaveText(/1,?246 squares/);
  await expect(page.getByTestId("fabric-count-c")).toHaveText(/1,?229 squares/);
  // No hex codes: the fixture colors are #9db8d9 and #f2e8d5.
  await expect(census).not.toContainText(/#|9db8d9|f2e8d5/i);

  // No photo, so no photo panel, no Compare and no flagged line; no
  // strategy cards, metrics, confidence pill or stage meters.
  await expect(page.getByTestId("pattern-photo")).toHaveCount(0);
  await expect(page.getByTestId("open-lightbox")).toHaveCount(0);
  await expect(page.getByTestId("flagged-count")).toHaveCount(0);
  await expect(page.locator("[data-testid^='strategy-card-']")).toHaveCount(0);
  await expect(page.locator("[data-testid^='confidence-']")).toHaveCount(0);
  await expect(page.getByTestId("overall-pill")).toHaveCount(0);
  await expect(screen).not.toContainText(/difficulty|minutes|\bpieces\b|confidence/i);

  const pdf = await savePattern(page);
  // slugify("Double Irish Chain 75x90"): lowercase, then each run of
  // characters outside a-z and 0-9 becomes one hyphen.
  expect(pdf.name).toBe("double-irish-chain-75x90.pdf");
  expect(pdf.bytes.subarray(0, 5).toString("latin1")).toBe("%PDF-");
  await expect(page.getByTestId("toast")).toHaveAttribute("data-tone", "success");
  await expect(page.getByTestId("download-pattern")).toHaveAttribute("data-state", "idle");
  await expect(page.getByTestId("pattern-error")).toHaveCount(0);
});

test("the sample shows at once and says it is working until the engine is ready", async ({
  context,
  page,
}) => {
  // Hold the engine import open: the quilt renders without the engine, and
  // the loading line stands in for the method meanwhile.
  await context.route(ENGINE_IMPORT, () => {});
  await openSample(page);
  await expect(page.getByTestId("quilt-canvas")).toBeVisible();
  const working = page.getByTestId("pattern-working");
  await expect(working).toBeVisible();
  await expect(working).not.toHaveText(/download|install/i);
  await expect(page.getByTestId("method-line")).toHaveCount(0);
  await expect(page.getByTestId("download-pattern")).toBeVisible();
});

test.describe("Your pattern at 1440 x 900", { tag: "@phone" }, () => {
  test.use(DESKTOP_OPTIONS);

  test("the quilt sits beside the photo from 720 px, stacks below it on a phone, and Compare opens the lightbox", async ({
    page,
  }) => {
    await photoToPattern(page);
    const photo = page.getByTestId("pattern-photo");
    const quilt = page.getByTestId("pattern-quilt");
    await expect(photo).toBeVisible();
    await expect(quilt).toBeVisible();

    for (const width of [1440, 720]) {
      await page.setViewportSize({ width, height: 900 });
      const p = (await photo.boundingBox())!;
      const q = (await quilt.boundingBox())!;
      expect(q.x, `${width}: quilt starts right of the photo`).toBeGreaterThanOrEqual(p.x + p.width);
      expect(q.y, `${width}: quilt starts above the photo's foot`).toBeLessThan(p.y + p.height);
    }
    await page.setViewportSize({ width: 1440, height: 900 });
    await expectNoHorizontalOverflow(page, "your-pattern-photo");

    await page.setViewportSize(PHONE);
    {
      const p = (await photo.boundingBox())!;
      const q = (await quilt.boundingBox())!;
      expect(q.y, "390: quilt starts below the photo").toBeGreaterThanOrEqual(p.y + p.height);
    }
    await page.setViewportSize({ width: 1440, height: 900 });

    // Flagged squares come from the read: a whole count, outlined by default.
    const flagged = page.getByTestId("flagged-count");
    await expect(flagged).toBeVisible();
    const count = Number(await flagged.getAttribute("data-count"));
    expect(Number.isInteger(count) && count >= 0).toBe(true);
    if (count > 0) {
      await expect(page.getByTestId("flagged-toggle")).toHaveAttribute("aria-pressed", "true");
    }

    await page.getByTestId("open-lightbox").click();
    await expect(page.getByTestId("lightbox")).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(page.getByTestId("lightbox")).toHaveCount(0);
  });

  test("the sample pattern stays inside the desktop", async ({ page }) => {
    await openSample(page);
    await waitForEngine(page);
    await expect(page.getByTestId("fabric-count-b")).toBeVisible();
    await expectNoHorizontalOverflow(page, "your-pattern-sample");
  });
});

test.describe("Your pattern on a short desktop", { tag: "@phone" }, () => {
  test.use({ ...DESKTOP_OPTIONS, viewport: { width: 1440, height: 360 } });

  test("the quilt stays in view while the side column scrolls", async ({ page }) => {
    await openSample(page);
    await waitForEngine(page);
    await expect(page.getByTestId("fabric-count-c")).toBeVisible();
    const canvas = page.getByTestId("quilt-canvas");
    const headerBottom = await page
      .locator(".qrep-header")
      .evaluate((el) => el.getBoundingClientRect().bottom);
    const atRest = (await canvas.boundingBox())!;

    await page.evaluate(() => window.scrollTo(0, document.documentElement.scrollHeight));
    await expect.poll(() => page.evaluate(() => window.scrollY)).toBeGreaterThan(0);
    const scrolled = await page.evaluate(() => window.scrollY);
    // The page scrolls far enough that a quilt left in the flow would slide
    // under the sticky header.
    expect(scrolled, "scroll distance").toBeGreaterThan(atRest.y - headerBottom);

    const box = (await canvas.boundingBox())!;
    const innerHeight = await page.evaluate(() => window.innerHeight);
    expect(box.y, "canvas top below the header").toBeGreaterThanOrEqual(headerBottom);
    expect(box.y + box.height, "canvas foot inside the viewport").toBeLessThanOrEqual(innerHeight);
  });
});

test.describe("Your pattern at 390 x 844 (iPhone emulation)", { tag: "@phone" }, () => {
  test.use({
    viewport: PHONE,
    userAgent: iPhone.userAgent,
    deviceScaleFactor: iPhone.deviceScaleFactor,
    isMobile: iPhone.isMobile,
    hasTouch: iPhone.hasTouch,
  });

  test("Download pattern (PDF) is on screen without scrolling, above the census", async ({
    page,
  }) => {
    await openSample(page);
    await waitForEngine(page);
    await expect(page.getByTestId("fabric-count-b")).toBeVisible();
    await expect(page.getByTestId("method-line")).toBeVisible();
    expect(await page.evaluate(() => window.scrollY)).toBe(0);
    const button = page.getByTestId("download-pattern");
    await expect(button).toBeInViewport({ ratio: 1 });
    const buttonBox = (await button.boundingBox())!;
    const censusBox = (await page.getByTestId("fabric-census").boundingBox())!;
    expect(buttonBox.y + buttonBox.height).toBeLessThanOrEqual(censusBox.y);
    // The full guard waits for the header: with a quilt open its Open and
    // Save buttons still push it past 390 px (web-02), which C6a fixes along
    // with the editor. The screen's own content must fit meanwhile.
    const fit = await page.getByTestId("your-pattern").evaluate((root) => ({
      right: root.getBoundingClientRect().right,
      scrollWidth: root.scrollWidth,
      clientWidth: root.clientWidth,
    }));
    expect(fit.right).toBeLessThanOrEqual(PHONE.width);
    expect(fit.scrollWidth).toBeLessThanOrEqual(fit.clientWidth);
  });

  test("a one-finger drag scrolls the page at Fit and pans the quilt once zoomed", async ({
    page,
  }) => {
    await openSample(page);
    const quilt = page.getByTestId("pattern-quilt");
    const canvas = page.getByTestId("quilt-canvas");
    await expect(quilt).toHaveAttribute("data-zoomed", "false");
    const cdp = await page.context().newCDPSession(page);

    const drag = async () => {
      const box = (await canvas.boundingBox())!;
      const innerHeight = await page.evaluate(() => window.innerHeight);
      const x = box.x + box.width / 2;
      // Start inside both the canvas and the viewport, then move up 240 px.
      const startY = Math.min(box.y + box.height - 20, innerHeight - 40);
      await cdp.send("Input.dispatchTouchEvent", {
        type: "touchStart",
        touchPoints: [{ x, y: startY }],
      });
      for (let step = 1; step <= 12; step++) {
        await cdp.send("Input.dispatchTouchEvent", {
          type: "touchMove",
          touchPoints: [{ x, y: startY - step * 20 }],
        });
      }
      await cdp.send("Input.dispatchTouchEvent", { type: "touchEnd", touchPoints: [] });
    };
    const scrollY = () => page.evaluate(() => window.scrollY);

    // At Fit the drag belongs to the page.
    expect(await scrollY()).toBe(0);
    await drag();
    await expect.poll(scrollY).toBeGreaterThan(0);
    await expect(quilt).toHaveAttribute("data-zoomed", "false");

    // Zoomed in, the same drag pans the quilt and leaves the page still.
    await quilt.getByRole("button", { name: "Zoom in" }).click();
    await expect(quilt).toHaveAttribute("data-zoomed", "true");
    // Let any fling from the first drag finish before measuring.
    let last = -1;
    await expect
      .poll(async () => {
        const now = await scrollY();
        const settled = now === last;
        last = now;
        return settled;
      })
      .toBe(true);
    const before = await scrollY();
    const originBefore = await canvas.getAttribute("data-view-origin-y");
    await drag();
    await expect.poll(() => canvas.getAttribute("data-view-origin-y")).not.toBe(originBefore);
    expect(await scrollY()).toBe(before);
  });
});
