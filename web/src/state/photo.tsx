/*
 * Photo flow state (C1a, issue #146): staging, analysis, the vision wheel,
 * size entry and the uncertainty overlay. The two editor entries in PhotoApi
 * (openInEditor, startInEditorFromFailure) are editing actions, so
 * project.tsx supplies them when it composes the photo context.
 *
 * C3b (issue #101): a dropped file is decoded before the confirm screen opens,
 * the confirm screen's pins, frame, bands and counts live in ConfirmFlow
 * (confirm/confirmFlow.ts), and Continue stages one crop of the decoded photo
 * at full resolution (confirm/stagePhoto.ts). PhotoFlowMachine stays the
 * screen router only; detect_quad is never called.
 */
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import { useEngine } from "../engine/useEngine";
import type { Engine } from "../engine/useEngine";
import { useEngineStatus } from "../engine/engineStatus";
import { EngineError } from "../engine/rpc";
import type { VisionState } from "../engine/rpc";
import { parseSizeResult } from "../engine/contract";
import type { BorderBand, Corners, Point } from "../engine/contract";
import { ConfirmFlow } from "../confirm/confirmFlow";
import type { ConfirmStatus } from "../confirm/confirmFlow";
import type { AxisCount } from "../confirm/counts";
import { CORNER_NAMES } from "../confirm/frame";
import type { CornerName, FrameMode } from "../confirm/frame";
import type { Size } from "../confirm/geometry";
import { decodePhoto, frameSquares, squarePx, stagePhoto } from "../confirm/stagePhoto";
import type { CropPlan } from "../confirm/stagePhoto";
import type { QuiltModel } from "../model/types";
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

/** One reverse_photo run, with its wall time. */
interface ReverseOutcome {
  model: QuiltModel;
  verdict?: string;
  diagnostics?: Record<string, unknown>;
  requested?: { width: number | null; height: number | null } | null;
  achieved?: { width: number; height: number } | null;
  ms: number;
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

/** The confirm screen's state and gestures (C3b, issue #101): a snapshot of
 * ConfirmFlow taken after every change. Corners are in decoded-photo pixels. */
export interface ConfirmApi {
  status: ConfirmStatus;
  /** Why the last photo could not be opened, in plain words. */
  error: string | null;
  /** The decoded photo's size, EXIF orientation applied. */
  size: Size | null;
  mode: FrameMode;
  corners: Corners | null;
  bands: BorderBand[];
  across: AxisCount;
  down: AxisCount;
  /** Continue is cutting the crop. */
  staging: boolean;
  /** The finished square size in eighths for typed band widths, or null. */
  squareEighths: number | null;
  /** Why Continue is off, or null. */
  blocked: string | null;
  canContinue: boolean;
  setCorner: (name: CornerName, point: Point) => void;
  setMode: (mode: FrameMode) => void;
  setBands: (bands: BorderBand[]) => void;
  setCounts: (across: AxisCount, down: AxisCount) => void;
}

/** The photo-reverse flow API (owned by the state layer; PhotoFlow consumes it).
 *
 * The flow is idle (the dropzone) -> crop (the confirm screen) -> progress ->
 * results. stage() decodes the file and opens the confirm screen; analyze()
 * (Continue) stages the confirmed crop and reverses it with the corners.
 * toCrop() re-enters the confirm screen with the confirmed frame kept. */
export interface PhotoApi {
  /** True from the dropzone entry until the recovered model opens in the editor. */
  active: boolean;
  state: PhotoScreen;
  photoUrl: string | null;
  result: PhotoResult | null;
  visionState: VisionState;
  visionBytes: number | null;
  /** Legacy (C6b removes it with the crop machine): the old normalized crop
   * pins, no longer shown or sent; the confirm screen reads confirm.corners. */
  corners: [number, number][];
  /** Legacy (C6b): always null, detect_quad is never called. */
  detectedQuad: [number, number][] | null;
  /** Legacy (C6b): always false, detect_quad is never called. */
  detectPending: boolean;
  /** Legacy (C6b): the old crop machine's pin source. */
  quadSource: QuadSource;
  /** C3b: the confirm screen. */
  confirm: ConfirmApi;
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
  /** Legacy (C6b): moves the old crop machine's pins only. */
  setCorner: (index: number, xy: [number, number]) => void;
  /** Legacy (C6b): the confirm screen has no Reset to auto (criteria U3-4). */
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

type ConfirmView = Omit<ConfirmApi, "setCorner" | "setMode" | "setBands" | "setCounts">;

const copyPoint = (p: Point): Point => ({ x: p.x, y: p.y });

// Copies, so a flow that edits its objects in place still hands React new
// values and every memo on them recomputes.
function readConfirmView(flow: ConfirmFlow): ConfirmView {
  const c = flow.corners;
  return {
    status: flow.status,
    error: flow.error,
    size: flow.size ? { width: flow.size.width, height: flow.size.height } : null,
    mode: flow.mode,
    corners: c
      ? {
          top_left: copyPoint(c.top_left),
          top_right: copyPoint(c.top_right),
          bottom_right: copyPoint(c.bottom_right),
          bottom_left: copyPoint(c.bottom_left),
        }
      : null,
    bands: flow.bands.map((band) => ({ width_squares: band.width_squares })),
    across: { ...flow.across },
    down: { ...flow.down },
    staging: flow.staging,
    squareEighths: flow.squareEighths,
    blocked: flow.blocked,
    canContinue: flow.canContinue,
  };
}

function closeBitmap(bitmap: ImageBitmap | null): void {
  if (bitmap && typeof bitmap.close === "function") bitmap.close();
}

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
  const confirmRef = useRef<ConfirmFlow>(new ConfirmFlow());
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
  const [confirmView, setConfirmView] = useState<ConfirmView>(() => readConfirmView(confirmRef.current));

