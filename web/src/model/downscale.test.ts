/**
 * Device-classed downscale caps (S6, issue #46): phones cap the longest
 * side at 1400 px, desktop/tablet at 2000 px; aspect ratio preserved,
 * dimensions rounded to integers; images under the cap pass through
 * untouched. Hand-computed cases in comments.
 */
import { describe, expect, it } from "vitest";
import { CAP_DESKTOP, CAP_PHONE, STAGE_CAP, capLongest, targetSize } from "./downscale";

describe("targetSize", () => {
  it("caps are the contract values", () => {
    expect(CAP_PHONE).toBe(1400);
    expect(CAP_DESKTOP).toBe(2000);
  });

  it("desktop: 4000x3000 -> 2000x1500 (3000*2000/4000)", () => {
    expect(targetSize(4000, 3000, "desktop")).toEqual({
      width: 2000,
      height: 1500,
      scaled: true,
    });
  });

  it("phone: 4000x3000 -> 1400x1050 (3000*1400/4000)", () => {
    expect(targetSize(4000, 3000, "phone")).toEqual({ width: 1400, height: 1050, scaled: true });
  });

  it("portrait phone: 3000x4000 -> 1050x1400", () => {
    expect(targetSize(3000, 4000, "phone")).toEqual({ width: 1050, height: 1400, scaled: true });
  });

  it("under the cap passes through", () => {
    expect(targetSize(1200, 800, "desktop")).toEqual({ width: 1200, height: 800, scaled: false });
    expect(targetSize(1400, 900, "phone")).toEqual({ width: 1400, height: 900, scaled: false });
  });

  it("rounds the short side: 3999x2999 phone -> 1400x1050", () => {
    // 2999 * 1400 / 3999 = 1049.86... -> 1050.
    expect(targetSize(3999, 2999, "phone")).toEqual({ width: 1400, height: 1050, scaled: true });
  });
});

/**
 * The one staging cap (C3b, issue #101; ux-06): every viewport stages at the
 * old desktop cap, so the window width never changes the staged pixels.
 */
describe("capLongest", () => {
  it("the staging cap is the old desktop cap, 2000 px (downscale.ts:9)", () => {
    expect(STAGE_CAP).toBe(2000);
  });

  it("landscape: 4000x3000 -> 2000x1500, scale 0.5", () => {
    // Longest side 4000 > 2000: scale = 2000 / 4000 = 0.5;
    // width 4000 x 0.5 = 2000, height 3000 x 0.5 = 1500.
    expect(capLongest(4000, 3000)).toEqual({ width: 2000, height: 1500, scale: 0.5, scaled: true });
  });

  it("portrait: 3000x8000 -> 750x2000, scale 0.25", () => {
    // Longest side 8000: scale = 2000 / 8000 = 0.25;
    // width 3000 x 0.25 = 750, height 8000 x 0.25 = 2000.
    expect(capLongest(3000, 8000)).toEqual({ width: 750, height: 2000, scale: 0.25, scaled: true });
  });

  it("under or at the cap passes through with scale 1", () => {
    // 778 <= 2000 (the docs-03 crop) and 2000 <= 2000: nothing scales.
    expect(capLongest(778, 778)).toEqual({ width: 778, height: 778, scale: 1, scaled: false });
    expect(capLongest(2000, 1200)).toEqual({ width: 2000, height: 1200, scale: 1, scaled: false });
  });

  it("rounds the short side: 7400x5600 -> 2000x1514", () => {
    // scale = 2000 / 7400 = 0.270270...;
    // height 5600 x 2000 / 7400 = 11200000 / 7400 = 1513.51... -> 1514.
    const out = capLongest(7400, 5600);
    expect(out.width).toBe(2000);
    expect(out.height).toBe(1514);
    expect(out.scale).toBeCloseTo(2000 / 7400, 12);
    expect(out.scaled).toBe(true);
  });

  it("takes another cap: 1290x2796 at 1400 -> 646x1400", () => {
    // The 834d8be phone cap on the docs-03 screenshot: scale = 1400 / 2796;
    // width 1290 x 1400 / 2796 = 1806000 / 2796 = 645.92... -> 646.
    const out = capLongest(1290, 2796, 1400);
    expect(out.width).toBe(646);
    expect(out.height).toBe(1400);
    expect(out.scale).toBeCloseTo(1400 / 2796, 12);
  });
});
