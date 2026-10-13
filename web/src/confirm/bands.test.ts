/**
 * Border bands set inward from the outer edge (C3a, issue #149; plan section
 * 2.1): one width per band in finished squares, from a dragged inner line
 * converted in the rectified plane, a stepper, or a typed width in inches.
 */
import { describe, expect, it } from "vitest";
import {
  bandHandles,
  fieldQuad,
  fieldRange,
  inchesToSquares,
  roundQuarterInch,
  squaresToInches,
  stepBand,
  widthFromDepth,
  widthFromHandle,
} from "./bands";
import { squareToQuad, type Quad } from "./geometry";

// An outer edge 400 px square from (0, 0), with 8 x 8 squares in the field.
const OUTER: Quad = [
  { x: 0, y: 0 },
  { x: 400, y: 0 },
  { x: 400, y: 400 },
  { x: 0, y: 400 },
];

describe("the field inside the bands", () => {
  it("leaves the outer edge minus a band on each side", () => {
    // Source: issue #149 criterion 1.
    // Inputs: outer edge 400 px; 8 field squares and one band 1 square wide
    // Arithmetic: 8 + 2 x 1 = 10 squares span 400 px, so 40 px per square and
    //             the band is 40 px deep; the field is 400 - 2 x 40 = 320 px,
    //             from x 40 to x 360
    // Expected: field corners (40, 40) and (360, 360), 320 px across
    const field = fieldQuad(squareToQuad(OUTER), 8, 8, [{ width_squares: 1 }]);
    expect(field[0].x).toBeCloseTo(40, 9);
    expect(field[0].y).toBeCloseTo(40, 9);
    expect(field[2].x).toBeCloseTo(360, 9);
    expect(field[2].y).toBeCloseTo(360, 9);
    expect(field[1].x - field[0].x).toBeCloseTo(320, 9);
  });

  it("measures each axis against its own square count", () => {
    // Inputs: 6 columns, 10 rows, bands 1 and 0.5 squares (1.5 in all)
    // Arithmetic: across 6 + 2 x 1.5 = 9 squares, u0 = 1.5 / 9 = 0.1667;
    //             down 10 + 2 x 1.5 = 13 squares, v0 = 1.5 / 13 = 0.1154
    const range = fieldRange(6, 10, [{ width_squares: 1 }, { width_squares: 0.5 }]);
    expect(range.u0).toBeCloseTo(1.5 / 9, 12);
    expect(range.u1).toBeCloseTo(7.5 / 9, 12);
    expect(range.v0).toBeCloseTo(1.5 / 13, 12);
    expect(range.v1).toBeCloseTo(11.5 / 13, 12);
  });
});

