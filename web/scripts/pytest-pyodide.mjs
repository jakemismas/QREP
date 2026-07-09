/**
 * Runs the FULL native pytest suite under the pinned, vendored Pyodide
 * runtime in Node (S1, issue #41): the drift-proof check that the shipped
 * engine is the tested engine.
 *
 * Prereqs (same as the site build): node scripts/vendor.mjs && node
 * scripts/wheel.mjs, so public/pyodide holds the runtime + closure wheels
 * and public/wheels holds reportlab/svgwrite/qrep. Test-only packages
 * (pytest, pypdf, typer, click) are pure Python and installed via micropip
 * from PyPI at run time - build-machine network, never site runtime.
 *
 * The repo checkout is mounted read-write at /repo via NODEFS and pytest
 * runs against /repo/tests exactly as native CI does. A wasm-only failure
 * is a real cross-runtime divergence: KNOWN_ISSUES protocol, never a
 * threshold edit.
 */
import { readFileSync, readdirSync } from "node:fs";
import * as path from "node:path";
import { fileURLToPath } from "node:url";
import { loadPyodide } from "pyodide";

const webRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const repoRoot = path.resolve(webRoot, "..");
const pyodideDir = path.join(webRoot, "public", "pyodide");
const wheelsDir = path.join(webRoot, "public", "wheels");

// Node runs the runtime from the npm package dir (same pinned version as
// the vendored copy; loading pyodide.asm.js out of web/public would be
// misparsed as ESM because web/package.json says "type": "module").
// packageCacheDir points loadPackage at the vendored wheels, so the
// closure under test is byte-for-byte the one the site ships.
console.log(`booting pyodide (wheels from ${pyodideDir})`);
const pyodide = await loadPyodide({ packageCacheDir: pyodideDir });
console.log(`pyodide ${pyodide.version} ready`);

await pyodide.loadPackage(["numpy", "opencv-python", "pillow", "pydantic", "micropip"]);

// Local wheels (reportlab, svgwrite, qrep) go through the Emscripten FS so
// the install path is identical on every host OS.
pyodide.FS.mkdirTree("/wheels");
const localWheels = readdirSync(wheelsDir).filter((f) => f.endsWith(".whl"));
for (const wheel of localWheels) {
  pyodide.FS.writeFile(`/wheels/${wheel}`, readFileSync(path.join(wheelsDir, wheel)));
}
pyodide.globals.set(
  "local_wheels",
  pyodide.toPy(localWheels.map((f) => `emfs:/wheels/${f}`)),
);
await pyodide.runPythonAsync(`
import micropip
await micropip.install(list(local_wheels), deps=False)
await micropip.install(["pytest", "pypdf", "typer", "click"])
`);

pyodide.FS.mkdir("/repo");
pyodide.FS.mount(pyodide.FS.filesystems.NODEFS, { root: repoRoot }, "/repo");

// --capture=sys: pytest's default fd-level capture dups stdio fds and
// emscripten closes them with an fsync that Windows Node rejects (EPERM
// fatal). Object-level capture keeps capsys semantics without touching fds;
// no test uses fd-level capfd.
const exitCode = await pyodide.runPythonAsync(`
import os
import pytest
os.chdir("/repo")
pytest.main(["-q", "--capture=sys", "-p", "no:cacheprovider", "tests"])
`);
process.exit(exitCode);
