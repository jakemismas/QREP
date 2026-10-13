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
 *
 * Reads after a drop poll: React renders a pointermove's update at a lower
 * priority than the drop's, so a read straight after the input call can see
 * an earlier frame (PR #247 review of 0b7e9a3, major 5).
 *
 * The lacma tests open a copy of corpus/annotations/lacma-54871.json with
 * every verified-jake claim taken out, so verifying that photo on this page
 * and committing the result leaves these tests as they are.
 *
 * Against the deployed site (SPIKE_BASE_URL) the page is absent by design,
 * so only the check that it stays unpublished is registered there.
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
/** PinLayer's hit area, 44 x 44 CSS px at every zoom (criteria U3-3). */
const PIN_HIT_PX = 44;
// Chromium composes transforms in float32, so a pin's scale(1 / 1.5) inside
// the view's scale(1.5) measures 43.99994 px, not 44. A 1/64 px allowance (its
// layout unit) absorbs that rounding only; a box short by any visible amount,
// such as 44 / 1.5 = 29.3 px for a pin that shrank with the view, still fails.
const LAYOUT_UNIT_PX = 1 / 64;

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
const LACMA_PHOTO = "images/lacma-54871.jpg";
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
    // -I: isolated mode keeps the working directory off sys.path, so only scripts/eval and the installed qrep load.
    execFileSync(python, ["-I", "-c", VALIDATE, evalDir, file], { stdio: "pipe" });
  } catch (err) {
    const failed = err as { status?: number | null; stderr?: Buffer | string };
    status = failed.status ?? -1;
    stderr = String(failed.stderr || err);
  }
  expect(status, `${python} refused ${file}: ${stderr}`).toBe(0);
}

/** The committed lacma-54871 annotation with every verified-jake claim taken out. */
function readAnnotation(): Json {
  const committed = JSON.parse(readFileSync(lacmaAnnotation, "utf8")) as Json;
  const stripped: Json = {};
  for (const [field, value] of Object.entries(committed)) {
    if (IDENTITY_FIELDS.includes(field)) {
      stripped[field] = value;
      continue;
    }
    const claims = (value as Claim[]).filter((claim) => claim.provenance !== "verified-jake");
    if (claims.length) stripped[field] = claims;
  }
  return stripped;
}

/** The stripped copy as a file the page can open. */
function lacmaAnnotationFile() {
  return {
    name: "lacma-54871.json",
    mimeType: "application/json",
    buffer: Buffer.from(JSON.stringify(readAnnotation(), null, 2)),
  };
}

function claimBy(claims: unknown, provenance: string): Claim {
  const found = (claims as Claim[] | undefined)?.find((claim) => claim.provenance === provenance);
  if (!found) throw new Error(`no ${provenance} claim`);
  return found;
}

/**
 * Draws the generated quilt on a canvas in the page and returns its PNG
 * bytes; another background gives another photo of the same size.
 */
async function drawQuilt(page: Page, background = "#808080"): Promise<Buffer> {
  const dataUrl = await page.evaluate(
    ({ size, outer, field, cols, rows, square, background }) => {
      const canvas = document.createElement("canvas");
      canvas.width = size.width;
      canvas.height = size.height;
      const ctx = canvas.getContext("2d");
      if (!ctx) throw new Error("this browser has no 2d canvas");
      ctx.fillStyle = background;
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
      background,
    },
  );
  return Buffer.from(dataUrl.slice(dataUrl.indexOf(",") + 1), "base64");
}

// The generated quilt's colors as RGB: the band #1f3a93 and the field's top
// left square #b03a2e, (row + col) % 2 = 0.
const BAND_RGB = [0x1f, 0x3a, 0x93];
const RED_SQUARE_RGB = [0xb0, 0x3a, 0x2e];

// The turned photo: 800 x 600 stored, one color a quadrant, so a view turned
// by its EXIF tag puts other colors under the same point.
const QUADRANT_RGB = {
  top_left: [220, 40, 40],
  top_right: [40, 40, 220],
  bottom_left: [40, 180, 40],
  bottom_right: [230, 220, 40],
};

/** An 800 x 600 JPEG with one color in each quadrant, as stored (no EXIF). */
async function drawQuadrants(page: Page): Promise<Buffer> {
  const dataUrl = await page.evaluate((colors) => {
    const canvas = document.createElement("canvas");
    canvas.width = 800;
    canvas.height = 600;
    const ctx = canvas.getContext("2d");
    if (!ctx) throw new Error("this browser has no 2d canvas");
    const fill = (rgb: number[], x: number, y: number) => {
      ctx.fillStyle = `rgb(${rgb.join(", ")})`;
      ctx.fillRect(x, y, 400, 300);
    };
    fill(colors.top_left, 0, 0);
    fill(colors.top_right, 400, 0);
    fill(colors.bottom_left, 0, 300);
    fill(colors.bottom_right, 400, 300);
    return canvas.toDataURL("image/jpeg", 0.95);
  }, QUADRANT_RGB);
  return Buffer.from(dataUrl.slice(dataUrl.indexOf(",") + 1), "base64");
}

/**
 * The JPEG with an EXIF APP1 segment right after its SOI marker, built by
 * hand as in src/dev/annotate/orientation.test.ts: FF E1, length 0x22 = 2 +
 * 6 ("Exif" 00 00) + 8 (TIFF header MM 00 2A, IFD0 at 8) + 2 (one entry) + 12
 * (tag 0x0112 Orientation, type 3 SHORT, count 1, the value) + 4 (no next IFD)
 * = 34.
 */
function withExifOrientation(jpeg: Buffer, orientation: number): Buffer {
  expect([jpeg[0], jpeg[1]], "a JPEG starts with FF D8").toEqual([0xff, 0xd8]);
  const app1 = Buffer.from([
    0xff, 0xe1, 0x00, 0x22, 0x45, 0x78, 0x69, 0x66, 0x00, 0x00,
    0x4d, 0x4d, 0x00, 0x2a, 0x00, 0x00, 0x00, 0x08,
    0x00, 0x01,
    0x01, 0x12, 0x00, 0x03, 0x00, 0x00, 0x00, 0x01, 0x00, orientation, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00,
  ]);
  return Buffer.concat([jpeg.subarray(0, 2), app1, jpeg.subarray(2)]);
}

/** Opens the generated quilt in the page and waits for its hash. */
async function loadQuilt(page: Page, png: Buffer): Promise<string> {
  await page.getByTestId("photo-input").setInputFiles({ name: QUILT_NAME, mimeType: "image/png", buffer: png });
  // Node's hash is the oracle for the page's own SHA-256.
  const sha = createHash("sha256").update(png).digest("hex");
  await expect(page.getByTestId("identity")).toHaveText(`Canvas 800 x 600 px; sha256 ${sha}`);
  await expect(page.locator("[data-pin-id]").first()).toBeVisible();
  return sha;
}

async function openQuilt(page: Page): Promise<{ png: Buffer; sha: string }> {
  await page.goto("annotate.html");
  const png = await drawQuilt(page);
  return { png, sha: await loadQuilt(page, png) };
}

