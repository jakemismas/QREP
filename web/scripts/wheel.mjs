/**
 * Builds the qrep wheel from the repo checkout into web/public/wheels and
 * records its filename in the wheel manifest. The interpreter defaults to
 * the repo venv on Windows dev boxes and plain `python` in CI; override with
 * QREP_PYTHON.
 */
import { execFileSync } from "node:child_process";
import { existsSync, readFileSync, readdirSync, rmSync, writeFileSync } from "node:fs";
import * as path from "node:path";
import { fileURLToPath } from "node:url";

const webRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const repoRoot = path.resolve(webRoot, "..");
const wheelsDir = path.join(webRoot, "public", "wheels");

const venvPython = path.join(repoRoot, ".venv", "Scripts", "python.exe");
const python = process.env.QREP_PYTHON ?? (existsSync(venvPython) ? venvPython : "python");

for (const stale of readdirSync(wheelsDir).filter((f) => f.startsWith("qrep-"))) {
  rmSync(path.join(wheelsDir, stale));
}

execFileSync(python, ["-m", "pip", "wheel", repoRoot, "--no-deps", "-w", wheelsDir], {
  stdio: "inherit",
});

const wheels = readdirSync(wheelsDir).filter((f) => f.startsWith("qrep-") && f.endsWith(".whl"));
if (wheels.length !== 1) {
  throw new Error(`expected exactly one qrep wheel, found: ${wheels.join(", ") || "none"}`);
}

const manifestPath = path.join(wheelsDir, "manifest.json");
const manifest = existsSync(manifestPath) ? JSON.parse(readFileSync(manifestPath, "utf8")) : {};
manifest.qrepWheel = wheels[0];
writeFileSync(manifestPath, JSON.stringify(manifest, null, 2) + "\n");
console.log(`qrep wheel: ${wheels[0]}`);