  // A pin drag syncs on every pointer move, so it refreshes the confirm
  // snapshot alone rather than every mirrored value.
  const syncConfirm = useCallback(() => {
    setConfirmView(readConfirmView(confirmRef.current));
  }, []);

  // mirror the pure machines into React state after every transition
  const syncPhoto = useCallback(() => {
    const m = machineRef.current;
    setPhotoState(m.state);
    setCorners(m.corners);
    setDetectedQuad(m.detectedQuad);
    setDetectPending(m.detectPending);
    setQuadSource(m.quadSource);
    setSizeView(readSizeView(sizeRef.current));
    setConfirmView(readConfirmView(confirmRef.current));
  }, []);

  const photoUrlRef = useRef<string | null>(null);
  photoUrlRef.current = photoUrl;
  // The decoded photo, EXIF applied: Continue cuts its crop from this.
  const bitmapRef = useRef<ImageBitmap | null>(null);
  const stagedBytesRef = useRef<Uint8Array | null>(null);
  const stagedDimsRef = useRef<{ width: number; height: number } | null>(null);
  const stagedTokenRef = useRef<string | null>(null);
  const reverseTokenRef = useRef<{ cancelled: boolean }>({ cancelled: false });
  const retryGateRef = useRef<(() => void) | null>(null);
  const prefetchedRef = useRef(false);

  // ---- S6 photo reverse flow (issue #46) ---------------------------------
  //
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

