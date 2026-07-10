/**
 * S0 wasm-gate performance recorder (sprint 3, issue #66).
 *
 * Boots the vendored Pyodide runtime exactly like pytest-pyodide.mjs, then
 * times the shared gate ops (tests/fixtures/wasm_gate/ops.py) on the
 * committed photoreal fixtures at both staged caps: grabCut at the ~600 px
 * detection downscale and the cv2.dft autocorrelation at full cap. Prints
 * wall times and process RSS; run manually, results posted to the slice
 * issue. Not a CI job: CI proves parity via tests/test_wasm_gate.py; this
 * script records the perf numbers on a real machine.
 *
 * Usage (from web/): node scripts/wasm-gate-perf.mjs
 */
import * as path from "node:path";
import { fileURLToPath } from "node:url";
import { loadPyodide } from "pyodide";

const webRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const repoRoot = path.resolve(webRoot, "..");
const pyodideDir = path.join(webRoot, "public", "pyodide");

const bootStart = performance.now();
const pyodide = await loadPyodide({ packageCacheDir: pyodideDir });
await pyodide.loadPackage(["numpy", "opencv-python"]);
console.log(
  `pyodide ${pyodide.version} + numpy + opencv ready in ` +
    `${((performance.now() - bootStart) / 1000).toFixed(1)}s`,
);

pyodide.FS.mkdir("/repo");
pyodide.FS.mount(pyodide.FS.filesystems.NODEFS, { root: repoRoot }, "/repo");

const report = await pyodide.runPythonAsync(`
import importlib.util
import time

spec = importlib.util.spec_from_file_location(
    "wasm_gate_ops", "/repo/tests/fixtures/wasm_gate/ops.py"
)
ops = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ops)

lines = []
for name, cap in [("render_on_wood", 1400), ("render_on_wood", 2000)]:
    image = ops.load_fixture_bgr(name, cap)
    t = time.monotonic()
    ops.grabcut_op(image)
    dt = time.monotonic() - t
    lines.append(f"grabCut {name}@{cap} (600px downscale, 5 iters): {dt*1000:.0f} ms")
for name, cap in [("render_on_white", 1400), ("render_on_white", 2000)]:
    image = ops.load_fixture_bgr(name, cap)
    t = time.monotonic()
    ops.dft_autocorr_op(image)
    dt = time.monotonic() - t
    lines.append(f"dft autocorr {name}@{cap} (full cap): {dt*1000:.0f} ms")
# sprint 4 S0: the block-lattice ladder op sweeps 3 Lab channels x 3 detrend
# sigmas, each a padded 2D autocorr; this is the wall-time/memory gate case
for name, cap in [("antique_wash_chain", 1400), ("hst_star", 2000), ("quarter_circle_fine", 2000)]:
    image = ops.load_fixture_bgr(name, cap)
    t = time.monotonic()
    ops.lab_ladder_autocorr_op(image)
    dt = time.monotonic() - t
    lines.append(f"ladder autocorr {name}@{cap} (3ch x 3sigma sweep): {dt*1000:.0f} ms")
"\\n".join(lines)
`);
console.log(report);
console.log(`node process RSS: ${(process.memoryUsage().rss / 1e6).toFixed(0)} MB`);
