/**
 * The flagged squares on Your pattern (C2a, issue #96), framework-free so
 * vitest covers them without a DOM. They come from the photo read alone: its
 * own count (PhotoResult.uncertainCount) and its own model, whose cell
 * confidences QuiltCanvas outlines. The editor's model never feeds them, and
 * the sample has no read, so it has none.
 */
import type { QuiltModel } from "../model/types";
import type { PatternSource } from "../state/pattern";
import type { PhotoResult } from "../state/photo";

export interface ReadFlags {
  /** Squares the read flagged to double-check; 0 when there is no read. */
  count: number;
  /** The read's model, or null when there is no read to show flags for. */
  model: QuiltModel | null;
}

const NO_FLAGS: ReadFlags = { count: 0, model: null };

export function readFlags(
  source: PatternSource,
  read: Pick<PhotoResult, "uncertainCount" | "modelJson"> | null,
): ReadFlags {
  if (source !== "photo" || read === null) return NO_FLAGS;
  try {
    return { count: read.uncertainCount, model: JSON.parse(read.modelJson) as QuiltModel };
  } catch {
    return NO_FLAGS;
  }
}
