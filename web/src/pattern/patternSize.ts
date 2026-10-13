/**
 * The size control and the two fabric widths on Your pattern (C2b, issue
 * #148), framework-free so vitest drives them without a DOM.
 *
 * Every number here comes from the engine: bridge.size_pattern sizes the
 * quilt (qrep/model/sizing.py, the one sizing module; SPEC.md section 6.3),
 * bridge.presets() supplies the chips, and the export_pattern summary gives
 * the finished size and the amounts. This module only builds requests and
 * prints the engine's numbers, so it holds no sizing or yardage math
 * (criterion P13; REBASELINE.md W23).
 *
 * PatternSizer always sizes the quilt as it was opened, never a sized copy,
 * because sizing a sized model rounds its borders again (SPEC.md section
 * 6.3). The two widths are settings the engine reads, so they ride on the
 * model it is sent: the sized model when there is one, else the opened one.
 */
import { parseSizeResult } from "../engine/contract";
import type { SizeBasis, SizeRequest } from "../engine/contract";
import type { QuiltModel } from "../model/types";
import { parseSizeInput } from "../model/sizeEntry";
import type { SizeUnit } from "../model/sizeEntry";
import { formatEighths } from "../model/units";
import type { PatternSource } from "../state/pattern";
import { isEngineRestart } from "./patternPdf";
import type { EngineCall } from "./patternPdf";

export const SIZE_FAILED = "That size could not be set. Check the numbers and try again.";

// ------------------------------------------------------------------ text

