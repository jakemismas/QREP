/*
 * Photo flow state (C1a, issue #146): staging, analysis, the vision wheel,
 * size entry and the uncertainty overlay. The two editor entries in PhotoApi
 * (openInEditor, startInEditorFromFailure) are editing actions, so
 * project.tsx supplies them when it composes the photo context.
 */
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import { useEngine } from "../engine/useEngine";
import type { Engine } from "../engine/useEngine";
import { EngineError } from "../engine/rpc";
import type { VisionState } from "../engine/rpc";
import type { QuiltModel } from "../model/types";
import { classifyDevice, targetSize } from "../model/downscale";
import { SizeEntryState } from "../model/sizeEntry";
import type { SizeSource, SizeUnit } from "../model/sizeEntry";
import { useToast } from "../ui";
import { DEMO_URL } from "./model";
import { base64ToArrayBuffer } from "./pattern";
import { PhotoFlowMachine } from "./photoFlow";
import type { PhotoScreen, QuadSource } from "./photoFlow";

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

/** detect_quad's bridge result (S2, issue #68). */
interface DetectQuadResult {
  quad: [number, number][];
  tier: number | null;
  confidence: number;
  predicted_size: {
    width_px: number;
    height_px: number;
    aspect: number | null;
    preset: string | null;
  };
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
  /** S4 (issue #70), additive: the verdict contract. S8 renders these. */
  verdict?: string;
  diagnostics?: Record<string, unknown>;
  /** S6/S7 (issues #72/#73), additive: the size story. */
  sizeRequested?: { width: number | null; height: number | null } | null;
  sizeAchieved?: { width: number; height: number } | null;
}

/** The photo-reverse flow API (owned by the state layer; PhotoFlow consumes it).
 *
 * S2 (issue #68): the flow is idle -> crop -> progress -> results. start()
 * split into stage() (file in, photo shown immediately, detect_quad kicked
 * off) and analyze() (reverse with the user's pins when they moved one).
 * The post-results corners screen is retired; toCrop() re-enters the crop
 * screen seeded with the confirmed quad. */
export interface PhotoApi {
  /** True from the dropzone entry until the recovered model opens in the editor. */
  active: boolean;
  state: PhotoScreen;
  photoUrl: string | null;
  result: PhotoResult | null;
  visionState: VisionState;
  visionBytes: number | null;
  corners: [number, number][];
  detectedQuad: [number, number][] | null;
  detectPending: boolean;
  quadSource: QuadSource;
  stage: (file: File) => Promise<void>;
  analyze: () => Promise<void>;
  /** S7 (issue #73): the size block state + gestures (UI-SPEC section 2). */
  size: {
    widthEighths: number | null;
    heightEighths: number | null;
    source: SizeSource;
    unit: SizeUnit;
    enteredInCm: boolean;
    suggestedPreset: string | null;
    editInput: (which: "width" | "height", text: string) => boolean;
    tapChip: (name: string) => void;
    toggleUnit: () => void;
    seedForEdit: (width: number, height: number) => void;
    canApply: boolean;
  };
  applySizeFromResults: () => Promise<void>;
  startSample: () => Promise<void>;
  cancel: () => void;
  toCrop: () => void;
  setCorner: (index: number, xy: [number, number]) => void;
  resetToAuto: () => void;
  backFromCrop: () => void;
  openInEditor: () => void;
  /** S8 (issue #74): blank-grid escape from a failure verdict; keeps the
   * recovered palette only when it clears the frozen trust gate. */
  startInEditorFromFailure: () => void;
  backToDropzone: () => void;
  /** Retry a stalled vision load (vision-retry affordance on the progress screen). */
  retryVision: () => void;
}

/** Derived uncertainty state for the open (photo-sourced) model. */
export interface UncertaintyApi {
  count: number;
  showUncertain: boolean;
  toggle: () => void;
}

/** The size entry's values: a snapshot of the mutable SizeEntryState, taken
 * after every change so the size value can be memoized on it. */
type SizeView = Omit<PhotoApi["size"], "editInput" | "tapChip" | "toggleUnit" | "seedForEdit">;

