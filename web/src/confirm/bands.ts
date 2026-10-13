/**
 * Border bands set inward from the outer edge (C3a, issue #149; plan section
 * 2.1; Critique: CR-cv-25). Each band has one width in finished squares that
 * need not be whole, the shape E1b's request takes (BorderBand).
 *
 * In the rectified plane of the outer edge, the field has cols x rows
 * squares and every band adds its width on both sides, so the outer edge
 * spans cols + 2B squares across and rows + 2B down, B being the bands'
 * total. A band's inner line therefore sits at depth D / N, where D is the
 * width of the bands through it and N the squares on that axis.
 */
import type { BorderBand, Point } from "../engine/contract";
import {
  applyHomography,
  invertHomography,
  rangeQuad,
  type Homography,
  type Quad,
  type UVRange,
} from "./geometry";

/** Steppers count squares, so they work before a square size is set (#149, comment 6142353076). */
export const BAND_STEP_SQUARES = 0.25;

export type BandSide = "top" | "right" | "bottom" | "left";

export function bandTotal(bands: readonly BorderBand[]): number {
  return bands.reduce((sum, band) => sum + band.width_squares, 0);
}

function insetRange(cols: number, rows: number, bands: readonly BorderBand[], depth: number): UVRange {
  const total = bandTotal(bands);
  const u = depth / (cols + 2 * total);
  const v = depth / (rows + 2 * total);
  return { u0: u, u1: 1 - u, v0: v, v1: 1 - v };
}

/** The field's part of the rectified plane. */
export function fieldRange(cols: number, rows: number, bands: readonly BorderBand[]): UVRange {
  return insetRange(cols, rows, bands, bandTotal(bands));
}

/** The rectified range inside band k's inner line. */
export function bandRange(cols: number, rows: number, bands: readonly BorderBand[], k: number): UVRange {
  return insetRange(cols, rows, bands, bandTotal(bands.slice(0, k + 1)));
}

export function fieldQuad(m: Homography, cols: number, rows: number, bands: readonly BorderBand[]): Quad {
  return rangeQuad(m, fieldRange(cols, rows, bands));
}

/**
 * Band k's width when its inner line sits at depth f on an axis of squares
 * field squares, or null when that depth leaves no field or no band. From
 * f (squares + 2S + 2w) = P + w, with P the bands outside k and S the other
 * bands' total: w = (f (squares + 2S) - P) / (1 - 2f).
 */
export function widthFromDepth(f: number, squares: number, bands: readonly BorderBand[], k: number): number | null {
  if (!(f > 0 && f < 0.5)) return null;
  const outside = bandTotal(bands.slice(0, k));
  const others = bandTotal(bands) - bands[k].width_squares;
  const width = (f * (squares + 2 * others) - outside) / (1 - 2 * f);
  return width > 0 && Number.isFinite(width) ? width : null;
}

/** The midpoint of each side of band k's inner line, where its drag handles sit. */
export function bandHandles(
  m: Homography,
  cols: number,
  rows: number,
  bands: readonly BorderBand[],
  k: number,
): Record<BandSide, Point> {
  // The rectified midpoint (0.5), not the pixel midpoint, so a handle stays
  // on the middle of its side under perspective.
  const r = bandRange(cols, rows, bands, k);
  return {
    top: applyHomography(m, 0.5, r.v0),
    right: applyHomography(m, r.u1, 0.5),
    bottom: applyHomography(m, 0.5, r.v1),
    left: applyHomography(m, r.u0, 0.5),
  };
}

/** Band k's width from a handle dragged to point, read in the rectified plane. */
export function widthFromHandle(
  m: Homography,
  side: BandSide,
  point: Point,
  cols: number,
  rows: number,
  bands: readonly BorderBand[],
  k: number,
): number | null {
  const { u, v } = invertHomography(m)(point);
  const depth = side === "top" ? v : side === "bottom" ? 1 - v : side === "left" ? u : 1 - u;
  const squares = side === "top" || side === "bottom" ? rows : cols;
  return widthFromDepth(depth, squares, bands, k);
}

/** Four decimal places: 0.0001 of a 4 in square is far below a pin's error. */
export function roundWidth(width: number): number {
  return Math.round(width * 1e4) / 1e4;
}

export function roundQuarterInch(inches: number): number {
  return Math.round(inches * 4) / 4;
}

/** A typed width in inches, rounded to 1/4 in, in squares of squareEighths eighths. */
export function inchesToSquares(inches: number, squareEighths: number): number {
  return roundWidth((roundQuarterInch(inches) * 8) / squareEighths);
}

export function squaresToInches(width: number, squareEighths: number): number {
  return (width * squareEighths) / 8;
}

/** One stepper press; a step that would reach zero leaves the width as it is. */
export function stepBand(width: number, direction: 1 | -1): number {
  const next = roundWidth(width + direction * BAND_STEP_SQUARES);
  return next > 0 ? next : width;
}
