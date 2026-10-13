/**
 * Confirm-screen geometry (C3a, issue #149): pins map from the image
 * element's own rect, and the grid is drawn through the unit-square-to-quad
 * homography. Every expected value is computed by hand in the comments.
 */
import { describe, expect, it } from "vitest";
import {
  applyHomography,
  displayToFraction,
  displayToSource,
  gridLines,
  invertHomography,
  snapToPixel,
  sourceToDisplay,
  squareToQuad,
  type Quad,
} from "./geometry";

const RECT = { left: 100, top: 50, width: 400, height: 300 };
const SOURCE = { width: 2000, height: 1500 };

describe("pins map from the image element's own rect (ux-06)", () => {
  it("places a pin at its fraction of the image rect, not of the padded box", () => {
    // Source: issue #149 criterion 1 (ux-06).
    // Formula: fraction = (pin x - rect left) / rect width
    // Inputs: pin x 636.35, rect left 595.42, rect width 249.14
    // Arithmetic: 636.35 - 595.42 = 40.93; 40.93 / 249.14 = 0.16428
    // Expected: 0.1643 (the 834d8be crop screen stored 0.1982 from the padded box)
    const rect = { left: 595.42, top: 0, width: 249.14, height: 100 };
    expect(displayToFraction({ x: 636.35, y: 50 }, rect).x).toBeCloseTo(0.1643, 4);
  });

  it("scales the fraction to source-image pixels", () => {
    // Formula: source = (display - rect origin) / rect size x source size
    // Inputs: display (300, 200), rect at (100, 50) sized 400 x 300, source 2000 x 1500
    // Arithmetic: x (300 - 100) / 400 = 0.5, 0.5 x 2000 = 1000;
    //             y (200 - 50) / 300 = 0.5, 0.5 x 1500 = 750
    // Expected: (1000, 750)
    expect(displayToSource({ x: 300, y: 200 }, RECT, SOURCE)).toEqual({ x: 1000, y: 750 });
  });

  it("clamps a pin dragged off the image to the image edge (vision-15)", () => {
    // Inputs: display (50, 400) with the same rect and source
    // Arithmetic: x (50 - 100) / 400 = -0.125, clamped to 0, so 0 px;
    //             y (400 - 50) / 300 = 1.1667, clamped to 1, so 1500 px
    // Expected: (0, 1500)
    expect(displayToSource({ x: 50, y: 400 }, RECT, SOURCE)).toEqual({ x: 0, y: 1500 });
  });

  it("maps a source pixel back onto the rect", () => {
    // Formula: display = rect origin + source / source size x rect size
    // Inputs: source (1000, 750)
    // Arithmetic: x 100 + 1000 / 2000 x 400 = 300; y 50 + 750 / 1500 x 300 = 200
    // Expected: (300, 200)
    expect(sourceToDisplay({ x: 1000, y: 750 }, RECT, SOURCE)).toEqual({ x: 300, y: 200 });
  });

  it("snaps a pin to the nearest whole source pixel inside the image", () => {
    // Inputs: (328.57, -0.4) and (1999.6, 1500.2) on a 2000 x 1500 source
    // Arithmetic: round(328.57) = 329, round(-0.4) = 0 (clamped at 0);
    //             round(1999.6) = 2000, round(1500.2) = 1500
    // Expected: (329, 0) and (2000, 1500)
    expect(snapToPixel({ x: 328.57, y: -0.4 }, SOURCE)).toEqual({ x: 329, y: 0 });
    expect(snapToPixel({ x: 1999.6, y: 1500.2 }, SOURCE)).toEqual({ x: 2000, y: 1500 });
  });
});

const AXIS_QUAD: Quad = [
  { x: 100, y: 50 },
  { x: 500, y: 50 },
  { x: 500, y: 450 },
  { x: 100, y: 450 },
];

// A trapezoid: the top edge is wider than the bottom, as when the camera
// tilts toward the quilt's lower edge.
const TRAPEZOID: Quad = [
  { x: 0, y: 0 },
  { x: 400, y: 0 },
  { x: 300, y: 200 },
  { x: 100, y: 200 },
];

