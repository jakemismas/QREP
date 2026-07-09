/**
 * Loading-copy audit (S2, issue #42; PARITY item 8): the words "download"
 * and "install" are banned from all UI strings - asset fetches say
 * "loading"; "download" is reserved for user-initiated file saves, which
 * do not exist until S5 (when S5 adds them, extend the allowlist below
 * with those exact strings, never with loading/progress copy).
 *
 * The audit scans string literals in every source file under web/src
 * (tests excluded), so a violation anywhere in UI copy fails vitest.
 */
import { readdirSync, readFileSync, statSync } from "node:fs";
import * as path from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const srcRoot = path.dirname(fileURLToPath(import.meta.url));
const BANNED = /download|install/i;
// Exact string literals that may legitimately contain banned words.
const ALLOWLIST: string[] = [
  "micropip.install", // python code run in the worker, not UI copy
  "download-cutlist-csv", // S5 export button test id (not UI copy)
  "download-cutlist-md", // S5 export button test id (not UI copy)
  "download-yardage", // S5 export button test id (not UI copy)
  "download-svg", // S5 export button test id (not UI copy)
  "download-pdf", // S5 export button test id (not UI copy)
];

function sourceFiles(dir: string): string[] {
  const out: string[] = [];
  for (const entry of readdirSync(dir)) {
    const full = path.join(dir, entry);
    if (statSync(full).isDirectory()) {
      out.push(...sourceFiles(full));
    } else if (/\.(ts|tsx|css)$/.test(entry) && !/\.test\.tsx?$/.test(entry)) {
      out.push(full);
    }
  }
  return out;
}

// Matches "...", '...', and `...` literals, non-greedy, single line segments.
const STRING_LITERAL = /(["'`])((?:\\.|(?!\1)[^\\\n])*)\1/g;

describe("loading-copy audit", () => {
  for (const file of sourceFiles(srcRoot)) {
    it(path.relative(srcRoot, file), () => {
      const source = readFileSync(file, "utf8");
      const violations: string[] = [];
      for (const match of source.matchAll(STRING_LITERAL)) {
        const literal = match[2];
        if (!BANNED.test(literal)) continue;
        if (ALLOWLIST.some((allowed) => literal.includes(allowed))) continue;
        violations.push(literal);
      }
      expect(violations, `banned loading copy in ${file}`).toEqual([]);
    });
  }
});
