/**
 * Read-only, true-to-scale quilt viewer (S2). Pure JS: never calls Python.
 * Renders center squares + concentric border bands + binding onto a
 * devicePixelRatio-aware canvas over the cutting-mat stage, with canvas-drawn
 * inch rulers whose far-end labels are real DOM (asserted by the e2e).
 */
import { useCallback, useEffect, useMemo, useRef } from "react";
import type { QuiltModel } from "../model/types";
import { EIGHTHS_PER_INCH, formatEighths } from "../model/units";
import { useToast } from "../ui";
import { clampCell, dedupeCells, edgeBetween, pointToCell, supercoverLine } from "./paintGeometry";
import type { PaintCell } from "./paintGeometry";

const RULER_W = 41;
const RULER_H = 27;
const PAD = 16;
const BASE_PPI = 96; // 1 inch = 96 CSS px at 100% ("actual size")
const MIN_PPI = 0.7;
const MAX_PPI = BASE_PPI * 2.2;
const ZOOM_STEPS = [0.08, 0.12, 0.18, 0.25, 0.35, 0.5, 0.75, 1];
const CANVAS_FONT = "11.5px Seravek, 'Gill Sans', 'Trebuchet MS', Verdana, sans-serif";
// Touch paint: below this on-screen square size a finger tap zooms in instead
// of painting a mis-tap; the auto-zoom aims for a comfortable square size.
const TOUCH_MIN_CELL_PX = 14;
const TOUCH_TARGET_CELL_PX = 22;
const AUTO_ZOOM_TOAST =
  "Zoomed in — the squares were too small to touch. Tap again to edit; pan with two fingers.";
// Seam overlay: a warm, half-opaque line stroked over the fabric on every
// interior edge that is NOT merged (i.e. a real seam), matching the mock's
// seam style (rgba(110,80,45,0.4), 1.5px), drawn only when squares are large
// enough to read. Fixed alpha over user fabric colors reads in both skins.
const SEAM_STROKE = "rgba(110, 80, 45, 0.4)";
const SEAM_LINE_WIDTH = 1.5;
const SEAM_MIN_CELL_PX = 4.5;

type PaintStrokeState = { pointerId: number; cells: PaintCell[]; last: PaintCell };
// One seam gesture: `moved` flips the first time the pointer enters a different
// square (that is the merge drag); a gesture that never leaves its start square
// is a tap (split). `edges` collects the same-fabric interior edges swept.
type SeamGestureState = {
  pointerId: number;
  startCell: PaintCell;
  lastCell: PaintCell;
  edges: Set<string>;
  moved: boolean;
};

interface View {
  ppi: number;
  panX: number;
  panY: number;
  fit: boolean;
  cvW: number;
  cvH: number;
}

interface Colors {
  mut: string;
  ink2: string;
  uncFill: string;
  uncStroke: string;
}

/** PARITY item 6: a square is uncertain below this per-cell confidence. */
const UNCERTAIN_THRESHOLD = 0.9;

interface ModelData {
  cell: number;
  cols: number;
  rows: number;
  bandTotal: number;
  finishedWidth: number;
  finishedHeight: number;
  colorById: Map<string, string>;
  majorityId: string;
  majorityColor: string;
  borders: { width: number; color: string }[];
  bindingStroke: string;
  cells: string[][];
  cellConfidence: number[][] | null;
}

type Gesture =
  | { type: "none" }
  | { type: "pan"; lastX: number; lastY: number }
  | { type: "pinch"; startDist: number; ppi0: number; qx: number; qy: number };

function clamp(v: number, lo: number, hi: number): number {
  return v < lo ? lo : v > hi ? hi : v;
}

function shade(hex: string, factor: number): string {
  const m = /^#?([0-9a-f]{6})$/i.exec(hex.trim());
  if (!m) return hex;
  const n = parseInt(m[1], 16);
  const r = Math.round(((n >> 16) & 255) * factor);
  const g = Math.round(((n >> 8) & 255) * factor);
  const b = Math.round((n & 255) * factor);
  return `rgb(${r}, ${g}, ${b})`;
}

function readColors(): Colors {
  const cs = getComputedStyle(document.documentElement);
  const get = (name: string, fallback: string): string => {
    const v = cs.getPropertyValue(name).trim();
    return v || fallback;
  };
  return {
    mut: get("--mut", "#8a7a61"),
    ink2: get("--ink2", "#5d4f39"),
    uncFill: get("--uncertain-fill", "rgba(196, 90, 40, 0.32)"),
    uncStroke: get("--uncertain-stroke", "#d06a35"),
  };
}

function prepCanvas(
  canvas: HTMLCanvasElement,
  cssW: number,
  cssH: number,
  dpr: number,
): CanvasRenderingContext2D | null {
  const bw = Math.max(1, Math.round(cssW * dpr));
  const bh = Math.max(1, Math.round(cssH * dpr));
  if (canvas.width !== bw) canvas.width = bw;
  if (canvas.height !== bh) canvas.height = bh;
  const ctx = canvas.getContext("2d");
  if (!ctx) return null;
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  return ctx;
}

