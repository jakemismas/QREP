/**
 * The dev annotate page, driven end to end (C3a, issue #149, last criterion):
 * with a mouse at 1440 x 900 and with touch on an iPhone 13, drag each pin,
 * see the loupe, nudge with keys, set counts by stepper and by typing, and
 * save JSON whose values match a generated test image's hand-computed
 * geometry.
 *
 * The test image is drawn in the browser at run time, so no image fixture is
 * committed, and its sha256 is checked against Node's own hash. Saved files
 * land under web/test-results/annotate/ (gitignored), and the pydantic
 * Annotation model that corpus/schema/annotation.schema.json is exported from
 * validates each one, so the page and the eval agree on the format.
 *
 * Touch input goes through CDP Input.dispatchTouchEvent, which reaches the
 * page as real touch pointers, so the one-finger drag and the two-finger
 * pinch take the same path as on a phone.
 */
import { execFileSync } from "node:child_process";
import { createHash } from "node:crypto";
import { existsSync, mkdirSync, readFileSync } from "node:fs";
import * as path from "node:path";
import { fileURLToPath } from "node:url";
import { devices, expect, test, type CDPSession, type Page } from "@playwright/test";
import { expectNoHorizontalOverflow } from "./helpers/layout";

const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const outDir = path.join(repoRoot, "web", "test-results", "annotate");
const evalDir = path.join(repoRoot, "scripts", "eval");
const lacmaImage = path.join(repoRoot, "corpus", "images", "lacma-54871.jpg");
const lacmaAnnotation = path.join(repoRoot, "corpus", "annotations", "lacma-54871.json");

const DESKTOP_OPTIONS = { viewport: { width: 1440, height: 900 }, isMobile: false, hasTouch: false };
const iPhone = devices["iPhone 13"];
// The descriptor less defaultBrowserType: that one is a worker option, which a
// describe group cannot set, and the config pins chromium.
const IPHONE_OPTIONS = {
  viewport: iPhone.viewport,
  userAgent: iPhone.userAgent,
  deviceScaleFactor: iPhone.deviceScaleFactor,
  isMobile: iPhone.isMobile,
  hasTouch: iPhone.hasTouch,
};

interface Point {
  x: number;
  y: number;
}
interface Size {
  width: number;
  height: number;
}
interface Box {
  x: number;
  y: number;
  width: number;
  height: number;
}
const CORNERS = ["top_left", "top_right", "bottom_right", "bottom_left"] as const;
type Corners = Record<(typeof CORNERS)[number], Point>;
interface Claim {
  value: unknown;
  provenance: string;
}
type Json = Record<string, unknown>;
interface FrameValue {
  outer_edge: { corners: Corners };
  field?: { corners: Corners } | null;
}
interface DrillRecord {
  seq: number;
  t_ms: number;
  kind: string;
  [key: string]: unknown;
}

const IDENTITY_FIELDS = ["schema_version", "photo", "sha256", "canvas"];
const VERIFIED_FIELDS = ["frame", "counts", "construction_class"];

// The generated quilt, by hand: an 800 x 600 photo on gray; the outer edge is
// the rectangle (100, 100) to (700, 500); one border band 1 square wide in one
// color; the field is 10 squares across and 6 down. Across: 10 + 2 x 1 = 12
// squares over 700 - 100 = 600 px, so 600 / 12 = 50 px a square; down: 6 + 2 x
// 1 = 8 squares over 500 - 100 = 400 px, so 400 / 8 = 50 px. The field runs
// from (100 + 50, 100 + 50) = (150, 150) to (700 - 50, 500 - 50) = (650, 450).
// Counts: 2 blocks x 5 squares = 10 across, 2 blocks x 3 squares = 6 down.
const QUILT: Size = { width: 800, height: 600 };
const QUILT_NAME = "generated-quilt.png";
const OUTER: Corners = {
  top_left: { x: 100, y: 100 },
  top_right: { x: 700, y: 100 },
  bottom_right: { x: 700, y: 500 },
  bottom_left: { x: 100, y: 500 },
};
const FIELD: Corners = {
  top_left: { x: 150, y: 150 },
  top_right: { x: 650, y: 150 },
  bottom_right: { x: 650, y: 450 },
  bottom_left: { x: 150, y: 450 },
};
// The neutral inset, 15 percent of the canvas: 0.15 x 800 = 120, 0.85 x 800 =
// 680, 0.15 x 600 = 90, 0.85 x 600 = 510.
const QUILT_INSET: Corners = {
  top_left: { x: 120, y: 90 },
  top_right: { x: 680, y: 90 },
  bottom_right: { x: 680, y: 510 },
  bottom_left: { x: 120, y: 510 },
};

