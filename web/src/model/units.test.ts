/**
 * Fraction display parity (S2, issue #42): the TS formatter must agree with
 * qrep.model.units.format_inches on every pair in the shared hand-authored
 * fixture tests/fixtures/fraction_display.json. The Python side is pinned by
 * tests/test_fraction_parity.py against the SAME file.
 */
import { readFileSync } from "node:fs";
import * as path from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { formatEighths } from "./units";

const fixturePath = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "../../../tests/fixtures/fraction_display.json",
);
const cases: { eighths: number; display: string }[] = JSON.parse(
  readFileSync(fixturePath, "utf8"),
).cases;

describe("formatEighths parity with qrep.model.units", () => {
  for (const { eighths, display } of cases) {
    it(`${eighths} -> ${display}`, () => {
      expect(formatEighths(eighths)).toBe(display);
    });
  }
});
