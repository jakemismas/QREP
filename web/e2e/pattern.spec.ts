/**
 * Your pattern e2e (C2a, issue #96). DOM contract: see-sample (start
 * screen) and see-pattern (results) open your-pattern (data-source sample
 * or photo), which holds pattern-photo beside or above pattern-quilt
 * (data-zoomed), open-lightbox (Compare with your photo), method-line or
 * pattern-working while the summary loads, download-pattern (aria-busy,
 * data-state idle, busy, failed or refused), pattern-error with pattern-retry
 * (no Retry for a refusal), flagged-count (data-count) with flagged-hint and
 * flagged-toggle, and the census rows fabric-letter-<id> and
 * fabric-count-<id> inside fabric-census.
 *
 * The photos are generated at test runtime by the native renderer, as in
 * photo.spec.ts, under their own names: save_render writes the PNG and a
 * sidecar JSON whose "corners" are the quilt's outer corners in image
 * pixels (top left, top right, bottom right, bottom left), the order of
 * corner-pin-0 to corner-pin-3. Level 0 is the clean render; level 1 adds
 * fabric texture (qrep/render/renderer.py), so its read flags squares. Each
 * pinned test pins a render to its own sidecar.
 *
 * No screenshot or snapshot assertions; layout checks read element boxes.
 */
import { execFileSync } from "node:child_process";
import { existsSync, mkdirSync, readFileSync } from "node:fs";
import * as path from "node:path";
import { fileURLToPath } from "node:url";
import { devices, expect, test, type Download, type Page, type Route } from "@playwright/test";
import { expectNoHorizontalOverflow } from "./helpers/layout";

const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const generatedDir = path.join(repoRoot, "tests", "fixtures", "_generated");
const photoPath = path.join(generatedDir, "pattern_e2e_l0.png");
const sidecarPath = path.join(generatedDir, "pattern_e2e_l0.json");
const texturedPath = path.join(generatedDir, "pattern_e2e_l1.png");
const texturedSidecarPath = path.join(generatedDir, "pattern_e2e_l1.json");
const fixturePath = path.join(repoRoot, "tests", "fixtures", "double_irish_chain.json");
const READY_TIMEOUT = 300_000;
const REVERSE_TIMEOUT = 300_000;
const FAILED_TIMEOUT = 120_000;
const ENGINE_IMPORT = "**/pyodide/pyodide.mjs";
const ENGINE_FILES = "**/pyodide/**";
const SAMPLE_FILE = "**/fixtures/double_irish_chain.json";
const PHONE = { width: 390, height: 844 };
const iPhone = devices["iPhone 13"];
const DESKTOP_OPTIONS = { viewport: { width: 1440, height: 900 }, isMobile: false, hasTouch: false };

function renderFixture(level: number, file: string): void {
  mkdirSync(generatedDir, { recursive: true });
  const venvPython = path.join(repoRoot, ".venv", "Scripts", "python.exe");
  const python = process.env.QREP_PYTHON ?? (existsSync(venvPython) ? venvPython : "python");
  // Direct API call, as photo.spec.ts does: qrep.cli has no __main__ guard.
  execFileSync(python, [
    "-c",
    "import sys; from pathlib import Path; from qrep.model import load; from qrep.render import save_render; " +
      "save_render(load(sys.argv[1]), Path(sys.argv[2]), level=int(sys.argv[3]), seed=42, scale=10)",
    fixturePath,
    file,
    String(level),
  ]);
  if (!existsSync(file)) throw new Error(`fixture render at level ${level} produced no photo`);
}

test.beforeAll(() => {
  if (!existsSync(photoPath) || !existsSync(sidecarPath)) renderFixture(0, photoPath);
  if (!existsSync(sidecarPath)) throw new Error("fixture render produced no sidecar");
  if (!existsSync(texturedPath) || !existsSync(texturedSidecarPath)) renderFixture(1, texturedPath);
  if (!existsSync(texturedSidecarPath)) throw new Error("level 1 render produced no sidecar");
});

/** Width and height from the PNG's IHDR chunk (bytes 16 to 23, big endian). */
function pngSize(file: string): { width: number; height: number } {
  const bytes = readFileSync(file);
  return { width: bytes.readUInt32BE(16), height: bytes.readUInt32BE(20) };
}

