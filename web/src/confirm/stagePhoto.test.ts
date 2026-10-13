/**
 * Crop-aware staging (C3b, issue #101): one crop around the confirmed frame
 * plus at least one square of margin, clamped to the image, cut at full
 * decoded resolution and capped at 2000 px for every viewport (ux-06,
 * docs-03). Every expected value is hand computed in the comment above it.
 */
import { afterEach, describe, expect, it, vi } from "vitest";
import type { Corners } from "../engine/contract";
import { DECODE_ERROR, decodePhoto, frameSquares, isTruncatedImage, planCrop, squarePx, stagePhoto } from "./stagePhoto";

function expectCorners(actual: Corners, expected: Corners, digits = 9): void {
  for (const name of ["top_left", "top_right", "bottom_right", "bottom_left"] as const) {
    expect(actual[name].x).toBeCloseTo(expected[name].x, digits);
    expect(actual[name].y).toBeCloseTo(expected[name].y, digits);
  }
}

afterEach(() => {
  vi.unstubAllGlobals();
});

// docs-03 (issue #101, "Prove the cap"): a 1290 x 2796 screenshot holding a
// 40 x 40 grid of 18.5 px squares, so the grid spans 40 x 18.5 = 740 px.
const DOCS03_IMAGE = { width: 1290, height: 2796 };
const DOCS03_CORNERS: Corners = {
  top_left: { x: 275, y: 1028 },
  top_right: { x: 1015, y: 1028 },
  bottom_right: { x: 1015, y: 1768 },
  bottom_left: { x: 275, y: 1768 },
};

describe("the docs-03 vector keeps 18.5 px per square", () => {
  it("plans a 778 x 778 crop at full resolution", () => {
    // Counts: 8 blocks x 5 squares = 40 each way, field frame, no bands.
    const squares = frameSquares("field", { blocks: 8, squaresPerBlock: 5 }, { blocks: 8, squaresPerBlock: 5 }, []);
    expect(squares).toEqual({ across: 40, down: 40 });
    // Every edge is 1015 - 275 = 740 or 1768 - 1028 = 740 px: 740 / 40 = 18.5.
    const px = squarePx(DOCS03_CORNERS, squares);
    expect(px).toBe(18.5);
    // margin = ceil(18.5) = 19
    // x0 = max(0, 275 - 19) = 256, y0 = max(0, 1028 - 19) = 1009
    // x1 = min(1290, 1015 + 19) = 1034, y1 = min(2796, 1768 + 19) = 1787
    // crop = (1034 - 256, 1787 - 1009) = (778, 778); 778 <= 2000, so staged = crop
    const plan = planCrop(DOCS03_IMAGE, DOCS03_CORNERS, px);
    expect(plan.offset).toEqual({ x: 256, y: 1009 });
    expect(plan.crop).toEqual({ width: 778, height: 778 });
    expect(plan.staged).toEqual({ width: 778, height: 778 });
    // Corners minus the offset, times 778 / 778 = 1:
    // 275 - 256 = 19, 1015 - 256 = 759, 1028 - 1009 = 19, 1768 - 1009 = 759.
    expectCorners(plan.corners, {
      top_left: { x: 19, y: 19 },
      top_right: { x: 759, y: 19 },
      bottom_right: { x: 759, y: 759 },
      bottom_left: { x: 19, y: 759 },
    });
    // Staged px per square: (759 - 19) / 40 = 740 / 40 = 18.5.
    expect((plan.corners.top_right.x - plan.corners.top_left.x) / 40).toBe(18.5);
    expect((plan.corners.bottom_left.y - plan.corners.top_left.y) / 40).toBe(18.5);
  });

  it("keeps about twice the px per square of the 834d8be phone path", () => {
    // 834d8be staged the whole screenshot at the phone cap, 1400 px on the
    // 2796 px side: 18.5 x 1400 / 2796 = 25900 / 2796 = 9.263 px per square
    // (2796 x 9 = 25164, 736 / 2796 = 0.263). A hand-computed constant, not
    // the old code.
    const PHONE_PATH_PX = 9.263;
    expect((18.5 * 1400) / 2796).toBeCloseTo(PHONE_PATH_PX, 3);
    const plan = planCrop(DOCS03_IMAGE, DOCS03_CORNERS, 18.5);
    const staged = (plan.corners.top_right.x - plan.corners.top_left.x) / 40;
    // 18.5 against 9.263: 18.5 / 9.263 = 1.997, about twice.
    expect(staged).toBe(18.5);
    expect(staged / PHONE_PATH_PX).toBeCloseTo(1.997, 3);
  });
});

