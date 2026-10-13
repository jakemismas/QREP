/**
 * Pattern settings e2e (C2b, issue #148): the fabric widths, the census
 * yards and the shopping lines on Your pattern for the sample. DOM contract:
 * see-sample opens your-pattern for the hand-authored double Irish chain
 * (tests/fixtures/double_irish_chain.json: 45 columns x 55 rows of 12 e
 * squares, one 30 e cream border, binding in fabric b, settings wof 336 e and
 * backing_width 336 e; e = eighths of an inch). pattern-size-line shows the
 * finished size; fabric-census holds fabric-yards-<fabricId> rows with
 * data-yards; shopping-lines holds shop-binding, shop-backing, shop-wide-back
 * (only when the engine returns one) and shop-batting, each with .sl-name and
 * .sl-amount, plus shop-widths; pattern-settings holds the strip-width and
 * backing-width selects.
 *
 * Every amount on the screen is the engine summary's (criterion P13). PS-40
 * compares the page with the native engine's own summary of the same model;
 * the widths tests change a select and read the new summary; the layout tests
 * keep every amount inside its column at the four viewports the ticket names
 * and run the C10 guard. No screenshot or snapshot assertions.
 */
import { execFileSync } from "node:child_process";
import { existsSync } from "node:fs";
import * as path from "node:path";
import { fileURLToPath } from "node:url";
import { devices, expect, test, type Locator, type Page } from "@playwright/test";
import { expectNoHorizontalOverflow } from "./helpers/layout";

const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const fixturePath = path.join(repoRoot, "tests", "fixtures", "double_irish_chain.json");
const READY_TIMEOUT = 300_000;
// Every summary comes from export_pattern, which builds the whole pattern PDF
// in the browser engine, and each width change asks for a new one; 60 s is
// the wait size.spec.ts gives a new size's summary.
const SUMMARY_TIMEOUT = 60_000;
// Element edges are fractional; the C10 guard allows the same half pixel.
const TOLERANCE_PX = 0.5;
const iPhone = devices["iPhone 13"];

interface NativeLine {
  fabric_id: string | null;
  name: string;
  yards: number;
}

interface NativeSummary {
  finished_width: number;
  finished_height: number;
  fabrics: { fabric_id: string; name: string; yards: number }[];
  binding: NativeLine[];
  backing: NativeLine;
  wide_back: NativeLine | null;
}

/** The native engine's summary of the fixture, from the worktree's venv. */
function nativeSummary(): NativeSummary {
  const venvPython = path.join(repoRoot, ".venv", "Scripts", "python.exe");
  const python = process.env.QREP_PYTHON ?? (existsSync(venvPython) ? venvPython : "python");
  const out = execFileSync(
    python,
    [
      "-c",
      "import json, sys; from qrep import bridge; print(bridge.export_pattern(open(sys.argv[1]).read()))",
      fixturePath,
    ],
    // The envelope carries the whole PDF as base64, past the 1 MB default.
    { encoding: "utf8", maxBuffer: 256 * 1024 * 1024 },
  );
  const envelope = JSON.parse(out) as { ok: boolean; result?: { summary?: NativeSummary } };
  if (!envelope.ok || !envelope.result?.summary) {
    throw new Error(`native export_pattern gave no summary: ${out.slice(0, 400)}`);
  }
  return envelope.result.summary;
}

async function openSamplePattern(page: Page): Promise<void> {
  await page.goto("./");
  await page.getByTestId("see-sample").click();
  await expect(page.getByTestId("your-pattern")).toBeVisible();
  await expect(page.getByTestId("engine-chip")).toHaveAttribute("data-engine-phase", "ready", {
    timeout: READY_TIMEOUT,
  });
}

async function yardsOf(locator: Locator): Promise<number> {
  return Number(await locator.getAttribute("data-yards"));
}

