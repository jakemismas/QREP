/**
 * React seam over EngineClient (S2). One client per app; status streamed
 * into React state; retry re-boots the disposable worker.
 */
import { createContext, useContext, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { EngineClient, type EngineStatus, type WorkerLike } from "./rpc";
import type { ModelSummary } from "../model/types";

export interface Engine {
  status: EngineStatus;
  retry: () => void;
  /** bridge.validate: model JSON -> summary (rejects with EngineError). */
  validate: (modelJson: string) => Promise<ModelSummary>;
  call: <T>(method: string, ...args: unknown[]) => Promise<T>;
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
      status,
      retry: () => client.restart(),
      validate: (modelJson: string) => client.call<ModelSummary>("validate", modelJson),
      call: (method, ...args) => client.call(method, ...args),
    }),
    [client, status],
  );

  return <EngineContext.Provider value={engine}>{children}</EngineContext.Provider>;
}

export function useEngine(): Engine {
  const engine = useContext(EngineContext);
  if (engine === null) throw new Error("useEngine requires EngineProvider");
  return engine;
}
