/*
 * Pattern state (C1a, issue #146): the seam strategy, the three strategy
 * plans, the engine exports, copy-my-settings and the round-trip demo. Every
 * one of them reads the model from model.tsx's plain state.
 *
 * C2a (issue #96) adds Your pattern: which screen shows the open quilt (the
 * editor, or Your pattern for the sample or a photo read), the pattern
 * summary that screen shows, and its one pattern PDF. Both engine calls run
 * through the framework-free controllers in pattern/patternPdf.ts.
 *
 * C2b (issue #148) adds the size you set and the two fabric widths. Your
 * pattern makes its summary and PDF from the opened quilt sized by
 * bridge.size_pattern, with your widths in its settings; the opened quilt
 * itself, the editor's model, never changes, so every size starts from it.
 */
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import { useEngine } from "../engine/useEngine";
import type { Engine } from "../engine/useEngine";
import { EngineError } from "../engine/rpc";
import type { SizeRequest } from "../engine/contract";
import type { ModelSummary, QuiltModel } from "../model/types";
import type { SeamStrategy } from "../model/seams";
import { useToast } from "../ui";
import { PatternPdfController, PatternSummaryLoader, retryPattern } from "../pattern/patternPdf";
import type { PdfView, RetryAction, SummaryView } from "../pattern/patternPdf";
import { NO_WIDTHS, PatternSizer, SIZER_IDLE, parsePresets, withWidths } from "../pattern/patternSize";
import type { Preset, SizerView, Widths } from "../pattern/patternSize";
import type { ModelApi } from "./model";
import { buildSettingsSummary } from "./patternText";
import type { StrategyPlan } from "./patternText";

/** The three seam/plan strategies, in card order. */
const STRATEGIES: SeamStrategy[] = ["historical", "strip", "modern"];
export const DEFAULT_STRATEGY: SeamStrategy = "strip";
const NO_PLANS: Record<SeamStrategy, StrategyPlan | null> = {
  historical: null,
  strip: null,
  modern: null,
};

/** A user-initiated engine export (PARITY item 11). */
export type ExportKind = "cutlist-csv" | "cutlist-md" | "yardage" | "svg" | "pdf";

export interface RoundTripReport {
  dimsMatch: boolean;
  cellAccuracy: number;
}

/** Round-trip demo panel (render -> reverse -> compare) shown in the Pattern tab. */
export interface RoundTripApi {
  run: (level: 0 | 2) => Promise<void>;
  report: RoundTripReport | null;
}

/** Which screen shows the open quilt. */
export type PatternScreen = "editor" | "pattern";
/** Where the quilt on Your pattern came from: the sample, or a photo read. */
export type PatternSource = "sample" | "photo";

export interface YourPatternApi {
  screen: PatternScreen;
  source: PatternSource;
  /** Show the quilt that has just opened on Your pattern; call it right
   * after the open, so it binds to that quilt and to no later one. */
  showPattern: (source: PatternSource) => void;
  showEditor: () => void;
  summary: SummaryView;
  pdf: PdfView;
  savePdf: () => void;
  /** The error line's Retry: reboot a failed engine, or send a failed call
   * again (pattern/patternPdf.ts retryPattern). */
  retry: (which: RetryAction) => void;
  /** The quilt the summary and the PDF are made from: the opened quilt,
   * sized for the size you set, with your widths; null with no quilt. */
  model: QuiltModel | null;
  /** The size you set: the newest sized result, and a size on its way or refused. */
  sizer: SizerView;
  /** bridge.presets(), the size chips; empty until it lands. */
  presets: Preset[];
  /** The widths you chose; null keeps the model's own. */
  widths: Widths;
  /** Size the opened quilt for a request, with no re-read. */
  setSize: (request: SizeRequest, preset: string | null) => void;
  setWidths: (widths: Partial<Widths>) => void;
}

export interface PatternApi {
  seamStrategy: SeamStrategy;
  plans: Record<SeamStrategy, StrategyPlan | null>;
  setPatternActive: (active: boolean) => void;
  exportDownload: (kind: ExportKind) => Promise<void>;
  copySettings: () => Promise<boolean>;
  roundtrip: RoundTripApi;
  yourPattern: YourPatternApi;
}

