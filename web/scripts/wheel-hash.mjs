/**
 * Wheel freshness stamp. wheel.mjs records a hash of the qrep/ sources plus
 * pyproject.toml next to the wheel it builds (public/wheels/qrep-source-hash.json),
 * and the site build (npm prebuild), the Pyodide test run and the local e2e
 * run refuse a wheel whose stamp no longer matches the sources. A version
 * check cannot do this job: every merge in a sprint keeps the same version,
 * so a stale wheel would ship, and be tested, under the current version.
 *
 * CLI: node scripts/wheel-hash.mjs [wheels-dir]   (default: public/wheels)
 * Playwright globalSetup (default export): checks dist/wheels, the copy the
 * preview server serves, unless SPIKE_BASE_URL points at a deployed site.
 */
import { createHash } from "node:crypto";
import { existsSync, readFileSync, readdirSync, writeFileSync } from "node:fs";
import * as path from "node:path";
import { fileURLToPath } from "node:url";

const webRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const defaultRepoRoot = path.resolve(webRoot, "..");
export const STAMP_FILE = "qrep-source-hash.json";

function sourceFiles(repoRoot) {
  const files = [];
  const walk = (rel) => {
    for (const entry of readdirSync(path.join(repoRoot, rel), { withFileTypes: true })) {
      const child = `${rel}/${entry.name}`;
      if (entry.isDirectory()) {
        if (entry.name !== "__pycache__") walk(child);
      } else if (entry.isFile() && !/\.py[co]$/.test(entry.name)) {
        files.push(child);
      }
    }
  };
  walk("qrep");
  files.push("pyproject.toml");
  return files.sort();
}

export function qrepSourceHash(repoRoot = defaultRepoRoot) {
  const digest = createHash("sha256");
  for (const rel of sourceFiles(repoRoot)) {
    const fileHash = createHash("sha256")
      .update(readFileSync(path.join(repoRoot, rel)))
      .digest("hex");
    digest.update(`${rel}\0${fileHash}\n`);
  }
  return digest.digest("hex");
}

export function writeWheelStamp(wheelsDir, wheel, sourceHash) {
  const stamp = { wheel, sourceHash };
  writeFileSync(path.join(wheelsDir, STAMP_FILE), JSON.stringify(stamp, null, 2) + "\n");
  return stamp;
}

/** Returns null for a fresh wheel, otherwise what is wrong with it. */
export function wheelStampProblem(wheelsDir, repoRoot = defaultRepoRoot) {
  const stampPath = path.join(wheelsDir, STAMP_FILE);
  if (!existsSync(stampPath)) return `${stampPath} is missing`;
  let stamp;
  try {
    stamp = JSON.parse(readFileSync(stampPath, "utf8"));
  } catch (err) {
    return `${stampPath} is unreadable (${err.message})`;
  }
  if (!stamp.wheel || !existsSync(path.join(wheelsDir, stamp.wheel))) {
    return `the stamped wheel ${stamp.wheel} is missing from ${wheelsDir}`;
  }
  const current = qrepSourceHash(repoRoot);
  if (stamp.sourceHash !== current) {
    return (
      `${stamp.wheel} in ${wheelsDir} was built from other qrep sources ` +
      `(stamp ${String(stamp.sourceHash).slice(0, 12)}, sources now ${current.slice(0, 12)})`
    );
  }
  return null;
}

export function assertFreshWheel(wheelsDir, rebuildHint, repoRoot = defaultRepoRoot) {
  const problem = wheelStampProblem(wheelsDir, repoRoot);
  if (problem) throw new Error(`stale qrep wheel: ${problem}. Rebuild from web/: ${rebuildHint}`);
}

export default function globalSetup() {
  if (process.env.SPIKE_BASE_URL) return;
  assertFreshWheel(
    path.join(webRoot, "dist", "wheels"),
    "node scripts/wheel.mjs && npm run build",
  );
}

const invokedPath = process.argv[1] ? path.resolve(process.argv[1]) : "";
if (invokedPath.toLowerCase() === fileURLToPath(import.meta.url).toLowerCase()) {
  const wheelsDir = path.resolve(process.argv[2] ?? path.join(webRoot, "public", "wheels"));
  try {
    assertFreshWheel(wheelsDir, "node scripts/wheel.mjs");
  } catch (err) {
    console.error(err.message);
    process.exit(1);
  }
  console.log(`qrep wheel is fresh: ${wheelsDir}`);
}
