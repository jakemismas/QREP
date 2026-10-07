/**
 * Builds the qrep wheel from the repo checkout into web/public/wheels,
 * records its filename in the wheel manifest, and stamps it with a hash of
 * the sources it was built from (scripts/wheel-hash.mjs) so later build and
 * test steps can refuse a stale wheel. The interpreter defaults to the repo
 * venv on Windows dev boxes and plain `python` in CI; override with
 * QREP_PYTHON.
 */
import { execFileSync } from "node:child_process";
import { existsSync, readFileSync, readdirSync, rmSync, writeFileSync } from "node:fs";
import * as path from "node:path";
import { fileURLToPath } from "node:url";
import { STAMP_FILE, qrepSourceHash, writeWheelStamp } from "./wheel-hash.mjs";

const webRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const repoRoot = path.resolve(webRoot, "..");
const wheelsDir = path.join(webRoot, "public", "wheels");

const venvPython = path.join(repoRoot, ".venv", "Scripts", "python.exe");
const python = process.env.QREP_PYTHON ?? (existsSync(venvPython) ? venvPython : "python");

for (const stale of readdirSync(wheelsDir).filter((f) => f.startsWith("qrep-"))) {
  rmSync(path.join(wheelsDir, stale));
}
// A failed build below must not leave an old stamp vouching for a wheel.
rmSync(path.join(wheelsDir, STAMP_FILE), { force: true });

// Hashed before building: a source edit during the build then reads as
// stale afterwards instead of being stamped as built.
const sourceHash = qrepSourceHash(repoRoot);
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
writeWheelStamp(wheelsDir, wheels[0], sourceHash);
console.log(`qrep wheel: ${wheels[0]} (sources ${sourceHash.slice(0, 12)})`);