/** What the provider that composes this module needs beyond the context value. */
export interface PatternState {
  api: PatternApi;
  setSeamStrategy: (strategy: SeamStrategy) => void;
  /** A new quilt opened: restore its strategy and drop the old quilt's plans. */
  resetPlans: (strategy: SeamStrategy) => void;
  /** Home: the default strategy, no plans, the Pattern tab closed, no round trip. */
  closePattern: () => void;
}

export function slugify(name: string): string {
  const slug = name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "");
  return slug || "quilt";
}

/** The pattern PDF's file name: the pattern name in kebab case. */
export function patternFileName(patternName: string): string {
  return `${slugify(patternName)}.pdf`;
}

/** The file name Download pattern (PDF) saves under: the engine's pattern
 * name, which is the validate summary's, else the model's own. */
export function patternPdfName(
  summary: Pick<ModelSummary, "name"> | null,
  model: Pick<QuiltModel, "metadata">,
): string {
  return patternFileName(summary?.name || model.metadata?.name || "");
}

export function base64ToArrayBuffer(b64: string): ArrayBuffer {
  const binary = atob(b64);
  const buffer = new ArrayBuffer(binary.length);
  const bytes = new Uint8Array(buffer);
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
  return buffer;
}

/** Save a blob under `filename` via a temporary anchor (same trick as saveToFile). */
function triggerBlob(data: BlobPart, filename: string, mime: string): void {
  const blob = new Blob([data], { type: mime });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  setTimeout(() => URL.revokeObjectURL(url), 10_000);
}

function execCommandCopy(text: string): boolean {
  try {
    const area = document.createElement("textarea");
    area.value = text;
    area.style.position = "fixed";
    area.style.opacity = "0";
    document.body.appendChild(area);
    area.focus();
    area.select();
    const ok = document.execCommand("copy");
    area.remove();
    return ok;
  } catch {
    return false;
  }
}

export const PatternContext = createContext<PatternApi | null>(null);

function savePatternFile(pdfB64: string, filename: string): void {
  triggerBlob(base64ToArrayBuffer(pdfB64), filename, "application/pdf");
}