test.describe("PS-40: the screen and the native engine agree", () => {
  let summary: NativeSummary;

  test.beforeAll(() => {
    summary = nativeSummary();
  });

  test("Your pattern shows the native summary's finished size, fabric names and yards", async ({
    page,
  }) => {
    // The finished size the native summary must hold: 45 columns x 12 e +
    // 2 x 30 e border = 540 + 60 = 600 e wide; 55 rows x 12 e + 2 x 30 e =
    // 660 + 60 = 720 e high. The fixture's palette has two fabrics, b and c.
    expect(summary.finished_width).toBe(600);
    expect(summary.finished_height).toBe(720);
    expect(summary.fabrics).toHaveLength(2);

    await openSamplePattern(page);
    await expect(page.getByTestId("shopping-lines")).toBeVisible({ timeout: SUMMARY_TIMEOUT });

    // 600 / 8 = 75 in and 720 / 8 = 90 in, as mixed inches.
    await expect(page.getByTestId("pattern-size-line")).toContainText("75 x 90 in");

    const census = page.getByTestId("fabric-census");
    for (const fabric of summary.fabrics) {
      await expect(census).toContainText(fabric.name);
      const row = page.getByTestId(`fabric-yards-${fabric.fabric_id}`);
      if (fabric.yards > 0) {
        await expect(row).toBeVisible();
        expect(await yardsOf(row), `fabric ${fabric.fabric_id} yards`).toBe(fabric.yards);
      } else {
        // A fabric the top does not use has no yards row (FabricCensus.tsx).
        await expect(row).toHaveCount(0);
      }
    }

    const binding = page.getByTestId("shop-binding");
    await expect(binding).toHaveCount(summary.binding.length);
    for (const [index, line] of summary.binding.entries()) {
      expect(await yardsOf(binding.nth(index)), `binding ${index} yards`).toBe(line.yards);
    }
    expect(await yardsOf(page.getByTestId("shop-backing")), "backing yards").toBe(
      summary.backing.yards,
    );
    if (summary.wide_back !== null) {
      expect(await yardsOf(page.getByTestId("shop-wide-back")), "wide-back yards").toBe(
        summary.wide_back.yards,
      );
    } else {
      await expect(page.getByTestId("shop-wide-back")).toHaveCount(0);
    }
  });
});

test.describe("fabric widths re-request the pattern", () => {
  test("a 40 in cutting width reaches the summary", async ({ page }) => {
    await openSamplePattern(page);
    const widths = page.getByTestId("shop-widths");
    // The fixture stores wof 336 e = 42 in, so cutting starts at 42 in.
    await expect(widths).toContainText("strips at 42 in", { timeout: SUMMARY_TIMEOUT });
    await expect(page.getByTestId("strip-width")).toHaveValue("336");

    await page.getByTestId("strip-width").selectOption("320");
    // 320 e / 8 = 40 in. shop-widths prints the summary's strip_width, so the
    // new width shows only once the engine has made a new summary with it.
    await expect(widths).toContainText("strips at 40 in", { timeout: SUMMARY_TIMEOUT });
    await expect(page.getByTestId("strip-width")).toHaveValue("320");
    // The backing keeps its own width: backing_width 336 e = 42 in.
    await expect(widths).toContainText("fabric 42 in wide");
    await expect(page.getByTestId("photo-progress")).toHaveCount(0);
  });

  test("a 108 in backing is one piece with no wide-back line, and 42 in brings 5 3/4 yd back", async ({
    page,
  }) => {
    await openSamplePattern(page);
    const backing = page.getByTestId("shop-backing");
    // V-BACK-09: 2 vertical panels x 98 in = 1568 e, + 72 e pieced allowance =
    // 1640 e; ceil(1640 / 72) = 23 quarter yards = 23 / 4 = 5.75 yd.
    await expect(backing).toHaveAttribute("data-yards", "5.75", { timeout: SUMMARY_TIMEOUT });

    await page.getByTestId("backing-width").selectOption("864");
    // 864 e / 8 = 108 in.
    await expect(page.getByTestId("shop-widths")).toContainText("fabric 108 in wide", {
      timeout: SUMMARY_TIMEOUT,
    });
    // The backing is the quilt plus 4 in a side: (75 + 8) x (90 + 8) in =
    // 83 x 98 in = 664 x 784 e. At 864 e each side fits one width (F9: a side
    // no wider than B is one panel), so both layouts are one piece; F10 keeps
    // the smaller total: one piece 83 in long (the 98 in side across the
    // width) totals 664 + 36 = 700 e, against 784 + 36 = 820 e for one piece
    // 98 in long. So one piece 83 in long, and
    // ceil(700 / 72) = 10 quarter yards = 2.5 yd. The engine names the line
    // with format_inches, whose inch mark is a double quote (MATH.md F13;
    // qrep/construct/yardage.py backing_line), and the screen prints the
    // engine's name as given.
    await expect(backing.locator(".sl-name")).toContainText('108" wide fabric: one piece');
    await expect(backing).toHaveAttribute("data-yards", "2.5");
    // A one-piece backing has no wide-back alternative (MATH.md F11: shown
    // only when the pieced backing needs two or more panels).
    await expect(page.getByTestId("shop-wide-back")).toHaveCount(0);

    await page.getByTestId("backing-width").selectOption("336");
    await expect(page.getByTestId("shop-widths")).toContainText("fabric 42 in wide", {
      timeout: SUMMARY_TIMEOUT,
    });
    await expect(backing).toHaveAttribute("data-yards", "5.75");
  });
});

