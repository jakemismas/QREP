/**
 * Confirm screen e2e (C3b, issue #101). DOM contract: the dropzone
 * (photo-dropzone, aria-busy while a file decodes; photo-file-input and its
 * accept list; photo-decoding; photo-error, role alert; capture-tips) and the
 * confirm screen (crop-screen, whose data-canvas-width and data-canvas-height
 * are the decoded size; corner-pin-0 to corner-pin-3, top left, top right,
 * bottom right and bottom left, whose data-x and data-y are source pixels;
 * pin-image; counts-<across|down>-<blocks|squares>; band-add and
 * band-<k>-width and band-<k>-inches, or bands-inches-off while no square
 * size is known; size-block; confirm-bar with crop-back and crop-analyze, the
 * Continue button, and crop-blocked, why Continue is off). From results,
 * adjust-corners returns to the confirm screen.
 *
 * Staging is watched where it leaves the page: an init script wraps
 * Worker.prototype.postMessage, as pattern.spec.ts does, and keeps a copy of
 * the PNG bytes of every stage_photo call, the options of every reverse_photo
 * call and the time of every detect_quad call, each with performance.now().
 * The bytes are decoded and hashed in the page.
 *
 * No input image is committed here. The level 0 render comes from the native
 * renderer at test runtime under this spec's own name (save_render also
 * writes its sidecar, whose "corners" are the quilt's outer corners), and
 * the JPEGs and the phone screenshot are drawn on a canvas in the page. The
 * screenshot fixture is the committed photoreal one.
 *
 * Every expected number is worked by hand in a comment next to its assertion.
 */
import { execFileSync } from "node:child_process";
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import * as os from "node:os";
import * as path from "node:path";
import { fileURLToPath } from "node:url";
import { devices, expect, test, type BrowserContextOptions, type Page } from "@playwright/test";
import { expectNoHorizontalOverflow } from "./helpers/layout";

const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const generatedDir = path.join(repoRoot, "tests", "fixtures", "_generated");
const l0Path = path.join(generatedDir, "confirm_e2e_l0.png");
const l0SidecarPath = path.join(generatedDir, "confirm_e2e_l0.json");
const screenshotPath = path.join(repoRoot, "tests", "fixtures", "photoreal", "screenshot_composite_1400.png");
const screenshotSidecarPath = screenshotPath.replace(/\.png$/, ".json");
const outDir = path.join(repoRoot, "web", "test-results", "confirm");
const READY_TIMEOUT = 300_000;
const REVERSE_TIMEOUT = 300_000;
// Generous: the 48 MP photo is decoded twice (createImageBitmap and the img
// element) and cut at full resolution, and a CI runner is many times slower
// than a desktop.
const BIG_PHOTO_TIMEOUT = 180_000;
const ENGINE_IMPORT = "**/pyodide/pyodide.mjs";
const PHONE = { width: 390, height: 844 };
const DESKTOP = { width: 1440, height: 900 };
const iPhone = devices["iPhone 13"];

interface Point {
  x: number;
  y: number;
}

// The two windows of the layout criteria, as layout.spec.ts runs them: the
// phone with the iPhone 13 descriptor, the desktop with touch off.
const VIEWS: { name: string; size: { width: number; height: number }; options: BrowserContextOptions }[] = [
  {
    name: "phone",
    size: PHONE,
    options: {
      viewport: PHONE,
      userAgent: iPhone.userAgent,
      deviceScaleFactor: iPhone.deviceScaleFactor,
      isMobile: iPhone.isMobile,
      hasTouch: iPhone.hasTouch,
    },
  },
  { name: "desktop", size: DESKTOP, options: { viewport: DESKTOP, isMobile: false, hasTouch: false } },
];

test.use({ viewport: DESKTOP });

test.beforeAll(() => {
  if (existsSync(l0Path) && existsSync(l0SidecarPath)) return;
  mkdirSync(generatedDir, { recursive: true });
  const venvPython = path.join(repoRoot, ".venv", "Scripts", "python.exe");
  const python = process.env.QREP_PYTHON ?? (existsSync(venvPython) ? venvPython : "python");
  // Direct API call, as photo.spec.ts does: qrep.cli has no __main__ guard.
  execFileSync(python, [
    "-c",
    "import sys; from pathlib import Path; from qrep.model import load; from qrep.render import save_render; " +
      "save_render(load(sys.argv[1]), Path(sys.argv[2]), level=0, seed=42, scale=10)",
    path.join(repoRoot, "tests", "fixtures", "double_irish_chain.json"),
    l0Path,
  ]);
  if (!existsSync(l0Path) || !existsSync(l0SidecarPath)) throw new Error("the level 0 render produced no photo or sidecar");
});

/** A sidecar's outer corners in pin order: save_render writes "corners", the photoreal generator "quad". */
function sidecarCorners(file: string): Point[] {
  const sidecar = JSON.parse(readFileSync(file, "utf8")) as { corners?: [number, number][]; quad?: [number, number][] };
  const corners = sidecar.corners ?? sidecar.quad;
  if (!corners) throw new Error(`${file} has no corners`);
  return corners.map(([x, y]) => ({ x, y }));
}

// ---- Watching staging -------------------------------------------------------

interface StagingRecord {
  staged: { bytes: Uint8Array<ArrayBuffer>; at: number }[];
  reads: { options: string; at: number }[];
  quads: { at: number }[];
}

interface ReadOptions {
  corners: [number, number][];
  crop_offset: Point;
}

/** Keeps every stage_photo, reverse_photo and detect_quad call the page posts to its worker, from the first load on. */
async function watchStaging(page: Page): Promise<void> {
  await page.addInitScript(() => {
    const record: StagingRecord = { staged: [], reads: [], quads: [] };
    (window as unknown as { stagingRecord: StagingRecord }).stagingRecord = record;
    const post = Worker.prototype.postMessage;
    Worker.prototype.postMessage = function (this: Worker, ...args: unknown[]) {
      const message = args[0] as { type?: string; method?: string; args?: unknown[] } | null;
      if (message?.type === "call" && message.method === "stage_photo") {
        // A copy, so the record holds these bytes whatever the client later does with its own.
        record.staged.push({ bytes: new Uint8Array(message.args?.[0] as Uint8Array), at: performance.now() });
      } else if (message?.type === "call" && message.method === "reverse_photo") {
        record.reads.push({ options: String(message.args?.[1]), at: performance.now() });
      } else if (message?.type === "call" && message.method === "detect_quad") {
        record.quads.push({ at: performance.now() });
      }
      return (post as (...rest: unknown[]) => void).apply(this, args);
    } as typeof Worker.prototype.postMessage;
  });
}

function stagingCounts(page: Page): Promise<{ staged: number; reads: number }> {
  return page.evaluate(() => {
    const record = (window as unknown as { stagingRecord: StagingRecord }).stagingRecord;
    return { staged: record.staged.length, reads: record.reads.length };
  });
}

/** How many detect_quad calls the page has posted: criteria U3-4 allows none. */
function detectQuadCalls(page: Page): Promise<number> {
  return page.evaluate(() => (window as unknown as { stagingRecord: StagingRecord }).stagingRecord.quads.length);
}

/** One staged PNG decoded in the page: its size, its SHA-256 and when it was posted. */
function stagedPhoto(page: Page, index: number): Promise<{ width: number; height: number; sha256: string; at: number }> {
  return page.evaluate(async (i) => {
    const entry = (window as unknown as { stagingRecord: StagingRecord }).stagingRecord.staged.at(i);
    if (!entry) throw new Error(`no stage_photo call at ${i}`);
    const bitmap = await createImageBitmap(new Blob([entry.bytes], { type: "image/png" }));
    const digest = new Uint8Array(await crypto.subtle.digest("SHA-256", entry.bytes));
    const sha256 = [...digest].map((byte) => byte.toString(16).padStart(2, "0")).join("");
    const size = { width: bitmap.width, height: bitmap.height };
    bitmap.close();
    return { ...size, sha256, at: entry.at };
  }, index);
}

/** The RGBA of a staged PNG at each point. */
function stagedPixels(page: Page, index: number, points: Point[]): Promise<number[][]> {
  return page.evaluate(
    async ({ i, at }) => {
      const entry = (window as unknown as { stagingRecord: StagingRecord }).stagingRecord.staged.at(i);
      if (!entry) throw new Error(`no stage_photo call at ${i}`);
      const bitmap = await createImageBitmap(new Blob([entry.bytes], { type: "image/png" }));
      const canvas = document.createElement("canvas");
      canvas.width = bitmap.width;
      canvas.height = bitmap.height;
      const ctx = canvas.getContext("2d")!;
      ctx.drawImage(bitmap, 0, 0);
      bitmap.close();
      return at.map((p) => [...ctx.getImageData(p.x, p.y, 1, 1).data]);
    },
    { i: index, at: points },
  );
}