// lacma-54871's source canvas (the committed copy is downsized) and its
// neutral inset: round(0.15 x 3873) = round(580.95) = 581, round(0.85 x 3873)
// = round(3292.05) = 3292, round(0.15 x 4096) = round(614.4) = 614, round(0.85
// x 4096) = round(3481.6) = 3482.
const LACMA_CANVAS: Size = { width: 3873, height: 4096 };
const LACMA_INSET: Corners = {
  top_left: { x: 581, y: 614 },
  top_right: { x: 3292, y: 614 },
  bottom_right: { x: 3292, y: 3482 },
  bottom_left: { x: 581, y: 3482 },
};

/** The worktree's interpreter, read the way web/playwright.config.ts reads .qrep-worker.env. */
function workerEnvPython(): string | undefined {
  const file = path.join(repoRoot, ".qrep-worker.env");
  if (!existsSync(file)) return undefined;
  for (const line of readFileSync(file, "utf8").split(/\r?\n/)) {
    const match = /^\s*([A-Z0-9_]+)\s*=\s*(.*?)\s*$/.exec(line);
    if (match && match[1] === "QREP_PYTHON") return match[2].replace(/^"(.*)"$/, "$1");
  }
  return undefined;
}

// CI's web-spike job installs qrep into the python on its PATH.
const python = process.env.QREP_PYTHON || workerEnvPython() || "python";
const VALIDATE = [
  "import sys, pathlib",
  "sys.path.insert(0, sys.argv[1])",
  "from qrep_eval.annotation import Annotation",
  "Annotation.model_validate_json(pathlib.Path(sys.argv[2]).read_text(encoding='utf-8'))",
].join("; ");

function expectValidAnnotation(file: string) {
  let status = 0;
  let stderr = "";
  try {
    execFileSync(python, ["-c", VALIDATE, evalDir, file], { stdio: "pipe" });
  } catch (err) {
    const failed = err as { status?: number | null; stderr?: Buffer | string };
    status = failed.status ?? -1;
    stderr = String(failed.stderr || err);
  }
  expect(status, `${python} refused ${file}: ${stderr}`).toBe(0);
}

function readAnnotation(): Json {
  return JSON.parse(readFileSync(lacmaAnnotation, "utf8")) as Json;
}

function claimBy(claims: unknown, provenance: string): Claim {
  const found = (claims as Claim[] | undefined)?.find((claim) => claim.provenance === provenance);
  if (!found) throw new Error(`no ${provenance} claim`);
  return found;
}

/** Draws the generated quilt on a canvas in the page and returns its PNG bytes. */
async function drawQuilt(page: Page): Promise<Buffer> {
  const dataUrl = await page.evaluate(
    ({ size, outer, field, cols, rows, square }) => {
      const canvas = document.createElement("canvas");
      canvas.width = size.width;
      canvas.height = size.height;
      const ctx = canvas.getContext("2d");
      if (!ctx) throw new Error("this browser has no 2d canvas");
      ctx.fillStyle = "#808080";
      ctx.fillRect(0, 0, size.width, size.height);
      // The band fills the whole outer edge; the field covers all but its outer square.
      ctx.fillStyle = "#1f3a93";
      ctx.fillRect(outer.x, outer.y, outer.width, outer.height);
      for (let row = 0; row < rows; row++) {
        for (let col = 0; col < cols; col++) {
          ctx.fillStyle = (row + col) % 2 === 0 ? "#b03a2e" : "#f2e6c9";
          ctx.fillRect(field.x + col * square, field.y + row * square, square, square);
        }
      }
      return canvas.toDataURL("image/png");
    },
    {
      size: QUILT,
      outer: { x: 100, y: 100, width: 600, height: 400 },
      field: { x: 150, y: 150 },
      cols: 10,
      rows: 6,
      square: 50,
    },
  );
  return Buffer.from(dataUrl.slice(dataUrl.indexOf(",") + 1), "base64");
}

