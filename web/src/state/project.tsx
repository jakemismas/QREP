/*
 * Project state (S2, issue #42). Holds the currently-open quilt model and its
 * bridge-derived summary. Rendering reads `model` (parsed synchronously) and
 * NEVER waits on the engine; `summary` is filled once the engine reaches
 * `ready`, so the editor opens and draws while the chip is still booting.
 */
import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import { useEngine } from "../engine/useEngine";
import { EngineError } from "../engine/rpc";
import { parseProjectFile } from "../model/types";
import type { QuiltModel, ModelSummary } from "../model/types";
import { useToast } from "../ui";

const DEFAULT_NAME = "My quilt project";
const DEMO_URL = "fixtures/double_irish_chain.json";

interface ProjectApi {
  modelJson: string | null;
  model: QuiltModel | null;
  name: string;
  summary: ModelSummary | null;
  openDemo: () => Promise<boolean>;
  openFromText: (text: string, fallbackName: string) => boolean;
  rename: (name: string) => void;
  goHome: () => void;
}

const ProjectContext = createContext<ProjectApi | null>(null);

function looksLikeModel(model: QuiltModel | undefined | null): boolean {
  return Boolean(model && model.center && model.center.cells && model.palette && model.palette.fabrics);
}

export function ProjectProvider({ children }: { children: ReactNode }) {
  const engine = useEngine();
  const toast = useToast();

  const [modelJson, setModelJson] = useState<string | null>(null);
  const [model, setModel] = useState<QuiltModel | null>(null);
  const [name, setName] = useState<string>(DEFAULT_NAME);
  const [summary, setSummary] = useState<ModelSummary | null>(null);

  // Guards for the validate effect: which model-JSON has been sent to
  // validate (so it runs once per model) and what the live model is (so a
  // late-resolving validate for a replaced model cannot clobber the summary).
  const validatedRef = useRef<string | null>(null);
  const modelJsonRef = useRef<string | null>(null);
  modelJsonRef.current = modelJson;

  const openFromText = useCallback(
    (text: string, fallbackName: string): boolean => {
      let parsed: { modelJson: string; name: string };
      try {
        parsed = parseProjectFile(text);
      } catch (err) {
        const detail = err instanceof Error ? err.message : String(err);
        toast.push(`malformed JSON: ${detail}`, "error");
        return false;
      }
      let parsedModel: QuiltModel;
      try {
        parsedModel = JSON.parse(parsed.modelJson) as QuiltModel;
      } catch (err) {
        const detail = err instanceof Error ? err.message : String(err);
        toast.push(`malformed JSON: ${detail}`, "error");
        return false;
      }
      if (!looksLikeModel(parsedModel)) {
        toast.push("That file isn’t a QREP project — nothing was changed.", "error");
        return false;
      }
      const displayName =
        parsed.name && parsed.name !== "Untitled" ? parsed.name : fallbackName;
      validatedRef.current = null;
      setModelJson(parsed.modelJson);
      setModel(parsedModel);
      setName(displayName || DEFAULT_NAME);
      setSummary(null);
      return true;
    },
    [toast],
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

  const rename = useCallback((next: string) => {
    setName(next.trim() || DEFAULT_NAME);
  }, []);

  const goHome = useCallback(() => {
    validatedRef.current = null;
    setModelJson(null);
    setModel(null);
    setSummary(null);
    setName(DEFAULT_NAME);
  }, []);

  const phase = engine.status.phase;
  useEffect(() => {
    if (modelJson === null || phase !== "ready") return;
    if (validatedRef.current === modelJson) return;
    validatedRef.current = modelJson;
    const target = modelJson;
    engine.validate(target).then(
      (result) => {
        if (modelJsonRef.current === target) setSummary(result);
      },
      (err: unknown) => {
        const message = err instanceof EngineError ? err.message : "validation failed";
        toast.push(message, "error");
      },
    );
  }, [modelJson, phase, engine, toast]);

  const api: ProjectApi = {
    modelJson,
    model,
    name,
    summary,
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