describe("the 2000 px cap", () => {
  it("caps a crop of an 8000 x 6000 photo to 2000 x 1500", () => {
    // Quad 900..7100 across and 700..5300 down of an 8000 x 6000 photo.
    // Counts 2 x 31 = 62 across and 2 x 23 = 46 down, field frame:
    // 6200 / 62 = 100 and 4600 / 46 = 100, so squarePx = 100.
    const corners: Corners = {
      top_left: { x: 900, y: 700 },
      top_right: { x: 7100, y: 700 },
      bottom_right: { x: 7100, y: 5300 },
      bottom_left: { x: 900, y: 5300 },
    };
    const squares = frameSquares("field", { blocks: 2, squaresPerBlock: 31 }, { blocks: 2, squaresPerBlock: 23 }, []);
    const px = squarePx(corners, squares);
    expect(px).toBe(100);
    // margin = 100; x0 = 900 - 100 = 800, y0 = 700 - 100 = 600,
    // x1 = min(8000, 7100 + 100) = 7200, y1 = min(6000, 5300 + 100) = 5400
    // crop = (7200 - 800, 5400 - 600) = (6400, 4800)
    // capLongest: scale = 2000 / 6400 = 0.3125; 4800 x 0.3125 = 1500
    const plan = planCrop({ width: 8000, height: 6000 }, corners, px);
    expect(plan.offset).toEqual({ x: 800, y: 600 });
    expect(plan.crop).toEqual({ width: 6400, height: 4800 });
    expect(plan.staged).toEqual({ width: 2000, height: 1500 });
    // x: (900 - 800) x 2000 / 6400 = 31.25, (7100 - 800) x 2000 / 6400 = 1968.75
    // y: (700 - 600) x 1500 / 4800 = 31.25, (5300 - 600) x 1500 / 4800 = 1468.75
    expectCorners(plan.corners, {
      top_left: { x: 31.25, y: 31.25 },
      top_right: { x: 1968.75, y: 31.25 },
      bottom_right: { x: 1968.75, y: 1468.75 },
      bottom_left: { x: 31.25, y: 1468.75 },
    });
  });

  it("maps each axis by its own staged to crop ratio when the short side rounds", () => {
    // Quad 400..7600 across and 300..5700 down of 8000 x 6000, squarePx 100:
    // offset (300, 200), x1 = 7700, y1 = 5800, crop = (7400, 5600)
    // capLongest: 2000 x round(5600 x 2000 / 7400 = 1513.51) = 2000 x 1514
    const corners: Corners = {
      top_left: { x: 400, y: 300 },
      top_right: { x: 7600, y: 300 },
      bottom_right: { x: 7600, y: 5700 },
      bottom_left: { x: 400, y: 5700 },
    };
    const plan = planCrop({ width: 8000, height: 6000 }, corners, 100);
    expect(plan.offset).toEqual({ x: 300, y: 200 });
    expect(plan.crop).toEqual({ width: 7400, height: 5600 });
    expect(plan.staged).toEqual({ width: 2000, height: 1514 });
    // x: 100 x 2000 / 7400 = 27.027027..., 7300 x 2000 / 7400 = 1972.972972...
    // y: 100 x 1514 / 5600 = 27.035714..., 5500 x 1514 / 5600 = 1486.964285...
    expectCorners(
      plan.corners,
      {
        top_left: { x: 27.027027, y: 27.035714 },
        top_right: { x: 1972.972973, y: 27.035714 },
        bottom_right: { x: 1972.972973, y: 1486.964286 },
        bottom_left: { x: 27.027027, y: 1486.964286 },
      },
      5,
    );
  });
});

