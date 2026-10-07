/**
 * Runs the FULL native pytest suite under the pinned, vendored Pyodide
 * runtime in Node (S1, issue #41): the drift-proof check that the shipped
 * engine is the tested engine.
 *
 * Prereqs (same as the site build): node scripts/vendor.mjs && node
 * scripts/wheel.mjs, so public/pyodide holds the runtime + closure wheels
 * and public/wheels holds reportlab/svgwrite/qrep. The run refuses a qrep
 * wheel whose source stamp no longer matches qrep/ (scripts/wheel-hash.mjs),
 * so the wasm suite never tests stale engine code. Test-only packages
 * (pytest, pypdf, typer and their dependencies) are pure Python, installed
 * via micropip from PyPI at run time - build-machine network, never site
 * runtime - at the exact versions repo-root constraints.txt pins for the
 * native suite, so neither runtime's test tooling can float.
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
import { assertFreshWheel } from "./wheel-hash.mjs";

const webRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const repoRoot = path.resolve(webRoot, "..");
const pyodideDir = path.join(webRoot, "public", "pyodide");
const wheelsDir = path.join(webRoot, "public", "wheels");

assertFreshWheel(wheelsDir, "node scripts/wheel.mjs");

const canonical = (name) => name.toLowerCase().replace(/[-_.]+/g, "-");
const constraints = readFileSync(path.join(repoRoot, "constraints.txt"), "utf8")
  .split(/\r?\n/)
  .map((line) => line.replace(/#.*/, "").trim())
  .filter(Boolean);
for (const line of constraints) {
  if (!/^[A-Za-z0-9._-]+==[A-Za-z0-9.+!_-]+$/.test(line)) {
    throw new Error(`constraints.txt line is not an exact name==version pin: ${line}`);
  }
}
const exactPin = (name) => {
  const pin = constraints.find((line) => canonical(line.split("==")[0]) === canonical(name));
  if (!pin) throw new Error(`constraints.txt has no pin for test package ${name}`);
  return pin;
};
// The pinned typer (0.26.8) vendors click as typer._click, so click itself
// is not installed.
const testRequirements = ["pytest", "pypdf", "typer"].map(exactPin);

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
pyodide.globals.set("test_requirements", pyodide.toPy(testRequirements));
// Passing every pin as a micropip constraint also fixes the transitive
// dependencies (pluggy, pygments, rich, ...), not just the top-level names.
pyodide.globals.set("test_constraints", pyodide.toPy(constraints));
const installed = await pyodide.runPythonAsync(`
import micropip
await micropip.install(list(local_wheels), deps=False)
await micropip.install(list(test_requirements), constraints=list(test_constraints))
", ".join(sorted(f"{p.name}=={p.version}" for p in micropip.list().values()))
`);
console.log(`installed: ${installed}`);

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
