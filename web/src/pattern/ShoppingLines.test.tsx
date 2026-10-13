/**
 * The shopping lines on Your pattern (C2b, issue #148) print the engine
 * summary's lines as the engine names them, with its amounts, and compute
 * nothing (criterion P13). Rendered to a string in Node, so no DOM. The
 * summary below is the sample's at the fixture's stored widths: V-BACK-09
 * backing, V-BATT-01 batting.
 */
import { renderToString } from "react-dom/server";
import { describe, expect, it } from "vitest";
import type { PatternSummary, PurchaseLine } from "../engine/contract";
import { ShoppingLines } from "./ShoppingLines";

function summary(over: Partial<PatternSummary> = {}): PatternSummary {
  return {
    finished_width: 600,
    finished_height: 720,
    size_basis: null,
    method: "strip",
    method_reason: "Blocks of 5 x 5 squares repeat across the quilt, so it is strip pieced.",
    fabrics: [],
    binding: [{ fabric_id: "b", name: "Binding - Navy", yards: 0.75 }],
    // V-BACK-09: 2 panels x 98 in = 1568 e, + 72 e = 1640 e; ceil(1640 / 72) =
    // 23 quarter yards = 5.75 yd.
    backing: {
      fabric_id: null,
      name: "backing, 42 in wide fabric: (2) panels 98 in long, vertical seams",
      yards: 5.75,
    },
    wide_back: null,
    // V-BATT-01: (75 + 8) x (90 + 8) in = 83 x 98 in = 664 x 784 e.
    batting: { width: 664, height: 784 },
    strip_width: 336,
    backing_width: 336,
    uncertain_squares: 0,
    ...over,
  };
}

/** The text of the element whose data-testid is `id`, tags stripped. */
function textOf(html: string, id: string): string | null {
  const match = html.match(new RegExp(`data-testid="${id}"[^>]*>(.*?)</li>`, "s"));
  if (!match) return null;
  return match[1].replace(/<[^>]+>/g, "").replace(/&quot;/g, '"');
}

describe("ShoppingLines", () => {
  it("prints the backing line as the engine names it, with 5 3/4 yd", () => {
    const html = renderToString(<ShoppingLines summary={summary()} />);
    const backing = textOf(html, "shop-backing");
    expect(backing).toContain("backing, 42 in wide fabric: (2) panels 98 in long, vertical seams");
    // 5.75 yd = 23 / 4 yd = 5 3/4 yd (V-BACK-09).
    expect(backing).toContain("5 3/4 yd");
    // The engine's number rides on the row, unchanged, for the e2e checks.
    expect(html).toMatch(/data-testid="shop-backing"[^>]*data-yards="5.75"/);
  });

  it("prints the binding line as the summary gives it", () => {
    const html = renderToString(<ShoppingLines summary={summary()} />);
    expect(textOf(html, "shop-binding")).toContain("Binding - Navy");
    // 0.75 yd = 3/4 yd.
    expect(textOf(html, "shop-binding")).toContain("3/4 yd");
  });

  it("prints the batting size from the summary", () => {
    const html = renderToString(<ShoppingLines summary={summary()} />);
    // 664 e / 8 = 83 in; 784 e / 8 = 98 in (V-BATT-01).
    expect(textOf(html, "shop-batting")).toContain("83 x 98 in");
  });

  it("shows the wide-back line only when the engine returns it", () => {
    expect(renderToString(<ShoppingLines summary={summary()} />)).not.toContain("shop-wide-back");
    // A wide back for the fixture: min(83, 98) in = 83 in = 664 e, + 36 e =
    // 700 e; ceil(700 / 72) = 10 quarter yards = 2.5 yd (MATH.md F11).
    const wide: PurchaseLine = {
      fabric_id: null,
      name: "wide backing, 108 in wide fabric: one piece 83 in long",
      yards: 2.5,
    };
    const html = renderToString(<ShoppingLines summary={summary({ wide_back: wide })} />);
    expect(textOf(html, "shop-wide-back")).toContain("wide backing, 108 in wide fabric");
    expect(textOf(html, "shop-wide-back")).toContain("2 1/2 yd");
  });

  it("never calls the pieced backing wide backing (MATH.md D-07)", () => {
    const html = renderToString(<ShoppingLines summary={summary()} />);
    expect(textOf(html, "shop-backing")).not.toMatch(/wide back/i);
  });

  it("names both widths from the summary (MATH.md D-16)", () => {
    // 336 e / 8 = 42 in for each width: the fixture stores 42 in for cutting
    // until A6 (MATH.md section 1.3), and 42 in is B's default.
    const html = renderToString(<ShoppingLines summary={summary()} />);
    const widths = html.match(/data-testid="shop-widths"[^>]*>(.*?)<\/p>/s)?.[1] ?? "";
    expect(widths).toContain("strips at 42 in");
    expect(widths).toContain("backing assumes fabric 42 in wide");
    // 320 e = 40 in for cutting; 864 e = 108 in for the backing.
    const other = renderToString(
      <ShoppingLines summary={summary({ strip_width: 320, backing_width: 864 })} />,
    );
    expect(other).toContain("strips at 40 in");
    expect(other).toContain("backing assumes fabric 108 in wide");
  });
});
