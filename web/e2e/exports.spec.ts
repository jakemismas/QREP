/**
 * S5 exports e2e (issue #45). DOM contract: pattern-panel (Pattern tab),
 * strategy-card-<historical|strip|modern> (click selects; carry
 * data-selected), per-card metric text from bridge plan output only,
 * hand-tweaked badge (data-testid="hand-tweaked"), yardage-table with
 * yardage-row-<fabricId|binding|backing|batting> rows carrying
 * data-quarter-yards, download buttons download-cutlist-csv / -cutlist-md /
 * -yardage / -svg / -pdf, print-plan + print-sheet, copy-settings, and the
 * Seams mode via mode-seams in the toolbar. The yardage test reads Your
 * pattern's shopping lines instead (C2b, issue #148): shop-binding,
 * shop-backing and shop-batting with data-yards, shop-widths, the
 * strip-width select and the census rows fabric-yards-<fabricId>.
 *
 * Golden discipline: byte-compares read the CANONICAL files from
 * tests/golden/ at test runtime. No snapshot APIs. Known literals: strip
 * strip_set_count 25 and historical piece_count 2479 (test_construct),
 * backing 23 quarter yards = 5 3/4 yd (MATH.md V-BACK-09), batting 83" x 98"
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

async function openSamplePattern(page: Page): Promise<void> {
  await page.goto("./");
  await page.getByTestId("see-sample").click();
  await expect(page.getByTestId("your-pattern")).toBeVisible();
  await expect(page.getByTestId("engine-chip")).toHaveAttribute("data-engine-phase", "ready", {
    timeout: READY_TIMEOUT,
  });
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
  // C2a (issue #96; REBASELINE.md): the sample pattern's one Download
  // pattern (PDF) button, twice. The CSV, SVG and yardage parts left this
  // test; the golden tests keep pinning those bytes.
  await openSamplePattern(page);
  const first = await downloadBytes(page, "download-pattern");
  const pdf = await downloadBytes(page, "download-pattern");
  expect(pdf.bytes.equals(first.bytes)).toBe(true);
  // SLUG is PARITY item 11's slug, and the one pattern file is the pattern
  // name in kebab case plus .pdf (REBASELINE.md criterion P27).
  expect(pdf.name).toBe(`${SLUG}.pdf`);
  expect(pdf.bytes.subarray(0, 5).toString("latin1")).toBe("%PDF-");
  mkdirSync(downloadDir, { recursive: true });
  writeFileSync(path.join(downloadDir, "booklet.pdf"), pdf.bytes);
});

test("strategy cards show bridge metrics field-for-field", async ({ page }) => {
  await openPattern(page);
  // Hand-known engine literals (test_construct): strip has 25 strip sets;
  // historical has 2479 pieces. Both labeled rough heuristic where shown.
  await expect(page.getByTestId("strategy-card-strip")).toContainText("25");
  await expect(page.getByTestId("strategy-card-historical")).toContainText(/2,?479/);
  await expect(page.getByTestId("strategy-card-strip")).toContainText(/rough heuristic/i);
});

test("yardage on Your pattern: binding, backing 5 3/4 yd, batting, both widths", async ({
  page,
}) => {
  // C2b (issue #148; REBASELINE.md): the yardage table's checks move onto
  // Your pattern's shopping lines for the sample, every amount from the
  // engine summary. The summary is export_pattern's, which builds the whole
  // pattern PDF in the browser engine, so its first arrival gets 60 s.
  await openSamplePattern(page);
  await expect(page.getByTestId("shopping-lines")).toBeVisible({ timeout: 60_000 });

  // The binding line shows as the summary gives it. The summary carries no
  // strip count yet (a later commit adds it), so only its amount is checked.
  const binding = page.getByTestId("shop-binding");
  await expect(binding).toBeVisible();
  expect(Number(await binding.getAttribute("data-yards"))).toBeGreaterThan(0);

  // V-BACK-09: 2 vertical panels x 98 in = 1568 e, + 72 e pieced allowance =
  // 1640 e; ceil(1640 / 72) = 23 quarter yards = 23 / 4 = 5.75 yd.
  const backing = page.getByTestId("shop-backing");
  await expect(backing).toHaveAttribute("data-yards", "5.75");
  await expect(backing.locator(".sl-amount")).toHaveText("5 3/4 yd");

  // V-BATT-01: the finished 75 x 90 in plus 4 in a side, (75 + 8) x (90 + 8)
  // in = 83 x 98 in.
  await expect(page.getByTestId("shop-batting")).toContainText("83 x 98 in");

  // Both widths named (MATH.md D-16). The cutting width offers 40 in as its
  // default (MATH.md section 1.3, U), but the fixture stores wof 336 e =
  // 42 in until A6, so the select and the copy show 42 in for cutting (MATH.md
  // section 3.2, row web/e2e/exports.spec.ts); the backing is the 42 in
  // default (B, backing_width 336 e).
  const stripWidth = page.getByTestId("strip-width");
  await expect(stripWidth.locator("option", { hasText: "40 in (default)" })).toHaveCount(1);
  await expect(stripWidth).toHaveValue("336");
  const widths = page.getByTestId("shop-widths");
  await expect(widths).toContainText("strips at 42 in");
  await expect(widths).toContainText("fabric 42 in wide");

  // A positive amount on every fabric line, each a whole number of quarter
  // yards. The fixture's palette has two fabrics, b and c, and the top uses
  // both, so both rows carry yards.
  const fabricYards = page.locator("[data-testid^='fabric-yards-']");
  await expect(fabricYards).toHaveCount(2);
  for (const row of await fabricYards.all()) {
    const yards = Number(await row.getAttribute("data-yards"));
    expect(yards).toBeGreaterThan(0);
    expect(Number.isInteger(yards * 4)).toBe(true);
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
