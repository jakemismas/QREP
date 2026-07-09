/**
 * Device-classed downscale caps (S6, issue #46): phones cap the longest
 * side at 1400 px, desktop/tablet at 2000 px; aspect ratio preserved,
 * dimensions rounded to integers; images under the cap pass through
 * untouched. Hand-computed cases in comments.
 */
import { describe, expect, it } from "vitest";
import { CAP_DESKTOP, CAP_PHONE, targetSize } from "./downscale";

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
