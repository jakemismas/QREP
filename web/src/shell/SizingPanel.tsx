/**
 * Sizing panel (S4, issue #44). Mixed-fraction W/H/square-size inputs with
 * steppers, a proportion lock, standard-size presets, an asked-vs-got line,
 * border rows, and the finished-size equation box.
 *
 * PARITY item 4 is the law here: the JS mirror in model/sizing.ts drives the
 * immediate typing/preview echo, but EVERY commit (Enter, blur, stepper,
 * preset, but not the lock toggle) round-trips through the bridge and adopts
 * its returned model, so the band-scaling math is engine-authoritative. Border
 * edits go through project's validate-then-commit gate instead of a resize.
 *
 * Copy follows the mock (squares never "cells"; mixed fractions everywhere).
 */
import { useEffect, useRef, useState } from "react";
import type { ChangeEvent } from "react";
import { formatEighths } from "../model/units";
import { parseFractionInput } from "../model/fraction";
import {
  BAND_MAX,
  BAND_MIN,
  CELL_MAX,
  CELL_MIN,
  PRESETS,
  normalizeDim,
  previewLocked,
  unlockedResize,
} from "../model/sizing";
import { useProject } from "../state/project";
import { Tooltip, useToast } from "../ui";

const QUARTER = 2; // 1/4" in eighths
const EIGHTH = 1; // 1/8" in eighths
const CUT_ALLOWANCE = 4; // 1/2" total seam allowance in eighths

function clampNum(value: number, low: number, high: number): number {
  return Math.max(low, Math.min(high, value));
}