describe("clamping to the image", () => {
  it("clamps the offset to 0 and the far side to the image size", () => {
    // 1000 x 800 image, every pin within 20 px of an edge, squarePx 20:
    // margin = 20; x0 = max(0, floor(3) - 20 = -17) = 0,
    // y0 = max(0, floor(5.6) - 20 = -15) = 0,
    // x1 = min(1000, ceil(995) + 20 = 1015) = 1000,
    // y1 = min(800, ceil(795.5) + 20 = 816) = 800
    // crop = staged = 1000 x 800, so the corners stay where they are.
    const corners: Corners = {
      top_left: { x: 10.4, y: 5.6 },
      top_right: { x: 990.2, y: 12 },
      bottom_right: { x: 995, y: 795.5 },
      bottom_left: { x: 3, y: 790 },
    };
    const plan = planCrop({ width: 1000, height: 800 }, corners, 20);
    expect(plan.offset).toEqual({ x: 0, y: 0 });
    expect(plan.crop).toEqual({ width: 1000, height: 800 });
    expect(plan.staged).toEqual({ width: 1000, height: 800 });
    expectCorners(plan.corners, corners);
  });

  it("floors the near side, ceils the far side and rounds the margin up", () => {
    // 1000 x 800 image, squarePx 40.2: margin = ceil(40.2) = 41
    // x0 = max(0, floor(30.7) - 41 = -11) = 0, y0 = max(0, floor(100.2) - 41) = 59
    // x1 = min(1000, ceil(600.5) + 41) = 642, y1 = min(800, ceil(500.9) + 41) = 542
    // crop = (642, 483), under the cap
    // corners: x - 0, y - 59: 100.2 - 59 = 41.2, 500.9 - 59 = 441.9
    const corners: Corners = {
      top_left: { x: 30.7, y: 100.2 },
      top_right: { x: 600.5, y: 100.2 },
      bottom_right: { x: 600.5, y: 500.9 },
      bottom_left: { x: 30.7, y: 500.9 },
    };
    const plan = planCrop({ width: 1000, height: 800 }, corners, 40.2);
    expect(plan.offset).toEqual({ x: 0, y: 59 });
    expect(plan.crop).toEqual({ width: 642, height: 483 });
    expect(plan.staged).toEqual({ width: 642, height: 483 });
    expectCorners(plan.corners, {
      top_left: { x: 30.7, y: 41.2 },
      top_right: { x: 600.5, y: 41.2 },
      bottom_right: { x: 600.5, y: 441.9 },
      bottom_left: { x: 30.7, y: 441.9 },
    });
  });

  it("floors a near side at .7 and ceils a far side at .2, where rounding would not", () => {
    // 1000 x 800 image, squarePx 9.2: margin = ceil(9.2) = 10 (round gives 9).
    // Near side x 50.7, y 60.7: floor gives 50 and 60, round 51 and 61.
    // Far side x 700.2, y 500.2: ceil gives 701 and 501, round 700 and 500.
    // x0 = max(0, 50 - 10) = 40, y0 = max(0, 60 - 10) = 50 (neither clamped),
    // x1 = min(1000, 701 + 10) = 711, y1 = min(800, 501 + 10) = 511 (neither clamped).
    // crop = (711 - 40, 511 - 50) = (671, 461), under the cap.
    // Math.round everywhere would give x0 = 51 - 9 = 42, y0 = 61 - 9 = 52,
    // x1 = 700 + 9 = 709, y1 = 500 + 9 = 509: crop 667 x 457.
    const corners: Corners = {
      top_left: { x: 50.7, y: 60.7 },
      top_right: { x: 700.2, y: 60.7 },
      bottom_right: { x: 700.2, y: 500.2 },
      bottom_left: { x: 50.7, y: 500.2 },
    };
    const plan = planCrop({ width: 1000, height: 800 }, corners, 9.2);
    expect(plan.offset).toEqual({ x: 40, y: 50 });
    expect(plan.crop).toEqual({ width: 671, height: 461 });
    expect(plan.staged).toEqual({ width: 671, height: 461 });
    // Scale 1: x - 40 and y - 50: 50.7 - 40 = 10.7, 700.2 - 40 = 660.2,
    // 60.7 - 50 = 10.7, 500.2 - 50 = 450.2.
    expectCorners(plan.corners, {
      top_left: { x: 10.7, y: 10.7 },
      top_right: { x: 660.2, y: 10.7 },
      bottom_right: { x: 660.2, y: 450.2 },
      bottom_left: { x: 10.7, y: 450.2 },
    });
  });

  it("keeps at least one pixel of margin for a sub-pixel square", () => {
    // squarePx 0.4: margin = ceil(0.4) = 1; quad 10..20 of a 100 x 100 image:
    // x0 = y0 = 10 - 1 = 9, x1 = y1 = 20 + 1 = 21, crop = 12 x 12.
    const corners: Corners = {
      top_left: { x: 10, y: 10 },
      top_right: { x: 20, y: 10 },
      bottom_right: { x: 20, y: 20 },
      bottom_left: { x: 10, y: 20 },
    };
    const plan = planCrop({ width: 100, height: 100 }, corners, 0.4);
    expect(plan.offset).toEqual({ x: 9, y: 9 });
    expect(plan.crop).toEqual({ width: 12, height: 12 });
  });

  it("refuses a square size that is not a positive number", () => {
    expect(() => planCrop(DOCS03_IMAGE, DOCS03_CORNERS, 0)).toThrow(RangeError);
    expect(() => planCrop(DOCS03_IMAGE, DOCS03_CORNERS, Number.NaN)).toThrow(RangeError);
  });
});

