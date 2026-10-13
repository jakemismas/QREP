/**
 * The census's yards column (C2b, issue #148): each fabric row shows the
 * yards of the engine summary's fabric line, verbatim (PS-40), and computes
 * none (criterion P13). Rendered to a string in Node, so no DOM.
 */
import { renderToString } from "react-dom/server";
import { describe, expect, it } from "vitest";
import type { FabricLine } from "../engine/contract";
import type { Fabric } from "../model/types";
import { FabricCensus } from "./FabricCensus";

const PALETTE: Fabric[] = [
  { id: "b", name: "Navy", color: "#223355" },
  { id: "w", name: "White", color: "#ffffff" },
  { id: "r", name: "Red", color: "#aa2222" },
];

// Hand-made summary lines: 3 1/4 yd is 13 quarter yards; 1/2 yd is 2 quarter
// yards; a fabric the top does not use carries 0 yd (qrep/export/pattern).
const LINES: FabricLine[] = [
  { letter: "b", fabric_id: "b", name: "Navy", yards: 3.25 },
  { letter: "w", fabric_id: "w", name: "White", yards: 0.5 },
  { letter: "r", fabric_id: "r", name: "Red", yards: 0 },
];

function render(): string {
  return renderToString(
    <FabricCensus lines={LINES} palette={PALETTE} census={null} countFailed={false} />,
  );
}

describe("FabricCensus yards column", () => {
  it("shows each fabric's yards from its summary line", () => {
    const html = render();
    // 3.25 yd = 3 1/4 yd; 0.5 yd = 1/2 yd.
    expect(html).toMatch(/data-testid="fabric-yards-b"[^>]*data-yards="3.25"[^>]*>3 1\/4 yd</);
    expect(html).toMatch(/data-testid="fabric-yards-w"[^>]*data-yards="0.5"[^>]*>1\/2 yd</);
  });

  it("shows no amount for a fabric the top does not use", () => {
    expect(render()).not.toContain("fabric-yards-r");
  });

  it("keeps the rows' letters and names", () => {
    const html = render();
    expect(html).toContain('data-testid="fabric-letter-b"');
    expect(html).toContain("Navy");
  });
});
