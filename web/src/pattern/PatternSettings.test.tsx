/**
 * The two fabric widths on Your pattern (C2b, issue #148): Fabric width for
 * cutting strips (default 40 in) and Backing fabric width (default 42 in,
 * with a 108 in wide-back choice), MATH.md section 1.3's U, B and BW.
 * Rendered to a string in Node, so no DOM.
 */
import { renderToString } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { PatternSettings } from "./PatternSettings";

function render(strip: number | null, backing: number | null, disabled = false): string {
  return renderToString(
    <PatternSettings
      stripWidth={strip}
      backingWidth={backing}
      disabled={disabled}
      onChange={() => undefined}
    />,
  );
}

/** The option a select marks selected, by the select's test id. */
function selected(html: string, id: string): string | null {
  const select = html.match(new RegExp(`data-testid="${id}".*?</select>`, "s"))?.[0] ?? "";
  return select.match(/<option[^>]*selected=""[^>]*>(.*?)<\/option>/)?.[1] ?? null;
}

describe("PatternSettings", () => {
  it("names both widths and their defaults (MATH.md D-16)", () => {
    const html = render(320, 336);
    expect(html).toContain("Fabric width for cutting strips");
    expect(html).toContain("Backing fabric width");
    // U = 40 in = 320 e and B = 42 in = 336 e are the defaults.
    expect(selected(html, "strip-width")).toBe("40 in (default)");
    expect(selected(html, "backing-width")).toBe("42 in (default)");
  });

  it("offers the 108 in wide back for the backing", () => {
    // BW = 108 in = 864 e.
    const html = render(320, 864);
    expect(html).toContain('value="864"');
    expect(selected(html, "backing-width")).toBe("108 in wide back");
  });

  it("shows a stored width the list lacks, so the select never lies", () => {
    // 38 in x 8 = 304 e, not one of the offered widths.
    const html = render(304, 336);
    expect(selected(html, "strip-width")).toBe("38 in");
  });

  it("shows the fixture's stored 42 in for cutting", () => {
    // The fixture stores wof 336 e = 42 in until A6 (MATH.md section 1.3).
    expect(selected(render(336, 336), "strip-width")).toBe("42 in");
  });

  it("waits for the pattern before it offers a change", () => {
    const html = render(null, null, true);
    expect(html).toMatch(/data-testid="strip-width"[^>]*disabled/);
    expect(html).toMatch(/data-testid="backing-width"[^>]*disabled/);
  });
});
