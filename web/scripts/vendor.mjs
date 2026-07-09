/**
 * Vendors the pinned Pyodide runtime and wheel closure into web/public so the
 * built site serves everything same-origin (no CDN fetches at runtime).
 *
 * Sources, per vendor.lock.json:
 *  - Core runtime files: copied from node_modules/pyodide (the npm package is
 *    pinned to the same version; npm verifies its integrity via package-lock).
 *  - Distribution wheels: downloaded once from the pinned jsDelivr URL into
 *    .vendor-cache/ with sha256 verification, then copied next to
 *    pyodide-lock.json (loadPackage resolves wheels at the lockfile base URL).
 *  - PyPI pure-Python wheels (reportlab, svgwrite): same download+verify flow,
 *    copied to public/wheels/ for micropip.install(..., deps=False).
 *  - The benchmark fixture JSON is copied from tests/fixtures (single source
 *    of truth; never duplicated by hand).
 *
 * Also writes public/wheels/manifest.json so the spike page knows the exact
 * wheel filenames without hardcoding versions.
 */
import { createHash } from "node:crypto";
import { copyFileSync, existsSync, mkdirSync, readFileSync, statSync, writeFileSync } from "node:fs";
import * as path from "node:path";
import { fileURLToPath } from "node:url";

const webRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const repoRoot = path.resolve(webRoot, "..");
const lock = JSON.parse(readFileSync(path.join(webRoot, "vendor.lock.json"), "utf8"));

const cacheDir = path.join(webRoot, ".vendor-cache");
const pyodideDir = path.join(webRoot, "public", "pyodide");
const wheelsDir = path.join(webRoot, "public", "wheels");
const fixturesDir = path.join(webRoot, "public", "fixtures");
for (const dir of [cacheDir, pyodideDir, wheelsDir, fixturesDir]) {
  mkdirSync(dir, { recursive: true });
}

function sha256(buffer) {
  return createHash("sha256").update(buffer).digest("hex");
}

async function fetchVerified(url, expectedSha256, fileName) {
  const cached = path.join(cacheDir, fileName);
  if (existsSync(cached)) {
    const bytes = readFileSync(cached);
    if (sha256(bytes) === expectedSha256) return bytes;
    console.warn(`cache sha256 mismatch for ${fileName}; refetching`);
  }
  console.log(`fetching ${url}`);
  const response = await fetch(url);
  if (!response.ok) throw new Error(`HTTP ${response.status} for ${url}`);
  const bytes = Buffer.from(await response.arrayBuffer());
  const actual = sha256(bytes);
  if (actual !== expectedSha256) {
    throw new Error(`sha256 mismatch for ${fileName}: expected ${expectedSha256}, got ${actual}`);
  }
  writeFileSync(cached, bytes);
  return bytes;
}

// 1. Core runtime from the pinned npm package.
const npmPyodide = path.join(webRoot, "node_modules", "pyodide");
const npmVersion = JSON.parse(readFileSync(path.join(npmPyodide, "package.json"), "utf8")).version;
if (npmVersion !== lock.pyodideVersion) {
  throw new Error(
    `node_modules/pyodide is ${npmVersion} but vendor.lock.json pins ${lock.pyodideVersion}; ` +
      `run npm ci or align the pins`,
  );
}
for (const file of lock.coreFiles) {
  copyFileSync(path.join(npmPyodide, file), path.join(pyodideDir, file));
}
console.log(`core: ${lock.coreFiles.length} files from npm pyodide@${npmVersion}`);

// 2. Distribution wheels next to pyodide-lock.json.
for (const wheel of lock.distributionWheels) {
  const bytes = await fetchVerified(
    lock.distributionWheelUrlBase + wheel.file,
    wheel.sha256,
    wheel.file,
  );
  writeFileSync(path.join(pyodideDir, wheel.file), bytes);
}
console.log(`distribution wheels: ${lock.distributionWheels.length} verified`);

// 3. PyPI wheels for micropip.
for (const wheel of lock.pypiWheels) {
  const bytes = await fetchVerified(wheel.url, wheel.sha256, wheel.file);
  writeFileSync(path.join(wheelsDir, wheel.file), bytes);
}
console.log(`pypi wheels: ${lock.pypiWheels.length} verified`);

// 4. Fixture from the canonical repo location.
copyFileSync(
  path.join(repoRoot, "tests", "fixtures", "double_irish_chain.json"),
  path.join(fixturesDir, "double_irish_chain.json"),
);

// 5. Manifest for the spike page (qrep wheel entry is added by wheel.mjs).
const manifestPath = path.join(wheelsDir, "manifest.json");
const existing = existsSync(manifestPath) ? JSON.parse(readFileSync(manifestPath, "utf8")) : {};
writeFileSync(
  manifestPath,
  JSON.stringify(
    {
      ...existing,
      pyodideVersion: lock.pyodideVersion,
      distributionPackages: lock.distributionWheels.map((w) => w.name),
      pypiWheels: lock.pypiWheels.map((w) => w.file),
      // Measured vision payload (S6): the UI's loading copy shows this
      // real number, never a placeholder.
      visionBytes: statSync(
        path.join(
          pyodideDir,
          lock.distributionWheels.find((w) => w.name === "opencv-python").file,
        ),
      ).size,
    },
    null,
    2,
  ) + "\n",
);
console.log("vendor complete");
