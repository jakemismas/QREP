/**
 * S2 crop-screen e2e (sprint 3, issue #68). DOM contract: crop-screen with
 * corner-pin-0..3 rendered IMMEDIATELY on drop (no engine on the critical
 * path), crop-detecting affordance while detect_quad resolves, snap-in of
 * the detected quad, crop-analyze / crop-reset / crop-back, sample bypass,
 * and results "Adjust the crop" returning here seeded with the confirmed
 * quad. The upload is the COMMITTED screenshot composite fixture
 * (tests/fixtures/photoreal/, rights-clean): its quilt sits between chrome
 * bars, so the detected pin positions are far from the 6% default inset and
 * the snap-in is observable.
 */
import * as path from "node:path";
import { fileURLToPath } from "node:url";
import { expect, test } from "@playwright/test";

const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const screenshotFixture = path.join(
  repoRoot,
  "tests",
  "fixtures",
  "photoreal",
  "screenshot_composite_1400.png",
);
const REVERSE_TIMEOUT = 300_000;

/** Percent value of a pin's CSS `top` (its normalized y * 100). */
async function pinTopPercent(page: import("@playwright/test").Page, index: number): Promise<number> {
  const style = await page.getByTestId(`corner-pin-${index}`).getAttribute("style");
  const match = /top:\s*([\d.]+)%/.exec(style ?? "");
  if (!match) throw new Error(`pin ${index} has no top style: ${style}`);
  return Number(match[1]);
}

test("crop screen: pins immediately, quad snaps in, analyze reaches results, adjust returns seeded", async ({
  page,
}) => {
  await page.goto("./");
  await page.getByTestId("start-photo").click();
  await page.getByTestId("photo-file-input").setInputFiles(screenshotFixture);

  // pins render immediately with no engine on the critical path
  const crop = page.getByTestId("crop-screen");
  await expect(crop).toBeVisible();
  await expect(page.getByTestId("corner-pin-0")).toBeVisible();

  // the detected quad snaps in: the screenshot fixture's quilt top edge sits
  // at ~23% of the frame (between the chrome bars), far from the 6% default
  // inset, so a top value well past 15% proves detection replaced the seeds
  await expect(page.getByTestId("crop-detecting")).toHaveCount(0, { timeout: REVERSE_TIMEOUT });
  expect(await pinTopPercent(page, 0)).toBeGreaterThan(15);

  // adjust a pin, then analyze through to results
  const pin = page.getByTestId("corner-pin-0");
  const box = (await pin.boundingBox())!;
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
  await page.mouse.down();
  await page.mouse.move(box.x + box.width / 2 + 8, box.y + box.height / 2 + 8, { steps: 3 });
  await page.mouse.up();
  await page.getByTestId("crop-analyze").click();
  await expect(page.getByTestId("photo-results")).toBeVisible({ timeout: REVERSE_TIMEOUT });

  // "Adjust the crop" returns to the same crop screen seeded with the
  // confirmed quad, not the default pins
  await page.getByTestId("adjust-corners").click();
  await expect(crop).toBeVisible();
  expect(await pinTopPercent(page, 0)).toBeGreaterThan(15);
});

test("sample photo bypasses the crop screen entirely", async ({ page }) => {
  await page.goto("./");
  await page.getByTestId("start-photo").click();
  await page.getByTestId("photo-sample").click();
  // straight to analysis: the crop screen never mounts for the sample
  await expect(page.getByTestId("crop-screen")).toHaveCount(0);
  await expect(page.getByTestId("photo-results")).toBeVisible({ timeout: REVERSE_TIMEOUT });
  await expect(page.getByTestId("crop-screen")).toHaveCount(0);
});
