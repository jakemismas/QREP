/*
 * Engine status context (C1a, issue #146). Every bridge call flips the status
 * to busy and back, so it travels apart from the engine calls: only the
 * components that show or wait on it subscribe, and useEngine()'s value never
 * changes. EngineProvider (useEngine.tsx) provides it.
 */
import { createContext, useContext } from "react";
import type { EngineStatus } from "./rpc";

export const EngineStatusContext = createContext<EngineStatus | null>(null);

export function useEngineStatus(): EngineStatus {
  const status = useContext(EngineStatusContext);
  if (status === null) throw new Error("useEngineStatus requires EngineProvider");
  return status;
}