function drawQuilt(ctx: CanvasRenderingContext2D, view: View, md: ModelData): void {
  const { panX, panY, ppi } = view;
  const pxPerE = ppi / EIGHTHS_PER_INCH;
  const wPx = md.finishedWidth * pxPerE;
  const hPx = md.finishedHeight * pxPerE;

  // Warm drop shadow under the whole quilt, drawn once behind everything.
  ctx.save();
  ctx.shadowColor = "rgba(60, 40, 15, 0.28)";
  ctx.shadowBlur = 14;
  ctx.shadowOffsetY = 5;
  ctx.fillStyle = md.borders.length ? md.borders[md.borders.length - 1].color : md.majorityColor;
  ctx.fillRect(panX, panY, wPx, hPx);
  ctx.restore();

  // Concentric border bands, outermost first, inset toward the center.
  let x0 = 0;
  let y0 = 0;
  let x1 = md.finishedWidth;
  let y1 = md.finishedHeight;
  for (let i = md.borders.length - 1; i >= 0; i--) {
    const b = md.borders[i];
    ctx.fillStyle = b.color;
    ctx.fillRect(panX + x0 * pxPerE, panY + y0 * pxPerE, (x1 - x0) * pxPerE, (y1 - y0) * pxPerE);
    x0 += b.width;
    y0 += b.width;
    x1 -= b.width;
    y1 -= b.width;
  }

  // Center grid: paint the majority fabric as one rect, then only the
  // minority squares (culled to the viewport). 0.3px overdraw kills seams.
  const cx0 = panX + md.bandTotal * pxPerE;
  const cy0 = panY + md.bandTotal * pxPerE;
  const cellPx = md.cell * pxPerE;
  ctx.fillStyle = md.majorityColor;
  ctx.fillRect(cx0, cy0, md.cols * cellPx, md.rows * cellPx);

  const over = 0.3;
  const colStart = Math.max(0, Math.floor((0 - cx0) / cellPx));
  const colEnd = Math.min(md.cols - 1, Math.ceil((view.cvW - cx0) / cellPx));
  const rowStart = Math.max(0, Math.floor((0 - cy0) / cellPx));
  const rowEnd = Math.min(md.rows - 1, Math.ceil((view.cvH - cy0) / cellPx));
  for (let r = rowStart; r <= rowEnd; r++) {
    const row = md.cells[r];
    if (!row) continue;
    for (let c = colStart; c <= colEnd; c++) {
      const id = row[c];
      if (id == null || id === md.majorityId) continue;
      const color = md.colorById.get(id);
      if (!color) continue;
      ctx.fillStyle = color;
      ctx.fillRect(cx0 + c * cellPx, cy0 + r * cellPx, cellPx + over, cellPx + over);
    }
  }

  // Binding: a darkened outline just inside the finished edge.
  ctx.strokeStyle = md.bindingStroke;
  ctx.lineWidth = 2.5;
  ctx.strokeRect(panX + 1.25, panY + 1.25, wPx - 2.5, hPx - 2.5);
}

/**
 * Live paint preview: the model is only mutated when the stroke commits on
 * pointerup, so the pending squares are drawn on top of the quilt in the
 * selected fabric's color while the finger/mouse is down.
 */
function drawStrokePreview(
  ctx: CanvasRenderingContext2D,
  view: View,
  md: ModelData,
  stroke: PaintStrokeState | null,
  selectedFabricId: string | null,
): void {
  if (!stroke || selectedFabricId == null) return;
  const color = md.colorById.get(selectedFabricId);
  if (!color) return;
  const pxPerE = view.ppi / EIGHTHS_PER_INCH;
  const cx0 = view.panX + md.bandTotal * pxPerE;
  const cy0 = view.panY + md.bandTotal * pxPerE;
  const cellPx = md.cell * pxPerE;
  ctx.fillStyle = color;
  for (const c of stroke.cells) {
    if (c.row < 0 || c.row >= md.rows || c.col < 0 || c.col >= md.cols) continue;
    ctx.fillRect(cx0 + c.col * cellPx, cy0 + c.row * cellPx, cellPx + 0.3, cellPx + 0.3);
  }
}

/**
 * Low-confidence overlay (S6, PARITY item 6): a translucent terracotta rect
 * plus outline over every center square whose per-cell confidence is below
 * 0.90. Fixed uncertain tokens (both skins). Culled to the viewport and drawn
 * only when squares are large enough to read.
 */
function drawUncertainOverlay(
  ctx: CanvasRenderingContext2D,
  view: View,
  md: ModelData,
  colors: Colors,
): void {
  const confidence = md.cellConfidence;
  if (!confidence) return;
  const pxPerE = view.ppi / EIGHTHS_PER_INCH;
  const cellPx = md.cell * pxPerE;
  if (cellPx < SEAM_MIN_CELL_PX) return;
  const cx0 = view.panX + md.bandTotal * pxPerE;
  const cy0 = view.panY + md.bandTotal * pxPerE;

  const colStart = Math.max(0, Math.floor((0 - cx0) / cellPx));
  const colEnd = Math.min(md.cols - 1, Math.ceil((view.cvW - cx0) / cellPx));
  const rowStart = Math.max(0, Math.floor((0 - cy0) / cellPx));
  const rowEnd = Math.min(md.rows - 1, Math.ceil((view.cvH - cy0) / cellPx));
  if (colStart > colEnd || rowStart > rowEnd) return;

  ctx.save();
  ctx.fillStyle = colors.uncFill;
  ctx.strokeStyle = colors.uncStroke;
  ctx.lineWidth = 1;
  for (let r = rowStart; r <= rowEnd; r++) {
    const row = confidence[r];
    if (!row) continue;
    for (let c = colStart; c <= colEnd; c++) {
      const value = row[c];
      if (value == null || value >= UNCERTAIN_THRESHOLD) continue;
      const x = cx0 + c * cellPx;
      const y = cy0 + r * cellPx;
      ctx.fillRect(x, y, cellPx, cellPx);
      ctx.strokeRect(x + 0.5, y + 0.5, cellPx - 1, cellPx - 1);
    }
  }
  ctx.restore();
}

