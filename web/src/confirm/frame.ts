/**
 * The two frames of plan section 2.1 (C3a, issue #149): the four corners of
 * the pieced field, or the outer quilt edge with border bands set inward,
 * because field corners are often hidden ([CP] 3.4; Critique: CR-cv-08).
 * Both leave here in E1b's request shape (web/src/engine/contract.ts Frame).
 */
import type { BorderBand, Corners, Frame, Point } from "../engine/contract";
import type { Quad, Size } from "./geometry";

export type FrameMode = Frame["kind"];

export const CORNER_NAMES = ["top_left", "top_right", "bottom_right", "bottom_left"] as const;
export type CornerName = (typeof CORNER_NAMES)[number];

export const CORNER_LABELS: Record<CornerName, string> = {
  top_left: "top left",
  top_right: "top right",
  bottom_right: "bottom right",
  bottom_left: "bottom left",
};

export function cornersToQuad(c: Corners): Quad {
  return [c.top_left, c.top_right, c.bottom_right, c.bottom_left];
}

export function quadToCorners(q: Quad): Corners {
  return { top_left: q[0], top_right: q[1], bottom_right: q[2], bottom_left: q[3] };
}

/** The read request's frame; a field frame carries no bands. */
export function toRequestFrame(mode: FrameMode, corners: Corners, bands: readonly BorderBand[]): Frame {
  if (mode === "field") return { kind: "field", corners };
  return { kind: "outer_edge", corners, bands: bands.map((band) => ({ width_squares: band.width_squares })) };
}

/**
 * Pins start inset from the image edges, never on a guessed quilt: QREP
 * never presents a full-frame fallback as a detection (plan section 2.1;
 * approaches-37).
 */
export function neutralInset(size: Size, inset = 0.15): Corners {
  const left = Math.round(size.width * inset);
  const right = Math.round(size.width * (1 - inset));
  const top = Math.round(size.height * inset);
  const bottom = Math.round(size.height * (1 - inset));
  return {
    top_left: { x: left, y: top },
    top_right: { x: right, y: top },
    bottom_right: { x: right, y: bottom },
    bottom_left: { x: left, y: bottom },
  };
}

// z of (b - a) x (c - a); with y pointing down, positive turns clockwise.
function cross(a: Point, b: Point, c: Point): number {
  return (b.x - a.x) * (c.y - a.y) - (b.y - a.y) * (c.x - a.x);
}

/**
 * Why corners cannot be saved, or null. The same checks as
 * scripts/eval/qrep_eval/annotation.py _check_quad, so a saved file loads
 * there: each corner on its own side, then a convex quad traced clockwise.
 */
export function quadProblem(c: Corners, what = "The frame"): string | null {
  const { top_left: tl, top_right: tr, bottom_right: br, bottom_left: bl } = c;
  if (!(tl.x < tr.x && bl.x < br.x && tl.y < bl.y && tr.y < br.y)) {
    return `${what} corners are out of order: pin the top left, top right, bottom right and bottom left corners.`;
  }
  const quad = cornersToQuad(c);
  for (let i = 0; i < 4; i++) {
    if (cross(quad[i], quad[(i + 1) % 4], quad[(i + 2) % 4]) <= 0) {
      return `${what} is crossed, concave or flat: move a pin so the four corners make a box.`;
    }
  }
  return null;
}

/** The field lies inside the outer edge, or on it when there is no border. */
export function fieldInsideProblem(outer: Corners, field: Corners): string | null {
  const edge = cornersToQuad(outer);
  for (const corner of cornersToQuad(field)) {
    for (let i = 0; i < 4; i++) {
      if (cross(edge[i], edge[(i + 1) % 4], corner) < 0) {
        return "A field corner lies outside the outer edge: move it inside.";
      }
    }
  }
  return null;
}
