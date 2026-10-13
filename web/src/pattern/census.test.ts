/**
 * The census join (C2a, issue #96): letters and names from the engine's
 * pattern summary, swatches from the palette, square counts from the
 * validate census. Every expected value below is an input carried through
 * the join, so the comments name which input each one comes from.
 */
import { describe, expect, it } from "vitest";
import type { FabricLine } from "../engine/contract";
import type { Fabric, ModelSummary } from "../model/types";
import { censusRows } from "./census";

// The fixture's two fabrics (tests/fixtures/double_irish_chain.json), with
// the interim letters equal to the fabric ids (qrep/export/pattern.py).
const LINES: FabricLine[] = [
  { letter: "b", fabric_id: "b", name: "Chain blue", yards: 2.5 },
  { letter: "c", fabric_id: "c", name: "Background cream", yards: 4 },
];

// Palette names differ from the engine's on purpose: the row must carry the
// engine's name, not the palette's.
const PALETTE: Fabric[] = [
  { id: "c", name: "palette cream", color: "#f2e8d5" },
  { id: "b", name: "palette blue", color: "#9db8d9" },
];

function census(counts: Record<string, number>): ModelSummary {
  return {
    name: "Double Irish Chain 75x90",
    rows: 55,
    cols: 45,
    fabric_count: 2,
    fabrics: Object.entries(counts).map(([id, cell_count]) => ({
      id,
      name: id,
      color: "#000000",
      cell_count,
    })),
    finished_width: 600,
    finished_height: 720,
    batting_width: 664,
    batting_height: 784,
    usable_width: 336,
  };
}

describe("censusRows", () => {
  it("joins the engine's letters and names, the palette swatch and the census count", () => {
    // Counts: the design doc's census literals, 1246 blue and 1229 cream.
    expect(censusRows(LINES, PALETTE, census({ b: 1246, c: 1229 }))).toEqual([
      { fabricId: "b", letter: "b", name: "Chain blue", color: "#9db8d9", count: 1246 },
      { fabricId: "c", letter: "c", name: "Background cream", color: "#f2e8d5", count: 1229 },
    ]);
  });

  it("keeps the engine's order and leaves the count empty until the census lands", () => {
    const reversed = [LINES[1], LINES[0]];
    expect(censusRows(reversed, PALETTE, null)).toEqual([
      { fabricId: "c", letter: "c", name: "Background cream", color: "#f2e8d5", count: null },
      { fabricId: "b", letter: "b", name: "Chain blue", color: "#9db8d9", count: null },
    ]);
  });

  it("gives a fabric missing from the palette or the census no swatch and no count", () => {
    const lines: FabricLine[] = [{ letter: "A", fabric_id: "f9", name: "Fabric 9", yards: 1 }];
    expect(censusRows(lines, PALETTE, census({ b: 1246 }))).toEqual([
      { fabricId: "f9", letter: "A", name: "Fabric 9", color: null, count: null },
    ]);
  });
});