/** One reverse_photo call's corners and crop offset, and when it was posted. */
function readCall(page: Page, index: number): Promise<ReadOptions & { at: number }> {
  return page.evaluate((i) => {
    const entry = (window as unknown as { stagingRecord: StagingRecord }).stagingRecord.reads.at(i);
    if (!entry) throw new Error(`no reverse_photo call at ${i}`);
    const options = JSON.parse(entry.options) as ReadOptions;
    return { corners: options.corners, crop_offset: options.crop_offset, at: entry.at };
  }, index);
}

// ---- Generated photos -------------------------------------------------------

interface Scene {
  width: number;
  height: number;
  type: "image/jpeg" | "image/png";
  background: string;
  rects?: { x: number; y: number; w: number; h: number; color: string }[];
  /** A checkerboard of cols x rows cells of cell px from (left, top). */
  grid?: { left: number; top: number; cell: number; cols: number; rows: number; colors: [string, string] };
  /** Seeded color noise tiled over everything at alpha, so a JPEG carries a photo's entropy, not a flat chart's. */
  noise?: { tile: number; alpha: number; seed: number };
  /** Also keeps the encoded file in the page as window.keptPhotos[keep], for chooseInPage. */
  keep?: string;
}

/** Draws a scene on a canvas in the page and returns the encoded file. */
async function drawInPage(page: Page, scene: Scene): Promise<Buffer> {
  const base64 = await page.evaluate(async (s) => {
    const canvas = document.createElement("canvas");
    canvas.width = s.width;
    canvas.height = s.height;
    const ctx = canvas.getContext("2d")!;
    ctx.fillStyle = s.background;
    ctx.fillRect(0, 0, s.width, s.height);
    for (const r of s.rects ?? []) {
      ctx.fillStyle = r.color;
      ctx.fillRect(r.x, r.y, r.w, r.h);
    }
    const g = s.grid;
    if (g) {
      for (let row = 0; row < g.rows; row++) {
        for (let col = 0; col < g.cols; col++) {
          ctx.fillStyle = g.colors[(row + col) % 2];
          ctx.fillRect(g.left + col * g.cell, g.top + row * g.cell, g.cell, g.cell);
        }
      }
    }
    const n = s.noise;
    if (n) {
      const tile = document.createElement("canvas");
      tile.width = n.tile;
      tile.height = n.tile;
      const tileCtx = tile.getContext("2d")!;
      const pixels = tileCtx.createImageData(n.tile, n.tile);
      // A 32-bit LCG (Numerical Recipes constants), its top byte per channel.
      let state = n.seed >>> 0;
      for (let i = 0; i < pixels.data.length; i++) {
        state = (Math.imul(state, 1664525) + 1013904223) >>> 0;
        pixels.data[i] = (i & 3) === 3 ? 255 : state >>> 24;
      }
      tileCtx.putImageData(pixels, 0, 0);
      ctx.globalAlpha = n.alpha;
      ctx.fillStyle = ctx.createPattern(tile, "repeat")!;
      ctx.fillRect(0, 0, s.width, s.height);
      ctx.globalAlpha = 1;
    }
    const blob = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, s.type, 0.92));
    // Frees the backing store at once: the 48 MP canvas holds 192 MB.
    canvas.width = 0;
    canvas.height = 0;
    if (!blob) throw new Error("the canvas did not encode");
    if (s.keep) {
      const holder = window as unknown as { keptPhotos?: Record<string, File> };
      holder.keptPhotos = { ...holder.keptPhotos, [s.keep]: new File([blob], s.keep, { type: s.type }) };
    }
    const url = await new Promise<string>((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(String(reader.result));
      reader.onerror = () => reject(reader.error);
      reader.readAsDataURL(blob);
    });
    return url.slice(url.indexOf(",") + 1);
  }, scene);
  return Buffer.from(base64, "base64");
}

/**
 * Inserts an EXIF APP1 segment right after the JPEG's SOI, holding one tag:
 * Orientation (0x0112), SHORT, count 1. Byte counts:
 *   TIFF data: header 8 (II, 42, IFD0 offset 8) + entry count 2 + one entry
 *     12 + next-IFD offset 4 = 26 bytes.
 *   Segment length (counts its own 2 bytes): 2 + "Exif\0\0" 6 + 26 = 34 = 0x0022.
 *   Whole segment: marker FF E1 (2) + 34 = 36 bytes.
 */
function withOrientation(jpeg: Buffer, orientation: number): Buffer {
  if (jpeg[0] !== 0xff || jpeg[1] !== 0xd8) throw new Error("not a JPEG");
  const app1 = Buffer.from([
    0xff, 0xe1, 0x00, 0x22,
    0x45, 0x78, 0x69, 0x66, 0x00, 0x00,
    0x49, 0x49, 0x2a, 0x00, 0x08, 0x00, 0x00, 0x00,
    0x01, 0x00,
    0x12, 0x01, 0x03, 0x00, 0x01, 0x00, 0x00, 0x00, orientation, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00,
  ]);
  expect(app1.length).toBe(36);
  return Buffer.concat([jpeg.subarray(0, 2), app1, jpeg.subarray(2)]);
}

/**
 * Chooses kept photos on the dropzone's file input one after another in a
 * single task, as two quick picks would: each assignment fires the change
 * event the input's onChange reads. Returns performance.now() before the first.
 */
function chooseInPage(page: Page, names: string[]): Promise<number> {
  return page.evaluate((keys) => {
    const input = document.querySelector<HTMLInputElement>("[data-testid='photo-file-input']");
    const kept = (window as unknown as { keptPhotos?: Record<string, File> }).keptPhotos ?? {};
    if (!input) throw new Error("no file input");
    const started = performance.now();
    for (const key of keys) {
      const file = kept[key];
      if (!file) throw new Error(`no kept photo ${key}`);
      const transfer = new DataTransfer();
      transfer.items.add(file);
      input.files = transfer.files;
      input.dispatchEvent(new Event("change", { bubbles: true }));
    }
    return started;
  }, names);
}

const pageNow = (page: Page): Promise<number> => page.evaluate(() => performance.now());

// ---- The confirm screen ---------------------------------------------------

async function openDropzone(page: Page): Promise<void> {
  await page.goto("./");
  await page.getByTestId("start-photo").click();
  await expect(page.getByTestId("photo-dropzone")).toBeVisible();
}

/** Waits until the confirm screen's photo has loaded and its fade-in has ended, so boxes read now hold. */
async function waitForPhoto(page: Page, timeout = 30_000): Promise<void> {
  await expect(page.getByTestId("crop-screen")).toBeVisible({ timeout });
  await expect
    .poll(() => page.getByTestId("pin-image").evaluate((img: HTMLImageElement) => img.naturalWidth), { timeout })
    .toBeGreaterThan(0);
  // The screen slides 8 px as it fades in (qFade, index.css). Spinners
  // repeat forever, so only animations that end are awaited.
  await page.evaluate(() =>
    Promise.all(
      document
        .getAnimations()
        .filter((animation) => animation.effect?.getTiming().iterations !== Infinity)
        .map((animation) => animation.finished.catch(() => null)),
    ).then(() => null),
  );
}

async function pinAt(page: Page, index: number): Promise<Point> {
  const pin = page.getByTestId(`corner-pin-${index}`);
  return { x: Number(await pin.getAttribute("data-x")), y: Number(await pin.getAttribute("data-y")) };
}

async function nudge(page: Page, delta: number, plus: string, minus: string): Promise<void> {
  const key = delta > 0 ? plus : minus;
  const steps = Math.abs(delta);
  // PinLayer.tsx: Shift+arrow moves 10 source px, an arrow alone 1.
  for (let i = 0; i < Math.floor(steps / 10); i++) await page.keyboard.press(`Shift+${key}`);
  for (let i = 0; i < steps % 10; i++) await page.keyboard.press(key);
}

/** Drags pin `index` near `target`, then nudges it with the arrow keys until its data-x and data-y are the target. */
async function placePin(page: Page, index: number, target: Point): Promise<void> {
  const crop = page.getByTestId("crop-screen");
  const width = Number(await crop.getAttribute("data-canvas-width"));
  const height = Number(await crop.getAttribute("data-canvas-height"));
  const pin = page.getByTestId(`corner-pin-${index}`);
  await pin.scrollIntoViewIfNeeded();
  const image = (await page.getByTestId("pin-image").boundingBox())!;
  const box = (await pin.boundingBox())!;
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
  await page.mouse.down();
  await page.mouse.move(image.x + (target.x / width) * image.width, image.y + (target.y / height) * image.height, {
    steps: 4,
  });
  await page.mouse.up();
  await pin.focus();
  // A drag lands within a display pixel, several source pixels on a phone.
  for (let round = 0; round < 4; round++) {
    const at = await pinAt(page, index);
    if (at.x === target.x && at.y === target.y) break;
    await nudge(page, target.x - at.x, "ArrowRight", "ArrowLeft");
    await nudge(page, target.y - at.y, "ArrowDown", "ArrowUp");
  }
  await expect(pin).toHaveAttribute("data-x", String(target.x));
  await expect(pin).toHaveAttribute("data-y", String(target.y));
}

