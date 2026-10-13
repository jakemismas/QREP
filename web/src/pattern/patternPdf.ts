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
 * never the engine's raw message. A refusal gets its own status, because
 * the same quilt is refused again: the screen offers no Retry for it.
 *
 * An engine restart is never a failure. An engine Retry restarts the engine
 * (Your pattern's, or the header's engine chip, which calls engine.retry
 * directly), and the restart rejects every waiting call; both classes send a
 * still-current request again on their own, once per rejection, so either
 * Retry recovers Your pattern.
 *
 * A failed call's Retry (retryPattern) sends the call again, to the same
 * worker after a bridge error. A failure of the worker itself would meet the
 * same broken worker, so after one the Retry restarts the engine first and
 * the request goes to the fresh worker.
 */
import { parsePatternResult } from "../engine/contract";
import type { PatternSummary } from "../engine/contract";
import { EngineError } from "../engine/rpc";

/** Engine.call, narrowed to what these calls need. */
export type EngineCall = (method: string, ...args: unknown[]) => Promise<unknown>;

export const PATTERN_FAILED = "Your pattern could not be made this time. Try again.";
export const SAVE_FAILED = "Your browser did not save the pattern file. Try again.";

type Made =
  | { ok: true; pdfB64: string; summary: PatternSummary }
  | { ok: false; message: string; refused: boolean; workerDown: boolean };

// rpc.ts restart() rejects every queued and in-flight call with exactly this
// kind and message; the engine itself never answers with it.
const RESTART_KIND = "worker";
const RESTART_MESSAGE = "the engine was restarted";

/** True for the rejection an engine restart gives a call that was waiting. */
export function isEngineRestart(err: unknown): boolean {
  return err instanceof EngineError && err.kind === RESTART_KIND && err.message === RESTART_MESSAGE;
}

// The bridge wraps every engine exception in its own envelope, and its one
// kind "internal" error always carries this sentence (qrep/bridge.py, the
// _envelope catch-all). Kind "internal" with any other message comes from
// the plumbing around the bridge: worker.ts's catch in serve() ("engine call
// failed in the worker", or the vision load's message) and rpc.ts's result
// without an envelope ("no envelope").
const BRIDGE_INTERNAL_MESSAGE = "internal engine error; see the browser console log";

/** True when the worker itself failed the call, not the engine inside it:
 * kind "internal" from the worker or the client rather than the bridge, or
 * kind "worker" (worker.ts: "engine is not booted") other than a restart's
 * rejection. Read as a worker failure, an unknown internal message costs
 * only a restart, while the reverse would resend to a broken worker. */
export function isWorkerFailure(err: unknown): boolean {
  if (!(err instanceof EngineError) || isEngineRestart(err)) return false;
  if (err.kind === "worker") return true;
  return err.kind === "internal" && err.message !== BRIDGE_INTERNAL_MESSAGE;
}

/** `current` says whether the caller still wants this request: a restart
 * sends a current request again, and a replaced one stops at its rejection. */
async function makePattern(
  call: EngineCall,
  modelJson: string,
  current: () => boolean,
): Promise<Made> {
  let raw: unknown;
  for (;;) {
    try {
      raw = await call("export_pattern", modelJson);
      break;
    } catch (err) {
      if (isEngineRestart(err) && current()) continue;
      return { ok: false, message: PATTERN_FAILED, refused: false, workerDown: isWorkerFailure(err) };
    }
  }
  try {
    const result = parsePatternResult(raw);
    if (result.outcome === "pattern_ready") {
      // parsePatternResult already required both on a ready pattern.
      return { ok: true, pdfB64: result.pdf_b64 as string, summary: result.summary as PatternSummary };
    }
    return {
      ok: false,
      message: (result.reason as { message: string }).message,
      refused: true,
      workerDown: false,
    };
  } catch {
    return { ok: false, message: PATTERN_FAILED, refused: false, workerDown: false };
  }
}

export type PdfStatus = "idle" | "busy" | "failed" | "refused";

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
  private down = false;

  constructor(options: PdfOptions) {
    this.options = options;
  }

  get view(): PdfView {
    return this.current;
  }

  /** True while the shown failure is the worker's own (isWorkerFailure). */
  get workerDown(): boolean {
    return this.down;
  }

  /** Make the pattern and save it; a no-op while one is being made. */
  start(modelJson: string, filename: string): Promise<void> {
    if (this.current.status === "busy") return Promise.resolve();
    return this.make(modelJson, filename);
  }

  /** Run the last request again. */
  retry(): Promise<void> {
    if (this.last === null) return Promise.resolve();
    return this.start(this.last.modelJson, this.last.filename);
  }

  private async make(modelJson: string, filename: string): Promise<void> {
    this.last = { modelJson, filename };
    const run = ++this.run;
    this.down = false;
    this.set({ status: "busy", message: null });
    const made = await makePattern(this.options.call, modelJson, () => run === this.run);
    if (run !== this.run) return;
    if (!made.ok) {
      this.down = made.workerDown;
      this.set({ status: made.refused ? "refused" : "failed", message: made.message });
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

  /** Back to idle, dropping any pattern still being made. */
  reset(): void {
    this.run += 1;
    this.last = null;
    this.down = false;
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
  | { status: "failed" | "refused"; message: string };

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
  private down = false;

  constructor(options: SummaryOptions) {
    this.options = options;
  }

  get view(): SummaryView {
    return this.current;
  }

  /** True while the shown failure is the worker's own (isWorkerFailure). */
  get workerDown(): boolean {
    return this.down;
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
    this.down = false;
    this.set(SUMMARY_IDLE);
  }

  private async fetch(modelJson: string): Promise<void> {
    const run = ++this.run;
    this.down = false;
    this.set({ status: "loading" });
    const made = await makePattern(this.options.call, modelJson, () => run === this.run);
    if (run !== this.run) return;
    this.down = !made.ok && made.workerDown;
    this.set(
      made.ok
        ? { status: "ready", summary: made.summary }
        : { status: made.refused ? "refused" : "failed", message: made.message },
    );
  }

  private set(view: SummaryView): void {
    this.current = view;
    this.options.onChange?.(view);
  }
}

export interface RetryTargets {
  loader: PatternSummaryLoader;
  pdf: PatternPdfController;
  /** engine.retry: terminate the worker and boot a fresh one. */
  restart: () => void;
}

/**
 * Retry for a failed call on Your pattern: `which` names the failure the
 * error line shows. After a bridge error the call goes again to the same
 * worker. After a failure of the worker itself, the engine restarts first,
 * so the call queues for the fresh worker instead of meeting the broken one;
 * a summary that failed too goes again with it, as an engine Retry sends it,
 * because nothing else would ask for it once the engine is back.
 */
export function retryPattern({ loader, pdf, restart }: RetryTargets, which: "pdf" | "summary"): void {
  if (!pdf.workerDown && !loader.workerDown) {
    if (which === "pdf") void pdf.retry();
    else loader.retry();
    return;
  }
  restart();
  if (which === "pdf") void pdf.retry();
  if (loader.view.status === "failed") loader.retry();
}