describe("frameSquares", () => {
  const across = { blocks: 9, squaresPerBlock: 5 };
  const down = { blocks: 11, squaresPerBlock: 5 };

  it("adds both sides' bands on an outer edge", () => {
    // across 9 x 5 = 45, plus 2 x 2.5 = 5: 50; down 11 x 5 = 55, plus 5: 60.
    expect(frameSquares("outer_edge", across, down, [{ width_squares: 2.5 }])).toEqual({ across: 50, down: 60 });
  });

  it("sums every band: 2 + 0.5 = 2.5 a side", () => {
    // 45 + 2 x (2 + 0.5) = 50 and 55 + 5 = 60, the same as one 2.5 band.
    expect(frameSquares("outer_edge", across, down, [{ width_squares: 2 }, { width_squares: 0.5 }])).toEqual({
      across: 50,
      down: 60,
    });
  });

  it("ignores bands on a field frame", () => {
    // The field corners bound the field alone: 45 x 55.
    expect(frameSquares("field", across, down, [{ width_squares: 2.5 }])).toEqual({ across: 45, down: 55 });
  });
});

describe("squarePx picks the longest edge per axis", () => {
  it("measures the longer bottom edge of a trapezoid", () => {
    // TL (100, 100), TR (500, 100), BR (600, 400), BL (0, 400), 10 x 10 squares:
    // top 500 - 100 = 400 -> 40; bottom 600 - 0 = 600 -> 60;
    // left = right = hypot(100, 300) = sqrt(100000) = 316.23 -> 31.62. Max 60.
    const trapezoid: Corners = {
      top_left: { x: 100, y: 100 },
      top_right: { x: 500, y: 100 },
      bottom_right: { x: 600, y: 400 },
      bottom_left: { x: 0, y: 400 },
    };
    expect(squarePx(trapezoid, { across: 10, down: 10 })).toBe(60);
  });

  it("measures a slanted side along its length, not its height", () => {
    // The same trapezoid, 10 across and 5 down: top 40, bottom 60,
    // left = right = sqrt(100000) / 5 = 316.2278 / 5 = 63.2456. Max 63.2456.
    const trapezoid: Corners = {
      top_left: { x: 100, y: 100 },
      top_right: { x: 500, y: 100 },
      bottom_right: { x: 600, y: 400 },
      bottom_left: { x: 0, y: 400 },
    };
    expect(squarePx(trapezoid, { across: 10, down: 5 })).toBeCloseTo(63.2456, 4);
  });
});

