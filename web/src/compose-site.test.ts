/**
 * Pages artifact composition (S7, issue #47): the root serves the app, the
 * legacy docs URLs keep working, and /app/ redirects home so every sprint-2
 * link survives the flip. Runs the real compose script against the real
 * build output into a temp dir and inspects the result.
 */
import { execFileSync } from "node:child_process";
import { existsSync, mkdtempSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import * as path from "node:path";
import { fileURLToPath } from "node:url";
import { afterAll, beforeAll, describe, expect, it } from "vitest";

const webRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const repoRoot = path.resolve(webRoot, "..");
let siteDir: string;

beforeAll(() => {
  siteDir = mkdtempSync(path.join(tmpdir(), "qrep-site-"));
  execFileSync("node", [path.join(webRoot, "scripts", "compose-site.mjs"), siteDir], {
    stdio: "pipe",
  });
});

afterAll(() => {
  rmSync(siteDir, { recursive: true, force: true });
});

describe("composed Pages artifact", () => {
  it("serves the app at the root", () => {
    const index = readFileSync(path.join(siteDir, "index.html"), "utf8");
    expect(index).toContain("<title>QREP</title>");
    // The app shell references its hashed entry chunk (the rollup input is
    // named "main"), not the docs landing page.
    expect(index).toMatch(/assets\/main-[\w-]+\.js/);
  });

  it("keeps the legacy docs URLs alive (viewer.html, demo artifacts)", () => {
    expect(existsSync(path.join(siteDir, "viewer.html"))).toBe(true);
    expect(existsSync(path.join(siteDir, "demo", "booklet.pdf"))).toBe(true);
  });

  it("redirects /app/ to the root so sprint-2 URLs survive", () => {
    const stub = readFileSync(path.join(siteDir, "app", "index.html"), "utf8");
    expect(stub).toMatch(/http-equiv="refresh"|location\.replace/);
  });

  it("ships the runtime, wheels, and .nojekyll", () => {
    expect(existsSync(path.join(siteDir, "pyodide", "pyodide-lock.json"))).toBe(true);
    expect(existsSync(path.join(siteDir, "wheels", "manifest.json"))).toBe(true);
    expect(existsSync(path.join(siteDir, ".nojekyll"))).toBe(true);
    expect(existsSync(path.join(siteDir, "spike.html"))).toBe(true);
  });
});

describe("release version sync", () => {
  const pyproject = readFileSync(path.join(repoRoot, "pyproject.toml"), "utf8");
  const init = readFileSync(path.join(repoRoot, "qrep", "__init__.py"), "utf8");
  const pkg = readFileSync(path.join(webRoot, "package.json"), "utf8");
  const pyVersion = pyproject.match(/^version = "([^"]+)"/m)?.[1];
  const initVersion = init.match(/__version__ = "([^"]+)"/)?.[1];
  const webVersion = (JSON.parse(pkg) as { version?: string }).version;

  it("pyproject and qrep.__version__ agree", () => {
    expect(pyVersion).toBeTruthy();
    expect(pyVersion).toBe(initVersion);
  });

  // S9 (issue #75): the release ships one version everywhere - the web
  // package.json must track the engine version so a bumped release cannot
  // half-land (pyproject moved, the app left behind).
  it("web package.json tracks the engine version", () => {
    expect(webVersion).toBeTruthy();
    expect(webVersion).toBe(pyVersion);
  });
});
