/**
 * Paint geometry unit tests (S3, issue #43). Every expected list is computed
 * by hand from the algorithm definition, never copied from observed output.
 *
 * Supercover contract: consecutive squares are edge-adjacent (4-connected);
 * a straight run is exactly the run; an exact-corner crossing emits both
 * edge-neighbours (a staircase), stepping the x-neighbour first.
 */
import { describe, expect, it } from "vitest";
import {
  clampCell,
  dedupeCells,
  pointToCell,
  supercoverLine,
  type PaintCell,
  type ViewTransform,
} from "./paintGeometry";

// scale 2 px/eighth, quilt top-left at (10,20), 10-eighth squares, 5-eighth
// border. Square (r,c) centre in canvas px:
//   x = 10 + (5 + (c + 0.5)*10) * 2,  y = 20 + (5 + (r + 0.5)*10) * 2
const VIEW: ViewTransform = { scale: 2, originX: 10, originY: 20, cell: 10, borderTotal: 5 };

describe("pointToCell", () => {
  it("maps the centre of square (0,0)", () => {
    // qx = 5 + 0.5*10 = 10 eighths -> px = 10 + 20 = 30; qy likewise -> py = 40.
    expect(pointToCell(30, 40, VIEW)).toEqual({ row: 0, col: 0 });
  });

  it("maps the centre of square (2,3)", () => {
    // qx = 5 + 3.5*10 = 40 -> px = 10 + 80 = 90; qy = 5 + 2.5*10 = 30 -> py = 80.
    expect(pointToCell(90, 80, VIEW)).toEqual({ row: 2, col: 3 });
  });

  it("returns a negative square left/above the grid", () => {
    // px 0: eighthX = (0-10)/2 - 5 = -10 -> col floor(-1) = -1.
    // py 0: eighthY = (0-20)/2 - 5 = -15 -> row floor(-1.5) = -2.
    expect(pointToCell(0, 0, VIEW)).toEqual({ row: -2, col: -1 });
  });
});

describe("clampCell", () => {
  it("clamps below and above the bounds", () => {
    expect(clampCell({ row: -1, col: -3 }, 5, 5)).toEqual({ row: 0, col: 0 });
    expect(clampCell({ row: 9, col: 12 }, 5, 5)).toEqual({ row: 4, col: 4 });
    expect(clampCell({ row: 2, col: 3 }, 5, 5)).toEqual({ row: 2, col: 3 });
  });
});

describe("supercoverLine", () => {
  it("a single square is its own one-square walk", () => {
    expect(supercoverLine({ row: 4, col: 4 }, { row: 4, col: 4 })).toEqual([{ row: 4, col: 4 }]);
  });

  it("a horizontal run covers every square, endpoints inclusive", () => {
    // (2,0) -> (2,9): row fixed, cols 0..9 in order.
    const expected: PaintCell[] = Array.from({ length: 10 }, (_, c) => ({ row: 2, col: c }));
    expect(supercoverLine({ row: 2, col: 0 }, { row: 2, col: 9 })).toEqual(expected);
  });

  it("a vertical run covers every square", () => {
    // (0,3) -> (4,3): col fixed, rows 0..4.
    const expected: PaintCell[] = Array.from({ length: 5 }, (_, r) => ({ row: r, col: 3 }));
    expect(supercoverLine({ row: 0, col: 3 }, { row: 4, col: 3 })).toEqual(expected);
  });

  it("walks a horizontal run in reverse when b is left of a", () => {
    // (2,3) -> (2,0): cols 3,2,1,0.
    expect(supercoverLine({ row: 2, col: 3 }, { row: 2, col: 0 })).toEqual([
      { row: 2, col: 3 },
      { row: 2, col: 2 },
      { row: 2, col: 1 },
      { row: 2, col: 0 },
    ]);
  });

  it("a pure diagonal (0,0)->(2,2) is an edge-connected staircase", () => {
    // nx=ny=2: each step is an exact corner (cx==cy), stepping col first then
    // row. Step 1: col->1 gives (0,1), row->1 gives (1,1). Step 2: col->2
    // gives (1,2), row->2 gives (2,2). Includes (0,0),(1,1),(2,2); connected.
    expect(supercoverLine({ row: 0, col: 0 }, { row: 2, col: 2 })).toEqual([
      { row: 0, col: 0 },
      { row: 0, col: 1 },
      { row: 1, col: 1 },
      { row: 1, col: 2 },
      { row: 2, col: 2 },
    ]);
  });

  it("every step in the staircase is edge-adjacent", () => {
    const walk = supercoverLine({ row: 0, col: 0 }, { row: 2, col: 2 });
    for (let i = 1; i < walk.length; i++) {
      const d = Math.abs(walk[i].row - walk[i - 1].row) + Math.abs(walk[i].col - walk[i - 1].col);
      expect(d).toBe(1);
    }
  });

  it("a shallow diagonal (0,0)->(1,3) crosses columns with a single row jump", () => {
    // nx=3, ny=1. Crossings (ix+0.5)/3 vs (iy+0.5)/1:
    //  step: cx=(1+2ix)*1 vs cy=(1+2iy)*3.
    //  ix0,iy0: 1 vs 3 -> col-> (0,1)
    //  ix1,iy0: 3 vs 3 -> corner -> col->(0,2), row->(1,2)
    //  ix2,iy1: 5 vs 9 -> col->(1,3)
    expect(supercoverLine({ row: 0, col: 0 }, { row: 1, col: 3 })).toEqual([
      { row: 0, col: 0 },
      { row: 0, col: 1 },
      { row: 0, col: 2 },
      { row: 1, col: 2 },
      { row: 1, col: 3 },
    ]);
  });
});

describe("dedupeCells", () => {
  it("keeps first-seen paint order and drops repeats", () => {
    expect(
      dedupeCells([
        { row: 0, col: 0 },
        { row: 0, col: 1 },
        { row: 0, col: 0 },
        { row: 2, col: 5 },
        { row: 0, col: 1 },
      ]),
    ).toEqual([
      { row: 0, col: 0 },
      { row: 0, col: 1 },
      { row: 2, col: 5 },
    ]);
  });
});
