/**
 * Golden discipline guards (S5, issue #45; council finding, binding):
 *  1. Playwright snapshot APIs are BANNED anywhere under web/ - they
 *     auto-write goldens on first run, which is an implicit bless.
 *  2. No copy of any canonical golden may exist under web/: e2e checks read
 *     tests/golden/ at test runtime, never a committed copy.
 */
import { readdirSync, readFileSync, statSync } from "node:fs";
import * as path from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const webRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const repoRoot = path.resolve(webRoot, "..");
const goldenNames = readdirSync(path.join(repoRoot, "tests", "golden"));

const SKIP_DIRS = new Set(["node_modules", "dist", "test-results", ".vendor-cache", "playwright-report", "pyodide", "wheels"]);

function walk(dir: string): string[] {
  const out: string[] = [];
  for (const entry of readdirSync(dir)) {
    const full = path.join(dir, entry);
    if (statSync(full).isDirectory()) {
      if (!SKIP_DIRS.has(entry)) out.push(...walk(full));
    } else {
      out.push(full);
    }
  }
  return out;
}

const files = walk(webRoot);

describe("golden discipline", () => {
  it("no Playwright snapshot APIs anywhere under web/", () => {
    const offenders = files
      .filter((f) => /\.(ts|tsx|js|mjs)$/.test(f) && !f.endsWith("golden-discipline.test.ts"))
      .filter((f) => /toMatchSnapshot|toHaveScreenshot/.test(readFileSync(f, "utf8")));
    expect(offenders).toEqual([]);
  });

  it("no file under web/ shares a canonical golden's name", () => {
    const offenders = files.filter((f) => goldenNames.includes(path.basename(f)));
    expect(offenders).toEqual([]);
  });
});
