/**
 * S4 sizing e2e (issue #44). DOM contract: sizing-panel (Sizing tab),
 * size-width / size-height / size-cell fraction inputs (display mixed
 * fractions), size-cell-up/-down steppers, size-preset <select> with
 * Custom + the six presets, proportion-lock toggle (default locked),
 * size-asked / size-got shown when they differ, border-row-<i> with
 * border-width-<i>, border-fabric-<i>, border-remove-<i>, plus border-add,
 * equation-box and blocks-line.
 *
 * Every expected number is hand-derived from the bridge semantics pinned in
 * tests/test_bridge.py (PARITY item 4):
 *  - Queen preset (720x864): min-ratio cell 15, band 30->38, achieved
 *    751x901 eighths = 93 7/8" x 112 5/8" (asked-vs-got differs -> preset
 *    reads Custom after commit, per the 0.07" detection tolerance).
 *  - Typed width "75 1/2" locked: cell round_div(544,45)=12, bands stay 30,
 *    achieved 600x720 = 75" x 90" (asked 75 1/2" vs got 75").
 *  - Unlocked width 87 1/2" (700): 55 cols, achieved 720 = 90".
 *  - Border 3 3/4" -> 2": extents 45*12+2*16=572 (71 1/2") x 692 (86 1/2").
 *  - Border add (innermost 2" default): totals 46 -> 632 (79") x 752 (94").
 *  - Cell stepper +1/4": cell 14, bands round_div(30*14,12)=35, achieved
 *    700 (87 1/2") x 840 (105").
 */
import { expect, test, type Page } from "@playwright/test";

const READY_TIMEOUT = 300_000;

async function openDemoSizing(page: Page): Promise<void> {
  await page.goto("./");
  await page.getByTestId("open-demo").click();
  await expect(page.getByTestId("editor")).toBeVisible();
  await expect(page.getByTestId("engine-chip")).toHaveAttribute("data-engine-phase", "ready", {
    timeout: READY_TIMEOUT,
  });
  await page.getByRole("tab", { name: "Sizing" }).click();
  await expect(page.getByTestId("sizing-panel")).toBeVisible();
}

test("locked preset commit adopts bridge numbers exactly", async ({ page }) => {
  await openDemoSizing(page);
  // Select by value: the visible label carries the mock's "Queen — 90 × 108"
  // copy, which exact-label matching would forbid.
  await page.getByTestId("size-preset").selectOption("queen");
  await expect(page.getByTestId("size-preset").locator("option[value=queen]")).toHaveText(
    /Queen/,
  );
  await expect(page.getByTestId("ruler-x-end")).toHaveText('93 7/8"');
  await expect(page.getByTestId("ruler-y-end")).toHaveText('112 5/8"');
  // Counts never change locked; the census is untouched.
  await expect(page.getByTestId("fabric-count-b")).toHaveText(/1,?246/);
  // Cell input displays the bridge cell (15 eighths = 1 7/8").
  await expect(page.getByTestId("size-cell")).toHaveValue(/1 7\/8/);
  // Achieved differs from the preset dims, so detection reads Custom and
  // asked-vs-got is shown.
  await expect(page.getByTestId("size-preset")).toHaveValue("custom");
  await expect(page.getByTestId("size-asked")).toContainText('90"');
  await expect(page.getByTestId("size-got")).toContainText('93 7/8"');
});

test("locked typed width commit: asked 75 1/2, got 75", async ({ page }) => {
  await openDemoSizing(page);
  const width = page.getByTestId("size-width");
  await width.fill("75 1/2");
  await width.press("Enter");
  await expect(page.getByTestId("ruler-x-end")).toHaveText('75"');
  await expect(page.getByTestId("ruler-y-end")).toHaveText('90"');
  await expect(page.getByTestId("size-asked")).toContainText('75 1/2"');
  await expect(page.getByTestId("size-got")).toContainText('75"');
  await expect(page.getByTestId("fabric-count-b")).toHaveText(/1,?246/);
});

test("unlocked resize moves whole blocks with asked-vs-got shown", async ({ page }) => {
  await openDemoSizing(page);
  await page.getByTestId("proportion-lock").click();
  const width = page.getByTestId("size-width");
  await width.fill("87 1/2");
  await width.press("Enter");
  await expect(page.getByTestId("quilt-canvas")).toHaveAttribute("data-finished-width", "720");
  await expect(page.getByTestId("ruler-x-end")).toHaveText('90"');
  await expect(page.getByTestId("size-asked")).toContainText('87 1/2"');
  await expect(page.getByTestId("size-got")).toContainText('90"');
});

test("border width change re-renders extents from the bridge model", async ({ page }) => {
  await openDemoSizing(page);
  const bandWidth = page.getByTestId("border-width-0");
  await expect(bandWidth).toHaveValue(/3 3\/4/);
  await bandWidth.fill("2");
  await bandWidth.press("Enter");
  await expect(page.getByTestId("ruler-x-end")).toHaveText('71 1/2"');
  await expect(page.getByTestId("ruler-y-end")).toHaveText('86 1/2"');
});

test("border add inserts innermost at 2in default; remove restores", async ({ page }) => {
  await openDemoSizing(page);
  await page.getByTestId("border-add").click();
  await expect(page.getByTestId("border-width-0")).toHaveValue(/^2/);
  await expect(page.getByTestId("ruler-x-end")).toHaveText('79"');
  await expect(page.getByTestId("ruler-y-end")).toHaveText('94"');
  await page.getByTestId("border-remove-0").click();
  await expect(page.getByTestId("ruler-x-end")).toHaveText('75"');
  await expect(page.getByTestId("ruler-y-end")).toHaveText('90"');
});

test("cell stepper moves 1/4in locked and commits through the bridge", async ({ page }) => {
  await openDemoSizing(page);
  await page.getByTestId("size-cell-up").click();
  await expect(page.getByTestId("ruler-x-end")).toHaveText('87 1/2"');
  await expect(page.getByTestId("ruler-y-end")).toHaveText('105"');
  await expect(page.getByTestId("size-cell")).toHaveValue(/1 3\/4/);
});

test("invalid fraction input restores the prior value with a toast", async ({ page }) => {
  await openDemoSizing(page);
  const width = page.getByTestId("size-width");
  await width.fill("abc");
  await width.press("Enter");
  await expect(page.getByTestId("toast")).toBeVisible();
  await expect(width).toHaveValue(/^75/);
  await expect(page.getByTestId("ruler-x-end")).toHaveText('75"');
});

test("equation box and blocks line render engine numbers", async ({ page }) => {
  await openDemoSizing(page);
  const equation = page.getByTestId("equation-box");
  // Squares + borders = finished, in mixed fractions (engine values).
  await expect(equation).toContainText('67 1/2"');
  await expect(equation).toContainText('3 3/4"');
  await expect(equation).toContainText('75"');
  const blocks = page.getByTestId("blocks-line");
  // 9 x 11 blocks of 5 (design-doc fixture geometry).
  await expect(blocks).toContainText("9");
  await expect(blocks).toContainText("11");
});