/** formatEighths writes an inch mark; the pattern writes "in" (MATH.md F13). */
function bare(eighths: number): string {
  return formatEighths(eighths).replace(/"$/, "");
}

/** A finished size, width first; a side left out says which side is given. */
export function sizeText(width: number | null, height: number | null): string {
  if (width !== null && height !== null) return `${bare(width)} x ${bare(height)} in`;
  if (width !== null) return `${bare(width)} in wide`;
  if (height !== null) return `${bare(height)} in high`;
  return "";
}

/** One length in inches, such as a fabric width. */
export function inchText(eighths: number): string {
  return `${bare(eighths)} in`;
}

/**
 * The engine's yards as a mixed fraction. The summary carries the purchase
 * as a number of yards that is already a whole count of the purchase
 * increment, so this prints that number and computes nothing: eighths of a
 * yard hold every 1/4 and 1/8 yd amount exactly.
 */
export function yardsText(yards: number): string {
  return `${bare(Math.round(yards * 8))} yd`;
}

// ---------------------------------------------------------------- widths

export interface WidthChoice {
  eighths: number;
  label: string;
  isDefault: boolean;
}

// The defaults are MATH.md section 1.3's U (40 in) and B (42 in), with BW
// (108 in) as the backing's wide-back choice; each is a Settings default in
// qrep/model/schema.py, so the engine applies the same value when unset.
export const STRIP_WIDTHS: readonly WidthChoice[] = [
  { eighths: 320, label: "40 in (default)", isDefault: true },
  { eighths: 336, label: "42 in", isDefault: false },
  { eighths: 352, label: "44 in", isDefault: false },
];

export const BACKING_WIDTHS: readonly WidthChoice[] = [
  { eighths: 336, label: "42 in (default)", isDefault: true },
  { eighths: 352, label: "44 in", isDefault: false },
  { eighths: 864, label: "108 in wide back", isDefault: false },
];

/** The widths you chose; null keeps the model's own setting. */
export interface Widths {
  strip: number | null;
  backing: number | null;
}

export const NO_WIDTHS: Widths = { strip: null, backing: null };

// Settings refuses a wide-back width at or below the backing width
// (qrep/model/schema.py, _wide_back_is_wider), and the wide back defaults to
// 108 in. A 108 in backing therefore moves the wide back to MATH.md section
// 1.3's other common width, 118 in, so the model stays valid.
const WIDE_BACK_108 = 864;
const WIDE_BACK_118 = 944;

/** The model with your widths in its settings (Settings.wof and backing_width). */
export function withWidths(model: QuiltModel, widths: Widths): QuiltModel {
  if (widths.strip === null && widths.backing === null) return model;
  const settings: Record<string, unknown> = { ...(model.settings ?? {}) };
  if (widths.strip !== null) settings.wof = widths.strip;
  if (widths.backing !== null) {
    settings.backing_width = widths.backing;
    if (widths.backing >= WIDE_BACK_108) settings.wide_back_width = WIDE_BACK_118;
  }
  return { ...model, settings };
}

// ---------------------------------------------------------------- entry

export interface Preset {
  name: string;
  width: number;
  height: number;
}

/** bridge.presets()'s table, in its order; any other shape gives no chips. */
export function parsePresets(raw: unknown): Preset[] {
  const list = (raw as { presets?: unknown } | null)?.presets;
  if (!Array.isArray(list)) return [];
  const valid = list.every(
    (item) =>
      typeof item === "object" &&
      item !== null &&
      typeof (item as Preset).name === "string" &&
      Number.isInteger((item as Preset).width) &&
      Number.isInteger((item as Preset).height),
  );
  return valid ? list.map(({ name, width, height }: Preset) => ({ name, width, height })) : [];
}

/** A typed side: eighths, null when blank, "invalid" when it is no length. */
export function parseSide(text: string, unit: SizeUnit): number | null | "invalid" {
  if (!text.trim()) return null;
  const eighths = parseSizeInput(text, unit);
  return eighths !== null && eighths > 0 ? eighths : "invalid";
}

/** A typed size request from the sides you set, or null with no side. */
export function typedRequest(width: number | null, height: number | null): SizeRequest | null {
  if (width === null && height === null) return null;
  const request: SizeRequest = { source: "typed" };
  if (width !== null) request.width = width;
  if (height !== null) request.height = height;
  return request;
}

export function presetRequest(name: string): SizeRequest {
  return { source: "preset", preset: name };
}

// ----------------------------------------------------------------- sizer

/** A size the engine set: the sized model, its basis, and the preset you picked. */
export interface Sized {
  model: QuiltModel;
  basis: SizeBasis;
  preset: string | null;
}

export interface SizerView {
  status: "idle" | "busy" | "failed";
  /** The newest size that landed; a failed request keeps the one before it. */
  sized: Sized | null;
  message: string | null;
}

export const SIZER_IDLE: SizerView = { status: "idle", sized: null, message: null };

export interface SizerOptions {
  call: EngineCall;
  onChange?: (view: SizerView) => void;
}

export class PatternSizer {
  private readonly options: SizerOptions;
  private current: SizerView = SIZER_IDLE;
  // Bumped by every request and clear: only the newest request lands.
  private run = 0;

  constructor(options: SizerOptions) {
    this.options = options;
  }

  get view(): SizerView {
    return this.current;
  }

  /** Size the opened quilt (its JSON) for a request, with no re-read. */
  async apply(baseJson: string, request: SizeRequest, preset: string | null): Promise<void> {
    const run = ++this.run;
    const requestJson = JSON.stringify(request);
    this.set({ status: "busy", sized: this.current.sized, message: null });
    let sized: Sized;
    for (;;) {
      try {
        const result = parseSizeResult(
          await this.options.call("size_pattern", baseJson, requestJson),
        );
        sized = { model: result.model, basis: result.basis, preset };
        break;
      } catch (err) {
        // A restart rejects every waiting call; a request still wanted goes again.
        if (isEngineRestart(err) && run === this.run) continue;
        if (run !== this.run) return;
        this.set({ status: "failed", sized: this.current.sized, message: SIZE_FAILED });
        return;
      }
    }
    if (run !== this.run) return;
    this.set({ status: "idle", sized, message: null });
  }

  /** Forget every size, dropping any request still on its way. */
  clear(): void {
    this.run += 1;
    this.set(SIZER_IDLE);
  }

  private set(view: SizerView): void {
    this.current = view;
    this.options.onChange?.(view);
  }
}

// ------------------------------------------------------------- size line

type RecordedBasis = Pick<SizeBasis, "source" | "requested_width" | "requested_height">;

/** The model's own size basis, which the engine writes (qrep/model/schema.py). */
function modelBasis(model: QuiltModel): RecordedBasis | null {
  const basis = (model as QuiltModel & { size_basis?: Partial<RecordedBasis> | null }).size_basis;
  if (!basis || typeof basis.source !== "string") return null;
  return {
    source: basis.source,
    requested_width: basis.requested_width ?? null,
    requested_height: basis.requested_height ?? null,
  };
}

export interface SizeLine {
  kind: "default" | "typed" | "preset";
  label: string;
  /** The finished size the pattern prints. */
  achieved: string;
  /** For a default: where the size came from and the square size assumed (PS-09). */
  note: string | null;
  /** The size you asked for, shown only when the achieved size misses it. */
  asked: string | null;
}

function missed(requested: number | null, achieved: number): boolean {
  return requested !== null && requested !== achieved;
}

/**
 * What the size line says. `finished` is the summary's finished size, the
 * one the PDF prints. A size you set shows your request beside it when they
 * differ; any other size is labeled a default, never a measurement (PS-09).
 */
export function sizeLine(
  model: QuiltModel,
  finished: { width: number; height: number },
  sized: Sized | null,
  source: PatternSource,
): SizeLine {
  const achieved = sizeText(finished.width, finished.height);
  const basis = sized?.basis ?? modelBasis(model);
  const chosen = basis?.source ?? "default";
  if (basis && (chosen === "typed" || chosen === "preset")) {
    const asked =
      missed(basis.requested_width, finished.width) || missed(basis.requested_height, finished.height)
        ? sizeText(basis.requested_width, basis.requested_height)
        : null;
    const label = chosen === "preset" && sized?.preset ? `${sized.preset} size` : "Your size";
    return { kind: chosen, label, achieved, note: null, asked };
  }
  const square = inchText(model.center.cell_size);
  const note =
    source === "photo"
      ? `Estimated from your photo, with ${square} squares. Set your size below.`
      : `The sample pattern as drawn, with ${square} squares. Set your size below.`;
  return { kind: "default", label: "Default size", achieved, note, asked: null };
}

/**
 * The quilt the canvas draws, true to scale: the sized quilt once you set a
 * size, else the read's own model, else the opened one. Sizing changes the
 * square and the borders, never the grid, so the read's square confidences
 * still line up with the sized quilt and its flagged squares stay outlined.
 */
export function canvasModel(
  sized: QuiltModel | null,
  opened: QuiltModel,
  read: QuiltModel | null,
): QuiltModel {
  if (sized === null) return read ?? opened;
  const confidence = read?.center.cell_confidence;
  const sameGrid = read?.center.rows === sized.center.rows && read?.center.cols === sized.center.cols;
  if (!confidence || !sameGrid) return sized;
  return { ...sized, center: { ...sized.center, cell_confidence: confidence } };
}
