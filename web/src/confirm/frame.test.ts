/**
 * The two frames of plan section 2.1 (C3a, issue #149): four field corners,
 * or the outer quilt edge with border bands, emitted in E1b's request shape.
 */
import { describe, expect, it } from "vitest";
import type { Corners } from "../engine/contract";
import { cornersToQuad, fieldInsideProblem, neutralInset, quadProblem, quadToCorners, toRequestFrame } from "./frame";

const SQUARE: Corners = {
  top_left: { x: 100, y: 50 },
  top_right: { x: 500, y: 50 },
  bottom_right: { x: 500, y: 450 },
  bottom_left: { x: 100, y: 450 },
};

describe("E1b's request shape", () => {
  it("emits the field frame as four corners", () => {
    // web/src/engine/contract.ts FieldFrame: kind "field" and corners only.
    const frame = toRequestFrame("field", SQUARE, [{ width_squares: 1 }]);
    expect(frame).toEqual({ kind: "field", corners: SQUARE });
  });

  it("emits the outer edge with each band's width in squares, outside in", () => {
    // web/src/engine/contract.ts OuterEdgeFrame: kind, corners and bands.
    const frame = toRequestFrame("outer_edge", SQUARE, [{ width_squares: 2 }, { width_squares: 0.5 }]);
    expect(frame).toEqual({
      kind: "outer_edge",
      corners: SQUARE,
      bands: [{ width_squares: 2 }, { width_squares: 0.5 }],
    });
  });

  it("converts between corners and the quad order top left, clockwise", () => {
    const quad = cornersToQuad(SQUARE);
    expect(quad).toEqual([SQUARE.top_left, SQUARE.top_right, SQUARE.bottom_right, SQUARE.bottom_left]);
    expect(quadToCorners(quad)).toEqual(SQUARE);
  });
});

describe("pins start at a neutral inset (plan section 2.1)", () => {
  it("insets each pin 15 percent from the image edges", () => {
    // Inputs: a 1000 x 800 image, inset 0.15
    // Arithmetic: x 0.15 x 1000 = 150 and 0.85 x 1000 = 850;
    //             y 0.15 x 800 = 120 and 0.85 x 800 = 680
    expect(neutralInset({ width: 1000, height: 800 })).toEqual({
      top_left: { x: 150, y: 120 },
      top_right: { x: 850, y: 120 },
      bottom_right: { x: 850, y: 680 },
      bottom_left: { x: 150, y: 680 },
    });
  });
});

describe("quad checks before saving", () => {
  // The same checks as scripts/eval/qrep_eval/annotation.py _check_quad and
  // _quads_in_order, so a file the page saves loads there.
  it("accepts a convex quad in corner order", () => {
    expect(quadProblem(SQUARE)).toBeNull();
  });

  it("refuses swapped corners", () => {
    const swapped = { ...SQUARE, top_left: SQUARE.top_right, top_right: SQUARE.top_left };
    expect(quadProblem(swapped)).toMatch(/order/);
  });

  it("refuses a concave quad whose corners are each on their own side", () => {
    // Inputs: bottom left moved to (400, 100); the order checks pass
    // (100 < 500, 400 < 500, 50 < 100, 50 < 450).
    // Cross at bottom right, bottom left, top left, with y down:
    //   (BL - BR) = (-100, -350), (TL - BR) = (-400, -400)
    //   (-100)(-400) - (-350)(-400) = 40000 - 140000 = -100000, not positive
    // Expected: refused as concave
    const concave = { ...SQUARE, bottom_left: { x: 400, y: 100 } };
    expect(quadProblem(concave)).toMatch(/concave/);
  });

  it("requires the field inside the outer edge, or on it with no border", () => {
    const inner: Corners = {
      top_left: { x: 140, y: 90 },
      top_right: { x: 460, y: 90 },
      bottom_right: { x: 460, y: 410 },
      bottom_left: { x: 140, y: 410 },
    };
    expect(fieldInsideProblem(SQUARE, inner)).toBeNull();
    expect(fieldInsideProblem(SQUARE, SQUARE)).toBeNull();
    const outside = { ...inner, top_left: { x: 90, y: 90 } };
    expect(fieldInsideProblem(SQUARE, outside)).toMatch(/outside/);
  });
});