/** Opens the page with the generated quilt and waits for its hash. */
async function openQuilt(page: Page): Promise<string> {
  await page.goto("annotate.html");
  const png = await drawQuilt(page);
  await page.getByTestId("photo-input").setInputFiles({ name: QUILT_NAME, mimeType: "image/png", buffer: png });
  // Node's hash is the oracle for the page's own SHA-256.
  const sha = createHash("sha256").update(png).digest("hex");
  await expect(page.getByTestId("identity")).toHaveText(`Canvas 800 x 600 px; sha256 ${sha}`);
  await expect(page.getByTestId("pin-outer.top_left")).toBeVisible();
  return sha;
}

async function openLacma(page: Page) {
  await page.goto("annotate.html");
  await page.getByTestId("photo-input").setInputFiles(lacmaImage);
  await page.getByTestId("annotation-input").setInputFiles(lacmaAnnotation);
  await expect(page.getByTestId("identity")).toContainText("Canvas 3873 x 4096");
  await expect(page.getByTestId("pin-outer.top_left")).toBeVisible();
}

const pin = (page: Page, id: string) => page.getByTestId(`pin-${id}`);

async function pinPoint(page: Page, id: string): Promise<Point> {
  const el = pin(page, id);
  await expect(el).toHaveCount(1);
  return { x: Number(await el.getAttribute("data-x")), y: Number(await el.getAttribute("data-y")) };
}

async function expectPinAt(page: Page, id: string, at: Point) {
  await expect(pin(page, id), `${id} x`).toHaveAttribute("data-x", String(at.x));
  await expect(pin(page, id), `${id} y`).toHaveAttribute("data-y", String(at.y));
}

async function allPins(page: Page): Promise<string[]> {
  return page
    .locator("[data-pin-id]")
    .evaluateAll((els) => els.map((el) => `${el.getAttribute("data-pin-id")} ${el.getAttribute("data-x")} ${el.getAttribute("data-y")}`));
}

/** Scrolls the photo to the top of the viewport and returns the img element's box. */
async function showPhoto(page: Page): Promise<Box> {
  await page.getByTestId("pin-stage").evaluate((el) => el.scrollIntoView({ block: "start" }));
  const box = await page.getByTestId("pin-image").boundingBox();
  if (!box) throw new Error("the photo has no box");
  return box;
}

/** Source pixels to client pixels through the image rect, the page's own mapping. */
function toScreen(box: Box, canvas: Size, p: Point): Point {
  return { x: box.x + (p.x * box.width) / canvas.width, y: box.y + (p.y * box.height) / canvas.height };
}

// A pointer outside the viewport reaches nothing, so a drag there would fail for the wrong reason.
function expectOnScreen(page: Page, p: Point, what: string) {
  const viewport = page.viewportSize();
  if (!viewport) throw new Error("this test needs a fixed viewport");
  expect(p.x >= 0 && p.x <= viewport.width && p.y >= 0 && p.y <= viewport.height, `${what} on screen`).toBe(true);
}

const between = (a: Point, b: Point, t: number): Point => ({ x: a.x + (b.x - a.x) * t, y: a.y + (b.y - a.y) * t });

/**
 * A drop lands within one screen pixel of its target: one screen pixel spans
 * canvas.width / box.width source pixels, and snapping to whole pixels adds
 * up to 0.5 more. This proves the pointer maps through the image rect.
 */
function expectWithinScreenPixel(at: Point, target: Point, box: Box, canvas: Size, what: string) {
  const tolerance = canvas.width / box.width + 0.5;
  expect(Math.abs(at.x - target.x), `${what}: x ${at.x} vs ${target.x}`).toBeLessThanOrEqual(tolerance);
  expect(Math.abs(at.y - target.y), `${what}: y ${at.y} vs ${target.y}`).toBeLessThanOrEqual(tolerance);
}

