/**
 * Forgiving fraction-input grammar (S4, issue #44; PARITY item 13).
 * Hand-authored cases: value in eighths = whole*8 + num*(8/den); decimals
 * accepted only when they land exactly on an eighth; denominators must
 * divide 8; negatives and garbage are rejected (null -> the input restores
 * its prior value).
 */
import { describe, expect, it } from "vitest";
import { parseFractionInput } from "./fraction";

const ACCEPTED: [string, number][] = [
  ["75", 600],
  ["75 1/2", 604],
  ["75.5", 604],
  ["75.125", 601],
  ['2 1/2"', 20],
  ["3 3/4 in", 30],
  ["3 3/4in", 30],
  ["1/8", 1],
  ["7/8", 7],
  ["0", 0],
  ["½", 4],
  ["1½", 12],
  ['1 ½"', 12],
  ["⅜", 3],
  ["2¾", 22],
  ["  90  ", 720],
];

const REJECTED = ["", "abc", "75.3", "1 2/3", "-5", "1/0", '"', "1 1"];

describe("parseFractionInput", () => {
  for (const [text, eighths] of ACCEPTED) {
    it(`accepts ${JSON.stringify(text)} as ${eighths} eighths`, () => {
      expect(parseFractionInput(text)).toBe(eighths);
    });
  }
  for (const text of REJECTED) {
    it(`rejects ${JSON.stringify(text)}`, () => {
      expect(parseFractionInput(text)).toBeNull();
    });
  }
});
