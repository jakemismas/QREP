/**
 * React seam over EngineClient (S2). One client per app; status streamed
 * into React state; retry re-boots the disposable worker.
 *
 * The calls and the status travel in two contexts (C1a, issue #146). Every
 * bridge call flips the status to busy and back, so a single context value
 * holding both would change on every call; the calls value is memoized on the
 * client alone and never changes.
 */
import { createContext, useContext, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { EngineClient, type EngineStatus, type VisionState, type WorkerLike } from "./rpc";
import type { ModelSummary } from "../model/types";

export interface Engine {
  status: EngineStatus;
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

type EngineCalls = Omit<Engine, "status">;

function makeWorker(): WorkerLike {
  const worker = new Worker(new URL("./worker.ts", import.meta.url), { type: "module" });
  worker.postMessage({ type: "init", baseUrl: new URL(".", document.baseURI).href });
  return worker as unknown as WorkerLike;
}

const EngineContext = createContext<EngineCalls | null>(null);
const EngineStatusContext = createContext<EngineStatus | null>(null);

export function EngineProvider({ children }: { children: ReactNode }) {
  const client = useMemo(() => new EngineClient(makeWorker), []);
  const [status, setStatus] = useState<EngineStatus>(client.getStatus());

  useEffect(() => {
    const unsubscribe = client.onStatus(setStatus);
    client.start();
    return unsubscribe;
  }, [client]);

  const calls = useMemo<EngineCalls>(
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
    <EngineContext.Provider value={calls}>
      <EngineStatusContext.Provider value={status}>{children}</EngineStatusContext.Provider>
    </EngineContext.Provider>
  );
}

/** The calls plus the current status; a component that reads it re-renders on
 * every status change, while the calls themselves stay the same functions. */
export function useEngine(): Engine {
  const calls = useContext(EngineContext);
  const status = useContext(EngineStatusContext);
  const engine = useMemo(
    () => (calls !== null && status !== null ? { ...calls, status } : null),
    [calls, status],
  );
  if (engine === null) throw new Error("useEngine requires EngineProvider");
  return engine;
}
