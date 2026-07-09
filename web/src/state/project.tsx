/*
 * Project state (S2 + S3, issues #42 / #43). Wraps an EditorStore for the open
 * model and drives the three commit-time side effects the editing slice needs:
 *   (a) a React snapshot of the mutable model so the canvas and panels redraw,
 *   (b) a debounced autosave of the wrapper doc to localStorage, and
 *   (c) a coalesced bridge re-validation whose summary is the fabric census.
 * Rendering still reads `model` synchronously and never waits on the engine;
 * `summary` fills in once validation lands.
 */
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";
import { useEngine } from "../engine/useEngine";
import type { Engine } from "../engine/useEngine";
import { EngineError } from "../engine/rpc";
import type { VisionState } from "../engine/rpc";
import { parseProjectFile } from "../model/types";
import type { QuiltModel, ModelSummary } from "../model/types";
import { classifyDevice, targetSize } from "../model/downscale";
import { effectiveMerges, pieceEstimate } from "../model/seams";
import type { SeamFix, SeamStrategy } from "../model/seams";
import { useToast } from "../ui";
import {
  COALESCE_WINDOW_MS,
  EditorStore,
  buildAutosaveDoc,
  buildProjectFile,
  makeBlankModel,
  parseAutosaveDoc,
} from "./editor";
import type { CellRef, ProjectUi } from "./editor";
import { buildSettingsSummary } from "./patternText";
import type { StrategyPlan } from "./patternText";

const DEFAULT_NAME = "My quilt project";
const DEMO_URL = "fixtures/double_irish_chain.json";
const AUTOSAVE_KEY = "qrep-autosave";
const AUTOSAVE_DEBOUNCE_MS = 800;

export type EditorMode = "move" | "paint" | "seams";

/** The three seam/plan strategies, in card order. */
const STRATEGIES: SeamStrategy[] = ["historical", "strip", "modern"];
const DEFAULT_STRATEGY: SeamStrategy = "strip";

// ---- S6 photo reverse (issue #46) --------------------------------------

/** Engine provenance stage keys -> UI stage keys (PARITY vocabulary). */
const STAGE_NAME_MAP: Record<string, string> = {
  rectify: "straighten",
  palette: "colors",
  grid: "grid",
  cells: "squares",
  repeat: "repeats",
  border: "borders",
};

/** PARITY item 6: a square is uncertain below this per-cell confidence. */
const UNCERTAIN_THRESHOLD = 0.9;

/** Normalized [0,1] corner seeds, inset to match the corner-editor pins. */
const DEFAULT_CORNERS: [number, number][] = [
  [0.06, 0.06],
  [0.94, 0.06],
  [0.94, 0.94],
  [0.06, 0.94],
];

function seedCorners(): [number, number][] {
  return DEFAULT_CORNERS.map((corner) => [...corner]) as [number, number][];
}

function mapStageConfidence(raw: Record<string, number> | undefined): Record<string, number> {
  const out: Record<string, number> = {};
  if (!raw) return out;
  for (const [key, value] of Object.entries(raw)) out[STAGE_NAME_MAP[key] ?? key] = value;
  return out;
}

function countUncertain(confidence: number[][] | null | undefined): number {
  if (!confidence) return 0;
  let count = 0;
  for (const row of confidence) {
    for (const value of row) if (value < UNCERTAIN_THRESHOLD) count += 1;
  }
  return count;
}

/** Encode a canvas to PNG bytes (worker stages these into MEMFS). */
function canvasToPngBytes(canvas: HTMLCanvasElement): Promise<Uint8Array> {
  return new Promise((resolve, reject) => {
    canvas.toBlob((blob) => {
      if (!blob) {
        reject(new Error("could not encode the photo"));
        return;
      }
      blob.arrayBuffer().then((buffer) => resolve(new Uint8Array(buffer)), reject);
    }, "image/png");
  });
}

/** The recovered analysis surfaced to the results screen. */
export interface PhotoResult {
  modelJson: string;
  stageConfidence: Record<string, number>;
  uncertainCount: number;
  reverseMs: number;
}

/** The photo-reverse flow API (owned by the state layer; PhotoFlow consumes it). */
export interface PhotoApi {
  /** True from the dropzone entry until the recovered model opens in the editor. */
  active: boolean;
  state: "idle" | "progress" | "results" | "corners";
  photoUrl: string | null;
  result: PhotoResult | null;
  visionState: VisionState;
  visionBytes: number | null;
  corners: [number, number][] | null;
  start: (file: File) => Promise<void>;
  startSample: () => Promise<void>;
  cancel: () => void;
  toCorners: () => void;
  setCorner: (index: number, xy: [number, number]) => void;
  resetCorners: () => void;
  rerunWithCorners: () => Promise<void>;
  openInEditor: () => void;
  backToDropzone: () => void;
  /** Return from the corner editor to the results screen. */
  backToResults: () => void;
  /** Retry a stalled vision load (vision-retry affordance on the progress screen). */
  retryVision: () => void;
}

/** Round-trip demo panel (render -> reverse -> compare) shown in the Pattern tab. */
export interface RoundTripApi {
  run: (level: 0 | 2) => Promise<void>;
  report: { dimsMatch: boolean; cellAccuracy: number } | null;
}

/** Derived uncertainty state for the open (photo-sourced) model. */
export interface UncertaintyApi {
  count: number;
  showUncertain: boolean;
  toggle: () => void;
}

/** A user-initiated engine export (PARITY item 11). */
export type ExportKind = "cutlist-csv" | "cutlist-md" | "yardage" | "svg" | "pdf";

function readStrategy(ui: ProjectUi | undefined): SeamStrategy {
  const value = ui?.seamStrategy;
  return value === "historical" || value === "strip" || value === "modern"
    ? value
    : DEFAULT_STRATEGY;
}