function readSizeView(entry: SizeEntryState): SizeView {
  return {
    widthEighths: entry.widthEighths,
    heightEighths: entry.heightEighths,
    source: entry.source,
    unit: entry.unit,
    enteredInCm: entry.enteredInCm,
    suggestedPreset: entry.suggestedPreset,
    canApply: entry.sizeOptions() !== null,
  };
}

/** The photo context value. */
export interface PhotoSurface {
  photo: PhotoApi;
  uncertainty: UncertaintyApi;
}

/** What the provider that composes this module needs beyond the context value. */
export interface PhotoFlowState {
  flow: Omit<PhotoApi, "openInEditor" | "startInEditorFromFailure">;
  uncertainty: UncertaintyApi;
  /** Leave the flow for the editor; the photo stays for the editor's compare view. */
  exitToEditor: () => void;
  /** Leave the flow for home and drop the session photo. */
  reset: () => void;
}

export const PhotoContext = createContext<PhotoSurface | null>(null);

/** `model` is the open quilt, whose per-cell confidences give the uncertainty count. */
export function usePhotoState(model: QuiltModel | null): PhotoFlowState {
  const engine = useEngine();
  const { push } = useToast();
  const toast = useMemo(() => ({ push }), [push]);

  const engineRef = useRef<Engine>(engine);
  engineRef.current = engine;

  // ---- S6/S2 photo reverse state ------------------------------------------
  const machineRef = useRef<PhotoFlowMachine>(new PhotoFlowMachine());
  const sizeRef = useRef<SizeEntryState>(new SizeEntryState());
  const [photoActive, setPhotoActive] = useState(false);
  const [photoState, setPhotoState] = useState<PhotoScreen>("idle");
  const [photoUrl, setPhotoUrl] = useState<string | null>(null);
  const [photoResult, setPhotoResult] = useState<PhotoResult | null>(null);
  const [visionState, setVisionState] = useState<VisionState>("cold");
  const [visionBytes, setVisionBytes] = useState<number | null>(null);
  const [corners, setCorners] = useState<[number, number][]>(machineRef.current.corners);
  const [detectedQuad, setDetectedQuad] = useState<[number, number][] | null>(null);
  const [detectPending, setDetectPending] = useState(false);
  const [quadSource, setQuadSource] = useState<QuadSource>("default");
  const [showUncertain, setShowUncertain] = useState(false);

  const [sizeView, setSizeView] = useState<SizeView>(() => readSizeView(sizeRef.current));

  // mirror the pure machines into React state after every transition
  const syncPhoto = useCallback(() => {
    const m = machineRef.current;
    setPhotoState(m.state);
    setCorners(m.corners);
    setDetectedQuad(m.detectedQuad);
    setDetectPending(m.detectPending);
    setQuadSource(m.quadSource);
    setSizeView(readSizeView(sizeRef.current));
  }, []);

  const photoUrlRef = useRef<string | null>(null);
  photoUrlRef.current = photoUrl;
  const stagedBytesRef = useRef<Uint8Array | null>(null);
  const stagedDimsRef = useRef<{ width: number; height: number } | null>(null);
  const stagedTokenRef = useRef<string | null>(null);
  const reverseTokenRef = useRef<{ cancelled: boolean }>({ cancelled: false });
  const retryGateRef = useRef<(() => void) | null>(null);
  const prefetchedRef = useRef(false);

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
      payload: Uint8Array | string,
      optionsJson: string,
      token: { cancelled: boolean },
    ): Promise<{
      model: QuiltModel;
      verdict?: string;
      diagnostics?: Record<string, unknown>;
      requested?: { width: number | null; height: number | null } | null;
      achieved?: { width: number; height: number } | null;
      ms: number;
    }> => {
      for (;;) {
        if (token.cancelled) throw new EngineError("worker", "cancelled");
        try {
          const started = performance.now();
          const result = await engineRef.current.call<{
            model: QuiltModel;
            verdict?: string;
            diagnostics?: Record<string, unknown>;
            requested?: { width: number | null; height: number | null };
            achieved?: { width: number; height: number };
          }>("reverse_photo", payload, optionsJson);
          return {
            model: result.model,
            verdict: result.verdict,
            diagnostics: result.diagnostics,
            requested: result.requested ?? null,
            achieved: result.achieved ?? null,
            ms: performance.now() - started,
          };
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

  const applyReverse = useCallback(
    (
      model: QuiltModel,
      ms: number,
      verdict?: string,
      diagnostics?: Record<string, unknown>,
      requested?: { width: number | null; height: number | null } | null,
      achieved?: { width: number; height: number } | null,
    ) => {
      setPhotoResult({
        modelJson: JSON.stringify(model),
        stageConfidence: mapStageConfidence(model.provenance?.stage_confidence),
        uncertainCount: countUncertain(model.center.cell_confidence),
        reverseMs: ms,
        verdict,
        diagnostics,
        sizeRequested: requested ?? null,
        sizeAchieved: achieved ?? null,
      });
    },
    [],
  );

  /** Stage the photo's bytes into the worker once; the token is reused by
   * detect_quad and analyze, and re-staged if a worker restart wiped it. */
  const ensureStagedToken = useCallback(async (): Promise<string | null> => {
    if (stagedTokenRef.current) return stagedTokenRef.current;
    const bytes = stagedBytesRef.current;
    if (!bytes) return null;
    const staged = await engineRef.current.call<{ token: string }>("stage_photo", bytes);
    stagedTokenRef.current = staged.token;
    return staged.token;
  }, []);

  // S2 stage(): the photo and default pins render IMMEDIATELY (no engine on
  // the critical path); detection resolves in the background and snaps in
  // unless the user already moved a pin (the machine owns that race).
  const stage = useCallback(
    async (file: File): Promise<void> => {
      setPhotoActive(true);
      setPhotoResult(null);
      stagedTokenRef.current = null;
      sizeRef.current.reset();
      const seq = machineRef.current.enterCrop();
      syncPhoto();
      setSessionPhoto(URL.createObjectURL(file));
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
        const token = await ensureStagedToken();
        if (!token) throw new Error("no staged photo");
        const detected = await engineRef.current.call<DetectQuadResult>("detect_quad", token);
        machineRef.current.detectionResolved(seq, {
          quad: detected.quad,
          tier: detected.tier,
          confidence: detected.confidence,
        });
        sizeRef.current.suggest(detected.predicted_size?.preset ?? null);
        syncPhoto();
      } catch {
        // the crop screen stays fully usable on default pins; the finding-
        // your-quilt affordance simply disappears (cold-start contract)
        machineRef.current.detectionFailed(seq);
        syncPhoto();
      }
    },
    [ensureStagedToken, setSessionPhoto, syncPhoto],
  );

  // S2 analyze(): reverse via the staged token; corners ride along ONLY when
  // the user moved a pin (see photoFlow.ts for the honesty rationale).
  const analyze = useCallback(async (): Promise<void> => {
    const passed = machineRef.current.analyze();
    syncPhoto();
    setPhotoResult(null);
    const token = { cancelled: false };
    reverseTokenRef.current = token;
    try {
      const dims = stagedDimsRef.current ?? { width: 1, height: 1 };
      const options: Record<string, unknown> = {};
      if (passed) {
        options.corners = passed.map(([x, y]) => [x * dims.width, y * dims.height]);
      }
      const sized = sizeRef.current.sizeOptions();
      if (sized) {
        options.finished_width = sized.finished_width;
        options.finished_height = sized.finished_height;
      }
      const optionsJson = Object.keys(options).length ? JSON.stringify(options) : "{}";
      let staged = await ensureStagedToken();
      if (!staged) throw new Error("no staged photo");
      let outcome: {
        model: QuiltModel;
        verdict?: string;
        diagnostics?: Record<string, unknown>;
        requested?: { width: number | null; height: number | null } | null;
        achieved?: { width: number; height: number } | null;
        ms: number;
      };
      try {
        outcome = await runReverse(staged, optionsJson, token);
      } catch (error) {
        // a worker restart wiped MEMFS: the token is stale; re-stage once
        const stale =
          error instanceof EngineError &&
          error.kind === "value" &&
          /not found/i.test(error.message);
        if (!stale) throw error;
        stagedTokenRef.current = null;
        staged = await ensureStagedToken();
        if (!staged) throw error;
        outcome = await runReverse(staged, optionsJson, token);
      }
      if (token.cancelled) return;
      applyReverse(outcome.model, outcome.ms, outcome.verdict, outcome.diagnostics, outcome.requested, outcome.achieved);
      machineRef.current.results();
      syncPhoto();
    } catch {
      if (token.cancelled) return;
      toast.push("That photo didn’t come through, try another?", "error");
      machineRef.current.seedFromConfirmed();
      syncPhoto();
    }
  }, [ensureStagedToken, runReverse, applyReverse, syncPhoto, toast]);

  const startSample = useCallback(async (): Promise<void> => {
    // sample bypass (S2 contract): auto-confirmed full-frame render, no crop
    setPhotoActive(true);
    setPhotoResult(null);
    machineRef.current.bypassToProgress();
    syncPhoto();
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
      stagedTokenRef.current = null;
      try {
        const bitmap = await createImageBitmap(new Blob([bytes], { type: "image/png" }));
        stagedDimsRef.current = { width: bitmap.width, height: bitmap.height };
        if (typeof bitmap.close === "function") bitmap.close();
      } catch {
        stagedDimsRef.current = null;
      }
      setSessionPhoto(URL.createObjectURL(new Blob([bytes], { type: "image/png" })));
      const outcome = await runReverse(bytes, "{}", token);
      if (token.cancelled) return;
      applyReverse(outcome.model, outcome.ms, outcome.verdict, outcome.diagnostics, outcome.requested, outcome.achieved);
      machineRef.current.results();
      syncPhoto();
    } catch {
      if (token.cancelled) return;
      toast.push("The sample didn’t load, try again?", "error");
      machineRef.current.reset();
      syncPhoto();
    }
  }, [runReverse, applyReverse, setSessionPhoto, syncPhoto, toast]);

  const cancel = useCallback(() => {
    // PARITY item 14 (sprint 2, frozen): cancel returns to the dropzone;
    // the worker restart also invalidates the staged token by design
    reverseTokenRef.current.cancelled = true;
    retryGateRef.current?.();
    engineRef.current.restart();
    stagedTokenRef.current = null;
    machineRef.current.cancel();
    syncPhoto();
    setPhotoResult(null);
  }, [syncPhoto]);

  const retryVision = useCallback(() => {
    engineRef.current.prefetchVision();
    retryGateRef.current?.();
  }, []);

  // S7: inline size edit from results via apply_finished_size (no re-run)
  const applySizeFromResults = useCallback(async (): Promise<void> => {
    const current = photoResult;
    const sized = sizeRef.current.sizeOptions();
    if (!current || !sized) return;
    try {
      const applied = await engineRef.current.call<{
        model: QuiltModel;
        requested: { width: number | null; height: number | null };
        achieved: { width: number; height: number };
      }>("apply_finished_size", current.modelJson, sized.finished_width, sized.finished_height);
      setPhotoResult({
        ...current,
        modelJson: JSON.stringify(applied.model),
        sizeRequested: applied.requested,
        sizeAchieved: applied.achieved,
        diagnostics: { ...(current.diagnostics ?? {}), size_source: "user", size_is_guess: false },
      });
    } catch (err) {
      const message = err instanceof EngineError ? err.message : "That size did not apply. Try again?";
      toast.push(message, "error");
    }
  }, [photoResult, toast]);

  // "Adjust the crop" from results: one pin surface, reachable from both ends
  const toCrop = useCallback(() => {
    machineRef.current.seedFromConfirmed();
    syncPhoto();
  }, [syncPhoto]);

  const setCorner = useCallback(
    (index: number, xy: [number, number]) => {
      machineRef.current.movePin(index, xy);
      syncPhoto();
    },
    [syncPhoto],
  );

  const resetToAuto = useCallback(() => {
    machineRef.current.resetToAuto();
    syncPhoto();
  }, [syncPhoto]);

  const backFromCrop = useCallback(() => {
    // Back discards the staged photo (UI-SPEC section 1 flow rules)
    machineRef.current.backFromCrop();
    syncPhoto();
    stagedBytesRef.current = null;
    stagedDimsRef.current = null;
    stagedTokenRef.current = null;
    setSessionPhoto(null);
  }, [setSessionPhoto, syncPhoto]);

  const backToDropzone = useCallback(() => {
    setPhotoActive(true);
    machineRef.current.reset();
    syncPhoto();
    setPhotoResult(null);
    stagedBytesRef.current = null;
    stagedTokenRef.current = null;
    setSessionPhoto(null);
    // vision prefetch fires on photo-flow ENTRY, not on drop (S2 contract);
    // this is also the entry path from the start screen
    engineRef.current.prefetchVision();
  }, [setSessionPhoto, syncPhoto]);

  const exitToEditor = useCallback(() => {
    setPhotoActive(false);
    setPhotoState("idle");
    // photoUrl stays: the editor compare affordance reads it until reload.
  }, []);

  const reset = useCallback(() => {
    setPhotoActive(false);
    machineRef.current.reset();
    syncPhoto();
    setPhotoResult(null);
    stagedBytesRef.current = null;
    stagedTokenRef.current = null;
    setShowUncertain(false);
    setSessionPhoto(null);
  }, [setSessionPhoto, syncPhoto]);

  // ---- derived uncertainty for the open (photo-sourced) model --------------

  const uncertainCount = useMemo(() => countUncertain(model?.center.cell_confidence), [model]);
  const toggleUncertain = useCallback(() => setShowUncertain((value) => !value), []);
  const uncertainty = useMemo<UncertaintyApi>(
    () => ({ count: uncertainCount, showUncertain, toggle: toggleUncertain }),
    [uncertainCount, showUncertain, toggleUncertain],
  );

  const size = useMemo<PhotoApi["size"]>(
    () => ({
      ...sizeView,
      editInput: (which: "width" | "height", text: string) => {
        const ok = sizeRef.current.editInput(which, text);
        syncPhoto();
        return ok;
      },
      tapChip: (name: string) => {
        sizeRef.current.tapChip(name);
        syncPhoto();
      },
      toggleUnit: () => {
        sizeRef.current.toggleUnit();
        syncPhoto();
      },
      seedForEdit: (width: number, height: number) => {
        if (sizeRef.current.source === "none") {
          sizeRef.current.widthEighths = width;
          sizeRef.current.heightEighths = height;
        }
        syncPhoto();
      },
    }),
    [sizeView, syncPhoto],
  );

  const flow = useMemo<PhotoFlowState["flow"]>(
    () => ({
      active: photoActive,
      state: photoState,
      photoUrl,
      result: photoResult,
      visionState,
      visionBytes,
      corners,
      detectedQuad,
      detectPending,
      quadSource,
      stage,
      analyze,
      size,
      applySizeFromResults,
      startSample,
      cancel,
      toCrop,
      setCorner,
      resetToAuto,
      backFromCrop,
      backToDropzone,
      retryVision,
    }),
    [
      photoActive,
      photoState,
      photoUrl,
      photoResult,
      visionState,
      visionBytes,
      corners,
      detectedQuad,
      detectPending,
      quadSource,
      stage,
      analyze,
      size,
      applySizeFromResults,
      startSample,
      cancel,
      toCrop,
      setCorner,
      resetToAuto,
      backFromCrop,
      backToDropzone,
      retryVision,
    ],
  );

  return useMemo(
    () => ({ flow, uncertainty, exitToEditor, reset }),
    [flow, uncertainty, exitToEditor, reset],
  );
}

export function usePhoto(): PhotoApi {
  const value = useContext(PhotoContext);
  if (value === null) throw new Error("usePhoto requires ProjectProvider");
  return value.photo;
}

export function useUncertainty(): UncertaintyApi {
  const value = useContext(PhotoContext);
  if (value === null) throw new Error("useUncertainty requires ProjectProvider");
  return value.uncertainty;
}
