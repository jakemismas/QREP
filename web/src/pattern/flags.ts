/**
 * The flagged squares on Your pattern (C2a, issue #96), framework-free so
 * vitest covers them without a DOM. They come from the photo read alone: its
 * own model, whose cell confidences QuiltCanvas outlines, and the count of
 * those same confidences below the mark, so the count always matches the
 * outlines. The editor's model never feeds them, and the sample has no read,
 * so it has none.
 */
import type { QuiltModel } from "../model/types";
import type { PatternSource } from "../state/pattern";
import type { PhotoResult } from "../state/photo";

// PARITY item 6: a square below 0.9 confidence is flagged, the mark
// QuiltCanvas outlines at (UNCERTAIN_THRESHOLD there and in state/photo.tsx).
const FLAG_BELOW = 0.9;

export interface ReadFlags {
  /** Squares the read flagged to double-check; 0 when there is no read. */
  count: number;
  /** The read's model, or null when there is no read to show flags for. */
  model: QuiltModel | null;
}

const NO_FLAGS: ReadFlags = { count: 0, model: null };

/** Squares below the mark; a missing value is skipped, as QuiltCanvas skips it. */
function countFlagged(confidence: number[][] | null | undefined): number {
  let count = 0;
  for (const row of confidence ?? []) {
    for (const value of row) if (value != null && value < FLAG_BELOW) count += 1;
  }
  return count;
}

export function readFlags(
  source: PatternSource,
  read: Pick<PhotoResult, "modelJson"> | null,
): ReadFlags {
  if (source !== "photo" || read === null) return NO_FLAGS;
  try {
    const model = JSON.parse(read.modelJson) as QuiltModel;
    return { count: countFlagged(model.center?.cell_confidence), model };
  } catch {
    return NO_FLAGS;
  }
}
