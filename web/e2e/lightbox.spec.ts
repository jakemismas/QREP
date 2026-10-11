/**
 * Compare lightbox in the editor (C1b; web-03). The lightbox's rules used to
 * live in a style string that PhotoFlow injected only while it was mounted,
 * so the editor's "Compare with your photo" rendered it unstyled: position
 * static and a transparent scrim at 834d8be, inline under the canvas. Its
 * stylesheet now ships with the component, so it overlays the viewport
 * wherever it mounts.
 *
 * The L0 upload is the same seeded render photo.spec.ts generates (seed 42,
 * level 0, scale 10), and it reads cleanly, so Open in the editor is offered.
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
  // qrep.cli has no __main__ guard, so call the renderer the CLI wraps.
  execFileSync(python, [
    "-c",
    "import sys; from pathlib import Path; from qrep.model import load; from qrep.render import save_render; " +
      "save_render(load(sys.argv[1]), Path(sys.argv[2]), level=0, seed=42, scale=10)",
    path.join(repoRoot, "tests", "fixtures", "double_irish_chain.json"),
    l0Path,
  ]);
  if (!existsSync(l0Path)) throw new Error("fixture render produced no file");
});

test.describe("compare lightbox in the editor", { tag: "@phone" }, () => {
  test("overlays the viewport with a tinted scrim", async ({ page }) => {
    await page.goto("./");
    await page.getByTestId("start-photo").click();
    await page.getByTestId("photo-file-input").setInputFiles(l0Path);
    await expect(page.getByTestId("crop-screen")).toBeVisible();
    await page.getByTestId("crop-analyze").click();
    await expect(page.getByTestId("photo-results")).toBeVisible({ timeout: REVERSE_TIMEOUT });
    await page.getByTestId("open-in-editor").click();
    await expect(page.getByTestId("editor")).toBeVisible();

    await page.getByTestId("open-lightbox").click();
    const lightbox = page.getByTestId("lightbox");
    await expect(lightbox).toBeVisible();

    // Source: Lightbox.css .pf-lb { position: fixed; inset: 0 }. A fixed box
    // with all four insets 0 spans the viewport: x 0, y 0, width and height
    // equal to the viewport's.
    await expect(lightbox).toHaveCSS("position", "fixed");
    const viewport = page.viewportSize();
    if (!viewport) throw new Error("this spec needs a fixed viewport");
    const box = await lightbox.boundingBox();
    expect(box).toEqual({ x: 0, y: 0, width: viewport.width, height: viewport.height });

    // Source: web/src/ui/tokens.css:33, --modal-backdrop: rgba(18, 12, 6, 0.6),
    // set once for both themes. Its alpha 0.6 is above 0, so the scrim tints
    // the editor instead of the rgba(0, 0, 0, 0) web-03 measured.
    const scrim = lightbox.locator(".pf-lb-scrim");
    await expect(scrim).toHaveCSS("background-color", "rgba(18, 12, 6, 0.6)");
    await expect(scrim).toHaveCSS("position", "absolute");

    // Escape closes it (Lightbox's keydown handler), back to the editor.
    await page.keyboard.press("Escape");
    await expect(lightbox).toHaveCount(0);
    await expect(page.getByTestId("editor")).toBeVisible();
  });
});
