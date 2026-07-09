/**
 * Sizing mirror parity (S4, issue #44). The TS preview mirror must agree
 * with qrep/viewer/sizing.py on the EXACT literals of tests/test_viewer.py
 * (fixture: 55 rows x 45 cols of 12 eighths, border total 30, block 5), and
 * with the bridge's PARITY-4 layer on the exact literals of
 * tests/test_bridge.py. If any of these drift, the mirror must be dropped
 * per the design doc - never adjusted to disagree with Python.
 */
import { describe, expect, it } from "vitest";
import {
  bandScale,
  lockedResize,
  previewLocked,
  roundDiv,
  unlockedResize,
} from "./sizing";

describe("roundDiv half-up parity (test_viewer.test_round_div_half_up)", () => {
  it("mirrors the Python literals", () => {
    expect(roundDiv(29, 2)).toBe(15); // 14.5 rounds UP
    expect(roundDiv(12, 5)).toBe(2);
    expect(roundDiv(13, 5)).toBe(3);
    expect(roundDiv(660, 45)).toBe(15);
    expect(roundDiv(0, 45)).toBe(0);
  });
});

describe("lockedResize parity (test_viewer locked literals)", () => {
  it("queen width 720: cell 15, counts unchanged, achieved 735x885", () => {
    const result = lockedResize(55, 45, 12, 30, { targetWidth: 720 });
    expect(result.cellSize).toBe(15);
    expect([result.rows, result.cols]).toEqual([55, 45]);
    expect(result.achievedWidth).toBe(735);
    expect(result.achievedHeight).toBe(885);
  });

  it("identity width 600: cell 12, achieved 600x720", () => {
    const result = lockedResize(55, 45, 12, 30, { targetWidth: 600 });
    expect(result.cellSize).toBe(12);
    expect(result.achievedWidth).toBe(600);
    expect(result.achievedHeight).toBe(720);
  });

  it("by cell 16", () => {
    const result = lockedResize(55, 45, 12, 30, { targetCell: 16 });
    expect(result.cellSize).toBe(16);
  });

  it("clamps to one eighth at width 0", () => {
    const result = lockedResize(55, 45, 12, 30, { targetWidth: 0 });
    expect(result.cellSize).toBe(1);
  });
});

describe("unlockedResize parity (test_viewer unlocked literals)", () => {
  it("exact block fit width 780: 60 cols, achieved 780", () => {
    const result = unlockedResize(55, 45, 12, 30, 5, { targetWidth: 780 });
    expect(result.cols).toBe(60);
    expect(result.achievedWidth).toBe(780);
  });

  it("quantizes width 700 to 55 cols, achieved 720", () => {
    const result = unlockedResize(55, 45, 12, 30, 5, { targetWidth: 700 });
    expect(result.cols).toBe(55);
    expect(result.achievedWidth).toBe(720);
  });

  it("height 780 independent: 60 rows, cols untouched", () => {
    const result = unlockedResize(55, 45, 12, 30, 5, { targetHeight: 780 });
    expect(result.rows).toBe(60);
    expect(result.cols).toBe(45);
    expect(result.achievedHeight).toBe(780);
  });
});

describe("PARITY-4 preview layer parity (test_bridge resize literals)", () => {
  it("width 720: cell 15, band 30 -> 38, achieved 751x901", () => {
    const preview = previewLocked(
      { rows: 55, cols: 45, cellSize: 12, bands: [30] },
      { width: 720 },
    );
    expect(preview.cellSize).toBe(15);
    expect(preview.bands).toEqual([38]);
    expect(preview.achievedWidth).toBe(751);
    expect(preview.achievedHeight).toBe(901);
    expect(preview.requested.width).toBe(720);
  });

  it("crib preset 288x416 drives the cell to the 3/4in floor", () => {
    const preview = previewLocked(
      { rows: 55, cols: 45, cellSize: 12, bands: [30] },
      { preset: { width: 288, height: 416 } },
    );
    expect(preview.cellSize).toBe(6);
    expect(preview.bands).toEqual([15]);
    expect(preview.achievedWidth).toBe(300);
    expect(preview.achievedHeight).toBe(360);
  });

  it("quarter-rounds requested 723 to 724", () => {
    const preview = previewLocked(
      { rows: 55, cols: 45, cellSize: 12, bands: [30] },
      { width: 723 },
    );
    expect(preview.requested.width).toBe(724);
    expect(preview.cellSize).toBe(15);
  });

  it("clamps requested 1200 to the 140in cap", () => {
    const preview = previewLocked(
      { rows: 55, cols: 45, cellSize: 12, bands: [30] },
      { width: 1200 },
    );
    expect(preview.requested.width).toBe(1120);
    expect(preview.cellSize).toBe(24);
    expect(preview.bands).toEqual([60]);
  });

  it("band floor: width 2 at cell 20 -> 6 stays 2 (1/4in floor)", () => {
    expect(bandScale(2, 6, 20)).toBe(2);
    // And the plain scaling case from the bridge tests: 30 at 15/12 -> 38.
    expect(bandScale(30, 15, 12)).toBe(38);
  });
});
