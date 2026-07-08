/**
 * S0 feasibility spike (issue #40). Runs the spike page in a real browser
 * against the built site and asserts the gate criteria:
 *
 *  1. The full dependency closure installs in Pyodide in a Web Worker with
 *     every request same-origin (no CDN fetches).
 *  2. The strip cut-list CSV generated inside Pyodide is byte-equal to the
 *     canonical frozen golden tests/golden/cutlist_strip.csv, read from the
 *     repo at test runtime (never a copy under web/).
 *  3. The PDF booklet renders inside Pyodide; bytes are saved for the
 *     native-side pypdf structure checks (tests/test_wasm_artifacts.py).
 *  4. reverse() completes on an L0 render of the fixture with interior grid
 *     dims 45x55 (cols x rows) and wall-clock timing recorded.
 *  5. Photo bytes reach the pipeline via Emscripten MEMFS staging: the page
 *     writes the PNG bytes from JS via pyodide.FS.writeFile and reverse()
 *     reads that path.
 *
 * Expected values are hand-derived from the fixture geometry (design doc:
 * center field 45x55 cells) and the frozen golden file; nothing here is
 * blessed from observed output.
 */
import { expect, test } from "@playwright/test";
import { createHash } from "node:crypto";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import * as path from "node:path";
import { fileURLToPath } from "node:url";

const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const goldenCsvPath = path.join(repoRoot, "tests", "golden", "cutlist_strip.csv");
const outDir = path.join(repoRoot, "web", "test-results", "spike");

interface SpikeResults {
  status: "done" | "failed";
  errors: string[];
  pyodideVersion: string;
  pythonVersion: string;
  packages: Record<string, string>;
  csvB64: string;
  pdfB64: string;
  reverse: {
    rows: number;
    cols: number;
    wallMs: number;
    cellAccuracy: number;
    stageConfidence: Record<string, number>;
    memfsStaged: boolean;
  };
  timings: Record<string, number>;
}

test("S0 spike: closure, cut-list golden, booklet PDF, reverse, MEMFS staging", async ({
  page,
  baseURL,
}) => {
  const origin = new URL(baseURL!).origin;
  const offOrigin: string[] = [];
  page.on("request", (request) => {
    if (new URL(request.url()).origin !== origin) offOrigin.push(request.url());
  });

  await page.goto("./");
  await page.getByTestId("run-spike").click();
  await expect(page.locator("[data-spike-status='done']")).toBeVisible({ timeout: 540_000 });

  const raw = await page.getByTestId("spike-results").textContent();
  expect(raw, "spike page must publish a results JSON").toBeTruthy();
  const results: SpikeResults = JSON.parse(raw!);

  // Save artifacts before asserting so the native pypdf checks and the
  // closing-comment numbers survive any assertion failure below.
  const producedCsv = Buffer.from(results.csvB64, "base64");
  const pdf = Buffer.from(results.pdfB64, "base64");
  mkdirSync(outDir, { recursive: true });
  writeFileSync(path.join(outDir, "booklet.pdf"), pdf);
  writeFileSync(path.join(outDir, "cutlist.csv"), producedCsv);
  writeFileSync(
    path.join(outDir, "spike-report.json"),
    JSON.stringify(
      {
        pyodideVersion: results.pyodideVersion,
        pythonVersion: results.pythonVersion,
        packages: results.packages,
        reverse: results.reverse,
        timings: results.timings,
        csvSha256: sha256(producedCsv),
        pdfBytes: pdf.length,
      },
      null,
      2,
    ),
  );

  // Criterion 1: full closure importable in the worker, same-origin only.
  expect(results.errors).toEqual([]);
  for (const mod of ["numpy", "cv2", "PIL", "pydantic", "reportlab", "svgwrite", "qrep"]) {
    expect(results.packages[mod], `${mod} must import in the worker`).toBeTruthy();
  }
  expect(offOrigin, "no cross-origin (CDN) requests allowed").toEqual([]);

  // Criterion 2: CSV byte-equality against the canonical frozen golden.
  const golden = readFileSync(goldenCsvPath);
  expect(
    producedCsv.equals(golden),
    `wasm cut-list CSV must be byte-equal to tests/golden/cutlist_strip.csv ` +
      `(golden sha256 ${sha256(golden)}, wasm sha256 ${sha256(producedCsv)})`,
  ).toBe(true);

  // Criterion 3: booklet renders in wasm. This is a smoke check only (PDF
  // magic + non-empty document); the authoritative structure gate is the
  // native pypdf run in tests/test_wasm_artifacts.py against these bytes.
  expect(pdf.subarray(0, 5).toString("latin1")).toBe("%PDF-");
  expect(pdf.length).toBeGreaterThan(1024);

  // Criterion 4: reverse() on the L0 render recovers the interior grid.
  // Hand-derived: fixture center field is 45 cols x 55 rows.
  expect(results.reverse.cols).toBe(45);
  expect(results.reverse.rows).toBe(55);
  expect(results.reverse.wallMs).toBeGreaterThan(0);

  // Criterion 5: the PNG bytes were staged from JS onto MEMFS and reverse()
  // consumed the staged path.
  expect(results.reverse.memfsStaged).toBe(true);
});

function sha256(buffer: Buffer): string {
  return createHash("sha256").update(buffer).digest("hex");
}
