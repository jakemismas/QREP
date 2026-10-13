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
import { isEngineRestart, isWorkerFailure } from "../pattern/patternPdf";
import type { CensusTarget } from "../pattern/patternPdf";
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
  /** Counts fresh replacements (a newly opened quilt, or none), so a screen
   * bound to one quilt can tell an opened quilt from an edit. */
  opened: number;
  /** `opened` as of the latest replaceModel, ahead of the render that shows
   * it, so a caller can bind to the quilt it has just opened. */
  latestOpened: () => number;
  /** True while the open model's census failed; Your pattern shows it with a Retry. */
  censusFailed: boolean;
  /** The census request, which Your pattern's Retry sends again (retryPattern). */
  censusRequest: CensusTarget;
  /** Install the test for when a failed census raises no error toast: Your
   * pattern reports it on its own line, with Retry, in a plain sentence. */
  quietCensusWhen: (quiet: () => boolean) => void;
}

export const ModelContext = createContext<ModelApi | null>(null);

export interface CensusOptions {
  validate: (modelJson: string) => Promise<ModelSummary>;
  onSummary: (summary: ModelSummary) => void;
  onError: (message: string) => void;
  /** Called whenever `failed` may have changed. Required, so the screen that
   * shows a failed census cannot be left unwired. */
  onFailedChange: (failed: boolean) => void;
}

/**
 * Coalesced validation (the fabric census), framework-free so vitest drives
 * it against the engine client without a DOM. Only one validate is in flight
 * at a time; newer models overwrite the pending request, and a result applies
 * only if it is still the newest (version === latest), so a late resolve for
 * a replaced model cannot clobber the census.
 *
 * A failed validate of the newest model stays on record until a newer request
 * or model, so Your pattern's Retry (pattern/patternPdf.ts retryPattern) can
 * send it again: no model change would, and the census would otherwise wait
 * on "counting squares" for good.
 */
export class CensusQueue implements CensusTarget {
  private readonly options: CensusOptions;
  private version = 0;
  private pending: { json: string; version: number } | null = null;
  private validating = false;
  private failure: { json: string; version: number; workerDown: boolean } | null = null;

  constructor(options: CensusOptions) {
    this.options = options;
  }

  /** True while the newest model's census failed. */
  get failed(): boolean {
    return this.failure !== null && this.failure.version === this.version;
  }

  /** True while that failure is the worker's own (isWorkerFailure). */
  get workerDown(): boolean {
    return this.failed && this.failure!.workerDown;
  }

  /** A newer model replaced the open one: drop its waiting request, and any
   * result still in flight for it. */
  replace(): void {
    this.version += 1;
    this.pending = null;
    this.setFailure(null);
  }

  /** Ask for the census of the newest model. */
  request(modelJson: string): void {
    this.pending = { json: modelJson, version: this.version };
    this.setFailure(null);
    this.drain();
  }

  /** Ask again for the newest model's census, if it failed. */
  retry(): void {
    if (this.failed) this.request(this.failure!.json);
  }

  private setFailure(failure: CensusQueue["failure"]): void {
    this.failure = failure;
    this.options.onFailedChange(this.failed);
  }

  private drain(): void {
    if (this.validating) return;
    const want = this.pending;
    if (!want) return;
    this.pending = null;
    this.validating = true;
    this.options
      .validate(want.json)
      .then(
        (result) => {
          if (want.version === this.version) this.options.onSummary(result);
        },
        (err: unknown) => {
          if (want.version !== this.version) return;
          if (isEngineRestart(err)) {
            // A restart (Retry after a failed boot) drops the queue, but the
            // census is still wanted: it goes again, to the new worker,
            // unless a newer model's request already waits.
            this.pending ??= want;
            return;
          }
          // A request for the same model that waits behind this one is still
          // to run, so nothing has failed yet.
          if (this.pending === null) {
            this.setFailure({ json: want.json, version: want.version, workerDown: isWorkerFailure(err) });
          }
          this.options.onError(err instanceof EngineError ? err.message : "validation failed");
        },
      )
      .finally(() => {
        this.validating = false;
        this.drain();
      });
  }
}

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
  // The queue outlives renders, so it reads the toast through a ref.
  const toastRef = useRef(toast);
  toastRef.current = toast;

  const [model, setModel] = useState<QuiltModel | null>(null);
  const [name, setName] = useState<string>(DEFAULT_NAME);
  const [summary, setSummary] = useState<ModelSummary | null>(null);
  const [opened, setOpened] = useState(0);
  const openedRef = useRef(0);
  const [censusFailed, setCensusFailed] = useState(false);
  // Read when a census fails, not when the queue is made, so the screen
  // showing at that moment decides.
  const quietRef = useRef<() => boolean>(() => false);

  const censusRef = useRef<CensusQueue | null>(null);
  censusRef.current ??= new CensusQueue({
    validate: (json) => engineRef.current.validate(json),
    onSummary: setSummary,
    onError: (message) => {
      if (!quietRef.current()) toastRef.current.push(message, "error");
    },
    onFailedChange: setCensusFailed,
  });
  const censusRequest: CensusTarget = censusRef.current;

  // The model the latest replaceModel installed. A render's effect can run
  // after a newer replaceModel (a non-urgent render's effects wait for a
  // scheduler task, and a keypress can land first); that stale effect must not
  // send its older model under the newer version.
  const latestRef = useRef<QuiltModel | null>(null);

  const replaceModel = useCallback((next: QuiltModel | null, fresh: boolean) => {
    // The same model keeps its census and the validation already in flight
    // for it; no effect would run to send another.
    if (next === latestRef.current) return;
    // Bump the version now, not in the effect, so a validation still in flight
    // for the replaced model is dropped even if it lands before the next render.
    censusRef.current?.replace();
    latestRef.current = next;
    setModel(next);
    if (fresh) {
      setSummary(null);
      openedRef.current += 1;
      setOpened(openedRef.current);
    }
  }, []);

  useEffect(() => {
    if (!model || model !== latestRef.current) return;
    censusRef.current?.request(JSON.stringify(model));
  }, [model]);

  const latestModel = useCallback(() => latestRef.current, []);
  const latestOpened = useCallback(() => openedRef.current, []);
  const quietCensusWhen = useCallback((quiet: () => boolean) => {
    quietRef.current = quiet;
  }, []);

  return useMemo(
    () => ({
      model,
      name,
      summary,
      replaceModel,
      setName,
      latestModel,
      opened,
      latestOpened,
      censusFailed,
      censusRequest,
      quietCensusWhen,
    }),
    [
      model,
      name,
      summary,
      replaceModel,
      latestModel,
      opened,
      latestOpened,
      censusFailed,
      censusRequest,
      quietCensusWhen,
    ],
  );
}

export function useModel(): ModelApi {
  const value = useContext(ModelContext);
  if (value === null) throw new Error("useModel requires ProjectProvider");
  return value;
}