describe("no viewport input (ux-06)", () => {
  it("plans the same crop at a 390 px and a 1440 px window", () => {
    // ux-06: 834d8be picked the cap from window.innerWidth, so one photo and
    // one set of pins gave different quilts on a phone and a desktop. The
    // window width changing between calls must leave the plan unchanged.
    vi.stubGlobal("innerWidth", 390);
    const phone = planCrop(DOCS03_IMAGE, DOCS03_CORNERS, 18.5);
    vi.stubGlobal("innerWidth", 1440);
    const desktop = planCrop(DOCS03_IMAGE, DOCS03_CORNERS, 18.5);
    expect(desktop).toEqual(phone);
    // And it is the docs-03 plan computed by hand above.
    expect(desktop.offset).toEqual({ x: 256, y: 1009 });
    expect(desktop.staged).toEqual({ width: 778, height: 778 });
  });

  it("caps a crop longer than 1400 px at 2000 with a 390 px window", () => {
    // The docs-03 crop is 778 px, under the old 1400 px phone cap, so it
    // cannot tell the caps apart. This one is longer than 1400.
    // A 3000 x 2000 photo of 100 px squares, pins (100, 100) to (2900, 1900),
    // 28 x 1 = 28 squares across and 18 x 1 = 18 down, field frame:
    // 2800 / 28 = 100 and 1800 / 18 = 100, so squarePx = 100, margin = 100.
    // x0 = max(0, 100 - 100) = 0, y0 = 0, x1 = min(3000, 2900 + 100) = 3000,
    // y1 = min(2000, 1900 + 100) = 2000: crop 3000 x 2000.
    // capLongest(3000, 2000) at 2000: 2000 x round(2000 x 2000 / 3000 =
    // 1333.33) = 2000 x 1333. The phone cap would give 1400 x round(933.33) = 1400 x 933.
    vi.stubGlobal("innerWidth", 390);
    const corners: Corners = {
      top_left: { x: 100, y: 100 },
      top_right: { x: 2900, y: 100 },
      bottom_right: { x: 2900, y: 1900 },
      bottom_left: { x: 100, y: 1900 },
    };
    const squares = frameSquares("field", { blocks: 28, squaresPerBlock: 1 }, { blocks: 18, squaresPerBlock: 1 }, []);
    const px = squarePx(corners, squares);
    expect(px).toBe(100);
    const plan = planCrop({ width: 3000, height: 2000 }, corners, px);
    expect(plan.offset).toEqual({ x: 0, y: 0 });
    expect(plan.crop).toEqual({ width: 3000, height: 2000 });
    expect(plan.staged).toEqual({ width: 2000, height: 1333 });
    // x: 100 x 2000 / 3000 = 66.666667, 2900 x 2000 / 3000 = 1933.333333
    // y: 100 x 1333 / 2000 = 66.65, 1900 x 1333 / 2000 = 1266.35
    expectCorners(
      plan.corners,
      {
        top_left: { x: 66.666667, y: 66.65 },
        top_right: { x: 1933.333333, y: 66.65 },
        bottom_right: { x: 1933.333333, y: 1266.35 },
        bottom_left: { x: 66.666667, y: 1266.35 },
      },
      5,
    );
  });
});

// Chromium 149's encoder output (canvas.toBlob), base64: an 8 x 8 JPEG
// (858 bytes, ends FF D9) and a 4 x 4 PNG (155 bytes, ends with IEND).
const SMALL_JPEG =
  "/9j/4AAQSkZJRgABAQAAAQABAAD/4gHYSUNDX1BST0ZJTEUAAQEAAAHIAAAAAAQwAABtbnRyUkdCIFhZWiAH4AABAAEAAAAAAABhY3NwAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAQAA9tYAAQAAAADTLQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAlkZXNjAAAA8AAAACRyWFlaAAABFAAAABRnWFlaAAABKAAAABRiWFlaAAABPAAAABR3dHB0AAABUAAAABRyVFJDAAABZAAAAChnVFJDAAABZAAAAChiVFJDAAABZAAAAChjcHJ0AAABjAAAADxtbHVjAAAAAAAAAAEAAAAMZW5VUwAAAAgAAAAcAHMAUgBHAEJYWVogAAAAAAAAb6IAADj1AAADkFhZWiAAAAAAAABimQAAt4UAABjaWFlaIAAAAAAAACSgAAAPhAAAts9YWVogAAAAAAAA9tYAAQAAAADTLXBhcmEAAAAAAAQAAAACZmYAAPKnAAANWQAAE9AAAApbAAAAAAAAAABtbHVjAAAAAAAAAAEAAAAMZW5VUwAAACAAAAAcAEcAbwBvAGcAbABlACAASQBuAGMALgAgADIAMAAxADb/2wBDAAMCAgMCAgMDAwMEAwMEBQgFBQQEBQoHBwYIDAoMDAsKCwsNDhIQDQ4RDgsLEBYQERMUFRUVDA8XGBYUGBIUFRT/2wBDAQMEBAUEBQkFBQkUDQsNFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBT/wAARCAAIAAgDASIAAhEBAxEB/8QAFQABAQAAAAAAAAAAAAAAAAAAAAf/xAAeEAACAgIDAQEAAAAAAAAAAAACAwEEAAUREhQhIv/EABUBAQEAAAAAAAAAAAAAAAAAAAYH/8QAIREAAQMEAQUAAAAAAAAAAAAAAQIEEQMFIUEAFDFRYfD/2gAMAwEAAhEDEQA/AJNb1zd5pz73q+9GKDFp8PoroVJ1hkDlNf8AMwQGv4weODmOe0ihTGMRXJ85tFYN6CyRE59qUdQN+JOyeROwt+rRUWVFMEYEADA7CDH08//Z";
