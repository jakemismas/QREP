/**
 * Confirm-screen geometry (C3a, issue #149): engine-free and pure, so the
 * product confirm screen (C3b) and the dev annotate page share one tested
 * copy.
 *
 * Pins live in source-image pixels. A pointer maps through the image
 * element's own rect, never a padded box around it (ux-06: fractions of the
 * padded .pf-corner-box put the read 5 to 7 percent inside each corner), and
 * clamps to the image (vision-15).
 *
 * The overlay goes through the projective map from the unit square to the
 * pinned quad: (0, 0) top left, (1, 0) top right, (1, 1) bottom right,
 * (0, 1) bottom left. In that rectified plane every square has the same
 * size, so grid lines, band depths and a measured square are all computed
 * there and mapped back, which keeps them right under perspective.
 */
import type { Point } from "../engine/contract";

export interface Rect {
  left: number;
  top: number;
  width: number;
  height: number;
}

export interface Size {
  width: number;
  height: number;
}

/** Corners top left, top right, bottom right, bottom left. */
export type Quad = [Point, Point, Point, Point];

/** x = (a u + b v + c) / w and y = (d u + e v + f) / w, with w = g u + h v + 1. */
export interface Homography {
  a: number;
  b: number;
  c: number;
  d: number;
  e: number;
  f: number;
  g: number;
  h: number;
}

export interface UV {
  u: number;
  v: number;
}

const clamp01 = (value: number) => Math.min(1, Math.max(0, value));

/** Where a pointer sits across the image rect, from 0 to 1 on each axis, clamped. */
export function displayToFraction(display: Point, rect: Rect): Point {
  return {
    x: clamp01((display.x - rect.left) / rect.width),
    y: clamp01((display.y - rect.top) / rect.height),
  };
}

/** A pointer in client pixels to a clamped point in source-image pixels. */
export function displayToSource(display: Point, rect: Rect, source: Size): Point {
  const fraction = displayToFraction(display, rect);
  return { x: fraction.x * source.width, y: fraction.y * source.height };
}

export function sourceToDisplay(point: Point, rect: Rect, source: Size): Point {
  return {
    x: rect.left + (point.x / source.width) * rect.width,
    y: rect.top + (point.y / source.height) * rect.height,
  };
}

/**
 * Rounds to whole source pixels inside the image. Why whole pixels: one
 * display pixel spans several source pixels on a phone, so finer values are
 * noise, and whole values make an arrow-key nudge exactly one pixel.
 */
export function snapToPixel(point: Point, source: Size): Point {
  return {
    x: Math.min(source.width, Math.max(0, Math.round(point.x))),
    y: Math.min(source.height, Math.max(0, Math.round(point.y))),
  };
}

/** The projective map from the unit square onto quad (Heckbert, 1989, section 2.2.3). */
export function squareToQuad(quad: Quad): Homography {
  const [p0, p1, p2, p3] = quad;
  const sx = p0.x - p1.x + p2.x - p3.x;
  const sy = p0.y - p1.y + p2.y - p3.y;
  if (sx === 0 && sy === 0) {
    // A parallelogram: the map is affine.
    return {
      a: p1.x - p0.x,
      b: p3.x - p0.x,
      c: p0.x,
      d: p1.y - p0.y,
      e: p3.y - p0.y,
      f: p0.y,
      g: 0,
      h: 0,
    };
  }
  const dx1 = p1.x - p2.x;
  const dx2 = p3.x - p2.x;
  const dy1 = p1.y - p2.y;
  const dy2 = p3.y - p2.y;
  const det = dx1 * dy2 - dx2 * dy1;
  const g = (sx * dy2 - dx2 * sy) / det;
  const h = (dx1 * sy - sx * dy1) / det;
  return {
    a: p1.x - p0.x + g * p1.x,
    b: p3.x - p0.x + h * p3.x,
    c: p0.x,
    d: p1.y - p0.y + g * p1.y,
    e: p3.y - p0.y + h * p3.y,
    f: p0.y,
    g,
    h,
  };
}

export function applyHomography(m: Homography, u: number, v: number): Point {
  const w = m.g * u + m.h * v + 1;
  return { x: (m.a * u + m.b * v + m.c) / w, y: (m.d * u + m.e * v + m.f) / w };
}

/** The inverse map, from image pixels back to the unit square, by the adjugate. */
export function invertHomography(m: Homography): (point: Point) => UV {
  // Matrix [[a, b, c], [d, e, f], [g, h, 1]]; its adjugate is the inverse up
  // to scale, and the scale cancels in the division below.
  const A = m.e - m.f * m.h;
  const B = m.c * m.h - m.b;
  const C = m.b * m.f - m.c * m.e;
  const D = m.f * m.g - m.d;
  const E = m.a - m.c * m.g;
  const F = m.c * m.d - m.a * m.f;
  const G = m.d * m.h - m.e * m.g;
  const H = m.b * m.g - m.a * m.h;
  const I = m.a * m.e - m.b * m.d;
  return (point) => {
    const w = G * point.x + H * point.y + I;
    return { u: (A * point.x + B * point.y + C) / w, v: (D * point.x + E * point.y + F) / w };
  };
}

export interface UVRange {
  u0: number;
  u1: number;
  v0: number;
  v1: number;
}

export type Segment = [Point, Point];

export interface GridLines {
  /** cols + 1 lines, left edge first. */
  vertical: Segment[];
  /** rows + 1 lines, top edge first. */
  horizontal: Segment[];
}

/** Square lines across range of the rectified plane, cols by rows squares. */
export function gridLines(
  m: Homography,
  cols: number,
  rows: number,
  range: UVRange = { u0: 0, u1: 1, v0: 0, v1: 1 },
): GridLines {
  const { u0, u1, v0, v1 } = range;
  const vertical: Segment[] = [];
  for (let i = 0; i <= cols; i++) {
    const u = u0 + ((u1 - u0) * i) / cols;
    vertical.push([applyHomography(m, u, v0), applyHomography(m, u, v1)]);
  }
  const horizontal: Segment[] = [];
  for (let j = 0; j <= rows; j++) {
    const v = v0 + ((v1 - v0) * j) / rows;
    horizontal.push([applyHomography(m, u0, v), applyHomography(m, u1, v)]);
  }
  return { vertical, horizontal };
}

/** The quad a sub-range of the rectified plane covers. */
export function rangeQuad(m: Homography, range: UVRange): Quad {
  return [
    applyHomography(m, range.u0, range.v0),
    applyHomography(m, range.u1, range.v0),
    applyHomography(m, range.u1, range.v1),
    applyHomography(m, range.u0, range.v1),
  ];
}