async function placePins(page: Page, corners: Point[]): Promise<void> {
  for (const [index, corner] of corners.entries()) await placePin(page, index, corner);
}

/** Types blocks and squares per block on one axis; a count the panel refused would show its old value once the field is left. */
async function enterCount(page: Page, axis: "across" | "down", blocks: number, squares: number): Promise<void> {
  for (const [part, value] of [
    ["blocks", blocks],
    ["squares", squares],
  ] as const) {
    const input = page.getByTestId(`counts-${axis}-${part}`);
    await input.fill(String(value));
    await input.blur();
    await expect(input).toHaveValue(String(value));
  }
}

const COUNT_INPUTS = ["counts-across-blocks", "counts-across-squares", "counts-down-blocks", "counts-down-squares"];

// ---- Tests ------------------------------------------------------------------

test("the dropzone invites traditional, antique and owned quilts, names JPG or PNG, and shows the capture tips at 390 x 844 and 1440 x 900", async ({
  browser,
  baseURL,
}) => {
  for (const view of VIEWS) {
    const context = await browser.newContext({ baseURL, ...view.options });
    try {
      const page = await context.newPage();
      await openDropzone(page);
      const screen = page.locator('[data-screen-label="Photo dropzone"]');
      const lede = screen.locator("p.pf-lede");
      // Criterion 4: traditional and antique quilts, quilts you own, and
      // photos and screenshots still welcome. The shop-listing sentence
      // stays until Jake rules on #101, so nothing here asserts its absence.
      await expect(lede).toContainText(/traditional/i);
      await expect(lede).toContainText(/antique/i);
      await expect(lede).toContainText(/you own/i);
      await expect(lede).toContainText(/\bphoto\b/i);
      await expect(lede).toContainText(/screenshot/i);

      // ux-16: the accept list and the copy name the same formats.
      const dropzone = page.getByTestId("photo-dropzone");
      await expect(page.getByTestId("photo-file-input")).toHaveAttribute("accept", "image/jpeg,image/png");
      await expect(dropzone).toContainText("JPG or PNG");

      // Section 2.1, screen 1: the whole quilt flat and square-on with a
      // margin, even light without glare, and a zoomed-in screenshot.
      const tips = page.getByTestId("capture-tips");
      await expect(tips).toBeVisible();
      for (const words of [/flat/i, /square-on/i, /margin/i, /even light/i, /glare/i, /screenshot/i, /zoom in/i]) {
        await expect(tips).toContainText(words);
      }
      const pick = (await dropzone.boundingBox())!;
      const tip = (await tips.boundingBox())!;
      if (view.size.width >= 820) {
        // DropzoneScreen.css: from 820 px .pf-dz-row has two columns, the
        // picker and a 270 px tips column, so at 1440 the tips sit beside
        // the picker: right of its right edge and level with it.
        expect(tip.x, `${view.name}: tips left`).toBeGreaterThanOrEqual(pick.x + pick.width);
        expect(tip.y, `${view.name}: tips top`).toBeLessThan(pick.y + pick.height);
      } else {
        // Below 820 px the row is one column, so at 390 the tips sit below the picker.
        expect(tip.y, `${view.name}: tips top`).toBeGreaterThanOrEqual(pick.y + pick.height);
      }
      await expectNoHorizontalOverflow(page, "confirm-dropzone");
    } finally {
      await context.close();
    }
  }
});

test("a text file and a truncated JPEG show an error on the dropzone and never open the confirm screen", async ({
  page,
}) => {
  await page.goto("./");
  const jpeg = await drawInPage(page, {
    width: 400,
    height: 300,
    type: "image/jpeg",
    background: "#f2e8d5",
    grid: { left: 0, top: 0, cell: 20, cols: 20, rows: 15, colors: ["#2f4f8f", "#f2e8d5"] },
  });
  const cut = jpeg.subarray(0, Math.floor(jpeg.length * 0.6));
  // The cut drops the end of the scan and the EOI marker (FF D9) that closes the file.
  expect([...cut.subarray(cut.length - 2)]).not.toEqual([0xff, 0xd9]);
  const files = [
    { name: "notes.txt", mimeType: "text/plain", buffer: Buffer.from("A list of fabrics, not a photo.\n") },
    { name: "cut-short.jpg", mimeType: "image/jpeg", buffer: cut },
  ];
  for (const file of files) {
    // A fresh dropzone for each file, so each error is that file's own.
    await openDropzone(page);
    await page.getByTestId("photo-file-input").setInputFiles(file);
    const error = page.getByTestId("photo-error");
    await expect(error, file.name).toBeVisible();
    await expect(error).toHaveAttribute("role", "alert");
    await expect(page.getByTestId("photo-dropzone")).toBeVisible();
    // The decode has settled (the error is up), so the confirm screen can no longer open.
    await expect(page.getByTestId("photo-decoding")).toHaveCount(0);
    await expect(page.getByTestId("crop-screen"), file.name).toHaveCount(0);
  }
});

test("the pins render before the engine finishes booting", async ({ context, page }) => {
  // As layout.spec.ts does: an unanswered route keeps the worker's import of
  // pyodide.mjs pending, so the engine stays booting for the whole test.
  await context.route(ENGINE_IMPORT, () => {});
  await page.goto("./");
  const chip = page.getByTestId("engine-chip");
  await expect(chip).toHaveAttribute("data-engine-phase", "booting");
  await page.getByTestId("start-photo").click();
  await page.getByTestId("photo-file-input").setInputFiles(l0Path);
  await expect(page.getByTestId("crop-screen")).toBeVisible();
  for (let i = 0; i < 4; i++) await expect(page.getByTestId(`corner-pin-${i}`)).toBeVisible();
  // Criterion W7: the pins are up while the engine is still booting.
  expect(await chip.getAttribute("data-engine-phase")).toBe("booting");
});

test("Back returns to the dropzone, and a second photo starts from its own default pins and counts", async ({
  page,
}) => {
  await openDropzone(page);
  await page.getByTestId("photo-file-input").setInputFiles(l0Path);
  await waitForPhoto(page);
  // Photo A, the 894 x 1044 L0 render: its pin 0 starts at the neutral inset
  // (round(894 x 0.15), round(1044 x 0.15)) = (round(134.1), round(156.6)) = (134, 157).
  expect(await pinAt(page, 0)).toEqual({ x: 134, y: 157 });
  const pin = (await page.getByTestId("corner-pin-0").boundingBox())!;
  await page.mouse.move(pin.x + pin.width / 2, pin.y + pin.height / 2);
  await page.mouse.down();
  await page.mouse.move(pin.x + pin.width / 2 + 40, pin.y + pin.height / 2 + 40, { steps: 4 });
  await page.mouse.up();
  expect(await pinAt(page, 0)).not.toEqual({ x: 134, y: 157 });
  await page.getByTestId("counts-across-blocks-inc").click();
  // One block (the default) plus one.
  await expect(page.getByTestId("counts-across-blocks")).toHaveValue("2");

  // U3-6: Back leaves the confirm screen for the dropzone.
  await page.getByTestId("crop-back").click();
  await expect(page.getByTestId("photo-dropzone")).toBeVisible();
  await expect(page.getByTestId("crop-screen")).toHaveCount(0);

  // U3-8: photo B, the 647 x 1400 screenshot fixture, starts at its own
  // neutral inset (confirm/frame.ts neutralInset, 0.15, Math.round):
  // left round(647 x 0.15) = round(97.05) = 97, right round(647 x 0.85) =
  // round(549.95) = 550, top round(1400 x 0.15) = 210, bottom round(1400 x 0.85) = 1190.
  await page.getByTestId("photo-file-input").setInputFiles(screenshotPath);
  const crop = page.getByTestId("crop-screen");
  await expect(crop).toHaveAttribute("data-canvas-width", "647");
  await expect(crop).toHaveAttribute("data-canvas-height", "1400");
  const expected = [
    { x: 97, y: 210 },
    { x: 550, y: 210 },
    { x: 550, y: 1190 },
    { x: 97, y: 1190 },
  ];
  for (const [i, corner] of expected.entries()) expect(await pinAt(page, i), `pin ${i}`).toEqual(corner);
  // DEFAULT_COUNTS (confirm/confirmFlow.ts): one block of one square on each axis.
  for (const id of COUNT_INPUTS) await expect(page.getByTestId(id), id).toHaveValue("1");
});