describe("a dragged inner line", () => {
  it("converts its depth to the band's width in squares", () => {
    // Formula: the inner line of band k sits at depth f = D / N, where D is
    // the bands' width through k and N = squares + 2 x all bands. With P the
    // bands outside k and S the other bands' total, f (squares + 2S + 2w) =
    // P + w, so w = (f (squares + 2S) - P) / (1 - 2f).
    // Inputs: 8 squares, one band, line dragged to x 40 on a 0 to 400 edge
    // Arithmetic: f = 40 / 400 = 0.1; w = (0.1 x 8 - 0) / (1 - 0.2) = 1.0
    // Check: 8 + 2 x 1 = 10 squares over 400 px is 40 px each, so the line is at 40.
    // The band's width before the drag (2) does not enter the formula.
    expect(widthFromDepth(0.1, 8, [{ width_squares: 2 }], 0)).toBeCloseTo(1, 12);
    // Inputs: 6 squares, bands [1, 1], band 2 dragged to f = 0.3
    // Arithmetic: P = 1, S = 1; w = (0.3 x (6 + 2) - 1) / (1 - 0.6) = 1.4 / 0.4 = 3.5
    // Check: 6 + 2 x 4.5 = 15 squares; (1 + 3.5) / 15 = 0.3
    expect(widthFromDepth(0.3, 6, [{ width_squares: 1 }, { width_squares: 1 }], 1)).toBeCloseTo(3.5, 12);
  });

  it("refuses a depth that leaves no field or no band", () => {
    // f = 0.5 or deeper leaves no field (1 - 2f <= 0); a line outside the
    // band's outer edge gives w <= 0. Both return null so the drag holds.
    expect(widthFromDepth(0.5, 8, [{ width_squares: 1 }], 0)).toBeNull();
    // P = 1: f = 0.05 gives w = (0.05 x (6 + 2) - 1) / 0.9 < 0
    expect(widthFromDepth(0.05, 6, [{ width_squares: 1 }, { width_squares: 1 }], 1)).toBeNull();
  });

  it("puts a handle at the middle of each side of the band's inner line", () => {
    // Inputs: OUTER, 8 x 8 squares, one band 1 square wide
    // Arithmetic: the inner line is 40 px in (see above); side midpoints are
    //             (200, 40), (360, 200), (200, 360) and (40, 200)
    const handles = bandHandles(squareToQuad(OUTER), 8, 8, [{ width_squares: 1 }], 0);
    expect(handles.top.x).toBeCloseTo(200, 9);
    expect(handles.top.y).toBeCloseTo(40, 9);
    expect(handles.right.x).toBeCloseTo(360, 9);
    expect(handles.bottom.y).toBeCloseTo(360, 9);
    expect(handles.left.x).toBeCloseTo(40, 9);
  });

  it("puts a trapezoid's handles at the rectified midpoints of the inner line", () => {
    // Source: PR #247 review of 0b7e9a3 (bands.test.ts:93), a hand vector.
    // Inputs: the trapezoid (0, 0), (400, 0), (300, 200), (100, 200); 10 x 6
    // squares; one band 1.25 squares wide.
    // The homography (geometry.ts squareToQuad): sx = 0 - 400 + 300 - 100 =
    // -200, sy = 0; dx1 = 100, dx2 = -200, dy1 = -200, dy2 = 0; det = 0 -
    // (-200 x -200) = -40000; g = (0 - 0) / det = 0; h = (0 - (-200 x -200)) /
    // det = 1; a = 400, b = 100 + 100 = 200, c = 0, d = 0, e = 200 + 200 = 400,
    // f = 0. So x = (400u + 200v) / (v + 1) and y = 400v / (v + 1).
    // The inner line: u0 = 1.25 / (10 + 2.5) = 0.1, u1 = 0.9;
    // v0 = 1.25 / (6 + 2.5) = 1.25 / 8.5, v1 = 7.25 / 8.5.
    // Left (0.1, 0.5): x = (40 + 100) / 1.5 = 93.33, y = 200 / 1.5 = 133.33.
    // Right (0.9, 0.5): x = (360 + 100) / 1.5 = 306.67, y = 133.33.
    // Top (0.5, v0): x = (200 + 200 v0) / (v0 + 1) = 200; y = 400 x 1.25 /
    // (1.25 + 8.5) = 500 / 9.75 = 51.28.
    // Bottom (0.5, v1): x = 200; y = 400 x 7.25 / (7.25 + 8.5) = 2900 / 15.75 = 184.13.
    // The left side's pixel midpoint would sit at y = (51.28 + 184.13) / 2 = 117.70.
    const trapezoid: Quad = [
      { x: 0, y: 0 },
      { x: 400, y: 0 },
      { x: 300, y: 200 },
      { x: 100, y: 200 },
    ];
    const handles = bandHandles(squareToQuad(trapezoid), 10, 6, [{ width_squares: 1.25 }], 0);
    expect(handles.left.x).toBeCloseTo(280 / 3, 9);
    expect(handles.left.y).toBeCloseTo(400 / 3, 9);
    expect(handles.right.x).toBeCloseTo(920 / 3, 9);
    expect(handles.right.y).toBeCloseTo(400 / 3, 9);
    expect(handles.top.x).toBeCloseTo(200, 9);
    expect(handles.top.y).toBeCloseTo(500 / 9.75, 9);
    expect(handles.bottom.x).toBeCloseTo(200, 9);
    expect(handles.bottom.y).toBeCloseTo(2900 / 15.75, 9);
  });

  it("reads a handle dragged in perspective through the rectified plane", () => {
    // Round trip on a trapezoid: the handle drawn for a 1.25 square band,
    // dragged nowhere, reads back as 1.25 squares from every side.
    const trapezoid: Quad = [
      { x: 0, y: 0 },
      { x: 400, y: 0 },
      { x: 300, y: 200 },
      { x: 100, y: 200 },
    ];
    const h = squareToQuad(trapezoid);
    const bands = [{ width_squares: 1.25 }];
    const handles = bandHandles(h, 10, 6, bands, 0);
    for (const side of ["top", "right", "bottom", "left"] as const) {
      expect(widthFromHandle(h, side, handles[side], 10, 6, bands, 0)).toBeCloseTo(1.25, 9);
    }
    // Dragged on an axis-aligned edge: the left handle moved to x 80 is
    // f = 80 / 400 = 0.2, so w = (0.2 x 8) / (1 - 0.4) = 2.6667 squares.
    expect(
      widthFromHandle(squareToQuad(OUTER), "left", { x: 80, y: 200 }, 8, 8, [{ width_squares: 1 }], 0),
    ).toBeCloseTo(1.6 / 0.6, 4);
  });
});

