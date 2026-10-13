/**
 * S2 crop-screen e2e (sprint 3, issue #68), on the confirm screen since C3b
 * (issue #101). DOM contract: crop-screen with corner-pin-0..3 rendered
 * IMMEDIATELY on drop (no engine on the critical path), whose data-x and
 * data-y are source pixels, crop-analyze / crop-back, sample bypass, and
 * results "Adjust the crop" returning here seeded with the confirmed quad.
 * The upload is the COMMITTED screenshot composite fixture
 * (tests/fixtures/photoreal/, rights-clean): its quilt sits between chrome
 * bars, so its corners are far from the 15% neutral inset the pins start at.
 *
 * C3b re-expression (docs/sprint-5/REBASELINE.md): nothing detects the quad
 * any more (criteria U3-4), so the snap-in step is gone and the four pins are
 * placed by hand on the fixture's sidecar quad before analyze.
 */
import { readFileSync } from "node:fs";
import * as path from "node:path";
import { fileURLToPath } from "node:url";
import { expect, test, type Page } from "@playwright/test";

const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const screenshotFixture = path.join(
  repoRoot,
  "tests",
  "fixtures",
  "photoreal",
  "screenshot_composite_1400.png",
);
const REVERSE_TIMEOUT = 300_000;

interface Point {
  x: number;
  y: number;
}

/** The fixture's quilt corners in pin order, from its sidecar "quad". */
function sidecarQuad(): Point[] {
  const sidecar = JSON.parse(readFileSync(screenshotFixture.replace(/\.png$/, ".json"), "utf8")) as {
    quad: [number, number][];
  };
  return sidecar.quad.map(([x, y]) => ({ x, y }));
}

/** Percent value of a pin's CSS `top` (its normalized y * 100). */
async function pinTopPercent(page: Page, index: number): Promise<number> {
  const style = await page.getByTestId(`corner-pin-${index}`).getAttribute("style");
  const match = /top:\s*([\d.]+)%/.exec(style ?? "");
  if (!match) throw new Error(`pin ${index} has no top style: ${style}`);
  return Number(match[1]);
}

/** Drags a pin near the target, then nudges it with the arrow keys (Shift for 10 source px) onto it exactly. */
async function placePin(page: Page, index: number, target: Point): Promise<void> {
  const crop = page.getByTestId("crop-screen");
  const width = Number(await crop.getAttribute("data-canvas-width"));
  const height = Number(await crop.getAttribute("data-canvas-height"));
  const pin = page.getByTestId(`corner-pin-${index}`);
  const image = (await page.getByTestId("pin-image").boundingBox())!;
  const box = (await pin.boundingBox())!;
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
  await page.mouse.down();
  await page.mouse.move(image.x + (target.x / width) * image.width, image.y + (target.y / height) * image.height, {
    steps: 4,
  });
  await page.mouse.up();
  await pin.focus();
  for (let round = 0; round < 4; round++) {
    const dx = target.x - Number(await pin.getAttribute("data-x"));
    const dy = target.y - Number(await pin.getAttribute("data-y"));
    if (dx === 0 && dy === 0) break;
    for (const [delta, plus, minus] of [
      [dx, "ArrowRight", "ArrowLeft"],
      [dy, "ArrowDown", "ArrowUp"],
    ] as const) {
      const key = delta > 0 ? plus : minus;
      for (let i = 0; i < Math.floor(Math.abs(delta) / 10); i++) await page.keyboard.press(`Shift+${key}`);
      for (let i = 0; i < Math.abs(delta) % 10; i++) await page.keyboard.press(key);
    }
  }
  await expect(pin).toHaveAttribute("data-x", String(target.x));
  await expect(pin).toHaveAttribute("data-y", String(target.y));
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

  // C3b: no quad snaps in; the pins go by hand onto the sidecar quad, once
  // the photo they map through has loaded
  await expect
    .poll(() => page.getByTestId("pin-image").evaluate((img: HTMLImageElement) => img.naturalWidth))
    .toBeGreaterThan(0);
  const quad = sidecarQuad();
  for (const [index, corner] of quad.entries()) await placePin(page, index, corner);
  await page.getByTestId("crop-analyze").click();
  await expect(page.getByTestId("photo-results")).toBeVisible({ timeout: REVERSE_TIMEOUT });

  // "Adjust the crop" returns to the same confirm screen seeded with the
  // confirmed quad, not the default pins: the quilt's top edge sits at
  // 322 / 1400 = 23% of the frame, past the 15% neutral inset
  await page.getByTestId("adjust-corners").click();
  await expect(crop).toBeVisible();
  expect(await pinTopPercent(page, 0)).toBeGreaterThan(15);
  for (const [index, corner] of quad.entries()) {
    const pin = page.getByTestId(`corner-pin-${index}`);
    await expect(pin).toHaveAttribute("data-x", String(corner.x));
    await expect(pin).toHaveAttribute("data-y", String(corner.y));
  }
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