test("a photo dropped after a cancelled read is the photo Continue stages and reads", async ({ page }) => {
  await watchStaging(page);
  // As the vision copy test in photo.spec.ts does: hold every opencv fetch,
  // here unanswered, so a read waits on the vision engine and stays in progress.
  await page.route("**/*opencv*", () => {});
  await openDropzone(page);

  // Photo A, the L0 render, read on its default pins and counts.
  await page.getByTestId("photo-file-input").setInputFiles(l0Path);
  await waitForPhoto(page);
  await page.getByTestId("crop-analyze").click();
  await expect(page.getByTestId("photo-progress")).toBeVisible();
  await expect.poll(() => stagingCounts(page), { timeout: READY_TIMEOUT }).toEqual({ staged: 1, reads: 1 });

  await page.getByTestId("photo-cancel").click();
  await expect(page.getByTestId("photo-dropzone")).toBeVisible();

  // Photo B, the screenshot fixture, and Continue the moment it is enabled.
  await page.getByTestId("photo-file-input").setInputFiles(screenshotPath);
  await expect(page.getByTestId("crop-screen")).toHaveAttribute("data-canvas-width", "647");
  const analyze = page.getByTestId("crop-analyze");
  await expect(analyze).toBeEnabled();
  await analyze.click();
  // Cancel restarted the worker, so B's stage_photo waits for the new boot.
  await expect.poll(() => stagingCounts(page), { timeout: READY_TIMEOUT }).toEqual({ staged: 2, reads: 2 });

  // Default pins and counts (stagePhoto.ts planCrop): one square per axis,
  // so a square is a whole pinned edge and the margin clamps to the photo.
  // A, 894 x 1044: pins (134, 157) to (760, 887); squarePx = max(760 - 134,
  // 887 - 157) = max(626, 730) = 730; the crop is all of 894 x 1044.
  // B, 647 x 1400: pins (97, 210) to (550, 1190); squarePx = max(453, 980) =
  // 980; the crop is all of 647 x 1400. Both are under the 2000 px cap.
  const a = await stagedPhoto(page, 0);
  const b = await stagedPhoto(page, 1);
  expect({ width: a.width, height: a.height }).toEqual({ width: 894, height: 1044 });
  expect({ width: b.width, height: b.height }).toEqual({ width: 647, height: 1400 });

  // The read after B's staging is B's: B's default pins less a (0, 0) offset at scale 1.
  const read = await readCall(page, 1);
  expect(read.at).toBeGreaterThan(b.at);
  expect(read.corners).toEqual([
    [97, 210],
    [550, 210],
    [550, 1190],
    [97, 1190],
  ]);
  expect(read.crop_offset).toEqual({ x: 0, y: 0 });
});

test("the same photo and pins stage the same bytes and corners at 1440 x 900 and 390 x 844", async ({ page }) => {
  // Sidecar quad (tests/fixtures/photoreal/screenshot_composite_1400.json):
  // (32, 322), (614, 322), (614, 1021), (32, 1021) in a 647 x 1400 photo.
  const quad = sidecarCorners(screenshotSidecarPath);
  expect(quad).toEqual([
    { x: 32, y: 322 },
    { x: 614, y: 322 },
    { x: 614, y: 1021 },
    { x: 32, y: 1021 },
  ]);
  await watchStaging(page);
  const runs: { staged: { width: number; height: number; sha256: string }; read: ReadOptions }[] = [];
  for (const size of [DESKTOP, PHONE]) {
    await page.setViewportSize(size);
    await openDropzone(page);
    await page.getByTestId("photo-file-input").setInputFiles(screenshotPath);
    await waitForPhoto(page);
    await placePins(page, quad);
    await enterCount(page, "across", 9, 5);
    await enterCount(page, "down", 11, 5);
    await page.getByTestId("crop-analyze").click();
    await expect.poll(() => stagingCounts(page), { timeout: READY_TIMEOUT }).toEqual({ staged: 1, reads: 1 });
    const { width, height, sha256 } = await stagedPhoto(page, 0);
    const { corners, crop_offset } = await readCall(page, 0);
    runs.push({ staged: { width, height, sha256 }, read: { corners, crop_offset } });
  }
  const [desktop, phone] = runs;
  // ux-06: one photo and one set of pins give one staged crop at any window width.
  expect(phone.staged.sha256).toBe(desktop.staged.sha256);
  expect(phone.read).toEqual(desktop.read);

  // The plan by hand (stagePhoto.ts frameSquares, squarePx, planCrop): outer
  // edge, no bands, 9 x 5 = 45 squares across and 11 x 5 = 55 down.
  // Top and bottom edges 614 - 32 = 582 px, 582 / 45 = 12.933 px a square;
  // left and right edges 1021 - 322 = 699 px, 699 / 55 = 12.709.
  // squarePx = max = 12.933, margin = ceil(12.933) = 13.
  // x0 = max(0, 32 - 13) = 19, y0 = max(0, 322 - 13) = 309,
  // x1 = min(647, 614 + 13) = 627, y1 = min(1400, 1021 + 13) = 1034:
  // crop 627 - 19 = 608 by 1034 - 309 = 725; 725 <= 2000, so no scaling.
  // Corners less the offset: (13, 13), (595, 13), (595, 712), (13, 712).
  expect({ width: desktop.staged.width, height: desktop.staged.height }).toEqual({ width: 608, height: 725 });
  expect(desktop.read.crop_offset).toEqual({ x: 19, y: 309 });
  expect(desktop.read.corners).toEqual([
    [13, 13],
    [595, 13],
    [595, 712],
    [13, 712],
  ]);
});

test("a crop longer than 1400 px stages at the 2000 px cap with the same bytes and corners at 1440 x 900 and 390 x 844", async ({
  page,
}) => {
  // Every crop staged at phone width elsewhere in this spec is under 1400 px,
  // 834d8be's phone cap, so none of them can tell a cap picked from the window
  // width (ux-06) from the one 2000 px cap. This crop is longer than 1400.
  await watchStaging(page);
  await page.goto("./");
  // A 3000 x 2000 PNG checkerboard of 100 px squares, 30 x 20 from (0, 0).
  const photo = await drawInPage(page, {
    width: 3000,
    height: 2000,
    type: "image/png",
    background: "#f2e8d5",
    grid: { left: 0, top: 0, cell: 100, cols: 30, rows: 20, colors: ["#2f4f8f", "#f2e8d5"] },
  });
  const pins = [
    { x: 100, y: 100 },
    { x: 2900, y: 100 },
    { x: 2900, y: 1900 },
    { x: 100, y: 1900 },
  ];
  const runs: { staged: { width: number; height: number; sha256: string }; read: ReadOptions }[] = [];
  for (const size of [DESKTOP, PHONE]) {
    await page.setViewportSize(size);
    await openDropzone(page);
    await page.getByTestId("photo-file-input").setInputFiles({ name: "grid-3000.png", mimeType: "image/png", buffer: photo });
    await waitForPhoto(page);
    await expect(page.getByTestId("crop-screen")).toHaveAttribute("data-canvas-width", "3000");
    await placePins(page, pins);
    await enterCount(page, "across", 28, 1);
    await enterCount(page, "down", 18, 1);
    await page.getByTestId("crop-analyze").click();
    await expect.poll(() => stagingCounts(page), { timeout: READY_TIMEOUT }).toEqual({ staged: 1, reads: 1 });
    const { width, height, sha256 } = await stagedPhoto(page, 0);
    const { corners, crop_offset } = await readCall(page, 0);
    runs.push({ staged: { width, height, sha256 }, read: { corners, crop_offset } });
  }
  const [desktop, phone] = runs;
  // ux-06: one photo and one set of pins give one staged crop at any window width.
  expect(phone.staged.sha256).toBe(desktop.staged.sha256);
  expect(phone.read).toEqual(desktop.read);

  // The plan by hand (stagePhoto.ts): outer edge, no bands, 28 x 1 = 28
  // squares across and 18 x 1 = 18 down. Top and bottom 2900 - 100 = 2800 px,
  // 2800 / 28 = 100; left and right 1900 - 100 = 1800 px, 1800 / 18 = 100.
  // squarePx = 100, margin = ceil(100) = 100.
  // x0 = max(0, 100 - 100) = 0, y0 = max(0, 100 - 100) = 0,
  // x1 = min(3000, 2900 + 100) = 3000, y1 = min(2000, 1900 + 100) = 2000:
  // crop 3000 x 2000. capLongest(3000, 2000) at 2000: 2000 x round(2000 x
  // 2000 / 3000 = 1333.33) = 2000 x 1333. The 1400 px phone cap would give
  // 1400 x round(2000 x 1400 / 3000 = 933.33) = 1400 x 933.
  for (const [name, run] of [
    ["desktop", desktop],
    ["phone", phone],
  ] as const) {
    expect({ width: run.staged.width, height: run.staged.height }, name).toEqual({ width: 2000, height: 1333 });
    expect(run.read.crop_offset, name).toEqual({ x: 0, y: 0 });
  }
  // Corners scaled per axis: x 100 x 2000 / 3000 = 66.667, 2900 x 2000 / 3000
  // = 1933.333; y 100 x 1333 / 2000 = 66.65, 1900 x 1333 / 2000 = 1266.35.
  const expected = [
    [66.667, 66.65],
    [1933.333, 66.65],
    [1933.333, 1266.35],
    [66.667, 1266.35],
  ];
  for (const [i, [x, y]] of expected.entries()) {
    expect(desktop.read.corners[i][0], `corner ${i} x`).toBeCloseTo(x, 3);
    expect(desktop.read.corners[i][1], `corner ${i} y`).toBeCloseTo(y, 3);
  }
});