const LAYOUTS = [
  { label: "1280 x 860", options: { viewport: { width: 1280, height: 860 } } },
  { label: "1366 x 768", options: { viewport: { width: 1366, height: 768 } } },
  { label: "1440 x 900", options: { viewport: { width: 1440, height: 900 } } },
  {
    label: "390 x 844 (iPhone emulation)",
    options: {
      viewport: { width: 390, height: 844 },
      userAgent: iPhone.userAgent,
      deviceScaleFactor: iPhone.deviceScaleFactor,
      isMobile: iPhone.isMobile,
      hasTouch: iPhone.hasTouch,
    },
  },
];

for (const { label, options } of LAYOUTS) {
  test.describe(`Your pattern amounts at ${label}`, () => {
    test.use(options);

    test("every amount stays inside its column and the page inside the viewport", async ({
      page,
    }) => {
      const viewportWidth = options.viewport.width;
      await openSamplePattern(page);
      await expect(page.getByTestId("shopping-lines")).toBeVisible({ timeout: SUMMARY_TIMEOUT });

      // Both fabrics carry yards (the top uses b and c). The shopping lines
      // are binding (one binding fabric, b), backing, wide back (F11: the
      // pieced backing needs 2 panels, and 83 and 98 in both fit 108 in) and
      // batting: 4 amounts.
      const fabricAmounts = page.locator("[data-testid^='fabric-yards-']");
      const shopAmounts = page.getByTestId("shopping-lines").locator(".sl-amount");
      await expect(fabricAmounts).toHaveCount(2);
      await expect(shopAmounts).toHaveCount(4);

      const columns: [Locator, string][] = [
        [fabricAmounts, "fabric-census"],
        [shopAmounts, "shopping-lines"],
      ];
      for (const [amounts, sectionId] of columns) {
        const section = (await page.getByTestId(sectionId).boundingBox())!;
        for (const amount of await amounts.all()) {
          const box = (await amount.boundingBox())!;
          const what = `${label}: ${(await amount.textContent()) ?? ""} in ${sectionId}`;
          expect(box.x, `${what} starts inside its column`).toBeGreaterThanOrEqual(
            section.x - TOLERANCE_PX,
          );
          expect(box.x + box.width, `${what} ends inside its column`).toBeLessThanOrEqual(
            section.x + section.width + TOLERANCE_PX,
          );
          expect(box.y, `${what} starts below its column's top`).toBeGreaterThanOrEqual(
            section.y - TOLERANCE_PX,
          );
          expect(box.y + box.height, `${what} ends above its column's foot`).toBeLessThanOrEqual(
            section.y + section.height + TOLERANCE_PX,
          );
          expect(box.x, `${what} starts inside the viewport`).toBeGreaterThanOrEqual(
            -TOLERANCE_PX,
          );
          expect(box.x + box.width, `${what} ends inside the viewport`).toBeLessThanOrEqual(
            viewportWidth + TOLERANCE_PX,
          );
        }
      }

      if (viewportWidth >= 720) {
        await expectNoHorizontalOverflow(page, "your-pattern-amounts");
      } else {
        // The full guard waits for the header: with a quilt open its Open and
        // Save buttons still push it past 390 px (web-02), which C6a fixes
        // with the editor, as pattern.spec.ts records. The screen's own
        // content must fit meanwhile.
        const fit = await page.getByTestId("your-pattern").evaluate((root) => ({
          right: root.getBoundingClientRect().right,
          scrollWidth: root.scrollWidth,
          clientWidth: root.clientWidth,
        }));
        expect(fit.right).toBeLessThanOrEqual(viewportWidth);
        expect(fit.scrollWidth).toBeLessThanOrEqual(fit.clientWidth);
      }
    });
  });
}
