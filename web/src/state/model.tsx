/*
 * Model state (C1a, issue #146): the open quilt as plain React state, its
 * name, and the fabric census, which is the bridge validation summary of that
 * model. Exports, plans, validation and the round trip read the model here,
 * never through the editor's store, so the editor can leave (C6a) without
 * touching them.
 */
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import { useEngine } from "../engine/useEngine";
import type { Engine } from "../engine/useEngine";
import { EngineError } from "../engine/rpc";
import type { QuiltModel, ModelSummary } from "../model/types";
import { useToast } from "../ui";

export const DEFAULT_NAME = "My quilt project";
export const DEMO_URL = "fixtures/double_irish_chain.json";

export interface ModelApi {
  model: QuiltModel | null;
  name: string;
  /** The fabric census: the bridge's validation summary of `model`. */
  summary: ModelSummary | null;
  /** Replace the open model. A fresh model (a newly opened quilt, or none)
   * drops the census of the one it replaces; an edit keeps the old census on
   * screen until the new one lands. */
  replaceModel: (next: QuiltModel | null, fresh: boolean) => void;
  setName: (name: string) => void;
  /** The model the latest replaceModel installed, ahead of the render that
   * shows it, so a result that lands late can tell its model was replaced. */
  latestModel: () => QuiltModel | null;
}

export const ModelContext = createContext<ModelApi | null>(null);

export function useModelState(): ModelApi {
  const engine = useEngine();
  // ToastProvider rebuilds its value on every toast; keyed on that object,
  // the validation effect below would re-validate after each toast.
  const { push } = useToast();
  const toast = useMemo(() => ({ push }), [push]);

  // `engine.validate` delegates to a stable client, but keep the latest ref so
  // scheduled validations never fire through a stale closure.
  const engineRef = useRef<Engine>(engine);
  engineRef.current = engine;

  const [model, setModel] = useState<QuiltModel | null>(null);
  const [name, setName] = useState<string>(DEFAULT_NAME);
  const [summary, setSummary] = useState<ModelSummary | null>(null);

  // ---- coalesced validation (the fabric census) ---------------------------
  //
  // Only one validate is in flight at a time; newer models overwrite the
  // pending request, and a result applies only if it is still the newest
  // (version === latest), so a late resolve for a replaced model cannot
  // clobber the census.

  const versionRef = useRef(0);
  const pendingRef = useRef<{ json: string; version: number } | null>(null);
  const validatingRef = useRef(false);
  // The model the latest replaceModel installed. A render's effect can run
  // after a newer replaceModel (a non-urgent render's effects wait for a
  // scheduler task, and a keypress can land first); that stale effect must not
  // send its older model under the newer version.
  const latestRef = useRef<QuiltModel | null>(null);

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

  const replaceModel = useCallback((next: QuiltModel | null, fresh: boolean) => {
    // The same model keeps its census and the validation already in flight
    // for it; no effect would run to send another.
    if (next === latestRef.current) return;
    // Bump the version now, not in the effect, so a validation still in flight
    // for the replaced model is dropped even if it lands before the next render.
    versionRef.current += 1;
    pendingRef.current = null;
    latestRef.current = next;
    setModel(next);
    if (fresh) setSummary(null);
  }, []);

  useEffect(() => {
    if (!model || model !== latestRef.current) return;
    pendingRef.current = { json: JSON.stringify(model), version: versionRef.current };
    drainValidation();
  }, [model, drainValidation]);

  const latestModel = useCallback(() => latestRef.current, []);

  return useMemo(
    () => ({ model, name, summary, replaceModel, setName, latestModel }),
    [model, name, summary, replaceModel, latestModel],
  );
}

export function useModel(): ModelApi {
  const value = useContext(ModelContext);
  if (value === null) throw new Error("useModel requires ProjectProvider");
  return value;
}