test("the 2000 px cap keeps a phone screenshot's squares at 18.5 px", async ({ page }) => {
  await page.setViewportSize(PHONE);
  await watchStaging(page);
  await page.goto("./");
  // A 1290 x 2796 phone screenshot holding a 40 x 40 grid of 18.5 px squares
  // from (275, 1028): right 275 + 40 x 18.5 = 275 + 740 = 1015, bottom 1028 + 740 = 1768.
  const screenshot = await drawInPage(page, {
    width: 1290,
    height: 2796,
    type: "image/png",
    background: "#ffffff",
    grid: { left: 275, top: 1028, cell: 18.5, cols: 40, rows: 40, colors: ["#2f4f8f", "#f2e8d5"] },
  });
  await page.getByTestId("start-photo").click();
  await page.getByTestId("photo-file-input").setInputFiles({
    name: "phone-screenshot.png",
    mimeType: "image/png",
    buffer: screenshot,
  });
  await waitForPhoto(page);
  await expect(page.getByTestId("crop-screen")).toHaveAttribute("data-canvas-width", "1290");
  await placePins(page, [
    { x: 275, y: 1028 },
    { x: 1015, y: 1028 },
    { x: 1015, y: 1768 },
    { x: 275, y: 1768 },
  ]);
  await enterCount(page, "across", 8, 5);
  await enterCount(page, "down", 8, 5);
  await page.getByTestId("crop-analyze").click();
  await expect.poll(() => stagingCounts(page), { timeout: READY_TIMEOUT }).toEqual({ staged: 1, reads: 1 });

  // By hand: 8 x 5 = 40 squares each way, so squarePx = 740 / 40 = 18.5 on
  // every edge and the margin is ceil(18.5) = 19. x0 = 275 - 19 = 256,
  // y0 = 1028 - 19 = 1009, x1 = 1015 + 19 = 1034, y1 = 1768 + 19 = 1787:
  // crop 1034 - 256 = 778 by 1787 - 1009 = 778, under the 2000 px cap, so
  // it stages at full resolution.
  const staged = await stagedPhoto(page, 0);
  expect({ width: staged.width, height: staged.height }).toEqual({ width: 778, height: 778 });
  const read = await readCall(page, 0);
  expect(read.crop_offset).toEqual({ x: 256, y: 1009 });
  // (275 - 256, 1028 - 1009) = (19, 19), (1015 - 256, 19) = (759, 19), and so on.
  expect(read.corners).toEqual([
    [19, 19],
    [759, 19],
    [759, 759],
    [19, 759],
  ]);
  // (759 - 19) / 40 = 740 / 40 = 18.5 px a square in the staged crop, where
  // 834d8be's phone path capped the whole photo at 1400 on its longest
  // side: 18.5 x 1400 / 2796 = 9.26 px (docs-03).
  expect((read.corners[1][0] - read.corners[0][0]) / 40).toBe(18.5);
});

test("a JPEG with EXIF orientation 6 stages upright, with the pins on the displayed pixels", async ({ page }) => {
  await watchStaging(page);
  await page.goto("./");
  // Stored 300 x 200: mid gray, with its bottom-left 60 x 60 (x 0 to 59,
  // y 140 to 199) red. Orientation 6 shows the stored image turned 90
  // degrees clockwise: displayed 200 x 300, and stored (x, y) shows at
  // (199 - y, x). The stored bottom-left (0, 199) shows at (0, 0), so the
  // red block becomes the displayed top-left 60 x 60 (x' = 199 - y from 0
  // to 59, y' = x from 0 to 59).
  const stored = await drawInPage(page, {
    width: 300,
    height: 200,
    type: "image/jpeg",
    background: "#808080",
    rects: [{ x: 0, y: 140, w: 60, h: 60, color: "#ff0000" }],
  });
  await page.getByTestId("start-photo").click();
  await page.getByTestId("photo-file-input").setInputFiles({
    name: "turned.jpg",
    mimeType: "image/jpeg",
    buffer: withOrientation(stored, 6),
  });
  await waitForPhoto(page);
  const crop = page.getByTestId("crop-screen");
  await expect(crop).toHaveAttribute("data-canvas-width", "200");
  await expect(crop).toHaveAttribute("data-canvas-height", "300");
  const natural = await page
    .getByTestId("pin-image")
    .evaluate((img: HTMLImageElement) => ({ width: img.naturalWidth, height: img.naturalHeight }));
  expect(natural).toEqual({ width: 200, height: 300 });

  // Each pin's center, mapped back through the photo's own box, lands on its
  // data-x and data-y within one display pixel's worth of source pixels
  // (200 / box width across, 300 / box height down).
  const image = (await page.getByTestId("pin-image").boundingBox())!;
  for (let i = 0; i < 4; i++) {
    const box = (await page.getByTestId(`corner-pin-${i}`).boundingBox())!;
    const at = await pinAt(page, i);
    const x = ((box.x + box.width / 2 - image.x) / image.width) * 200;
    const y = ((box.y + box.height / 2 - image.y) / image.height) * 300;
    expect(Math.abs(x - at.x), `pin ${i} x`).toBeLessThanOrEqual(200 / image.width);
    expect(Math.abs(y - at.y), `pin ${i} y`).toBeLessThanOrEqual(300 / image.height);
  }

  await page.getByTestId("crop-analyze").click();
  await expect.poll(() => stagingCounts(page), { timeout: READY_TIMEOUT }).toEqual({ staged: 1, reads: 1 });
  // Default pins (30, 45) to (170, 255) and one square per axis: squarePx =
  // max(140, 210) = 210, so the crop clamps to the whole 200 x 300 photo.
  const staged = await stagedPhoto(page, 0);
  expect({ width: staged.width, height: staged.height }).toEqual({ width: 200, height: 300 });
  const [topLeft, bottomRight] = await stagedPixels(page, 0, [
    { x: 10, y: 10 },
    { x: 190, y: 290 },
  ]);
  // (10, 10) is stored (10, 199 - 10) = (10, 189), inside the red block; a
  // JPEG keeps a flat block's color within a few levels away from its edges.
  expect(topLeft[0], `red at (10, 10): ${topLeft}`).toBeGreaterThan(200);
  expect(topLeft[1], `red at (10, 10): ${topLeft}`).toBeLessThan(60);
  expect(topLeft[2], `red at (10, 10): ${topLeft}`).toBeLessThan(60);
  // (190, 290) is stored (290, 199 - 190) = (290, 9), the gray (128, 128, 128).
  for (const channel of bottomRight.slice(0, 3)) {
    expect(Math.abs(channel - 128), `gray at (190, 290): ${bottomRight}`).toBeLessThanOrEqual(16);
  }
});

