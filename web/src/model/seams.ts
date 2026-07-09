/**
 * Seam preview core (S5, issue #45; PARITY item 2). A PREVIEW layer: the
 * strategy implies a default seam pattern, ui.seamFix overrides individual
 * edges, and the piece/seam numbers derived here are clearly-labeled
 * ESTIMATES. Exports and plans always come from the engine and are never
 * affected by this module.
 *
 * Edge ids: `${r},${c}:v` joins (r,c)-(r,c+1); `${r},${c}:h` joins
 * (r,c)-(r+1,c). Merges are only ever valid between same-fabric neighbors.
 */

export type SeamStrategy = "historical" | "strip" | "modern";
export type SeamFix = Record<string, "merge" | "split">;

function neighbors(edge: string): { ar: number; ac: number; br: number; bc: number } {
  const [pos, kind] = edge.split(":");
  const [r, c] = pos.split(",").map(Number);
  return kind === "v"
    ? { ar: r, ac: c, br: r, bc: c + 1 }
    : { ar: r, ac: c, br: r + 1, bc: c };
}

function sameFabric(cells: string[][], edge: string): boolean {
  const { ar, ac, br, bc } = neighbors(edge);
  if (br >= cells.length || bc >= cells[0].length) return false;
  return cells[ar][ac] === cells[br][bc];
}

/** Strategy-implied merge set (PARITY item 2). */
export function defaultMerges(cells: string[][], strategy: SeamStrategy): Set<string> {
  const merges = new Set<string>();
  const rows = cells.length;
  const cols = cells[0].length;
  if (strategy === "strip") {
    // Row runs: horizontally-adjacent same-fabric cells merge.
    for (let r = 0; r < rows; r++) {
      for (let c = 0; c < cols - 1; c++) {
        if (cells[r][c] === cells[r][c + 1]) merges.add(`${r},${c}:v`);
      }
    }
  } else if (strategy === "modern") {
    // Greedy top-left rectangles: at the first unclaimed cell in row-major
    // order, take the maximal same-fabric horizontal run of unclaimed
    // cells, then extend the run downward while every covered cell matches
    // and is unclaimed. (An estimate of the engine's rectangle merge.)
    const claimed = cells.map((row) => row.map(() => false));
    for (let r = 0; r < rows; r++) {
      for (let c = 0; c < cols; c++) {
        if (claimed[r][c]) continue;
        const fabric = cells[r][c];
        let endCol = c;
        while (endCol + 1 < cols && !claimed[r][endCol + 1] && cells[r][endCol + 1] === fabric) {
          endCol++;
        }
        let endRow = r;
        const fits = (row: number) => {
          for (let cc = c; cc <= endCol; cc++) {
            if (claimed[row][cc] || cells[row][cc] !== fabric) return false;
          }
          return true;
        };
        while (endRow + 1 < rows && fits(endRow + 1)) endRow++;
        for (let rr = r; rr <= endRow; rr++) {
          for (let cc = c; cc <= endCol; cc++) {
            claimed[rr][cc] = true;
            if (cc < endCol) merges.add(`${rr},${cc}:v`);
            if (rr < endRow) merges.add(`${rr},${cc}:h`);
          }
        }
      }
    }
  }
  // historical: pure grid, no merges.
  return merges;
}

/** Defaults with ui.seamFix applied; invalid merges are dropped. */
export function effectiveMerges(
  cells: string[][],
  strategy: SeamStrategy,
  fix: SeamFix,
): Set<string> {
  const merges = defaultMerges(cells, strategy);
  for (const [edge, action] of Object.entries(fix)) {
    if (action === "split") {
      merges.delete(edge);
    } else if (sameFabric(cells, edge)) {
      merges.add(edge);
    }
  }
  return merges;
}

/**
 * Estimated piece and seam counts: pieces = connected components under the
 * merge set; seams = unmerged interior edges joining DIFFERENT pieces (an
 * unmerged edge inside one piece is not sewn).
 */
export function pieceEstimate(
  cells: string[][],
  merges: Set<string>,
): { pieces: number; seams: number } {
  const rows = cells.length;
  const cols = cells[0].length;
  const component = new Array<number>(rows * cols).fill(-1);
  let pieces = 0;
  for (let start = 0; start < rows * cols; start++) {
    if (component[start] !== -1) continue;
    const stack = [start];
    component[start] = pieces;
    while (stack.length > 0) {
      const index = stack.pop()!;
      const r = Math.floor(index / cols);
      const c = index % cols;
      const linked: number[] = [];
      if (merges.has(`${r},${c}:v`)) linked.push(index + 1);
      if (c > 0 && merges.has(`${r},${c - 1}:v`)) linked.push(index - 1);
      if (merges.has(`${r},${c}:h`)) linked.push(index + cols);
      if (r > 0 && merges.has(`${r - 1},${c}:h`)) linked.push(index - cols);
      for (const next of linked) {
        if (component[next] === -1) {
          component[next] = pieces;
          stack.push(next);
        }
      }
    }
    pieces++;
  }
  let seams = 0;
  for (let r = 0; r < rows; r++) {
    for (let c = 0; c < cols; c++) {
      const index = r * cols + c;
      if (c < cols - 1 && !merges.has(`${r},${c}:v`) && component[index] !== component[index + 1]) {
        seams++;
      }
      if (r < rows - 1 && !merges.has(`${r},${c}:h`) && component[index] !== component[index + cols]) {
        seams++;
      }
    }
  }
  return { pieces, seams };
}
