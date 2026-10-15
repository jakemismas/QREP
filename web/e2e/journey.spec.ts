/**
 * The quilter journey (issue #280): the built site driven the way a quilter
 * uses it, on a touch phone at 390 x 844 and a desktop at 1280 x 800. It
 * checks that she gets the right pattern, not only that screens render, and
 * that every screen keeps the plain-language rules (RESET.md section 6)
 * through helpers/grandma.ts. Each later UI ticket adds its own steps here.
 *
 * Today's path: the start screen, See a sample pattern, Your pattern, and
 * Download pattern (PDF). Each step leaves a full-page screenshot under
 * test-results/spike/journey/, which CI uploads as spike-artifacts, and the
 * run composes them into contact-sheet.png there, beside violations.json
 * (every finding of the run) and each size's downloaded PDF.
 *
 * Both sizes run in one test, so the allowlist comparison sees every step
 * at every size: grandma-allowlist.json fails the run on a violation it does
 * not list and on an entry the run did not see.
 */
import { mkdirSync, writeFileSync } from "node:fs";
import * as path from "node:path";
import { fileURLToPath } from "node:url";
import { devices, expect, test, type BrowserContextOptions, type Page } from "@playwright/test";
import { writeContactSheet, type SheetRow } from "./helpers/contact-sheet";
import { check, compareWithAllowlist, loadAllowlist, type Violation } from "./helpers/grandma";
import { pdfText } from "./helpers/pdf-text";

const journeyDir = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "..",
  "test-results",
  "spike",
  "journey",
);
const READY_TIMEOUT = 300_000;
const iPhone = devices["iPhone 13"];

const SIZES: { name: string; title: string; cellWidth: number; options: BrowserContextOptions }[] = [
  {
    name: "phone",
    title: "Phone, 390 x 844, touch",
    cellWidth: 390,
    options: {
      viewport: { width: 390, height: 844 },
      userAgent: iPhone.userAgent,
      deviceScaleFactor: iPhone.deviceScaleFactor,
      isMobile: true,
      hasTouch: true,
    },
  },
  {
    name: "desktop",
    title: "Desktop, 1280 x 800",
    cellWidth: 800,
    options: { viewport: { width: 1280, height: 800 }, isMobile: false, hasTouch: false },
  },
];

// The demo quilt, worked by hand from tests/fixtures/double_irish_chain.json.
//
// The center is 55 rows by 45 columns of squares, each 12 eighths (1 1/2")
// finished. In 5 x 5 blocks that is 45 / 5 = 9 blocks across and 55 / 5 = 11
// down, 9 x 11 = 99 blocks, of two kinds:
//   block A (rows 0 to 4, columns 0 to 4): bbcbb, bbbbb, cbbbc, bbbbb, bbcbb,
//     so b = 4 + 5 + 3 + 5 + 4 = 21 and c = 1 + 0 + 2 + 0 + 1 = 4;
//   block B (rows 0 to 4, columns 5 to 9): bcccb, ccccc, ccccc, ccccc, bcccb,
//     so b = 2 + 0 + 0 + 0 + 2 = 4 and c = 3 + 5 + 5 + 5 + 3 = 21.
// They alternate as a checkerboard with A in the corners: block row r,
// block column k holds A when r + k is even. The 6 even block rows (0, 2,
// 4, 6, 8, 10) hold A at the 5 even columns (0, 2, 4, 6, 8), and the 5 odd
// rows at the 4 odd columns: 6 x 5 + 5 x 4 = 30 + 20 = 50 A, and
// 99 - 50 = 49 B.
//   Chain blue (b):       50 x 21 + 49 x 4 = 1,050 + 196 = 1,246 squares.
//   Background cream (c): 50 x 4 + 49 x 21 = 200 + 1,029 = 1,229 squares.
//   Check: 1,246 + 1,229 = 2,475 = 55 x 45.
// The palette has those two fabrics, so Your pattern lists 2.
//
// The finished size adds the one cream border, 30 eighths (3 3/4"), on
// every side; the binding wraps the edge and adds nothing:
//   width  45 x 12 + 2 x 30 = 540 + 60 = 600 eighths = 75";
//   height 55 x 12 + 2 x 30 = 660 + 60 = 720 eighths = 90".
// The screen prints eighths as whole inches with an inch mark
// (formatEighths), and the PDF as 75" wide by 90" tall (qrep/export/pdf.py,
// the introduction) or 75" x 90" (size() in qrep/export/pattern/document.py).
const FABRICS = [
  { id: "b", name: "Chain blue", squares: "1,246 squares" },
  { id: "c", name: "Background cream", squares: "1,229 squares" },
];
const WIDTH = '75"';
const HEIGHT = '90"';
// slugify("Double Irish Chain 75x90"): lowercase, then each run of
// characters outside a-z and 0-9 becomes one hyphen.
const PDF_NAME = "double-irish-chain-75x90.pdf";

