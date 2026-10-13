/**
 * Counts in quilter units (C3a, issue #149; plan section 2.1): blocks across
 * x squares per block, and the same down, with the one-square seed.
 */
import { describe, expect, it } from "vitest";
import {
  axisLabel,
  fromCounts,
  parseCount,
  seedAxis,
  seedFromSquare,
  seedSquares,
  toCounts,
  totalSquares,
} from "./counts";
import { squareToQuad, type Quad } from "./geometry";

describe("totals", () => {
  it("multiplies blocks by squares per block on each axis", () => {
    // Source: issue #149 criterion 1.
    // Arithmetic: 9 blocks across x 5 squares = 45 columns;
    //             11 blocks down x 5 squares = 55 rows
    expect(totalSquares({ blocks: 9, squaresPerBlock: 5 })).toBe(45);
    expect(totalSquares({ blocks: 11, squaresPerBlock: 5 })).toBe(55);
  });

  it("labels the total in quilter units", () => {
    // Source: plan section 2.1, screen 2: "8 blocks x 5 squares = 40 squares".
    // Arithmetic: 8 x 5 = 40; 1 x 40 = 40 (no repeating block); 1 x 1 = 1
    expect(axisLabel({ blocks: 8, squaresPerBlock: 5 })).toBe("8 blocks x 5 squares = 40 squares");
    expect(axisLabel({ blocks: 1, squaresPerBlock: 40 })).toBe("1 block x 40 squares = 40 squares");
    expect(axisLabel({ blocks: 1, squaresPerBlock: 1 })).toBe("1 block x 1 square = 1 square");
  });

  it("emits and reads E1b's Counts fields", () => {
    // web/src/engine/contract.ts Counts: blocks_across, blocks_down,
    // squares_per_block_across, squares_per_block_down.
    const counts = toCounts({ blocks: 9, squaresPerBlock: 5 }, { blocks: 11, squaresPerBlock: 5 });
    expect(counts).toEqual({
      blocks_across: 9,
      blocks_down: 11,
      squares_per_block_across: 5,
      squares_per_block_down: 5,
    });
    expect(fromCounts(counts)).toEqual({
      across: { blocks: 9, squaresPerBlock: 5 },
      down: { blocks: 11, squaresPerBlock: 5 },
    });
  });

  it("accepts a typed count only as a whole number of at least 1", () => {
    // The annotation schema's Counts fields are integers with minimum 1.
    expect(parseCount("12")).toBe(12);
    expect(parseCount(" 7 ")).toBe(7);
    expect(parseCount("0")).toBeNull();
    expect(parseCount("2.5")).toBeNull();
    expect(parseCount("")).toBeNull();
    expect(parseCount("x3")).toBeNull();
  });
});

describe("the one-square seed", () => {
  it("divides the span between pins by one square's width", () => {
    // Source: issue #149 criterion 1.
    // Arithmetic: 400 px / 25 px = 16 squares
    expect(seedSquares(400, 25)).toBe(16);
  });

  it("measures the square in the rectified plane", () => {
    // Inputs: quad (100, 50) to (500, 450); one square from (100, 50) to (125, 75)
    // Arithmetic: across, the square spans 25 / 400 = 0.0625 of the quad, so
    //             1 / 0.0625 = 16 squares; down, 25 / 400 likewise, 16 squares
    // Expected: 16 across and 16 down with no bands
    const quad: Quad = [
      { x: 100, y: 50 },
      { x: 500, y: 50 },
      { x: 500, y: 450 },
      { x: 100, y: 450 },
    ];
    const square = [{ x: 100, y: 50 }, { x: 125, y: 75 }] as const;
    expect(seedFromSquare(squareToQuad(quad), square, 0)).toEqual({ across: 16, down: 16 });
    // With border bands totalling 2 squares on each side, the outer edge spans
    // 16 squares, so the field spans 16 - 2 x 2 = 12 each way.
    expect(seedFromSquare(squareToQuad(quad), square, 2)).toEqual({ across: 12, down: 12 });
  });

  it("keeps the block period when it divides the seeded total, else uses one block", () => {
    // Arithmetic: 45 / 5 = 9 blocks of 5; 16 / 5 is not whole, so 1 block of 16
    expect(seedAxis({ blocks: 1, squaresPerBlock: 5 }, 45)).toEqual({ blocks: 9, squaresPerBlock: 5 });
    expect(seedAxis({ blocks: 1, squaresPerBlock: 5 }, 16)).toEqual({ blocks: 1, squaresPerBlock: 16 });
  });
});