/** The input echo of a length: a mixed fraction with no trailing inch mark. */
function fmtAscii(eighths: number): string {
  return formatEighths(eighths).replace(/"$/, "");
}

function gcd(a: number, b: number): number {
  while (b !== 0) {
    [a, b] = [b, a % b];
  }
  return a;
}

/**
 * Display-only block period, mirroring the engine's infer_block_structure:
 * the smallest p > 1 dividing both dims that tiles into <= 8 distinct p x p
 * blocks. A single distinct block is a uniform grid (block 1, PARITY item 15).
 */
function inferBlock(cells: string[][]): number {
  const rows = cells.length;
  if (rows === 0) return 1;
  const cols = cells[0].length;
  if (cols === 0) return 1;
  const g = gcd(rows, cols);
  for (let p = 2; p <= g; p++) {
    if (g % p !== 0) continue;
    const seen = new Set<string>();
    for (let br = 0; br < rows / p; br++) {
      for (let bc = 0; bc < cols / p; bc++) {
        const parts: string[] = [];
        for (let r = 0; r < p; r++) {
          for (let c = 0; c < p; c++) parts.push(cells[br * p + r][bc * p + c]);
        }
        seen.add(parts.join(","));
      }
    }
    if (seen.size <= 8) return seen.size > 1 ? p : 1;
  }
  return 1;
}

const PRESET_TOL = 0.56; // 0.07" in eighths: an axis matches a preset within this

function presetKey(name: string): string {
  return name.toLowerCase();
}

function detectPreset(width: number, height: number): string {
  for (const p of PRESETS) {
    if (Math.abs(p.width - width) <= PRESET_TOL && Math.abs(p.height - height) <= PRESET_TOL) {
      return presetKey(p.name);
    }
  }
  return "custom";
}

/**
 * A single mixed-fraction field: owns its draft, resyncs from the committed
 * value, restores + toasts on invalid, and reports keystrokes for live preview.
 */
function FractionField({
  testid,
  valueEighths,
  ariaLabel,
  errorCopy,
  narrow,
  onCommit,
  onPreview,
}: {
  testid: string;
  valueEighths: number;
  ariaLabel: string;
  errorCopy: string;
  narrow?: boolean;
  onCommit: (parsed: number) => void;
  onPreview?: (parsed: number | null) => void;
}) {
  const toast = useToast();
  const [draft, setDraft] = useState(() => fmtAscii(valueEighths));
  const editingRef = useRef(false);

  useEffect(() => {
    if (!editingRef.current) setDraft(fmtAscii(valueEighths));
  }, [valueEighths]);

  const commit = () => {
    editingRef.current = false;
    onPreview?.(null);
    const parsed = parseFractionInput(draft);
    if (parsed == null) {
      setDraft(fmtAscii(valueEighths));
      toast.push(errorCopy, "error");
      return;
    }
    onCommit(parsed);
  };

  return (
    <input
      className={`sz-input${narrow ? " sz-input--narrow" : ""}`}
      data-testid={testid}
      value={draft}
      aria-label={ariaLabel}
      inputMode="decimal"
      onChange={(event) => {
        editingRef.current = true;
        setDraft(event.target.value);
        onPreview?.(parseFractionInput(event.target.value));
      }}
      onBlur={commit}
      onKeyDown={(event) => {
        if (event.key === "Enter") {
          event.preventDefault();
          event.currentTarget.blur();
        } else if (event.key === "Escape") {
          editingRef.current = false;
          onPreview?.(null);
          setDraft(fmtAscii(valueEighths));
          event.currentTarget.blur();
        }
      }}
    />
  );
}

function Stepper({
  glyph,
  title,
  ariaLabel,
  testid,
  onClick,
}: {
  glyph: string;
  title: string;
  ariaLabel: string;
  testid?: string;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      className="sz-step"
      data-testid={testid}
      title={title}
      aria-label={ariaLabel}
      onClick={onClick}
    >
      {glyph}
    </button>
  );
}

export function SizingPanel() {
  const {
    model,
    lastResize,
    resizeLocked,
    resizeUnlocked,
    setBorderWidth,
    setBorderFabric,
    addBorder,
    removeBorder,
    clearResizeHint,
  } = useProject();
  const toast = useToast();
  const [locked, setLocked] = useState(true);
  // Live preview target while a dimension field is mid-edit.
  const [preview, setPreview] = useState<{ axis: "width" | "height"; value: number } | null>(null);

  if (model === null) return null;

  const cell = model.center.cell_size;
  const cols = model.center.cols;
  const rows = model.center.rows;
  const bands = model.borders;
  const bandWidths = bands.map((b) => b.width);
  const borderTotal = bandWidths.reduce((a, b) => a + b, 0);
  const finishedWidth = cols * cell + 2 * borderTotal;
  const finishedHeight = rows * cell + 2 * borderTotal;
  const block = inferBlock(model.center.cells);
  const fabrics = model.palette.fabrics;
  const colorById = new Map(fabrics.map((f) => [f.id, f.color]));

  const presetVal = detectPreset(finishedWidth, finishedHeight);

  // --- asked-vs-got -------------------------------------------------------
  // A live mirror preview wins while typing; otherwise the committed bridge
  // envelope drives it, shown only when a requested axis missed its target.
  let askText: string | null = null;
  let gotText: string | null = null;
  if (preview) {
    let reqW: number;
    let reqH: number;
    let gotW: number;
    let gotH: number;
    if (locked) {
      const p = previewLocked(
        { rows, cols, cellSize: cell, bands: bandWidths },
        preview.axis === "width" ? { width: preview.value } : { height: preview.value },
      );
      gotW = p.achievedWidth;
      gotH = p.achievedHeight;
      reqW = preview.axis === "width" ? (p.requested.width ?? preview.value) : gotW;
      reqH = preview.axis === "height" ? (p.requested.height ?? preview.value) : gotH;
    } else {
      const dim = normalizeDim(preview.value);
      const r = unlockedResize(
        rows,
        cols,
        cell,
        borderTotal,
        block,
        preview.axis === "width" ? { targetWidth: dim } : { targetHeight: dim },
      );
      gotW = r.achievedWidth;
      gotH = r.achievedHeight;
      reqW = preview.axis === "width" ? dim : gotW;
      reqH = preview.axis === "height" ? dim : gotH;
    }
    if (gotW !== reqW || gotH !== reqH) {
      askText = `${formatEighths(reqW)} × ${formatEighths(reqH)}`;
      gotText = `${formatEighths(gotW)} × ${formatEighths(gotH)}`;
    }
  } else if (lastResize) {
    const { requested, achieved } = lastResize;
    const missW = requested.width != null && requested.width !== achieved.width;
    const missH = requested.height != null && requested.height !== achieved.height;
    if (missW || missH) {
      askText = `${formatEighths(requested.width ?? achieved.width)} × ${formatEighths(
        requested.height ?? achieved.height,
      )}`;
      gotText = `${formatEighths(achieved.width)} × ${formatEighths(achieved.height)}`;
    }
  }

  // --- copy ---------------------------------------------------------------
  const lockTitle = locked
    ? "Locked: sizes scale together, pattern stays put. Tap to unlock."
    : "Unlocked: each side grows by whole blocks. Tap to lock.";
  const lockModeLine = locked
    ? "Locked: the pattern stays identical — the squares themselves resize."
    : block > 1
      ? `Unlocked: each side grows or shrinks by whole blocks (${block} squares at a time).`
      : "Unlocked: each side grows or shrinks a row or column of squares at a time.";
  const stepTitle = locked ? "Scales the whole quilt" : "One block at a time";
  const cutText = fmtAscii(cell + CUT_ALLOWANCE);

  // Mock copy (grid shape at square size) plus the engine-computed area.
  const eqSquares =
    `${cols} × ${rows} squares at ${formatEighths(cell)} — ` +
    `${formatEighths(cols * cell)} × ${formatEighths(rows * cell)}`;
  const eqBorder = `${bandWidths.map((w) => formatEighths(w)).join(" + ")}${
    bands.length > 1 ? " bands" : " all around"
  }`;
  const eqTotal = `${formatEighths(finishedWidth)} × ${formatEighths(finishedHeight)}`;
  const blocksLine =
    block === 5
      ? `${cols / 5} × ${rows / 5} blocks of 5 × 5 squares — ${
          (cols / 5) % 2 && (rows / 5) % 2
            ? "a chain block lands in every corner."
            : "even block count; the chain won’t reach every corner."
        }`
      : `${(cols * rows).toLocaleString("en-US")} squares to play with — paint away.`;

  // --- actions ------------------------------------------------------------
  const toggleLock = () => {
    const next = !locked;
    setLocked(next);
    clearResizeHint();
    setPreview(null);
    toast.push(
      next
        ? "Locked — width and height scale together."
        : "Unlocked — each side moves by whole blocks.",
      "success",
    );
  };

  const onPreset = (event: ChangeEvent<HTMLSelectElement>) => {
    const p = PRESETS.find((x) => presetKey(x.name) === event.target.value);
    if (!p) return;
    if (locked) void resizeLocked({ preset: { width: p.width, height: p.height } });
    else void resizeUnlocked({ width: p.width, height: p.height });
  };

  const commitWidth = (parsed: number) => {
    if (locked) void resizeLocked({ width: parsed });
    else void resizeUnlocked({ width: parsed });
  };
  const commitHeight = (parsed: number) => {
    if (locked) void resizeLocked({ height: parsed });
    else void resizeUnlocked({ height: parsed });
  };
  const commitCell = (parsed: number) => {
    void resizeLocked({ cell: clampNum(parsed, CELL_MIN, CELL_MAX) });
  };

  const stepWidth = (dir: number) => {
    if (locked) void resizeLocked({ cell: cell + dir * EIGHTH });
    else void resizeUnlocked({ width: Math.max(block, cols + dir * block) * cell + 2 * borderTotal });
  };
  const stepHeight = (dir: number) => {
    if (locked) void resizeLocked({ cell: cell + dir * EIGHTH });
    else void resizeUnlocked({ height: Math.max(block, rows + dir * block) * cell + 2 * borderTotal });
  };
  const stepCell = (dir: number) => {
    void resizeLocked({ cell: cell + dir * QUARTER });
  };

  return (
    <section className="sz-root" data-testid="sizing-panel">
      <header className="sz-head">
        <h2 className="sz-title">Sizing</h2>
        <span className="sz-rule" />
        <span className="sz-pill">finished sizes</span>
      </header>

      <label className="sz-field">
        <span className="sz-label">Standard size</span>
        <select className="sz-select" data-testid="size-preset" value={presetVal} onChange={onPreset}>
          <option value="custom">Custom size</option>
          {PRESETS.map((p) => (
            <option key={p.name} value={presetKey(p.name)}>
              {`${p.name} — ${p.width / 8} × ${p.height / 8}`}
            </option>
          ))}
        </select>
      </label>

      <div className="sz-wh">
        <div className="sz-field">
          <span className="sz-label">
            Width <span className="sz-unit">· in</span>
          </span>
          <div className="sz-inrow">
            <Stepper glyph="−" title={stepTitle} ariaLabel="Narrower" onClick={() => stepWidth(-1)} />
            <FractionField
              testid="size-width"
              valueEighths={finishedWidth}
              ariaLabel="Finished width in inches"
              errorCopy="Try inches like 75 or 75 1/2"
              onCommit={commitWidth}
              onPreview={(v) => setPreview(v == null ? null : { axis: "width", value: v })}
            />
            <Stepper glyph="+" title={stepTitle} ariaLabel="Wider" onClick={() => stepWidth(1)} />
          </div>
        </div>

        <Tooltip tip={lockTitle}>
          <button
            type="button"
            className={`sz-lock${locked ? " sz-lock--on" : ""}`}
            data-testid="proportion-lock"
            aria-pressed={locked}
            aria-label={locked ? "Proportion lock on" : "Proportion lock off"}
            onClick={toggleLock}
          >
            {locked ? (
              <svg width="21" height="23" viewBox="0 0 21 23" aria-hidden="true">
                <path d="M6 10.5V7a4.5 4.5 0 0 1 9 0v3.5" fill="none" stroke="currentColor" strokeWidth="2.4" />
                <rect x="3" y="10.5" width="15" height="10.5" rx="2.5" fill="currentColor" />
              </svg>
            ) : (
              <svg width="23" height="23" viewBox="0 0 23 23" aria-hidden="true">
                <path d="M9 10.5V6a4.5 4.5 0 0 1 9 0v1.5" fill="none" stroke="currentColor" strokeWidth="2.4" />
                <rect x="3" y="10.5" width="15" height="10.5" rx="2.5" fill="currentColor" />
              </svg>
            )}
          </button>
        </Tooltip>

        <div className="sz-field">
          <span className="sz-label">
            Height <span className="sz-unit">· in</span>
          </span>
          <div className="sz-inrow">
            <Stepper glyph="−" title={stepTitle} ariaLabel="Shorter" onClick={() => stepHeight(-1)} />
            <FractionField
              testid="size-height"
              valueEighths={finishedHeight}
              ariaLabel="Finished height in inches"
              errorCopy="Try inches like 90 or 90 1/2"
              onCommit={commitHeight}
              onPreview={(v) => setPreview(v == null ? null : { axis: "height", value: v })}
            />
            <Stepper glyph="+" title={stepTitle} ariaLabel="Taller" onClick={() => stepHeight(1)} />
          </div>
        </div>
      </div>

      <p className="sz-hint">{lockModeLine}</p>

      {askText !== null && gotText !== null ? (
        <div className="sz-req">
          <div className="sz-req-cols">
            <div className="sz-req-col">
              <div className="sz-req-cap">You asked for</div>
              <div className="sz-req-ask" data-testid="size-asked">
                {askText}
              </div>
            </div>
            <span className="sz-req-arrow">→</span>
            <div className="sz-req-col">
              <div className="sz-req-cap">You’ll get</div>
              <div className="sz-req-got" data-testid="size-got">
                {gotText}
              </div>
            </div>
          </div>
          <div className="sz-req-note">
            You can’t sew part of a block, so QREP picked the closest whole-block size. Nudge a
            border to land exactly.
          </div>
        </div>
      ) : null}

      <div className="sz-cellrow">
        <div className="sz-field">
          <span className="sz-label">
            Square size <span className="sz-unit">· in</span>
          </span>
          <div className="sz-inrow">
            <Stepper
              glyph="−"
              title="A quarter inch smaller"
              ariaLabel="A quarter inch smaller"
              testid="size-cell-down"
              onClick={() => stepCell(-1)}
            />
            <FractionField
              testid="size-cell"
              valueEighths={cell}
              ariaLabel="Square size in inches"
              errorCopy="Try a size like 1 1/2 or 2"
              onCommit={commitCell}
            />
            <Stepper
              glyph="+"
              title="A quarter inch bigger"
              ariaLabel="A quarter inch bigger"
              testid="size-cell-up"
              onClick={() => stepCell(1)}
            />
          </div>
        </div>
        <p className="sz-cut">
          Cut squares at <strong>{cutText}″</strong> — ¼″ seams included.
        </p>
      </div>

      <div className="sz-borders">
        <div className="sz-borders-head">
          <span className="sz-label">
            Borders <span className="sz-unit">· in</span>
          </span>
          <button
            type="button"
            className="sz-addborder"
            data-testid="border-add"
            onClick={() => void addBorder()}
          >
            ＋ add a border
          </button>
        </div>
        {bands.map((band, i) => (
          <div className="sz-brow" data-testid={`border-row-${i}`} key={i}>
            <span
              className="sz-bswatch"
              style={{ background: colorById.get(band.fabric_id) ?? "#ccc" }}
              aria-hidden="true"
            />
            <select
              className="sz-bselect"
              data-testid={`border-fabric-${i}`}
              value={band.fabric_id}
              aria-label={`Border ${i + 1} fabric`}
              onChange={(event) => void setBorderFabric(i, event.target.value)}
            >
              {fabrics.map((f) => (
                <option key={f.id} value={f.id}>
                  {f.name}
                </option>
              ))}
            </select>
            <Stepper
              glyph="−"
              title="A quarter inch narrower"
              ariaLabel="A quarter inch narrower"
              onClick={() => void setBorderWidth(i, clampNum(band.width - QUARTER, BAND_MIN, BAND_MAX))}
            />
            <FractionField
              testid={`border-width-${i}`}
              valueEighths={band.width}
              ariaLabel={`Border ${i + 1} width in inches`}
              errorCopy="Try a width like 3 3/4"
              narrow
              onCommit={(parsed) => void setBorderWidth(i, clampNum(parsed, BAND_MIN, BAND_MAX))}
            />
            <Stepper
              glyph="+"
              title="A quarter inch wider"
              ariaLabel="A quarter inch wider"
              onClick={() => void setBorderWidth(i, clampNum(band.width + QUARTER, BAND_MIN, BAND_MAX))}
            />
            {bands.length > 1 ? (
              <button
                type="button"
                className="sz-bremove"
                data-testid={`border-remove-${i}`}
                title="Remove this border"
                aria-label={`Remove border ${i + 1}`}
                onClick={() => void removeBorder(i)}
              >
                ✕
              </button>
            ) : null}
          </div>
        ))}
      </div>

      <div className="sz-eq" data-testid="equation-box">
        <div className="sz-eq-row">
          <span>Squares</span>
          <strong>{eqSquares}</strong>
        </div>
        <div className="sz-eq-row">
          <span>Borders</span>
          <strong>{eqBorder}</strong>
        </div>
        <div className="sz-eq-total">
          <span>Finished quilt</span>
          <strong>{eqTotal}</strong>
        </div>
        <div className="sz-blocks" data-testid="blocks-line">
          {blocksLine}
        </div>
      </div>

      <style>{SZ_CSS}</style>
    </section>
  );
}

const SZ_CSS = `
.sz-root { background: var(--card); border: 1px solid var(--line); border-radius: 16px; box-shadow: 0 2px 10px var(--shadow); padding: 18px; display: flex; flex-direction: column; gap: 15px; font: 400 16.5px var(--sans, sans-serif); color: var(--ink2); }
.sz-head { display: flex; align-items: center; gap: 12px; }
.sz-title { margin: 0; font: 700 21px var(--serif, serif); color: var(--denim); }
.sz-rule { flex: 1; border-top: 2px dashed var(--line2); }
.sz-pill { font-size: 12.5px; color: var(--mut); border: 1px solid var(--pillLn); border-radius: 999px; padding: 4px 11px; background: var(--pill); }
.sz-field { display: flex; flex-direction: column; min-width: 0; }
.sz-label { display: block; font-size: 14.5px; color: var(--mut); margin-bottom: 6px; }
.sz-unit { color: var(--faint); }
.sz-select { width: 100%; padding: 12px 13px; font-size: 16.5px; font-family: var(--sans, sans-serif); color: var(--ink); background: var(--card); border: 1.5px solid var(--line2); border-radius: 10px; cursor: pointer; }
.sz-select:focus { border-color: var(--accent); box-shadow: 0 0 0 3px rgba(165, 80, 47, 0.16); outline: none; }
.sz-wh { display: grid; grid-template-columns: 1fr auto 1fr; gap: 8px; align-items: end; }
.sz-inrow { display: flex; gap: 5px; }
.sz-input { width: 100%; min-width: 0; text-align: center; font: 600 17.5px var(--serif, serif); color: var(--ink); background: var(--card); border: 1.5px solid var(--line2); border-radius: 10px; padding: 6px 2px; }
.sz-input--narrow { width: 64px; flex: none; padding: 12px 2px; font-size: 17px; }
.sz-input:focus { border-color: var(--accent); box-shadow: 0 0 0 3px rgba(165, 80, 47, 0.16); outline: none; }
.sz-step { width: 36px; height: 50px; flex: none; font-size: 21px; line-height: 1; color: var(--ink2); background: var(--card2); border: 1.5px solid var(--line2); border-radius: 10px; cursor: pointer; }
.sz-step:hover { background: var(--card3); }
.sz-lock { width: 44px; height: 50px; flex: none; border-radius: 10px; cursor: pointer; display: flex; align-items: center; justify-content: center; background: var(--card2); border: 1.5px solid var(--line2); color: var(--mut); }
.sz-lock--on { background: var(--sageBg); border-color: var(--accent); color: var(--accent); }
.sz-hint { margin: -5px 0 0; font-size: 13.5px; color: var(--faint); line-height: 1.5; }
.sz-req { background: var(--sageBg); border: 1px solid var(--sageLn); border-radius: 12px; padding: 12px 14px; }
.sz-req-cols { display: flex; gap: 10px; align-items: stretch; }
.sz-req-col { flex: 1; text-align: center; }
.sz-req-cap { font-size: 12.5px; color: var(--mut); margin-bottom: 2px; }
.sz-req-ask { font: 600 17px var(--serif, serif); color: var(--ink2); }
.sz-req-got { font: 700 17px var(--serif, serif); color: var(--sage); }
.sz-req-arrow { display: flex; align-items: center; color: var(--sage); font-size: 17px; }
.sz-req-note { font-size: 13.5px; color: var(--ink2); line-height: 1.5; margin-top: 8px; }
.sz-cellrow { display: grid; grid-template-columns: 1fr 1fr; gap: 13px; align-items: end; }
.sz-cut { margin: 0 0 5px; font-size: 14px; color: var(--mut); line-height: 1.5; }
.sz-cut strong { color: var(--ink2); }
.sz-borders-head { display: flex; align-items: baseline; justify-content: space-between; gap: 10px; margin-bottom: 6px; }
.sz-addborder { background: none; border: none; padding: 2px 0; font: 600 14px var(--sans, sans-serif); color: var(--accent); cursor: pointer; }
.sz-brow { display: flex; gap: 5px; align-items: center; margin-bottom: 8px; }
.sz-bswatch { width: 34px; height: 50px; flex: none; border-radius: 9px; border: 1px solid var(--line2); box-shadow: inset 0 -2px 5px rgba(0, 0, 0, 0.07); }
.sz-bselect { flex: 1; min-width: 0; padding: 12px 8px; font-size: 14.5px; font-family: var(--sans, sans-serif); color: var(--ink); background: var(--card); border: 1.5px solid var(--line2); border-radius: 10px; cursor: pointer; }
.sz-bremove { width: 30px; height: 50px; flex: none; font-size: 17px; color: var(--faint); background: none; border: none; cursor: pointer; }
.sz-bremove:hover { color: var(--accent); }
.sz-eq { background: var(--card3); border: 1px dashed var(--line2); border-radius: 12px; padding: 13px 15px; display: flex; flex-direction: column; gap: 6px; }
.sz-eq-row { display: flex; justify-content: space-between; gap: 12px; font-size: 15.5px; color: var(--ink2); }
.sz-eq-row strong { font-weight: 600; }
.sz-eq-total { border-top: 1px dashed var(--line2); margin-top: 2px; padding-top: 8px; display: flex; justify-content: space-between; align-items: baseline; gap: 12px; }
.sz-eq-total span { font-size: 14px; color: var(--mut); }
.sz-eq-total strong { font: 700 19px var(--serif, serif); color: var(--accent); }
.sz-blocks { font-size: 13.5px; color: var(--faint); line-height: 1.5; }
`;
