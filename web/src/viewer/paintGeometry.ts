/**
 * Pure pointer->square mapping and supercover line walk for the paint tool.
 * No DOM, no React: the canvas hands in a plain view transform (the same
 * numbers it publishes as data-* attributes), so this is unit-testable alone.
 */

export interface PaintCell {
  row: number;
  col: number;
}

/** The canvas's live transform, mirrored 1:1 by its data-* attributes. */
export interface ViewTransform {
  /** CSS px per eighth at the current zoom (data-view-scale). */
  scale: number;
  /** Canvas-relative px of the quilt's top-left corner (data-view-origin-*). */
  originX: number;
  originY: number;
  /** Eighths per square (data-cell-size). */
  cell: number;
  /** Sum of border band widths in eighths (data-border-total). */
  borderTotal: number;
}

/**
 * Map a canvas-relative pointer point (CSS px from the canvas top-left) to the
 * center-grid square under it. The result is the raw floored square and may
 * fall outside [0,rows) x [0,cols); callers clamp or drop out-of-range squares.
 */
export function pointToCell(px: number, py: number, view: ViewTransform): PaintCell {
  const eighthX = (px - view.originX) / view.scale - view.borderTotal;
  const eighthY = (py - view.originY) / view.scale - view.borderTotal;
  return {
    row: Math.floor(eighthY / view.cell),
    col: Math.floor(eighthX / view.cell),
  };
}

export function clampCell(cell: PaintCell, rows: number, cols: number): PaintCell {
  const clamp = (v: number, hi: number): number => (v < 0 ? 0 : v >= hi ? hi - 1 : v);
  return { row: clamp(cell.row, rows), col: clamp(cell.col, cols) };
}

function sign(n: number): number {
  return n > 0 ? 1 : n < 0 ? -1 : 0;
}

/**
 * Supercover line between two squares, inclusive, in walk order from `a` to
 * `b`. Consecutive squares always share an edge (4-connected), so a fast drag
 * sampled at only a few points still paints an unbroken run. At an exact
 * corner crossing the walk emits both edge-adjacent squares (a staircase)
 * rather than a diagonal jump that could leak paint between two squares.
 */
export function supercoverLine(a: PaintCell, b: PaintCell): PaintCell[] {
  const x0 = a.col;
  const y0 = a.row;
  const dx = b.col - x0;
  const dy = b.row - y0;
  const nx = Math.abs(dx);
  const ny = Math.abs(dy);
  const sx = sign(dx);
  const sy = sign(dy);
  let x = x0;
  let y = y0;
  const out: PaintCell[] = [{ row: y, col: x }];
  let ix = 0;
  let iy = 0;
  while (ix < nx || iy < ny) {
    // Compare the next vertical crossing (ix+0.5)/nx against the next
    // horizontal crossing (iy+0.5)/ny, cross-multiplied to stay in integers.
    const cx = (1 + 2 * ix) * ny;
    const cy = (1 + 2 * iy) * nx;
    if (cx === cy) {
      // Exact corner: step through both edge-neighbours in turn.
      x += sx;
      ix += 1;
      out.push({ row: y, col: x });
      y += sy;
      iy += 1;
      out.push({ row: y, col: x });
    } else if (cx < cy) {
      x += sx;
      ix += 1;
      out.push({ row: y, col: x });
    } else {
      y += sy;
      iy += 1;
      out.push({ row: y, col: x });
    }
  }
  return out;
}

/**
 * The interior edge shared by two 4-adjacent squares, or null when `a` and `b`
 * are the same square or are not edge-adjacent. Edge ids match seams.ts:
 * `${r},${c}:v` joins (r,c)-(r,c+1); `${r},${c}:h` joins (r,c)-(r+1,c). The id
 * always names the lower-index square, so the order of `a`/`b` does not matter.
 */
export function edgeBetween(a: PaintCell, b: PaintCell): string | null {
  const dr = b.row - a.row;
  const dc = b.col - a.col;
  if (dr === 0 && (dc === 1 || dc === -1)) {
    return `${a.row},${Math.min(a.col, b.col)}:v`;
  }
  if (dc === 0 && (dr === 1 || dr === -1)) {
    return `${Math.min(a.row, b.row)},${a.col}:h`;
  }
  return null;
}

/**
 * The distinct interior edges a 4-connected walk of squares crosses, in
 * first-seen order. Each consecutive pair contributes the edge between them;
 * a pair that is not edge-adjacent contributes nothing, and a re-crossed edge
 * is emitted once. Fed the supercover walk between two pointer samples, this is
 * exactly the seam boundaries the pointer path swept.
 */
export function pathEdges(cells: PaintCell[]): string[] {
  const seen = new Set<string>();
  const out: string[] = [];
  for (let i = 1; i < cells.length; i++) {
    const edge = edgeBetween(cells[i - 1], cells[i]);
    if (edge && !seen.has(edge)) {
      seen.add(edge);
      out.push(edge);
    }
  }
  return out;
}

/** De-duplicate squares, keeping first-seen paint order. */
export function dedupeCells(cells: PaintCell[]): PaintCell[] {
  const seen = new Set<string>();
  const out: PaintCell[] = [];
  for (const c of cells) {
    const key = `${c.row},${c.col}`;
    if (seen.has(key)) continue;
    seen.add(key);
    out.push(c);
  }
  return out;
}
