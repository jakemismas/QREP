/**
 * The flagged squares on Your pattern (C2a, issue #96) come from the photo
 * read alone: its own model's cell confidences, and the count of those below
 * the mark. The sample has no read, so it has none.
 */
import { describe, expect, it } from "vitest";
import { readFlags } from "./flags";

// A hand-made read: six squares in two rows. PARITY item 6 flags a square
// below 0.9, so the flagged ones are 0.5 and 0.89; 0.9 itself is not below
// 0.9, and 1, 0.95 and 1 are above it: 2 squares.
const CONFIDENCE = [
  [1, 0.5, 0.9],
  [0.89, 1, 0.95],
];
const READ = {
  modelJson: JSON.stringify({
    metadata: { name: "Read quilt" },
    center: { rows: 2, cols: 3, cell_confidence: CONFIDENCE },
  }),
};

describe("readFlags", () => {
  it("counts the read's own squares below 0.9 and takes its cell confidences", () => {
    const flags = readFlags("photo", READ);
    expect(flags.count).toBe(2);
    expect(flags.model?.center.cell_confidence).toEqual(CONFIDENCE);
  });

  it("counts none for a read whose model carries no confidences", () => {
    // Hand: no cell_confidence, so no square is below the mark.
    const read = { modelJson: JSON.stringify({ center: { rows: 1, cols: 1 } }) };
    const flags = readFlags("photo", read);
    expect(flags.count).toBe(0);
    expect(flags.model).not.toBeNull();
  });

  it("gives the sample no flags, whatever read is left over", () => {
    expect(readFlags("sample", READ)).toEqual({ count: 0, model: null });
    expect(readFlags("sample", null)).toEqual({ count: 0, model: null });
  });

  it("gives a photo source with no readable read no flags", () => {
    expect(readFlags("photo", null)).toEqual({ count: 0, model: null });
    expect(readFlags("photo", { modelJson: "{not json" })).toEqual({ count: 0, model: null });
  });
});
