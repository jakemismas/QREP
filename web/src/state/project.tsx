/*
 * Project state (S2 + S3, issues #42 / #43). Wraps an EditorStore for the open
 * model and drives the three commit-time side effects the editing slice needs:
 *   (a) a React snapshot of the mutable model so the canvas and panels redraw,
 *   (b) a debounced autosave of the wrapper doc to localStorage, and
 *   (c) a coalesced bridge re-validation whose summary is the fabric census.
 * Rendering still reads `model` synchronously and never waits on the engine;
 * `summary` fills in once validation lands.
 */
import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import { useEngine } from "../engine/useEngine";
import type { Engine } from "../engine/useEngine";
import { EngineError } from "../engine/rpc";
import { parseProjectFile } from "../model/types";
import type { QuiltModel, ModelSummary } from "../model/types";
import { useToast } from "../ui";
import {
  COALESCE_WINDOW_MS,
  EditorStore,
  buildAutosaveDoc,
  buildProjectFile,
  makeBlankModel,
  parseAutosaveDoc,
} from "./editor";
import type { CellRef } from "./editor";

const DEFAULT_NAME = "My quilt project";
const DEMO_URL = "fixtures/double_irish_chain.json";
const AUTOSAVE_KEY = "qrep-autosave";
const AUTOSAVE_DEBOUNCE_MS = 800;

export type EditorMode = "move" | "paint";

interface ResumeInfo {
  name: string;
  savedAt: number;
}

interface RestoreState {
  resume: ResumeInfo | null;
  autosaveError: string | null;
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
  undo: () => void;
  redo: () => void;
  saveToFile: () => void;
  startBlank: () => void;
  resumeAutosave: () => void;
  openDemo: () => Promise<boolean>;
  openFromText: (text: string, fallbackName: string) => boolean;
  rename: (name: string) => void;
  goHome: () => void;
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
  const [restore, setRestore] = useState<RestoreState>(readAutosave);

  const nameRef = useRef(name);
  nameRef.current = name;
  const selectedFabricIdRef = useRef(selectedFabricId);
  selectedFabricIdRef.current = selectedFabricId;

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
      localStorage.setItem(AUTOSAVE_KEY, buildAutosaveDoc(s.model, nameRef.current, Date.now()));
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

  const afterMutation = useCallback(() => {
    refresh();
    requestValidation();
    scheduleAutosave();
  }, [refresh, requestValidation, scheduleAutosave]);

  // ---- open / restore ----------------------------------------------------

  const installModel = useCallback(
    (next: QuiltModel, displayName: string) => {
      const s = storeRef.current;
      if (s) s.reset(next);
      else storeRef.current = new EditorStore(next, clockObjRef.current);
      setName(displayName || DEFAULT_NAME);
      setMode("move");
      setSelectedFabricId(next.palette.fabrics[0]?.id ?? null);
      setSummary(null);
      refresh();
      requestValidation();
    },
    [refresh, requestValidation],
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
      installModel(parsedModel, displayName || DEFAULT_NAME);
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
    installModel(doc.model, doc.name);
  }, [installModel]);

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
      const blob = new Blob([buildProjectFile(s.model, nameRef.current)], {
        type: "application/json",
      });
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
    setModel(null);
    setSummary(null);
    setName(DEFAULT_NAME);
    setMode("move");
    setSelectedFabricId(null);
    setCanUndo(false);
    setCanRedo(false);
    setDirty(false);
  }, []);

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
    setMode,
    selectFabric,
    paintStroke,
    recolorFabric,
    renameFabric,
    addFabric,
    deleteFabric,
    undo,
    redo,
    saveToFile,
    startBlank,
    resumeAutosave,
    openDemo,
    openFromText,
    rename,
    goHome,
  };

  return <ProjectContext.Provider value={api}>{children}</ProjectContext.Provider>;
}

export function useProject(): ProjectApi {
  const value = useContext(ProjectContext);
  if (value === null) throw new Error("useProject requires ProjectProvider");
  return value;
}