const SMALL_PNG =
  "iVBORw0KGgoAAAANSUhEUgAAAAQAAAAECAYAAACp8Z5+AAAAUElEQVR4AQBEALv/Ag455P8Av2L/QIM9/4CSrv8C8lcTAADB5gDALaEAgI7DAAIAQPMAAEASAABARQAAQPwAAgBA6AAAQPcAQEBaAADbFAAAAAD//ysziMgAAAAGSURBVAMAmnIW4fh/sakAAAAASUVORK5CYII=";

const fromBase64 = (b64: string) => Uint8Array.from(atob(b64), (c) => c.charCodeAt(0));

// A JPEG marker segment: FF, the marker, a two-byte length that counts itself
// (payload + 2), then the payload.
function segment(marker: number, payload: number[]): number[] {
  const length = payload.length + 2;
  return [0xff, marker, length >> 8, length & 0xff, ...payload];
}

const SOI = [0xff, 0xd8];
const EOI = [0xff, 0xd9];
// A thumbnail inside APP1 carries its own scan and end of image, which a scan
// for "the last FF DA" or "any FF D9" would mistake for the photo's.
const APP1_WITH_THUMBNAIL = segment(0xe1, [0x45, 0x78, 0x69, 0x66, 0, 0, ...SOI, ...segment(0xda, [1, 2]), 9, 9, ...EOI]);
const SOF0 = segment(0xc0, [8, 0, 8, 0, 8, 1, 1, 0x11, 0]);
const DHT = segment(0xc4, [0, 1, 2, 3]);
const SOS = segment(0xda, [1, 1, 0, 0, 63, 0]);
// Entropy data with a stuffed FF 00 and a restart marker FF D3, neither of
// which ends the scan.
const SCAN = [0x12, 0xff, 0x00, 0x34, 0xff, 0xd3, 0x56, 0x78];

describe("isTruncatedImage", () => {
  it("passes Chromium's complete JPEG and flags every shorter prefix", () => {
    // A prefix from the 2-byte SOI to n - 1 bytes lacks the closing FF D9.
    const jpeg = fromBase64(SMALL_JPEG);
    expect(jpeg.length).toBe(858);
    expect(isTruncatedImage(jpeg)).toBe(false);
    for (let n = 2; n < jpeg.length; n++) {
      if (!isTruncatedImage(jpeg.subarray(0, n))) throw new Error(`a ${n}-byte prefix read as complete`);
    }
  });

  it("passes Chromium's complete PNG and flags every shorter prefix", () => {
    // A prefix from the 8-byte signature to n - 1 bytes lacks a whole IEND chunk.
    const png = fromBase64(SMALL_PNG);
    expect(png.length).toBe(155);
    expect(isTruncatedImage(png)).toBe(false);
    for (let n = 8; n < png.length; n++) {
      if (!isTruncatedImage(png.subarray(0, n))) throw new Error(`a ${n}-byte prefix read as complete`);
    }
  });

  it("skips a thumbnail's own scan and end marker inside APP1", () => {
    const head = [...SOI, ...APP1_WITH_THUMBNAIL, ...SOF0, ...DHT, ...SOS, ...SCAN];
    expect(isTruncatedImage(new Uint8Array([...head, ...EOI]))).toBe(false);
    expect(isTruncatedImage(new Uint8Array(head))).toBe(true);
    // Cut right after APP1: the thumbnail's FF D9 is there, the photo is not.
    expect(isTruncatedImage(new Uint8Array([...SOI, ...APP1_WITH_THUMBNAIL]))).toBe(true);
  });

  it("ignores bytes after the end of image (a motion photo's video)", () => {
    // Google and Samsung motion photos append an MP4 after FF D9; here the
    // trailer holds an FF DA and no FF D9 after it.
    const trailer = [0x66, 0x74, 0x79, 0x70, 0xff, 0xda, 0x00, 0x01];
    expect(isTruncatedImage(new Uint8Array([...SOI, ...SOF0, ...SOS, ...SCAN, ...EOI, ...trailer]))).toBe(false);
  });

  it("follows a progressive JPEG's scans to the end", () => {
    // Two scans with a Huffman table between them, as progressive files have.
    const head = [...SOI, ...SOF0, ...DHT, ...SOS, ...SCAN, ...DHT, ...SOS, ...SCAN];
    expect(isTruncatedImage(new Uint8Array([...head, ...EOI]))).toBe(false);
    expect(isTruncatedImage(new Uint8Array(head.slice(0, -3)))).toBe(true);
  });

  it("tolerates fill bytes and a stray byte before a marker, as libjpeg does", () => {
    const bytes = [...SOI, 0xff, 0xff, ...SOF0, 0x00, ...SOS, ...SCAN, 0xff, ...EOI];
    expect(isTruncatedImage(new Uint8Array(bytes))).toBe(false);
  });

  it("flags a segment whose length runs past the end", () => {
    // An APP1 that claims 0x1000 bytes with 4 present.
    expect(isTruncatedImage(new Uint8Array([...SOI, 0xff, 0xe1, 0x10, 0x00, 1, 2, 3, 4]))).toBe(true);
  });

  it("passes a PNG with bytes after IEND", () => {
    const png = fromBase64(SMALL_PNG);
    expect(isTruncatedImage(new Uint8Array([...png, 1, 2, 3]))).toBe(false);
  });

  it("leaves other formats to the browser", () => {
    // Text and a GIF header are neither JPEG (FF D8) nor PNG (89 50 4E 47 0D 0A 1A 0A).
    expect(isTruncatedImage(new TextEncoder().encode("hello, this is not a photo"))).toBe(false);
    expect(isTruncatedImage(new TextEncoder().encode("GIF89a"))).toBe(false);
    expect(isTruncatedImage(new Uint8Array(0))).toBe(false);
  });
});