export function usePatternState({
  model,
  name,
  summary,
  latestModel,
  opened,
  latestOpened,
  censusRequest,
  quietCensusWhen,
}: ModelApi): PatternState {
  const engine = useEngine();
  // ToastProvider rebuilds its value on every toast; keyed on that object,
  // the plans effect below would re-run after each toast.
  const { push } = useToast();
  const toast = useMemo(() => ({ push }), [push]);

  const engineRef = useRef<Engine>(engine);
  engineRef.current = engine;

  const [seamStrategy, setSeamStrategy] = useState<SeamStrategy>(DEFAULT_STRATEGY);
  const [plans, setPlans] = useState<Record<SeamStrategy, StrategyPlan | null>>(NO_PLANS);
  const [patternActive, setPatternActive] = useState(false);
  const [roundtripReport, setRoundtripReport] = useState<RoundTripReport | null>(null);

  // ---- plans (explicit, per model revision) ------------------------------
  //
  // PARITY item 1: card metrics and yardage are engine-authoritative. When the
  // Pattern tab is open the three strategies are planned once per model
  // revision; a plan whose model was superseded by a later edit is dropped.
  // Every edit produces a new model object, so the object is the revision,
  // and the revision advances the moment replaceModel runs (latestModel), not
  // when this effect next runs.

  const plannedRef = useRef<QuiltModel | null>(null);

  useEffect(() => {
    if (!patternActive || !model || model !== latestModel()) return;
    if (plannedRef.current === model) return; // already requested for this revision
    plannedRef.current = model;
    const json = JSON.stringify(model);
    const current = () => plannedRef.current === model && latestModel() === model;
    for (const strategy of STRATEGIES) {
      engineRef.current.call<StrategyPlan>("plan", json, strategy).then(
        (result) => {
          if (current()) {
            setPlans((prev) => ({ ...prev, [strategy]: result }));
          }
        },
        (err: unknown) => {
          if (!current()) return;
          const message =
            err instanceof EngineError ? err.message : "Couldn’t work out the plan, try again?";
          toast.push(message, "error");
        },
      );
    }
  }, [model, patternActive, toast, latestModel]);

  const resetPlans = useCallback((strategy: SeamStrategy) => {
    setSeamStrategy(strategy);
    setPlans(NO_PLANS);
    plannedRef.current = null;
  }, []);

  // ---- Your pattern (C2a) -------------------------------------------------

  // Your pattern shows one opened quilt: `bound` holds that open's count
  // (ModelApi.opened). showPattern binds the quilt that has just opened, so a
  // quilt opened any other way, say from the header's Open, has a later count
  // and goes to the editor, as it did before C2a. No flag waits for a future
  // open, so a slow sample load cannot send some other quilt to Your pattern.
  const [bound, setBound] = useState<number | null>(null);
  const boundRef = useRef<number | null>(null);
  const screen: PatternScreen = bound !== null && bound === opened ? "pattern" : "editor";
  const [source, setSource] = useState<PatternSource>("sample");
  const [summaryView, setSummaryView] = useState<SummaryView>({ status: "idle" });
  const [pdfView, setPdfView] = useState<PdfView>({ status: "idle", message: null });

  const engineCall = useCallback(
    (method: string, ...args: unknown[]) => engineRef.current.call<unknown>(method, ...args),
    [],
  );
  const loaderRef = useRef<PatternSummaryLoader | null>(null);
  loaderRef.current ??= new PatternSummaryLoader({ call: engineCall, onChange: setSummaryView });
  // The controller outlives renders, so its save reads the toast through a ref.
  const toastRef = useRef(toast);
  toastRef.current = toast;
  const pdfRef = useRef<PatternPdfController | null>(null);
  pdfRef.current ??= new PatternPdfController({
    call: engineCall,
    save: (pdfB64, filename) => {
      savePatternFile(pdfB64, filename);
      toastRef.current.push("Saved: your pattern file is ready.", "success");
    },
    onChange: setPdfView,
  });
  const [sizerView, setSizerView] = useState<SizerView>(SIZER_IDLE);
  const sizerRef = useRef<PatternSizer | null>(null);
  sizerRef.current ??= new PatternSizer({ call: engineCall, onChange: setSizerView });
  const [widths, setWidthsState] = useState<Widths>(NO_WIDTHS);
  const [presets, setPresets] = useState<Preset[]>([]);

  // While Your pattern shows the open quilt, a failed census is its error
  // line's to report, in a plain sentence with Retry; the editor keeps the
  // engine's message as a toast.
  useEffect(() => {
    quietCensusWhen(() => boundRef.current !== null && boundRef.current === latestOpened());
  }, [quietCensusWhen, latestOpened]);

  // A size and widths belong to the quilt they were set on.
  const forgetSettings = useCallback(() => {
    sizerRef.current?.clear();
    setWidthsState(NO_WIDTHS);
  }, []);

  const leavePattern = useCallback(() => {
    boundRef.current = null;
    setBound(null);
    loaderRef.current?.clear();
    pdfRef.current?.reset();
    forgetSettings();
  }, [forgetSettings]);

  // Another quilt opened: drop the bound quilt's summary and any pattern
  // still being made for it, so it is not saved under the new quilt.
  const seenOpenRef = useRef(opened);
  useEffect(() => {
    if (opened === seenOpenRef.current) return;
    seenOpenRef.current = opened;
    if (opened !== boundRef.current) leavePattern();
  }, [opened, leavePattern]);

  const showPattern = useCallback(
    (next: PatternSource) => {
      const open = latestOpened();
      boundRef.current = open;
      setBound(open);
      // The plans feed the editor's Pattern tab; Your pattern never asks for them.
      setPatternActive(false);
      setSource(next);
      loaderRef.current?.clear();
      pdfRef.current?.reset();
      forgetSettings();
    },
    [latestOpened, forgetSettings],
  );

  const showEditor = useCallback(() => {
    leavePattern();
  }, [leavePattern]);

  // One summary per model revision of the bound quilt; the loader drops a
  // replaced model's. A render that still shows Your pattern can run this
  // after a newer open (the header's Open), whose quilt goes to the editor
  // and must not cost an engine call.
  // The quilt the pattern is made from: the sized quilt when you set a size,
  // else the opened one, with your widths in its settings. A new size or a
  // new width makes a new object, which asks for the summary again below.
  const sized = sizerView.sized;
  const patternModel = useMemo(
    () => (model && screen === "pattern" ? withWidths(sized?.model ?? model, widths) : model),
    [model, screen, sized, widths],
  );

  useEffect(() => {
    if (screen !== "pattern" || !model || model !== latestModel()) return;
    if (boundRef.current !== latestOpened()) return;
    if (patternModel) loaderRef.current?.load(JSON.stringify(patternModel));
  }, [screen, model, patternModel, latestModel, latestOpened]);

  // The chips come from the bridge's one preset table (web-23; engine-22).
  // A failure leaves no chips; a typed size still works.
  const wantPresets = screen === "pattern" && presets.length === 0;
  useEffect(() => {
    if (!wantPresets) return;
    let live = true;
    engineRef.current.call<unknown>("presets").then(
      (raw) => {
        if (live) setPresets(parsePresets(raw));
      },
      () => undefined,
    );
    return () => {
      live = false;
    };
  }, [wantPresets]);

  // Every size starts from the opened quilt, never a sized copy, because
  // sizing a sized model rounds its borders again (SPEC.md section 6.3).
  const setSize = useCallback(
    (request: SizeRequest, preset: string | null) => {
      if (!model || boundRef.current === null || boundRef.current !== latestOpened()) return;
      void sizerRef.current?.apply(JSON.stringify(model), request, preset);
    },
    [model, latestOpened],
  );

  const setWidths = useCallback((next: Partial<Widths>) => {
    setWidthsState((prev) => ({ ...prev, ...next }));
  }, []);

  const savePdf = useCallback(() => {
    if (!patternModel) return;
    void pdfRef.current?.start(JSON.stringify(patternModel), patternPdfName(summary, patternModel));
  }, [patternModel, summary]);

  // Every Retry on Your pattern goes through retryPattern: it restarts the
  // engine for an engine Retry or after a failure of the worker itself, and
  // sends the failed calls again. A restart rejects every waiting call, and
  // the loader, the PDF controller and the census send theirs again on their
  // own, so only calls that had already failed are sent here.
  const retry = useCallback(
    (which: RetryAction) => {
      const loader = loaderRef.current;
      const pdf = pdfRef.current;
      if (!loader || !pdf) return;
      retryPattern(
        { loader, pdf, census: censusRequest, restart: () => engineRef.current.retry() },
        which,
      );
    },
    [censusRequest],
  );

  const yourPattern = useMemo<YourPatternApi>(
    () => ({
      screen,
      source,
      showPattern,
      showEditor,
      summary: summaryView,
      pdf: pdfView,
      savePdf,
      retry,
      model: patternModel,
      sizer: sizerView,
      presets,
      widths,
      setSize,
      setWidths,
    }),
    [
      screen,
      source,
      showPattern,
      showEditor,
      summaryView,
      pdfView,
      savePdf,
      retry,
      patternModel,
      sizerView,
      presets,
      widths,
      setSize,
      setWidths,
    ],
  );

  const closePattern = useCallback(() => {
    resetPlans(DEFAULT_STRATEGY);
    setPatternActive(false);
    setRoundtripReport(null);
    leavePattern();
  }, [resetPlans, leavePattern]);

  // ---- round-trip demo panel (render -> reverse -> compare) ----------------

  const runRoundtrip = useCallback(
    async (level: 0 | 2): Promise<void> => {
      if (!model) return;
      const json = JSON.stringify(model);
      try {
        const rendered = await engineRef.current.call<{ png_b64: string }>(
          "render",
          json,
          level,
          42,
          10,
        );
        const bytes = new Uint8Array(base64ToArrayBuffer(rendered.png_b64));
        const recovered = await engineRef.current.call<{ model: QuiltModel }>(
          "reverse_photo",
          bytes,
          "{}",
        );
        const report = await engineRef.current.call<{ dims_match: boolean; cell_accuracy: number }>(
          "compare",
          json,
          JSON.stringify(recovered.model),
        );
        setRoundtripReport({ dimsMatch: report.dims_match, cellAccuracy: report.cell_accuracy });
      } catch (err) {
        const message =
          err instanceof EngineError ? err.message : "The round trip didn’t finish, try again?";
        toast.push(message, "error");
      }
    },
    [model, toast],
  );

  // ---- exports + copy (PARITY items 11/12) --------------------------------

  const exportDownload = useCallback(
    async (kind: ExportKind): Promise<void> => {
      if (!model) return;
      const json = JSON.stringify(model);
      const strategy = seamStrategy;
      const slug = slugify(name);
      try {
        let data: BlobPart;
        let filename: string;
        let mime: string;
        if (kind === "svg") {
          const r = await engineRef.current.call<{ text: string }>("export_svg", json);
          data = r.text;
          filename = `${slug}-diagram.svg`;
          mime = "image/svg+xml";
        } else if (kind === "cutlist-csv") {
          const r = await engineRef.current.call<{ text: string }>(
            "export_cutlist_csv",
            json,
            strategy,
          );
          data = r.text;
          filename = `${slug}-cut-list.csv`;
          mime = "text/csv";
        } else if (kind === "cutlist-md") {
          const r = await engineRef.current.call<{ text: string }>(
            "export_cutlist_md",
            json,
            strategy,
          );
          data = r.text;
          filename = `${slug}-cut-list.md`;
          mime = "text/markdown";
        } else if (kind === "yardage") {
          const r = await engineRef.current.call<{ text: string }>("export_yardage", json, strategy);
          data = r.text;
          filename = `${slug}-yardage.txt`;
          mime = "text/plain";
        } else {
          const r = await engineRef.current.call<{ pdf_b64: string }>("export_pdf", json, strategy);
          data = base64ToArrayBuffer(r.pdf_b64);
          filename = `${slug}-booklet.pdf`;
          mime = "application/pdf";
        }
        triggerBlob(data, filename, mime);
        toast.push("Saved: your pattern file is ready.", "success");
      } catch (err) {
        const message =
          err instanceof EngineError ? err.message : "That export didn’t work, try again?";
        toast.push(message, "error");
      }
    },
    [model, name, seamStrategy, toast],
  );

  const copySettings = useCallback(async (): Promise<boolean> => {
    if (!model) return false;
    const text = buildSettingsSummary(model, name, summary, plans[seamStrategy]);
    let ok = false;
    try {
      await navigator.clipboard.writeText(text);
      ok = true;
    } catch {
      ok = execCommandCopy(text);
    }
    toast.push(
      ok ? "Copied! Paste it into notes, email, anywhere." : "Could not copy, sorry!",
      ok ? "success" : "error",
    );
    return ok;
  }, [model, name, summary, plans, seamStrategy, toast]);

  const roundtrip = useMemo<RoundTripApi>(
    () => ({ run: runRoundtrip, report: roundtripReport }),
    [runRoundtrip, roundtripReport],
  );

  const api = useMemo<PatternApi>(
    () => ({
      seamStrategy,
      plans,
      setPatternActive,
      exportDownload,
      copySettings,
      roundtrip,
      yourPattern,
    }),
    [seamStrategy, plans, exportDownload, copySettings, roundtrip, yourPattern],
  );

  return useMemo(
    () => ({ api, setSeamStrategy, resetPlans, closePattern }),
    [api, resetPlans, closePattern],
  );
}

export function usePattern(): PatternApi {
  const value = useContext(PatternContext);
  if (value === null) throw new Error("usePattern requires ProjectProvider");
  return value;
}

export function useRoundTrip(): RoundTripApi {
  return usePattern().roundtrip;
}

export function useYourPattern(): YourPatternApi {
  return usePattern().yourPattern;
}