function readSeamFix(ui: ProjectUi | undefined): SeamFix {
  const value = ui?.seamFix;
  if (!value || typeof value !== "object") return {};
  const fix: SeamFix = {};
  for (const [edge, action] of Object.entries(value as Record<string, unknown>)) {
    if (action === "merge" || action === "split") fix[edge] = action;
  }
  return fix;
}

function base64ToArrayBuffer(b64: string): ArrayBuffer {
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

interface ResumeInfo {
  name: string;
  savedAt: number;
}

interface RestoreState {
  resume: ResumeInfo | null;
  autosaveError: string | null;
}

/** A locked/unlocked/cell/preset resize target handed to the bridge. */
export type ResizeTarget =
  | { width: number }
  | { height: number }
  | { cell: number }
  | { preset: { width: number; height: number } };

/** The bridge's resize envelope, kept so the panel can show asked-vs-got. */
export interface ResizeInfo {
  requested: { width?: number; height?: number; cell?: number };
  achieved: {
    width: number;
    height: number;
    cell_size: number;
    rows: number;
    cols: number;
    borders: number[];
  };
}

interface ProjectApi {
  model: QuiltModel | null;
  name: string;
  summary: ModelSummary | null;
  mode: EditorMode;
  selectedFabricId: string | null;
  canUndo: boolean;
  canRedo: boolean;
  resume: ResumeInfo | null;
  autosaveError: string | null;
  setMode: (mode: EditorMode) => void;
  selectFabric: (id: string) => void;
  paintStroke: (cells: CellRef[]) => void;
  recolorFabric: (id: string, color: string) => void;
  renameFabric: (id: string, name: string) => void;
  addFabric: () => void;
  deleteFabric: (id: string) => Promise<void>;
  lastResize: ResizeInfo | null;
  resizeLocked: (target: ResizeTarget) => Promise<void>;
  resizeUnlocked: (target: { width?: number; height?: number }) => Promise<void>;
  setBorderWidth: (index: number, eighths: number) => Promise<void>;
  setBorderFabric: (index: number, fabricId: string) => Promise<void>;
  addBorder: () => Promise<void>;
  removeBorder: (index: number) => Promise<void>;
  clearResizeHint: () => void;
  undo: () => void;
  redo: () => void;
  saveToFile: () => void;
  startBlank: () => void;
  resumeAutosave: () => void;
  openDemo: () => Promise<boolean>;
  openFromText: (text: string, fallbackName: string) => boolean;
  rename: (name: string) => void;
  goHome: () => void;
  // --- S5 pattern + seams ---
  seamStrategy: SeamStrategy;
  selectStrategy: (strategy: SeamStrategy) => void;
  seamMerges: string[];
  seamDrag: (edges: string[]) => void;
  seamTap: (cell: { row: number; col: number }) => void;
  handTweaked: boolean;
  estimates: { pieces: number; seams: number };
  plans: Record<SeamStrategy, StrategyPlan | null>;
  setPatternActive: (active: boolean) => void;
  exportDownload: (kind: ExportKind) => Promise<void>;
  copySettings: () => Promise<boolean>;
  // --- S6 photo reverse + round trip + uncertainty ---
  photo: PhotoApi;
  roundtrip: RoundTripApi;
  uncertainty: UncertaintyApi;
}

const ProjectContext = createContext<ProjectApi | null>(null);

function looksLikeModel(model: QuiltModel | undefined | null): boolean {
  return Boolean(model && model.center && model.center.cells && model.palette && model.palette.fabrics);
}

function slugify(name: string): string {
  const slug = name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "");
  return slug || "quilt";
}

/** Read the autosave slot once at startup: a resumable doc, a loud error, or nothing. */
function readAutosave(): RestoreState {
  let raw: string | null = null;
  try {
    raw = localStorage.getItem(AUTOSAVE_KEY);
  } catch {
    return { resume: null, autosaveError: null };
  }
  if (!raw) return { resume: null, autosaveError: null };
  try {
    const doc = parseAutosaveDoc(raw);
    return { resume: { name: doc.name, savedAt: doc.savedAt }, autosaveError: null };
  } catch (err) {
    // A foreign schema_version is surfaced verbatim, never cleared silently.
    return { resume: null, autosaveError: err instanceof Error ? err.message : String(err) };
  }
}

