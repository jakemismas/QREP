/**
 * S8 verdict-surface e2e (sprint 3, issue #74; UI-SPEC sections 3-4).
 * Uploads the committed solid-fabric fixture (rights-clean, generated):
 * a quilt-free solid rectangle reads as verdict=no_grid, landing on the
 * failure panel. Asserts the honest-messaging contract end to end:
 * failure pill with no percentage, disclosure collapsed by default,
 * banner on expand, lightbox still offered, and the blank-grid escape.
 * The solid fixture's recovered palette is k=8 phantom splits (S0
 * fidelity evidence on #74), which the frozen trust gate excludes, so
 * "Start in the editor" must open the PLAIN blank grid (Background +
 * Accent 1), not recovered fabrics.
 */
import * as path from "node:path";
import { fileURLToPath } from "node:url";
import { expect, test } from "@playwright/test";

const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const solidFixture = path.join(repoRoot, "tests", "fixtures", "photoreal", "solid_fabric_1400.png");
const REVERSE_TIMEOUT = 300_000;

test("no_grid: failure panel, collapsed disclosure, banner on expand, plain blank escape", async ({
  page,
}) => {
  await page.goto("./");
  await page.getByTestId("start-photo").click();
  await page.getByTestId("photo-file-input").setInputFiles(solidFixture);

  // crop screen with default pins (a solid rectangle detects no quad; the
  // cold-start contract keeps the screen usable), analyze straight through
  await expect(page.getByTestId("crop-screen")).toBeVisible();
  await page.getByTestId("crop-analyze").click();
  const results = page.getByTestId("photo-results");
  await expect(results).toBeVisible({ timeout: REVERSE_TIMEOUT });
  await expect(results).toHaveAttribute("data-verdict", "no_grid");

  // failure pill: accent statement, NO percentage
  const pill = page.getByTestId("overall-pill");
  await expect(pill).toHaveText("Could not read this photo");
  await expect(pill).toHaveAttribute("data-failure", "true");

  // failure panel owns the primary actions; the side stack drops its editor
  // entry (opening a wrong model contradicts the verdict) but keeps
  // "Adjust the crop" - UI-SPEC section 1: from results, success OR failure
  await expect(page.getByTestId("failure-panel")).toBeVisible();
  await expect(page.getByTestId("failure-panel")).toContainText(
    "We could not find a square grid in this photo",
  );
  await expect(page.getByTestId("open-in-editor")).toHaveCount(0);
  await expect(page.getByTestId("adjust-corners")).toBeVisible();
  await expect(page.getByTestId("failure-adjust-crop")).toBeVisible();

  // evidence collapsed by default: disclosure present, banner not visible
  const disclosure = page.getByTestId("verdict-disclosure");
  await expect(disclosure).toBeVisible();
  await expect(page.getByTestId("wrong-banner")).not.toBeVisible();

  // expand: the persistent this-is-wrong banner shows above the quilt
  await page.getByTestId("verdict-disclosure-summary").click();
  await expect(page.getByTestId("wrong-banner")).toHaveText(
    "This reading is wrong - shown only to help you see what went wrong.",
  );

  // the side-by-side lightbox stays available on failure
  await expect(page.getByTestId("open-lightbox")).toBeVisible();

  // blank-grid escape: solid's k=8 palette is gate-excluded, so the editor
  // opens the PLAIN blank grid - exactly the two default fabrics
  await page.getByTestId("failure-start-editor").click();
  await expect(page.getByTestId("editor")).toBeVisible();
  await expect(page.getByTestId("fabric-row-bg")).toBeVisible();
  await expect(page.getByTestId("fabric-row-a1")).toBeVisible();
  await expect(page.locator('[data-testid^="fabric-row-"]')).toHaveCount(2);
});