async function mouseDrag(page: Page, id: string, target: Point, canvas: Size): Promise<Box> {
  const box = await showPhoto(page);
  const from = toScreen(box, canvas, await pinPoint(page, id));
  const to = toScreen(box, canvas, target);
  expectOnScreen(page, from, `${id} start`);
  expectOnScreen(page, to, `${id} target`);
  await page.mouse.move(from.x, from.y);
  await page.mouse.down();
  const mid = between(from, to, 0.5);
  await page.mouse.move(mid.x, mid.y, { steps: 4 });
  await expect(page.getByTestId("loupe"), `${id}: loupe while dragging`).toBeVisible();
  await page.mouse.move(to.x, to.y, { steps: 4 });
  await page.mouse.up();
  await expect(page.getByTestId("loupe"), `${id}: loupe after the drop`).toBeHidden();
  return box;
}

async function touch(cdp: CDPSession, type: "touchStart" | "touchMove" | "touchEnd", points: Point[]) {
  await cdp.send("Input.dispatchTouchEvent", {
    type,
    touchPoints: points.map((p, id) => ({ x: p.x, y: p.y, id })),
  });
}

async function touchDrag(page: Page, cdp: CDPSession, id: string, target: Point, canvas: Size): Promise<Box> {
  const box = await showPhoto(page);
  const from = toScreen(box, canvas, await pinPoint(page, id));
  const to = toScreen(box, canvas, target);
  expectOnScreen(page, from, `${id} start`);
  expectOnScreen(page, to, `${id} target`);
  await touch(cdp, "touchStart", [from]);
  for (const t of [0.25, 0.5]) await touch(cdp, "touchMove", [between(from, to, t)]);
  await expect(page.getByTestId("loupe"), `${id}: loupe while dragging`).toBeVisible();
  for (const t of [0.75, 1]) await touch(cdp, "touchMove", [between(from, to, t)]);
  await touch(cdp, "touchEnd", []);
  await expect(page.getByTestId("loupe"), `${id}: loupe after the drop`).toBeHidden();
  return box;
}

/** Arrow keys from the pin's spot to target, one source pixel a press. */
async function nudgeTo(page: Page, id: string, target: Point) {
  await pin(page, id).focus();
  const at = await pinPoint(page, id);
  const dx = target.x - at.x;
  const dy = target.y - at.y;
  for (let i = 0; i < Math.abs(dx); i++) await page.keyboard.press(dx > 0 ? "ArrowRight" : "ArrowLeft");
  for (let i = 0; i < Math.abs(dy); i++) await page.keyboard.press(dy > 0 ? "ArrowDown" : "ArrowUp");
  await expectPinAt(page, id, target);
}

/** A drop can land on its target exactly and need no nudge, so the keys get pressed here regardless. */
async function expectKeySteps(page: Page, id: string, at: Point) {
  await pin(page, id).focus();
  await page.keyboard.press("Shift+ArrowRight");
  // Shift moves 10 source pixels: x + 10.
  await expectPinAt(page, id, { x: at.x + 10, y: at.y });
  await page.keyboard.press("Shift+ArrowLeft");
  await page.keyboard.press("ArrowDown");
  // Back 10, then down 1: (x, y + 1).
  await expectPinAt(page, id, { x: at.x, y: at.y + 1 });
  await page.keyboard.press("ArrowUp");
  await expectPinAt(page, id, at);
}

async function saveJson(page: Page, name: string, prefix: string): Promise<{ file: string; data: Json }> {
  mkdirSync(outDir, { recursive: true });
  const waiting = page.waitForEvent("download");
  await page.getByTestId("save").click();
  const download = await waiting;
  expect(download.suggestedFilename()).toBe(name);
  const file = path.join(outDir, `${prefix}-${name}`);
  await download.saveAs(file);
  return { file, data: JSON.parse(readFileSync(file, "utf8")) as Json };
}

