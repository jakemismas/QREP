/**
 * Your pattern's engine calls (C2a, issue #96), framework-free so vitest
 * drives them without a DOM. Both ask bridge.export_pattern for the pattern
 * with the model JSON alone: the engine picks the method, so the call takes
 * no strategy (SPEC.md section 12.1).
 *
 * PatternPdfController makes the PDF on request and hands it to a save
 * callback; PatternSummaryLoader fetches the summary the screen shows
 * (method line, census letters and names), since no lighter bridge call
 * returns it. A failure is always a plain sentence: a refused outcome shows
 * its reason, which the engine writes for people, and anything else (an
 * engine error, a result without a valid outcome) shows PATTERN_FAILED,
 * never the engine's raw message.
 */
import { parsePatternResult } from "../engine/contract";
import type { PatternSummary } from "../engine/contract";

/** Engine.call, narrowed to what these calls need. */
export type EngineCall = (method: string, ...args: unknown[]) => Promise<unknown>;

export const PATTERN_FAILED = "Your pattern could not be made this time. Try again.";
export const SAVE_FAILED = "Your browser did not save the pattern file. Try again.";

type Made = { ok: true; pdfB64: string; summary: PatternSummary } | { ok: false; message: string };

async function makePattern(call: EngineCall, modelJson: string): Promise<Made> {
  let raw: unknown;
  try {
    raw = await call("export_pattern", modelJson);
  } catch {
    return { ok: false, message: PATTERN_FAILED };
  }
  try {
    const result = parsePatternResult(raw);
    if (result.outcome === "pattern_ready") {
      // parsePatternResult already required both on a ready pattern.
      return { ok: true, pdfB64: result.pdf_b64 as string, summary: result.summary as PatternSummary };
    }
    return { ok: false, message: (result.reason as { message: string }).message };
  } catch {
    return { ok: false, message: PATTERN_FAILED };
  }
}

export type PdfStatus = "idle" | "busy" | "failed";

export interface PdfView {
  status: PdfStatus;
  message: string | null;
}

const PDF_IDLE: PdfView = { status: "idle", message: null };

export interface PdfOptions {
  call: EngineCall;
  /** Receives the PDF as the engine's base64 and the file name to save it under. */
  save: (pdfB64: string, filename: string) => void;
  onChange?: (view: PdfView) => void;
}

export class PatternPdfController {
  private readonly options: PdfOptions;
  private current: PdfView = PDF_IDLE;
  private last: { modelJson: string; filename: string } | null = null;
  // Bumped by every start and reset, so a result that lands after a reset
  // (Home, another quilt) is dropped instead of saved.
  private run = 0;

  constructor(options: PdfOptions) {
    this.options = options;
  }

  get view(): PdfView {
    return this.current;
  }

  /** Make the pattern and save it; a no-op while one is being made. */
  async start(modelJson: string, filename: string): Promise<void> {
    if (this.current.status === "busy") return;
    this.last = { modelJson, filename };
    const run = ++this.run;
    this.set({ status: "busy", message: null });
    const made = await makePattern(this.options.call, modelJson);
    if (run !== this.run) return;
    if (!made.ok) {
      this.set({ status: "failed", message: made.message });
      return;
    }
    try {
      this.options.save(made.pdfB64, filename);
    } catch {
      this.set({ status: "failed", message: SAVE_FAILED });
      return;
    }
    this.set(PDF_IDLE);
  }

  /** Run the last request again. */
  retry(): Promise<void> {
    if (this.last === null) return Promise.resolve();
    return this.start(this.last.modelJson, this.last.filename);
  }

  /** Back to idle, dropping any pattern still being made. */
  reset(): void {
    this.run += 1;
    this.last = null;
    this.set(PDF_IDLE);
  }

  private set(view: PdfView): void {
    this.current = view;
    this.options.onChange?.(view);
  }
}

export type SummaryView =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "ready"; summary: PatternSummary }
  | { status: "failed"; message: string };

const SUMMARY_IDLE: SummaryView = { status: "idle" };

export interface SummaryOptions {
  call: EngineCall;
  onChange?: (view: SummaryView) => void;
}

export class PatternSummaryLoader {
  private readonly options: SummaryOptions;
  private current: SummaryView = SUMMARY_IDLE;
  private modelJson: string | null = null;
  // Bumped by every request and clear: only the newest model's summary lands.
  private run = 0;

  constructor(options: SummaryOptions) {
    this.options = options;
  }

  get view(): SummaryView {
    return this.current;
  }

  /** Fetch the summary for a model, once: the same model again is a no-op. */
  load(modelJson: string): void {
    if (modelJson === this.modelJson && this.current.status !== "idle") return;
    this.modelJson = modelJson;
    void this.fetch(modelJson);
  }

  retry(): void {
    if (this.modelJson !== null) void this.fetch(this.modelJson);
  }

  clear(): void {
    this.run += 1;
    this.modelJson = null;
    this.set(SUMMARY_IDLE);
  }

  private async fetch(modelJson: string): Promise<void> {
    const run = ++this.run;
    this.set({ status: "loading" });
    const made = await makePattern(this.options.call, modelJson);
    if (run !== this.run) return;
    this.set(
      made.ok
        ? { status: "ready", summary: made.summary }
        : { status: "failed", message: made.message },
    );
  }

  private set(view: SummaryView): void {
    this.current = view;
    this.options.onChange?.(view);
  }
}