/** A render's own sidecar: save_render writes it beside the PNG, same stem. */
function sidecarOf(photo: string): string {
  return photo.replace(/\.png$/, ".json");
}

/** The render's sidecar quilt corners as fractions of the photo, in pin order. */
function cornerFractions(photo: string): [number, number][] {
  const { width, height } = pngSize(photo);
  const sidecar = JSON.parse(readFileSync(sidecarOf(photo), "utf8")) as {
    corners: [number, number][];
  };
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

/** Open the fixture as a project file through the Open dialog. */
async function openFixtureFile(page: Page): Promise<void> {
  await page.getByTestId("open-project").click();
  await page.getByTestId("open-file-input").setInputFiles({
    name: "double_irish_chain.json",
    mimeType: "application/json",
    buffer: readFileSync(fixturePath),
  });
}

/** Upload a render and reach the results screen. With pins, set the four pins
 * on that render's own sidecar corners first; without, analyze where the
 * corner search put them, as photo.spec.ts does. */
async function photoToResults(page: Page, { photo = photoPath, pins = true } = {}): Promise<void> {
  await page.goto("./");
  await page.getByTestId("start-photo").click();
  await expect(page.getByTestId("photo-dropzone")).toBeVisible();
  await page.getByTestId("photo-file-input").setInputFiles(photo);
  const crop = page.getByTestId("crop-screen");
  await expect(crop).toBeVisible();
  // The box settles once the photo has loaded and the corner search has
  // finished (its status line sits above the box); a pin the search moves
  // after a drag would also undo that drag.
  await expect
    .poll(() => crop.locator("img.pf-corner-img").evaluate((img: HTMLImageElement) => img.naturalWidth))
    .toBeGreaterThan(0);
  await expect(page.getByTestId("crop-detecting")).toHaveCount(0, { timeout: REVERSE_TIMEOUT });
  if (pins) await pinCorners(page, photo);
  await page.getByTestId("crop-analyze").click();
  await expect(page.getByTestId("photo-results")).toBeVisible({ timeout: REVERSE_TIMEOUT });
}

/** Drag the four pins onto the render's own sidecar corners. */
async function pinCorners(page: Page, photo: string): Promise<void> {
  const crop = page.getByTestId("crop-screen");
  // PinOverlay places each pin at left/top percent of .pf-corner-box, and a
  // drag stores the pointer's fraction of that same box.
  const targets = cornerFractions(photo);
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
}

async function seePattern(page: Page): Promise<void> {
  await page.getByTestId("see-pattern").click();
  await expect(page.getByTestId("your-pattern")).toHaveAttribute("data-source", "photo");
}

/** Upload the render, set the four pins on its corners, analyze, open Your pattern. */
async function photoToPattern(page: Page): Promise<void> {
  await photoToResults(page);
  await seePattern(page);
}

/** The results screen leads with See your pattern and stays inside the viewport. */
async function expectResultsScreen(page: Page, name: string): Promise<void> {
  await expect(page.getByTestId("see-pattern")).toHaveClass(/\bpf-btn--primary\b/);
  await expect(page.getByTestId("open-in-editor")).toHaveClass(/\bpf-btn--secondary\b/);
  await expectNoHorizontalOverflow(page, name);
}

/** Your pattern shows a photo read with no confidence pill, meters or wording. */
async function expectNoConfidence(page: Page): Promise<void> {
  await expect(page.getByTestId("overall-pill")).toHaveCount(0);
  await expect(page.locator("[data-testid^='confidence-']")).toHaveCount(0);
  await expect(page.getByTestId("your-pattern")).not.toContainText(/confidence/i);
}

/** Record every engine call the page posts to its worker, from the first
 * page load on; read it back with `engineCalls`. */
async function recordEngineCalls(page: Page): Promise<void> {
  await page.addInitScript(() => {
    const calls: string[] = [];
    (window as unknown as { engineCalls: string[] }).engineCalls = calls;
    const post = Worker.prototype.postMessage;
    Worker.prototype.postMessage = function (this: Worker, ...args: unknown[]) {
      const message = args[0] as { type?: string; method?: string } | null;
      if (message?.type === "call" && message.method) calls.push(message.method);
      return (post as (...rest: unknown[]) => void).apply(this, args);
    } as typeof Worker.prototype.postMessage;
  });
}

/** How many calls of `method` the page has posted to its worker so far. */
function engineCalls(page: Page, method: string): Promise<number> {
  return page.evaluate(
    (wanted) =>
      (window as unknown as { engineCalls: string[] }).engineCalls.filter(
        (name) => name === wanted,
      ).length,
    method,
  );
}

interface SeenToast {
  tone: string;
  text: string;
}

/** Record every toast the page shows from now on. A new toast replaces the
 * one before it in the DOM, so a check on the toast showing at the end
 * cannot see an earlier one; a MutationObserver keeps them all. */
async function recordToasts(page: Page): Promise<void> {
  await page.evaluate(() => {
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
    new MutationObserver((mutations) => {
      for (const mutation of mutations) mutation.addedNodes.forEach(take);
    }).observe(document.body, { childList: true, subtree: true });
  });
}

function seenToasts(page: Page): Promise<SeenToast[]> {
  return page.evaluate(() => (window as unknown as { toastRecord: SeenToast[] }).toastRecord);
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
  await expectNoConfidence(page);
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
    // Data and object URLs, raw PNG bytes, and base64 PNG, JPEG and WebP.
    for (const marker of ["data:image", "blob:", "\x89PNG", "iVBORw0KGgo", "/9j/", "UklGR"]) {
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

  // Names are the fixture palette's; counts are the design doc's census
  // literals, each the element's whole text.
  const census = page.getByTestId("fabric-census");
  await expect(census).toContainText("Chain blue");
  await expect(census).toContainText("Background cream");
  await expect(page.getByTestId("fabric-count-b")).toHaveText(/^1,?246 squares$/);
  await expect(page.getByTestId("fabric-count-c")).toHaveText(/^1,?229 squares$/);
  // Each of the fixture's two fabrics shows a letter, and no two match. The
  // engine prints the fabric id as the letter until ticket A4b prints A, B
  // and C, so no test pins the letter text.
  const letters = census.locator("[data-testid^='fabric-letter-']");
  await expect(letters).toHaveCount(2);
  const letterTexts = (await letters.allTextContents()).map((text) => text.trim());
  expect(letterTexts.filter((text) => text.length === 0)).toEqual([]);
  expect(new Set(letterTexts).size).toBe(letterTexts.length);
  // No hex codes: the fixture colors are #9db8d9 and #f2e8d5, and no row
  // shows any color code at all.
  await expect(census).not.toContainText(/#|9db8d9|f2e8d5/i);
  const rows = await census.locator("li").allTextContents();
  expect(rows).toHaveLength(2);
  for (const row of rows) expect(row).not.toMatch(/#[0-9a-f]{3,8}\b|\b[0-9a-f]{6}\b/i);

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

// Both Retry buttons show while the engine is down and both restart it: Your
// pattern's (pattern-retry) and the header engine chip's (engine-retry), which
// calls engine.retry directly. Either one must bring Your pattern back.
for (const [retryName, retryId] of [
  ["Your pattern's Retry", "pattern-retry"],
  ["the header's engine Retry", "engine-retry"],
] as const) {
  test(`one click on ${retryName} after a failed engine boot brings the method, the census and a waiting PDF`, async ({
    page,
  }) => {
    await recordEngineCalls(page);
    // Abort every engine file, as app.spec.ts does: the boot fails, and the
    // calls queued meanwhile (the census, the summary, then the PDF) wait.
    await page.route(ENGINE_FILES, (route) => route.abort());
    await openSample(page);
    await recordToasts(page);
    const error = page.getByTestId("pattern-error");
    await expect(error).toBeVisible({ timeout: FAILED_TIMEOUT });
    await expect(error.locator(".yp-error-text")).toHaveText(
      "The pattern engine did not start, so your pattern is not ready yet.",
    );
    await expect(error).not.toContainText(/traceback|exception|pyodide/i);
    await expect(page.getByTestId("pattern-retry")).toBeVisible();
    await expect(page.getByTestId("engine-retry")).toBeVisible();
    // A working line or spinner beside the error would say the wait goes on.
    await expect(page.getByTestId("pattern-working")).toHaveCount(0);

    // Download while the engine is down: the PDF waits, without a spinner.
    const button = page.getByTestId("download-pattern");
    await button.click();
    await expect(button).toHaveAttribute("data-state", "busy");
    await expect(button).toHaveAttribute("aria-busy", "false");

    await page.unroute(ENGINE_FILES);
    const download = page.waitForEvent("download", { timeout: READY_TIMEOUT });
    await page.getByTestId(retryId).click();

    await expect(page.getByTestId("method-line")).toHaveText(
      "Blocks of 5 x 5 squares repeat across the quilt, so it is strip pieced.",
      { timeout: READY_TIMEOUT },
    );
    const saved = await download;
    // slugify("Double Irish Chain 75x90"), as in the sample test above.
    expect(saved.suggestedFilename()).toBe("double-irish-chain-75x90.pdf");
    // The design doc's census literal, the element's whole text: the census
    // the restart rejected was asked for again.
    await expect(page.getByTestId("fabric-count-b")).toHaveText(/^1,?246 squares$/, {
      timeout: READY_TIMEOUT,
    });
    await expect(button).toHaveAttribute("data-state", "idle");
    await expect(page.getByTestId("pattern-error")).toHaveCount(0);
    await expect(page.getByTestId("engine-chip")).toHaveAttribute("data-engine-phase", "ready");

    // Hand count: the failed worker never booted, so the client posted it
    // nothing; the restart rejected the waiting summary and the waiting PDF
    // once each, and each was sent once more: two pattern calls in all.
    expect(await engineCalls(page, "export_pattern")).toBe(2);

    // The restart is not news. Every toast from Your pattern's opening on
    // was recorded, and the only one is the saved file's success toast; no
    // raw engine message reached any toast.
    await expect.poll(() => seenToasts(page)).toEqual([
      { tone: "success", text: expect.stringContaining("Saved: your pattern file is ready.") },
    ]);
    for (const toast of await seenToasts(page)) {
      expect(toast.text).not.toMatch(/restarted|traceback|worker/i);
    }
  });
}

test("Download pattern (PDF) reports busy while it works and saves once for a double tap", async ({
  page,
}) => {
  await openSample(page);
  await waitForEngine(page);
  await expect(page.getByTestId("method-line")).toBeVisible();
  await expect(page.getByTestId("fabric-count-b")).toBeVisible();
  const button = page.getByTestId("download-pattern");
  await expect(button).toHaveAttribute("data-state", "idle");

  const downloads: Download[] = [];
  page.on("download", (download) => downloads.push(download));
  // A MutationObserver keeps every value the two attributes held, so the busy
  // state is seen however fast the export runs, and a click listener counts
  // the file saves the page starts (an anchor click with a download name).
  await button.evaluate((el) => {
    const record = { state: [] as string[], busy: [] as string[], saves: 0 };
    (window as unknown as { pdfRecord: typeof record }).pdfRecord = record;
    new MutationObserver((mutations) => {
      for (const mutation of mutations) {
        const list = mutation.attributeName === "data-state" ? record.state : record.busy;
        list.push(mutation.oldValue ?? "");
      }
    }).observe(el, {
      attributes: true,
      attributeOldValue: true,
      attributeFilter: ["data-state", "aria-busy"],
    });
    document.addEventListener(
      "click",
      (event) => {
        if (event.target instanceof HTMLAnchorElement && event.target.download) record.saves += 1;
      },
      true,
    );
  });

  const first = page.waitForEvent("download");
  // Two clicks in one task: the second lands before React renders the busy
  // state, the window a guard on the rendered state alone would miss.
  await button.evaluate((el: HTMLElement) => {
    el.click();
    el.click();
  });
  await first;
  await expect(button).toHaveAttribute("data-state", "idle");
  // The engine has nothing queued, so a second export cannot still be on its way.
  await expect(page.getByTestId("engine-chip")).toHaveAttribute("data-engine-phase", "ready");

  const record = await page.evaluate(
    () => (window as unknown as { pdfRecord: { state: string[]; busy: string[]; saves: number } })
      .pdfRecord,
  );
  // Each list holds the old values; the current one ends it. One busy spell:
  // idle, busy, idle, and aria-busy false, true, false.
  expect([...record.state, await button.getAttribute("data-state")]).toEqual([
    "idle",
    "busy",
    "idle",
  ]);
  expect([...record.busy, await button.getAttribute("aria-busy")]).toEqual([
    "false",
    "true",
    "false",
  ]);
  expect(record.saves).toBe(1);
  expect(downloads).toHaveLength(1);
});

test("a textured photo's flagged squares are counted, outlined, and can be hidden", async ({
  page,
}) => {
  // Pinned to the level 1 render's own sidecar corners, so the read's grid
  // is the quilt's and the flags come from the squares alone, not from where
  // a corner search happened to land.
  await photoToResults(page, { photo: texturedPath, pins: true });
  await seePattern(page);
  await expectNoConfidence(page);
  const flagged = page.getByTestId("flagged-count");
  await expect(flagged).toHaveAttribute("data-count", /^\d+$/);
  // Why above 0: the level 1 render adds texture to every square.
  // _apply_texture in qrep/render/renderer.py redraws each center square
  // with its own seeded tint of -6 to +6 per channel (rng.integers(-6, 7))
  // and then adds pixel noise of sigma 2.5 (rng.normal(0, 2.5)) over the
  // whole quilt, so some squares read below the 0.9 confidence mark
  // (UNCERTAIN_THRESHOLD in src/state/photo.tsx, PARITY item 6). The
  // property is a count above 0; the number itself is the reader's and is
  // not pinned here.
  expect(Number(await flagged.getAttribute("data-count"))).toBeGreaterThan(0);
  await expect(page.getByTestId("flagged-hint")).toBeVisible();
  await expect(flagged).not.toContainText(/download|install/i);
  const toggle = page.getByTestId("flagged-toggle");
  await expect(toggle).toHaveAttribute("aria-pressed", "true");
  await toggle.click();
  await expect(toggle).toHaveAttribute("aria-pressed", "false");
  await toggle.click();
  await expect(toggle).toHaveAttribute("aria-pressed", "true");
});

// Every start-screen entry that opens or starts something, the resume
// banner's Continue among them, besides See a sample pattern itself.
const START_ENTRIES = ["start-photo", "resume-accept", "open-demo", "start-blank", "open-project"];

/** Leave an autosave behind, so the start screen shows the resume banner. */
async function seedAutosave(page: Page): Promise<void> {
  await page.goto("./");
  const model = JSON.parse(readFileSync(fixturePath, "utf8")) as unknown;
  await page.evaluate((saved) => {
    localStorage.setItem(
      "qrep-autosave",
      JSON.stringify({
        app: "QREP",
        version: 1,
        name: "Saved quilt",
        savedAt: Date.now(),
        model: saved,
        ui: {},
      }),
    );
  }, model);
  await page.reload();
  await expect(page.getByTestId("resume-banner")).toBeVisible();
}

test("See a sample pattern holds every start entry while it loads, then shows the sample", async ({
  page,
}) => {
  await seedAutosave(page);
  // Hold the sample's file until the entries are checked, then let it load.
  const held: Route[] = [];
  await page.route(SAMPLE_FILE, (route) => {
    held.push(route);
  });
  const see = page.getByTestId("see-sample");
  await see.click();
  await expect(see).toBeDisabled();
  await expect(see).toHaveAttribute("aria-busy", "true");
  // No other quilt can open while the sample loads, so none can be replaced
  // by the sample when its file lands.
  for (const id of START_ENTRIES) await expect(page.getByTestId(id), id).toBeDisabled();
  await expect.poll(() => held.length).toBe(1);

  await held[0].continue();
  const screen = page.getByTestId("your-pattern");
  await expect(screen).toHaveAttribute("data-source", "sample");
  await expect(page.getByTestId("start-screen")).toHaveCount(0);
  // The fixture's method line, as in the sample test above.
  await expect(page.getByTestId("method-line")).toHaveText(
    "Blocks of 5 x 5 squares repeat across the quilt, so it is strip pieced.",
    { timeout: READY_TIMEOUT },
  );
});

test("after a failed sample load the button works again and the next open goes to the editor", async ({
  page,
}) => {
  await seedAutosave(page);
  await page.route(SAMPLE_FILE, (route) => route.abort(), { times: 1 });
  const see = page.getByTestId("see-sample");
  await see.click();
  await expect(page.getByTestId("toast")).toHaveAttribute("data-tone", "error");
  await expect(see).toBeEnabled();
  await expect(see).toHaveAttribute("aria-busy", "false");
  for (const id of START_ENTRIES) await expect(page.getByTestId(id), id).toBeEnabled();
  await expect(page.getByTestId("start-screen")).toBeVisible();

  await page.getByTestId("open-demo").click();
  await expect(page.getByTestId("editor")).toBeVisible();
  await expect(page.getByTestId("your-pattern")).toHaveCount(0);
});

test("leaving Your pattern through Open sends no pattern call for the quilt that goes to the editor", async ({
  page,
}) => {
  await recordEngineCalls(page);
  const patternCalls = () => engineCalls(page, "export_pattern");

  await openSample(page);
  await waitForEngine(page);
  await expect(page.getByTestId("method-line")).toBeVisible();
  await expect(page.getByTestId("fabric-count-b")).toBeVisible();
  // The summary is the one pattern call so far.
  expect(await patternCalls()).toBe(1);

  await openFixtureFile(page);
  await expect(page.getByTestId("editor")).toBeVisible();
  // A fresh open drops the census, so its count shows again only once the
  // opened quilt's validate returns; the client posts its next queued call
  // before that result reaches the page, so any pattern call is out by then.
  // The editor adds " + borders" to a fabric the borders use.
  await expect(page.getByTestId("fabric-count-b")).toHaveText(
    /^1,?246 squares( \+ borders)?$/,
  );
  await expect(page.getByTestId("engine-chip")).toHaveAttribute("data-engine-phase", "ready");
  expect(await patternCalls()).toBe(1);
});

test.describe("Your pattern at 1440 x 900", { tag: "@phone" }, () => {
  test.use(DESKTOP_OPTIONS);

  test("the quilt sits beside the photo from 720 px, stacks below it on a phone, and Compare opens the lightbox", async ({
    page,
  }) => {
    await photoToResults(page);
    await expectResultsScreen(page, "photo-results");
    await seePattern(page);
    await expectNoConfidence(page);
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
    // The attribute must be there: Number(null) is 0 and would pass.
    const flagged = page.getByTestId("flagged-count");
    await expect(flagged).toBeVisible();
    await expect(flagged).toHaveAttribute("data-count", /^\d+$/);
    const count = Number(await flagged.getAttribute("data-count"));
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

  test("the results screen stays inside the phone and leads with See your pattern", async ({
    page,
  }) => {
    await photoToResults(page, { pins: false });
    await expectResultsScreen(page, "photo-results");
  });

  // Fingers spread across, up and down, and on a diagonal: the page keeps a
  // vertical one-finger drag at Fit, and a pinch must not read as one.
  for (const [way, dx, dy] of [
    ["across", 1, 0],
    ["up and down", 0, 1],
    ["on a diagonal", Math.SQRT1_2, Math.SQRT1_2],
  ] as const) {
    test(`a two-finger pinch ${way} on the quilt at Fit zooms it`, async ({ page }) => {
      await openSample(page);
      const quilt = page.getByTestId("pattern-quilt");
      const canvas = page.getByTestId("quilt-canvas");
      await expect(quilt).toHaveAttribute("data-zoomed", "false");
      await expect(canvas).toHaveAttribute("data-view-scale", /\d/);
      const scaleAtFit = Number(await canvas.getAttribute("data-view-scale"));
      const cdp = await page.context().newCDPSession(page);

      const box = (await canvas.boundingBox())!;
      const innerHeight = await page.evaluate(() => window.innerHeight);
      const x = box.x + box.width / 2;
      // Inside both the canvas and the viewport, with room for the spread.
      const y = Math.min(box.y + box.height / 2, innerHeight - 140);
      // Two fingers land together 40 px apart and spread to 200 px apart.
      const fingers = (gap: number) => [
        { x: x - (dx * gap) / 2, y: y - (dy * gap) / 2, id: 0 },
        { x: x + (dx * gap) / 2, y: y + (dy * gap) / 2, id: 1 },
      ];
      await cdp.send("Input.dispatchTouchEvent", { type: "touchStart", touchPoints: fingers(40) });
      for (let step = 1; step <= 10; step++) {
        await cdp.send("Input.dispatchTouchEvent", {
          type: "touchMove",
          touchPoints: fingers(40 + step * 16),
        });
      }
      await cdp.send("Input.dispatchTouchEvent", { type: "touchEnd", touchPoints: [] });

      await expect(quilt).toHaveAttribute("data-zoomed", "true");
      await expect
        .poll(async () => Number(await canvas.getAttribute("data-view-scale")))
        .toBeGreaterThan(scaleAtFit);
    });
  }

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