test("a 48 MP JPEG decodes and stages, and its times are recorded", async ({ page, browser }) => {
  await watchStaging(page);
  // Drop, the confirm screen shown and Continue, each at performance.now()
  // in the page, the clock the staging record uses.
  await page.addInitScript(() => {
    const marks: Record<string, number> = {};
    (window as unknown as { stagingMarks: Record<string, number> }).stagingMarks = marks;
    document.addEventListener(
      "change",
      (event) => {
        if ((event.target as Element | null)?.getAttribute?.("data-testid") === "photo-file-input") {
          marks.drop = performance.now();
        }
      },
      true,
    );
    document.addEventListener(
      "click",
      (event) => {
        if ((event.target as Element | null)?.closest?.("[data-testid='crop-analyze']")) marks.continue = performance.now();
      },
      true,
    );
    new MutationObserver(() => {
      if (marks.shown === undefined && document.querySelector("[data-testid='crop-screen']")) {
        marks.shown = performance.now();
      }
    }).observe(document, { childList: true, subtree: true });
  });
  await page.goto("./");
  // Booted first, so neither time includes the engine's boot.
  await expect(page.getByTestId("engine-chip")).toHaveAttribute("data-engine-phase", "ready", {
    timeout: READY_TIMEOUT,
  });
  // 8000 x 6000 = 48,000,000 px: a checkerboard of 100 px squares, 80 x 60,
  // under noise, so the file's size and decode cost are a photo's rather
  // than a flat chart's (the bare checkerboard encodes to about 1.5 MB).
  const photo = await drawInPage(page, {
    width: 8000,
    height: 6000,
    type: "image/jpeg",
    background: "#f2e8d5",
    grid: { left: 0, top: 0, cell: 100, cols: 80, rows: 60, colors: ["#2f4f8f", "#f2e8d5"] },
    noise: { tile: 509, alpha: 0.15, seed: 42 },
  });
  await page.getByTestId("start-photo").click();
  await page.getByTestId("photo-file-input").setInputFiles({ name: "48mp.jpg", mimeType: "image/jpeg", buffer: photo });
  await waitForPhoto(page, BIG_PHOTO_TIMEOUT);
  await expect(page.getByTestId("crop-screen")).toHaveAttribute("data-canvas-width", "8000");
  await page.getByTestId("crop-analyze").click();
  await expect
    .poll(() => stagingCounts(page), { timeout: BIG_PHOTO_TIMEOUT })
    .toEqual({ staged: 1, reads: 1 });

  // Default pins: left round(8000 x 0.15) = 1200, right round(8000 x 0.85) =
  // 6800, top round(6000 x 0.15) = 900, bottom round(6000 x 0.85) = 5100.
  // One square per axis: squarePx = max(5600, 4200) = 5600, so the crop is
  // the whole 8000 x 6000; capLongest scales by 2000 / 8000 = 0.25 to
  // 2000 x round(6000 x 0.25) = 2000 x 1500.
  const staged = await stagedPhoto(page, 0);
  expect({ width: staged.width, height: staged.height }).toEqual({ width: 2000, height: 1500 });
  // The corners scale with it: (1200 x 0.25, 900 x 0.25) = (300, 225), (1700, 225), (1700, 1275), (300, 1275).
  expect((await readCall(page, 0)).corners).toEqual([
    [300, 225],
    [1700, 225],
    [1700, 1275],
    [300, 1275],
  ]);

  const marks = await page.evaluate(
    () => (window as unknown as { stagingMarks: Record<string, number> }).stagingMarks,
  );
  const timing = {
    photo: { width: 8000, height: 6000, jpegBytes: photo.length, content: "checkerboard under seeded noise" },
    decodeMs: Math.round(marks.shown - marks.drop),
    stageMs: Math.round(staged.at - marks.continue),
    staged: { width: staged.width, height: staged.height },
    machine: {
      cpu: os.cpus()[0]?.model ?? "unknown",
      cores: os.cpus().length,
      memoryGb: Math.round(os.totalmem() / 2 ** 30),
      platform: `${os.platform()} ${os.release()}`,
      chromium: browser.version(),
    },
  };
  mkdirSync(outDir, { recursive: true });
  writeFileSync(path.join(outDir, "staging-48mp.json"), JSON.stringify(timing, null, 2) + "\n");
  console.log(`48 MP staging: decode ${timing.decodeMs} ms, stage ${timing.stageMs} ms`, timing);
  expect(timing.decodeMs).toBeGreaterThan(0);
  expect(timing.stageMs).toBeGreaterThan(0);
});

test("Continue stays in view without scrolling and the photo takes the available height at 1440 x 900 and 390 x 844", async ({
  browser,
  baseURL,
}) => {
  for (const view of VIEWS) {
    const context = await browser.newContext({ baseURL, ...view.options });
    try {
      const page = await context.newPage();
      await openDropzone(page);
      await page.getByTestId("photo-file-input").setInputFiles(l0Path);
      await waitForPhoto(page);
      expect(await page.evaluate(() => window.scrollY), `${view.name}: scrolled`).toBe(0);
      const bar = page.getByTestId("confirm-bar");
      await expect(bar).toBeInViewport({ ratio: 1 });
      await expect(page.getByTestId("crop-analyze")).toBeInViewport({ ratio: 1 });
      const image = (await page.getByTestId("pin-image").boundingBox())!;
      const barBox = (await bar.boundingBox())!;
      expect(image.y + image.height, `${view.name}: photo bottom`).toBeLessThanOrEqual(barBox.y);
      // Criterion: the size block stays on the confirm screen until C3c.
      await expect(page.getByTestId("size-block"), `${view.name}: size block`).toBeVisible();

      // The photo's height, from the rules that size it. CropScreen.tsx sets
      // available = window height - the photo box's top - the bar's height
      // - 14 (ROW_GAP_PX) - 12 (BOTTOM_MARGIN_PX), and CropScreen.css sizes
      // PinLayer's stage to fit available less 96 px of PinLayer chrome
      // (2 x 22 stage padding + an 8 px gap + the 44 px zoom row), or the
      // photo column's width, whichever binds. The L0 render is 894 x 1044.
      // scrollY is 0, so the photo box's viewport top is its document top.
      const photoTop = (await page.locator(".pf-confirm__photo").boundingBox())!.y;
      const chrome = photoTop + barBox.height;
      // Whole-pixel offsetTop and offsetHeight in CropScreen.tsx and the
      // Math.floor there against fractional boxes here: within 2 px.
      const heightBound = Math.floor(view.size.height - chrome - 14 - 12) - 96;
      if (view.name === "desktop") {
        // At 1440 x 900 the height binds: .app-main is 1420 px less 2 x 22
        // padding = 1376 px, the photo column 1376 - 24 (gap) - 390 (side)
        // = 962 px, and an available - 96 px tall photo is
        // (available - 96) x 894 / 1044 wide, under 962 - 44 for any
        // available up to 900. With the header, title, lede and bar under
        // 300 px, the photo is at least 900 - 300 - 26 - 96 = 478 px tall,
        // 478 / 900 = 53 percent of the window.
        expect(chrome, "desktop: chrome above and below the photo").toBeLessThanOrEqual(300);
        expect(image.height, "desktop: photo height").toBeGreaterThanOrEqual(478);
        expect(Math.abs(image.height - heightBound), "desktop: photo takes the available height").toBeLessThanOrEqual(2);
      } else {
        // At 390 x 844 the width binds: 390 - 2 x 14 (.app-main padding)
        // = 362 px of stage, less 2 x 22 padding = 318 px of photo, so
        // 318 x 1044 / 894 = 331992 / 894 = 371.36 px tall, 371.36 / 844 =
        // 44 percent of the window. The height would bind first only if the
        // chrome passed 844 - 26 - 96 - 371.36 = 350.64 px.
        expect(chrome, "phone: chrome above and below the photo").toBeLessThanOrEqual(350);
        expect(heightBound, "phone: the height does not bind").toBeGreaterThanOrEqual(371);
        expect(image.width, "phone: photo width").toBeCloseTo(318, 0);
        expect(image.height, "phone: photo height").toBeCloseTo(371.36, 0);
      }
      await expectNoHorizontalOverflow(page, "confirm-screen");

      if (view.name === "phone") {
        // The tall 647 x 1400 screenshot fixture: here the height binds
        // ((available - 96) x 647 / 1400 is under 318 px), and Continue
        // still sits in view without scrolling.
        await page.getByTestId("crop-back").click();
        await page.getByTestId("photo-file-input").setInputFiles(screenshotPath);
        await waitForPhoto(page);
        await expect(page.getByTestId("crop-screen")).toHaveAttribute("data-canvas-height", "1400");
        expect(await page.evaluate(() => window.scrollY), "phone, tall photo: scrolled").toBe(0);
        await expect(bar, "phone, tall photo: confirm bar").toBeInViewport({ ratio: 1 });
        await expect(page.getByTestId("crop-analyze"), "phone, tall photo: Continue").toBeInViewport({ ratio: 1 });
        const tall = (await page.getByTestId("pin-image").boundingBox())!;
        const tallBar = (await bar.boundingBox())!;
        expect(tall.y + tall.height, "phone, tall photo: photo bottom").toBeLessThanOrEqual(tallBar.y);
        await expectNoHorizontalOverflow(page, "confirm-screen-tall");
      }
    } finally {
      await context.close();
    }
  }
});