test.describe("annotate page with a mouse at 1440 x 900", { tag: "@phone" }, () => {
  test.use(DESKTOP_OPTIONS);

  test("a mouse drags, nudges, bands and counts a generated quilt, and the saved JSON is its hand geometry", async ({
    page,
  }) => {
    const sha = await openQuilt(page);
    for (const name of CORNERS) await expectPinAt(page, `outer.${name}`, QUILT_INSET[name]);
    await expect(page.getByTestId("pin-view")).toHaveAttribute("data-scale", "1.000");

    for (const name of CORNERS) {
      const id = `outer.${name}`;
      const box = await mouseDrag(page, id, OUTER[name], QUILT);
      expectWithinScreenPixel(await pinPoint(page, id), OUTER[name], box, QUILT, `${id} drop`);
      await nudgeTo(page, id, OUTER[name]);
    }
    await expectKeySteps(page, "outer.top_left", OUTER.top_left);

    // Across blocks by stepper, 1 + 1 = 2; squares typed, 5. Down the same: 2 and 3.
    await page.getByTestId("counts-across-blocks-inc").click();
    await expect(page.getByTestId("counts-across-blocks")).toHaveValue("2");
    await page.getByTestId("counts-across-squares").fill("5");
    await page.getByTestId("counts-down-blocks-inc").click();
    await expect(page.getByTestId("counts-down-blocks")).toHaveValue("2");
    await page.getByTestId("counts-down-squares").fill("3");
    // 2 x 5 = 10 squares across, 2 x 3 = 6 down.
    await expect(page.getByTestId("counts-across-total")).toHaveText("2 blocks x 5 squares = 10 squares");
    await expect(page.getByTestId("counts-down-total")).toHaveText("2 blocks x 3 squares = 6 squares");
    const grid = page.getByTestId("grid-overlay");
    await expect(grid).toHaveAttribute("data-cols", "10");
    await expect(grid).toHaveAttribute("data-rows", "6");

    // No square size yet, so inches are off, and no band exists.
    await expect(page.getByTestId("bands-inches-off")).toBeVisible();
    await expect(page.getByTestId("band-1")).toHaveCount(0);
    await page.getByTestId("band-add").click();
    await expect(page.getByTestId("band-1-width")).toHaveText("1 square");
    await expect(page.getByTestId("band-2")).toHaveCount(0);
    await expect(page.getByTestId("band-line-1")).toHaveCount(1);
    await page.getByTestId("band-1-inc").click();
    // 1 + 0.25 = 1.25 squares.
    await expect(page.getByTestId("band-1-width")).toHaveText("1.25 squares");
    await expect(page.getByTestId("band-1-inches")).toBeDisabled();

    // Adding a band selects it (BandsControl's band-add), and band-1-select
    // toggles: off, which hides the handles, then on again.
    const select = page.getByTestId("band-1-select");
    await expect(select).toHaveAttribute("aria-pressed", "true");
    await select.click();
    await expect(select).toHaveAttribute("aria-pressed", "false");
    await expect(pin(page, "band.left")).toHaveCount(0);
    await select.click();
    await expect(select).toHaveAttribute("aria-pressed", "true");
    // Band 1's inner line at 1.25 squares sits 1.25 / (10 + 2 x 1.25) = 1.25 /
    // 12.5 = 0.1 of the way in, so the left handle is at x = 100 + 600 x 0.1 =
    // 160, y = 100 + 400 x 0.5 = 300.
    const handle = await pinPoint(page, "band.left");
    expect(handle.x).toBeCloseTo(160, 6);
    expect(handle.y).toBeCloseTo(300, 6);

    const handleTarget = { x: 150, y: 300 };
    const box = await mouseDrag(page, "band.left", handleTarget, QUILT);
    // f = (150 - 100) / 600 = 1/12; w = (f x 10) / (1 - 2f) = (10/12) / (10/12)
    // = 1.0 square. The drop is within one screen pixel (800 / box.width, about
    // 1.05 source px at this width, then snapped): x = 151 gives f = 51/600 =
    // 0.085 and w = 0.85 / 0.83 = 1.024, x = 149 gives f = 49/600 and w = 0.8167
    // / 0.8367 = 0.976, both within 0.05.
    const widthText = (await page.getByTestId("band-1-width").textContent()) ?? "";
    expect(widthText).toMatch(/^\d+(\.\d+)? squares?$/);
    expect(Math.abs(Number.parseFloat(widthText) - 1), `band width from "${widthText}"`).toBeLessThanOrEqual(0.05);
    // The handle follows the band's new inner line, at the drop.
    expectWithinScreenPixel(await pinPoint(page, "band.left"), handleTarget, box, QUILT, "band.left drop");

    await page.getByTestId("square-size").selectOption("12");
    await expect(page.getByTestId("bands-inches-off")).toHaveCount(0);
    const inches = page.getByTestId("band-1-inches");
    await expect(inches).toBeEnabled();
    await inches.fill("1.5");
    await inches.press("Enter");
    // "12" is 12 eighths = 1 1/2 in a square; 1.5 in (already a quarter inch)
    // / 1.5 in = 1 square exactly, which is 1 x 1.5 = 1 1/2 in.
    await expect(page.getByTestId("band-1-width")).toHaveText("1 square, 1 1/2 in");

    await page.getByTestId("field-visible").check();
    // The field from the band and counts: u = 1 / (10 + 2 x 1) = 1/12 and v =
    // 1 / (6 + 2 x 1) = 1/8 in from each side, so x = 100 + 600 x 1/12 = 150
    // and 700 - 50 = 650, y = 100 + 400 x 1/8 = 150 and 500 - 50 = 450.
    for (const name of CORNERS) await expectPinAt(page, `field.${name}`, FIELD[name]);

    const requestFrame = page.getByTestId("request-frame");
    await page.locator("details", { has: requestFrame }).locator("summary").click();
    await expect(requestFrame).toBeVisible();
    expect(JSON.parse((await requestFrame.textContent()) ?? "")).toEqual({
      kind: "outer_edge",
      corners: OUTER,
      bands: [{ width_squares: 1 }],
    });

    await page.getByTestId("construction-class").selectOption("squares");
    const saved = await saveJson(page, "generated-quilt.json", "mouse");
    await expect(page.getByTestId("status")).toHaveText("Saved generated-quilt.json.");
    expect(saved.data).toEqual({
      schema_version: 1,
      photo: QUILT_NAME,
      sha256: sha,
      canvas: [800, 600],
      frame: [
        {
          provenance: "verified-jake",
          value: {
            outer_edge: { kind: "outer_edge", corners: OUTER, bands: [{ width_squares: 1 }] },
            field: { kind: "field", corners: FIELD },
          },
        },
      ],
      counts: [
        {
          provenance: "verified-jake",
          value: { blocks_across: 2, blocks_down: 2, squares_per_block_across: 5, squares_per_block_down: 3 },
        },
      ],
      construction_class: [{ provenance: "verified-jake", value: "squares" }],
    });
    expectValidAnnotation(saved.file);

    await expectNoHorizontalOverflow(page, "annotate-loaded");
  });

  test("the committed lacma-54871 copy opens on proposed-a and saves one verified claim beside every original", async ({
    page,
  }) => {
    const original = readAnnotation();
    // The page opens on the verified claim, else proposed-a's: this file has no
    // verified-jake claim in any field, so it opens on proposed-a's.
    const provenances = Object.entries(original)
      .filter(([field]) => !IDENTITY_FIELDS.includes(field))
      .flatMap(([, claims]) => (claims as Claim[]).map((claim) => claim.provenance));
    expect(provenances).not.toContain("verified-jake");
    const frameA = claimBy(original.frame, "proposed-a");
    const countsA = claimBy(original.counts, "proposed-a");
    const classA = claimBy(original.construction_class, "proposed-a");
    const start = frameA.value as FrameValue;

    await openLacma(page);
    await expect(page.getByTestId("mode")).toHaveText("Verifying, starting from proposed-a");
    for (const name of CORNERS) await expectPinAt(page, `outer.${name}`, start.outer_edge.corners[name]);
    await expect(page.getByTestId("construction-class")).toHaveValue(String(classA.value));

    const saved = await saveJson(page, "lacma-54871.json", "corpus");
    const data = saved.data;
    expect(Object.keys(data).sort()).toEqual(Object.keys(original).sort());
    for (const field of IDENTITY_FIELDS) expect(data[field], field).toEqual(original[field]);
    expect(data.sha256).toBe(original.sha256);
    for (const [field, claims] of Object.entries(original)) {
      if (IDENTITY_FIELDS.includes(field)) continue;
      const before = claims as Claim[];
      const after = data[field] as Claim[];
      expect(after.slice(0, before.length), `${field}: the original claims, unchanged`).toEqual(before);
      expect(after.length, `${field}: claims added`).toBe(before.length + (VERIFIED_FIELDS.includes(field) ? 1 : 0));
    }
    // Nothing moved, so each verified claim holds the value the page opened with, proposed-a's.
    expect((data.frame as Claim[]).at(-1)).toEqual({ provenance: "verified-jake", value: frameA.value });
    expect((data.counts as Claim[]).at(-1)).toEqual({ provenance: "verified-jake", value: countsA.value });
    expect((data.construction_class as Claim[]).at(-1)).toEqual({ provenance: "verified-jake", value: classA.value });
    expectValidAnnotation(saved.file);
  });

  test("the pin drill starts at the neutral inset and records a drag, a nudge and a count in order", async ({
    page,
  }) => {
    const original = readAnnotation();
    const start = claimBy(original.frame, "proposed-a").value as FrameValue;
    await openLacma(page);
    for (const name of CORNERS) await expectPinAt(page, `outer.${name}`, start.outer_edge.corners[name]);

    await page.getByTestId("drill-start").click();
    await expect(page.getByTestId("mode")).toHaveText("Pin drill: the annotation is hidden; 0 records");
    for (const name of CORNERS) await expectPinAt(page, `outer.${name}`, LACMA_INSET[name]);
    await expect(pin(page, "field.top_left")).toHaveCount(0);

    const id = "outer.top_left";
    const target = { x: 400, y: 450 };
    const box = await mouseDrag(page, id, target, LACMA_CANVAS);
    const dropped = await pinPoint(page, id);
    expectWithinScreenPixel(dropped, target, box, LACMA_CANVAS, `${id} drop`);
    await pin(page, id).focus();
    await page.keyboard.press("ArrowRight");
    await expectPinAt(page, id, { x: dropped.x + 1, y: dropped.y });
    await page.getByTestId("counts-across-blocks-inc").click();
    await expect(page.getByTestId("mode")).toHaveText("Pin drill: the annotation is hidden; 3 records");

    await expect(page.getByTestId("save")).toHaveText("Save drill records");
    const saved = await saveJson(page, "lacma-54871.drill.json", "drill");
    const log = saved.data;
    expect(log).toMatchObject({
      drill_version: 1,
      photo: "images/lacma-54871.jpg",
      sha256: original.sha256,
      canvas: [3873, 4096],
      frame_mode: "outer_edge",
      // DESKTOP_OPTIONS: 1440 x 900, Playwright's default scale factor 1, and no touch, so a fine pointer.
      device: { viewport_width: 1440, viewport_height: 900, device_pixel_ratio: 1, pointer: "fine" },
    });
    expect(Number.isNaN(Date.parse(String(log.started_at))), "started_at is a date").toBe(false);
    const records = log.records as DrillRecord[];
    expect(records).toEqual([
      { seq: 1, t_ms: expect.any(Number), kind: "pin", pin: id, x: dropped.x, y: dropped.y, input: "pointer" },
      // One ArrowRight moves the pin 1 source pixel: x + 1.
      { seq: 2, t_ms: expect.any(Number), kind: "pin", pin: id, x: dropped.x + 1, y: dropped.y, input: "key" },
      // The drill starts at 1 x 1 on each axis; one press makes 1 + 1 = 2 blocks across.
      {
        seq: 3,
        t_ms: expect.any(Number),
        kind: "counts",
        counts: { blocks_across: 2, blocks_down: 1, squares_per_block_across: 1, squares_per_block_down: 1 },
      },
    ]);
    expect(records[0].t_ms).toBeGreaterThanOrEqual(0);
    for (let i = 1; i < records.length; i++) {
      expect(records[i].t_ms, `record ${i + 1} t_ms`).toBeGreaterThanOrEqual(records[i - 1].t_ms);
    }

    await page.getByTestId("drill-stop").click();
    await expect(page.getByTestId("mode")).toHaveText("Verifying, starting from proposed-a");
    for (const name of CORNERS) await expectPinAt(page, `outer.${name}`, start.outer_edge.corners[name]);
  });
});

