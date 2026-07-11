/**
 * Verdict-copy audit (S8, issue #74; UI-SPEC sections 3-4). ADDITIVE to
 * copy-audit.test.ts (which owns the loading-copy ban): this file audits
 * the S8 honesty rules.
 *
 * 1. The phrase "read as squares" is banned from all UI strings (UI-SPEC
 *    section 4 bans "read as squares - N percent" for non_square_repeat).
 * 2. Verdict/pill consistency: a failure verdict never shows a number in
 *    the pill, never hides the evidence (disclosure always offered), and
 *    readable verdicts carry no failure framing.
 * 3. The S8 entry-copy strings exist verbatim where the plan put them
 *    (dropzone sub-copy, start-screen lede) so they cannot silently
 *    regress.
 */
import { readdirSync, readFileSync, statSync } from "node:fs";
import * as path from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { verdictStory } from "./model/verdictStory";
import type { PhotoResult } from "./shell/photoApi";

const srcRoot = path.dirname(fileURLToPath(import.meta.url));

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

const STRING_LITERAL = /(["'`])((?:\\.|(?!\1)[^\\\n])*)\1/g;
const BANNED_PHRASE = /read as squares/i;

describe("verdict-copy audit: banned phrasing", () => {
  for (const file of sourceFiles(srcRoot)) {
    it(path.relative(srcRoot, file), () => {
      const source = readFileSync(file, "utf8");
      const violations: string[] = [];
      for (const match of source.matchAll(STRING_LITERAL)) {
        if (BANNED_PHRASE.test(match[2])) violations.push(match[2]);
      }
      expect(violations, `banned verdict copy in ${file}`).toEqual([]);
    });
  }
});

const BASE = {
  modelJson: "{}",
  stageConfidence: { rectify: 0.9, palette: 0.9, grid: 0.9, cells: 0.9, repeat: 0.9, border: 0.9 },
  uncertainCount: 0,
  reverseMs: 100,
};
const GRID = { cols: 20, rows: 24, cellSize: 12 };

function story(verdict: string | undefined, diagnostics: Record<string, unknown>) {
  return verdictStory({ ...BASE, verdict, diagnostics } as PhotoResult, GRID);
}

describe("verdict/pill consistency invariants", () => {
  it("no_grid: no number next to a failure statement, evidence never hidden", () => {
    for (const diagnosis of [
      "no_quilt_found",
      "no_periodicity",
      "profile_too_short",
      "anisotropic_pitch",
      "implausible_dims",
      "weak_periodicity",
      "non_square_content",
      "some_future_diagnosis",
    ]) {
      const s = story("no_grid", { grid_diagnosis: diagnosis });
      expect(s.pill.mode).toBe("failure");
      expect(s.pill.text).not.toMatch(/\d|%/);
      expect(s.failurePanel).not.toBeNull();
      expect(s.failurePanel!.reason).not.toMatch(/%/);
      expect(s.disclosure, `evidence hidden for ${diagnosis}`).not.toBeNull();
      expect(s.dashedStages.length).toBeGreaterThan(0);
    }
  });

  it("non_square_repeat: approximation labeled, pill text carries no number itself", () => {
    const s = story("non_square_repeat", { block_period_cells: [4, 4], size_source: "guess" });
    expect(s.pill.mode).toBe("nonsquare");
    expect(s.pill.text).not.toMatch(/\d|%/);
    expect(s.infoPanel).not.toBeNull();
    expect(s.disclosure).not.toBeNull();
    expect(s.disclosure!.banner).toContain("approximation");
    expect(s.failurePanel).toBeNull();
  });

  it("readable verdicts carry no failure framing", () => {
    for (const verdict of ["readable", "readable_no_repeat", undefined]) {
      const s = story(verdict, { size_source: "guess" });
      expect(s.pill.mode).toBe("percent");
      expect(s.failurePanel).toBeNull();
      expect(s.disclosure).toBeNull();
      expect(s.dashedStages).toEqual([]);
    }
  });
});

describe("S8 entry copy present verbatim", () => {
  it("dropzone sub-copy", () => {
    const source = readFileSync(path.join(srcRoot, "shell", "PhotoFlow.tsx"), "utf8");
    expect(source).toContain("photo, a screenshot, or a shop listing picture all work");
  });
  it("start-screen lede honest size line", () => {
    const source = readFileSync(path.join(srcRoot, "shell", "StartScreen.tsx"), "utf8");
    expect(source).toContain("Size is optional: QREP guesses until you set the real one.");
  });
});