test("a typed band width in inches converts with the read's default square size", async ({ page }) => {
  await watchStaging(page);
  await openDropzone(page);
  await page.getByTestId("photo-file-input").setInputFiles(l0Path);
  await waitForPhoto(page);

  // Before any read there is no square size, so the inch field is off.
  await expect(page.getByTestId("bands-inches-off")).toBeVisible();
  await page.getByTestId("band-add").click();
  await expect(page.getByTestId("band-1-inches")).toBeDisabled();
  await page.getByTestId("band-1-remove").click();
  await expect(page.getByTestId("band-1")).toHaveCount(0);

  await placePins(page, sidecarCorners(l0SidecarPath));
  await enterCount(page, "across", 9, 5);
  await enterCount(page, "down", 11, 5);
  await page.getByTestId("crop-analyze").click();
  await expect(page.getByTestId("photo-results")).toBeVisible({ timeout: REVERSE_TIMEOUT });
  // Criteria U3-4: nothing detects the quad, through a whole Continue to results.
  expect(await detectQuadCalls(page)).toBe(0);

  await page.getByTestId("adjust-corners").click();
  await expect(page.getByTestId("crop-screen")).toBeVisible();
  // A10's default (#149 decision), worked from the code:
  // - The L0 render draws eighths x scale / 8 px (qrep/render/renderer.py:73-74,
  //   px() at :84), and beforeAll renders at scale 10: 10 px per inch.
  // - The pins sit on the sidecar's outer corners, 822 - 72 = 750 px apart
  //   across. The staged crop, 72 to 822 by 72 to 972 plus a margin of
  //   ceil(750 / 45) = 17, is 784 x 934 (stagePhoto.ts planCrop), under the
  //   2000 px cap, so 1 staged px is 1 photo px, and rectify keeps
  //   that scale: its width is the mean top and bottom edge, 750 px
  //   (qrep/vision/rectify.py:522).
  // - 750 px spans 45 squares plus a 30 eighth border on both sides, and
  //   30 / 12 = 2.5 squares, so 45 + 2 x 2.5 = 50 squares of 750 / 50 = 15 px.
  // - The read assumes 10 px per inch (ASSUMED_PPI, qrep/vision/pipeline.py:53)
  //   and sets cell_size = round(pitch x 8 / ASSUMED_PPI) (pipeline.py:236):
  //   round(15 x 8 / 10) = 12 eighths, 15 / 10 = 1.5 in.
  // - size_pattern with source "default" (qrep/model/sizing.py:323) fits the
  //   read's own size in SQUARE_STEP = 2 eighth (1/4 in) squares
  //   (sizing.py:53). 12 is a multiple of 2, so the read's own square is one
  //   of the steps and keeps the read's size up to the 1/4 in border snap
  //   (BORDER_STEP, sizing.py:54); a step of 10 or 14 moves the 45 squares
  //   across alone by 45 x 2 = 90 eighths. The default square stays 12.
  await expect(page.getByTestId("bands-inches-off")).toHaveCount(0, { timeout: READY_TIMEOUT });
  await page.getByTestId("band-add").click();
  // A new band is 1 square wide: 1 x 12 / 8 = 1.5 in, shown as 1 1/2 in (BandsControl.tsx formatInches).
  await expect(page.getByTestId("band-1-width")).toHaveText("1 square, 1 1/2 in");
  const inches = page.getByTestId("band-1-inches");
  await expect(inches).toBeEnabled();
  await inches.fill("3");
  await inches.press("Enter");
  // 3 in = 24 eighths, already a whole quarter inch; 24 / 12 = 2 squares
  // (confirm/bands.ts inchesToSquares), shown as 2 x 12 / 8 = 3 in.
  await expect(page.getByTestId("band-1-width")).toHaveText("2 squares, 3 in");
});

test("Adjust the crop after the sample opens the sample with its default pins, and Continue reads it again", async ({
  page,
}) => {
  await watchStaging(page);
  await page.goto("./");
  await page.getByTestId("start-photo").click();
  await page.getByTestId("photo-sample").click();
  // The sample still bypasses the confirm screen on the way in.
  await expect(page.getByTestId("crop-screen")).toHaveCount(0);
  await expect(page.getByTestId("photo-results")).toBeVisible({ timeout: REVERSE_TIMEOUT });
  await expect(page.getByTestId("crop-screen")).toHaveCount(0);

  await page.getByTestId("adjust-corners").click();
  await waitForPhoto(page);
  // The sample is the level 0 render of double_irish_chain.json at scale 10
  // (photo.tsx startSample: render(demo, 0, 42, 10), as this spec's beforeAll):
  // 600 x 720 eighths x 10 / 8 = 750 x 900 px plus a margin of
  // round(0.08 x 900) = 72 on each side (renderer.py MARGIN_FRACTION): 894 x 1044.
  const crop = page.getByTestId("crop-screen");
  await expect(crop).toHaveAttribute("data-canvas-width", "894");
  await expect(crop).toHaveAttribute("data-canvas-height", "1044");
  // Its neutral inset (frame.ts, 0.15): x round(134.1) = 134 and round(759.9)
  // = 760, y round(156.6) = 157 and round(887.4) = 887.
  const pins = [
    { x: 134, y: 157 },
    { x: 760, y: 157 },
    { x: 760, y: 887 },
    { x: 134, y: 887 },
  ];
  for (const [i, pin] of pins.entries()) {
    await expect(page.getByTestId(`corner-pin-${i}`)).toBeVisible();
    expect(await pinAt(page, i), `pin ${i}`).toEqual(pin);
  }
  const analyze = page.getByTestId("crop-analyze");
  await expect(analyze).toBeEnabled();

  await analyze.click();
  // The sample's own read sent its bytes with reverse_photo; this read
  // stages a crop first, so one stage_photo and a second reverse_photo.
  await expect.poll(() => stagingCounts(page), { timeout: READY_TIMEOUT }).toEqual({ staged: 1, reads: 2 });
  // One square per axis: squarePx = max(760 - 134, 887 - 157) = max(626, 730)
  // = 730, so the margin clamps the crop to the whole 894 x 1044, under the cap.
  const staged = await stagedPhoto(page, 0);
  expect({ width: staged.width, height: staged.height }).toEqual({ width: 894, height: 1044 });
  const read = await readCall(page, 1);
  expect(read.crop_offset).toEqual({ x: 0, y: 0 });
  expect(read.corners).toEqual(pins.map((p) => [p.x, p.y]));
});

test("a pin moved while Continue stages shows where the read had it after Adjust the crop", async ({ page }) => {
  await watchStaging(page);
  // Notes whether the side controls' fieldset is ever disabled.
  await page.addInitScript(() => {
    const seen = { disabled: false };
    (window as unknown as { controlsSeen: typeof seen }).controlsSeen = seen;
    new MutationObserver(() => {
      if (document.querySelector("fieldset.pf-confirm__controls[disabled]")) seen.disabled = true;
    }).observe(document, { subtree: true, childList: true, attributes: true, attributeFilter: ["disabled"] });
  });
  await openDropzone(page);
  await page.getByTestId("photo-file-input").setInputFiles(l0Path);
  await waitForPhoto(page);
  const outer = sidecarCorners(l0SidecarPath);
  await placePins(page, outer);
  await enterCount(page, "across", 9, 5);
  await enterCount(page, "down", 11, 5);

  // Continue, then in the same task one arrow-key nudge of the top-left pin,
  // as a hand still on the pin would make while the crop stages.
  await page.evaluate(() => {
    document.querySelector<HTMLButtonElement>("[data-testid='crop-analyze']")!.click();
    document
      .querySelector("[data-testid='corner-pin-0']")!
      .dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowRight", bubbles: true, cancelable: true }));
  });
  await expect(page.getByTestId("photo-results")).toBeVisible({ timeout: REVERSE_TIMEOUT });
  // The side controls were inert while it staged.
  expect(await page.evaluate(() => (window as unknown as { controlsSeen: { disabled: boolean } }).controlsSeen.disabled)).toBe(true);
  expect(await detectQuadCalls(page)).toBe(0);

  // The read used the pins as they were at Continue: the sidecar corners
  // (72, 72) to (822, 972), 45 x 55 squares, squarePx = max(750 / 45, 900 /
  // 55) = 16.667, margin 17, offset (72 - 17, 72 - 17) = (55, 55), crop
  // 784 x 934 at scale 1: corners (17, 17), (767, 17), (767, 917), (17, 917).
  const read = await readCall(page, 0);
  expect(read.crop_offset).toEqual({ x: 55, y: 55 });
  expect(read.corners).toEqual([
    [17, 17],
    [767, 17],
    [767, 917],
    [17, 917],
  ]);

  await page.getByTestId("adjust-corners").click();
  await waitForPhoto(page);
  // The read's top-left pin (72, 72), not the nudged (73, 72), and its counts.
  expect(await pinAt(page, 0)).toEqual(outer[0]);
  for (const [i, corner] of outer.entries()) expect(await pinAt(page, i), `pin ${i}`).toEqual(corner);
  await expect(page.getByTestId("counts-across-blocks")).toHaveValue("9");
  await expect(page.getByTestId("counts-across-squares")).toHaveValue("5");
  await expect(page.getByTestId("counts-down-blocks")).toHaveValue("11");
  await expect(page.getByTestId("counts-down-squares")).toHaveValue("5");
  await expect(page.getByTestId("crop-analyze")).toBeEnabled();
});

test("Continue stays off while the photo on screen is not the photo QREP decoded", async ({ page }) => {
  await openDropzone(page);
  await page.getByTestId("photo-file-input").setInputFiles(l0Path);
  await waitForPhoto(page);
  const analyze = page.getByTestId("crop-analyze");
  await expect(analyze).toBeEnabled();
  const image = page.getByTestId("pin-image");
  const decodedSrc = (await image.getAttribute("src"))!;
  const message = "QREP could not show this photo the way it reads it. Go back and choose it again.";

  // A 10 x 10 PNG in place of the decoded 894 x 1044 photo, as a browser
  // that sized or turned the img differently from createImageBitmap would show.
  await image.evaluate((img: HTMLImageElement) => {
    const canvas = document.createElement("canvas");
    canvas.width = 10;
    canvas.height = 10;
    img.src = canvas.toDataURL("image/png");
  });
  await expect(analyze).toBeDisabled();
  await expect(page.getByTestId("crop-blocked")).toHaveText(message);

  // The decoded photo again: the sizes match and Continue comes back.
  await image.evaluate((img: HTMLImageElement, src: string) => {
    img.src = src;
  }, decodedSrc);
  await expect(analyze).toBeEnabled();
  await expect(page.getByTestId("crop-blocked")).toHaveCount(0);

  // An img that fails to load.
  await image.evaluate((img: HTMLImageElement) => {
    img.src = "data:image/png;base64,AAAA";
  });
  await expect(analyze).toBeDisabled();
  await expect(page.getByTestId("crop-blocked")).toHaveText(message);
});

