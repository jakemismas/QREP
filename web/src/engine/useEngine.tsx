/**
 * React seam over EngineClient (S2). One client per app; status streamed
 * into React state; retry re-boots the disposable worker.
 *
 * The status rides its own context (engineStatus.ts; C1a, issue #146): every
 * bridge call flips it to busy and back, so the engine value holds the calls
 * alone, is memoized on the client, and never changes.
 */
import { createContext, useContext, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { EngineClient, type EngineStatus, type VisionState, type WorkerLike } from "./rpc";
import { EngineStatusContext } from "./engineStatus";
import type { ModelSummary } from "../model/types";

export interface Engine {
  retry: () => void;
  /** Terminate and re-boot the disposable worker (cancel / recover). */
  restart: () => void;
  /** bridge.validate: model JSON -> summary (rejects with EngineError). */
  validate: (modelJson: string) => Promise<ModelSummary>;
  call: <T>(method: string, ...args: unknown[]) => Promise<T>;
  /** Vision wheel lifecycle (S6): subscribe and prefetch. */
  onVision: (listener: (state: VisionState) => void) => () => void;
  prefetchVision: () => void;
}

function makeWorker(): WorkerLike {
  const worker = new Worker(new URL("./worker.ts", import.meta.url), { type: "module" });
  worker.postMessage({ type: "init", baseUrl: new URL(".", document.baseURI).href });
  return worker as unknown as WorkerLike;
}

const EngineContext = createContext<Engine | null>(null);

export function EngineProvider({ children }: { children: ReactNode }) {
  const client = useMemo(() => new EngineClient(makeWorker), []);
  const [status, setStatus] = useState<EngineStatus>(client.getStatus());

  useEffect(() => {
    const unsubscribe = client.onStatus(setStatus);
    client.start();
    return unsubscribe;
  }, [client]);

  const engine = useMemo<Engine>(
    () => ({
      retry: () => client.restart(),
      restart: () => client.restart(),
      validate: (modelJson: string) => client.call<ModelSummary>("validate", modelJson),
      call: (method, ...args) => client.call(method, ...args),
      onVision: (listener) => client.onVision(listener),
      prefetchVision: () => client.prefetchVision(),
    }),
    [client],
  );

  return (
    <EngineContext.Provider value={engine}>
      <EngineStatusContext.Provider value={status}>{children}</EngineStatusContext.Provider>
    </EngineContext.Provider>
  );
}

export function useEngine(): Engine {
  const engine = useContext(EngineContext);
  if (engine === null) throw new Error("useEngine requires EngineProvider");
  return engine;
}
