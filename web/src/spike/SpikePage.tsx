import { useCallback, useRef, useState } from "react";

/**
 * S0 spike page (issue #40): a bare page that runs the wasm feasibility
 * checks in a Web Worker and reports results as JSON for the e2e spec.
 * This page is replaced by the real app shell in S2.
 */

interface SpikeState {
  status: "idle" | "running" | "done" | "failed";
  log: string[];
  results?: unknown;
  error?: string;
}

interface WorkerMessage {
  type: "progress" | "done" | "error";
  stage?: string;
  results?: unknown;
  error?: string;
}

export default function App() {
  const [state, setState] = useState<SpikeState>({ status: "idle", log: [] });
  const workerRef = useRef<Worker | null>(null);

  const run = useCallback(() => {
    workerRef.current?.terminate();
    const worker = new Worker(new URL("./spikeWorker.ts", import.meta.url), {
      type: "module",
    });
    workerRef.current = worker;
    setState({ status: "running", log: ["Starting the engine worker"] });
    worker.onmessage = (event: MessageEvent<WorkerMessage>) => {
      const message = event.data;
      if (message.type === "progress" && message.stage !== undefined) {
        const stage = message.stage;
        setState((s) => ({ ...s, log: [...s.log, stage] }));
      } else if (message.type === "done") {
        setState((s) => ({ ...s, status: "done", results: message.results }));
      } else if (message.type === "error") {
        setState((s) => ({ ...s, status: "failed", error: message.error }));
      }
    };
    worker.onerror = (event) => {
      setState((s) => ({ ...s, status: "failed", error: event.message }));
    };
    worker.postMessage({ type: "run", baseUrl: new URL(".", document.baseURI).href });
  }, []);

  return (
    <main data-spike-status={state.status} style={{ fontFamily: "system-ui", margin: "2rem" }}>
      <h1>QREP web spike (S0)</h1>
      <p>
        Proves the QREP engine runs in this browser: package closure, cut-list golden, PDF
        booklet, and photo reverse. Everything runs on your device; nothing is uploaded.
      </p>
      <button
        type="button"
        data-testid="run-spike"
        onClick={run}
        disabled={state.status === "running"}
      >
        Run spike
      </button>
      <ol>
        {state.log.map((line, index) => (
          <li key={index}>{line}</li>
        ))}
      </ol>
      {state.error !== undefined && <pre data-testid="spike-error">{state.error}</pre>}
      {state.results !== undefined && (
        <pre data-testid="spike-results" style={{ whiteSpace: "pre-wrap", maxWidth: "60rem" }}>
          {JSON.stringify(state.results, null, 2)}
        </pre>
      )}
    </main>
  );
}