/**
 * Seam-preview overlay (S5): in seams mode, stroke a line on every interior
 * center-grid edge that is not in `merges`, plus the pieced center's outer
 * frame. Merged edges get nothing (the two squares read as one piece). The
 * whole overlay is one Path2D stroked once, so the translucent line never
 * double-darkens where segments meet. Culled to the viewport and skipped when
 * squares are too small to show a seam.
 */
function drawSeamOverlay(
  ctx: CanvasRenderingContext2D,
  view: View,
  md: ModelData,
  merges: Set<string>,
): void {
  const pxPerE = view.ppi / EIGHTHS_PER_INCH;
  const cellPx = md.cell * pxPerE;
  if (cellPx < SEAM_MIN_CELL_PX) return;
  const cx0 = view.panX + md.bandTotal * pxPerE;
  const cy0 = view.panY + md.bandTotal * pxPerE;

  const colStart = Math.max(0, Math.floor((0 - cx0) / cellPx));
  const colEnd = Math.min(md.cols - 1, Math.ceil((view.cvW - cx0) / cellPx));
  const rowStart = Math.max(0, Math.floor((0 - cy0) / cellPx));
  const rowEnd = Math.min(md.rows - 1, Math.ceil((view.cvH - cy0) / cellPx));
  if (colStart > colEnd || rowStart > rowEnd) return;

  const path = new Path2D();
  // Interior vertical edges `r,c:v` (between columns c and c+1).
  const vColEnd = Math.min(colEnd, md.cols - 2);
  for (let r = rowStart; r <= rowEnd; r++) {
    const y = cy0 + r * cellPx;
    for (let c = colStart; c <= vColEnd; c++) {
      if (merges.has(`${r},${c}:v`)) continue;
      const x = cx0 + (c + 1) * cellPx;
      path.moveTo(x, y);
      path.lineTo(x, y + cellPx);
    }
  }
  // Interior horizontal edges `r,c:h` (between rows r and r+1).
  const hRowEnd = Math.min(rowEnd, md.rows - 2);
  for (let r = rowStart; r <= hRowEnd; r++) {
    const y = cy0 + (r + 1) * cellPx;
    for (let c = colStart; c <= colEnd; c++) {
      if (merges.has(`${r},${c}:h`)) continue;
      const x = cx0 + c * cellPx;
      path.moveTo(x, y);
      path.lineTo(x + cellPx, y);
    }
  }
  // Outer frame of the pieced center (the mock draws this perimeter too).
  const gx1 = cx0 + md.cols * cellPx;
  const gy1 = cy0 + md.rows * cellPx;
  path.moveTo(cx0, cy0);
  path.lineTo(gx1, cy0);
  path.lineTo(gx1, gy1);
  path.lineTo(cx0, gy1);
  path.lineTo(cx0, cy0);

  ctx.save();
  ctx.strokeStyle = SEAM_STROKE;
  ctx.lineWidth = SEAM_LINE_WIDTH;
  ctx.lineCap = "butt";
  ctx.stroke(path);
  ctx.restore();
}

function drawTopRuler(
  ctx: CanvasRenderingContext2D,
  view: View,
  md: ModelData,
  colors: Colors,
): void {
  ctx.clearRect(0, 0, view.cvW, RULER_H);
  const off = view.panX;
  const ppi = view.ppi;
  const lenIn = md.finishedWidth / EIGHTHS_PER_INCH;
  const floorLen = Math.floor(lenIn + 1e-6);
  ctx.font = CANVAS_FONT;
  ctx.textBaseline = "alphabetic";
  for (let i = 0; i <= floorLen; i++) {
    const p = off + i * ppi;
    if (p < -4 || p > view.cvW + 4) continue;
    const major = i % 5 === 0;
    ctx.strokeStyle = major ? colors.ink2 : colors.mut;
    ctx.lineWidth = major ? 1.6 : 1;
    ctx.beginPath();
    ctx.moveTo(p, RULER_H);
    ctx.lineTo(p, RULER_H - (major ? 11 : 6));
    ctx.stroke();
    if (major && (i === 0 || (lenIn - i) * ppi >= 26)) {
      ctx.fillStyle = colors.mut;
      ctx.textAlign = "center";
      ctx.fillText(String(i), p, 12);
    }
  }
  const pend = off + lenIn * ppi;
  if (pend >= -4 && pend <= view.cvW + 4) {
    ctx.strokeStyle = colors.ink2;
    ctx.lineWidth = 1.6;
    ctx.beginPath();
    ctx.moveTo(pend, RULER_H);
    ctx.lineTo(pend, RULER_H - 11);
    ctx.stroke();
  }
}

function drawLeftRuler(
  ctx: CanvasRenderingContext2D,
  view: View,
  md: ModelData,
  colors: Colors,
): void {
  ctx.clearRect(0, 0, RULER_W, view.cvH);
  const off = view.panY;
  const ppi = view.ppi;
  const lenIn = md.finishedHeight / EIGHTHS_PER_INCH;
  const floorLen = Math.floor(lenIn + 1e-6);
  ctx.font = CANVAS_FONT;
  ctx.textBaseline = "alphabetic";
  for (let i = 0; i <= floorLen; i++) {
    const p = off + i * ppi;
    if (p < -4 || p > view.cvH + 4) continue;
    const major = i % 5 === 0;
    ctx.strokeStyle = major ? colors.ink2 : colors.mut;
    ctx.lineWidth = major ? 1.6 : 1;
    ctx.beginPath();
    ctx.moveTo(RULER_W, p);
    ctx.lineTo(RULER_W - (major ? 11 : 6), p);
    ctx.stroke();
    if (major && (i === 0 || (lenIn - i) * ppi >= 20)) {
      ctx.fillStyle = colors.mut;
      ctx.textAlign = "right";
      ctx.fillText(String(i), 27, p + 4);
    }
  }
  const pend = off + lenIn * ppi;
  if (pend >= -4 && pend <= view.cvH + 4) {
    ctx.strokeStyle = colors.ink2;
    ctx.lineWidth = 1.6;
    ctx.beginPath();
    ctx.moveTo(RULER_W, pend);
    ctx.lineTo(RULER_W - 11, pend);
    ctx.stroke();
  }
}