// The success toast leaves after 3.6 s (DISMISS_MS in src/ui/Toast.tsx), so
// a check that takes longer would see it or not by chance. Once the
// journey sets the flag, that one timer never fires, and the step after
// the download is checked with the toast she saw. The step asserts the
// toast is still there afterwards, so a changed delay fails loudly.
function holdToast(): void {
  const realSetTimeout = window.setTimeout.bind(window);
  const held = ((handler: TimerHandler, timeout?: number, ...args: unknown[]) => {
    if ((window as unknown as { __journeyHoldToast?: boolean }).__journeyHoldToast && timeout === 3600) {
      return realSetTimeout(() => undefined, 0);
    }
    return realSetTimeout(handler, timeout, ...args);
  }) as typeof window.setTimeout;
  window.setTimeout = held;
}

const escapeRegExp = (text: string) => text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

async function waitForEngine(page: Page): Promise<void> {
  await expect(page.getByTestId("engine-chip")).toHaveAttribute("data-engine-phase", "ready", {
    timeout: READY_TIMEOUT,
  });
}

async function walk(page: Page, size: (typeof SIZES)[number], row: SheetRow, violations: Violation[]) {
  const step = async (name: string, label: string) => {
    await page.evaluate(() => document.fonts.ready);
    const png = await page.screenshot({ fullPage: true, animations: "disabled", scale: "css" });
    writeFileSync(path.join(journeyDir, `${size.name}-${row.shots.length + 1}-${name}.png`), png);
    row.shots.push({ label, png });
    violations.push(...(await check(page, name)));
  };

  // 1. The start screen, once the header says the app is ready.
  await page.goto("./");
  await expect(page.getByTestId("see-sample")).toBeVisible();
  await waitForEngine(page);
  await step("start", "Start screen");

  // 2. See a sample pattern opens Your pattern on the demo quilt.
  await page.getByTestId("see-sample").click();
  const screen = page.getByTestId("your-pattern");
  await expect(screen).toBeVisible();
  await expect(screen).toHaveAttribute("data-source", "sample");
  await waitForEngine(page);
  await expect(page.getByTestId("method-line")).toBeVisible();
  await expect(page.getByTestId("pattern-working")).toHaveCount(0);

  const census = page.getByTestId("fabric-census");
  await expect(census.locator("li")).toHaveCount(FABRICS.length);
  await expect(census.locator("[data-testid^='fabric-count-']")).toHaveCount(FABRICS.length);
  const letters = new Map<string, string>();
  for (const fabric of FABRICS) {
    const count = page.getByTestId(`fabric-count-${fabric.id}`);
    await expect(count).toBeVisible();
    await expect(count).toHaveText(fabric.squares);
    await expect(census.locator("li", { has: count })).toContainText(fabric.name);
    const letter = ((await page.getByTestId(`fabric-letter-${fabric.id}`).textContent()) ?? "").trim();
    expect(letter, `${fabric.name} shows a letter`).toMatch(/^\S+$/);
    letters.set(fabric.name, letter);
  }
  expect(new Set(letters.values()).size, "no two fabrics share a letter").toBe(FABRICS.length);
  await expect(screen.locator(".qc-size")).toBeVisible();
  await expect(screen.locator(".qc-size")).toHaveText(`${WIDTH} × ${HEIGHT} finished`);
  await expect(page.getByTestId("ruler-x-end")).toHaveText(WIDTH);
  await expect(page.getByTestId("ruler-y-end")).toHaveText(HEIGHT);
  await step("your-pattern", "Your pattern");

  // 3. Download pattern (PDF).
  await page.evaluate(() => {
    (window as unknown as { __journeyHoldToast: boolean }).__journeyHoldToast = true;
  });
  const waiting = page.waitForEvent("download");
  await page.getByTestId("download-pattern").click();
  const download = await waiting;
  const chunks: Buffer[] = [];
  for await (const chunk of await download.createReadStream()) chunks.push(Buffer.from(chunk as Buffer));
  const bytes = Buffer.concat(chunks);
  writeFileSync(path.join(journeyDir, `${size.name}-${PDF_NAME}`), bytes);
  expect(download.suggestedFilename()).toBe(PDF_NAME);
  const toast = page.getByTestId("toast");
  await expect(toast).toHaveAttribute("data-tone", "success");
  await expect(page.getByTestId("download-pattern")).toHaveAttribute("data-state", "idle");
  await expect(page.getByTestId("pattern-error")).toHaveCount(0);
  await waitForEngine(page);
  await step("downloaded", "Pattern downloaded");
  await expect(toast, "the toast stayed for the check").toBeVisible();

  // The PDF says the same size and every letter Your pattern shows, each
  // beside its fabric's name.
  expect(bytes.subarray(0, 5).toString("latin1")).toBe("%PDF-");
  const text = pdfText(bytes);
  writeFileSync(path.join(journeyDir, `${size.name}-pattern-text.txt`), text);
  expect(text, "the PDF states the finished size").toMatch(
    new RegExp(`(^|\\s)${escapeRegExp(WIDTH)} (wide by|x) ${escapeRegExp(HEIGHT)}`),
  );
  for (const [name, letter] of letters) {
    const n = escapeRegExp(name);
    const l = escapeRegExp(letter);
    expect(text, `the PDF labels ${name} with ${letter}`).toMatch(
      new RegExp(`(^|\\s)(${n} ${l}|${l} ${n})(\\s|$)`),
    );
  }
}

