/// <reference lib="webworker" />
/**
 * S0 spike worker: boots the vendored Pyodide runtime, loads the engine
 * closure same-origin, installs the qrep wheel with micropip deps=False,
 * runs the spike checks, and posts a results JSON back to the page.
 */
import type { PyodideInterface } from "pyodide";
import spikeCode from "./spike_check.py?raw";

interface RunMessage {
  type: "run";
  baseUrl: string;
}

type LoadPyodide = (options: { indexURL: string }) => Promise<PyodideInterface>;

const scope = self as unknown as DedicatedWorkerGlobalScope;

scope.onmessage = async (event: MessageEvent<RunMessage>) => {
  if (event.data.type !== "run") return;
  const { baseUrl } = event.data;
  const progress = (stage: string) => scope.postMessage({ type: "progress", stage });
  const timings: Record<string, number> = {};
  try {
    progress("Loading the Python engine");
    let t = performance.now();
    const { loadPyodide } = (await import(
      /* @vite-ignore */ `${baseUrl}pyodide/pyodide.mjs`
    )) as { loadPyodide: LoadPyodide };
    const pyodide = await loadPyodide({ indexURL: `${baseUrl}pyodide/` });
    timings.bootMs = performance.now() - t;

    progress("Loading engine packages");
    t = performance.now();
    await pyodide.loadPackage(["numpy", "opencv-python", "pillow", "pydantic", "micropip"]);
    timings.closureMs = performance.now() - t;

    progress("Loading the qrep engine");
    const manifest = (await (await fetch(`${baseUrl}wheels/manifest.json`)).json()) as {
      pypiWheels: string[];
      qrepWheel: string;
    };
    const wheelUrls = [...manifest.pypiWheels, manifest.qrepWheel].map(
      (file) => `${baseUrl}wheels/${file}`,
    );
    t = performance.now();
    pyodide.globals.set("wheel_urls", pyodide.toPy(wheelUrls));
    await pyodide.runPythonAsync(
      "import micropip\nawait micropip.install(list(wheel_urls), deps=False)",
    );
    timings.qrepInstallMs = performance.now() - t;

    progress("Running engine checks (plan, cut list, booklet, render)");
    pyodide.runPython(spikeCode);
    const fixtureJson = await (
      await fetch(`${baseUrl}fixtures/double_irish_chain.json`)
    ).text();
    pyodide.globals.set("fixture_json", fixtureJson);
    t = performance.now();
    const phaseA = JSON.parse(await pyodide.runPythonAsync("phase_a(fixture_json)")) as {
      versions: Record<string, string>;
      timings: Record<string, number>;
      csvB64: string;
      pdfB64: string;
      pngB64: string;
    };
    timings.phaseAMs = performance.now() - t;

    progress("Staging photo bytes onto MEMFS");
    const pngBytes = Uint8Array.from(atob(phaseA.pngB64), (c) => c.charCodeAt(0));
    pyodide.FS.mkdirTree("/staging");
    pyodide.FS.writeFile("/staging/photo.png", pngBytes);
    const memfsStaged = pyodide.FS.analyzePath("/staging/photo.png").exists === true;

    progress("Reversing the L0 render");
    t = performance.now();
    const reverseResult = JSON.parse(
      await pyodide.runPythonAsync("phase_b(fixture_json, '/staging/photo.png')"),
    ) as Record<string, unknown>;
    timings.reverseTotalMs = performance.now() - t;

    scope.postMessage({
      type: "done",
      results: {
        status: "done",
        errors: [],
        pyodideVersion: pyodide.version,
        pythonVersion: phaseA.versions.python,
        packages: phaseA.versions,
        csvB64: phaseA.csvB64,
        pdfB64: phaseA.pdfB64,
        reverse: { ...reverseResult, memfsStaged },
        timings: { ...timings, ...phaseA.timings },
      },
    });
  } catch (error) {
    scope.postMessage({
      type: "error",
      error: error instanceof Error ? (error.stack ?? error.message) : String(error),
    });
  }
};
