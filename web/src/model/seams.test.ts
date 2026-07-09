/**
 * Seam preview core (S5, issue #45; PARITY item 2). Pure logic, no engine:
 * a preview layer whose overrides live in the wrapper's ui.seamFix and
 * never change exports or plans.
 *
 * Edge ids: `${r},${c}:v` joins (r,c)-(r,c+1); `${r},${c}:h` joins
 * (r,c)-(r+1,c). A merge is only ever valid between same-fabric neighbors.
 *
 * All expectations are hand-derived on this 3x3 grid (derivations in
 * comments; 12 interior edges total = 6 vertical + 6 horizontal):
 *
 *      a a b
 *      a b b
 *      a a a
 */
import { describe, expect, it } from "vitest";
import {
  defaultMerges,
  effectiveMerges,
  pieceEstimate,
  type SeamFix,
} from "./seams";

const CELLS = [
  ["a", "a", "b"],
  ["a", "b", "b"],
  ["a", "a", "a"],
];

describe("strategy default merges", () => {
  it("historical: pure grid, no merges, 9 pieces, 12 seams", () => {
    const merges = defaultMerges(CELLS, "historical");
    expect(merges.size).toBe(0);
    const estimate = pieceEstimate(CELLS, merges);
    expect(estimate.pieces).toBe(9);
    expect(estimate.seams).toBe(12);
  });

  it("strip: row runs merge horizontally-adjacent same-fabric cells", () => {
    // Row 0: a-a merges (0,0:v); a-b does not. Row 1: b-b merges (1,1:v).
    // Row 2: a-a, a-a merge (2,0:v),(2,1:v). Pieces: [aa][b] / [a][bb] /
    // [aaa] = 5; seams = 12 interior - 4 merged = 8.
    const merges = defaultMerges(CELLS, "strip");
    expect(merges).toEqual(new Set(["0,0:v", "1,1:v", "2,0:v", "2,1:v"]));
    const estimate = pieceEstimate(CELLS, merges);
    expect(estimate.pieces).toBe(5);
    expect(estimate.seams).toBe(8);
  });

  it("modern: greedy top-left rectangles", () => {
    // Greedy rule (fixed): at the first unclaimed cell in row-major order,
    // take the maximal same-fabric horizontal run of unclaimed cells, then
    // extend the full run downward while every covered cell matches and is
    // unclaimed. Hand walk: (0,0) run cols 0-1, row 1 breaks (b) -> 1x2.
    // (0,2) 'b' run col 2, extends to row 1 -> 2x1. (1,0) 'a' run col 0,
    // extends to row 2 -> 2x1. (1,1) 'b' 1x1. (2,1) run cols 1-2 -> 1x2.
    // Pieces 5; merges: (0,0:v),(0,2:h),(1,0:h),(2,1:v) = 4; seams 8.
    const merges = defaultMerges(CELLS, "modern");
    expect(merges).toEqual(new Set(["0,0:v", "0,2:h", "1,0:h", "2,1:v"]));
    const estimate = pieceEstimate(CELLS, merges);
    expect(estimate.pieces).toBe(5);
    expect(estimate.seams).toBe(8);
  });
});

describe("seamFix overrides", () => {
  it("split re-adds a seam on top of the strategy default", () => {
    // Strip defaults minus (0,0:v): row 0 becomes [a][a][b] -> 6 pieces,
    // seams 12 - 3 = 9.
    const fix: SeamFix = { "0,0:v": "split" };
    const merges = effectiveMerges(CELLS, "strip", fix);
    expect(merges.has("0,0:v")).toBe(false);
    const estimate = pieceEstimate(CELLS, merges);
    expect(estimate.pieces).toBe(6);
    expect(estimate.seams).toBe(9);
  });

  it("merge joins same-fabric neighbors on top of historical", () => {
    // Historical + merge (0,0:h): (0,0)-(1,0) both 'a' -> 8 pieces, 11 seams.
    const fix: SeamFix = { "0,0:h": "merge" };
    const merges = effectiveMerges(CELLS, "historical", fix);
    expect(merges).toEqual(new Set(["0,0:h"]));
    const estimate = pieceEstimate(CELLS, merges);
    expect(estimate.pieces).toBe(8);
    expect(estimate.seams).toBe(11);
  });

  it("a merge between different fabrics is ignored", () => {
    // (0,1:h) joins (0,1)='a' and (1,1)='b': invalid, dropped.
    const fix: SeamFix = { "0,1:h": "merge" };
    const merges = effectiveMerges(CELLS, "historical", fix);
    expect(merges.size).toBe(0);
  });

  it("an unmerged edge inside one piece is not a seam", () => {
    // Ring grid: 8 'a' cells around a center 'b'. Merge 7 of the 8 ring
    // edges (all but (2,0:v)): the ring is ONE piece, and the unmerged
    // (2,0:v) sits between two cells of the same piece - nothing is sewn
    // there. Seams = the 4 edges around the center only. Pieces = 2.
    const ring = [
      ["a", "a", "a"],
      ["a", "b", "a"],
      ["a", "a", "a"],
    ];
    const fix: SeamFix = {
      "0,0:v": "merge",
      "0,1:v": "merge",
      "0,0:h": "merge",
      "0,2:h": "merge",
      "1,0:h": "merge",
      "1,2:h": "merge",
      "2,1:v": "merge",
    };
    const merges = effectiveMerges(ring, "historical", fix);
    expect(merges.size).toBe(7);
    const estimate = pieceEstimate(ring, merges);
    expect(estimate.pieces).toBe(2);
    expect(estimate.seams).toBe(4);
  });

  it("estimates count seams only between distinct pieces", () => {
    // Merge all three row-2 edges' worth: (2,0:v),(2,1:v) via strip default
    // then ALSO merge (1,0:h) joining row1 col0 to the row-2 run: pieces
    // [aa][b]/[a+aaa piece][bb] -> derive: strip merges 4, plus (1,0:h)
    // valid ('a','a') = 5 merges; components: {(0,0),(0,1)}, {(0,2)},
    // {(1,0),(2,0),(2,1),(2,2)}, {(1,1),(1,2)} = 4 pieces; seams = 12-5 = 7.
    const fix: SeamFix = { "1,0:h": "merge" };
    const merges = effectiveMerges(CELLS, "strip", fix);
    expect(merges.size).toBe(5);
    const estimate = pieceEstimate(CELLS, merges);
    expect(estimate.pieces).toBe(4);
    expect(estimate.seams).toBe(7);
  });
});
