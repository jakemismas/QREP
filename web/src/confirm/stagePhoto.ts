/**
 * Crop-aware staging (C3b, issue #101): the confirmed frame's bounding box
 * plus at least one square of margin, clamped to the photo, cut at full
 * decoded resolution and then capped at STAGE_CAP on its longest side.
 * Staging the whole photo at a cap picked from the window width left a quilt
 * that fills part of a phone screenshot at about 9 px per square (docs-03,
 * approaches-30) and gave a phone and a desktop different quilts (ux-06), so
 * nothing here reads the viewport. The staged corners are pixels of the crop,
 * and the crop offset places it in the decoded photo, as B2a's read takes them.
 *
 * Exported for D4b, which decodes eval inputs through this same browser path
 * (Critique: CR-cv-21).
 */
import type { BorderBand, Corners, Point } from "../engine/contract";
import { capLongest, STAGE_CAP } from "../model/downscale";
import { bandTotal } from "./bands";
import { totalSquares, type AxisCount } from "./counts";
import { cornersToQuad, type FrameMode } from "./frame";
import type { Size } from "./geometry";

/** Total squares across and down the pinned quad: the field counts, plus both sides' bands on an outer edge. */
export function frameSquares(
  mode: FrameMode,
  across: AxisCount,
  down: AxisCount,
  bands: readonly BorderBand[],
): { across: number; down: number } {
  const field = { across: totalSquares(across), down: totalSquares(down) };
  if (mode === "field") return field;
  const sides = 2 * bandTotal(bands);
  return { across: field.across + sides, down: field.down + sides };
}

const distance = (a: Point, b: Point) => Math.hypot(b.x - a.x, b.y - a.y);

/**
 * The largest square side along any edge of the pinned quad, in photo px:
 * max(top/across, bottom/across, left/down, right/down). The largest, so
 * under perspective the margin still holds a whole square of the near side.
 */
export function squarePx(corners: Corners, squares: { across: number; down: number }): number {
  const [tl, tr, br, bl] = cornersToQuad(corners);
  return Math.max(
    distance(tl, tr) / squares.across,
    distance(bl, br) / squares.across,
    distance(tl, bl) / squares.down,
    distance(tr, br) / squares.down,
  );
}

export interface CropPlan {
  /** The crop's top-left corner in decoded-photo pixels (the crop offset of #101). */
  offset: Point;
  /** The crop in decoded-photo pixels. */
  crop: Size;
  /** The staged crop after the cap. */
  staged: Size;
  /** The corners in the staged crop's pixel frame. */
  corners: Corners;
}

/**
 * margin = ceil(squarePx) (at least one square); x0 = max(0, floor(minX) - margin), y0 likewise,
 * x1 = min(W, ceil(maxX) + margin), y1 likewise; crop = (x1 - x0, y1 - y0); staged = capLongest(crop);
 * corner c maps to ((c.x - x0) * staged.width / crop.width, (c.y - y0) * staged.height / crop.height).
 * No viewport input: the same photo and pins plan the same crop at any window width (ux-06).
 */
export function planCrop(image: Size, corners: Corners, squarePx: number, cap = STAGE_CAP): CropPlan {
  if (!(squarePx > 0 && Number.isFinite(squarePx))) {
    throw new RangeError(`A square must be a positive number of pixels, not ${squarePx}.`);
  }
  const margin = Math.ceil(squarePx);
  const quad = cornersToQuad(corners);
  const xs = quad.map((p) => p.x);
  const ys = quad.map((p) => p.y);
  const x0 = Math.max(0, Math.floor(Math.min(...xs)) - margin);
  const y0 = Math.max(0, Math.floor(Math.min(...ys)) - margin);
  const x1 = Math.min(image.width, Math.ceil(Math.max(...xs)) + margin);
  const y1 = Math.min(image.height, Math.ceil(Math.max(...ys)) + margin);
  const crop = { width: x1 - x0, height: y1 - y0 };
  if (crop.width < 1 || crop.height < 1) {
    throw new RangeError("The pins lie outside the photo.");
  }
  const capped = capLongest(crop.width, crop.height, cap);
  const staged = { width: capped.width, height: capped.height };
  // Each axis maps by its own ratio: drawImage stretches the crop to the
  // staged size per axis, and the short side's rounding makes them differ.
  const map = (p: Point): Point => ({
    x: ((p.x - x0) * staged.width) / crop.width,
    y: ((p.y - y0) * staged.height) / crop.height,
  });
  return {
    offset: { x: x0, y: y0 },
    crop,
    staged,
    corners: {
      top_left: map(corners.top_left),
      top_right: map(corners.top_right),
      bottom_right: map(corners.bottom_right),
      bottom_left: map(corners.bottom_left),
    },
  };
}

export interface StagedPhoto {
  /** PNG. */
  bytes: Uint8Array;
  plan: CropPlan;
}

/** What the dropzone shows for a file the browser cannot open. */
export const DECODE_ERROR = "QREP could not open this file. Choose a JPG or PNG photo of your quilt.";

const STAGE_ERROR = "QREP could not prepare this photo. Try again, or choose another photo.";

const PNG_SIGNATURE = [0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a];

/**
 * Walks the marker segments from SOI to the first EOI. Each segment is
 * skipped by its length, because an EXIF thumbnail inside APP1 carries its
 * own scan and EOI; scan data is stepped through, where FF 00 is a stuffed
 * byte and FF D0 to FF D7 are restarts. Bytes after the first EOI (a motion
 * photo's video, an MPF gain map) are never looked at.
 */