describe("decodePhoto", () => {
  it("asks for the EXIF orientation", async () => {
    const bitmap = { width: 4, height: 3, close: vi.fn() };
    const create = vi.fn().mockResolvedValue(bitmap);
    vi.stubGlobal("createImageBitmap", create);
    const file = new Blob([fromBase64(SMALL_PNG)], { type: "image/png" });
    await expect(decodePhoto(file)).resolves.toBe(bitmap);
    expect(create).toHaveBeenCalledTimes(1);
    expect(create).toHaveBeenCalledWith(file, { imageOrientation: "from-image" });
  });

  it("retries without options when the browser rejects the options bag", async () => {
    const bitmap = { width: 4, height: 3, close: vi.fn() };
    const create = vi.fn().mockRejectedValueOnce(new TypeError("bad imageOrientation")).mockResolvedValueOnce(bitmap);
    vi.stubGlobal("createImageBitmap", create);
    const file = new Blob([fromBase64(SMALL_PNG)], { type: "image/png" });
    await expect(decodePhoto(file)).resolves.toBe(bitmap);
    expect(create).toHaveBeenCalledTimes(2);
    expect(create.mock.calls[1]).toEqual([file]);
  });

  it("turns a decode failure into a plain sentence", async () => {
    vi.stubGlobal("createImageBitmap", vi.fn().mockRejectedValue(new Error("The source image could not be decoded.")));
    const text = new Blob(["hello, this is not a photo"], { type: "text/plain" });
    await expect(decodePhoto(text)).rejects.toThrow(DECODE_ERROR);
    expect(DECODE_ERROR).toBe("QREP could not open this file. Choose a JPG or PNG photo of your quilt.");
  });

  it("reads only the 16-byte head of a file that is neither JPEG nor PNG", async () => {
    // A GIF head (47 49 46 38 39 61, "GIF89a") is neither FF D8 FF nor
    // 89 50 4E 47 0D 0A 1A 0A, so the whole file is never read: its
    // arrayBuffer throws, and only slice(0, 16) gives bytes.
    const bitmap = { width: 4, height: 3, close: vi.fn() };
    const create = vi.fn().mockResolvedValue(bitmap);
    vi.stubGlobal("createImageBitmap", create);
    const slices: [number | undefined, number | undefined][] = [];
    const whole = vi.fn(() => {
      throw new Error("read the whole file");
    });
    const file = {
      size: 50_000_000,
      type: "image/gif",
      slice: (start?: number, end?: number) => {
        slices.push([start, end]);
        return new Blob([new TextEncoder().encode("GIF89a\x04\x00\x03\x00")]);
      },
      arrayBuffer: whole,
    } as unknown as Blob;
    await expect(decodePhoto(file)).resolves.toBe(bitmap);
    expect(slices).toEqual([[0, 16]]);
    expect(whole).not.toHaveBeenCalled();
    expect(create).toHaveBeenCalledWith(file, { imageOrientation: "from-image" });
  });

  it("reads the whole file of a JPEG head for the integrity walk", async () => {
    // SMALL_JPEG starts FF D8 FF, so its whole 858 bytes are walked to FF D9.
    const bitmap = { width: 8, height: 8, close: vi.fn() };
    vi.stubGlobal("createImageBitmap", vi.fn().mockResolvedValue(bitmap));
    const file = new Blob([fromBase64(SMALL_JPEG)], { type: "image/jpeg" });
    const whole = vi.spyOn(file, "arrayBuffer");
    await expect(decodePhoto(file)).resolves.toBe(bitmap);
    expect(whole).toHaveBeenCalledTimes(1);
  });

  it("rejects a truncated JPEG before the browser can decode it blank", async () => {
    // WebKit 26.5 resolves a truncated JPEG to a transparent bitmap, so the
    // check runs first and the browser is never asked.
    const create = vi.fn();
    vi.stubGlobal("createImageBitmap", create);
    const jpeg = fromBase64(SMALL_JPEG);
    const cut = new Blob([jpeg.subarray(0, Math.floor(jpeg.length * 0.6))], { type: "image/jpeg" });
    await expect(decodePhoto(cut)).rejects.toThrow(DECODE_ERROR);
    expect(create).not.toHaveBeenCalled();
  });
});