describe("the unit-square-to-quad homography", () => {
  it("sends the unit square's corners to the quad's corners", () => {
    // By construction: (0, 0) to top left, (1, 0) to top right, (1, 1) to
    // bottom right, (0, 1) to bottom left.
    const h = squareToQuad(TRAPEZOID);
    const corners = [
      applyHomography(h, 0, 0),
      applyHomography(h, 1, 0),
      applyHomography(h, 1, 1),
      applyHomography(h, 0, 1),
    ];
    corners.forEach((corner, i) => {
      expect(corner.x).toBeCloseTo(TRAPEZOID[i].x, 9);
      expect(corner.y).toBeCloseTo(TRAPEZOID[i].y, 9);
    });
  });

  it("puts the square's center where the quad's diagonals cross", () => {
    // A homography keeps lines and where they meet, so the unit square's
    // center, where its diagonals cross, lands where the quad's diagonals cross.
    // Diagonal top left to bottom right: (300t, 200t).
    // Diagonal top right to bottom left: (400 - 300s, 200s).
    // Arithmetic: 200t = 200s, so t = s; 300t = 400 - 300t, so t = 2/3.
    // Expected: (300 x 2/3, 200 x 2/3) = (200, 133.33)
    const center = applyHomography(squareToQuad(TRAPEZOID), 0.5, 0.5);
    expect(center.x).toBeCloseTo(200, 9);
    expect(center.y).toBeCloseTo(400 / 3, 9);
  });

  it("inverts: a point mapped forward and back returns to itself", () => {
    // Identity: inverse(forward(u, v)) = (u, v) for (0.3, 0.7).
    const h = squareToQuad(TRAPEZOID);
    const p = applyHomography(h, 0.3, 0.7);
    const back = invertHomography(h)(p);
    expect(back.u).toBeCloseTo(0.3, 9);
    expect(back.v).toBeCloseTo(0.7, 9);
  });
});

describe("grid lines", () => {
  it("divides an axis-aligned quad into equal squares", () => {
    // Source: issue #149 criterion 1.
    // Formula: pitch = (right - left) / columns; line i at left + i x pitch
    // Inputs: quad (100, 50) to (500, 450), 4 x 4 squares
    // Arithmetic: pitch = (500 - 100) / 4 = 100; interior lines at
    //             100 + 100 = 200, 100 + 200 = 300, 100 + 300 = 400
    // Expected: interior verticals at x 200, 300 and 400, each from y 50 to 450
    const lines = gridLines(squareToQuad(AXIS_QUAD), 4, 4);
    expect(lines.vertical).toHaveLength(5);
    const interior = lines.vertical.slice(1, 4);
    expect(interior.map(([a]) => a.x)).toEqual([200, 300, 400]);
    for (const [a, b] of interior) {
      expect(a.x).toBeCloseTo(b.x, 9);
      expect(a.y).toBeCloseTo(50, 9);
      expect(b.y).toBeCloseTo(450, 9);
    }
    expect(lines.horizontal.slice(1, 4).map(([a]) => a.y)).toEqual([150, 250, 350]);
  });

  it("draws a trapezoid's middle lines where perspective puts them, not halfway", () => {
    // Source: PR #247 review of 0b7e9a3 (geometry.test.ts:123), a hand vector.
    // Inputs: TRAPEZOID, 2 x 2 squares.
    // The middle row line (v = 0.5) passes through the square's center, where
    // the diagonals cross, (200, 400 / 3) (test above). The top and bottom
    // edges are both horizontal, so they meet at infinity and the line through
    // the center toward that point is horizontal: y = 400 / 3 = 133.33. It
    // runs from the left edge x = y / 2 = 66.67 to the right edge
    // x = 400 - y / 2 = 333.33. Halfway between the edges would be y = 100.
    // The middle column line (u = 0.5) runs from the center toward where the
    // side edges meet: x = y / 2 and x = 400 - y / 2 cross at (200, 400), so it
    // is x = 200, from (200, 0) to (200, 200).
    const lines = gridLines(squareToQuad(TRAPEZOID), 2, 2);
    const [left, right] = lines.horizontal[1];
    expect(left.x).toBeCloseTo(200 / 3, 9);
    expect(left.y).toBeCloseTo(400 / 3, 9);
    expect(right.x).toBeCloseTo(1000 / 3, 9);
    expect(right.y).toBeCloseTo(400 / 3, 9);
    const [top, bottom] = lines.vertical[1];
    expect(top.x).toBeCloseTo(200, 9);
    expect(top.y).toBeCloseTo(0, 9);
    expect(bottom.x).toBeCloseTo(200, 9);
    expect(bottom.y).toBeCloseTo(200, 9);
  });

  it("draws only inside a sub-range of the unit square", () => {
    // Inputs: the same quad, 2 columns across u from 0.25 to 0.75
    // Arithmetic: u 0.25 is x 100 + 0.25 x 400 = 200; u 0.5 is 300; u 0.75 is 400;
    //             each line runs over v 0 to 1, y 50 to 450
    // Expected: verticals at x 200, 300 and 400
    const lines = gridLines(squareToQuad(AXIS_QUAD), 2, 1, { u0: 0.25, u1: 0.75, v0: 0, v1: 1 });
    expect(lines.vertical.map(([a]) => a.x)).toEqual([200, 300, 400]);
  });
});