describe("typed inches and steppers", () => {
  it("rounds a typed width to the nearest quarter inch", () => {
    // Arithmetic: 3.1 x 4 = 12.4, rounds to 12, so 3 in;
    //             3.13 x 4 = 12.52, rounds to 13, so 3.25 in
    expect(roundQuarterInch(3.1)).toBe(3);
    expect(roundQuarterInch(3.13)).toBe(3.25);
  });

  it("converts inches to squares with the finished square size in eighths", () => {
    // Inputs: a 1 1/2 in square is 12 eighths
    // Arithmetic: 3.1 in rounds to 3 in, 3 / 1.5 = 2 squares;
    //             1.3 in rounds to 1.25 in, 1.25 / 1.5 = 0.8333 squares
    expect(inchesToSquares(3.1, 12)).toBe(2);
    expect(inchesToSquares(1.3, 12)).toBeCloseTo(0.8333, 4);
    // Arithmetic: 2 squares x 1.5 in = 3 in
    expect(squaresToInches(2, 12)).toBe(3);
  });

  it("steps a band by a whole square and never to zero", () => {
    // Steppers count whole squares, so they need no square size (decision on
    // #149, comment 6142353076). Arithmetic: 2.15 + 1 = 3.15; 1.3333 - 1 =
    // 0.3333; 1 - 1 = 0 is not positive, so the width stays 1
    expect(stepBand(2.15, 1)).toBe(3.15);
    expect(stepBand(1.3333, -1)).toBe(0.3333);
    expect(stepBand(1, -1)).toBe(1);
  });

  it("keeps a quarter-inch border on the quarter-inch grid when it steps", () => {
    // Source: PR #247 review of 0b7e9a3 (bands.ts:22-23); plan section 2.1,
    // Screen 4: border widths in 1/4 in steps. Every offered square size is a whole number of
    // quarter inches (3/4 in to 4 in), so a whole-square step adds one.
    // Inputs: a 1 1/2 in square (12 eighths), a band of 1 square (1 1/2 in)
    // Arithmetic: 1 + 1 = 2 squares, 2 x 1.5 = 3 in; 3 x 4 = 12 quarters, whole
    expect(squaresToInches(stepBand(1, 1), 12)).toBe(3);
  });
});