const CSS = `
.qc-root { display: flex; flex-direction: column; gap: 10px; }
.qc-toolbar { display: flex; align-items: center; gap: 6px; }
.qc-zbtn { width: 38px; height: 38px; font-size: 20px; line-height: 1; color: var(--ink2); background: var(--card2); border: 1.5px solid var(--line2); border-radius: 10px; cursor: pointer; }
.qc-zbtn:hover { background: var(--card3); }
.qc-zlabel { min-width: 46px; text-align: center; font: 600 14px var(--sans, sans-serif); color: var(--mut); }
.qc-fit { height: 38px; padding: 0 12px; font: 600 14px var(--sans, sans-serif); color: var(--ink2); background: var(--card2); border: 1.5px solid var(--line2); border-radius: 10px; cursor: pointer; }
.qc-fit:hover { background: var(--card3); }
.qc-stage { position: relative; background: var(--stage); border-radius: 12px; box-shadow: inset 0 1px 8px var(--shadow); overflow: hidden; height: clamp(430px, calc(100vh - 330px), 860px); }
.qc-corner { position: absolute; left: 0; top: 0; width: 41px; height: 27px; background: var(--card2); border-right: 1px solid var(--line); border-bottom: 1px solid var(--line); z-index: 2; display: flex; align-items: center; justify-content: center; }
.qc-corner span { font: italic 12px var(--serif, serif); color: var(--mut); }
.qc-topruler { position: absolute; left: 41px; right: 0; top: 0; height: 27px; background: var(--card2); border-bottom: 1px solid var(--line); overflow: hidden; z-index: 1; }
.qc-leftruler { position: absolute; left: 0; top: 27px; bottom: 0; width: 41px; background: var(--card2); border-right: 1px solid var(--line); overflow: hidden; z-index: 1; }
.qc-rulercanvas { position: absolute; left: 0; top: 0; width: 100%; height: 100%; display: block; }
.qc-viewport { position: absolute; left: 41px; top: 27px; right: 0; bottom: 0; overflow: hidden; }
.qc-canvas { position: absolute; left: 0; top: 0; width: 100%; height: 100%; display: block; touch-action: none; user-select: none; cursor: grab; }
.qc-canvas:active { cursor: grabbing; }
.qc-canvas--paint, .qc-canvas--paint:active { cursor: crosshair; }
.qc-canvas--seams, .qc-canvas--seams:active { cursor: cell; }
.qc-ruler-end-x { position: absolute; top: 4px; left: 0; font: 700 12px var(--sans, sans-serif); color: var(--accent); pointer-events: none; white-space: nowrap; }
.qc-ruler-end-y { position: absolute; top: 0; left: 0; width: 34px; text-align: right; font: 700 12px var(--sans, sans-serif); color: var(--accent); pointer-events: none; }
.qc-caption { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; padding: 0 4px; }
.qc-scale { font: 400 13.5px var(--sans, sans-serif); color: var(--faint); }
.qc-size-num { font: 600 19px var(--serif, serif); color: var(--ink); }
.qc-size-suffix { font: 400 13.5px var(--sans, sans-serif); color: var(--faint); }
`;