test.describe("annotate page with touch on an iPhone 13", { tag: "@phone" }, () => {
  test.use(IPHONE_OPTIONS);

  test("one finger drags a pin, a drag off the pins moves nothing, and two fingers pinch to zoom", async ({
    page,
  }) => {
    await openQuilt(page);
    // Records each pointerdown's type, so the test shows its input arrived as touch, not as a mouse.
    await page.evaluate(() => {
      const types: string[] = [];
      Object.assign(window, { pointerTypes: types });
      window.addEventListener("pointerdown", (event) => types.push(event.pointerType), true);
    });
    const pointerTypes = () => page.evaluate(() => (window as unknown as { pointerTypes: string[] }).pointerTypes);
    const cdp = await page.context().newCDPSession(page);
    const view = page.getByTestId("pin-view");
    const id = "outer.top_left";
    await expectPinAt(page, id, QUILT_INSET.top_left);
    await expect(view).toHaveAttribute("data-scale", "1.000");

    const box = await touchDrag(page, cdp, id, OUTER.top_left, QUILT);
    expectWithinScreenPixel(await pinPoint(page, id), OUTER.top_left, box, QUILT, `${id} drop`);
    await nudgeTo(page, id, OUTER.top_left);
    await expectKeySteps(page, id, OUTER.top_left);

    // One finger from the middle of the photo, well clear of every pin's 44 px hit area.
    const pins = await allPins(page);
    const photo = await showPhoto(page);
    const from = toScreen(photo, QUILT, { x: 400, y: 300 });
    const to = { x: from.x + 60, y: from.y + 40 };
    await touch(cdp, "touchStart", [from]);
    for (const t of [0.25, 0.5, 0.75, 1]) await touch(cdp, "touchMove", [between(from, to, t)]);
    await expect(page.getByTestId("loupe")).toHaveCount(0);
    await touch(cdp, "touchEnd", []);
    expect(await allPins(page), "a drag off the pins moves no pin").toEqual(pins);
    await expect(view).toHaveAttribute("data-scale", "1.000");

    // Two fingers 60 px apart about the photo's middle spread to 180 px apart:
    // scale = 1 x 180 / 60 = 3.
    const mid = { x: Math.round(photo.x + photo.width / 2), y: Math.round(photo.y + photo.height / 2) };
    const fingers = (half: number): Point[] => [
      { x: mid.x - half, y: mid.y },
      { x: mid.x + half, y: mid.y },
    ];
    await touch(cdp, "touchStart", fingers(30));
    for (const half of [45, 60, 75, 90]) await touch(cdp, "touchMove", fingers(half));
    await touch(cdp, "touchEnd", []);
    await expect(view).toHaveAttribute("data-scale", "3.000");
    // The page zoomed its own view, not the browser's.
    expect(await page.evaluate(() => window.visualViewport?.scale ?? 1)).toBe(1);
    expect(await allPins(page), "a pinch moves no pin").toEqual(pins);
    // One finger on the pin, one off the pins, then two for the pinch.
    expect(await pointerTypes()).toEqual(["touch", "touch", "touch", "touch"]);
    await page.getByRole("button", { name: "Fit", exact: true }).tap();
    await expect(view).toHaveAttribute("data-scale", "1.000");

    // Across blocks by stepper, 1 + 1 = 2; down squares typed, 3.
    await page.getByTestId("counts-across-blocks-inc").tap();
    await page.getByTestId("counts-down-squares").fill("3");
    // 2 blocks x 1 square = 2 squares across; 1 block x 3 squares = 3 down.
    await expect(page.getByTestId("counts-across-total")).toHaveText("2 blocks x 1 square = 2 squares");
    await expect(page.getByTestId("counts-down-total")).toHaveText("1 block x 3 squares = 3 squares");

    await expectNoHorizontalOverflow(page, "annotate-phone");
  });
});