function jpegReachesEnd(b: Uint8Array): boolean {
  let i = 2;
  for (;;) {
    // libjpeg skips stray bytes before a marker, so this does too.
    i = b.indexOf(0xff, i);
    if (i < 0 || i + 1 >= b.length) return false;
    const marker = b[i + 1];
    if (marker === 0xd9) return true;
    if (marker === 0xff) {
      i += 1;
      continue;
    }
    if (marker === 0x00 || marker === 0x01 || (marker >= 0xd0 && marker <= 0xd8)) {
      i += 2;
      continue;
    }
    if (i + 3 >= b.length) return false;
    i += 2 + ((b[i + 2] << 8) | b[i + 3]);
    if (marker === 0xda) {
      i = scanEnd(b, i);
      if (i < 0) return false;
    }
  }
}

/** Where the marker after a scan's data starts, or -1 when the bytes stop first. */
function scanEnd(b: Uint8Array, from: number): number {
  let i = from;
  for (;;) {
    i = b.indexOf(0xff, i);
    if (i < 0 || i + 1 >= b.length) return -1;
    const next = b[i + 1];
    if (next !== 0x00 && !(next >= 0xd0 && next <= 0xd7)) return i;
    i += 2;
  }
}

/** Walks the chunks (length, type, data, CRC) to a whole IEND chunk. */
function pngReachesEnd(b: Uint8Array): boolean {
  const view = new DataView(b.buffer, b.byteOffset, b.byteLength);
  for (let i = 8; i + 8 <= b.length; ) {
    const end = i + 12 + view.getUint32(i);
    if (end > b.length) return false;
    if (b[i + 4] === 0x49 && b[i + 5] === 0x45 && b[i + 6] === 0x4e && b[i + 7] === 0x44) return true;
    i = end;
  }
  return false;
}

/**
 * True when bytes are a JPEG or PNG that stops before its end. Other formats
 * (HEIC, WebP, text) are left to the browser's decoder.
 */
export function isTruncatedImage(bytes: Uint8Array): boolean {
  if (bytes.length >= 2 && bytes[0] === 0xff && bytes[1] === 0xd8) return !jpegReachesEnd(bytes);
  if (bytes.length >= 8 && PNG_SIGNATURE.every((value, i) => bytes[i] === value)) return !pngReachesEnd(bytes);
  return false;
}

async function orientedBitmap(file: Blob): Promise<ImageBitmap> {
  try {
    return await createImageBitmap(file, { imageOrientation: "from-image" });
  } catch (error) {
    // An engine that predates "from-image" rejects the options bag itself
    // with a TypeError; its own default orientation then applies.
    if (error instanceof TypeError) return await createImageBitmap(file);
    throw error;
  }
}

/**
 * Decodes a file with EXIF orientation applied; rejects with a plain-English
 * Error for anything the browser cannot decode (a text file, a truncated JPEG).
 */
export async function decodePhoto(file: Blob): Promise<ImageBitmap> {
  try {
    // Chromium 149 rejects a truncated JPEG or PNG here, but WebKit 26.5
    // (Playwright's build of Safari's engine) resolves one cut to 2 to 95
    // percent of its bytes as a full-size, fully transparent bitmap (C3b
    // probe, 2026-10-13), which would open the confirm screen on a blank
    // photo. So the bytes are checked before the browser decodes them.
    if (isTruncatedImage(new Uint8Array(await file.arrayBuffer()))) throw new Error("the file stops early");
    return await orientedBitmap(file);
  } catch (error) {
    throw new Error(DECODE_ERROR, { cause: error });
  }
}

type DrawContext = CanvasDrawImage & CanvasImageSmoothing;

function drawCrop(ctx: DrawContext | null, bitmap: ImageBitmap, plan: CropPlan): void {
  if (!ctx) throw new Error(STAGE_ERROR);
  ctx.imageSmoothingEnabled = true;
  ctx.imageSmoothingQuality = "high";
  const { offset, crop, staged } = plan;
  ctx.drawImage(bitmap, offset.x, offset.y, crop.width, crop.height, 0, 0, staged.width, staged.height);
}

async function cropToPng(bitmap: ImageBitmap, plan: CropPlan): Promise<Uint8Array> {
  const { width, height } = plan.staged;
  let blob: Blob | null;
  if (typeof document !== "undefined") {
    const canvas = document.createElement("canvas");
    canvas.width = width;
    canvas.height = height;
    drawCrop(canvas.getContext("2d"), bitmap, plan);
    blob = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, "image/png"));
  } else {
    // A worker has no document; D4b may stage there.
    const canvas = new OffscreenCanvas(width, height);
    drawCrop(canvas.getContext("2d"), bitmap, plan);
    blob = await canvas.convertToBlob({ type: "image/png" });
  }
  if (!blob) throw new Error(STAGE_ERROR);
  return new Uint8Array(await blob.arrayBuffer());
}

/**
 * Cuts plan.crop out of the decoded photo at full resolution, draws it at
 * plan.staged (imageSmoothingQuality "high"), and encodes PNG. Accepts a Blob
 * (decoded first) or a decoded bitmap.
 */
export async function stagePhoto(photo: Blob | ImageBitmap, corners: Corners, squarePx: number): Promise<StagedPhoto> {
  const owned = photo instanceof Blob;
  const bitmap = owned ? await decodePhoto(photo) : photo;
  try {
    const plan = planCrop({ width: bitmap.width, height: bitmap.height }, corners, squarePx);
    return { bytes: await cropToPng(bitmap, plan), plan };
  } finally {
    // A bitmap the caller passed in stays the caller's to close.
    if (owned) bitmap.close();
  }
}
