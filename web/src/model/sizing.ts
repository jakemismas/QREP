/**
 * JS preview mirror of qrep/viewer/sizing.py plus the bridge's PARITY-4
 * layer (S4, issue #44). PREVIEW ONLY: every commit adopts the bridge's
 * resize_locked/resize_unlocked result; this module exists so sliders and
 * typing feel immediate. Parity is pinned to the Python unit-test literals
 * in sizing.test.ts - if parity ever breaks, delete this module and
 * debounce the Python call instead (design-doc rule); never fork the math.
 */

export const PRESETS: { name: string; width: number; height: number }[] = [
  { name: "Crib", width: 36 * 8, height: 52 * 8 },
  { name: "Throw", width: 50 * 8, height: 65 * 8 },
  { name: "Twin", width: 70 * 8, height: 90 * 8 },
  { name: "Full", width: 84 * 8, height: 90 * 8 },
  { name: "Queen", width: 90 * 8, height: 108 * 8 },
  { name: "King", width: 110 * 8, height: 108 * 8 },
];

// PARITY-4 clamps, mirroring qrep/bridge.py exactly.
export const CELL_MIN = 6;
export const CELL_MAX = 32;
export const DIM_MIN = 160;
export const DIM_MAX = 1120;
export const BAND_MIN = 2;
export const BAND_MAX = 112;
const QUARTER = 2;

/** Half-up integer division, the exact JS form documented in sizing.py. */
export function roundDiv(a: number, b: number): number {
  return Math.floor((a + Math.floor(b / 2)) / b);
}

function clamp(value: number, low: number, high: number): number {
  return Math.max(low, Math.min(high, value));
}

export interface SizingResult {
  rows: number;
  cols: number;
  cellSize: number;
  achievedWidth: number;
  achievedHeight: number;
}

export function lockedResize(
  rows: number,
  cols: number,
  cellSize: number,
  borderTotal: number,
  target: { targetWidth?: number; targetHeight?: number; targetCell?: number },
): SizingResult {
  let cell: number;
  if (target.targetWidth !== undefined) {
    cell = Math.max(1, roundDiv(Math.max(target.targetWidth - 2 * borderTotal, 0), cols));
  } else if (target.targetHeight !== undefined) {
    cell = Math.max(1, roundDiv(Math.max(target.targetHeight - 2 * borderTotal, 0), rows));
  } else if (target.targetCell !== undefined) {
    cell = Math.max(1, target.targetCell);
  } else {
    cell = cellSize;
  }
  return {
    rows,
    cols,
    cellSize: cell,
    achievedWidth: cols * cell + 2 * borderTotal,
    achievedHeight: rows * cell + 2 * borderTotal,
  };
}

export function unlockedResize(
  rows: number,
  cols: number,
  cellSize: number,
  borderTotal: number,
  block: number,
  target: { targetWidth?: number; targetHeight?: number },
): SizingResult {
  let newCols = cols;
  let newRows = rows;
  if (target.targetWidth !== undefined) {
    const blocks = Math.max(
      1,
      roundDiv(Math.max(target.targetWidth - 2 * borderTotal, 0), block * cellSize),
    );
    newCols = blocks * block;
  }
  if (target.targetHeight !== undefined) {
    const blocks = Math.max(
      1,
      roundDiv(Math.max(target.targetHeight - 2 * borderTotal, 0), block * cellSize),
    );
    newRows = blocks * block;
  }
  return {
    rows: newRows,
    cols: newCols,
    cellSize,
    achievedWidth: newCols * cellSize + 2 * borderTotal,
    achievedHeight: newRows * cellSize + 2 * borderTotal,
  };
}

/** Requested dims quarter-round then clamp [20", 140"] (bridge parity). */
export function normalizeDim(value: number): number {
  return clamp(roundDiv(value, QUARTER) * QUARTER, DIM_MIN, DIM_MAX);
}

/** Band scaling by the cell factor: round_div, 1/4" floor, 14" cap. */
export function bandScale(band: number, newCell: number, oldCell: number): number {
  return clamp(roundDiv(band * newCell, oldCell), BAND_MIN, BAND_MAX);
}

export interface LockedPreviewInput {
  rows: number;
  cols: number;
  cellSize: number;
  bands: number[];
}

export interface LockedPreview {
  cellSize: number;
  bands: number[];
  achievedWidth: number;
  achievedHeight: number;
  requested: { width?: number; height?: number; cell?: number };
}

/** Mirrors bridge.resize_locked including clamps and preset min-ratio. */
export function previewLocked(
  input: LockedPreviewInput,
  target: { width?: number; height?: number; cell?: number; preset?: { width: number; height: number } },
): LockedPreview {
  const borderTotal = input.bands.reduce((a, b) => a + b, 0);
  const requested: LockedPreview["requested"] = {};
  let cell: number;
  if (target.preset) {
    const width = normalizeDim(target.preset.width);
    const height = normalizeDim(target.preset.height);
    requested.width = width;
    requested.height = height;
    const byWidth = lockedResize(input.rows, input.cols, input.cellSize, borderTotal, {
      targetWidth: width,
    }).cellSize;
    const byHeight = lockedResize(input.rows, input.cols, input.cellSize, borderTotal, {
      targetHeight: height,
    }).cellSize;
    cell = Math.min(byWidth, byHeight);
  } else if (target.width !== undefined) {
    const width = normalizeDim(target.width);
    requested.width = width;
    cell = lockedResize(input.rows, input.cols, input.cellSize, borderTotal, {
      targetWidth: width,
    }).cellSize;
  } else if (target.height !== undefined) {
    const height = normalizeDim(target.height);
    requested.height = height;
    cell = lockedResize(input.rows, input.cols, input.cellSize, borderTotal, {
      targetHeight: height,
    }).cellSize;
  } else if (target.cell !== undefined) {
    requested.cell = target.cell;
    cell = target.cell;
  } else {
    cell = input.cellSize;
  }
  cell = clamp(cell, CELL_MIN, CELL_MAX);
  const bands = input.bands.map((band) => bandScale(band, cell, input.cellSize));
  const bandTotal = bands.reduce((a, b) => a + b, 0);
  return {
    cellSize: cell,
    bands,
    achievedWidth: input.cols * cell + 2 * bandTotal,
    achievedHeight: input.rows * cell + 2 * bandTotal,
    requested,
  };
}
