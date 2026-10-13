/**
 * The size control on Your pattern (C2b, issue #148): the size line with
 * its default label or the asked-vs-achieved line, the preset chips from
 * bridge.presets(), and the typed W x H with the in or cm toggle. Rendered
 * to a string in Node, so no DOM; the e2e specs drive the clicks.
 */
import { renderToString } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { SizeControl } from "./SizeControl";
import type { Preset, SizeLine } from "./patternSize";

// bridge.presets() in eighths: Crib 36 x 52 in = 288 x 416 e; Queen
// 90 x 108 in = 720 x 864 e.
const PRESETS: Preset[] = [
  { name: "Crib", width: 288, height: 416 },
  { name: "Queen", width: 720, height: 864 },
];

const DEFAULT_LINE: SizeLine = {
  kind: "default",
  label: "Default size",
  achieved: "75 x 90 in",
  note: "The sample pattern as drawn, with 1 1/2 in squares. Set your size below.",
  asked: null,
};

function render(over: Partial<Parameters<typeof SizeControl>[0]> = {}): string {
  return renderToString(
    <SizeControl
      line={DEFAULT_LINE}
      presets={PRESETS}
      status="idle"
      message={null}
      onSize={() => undefined}
      {...over}
    />,
  );
}

describe("SizeControl", () => {
  it("labels a default size as a default and says where it came from", () => {
    const html = render();
    expect(html).toMatch(/data-testid="pattern-size-line"[^>]*data-size-kind="default"/);
    expect(html).toContain("Default size");
    expect(html).toContain("75 x 90 in");
    expect(html).toContain("1 1/2 in squares");
    expect(html).not.toContain("pattern-size-asked");
  });

  it("shows the asked size beside the achieved size", () => {
    const html = render({
      line: {
        kind: "typed",
        label: "Your size",
        achieved: "62 3/4 x 75 1/4 in",
        note: null,
        asked: "86 x 67 1/2 in",
      },
    });
    expect(html).toMatch(/data-testid="pattern-size-line"[^>]*data-size-kind="typed"/);
    const asked = html.match(/data-testid="pattern-size-asked"[^>]*>(.*?)<\/p>/s)?.[1] ?? "";
    expect(asked).toContain("86 x 67 1/2 in");
    expect(asked).toContain("62 3/4 x 75 1/4 in");
  });

  it("offers a chip per preset, in the bridge's order, with its size", () => {
    const html = render();
    const crib = html.indexOf('data-testid="pattern-size-chip-crib"');
    const queen = html.indexOf('data-testid="pattern-size-chip-queen"');
    expect(crib).toBeGreaterThan(-1);
    expect(queen).toBeGreaterThan(crib);
    // 720 e / 8 = 90 in; 864 e / 8 = 108 in.
    expect(html).toContain("90 x 108 in");
  });

  it("offers no chips before the presets land, and still takes a typed size", () => {
    const html = render({ presets: [] });
    expect(html).not.toContain("pattern-size-chip-");
    expect(html).toContain('data-testid="pattern-size-width"');
    expect(html).toContain('data-testid="pattern-size-height"');
    expect(html).toContain('data-testid="pattern-size-apply"');
  });

  it("starts in inches with a toggle to centimeters", () => {
    const html = render();
    expect(html).toMatch(/data-testid="pattern-size-unit"[^>]*>in</);
  });

  it("disables the inputs while a size is on its way and says so", () => {
    const html = render({ status: "busy" });
    expect(html).toMatch(/data-testid="pattern-size-apply"[^>]*disabled/);
    expect(html).toContain('data-testid="pattern-size-busy"');
  });

  it("shows the engine's refusal as a plain sentence", () => {
    const html = render({ status: "failed", message: "That size could not be set." });
    expect(html).toMatch(/role="alert"[^>]*>That size could not be set.</);
  });

  it("waits for the summary before it shows a size", () => {
    const html = render({ line: null });
    expect(html).not.toContain("pattern-size-line");
    expect(html).toContain("Working out the size");
  });
});
