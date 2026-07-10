/**
 * S7 size-UI e2e (sprint 3, issue #73). DOM contract: size-block on the
 * crop screen with size-chip-<name>, size-width/size-height fraction
 * inputs, size-unit-toggle; results size-line (tappable both states),
 * size-asked-got, size-inline-editor + size-apply.
 *
 * The plan's flow: enter 86 x 67.5 on the crop screen; results shows the
 * achieved size with the asked-vs-got line; the editor opens at it; edit
 * the size inline from results and see it stick without a re-run.
 * Hand math for the L0 upload (recovered 45x55 grid, cell 12, one border
 * band 30 eighths): cell candidates round_div(8256, 600) = 14 and
 * round_div(6480, 720) = 9 -> min 9; band = max(2, round_div(30*9, 12))
 * = 23; achieved W = 45*9 + 46 = 451 (56 3/8 in), H = 55*9 + 46 = 541
 * (67 5/8 in).
 */
import { execFileSync } from "node:child_process";
import { existsSync, mkdirSync } from "node:fs";
import * as path from "node:path";
import { fileURLToPath } from "node:url";
import { expect, test } from "@playwright/test";

const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const generatedDir = path.join(repoRoot, "tests", "fixtures", "_generated");
const l0Path = path.join(generatedDir, "photo_e2e_l0.png");
const REVERSE_TIMEOUT = 300_000;

test.beforeAll(() => {
  if (existsSync(l0Path)) return;
  mkdirSync(generatedDir, { recursive: true });
  const venvPython = path.join(repoRoot, ".venv", "Scripts", "python.exe");
  const python = process.env.QREP_PYTHON ?? (existsSync(venvPython) ? venvPython : "python");
  execFileSync(python, [
    "-c",
    "import sys; from pathlib import Path; from qrep.model import load; from qrep.render import save_render; " +
      "save_render(load(sys.argv[1]), Path(sys.argv[2]), level=0, seed=42, scale=10)",
    path.join(repoRoot, "tests", "fixtures", "double_irish_chain.json"),
    l0Path,
  ]);
});

test("86 x 67.5 entered at crop flows to achieved size, asked-vs-got, and the editor", async ({
  page,
}) => {
  await page.goto("./");
  await page.getByTestId("start-photo").click();
  await page.getByTestId("photo-file-input").setInputFiles(l0Path);
  await expect(page.getByTestId("crop-screen")).toBeVisible();

  // the size block renders on the crop screen; type the shopper's listing
  await page.getByTestId("size-width").fill("86");
  await page.getByTestId("size-width").press("Enter");
  await page.getByTestId("size-height").fill("67.5");
  await page.getByTestId("size-height").press("Enter");
  await page.getByTestId("crop-analyze").click();

  await expect(page.getByTestId("photo-results")).toBeVisible({ timeout: REVERSE_TIMEOUT });
  // achieved size (hand math in the header): 56 3/8 x 67 5/8, sized state
  const line = page.getByTestId("size-line");
  await expect(line).toHaveAttribute("data-sized", "true");
  await expect(line).toContainText("56 3/8");
  await expect(line).toContainText("67 5/8");
  // asked-vs-got shows because 86 x 67 1/2 was not representable
  const asked = page.getByTestId("size-asked-got");
  await expect(asked).toBeVisible();
  await expect(asked).toContainText("86");
  await expect(asked).toContainText("67 1/2");

  // the editor opens at the achieved dims (the model carries them): the
  // sizing tab's equation box computes from the model, so it must show the
  // hand-known 56 3/8 width
  await page.getByTestId("open-in-editor").click();
  await expect(page.getByTestId("editor")).toBeVisible();
  await page.getByRole("tab", { name: "Sizing" }).click();
  await expect(page.getByTestId("equation-box")).toContainText("56 3/8", { timeout: 60_000 });
});

test("inline size edit from results sticks without a re-run", async ({ page }) => {
  await page.goto("./");
  await page.getByTestId("start-photo").click();
  await page.getByTestId("photo-file-input").setInputFiles(l0Path);
  await expect(page.getByTestId("crop-screen")).toBeVisible();
  await page.getByTestId("crop-analyze").click();
  await expect(page.getByTestId("photo-results")).toBeVisible({ timeout: REVERSE_TIMEOUT });

  // guessed state invites setting the real size
  const line = page.getByTestId("size-line");
  await expect(line).toContainText(/our guess/i);
  await line.click();
  const editor = page.getByTestId("size-inline-editor");
  await expect(editor).toBeVisible();
  await page.getByTestId("size-width").fill("45");
  await page.getByTestId("size-width").press("Enter");
  await page.getByTestId("size-height").fill("54");
  await page.getByTestId("size-height").press("Enter");
  await page.getByTestId("size-apply").click();
  // applies via apply_finished_size: no progress screen, the line updates
  await expect(page.getByTestId("photo-progress")).toHaveCount(0);
  await expect(line).toHaveAttribute("data-sized", "true", { timeout: 60_000 });
  await expect(line).toContainText(/tap to edit/i);
});

test("size block renders usable at phone width", async ({ page }) => {
  await page.setViewportSize({ width: 400, height: 800 });
  await page.goto("./");
  await page.getByTestId("start-photo").click();
  await page.getByTestId("photo-file-input").setInputFiles(l0Path);
  await expect(page.getByTestId("crop-screen")).toBeVisible();
  await expect(page.getByTestId("size-block")).toBeVisible();
  await expect(page.getByTestId("size-chip-king")).toBeVisible();
  await expect(page.getByTestId("crop-analyze")).toBeVisible();
});