  /** Forgets the decoded photo and everything staged from it (web-09, ux-16). */
  const dropStaged = useCallback(() => {
    closeBitmap(bitmapRef.current);
    bitmapRef.current = null;
    stagedBytesRef.current = null;
    stagedDimsRef.current = null;
    stagedTokenRef.current = null;
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
  const enginePhase = useEngineStatus().phase;
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
    ): Promise<ReverseOutcome> => {
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

  /** Stage the staged crop's bytes into the worker once; the token is
   * reused by analyze and re-staged if a worker restart wiped it. */
  const ensureStagedToken = useCallback(async (): Promise<string | null> => {
    if (stagedTokenRef.current) return stagedTokenRef.current;
    const bytes = stagedBytesRef.current;
    if (!bytes) return null;
    const staged = await engineRef.current.call<{ token: string }>("stage_photo", bytes);
    // Bytes replaced while this staged (a newer photo or crop) keep their own
    // token slot empty, so a later read never reuses this one (web-09).
    if (stagedBytesRef.current === bytes) stagedTokenRef.current = staged.token;
    return staged.token;
  }, []);

  // C3b stage(): the dropzone stays up while the file decodes; only a photo
  // the browser can decode opens the confirm screen (ux-16).
  const stage = useCallback(
    async (file: File): Promise<void> => {
      const flow = confirmRef.current;
      const seq = flow.newPhoto();
      dropStaged();
      setSessionPhoto(null);
      setPhotoActive(true);
      setPhotoResult(null);
      sizeRef.current.reset();
      syncPhoto();
      let bitmap: ImageBitmap;
      try {
        bitmap = await decodePhoto(file);
      } catch (error) {
        const message =
          error instanceof Error && error.message
            ? error.message
            : "This file could not be opened as a photo. Try another one.";
        if (flow.decodeFailed(seq, message)) syncPhoto();
        return;
      }
      if (!flow.decoded(seq, { width: bitmap.width, height: bitmap.height })) {
        closeBitmap(bitmap);
        return;
      }
      bitmapRef.current = bitmap;
      // The img element honors EXIF orientation as createImageBitmap does, so
      // the pins' pixel frame is the decoded photo's.
      setSessionPhoto(URL.createObjectURL(file));
      const machineSeq = machineRef.current.enterCrop();
      machineRef.current.detectionFailed(machineSeq);
      syncPhoto();
    },
    [dropStaged, setSessionPhoto, syncPhoto],
  );

  // A10's default square size for typed band widths (C3a carried item, #149):
  // sized from the read's own estimate; a failure leaves it unset.
  const loadSquareSize = useCallback(
    async (model: QuiltModel, seq: number): Promise<void> => {
      let eighths: number | null = null;
      try {
        const raw = await engineRef.current.call<unknown>(
          "size_pattern",
          JSON.stringify(model),
          JSON.stringify({ source: "default" }),
        );
        eighths = parseSizeResult(raw).model.center.cell_size;
      } catch {
        eighths = null;
      }
      const flow = confirmRef.current;
      if (!flow.isCurrent(seq)) return;
      flow.setSquareEighths(eighths);
      syncConfirm();
    },
    [syncConfirm],
  );

  // C3b analyze() (Continue): stage the confirmed crop, then reverse it with
  // the corners in the crop's pixel frame, moved or not (criteria U3-5).
  // Every await is followed by a staleness check against the staging
  // sequence, so a read never finishes into a newer photo (web-09).
  const analyze = useCallback(async (): Promise<void> => {
    const flow = confirmRef.current;
    const frame = flow.beginStaging();
    syncConfirm();
    if (!frame) return;
    const { seq } = frame;
    let plan: CropPlan;
    try {
      const bitmap = bitmapRef.current;
      if (!bitmap) throw new Error("no decoded photo");
      const squares = frameSquares(frame.mode, frame.across, frame.down, frame.bands);
      const staged = await stagePhoto(bitmap, frame.corners, squarePx(frame.corners, squares));
      if (!flow.isCurrent(seq)) return;
      stagedBytesRef.current = staged.bytes;
      stagedDimsRef.current = { width: staged.plan.staged.width, height: staged.plan.staged.height };
      stagedTokenRef.current = null;
      plan = staged.plan;
    } catch {
      if (!flow.isCurrent(seq)) return;
      flow.endStaging(seq);
      syncConfirm();
      toast.push("That photo didn’t come through, try another?", "error");
      return;
    }
    flow.endStaging(seq);
    machineRef.current.analyze();
    syncPhoto();
    setPhotoResult(null);
    const token = { cancelled: false };
    reverseTokenRef.current = token;
    const stale = () => token.cancelled || !flow.isCurrent(seq);
    try {
      const options: Record<string, unknown> = {
        corners: CORNER_NAMES.map((name) => [plan.corners[name].x, plan.corners[name].y]),
        // Decoded-photo pixels: the old bridge ignores it; B2a's
        // read_confirmed maps the crop back with it (#101).
        crop_offset: { x: plan.offset.x, y: plan.offset.y },
      };
      const sized = sizeRef.current.sizeOptions();
      if (sized) {
        options.finished_width = sized.finished_width;
        options.finished_height = sized.finished_height;
      }
      const optionsJson = JSON.stringify(options);
      let staged = await ensureStagedToken();
      if (stale()) return;
      if (!staged) throw new Error("no staged photo");
      let outcome: ReverseOutcome;
      try {
        outcome = await runReverse(staged, optionsJson, token);
      } catch (error) {
        if (stale()) return;
        // a worker restart wiped MEMFS: the token is stale; re-stage once
        const wiped =
          error instanceof EngineError &&
          error.kind === "value" &&
          /not found/i.test(error.message);
        if (!wiped) throw error;
        stagedTokenRef.current = null;
        staged = await ensureStagedToken();
        if (stale()) return;
        if (!staged) throw error;
        outcome = await runReverse(staged, optionsJson, token);
      }
      if (stale()) return;
      applyReverse(outcome.model, outcome.ms, outcome.verdict, outcome.diagnostics, outcome.requested, outcome.achieved);
      machineRef.current.results();
      syncPhoto();
      void loadSquareSize(outcome.model, seq);
    } catch {
      if (stale()) return;
      toast.push("That photo didn’t come through, try another?", "error");
      machineRef.current.seedFromConfirmed();
      syncPhoto();
    }
  }, [ensureStagedToken, runReverse, applyReverse, loadSquareSize, syncConfirm, syncPhoto, toast]);

  const startSample = useCallback(async (): Promise<void> => {
    // sample bypass (S2 contract): auto-confirmed full-frame render, no crop
    confirmRef.current.clear();
    dropStaged();
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
  }, [dropStaged, runReverse, applyReverse, setSessionPhoto, syncPhoto, toast]);

  const cancel = useCallback(() => {
    // PARITY item 14 (sprint 2, frozen): cancel returns to the dropzone;
    // the worker restart also invalidates the staged token by design
    reverseTokenRef.current.cancelled = true;
    retryGateRef.current?.();
    engineRef.current.restart();
    confirmRef.current.clear();
    dropStaged();
    machineRef.current.cancel();
    syncPhoto();
    setPhotoResult(null);
  }, [dropStaged, syncPhoto]);

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

  // "Adjust the crop" from results: back to the confirm screen, where the
  // flow still holds the confirmed corners, counts, bands and frame.
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
    // Back discards the staged photo (UI-SPEC section 1 flow rules; U3-6)
    confirmRef.current.clear();
    dropStaged();
    machineRef.current.backFromCrop();
    syncPhoto();
    setSessionPhoto(null);
  }, [dropStaged, setSessionPhoto, syncPhoto]);