test("a quilter opens the sample, reads her pattern and downloads it, on a phone and a desktop", async ({
  browser,
  baseURL,
  page,
}) => {
  mkdirSync(journeyDir, { recursive: true });
  const allowlist = loadAllowlist();
  const violations: Violation[] = [];
  const rows: SheetRow[] = [];
  // The sheet is most useful when a step fails, so it is written either way,
  // and the journey's own error, if any, is the one the run reports.
  const failures: unknown[] = [];
  try {
    for (const size of SIZES) {
      const row: SheetRow = { title: size.title, cellWidth: size.cellWidth, shots: [] };
      rows.push(row);
      const context = await browser.newContext({ ...size.options, baseURL });
      try {
        await context.addInitScript(holdToast);
        await walk(await context.newPage(), size, row, violations);
      } finally {
        await context.close();
      }
    }
  } catch (error) {
    failures.push(error);
  }
  writeFileSync(path.join(journeyDir, "violations.json"), `${JSON.stringify(violations, null, 2)}\n`);
  try {
    await writeContactSheet(page, rows, path.join(journeyDir, "contact-sheet.png"));
  } catch (error) {
    failures.push(error);
  }
  if (failures.length > 0) throw failures[0];

  const { unlisted, stale } = compareWithAllowlist(violations, allowlist);
  expect(
    { unlisted, stale },
    "plain-language check: fix each unlisted violation, and remove each stale entry from " +
      "e2e/grandma-allowlist.json",
  ).toEqual({ unlisted: [], stale: [] });
});