describe("stagePhoto", () => {
  // A stand-in OffscreenCanvas (no document in Node) that records the draw.
  function fakeCanvas() {
    const draws: unknown[][] = [];
    const ctx = {
      imageSmoothingEnabled: false,
      imageSmoothingQuality: "low",
      drawImage: (...args: unknown[]) => draws.push(args),
    };
    const sizes: number[][] = [];
    const types: unknown[] = [];
    class FakeOffscreenCanvas {
      constructor(width: number, height: number) {
        sizes.push([width, height]);
      }
      getContext() {
        return ctx;
      }
      convertToBlob(options: { type: string }) {
        types.push(options.type);
        return Promise.resolve(new Blob([new Uint8Array([137, 80, 78, 71])], { type: options.type }));
      }
    }
    vi.stubGlobal("OffscreenCanvas", FakeOffscreenCanvas);
    return { ctx, draws, sizes, types };
  }

  it("cuts the planned crop at full resolution and draws it at the staged size", async () => {
    const canvas = fakeCanvas();
    const bitmap = { width: 1290, height: 2796, close: vi.fn() };
    const staged = await stagePhoto(bitmap as unknown as ImageBitmap, DOCS03_CORNERS, 18.5);
    // The docs-03 plan by hand: offset (256, 1009), crop 778 x 778, staged 778 x 778.
    expect(staged.plan.offset).toEqual({ x: 256, y: 1009 });
    expect(canvas.sizes).toEqual([[778, 778]]);
    expect(canvas.draws).toEqual([[bitmap, 256, 1009, 778, 778, 0, 0, 778, 778]]);
    expect(canvas.ctx.imageSmoothingQuality).toBe("high");
    expect(canvas.types).toEqual(["image/png"]);
    expect(Array.from(staged.bytes)).toEqual([137, 80, 78, 71]);
    // The caller owns a bitmap it passed in.
    expect(bitmap.close).not.toHaveBeenCalled();
  });

  it("decodes a Blob, stages it at the cap and closes the bitmap it made", async () => {
    const canvas = fakeCanvas();
    const bitmap = { width: 8000, height: 6000, close: vi.fn() };
    vi.stubGlobal("createImageBitmap", vi.fn().mockResolvedValue(bitmap));
    const corners: Corners = {
      top_left: { x: 900, y: 700 },
      top_right: { x: 7100, y: 700 },
      bottom_right: { x: 7100, y: 5300 },
      bottom_left: { x: 900, y: 5300 },
    };
    const file = new Blob([fromBase64(SMALL_PNG)], { type: "image/png" });
    const staged = await stagePhoto(file, corners, 100);
    // The 8000 x 6000 plan by hand: offset (800, 600), crop 6400 x 4800,
    // staged 2000 x 1500.
    expect(canvas.draws).toEqual([[bitmap, 800, 600, 6400, 4800, 0, 0, 2000, 1500]]);
    expect(staged.plan.staged).toEqual({ width: 2000, height: 1500 });
    expect(bitmap.close).toHaveBeenCalledTimes(1);
  });
});