export function QuiltCanvas({
  model,
  mode = "move",
  selectedFabricId = null,
  onPaintStroke,
  seamMerges,
  onSeamDrag,
  onSeamTap,
  showUncertain = false,
}: {
  model: QuiltModel;
  mode?: "move" | "paint" | "seams";
  selectedFabricId?: string | null;
  onPaintStroke?: (cells: { row: number; col: number }[]) => void;
  seamMerges?: string[];
  onSeamDrag?: (edges: string[]) => void;
  onSeamTap?: (cell: { row: number; col: number }) => void;
  showUncertain?: boolean;
}) {
  const modelData = useMemo<ModelData>(() => {
    const cell = model.center.cell_size;
    const cols = model.center.cols;
    const rows = model.center.rows;
    const cells = model.center.cells;
    const bandTotal = model.borders.reduce((s, b) => s + b.width, 0);
    const finishedWidth = cols * cell + 2 * bandTotal;
    const finishedHeight = rows * cell + 2 * bandTotal;
    const colorById = new Map(model.palette.fabrics.map((f) => [f.id, f.color]));

    const counts = new Map<string, number>();
    for (let r = 0; r < rows; r++) {
      const row = cells[r];
      if (!row) continue;
      for (let c = 0; c < cols; c++) {
        const id = row[c];
        if (id == null) continue;
        counts.set(id, (counts.get(id) ?? 0) + 1);
      }
    }
    let majorityId = model.palette.fabrics[0]?.id ?? "";
    let max = -1;
    for (const [id, n] of counts) {
      if (n > max) {
        max = n;
        majorityId = id;
      }
    }

    const bindingColor = colorById.get(model.binding.fabric_id) ?? "#8c6f4e";
    return {
      cell,
      cols,
      rows,
      bandTotal,
      finishedWidth,
      finishedHeight,
      colorById,
      majorityId,
      majorityColor: colorById.get(majorityId) ?? "#cccccc",
      borders: model.borders.map((b) => ({
        width: b.width,
        color: colorById.get(b.fabric_id) ?? "#cccccc",
      })),
      bindingStroke: shade(bindingColor, 0.72),
      cells,
      cellConfidence: model.center.cell_confidence ?? null,
    };
  }, [model]);

  const { finishedWidth, finishedHeight } = modelData;

  const containerRef = useRef<HTMLDivElement>(null);
  const quiltViewportRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const topRulerRef = useRef<HTMLCanvasElement>(null);
  const leftRulerRef = useRef<HTMLCanvasElement>(null);
  const xEndRef = useRef<HTMLSpanElement>(null);
  const yEndRef = useRef<HTMLSpanElement>(null);
  const scaleTextRef = useRef<HTMLSpanElement>(null);
  const zoomLabelRef = useRef<HTMLSpanElement>(null);

  const viewRef = useRef<View>({ ppi: BASE_PPI, panX: 0, panY: 0, fit: true, cvW: 0, cvH: 0 });
  const pointersRef = useRef<Map<number, { x: number; y: number }>>(new Map());
  const gestureRef = useRef<Gesture>({ type: "none" });
  const colorsRef = useRef<Colors>({
    mut: "#8a7a61",
    ink2: "#5d4f39",
    uncFill: "rgba(196, 90, 40, 0.32)",
    uncStroke: "#d06a35",
  });
  const rafRef = useRef<number>(0);
  const drawRef = useRef<() => void>(() => {});

  // Live prop/model mirrors so the once-bound pointer listeners never go stale.
  const modeRef = useRef(mode);
  modeRef.current = mode;
  const selectedFabricRef = useRef<string | null>(selectedFabricId ?? null);
  selectedFabricRef.current = selectedFabricId ?? null;
  const onPaintStrokeRef = useRef(onPaintStroke);
  onPaintStrokeRef.current = onPaintStroke;
  const onSeamDragRef = useRef(onSeamDrag);
  onSeamDragRef.current = onSeamDrag;
  const onSeamTapRef = useRef(onSeamTap);
  onSeamTapRef.current = onSeamTap;
  const seamMergeSet = useMemo(() => new Set(seamMerges ?? []), [seamMerges]);
  const seamMergeSetRef = useRef(seamMergeSet);
  seamMergeSetRef.current = seamMergeSet;
  const modelDataRef = useRef(modelData);
  modelDataRef.current = modelData;
  const strokeRef = useRef<PaintStrokeState | null>(null);
  const seamRef = useRef<SeamGestureState | null>(null);
  const toast = useToast();
  const pushRef = useRef(toast.push);
  pushRef.current = toast.push;
  const showUncertainRef = useRef(showUncertain);
  showUncertainRef.current = showUncertain;

  const draw = useCallback(() => {
    const canvas = canvasRef.current;
    const topR = topRulerRef.current;
    const leftR = leftRulerRef.current;
    const vp = quiltViewportRef.current;
    if (!canvas || !topR || !leftR || !vp) return;
    const view = viewRef.current;
    const dpr = window.devicePixelRatio || 1;
    const cvW = vp.clientWidth;
    const cvH = vp.clientHeight;
    if (cvW < 2 || cvH < 2) return;
    view.cvW = cvW;
    view.cvH = cvH;

    if (view.fit) {
      const inW = modelData.finishedWidth / EIGHTHS_PER_INCH;
      const inH = modelData.finishedHeight / EIGHTHS_PER_INCH;
      const ppi = Math.max(MIN_PPI, Math.min((cvW - 2 * PAD) / inW, (cvH - 2 * PAD) / inH));
      view.ppi = ppi;
      view.panX = (cvW - inW * ppi) / 2;
      view.panY = (cvH - inH * ppi) / 2;
    }

    // Publish the live transform so the paint layer (and the e2e) can convert
    // between pointer px and square coordinates. Full precision, no rounding.
    canvas.setAttribute("data-view-scale", String(view.ppi / EIGHTHS_PER_INCH));
    canvas.setAttribute("data-view-origin-x", String(view.panX));
    canvas.setAttribute("data-view-origin-y", String(view.panY));

    const colors = colorsRef.current;
    const qctx = prepCanvas(canvas, cvW, cvH, dpr);
    if (qctx) {
      qctx.clearRect(0, 0, cvW, cvH);
      drawQuilt(qctx, view, modelData);
      if (showUncertainRef.current) {
        drawUncertainOverlay(qctx, view, modelData, colors);
      }
      drawStrokePreview(qctx, view, modelData, strokeRef.current, selectedFabricRef.current);
      if (modeRef.current === "seams") {
        drawSeamOverlay(qctx, view, modelData, seamMergeSetRef.current);
      }
    }
    const tctx = prepCanvas(topR, cvW, RULER_H, dpr);
    if (tctx) drawTopRuler(tctx, view, modelData, colors);
    const lctx = prepCanvas(leftR, RULER_W, cvH, dpr);
    if (lctx) drawLeftRuler(lctx, view, modelData, colors);

    const inW = modelData.finishedWidth / EIGHTHS_PER_INCH;
    const inH = modelData.finishedHeight / EIGHTHS_PER_INCH;
    if (xEndRef.current) {
      xEndRef.current.style.transform = `translateX(calc(${(view.panX + inW * view.ppi).toFixed(1)}px - 50%))`;
    }
    if (yEndRef.current) {
      yEndRef.current.style.transform = `translateY(calc(${(view.panY + inH * view.ppi).toFixed(1)}px - 50%))`;
    }

    const ppi = view.ppi;
    const zoomPct = Math.round((ppi / BASE_PPI) * 100);
    const n = Math.max(1, Math.round(BASE_PPI / ppi));
    let scaleTxt: string;
    let zLabel: string;
    if (view.fit) {
      scaleTxt = `Fit — about 1:${n} of real size`;
      zLabel = "Fit";
    } else if (Math.abs(ppi - BASE_PPI) < 0.5) {
      scaleTxt = "100% — actual size on most screens";
      zLabel = "100%";
    } else {
      scaleTxt = `${zoomPct}% — about 1:${n} of real size`;
      zLabel = `${zoomPct}%`;
    }
    if (scaleTextRef.current) scaleTextRef.current.textContent = scaleTxt;
    if (zoomLabelRef.current) zoomLabelRef.current.textContent = zLabel;
  }, [modelData]);

  const scheduleDraw = useCallback(() => {
    if (rafRef.current) return;
    rafRef.current = requestAnimationFrame(() => {
      rafRef.current = 0;
      drawRef.current();
    });
  }, []);

  const zoomCenter = useCallback(
    (targetPpi: number) => {
      const v = viewRef.current;
      const cx = v.cvW / 2;
      const cy = v.cvH / 2;
      const newPpi = clamp(targetPpi, MIN_PPI, MAX_PPI);
      const qx = (cx - v.panX) / v.ppi;
      const qy = (cy - v.panY) / v.ppi;
      v.panX = cx - qx * newPpi;
      v.panY = cy - qy * newPpi;
      v.ppi = newPpi;
      v.fit = false;
      scheduleDraw();
    },
    [scheduleDraw],
  );

  const handleZoomIn = useCallback(() => {
    const cur = viewRef.current.ppi / BASE_PPI;
    const next = ZOOM_STEPS.find((s) => s > cur * 1.01) ?? 1;
    zoomCenter(next * BASE_PPI);
  }, [zoomCenter]);

  const handleZoomOut = useCallback(() => {
    const cur = viewRef.current.ppi / BASE_PPI;
    let below = 0;
    for (const s of ZOOM_STEPS) {
      if (s < cur * 0.99) below = s;
    }
    if (below > 0) {
      zoomCenter(below * BASE_PPI);
    } else {
      viewRef.current.fit = true;
      scheduleDraw();
    }
  }, [zoomCenter, scheduleDraw]);

  const handleZoomFit = useCallback(() => {
    viewRef.current.fit = true;
    scheduleDraw();
  }, [scheduleDraw]);

  const onWheel = useCallback(
    (e: WheelEvent) => {
      e.preventDefault();
      const vp = quiltViewportRef.current;
      if (!vp) return;
      const r = vp.getBoundingClientRect();
      const cx = e.clientX - r.left;
      const cy = e.clientY - r.top;
      let dy = e.deltaY;
      if (e.deltaMode === 1) dy *= 16;
      else if (e.deltaMode === 2) dy *= viewRef.current.cvH || 400;
      const factor = Math.exp(-dy * 0.0015);
      const v = viewRef.current;
      const newPpi = clamp(v.ppi * factor, MIN_PPI, MAX_PPI);
      const qx = (cx - v.panX) / v.ppi;
      const qy = (cy - v.panY) / v.ppi;
      v.panX = cx - qx * newPpi;
      v.panY = cy - qy * newPpi;
      v.ppi = newPpi;
      v.fit = false;
      scheduleDraw();
    },
    [scheduleDraw],
  );

  // Rebuild the active gesture from whatever pointers remain down (used after
  // a pointer lifts or a stroke is cancelled).
  const resyncGesture = useCallback(() => {
    const pointers = pointersRef.current;
    if (pointers.size >= 2) {
      const pts = [...pointers.values()];
      const dist = Math.hypot(pts[0].x - pts[1].x, pts[0].y - pts[1].y) || 1;
      const midX = (pts[0].x + pts[1].x) / 2;
      const midY = (pts[0].y + pts[1].y) / 2;
      const v = viewRef.current;
      gestureRef.current = {
        type: "pinch",
        startDist: dist,
        ppi0: v.ppi,
        qx: (midX - v.panX) / v.ppi,
        qy: (midY - v.panY) / v.ppi,
      };
    } else if (pointers.size === 1) {
      const [only] = [...pointers.values()];
      gestureRef.current = { type: "pan", lastX: only.x, lastY: only.y };
    } else {
      gestureRef.current = { type: "none" };
    }
  }, []);

  const onPointerDown = useCallback(
    (e: PointerEvent) => {
      const canvas = canvasRef.current;
      const vp = quiltViewportRef.current;
      if (!canvas || !vp) return;
      const r = vp.getBoundingClientRect();
      const x = e.clientX - r.left;
      const y = e.clientY - r.top;
      const pointers = pointersRef.current;
      pointers.set(e.pointerId, { x, y });
      try {
        canvas.setPointerCapture(e.pointerId);
      } catch {
        /* capture is best-effort */
      }

      if (pointers.size >= 2) {
        // A second pointer abandons any in-progress paint or seam gesture
        // (nothing is committed) and turns it into a two-finger pan/pinch.
        strokeRef.current = null;
        seamRef.current = null;
        resyncGesture();
        return;
      }

      if (modeRef.current === "paint") {
        const md = modelDataRef.current;
        const v = viewRef.current;
        const cellCssPx = (v.ppi / EIGHTHS_PER_INCH) * md.cell;
        // Touch on tiny squares: zoom toward the tap instead of a mis-paint.
        if (e.pointerType === "touch" && cellCssPx < TOUCH_MIN_CELL_PX) {
          const targetPpi = clamp(
            (TOUCH_TARGET_CELL_PX * EIGHTHS_PER_INCH) / md.cell,
            MIN_PPI,
            MAX_PPI,
          );
          const qx = (x - v.panX) / v.ppi;
          const qy = (y - v.panY) / v.ppi;
          v.panX = x - qx * targetPpi;
          v.panY = y - qy * targetPpi;
          v.ppi = targetPpi;
          v.fit = false;
          gestureRef.current = { type: "none" };
          scheduleDraw();
          pushRef.current(AUTO_ZOOM_TOAST, "success");
          return;
        }
        // Painting needs a chosen fabric and a sink for the committed stroke.
        if (selectedFabricRef.current == null || !onPaintStrokeRef.current) {
          gestureRef.current = { type: "none" };
          return;
        }
        const cell = clampCell(
          pointToCell(x, y, {
            scale: v.ppi / EIGHTHS_PER_INCH,
            originX: v.panX,
            originY: v.panY,
            cell: md.cell,
            borderTotal: md.bandTotal,
          }),
          md.rows,
          md.cols,
        );
        strokeRef.current = { pointerId: e.pointerId, cells: [cell], last: cell };
        gestureRef.current = { type: "none" };
        scheduleDraw();
        return;
      }

      if (modeRef.current === "seams") {
        // Single-pointer drag is the merge gesture, never a pan. The gesture
        // stays a tap until the pointer enters a different square.
        const md = modelDataRef.current;
        const v = viewRef.current;
        const cell = clampCell(
          pointToCell(x, y, {
            scale: v.ppi / EIGHTHS_PER_INCH,
            originX: v.panX,
            originY: v.panY,
            cell: md.cell,
            borderTotal: md.bandTotal,
          }),
          md.rows,
          md.cols,
        );
        seamRef.current = {
          pointerId: e.pointerId,
          startCell: cell,
          lastCell: cell,
          edges: new Set(),
          moved: false,
        };
        gestureRef.current = { type: "none" };
        return;
      }

      // Move mode: single-pointer pan.
      gestureRef.current = { type: "pan", lastX: x, lastY: y };
    },
    [resyncGesture, scheduleDraw],
  );

  const onPointerMove = useCallback(
    (e: PointerEvent) => {
      const pointers = pointersRef.current;
      if (!pointers.has(e.pointerId)) return;
      const vp = quiltViewportRef.current;
      if (!vp) return;
      const r = vp.getBoundingClientRect();
      const x = e.clientX - r.left;
      const y = e.clientY - r.top;
      pointers.set(e.pointerId, { x, y });
      const v = viewRef.current;
      const g = gestureRef.current;

      if (pointers.size >= 2 && g.type === "pinch") {
        const pts = [...pointers.values()];
        const dist = Math.hypot(pts[0].x - pts[1].x, pts[0].y - pts[1].y) || 1;
        const midX = (pts[0].x + pts[1].x) / 2;
        const midY = (pts[0].y + pts[1].y) / 2;
        const f = dist / g.startDist;
        const newPpi = clamp(g.ppi0 * f, MIN_PPI, MAX_PPI);
        v.panX = midX - g.qx * newPpi;
        v.panY = midY - g.qy * newPpi;
        v.ppi = newPpi;
        v.fit = false;
        scheduleDraw();
        return;
      }

      const stroke = strokeRef.current;
      if (stroke && stroke.pointerId === e.pointerId) {
        const md = modelDataRef.current;
        const cell = clampCell(
          pointToCell(x, y, {
            scale: v.ppi / EIGHTHS_PER_INCH,
            originX: v.panX,
            originY: v.panY,
            cell: md.cell,
            borderTotal: md.bandTotal,
          }),
          md.rows,
          md.cols,
        );
        if (cell.row !== stroke.last.row || cell.col !== stroke.last.col) {
          // Walk the square line between samples so a fast drag skips nothing.
          const seg = supercoverLine(stroke.last, cell);
          for (let i = 1; i < seg.length; i++) stroke.cells.push(seg[i]);
          stroke.last = cell;
          scheduleDraw();
        }
        return;
      }

      const seam = seamRef.current;
      if (seam && seam.pointerId === e.pointerId) {
        const md = modelDataRef.current;
        const cell = clampCell(
          pointToCell(x, y, {
            scale: v.ppi / EIGHTHS_PER_INCH,
            originX: v.panX,
            originY: v.panY,
            cell: md.cell,
            borderTotal: md.bandTotal,
          }),
          md.rows,
          md.cols,
        );
        if (cell.row !== seam.lastCell.row || cell.col !== seam.lastCell.col) {
          // Walk the square line between samples so a fast drag skips no edge;
          // keep only interior edges whose two squares are the same fabric.
          const walk = supercoverLine(seam.lastCell, cell);
          for (let i = 1; i < walk.length; i++) {
            const p = walk[i - 1];
            const q = walk[i];
            const edge = edgeBetween(p, q);
            if (!edge) continue;
            const fa = md.cells[p.row]?.[p.col];
            const fb = md.cells[q.row]?.[q.col];
            if (fa != null && fa === fb) seam.edges.add(edge);
          }
          seam.lastCell = cell;
          seam.moved = true;
        }
        return;
      }

      if (g.type === "pan") {
        v.panX += x - g.lastX;
        v.panY += y - g.lastY;
        g.lastX = x;
        g.lastY = y;
        v.fit = false;
        scheduleDraw();
      }
    },
    [scheduleDraw],
  );

  const onPointerUp = useCallback(
    (e: PointerEvent) => {
      const pointers = pointersRef.current;
      const stroke = strokeRef.current;
      if (stroke && stroke.pointerId === e.pointerId) {
        // Commit exactly one stroke: the deduplicated in-bounds squares in
        // paint order. The store applies the selected fabric.
        strokeRef.current = null;
        const md = modelDataRef.current;
        const cells = dedupeCells(stroke.cells).filter(
          (c) => c.row >= 0 && c.row < md.rows && c.col >= 0 && c.col < md.cols,
        );
        if (cells.length > 0) onPaintStrokeRef.current?.(cells);
        scheduleDraw();
      }
      const seam = seamRef.current;
      if (seam && seam.pointerId === e.pointerId) {
        // A gesture that entered another square is a merge drag; one that never
        // left its start square is a tap that splits the piece under it.
        seamRef.current = null;
        if (seam.moved) {
          const edges = [...seam.edges];
          if (edges.length > 0) onSeamDragRef.current?.(edges);
        } else {
          onSeamTapRef.current?.({ row: seam.startCell.row, col: seam.startCell.col });
        }
      }
      pointers.delete(e.pointerId);
      const canvas = canvasRef.current;
      if (canvas) {
        try {
          canvas.releasePointerCapture(e.pointerId);
        } catch {
          /* release is best-effort */
        }
      }
      resyncGesture();
    },
    [resyncGesture, scheduleDraw],
  );

  const onPointerCancel = useCallback(
    (e: PointerEvent) => {
      // Cancel discards any pending paint or seam gesture without committing.
      strokeRef.current = null;
      seamRef.current = null;
      const pointers = pointersRef.current;
      pointers.delete(e.pointerId);
      const canvas = canvasRef.current;
      if (canvas) {
        try {
          canvas.releasePointerCapture(e.pointerId);
        } catch {
          /* release is best-effort */
        }
      }
      resyncGesture();
      scheduleDraw();
    },
    [resyncGesture, scheduleDraw],
  );

  // Keep the RAF draw pointer current and repaint on model changes WITHOUT
  // snapping back to fit - a paint edit must not reset the user's zoom/pan.
  useEffect(() => {
    drawRef.current = draw;
    scheduleDraw();
  }, [draw, scheduleDraw]);

  // The seam overlay depends on the mode and the merge set, neither of which is
  // a draw() dependency; repaint when either changes so it appears, hides, or
  // reflects a new fix without waiting on the next zoom/pan.
  useEffect(() => {
    scheduleDraw();
  }, [mode, seamMergeSet, showUncertain, scheduleDraw]);

  // Fit on mount and whenever the finished dimensions change (a new document).
  // Editing keeps the dimensions, so the current view is preserved.
  useEffect(() => {
    viewRef.current.fit = true;
    scheduleDraw();
  }, [finishedWidth, finishedHeight, scheduleDraw]);

  useEffect(() => {
    colorsRef.current = readColors();
    const vp = quiltViewportRef.current;
    const canvas = canvasRef.current;
    if (!vp || !canvas) return;
    scheduleDraw();

    const ro = new ResizeObserver(() => scheduleDraw());
    ro.observe(vp);
    const mo = new MutationObserver(() => {
      colorsRef.current = readColors();
      scheduleDraw();
    });
    mo.observe(document.documentElement, { attributes: true, attributeFilter: ["data-skin"] });

    canvas.addEventListener("wheel", onWheel, { passive: false });
    canvas.addEventListener("pointerdown", onPointerDown);
    canvas.addEventListener("pointermove", onPointerMove);
    canvas.addEventListener("pointerup", onPointerUp);
    canvas.addEventListener("pointercancel", onPointerCancel);

    return () => {
      ro.disconnect();
      mo.disconnect();
      canvas.removeEventListener("wheel", onWheel);
      canvas.removeEventListener("pointerdown", onPointerDown);
      canvas.removeEventListener("pointermove", onPointerMove);
      canvas.removeEventListener("pointerup", onPointerUp);
      canvas.removeEventListener("pointercancel", onPointerCancel);
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
    };
  }, [scheduleDraw, onWheel, onPointerDown, onPointerMove, onPointerUp, onPointerCancel]);

  return (
    <div className="qc-root" ref={containerRef}>
      <div className="qc-toolbar">
        <button type="button" className="qc-zbtn" aria-label="Zoom out" title="Zoom out" onClick={handleZoomOut}>
          −
        </button>
        <span className="qc-zlabel" ref={zoomLabelRef}>
          Fit
        </span>
        <button type="button" className="qc-zbtn" aria-label="Zoom in" title="Zoom in" onClick={handleZoomIn}>
          +
        </button>
        <button type="button" className="qc-fit" onClick={handleZoomFit}>
          Fit
        </button>
      </div>
      <div className="qc-stage">
        <div className="qc-corner">
          <span>in</span>
        </div>
        <div className="qc-topruler">
          <canvas ref={topRulerRef} className="qc-rulercanvas" />
          <span className="qc-ruler-end-x" ref={xEndRef} data-testid="ruler-x-end">
            {formatEighths(finishedWidth)}
          </span>
        </div>
        <div className="qc-leftruler">
          <canvas ref={leftRulerRef} className="qc-rulercanvas" />
          <span className="qc-ruler-end-y" ref={yEndRef} data-testid="ruler-y-end">
            {formatEighths(finishedHeight)}
          </span>
        </div>
        <div className="qc-viewport" ref={quiltViewportRef}>
          <canvas
            ref={canvasRef}
            className={`qc-canvas${
              mode === "paint" ? " qc-canvas--paint" : mode === "seams" ? " qc-canvas--seams" : ""
            }`}
            data-testid="quilt-canvas"
            data-mode={mode}
            data-finished-width={finishedWidth}
            data-finished-height={finishedHeight}
            data-cell-size={modelData.cell}
            data-border-total={modelData.bandTotal}
            role="img"
            aria-label={`Quilt preview, ${formatEighths(finishedWidth)} by ${formatEighths(finishedHeight)} finished`}
          />
        </div>
      </div>
      <div className="qc-caption">
        <span className="qc-scale" ref={scaleTextRef} />
        <span className="qc-size">
          <span className="qc-size-num">
            {formatEighths(finishedWidth)} × {formatEighths(finishedHeight)}
          </span>
          <span className="qc-size-suffix"> finished</span>
        </span>
      </div>
      <style>{CSS}</style>
    </div>
  );
}