async function openLacma(page: Page) {
  await page.goto("annotate.html");
  await page.getByTestId("photo-input").setInputFiles(lacmaImage);
  await page.getByTestId("annotation-input").setInputFiles(lacmaAnnotationFile());
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

async function boxOf(page: Page, testId: string): Promise<Box> {
  const box = await page.getByTestId(testId).boundingBox();
  if (!box) throw new Error(`${testId} has no box`);
  return box;
}

/** Scrolls the photo to the top of the viewport and returns the img element's box. */
async function showPhoto(page: Page): Promise<Box> {
  await page.getByTestId("pin-stage").evaluate((el) => el.scrollIntoView({ block: "start" }));
  return boxOf(page, "pin-image");
}

/** Source pixels to client pixels through the image rect, the page's own mapping. */
function toScreen(box: Box, canvas: Size, p: Point): Point {
  return { x: box.x + (p.x * box.width) / canvas.width, y: box.y + (p.y * box.height) / canvas.height };
}

/**
 * A pointer outside the viewport reaches nothing, and the stage clips the
 * zoomed photo, so a drag outside either would fail for the wrong reason.
 */
async function expectReachable(page: Page, p: Point, what: string) {
  const viewport = page.viewportSize();
  if (!viewport) throw new Error("this test needs a fixed viewport");
  const stage = await boxOf(page, "pin-stage");
  const left = Math.max(0, stage.x);
  const top = Math.max(0, stage.y);
  const right = Math.min(viewport.width, stage.x + stage.width);
  const bottom = Math.min(viewport.height, stage.y + stage.height);
  expect(p.x >= left && p.x <= right && p.y >= top && p.y <= bottom, `${what} at (${p.x}, ${p.y}) is reachable`).toBe(true);
}

const between = (a: Point, b: Point, t: number): Point => ({ x: a.x + (b.x - a.x) * t, y: a.y + (b.y - a.y) * t });

/** One screen pixel spans canvas.width / box.width source pixels, and snapping to whole pixels adds up to 0.5 more. */
const screenPixel = (box: Box, canvas: Size) => canvas.width / box.width + 0.5;

/**
 * A drop lands within one screen pixel of its target, which proves the
 * pointer maps through the image rect. Polled, then returned.
 */
async function expectDropNear(page: Page, id: string, target: Point, box: Box, canvas: Size, what: string): Promise<Point> {
  const tolerance = screenPixel(box, canvas);
  await expect
    .poll(
      async () => {
        const at = await pinPoint(page, id);
        return Math.max(Math.abs(at.x - target.x), Math.abs(at.y - target.y));
      },
      { message: `${what}: within ${tolerance.toFixed(2)} source px of (${target.x}, ${target.y})` },
    )
    .toBeLessThanOrEqual(tolerance);
  return pinPoint(page, id);
}

/** The view's pan, from pin-view's own transform: translate(x px, y px) scale(s). */
async function viewTranslate(page: Page): Promise<Point> {
  const style = (await page.getByTestId("pin-view").getAttribute("style")) ?? "";
  const match = /translate\(\s*(-?[\d.e+-]+)px\s*,\s*(-?[\d.e+-]+)px\s*\)/.exec(style);
  if (!match) throw new Error(`pin-view has no translate in "${style}"`);
  return { x: Number(match[1]), y: Number(match[2]) };
}

async function expectPinHitAreas(page: Page, ids: string[], when: string) {
  for (const id of ids) {
    const box = await boxOf(page, `pin-${id}`);
    expect(box.width, `${id} width ${when}`).toBeGreaterThanOrEqual(PIN_HIT_PX - LAYOUT_UNIT_PX);
    expect(box.height, `${id} height ${when}`).toBeGreaterThanOrEqual(PIN_HIT_PX - LAYOUT_UNIT_PX);
  }
}

/**
 * The pin's whole box takes a touch: the point 1 px inside each corner of it,
 * and its center, hit that pin. boundingBox alone ignores clipping, so a box
 * the stage cuts in half still measures 44 x 44 (PR #247 review of 0b7e9a3,
 * major 1).
 */
async function expectWholeHitArea(page: Page, id: string, when: string) {
  const box = await boxOf(page, `pin-${id}`);
  expect(box.width, `${id} width ${when}`).toBeGreaterThanOrEqual(PIN_HIT_PX - LAYOUT_UNIT_PX);
  expect(box.height, `${id} height ${when}`).toBeGreaterThanOrEqual(PIN_HIT_PX - LAYOUT_UNIT_PX);
  const probes = [
    { x: box.x + 1, y: box.y + 1 },
    { x: box.x + box.width - 1, y: box.y + 1 },
    { x: box.x + 1, y: box.y + box.height - 1 },
    { x: box.x + box.width - 1, y: box.y + box.height - 1 },
    { x: box.x + box.width / 2, y: box.y + box.height / 2 },
  ];
  const hits = await page.evaluate(
    (points) =>
      points.map((p) => document.elementFromPoint(p.x, p.y)?.closest("[data-pin-id]")?.getAttribute("data-pin-id") ?? null),
    probes,
  );
  expect(hits, `${id}: each corner and the center of its box ${when}`).toEqual(probes.map(() => id));
}

/** A mouse drag that starts on the stage's middle, where no test puts a pin. */
async function panBy(page: Page, dx: number, dy: number) {
  const stage = await boxOf(page, "pin-stage");
  const grab = { x: Math.round(stage.x + stage.width / 2), y: Math.round(stage.y + stage.height / 2) };
  await expectReachable(page, { x: grab.x + dx, y: grab.y + dy }, "the pan's end");
  await page.mouse.move(grab.x, grab.y);
  await page.mouse.down();
  await page.mouse.move(grab.x + dx, grab.y + dy, { steps: 4 });
  await page.mouse.up();
}

/** The loupe's RGB at points given as fractions of its size. */
async function loupePixels(page: Page, at: Point[]): Promise<number[][]> {
  return page.getByTestId("loupe").evaluate((el, points) => {
    const canvas = el as HTMLCanvasElement;
    const ctx = canvas.getContext("2d");
    if (!ctx) throw new Error("the loupe has no 2d context");
    return points.map((p) =>
      Array.from(ctx.getImageData(Math.floor(p.x * canvas.width), Math.floor(p.y * canvas.height), 1, 1).data.slice(0, 3)),
    );
  }, at);
}

interface LoupeProbe {
  name: string;
  /** Fractions of the loupe's size. */
  at: Point;
  rgb: number[];
}

/** The loupe draws the photo under the pin: each probe shows its color within tolerance per channel. Polled, since it draws after a render. */
async function expectLoupeShows(page: Page, probes: LoupeProbe[], tolerance: number, what: string) {
  await expect
    .poll(
      async () => {
        const got = await loupePixels(page, probes.map((p) => p.at));
        return probes
          .map((p, i) => ({ p, rgb: got[i] }))
          .filter(({ p, rgb }) => rgb.some((value, k) => Math.abs(value - p.rgb[k]) > tolerance))
          .map(({ p, rgb }) => `${p.name}: ${rgb.join(", ")} for ${p.rgb.join(", ")}`);
      },
      { message: `${what}: the loupe shows the photo under the pin` },
    )
    .toEqual([]);
}

/**
 * The loupe spans LOUPE_CSS_PX / (shown x LOUPE_MAGNIFICATION) source pixels,
 * 128 / (shown x 3), where shown is box.width / canvas.width screen pixels a
 * source pixel (src/confirm/Loupe.tsx). A probe a quarter of the way in from
 * an edge sits a quarter span from the pin.
 */
const loupeQuarterSpan = (box: Box, canvas: Size) => 128 / ((box.width / canvas.width) * 3) / 4;

interface DragOptions {
  /** The loupe's side at the drop: right while the pin shows in the stage's top left quarter. */
  side?: "left" | "right";
  /** Runs at the drop, before the pointer lifts. */
  atDrop?: () => Promise<void>;
}

async function mouseDrag(page: Page, id: string, target: Point, canvas: Size, options: DragOptions = {}): Promise<Box> {
  const box = await showPhoto(page);
  const from = toScreen(box, canvas, await pinPoint(page, id));
  const to = toScreen(box, canvas, target);
  await expectReachable(page, from, `${id} start`);
  await expectReachable(page, to, `${id} target`);
  await page.mouse.move(from.x, from.y);
  await page.mouse.down();
  const mid = between(from, to, 0.5);
  await page.mouse.move(mid.x, mid.y, { steps: 4 });
  await expect(page.getByTestId("loupe"), `${id}: loupe while dragging`).toBeVisible();
  await page.mouse.move(to.x, to.y, { steps: 4 });
  if (options.side) await expect(page.getByTestId("loupe"), `${id}: loupe side`).toHaveAttribute("data-side", options.side);
  if (options.atDrop) await options.atDrop();
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

/** One finger from the pin's spot to target; the photo is not scrolled, so a zoomed view keeps its pan. */
async function touchDrag(page: Page, cdp: CDPSession, id: string, target: Point, canvas: Size): Promise<Box> {
  const box = await boxOf(page, "pin-image");
  const from = toScreen(box, canvas, await pinPoint(page, id));
  const to = toScreen(box, canvas, target);
  await expectReachable(page, from, `${id} start`);
  await expectReachable(page, to, `${id} target`);
  await touch(cdp, "touchStart", [from]);
  for (const t of [0.25, 0.5]) await touch(cdp, "touchMove", [between(from, to, t)]);
  await expect(page.getByTestId("loupe"), `${id}: loupe while dragging`).toBeVisible();
  for (const t of [0.75, 1]) await touch(cdp, "touchMove", [between(from, to, t)]);
  // A finger rests on its spot before it lifts. CDP moves arrive all at once,
  // so lifting straight away reads as a flick, and Chromium then swallows the
  // click of the next tap (seen as a Fit tap that delivered no click). The
  // wait is a floor on the rest, so a loaded machine only makes it longer.
  await page.waitForTimeout(100);
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

/** A mouse drop, checked against one screen pixel, then nudged onto target exactly. */
async function placeByMouse(page: Page, id: string, target: Point, canvas: Size, options: DragOptions = {}) {
  const box = await mouseDrag(page, id, target, canvas, options);
  await expectDropNear(page, id, target, box, canvas, `${id} drop`);
  await nudgeTo(page, id, target);
}

/** Presses key on the pin times times. */
async function pressOn(page: Page, id: string, key: string, times: number) {
  await pin(page, id).focus();
  for (let i = 0; i < times; i++) await page.keyboard.press(key);
}

/** The band's width in squares, from its label: "1.0244 squares" or "1 square, 1 1/2 in". */
async function bandWidth(page: Page, band: number): Promise<number> {
  return Number.parseFloat((await page.getByTestId(`band-${band}-width`).textContent()) ?? "");
}

// The page rounds a width to four decimals (bands.ts roundWidth), so a bound
// on it rounds outward the same way.
const roundDown4 = (value: number) => Math.floor(value * 1e4) / 1e4;
const roundUp4 = (value: number) => Math.ceil(value * 1e4) / 1e4;

/** The band's width is within tolerance of expected squares. Polled. */
async function expectBandWidth(page: Page, band: number, expected: number, tolerance: number, what: string) {
  await expect
    .poll(async () => Math.abs((await bandWidth(page, band)) - expected), { message: `${what}: band ${band} width near ${expected}` })
    .toBeLessThanOrEqual(tolerance);
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

/** The square grid's vertical lines, from the d attribute GridOverlay writes as M x y L x y per segment. */
async function verticalSquareLines(page: Page): Promise<[Point, Point][]> {
  const d = (await page.locator("path.cf-grid__square").getAttribute("d")) ?? "";
  const number = "(-?[\\d.]+(?:e[+-]?\\d+)?)";
  const segment = new RegExp(`M${number} ${number}L${number} ${number}`, "g");
  const lines: [Point, Point][] = [];
  for (const m of d.matchAll(segment)) {
    const a = { x: Number(m[1]), y: Number(m[2]) };
    const b = { x: Number(m[3]), y: Number(m[4]) };
    if (Math.abs(a.x - b.x) < 1e-6) lines.push([a, b]);
  }
  return lines;
}

if (process.env.SPIKE_BASE_URL) {
  // .github/workflows/pages.yml's live-spike job runs every spec against the
  // deployed Pages site, where web/scripts/compose-site.mjs leaves the dev
  // page out (ux-24): the page tests would each wait out the timeout there,
  // so the one check on the live site is that the page stays unpublished.
  test("the deployed site does not serve the dev annotate page", { tag: "@phone" }, async ({ request }) => {
    const response = await request.get("annotate.html");
    expect(response.status()).toBe(404);
  });
} else {
  test.describe("annotate page with a mouse at 1440 x 900", { tag: "@phone" }, () => {
    test.use(DESKTOP_OPTIONS);

    test("a mouse drags, nudges, zooms, bands, seeds and counts a generated quilt, and the saved JSON is its hand geometry", async ({
      page,
    }) => {
      const { sha } = await openQuilt(page);
      const outerIds = CORNERS.map((name) => `outer.${name}`);
      for (const name of CORNERS) await expectPinAt(page, `outer.${name}`, QUILT_INSET[name]);
      const view = page.getByTestId("pin-view");
      await expect(view).toHaveAttribute("data-scale", "1.000");

      // A right button press on a pin drags nothing: it opens the browser's
      // menu and may never send pointerup (PinLayer's primary-button guard).
      const fitBox = await showPhoto(page);
      const rightStart = toScreen(fitBox, QUILT, QUILT_INSET.top_right);
      await page.mouse.move(rightStart.x, rightStart.y);
      await page.mouse.down({ button: "right" });
      await page.mouse.move(rightStart.x - 40, rightStart.y + 40, { steps: 4 });
      await expect(page.getByTestId("loupe"), "no loupe on a right-button drag").toHaveCount(0);
      await page.mouse.up({ button: "right" });
      await page.keyboard.press("Escape");
      await expectPinAt(page, "outer.top_right", QUILT_INSET.top_right);

      // The hit area holds at fit and, through the pins' counter-scale, after a zoom.
      await expectPinHitAreas(page, outerIds, "at fit");
      await page.getByRole("button", { name: "Zoom in", exact: true }).click();
      // One step of ZOOM_STEP from fit: 1 x 1.5 = 1.5.
      await expect(view).toHaveAttribute("data-scale", "1.500");
      await expectPinHitAreas(page, outerIds, "at 1.5");

      // A mouse drag from the stage's middle, which shows source (400, 300) with
      // no pin near it, pans the view by the pointer's move. The zoom about the
      // middle put the view at -w/4, -h/4; moving (-60, -40) stays inside the
      // clamp of -w/2, -h/2 because w/4 and h/4 exceed 60 and 40 at this size.
      await showPhoto(page);
      const pins = await allPins(page);
      const stage = await boxOf(page, "pin-stage");
      const grab = { x: Math.round(stage.x + stage.width / 2), y: Math.round(stage.y + stage.height / 2) };
      const panned = await viewTranslate(page);
      await page.mouse.move(grab.x, grab.y);
      await page.mouse.down();
      await page.mouse.move(grab.x - 30, grab.y - 20, { steps: 3 });
      await expect(page.getByTestId("loupe"), "no loupe while panning").toHaveCount(0);
      await page.mouse.move(grab.x - 60, grab.y - 40, { steps: 3 });
      await page.mouse.up();
      // React renders a pointermove after the input call returns, so the pan is polled.
      await expect.poll(async () => (await viewTranslate(page)).x - panned.x, { message: "pan x" }).toBeCloseTo(-60, 2);
      await expect.poll(async () => (await viewTranslate(page)).y - panned.y, { message: "pan y" }).toBeCloseTo(-40, 2);
      expect(await allPins(page), "a pan moves no pin").toEqual(pins);
      await page.getByRole("button", { name: "Fit", exact: true }).click();
      await expect(view).toHaveAttribute("data-scale", "1.000");
      expect(await viewTranslate(page)).toEqual({ x: 0, y: 0 });

      // The loupe sits in the stage's top left corner, so it moves right while
      // the pin shows in the stage's top left quarter: only top_left's target,
      // (100, 100) of 800 x 600, is in that quarter.
      for (const name of CORNERS) {
        await placeByMouse(page, `outer.${name}`, OUTER[name], QUILT, { side: name === "top_left" ? "right" : "left" });
      }
      await expectKeySteps(page, "outer.top_left", OUTER.top_left);

      // No square size yet, so inches are off, and no band exists.
      await expect(page.getByTestId("bands-inches-off")).toBeVisible();
      await expect(page.getByTestId("band-1")).toHaveCount(0);
      await page.getByTestId("band-add").click();
      // A new band starts 1 square wide, the width the seed below needs.
      await expect(page.getByTestId("band-1-width")).toHaveText("1 square");
      await expect(page.getByTestId("band-2")).toHaveCount(0);
      await expect(page.getByTestId("band-line-1")).toHaveCount(1);

      // Seed the counts from one field square, with the band at exactly 1 square.
      await page.getByTestId("measure-square").click();
      // Counts 1 x 1 and one band of 1: 1 / (1 + 2 x 1) = 1/3 exceeds a tenth,
      // so the pins start a tenth apart about the middle, at u, v = 0.45 and
      // 0.55: (100 + 600 x 0.45, 100 + 400 x 0.45) = (370, 280) and (100 + 600 x
      // 0.55, 100 + 400 x 0.55) = (430, 320).
      await expectPinAt(page, "square.a", { x: 370, y: 280 });
      await expectPinAt(page, "square.b", { x: 430, y: 320 });
      // The field's top left square: (150, 150) to (150 + 50, 150 + 50) = (200, 200).
      // Held at (150, 150), the field's corner, the loupe's four quarters show
      // what lies around it: the band up and to the left, the red top left
      // square down and to the right. A probe a quarter of the loupe in from
      // its corner sits a quarter span from the pin; that must clear the
      // drop's error and stay inside the 50 px square, or the probes would
      // straddle an edge.
      const fieldCorner = { x: 150, y: 150 };
      await placeByMouse(page, "square.a", fieldCorner, QUILT, {
        side: "right",
        atDrop: async () => {
          const box = await boxOf(page, "pin-image");
          const quarter = loupeQuarterSpan(box, QUILT);
          const slack = screenPixel(box, QUILT);
          expect(quarter, "a quarter span clears the drop's error").toBeGreaterThan(slack);
          expect(quarter + slack, "a quarter span stays inside one square").toBeLessThan(50);
          await expectLoupeShows(
            page,
            [
              { name: "up and left", at: { x: 0.25, y: 0.25 }, rgb: BAND_RGB },
              { name: "up and right", at: { x: 0.75, y: 0.25 }, rgb: BAND_RGB },
              { name: "down and left", at: { x: 0.25, y: 0.75 }, rgb: BAND_RGB },
              { name: "down and right", at: { x: 0.75, y: 0.75 }, rgb: RED_SQUARE_RGB },
            ],
            // A lossless PNG drawn unsmoothed: only color management can move a channel, and not by 8.
            8,
            "square.a at the field's corner",
          );
        },
      });
      await placeByMouse(page, "square.b", { x: 200, y: 200 }, QUILT, { side: "right" });
      await page.getByTestId("square-use").click();
      await expect(pin(page, "square.a")).toHaveCount(0);
      // The square spans 50 / 600 of the outer edge across, so 600 / 50 = 12
      // squares across it, less 2 x 1 band square = 10 field columns; down 50 /
      // 400, so 8 less 2 = 6 rows. From 1 x 1 counts, seedAxis keeps 1 square a
      // block (10 % 1 = 0 and 6 % 1 = 0), so 10 blocks and 6 blocks.
      await expect(page.getByTestId("counts-across-total")).toHaveText("10 blocks x 1 square = 10 squares");
      await expect(page.getByTestId("counts-down-total")).toHaveText("6 blocks x 1 square = 6 squares");

      // To 2 x 5 across: blocks typed, 2; squares by stepper, 1 + 4 = 5.
      await page.getByTestId("counts-across-blocks").fill("2");
      for (let i = 0; i < 4; i++) await page.getByTestId("counts-across-squares-inc").click();
      await expect(page.getByTestId("counts-across-squares")).toHaveValue("5");
      // To 2 x 3 down: blocks by stepper, 6 - 4 = 2; squares typed, 3.
      for (let i = 0; i < 4; i++) await page.getByTestId("counts-down-blocks-dec").click();
      await expect(page.getByTestId("counts-down-blocks")).toHaveValue("2");
      await page.getByTestId("counts-down-squares").fill("3");
      // 2 x 5 = 10 squares across, 2 x 3 = 6 down.
      await expect(page.getByTestId("counts-across-total")).toHaveText("2 blocks x 5 squares = 10 squares");
      await expect(page.getByTestId("counts-down-total")).toHaveText("2 blocks x 3 squares = 6 squares");
      const grid = page.getByTestId("grid-overlay");
      await expect(grid).toHaveAttribute("data-cols", "10");
      await expect(grid).toHaveAttribute("data-rows", "6");

      // Square lines run on the field, not the outer edge: 10 columns make 10 +
      // 1 = 11 vertical lines from x 150 to x 650, the second at 150 + 50 = 200,
      // each from the field's top y 150 to its bottom y 450.
      const verticals = await verticalSquareLines(page);
      expect(verticals).toHaveLength(11);
      const second = verticals.find(([a]) => Math.abs(a.x - 200) < 1e-6);
      expect(second, "a vertical square line at x 200").toBeDefined();
      if (second) {
        const [top, bottom] = second;
        expect(Math.abs(top.x - 200)).toBeLessThan(1e-6);
        expect(Math.abs(top.y - 150)).toBeLessThan(1e-6);
        expect(Math.abs(bottom.x - 200)).toBeLessThan(1e-6);
        expect(Math.abs(bottom.y - 450)).toBeLessThan(1e-6);
      }
      for (const [a] of verticals) expect(a.x, "no square line left of the field").toBeGreaterThanOrEqual(150 - 1e-6);

      await page.getByTestId("band-1-inc").click();
      // Steppers move whole squares: 1 + 1 = 2 squares.
      await expect(page.getByTestId("band-1-width")).toHaveText("2 squares");
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
      // Band 1's inner line at 2 squares sits 2 / (10 + 2 x 2) = 1/7 of the way
      // in, so the left handle is at x = 100 + 600 / 7 = 185.714, y = 100 + 400
      // x 0.5 = 300.
      const handle = await pinPoint(page, "band.left");
      expect(handle.x).toBeCloseTo(100 + 600 / 7, 6);
      expect(handle.y).toBeCloseTo(300, 6);

      // Each handle, dragged on its own axis, sets the one band's width. With
      // one band, bands.ts widthFromDepth gives w = f N / (1 - 2f) for a line
      // at depth f on an axis of N squares: N = 10 across for left and right,
      // 6 down for top and bottom. Each drop lands within one screen pixel,
      // which snaps to the target or a whole pixel either side (800 /
      // box.width + 0.5 is under 2 at this width), so each width is checked
      // at the target, within the band the two neighbouring pixels give.
      //   left to x 150: f = 50 / 600 = 1/12, w = (10/12) / (10/12) = 1;
      //     x 149: f = 49/600, w = 0.8167 / 0.8367 = 0.976; x 151: 0.85 / 0.83 = 1.024.
      //   top to y 180: f = 80 / 400 = 0.2, w = 1.2 / 0.6 = 2;
      //     y 179: f = 0.1975, w = 1.185 / 0.605 = 1.959; y 181: 1.215 / 0.595 = 2.042.
      //   right to x 640: f = 60 / 600 = 0.1, w = 1 / 0.8 = 1.25;
      //     x 641: f = 59/600, w = 0.9833 / 0.8033 = 1.224; x 639: 1.0167 / 0.7967 = 1.276.
      //   bottom to y 460: f = 40 / 400 = 0.1, w = 0.6 / 0.8 = 0.75;
      //     y 461: f = 0.0975, w = 0.585 / 0.805 = 0.727; y 459: 0.615 / 0.795 = 0.774.
      // Every neighbour is within 0.05 of its target width.
      const handleDrags: { side: string; target: Point; width: number }[] = [
        { side: "left", target: { x: 150, y: 300 }, width: 1 },
        { side: "top", target: { x: 400, y: 180 }, width: 2 },
        { side: "right", target: { x: 640, y: 300 }, width: 1.25 },
        { side: "bottom", target: { x: 400, y: 460 }, width: 0.75 },
      ];
      for (const { side, target, width } of handleDrags) {
        const id = `band.${side}`;
        const box = await mouseDrag(page, id, target, QUILT);
        expect(screenPixel(box, QUILT), "a drop lands on its target or a whole pixel either side").toBeLessThan(2);
        await expectBandWidth(page, 1, width, 0.05, `${id} drop`);
        // The handle follows the band's new inner line, at the drop.
        await expectDropNear(page, id, target, box, QUILT, `${id} drop`);
      }
      const widthLabel = page.getByTestId("band-1-width");
      await expect(widthLabel).toHaveText(/^\d+(\.\d+)? squares?$/);

      await page.getByTestId("square-size").selectOption("12");
      await expect(page.getByTestId("bands-inches-off")).toHaveCount(0);
      const inches = page.getByTestId("band-1-inches");
      await expect(inches).toBeEnabled();
      // Leaving the field without typing keeps the dragged width: rounding the
      // shown inches to 1/4 in would move it (0.75 squares x 1.5 in = 1.125 in
      // rounds to 1.25 in, 0.8333 squares).
      const dragged = (await widthLabel.textContent()) ?? "";
      expect(dragged).toMatch(/ in$/);
      await inches.focus();
      await page.keyboard.press("Tab");
      await expect(inches).not.toBeFocused();
      await expect(widthLabel).toHaveText(dragged);
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
      // A field pin moves on its own: its top left to (150 + 10, 150 + 10) = (160, 160).
      const fieldTopLeft = { x: 160, y: 160 };
      await placeByMouse(page, "field.top_left", fieldTopLeft, QUILT);
      const savedField: Corners = { ...FIELD, top_left: fieldTopLeft };
      for (const name of CORNERS) await expectPinAt(page, `field.${name}`, savedField[name]);

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
              field: { kind: "field", corners: savedField },
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

    test("a pin on the photo's edge keeps its whole hit area at fit and zoomed with the view at that edge", async ({
      page,
    }) => {
      await openQuilt(page);
      // Keys take two pins onto the photo's corners. From the inset (120, 90):
      // 12 Shift+Left presses of 10 px give 120 - 120 = 0, 9 Shift+Up give 90 -
      // 90 = 0. From (680, 510): 12 Shift+Right give 680 + 120 = 800 and 9
      // Shift+Down give 510 + 90 = 600, the far edges, where snapToPixel stops.
      await pressOn(page, "outer.top_left", "Shift+ArrowLeft", 12);
      await pressOn(page, "outer.top_left", "Shift+ArrowUp", 9);
      await pressOn(page, "outer.bottom_right", "Shift+ArrowRight", 12);
      await pressOn(page, "outer.bottom_right", "Shift+ArrowDown", 9);
      await expectPinAt(page, "outer.top_left", { x: 0, y: 0 });
      await expectPinAt(page, "outer.bottom_right", { x: 800, y: 600 });

      const fit = await showPhoto(page);
      await expectWholeHitArea(page, "outer.top_left", "at fit");
      await expectWholeHitArea(page, "outer.bottom_right", "at fit");

      const view = page.getByTestId("pin-view");
      await page.getByRole("button", { name: "Zoom in", exact: true }).click();
      await expect(view).toHaveAttribute("data-scale", "1.500");
      // The zoom about the middle put the view at (-w/4, -h/4), w and h the
      // photo's fit size (about -180 and -135 here). A pan of (+300, +250) runs
      // past the clamp, which stops at (0, 0): the photo's top left corner a
      // gutter inside the stage's.
      await panBy(page, 300, 250);
      await expect.poll(async () => viewTranslate(page), { message: "panned to the top left" }).toEqual({ x: 0, y: 0 });
      await expectWholeHitArea(page, "outer.top_left", "at 1.5, the view at the top left");
      // Two pans of (-250, -200) run past the other clamp, at w (1 - 1.5) =
      // -w / 2 and -h / 2: the photo's bottom right corner a gutter inside.
      await panBy(page, -250, -200);
      await panBy(page, -250, -200);
      await expect.poll(async () => (await viewTranslate(page)).x, { message: "panned to the right" }).toBeCloseTo(-fit.width / 2, 1);
      await expect.poll(async () => (await viewTranslate(page)).y, { message: "panned to the bottom" }).toBeCloseTo(-fit.height / 2, 1);
      await expectWholeHitArea(page, "outer.bottom_right", "at 1.5, the view at the bottom right");
    });

    test("a JPEG tagged EXIF orientation 6 opens as stored: the canvas, the pins and the loupe index the stored pixels", async ({
      page,
    }) => {
      await page.goto("annotate.html");
      const tagged = withExifOrientation(await drawQuadrants(page), 6);
      // The fixture works as a test only if this browser turns it: shown as a
      // plain image, orientation 6 (a quarter turn clockwise) swaps 800 x 600
      // to 600 x 800.
      const turned = await page.evaluate(async (base64) => {
        const bytes = Uint8Array.from(atob(base64), (c) => c.charCodeAt(0));
        const img = new Image();
        img.src = URL.createObjectURL(new Blob([bytes], { type: "image/jpeg" }));
        await img.decode();
        return { width: img.naturalWidth, height: img.naturalHeight };
      }, tagged.toString("base64"));
      expect(turned, "this browser turns the tagged JPEG").toEqual({ width: 600, height: 800 });

      await page.getByTestId("photo-input").setInputFiles({ name: "turned.jpg", mimeType: "image/jpeg", buffer: tagged });
      // The page hashes the file as it is, tag and all.
      const sha = createHash("sha256").update(tagged).digest("hex");
      await expect(page.getByTestId("identity")).toHaveText(`Canvas 800 x 600 px; sha256 ${sha}`);
      for (const name of CORNERS) await expectPinAt(page, `outer.${name}`, QUILT_INSET[name]);
      const box = await showPhoto(page);
      // Shown as stored: 800 / 600 = 1.333 wide for 1 high.
      expect(box.width / box.height).toBeCloseTo(800 / 600, 2);

      // The loupe draws the stored pixels too. Held at (200, 150), the middle of
      // the stored top left quadrant, it shows that quadrant's red; a view
      // turned by the tag would put the stored point (150, 399), in the green
      // bottom left quadrant, under the same coordinates. Then (600, 450), the
      // middle of the bottom right, shows yellow. A probe a quarter span from
      // the pin stays inside a 400 x 300 quadrant's middle 100 px.
      const quadrantProbes = (rgb: number[]): LoupeProbe[] => [
        { name: "up and left", at: { x: 0.25, y: 0.25 }, rgb },
        { name: "down and right", at: { x: 0.75, y: 0.75 }, rgb },
      ];
      expect(loupeQuarterSpan(box, QUILT) + screenPixel(box, QUILT)).toBeLessThan(100);
      // JPEG at quality 0.95 shifts a flat color by a few levels; 30 still
      // tells red, blue, green and yellow apart by far.
      for (const [target, rgb, side] of [
        [{ x: 200, y: 150 }, QUADRANT_RGB.top_left, "right"],
        [{ x: 600, y: 450 }, QUADRANT_RGB.bottom_right, "left"],
      ] as const) {
        const dragBox = await mouseDrag(page, "outer.top_left", target, QUILT, {
          side,
          atDrop: () => expectLoupeShows(page, quadrantProbes([...rgb]), 30, `held at (${target.x}, ${target.y})`),
        });
        await expectDropNear(page, "outer.top_left", target, dragBox, QUILT, "outer.top_left drop");
      }
    });

    test("a field-corner frame saves with no border and reopens in field mode", async ({ page }) => {
      const { png, sha } = await openQuilt(page);
      await page.getByTestId("frame-mode").selectOption("field");
      await expect(pin(page, "outer.top_left")).toHaveCount(0);
      // The field pins start where the outer ones were: with no bands the field
      // range is the whole outer edge (u = 0 / (1 + 0) = 0), so the inset corners.
      for (const name of CORNERS) await expectPinAt(page, `field.${name}`, QUILT_INSET[name]);
      for (const name of CORNERS) await placeByMouse(page, `field.${name}`, FIELD[name], QUILT);

      await page.getByTestId("construction-class").selectOption("squares");
      const saved = await saveJson(page, "generated-quilt.json", "field");
      // A field frame saves as an outer edge equal to the field with no bands
      // (corpus/README.md: no border means no bands); counts stay at 1 x 1.
      expect(saved.data).toEqual({
        schema_version: 1,
        photo: QUILT_NAME,
        sha256: sha,
        canvas: [800, 600],
        frame: [
          {
            provenance: "verified-jake",
            value: {
              outer_edge: { kind: "outer_edge", corners: FIELD, bands: [] },
              field: { kind: "field", corners: FIELD },
            },
          },
        ],
        counts: [
          {
            provenance: "verified-jake",
            value: { blocks_across: 1, blocks_down: 1, squares_per_block_across: 1, squares_per_block_down: 1 },
          },
        ],
        construction_class: [{ provenance: "verified-jake", value: "squares" }],
      });
      expectValidAnnotation(saved.file);

      await page.reload();
      await loadQuilt(page, png);
      await page.getByTestId("annotation-input").setInputFiles(saved.file);
      await expect(page.getByTestId("mode")).toHaveText("Verifying, starting from verified-jake");
      await expect(page.getByTestId("frame-mode")).toHaveValue("field");
      await expect(pin(page, "outer.top_left")).toHaveCount(0);
      for (const name of CORNERS) await expectPinAt(page, `field.${name}`, FIELD[name]);

      // Another photo of the canvas's size under the same name keeps the
      // annotation by its stem, but its sha256 is not the annotation's, so the
      // page refuses it instead of saving its pins under the first photo's
      // identity (PR #247 review of 0b7e9a3, AnnotatePage.tsx:173).
      const other = await drawQuilt(page, "#5a5a5a");
      const otherSha = createHash("sha256").update(other).digest("hex");
      expect(otherSha).not.toBe(sha);
      await page.getByTestId("photo-input").setInputFiles({ name: QUILT_NAME, mimeType: "image/png", buffer: other });
      await expect(page.getByTestId("sha-error")).toHaveText(
        `This photo's sha256 is ${otherSha}, but the annotation names ${sha}: it is another photo. Open the photo the annotation names.`,
      );
      await expect(page.locator("[data-pin-id]")).toHaveCount(0);
      await expect(page.getByTestId("save")).toHaveCount(0);
    });

    test("a photo with another stem closes the annotation, and an annotation for another photo is refused", async ({
      page,
    }) => {
      await openLacma(page);
      const photoPath = page.getByTestId("photo-path");
      await expect(photoPath).toHaveValue(LACMA_PHOTO);
      await expect(photoPath).not.toBeEditable();

      const png = await drawQuilt(page);
      const sha = await loadQuilt(page, png);
      await expect(page.getByTestId("status")).toHaveText(
        `Closed the annotation for ${LACMA_PHOTO}: it names another photo.`,
      );
      await expect(photoPath).toBeEditable();
      await expect(photoPath).toHaveValue(QUILT_NAME);
      await expect(page.getByTestId("mode")).toHaveText("Verifying a new photo");
      for (const name of CORNERS) await expectPinAt(page, `outer.${name}`, QUILT_INSET[name]);

      // A fresh copy of the file: the input still holds the one opened above, and
      // choosing an unchanged selection again fires no change event (the next test).
      await page.getByTestId("annotation-input").setInputFiles(lacmaAnnotationFile());
      await expect(page.getByTestId("error")).toHaveText(
        `This annotation names ${LACMA_PHOTO}, but the open photo is ${QUILT_NAME}. Open the photo it names first.`,
      );
      await expect(page.getByTestId("identity")).toHaveText(`Canvas 800 x 600 px; sha256 ${sha}`);
      await expect(photoPath).toBeEditable();
      for (const name of CORNERS) await expectPinAt(page, `outer.${name}`, QUILT_INSET[name]);
    });

    test("after a stem mismatch closes it, reopening the photo and then the same annotation file restores it", async ({
      page,
    }) => {
      const start = claimBy(readAnnotation().frame, "proposed-a").value as FrameValue;
      await openLacma(page);
      await loadQuilt(page, await drawQuilt(page));
      await expect(page.getByTestId("status")).toHaveText(
        `Closed the annotation for ${LACMA_PHOTO}: it names another photo.`,
      );
      // The way back after opening the wrong photo: its own photo, then its
      // annotation, chosen from the same file inputs as before.
      await page.getByTestId("photo-input").setInputFiles(lacmaImage);
      await expect(page.getByTestId("photo-path")).toHaveValue("lacma-54871.jpg");
      await page.getByTestId("annotation-input").setInputFiles(lacmaAnnotationFile());
      await expect(page.getByTestId("identity")).toContainText("Canvas 3873 x 4096");
      await expect(page.getByTestId("mode")).toHaveText("Verifying, starting from proposed-a");
      for (const name of CORNERS) await expectPinAt(page, `outer.${name}`, start.outer_edge.corners[name]);
    });

    test("lacma-54871 with no verified claim opens on proposed-a and saves one verified claim beside every original", async ({
      page,
    }) => {
      const original = readAnnotation();
      // The page opens on the verified claim, else proposed-a's: the stripped
      // copy has no verified-jake claim in any field, so it opens on proposed-a's.
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

    test("the pin drill starts at the neutral inset, records drags, nudges, counts and bands in order, and gives back the verify edits", async ({
      page,
    }) => {
      const original = readAnnotation();
      const start = claimBy(original.frame, "proposed-a").value as FrameValue;
      await openLacma(page);
      for (const name of CORNERS) await expectPinAt(page, `outer.${name}`, start.outer_edge.corners[name]);
      // An unsaved verify edit before the drill: one ArrowDown, y + 1.
      const edited: Corners = {
        ...start.outer_edge.corners,
        bottom_right: { x: start.outer_edge.corners.bottom_right.x, y: start.outer_edge.corners.bottom_right.y + 1 },
      };
      await pressOn(page, "outer.bottom_right", "ArrowDown", 1);
      await expectPinAt(page, "outer.bottom_right", edited.bottom_right);

      await page.getByTestId("drill-start").click();
      await expect(page.getByTestId("mode")).toHaveText("Pin drill: the annotation is hidden; 0 records");
      for (const name of CORNERS) await expectPinAt(page, `outer.${name}`, LACMA_INSET[name]);
      await expect(pin(page, "field.top_left")).toHaveCount(0);

      const id = "outer.top_left";
      const target = { x: 400, y: 450 };
      const box = await mouseDrag(page, id, target, LACMA_CANVAS);
      const dropped = await expectDropNear(page, id, target, box, LACMA_CANVAS, `${id} drop`);
      await pin(page, id).focus();
      await page.keyboard.press("ArrowRight");
      await expectPinAt(page, id, { x: dropped.x + 1, y: dropped.y });
      await page.getByTestId("counts-across-blocks-inc").click();
      await expect(page.getByTestId("mode")).toHaveText("Pin drill: the annotation is hidden; 3 records");
      // Typed "24" key by key is one entry once the field is left: "2" and then
      // "24" both parse, so a record a keystroke would make two.
      const downSquares = page.getByTestId("counts-down-squares");
      await downSquares.selectText();
      await downSquares.pressSequentially("24");
      await expect(page.getByTestId("counts-down-total")).toHaveText("1 block x 24 squares = 24 squares");
      await expect(page.getByTestId("mode")).toHaveText("Pin drill: the annotation is hidden; 3 records");
      await page.keyboard.press("Tab");
      await expect(page.getByTestId("mode")).toHaveText("Pin drill: the annotation is hidden; 4 records");
      // A band added starts 1 square wide; one step makes 1 + 1 = 2.
      await page.getByTestId("band-add").click();
      await page.getByTestId("band-1-inc").click();
      await expect(page.getByTestId("mode")).toHaveText("Pin drill: the annotation is hidden; 6 records");

      await expect(page.getByTestId("save")).toHaveText("Save drill records");
      const saved = await saveJson(page, "lacma-54871.drill.json", "drill");
      const log = saved.data;
      expect(log).toMatchObject({
        drill_version: 1,
        photo: LACMA_PHOTO,
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
        // The typed 24 squares down, once.
        {
          seq: 4,
          t_ms: expect.any(Number),
          kind: "counts",
          counts: { blocks_across: 2, blocks_down: 1, squares_per_block_across: 1, squares_per_block_down: 24 },
        },
        { seq: 5, t_ms: expect.any(Number), kind: "bands", bands: [{ width_squares: 1 }] },
        { seq: 6, t_ms: expect.any(Number), kind: "bands", bands: [{ width_squares: 2 }] },
      ]);
      expect(records[0].t_ms).toBeGreaterThanOrEqual(0);
      for (let i = 1; i < records.length; i++) {
        expect(records[i].t_ms, `record ${i + 1} t_ms`).toBeGreaterThanOrEqual(records[i - 1].t_ms);
      }

      // Ending the drill gives back the verify draft, the unsaved edit included.
      await page.getByTestId("drill-stop").click();
      await expect(page.getByTestId("mode")).toHaveText("Verifying, starting from proposed-a");
      for (const name of CORNERS) await expectPinAt(page, `outer.${name}`, edited[name]);
      await expect(page.getByTestId("counts-across-blocks")).toHaveValue(String((claimBy(original.counts, "proposed-a").value as Json).blocks_across));
    });
  });

  test.describe("annotate page with touch on an iPhone 13", { tag: "@phone" }, () => {
    test.use(IPHONE_OPTIONS);

    test("one finger drags every pin and a band, two fingers pinch and pan, a zoomed drag maps, and the saved JSON is the hand geometry", async ({
      page,
    }) => {
      const { sha } = await openQuilt(page);
      // Records each pointerdown's type, so the test shows its input arrived as touch, not as a mouse.
      await page.evaluate(() => {
        const types: string[] = [];
        Object.assign(window, { pointerTypes: types });
        window.addEventListener("pointerdown", (event) => types.push(event.pointerType), true);
      });
      const pointerTypes = () => page.evaluate(() => (window as unknown as { pointerTypes: string[] }).pointerTypes);
      const cdp = await page.context().newCDPSession(page);
      const view = page.getByTestId("pin-view");
      for (const name of CORNERS) await expectPinAt(page, `outer.${name}`, QUILT_INSET[name]);
      await expect(view).toHaveAttribute("data-scale", "1.000");

      await showPhoto(page);
      for (const name of CORNERS) {
        const id = `outer.${name}`;
        const box = await touchDrag(page, cdp, id, OUTER[name], QUILT);
        await expectDropNear(page, id, OUTER[name], box, QUILT, `${id} drop`);
        await nudgeTo(page, id, OUTER[name]);
      }
      await expectKeySteps(page, "outer.top_left", OUTER.top_left);

      // One finger from the middle of the photo, well clear of every pin's 44 px hit area.
      const pins = await allPins(page);
      const fit = await showPhoto(page);
      const from = toScreen(fit, QUILT, { x: 400, y: 300 });
      const to = { x: from.x + 60, y: from.y + 40 };
      await touch(cdp, "touchStart", [from]);
      for (const t of [0.25, 0.5, 0.75, 1]) await touch(cdp, "touchMove", [between(from, to, t)]);
      await expect(page.getByTestId("loupe")).toHaveCount(0);
      await touch(cdp, "touchEnd", []);
      expect(await allPins(page), "a drag off the pins moves no pin").toEqual(pins);
      await expect(view).toHaveAttribute("data-scale", "1.000");

      // Two fingers beside the top left pin, outside its 44 px box (25 px left
      // and 33 px above its center, more than 22 each way), 60 px apart; the
      // left one holds while the right one moves out to 180 px apart: scale = 1
      // x 180 / 60 = 3. The pin then sits 3 times as far from the held finger,
      // so it stays on the stage.
      const corner = toScreen(fit, QUILT, OUTER.top_left);
      const held = { x: Math.round(corner.x - 25), y: Math.round(corner.y - 33) };
      const fingers = (apart: number, shift: Point = { x: 0, y: 0 }): Point[] => [
        { x: held.x + shift.x, y: held.y + shift.y },
        { x: held.x + apart + shift.x, y: held.y + shift.y },
      ];
      await touch(cdp, "touchStart", fingers(60));
      for (const apart of [90, 120, 150, 180]) await touch(cdp, "touchMove", fingers(apart));
      await expect(view).toHaveAttribute("data-scale", "3.000");
      // Both fingers then move together by (-20, -15): at a fixed spread the
      // scale holds at 3 and the content under the first midpoint follows the
      // midpoint, so the view moves by (-20, -15). The pinch left the view at
      // -2 times the held finger's place in the photo's box, near its top left
      // corner, so close to the clamp at (0, 0); a move left and up heads for
      // the far clamp at w (1 - 3) = -2w and -2h instead, which it stays inside.
      const pinched = await viewTranslate(page);
      expect(pinched.x - 20, "the pan stays inside the far x clamp").toBeGreaterThan(-2 * fit.width);
      expect(pinched.y - 15, "the pan stays inside the far y clamp").toBeGreaterThan(-2 * fit.height);
      for (const t of [0.5, 1]) await touch(cdp, "touchMove", fingers(180, { x: -20 * t, y: -15 * t }));
      // React renders a pointermove after the input call returns, so the pan is polled.
      await expect
        .poll(async () => (await viewTranslate(page)).x - pinched.x, { message: "two-finger pan x" })
        .toBeCloseTo(-20, 2);
      await expect
        .poll(async () => (await viewTranslate(page)).y - pinched.y, { message: "two-finger pan y" })
        .toBeCloseTo(-15, 2);
      await touch(cdp, "touchEnd", []);
      await expect(view).toHaveAttribute("data-scale", "3.000");
      // The page zoomed its own view, not the browser's.
      expect(await page.evaluate(() => window.visualViewport?.scale ?? 1)).toBe(1);
      expect(await allPins(page), "a pinch and pan move no pin").toEqual(pins);

      // A one-finger drag at scale 3: the image rect is 3 times its fit width,
      // so one screen pixel spans 800 / (3 x fit width) source pixels.
      const zoomedTarget = { x: 130, y: 120 };
      const zoomed = await touchDrag(page, cdp, "outer.top_left", zoomedTarget, QUILT);
      expect(zoomed.width).toBeCloseTo(3 * fit.width, 3);
      await expectDropNear(page, "outer.top_left", zoomedTarget, zoomed, QUILT, "zoomed drop");
      await nudgeTo(page, "outer.top_left", zoomedTarget);
      // Four corner drags, one off the pins, two fingers for the pinch, one zoomed drag.
      expect(await pointerTypes()).toEqual(["touch", "touch", "touch", "touch", "touch", "touch", "touch", "touch"]);
      await page.getByRole("button", { name: "Fit", exact: true }).tap();
      await expect(view).toHaveAttribute("data-scale", "1.000");

      // Back onto the quilt's corner by keys: (130, 120) less 30 and 20 is (100, 100).
      await nudgeTo(page, "outer.top_left", OUTER.top_left);

      // The quilt's counts: blocks by stepper, 1 + 1 = 2 on each axis; squares
      // a block typed, 5 across and 3 down.
      await page.getByTestId("counts-across-blocks-inc").tap();
      await page.getByTestId("counts-down-blocks-inc").tap();
      await page.getByTestId("counts-across-squares").fill("5");
      await page.getByTestId("counts-down-squares").fill("3");
      // 2 x 5 = 10 squares across; 2 x 3 = 6 down.
      await expect(page.getByTestId("counts-across-total")).toHaveText("2 blocks x 5 squares = 10 squares");
      await expect(page.getByTestId("counts-down-total")).toHaveText("2 blocks x 3 squares = 6 squares");

      // A band by touch. It starts 1 square wide, so its inner line is 1 / (10
      // + 2) = 1/12 in and the left handle at x = 100 + 600 / 12 = 150, y = 300.
      // Dragged to x 175: f = 75 / 600 = 0.125, w = 10 x 0.125 / (1 - 0.25) =
      // 1.6667 squares. The drop lands within one screen pixel, s source px, of
      // the target, and w grows with x, so the width lies between w at 175 - s
      // and at 175 + s, by that same formula.
      await page.getByTestId("band-add").tap();
      await expect(page.getByTestId("band-1-width")).toHaveText("1 square");
      await showPhoto(page);
      const bandHandle = await pinPoint(page, "band.left");
      expect(bandHandle.x).toBeCloseTo(150, 6);
      expect(bandHandle.y).toBeCloseTo(300, 6);
      const bandTarget = { x: 175, y: 300 };
      const bandBox = await touchDrag(page, cdp, "band.left", bandTarget, QUILT);
      const s = screenPixel(bandBox, QUILT);
      const widthAtX = (x: number) => {
        const f = (x - 100) / 600;
        return (10 * f) / (1 - 2 * f);
      };
      await expect
        .poll(async () => bandWidth(page, 1), { message: "band.left touch drop" })
        .toBeGreaterThanOrEqual(roundDown4(widthAtX(bandTarget.x - s)));
      expect(await bandWidth(page, 1)).toBeLessThanOrEqual(roundUp4(widthAtX(bandTarget.x + s)));
      await expectDropNear(page, "band.left", bandTarget, bandBox, QUILT, "band.left touch drop");
      // Typed, it is exact: 1.5 in on a 1 1/2 in square (12 eighths) is 1 square.
      await page.getByTestId("square-size").selectOption("12");
      await page.getByTestId("band-1-inches").fill("1.5");
      await page.getByTestId("band-1-inches").press("Enter");
      await expect(page.getByTestId("band-1-width")).toHaveText("1 square, 1 1/2 in");

      await page.getByTestId("construction-class").selectOption("squares");
      const saved = await saveJson(page, "generated-quilt.json", "touch");
      expect(saved.data).toEqual({
        schema_version: 1,
        photo: QUILT_NAME,
        sha256: sha,
        canvas: [800, 600],
        frame: [
          {
            provenance: "verified-jake",
            value: { outer_edge: { kind: "outer_edge", corners: OUTER, bands: [{ width_squares: 1 }] }, field: null },
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

      // On the phone too, a pin on the photo's corner keeps its whole hit area:
      // from (100, 100), 10 Shift+Left and 10 Shift+Up presses of 10 px reach (0, 0).
      await pressOn(page, "outer.top_left", "Shift+ArrowLeft", 10);
      await pressOn(page, "outer.top_left", "Shift+ArrowUp", 10);
      await expectPinAt(page, "outer.top_left", { x: 0, y: 0 });
      await showPhoto(page);
      await expectWholeHitArea(page, "outer.top_left", "on the phone at fit");

      // A drag the browser cancels still moved the pin on screen, so the drill
      // records it as a placement (PinLayer's pointercancel).
      await page.getByTestId("drill-start").tap();
      await expect(page.getByTestId("mode")).toHaveText("Pin drill: the annotation is hidden; 0 records");
      await showPhoto(page);
      const drillBox = await boxOf(page, "pin-image");
      const cancelFrom = toScreen(drillBox, QUILT, QUILT_INSET.top_left);
      const cancelTo = toScreen(drillBox, QUILT, { x: 200, y: 200 });
      await touch(cdp, "touchStart", [cancelFrom]);
      for (const t of [0.5, 1]) await touch(cdp, "touchMove", [between(cancelFrom, cancelTo, t)]);
      await expect(page.getByTestId("loupe")).toBeVisible();
      await cdp.send("Input.dispatchTouchEvent", { type: "touchCancel", touchPoints: [] });
      await expect(page.getByTestId("loupe")).toBeHidden();
      await expect(page.getByTestId("mode")).toHaveText("Pin drill: the annotation is hidden; 1 records");
      await page.getByTestId("drill-stop").tap();
      await expectPinAt(page, "outer.top_left", { x: 0, y: 0 });

      await expectNoHorizontalOverflow(page, "annotate-phone");
    });
  });
}