  const backToDropzone = useCallback(() => {
    confirmRef.current.clear();
    dropStaged();
    setPhotoActive(true);
    machineRef.current.reset();
    syncPhoto();
    setPhotoResult(null);
    setSessionPhoto(null);
    // vision prefetch fires on photo-flow ENTRY, not on drop (S2 contract);
    // this is also the entry path from the start screen
    engineRef.current.prefetchVision();
  }, [dropStaged, setSessionPhoto, syncPhoto]);

  const exitToEditor = useCallback(() => {
    // The editor never returns to Confirm, so the decoded bitmap (192 MB for a
    // 48 MP photo) goes now rather than at the next photo.
    confirmRef.current.clear();
    dropStaged();
    setPhotoActive(false);
    setPhotoState("idle");
    // photoUrl stays: the editor compare affordance reads it until reload.
  }, [dropStaged]);

  const reset = useCallback(() => {
    confirmRef.current.clear();
    dropStaged();
    setPhotoActive(false);
    machineRef.current.reset();
    syncPhoto();
    setPhotoResult(null);
    setShowUncertain(false);
    setSessionPhoto(null);
  }, [dropStaged, setSessionPhoto, syncPhoto]);

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

  const confirmActions = useMemo(
    () => ({
      setCorner: (name: CornerName, point: Point) => {
        confirmRef.current.setCorner(name, point);
        syncConfirm();
      },
      setMode: (mode: FrameMode) => {
        confirmRef.current.setMode(mode);
        syncConfirm();
      },
      setBands: (bands: BorderBand[]) => {
        confirmRef.current.setBands(bands);
        syncConfirm();
      },
      setCounts: (across: AxisCount, down: AxisCount) => {
        confirmRef.current.setCounts(across, down);
        syncConfirm();
      },
    }),
    [syncConfirm],
  );

  const confirm = useMemo<ConfirmApi>(
    () => ({ ...confirmView, ...confirmActions }),
    [confirmView, confirmActions],
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
      confirm,
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
      confirm,
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
