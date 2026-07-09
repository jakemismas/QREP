/// <reference lib="webworker" />
/**
 * Engine worker (S2, issue #42): boots the vendored Pyodide runtime once,
 * then serves bridge calls over the typed RPC protocol (see rpc.ts). The
 * worker is disposable - bridge calls are stateless, the model JSON travels
 * with every call - so the client may terminate and re-boot at any time.
 */
import type { PyodideInterface } from "pyodide";

interface InitMessage {
  type: "init";
  baseUrl: string;
}

interface CallMessage {
  type: "call";
  id: number;
  method: string;
  args: unknown[];
}

type InMessage = InitMessage | CallMessage;

type LoadPyodide = (options: { indexURL: string }) => Promise<PyodideInterface>;

// The bridge surface; anything else is rejected without touching Python.
const BRIDGE_METHODS = new Set([
  "validate",
  "plan",
  "export_cutlist_md",
  "export_cutlist_csv",
  "export_yardage",
  "export_svg",
  "export_pdf",
  "render",
  "reverse",
  "compare",
  "resize_locked",
  "resize_unlocked",
]);

const scope = self as unknown as DedicatedWorkerGlobalScope;
let pyodidePromise: Promise<PyodideInterface> | null = null;

async function boot(baseUrl: string): Promise<PyodideInterface> {
  const progress = (step: string) => scope.postMessage({ type: "boot-progress", step });
  progress("Loading the Python engine");
  const { loadPyodide } = (await import(
    /* @vite-ignore */ `${baseUrl}pyodide/pyodide.mjs`
  )) as { loadPyodide: LoadPyodide };
  const pyodide = await loadPyodide({ indexURL: `${baseUrl}pyodide/` });
  progress("Loading engine packages");
  await pyodide.loadPackage(["numpy", "opencv-python", "pillow", "pydantic", "micropip"]);
  progress("Loading the qrep engine");
  const manifest = (await (await fetch(`${baseUrl}wheels/manifest.json`)).json()) as {
    pypiWheels: string[];
    qrepWheel: string;
  };
  const wheelUrls = [...manifest.pypiWheels, manifest.qrepWheel].map(
    (file) => `${baseUrl}wheels/${file}`,
  );
  pyodide.globals.set("wheel_urls", pyodide.toPy(wheelUrls));
  await pyodide.runPythonAsync(
    "import micropip\nawait micropip.install(list(wheel_urls), deps=False)",
  );
  pyodide.runPython("import qrep.bridge");
  return pyodide;
}

async function serve(message: CallMessage): Promise<void> {
  const fail = (kind: string, text: string) =>
    scope.postMessage({
      type: "result",
      id: message.id,
      envelope: { ok: false, error: { kind, message: text } },
    });
  if (!BRIDGE_METHODS.has(message.method)) {
    fail("value", `unknown bridge method: ${message.method}`);
    return;
  }
  if (pyodidePromise === null) {
    fail("worker", "engine is not booted");
    return;
  }
  try {
    const pyodide = await pyodidePromise;
    const bridge = pyodide.pyimport("qrep.bridge");
    try {
      const raw: string = bridge[message.method](...message.args);
      scope.postMessage({ type: "result", id: message.id, envelope: JSON.parse(raw) });
    } finally {
      bridge.destroy();
    }
  } catch {
    // The bridge itself wraps engine errors; reaching here means the worker
    // plumbing failed (boot rejection or ffi error) - keep it generic.
    fail("internal", "engine call failed in the worker");
  }
}

scope.onmessage = (event: MessageEvent<InMessage>) => {
  const message = event.data;
  if (message.type === "init") {
    pyodidePromise = boot(message.baseUrl);
    pyodidePromise
      .then(() => scope.postMessage({ type: "boot-done" }))
      .catch((error: unknown) =>
        scope.postMessage({
          type: "boot-failed",
          message: error instanceof Error ? error.message : String(error),
        }),
      );
  } else if (message.type === "call") {
    void serve(message);
  }
};
