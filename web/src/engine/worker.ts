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

interface LoadVisionMessage {
  type: "load-vision";
}

type InMessage = InitMessage | CallMessage | LoadVisionMessage;

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
  "detect_quad",
  "presets",
  "apply_finished_size",
  "resize_locked",
  "resize_unlocked",
]);

// Bridge methods that need cv2: the vision wheel lazy-loads before these
// run (S6). Everything else works on the boot closure alone.
const VISION_METHODS = new Set(["reverse", "reverse_photo", "render", "compare", "detect_quad"]);

const scope = self as unknown as DedicatedWorkerGlobalScope;
let pyodidePromise: Promise<PyodideInterface> | null = null;
let visionPromise: Promise<void> | null = null;
let stagingCounter = 0;
// S2 crop flow (issue #68): the photo is staged ONCE via stage_photo and the
// token (a MEMFS path) is reused across detect_quad and reverse calls, so the
// bytes cross the RPC boundary a single time. The previous token's file is
// unlinked when a new one is staged; a worker restart wipes MEMFS, so stale
// tokens fail with a "not found" value error and the client re-stages.
let stagedTokenPath: string | null = null;

function unlinkQuietly(pyodide: PyodideInterface, path: string): void {
  try {
    pyodide.FS.unlink(path);
  } catch {
    // already gone
  }
}

function ensureVision(): Promise<void> {
  if (visionPromise === null) {
    visionPromise = (async () => {
      const pyodide = await pyodidePromise!;
      scope.postMessage({ type: "vision-progress" });
      await pyodide.loadPackage(["opencv-python"]);
      scope.postMessage({ type: "vision-ready" });
    })().catch((error: unknown) => {
      visionPromise = null; // retryable
      scope.postMessage({
        type: "vision-failed",
        message: error instanceof Error ? error.message : String(error),
      });
      throw new Error("the vision engine failed to load; retry when back online");
    });
  }
  return visionPromise;
}

async function boot(baseUrl: string): Promise<PyodideInterface> {
  const progress = (step: string) => scope.postMessage({ type: "boot-progress", step });
  progress("Loading the Python engine");
  const { loadPyodide } = (await import(
    /* @vite-ignore */ `${baseUrl}pyodide/pyodide.mjs`
  )) as { loadPyodide: LoadPyodide };
  const pyodide = await loadPyodide({ indexURL: `${baseUrl}pyodide/` });
  progress("Loading engine packages");
  // No opencv here: the vision wheel lazy-loads on first photo use (S6).
  await pyodide.loadPackage(["numpy", "pillow", "pydantic", "micropip"]);
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
  if (
    !BRIDGE_METHODS.has(message.method) &&
    message.method !== "reverse_photo" &&
    message.method !== "stage_photo"
  ) {
    fail("value", `unknown bridge method: ${message.method}`);
    return;
  }
  if (pyodidePromise === null) {
    fail("worker", "engine is not booted");
    return;
  }
  try {
    const pyodide = await pyodidePromise;
    if (VISION_METHODS.has(message.method)) {
      await ensureVision();
    }
    let method = message.method;
    let args = message.args;
    // one staged file per crop session; cleaned up per the S2 contract
    let unlinkAfterCall: string | null = null;
    if (method === "stage_photo") {
      const [bytes] = args as [Uint8Array | ArrayBuffer];
      const data = bytes instanceof Uint8Array ? bytes : new Uint8Array(bytes);
      const path = `/staging/photo-${++stagingCounter}.png`;
      try {
        pyodide.FS.mkdirTree("/staging");
      } catch {
        // already exists
      }
      if (stagedTokenPath) unlinkQuietly(pyodide, stagedTokenPath);
      pyodide.FS.writeFile(path, data);
      stagedTokenPath = path;
      scope.postMessage({
        type: "result",
        id: message.id,
        envelope: { ok: true, result: { token: path } },
      });
      return;
    }
    if (method === "detect_quad") {
      // args: [token] from stage_photo; the file stays for the analyze call
      const [token] = args as [string];
      args = [token];
    }
    if (method === "reverse_photo") {
      const [payload, optionsJson] = args as [Uint8Array | ArrayBuffer | string, string];
      if (typeof payload === "string") {
        // token path from stage_photo: reuse the staged file (crop flow)
        args = [payload, optionsJson];
      } else {
        // legacy inline bytes (sample photo, round-trip panel): stage a
        // scratch file and unlink it after the call - the pre-S2 leak fix
        const data = payload instanceof Uint8Array ? payload : new Uint8Array(payload);
        const path = `/staging/upload-${++stagingCounter}.png`;
        try {
          pyodide.FS.mkdirTree("/staging");
        } catch {
          // already exists
        }
        pyodide.FS.writeFile(path, data);
        unlinkAfterCall = path;
        args = [path, optionsJson];
      }
      method = "reverse";
    }
    const bridge = pyodide.pyimport("qrep.bridge");
    try {
      const raw: string = bridge[method](...args);
      scope.postMessage({ type: "result", id: message.id, envelope: JSON.parse(raw) });
    } finally {
      bridge.destroy();
      if (unlinkAfterCall) unlinkQuietly(pyodide, unlinkAfterCall);
    }
  } catch (error) {
    // The bridge itself wraps engine errors; reaching here means the worker
    // plumbing failed (boot rejection, vision load failure, or ffi error).
    fail(
      "internal",
      error instanceof Error && error.message.includes("vision")
        ? error.message
        : "engine call failed in the worker",
    );
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
  } else if (message.type === "load-vision") {
    void ensureVision().catch(() => {
      // vision-failed already posted; prefetch failures are silent by design.
    });
  } else if (message.type === "call") {
    void serve(message);
  }
};
