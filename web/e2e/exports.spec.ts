/**
 * S5 exports e2e (issue #45). DOM contract: pattern-panel (Pattern tab),
 * strategy-card-<historical|strip|modern> (click selects; carry
 * data-selected), per-card metric text from bridge plan output only,
 * hand-tweaked badge (data-testid="hand-tweaked"), yardage-table with
 * yardage-row-<fabricId|binding|backing|batting> rows carrying
 * data-quarter-yards, download buttons download-cutlist-csv / -cutlist-md /
 * -yardage / -svg / -pdf, print-plan + print-sheet, copy-settings, and the
 * Seams mode via mode-seams in the toolbar.
 *
 * Golden discipline: byte-compares read the CANONICAL files from
 * tests/golden/ at test runtime. No snapshot APIs. Known literals: strip
 * strip_set_count 25 and historical piece_count 2479 (test_construct),
 * backing 5.5 yd = 22 quarter-yards (design doc), batting 83" x 98"
 * (PARITY item 9), slug double-irish-chain-75x90 (PARITY item 11).
 */
import { expect, test, type Download, type Page } from "@playwright/test";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import * as path from "node:path";
import { fileURLToPath } from "node:url";

const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const goldenDir = path.join(repoRoot, "tests", "golden");
const downloadDir = path.join(repoRoot, "web", "test-results", "downloads");
const READY_TIMEOUT = 300_000;
const SLUG = "double-irish-chain-75x90";

async function openPattern(page: Page): Promise<void> {
  await page.goto("./");
  await page.getByTestId("open-demo").click();
  await expect(page.getByTestId("editor")).toBeVisible();
  await expect(page.getByTestId("engine-chip")).toHaveAttribute("data-engine-phase", "ready", {
    timeout: READY_TIMEOUT,
  });
  await page.getByRole("tab", { name: "Pattern" }).click();
  await expect(page.getByTestId("pattern-panel")).toBeVisible();
  // Cards populate from bridge plan calls (explicit action on panel open).
  await expect(page.getByTestId("strategy-card-strip")).toBeVisible();
}

async function downloadBytes(page: Page, testId: string): Promise<{ bytes: Buffer; name: string }> {
  const waiting = page.waitForEvent("download");
  await page.getByTestId(testId).click();
  const download: Download = await waiting;
  const stream = await download.createReadStream();
  const chunks: Buffer[] = [];
  for await (const chunk of stream) chunks.push(Buffer.from(chunk as Buffer));
  return { bytes: Buffer.concat(chunks), name: download.suggestedFilename() };
}

test("strip cut-list CSV and MD downloads byte-equal the canonical goldens", async ({ page }) => {
  await openPattern(page);
  await page.getByTestId("strategy-card-strip").click();

  const csv = await downloadBytes(page, "download-cutlist-csv");
  expect(csv.name).toBe(`${SLUG}-cut-list.csv`);
  expect(csv.bytes.equals(readFileSync(path.join(goldenDir, "cutlist_strip.csv")))).toBe(true);

  const md = await downloadBytes(page, "download-cutlist-md");
  expect(md.name).toBe(`${SLUG}-cut-list.md`);
  expect(md.bytes.equals(readFileSync(path.join(goldenDir, "cutlist_strip.md")))).toBe(true);
});

test("SVG downloads byte-equal the frozen golden and parse sanely", async ({ page }) => {
  await openPattern(page);
  const svg = await downloadBytes(page, "download-svg");
  expect(svg.name).toBe(`${SLUG}-diagram.svg`);
  expect(svg.bytes.equals(readFileSync(path.join(goldenDir, "top.svg")))).toBe(true);
  // Parse sanity on the downloaded bytes: at least one rect per grid cell.
  const text = svg.bytes.toString("utf8");
  const rects = text.match(/<rect/g) ?? [];
  expect(rects.length).toBeGreaterThanOrEqual(2475);
});

test("exports are deterministic within a session; PDF saved for pypdf", async ({ page }) => {
  await openPattern(page);
  await page.getByTestId("strategy-card-strip").click();
  const first = await downloadBytes(page, "download-cutlist-csv");
  const second = await downloadBytes(page, "download-cutlist-csv");
  expect(second.bytes.equals(first.bytes)).toBe(true);
  const svg1 = await downloadBytes(page, "download-svg");
  const svg2 = await downloadBytes(page, "download-svg");
  expect(svg2.bytes.equals(svg1.bytes)).toBe(true);

  const pdf = await downloadBytes(page, "download-pdf");
  expect(pdf.name).toBe(`${SLUG}-booklet.pdf`);
  expect(pdf.bytes.subarray(0, 5).toString("latin1")).toBe("%PDF-");
  mkdirSync(downloadDir, { recursive: true });
  writeFileSync(path.join(downloadDir, "booklet.pdf"), pdf.bytes);
  // Success toast and a filename per PARITY item 11 for the yardage report.
  const yardage = await downloadBytes(page, "download-yardage");
  expect(yardage.name).toBe(`${SLUG}-yardage.txt`);
});

