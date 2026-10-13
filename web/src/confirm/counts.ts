/**
 * Counts in quilter units (C3a, issue #149; plan section 2.1): blocks across
 * x squares per block, and blocks down x squares per block. Entering the
 * block period is how the user confirms it, and the period drives the read
 * and the method (Critique: CR-cv-03, CR-product-18). A quilt with no
 * repeating block uses one block per axis.
 */
import type { Counts, Point } from "../engine/contract";
import { invertHomography, type Homography } from "./geometry";

export interface AxisCount {
  blocks: number;
  squaresPerBlock: number;
}

/** A typed count above this is a slip of the finger, not a quilt. */
export const COUNT_MAX = 999;

export function totalSquares(axis: AxisCount): number {
  return axis.blocks * axis.squaresPerBlock;
}

const plural = (n: number, word: string) => `${n} ${word}${n === 1 ? "" : "s"}`;

/** "8 blocks x 5 squares = 40 squares" (plan section 2.1). */
export function axisLabel(axis: AxisCount): string {
  return (
    `${plural(axis.blocks, "block")} x ${plural(axis.squaresPerBlock, "square")} = ` +
    plural(totalSquares(axis), "square")
  );
}

export function toCounts(across: AxisCount, down: AxisCount): Counts {
  return {
    blocks_across: across.blocks,
    blocks_down: down.blocks,
    squares_per_block_across: across.squaresPerBlock,
    squares_per_block_down: down.squaresPerBlock,
  };
}

export function fromCounts(counts: Counts): { across: AxisCount; down: AxisCount } {
  return {
    across: { blocks: counts.blocks_across, squaresPerBlock: counts.squares_per_block_across },
    down: { blocks: counts.blocks_down, squaresPerBlock: counts.squares_per_block_down },
  };
}

/** A typed count: a whole number from 1 to COUNT_MAX, or null. */
export function parseCount(text: string): number | null {
  const trimmed = text.trim();
  if (!/^\d+$/.test(trimmed)) return null;
  const value = Number(trimmed);
  return value >= 1 && value <= COUNT_MAX ? value : null;
}

export function clampCount(value: number): number {
  return Math.min(COUNT_MAX, Math.max(1, Math.round(value)));
}

/** The geometric estimate: how many squares of one width fit in a span. */
export function seedSquares(spanPx: number, squarePx: number): number {
  return clampCount(spanPx / squarePx);
}

/**
 * Squares across and down the field from one square the user marked by two
 * opposite corners, measured in the rectified plane of the pinned quad so
 * perspective does not skew it. bandSquares is the bands' total width in
 * squares on each side, zero for a field frame.
 */
export function seedFromSquare(
  m: Homography,
  square: readonly [Point, Point],
  bandSquares: number,
): { across: number; down: number } {
  const toUV = invertHomography(m);
  const a = toUV(square[0]);
  const b = toUV(square[1]);
  const du = Math.abs(b.u - a.u);
  const dv = Math.abs(b.v - a.v);
  return {
    across: clampCount(1 / du - 2 * bandSquares),
    down: clampCount(1 / dv - 2 * bandSquares),
  };
}

/** Keeps the block period when it divides the seeded total; else one block. */
export function seedAxis(axis: AxisCount, total: number): AxisCount {
  if (total % axis.squaresPerBlock === 0) {
    return { blocks: total / axis.squaresPerBlock, squaresPerBlock: axis.squaresPerBlock };
  }
  return { blocks: 1, squaresPerBlock: total };
}