test("leaving for home during a read that waits on the vision engine stops its retries", async ({ page }) => {
  // Every reverse_photo is answered at once with the envelope worker.ts posts
  // when the vision wheel fails to load (serve's fail("internal", ...) with
  // ensureVision's message), so photo.tsx runReverse waits for its 2000 ms
  // safety-net timer and asks again. An aborted opencv fetch does not give
  // that reply reliably: Pyodide's loadPackage can resolve without opencv,
  // and the read then fails with another error that is not retried.
  await page.addInitScript(() => {
    const record = { reads: 0 };
    (window as unknown as { visionRecord: typeof record }).visionRecord = record;
    const post = Worker.prototype.postMessage;
    Worker.prototype.postMessage = function (this: Worker, ...args: unknown[]) {
      const message = args[0] as { type?: string; method?: string; id?: number } | null;
      if (message?.type === "call" && message.method === "reverse_photo") {
        record.reads += 1;
        const reply = {
          type: "result",
          id: message.id,
          envelope: {
            ok: false,
            error: { kind: "internal", message: "the vision engine failed to load; retry when back online" },
          },
        };
        setTimeout(() => this.onmessage?.(new MessageEvent("message", { data: reply })), 50);
        return;
      }
      return (post as (...rest: unknown[]) => void).apply(this, args);
    } as typeof Worker.prototype.postMessage;
  });
  const reads = () => page.evaluate(() => (window as unknown as { visionRecord: { reads: number } }).visionRecord.reads);
  await openDropzone(page);
  await page.getByTestId("photo-file-input").setInputFiles(l0Path);
  await waitForPhoto(page);
  await page.getByTestId("crop-analyze").click();
  // Two reads: the first and at least one retry, so the loop is running.
  await expect.poll(reads, { timeout: READY_TIMEOUT }).toBeGreaterThanOrEqual(2);
  await expect(page.getByTestId("photo-progress")).toBeVisible();

  await page.getByRole("button", { name: "Back to the start screen" }).click();
  await expect(page.getByTestId("photo-progress")).toHaveCount(0);
  const before = await reads();
  // 5000 ms is two and a half 2000 ms retry periods: a live loop would ask
  // at least twice more.
  await page.waitForTimeout(5_000);
  expect(await reads()).toBe(before);
});

test("a photo chosen while a larger one decodes is the one the confirm screen shows", async ({ page }) => {
  await page.goto("./");
  // A: 4000 x 3000 JPEG of 100 px squares under noise, so it decodes slowly
  // the way a phone photo does. B: a 300 x 200 PNG.
  await drawInPage(page, {
    width: 4000,
    height: 3000,
    type: "image/jpeg",
    background: "#f2e8d5",
    grid: { left: 0, top: 0, cell: 100, cols: 40, rows: 30, colors: ["#2f4f8f", "#f2e8d5"] },
    noise: { tile: 509, alpha: 0.15, seed: 7 },
    keep: "a.jpg",
  });
  await drawInPage(page, {
    width: 300,
    height: 200,
    type: "image/png",
    background: "#808080",
    rects: [{ x: 0, y: 0, w: 60, h: 60, color: "#ff0000" }],
    keep: "b.png",
  });
  await page.getByTestId("start-photo").click();
  const crop = page.getByTestId("crop-screen");

  // A alone first, to time its decode: from the pick to the confirm screen.
  const aStarted = await chooseInPage(page, ["a.jpg"]);
  await expect(crop).toHaveAttribute("data-canvas-width", "4000", { timeout: BIG_PHOTO_TIMEOUT });
  const decodeMs = (await pageNow(page)) - aStarted;
  await page.getByTestId("crop-back").click();
  await expect(page.getByTestId("photo-dropzone")).toBeVisible();

  // A, then B at once: B's decode starts while A's runs.
  const started = await chooseInPage(page, ["a.jpg", "b.png"]);
  await expect(crop).toHaveAttribute("data-canvas-width", "300", { timeout: BIG_PHOTO_TIMEOUT });
  await expect(crop).toHaveAttribute("data-canvas-height", "200");
  // Well past A's decode: three times its measured time plus a second.
  const settle = 3 * decodeMs + 1000;
  const waited = (await pageNow(page)) - started;
  if (waited < settle) await page.waitForTimeout(settle - waited);
  console.log(`A decoded alone in ${Math.round(decodeMs)} ms; checked B ${Math.round(settle)} ms after the picks`);
  await expect(crop).toHaveAttribute("data-canvas-width", "300");
  await expect(crop).toHaveAttribute("data-canvas-height", "200");
  const natural = await page
    .getByTestId("pin-image")
    .evaluate((img: HTMLImageElement) => ({ width: img.naturalWidth, height: img.naturalHeight }));
  expect(natural).toEqual({ width: 300, height: 200 });
  await expect(page.getByTestId("crop-analyze")).toBeEnabled();
});

test("Back pressed as Continue starts staging a large photo posts nothing for it", async ({ page }) => {
  await watchStaging(page);
  await page.goto("./");
  // Booted first: an engine call posts at once only when the engine is ready
  // and idle (rpc.ts pump), so a stage_photo cannot hide in the queue.
  await expect(page.getByTestId("engine-chip")).toHaveAttribute("data-engine-phase", "ready", {
    timeout: READY_TIMEOUT,
  });
  await drawInPage(page, {
    width: 4000,
    height: 3000,
    type: "image/jpeg",
    background: "#f2e8d5",
    grid: { left: 0, top: 0, cell: 100, cols: 40, rows: 30, colors: ["#2f4f8f", "#f2e8d5"] },
    noise: { tile: 509, alpha: 0.15, seed: 11 },
    keep: "large.jpg",
  });
  await page.getByTestId("start-photo").click();
  const analyze = page.getByTestId("crop-analyze");

  // Timing run: Continue alone, from the click to its stage_photo.
  await chooseInPage(page, ["large.jpg"]);
  await waitForPhoto(page, BIG_PHOTO_TIMEOUT);
  await expect(analyze).toBeEnabled();
  const clicked = await page.evaluate(() => {
    const at = performance.now();
    document.querySelector<HTMLButtonElement>("[data-testid='crop-analyze']")!.click();
    return at;
  });
  await expect.poll(() => stagingCounts(page), { timeout: BIG_PHOTO_TIMEOUT }).toEqual({ staged: 1, reads: 1 });
  const timed = await stagedPhoto(page, 0);
  const stageMs = timed.at - clicked;
  // Default pins and one square per axis: squarePx = max(3400 - 600,
  // 2550 - 450) = 2800, so the crop is the whole 4000 x 3000, capped at
  // 2000 x round(3000 x 2000 / 4000) = 2000 x 1500.
  expect({ width: timed.width, height: timed.height }).toEqual({ width: 2000, height: 1500 });
  await page.getByTestId("photo-cancel").click();
  await expect(page.getByTestId("photo-dropzone")).toBeVisible();
  // Cancel restarts the engine; wait for the new one, for the same reason as above.
  await expect(page.getByTestId("engine-chip")).toHaveAttribute("data-engine-phase", "ready", {
    timeout: READY_TIMEOUT,
  });

  // The same photo, then Continue and Back in one task.
  await chooseInPage(page, ["large.jpg"]);
  await waitForPhoto(page, BIG_PHOTO_TIMEOUT);
  await expect(analyze).toBeEnabled();
  const backAt = await page.evaluate(() => {
    document.querySelector<HTMLButtonElement>("[data-testid='crop-analyze']")!.click();
    document.querySelector<HTMLButtonElement>("[data-testid='crop-back']")!.click();
    return performance.now();
  });
  await expect(page.getByTestId("photo-dropzone")).toBeVisible();
  // Three times the measured staging plus a second, so a crop that was not
  // discarded would have posted by now.
  const settle = 3 * stageMs + 1000;
  const waited = (await pageNow(page)) - backAt;
  if (waited < settle) await page.waitForTimeout(settle - waited);
  console.log(`staging took ${Math.round(stageMs)} ms; checked ${Math.round(settle)} ms after Back`);
  // Only the timing run's stage_photo and reverse_photo, both before Back.
  expect(await stagingCounts(page)).toEqual({ staged: 1, reads: 1 });
  expect(timed.at).toBeLessThan(backAt);
  expect((await readCall(page, 0)).at).toBeLessThan(backAt);
});