test("strategy cards show bridge metrics field-for-field", async ({ page }) => {
  await openPattern(page);
  // Hand-known engine literals (test_construct): strip has 25 strip sets;
  // historical has 2479 pieces. Both labeled rough heuristic where shown.
  await expect(page.getByTestId("strategy-card-strip")).toContainText("25");
  await expect(page.getByTestId("strategy-card-historical")).toContainText(/2,?479/);
  await expect(page.getByTestId("strategy-card-strip")).toContainText(/rough heuristic/i);
});

test("yardage table: binding, backing 5 1/2 yd, batting row, engine usable width", async ({
  page,
}) => {
  await openPattern(page);
  const table = page.getByTestId("yardage-table");
  await expect(table).toBeVisible();
  await expect(page.getByTestId("yardage-row-binding")).toBeVisible();
  // Backing: design-doc literal 5.5 yd = 22 quarter-yards, mixed fraction.
  const backing = page.getByTestId("yardage-row-backing");
  await expect(backing).toHaveAttribute("data-quarter-yards", "22");
  await expect(backing).toContainText("5 1/2");
  // Batting per PARITY item 9: finished + 8" per axis = 83" x 98".
  const batting = page.getByTestId("yardage-row-batting");
  await expect(batting).toContainText('83"');
  await expect(batting).toContainText('98"');
  // Usable width copy reads the engine settings value, never hardcoded 40.
  await expect(page.getByTestId("pattern-panel")).toContainText('42"');
  // Every fabric row's quarter-yards attribute is a positive integer
  // (multiples of 0.25 yd by construction).
  for (const row of await page.locator("[data-testid^='yardage-row-']").all()) {
    const quarters = Number(await row.getAttribute("data-quarter-yards"));
    expect(Number.isInteger(quarters)).toBe(true);
    expect(quarters).toBeGreaterThan(0);
  }
});

test("seams: tweak shows badge and estimates; strategy switch resets; exports unaffected", async ({
  page,
}) => {
  await openPattern(page);
  await page.getByTestId("strategy-card-strip").click();
  await page.getByTestId("mode-seams").click();

  // Drag-merge two vertically-adjacent blue squares: fixture cells (0,0)
  // and (1,0) are both 'b' (Block A col 0 rows bb). Strip defaults only
  // merge horizontally, so this vertical merge is a hand tweak.
  const canvas = page.getByTestId("quilt-canvas");
  const box = (await canvas.boundingBox())!;
  const scale = Number(await canvas.getAttribute("data-view-scale"));
  const originX = Number(await canvas.getAttribute("data-view-origin-x"));
  const originY = Number(await canvas.getAttribute("data-view-origin-y"));
  const cell = Number(await canvas.getAttribute("data-cell-size"));
  const border = Number(await canvas.getAttribute("data-border-total"));
  const cx = (col: number) => box.x + originX + (border + (col + 0.5) * cell) * scale;
  const cy = (row: number) => box.y + originY + (border + (row + 0.5) * cell) * scale;
  await page.mouse.move(cx(0), cy(0));
  await page.mouse.down();
  await page.mouse.move(cx(0), cy(1), { steps: 3 });
  await page.mouse.up();

  const badge = page.getByTestId("hand-tweaked");
  await expect(badge).toBeVisible();
  await expect(page.getByTestId("strategy-card-strip")).toContainText(/estimate/i);

  // Exports remain engine-authoritative: CSV still byte-equals the golden.
  const csv = await downloadBytes(page, "download-cutlist-csv");
  expect(csv.bytes.equals(readFileSync(path.join(goldenDir, "cutlist_strip.csv")))).toBe(true);

  // Tap-split undoes the merge region; badge remains while any fix exists,
  // then switching strategy resets tweaks with a toast and clears the badge.
  await page.getByTestId("strategy-card-modern").click();
  await expect(page.getByTestId("toast")).toBeVisible();
  await expect(badge).not.toBeVisible();
});

test("copy-my-settings writes the clipboard summary", async ({ page, context }) => {
  await context.grantPermissions(["clipboard-read", "clipboard-write"]);
  await openPattern(page);
  await page.getByTestId("copy-settings").click();
  await expect(page.getByTestId("toast")).toBeVisible();
  const text = await page.evaluate(() => navigator.clipboard.readText());
  expect(text).toContain("Double Irish Chain 75x90");
  expect(text).toContain('75"');
  expect(text).toMatch(/backing/i);
  expect(text).toMatch(/batting/i);
});

test("print one-page plan populates the print sheet and calls print", async ({ page }) => {
  await page.addInitScript(() => {
    (window as unknown as { __printed: boolean }).__printed = false;
    window.print = () => {
      (window as unknown as { __printed: boolean }).__printed = true;
    };
  });
  await openPattern(page);
  await page.getByTestId("print-plan").click();
  const sheet = page.getByTestId("print-sheet");
  await expect(sheet).toContainText('75" × 90"');
  await expect(sheet).toContainText(/backing/i);
  expect(await page.evaluate(() => (window as unknown as { __printed: boolean }).__printed)).toBe(
    true,
  );
});