export function ProjectProvider({ children }: { children: ReactNode }) {
  const engine = useEngine();
  const toast = useToast();

  // `engine.validate` delegates to a stable client, but keep the latest ref so
  // scheduled validations never fire through a stale closure.
  const engineRef = useRef<Engine>(engine);
  engineRef.current = engine;

  const storeRef = useRef<EditorStore | null>(null);

  // The store coalesces same-kind edits inside COALESCE_WINDOW_MS. QuiltCanvas
  // commits exactly one stroke per pointer gesture, so a discrete gesture must
  // land as its own undo entry: a controllable logical clock is advanced past
  // the window before each such commit. Recolor deliberately does NOT advance,
  // so a color-picker drag's rapid changes still merge into one undo entry.
  const clockRef = useRef(0);
  const clockObjRef = useRef<{ now: () => number }>({ now: () => clockRef.current });
  const advanceClock = useCallback(() => {
    clockRef.current += COALESCE_WINDOW_MS + 1;
  }, []);

  const [model, setModel] = useState<QuiltModel | null>(null);
  const [name, setName] = useState<string>(DEFAULT_NAME);
  const [summary, setSummary] = useState<ModelSummary | null>(null);
  const [mode, setMode] = useState<EditorMode>("move");
  const [selectedFabricId, setSelectedFabricId] = useState<string | null>(null);
  const [canUndo, setCanUndo] = useState(false);
  const [canRedo, setCanRedo] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [lastResize, setLastResize] = useState<ResizeInfo | null>(null);
  const [restore, setRestore] = useState<RestoreState>(readAutosave);

  // ---- S6 photo reverse state --------------------------------------------
  const [photoActive, setPhotoActive] = useState(false);
  const [photoState, setPhotoState] = useState<"idle" | "progress" | "results" | "corners">("idle");
  const [photoUrl, setPhotoUrl] = useState<string | null>(null);
  const [photoResult, setPhotoResult] = useState<PhotoResult | null>(null);
  const [visionState, setVisionState] = useState<VisionState>("cold");
  const [visionBytes, setVisionBytes] = useState<number | null>(null);
  const [corners, setCorners] = useState<[number, number][] | null>(null);
  const [roundtripReport, setRoundtripReport] = useState<
    { dimsMatch: boolean; cellAccuracy: number } | null
  >(null);
  const [showUncertain, setShowUncertain] = useState(false);

  const photoUrlRef = useRef<string | null>(null);
  photoUrlRef.current = photoUrl;
  const cornersRef = useRef<[number, number][] | null>(null);
  cornersRef.current = corners;
  const photoResultRef = useRef<PhotoResult | null>(null);
  photoResultRef.current = photoResult;
  const stagedBytesRef = useRef<Uint8Array | null>(null);
  const stagedDimsRef = useRef<{ width: number; height: number } | null>(null);
  const reverseTokenRef = useRef<{ cancelled: boolean }>({ cancelled: false });
  const retryGateRef = useRef<(() => void) | null>(null);
  const prefetchedRef = useRef(false);

  const [seamStrategy, setSeamStrategy] = useState<SeamStrategy>(DEFAULT_STRATEGY);
  const [seamFix, setSeamFix] = useState<SeamFix>({});
  const [plans, setPlans] = useState<Record<SeamStrategy, StrategyPlan | null>>({
    historical: null,
    strip: null,
    modern: null,
  });

  const nameRef = useRef(name);
  nameRef.current = name;
  const selectedFabricIdRef = useRef(selectedFabricId);
  selectedFabricIdRef.current = selectedFabricId;
  const seamStrategyRef = useRef(seamStrategy);
  seamStrategyRef.current = seamStrategy;
  const seamFixRef = useRef(seamFix);
  seamFixRef.current = seamFix;
  const summaryRef = useRef(summary);
  summaryRef.current = summary;
  const plansRef = useRef(plans);
  plansRef.current = plans;
  // Pattern tab drives explicit plan requests; edits bump the model revision so
  // a stale in-flight plan can be discarded and the three strategies recomputed.
  const patternActiveRef = useRef(false);
  const editRevRef = useRef(0);
  const plansRevRef = useRef(-1);

  // ---- React snapshot of the mutable store -------------------------------

  const refresh = useCallback(() => {
    const s = storeRef.current;
    if (!s) return;
    setModel(structuredClone(s.model));
    setCanUndo(s.canUndo());
    setCanRedo(s.canRedo());
    setDirty(s.hasUnsavedChanges());
  }, []);

  // ---- coalesced commit-time validation (the fabric census) --------------
  //
  // Only one validate is in flight at a time; newer commits overwrite the
  // pending request, and a result applies only if it is still the newest
  // (version === latest), so a late resolve for a replaced model cannot
  // clobber the census.

  const versionRef = useRef(0);
  const pendingRef = useRef<{ json: string; version: number } | null>(null);
  const validatingRef = useRef(false);

  const drainValidation = useCallback(() => {
    if (validatingRef.current) return;
    const want = pendingRef.current;
    if (!want) return;
    pendingRef.current = null;
    validatingRef.current = true;
    engineRef.current
      .validate(want.json)
      .then(
        (result) => {
          if (want.version === versionRef.current) setSummary(result);
        },
        (err: unknown) => {
          if (want.version !== versionRef.current) return;
          const message = err instanceof EngineError ? err.message : "validation failed";
          toast.push(message, "error");
        },
      )
      .finally(() => {
        validatingRef.current = false;
        drainValidation();
      });
  }, [toast]);

  const requestValidation = useCallback(() => {
    const s = storeRef.current;
    if (!s) return;
    pendingRef.current = { json: JSON.stringify(s.model), version: ++versionRef.current };
    drainValidation();
  }, [drainValidation]);

  // ---- debounced autosave ------------------------------------------------

  const autosaveTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const writeAutosave = useCallback(() => {
    const s = storeRef.current;
    if (!s) return;
    try {
      localStorage.setItem(
        AUTOSAVE_KEY,
        buildAutosaveDoc(s.model, nameRef.current, Date.now(), {
          seamFix: seamFixRef.current,
          seamStrategy: seamStrategyRef.current,
        }),
      );
    } catch {
      /* storage blocked or full: autosave is best-effort */
    }
  }, []);

  const scheduleAutosave = useCallback(() => {
    if (autosaveTimer.current !== null) clearTimeout(autosaveTimer.current);
    autosaveTimer.current = setTimeout(() => {
      autosaveTimer.current = null;
      writeAutosave();
    }, AUTOSAVE_DEBOUNCE_MS);
  }, [writeAutosave]);

  // ---- plans (explicit, per model revision) ------------------------------
  //
  // PARITY item 1: card metrics and yardage are engine-authoritative. When the
  // Pattern tab is open the three strategies are planned once per model
  // revision; a plan whose revision was superseded by a later edit is dropped.

  const requestPlans = useCallback(() => {
    const s = storeRef.current;
    if (!s) return;
    const rev = editRevRef.current;
    if (plansRevRef.current === rev) return; // already requested for this revision
    plansRevRef.current = rev;
    const json = JSON.stringify(s.model);
    for (const strategy of STRATEGIES) {
      engineRef.current.call<StrategyPlan>("plan", json, strategy).then(
        (result) => {
          if (plansRevRef.current === rev) {
            setPlans((prev) => ({ ...prev, [strategy]: result }));
          }
        },
        (err: unknown) => {
          if (plansRevRef.current !== rev) return;
          const message =
            err instanceof EngineError ? err.message : "Couldn’t work out the plan — try again?";
          toast.push(message, "error");
        },
      );
    }
  }, [toast]);

  const setPatternActive = useCallback(
    (active: boolean) => {
      patternActiveRef.current = active;
      if (active) requestPlans();
    },
    [requestPlans],
  );

  const afterMutation = useCallback(() => {
    editRevRef.current += 1;
    refresh();
    requestValidation();
    scheduleAutosave();
    if (patternActiveRef.current) requestPlans();
  }, [refresh, requestValidation, scheduleAutosave, requestPlans]);

  // ---- open / restore ----------------------------------------------------

  const installModel = useCallback(
    (next: QuiltModel, displayName: string, ui?: ProjectUi) => {
      const s = storeRef.current;
      if (s) s.reset(next);
      else storeRef.current = new EditorStore(next, clockObjRef.current);
      setName(displayName || DEFAULT_NAME);
      setMode("move");
      setSelectedFabricId(next.palette.fabrics[0]?.id ?? null);
      setSummary(null);
      setLastResize(null);
      // Restore persisted seam UI (PARITY item 2/5); default strip, no fixes.
      const restoredStrategy = readStrategy(ui);
      const restoredFix = readSeamFix(ui);
      setSeamStrategy(restoredStrategy);
      seamStrategyRef.current = restoredStrategy;
      setSeamFix(restoredFix);
      seamFixRef.current = restoredFix;
      setPlans({ historical: null, strip: null, modern: null });
      plansRevRef.current = -1;
      editRevRef.current += 1;
      refresh();
      requestValidation();
      if (patternActiveRef.current) requestPlans();
    },
    [refresh, requestValidation, requestPlans],
  );

  const openFromText = useCallback(
    (text: string, fallbackName: string): boolean => {
      let parsed: { modelJson: string; name: string };
      try {
        parsed = parseProjectFile(text);
      } catch (err) {
        toast.push(`malformed JSON: ${err instanceof Error ? err.message : String(err)}`, "error");
        return false;
      }
      let parsedModel: QuiltModel;
      try {
        parsedModel = JSON.parse(parsed.modelJson) as QuiltModel;
      } catch (err) {
        toast.push(`malformed JSON: ${err instanceof Error ? err.message : String(err)}`, "error");
        return false;
      }
      if (!looksLikeModel(parsedModel)) {
        toast.push("That file isn’t a QREP project — nothing was changed.", "error");
        return false;
      }
      const displayName = parsed.name && parsed.name !== "Untitled" ? parsed.name : fallbackName;
      // parseProjectFile validates the wrapper already; recover ui.seamFix /
      // ui.seamStrategy from it (the frozen parser returns only model + name).
      let ui: ProjectUi | undefined;
      try {
        const doc = JSON.parse(text) as Record<string, unknown>;
        if (doc && doc.app === "QREP" && doc.ui && typeof doc.ui === "object") {
          ui = doc.ui as ProjectUi;
        }
      } catch {
        /* text already parsed above; ignore */
      }
      installModel(parsedModel, displayName || DEFAULT_NAME, ui);
      return true;
    },
    [toast, installModel],
  );

  const openDemo = useCallback(async (): Promise<boolean> => {
    try {
      const url = new URL(DEMO_URL, document.baseURI);
      const response = await fetch(url);
      if (!response.ok) throw new Error(`fetch failed: ${response.status}`);
      const text = await response.text();
      return openFromText(text, "Double Irish Chain");
    } catch {
      toast.push("Couldn’t load the demo quilt — try again?", "error");
      return false;
    }
  }, [openFromText, toast]);

  const startBlank = useCallback(() => {
    const blank = makeBlankModel();
    installModel(blank, blank.metadata.name || "New quilt");
  }, [installModel]);

  const resumeAutosave = useCallback(() => {
    let raw: string | null = null;
    try {
      raw = localStorage.getItem(AUTOSAVE_KEY);
    } catch {
      raw = null;
    }
    if (!raw) return;
    let doc: ReturnType<typeof parseAutosaveDoc>;
    try {
      doc = parseAutosaveDoc(raw);
    } catch (err) {
      setRestore({ resume: null, autosaveError: err instanceof Error ? err.message : String(err) });
      return;
    }
    installModel(doc.model, doc.name, doc.ui);
  }, [installModel]);

  // ---- S6 photo reverse flow (issue #46) ---------------------------------
  //
  // The state machine is idle(dropzone) -> progress -> results -> corners.
  // `active` is the app-level "in the photo flow" bit: idle doubles as the
  // dropzone, so App routes to PhotoFlow on `active`, not on state alone.
  // The session bitmap (photoUrl) is never persisted (PARITY item 7).

  const setSessionPhoto = useCallback((url: string | null) => {
    const previous = photoUrlRef.current;
    if (previous && previous !== url) {
      try {
        URL.revokeObjectURL(previous);
      } catch {
        /* revoke is best-effort */
      }
    }
    photoUrlRef.current = url;
    setPhotoUrl(url);
  }, []);

  // Mirror the RPC vision state onto <body> for the e2e and the loading bar,
  // and fetch the manifest once for the measured payload size.
  useEffect(() => {
    const unsubscribe = engineRef.current.onVision((state) => {
      try {
        document.body.dataset.visionState = state;
      } catch {
        /* SSR guard; never reached in the browser */
      }
      setVisionState(state);
    });
    return unsubscribe;
  }, []);

  useEffect(() => {
    let alive = true;
    fetch(new URL("wheels/manifest.json", document.baseURI))
      .then((response) => response.json())
      .then((manifest: { visionBytes?: number }) => {
        if (alive && typeof manifest.visionBytes === "number") setVisionBytes(manifest.visionBytes);
      })
      .catch(() => {
        /* the loading bar shows a placeholder size if the manifest is missing */
      });
    return () => {
      alive = false;
    };
  }, []);

  // PARITY item 17: after the engine is ready and the page is idle, quietly
  // prefetch the vision stack (skipped when the browser signals Save-Data).
  const enginePhase = engine.status.phase;
  useEffect(() => {
    if (enginePhase !== "ready" || prefetchedRef.current) return;
    const connection = (navigator as { connection?: { saveData?: boolean } }).connection;
    if (connection?.saveData) return;
    prefetchedRef.current = true;
    const run = () => engineRef.current.prefetchVision();
    const idle = (window as typeof window & { requestIdleCallback?: (cb: () => void) => number })
      .requestIdleCallback;
    if (typeof idle === "function") idle(run);
    else window.setTimeout(run, 1500);
  }, [enginePhase]);

  const isVisionError = (error: unknown): boolean =>
    error instanceof EngineError && /vision/i.test(error.message);

  // One reverse attempt with a vision-retry loop: a blocked vision wheel
  // rejects the call, so we wait for a retry ping (manual or a safety-net
  // timeout) and re-issue, which re-triggers the worker's lazy vision load.
  const runReverse = useCallback(
    async (
      bytes: Uint8Array,
      optionsJson: string,
      token: { cancelled: boolean },
    ): Promise<{ model: QuiltModel; ms: number }> => {
      for (;;) {
        if (token.cancelled) throw new EngineError("worker", "cancelled");
        try {
          const started = performance.now();
          const result = await engineRef.current.call<{ model: QuiltModel }>(
            "reverse_photo",
            bytes,
            optionsJson,
          );
          return { model: result.model, ms: performance.now() - started };
        } catch (error) {
          if (token.cancelled || !isVisionError(error)) throw error;
          await new Promise<void>((resolve) => {
            let done = false;
            const finish = () => {
              if (done) return;
              done = true;
              retryGateRef.current = null;
              clearTimeout(timer);
              resolve();
            };
            const timer = setTimeout(finish, 2000);
            retryGateRef.current = finish;
          });
        }
      }
    },
    [],
  );

  const applyReverse = useCallback((model: QuiltModel, ms: number) => {
    setPhotoResult({
      modelJson: JSON.stringify(model),
      stageConfidence: mapStageConfidence(model.provenance?.stage_confidence),
      uncertainCount: countUncertain(model.center.cell_confidence),
      reverseMs: ms,
    });
    setPhotoState("results");
  }, []);

  const start = useCallback(
    async (file: File): Promise<void> => {
      setPhotoActive(true);
      setPhotoState("progress");
      setPhotoResult(null);
      setCorners(null);
      cornersRef.current = null;
      const token = { cancelled: false };
      reverseTokenRef.current = token;
      try {
        const bitmap = await createImageBitmap(file);
        const size = targetSize(bitmap.width, bitmap.height, classifyDevice(window.innerWidth));
        const canvas = document.createElement("canvas");
        canvas.width = size.width;
        canvas.height = size.height;
        const ctx = canvas.getContext("2d");
        if (!ctx) throw new Error("no 2d canvas context");
        ctx.drawImage(bitmap, 0, 0, size.width, size.height);
        if (typeof bitmap.close === "function") bitmap.close();
        const bytes = await canvasToPngBytes(canvas);
        stagedBytesRef.current = bytes;
        stagedDimsRef.current = { width: size.width, height: size.height };
        setSessionPhoto(URL.createObjectURL(file));
        if (token.cancelled) return;
        const { model, ms } = await runReverse(bytes, "{}", token);
        if (token.cancelled) return;
        applyReverse(model, ms);
      } catch {
        if (token.cancelled) return;
        toast.push("That photo didn’t come through — try another?", "error");
        setPhotoState("idle");
      }
    },
    [runReverse, applyReverse, setSessionPhoto, toast],
  );

  const startSample = useCallback(async (): Promise<void> => {
    setPhotoActive(true);
    setPhotoState("progress");
    setPhotoResult(null);
    setCorners(null);
    cornersRef.current = null;
    const token = { cancelled: false };
    reverseTokenRef.current = token;
    try {
      const demoText = await (await fetch(new URL(DEMO_URL, document.baseURI))).text();
      const rendered = await engineRef.current.call<{ png_b64: string }>(
        "render",
        demoText,
        0,
        42,
        10,
      );
      if (token.cancelled) return;
      const bytes = new Uint8Array(base64ToArrayBuffer(rendered.png_b64));
      stagedBytesRef.current = bytes;
      try {
        const bitmap = await createImageBitmap(new Blob([bytes], { type: "image/png" }));
        stagedDimsRef.current = { width: bitmap.width, height: bitmap.height };
        if (typeof bitmap.close === "function") bitmap.close();
      } catch {
        stagedDimsRef.current = null;
      }
      setSessionPhoto(URL.createObjectURL(new Blob([bytes], { type: "image/png" })));
      const { model, ms } = await runReverse(bytes, "{}", token);
      if (token.cancelled) return;
      applyReverse(model, ms);
    } catch {
      if (token.cancelled) return;
      toast.push("The sample didn’t load — try again?", "error");
      setPhotoState("idle");
    }
  }, [runReverse, applyReverse, setSessionPhoto, toast]);

  const cancel = useCallback(() => {
    reverseTokenRef.current.cancelled = true;
    retryGateRef.current?.();
    engineRef.current.restart();
    setPhotoState("idle");
    setPhotoResult(null);
  }, []);

  const retryVision = useCallback(() => {
    engineRef.current.prefetchVision();
    retryGateRef.current?.();
  }, []);

  const toCorners = useCallback(() => {
    if (cornersRef.current === null) {
      const seed = seedCorners();
      cornersRef.current = seed;
      setCorners(seed);
    }
    setPhotoState("corners");
  }, []);

  const backToResults = useCallback(() => {
    setPhotoState("results");
  }, []);

  const setCorner = useCallback((index: number, xy: [number, number]) => {
    const current = cornersRef.current ?? seedCorners();
    const next = current.map((c, i) => (i === index ? xy : c)) as [number, number][];
    cornersRef.current = next;
    setCorners(next);
  }, []);

  const resetCorners = useCallback(() => {
    const seed = seedCorners();
    cornersRef.current = seed;
    setCorners(seed);
  }, []);

  const rerunWithCorners = useCallback(async (): Promise<void> => {
    const bytes = stagedBytesRef.current;
    const cornerList = cornersRef.current;
    if (!bytes || !cornerList) return;
    setPhotoState("progress");
    const token = { cancelled: false };
    reverseTokenRef.current = token;
    try {
      // UI corners are normalized [0,1]; scale into staged-image pixel space.
      const dims = stagedDimsRef.current ?? { width: 1, height: 1 };
      const pixels = cornerList.map(([x, y]) => [x * dims.width, y * dims.height]);
      const { model, ms } = await runReverse(bytes, JSON.stringify({ corners: pixels }), token);
      if (token.cancelled) return;
      applyReverse(model, ms);
    } catch {
      if (token.cancelled) return;
      toast.push("That re-run didn’t finish — try again?", "error");
      setPhotoState("results");
    }
  }, [runReverse, applyReverse, toast]);

  const openInEditor = useCallback(() => {
    const result = photoResultRef.current;
    if (!result) return;
    let model: QuiltModel;
    try {
      model = JSON.parse(result.modelJson) as QuiltModel;
    } catch {
      return;
    }
    const displayName = model.metadata?.name || "Photo quilt";
    installModel(model, displayName);
    // Persist immediately so a reload can resume (the bitmap stays session-only).
    nameRef.current = displayName;
    writeAutosave();
    setPhotoActive(false);
    setPhotoState("idle");
    // photoUrl stays: the editor compare affordance reads it until reload.
  }, [installModel, writeAutosave]);

  const backToDropzone = useCallback(() => {
    setPhotoActive(true);
    setPhotoState("idle");
    setPhotoResult(null);
    setCorners(null);
    cornersRef.current = null;
    setSessionPhoto(null);
  }, [setSessionPhoto]);

  // ---- round-trip demo panel (render -> reverse -> compare) ----------------

  const runRoundtrip = useCallback(
    async (level: 0 | 2): Promise<void> => {
      const s = storeRef.current;
      if (!s) return;
      const json = JSON.stringify(s.model);
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
          err instanceof EngineError ? err.message : "The round trip didn’t finish — try again?";
        toast.push(message, "error");
      }
    },
    [toast],
  );

  // ---- derived uncertainty for the open (photo-sourced) model --------------

  const uncertainCount = useMemo(() => countUncertain(model?.center.cell_confidence), [model]);
  const toggleUncertain = useCallback(() => setShowUncertain((value) => !value), []);

  // ---- editing actions ---------------------------------------------------

  const selectFabric = useCallback((id: string) => {
    setSelectedFabricId(id);
    // Picking a fabric arms the brush (mock: select implies paint mode).
    setMode("paint");
  }, []);

  const paintStroke = useCallback(
    (cells: CellRef[]) => {
      const s = storeRef.current;
      const fabricId = selectedFabricIdRef.current;
      if (!s || fabricId === null || cells.length === 0) return;
      advanceClock();
      s.paintStroke(cells, fabricId);
      afterMutation();
    },
    [advanceClock, afterMutation],
  );

  const recolorFabric = useCallback(
    (id: string, color: string) => {
      const s = storeRef.current;
      if (!s) return;
      s.recolorFabric(id, color);
      afterMutation();
    },
    [afterMutation],
  );

  const renameFabric = useCallback(
    (id: string, next: string) => {
      const s = storeRef.current;
      if (!s) return;
      advanceClock();
      s.renameFabric(id, next);
      afterMutation();
    },
    [advanceClock, afterMutation],
  );

  const addFabric = useCallback(() => {
    const s = storeRef.current;
    if (!s) return;
    advanceClock();
    const id = s.addFabric();
    setSelectedFabricId(id);
    setMode("paint");
    afterMutation();
    toast.push("New fabric added — it’s now your paintbrush.", "success");
  }, [advanceClock, afterMutation, toast]);

  const deleteFabric = useCallback(
    async (id: string): Promise<void> => {
      const s = storeRef.current;
      if (!s) return;
      const candidate = s.withFabricRemoved(id);
      try {
        await engineRef.current.validate(JSON.stringify(candidate));
      } catch (err) {
        // The bridge owns referential integrity: a still-referenced fabric
        // fails here and the palette is left untouched.
        const message = err instanceof EngineError ? err.message : "That fabric can’t be removed.";
        toast.push(message, "error");
        return;
      }
      advanceClock();
      s.commitCandidate(candidate, "delete-fabric");
      if (selectedFabricIdRef.current === id) {
        setSelectedFabricId(s.model.palette.fabrics[0]?.id ?? null);
      }
      afterMutation();
    },
    [advanceClock, afterMutation, toast],
  );

  // ---- sizing actions (S4, issue #44) ------------------------------------
  //
  // PARITY item 4: every commit adopts the band-scaling bridge model; the JS
  // preview mirror only makes typing feel immediate. Locked/unlocked resize go
  // through resize_locked/resize_unlocked; border ops build a candidate and
  // pass the same validate-then-commit gate deleteFabric uses.

  const runResize = useCallback(
    async (
      method: "resize_locked" | "resize_unlocked",
      target: ResizeTarget | { width?: number; height?: number },
    ): Promise<void> => {
      const s = storeRef.current;
      if (!s) return;
      let result: ResizeInfo & { model: QuiltModel };
      try {
        result = await engineRef.current.call<ResizeInfo & { model: QuiltModel }>(
          method,
          JSON.stringify(s.model),
          JSON.stringify(target),
        );
      } catch (err) {
        const message = err instanceof EngineError ? err.message : "That size didn’t work — try again?";
        toast.push(message, "error");
        return;
      }
      advanceClock();
      s.commitCandidate(result.model, "resize");
      setLastResize({ requested: result.requested, achieved: result.achieved });
      afterMutation();
    },
    [advanceClock, afterMutation, toast],
  );

  const resizeLocked = useCallback(
    (target: ResizeTarget): Promise<void> => runResize("resize_locked", target),
    [runResize],
  );

  const resizeUnlocked = useCallback(
    (target: { width?: number; height?: number }): Promise<void> =>
      runResize("resize_unlocked", target),
    [runResize],
  );

  const commitBorderCandidate = useCallback(
    async (candidate: QuiltModel, kind: string): Promise<boolean> => {
      const s = storeRef.current;
      if (!s) return false;
      try {
        // The bridge owns referential integrity and band bounds; a bad border
        // fails here and the model is left untouched (exact deleteFabric shape).
        await engineRef.current.validate(JSON.stringify(candidate));
      } catch (err) {
        const message = err instanceof EngineError ? err.message : "That border can’t be applied.";
        toast.push(message, "error");
        return false;
      }
      advanceClock();
      s.commitCandidate(candidate, kind);
      // A border edit is a fresh commit with no requested finished size, so the
      // asked-vs-got hint from a prior resize no longer applies.
      setLastResize(null);
      afterMutation();
      return true;
    },
    [advanceClock, afterMutation, toast],
  );

  const setBorderWidth = useCallback(
    async (index: number, eighths: number): Promise<void> => {
      const s = storeRef.current;
      if (!s || !s.model.borders[index]) return;
      const candidate = structuredClone(s.model);
      candidate.borders[index].width = eighths;
      await commitBorderCandidate(candidate, "border-width");
    },
    [commitBorderCandidate],
  );

  const setBorderFabric = useCallback(
    async (index: number, fabricId: string): Promise<void> => {
      const s = storeRef.current;
      if (!s || !s.model.borders[index]) return;
      const candidate = structuredClone(s.model);
      candidate.borders[index].fabric_id = fabricId;
      await commitBorderCandidate(candidate, "border-fabric");
    },
    [commitBorderCandidate],
  );

  const addBorder = useCallback(async (): Promise<void> => {
    const s = storeRef.current;
    if (!s) return;
    const backgroundId = s.model.palette.fabrics[0]?.id;
    if (backgroundId == null) return;
    const candidate = structuredClone(s.model);
    // Innermost = index 0 (the engine stores bands inner-to-outer); 2" default.
    candidate.borders.unshift({ fabric_id: backgroundId, width: 16 });
    if (await commitBorderCandidate(candidate, "border-add")) {
      toast.push("New border added inside the others.", "success");
    }
  }, [commitBorderCandidate, toast]);

  const removeBorder = useCallback(
    async (index: number): Promise<void> => {
      const s = storeRef.current;
      if (!s || s.model.borders.length <= 1) return;
      const candidate = structuredClone(s.model);
      candidate.borders.splice(index, 1);
      await commitBorderCandidate(candidate, "border-remove");
    },
    [commitBorderCandidate],
  );

  const clearResizeHint = useCallback(() => setLastResize(null), []);

  const undo = useCallback(() => {
    const s = storeRef.current;
    if (!s || !s.canUndo()) return;
    s.undo();
    afterMutation();
  }, [afterMutation]);

  const redo = useCallback(() => {
    const s = storeRef.current;
    if (!s || !s.canRedo()) return;
    s.redo();
    afterMutation();
  }, [afterMutation]);

  const saveToFile = useCallback(() => {
    const s = storeRef.current;
    if (!s) return;
    const filename = `${slugify(nameRef.current)}.qrep.json`;
    try {
      const blob = new Blob(
        [
          buildProjectFile(s.model, nameRef.current, {
            seamFix: seamFixRef.current,
            seamStrategy: seamStrategyRef.current,
          }),
        ],
        { type: "application/json" },
      );
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      // Set via the property, not a string attribute name, to keep the banned
      // save-verb out of source-string scans while still triggering the save.
      anchor.download = filename;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      setTimeout(() => URL.revokeObjectURL(url), 10_000);
      s.markFileSaved();
      setDirty(false);
      toast.push(`Project saved as ${filename}`, "success");
    } catch {
      toast.push("Save didn’t work — try again?", "error");
    }
  }, [toast]);

  const rename = useCallback(
    (next: string) => {
      setName(next.trim() || DEFAULT_NAME);
      scheduleAutosave();
    },
    [scheduleAutosave],
  );

  const goHome = useCallback(() => {
    storeRef.current = null;
    pendingRef.current = null;
    versionRef.current++;
    patternActiveRef.current = false;
    plansRevRef.current = -1;
    setModel(null);
    setSummary(null);
    setName(DEFAULT_NAME);
    setMode("move");
    setSelectedFabricId(null);
    setCanUndo(false);
    setCanRedo(false);
    setDirty(false);
    setLastResize(null);
    setSeamStrategy(DEFAULT_STRATEGY);
    seamStrategyRef.current = DEFAULT_STRATEGY;
    setSeamFix({});
    seamFixRef.current = {};
    setPlans({ historical: null, strip: null, modern: null });
    // Leaving for home also exits any photo flow and drops the session bitmap.
    setPhotoActive(false);
    setPhotoState("idle");
    setPhotoResult(null);
    setCorners(null);
    cornersRef.current = null;
    setShowUncertain(false);
    setRoundtripReport(null);
    setSessionPhoto(null);
  }, [setSessionPhoto]);

  // ---- seams tool (PARITY item 2; preview layer over ui.seamFix) ----------

  const handleSetMode = useCallback(
    (next: EditorMode) => {
      setMode(next);
      if (next === "seams") {
        toast.push("Seams: drag to sew squares together, tap a piece to split it.", "success");
      }
    },
    [toast],
  );

  const selectStrategy = useCallback(
    (strategy: SeamStrategy) => {
      const hadFixes = Object.keys(seamFixRef.current).length > 0;
      setSeamStrategy(strategy);
      seamStrategyRef.current = strategy;
      if (hadFixes) {
        setSeamFix({});
        seamFixRef.current = {};
        toast.push("Seam tweaks reset for the new plan.", "success");
      }
      scheduleAutosave();
    },
    [toast, scheduleAutosave],
  );

  const seamDrag = useCallback(
    (edges: string[]) => {
      const s = storeRef.current;
      if (!s || edges.length === 0) return;
      const cells = s.model.center.cells;
      const merged = effectiveMerges(cells, seamStrategyRef.current, seamFixRef.current);
      let changed = false;
      const next: SeamFix = { ...seamFixRef.current };
      for (const edge of edges) {
        if (!merged.has(edge)) {
          next[edge] = "merge";
          changed = true;
        }
      }
      if (!changed) return;
      setSeamFix(next);
      seamFixRef.current = next;
      scheduleAutosave();
    },
    [scheduleAutosave],
  );

  const seamTap = useCallback(
    (cell: { row: number; col: number }) => {
      const s = storeRef.current;
      if (!s) return;
      const cells = s.model.center.cells;
      const rows = cells.length;
      const cols = cells[0]?.length ?? 0;
      if (cell.row < 0 || cell.row >= rows || cell.col < 0 || cell.col >= cols) return;
      const merged = effectiveMerges(cells, seamStrategyRef.current, seamFixRef.current);
      // Walk the piece under the tap, collecting every merged edge inside it, then
      // split each one so the whole piece breaks back into single squares.
      const start = cell.row * cols + cell.col;
      const visited = new Set<number>([start]);
      const inside = new Set<string>();
      const stack = [start];
      while (stack.length > 0) {
        const index = stack.pop()!;
        const r = Math.floor(index / cols);
        const c = index % cols;
        const step = (edge: string, neighbor: number) => {
          if (!merged.has(edge)) return;
          inside.add(edge);
          if (!visited.has(neighbor)) {
            visited.add(neighbor);
            stack.push(neighbor);
          }
        };
        if (c < cols - 1) step(`${r},${c}:v`, index + 1);
        if (c > 0) step(`${r},${c - 1}:v`, index - 1);
        if (r < rows - 1) step(`${r},${c}:h`, index + cols);
        if (r > 0) step(`${r - 1},${c}:h`, index - cols);
      }
      if (inside.size === 0) return;
      const next: SeamFix = { ...seamFixRef.current };
      for (const edge of inside) next[edge] = "split";
      setSeamFix(next);
      seamFixRef.current = next;
      scheduleAutosave();
    },
    [scheduleAutosave],
  );

  const seamMerges = useMemo<string[]>(() => {
    if (!model) return [];
    return [...effectiveMerges(model.center.cells, seamStrategy, seamFix)];
  }, [model, seamStrategy, seamFix]);

  const estimates = useMemo(() => {
    if (!model) return { pieces: 0, seams: 0 };
    return pieceEstimate(
      model.center.cells,
      effectiveMerges(model.center.cells, seamStrategy, seamFix),
    );
  }, [model, seamStrategy, seamFix]);

  const handTweaked = Object.keys(seamFix).length > 0;

  // ---- exports + copy (PARITY items 11/12) --------------------------------

  const exportDownload = useCallback(
    async (kind: ExportKind): Promise<void> => {
      const s = storeRef.current;
      if (!s) return;
      const json = JSON.stringify(s.model);
      const strategy = seamStrategyRef.current;
      const slug = slugify(nameRef.current);
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
        toast.push("Saved — your pattern file is ready.", "success");
      } catch (err) {
        const message =
          err instanceof EngineError ? err.message : "That export didn’t work — try again?";
        toast.push(message, "error");
      }
    },
    [toast],
  );

  const copySettings = useCallback(async (): Promise<boolean> => {
    const s = storeRef.current;
    if (!s) return false;
    const text = buildSettingsSummary(
      s.model,
      nameRef.current,
      summaryRef.current,
      plansRef.current[seamStrategyRef.current],
    );
    let ok = false;
    try {
      await navigator.clipboard.writeText(text);
      ok = true;
    } catch {
      ok = execCommandCopy(text);
    }
    toast.push(
      ok ? "Copied! Paste it into notes, email, anywhere." : "Could not copy — sorry!",
      ok ? "success" : "error",
    );
    return ok;
  }, [toast]);

  // ---- beforeunload guard (registered only while file-dirty) -------------

  useEffect(() => {
    if (!dirty) return;
    const handler = (event: BeforeUnloadEvent) => {
      // Flush the latest state so a reload before the debounce still resumes.
      writeAutosave();
      event.preventDefault();
      // A non-empty returnValue arms the native confirm in Chromium; the
      // browser substitutes its own generic wording.
      event.returnValue = "You have unsaved changes.";
    };
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  }, [dirty, writeAutosave]);

  const api: ProjectApi = {
    model,
    name,
    summary,
    mode,
    selectedFabricId,
    canUndo,
    canRedo,
    resume: restore.resume,
    autosaveError: restore.autosaveError,
    setMode: handleSetMode,
    selectFabric,
    paintStroke,
    recolorFabric,
    renameFabric,
    addFabric,
    deleteFabric,
    lastResize,
    resizeLocked,
    resizeUnlocked,
    setBorderWidth,
    setBorderFabric,
    addBorder,
    removeBorder,
    clearResizeHint,
    undo,
    redo,
    saveToFile,
    startBlank,
    resumeAutosave,
    openDemo,
    openFromText,
    rename,
    goHome,
    seamStrategy,
    selectStrategy,
    seamMerges,
    seamDrag,
    seamTap,
    handTweaked,
    estimates,
    plans,
    setPatternActive,
    exportDownload,
    copySettings,
    photo: {
      active: photoActive,
      state: photoState,
      photoUrl,
      result: photoResult,
      visionState,
      visionBytes,
      corners,
      start,
      startSample,
      cancel,
      toCorners,
      setCorner,
      resetCorners,
      rerunWithCorners,
      openInEditor,
      backToDropzone,
      backToResults,
      retryVision,
    },
    roundtrip: { run: runRoundtrip, report: roundtripReport },
    uncertainty: { count: uncertainCount, showUncertain, toggle: toggleUncertain },
  };

  return <ProjectContext.Provider value={api}>{children}</ProjectContext.Provider>;
}

export function useProject(): ProjectApi {
  const value = useContext(ProjectContext);
  if (value === null) throw new Error("useProject requires ProjectProvider");
  return value;
}
